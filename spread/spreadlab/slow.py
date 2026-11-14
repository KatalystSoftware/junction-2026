"""The chance that an order arrives late, from what the desk knows at the quote: how long the desk has to find a
driver, how many drivers hear of the pickup, the car, the drive and the day. A car that is slow to find a driver
fills the backlog, and the backlog stops the desk from quoting better requests (policy: `slow_bar`, `slow_step`).

The weights are a logistic regression over the won orders of the reference's saved weeks (scratch/slow_fit.py).
"""
from __future__ import annotations

import math

DAY, HOUR = 1440, 60
NAMES = ["intercept", "under 6 hours", "6 to 8 hours", "8 to 12 hours", "12 to 24 hours", "under 10 drivers notified",
         "10 to 39 drivers notified", "premium car", "hours of drive beyond 4", "Friday", "note", "hundreds of drivers short of 760",
         "collected by a Friday", "collected by a Friday with under 12 hours"]
# The first fit has no terms for Friday's deadlines, and every variant played with it keeps it: a list shorter than `NAMES` leaves the last terms out.
WEIGHTS = [-4.515, 1.837, 1.261, 0.855, 0.422, 0.795, 0.695, 1.488, 0.42, 0.258, 0.424, 0.292]
# The second fit, over 401 weeks: an order that must be collected on a Friday is late more often, and one with under 12 hours
# then twice as often as on another day (24% against 14% with under 6 hours). An order that arrives on a Friday for next week is not.
MODELS = {"": WEIGHTS, "friday": [-4.601, 1.803, 1.239, 0.813, 0.392, 0.784, 0.681, 1.539, 0.454, -0.327, 0.437, 0.3, 0.22, 0.715]}


def known(request: dict, fastest: dict, notified: int, drive: int, drivers: int) -> list[float]:
    """What the desk knows at the quote, in the order of `NAMES`. The hours run from the answer to the last minute to
    collect the car, if the dealer takes the fastest option quoted. `drivers` is the length of the week's driver list."""
    last = fastest["deadline"] - drive
    hours, friday = (last - request["respondBy"]) / HOUR, last // DAY % 7 == 4
    return [1.0, float(hours < 6), float(6 <= hours < 8), float(8 <= hours < 12), float(12 <= hours < 24),
            float(notified < 10), float(10 <= notified < 40), float(any(leg["car"]["premium"] for leg in request["legs"])),
            max(0, drive - 4 * HOUR) / HOUR, float(request["arrivedAt"] // DAY % 7 == 4), float(request["note"] is not None),
            max(0, 760 - drivers) / 100, float(friday), float(friday and hours < 12)]


def chance(known_: list[float], weights: list[float] = WEIGHTS) -> float:
    return 1 / (1 + math.exp(-sum(w * v for w, v in zip(weights, known_))))
