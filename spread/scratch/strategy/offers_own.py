"""Answers to direct offers, by whether the driver holds one of our cars at that minute and whether that car ends where the offered car starts.
usage: offers_own.py <cache> <map.json> <variant> [...]"""
import pickle, glob, sys, json, math, collections
cache, mapf = sys.argv[1:3]
m = json.load(open(mapf))
P = {p["id"]: (p["lat"], p["lon"]) for p in m["places"]}
def km(a, b):
    (la, lo), (lb, lob) = P[a], P[b]
    return 6371 * math.hypot(math.radians(lob - lo) * math.cos(math.radians((la + lb) / 2)), math.radians(lb - la))
NEAR = {(a, b): a == b or km(a, b) <= 30 for a in P for b in P}
tab = collections.defaultdict(collections.Counter); weeks = 0
for v in sys.argv[3:]:
    for f in sorted(glob.glob(f"{cache}/{v}/*.pkl")):
        w = pickle.load(open(f, "rb")); weeks += 1
        home = {d["id"]: d["homePlaceId"] for d in w["roster"]}
        req = {r["request"]["id"]: r["request"] for r in w["requests"]}
        lane = {}
        for g in w["gigs"]:
            r = req.get(g["stops"][0]["orderId"])
            if r and len(r["legs"]) == 1: lane[g["id"]] = (r["legs"][0]["pickup"]["placeId"], r["legs"][0]["delivery"]["placeId"])
        holds = collections.defaultdict(list)
        for e in w["events"]:
            k = e["kind"]
            if k == "gig_booked" and e["gigId"] in lane: holds[e["driverId"]].append([e["gigId"], e["at"], 10**9])
            elif k == "gig_dropped":
                for h in holds[e["driverId"]]:
                    if h[0] == e["gigId"] and h[2] == 10**9: h[2] = e["at"]
            elif k == "delivered":
                for hs in holds.values():
                    for h in hs:
                        if h[0] == e["gigId"] and h[2] == 10**9: h[2] = e["at"] + 240
            elif k == "offer_answered" and e["gigId"] in lane:
                a, b = lane[e["gigId"]]; d = e["driverId"]; at = e["at"] - 10
                mine = [lane[g][1] for g, s, t in holds.get(d, []) if s <= at <= t and g != e["gigId"]]
                there = any(NEAR[(x, a)] for x in mine); homeward = NEAR[(home[d], b)]
                what = ("holds our car that ends there, lives at the delivery" if there and homeward else "holds our car that ends there" if there else
                        "holds another car of ours" if mine else "lives at the delivery, holds none" if homeward else "holds none")
                tab[what][e["answer"]] += 1
print(weeks, "weeks")
for what, c in sorted(tab.items(), key=lambda x: -sum(x[1].values())):
    n = sum(c.values())
    print(" %-55s offers %7d (%.1f a week), accepted %5d = %.2f%%, declined (read and refused) %.1f%%, expired %.1f%%" % (what, n, n / weeks, c["accepted"], 100 * c["accepted"] / n, 100 * c["declined"] / n, 100 * c["expired"] / n))
