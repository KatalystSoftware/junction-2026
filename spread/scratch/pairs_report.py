"""Scratch: how the out-and-back pairs (spreadlab/pairs.py) went against the variant they are built on, on the weeks both
played. For each pairs variant: pair gigs a week, the share booked within 1 and 2 hours of the post, the fee paid over the
two typical fees, the pair orders that ended late, the splits by reason; the held cars, and how often those that found no
return ended late against the same orders in the base variant; the return quotes and their won share; and the margin
against the base with its 95% interval, orders, late orders a week, weeks under 90% and the lowest week.

The plan's checks (README, "Out-and-back pairs"): pass with 75% of pair gigs booked within 2 hours, pair orders at most 5%
late, and held cars without a return no more than 1 point later. Stop under 50% booked within the hour at 0.8, or over 8% late.

    PYTHONPATH=. uv run python scratch/pairs_report.py --base slow-friday-late-150-kinds-limits \
        --variants slow-friday-late-150-kinds-limits-pairs-0.6,slow-friday-late-150-kinds-limits-pairs-0.7 --list tune --count 10
"""
from __future__ import annotations

import argparse
import collections
import statistics

from spreadlab.catalogue import load_seeds
from spreadlab.play import load_run, run_path
from spreadlab.report import interval


def week(variant: str, seed: str) -> dict:
    run = load_run(variant, seed)
    requests = {r["request"]["id"]: r["request"] for r in run["reveal"]["requests"]}
    won = {e["order"]["id"]: e["at"] for e in run["events"] if e["kind"] == "order_won"}
    late, fees, booked = set(), collections.Counter(), {}
    for e in run["events"]:
        if e["kind"] == "gig_booked":
            booked.setdefault(e["gigId"], e["at"])
        elif e["kind"] == "ledger":
            line = e["line"]
            if line["kind"] in ("late_refund", "undelivered_penalty") and line.get("orderId"):
                late.add(line["orderId"])
            elif line["kind"] == "driver_fee" and line.get("gigId"):
                fees[line["gigId"]] -= line["cents"]
    return {"run": run, "requests": requests, "won": won, "late": late, "fees": fees, "booked": booked}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="slow-friday-late-150-kinds-limits")
    parser.add_argument("--variants", required=True)
    parser.add_argument("--list", default="tune")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--seeds")
    args = parser.parse_args()
    seeds = args.seeds.split(",") if args.seeds else load_seeds(args.list, args.count)
    for variant in args.variants.split(","):
        common = [s for s in seeds if run_path(args.base, s).exists() and run_path(variant, s).exists()]
        if not common:
            print(f"{variant}: no week played by both")
            continue
        c = collections.Counter()
        diffs, rows = [], []
        for seed in common:
            base, mine = week(args.base, seed), week(variant, seed)
            run = mine["run"]
            diffs.append(run["score"]["marginCents"] - base["run"]["score"]["marginCents"])
            rows.append(run["score"])
            c["late"] += run["score"]["wonOrders"] * (1 - run["score"]["onTimeShare"])  # the world's count, as the 90% rule takes it
            c["base_late"] += base["run"]["score"]["wonOrders"] * (1 - base["run"]["score"]["onTimeShare"])
            c["base_orders"] += len(base["won"])
            gigs = {g["id"]: g for g in run["gigs"]}
            pair_gigs = {d["paired"]["gig"] for d in run["decisions"].values() if "gig" in d.get("paired", {})}
            for gig_id in pair_gigs:
                gig = gigs[gig_id]
                ids = list(dict.fromkeys(s["orderId"] for s in gig["stops"]))
                c["pairs"] += 1
                wait = mine["booked"].get(gig_id, 10**9) - gig["postedAt"]
                c["pair_1h"] += wait <= 60
                c["pair_2h"] += wait <= 120
                if gig_id in mine["booked"] and gig["status"] == "done":
                    c["pair_done"] += 1
                    c["pair_fee"] += mine["fees"][gig_id]
                    c["pair_typical"] += sum(mine["requests"][i]["referenceFeeCents"] for i in ids)
            for id_, decision in run["decisions"].items():
                paired, held = decision.get("paired", {}), decision.get("held")
                if "gig" in paired:
                    c["pair_orders"] += 1
                    c["pair_late"] += id_ in mine["late"]
                    if "split" in paired:
                        c["split_" + paired["split"]["why"]] += 1
                if paired.get("refused"):
                    c["refused"] += 1
                if held:
                    c["held"] += 1
                if held and "alone" in held:
                    c["alone"] += 1
                    c["alone_late"] += id_ in mine["late"]
                    if id_ in base["won"]:
                        c["alone_common"] += 1
                        c["alone_common_late"] += id_ in mine["late"]
                        c["alone_common_base_late"] += id_ in base["late"]
                if "pair" in decision and not decision.get("declined"):
                    c["return_quotes"] += 1
                    c["return_won"] += id_ in mine["won"]
                    c["return_new"] += id_ in mine["won"] and id_ not in base["won"]
        n = len(common)
        low, high = interval(diffs)
        on_time = [r["onTimeShare"] for r in rows]
        share = lambda a, b: f"{c[a] / c[b]:.1%}" if c[b] else "-"  # noqa: E731
        print(f"== {variant} against {args.base}, {n} weeks")
        print(f"  margin {statistics.mean(diffs) / 100:+,.0f} a week ({low / 100:,.0f} to {high / 100:,.0f}), better in {sum(d > 0 for d in diffs)}/{n}; "
              f"orders {statistics.mean(r['wonOrders'] for r in rows):.0f} against {c['base_orders'] / n:.0f}; "
              f"late a week {c['late'] / n:.1f} against {c['base_late'] / n:.1f}; weeks under 90% {sum(t < 0.9 for t in on_time)}; lowest week {min(on_time):.1%}")
        print(f"  pair gigs a week {c['pairs'] / n:.1f}: booked within 1 h {share('pair_1h', 'pairs')}, within 2 h {share('pair_2h', 'pairs')}; "
              f"fee paid over the two typical fees {c['pair_fee'] / c['pair_typical'] if c['pair_typical'] else 0:.2f}; "
              f"pair orders late {share('pair_late', 'pair_orders')} of {c['pair_orders']}; refused posts {c['refused']}")
        splits = {k[6:]: v for k, v in c.items() if k.startswith("split_")}
        print(f"  pair orders posted alone again, by reason: {splits or 'none'}")
        print(f"  held a week {c['held'] / n:.1f}, of which alone {c['alone'] / n:.1f}, late {share('alone_late', 'alone')}; "
              f"the {c['alone_common']} also won by the base: late {share('alone_common_late', 'alone_common')} against {share('alone_common_base_late', 'alone_common')}")
        print(f"  return quotes a week {c['return_quotes'] / n:.1f}, won {share('return_won', 'return_quotes')}, "
              f"won and not won by the base {c['return_new'] / n:.1f} a week")


if __name__ == "__main__":
    main()
