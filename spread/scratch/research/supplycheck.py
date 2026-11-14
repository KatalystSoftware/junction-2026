"""Checks of the supply analyst's claims on my rows: weekday decline, town supply against fee, long drives."""
import json, sys
import numpy as np
d = json.load(open(sys.argv[1])); cols = d["cols"]; rows = d["rows"]; ix = {c: i for i, c in enumerate(cols)}
g = lambda c, t=float: np.array([r[ix[c]] for r in rows], dtype=t)
at, fee, ref, lane, lane_n, booked, nth, near, learned, bel, had, first_fee = (g(c) for c in ["at", "fee", "ref", "lane", "lane_n", "booked", "nth_view", "near", "learned", "bel_ratio", "had_book", "first_fee"])
opening = (fee == first_fee) & (had == 0) & (fee / ref < 1.25)
day = (at // 1440).astype(int)
print("opening-fee looks, share that book, by weekday (all | first look on the order | drivers with no learned bookings | with 3+):")
for k in range(5):
    s = opening & (day == k)
    print(f"  day {k}: {booked[s].mean():.3f} (n={s.sum()}) | {booked[s & (nth == 1)].mean():.3f} | {booked[s & (learned == 0)].mean():.3f} (n={(s & (learned == 0)).sum()}) | {booked[s & (learned >= 3)].mean():.3f} (n={(s & (learned >= 3)).sum()})")
print("  first look, by weekday and the driver's learned ratio: " + " ".join(f"day{k}: none {booked[opening & (day == k) & (nth == 1) & (learned == 0)].mean():.2f} <=1.02 {booked[opening & (day == k) & (nth == 1) & (learned > 0) & (bel <= 1.02)].mean():.2f} >1.1 {booked[opening & (day == k) & (nth == 1) & (bel > 1.1)].mean():.2f};" for k in range(5)))
O = [o for o in d["orders"] if o.get("posted") is not None and o.get("ref")]
a = lambda c: np.array([np.nan if o.get(c) is None else o[c] for o in O], float)
posted, book, ref, lane, lane_n, near, near_to, minutes, late, fees, lpa, first_fee = (a(c) for c in ["posted", "book", "ref", "lane", "lane_n", "near", "near_to", "minutes", "late", "fees", "lastPickupAt", "first_fee"])
opt = np.array([o["option"] for o in O]); wait = book - posted; h1 = np.nan_to_num(wait, nan=1e9) <= 60; m5 = np.nan_to_num(wait, nan=1e9) <= 5
rel = 1.2 * np.exp(np.log(ref) - lane); ok = lane_n >= 20
wd = (posted // 1440).astype(int); hour = posted % 1440 / 60
print(f"\n{len(O)} orders. first hour / 5 min / late / paid over typical, by drivers living within 30 km of the pickup, split by opening fee over the lane's usual:")
for lo, hi in [(0, 1), (1, 5), (5, 20), (20, 100), (100, 1e9)]:
    s = (near >= lo) & (near < hi)
    line = f"  near {lo:.0f}-{hi:.0f}: n={s.sum():5d} 1h {h1[s].mean():.3f} 5m {m5[s].mean():.3f} late {late[s].mean():.3f} paid {np.nansum(fees[s]) / ref[s].sum():.3f} ||"
    for a_, b_ in [(0, 1.08), (1.08, 1.2), (1.2, 9)]:
        t = s & ok & (rel >= a_) & (rel < b_)
        line += f" fee/lane {a_}-{b_}: 1h {h1[t].mean():.3f} late {late[t].mean():.3f} paid/lane {np.nansum(fees[t]) / np.exp(lane[t]).sum():.3f} (n={t.sum()}) |"
    print(line)
print("same, deep supply (100+), by option and hour posted:")
for name, s in [("same_day before 12", (opt == "same_day") & (hour < 12)), ("same_day 12-15", (opt == "same_day") & (hour >= 12) & (hour < 15)), ("same_day 15+", (opt == "same_day") & (hour >= 15)), ("other before 12", (opt != "same_day") & (hour < 12)), ("other 12-15", (opt != "same_day") & (hour >= 12) & (hour < 15)), ("other 15+", (opt != "same_day") & (hour >= 15))]:
    for deep in (True, False):
        line = f"  {name:20s} {'deep' if deep else 'thin'}:"
        for a_, b_ in [(0, 1.08), (1.08, 1.2), (1.2, 9)]:
            t = s & ok & ((near >= 100) == deep) & (rel >= a_) & (rel < b_)
            line += f" fee/lane {a_}-{b_}: 1h {h1[t].mean():.3f} late {late[t].mean():.3f} paid/lane {np.nansum(fees[t]) / np.exp(lane[t]).sum():.3f} (n={t.sum()}) |"
        print(line)
print("by drive minutes: " + "  ".join(f"{lo}-{hi}: n={((minutes >= lo) & (minutes < hi)).sum()} 1h {h1[(minutes >= lo) & (minutes < hi)].mean():.2f} late {late[(minutes >= lo) & (minutes < hi)].mean():.3f} paid {np.nansum(fees[(minutes >= lo) & (minutes < hi)]) / ref[(minutes >= lo) & (minutes < hi)].sum():.2f}" for lo, hi in [(0, 60), (60, 180), (180, 400), (400, 9999)]))
print("by weekday posted: " + "  ".join(f"day{k}: 1h {h1[wd == k].mean():.3f} late {late[wd == k].mean():.3f} same_day late {late[(wd == k) & (opt == 'same_day')].mean():.3f} paid {np.nansum(fees[wd == k]) / ref[wd == k].sum():.3f}" for k in range(5)))
slack = (lpa - book) / 60; over = np.nan_to_num(fees - 1.2 * ref, nan=0); weeks = len({(o["variant"], o["seed"]) for o in O})
print(f"fees above 1.2 x typical, EUR a week ({weeks} weeks), by hours left to the last pickup at the first booking: " + "  ".join(f"{lo}-{hi}h: {over[(slack >= lo) & (slack < hi)].sum() / 100 / weeks:.0f}" for lo, hi in [(-999, 0), (0, 6), (6, 12), (12, 24), (24, 999)]))
