import json,sys,statistics as st
R=json.load(open(sys.argv[1]))
us=[t for t in R if t['team']=='katalyst' or 'atalyst' in t['name']][0]
hb=[t for t in R if t['name']=='House best'][0]
def wk(t):
    rs=t['runs']; o=sum(r['wonOrders'] for r in rs); m=sum(r['marginCents'] for r in rs)/100
    late=sum(r['wonOrders']*(1-r['onTimeShare']) for r in rs)
    return o/5,m/5,m/o,late/5,min(r['onTimeShare'] for r in rs)
top=R[:10]
print(f"ranked {len(R)}; us rank {us['rank']}; 10th {R[9]['margin']/100:.0f}; 1st {R[0]['margin']/100:.0f}; median {R[len(R)//2]['margin']/100:.0f}")
print("team orders/wk margin/wk €/order late/wk lowest")
for t in top+[us,hb]:
    o,m,po,l,lo=wk(t); print(f"{t['rank']:>3} {t['name'][:22]:<22} {o:6.0f} {m:8.0f} {po:6.1f} {l:5.1f} {lo*100:5.1f}")
A=[wk(t) for t in top]; mean=[st.mean(x) for x in zip(*A)]
print('top10 mean', [round(x,1) for x in mean])
uo,um,upo,ul,_=wk(us)
to,tm,tpo,tl,_=mean[:5]
print(f"gap to top10 mean: {tm-um:.0f}/wk = volume {(to-uo)*upo:.0f} (+{to-uo:.0f} orders at our €{upo:.1f}) + per-order {(tpo-upo)*to:.0f} ({tpo-upo:+.1f} €/order on their {to:.0f})")
t10=R[9]; o,m,po,l,_=wk(t10)
print(f"gap to 10th: {m-um:.0f}/wk = volume {(o-uo)*upo:.0f} (+{o-uo:.0f} orders) + per-order {(po-upo)*o:.0f} ({po-upo:+.1f})")
# per run
print("per run: us orders/margin/€per | top10 mean orders/margin/€per | ratio orders, ratio margin | house best | field median orders")
for i in range(5):
    u=us['runs'][i]; tr=[t['runs'][i] for t in top]
    to=st.mean(r['wonOrders'] for r in tr); tm=st.mean(r['marginCents'] for r in tr)/100
    h=hb['runs'][i]; allo=st.median(t['runs'][i]['wonOrders'] for t in R)
    tl=st.mean(r['wonOrders']*(1-r['onTimeShare']) for r in tr)
    print(f"run{i+1}: {u['wonOrders']}/{u['marginCents']/100:.0f}/{u['marginCents']/100/u['wonOrders']:.1f} late {u['wonOrders']*(1-u['onTimeShare']):.0f} | {to:.0f}/{tm:.0f}/{tm/to:.1f} late {tl:.0f} | {to/u['wonOrders']:.2f} {tm/(u['marginCents']/100):.2f} | HB {h['wonOrders']}/{h['marginCents']/100:.0f} | med {allo:.0f}")
# across field: regression margin on orders
import math
xs=[wk(t)[0] for t in R]; ys=[wk(t)[1] for t in R]
mx,my=st.mean(xs),st.mean(ys); b=sum((x-mx)*(y-my) for x,y in zip(xs,ys))/sum((x-mx)**2 for x in xs)
r=b*math.sqrt(sum((x-mx)**2 for x in xs)/sum((y-my)**2 for y in ys))
print(f"field: margin/wk = {my:.0f} + {b:.1f} €/extra order; r={r:.2f}; n={len(R)}")
# teams with orders within +-15 of ours
print('teams near our volume (<=370/wk):')
for t in R:
    o,m,po,l,lo=wk(t)
    if o<=370: print(f"  {t['rank']:>3} {t['name'][:22]:<22} {o:5.0f} {m:7.0f} {po:5.1f} {l:4.1f}")
