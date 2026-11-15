import json, glob, statistics as st, collections
seen = {}
for f in sorted(glob.glob('boards/board-*.json')):
    d = json.load(open(f))
    for key in ('previous', 'current'):
        if d.get(key): seen[d[key]['name']] = d[key]
names = sorted(seen, key=lambda n: seen[n]['startedAt'])
T = {}
for n in names:
    T[n] = [t for t in seen[n]['teams'] if t.get('played') == 5 and t['name'] != 'House starter' and all(r.get('marginCents') is not None for r in t['runs'])]
    for t in T[n]: t['runs'].sort(key=lambda r: r['run'])
for n in names:
    ts = T[n]; ranked = sorted([t for t in ts if t['ranked']], key=lambda t: -t['marginCents']); un = [t for t in ts if not t['ranked']]
    print(f"== {n}: {len(ts)} teams finished, {len(ranked)} ranked, {len(un)} not ranked")
    for lab, t in (('1st', ranked[0]), ('3rd', ranked[2]), ('10th', ranked[9])):
        print(f"  {lab}: {t['name']}: {t['marginCents']/500:.0f} a week on {sum(r['wonOrders'] for r in t['runs'])/5:.0f} orders, {t['onTimeShare']*100:.1f}% on time, lowest week {min(r['onTimeShare'] for r in t['runs'])*100:.1f}%")
    t10 = ranked[9]['marginCents']
    # unranked teams whose five-week margin would have been top 10
    hi = [t for t in un if sum(r['marginCents'] for r in t['runs']) >= t10]
    print(f"  not ranked with a five-week margin at or above 10th: {len(hi)}: " + ', '.join(f"{t['name']} {sum(r['marginCents'] for r in t['runs'])/500:.0f}/wk ({sum(r['onTimeShare']<0.9 for r in t['runs'])} weeks under 90%, lowest {min(r['onTimeShare'] for r in t['runs'])*100:.1f}%)" for t in hi))
    # by five-week margin regardless of ranking: the 10, 15 and 20 highest; their weeks under 90
    allm = sorted(ts, key=lambda t: -sum(r['marginCents'] for r in t['runs']))
    for k in (10, 20):
        v = allm[:k]; w = [r for t in v for r in t['runs']]
        print(f"  the {k} highest five-week margins, ranked or not: {sum(r['onTimeShare']<0.9 for r in w)} of {len(w)} weeks under 90%, {sum(r['onTimeShare']<0.92 for r in w)} under 92%, {sum(1 for t in v if not t['ranked'])} teams not ranked")
    # one week at a time: the 10 highest margins of each week, valid or not
    bad = tot = bad92 = 0
    for i in range(5):
        v = sorted(ts, key=lambda t: -t['runs'][i]['marginCents'])[:10]
        bad += sum(t['runs'][i]['onTimeShare'] < 0.9 for t in v); bad92 += sum(t['runs'][i]['onTimeShare'] < 0.92 for t in v); tot += 10
    print(f"  the 10 highest margins of each single week, valid or not: {bad} of {tot} under 90%, {bad92} under 92%")
    lows = sorted(min(r['onTimeShare'] for r in t['runs']) for t in ranked[:10]); print(f"  ranked top 10: lowest weeks {', '.join(f'{x*100:.1f}' for x in lows)}; late share mean {1-st.mean(t['onTimeShare'] for t in ranked[:10]):.3f}")
    allw = [r for t in ts for r in t['runs']]
    print(f"  whole field: {sum(r['onTimeShare']<0.9 for r in allw)} of {len(allw)} weeks under 90% ({60*sum(r['onTimeShare']<0.9 for r in allw)/len(allw):.1f} per 60); teams at the week's median orders or more: {sum(1 for t in ts for i in range(5) if t['runs'][i]['wonOrders']>=st.median(x['runs'][i]['wonOrders'] for x in ts) and t['runs'][i]['onTimeShare']<0.9)} under 90%")
# follow the earlier round's top 10 into the later round
a, b = names[0], names[-1]
top = [t['team'] for t in sorted([t for t in T[a] if t['ranked']], key=lambda t: -t['marginCents'])[:10]]
nxt = [t for t in T[b] if t['team'] in top]; w = [r for t in nxt for r in t['runs']]
print(f"\nThe top 10 of {a} in {b}: {len(nxt)} teams finished, {sum(1 for t in nxt if t['ranked'])} ranked; {sum(r['onTimeShare']<0.9 for r in w)} of {len(w)} weeks under 90%, {sum(r['onTimeShare']<0.92 for r in w)} under 92%, {st.mean(r['wonOrders'] for r in w):.0f} orders a week")
top20 = [t['team'] for t in sorted([t for t in T[a]], key=lambda t: -sum(r['marginCents'] for r in t['runs']))[:20]]
nxt = [t for t in T[b] if t['team'] in top20]; w = [r for t in nxt for r in t['runs']]
print(f"The 20 highest margins of {a}, ranked or not, in {b}: {len(nxt)} teams, {sum(r['onTimeShare']<0.9 for r in w)} of {len(w)} weeks under 90%, {sum(r['onTimeShare']<0.92 for r in w)} under 92%")
