"""The quote as an optimisation: the multiple of the list price with the highest expected value of the order.

    value = chance that the dealer buys x (price x (1 - REFUND x late) - (cost + mu) x typical fee + lambda x (0.1 - late))

- The chance is a logistic curve in the log of the price, as in curve.py, with its own weights: the options quoted, the
  dealer's orders on time and late, the lane, the hour and the car.
- The market level is what no weight holds: the world's price level and today's deviation from it, with the price war as
  a second kind of day. `Level` keeps a belief over both, updated by every answer. It differs from `curve.shift` in two
  ways: the world's part carries over to the next morning, and the price is chosen over the whole belief, not at its
  most likely point.
- `late` and `cost` are the order's chance to arrive late and its fees, fines and waiting over its typical fee, by what
  the desk sees at the quote. A late order gives back REFUND of its price.
- `mu` is the price of a driver's time, in typical fees for each order won. It does what a higher `cost` or the backlog
  surcharge does. `lambda` is the price of the 90% rule, in euros: an order that is surely on time earns a tenth of it,
  and an order pays it in full by its chance to be late. It does what `late_cost` and `slow_step` do.

The weights are in optquote.json, fitted by spikes/spread-optim/export.py on the saved weeks of 151 worlds.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

DAY, HOUR = 1440, 60
WEIGHTS = json.loads(Path(__file__).with_name("optquote.json").read_text(encoding="utf-8"))
SPEED = ["same_day", "next_day", "within_3_days"]
STEP = 0.025  # the grid of the belief, in log price
WORLD = [-0.25 + STEP * n for n in range(21)]  # the world's level around the mean world's
TODAY = [-0.40 + STEP * n for n in range(29)]  # today's level around the world's
LEVELS = [WORLD[0] + TODAY[0] + STEP * n for n in range(len(WORLD) + len(TODAY) - 1)]  # their sums
WAR_UNDER = -0.12  # a day this far under its world's level was the price war (RULES.md: 20% under, once a week)
DAYS = 5  # the days with requests
MULTIPLES = [1.0 + 0.02 * n for n in range(81)]  # the multiples of the list price to choose from: 1.0 to 2.6
DECLINE = 10  # the multiple when no price has a value above zero
SLACK = (4, 6, 8, 12, 24, 30, 48)  # the bands of the hours to find a driver
DRIVERS = (630, 950)  # the shortest and the longest driver list of the saved weeks: the weights hold inside them
OPENING = 0.9  # the fees paid rise by this share of a rise in the opening fee (the `curve-fee-*` weeks); the weights are for 1.0


def sigmoid(z: float) -> float:
    return 1 / (1 + math.exp(-z)) if z > -700 else 0.0


def bell(xs: list[float], mean: float, sd: float) -> list[float]:
    ws = [math.exp(-0.5 * ((x - mean) / sd) ** 2) for x in xs]
    return [w / sum(ws) for w in ws]


class Level:
    """The belief over the market level: a grid over the world's level and today's deviation."""

    def __init__(self, weights: dict = WEIGHTS["win"]):
        self.w = weights
        self.world = bell(WORLD, 0.0, weights["world_sd"])
        self.war_left = 1.0  # the chance that the price war is still to come
        self.day: int | None = None
        self.joint: list[list[float]] = []
        self.start(0)

    def start(self, day: int) -> None:
        """A new day: the world's level stays as the answers left it, and today's deviation starts from its prior."""
        if day == self.day:
            return
        if self.day is not None:
            self.world = [sum(row) for row in self.joint]
            self.war_left *= 1 - sum(p for row in self.joint for x, p in zip(TODAY, row) if x < WAR_UNDER)
        self.day = day
        war = self.war_left / max(1, DAYS - day)
        usual, low = bell(TODAY, 0.0, self.w["day_sd"]), bell(TODAY, *self.w["war"])
        today = [(1 - war) * u + war * v for u, v in zip(usual, low)]
        self.joint = [[a * b for b in today] for a in self.world]

    def levels(self) -> list[float]:
        """The chance of each level in LEVELS."""
        chances = [0.0] * len(LEVELS)
        for i, row in enumerate(self.joint):
            for j, p in enumerate(row):
                chances[i + j] += p
        return chances

    def mean(self) -> float:
        return sum(x * p for x, p in zip(LEVELS, self.levels()))

    def answer(self, at_list: float, log_multiple: float, won: bool) -> None:
        """One answer: the log odds of the quote at the list price in the mean world, the log of its multiple, and
        whether the dealer bought."""
        likely = [sigmoid(at_list + self.w["slope"] * (level - log_multiple)) for level in LEVELS]
        if not won:
            likely = [1 - p for p in likely]
        joint = [[p * likely[i + j] for j, p in enumerate(row)] for i, row in enumerate(self.joint)]
        total = sum(map(sum, joint))
        if total > 0:
            self.joint = [[p / total for p in row] for row in joint]


def fastest(options: list[dict]) -> dict:
    return min(options, key=lambda o: SPEED.index(o["kind"]))


def flags(request: dict) -> dict[str, float]:
    car = request["legs"][0]["car"]
    return {"premium": float(car["premium"]), "electric": float(car["electric"]), "note": float(request["note"] is not None),
            "batch": float(request["batchId"] is not None)}


def at_list(request: dict, options: list[dict], on_time: int, late: int, km: float, weights: dict = WEIGHTS["win"]) -> float:
    """The log odds that the dealer buys when every quoted option is at its list price, at the mean world's level.
    `on_time` is the dealer's count of orders on time, and `late` the orders it has had late."""
    w, leg, first = weights, request["legs"][0], fastest(options)
    kinds = "+".join(sorted((o["kind"] for o in options), key=SPEED.index))
    lkm = math.log(max(km, 1.0)) - 5
    return (w["intercept"] + w["trust"] * math.log(1 + 0.01 * on_time) + w["lates"] * min(late, 4) + w["lkm"] * lkm + w["lkm2"] * lkm**2
            + w["feelist"] * math.log(request["referenceFeeCents"] / first["listPriceCents"]) + sum(w[k] * v for k, v in flags(request).items())
            + w["kinds"].get(kinds, 0.0) + w["from"].get(leg["pickup"]["placeId"], 0.0) + w["to"].get(leg["delivery"]["placeId"], 0.0)
            + w["hour"].get(str(request["arrivedAt"] % DAY // 120), 0.0))


def seen(request: dict, options: list[dict], drive: int, unbooked: int, unbooked_here: int, drivers: int) -> dict[str, float]:
    """What the desk sees at a quote about how the order will go, by the names of the weights `late` and `cost`. `drive`
    is the minutes on the road, `unbooked` the won cars without a driver, `unbooked_here` those at this pickup place,
    and `drivers` the length of the driver list."""
    leg, first, day, minute = request["legs"][0], fastest(options), request["arrivedAt"] // DAY % 7, request["arrivedAt"] % DAY
    return {"same_day": float(first["kind"] == "same_day"), "friday": float(day == 4), "monday": float(day == 0),
            "ready_later": float(leg["pickup"]["window"]["from"] - request["respondBy"] > 3 * HOUR), "long": float(drive > 240),
            "short": float(drive < 30), "afternoon": float(minute >= 900), "unbooked": min(unbooked, 25) / 10,
            "unbooked_here": min(unbooked_here, 8) / 4, "drivers": (min(max(drivers, DRIVERS[0]), DRIVERS[1]) - 780) / 100, **flags(request)}


def score(weights: dict, request: dict, options: list[dict], drive: int, seen_: dict[str, float]) -> float:
    leg, hours = request["legs"][0], (fastest(options)["deadline"] - drive - request["respondBy"]) / HOUR
    band = next((f"<{under}" for under in SLACK if hours < under), "rest")
    return (weights["intercept"] + sum(weights[k] * v for k, v in seen_.items()) + weights["slack"].get(band, 0.0)
            + weights["from"].get(leg["pickup"]["placeId"], 0.0) + weights["to"].get(leg["delivery"]["placeId"], 0.0))


def late(request: dict, options: list[dict], drive: int, seen_: dict[str, float]) -> float:
    """The chance that the order arrives late, if the dealer takes the fastest option quoted."""
    return sigmoid(score(WEIGHTS["late"], request, options, drive, seen_))


def cost(request: dict, options: list[dict], drive: int, seen_: dict[str, float]) -> float:
    """What the order costs without refunds, as a multiple of its typical fee: fees, fines, waiting and failed visits."""
    return score(WEIGHTS["cost"], request, options, drive, seen_)


def best(at_list_: float, levels: list[float], list_cents: int, cost_cents: float, late_: float, bonus_cents: float = 0.0) -> tuple[float, float]:
    """The multiple of the list price with the highest expected value over the belief `levels`, and that value in cents.
    A late order gives back the refund's share of its price; `bonus_cents` is what the order is worth beyond its money."""
    slope, kept = WEIGHTS["win"]["slope"], 1 - WEIGHTS["refund"] * late_
    live = [(level, p) for level, p in zip(LEVELS, levels) if p > 1e-6]

    def value(multiple: float) -> float:
        log_multiple = math.log(multiple)
        chance = sum(p * sigmoid(at_list_ + slope * (level - log_multiple)) for level, p in live)
        return chance * (multiple * list_cents * kept - cost_cents + bonus_cents)

    multiple = max(MULTIPLES, key=value)
    return multiple, value(multiple)


class Quotes:
    """The desk's side: the belief, and the quotes that have no answer yet."""

    def __init__(self, map_: dict, roster: list[dict]):
        self.km = {(road["from"], road["to"]): road["km"] for road in map_["roads"]}
        self.drivers = len(roster)
        self.level = Level()
        self.asked: dict[str, tuple[int, float, float]] = {}  # request id -> the day, the log odds at the list price and the log of the multiple

    def quote(self, desk, request: dict, options: list[dict], p: dict) -> tuple[float, float]:
        """The multiple of the list price for the options, and the log odds that the dealer buys at it."""
        leg, first, dealer, day = request["legs"][0], fastest(options), request["dealerId"], request["arrivedAt"] // DAY
        place, drive = leg["pickup"]["placeId"], desk.drive(request)
        lates = sum(1 for id_ in desk.late if id_ in desk.requests and desk.requests[id_]["dealerId"] == dealer)
        here = sum(1 for id_, order in desk.orders.items() for n, at in enumerate(order["deliveredAt"])
                   if at is None and desk.leg_gigs.get(id_, {}).get(n) not in desk.booked and order["legs"][n]["pickup"]["placeId"] == place)
        seen_ = seen(request, options, drive, desk.unbooked(), here, self.drivers)
        late_ = late(request, options, drive, seen_)
        multiple_of_fee = cost(request, options, drive, seen_) + OPENING * (desk.opening(request, p) - 1) + p["opt_mu"]
        at_list_ = at_list(request, options, desk.trust.get(dealer, 0), lates, self.km[(place, leg["delivery"]["placeId"])])
        self.level.start(day)
        multiple, value = best(at_list_, self.level.levels(), first["listPriceCents"], desk.usual_fee(request, p) * multiple_of_fee,
                               late_, 100 * p["opt_lambda"] * (0.1 - late_))
        if value <= 0:
            multiple = DECLINE
        self.asked[request["id"]] = (day, at_list_, math.log(multiple))
        return multiple, at_list_ + WEIGHTS["win"]["slope"] * (self.level.mean() - math.log(multiple))

    def answer(self, request_id: str, won: bool, counts: bool = True) -> None:
        """The dealer's answer to a request. It counts only when it answers the price that the desk chose: the live desk
        knows when the world never took that quote, because it came late or the desk was down."""
        asked = self.asked.pop(request_id, None)
        if counts and asked is not None and asked[2] < math.log(DECLINE):
            day, at_list_, log_multiple = asked
            self.level.start(max(day, self.level.day or 0))
            self.level.answer(at_list_, log_multiple, won)
