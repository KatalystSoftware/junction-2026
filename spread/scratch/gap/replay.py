"""A replay of the saved reference weeks with feedback: the quotes change what is won, what is won changes the backlog,
the day's live shift and each dealer's trust, and those change the next quotes. Offline: it reads saved weeks only.

What is taken from the saved week: the requests, each day's price level (fitted on the whole day's answers), and for each
quote one hidden draw that agrees with its answer at the played price and trust, so the reference rules reproduce the
played week. An order that the replay wins and the week also won keeps its own course (bookings, drops, delivery,
lateness); another order takes the course of a saved order with the same hours to find a driver, on a Friday or not. More won cars
without a driver raise an order's chance to be late by the fit in backlog_late.py.

Not in it: drivers getting scarcer as more cars are won beyond that fit, and the competitor cutting prices where the
desk wins most. PYTHONPATH=. uv run --with numpy python scratch/gap/replay.py <data> <cache> <variant> [draws]"""
import sys, json, math, collections, pickle, random
import numpy as np
import lib
from spreadlab import curve
data, cache, variant = sys.argv[1:4]
DRAWS = int(sys.argv[4]) if len(sys.argv) > 4 else 2
minutes = lib.minutes_of(json.load(open(f"{data}/map.json")))
weeks = lib.cached(data, variant, minutes, cache)
quotes = {(r["w"], r["rid"]): r for r in pickle.load(open(f"{cache}/quotes-{variant}.pkl", "rb"))}
state = {(s["w"], s["rid"]): s for s in pickle.load(open(f"{cache}/state-{variant}.pkl", "rb"))}
level = {tuple(int(x) for x in k.split("|")): v for k, v in json.load(open(f"{cache}/levels-{variant}.json"))["level"].items()}
M = curve.MODELS["day"]; B = M["slope"]; TW = M["trust"]; DAY = 1440; n = len(weeks)
MULT = np.array([curve.LOW + curve.STEP * k for k in range(int(round((curve.HIGH - curve.LOW) / curve.STEP)) + 1)]); LOGM = np.log(MULT)
LATE_W = (0.075, 0.157, 0.030)  # log odds of a late order per won car without a driver: due within 8 h, 8 to 24 h, later (backlog_late.py)
sig = lambda z: 1 / (1 + math.exp(-z))

def best(a, shift, list_c, cost_c):
    return float(MULT[np.argmax((MULT * list_c - cost_c) / (1 + np.exp(-(a - B * (LOGM - shift)))))])

def live_shift(zs, wons, sd):
    if not zs: return 0.0
    z = np.array(zs); w = np.array(wons, float); d = 0.0
    for _ in range(8):
        c = 1 / (1 + np.exp(-(z + B * d)))
        d += max(-0.3, min(0.3, (B * (w - c).sum() - d / sd ** 2) / (B * B * (c * (1 - c)).sum() + 1 / sd ** 2)))
    return d

cls = lambda h: "<6" if h < 6 else "6-8" if h < 8 else "8-12" if h < 12 else "12-30" if h < 30 else "30+"

def slack(q, o):
    leg = q["legs"][0]
    return o["deadline"] - minutes[(leg["pickup"]["placeId"], leg["delivery"]["placeId"])] - max(q["respondBy"], leg["pickup"]["window"]["from"])

# the weeks, as plain rows
W = []; pool = collections.defaultdict(list); took = collections.defaultdict(collections.Counter); mismatch = 0; checked = 0
for wi, w in enumerate(weeks):
    booked_iv = {}
    for o in w["orders"].values():  # the minutes, from the win, in which no driver held the order's car
        ev = sorted([(b[0], 1) for b in o["bookings"]] + [(d[0], 0) for d in o["drops"]])
        open_from, iv = o["wonAt"], []
        for at, kind in ev:
            if kind == 1 and open_from is not None: iv.append((open_from - o["wonAt"], at - o["wonAt"])); open_from = None
            elif kind == 0 and open_from is None: open_from = at
        if open_from is not None: iv.append((open_from - o["wonAt"], (o["pickedUp"] or o["lastPickupAt"] + 600) - o["wonAt"]))
        booked_iv[o["id"]] = iv
    reqs = []
    for rid, r in sorted(w["reqs"].items(), key=lambda kv: (kv[1]["request"]["arrivedAt"], kv[0])):
        q = r["request"]; dec = w["decisions"][rid]
        if lib.req_kind(q) != "dealer" or dec["declined"] == "slack": continue
        opts = [o for o in q["options"] if slack(q, o) >= 300]
        if dec["declined"] is None:
            checked += 1; mismatch += sorted(o["kind"] for o in opts) != sorted(dec["prices"])
            opts = [o for o in q["options"] if o["kind"] in dec["prices"]]
        if not opts: continue
        first = curve.fastest(opts); day = q["arrivedAt"] // DAY
        if (wi, day) not in level: continue
        row = {"rid": rid, "at": q["arrivedAt"], "by": q["respondBy"], "dealer": q["dealerId"], "day": day, "a0": curve.at_list(q, opts, 0, M), "list": first["listPriceCents"],
               "lists": {o["kind"]: o["listPriceCents"] for o in opts}, "fee": q["referenceFeeCents"], "s": level[(wi, day)], "kinds": "+".join(sorted(o["kind"] for o in opts)),
               "ready": q["legs"][0]["pickup"]["window"]["from"], "played": None, "life": None,
               "premium": q["legs"][0]["car"]["premium"],
               "h": (first["deadline"] - minutes[(q["legs"][0]["pickup"]["placeId"], q["legs"][0]["delivery"]["placeId"])] - q["respondBy"]) / 60}
        pq = quotes.get((wi, rid))
        if pq is not None: row["played"] = (sig(pq["a"] - B * (math.log(pq["m"]) - pq["s"])), pq["won"])
        o = w["orders"].get(rid)
        if o is not None and not o["cancelled"]:
            st = state[(wi, rid)]
            life = {"iv": booked_iv[rid], "lag": None if o["delivered"] is None else o["delivered"] - max(row["ready"], o["wonAt"]), "late": o["late"], "last": o["lastPickupAt"] - o["wonAt"],
                    "fee": o["fees"] / q["referenceFeeCents"], "refund": o["refund"] / max(o["price"], 1), "other": o["other"], "option": o["option"], "u": (st["u8"], st["u24"], st["ulater"])}
            row["life"] = life
            key = (cls(row["h"]), o["wonAt"] // DAY == 4)
            pool[key].append(life); pool[key[:1]].append(life); took[row["kinds"]][o["option"]] += 1
        reqs.append(row)
    W.append(reqs)
print(f"options rebuilt as the policy chose them on {100 * (1 - mismatch / checked):.1f}% of {checked} quotes")
REFUND_LATE = lib.mean(l["refund"] for v in pool.values() for l in v if l["late"])

def play(rule, seed=0, learn=0.16, gate=15):
    """rule(parts, row, trust) -> the order's cost in typical fees, where parts = (cars without a driver due within 8 h, 8 to 24 h, later)."""
    rng = random.Random(seed); tot = collections.Counter(); per_week = []
    for wi, reqs in enumerate(W):
        trust = collections.Counter(); orders = []; pending = []; deliveries = []; today = (-1, [], []); wk = collections.Counter()
        for row in reqs:
            now = row["at"]
            pending.sort(key=lambda p: p[0])
            while pending and pending[0][0] <= now:
                by, r, won, z, price_mult = pending.pop(0)
                if today[0] != r["day"]: today = (r["day"], [], [])
                today[1].append(z); today[2].append(won)
                if not won: continue
                parts = [0, 0, 0]
                for o in orders:
                    if any(a <= by - o["won"] < b for a, b in o["iv"]):
                        left = o["won"] + o["last"] - by; parts[0 if left <= 480 else 1 if left <= 1440 else 2] += 1
                life = r["life"]
                if life is None:
                    kinds = took[r["kinds"]]; option = rng.choices(list(kinds), list(kinds.values()))[0] if kinds else curve.fastest([{"kind": k} for k in r["lists"]])["kind"]
                    if option not in r["lists"]: option = next(iter(r["lists"]))
                    key = (cls(r["h"]), by // DAY == 4)
                    life = rng.choice(pool.get(key) or pool[key[:1]])
                else: option = life["option"]
                # the chance to be late moves with the backlog at the win, against the backlog its course was saved under
                shift_ = sum(wt * (p - u) for wt, p, u in zip(LATE_W, parts, life["u"]))
                late, p0 = life["late"], 0.044
                p1 = sig(math.log(p0 / (1 - p0)) + shift_)
                if not late and p1 > p0 and rng.random() < (p1 - p0) / (1 - p0): late = True
                elif late and p1 < p0 and rng.random() < (p0 - p1) / p0: late = False
                price = price_mult * r["lists"][option]
                refund = (life["refund"] if life["late"] else REFUND_LATE) * price if late else 0
                orders.append({"won": by, "iv": life["iv"], "last": life["last"]})
                lag = life["lag"] if life["lag"] is not None else 3 * DAY
                deliveries.append((max(r["ready"], by) + lag, r["dealer"], not late))
                wk["orders"] += 1; wk["late"] += late; wk["revenue"] += price; wk["fees"] += life["fee"] * r["fee"]; wk["refund"] += refund; wk["other"] += life["other"]
                wk["typ"] += r["fee"]
            deliveries.sort()
            while deliveries and deliveries[0][0] <= now:
                _, dealer, ok = deliveries.pop(0)
                trust[dealer] = min(25, trust[dealer] + 1) if ok else trust[dealer] // 2
            parts = [0, 0, 0]
            for o in orders:
                if any(a <= now - o["won"] < b for a, b in o["iv"]):
                    left = o["won"] + o["last"] - now; parts[0 if left <= 480 else 1 if left <= 1440 else 2] += 1
            wk["quotes_seen"] += 1; wk["backlog"] += sum(parts)
            if gate and sum(parts) >= gate:
                wk["gated"] += 1; continue
            t = trust[row["dealer"]]; a = row["a0"] + TW * math.log(1 + 0.01 * t)
            shift = live_shift(today[1], today[2], learn) if today[0] == row["day"] else 0.0
            m = best(a, shift, row["list"], row["fee"] * rule(parts, row, t))
            p = sig(a - B * (math.log(m) - row["s"]))
            if row["played"] is not None:
                p0, won0 = row["played"]
                u = row.setdefault("u", {}).setdefault(seed, rng.random() * p0 if won0 else p0 + rng.random() * (1 - p0))
            else: u = row.setdefault("u", {}).setdefault(seed, rng.random())
            wk["quotes"] += 1; wk["trust"] += t
            pending.append((row["by"], row, u < p, a - B * math.log(m), m))
        # the quotes still without an answer at the end of the week are answered too
        for by, r, won, z, price_mult in pending:
            if won:
                life = r["life"] or rng.choice(pool[(cls(r["h"]),)])
                price = price_mult * r["lists"].get(life["option"], r["list"])
                wk["orders"] += 1; wk["late"] += life["late"]; wk["revenue"] += price; wk["fees"] += life["fee"] * r["fee"]; wk["refund"] += life["refund"] * price; wk["other"] += life["other"]; wk["typ"] += r["fee"]
        per_week.append(wk); tot.update(wk)
    return tot, per_week

def show(name, rule, **kw):
    res = [play(rule, seed, **kw) for seed in range(DRAWS)]
    f = lambda k: sum(t[k] for t, _ in res) / DRAWS / n
    orders, late = f("orders"), f("late")
    margin = (f("revenue") - f("fees") - f("refund") - f("other")) / 100
    load = 0.026 * max(0.0, orders - BASE[0]) / 100 * f("typ") / 100 if BASE else 0.0  # paid fees rise 0.026 x the typical fee per 100 more orders
    ontime = [1 - sum(pw[i]["late"] for _, pw in res) / max(1, sum(pw[i]["orders"] for _, pw in res)) for i in range(n)]
    worst = sorted(ontime)
    print(f"{name:58} orders {orders:6.1f}  late {late:5.1f}  on time {100 * (1 - late / orders):5.1f}%  weeks under 92% {sum(x < 0.92 for x in ontime):2}, under 90% {sum(x < 0.90 for x in ontime):2}, lowest {100 * worst[0]:.1f}%"
          f"  price/order {f('revenue') / orders / 100:6.1f}  fee/typ {f('fees') / f('typ'):.3f}  margin {margin:7.0f}  with dearer drivers {margin - load:7.0f}  gated {f('gated'):5.1f}  backlog {f('backlog') / f('quotes_seen'):4.1f}  trust at quote {f('trust') / f('quotes'):4.1f}")
    return orders, margin - load

BASE = None
BASE = show("reference: cost 1.3 + 0.04 a car, gate 15", lambda p, r, t: 1.3 + 0.04 * sum(p))
if __name__ == "__main__":
    print("-- checks against played sweeps (cost 1.4: -31.5 orders, -2.7 late, -460; cost 1.2 on `steep`: +34 orders, +2.6 late, +709)")
    show("cost 1.4 + 0.04 a car", lambda p, r, t: 1.4 + 0.04 * sum(p))
    show("cost 1.2 + 0.04 a car", lambda p, r, t: 1.2 + 0.04 * sum(p))
    print("-- the backlog surcharge")
    show("cost 1.3 + 0.02 a car", lambda p, r, t: 1.3 + 0.02 * sum(p))
    show("cost 1.3 + 0.01 a car", lambda p, r, t: 1.3 + 0.01 * sum(p))
    show("cost 1.3, no surcharge", lambda p, r, t: 1.3)
    show("cost 1.3, no surcharge, gate 25", lambda p, r, t: 1.3, gate=25)
    show("cost 1.3 + 0.04 a car due within 24 h", lambda p, r, t: 1.3 + 0.04 * (p[0] + p[1]))
    show("cost 1.3 + 0.08 a car due within 24 h", lambda p, r, t: 1.3 + 0.08 * (p[0] + p[1]))
    show("cost 1.3 + 0.04 a car due within 24 h, gate 25", lambda p, r, t: 1.3 + 0.04 * (p[0] + p[1]), gate=25)
    show("cost 1.4 + 0.04 a car due within 24 h, gate 25", lambda p, r, t: 1.4 + 0.04 * (p[0] + p[1]), gate=25)
    show("cost 1.4, no surcharge, gate 25", lambda p, r, t: 1.4, gate=25)
    show("cost 1.2, no surcharge, gate 25", lambda p, r, t: 1.2, gate=25)
