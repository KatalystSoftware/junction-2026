"""The late orders of the reference: how many drivers looked before the last pickup minute, at what fee, and what the desk did.
PYTHONPATH=. uv run --with numpy python scratch/gap/late.py <data> <cache> <variant>"""
import sys, json, collections
import lib
data, cache, variant = sys.argv[1:4]
minutes = lib.minutes_of(json.load(open(f"{data}/map.json")))
weeks = lib.cached(data, variant, minutes, cache); n = len(weeks); DAY = 1440
rows = []
for w in weeks:
    views = collections.defaultdict(list)
    for v in w["views"]:
        for oid in w["gig_orders"].get(v["gigId"], []): views[oid].append(v)
    for o in w["orders"].values():
        if o["cancelled"] or len(o["request"]["legs"]) > 1: continue
        q = o["request"]; typ = q["referenceFeeCents"]; last = o["lastPickupAt"]
        vs = [v for v in views[o["id"]] if v["at"] <= last]
        first = min((b[0] for b in o["bookings"]), default=None)
        final = max(o["bookings"])[0] if o["bookings"] else None
        held_at_last = any(b[0] <= last and not any(b[0] < d[0] <= last for d in o["drops"]) for b in o["bookings"])
        cause = ("held by a driver at the last pickup minute (slow, failed visit or a tighter note)" if held_at_last else
                 "dropped and not booked again in time" if any(d[0] <= last for d in o["drops"]) else "never booked in time")
        rows.append({"late": o["late"], "cause": cause, "lookers": len({v["driverId"] for v in vs}), "maxfee": max((v["feeCents"] for v in vs), default=0) / typ,
                     "to_last": (last - o["wonAt"]) / 60, "refund": o["refund"], "price": o["price"], "wonhour": o["wonAt"] % DAY / 60, "fri": o["wonAt"] // DAY == 4,
                     "drive": minutes[(q["legs"][0]["pickup"]["placeId"], q["legs"][0]["delivery"]["placeId"])], "first": None if first is None else (first - o["wonAt"]) / 60,
                     "failed": o["failed"], "changed": o.get("changed", False), "note": q["note"] is not None})
late = [r for r in rows if r["late"]]
print(f"{len(late) / n:.1f} late orders a week of {len(rows) / n:.1f}; refund a late order {lib.mean(r['refund'] for r in late) / 100:.0f} euros, {100 * lib.mean(r['refund'] / r['price'] for r in late):.0f}% of its price")
g = collections.defaultdict(list)
for r in late: g[r["cause"]].append(r)
for k, v in sorted(g.items(), key=lambda kv: -len(kv[1])):
    print(f"\n{k}: {len(v) / n:.1f} a week; hours from win to last pickup: under 8 {100 * lib.mean(r['to_last'] < 8 for r in v):.0f}%, 8-24 {100 * lib.mean(8 <= r['to_last'] < 24 for r in v):.0f}%, over 24 {100 * lib.mean(r['to_last'] >= 24 for r in v):.0f}%;"
          f" drive over 400 min {100 * lib.mean(r['drive'] > 400 for r in v):.0f}%; won on Friday {100 * lib.mean(r['fri'] for r in v):.0f}%; failed visit {100 * lib.mean(r['failed'] > 0 for r in v):.0f}%; order changed {100 * lib.mean(r['changed'] for r in v):.0f}%; note {100 * lib.mean(r['note'] for r in v):.0f}%")
    c = collections.Counter("0" if r["lookers"] == 0 else "1-2" if r["lookers"] <= 2 else "3-9" if r["lookers"] <= 9 else "10-29" if r["lookers"] <= 29 else "30+" for r in v)
    print("   drivers who looked before the last pickup minute:", {k2: f"{100 * c[k2] / len(v):.0f}%" for k2 in ["0", "1-2", "3-9", "10-29", "30+"]},
          "| highest fee a driver saw, x typical: median %.2f" % sorted(r["maxfee"] for r in v)[len(v) // 2])
nb = [r for r in late if r["cause"] != "held by a driver at the last pickup minute (slow, failed visit or a tighter note)"]
print("\nlate without a driver at the last pickup minute, by hours from the win to that minute and the drive:")
for name, f in (("under 6 h", lambda r: r["to_last"] < 6), ("6-8 h", lambda r: 6 <= r["to_last"] < 8), ("8-24 h", lambda r: 8 <= r["to_last"] < 24), ("over 24 h", lambda r: r["to_last"] >= 24)):
    v = [r for r in nb if f(r)]
    print(f"  {name:10} {len(v) / n:4.1f} a week; drive over 400 min {100 * lib.mean(r['drive'] > 400 for r in v):3.0f}%; at most 2 lookers {100 * lib.mean(r['lookers'] <= 2 for r in v):3.0f}%; 10 or more lookers {100 * lib.mean(r['lookers'] >= 10 for r in v):3.0f}%; won after 14:00 {100 * lib.mean(r['wonhour'] >= 14 for r in v):3.0f}%")
ok = [r for r in rows if not r["late"]]
print("\nfor comparison, orders on time: at most 2 lookers %.0f%%, 10 or more %.0f%%" % (100 * lib.mean(r["lookers"] <= 2 for r in ok), 100 * lib.mean(r["lookers"] >= 10 for r in ok)))
