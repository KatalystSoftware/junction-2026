"""Scratch: can a tree on saved weeks predict winning and the margin of a quote on weeks it has not seen, and what would its quote-or-not choice have kept?"""
import collections, json, os
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor, export_text
rows = json.load(open(os.path.dirname(os.path.abspath(__file__)) + "/tree_rows.json"))
A = ["qlist", "qref"]
B = A + ["reflist", "ref", "same_day", "options", "day", "hour", "slack", "notified", "legs", "private", "note", "carsPerDriver", "dealerShare"]
H = ["dayN", "dayWin", "dealerDayN", "dealerDayWin", "dealerWeekN", "dealerWeekWin", "dealerPrevDayWin", "prevDayWin", "last20Win"]
C = B + H
def X(cols): return np.array([[(-1.0 if r[c] is None else float(r[c])) for c in cols] for r in rows])
seeds = np.array([r["seed"] for r in rows]); variant = np.array([r["variant"] for r in rows])
won = np.array([r["won"] for r in rows], int); margin = np.array([r["margin"] for r in rows])
folds = list(GroupKFold(5).split(rows, groups=seeds))
print(f"{len(rows)} quotes, {len(set(seeds))} seeds, {len(set(zip(seeds, variant)))} weeks, win rate {won.mean():.3f}")
print(f"constant: log loss {log_loss(won, np.full(len(won), won.mean())):.4f}")
def cv(make, x, y, proba=True):
    p = np.zeros(len(y))
    for tr, te in folds:
        m = make().fit(x[tr], y[tr]); p[te] = m.predict_proba(x[te])[:, 1] if proba else m.predict(x[te])
    return p
tree = lambda: DecisionTreeClassifier(max_depth=5, min_samples_leaf=300)
gb = lambda: HistGradientBoostingClassifier(max_depth=4, max_iter=200, learning_rate=0.06)
print("\nwin model, weeks of held-out seeds:        one tree (depth 5)      boosted trees")
P = {}
for name, cols in (("price only", A), ("+ request and week", B), ("+ history in the week", C), ("history only", H)):
    x = X(cols); pt = cv(tree, x, won); pg = cv(gb, x, won); P[name] = pg
    print(f"  {name:24s} AUC {roc_auc_score(won, pt):.3f} loss {log_loss(won, pt):.4f}    AUC {roc_auc_score(won, pg):.3f} loss {log_loss(won, pg):.4f}")
m = DecisionTreeClassifier(max_depth=3, min_samples_leaf=1000).fit(X(C), won)
print("\na depth-3 tree on everything:\n" + export_text(m, feature_names=C, decimals=2))
g = HistGradientBoostingClassifier(max_depth=4, max_iter=200, learning_rate=0.06).fit(X(C), won)
from sklearn.inspection import permutation_importance
idx = np.random.default_rng(0).choice(len(rows), 15000, replace=False)
imp = permutation_importance(g, X(C)[idx], won[idx], n_repeats=3, random_state=0, scoring="roc_auc")
print("AUC lost when a feature is shuffled (in sample):", "  ".join(f"{c} {v:.3f}" for v, c in sorted(zip(imp.importances_mean, C), reverse=True)[:8]))
# quote or not: predicted margin of a quote, on held-out seeds
D = C + ["backlog"]
x = X(D)
for mname, make in (("one tree (depth 5)", lambda: DecisionTreeRegressor(max_depth=5, min_samples_leaf=300)), ("boosted trees", lambda: HistGradientBoostingRegressor(max_depth=4, max_iter=200, learning_rate=0.06))):
    pred = cv(make, x, margin, proba=False)
    print(f"\nquote-or-not by {mname}: keep a quote when its predicted margin is over the cut. Held-out seeds, euros a week from what was actually earned.")
    for v in ("gate-10", "floor-1.7-all", "with-same-day"):
        sel = variant == v; weeks = len(set(seeds[sel])); won_v = sel & (won == 1)
        late = np.array([bool(r["late"]) for r in rows])
        base = f"  {v:14s} {weeks} weeks: all quotes {margin[sel].sum()/weeks:6.0f}, {won_v.sum()/weeks:.0f} cars, {100*late[won_v].mean():.1f}% late"
        for cut in (0, 2):
            keep = sel & (pred > cut); kw = keep & (won == 1); drop = sel & ~(pred > cut); dw = drop & (won == 1)
            base += f" | cut {cut}: keeps {100*keep.sum()/sel.sum():.0f}% of quotes, {margin[keep].sum()/weeks:6.0f}, {kw.sum()/weeks:.0f} cars, {100*late[kw].mean():.1f}% late; dropped cars made {margin[drop].sum()/weeks:6.0f}, {100*late[dw].mean() if dw.sum() else 0:.1f}% late"
        print(base)
# the same request at three floors: a paired price response
by = collections.defaultdict(dict)
for r in rows:
    if r["variant"] in ("floor-1.5", "floor-1.7", "floor-1.9"): by[(r["seed"], r["id"])][r["variant"]] = r
trip = [v for v in by.values() if len(v) == 3 and all(abs(v[f"floor-{k}"]["qref"] - float(k)) < 0.01 for k in ("1.5", "1.7", "1.9"))]
print(f"\nthe same {len(trip)} requests quoted at 1.5, 1.7 and 1.9 x typical fee (the floor set the price in all three), 10 tuning seeds")
def resp(title, key):
    print(f"  {title:22s}    n    win% at 1.5 / 1.7 / 1.9      margin per quote at 1.5 / 1.7 / 1.9 (euros, as earned)")
    g = collections.defaultdict(list)
    for t in trip: g[key(t["floor-1.7"])].append(t)
    for k in sorted(g, key=str):
        b = g[k]
        print(f"  {str(k):22s} {len(b):5d}   " + " / ".join(f"{100*np.mean([t[f'floor-{f}']['won'] for t in b]):4.1f}" for f in ("1.5", "1.7", "1.9")) + "          " + " / ".join(f"{np.mean([t[f'floor-{f}']['margin'] for t in b]):5.2f}" for f in ("1.5", "1.7", "1.9")))
resp("all", lambda r: "all")
resp("dealer", lambda r: "two largest" if r["situation"] == "large_dealer" else "other")
resp("day", lambda r: r["day"])
resp("cars per driver", lambda r: "tight, 1.3 and over" if r["carsPerDriver"] >= 1.3 else "loose, under 1.3")
resp("won at dealer so far", lambda r: "no quote yet" if r["dealerWeekWin"] is None else "under 15%" if r["dealerWeekWin"] < .15 else "15-35%" if r["dealerWeekWin"] < .35 else "35% and over")
