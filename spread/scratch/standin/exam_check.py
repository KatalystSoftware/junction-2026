"""Sets a stand-in run on the merge exam's seeds beside the played exam rows: does it flag the weeks play had under 90%?

    python3 scratch/standin/exam_check.py <exam-rows.csv of trackb-rounds> <rows.csv of a screen run> [<rows.csv> ...]

For each variant in both files and each panel (the exam's natural-order seeds `fresh-8201` to `8260`, and its thin seeds): the weeks
under 90% and 92% in play and in the stand-in (a rate per 60 over all draws), the on-time share and its seed-by-seed correlation, and
how the stand-in ranks play's low weeks: for each played week under 92%, the share of its draws under 90% and 92% and its rank among
the panel's seeds by mean stand-in on-time share (1 is the stand-in's riskiest seed). The last line says how likely a played week
under 92% is to sit below a played week over it in the stand-in's order (0.5 is chance).
"""
from __future__ import annotations

import collections
import csv
import math
import sys


def corr(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sx, sy = math.sqrt(sum((x - mx) ** 2 for x in xs)), math.sqrt(sum((y - my) ** 2 for y in ys))
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy) if sx and sy else float("nan")


def main() -> None:
    played: dict = collections.defaultdict(dict)
    for r in csv.DictReader(open(sys.argv[1])):
        played[r["variant"]][r["seed"]] = r
    natural = {f"fresh-{i}" for i in range(8201, 8261)}
    for path in sys.argv[2:]:
        sim: dict = collections.defaultdict(lambda: collections.defaultdict(list))
        for r in csv.DictReader(open(path)):
            sim[r["variant"]][r["seed"]].append(r)
        print(f"== {path}")
        for variant in sim:
            for panel, keep in (("natural-order", lambda s: s in natural), ("thin", lambda s: s not in natural)):
                seeds = sorted(s for s in sim[variant] if keep(s))
                if not seeds:
                    continue
                draws = [float(w["on_time"]) for s in seeds for w in sim[variant][s]]
                mean = {s: sum(float(w["on_time"]) for w in sim[variant][s]) / len(sim[variant][s]) for s in seeds}
                margin = sum(float(w["ranked_margin"]) for s in seeds for w in sim[variant][s]) / len(draws)
                orders = sum(float(w["orders"]) for s in seeds for w in sim[variant][s]) / len(draws)
                print(f"\n{variant}, {panel}: {len(seeds)} seeds, {len(draws) // len(seeds)} draws")
                print(f"  stand-in: margin {margin:.0f}, orders {orders:.1f}, on time {sum(draws) / len(draws):.3f}, under 90% {60 * sum(d < 0.90 for d in draws) / len(draws):.2f} per 60, "
                      f"under 92% {60 * sum(d < 0.92 for d in draws) / len(draws):.2f} per 60, seeds with any draw under 90%: {sum(any(float(w['on_time']) < 0.90 for w in sim[variant][s]) for s in seeds)}")
                both = [s for s in seeds if s in played.get(variant, {})]
                if not both:
                    print("  no played week of this variant on these seeds")
                    continue
                p = {s: float(played[variant][s]["on_time"]) for s in both}
                ranked = lambda s: float(played[variant][s]["margin"]) if p[s] >= 0.90 else 0.0
                print(f"  played ({len(both)} seeds): margin {sum(map(ranked, both)) / len(both):.0f}, orders {sum(float(played[variant][s]['orders']) for s in both) / len(both):.1f}, "
                      f"on time {sum(p.values()) / len(both):.3f}, under 90% {60 * sum(v < 0.90 for v in p.values()) / len(both):.2f} per 60, under 92% {60 * sum(v < 0.92 for v in p.values()) / len(both):.2f} per 60")
                print(f"  seed by seed: on-time correlation {corr([p[s] for s in both], [mean[s] for s in both]):.2f}, "
                      f"orders {corr([float(played[variant][s]['orders']) for s in both], [sum(float(w['orders']) for w in sim[variant][s]) / len(sim[variant][s]) for s in both]):.2f}, "
                      f"late orders {corr([float(played[variant][s]['late']) for s in both], [sum(float(w['late']) for w in sim[variant][s]) / len(sim[variant][s]) for s in both]):.2f}")
                order = sorted(both, key=lambda s: mean[s])
                low = sorted((s for s in both if p[s] < 0.92), key=lambda s: p[s])
                for s in low:
                    ws = [float(w["on_time"]) for w in sim[variant][s]]
                    print(f"    {s}: played {p[s]:.3f} ({played[variant][s]['drivers']} drivers), stand-in mean {mean[s]:.3f}, lowest {min(ws):.3f}, "
                          f"draws under 90%: {sum(w < 0.90 for w in ws)}/{len(ws)}, under 92%: {sum(w < 0.92 for w in ws)}/{len(ws)}, rank {order.index(s) + 1} of {len(order)}")
                rest = [s for s in both if p[s] >= 0.92]
                if low and rest:
                    wins = sum((mean[a] < mean[b]) + 0.5 * (mean[a] == mean[b]) for a in low for b in rest)
                    print(f"  a played week under 92% sits below a played week over it in the stand-in's order with chance {wins / (len(low) * len(rest)):.2f}")
                riskiest = order[:5]
                print("  the stand-in's five riskiest seeds: " + ", ".join(f"{s} ({mean[s]:.3f}, played {p[s]:.3f})" for s in riskiest))


if __name__ == "__main__":
    main()
