"""What marks a week with a low on-time share, from what the desk knows on Monday morning (the driver list)?

One row per archived week (all opened at 1.2 x typical): roster size, the share of its orders whose pickup has few
drivers within 30 km, orders won, late share, first-hour booking share, fees paid over typical.
"""
import json, sys, collections
import numpy as np
d = json.load(open(sys.argv[1])); W = collections.defaultdict(list)
for o in d["orders"]:
    if o.get("posted") is not None and o.get("ref"): W[(o["variant"], o["seed"])].append(o)
rows = []
for (variant, seed), O in W.items():
    near = np.array([o["near"] for o in O], float); late = np.array([o["late"] for o in O], float)
    wait = np.array([1e9 if o["book"] is None else o["book"] - o["posted"] for o in O], float)
    rows.append((O[0]["drivers"], len(O), late.mean(), (wait <= 60).mean(), sum(o["fees"] or 0 for o in O) / sum(o["ref"] for o in O), (near < 5).mean(), (near < 20).mean(), np.median(near),
                 late[near < 20].mean() if (near < 20).any() else np.nan, late[near >= 100].mean() if (near >= 100).any() else np.nan))
A = np.array(rows, float); drivers, n, late, h1, paid, thin5, thin20, mednear, late_thin, late_deep = A.T
print(len(A), "weeks; roster size quantiles 5/25/50/75/95:", np.quantile(drivers, [.05, .25, .5, .75, .95]).round(), "| on-time share: mean", (1 - late).mean().round(4), "5%", np.quantile(1 - late, .05).round(4), "min", (1 - late).min().round(4))
c = lambda a, b: np.corrcoef(a, b)[0, 1]
print(f"correlation of a week's late share with: roster size {c(late, drivers):+.2f}, orders won {c(late, n):+.2f}, share of orders with under 20 drivers near the pickup {c(late, thin20):+.2f}, under 5 {c(late, thin5):+.2f}, first-hour share {c(late, h1):+.2f}")
print(f"correlation of roster size with: first-hour share {c(drivers, h1):+.2f}, paid over typical {c(drivers, paid):+.2f}, orders {c(drivers, n):+.2f}, thin share {c(drivers, thin20):+.2f}")
X = np.column_stack([np.ones(len(A)), (drivers - 800) / 100, (n - n.mean()) / 100, thin20 - thin20.mean()])
for name, y in [("late share", late), ("first-hour share", h1), ("paid over typical", paid)]:
    w, res, *_ = np.linalg.lstsq(X, y, rcond=None); r = y - X @ w; se = np.sqrt(np.diag(np.linalg.inv(X.T @ X)) * r.var(ddof=4))
    print(f"  {name:18s} = {w[0]:.4f} {w[1]:+.4f} (se {se[1]:.4f}) per 100 drivers {w[2]:+.4f} (se {se[2]:.4f}) per 100 orders {w[3]:+.4f} (se {se[3]:.4f}) per unit of thin share; R2 {1 - r.var() / y.var():.2f}")
print("by roster size:")
for lo, hi in [(0, 700), (700, 760), (760, 820), (820, 880), (880, 2000)]:
    s = (drivers >= lo) & (drivers < hi)
    if s.sum(): print(f"  {lo}-{hi}: weeks {s.sum():3d} orders {n[s].mean():.0f} late {late[s].mean():.3f} lowest on-time week {(1 - late[s]).min():.3f} weeks under 94% {(1 - late[s] < .94).mean():.2f} first hour {h1[s].mean():.3f} paid {paid[s].mean():.3f} | late in thin towns {np.nanmean(late_thin[s]):.3f} deep {np.nanmean(late_deep[s]):.3f}")
# the same seed across variants: is a hard week hard for every policy?
by = collections.defaultdict(dict)
for (variant, seed), r in zip(W.keys(), rows): by[seed][variant] = r[2]
pairs = [(v["curve-live"], v["curve-live-surcharge"]) for v in by.values() if "curve-live" in v and "curve-live-surcharge" in v]
if pairs: print(f"same seed, late share under two policies ({len(pairs)} seeds): correlation {c(*np.array(pairs).T):+.2f}")
