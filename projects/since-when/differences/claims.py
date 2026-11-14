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

The claims of one passage that go to the same edition are judged in one call, at most BATCH
together, against the passages their searches returned.

Claims come from two places: the classifier's rows (a missing fact's quote; both quotes of a
numbers or contradiction row), and the figures and dates the model lists for a passage on its
own (extract). A contradicted claim is then turned round: the statement that contradicts it is
looked up, as a claim of its own, in the first edition. Only when that is contradicted too do
the editions differ; if the first edition also says what the second says, somewhere else, they
do not. What the verdicts do to a row:

    missing fact, not_mentioned   stays a missing fact, now checked against the whole article
    missing fact, supported       no finding: the fact is elsewhere in the article (set aside,
                                  with the passage that states it)
    any claim, contradicted and   a numbers or contradiction finding between the claim and the
    confirmed from the other side quote that contradicts it, wherever in the article that is
    missing fact, contradicted    stays a missing fact: the other edition says something near it,
    and not confirmed             and not this
    numbers or contradiction row with no confirmed contradiction: no finding (set aside)
    a contradiction that repeats one already written: reported once (the others set aside)
    framing                       unchanged; framing is about words, not checked here

Five steps, the searches in the database:

    python -m differences.claims claims PAIRS.jsonl ROWS.jsonl [--extract] > CLAIMS.jsonl
    python -m gapfinder.evidence search CLAIMS.jsonl > EVIDENCE.jsonl
    python -m differences.claims reverse EVIDENCE.jsonl > REVERSE.jsonl
    python -m gapfinder.evidence search REVERSE.jsonl > REVERSE-EVIDENCE.jsonl
    python -m differences.claims findings EVIDENCE.jsonl PAIRS.jsonl ROWS.jsonl \\
        --reverse REVERSE-EVIDENCE.jsonl --out DIR

DIR gets differences.jsonl (the finding rows, in the shape of classify.py's with extra fields),
set-aside.jsonl (rows and claims that are no finding, each with the verdict and the passage that
settled it), verdicts.jsonl (every claim with its verdict) and run.json (the judging model). Model answers are cached under
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

from . import classify, figures, lexicon, llm

PROMPT_VERSION = 3
CACHE_DIR = Path(
    os.environ.get(
        "DIFFERENCES_CLAIMS_CACHE", Path(__file__).resolve().parent.parent / "data" / "differences" / "claims-cache"
    )
)
OFFLINE = False
LANGS = ("fi", "sv", "en")
MAX_CLAIMS = 10  # figures and dates listed for one passage
BATCH = 6  # claims of one passage judged in one call
MAX_READ = 10  # passages of the other edition read in one call
CHECKED = ("missing_fact", "numbers", "contradiction")
VERDICTS = ("supported", "contradicted", "not_mentioned")

JUDGE = """You check claims from one passage of one language edition of Wikipedia against passages of another edition's article on the same topic. Those passages were picked by a search over the whole article: the ones nearest to each claim in meaning and the ones that share its names and numbers. They are in the article's order and may be in another language than the claims. For each claim, decide what the other edition says about the claim's point.

First say what the claim is about: who, which event, which quantity, at which moment, where. Read the claims' own passage for that: "it" or "the movement" in a claim may be another organisation, person or event than the article's topic. Then give one verdict:

- supported: a passage states the same fact. Other words, another language and less precision all count: "in the spring of 1920" supports "12 April 1920", and "more than 400 ships" supports "430 ships". An approximate figure supports an exact one only when the exact one rounds to it: "about 5,000" supports "4,900" and not "5,600".
- contradicted: a passage makes a statement about the same thing and both cannot be true: another figure for the same quantity, another date for the same event, another actor, place, cause or outcome. Both statements must be about the very same thing. Not contradictions: two different events (a treaty's signing and its ratification), two different quantities (a whole army and the part of it that fought; a planned strength and an actual one; the dead and all casualties), the same quantity at two moments (a garrison in March and in May), two steps of one course of events. If the passages give the claim's figure in one place and another figure elsewhere, the claim is supported.
- not_mentioned: no passage states the fact and none contradicts it. A passage may cover the same event and leave this fact out; that is still not_mentioned.

Rules:
- Give one verdict per claim, in the claims' order; claim is the claim's number.
- quote is copied character for character from one passage of the other edition, in its own language, never translated, one sentence or shorter. For supported it is the statement of the fact; for contradicted the statement that disagrees; for not_mentioned the sentence about the same event where the fact would belong, or empty when no passage covers the event.
- passage is the number of the passage the quote is from, 0 when the quote is empty.
- When several passages speak of the same thing, quote the most exact statement: the sentence that gives the day or the exact figure, not one that gives only the month or a rough size.
- evidence_about says what the quoted sentence is about, as exactly as you said what the claim is about. If the two are not about the same thing, the verdict cannot be contradicted.
- claim_figure and evidence_figure: when the claim's point is a figure (a count, date, duration or percentage) and the quote gives a figure for the very same thing, copy each figure as it is written, with its hedge and unit ("omkring 400", "over 2,000", "3 June 1920", "kesäkuun alussa 1920"); otherwise leave both empty. Whether the two figures agree is computed from these, so copy them exactly.
- difference is "figure" when the claim is contradicted by another figure for the same quantity (a count, date, duration or percentage), "fact" when it is contradicted in another way, "none" otherwise.
- note is one neutral English sentence that names the editions by language and says what each says about the point, for example "The Swedish article gives about 400 ships for the fleet that sailed in June 1920; the English article gives 430." Keep hedges and attributions ("according to", "about"). Never say which edition is right.
- Judge only from the passages given. Do not use what you know about the topic."""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "integer"},
                    "about": {"type": "string"},
                    "evidence_about": {"type": "string"},
                    "verdict": {"type": "string", "enum": list(VERDICTS)},
                    "difference": {"type": "string", "enum": ["figure", "fact", "none"]},
                    "passage": {"type": "integer"},
                    "quote": {"type": "string"},
                    "claim_figure": {"type": "string"},
                    "evidence_figure": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": [
                    "claim",
                    "about",
                    "evidence_about",
                    "verdict",
                    "difference",
                    "passage",
                    "quote",
                    "claim_figure",
                    "evidence_figure",
                    "note",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["verdicts"],
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
    return json.loads(content[start : end + 1] if start >= 0 and end > start else content)


def _ask(kind, messages, schema, cfg, valid):
    """The model's parsed answer to `messages`, from the cache when it is there.

    Only an answer that parses and that `valid` accepts is cached; another is asked again, three
    times in all, and the last one is returned as it is.
    """
    opts = {k: v for k, v in llm.options().items() if k != "max_tokens"}
    key = hashlib.sha256(
        json.dumps([kind, PROMPT_VERSION, cfg[0], cfg[2], opts, messages], ensure_ascii=False).encode()
    ).hexdigest()
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
        raise ValueError("no answer that parses")  # noqa: TRY004  the answer's text is wrong, not a caller's type
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
    whole = text[spans[0][0] : spans[-1][1]].strip() if spans else quote
    return whole if len(whole) <= limit else quote


def _claim(pair, side, other, quote, origin, about="", kind="", value="", row=None):
    p, target = pair[side], pair[other]
    ident = hashlib.sha1(
        json.dumps([pair["wikidata_id"], pair["as_of"], p["lang"], target["lang"], quote], ensure_ascii=False).encode()
    ).hexdigest()[:16]
    return {
        "claim_id": ident,
        "wikidata_id": pair["wikidata_id"],
        "as_of": pair["as_of"],
        "pair_id": pair["pair_id"],
        "lang": p["lang"],
        "title": p.get("title", ""),
        "chunk_id": p.get("chunk_id"),
        "section": p.get("section", ""),
        "chunk_no": p.get("chunk_no", 0),
        "rev_id": p.get("rev_id"),
        "quote": quote,
        "text": sentence(quote, p["text"]),
        "context": p["text"],
        "about": about,
        "kind": kind,
        "value": value,
        "origin": origin,
        "row": row,
        "target_lang": target["lang"],
        "target_title": target.get("title", ""),
        "always": [target["chunk_id"]] if target.get("chunk_id") is not None else [],
    }


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
            # A missing fact with two quotes: the one of the passage said to lack the fact only
            # shows where it belongs, and with no edition named the first is the fact. With one
            # quote, that quote is the fact, whichever edition the classifier named: it named the
            # wrong one, or none, in one row of ten.
            named = row.get("missing_in")
            shows_where = named not in (None, pair[other]["lang"]) or (not named and side == "b")
            if row["type"] == "missing_fact" and row["quote_a"] and row["quote_b"] and shows_where:
                continue
            out.append(_claim(pair, side, other, quote, "classifier", row=n))
    return out


def _passage(p):
    where = f'section "{p["section"]}"' if p.get("section") else "lead"
    return f'{lexicon.LANG_NAME.get(p["lang"], p["lang"])} Wikipedia, "{p.get("title", "")}", {where}'


def extract(passage, cfg):
    """The figures and dates of one passage, as {"quote", "about", "kind", "value"}, quotes verbatim."""
    messages = [
        {"role": "system", "content": EXTRACT},
        {"role": "user", "content": f"Passage ({_passage(passage)}):\n<<<\n{passage['text']}\n>>>"},
    ]
    answer = _ask("extract", messages, EXTRACT_SCHEMA, cfg, lambda a: isinstance(a.get("claims"), list))
    out = []
    for c in answer.get("claims") or []:
        quote = classify.locate(str(c.get("quote") or ""), passage["text"])
        if quote and str(c.get("about") or "").strip():
            out.append(
                {
                    "quote": quote,
                    "about": c["about"].strip(),
                    "kind": c.get("kind") or "",
                    "value": str(c.get("value") or ""),
                }
            )
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
        except Exception as e:  # noqa: BLE001  one bad call should not stop a run over hundreds of passages
            print(
                f"claims: extract {p.get('lang')} {p.get('chunk_id')}: {e}; no claims, a re-run retries it",
                file=sys.stderr,
            )
            return []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        found = dict(zip(passages, pool.map(one, passages.values())))
    out = {}
    for pair in pairs:
        for side, other in (("a", "b"), ("b", "a")):
            for c in found[pair[side]["text"]]:
                claim = _claim(pair, side, other, c["quote"], "extract", c["about"], c["kind"], c["value"])
                if claim["claim_id"] in out:  # the passage is paired with two passages of this edition
                    out[claim["claim_id"]]["always"] += claim["always"]
                else:
                    out[claim["claim_id"]] = claim
    return list(out.values())


# --- the verdict ---------------------------------------------------------------------------------

UNCHECKED = {
    "verdict": "unchecked",
    "difference": "none",
    "about": "",
    "evidence_about": "",
    "note": "",
    "quote": "",
    "passage": None,
    "figures": None,
}


def groups(claims, size=BATCH):
    """Lists of positions in `claims` that are judged in one call: claims of one passage, looked
    up in one edition, at most `size` together."""
    by_passage = {}
    for n, c in enumerate(claims):
        key = (c["wikidata_id"], c["as_of"], c["lang"], c.get("context") or c["text"], c["target_lang"])
        by_passage.setdefault(key, []).append(n)
    return [ns[i : i + size] for ns in by_passage.values() for i in range(0, len(ns), size)]


def _read_together(group):
    """The passages the claims of one call are read against: each claim's own in turn (the one
    its passage was paired with first, then by its best rank) until MAX_READ, in the article's order."""
    lists: list[list[dict]] = []
    for c in group:
        always = set(c.get("always") or ())
        lists.append(
            sorted(
                c["evidence"]["passages"],
                key=lambda p: (
                    p["chunk_id"] not in always,
                    min(p["by_vector"], p.get("by_passage", 99) + 2, p["by_terms"] if p["term_hits"] else 99),
                ),
            )
        )
    chosen: dict[int, dict] = {}
    for rank in range(max((len(ps) for ps in lists), default=0)):
        for ps in lists:
            if rank < len(ps) and len(chosen) < MAX_READ:
                chosen.setdefault(ps[rank]["chunk_id"], ps[rank])
    return sorted(chosen.values(), key=lambda p: p["ord"])


def _judge_messages(group, passages):
    first = group[0]
    source = {"lang": first["lang"], "title": first["title"], "section": first["section"]}
    lines = [
        f"Claims from {_passage(source)}. Their own passage, only to tell who and what each claim speaks of:",
        f"<<<\n{first.get('context') or first['text']}\n>>>",
    ]
    for n, c in enumerate(group, 1):
        lines.append(f'\nClaim {n}: "{c["quote"]}"')
        if c["text"].rstrip(".") != c["quote"].rstrip("."):
            lines.append(f'  in the sentence: "{c["text"]}"')
        if c.get("about"):
            lines.append(f"  what it measures: {c['about']}")
    searched = max(c["evidence"]["searched"] for c in group)
    lines.append(
        f"\nPassages of {lexicon.LANG_NAME.get(first['target_lang'], first['target_lang'])} Wikipedia, "
        f'"{first["target_title"]}" ({len(passages)} of the article\'s {searched}):'
    )
    for n, p in enumerate(passages, 1):
        where = f'section "{p["section"]}"' if p["section"] else "lead"
        lines.append(f"\nPassage {n} ({where}):\n<<<\n{p['text']}\n>>>")
    return [{"role": "system", "content": JUDGE}, {"role": "user", "content": "\n".join(lines)}]


def judge(group, cfg):
    """The verdicts on claims of one passage that carry their `evidence` (gapfinder.evidence.search),
    one per claim: {"verdict", "difference", "about", "evidence_about", "note", "quote", "passage",
    "figures"}.

    quote is an exact substring of the passage it names (one of the evidence passages, with this
    claim's own distance and rank when its search returned that passage), or "" with passage None.
    A supported or contradicted verdict whose quote is in none of the passages, and a claim the
    answer leaves out, is asked again and, if it stays that way, is "unchecked".

    When the model gives both sides' figures for the same thing, figures.compatible decides
    between supported and contradicted, whatever the model said of the two; "figures" keeps the
    two figures, whether they agree and the model's own verdict.
    """
    passages = _read_together(group)
    if not passages:
        return [dict(UNCHECKED, verdict="not_mentioned", about=c.get("about", "")) for c in group]

    def find(answer):
        """(exact quote, passage) of one verdict's quote: in the passage it names, else in any."""
        raw, named = str(answer.get("quote") or ""), answer.get("passage")
        order = ([passages[named - 1]] if isinstance(named, int) and 1 <= named <= len(passages) else []) + passages
        for p in order:
            quote = classify.locate(raw, p["text"])
            if quote:
                return quote, p
        return "", None

    def by_claim(answer):
        got = {}
        for v in answer.get("verdicts") or []:
            if isinstance(v, dict) and isinstance(v.get("claim"), int) and v.get("verdict") in VERDICTS:
                got.setdefault(v["claim"], v)
        return got

    def valid(answer):
        got = by_claim(answer)
        return all(
            n in got and (got[n]["verdict"] == "not_mentioned" or find(got[n])[1] is not None)
            for n in range(1, len(group) + 1)
        )

    got = by_claim(_ask("judge", _judge_messages(group, passages), JUDGE_SCHEMA, cfg, valid))
    out = []
    for n, claim in enumerate(group, 1):
        answer = got.get(n)
        if not answer:
            out.append(dict(UNCHECKED))
            continue
        quote, passage = find(answer)
        if passage is not None:  # this claim's own distance and rank, unknown if another claim's search found it
            own = {p["chunk_id"]: p for p in claim["evidence"]["passages"]}
            passage = own.get(passage["chunk_id"]) or {
                **passage,
                "distance": None,
                "passage_distance": None,
                "by_vector": None,
                "by_passage": None,
                "term_hits": None,
            }
        verdict, difference, both = answer["verdict"], answer.get("difference"), None
        if verdict in ("supported", "contradicted") and passage is None:
            verdict = "unchecked"
        mine, theirs = str(answer.get("claim_figure") or "").strip(), str(answer.get("evidence_figure") or "").strip()
        if mine and theirs and passage is not None:
            agree = figures.compatible(mine, theirs)
            both = {"claim": mine, "evidence": theirs, "agree": agree, "model": answer["verdict"]}
            if agree is False and verdict == "supported":
                verdict, difference = "contradicted", "figure"
            elif agree is True and verdict == "contradicted" and difference == "figure":
                verdict = "supported"
        out.append(
            {
                "verdict": verdict,
                "difference": difference if verdict == "contradicted" else "none",
                "about": str(answer.get("about") or ""),
                "evidence_about": str(answer.get("evidence_about") or ""),
                "note": str(answer.get("note") or "").strip(),
                "quote": quote,
                "passage": passage,
                "figures": both,
            }
        )
    return out


def judge_all(claims, cfg, workers=8, size=BATCH, progress=None):
    """The verdict of every claim, in input order. A failed call leaves its claims "unchecked"."""

    def one(positions):
        group = [claims[n] for n in positions]
        try:
            verdicts = judge(group, cfg)
        except Exception as e:  # noqa: BLE001  one bad call should not stop a run over hundreds of claims
            print(
                f"claims: {', '.join(c['claim_id'] for c in group)}: {e}; unchecked, a re-run retries it",
                file=sys.stderr,
            )
            verdicts = [dict(UNCHECKED) for _ in group]
        if progress:
            progress(group, verdicts)
        return positions, verdicts

    out = [None] * len(claims)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for positions, verdicts in pool.map(one, groups(claims, size)):
            for n, v in zip(positions, verdicts):
                out[n] = v
    return out


# --- from verdicts to finding rows ---------------------------------------------------------------


def _words(text):
    return set(re.findall(r"\w+", (text or "").lower()))


def _same(x, y):
    a, b = _words(x), _words(y)
    return bool(a and b) and len(a & b) / min(len(a), len(b)) >= 0.5


def _check(claim, v):
    """What the page needs to show the check: the search, and the passage that settled it."""
    e, p = claim["evidence"], v["passage"]
    out = {
        "verdict": v["verdict"],
        "claim": {
            "lang": claim["lang"],
            "quote": claim["quote"],
            "about": v["about"] or claim.get("about", ""),
            "kind": claim.get("kind", ""),
            "origin": claim["origin"],
        },
        "checked": {
            "lang": claim["target_lang"],
            "as_of": claim["as_of"],
            "searched": e["searched"],
            "read": len(e["passages"]),
            "sql": e["sql"],
            "ms": e["ms"],
        },
        "evidence": None,
        "figures": v.get("figures"),
    }
    if p:
        out["evidence"] = {
            "lang": claim["target_lang"],
            "chunk_id": p["chunk_id"],
            "section": p["section"],
            "chunk_no": p["chunk_no"],
            "rev_id": p["rev_id"],
            "quote": v["quote"],
            "about": v["evidence_about"],
            "sentence": p.get("sentence"),
            "distance": p["distance"],
            "by_vector": p["by_vector"],
            "term_hits": p["term_hits"],
        }
    return out


def _contradicted(claim, v, model):
    """A numbers or contradiction row between a claim and the quote that contradicts it."""
    p = v["passage"]
    mine = {"lang": claim["lang"], "chunk_id": claim["chunk_id"], "quote": claim["quote"]}
    theirs = {"lang": claim["target_lang"], "chunk_id": p["chunk_id"], "quote": v["quote"]}
    a, b = sorted([mine, theirs], key=lambda s: LANGS.index(s["lang"]))
    return {
        "pair_id": f"{claim['wikidata_id']}:{claim['as_of']}:{a['lang']}:{a['chunk_id']}:{b['lang']}:{b['chunk_id']}",
        "wikidata_id": claim["wikidata_id"],
        "as_of": claim["as_of"],
        "type": "numbers" if v["difference"] == "figure" else "contradiction",
        "missing_in": None,
        "quote_a": a["quote"],
        "quote_b": b["quote"],
        "summary": v["note"],
        "terms": [],
        "source": "llm",
        "model": model,
        "distance": p["distance"],
        "from_pair": claim["pair_id"],
        **_check(claim, v),
    }


def _side(row, lang):
    """(quote, figure) of one edition in a row the check wrote."""
    a_lang = row["pair_id"].split(":")[2]
    both = row.get("figures") or {}
    return (
        row["quote_a"] if lang == a_lang else row["quote_b"],
        both.get("claim" if row["claim"]["lang"] == lang else "evidence"),
    )


def _repeats(row, other):
    """Whether a row says what `other` already says: the same two statements, reached from the
    other side or from another pair, or one statement and its figure set against a second sentence
    of the other edition (a ban dated 21 November against three sentences on the stages of the
    ban). A sentence with two figures can still carry two rows."""
    langs = {row["claim"]["lang"], row["checked"]["lang"]}
    if other["wikidata_id"] != row["wikidata_id"] or langs != {other["claim"]["lang"], other["checked"]["lang"]}:
        return False
    same = [lang for lang in langs if _same(_side(row, lang)[0], _side(other, lang)[0])]
    return len(same) == 2 or any(_side(row, lang)[1] == _side(other, lang)[1] for lang in same)


def reverse_claims(claims, verdicts):
    """For every contradicted claim, the statement that contradicts it as a claim of its own
    edition, to be looked up in the first claim's edition. A contradiction is a finding only when
    it is seen from both sides: if the first edition also says what the second says, somewhere
    else, the two editions do not differ."""
    out = {}
    for c, v in zip(claims, verdicts):
        if v["verdict"] != "contradicted":
            continue
        p = v["passage"]
        ident = hashlib.sha1(
            json.dumps(
                [c["wikidata_id"], c["as_of"], c["target_lang"], c["lang"], v["quote"]], ensure_ascii=False
            ).encode()
        ).hexdigest()[:16]
        out[c["claim_id"]] = {
            "claim_id": ident,
            "reverses": c["claim_id"],
            "wikidata_id": c["wikidata_id"],
            "as_of": c["as_of"],
            "pair_id": c["pair_id"],
            "lang": c["target_lang"],
            "title": c["target_title"],
            "chunk_id": p["chunk_id"],
            "section": p["section"],
            "chunk_no": p["chunk_no"],
            "rev_id": p["rev_id"],
            "quote": v["quote"],
            "text": sentence(v["quote"], p["text"]),
            "context": p["text"],
            "about": v["evidence_about"],
            "kind": "",
            "value": "",
            "origin": "reverse",
            "row": None,
            "target_lang": c["lang"],
            "target_title": c["title"],
            "always": [c["chunk_id"]] if c.get("chunk_id") is not None else [],
        }
    return list(out.values())


def findings(pairs, rows_by_pair, claims, verdicts, model, reverse=None):
    """(finding rows, rows and claims set aside) from the classifier's rows and the claims' verdicts.

    `rows_by_pair` maps a pair id to its classifier rows in the order row_claims saw them.
    `reverse` maps a contradicted claim's id to (its reverse claim, that claim's verdict); given,
    a contradiction counts only when the reverse verdict is contradicted too.
    """

    def confirmed(c, v):
        return v["verdict"] == "contradicted" and (
            reverse is None or (c["claim_id"] in reverse and reverse[c["claim_id"]][1]["verdict"] == "contradicted")
        )

    def check(c, v):
        """_check, with the reverse check of a contradicted claim, and as not_mentioned when that failed."""
        out = _check(c, v)
        if reverse is not None and c["claim_id"] in reverse:
            out["reverse"] = _check(*reverse[c["claim_id"]])
            if not confirmed(c, v):
                out["verdict"] = "not_mentioned"
        return out

    by_row, extracted = {}, []
    for claim, v in zip(claims, verdicts):
        if claim["origin"] == "classifier":
            by_row.setdefault((claim["pair_id"], claim["row"]), []).append((claim, v))
        elif claim["origin"] != "reverse":
            extracted.append((claim, v))
    kept, aside, contradictions = [], [], []
    for pair in pairs:
        for n, row in enumerate(rows_by_pair.get(pair["pair_id"], [])):
            checks = by_row.get((pair["pair_id"], n), [])
            if row["type"] not in CHECKED or not checks:
                kept.append(row)  # framing, or a row the search never saw
                continue
            hits = [(c, v) for c, v in checks if confirmed(c, v)]
            if hits:
                contradictions += [(c, v, row) for c, v in hits]
            elif row["type"] == "missing_fact" and checks[0][1]["verdict"] != "supported":
                # not mentioned, unchecked, or a contradiction the other side did not confirm: the
                # other edition says something near it, and not this
                # missing_in becomes the edition that was searched; the classifier's own value
                # stays beside it, since the finding it wrote is keyed by that.
                searched = {"missing_in": checks[0][0]["target_lang"], "classifier_missing_in": row.get("missing_in")}
                kept.append({**row, **searched, **check(*checks[0])})
            else:
                aside.append({**row, **check(*checks[0]), "checks": [check(c, v) for c, v in checks[1:]]})
    for c, v in extracted:
        if confirmed(c, v):
            contradictions.append((c, v, None))
        elif v["verdict"] == "contradicted":  # a figure the other side did not confirm
            aside.append({**_contradicted(c, v, model), **check(c, v), "verdict": "unconfirmed"})
    # The classifier's own numbers and contradiction rows first, then what its missing facts
    # turned into, then the figures the check listed: of rows that say the same, the first stays.
    contradictions.sort(key=lambda x: 2 if x[2] is None else x[2]["type"] == "missing_fact")
    seen = []
    for claim, v, first in contradictions:
        row = {**_contradicted(claim, v, model), **check(claim, v)}
        if first:  # the classifier's row this one comes from, so a loader can find its finding
            row["original"] = {k: first.get(k) for k in ("pair_id", "type", "missing_in", "quote_a", "quote_b")}
        if not any(_repeats(row, other) for other in seen):
            seen.append(row)
        elif first and not any(o.get("original") == row["original"] for o in seen + aside):
            # The difference is reported once; this classifier row's finding is set aside as a repeat.
            aside.append({**row, "aside": "repeat"})
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
    p = sub.add_parser("reverse", help="judge the claims and print, for each contradicted one, the reverse claim")
    p.add_argument("evidence")
    p = sub.add_parser("findings", help="judge the claims and write the finding rows")
    p.add_argument("evidence")
    p.add_argument("pairs")
    p.add_argument("rows")
    p.add_argument(
        "--reverse", help="the reverse claims with their evidence; without it a contradiction needs no confirmation"
    )
    p.add_argument("--out", required=True)
    for p in sub.choices.values():
        p.add_argument("--batch", type=int, default=BATCH, help="claims of one passage judged in one call")
        p.add_argument("--workers", type=int, default=8)
        p.add_argument("--offline", action="store_true", help="answers from the cache only, no model call")
        p.add_argument(
            "--retries",
            type=int,
            help="tries per request on a rate limit or server error "
            f"(default {llm.RETRIES}); a busy free tier needs hundreds",
        )
    args = ap.parse_args()
    OFFLINE = args.offline
    if args.retries:
        llm.RETRIES = args.retries
    cfg = llm.config()
    if not cfg:
        sys.exit("no model key in the environment (see differences/llm.py)")

    if args.cmd == "claims":
        pairs, rows = _read(args.pairs), _rows_by_pair(args.rows)
        claims = [c for pair in pairs for c in row_claims(pair, rows.get(pair["pair_id"], []))]
        if args.extract:
            claims += extracted_claims(pairs, cfg, args.workers)
        for c in claims:
            print(json.dumps(c, ensure_ascii=False))
        print(f"claims: {len(claims)} from {len(pairs)} pairs", file=sys.stderr)
        return

    def judged(path):
        claims, done = _read(path), []

        def progress(group, verdicts):
            done.extend(verdicts)
            print(f"{len(done)}/{len(claims)} " + " ".join(v["verdict"] for v in verdicts), file=sys.stderr, flush=True)

        return claims, judge_all(claims, cfg, args.workers, args.batch, progress)

    claims, verdicts = judged(args.evidence)
    if args.cmd == "reverse":
        back = reverse_claims(claims, verdicts)
        for c in back:
            print(json.dumps(c, ensure_ascii=False))
        print(
            f"claims: {len(back)} contradicted of {len(claims)}, to be confirmed from the other side", file=sys.stderr
        )
        return

    reverse = None
    if args.reverse:
        back, back_verdicts = judged(args.reverse)
        reverse = {c["reverses"]: (c, v) for c, v in zip(back, back_verdicts)}
        claims, verdicts = claims + back, verdicts + back_verdicts
    kept, aside = findings(_read(args.pairs), _rows_by_pair(args.rows), claims, verdicts, cfg[2], reverse)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    slim = lambda v: {
        **{k: x for k, x in v.items() if k != "quote"},
        "evidence_quote": v["quote"],
        "passage": v["passage"] and v["passage"]["chunk_id"],
    }
    for name, items in (
        ("differences.jsonl", kept),
        ("set-aside.jsonl", aside),
        (
            "verdicts.jsonl",
            [
                {
                    **{
                        k: c.get(k)
                        for k in (
                            "claim_id",
                            "reverses",
                            "pair_id",
                            "row",
                            "origin",
                            "lang",
                            "target_lang",
                            "quote",
                            "kind",
                            "value",
                        )
                    },
                    **slim(v),
                }
                for c, v in zip(claims, verdicts)
            ],
        ),
    ):
        with open(out / name, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(item, ensure_ascii=False) + "\n" for item in items)
    (out / "run.json").write_text(json.dumps({"judge": cfg[2], "prompt_version": PROMPT_VERSION}) + "\n")
    count = lambda items, key: ", ".join(
        f"{k} {sum(1 for i in items if i[key] == k)}" for k in sorted({i[key] for i in items})
    )
    u = llm.USAGE
    print(
        f"{cfg[2]}, claims prompt version {PROMPT_VERSION}: {len(claims)} claims ({count(verdicts, 'verdict')}); "
        f"{len(kept)} finding rows ({count(kept, 'type')}), {len(aside)} set aside; "
        f"{u['calls']} model calls not from the cache, {u['input_tokens']:,} input and {u['output_tokens']:,} output tokens"
    )


if __name__ == "__main__":
    main()
