"""Notes per real minute on the final's clock: 18 real seconds an hour from 06:00 to 22:00 on weekdays, 3 at night."""
import json, collections, statistics
from spreadlab.server import data_dir
D = str(data_dir() / "llm-notes") + "/"  # the extracts: large, in the data folder, not committed
def real(m):  # real seconds from the world's start (Monday 00:00) to world minute m, weekdays of the first week
    day, minute = divmod(m, 1440)
    per_day = (6 * 3 + 16 * 18 + 2 * 3)
    s = day * per_day
    for h in range(24):
        rate = 18 if 6 <= h < 22 else 3
        s += rate * max(0, min(60, minute - h * 60)) / 60
    return s
notes = collections.defaultdict(list)
for l in open(D + "notes.jsonl"):
    n = json.loads(l); notes[n["seed"]].append(real(n["arrivedAt"]))
won = collections.defaultdict(list)
for l in open(D + "ref_orders.jsonl"):
    o = json.loads(l)
    if o["variant"] == "steep-notes-offers-8" and o["note"]: won[o["seed"]].append(real(o["wonAt"]))
def peaks(ts, window):
    ts = sorted(ts); best = j = 0
    for i, t in enumerate(ts):
        while ts[j] < t - window: j += 1
        best = max(best, i - j + 1)
    return best
for name, d in (("all notes, at the request", notes), ("won orders with a note, at the win", won)):
    for w in (60, 10):
        p = [peaks(ts, w) for ts in d.values()]
        print(f"{name}: weeks {len(d)}, per week {statistics.mean(len(t) for t in d.values()):.0f}, most in {w} real s: median {statistics.median(p)}, p95 {sorted(p)[int(.95 * len(p))]}, max {max(p)}")
    span = [max(ts) - min(ts) for ts in d.values()]
    print("   real seconds from first to last:", round(statistics.mean(span)))
