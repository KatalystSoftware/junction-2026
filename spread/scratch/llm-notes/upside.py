import sys, json, collections, statistics
from spreadlab import notes
from spreadlab.server import data_dir
D = str(data_dir() / "llm-notes") + "/"  # the extracts: large, in the data folder, not committed
V = sys.argv[1] if len(sys.argv) > 1 else "steep-notes-offers-8"
orders = [o for o in map(json.loads, open(D + "ref_orders.jsonl")) if o["variant"] == V]
weeks = len({o["seed"] for o in orders})
print(V, "weeks", weeks, "orders", len(orders), "with note", sum(1 for o in orders if o["note"]))
eur = collections.Counter(); cnt = collections.Counter(); ex = collections.defaultdict(list)
def hours_open(h, t):
    if h is None: return True
    day, m = t // 1440 % 7, t % 1440
    if day in h["weekdays"]: return h["opens"] <= m < h["closes"]
    if day == 5 and h.get("saturday"): return h["saturday"]["opens"] <= m < h["saturday"]["closes"]
    return False
for o in orders:
    text = o["note"]["text"] if o["note"] else ""
    facts = notes.read(o["note"], o["arrivedAt"])
    for at, kind, cents, detail, gig in o["ledger"]:
        eur[kind] += cents; cnt[kind] += 1
    t0, leg0 = o["truth"][0], o["reqLegs"][0]
    late = [l for l in o["ledger"] if l[1] == "late_refund"]
    flags = []
    for i, t in enumerate(o["truth"]):
        leg = o["reqLegs"][i]
        if max(t["readyAt"], t["releasedAt"] or 0) > leg["pickup"]["window"]["from"]: flags.append("ready later")
        if t["needsPlates"]: flags.append("plates")
        if t["manualGearbox"]: flags.append("manual")
        if t["summerTyres"]: flags.append("summer tyres")
        if t["noteDeadline"] is not None: flags.append("note deadline")
        if t["pickupHours"] != leg["pickup"]["hours"]: flags.append("pickup hours")
        if t["deliveryHours"] != leg["delivery"]["hours"]: flags.append("delivery hours")
    for f in set(flags) or {"none" if text else "no note"}:
        cnt["orders: " + f] += 1; cnt["late: " + f] += bool(late)
        eur["late refund: " + f] += sum(l[2] for l in late)
        eur["failed_visit: " + f] += sum(l[2] for l in o["ledger"] if l[1] == "failed_visit")
        eur["waiting: " + f] += sum(l[2] for l in o["ledger"] if l[1] == "waiting")
    # failed visits by cause
    fv = [l for l in o["ledger"] if l[1] == "failed_visit"]
    for (at, legi, reason, gig), line in zip(o["fails"], fv + [None] * len(o["fails"])):
        t, leg = o["truth"][legi], o["reqLegs"][legi]
        true_from = max(t["readyAt"], t["releasedAt"] or 0)
        if reason == "no_plates": cause = "plates: reader missed" if not facts.plates else "plates: read, not posted"
        elif reason == "licence": cause = "licence: reader missed" if not facts.manual else "licence: read, not posted"
        elif reason == "not_ready":
            if at < true_from: cause = "not ready: reader too early" if max(leg["pickup"]["window"]["from"], facts.pickup_from) < true_from else "not ready: read right, driver early"
            elif t["summerTyres"]: cause = "not ready: summer tyres in snow"
            else: cause = "not ready: other"
        else:
            stated_open, real_open = hours_open(leg["pickup"]["hours"], at), hours_open(t["pickupHours"], at)
            cause = "closed: real hours differ from stated (note)" if stated_open and not real_open else "closed: by stated hours" if not stated_open else "closed: other"
        cnt["fail " + cause] += 1; eur["fail " + cause] += line[2] if line else 0
        if len(ex[cause]) < 8: ex[cause].append(f"at d{at//1440} {at%1440//60:02d}:{at%1440%60:02d} | {text} | stated {leg['pickup']['hours']} real {t['pickupHours']} win {leg['pickup']['window']}")
    for l in o["ledger"]:
        if l[1] == "waiting":
            t, leg = o["truth"][0], o["reqLegs"][0]
            cause = "waiting: delivery hours differ (note)" if any(t["deliveryHours"] != leg["delivery"]["hours"] for t, leg in zip(o["truth"], o["reqLegs"])) else "waiting: other"
            cnt[cause] += 1; eur[cause] += l[2]
            if len(ex[cause]) < 8: ex[cause].append(f"{l[3]} | {text} | stated {leg['delivery']['hours']} real {t['deliveryHours']}")
    # late only by the note's deadline
    if late:
        nd = [t["noteDeadline"] for t in o["truth"] if t["noteDeadline"] is not None]
        dl = max((t["deliveredAt"] or 10**9) for t in o["truth"])
        if nd and dl <= o["order"]["deadline"]:
            cnt["late only by the note's deadline"] += 1; eur["late only by the note's deadline"] += sum(l[2] for l in late)
            if len(ex["notedl"]) < 8: ex["notedl"].append(f"{text} | deadline {o['order']['deadline']} note {nd} delivered {dl}")
        elif nd: cnt["late with note deadline, also by order deadline"] += 1
for k in sorted(set(eur) | set(cnt)):
    print(f"{k:58s} {cnt[k] / weeks:8.2f}/wk  {eur[k] / weeks / 100:9.1f} EUR/wk")
for k, v in ex.items():
    print("==", k)
    for x in v: print("   ", x)
