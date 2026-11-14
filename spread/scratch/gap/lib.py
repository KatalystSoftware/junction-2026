"""Loads saved weeks (spread/data/runs/<variant>/<seed>-L8.json.gz) into per-request and per-order rows.
Offline only: reads files, plays nothing. The scripts beside it take the data folder as an argument (see README.md)."""
import gzip, json, os, pickle, collections

DAY, HOUR = 1440, 60

def load(path):
    with gzip.open(path) as f:
        return json.load(f)

def runs(data, variant, prefixes=("fresh-", "cat-")):
    folder = os.path.join(data, "runs", variant)
    out = []
    for name in sorted(os.listdir(folder)):
        if name.endswith(".json.gz") and name.startswith(tuple(prefixes)):
            out.append(os.path.join(folder, name))
    return out

def minutes_of(map_):
    return {(r["from"], r["to"]): r["minutes"] for r in map_["roads"]}

def km_of(map_):
    return {(r["from"], r["to"]): r["km"] for r in map_["roads"]}

def week(path, minutes):
    """One week as dict: requests rows, orders rows, events by kind, roster."""
    d = load(path)
    ev = collections.defaultdict(list)
    for e in d["events"]:
        ev[e["kind"]].append(e)
    reqs = {r["request"]["id"]: r for r in d["reveal"]["requests"]}
    gig_orders = {}
    for g in d["gigs"]:
        gig_orders[g["id"]] = sorted({s["orderId"] for s in g["stops"]})
    orders = {}
    for e in ev["order_won"]:
        o = e["order"]
        orders[o["id"]] = {"id": o["id"], "wonAt": e["at"], "option": o["option"], "price": o["priceCents"], "deadline": o["deadline"],
                           "lastPickupAt": o["lastPickupAt"], "dealer": o["dealerId"], "gigs": [], "bookings": [], "drops": [], "fees": 0,
                           "refund": 0, "other": 0, "revenue": 0, "cancelled": False, "failed": 0, "warned": None, "delivered": None, "pickedUp": None}
    for e in ev["order_changed"]:
        o = e["order"]
        if o["id"] in orders:
            orders[o["id"]]["deadline"] = o["deadline"]
            orders[o["id"]]["changed"] = True
    for e in ev["order_cancelled"]:
        if e["orderId"] in orders:
            orders[e["orderId"]]["cancelled"] = True
    for g in d["gigs"]:
        for oid in gig_orders[g["id"]]:
            if oid in orders:
                orders[oid]["gigs"].append(g)
    for e in ev["gig_booked"]:
        for oid in gig_orders.get(e["gigId"], []):
            if oid in orders:
                orders[oid]["bookings"].append((e["at"], e["driverId"], e["feeCents"], e["gigId"]))
    for kind in ("gig_dropped", "no_show"):
        for e in ev[kind]:
            for oid in gig_orders.get(e["gigId"], []):
                if oid in orders:
                    orders[oid]["drops"].append((e["at"], e["driverId"], kind))
    for e in ev["visit_failed"]:
        if e["orderId"] in orders:
            orders[e["orderId"]]["failed"] += 1
    for e in ev["deadline_close"]:
        if e["orderId"] in orders and orders[e["orderId"]]["warned"] is None:
            orders[e["orderId"]]["warned"] = e["at"]
    for e in ev["picked_up"]:
        if e["orderId"] in orders and orders[e["orderId"]]["pickedUp"] is None:
            orders[e["orderId"]]["pickedUp"] = e["at"]
    for e in ev["delivered"]:
        if e["orderId"] in orders:
            orders[e["orderId"]]["delivered"] = e["at"]
    ledger_kinds = collections.Counter()
    for e in ev["ledger"]:
        line = e["line"]
        ledger_kinds[line["kind"]] += line["cents"]
        oid = line.get("orderId")
        if oid is None and line.get("gigId") in gig_orders and len(gig_orders[line["gigId"]]) == 1:
            oid = gig_orders[line["gigId"]][0]
        if oid in orders:
            o = orders[oid]
            if line["kind"] == "revenue":
                o["revenue"] += line["cents"]
            elif line["kind"] == "driver_fee":
                o["fees"] += -line["cents"]
            elif line["kind"] in ("late_refund", "undelivered_penalty"):
                o["refund"] += -line["cents"]
            else:
                o["other"] += -line["cents"]
    for o in orders.values():
        r = reqs[o["id"]]["request"]
        o["request"] = r
        o["late"] = o["refund"] > 0 or (o["delivered"] is None and not o["cancelled"])
        o["margin"] = o["revenue"] - o["fees"] - o["refund"] - o["other"]
    return {"path": path, "seed": d["seed"], "variant": d["variant"], "score": d["score"], "reqs": reqs, "orders": orders, "ev": ev,
            "roster": d["roster"], "decisions": d["decisions"], "views": d["reveal"]["views"], "gigs": d["gigs"], "gig_orders": gig_orders,
            "ledger": dict(ledger_kinds), "params": d["params"]}

def cached(data, variant, minutes, cache, prefixes=("fresh-", "cat-")):
    os.makedirs(cache, exist_ok=True)
    p = os.path.join(cache, f"{variant}-{'_'.join(prefixes)}.pkl")
    if os.path.exists(p):
        with open(p, "rb") as f:
            return pickle.load(f)
    weeks = [week(path, minutes) for path in runs(data, variant, prefixes)]
    with open(p, "wb") as f:
        pickle.dump(weeks, f)
    return weeks

def req_kind(r):
    if len(r["legs"]) > 1:
        return "trade_in"
    leg = r["legs"][0]
    return "private_pickup" if leg["pickup"]["privateAddress"] else "private_delivery" if leg["delivery"]["privateAddress"] else "dealer"

def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")
