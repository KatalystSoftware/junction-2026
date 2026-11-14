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
from pathlib import Path
from typing import Optional

from spread.starter import DAY, HOUR, WAKE_ON, Desk, Retry, pickups, rising, steep, stops_for, without_windows

from . import curve, notes, optquote, slow
from .server import drivers_near, near_places

DEFAULTS = {
    "price": 1.5,         # the quote, as a multiple of the option's list price
    "floor": 0,           # the lowest quote, as a multiple of the request's typical fee; 0 is no floor
    "quote_share": 0.6,   # the share of acceptable requests that get a serious quote, to limit the cars won
    "same_day": False,    # offer the same_day option
    "same_day_extra": 0,  # quote same_day this share over the policy's price when the request has a slower option too: it leaves the least time for a driver
    "trade_in": False,    # quote requests with two cars
    "private": False,     # quote requests with a private address
    "min_slack": 300,     # offer an option only with this many minutes between the first possible pickup and the last one that is on time
    "min_notified": 0,    # decline when fewer drivers than this are notified of the pickup
    "max_unbooked": 0,    # decline while this many won cars have no driver; 0 is no limit
    "fee": 1.2,           # the opening fee, as a multiple of the request's typical fee
    # The fees after the opening. The starter's schedule rises 10% of the opening fee an hour, to 1.5 times. Each is off at its default.
    "fee_cap": 0,         # the fee rises a tenth of the typical fee an hour up to this multiple of it, then holds
    "drop_fee": 0,        # after a driver drops a gig, its fees start again at this multiple of the opening fee; the old schedule is at its top by then
    "jump": 0,            # one step to this multiple of the typical fee, when drivers plan the day of the order's last pickup and the gig is still open
    "lane_fee": False,    # the fees and the cost follow the lane's usual fee (lanes.json) in place of the request's typical fee
    # The orders that open at another fee. Each is off at its default.
    "deep_drivers": 0,    # where at least this many drivers are notified of the pickup ...
    "deep_fee": 0,        # ... the gig opens at this multiple of the typical fee: many drivers see it, so a lower fee still books
    "long_drive": 0,      # an order that drives longer than this many minutes ...
    "long_fee": 0,        # ... opens at this multiple of the typical fee: few drivers can do it in the time, and it is often late
    "long_cost": 0,       # ... and is taken to cost this multiple of it at the quote
    "max_drive": 0,       # decline a request that drives longer than this many minutes; 0 is no limit
    # Direct offers. A driver who reads one takes it when the fee pays, and does not wait for a rise (RULES.md, Direct offers).
    "offer_hours": 0,     # an open gig gets direct offers once its order must be collected within this many hours; 0 sends none
    "offer_fee": 1.3,     # ... at this multiple of the typical fee, or at the fee in the app when that is higher
    # Direct offers to the drivers who live where the car is going: such a driver needs much less than the typical fee (RULES.md). Off at 0.
    "home_offers": 0,     # at the posting of a one-car gig, and when it is open again after a drop: this many offers at once, at most 3
    "home_fee": 1.0,      # ... at this multiple of the typical fee
    "home_km": 0,         # ... to the drivers who live in the delivery town; above 0, also those within the notification distance of it
    "home_rounds": 1,     # ... and when they end unanswered and the gig is still open, the next drivers, this many rounds in all
    "private_cost": 0,    # a request with a private address is taken to cost this multiple of its typical fee; 0 is `cost`
    # With `read_notes`: the note's own deadline and the site hours it gives (notes.limits) count at the quote and in the posting. A desk
    # that rejoins a world takes its orders from the world again, without the note's deadline in its books; the postings keep it.
    "note_limits": False,
    "read_notes": False,  # read the note before the first posting (notes.py): the first minute to collect the car, plates, a manual licence
    # What the floor follows. Each is off at its default.
    "dealer_steps": [],   # [[share, floor], ...]: the floor at a dealer once the desk has won this share of its quotes there in the week
    "day_floor": {},      # {"0": floor}: the floor on a day of the week (0 is Monday), whatever the dealer
    "backlog_step": 0,    # the floor rises by this much for each won car without a driver ...
    "backlog_from": 0,    # ... beyond this many
    "trust": 0,           # the quote rises by this share for each order the dealer has had on time, up to 25 (RULES.md, Dealer trust)
    "explore": [],        # [low, high]: quote a random multiple of the list price in this range, to learn what dealers accept
    # The same for the two kinds of request that no curve has answers for. The other requests stay on the policy.
    "explore_private": [],   # [low, high] for one-car requests with a private address, never under 1.3 x the typical fee
    "explore_trade_in": [],  # [low, high] for requests with two cars
    # The kinds of request that are not one car between two dealer sites: "private_pickup", "private_delivery" and "trade_in".
    # A kind that is named here is quoted, with what differs for it: {"cost": .., "fee": .., "odds": ..} are the cost in
    # the quote and the opening fee, as multiples of the typical fee, and what the curve's log odds are off by for the kind.
    "kinds": {},
    # The win curve (curve.py) replaces `price`: the quote with the highest (price - cost) x chance that the dealer buys.
    "curve": False,
    "model": "",          # the curve's weights (curve.MODELS): "" is the fit over all days, "day" the fit with a level for each day
    "cost": 1.4,          # what an order costs, as a multiple of its typical fee: fees, failed visits and refunds
    "learn": 0,           # how far a day's prices usually are from the curve, in log price; 0 does not correct the curve by the day's answers
    "learn_pickup": 0,    # the same for the pickup town, on top of the day's correction and new each morning: an outage raises the prices of one region
    "cost_hours": [],     # [[hours, cost], ...] in rising hours: the cost of an order with fewer than this many hours from the answer to the last pickup minute of the fastest option quoted; `cost` for the others
    "premium_cost": 0,    # added to the cost of a premium car: only experienced drivers may take it
    "backlog_hours": 0,   # the backlog surcharge counts only the won cars without a driver that must be collected within this many hours; 0 counts all
    # Cars that are slow to find a driver fill the backlog, and a full backlog stops the desk from quoting. Each is off at its default.
    "slow_bar": [],       # [[cars, chance], ...] in rising cars: once this many won cars have no driver, decline a request whose chance of arriving late (slow.py) is above this
    "slow_model": "",     # the weights of the chance of arriving late (slow.MODELS): "friday" has terms for an order that must be collected on a Friday
    "slow_step": 0,       # the cost rises by this much x the request's chance of arriving late, for each won car without a driver
    "late_cost": 0,       # the cost rises by the request's chance of arriving late (slow.py) x this many euros: the refund and the dealer's trust
    "rule_cost": 0,       # ... and by (that chance - 0.10) x this many euros, the price of the 90% rule: an order safer than the rule gets cheaper. The cost is then never under the typical fee
    # Snow. A `forecast` event names places and hours a day ahead; there drives are slower and some drivers stay at home. Each is off at its default.
    "snow_odds": 0,       # added to the log odds of the late chance when snow is forecast at a pickup or delivery place between the first pickup minute and the fastest option's deadline
    "snow_fee": 0,        # the fees of a gig whose order has snow forecast at one of its places before its deadline are this multiple of the usual schedule
    "backlog_later": 0,   # the surcharge for each won car without a driver that is not due within `backlog_hours`; `backlog_step` is then for those that are
    "full_from": 0,       # the backlog is filling once this many won cars have no driver; 0 is never
    "when_full": {},      # the parameters while it is filling; they come after those of a desk that is behind
    "push_from": 0,       # once this many won cars have no driver, the open gigs that are short of time show a higher fee at once; 0 is never
    "push_hours": 24,     # ... those whose order must be collected within this many hours
    "push_fee": 1.4,      # ... at least this multiple of the typical fee
    # [[drivers from, drivers under, hours from, hours under, opening fee, rise an hour, top fee], ...]: the fees of a gig by the drivers
    # notified of its pickup and the hours left to collect the car when it is posted, as multiples of the typical fee. The first rule that fits applies.
    "fee_rules": [],
    "slope_by": 1,        # multiplies the curve's slope where the price is chosen: above 1 takes dealers to be more sensitive to the price
    "cost_by_order": False,  # the cost follows the order (curve.cost: long lanes, few drivers, a note) and replaces `cost`
    "trust_value": 0,     # the share to count of what an order on time, or a late one, is worth in the dealer's later prices; 0 counts none
    # The quote as an optimisation (optquote.py) replaces `price` and the curve's price: the highest expected value of the order.
    "opt": False,
    "opt_mu": 0,          # the price of a driver's time, in typical fees for each order won, on top of the order's own cost; the backlog surcharge adds to it
    "opt_lambda": 0,      # the price of the 90% rule, in euros: an order pays it by its chance to arrive late, and one that is surely on time earns a tenth of it
    # Two rules change the parameters above. Each names the parameters it replaces while it applies.
    "tight_drivers": 0,   # the week is tight when the driver list is shorter than this; 0 is never
    "when_tight": {},     # the parameters of a tight week, known before the first quote
    "min_on_time": 0,     # the desk is behind while its projected on-time share is under this; 0 is never
    "behind_from": 0,     # ... and it has won at least this many orders: with few orders, one late order moves the share far
    "when_behind": {},    # the parameters while it is behind; they come after those of a tight week
}
RULES = {"tight_drivers", "when_tight", "min_on_time", "behind_from", "when_behind"}
DECLINE = 10  # times the list price: a quote that loses costs nothing, and no quote costs goodwill (RULES.md)
# The chance that an order which is not late yet arrives late, by what the desk sees of it at a quote.
# Measured on the 10 tuning weeks of `gate-10` and of `gate-15`: 3% late while drivers hold all its cars,
# 12 to 15% while a car waits for a driver, and 34 to 39% once it has waited two hours.
LATE_HELD, LATE_WAITING, LATE_WAITING_LONG = 0.03, 0.15, 0.40
LONG_WAIT = 120  # minutes
EXPLORE_FLOOR = 1.3  # a random price for a kind of request is never under this multiple of the typical fee
MIN_ANSWERS = 5  # a dealer's win share counts once it has answered this many quotes
MAX_TRUST = 25  # a dealer counts at most this many orders on time (RULES.md)
# Drivers book open gigs mostly when they plan: early in the morning for the day, and in the late afternoon for the next.
PLAN_MORNING, PLAN_EVENING, PLANS_SAME_DAY = 4 * 60 + 30, 16 * 60, 10 * 60  # a last pickup after 10:00 is planned that morning
OFFER_AFTER, OFFER_LASTS, OFFERS_A_GIG, OFFERS_A_DRIVER = 30, 10, 3, 3  # minutes a gig is open before its first offer; RULES.md: 10 minutes, 3 open a gig, 3 a driver a day
OFFERS_FROM, OFFERS_TO, LOOK_EVERY = 7 * 60, 23 * 60, 15  # no driver reads an offer from 23:00 to 07:00; the desk looks at its open gigs every 15 minutes
EXPERIENCED = (4.8, 50)  # the rating and the completed gigs of an experienced driver (RULES.md, Gigs)
NEVER = 10**9
# lane -> the mean of the log of its requests' typical fee, in cents (scratch/lane_fit.py). A request's typical fee is
# its lane's usual fee times noise that the drivers do not share.
LANES = json.loads(Path(__file__).with_name("lanes.json").read_text(encoding="utf-8"))
OPENS, OPEN = 8 * 60, 10 * 60  # requests arrive from 08:00 for about ten hours, Monday to Friday


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
        self.model = curve.MODELS[self.p["model"]]
        self.tight = len(roster) < self.p["tight_drivers"]
        if self.tight:
            self.p = {**self.p, **self.p["when_tight"]}
        self.won_at: dict[str, int] = {}  # order id -> the minute the desk learned of the win
        self.late: set[str] = set()  # the orders that the account has refunded or fined for lateness
        self.asked: dict[str, tuple[str, int, float]] = {}  # request id -> dealer, day and the curve's log odds, for each serious quote without an answer
        self.today: tuple[int, list[tuple[float, bool]]] = (0, [])  # the day, and the answers to its quotes: the curve's log odds and whether the dealer bought
        self.today_at: dict[str, list[tuple[float, bool]]] = {}  # pickup place -> today's answers to the quotes for cars from there
        self.asked_at: dict[str, str] = {}  # request id -> the pickup place, for each serious quote without an answer
        self.answers: dict[str, list[int]] = {}  # dealer -> [serious quotes answered, of which won]
        self.requested: dict[str, int] = {}  # dealer -> its requests so far
        self.trust: dict[str, int] = {}  # dealer -> the orders it counts as on time, as the dealer counts them
        self.minutes = {(road["from"], road["to"]): road["minutes"] for road in map_["roads"]}
        self.near = near_places(map_)  # place -> the places within the notification distance of it
        self.notified = drivers_near(roster, self.near)
        self.home: dict[str, int] = {}  # gig id -> the rounds of offers it may still get to drivers who live where the car is going
        self.wake_on = WAKE_ON + (["gig_dropped"] if self.p["drop_fee"] else [])  # the events that the desk answers at once
        self.roster = roster
        self.seen: dict[str, int] = {}  # driver -> the last day the driver looked at a gig of the desk or booked one: that day the driver uses the app
        self.gave_back: dict[str, set[str]] = {}  # gig id -> the drivers who dropped it
        self.opened: dict[str, int] = {}  # gig id -> the minute the world accepted its post
        self.fees: dict[str, list[dict]] = {}  # gig id -> its fee schedule now
        self.pushed: set[str] = set()  # the gigs whose fee the desk raised because the backlog was filling
        self.offers: dict[str, dict[str, int]] = {}  # gig id -> driver -> the minute the desk's offer to the driver ends
        self.offered: tuple[int, dict[str, int]] = (0, {})  # the day, and driver -> the offers the desk sent the driver that day
        self.decisions: dict[str, dict] = {}  # request id -> what the policy answered, and why it declined
        self.refused: list[dict] = []  # the actions that the world refused
        self.opt = optquote.Quotes(map_, roster) if self.p["opt"] else None
        self.forecasts: list[dict] = []  # the snow forecasts so far: places, and the minutes from and to

    def params(self) -> dict:
        """The parameters at this minute: those of the week, of a desk that is behind, or of one whose backlog is filling."""
        p = self.p
        if p["min_on_time"] and len(self.orders) >= p["behind_from"] and self.on_time() < p["min_on_time"]:
            p = {**p, **p["when_behind"]}
        if p["full_from"] and self.unbooked() >= p["full_from"]:
            p = {**p, **p["when_full"]}
        return p

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
        self.requested[request["dealerId"]] = self.requested.get(request["dealerId"], 0) + 1
        p = self.params()
        reason, options = self.choose(request, p)
        explored = self.explored(request, p)
        if reason:
            first = request["options"][0]
            prices = {first["kind"]: first["listPriceCents"] * DECLINE}
        elif explored:  # a random price; its answer says nothing about the day's level, so it is not counted there
            multiple = self.draw(request, *p["explore_" + explored])
            prices = {o["kind"]: int(round(max(o["listPriceCents"] * multiple, request["referenceFeeCents"] * EXPLORE_FLOOR))) for o in options}
        else:
            fee, day, on_time = request["referenceFeeCents"], request["arrivedAt"] // DAY, self.trust.get(request["dealerId"], 0)
            surcharge = p["backlog_step"] * max(0, self.unbooked(p["backlog_hours"]) - p["backlog_from"])
            if p["slow_step"]:
                surcharge += p["slow_step"] * self.unbooked() * self.slow(request, options)
            if p["backlog_later"]:
                surcharge += p["backlog_later"] * (self.unbooked() - self.unbooked(p["backlog_hours"]))
            log_odds = 0.0
            if p["opt"]:
                multiple, log_odds = self.opt.quote(self, request, options, {**p, "opt_mu": p["opt_mu"] + surcharge})
                prices = {o["kind"]: int(round(max(o["listPriceCents"] * multiple, fee * self.floor(request, p)))) for o in options}
            elif p["curve"]:
                own = p["kinds"].get(kind(request), {})
                at_list, first, slope = curve.at_list(request, options, on_time, self.model) + own.get("odds", 0), curve.fastest(options), self.model["slope"] * p["slope_by"]
                known = curve.known(request, options, min(self.notified[leg["pickup"]["placeId"]] for leg in request["legs"]), self.unbooked())
                private = any(leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"] for leg in request["legs"])
                flat = own["cost"] if own.get("cost") else p["long_cost"] if p["long_cost"] and self.long(request, p) else p["private_cost"] if p["private_cost"] and private else p["cost"]
                if flat == p["cost"]:  # the hours the desk has to find a driver, if the dealer takes the fastest option
                    hours = (first["deadline"] - self.drive(request) - request["respondBy"]) / HOUR
                    flat = next((cost_ for under, cost_ in p["cost_hours"] if hours < under), flat)
                flat += p["premium_cost"] * any(leg["car"]["premium"] for leg in request["legs"])
                cost, shift = self.usual_fee(request, p) * ((curve.cost(known) if p["cost_by_order"] else flat) + surcharge), self.shift(day, p, request["legs"][0]["pickup"]["placeId"])
                if p["late_cost"] or p["rule_cost"]:
                    late = self.slow(request, options)
                    cost = max(cost + 100 * (p["late_cost"] * late + p["rule_cost"] * (late - 0.10)), self.usual_fee(request, p))
                multiple = curve.best(at_list, shift, first["listPriceCents"], cost, slope)
                if p["trust_value"]:  # an order on time raises what the dealer accepts later, and a late one lowers it
                    revenue = multiple * first["listPriceCents"] * curve.chance(at_list, multiple, shift, slope)
                    cost -= p["trust_value"] * self.trust_worth(request, on_time, curve.late(known), revenue)
                    multiple = curve.best(at_list, shift, first["listPriceCents"], cost, slope)
                log_odds = at_list - slope * math.log(multiple)
                prices = {o["kind"]: int(round(max(o["listPriceCents"] * multiple, fee * self.floor(request, p)))) for o in options}
            else:
                multiple = self.draw(request, *p["explore"]) if p["explore"] else p["price"]
                floor = fee * (self.floor(request, p) + surcharge)
                prices = {o["kind"]: int(round(max(o["listPriceCents"] * multiple, floor) * (1 + p["trust"] * on_time))) for o in options}
            self.asked[request["id"]] = (request["dealerId"], day, log_odds)
            self.asked_at[request["id"]] = request["legs"][0]["pickup"]["placeId"]
        if p["same_day_extra"] and not reason and not explored and len(prices) > 1 and "same_day" in prices:
            prices["same_day"] = int(round(prices["same_day"] * (1 + p["same_day_extra"])))
        self.decisions[request["id"]] = {"declined": reason, "prices": prices}
        if explored:
            self.decisions[request["id"]]["explored"] = explored
        if p["explore"] or explored:  # what the desk knew at the quote, for the fit of the win curve
            self.decisions[request["id"]]["seen"] = {"trust": self.trust.get(request["dealerId"], 0), "unbooked": self.unbooked(),
                                                     "answers": list(self.answers.get(request["dealerId"], [0, 0])),
                                                     "shift": round(self.shift(request["arrivedAt"] // DAY, p, request["legs"][0]["pickup"]["placeId"]), 4)}
        if p["min_on_time"]:
            self.decisions[request["id"]]["onTime"] = round(self.on_time(), 4)
        self.outbox.append({"type": "quote", "requestId": request["id"], "prices": prices})

    @staticmethod
    def explored(request, p: dict) -> str:
        """The kind of a request that gets a random price: "private", "trade_in", or "" for the others."""
        own = kind(request)
        return "trade_in" if own == "trade_in" and p["explore_trade_in"] else "private" if own.startswith("private") and p["explore_private"] else ""

    def floor(self, request, p: dict) -> float:
        """The lowest quote for the request, as a multiple of its typical fee."""
        floor, day = p["floor"], str(request["arrivedAt"] // DAY % 7)
        answered, won = self.answers.get(request["dealerId"], (0, 0))
        if day in p["day_floor"]:
            floor = p["day_floor"][day]
        elif answered >= MIN_ANSWERS:
            floor = max([step for least, step in p["dealer_steps"] if won / answered >= least], default=floor)
        return floor

    def trust_worth(self, request, on_time: int, late: float, revenue: float) -> float:
        """What winning this order is worth in the dealer's later prices, in cents. Each order on time raises the prices
        the dealer accepts by 1%, up to 25, and a late one halves the count. One count is worth 1% of the revenue that
        the desk expects from the dealer in the rest of the week: its requests so far, continued at the same rate, each
        at the expected revenue of this one."""
        minute = request["arrivedAt"]
        elapsed = minute // DAY * OPEN + min(max(minute % DAY - OPENS, 0), OPEN)
        later = self.requested[request["dealerId"]] * max(0, 5 * OPEN - elapsed) / (elapsed + 60)  # an hour is added, so that the first requests do not promise a week of them
        counts = (1 - late) * (on_time < MAX_TRUST) - late * (on_time - on_time // 2)
        return 0.01 * later * revenue * counts

    def shift(self, day: int, p: dict, place: str = "") -> float:
        """How far today's dealers are from the curve, from their answers so far today, and how much further those
        with cars in the pickup town are."""
        if self.today[0] != day or not p["learn"] or not self.today[1]:
            return 0.0
        slope = self.model["slope"]
        shift = curve.shift(self.today[1], p["learn"], slope)
        here = self.today_at.get(place, [])
        if p["learn_pickup"] and here:
            shift += curve.shift([(log_odds + slope * shift, won) for log_odds, won in here], p["learn_pickup"], slope)
        return shift

    @staticmethod
    def draw(request, low: float, high: float) -> float:
        """A multiple from low to high that is fixed for the request, and differs between weeks for the same request id."""
        return low + (high - low) * share(f"{request['id']} {request['arrivedAt']} {request['referenceFeeCents']}")

    def choose(self, request, p: dict) -> tuple[Optional[str], list[dict]]:
        """The options to quote under the parameters `p`, or the reason to decline the request."""
        legs = request["legs"]
        named = self.explored(request, p) or kind(request) in p["kinds"]
        if len(legs) > 1 and not (p["trade_in"] or named):
            return "trade_in", []
        if not (p["private"] or named) and any(leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"] for leg in legs):
            return "private", []
        if min(self.notified[leg["pickup"]["placeId"]] for leg in legs) < p["min_notified"]:
            return "few_drivers", []
        due = self.limits(request, p).deadline  # the note's own deadline ends an option where it is the earlier one
        options = [{**o, "deadline": min(o["deadline"], due)} if due else o for o in request["options"] if p["same_day"] or o["kind"] != "same_day"]
        if not options:
            return "same_day_only", []
        drive = self.drive(request)
        if p["max_drive"] and drive > p["max_drive"]:
            return "long", []
        options = [o for o in options if self.slack(request, o) >= p["min_slack"]]
        if not options:
            return "slack", []
        if p["max_unbooked"] and self.unbooked() >= p["max_unbooked"]:
            return "backlog", []
        bar = next((chance for cars, chance in reversed(p["slow_bar"]) if self.unbooked() >= cars), None)
        if bar is not None and self.slow(request, options) > bar:
            return "slow", []
        if share(request["id"]) >= p["quote_share"]:
            return "volume", []
        return None, options

    def slack(self, request, option) -> int:
        """The minutes the desk has to find a driver: from the first minute a driver can set out with the first car to
        the last minute that is still on time."""
        legs = request["legs"]
        drives = [self.minutes[(leg["pickup"]["placeId"], leg["delivery"]["placeId"])] for leg in legs]
        if len(legs) == 1:
            return option["deadline"] - drives[0] - max(request["respondBy"], legs[0]["pickup"]["window"]["from"])
        # A trade-in: the new car must reach the customer inside their slot, and the old car comes back in the same
        # visit. The old car's pickup window is that slot, not a time the desk has to wait for.
        ready = max(request["respondBy"], legs[0]["pickup"]["window"]["from"])
        return min(legs[0]["delivery"]["window"]["to"], option["deadline"] - drives[1]) - drives[0] - ready

    def slow(self, request, options) -> float:
        """The chance that the request's order arrives late (slow.py), if the dealer takes the fastest of the options."""
        notified, fastest = min(self.notified[leg["pickup"]["placeId"]] for leg in request["legs"]), curve.fastest(options)
        start = max(request["respondBy"], request["legs"][0]["pickup"]["window"]["from"])
        odds = self.p["snow_odds"] if self.p["snow_odds"] and self.snowy(request["legs"], start, fastest["deadline"]) else 0
        return slow.chance(slow.known(request, fastest, notified, self.drive(request), len(self.roster)), slow.MODELS[self.p["slow_model"]], odds)

    def snowy(self, legs, start: int, end: int) -> bool:
        """Whether a forecast so far names a pickup or delivery place of the legs for hours between the two minutes."""
        places = {leg[end_]["placeId"] for leg in legs for end_ in ("pickup", "delivery")}
        return any(places & set(f["placeIds"]) and start < f["to"] and end > f["from"] for f in self.forecasts)

    def unbooked(self, hours: float = 0) -> int:
        """The won cars that no driver holds now: just won, dropped, or posted again after a failed visit. With `hours`,
        only those whose order must be collected within that many hours."""
        return sum(1 for id_, order in self.orders.items() for leg, at in enumerate(order["deliveredAt"])
                   if at is None and self.leg_gigs.get(id_, {}).get(leg) not in self.booked
                   and (not hours or order["lastPickupAt"] - self.now <= hours * HOUR))

    def drive(self, request) -> int:
        """The minutes on the road with the request's cars."""
        return sum(self.minutes[(leg["pickup"]["placeId"], leg["delivery"]["placeId"])] for leg in request["legs"])

    def long(self, request, p: dict) -> bool:
        return bool(p["long_drive"]) and self.drive(request) > p["long_drive"]

    def opening(self, request, p: dict) -> float:
        """The opening fee of the request's gigs, as a multiple of its typical fee."""
        if p["kinds"].get(kind(request), {}).get("fee"):
            return p["kinds"][kind(request)]["fee"]
        if p["long_fee"] and self.long(request, p):
            return p["long_fee"]
        if p["deep_drivers"] and min(self.notified[leg["pickup"]["placeId"]] for leg in request["legs"]) >= p["deep_drivers"]:
            return p["deep_fee"]
        return p["fee"]

    def post(self, order, legs, retry: Retry = Retry()) -> None:
        if not self.params()["read_notes"]:
            return super().post(order, legs, retry)
        # The starter's post, with what the note says in the first posting. The starter learns that from a failed visit,
        # which costs half the fee.
        request = self.requests[order["id"]]
        facts = notes.read(request["note"], request["arrivedAt"])
        retry = Retry(max(retry.pickup_from, facts.pickup_from), retry.manual_licence or facts.manual, retry.plates or facts.plates)
        audience = {"experienced": any(leg["car"]["premium"] for leg in order["legs"]), "manualLicence": retry.manual_licence}
        stops = without_windows(stops_for(order, legs, request["note"], retry), self.now)
        for stop in stops:
            leg = order["legs"][stop["leg"]]
            # The starter reads a closing time on the day the window starts. When the car is ready on a later day,
            # that leaves no time to collect it: the pickup then runs to the end of the request's window.
            if stop["kind"] == "pickup" and "window" in stop and stop["window"]["to"] < stop["window"]["from"] + HOUR:
                stop["window"] = {"from": stop["window"]["from"], "to": max(stop["window"]["from"], leg["pickup"]["window"]["to"])}
            # A trade-in's new car is due in the customer's slot, hours before the order's deadline, by which the old car
            # is back. Without a window of its own the world plans that delivery by the order's deadline.
            elif (stop["kind"] == "delivery" and "window" not in stop and len(order["legs"]) > 1 and leg["delivery"]["privateAddress"]
                  and leg["delivery"]["window"]["to"] >= self.now):
                stop["window"] = dict(leg["delivery"]["window"])
        if len(order["legs"]) == 1:
            self.fit(order, request, stops)
        self.outbox.append({"type": "post", "stops": stops, "audience": audience, "schedule": self.fees_for(order, len(legs))})
        if len(legs) > 1:  # a trade-in over the 12-hour limit for a gig with two cars goes as one gig per car
            self.send()
            if not self.gigs_of(order["id"]):
                for leg in legs:
                    self.post(order, [leg], retry)

    def limits(self, request, p: dict) -> notes.Limits:
        return notes.limits(request["note"], request["arrivedAt"]) if p["read_notes"] and p["note_limits"] else notes.Limits()

    def limited(self, order) -> dict:
        """The order as the desk books it: with the note's own deadline where that is the earlier one, and the last
        minute to collect the car that goes with it. A copy, so the world's order stays as it came."""
        request = self.requests.get(order["id"])
        due = self.limits(request, self.p).deadline if request else 0
        if not due or due >= order["deadline"]:
            return order
        last = {"lastPickupAt": min(order["lastPickupAt"], due - self.drive(request))} if "lastPickupAt" in order else {}
        return {**order, "deadline": due, **last}

    def fit(self, order, request, stops) -> None:
        """Fits the stops of a one-car order to the note's limits. The delivery ends at the note's deadline. Where the
        note gives the hours of a site, the pickup goes on one day while the site is open, the first day that is in
        time for the deadline: a window over several days lets a driver come after closing, and a visit at the closing
        minute fails. Where the drive allows it, the delivery is that day too, while its site is open. When the day
        ends without a driver, the gig expires and is posted again for the next day."""
        limits = self.limits(request, self.params())
        if limits == notes.Limits():
            return
        leg, drive = order["legs"][0], self.drive(request)
        pickup, delivery = (next(stop for stop in stops if stop["kind"] == kind_) for kind_ in ("pickup", "delivery"))
        deadline = min(order["deadline"], limits.deadline or order["deadline"])
        start, last = max(pickup.get("window", leg["pickup"]["window"])["from"], self.now), deadline - drive
        slot = leg["delivery"]["window"]["from"]  # a private address has its own slot, which can be days after the pickup

        def open_on(day: int, noted: tuple[int, int], stated) -> Optional[tuple[int, int]]:
            """The minutes a site is open on a day: the note's hours on a working day, the stated ones cut to them on a Saturday."""
            if stated is None:
                return (day * DAY + noted[0], day * DAY + (noted[1] or DAY))
            if day % 7 in stated["weekdays"]:
                return (day * DAY + (noted[0] or stated["opens"]), day * DAY + (noted[1] or stated["closes"]))
            if day % 7 == 5 and stated["saturday"]:
                return (day * DAY + max(noted[0], stated["saturday"]["opens"]), day * DAY + min(noted[1] or DAY, stated["saturday"]["closes"]))
            return None

        if limits.pickup_hours != (0, 0) or limits.delivery_hours != (0, 0):
            days = range(start // DAY, max(start, last) // DAY + 8)
            # First a day with both stops in the sites' hours and in time; then one with the pickup in its site's hours and
            # in time; then, for an order that is late whatever happens, the first day the pickup site is open.
            for both, in_time in ((True, True), (False, True), (False, False)):
                for day in days:
                    here, there = open_on(day, limits.pickup_hours, leg["pickup"]["hours"]), open_on(day, limits.delivery_hours, leg["delivery"]["hours"])
                    if here is None or (both and there is None):
                        continue
                    arrive, until = (max(slot, there[0]), min(deadline, there[1] - 1)) if both else (0, 1)
                    if arrive >= until:  # the delivery's slot is not on this day
                        continue
                    first = max(start, here[0], there[0] - drive if both else 0)
                    final = min(here[1] - 1, last if in_time else NEVER, there[1] - 1 - drive if both else NEVER)
                    if final - first >= HOUR:
                        pickup["window"] = {"from": first, "to": final}
                        if both:
                            delivery["window"] = {"from": arrive, "to": until}
                        elif limits.deadline and deadline > max(self.now, slot):
                            delivery["window"] = {"from": slot, "to": deadline}
                        else:
                            delivery.pop("window", None)
                        return
        if limits.deadline and deadline > max(self.now, slot):  # in place of the starter's reading, which takes the time on the day the window starts
            delivery["window"] = {"from": slot, "to": deadline}

    def repost(self, gig_id: str) -> None:
        """A gig whose window ended without a driver. The starter posts it again without windows; with the note's
        limits the desk posts a one-car gig for the next day that fits them."""
        action = self.posts.get(gig_id)
        order = self.orders.get(action["stops"][0]["orderId"]) if action else None
        if (order is None or len(order["legs"]) != 1 or self.leg_gigs.get(order["id"], {}).get(0) != gig_id
                or self.limits(self.requests[order["id"]], self.params()) == notes.Limits()):
            return super().repost(gig_id)
        self.leg_gigs[order["id"]].pop(0)
        before = {stop["kind"]: stop.get("window") for stop in action["stops"]}
        self.post(order, [0], Retry((before["pickup"] or {"from": 0})["from"], action["audience"]["manualLicence"], any(stop.get("withPlates") for stop in action["stops"])))
        for stop in self.outbox[-1]["stops"]:  # a window that ended once ends again: the world's own window then applies, as in the starter
            if "window" in stop and stop["window"] == before[stop["kind"]]:
                del stop["window"]

    def change(self, order) -> None:
        super().change(self.limited(order))

    def usual_fee(self, request, p: dict) -> float:
        """What drivers usually take for the request, in cents: its typical fee, or its lane's usual fee."""
        if p["lane_fee"] and len(request["legs"]) == 1 and lane(request) in LANES:
            return math.exp(LANES[lane(request)])
        return request["referenceFeeCents"]

    def fees_for(self, order, cars, opening: float = 1.0):
        """The fees for some of the order's cars from now. `opening` multiplies the opening fee."""
        p = self.params()
        request = self.requests[order["id"]]
        usual = self.usual_fee(request, p) * cars / len(order["legs"])
        if p["snow_fee"] and self.snowy(order["legs"], self.now, order["deadline"]):
            usual *= p["snow_fee"]  # drivers who stay at home leave fewer to book it: the whole schedule is dearer
        rule = self.fee_rule(order, p)
        fee = usual * (rule[0] if rule else self.opening(request, p)) * opening
        if order["id"] in self.urgent:
            return steep(self.now, fee, self.level)
        if self.level == 1 or not (p["fee_cap"] or p["jump"] or rule):
            return rising(self.now, fee, self.level)
        step, top = (usual * rule[1], max(fee, usual * rule[2])) if rule else (usual / 10, max(fee, usual * p["fee_cap"])) if p["fee_cap"] else (fee / 10, fee * 1.5)
        fees = {self.now + k * HOUR: min(fee + k * step, top) for k in range(math.ceil((top - fee) / step - 1e-9) + 1)}
        last, jump = order["lastPickupAt"], usual * p["jump"]
        plan = last // DAY * DAY + PLAN_MORNING if last % DAY > PLANS_SAME_DAY else (last // DAY - 1) * DAY + PLAN_EVENING
        if jump > fee and plan > self.now:
            before = max(fee_ for at, fee_ in fees.items() if at <= plan)
            fees = {**{at: fee_ if at < plan else max(fee_, jump) for at, fee_ in fees.items()}, plan: max(before, jump)}
        steps, shown = [], None
        for at, fee_ in sorted(fees.items()):
            cents = max(1, int(fee_ + 0.5))
            if cents != shown:
                steps.append({"at": at, "feeCents": cents})
                shown = cents
        return steps

    def fee_rule(self, order, p: dict) -> Optional[list[float]]:
        """The rule of `fee_rules` for the order now: [opening fee, rise an hour, top fee], or None."""
        if not p["fee_rules"]:
            return None
        notified, hours = min(self.notified[leg["pickup"]["placeId"]] for leg in order["legs"]), (order["lastPickupAt"] - self.now) / HOUR
        return next((rule[4:] for rule in p["fee_rules"] if rule[0] <= notified < rule[1] and rule[2] <= hours < rule[3]), None)

    def push(self) -> None:
        """While `push_from` won cars have no driver, each open gig whose order must be collected within `push_hours`
        shows at least `push_fee` x the typical fee from now, once: the cars that fill the backlog leave it sooner."""
        p = self.params()
        if not p["push_from"] or self.unbooked() < p["push_from"]:
            return
        for id_, order in self.orders.items():
            if id_ in self.urgent or order["lastPickupAt"] - self.now > p["push_hours"] * HOUR:
                continue
            for gig_id in self.gigs_of(id_):
                action = self.posts.get(gig_id)
                if action is None or gig_id in self.booked or gig_id in self.pushed:
                    continue
                request = self.requests[id_]
                usual = self.usual_fee(request, p) * pickups(action) / len(order["legs"])
                shown = max((step["feeCents"] for step in self.fees.get(gig_id, []) if step["at"] <= self.now), default=0)
                self.pushed.add(gig_id)
                if shown < usual * p["push_fee"]:
                    opens = (self.fee_rule(order, p) or [self.opening(request, p)])[0]
                    self.outbox.append({"type": "reprice", "gigId": gig_id, "schedule": self.fees_for(order, pickups(action), p["push_fee"] / opens)})

    def chased(self) -> list[tuple[str, dict]]:
        """The open gigs that get direct offers now: (gig id, order). Its order must be collected within `offer_hours`,
        or should have been, and the app has had half an hour to find a driver."""
        hours = self.params()["offer_hours"]
        return [(gig_id, order) for id_, order in self.orders.items() if hours and order["lastPickupAt"] - self.now <= hours * HOUR
                for gig_id in self.gigs_of(id_) if gig_id not in self.booked and self.now - self.opened.get(gig_id, self.now) >= OFFER_AFTER]

    def wake_at(self) -> int:
        """The next minute the desk looks at its open gigs, whatever happens until then."""
        home = self.home_wake()
        if not self.chased():
            return home
        minute = self.now % DAY
        return min(home, self.now + LOOK_EVERY if OFFERS_FROM <= minute < OFFERS_TO else self.now - minute + OFFERS_FROM + (DAY if minute >= OFFERS_TO else 0))

    def home_wake(self) -> int:
        """The next minute for offers to drivers who live where a car is going: when the open ones end, or at 07:00."""
        ends = [max(self.offers.get(gig_id, {}).values(), default=0) for gig_id, rounds in self.home.items() if rounds > 0 and gig_id not in self.booked]
        if not ends:
            return NEVER
        minute = self.now % DAY
        if not OFFERS_FROM <= minute < OFFERS_TO - OFFER_LASTS:
            return self.now - minute + OFFERS_FROM + (DAY if minute >= OFFERS_FROM else 0)
        return max(self.now + 1, min(ends))

    def home_look(self) -> None:
        """Sends direct offers for the open one-car gigs to drivers who live where the car is going, those who used the
        app today first. The app notifies drivers by the pickup, so these drivers do not hear of the gig otherwise."""
        p, today, minute = self.params(), self.now // DAY, self.now % DAY
        if not p["home_offers"] or not self.home or not OFFERS_FROM <= minute < OFFERS_TO - OFFER_LASTS:
            return
        if self.offered[0] != today:
            self.offered = (today, {})
        sent = self.offered[1]
        for gig_id, rounds in list(self.home.items()):
            action = self.posts.get(gig_id)
            order = self.orders.get(action["stops"][0]["orderId"]) if action else None
            leg = action["stops"][0]["leg"] if action else 0
            if order is None or rounds <= 0 or gig_id not in self.gigs_of(order["id"]) or order["deliveredAt"][leg] is not None:
                del self.home[gig_id]
                continue
            sent_here = self.offers.setdefault(gig_id, {})
            if gig_id in self.booked or any(until > self.now for until in sent_here.values()):
                continue  # a driver holds it, or its offers are still open
            request, place, audience = self.requests[order["id"]], order["legs"][leg]["delivery"]["placeId"], action["audience"]
            homes = self.near[place] if p["home_km"] else {place}
            drivers = sorted((self.seen.get(d["id"]) != today, d["homePlaceId"] != place, d["id"]) for d in self.roster
                             if d["homePlaceId"] in homes and d["id"] not in sent_here and sent.get(d["id"], 0) < OFFERS_A_DRIVER
                             and d["id"] not in self.gave_back.get(gig_id, ())
                             and (not audience["manualLicence"] or d["licence"] == "manual")
                             and (not audience["experienced"] or (d["rating"] >= EXPERIENCED[0] and d["completedGigs"] >= EXPERIENCED[1])))
            fee = max(1, int(self.usual_fee(request, p) * pickups(action) / len(order["legs"]) * p["home_fee"] + 0.5))
            for _, _, driver in drivers[:min(p["home_offers"], OFFERS_A_GIG)]:
                self.outbox.append({"type": "offer", "gigId": gig_id, "driverId": driver, "feeCents": fee})
                sent_here[driver] = self.now + OFFER_LASTS
                sent[driver] = sent.get(driver, 0) + 1
            self.home[gig_id] = rounds - 1

    def look(self) -> None:
        """Sends direct offers for the gigs that are short of time, to the drivers who live nearest to the pickup among
        those who used the app today. The desk cannot see who works on a day; a look at a gig or a booking shows it."""
        self.home_look()
        p, today, minute = self.params(), self.now // DAY, self.now % DAY
        if not p["offer_hours"] or not OFFERS_FROM <= minute < OFFERS_TO - OFFER_LASTS:
            return
        if self.offered[0] != today:
            self.offered = (today, {})
        sent = self.offered[1]
        for gig_id, order in self.chased():
            action, sent_here = self.posts[gig_id], self.offers.setdefault(gig_id, {})
            free = OFFERS_A_GIG - sum(1 for until in sent_here.values() if until > self.now)
            if free <= 0:
                continue
            request, place = self.requests[order["id"]], order["legs"][action["stops"][0]["leg"]]["pickup"]["placeId"]
            audience = action["audience"]
            drivers = sorted((self.minutes.get((d["homePlaceId"], place), 0), d["id"]) for d in self.roster
                             if self.seen.get(d["id"]) == today and d["id"] not in sent_here and sent.get(d["id"], 0) < OFFERS_A_DRIVER
                             and d["id"] not in self.gave_back.get(gig_id, ())
                             and (not audience["manualLicence"] or d["licence"] == "manual")
                             and (not audience["experienced"] or (d["rating"] >= EXPERIENCED[0] and d["completedGigs"] >= EXPERIENCED[1])))
            in_app = max((step["feeCents"] for step in self.fees.get(gig_id, []) if step["at"] <= self.now), default=0)
            fee = max(in_app, int(self.usual_fee(request, p) * pickups(action) / len(order["legs"]) * p["offer_fee"] + 0.5))
            for _, driver in drivers[:free]:
                self.outbox.append({"type": "offer", "gigId": gig_id, "driverId": driver, "feeCents": fee})
                sent_here[driver] = self.now + OFFER_LASTS
                sent[driver] = sent.get(driver, 0) + 1

    def reopen(self, gig_id: str) -> None:
        """A dropped gig is open again with its old schedule, which shows its top fee by then. Drivers are notified
        of it again and book it fast at any fee, so its fees start again near the opening fee."""
        action = self.posts.get(gig_id)
        order = self.orders.get(action["stops"][0]["orderId"]) if action else None
        # After the deadline warning, the world sends the warning again and the steep fees start again.
        if order is not None and order["id"] not in self.urgent and gig_id in self.gigs_of(order["id"]):
            self.outbox.append({"type": "reprice", "gigId": gig_id, "schedule": self.fees_for(order, pickups(action), self.params()["drop_fee"])})

    def win(self, order) -> None:
        self.won_at.setdefault(order["id"], self.now)
        super().win(self.limited(order))
        self.push()

    def handle(self, event) -> None:
        if event["kind"] == "ledger" and event["line"]["kind"] in ("late_refund", "undelivered_penalty") and event["line"]["orderId"]:
            self.late.add(event["line"]["orderId"])
        elif event["kind"] in ("order_won", "order_lost"):
            if self.opt:  # as below: an answer counts only for a quote that is still in `asked`
                asked_id = event["order"]["id"] if event["kind"] == "order_won" else event["requestId"]
                self.opt.answer(asked_id, event["kind"] == "order_won", asked_id in self.asked)
            asked = self.asked.pop(event["order"]["id"] if event["kind"] == "order_won" else event["requestId"], None)
            if asked is not None:
                dealer, day, log_odds = asked
                answers = self.answers.setdefault(dealer, [0, 0])
                answers[0] += 1
                answers[1] += event["kind"] == "order_won"
                if self.today[0] != day:
                    self.today, self.today_at = (day, []), {}
                self.today[1].append((log_odds, event["kind"] == "order_won"))
                self.today_at.setdefault(self.asked_at.pop(event["order"]["id"] if event["kind"] == "order_won" else event["requestId"]), []).append((log_odds, event["kind"] == "order_won"))
        elif event["kind"] == "forecast":
            self.forecasts.append({"from": event["from"], "to": event["to"], "placeIds": event["placeIds"]})
        elif event["kind"] in ("gig_viewed", "gig_booked"):
            self.seen[event["driverId"]] = event["at"] // DAY
        elif event["kind"] == "gig_dropped":
            self.gave_back.setdefault(event["gigId"], set()).add(event["driverId"])
            if self.p["home_offers"] and event["gigId"] in self.posts and pickups(self.posts[event["gigId"]]) == 1:
                self.home[event["gigId"]] = self.p["home_rounds"]
        super().handle(event)
        if event["kind"] == "gig_dropped" and self.p["drop_fee"]:
            self.reopen(event["gigId"])
        if event["kind"] == "gig_dropped":
            self.push()

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
            elif action["type"] == "post":
                self.opened[result["id"]], self.fees[result["id"]] = self.now, action["schedule"]
                if self.p["home_offers"] and pickups(action) == 1:
                    self.home[result["id"]] = self.p["home_rounds"]
            elif action["type"] == "reprice":
                self.fees[action["gigId"]] = action["schedule"]


def kind(request) -> str:
    """The kind of a request that is not one car between two dealer sites: "trade_in", "private_pickup" or
    "private_delivery"; "" for the others."""
    if len(request["legs"]) > 1:
        return "trade_in"
    leg = request["legs"][0]
    return "private_pickup" if leg["pickup"]["privateAddress"] else "private_delivery" if leg["delivery"]["privateAddress"] else ""


def lane(request) -> str:
    """The key of a one-car request in LANES: its pickup place, its delivery place, and whether an address is private."""
    leg = request["legs"][0]
    private = leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"]
    return f"{leg['pickup']['placeId']}>{leg['delivery']['placeId']}{' private' if private else ''}"


def share(request_id: str) -> float:
    """A number from 0 to 1 that is fixed for a request id, so a variant makes the same choice on every run."""
    return int.from_bytes(hashlib.sha256(request_id.encode()).digest()[:8], "big") / 2**64


def fingerprint(params: dict) -> str:
    """Changes when the parameters or this file change. A sweep plays a week again when its saved run has another fingerprint."""
    source = inspect.getsource(sys.modules[__name__])
    if params.get("curve"):  # the curve's code and weights count only for the variants that price by it
        source += inspect.getsource(curve) + json.dumps(curve.MODELS[params.get("model", "")], sort_keys=True)
    if params.get("opt"):
        source += inspect.getsource(optquote) + json.dumps(optquote.WEIGHTS, sort_keys=True)
    if params.get("lane_fee"):
        source += json.dumps(LANES, sort_keys=True)
    if params.get("read_notes"):
        source += inspect.getsource(notes)
    if any(params.get(name) for name in ("slow_bar", "slow_step", "late_cost", "rule_cost")):
        source += inspect.getsource(slow)
    return hashlib.sha256((source + json.dumps({**DEFAULTS, **params}, sort_keys=True)).encode()).hexdigest()[:12]
