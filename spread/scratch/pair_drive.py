"""Which pair gigs find no driver, and how late their cars end, by how the pair was formed, its shape, its planned drive, the
drivers who hear of it and the hour it was posted. Reads the stand-in's packed weeks (spreadlab/standin/pack.py on spread-standin).

    SPREAD_MAP=data/map.json python3 scratch/pair_drive.py "<standin>/weeks/<variant>/*" [least drivers, most drivers]
"""
import gzip, json, sys, glob, collections, os
DAY=1440
m=json.load(open(os.environ.get('SPREAD_MAP', 'data/map.json'))); MIN={(r['from'],r['to']):r['minutes'] for r in m['roads']}
import math
P={p['id']:p for p in m['places']}
def km(a,b):
    a,b=P[a],P[b]; la1,la2=math.radians(a['lat']),math.radians(b['lat']); dlo=math.radians(b['lon']-a['lon'])
    x=math.sin((la2-la1)/2)**2+math.cos(la1)*math.cos(la2)*math.sin(dlo/2)**2
    return 6371*2*math.asin(math.sqrt(x))
lo,hi=(int(sys.argv[2]),int(sys.argv[3])) if len(sys.argv)>3 else (760,10**9)
W=0; G=collections.defaultdict(lambda:[0,0,0,0])
for f in sorted(glob.glob(sys.argv[1])):
    d=json.load(gzip.open(f))
    if not lo<=d['drivers']<hi: continue
    wf=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(f))),'worlds',os.path.basename(f))
    w=json.load(gzip.open(wf)); req={r['id']:r for r in w['requests']}; W+=1
    homes=collections.Counter(r['homePlaceId'] for r in w['roster'])
    near=lambda place: sum(n for h,n in homes.items() if km(h,place)<=30)
    late=set(l[3] for l in d['ledger'] if l[1] in('late_refund','undelivered_penalty') and l[3])
    by=collections.defaultdict(list)
    for g in d['gigs']:
        for o in set(s['orderId'] for s in g['stops']): by[o].append(g)
    for g in d['gigs']:
        orders=[]
        for s in g['stops']:
            if s['kind']=='pickup' and s['orderId'] not in orders: orders.append(s['orderId'])
        if len(orders)!=2 or any(o not in d['orders'] or o not in req or len(req[o]['legs'])>1 for o in orders): continue
        if any(d['orders'][o]['cancelled'] is not None for o in orders): continue
        a,b=orders; la,lb=req[a]['legs'][0],req[b]['legs'][0]
        driven=bool(g['booked']) and g['started'] is not None
        nlate=sum(o in late for o in orders)
        earlier=[o for o in orders if any(q is not g and q['postedAt']<g['postedAt'] for q in by[o])]
        was_dropped=[o for o in orders if any(q is not g and q['postedAt']<g['postedAt'] and q['dropped'] for q in by[o])]
        back=MIN[(la['delivery']['placeId'],lb['pickup']['placeId'])]<=40 and MIN[(lb['delivery']['placeId'],la['pickup']['placeId'])]<=40
        drive=MIN[(la['pickup']['placeId'],la['delivery']['placeId'])]+MIN[(la['delivery']['placeId'],lb['pickup']['placeId'])]+MIN[(lb['pickup']['placeId'],lb['delivery']['placeId'])]
        L=min(d['orders'][o]['lastPickupAt'] for o in orders); hours=(L-g['postedAt'])/60; clock=(g['postedAt']%DAY)//60
        n=near(la['pickup']['placeId'])
        home_end=near(lb['delivery']['placeId'])
        keys=['formed: '+('with a car that had been posted alone before' if earlier else 'both cars held, never posted'),
              'shape: '+('out-and-back' if back else 'onward'),
              'shape x formed: '+('out-and-back' if back else 'onward')+(', one car posted before' if earlier else ', both held'),
              'drive: '+('under 4 h' if drive<240 else '4 to 6 h' if drive<360 else '6 to 8 h' if drive<480 else '8 h+'),
              'drivers hear of the first pickup: '+('under 10' if n<10 else '10 to 39' if n<40 else '40 to 99' if n<100 else '100+'),
              'drivers live near the last delivery: '+('under 10' if home_end<10 else '10 to 39' if home_end<40 else '40 to 99' if home_end<100 else '100+'),
              'posted: '+('09-12' if 9<=clock<12 else '12-15' if 12<=clock<15 else '15-18' if 15<=clock<18 else 'other'),
              'hours to the first last pickup at the post: '+('under 12' if hours<12 else '12 to 20' if hours<20 else '20 to 30' if hours<30 else '30+'),
              'all']
        if earlier: keys.append('formed with a posted car: '+('that car had been dropped' if was_dropped else 'never booked'))
        for k in keys:
            c=G[k]; c[0]+=1; c[1]+=not driven; c[2]+=nlate; c[3]+=2
print(sys.argv[1].split('/')[-2],'weeks',W,'drivers',lo,hi)
for k in sorted(G):
    n,u,l,cars=G[k]; print(f"   {k:72s} {n/W:5.1f} pair gigs a week, no driver {100*u/n:5.1f}% ({u/W:4.1f} a week), its cars late {100*l/cars:4.1f}% ({l/W:4.1f} a week)")
