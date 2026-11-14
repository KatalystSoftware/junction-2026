"""Online learning of the level, replayed in time order on weeks the curve has not seen.

The curve's weights (what holds in every world) are fitted on four fifths of the weeks, with one level per week and day.
On each other week the desk starts from the mean level and learns, from each answer (15 minutes after its quote), a
shift of the log price for the week, the day, the pickup place, the delivery place and the dealer. The learner is a
Kalman filter on those shifts with a logistic observation (one Newton step per answer). Prints the log loss of each
set of shifts: lower is better.
"""
import sys, json, itertools
import numpy as np, scipy.sparse as sp
sys.path.insert(0, __import__("os").path.dirname(__file__))
from lib import *

def base_scores(d):
    """For every row, the log odds without price and level from a curve fitted on the other folds; and its slope."""
    B, _ = base_design(d); n = d["n"]; col = lambda v: sp.csr_matrix(v[:, None])
    L = onehot(d["sd"], list(range(5 * len(d["seeds"]))))
    z = np.zeros(n); slope = np.zeros(n)
    for k in range(5):
        tr = d["seed"] % 5 != k; te = ~tr
        keep = np.unique(d["sd"][tr])
        X = sp.hstack([col(d["x"]), B, L[:, keep]]).tocsr()
        ridge = np.concatenate([np.full(1 + B.shape[1], 1e-2), np.full(len(keep), 1e-2)])
        Xi = sp.hstack([X, col(np.ones(n))]).tocsr()
        w = fit_logit_sparse(Xi[tr], d["y"][tr], np.append(ridge, 1e-8))
        nb = 1 + B.shape[1]
        level = w[nb:nb + len(keep)]
        z[te] = (B[te] @ w[1:nb]) + w[-1] + level.mean()
        slope[te] = -w[0]
    return z, slope

def replay(d, z, slope, sds, q=0.0, war=None, lag=15):
    """The chance the filter gives each quote before its answer. sds: prior sd of each family of shifts (log price);
    q: the sd that each place and dealer shift may move each morning."""
    fams = [f for f in ("week", "day", "from", "to", "dealer", "dealer_day", "from_day") if sds.get(f)]
    towns, dealers = d["towns"], d["dealers"]
    size = {"week": 1, "day": 1, "from": len(towns), "to": len(towns), "dealer": len(dealers), "dealer_day": len(dealers), "from_day": len(towns)}
    off = {}; at = 0
    for f in fams: off[f] = at; at += size[f]
    ti = {t: i for i, t in enumerate(towns)}; di = {t: i for i, t in enumerate(dealers)}
    out = np.zeros(d["n"])
    for s in range(len(d["seeds"])):
        ix = np.nonzero(d["seed"] == s)[0]; ix = ix[np.argsort(d["at"][ix], kind="stable")]
        m = np.zeros(at); P = np.zeros((at, at))
        for f in fams: P[off[f]:off[f] + size[f], off[f]:off[f] + size[f]] = np.eye(size[f]) * sds[f] ** 2
        H = []
        for i in ix:
            h = []
            if "week" in off: h.append(off["week"])
            if "day" in off: h.append(off["day"])
            if "from" in off: h.append(off["from"] + ti[d["pickup"][i]])
            if "to" in off: h.append(off["to"] + ti[d["delivery"][i]])
            if "dealer" in off: h.append(off["dealer"] + di[d["dealer"][i]])
            if "dealer_day" in off: h.append(off["dealer_day"] + di[d["dealer"][i]])
            if "from_day" in off: h.append(off["from_day"] + ti[d["pickup"][i]])
            H.append(np.array(h, int))
        pend = 0; today = -1
        for k, i in enumerate(ix):
            if d["day"][i] != today:  # a new day: flush yesterday's answers, then reset what is new each day
                while pend < k:
                    j = ix[pend]; h = H[pend]; pend += 1
                    sl = slope[j]; p = 1 / (1 + np.exp(-(z[j] - sl * d["x"][j] + sl * m[h].sum()))); Ph = P[:, h].sum(1); v = sl * sl * p * (1 - p)
                    m += Ph * sl * (d["y"][j] - p) / (1 + v * Ph[h].sum()); P -= np.outer(Ph, Ph) * v / (1 + v * Ph[h].sum())
                today = d["day"][i]
                for f in ("day", "dealer_day", "from_day"):
                    if f in off:
                        a, b = off[f], off[f] + size[f]; m[a:b] = 0; P[a:b, :] = 0; P[:, a:b] = 0; P[a:b, a:b] = np.eye(size[f]) * sds[f] ** 2
                if q:
                    for f in ("from", "to", "dealer"):
                        if f in off:
                            a, b = off[f], off[f] + size[f]; P[a:b, a:b] += np.eye(size[f]) * q ** 2
            while pend < k and d["at"][ix[pend]] + lag <= d["at"][i]:
                j = ix[pend]; h = H[pend]; pend += 1
                sl = slope[j]; p = 1 / (1 + np.exp(-(z[j] - sl * d["x"][j] + sl * m[h].sum()))); Ph = P[:, h].sum(1); v = sl * sl * p * (1 - p)
                m += Ph * sl * (d["y"][j] - p) / (1 + v * Ph[h].sum()); P -= np.outer(Ph, Ph) * v / (1 + v * Ph[h].sum())
            h = H[k]; out[i] = m[h].sum()
    return out  # the shift of the log price for each quote

if __name__ == "__main__":
    d = load(sys.argv[1]); y = d["y"]
    z, slope = base_scores(d)
    np.save(sys.argv[2], np.column_stack([z, slope]))
    print("slope by fold:", np.unique(np.round(slope, 2)))
    def score(label, sds, mult=1.0, **kw):
        sh = replay(d, z, slope * mult, sds, **kw)
        p = sigmoid(z - slope * mult * (d["x"] - sh))
        byday = " ".join(f"{logloss(p[d['day'] == k], y[d['day'] == k]):.4f}" for k in range(5))
        print(f"{label:60s} {logloss(p, y):.4f} | by weekday {byday}", flush=True)
        return sh
    score("no correction", {})
    score("day 0.16", {"day": 0.16})
    score("week 0.07 + day 0.13", {"week": 0.07, "day": 0.13})
    score("week + day + from 0.06 + to 0.06", {"week": 0.07, "day": 0.13, "from": 0.06, "to": 0.06})
    score("week + day + dealer 0.055", {"week": 0.07, "day": 0.13, "dealer": 0.055})
    score("week + day + from + to + dealer", {"week": 0.07, "day": 0.13, "from": 0.06, "to": 0.06, "dealer": 0.055})
    for mult in (1.1, 1.2, 1.3):
        score(f"week + day + from + to + dealer, slope x {mult}", {"week": 0.07, "day": 0.13, "from": 0.06, "to": 0.06, "dealer": 0.055}, mult=mult)
