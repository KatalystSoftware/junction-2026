"""How much of the typical fee is the request's own noise? Fit ln fee on the lane (pickup x delivery) over all requests of the saved weeks."""
import gzip, json, sys, glob, collections
import numpy as np
lane = collections.defaultdict(list); allr = []
for path in sorted(glob.glob(f"{sys.argv[1]}/runs/explore/*-L8.json.gz")):
    run = json.load(gzip.open(path)); seed = path.split("/")[-1][:-11]
    for r in run["reveal"]["requests"]:
        q = r["request"]
        if len(q["legs"]) != 1: continue
        leg = q["legs"][0]; priv = leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"]
        car = leg["car"]
        allr.append((leg["pickup"]["placeId"], leg["delivery"]["placeId"], priv, np.log(q["referenceFeeCents"]), np.log(q["options"][0]["listPriceCents"]), q["options"][0]["kind"], car["premium"], car["electric"], seed, q["arrivedAt"] % 1440 / 60, q["arrivedAt"] // 1440))
for a in allr: lane[a[:3]].append(a[3])
mean = {k: np.mean(v) for k, v in lane.items()}
res = np.array([a[3] - mean[a[:3]] for a in allr]); cnt = np.array([len(lane[a[:3]]) for a in allr])
print(len(allr), "requests,", len(lane), "lanes (with private flag); requests on lanes with 20+ :", (cnt >= 20).mean())
big = cnt >= 20
print("sd of ln fee within a lane: %.4f; quantiles 5%% 25%% 75%% 95%%: %s" % (res[big].std(), np.round(np.quantile(res[big], [.05, .25, .75, .95]), 3)))
# is the noise explained by something the request shows?
for name, idx in (("premium", 6), ("electric", 7)):
    v = np.array([a[idx] for a in allr]); print(f"  {name}: share {v.mean():.3f}, mean residual with {res[big & v].mean():+.4f} without {res[big & ~v].mean():+.4f}")
kinds = np.array([a[5] for a in allr])
for k in sorted(set(kinds)): print(f"  first option {k}: {np.mean(kinds == k):.3f} residual {res[big & (kinds == k)].mean():+.4f}")
hour = np.array([a[9] for a in allr]); day = np.array([a[10] for a in allr])
print("  by hour band:", " ".join(f"{lo}-{hi}: {res[big & (hour >= lo) & (hour < hi)].mean():+.4f}" for lo, hi in ((8, 10), (10, 12), (12, 14), (14, 16), (16, 19))))
print("  by day:", " ".join(f"{k}: {res[big & (day == k)].mean():+.4f}" for k in range(5)))
seeds = sorted({a[8] for a in allr}); sm = [res[big & (np.array([a[8] for a in allr]) == s)].mean() for s in seeds[:50]]
print("  by week: sd of week means %.4f" % np.std(sm))
json.dump({"|".join(map(str, k)): [float(v), len(lane[k])] for k, v in mean.items()}, open(sys.argv[2], "w"))
