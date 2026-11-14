"""Shared helpers for the general-structure analysis of the random-price weeks (rows of scratch/curve_rows.py)."""
import json, math
import numpy as np
import scipy.sparse as sp

KINDS = ["next_day", "next_day+within_3_days", "same_day", "same_day+next_day", "same_day+next_day+within_3_days"]


def load(path):
    rows = [r for r in json.load(open(path)) if r.get("variant", "explore") == "explore"]
    rows.sort(key=lambda r: (r["seed"], r["at"], r["id"]))
    seeds = sorted({r["seed"] for r in rows})
    a = lambda k, t=float: np.array([r[k] for r in rows], dtype=t)
    d = dict(rows=rows, seeds=seeds, n=len(rows), y=a("won"), x=np.log(a("price") / a("list")), trust=np.log1p(0.01 * a("trust")), ntrust=a("trust"),
             feelist=np.log(a("fee") / a("list")), fee=a("fee"), list=a("list"), price=a("price"), day=a("day", int), at=a("at", int), hour=a("hour"),
             unbooked=a("unbooked"), notified=a("notified"), drivers=a("drivers"), note=a("note"),
             seed=np.array([seeds.index(r["seed"]) for r in rows]), kinds=np.array(["+".join(r["kinds"]) for r in rows]),
             pickup=np.array([r["pickup"] for r in rows]), delivery=np.array([r["delivery"] for r in rows]), dealer=np.array([r["dealer"] for r in rows]))
    d["sd"] = d["seed"] * 5 + d["day"]  # one group per week and day
    d["towns"] = sorted(set(d["pickup"]) | set(d["delivery"]))
    d["dealers"] = sorted(set(d["dealer"]))
    return d


def onehot(values, levels):
    index = {v: i for i, v in enumerate(levels)}
    col = np.array([index.get(v, -1) for v in values]); ok = col >= 0
    return sp.csr_matrix((np.ones(ok.sum()), (np.nonzero(ok)[0], col[ok])), shape=(len(values), len(levels)))


def base_design(d, places=True):
    """The columns that hold in every world: trust, options, fee over list, pickup and delivery place. No price, no level."""
    cols = [sp.csr_matrix(d["trust"][:, None]), sp.csr_matrix(d["feelist"][:, None]), onehot(d["kinds"], KINDS[1:])]
    names = ["trust", "feelist"] + ["kinds=" + k for k in KINDS[1:]]
    if places:
        cols += [onehot(d["pickup"], d["towns"][1:]), onehot(d["delivery"], d["towns"][1:])]
        names += ["from=" + t for t in d["towns"][1:]] + ["to=" + t for t in d["towns"][1:]]
    return sp.hstack(cols).tocsr(), names


def fit_logit(X, y, C=10.0, it=40):
    """Logistic regression by Newton steps with a ridge of 1/C on the weights (not on the intercept). Returns weights, intercept."""
    X = np.asarray(X.todense()) if sp.issparse(X) else np.asarray(X)
    A = np.hstack([X, np.ones((len(y), 1))]); w = np.zeros(A.shape[1])
    ridge = np.full(A.shape[1], 1.0 / C); ridge[-1] = 1e-8
    for _ in range(it):
        p = 1 / (1 + np.exp(-(A @ w))); W = p * (1 - p)
        step = np.linalg.solve((A * W[:, None]).T @ A + np.diag(ridge), A.T @ (y - p) - ridge * w)
        w += np.clip(step, -5, 5)
        if np.abs(step).max() < 1e-7:
            break
    return w[:-1], float(w[-1])


def sigmoid(z):
    return 1 / (1 + np.exp(-z))


def logloss(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def group_shift(z, y, g, ng, slope, sd=1e9, it=30):
    """For each group, the shift d of the log price that fits its answers best: logit = z + slope * d, normal prior sd."""
    d = np.zeros(ng)
    for _ in range(it):
        p = sigmoid(z + slope * d[g])
        grad = slope * np.bincount(g, y - p, ng) - d / sd**2
        hess = slope**2 * np.bincount(g, p * (1 - p), ng) + 1 / sd**2
        d += np.clip(grad / hess, -0.5, 0.5)
    return d


def fit_logit_sparse(X, y, ridge, it=40):
    """Logistic regression by Newton steps for a wide sparse X. `ridge` is one penalty per column (1 / prior variance)."""
    import scipy.sparse.linalg as spl
    X = X.tocsr(); w = np.zeros(X.shape[1]); R = sp.diags(ridge)
    for _ in range(it):
        p = 1 / (1 + np.exp(-(X @ w))); W = p * (1 - p)
        step = spl.spsolve((X.T @ X.multiply(W[:, None]) + R).tocsc(), X.T @ (y - p) - ridge * w)
        w += np.clip(step, -5, 5)
        if np.abs(step).max() < 1e-6:
            break
    return w
