"""Our own progress, played again from scratch on the stand-in: the milestones from the kit-like baseline to merge 1, each set beside its
played weeks on the same seeds.

    PYTHONPATH=. python3 scratch/standin/progress_check.py <stand-in rows.csv> [anchor variant]

`rows.csv` is a screen of the milestones (screen.py) on the seeds `natural thin cat`. For each variant with played weeks in the packed
archive it prints, on the seeds both have: the margin a week (a week under 90% on time counts as none), orders, on-time share and weeks
under 90%, played and stand-in. Then each variant's gain over the anchor (default: the reference `steep-notes-offers-8`, which has a
played week on every seed) on their common seeds, played with a 95% interval against the stand-in, natural and thin apart.
The stand-in measures each seed's market on the default desk's played week; no other variant's played week is read to play it.
"""
from __future__ import annotations

import csv
import sys

from spreadlab.standin import pack, run

rows: dict = {}
order: list[str] = []
for r in csv.DictReader(open(sys.argv[1])):
    if r["variant"] not in rows:
        order.append(r["variant"])
    rows.setdefault(r["variant"], {})[r["seed"]] = {"drivers": int(r["drivers"]), "margin": float(r["margin"]), "orders": int(r["orders"]), "on_time": float(r["on_time"])}
anchor = sys.argv[2] if len(sys.argv) > 2 else "steep-notes-offers-8"
played = {v: {s: run.played_week(v, s) for s in rows[v] if pack.week_path(v, s).exists()} for v in order}
mean = lambda xs: sum(xs) / len(xs) if xs else float("nan")
print(f"{'variant':44} {'seeds':>5} {'margin p':>8} {'margin s':>8} {'orders p':>8} {'orders s':>8} {'on time p':>9} {'on time s':>9} {'<90 p':>5} {'<90 s':>5}")
for v in order:
    seeds = sorted(played[v])
    if not seeds:
        print(f"{v[:44]:44} {0:5}  no played week in the archive; stand-in on all its seeds: margin {mean([run.ranked(w) for w in rows[v].values()]):.0f}, orders {mean([w['orders'] for w in rows[v].values()]):.1f}")
        continue
    p, s = [played[v][x] for x in seeds], [rows[v][x] for x in seeds]
    print(f"{v[:44]:44} {len(seeds):5} {mean([run.ranked(w) for w in p]):8.0f} {mean([run.ranked(w) for w in s]):8.0f} {mean([w['orders'] for w in p]):8.1f} {mean([w['orders'] for w in s]):8.1f} "
          f"{mean([w['on_time'] for w in p]):9.3f} {mean([w['on_time'] for w in s]):9.3f} {sum(w['on_time'] < 0.9 for w in p):5} {sum(w['on_time'] < 0.9 for w in s):5}")
agree = total = 0
for group, keep in (("natural", lambda d: d >= run.THIN), ("thin", lambda d: d < run.THIN), ("all", lambda d: True)):
    print(f"\ngain over {anchor}, {group} worlds: seeds, played (95% interval), stand-in, stand-in over the anchor on all its {group} seeds")
    for v in order:
        if v == anchor:
            continue
        seeds = [x for x in played[v] if x in played[anchor] and keep(rows[v][x]["drivers"])]
        every = [x for x in rows[v] if x in rows[anchor] and keep(rows[v][x]["drivers"])]
        wide = mean([run.ranked(rows[v][x]) - run.ranked(rows[anchor][x]) for x in every])
        if len(seeds) < 5:
            print(f"  {v[:44]:44} {len(seeds):4} {'':38} {wide:+7.0f} on {len(every)}")
            continue
        p = [run.ranked(played[v][x]) - run.ranked(played[anchor][x]) for x in seeds]
        s = [run.ranked(rows[v][x]) - run.ranked(rows[anchor][x]) for x in seeds]
        lo, hi = run.interval(p)
        same = (mean(p) > 0) == (mean(s) > 0)
        if group == "all":
            total += 1; agree += same
        print(f"  {v[:44]:44} {len(seeds):4} {mean(p):+7.0f} ({lo:+6.0f} to {hi:+6.0f}) {mean(s):+7.0f} {'' if same else 'OTHER SIGN':10} {wide:+7.0f} on {len(every)}")
print(f"\nSame sign of the gain over {anchor} in {agree} of {total} variants with played weeks.")
