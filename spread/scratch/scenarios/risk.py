"""What one avoided late order costs when the desk gives up its riskiest orders first, and where that price meets L.

A late-chance model from what the desk knows at the quote, fitted on half the seeds and applied to the other half.
Orders are then given up from the riskiest down: each slice shows the late orders avoided and the margin forgone.

    python scratch/scenarios/risk.py <rows.json from extract.py>
"""
import json, math, sys
import numpy as np

DAY, HOUR = 1440, 60
W = json.load(open(sys.argv[1])); n = len(W)
rows = []
for wi, w in enumerate(W):
    Ow = sorted([o for o in w["orders"] if not o["cancelled"]], key=lambda o: o["won"])
    for o in Ow:
        t = o["won"]
        waiting = [p for p in Ow if p["won"] < t and (p["book"] is None or p["book"] > t) and (p["delivered"] is None or p["delivered"] > t)]
        hours = (o["last"] - t) / 60
        rows.append(dict(week=wi, late=o["late"], margin=(o["price"] - o["fees"] - o["refund"]) / 100, clean=(o["price"] - o["fees"]) / 100, refund=o["refund"] / 100, hours=hours, near=o["near"], ref=o["ref"] / 100,
                         fri=o["day"] == 4, note=o["note"], premium=o["premium"], snow=o["snow"], drivers=w["drivers"], same=o["option"] == "same_day",
                         w8=sum(1 for p in waiting if p["last"] - t <= 8 * 60), w24=sum(1 for p in waiting if 8 * 60 < p["last"] - t <= 24 * 60), wl=sum(1 for p in waiting if p["last"] - t > 24 * 60),
                         price=o["price"] / 100, thin=w["drivers"] < 700))
N = len(rows)
A = {k: np.array([r[k] for r in rows], float) for k in rows[0]}
X = np.column_stack([np.ones(N), A["hours"] < 6, (A["hours"] >= 6) & (A["hours"] < 8), (A["hours"] >= 8) & (A["hours"] < 12), A["hours"] >= 36, A["ref"] > 150, (A["ref"] > 90) & (A["ref"] <= 150),
                     A["fri"], A["note"], A["premium"], A["snow"], np.log1p(A["near"]), (800 - A["drivers"]) / 100, A["w8"], A["w24"], A["wl"]])
names = ["intercept", "under 6 h", "6-8 h", "8-12 h", "36 h+", "fee over 150", "fee 90-150", "Friday", "note", "premium", "snow forecast", "ln(1+drivers near)", "per 100 drivers under 800", "waiting due in 8 h", "waiting 8-24 h", "waiting later"]
y = A["late"]


def fit(X, y, ridge=1.0):
    w = np.zeros(X.shape[1])
    for _ in range(30):
        p = 1 / (1 + np.exp(-(X @ w))); R = np.full(X.shape[1], ridge); R[0] = 1e-6
        w += np.linalg.solve((X * (p * (1 - p))[:, None]).T @ X + np.diag(R), X.T @ (y - p) - R * w)
    return w


fold = A["week"] % 2
p = np.zeros(N)
for f in (0, 1):
    p[fold == f] = 1 / (1 + np.exp(-(X[fold == f] @ fit(X[fold != f], y[fold != f]))))
wall = fit(X, y)
print(f"{N} orders of {n} weeks, {y.mean():.4f} late. weights (log odds), all weeks:")
print("  " + "; ".join(f"{k} {v:+.2f}" for k, v in zip(names, wall)))
ll = lambda q: -np.mean(y * np.log(q) + (1 - y) * np.log(1 - q))
print(f"out of sample by seed: log loss {ll(p):.4f} against {ll(np.full(N, y.mean())):.4f} for one share; mean chance {p.mean():.4f}")
order = np.argsort(-p)
print("giving up the riskiest orders first (out of sample):")
print("  share given up | orders a week | their late share | late avoided a week | margin forgone a week | margin an order | price of one avoided late order (slice)")
prev = 0
for share in (0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50, 1.0):
    k = int(N * share); idx = order[prev:k]; allidx = order[:k]
    print(f"  {share:5.2f}  {k / n:7.1f}  {y[idx].mean():7.3f}  {y[allidx].sum() / n:7.2f}  {A['margin'][allidx].sum() / n:9.0f}  {A['margin'][idx].mean():7.1f}  {A['margin'][idx].sum() / max(1, y[idx].sum()):8.0f}  (chance from {p[idx].max():.3f} to {p[idx].min():.3f})")
    prev = k
# by the rule p x L > margin: which orders does a late cost L remove
print("the orders that do not earn their own lateness cost: expected clean margin under p x (L + refund), by L (out of sample; margin before refunds, 'clean')")
exp_clean = A["clean"]  # realised margin before refunds; its mean by risk band stands in for the expected one
for L in (0, 50, 100, 200, 400, 800):
    # an order is given up when its band's mean clean margin is under p x (refund + L): use the order's own chance and the mean clean margin of orders of like chance
    bands = np.digitize(p, np.quantile(p, np.linspace(0, 1, 21)[1:-1])); mean_clean = np.array([A["clean"][bands == b].mean() for b in range(20)])[bands]
    give = mean_clean < p * (45 + L)
    for name, s in [("all weeks", np.ones(N, bool)), ("under 700 drivers", A["thin"] == 1)]:
        weeks = len(set(A["week"][s])); g = give & s
        base = y[s].sum() / s.sum(); after = (y[s].sum() - y[g].sum()) / max(1, s.sum() - g.sum())
        print(f"  L {L:4d} {name:18s}: gives up {g.sum() / weeks:6.1f} orders a week, {y[g].sum() / weeks:5.2f} late among them, margin forgone {A['margin'][g].sum() / weeks:6.0f}; late share {base:.4f} -> {after:.4f}")
# the worst weeks: what would the same rule have done to their on-time share
print("the 10 weeks nearest the rule, with the L rule applied to the orders they won (no feedback on later orders):")
ont = np.array([w["score"]["onTimeShare"] for w in W]); worst = np.argsort(ont)[:10]
for L in (0, 200, 400, 800):
    bands = np.digitize(p, np.quantile(p, np.linspace(0, 1, 21)[1:-1])); mean_clean = np.array([A["clean"][bands == b].mean() for b in range(20)])[bands]
    give = mean_clean < p * (45 + L); out = []
    for wi in worst:
        s = A["week"] == wi; out.append(1 - (y[s & ~give].sum()) / max(1, (s & ~give).sum()))
    print(f"  L {L:4d}: on time {np.round(out, 3)}; lowest {min(out):.3f}; orders given up {np.mean([(give & (A['week'] == wi)).sum() for wi in worst]):.0f} a week, margin forgone {np.mean([A['margin'][give & (A['week'] == wi)].sum() for wi in worst]):.0f}")
