"""Out-and-back pairs (variants `...-pairs-*`): one driver delivers a won car and drives another back in one gig.

A one-way fee pays for the driver's trip home; a car that goes back the same way removes it. The world prices a trade-in,
which is one car out and one back, at 26.3 cents a drive minute against 47.2 for a one-car dealer request, and drivers
book trade-ins at 0.78 of the two cars' one-way typical fees as fast as our one-car gigs at 1.0 x. Our cars book in six
minutes, so a return request rarely finds the first car still without a driver: the desk has to wait for it
(scratch/strategy/README.md, `pairs.py`: 296 of 887 one-car dealer requests a week are followed by a return in time).

- **Hold.** A won one-car dealer order with `pair_slack` hours or more to its last pickup minute, on a lane with
  `pair_traffic` or more return requests a week (returns.json, scratch/pairs_returns.py), is not posted at once. It waits
  at most `pair_hold` hours, never past the day's last requests, and never past `pair_left` hours before its last pickup.
  Held cars do not count as cars without a driver in the backlog surcharge and the gate: they wait by choice, with a day
  in hand.
- **Quote the return at the pair's cost** (`pair_cost`). A one-car dealer request that can run back with a held car,
  both ends within the notification distance of the held car's other ends, is priced at that cost in place of `cost`.
- **One gig.** When such an order is won, both cars go in one gig, in the order that leaves a driver the most time:
  out, deliver, collect, back. It needs a plan that is on time for both cars by the road minutes, the stops' windows and
  the sites' stated hours, within the 12 hours of driving of a gig with more than one car (RULES.md, Gigs), for a driver
  who books it `pair_left` hours from now. It opens at `pair_fee` x the two typical fees and rises a tenth of them an
  hour to `pair_top` x. A held car without a return is posted alone, as the policy posts it.
- **Two again when it goes wrong.** An open pair gig whose latest start is `pair_split` hours away, that expires, that
  gets a deadline warning, or whose order changes is withdrawn and both cars are posted alone. A cancelled order leaves
  the other car alone in its gig when a driver holds it (the world shortens the gig); when the gig was open, the other car
  is posted alone. A failed visit posts that car alone, and the driver goes on with the other. Direct offers go to the
  cars alone, not to pair gigs.

Kept out of policy.py so that the fingerprints of the saved weeks stay: play.py takes this class when `pair_hold` is set.
`VERSION` follows this file and returns.json, so a sweep plays the weeks again when either changes. The live desk does
not take this class yet: a gig with two orders is a new case for its restart logic, and must pass the replays first.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Optional

from spread.starter import DAY, HOUR, Retry, steep

from .policy import OPEN, OPENS, Policy, kind

HERE = Path(__file__)
RETURNS: dict[str, float] = json.loads(HERE.with_name("returns.json").read_text(encoding="utf-8"))  # "a>b" -> return requests a week
VERSION = hashlib.sha256(HERE.read_bytes() + HERE.with_name("returns.json").read_bytes()).hexdigest()[:12]
PARAMS = {
    "pair_hold": 0,       # the most hours a won car waits unposted for a return request; 0 is off
    "pair_slack": 16,     # ... a car with at least this many hours from the win to its last pickup minute
    "pair_traffic": 8,    # ... on a lane with at least this many return requests a week
    "pair_left": 10,      # a pair forms only when a driver who books it this many hours from now can still deliver both cars on time; a held car goes alone this long before its last pickup
    "pair_split": 6,      # an open pair gig goes again as two gigs this many hours before its latest start
    "pair_fee": 0.7,      # the pair gig opens at this multiple of the two cars' typical fees ...
    "pair_top": 1.0,      # ... and rises a tenth of them an hour up to this multiple
    "pair_cost": 0,       # a request that can pair with a held car is quoted at this cost, as a multiple of its typical fee; 0 is `cost`
    "pair_version": "",   # VERSION, set by the variant, so a sweep plays the weeks again when this file changes
}
GIG_DRIVING = 12 * HOUR  # RULES.md: a gig with more than one car plans at most 12 hours of driving
PLATES, CHARGING = 30, 40  # minutes on a pickup (RULES.md, Gigs)


def next_open(t: int, hours: Optional[dict]) -> int:
    """The first minute from t that a site with these stated hours is open."""
    if hours is None:
        return t
    for _ in range(8):
        day, minute = divmod(t, DAY)
        if day % 7 in hours["weekdays"]:
            opens, closes = hours["opens"], hours["closes"]
        elif day % 7 == 5 and hours.get("saturday"):
            opens, closes = hours["saturday"]["opens"], hours["saturday"]["closes"]
        else:
            t = (day + 1) * DAY
            continue
        if minute < opens:
            return day * DAY + opens
        if minute < closes:
            return t
        t = (day + 1) * DAY
    return t


class PairPolicy(Policy):
    def __init__(self, world, level: int, now: int, params: dict, roster: list[dict], map_: dict):
        own = {name: params.get(name, default) for name, default in PARAMS.items()}
        super().__init__(world, level, now, {k: v for k, v in params.items() if k not in PARAMS}, roster, map_)
        if self.p["push_from"] or self.p["home_offers"]:
            raise ValueError("Pairs do not reprice for the backlog (push_from) or send offers home (home_offers)")
        self.p.update(own)
        self.held: dict[str, int] = {}  # order id -> the minute its car is posted alone if no return comes
        self.pair_gigs: dict[str, int] = {}  # gig id of a pair -> the latest minute a driver can set out and deliver both cars on time
        self.first: Optional[str] = None  # the order whose first post is being decided
        self.pairing = False  # the quote being made is for a return of a held car

    # The parts of the policy that see a held car or a pair gig.

    def params(self) -> dict:
        p = super().params()
        return {**p, "cost": p["pair_cost"]} if self.pairing and p["pair_cost"] else p

    def unbooked(self, hours: float = 0) -> int:
        held = sum(1 for id_ in self.held if not hours or self.orders[id_]["lastPickupAt"] - self.now <= hours * HOUR)
        return super().unbooked(hours) - held

    def quote(self, request) -> None:
        self.requests[request["id"]] = request
        partner = self.partner(request) if self.p["pair_hold"] else None
        self.pairing = partner is not None
        try:
            super().quote(request)
        finally:
            self.pairing = False
        if partner:
            self.decisions[request["id"]]["pair"] = partner

    def win(self, order) -> None:
        self.first = order["id"]
        try:
            super().win(order)
        finally:
            self.first = None

    def post(self, order, legs, retry: Retry = Retry()) -> None:
        if self.first == order["id"]:
            self.first = None
            if self.p["pair_hold"] and self.pairable(order) and (self.pair_up(order) or self.hold(order)):
                return
        super().post(order, legs, retry)

    def look(self) -> None:
        for id_, until in list(self.held.items()):
            if until <= self.now:
                self.release(id_)
        for gig_id, latest in list(self.pair_gigs.items()):
            if gig_id not in self.booked and latest - self.p["pair_split"] * HOUR <= self.now:
                self.split(gig_id, "split")
        super().look()

    def wake_at(self) -> int:
        times = [*self.held.values(), *(latest - self.p["pair_split"] * HOUR for gig_id, latest in self.pair_gigs.items() if gig_id not in self.booked)]
        return min([super().wake_at(), *(max(t, self.now + 1) for t in times)])

    def repost(self, gig_id: str) -> None:
        if gig_id in self.pair_gigs:  # the gig has left the app
            return self.split(gig_id, "expired", withdraw=False)
        super().repost(gig_id)

    def raise_fees(self, order_id: str) -> None:
        if order_id in self.held:
            self.urgent.add(order_id)
            return self.release(order_id)
        gig_id = self.pair_of(order_id)
        if gig_id and gig_id not in self.booked:
            self.urgent.add(order_id)
            return self.split(gig_id, "warning")
        super().raise_fees(order_id)

    def change(self, order) -> None:
        self.held.pop(order["id"], None)  # Desk.change posts it, alone
        gig_id = self.pair_of(order["id"])
        if gig_id and gig_id not in self.booked and order["id"] in self.orders:
            self.orders[order["id"]] = self.limited(order)
            return self.split(gig_id, "changed")
        super().change(order)

    def reopen(self, gig_id: str) -> None:
        if gig_id in self.pair_gigs:
            ids = self.ids_of(gig_id)
            if len(ids) < 2:  # a cancelled order left one car in it: that car goes alone, at its own fee
                return self.split(gig_id, "dropped")
            if not any(id_ in self.urgent for id_ in ids):
                self.outbox.append({"type": "reprice", "gigId": gig_id, "schedule": self.pair_fees(ids, self.p["drop_fee"] or 1.0)})
            return
        super().reopen(gig_id)

    def chased(self) -> list[tuple[str, dict]]:
        return [(gig_id, order) for gig_id, order in super().chased() if gig_id not in self.pair_gigs]

    def handle(self, event) -> None:
        if event["kind"] == "order_cancelled":
            self.held.pop(event["orderId"], None)
            gig_id = self.pair_of(event["orderId"])
            super().handle(event)
            if gig_id and any(g["gigId"] == gig_id and g["outcome"] == "withdrawn" for g in event["gigs"]):
                self.split(gig_id, "cancelled", withdraw=False)
            return
        super().handle(event)

    # Holding, pairing and splitting.

    def pairable(self, order) -> bool:
        """A one-car order between two dealer sites, still to collect, without a deadline warning."""
        request = self.requests.get(order["id"])
        return (request is not None and len(order["legs"]) == 1 and kind(request) == "" and order["deliveredAt"][0] is None
                and order["id"] not in self.urgent)

    def hold(self, order) -> bool:
        p, leg = self.p, order["legs"][0]
        if order["lastPickupAt"] - self.now < p["pair_slack"] * HOUR:
            return False
        if RETURNS.get(f"{leg['pickup']['placeId']}>{leg['delivery']['placeId']}", 0) < p["pair_traffic"]:
            return False
        last_request = self.now // DAY * DAY + OPENS + OPEN
        until = min(self.now + int(p["pair_hold"] * HOUR), last_request, order["lastPickupAt"] - int(p["pair_left"] * HOUR))
        if until <= self.now:
            return False
        self.held[order["id"]] = until
        self.decisions.setdefault(order["id"], {})["held"] = {"at": self.now, "until": until}
        return True

    def release(self, order_id: str) -> None:
        """Posts a held car alone."""
        del self.held[order_id]
        self.decisions.setdefault(order_id, {}).setdefault("held", {})["alone"] = self.now
        Policy.post(self, self.orders[order_id], [0])

    def partner(self, request) -> Optional[str]:
        """The held order that the request's car can go back with, in one gig that a driver can still book in time."""
        if len(request["legs"]) != 1 or kind(request) != "" or not self.held:
            return None
        reason, options = self.choose(request, self.params())
        if reason:
            return None
        option = min(options, key=lambda o: o["deadline"])
        drive = self.drive(request)
        order = {"id": request["id"], "legs": request["legs"], "deadline": option["deadline"], "lastPickupAt": option["deadline"] - drive,
                 "deliveredAt": [None], "option": option["kind"]}
        best = self.best_pair(order, at=request["respondBy"])
        return best[0] if best else None

    def returns(self, order, other) -> bool:
        """Whether one car runs back from near the other's delivery place to near its pickup place."""
        a, b = order["legs"][0], other["legs"][0]
        return (b["pickup"]["placeId"] in self.near[a["delivery"]["placeId"]] and b["delivery"]["placeId"] in self.near[a["pickup"]["placeId"]])

    def best_pair(self, order, at: int) -> Optional[tuple[str, dict, int]]:
        """The held order to pair with, the post of both cars, and the latest start: the pair that leaves a driver the most time."""
        best = None
        for id_ in self.held:
            other = self.orders[id_]
            if not self.returns(other, order):
                continue
            mine, theirs = self.single(order), self.single(other)
            for stops in (theirs["stops"] + mine["stops"], mine["stops"] + theirs["stops"]):
                latest = self.latest(stops, {order["id"]: order, id_: other})
                if latest is not None and latest >= at + self.p["pair_left"] * HOUR and (best is None or latest > best[2]):
                    audience = {name: theirs["audience"][name] or mine["audience"][name] for name in mine["audience"]}
                    best = (id_, {"type": "post", "stops": stops, "audience": audience}, latest)
        return best

    def pair_up(self, order) -> bool:
        """Posts the order's car in one gig with a held car that it runs back with. False when none fits."""
        best = self.best_pair(order, at=self.now)
        if best is None:
            return False
        id_, action, latest = best
        del self.held[id_]
        self.outbox.append({**action, "schedule": self.pair_fees([id_, order["id"]])})
        self.send()  # the gig's id now, as for a trade-in: later events of either order find it
        gig_id = self.leg_gigs.get(order["id"], {}).get(0)
        if gig_id is None:  # refused: both alone
            Policy.post(self, self.orders[id_], [0])
            Policy.post(self, order, [0])
            self.decisions.setdefault(order["id"], {})["paired"] = {"with": id_, "refused": True}
            return True
        self.pair_gigs[gig_id] = latest
        for one, other in ((order["id"], id_), (id_, order["id"])):
            self.decisions.setdefault(one, {})["paired"] = {"with": other, "gig": gig_id, "at": self.now, "latest": latest}
        return True

    def split(self, gig_id: str, why: str, withdraw: bool = True) -> None:
        """Takes a pair gig out of the app, when it is still there, and posts each car that it still carries alone."""
        del self.pair_gigs[gig_id]
        if withdraw:
            self.outbox.append({"type": "withdraw", "gigId": gig_id})
        for stop in self.posts[gig_id]["stops"]:
            if stop["kind"] == "pickup" and self.leg_gigs.get(stop["orderId"], {}).get(stop["leg"]) == gig_id:
                self.leg_gigs[stop["orderId"]].pop(stop["leg"])
                if stop["orderId"] in self.orders:
                    self.decisions.setdefault(stop["orderId"], {}).setdefault("paired", {})["split"] = {"at": self.now, "why": why}
                    Policy.post(self, self.orders[stop["orderId"]], [stop["leg"]])

    def single(self, order) -> dict:
        """The policy's post of the order's car alone, without sending it."""
        Policy.post(self, order, [0])
        return self.outbox.pop()

    def latest(self, stops: list[dict], orders: dict[str, dict]) -> Optional[int]:
        """The latest minute that a driver can set out to the first stop and still make every stop in its window and on
        time, or None when no start can; within the 12 hours of driving of a gig with two cars."""
        places = [orders[s["orderId"]]["legs"][s["leg"]][s["kind"]]["placeId"] for s in stops]
        if sum(self.minutes[(a, b)] for a, b in zip(places, places[1:])) > GIG_DRIVING:
            return None
        if not self.in_time(stops, orders, self.now):
            return None
        low, high = self.now, self.now + 4 * DAY
        while high - low > 5:
            mid = (low + high) // 2
            low, high = (mid, high) if self.in_time(stops, orders, mid) else (low, mid)
        return low

    def in_time(self, stops: list[dict], orders: dict[str, dict], start: int) -> bool:
        """Whether a driver who arrives at the first stop no earlier than `start` makes every stop in its window, when
        its site is open, and delivers every car by its deadline."""
        t, place = start, None
        for stop in stops:
            order = orders[stop["orderId"]]
            leg = order["legs"][stop["leg"]]
            site = leg[stop["kind"]]
            if place is not None:
                t += self.minutes[(place, site["placeId"])]
            place = site["placeId"]
            if stop["kind"] == "pickup":
                window = stop.get("window", leg["pickup"]["window"])
                end = window["to"]
            else:
                window = stop.get("window", {"from": leg["delivery"]["window"]["from"], "to": order["deadline"]})
                end = min(window["to"], order["deadline"])
            t = next_open(max(t, window["from"]), site["hours"])
            if t > end:
                return False
            if stop["kind"] == "pickup":
                t += PLATES * bool(stop.get("withPlates")) + CHARGING * bool(stop.get("withCharging"))
        return True

    def ids_of(self, gig_id: str) -> list[str]:
        """The orders whose cars a gig still carries."""
        return list(dict.fromkeys(s["orderId"] for s in self.posts[gig_id]["stops"]
                                  if self.leg_gigs.get(s["orderId"], {}).get(s["leg"]) == gig_id))

    def pair_of(self, order_id: str) -> Optional[str]:
        return next((gig_id for gig_id in self.gigs_of(order_id) if gig_id in self.pair_gigs), None)

    def pair_fees(self, order_ids: list[str], opening: float = 1.0) -> list[dict]:
        """The fees of a pair gig from now: `pair_fee` x the two typical fees, rising a tenth of them an hour to `pair_top` x."""
        p = self.p
        usual = sum(self.usual_fee(self.requests[id_], p) for id_ in order_ids)
        if any(id_ in self.urgent for id_ in order_ids):
            return steep(self.now, usual, self.level)
        fee, step = usual * p["pair_fee"] * opening, usual / 10
        top = max(fee, usual * p["pair_top"])
        steps, shown = [], None
        for k in range(math.ceil((top - fee) / step - 1e-9) + 1):
            cents = max(1, int(min(fee + k * step, top) + 0.5))
            if cents != shown:
                steps.append({"at": self.now + k * HOUR, "feeCents": cents})
                shown = cents
        return steps
