"""Scratch: per week and due day, the one-car orders due (last pickup that day), how many ended late, the drops in the
night's first hour and the gigs held as it started; whether one night a week stands out (the flu day of RULES.md);
and how the late share of a day's cars grows with how many are due, with and without a wave.

    PYTHONPATH=. uv run --with numpy python scratch/exposure/days.py     # reads data/exposure/*.pkl (measure.py rows)
"""
import collections
import pickle
import sys

import numpy as np

from spreadlab.server import data_dir

DAY, WAVE = 1440, 10
for p in sorted((data_dir() / "exposure").glob("*.pkl")):
    weeks = pickle.load(open(p, "rb"))
    print(f"\n=== {p.stem}: {len(weeks)} weeks")
    top = collections.Counter(); rows = []
    for w in weeks:
        shares = {d: w["first_hour"].get(d, 0) / w["night"][d][0] for d in range(1, 5) if w["night"].get(d, (0, 0))[0] >= 20}
        if shares:
            d, s = max(shares.items(), key=lambda kv: kv[1])
            rest = sorted(shares.values())[-2] if len(shares) > 1 else 0
            top[(d, "stands out" if s >= 0.12 and s - rest >= 0.08 else "none")] += 1
        due = collections.Counter(o["last"] // DAY for o in w["orders"] if not o["cancelled"])
        late = collections.Counter(o["last"] // DAY for o in w["orders"] if not o["cancelled"] and o["late"])
        for d in range(1, 5):
            rows.append((due[d], late[d], w["first_hour"].get(d, 0) >= WAVE, w["drivers"], w["night"].get(d, (0, 0))[0]))
    print("the night with the highest share dropped (nights with 20+ held), by weekday Tue-Fri, standing out (>=12%, 8 points over the next) or not:")
    print("  ", {f"{['Mon','Tue','Wed','Thu','Fri'][d]} {k}": v for (d, k), v in sorted(top.items())}, f"weeks with no night of 20 held: {len(weeks) - sum(top.values())}")
    A = np.array(rows, float); n, l, wave, drivers, held = A.T
    for label, keep in (("calm", wave == 0), ("wave", wave == 1)):
        print(f"  {label} days: late share of the day's cars by cars due:", "  ".join(
            f"{a}-{b}: {l[keep & (n >= a) & (n < b)].sum() / max(1, n[keep & (n >= a) & (n < b)].sum()):.3f} ({int((keep & (n >= a) & (n < b)).sum())} days)" for a, b in ((0, 30), (30, 50), (50, 70), (70, 90), (90, 110), (110, 999))))
        for lo, hi in ((0, 720), (720, 800), (800, 9999)):
            k = keep & (drivers >= lo) & (drivers < hi)
            print(f"     drivers {lo}-{hi}: by cars due per 100 drivers:", "  ".join(
                f"{a}-{b}: {l[k & (100 * n / drivers >= a) & (100 * n / drivers < b)].sum() / max(1, n[k & (100 * n / drivers >= a) & (100 * n / drivers < b)].sum()):.3f}"
                f"({int((k & (100 * n / drivers >= a) & (100 * n / drivers < b)).sum())})" for a, b in ((0, 4), (4, 7), (7, 10), (10, 13), (13, 99))))
    # Poisson-ish fit: late of a day = n x sig(a + b wave + c n/drivers x 100 + e wave n/drivers x 100)
    X = np.column_stack([np.ones_like(n), wave, 100 * n / drivers, wave * 100 * n / drivers]); keep = n > 0
    X, y, m = X[keep], l[keep], n[keep]
    beta = np.zeros(4); beta[0] = np.log(y.sum() / (m.sum() - y.sum()))
    for _ in range(50):
        pr = 1 / (1 + np.exp(-X @ beta))
        beta += np.linalg.solve(X.T @ (X * (m * pr * (1 - pr))[:, None]) + 1e-6 * np.eye(4), X.T @ (y - m * pr))
    print(f"  binomial fit of a day's late share: intercept {beta[0]:.3f}, wave {beta[1]:+.3f}, per car due per 100 drivers {beta[2]:+.4f}, extra on a wave day {beta[3]:+.4f}")
