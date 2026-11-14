"""The shape of the price response, with one level per week and day so that only what holds in every world is left."""
import sys
import numpy as np, scipy.sparse as sp
sys.path.insert(0, __import__("os").path.dirname(__file__))
from lib import *
d = load(sys.argv[1]); y, x = d["y"], d["x"]; n = d["n"]
B, names = base_design(d)
L = onehot(d["sd"], list(range(250)))
col = lambda v: sp.csr_matrix(v[:, None])
def fit(extra, label, levels=True, show=None):
    X = sp.hstack([col(x)] + extra + [B] + ([L] if levels else [])).tocsr()
    w, b = fit_logit(X, y, C=100.0)
    p = sigmoid(X @ w + b)
    k = 1 + len(extra)
    print(f"{label:44s} in-sample loss {logloss(p, y):.5f}  coefs " + " ".join(f"{c:+.3f}" for c in w[:k]) + f"  trust {w[k]:+.2f}")
    return w, b, p, X
w0, b0, p0, X0 = fit([], "linear in log price")
slope = -w0[0]
# calibration by price band
print("by price band (x list): quotes, won, predicted")
m = np.exp(x)
for lo, hi in [(1.0, 1.2), (1.2, 1.3), (1.3, 1.4), (1.4, 1.5), (1.5, 1.6), (1.6, 1.8), (1.8, 2.0), (2.0, 2.2), (2.2, 2.5), (2.5, 9)]:
    s = (m >= lo) & (m < hi); print(f"  {lo:.1f}-{hi:.1f} n={s.sum():5d} won {y[s].mean():.4f} predicted {p0[s].mean():.4f}")
print("by predicted chance: quotes, won, predicted")
for lo, hi in [(0, .01), (.01, .03), (.03, .1), (.1, .2), (.2, .35), (.35, .5), (.5, .65), (.65, .8), (.8, .9), (.9, 1.01)]:
    s = (p0 >= lo) & (p0 < hi); print(f"  {lo:.2f}-{hi:.2f} n={s.sum():5d} won {y[s].mean():.4f} predicted {p0[s].mean():.4f}")
fit([col(x**2)], "+ square of log price")
fit([col(np.maximum(x - 0.35, 0))], "+ hinge at 1.42 x list")
fit([col(x * d["trust"])], "+ price x trust")
fit([col(x * d["feelist"])], "+ price x fee/list")
fit([col(x * np.log(d["list"] / 6000))], "+ price x log list price")
fit([col(x * (d["kinds"] == k)) for k in KINDS[1:]], "+ price x options")
fit([col(x * (d["day"] == k)) for k in range(1, 5)], "+ price x day of week")
fit([col(x * (d["hour"] >= 14))], "+ price x afternoon")
fit([col(x * d["note"])], "+ price x note")
fit([col(d["note"]), col(np.log1p(d["notified"])), col(np.log(d["list"] / 6000)), col(d["hour"] >= 14)], "+ note, notified, log list, afternoon (levels)")
# per dealer slope
D = onehot(d["dealer"], d["dealers"])
X = sp.hstack([D.multiply(x[:, None]), B, L, D[:, 1:]]).tocsr()
w, b = fit_logit(X, y, C=100.0)
nd = len(d["dealers"]); cnt = np.asarray(D.sum(0)).ravel()
print(f"slope per dealer ({nd} dealers): in-sample loss {logloss(sigmoid(X @ w + b), y):.5f}; slopes weighted mean {np.average(-w[:nd], weights=cnt):.2f} sd {np.sqrt(np.average((w[:nd] + np.average(-w[:nd], weights=cnt))**2, weights=cnt)):.2f} min {(-w[:nd]).min():.2f} max {(-w[:nd]).max():.2f}")
order = np.argsort(-cnt)[:12]
print("  largest dealers: " + ", ".join(f"{d['dealers'][i]} n={int(cnt[i])} slope {-w[i]:.1f}" for i in order))
# does the dealer slope hold across weeks? fit on even and odd weeks
ev = d["seed"] % 2 == 0
ws = []
for s in (ev, ~ev):
    w_, b_ = fit_logit(X[s], y[s], C=100.0); ws.append(-w_[:nd])
big = cnt >= 400
print(f"  dealer slopes, even weeks against odd weeks (dealers with 400+ quotes, {big.sum()}): correlation {np.corrcoef(ws[0][big], ws[1][big])[0, 1]:.2f}")
# link test: add the square of the fitted log odds; a weight far from 0 says the logistic link is the wrong shape
z0 = X0 @ w0 + b0
w, b = fit_logit(np.column_stack([z0, z0**2]), y, C=1e6)
print(f"link test: log odds {w[0]:+.3f}, square {w[1]:+.4f}, loss {logloss(sigmoid(w[0] * z0 + w[1] * z0**2 + b), y):.5f}")
