"""Scratch: what a won car's driver fees were, against what the policy can see when it quotes."""
import collections, glob, json, os, statistics, sys
from spreadlab import ledger
from spreadlab.play import load_run
from spreadlab.server import data_dir, drivers_near, near_places, world_map

map_ = world_map()
near = near_places(map_)
minutes = {(r["from"], r["to"]): r["minutes"] for r in map_["roads"]}
km = {(r["from"], r["to"]): r["km"] for r in map_["roads"]}
rows = []
for path in sorted(glob.glob(str(data_dir() / "runs" / "*" / "*-L8.json.gz"))):
    variant, seed = path.split("/")[-2], path.split("/")[-1][:-len("-L8.json.gz")]
    if variant == "decline-all":
        continue
    run = load_run(variant, seed)
    played = ledger.week(run, near)
    notified = drivers_near(run["roster"], near)
    requests = {r["request"]["id"]: r["request"] for r in run["reveal"]["requests"]}
    cars = sum(len(r["legs"]) for r in requests.values())
    for id_, row in played["requests"].items():
        if row["outcome"] != "won":
            continue
        q = requests[id_]
        leg = q["legs"][0]
        option = next(o for o in q["options"] if o["kind"] == row["option"])
        a, b = leg["pickup"]["placeId"], leg["delivery"]["placeId"]
        rows.append({"variant": variant, "seed": seed, "id": id_, "ref": q["referenceFeeCents"], "list": option["listPriceCents"], "price": row["price"],
                     "fees": row["fees"], "costs": row["costs"], "late": row["late"], "onTime": row["onTime"], "option": row["option"], "situation": row["situation"],
                     "notified": notified[a], "notifiedDelivery": notified[b], "minutes": minutes[(a, b)], "km": km[(a, b)], "legs": len(q["legs"]),
                     "slack": option["deadline"] - minutes[(a, b)] - max(q["respondBy"], leg["pickup"]["window"]["from"]),
                     "day": q["arrivedAt"] // 1440, "hour": q["arrivedAt"] % 1440 // 60, "weekTight": cars / len(run["roster"]),
                     "premium": leg["car"]["premium"], "note": q["note"] is not None})
json.dump(rows, open(sys.argv[1], "w"))
print(len(rows), "won orders")
print(json.dumps(rows[0]))
