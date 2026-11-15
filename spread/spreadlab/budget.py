"""The on-time budget: the late cost follows how far the week's projected on-time share is above the 90% rule.

At each quote the desk projects the share it ends the week with: the orders already late, a late chance for each open
order by its hours to the deadline and whether a driver holds every car still out, and the orders it has yet to win at
the late share of orders won on that day. All rates are measured on 266 played weeks (scratch/budget_fit.py). The
projection's spread is that of independent orders, times `sd_by` for the drop waves that make late orders come together.

    z = (projected share - floor) / spread        late_cost x  hi at z <= z_lo,  lo at z >= z_hi,  linear between

A strong early week banks on-time orders: they cannot go late, so the projection stays high. Late in the week few orders are
still to come, so the spread is small and the same margin gives a higher z: a late Friday order cannot pull the week under
90% when the week has banked enough. The waiting-car charge (`slow_step`) is left as it is.

With `budget` {"floor", "z_lo", "z_hi", "lo", "hi", "sd_by", "drivers"}: on from `drivers` listed drivers (0 for all weeks),
put first among the bases so that it applies to `thin_play`'s parameters too. Off when the variant does not set it.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from .thin_play import ThinWidePairPolicy

VERSION = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
DAY, OPENS, OPEN, DAYS = 1440, 8 * 60, 10 * 60, 5  # requests arrive from 08:00 for about ten hours, Monday to Friday
# The late share of an open order by its hours to the deadline (upper ends), held by a driver or waiting for one.
BANDS = [6, 12, 24, 48]
HELD = [0.075, 0.025, 0.0215, 0.020, 0.010]
WAITING = [0.80, 0.50, 0.24, 0.22, 0.079]
WON_LATE = [0.025, 0.035, 0.039, 0.047, 0.043]  # the late share of the orders won on each day
PRIOR_WINS, PRIOR_WEIGHT = 300, 30  # the wins of a week before the desk has its own rate: 300, weighing as 30 orders


def elapsed(now: int) -> int:
    """Minutes of request hours so far this week."""
    return sum(min(max(now - day * DAY - OPENS, 0), OPEN) for day in range(DAYS))


class Budget:
    """Put it first among the bases."""

    def __init__(self, world, level: int, now: int, params: dict, roster: list[dict], map_: dict):
        rule = params.get("budget")
        params = {k: v for k, v in params.items() if k != "budget"}
        self.budget = rule if rule and len(roster) >= rule.get("drivers", 0) else None
        self.budget_by = None
        super().__init__(world, level, now, params, roster, map_)

    def projection(self) -> tuple[float, float]:
        """The projected on-time share of the week and its spread."""
        late = mean = var = 0.0
        for id_, order in self.orders.items():
            delivered = order["deliveredAt"]
            if id_ in self.late or any((self.now if at is None else at) > order["deadline"] for at in delivered):
                late += 1
            elif any(at is None for at in delivered):
                held = all(at is not None or self.leg_gigs.get(id_, {}).get(leg) in self.booked for leg, at in enumerate(delivered))
                hours = (order["deadline"] - self.now) / 60
                band = next((i for i, top in enumerate(BANDS) if hours < top), len(BANDS))
                f = (HELD if held else WAITING)[band]
                mean += f
                var += f * (1 - f)
        done, total = elapsed(self.now), DAYS * OPEN
        rate = (len(self.orders) + PRIOR_WEIGHT) / (done + PRIOR_WEIGHT * total / PRIOR_WINS)
        coming = rate * (total - done)
        q = WON_LATE[min(self.now // DAY, DAYS - 1)]
        orders = len(self.orders) + coming
        if orders < 1:
            return 1.0, 1.0
        mean += coming * q
        var += coming * q * (1 - q)
        return 1 - (late + mean) / orders, self.budget["sd_by"] * math.sqrt(var) / orders

    def budget_multiple(self) -> float:
        b = self.budget
        share, spread = self.projection()
        z = (share - b["floor"]) / max(spread, 1e-6)
        at = min(max((z - b["z_lo"]) / (b["z_hi"] - b["z_lo"]), 0.0), 1.0)
        return b["hi"] + (b["lo"] - b["hi"]) * at

    def params(self) -> dict:
        p = super().params()
        return {**p, "late_cost": p["late_cost"] * self.budget_by} if self.budget_by is not None else p

    def quote(self, request) -> None:
        if self.budget is None:
            return super().quote(request)
        self.budget_by = self.budget_multiple()
        try:
            super().quote(request)
            self.decisions[request["id"]]["budget"] = round(self.budget_by, 3)
        finally:
            self.budget_by = None


class BudgetThinWidePairPolicy(Budget, ThinWidePairPolicy):
    """The on-time budget on the wide late chance with pairs and the thin play."""
