"""python -m differences classify PAIRS.jsonl > differences.jsonl
python -m differences evaluate [-v]"""

import argparse
import json
import sys

from . import llm
from .classify import classify_pairs
from .evaluate import evaluate, load, report


def main():
    ap = argparse.ArgumentParser(prog="python -m differences")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("classify", help="read aligned pairs as JSON lines, write one difference per line")
    c.add_argument("pairs", nargs="?", default="-")
    c.add_argument("--workers", type=int, default=8)
    e = sub.add_parser("evaluate", help="score against the hand-labelled pairs in eval/")
    e.add_argument("-v", "--verbose", action="store_true", help="list each wrong pair")
    e.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    if not llm.config():
        print("differences: no model key (see README.md), so no differences are written", file=sys.stderr)

    if args.cmd == "classify":
        src = sys.stdin if args.pairs == "-" else open(args.pairs, encoding="utf-8")
        pairs = (json.loads(line) for line in src if line.strip())
        for rows in classify_pairs(pairs, workers=args.workers):
            for row in rows:
                print(json.dumps(row, ensure_ascii=False), flush=True)
    else:
        result = evaluate(*load(), workers=args.workers)
        print(report(result))
        if args.verbose:
            print()
            for pair_id, t, kind in result["errors"]:
                print(f"{kind} {t:14} {pair_id}")


main()
