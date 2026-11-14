"""Print a seeded sample of a run's rows for a hand check, leaving out the rows already labelled.

    python3 demo/hero_sample.py RUN.jsonl [--per-type 8] [--seed 5] [--types numbers,contradiction]
                                [--aside]   # RUN.jsonl is a set-aside.jsonl: sample by verdict

Rows that hero-labels.json already judges (kept, by hero_score.py's rule) are skipped, so the
sample is of rows the labels do not cover. Each row is printed with what the check found: the
claim, the verdict, how many passages of the other edition were searched and the quote that
settled it, so the row can be judged against the article itself.
"""

import argparse
import json
import random
from pathlib import Path

from hero_score import outcome, sides

HERE = Path(__file__).resolve().parent


def show(n, row):
    langs = sides(row)
    print(
        f"[{n}] {row['wikidata_id']} {'/'.join(langs)} {row['type']}"
        + (f" missing in {row['missing_in']}" if row.get("missing_in") else "")
        + (f" verdict {row['verdict']}" if row.get("verdict") else "")
    )
    for lang, quote in langs.items():
        if quote:
            print(f"    {lang}: {quote}")
    print(f"    summary: {row['summary']}")
    for name, check in (("check", row), ("reverse", row.get("reverse") or {})):
        if check.get("checked"):
            c, e = check["checked"], check.get("evidence")
            print(
                f"    {name}: {check['claim']['lang']} claim in {c['lang']}, {c['searched']} passages searched, "
                f"{c['read']} read: {check['verdict']}"
                + (f"; {e['lang']} «{e['quote']}» ({e['section'] or 'lead'}, distance {e['distance']})" if e else "")
            )
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--per-type", type=int, default=8)
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--types")
    ap.add_argument("--aside", action="store_true")
    args = ap.parse_args()
    labels = json.loads((HERE / "hero-labels.json").read_text())["rows"]
    rows = [json.loads(line) for line in open(args.run, encoding="utf-8") if line.strip()]
    fresh = [r for r in rows if not any(outcome(label, [r])[0] == "kept" for label in labels)]
    key = (lambda r: r.get("verdict") or "none") if args.aside else (lambda r: r["type"])
    groups = sorted({key(r) for r in fresh})
    if args.types:
        groups = [g for g in groups if g in args.types.split(",")]
    random.seed(args.seed)
    n = 0
    for group in groups:
        mine = [r for r in fresh if key(r) == group]
        print(
            f"## {group}: {min(args.per_type, len(mine))} of {len(mine)} rows not labelled ({len(rows)} rows in all)\n"
        )
        for row in random.sample(mine, min(args.per_type, len(mine))):
            n += 1
            show(n, row)


if __name__ == "__main__":
    main()
