"""Scratch: how far dealers truly differ from the day's level, and whether a dealer's level moves with our win share there.

    PYTHONPATH=. uv run --with numpy python scratch/dealer_truth.py

1. Spread of the dealers' week offsets: each dealer-week offset fitted in hindsight with a flat prior, its variance minus
   the mean of the offsets' sampling variances (method of moments), for dealers with at least 30 answers.
2. The competitor lowers its prices each morning at dealers where we won most of their recent requests (RULES.md). For
   each dealer and day from Tuesday: the hindsight offset of that dealer-day against our win share at the dealer the
   day before, with the day's shift at its hindsight value; within a dealer's week, so that a dealer that accepts more
   (and where the desk wins more) does not count. A negative slope is the drift a filter has to follow.
"""
import os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dealer_filter as f

weeks = {**f.load("explore"), **f.load("steep-notes-offers-8")}
offs, ses, slope_rows = [], [], []
for seed, week in weeks.items():
    o, D = f.hindsight(week, dealer_sd=1.0)
    for d, (m, v, n) in o.items():
        if n >= 30:
            offs.append(m); ses.append(v)
    # dealer-day offsets with the day's shift fixed at its hindsight value
    z = np.array([r["z"] for r in week]); x = np.array([r["x"] for r in week]); won = np.array([float(r["won"]) for r in week])
    day = np.array([r["day"] for r in week]); dealer = np.array([r["dealer"] for r in week])
    for dd in range(1, 5):
        for d in set(dealer[day == dd]):
            sel, prev = (day == dd) & (dealer == d), (day == dd - 1) & (dealer == d)
            if sel.sum() < 8 or prev.sum() < 8:
                continue
            od = 0.0
            for _ in range(20):
                p = f.sig(z[sel] - f.SLOPE * (x[sel] - D[dd] - od))
                od += np.clip((f.SLOPE * np.sum(won[sel] - p) - od / 0.3**2) / (f.SLOPE**2 * np.sum(p * (1 - p)) + 1 / 0.3**2), -0.3, 0.3)
            slope_rows.append((won[prev].mean(), od, seed.startswith("explore"), sel.sum(), f"{seed} {d}"))
offs, ses = np.array(offs), np.array(ses)
print(f"1. dealer-week offsets with 30+ answers: {len(offs)}; sd of the estimates {offs.std():.4f}, mean sampling sd {np.sqrt(ses.mean()):.4f},"
      f" true sd by moments {np.sqrt(max(0, offs.var() - ses.mean())):.4f}")
# Within each dealer-week: a dealer that accepts more is also one where we win more, so the persistent part is taken out
# by subtracting the dealer-week's mean of both, which leaves the moves from day to day.
groups = {}
for r in slope_rows:
    groups.setdefault(r[4], []).append(r)
within = []
for rs in groups.values():
    if len(rs) < 2:
        continue
    ms, mo = np.mean([r[0] for r in rs]), np.mean([r[1] for r in rs])
    within += [(r[0] - ms, r[1] - mo, r[2], r[3]) for r in rs]
for label, keep, data in (("all weeks", lambda r: True, slope_rows), ("random-price weeks", lambda r: r[2], slope_rows),
                          ("reference weeks", lambda r: not r[2], slope_rows),
                          ("within dealer-week, random-price weeks", lambda r: r[2], within), ("within dealer-week, reference weeks", lambda r: not r[2], within)):
    a = np.array([(r[0], r[1], r[3]) for r in data if keep(r)])
    w = a[:, 2]
    X = np.c_[np.ones(len(a)), a[:, 0]]
    beta = np.linalg.solve(X.T @ (X * w[:, None]), X.T @ (w * a[:, 1]))
    rng = np.random.default_rng(0)
    bs = []
    for _ in range(2000):
        i = rng.integers(0, len(a), len(a))
        bs.append(np.linalg.solve(X[i].T @ (X[i] * w[i, None]), X[i].T @ (w[i] * a[i, 1]))[1])
    print(f"2. {label}: {len(a)} dealer-days; offset = {beta[0]:+.4f} {beta[1]:+.4f} x yesterday's win share there"
          f" (95% interval of the slope {np.percentile(bs, 2.5):+.4f} to {np.percentile(bs, 97.5):+.4f})")
