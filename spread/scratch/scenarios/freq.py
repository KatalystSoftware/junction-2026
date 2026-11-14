"""How often each scenario shows in the saved weeks of one variant, and what it cost there.

    python scratch/scenarios/freq.py <rows.json from extract.py>
"""
import collections, json, sys
import numpy as np

DAY, HOUR = 1440, 60
W = json.load(open(sys.argv[1]))
n = len(W)
margin = np.array([w["score"]["marginCents"] / 100 for w in W]); ontime = np.array([w["score"]["onTimeShare"] for w in W])
orders = np.array([w["score"]["wonOrders"] for w in W]); drivers = np.array([w["drivers"] for w in W])
print(f"{n} weeks of {W[0]['variant']}: margin mean {margin.mean():.0f} sd {margin.std():.0f} min {margin.min():.0f} 10% {np.quantile(margin, .1):.0f} median {np.median(margin):.0f} 90% {np.quantile(margin, .9):.0f} max {margin.max():.0f}")
print(f"  on time mean {ontime.mean():.4f} min {ontime.min():.4f} | under 90%: {(ontime < .9).sum()} under 91%: {(ontime < .91).sum()} under 92%: {(ontime < .92).sum()} | orders {orders.mean():.0f} sd {orders.std():.0f} | drivers {drivers.min()}-{drivers.max()}")
c = lambda a, b: np.corrcoef(a, b)[0, 1]
print(f"  corr margin~drivers {c(margin, drivers):+.2f} margin~orders {c(margin, orders):+.2f} ontime~drivers {c(ontime, drivers):+.2f} ontime~orders {c(ontime, orders):+.2f}")
for lo, hi in [(0, 680), (680, 720), (720, 760), (760, 820), (820, 880), (880, 2000)]:
    s = (drivers >= lo) & (drivers < hi)
    if s.sum(): print(f"  drivers {lo}-{hi}: weeks {s.sum():3d} margin {margin[s].mean():6.0f} orders {orders[s].mean():4.0f} on time {ontime[s].mean():.3f} lowest {ontime[s].min():.3f} under 92% {(ontime[s] < .92).mean():.2f}")

print("\n== events a week (mean; share of weeks with any) ==")
keys = ["gig_dropped", "no_show", "gig_expired", "deadline_close", "visit_failed", "order_changed", "order_cancelled", "forecast", "release", "failed_closed", "failed_not_ready", "failed_no_plates", "failed_licence"]
for k in keys:
    v = np.array([w["counts"].get(k, 0) for w in W]); print(f"  {k:18s} {v.mean():6.2f}  any {np.mean(v > 0):.2f}  max {v.max()}")
for k in ["cents_late_refund", "cents_failed_visit", "cents_release_fee", "cents_fine", "cents_waiting", "cents_undelivered_penalty"]:
    v = np.array([w["counts"].get(k, 0) for w in W]) / 100; print(f"  {k:26s} {v.mean():8.1f} euros a week")
print("  ledger kinds:", sorted({k for w in W for k in w["counts"] if k.startswith("cents_")}))

O = [dict(o, seed=w["seed"], drivers=w["drivers"]) for w in W for o in w["orders"] if not o["cancelled"]]
late = lambda rows: np.mean([o["late"] for o in rows]) if rows else float("nan")
def row(name, rows):
    if not rows: print(f"  {name:38s} none"); return
    m = np.mean([(o['price'] - o['fees'] - o['refund']) / 100 for o in rows])
    print(f"  {name:38s} {len(rows) / n:6.1f} a week  late {late(rows):.3f}  margin an order {m:6.1f}  refund per late {np.mean([o['refund'] for o in rows if o['late']] or [0]) / 100:5.1f}")
print(f"\n== won orders: {len(O) / n:.1f} a week, late {late(O):.4f} ==")
row("all", O)
row("snow forecast at pickup or delivery", [o for o in O if o["snow"]])
row("no snow", [o for o in O if not o["snow"]])
row("premium car", [o for o in O if o["premium"]]); row("electric", [o for o in O if o["electric"]])
row("with a note", [o for o in O if o["note"]]); row("no note", [o for o in O if not o["note"]])
row("note: ready later than the window", [o for o in O if o["ready_later"]])
row("note: handover after payment", [o for o in O if o["released"]])
row("note: plates", [o for o in O if o["plates"]]); row("note: manual", [o for o in O if o["manual"]]); row("note: summer tyres", [o for o in O if o["tyres"]])
row("note: tighter deadline", [o for o in O if o["notedeadline"]])
row("note: pickup hours differ", [o for o in O if o["hours_p"]]); row("note: delivery hours differ", [o for o in O if o["hours_d"]])
row("failed visit", [o for o in O if o["failed"]]); row("dropped once or more", [o for o in O if o["drops"]])
row("changed by the dealer or snow", [o for o in O if o["changed"]])
row("in a bulk batch", [o for o in O if o["batch"]])
for lo, hi in [(0, 5), (5, 20), (20, 50), (50, 100), (100, 10**6)]:
    row(f"drivers within 30 km of pickup {lo}-{hi}", [o for o in O if lo <= o["near"] < hi])
for d in range(5):
    row(f"won on {'Mon Tue Wed Thu Fri'.split()[d]}", [o for o in O if o["day"] == d])

# late causes
L = [o for o in O if o["late"]]
nodrv = [o for o in L if o["lastbook"] is None or o["lastbook"] > o["last"]]
print(f"\n== late orders {len(L) / n:.1f} a week: final driver after the last pickup minute or none {len(nodrv) / n:.1f}; with a failed visit {sum(1 for o in L if o['failed']) / n:.1f}; dropped {sum(1 for o in L if o['drops']) / n:.1f}; note deadline {sum(1 for o in L if o['notedeadline']) / n:.1f}; hours differ {sum(1 for o in L if o['hours_p'] or o['hours_d']) / n:.1f}; snow {sum(1 for o in L if o['snow']) / n:.1f}")

# bulk order
print("\n== bulk batches ==")
sizes, winsh, days, nears = [], [], [], []
for w in W:
    b = collections.defaultdict(list)
    for q in w["quotes"]:
        if q["batch"]: b[q["batch"]].append(q)
    for rows in b.values():
        sizes.append(len(rows)); winsh.append(np.mean([q["outcome"] == "won" for q in rows])); days.append(rows[0]["at"] // DAY); nears.append(w["near"].get(rows[0]["pick"], 0))
    if not b: sizes.append(0)
sizes = np.array(sizes)
print(f"  weeks with a batch {np.mean([any(q['batch'] for q in w['quotes']) for w in W]):.2f}; size median {np.median(sizes[sizes > 0]):.0f} range {sizes[sizes > 0].min()}-{sizes.max()}; won share {np.mean(winsh):.2f}; day counts {collections.Counter(days)}; drivers near the yard: median {np.median(nears):.0f} under 20 in {np.mean(np.array(nears) < 20):.2f}")
bo = [o for o in O if o["batch"]]
print(f"  declined for backlog inside a batch: {np.mean([q['declined'] == 'backlog' for w in W for q in w['quotes'] if q['batch']]):.2f} of its requests")

# requests by minute of day, and the quote funnel
at = np.array([q["at"] % DAY for w in W for q in w["quotes"]])
print(f"\n== requests {len(at) / n:.0f} a week: before 06:00 {np.mean(at < 360):.4f}, 06-08 {np.mean((at >= 360) & (at < 480)):.4f}, 08-09 {np.mean((at >= 480) & (at < 540)):.4f}, 18-22 {np.mean((at >= 1080) & (at < 1320)):.4f}, after 22:00 {np.mean(at >= 1320):.4f}; min {at.min()} max {at.max()}")
dec = collections.Counter(q["declined"] for w in W for q in w["quotes"])
print("  declined a week:", {k: round(v / n, 1) for k, v in dec.items()})
same = collections.Counter()
for w in W:
    t = collections.Counter(q["at"] for q in w["quotes"]); same.update(min(v, 50) // 5 * 5 for v in t.values())
print("  requests arriving in the same minute (size bucket -> minutes a week):", {k: round(v / n, 1) for k, v in sorted(same.items())})
