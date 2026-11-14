"""What is new in each world: how far the level of the curve moves by week, day, place, lane and dealer, in log price.
Each line adds one family of levels (one per group, normal prior) to the fit and reports the slope and the spread of
the levels it found, corrected for the noise of estimating them."""
import sys, json
import numpy as np, scipy.sparse as sp
sys.path.insert(0, __import__("os").path.dirname(__file__))
from lib import *
d = load(sys.argv[1]); y, x, n = d["y"], d["x"], d["n"]
B, names = base_design(d)
col = lambda v: sp.csr_matrix(v[:, None])
def groups(keys):
    lev = sorted(set(keys)); return onehot(keys, lev), lev
seedname = np.array(d["seeds"])[d["seed"]]
K = {"week": seedname, "week-day": np.char.add(seedname, np.char.add("|", d["day"].astype(str))),
     "week-from": np.char.add(seedname, np.char.add("|f", d["pickup"])), "week-to": np.char.add(seedname, np.char.add("|t", d["delivery"])),
     "week-dealer": np.char.add(seedname, np.char.add("|", d["dealer"]))}
K["week-lane"] = np.char.add(K["week-from"], np.char.add(">", d["delivery"]))
K["week-day-dealer"] = np.char.add(K["week-day"], np.char.add("|", d["dealer"]))
K["week-day-from"] = np.char.add(K["week-day"], np.char.add("|f", d["pickup"]))
K["week-day-to"] = np.char.add(K["week-day"], np.char.add("|t", d["delivery"]))
def run(fams, prior_sd=0.15, slope_guess=13.0):
    mats = [col(x), B, col(np.ones(n))]; ridge = [np.full(1 + B.shape[1], 1e-3), [1e-8]]; spans = {}
    at = 2 + B.shape[1]
    for f in fams:
        G, lev = groups(K[f]); mats.append(G); spans[f] = (at, at + len(lev)); at += len(lev)
        ridge.append(np.full(len(lev), 1.0 / (prior_sd * slope_guess) ** 2))
    X = sp.hstack(mats).tocsr(); w = fit_logit_sparse(X, y, np.concatenate([np.ravel(r) for r in ridge]))
    p = sigmoid(X @ w); slope = -w[0]
    out = f"{' + '.join(fams) or 'no levels':58s} slope {slope:5.2f} trust/slope {w[1] / slope:.2f} loss {logloss(p, y):.4f} | sd of levels (log price):"
    for f, (a, b) in spans.items():
        out += f" {f} {np.std(w[a:b]) / slope:.3f}"
    print(out, flush=True)
    return w, X, spans, slope
run([])
run(["week"])
w1, X1, spans1, slope1 = run(["week-day"])
run(["week-day", "week-from", "week-to"])
run(["week-day", "week-dealer"])
run(["week-day", "week-from", "week-to", "week-dealer"])
run(["week-day", "week-lane"])
run(["week-day", "week-from", "week-to", "week-dealer", "week-lane"])
run(["week-day", "week-day-dealer"])
run(["week-day", "week-day-from"])
run(["week-day", "week-day-to"])
wf, Xf, spansf, slopef = run(["week-day", "week-from", "week-to", "week-dealer", "week-day-dealer", "week-day-from"])
# The days of a week, lowest first: the price war should stand out as one day about ln 0.8 = -0.22 under the others.
a, b = spans1["week-day"]; lev = (w1[a:b] / slope1).reshape(50, 5)
srt = np.sort(lev - np.median(lev, axis=1, keepdims=True), axis=1)
print("day levels against the week's median day, lowest first: mean " + " ".join(f"{v:+.3f}" for v in srt.mean(0)) + " | sd " + " ".join(f"{v:.3f}" for v in srt.std(0)))
print("which weekday is the lowest:", np.bincount(lev.argmin(1), minlength=5), " week medians: sd %.3f min %+.3f max %+.3f" % (np.median(lev, 1).std(), (np.median(lev, 1) - np.median(lev)).min(), (np.median(lev, 1) - np.median(lev)).max()))
print("mean level by weekday (Mon..Fri):", " ".join(f"{v:+.3f}" for v in (lev - lev.mean()).mean(0)))
others = np.array([np.delete(lev[i], lev[i].argmin()) for i in range(50)])
print(f"days without the lowest: sd within a week {others.std(1, ddof=1).mean():.3f}; day-to-day correlation of neighbours {np.corrcoef(np.concatenate([o[:-1] - o.mean() for o in others]), np.concatenate([o[1:] - o.mean() for o in others]))[0, 1]:+.2f}")
drv = np.array([d["drivers"][d["seed"] == s][0] for s in range(50)])
print(f"week level against the driver count of the week: correlation {np.corrcoef(np.median(lev, 1), drv)[0, 1]:+.2f}")
json.dump({"seeds": d["seeds"], "levels": lev.tolist()}, open(sys.argv[2], "w"))
