import sys, json, collections, re
from spreadlab import notes
from spreadlab.server import data_dir
D = str(data_dir() / "llm-notes") + "/"  # the extracts: large, in the data folder, not committed
rows = [r for r in map(json.loads, open(D + "rows.jsonl")) if r["note"]]
tm = lambda m: f"d{m // 1440} {m % 1440 // 60:02d}:{m % 1440 % 60:02d}"
pref = collections.Counter(re.sub(r"-?\d+$", "", r["seed"]) for r in rows); print(pref)
counts = collections.defaultdict(collections.Counter); wrong = collections.defaultdict(list)
for r in rows:
    g = re.sub(r"-?\d+$", "", r["seed"])
    facts = notes.read(r["note"], r["arrivedAt"])
    leg, truth = r["legs"][0], r["truth"][0]
    stated = leg["pickup"]["window"]["from"]
    true_from = max(truth["readyAt"], truth["releasedAt"] or 0)
    read_from = max(stated, facts.pickup_from)
    kind = ("later" if true_from > stated else "same") + " " + ("right" if read_from == true_from else "too early" if read_from < true_from else "too late")
    for k in (g, "all"):
        counts[k]["n"] += 1; counts[k]["pickup " + kind] += 1
        for name, said, true in (("plates", facts.plates, truth["needsPlates"]), ("manual", facts.manual, truth["manualGearbox"])):
            counts[k][f"{name} {'needed' if true else 'not needed'} {'read' if said else 'not read'}"] += 1
    if not kind.endswith("right"): wrong[kind].append(f"[{r['seed']}] arr {tm(r['arrivedAt'])} stated {tm(stated)} true {tm(true_from)} read {tm(read_from)} | {r['note']['text']}")
    for name, said, true in (("plates", facts.plates, truth["needsPlates"]), ("manual", facts.manual, truth["manualGearbox"])):
        if said != true: wrong[name + (" missed" if true else " false alarm")].append(f"[{r['seed']}] {r['note']['text']}")
for g, c in counts.items():
    print("==", g, dict(sorted(c.items())))
for k, v in wrong.items():
    print("==", k, len(v), "distinct texts", len({x.split('| ')[-1] for x in v}))
    for x in v[:14]: print("   ", x)
