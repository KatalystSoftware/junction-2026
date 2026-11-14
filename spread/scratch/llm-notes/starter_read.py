"""What the kit's keyword reading (spread.starter.window_from_note, which the reference still uses for closing times and
deadlines) gets right on the facts that notes.py does not read, and on the reference's own closed visits and waits."""
import sys, json, collections
from spread.starter import window_from_note
from spreadlab.server import data_dir
D = str(data_dir() / "llm-notes") + "/"  # the extracts: large, in the data folder, not committed
rows = [r for r in map(json.loads, open(D + "rows.jsonl")) if r["note"] and len(r["truth"]) == 1]
c = collections.Counter()
def reads(note, leg, t, deadline):
    out = {}
    pw = leg["pickup"]["window"]; w = window_from_note(note, pw, "pickup")
    real, h = t["pickupHours"], leg["pickup"]["hours"]
    if real and real != h:
        out["pickup closes"] = w["to"] < pw["to"] and w["to"] % 1440 == real["closes"]
        out["pickup closes, on a day the car can be collected"] = out["pickup closes"] and w["to"] > max(t["readyAt"], t["releasedAt"] or 0, pw["from"])
    real, h = t["deliveryHours"], leg["delivery"]["hours"]
    base = {"from": leg["delivery"]["window"]["from"], "to": max(leg["delivery"]["window"]["from"], deadline)}
    w = window_from_note(note, base, "delivery")
    if real and real != h:
        out["delivery closes"] = w["to"] < base["to"] and w["to"] % 1440 == real["closes"]
    if t["noteDeadline"] is not None:
        out["deadline"] = w["to"] == t["noteDeadline"]
        if t["noteDeadline"] < deadline: out["deadline, tighter than the order's"] = w["to"] == t["noteDeadline"]
    return out
for r in rows:
    for k, v in reads(r["note"], r["legs"][0], r["truth"][0], r["deadline"]).items():
        c[k] += 1; c[k + " right"] += v
for k in [k for k in c if not k.endswith("right")]:
    print(f"{k:55s} {c[k + ' right']}/{c[k]} = {c[k + ' right'] / c[k]:.0%}")
# The reference's own losses: was the fact read by the starter's keywords when the visit failed or the driver waited?
orders = [o for o in map(json.loads, open(D + "ref_orders.jsonl")) if o["variant"] == "steep-notes-offers-8" and o["note"]]
weeks = 104; e = collections.Counter(); n = collections.Counter()
def hours_open(h, t):
    day, m = t // 1440 % 7, t % 1440
    if day in h["weekdays"]: return h["opens"] <= m < h["closes"]
    return bool(day == 5 and h.get("saturday") and h["saturday"]["opens"] <= m < h["saturday"]["closes"])
for o in orders:
    fv = [l for l in o["ledger"] if l[1] == "failed_visit"]
    for (at, legi, reason, gig), line in zip(o["fails"], fv):
        if reason != "closed": continue
        t, leg = o["truth"][legi], o["reqLegs"][legi]
        if not (hours_open(leg["pickup"]["hours"], at) and not hours_open(t["pickupHours"], at)): continue
        got = reads(o["note"], leg, t, o["order"]["deadline"])
        early = at % 1440 < t["pickupHours"]["opens"]
        k = "closed visit: " + ("before the real opening" if early else "after the real closing") + (", closing time read by the kit" if got.get("pickup closes") else ", not read")
        n[k] += 1; e[k] += line[2]
    for l in o["ledger"]:
        if l[1] == "waiting":
            got = reads(o["note"], o["reqLegs"][0], o["truth"][0], o["order"]["deadline"])
            k = "wait at delivery: " + ("closing time read by the kit" if got.get("delivery closes") else "not read")
            n[k] += 1; e[k] += l[2]
    late = [l for l in o["ledger"] if l[1] == "late_refund"]
    nd = o["truth"][0]["noteDeadline"]
    if late and nd is not None and max((t["deliveredAt"] or 10**9) for t in o["truth"]) <= o["order"]["deadline"]:
        got = reads(o["note"], o["reqLegs"][0], o["truth"][0], o["order"]["deadline"])
        k = "late by the note's deadline only: " + ("deadline read by the kit" if got.get("deadline") else "not read")
        n[k] += 1; e[k] += sum(l[2] for l in late)
for k in sorted(n): print(f"{k:75s} {n[k] / weeks:5.2f}/wk {e[k] / weeks / 100:7.1f} EUR/wk")
# requests with a note that arrive outside 06:00-22:00
notes = [json.loads(l) for l in open(D + "notes.jsonl")]
print("notes at night:", sum(1 for x in notes if not 360 <= x["arrivedAt"] % 1440 < 1320), "of", len(notes), "hours", sorted(collections.Counter(x["arrivedAt"] % 1440 // 60 for x in notes).items()))
