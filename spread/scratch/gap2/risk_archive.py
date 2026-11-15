"""Every archived played week of our desks (the stand-in's packed weeks): weeks under 90% as orders rise."""
import gzip, json, glob, sys, os, collections, statistics as st
from multiprocessing import Pool
def read(f):
    try:
        w = json.load(gzip.open(f)); s = w['score']
        return (w['variant'], w['seed'], w['drivers'], s['orders'], s['on_time'], s['margin'] / 100)
    except Exception: return None
if __name__ == '__main__':
    files = glob.glob(sys.argv[1] + '/weeks/*/*.json.gz')
    with Pool(8) as p: R = [r for r in p.map(read, files, chunksize=50) if r and r[3] > 0]
    json.dump(R, open('archive-weeks.json', 'w'))
    print(len(R), 'weeks,', len({r[0] for r in R}), 'variants')
    by = collections.defaultdict(list)
    for r in R: by[r[0]].append(r)
    # desks by their mean orders per 100 drivers: weeks under 90 per 60
    print('\nDesks with 40 or more played weeks, by orders per 100 drivers: weeks, orders, margin, under 90% per 60, under 92% per 60')
    rows = []
    for v, ws in by.items():
        if len(ws) < 40: continue
        rows.append((st.mean(100 * w[3] / w[2] for w in ws), v, len(ws), st.mean(w[3] for w in ws), st.mean(w[5] for w in ws), 60 * sum(w[4] < 0.9 for w in ws) / len(ws), 60 * sum(w[4] < 0.92 for w in ws) / len(ws)))
    for r in sorted(rows)[-22:]: print(f'  {r[0]:5.1f} {r[1][:58]:58s} {r[2]:4d} {r[3]:5.0f} {r[4]:7.0f} {r[5]:5.1f} {r[6]:5.1f}')
    def tab(sel, label, edges=(0, 34, 38, 42, 46, 50, 54, 58, 64, 72, 200)):
        print(f'\n{label}: by orders per 100 drivers')
        for lo, hi in zip(edges, edges[1:]):
            v = [r for r in R if sel(r) and lo <= 100 * r[3] / r[2] < hi]
            if len(v) >= 20: print(f'  {lo:3d}-{hi:3d}: {len(v):5d} weeks, {st.mean(r[3] for r in v):4.0f} orders, {60*sum(r[4]<0.9 for r in v)/len(v):5.1f} under 90% per 60, {60*sum(r[4]<0.92 for r in v)/len(v):5.1f} under 92%, mean on time {st.mean(r[4] for r in v):.1%}, margin {st.mean(r[5] for r in v):6.0f}')
    modern = lambda r: any(k in r[0] for k in ('slow-', 'fee16', 'f80', 'opt-mu', 's1-', 'hours-due', 'due-24', 'target', 'exposure', 'search'))
    tab(lambda r: modern(r) and r[2] >= 760, 'Desks since the late-chance surcharge, 760 drivers or more')
    tab(lambda r: modern(r) and r[2] < 760, 'Desks since the late-chance surcharge, under 760 drivers')
    print(sorted({r[0] for r in R if modern(r)})[:60])
