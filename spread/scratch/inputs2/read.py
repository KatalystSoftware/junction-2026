"""Tables from passes.py's output."""
import json, sys
from collections import defaultdict
rows = [r for f in sys.argv[1:] for r in json.load(open(f))]
W = len(rows)
print(f"{W} weeks, {sum(r['orders'] for r in rows)/W:.0f} orders a week, {sum(r['late'] for r in rows)/W:.1f} late; under 90%: {sum(r['late']/r['orders'] > .10 for r in rows)}, under 92%: {sum(r['late']/r['orders'] > .08 for r in rows)}")
CATS = ["held due today dropped", "held due today kept", "waiting due today", "won today due today", "won today due next day", "won today due later", "held later dropped", "held later", "waiting later"]
def band(d):
    return "wave 10+" if d["drops"] >= 10 else "5 to 9" if d["drops"] >= 5 else "0 to 4"
for name, pick in (("all weeks", lambda r: True), ("under 720 drivers", lambda r: r["drivers"] < 720), ("720 or more", lambda r: r["drivers"] >= 720)):
    t = defaultdict(lambda: defaultdict(lambda: [0, 0])); nd = defaultdict(int)
    wk = [r for r in rows if pick(r)]
    for r in wk:
        for d in r["days"]:
            b = band(d); nd[b] += 1
            for c, (n, l) in d["cat"].items():
                t[b][c][0] += n; t[b][c][1] += l
    print(f"\n== {name}: {len(wk)} weeks. Days Tue-Fri by the first hour's drops; cars a day, late share")
    print(f"{'':28s}" + "".join(f"{b + ' (' + str(nd[b]) + ' days)':>26s}" for b in ("0 to 4", "5 to 9", "wave 10+")))
    for c in CATS:
        print(f"{c:28s}" + "".join(f"{t[b][c][0] / max(nd[b], 1):12.1f} {100 * t[b][c][1] / max(t[b][c][0], 1):11.1f}%" for b in ("0 to 4", "5 to 9", "wave 10+")))
    for b in ("0 to 4", "5 to 9", "wave 10+"):
        tot = sum(t[b][c][1] for c in CATS[:5]); print(f"  {b}: late orders a day among today's cars and today's wins: {tot / max(nd[b], 1):.2f}")
# the wave by weekday, and weeks by wave
by = defaultdict(int)
for r in rows:
    ds = [d["day"] for d in r["days"] if d["drops"] >= 10]
    by[tuple(ds)] += 1
print("\nweeks by wave days (1=Tue..4=Fri):", dict(sorted(by.items(), key=lambda kv: -kv[1])))
wave = [r for r in rows if any(d["drops"] >= 10 for d in r["days"])]
calm = [r for r in rows if not any(d["drops"] >= 10 for d in r["days"])]
for nm, g in (("wave weeks", wave), ("no wave", calm)):
    if g: print(f"{nm}: {len(g)} weeks, late share {sum(r['late'] for r in g) / sum(r['orders'] for r in g):.3%}, under 90%: {sum(r['late']/r['orders'] > .10 for r in g)}, under 92%: {sum(r['late']/r['orders'] > .08 for r in g)}")
# share of the held cars due today that drop in the first hour: wave against calm
import statistics
sh = defaultdict(list)
for r in rows:
    for d in r["days"]:
        if d["held_today"] >= 5:
            sh[band(d)].append(d["cat"].get("held due today dropped", [0, 0])[0] / d["held_today"])
print("share of held cars due today dropped in the first hour (days with 5+ held):", {k: (len(v), round(statistics.mean(v), 3), round(statistics.median(v), 3)) for k, v in sh.items()})
# after a wave: the later days of the week
aft = defaultdict(lambda: [0, 0, 0])
for r in rows:
    first = next((d["day"] for d in r["days"] if d["drops"] >= 10), None)
    for d in r["days"]:
        key = "no wave yet or never" if first is None or d["day"] < first else "wave day" if d["day"] == first else "after the wave"
        n = sum(d["cat"].get(c, [0, 0])[0] for c in CATS[3:6]); l = sum(d["cat"].get(c, [0, 0])[1] for c in CATS[3:6])
        aft[key][0] += n; aft[key][1] += l; aft[key][2] += 1
print("orders won on a day, late share:", {k: (v[2], round(v[0] / v[2], 1), f"{v[1] / v[0]:.2%}") for k, v in aft.items()})
# positions
b = defaultdict(lambda: defaultdict(float)); o = defaultdict(lambda: defaultdict(float)); ch = defaultdict(float)
for r in rows:
    for k, v in r["books"].items():
        for kk, vv in v.items(): b[k][kk] += vv
    for k, v in r["offers"].items():
        for kk, vv in v.items(): o[k][kk] += vv
    for k, v in r["chances"].items(): ch[k] += v
print("\n== bookings of one-car gigs by whether the driver delivered one of the desk's cars within 30 km of the pickup in the 4 hours before (same day)")
for k, v in b.items():
    n = v["n"]; print(f"  near={k}: {n / W:.1f} a week, fee paid {v['ratio'] / n:.3f} x typical, minutes from post to booking {v['wait'] / n:.0f}, late {v['late'] / n:.2%}, hours left {v['hours'] / n:.1f}, home near pickup {v['home_pickup'] / n:.2%}, home near delivery {v['home_delivery'] / n:.2%}")
print("== direct offers by (driver just delivered nearby, driver delivered a car of the desk today, answer)")
tot = defaultdict(lambda: defaultdict(float))
for k, v in o.items():
    near, worked, ans = eval(k); tot[(near, worked)][ans] += v["n"]
for k, v in sorted(tot.items()):
    s = sum(v.values()); print(f"  near={k[0]} worked today={k[1]}: {s / W:.1f} offers a week, accepted {v.get('accepted', 0) / s:.2%}, declined (read) {v.get('declined', 0) / s:.2%}, expired {v.get('expired', 0) / s:.2%}")
print("== at each delivery by a driver of the desk:", {k: round(v / W, 1) for k, v in ch.items()}, "a week")
