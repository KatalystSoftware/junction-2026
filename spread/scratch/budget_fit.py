"""Fits the late rates of the on-time budget (spreadlab/budget.py) on played weeks.

    python3 scratch/budget_fit.py <folder of played weeks, *.json.gz>

Every hour of the week, each won order that is open (a car not delivered, the deadline not passed) is one row: its hours
to the deadline, whether a driver holds every car still out, and whether it ended late. Prints the late share by band, and
the late share of the orders won on each day, for the orders the desk has not won yet.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

DAY = 1440
BANDS = [6, 12, 24, 48, 10**9]  # hours to the deadline, upper ends


def held_at(gigs: list[dict], t: int) -> bool:
    """A driver holds the leg at minute t: its last booking before t is later than its last drop before t."""
    for gig in gigs:
        booked = [b[0] for b in gig["booked"] if b[0] <= t]
        dropped = [d[0] for d in gig["dropped"] if d[0] <= t]
        if booked and (not dropped or max(booked) > max(dropped)):
            return True
    return False


def main() -> None:
    rows = {(band, held): [0, 0] for band in range(len(BANDS)) for held in (False, True)}
    won_day = {d: [0, 0] for d in range(5)}
    weeks = sorted(Path(sys.argv[1]).glob("*.json.gz"))
    for path in weeks:
        week = json.loads(gzip.open(path).read())
        late_ids = {e[3] for e in week["ledger"] if e[1] == "late_refund"}
        leg_gigs: dict[tuple[str, int], list[dict]] = {}
        for gig in week["gigs"]:
            for stop in gig["stops"]:
                if stop["kind"] == "pickup":
                    leg_gigs.setdefault((stop["orderId"], stop["leg"]), []).append(gig)
        for id_, order in week["orders"].items():
            if order["cancelled"] is not None:
                continue
            late = id_ in late_ids or any(leg["deliveredAt"] is None or leg["deliveredAt"] > order["deadline"] for leg in order["legs"])
            won_day[min(order["wonAt"] // DAY, 4)][0] += 1
            won_day[min(order["wonAt"] // DAY, 4)][1] += late
            for t in range((order["wonAt"] // 60 + 1) * 60, order["deadline"], 60):
                out = [i for i, leg in enumerate(order["legs"]) if leg["deliveredAt"] is None or leg["deliveredAt"] > t]
                if not out:
                    break
                band = next(i for i, top in enumerate(BANDS) if (order["deadline"] - t) / 60 < top)
                held = all(held_at(leg_gigs.get((id_, i), []), t) for i in out)
                rows[band, held][0] += 1
                rows[band, held][1] += late
    print(f"{len(weeks)} weeks")
    for (band, held), (n, late) in sorted(rows.items()):
        print(f"under {BANDS[band]:>10} h  {'held' if held else 'waiting'}  {n:>8} rows  late {late / max(n, 1):.4f}")
    for day, (n, late) in won_day.items():
        print(f"won on day {day}: {n} orders, late {late / max(n, 1):.4f}")


if __name__ == "__main__":
    main()
