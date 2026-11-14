"""One compact row set per archived week, for the scenario map: what the final could throw at the desk, how often
the saved weeks show it, and what it cost the variant that played them.

    python scratch/scenarios/extract.py <data folder> <out.json> <variant> [<variant> ...]

Reads only the saved weeks; plays nothing. Each week gives: the roster, the score, one row per won order, one per
quoted request, one per day, and the counts of the events that a scenario shows as.
"""
import collections, gzip, json, math, sys
sys.path.insert(0, ".")
from spreadlab import curve
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

DAY, HOUR = 1440, 60
MAP = None


def near_counts(roster, map_):
    """Drivers whose home is within 30 km in a straight line of each place (the app notifies those)."""
    places = {p["id"]: (p["lat"], p["lon"]) for p in map_["places"]}
    homes = collections.Counter(d["homePlaceId"] for d in roster)
    out = {}
    for a, (la, lo) in places.items():
        n = 0
        for b, (lb, lob) in places.items():
            x = math.radians(lob - lo) * math.cos(math.radians((la + lb) / 2)); y = math.radians(lb - la)
            if 6371 * math.hypot(x, y) <= 30:
                n += homes.get(b, 0)
        out[a] = n
    return out


def week(path):
    r = json.load(gzip.open(path))
    map_ = json.load(open(Path(path).parents[2] / "map.json"))
    near = near_counts(r["roster"], map_)
    ev = r["events"]
    requests, orders = {}, {}
    gig_orders, gig_post, booked, dropped, views = {}, {}, {}, collections.Counter(), collections.defaultdict(list)
    for g in r["gigs"]:
        gig_orders[g["id"]] = sorted({s["orderId"] for s in g["stops"]})
        gig_post[g["id"]] = g["postedAt"]
    counts = collections.Counter()
    late_refund, failed, warned, fees, offers = {}, collections.Counter(), {}, collections.Counter(), collections.Counter()
    first_book, last_book, first_post, changed, cancelled, forecasts = {}, {}, {}, {}, set(), []
    viewers_day = collections.defaultdict(set)
    trust, trust_at, model, dec = collections.Counter(), {}, curve.MODELS["day"], r.get("decisions", {})
    deadline_of, dealer_of = {}, {}
    for e in ev:
        k = e["kind"]; counts[k] += 1
        if k == "price_request":
            requests[e["request"]["id"]] = e["request"]
            trust_at[e["request"]["id"]] = trust[e["request"]["dealerId"]]
        elif k == "delivered":
            o = orders.get(e["orderId"])
            if o is not None and len(o["legs"]) == 1:
                d = o["dealerId"]
                trust[d] = min(25, trust[d] + 1) if e["at"] <= o["deadline"] else trust[d] // 2
        elif k == "order_won":
            o = e["order"]; orders[o["id"]] = dict(o, wonAt=e["at"])
        elif k == "gig_viewed":
            views[e["gigId"]].append((e["at"], e["driverId"])); viewers_day[e["at"] // DAY].add(e["driverId"])
        elif k == "gig_booked":
            for oid in gig_orders.get(e["gigId"], []):
                first_book.setdefault(oid, e["at"]); last_book[oid] = e["at"]
        elif k == "gig_dropped":
            for oid in gig_orders.get(e["gigId"], []):
                dropped[oid] += 1
        elif k == "no_show":
            for oid in gig_orders.get(e["gigId"], []):
                counts["no_show_orders"] += 1
        elif k == "visit_failed":
            failed[e["orderId"]] += 1; counts["failed_" + e["reason"]] += 1
        elif k == "deadline_close":
            warned.setdefault(e["orderId"], e["at"])
        elif k == "order_changed":
            changed.setdefault(e["order"]["id"], []).append((e["at"], (e.get("message") or {}).get("text", "")[:60]))
        elif k == "order_cancelled":
            cancelled.add(e["orderId"])
        elif k == "forecast":
            forecasts.append({"at": e["at"], "from": e["from"], "to": e["to"], "places": e["placeIds"]})
        elif k == "offer_answered":
            offers[e["answer"]] += 1
        elif k == "ledger":
            line = e["line"]
            if line["kind"] in ("late_refund", "undelivered_penalty") and line["orderId"]:
                late_refund[line["orderId"]] = late_refund.get(line["orderId"], 0) + line["cents"]
            counts["cents_" + line["kind"]] += line["cents"]
            if line["kind"] == "driver_fee" and line.get("orderId"):
                fees[line["orderId"]] += -line["cents"]
    for g in r["gigs"]:
        for oid in gig_orders[g["id"]]:
            first_post[oid] = min(first_post.get(oid, 10**9), g["postedAt"])
    truth = {o["orderId"]: o["legs"] for o in r["reveal"]["orders"]}
    quoted = {q["request"]["id"]: q for q in r["reveal"]["requests"]}
    snow = lambda place, a, b: any(place in f["places"] and a < f["to"] and b > f["from"] for f in forecasts)
    first_gig = {}
    for g in sorted(r["gigs"], key=lambda g: g["postedAt"]):
        for oid in gig_orders[g["id"]]:
            first_gig.setdefault(oid, g["id"])
    orows = []
    for oid, o in orders.items():
        req = requests[oid]; leg = req["legs"][0]; t = truth.get(oid, [{}])[0]
        pick, deliv = leg["pickup"]["placeId"], leg["delivery"]["placeId"]
        stated_p, real_p = leg["pickup"]["hours"], t.get("pickupHours")
        stated_d, real_d = leg["delivery"]["hours"], t.get("deliveryHours")
        orows.append(dict(
            v15=len({d for at, d in views.get(first_gig.get(oid), []) if at - first_post.get(oid, 0) <= 15}), v60=len({d for at, d in views.get(first_gig.get(oid), []) if at - first_post.get(oid, 0) <= 60}),
            id=oid, dealer=o["dealerId"], won=o["wonAt"], day=o["wonAt"] // DAY, option=o["option"], price=o["priceCents"], ref=req["referenceFeeCents"],
            list=next(x["listPriceCents"] for x in req["options"] if x["kind"] == o["option"]), last=o["lastPickupAt"], deadline=o["deadline"],
            late=oid in late_refund, refund=-late_refund.get(oid, 0), cancelled=oid in cancelled, post=first_post.get(oid), book=first_book.get(oid), lastbook=last_book.get(oid),
            drops=dropped.get(oid, 0), failed=failed.get(oid, 0), warned=warned.get(oid), fees=fees.get(oid, 0), near=near.get(pick, 0), near_to=near.get(deliv, 0),
            pick=pick, deliv=deliv, note=bool(req["note"]), notetext=req["note"], batch=req.get("batchId"), premium=leg["car"]["premium"], electric=leg["car"]["electric"],
            legs=len(req["legs"]), changed=len(changed.get(oid, [])), snow=snow(pick, o["wonAt"], o["deadline"]) or snow(deliv, o["wonAt"], o["deadline"]),
            ready_later=bool(t) and t.get("readyAt") is not None and t["readyAt"] > leg["pickup"]["window"]["from"], released=bool(t.get("releasedAt")),
            plates=bool(t.get("needsPlates")), manual=bool(t.get("manualGearbox")), tyres=bool(t.get("summerTyres")), notedeadline=t.get("noteDeadline"),
            hours_p=bool(real_p) and real_p != stated_p, hours_d=bool(real_d) and real_d != stated_d, picked=t.get("pickedUpAt"), delivered=t.get("deliveredAt"),
            readyAt=t.get("readyAt"), winfrom=leg["pickup"]["window"]["from"]))
    qrows = []
    for rid, req in requests.items():
        q = quoted.get(rid, {}); d = dec.get(rid, {})
        first = req["options"][0]
        price = (q.get("quote") or {}).get(first["kind"])
        z = x = None
        if not d.get("declined") and d.get("prices") and len(req["legs"]) == 1:
            options = [o for o in req["options"] if o["kind"] in d["prices"]]
            fast = curve.fastest(options)
            z = curve.at_list(req, options, trust_at[rid], model); x = math.log(d["prices"][fast["kind"]] / fast["listPriceCents"])
        qrows.append(dict(z=z, x=x, trust=trust_at[rid], id=rid, at=req["arrivedAt"], dealer=req["dealerId"], batch=req.get("batchId"), declined=d.get("declined"), outcome=q.get("outcome"),
                          ratio=price / first["listPriceCents"] if price else None, ref=req["referenceFeeCents"], list=first["listPriceCents"], pick=req["legs"][0]["pickup"]["placeId"],
                          private=any(l["pickup"]["privateAddress"] or l["delivery"]["privateAddress"] for l in req["legs"]), legs=len(req["legs"]), note=bool(req["note"])))
    # per day: gigs first posted that day, booked within an hour, viewers, views per gig in the first 15 minutes
    drows = []
    for day in range(8):
        posted = [o for o in orows if o["post"] is not None and o["post"] // DAY == day and o["post"] % DAY < 18 * HOUR]
        h1 = [o for o in posted if o["book"] is not None and o["book"] - o["post"] <= 60]
        drows.append(dict(day=day, posted=len(posted), h1=len(h1), viewers=len(viewers_day.get(day, ())),
                          late=sum(o["late"] for o in posted), near=sum(o["near"] for o in posted)))
    return dict(variant=r["variant"], seed=r["seed"], drivers=len(r["roster"]), score=r["score"], counts=dict(counts), offers=dict(offers), forecasts=forecasts,
                orders=orows, quotes=qrows, days=drows, near=near)


if __name__ == "__main__":
    data, out, variants = Path(sys.argv[1]), sys.argv[2], sys.argv[3:]
    paths = [str(p) for v in variants for p in sorted((data / "runs" / v).glob("*-L8.json.gz"))]
    with ProcessPoolExecutor(6) as pool:
        weeks = list(pool.map(week, paths, chunksize=2))
    json.dump(weeks, open(out, "w"))
    print(len(weeks), "weeks ->", out)
