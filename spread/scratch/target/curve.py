"""The on-time target curve: for each variant and seed set, the margin a week with its 95% interval, the difference to the
candidate on the same seeds, orders, late orders, the mean and lowest on-time share, the weeks under 90%, and the same
for the thin worlds (under 720 drivers). Reads one row per played week; plays nothing.

    uv run python scratch/target/curve.py weeks.csv

Columns: variant, seed, drivers, margin (euros), orders, late, on_time (a share, 0 to 1). Sets by seed: `cat-` is tune,
`fresh-17..` is unseen A, `fresh-18..` is unseen B.
"""
from __future__ import annotations

import collections
import csv
import random
import statistics
import sys

CANDIDATE, THIN = "slow-friday-late-150-kinds-limits", 720


def seed_set(seed: str) -> str:
    return "tune" if seed.startswith("cat-") else "A" if seed.startswith("fresh-17") else "B" if seed.startswith("fresh-18") else "other"


def interval(values: list[float], draws: int = 10_000) -> tuple[float, float]:
    rng = random.Random(0)
    means = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(draws))
    return means[int(0.025 * draws)], means[int(0.975 * draws)]


def main(path: str) -> None:
    weeks = collections.defaultdict(dict)  # (set, variant) -> seed -> row
    for row in csv.DictReader(open(path, encoding="utf-8")):
        row = {**row, **{k: float(row[k]) for k in ("drivers", "margin", "orders", "late", "on_time")}}
        if row["on_time"] > 1:
            row["on_time"] /= 100
        weeks[(seed_set(row["seed"]), row["variant"])][row["seed"]] = row
    for set_ in ("tune", "A", "B", "other"):
        names = sorted({v for s, v in weeks if s == set_}, key=lambda v: (v != CANDIDATE, v))
        if not names:
            continue
        print(f"\n{set_}")
        print(f"{'variant':36} {'n':>3} {'margin':>7} {'95% interval':>16} {'vs cand':>7} {'95% interval':>16} {'ranked':>7} "
              f"{'orders':>6} {'late':>5} {'mean':>6} {'low':>6} {'<90%':>6} | thin: {'n':>2} {'margin':>7} {'low':>6} {'<90%':>4}")
        base = weeks.get((set_, CANDIDATE), {})
        for name in names:
            rows = weeks[(set_, name)]
            margins = [r["margin"] for r in rows.values()]
            ranked = [r["margin"] * (r["on_time"] >= 0.90) for r in rows.values()]
            paired = [rows[s]["margin"] * (rows[s]["on_time"] >= 0.9) - base[s]["margin"] * (base[s]["on_time"] >= 0.9) for s in rows if s in base]
            thin = [r for r in rows.values() if r["drivers"] < THIN]
            low = min(r["on_time"] for r in rows.values())
            under = sum(r["on_time"] < 0.90 for r in rows.values())
            lo, hi = interval(margins)
            diff = f"{statistics.fmean(paired):+7.0f} {'(%.0f to %.0f)' % interval(paired):>16}" if paired and name != CANDIDATE else f"{'':7} {'':16}"
            thin_txt = (f"{len(thin):2d} {statistics.fmean(r['margin'] for r in thin):7.0f} {min(r['on_time'] for r in thin):6.1%} "
                        f"{sum(r['on_time'] < 0.9 for r in thin):4d}") if thin else ""
            print(f"{name:36} {len(rows):3d} {statistics.fmean(margins):7.0f} {'(%.0f to %.0f)' % (lo, hi):>16} {diff} {statistics.fmean(ranked):7.0f} "
                  f"{statistics.fmean(r['orders'] for r in rows.values()):6.0f} {statistics.fmean(r['late'] for r in rows.values()):5.1f} "
                  f"{statistics.fmean(r['on_time'] for r in rows.values()):6.1%} {low:6.1%} {under:2d}/{len(rows):<3d} | thin: {thin_txt}")
            worst = sorted(rows.values(), key=lambda r: r["on_time"])[:3]
            print(f"{'':36}     lowest weeks: " + ", ".join(f"{r['seed']} {r['on_time']:.1%} ({r['drivers']:.0f} drivers)" for r in worst))


if __name__ == "__main__":
    main(sys.argv[1])
