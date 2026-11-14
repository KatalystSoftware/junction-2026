"""An outage detector on the random-price weeks: is one region accepting about 30% higher prices today?

For every centre town, the region is the places within 80 km. Before each quote, the answers of today (08:00-18:00,
answered at least 15 minutes ago) from the region give a likelihood ratio between "prices shifted by +SHIFT here today"
and "no shift". The chance of a win is then the mixture. Prints log loss, how fast a region is flagged, and what flagged
quotes win at each price band against the rest.
"""
import sys, json, math
import numpy as np
sys.path.insert(0, __import__("os").path.dirname(__file__))
from lib import *
from filt import replay
d = load(sys.argv[1]); y = d["y"]; zs = np.load(sys.argv[2]); z, slope = zs[:, 0], zs[:, 1]
m = json.load(open(sys.argv[3])); pos = {p["id"]: (p["lat"], p["lon"]) for p in m["places"]}
def km(a, b):
    (la, lo), (lb, lob) = pos[a], pos[b]; x = math.radians(lob - lo) * math.cos(math.radians((la + lb) / 2)); return 6371 * math.hypot(x, math.radians(lb - la))
towns = d["towns"]; missing = [t for t in towns if t not in pos]
if missing: print("places not on the map:", missing[:5]); towns = [t for t in towns if t in pos]
region = {c: {t for t in towns if km(c, t) <= 80} for c in towns}
member = {t: [c for c in towns if t in region[c]] for t in towns}
print("places per region: median", np.median([len(v) for v in region.values()]), "max", max(len(v) for v in region.values()))
sh = replay(d, z, slope, {"day": 0.16, "from": 0.06, "to": 0.06}); base = z - slope * (d["x"] - sh); p0 = sigmoid(base)
sh2 = replay(d, z, slope, {"day": 0.16, "from": 0.06, "to": 0.06, "from_day": 0.05}); pfd = sigmoid(z - slope * (d["x"] - sh2))
print(f"log loss: day + from + to {logloss(p0, y):.4f} | + from-today 0.05 {logloss(pfd, y):.4f}")
mult = np.exp(d["x"])


def run(key, SHIFT, prior, show=False):
    q = np.zeros(d["n"]); first = []; flagged_days = []
    for s in range(len(d["seeds"])):
        ix = np.nonzero(d["seed"] == s)[0]; ix = ix[np.argsort(d["at"][ix], kind="stable")]
        llr = {}; pend = 0; today = -1; seen = {}
        for k, i in enumerate(ix):
            if d["day"][i] != today:
                for c, v in llr.items():
                    if v > math.log(0.9 / 0.1) - math.log(prior / (1 - prior)): flagged_days.append((s, today, c))
                today = d["day"][i]; llr = {}; pend = k; seen = {}
            while pend < k and d["at"][ix[pend]] + 15 <= d["at"][i]:
                j = ix[pend]; pend += 1
                if not 8 <= d["hour"][j] < 18 or d[key][j] not in member: continue
                a = sigmoid(base[j]); b = sigmoid(base[j] + slope[j] * SHIFT)
                step = math.log(b / a) if y[j] else math.log((1 - b) / (1 - a))
                for c in member[d[key][j]]: llr[c] = llr.get(c, 0.0) + step
            if 8 <= d["hour"][i] < 18 and d[key][i] in member:
                best = max((llr.get(c, 0.0) for c in member[d[key][i]]), default=0.0)
                q[i] = 1 / (1 + math.exp(-(math.log(prior / (1 - prior)) + best)))
                if q[i] > 0.8 and (s, today) not in seen: seen[(s, today)] = 1; first.append((s, today, d["hour"][i]))
    p = (1 - q) * p0 + q * sigmoid(base + slope * SHIFT)
    print(f"  outage by {key}, shift {SHIFT}, prior {prior}: log loss {logloss(p, y):.4f}; quotes with q>0.8: {(q > 0.8).sum() / len(d['seeds']):.1f} a week; week-days flagged at a quote: {len(first) / len(d['seeds']):.2f} a week; weeks with a flag {len({f[0] for f in first})} of {len(d['seeds'])}")
    if show:
        hrs = np.array([f[2] for f in first]); print("    hour of the first flagged quote, quantiles 25/50/75:", np.round(np.quantile(hrs, [.25, .5, .75]), 1))
        f = q > 0.8; rest = (q < 0.05) & (d["hour"] >= 8) & (d["hour"] < 18)
        print("    price band (x list): flagged n, won, predicted without outage | others won")
        for lo, hi in [(1.2, 1.4), (1.4, 1.6), (1.6, 1.8), (1.8, 2.0), (2.0, 2.2), (2.2, 2.5)]:
            a = f & (mult >= lo) & (mult < hi); b = rest & (mult >= lo) & (mult < hi)
            print(f"      {lo}-{hi}: n={a.sum():4d} won {y[a].mean():.3f} predicted {p0[a].mean():.3f} | {y[b].mean():.3f}")
        # the shift that fits the flagged quotes best, given the rest of the curve
        best = min(np.arange(0, 0.5, 0.01), key=lambda t: logloss(sigmoid(base[f] + slope[f] * t), y[f]))
        print(f"    shift of the log price that fits the flagged quotes best: {best:.2f} (x{math.exp(best):.2f}); trust of flagged quotes mean {d['ntrust'][f].mean():.1f}, others {d['ntrust'][rest].mean():.1f}")
        np.save(sys.argv[4], q)
    return q


for key in ("pickup", "delivery"):
    for SHIFT in (0.2, 0.26):
        for prior in (0.01, 0.03):
            run(key, SHIFT, prior)
run("pickup", 0.26, 0.01, show=True)
run("delivery", 0.26, 0.01, show=True)
