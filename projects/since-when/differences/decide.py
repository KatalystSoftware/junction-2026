"""The claim check judged by Gemini Decision, beside the chat judges of claims.py.

Gemini Decision (llm.decide) answers questions about one shared input with probabilities and
writes no text. So the check is asked as questions, the claims that go to one article together in
one request:

    verdict   per claim, a choice: supported, other_figure, other_fact or not_mentioned. The two
              middle ones together are claims.py's "contradicted".
    passage   per claim that is not not_mentioned, a choice among the passages: which one states it
    sentence  per such claim, a choice among that passage's sentences: the quote

A contradicted claim's sentence is then turned round and asked as a claim against the first
edition's whole article, as in claims.py. With the verdicts in the shape claims.judge returns,
claims.findings writes the same files.

Two ways to show the article, --read:

    article   the whole other article as it stood on the claim's date is the request's input, and
              no search is used
    passages  each question carries the passages the claim's search returned (EVIDENCE.jsonl, the
              same text the chat judges read); the request's input is only a heading

A verdict is a probability, so it needs a threshold: a claim is supported or contradicted when that
answer's probability is at least --threshold, and not_mentioned otherwise. The questions sent do
not depend on the threshold, so another threshold is answered from the cache.

    python -m differences.decide EVIDENCE.jsonl PAIRS.jsonl ROWS.jsonl --articles ARTICLES.jsonl \\
        --read article --threshold 0.5 0.7 0.9 --out DIR

ARTICLES.jsonl has one passage per line (wikidata_id, lang, as_of, chunk_id, ord, section,
chunk_no, rev_id, text). DIR gets a folder per threshold, t50 for 0.5, with the files of
claims.py. What Gemini Decision cannot give: the two figures as written (figures.py is not
used), what each side is about, and the note, which here is the two quotes side by side.
Every answer is cached under $DIFFERENCES_DECIDE_CACHE; --offline never sends a request, and
--max-requests (default 40) stops a run that would send more.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from . import claims, lexicon, llm

VERSION = 1
CACHE_DIR = Path(
    os.environ.get(
        "DIFFERENCES_DECIDE_CACHE", Path(__file__).resolve().parent.parent / "data" / "differences" / "decide-cache"
    )
)
OFFLINE = False
MAX_REQUESTS = 40
SENT = {"requests": 0, "tokens": 0, "cached": 0}
LOWEST = 0.3  # passages and sentences are asked for every claim whose verdict could count at any threshold
MAX_CHARS = 450_000  # of one request, about 150,000 tokens of the 262,144 allowed
MAX_QUESTIONS = 1000
MAX_OPTIONS = 255

BRIEF = """You check claims from one language edition of Wikipedia against another edition's article on the same topic. The article may be in another language than the claims. Judge only from the article text given, not from what you know about the topic. Other words, another language and less precision all state the same fact: "in the spring of 1920" states "12 April 1920", and "more than 400 ships" states "430 ships"."""

VERDICT = {
    "supported": "The article states the same fact somewhere, in any words, in any language, or with less precision. "
    "If the article gives the claim's figure in one place and another figure elsewhere, this is the answer.",
    "other_figure": "The article gives another count, date, duration or percentage for the very same quantity or "
    "event, and both cannot be true. Not this: two different events, two different quantities (a whole army and "
    "the part that fought; the dead and all casualties), the same quantity at two moments, two steps of one course "
    "of events.",
    "other_fact": "The article says something else about the very same thing and both cannot be true: another "
    "actor, place, cause or outcome.",
    "not_mentioned": "The article neither states the fact nor contradicts it. It may cover the same event and "
    "leave this fact out.",
}


def _ask(text, questions):
    """llm.decide, from the cache when the same request was answered before."""
    key = hashlib.sha256(json.dumps([VERSION, llm.DECISION_MODEL, text, questions], ensure_ascii=False).encode())
    path = CACHE_DIR / f"{key.hexdigest()}.json"
    if path.exists():
        SENT["cached"] += 1
        return json.loads(path.read_text())["answers"]
    if OFFLINE:
        raise LookupError("not in the cache (offline)")
    if SENT["requests"] >= MAX_REQUESTS:
        raise RuntimeError(f"{MAX_REQUESTS} requests sent, the limit of this run (--max-requests)")
    before = llm.USAGE["calls"]
    try:
        answers, usage = llm.decide(text, questions)
    finally:
        SENT["requests"] += llm.USAGE["calls"] - before
    SENT["tokens"] += usage.get("total_input_tokens", 0)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"model": llm.DECISION_MODEL, "questions": len(questions), "usage": usage, "answers": answers})
    )
    return answers


def _ask_all(text, questions):
    """The answers to any number of questions about one input, in as few requests as the limits allow."""
    out, part, size = {}, {}, len(text)
    for key, q in questions.items():
        n = len(json.dumps(q, ensure_ascii=False))
        if part and (len(part) >= MAX_QUESTIONS or size + n > MAX_CHARS):
            out.update(_ask(text, part))
            part, size = {}, len(text)
        part[key] = q
        size += n
    if part:
        out.update(_ask(text, part))
    return out


def _where(p):
    return f'section "{p["section"]}"' if p.get("section") else "lead"


def _numbered(passages):
    return "\n".join(f"\nPassage {n} ({_where(p)}):\n<<<\n{p['text']}\n>>>" for n, p in enumerate(passages, 1))


def _claim_text(c):
    source = {"lang": c["lang"], "title": c["title"], "section": c["section"]}
    lines = [f'Claim, from {claims._passage(source)}: "{c["quote"]}"']
    if c["text"].rstrip(".") != c["quote"].rstrip("."):
        lines.append(f'In the sentence: "{c["text"]}"')
    if c.get("about"):
        lines.append(f"What it measures: {c['about']}")
    lines.append(
        'The claim\'s own passage, only to tell who and what it speaks of ("it" or "the movement" may be '
        f"another organisation, person or event than the article's topic):\n<<<\n{c.get('context') or c['text']}\n>>>"
    )
    return "\n".join(lines)


def _passages(c, article, read):
    """The passages of the other article one claim is read against, in the article's order."""
    if read == "article" or "evidence" not in c:
        return article
    return sorted(c["evidence"]["passages"], key=lambda p: p["ord"])[:MAX_OPTIONS]


def judge_article(group, article, read, locate=True):
    """The answers on claims that go to one article: per claim {"p": {answer: probability},
    "passage": the passage chosen or None, "quote": the sentence chosen or ""}.

    `article` is the article's passages in order. With read "passages" each claim is read against
    its own evidence passages instead. Without `locate` only the verdict is asked.
    """
    first = group[0]
    name = f'{lexicon.LANG_NAME.get(first["target_lang"], first["target_lang"])} Wikipedia, "{first["target_title"]}"'
    whole = read == "article"
    text = f"{BRIEF}\n\nThe article: {name}" + (
        f", all {len(article)} passages.\n{_numbered(article)}" if whole else "."
    )
    shown = [_passages(c, article, read) for c in group]

    def ask(question, n, c):
        given = (
            ""
            if whole
            else (
                f"\n\nPassages of the article ({len(shown[n])} of {c['evidence']['searched']}, picked by a search):"
                f"{_numbered(shown[n])}"
            )
        )
        return f"{question}\n\n{_claim_text(c)}{given}"

    verdicts = _ask_all(
        text,
        {
            f"c{n}": {
                "type": "choice",
                "instructions": ask("What does the article say about this claim's point?", n, c),
                "criteria": VERDICT,
            }
            for n, c in enumerate(group)
        },
    )
    out: list[dict] = [
        {"p": verdicts[f"c{n}"]["probabilities"], "passage": None, "quote": ""} for n in range(len(group))
    ]
    if not locate:
        return out
    found = [n for n, v in enumerate(out) if 1 - v["p"]["not_mentioned"] >= LOWEST and shown[n]]
    # Which passage: the answer is a passage number. One passage needs no question.
    where = _ask_all(
        text,
        {
            f"c{n}": {
                "type": "choice",
                "instructions": ask(
                    "Which passage of the article states this claim's point, or says something else about the "
                    "very same thing?",
                    n,
                    group[n],
                ),
                "criteria": {f"passage_{i}": _where(p) for i, p in enumerate(shown[n], 1)},
            }
            for n in found
            if len(shown[n]) > 1
        },
    )
    for n in found:
        chosen = where[f"c{n}"]["choice"] if len(shown[n]) > 1 else "passage_1"
        out[n]["passage"] = shown[n][int(chosen.split("_")[1]) - 1]
    # Which sentence of that passage: the options are the sentences themselves.
    spans = {n: claims.sentences(out[n]["passage"]["text"])[:MAX_OPTIONS] for n in found}
    which = _ask_all(
        text,
        {
            f"c{n}": {
                "type": "choice",
                "instructions": ask(
                    "Which sentence of the article states this claim's point, or says something else about the "
                    "very same thing? The most exact one: the sentence that gives the day or the exact figure.",
                    n,
                    group[n],
                ),
                "criteria": {
                    f"sentence_{i}": out[n]["passage"]["text"][s:e].strip() for i, (s, e) in enumerate(spans[n], 1)
                },
            }
            for n in found
            if len(spans[n]) > 1
        },
    )
    for n in found:
        chosen = which[f"c{n}"]["choice"] if len(spans[n]) > 1 else "sentence_1"
        s, e = spans[n][int(chosen.split("_")[1]) - 1]
        out[n]["quote"] = out[n]["passage"]["text"][s:e].strip()
    return out


def verdict(claim, answer, threshold):
    """One answer as claims.judge returns a verdict, at `threshold`."""
    p = answer["p"]
    contradicted = p["other_figure"] + p["other_fact"]
    name = "not_mentioned"
    if max(p["supported"], contradicted) >= threshold:
        name = "supported" if p["supported"] >= contradicted else "contradicted"
    passage = answer["passage"]
    if passage is not None:
        own = {x["chunk_id"]: x for x in (claim.get("evidence") or {}).get("passages", [])}
        blank = {"distance": None, "passage_distance": None, "by_vector": None, "by_passage": None, "term_hits": None}
        passage = own.get(passage["chunk_id"]) or {**blank, **passage}
    langs = [lexicon.LANG_NAME.get(claim[k], claim[k]) for k in ("lang", "target_lang")]
    return {
        "verdict": name,
        "difference": ("figure" if p["other_figure"] >= p["other_fact"] else "fact")
        if name == "contradicted"
        else "none",
        "about": claim.get("about", ""),
        "evidence_about": "",
        "note": f'The {langs[0]} article says "{claim["quote"]}"; the {langs[1]} article says "{answer["quote"]}".'
        if name == "contradicted"
        else "",
        "quote": answer["quote"],
        "passage": passage,
        "figures": None,
        "probabilities": {k: round(v, 4) for k, v in p.items()},
    }


def judge_all(items, articles, read, locate=True):
    """The answer on every claim, in input order: one group of requests per article asked."""
    by_article = {}
    for n, c in enumerate(items):
        by_article.setdefault((c["wikidata_id"], c["target_lang"], c["as_of"]), []).append(n)
    out = [None] * len(items)
    for key, positions in by_article.items():
        for n, answer in zip(positions, judge_article([items[n] for n in positions], articles[key], read, locate)):
            out[n] = answer
        print(f"decide: {' '.join(key)}: {len(positions)} claims", file=sys.stderr, flush=True)
    return out


def _searched(claim, article):
    """A claim with the whole article as its evidence, for a claim no search was run for."""
    return {**claim, "evidence": {"sql": "", "ms": 0, "terms": [], "searched": len(article), "passages": []}}


def run(items, pairs, rows_by_pair, articles, read, thresholds):
    """{threshold: (finding rows, set aside, claims, verdicts)}. The statement that contradicts a
    claim at the lowest threshold is asked back against the claim's own whole article."""
    answers = judge_all(items, articles, read)
    low = [verdict(c, a, min(thresholds)) for c, a in zip(items, answers)]
    back = [
        _searched(c, articles[(c["wikidata_id"], c["target_lang"], c["as_of"])])
        for c in claims.reverse_claims(items, low)
    ]
    back_answers = judge_all(back, articles, "article", locate=False) if back else []
    out = {}
    for t in thresholds:
        verdicts = [verdict(c, a, t) for c, a in zip(items, answers)]
        back_verdicts = [verdict(c, a, t) for c, a in zip(back, back_answers)]
        reverse = {c["reverses"]: (c, v) for c, v in zip(back, back_verdicts)}
        kept, aside = claims.findings(
            pairs, rows_by_pair, items + back, verdicts + back_verdicts, llm.DECISION_MODEL, reverse
        )
        out[t] = (kept, aside, items + back, verdicts + back_verdicts)
    return out


def main():
    global OFFLINE, MAX_REQUESTS
    ap = argparse.ArgumentParser(prog="python -m differences.decide", description=__doc__.split("\n\n")[0])
    ap.add_argument("evidence", help="the claims, with their evidence (gapfinder.evidence search)")
    ap.add_argument("pairs")
    ap.add_argument("rows")
    ap.add_argument("--articles", required=True, help="every passage of the articles, one per line")
    ap.add_argument("--read", choices=("article", "passages"), default="article")
    ap.add_argument("--threshold", type=float, nargs="+", default=[0.5])
    ap.add_argument("--out", required=True)
    ap.add_argument("--offline", action="store_true", help="answers from the cache only, no request")
    ap.add_argument("--max-requests", type=int, default=MAX_REQUESTS)
    args = ap.parse_args()
    OFFLINE, MAX_REQUESTS = args.offline, args.max_requests
    if min(args.threshold) < LOWEST:
        sys.exit(f"the lowest threshold is {LOWEST}")
    if not OFFLINE and not os.environ.get("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY is not in the environment")
    articles = {}
    for p in claims._read(args.articles):
        articles.setdefault((p["wikidata_id"], p["lang"], p["as_of"]), []).append(p)
    for passages in articles.values():
        passages.sort(key=lambda p: p["ord"])
    try:
        results = run(
            claims._read(args.evidence),
            claims._read(args.pairs),
            claims._rows_by_pair(args.rows),
            articles,
            args.read,
            args.threshold,
        )
    finally:
        print(
            f"{llm.DECISION_MODEL}, read {args.read}: {SENT['requests']} requests sent, "
            f"{SENT['tokens']:,} input tokens, {SENT['cached']} answers from the cache",
            file=sys.stderr,
        )
    for t, (kept, aside, items, verdicts) in results.items():
        out = Path(args.out) / f"t{round(t * 100)}"
        out.mkdir(parents=True, exist_ok=True)
        slim = [
            {
                **{
                    k: c.get(k)
                    for k in ("claim_id", "reverses", "pair_id", "row", "origin", "lang", "target_lang", "quote")
                },
                **{k: x for k, x in v.items() if k not in ("quote", "passage")},
                "evidence_quote": v["quote"],
                "passage": v["passage"] and v["passage"]["chunk_id"],
            }
            for c, v in zip(items, verdicts)
        ]
        for name, lines in (("differences.jsonl", kept), ("set-aside.jsonl", aside), ("verdicts.jsonl", slim)):
            with open(out / name, "w", encoding="utf-8") as f:
                f.writelines(json.dumps(line, ensure_ascii=False) + "\n" for line in lines)
        (out / "run.json").write_text(
            json.dumps({"judge": llm.DECISION_MODEL, "version": VERSION, "read": args.read, "threshold": t}) + "\n"
        )
        count = lambda xs, key: ", ".join(
            f"{k} {sum(1 for i in xs if i[key] == k)}" for k in sorted({i[key] for i in xs})
        )
        print(
            f"{out}: {len(items)} claims ({count(verdicts, 'verdict')}); {len(kept)} finding rows ({count(kept, 'type')}), {len(aside)} set aside"
        )


if __name__ == "__main__":
    main()
