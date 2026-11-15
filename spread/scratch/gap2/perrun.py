import json,sys,statistics as st
d=json.load(open(sys.argv[1]))
for key in ('previous','current'):
    rnd=d[key]
    T=[t for t in rnd['teams'] if t.get('played')==5 and all(r.get('marginCents') is not None for r in t['runs']) and 'starter' not in t['name'].lower()]
    for t in T: t['runs'].sort(key=lambda r:r['run'])
    print('==',rnd['name'],'complete teams',len(T), 'unranked', sum(1 for t in T if not t['ranked']))
    fails=0;tot=0
    for i in range(5):
        ok=[t for t in T if t['runs'][i]['onTimeShare']>=0.9 and t['runs'][i]['wonOrders']>0]
        tot+=len(T); fails+=len(T)-len(ok)
        ok.sort(key=lambda t:-t['runs'][i]['marginCents'])
        names=[t['team'] for t in ok]
        ur=names.index('katalyst')+1; u=ok[ur-1]['runs'][i]
        t10=ok[9]['runs'][i]; t1=ok[0]['runs'][i]
        hb=[t for t in T if t['name']=='House best'][0]['runs'][i]
        # frontier: among ok teams, orders quantiles and late share
        os_=sorted(t['runs'][i]['wonOrders'] for t in ok)
        hi=[t for t in ok if t['runs'][i]['wonOrders']>=1.2*u['wonOrders']]
        hi_ot=st.mean(t['runs'][i]['onTimeShare'] for t in hi) if hi else 0
        allhi=[t for t in T if t['runs'][i]['wonOrders']>=1.2*u['wonOrders']]
        hifail=sum(1 for t in allhi if t['runs'][i]['onTimeShare']<0.9)
        print(f"run{i+1}: us rank {ur}/{len(ok)} margin {u['marginCents']/100:.0f} ({u['marginCents']/t10['marginCents']:.2f} of 10th {t10['marginCents']/100:.0f}; 1st {t1['marginCents']/100:.0f}) orders {u['wonOrders']} | field orders p25/50/75/max {os_[len(os_)//4]}/{os_[len(os_)//2]}/{os_[3*len(os_)//4]}/{os_[-1]} | teams with >=1.2x our orders: {len(allhi)} of {len(T)}, {hifail} under 90%, mean on-time of rest {hi_ot*100:.1f} | fail {len(T)-len(ok)}")
    print('week failure rate across field', fails, tot, round(fails/tot,3))
    # single week top10 margin cut vs ours scaled
