"""Trade-in gigs (two cars, one gig) in the played weeks: what drivers took for them against one-car fees.
usage: tradein.py <data dir> <variant> [<variant> ...]"""
import gzip, json, glob, sys, statistics as st, math
data = sys.argv[1]
roads = {(r["from"], r["to"]): r["minutes"] for r in json.load(open(f"{data}/map.json"))["roads"]}
rows = []
singles = []
for v in sys.argv[2:]:
    for f in sorted(glob.glob(f"{data}/runs/{v}/*.json.gz")):
        d = json.load(gzip.open(f))
        req = {r["request"]["id"]: r for r in d["reveal"]["requests"]}
        late = set()
        for e in d["events"]:
            if e["kind"] == "ledger" and e["line"]["kind"] in ("late_refund", "undelivered_penalty") and e["line"].get("orderId"):
                late.add(e["line"]["orderId"])
        for g in d["gigs"]:
            orders = {s["orderId"] for s in g["stops"]}
            cars = len({(s["orderId"], s["leg"]) for s in g["stops"]})
            if g["status"] not in ("done", "completed", "delivered", "finished") and not g.get("driverId"):
                continue
            oid = next(iter(orders))
            if oid not in req: continue
            r = req[oid]["request"]
            ref = r["referenceFeeCents"]
            first = g["schedule"][0]["feeCents"]
            if len(r["legs"]) == 2 and cars == 2:
                legs = r["legs"]
                d1 = roads[(legs[0]["pickup"]["placeId"], legs[0]["delivery"]["placeId"])]
                d2 = roads[(legs[1]["pickup"]["placeId"], legs[1]["delivery"]["placeId"])]
                rows.append((g["feeCents"] / ref, first / ref, ref, d1 + d2, oid in late, g["status"], v))
            elif len(r["legs"]) == 1 and cars == 1 and not r["legs"][0]["pickup"]["privateAddress"] and not r["legs"][0]["delivery"]["privateAddress"]:
                leg = r["legs"][0]
                singles.append((g["feeCents"] / ref, ref, roads[(leg["pickup"]["placeId"], leg["delivery"]["placeId"])]))
print("statuses", {s: sum(1 for r in rows if r[5] == s) for s in {r[5] for r in rows}})
print("trade-in two-car gigs with a driver:", len(rows))
if rows:
    print(" paid/ref mean %.2f median %.2f ; opening/ref mean %.2f ; late %.1f%%" % (st.mean(r[0] for r in rows), st.median(r[0] for r in rows), st.mean(r[1] for r in rows), 100 * st.mean(r[4] for r in rows)))
    print(" ref cents per drive minute (trade-in, two legs): %.1f" % (sum(r[2] for r in rows) / sum(r[3] for r in rows)))
    print(" paid cents per drive minute (trade-in): %.1f" % (sum(r[0] * r[2] for r in rows) / sum(r[3] for r in rows)))
    booked_open = [r for r in rows if abs(r[0] - r[1]) < 0.01]
    print(" booked at the opening fee: %d of %d, opening/ref there %.2f" % (len(booked_open), len(rows), st.mean(r[1] for r in booked_open) if booked_open else 0))
print("one-car dealer gigs:", len(singles))
print(" paid/ref mean %.2f ; ref cents per drive minute %.1f ; paid cents per drive minute %.1f" % (st.mean(s[0] for s in singles), sum(s[1] for s in singles) / sum(s[2] for s in singles), sum(s[0] * s[1] for s in singles) / sum(s[2] for s in singles)))
