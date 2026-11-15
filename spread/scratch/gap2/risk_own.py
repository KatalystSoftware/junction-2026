"""Our own played weeks (trackb-rounds row files): weeks under 90% as orders rise, by orders per 100 drivers."""
import csv, glob, collections, statistics as st, math
rows = {}
for f in glob.glob('rounds/*.csv'):
    for r in csv.DictReader(open(f)):
        try: rows[(r['variant'], r['seed'])] = dict(v=r['variant'], seed=r['seed'], d=int(r['drivers']), o=int(r['orders']), ot=float(r['on_time']) if 'on_time' in r else float(r['on_time_share']), m=float(r['margin']))
        except Exception as e: err = (f, e, list(r)[:12])
R = list(rows.values())
if not R: print(err); raise SystemExit
for r in R:
    if r['ot'] > 1.5: r['ot'] /= 100
    if r['m'] > 200000: r['m'] /= 100
print(len(R), 'played weeks,', len({r['v'] for r in R}), 'variants; orders', st.mean(r['o'] for r in R), 'on time', st.mean(r['ot'] for r in R), 'margin', st.mean(r['m'] for r in R))
def tab(key, edges, label, sel=lambda r: True):
    print(f'\n{label}')
    print('  band        weeks  orders  drivers  under 90%  per 60  under 92%  mean on time  margin')
    for lo, hi in zip(edges, edges[1:]):
        v = [r for r in R if sel(r) and lo <= key(r) < hi]
        if len(v) < 15: continue
        f = sum(r['ot'] < 0.9 for r in v)
        print(f"  {lo:5.0f}-{hi:5.0f} {len(v):6d} {st.mean(r['o'] for r in v):7.0f} {st.mean(r['d'] for r in v):8.0f} {f:6d} {f/len(v):5.1%} {60*f/len(v):6.1f} {sum(r['ot']<0.92 for r in v)/len(v):9.1%} {st.mean(r['ot'] for r in v):12.1%} {st.mean(r['m'] for r in v):8.0f}")
tab(lambda r: 100 * r['o'] / r['d'], [0, 34, 38, 42, 46, 50, 54, 58, 100], 'By orders per 100 drivers, all played weeks in the row files')
tab(lambda r: r['o'], [0, 260, 300, 330, 360, 390, 420, 600], 'By orders')
tab(lambda r: 100 * r['o'] / r['d'], [0, 38, 42, 46, 50, 54, 100], '... worlds with 760 drivers or more', lambda r: r['d'] >= 760)
tab(lambda r: 100 * r['o'] / r['d'], [0, 38, 42, 46, 50, 54, 100], '... worlds under 760 drivers', lambda r: r['d'] < 760)
# logistic fit of a week under 90% on orders per 100 drivers
import random
def fit(X, y, it=4000, lr=0.05):
    a, b = -4.0, 0.0; mx = st.mean(X); sx = st.pstdev(X)
    Z = [(x - mx) / sx for x in X]
    for _ in range(it):
        ga = gb = 0
        for z, t in zip(Z, y):
            p = 1 / (1 + math.exp(-(a + b * z))); ga += p - t; gb += (p - t) * z
        a -= lr * ga / len(Z) * 10; b -= lr * gb / len(Z) * 10
    return lambda x: 1 / (1 + math.exp(-(a + b * (x - mx) / sx))), b / sx
X = [100 * r['o'] / r['d'] for r in R]; y = [r['ot'] < 0.9 for r in R]
p, slope = fit(X, y)
print(f'\nLogistic fit, a week under 90% against orders per 100 drivers ({sum(y)} such weeks of {len(y)}): odds x{math.exp(slope*5):.2f} for each 5 more orders per 100 drivers')
for x in (40, 44, 48, 52, 56, 60, 64): print(f'  {x} per 100 drivers: {p(x):.1%} of weeks, {60*p(x):.1f} per 60')
print('\nlate orders a week against orders, same seed, across arms (within-seed slope): extra late orders for each extra order')
by = collections.defaultdict(list)
for r in R: by[r['seed']].append(r)
num = den = 0
for s, v in by.items():
    if len(v) < 2: continue
    mo = st.mean(r['o'] for r in v); ml = st.mean(r['o'] * (1 - r['ot']) for r in v)
    for r in v: num += (r['o'] - mo) * (r['o'] * (1 - r['ot']) - ml); den += (r['o'] - mo) ** 2
print(f'  {num/den:.3f} late for each extra order, over {sum(len(v) for v in by.values() if len(v)>1)} weeks on {sum(1 for v in by.values() if len(v)>1)} seeds')
num = den = 0
for s, v in by.items():
    if len(v) < 2: continue
    mo = st.mean(r['o'] for r in v); mm = st.mean(r['m'] for r in v)
    for r in v: num += (r['o'] - mo) * (r['m'] - mm); den += (r['o'] - mo) ** 2
print(f'  {num/den:.1f} euros of margin for each extra order, within a seed across our arms')
