"""The test final's (or the final's) standings from Bahn's public stream: price and cost an order for each team, and the gap to a place split into volume, price and cost.
    python3 -I split.py lb-last.json"""
import json, sys, statistics as st, math
m = json.load(open(sys.argv[1])); T = [t for t in m['teams'] if t['wonOrders'] > 0]
R = sorted([t for t in T if t['ranked']], key=lambda t: -t['marginCents'])
def f(t):
    o = t['wonOrders']; return dict(name=t['name'], m=t['marginCents'] / 100, o=o, rev=t['revenueCents'] / 100 / o, cost=(t['revenueCents'] - t['marginCents']) / 100 / o, mo=t['marginCents'] / 100 / o, ot=t['onTimeShare'], und=t['undeliveredShare'], share=t['marginShare'])
F = [f(t) for t in R]; us = [x for x in F if x['name'].lower() == 'katalyst'][0]; ui = F.index(us) + 1
print(f"{m['status']}, {len(m['teams'])} teams listed, {len(T)} won an order, {len(R)} ranked, {sum(1 for t in T if t['onTimeShare'] < 0.9)} under 90%")
print('place team                      margin orders  price/order cost/order margin/order margin share on time')
for i, x in enumerate(F, 1):
    if i <= 15 or x is us or 'ouse' in x['name'].lower(): print(f"{i:4d} {x['name'][:24]:24s} {x['m']:8.0f} {x['o']:5d} {x['rev']:10.1f} {x['cost']:10.1f} {x['mo']:10.1f} {x['share']:10.1%} {x['ot']:8.1%}")
for t in T:
    if 'ouse' in t['name'].lower() and not t['ranked']: x = f(t); print(f"   - {x['name'][:24]:24s} {x['m']:8.0f} {x['o']:5d} {x['rev']:10.1f} {x['cost']:10.1f} {x['mo']:10.1f} {x['share']:10.1%} {x['ot']:8.1%} (not ranked)")
def mean(v, k): return st.mean(x[k] for x in v)
def split(label, v):
    o, rev, cost = mean(v, 'o'), mean(v, 'rev'), mean(v, 'cost'); gap = mean(v, 'm') - us['m']
    vol = (o - us['o']) * us['mo']; price = (rev - us['rev']) * o; c = -(cost - us['cost']) * o
    print(f"{label}: margin {mean(v,'m'):.0f}, {o:.0f} orders, price {rev:.1f}, cost {cost:.1f}, margin an order {mean(v,'mo'):.1f}, on time {mean(v,'ot'):.1%}")
    print(f"   gap {gap:+.0f} = volume {vol:+.0f} ({o-us['o']:+.0f} orders at our {us['mo']:.1f}) + price {price:+.0f} ({rev-us['rev']:+.1f} an order) + cost {c:+.0f} ({cost-us['cost']:+.1f} an order)")
print(f"\nus: place {ui}, margin {us['m']:.0f}, {us['o']} orders, price {us['rev']:.1f}, cost {us['cost']:.1f}, margin an order {us['mo']:.1f}, margin share {us['share']:.1%}, on time {us['ot']:.1%}")
split('1st', F[:1]); split('top 5', F[:5]); split('top 10', F[:10]); split('10th', F[9:10]); split('places 8 to 12', F[7:12])
# across ranked teams: price and cost an order against orders
xs = [x['o'] for x in F]
for k in ('rev', 'cost', 'mo'):
    ys = [x[k] for x in F]; mx, my = st.mean(xs), st.mean(ys)
    b = sum((a - mx) * (c - my) for a, c in zip(xs, ys)) / sum((a - mx) ** 2 for a in xs)
    r = b * math.sqrt(sum((a - mx) ** 2 for a in xs) / sum((c - my) ** 2 for c in ys))
    print(f"ranked teams: {k} an order falls by {-100*b:.1f} for each 100 more orders (r {r:.2f})")
ys = [x['m'] for x in F]; mx, my = st.mean(xs), st.mean(ys); b = sum((a - mx) * (c - my) for a, c in zip(xs, ys)) / sum((a - mx) ** 2 for a in xs)
print(f"ranked teams: margin rises {b:.1f} for each extra order; median orders {st.median(xs):.0f}, ours {us['o']}; teams with more orders than us: {sum(x['o'] > us['o'] for x in F)} of {len(F)}")
print('by orders band (ranked): teams, price, cost, margin an order, on time, margin')
for lo, hi in ((0, 220), (220, 280), (280, 340), (340, 400), (400, 460), (460, 999)):
    v = [x for x in F if lo <= x['o'] < hi]
    if v: print(f"  {lo}-{hi}: {len(v)} teams, price {mean(v,'rev'):.1f}, cost {mean(v,'cost'):.1f}, margin {mean(v,'mo'):.1f}, on time {mean(v,'ot'):.1%}, margin {mean(v,'m'):.0f}")
bad = [f(t) for t in T if t['onTimeShare'] < 0.9]
print('under 90%:', len(bad), 'teams; their orders:', sorted(x['o'] for x in bad))
