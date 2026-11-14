"""The stand-in world: a week that answers a desk's quotes and gigs the way the played weeks did, so any desk in variants.py
can play it offline. It has the routes a desk uses of Bahn's practice world (`advance`, `act`, `snapshot`, `roster`,
`score`, `reveal`), and plays the requests and drivers of one seed's world file (pack.py).

What it draws, and from what:
- **Dealers.** A quote wins by the team's win curve (curve.py, the fit with a level for each day) at the day's level, which
  is measured from a played week of the same seed (the base week) when there is one. Each request has one hidden draw that
  agrees with the base week's answer at the base week's price, so the stand-in replays the base desk's wins and loses or
  wins the others by how far the new price is from that one. Each dealer's trust is counted as RULES.md says. The
  competitor answers what the desk wins at a dealer against the base week (`react`, fitted in scratch/opt).
- **Drivers.** An open gig is booked by the fitted chance a minute (model.py, fit.py). A booked driver drops the gig, or
  collects the car inside the time they have and drives it, by the fitted tables. The night the drivers stay at home is the
  base week's: the bookings due that day drop in its first hour by the share that dropped then.
- **Rules.** Fee schedules, stop windows, gigs that expire, the deadline warning, direct offers and the account follow
  RULES.md.

What it does not have: cancelled and changed orders, failed visits (it takes every note as read correctly), fines,
snow's slower drives, and drivers as people with a day: no driver is short because another gig took them, beyond the
fitted effect of the desk's other open gigs near the pickup. See README.md for what that means for its answers.
"""
from __future__ import annotations

import collections
import heapq
import math
import random
import zlib

from .. import curve
from . import fit, model

DAY, HOUR = 1440, 60
ENDS_AT = 9 * DAY + 22 * HOUR  # the second Wednesday at 22:00
M = curve.MODELS["day"]
# The odds of the kinds of request that the curve was not fitted on, as the default desk takes them (variants.KINDS).
KIND_ODDS = {"private_pickup": 0.06, "private_delivery": 0.37, "trade_in": 0.27}
DESIGN = {
    "react": 0.6,        # the competitor's answer to the desk's share at a dealer the day before, in log price per unit of share
    "anchor": 1.0,       # how far each day's own booking speed, measured on the base week, moves the fitted chance (0 is not at all)
    "level_sd": 0.3,     # how far a day's level can be from the curve, in log price, when it is measured on the base week
    "wave": 1.0,         # multiplies the share of the due bookings dropped on the wave night
    "wave_own": 1.0,     # 1 takes the wave night's share from the base week, 0 the fitted one
    "fee_gain": 1.0,     # multiplies the fitted effect of the fee on the chance of a booking
    "crowd_gain": 1.0,   # multiplies the fitted effect of the desk's other open gigs near the pickup
    "hazard": 0.0,       # added to the log of the chance of a booking, everywhere
    "drops": 1.0,        # multiplies the ordinary drops (not the wave night's)
    "rival": 0.0,        # added to every day's level, in log price
}
_max = max  # `advance` takes `max` as the API names it
sig = lambda z: 1 / (1 + math.exp(-max(-40.0, min(40.0, z))))


def kind_of(request: dict) -> str:
    if len(request["legs"]) > 1:
        return "trade_in"
    leg = request["legs"][0]
    return "private_pickup" if leg["pickup"]["privateAddress"] else "private_delivery" if leg["delivery"]["privateAddress"] else ""


def closes(hours: dict | None, day: int) -> int | None:
    """The minute of the day's closing at a site, or None when it is closed that day or has no hours."""
    if not hours:
        return None
    weekday = day % 7
    if weekday in hours["weekdays"]:
        return day * DAY + hours["closes"]
    if weekday == 5 and hours.get("saturday"):
        return day * DAY + hours["saturday"]["closes"]
    return None


def next_open(hours: dict | None, minute: int) -> int:
    """The first minute at or after `minute` at which the site is open."""
    if not hours:
        return minute
    for day in range(minute // DAY, minute // DAY + 9):
        weekday = day % 7
        span = (hours["opens"], hours["closes"]) if weekday in hours["weekdays"] else (hours["saturday"]["opens"], hours["saturday"]["closes"]) if weekday == 5 and hours.get("saturday") else None
        if span and minute < day * DAY + span[1]:
            return max(minute, day * DAY + span[0])
    return minute


def base_state(world: dict, base: dict | None, minutes: dict) -> dict:
    """What the base week shows of the seed's hidden week: each day's level, the answer and price of each of its quotes with the trust
    its dealer had then, the dealer's wins a day, and the night the drivers stayed at home."""
    out = {"level": {}, "quotes": {}, "won_day": collections.Counter(), "wave": {}, "orders": {}}
    if base is None:
        return out
    requests = {r["id"]: r for r in world["requests"]}
    # Trust as the dealer counted it through the base week: each delivered order on time adds one, a late one halves.
    done = sorted((line[0], line[3]) for line in base["ledger"] if line[1] == "revenue" and line[3])
    late = {oid for oid, o in base["orders"].items() if o.get("late")}
    trust, k, answers = collections.Counter(), 0, collections.defaultdict(list)
    for rid, request in sorted(requests.items(), key=lambda kv: (kv[1]["respondBy"], kv[0])):
        while k < len(done) and done[k][0] <= request["arrivedAt"]:
            dealer = requests[done[k][1]]["dealerId"] if done[k][1] in requests else None
            if dealer:
                trust[dealer] = trust[dealer] // 2 if done[k][1] in late else min(25, trust[dealer] + 1)
            k += 1
        quote, outcome, _ = base["quotes"].get(rid, (None, "unquoted", None))
        if not quote:
            continue
        options = [o for o in request["options"] if o["kind"] in quote]
        if not options:
            continue
        first = curve.fastest(options)
        multiple = quote[first["kind"]] / first["listPriceCents"]
        if multiple > 5:  # a decline
            continue
        a = curve.at_list(request, options, trust[request["dealerId"]], M) + KIND_ODDS.get(kind_of(request), 0.0)
        out["quotes"][rid] = (a, multiple, outcome == "won")
        if kind_of(request) == "":
            answers[request["arrivedAt"] // DAY].append((a - M["slope"] * math.log(multiple), outcome == "won"))
        if outcome == "won":
            out["won_day"][(request["dealerId"], request["arrivedAt"] // DAY)] += 1
    out["answers"] = dict(answers)
    out["orders"] = base["orders"]
    # The wave night: the bookings due that day that were held at midnight, and how many of them dropped in the first hour.
    night = fit.wave_days(base)
    for day, dropped in night.items():
        if dropped >= fit.WAVE:
            held = 0
            for gig in base["gigs"]:
                for at, _, _ in gig["booked"]:
                    end = next((d[0] for d in sorted(gig["dropped"]) if d[0] >= at), None) or (gig["picked"][0][0] if gig["picked"] else None)
                    if end is not None and at < day * DAY <= end and end // DAY == day:
                        held += 1
            out["wave"][day] = (dropped, max(held, dropped))
    return out


class StandIn:
    def __init__(self, world: dict, base: dict | None, weights: dict, map_: dict, design: dict | None = None, draw: int = 0, anchor: dict | None = None):
        self.world, self.w, self.d, self.draw = world, weights, {**DESIGN, **(design or {})}, draw
        unknown = set(design or {}) - set(DESIGN)
        if unknown:
            raise ValueError(f"Unknown design options {sorted(unknown)}")
        self.seed = world["seed"]
        self.minutes = {(r["from"], r["to"]): r["minutes"] for r in map_["roads"]}
        g = fit.geo()
        self.near = g["near"]
        self.roster_ = world["roster"]
        self.home = {d["id"]: d["homePlaceId"] for d in self.roster_}
        self.homes = collections.Counter(self.home.values())
        self.requests = {r["id"]: r for r in world["requests"]}
        self.base = base_state(world, base, self.minutes)
        sd = self.d["level_sd"]
        self.level = {day: curve.shift(answers, sd, M["slope"]) + self.d["rival"] for day, answers in self.base.get("answers", {}).items()}
        self.beta = [weights["weights"][name] for name in model.NAMES]
        i = model.NAMES.index
        for name in ("ln fee", "ln fee, first 15 min", "ln fee squared"):
            self.beta[i(name)] *= self.d["fee_gain"]
        self.beta[i("ln crowd")] *= self.d["crowd_gain"]
        self.offset = weights["intercept"] + self.d["hazard"]
        # day -> how much faster the base week's gigs were booked that day than the fitted chance says, as a log ratio; "week" for the other days
        self.anchor = {day: self.d["anchor"] * value for day, value in (anchor or {}).items()}
        self.now, self.seq, self.queue, self.n = 0, 0, [], 0
        self.out: list[dict] = []  # the events published since the last advance
        self.history: list[dict] = []
        self.quotes: dict[str, dict] = {}
        self.orders: dict[str, dict] = {}
        self.state: dict[str, dict] = {}  # order id -> what the world tracks of it
        self.gigs: dict[str, dict] = {}
        self.car_gig: dict[tuple[str, int], str] = {}  # the live gig of each car
        self.first_post: dict[tuple[str, int], int] = {}
        self.posts: collections.Counter = collections.Counter()
        self.busy: dict[str, int] = {}  # driver -> the minute they are free again
        self.offers_day: collections.Counter = collections.Counter()
        self.trust: collections.Counter = collections.Counter()
        self.won_day: collections.Counter = collections.Counter()
        self.asked_day: collections.Counter = collections.Counter()
        self.moved: dict[str, float] = {}
        self.moved_day = -1
        self.margin = self.revenue = 0
        self.outcomes: dict[str, tuple[str, str | None]] = {}
        self.ledger: collections.Counter = collections.Counter()
        for request in world["requests"]:
            self.at(request["arrivedAt"], "request", request["id"])
            self.at(request["respondBy"], "decide", request["id"])
        for event in world.get("forecasts", []):
            self.at(event["at"], "forecast", event)

    # Time.

    def at(self, minute: int, what: str, arg) -> None:
        self.n += 1
        heapq.heappush(self.queue, (minute, self.n, what, arg))

    def publish(self, kind: str, **fields) -> None:
        event = {"seq": self.seq, "at": self.now, "kind": kind, **fields}
        self.seq += 1
        self.out.append(event)
        self.history.append(event)

    def rng(self, *key) -> random.Random:
        return random.Random(zlib.crc32("|".join(map(str, (self.seed, self.draw) + key)).encode()))

    def advance(self, until=None, max: int = ENDS_AT, actions=None, **_) -> dict:
        results = self.act(actions) if actions else []
        stop, wake = min(max, ENDS_AT), set(until or ())
        woke = None
        while self.queue and self.queue[0][0] <= stop and (woke is None or self.queue[0][0] <= woke):
            minute, _, what, arg = heapq.heappop(self.queue)
            self.now = _max(self.now, minute)
            before = len(self.out)
            getattr(self, "do_" + what)(arg)
            if woke is None and any(e["kind"] in wake for e in self.out[before:]):
                woke = self.now
        self.now = woke if woke is not None else stop
        if self.now >= ENDS_AT:
            self.finish()
        events, self.out = self.out, []
        return {"results": results, "now": self.now, "events": events}

    def act(self, actions: list[dict]) -> list[dict]:
        return [getattr(self, "act_" + action["type"])(action) for action in actions]

    def snapshot(self) -> dict:
        return {"worldId": f"standin-{self.seed}", "now": self.now, "endsAt": ENDS_AT, "score": self.score(), "openRequests": [], "driverPositions": [],
                "orders": [dict(o) for o in self.orders.values()], "gigs": [self.public(g) for g in self.gigs.values()]}

    def roster(self) -> list[dict]:
        return self.roster_

    def delete(self) -> None:
        pass

    def events(self, after: int = -1, limit=None) -> list[dict]:
        return [e for e in self.history if e["seq"] > after]

    # Dealers.

    def do_request(self, rid: str) -> None:
        self.publish("price_request", request=self.requests[rid])

    def do_forecast(self, event: dict) -> None:
        self.publish("forecast", **{k: v for k, v in event.items() if k not in ("seq", "at", "kind")})

    def act_quote(self, action: dict) -> dict:
        request = self.requests.get(action["requestId"])
        if request is None or self.now >= request["respondBy"]:
            return {"ok": False, "reason": f"The response deadline of {action['requestId']} has passed"}
        self.quotes[request["id"]] = action["prices"]
        return {"ok": True}

    def do_decide(self, rid: str) -> None:
        request, prices = self.requests[rid], self.quotes.get(rid)
        dealer, day = request["dealerId"], request["arrivedAt"] // DAY
        if day != self.moved_day:  # the morning: the competitor looks at each dealer's requests of the day before
            self.moved_day = day
            react = self.d["react"]
            self.moved = {d: _max(-0.15, min(0.15, -react * (self.won_day[(d, dd)] - self.base["won_day"][(d, dd)]) / n))
                          for (d, dd), n in self.asked_day.items() if dd == day - 1 and n >= 5} if react and self.base["quotes"] else {}
        self.asked_day[(dealer, day)] += 1
        options = [o for o in request["options"] if prices and o["kind"] in prices]
        first = curve.fastest(options) if options else None
        multiple = prices[first["kind"]] / first["listPriceCents"] if first else 99.0
        won = False
        if multiple < 5:
            a = curve.at_list(request, options, self.trust[dealer], M) + KIND_ODDS.get(kind_of(request), 0.0)
            level = self.level.get(day, self.d["rival"]) + self.moved.get(dealer, 0.0)
            p = sig(a - M["slope"] * (math.log(multiple) - level))
            u = self.rng("dealer", rid).random()
            played = self.base["quotes"].get(rid)
            if played is not None:  # a hidden draw that agrees with the base week's answer at its price
                a0, m0, won0 = played
                p0 = sig(a0 - M["slope"] * (math.log(m0) - self.level.get(day, 0.0)))
                u = u * p0 if won0 else p0 + u * (1 - p0)
            won = u < p
        if not won:
            self.outcomes[rid] = ("lost" if prices else "unquoted", None)
            self.publish("order_lost", requestId=rid)
            return
        self.won_day[(dealer, day)] += 1
        menu = "+".join(sorted(o["kind"] for o in options))
        option = self.base["orders"][rid]["option"] if rid in self.base["orders"] and self.base["orders"][rid]["option"] in prices else None
        if option is None:
            taken, r, acc = self.w["took"].get(menu, {}), self.rng("option", rid).random(), 0.0
            total = sum(taken.values())
            option = first["kind"]
            for name in sorted(taken):
                acc += taken[name] / total
                if r < acc:
                    option = name
                    break
        self.win(request, option, prices[option])

    def win(self, request: dict, option: str, price: int) -> None:
        rid = request["id"]
        chosen = next(o for o in request["options"] if o["kind"] == option)
        played = self.base["orders"].get(rid)
        same = played is not None and played["option"] == option and not played["changed"]
        deadline = played["deadline"] if same else chosen["deadline"]
        legs = []
        for n, leg in enumerate(request["legs"]):
            windows = played["windows"][n] if same else [
                leg[end]["window"] if leg[end]["privateAddress"] else {"from": leg[end]["window"]["from"], "to": _max(leg[end]["window"]["from"], deadline)} for end in ("pickup", "delivery")]
            legs.append({"car": leg["car"], "pickup": {**leg["pickup"], "window": windows[0]}, "delivery": {**leg["delivery"], "window": windows[1]}})
        drive = self.route([(leg["pickup"]["placeId"], leg["delivery"]["placeId"]) for leg in legs])
        last = played["lastPickupAt"] if same else self.last_pickup(legs[0], deadline - drive - 1)
        order = {"id": rid, "dealerId": request["dealerId"], "option": option, "priceCents": price, "deadline": deadline, "legs": legs, "status": "waiting",
                 "deliveredAt": [None] * len(legs), "lastPickupAt": last}
        self.orders[rid] = order
        self.state[rid] = {"picked": [None] * len(legs), "warned": False, "late": False}
        self.outcomes[rid] = ("won", option)
        self.publish("order_won", order={**order, "deliveredAt": list(order["deliveredAt"])})
        self.at(_max(self.now, last - 3 * HOUR), "warn", rid)

    @staticmethod
    def last_pickup(leg: dict, minute: int) -> int:
        """The last minute at or before `minute` at which the pickup site's stated hours show it open."""
        hours = leg["pickup"].get("hours")
        if not hours or leg["pickup"]["privateAddress"]:
            return minute
        for day in range(minute // DAY, minute // DAY - 8, -1):
            close = closes(hours, day)
            if close is not None and next_open(hours, day * DAY) <= minute:
                return min(minute, close)
        return minute

    def route(self, lanes: list[tuple[str, str]]) -> int:
        """The road minutes of the cars in order, the drives between them included."""
        total = 0
        for n, (a, b) in enumerate(lanes):
            total += self.minutes[(a, b)] + (self.minutes[(lanes[n - 1][1], a)] if n else 0)
        return total

    def do_warn(self, oid: str) -> None:
        """`deadline_close`: the order has no driver three hours before its last pickup; again when it loses its driver later."""
        order, st = self.orders[oid], self.state[oid]
        if all(at is not None for at in order["deliveredAt"]) or self.held(oid):
            return
        st["warned"] = True
        self.publish("deadline_close", orderId=oid, lastPickupAt=order["lastPickupAt"])

    def held(self, oid: str) -> bool:
        """Whether a driver holds every car of the order that is still to collect."""
        st = self.state[oid]
        for leg, picked in enumerate(st["picked"]):
            if picked is None:
                gig = self.gigs.get(self.car_gig.get((oid, leg), ""))
                if gig is None or gig["status"] not in ("booked", "working"):
                    return False
        return True

    # Gigs.

    def public(self, gig: dict) -> dict:
        return {k: gig[k] for k in ("id", "stops", "audience", "schedule", "status", "postedAt", "feeCents", "driverId")}

    def act_post(self, action: dict) -> dict:
        stops = action["stops"]
        cars = [(s["orderId"], s["leg"]) for s in stops if s["kind"] == "pickup"]
        if not cars or any(oid not in self.orders for oid, _ in cars):
            return {"ok": False, "reason": "The gig names an order the desk does not hold"}
        for oid, leg in cars:
            live = self.gigs.get(self.car_gig.get((oid, leg), ""))
            if self.state[oid]["picked"][leg] is not None or (live is not None and live["status"] in ("open", "booked", "working")):
                return {"ok": False, "reason": f"{oid} leg {leg} is already in gig {live['id'] if live else '?'}"}
        legs = [self.orders[oid]["legs"][leg] for oid, leg in cars]
        lanes = [(leg["pickup"]["placeId"], leg["delivery"]["placeId"]) for leg in legs]
        if len(cars) > 1 and self.route(lanes) > 12 * HOUR:
            return {"ok": False, "reason": "A gig with more than one car may not plan more than 12 hours of driving"}
        for s in stops:
            if "window" in s and s["window"]["to"] < self.now:
                return {"ok": False, "reason": f"The {s['kind']} window of {s['orderId']} leg {s['leg']} ended: no driver can {'collect' if s['kind'] == 'pickup' else 'deliver'} the car in it"}
        # The last minute a driver can collect the first car and still reach every stop inside its window; None when the windows have run out
        # and the stops without one of their own run to the end of the world.
        first_oid, first_leg = cars[0]
        order, leg0 = self.orders[first_oid], legs[0]
        pickup_stop = next(s for s in stops if s["kind"] == "pickup")
        ready = _max(leg0["pickup"]["window"]["from"], pickup_stop.get("window", {}).get("from", 0))
        own = [s["window"] for s in stops if "window" in s]
        last = min(self.orders[oid]["lastPickupAt"] for oid, _ in cars)
        deadline = order["deadline"]
        close = closes(leg0["pickup"].get("hours"), deadline // DAY)
        ends = min([deadline] + ([close] if close else []))  # the order's own windows end here
        bounded = self.now <= last and self.now < ends
        latest, expires = None, None
        if bounded:
            latest = last
            if "window" in pickup_stop:
                latest = min(latest, pickup_stop["window"]["to"])
            for s in stops:
                if s["kind"] == "delivery" and "window" in s and (s["orderId"], s["leg"]) == cars[0]:
                    latest = min(latest, s["window"]["to"] - self.minutes[lanes[0]])
            expires = min([ends] + [w["to"] for w in own])
        elif own:
            expires = min(w["to"] for w in own)
        self.posts[cars[0]] += 1
        gid = f"g{len(self.gigs) + 1}"
        ref = sum(self.requests[oid]["referenceFeeCents"] / len(self.requests[oid]["legs"]) for oid, _ in cars)
        info = {"notified": sum(self.homes[p] for p in self.near[lanes[0][0]]), "at_delivery": sum(self.homes[p] for p in self.near[lanes[-1][1]]),
                "drivers": len(self.roster_), "drive": sum(self.minutes[lane] for lane in lanes), "experienced": action["audience"]["experienced"],
                "manual": action["audience"]["manualLicence"], "cars": len(cars),
                "private": any(leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"] for leg in legs)}
        first = self.first_post.setdefault(cars[0], self.now)
        gig = {"id": gid, "stops": stops, "audience": action["audience"], "schedule": action["schedule"], "status": "open", "postedAt": self.now,
               "feeCents": action["schedule"][0]["feeCents"], "driverId": None, "cars": cars, "lanes": lanes, "ref": ref, "static": model.static(info),
               "ready": ready, "latest": latest, "expires": expires, "first": first, "opened": self.now, "reopened": False, "reposted": self.now > first,
               "version": 0, "rng": self.rng("gig", cars[0][0], cars[0][1], self.posts[cars[0]]), "offers": {}, "gave_back": set(), "pickup": lanes[0][0],
               "delivery": lanes[-1][1], "last": last}
        self.gigs[gid] = gig
        for car in cars:
            self.car_gig[car] = gid
        if expires is not None:
            self.at(_max(expires, self.now + 1), "expire", gid)
        self.open(gig)
        return {"ok": True, "id": gid}

    def open(self, gig: dict) -> None:
        """The gig is in the app from now: a few drivers near the pickup look at it, and the first slice of its time starts."""
        gig["version"] += 1
        r = gig["rng"]
        near = [d["id"] for d in self.roster_ if d["homePlaceId"] in self.near[gig["pickup"]]]
        hour = self.now % DAY // HOUR
        for driver in r.sample(near, min(len(near), 0 if hour >= 23 or hour < 6 else 1 + int(r.random() * 3))):
            self.at(self.now + 1 + int(r.random() * 10), "view", (gig["id"], gig["version"], driver))
        self.at(self.now, "slice", (gig["id"], gig["version"]))

    def do_view(self, arg) -> None:
        gid, version, driver = arg
        gig = self.gigs[gid]
        if gig["status"] == "open" and gig["version"] == version:
            self.publish("gig_viewed", gigId=gid, driverId=driver)

    def crowd(self, gig: dict) -> int:
        places = self.near[gig["pickup"]]
        return sum(1 for other in self.gigs.values() if other["status"] == "open" and other is not gig and other["pickup"] in places)

    def do_slice(self, arg) -> None:
        """One slice of an open gig's time: whether a driver books it in the slice, and when."""
        gid, version = arg
        gig = self.gigs[gid]
        if gig["status"] != "open" or gig["version"] != version:
            return
        now = self.now
        steps = [s["at"] for s in gig["schedule"]]
        horizon = min(ENDS_AT, gig["expires"] if gig["expires"] is not None else ENDS_AT)
        cuts = model.edges(now, gig["opened"], _max(now + 1, min(horizon, now + 12 * HOUR)), steps)
        end = cuts[1] if len(cuts) > 1 else min(horizon, now + 12 * HOUR)
        if end <= now:
            return
        if gig["latest"] is not None and now + 30 > gig["latest"]:
            return  # no driver can still reach every stop inside its window: the gig waits for its end
        fee = model.fee_at(gig["schedule"], now)
        top = _max(s["feeCents"] for s in gig["schedule"])
        x = model.features(gig["static"], now, gig["opened"], gig["first"], fee, top, gig["ref"], gig["last"], gig["ready"], gig["reopened"], gig["reposted"],
                           self.crowd(gig), now // DAY in self.base["wave"])
        rate = math.exp(_max(-30.0, min(3.0, self.offset + self.anchor.get(now // DAY, self.anchor.get("week", 0.0)) + sum(b * v for b, v in zip(self.beta, x) if v))))
        if gig["latest"] is not None:
            end = min(end, _max(now + 1, gig["latest"] - 30))
        wait = gig["rng"].expovariate(rate)
        if wait < end - now:
            self.at(now + 1 + int(wait), "book", (gid, version, None, None))
        else:
            self.at(end, "slice", (gid, version))

    def pick_driver(self, gig: dict) -> str:
        """A driver for a booking in the app, by where the bookers of played weeks lived against the car's two ends."""
        r, shares = gig["rng"], self.w["who"]["booked"]
        classes = collections.defaultdict(list)
        for d in self.roster_:
            if d["id"] in gig["gave_back"] or self.busy.get(d["id"], 0) > self.now:
                continue
            if gig["audience"]["experienced"] and not (d["rating"] >= 4.8 and d["completedGigs"] >= 50):
                continue
            if gig["audience"]["manualLicence"] and d["licence"] != "manual":
                continue
            classes[fit.home_class(d["homePlaceId"], gig["pickup"], gig["delivery"], self.near)].append(d["id"])
        names = [c for c in classes if shares.get(c)]
        if not names:
            return r.choice([d["id"] for d in self.roster_])
        cls = r.choices(names, weights=[shares[c] for c in names])[0]
        return r.choice(classes[cls])

    def do_book(self, arg) -> None:
        gid, version, driver, fee = arg
        gig = self.gigs[gid]
        if gig["status"] != "open" or gig["version"] != version:
            return
        if gig["latest"] is not None and self.now + 30 > gig["latest"] and driver is None:
            return
        r = gig["rng"]
        if driver is None:
            driver = self.pick_driver(gig)
            fee = model.fee_at(gig["schedule"], self.now)
            self.publish("gig_viewed", gigId=gid, driverId=driver)
        gig.update(status="booked", driverId=driver, feeCents=fee, bookedAt=self.now)
        gig["version"] += 1
        self.publish("gig_booked", gigId=gid, driverId=driver, feeCents=fee)
        # When the driver collects the first car: a share of the time they have, as the bookers of played weeks used theirs.
        earliest = _max(self.now + 30, gig["ready"])
        latest = gig["latest"]
        leads = self.w["leads"]
        if latest is not None and latest > earliest:
            share = r.choice(leads.get(fit.lead_band((latest - earliest) / HOUR)) or [0.5])
            pickup = int(earliest + _max(0.0, min(1.0, share)) * (latest - earliest))
        else:
            pickup = int(earliest + _max(0, r.choice(leads.get("0") or [30])))
            pickup = next_open(self.orders[gig["cars"][0][0]]["legs"][gig["cars"][0][1]]["pickup"].get("hours"), pickup)
        start = _max(self.now + 1, pickup - 30)
        # Whether the driver gives the gig back before they leave, and when.
        ratio = fee / gig["ref"]
        band = "low" if ratio < 1.05 else "mid" if ratio < 1.3 else "high"
        drops, scale, drop_at = self.w["drops"], self.d["drops"], None
        if r.random() < drops["first hour"][band] * scale:
            drop_at = self.now + 1 + int(r.random() * 58)
        for t in range(self.now + HOUR, start, HOUR):
            if drop_at is None and 7 <= t % DAY // HOUR < 23 and r.random() < drops["hour"][band] * scale:
                drop_at = t + int(r.random() * HOUR)
        for day in range(self.now // DAY + 1, start // DAY + 1):
            due = day == pickup // DAY
            if day in self.base["wave"]:
                dropped, held = self.base["wave"][day]
                own = (dropped + 2.0) / (held + 8.0)
                share = (self.d["wave_own"] * own + (1 - self.d["wave_own"]) * drops["wave night due"][band]) * self.d["wave"] if due else drops["wave night ahead"][band]
            else:
                share = drops["night due" if due else "night ahead"][band] * scale
            if r.random() < share:
                at = day * DAY + int(r.random() * HOUR)
                drop_at = at if drop_at is None else min(drop_at, at)
        if drop_at is not None and drop_at < start:
            self.at(drop_at, "drop", (gid, gig["version"]))
        else:
            self.busy[driver] = pickup + sum(self.minutes[lane] for lane in gig["lanes"])
            self.at(start, "start", (gid, gig["version"], pickup))

    def do_drop(self, arg) -> None:
        gid, version = arg
        gig = self.gigs[gid]
        if gig["status"] != "booked" or gig["version"] != version:
            return
        driver = gig["driverId"]
        gig["gave_back"].add(driver)
        gig.update(status="open", driverId=None, opened=self.now, reopened=True)
        self.publish("gig_dropped", gigId=gid, driverId=driver)
        for oid in dict.fromkeys(o for o, _ in gig["cars"]):
            order = self.orders[oid]
            if self.now >= order["lastPickupAt"] - 3 * HOUR:
                self.publish("deadline_close", orderId=oid, lastPickupAt=order["lastPickupAt"])
        self.open(gig)

    def do_start(self, arg) -> None:
        gid, version, pickup = arg
        gig = self.gigs[gid]
        if gig["status"] != "booked" or gig["version"] != version:
            return
        gig["status"] = "working"
        self.publish("gig_started", gigId=gid, driverId=gig["driverId"])
        at, r = _max(pickup, self.now), gig["rng"]
        for n, (oid, leg) in enumerate(gig["cars"]):
            if n:
                at += self.minutes[(gig["lanes"][n - 1][1], gig["lanes"][n][0])]
            self.at(at, "pickup", (gid, oid, leg))
            at += _max(1, int(self.minutes[gig["lanes"][n]] * r.choice(self.w["drives"])))
            self.at(at, "deliver", (gid, oid, leg, n == len(gig["cars"]) - 1))

    def do_pickup(self, arg) -> None:
        gid, oid, leg = arg
        self.state[oid]["picked"][leg] = self.now
        self.publish("picked_up", gigId=gid, orderId=oid, leg=leg, placeId=self.orders[oid]["legs"][leg]["pickup"]["placeId"])

    def do_deliver(self, arg) -> None:
        gid, oid, leg, last = arg
        gig, order = self.gigs[gid], self.orders[oid]
        order["deliveredAt"][leg] = self.now
        self.publish("delivered", gigId=gid, orderId=oid, leg=leg, placeId=order["legs"][leg]["delivery"]["placeId"])
        if all(at is not None for at in order["deliveredAt"]):
            order["status"] = "delivered"
            self.settle(order)
        if last:
            gig["status"] = "done"
            self.line("driver_fee", -gig["feeCents"], None, gid)

    def settle(self, order: dict) -> None:
        """The price, and the refund of a late order by how late it is (RULES.md, Your account)."""
        price, late = order["priceCents"], _max(order["deliveredAt"]) - order["deadline"]
        self.line("revenue", price, order["id"], None)
        self.revenue += price
        dealer = order["dealerId"]
        if late <= 0:
            self.trust[dealer] = min(25, self.trust[dealer] + 1)
            return
        self.state[order["id"]]["late"] = True
        self.trust[dealer] //= 2
        days = sum(1 for day in range(order["deadline"] // DAY + 1, _max(order["deliveredAt"]) // DAY + 1) if day % 7 < 5)
        share = 0.10 if late <= 2 * HOUR else 0.25 if late <= DAY else 0.5 if days <= 2 else 1.0
        self.line("late_refund", -int(price * share), order["id"], None)

    def line(self, kind: str, cents: int, oid, gid) -> None:
        self.margin += cents
        self.ledger[kind] += cents
        self.publish("ledger", line={"at": self.now, "kind": kind, "cents": cents, "orderId": oid, "gigId": gid, "detail": ""})

    def do_expire(self, gid: str) -> None:
        gig = self.gigs[gid]
        if gig["status"] == "open":
            gig["status"] = "withdrawn"
            gig["version"] += 1
            self.publish("gig_expired", gigId=gid)

    def act_reprice(self, action: dict) -> dict:
        gig = self.gigs.get(action["gigId"])
        if gig is None or gig["status"] != "open":
            return {"ok": False, "reason": f"Gig {action['gigId']} is not open"}
        gig["schedule"] = action["schedule"]
        gig["version"] += 1
        self.at(self.now, "slice", (gig["id"], gig["version"]))
        return {"ok": True}

    def act_withdraw(self, action: dict) -> dict:
        gig = self.gigs.get(action["gigId"])
        if gig is None or gig["status"] != "open":
            return {"ok": False, "reason": f"Gig {action['gigId']} is not open"}
        gig["status"] = "withdrawn"
        gig["version"] += 1
        return {"ok": True}

    def act_release(self, action: dict) -> dict:
        gig = self.gigs.get(action["gigId"])
        if gig is None or gig["status"] != "booked":
            return {"ok": False, "reason": f"Gig {action['gigId']} has no driver to release"}
        hours = (gig["ready"] - self.now) / HOUR
        self.line("release_fee", -int(gig["feeCents"] * (0.25 if hours > 24 else 0.5 if hours > 2 else 1.0)), None, gig["id"])
        gig["status"] = "withdrawn"
        gig["version"] += 1
        return {"ok": True}

    def act_offer(self, action: dict) -> dict:
        gig = self.gigs.get(action["gigId"])
        if gig is None or gig["status"] != "open":
            return {"ok": False, "reason": f"Gig {action['gigId']} is not open"}
        driver, day = action["driverId"], self.now // DAY
        if driver not in self.home:
            return {"ok": False, "reason": f"No driver {driver}"}
        if self.offers_day[(driver, day)] >= 3:
            return {"ok": False, "reason": f"Driver {driver} has had three direct offers today"}
        if sum(1 for until in gig["offers"].values() if until > self.now) >= 3:
            return {"ok": False, "reason": f"Gig {gig['id']} has three open direct offers"}
        self.offers_day[(driver, day)] += 1
        gig["offers"][driver] = self.now + 10
        r, hour = gig["rng"], self.now % DAY // HOUR
        cls = fit.home_class(self.home[driver], gig["pickup"], gig["delivery"], self.near)
        band = fit.offer_band(action["feeCents"] / gig["ref"])
        n, share = self.w["offers"].get(f"{cls}|{band}", [0, 0.0])
        if n < 200:
            n, share = self.w["offers"].get(f"all|{band}", [0, 0.005])
        free = self.busy.get(driver, 0) <= self.now and driver not in gig["gave_back"] and not (gig["latest"] is not None and self.now + 40 > gig["latest"])
        if 7 <= hour < 23 and free and r.random() < share:
            self.at(self.now + 1 + int(r.random() * 8), "offer_yes", (gig["id"], gig["version"], driver, action["feeCents"]))
        else:
            self.at(self.now + 10, "offer_no", (gig["id"], driver, "declined" if r.random() < 0.3 else "expired"))
        return {"ok": True}

    def do_offer_yes(self, arg) -> None:
        gid, version, driver, fee = arg
        gig = self.gigs[gid]
        if gig["status"] != "open" or gig["version"] != version:
            self.at(_max(self.now, gig["offers"].get(driver, self.now)), "offer_no", (gid, driver, "expired"))
            return
        self.publish("gig_viewed", gigId=gid, driverId=driver)
        self.publish("offer_answered", gigId=gid, driverId=driver, answer="accepted")
        self.do_book((gid, version, driver, fee))

    def do_offer_no(self, arg) -> None:
        gid, driver, answer = arg
        self.publish("offer_answered", gigId=gid, driverId=driver, answer=answer)

    # The end.

    def finish(self) -> None:
        if getattr(self, "finished", False):
            return
        self.finished = True
        for order in self.orders.values():
            if any(at is None for at in order["deliveredAt"]):
                self.state[order["id"]]["late"] = True
                self.line("undelivered_penalty", -2 * order["priceCents"], order["id"], None)

    def score(self) -> dict:
        won = len(self.orders)
        late = sum(1 for oid, o in self.orders.items() if self.state[oid]["late"] or any((self.now if at is None else at) > o["deadline"] for at in o["deliveredAt"]))
        undelivered = sum(1 for o in self.orders.values() if any(at is None for at in o["deliveredAt"]))
        on_time = 1 - late / won if won else None
        return {"marginCents": self.margin, "revenueCents": self.revenue, "marginShare": self.margin / self.revenue if self.revenue else 0, "wonOrders": won,
                "onTimeShare": on_time, "undeliveredShare": undelivered / won if won and self.now >= ENDS_AT else 0, "ranked": bool(won) and on_time >= 0.9}

    def reveal(self) -> dict:
        return {"requests": [{"request": r, "quote": self.quotes.get(r["id"]), "outcome": self.outcomes.get(r["id"], ("unquoted", None))[0],
                              "option": self.outcomes.get(r["id"], ("unquoted", None))[1]} for r in self.world["requests"]],
                "orders": [{"orderId": oid, "legs": [{"pickedUpAt": st["picked"][n], "deliveredAt": self.orders[oid]["deliveredAt"][n]} for n in range(len(st["picked"]))]}
                           for oid, st in self.state.items()], "views": []}

