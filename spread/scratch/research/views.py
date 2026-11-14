"""One row per driver view of a single-car order's gig: what the driver saw and whether they booked on that look."""
import gzip, json, sys, glob, collections, math
arch = sys.argv[1]
m = json.load(open(arch + "/map.json")); pos = {p["id"]: (p["lat"], p["lon"]) for p in m["places"]}
def km(a, b):
    (la, lo), (lb, lob) = pos[a], pos[b]; x = math.radians(lob - lo) * math.cos(math.radians((la + lb) / 2)); y = math.radians(lb - la)
    return 6371 * math.hypot(x, y)
road = {(r["from"], r["to"]): r["minutes"] for r in m["roads"]}
lanefee = json.load(open(sys.argv[2]))
rows = []; orders = []
for variant in sys.argv[3:]:
    for path in sorted(glob.glob(f"{arch}/runs/{variant}/*-L8.json.gz")):
        run = json.load(gzip.open(path)); seed = path.split("/")[-1][:-11]
        req = {r["request"]["id"]: r["request"] for r in run["reveal"]["requests"]}
        home = {d["id"]: d["homePlaceId"] for d in run["roster"]}; rost = {d["id"]: d for d in run["roster"]}
        near = {p: sum(km(h, p) <= 30 for h in home.values()) for p in pos}
        gig = {g["id"]: g for g in run["gigs"]}
        single = {g["id"] for g in run["gigs"] if len({s["orderId"] for s in g["stops"]}) == 1 and len(g["stops"]) == 2}
        o = collections.defaultdict(lambda: dict(first_post=None, first_view=None, first_fee=None, views=0, drops=0, book=None, seen=collections.Counter(), late=0, refund=0, fees=0, other=0, lastPickupAt=None, close=None, booked_by=None, viewers={}))
        belief = collections.defaultdict(list)  # driver -> [(ratio, minutes)] learned so far
        for g in run["gigs"]:
            oid = g["stops"][0]["orderId"]; o[oid]["first_post"] = g["postedAt"] if o[oid]["first_post"] is None else min(o[oid]["first_post"], g["postedAt"])
        ev = run["events"]; booked_at = {(e["gigId"], e["driverId"], e["at"]) for e in ev if e["kind"] == "gig_booked"}
        unbooked = 0
        for e in ev:
            k = e["kind"]
            if k == "order_won":
                r = o[e["order"]["id"]]; r.update(won=e["at"], option=e["order"]["option"], deadline=e["order"]["deadline"], price=e["order"]["priceCents"], lastPickupAt=e["order"].get("lastPickupAt"), unbooked_at_win=unbooked); unbooked += 1
            elif k == "order_changed" and e.get("order", {}).get("id") in o: o[e["order"]["id"]]["lastPickupAt"] = e["order"].get("lastPickupAt", o[e["order"]["id"]]["lastPickupAt"])
            elif k == "deadline_close": o[e["orderId"]]["close"] = e["at"] if o[e["orderId"]]["close"] is None else o[e["orderId"]]["close"]
            elif k == "gig_viewed":
                g = gig[e["gigId"]]; oid = g["stops"][0]["orderId"]; r = o[oid]; q = req.get(oid)
                fee = [s["feeCents"] for s in g["schedule"] if s["at"] <= e["at"]]; fee = fee[-1] if fee else g["schedule"][0]["feeCents"]
                if r["first_view"] is None: r["first_view"] = e["at"]; r["first_fee"] = fee
                d = e["driverId"]; r["views"] += 1; r["seen"][d] += 1; r["viewers"].setdefault(d, fee)
                if q is None or len(q["legs"]) != 1 or e["gigId"] not in single: continue
                leg = q["legs"][0]; a, b = leg["pickup"]["placeId"], leg["delivery"]["placeId"]; priv = leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"]
                lf = lanefee.get(f"{a}|{b}|{priv}", [None, 0]); bl = belief[d]
                rows.append([variant, seed, oid, d, e["at"], fee, q["referenceFeeCents"], lf[0], lf[1], int((e["gigId"], d, e["at"]) in booked_at or (e["gigId"], d, e["at"] + 1) in booked_at),
                             r["first_post"], r["views"], r["seen"][d], r["lastPickupAt"], r.get("deadline"), r.get("option"), r["drops"], r["close"] is not None,
                             round(km(home[d], a), 1), near[a], near[b], road.get((a, b)), rost[d]["rating"], rost[d]["completedGigs"], rost[d]["drops"], rost[d]["licence"],
                             len(bl), sum(x[0] for x in bl[-10:]) / max(1, len(bl[-10:])), sum(x[1] for x in bl[-10:]) / max(1, len(bl[-10:])), r["first_fee"], leg["pickup"]["window"]["from"], priv, len(run["roster"]), unbooked, r["book"] is not None])
            elif k == "gig_booked":
                g = gig[e["gigId"]]; oid = g["stops"][0]["orderId"]; r = o[oid]
                if r["book"] is None: r["book"] = e["at"]; r["book_fee"] = e["feeCents"]; unbooked -= 1
                elif r["booked_by"] is None: unbooked -= 1
                r["booked_by"] = e["driverId"]; r["last_book"] = e["at"]; r["last_fee"] = e["feeCents"]
                if r["first_fee"]:
                    for d in r["viewers"]: belief[d].append((e["feeCents"] / r["first_fee"], e["at"] - r["first_view"]))
            elif k == "gig_dropped":
                r = o[gig[e["gigId"]]["stops"][0]["orderId"]]; r["drops"] += 1; r["booked_by"] = None; unbooked += 1
            elif k == "ledger":
                l = e["line"]
                if l.get("orderId"):
                    r = o[l["orderId"]]
                    if l["kind"] in ("late_refund", "undelivered_penalty"): r["late"] = 1; r["refund"] -= l["cents"]
                    elif l["kind"] == "driver_fee": r["fees"] -= l["cents"]
                    elif l["kind"] != "revenue" and l["cents"] < 0: r["other"] -= l["cents"]
        for oid, r in o.items():
            q = req.get(oid)
            if q is None or r.get("won") is None or len(q["legs"]) != 1: continue
            leg = q["legs"][0]; a, b = leg["pickup"]["placeId"], leg["delivery"]["placeId"]; priv = leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"]
            lf = lanefee.get(f"{a}|{b}|{priv}", [None, 0])
            orders.append(dict(variant=variant, seed=seed, id=oid, ref=q["referenceFeeCents"], lane=lf[0], lane_n=lf[1], list=q["options"][0]["listPriceCents"], price=r["price"], option=r["option"], won=r["won"], posted=r["first_post"], first_view=r["first_view"], first_fee=r["first_fee"],
                               book=r["book"], book_fee=r.get("book_fee"), last_book=r.get("last_book"), last_fee=r.get("last_fee"), views=r["views"], viewers=len(r["viewers"]), drops=r["drops"], late=r["late"], refund=r["refund"], fees=r["fees"], other=r["other"],
                               lastPickupAt=r["lastPickupAt"], deadline=r["deadline"], close=r["close"], near=near[a], near_to=near[b], minutes=road.get((a, b)), ready=leg["pickup"]["window"]["from"], priv=priv, drivers=len(run["roster"]), unbooked=r["unbooked_at_win"], note=q["note"] is not None))
        print(variant, seed, len(rows), len(orders), file=sys.stderr)
json.dump(dict(cols="variant seed oid driver at fee ref lane lane_n booked first_post nth_view nth_own lastPickupAt deadline option drops closed home_km near near_to minutes rating done pastdrops licence learned bel_ratio bel_min first_fee ready priv drivers unbooked had_book".split(), rows=rows, orders=orders), open(arch + "/view_rows.json", "w"))
