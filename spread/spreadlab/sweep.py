"""Plays variants on a seed list, several weeks at once, and prints the comparison.

    python -m spreadlab.sweep --variants baseline,price-1.6 --list tune --count 10
    python -m spreadlab.sweep --variants baseline --seeds cat-001,cat-002

A week that is already saved with the same parameters and policy code is not played again.
A team holds at most 8 practice worlds that have not ended, on one key: with --parallel 7, one slot
stays free for a teammate.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .catalogue import load_seeds
from .play import failure_path, line, load_score, play
from .policy import fingerprint
from .report import compare
from .variants import VARIANTS


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variants", required=True, help="comma-separated names from variants.py; the first is the reference")
    parser.add_argument("--list", default="tune", help="a seed list of catalogue/seeds.json: tune or holdout")
    parser.add_argument("--count", type=int, default=10, help="the first seeds of the list")
    parser.add_argument("--seeds", help="comma-separated seeds, instead of --list")
    parser.add_argument("--level", type=int, default=8)
    parser.add_argument("--parallel", type=int, default=7)
    parser.add_argument("--force", action="store_true", help="play saved weeks again")
    args = parser.parse_args()
    variants = args.variants.split(",")
    seeds = args.seeds.split(",") if args.seeds else load_seeds(args.list, args.count)
    todo = []
    for seed in seeds:  # seed by seed, so that a sweep that stops early has whole rows to compare
        for variant in variants:
            saved = load_score(variant, seed, args.level)
            if args.force or saved is None or saved["fingerprint"] != fingerprint(VARIANTS[variant]):
                todo.append((variant, seed))
    print(f"{len(todo)} weeks to play, {len(variants) * len(seeds) - len(todo)} saved", flush=True)
    started, failed = time.time(), 0
    with ThreadPoolExecutor(args.parallel) as pool:
        futures = {pool.submit(play, variant, VARIANTS[variant], seed, args.level): (variant, seed) for variant, seed in todo}
        for future in as_completed(futures):
            try:
                print(line(future.result()), flush=True)
            except Exception as error:  # one failed week does not stop the others
                failed += 1
                path = failure_path(*futures[future], args.level)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"error": repr(error)}) + "\n", encoding="utf-8")
                print(f"{futures[future][0]} {futures[future][1]} FAILED: {error!r}", flush=True)
    if todo:
        print(f"{len(todo) - failed} weeks in {time.time() - started:.0f} s\n")
    compare(variants, seeds, args.level)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
