"""What the rules' misreadings cost in the reference's 104 archived weeks: the account lines of the orders whose note it read wrong."""
import sys, json, collections
from spreadlab import notes
from spreadlab.server import data_dir
D = str(data_dir() / "llm-notes") + "/"  # the extracts: large, in the data folder, not committed
n = 0; tot = collections.Counter(); weeks = set(); withnote = 0
for o in map(json.loads, open(D + "ref_orders.jsonl")):
    if o["variant"] != "steep-notes-offers-8": continue
    weeks.add(o["seed"])
    if not o["note"]: continue
    withnote += 1
    f, t, leg = notes.read(o["note"], o["arrivedAt"]), o["truth"][0], o["reqLegs"][0]
    wrong = []
    if max(leg["pickup"]["window"]["from"], f.pickup_from) != max(t["readyAt"], t["releasedAt"] or 0): wrong.append("ready")
    if f.plates != t["needsPlates"]: wrong.append("plates")
    if f.manual != t["manualGearbox"]: wrong.append("manual")
    if not wrong: continue
    n += 1
    lines = collections.Counter()
    for at, kind, cents, detail, gig in o["ledger"]: lines[kind] += cents
    tot.update({k: v for k, v in lines.items() if k in ("failed_visit", "late_refund", "waiting")})
    print(o["seed"], wrong, {k: v / 100 for k, v in lines.items()}, "fails", [x[2] for x in o["fails"]], "|", o["note"]["text"])
print(len(weeks), "weeks,", withnote, "won orders with a note,", n, "read wrong;", {k: round(v / 100 / len(weeks), 2) for k, v in tot.items()}, "EUR a week")
