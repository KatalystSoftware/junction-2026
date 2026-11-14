"""A fluid replay of dealer trust on the random-price weeks: does paying for trust early (a "sprint") earn its cost?

The win curve is fitted on all weeks with one level per week and day (so the level is known, an oracle). Each week is
replayed in time order in expected values: every request is quoted at the multiple of the list price that maximises
(price - cost + bonus) x win chance, the expected win is added to the dealer's count when the car would arrive
(same_day: 20:00 that day, next_day: 14:00 the next day, else two days on), and a late car halves the count.
bonus = v x (requests the dealer still sends this week) while the count is under 25: v is the value of one trust point
per remaining request. Prints the mean week for each v, cost and scope.
"""
import sys, heapq
import numpy as np, scipy.sparse as sp
sys.path.insert(0, __import__("os").path.dirname(__file__))
from lib import *
d = load(sys.argv[1]); y, x, n = d["y"], d["x"], d["n"]
B, names = base_design(d); L = onehot(d["sd"], list(range(5 * len(d["seeds"])))); col = lambda v: sp.csr_matrix(v[:, None])
X = sp.hstack([col(x), B, L]).tocsr(); w, b = fit_logit(X, y, C=100.0)
S, WT = -w[0], w[1 + names.index("trust")]
z0 = np.asarray(X @ w).ravel() + b + S * x - WT * d["trust"]   # log odds at the list price and a count of 0
print(f"curve: slope {S:.2f}, trust weight {WT:.2f}; quotes {n}, weeks {len(d['seeds'])}")
grid = np.arange(1.0, 2.41, 0.01); lg = np.log(grid); LATE = 0.037
rows = d["rows"]; first = np.array([r["first"] for r in rows]); dealer = d["dealer"]; lst, fee, at, day = d["list"] / 100, d["fee"] / 100, d["at"], d["day"]
share = {k: (dealer == k).mean() for k in d["dealers"]}; top = sorted(share, key=share.get, reverse=True)
print("largest dealers, share of requests:", " ".join(f"{k} {share[k]:.2f}" for k in top[:5]))
lowest = {}  # the war day of each week: the day with the lowest level
lev = w[1 + B.shape[1]:]
for s in range(len(d["seeds"])): lowest[s] = int(np.argmin(lev[s * 5:s * 5 + 5]))


def play(v, cost, slope=None, scope=None, days=(0, 1, 2, 3, 4), guard=False, stop_at=25, believe=None):
    """Mean week: margin, orders, mean count at the quote, D-largest count on Tuesday 08:00. `believe`: the slope the desk prices with."""
    out = []
    for s in range(len(d["seeds"])):
        ix = np.nonzero(d["seed"] == s)[0]; ix = ix[np.argsort(at[ix], kind="stable")]
        T = {}; heap = []; left = {}
        for i in ix: left[dealer[i]] = left.get(dealer[i], 0) + 1
        margin = orders = tsum = 0.0; tue = None
        for i in ix:
            while heap and heap[0][0] <= at[i]:
                _, k, wins = heapq.heappop(heap); t = T.get(k, 0.0)
                T[k] = min(25.0, t + wins * (1 - LATE)) - wins * LATE * t / 2
            if tue is None and at[i] >= 1440 + 480: tue = T.get(top[0], 0.0)
            k = dealer[i]; left[k] -= 1; t = T.get(k, 0.0)
            zt = z0[i] + WT * np.log1p(0.01 * t); p = 1 / (1 + np.exp(-(zt - S * lg)))
            pb = p if believe is None else 1 / (1 + np.exp(-(zt - S * np.log(1.5) + believe * np.log(1.5) - believe * lg)))  # same chance at 1.5 x list, flatter away from it
            c = cost * fee[i]
            bonus = v * left[k] if (t < stop_at and (scope is None or k in scope) and day[i] in days and not (guard and day[i] == lowest[s])) else 0.0
            j = int(np.argmax((grid * lst[i] - c + bonus) * pb))
            margin += (grid[j] * lst[i] - c) * p[j]; orders += p[j]; tsum += t
            due = day[i] * 1440 + 1200 if first[i] == "same_day" else (day[i] + (1 if "next_day" in first[i] else 2)) * 1440 + 840
            heapq.heappush(heap, (due, k, p[j]))
        out.append((margin, orders, tsum / len(ix), tue or 0.0))
    return np.array(out)


for cost in (1.4, 1.2):
    for believe in (None, 9.16):
        base = play(0.0, cost, believe=believe)
        print(f"\ncost {cost} x typical fee, desk prices with slope {'true' if believe is None else believe}: no bonus: margin EUR {base[:, 0].mean():.0f}, orders {base[:, 1].mean():.0f}, mean count at the quote {base[:, 2].mean():.1f}, largest dealer's count on Tuesday 08:00 {base[:, 3].mean():.1f}")
        for label, kw in [("all dealers, all week", {}), ("3 largest, all week", dict(scope=set(top[:3]))), ("3 largest, Monday and Tuesday", dict(scope=set(top[:3]), days=(0, 1))),
                          ("3 largest, Mon-Tue, not on the war day", dict(scope=set(top[:3]), days=(0, 1), guard=True)), ("3 largest, Mon-Tue, no war day, until a count of 15", dict(scope=set(top[:3]), days=(0, 1), guard=True, stop_at=15))]:
            line = f"  {label:52s}"
            for v in (0.05, 0.1, 0.2, 0.3, 0.6):
                r = play(v, cost, believe=believe, **kw); diff = r[:, 0] - base[:, 0]
                line += f" v={v}: {diff.mean():+5.0f} ({(diff > 0).sum():2d}/50, orders {r[:, 1].mean() - base[:, 1].mean():+.0f}, Tue {r[:, 3].mean():.0f}) |"
            print(line, flush=True)
