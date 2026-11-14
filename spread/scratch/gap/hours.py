"""What an order costs by the time the desk has to find a driver, as known at the quote: from the answer to the last pickup
minute of the fastest option quoted. PYTHONPATH=. uv run --with numpy python scratch/gap/hours.py <data> <cache> <variant>..."""
import sys, json, collections
import lib
data, cache = sys.argv[1:3]
minutes = lib.minutes_of(json.load(open(f"{data}/map.json")))
SPEED = ["same_day", "next_day", "within_3_days"]; DAY = 1440
def hours(q, kinds):
    leg = q["legs"][0]
    fast = min((o for o in q["options"] if o["kind"] in kinds), key=lambda o: SPEED.index(o["kind"]))
    return (fast["deadline"] - minutes[(leg["pickup"]["placeId"], leg["delivery"]["placeId"])] - q["respondBy"]) / 60
cls = lambda h: "<6" if h < 6 else "6-8" if h < 8 else "8-12" if h < 12 else "12-30" if h < 30 else "30+"
C = ["<6", "6-8", "8-12", "12-30", "30+"]
for variant in sys.argv[3:]:
    weeks = lib.cached(data, variant, minutes, cache); n = len(weeks)
    g = collections.defaultdict(lambda: collections.Counter())
    for w in weeks:
        for rid, r in w["reqs"].items():
            dec = w["decisions"][rid]; q = r["request"]
            if dec["declined"] or lib.req_kind(q) != "dealer": continue
            c = g[cls(hours(q, dec["prices"]))]; c["quotes"] += 1
            o = w["orders"].get(rid)
            if o is None or o["cancelled"]: continue
            first = min((b[0] for b in o["bookings"]), default=None)
            c["won"] += 1; c["late"] += o["late"]; c["fees"] += o["fees"]; c["refund"] += o["refund"]; c["other"] += o["other"]; c["typ"] += q["referenceFeeCents"]; c["price"] += o["price"]
            c["hour"] += first is not None and first - o["wonAt"] <= 60; c["margin"] += o["margin"]
    print(f"\n== {variant}, {n} weeks\nhours to find a driver | quotes/wk | won/wk | win% | late% | booked in an hour% | fees/typ | (fees+refunds+other)/typ | with 100 euros of lost trust a late order | price/typ | margin/order")
    for k in C:
        c = g[k]
        if not c["won"]: continue
        full = (c["fees"] + c["refund"] + c["other"]) / c["typ"]
        print(f"  {k:6} {c['quotes'] / n:7.1f} {c['won'] / n:7.1f} {100 * c['won'] / c['quotes']:5.1f} {100 * c['late'] / c['won']:5.1f} {100 * c['hour'] / c['won']:6.1f} {c['fees'] / c['typ']:8.3f} {full:8.3f} {full + 10000 * c['late'] / c['typ']:8.3f} {c['price'] / c['typ']:8.3f} {c['margin'] / c['won'] / 100:7.1f}")
