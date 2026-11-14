"""Where a variant's week goes, in euros a week, for the gap to the practice rankings.

    PYTHONPATH=. python scratch/gap.py --variant curve-live-surcharge --seeds cat-001,cat-002

Reads saved weeks only. Per week: requests, quotes, wins, the money by ledger line, and prices and
fees against the list price and the typical fee. It also splits the requests by what was done with them.
"""
from __future__ import annotations

import argparse
import collections
import statistics

from spreadlab.play import load_run, run_path

DAY = 1440


def week(variant: str, seed: str) -> dict:
    run = load_run(variant, seed)
    lines: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    won, booked, won_at = {}, {}, {}
    order_of = {gig["id"]: gig["stops"][0]["orderId"] for gig in run["gigs"]}
    for e in run["events"]:
        if e["kind"] == "ledger":
            lines[e["line"]["orderId"] or ""][e["line"]["kind"]] += e["line"]["cents"]
        elif e["kind"] == "order_won":
            won[e["order"]["id"]] = e["order"]
            won_at[e["order"]["id"]] = e["at"]
        elif e["kind"] == "gig_booked":
            booked.setdefault(order_of.get(e["gigId"]), e["at"])
    out = collections.Counter()
    out["margin"] = run["score"]["marginCents"]
    out["orders"] = run["score"]["wonOrders"]
    out["on_time_orders"] = round(run["score"]["onTimeShare"] * run["score"]["wonOrders"])
    for revealed in run["reveal"]["requests"]:
        request, decision = revealed["request"], run["decisions"].get(revealed["request"]["id"], {})
        out["requests"] += 1
        fee = request["referenceFeeCents"]
        next_day = [o for o in request["options"] if o["kind"] != "same_day"] or request["options"]
        list_price = min(o["listPriceCents"] for o in next_day)
        out["all_list"] += list_price
        out["all_fee"] += fee
        reason = decision.get("declined")
        if reason:
            out[f"declined_{reason}"] += 1
            out[f"declined_{reason}_spread"] += list_price * 1.2 - fee * 1.4  # what it would bring at 1.2 x list and the usual cost
            continue
        out["quoted"] += 1
        out["quoted_list"] += list_price
        if request["id"] not in won:
            out["lost"] += 1
            out["lost_list"] += list_price
            out["lost_fee"] += fee
            out["lost_quote"] += min(revealed["quote"].values()) if revealed["quote"] else 0
            continue
        order, account = won[request["id"]], lines[request["id"]]
        option = next(o for o in request["options"] if o["kind"] == order["option"])
        out["won"] += 1
        out["won_same_day"] += order["option"] == "same_day"
        out["won_price"] += order["priceCents"]
        out["won_list"] += option["listPriceCents"]
        out["won_typical_fee"] += fee
        for kind, cents in account.items():
            out[f"line_{kind}"] += cents
        if request["id"] in booked:
            out["booked"] += 1
            out["hours_to_booking"] += (booked[request["id"]] - won_at[request["id"]]) / 60
    for kind, cents in lines[""].items():
        out[f"line_no_order_{kind}"] += cents
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default="curve-live-surcharge")
    parser.add_argument("--seeds", required=True)
    args = parser.parse_args()
    seeds = [s for s in args.seeds.split(",") if run_path(args.variant, s).exists()]
    weeks = [week(args.variant, seed) for seed in seeds]
    keys = sorted({k for w in weeks for k in w})
    mean = {k: statistics.mean(w[k] for w in weeks) for k in keys}
    print(f"{args.variant}: {len(weeks)} weeks")
    for k in keys:
        money = k.startswith(("line_", "margin", "won_price", "won_list", "won_typical", "all_", "lost_", "quoted_list")) or k.endswith("_spread")
        print(f"  {k:32s} {mean[k] / 100:12,.0f} EUR" if money else f"  {k:32s} {mean[k]:12,.1f}")
    won = mean["won"]
    print(f"  price / list of wins        {mean['won_price'] / mean['won_list']:.3f}")
    print(f"  driver fee / typical fee    {-mean['line_driver_fee'] / mean['won_typical_fee']:.3f}")
    print(f"  typical fee / list, wins    {mean['won_typical_fee'] / mean['won_list']:.3f}   all requests {mean['all_fee'] / mean['all_list']:.3f}")
    print(f"  per order: price {mean['won_price'] / won / 100:.1f}  fee {-mean['line_driver_fee'] / won / 100:.1f}  margin {mean['margin'] / won / 100:.1f}")
    print(f"  share of requests quoted {mean['quoted'] / mean['requests']:.3f}  won of quoted {won / mean['quoted']:.3f}  won of all {won / mean['requests']:.3f}")
    print(f"  lost quotes at {mean['lost_quote'] / mean['lost_list']:.3f} x list")
    print("  margin per week: min %.0f  median %.0f  max %.0f" % tuple(f(w["margin"] for w in weeks) / 100 for f in (min, statistics.median, max)))
    print("  orders per week: min %d  median %d  max %d   requests min %d max %d" % (min(w["orders"] for w in weeks), statistics.median(w["orders"] for w in weeks), max(w["orders"] for w in weeks), min(w["requests"] for w in weeks), max(w["requests"] for w in weeks)))


if __name__ == "__main__":
    main()
