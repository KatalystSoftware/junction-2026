"""A second pass over saved weeks: (a) what the first days show of the week (warnings, late orders, booking speed);
(b) orders with snow forecast at the win; (c) an order's all-in cost by the drivers who live near its pickup and its
delivery; (d) what a late order costs in the dealer's trust count.

    SPREAD_DATA=... PYTHONPATH=spread python passes2.py out.json variant[,variant...]
"""
import gzip, json, sys, multiprocessing
from collections import defaultdict
from spreadlab.server import data_dir, near_places, drivers_near

DAY = 1440
MAP = json.loads((data_dir() / "map.json").read_text())
NEAR = near_places(MAP)


def band(n, cuts):
    return next((i for i, c in enumerate(cuts) if n < c), len(cuts))


def week(path):
    try:
        w = json.load(gzip.open(path))
    except Exception:
        return None
    ev, roster = w["events"], w["roster"]
    notified = drivers_near(roster, NEAR)
    req = {e["request"]["id"]: e["request"] for e in ev if e["kind"] == "price_request"}
    gig_orders = {g["id"]: sorted({s["orderId"] for s in g["stops"]}) for g in w["gigs"]}
    posted = {g["id"]: g["postedAt"] for g in w["gigs"]}
    booked_first = {}
    orders, cancelled = {}, set()
    money = defaultdict(lambda: defaultdict(int))
    daily = [defaultdict(int) for _ in range(10)]
    forecasts = []
    trust, trust_rows = defaultdict(int), []
    deliveries = defaultdict(list)  # dealer -> [(minute, on time?)]
    for e in ev:
        at, k = e["at"], e["kind"]
        d = min(at // DAY, 9)
        if k == "forecast":
            forecasts.append(e)
        elif k == "order_won":
            o = e["order"]
            leg = o["legs"][0]
            pk, dl = leg["pickup"]["placeId"], leg["delivery"]["placeId"]
            snow = any(set(f["placeIds"]) & {pk, dl} and f["from"] < o["deadline"] and f["to"] > at for f in forecasts)
            r = req.get(o["id"])
            kind = "trade_in" if len(o["legs"]) > 1 else "private" if leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"] else ""
            orders[o["id"]] = {"won": at, "last": o["lastPickupAt"], "deadline": o["deadline"], "price": o["priceCents"], "typ": r["referenceFeeCents"] if r else 0, "kind": kind,
                               "dealer": o["dealerId"], "snow": snow, "pb": band(notified.get(pk, 0), (10, 40, 100)), "db": band(notified.get(dl, 0), (10, 100)), "option": o["option"]}
            daily[d]["won"] += 1
        elif k == "order_cancelled":
            cancelled.add(e["orderId"])
        elif k == "deadline_close":
            daily[d]["warn"] += 1
        elif k == "gig_dropped":
            daily[d]["drops"] += 1
        elif k == "gig_booked":
            g = e["gigId"]
            if g not in booked_first:
                booked_first[g] = at
        elif k == "ledger":
            ln = e["line"]
            money[ln["orderId"]][ln["kind"]] += ln["cents"]
            o = orders.get(ln["orderId"])
            if ln["kind"] == "late_refund":
                daily[d]["late"] += 1
            if o and ln["kind"] == "revenue":
                deliveries[o["dealer"]].append((at, ln["orderId"]))
    late = {o for o, m in money.items() if m.get("late_refund") or m.get("undelivered_penalty")}
    for g, p in posted.items():
        d = min(p // DAY, 9)
        daily[d]["posted"] += 1
        daily[d]["fast"] += g in booked_first and booked_first[g] - p <= 30
    # (d) trust: the count as the rules give it, and what each late order takes from the dealer's later prices
    wins_by_dealer = defaultdict(list)
    for o, v in orders.items():
        if o not in cancelled:
            wins_by_dealer[v["dealer"]].append((v["won"], v["price"]))
    reqs_by_dealer = defaultdict(int)
    for r in req.values():
        reqs_by_dealer[r["dealerId"]] += 1
    top3 = {dd for dd, _ in sorted(reqs_by_dealer.items(), key=lambda kv: -kv[1])[:3]}
    for dealer, ds in deliveries.items():
        c = 0
        ds.sort()
        for i, (at, o) in enumerate(ds):
            if o in late:
                lost = c - c // 2
                c //= 2
                # the dealer's later wins pay `gap` % less until on-time deliveries win the count back
                gap, loss, later = lost, 0.0, [x for x in ds[i + 1:]]
                times = sorted([(t, "win", p) for t, p in wins_by_dealer[dealer] if t > at] + [(t, "del", oo) for t, oo in later])
                for t, what, x in times:
                    if gap <= 0:
                        break
                    if what == "win":
                        loss += x * gap / 100
                    elif x not in late:
                        gap -= 1
                trust_rows.append({"count": c + lost, "lost": lost, "loss": loss / 100, "top3": dealer in top3, "day": at // DAY})
            else:
                c = min(25, c + 1)
    cost = defaultdict(lambda: defaultdict(float))
    snow = defaultdict(lambda: [0, 0])
    for o, v in orders.items():
        if o in cancelled:
            continue
        m = money[o]
        snow[(v["snow"], v["kind"] == "")][0] += 1; snow[(v["snow"], v["kind"] == "")][1] += o in late
        if v["kind"] == "" and v["typ"]:
            hb = band((v["last"] - v["won"]) / 60, (8, 24))
            for key in (("pd", v["pb"], v["db"]), ("p", v["pb"]), ("d", v["db"]), ("ph", v["pb"], hb)):
                c = cost[str(key)]
                c["n"] += 1; c["typ"] += v["typ"]; c["fees"] -= m.get("driver_fee", 0); c["refund"] -= m.get("late_refund", 0) + m.get("undelivered_penalty", 0)
                c["other"] -= sum(x for kk, x in m.items() if kk not in ("revenue", "driver_fee", "late_refund", "undelivered_penalty")); c["price"] += v["price"]; c["late"] += o in late
    quotes = defaultdict(lambda: [0, 0])
    for rid, r in req.items():
        if len(r["legs"]) == 1 and not r["legs"][0]["pickup"]["privateAddress"] and not r["legs"][0]["delivery"]["privateAddress"]:
            leg = r["legs"][0]
            key = str(("pd", band(notified.get(leg["pickup"]["placeId"], 0), (10, 40, 100)), band(notified.get(leg["delivery"]["placeId"], 0), (10, 100))))
            quotes[key][0] += 1; quotes[key][1] += rid in orders
    n = sum(1 for o in orders if o not in cancelled)
    return {"variant": w["variant"], "seed": w["seed"], "drivers": len(roster), "orders": n, "late": sum(1 for o in orders if o not in cancelled and o in late),
            "daily": [dict(x) for x in daily[:6]], "late_by_won_day": [[sum(1 for o, v in orders.items() if o not in cancelled and v["won"] // DAY == dd), sum(1 for o, v in orders.items() if o not in cancelled and v["won"] // DAY == dd and o in late)] for dd in range(5)],
            "snow": {str(k): v for k, v in snow.items()}, "cost": {k: dict(v) for k, v in cost.items()}, "quotes": dict(quotes), "trust": trust_rows,
            "dealers": len(reqs_by_dealer), "top3_share": sum(reqs_by_dealer[dd] for dd in top3) / max(1, len(req)), "forecasts": len(forecasts)}


if __name__ == "__main__":
    out, variants = sys.argv[1], sys.argv[2].split(",")
    paths = [str(p) for v in variants for p in sorted((data_dir() / "runs" / v).glob("*-L8.json.gz"))]
    with multiprocessing.Pool(2) as pool:
        rows = [r for r in pool.imap_unordered(week, paths, chunksize=4) if r]
    json.dump(rows, open(out, "w"))
    print(len(rows), "weeks of", len(paths))
