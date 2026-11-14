"""A recorded week played back on the final's clock: a stand-in for Bahn's server, so the live desk (live.py) can be
tested without the team key and without a practice world.

    uv run python -m spreadlab.replay --seed fresh-001                         # the reference's recorded week, at the final's speed
    uv run python -m spreadlab.replay --seed fresh-001 --speed 4 --crash-at 2200 --down 10   # faster, with a crash at Tue 12:40
    uv run python -m spreadlab.replay --seed fresh-001 --start 4320 --slow 0.05  # from Thursday as a test final; 5% of quotes stall

The events are those of the week that `play` recorded for the reference, so the dealers' answers, the bookings and
the drops are those of the recording, whatever the desk does. The stand-in takes the desk's actions as the world would:
it refuses a quote at its response deadline or later, and numbers the gigs in the order they are posted, so a desk
that posts what the recording posted gets the recording's gig ids, and the recorded bookings fall on its gigs.

At the end it compares the desk with the recording: its quote for each request with the recorded one, its gigs
with the recorded gigs, and it counts the requests that got no quote in time and the cars posted twice.
A crash (`--crash-at`) stops the desk in the middle of a batch of actions, after the world has applied them and
before the desk has read the answers: the worst moment. The world goes on, and a new desk starts from the books on disk.
"""
from __future__ import annotations

import argparse
import copy
import shutil
import threading
import time
from collections import Counter
from typing import Iterator, Optional

from spread.client import SpreadError

from .live import Clock, Live, LiveDesk, VARIANT, clock_text, folder_of, report
from .play import load_run
from .server import world_map
from .variants import VARIANTS


class Crash(BaseException):
    """The desk's process dies. A BaseException, so that no handler of the desk takes it for an error to go on from."""


def as_sent(events: list[dict]) -> list[dict]:
    """The events as the world sent them. A recorded run shares the order of `order_won` with the desk's books, which
    filled in its delivery times later: an order is sent with the cars delivered by the event's minute."""
    events, delivered = copy.deepcopy(events), {}
    for event in events:
        if event["kind"] == "delivered":
            delivered[(event["orderId"], event["leg"])] = event["at"]
    for event in events:
        if event["kind"] in ("order_won", "order_changed"):
            order = event["order"]
            order["deliveredAt"] = [at if at is not None and at <= event["at"] and delivered.get((order["id"], leg)) == at else None
                                    for leg, at in enumerate(order["deliveredAt"])]
    return events


class Replay:
    """The world of a recorded week. Its clock moves by itself from `start`, at the final's speed times `speed`."""

    def __init__(self, events: list[dict], roster: list[dict], ends_at: int, start: int = 0, speed: float = 1.0, world_id: str = "replay"):
        self.id, self.all, self.roster_, self.ends_at = world_id, as_sent(events), roster, ends_at
        self.clock, self.lock = Clock(start, speed), threading.Lock()
        self.published = 0  # the events published so far: those at or before the world's minute
        self.orders: dict[str, dict] = {}
        self.gigs: dict[str, dict] = {}
        self.requests: dict[str, dict] = {}
        self.quotes: dict[str, list] = {}  # request id -> [(minute, prices, by whom)] that the world accepted
        self.refused: list[tuple[int, dict, str]] = []
        self.margin = 0
        self.offers: list[tuple[int, str, str]] = []  # (minute, gig id, driver id) of each direct offer sent
        self.crash_next_act = False
        self.withdrawn_at: dict[str, int] = {}  # gig id -> the minute the recorded desk withdrew it, for gigs it posted before the start

    def resume_from(self, gigs: list[dict], start: int) -> None:
        """The recorded gigs posted before `start`, for a desk that joins in the middle of the week without its books:
        the world holds them, and the events published at the first read update them. A gig that the recorded desk
        withdrew has no event for it: it counts as withdrawn from the minute a later gig took one of its cars."""
        ended = {e["gigId"] for e in self.all if e["kind"] == "gig_expired"}
        ended |= {o["gigId"] for e in self.all if e["kind"] == "order_cancelled" for o in e["gigs"]}
        cars = lambda gig: {(stop["orderId"], stop["leg"]) for stop in gig["stops"]}
        for gig in sorted((g for g in gigs if g["postedAt"] < start), key=lambda g: int(g["id"][1:])):
            self.gigs[gig["id"]] = {**gig, "status": "open", "driverId": None}
            if gig["status"] == "withdrawn" and gig["id"] not in ended:
                later = [g["postedAt"] for g in gigs if int(g["id"][1:]) > int(gig["id"][1:]) and cars(g) & cars(gig)]
                if later:
                    self.withdrawn_at[gig["id"]] = min(later)

    def minute(self) -> int:
        return min(self.ends_at, int(self.clock.now()))

    def publish(self) -> None:
        """Publishes the events up to the world's minute and keeps the books of the world from them."""
        now = self.minute()
        while self.published < len(self.all) and self.all[self.published]["at"] <= now:
            event = self.all[self.published]
            self.published += 1
            kind, gig = event["kind"], self.gigs.get(event.get("gigId", ""))
            if kind == "price_request":
                self.requests[event["request"]["id"]] = event["request"]
            elif kind in ("order_won", "order_changed"):
                old = self.orders.get(event["order"]["id"])
                self.orders[event["order"]["id"]] = {**event["order"], "status": "waiting",
                                                     "deliveredAt": old["deliveredAt"] if old else [None] * len(event["order"]["legs"])}
            elif kind == "delivered" and event["orderId"] in self.orders:
                self.orders[event["orderId"]]["deliveredAt"][event["leg"]] = event["at"]
            elif kind == "order_cancelled" and event["orderId"] in self.orders:
                self.orders[event["orderId"]]["status"] = "cancelled"
                for outcome in event["gigs"]:
                    if outcome["gigId"] in self.gigs and outcome["outcome"] in ("withdrawn", "released"):
                        self.gigs[outcome["gigId"]]["status"] = "withdrawn"
            elif kind == "ledger":
                self.margin += event["line"]["cents"]
            if gig is not None:
                if kind == "gig_booked":
                    gig.update(status="booked", driverId=event["driverId"], feeCents=event["feeCents"])
                elif kind in ("gig_dropped", "no_show"):
                    gig.update(status="open", driverId=None)
                elif kind == "gig_started":
                    gig["status"] = "working"
                elif kind == "gig_expired":
                    gig["status"] = "withdrawn"
                elif kind == "delivered" and all(self.orders[s["orderId"]]["deliveredAt"][s["leg"]] is not None
                                                 for s in gig["stops"] if s["orderId"] in self.orders):
                    gig["status"] = "done"
        for gig_id, at in self.withdrawn_at.items():
            if at <= now and self.gigs[gig_id]["status"] == "open":
                self.gigs[gig_id]["status"] = "withdrawn"

    # The routes of a world that the live desk uses.

    def snapshot(self) -> dict:
        with self.lock:
            self.publish()
            now = self.minute()
            return {"worldId": self.id, "now": now, "endsAt": self.ends_at, "driverPositions": [], "score": self.score_now(),
                    "openRequests": [r for r in self.requests.values() if r["respondBy"] > now],
                    "orders": [dict(o, deliveredAt=list(o["deliveredAt"])) for o in self.orders.values()],
                    "gigs": [dict(g) for g in self.gigs.values()]}

    def events(self, after: int = -1, limit: Optional[int] = None) -> list[dict]:
        with self.lock:
            self.publish()
            found = [e for e in self.all[: self.published] if e["seq"] > after]
        return found[:limit] if limit else found

    def stream(self, after: Optional[int] = None, idle: Optional[float] = None) -> Iterator[Optional[dict]]:
        with self.lock:
            self.publish()
            sent = self.published if after is None else next((i for i, e in enumerate(self.all) if e["seq"] > after), len(self.all))
        quiet = time.monotonic()
        while True:
            with self.lock:
                self.publish()
                ready = self.all[sent : self.published]
            for event in ready:
                yield event
            sent += len(ready)
            if ready:
                quiet = time.monotonic()
            elif idle is not None and time.monotonic() - quiet >= idle:
                quiet = time.monotonic()
                yield None
            if sent >= len(self.all) and self.minute() >= self.ends_at:
                return
            time.sleep(0.01)

    def act(self, actions: list[dict], by: str = "desk") -> list[dict]:
        if len(actions) > 50:
            raise SpreadError(400, "at most 50 actions", "")
        with self.lock:
            self.publish()
            now, results = self.minute(), []
            for action in actions:
                results.append(self.apply(action, now, by))
            crash = self.crash_next_act and by == "desk"
            self.crash_next_act &= not crash
        if crash:
            raise Crash()
        return results

    def apply(self, action: dict, now: int, by: str) -> dict:
        kind, gig = action["type"], self.gigs.get(action.get("gigId", ""))
        if kind == "quote":
            request = self.requests.get(action["requestId"])
            if request is None or now >= request["respondBy"]:
                return self.refuse(action, now, f"The response deadline of {action['requestId']} has passed")
            self.quotes.setdefault(request["id"], []).append((now, action["prices"], by))
            return {"ok": True}
        if kind == "post":
            gig_id = f"g{len(self.gigs) + 1}"
            self.gigs[gig_id] = {"id": gig_id, "stops": action["stops"], "audience": action["audience"], "schedule": action["schedule"],
                                 "status": "open", "postedAt": now, "feeCents": action["schedule"][0]["feeCents"], "driverId": None}
            return {"ok": True, "id": gig_id}
        if kind == "offer":
            self.offers.append((now, action["gigId"], action["driverId"]))
        if kind in ("reprice", "withdraw", "offer") and (gig is None or gig["status"] != "open"):
            return self.refuse(action, now, f"Gig {action['gigId']} is not open")
        if kind == "reprice":
            gig["schedule"] = action["schedule"]
        elif kind == "withdraw":
            gig["status"] = "withdrawn"
        return {"ok": True}

    def refuse(self, action: dict, now: int, reason: str) -> dict:
        self.refused.append((now, action, reason))
        return {"ok": False, "reason": reason}

    def guard_act(self, actions: list[dict]) -> list[dict]:
        return self.act(actions, by="fallback")

    def roster(self) -> list[dict]:
        return self.roster_

    def score_now(self) -> dict:
        won = sum(1 for o in self.orders.values() if o["status"] != "cancelled")
        return {"marginCents": self.margin, "revenueCents": 0, "marginShare": 0, "wonOrders": won, "onTimeShare": None, "undeliveredShare": 0, "ranked": False}

    def score(self) -> dict:
        with self.lock:
            self.publish()
            return self.score_now()

    def reveal(self) -> None:
        return None


def slow_quotes(share: float, seconds: float) -> None:
    """Makes the policy stall on a share of the requests, to show the guard's fallback."""
    from .policy import share as fixed_share

    quote = LiveDesk.quote

    def stalled(self, request):
        if not self.offline and fixed_share("slow " + request["id"]) < share:
            time.sleep(seconds)
        return quote(self, request)

    LiveDesk.quote = stalled


def compare(run: dict, replay: Replay, start: int, down: tuple[int, int]) -> list[str]:
    """The desk against the recording."""
    decisions, recorded_gigs = run["decisions"], {g["id"]: g for g in run["gigs"]}
    asked = [r for r in replay.requests.values() if r["arrivedAt"] >= start]
    outage = [r for r in asked if r["respondBy"] > down[0] and r["arrivedAt"] < down[1]]
    answered, same, by_fallback, missed = 0, 0, 0, []
    for request in asked:
        quotes = replay.quotes.get(request["id"])
        if not quotes:
            if request not in outage:
                missed.append(request["id"])
            continue
        answered += 1
        _, prices, by = quotes[-1]
        by_fallback += by == "fallback"
        same += by == "desk" and prices == decisions.get(request["id"], {}).get("prices")
    stops = lambda gig: [(s["orderId"], s["leg"], s["kind"]) for s in gig["stops"]]
    gigs_same = sum(1 for gig_id, gig in replay.gigs.items() if gig_id in recorded_gigs and stops(gig) == stops(recorded_gigs[gig_id]))
    # The whole post: the stops with the windows and plates that the note reader set, and who may drive.
    exact = sum(1 for gig_id, gig in replay.gigs.items() if gig_id in recorded_gigs
                and (gig["stops"], gig["audience"]) == (recorded_gigs[gig_id]["stops"], recorded_gigs[gig_id]["audience"]))
    twice, live = 0, {}
    for gig in replay.gigs.values():  # a car in two gigs that were live at once
        if gig["status"] in ("open", "booked", "working", "done"):
            for stop in gig["stops"]:
                if stop["kind"] == "pickup":
                    live.setdefault((stop["orderId"], stop["leg"]), []).append(gig["id"])
    for key, ids in live.items():
        twice += len([i for i in ids if replay.gigs[i]["status"] != "done"]) > 1
    recorded_offers = Counter((e["gigId"], e["driverId"]) for e in replay.all if e["kind"] == "offer_answered" and e["at"] >= start)
    sent_offers = Counter((gig, driver) for at, gig, driver in replay.offers)
    return [f"Requests from {clock_text(start)}: {len(asked)}; answered in time {answered}; by the fallback {by_fallback}; "
            f"missed while the desk ran {len(missed)}{' ' + str(missed[:8]) if missed else ''}; arrived while it was down {len(outage)}.",
            f"Policy quotes equal to the recording's: {same} of {answered - by_fallback}.",
            f"Gigs: {len(replay.gigs)} posted against {len(recorded_gigs)} recorded; {gigs_same} carry the same cars as the recorded gig of their id, "
            f"{exact} with the same stop windows, plates and audience.",
            f"Direct offers: {sum(sent_offers.values())} sent against {sum(recorded_offers.values())} answered in the recording; "
            f"{sum((sent_offers & recorded_offers).values())} to the same driver for the same gig.",
            f"Cars in two live gigs at once: {twice}. Actions refused: {len(replay.refused)}"
            f" ({', '.join(sorted({r[2].split(' of ')[0].split(' g')[0] for r in replay.refused}))})."]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", required=True, help="a week that `play` recorded for the reference variant")
    parser.add_argument("--speed", type=float, default=1.0, help="1 is the final's speed")
    parser.add_argument("--start", type=int, default=0, help="the minute the clock starts from: 4320 is Thursday 00:00, as in a test final")
    parser.add_argument("--crash-at", type=int, default=0, help="the world minute at which the desk dies in the middle of a batch")
    parser.add_argument("--down", type=float, default=10, help="real seconds the desk stays down")
    parser.add_argument("--slow", type=float, default=0, help="the share of requests on which the policy stalls for 6 seconds, more than a request gives")
    parser.add_argument("--tag", default="", help="a name for this run's folder, data/live/replay-<seed>-<tag>")
    args = parser.parse_args()
    run = load_run(VARIANT, args.seed)
    replay = Replay(run["events"], run["roster"], max(e["at"] for e in run["events"]) + 1, args.start, args.speed, "-".join(filter(None, ["replay", args.seed, args.tag])))
    replay.resume_from(run["gigs"], args.start)
    folder = folder_of(replay.id)
    shutil.rmtree(folder, ignore_errors=True)
    if args.slow:
        slow_quotes(args.slow, 6 / args.speed)

    def desk() -> Live:
        return Live(replay, replay.guard_act, replay.minute, run["level"], VARIANTS[VARIANT], world_map(), folder, args.speed)

    live, down = desk(), (0, 0)
    print(f"Replay of {args.seed} from {clock_text(args.start)} at {args.speed} x the final's speed; files in {folder}.", flush=True)
    if args.crash_at:
        try:
            live.run(stop_at=args.crash_at)
            live.store.save = lambda desk: None  # a process that dies saves nothing more
            replay.crash_next_act = True  # the desk dies inside its next batch of actions
            live.run()
        except Crash:
            live.stop()  # the process is gone: its guard and stream go with it
            died = replay.minute()
            print(f"The desk died at {clock_text(died)}, inside a batch of actions. Down for {args.down} seconds.", flush=True)
            time.sleep(args.down)
            down = (died, replay.minute() + 1)
            live = desk()  # a new process: it knows only the books on disk
    live.run()
    live.stop()
    print(report(replay.id))
    print("\n".join(compare(run, replay, args.start, down)))


if __name__ == "__main__":
    main()
