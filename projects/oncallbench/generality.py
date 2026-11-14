"""How the reference holds on seeds nobody tuned on: its share of what an oracle that knows the
faults avoids, per seed, with the whole distribution and the lower tail.

python3 generality.py --seeds 2000-2199 [--level N] [--out file.jsonl] [--jobs N]
"""

import argparse
import json
import multiprocessing
import statistics

import eval as E
import incident


def one(job):
    seed, level = job
    cost = {name: E.run(seed, level, name).total_cost() for name in ("nothing", "reference", "no-late")}
    null, ref = cost["nothing"], cost["reference"]
    return dict(seed=seed, level=level, cost_null=round(null, 2), cost_ref=round(ref, 2),
                ratio=round((null - ref) / (null - E.oracle(seed, level)), 4),
                no_late=round(incident.score(cost["no-late"], null, ref), 4))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", required=True, help="first-last, inclusive")
    ap.add_argument("--level", type=int, default=incident.SUBMITTED)
    ap.add_argument("--out")
    ap.add_argument("--jobs", type=int, default=10)
    opts = ap.parse_args()
    first, last = map(int, opts.seeds.split("-"))
    with multiprocessing.Pool(opts.jobs) as pool:
        rows = sorted(pool.imap_unordered(one, [(s, opts.level) for s in range(first, last + 1)]),
                      key=lambda r: r["seed"])
    if opts.out:
        with open(opts.out, "w") as f:
            f.writelines(json.dumps(r) + "\n" for r in rows)
    ratios = sorted(r["ratio"] for r in rows)
    cut = statistics.quantiles(ratios, n=20) if len(ratios) > 1 else ratios * 19
    below = [r["seed"] for r in rows if r["ratio"] < 0.75]
    print(json.dumps(dict(
        level=opts.level, seeds=opts.seeds, n=len(rows), min=ratios[0], p05=round(cut[0], 4),
        p25=round(cut[4], 4), median=round(statistics.median(ratios), 4), mean=round(statistics.mean(ratios), 4),
        p75=round(cut[14], 4), p95=round(cut[18], 4), max=ratios[-1], below_075=len(below),
        below_060=sum(r < 0.6 for r in ratios), worse_than_nothing=sum(r["cost_ref"] > r["cost_null"] for r in rows),
        no_late_at_1=sum(r["no_late"] >= 0.999 for r in rows), lowest=sorted(rows, key=lambda r: r["ratio"])[:5])))
