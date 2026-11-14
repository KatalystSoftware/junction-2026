"""Late share and cost of won orders by what the request shows at the quote. PYTHONPATH=. uv run --with numpy python scratch/gap/flags.py <data> <cache> <variant>"""
import sys, json, collections
import lib
data, cache, variant = sys.argv[1:4]
map_ = json.load(open(f"{data}/map.json")); minutes = lib.minutes_of(map_); km = lib.km_of(map_)
weeks = lib.cached(data, variant, minutes, cache); n = len(weeks); DAY = 1440
rows = []
for w in weeks:
    exp_at = collections.Counter(); all_at = collections.Counter()
    for d in w["roster"]:
        all_at[d["homePlaceId"]] += 1
        if d["rating"] >= 4.8 and d["completedGigs"] >= 50: exp_at[d["homePlaceId"]] += 1
    places = [p["id"] for p in map_["places"]]
    near = {p: [x for x in places if minutes.get((x, p), 9999) <= 45] for p in places}
    truth = {o["orderId"]: o["legs"][0] for o in w["reveal"]["orders"]} if "reveal" in w else {}
    for o in w["orders"].values():
        if o["cancelled"] or len(o["request"]["legs"]) > 1: continue
        q = o["request"]; leg = q["legs"][0]; car = leg["car"]; pick = leg["pickup"]["placeId"]
        hrs = leg["pickup"]["hours"]; ready = max(leg["pickup"]["window"]["from"], o["wonAt"])
        rows.append({"late": o["late"], "premium": car["premium"], "electric": car["electric"], "low": car["electric"] and (car["chargePercent"] or 100) < 30, "note": q["note"] is not None,
                     "exp_near": sum(exp_at[x] for x in near[pick]), "all_near": sum(all_at[x] for x in near[pick]), "typ": q["referenceFeeCents"],
                     "cost": o["fees"] + o["refund"] + o["other"], "fees": o["fees"], "margin": o["margin"], "price": o["price"], "sat": hrs is not None and hrs.get("saturday") is None,
                     "ready_dow": ready // DAY, "last_dow": o["lastPickupAt"] // DAY, "drive": minutes[(pick, leg["delivery"]["placeId"])], "wondow": o["wonAt"] // DAY,
                     "first": min((b[0] for b in o["bookings"]), default=10**9) - o["wonAt"]})
def table(name, key, order=None, rows=rows):
    g = collections.defaultdict(list)
    for r in rows: g[key(r)].append(r)
    print(f"\n{name:44} orders/wk  late%  late/wk  booked in an hour%  fees/typ  cost/typ  price/typ  margin/order")
    for k in (order or sorted(g, key=str)):
        v = g.get(k)
        if v: print(f"  {str(k):42} {len(v) / n:7.1f} {100 * lib.mean(r['late'] for r in v):6.1f} {sum(r['late'] for r in v) / n:7.2f} {100 * lib.mean(r['first'] <= 60 for r in v):10.1f} {sum(r['fees'] for r in v) / sum(r['typ'] for r in v):12.3f} {sum(r['cost'] for r in v) / sum(r['typ'] for r in v):8.3f} {sum(r['price'] for r in v) / sum(r['typ'] for r in v):9.3f} {lib.mean(r['margin'] for r in v) / 100:9.1f}")
table("premium car (experienced drivers only)", lambda r: r["premium"])
prem = [r for r in rows if r["premium"]]
table("premium: experienced drivers within 45 min of the pickup", lambda r: "0-4" if r["exp_near"] < 5 else "5-14" if r["exp_near"] < 15 else "15-39" if r["exp_near"] < 40 else "40+", ["0-4", "5-14", "15-39", "40+"], prem)
table("not premium: drivers within 45 min of the pickup", lambda r: "0-9" if r["all_near"] < 10 else "10-29" if r["all_near"] < 30 else "30-99" if r["all_near"] < 100 else "100+", ["0-9", "10-29", "30-99", "100+"], [r for r in rows if not r["premium"]])
table("electric car", lambda r: "under 30% charge" if r["low"] else "electric" if r["electric"] else "no")
table("note", lambda r: r["note"])
table("drive", lambda r: "over 400 min" if r["drive"] > 400 else "300-400" if r["drive"] > 300 else "under 300", ["under 300", "300-400", "over 400 min"])
table("weekday of the win x last pickup on a later day", lambda r: f"{'Mon-Thu' if r['wondow'] < 4 else 'Fri'}, last pickup {'same day' if r['last_dow'] == r['wondow'] else 'next day' if r['last_dow'] == r['wondow'] + 1 else 'Sat-Mon' if r['wondow'] == 4 else 'later'}")
