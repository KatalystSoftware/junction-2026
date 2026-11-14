"""The bulk order (requests with a batch id) and the events the desk does not act on. PYTHONPATH=. uv run --with numpy python scratch/gap/bulk.py <data> <cache> <variant>"""
import sys, json, collections
import lib
data, cache, variant = sys.argv[1:4]
minutes = lib.minutes_of(json.load(open(f"{data}/map.json")))
weeks = lib.cached(data, variant, minutes, cache); n = len(weeks)
c = collections.Counter(); kinds = collections.Counter(); sizes = []
for w in weeks:
    batches = collections.defaultdict(list)
    for rid, r in w["reqs"].items():
        if r["request"].get("batchId"): batches[r["request"]["batchId"]].append(rid)
    for k in w["ev"]: kinds[k] += len(w["ev"][k])
    for b, rids in batches.items():
        sizes.append(len(rids))
        for rid in rids:
            r = w["reqs"][rid]; dec = w["decisions"][rid]; o = w["orders"].get(rid)
            c["requests"] += 1; c["declined: " + str(dec["declined"])] += dec["declined"] is not None; c["quoted"] += dec["declined"] is None
            if o and not o["cancelled"]:
                c["won"] += 1; c["late"] += o["late"]; c["margin"] += o["margin"]; c["fees"] += o["fees"]; c["typ"] += r["request"]["referenceFeeCents"]
    big = [rids for rids in batches.values() if len(rids) >= 20]
    for rids in big:
        won = [w["orders"][x] for x in rids if x in w["orders"] and not w["orders"][x]["cancelled"]]
        c["bulk orders"] += 1; c["bulk requests"] += len(rids); c["bulk won"] += len(won); c["bulk late"] += sum(o["late"] for o in won); c["bulk margin"] += sum(o["margin"] for o in won)
        c["bulk quoted"] += sum(w["decisions"][x]["declined"] is None for x in rids); c["bulk gated"] += sum(w["decisions"][x]["declined"] == "backlog" for x in rids)
        dealers = {w["reqs"][x]["request"]["dealerId"] for x in rids}; pickups = {w["reqs"][x]["request"]["legs"][0]["pickup"]["placeId"] for x in rids}
        c["bulk one pickup place"] += len(pickups) == 1
print("batch sizes:", collections.Counter("1" if s == 1 else "2-5" if s <= 5 else "6-19" if s < 20 else "20+" for s in sizes))
print({k: round(v / n, 2) for k, v in c.items()})
if c["won"]: print("batch orders: late %.1f%%, fees/typ %.3f, margin/order %.1f" % (100 * c["late"] / c["won"], c["fees"] / c["typ"], c["margin"] / c["won"] / 100))
if c["bulk won"]: print("bulk order: won %.1f of %.1f requests a week (%.1f quoted, %.1f gated), late %.1f%%, margin/order %.1f" % (c["bulk won"] / n, c["bulk requests"] / n, c["bulk quoted"] / n, c["bulk gated"] / n, 100 * c["bulk late"] / c["bulk won"], c["bulk margin"] / c["bulk won"] / 100))
print("events a week:", {k: round(v / n, 1) for k, v in kinds.items() if k not in ("price_request", "gig_viewed", "ledger")})
