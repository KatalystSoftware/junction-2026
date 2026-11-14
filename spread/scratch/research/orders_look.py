"""Per order: booking speed, fee paid, drops and late share by the request's fee noise, option and wait to the first booking. Argument: view rows JSON (views.py)."""
import json, sys
import numpy as np
d = json.load(open(sys.argv[1])); O = [o for o in d["orders"] if o["lane_n"] >= 20 and o["posted"] is not None]
f = lambda k: np.array([np.nan if o[k] is None else float(o[k]) for o in O])
ref, lane, lst, price, posted, book, bfee, lfee, fees, late, refund, other, drops, lpa = (f(k) for k in "ref lane list price posted book book_fee last_fee fees late refund other drops lastPickupAt".split())
opt = np.array([o["option"] for o in O]); resid = np.log(ref) - lane; wait = book - posted; L = np.exp(lane)
print(len(O), "orders; corr of fee noise with ln list noise:", np.corrcoef(resid, np.log(lst) - np.log(ref))[0, 1].round(3), "| fees/typical", (fees.sum() / ref.sum()).round(3), "| fees above 1.2x typical per week EUR", round((fees.sum() - 1.2 * ref.sum()) / 100 / len({(o['variant'], o['seed']) for o in O})), "| refunds/wk", round(refund.sum() / 100 / len({(o['variant'], o['seed']) for o in O})), "other/wk", round(other.sum() / 100 / len({(o['variant'], o['seed']) for o in O})))
print("by request noise (typical fee over the lane's usual):  n  booked<=5m  <=60m  >4h/never  first fee/typ  paid/typ  paid/lane  drop  late  cost/typ  cost/lane")
edges = [-1, -.2, -.12, -.06, 0, .06, .12, .2, 1]
for lo, hi in zip(edges[:-1], edges[1:]):
    s = (resid >= lo) & (resid < hi); w = wait[s]
    print(f"  {lo:+.2f}..{hi:+.2f} (fee/lane {1.2 * np.exp(resid[s]).mean():.2f}) n={s.sum():5d} {np.mean(w <= 5):.3f} {np.mean(w <= 60):.3f} {np.mean(~(w <= 240)):.3f}   {np.nanmean(bfee[s] / ref[s]):.3f} {fees[s].sum() / ref[s].sum():.3f} {fees[s].sum() / L[s].sum():.3f} {np.mean(drops[s] > 0):.3f} {late[s].mean():.3f} {(fees[s] + refund[s] + other[s]).sum() / ref[s].sum():.3f} {(fees[s] + refund[s] + other[s]).sum() / L[s].sum():.3f}")
print("by option and noise half:")
for o in ("same_day", "next_day"):
    for nm, s in (("typical below lane", (opt == o) & (resid < -.06)), ("near", (opt == o) & (abs(resid) <= .06)), ("above", (opt == o) & (resid > .06))):
        w = wait[s]; print(f"  {o} {nm}: n={s.sum()} <=5m {np.mean(w <= 5):.3f} <=60m {np.mean(w <= 60):.3f} >4h {np.mean(~(w <= 240)):.3f} paid/typ {fees[s].sum() / ref[s].sum():.3f} late {late[s].mean():.3f}")
print("what a late order costs: refund per late order EUR %.0f, share of price %.3f; price mean EUR %.0f" % (refund[late == 1].mean() / 100, refund[late == 1].sum() / price[late == 1].sum(), price.mean() / 100))
print("wait to first booking -> late, paid/typ, drop:")
for lo, hi in [(0, 5), (5, 60), (60, 120), (120, 240), (240, 480), (480, 960), (960, 1e9)]:
    s = (wait >= lo) & (wait < hi); print(f"  {lo}-{hi:g}: n={s.sum()} ({s.mean():.3f}) late {late[s].mean():.3f} paid/typ {fees[s].sum() / ref[s].sum():.2f} first fee/typ {np.mean(bfee[s] / ref[s]):.2f}")
s = np.isnan(wait); print(f"  never: n={s.sum()} late {late[s].mean():.3f}")
print("first booking fee over typical, share of orders:", {k: round(float(np.mean((bfee / ref >= lo) & (bfee / ref < hi))), 3) for k, lo, hi in (("1.2", 0, 1.25), ("1.32", 1.25, 1.38), ("1.44", 1.38, 1.5), ("1.56", 1.5, 1.62), ("1.68", 1.62, 1.74), ("1.8", 1.74, 1.9), (">1.9", 1.9, 99))})
