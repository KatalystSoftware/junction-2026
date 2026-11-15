"""Post-analysis of the final from the desk log and reveal. Usage: python3 -I final_split.py <dir with log.jsonl and end.json>"""
import json, sys, collections, statistics as st
D = sys.argv[1]
rev = json.load(open(D + "/end.json"))["reveal"]
dec, shift, posts, booked, fees_by_gig = {}, [], {}, {}, collections.Counter()
for l in open(D + "/log.jsonl"):
    r = json.loads(l)
    if r["kind"] == "decision":
        dec[r["requestId"]] = r
    elif r["kind"] == "action" and r["action"]["type"] == "post" and r["ok"]:
        posts[r["id"]] = [s["orderId"] for s in r["action"]["stops"] if s["kind"] == "pickup"]
    elif r["kind"] == "event":
        e = r["event"]
        if e["kind"] == "gig_booked": booked[e["gigId"]] = e["feeCents"]
        if e["kind"] == "ledger" and e["line"]["kind"] == "driver_fee" and e["line"]["gigId"]:
            fees_by_gig[e["line"]["gigId"]] += -e["line"]["cents"]
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
reqs = rev["requests"]
ref = {x["request"]["id"]: x["request"]["referenceFeeCents"] for x in reqs}
print("requests", len(reqs), "won", sum(x["outcome"] == "won" for x in reqs))
print("declines", collections.Counter(d["declined"] for d in dec.values() if d["declined"]))
# by day
by = collections.defaultdict(lambda: dict(n=0, w=0, dec=0, rat=[], shift=[], wp=[], wref=[]))
rows = []
for x in reqs:
    q, rq = x["request"], x["quote"]
    day = q["arrivedAt"] // 1440
    lst = {o["kind"]: o["listPriceCents"] for o in q["options"]}
    d = dec[q["id"]]
    declined = bool(d["declined"])
    ratios = [rq[k] / lst[k] for k in rq if k in lst]
    rr = min(ratios) if ratios and not declined else None
    refr = min(rq.values()) / q["referenceFeeCents"] if rq and not declined else None
    b = by[day]; b["n"] += 1; b["dec"] += declined; b["shift"].append(d["shift"])
    won = x["outcome"] == "won"
    b["w"] += won
    if rr: b["rat"].append(rr)
    if won: b["wp"].append(rq[x["option"]]); b["wref"].append(rq[x["option"]] / q["referenceFeeCents"])
    rows.append((rr, refr, won, declined, day, len(q["legs"])))
print("\nday | requests | declined | won | win rate of quoted | min quote/list (median) | day shift (mean) | won price € | won price/ref fee")
cum = 0
for k in sorted(by):
    b = by[k]; cum += b["w"]
    print(DAYS[k], b["n"], b["dec"], b["w"], cum, f"{b['w']/max(1,b['n']-b['dec']):.2f}", f"{st.median(b['rat']):.2f}" if b["rat"] else "-",
          f"{st.mean(b['shift']):+.3f}", f"{st.mean(b['wp'])/100:.1f}" if b["wp"] else "-", f"{st.mean(b['wref']):.2f}" if b["wref"] else "-")
# win rate vs price relative to the reference fee
print("\nquote/ref fee bucket | quoted | won | win rate")
edges = [0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.7, 2.0, 99]
for a, z in zip(edges, edges[1:]):
    s = [r for r in rows if r[1] and a <= r[1] < z]
    if s: print(f"{a}-{z}", len(s), sum(r[2] for r in s), f"{sum(r[2] for r in s)/len(s):.2f}")
print("\nmin quote/list bucket | quoted | won | win rate")
edges = [0, 1.0, 1.2, 1.3, 1.4, 1.5, 1.6, 1.8, 99]
for a, z in zip(edges, edges[1:]):
    s = [r for r in rows if r[0] and a <= r[0] < z]
    if s: print(f"{a}-{z}", len(s), sum(r[2] for r in s), f"{sum(r[2] for r in s)/len(s):.2f}")
# driver fee per order against the reference fee
orders = {o["orderId"] for o in rev["orders"]}
per_order, pair = [], 0
for g, oids in posts.items():
    if g not in fees_by_gig: continue
    oids = [o for o in oids if o in ref]
    if len(oids) > 1: pair += 1
    tot = sum(ref[o] for o in oids)
    for o in oids: per_order.append(fees_by_gig[g] * ref[o] / tot / ref[o])
print("\ngigs paid", len(fees_by_gig), "of which with 2+ orders", pair, "| paid fee / reference fee per order: median",
      f"{st.median(per_order):.2f}", "mean", f"{st.mean(per_order):.2f}", "p25/p75",
      [f"{x:.2f}" for x in st.quantiles(per_order, n=4)[::2]])
print("fees total €", sum(fees_by_gig.values()) / 100, "per won order €", sum(fees_by_gig.values()) / 100 / 350)
print("won orders: mean ref fee €", st.mean(ref[o] for o in orders) / 100, "| all requests: mean ref fee €", st.mean(ref.values()) / 100)
