"""Scratch: scores `notes.limits` (the note's own deadline, and the hours of the pickup and delivery sites when the
note gives others than the request) against what the reveal says was true. Rows from scratch/notes_rows.py.

    PYTHONPATH=. uv run python scratch/notes_limits_check.py rows.jsonl [--show 15]
"""
import collections
import json
import sys

from spreadlab import notes

D = 1440
tm = lambda m: "-" if m is None else f"d{m // D} {m % D // 60:02d}:{m % D % 60:02d}"  # noqa: E731
rows = [json.loads(line) for line in open(sys.argv[1])]
show = int(sys.argv[sys.argv.index("--show") + 1]) if "--show" in sys.argv else 0
counts, wrong = collections.Counter(), collections.defaultdict(list)
for r in rows:
    limits = notes.limits({"text": r["note"]}, r["arrivedAt"])
    leg, truth, day = r["legs"][0], r["truth"][0], r["arrivedAt"] // D * D
    # A deadline at or after the order's own changes nothing, so both are counted by the earlier of the two.
    true, read = truth["noteDeadline"], limits.deadline or None
    true, read = (true if true is not None and true < r["deadline"] else None), (read if read is not None and read < r["deadline"] else None)
    kind = ("earlier " if true is not None else "none ") + ("right" if read == true else "missed" if read is None else "false alarm" if true is None else "wrong")
    counts["deadline " + kind] += 1
    if not kind.endswith("right"):
        wrong["deadline " + kind].append(f"arr {tm(r['arrivedAt'] - day)} true {tm(true and true - day)} read {tm(read and read - day)} | {r['note']}")
    for site, hours in (("pickup", limits.pickup_hours), ("delivery", limits.delivery_hours)):
        stated, real = leg[site]["hours"], truth[site + "Hours"]
        if stated is None or real is None:
            counts[f"{site} hours: none stated"] += 1
            continue
        want = (real["opens"], real["closes"])
        got = (hours[0] or stated["opens"], hours[1] or stated["closes"])
        differs = want != (stated["opens"], stated["closes"])
        kind = ("other " if differs else "same ") + ("right" if got == want else "missed" if hours == (0, 0) else "false alarm" if not differs else "wrong")
        counts[f"{site} hours {kind}"] += 1
        if not kind.endswith("right"):
            wrong[f"{site} hours {kind}"].append(f"stated {tm(stated['opens'])[3:]}-{tm(stated['closes'])[3:]} true {tm(want[0])[3:]}-{tm(want[1])[3:]} read {tm(hours[0])[3:]}-{tm(hours[1])[3:]} | {r['note']}")
print(len(rows), "orders with a note")
for key in sorted(counts):
    print(f"  {key:36s} {counts[key]}")
for kind, lines in sorted(wrong.items()):
    print("==", kind, len(lines))
    for line in lines[:show]:
        print("  ", line[:300])
