"""Won one-car dealer orders for which, at the win, a driver already holds one of our cars that ends where this car starts
and lives where this car is going: how many there are, who drove them, and at what fee. usage: own_return.py <cache> <map.json> <variant>"""
import pickle, glob, sys, json, math, collections, statistics as st
cache, mapf, v = sys.argv[1:4]
m = json.load(open(mapf))
P = {p["id"]: (p["lat"], p["lon"]) for p in m["places"]}
MIN = {(r["from"], r["to"]): r["minutes"] for r in m["roads"]}
def km(a, b):
    (la, lo), (lb, lob) = P[a], P[b]
    return 6371 * math.hypot(math.radians(lob - lo) * math.cos(math.radians((la + lb) / 2)), math.radians(lb - la))
NEAR = {(a, b): km(a, b) <= 30 for a in P for b in P}
c = collections.Counter(); fees = []; reffs = []
files = sorted(glob.glob(f"{cache}/{v}/fresh-*.pkl"))[:120]
for f in files:
    w = pickle.load(open(f, "rb"))
    home = {d["id"]: d["homePlaceId"] for d in w["roster"]}
    req = {r["request"]["id"]: r["request"] for r in w["requests"]}
    gigs = {g["id"]: g for g in w["gigs"]}
    order_of = {g["id"]: g["stops"][0]["orderId"] for g in w["gigs"]}
    holds = []  # [driver, gig, booked at, ends at (drop or delivery), delivery place, delivered at or None]
    deliv = {}
    for e in w["events"]:
        if e["kind"] == "gig_booked":
            r = req.get(order_of.get(e["gigId"]))
            if r and len(r["legs"]) == 1: holds.append([e["driverId"], e["gigId"], e["at"], 10**9, r["legs"][0]["delivery"]["placeId"], None, e["feeCents"]])
        elif e["kind"] == "gig_dropped":
            for h in holds:
                if h[1] == e["gigId"] and h[0] == e["driverId"] and h[3] == 10**9: h[3] = e["at"]
        elif e["kind"] == "delivered":
            for h in holds:
                if h[1] == e["gigId"] and h[3] == 10**9: h[5] = e["at"]; h[3] = e["at"] + 240
    final = {}
    for h in holds:
        if h[5] is not None: final[order_of[h[1]]] = (h[0], h[6])
    for e in w["events"]:
        if e["kind"] != "order_won": continue
        o = e["order"]; r = req[o["id"]]
        if len(r["legs"]) != 1 or r["legs"][0]["pickup"]["privateAddress"] or r["legs"][0]["delivery"]["privateAddress"]: continue
        a, b = r["legs"][0]["pickup"]["placeId"], r["legs"][0]["delivery"]["placeId"]
        last = o.get("lastPickupAt", o["deadline"])
        c["orders"] += 1
        cands = {h[0] for h in holds if h[2] <= e["at"] <= h[3] and (h[4] == a or NEAR[(h[4], a)]) and (home[h[0]] == b or NEAR[(home[h[0]], b)])
                 and not (home[h[0]] == a or NEAR[(home[h[0]], a)])}
        if not cands: continue
        c["with a driver of ours bound there"] += 1; reffs.append(r["referenceFeeCents"])
        drv = final.get(o["id"])
        if drv:
            c["driven by one of them"] += drv[0] in cands
            if drv[0] in cands: fees.append(drv[1] / r["referenceFeeCents"])
n = len(files)
print(v, n, "weeks:", {k: round(x / n, 1) for k, x in c.items()}, "| typical fee of those orders %.0f eur | fee paid to such a driver %.2f x typical" % (st.mean(reffs) / 100, st.mean(fees) if fees else 0))
