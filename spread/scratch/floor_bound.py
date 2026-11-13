"""Scratch: the quotes that the floor raised: how many won, and what they earned, against the same requests without a floor."""
import json, sys
from spreadlab import ledger
from spreadlab.play import load_run
from spreadlab.server import near_places, world_map
near = near_places(world_map())
seeds = json.load(open("catalogue/seeds.json"))["tune"][:10]
def rows(variant):
    out = {}
    for seed in seeds:
        run = load_run(variant, seed); played = ledger.week(run, near)
        reqs = {r["request"]["id"]: r["request"] for r in run["reveal"]["requests"]}
        for id_, row in played["requests"].items():
            d = run["decisions"][id_]
            if d["declined"] or len(reqs[id_]["legs"]) > 1: continue
            q = reqs[id_]
            raised = {k for k, p in d["prices"].items() if p > round(next(o for o in q["options"] if o["kind"] == k)["listPriceCents"] * 1.5)}
            won = row["outcome"] == "won"
            out[(seed, id_)] = (bool(raised), won, (row["price"] - row["fees"] - row["costs"] - row["late"]) / 100 if won else 0, max(d["prices"][k] / next(o for o in q["options"] if o["kind"] == k)["listPriceCents"] for k in d["prices"]))
    return out
ref = rows("with-same-day")
for v in sys.argv[1:]:
    r = rows(v); b = [k for k in r if r[k][0]]; rest = [k for k in r if not r[k][0]]
    print(f"{v}: {len(r)} requests quoted, floor raised {len(b)} ({100*len(b)/len(r):.0f}%)")
    for name, ks in (("raised", b), ("not raised", rest)):
        print(f"  {name:10s} with floor: won {100*sum(r[k][1] for k in ks)/len(ks):4.1f}%  margin/wk {sum(r[k][2] for k in ks)/10:7.0f}   no floor: won {100*sum(ref[k][1] for k in ks if k in ref)/len(ks):4.1f}%  margin/wk {sum(ref[k][2] for k in ks if k in ref)/10:7.0f}")
