"""One pass over saved weeks: (1) the night's first-hour drops (the flu day) and what ends late on that day, by where the car
stood at midnight; (2) what the desk can see of its own drivers' positions: bookings and direct offers by whether the driver
had just delivered one of the desk's cars near the pickup.

    SPREAD_DATA=... PYTHONPATH=spread python passes.py out.json variant[,variant...]
"""
import gzip, json, sys, multiprocessing
from collections import defaultdict
from spreadlab.server import data_dir, near_places

DAY = 1440
MAP = json.loads((data_dir() / "map.json").read_text())
NEAR = near_places(MAP)


def week(path):
    try:
        w = json.load(gzip.open(path))
    except Exception:
        return None
    ev = w["events"]
    home = {d["id"]: d["homePlaceId"] for d in w["roster"]}
    req = {e["request"]["id"]: e["request"] for e in ev if e["kind"] == "price_request"}
    gig_orders = {g["id"]: sorted({s["orderId"] for s in g["stops"]}) for g in w["gigs"]}
    posted = {g["id"]: g["postedAt"] for g in w["gigs"]}
    late, cancelled = set(), set()
    for e in ev:
        if e["kind"] == "ledger" and e["line"]["kind"] in ("late_refund", "undelivered_penalty"):
            late.add(e["line"]["orderId"])
        elif e["kind"] == "order_cancelled":
            cancelled.add(e["orderId"])
    orders, holder, picked, delivered_at = {}, {}, {}, {}
    drops_first = defaultdict(list)      # day -> orders dropped in its first hour
    snaps = {}                           # day -> {order: held?} at 00:00 for the cars not yet collected
    last_delivery = {}                   # driver -> (minute, place) of the last car of the desk they delivered
    books, offers, chances = [], [], []
    open_gigs = {}                       # gig -> posted and unbooked
    offer_sent = {}
    next_day = 1
    for e in ev:
        at, k = e["at"], e["kind"]
        while next_day <= 4 and at >= next_day * DAY:
            snaps[next_day] = {o: (o in holder) for o in orders if o not in picked and o not in cancelled}
            next_day += 1
        if k == "order_won":
            o = e["order"]
            orders[o["id"]] = {"won": at, "last": o["lastPickupAt"], "deadline": o["deadline"], "option": o["option"], "legs": len(o["legs"]),
                               "pickup": o["legs"][0]["pickup"]["placeId"], "delivery": o["legs"][0]["delivery"]["placeId"], "fee": req[o["id"]]["referenceFeeCents"] if o["id"] in req else 0}
        elif k == "order_changed":
            o = e["order"]
            if o["id"] in orders:
                orders[o["id"]]["last"] = o["lastPickupAt"]
        elif k == "gig_booked":
            g, d = e["gigId"], e["driverId"]
            os_ = gig_orders.get(g, [])
            for o in os_:
                holder[o] = d
            if len(os_) == 1 and os_[0] in orders:
                o = orders[os_[0]]
                ld = last_delivery.get(d)
                near = bool(ld and ld[0] // DAY == at // DAY and at - ld[0] <= 240 and o["pickup"] in NEAR.get(ld[1], ()))
                books.append({"near": near, "ratio": e["feeCents"] / o["fee"] if o["fee"] else None, "wait": at - posted.get(g, at), "late": os_[0] in late,
                              "hours": (o["last"] - at) / 60, "home_pickup": o["pickup"] in NEAR.get(home.get(d), ()), "home_delivery": o["delivery"] in NEAR.get(home.get(d), ())})
        elif k in ("gig_dropped", "no_show"):
            for o in gig_orders.get(e["gigId"], []):
                holder.pop(o, None)
                if k == "gig_dropped" and at % DAY < 60:
                    drops_first[at // DAY].append(o)
        elif k == "picked_up":
            picked[e["orderId"]] = at
        elif k == "delivered":
            delivered_at[e["orderId"]] = at
            d = holder.get(e["orderId"])
            if d:
                last_delivery[d] = (at, e["placeId"])
                # the desk's cars without a driver, posted, that this driver could take from here: pickup within 30 km of where they stand
                here = NEAR.get(e["placeId"], ())
                cands = [o for o, v in orders.items() if o not in holder and o not in picked and o not in cancelled and v["legs"] == 1 and v["won"] < at and v["pickup"] in here
                         and v["last"] >= at + 30]
                today = [o for o in cands if orders[o]["last"] // DAY == at // DAY]
                homeward = [o for o in cands if orders[o]["delivery"] in NEAR.get(home.get(d), ())]
                chances.append({"n": len(cands), "today": len(today), "homeward": len(homeward), "hour": at % DAY // 60,
                                "late_any": any(o in late for o in cands), "late_today": sum(o in late for o in today)})
        elif k == "offer_answered":
            g, d = e["gigId"], e["driverId"]
            os_ = gig_orders.get(g, [])
            if len(os_) == 1 and os_[0] in orders:
                o = orders[os_[0]]
                ld = last_delivery.get(d)
                sent = at - (0 if e["answer"] == "accepted" else 10)
                near = bool(ld and ld[0] // DAY == sent // DAY and sent - ld[0] <= 240 and o["pickup"] in NEAR.get(ld[1], ()))
                worked = bool(ld and ld[0] // DAY == sent // DAY)
                offers.append({"near": near, "worked": worked, "answer": e["answer"], "homeward": o["delivery"] in NEAR.get(home.get(d), ())})
    days = []
    for day in range(1, 5):
        snap = snaps.get(day, {})
        dropped = set(drops_first.get(day, []))
        cat = defaultdict(lambda: [0, 0])
        for o, held in snap.items():
            v = orders[o]
            due = v["last"] // DAY
            c = ("held due today dropped" if o in dropped else "held due today kept") if held and due == day else "waiting due today" if due == day else \
                ("held later dropped" if o in dropped else "held later") if held else "waiting later"
            cat[c][0] += 1; cat[c][1] += o in late
        for o, v in orders.items():
            if v["won"] // DAY == day and o not in cancelled:
                c = "won today due today" if v["last"] // DAY == day else "won today due next day" if v["last"] // DAY == day + 1 else "won today due later"
                cat[c][0] += 1; cat[c][1] += o in late
        held_today = sum(1 for o, h in snap.items() if h and orders[o]["last"] // DAY == day)
        days.append({"day": day, "drops": len(dropped), "held_today": held_today, "cat": dict(cat)})
    n = sum(1 for o in orders if o not in cancelled)
    nl = sum(1 for o in orders if o not in cancelled and o in late)
    def agg(rows, key):
        out = defaultdict(lambda: defaultdict(float))
        for r in rows:
            b = out[key(r)]
            b["n"] += 1
            for kk, vv in r.items():
                if isinstance(vv, (int, float, bool)) and vv is not None:
                    b[kk] += vv
        return {str(k): dict(v) for k, v in out.items()}
    return {"variant": w["variant"], "seed": w["seed"], "drivers": len(w["roster"]), "orders": n, "late": nl, "margin": w["score"]["marginCents"] / 100, "days": days,
            "books": agg([b for b in books if b["ratio"]], lambda b: b["near"]), "offers": agg(offers, lambda r: (r["near"], r["worked"], r["answer"])),
            "chances": {"deliveries": len(chances), "with_any": sum(c["n"] > 0 for c in chances), "with_today": sum(c["today"] > 0 for c in chances),
                        "with_homeward": sum(c["homeward"] > 0 for c in chances), "late_today": sum(c["late_today"] for c in chances)}}


if __name__ == "__main__":
    out, variants = sys.argv[1], sys.argv[2].split(",")
    paths = [str(p) for v in variants for p in sorted((data_dir() / "runs" / v).glob("*-L8.json.gz"))]
    with multiprocessing.Pool(2) as pool:
        rows = [r for r in pool.imap_unordered(week, paths, chunksize=4) if r]
    json.dump(rows, open(out, "w"))
    print(len(rows), "weeks of", len(paths))
