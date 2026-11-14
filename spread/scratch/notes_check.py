"""Scratch: scores the note reader (spreadlab/notes.py) against what the reveal says was true of each won car.
The rows come from scratch/notes_rows.py: one for each won order with a note.

    PYTHONPATH=. uv run python scratch/notes_check.py rows.jsonl [--show 30]
"""
import collections, json, sys
from spreadlab import notes

D = 1440
tm = lambda m: f"d{m // D} {m % D // 60:02d}:{m % D % 60:02d}"
rows = [json.loads(line) for line in open(sys.argv[1])]
show = int(sys.argv[sys.argv.index("--show") + 1]) if "--show" in sys.argv else 0
counts, wrong = collections.Counter(), collections.defaultdict(list)
for r in rows:
    facts = notes.read({"text": r["note"]}, r["arrivedAt"])
    leg, truth = r["legs"][0], r["truth"][0]
    stated = leg["pickup"]["window"]["from"]
    true_from = max(truth["readyAt"], truth["releasedAt"] or 0)
    read_from = max(stated, facts.pickup_from)
    kind = ("later" if true_from > stated else "same") + " " + ("right" if read_from == true_from else "too early" if read_from < true_from else "too late")
    counts["pickup " + kind] += 1
    if not kind.endswith("right"):
        wrong[kind].append(f"arr {tm(r['arrivedAt'])} stated {tm(stated)} true {tm(true_from)} read {tm(read_from)} | {r['note']}")
    for name, said, true in (("plates", facts.plates, truth["needsPlates"]), ("manual", facts.manual, truth["manualGearbox"])):
        counts[f"{name} {'needed' if true else 'not needed'} {'read' if said else 'not read'}"] += 1
        if said != true:
            wrong[name].append(f"true {true} | {r['note']}")
print(len(rows), "orders with a note")
for key in sorted(counts):
    print(f"  {key:32s} {counts[key]}")
for kind, lines in wrong.items():
    print("==", kind, len(lines))
    for line in lines[:show]:
        print("  ", line)
