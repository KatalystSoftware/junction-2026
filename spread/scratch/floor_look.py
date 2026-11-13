"""Scratch: win rate and margin by quote / typical fee, and what dropping quotes under a floor would have left."""
import collections, glob, json, sys
from spreadlab import ledger
from spreadlab.play import load_run
from spreadlab.server import data_dir, near_places, world_map
near = near_places(world_map())
tune = set(json.load(open("catalogue/seeds.json"))["tune"])
shown = False
for variant in ("baseline", "price-1.4", "with-same-day"):
    rows = []
    weeks = 0
    for path in sorted(glob.glob(str(data_dir() / "runs" / variant / "*-L8.json.gz"))):
        seed = path.split("/")[-1][:-len("-L8.json.gz")]
        if seed not in tune: continue
        run = load_run(variant, seed); weeks += 1
        played = ledger.week(run, near)
        reqs = {r["request"]["id"]: r for r in run["reveal"]["requests"]}
        if not shown:
            r0 = run["reveal"]["requests"][0]; print("reveal request keys", {k: (v if k != "request" else "...") for k, v in r0.items()})
            print("ledger row", next(iter(played["requests"].values()))); shown = True
        for id_, row in played["requests"].items():
            if run["decisions"][id_]["declined"] or len(reqs[id_]["request"]["legs"]) > 1: continue
            q = reqs[id_]["request"]
            for kind, price in run["decisions"][id_]["prices"].items():
                o = next(o for o in q["options"] if o["kind"] == kind)
                won = row["outcome"] == "won" and row["option"] == kind
                rows.append((price / q["referenceFeeCents"], q["referenceFeeCents"] / o["listPriceCents"], won, (row["price"] - row["fees"] - row["costs"] - row["late"]) / 100 if won else 0, row.get("onTime") if won else None))
    print(f"\n{variant}: {weeks} tune weeks, {len(rows)} option quotes")
    edges = [0, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5, 9]
    print("  quote/ref     quotes  won   win%   margin/wk  margin/won  late%")
    for lo, hi in zip(edges, edges[1:]):
        b = [r for r in rows if lo <= r[0] < hi]; w = [r for r in b if r[2]]
        if b: print(f"  {lo:.1f}-{hi:.1f}  {len(b):7d} {len(w):5d} {100*len(w)/len(b):5.1f}  {sum(r[3] for r in w)/weeks:10.0f}  {sum(r[3] for r in w)/max(1,len(w)):9.1f}  {100*sum(1 for r in w if not r[4])/max(1,len(w)):5.1f}")
    print("  total margin/wk on single cars", round(sum(r[3] for r in rows) / weeks))
