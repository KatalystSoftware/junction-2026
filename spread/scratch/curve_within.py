"""Scratch: the win curve fitted with one level for each week and day, against the curve fitted without them.

    PYTHONPATH=. uv run --with scikit-learn python scratch/curve_within.py

Days differ in what dealers accept. A fit that gives every day the same level reads those differences as noise, which
flattens its slope. With a level per week and day the slope is the one that holds inside a day, which is the one that
counts once the desk measures the day's level live. Both fits are scored on unseen weeks (5 folds by week), read in time
order with the live day shift of curve_live.py, by log loss: lower is better.
"""
import json, math, os
import numpy as np
from sklearn.linear_model import LogisticRegression

here = os.path.dirname(os.path.abspath(__file__))
rows = [r for r in json.load(open(os.path.join(here, "curve_rows.json"))) if r["variant"] == "explore"]
seeds = sorted({r["seed"] for r in rows})
BLOCKS = [lambda r: {"x": math.log(r["price"] / r["list"])}, lambda r: {"trust": math.log(1 + 0.01 * r["trust"])},
          lambda r: {"kinds=" + "+".join(r["kinds"]): 1}, lambda r: {"feelist": math.log(r["fee"] / r["list"])},
          lambda r: {"from=" + r["pickup"]: 1, "to=" + r["delivery"]: 1}]
LEVEL = lambda r: {f"level={r['seed']}:{r['day']}": 1}


def design(rows_, blocks, names=None):
    feats = [{k: float(v) for b in blocks for k, v in b(r).items()} for r in rows_]
    names = names or sorted({k for f in feats for k in f})
    index = {n: i for i, n in enumerate(names)}
    X = np.zeros((len(rows_), len(names)))
    for i, f in enumerate(feats):
        for k, v in f.items():
            if k in index:
                X[i, index[k]] = v
    return X, names


def fit(train, levels):
    """The weights without the levels, the intercept with the mean level in it, the slope and the levels in log price."""
    X, names = design(train, BLOCKS + ([LEVEL] if levels else []))
    model = LogisticRegression(C=10.0, max_iter=5000).fit(X, np.array([float(r["won"]) for r in train]))
    weights = dict(zip(names, model.coef_[0]))
    slope = -weights["x"]
    level = {n[6:]: w for n, w in weights.items() if n.startswith("level=")}
    mean = float(np.mean(list(level.values()))) if level else 0.0
    return {n: w for n, w in weights.items() if not n.startswith("level=")}, model.intercept_[0] + mean, slope, {k: (v - mean) / slope for k, v in level.items()}


def shift(z, won, slope, sd):
    d = 0.0
    for _ in range(12):
        p = 1 / (1 + np.exp(-(z + slope * d)))
        d += float(np.clip((slope * np.sum(won - p) - d / sd**2) / (slope**2 * np.sum(p * (1 - p)) + 1 / sd**2), -0.5, 0.5))
    return d


def loss(p, y):
    p = np.clip(np.array(p), 1e-6, 1 - 1e-6); y = np.array(y)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def live(week, z, slope, sd):
    at = np.array([r["at"] for r in week]); day = at // 1440; won = np.array([float(r["won"]) for r in week])
    out = np.zeros(len(week)); memo = {}
    for i in np.argsort(at):
        sel = (at + 15 <= at[i]) & (day == day[i])
        key = (day[i], int(sel.sum()))
        if key not in memo:
            memo[key] = shift(z[sel], won[sel], slope, sd) if sd and sel.any() else 0.0
        out[i] = 1 / (1 + math.exp(-(z[i] + slope * memo[key])))
    return out


if __name__ == "__main__":
    weights, intercept, slope, level = fit(rows, True)
    values = np.array(list(level.values()))
    by_seed = {s: [level[f"{s}:{d}"] for d in range(5) if f"{s}:{d}" in level] for s in seeds}
    print(f"fit on every week with levels: slope {slope:.2f}, trust {weights['trust']:.2f}, intercept {intercept:+.2f}")
    print(f"levels in log price: sd {values.std():.3f}; week means sd {np.std([np.mean(v) for v in by_seed.values()]):.3f}; "
          f"days within a week sd {np.mean([np.std(v) for v in by_seed.values()]):.3f}; lowest day of a week {np.mean([min(v) for v in by_seed.values()]):+.3f}, "
          f"second lowest {np.mean([sorted(v)[1] for v in by_seed.values()]):+.3f}, highest {np.mean([max(v) for v in by_seed.values()]):+.3f}")
    print("by day of the week:", " ".join(f"{np.mean([v[d] for v in by_seed.values() if len(v) == 5]):+.3f}" for d in range(5)))
    results = {}
    for k in range(5):
        train = [r for r in rows if seeds.index(r["seed"]) % 5 != k]
        for name, levels in (("without levels", False), ("with levels", True)):
            weights, intercept, slope, _ = fit(train, levels)
            for seed in [s for s in seeds if seeds.index(s) % 5 == k]:
                week = [r for r in rows if r["seed"] == seed]
                X, _ = design(week, BLOCKS, sorted(weights))
                z = X @ np.array([weights[n] for n in sorted(weights)]) + intercept
                for sd in (0, 0.10, 0.16, 0.25, 0.40):
                    results.setdefault((name, sd), []).append((live(week, z, slope, sd), [float(r["won"]) for r in week]))
    print(f"{'fit':16s} " + " ".join(f"sd {sd:4.2f}" for sd in (0, 0.10, 0.16, 0.25, 0.40)))
    for name in ("without levels", "with levels"):
        print(f"{name:16s} " + " ".join(f"{loss(np.concatenate([p for p, _ in results[name, sd]]), np.concatenate([w for _, w in results[name, sd]])):7.4f}" for sd in (0, 0.10, 0.16, 0.25, 0.40)))
