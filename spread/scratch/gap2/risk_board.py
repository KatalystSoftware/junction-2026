"""Across teams and weeks on the board: how the share of weeks under 90% rises with orders, and what a place needs in one week."""
import json, sys, glob, statistics as st, collections
seen = {}
for f in sorted(glob.glob('boards/board-*.json')):
    d = json.load(open(f))
    for key in ('previous', 'current'):
        r = d.get(key)
        if r: seen[r['name']] = r   # the latest read of each round wins
obs = []; need = []
for name, rnd in seen.items():
    T = [t for t in rnd['teams'] if t.get('played') == 5 and all(r.get('marginCents') is not None for r in t['runs'])]
    for t in T: t['runs'].sort(key=lambda r: r['run'])
    hb = [t for t in T if t['name'] == 'House best']
    us = [t for t in T if t['team'] == 'katalyst']
    print(f'== {name}: {len(T)} teams with five weeks')
    for i in range(5):
        runs = [(t, t['runs'][i]) for t in T if t['name'] != 'House starter']
        med = st.median(r['wonOrders'] for _, r in runs)
        ok = sorted((r for _, r in runs if r['onTimeShare'] >= 0.9 and r['wonOrders'] > 0), key=lambda r: -r['marginCents'])
        h = hb[0]['runs'][i] if hb else None; u = us[0]['runs'][i] if us else None
        for t, r in runs:
            obs.append(dict(rnd=name, run=i, team=t['team'], orders=r['wonOrders'], rel=r['wonOrders'] / med, relhb=r['wonOrders'] / h['wonOrders'] if h else None,
                            ot=r['onTimeShare'], m=r['marginCents'] / 100, relus=r['wonOrders'] / u['wonOrders'] if u else None))
        if u:
            top = ok[0]; t3 = ok[2]; t10 = ok[9]
            need.append(dict(rnd=name, run=i, us=u['marginCents'] / 100, us_o=u['wonOrders'], first=top['marginCents'] / 100, first_o=top['wonOrders'], third=t3['marginCents'] / 100,
                             tenth=t10['marginCents'] / 100, o10=st.mean(r['wonOrders'] for r in ok[5:15]), o1=st.mean(r['wonOrders'] for r in ok[:3]), hb=h['marginCents'] / 100,
                             ot1=st.mean(r['onTimeShare'] for r in ok[:3]), ot10=st.mean(r['onTimeShare'] for r in ok[5:15]), valid=len(ok)))
            n = need[-1]
            print(f"  week {i+1}: us {n['us']:.0f} on {n['us_o']}; 10th {n['tenth']:.0f} (x{n['tenth']/n['us']:.2f}), places 6-15 win {n['o10']:.0f} orders (x{n['o10']/n['us_o']:.2f}) at {n['ot10']*100:.1f}%; 1st {n['first']:.0f} (x{n['first']/n['us']:.2f}), top 3 win {n['o1']:.0f} (x{n['o1']/n['us_o']:.2f}) at {n['ot1']*100:.1f}%; valid teams {n['valid']}")
print('\nOne week, over all weeks we played: margin needed over ours, mean and range')
for k, ok_ in (('tenth', 'o10'), ('third', None), ('first', 'o1')):
    xs = [n[k] / n['us'] for n in need]; d = [n[k] - n['us'] for n in need]
    line = f"  {k:6s}: x{st.mean(xs):.2f} ({min(xs):.2f} to {max(xs):.2f}), +{st.mean(d):.0f} euros a week ({min(d):.0f} to {max(d):.0f})"
    if ok_: line += f"; orders x{st.mean(n[ok_]/n['us_o'] for n in need):.2f} of ours ({min(n[ok_]/n['us_o'] for n in need):.2f} to {max(n[ok_]/n['us_o'] for n in need):.2f})"
    print(line)
for rname in seen:
    nn = [n for n in need if n['rnd'] == rname]
    if nn: print(f"  {rname}: 10th x{st.mean(n['tenth']/n['us'] for n in nn):.2f}, 1st x{st.mean(n['first']/n['us'] for n in nn):.2f}; orders of places 6-15 x{st.mean(n['o10']/n['us_o'] for n in nn):.2f}, of top 3 x{st.mean(n['o1']/n['us_o'] for n in nn):.2f}")
def table(key, edges, label):
    print(f'\nWeeks under 90% by orders {label} (all teams but House starter, {len(obs)} team-weeks)')
    print('  band            team-weeks  under 90%  per 60   under 92%   mean on time   median margin over the week\'s median')
    for lo, hi in zip(edges, edges[1:]):
        v = [o for o in obs if o[key] is not None and lo <= o[key] < hi]
        if len(v) < 8: continue
        f90 = sum(o['ot'] < 0.9 for o in v); f92 = sum(o['ot'] < 0.92 for o in v)
        print(f'  {lo:4.2f} to {hi:4.2f}  {len(v):8d}  {f90:5d} {f90/len(v):6.1%}  {60*f90/len(v):5.1f}  {f92/len(v):8.1%}  {st.mean(o["ot"] for o in v):10.1%}')
table('relus', [0, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.55, 1.8, 9], "over ours in the same week")
table('rel', [0, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 9], "over the week's median")
# margin against orders inside a week: among valid teams, margin over ours by order band over ours
print('\nMargin over ours in the same week, by orders over ours (valid team-weeks only): median, upper quartile, best')
for lo, hi in zip([0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.55], [1.0, 1.1, 1.2, 1.3, 1.4, 1.55, 1.8]):
    v = []
    for o in obs:
        if o['relus'] is None or not lo <= o['relus'] < hi or o['ot'] < 0.9: continue
        n = [x for x in need if x['rnd'] == o['rnd'] and x['run'] == o['run']][0]; v.append(o['m'] / n['us'])
    if len(v) >= 8:
        v.sort(); print(f'  {lo:4.2f} to {hi:4.2f}: {len(v):4d} team-weeks, median x{st.median(v):.2f}, upper quartile x{v[3*len(v)//4]:.2f}, best x{v[-1]:.2f}')
json.dump(obs, open('board-obs.json', 'w')); json.dump(need, open('board-need.json', 'w'))
