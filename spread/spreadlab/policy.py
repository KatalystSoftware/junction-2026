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
import sys
from typing import Optional

from spread.starter import Desk, rising, steep

from .server import drivers_near, near_places

DEFAULTS = {
    "price": 1.5,         # the quote, as a multiple of the option's list price
    "quote_share": 0.6,   # the share of acceptable requests that get a serious quote, to limit the cars won
    "same_day": False,    # offer the same_day option
    "trade_in": False,    # quote requests with two cars
    "private": False,     # quote requests with a private address
    "min_slack": 300,     # offer an option only with this many minutes between the first possible pickup and the last one that is on time
    "min_notified": 0,    # decline when fewer drivers than this are notified of the pickup
    "fee": 1.2,           # the opening fee, as a multiple of the request's typical fee
}
DECLINE = 10  # times the list price: a quote that loses costs nothing, and no quote costs goodwill (RULES.md)


class Policy(Desk):
    def __init__(self, world, level: int, now: int, params: dict, roster: list[dict], map_: dict):
        super().__init__(world, level, now)
        unknown = set(params) - set(DEFAULTS)
        if unknown:
            raise ValueError(f"Unknown parameters {sorted(unknown)}. The parameters are {sorted(DEFAULTS)}")
        self.p = {**DEFAULTS, **params}
        self.minutes = {(road["from"], road["to"]): road["minutes"] for road in map_["roads"]}
        self.notified = drivers_near(roster, near_places(map_))
        self.decisions: dict[str, dict] = {}  # request id -> what the policy answered, and why it declined
        self.refused: list[dict] = []  # the actions that the world refused

    def quote(self, request) -> None:
        self.requests[request["id"]] = request
        reason, options = self.choose(request)
        if reason:
            first = request["options"][0]
            prices = {first["kind"]: first["listPriceCents"] * DECLINE}
        else:
            prices = {o["kind"]: int(round(o["listPriceCents"] * self.p["price"])) for o in options}
        self.decisions[request["id"]] = {"declined": reason, "prices": prices}
        self.outbox.append({"type": "quote", "requestId": request["id"], "prices": prices})

    def choose(self, request) -> tuple[Optional[str], list[dict]]:
        """The options to quote, or the reason to decline the request."""
        legs = request["legs"]
        if len(legs) > 1 and not self.p["trade_in"]:
            return "trade_in", []
        if not self.p["private"] and any(leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"] for leg in legs):
            return "private", []
        if min(self.notified[leg["pickup"]["placeId"]] for leg in legs) < self.p["min_notified"]:
            return "few_drivers", []
        options = [o for o in request["options"] if self.p["same_day"] or o["kind"] != "same_day"]
        if not options:
            return "same_day_only", []
        drive = sum(self.minutes[(leg["pickup"]["placeId"], leg["delivery"]["placeId"])] for leg in legs)
        ready = max(request["respondBy"], max(leg["pickup"]["window"]["from"] for leg in legs))
        options = [o for o in options if o["deadline"] - drive - ready >= self.p["min_slack"]]
        if not options:
            return "slack", []
        if share(request["id"]) >= self.p["quote_share"]:
            return "volume", []
        return None, options

    def fees_for(self, order, cars):
        fee = self.requests[order["id"]]["referenceFeeCents"] * cars / len(order["legs"]) * self.p["fee"]
        return steep(self.now, fee, self.level) if order["id"] in self.urgent else rising(self.now, fee, self.level)

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
    return hashlib.sha256((source + json.dumps({**DEFAULTS, **params}, sort_keys=True)).encode()).hexdigest()[:12]
