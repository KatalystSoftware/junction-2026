"""One-car dealer requests whose delivery place has 100 or more drivers living within 30 km and whose pickup has under 40
("homeward": a driver ends the gig near home), against the other requests: share won, price asked, cost, late share.

    SPREAD_DATA=... PYTHONPATH=spread python homeward.py variant[,variant...]
"""
import gzip, json, sys, multiprocessing
from collections import defaultdict
from spreadlab.server import data_dir, near_places, drivers_near
MAP = json.loads((data_dir() / "map.json").read_text()); NEAR = near_places(MAP)
MIN = {(r["from"], r["to"]): r["minutes"] for r in MAP["roads"]}

def week(path):
    try: w = json.load(gzip.open(path))
    except Exception: return None
    ev = w["events"]; notified = drivers_near(w["roster"], NEAR)
    money = defaultdict(lambda: defaultdict(int)); won = {}; cancelled = set(); posted = {g["id"]: g["postedAt"] for g in w["gigs"]}; first_book = {}; gig_of = {}
    for g in w["gigs"]:
        for s in g["stops"]: gig_of.setdefault(s["orderId"], []).append(g["id"])
    for e in ev:
        k = e["kind"]
        if k == "ledger": money[e["line"]["orderId"]][e["line"]["kind"]] += e["line"]["cents"]
        elif k == "order_won": won[e["order"]["id"]] = e
        elif k == "order_cancelled": cancelled.add(e["orderId"])
        elif k == "gig_booked": first_book.setdefault(e["gigId"], e["at"])
    out = defaultdict(lambda: defaultdict(float))
    thin = len(w["roster"]) < 720
    for e in ev:
        if e["kind"] != "price_request": continue
        r = e["request"]
        if len(r["legs"]) != 1: continue
        leg = r["legs"][0]
        if leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"]: continue
        pk, dl = leg["pickup"]["placeId"], leg["delivery"]["placeId"]
        np_, nd = notified.get(pk, 0), notified.get(dl, 0)
        seg = "homeward (pickup under 40, delivery 100+)" if np_ < 40 and nd >= 100 else "outward (pickup 100+, delivery under 100)" if np_ >= 100 and nd < 100 else "city (both 100+)" if np_ >= 100 else "country (pickup under 100, delivery under 100)" if nd < 100 else "other"
        for key in ((seg, "all"), (seg, "thin" if thin else "not thin")):
            o = out[str(key)]
            o["requests"] += 1; o["typ"] += r["referenceFeeCents"]; o["drive"] += MIN.get((pk, dl), 0)
            dec = w["decisions"].get(r["id"]) or {}
            prices = dec.get("prices") or {}
            fast = min(r["options"], key=lambda x: x["deadline"])
            if fast["kind"] in prices:
                o["asked"] += 1; o["ask_list"] += prices[fast["kind"]] / fast["listPriceCents"]; o["ask_typ"] += prices[fast["kind"]] / r["referenceFeeCents"]; o["list_typ"] += fast["listPriceCents"] / r["referenceFeeCents"]
            if r["id"] in won and r["id"] not in cancelled:
                m = money[r["id"]]; ow = won[r["id"]]["order"]
                o["won"] += 1; o["price"] += ow["priceCents"]; o["wtyp"] += r["referenceFeeCents"]; o["fees"] -= m.get("driver_fee", 0)
                o["refund"] -= m.get("late_refund", 0) + m.get("undelivered_penalty", 0); o["late"] += bool(m.get("late_refund") or m.get("undelivered_penalty"))
                o["hours"] += (ow["lastPickupAt"] - won[r["id"]]["at"]) / 60
                gs = gig_of.get(r["id"], [])
                b = min((first_book[g] for g in gs if g in first_book), default=None)
                if b is not None and gs: o["booked"] += 1; o["wait"] += b - min(posted[g] for g in gs); o["fast"] += b - min(posted[g] for g in gs) <= 60
    return {k: dict(v) for k, v in out.items()}

if __name__ == "__main__":
    paths = [str(p) for v in sys.argv[1].split(",") for p in sorted((data_dir() / "runs" / v).glob("*-L8.json.gz"))]
    with multiprocessing.Pool(2) as pool: rows = [r for r in pool.imap_unordered(week, paths, chunksize=4) if r]
    W = len(rows); tot = defaultdict(lambda: defaultdict(float))
    for r in rows:
        for k, v in r.items():
            for kk, vv in v.items(): tot[k][kk] += vv
    print(f"{W} weeks of {sys.argv[1][:60]}")
    for k in sorted(tot):
        v = tot[k]; seg, which = eval(k)
        print(f"{which:8s} {seg:48s} requests {v['requests'] / W:6.1f}  won {v['won'] / v['requests']:.1%} ({v['won'] / W:5.1f} a week)  typical fee {v['typ'] / v['requests'] / 100:5.1f}  drive {v['drive'] / v['requests']:4.0f} min  asked {v['ask_typ'] / max(v['asked'], 1):.2f} x typ ({v['ask_list'] / max(v['asked'], 1):.2f} x list; list is {v['list_typ'] / max(v['asked'], 1):.2f} x typ)"
              f"  won at {v['price'] / max(v['wtyp'], 1):.2f}  fees {v['fees'] / max(v['wtyp'], 1):.3f}  refunds {v['refund'] / max(v['wtyp'], 1):.3f}  late {v['late'] / max(v['won'], 1):.2%}  hours to last pickup {v['hours'] / max(v['won'], 1):.0f}  booked within the hour {v['fast'] / max(v['booked'], 1):.0%}  margin an order {(v['price'] - v['fees'] - v['refund']) / max(v['won'], 1) / 100:.1f}")
