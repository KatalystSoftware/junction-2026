import sys, json, collections, statistics, re
from spreadlab import notes
from spreadlab.server import data_dir
D = str(data_dir() / "llm-notes") + "/"  # the extracts: large, in the data folder, not committed
rows = [json.loads(l) for l in open(D + "rows.jsonl")]
allnotes = [json.loads(l) for l in open(D + "notes.jsonl")]
runs = [json.loads(l) for l in open(D + "runs.jsonl")]
scans = [r["scan"] for r in runs if "scan" in r]; runs = [r for r in runs if "scan" not in r]
print("scans", len(scans), "requests/week", statistics.mean(s["requests"] for s in scans))
per_seed = collections.Counter(n["seed"] for n in allnotes)
print("notes: total", len(allnotes), "per week mean", statistics.mean(per_seed.values()), "min", min(per_seed.values()), "max", max(per_seed.values()))
print("languages", collections.Counter(n["note"]["language"] for n in allnotes))
L = [len(n["note"]["text"]) for n in allnotes]
print("chars mean", statistics.mean(L), "median", statistics.median(L), "p95", sorted(L)[int(.95*len(L))], "max", max(L))
print("distinct texts", len({n["note"]["text"] for n in allnotes}))
print("won orders", len(rows), "with note", sum(1 for r in rows if r["note"]), "seeds", len({r["seed"] for r in rows}))
print("truth keys", collections.Counter(k for r in rows[:2000] for l in r["truth"] for k in l))
# facts in truth
c = collections.Counter()
for r in rows:
    for i, t in enumerate(r["truth"]):
        leg = r["legs"][i]
        stated = leg["pickup"]["window"]["from"]
        true_from = max(t["readyAt"], t["releasedAt"] or 0)
        c["legs"] += 1
        c["note"] += bool(r["note"])
        c["later"] += true_from > stated
        c["later, no note"] += true_from > stated and not r["note"]
        c["plates"] += t["needsPlates"]; c["plates no note"] += t["needsPlates"] and not r["note"]
        c["manual"] += t["manualGearbox"]; c["manual no note"] += t["manualGearbox"] and not r["note"]
        c["summerTyres"] += t["summerTyres"]; c["summer no note"] += t["summerTyres"] and not r["note"]
        c["noteDeadline"] += t["noteDeadline"] is not None
        c["released"] += t["releasedAt"] is not None
        c["pickupHours differ"] += t["pickupHours"] != leg["pickup"]["hours"]
        c["deliveryHours differ"] += t["deliveryHours"] != leg["delivery"]["hours"]
        c["multi-leg"] += len(r["truth"]) > 1
print(dict(c))
