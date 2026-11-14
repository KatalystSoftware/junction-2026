"""Scratch: how drivers answer the fee. Each view of a gig is one row: the fee shown over the typical fee, how long the
gig had been open, and whether that driver booked it then. Reads saved weeks of variants that differ in the opening fee.

    PYTHONPATH=. python scratch/driver_views.py --variants curve-fee-0.9,curve-fee-1.0,curve-live-surcharge --list tune --count 10
"""
from __future__ import annotations

import argparse
import collections
import statistics

from spreadlab.catalogue import load_seeds
from spreadlab.play import load_run, run_path

EDGES = [0.85, 0.95, 1.05, 1.15, 1.25, 1.35, 1.45, 1.6, 1.8, 2.1]


def band(value: float, edges: list[float]) -> str:
    return next((f"<{e}" for e in edges if value < e), f">={edges[-1]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", required=True)
    parser.add_argument("--list", default="tune")
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()
    views = collections.defaultdict(lambda: [0, 0])  # (fee band, hours open band) -> [views, bookings]
    by_fee = collections.defaultdict(lambda: [0, 0])
    by_hour = collections.defaultdict(lambda: [0, 0])  # hour of the day -> [views, bookings] at 0.95 to 1.25
    first_view = collections.defaultdict(lambda: [0, 0])  # fee band -> [first views of a driver on a gig, bookings]
    for variant in args.variants.split(","):
        per_week = collections.Counter()
        waits, weeks = [], 0
        for seed in load_seeds(args.list, args.count):
            if not run_path(variant, seed).exists():
                continue
            run, weeks = load_run(variant, seed), weeks + 1
            typical = {r["request"]["id"]: r["request"]["referenceFeeCents"] / len(r["request"]["legs"]) for r in run["reveal"]["requests"]}
            gig_typical = {g["id"]: sum(typical[s["orderId"]] for s in g["stops"] if s["kind"] == "pickup") for g in run["gigs"]}
            posted = {g["id"]: g["postedAt"] for g in run["gigs"]}
            order_of = {g["id"]: g["stops"][0]["orderId"] for g in run["gigs"]}
            booked = {(e["gigId"], e["driverId"], e["at"]) for e in run["events"] if e["kind"] == "gig_booked"}
            seen: set[tuple[str, str]] = set()
            won_at, first_booking = {}, {}
            for e in run["events"]:
                if e["kind"] == "order_won":
                    won_at[e["order"]["id"]] = e["at"]
                elif e["kind"] == "gig_booked":
                    first_booking.setdefault(order_of[e["gigId"]], e["at"])
                    per_week["bookings"] += 1
                    per_week["booked_fee"] += e["feeCents"]
                    per_week["booked_typical"] += gig_typical[e["gigId"]]
                elif e["kind"] in ("gig_dropped", "no_show", "deadline_close", "visit_failed", "release"):
                    per_week[e["kind"]] += 1
                elif e["kind"] == "ledger" and e["line"]["kind"] in ("driver_fee", "late_refund"):
                    per_week[e["line"]["kind"]] += e["line"]["cents"]
                    per_week["n_" + e["line"]["kind"]] += 1
            for e in run["reveal"]["views"]:
                if True:
                    took = (e["gigId"], e["driverId"], e["at"]) in booked
                    fee, open_ = band(e["feeCents"] / gig_typical[e["gigId"]], EDGES), band((e["at"] - posted[e["gigId"]]) / 60, [0.25, 1, 2, 4, 8, 16])
                    for table, key in ((views, (fee, open_)), (by_fee, fee)):
                        table[key][0] += 1
                        table[key][1] += took
                    if 0.95 <= e["feeCents"] / gig_typical[e["gigId"]] < 1.25:
                        by_hour[e["at"] % 1440 // 60][0] += 1
                        by_hour[e["at"] % 1440 // 60][1] += took
                    if (e["gigId"], e["driverId"]) not in seen:
                        seen.add((e["gigId"], e["driverId"]))
                        first_view[fee][0] += 1
                        first_view[fee][1] += took
                    per_week["views"] += 1
            waits += [(first_booking[o] - at) / 60 for o, at in won_at.items() if o in first_booking]
            per_week["orders"] += len(won_at)
            per_week["never_booked"] += sum(o not in first_booking for o in won_at)
        if weeks:
            waits.sort()
            print(f"{variant:24s} weeks {weeks}  orders {per_week['orders'] / weeks:.0f}  bookings {per_week['bookings'] / weeks:.0f}  drops {per_week['gig_dropped'] / weeks:.0f}  "
                  f"warnings {per_week['deadline_close'] / weeks:.0f}  failed visits {per_week['visit_failed'] / weeks:.0f}  late {per_week['n_late_refund'] / weeks:.1f}  "
                  f"paid/typical {-per_week['driver_fee'] / max(1, per_week['booked_typical']) :.3f}*  booked fee/typical {per_week['booked_fee'] / per_week['booked_typical']:.3f}  "
                  f"hours to first booking: median {statistics.median(waits):.1f}  p75 {waits[int(.75 * len(waits))]:.1f}  p90 {waits[int(.9 * len(waits))]:.1f}  views a week {per_week['views'] / weeks:.0f}")
    order = lambda key: EDGES.index(float(key.lstrip("<>="))) + key.startswith(">")
    print("\nshare of views that book, by the fee over the typical fee (all views; a driver's first view of the gig)")
    for fee in sorted(by_fee, key=order):
        n, k = by_fee[fee]
        fn, fk = first_view[fee]
        print(f"  {fee:>7s}  views {n:6d}  book {k / n:6.1%}   first views {fn:6d}  book {fk / max(1, fn):6.1%}")
    print("\nshare of views that book, by the fee and the hours the gig has been open")
    opens = ["<0.25", "<1", "<2", "<4", "<8", "<16", ">=16"]
    print("          " + "".join(f"{o:>14s}" for o in opens))
    for fee in sorted(by_fee, key=order):
        print(f"  {fee:>7s} " + "".join(f"{views[(fee, o)][1] / views[(fee, o)][0]:7.1%} {views[(fee, o)][0]:5d} " if views[(fee, o)][0] else " " * 14 for o in opens))
    print("\nviews and bookings by the hour of the day, fee 0.95 to 1.25 x typical")
    print("  " + "  ".join(f"{h:02d}h {n} {k / n:.0%}" for h, (n, k) in sorted(by_hour.items())))


if __name__ == "__main__":
    main()
