"""What a volume target costs in weeks under 90%: merge 1's played weeks, with the extra orders arriving late at the rate our own arms show on the same seed."""
import csv, glob, collections, statistics as st, random
rows = {}
for f in glob.glob('rounds/*.csv'):
    for r in csv.DictReader(open(f)):
        try: rows[(r['variant'], r['seed'])] = dict(v=r['variant'], seed=r['seed'], d=int(r['drivers']), o=int(r['orders']), late=float(r['late']), ot=float(r['on_time']), m=float(r['margin']), wave=r.get('drop_wave_days', ''))
        except Exception: pass
R = list(rows.values()); M1 = 'fee16-80-q24-wide-pairs-0.6-return-0.75'
by = collections.defaultdict(list)
for r in R: by[r['seed']].append(r)
def slope(sel, y='late'):
    num = den = n = 0
    for s, v in by.items():
        v = [r for r in v if sel(r)]
        if len(v) < 2: continue
        mo = st.mean(r['o'] for r in v); ml = st.mean(r[y] for r in v)
        for r in v: num += (r['o'] - mo) * (r[y] - ml); den += (r['o'] - mo) ** 2; n += 1
    return num / den, n
print('Extra late orders for each extra order, same seed across our arms:')
for label, sel in (('all', lambda r: True), ('760 drivers or more', lambda r: r['d'] >= 760), ('under 760', lambda r: r['d'] < 760), ('under 700', lambda r: r['d'] < 700)):
    s, n = slope(sel); m, _ = slope(sel, 'm'); print(f'  {label:22s} {s:.3f} late, {m:5.1f} euros of margin ({n} weeks)')
# pairs against merge 1 on the same seed: distribution of extra late per extra order where the arm won at least 15 more orders
pairs = []
for s, v in by.items():
    base = [r for r in v if r['v'] == M1]
    if not base: continue
    b = base[0]
    for r in v:
        if r['v'] != M1 and r['o'] - b['o'] >= 15: pairs.append(((r['late'] - b['late']) / (r['o'] - b['o']), b['d'], (r['m'] - b['m']) / (r['o'] - b['o']), r['v'], r['o'] - b['o']))
print(f'\nArms that won 15 or more orders above merge 1 on the same seed: {len(pairs)} weeks, {st.mean(p[4] for p in pairs):.0f} more orders')
for label, sel in (('760 or more', lambda p: p[1] >= 760), ('under 760', lambda p: p[1] < 760)):
    v = sorted(p[0] for p in pairs if sel(p))
    if len(v) > 5: print(f'  {label}: {len(v)} weeks; extra late per extra order: mean {st.mean(v):.3f}, median {st.median(v):.3f}, 9 in 10 under {v[int(0.9*len(v))]:.3f}, highest {v[-1]:.3f}; margin per extra order {st.mean(p[2] for p in pairs if sel(p)):.0f} euros')
print('  arms:', collections.Counter(p[3][-34:] for p in pairs).most_common(6))
base = [r for r in R if r['v'] == M1]
print(f'\nMerge 1: {len(base)} played weeks. Late share: 760 or more mean {st.mean(r["late"]/r["o"] for r in base if r["d"]>=760):.3f} sd {st.pstdev([r["late"]/r["o"] for r in base if r["d"]>=760]):.3f} highest {max(r["late"]/r["o"] for r in base if r["d"]>=760):.3f}; under 760 mean {st.mean(r["late"]/r["o"] for r in base if r["d"]<760):.3f} sd {st.pstdev([r["late"]/r["o"] for r in base if r["d"]<760]):.3f} highest {max(r["late"]/r["o"] for r in base if r["d"]<760):.3f}')
random.seed(1)
def sim(mult, rate_of, label):
    out = {}
    for name, sel in (('760 or more', lambda r: r['d'] >= 760), ('under 760', lambda r: r['d'] < 760)):
        v = [r for r in base if sel(r)]; bad = 0; n = 0
        for r in v:
            for _ in range(200):
                extra = r['o'] * (mult - 1); rate = rate_of(r)
                bad += (r['late'] + rate * extra) / (r['o'] + extra) > 0.10; n += 1
        out[name] = 60 * bad / n
    mix = 0.65 * out['760 or more'] + 0.35 * out['under 760']
    print(f"  x{mult:.2f} {label:44s} per 60 weeks: 760 or more {out['760 or more']:5.1f}, under 760 {out['under 760']:5.1f}, mix 65/35 {mix:5.1f}")
rich = [p[0] for p in pairs if p[1] >= 760]; thin = [p[0] for p in pairs if p[1] < 760]
print('\nWeeks under 90% per 60 if merge 1 won x times its orders (its own played weeks, extra orders late at the rate named):')
for mult in (1.0, 1.1, 1.2, 1.3, 1.4, 1.5):
    sim(mult, lambda r: 0.075, 'flat 0.075 (all arms, same seed)')
    sim(mult, lambda r: random.choice(rich if r['d'] >= 760 else thin), 'drawn from the arms above, by world')
    sim(mult, lambda r: 2 * random.choice(rich if r['d'] >= 760 else thin), 'twice that draw (rate rises with volume)')
    sim(mult, lambda r: max(0.075, 2.0 * r['late'] / r['o']), "twice the week's own late share")
