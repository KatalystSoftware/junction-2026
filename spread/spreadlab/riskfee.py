"""Driver fees by each car's risk of ending late (variants `risk-*`).

The policy opens every gig at the typical fee and raises it a tenth of the typical fee an hour, to 1.2 x, from the
posting on. Most cars are booked within minutes at the opening fee whatever it is, and a raise barely moves the drivers
who wait: it pays only when a late order costs more than 2 to 3 typical fees. So here a gig holds its opening fee
until its car is at risk, and only then rises as the policy's do, a tenth of the typical fee an hour to `fee_cap`:

- **Risk** is the car's chance of ending late (slow.py) with the hours left now to collect it. The chance grows as the
  hours run out, faster for a car with few drivers notified, a premium car, a long drive or a Friday deadline. The gig
  rises from the first minute that chance reaches `risk_raise_late`: from the posting for a risky car, which then
  gets the policy's fees, and 6 to 24 hours before the last pickup for the others. At 4%, on 40 weeks of
  `slow-step-gate-25`, 22% of one-car orders rise from the posting, 13% with under 24 hours left, 30% under 12, 17%
  under 8 and 18% under 6. A car that never reaches the bar keeps its fee until the deadline warning and the offers.
- **A safe car opens lower.** A car with at least `risk_open_hours` to its last pickup and a chance under
  `risk_open_late` at the posting opens at `risk_open` x the typical fee. On 40 paired weeks of `curve-fee-0.9-cost-1.2`
  and `curve-fee-1.0-cost-1.2`, such cars paid 0.08 to 0.10 x less at 0.9 and were late as often; cars with under 8
  hours were late more often.
- **The waiting cars that count.** A safe car that opens lower waits longer for a driver, and each waiting car makes the
  next quotes dearer (`slow_step`) and fills the gate (`max_unbooked`). With `risk_queue_hours` both count only the
  waiting cars due within that many hours.

Kept out of policy.py so that the fingerprints of the saved weeks stay: play.py takes this class when `risk_fees` is
set. Raise `risk_version` whenever this file changes, so a sweep plays the weeks again.
"""
from __future__ import annotations

import math
from typing import Optional

from spread.starter import HOUR, steep

from . import slow
from .policy import Policy, kind

PARAMS = {
    "risk_fees": False,      # fees by the car's risk; off is the policy's own fees
    "risk_open": 0.9,        # the opening fee of a safe car, as a multiple of the typical fee
    "risk_open_hours": 16,   # ... a car with at least this many hours to its last pickup at the posting ...
    "risk_open_late": 0.06,  # ... and a chance of ending late under this at the posting
    "risk_raise_late": 0.04,  # the gig holds its opening fee until the car's chance of ending late, with the hours left then, reaches this
    "risk_queue_hours": 0,   # `slow_step` and `max_unbooked` count only the waiting cars due within this many hours; 0 counts all
    "risk_version": 1,       # raised when this file changes
}
# The hours left under which slow.py's chance steps up (its hour terms), from the most to the fewest.
STEPS = (24, 12, 8, 6)


class RiskFeePolicy(Policy):
    def __init__(self, world, level: int, now: int, params: dict, roster: list[dict], map_: dict):
        own = {name: params.get(name, default) for name, default in PARAMS.items()}
        super().__init__(world, level, now, {k: v for k, v in params.items() if k not in PARAMS}, roster, map_)
        self.p.update(own)

    def late_at(self, order, minute: int) -> float:
        """The chance that the order ends late if its car still has no driver at this minute (slow.py, with the hours
        left then to collect the car)."""
        request = self.requests[order["id"]]
        notified = min(self.notified[leg["pickup"]["placeId"]] for leg in request["legs"])
        odds = self.p["snow_odds"] if self.p["snow_odds"] and self.snowy(order["legs"], minute, order["deadline"]) else 0
        known = slow.known({**request, "respondBy": minute}, {"deadline": order["deadline"]}, notified, self.drive(request), len(self.roster))
        return slow.chance(known, slow.MODELS[self.p["slow_model"]], odds)

    def at_risk(self, order) -> Optional[int]:
        """The first minute from now that the car is at risk, or None when it is not before its last pickup."""
        last = order["lastPickupAt"]
        for minute in [self.now] + [last - h * HOUR + 1 for h in STEPS if last - h * HOUR + 1 > self.now]:
            if self.late_at(order, minute) >= self.p["risk_raise_late"]:
                return minute
        return None

    def fees_for(self, order, cars, opening: float = 1.0):
        p = self.params()
        request = self.requests[order["id"]]
        if not p["risk_fees"] or len(order["legs"]) != 1 or p["kinds"].get(kind(request), {}).get("fee"):
            return super().fees_for(order, cars, opening)
        usual = self.usual_fee(request, p) * cars / len(order["legs"])
        if p["snow_fee"] and self.snowy(order["legs"], self.now, order["deadline"]):
            usual *= p["snow_fee"]
        safe = (order["lastPickupAt"] - self.now >= p["risk_open_hours"] * HOUR and self.late_at(order, self.now) < p["risk_open_late"])
        fee = usual * (p["risk_open"] if safe else self.opening(request, p)) * opening
        if order["id"] in self.urgent:
            return steep(self.now, fee, self.level)
        fees = {self.now: fee}
        risk = self.at_risk(order)
        if risk is not None:  # from then on the policy's rises: a tenth of the typical fee an hour, to the cap
            step, top = usual / 10, max(fee, usual * (p["fee_cap"] or 1.5))
            fees.update({risk + k * HOUR: min(fee + k * step, top) for k in range(1, math.ceil((top - fee) / step - 1e-9) + 1)})
        steps, shown = [], None
        for at, fee_ in sorted(fees.items()):
            cents = max(1, int(fee_ + 0.5))
            if cents != shown:
                steps.append({"at": at, "feeCents": cents})
                shown = cents
        return steps

    def unbooked(self, hours: float = 0) -> int:
        return super().unbooked(hours or self.p["risk_queue_hours"])
