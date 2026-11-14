"""One row for each won order of the cached weeks: what the desk knew at the quote (slow.py's terms), the won cars
without a driver at that minute, the day, whether it ended late, and its account lines. usage: rows.py <cache> <map.json> <out.pkl> <variant> [...]"""
import pickle, glob, sys, json, math, collections
from multiprocessing import Pool
cache, mapf, out = sys.argv[1], sys.argv[2], sys.argv[3]
m = json.load(open(mapf))
MIN = {(r["from"], r["to"]): r["minutes"] for r in m["roads"]}
P = {p["id"]: (p["lat"], p["lon"]) for p in m["places"]}
def km(a, b):
    (la, lo), (lb, lob) = P[a], P[b]
    return 6371 * math.hypot(math.radians(lob - lo) * math.cos(math.radians((la + lb) / 2)), math.radians(lb - la))
NEAR = {a: [b for b in P if km(a, b) <= 30] for a in P}
DAY, HOUR = 1440, 60
def kind(r):
    if len(r["legs"]) > 1: return "trade_in"
    l = r["legs"][0]
    return "private_pickup" if l["pickup"]["privateAddress"] else "private_delivery" if l["delivery"]["privateAddress"] else ""
def week(f):
    w = pickle.load(open(f, "rb"))
    homes = collections.Counter(d["homePlaceId"] for d in w["roster"])
    notified = {a: sum(homes[b] for b in NEAR[a]) for a in P}
    req = {r["request"]["id"]: r for r in w["requests"]}
    order_of = {g["id"]: g["stops"][0]["orderId"] for g in w["gigs"]}
    won, booked, done, money, late = {}, collections.defaultdict(set), {}, collections.Counter(), set()
    timeline = []  # (at, order id, +1 unbooked / -1 booked)
    for e in w["events"]:
        k = e["kind"]
        if k == "order_won": won[e["order"]["id"]] = e
        elif k == "ledger":
            o = e["line"].get("orderId")
            if o:
                money[o] += e["line"]["cents"]
                if e["line"]["kind"] in ("late_refund", "undelivered_penalty"): late.add(o)
    # intervals in which a won order has no driver: from the win to the first booking, and from each drop to the next booking
    state = {}
    spans = collections.defaultdict(list)
    for e in w["events"]:
        k = e["kind"]
        if k == "order_won": state[e["order"]["id"]] = e["at"]
        elif k == "gig_booked":
            o = order_of.get(e["gigId"])
            if o in state and state[o] is not None: spans[o].append((state[o], e["at"])); state[o] = None
        elif k in ("gig_dropped", "no_show"):
            o = order_of.get(e["gigId"])
            if o in state and state[o] is None: state[o] = e["at"]
        elif k in ("order_cancelled",):
            o = e.get("orderId") or (e.get("order") or {}).get("id")
            if o in state and state[o] is not None: spans[o].append((state[o], e["at"])); state[o] = None
    for o, s in state.items():
        if s is not None: spans[o].append((s, 10**9))
    last = {o: e["order"].get("lastPickupAt", e["order"]["deadline"]) for o, e in won.items()}
    flat = sorted((a, b, last[o]) for o, ss in spans.items() for a, b in ss)
    rows = []
    for o, e in won.items():
        r = req[o]["request"]
        at = r["arrivedAt"]
        quoted = [op for op in r["options"] if op["kind"] in (w["decisions"].get(o, {}).get("prices") or req[o].get("quote") or {})] or r["options"]
        fastest = min(quoted, key=lambda op: op["deadline"])
        drive = sum(MIN[(l["pickup"]["placeId"], l["delivery"]["placeId"])] for l in r["legs"])
        lastp = fastest["deadline"] - drive
        hours, friday = (lastp - r["respondBy"]) / HOUR, lastp // DAY % 7 == 4
        nt = min(notified[l["pickup"]["placeId"]] for l in r["legs"])
        x = [1.0, float(hours < 6), float(6 <= hours < 8), float(8 <= hours < 12), float(12 <= hours < 24), float(nt < 10), float(10 <= nt < 40),
             float(any(l["car"]["premium"] for l in r["legs"])), max(0, drive - 4 * HOUR) / HOUR, float(at // DAY % 7 == 4), float(r["note"] is not None),
             max(0, 760 - len(w["roster"])) / 100, float(friday), float(friday and hours < 12)]
        w24 = sum(1 for a, b, lp in flat if a <= at < b and lp - at <= 24 * HOUR)
        wl = sum(1 for a, b, lp in flat if a <= at < b and lp - at > 24 * HOUR)
        rows.append(dict(variant=w["variant"], seed=w["seed"], id=o, day=at // DAY, kind=kind(r), x=x, w24=w24, wl=wl, late=o in late, cents=money[o],
                         price=e["order"]["priceCents"], ref=r["referenceFeeCents"], list=fastest["listPriceCents"], hours=hours, drivers=len(w["roster"]),
                         onTime=w["score"]["onTimeShare"], margin=w["score"]["marginCents"], orders=w["score"]["wonOrders"]))
    return rows
if __name__ == "__main__":
    files = [f for v in sys.argv[4:] for f in sorted(glob.glob(f"{cache}/{v}/*.pkl"))]
    with Pool(4) as p: res = p.map(week, files, chunksize=4)
    pickle.dump([r for rs in res for r in rs], open(out, "wb"))
    print(len(files), "weeks", sum(len(r) for r in res), "orders")
