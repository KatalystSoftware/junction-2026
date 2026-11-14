"""Scratch: the scanned seeds whose driver list is shorter than a limit, as a comma-separated list.

    PYTHONPATH=. uv run python scratch/thin_seeds.py --prefix fresh --first 142 --last 301 --under 720
"""
from __future__ import annotations

import argparse
import gzip
import json

from spreadlab.server import data_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="fresh")
    parser.add_argument("--first", type=int, required=True)
    parser.add_argument("--last", type=int, required=True)
    parser.add_argument("--under", type=int, default=720)
    args = parser.parse_args()
    thin = []
    for number in range(args.first, args.last + 1):
        seed = f"{args.prefix}-{number:03d}"
        path = data_dir() / "scans" / f"{seed}-L8.json.gz"
        if path.exists() and len(json.loads(gzip.open(path).read())["roster"]) < args.under:
            thin.append(seed)
    print(",".join(thin))


main()
