"""The quote's cost by the late orders that one more order adds to the cars in flight (variants `exposure-*`).

Drivers drop booked gigs: 0.107 of a held car a day, and once a week on the flu day of RULES.md (30% of the drivers who meant to work
stay at home) a third of the held gigs due that day in the night's first hour. A car that needs a driver is late more often the less
time it has and the more cars wait for drivers with it. This file prices that, in place of the waiting-car surcharge (`slow_step`), the
late cost (`late_cost`), the Friday terms of the late chance and the day cap (`due_cap`, `due_cap_wave`):

    cost = typical fee x cost  +  `exposure_late` x Δ(expected late orders)  +  `exposure_kappa` x V x Δ P(week under 90% on time)

where each Δ is the desk's book with the order minus the book without it, and V is what the week is worth if it is ranked. The
spec, with the measurements behind each number: the "Spread exposure pricing spec" of the Track B planning thread; the fits are
spread/scratch/exposure/need_fit.py on saved weeks without `fresh-1301` to `fresh-1460`.

- `need(car, hours, waiting)`: the chance that a car which needs a driver now ends late, by its hours left to the last pickup,
  slow.py's other terms (drivers notified, premium car, drive, note, the driver list), whether a driver dropped it, and the live load:
  the waiting cars due the same day, and on other days, per 100 listed drivers.
- Scenarios: one flu day a week, each day of the week as likely. A night that has passed weighs its day by how much likelier its
  first-hour drops of the held cars due that day are under a wave than on a calm night. Monday tells nothing (nothing is held), and
  after a clear wave every later day weighs about 0.
- A car's late chance in a scenario: without a driver, `need` now; with one, an ordinary drop at the measured rate and then `need`
  with half the hours left; on its day's flu day, a third of the held cars drop at 00:00 and need a driver with the cars waiting then.
- The week: per scenario a normal late count, over-dispersed by `OMEGA`, with the spread of the wave's size, plus the orders still
  to come at the week's late share so far. P(week under 90%) is the weighted tail.

Pure functions over a book of plain dicts, and `ExposurePolicy`, which prices the policy's quotes by them. Kept out of policy.py so
that the fingerprints of the saved weeks stay, as pairs.py and late_wide.py are; play.py and live.py take the class when `exposure`
is set. `VERSION` follows this file and exposure.json.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from . import curve
from .policy import Policy, kind

DAY, HOUR = 1440, 60
OPENS, OPEN, DAYS = 8 * 60, 10 * 60, 5  # requests arrive from 08:00 for about ten hours, Monday to Friday
FITS = json.loads(Path(__file__).with_name("exposure.json").read_text(encoding="utf-8"))
VERSION = hashlib.sha256(Path(__file__).read_bytes() + Path(__file__).with_name("exposure.json").read_bytes()).hexdigest()[:12]
TERMS = ["under 2 hours", "2 to 4 hours", "4 to 8 hours", "8 to 16 hours", "16 to 30 hours", "30 hours or more",
         "under 10 drivers notified", "10 to 39 drivers notified", "premium car", "hours of drive beyond 4", "note",
         "hundreds of drivers short of 760", "dropped by a driver",
         "ln(1 + waiting cars due the same day per 100 drivers)", "ln(1 + waiting cars due on other days per 100 drivers)",
         "due on the flu day, from its night on", "needs a driver at night (20:00 to 07:00)", "ln(1 + hours it has waited for a driver)",
         "dropped x ln(1 + waiting cars due the same day per 100 drivers)", "on the flu day with under 16 hours left"]
BANDS = (2, 4, 8, 16, 30)
LOAD = (13, 14, 18)  # the load terms, which `exposure_load` multiplies
M = FITS["measured"]


def sig(z: float) -> float:
    return 1 / (1 + math.exp(-max(-40.0, min(40.0, z))))


def night(minute: int) -> bool:
    return not 7 * HOUR <= minute % DAY < 20 * HOUR


def terms(hours: float, car: dict, dropped: bool, same: float, other: float, drivers: int, flu: bool = False, dark: bool = False, waited: float = 0.0) -> list[float]:
    """The terms of `need` in the order of `TERMS`. `car` has `notified`, `premium`, `drive` (minutes) and `note`."""
    band = sum(hours >= b for b in BANDS)
    per = max(drivers, 1) / 100
    return ([float(band == k) for k in range(6)]
            + [float(car["notified"] < 10), float(10 <= car["notified"] < 40), float(car["premium"]), max(0, car["drive"] - 4 * HOUR) / HOUR,
               float(car["note"]), max(0, 760 - drivers) / 100, float(dropped), math.log(1 + same / per), math.log(1 + other / per), float(flu),
               float(dark), math.log(1 + max(waited, 0.0)), float(dropped) * math.log(1 + same / per), float(flu and hours < 16)])


def hard(car: dict, drivers: int) -> float:
    """The part of `need`'s log odds that is the car's own: everything but the hours, the drop and the load."""
    w = FITS["weights"]
    return sum(w[k] * v for k, v in enumerate(terms(0, car, False, 0, 0, drivers)) if 6 <= k < 12)


def need(car: dict, hours: float, same: float, other: float, drivers: int, load: float = 1.0, dropped: bool = False, flu: bool = False,
         dark: bool = False, waited: float = 0.0, shift: float = 0.0) -> float:
    """The chance that a car which needs a driver now, with `hours` to its last pickup, ends late (certainly, past its last pickup). `car["hard"]` is `hard(car)`; `flu`
    is for a car due on the flu day, once its night has come: fewer drivers work that day. `dark` when it is night now (drivers plan
    in the morning), `waited` the hours it has needed a driver already, `shift` a shift of the log odds shared with other cars."""
    if hours < 0:
        return 1.0
    w, per = FITS["weights"], max(drivers, 1) / 100
    z = shift + w[sum(hours >= b for b in BANDS)] + car["hard"] + w[12] * dropped + w[15] * flu + w[16] * dark + w[17] * math.log(1 + max(waited, 0.0)) + w[19] * (flu and hours < 16)
    z += load * ((w[13] + w[18] * dropped) * math.log(1 + same / per) + w[14] * math.log(1 + other / per))
    return sig(z)


def ratio(held: int, dropped: int) -> float:
    """How much likelier a night's first-hour drops are under a wave than on a calm night."""
    calm, shares = M["calm_share"], M["wave_shares"]
    dropped = min(dropped, held)
    return sum((s / calm) ** dropped * ((1 - s) / (1 - calm)) ** (held - dropped) for s in shares) / len(shares)


def weights(nights: dict[int, tuple[int, int]], now: int) -> dict:
    """The chance of each day of the week still to come being the flu day, and None for "no flu day left". `nights` is day -> (held cars
    due that day as its night began, of them dropped in the night's first hour), for the nights that have passed."""
    weight = {}
    for day in range(DAYS):
        if day * DAY + HOUR > now:
            weight[day] = 1.0
        else:
            weight[None] = weight.get(None, 0.0) + ratio(*nights.get(day, (0, 0)))
    total = sum(weight.values())
    return {d: w / total for d, w in weight.items()}


def by_night(hours: float) -> float:
    """The chance that a car without a driver now has one when the night `hours` away begins (book_rows.py)."""
    return next(p for under, p in M["held_by_night"] if hours < under)


def day_late(cars: list[dict], day: int, flu: bool, drivers: int, other: float, load: float, share: float, seen: bool = False, now: int = 12 * HOUR,
             shift: float = 0.0) -> tuple[float, float]:
    """The mean and variance of the late count of the cars due on `day`, with that day the flu day still to come or not; `seen` when its
    night has passed and was the flu day's. Each car: `held` (1 with a driver,
    0 without), `hours` left, `night` (hours from that day's 00:00 to its last pickup), `picked` (on the road), `hard`, and `weight`, its
    share of a waiting car (1, less for the candidate), and `waited`, the hours it has needed a driver. A car past its last pickup and not
    picked up is late. `shift` moves the log odds of every car that needs a driver."""
    eps, rate = M["held_late"], M["drop_day"]
    if flu:
        held = [1.0 if c["held"] else by_night(c["hours"] - c["night"]) for c in cars]
        n = [(1 - h + h * share) * c["weight"] for c, h in zip(cars, held)]
    else:
        held = [1.0 if c["held"] else 0.0 for c in cars]
        n = [(1 - h) * c["weight"] for c, h in zip(cars, held)]
    waiting = sum(n)
    mean = var = 0.0
    for c, k, h in zip(cars, n, held):
        if c["picked"]:
            p = eps
        elif c["hours"] < 0:
            p = 1.0
        elif flu and c["hours"] > c["night"]:  # the night is still to come
            p = h * (1 - share) * eps + (1 - h + h * share) * need(c, c["night"], waiting - k, other, drivers, load, True, True, True, shift=shift)
        elif not c["held"]:
            p = need(c, c["hours"], waiting - k, other, drivers, load, flu=seen, dark=night(now), waited=c.get("waited", 0.0), shift=shift)
        else:
            x = 1 - math.exp(-rate * max(c["hours"], 0) / 24)
            p = (1 - x) * eps + x * need(c, c["hours"] / 2, waiting + 1, other, drivers, load, True, seen, shift=shift)
        mean += p
        var += p * (1 - p)
    return mean, var


# Gauss-Hermite nodes and weights for a standard normal, 5 points
NODES = list(zip([-2.857, -1.3556, 0.0, 1.3556, 2.857], [0.01126, 0.22208, 0.53333, 0.22208, 0.01126]))


class Book:
    """The cars in flight at a minute, with each day's late count per scenario and shift, so that a quote recomputes only its own day.

    Cars are late together. Every car shares the week's shift of its log odds (normal, sd `week_sd`, the fit's week intercepts); the cars
    due on the flu day share a further shift (sd `flu_sd`), and those due on a calm day one of sd `calm_sd`, both measured on the fit
    weeks as the day's late count's spread beyond the cars' own (checks.py). The chance of a week under 90% is integrated over the
    week's shift and the flu day's on 5 nodes each; a calm day's shift enters as variance, and within a node the count is normal."""

    def __init__(self, now: int, cars: list[dict], nights: dict[int, tuple[int, int]], drivers: int, orders: int, resolved: int, late: int, load: float = 1.0):
        self.now, self.drivers, self.load, self.orders, self.resolved, self.late = now, drivers, load, orders, resolved, late
        self.days: dict[int, list[dict]] = {}
        for c in cars:
            self.days.setdefault(c["day"], []).append(c)
        self.weights = weights(nights, now)
        self.seen = {d for d, (held, dropped) in nights.items() if d * DAY + HOUR <= now and ratio(held, dropped) > 1}
        self.waiting = {d: sum(c["held"] < 1 for c in cs) for d, cs in self.days.items()}
        self.sums = {d: self.count(d, self.days[d]) for d in self.days}

    def flu_possible(self, day: int) -> bool:
        return self.weights.get(day, 0.0) > 0

    def count(self, day: int, cars: list[dict]) -> dict:
        """The mean and variance of the late count of the cars due on `day`: (None, i) for the day calm and the week's shift at node i,
        (day, i, j) for the day the flu day with the flu day's shift at node j."""
        other = sum(n for d, n in self.waiting.items() if d != day)
        week, flu = M["week_sd"], M["flu_sd"]
        out = {}
        for i, (x, _) in enumerate(NODES):
            out[(None, i)] = day_late(cars, day, False, self.drivers, other, self.load, 0, day in self.seen, self.now, week * x)
            if self.flu_possible(day):
                for j, (y, _) in enumerate(NODES):
                    out[(day, i, j)] = day_late(cars, day, True, self.drivers, other, self.load, M["wave_share"], shift=week * x + flu * y)
        return out

    def future(self) -> tuple[float, float]:
        """The orders still to come this week, and their late share: the rate so far pulled towards 0.43 orders a listed driver a week with
        the weight of one day; the measured late share, which the week's shift moves. The share of the orders resolved so far would say
        less: a late order resolves later than one on time."""
        today = self.now // DAY
        elapsed = min(today, DAYS) * OPEN + (min(max(self.now % DAY - OPENS, 0), OPEN) if today < DAYS else 0)
        rate = (self.orders + M["orders_a_driver"] * self.drivers / DAYS) / (elapsed + OPEN)
        return rate * max(0, DAYS * OPEN - elapsed), M["late_share"]

    def risk(self, day: int | None = None, car: dict | None = None, line: float = 0.10) -> tuple[float, float]:
        """P(week under 90% on time; `line` is the late share) and the expected late count of the book, with `car` added on `day` when given."""
        sums = self.sums
        if car is not None:
            sums = {**sums, day: self.count(day, self.days.get(day, []) + [car])}
        later, share = self.future()
        orders = self.orders + later + (car is not None)
        base = math.log(share / (1 - share))
        calm = M["calm_sd"]
        fail = expected = 0.0
        for flu, weight in self.weights.items():
            flu = flu if flu in sums else None
            for i, (x, a) in enumerate(NODES):
                s = sig(base + M["week_sd"] * x)
                m0, v0, spread = self.late + s * later, s * (1 - s) * later, 0.0
                for d, counts in sums.items():
                    if d != flu:
                        m, v = counts[(None, i)]
                        m0, v0, spread = m0 + m, v0 + v, spread + (calm * v) ** 2
                for j, (y, b) in enumerate(NODES if flu is not None else [(0.0, 1.0)]):
                    m, v = sums[flu][(flu, i, j)] if flu is not None else (0.0, 0.0)
                    mean, var = m0 + m, M["omega"] * (v0 + v) + spread
                    fail += weight * a * b * 0.5 * math.erfc((line * orders - mean) / math.sqrt(max(var, 1e-9)) / math.sqrt(2))
                    expected += weight * a * b * mean
        return fail, expected


def cost(book: Book, day: int, car: dict, late: float, kappa: float, value: float, tail: bool = True) -> float:
    """The euros that one more order, its car due on `day`, adds: `late` euros for each expected late order it adds, and `kappa` x
    `value` x its change to the chance of a week under 90%."""
    f0, e0 = book.risk()
    f1, e1 = book.risk(day, car)
    return late * (e1 - e0) + (kappa * value * (f1 - f0) if tail else 0.0)


# The policy ------------------------------------------------------------------------------------------------------------------------

PARAMS = {
    "exposure": False,        # price each quote by what its order adds to the book's late orders and to the risk of a week under 90%
    "exposure_kappa": 1.0,    # the price of the 90% line: multiplies the week's value x the change to that risk
    "exposure_load": 1.0,     # multiplies need's load weights
    "exposure_late": 82.0,    # euros a late order costs: the refund and the dealer's trust
    "exposure_version": "",   # VERSION, set by the variant, so that a sweep plays the weeks again when this file changes
}
REPLACES = {"slow_step": 0, "late_cost": 0, "due_cap": 0, "due_cap_wave": 0, "slow_model": "", "rule_cost": 0}


class ExposurePolicy(Policy):
    """The policy with the quote's cost from this file, for a variant that sets `exposure`. Put it first among the bases."""

    def __init__(self, world, level: int, now: int, params: dict, roster: list[dict], map_: dict):
        own = {name: params.get(name, default) for name, default in PARAMS.items()}
        rest = {k: v for k, v in params.items() if k not in PARAMS}
        if own["exposure"]:
            clash = {k: rest[k] for k, off in REPLACES.items() if rest.get(k, off) != off}
            if clash:
                raise ValueError(f"`exposure` replaces {sorted(REPLACES)}; turn these off: {clash}")
        super().__init__(world, level, now, rest, roster, map_)
        self.p.update(own)
        self.nights: dict[int, list[int]] = {}  # day -> [held cars due that day as its night began, of them dropped in its first hour]
        self.needs_since: dict[str, int] = {}  # order id -> the minute its car last came to need a driver: the win, a drop, a failed visit

    def handle(self, event) -> None:
        at = event.get("at", self.now)
        day = at // DAY
        if at % DAY < HOUR and day not in self.nights and day < DAYS:  # the night begins: count the held cars due today before its first event
            self.nights[day] = [self.held_due(day), 0]
        if event["kind"] in ("gig_dropped", "no_show") and event.get("gigId") in self.posts:
            for stop in self.posts[event["gigId"]]["stops"]:
                order = self.orders.get(stop["orderId"])
                if order is None:
                    continue
                self.needs_since[order["id"]] = at
                if at % DAY < HOUR and order["lastPickupAt"] // DAY == day and day in self.nights and stop["kind"] == "pickup":
                    self.nights[day][1] += 1
        elif event["kind"] == "visit_failed" and event.get("orderId"):
            self.needs_since[event["orderId"]] = at
        super().handle(event)

    def win(self, order) -> None:
        self.needs_since.setdefault(order["id"], self.now)
        super().win(order)

    def held_due(self, day: int) -> int:
        return sum(1 for order in self.orders.values() if order["lastPickupAt"] // DAY == day and None in order["deliveredAt"] and self.held(order))

    def held(self, order) -> bool:
        return all(at is not None or self.leg_gigs.get(order["id"], {}).get(leg) in self.booked for leg, at in enumerate(order["deliveredAt"]))

    def car(self, request, last: int, held: bool, waited: float) -> dict:
        legs = request["legs"]
        car = {"notified": min(self.notified[leg["pickup"]["placeId"]] for leg in legs), "premium": any(leg["car"]["premium"] for leg in legs),
               "drive": self.drive(request), "note": request["note"] is not None}
        hours = (last - self.now) / HOUR
        return {**car, "hard": hard(car, len(self.roster)), "day": last // DAY, "held": held, "picked": held and hours < 0, "hours": hours,
                "night": hours - (last // DAY * DAY - self.now) / HOUR, "weight": 1.0, "waited": waited}

    def book(self, p: dict) -> Book:
        cars, late = [], 0
        for id_, order in self.orders.items():
            delivered = order["deliveredAt"]
            if id_ in self.late or any((self.now if at is None else at) > order["deadline"] for at in delivered):
                late += None not in delivered
            if None not in delivered or id_ not in self.requests:
                continue
            held = self.held(order)
            waited = 0.0 if held else (self.now - self.needs_since.get(id_, self.won_at.get(id_, self.now))) / HOUR
            cars.append(self.car(self.requests[id_], order["lastPickupAt"], held, waited))
        resolved = len(self.orders) - len(cars)
        nights = {d: (held, dropped) for d, (held, dropped) in self.nights.items()}
        return Book(self.now, cars, nights, len(self.roster), len(self.orders), resolved, late, p["exposure_load"])

    def added(self, book: Book, request, option: dict, p: dict) -> float:
        """Euros that the order adds if the dealer takes `option`, the fastest of the menu quoted."""
        last = option["deadline"] - self.drive(request)
        car = {**self.car(request, last, False, 0.0), "weight": M["candidate_waiting"]}
        later, _ = book.future()
        value = (book.orders + later) * M["margin"]
        return cost(book, car["day"], car, p["exposure_late"], p["exposure_kappa"], value)

    def quote(self, request) -> None:
        p = self.params()
        if not p["exposure"] or not p["curve"] or self.explored(request, p):
            return super().quote(request)
        reason, options = self.choose(request, p)
        if reason:
            return super().quote(request)
        self.requests[request["id"]] = request
        self.requested[request["dealerId"]] = self.requested.get(request["dealerId"], 0) + 1
        fee, day, on_time = request["referenceFeeCents"], request["arrivedAt"] // DAY, self.trust.get(request["dealerId"], 0)
        own = p["kinds"].get(kind(request), {})
        private = any(leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"] for leg in request["legs"])
        flat = own["cost"] if own.get("cost") else p["long_cost"] if p["long_cost"] and self.long(request, p) else p["private_cost"] if p["private_cost"] and private else p["cost"]
        flat += p["premium_cost"] * any(leg["car"]["premium"] for leg in request["legs"])
        usual, shift, slope = self.usual_fee(request, p), self.shift(day, p, request["legs"][0]["pickup"]["placeId"]), self.model["slope"] * p["slope_by"]
        book = self.book(p)
        menu = sorted(options, key=lambda o: curve.SPEED.index(o["kind"]))
        best = None
        for k in range(len(menu)):  # the full menu, then without its fastest option, and so on: each priced on its fastest option's cost
            quoted = menu[k:]
            first = curve.fastest(quoted)
            at_list = curve.at_list(request, quoted, on_time, self.model) + own.get("odds", 0)
            cost_ = max(usual * flat + 100 * self.added(book, request, first, p), usual)
            multiple = curve.best(at_list, shift, first["listPriceCents"], cost_, slope)
            value = (multiple * first["listPriceCents"] - cost_) * curve.chance(at_list, multiple, shift, slope)
            if best is None or value > best[0]:
                best = (value, quoted, multiple, at_list - slope * math.log(multiple))
        _, quoted, multiple, log_odds = best
        prices = {o["kind"]: int(round(max(o["listPriceCents"] * multiple, fee * self.floor(request, p)))) for o in quoted}
        self.asked[request["id"]] = (request["dealerId"], day, log_odds)
        self.asked_at[request["id"]] = request["legs"][0]["pickup"]["placeId"]
        if p["same_day_extra"] and len(prices) > 1 and "same_day" in prices:
            prices["same_day"] = int(round(prices["same_day"] * (1 + p["same_day_extra"])))
        self.decisions[request["id"]] = {"declined": None, "prices": prices}
        if p["min_on_time"]:
            self.decisions[request["id"]]["onTime"] = round(self.on_time(), 4)
        self.outbox.append({"type": "quote", "requestId": request["id"], "prices": prices})
