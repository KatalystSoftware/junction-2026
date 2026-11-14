"""Per-order records of the reference variant's archived weeks: note, truth, ledger lines, failed visits, posted gigs."""
import sys, json, collections
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from spreadlab import archive
from spreadlab.server import data_dir
OUT = data_dir() / "llm-notes"  # large, not committed
BUNDLES = Path(sys.argv[1]) if len(sys.argv) > 1 else archive.BUNDLES  # the real bundles: after `git lfs pull`, or a folder of them
VARIANTS = ("steep-notes-offers-8", "fee-cap-1.2-drop-cost-1.3")

def work(args):
    name, content = args
    d = json.loads(content)
    req = {r["request"]["id"]: r["request"] for r in d["reveal"]["requests"]}
    won = {e["order"]["id"]: e for e in d["events"] if e["kind"] == "order_won"}
    lines = collections.defaultdict(list); fails = collections.defaultdict(list); other = collections.defaultdict(list)
    for e in d["events"]:
        if e["kind"] == "ledger":
            l = e["line"]; lines[l.get("orderId")].append([l["at"], l["kind"], l["cents"], l.get("detail"), l.get("gigId")])
        elif e["kind"] == "visit_failed":
            fails[e["orderId"]].append([e["at"], e["leg"], e["reason"], e["gigId"]])
        elif e["kind"] in ("order_changed", "order_cancelled", "release", "forecast"):
            other[e.get("orderId")].append(e)
    out = []
    for o in d["reveal"]["orders"]:
        if o["orderId"] not in won: continue
        r, w = req[o["orderId"]], won[o["orderId"]]
        out.append({"variant": d["variant"], "seed": d["seed"], "id": r["id"], "note": r["note"], "arrivedAt": r["arrivedAt"], "wonAt": w["at"], "order": w["order"],
                    "reqLegs": [{"pickup": l["pickup"], "delivery": l["delivery"]} for l in r["legs"]], "truth": o["legs"],
                    "ledger": lines.get(o["orderId"], []), "fails": fails.get(o["orderId"], []), "other": other.get(o["orderId"], [])})
    gigs = d.get("gigs")
    return {"variant": d["variant"], "seed": d["seed"], "score": d["score"], "unowned": lines.get(None, []), "gigsType": type(gigs).__name__,
            "gigSample": (list(gigs.items())[:1] if isinstance(gigs, dict) else gigs[:1]) if gigs else None, "decisionSample": str(d.get("decisions"))[:600]}, out

def items():
    held = archive.packed(BUNDLES)
    for bundle in sorted(BUNDLES.glob("*.tar.zst")):
        for name, content in archive.members(bundle):
            if held[name][1] == bundle and name.endswith("-L8.json.gz") and name.split("/")[1] in VARIANTS:
                yield name, content

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    import collections as c
    with ProcessPoolExecutor(3) as pool, open(OUT / "ref_orders.jsonl", "w") as fo, open(OUT / "ref_runs.jsonl", "w") as fr:
        it, pending, n = items(), c.deque(), 0
        def results():
            for item in it:
                pending.append(pool.submit(work, item))
                if len(pending) >= 8: yield pending.popleft().result()
            while pending: yield pending.popleft().result()
        for summary, out in results():
            n += 1
            fr.write(json.dumps(summary) + "\n")
            for x in out: fo.write(json.dumps(x) + "\n")
    print("done", n)
