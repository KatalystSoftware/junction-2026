"""The settings a joint search moves, their ranges, and how a point becomes parameters of the base (spreadlab/standin/search.py
plays them; README.md here says how a search runs and is read).

    python scratch/search/space.py design --n 192 --seed 1 --out scratch/search/r1.json
    python scratch/search/space.py around --fit fit.json --n 192 --seed 2 --out scratch/search/r2.json

Every setting acts only in a week with 760 drivers or more (search.full_weeks); a thinner week plays as the base.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

BASE = "fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760"
# name: (low, high, the base's value, kind). Integers are rounded.
SPACE = {
    "slow_step": (0.0, 1.0, 0.8, "float"),
    "late_cost": (50, 200, 150, "int"),
    "cost": (1.0, 1.3, 1.2, "float"),
    "queue_hours": (6, 48, 24, "int"),
    "max_unbooked": (12, 35, 25, "int"),  # the gate never binds above 25 with the 24-hour count (the climb)
    "learn": (0.08, 0.26, 0.16, "float"),
    "open16": (0.65, 0.95, 0.8, "float"),   # the opening fee of the rule for cars with `hours16` hours or more
    "hours16": (10, 24, 16, "int"),
    "fee": (0.9, 1.15, 1.0, "float"),        # the opening fee of the other cars
    "fee_cap": (1.1, 1.4, 1.2, "float"),
    "offer_hours": (4, 16, 8, "int"),
    "offer_fee": (1.1, 1.45, 1.3, "float"),
    "min_slack": (240, 420, 300, "int"),
    "pair_onward_cost": (0.8, 1.2, 1.0, "float"),
    "pair_onward": (0.6, 1.0, 0.8, "float"),
    "kinds_scale": (0.85, 1.15, 1.0, "float"),  # the costs of the declined kinds, scaled together
    "premium_cost": (0.0, 0.30, 0.0, "float"),
}
NAMES = list(SPACE)
KINDS = {"private_pickup": {"cost": 1.6, "odds": 0.06}, "private_delivery": {"cost": 1.3, "odds": 0.37}, "trade_in": {"cost": 2.3, "fee": 1.4, "odds": 0.27}}


def unit(point: dict) -> np.ndarray:
    return np.array([(point[n] - SPACE[n][0]) / (SPACE[n][1] - SPACE[n][0]) for n in NAMES])


def point_of(u: np.ndarray) -> dict:
    out = {}
    for n, x in zip(NAMES, u):
        lo, hi, _, kind = SPACE[n]
        v = lo + float(np.clip(x, 0, 1)) * (hi - lo)
        out[n] = int(round(v)) if kind == "int" else round(v, 3)
    return out


def knobs(point: dict) -> dict:
    """The point as parameters of the base. Only settings off the base's value are named, so the base's own point is no change."""
    base = {n: SPACE[n][2] for n in NAMES}
    out = {}
    for n in ("slow_step", "late_cost", "cost", "queue_hours", "max_unbooked", "learn", "fee", "fee_cap", "offer_hours", "offer_fee",
              "min_slack", "pair_onward_cost", "pair_onward", "premium_cost"):
        if point[n] != base[n]:
            out[n] = point[n]
    if point["open16"] != base["open16"] or point["hours16"] != base["hours16"]:
        out["fee_rules"] = [[0, 10 ** 6, point["hours16"], 10 ** 6, point["open16"], 0.1, 1.2]]
    if point["kinds_scale"] != 1.0:
        out["kinds"] = {k: {**v, "cost": round(v["cost"] * point["kinds_scale"], 3)} for k, v in KINDS.items()}
    return out


def lhs(n: int, rng: np.random.Generator, tries: int = 40) -> np.ndarray:
    """A Latin hypercube in the unit cube, the one of `tries` with the widest smallest gap between points."""
    best, gap = None, -1.0
    for _ in range(tries):
        u = np.stack([(rng.permutation(n) + rng.random(n)) / n for _ in NAMES], axis=1)
        d = np.sqrt(((u[:, None] - u[None]) ** 2).sum(-1)) + np.eye(n) * 9
        if d.min() > gap:
            best, gap = u, d.min()
    return best


def write(points: list[dict], prefix: str, out: str) -> None:
    arms = {f"{prefix}-{i:03d}": knobs(p) for i, p in enumerate(points)}
    Path(out).write_text(json.dumps({"baseline": BASE, "points": {f"{prefix}-{i:03d}": p for i, p in enumerate(points)}, "arms": arms}, indent=0) + "\n")
    print(f"{len(arms)} arms to {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=["design", "around"])
    parser.add_argument("--n", type=int, default=192)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--prefix", default="")
    parser.add_argument("--centre", default="", help="around: a JSON point to sample around")
    parser.add_argument("--width", type=float, default=0.25, help="around: the sd of a step, in units of each range")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    rng = np.random.default_rng(args.seed)
    if args.mode == "design":
        u = lhs(args.n - 1, rng)
        points = [{n: SPACE[n][2] for n in NAMES}] + [point_of(x) for x in u]  # the base's own point first: a check of the arm machinery
    else:
        c = unit(json.loads(args.centre))
        points = [point_of(np.clip(c + rng.normal(0, args.width, len(NAMES)), 0, 1)) for _ in range(args.n)]
    write(points, args.prefix or Path(args.out).stem, args.out)


if __name__ == "__main__":
    main()
