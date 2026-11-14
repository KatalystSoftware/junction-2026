"""Hour-by-hour: the chance that an unbooked single-car order finds its first driver in the next hour, and how late orders end by the time left at booking."""
import json, sys
import numpy as np
d = json.load(open(sys.argv[1])); O = [o for o in d["orders"] if o["posted"] is not None and o["lane_n"] >= 20 and o["lastPickupAt"] is not None]
rows = []  # age_h, clock hour, hours left, same_day, fee/typ, fee/lane, event, late
for o in O:
    end = o["book"] if o["book"] is not None else min(o["lastPickupAt"] + 600, 7 * 1440)
    k = 0
    while o["posted"] + 60 * k < end and k < 72:
        t = o["posted"] + 60 * k; mult = min(1.2 + 0.12 * k, 1.8); ev = o["book"] is not None and o["book"] < t + 60
        rows.append((k, t % 1440 / 60, (o["lastPickupAt"] - t) / 60, o["option"] == "same_day", mult, mult * o["ref"] / np.exp(o["lane"]), ev, o["late"], o["near"])); k += 1
A = np.array(rows, float); k, clock, left, same, mult, lm, ev, late, near = A.T
print(len(O), "orders,", len(A), "order-hours")
day = (clock >= 7) & (clock < 21)
print("chance of a first booking in the next hour, by hours on the board (daytime 07-21 starts):")
for lo, hi in [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 9), (9, 15), (15, 24), (24, 48), (48, 72)]:
    s = (k >= lo) & (k < hi) & day; print(f"  hour {lo:2d}-{hi:<2d} fee {mult[s].mean():.2f} n={s.sum():6d} book {ev[s].mean():.3f} | same_day {ev[s & (same == 1)].mean():.3f} next_day+ {ev[s & (same == 0)].mean():.3f}")
late_h = (k >= 5) & day
print("after 5 hours on the board (fee at the 1.8 cap), by clock hour:", " ".join(f"{h:02d}:{ev[late_h & (clock >= h) & (clock < h + 2)].mean():.3f}" for h in range(7, 21, 2)), "| night 21-07:", ev[(k >= 5) & ~day].mean().round(4))
print("after 5 hours, by hours left to the last pickup:", " ".join(f"{a}-{b}h:{ev[late_h & (left >= a) & (left < b)].mean():.3f}(n={int((late_h & (left >= a) & (left < b)).sum())})" for a, b in [(-50, 0), (0, 2), (2, 4), (4, 8), (8, 16), (16, 30), (30, 99)]))
print("after 5 hours, by fee over the lane's usual:", " ".join(f"{a}-{b}:{ev[late_h & (lm >= a) & (lm < b)].mean():.3f}" for a, b in [(1, 1.5), (1.5, 1.65), (1.65, 1.8), (1.8, 2), (2, 3)]))
print("hours 1-5 (fee 1.32 to 1.68), by fee over the lane's usual:", " ".join(f"{a}-{b}:{ev[(k >= 1) & (k < 5) & day & (lm >= a) & (lm < b)].mean():.3f}" for a, b in [(1, 1.25), (1.25, 1.4), (1.4, 1.55), (1.55, 1.7), (1.7, 3)]))
print("first hour, by fee over the lane's usual:", " ".join(f"{a}-{b}:{ev[(k == 0) & (lm >= a) & (lm < b)].mean():.3f}" for a, b in [(.7, 1), (1, 1.08), (1.08, 1.14), (1.14, 1.2), (1.2, 1.3), (1.3, 1.5), (1.5, 3)]))
print("first hour by clock hour:", " ".join(f"{h:02d}:{ev[(k == 0) & (clock >= h) & (clock < h + 1)].mean():.2f}" for h in range(8, 20)))
print("first hour by drivers notified:", " ".join(f"{a}-{b}:{ev[(k == 0) & (near >= a) & (near < b)].mean():.3f}" for a, b in [(0, 5), (5, 10), (10, 20), (20, 40), (40, 80), (80, 160), (160, 999)]))
# lateness by the hours left to the last pickup when the order found its last driver
g = lambda key: np.array([np.nan if o[key] is None else float(o[key]) for o in O])
lb, lpa, lt, ref, fees, refund, price, drops, book = (g(x) for x in "last_book lastPickupAt late ref fees refund price drops book".split())
slack = (lpa - lb) / 60; s0 = (lpa - book) / 60
print("late share by hours left to the last pickup at the final booking:")
for a, b in [(-999, 0), (0, 1), (1, 2), (2, 3), (3, 5), (5, 8), (8, 16), (16, 30), (30, 999)]:
    s = (slack >= a) & (slack < b); print(f"  {a}..{b} h: n={s.sum():5d} late {lt[s].mean():.3f} paid/typ {fees[s].sum() / ref[s].sum():.2f} refund/price {refund[s].sum() / price[s].sum():.3f}")
print("  never booked:", int(np.isnan(lb).sum()), "late", lt[np.isnan(lb)].mean().round(3))
print("orders still unbooked N hours before the last pickup -> share that end late: ", " ".join(f"{h}h:{lt[~(s0 >= h)].mean():.3f}(n={int((~(s0 >= h)).sum())})" for h in (24, 16, 12, 8, 6, 4, 3, 2)))
print("hours between win and last pickup, quantiles 5/25/50/75/95:", np.round(np.quantile((lpa - g('won')) / 60, [.05, .25, .5, .75, .95]), 1), "same_day:", np.round(np.quantile(((lpa - g('won')) / 60)[np.array([o['option'] == 'same_day' for o in O])], [.05, .25, .5, .75, .95]), 1))
np.save(sys.argv[2], A)  # one row per order-hour, read by windows.py
