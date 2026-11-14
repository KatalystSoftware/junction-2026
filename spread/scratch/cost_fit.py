"""Scratch: what a won order costs and how often it is late, by what the desk knows at the quote.

    PYTHONPATH=. uv run --with scikit-learn python scratch/cost_fit.py [--write]

Rows are the won orders of the random-price weeks (curve_rows.py). The cost is fees, failed visits, waiting and late
refunds over the typical fee. Both models are scored on unseen weeks (5 folds by week) against one number for every
order. `--write` adds the weights to spreadlab/curve.json.
"""
import json, math, os, sys
import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge

here = os.path.dirname(os.path.abspath(__file__))
rows = [r for r in json.load(open(os.path.join(here, "curve_rows.json"))) if r["variant"] == "explore" and r["outcome"] == "won"]
seeds = sorted({r["seed"] for r in rows})
NAMES = ["long", "few_notified", "note", "same_day", "unbooked"]


def features(r):  # the same as spreadlab.curve.known
    return [max(0.0, r["fee"] / 100 - 150) / 100,  # the typical fee beyond 150 euros, in hundreds of euros: long lanes
            1 / (1 + r["notified"]),               # few drivers are notified of the pickup
            float(r["note"]), float(r["first"] == "same_day"), min(r["unbooked"], 15) / 10]


X = np.array([features(r) for r in rows])
cost = np.array([(r["fees"] + r["costs"] + r["late"]) / r["fee"] for r in rows])
late = np.array([0.0 if r["onTime"] else 1.0 for r in rows])
fold = np.array([seeds.index(r["seed"]) % 5 for r in rows])
weight = np.array([r["fee"] for r in rows], dtype=float)  # an error on a dear order costs more euros
flat, fitted, ll0, ll1 = [], [], [], []
for k in range(5):
    tr, te = fold != k, fold == k
    model = Ridge(alpha=1.0).fit(X[tr], cost[tr], sample_weight=weight[tr])
    flat.append(np.average(np.abs(cost[te] - np.average(cost[tr], weights=weight[tr])) * weight[te]) / 100)
    fitted.append(np.average(np.abs(cost[te] - model.predict(X[te])) * weight[te]) / 100)
    clf = LogisticRegression(C=1.0, max_iter=2000).fit(X[tr], late[tr])
    p0, p1 = np.full(te.sum(), late[tr].mean()), clf.predict_proba(X[te])[:, 1]
    loss = lambda p: float(-np.mean(late[te] * np.log(p) + (1 - late[te]) * np.log(1 - p)))
    ll0.append(loss(p0)); ll1.append(loss(p1))
print(f"{len(rows)} won orders in {len(seeds)} weeks; mean cost {np.average(cost, weights=weight):.3f} x fee (by euro), {100 * late.mean():.1f}% late")
print(f"cost, mean error in euros an order on unseen weeks: one number {np.mean(flat):.2f}, model {np.mean(fitted):.2f}")
print(f"late, log loss on unseen weeks: one rate {np.mean(ll0):.4f}, model {np.mean(ll1):.4f}")
model = Ridge(alpha=1.0).fit(X, cost, sample_weight=weight)
clf = LogisticRegression(C=1.0, max_iter=2000).fit(X, late)
print("cost  = %.3f" % model.intercept_, " ".join(f"{c:+.3f} {n}" for n, c in zip(NAMES, model.coef_)))
print("late: logit = %.3f" % clf.intercept_[0], " ".join(f"{c:+.3f} {n}" for n, c in zip(NAMES, clf.coef_[0])))
for name, f in (("short lane, many drivers", [0, 1 / 81, 0, 0, 0]), ("typical fee 200", [0.5, 1 / 21, 0, 0, 0]), ("typical fee 250, 3 notified", [1.0, 1 / 4, 0, 0, 0]), ("note, same day, 8 waiting", [0, 1 / 41, 1, 1, 0.8])):
    f = np.array([f]); print(f"  {name:30s} cost {model.predict(f)[0]:.2f} x fee, late {100 * clf.predict_proba(f)[0, 1]:.0f}%")
if "--write" in sys.argv:
    target = os.path.join(here, "..", "spreadlab", "curve.json")
    saved = json.load(open(target))
    saved["cost"] = {"intercept": round(float(model.intercept_), 4), "names": NAMES, "weights": [round(float(c), 4) for c in model.coef_]}
    saved["late"] = {"intercept": round(float(clf.intercept_[0]), 4), "names": NAMES, "weights": [round(float(c), 4) for c in clf.coef_[0]]}
    json.dump(saved, open(target, "w"), indent=1)
    print("wrote", os.path.normpath(target))
