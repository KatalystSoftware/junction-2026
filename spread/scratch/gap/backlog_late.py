"""Does the backlog at the quote predict that the won order ends late, and which part of it? And the static model's
prediction for the cost changes that were played, to scale its other predictions.
PYTHONPATH=. uv run --with numpy python scratch/gap/backlog_late.py <data> <cache> <variant>"""
import sys, json, math, collections, pickle
import lib
from spreadlab import curve
data, cache, variant = sys.argv[1:4]
minutes = lib.minutes_of(json.load(open(f"{data}/map.json")))
weeks = lib.cached(data, variant, minutes, cache)
quotes = {(r["w"], r["rid"]): r for r in pickle.load(open(f"{cache}/quotes-{variant}.pkl", "rb"))}
state = pickle.load(open(f"{cache}/state-{variant}.pkl", "rb"))
B = curve.MODELS["day"]["slope"]; n = len(weeks)
won = []
for s in state:
    o = weeks[s["w"]]["orders"].get(s["rid"])
    if o is None or o["cancelled"]: continue
    first = min((b[0] for b in o["bookings"]), default=None)
    won.append({**s, "late": o["late"], "first": None if first is None else first - o["wonAt"], "fee": o["fees"] / o["request"]["referenceFeeCents"], "margin": o["margin"],
                "to_last": o["lastPickupAt"] - o["wonAt"]})
def table(name, key, order):
    g = collections.defaultdict(list)
    for r in won: g[key(r)].append(r)
    print(f"\n{name:44} orders/wk  late%  booked<=60m%  fee/typ  margin/order")
    for k in order:
        v = g.get(k)
        if not v: continue
        print(f"{str(k):44} {len(v) / n:8.1f} {100 * lib.mean(r['late'] for r in v):6.1f} {100 * lib.mean(r['first'] is not None and r['first'] <= 60 for r in v):9.1f} {lib.mean(r['fee'] for r in v):9.3f} {lib.mean(r['margin'] for r in v) / 100:8.1f}")
b = lambda x: "0" if x == 0 else "1-2" if x <= 2 else "3-5" if x <= 5 else "6-9" if x <= 9 else "10+"
O = ["0", "1-2", "3-5", "6-9", "10+"]
table("all won cars without a driver at the quote", lambda r: b(r["unb"]), O)
table("of them, last pickup within 8 h", lambda r: b(r["u8"]), O)
table("of them, last pickup 8-24 h away", lambda r: b(r["u24"]), O)
table("of them, last pickup over 24 h away", lambda r: b(r["ulater"]), O)
# two-way: urgent backlog low/high x later backlog low/high
table("within 24 h (u) x later (l)", lambda r: ("u<=2" if r["u8"] + r["u24"] <= 2 else "u>=3") + " " + ("l<=2" if r["ulater"] <= 2 else "l 3-5" if r["ulater"] <= 5 else "l>=6"),
      ["u<=2 l<=2", "u<=2 l 3-5", "u<=2 l>=6", "u>=3 l<=2", "u>=3 l 3-5", "u>=3 l>=6"])
# a logistic fit of late on the parts, with the order's own time to its last pickup
try:
    import numpy as np
    X = np.array([[1, r["u8"], r["u24"], r["ulater"], r["to_last"] < 480, r["to_last"] < 1440] for r in won], float); y = np.array([r["late"] for r in won], float)
    w = np.zeros(X.shape[1])
    for _ in range(50):
        p = 1 / (1 + np.exp(-X @ w)); H = X.T @ (X * (p * (1 - p))[:, None]) + 1e-6 * np.eye(len(w)); w += np.linalg.solve(H, X.T @ (y - p))
    se = np.sqrt(np.diag(np.linalg.inv(H)))
    print("\nlogistic fit of 'late' (log odds per car): ", {k: f"{a:+.3f} (se {s:.3f})" for k, a, s in zip(["intercept", "due<8h", "due 8-24h", "due later", "own<8h", "own<24h"], w, se)})
except ImportError:
    print("no numpy")
# the static model on changes that were played
ser = [s for s in state if "recon" in s]
def run(cost_of):
    wins = 0.0
    for s in ser:
        q = quotes[(s["w"], s["rid"])]
        m = curve.best(q["a"], s["live"], q["list"], q["fee"] * cost_of(s), B)
        wins += 1 / (1 + math.exp(-(q["a"] - B * (math.log(m) - q["s"]))))
    return wins / n
base = run(lambda s: 1.3 + 0.04 * s["unb"])
print("\nstatic model, orders/wk: cost 1.3 %.1f; cost 1.4 %.1f (played: -31.5 on 40 seeds); cost 1.2 %.1f (played on `steep`: +34.0 on 10 seeds)" % (
    base, run(lambda s: 1.4 + 0.04 * s["unb"]), run(lambda s: 1.2 + 0.04 * s["unb"])))
