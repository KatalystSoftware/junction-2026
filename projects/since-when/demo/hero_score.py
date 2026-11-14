"""Score a run's rows against the hand judgements of the hero topics.

    python3 demo/hero_score.py RUN.jsonl [RUN2.jsonl ...] [-v] [--labels demo/hero-labels.json]

RUN.jsonl holds one finding row per line, as hero_classify.py and hero_verify.py write them
(differences.jsonl). For every labelled row the run is asked whether it still reports the same
thing:

    kept    a row of the same type, between the same two editions, with the same quotes: both
            quotes for numbers, contradiction and framing; for a missing fact the quote of the
            edition that has the fact, and the same edition lacking it
    moved   a row the claim check wrote (it names the pair its claim came from) that shares one of
            the labelled row's quotes: the same statement is still reported, against other
            evidence or under another type. Listed with -v, to be judged by hand
    gone    nothing like it

Two quotes are the same when they share at least six in ten of the shorter one's words of three
letters or more. Per type the
table counts, of the rows the hand check called false, how many are gone, and of the rows it
called real, how many are kept: a real row that is gone is as bad as a false one that is kept.
The label file's `recheck` entries (labels a search of the stored article contradicts) are applied
in a second table.
"""

import argparse
import collections
import json
import re
from pathlib import Path

TYPES = ["missing_fact", "numbers", "contradiction", "framing"]
HERE = Path(__file__).resolve().parent


def words(text):
    """The words of three letters or more: "at", "on", "of" and "in" alone made a short quote match a long one."""
    return set(re.findall(r"\w{3,}", (text or "").lower()))


def same(x, y):
    """Whether two quotes share at least six in ten of the shorter one's words."""
    a, b = words(x), words(y)
    return bool(a and b) and len(a & b) / min(len(a), len(b)) >= 0.6


def sides(row):
    """A row's quotes by language, from its pair id (topic:date:lang:chunk:lang:chunk)."""
    _, _, a_lang, _, b_lang, _ = row["pair_id"].split(":")
    return {a_lang: row.get("quote_a") or "", b_lang: row.get("quote_b") or ""}


def outcome(label, rows):
    """("kept" | "moved" | "gone", the run's row or None) for one labelled row."""
    want = {label["a_lang"]: label["quote_a"], label["b_lang"]: label["quote_b"]}
    moved = None
    for row in rows:
        got = sides(row)
        if row["wikidata_id"] != label["wikidata_id"] or set(got) != set(want):
            continue
        hits = {lang for lang in want if same(want[lang], got[lang])}
        if label["type"] == "missing_fact":
            # The fact is quoted from the edition that has it; a row without missing_in names none.
            has = [lang for lang in want if lang != label["missing_in"] and want[lang]]
            full = bool(has) and all(lang in hits for lang in has) and row.get("missing_in") == label["missing_in"]
        else:
            full = hits == set(want)
        if full and row["type"] == label["type"]:
            return "kept", row
        if hits and moved is None and row.get("from_pair"):
            moved = row
    return ("moved", moved) if moved else ("gone", None)


def score(labels, rows, recheck=False):
    table = {t: collections.Counter() for t in TYPES}
    detail = []
    for label in labels:
        verdict = (label.get("recheck") or {}).get("label") if recheck else None
        verdict = verdict or label["label"]
        what, row = outcome(label, rows)
        table[label["type"]][(verdict, what)] += 1
        detail.append((label, verdict, what, row))
    return table, detail


def report(table):
    head = f"{'type':14}{'false':>6}{'gone':>6}{'moved':>6}{'kept':>6}  |{'real':>6}{'kept':>6}{'moved':>6}{'gone':>6}"
    lines = [head + f"  |{'unclear':>8}{'kept':>6}{'moved':>6}{'gone':>6}"]
    for t in TYPES:
        c = table[t]

        def n(verdict, c=c):
            return sum(c[(verdict, w)] for w in ("kept", "moved", "gone"))

        lines.append(
            f"{t:14}{n('false'):>6}{c[('false', 'gone')]:>6}{c[('false', 'moved')]:>6}{c[('false', 'kept')]:>6}  |"
            f"{n('real'):>6}{c[('real', 'kept')]:>6}{c[('real', 'moved')]:>6}{c[('real', 'gone')]:>6}  |"
            f"{n('unclear'):>8}{c[('unclear', 'kept')]:>6}{c[('unclear', 'moved')]:>6}{c[('unclear', 'gone')]:>6}"
        )
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--labels", default=HERE / "hero-labels.json")
    ap.add_argument("-v", action="store_true", help="list every labelled row with what became of it")
    args = ap.parse_args()
    labels = json.loads(Path(args.labels).read_text())["rows"]
    for path in args.runs:
        rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
        by_type = collections.Counter(r["type"] for r in rows)
        print(f"{path}: {len(rows)} rows (" + ", ".join(f"{t} {by_type[t]}" for t in TYPES) + ")")
        table, detail = score(labels, rows)
        print(report(table))
        if any(label.get("recheck") for label in labels):
            print("\nwith the rechecked labels:")
            print(report(score(labels, rows, recheck=True)[0]))
        if args.v:
            print()
            for label, verdict, what, row in detail:
                line = f"{label['id']:18}{verdict:8}{what:6} {label['note']}"
                if what == "moved":
                    line += f"\n{'':32}now {row['type']}: {json.dumps(sides(row), ensure_ascii=False)}"
                print(line)
        print()


if __name__ == "__main__":
    main()
