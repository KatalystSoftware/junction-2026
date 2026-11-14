"""Tables of the share of driver looks that book: by fee shown, fee over the lane's usual, distance from home, view number, minutes posted, clock hour, drivers notified, and after raises. Argument: view rows JSON (views.py)."""
import json, sys
import numpy as np
d = json.load(open(sys.argv[1])); C = d["cols"]; R = d["rows"]
col = lambda k: np.array([r[C.index(k)] for r in R], dtype=object)
num = lambda k: np.array([np.nan if r[C.index(k)] is None else float(r[C.index(k)]) for r in R])
variant = col("variant"); fee, ref, lane, lane_n, booked = num("fee"), num("ref"), num("lane"), num("lane_n"), num("booked")
at, post, nth, own, lpa = num("at"), num("first_post"), num("nth_view"), num("nth_own"), num("lastPickupAt")
home, near, option, drops, closed, had = num("home_km"), num("near"), col("option"), num("drops"), num("closed"), num("had_book")
mult = fee / ref; resid = np.log(ref) - lane; lanemult = fee / np.exp(lane); age = at - post; left = lpa - at; hour = at % 1440 / 60
print(len(R), "views; booked on the look", booked.mean().round(4), "; views per variant", {v: int((variant == v).sum()) for v in sorted(set(variant))})
def tab(name, key, edges, sel=None, fmt="{:.2f}"):
    sel = np.ones(len(R), bool) if sel is None else sel
    print(f"  {name}:")
    for lo, hi in zip(edges[:-1], edges[1:]):
        s = sel & (key >= lo) & (key < hi)
        if s.sum() >= 30: print(f"    {fmt.format(lo):>7}-{fmt.format(hi):<7} n={s.sum():6d} book {booked[s].mean():.3f}")
tab("fee shown / typical fee of the request", mult, [1.0, 1.25, 1.35, 1.47, 1.6, 1.75, 1.9, 2.2, 2.6, 4])
fresh = (drops == 0) & (had == 0) & (lane_n >= 20) & ~np.isnan(left)
first = fresh & (mult < 1.25)
print("views of a never-booked order at the opening fee 1.2:", first.sum(), "book", booked[first].mean().round(4))
tab("request noise: ln(typical fee) - lane mean, at the opening fee", resid, [-.5, -.2, -.12, -.06, 0, .06, .12, .2, .5], first)
tab("fee / lane-typical fee, at the opening fee", lanemult, [.8, 1.0, 1.08, 1.14, 1.2, 1.26, 1.32, 1.4, 1.5, 2], first)
loc = home <= 30
tab("same, drivers living within 30 km of the pickup", lanemult, [.8, 1.0, 1.08, 1.14, 1.2, 1.26, 1.32, 1.4, 1.5, 2], first & loc)
tab("same, drivers further away", lanemult, [.8, 1.0, 1.08, 1.14, 1.2, 1.26, 1.32, 1.4, 1.5, 2], first & ~loc)
tab("home km to pickup (opening fee)", home, [0, 1, 30, 60, 100, 150, 250, 1000], first, "{:.0f}")
tab("view number on the order (opening fee)", nth, [1, 2, 3, 4, 6, 10, 20, 1000], first, "{:.0f}")
tab("the driver's own look number (opening fee)", own, [1, 2, 3, 100], first, "{:.0f}")
tab("minutes since posted (opening fee)", age, [0, 2, 5, 15, 30, 60.01], first, "{:.0f}")
tab("hours to last pickup (opening fee)", left / 60, [-100, 2, 4, 8, 16, 24, 36, 48, 1000], first, "{:.0f}")
tab("hour of day (opening fee)", hour, [0, 7, 9, 11, 13, 15, 17, 19, 24], first, "{:.0f}")
tab("drivers notified at pickup (opening fee)", near, [0, 5, 10, 20, 40, 80, 160, 1000], first, "{:.0f}")
for o in ("same_day", "next_day", "within_3_days"): s = first & (option == o); print(f"    {o}: n={s.sum()} book {booked[s].mean():.3f}")
print("after raises (never-booked orders, no drop):")
for lo, hi in [(1.25, 1.35), (1.35, 1.47), (1.47, 1.6), (1.6, 1.75), (1.75, 1.9), (1.9, 4)]:
    s = fresh & (mult >= lo) & (mult < hi); print(f"    fee {lo}-{hi}: views {s.sum()} book {booked[s].mean():.3f}; own look 1: {booked[s & (own == 1)].mean():.3f} (n={int((s & (own == 1)).sum())}); returning: {booked[s & (own > 1)].mean():.3f} (n={int((s & (own > 1)).sum())})")
