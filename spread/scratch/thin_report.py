"""Scratch: how near the 90% rule each variant ends in the weeks with a short driver list.

    PYTHONPATH=. uv run python scratch/thin_report.py --variants steep-notes-offers-8,thin-cost-1.4 --seeds fresh-042,...

The first variant is the reference. Only the seeds that every variant has played are counted.
"""
from __future__ import annotations

import argparse
import random
import statistics

from spreadlab.play import load_run, run_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", required=True)
    parser.add_argument("--seeds", required=True)
    args = parser.parse_args()
    variants = args.variants.split(",")
    seeds = [s for s in args.seeds.split(",") if all(run_path(v, s).exists() for v in variants)]
    runs = {v: [load_run(v, s) for s in seeds] for v in variants}
    scores = {v: [r["score"] for r in runs[v]] for v in variants}
    # The requests a week that the desk declined because of its backlog: at the gate, and as too slow for a filling backlog.
    declined = {v: [statistics.mean(sum(d["declined"] == why for d in r["decisions"].values()) for r in runs[v]) for why in ("backlog", "slow")] for v in variants}
    base = scores[variants[0]]
    print(f"{len(seeds)} weeks played by every variant. Margins in euros; reference: {variants[0]}.")
    print(f"{'variant':24} {'margin':>7} {'vs reference':>13} {'95% interval':>17} {'orders':>6} {'late':>5} {'on time':>8} {'<90%':>5} {'90-91':>6} {'91-92':>6} {'92-93':>6} {'lowest':>7} {'gate':>6} {'slow':>6}")
    for variant in variants:
        rows = scores[variant]
        on_time = [100 * r["onTimeShare"] for r in rows]
        count = lambda low, high: sum(low <= x < high for x in on_time)  # noqa: E731
        diff = [(r["marginCents"] - b["marginCents"]) / 100 for r, b in zip(rows, base)]
        rng = random.Random(1)
        means = sorted(statistics.mean(rng.choices(diff, k=len(diff))) for _ in range(4000))
        versus = "" if variant == variants[0] else f"{statistics.mean(diff):+,.0f}"
        interval = "" if variant == variants[0] else f"{means[100]:,.0f} to {means[3899]:,.0f}"
        late = statistics.mean((1 - r["onTimeShare"]) * r["wonOrders"] for r in rows)
        print(f"{variant:24} {statistics.mean(r['marginCents'] for r in rows) / 100:7,.0f} {versus:>13} {interval:>17} {statistics.mean(r['wonOrders'] for r in rows):6.0f} {late:5.1f} "
              f"{statistics.mean(on_time):7.1f}% {count(0, 90):5} {count(90, 91):6} {count(91, 92):6} {count(92, 93):6} {min(on_time):6.1f}% {declined[variant][0]:6.1f} {declined[variant][1]:6.1f}")


main()
