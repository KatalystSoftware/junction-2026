"""Scratch: fits the chance that a won order arrives late from what the desk knows at the quote (spreadlab/slow.py),
over every saved week of one variant. Prints the weights, and the late share by band of the fitted chance.

    PYTHONPATH=. uv run python scratch/slow_fit.py --variant steep-notes-offers-8

Only orders with one car between two dealer sites. The fit is a logistic regression by Newton's method, in plain Python.
"""
from __future__ import annotations

import argparse
import json
import math

from spreadlab import curve, slow
from spreadlab.play import load_run
from spreadlab.policy import kind
from spreadlab.server import data_dir, drivers_near, near_places, world_map


def solve(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for i in range(n):
        pivot = max(range(i, n), key=lambda r: abs(m[r][i]))
        m[i], m[pivot] = m[pivot], m[i]
        for r in range(n):
            if r != i:
                f = m[r][i] / m[i][i]
                m[r] = [x - f * y for x, y in zip(m[r], m[i])]
    return [m[i][n] / m[i][i] for i in range(n)]


def fit(rows: list[list[float]], late: list[bool]) -> list[float]:
    n = len(rows[0])
    w = [0.0] * n
    for _ in range(25):
        gradient, hessian = [0.0] * n, [[1e-6 * (i == j) for j in range(n)] for i in range(n)]
        for x, y in zip(rows, late):
            p = 1 / (1 + math.exp(-sum(a * b for a, b in zip(w, x))))
            for i in range(n):
                if x[i]:
                    gradient[i] += (y - p) * x[i]
                    for j in range(n):
                        if x[j]:
                            hessian[i][j] += p * (1 - p) * x[i] * x[j]
        step = solve(hessian, gradient)
        w = [a + b for a, b in zip(w, step)]
        if max(abs(s) for s in step) < 1e-6:
            break
    return w


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default="steep-notes-offers-8")
    parser.add_argument("--every", type=int, default=1, help="read every n-th week")
    args = parser.parse_args()
    map_ = world_map()
    near = near_places(map_)
    minutes = {(r["from"], r["to"]): r["minutes"] for r in map_["roads"]}
    seeds = sorted(p.name[:-len("-L8.score.json")] for p in (data_dir() / "runs" / args.variant).glob("*-L8.score.json"))[::args.every]
    rows, late, held_out = [], [], []
    for n, seed in enumerate(seeds):
        try:
            run = load_run(args.variant, seed)
        except Exception:  # a week that is being written
            continue
        notified = drivers_near(run["roster"], near)
        requests = {e["request"]["id"]: e["request"] for e in run["events"] if e["kind"] == "price_request"}
        won = [e["order"]["id"] for e in run["events"] if e["kind"] == "order_won"]
        lates = {e["line"]["orderId"] for e in run["events"] if e["kind"] == "ledger" and e["line"]["kind"] in ("late_refund", "undelivered_penalty")}
        for id_ in won:
            q = requests[id_]
            if kind(q):
                continue
            leg = q["legs"][0]
            drive = minutes[(leg["pickup"]["placeId"], leg["delivery"]["placeId"])]
            ready = max(q["respondBy"], leg["pickup"]["window"]["from"])
            options = [o for o in q["options"] if o["deadline"] - drive - ready >= 300]
            if not options:
                continue
            rows.append(slow.known(q, curve.fastest(options), notified[leg["pickup"]["placeId"]], drive, len(run["roster"])))
            late.append(id_ in lates)
            held_out.append(n % 5 == 4)
    train = [(x, y) for x, y, h in zip(rows, late, held_out) if not h]
    weights = fit([x for x, _ in train], [y for _, y in train])
    print(f"{len(seeds)} weeks, {len(rows)} orders, {100 * sum(late) / len(late):.1f}% late; fitted on four weeks in five")
    print(json.dumps({name: round(w, 3) for name, w in zip(slow.NAMES, weights)}, indent=1))
    chance = lambda x: 1 / (1 + math.exp(-sum(a * b for a, b in zip(weights, x))))  # noqa: E731
    test = sorted((chance(x), y) for x, y, h in zip(rows, late, held_out) if h)
    print("The weeks left out, by the fitted chance:")
    edges = [0, 0.02, 0.03, 0.04, 0.06, 0.08, 0.12, 0.2, 0.3, 1.01]
    for low, high in zip(edges, edges[1:]):
        band = [(p, y) for p, y in test if low <= p < high]
        if band:
            print(f"  {100 * low:4.0f}-{100 * high:3.0f}%  {100 * len(band) / len(test):5.1f}% of orders  fitted {100 * sum(p for p, _ in band) / len(band):5.1f}%  late {100 * sum(y for _, y in band) / len(band):5.1f}%")
    print("Share of the orders left out with a chance at or under:", "  ".join(f"{100 * q:.0f}% -> {100 * sum(p <= q for p, _ in test) / len(test):.0f}%" for q in (0.03, 0.04, 0.05, 0.06, 0.08, 0.1, 0.15)))


main()
