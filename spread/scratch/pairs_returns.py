"""The return traffic of each lane, for the out-and-back pairs (spreadlab/pairs.py): how many one-car dealer requests a
week run back from near its delivery place to near its pickup place, both ends within `near` km. Writes
spreadlab/returns.json with --write, and prints how often a request had such a return within the hold, by its lane's
traffic, so the hold's threshold can be read off.

usage: PYTHONPATH=. uv run python scratch/pairs_returns.py [--near 30] [--hold 4] [--write]"""
from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import Counter
from pathlib import Path

from spreadlab.server import data_dir

ROOT = Path(__file__).resolve().parent.parent


def one_car_dealer(request: dict) -> bool:
    if len(request["legs"]) != 1:
        return False
    leg = request["legs"][0]
    return not (leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--near", type=float, default=30)
    parser.add_argument("--hold", type=float, default=4)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = data_dir()
    places = {p["id"]: (p["lat"], p["lon"]) for p in json.loads((data / "map.json").read_text())["places"]}

    def km(a: str, b: str) -> float:
        (la, lo), (lb, lob) = places[a], places[b]
        x = math.radians(lob - lo) * math.cos(math.radians((la + lb) / 2))
        return 6371 * math.hypot(x, math.radians(lb - la))

    near = {a: {b for b in places if km(a, b) <= args.near} for a in places}
    lanes: Counter = Counter()
    weeks = 0
    rows = []  # (lane, had a return within the hold)
    files = sorted((data / "scans").glob("*-L8.json.gz"))
    for path in files:
        events = json.loads(gzip.open(path).read())["events"]
        rs = [(e["request"]["arrivedAt"], e["request"]["legs"][0]["pickup"]["placeId"], e["request"]["legs"][0]["delivery"]["placeId"])
              for e in events if e["kind"] == "price_request" and one_car_dealer(e["request"])]
        weeks += 1
        lanes.update((a, b) for _, a, b in rs)
        for i, (t, a, b) in enumerate(rs):
            back = any(t < t2 <= t + args.hold * 60 and c in near[b] and d in near[a] for t2, c, d in rs[i + 1:i + 400])
            rows.append(((a, b), back))
    returns = {f"{a}>{b}": round(sum(n for (c, d), n in lanes.items() if c in near[b] and d in near[a]) / weeks, 2) for a in places for b in places}
    print(f"{weeks} weeks, {len(rows) / weeks:.0f} one-car dealer requests a week")
    print("returns a week on the lane | share of requests | had a return within the hold")
    edges = [0, 1, 2, 4, 8, 16, 32, 64, 10**6]
    for lo, hi in zip(edges, edges[1:]):
        sel = [back for lane, back in rows if lo <= returns[f"{lane[0]}>{lane[1]}"] < hi]
        if sel:
            print(f"  {lo:>3} to {hi:<7}  {len(sel) / len(rows):6.1%}  {sum(sel) / len(sel):6.1%}")
    if args.write:
        (ROOT / "spreadlab" / "returns.json").write_text(json.dumps({k: v for k, v in sorted(returns.items()) if v}, indent=0) + "\n")


if __name__ == "__main__":
    main()
