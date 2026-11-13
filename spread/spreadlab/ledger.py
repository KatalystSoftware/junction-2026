"""The mistake ledger: where each variant loses money, by situation.

    python -m spreadlab.ledger --variants baseline,price-1.6 --list tune --count 10

Reads the saved runs of the variants on the weeks that all of them played, and writes
data/ledger/ledger.json: one row per variant, situation and mistake, with the euros per week, the
count per week, the weeks it occurs in and the worst examples. Euros show what a mistake costs; the
share of weeks shows whether it is a habit of the variant or one bad week.

Two kinds of mistake:
- From the variant's own account, exact: late and undelivered orders (by what went with them), orders
  won below their driver fees, failed visits and waiting, and a week that is not ranked.
- Against the other variants on the same request, estimates: priced too low, lost or declined a car
  that another variant delivered on time at a profit, and paid the driver more. Variants win
  different cars, so drivers and dealers behave differently later in the week: a price that one
  variant won at is a hint for another, not proof. The paired weekly score (report.py) is the judge.

A situation is what the live system can see of a request: the bulk order, snow, a pickup that few
drivers are notified of, a trade-in, a private address, one of the two largest dealers, or none of
these. The price war, the outage and the flu are not labelled yet.
"""
from __future__ import annotations

import argparse
import collections
import json

from .catalogue import THIN, load_seeds
from .play import load_run, load_score
from .server import DAY, data_dir, drivers_near, near_places, world_map

SITUATIONS = ("bulk_order", "snow", "few_drivers", "trade_in", "private_address", "large_dealer", "normal")
BULK = 20  # requests in one batch
LATE_BOOKING = 120  # minutes from the win to the first booking
COSTS = ("failed_visit", "waiting", "fine")


def situation(request: dict, bulk_batches: set[str], forecasts: list[dict], notified: dict[str, int], large: set[str]) -> str:
    """The first situation of SITUATIONS that holds for the request."""
    legs = request["legs"]
    places = {leg[side]["placeId"] for leg in legs for side in ("pickup", "delivery")}
    last = max(option["deadline"] for option in request["options"])
    if request["batchId"] in bulk_batches:
        return "bulk_order"
    if any(places & set(f["placeIds"]) and request["arrivedAt"] < f["to"] and last > f["from"] for f in forecasts):
        return "snow"
    if min(notified[leg["pickup"]["placeId"]] for leg in legs) <= THIN:
        return "few_drivers"
    if len(legs) > 1:
        return "trade_in"
    if any(leg[side]["privateAddress"] for leg in legs for side in ("pickup", "delivery")):
        return "private_address"
    return "large_dealer" if request["dealerId"] in large else "normal"


def late_with(order_id: str, truth: list[dict], facts: dict) -> str:
    """What went with a late order: the first that holds. A correlate, not a proven cause."""
    if order_id in facts["failed"]:
        return "failed_visit"
    if order_id in facts["changed"]:
        return "order_changed"
    if order_id in facts["dropped"]:
        return "driver_dropped"
    if facts["first_booking"].get(order_id, 10**9) - facts["won_at"][order_id] > LATE_BOOKING:
        return "booked_late"
    if any(leg["noteDeadline"] is not None or leg["releasedAt"] is not None or leg["needsPlates"] or leg["manualGearbox"] for leg in truth):
        return "note_fact"
    return "other"


def week(run: dict, near: dict[str, set[str]]) -> dict:
    """One played week as one row per request, with the account of each won order, and the lines of the
    account that belong to no order."""
    events, reveal = run["events"], run["reveal"]
    requests = [r["request"] for r in reveal["requests"]]
    forecasts = [e for e in events if e["kind"] == "forecast"]
    notified = drivers_near(run["roster"], near)
    batches = collections.Counter(r["batchId"] for r in requests if r["batchId"])
    bulk_batches = {batch for batch, n in batches.items() if n >= BULK}
    large = {dealer for dealer, _ in collections.Counter(r["dealerId"] for r in requests).most_common(2)}
    order_of = {gig["id"]: gig["stops"][0]["orderId"] for gig in run["gigs"]}
    truth = {order["orderId"]: order["legs"] for order in reveal["orders"]}

    lines: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)  # order id -> line kind -> cents
    facts = {"failed": set(), "changed": set(), "dropped": set(), "first_booking": {}, "won_at": {}}
    won, cancelled = {}, set()
    for event in events:
        kind = event["kind"]
        if kind == "ledger":
            lines[event["line"]["orderId"] or ""][event["line"]["kind"]] += event["line"]["cents"]
        elif kind == "order_won":
            won[event["order"]["id"]] = event["order"]
            facts["won_at"][event["order"]["id"]] = event["at"]
        elif kind == "order_cancelled":
            cancelled.add(event["orderId"])
        elif kind == "visit_failed":
            facts["failed"].add(event["orderId"])
        elif kind == "order_changed":
            facts["changed"].add(event["order"]["id"])
        elif kind in ("gig_dropped", "no_show"):
            facts["dropped"].add(order_of.get(event["gigId"]))
        elif kind == "gig_booked":
            facts["first_booking"].setdefault(order_of.get(event["gigId"]), event["at"])

    rows = {}
    for revealed in reveal["requests"]:
        request = revealed["request"]
        decision = run["decisions"].get(request["id"], {})
        row = {"id": request["id"], "day": request["arrivedAt"] // DAY, "dealer": request["dealerId"],
               "situation": situation(request, bulk_batches, forecasts, notified, large),
               "outcome": "declined" if decision.get("declined") else revealed["outcome"], "declined": decision.get("declined")}
        if request["id"] in won:
            order, account = won[request["id"]], lines[request["id"]]
            late = account["late_refund"] + account["undelivered_penalty"]
            row.update({
                "outcome": "cancelled" if request["id"] in cancelled else "won", "option": order["option"], "price": order["priceCents"],
                "margin": sum(account.values()), "fees": -account["driver_fee"], "costs": -sum(account[kind] for kind in COSTS),
                "release": -account["release_fee"], "late": -late,
                "onTime": not account["late_refund"] and not account["undelivered_penalty"],
                "lateWith": late_with(request["id"], truth.get(request["id"], []), facts) if late else None,
            })
        rows[request["id"]] = row
    score = run["score"]
    return {"variant": run["variant"], "seed": run["seed"], "score": score, "requests": rows, "noOrder": sum(lines[""].values())}


def check(played: dict) -> list[str]:
    """The rows must give the week's score again: the margin to the cent, the orders, and the share on time."""
    score, rows = played["score"], played["requests"].values()
    orders = [row for row in rows if row["outcome"] == "won"]
    margin = sum(row.get("margin", 0) for row in rows) + played["noOrder"]
    problems = []
    if margin != score["marginCents"]:
        problems.append(f"margin {margin} is not the score's {score['marginCents']}")
    if len(orders) != score["wonOrders"]:
        problems.append(f"{len(orders)} orders, the score has {score['wonOrders']}")
    elif orders and abs(sum(row["onTime"] for row in orders) / len(orders) - score["onTimeShare"]) > 1e-9:
        problems.append(f"on time {sum(row['onTime'] for row in orders)} of {len(orders)}, the score has {score['onTimeShare']:.4f}")
    return [f"{played['variant']} {played['seed']}: {problem}" for problem in problems]


def mistakes(played: dict, others: list[dict]) -> list[dict]:
    """The mistakes of one week: {situation, mistake, cents, request}. `others` are the other variants' weeks on the seed."""
    found = []

    def add(row: dict | None, mistake: str, cents: int) -> None:
        if cents > 0:
            found.append({"situation": row["situation"] if row else "week", "mistake": mistake, "cents": cents, "request": row["id"] if row else None})

    score = played["score"]
    if not score["ranked"]:
        add(None, "week_not_ranked", score["marginCents"])  # the margin that does not count
    for request_id, row in played["requests"].items():
        theirs = [other["requests"][request_id] for other in others]
        good = [o for o in theirs if o["outcome"] == "won" and o["onTime"] and o["margin"] > 0]
        if row["outcome"] in ("lost", "declined", "unquoted"):
            add(row, "declined_good_car" if row["outcome"] == "declined" else "lost_good_car", max((o["margin"] for o in good), default=0))
            continue
        add(row, "cancelled_by_dealer", row["release"] + row["costs"] if row["outcome"] == "cancelled" else 0)
        if row["outcome"] != "won":
            continue
        add(row, f"late:{row['lateWith']}", row["late"])
        add(row, "failed_visit_or_waiting", row["costs"])
        if row["onTime"]:
            add(row, "won_below_fees", row["fees"] - row["price"])
            add(row, "priced_too_low", max((o["price"] - row["price"] for o in theirs if o["outcome"] == "won" and o["option"] == row["option"]), default=0))
            add(row, "overpaid_driver", max((row["fees"] - o["fees"] for o in theirs if o["outcome"] == "won" and o["onTime"]), default=0))
    return found


def build(variants: list[str], seeds: list[str], level: int = 8) -> tuple[list[dict], list[str], list[str]]:
    """The ledger rows, the weeks used, and the problems that `check` found."""
    near = near_places(world_map())
    common = [seed for seed in seeds if all(load_score(variant, seed, level) for variant in variants)]
    totals: dict[tuple, dict] = {}
    problems: list[str] = []
    for seed in common:
        played = {variant: week(load_run(variant, seed, level), near) for variant in variants}
        for variant in variants:
            problems += check(played[variant])
            for found in mistakes(played[variant], [played[other] for other in variants if other != variant]):
                total = totals.setdefault((variant, found["situation"], found["mistake"]), {"cents": 0, "count": 0, "examples": [], "seeds": set()})
                total["cents"] += found["cents"]
                total["count"] += 1
                total["seeds"].add(seed)
                total["examples"].append((found["cents"], seed, found["request"]))
    rows = [{"variant": variant, "situation": situation_, "mistake": mistake, "eurosPerWeek": round(total["cents"] / 100 / len(common), 1),
             "countPerWeek": round(total["count"] / len(common), 1), "weeks": sorted(total["seeds"]),
             "worst": [{"seed": seed, "request": request, "euros": cents / 100} for cents, seed, request in sorted(total["examples"], reverse=True)[:3]]}
            for (variant, situation_, mistake), total in totals.items()]
    rows.sort(key=lambda row: (row["variant"], -row["eurosPerWeek"]))
    return rows, common, problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variants", required=True)
    parser.add_argument("--list", default="tune")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--seeds")
    parser.add_argument("--level", type=int, default=8)
    parser.add_argument("--top", type=int, default=12, help="rows to print for each variant")
    args = parser.parse_args()
    variants = args.variants.split(",")
    seeds = args.seeds.split(",") if args.seeds else load_seeds(args.list, args.count)
    rows, common, problems = build(variants, seeds, args.level)
    if not common:
        print("No week that every variant has played.")
        return
    path = data_dir() / "ledger" / "ledger.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"variants": variants, "seeds": common, "rows": rows}, indent=1) + "\n", encoding="utf-8")
    print(f"{len(common)} weeks played by every variant. Euros per week. Wrote {path}")
    for problem in problems:
        print("CHECK FAILED:", problem)
    for variant in variants:
        mine = [row for row in rows if row["variant"] == variant]
        print(f"\n{variant}")
        for key in ("mistake", "situation"):
            print(f"  {'by ' + key + ' (weeks)':28s}" + "  ".join(f"{name} {total:,.0f} ({weeks}/{len(common)})" for name, total, weeks in by(mine, key)))
        print(f"  {'situation':16s} {'mistake':26s} {'euros/week':>10s} {'count/week':>10s} {'in weeks':>8s}  worst example")
        for row in mine[:args.top]:
            worst = row["worst"][0]
            print(f"  {row['situation']:16s} {row['mistake']:26s} {row['eurosPerWeek']:>10,.0f} {row['countPerWeek']:>10.1f} {len(row['weeks']):>5d}/{len(common):<2d}  "
                  f"{worst['seed']} {worst['request'] or ''} {worst['euros']:,.0f}")


def by(rows: list[dict], key: str) -> list[tuple[str, float, int]]:
    """For each value of `key`: the euros per week, and the number of weeks it occurs in."""
    totals: collections.Counter = collections.Counter()
    weeks: dict[str, set[str]] = collections.defaultdict(set)
    for row in rows:
        totals[row[key]] += row["eurosPerWeek"]
        weeks[row[key]] |= set(row["weeks"])
    return [(name, total, len(weeks[name])) for name, total in totals.most_common()]


if __name__ == "__main__":
    main()
