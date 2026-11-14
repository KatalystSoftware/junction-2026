"""How won orders find a driver, by how far ahead the pickup is. PYTHONPATH=. uv run --with numpy python scratch/gap/orders.py <data> <cache> <variant>"""
import sys, json, collections
import lib
data, cache, variant = sys.argv[1:4]
minutes = lib.minutes_of(json.load(open(f"{data}/map.json")))
weeks = lib.cached(data, variant, minutes, cache)
n = len(weeks); DAY = 1440
rows = []
for wi, w in enumerate(weeks):
    home = {d["id"]: d["homePlaceId"] for d in w["roster"]}
    for o in w["orders"].values():
        if o["cancelled"] or len(o["request"]["legs"]) > 1: continue
        q = o["request"]; leg = q["legs"][0]
        ready = max(leg["pickup"]["window"]["from"], o["wonAt"])
        first = min((b[0] for b in o["bookings"]), default=None)
        last = max(o["bookings"], default=None)
        rows.append({"w": wi, "won": o["wonAt"], "ready": leg["pickup"]["window"]["from"], "lead_days": leg["pickup"]["window"]["from"] // DAY - o["wonAt"] // DAY,
                     "slack": o["lastPickupAt"] - ready, "to_last": o["lastPickupAt"] - o["wonAt"], "first": None if first is None else first - o["wonAt"],
                     "final": None if last is None else last[0] - o["wonAt"], "final_before_last": None if last is None else o["lastPickupAt"] - last[0],
                     "drops": len(o["drops"]), "late": o["late"], "fee": o["fees"] / q["referenceFeeCents"], "typ": q["referenceFeeCents"], "option": o["option"],
                     "margin": o["margin"], "drive": minutes[(leg["pickup"]["placeId"], leg["delivery"]["placeId"])], "price": o["price"],
                     "booker_home": None if last is None else ("pickup" if home[last[1]] == leg["pickup"]["placeId"] else "delivery" if home[last[1]] == leg["delivery"]["placeId"] else "other"),
                     "wonhour": o["wonAt"] % DAY // 60, "failed": o["failed"]})
def table(name, key, order=None):
    g = collections.defaultdict(list)
    for r in rows: g[key(r)].append(r)
    print(f"\n{name:28} orders/wk  late%  booked<=15m <=60m  never  final booking after last pickup%  drops/order  fee/typ  margin/order")
    for k in (order or sorted(g)):
        v = g[k]
        if not v: continue
        f = lambda t: 100 * lib.mean(r["first"] is not None and r["first"] <= t for r in v)
        print(f"{str(k):28} {len(v) / n:8.1f} {100 * lib.mean(r['late'] for r in v):6.1f} {f(15):9.1f} {f(60):6.1f} {100 * lib.mean(r['first'] is None for r in v):6.1f}"
              f" {100 * lib.mean(r['final_before_last'] is None or r['final_before_last'] < 0 for r in v):12.1f} {lib.mean(r['drops'] for r in v):18.2f} {lib.mean(r['fee'] for r in v):8.3f} {lib.mean(r['margin'] for r in v) / 100:8.1f}")
print(variant, n, "weeks,", len(rows) / n, "one-car orders a week")
table("pickup day - win day", lambda r: min(r["lead_days"], 3))
table("option", lambda r: r["option"])
table("hours from win to last pickup", lambda r: "<6" if r["to_last"] < 360 else "6-8" if r["to_last"] < 480 else "8-12" if r["to_last"] < 720 else "12-24" if r["to_last"] < 1440 else "24-48" if r["to_last"] < 2880 else "48+", ["<6", "6-8", "8-12", "12-24", "24-48", "48+"])
table("hour of the win", lambda r: r["wonhour"] // 2 * 2)
table("drive minutes", lambda r: "<120" if r["drive"] < 120 else "120-240" if r["drive"] < 240 else "240-400" if r["drive"] < 400 else "400+", ["<120", "120-240", "240-400", "400+"])
table("home of the final driver", lambda r: r["booker_home"] or "none")
table("weekday of the win", lambda r: r["won"] // DAY)
late = [r for r in rows if r["late"]]
print("\nlate orders/wk %.1f: never booked %.1f, final booking after last pickup %.1f, dropped at least once %.1f, failed visit %.1f" % (
    len(late) / n, sum(r["first"] is None for r in late) / n, sum(r["final_before_last"] is not None and r["final_before_last"] < 0 for r in late) / n,
    sum(r["drops"] > 0 for r in late) / n, sum(r["failed"] > 0 for r in late) / n))
import pickle; pickle.dump(rows, open(f"{cache}/orders-{variant}.pkl", "wb"))
