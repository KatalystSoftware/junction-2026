"""The stand-in's ranking of policy pairs against play's, where the two were not played on the same seeds: played rows (a rows CSV of
`trackb-rounds`) against the rows of a stand-in screen (screen.py's rows.csv).

    python3 scratch/standin/pairs_check.py <played rows.csv> <stand-in rows.csv>

For every pair of variants in both files it prints the paired difference in play and in the stand-in (a week under 90% on time counts as
no margin), natural and thin worlds apart, and how often the two agree on which variant is ahead: over all pairs, and over the pairs
play decides (the played difference's 95% bootstrap interval excludes zero).
"""
from __future__ import annotations

import csv
import itertools
import random
import sys


def load(path: str) -> dict:
    out: dict = {}
    for r in csv.DictReader(open(path)):
        margin = float(r["margin"]) if float(r["on_time"]) >= 0.90 else 0.0
        out.setdefault(r["variant"], {}).setdefault(r["seed"], []).append({"drivers": int(r["drivers"]), "margin": margin, "orders": int(r["orders"]), "late": int(r["late"]), "on_time": float(r["on_time"])})
    return out


def diffs(rows: dict, a: str, b: str, thin) -> list[float]:
    mean = lambda ws: sum(w["margin"] for w in ws) / len(ws)
    return [mean(rows[a][s]) - mean(rows[b][s]) for s in rows[a] if s in rows[b] and (thin is None or (rows[a][s][0]["drivers"] < 720) == thin)]


def interval(d: list[float]) -> tuple[float, float]:
    r = random.Random(1)
    means = sorted(sum(r.choices(d, k=len(d))) / len(d) for _ in range(2000))
    return means[50], means[1949]


played, sim = load(sys.argv[1]), load(sys.argv[2])
names = [v for v in played if v in sim]
for group, thin in (("natural", False), ("thin", True), ("all", None)):
    print(f"\n{group}: variants a week, played / stand-in")
    for v in names:
        for label, rows in (("played", played), ("stand-in", sim)):
            ws = [w for s, wk in rows[v].items() for w in wk if thin is None or (w["drivers"] < 720) == thin]
            if ws:
                print(f"  {v[:44]:44} {label:8} weeks {len(ws):4} margin {sum(w['margin'] for w in ws) / len(ws):7.0f} orders {sum(w['orders'] for w in ws) / len(ws):6.1f} late {sum(w['late'] for w in ws) / len(ws):5.1f} "
                      f"under 90% {sum(w['on_time'] < 0.90 for w in ws):2} under 92% {sum(w['on_time'] < 0.92 for w in ws):2}")
    agree = decided = decided_agree = total = 0
    for a, b in itertools.combinations(names, 2):
        p, s = diffs(played, a, b, thin), diffs(sim, a, b, thin)
        if len(p) < 5 or len(s) < 5:
            continue
        mp, ms = sum(p) / len(p), sum(s) / len(s)
        lo, hi = interval(p)
        sure = lo > 0 or hi < 0
        total += 1; agree += (mp > 0) == (ms > 0); decided += sure; decided_agree += sure and (mp > 0) == (ms > 0)
        print(f"  {a[:30]:30} - {b[:30]:30} played {mp:+6.0f} ({lo:+.0f} to {hi:+.0f}, {len(p)} weeks) stand-in {ms:+6.0f} {'' if (mp > 0) == (ms > 0) else 'DISAGREE'}{'' if sure else ' (play undecided)'}")
    if total:
        print(f"  {group}: same variant ahead in {agree} of {total} pairs; of the {decided} pairs play decides, {decided_agree}")
