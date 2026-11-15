"""Item 1, offline: at what fee and how long before the last pickup did merge 1's late and warned cars book.
Reads the stand-in's packed weeks (release spread-standin-screen, unpacked): python3 -I item1.py <data>/standin [variant]"""
import gzip, json, sys, glob, os, collections, statistics as st
root = sys.argv[1]; variant = sys.argv[2] if len(sys.argv) > 2 else 'fee16-80-q24-wide-pairs-0.6-return-0.75'
files = sorted(glob.glob(f'{root}/weeks/{variant}/*.json.gz'))
H = 60
def bucket(x, edges):
    for e in edges:
        if x < e: return f'<{e}'
    return f'>={edges[-1]}'
rows = []; weeks = 0; wk = []
slices = collections.defaultdict(lambda: [0.0, 0])  # (hours-left bucket, fee bucket) -> [open gig-hours in 07-22, bookings]
for f in files:
    w = json.load(gzip.open(f)); seed = w['seed']
    world = json.load(gzip.open(f'{root}/worlds/{seed}.json.gz'))
    req = {r['id']: r for r in world['requests']}
    weeks += 1
    by_order = collections.defaultdict(list)
    for g in w['gigs']:
        cars = sorted({(s['orderId'], s['leg']) for s in g['stops'] if s['kind'] == 'pickup'})
        g['_orders'] = sorted({o for o, _ in cars})
        g['_ref'] = sum(req[o]['referenceFeeCents'] / len(req[o]['legs']) for o, _ in cars)
        for o in g['_orders']: by_order[o].append(g)
    refunds = collections.Counter(); fees = collections.Counter()
    for at, kind, cents, oid, gid in w['ledger']:
        if kind in ('late_refund', 'undelivered_penalty'): refunds[oid] -= cents
    nlate = 0
    for oid, o in w['orders'].items():
        if o['cancelled'] is not None: continue
        r = req[oid]; ref = r['referenceFeeCents']
        gigs = sorted(by_order.get(oid, []), key=lambda g: g['postedAt'])
        last = o['changed'][-1]['lastPickupAt'] if o['changed'] else o['lastPickupAt']
        books = sorted((b[0], b[2] / g['_ref'], len(g['_orders']), g) for g in gigs for b in g['booked'])
        drops = sorted(d[0] for g in gigs for d in g['dropped'])
        warned = o.get('warned', [])
        late = bool(o.get('late')); nlate += late
        done = [b for b in books if b[3]['status'] == 'done']
        fin = done[-1] if done else (books[-1] if books else None)
        legs = o.get('legs') or [{}]
        row = dict(seed=seed, oid=oid, drivers=w['drivers'], ref=ref, price=o['price'], option=o['option'], won=o['wonAt'], last=last, late=late,
                   refund=refunds[oid], warned=warned[0] if warned else None, nwarn=len(warned), nbook=len(books), ndrop=len(drops),
                   first=books[0][0] if books else None, fin_at=fin[0] if fin else None, fin_mult=fin[1] if fin else None, fin_cars=fin[2] if fin else None,
                   failed=sum(len(g['failed']) for g in gigs), changed=bool(o['changed']), note=any(l.get('noteDeadline') is not None for l in legs),
                   legs=len(r['legs']), private=any(l['pickup']['privateAddress'] or l['delivery']['privateAddress'] for l in r['legs']),
                   first_post=gigs[0]['postedAt'] if gigs else None,
                   open_mult=(gigs[0]['schedule'][0]['feeCents'] / gigs[0]['_ref']) if gigs else None)
        rows.append(row)
    wk.append((w['score']['orders'], nlate, w['drivers']))
    # booking chance an open one-car gig-hour, by hours to the last pickup and the fee shown, 07:00-22:00 only
    for g in w['gigs']:
        if len(g['_orders']) != 1 or not g['schedule']: continue
        o = w['orders'].get(g['_orders'][0])
        if not o: continue
        last = o['changed'][-1]['lastPickupAt'] if o['changed'] else o['lastPickupAt']
        ends = [b[0] for b in g['booked'][:1]] or [g['expired'] or min(last + 600, g['postedAt'] + 7 * 1440)]
        end = ends[0]; t = g['postedAt']
        sched = g['schedule']
        while t < end:
            if 7 * H <= t % 1440 < 22 * H:
                fee = sched[0]['feeCents']
                for s in sched:
                    if s['at'] <= t: fee = s['feeCents']
                k = (bucket((last - t) / H, [0, 3, 6, 12, 24, 48]), bucket(fee / g['_ref'], [0.85, 0.95, 1.05, 1.15, 1.25, 1.45, 1.75, 2.05, 2.35]))
                slices[k][0] += min(30, end - t) / H
                if g['booked'] and t + 30 >= end: slices[k][1] += 1
            t += 30
one = [r for r in rows if r['legs'] == 1]
n = len(rows); L = [r for r in rows if r['late']]
print(f'{variant}: {weeks} weeks, {n/weeks:.0f} orders a week, {len(L)/weeks:.1f} late ({len(L)/n:.1%}), refunds {sum(r["refund"] for r in L)/weeks/100:.0f} euros a week')
print(f'mean price {st.mean(r["price"] for r in rows)/100:.0f}, typical fee {st.mean(r["ref"] for r in rows)/100:.0f}, price over typical {sum(r["price"] for r in rows)/sum(r["ref"] for r in rows):.2f}; refund a late order {st.mean(r["refund"] for r in L)/100:.0f}')
def cause(r):
    if r['failed']: return 'failed visit'
    if r['note']: return "note's deadline"
    if r['changed']: return 'change of plan'
    if r['first'] is None or r['first'] > r['last']: return 'no driver before the last pickup'
    if r['warned'] is not None and r['first'] > r['warned']: return 'first driver only after the warning (last 3 h)'
    if r['ndrop']: return 'had a driver, dropped'
    return 'booked in time and kept, late anyway'
c = collections.Counter(cause(r) for r in L); cr = collections.Counter()
for r in L: cr[cause(r)] += r['refund']
print('\nWhy late (first cause that applies), a week:')
for k, v in c.most_common(): print(f'  {k:48s} {v/weeks:5.2f}  {v/len(L):5.1%}  refunds {cr[k]/weeks/100:5.0f}')
W = [r for r in rows if r['warned'] is not None]
print(f'\nWarned orders (deadline_close): {len(W)/weeks:.1f} a week, {sum(r["late"] for r in W)/len(W):.1%} of them late; they are {sum(r["late"] for r in W)/len(L):.1%} of all late orders')
W0 = [r for r in W if r['first'] is None or r['first'] > r['warned']]  # never had a driver before the warning
W1 = [r for r in W if r not in W0]
print(f'  never had a driver before the warning: {len(W0)/weeks:.1f} a week, {sum(r["late"] for r in W0)/max(1,len(W0)):.1%} late; had one and lost it: {len(W1)/weeks:.1f}, {sum(r["late"] for r in W1)/max(1,len(W1)):.1%} late')
print('  hours from the win (or first posting) to the warning, for those never booked before it: quartiles',
      [round(x, 1) for x in st.quantiles([(r['warned'] - (r['first_post'] or r['won'])) / H for r in W0], n=4)])
print('  ... typical fee quartiles (euros)', [round(x/100) for x in st.quantiles([r['ref'] for r in W0], n=4)], 'against all orders', [round(x/100) for x in st.quantiles([r['ref'] for r in rows], n=4)])
print('  ... price quartiles', [round(x/100) for x in st.quantiles([r['price'] for r in W0], n=4)], 'option', collections.Counter(r['option'] for r in W0).most_common())
print('\nAfter the warning, cars that had no driver before it: when and at what fee the first driver came')
tab = collections.defaultdict(lambda: [0, 0])
for r in W0:
    if r['first'] is None: k = ('never booked', '-')
    else:
        d = (r['first'] - r['warned']) / H
        k = (bucket(d, [0.5, 1, 2, 3, 6, 24]) + ' h after', '')
    tab[k][0] += 1; tab[k][1] += r['late']
for k in sorted(tab): print(f'  {k[0]:22s} {tab[k][0]/weeks:5.2f} a week  {tab[k][1]/tab[k][0]:5.1%} late')
ft = collections.defaultdict(lambda: [0, 0])
for r in W0:
    if r['fin_mult'] is not None: 
        k = bucket(r['fin_mult'], [1.25, 1.45, 1.75, 2.05, 2.35, 2.75]); ft[k][0] += 1; ft[k][1] += r['late']
print('  fee of the booking that moved the car, x typical fee:')
for k in sorted(ft, key=lambda s: float(s.strip('<>='))): print(f'    {k:8s} {ft[k][0]/weeks:5.2f} a week  {ft[k][1]/ft[k][0]:5.1%} late')
print('\nAll orders by the fee of the booking that moved them (x typical), share of orders, late share, and hours before the last pickup at that booking (median):')
ft = collections.defaultdict(list)
for r in rows:
    if r['fin_mult'] is not None: ft[bucket(r['fin_mult'], [0.75, 0.85, 0.95, 1.05, 1.15, 1.25, 1.45, 1.75, 2.05, 2.75])].append(r)
for k in sorted(ft, key=lambda s: (s[0] == '>', float(s.strip('<>=')))):
    v = ft[k]; print(f'  {k:8s} {len(v)/weeks:6.1f} a week  {sum(r["late"] for r in v)/len(v):5.1%} late  median {st.median((r["last"]-r["fin_at"])/H for r in v):6.1f} h before  two-car gigs {sum(r["fin_cars"]>1 for r in v)/len(v):4.0%}')
print('\nBooking chance an open hour (07-22), one-car gigs, by hours to the last pickup (rows) and fee shown x typical (columns): bookings per 100 gig-hours [gig-hours a week]')
rowsb = ['<0', '<3', '<6', '<12', '<24', '<48', '>=48']; cols = ['<0.85', '<0.95', '<1.05', '<1.15', '<1.25', '<1.45', '<1.75', '<2.05', '<2.35', '>=2.35']
print('  ' + ' ' * 6 + ''.join(f'{c:>14s}' for c in cols))
for rb in rowsb:
    print(f'  {rb:6s}' + ''.join((f'{100*slices[(rb,c)][1]/slices[(rb,c)][0]:6.1f} [{slices[(rb,c)][0]/weeks:5.1f}]' if slices[(rb, c)][0] > 20 else f'{"-":>14s}') for c in cols))
# how many cars are still without a driver at 12, 8, 6 h before the last pickup, and how they end
print('\nOne-car orders still without a driver X hours before the last pickup (won earlier than that), a week; share late; share later warned')
for x in (24, 12, 8, 6, 4):
    v = [r for r in one if r['won'] < r['last'] - x * H and (r['first'] is None or r['first'] > r['last'] - x * H)]
    if v: print(f'  {x:2d} h: {len(v)/weeks:5.1f} a week, {sum(r["late"] for r in v)/len(v):5.1%} late, {sum(r["warned"] is not None for r in v)/len(v):5.1%} warned, mean typical fee {st.mean(r["ref"] for r in v)/100:.0f}, mean price {st.mean(r["price"] for r in v)/100:.0f}, refund a late one {st.mean(r["refund"] for r in v if r["late"])/100 if any(r["late"] for r in v) else 0:.0f}')
print('\nBy drivers listed: orders, late, warned a week')
for lo, hi in ((0, 700), (700, 760), (760, 820), (820, 2000)):
    v = [r for r in rows if lo <= r['drivers'] < hi]; ws = len({r['seed'] for r in v})
    if ws: print(f'  {lo}-{hi}: {ws} weeks, {len(v)/ws:.0f} orders, {sum(r["late"] for r in v)/ws:.1f} late, {sum(r["warned"] is not None for r in v)/ws:.1f} warned')
json.dump(rows, open('item1-rows.json', 'w'))
