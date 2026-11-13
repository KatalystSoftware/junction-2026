"""Scratch: what the fixed numbers are worth against a choice per week, per day and per dealer group, from saved weeks only."""
import collections, json, statistics as st
from spreadlab import ledger
from spreadlab.play import load_run
from spreadlab.server import near_places, world_map
near = near_places(world_map())
S = json.load(open("catalogue/seeds.json"))
cat = json.load(open("catalogue/catalogue.json"))
cat = cat if isinstance(cat, list) else cat.get("weeks", cat)
drivers = {w["seed"]: w["drivers"] for w in cat if isinstance(w, dict) and "seed" in w}
def score(v, s):
    try:
        return json.load(open(f"{__import__('os').environ['SPREAD_DATA']}/runs/{v}/{s}-L8.score.json"))["score"]
    except FileNotFoundError:
        return None
def m(sc): return sc["marginCents"] / 100 if sc["ranked"] else 0
for name, seeds, vs in (("tune gates", S["tune"][:10], ["gate-5", "gate-10", "gate-15"]), ("holdout gates", S["holdout"][:10], ["gate-5", "gate-10"]),
                        ("tune floors, 60% cap", S["tune"][:10], ["floor-1.5", "floor-1.7", "floor-1.9"]), ("holdout floors", S["holdout"][:10], ["floor-1.5", "floor-1.7"]),
                        ("tune floor with gate 10", S["tune"][:10], ["floor-1.5-gate-10", "gate-10"])):
    tab = {s: {v: score(v, s) for v in vs} for s in seeds}
    means = {v: st.mean(m(tab[s][v]) for s in seeds) for v in vs}
    best = st.mean(max(m(tab[s][v]) for v in vs) for s in seeds)
    wins = collections.Counter(max(vs, key=lambda v: m(tab[s][v])) for s in seeds)
    print(f"\n{name}: " + "  ".join(f"{v} {means[v]:.0f}" for v in vs) + f"  | best per week {best:.0f}  | best in {dict(wins)}")
    if name == "tune floor with gate 10":
        for s in seeds:
            print(f"   {s} drivers {drivers.get(s)} cars/driver {1035/drivers[s]:.2f}  " + "  ".join(f"{v} {m(tab[s][v]):6.0f} {100*tab[s][v]['onTimeShare']:.1f}%" for v in vs))
        for cut in (1.2, 1.3, 1.4):
            print(f"   rule: floor 1.5 under {cut} cars/driver, else 1.7 -> {st.mean(m(tab[s]['floor-1.5-gate-10' if 1035/drivers[s] < cut else 'gate-10']) for s in seeds):.0f}")
# gate-10: by day and dealer group, on tune + holdout
rows = []
for s in S["tune"][:10] + S["holdout"][:10]:
    run = load_run("gate-10", s); played = ledger.week(run, near)
    reqs = {r["request"]["id"]: r["request"] for r in run["reveal"]["requests"]}
    n = collections.Counter(q["dealerId"] for q in reqs.values()); big = {d for d, _ in n.most_common(2)}
    for id_, row in played["requests"].items():
        d = run["decisions"][id_]
        if d["declined"]: continue
        q = reqs[id_]; won = row["outcome"] == "won"
        o = {o["kind"]: o for o in q["options"]}
        bind = any(p > round(o[k]["listPriceCents"] * 1.5) for k, p in d["prices"].items())
        mult = min(p / q["referenceFeeCents"] for p in d["prices"].values())
        margin = (row["price"] - row["fees"] - row["costs"] - row["late"]) / 100 if won else 0
        rows.append(dict(seed=s, day=row["day"], big=row["dealer"] in big, dealer=row["dealer"], won=won, margin=margin, bind=bind, mult=mult, sit=row["situation"]))
def show(title, key):
    print(f"\n{title}\n  {'group':24s} quotes  win%  margin/wk  margin/won")
    g = collections.defaultdict(list)
    for r in rows: g[key(r)].append(r)
    for k in sorted(g, key=str):
        b = g[k]; w = [r for r in b if r["won"]]
        print(f"  {str(k):24s} {len(b):6d} {100*len(w)/len(b):5.1f} {sum(r['margin'] for r in b)/20:9.0f} {sum(r['margin'] for r in w)/max(1,len(w)):9.1f}")
print(f"\ngate-10, 20 weeks: {len(rows)} quotes")
show("which price applied", lambda r: "floor 1.7x fee" if r["bind"] else "1.5x list")
show("quote over typical fee", lambda r: next(f"{lo:.1f}-{hi:.1f}" for lo, hi in zip([0, 1.7, 1.75, 1.9, 2.1, 2.5], [1.7, 1.75, 1.9, 2.1, 2.5, 99]) if lo <= r["mult"] < hi))
show("dealer group", lambda r: "two largest" if r["big"] else "others")
show("situation", lambda r: r["sit"])
show("day", lambda r: r["day"])
cells = collections.defaultdict(list)
for r in rows: cells[(r["seed"], r["day"])].append(r)
rates = sorted(100 * sum(r["won"] for r in b) / len(b) for b in cells.values() if len(b) >= 30)
print(f"\nwin rate by week-day ({len(rates)} days with 30+ quotes): min {rates[0]:.0f}%  p10 {rates[len(rates)//10]:.0f}%  median {rates[len(rates)//2]:.0f}%  p90 {rates[9*len(rates)//10]:.0f}%  max {rates[-1]:.0f}%")
for lo, hi in ((0, 10), (10, 20), (20, 35), (35, 50), (50, 101)):
    b = [r for k, c in cells.items() if len(c) >= 30 and lo <= 100 * sum(x["won"] for x in c) / len(c) < hi for r in c]
    nd = sum(1 for c in cells.values() if len(c) >= 30 and lo <= 100 * sum(x["won"] for x in c) / len(c) < hi)
    w = [r for r in b if r["won"]]
    if b: print(f"  days winning {lo}-{hi}%: {nd} days, {len(b)} quotes, margin/wk {sum(r['margin'] for r in b)/20:.0f}, margin/won {sum(r['margin'] for r in w)/max(1,len(w)):.1f}")
dc = collections.defaultdict(list)
for r in rows:
    if r["big"]: dc[(r["seed"], r["dealer"], r["day"])].append(r)
rr = sorted(100 * sum(x["won"] for x in c) / len(c) for c in dc.values() if len(c) >= 15)
print(f"large dealer x day ({len(rr)} cells with 15+ quotes): p10 {rr[len(rr)//10]:.0f}% median {rr[len(rr)//2]:.0f}% p90 {rr[9*len(rr)//10]:.0f}%")
