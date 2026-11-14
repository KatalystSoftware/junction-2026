"""Direct offers: who reads and accepts them, and how often a driver of ours ends a gig where an open gig starts.
What the desk knew of the driver when it sent the offer is in offers_known.py: an accepted offer is itself a booking
that day, so "booked today" has to be counted before the offer.
PYTHONPATH=. uv run --with numpy python scratch/gap/offers.py <data> <cache> <variant>..."""
import sys, json, collections
import lib
data, cache = sys.argv[1:3]
minutes = lib.minutes_of(json.load(open(f"{data}/map.json")))
DAY = 1440
for variant in sys.argv[3:]:
    weeks = lib.cached(data, variant, minutes, cache)
    n = len(weeks)
    rows = []; chain = collections.Counter()
    for w in weeks:
        home = {d["id"]: d["homePlaceId"] for d in w["roster"]}
        gig = {g["id"]: g for g in w["gigs"]}
        # where each driver is: deliveries of our gigs
        ends = collections.defaultdict(list)  # driver -> [(minute, place)]
        gig_driver = {}
        for e in w["ev"]["gig_started"]: gig_driver[e["gigId"]] = e["driverId"]
        for e in w["ev"]["delivered"]:
            d = gig_driver.get(e["gigId"])
            if d: ends[d].append((e["at"], e["placeId"]))
        for e in w["ev"]["offer_answered"]:
            g = gig.get(e["gigId"])
            if not g: continue
            oid = g["stops"][0]["orderId"]; o = w["orders"].get(oid)
            if not o: continue
            leg = o["request"]["legs"][g["stops"][0]["leg"]]
            pick, deliv = leg["pickup"]["placeId"], leg["delivery"]["placeId"]
            d = e["driverId"]; h = home[d]
            rows.append({"answer": e["answer"], "hp": minutes.get((h, pick), 0), "hd": minutes.get((deliv, h), 0), "hour": e["at"] % DAY // 60,
                         "to_last": o["lastPickupAt"] - e["at"], "drive": minutes[(pick, deliv)],
                         "here": any(place == pick and 0 <= e["at"] - at <= 240 for at, place in ends.get(d, []))})
        # chains without help: the final driver of an order ended another gig of ours at (or near) its pickup the same day, before collecting it
        for o in w["orders"].values():
            if o["cancelled"] or not o["bookings"] or len(o["request"]["legs"]) > 1: continue
            leg = o["request"]["legs"][0]; pick = leg["pickup"]["placeId"]
            last = max(o["bookings"]); d = last[1]
            pu = o["pickedUp"]
            chain["orders"] += 1
            if pu is not None and any(minutes.get((place, pick), 999) <= 30 and 0 <= pu - at <= 600 and at // DAY == pu // DAY for at, place in ends.get(d, [])):
                chain["driver came from a delivery of ours within 30 min of the pickup"] += 1
            if home[d] == pick: chain["driver lives at the pickup"] += 1
            if home[d] == leg["delivery"]["placeId"]: chain["driver lives at the delivery"] += 1
    print(f"\n== {variant}, {n} weeks: offers answered/wk {len(rows) / n:.0f}, accepted {sum(r['answer'] == 'accepted' for r in rows) / n:.1f}, declined (read) {sum(r['answer'] == 'declined' for r in rows) / n:.0f}, expired {sum(r['answer'] == 'expired' for r in rows) / n:.0f}")
    def table(name, key, order=None):
        g = collections.defaultdict(list)
        for r in rows: g[key(r)].append(r)
        print(f"{name:40} offers/wk  read%  accepted% of all  of read")
        for k in (order or sorted(g)):
            v = g.get(k)
            if not v: continue
            acc = sum(r["answer"] == "accepted" for r in v); read = acc + sum(r["answer"] == "declined" for r in v)
            print(f"  {str(k):38} {len(v) / n:7.1f} {100 * read / len(v):6.1f} {100 * acc / len(v):8.2f} {100 * acc / max(read, 1):10.1f}")
    b = lambda x: "0 (lives there)" if x == 0 else "1-30" if x <= 30 else "31-60" if x <= 60 else "61-120" if x <= 120 else "121+"
    O = ["0 (lives there)", "1-30", "31-60", "61-120", "121+"]
    table("minutes from home to the pickup", lambda r: b(r["hp"]), O)
    table("minutes from the delivery to home", lambda r: b(r["hd"]), O)
    table("ended a gig of ours at the pickup <4h ago", lambda r: r["here"])
    table("hour", lambda r: r["hour"] // 3 * 3)
    table("hours to the last pickup", lambda r: "<0" if r["to_last"] < 0 else "0-3" if r["to_last"] < 180 else "3-6" if r["to_last"] < 360 else "6-8" if r["to_last"] < 480 else "8-24" if r["to_last"] < 1440 else "24+", ["<0", "0-3", "3-6", "6-8", "8-24", "24+"])
    print("chains/wk:", {k: round(v / n, 1) for k, v in chain.items()})
