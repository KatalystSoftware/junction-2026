"""What a won order costs over its typical fee (fees, failed visits, refunds), by option, hour, notified drivers, list price, note and more. Argument: curve rows JSON (scratch/curve_rows.py)."""
import json, sys, collections
import numpy as np
rows = json.load(open(sys.argv[1]))
won = [r for r in rows if r["outcome"] == "won"]
f = lambda k: np.array([r[k] for r in won], float)
paid, fees, costs, late, fee, lst = f("paid"), f("fees"), f("costs"), f("late"), f("fee"), f("list")
ont = np.array([r["onTime"] for r in won])
print("won", len(won), "on time", ont.mean(), "late>0 share", (late > 0).mean(), "costs>0", (costs > 0).mean())
print("totals per week: paid %.0f fees %.0f costs %.0f late %.0f margin %.0f" % tuple(x.sum() / 5000 for x in (paid, fees, costs, late, paid - fees - costs - late)))
print("fees/fee quantiles", np.quantile(fees / fee, [.05, .25, .5, .75, .95, .99]), "mean", (fees / fee).mean(), "ratio of sums", fees.sum() / fee.sum())
print("(fees+costs+late)/fee mean", ((fees + costs + late) / fee).mean(), "ratio of sums", (fees + costs + late).sum() / fee.sum())
print("late/paid when late: ", collections.Counter(np.round(late[late > 0] / paid[late > 0], 2)).most_common(8))
print("late but onTime", ((late > 0) & ont).sum(), "not onTime but late==0", ((late == 0) & ~ont).sum())
print("fee/list quantiles", np.quantile(fee / lst, [.05, .25, .5, .75, .95]))
def tab(name, key, bins=None):
    v = np.array([key(r) for r in won])
    if bins is not None: v = np.digitize(v.astype(float), bins)
    print(name)
    for u in sorted(set(v.tolist())):
        m = v == u
        print(f"  {u!s:28s} n={m.sum():5d} fees/fee {fees[m].sum()/fee[m].sum():.3f} all/fee {(fees+costs+late)[m].sum()/fee[m].sum():.3f} late {1-ont[m].mean():.3f} paid/list {paid[m].sum()/lst[m].sum():.3f} margin/order {((paid-fees-costs-late)[m]).mean()/100:7.2f}")
tab("option", lambda r: r["option"])
tab("kinds", lambda r: "+".join(r["kinds"]))
tab("unbooked", lambda r: r["unbooked"], [1, 3, 5, 7, 9])
tab("day", lambda r: r["day"])
tab("hour", lambda r: r["hour"], [9, 10, 11, 12, 13, 14, 15, 16, 17])
tab("situation", lambda r: r["situation"])
tab("notified", lambda r: r["notified"], [20, 50, 100, 200, 400])
tab("drivers", lambda r: r["drivers"], [700, 760, 820, 880])
tab("fee/list", lambda r: r["fee"] / r["list"], [0.6, 0.8, 1.0, 1.2])
tab("list eur", lambda r: r["list"] / 100, [40, 60, 90, 130, 200])
tab("trust", lambda r: r["trust"], [1, 3, 6, 10, 15, 20])
tab("note", lambda r: r["note"])
tab("batch", lambda r: r["batch"] is not None)
