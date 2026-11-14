"""Scratch: the win curve with a level for each week and day. Run after curve_fit.py's rows exist.

    PYTHONPATH=. uv run --with scikit-learn python scratch/curve_day.py
"""
import json, math, os, sys
import numpy as np
from sklearn.linear_model import LogisticRegression

here = os.path.dirname(os.path.abspath(__file__))
rows = [r for r in json.load(open(os.path.join(here, "curve_rows.json"))) if r["variant"] == "explore"]
seeds = sorted({r["seed"] for r in rows})
y = np.array([r["won"] for r in rows], dtype=float)


def feats(r, level):
    f = {"x": math.log(r["price"] / r["list"]), "trust": math.log(1 + 0.01 * r["trust"]), "kinds=" + "+".join(r["kinds"]): 1.0,
         "feelist": math.log(r["fee"] / r["list"]), "from=" + r["pickup"]: 1.0, "to=" + r["delivery"]: 1.0}
    if level:
        f[f"level={r['seed']} {r['day']}"] = 1.0
    return f


def fit(level, C):
    fs = [feats(r, level) for r in rows]
    names = sorted({k for f in fs for k in f})
    index = {n: i for i, n in enumerate(names)}
    X = np.zeros((len(rows), len(names)))
    for i, f in enumerate(fs):
        for k, v in f.items():
            X[i, index[k]] = v
    model = LogisticRegression(C=C, max_iter=5000).fit(X, y)
    return dict(zip(names, model.coef_[0])), float(model.intercept_[0])


for level, C in ((False, 1.0), (True, 1.0), (True, 10.0), (True, 100.0)):
    w, b = fit(level, C)
    levels = np.array([v for k, v in w.items() if k.startswith("level=")]) if level else np.zeros(1)
    counts = np.array([sum(1 for r in rows if f"level={r['seed']} {r['day']}" == k) for k in w if k.startswith("level=")]) if level else np.ones(1)
    slope = -w["x"]
    print(f"level {level} C {C}: slope {slope:.2f} trust {w['trust']:.2f} feelist {w['feelist']:+.3f} intercept {b:+.3f} mean level {levels.mean():+.3f} "
          f"sd of levels {levels.std():.3f} = {levels.std() / slope:.3f} in log price; median level {np.median(levels):+.3f}")
    if level and C == 10.0 and "--write" in sys.argv:
        part = lambda prefix: {n[len(prefix):]: round(float(v), 4) for n, v in sorted(w.items()) if n.startswith(prefix)}
        json.dump({"weeks": len(seeds), "quotes": len(rows), "intercept": round(b + float(np.median(levels)), 4),
                   "slope": round(slope, 4), "trust": round(float(w["trust"]), 4), "feelist": round(float(w["feelist"]), 4), "kinds": part("kinds="),
                   "from": part("from="), "to": part("to=")}, open(os.path.join(here, "..", "spreadlab", "curve-day.json"), "w"), indent=1)
        print("wrote curve-day.json")
