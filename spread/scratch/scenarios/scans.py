"""What every world shows before any decision: rosters, request times, batches, snow. From the scans (weeks played with no actions).

    python scratch/scenarios/scans.py <data folder>
"""
import collections, gzip, json, math, sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np

DAY, HOUR = 1440, 60


def scan(path):
    s = json.load(gzip.open(path))
    map_ = json.load(open(Path(path).parents[1] / "map.json"))
    places = {p["id"]: (p["lat"], p["lon"]) for p in map_["places"]}
    homes = collections.Counter(d["homePlaceId"] for d in s["roster"])
    R = [e["request"] for e in s["events"] if e["kind"] == "price_request"]
    F = [e for e in s["events"] if e["kind"] == "forecast"]
    batches = collections.defaultdict(list)
    for r in R:
        if r.get("batchId"): batches[r["batchId"]].append(r)
    big = max(batches.values(), key=len, default=[])
    near = {}
    for a, (la, lo) in places.items():
        near[a] = sum(c for b, c in homes.items() if 6371 * math.hypot(math.radians(places[b][1] - lo) * math.cos(math.radians((la + places[b][0]) / 2)), math.radians(places[b][0] - la)) <= 30)
    dealer = collections.Counter(r["dealerId"] for r in R)
    exp = sum(1 for d in s["roster"] if d["rating"] >= 4.8 and d["completedGigs"] >= 50)
    return dict(seed=s["seed"], drivers=len(s["roster"]), experienced=exp, requests=len(R), at=[r["arrivedAt"] for r in R], per_minute=max(collections.Counter(r["arrivedAt"] for r in R).values()),
                big=len(big), big_at=big[0]["arrivedAt"] if big else None, big_near=near.get(big[0]["legs"][0]["pickup"]["placeId"]) if big else None,
                big_dealer=big[0]["dealerId"] if big else None, big_span=(max(r["arrivedAt"] for r in big) - min(r["arrivedAt"] for r in big)) if big else None,
                forecasts=[(f["at"], f["from"], f["to"], len(f["placeIds"])) for f in F],
                homes=dict(homes), near_pick=[near[r["legs"][0]["pickup"]["placeId"]] for r in R if len(r["legs"]) == 1],
                top_dealer=dealer.most_common(1)[0][1] / len(R), dealers=len(dealer), notes=sum(1 for r in R if r["note"]) / len(R),
                private=sum(1 for r in R if any(l["pickup"]["privateAddress"] or l["delivery"]["privateAddress"] for l in r["legs"])) / len(R),
                premium=sum(1 for r in R if r["legs"][0]["car"]["premium"]) / len(R),
                days=[sum(1 for r in R if r["arrivedAt"] // DAY == d) for d in range(5)])


if __name__ == "__main__":
    data = Path(sys.argv[1])
    paths = [str(p) for p in sorted((data / "scans").glob("*-L8.json.gz"))]
    with ProcessPoolExecutor(4) as pool:
        S = list(pool.map(scan, paths, chunksize=4))
    json.dump(S, open(data / "scans.json", "w"))
    n = len(S); q = lambda a, ps=(0, .01, .05, .25, .5, .75, .95, .99, 1): np.quantile(a, ps).round(2)
    drivers = np.array([s["drivers"] for s in S])
    print(f"{n} scans; prefixes {collections.Counter(s['seed'].rsplit('-', 1)[0] for s in S)}")
    print("drivers quantiles 0/1/5/25/50/75/95/99/100:", q(drivers), "| under 680:", np.mean(drivers < 680).round(3), "under 720:", np.mean(drivers < 720).round(3), "under 650:", np.mean(drivers < 650).round(3))
    print("experienced drivers:", q([s["experienced"] for s in S]), "share:", q([s["experienced"] / s["drivers"] for s in S]))
    at = np.concatenate([np.array(s["at"]) % DAY for s in S])
    print(f"requests a week {q([s['requests'] for s in S])}; {len(at)} requests: earliest {at.min() // 60}:{at.min() % 60:02d} latest {at.max() // 60}:{at.max() % 60:02d}; before 06:00 or after 22:00: {int(((at < 360) | (at >= 1320)).sum())}; after 18:00: {np.mean(at >= 1080):.4f}")
    print("most requests in one minute:", q([s["per_minute"] for s in S]))
    print("requests by day (mean):", np.mean([s["days"] for s in S], axis=0).round(0))
    big = np.array([s["big"] for s in S])
    print(f"largest batch: {q(big)}; weeks with one of 25+: {np.mean(big >= 25):.3f}; its day {collections.Counter(s['big_at'] // DAY for s in S if s['big'] >= 25)}; hour {q([s['big_at'] % DAY / 60 for s in S if s['big'] >= 25])}; span minutes {q([s['big_span'] for s in S if s['big'] >= 25])}")
    bn = np.array([s["big_near"] for s in S if s["big"] >= 25])
    print(f"  drivers within 30 km of the bulk yard: {q(bn)}; under 5: {np.mean(bn < 5):.3f} under 20: {np.mean(bn < 20):.3f} under 50: {np.mean(bn < 50):.3f}")
    nf = np.array([len(s["forecasts"]) for s in S])
    print(f"snow forecasts a week: {collections.Counter(nf.tolist())}; lead hours {q([(f[1] - f[0]) / 60 for s in S for f in s['forecasts']])}; length hours {q([(f[2] - f[1]) / 60 for s in S for f in s['forecasts']])}; places {q([f[3] for s in S for f in s['forecasts']])}; start day {collections.Counter(f[1] // DAY for s in S for f in s['forecasts'])}")
    # uneven shortage: share of one-car requests whose pickup has few drivers within 30 km
    thin5 = np.array([np.mean(np.array(s["near_pick"]) < 5) for s in S]); thin20 = np.array([np.mean(np.array(s["near_pick"]) < 20) for s in S])
    print(f"share of requests with under 5 drivers near the pickup: {q(thin5)}; under 20: {q(thin20)}; corr with roster size {np.corrcoef(thin20, drivers)[0, 1]:+.2f}")
    towns = sorted({t for s in S for t in s["homes"]})
    share = np.array([[s["homes"].get(t, 0) / s["drivers"] for t in towns] for s in S])
    cv = share.std(axis=0) / share.mean(axis=0)
    print(f"towns {len(towns)}; a town's share of the roster varies between worlds by cv {q(cv, (0, .25, .5, .75, 1))}; largest town share {q(share.max(axis=1), (0, .5, 1))}")
    print(f"top dealer's share of requests {q([s['top_dealer'] for s in S], (0, .5, 1))}; dealers {q([s['dealers'] for s in S], (0, .5, 1))}; notes {q([s['notes'] for s in S], (0, .5, 1))}; private {q([s['private'] for s in S], (0, .5, 1))}; premium {q([s['premium'] for s in S], (0, .5, 1))}")
