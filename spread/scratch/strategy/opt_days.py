"""The opt rule against slow-step-gate-25 and the reference on the seeds all played: by the day an order was won, and by
the won cars without a driver at its quote; and a late-chance fit with terms for those cars. usage: opt_days.py <rows.pkl>"""
import pickle, sys, collections, math, hashlib
import numpy as np
rows = pickle.load(open(sys.argv[1], "rb"))
FRIDAY = [-4.601, 1.803, 1.239, 0.813, 0.392, 0.784, 0.681, 1.539, 0.454, -0.327, 0.437, 0.3, 0.22, 0.715]
def chance(x, w=FRIDAY): return 1 / (1 + math.exp(-sum(a * b for a, b in zip(w, x))))
V = ["steep-notes-offers-8", "slow-step-gate-25", "opt-mu-0.3-lambda-100", "opt-mu-0.2"]
seeds = {v: {r["seed"] for r in rows if r["variant"] == v} for v in V}
common = set.intersection(*seeds.values())
print("seeds all four played:", len(common))
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
print("\nBy the day the order was won (a week, on those seeds): orders, late share, account lines of those orders in euros")
for v in V:
    rs = [r for r in rows if r["variant"] == v and r["seed"] in common]
    n = len(common)
    line = []
    for d in range(5):
        x = [r for r in rs if r["day"] == d]
        line.append("%s %5.1f %4.1f%% %6.0f" % (DAYS[d], len(x) / n, 100 * np.mean([r["late"] for r in x]), sum(r["cents"] for r in x) / 100 / n))
    print("%-24s" % v, " | ".join(line), "| week %6.0f, weeks under 90%%: %d" % (sum(r["cents"] for r in rs) / 100 / n, len({r["seed"] for r in rs if r["onTime"] < 0.9})))
print("\nBy the won cars without a driver at the quote: orders a week, late share, the friday model's chance")
B = [(0, 5), (6, 10), (11, 15), (16, 20), (21, 99)]
for v in V:
    rs = [r for r in rows if r["variant"] == v and r["seed"] in common and r["kind"] == ""]
    n = len(common); line = []
    for lo, hi in B:
        x = [r for r in rs if lo <= r["w24"] + r["wl"] <= hi]
        line.append("%d-%d: %5.1f %4.1f%% (%4.1f%%)" % (lo, hi, len(x) / n, 100 * np.mean([r["late"] for r in x]) if x else 0, 100 * np.mean([chance(r["x"]) for r in x]) if x else 0))
    print("%-24s" % v, " | ".join(line))
# Thursday and Friday wins of the opt rule by waiting cars
print("\nopt-mu-0.3-lambda-100, late share by day won and waiting cars (dealer one-car orders, all its weeks)")
rs = [r for r in rows if r["variant"] == "opt-mu-0.3-lambda-100" and r["kind"] == ""]
for name, days in (("Mon-Wed", (0, 1, 2)), ("Thu-Fri", (3, 4))):
    print(" ", name, " | ".join("%d-%d: n %d late %.1f%%" % (lo, hi, len(x), 100 * np.mean([r["late"] for r in x]) if x else 0) for lo, hi in B for x in [[r for r in rs if r["day"] in days and lo <= r["w24"] + r["wl"] <= hi]]))
# The fit: slow.py's friday terms, plus the waiting cars due within 24 hours and later, and the two times the order's own short time
def half(seed): return int(hashlib.sha256(seed.encode()).hexdigest(), 16) % 2
def feats(r):
    short = r["x"][1] + r["x"][2] + r["x"][3]
    return r["x"] + [min(r["w24"], 30) / 10, min(r["wl"], 30) / 10, short * min(r["w24"], 30) / 10]
allv = [r for r in rows if r["kind"] == ""]
train = [r for r in allv if half(r["seed"]) == 0]; test = [r for r in allv if half(r["seed"]) == 1]
X = np.array([feats(r) for r in train]); y = np.array([r["late"] for r in train], float)
w = np.zeros(X.shape[1])
for _ in range(40):
    p = 1 / (1 + np.exp(-X @ w)); g = X.T @ (y - p); H = (X * (p * (1 - p))[:, None]).T @ X + 1e-6 * np.eye(len(w))
    step = np.linalg.solve(H, g); w += step
    if np.abs(step).max() < 1e-7: break
print("\nfit on %d orders of %d seeds (all four variants and slow-step-gate-25-kinds), tested on %d orders of other seeds" % (len(train), len({r['seed'] for r in train}), len(test)))
print(" weights:", [round(float(a), 3) for a in w])
print(" last three: per 10 waiting cars due within 24 h %.3f, per 10 due later %.3f, per 10 due within 24 h when this order has under 12 h %.3f" % tuple(w[-3:]))
def p_new(r): return float(1 / (1 + np.exp(-np.array(feats(r)) @ w)))
print(" on the other seeds: late share, friday model, new fit")
for v in V + ["slow-step-gate-25-kinds"]:
    for lo, hi in ((0, 15), (16, 99)):
        x = [r for r in test if r["variant"] == v and lo <= r["w24"] + r["wl"] <= hi]
        if x: print("  %-24s waiting %2d-%2d: n %6d late %4.1f%%  friday %4.1f%%  new %4.1f%%" % (v, lo, hi, len(x), 100 * np.mean([r["late"] for r in x]), 100 * np.mean([chance(r["x"]) for r in x]), 100 * np.mean([p_new(r) for r in x])))
def auc(rs, f):
    s = sorted(rs, key=f); pos = sum(r["late"] for r in s); neg = len(s) - pos
    rank = sum(i + 1 for i, r in enumerate(s) if r["late"])
    return (rank - pos * (pos + 1) / 2) / (pos * neg)
for v in ("steep-notes-offers-8", "opt-mu-0.3-lambda-100"):
    x = [r for r in test if r["variant"] == v]
    print("  AUC on %s: friday %.3f, new %.3f" % (v, auc(x, lambda r: chance(r["x"])), auc(x, p_new)))
