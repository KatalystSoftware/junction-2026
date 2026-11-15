import json,sys,statistics as st
d=json.load(open(sys.argv[1]))
rnd=d[sys.argv[2]]
teams=[t for t in rnd['teams'] if t.get('played')]
print(rnd['name'], 'teams listed',len(rnd['teams']),'played',len(teams))
print({k:v for k,v in teams[0].items() if k!='runs'}); print(teams[0]['runs'][0])
full=[t for t in teams if len([r for r in t['runs'] if r.get('marginCents') is not None])==5]
ranked=[t for t in full if t.get('ranked')]
ranked.sort(key=lambda t:-t['marginCents'])
print('complete',len(full),'ranked',len(ranked))
def row(t,i):
    rs=sorted(t['runs'],key=lambda r:r['run'])
    return f"{i:>3} {t['name'][:24]:<24} {t['marginCents']/100:>9.0f} {t['onTimeShare']*100:5.2f} | "+" ".join(f"{r['marginCents']/100:>6.0f}/{r['wonOrders']:>3}/{r['onTimeShare']*100:4.1f}{'' if r.get('ranked',True) else '*'}" for r in rs)
for i,t in enumerate(ranked,1):
    if i<=25 or 'atalyst' in t['name'] or 'ouse' in t['name'].lower(): print(row(t,i))
for t in full:
    if 'ouse' in t['name'].lower() and t not in ranked: print(row(t,0))
json.dump([dict(name=t['name'],team=t['team'],rank=i,margin=t['marginCents'],runs=sorted(t['runs'],key=lambda r:r['run'])) for i,t in enumerate(ranked,1)],open(f'ranked-{sys.argv[2]}.json','w'))
