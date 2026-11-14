"""Logistic fit of the chance that a driver books on a look at the opening fee: fee over the lane's usual (kink at 1.22), option, view number, minutes posted, clock, belief. Argument: view rows JSON (views.py)."""
import json, sys
import numpy as np
sys.path.insert(0, __import__("os").path.dirname(__file__))
from lib import fit_logit, sigmoid
d = json.load(open(sys.argv[1])); C = d["cols"]; R = d["rows"]
num = lambda k: np.array([np.nan if r[C.index(k)] is None else float(r[C.index(k)]) for r in R])
col = lambda k: np.array([r[C.index(k)] for r in R], dtype=object)
fee, ref, lane, lane_n, booked, at, post, nth, own, lpa, home, near, drops, had, learned, belr, belm, firstfee = (num(k) for k in "fee ref lane lane_n booked at first_post nth_view nth_own lastPickupAt home_km near drops had_book learned bel_ratio bel_min first_fee".split())
option = col("option"); variant = col("variant")
mult = fee / ref; resid = np.log(ref) - lane; lm = fee / np.exp(lane); age = at - post; hour = at % 1440 / 60; left = (lpa - at) / 60
ok = (lane_n >= 20) & ~np.isnan(left)
print("1. after a drop: views", int((ok & (drops > 0)).sum()), "fee/typical quantiles 10/50/90:", np.round(np.quantile(mult[ok & (drops > 0)], [.1, .5, .9]), 2), "book per view", booked[ok & (drops > 0)].mean().round(3))
O = [o for o in d["orders"] if o["posted"] is not None]; g = lambda k: np.array([np.nan if o[k] is None else float(o[k]) for o in O])
oref, ofees, odrops, obfee, olfee, olate, obook, olbook, oposted = (g(k) for k in "ref fees drops book_fee last_fee late book last_book posted".split())
weeks = len({(o["variant"], o["seed"]) for o in O}); s = odrops > 0
print(f"   orders with a drop {s.mean():.3f}: first booked at {np.nanmean(obfee[s] / oref[s]):.2f}x typical, last booked at {np.nanmean(olfee[s] / oref[s]):.2f}x, paid {ofees[s].sum() / oref[s].sum():.2f}x, late {olate[s].mean():.3f}; hours from first to last booking median {np.nanmedian((olbook - obook)[s]) / 60:.1f}")
print(f"   EUR a week above 1.2x typical: all {(ofees.sum() - 1.2 * oref.sum()) / 100 / weeks:.0f}; orders with a drop {(ofees[s].sum() - 1.2 * oref[s].sum()) / 100 / weeks:.0f}; no drop, first booked above the opening fee {(ofees[~s & (obfee > 1.25 * oref)].sum() - 1.2 * oref[~s & (obfee > 1.25 * oref)].sum()) / 100 / weeks:.0f}; typical fee a week {oref.sum() / 100 / weeks:.0f}")
print("2. does the fee matter after the first hour? never-booked orders, booking per view by fee over the lane's usual, inside each step")
fresh = ok & (drops == 0) & (had == 0)
for lo, hi in [(1.0, 1.25), (1.25, 1.5), (1.5, 1.74), (1.74, 1.9)]:
    s = fresh & (mult >= lo) & (mult < hi); q = np.quantile(resid[s], [0, .25, .5, .75, 1])
    print(f"   step {lo}-{hi}: " + "  ".join(f"fee/lane {lm[s & (resid >= a) & (resid <= b)].mean():.2f}: {booked[s & (resid >= a) & (resid <= b)].mean():.4f}" for a, b in zip(q[:-1], q[1:])))
print("3. the driver's belief (mean of booked fee over first viewed fee, last 10 orders they saw) at the opening fee, first look")
s0 = fresh & (mult < 1.25)
for lo, hi in [(0, 1), (1, 3), (3, 10), (10, 1e9)]: s = s0 & (learned >= lo) & (learned < hi); print(f"   orders learned {lo}-{hi:g}: n={s.sum()} book {booked[s].mean():.3f}")
for lo, hi in [(0.99, 1.0001), (1.0001, 1.03), (1.03, 1.06), (1.06, 1.1), (1.1, 1.2), (1.2, 3)]: s = s0 & (learned >= 3) & (belr >= lo) & (belr < hi); print(f"   belief ratio {lo:.2f}-{hi:.2f}: n={s.sum()} book {booked[s].mean():.3f}  wait belief median {np.median(belm[s]):.0f} min")
# logistic on opening-fee first looks
knee = np.minimum(np.log(lm), np.log(1.22))
feats = {"ln fee/lane to 1.22": knee, "ln fee/lane above": np.log(lm) - knee, "same_day": (option == "same_day") * 1.0, "local": (home <= 30) * 1.0, "far 150km+": (home > 150) * 1.0, "ln view number": np.log(nth), "ln minutes since post": np.log1p(np.maximum(age, 0)), "hour after 15": np.maximum(hour - 15, 0), "morning before 11": (hour < 11) * 1.0, "belief ratio - 1": np.where(learned >= 1, belr - 1, 0), "no belief yet": (learned < 1) * 1.0, "ln near": np.log1p(near), "last pickup within 8h": (left < 8) * 1.0, "last pickup over 36h": (left > 36) * 1.0}
X = np.column_stack(list(feats.values()))[s0]; y = booked[s0]
w, b = fit_logit(X, y, C=1e4); p = sigmoid(X @ w + b)
print("4. logistic, opening-fee looks: n=%d, log loss %.4f against %.4f for the mean" % (len(y), -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)), -np.mean(y * np.log(y.mean()) + (1 - y) * np.log(1 - y.mean()))))
for n, c in zip(feats, w): print(f"   {n:28s} {c:+.3f}")
print("   intercept %.3f" % b)
