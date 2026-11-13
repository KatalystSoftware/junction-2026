"""Scratch: one row per serious quote in every saved week, with only what the desk sees at that minute, and the outcome."""
import collections, glob, json, os, sys
from spreadlab import ledger
from spreadlab.play import load_run
from spreadlab.server import data_dir, drivers_near, near_places, world_map
near = near_places(world_map())
out = []
for path in sorted(glob.glob(str(data_dir() / "runs" / "*" / "*-L8.json.gz"))):
    variant, seed = path.split("/")[-2], path.split("/")[-1][:-len("-L8.json.gz")]
    if variant == "decline-all": continue
    run = load_run(variant, seed); played = ledger.week(run, near)
    notified = drivers_near(run["roster"], near)
    order_of = {g["id"]: g["stops"][0]["orderId"] for g in run["gigs"]}
    reqs = sorted((r["request"] for r in run["reveal"]["requests"]), key=lambda q: (q["arrivedAt"], q["id"]))
    backlog = {}; open_ = {}; i = 0
    for e in run["events"]:
        while i < len(reqs) and reqs[i]["arrivedAt"] <= e["at"]:
            backlog[reqs[i]["id"]] = len(open_); i += 1
        k = e["kind"]
        if k == "order_won": open_[e["order"]["id"]] = 1
        elif k == "gig_booked": open_.pop(order_of.get(e["gigId"]), None)
        elif k in ("gig_dropped", "no_show"): open_.setdefault(order_of.get(e["gigId"]), 1)
        elif k in ("delivered", "order_cancelled"): open_.pop(e["orderId"], None)
    for q in reqs[i:]: backlog[q["id"]] = len(open_)
    known = []  # (respondBy, day, dealer, won) of earlier serious quotes
    seen = collections.Counter(); total = 0
    for q in reqs:
        d = run["decisions"][q["id"]]; row = played["requests"][q["id"]]
        day = q["arrivedAt"] // 1440; dealer = q["dealerId"]
        seen[dealer] += 1; total += 1
        if d["declined"]: continue
        past = [k for k in known if k[0] <= q["arrivedAt"]]
        def rate(sel):
            b = [k[3] for k in past if sel(k)]
            return (len(b), sum(b) / len(b) if b else None)
        o = {o["kind"]: o for o in q["options"]}
        won = row["outcome"] == "won"
        leg = q["legs"][0]
        f = dict(variant=variant, seed=seed, id=q["id"], won=won, margin=(row["price"] - row["fees"] - row["costs"] - row["late"]) / 100 if won else 0.0,
                 late=(not row["onTime"]) if won else None,
                 qlist=min(p / o[k]["listPriceCents"] for k, p in d["prices"].items()), qref=min(d["prices"].values()) / q["referenceFeeCents"],
                 reflist=q["referenceFeeCents"] / q["options"][0]["listPriceCents"], ref=q["referenceFeeCents"] / 100, same_day="same_day" in d["prices"], options=len(d["prices"]),
                 day=day, hour=(q["arrivedAt"] % 1440) / 60, slack=(max(o[k]["deadline"] for k in d["prices"]) - q["arrivedAt"]) / 60,
                 notified=notified[leg["pickup"]["placeId"]], legs=len(q["legs"]), private=any(l["pickup"]["privateAddress"] or l["delivery"]["privateAddress"] for l in q["legs"]),
                 note=q["note"] is not None, carsPerDriver=1035 / len(run["roster"]), dealerShare=seen[dealer] / total, backlog=backlog[q["id"]], situation=row["situation"])
        for name, sel in (("day", lambda k: k[1] == day), ("dealerDay", lambda k: k[1] == day and k[2] == dealer), ("dealerWeek", lambda k: k[2] == dealer),
                          ("dealerPrevDay", lambda k: k[1] == day - 1 and k[2] == dealer), ("prevDay", lambda k: k[1] == day - 1)):
            f[name + "N"], f[name + "Win"] = rate(sel)
        last = [k[3] for k in past[-20:]]
        f["last20Win"] = sum(last) / len(last) if last else None
        out.append(f)
        known.append((q["respondBy"], day, dealer, won))
    print(variant, seed, len(out), file=sys.stderr, flush=True)
json.dump(out, open(os.path.dirname(os.path.abspath(__file__)) + "/tree_rows.json", "w"))
print(len(out), "rows")
