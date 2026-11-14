"""Scratch: what the live correction is worth, on random-price weeks the curve has not seen.

    PYTHONPATH=. uv run --with scikit-learn python scratch/curve_live.py

The curve (price, trust, options, fee/list, places) is fitted on four fifths of the weeks. On each other week the quotes
are read in time order, and before each quote the curve is shifted along the log price by what the desk has learned from
the answers it has had by that minute (an answer comes 15 minutes after its quote): one shift for the week, one for the
day and one for the dealer or for the pickup region today. Each is the most likely shift under a normal prior around 0.
Prints the log loss of each combination: lower is better.
"""
import collections, itertools, json, math, os
import numpy as np
from sklearn.linear_model import LogisticRegression

here = os.path.dirname(os.path.abspath(__file__))
rows = [r for r in json.load(open(os.path.join(here, "curve_rows.json"))) if r["variant"] == "explore"]
seeds = sorted({r["seed"] for r in rows})
BLOCKS = [lambda r: {"x": math.log(r["price"] / r["list"])}, lambda r: {"trust": math.log(1 + 0.01 * r["trust"])},
          lambda r: {"kinds=" + "+".join(r["kinds"]): 1}, lambda r: {"feelist": math.log(r["fee"] / r["list"])},
          lambda r: {"from=" + r["pickup"]: 1, "to=" + r["delivery"]: 1}]


def design(rows_, names=None):
    feats = [{k: float(v) for b in BLOCKS for k, v in b(r).items()} for r in rows_]
    names = names or sorted({k for f in feats for k in f})
    index = {n: i for i, n in enumerate(names)}
    X = np.zeros((len(rows_), len(names)))
    for i, f in enumerate(feats):
        for k, v in f.items():
            if k in index:
                X[i, index[k]] = v
    return X, names


def shift(z, won, slope, sd):
    d = 0.0
    for _ in range(12):
        p = 1 / (1 + np.exp(-(z + slope * d)))
        d += float(np.clip((slope * np.sum(won - p) - d / sd**2) / (slope**2 * np.sum(p * (1 - p)) + 1 / sd**2), -0.5, 0.5))
    return d


def loss(p, y):
    p = np.clip(np.array(p), 1e-6, 1 - 1e-6); y = np.array(y)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def play(week, z, slope, sds, level2):
    """The chance of each quote of one week, in time order, with the live shifts. sds: (week, day, second level)."""
    order = sorted(range(len(week)), key=lambda i: week[i]["at"])
    out = np.zeros(len(week))
    at = np.array([week[i]["at"] for i in range(len(week))]); day = at // 1440
    won = np.array([float(r["won"]) for r in week])
    key2 = np.array([level2(r) for r in week])
    cache = {}
    for i in order:
        known = at + 15 <= at[i]
        n = int(known.sum())
        if n not in cache:
            cache.clear()
            cache[n] = {}
        memo = cache[n]
        d = 0.0
        if sds[0] and "w" not in memo:
            memo["w"] = shift(z[known], won[known], slope, sds[0]) if n else 0.0
        d += memo.get("w", 0.0)
        if sds[1]:
            k = ("d", day[i])
            if k not in memo:
                sel = known & (day == day[i])
                memo[k] = shift(z[sel] + slope * d, won[sel], slope, sds[1]) if sel.any() else 0.0
            d += memo[k]
        if sds[2]:
            k = ("2", key2[i], day[i])
            if k not in memo:
                sel = known & (key2 == key2[i])
                # each earlier answer keeps the week shift of now; its own day's shift is not known here, so today's is used
                memo[k] = shift(z[sel] + slope * d, won[sel], slope, sds[2]) if sel.any() else 0.0
            d += memo[k]
        out[i] = 1 / (1 + math.exp(-(z[i] + slope * d)))
    return out


y = np.array([float(r["won"]) for r in rows])
fold = np.array([seeds.index(r["seed"]) % 5 for r in rows])
GRID = [("no correction", (0, 0, 0), None), ("week", (0.07, 0, 0), None), ("day", (0, 0.16, 0), None), ("week + day", (0.07, 0.14, 0), None),
        ("day 0.25", (0, 0.25, 0), None), ("week + day 0.25", (0.07, 0.25, 0), None),
        ("week + day + dealer 0.05", (0.07, 0.14, 0.05), "dealer"), ("week + day + dealer 0.10", (0.07, 0.14, 0.10), "dealer"),
        ("week + day + dealer 0.20", (0.07, 0.14, 0.20), "dealer"),
        ("week + day + pickup today 0.10", (0.07, 0.14, 0.10), "pickup"), ("week + day + pickup today 0.30", (0.07, 0.14, 0.30), "pickup")]
KEY2 = {None: lambda r: "", "dealer": lambda r: r["dealer"], "pickup": lambda r: f"{r['pickup']} {r['day']}"}
total = collections.defaultdict(list)
for k in range(5):
    train = [r for r, f in zip(rows, fold) if f != k]
    X, names = design(train)
    model = LogisticRegression(C=1.0, max_iter=3000).fit(X, y[fold != k])
    slope = -model.coef_[0][names.index("x")]
    for seed in [s for s in seeds if seeds.index(s) % 5 == k]:
        week = [r for r in rows if r["seed"] == seed]
        z = design(week, names)[0] @ model.coef_[0] + model.intercept_[0]
        for name, sds, level2 in GRID:
            total[name].append((play(week, z, slope, sds, KEY2[level2]), [float(r["won"]) for r in week], week))
print(f"{'correction (prior sd of each shift)':36s} log loss   on the day the curve fits worst in each week")
for name, _, _ in GRID:
    p = np.concatenate([p for p, _, _ in total[name]]); w = np.concatenate([w for _, w, _ in total[name]])
    worst = []
    for (p0, w0, week), (pn, _, _) in zip(total["no correction"], total[name]):
        days = np.array([r["day"] for r in week])
        bad = max(range(5), key=lambda d: loss(p0[days == d], np.array(w0)[days == d]) if (days == d).sum() > 30 else 0)
        worst.append(loss(pn[days == bad], np.array(w0)[days == bad]))
    print(f"{name:36s} {loss(p, w):.4f}     {np.mean(worst):.4f}")
