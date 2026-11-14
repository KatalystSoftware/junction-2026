"""What is better knowledge of the day's price level worth? A fluid replay of the random-price weeks.

The "world" is a win curve fitted on all 50 weeks with a level per week and day and a level per week, day and pickup
place (so it holds the price war and the outage). Each desk quotes the multiple of the list price that maximises
(price - cost) x its own believed win chance; its margin is counted with the world's chance. Dealer counts are fluid
(expected wins, added when the car would arrive). No drivers, no backlog: use the differences only.

Desks: no live level; the live day shift (as the policy has); day + place shifts + pickup-today shift; the true day
level without the pickup-place-today part; the full truth.
"""
import sys, heapq
import numpy as np, scipy.sparse as sp
sys.path.insert(0, __import__("os").path.dirname(__file__))
from lib import *
from filt import replay
d = load(sys.argv[1]); y, x, n = d["y"], d["x"], d["n"]; zs = np.load(sys.argv[2]); zb, sb = zs[:, 0], zs[:, 1]; COST = float(sys.argv[3])
B, names = base_design(d); col = lambda v: sp.csr_matrix(v[:, None]); nw = len(d["seeds"])
L = onehot(d["sd"], list(range(5 * nw)))
keys = np.array([f"{a}|{b}" for a, b in zip(d["sd"], d["pickup"])]); R = onehot(keys, sorted(set(keys)))
SD_R = float(sys.argv[4]) if len(sys.argv) > 4 else 0.064
X = sp.hstack([col(x), B, L, R, col(np.ones(n))]).tocsr()
ridge = np.concatenate([[1e-2], np.full(B.shape[1], 1e-2), np.full(L.shape[1], 1e-2), np.full(R.shape[1], 1 / (13.0 * SD_R) ** 2), [1e-8]])
w = fit_logit_sparse(X, y, ridge); S = -w[0]; WT = w[1 + names.index("trust")]
r = np.asarray(R @ w[1 + B.shape[1] + L.shape[1]:-1]).ravel(); lin = np.asarray(X @ w).ravel()
z_true = lin + S * x - WT * d["trust"]
lev = w[1 + B.shape[1]:1 + B.shape[1] + L.shape[1]].reshape(nw, 5); war = lev.argmin(1)[d["seed"]] == d["day"]
out_q = r / S > 0.08  # quotes whose pickup place accepts 8% more than the day: the outage, mostly
print(f"world: slope {S:.2f}, trust {WT:.2f}, loss {logloss(sigmoid(lin), y):.4f}; pickup-place-today levels sd {np.std(r / S):.3f} in log price; quotes on the war day {war.mean():.3f}, in a region-day 8%+ above the day {out_q.mean():.3f}")
grid = np.arange(1.0, 2.41, 0.01); lg = np.log(grid); LATE = 0.04
rows = d["rows"]; first = np.array([q["first"] for q in rows]); dealer = d["dealer"]; lst, fee, at, day = d["list"] / 100, d["fee"] / 100, d["at"], d["day"]
BT = 13.9  # the trust weight of the desk's curve


def play(belief_z, belief_s, uses_obs_trust):
    """belief_z: the desk's log odds at the list price (at the trust of the data when uses_obs_trust, else at a count of 0)."""
    m = np.zeros(n); pr = np.zeros(n); mult = np.zeros(n); tq = np.zeros(n)
    for s in range(nw):
        ix = np.nonzero(d["seed"] == s)[0]; ix = ix[np.argsort(at[ix], kind="stable")]
        T = {}; heap = []
        for i in ix:
            while heap and heap[0][0] <= at[i]:
                _, k, wins = heapq.heappop(heap); t = T.get(k, 0.0); T[k] = min(25.0, t + wins * (1 - LATE)) - wins * LATE * t / 2
            k = dealer[i]; t = T.get(k, 0.0); lt = np.log1p(0.01 * t)
            zb_i = belief_z[i] - BT * d["trust"][i] + BT * lt if uses_obs_trust else belief_z[i] + WT * lt
            pb = 1 / (1 + np.exp(-(zb_i - belief_s[i] * lg))); c = COST * fee[i]
            j = int(np.argmax((grid * lst[i] - c) * pb)); p = 1 / (1 + np.exp(-(z_true[i] + WT * lt - S * lg[j])))
            m[i] = (grid[j] * lst[i] - c) * p; pr[i] = p; mult[i] = grid[j]; tq[i] = t
            due = day[i] * 1440 + 1200 if first[i] == "same_day" else (day[i] + (1 if "next_day" in first[i] else 2)) * 1440 + 840
            heapq.heappush(heap, (due, k, p))
    return m, pr, mult, tq


def week(v): return np.bincount(d["seed"], v, nw)


desks = [("no live level", zb, sb, True)]
for label, sds in [("day shift 0.16 (the policy)", {"day": 0.16}), ("day + pickup + delivery place shifts", {"day": 0.16, "from": 0.06, "to": 0.06}),
                   ("day + place + pickup-today shifts", {"day": 0.16, "from": 0.06, "to": 0.06, "from_day": 0.05}), ("day + pickup-today 0.10", {"day": 0.16, "from_day": 0.10})]:
    sh = replay(d, zb, sb, sds); desks.append((label, zb + sb * sh, sb, True))
desks += [("true day level, no pickup-today part", z_true - r, np.full(n, S), False), ("full truth", z_true, np.full(n, S), False)]
ref = None
print(f"cost {COST} x typical fee. EUR a week: margin | against the policy's day shift (weeks better) | orders | quote x list | margin on the war day | in the 8%+ region-days | elsewhere | quote x list in those region-days, win share there")
for label, bz, bs, obs in desks:
    m, pr, mult, tq = play(bz, bs, obs); wk = week(m)
    if label.startswith("day shift"): ref = wk
    diff = "" if ref is None else f"{(wk - ref).mean():+6.0f} ({((wk - ref) > 0).sum():2d}/50)"
    print(f"  {label:40s} {wk.mean():6.0f} | {diff:14s} | {week(pr).mean():4.0f} | {np.average(mult, weights=pr):.3f} | {week(m * war).mean():5.0f} | {week(m * (out_q & ~war)).mean():5.0f} | {week(m * (~out_q & ~war)).mean():5.0f} | {np.median(mult[out_q]):.2f}, {pr[out_q].mean():.2f}", flush=True)
