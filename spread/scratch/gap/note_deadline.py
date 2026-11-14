"""Orders whose note sets a tighter deadline (the reveal's noteDeadline): how many, how late, and whether the desk planned for it.
PYTHONPATH=. uv run --with numpy python scratch/gap/note_deadline.py <data> <variant>"""
import sys, collections
import lib
data, variant = sys.argv[1:3]
c = collections.Counter(); ex = []; n = 0; by = collections.Counter()
for path in lib.runs(data, variant):
    d = lib.load(path); n += 1
    truth = {o["orderId"]: o["legs"] for o in d["reveal"]["orders"]}
    won = {e["order"]["id"]: e["order"] for e in d["events"] if e["kind"] == "order_won"}
    for e in d["events"]:
        if e["kind"] == "order_changed" and e["order"]["id"] in won: won[e["order"]["id"]] = {**won[e["order"]["id"]], "deadline": e["order"]["deadline"]}
    cancelled = {e["orderId"] for e in d["events"] if e["kind"] == "order_cancelled"}
    refund = collections.Counter()
    for e in d["events"]:
        if e["kind"] == "ledger" and e["line"]["kind"] in ("late_refund", "undelivered_penalty"): refund[e["line"]["orderId"]] -= e["line"]["cents"]
    reqs = {r["request"]["id"]: r["request"] for r in d["reveal"]["requests"]}
    gig_window = {}
    for g in d["gigs"]:
        for s in g["stops"]:
            if s["kind"] == "delivery" and "window" in s: gig_window[s["orderId"]] = s["window"]
    for oid, o in won.items():
        if oid in cancelled or len(truth[oid]) > 1: continue
        leg = truth[oid][0]; late = refund[oid] > 0
        c["orders"] += 1; c["late"] += late
        nd = leg["noteDeadline"]
        if nd is None: continue
        c["note deadline"] += 1; c["note deadline: late"] += late; c["note deadline: refund"] += refund[oid]
        tighter = nd < o["deadline"]
        c["note deadline before the order's deadline"] += tighter
        delivered = leg["deliveredAt"]
        if delivered is not None:
            c["delivered after the note's deadline but by the order's"] += nd < delivered <= o["deadline"]
            c["delivered after both"] += delivered > o["deadline"]
        c["gig had a delivery window"] += oid in gig_window
        by[(o["deadline"] - nd) // 60] += 1
        if late and len(ex) < 6: ex.append((reqs[oid]["note"], nd, o["deadline"], delivered, o["option"]))
print(variant, n, "weeks; a week:", {k: round(v / n, 2) for k, v in c.items()})
print("late share with a note deadline: %.1f%%, without: %.1f%%" % (100 * c["note deadline: late"] / max(c["note deadline"], 1), 100 * (c["late"] - c["note deadline: late"]) / (c["orders"] - c["note deadline"])))
print("hours the note's deadline is before the order's:", sorted(by.items())[:12])
for e in ex: print("  ", e)
