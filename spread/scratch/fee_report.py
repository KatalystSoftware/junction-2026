"""Scratch: how the driver fees of each variant went, from saved weeks. One row a variant, means over its weeks:
the fees paid over the typical fees of the won orders, the share of orders whose first booking came within an hour
of the win, the deadline warnings, the drops, and the late orders.

    PYTHONPATH=. uv run python scratch/fee_report.py --variants curve-fee-1.0-cost-1.2,fee-drop --list tune --count 10
"""
from __future__ import annotations

import argparse
import collections

from spreadlab.catalogue import load_seeds
from spreadlab.play import load_run, run_path


def week(run: dict) -> dict:
    typical = {r["request"]["id"]: r["request"]["referenceFeeCents"] for r in run["reveal"]["requests"]}
    order_of = {g["id"]: g["stops"][0]["orderId"] for g in run["gigs"]}
    won_at, first_booking, counts = {}, {}, collections.Counter()
    for e in run["events"]:
        if e["kind"] == "order_won":
            won_at[e["order"]["id"]] = e["at"]
        elif e["kind"] == "gig_booked":
            first_booking.setdefault(order_of[e["gigId"]], e["at"])
        elif e["kind"] in ("gig_dropped", "deadline_close"):
            counts[e["kind"]] += 1
        elif e["kind"] == "ledger" and e["line"]["kind"] == "driver_fee":
            counts["fees"] -= e["line"]["cents"]
    score = run["score"]
    return {"margin": score["marginCents"] / 100, "orders": score["wonOrders"], "on_time": score["onTimeShare"],
            "fee": counts["fees"] / max(1, sum(typical[id_] for id_ in won_at)),
            "hour": sum(1 for id_, at in won_at.items() if first_booking.get(id_, 10**9) - at <= 60) / max(1, len(won_at)),
            "warnings": counts["deadline_close"], "drops": counts["gig_dropped"], "late": (1 - score["onTimeShare"]) * score["wonOrders"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", required=True)
    parser.add_argument("--list", default="tune")
    parser.add_argument("--seeds", help="comma-separated seeds, in place of --list")
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()
    seeds = args.seeds.split(",") if args.seeds else load_seeds(args.list, args.count)
    print(f"{'variant':26s} weeks  margin  orders  fee/typical  booked<1h  warnings  drops  late  lowest on time")
    for variant in args.variants.split(","):
        weeks = [week(load_run(variant, seed)) for seed in seeds if run_path(variant, seed).exists()]
        if not weeks:
            print(f"{variant:26s} no saved weeks")
            continue
        mean = {key: sum(w[key] for w in weeks) / len(weeks) for key in weeks[0]}
        print(f"{variant:26s} {len(weeks):>5} {mean['margin']:>7,.0f} {mean['orders']:>7.0f} {mean['fee']:>12.3f} {mean['hour']:>10.1%} "
              f"{mean['warnings']:>9.1f} {mean['drops']:>6.1f} {mean['late']:>5.1f} {min(w['on_time'] for w in weeks):>15.1%}")


if __name__ == "__main__":
    main()
