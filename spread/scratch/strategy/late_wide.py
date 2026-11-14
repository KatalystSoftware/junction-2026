"""The chance that an order arrives late, from what the desk knows at the quote: slow.py's terms, the won cars that wait
for a driver, and the request fields that slow.py leaves out (the sites' stated hours, the ready time, the slower options
quoted, the charge, the drivers who live at the delivery and in the pickup town, the weekday and the hour).

One logistic fit (late_fit.py) over the won one-car dealer orders of the saved weeks of 37 variants. It has the shape of
spreadlab/slow.py, so a variant can use it in its place: `chance(known(...))`. It needs no numpy and reads nothing.
"""
from __future__ import annotations

import math

DAY, HOUR = 1440, 60
CAP = 30  # the waiting cars count up to this many
NAMES = [
    # slow.py's terms, with its own definitions
    "intercept", "under 6 hours", "6 to 8 hours", "8 to 12 hours", "12 to 24 hours", "under 10 drivers notified",
    "10 to 39 drivers notified", "premium car", "hours of drive beyond 4", "Friday", "note", "hundreds of drivers short of 760",
    "collected by a Friday", "collected by a Friday with under 12 hours",
    # the won cars without a driver at the quote, in tens
    "tens of waiting cars due within 24 hours", "tens of waiting cars due later",
    "tens of waiting cars due within 24 hours, for an order with under 12 hours",
    # the request's own fields
    "under 6 hours by the sites' hours", "6 to 12 hours by the sites' hours", "12 to 24 hours by the sites' hours",
    "car ready on a later day", "under 4 hours to collect the car", "4 to 8 hours to collect the car",
    "a slower option is quoted too", "within_3_days is quoted", "charge under 30%",
    "100 or more drivers live within 30 km of the delivery", "under 10 drivers live within 30 km of the delivery",
    "no driver lives in the pickup town", "Monday", "Tuesday", "Wednesday", "arrives from 14:00", "due next week",
]
# The fit of late_fit.py over every seed: 404,374 orders of 1,356 weeks, 37 variants and 401 seeds. On seeds left out, a fit on
# the other half ranks late orders with an AUC of 0.774, where slow.py's `friday` weights have 0.739 (README).
WEIGHTS = [-3.649, 0.594, 0.135, 0.088, -0.722, 0.673, 0.557, 1.590, 0.468, -0.410, 0.530, 0.240, -0.291, 0.769,  # slow.py's terms
           0.305, 0.480, 0.860,  # the waiting cars
           0.587, 0.232, 0.735, -0.631, 0.148, -0.022, -0.149, -0.658, 0.962, -0.407, 0.109, 0.617, -0.488, -0.314, -0.270, 0.174, -1.345]


def open_at(minute: int, hours: dict | None) -> bool:
    """Whether a site's stated hours show it open at a minute. A private address has no hours and counts as open."""
    if hours is None:
        return True
    day, at = divmod(minute, DAY)
    if day % 7 in hours["weekdays"]:
        return hours["opens"] <= at < hours["closes"]
    saturday = hours.get("saturday")
    return bool(day % 7 == 5 and saturday and saturday["opens"] <= at < saturday["closes"])


def last_open(minute: int, hours: dict | None) -> int:
    """The last minute up to `minute` at which the site is open."""
    if hours is None:
        return minute
    for _ in range(10):
        if open_at(minute, hours):
            return minute
        day, at = divmod(minute, DAY)
        closes = hours["closes"] if day % 7 in hours["weekdays"] else hours["saturday"]["closes"] if day % 7 == 5 and hours.get("saturday") else 0
        opens = hours["opens"] if day % 7 in hours["weekdays"] else hours["saturday"]["opens"] if day % 7 == 5 and hours.get("saturday") else DAY
        minute = day * DAY + closes - 1 if closes and at >= closes else day * DAY - 1 if at < opens or not closes else minute - 1
    return minute


def last_pickup(leg: dict, deadline: int, drive: int) -> int:
    """The last minute to collect the car and still deliver it by the deadline, by the road minutes and the stated hours
    of both sites: the car must arrive while the delivery site is open, and leave while the pickup site is."""
    arrive = last_open(deadline, leg["delivery"]["hours"])
    return last_open(arrive - drive, leg["pickup"]["hours"])


def known(request: dict, options: list[dict], notified: dict[str, int], at_home: dict[str, int], drive: int, drivers: int,
          waiting_24: int, waiting_later: int) -> list[float]:
    """What the desk knows at the quote, in the order of `NAMES`, for a request with one car.

    `options` are the options the desk quotes. `notified` is place -> the drivers who live within 30 km of it (the policy's
    `notified`), `at_home` is place -> the drivers who live in the town itself, `drive` the road minutes, `drivers` the length
    of the driver list. `waiting_24` is the policy's `unbooked(24)` and `waiting_later` its `unbooked() - unbooked(24)`."""
    leg, fastest = request["legs"][0], min(options, key=lambda o: o["deadline"])
    pickup, delivery = leg["pickup"]["placeId"], leg["delivery"]["placeId"]
    last = fastest["deadline"] - drive
    hours, friday = (last - request["respondBy"]) / HOUR, last // DAY % 7 == 4
    near, w24, later = notified[pickup], min(waiting_24, CAP) / 10, min(waiting_later, CAP) / 10
    by_sites = last_pickup(leg, fastest["deadline"], drive)
    real = (by_sites - request["respondBy"]) / HOUR
    ready = max(request["respondBy"], leg["pickup"]["window"]["from"])
    collect = (by_sites - ready) / HOUR
    kinds = {o["kind"] for o in options}
    charge = leg["car"]["chargePercent"]
    day, at = divmod(request["arrivedAt"], DAY)
    return [1.0, float(hours < 6), float(6 <= hours < 8), float(8 <= hours < 12), float(12 <= hours < 24),
            float(near < 10), float(10 <= near < 40), float(leg["car"]["premium"]),
            max(0, drive - 4 * HOUR) / HOUR, float(day % 7 == 4), float(request["note"] is not None),
            max(0, 760 - drivers) / 100, float(friday), float(friday and hours < 12),
            w24, later, w24 * float(hours < 12),
            float(real < 6), float(6 <= real < 12), float(12 <= real < 24),
            float(ready // DAY > request["respondBy"] // DAY), float(collect < 4), float(4 <= collect < 8),
            float(len(options) > 1), float("within_3_days" in kinds), float(charge is not None and charge < 30),
            float(notified[delivery] >= 100), float(notified[delivery] < 10), float(at_home.get(pickup, 0) == 0),
            float(day % 7 == 0), float(day % 7 == 1), float(day % 7 == 2), float(at >= 14 * HOUR), float(fastest["deadline"] // DAY >= 7)]


def chance(known_: list[float], weights: list[float] | None = None, odds: float = 0.0) -> float:
    """`odds` adds to the log odds, as in slow.chance, for what the desk knows beside `known` (the policy's `snow_odds`)."""
    return 1 / (1 + math.exp(-sum(w * v for w, v in zip(weights or WEIGHTS, known_)) - odds))
