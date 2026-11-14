"""Tables from passes2.py's output."""
import json, sys
from collections import defaultdict
import numpy as np
rows = [r for f in sys.argv[1:] for r in json.load(open(f))]
W = len(rows)
print(f"{W} weeks, {sum(r['orders'] for r in rows) / W:.0f} orders a week, {sum(r['late'] for r in rows) / W:.1f} late")
# (a) early warning
def auc(y, x):
    y, x = np.asarray(y), np.asarray(x); pos, neg = x[y == 1], x[y == 0]
    return float("nan") if not len(pos) or not len(neg) else (sum((p > neg).sum() + 0.5 * (p == neg).sum() for p in pos)) / (len(pos) * len(neg))
print("\n== (a) what is known at the end of a day, against the late share of the orders won on later days")
for upto in (0, 1, 2):
    X = defaultdict(list); y_rest, y92, y_week = [], [], []
    for r in rows:
        dl = r["daily"]
        won = sum(dl[d].get("won", 0) for d in range(upto + 1)); warn = sum(dl[d].get("warn", 0) for d in range(upto + 1)); late = sum(dl[d].get("late", 0) for d in range(upto + 1))
        posted = sum(dl[d].get("posted", 0) for d in range(upto + 1)); fast = sum(dl[d].get("fast", 0) for d in range(upto + 1)); drops = sum(dl[d].get("drops", 0) for d in range(upto + 1))
        rest_n = sum(r["late_by_won_day"][d][0] for d in range(upto + 1, 5)); rest_l = sum(r["late_by_won_day"][d][1] for d in range(upto + 1, 5))
        if not rest_n or not won: continue
        X["drivers short of 1,000 (Mon 08:00)"].append(1000 - r["drivers"]); X["warnings per order won so far"].append(warn / won); X["late so far per order won"].append(late / won)
        X["slow bookings (share not within 30 min)"].append(1 - fast / max(posted, 1)); X["drops per order won"].append(drops / won); X["orders won per driver so far"].append(won / r["drivers"])
        y_rest.append(rest_l / rest_n); y92.append(int(r["late"] / r["orders"] > .08)); y_week.append(r["late"] / r["orders"])
    names = list(X); M = np.column_stack([X[n] for n in names]); yr = np.array(y_rest)
    print(f"-- by {['Monday', 'Tuesday', 'Wednesday'][upto]} 24:00 ({len(yr)} weeks; later orders are {yr.mean():.2%} late; weeks under 92%: {sum(y92)})")
    for i, n in enumerate(names):
        print(f"   {n:42s} corr with later late share {np.corrcoef(M[:, i], yr)[0, 1]:+.2f}   AUC for a week under 92% {auc(y92, M[:, i]):.2f}")
    Z = np.column_stack([np.ones(len(yr)), (M - M.mean(0)) / (M.std(0) + 1e-9)])
    half = np.arange(len(yr)) % 2 == 0
    for cols, nm in (([0, 1], "drivers alone"), (list(range(Z.shape[1])), "all")):
        b = np.linalg.lstsq(Z[half][:, cols], yr[half], rcond=None)[0]; pred = Z[~half][:, cols] @ b
        b2 = np.linalg.lstsq(Z[~half][:, cols], yr[~half], rcond=None)[0]; pred2 = Z[half][:, cols] @ b2
        p = np.r_[pred, pred2]; t = np.r_[yr[~half], yr[half]]; y9 = np.r_[np.array(y92)[~half], np.array(y92)[half]]
        top = p >= np.quantile(p, 0.8)
        print(f"   {nm}: left-out R2 {1 - ((t - p) ** 2).sum() / ((t - t.mean()) ** 2).sum():.3f}; AUC under 92% {auc(y9, p):.2f}; the worst-looking fifth of weeks: later orders {t[top].mean():.2%} late against {t[~top].mean():.2%}, holds {y9[top].sum()} of {y9.sum()} weeks under 92%")
# (b) snow
s = defaultdict(lambda: [0, 0])
for r in rows:
    for k, v in r["snow"].items(): s[k][0] += v[0]; s[k][1] += v[1]
print("\n== (b) snow forecast at the win, at the order's pickup or delivery before its deadline (flag, one-car dealer order): a week, late")
for k, v in sorted(s.items()): print(f"   {k}: {v[0] / W:.1f} a week, {v[1] / max(v[0], 1):.2%} late")
fw = [(r["forecasts"], r["late"] / r["orders"]) for r in rows]
print("   weeks by forecasts:", {n: (sum(1 for f, _ in fw if f == n), f"{np.mean([l for f, l in fw if f == n]):.2%}") for n in sorted({f for f, _ in fw})})
# (c) cost by supply
c = defaultdict(lambda: defaultdict(float)); q = defaultdict(lambda: [0, 0])
for r in rows:
    for k, v in r["cost"].items():
        for kk, vv in v.items(): c[k][kk] += vv
    for k, v in r["quotes"].items(): q[k][0] += v[0]; q[k][1] += v[1]
PB, DB, HB = ["under 10", "10-39", "40-99", "100+"], ["under 10", "10-99", "100+"], ["under 8 h", "8-24 h", "24 h+"]
print("\n== (c) one-car dealer orders by the drivers living within 30 km of the pickup (and of the delivery): orders a week, fees/typical, refunds/typical, all-in cost/typical, price/typical, late, margin an order; requests a week and share won")
for k in sorted(c):
    v = c[k]; key = eval(k)
    name = {"pd": lambda: f"pickup {PB[key[1]]}, delivery {DB[key[2]]}", "p": lambda: f"pickup {PB[key[1]]}", "d": lambda: f"delivery {DB[key[1]]}", "ph": lambda: f"pickup {PB[key[1]]}, {HB[key[2]]}"}[key[0]]()
    extra = f"   requests {q[k][0] / W:6.1f}, won {q[k][1] / max(q[k][0], 1):.1%}" if k in q else ""
    allin = (v["fees"] + v["refund"] + v["other"]) / v["typ"]
    print(f"   {name:34s} {v['n'] / W:6.1f}  fees {v['fees'] / v['typ']:.3f}  refunds {v['refund'] / v['typ']:.3f}  all-in {allin:.3f}  price {v['price'] / v['typ']:.3f}  late {v['late'] / v['n']:.2%}  margin {(v['price'] - v['fees'] - v['refund'] - v['other']) / v['n'] / 100:6.1f}{extra}")
# (d) trust
t = [x for r in rows for x in r["trust"]]
print(f"\n== (d) dealers a week {np.mean([r['dealers'] for r in rows]):.0f}; the three largest send {np.mean([r['top3_share'] for r in rows]):.1%} of requests")
print(f"   late deliveries counted {len(t) / W:.1f} a week; the dealer's count before it: mean {np.mean([x['count'] for x in t]):.1f}, 20 or more in {np.mean([x['count'] >= 20 for x in t]):.1%}; price lost on the dealer's later wins: {sum(x['loss'] for x in t) / W:.0f} euros a week, {np.mean([x['loss'] for x in t]):.1f} a late order")
for nm, g in (("three largest dealers", [x for x in t if x["top3"]]), ("other dealers", [x for x in t if not x["top3"]])):
    print(f"   {nm}: {len(g) / W:.1f} late a week, count before {np.mean([x['count'] for x in g]):.1f}, loss {np.mean([x['loss'] for x in g]):.1f} a late order (90th percentile {np.percentile([x['loss'] for x in g], 90):.0f})")
for lo, hi in ((0, 5), (5, 12), (12, 20), (20, 26)):
    g = [x for x in t if lo <= x["count"] < hi]
    if g: print(f"   count {lo}-{hi - 1}: {len(g) / W:.2f} a week, loss {np.mean([x['loss'] for x in g]):.1f} a late order")
for dday in range(1, 6):
    g = [x for x in t if x["day"] == dday]
    if g: print(f"   late delivery on day {dday}: {len(g) / W:.2f} a week, loss {np.mean([x['loss'] for x in g]):.1f}")
