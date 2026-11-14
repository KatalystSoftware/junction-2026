"""Rebuilds what the desk knew at each quote (won cars without a driver, the day's live shift), checks it against the price
it quoted, and splits the lost volume into the backlog surcharge, the gate and the late knowledge of the day's level.
Static: trust, the competitor and the backlog stay as played. PYTHONPATH=. uv run --with numpy python scratch/gap/backlog.py <data> <cache> <variant>"""
import sys, json, math, collections, pickle
import lib
from spreadlab import curve
data, cache, variant = sys.argv[1:4]
minutes = lib.minutes_of(json.load(open(f"{data}/map.json")))
weeks = lib.cached(data, variant, minutes, cache)
quotes = {(r["w"], r["rid"]): r for r in pickle.load(open(f"{cache}/quotes-{variant}.pkl", "rb"))}
M = curve.MODELS["day"]; B = M["slope"]; DAY = 1440; n = len(weeks)
out = []
for wi, w in enumerate(weeks):
    p = w["params"]
    events = sorted((e for v in w["ev"].values() for e in v), key=lambda e: e["seq"])
    orders = {}   # order id -> {"booked": bool, "last": lastPickupAt, "ready": minute}
    today = (0, [])
    asked = {}
    for e in events:
        k = e["kind"]
        if k == "price_request":
            rid = e["request"]["id"]
            q = quotes.get((wi, rid))
            dec = w["decisions"][rid]
            open_ = [o for o in orders.values() if not o["booked"]]
            now = e["at"]
            unb = len(open_)
            state = {"unb": unb, "u8": sum(o["last"] - now <= 480 for o in open_), "u24": sum(480 < o["last"] - now <= 1440 for o in open_),
                     "ulater": sum(o["last"] - now > 1440 for o in open_), "held": len(orders) - unb, "declined": dec["declined"], "w": wi, "rid": rid, "at": now}
            if q is not None:
                day = now // DAY
                live = curve.shift(today[1], p["learn"], B) if today[0] == day and today[1] else 0.0
                state.update(live=live, answers=len(today[1]) if today[0] == day else 0)
                asked[rid] = (day, q["a"] - B * math.log(q["m"]))
                cost = q["fee"] * (p["cost"] + p["backlog_step"] * unb)
                state["recon"] = curve.best(q["a"], live, q["list"], cost, B)
            out.append(state)
        elif k in ("order_won", "order_lost"):
            rid = e["order"]["id"] if k == "order_won" else e["requestId"]
            if rid in asked:
                day, z = asked.pop(rid)
                if today[0] != day: today = (day, [])
                today[1].append((z, k == "order_won"))
            if k == "order_won":
                o = e["order"]
                orders[o["id"]] = {"booked": False, "last": o["lastPickupAt"]}
        elif k == "order_changed" and e["order"]["id"] in orders:
            orders[e["order"]["id"]]["last"] = e["order"]["lastPickupAt"]
        elif k == "gig_booked":
            for oid in w["gig_orders"].get(e["gigId"], []):
                if oid in orders: orders[oid]["booked"] = True
        elif k in ("gig_dropped", "no_show", "gig_expired"):
            for oid in w["gig_orders"].get(e["gigId"], []):
                if oid in orders: orders[oid]["booked"] = False
        elif k == "visit_failed" and e["orderId"] in orders:
            orders[e["orderId"]]["booked"] = False
        elif k == "delivered":
            orders.pop(e["orderId"], None)
        elif k == "order_cancelled":
            orders.pop(e["orderId"], None)
pickle.dump(out, open(f"{cache}/state-{variant}.pkl", "wb"))
ser = [s for s in out if "recon" in s]
match = lib.mean(abs(s["recon"] - quotes[(s["w"], s["rid"])]["m"]) < 0.021 for s in ser)
print("quotes whose price the rebuild reproduces within one price step: %.1f%%" % (100 * match))
print("won cars without a driver at a quote: mean %.1f; of which last pickup within 8 h %.1f, 8-24 h %.1f, later %.1f; cars held by drivers %.1f" % (
    lib.mean(s["unb"] for s in out), lib.mean(s["u8"] for s in out), lib.mean(s["u24"] for s in out), lib.mean(s["ulater"] for s in out), lib.mean(s["held"] for s in out)))
dist = collections.Counter(min(s["unb"] // 3 * 3, 30) for s in ser)
print("serious quotes by backlog at the quote (share):", {k: round(v / len(ser), 3) for k, v in sorted(dist.items())})
print("mean surcharge on the cost, in typical fees: %.3f" % lib.mean(0.04 * s["unb"] for s in ser))
gate = [s for s in out if s["declined"] == "backlog"]
print("declined at the gate /wk %.1f; their backlog: within 8 h %.1f, 8-24 h %.1f, later %.1f" % (len(gate) / n, lib.mean(s["u8"] for s in gate), lib.mean(s["u24"] for s in gate), lib.mean(s["ulater"] for s in gate)))
# counterfactual prices
mult = [1.0 + 0.02 * i for i in range(71)]
def run(name, cost_of, shift_of, extra=()):
    wins = rev = fee = 0.0
    for s in ser:
        q = quotes[(s["w"], s["rid"])]
        m = curve.best(q["a"], shift_of(s, q), q["list"], q["fee"] * cost_of(s), B)
        pr = 1 / (1 + math.exp(-(q["a"] - B * (math.log(m) - q["s"]))))
        wins += pr; rev += pr * m * q["list"]; fee += pr * q["fee"]
    print(f"{name:58} orders/wk {wins / n:6.1f}  price/order {rev / wins / 100:6.1f}  margin/order at 1.08 x fee {(rev - 1.08 * fee) / wins / 100:5.1f}  margin/wk {(rev - 1.08 * fee) / n / 100:7.0f}  at 1.15: {(rev - 1.15 * fee) / n / 100:7.0f}")
live = lambda s, q: s["live"]; known = lambda s, q: q["s"]
print()
run("as played: surcharge 0.04 a car, live shift", lambda s: 1.3 + 0.04 * s["unb"], live)
run("surcharge 0.02 a car, live shift", lambda s: 1.3 + 0.02 * s["unb"], live)
run("surcharge only on cars due within 24 h, live shift", lambda s: 1.3 + 0.04 * (s["u8"] + s["u24"]), live)
run("surcharge only on cars due within 8 h, live shift", lambda s: 1.3 + 0.04 * s["u8"], live)
run("no surcharge, live shift", lambda s: 1.3, live)
run("surcharge 0.04, the day's level known", lambda s: 1.3 + 0.04 * s["unb"], known)
run("no surcharge, the day's level known", lambda s: 1.3, known)
run("no surcharge, cost 1.2, live shift", lambda s: 1.2, live)
run("no surcharge, cost 1.4, live shift", lambda s: 1.4, live)
# the live shift against the level, by answers so far
print("\nanswers so far today | quotes/wk | live shift - day's level (mean, mean abs) | win% | expected win% at the price for the known level")
g = collections.defaultdict(list)
for s in ser:
    g["0" if s["answers"] == 0 else "1-4" if s["answers"] < 5 else "5-14" if s["answers"] < 15 else "15-39" if s["answers"] < 40 else "40-99" if s["answers"] < 100 else "100+"].append(s)
for k in ["0", "1-4", "5-14", "15-39", "40-99", "100+"]:
    v = g[k]; qs = [quotes[(s["w"], s["rid"])] for s in v]
    print(f"{k:8} {len(v) / n:7.1f}  {lib.mean(s['live'] - q['s'] for s, q in zip(v, qs)):+.3f} {lib.mean(abs(s['live'] - q['s']) for s, q in zip(v, qs)):.3f}  {100 * lib.mean(q['won'] for q in qs):5.1f}")
