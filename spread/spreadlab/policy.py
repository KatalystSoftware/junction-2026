"""The policy: what the desk quotes and what it pays drivers. It extends the kit's starter desk, which
keeps the books and handles failed visits, changed orders and expired gigs, so the same class can
later play the final from the live stream.

A policy sees only what the live system sees at that minute: the request, the driver list, the map
and its own history in the week. It never sees a seed or the reveal. Its parameters are in DEFAULTS;
a variant (variants.py) changes some of them.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import math
import sys
from typing import Optional

from spread.starter import DAY, Desk, rising, steep

from . import curve
from .server import drivers_near, near_places

DEFAULTS = {
    "price": 1.5,         # the quote, as a multiple of the option's list price
    "floor": 0,           # the lowest quote, as a multiple of the request's typical fee; 0 is no floor
    "quote_share": 0.6,   # the share of acceptable requests that get a serious quote, to limit the cars won
    "same_day": False,    # offer the same_day option
    "trade_in": False,    # quote requests with two cars
    "private": False,     # quote requests with a private address
    "min_slack": 300,     # offer an option only with this many minutes between the first possible pickup and the last one that is on time
    "min_notified": 0,    # decline when fewer drivers than this are notified of the pickup
    "max_unbooked": 0,    # decline while this many won cars have no driver; 0 is no limit
    "fee": 1.2,           # the opening fee, as a multiple of the request's typical fee
    # What the floor follows. Each is off at its default.
    "dealer_steps": [],   # [[share, floor], ...]: the floor at a dealer once the desk has won this share of its quotes there in the week
    "day_floor": {},      # {"0": floor}: the floor on a day of the week (0 is Monday), whatever the dealer
    "backlog_step": 0,    # the floor rises by this much for each won car without a driver ...
    "backlog_from": 0,    # ... beyond this many
    "trust": 0,           # the quote rises by this share for each order the dealer has had on time, up to 25 (RULES.md, Dealer trust)
    "explore": [],        # [low, high]: quote a random multiple of the list price in this range, to learn what dealers accept
    # The win curve (curve.py) replaces `price`: the quote with the highest (price - cost) x chance that the dealer buys.
    "curve": False,
    "cost": 1.4,          # what an order costs, as a multiple of its typical fee: fees, failed visits and refunds
    "learn": 0,           # how far a day's prices usually are from the curve, in log price; 0 does not correct the curve by the day's answers
    # Two rules change the parameters above. Each names the parameters it replaces while it applies.
    "tight_drivers": 0,   # the week is tight when the driver list is shorter than this; 0 is never
    "when_tight": {},     # the parameters of a tight week, known before the first quote
    "min_on_time": 0,     # the desk is behind while its projected on-time share is under this; 0 is never
    "when_behind": {},    # the parameters while it is behind; they come after those of a tight week
}
RULES = {"tight_drivers", "when_tight", "min_on_time", "when_behind"}
DECLINE = 10  # times the list price: a quote that loses costs nothing, and no quote costs goodwill (RULES.md)
# The chance that an order which is not late yet arrives late, by what the desk sees of it at a quote.
# Measured on the 10 tuning weeks of `gate-10` and of `gate-15`: 3% late while drivers hold all its cars,
# 12 to 15% while a car waits for a driver, and 34 to 39% once it has waited two hours.
LATE_HELD, LATE_WAITING, LATE_WAITING_LONG = 0.03, 0.15, 0.40
LONG_WAIT = 120  # minutes
MIN_ANSWERS = 5  # a dealer's win share counts once it has answered this many quotes
MAX_TRUST = 25  # a dealer counts at most this many orders on time (RULES.md)


class Policy(Desk):
    def __init__(self, world, level: int, now: int, params: dict, roster: list[dict], map_: dict):
        super().__init__(world, level, now)
        unknown = set(params) - set(DEFAULTS)
        if unknown:
            raise ValueError(f"Unknown parameters {sorted(unknown)}. The parameters are {sorted(DEFAULTS)}")
        for rule in ("when_tight", "when_behind"):
            wrong = set(params.get(rule, {})) - (set(DEFAULTS) - RULES)
            if wrong:
                raise ValueError(f"{rule} cannot set {sorted(wrong)}. It sets some of {sorted(set(DEFAULTS) - RULES)}")
        self.p = {**DEFAULTS, **params}
        self.tight = len(roster) < self.p["tight_drivers"]
        if self.tight:
            self.p = {**self.p, **self.p["when_tight"]}
        self.won_at: dict[str, int] = {}  # order id -> the minute the desk learned of the win
        self.late: set[str] = set()  # the orders that the account has refunded or fined for lateness
        self.asked: dict[str, tuple[str, int, float]] = {}  # request id -> dealer, day and the curve's log odds, for each serious quote without an answer
        self.today: tuple[int, list[tuple[float, bool]]] = (0, [])  # the day, and the answers to its quotes: the curve's log odds and whether the dealer bought
        self.answers: dict[str, list[int]] = {}  # dealer -> [serious quotes answered, of which won]
        self.trust: dict[str, int] = {}  # dealer -> the orders it counts as on time, as the dealer counts them
        self.minutes = {(road["from"], road["to"]): road["minutes"] for road in map_["roads"]}
        self.notified = drivers_near(roster, near_places(map_))
        self.decisions: dict[str, dict] = {}  # request id -> what the policy answered, and why it declined
        self.refused: list[dict] = []  # the actions that the world refused

    def params(self) -> dict:
        """The parameters at this minute: those of the week, or those of a desk that is behind."""
        if self.p["min_on_time"] and self.on_time() < self.p["min_on_time"]:
            return {**self.p, **self.p["when_behind"]}
        return self.p

    def on_time(self) -> float:
        """The projected share of the won orders that arrive on time: 1 for each that did, 0 for each
        that is late, and for the others the chance by whether a driver holds every car of the order."""
        if not self.orders:
            return 1.0
        late = 0.0
        for id_, order in self.orders.items():
            delivered = order["deliveredAt"]
            # A car that is still out counts as late once the deadline has passed.
            if id_ in self.late or any((self.now if at is None else at) > order["deadline"] for at in delivered):
                late += 1
            elif any(at is None for at in delivered):
                held = all(at is not None or self.leg_gigs.get(id_, {}).get(leg) in self.booked for leg, at in enumerate(delivered))
                waited = self.now - self.won_at.get(id_, self.now)
                late += LATE_HELD if held else LATE_WAITING_LONG if waited >= LONG_WAIT else LATE_WAITING
        return 1 - late / len(self.orders)

    def quote(self, request) -> None:
        self.requests[request["id"]] = request
        p = self.params()
        reason, options = self.choose(request, p)
        if reason:
            first = request["options"][0]
            prices = {first["kind"]: first["listPriceCents"] * DECLINE}
        else:
            fee, day, on_time = request["referenceFeeCents"], request["arrivedAt"] // DAY, self.trust.get(request["dealerId"], 0)
            surcharge = p["backlog_step"] * max(0, self.unbooked() - p["backlog_from"])
            log_odds = 0.0
            if p["curve"]:
                at_list, first = curve.at_list(request, options, on_time), curve.fastest(options)
                multiple = curve.best(at_list, self.shift(day, p), first["listPriceCents"], fee * (p["cost"] + surcharge))
                log_odds = at_list - curve.SLOPE * math.log(multiple)
                prices = {o["kind"]: int(round(max(o["listPriceCents"] * multiple, fee * self.floor(request, p)))) for o in options}
            else:
                multiple = self.draw(request, *p["explore"]) if p["explore"] else p["price"]
                floor = fee * (self.floor(request, p) + surcharge)
                prices = {o["kind"]: int(round(max(o["listPriceCents"] * multiple, floor) * (1 + p["trust"] * on_time))) for o in options}
            self.asked[request["id"]] = (request["dealerId"], day, log_odds)
        self.decisions[request["id"]] = {"declined": reason, "prices": prices}
        if p["explore"]:  # what the desk knew at the quote, for the fit of the win curve
            self.decisions[request["id"]]["seen"] = {"trust": self.trust.get(request["dealerId"], 0), "unbooked": self.unbooked(),
                                                     "answers": list(self.answers.get(request["dealerId"], [0, 0]))}
        if p["min_on_time"]:
            self.decisions[request["id"]]["onTime"] = round(self.on_time(), 4)
        self.outbox.append({"type": "quote", "requestId": request["id"], "prices": prices})

    def floor(self, request, p: dict) -> float:
        """The lowest quote for the request, as a multiple of its typical fee."""
        floor, day = p["floor"], str(request["arrivedAt"] // DAY % 7)
        answered, won = self.answers.get(request["dealerId"], (0, 0))
        if day in p["day_floor"]:
            floor = p["day_floor"][day]
        elif answered >= MIN_ANSWERS:
            floor = max([step for least, step in p["dealer_steps"] if won / answered >= least], default=floor)
        return floor

    def shift(self, day: int, p: dict) -> float:
        """How far today's dealers are from the curve, from their answers so far today."""
        answers = self.today[1] if self.today[0] == day else []
        return curve.shift(answers, p["learn"]) if p["learn"] and answers else 0.0

    @staticmethod
    def draw(request, low: float, high: float) -> float:
        """A multiple from low to high that is fixed for the request, and differs between weeks for the same request id."""
        return low + (high - low) * share(f"{request['id']} {request['arrivedAt']} {request['referenceFeeCents']}")

    def choose(self, request, p: dict) -> tuple[Optional[str], list[dict]]:
        """The options to quote under the parameters `p`, or the reason to decline the request."""
        legs = request["legs"]
        if len(legs) > 1 and not p["trade_in"]:
            return "trade_in", []
        if not p["private"] and any(leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"] for leg in legs):
            return "private", []
        if min(self.notified[leg["pickup"]["placeId"]] for leg in legs) < p["min_notified"]:
            return "few_drivers", []
        options = [o for o in request["options"] if p["same_day"] or o["kind"] != "same_day"]
        if not options:
            return "same_day_only", []
        drive = sum(self.minutes[(leg["pickup"]["placeId"], leg["delivery"]["placeId"])] for leg in legs)
        ready = max(request["respondBy"], max(leg["pickup"]["window"]["from"] for leg in legs))
        options = [o for o in options if o["deadline"] - drive - ready >= p["min_slack"]]
        if not options:
            return "slack", []
        if p["max_unbooked"] and self.unbooked() >= p["max_unbooked"]:
            return "backlog", []
        if share(request["id"]) >= p["quote_share"]:
            return "volume", []
        return None, options

    def unbooked(self) -> int:
        """The won cars that no driver holds now: just won, dropped, or posted again after a failed visit."""
        return sum(1 for id_, order in self.orders.items() for leg, at in enumerate(order["deliveredAt"])
                   if at is None and self.leg_gigs.get(id_, {}).get(leg) not in self.booked)

    def fees_for(self, order, cars):
        fee = self.requests[order["id"]]["referenceFeeCents"] * cars / len(order["legs"]) * self.params()["fee"]
        return steep(self.now, fee, self.level) if order["id"] in self.urgent else rising(self.now, fee, self.level)

    def win(self, order) -> None:
        self.won_at.setdefault(order["id"], self.now)
        super().win(order)

    def handle(self, event) -> None:
        if event["kind"] == "ledger" and event["line"]["kind"] in ("late_refund", "undelivered_penalty") and event["line"]["orderId"]:
            self.late.add(event["line"]["orderId"])
        elif event["kind"] in ("order_won", "order_lost"):
            asked = self.asked.pop(event["order"]["id"] if event["kind"] == "order_won" else event["requestId"], None)
            if asked is not None:
                dealer, day, log_odds = asked
                answers = self.answers.setdefault(dealer, [0, 0])
                answers[0] += 1
                answers[1] += event["kind"] == "order_won"
                if self.today[0] != day:
                    self.today = (day, [])
                self.today[1].append((log_odds, event["kind"] == "order_won"))
        super().handle(event)

    def delivered(self, order_id: str, leg: int, at: int) -> None:
        super().delivered(order_id, leg, at)
        order = self.orders.get(order_id)
        if order is not None and all(at is not None for at in order["deliveredAt"]):
            dealer = self.requests[order_id]["dealerId"]
            count = self.trust.get(dealer, 0)
            on_time = all(at <= order["deadline"] for at in order["deliveredAt"])
            self.trust[dealer] = min(MAX_TRUST, count + 1) if on_time else count // 2

    def read_results(self, actions, results) -> None:
        super().read_results(actions, results)
        for action, result in zip(actions, results):
            if not result["ok"]:
                self.refused.append({"at": self.now, "action": action, "reason": result["reason"]})


def share(request_id: str) -> float:
    """A number from 0 to 1 that is fixed for a request id, so a variant makes the same choice on every run."""
    return int.from_bytes(hashlib.sha256(request_id.encode()).digest()[:8], "big") / 2**64


def fingerprint(params: dict) -> str:
    """Changes when the parameters or this file change. A sweep plays a week again when its saved run has another fingerprint."""
    source = inspect.getsource(sys.modules[__name__])
    if params.get("curve"):  # the curve's code and weights count only for the variants that price by it
        source += inspect.getsource(curve) + json.dumps(curve.MODEL, sort_keys=True)
    return hashlib.sha256((source + json.dumps({**DEFAULTS, **params}, sort_keys=True)).encode()).hexdigest()[:12]
