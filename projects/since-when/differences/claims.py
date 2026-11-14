"""Claims: single statements of one edition, checked against the whole article of another.

The pair classifier (classify.py) sees two passages, and its rows speak about two articles: a
fact "missing" in the other edition is often in a passage the pair did not include, and two
numbers that stand near each other often measure different things. Here a row is only a
proposal. Each proposal becomes a claim, one statement with what it is about, and the claim is
looked up in every passage of the other edition as it stood on the same date
(gapfinder/evidence.py, in MariaDB). The model then reads the claim against the passages found
and gives one verdict, with an exact quote:

    supported      a passage states the same fact
    contradicted   a passage says something else about the same thing
    not_mentioned  no passage states it

Claims come from two places: the classifier's rows (a missing fact's quote; both quotes of a
numbers or contradiction row), and the figures and dates the model lists for a passage on its
own (extract). What a verdict does to a row:

    missing fact, not_mentioned   stays a missing fact, now checked against the whole article
    missing fact, supported       no finding: the fact is elsewhere in the article (set aside,
                                  with the passage that states it)
    any claim, contradicted       a numbers or contradiction finding between the claim and the
                                  quote that contradicts it, wherever in the article that is
    numbers or contradiction row with no contradicted claim: no finding (set aside)
    framing                       unchanged; framing is about words, not checked here

Three steps, the middle one in the database:

    python -m differences.claims claims PAIRS.jsonl ROWS.jsonl [--extract] > CLAIMS.jsonl
    python -m gapfinder.evidence search CLAIMS.jsonl > EVIDENCE.jsonl
    python -m differences.claims judge EVIDENCE.jsonl PAIRS.jsonl ROWS.jsonl --out DIR

DIR gets differences.jsonl (the finding rows, in the shape of classify.py's with extra fields),
set-aside.jsonl (rows and claims that are no finding, each with the verdict and the passage that
settled it) and verdicts.jsonl (every claim with its verdict). Model answers are cached under
$DIFFERENCES_CLAIMS_CACHE; --offline never calls the model.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import classify, lexicon, llm

PROMPT_VERSION = 1
CACHE_DIR = Path(os.environ.get("DIFFERENCES_CLAIMS_CACHE",
                                Path(__file__).resolve().parent.parent / "data" / "differences" / "claims-cache"))
OFFLINE = False
LANGS = ("fi", "sv", "en")
MAX_CLAIMS = 10        # figures and dates listed for one passage
CHECKED = ("missing_fact", "numbers", "contradiction")
VERDICTS = ("supported", "contradicted", "not_mentioned")

JUDGE = """You check one claim from one language edition of Wikipedia against passages of another edition's article on the same topic. The passages were picked by a search over the whole article: the ones nearest to the claim in meaning and the ones that share its names and numbers. They are in the article's order and may be in another language than the claim. Decide what the other edition says about the claim's point.

First say what the claim is about: who, which event, which quantity, at which moment, where. Then give one verdict:

- supported: a passage states the same fact. Other words, another language and less precision all count: "in the spring of 1920" supports "12 April 1920", and "more than 400 ships" supports "430 ships". An approximate figure supports an exact one only when the exact one rounds to it: "about 5,000" supports "4,900" and not "5,600".
- contradicted: a passage makes a statement about the same thing and both cannot be true: another figure for the same quantity, another date for the same event, another actor, place, cause or outcome. Both statements must be about the very same thing. Not contradictions: two different events (a treaty's signing and its ratification), two different quantities (a whole army and the part of it that fought; a planned strength and an actual one; the dead and all casualties), the same quantity at two moments (a garrison in March and in May), two steps of one course of events. If the passages give the claim's figure in one place and another figure elsewhere, the claim is supported.
- not_mentioned: no passage states the fact and none contradicts it. A passage may cover the same event and leave this fact out; that is still not_mentioned.

Rules:
- quote is copied character for character from one passage, in its own language, never translated, one sentence or shorter. For supported it is the statement of the fact; for contradicted the statement that disagrees; for not_mentioned the sentence about the same event where the fact would belong, or empty when no passage covers the event.
- passage is the number of the passage the quote is from, 0 when the quote is empty.
- evidence_about says what the quoted sentence is about, as exactly as you said what the claim is about. If the two are not about the same thing, the verdict cannot be contradicted.
- difference is "figure" when the claim is contradicted by another figure for the same quantity (a count, date, duration or percentage), "fact" when it is contradicted in another way, "none" otherwise.
- note is one neutral English sentence that names the editions by language and says what each says about the point, for example "The Swedish article gives about 400 ships for the fleet that sailed in June 1920; the English article gives 430." Keep hedges and attributions ("according to", "about"). Never say which edition is right.
- Judge only from the passages given. Do not use what you know about the topic."""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "about": {"type": "string"},
        "evidence_about": {"type": "string"},
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "difference": {"type": "string", "enum": ["figure", "fact", "none"]},
        "passage": {"type": "integer"},
        "quote": {"type": "string"},
        "note": {"type": "string"},
    },
    "required": ["about", "evidence_about", "verdict", "difference", "passage", "quote", "note"],
    "additionalProperties": False,
}

EXTRACT = f"""You list the figures and dates in one passage of a Wikipedia article, so that each can be looked up in another language edition's article on the same topic. List at most {MAX_CLAIMS} claims, the ones that matter most for the topic first. A claim is a single statement with a figure another article could give differently:

- a count or size: men in a force, casualties, participants, votes, seats, a percentage, a sum
- a date of a named event: when something began, ended, was signed, banned, founded, surrendered
- a duration or a distance

For each claim:
- quote: the shortest span of the passage that carries the claim with its figure, copied character for character, in the passage's language, never translated, one sentence or shorter.
- about: in English, what the figure measures, so exactly that a reader who has not seen the passage could not confuse it with a neighbouring figure: which force, event, person or place, at which moment. For example "number of ships in the fleet that sailed from the harbour on 3 June 1920", "date on which the fortress surrendered to the besiegers", "strength of the northern brigade when it began its retreat in March".
- kind: "count", "date" or "duration".
- value: the figure as the passage writes it, with its hedge ("about 400", "3 June 1920", "over 2,000").

Skip years of birth and death, page numbers, figures inside titles and names, and dates the passage gives only as a year when the year is the topic's own frame (a war of 1914-1918). If the passage has no such claim, return an empty list."""

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "quote": {"type": "string"},
                    "about": {"type": "string"},
                    "kind": {"type": "string", "enum": ["count", "date", "duration"]},
                    "value": {"type": "string"},
                },
                "required": ["quote", "about", "kind", "value"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["claims"],
    "additionalProperties": False,
}


# --- the model, cached ---------------------------------------------------------------------------

def _json(content):
    content = content.strip()
    start, end = content.find("{"), content.rfind("}")
    return json.loads(content[start:end + 1] if start >= 0 and end > start else content)


def _ask(kind, messages, schema, cfg, valid):
    """The model's parsed answer to `messages`, from the cache when it is there.

    Only an answer that parses and that `valid` accepts is cached; another is asked again, three
    times in all, and the last one is returned as it is.
    """
    opts = {k: v for k, v in llm.options().items() if k != "max_tokens"}
    key = hashlib.sha256(json.dumps([kind, PROMPT_VERSION, cfg[0], cfg[2], opts, messages],
                                    ensure_ascii=False).encode()).hexdigest()
    path = CACHE_DIR / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())["answer"]
    if OFFLINE:
        raise LookupError("not in the cache (offline)")
    answer = None
    for _ in range(3):
        try:
            answer = _json(llm.chat_json(messages, schema, cfg))
        except ValueError:
            continue
        if isinstance(answer, dict) and valid(answer):
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"kind": kind, "model": cfg[2], "answer": answer}, ensure_ascii=False))
            return answer
    if not isinstance(answer, dict):
        raise ValueError("no answer that parses")
    return answer


# --- claims --------------------------------------------------------------------------------------

_END = re.compile(r"(?<![\s.(][A-ZÅÄÖ]\.)(?<=[.!?])[\"”’)]?\s+(?=[\"“”(]?[A-ZÅÄÖÜ0-9])|\n+")


def sentences(text):
    """(start, end) of each sentence of text, in order. A date such as "16. marraskuuta" and
    initials such as "C. G. E." do not end a sentence."""
    out, start = [], 0
    for m in list(_END.finditer(text)) + [None]:
        end = m.start() if m else len(text)
        if text[start:end].strip():
            out.append((start, end))
        start = m.end() if m else end
    return out


def sentence(quote, text, limit=600):
    """The whole sentence, or sentences, of text that quote is part of; quote itself if it is not in text."""
    at = text.find(quote)
    spans = [(s, e) for s, e in sentences(text) if s < at + len(quote) and e > at] if at >= 0 else []
    whole = text[spans[0][0]:spans[-1][1]].strip() if spans else quote
    return whole if len(whole) <= limit else quote


def _claim(pair, side, other, quote, origin, about="", kind="", value="", row=None):
    p, target = pair[side], pair[other]
    ident = hashlib.sha1(json.dumps([pair["wikidata_id"], pair["as_of"], p["lang"], target["lang"], quote],
                                    ensure_ascii=False).encode()).hexdigest()[:16]
    return {"claim_id": ident, "wikidata_id": pair["wikidata_id"], "as_of": pair["as_of"],
            "pair_id": pair["pair_id"], "lang": p["lang"], "title": p.get("title", ""),
            "chunk_id": p.get("chunk_id"), "section": p.get("section", ""), "chunk_no": p.get("chunk_no", 0),
            "rev_id": p.get("rev_id"), "quote": quote, "text": sentence(quote, p["text"]),
            "about": about, "kind": kind, "value": value, "origin": origin, "row": row,
            "target_lang": target["lang"], "target_title": target.get("title", ""),
            "always": [target["chunk_id"]] if target.get("chunk_id") is not None else []}


def row_claims(pair, rows):
    """The claims behind the classifier's rows of one pair. `rows` are the pair's rows in order;
    each claim names its row by position."""
    out = []
    for n, row in enumerate(rows):
        if row["type"] not in CHECKED:
            continue
        for side, other in (("a", "b"), ("b", "a")):
            quote = row["quote_" + side]
            if not quote:
                continue
            if row["type"] == "missing_fact" and row.get("missing_in") not in (None, pair[other]["lang"]):
                continue   # the quote of the passage said to lack the fact only shows where it belongs
            if row["type"] == "missing_fact" and row.get("missing_in") is None and side == "b" and row["quote_a"]:
                continue   # no edition named and two quotes: the first is the fact
            out.append(_claim(pair, side, other, quote, "classifier", about=row["summary"], row=n))
    return out


def _passage(p):
    where = f"section \"{p['section']}\"" if p.get("section") else "lead"
    return f"{lexicon.LANG_NAME.get(p['lang'], p['lang'])} Wikipedia, \"{p.get('title', '')}\", {where}"


def extract(passage, cfg):
    """The figures and dates of one passage, as {"quote", "about", "kind", "value"}, quotes verbatim."""
    messages = [{"role": "system", "content": EXTRACT},
                {"role": "user", "content": f"Passage ({_passage(passage)}):\n<<<\n{passage['text']}\n>>>"}]
    answer = _ask("extract", messages, EXTRACT_SCHEMA, cfg, lambda a: isinstance(a.get("claims"), list))
    out = []
    for c in answer.get("claims") or []:
        quote = classify.locate(str(c.get("quote") or ""), passage["text"])
        if quote and str(c.get("about") or "").strip():
            out.append({"quote": quote, "about": c["about"].strip(), "kind": c.get("kind") or "",
                        "value": str(c.get("value") or "")})
    return out[:MAX_CLAIMS]


def extracted_claims(pairs, cfg, workers=8):
    """The figures and dates of every passage of `pairs`, each as a claim against the edition its
    passage is paired with. One model call per distinct passage text."""
    passages = {}
    for pair in pairs:
        for side in ("a", "b"):
            passages.setdefault(pair[side]["text"], pair[side])

    def one(p):
        try:
            return extract(p, cfg)
        except Exception as e:
            print(f"claims: extract {p.get('lang')} {p.get('chunk_id')}: {e}; no claims, a re-run retries it", file=sys.stderr)
            return []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        found = dict(zip(passages, pool.map(one, passages.values())))
    out = {}
    for pair in pairs:
        for side, other in (("a", "b"), ("b", "a")):
            for c in found[pair[side]["text"]]:
                claim = _claim(pair, side, other, c["quote"], "extract", c["about"], c["kind"], c["value"])
                if claim["claim_id"] in out:   # the passage is paired with two passages of this edition
                    out[claim["claim_id"]]["always"] += claim["always"]
                else:
                    out[claim["claim_id"]] = claim
    return list(out.values())


# --- the verdict ---------------------------------------------------------------------------------

def _judge_messages(claim):
    source = {"lang": claim["lang"], "title": claim["title"], "section": claim["section"]}
    lines = [f"Claim, from {_passage(source)}:", f"<<<\n{claim['text']}\n>>>"]
    if claim["text"] != claim["quote"]:
        lines.append(f"The part to check: \"{claim['quote']}\"")
    if claim.get("about"):
        lines.append(("What it measures: " if claim["origin"] == "extract" else "Why it was picked: ") + claim["about"])
    lines.append(f"\nPassages of {lexicon.LANG_NAME.get(claim['target_lang'], claim['target_lang'])} Wikipedia, "
                 f"\"{claim['target_title']}\" ({len(claim['evidence']['passages'])} of the article's "
                 f"{claim['evidence']['searched']}):")
    for n, p in enumerate(claim["evidence"]["passages"], 1):
        where = f"section \"{p['section']}\"" if p["section"] else "lead"
        lines.append(f"\nPassage {n} ({where}):\n<<<\n{p['text']}\n>>>")
    return [{"role": "system", "content": JUDGE}, {"role": "user", "content": "\n".join(lines)}]


def judge(claim, cfg):
    """The verdict on a claim that carries its `evidence` (gapfinder.evidence.search).

    {"verdict", "difference", "about", "evidence_about", "note", "quote", "passage"}: quote is an
    exact substring of the passage it names (a dict of the evidence), or "" with passage None. A
    supported or contradicted verdict whose quote is in none of the passages is asked again and,
    if it stays that way, becomes "unchecked".
    """
    passages = claim["evidence"]["passages"]

    def find(answer):
        """(exact quote, passage) of the answer's quote: in the passage it names, else in any."""
        raw = str(answer.get("quote") or "")
        named = answer.get("passage")
        order = ([passages[named - 1]] if isinstance(named, int) and 1 <= named <= len(passages) else []) + passages
        for p in order:
            quote = classify.locate(raw, p["text"])
            if quote:
                return quote, p
        return "", None

    def valid(answer):
        return answer.get("verdict") in VERDICTS and (answer["verdict"] == "not_mentioned" or find(answer)[1] is not None)

    if not passages:
        return {"verdict": "not_mentioned", "difference": "none", "about": claim.get("about", ""), "evidence_about": "",
                "note": "", "quote": "", "passage": None}
    answer = _ask("judge", _judge_messages(claim), JUDGE_SCHEMA, cfg, valid)
    quote, passage = find(answer)
    verdict = answer.get("verdict") if answer.get("verdict") in VERDICTS else "unchecked"
    if verdict in ("supported", "contradicted") and passage is None:
        verdict = "unchecked"
    return {"verdict": verdict, "difference": answer.get("difference") if verdict == "contradicted" else "none",
            "about": str(answer.get("about") or ""), "evidence_about": str(answer.get("evidence_about") or ""),
            "note": str(answer.get("note") or "").strip(), "quote": quote, "passage": passage}


def judge_all(claims, cfg, workers=8):
    """judge over many claims in parallel, in input order. A failed call gives "unchecked"."""
    def one(claim):
        try:
            return judge(claim, cfg)
        except Exception as e:
            print(f"claims: {claim['claim_id']}: {e}; unchecked, a re-run retries it", file=sys.stderr)
            return {"verdict": "unchecked", "difference": "none", "about": "", "evidence_about": "", "note": "",
                    "quote": "", "passage": None}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        yield from pool.map(one, claims)


# --- from verdicts to finding rows ---------------------------------------------------------------

def _words(text):
    return set(re.findall(r"\w+", (text or "").lower()))


def _same(x, y):
    a, b = _words(x), _words(y)
    return bool(a and b) and len(a & b) / min(len(a), len(b)) >= 0.5


def _check(claim, v):
    """What the page needs to show the check: the search, and the passage that settled it."""
    e, p = claim["evidence"], v["passage"]
    out = {"verdict": v["verdict"],
           "claim": {"lang": claim["lang"], "quote": claim["quote"], "about": v["about"] or claim.get("about", ""),
                     "kind": claim.get("kind", ""), "origin": claim["origin"]},
           "checked": {"lang": claim["target_lang"], "as_of": claim["as_of"], "searched": e["searched"],
                       "read": len(e["passages"]), "sql": e["sql"], "ms": e["ms"]},
           "evidence": None}
    if p:
        out["evidence"] = {"lang": claim["target_lang"], "chunk_id": p["chunk_id"], "section": p["section"],
                           "chunk_no": p["chunk_no"], "rev_id": p["rev_id"], "quote": v["quote"],
                           "about": v["evidence_about"], "distance": p["distance"], "by_vector": p["by_vector"],
                           "term_hits": p["term_hits"]}
    return out


def _contradicted(claim, v, model):
    """A numbers or contradiction row between a claim and the quote that contradicts it."""
    p = v["passage"]
    mine = {"lang": claim["lang"], "chunk_id": claim["chunk_id"], "quote": claim["quote"]}
    theirs = {"lang": claim["target_lang"], "chunk_id": p["chunk_id"], "quote": v["quote"]}
    a, b = sorted([mine, theirs], key=lambda s: LANGS.index(s["lang"]))
    return {"pair_id": f"{claim['wikidata_id']}:{claim['as_of']}:{a['lang']}:{a['chunk_id']}:{b['lang']}:{b['chunk_id']}",
            "wikidata_id": claim["wikidata_id"], "as_of": claim["as_of"],
            "type": "numbers" if v["difference"] == "figure" else "contradiction", "missing_in": None,
            "quote_a": a["quote"], "quote_b": b["quote"], "summary": v["note"], "terms": [],
            "source": "llm", "model": model, "distance": p["distance"], **_check(claim, v)}


def findings(pairs, rows_by_pair, claims, verdicts, model):
    """(finding rows, rows and claims set aside) from the classifier's rows and the claims' verdicts.

    `rows_by_pair` maps a pair id to its classifier rows in the order row_claims saw them.
    """
    by_row, extracted = {}, []
    for claim, v in zip(claims, verdicts):
        if claim["origin"] == "classifier":
            by_row.setdefault((claim["pair_id"], claim["row"]), []).append((claim, v))
        else:
            extracted.append((claim, v))
    kept, aside, contradictions = [], [], []
    for pair in pairs:
        for n, row in enumerate(rows_by_pair.get(pair["pair_id"], [])):
            checks = by_row.get((pair["pair_id"], n), [])
            if row["type"] not in CHECKED or not checks:
                kept.append(row)   # framing, or a row the search never saw
                continue
            hits = [(c, v) for c, v in checks if v["verdict"] == "contradicted"]
            if hits:
                contradictions += hits
            elif row["type"] == "missing_fact" and checks[0][1]["verdict"] in ("not_mentioned", "unchecked"):
                kept.append({**row, **_check(*checks[0])})
            else:
                aside.append({**row, **_check(*checks[0]), "checks": [_check(c, v) for c, v in checks[1:]]})
    contradictions += [(c, v) for c, v in extracted if v["verdict"] == "contradicted"]
    seen = []
    for claim, v in contradictions:
        row = _contradicted(claim, v, model)
        langs = {claim["lang"], claim["target_lang"]}
        if any(o["wikidata_id"] == row["wikidata_id"] and set(o["pair_id"].split(":")[2:5:2]) == langs
               and _same(o["quote_a"], row["quote_a"]) and _same(o["quote_b"], row["quote_b"]) for o in seen):
            continue   # the same two statements, reached from the other side or from another pair
        seen.append(row)
    return kept + seen, aside


# --- command line --------------------------------------------------------------------------------

def _read(path):
    return [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]


def _rows_by_pair(path):
    out = {}
    for row in _read(path):
        out.setdefault(row["pair_id"], []).append(row)
    return out


def main():
    global OFFLINE
    ap = argparse.ArgumentParser(prog="python -m differences.claims", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("claims", help="the claims of the classifier's rows, and with --extract of the passages")
    p.add_argument("pairs")
    p.add_argument("rows")
    p.add_argument("--extract", action="store_true", help="also list each passage's figures and dates with the model")
    p = sub.add_parser("judge", help="verdicts for claims that carry their evidence, and the finding rows")
    p.add_argument("evidence")
    p.add_argument("pairs")
    p.add_argument("rows")
    p.add_argument("--out", required=True)
    for p in sub.choices.values():
        p.add_argument("--workers", type=int, default=8)
        p.add_argument("--offline", action="store_true", help="answers from the cache only, no model call")
        p.add_argument("--retries", type=int, help="tries per request on a rate limit or server error "
                                                     f"(default {llm.RETRIES}); a busy free tier needs hundreds")
    args = ap.parse_args()
    OFFLINE = args.offline
    if args.retries:
        llm.RETRIES = args.retries
    cfg = llm.config()
    if not cfg:
        sys.exit("no model key in the environment (see differences/llm.py)")
    pairs, rows = _read(args.pairs), _rows_by_pair(args.rows)

    if args.cmd == "claims":
        claims = [c for pair in pairs for c in row_claims(pair, rows.get(pair["pair_id"], []))]
        if args.extract:
            claims += extracted_claims(pairs, cfg, args.workers)
        for c in claims:
            print(json.dumps(c, ensure_ascii=False))
        print(f"claims: {len(claims)} from {len(pairs)} pairs", file=sys.stderr)
        return

    claims = _read(args.evidence)
    verdicts = []
    for n, v in enumerate(judge_all(claims, cfg, args.workers), 1):
        verdicts.append(v)
        print(f"{n}/{len(claims)} {claims[n - 1]['claim_id']} {v['verdict']}", file=sys.stderr, flush=True)
    kept, aside = findings(pairs, rows, claims, verdicts, cfg[2])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    slim = lambda v: {**{k: x for k, x in v.items() if k != "quote"}, "evidence_quote": v["quote"],
                      "passage": v["passage"] and v["passage"]["chunk_id"]}
    for name, items in (("differences.jsonl", kept), ("set-aside.jsonl", aside),
                        ("verdicts.jsonl", [{**{k: c[k] for k in ("claim_id", "pair_id", "row", "origin", "lang", "target_lang",
                                                                  "quote", "kind", "value")}, **slim(v)}
                                            for c, v in zip(claims, verdicts)])):
        with open(out / name, "w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
    count = lambda items, key: ", ".join(f"{k} {sum(1 for i in items if i[key] == k)}" for k in sorted({i[key] for i in items}))
    u = llm.USAGE
    print(f"{cfg[2]}, claims prompt version {PROMPT_VERSION}: {len(claims)} claims ({count(verdicts, 'verdict')}); "
          f"{len(kept)} finding rows ({count(kept, 'type')}), {len(aside)} set aside; "
          f"{u['calls']} model calls not from the cache, {u['input_tokens']:,} input and {u['output_tokens']:,} output tokens")


if __name__ == "__main__":
    main()
