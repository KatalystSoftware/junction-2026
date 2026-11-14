"""A cap on the cars to collect on one day (variants `*-day-cap-*`).

Some nights a wave of drivers drop the gigs they booked: 10 or more drops in a day's first hour, against 2 on other
nights. It came in 42 of the default's 230 saved weeks on a Friday and in 16 to 25 on another weekday, and the desk
cannot see it coming. The dropped cars must then find a driver on the day itself, and on that day few book: in
`fresh-098` the Friday gigs that ended late were seen 70 to 150 times each and stayed open at 1.5 to 2.5 x the typical
fee until they expired. Without a wave, the orders due on a Friday are 3 to 5% late however many there are. With one,
they are 8% late with 50 to 99 due that day and 15% with 100 or more. The default's three lowest weeks, `fresh-098`
(88.4%), `fresh-284` (89.9%) and `fresh-053` (90.2%), each had a Friday wave of 29 or 30 drops on 101 to 105 orders due
that day.

So the desk keeps one day from carrying too much: it does not quote an option whose last minute to collect the car
falls on a day that already has `day_cap` won orders with a car still to deliver. A slower option of the same request,
due on another day, is still quoted. With no option left, the request is declined as `day_full`.

Kept out of policy.py so that the fingerprints of the saved weeks stay: play.py takes this class when `day_cap` is set.
Raise `day_cap_version` whenever this file changes, so a sweep plays the weeks again.
"""
from __future__ import annotations

from typing import Optional

from spread.starter import DAY

from .policy import Policy

PARAMS = {
    "day_cap": 0,          # the most won orders with a car still to deliver whose last pickup minute falls on one day; 0 is no cap
    "day_cap_version": 1,  # raised when this file changes
}


class DayCapPolicy(Policy):
    def __init__(self, world, level: int, now: int, params: dict, roster: list[dict], map_: dict):
        own = {name: params.get(name, default) for name, default in PARAMS.items()}
        super().__init__(world, level, now, {k: v for k, v in params.items() if k not in PARAMS}, roster, map_)
        self.p.update(own)

    def due_on(self, day: int) -> int:
        """The won orders with a car still to deliver whose last minute to collect it falls on the day."""
        return sum(1 for order in self.orders.values() if order["lastPickupAt"] // DAY == day and None in order["deliveredAt"])

    def choose(self, request, p: dict) -> tuple[Optional[str], list[dict]]:
        reason, options = super().choose(request, p)
        if reason or not self.p["day_cap"]:
            return reason, options
        drive = self.drive(request)
        options = [o for o in options if self.due_on((o["deadline"] - drive) // DAY) < self.p["day_cap"]]
        return (None, options) if options else ("day_full", [])
