"""Streams the archive bundles and writes: notes.jsonl (every request with a note, from the scans), rows.jsonl (won orders
with a note and their truth, one per seed and request), fails.jsonl (failed visits, by run), runs.jsonl (run summaries)."""
import sys, json, collections
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from spreadlab import archive
from spreadlab.server import data_dir
OUT = data_dir() / "llm-notes"  # large, not committed
BUNDLES = Path(sys.argv[1]) if len(sys.argv) > 1 else archive.BUNDLES  # the real bundles: after `git lfs pull`, or a folder of them

def work(args):
    name, content = args
    d = json.loads(content)
    if name.startswith("scans/"):
        reqs = [e["request"] for e in d["events"] if e["kind"] == "price_request"]
        return "scan", {"seed": d["seed"], "requests": len(reqs)}, [{"seed": d["seed"], "id": r["id"], "arrivedAt": r["arrivedAt"], "note": r["note"]} for r in reqs if r["note"]], []
    req = {r["request"]["id"]: r["request"] for r in d["reveal"]["requests"]}
    won = {e["order"]["id"]: e["order"] for e in d["events"] if e["kind"] == "order_won"}
    rows = []
    for o in d["reveal"]["orders"]:
        r = req[o["orderId"]]
        if o["orderId"] not in won:
            continue
        order = won[o["orderId"]]
        rows.append({"seed": d["seed"], "id": r["id"], "note": r["note"], "arrivedAt": r["arrivedAt"], "option": order["option"], "deadline": order["deadline"],
                     "legs": [{"pickup": l["pickup"], "delivery": l["delivery"]} for l in r["legs"]], "truth": o["legs"]})
    fails = [{"variant": d["variant"], "seed": d["seed"], "orderId": e["orderId"], "leg": e["leg"], "reason": e["reason"], "at": e["at"]} for e in d["events"] if e["kind"] == "visit_failed"]
    ledger = collections.Counter()
    kinds = collections.Counter()
    for e in d["events"]:
        if e["kind"] == "ledger":
            line = e.get("line") or e
            kinds[line.get("type") or line.get("kind2") or "?"] += 1
            ledger[line.get("type") or "?"] += line.get("amountCents", 0)
    sample = next((e for e in d["events"] if e["kind"] == "ledger"), None)
    summary = {"variant": d["variant"], "seed": d["seed"], "fingerprint": d.get("fingerprint"), "score": d["score"], "won": len(won), "wonWithNote": sum(1 for r in rows if r["note"]),
               "fails": len(fails), "ledger": dict(ledger), "ledgerCount": dict(kinds), "ledgerSample": sample, "seconds": d.get("seconds")}
    return "run", summary, [], (rows, fails)

def items():
    held = archive.packed(BUNDLES)
    for bundle in sorted(BUNDLES.glob("*.tar.zst")):
        for name, content in archive.members(bundle):
            if held[name][1] == bundle and name.endswith("-L8.json.gz"):
                yield name, content

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    seen, n = set(), 0
    with ProcessPoolExecutor(3) as pool, open(OUT / "notes.jsonl", "w") as fn, open(OUT / "rows.jsonl", "w") as fr, open(OUT / "fails.jsonl", "w") as ff, open(OUT / "runs.jsonl", "w") as fs:
        import itertools, collections as c
        it, pending = items(), c.deque()
        def results():
            for item in it:
                pending.append(pool.submit(work, item))
                if len(pending) >= 8:
                    yield pending.popleft().result()
            while pending:
                yield pending.popleft().result()
        for kind, summary, notes, extra in results():
            n += 1
            if kind == "scan":
                fs.write(json.dumps({"scan": summary}) + "\n")
                for x in notes: fn.write(json.dumps(x) + "\n")
            else:
                fs.write(json.dumps(summary) + "\n")
                rows, fails = extra
                for row in rows:
                    if (row["seed"], row["id"]) not in seen:
                        seen.add((row["seed"], row["id"])); fr.write(json.dumps(row) + "\n")
                for x in fails: ff.write(json.dumps(x) + "\n")
            if n % 200 == 0: print(n, flush=True)
    print("done", n, len(seen))
