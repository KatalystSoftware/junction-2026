"""Scratch: what the notes' own limits cost each variant a week, from saved weeks: visits that found the pickup site
closed, waits at a delivery site, orders that were late only by the note's deadline, gigs that expired, and the
account lines of each.

    PYTHONPATH=. uv run python scratch/notes_effect.py --variants steep-notes-offers-8,notes-limits --seeds cat-001,...

Only the seeds that every variant has played are counted.
"""
from __future__ import annotations

import argparse
import collections

from spreadlab.play import load_run, run_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", required=True)
    parser.add_argument("--seeds", required=True)
    args = parser.parse_args()
    variants = args.variants.split(",")
    seeds = [s for s in args.seeds.split(",") if all(run_path(v, s).exists() for v in variants)]
    print(f"{len(seeds)} weeks played by every variant; a week:")
    print(f"{'variant':24} {'orders':>6} {'late':>5} {'closed visits':>13} {'euros':>6} {'other failed':>12} {'waits':>6} {'euros':>6} {'late by the note only':>21} {'expired gigs':>12} {'refused':>7}")
    for variant in variants:
        n = collections.Counter()
        for seed in seeds:
            run = load_run(variant, seed)
            truth = {o["orderId"]: o for o in run["reveal"]["orders"]}
            won = {e["order"]["id"]: e["order"] for e in run["events"] if e["kind"] == "order_won"}
            for e in run["events"]:
                if e["kind"] == "order_changed" and e["order"]["id"] in won:
                    won[e["order"]["id"]] = e["order"]
            n["orders"] += run["score"]["wonOrders"]
            n["late"] += round((1 - run["score"]["onTimeShare"]) * run["score"]["wonOrders"])
            n["refused"] += len(run["refused"])
            failed_at = collections.defaultdict(list)
            for e in run["events"]:
                if e["kind"] == "visit_failed":
                    n["closed" if e["reason"] == "closed" else "failed"] += 1
                    failed_at[e["orderId"]].append((e["at"], e["reason"]))
                elif e["kind"] == "gig_expired":
                    n["expired"] += 1
                elif e["kind"] == "ledger":
                    line = e["line"]
                    if line["kind"] == "waiting":
                        n["waits"] += 1
                        n["wait cents"] -= line["cents"]
                    elif line["kind"] == "failed_visit" and any(reason == "closed" and abs(at - e["at"]) <= 1 for at, reason in failed_at.get(line.get("orderId"), [])):
                        n["closed cents"] -= line["cents"]
            for id_, order in won.items():
                legs = truth.get(id_, {}).get("legs", [])
                if len(legs) == 1 and legs[0]["noteDeadline"] is not None and legs[0]["deliveredAt"] is not None and legs[0]["noteDeadline"] < legs[0]["deliveredAt"] <= order["deadline"]:
                    n["note late"] += 1
        w = len(seeds)
        print(f"{variant:24} {n['orders'] / w:6.0f} {n['late'] / w:5.1f} {n['closed'] / w:13.2f} {n['closed cents'] / w / 100:6.1f} {n['failed'] / w:12.2f} {n['waits'] / w:6.2f} {n['wait cents'] / w / 100:6.1f} "
              f"{n['note late'] / w:21.2f} {n['expired'] / w:12.2f} {n['refused'] / w:7.2f}")


main()
