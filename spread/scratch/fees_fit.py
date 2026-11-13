"""Scratch: how well what the policy sees at the quote predicts an order's cost, leaving one week out."""
import json, sys, collections, statistics
import numpy as np
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.ensemble import HistGradientBoostingRegressor
rows = [r for r in json.load(open(sys.argv[1])) if r["legs"] == 1]
tune = set(json.load(open("catalogue/seeds.json"))["tune"])
rows = [r for r in rows if r["seed"] in tune]
print(len(rows), "orders on", len({r["seed"] for r in rows}), "tune weeks")
def x(r):
    return [np.log(r["ref"] / 100), r["ref"] / r["list"], np.log1p(r["notified"]), np.log1p(r["notifiedDelivery"]), r["minutes"] / 60, min(r["slack"], 3000) / 60,
            r["option"] == "same_day", r["option"] == "within_3_days", r["hour"], r["day"], r["premium"], r["note"], r["weekTight"], r["situation"] == "snow", r["situation"] == "bulk_order"]
names = "logRef ref/list logNotified logNotifiedDelivery driveHours slackHours same_day within_3 hour day premium note weekTight snow bulk".split()
X = np.array([x(r) for r in rows], float)
seeds = np.array([r["seed"] for r in rows])
for target_name, y in (("fees/ref", np.array([r["fees"] / r["ref"] for r in rows])), ("(fees+costs+late)/ref", np.array([(r["fees"] + r["costs"] + r["late"]) / r["ref"] for r in rows]))):
    print(f"\n{target_name}: mean {y.mean():.3f} sd {y.std():.3f}")
    for model_name, make in (("linear", LinearRegression), ("boosted", lambda: HistGradientBoostingRegressor(max_depth=3, max_iter=150, learning_rate=0.05))):
        pred = np.zeros(len(y))
        for seed in sorted(set(seeds)):
            m = make().fit(X[seeds != seed], y[seeds != seed]); pred[seeds == seed] = m.predict(X[seeds == seed])
        print(f"  {model_name:8s} leave-one-week-out R2 {1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum():.3f}  mean abs error {np.abs(y - pred).mean():.3f}  (constant: {np.abs(y - y.mean()).mean():.3f})")
    m = LinearRegression().fit((X - X.mean(0)) / X.std(0), y)
    print("  linear, per standard deviation:", "  ".join(f"{n} {c:+.3f}" for n, c in sorted(zip(names, m.coef_), key=lambda t: -abs(t[1]))))
