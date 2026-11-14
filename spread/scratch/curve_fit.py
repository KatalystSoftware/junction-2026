"""Scratch: fits the win curve on the random-price weeks and tests it on weeks it has not seen.

    PYTHONPATH=. uv run --with scikit-learn python scratch/curve_fit.py [--write]

The outcome is whether the dealer bought (won or later cancelled). Every model is fitted on some weeks and scored on the
others (5 folds by week), by log loss: lower is better, and the first line is the loss of one win rate for every quote.
`live` adds what the desk can learn inside a week: one shift of the curve along the price for the week, one for the day and
one for the dealer, each fitted on the answers the desk has had by the minute of the quote.
"""
import collections, json, math, os, sys
import numpy as np
from sklearn.linear_model import LogisticRegression

rows = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "curve_rows.json")))
rows = [r for r in rows if r["variant"] == "explore"]
seeds = sorted({r["seed"] for r in rows})
print(f"{len(rows)} quotes in {len(seeds)} weeks, {100 * sum(r['won'] for r in rows) / len(rows):.1f}% bought")

x = lambda r: math.log(r["price"] / r["list"])
trust = lambda r: math.log(1 + 0.01 * r["trust"])
BLOCKS = {
    "price": lambda r: {"x": x(r)},
    "trust": lambda r: {"trust": trust(r)},
    "options": lambda r: {"kinds=" + "+".join(r["kinds"]): 1},
    "fee/list": lambda r: {"feelist": math.log(r["fee"] / r["list"])},
    "day": lambda r: {f"day={r['day']}": 1},
    "hour": lambda r: {"late_hour": r["hour"] >= 15, "early_hour": r["hour"] < 10},
    "places": lambda r: {"from=" + r["pickup"]: 1, "to=" + r["delivery"]: 1},
    "dealer": lambda r: {"dealer=" + r["dealer"]: 1},
    "notified": lambda r: {"notified": math.log(1 + r["notified"])},
}


def design(blocks, rows_, names=None):
    feats = [{k: float(v) for b in blocks for k, v in BLOCKS[b](r).items()} for r in rows_]
    names = names or sorted({k for f in feats for k in f})
    index = {n: i for i, n in enumerate(names)}
    X = np.zeros((len(rows_), len(names)))
    for i, f in enumerate(feats):
        for k, v in f.items():
            if k in index:
                X[i, index[k]] = v
    return X, names


def loss(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


y = np.array([r["won"] for r in rows], dtype=float)
fold = np.array([seeds.index(r["seed"]) % 5 for r in rows])
print(f"{'model':46s} log loss on unseen weeks")
print(f"{'one win rate':46s} {np.mean([loss(np.full((fold == k).sum(), y[fold != k].mean()), y[fold == k]) for k in range(5)]):.4f}")
MODELS = [["price"], ["price", "trust"], ["price", "trust", "options"], ["price", "trust", "options", "fee/list"],
          ["price", "trust", "options", "fee/list", "day"], ["price", "trust", "options", "fee/list", "hour"],
          ["price", "trust", "options", "fee/list", "notified"], ["price", "trust", "options", "fee/list", "places"],
          ["price", "trust", "options", "fee/list", "dealer"], ["price", "trust", "options", "fee/list", "places", "dealer"]]
for blocks in MODELS:
    scores = []
    for k in range(5):
        train = [r for r, f in zip(rows, fold) if f != k]
        test = [r for r, f in zip(rows, fold) if f == k]
        X, names = design(blocks, train)
        model = LogisticRegression(C=1.0, max_iter=2000).fit(X, y[fold != k])
        scores.append(loss(model.predict_proba(design(blocks, test, names)[0])[:, 1], y[fold == k]))
    print(f"{' + '.join(blocks):46s} {np.mean(scores):.4f}")

CHOSEN = ["price", "trust", "options", "fee/list", "places"]  # the policy's curve (spreadlab/curve.py)
X, names = design(CHOSEN, rows)
model = LogisticRegression(C=1.0, max_iter=2000).fit(X, y)
print("\nfit on every week:", " + ".join(CHOSEN))
print(f"  intercept {model.intercept_[0]:+.3f}")
for n, c in sorted(zip(names, model.coef_[0]), key=lambda nc: -abs(nc[1]))[:40]:
    print(f"  {n:34s} {c:+.3f}")
if "--write" in sys.argv:  # the weights that spreadlab/curve.py reads
    weights = {n: round(float(c), 4) for n, c in zip(names, model.coef_[0])}
    part = lambda prefix: {n[len(prefix):]: w for n, w in sorted(weights.items()) if n.startswith(prefix)}
    target = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "spreadlab", "curve.json")
    kept = {k: v for k, v in json.load(open(target)).items() if k in ("cost", "late")} if os.path.exists(target) else {}  # written by cost_fit.py
    json.dump({**kept, "weeks": len(seeds), "quotes": len(rows), "intercept": round(float(model.intercept_[0]), 4), "slope": -weights["x"], "trust": weights["trust"],
               "feelist": weights["feelist"], "kinds": part("kinds="), "from": part("from="), "to": part("to=")}, open(target, "w"), indent=1)
    print("wrote", os.path.normpath(target))

# Calibration by week: how far each week's answers are from the curve, as a shift of the log price.
slope = -model.coef_[0][names.index("x")]
base = X @ model.coef_[0] + model.intercept_[0]


def shift(z, won, prior=0.0, sd=1e9, start=0.0):
    """The shift d of the log price that fits the answers best: logit = z + slope * d, with a normal prior on d."""
    d = start
    for _ in range(25):
        p = 1 / (1 + np.exp(-(z + slope * d)))
        grad = slope * np.sum(won - p) - (d - prior) / sd**2
        hess = slope**2 * np.sum(p * (1 - p)) + 1 / sd**2
        d += float(np.clip(grad / hess, -0.5, 0.5))
    return d


by_week = collections.defaultdict(list)
for i, r in enumerate(rows):
    by_week[r["seed"]].append(i)
week_shift = {s: shift(base[ix], y[ix]) for s, ix in by_week.items()}
ws = np.array(list(week_shift.values()))
print(f"\nslope of the curve: {slope:.2f} per unit of log price (a price 10% higher multiplies the odds by {math.exp(-slope * math.log(1.1)):.2f})")
print(f"week shifts (log price): sd {ws.std():.3f}, min {ws.min():+.3f}, max {ws.max():+.3f}")
day_shift = []
for s, ix in by_week.items():
    for day in range(5):
        dix = [i for i in ix if rows[i]["day"] == day]
        if len(dix) >= 40:
            day_shift.append((shift(base[dix] + slope * week_shift[s], y[dix]), s, day))
ds = np.array([d for d, _, _ in day_shift])
print(f"day shifts within a week: sd {ds.std():.3f}; the lowest five: " + ", ".join(f"{d:+.2f} ({s} day {day})" for d, s, day in sorted(day_shift)[:5]))
print("  lowest day of each week: mean %+.3f; second lowest: mean %+.3f" % tuple(
    np.mean([sorted(d for d, s2, _ in day_shift if s2 == s)[k] for s in by_week if sum(1 for _, s2, _ in day_shift if s2 == s) >= 4]) for k in (0, 1)))
