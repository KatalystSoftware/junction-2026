"""Scratch: does the number of won cars without a driver, at the minute a request arrives, tell late deliveries?"""
import bisect, collections, json, sys
from spreadlab import ledger
from spreadlab.play import load_run
from spreadlab.server import near_places, world_map
near = near_places(world_map())
cat = {w["seed"]: w for w in json.load(open("catalogue/catalogue.json"))["weeks"]} if isinstance(json.load(open("catalogue/catalogue.json")), dict) and "weeks" in json.load(open("catalogue/catalogue.json")) else None
seeds = json.load(open("catalogue/seeds.json"))["tune"][:10]
STALE = 60
for variant in sys.argv[1:]:
    rows = []
    print(f"\n{variant}")
    print("  seed     drivers  won  late%   mean open  mean stale  max stale  stale by day (mean at request)")
    for seed in seeds:
        run = load_run(variant, seed); played = ledger.week(run, near)
        order_of = {g["id"]: g["stops"][0]["orderId"] for g in run["gigs"]}
        open_since = {}; series = []  # (at, open, stale)
        reqs = sorted((r["request"]["arrivedAt"], r["request"]["id"]) for r in run["reveal"]["requests"])
        at_request = {}; i = 0
        def snap(now):
            return len(open_since), sum(1 for t in open_since.values() if now - t > STALE)
        for e in run["events"]:
            while i < len(reqs) and reqs[i][0] <= e["at"]:
                at_request[reqs[i][1]] = snap(reqs[i][0]); i += 1
            k = e["kind"]
            if k == "order_won": open_since[e["order"]["id"]] = e["at"]
            elif k == "gig_booked": open_since.pop(order_of.get(e["gigId"]), None)
            elif k in ("gig_dropped", "no_show"): open_since.setdefault(order_of.get(e["gigId"]), e["at"])
            elif k == "delivered": open_since.pop(e["orderId"], None)
            elif k == "order_cancelled": open_since.pop(e["orderId"], None)
        while i < len(reqs):
            at_request[reqs[i][1]] = snap(reqs[i][0]); i += 1
        won = [(id_, r) for id_, r in played["requests"].items() if r["outcome"] == "won"]
        by_day = collections.defaultdict(list)
        for at, id_ in reqs: by_day[at // 1440].append(at_request[id_][1])
        o = [v[0] for v in at_request.values()]; s = [v[1] for v in at_request.values()]
        print(f"  {seed}  {len(run['roster']):5d} {len(won):4d} {100*sum(1 for _, r in won if not r['onTime'])/len(won):5.1f}  {sum(o)/len(o):9.1f}  {sum(s)/len(s):9.1f}  {max(s):8d}   " + " ".join(f"{sum(v)/len(v):5.1f}" for d, v in sorted(by_day.items())))
        for id_, r in won:
            rows.append((at_request[id_][0], at_request[id_][1], not r["onTime"], r["margin"] / 100, r["option"]))
    for name, col, edges in (("open", 0, [0, 3, 6, 10, 15, 25, 999]), ("stale over 60 min", 1, [0, 1, 2, 4, 7, 12, 999])):
        print(f"  cars won by {name} at the request:   n   late%   margin/car")
        for lo, hi in zip(edges, edges[1:]):
            b = [r for r in rows if lo <= r[col] < hi]
            if b: print(f"    {lo:3d}-{hi - 1:3d} {len(b):5d}  {100*sum(r[2] for r in b)/len(b):5.1f}  {sum(r[3] for r in b)/len(b):8.1f}")
