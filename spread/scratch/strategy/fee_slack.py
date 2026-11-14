"""Weeks that opened below the typical fee: by the hours a car had to its last pickup at the win, how fast it booked, what was paid and how often
it ended late, beside the reference's weeks on the same seeds. usage: fee_slack.py <cache> <low variant> <base variant>"""
import pickle, glob, sys, os, collections, statistics as st
cache, low, base = sys.argv[1:4]
def week(f):
    w = pickle.load(open(f, "rb"))
    req = {r["request"]["id"]: r["request"] for r in w["requests"]}
    order_of = {g["id"]: g["stops"][0]["orderId"] for g in w["gigs"]}
    won, first, fee, late = {}, {}, collections.Counter(), set()
    for e in w["events"]:
        k = e["kind"]
        if k == "order_won": won[e["order"]["id"]] = (e["at"], e["order"].get("lastPickupAt", e["order"]["deadline"]))
        elif k == "gig_booked": first.setdefault(order_of.get(e["gigId"]), e["at"])
        elif k == "ledger" and e["line"].get("orderId"):
            if e["line"]["kind"] in ("driver_fee", "failed_visit", "release_fee"): fee[e["line"]["orderId"]] -= e["line"]["cents"]
            if e["line"]["kind"] in ("late_refund", "undelivered_penalty"): late.add(e["line"]["orderId"])
    out = []
    for o, (at, last) in won.items():
        r = req[o]
        if len(r["legs"]) != 1 or r["legs"][0]["pickup"]["privateAddress"] or r["legs"][0]["delivery"]["privateAddress"]: continue
        h = (last - at) / 60
        out.append(("<8" if h < 8 else "8-16" if h < 16 else "16-30" if h < 30 else "30+", (first.get(o, 10**9) - at) / 60, fee[o] / r["referenceFeeCents"], o in late, r["referenceFeeCents"]))
    return out, w["score"]
seeds = sorted({os.path.basename(f) for f in glob.glob(f"{cache}/{low}/*.pkl")} & {os.path.basename(f) for f in glob.glob(f"{cache}/{base}/*.pkl")})
print(len(seeds), "seeds both played")
for v in (base, low):
    rows, scores = [], []
    for s in seeds:
        r, sc = week(f"{cache}/{v}/{s}"); rows += r; scores.append(sc)
    print(v, "margin %.0f, orders %.0f, lowest week %.1f%%" % (st.mean(s["marginCents"] for s in scores) / 100, st.mean(s["wonOrders"] for s in scores), 100 * min(s["onTimeShare"] for s in scores)))
    for b in ("<8", "8-16", "16-30", "30+"):
        x = [r for r in rows if r[0] == b]
        print("   %5s h to the last pickup: %5.1f orders a week, booked in 1 h %2.0f%%, in 4 h %2.0f%%, in 12 h %2.0f%%, paid %.3f x typical (typical %.0f eur), late %.1f%%" % (
            b, len(x) / len(seeds), 100 * sum(r[1] <= 1 for r in x) / len(x), 100 * sum(r[1] <= 4 for r in x) / len(x), 100 * sum(r[1] <= 12 for r in x) / len(x), st.mean(r[2] for r in x), st.mean(r[4] for r in x) / 100, 100 * st.mean(r[3] for r in x)))
