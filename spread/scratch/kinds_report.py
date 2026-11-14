"""Scratch: how the two kinds of request that the desk had never quoted went, from weeks that quoted them at random
prices (`explore_private`, `explore_trade_in`). For each kind: the answers by the quote over the list price, and for
the won orders the fees paid over the typical fees, the share first booked within an hour, the late share, the failed
visits, and the margin an order after its own costs. The dealer requests of the same weeks are the comparison.

    PYTHONPATH=. uv run python scratch/kinds_report.py --variant learn-kinds --seeds kinds-001,kinds-002
"""
from __future__ import annotations

import argparse
import collections

from spreadlab.play import load_run, run_path

BANDS = [1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.8, 2.0, 2.4]


def band(value: float) -> str:
    return next((f"<{edge}" for edge in BANDS if value < edge), f">={BANDS[-1]}")


def kind_of(request: dict) -> str:
    if len(request["legs"]) > 1:
        return "trade-in"
    leg = request["legs"][0]
    return "private pickup" if leg["pickup"]["privateAddress"] else "private delivery" if leg["delivery"]["privateAddress"] else "dealer sites"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--seeds", required=True)
    args = parser.parse_args()
    answers = collections.defaultdict(lambda: [0, 0])  # (kind, band of the quote over list) -> [quotes, won]
    by_typical = collections.defaultdict(lambda: [0, 0])  # (kind, band of the quote over the typical fee) -> [quotes, won]
    orders = collections.defaultdict(collections.Counter)
    weeks = 0
    for seed in args.seeds.split(","):
        if not run_path(args.variant, seed).exists():
            continue
        run, weeks = load_run(args.variant, seed), weeks + 1
        requests = {r["request"]["id"]: r["request"] for r in run["reveal"]["requests"]}
        order_of = {g["id"]: g["stops"][0]["orderId"] for g in run["gigs"]}
        won, first, late, failed, money = {}, {}, set(), collections.Counter(), collections.defaultdict(collections.Counter)
        for e in run["events"]:
            if e["kind"] == "order_won":
                won[e["order"]["id"]] = e
            elif e["kind"] == "gig_booked":
                first.setdefault(order_of[e["gigId"]], e["at"])
            elif e["kind"] == "visit_failed":
                failed[e["orderId"]] += 1
            elif e["kind"] == "ledger" and e["line"].get("orderId"):
                line = e["line"]
                money[line["orderId"]][line["kind"]] += line["cents"]
                if line["kind"] in ("late_refund", "undelivered_penalty"):
                    late.add(line["orderId"])
        for id_, decision in run["decisions"].items():
            request = requests[id_]
            kind = kind_of(request)
            if not decision["declined"]:
                option = min(request["options"], key=lambda o: o["listPriceCents"] if o["kind"] in decision["prices"] else 10**12)
                quote = decision["prices"][option["kind"]]
                for table, key in ((answers, band(quote / option["listPriceCents"])), (by_typical, band(quote / request["referenceFeeCents"]))):
                    table[(kind, key)][0] += 1
                    table[(kind, key)][1] += id_ in won
            if id_ in won:
                c, lines = orders[kind], money[id_]
                c["n"] += 1
                c["typical"] += request["referenceFeeCents"]
                c["fees"] -= lines["driver_fee"]
                c["revenue"] += lines["revenue"]
                c["margin"] += sum(lines.values())
                c["hour"] += first.get(id_, 10**9) - won[id_]["at"] <= 60
                c["late"] += id_ in late
                c["failed"] += failed[id_]
                c["list"] += won[id_]["order"]["priceCents"] and next(o["listPriceCents"] for o in request["options"] if o["kind"] == won[id_]["order"]["option"])
    print(f"{args.variant}: {weeks} weeks")
    for table, name in ((answers, "list price"), (by_typical, "typical fee")):
        print(f"won share by the quote over the {name}:")
        for kind in ("dealer sites", "private pickup", "private delivery", "trade-in"):
            cells = [f"{key} {table[(kind, key)][1] / table[(kind, key)][0]:4.0%} of {table[(kind, key)][0]:<4d}" for key in [f"<{e}" for e in BANDS] + [f">={BANDS[-1]}"] if table[(kind, key)][0]]
            print(f"  {kind:17s} " + "  ".join(cells))
    print(f"{'won orders':17s} a week  price/typical  list/typical  fees/typical  booked<1h   late  failed visits  margin an order  margin a week")
    for kind in ("dealer sites", "private pickup", "private delivery", "trade-in"):
        c = orders[kind]
        if c["n"]:
            print(f"{kind:17s} {c['n'] / weeks:6.1f} {c['revenue'] / c['typical']:14.2f} {c['list'] / c['typical']:13.2f} {c['fees'] / c['typical']:13.3f} {c['hour'] / c['n']:10.1%} "
                  f"{c['late'] / c['n']:6.1%} {c['failed'] / c['n']:14.2f} {c['margin'] / c['n'] / 100:16.1f} {c['margin'] / weeks / 100:14.0f}")


if __name__ == "__main__":
    main()
