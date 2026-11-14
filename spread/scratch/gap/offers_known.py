"""Direct offers by what the desk knew of the driver when it sent the offer (10 minutes before a no, up to 10 before a yes).
PYTHONPATH=. uv run --with numpy python scratch/gap/offers_known.py <data> <cache> <variant>..."""
import sys, json, collections
import lib
data, cache = sys.argv[1:3]
minutes = lib.minutes_of(json.load(open(f"{data}/map.json")))
DAY = 1440
for variant in sys.argv[3:]:
    weeks = lib.cached(data, variant, minutes, cache)
    n = len(weeks); rows = []
    for w in weeks:
        home = {d["id"]: d for d in w["roster"]}
        gig = {g["id"]: g for g in w["gigs"]}
        views = collections.defaultdict(list); books = collections.defaultdict(list); starts = collections.defaultdict(list); ends = collections.defaultdict(list)
        gig_driver = {}
        for e in w["ev"]["gig_viewed"]: views[e["driverId"]].append((e["at"], e["gigId"]))
        for e in w["ev"]["gig_booked"]: books[e["driverId"]].append((e["at"], e["gigId"]))
        for e in w["ev"]["gig_started"]: starts[e["driverId"]].append(e["at"]); gig_driver[e["gigId"]] = e["driverId"]
        for e in w["ev"]["delivered"]:
            d = gig_driver.get(e["gigId"])
            if d: ends[d].append(e["at"])
        for e in w["ev"]["offer_answered"]:
            g = gig.get(e["gigId"]); o = w["orders"].get(g["stops"][0]["orderId"]) if g else None
            if not o: continue
            d = e["driverId"]; sent = e["at"] - 10; day = e["at"] // DAY  # a yes comes sooner, so `sent` is then up to 10 minutes too early: that only hides knowledge
            leg = o["request"]["legs"][g["stops"][0]["leg"]]
            before = lambda v: [x for x in v if (x[0] if isinstance(x, tuple) else x) < sent]
            b_today = [x for x in before(books[d]) if x[0] // DAY == day and x[1] != e["gigId"]]
            b_week = [x for x in before(books[d]) if x[1] != e["gigId"]]
            drove_today = [x for x in before(starts[d]) if x // DAY == day]
            v_today = [x for x in before(views[d]) if x[0] // DAY == day]
            v_this = [x for x in before(views[d]) if x[1] == e["gigId"] or gig.get(x[1], {}).get("stops", [{}])[0].get("orderId") == o["id"]]
            state = "booked a gig today" if b_today else "drove a gig today" if drove_today else "booked earlier in the week" if b_week else "looked today, never booked" if v_today else "other"
            rows.append({"answer": e["answer"], "state": state, "hp": minutes.get((home[d]["homePlaceId"], leg["pickup"]["placeId"]), 0), "hour": e["at"] % DAY // 60,
                         "to_last": o["lastPickupAt"] - e["at"], "saw_this": bool(v_this), "views_today": len(v_today), "done": home[d]["completedGigs"],
                         "busy": any(s <= sent and not any(en > s and en <= sent for en in ends[d]) for s in drove_today)})
    acc = lambda v: sum(r["answer"] == "accepted" for r in v); read = lambda v: acc(v) + sum(r["answer"] == "declined" for r in v)
    print(f"\n== {variant}, {n} weeks: {len(rows) / n:.0f} offers a week, {acc(rows) / n:.1f} accepted")
    def table(name, key, order=None, rows=rows):
        g = collections.defaultdict(list)
        for r in rows: g[key(r)].append(r)
        print(f"{name:44} offers/wk  read%  accepted/wk  accepted% of all  of read")
        for k in (order or sorted(g)):
            v = g.get(k)
            if v: print(f"  {str(k):42} {len(v) / n:7.1f} {100 * read(v) / len(v):6.1f} {acc(v) / n:9.2f} {100 * acc(v) / len(v):12.2f} {100 * acc(v) / max(read(v), 1):10.1f}")
    table("what the desk knew of the driver", lambda r: r["state"])
    table("looked at this order's gig before", lambda r: r["saw_this"])
    table("on the road with a gig of ours", lambda r: r["busy"])
    table("driver's completed gigs (driver list)", lambda r: "0-9" if r["done"] < 10 else "10-49" if r["done"] < 50 else "50-199" if r["done"] < 200 else "200+", ["0-9", "10-49", "50-199", "200+"])
    good = [r for r in rows if r["state"] in ("booked a gig today", "drove a gig today", "booked earlier in the week")]
    table("known bookers: minutes home to pickup", lambda r: "0-30" if r["hp"] <= 30 else "31-60" if r["hp"] <= 60 else "61-120" if r["hp"] <= 120 else "121+", ["0-30", "31-60", "61-120", "121+"], good)
    table("known bookers: hour", lambda r: r["hour"] // 3 * 3, None, good)
    table("known bookers: hours to the last pickup", lambda r: "<0" if r["to_last"] < 0 else "0-3" if r["to_last"] < 180 else "3-6" if r["to_last"] < 360 else "6-8" if r["to_last"] < 480 else "8-24", ["<0", "0-3", "3-6", "6-8", "8-24"], good)
