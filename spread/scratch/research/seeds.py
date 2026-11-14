"""How many random-price weeks pin the slope of the win curve: per-week slopes, and the pooled slope on random subsets of k weeks."""
import sys
import numpy as np, scipy.sparse as sp
sys.path.insert(0, __import__("os").path.dirname(__file__))
from lib import *
d = load(sys.argv[1]); y, x, seed = d["y"], d["x"], d["seed"]; ns = len(d["seeds"])
col = lambda v: sp.csr_matrix(v[:, None])
K = sp.hstack([col(x), col(d["trust"]), col(d["feelist"]), onehot(d["kinds"], KINDS[1:])]).tocsr()


def slope_of(rows):
    levels = sorted(set(d["sd"][rows]))
    X = sp.hstack([K[rows], onehot(d["sd"][rows], levels[1:])]).tocsr()
    w, b = fit_logit(X, y[rows], C=100.0)
    # standard error of the slope from the information matrix
    A = np.hstack([np.asarray(X.todense()), np.ones((len(rows), 1))]); p = sigmoid(A @ np.append(w, b))
    cov = np.linalg.inv((A * (p * (1 - p))[:, None]).T @ A + np.eye(A.shape[1]) * 0.01)
    return -w[0], cov[0, 0] ** 0.5, w[1]


per = np.array([slope_of(np.nonzero(seed == s)[0]) for s in range(ns)])
sl, se = per[:, 0], per[:, 1]
print(f"{ns} weeks, {d['n']} quotes, {d['n'] / ns:.0f} a week")
print(f"per-week slope: mean {sl.mean():.2f} sd {sl.std(ddof=1):.2f} min {sl.min():.2f} max {sl.max():.2f}; mean standard error {se.mean():.2f}")
real = max(sl.var(ddof=1) - (se**2).mean(), 0) ** 0.5
print(f"real difference between weeks (sd after removing sampling error): {real:.2f}")
print(f"per-week trust weight: mean {per[:, 2].mean():.2f} sd {per[:, 2].std(ddof=1):.2f}")
rng = np.random.default_rng(0)


def best_markup(s, win=0.4):
    # price over cost that maximises (p - c) * chance, when the chance at that price is `win`: p / (p - c) = s * (1 - win)
    return 1 / (1 - 1 / (s * (1 - win)))


print("pooled slope on random subsets of k weeks (60 draws): 5%, 50%, 95% | best price over cost at a 40% win chance, 5% and 95%")
for k in [2, 3, 5, 10, 20, 30, 40]:
    out = []
    for _ in range(60):
        pick = rng.choice(ns, k, replace=False)
        out.append(slope_of(np.nonzero(np.isin(seed, pick))[0])[0])
    q = np.quantile(out, [.05, .5, .95])
    print(f"  k={k:2d}: {q[0]:.2f} {q[1]:.2f} {q[2]:.2f} | {best_markup(q[2]):.4f} {best_markup(q[0]):.4f}")
full = slope_of(np.arange(d["n"]))
print(f"all weeks: slope {full[0]:.2f} +- {full[1]:.2f}, best price over cost at 40% win {best_markup(full[0]):.4f}; at slope 9.16 {best_markup(9.16):.4f}")
