"""The live mode: plays the team's copy of the final, or of a test final, from the live stream with the
reference policy `steep-notes-offers-8`.

    uv run python -m spreadlab.live final                       # waits for the final or test final that is set, plays it to its end
    uv run python -m spreadlab.live rehearse --seed fresh-041   # a practice world whose clock moves like the final's
    uv run python -m spreadlab.live report <world id>           # the evidence of a run: quotes in time, fallbacks, restarts, score by day

In the final the clock moves by itself and `advance` is closed (API.md, The final). A request gives 15 world
minutes, 4.5 real seconds in the day. The desk reads the WebSocket stream, answers each event with the policy and
sends the actions at once, quotes first. The live clock adds three things to the policy:

- A guard thread quotes a safe price for a request that the policy has not answered when a third of its time is
  left: while the desk is busy, blocked on the network, or failed on the request.
- The desk's books go to disk after its actions. A desk that starts again, after a crash or a restart of the machine
  or of Bahn's server, loads them, reads the events it missed, takes the gigs and orders from the world's snapshot,
  posts the cars that have no gig and quotes the open requests. The world holds the won orders and the driver
  bookings; the books hold what the policy has learned: the day's answers, the dealers' orders on time, who uses the
  app today, the offers sent.
- Every event, action, answer and fallback goes to a log with the real time, for the jury.

The files go to data/live/<world id>/: state.pickle (the books), log.jsonl (the evidence), end.json (score and reveal).
The desk acts only on the final that `GET /v1/final` names, or on a practice world that is not a ranking run.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import pickle
import queue
import signal
import statistics
import subprocess
import sys
import threading
import time
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from spread.client import Client, SpreadError, Unreachable, World
from spread.starter import DAY, HOUR, WEEKDAYS, pickups, undelivered

from . import notes
from .policy import DECLINE, Policy
from .server import SERVER, PracticeClient, data_dir, world_map
from .variants import VARIANTS

VARIANT = "steep-notes-offers-8"
# A safe quote when the policy cannot answer in time: no same_day, no trade-in, no private address, and the higher of
# 1.9 x the typical fee and 1.5 x the list price. That is the price of `floor-1.9` in the first sweeps, which won few
# cars, paid on each, and was 96% on time (README, "Results so far"). It declines while the backlog gate is shut.
FALLBACK_FEE, FALLBACK_LIST = 1.9, 1.5
GUARD_SHARE, GUARD_MIN, GUARD_MAX = 1 / 3, 0.2, 1.5  # the guard quotes when this share of a request's time is left, in seconds
LATE = 0.05  # seconds: a quote that would reach the world later than this before its deadline is not sent
POLL, SAVE, SCORE = 1.0, 1.0, HOUR  # seconds between reads of the events that the stream may have missed, between saves; world minutes between scores


def seconds_per_minute(minute: float) -> float:
    """Real seconds per world minute on the final's clock (API.md, The final): an hour takes 18 seconds from 06:00 to
    22:00 on weekdays, 6 on Saturday, 9 on the last Monday, and 3 at night, on Sunday and after the last Monday."""
    day, hour = int(minute // DAY), minute % DAY / HOUR
    per_hour = (18 if day < 5 else 6 if day == 5 else 9 if day == 7 else 3) if 6 <= hour < 22 and day <= 7 else 3
    return per_hour / HOUR


class Clock:
    """The world minute at a real time: the last minute seen, run on at the final's speed. `speed` runs a rehearsal faster.
    A minute seen is a lower bound: the world is somewhere inside it."""

    def __init__(self, minute: float = 0, speed: float = 1.0):
        self.speed, self.lock = speed, threading.Lock()
        self.minute, self.at = float(minute), time.monotonic()
        self.hold = 0.0  # the monotonic time at which the world's clock starts to move: the final stands still until its start

    def start_at(self, wall: float) -> None:
        """The world's clock moves from this wall-clock time (epoch seconds) on."""
        self.hold = time.monotonic() + wall - time.time()

    def now(self, at: Optional[float] = None) -> float:
        at = time.monotonic() if at is None else at
        with self.lock:
            minute, left = self.minute, at - max(self.at, self.hold)
        while left > 0:  # hour by hour, because the speed changes on the hour
            per, hour = seconds_per_minute(minute) / self.speed, (minute // HOUR + 1) * HOUR
            rest = (hour - minute) * per
            if left < rest:
                return minute + left / per
            minute, left = hour, left - rest
        return minute

    def saw(self, minute: int, exact: bool = False) -> None:
        """The world has reached `minute`. `exact` is the world's own clock, which also moves the estimate back."""
        at = time.monotonic()
        estimate = self.now(at)
        with self.lock:
            if estimate < minute:
                self.minute, self.at = float(minute), at
            elif exact and estimate >= minute + 1:
                self.minute, self.at = minute + 0.99, at

    def seconds_until(self, minute: float) -> float:
        """Real seconds until the world reaches `minute`; below 0 once it has."""
        now = self.now()
        if minute <= now:
            return (minute - now) * seconds_per_minute(now) / self.speed
        total = max(0.0, self.hold - time.monotonic())
        while now < minute:
            step = min(minute, (now // HOUR + 1) * HOUR)
            total += (step - now) * seconds_per_minute(now) / self.speed
            now = step
        return total


class Log:
    """The evidence: one JSON line for each event, action, answer and decision, with the wall-clock time."""

    def __init__(self, path: Path, echo: bool = True):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file, self.lock, self.echo = open(path, "a", encoding="utf-8", buffering=1), threading.Lock(), echo

    def write(self, kind: str, **fields) -> None:
        line = json.dumps({"wall": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "kind": kind, **fields}, ensure_ascii=False)
        with self.lock:
            self.file.write(line + "\n")

    def say(self, text: str) -> None:
        self.write("say", text=text)
        if self.echo:
            print(text, flush=True)


def fallback_prices(request: dict) -> dict[str, int]:
    legs, first = request["legs"], request["options"][0]
    options = [o for o in request["options"] if o["kind"] != "same_day"]
    if len(legs) > 1 or not options or any(leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"] for leg in legs):
        return {first["kind"]: first["listPriceCents"] * DECLINE}
    fee = request["referenceFeeCents"]
    return {o["kind"]: int(round(max(o["listPriceCents"] * FALLBACK_LIST, fee * FALLBACK_FEE))) for o in options}


def declined(request: dict) -> dict[str, int]:
    first = request["options"][0]
    return {first["kind"]: first["listPriceCents"] * DECLINE}


class Guard(threading.Thread):
    """Quotes the fallback price for each request that the desk has not sent a quote for when a third of its time is left.
    It has its own connection, so a desk that waits on the network or on the rate limit does not hold it up."""

    def __init__(self, act: Callable[[list], list], clock: Clock, log: Log, max_unbooked: int):
        super().__init__(daemon=True, name="guard")
        self.act, self.clock, self.log, self.max_unbooked = act, clock, log, max_unbooked
        self.lock, self.stopped = threading.Lock(), threading.Event()
        self.pending: dict[str, dict] = {}  # request id -> {"request", "fire": monotonic time, "state": waiting, desk or fallback}
        self.fired: set[str] = set()  # the requests whose fallback the world accepted
        self.backlog = 0  # the won cars without a driver, as the desk last counted them

    def add(self, request: dict) -> None:
        left = self.clock.seconds_until(request["respondBy"])
        margin = min(GUARD_MAX, max(GUARD_MIN, left * GUARD_SHARE))
        with self.lock:
            self.pending.setdefault(request["id"], {"request": request, "fire": time.monotonic() + left - margin, "state": "waiting"})

    def claim(self, request_ids: list[str]) -> None:
        """The desk sends its quotes for these requests now. While the guard sends a fallback, this waits for it, so
        the desk's quote reaches the world after the fallback and replaces it."""
        with self.lock:
            for request_id in request_ids:
                entry = self.pending.get(request_id)
                if entry is not None and entry["state"] == "waiting":
                    entry["state"] = "desk"

    def run(self) -> None:
        while not self.stopped.wait(0.05):
            now, due = time.monotonic(), []
            with self.lock:
                for id_, entry in list(self.pending.items()):
                    if entry["state"] == "waiting" and now >= entry["fire"]:
                        entry["state"] = "fallback"
                        due.append(entry["request"])
                    elif now > entry["fire"] + 60:
                        del self.pending[id_]
                if due:
                    self.quote(due)

    def quote(self, requests: list[dict]) -> None:
        shut = self.backlog >= self.max_unbooked > 0
        actions = [{"type": "quote", "requestId": r["id"], "prices": declined(r) if shut else fallback_prices(r)} for r in requests]
        started = time.monotonic()
        try:
            results = self.act(actions)
        except Exception as error:  # the desk's next join quotes the open requests again
            self.log.write("fallback_failed", requests=[r["id"] for r in requests], error=str(error))
            return
        took = round(time.monotonic() - started, 3)
        for request, action, result in zip(requests, actions, results):
            self.log.write("fallback", requestId=request["id"], prices=action["prices"], ok=result["ok"], reason=result.get("reason"),
                           left=round(self.clock.seconds_until(request["respondBy"]), 3), took=took)
            if result["ok"]:
                self.fired.add(request["id"])
        self.log.say(f"Fallback quote for {', '.join(r['id'] for r in requests)}: the desk had not answered with a third of the time left.")


class LiveDesk(Policy):
    """The policy on the live stream: it takes each event once, sends its actions at once, and can be put on disk."""

    RUNTIME = ("world", "log", "guard", "clock")  # not on disk: the connection, the log, the guard thread and the clock

    def __init__(self, world, level: int, now: int, params: dict, roster: list[dict], map_: dict):
        super().__init__(world, level, now, params, roster, map_)
        self.world_id = world.id
        self.seq = -1  # the last event taken
        self.offline = False  # while it reads the events it missed: it learns from them and sends nothing
        self.quoted: set[str] = set()  # the requests whose policy quote the world accepted
        self.failed: dict[str, dict[int, str]] = {}  # order id -> leg -> the reason of its last failed visit
        self.log = self.guard = self.clock = None

    def __getstate__(self) -> dict:
        return {k: v for k, v in vars(self).items() if k not in self.RUNTIME}

    def __setstate__(self, state: dict) -> None:
        vars(self).update(state)
        for k in self.RUNTIME:
            setattr(self, k, None)

    def attach(self, world, log: Log, guard: Guard, clock: Clock) -> None:
        self.world, self.log, self.guard, self.clock = world, log, guard, clock

    def take(self, event: dict) -> None:
        """Answers one event, once: the stream and the reads of missed events can bring it twice."""
        if event["seq"] <= self.seq:
            return
        self.seq, self.now, kind = event["seq"], max(self.now, event["at"]), event["kind"]
        started = time.monotonic()
        self.log.write("event", replayed=self.offline, lag=round(self.clock.now() - event["at"], 2), event=event)
        if kind == "visit_failed":
            self.failed.setdefault(event["orderId"], {})[event["leg"]] = event["reason"]
        request = event.get("request") if kind == "price_request" else None
        try:
            self.handle(event)
            if request is not None and self.offline and request["id"] not in self.quoted:
                # A request that it missed got no quote of the desk: its answer says nothing about the desk's prices today.
                self.asked.pop(request["id"], None)
                self.asked_at.pop(request["id"], None)
        except Exception:  # a failure on one event must not stop the desk
            self.log.write("error", seq=event["seq"], eventKind=kind, trace=traceback.format_exc(limit=6))
            self.log.say(f"Error on {kind} {event['seq']}; see the log. The desk goes on.")
            if request is not None and not any(a.get("requestId") == request["id"] for a in self.outbox):
                self.outbox.append({"type": "quote", "requestId": request["id"], "prices": fallback_prices(request)})
        if self.offline:
            return
        if request is not None and request["id"] in self.decisions:
            day, place = request["arrivedAt"] // DAY, request["legs"][0]["pickup"]["placeId"]
            decision = self.decisions[request["id"]]
            self.log.write("decision", requestId=request["id"], declined=decision["declined"], prices=decision["prices"],
                           shift=round(self.shift(day, self.params(), place), 4), answersToday=len(self.today[1]) if self.today[0] == day else 0,
                           unbooked=self.unbooked(), ms=round((time.monotonic() - started) * 1000, 2))
        elif kind == "order_won" and event["order"]["id"] in self.orders:
            facts = notes.read(self.requests[event["order"]["id"]]["note"], self.requests[event["order"]["id"]]["arrivedAt"])
            if facts != notes.Facts():
                self.log.write("note", orderId=event["order"]["id"], pickupFrom=facts.pickup_from, plates=facts.plates, manual=facts.manual)

    def send(self) -> None:
        """Sends the outbox now, quotes first. A quote that cannot reach the world before its deadline stays home."""
        if self.offline or not self.outbox:
            return
        actions, self.outbox, keep = self.outbox, [], []
        for action in sorted(actions, key=lambda a: a["type"] != "quote"):
            if action["type"] == "quote":
                left = self.clock.seconds_until(self.requests[action["requestId"]]["respondBy"])
                if left < LATE:
                    self.log.write("quote_late", requestId=action["requestId"], left=round(left, 3))
                    self.asked.pop(action["requestId"], None)  # the answer is not to this price: it does not count in the day's correction
                    continue
            keep.append(action)
        if not keep:
            return
        self.guard.claim([action["requestId"] for action in keep if action["type"] == "quote"])
        started = time.monotonic()
        try:
            results = self.world.act(keep)
        except SpreadError as error:
            if isinstance(error, Unreachable) or error.status not in (0, 400):
                raise  # the next join reads the world and sends again what is still needed
            results = self.one_by_one(keep)  # one action the world cannot parse must not hold up the others
        took = round(time.monotonic() - started, 3)
        for action, result in zip(keep, results):
            fields = {"left": round(self.clock.seconds_until(self.requests[action["requestId"]]["respondBy"]), 3)} if action["type"] == "quote" else {}
            self.log.write("action", action=action, ok=result["ok"], id=result.get("id"), reason=result.get("reason"), took=took, **fields)
        self.read_results(keep, results)

    def one_by_one(self, actions: list) -> list:
        results = []
        for action in actions:
            try:
                results += self.world.act([action])
            except SpreadError as error:
                if isinstance(error, Unreachable) or error.status not in (0, 400):
                    raise
                results.append({"ok": False, "reason": f"not sent: {error}"})
        return results

    def read_results(self, actions, results) -> None:
        super().read_results(actions, results)
        for action, result in zip(actions, results):
            if action["type"] == "quote" and result["ok"]:
                self.quoted.add(action["requestId"])

    def catch_up(self, events: list[dict]) -> tuple[dict[str, int], dict[str, int]]:
        """Learns from the events that it missed, without acting on them: `reconcile` then acts on what the world
        is now. Returns the orders that changed and the gigs that were dropped meanwhile, with the minute of the last time."""
        changed, dropped = {}, {}
        self.offline = True
        try:
            for event in events:
                self.take(event)
                if event["kind"] == "order_changed":
                    changed[event["order"]["id"]] = event["at"]
                elif event["kind"] == "gig_dropped":
                    dropped[event["gigId"]] = event["at"]
        finally:
            self.offline, self.outbox = False, []
        return changed, dropped

    def adopt(self, snapshot: dict) -> None:
        """Takes the gigs and the orders from the world, which keeps them while the desk is away."""
        self.now = max(self.now, snapshot["now"])
        self.leg_gigs = {}
        self.booked = {gig["id"] for gig in snapshot["gigs"] if gig["status"] in ("booked", "working", "done")}
        for gig in snapshot["gigs"]:
            if gig["status"] in ("open", "booked", "working"):
                self.carry({"type": "post", "stops": gig["stops"], "audience": gig["audience"], "schedule": gig["schedule"]}, gig["id"])
                self.opened.setdefault(gig["id"], gig["postedAt"])
                self.fees[gig["id"]] = gig["schedule"]
        for order in snapshot["orders"]:
            if order["status"] == "cancelled":
                self.orders.pop(order["id"], None)
                self.leg_gigs.pop(order["id"], None)
            elif order["id"] in self.requests:
                self.orders[order["id"]] = order
                self.won_at.setdefault(order["id"], self.now)

    def reconcile(self, snapshot: dict, changed: dict[str, int], dropped: dict[str, int]) -> None:
        """Does what the missed events asked for and the desk has not done yet, against the world as it is now, and
        sends it. Each order and request is done on its own: one that fails must not keep the desk from the others."""
        live = [gig for gig in snapshot["gigs"] if gig["status"] in ("open", "booked", "working")]
        for order_id, at in changed.items():
            # A change is done when the order has a gig posted since: the desk took the old gig off and posted the new places.
            done = any(gig["postedAt"] >= at for gig in live if any(stop["orderId"] == order_id for stop in gig["stops"]))
            if order_id in self.orders and undelivered(self.orders[order_id]) and not done:
                self.safely("change", order_id, self.change, self.orders[order_id])
        if self.p["drop_fee"]:
            for gig in live:  # the fees start again after a drop, unless they did already
                if gig["status"] == "open" and gig["id"] in dropped and gig["schedule"][0]["at"] < dropped[gig["id"]]:
                    self.safely("reopen", gig["id"], self.reopen, gig["id"])
        posting = {(s["orderId"], s["leg"]) for a in self.outbox if a["type"] == "post" for s in a["stops"]}
        for order_id, order in list(self.orders.items()):
            legs = [leg for leg in undelivered(order) if leg not in self.leg_gigs.get(order_id, {}) and (order_id, leg) not in posting]
            failed = self.failed.get(order_id, {})
            for leg in legs:
                if leg in failed:
                    self.safely("retry", order_id, self.retry, order_id, leg, failed[leg])
            rest = [leg for leg in legs if leg not in failed]
            if rest:
                self.safely("post", order_id, self.post, order, rest)
        for order_id in self.urgent & set(self.orders):  # the steep fees of a deadline warning that came while the desk was away
            self.safely("steep", order_id, self.steepen, order_id)
        # The desk answers each open request. The guard does not replace a quote that the desk sent before it stopped.
        self.guard.claim([request["id"] for request in snapshot["openRequests"] if request["id"] in self.quoted])
        for request in snapshot["openRequests"]:
            if request["id"] not in self.quoted:
                self.safely("quote", request["id"], self.quote, request)
                if not any(a.get("requestId") == request["id"] for a in self.outbox):
                    self.outbox.append({"type": "quote", "requestId": request["id"], "prices": fallback_prices(request)})
        self.send()

    def steepen(self, order_id: str) -> None:
        for gig_id in self.gigs_of(order_id):
            if gig_id not in self.booked and gig_id in self.posts:
                steep_now = self.fees_for(self.orders[order_id], pickups(self.posts[gig_id]))
                if max(step["feeCents"] for step in self.fees.get(gig_id, [{"feeCents": 0}])) < steep_now[0]["feeCents"]:
                    self.outbox.append({"type": "reprice", "gigId": gig_id, "schedule": steep_now})

    def safely(self, what: str, about: str, fn, *args) -> None:
        try:
            fn(*args)
        except Exception:
            self.log.write("error", where=what, about=about, trace=traceback.format_exc(limit=6))
            self.log.say(f"Error on {what} {about}; see the log. The desk goes on.")


class Store:
    """The desk's books on disk, written whole and then moved into place, so a reader never sees half of them."""

    def __init__(self, folder: Path):
        self.path = folder / "state.pickle"

    def load(self, world_id: str) -> Optional[LiveDesk]:
        if not self.path.exists():
            return None
        with open(self.path, "rb") as f:
            desk = pickle.load(f)
        return desk if getattr(desk, "world_id", None) == world_id else None

    def save(self, desk: LiveDesk) -> None:
        partial = self.path.with_suffix(".part")
        with open(partial, "wb") as f:
            pickle.dump(desk, f, protocol=pickle.HIGHEST_PROTOCOL)
            f.flush()
            os.fsync(f.fileno())
        partial.replace(self.path)


class Live:
    """One desk on one world. `run` plays to the world's end and raises on a lost connection; calling it again,
    or starting the program again, goes on from the books on disk."""

    def __init__(self, world, guard_act: Callable[[list], list], minute_now: Callable[[], int], level: int, params: dict,
                 map_: dict, folder: Path, speed: float = 1.0, echo: bool = True):
        self.world, self.minute_now, self.level, self.params, self.map = world, minute_now, level, params, map_
        self.folder, self.store, self.log = folder, Store(folder), Log(folder / "log.jsonl", echo)
        self.clock = Clock(speed=speed)
        self.guard = Guard(guard_act, self.clock, self.log, params.get("max_unbooked", 0))
        self.guard.start()
        self.desk: Optional[LiveDesk] = None
        self.generation = 0  # a stream reader of an earlier generation stops
        self.ends_at = None

    def join(self) -> None:
        """Rebuilds the books: from memory, else from disk, else from the world's whole history."""
        first = self.world.snapshot()
        self.clock.saw(first["now"], exact=True)
        self.ends_at = first["endsAt"]
        for request in first["openRequests"]:
            self.guard.add(request)
        source = "memory" if self.desk is not None else "disk"
        if self.desk is None:
            self.desk = self.store.load(self.world.id)
        if self.desk is None:
            source = "world"
            self.desk = LiveDesk(self.world, self.level, first["now"], self.params, self.world.roster(), self.map)
        self.desk.attach(self.world, self.log, self.guard, self.clock)
        events = self.world.events(after=self.desk.seq)
        snapshot = self.world.snapshot()
        self.clock.saw(snapshot["now"], exact=True)
        for request in snapshot["openRequests"]:
            self.guard.add(request)
        changed, dropped = self.desk.catch_up(events)
        self.desk.adopt(snapshot)
        self.desk.reconcile(snapshot, changed, dropped)
        self.store.save(self.desk)
        live_gigs = sum(1 for g in snapshot["gigs"] if g["status"] in ("open", "booked", "working"))
        self.log.write("joined", source=source, minute=snapshot["now"], missed=len(events), seq=self.desk.seq, orders=len(self.desk.orders),
                       liveGigs=live_gigs, openRequests=len(snapshot["openRequests"]), level=self.level, params=self.desk.p)
        self.log.say(f"Joined world {self.world.id} at {clock_text(snapshot['now'])} from {source}: {len(events)} events read, "
                     f"{len(self.desk.orders)} orders, {live_gigs} live gigs, {len(snapshot['openRequests'])} open requests.")

    def read(self, out: queue.Queue, after: int, generation: int) -> None:
        """The stream, into the queue. A request goes to the guard as soon as it arrives."""
        try:
            for event in self.world.stream(after=after, idle=0.5):
                if self.generation != generation:
                    return
                if event is None:
                    continue
                self.clock.saw(event["at"])
                if event["kind"] == "price_request":
                    self.guard.add(event["request"])
                out.put(event)
            out.put(ConnectionError("the stream ended"))
        except BaseException as error:
            out.put(error)

    def run(self, stop_at: Optional[int] = None) -> None:
        self.join()
        desk, events = self.desk, queue.Queue()
        self.generation += 1
        threading.Thread(target=self.read, args=(events, desk.seq, self.generation), daemon=True, name="stream").start()
        saved = polled = time.monotonic()
        scored, dirty, look_at = -SCORE, False, desk.now
        try:
            while True:
                batch = []
                try:
                    batch.append(events.get(timeout=0.1))
                    while True:
                        batch.append(events.get_nowait())
                except queue.Empty:
                    pass
                mono = time.monotonic()
                if mono - polled >= POLL:  # the events that a stalled stream has not brought; the desk takes each once
                    polled = mono
                    self.clock.saw(self.minute_now(), exact=True)
                    missed = self.world.events(after=desk.seq)
                    for event in missed:
                        if event["kind"] == "price_request":
                            self.guard.add(event["request"])
                    batch += missed
                woken = False
                for item in batch:
                    if isinstance(item, BaseException):
                        if self.clock.now() >= self.ends_at:
                            break
                        raise item
                    desk.take(item)
                    woken |= item["kind"] in desk.wake_on
                    if item["kind"] == "price_request":  # its quote goes out now: a hold-up later in the batch does not delay it
                        desk.send()
                day = desk.now // DAY
                desk.now = max(desk.now, int(self.clock.now()))
                # The direct offers, when play.py looks: after each event that the desk answers, at midnight, and at the minute
                # that the policy names. That minute is counted from the last look.
                if woken or desk.now >= look_at or desk.now // DAY > day:
                    desk.safely("look", clock_text(desk.now), desk.look)
                    look_at = desk.wake_at()
                dirty |= bool(batch or desk.outbox)
                desk.send()
                self.guard.backlog = desk.unbooked()
                if dirty and time.monotonic() - saved >= SAVE:
                    self.store.save(desk)
                    saved, dirty = time.monotonic(), False
                if desk.now - scored >= SCORE:
                    self.score(desk.now, scored)
                    scored = desk.now // SCORE * SCORE
                if stop_at is not None and desk.now >= stop_at:
                    return
                if desk.now >= self.ends_at:
                    break
        finally:
            self.generation += 1
            self.store.save(desk)
        self.finish()

    def score(self, now: int, before: int) -> None:
        score = self.world.score()
        self.log.write("score", minute=now, score=score)
        if before >= 0 and now // DAY > before // DAY:
            on_time = score.get("onTimeShare")
            self.log.say(f"{WEEKDAYS[before // DAY % 7]:<9}  margin €{score['marginCents'] / 100:>11,.2f}  {score['wonOrders']:>4} orders  "
                         f"{'' if on_time is None else f'{on_time:6.1%} on time'}  fallbacks {len(self.guard.fired)}")

    def finish(self) -> None:
        score = self.world.score()
        reveal = None
        for _ in range(10):  # the final's reveal opens when it has ended
            try:
                reveal = self.world.reveal()
                break
            except (SpreadError, AttributeError):
                time.sleep(3)
        (self.folder / "end.json").write_text(json.dumps({"score": score, "reveal": reveal}, ensure_ascii=False), encoding="utf-8")
        self.log.write("end", score=score)
        self.log.say(f"End: margin €{score['marginCents'] / 100:,.2f}, {score['wonOrders']} orders, "
                     f"{'ranked' if score.get('ranked') else 'not ranked'}, {len(self.guard.fired)} fallback quotes.")

    def stop(self) -> None:
        self.generation += 1
        self.guard.stopped.set()


def clock_text(minute: int) -> str:
    return f"{WEEKDAYS[minute // DAY % 7][:3]} {minute % DAY // HOUR:02d}:{minute % HOUR:02d}"


def folder_of(world_id: str) -> Path:
    return data_dir() / "live" / world_id


def keep_going(live: Live, label: str) -> None:
    """Runs the desk to the world's end through lost connections and server restarts (API.md, Errors: the server
    answers again in under a minute, and every world goes on from where it was). One desk at a time: a second one on
    the same world would post every car again."""
    lock = open(live.folder / "desk.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)  # the kernel lets go when the process ends, also on a kill
    except BlockingIOError:
        live.stop()
        sys.exit(f"Another desk plays world {live.world.id} from {live.folder} on this machine. Stop it first, or let it play.")
    while True:
        try:
            live.run()
            return
        except KeyboardInterrupt:
            live.stop()
            sys.exit(f"Stopped. The {label} keeps running without the desk; the same command goes on from data/live/{live.world.id}.")
        except Exception as error:
            live.log.write("lost", error=repr(error), trace=traceback.format_exc(limit=6))
            live.log.say(f"{error!r}. Joining again in 5 seconds.")
            time.sleep(5)


def wait_for_final(client: Client) -> tuple[World, dict]:
    """The team's copy of the final or test final that is set now and has not ended. The organisers set a test final
    15 minutes before its start, and the final at 07:30."""
    said = False
    while True:
        try:
            final = client.final()
            world = client.world(final["worldId"])
            snapshot = world.snapshot()
            if snapshot["now"] < snapshot["endsAt"]:
                return world, final
        except Unreachable:
            pass
        except SpreadError as error:
            if error.status != 404:
                raise
        if not said:
            print("No final is set, or the last one has ended. Waiting for one; the organisers set a test final 15 minutes "
                  "before its start and the final at 07:30.", flush=True)
            said = True
        time.sleep(10)


def play_final(args) -> None:
    client = Client(url=os.environ.get("SPREAD_URL") or SERVER)
    world, final = wait_for_final(client)
    level = next((w["level"] for w in client.worlds() if w["worldId"] == world.id), 8)
    guard_world = World(Client(url=client.url, key=client.key), world.id)
    live = Live(world, guard_world.act, lambda: client.final()["now"], level, VARIANTS[args.variant], client.map(), folder_of(world.id))
    live.clock.start_at(datetime.fromisoformat(final["startsAt"].replace("Z", "+00:00")).timestamp())
    live.log.say(f"Final world {world.id}, level {level}, starts at {final['startsAt']}; variant {args.variant}. "
                 f"Ctrl-C stops the desk; the world goes on without it.")
    keep_going(live, "final")


def practice_world(client: Client, world_id: str) -> World:
    """A practice world of the team that is not a ranking run: the only other world the desk acts on."""
    summary = next((w for w in client.worlds() if w["worldId"] == world_id), None)
    if summary is None or summary["kind"] != "practice" or summary.get("boardRun") is not None:
        sys.exit(f"{world_id} is not a practice world of this key, or it is a ranking run: the desk plays practice worlds and the final only.")
    return client.world(world_id)


def play_practice(args) -> None:
    client = PracticeClient()
    world = practice_world(client, args.world)
    guard_world = World(PracticeClient(), world.id)
    live = Live(world, guard_world.act, lambda: world.snapshot()["now"], 8, VARIANTS[args.variant], world_map(client), folder_of(world.id), args.speed)
    keep_going(live, "practice world")


def pace(args) -> None:
    """Moves a practice world's clock like the final's: an `advance` every tenth of a second, to the minute the
    final's clock would show. It sends no actions."""
    client = PracticeClient()
    world = practice_world(client, args.world)
    snapshot = world.snapshot()
    minute, ends_at = snapshot["now"], snapshot["endsAt"]
    if args.start > minute:  # a test final starts on Thursday 00:00
        minute = world.advance(to=args.start)["now"]
    clock, mark = Clock(minute, args.speed), folder_of(world.id) / "minute"
    mark.parent.mkdir(parents=True, exist_ok=True)
    mark.write_text(str(minute))
    while minute < ends_at:
        time.sleep(0.1)
        target = min(ends_at, int(clock.now()))
        if target > minute:
            minute = world.advance(to=target)["now"]
            mark.write_text(str(minute))


def rehearse(args) -> None:
    """A practice week on the final's clock: one process moves the clock, another runs the desk, as in the final.
    With --kill-at, the desk is killed at that world minute and started again after --down seconds."""
    client = PracticeClient()
    world = client.create(level=8, seed=args.seed)  # PracticeClient refuses ranking runs
    folder = folder_of(world.id)
    folder.mkdir(parents=True, exist_ok=True)
    print(f"Practice world {world.id}, seed {args.seed}, speed {args.speed}. Files in {folder}.", flush=True)
    here = Path(__file__).resolve().parent.parent
    command = [sys.executable, "-m", "spreadlab.live"]
    desk = command + ["play", world.id, "--speed", str(args.speed), "--variant", args.variant]
    pacer = subprocess.Popen(command + ["pace", world.id, "--speed", str(args.speed), "--start", str(args.start)], cwd=here)
    minute = lambda: int((folder / "minute").read_text() or 0) if (folder / "minute").exists() else 0
    started, killed = [], False
    try:
        while args.start and minute() < args.start and pacer.poll() is None:  # the desk joins as a test final starts, on Thursday 00:00
            time.sleep(0.2)
        started.append(subprocess.Popen(desk, cwd=here))
        while pacer.poll() is None:
            time.sleep(0.5)
            if args.kill_at and not killed and minute() >= args.kill_at:
                started[-1].send_signal(signal.SIGKILL)
                started[-1].wait()
                killed = True
                print(f"Killed the desk at {clock_text(minute())}; starting it again in {args.down} seconds.", flush=True)
                time.sleep(args.down)
                started.append(subprocess.Popen(desk, cwd=here))
            elif started[-1].poll() is not None and pacer.poll() is None:  # as a supervisor would
                print(f"The desk stopped with code {started[-1].returncode} at {clock_text(minute())}; starting it again.", flush=True)
                started.append(subprocess.Popen(desk, cwd=here))
        started[-1].wait(timeout=300)
    except BaseException:
        for process in [pacer, *started]:
            process.kill()
        world.delete()
        raise
    if pacer.returncode != 0:
        sys.exit(f"The pacer stopped with code {pacer.returncode}.")
    print(report(world.id))


def join_text(join: dict) -> str:
    return f"from {join['source']} at {clock_text(join['minute'])}, {join['missed']} events read"


def report(world_id: str) -> str:
    """The evidence of a run from its log: every request and whether a quote reached the world in time."""
    lines = [json.loads(line) for line in open(folder_of(world_id) / "log.jsonl", encoding="utf-8")]
    requests = {l["event"]["request"]["id"]: l["event"]["request"] for l in lines if l["kind"] == "event" and l["event"]["kind"] == "price_request"}
    joins = [l for l in lines if l["kind"] == "joined"]
    live_from = joins[0]["minute"] if joins else 0
    desk_quotes = {l["action"]["requestId"]: l for l in lines if l["kind"] == "action" and l["action"]["type"] == "quote" and l["ok"]}
    fallbacks = {l["requestId"]: l for l in lines if l["kind"] == "fallback" and l["ok"]}
    asked = [r for r in requests.values() if r["respondBy"] > live_from]  # the requests that arrived while the desk could answer
    down, seen = [], live_from  # the world minutes between the last event a desk took and the join of the next one
    for l in lines:
        if l["kind"] == "event" and not l["replayed"]:
            seen = l["event"]["at"]
        elif l["kind"] == "joined" and l is not joins[0]:
            down.append((seen, l["minute"]))
    unanswered = [r for r in asked if r["id"] not in desk_quotes and r["id"] not in fallbacks]
    away = [r["id"] for r in unanswered if any(start <= r["arrivedAt"] <= end for start, end in down)]
    missed = [r["id"] for r in unanswered if r["id"] not in away]
    lead = sorted(l["left"] for l in desk_quotes.values())
    refused = Counter(l["reason"].split(":")[0][:60] for l in lines if l["kind"] == "action" and not l["ok"])
    shifts: dict[int, float] = {}
    for l in lines:
        if l["kind"] == "decision" and l["requestId"] in requests:
            shifts[requests[l["requestId"]]["arrivedAt"] // DAY] = l["shift"]
    end = next((l["score"] for l in reversed(lines) if l["kind"] in ("end", "score")), None)
    out = [f"World {world_id}: {len(asked)} requests while the desk ran, {len(desk_quotes)} quoted by the policy, "
           f"{len(fallbacks)} by the fallback, {len(missed)} missed{' (' + ', '.join(missed[:10]) + ')' if missed else ''}, "
           f"{len(away)} unquoted while the desk was down.",
           f"Seconds left at the policy's quotes: least {lead[0] if lead else '-'}, 5th percentile "
           f"{lead[len(lead) // 20] if lead else '-'}, median {statistics.median(lead) if lead else '-'}.",
           f"Joins: {len(joins)} ({'; '.join(join_text(j) for j in joins)}).",
           f"Errors: {sum(1 for l in lines if l['kind'] == 'error')}. Lost connections: {sum(1 for l in lines if l['kind'] == 'lost')}. "
           f"Quotes held back as late: {sum(1 for l in lines if l['kind'] == 'quote_late')}.",
           f"Refused actions: {sum(refused.values())}" + "".join(f"; {n} x {reason}" for reason, n in refused.most_common(4)) + ".",
           "The day's correction at its last quote: " + ", ".join(f"{WEEKDAYS[d % 7][:3]} {s:+.3f}" for d, s in sorted(shifts.items())) + ".",
           f"Notes read at a win: {sum(1 for l in lines if l['kind'] == 'note')}. Offers sent: "
           f"{sum(1 for l in lines if l['kind'] == 'action' and l['action']['type'] == 'offer' and l['ok'])}."]
    if end:
        on_time = end.get("onTimeShare")
        out.append(f"Score: margin €{end['marginCents'] / 100:,.2f}, {end['wonOrders']} orders"
                   f"{'' if on_time is None else f', {on_time:.1%} on time'}{', ranked' if end.get('ranked') else ''}.")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    final = commands.add_parser("final", help="wait for the final or test final that is set, and play it to its end")
    final.add_argument("--variant", default=VARIANT)
    play = commands.add_parser("play", help="play a practice world that something else moves (rehearse starts it)")
    play.add_argument("world")
    play.add_argument("--speed", type=float, default=1.0)
    play.add_argument("--variant", default=VARIANT)
    pacer = commands.add_parser("pace", help="move a practice world's clock like the final's")
    pacer.add_argument("world")
    pacer.add_argument("--speed", type=float, default=1.0)
    pacer.add_argument("--start", type=int, default=0, help="the minute to start from: 4320 is Thursday 00:00, as in a test final")
    rehearsal = commands.add_parser("rehearse", help="a practice week on the final's clock, with an optional kill and restart of the desk")
    rehearsal.add_argument("--seed", required=True)
    rehearsal.add_argument("--speed", type=float, default=1.0, help="1 is the final's speed; 2 runs twice as fast")
    rehearsal.add_argument("--start", type=int, default=0, help="the minute to start from: 4320 is Thursday 00:00, as in a test final")
    rehearsal.add_argument("--kill-at", type=int, default=0, help="the world minute at which to kill the desk")
    rehearsal.add_argument("--down", type=float, default=20, help="seconds the desk stays down")
    rehearsal.add_argument("--variant", default=VARIANT)
    reporting = commands.add_parser("report", help="the evidence of a run from its log")
    reporting.add_argument("world")
    args = parser.parse_args()
    run = {"final": play_final, "play": play_practice, "pace": pace, "rehearse": rehearse}.get(args.command)
    try:
        run(args) if run else print(report(args.world))
    except SpreadError as error:
        sys.exit(f"spread: {error}")


if __name__ == "__main__":
    main()
