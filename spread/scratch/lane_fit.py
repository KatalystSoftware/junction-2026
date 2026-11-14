"""Fits the lanes' usual driver fees: the mean of the log of the requests' typical fee by pickup place,
delivery place and whether an address is private, for lanes with at least 20 requests.

A request's typical fee is its lane's usual fee times noise that the drivers do not share, so a gig posted at
the lane's usual fee pays what the drivers of that lane expect. The fit reads scans only, and leaves out the
first 50 seeds of each list (the sweeps play those) and every `fresh` seed.

    PYTHONPATH=. uv run python scratch/lane_fit.py --write
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from spreadlab.policy import lane
from spreadlab.scan import load_scan

SKIP, LEAST = 50, 20


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true", help="write spreadlab/lanes.json")
    args = parser.parse_args()
    lists = json.loads(Path("catalogue/seeds.json").read_text(encoding="utf-8"))
    seeds = [seed for name in ("tune", "holdout") for seed in lists[name][SKIP:]]
    logs: dict[str, list[float]] = defaultdict(list)
    for seed in seeds:
        for event in load_scan(seed)["events"]:
            if event["kind"] == "price_request" and len(event["request"]["legs"]) == 1:
                logs[lane(event["request"])].append(math.log(event["request"]["referenceFeeCents"]))
    kept = {key: round(sum(values) / len(values), 4) for key, values in sorted(logs.items()) if len(values) >= LEAST}
    requests = sum(len(values) for values in logs.values())
    covered = sum(len(values) for key, values in logs.items() if key in kept)
    spread = math.sqrt(sum((v - kept[key]) ** 2 for key, values in logs.items() if key in kept for v in values) / covered)
    print(f"{len(seeds)} scans, {requests} one-car requests, {len(logs)} lanes, {len(kept)} with {LEAST} or more requests "
          f"({covered / requests:.1%} of the requests); sd of the log fee within a lane {spread:.3f}")
    if args.write:
        Path("spreadlab/lanes.json").write_text(json.dumps(kept, indent=0, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
