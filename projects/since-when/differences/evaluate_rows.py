"""Scores rows on disk against the hand labels in eval/, as evaluate.py scores the classifier live.

    python -m differences.evaluate_rows ROWS.jsonl [ROWS2.jsonl ...]

ROWS.jsonl is what `python -m differences classify eval/pairs.jsonl` wrote, or the differences.jsonl
of the claim check (claims.py) run on those rows: to see what the check does to the older labels.
A type counts as found for a pair when a row of that type came from it; a row born from a claim
names the pair its claim came from in `from_pair`.
"""
import json
import sys

from .classify import TYPES
from .evaluate import load


def score(pairs, labels, rows):
    """{type: {"tp", "fp", "fn", "precision", "recall"}} for rows grouped by the pair they came from."""
    got = {}
    for row in rows:
        got.setdefault(row.get("from_pair") or row["pair_id"], set()).add(row["type"])
    counts = {t: {"tp": 0, "fp": 0, "fn": 0} for t in TYPES}
    for pair in pairs:
        have, want = got.get(pair["pair_id"], set()), set(labels[pair["pair_id"]]["types"])
        for t in TYPES:
            if t in have and t in want:
                counts[t]["tp"] += 1
            elif t in have:
                counts[t]["fp"] += 1
            elif t in want:
                counts[t]["fn"] += 1
    for c in counts.values():
        c["precision"] = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else None
        c["recall"] = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else None
    return counts


def main():
    pairs, labels = load()
    fmt = lambda x: "  –  " if x is None else f"{x:5.2f}"
    for path in sys.argv[1:]:
        rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
        print(f"{path}: {len(rows)} rows, {len(pairs)} labelled pairs")
        print("type           labelled  found  right  precision  recall")
        for t, c in score(pairs, labels, rows).items():
            print(f"{t:14} {c['tp'] + c['fn']:8} {c['tp'] + c['fp']:6} {c['tp']:6}  {fmt(c['precision']):>9}  {fmt(c['recall']):>6}")
        print()


if __name__ == "__main__":
    main()
