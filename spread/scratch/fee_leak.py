"""Scratch: where a variant pays drivers more than the typical fee, from saved weeks. Euros a week.

Each done gig counts once, at the fee of its last booking, against the typical fee of its cars. What it paid over the
typical fee splits into the opening (the first fee of its first schedule over the typical fee) and what it paid over
its opening, which goes to the first class that fits, in this order:

- rebooked: the gig was booked again after a driver dropped it
- reposted: the order's car was posted again (an expired gig, a failed visit, a deadline warning)
- overnight: booked on a later day than it was posted
- same day: booked later the same day, after a rise

`--base 1.2` measures as the clean-room analysis did on `curve-live-surcharge`: the excess over 1.2 x the typical fee,
and the opening cost of 1.2 against 1.0 on every won order.

    PYTHONPATH=. uv run python scratch/fee_leak.py --variants curve-live-surcharge,slow-friday-late-150-kinds-limits
"""
from __future__ import annotations

import argparse
import collections
from pathlib import Path

from spreadlab.play import load_run
from spreadlab.server import data_dir

CLASSES = ("rebooked", "reposted", "overnight", "same day")


def week(run: dict, base: float | None) -> dict:
    typical = {r["request"]["id"]: r["request"]["referenceFeeCents"] for r in run["reveal"]["requests"]}
    legs = {r["request"]["id"]: len(r["request"]["legs"]) for r in run["reveal"]["requests"]}
    won = [e["order"]["id"] for e in run["events"] if e["kind"] == "order_won"]
    bookings = collections.defaultdict(list)
    for e in run["events"]:
        if e["kind"] == "gig_booked":
            bookings[e["gigId"]].append((e["at"], e["feeCents"]))
    first_gig: dict[str, int] = {}
    for g in run["gigs"]:
        order = g["stops"][0]["orderId"]
        first_gig[order] = min(first_gig.get(order, 10**9), g["postedAt"])
    out = collections.Counter()
    for g in run["gigs"]:
        if g["status"] != "done" or not bookings.get(g["id"]):
            continue
        order = g["stops"][0]["orderId"]
        cars = len({s["leg"] for s in g["stops"] if s["kind"] == "pickup"})
        ref = typical[order] * cars / legs[order]
        at, paid = bookings[g["id"]][-1]
        opening = g["schedule"][0]["feeCents"]
        floor = ref * base if base else opening
        over = max(0.0, paid - floor)
        if len(bookings[g["id"]]) > 1:
            cls = "rebooked"
        elif g["postedAt"] > first_gig[order]:
            cls = "reposted"
        elif at // 1440 > g["postedAt"] // 1440:
            cls = "overnight"
        else:
            cls = "same day"
        out["gigs"] += 1
        out["paid"] += paid / 100
        out["typical"] += ref / 100
        if not base:
            out["opening"] += (opening - ref) / 100
        out[cls] += over / 100
        out[cls + " gigs"] += over > 0
    if base:  # the opening at `base` against 1.0 on every won order, as the clean-room analysis counted it
        out["opening"] = (base - 1.0) * sum(typical[o] for o in won) / 100
    out["orders"] = len(won)
    out["margin"] = run["score"]["marginCents"] / 100
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", required=True)
    parser.add_argument("--seeds", help="comma-separated seeds; default every saved week of the variant")
    parser.add_argument("--base", type=float, help="count the excess over this multiple of the typical fee, not over the opening")
    args = parser.parse_args()
    for variant in args.variants.split(","):
        seeds = args.seeds.split(",") if args.seeds else sorted(p.name.split("-L")[0] for p in (data_dir() / "runs" / variant).glob("*-L8.json.gz"))
        weeks = [week(load_run(variant, seed), args.base) for seed in seeds if (data_dir() / "runs" / variant / f"{seed}-L8.json.gz").exists()]
        n = len(weeks)
        mean = {k: sum(w[k] for w in weeks) / n for k in set().union(*weeks)}
        rises = sum(mean.get(c, 0) for c in CLASSES)
        print(f"{variant} ({n} weeks{', over ' + str(args.base) + ' x typical' if args.base else ''}): orders {mean['orders']:.0f}, done gigs {mean['gigs']:.0f}, "
              f"paid {mean['paid']:,.0f} against typical {mean['typical']:,.0f} ({mean['paid'] / mean['typical']:.3f} x)")
        print(f"  opening {mean['opening']:,.0f}   over the {'base' if args.base else 'opening'} {rises:,.0f}: "
              + ", ".join(f"{c} {mean.get(c, 0):,.0f} ({mean.get(c + ' gigs', 0):.1f} gigs)" for c in CLASSES))


if __name__ == "__main__":
    main()
