"""Each look at a one-car gig, by what the gig is to the driver who looks: a way home, a second leg after one of our
gigs, or neither; and whether the driver books within 30 minutes. usage: looks.py <cache dir> <map.json> <variant> [...]"""
import pickle, glob, sys, json, math, collections
cache, mapf = sys.argv[1], sys.argv[2]
m = json.load(open(mapf))
P = {p["id"]: (p["lat"], p["lon"]) for p in m["places"]}
def km(a, b):
    (la, lo), (lb, lob) = P[a], P[b]
    return 6371 * math.hypot(math.radians(lob - lo) * math.cos(math.radians((la + lb) / 2)), math.radians(lb - la))
NEAR = {(a, b): km(a, b) <= 30 for a in P for b in P}
def band(x):
    return "<0.85" if x < 0.85 else "0.85-0.95" if x < 0.95 else "0.95-1.05" if x < 1.05 else "1.05-1.3" if x < 1.3 else ">=1.3"
tab = collections.defaultdict(lambda: [0, 0])
weeks = 0
for v in sys.argv[3:]:
    for f in sorted(glob.glob(f"{cache}/{v}/*.pkl")):
        w = pickle.load(open(f, "rb")); weeks += 1
        home = {d["id"]: d["homePlaceId"] for d in w["roster"]}
        req = {r["request"]["id"]: r["request"] for r in w["requests"]}
        gig = {}
        for g in w["gigs"]:
            cars = {(s["orderId"], s["leg"]) for s in g["stops"]}
            if len(cars) != 1: continue
            r = req.get(g["stops"][0]["orderId"])
            if r is None or len(r["legs"]) != 1: continue
            l = r["legs"][0]
            gig[g["id"]] = (l["pickup"]["placeId"], l["delivery"]["placeId"], r["referenceFeeCents"], l["pickup"]["privateAddress"] or l["delivery"]["privateAddress"])
        booked = collections.defaultdict(list)   # (gig, driver) -> minutes
        holds = collections.defaultdict(list)    # driver -> [booked at, gig, ended at]
        for e in w["events"]:
            if e["kind"] == "gig_booked":
                booked[(e["gigId"], e["driverId"])].append(e["at"])
                holds[e["driverId"]].append([e["at"], e["gigId"], 10**9])
            elif e["kind"] == "gig_dropped":
                for h in holds[e["driverId"]]:
                    if h[1] == e["gigId"] and h[2] == 10**9: h[2] = e["at"]
            elif e["kind"] == "delivered":
                for hs in holds.values():
                    for h in hs:
                        if h[1] == e["gigId"] and h[2] == 10**9: h[2] = e["at"] + 180   # still "there" for three hours after the delivery
        seen = set()
        for vw in sorted(w["views"], key=lambda x: x["at"]):
            g, d, at = vw["gigId"], vw["driverId"], vw["at"]
            if g not in gig or gig[g][3]: continue
            first = (g, d) not in seen; seen.add((g, d))
            a, b, ref, _ = gig[g]
            h = home.get(d)
            # a gig of ours that the driver holds or has just ended, which leaves the driver where this car is
            chain = any(bk <= at <= end and g2 in gig and g2 != g and (gig[g2][1] == a or NEAR[(gig[g2][1], a)]) for bk, g2, end in holds.get(d, []))
            homeward = h == b or NEAR[(h, b)]
            local = h == a or NEAR[(h, a)]
            what = ("after our gig, homeward" if chain and homeward else "after our gig, not homeward" if chain else
                    "lives at the delivery" if homeward and not local else "lives at the pickup" if local else "elsewhere")
            took = any(at <= t <= at + 30 for t in booked.get((g, d), []))
            for key in ((what, band(vw["feeCents"] / ref)), (what, "all")):
                tab[key][0] += 1; tab[key][1] += took
print(weeks, "weeks")
bands = ["<0.85", "0.85-0.95", "0.95-1.05", "1.05-1.3", ">=1.3", "all"]
print("%-30s" % "looks, share booked in 30 min" + "".join("%18s" % b for b in bands))
for what in ("lives at the pickup", "lives at the delivery", "after our gig, homeward", "after our gig, not homeward", "elsewhere"):
    print("%-30s" % what + "".join("%18s" % ("%d  %.1f%%" % (tab[(what, b)][0], 100 * tab[(what, b)][1] / max(1, tab[(what, b)][0]))) for b in bands))
