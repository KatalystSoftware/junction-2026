"""Scratch: why orders were late, from saved weeks. Each late order gets the first cause that applies:
a failed visit, a drop, a note's tighter deadline, a change of plan, a first booking after `lastPickupAt` or in its
last 3 hours, a private address, a drive of over 400 minutes, or none of these.

    PYTHONPATH=. uv run python scratch/late_causes.py --variant fee-cap-1.2-drop-cost-1.3 --lists tune,holdout --seeds fresh-001,...
"""
from __future__ import annotations

import argparse
import collections
import json

from spreadlab.catalogue import load_seeds
from spreadlab.play import load_run, run_path
from spreadlab.server import data_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", required=True)
    parser.add_argument("--lists", default="tune,holdout")
    parser.add_argument("--seeds", default="")
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()
    seeds = [seed for name in args.lists.split(",") if name for seed in load_seeds(name, args.count)] + [s for s in args.seeds.split(",") if s]
    minutes = {(r["from"], r["to"]): r["minutes"] for r in json.loads((data_dir() / "map.json").read_text(encoding="utf-8"))["roads"]}
    causes, refunds, weeks, orders = collections.Counter(), collections.Counter(), 0, 0
    by_option = collections.defaultdict(lambda: [0, 0])
    for seed in seeds:
        if not run_path(args.variant, seed).exists():
            continue
        run, weeks = load_run(args.variant, seed), weeks + 1
        requests = {r["request"]["id"]: r["request"] for r in run["reveal"]["requests"]}
        truth = {o["orderId"]: o for o in run["reveal"]["orders"]}
        order_of = {g["id"]: g["stops"][0]["orderId"] for g in run["gigs"]}
        won, late, failed, dropped, changed, booked_at = {}, collections.Counter(), set(), set(), set(), collections.defaultdict(list)
        for e in run["events"]:
            if e["kind"] == "order_won":
                won[e["order"]["id"]] = e["order"]
            elif e["kind"] == "ledger" and e["line"]["kind"] in ("late_refund", "undelivered_penalty"):
                late[e["line"]["orderId"]] -= e["line"]["cents"]
            elif e["kind"] == "visit_failed":
                failed.add(e["orderId"])
            elif e["kind"] in ("gig_dropped", "no_show"):
                dropped.add(order_of[e["gigId"]])
            elif e["kind"] == "order_changed":
                changed.add(e["order"]["id"])
            elif e["kind"] == "gig_booked":
                booked_at[order_of[e["gigId"]]].append(e["at"])
        orders += len(won)
        for id_, order in won.items():
            by_option[order["option"]][0] += 1
            if id_ not in late:
                continue
            by_option[order["option"]][1] += 1
            request, leg = requests[id_], requests[id_]["legs"][0]
            first, last = min(booked_at[id_], default=10**9), order["lastPickupAt"]
            cause = ("failed visit" if id_ in failed else "dropped" if id_ in dropped else "changed" if id_ in changed
                     else "note deadline" if any(l["noteDeadline"] is not None for l in truth[id_]["legs"])
                     else "first booked after the last pickup" if first > last else "first booked in the last 3 hours" if first > last - 180
                     else "private address" if leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"]
                     else "drive over 400 minutes" if minutes[(leg["pickup"]["placeId"], leg["delivery"]["placeId"])] > 400
                     else "booked in time, late anyway")
            causes[cause] += 1
            refunds[cause] += late[id_]
    total = sum(causes.values())
    print(f"{args.variant}: {weeks} weeks, {orders / weeks:.0f} orders and {total / weeks:.1f} late a week ({total / orders:.1%})")
    for cause, n in causes.most_common():
        print(f"  {cause:36s} {n / weeks:5.2f} a week  {n / total:5.1%} of the late  refunds {refunds[cause] / weeks / 100:6.0f} a week")
    for option, (n, l) in sorted(by_option.items()):
        print(f"  {option:16s} {n / weeks:6.1f} orders a week, {l / max(1, n):5.1%} late")


if __name__ == "__main__":
    main()
