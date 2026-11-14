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
from spread.starter import DAY, HOUR, WEEKDAYS, Retry, pickups, undelivered

from . import notes, watch
from .late_wide import WideLate
from .pairs import PairPolicy
from .policy import DECLINE, Policy
from .server import SERVER, PracticeClient, data_dir, world_map
from .variants import VARIANTS

VARIANT = "slow-friday-late-150-kinds-limits"
# A safe quote when the policy cannot answer in time: no same_day, no trade-in, no private address, and the higher of
# 1.9 x the typical fee and 1.5 x the list price. That is the price of `floor-1.9` in the first sweeps, which won few
# cars, paid on each, and was 96% on time (README, "Results so far"). It declines while the backlog gate is shut.
FALLBACK_FEE, FALLBACK_LIST = 1.9, 1.5
GUARD_SHARE, GUARD_MIN, GUARD_MAX = 1 / 3, 0.2, 1.5  # the guard quotes when this share of a request's time is left, in seconds
LATE = 0.05  # seconds: a quote that would reach the world later than this before its deadline is not sent
# The first post of a won order with a note waits for the note watcher's answer this long at most, in real seconds and
# in world minutes: a driver often books a gig within a minute or two of its post, and a booked gig cannot be withdrawn.
HOLD_SECONDS, HOLD_MINUTES = 1.5, 5
POLL, SAVE, SCORE = 1.0, 1.0, HOUR  # seconds between reads of the events that the stream may have missed, between saves; world minutes between scores
BEAT = 2.0  # seconds between the desk's heartbeats in the log, which alarm.py watches
FENCE = 5.0  # real seconds: a gig that this desk did not post, posted this long after its books end, is another desk's


class Fenced(BaseException):
    """Another desk plays this world: this one must never act on it again. A BaseException, so that keep_going stops."""


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

    RUNTIME = ("world", "log", "guard", "clock", "watch", "held")  # not on disk: the connection, the log, the guard, the clock, the note watcher, held posts

    def __init__(self, world, level: int, now: int, params: dict, roster: list[dict], map_: dict):
        super().__init__(world, level, now, params, roster, map_)
        self.world_id = world.id
        self.seq = -1  # the last event taken
        self.offline = False  # while it reads the events it missed: it learns from them and sends nothing
        self.quoted: set[str] = set()  # the requests whose policy quote the world accepted
        self.failed: dict[str, dict[int, tuple[str, str, int]]] = {}  # order id -> leg -> its last failed visit: reason, gig, minute
        self.fixes: dict[str, dict] = {}  # order id -> what the note watcher found that the rules missed: pickupFrom, plates, manual
        self.unchecked: set[str] = set()  # won orders whose note the watcher has not answered for
        self.foreign: set[str] = set()  # gigs in the stream that this desk did not post: another desk may be playing
        self.log = self.guard = self.clock = self.watch = None
        self.held: dict[str, dict] = {}  # order id -> its first post, while it waits for the note watcher: legs, retry, since, at

    def __getstate__(self) -> dict:
        return {k: v for k, v in vars(self).items() if k not in self.RUNTIME}

    def __setstate__(self, state: dict) -> None:
        vars(self).update(state)  # what older books lack, Live.join takes from a new desk
        for k in self.RUNTIME:
            setattr(self, k, None)

    def attach(self, world, log: Log, guard: Guard, clock: Clock, watcher: Optional[watch.Watcher] = None) -> None:
        self.world, self.log, self.guard, self.clock, self.watch = world, log, guard, clock, watcher
        self.held = self.held or {}  # a desk that starts again posts what was held, as any car without a gig

    def take(self, event: dict) -> None:
        """Answers one event, once: the stream and the reads of missed events can bring it twice."""
        if event["seq"] <= self.seq:
            return
        self.seq, self.now, kind = event["seq"], max(self.now, event["at"]), event["kind"]
        started = time.monotonic()
        self.log.write("event", replayed=self.offline, lag=round(self.clock.now() - event["at"], 2), event=event)
        if kind == "visit_failed":
            self.failed.setdefault(event["orderId"], {})[event["leg"]] = (event["reason"], event["gigId"], event["at"])
        elif kind == "gig_started":  # a driver who sets out holds the gig, whether or not the desk saw the booking
            self.booked.add(event["gigId"])
        gig_id = event.get("gigId")
        if gig_id and not self.offline and gig_id not in self.posts and gig_id not in self.foreign:
            self.foreign.add(gig_id)  # the world posts no gigs: a person may have started a second desk while this one plays
            self.log.write("foreign_gig", gigId=gig_id, eventKind=kind, at=event["at"])
            self.log.say(f"Warning: {kind} for gig {gig_id}, which this desk did not post. If a second desk plays this world, stop one of them now.")
        request = event.get("request") if kind == "price_request" else None
        if (kind == "order_won" and not self.offline and self.watch is not None and self.watch.verify is not None
                and self.requests.get(event["order"]["id"], {}).get("note") and event["order"]["id"] not in self.orders):
            self.held[event["order"]["id"]] = {"legs": None, "retry": Retry(), "since": time.monotonic(), "at": self.now}
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
        won = event["order"]["id"] if kind == "order_won" and event["order"]["id"] in self.orders else None
        if won and self.watch is not None and self.requests[won]["note"]:
            self.unchecked.add(won)  # checked now, or at the next join for a win that it reads offline
        if self.offline:
            return
        if request is not None and request["note"] and self.watch is not None:
            self.watch.observe(request)
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
            if won in self.unchecked:
                self.watch.check(won, self.requests[won], self.orders[won]["deadline"], facts, self.now)

    def post(self, order, legs, retry: Retry = Retry()) -> None:
        """The policy's post, with what the note watcher found that the rules missed: it only adds plates and a manual
        licence and moves the pickup later. The first post of a won note waits for the watcher in `held`."""
        if order["id"] in self.held:
            self.held[order["id"]].update(legs=legs, retry=retry)
            return
        fix = self.fixes.get(order["id"])
        if fix:
            retry = Retry(max(retry.pickup_from, fix["pickupFrom"]), retry.manual_licence or fix["manual"], retry.plates or fix["plates"])
        super().post(order, legs, retry)

    def correct(self, result: dict) -> None:
        """Applies the watcher's answer on a won note: posts the car again with the safe corrections, unless a driver
        has booked it, when they wait for its next post (a retry after a failed visit, or a change of plan)."""
        order_id = result["orderId"]
        self.unchecked.discard(order_id)
        order, old = self.orders.get(order_id), self.fixes.get(order_id, {"pickupFrom": 0, "plates": False, "manual": False})
        fix = result["fix"]
        new = {"pickupFrom": max(old["pickupFrom"], fix.get("pickupFrom", 0)), "plates": old["plates"] or fix.get("plates", False),
               "manual": old["manual"] or fix.get("manual", False)}
        changed = order is not None and new != old
        if changed:
            self.fixes[order_id] = new
        if order_id in self.held:  # the first post waited for this answer: it goes now, with the fix
            self.release(order_id, "answer")
            if changed:
                self.log.write("note_fix", orderId=order_id, fix=new, outcome="posted with the fix", problems=result["problems"])
                self.log.say(f"Note of {order_id}: the model found {self.found(old, new)}, which the rules missed; posted with the fix.")
            return
        if not changed:
            return
        self.send_post_of(order_id)  # the rules' post may still wait in the outbox: its gig must be known first
        legs, gigs = undelivered(order), self.gigs_of(order_id)
        if not legs:
            outcome = "nothing to do: delivered"
        elif any(gig_id in self.booked for gig_id in gigs):
            outcome = "kept for its next post: a driver holds the gig"
        else:
            # The withdrawal goes first and alone: a driver may book the gig meanwhile, and the world then refuses it.
            # Only the cars whose gig left the app, or that have none, go again; a post in the same batch would give a
            # booked car a second gig.
            withdrawals = [{"type": "withdraw", "gigId": gig_id} for gig_id in gigs]
            results = self.world.act(withdrawals) if withdrawals else []
            for action, answer in zip(withdrawals, results):
                self.log.write("action", action=action, ok=answer["ok"], reason=answer.get("reason"))
            off = {action["gigId"] for action, answer in zip(withdrawals, results) if answer["ok"]}
            held = self.leg_gigs.get(order_id, {})
            freed = [leg for leg in legs if held.get(leg) in off or leg not in held]
            for leg in freed:
                held.pop(leg, None)
            if freed:
                self.post(order, freed)
            posted = any(a["type"] == "post" and any(s["orderId"] == order_id for s in a["stops"]) for a in self.outbox) or bool(self.gigs_of(order_id))
            if not gigs:  # the car had no gig: a car held for a return goes out later, with the fix
                outcome = "posted with the fix" if posted else "kept for its next post: the car has no gig yet"
            else:
                outcome = "withdrawn and posted again" if len(off) == len(gigs) else "kept for its next post: a driver booked the gig as the desk withdrew it"
        self.log.write("note_fix", orderId=order_id, fix=new, outcome=outcome, problems=result["problems"])
        self.log.say(f"Note of {order_id}: the model found {self.found(old, new)}, which the rules missed; {outcome}.")

    @staticmethod
    def found(old: dict, new: dict) -> str:
        what = [f"ready from {clock_text(new['pickupFrom'])}" if new["pickupFrom"] > old["pickupFrom"] else "",
                "plates" if new["plates"] > old["plates"] else "", "a manual licence" if new["manual"] > old["manual"] else ""]
        return ", ".join(w for w in what if w)

    def release(self, order_id: str, why: str) -> None:
        """Posts a held first post now: with the watcher's fix, or with the rules alone when the answer is late."""
        entry = self.held.pop(order_id)
        self.log.write("note_hold", orderId=order_id, why=why, seconds=round(time.monotonic() - entry["since"], 3), minutes=self.now - entry["at"])
        order = self.orders.get(order_id)
        legs = [leg for leg in entry["legs"] or [] if order is not None and leg in undelivered(order)]
        if legs:
            self.post(order, legs, entry["retry"])

    def release_due(self) -> None:
        """Posts the held first posts whose answer is late: the rules' reading goes out, and a later no withdraws and posts again."""
        now = time.monotonic()
        for order_id in [i for i, e in self.held.items() if now - e["since"] >= HOLD_SECONDS or self.now - e["at"] >= HOLD_MINUTES]:
            self.release(order_id, "late")

    def recheck(self) -> None:
        """Hands the watcher the won notes that it has not answered for: those won while the desk was away, or in flight at a
        stop. Only cars that no driver holds yet: a fix can still change their post."""
        for order_id in sorted(self.unchecked):
            order, request = self.orders.get(order_id), self.requests.get(order_id)
            if order is None or request is None or not undelivered(order) or any(g in self.booked for g in self.gigs_of(order_id)):
                self.unchecked.discard(order_id)
            else:
                self.watch.check(order_id, request, order["deadline"], notes.read(request["note"], request["arrivedAt"]), self.now)

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
            failed, rest = self.failed.get(order_id, {}), []
            for leg in undelivered(order):
                if (order_id, leg) in posting:
                    continue
                if leg in failed:
                    # As the kit's starter does: a car whose visit failed goes again unless a gig posted since carries it.
                    # The world may still list it on the gig of the failed visit.
                    reason, gig_id, at = failed[leg]
                    if not any(gig["postedAt"] >= at and gig["id"] != gig_id and any(s["orderId"] == order_id and s["leg"] == leg for s in gig["stops"])
                               for gig in live):
                        self.safely("retry", order_id, self.retry, order_id, leg, reason)
                elif leg not in self.leg_gigs.get(order_id, {}):
                    rest.append(leg)
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


class LivePairDesk(LiveDesk, PairPolicy):
    """The live desk with out-and-back pairs (pairs.py), for a variant that sets `pair_hold`. A pair gig carries the cars
    of two orders. The world's snapshot gives every stop of it, so `adopt` finds both cars on their gig. What a pair adds
    after a restart and with the note watcher is here."""

    def alone(self, order, legs, retry: Retry = Retry()) -> None:
        """A car posted alone, or as one half of a pair gig, carries what the note watcher found, as LiveDesk.post does."""
        fix = self.fixes.get(order["id"])
        if fix:
            retry = Retry(max(retry.pickup_from, fix["pickupFrom"]), retry.manual_licence or fix["manual"], retry.plates or fix["plates"])
        PairPolicy.alone(self, order, legs, retry)

    def release(self, order_id: str, why: str) -> None:
        """The first post that waited for the note watcher is still a first post: it can be held for a return, or pair."""
        self.first = order_id
        try:
            super().release(order_id, why)
        finally:
            self.first = None

    def correct(self, result: dict) -> None:
        """When the fix took a pair gig out of the app, the other order's car goes again alone."""
        gig_id = self.pair_of(result["orderId"])
        super().correct(result)
        if gig_id in self.pair_gigs and gig_id not in self.gigs_of(result["orderId"]) and gig_id not in self.booked:
            self.split(gig_id, "note", withdraw=False)

    def catch_up(self, events: list[dict]) -> tuple[dict[str, int], dict[str, int]]:
        self.read_pairs = []  # wins read offline that would go back with a held car: reconcile gives them their first post
        return super().catch_up(events)

    def pair_up(self, order) -> bool:
        """Offline a pair gig cannot be posted, and pairs.py would take it for refused and post both cars alone. So a win
        read at a join that pairs leaves the held car held and its own car unposted, for `reconcile` to pair them online."""
        if not self.offline:
            return super().pair_up(order)
        if self.best_pair(order, at=self.now) is None:
            return False
        self.read_pairs.append(order["id"])
        return True

    def reconcile(self, snapshot: dict, changed: dict[str, int], dropped: dict[str, int]) -> None:
        for order_id in self.read_pairs:  # first, so that the cars they pair with are still held
            order = self.orders.get(order_id)
            if order is not None and undelivered(order) and not self.gigs_of(order_id) and order_id not in self.pair_wait:
                self.first = order_id
                try:
                    self.safely("post", order_id, self.post, order, undelivered(order))
                finally:
                    self.first = None
        self.read_pairs = []
        super().reconcile(snapshot, changed, dropped)

    def steepen(self, order_id: str) -> None:
        """A deadline warning that came while the desk was away: an open pair gig goes as two gigs, as pairs.py does."""
        gig_id = self.pair_of(order_id)
        if gig_id and gig_id not in self.booked:
            return self.split(gig_id, "warning")
        super().steepen(order_id)

    def adopt(self, snapshot: dict) -> None:
        """The pair gigs are the world's live gigs with cars of two orders; a held car whose order is gone is dropped."""
        super().adopt(snapshot)
        live = {g["id"]: g for g in snapshot["gigs"] if g["status"] in ("open", "booked", "working")}
        pairs = {g_id: g for g_id, g in live.items() if len({s["orderId"] for s in g["stops"]}) > 1}
        for gig_id in list(self.pair_gigs):
            if gig_id not in pairs:
                del self.pair_gigs[gig_id]  # gone while the desk was away: reconcile posts its cars that have no gig
        for gig_id, gig in pairs.items():
            if gig_id not in self.pair_gigs:  # posted just before the books were saved, or a join from the history alone
                orders = {s["orderId"]: self.orders[s["orderId"]] for s in gig["stops"] if s["orderId"] in self.orders}
                latest = self.latest(gig["stops"], orders) if len(orders) > 1 else None
                self.pair_gigs[gig_id] = self.now if latest is None else latest
        # A join replays each win offline, which holds its car again, and no look releases it there. A car stays held only
        # while its order is undelivered, has no gig in the world, and its hold has not ended; reconcile posts the others
        # that still need a gig, as any car without one.
        for order_id, until in list(self.pair_wait.items()):
            order = self.orders.get(order_id)
            if order is None or not undelivered(order) or self.leg_gigs.get(order_id) or until <= self.now:
                del self.pair_wait[order_id]


class LiveWideDesk(WideLate, LiveDesk):
    """The live desk with the wide late chance (late_wide.py), for a variant that sets `late_wide`."""


class LiveWidePairDesk(WideLate, LivePairDesk):
    """... and with out-and-back pairs."""


def desk_class(params: dict) -> type:
    if params.get("late_wide"):
        return LiveWidePairDesk if params.get("pair_hold") else LiveWideDesk
    return LivePairDesk if params.get("pair_hold") else LiveDesk


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
                 map_: dict, folder: Path, speed: float = 1.0, echo: bool = True, watcher: Optional[Callable[..., watch.Watcher]] = None):
        self.world, self.minute_now, self.level, self.params, self.map = world, minute_now, level, params, map_
        self.folder, self.store, self.log = folder, Store(folder), Log(folder / "log.jsonl", echo)
        self.watcher = watcher(self.log, folder) if watcher else None  # the note watcher, with --watch-notes
        if self.watcher is not None:
            self.watcher.start()
        self.clock = Clock(speed=speed)
        self.guard = Guard(guard_act, self.clock, self.log, params.get("max_unbooked", 0))
        self.guard.start()
        self.desk: Optional[LiveDesk] = None
        self.generation = 0  # a stream reader of an earlier generation stops
        self.ends_at = None

    def join(self, out: Optional[queue.Queue] = None) -> None:
        """Rebuilds the books: from memory, else from disk, else from the world's whole history. With `out`, the stream
        into it starts before the books are rebuilt, so a request that arrives meanwhile goes to the guard at once:
        reading a week's history takes seconds, longer than a request gives at night."""
        first = self.world.snapshot()
        self.clock.saw(first["now"], exact=True)
        self.ends_at = first["endsAt"]
        for request in first["openRequests"]:
            self.guard.add(request)
        source = "memory" if self.desk is not None else "disk"
        if self.desk is None:
            self.desk = self.store.load(self.world.id)
            if self.desk is not None:  # books that older code wrote lack what the desk has gained since: a new desk's starting values
                fresh = desk_class(self.params)(self.world, self.level, first["now"], self.params, self.world.roster(), self.map)
                vars(self.desk).update({k: v for k, v in vars(fresh).items() if k not in vars(self.desk)})
        if self.desk is None:
            source = "world"
            self.desk = desk_class(self.params)(self.world, self.level, first["now"], self.params, self.world.roster(), self.map)
        self.desk.attach(self.world, self.log, self.guard, self.clock, self.watcher)
        events = self.world.events(after=self.desk.seq)
        snapshot = self.world.snapshot()
        self.clock.saw(snapshot["now"], exact=True)
        if source != "world":
            self.fence(snapshot)
        if out is not None:
            self.generation += 1
            after = events[-1]["seq"] if events else self.desk.seq
            threading.Thread(target=self.read, args=(out, after, self.generation), daemon=True, name="stream").start()
        for request in snapshot["openRequests"]:
            self.guard.add(request)
        changed, dropped = self.desk.catch_up(events)
        self.desk.adopt(snapshot)
        self.desk.reconcile(snapshot, changed, dropped)
        if self.watcher is not None:
            self.desk.recheck()
        self.store.save(self.desk)
        live_gigs = sum(1 for g in snapshot["gigs"] if g["status"] in ("open", "booked", "working"))
        self.log.write("joined", source=source, minute=snapshot["now"], missed=len(events), seq=self.desk.seq, orders=len(self.desk.orders),
                       liveGigs=live_gigs, openRequests=len(snapshot["openRequests"]), level=self.level, params=self.desk.p)
        self.log.say(f"Joined world {self.world.id} at {clock_text(snapshot['now'])} from {source}: {len(events)} events read, "
                     f"{len(self.desk.orders)} orders, {live_gigs} live gigs, {len(snapshot['openRequests'])} open requests.")

    def fence(self, snapshot: dict) -> None:
        """Stops for good when another desk has played the world since this desk's books end. The world posts no gigs
        by itself, so a gig that this desk did not post, posted well after the last minute it knows, is another desk's:
        a standby that a person started while this one was away. Two desks on one world post every car twice."""
        # The books are saved when the desk has done something, so they can end long before a post that the world took
        # just as the desk died. Its log has a line every BEAT seconds and the event that the post answered.
        last = max(self.desk.now, last_minute(self.folder / "log.jsonl"))
        margin = FENCE / seconds_per_minute(last) * self.clock.speed  # world minutes in FENCE real seconds
        foreign = sorted((g["postedAt"], g["id"]) for g in snapshot["gigs"] if g["id"] not in self.desk.posts and g["postedAt"] > last + margin)
        if not foreign:
            return
        reason = (f"{len(foreign)} gigs that this desk did not post were posted from {clock_text(foreign[0][0])} on, after it last played at "
                  f"{clock_text(last)}: another desk plays world {self.world.id}.")
        (self.folder / "fenced").write_text(reason + "\n", encoding="utf-8")
        self.log.write("fenced", gigs=[g for _, g in foreign[:20]], lastPlayed=last, firstPostedAt=foreign[0][0])
        self.log.say(f"Stopped for good: {reason} This desk will not act on it again.")
        raise Fenced(reason)

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
        events = queue.Queue()
        try:
            self.join(events)
        except BaseException:
            self.generation += 1  # the stream that the join started stops
            raise
        desk = self.desk
        saved = polled = beat = time.monotonic()
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
                if self.watcher is not None:  # the answers of the note watcher; it never holds the desk up
                    for result in self.watcher.results():
                        desk.safely("note check", result["orderId"], desk.correct, result)
                    desk.now = max(desk.now, int(self.clock.now()))
                    desk.safely("note hold", "", desk.release_due)
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
                if time.monotonic() - beat >= BEAT:  # for the alarm: the desk is alive, and how far it is
                    beat = time.monotonic()
                    self.log.write("beat", minute=desk.now, clock=round(self.clock.now(), 1), seq=desk.seq, unbooked=self.guard.backlog)
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
            if self.watcher is not None:
                self.watcher.end_day(before // DAY)
                self.log.say(f"           {self.watcher.day_line()}")

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
        if self.watcher is not None:
            self.log.say(self.watcher.day_line())
            self.log.say(watch.summary(self.folder / "review.jsonl"))

    def stop(self) -> None:
        self.generation += 1
        self.guard.stopped.set()
        if self.watcher is not None:
            self.watcher.stopped.set()


def last_minute(log: Path) -> float:
    """The last world minute that the log shows the desk at: its heartbeats and the events it took, from the log's end."""
    try:
        with open(log, "rb") as f:
            f.seek(max(0, f.seek(0, os.SEEK_END) - 256_000))
            tail = f.read().split(b"\n")[1:]
    except OSError:
        return -1
    last = -1
    for raw in tail:
        try:
            line = json.loads(raw)
        except ValueError:
            continue
        if line.get("kind") == "beat":
            last = max(last, line["minute"])
        elif line.get("kind") == "event":
            last = max(last, line["event"]["at"])
    return last


def clock_text(minute: int) -> str:
    return f"{WEEKDAYS[minute // DAY % 7][:3]} {minute % DAY // HOUR:02d}:{minute % HOUR:02d}"


def folder_of(world_id: str) -> Path:
    return data_dir() / "live" / world_id


def keep_going(live: Live, label: str) -> None:
    """Runs the desk to the world's end through lost connections and server restarts (API.md, Errors: the server
    answers again in under a minute, and every world goes on from where it was). One desk at a time: a second one on
    the same world would post every car again."""
    fenced = live.folder / "fenced"
    if fenced.exists():  # another desk took the world over: a supervisor loop that starts this one again gets here at once
        live.stop()
        sys.exit(f"Fenced: {fenced.read_text(encoding='utf-8').strip()} Delete {fenced} and state.pickle to play this world from here again.")
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
        except Fenced as error:
            live.stop()
            sys.exit(f"Fenced: {error}")
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


def note_watcher(args) -> Optional[Callable[..., watch.Watcher]]:
    """The note watcher, with --watch-notes: the model checks each won note when its key is in the environment."""
    if not args.watch_notes:
        return None

    def start(log: Log, folder: Path) -> watch.Watcher:
        verify = watch.model_verifier()
        log.say(f"Note watcher on: {watch.MODEL} checks each won note after its post; corrections and the review queue go to {folder}."
                if verify else f"Note watcher on without a model ({watch.KEY} is not set): the rules read alone; new notes and drift go to the log.")
        return watch.Watcher(log, folder, verify, echo=log.echo)
    return start


def play_final(args) -> None:
    client = Client(url=os.environ.get("SPREAD_URL") or SERVER)
    world, final = wait_for_final(client)
    level = next((w["level"] for w in client.worlds() if w["worldId"] == world.id), 8)
    guard_world = World(Client(url=client.url, key=client.key), world.id)
    live = Live(world, guard_world.act, lambda: client.final()["now"], level, VARIANTS[args.variant], client.map(), folder_of(world.id),
                watcher=note_watcher(args))
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
    live = Live(world, guard_world.act, lambda: world.snapshot()["now"], 8, VARIANTS[args.variant], world_map(client), folder_of(world.id), args.speed,
                watcher=note_watcher(args))
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
    desk = command + ["play", world.id, "--speed", str(args.speed), "--variant", args.variant] + (["--watch-notes"] if args.watch_notes else [])
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
    checks = [l for l in lines if l["kind"] == "note_check"]
    if checks or any(l["kind"] == "note_new" for l in lines):
        answers, fixes = Counter(l["answer"] or l["error"] for l in checks), [l for l in lines if l["kind"] == "note_fix"]
        seconds = sorted(l["seconds"] for l in checks if l["answer"] and l["seconds"] is not None)
        drift = ", ".join(f"{l['topic']} {l['share']:.0%} at {clock_text(l['minute'])}" for l in lines if l["kind"] == "note_drift") or "none"
        holds = [l for l in lines if l["kind"] == "note_hold"]
        out.append(f"First posts held for the model: {len(holds)}, {sum(1 for l in holds if l['why'] == 'answer')} until its answer, "
                   f"{sum(1 for l in holds if l['why'] == 'late')} posted with the rules when it was late; longest "
                   f"{max((l['seconds'] for l in holds), default=0)} s, {max((l['minutes'] for l in holds), default=0)} world minutes.")
        out.append(f"Note watcher: {len(checks)} won notes checked ({', '.join(f'{n} {a}' for a, n in answers.most_common())}); "
                   f"seconds median {statistics.median(seconds) if seconds else '-'}, most {seconds[-1] if seconds else '-'}; "
                   f"{len(fixes)} fixed ({', '.join(f'{n} {o}' for o, n in Counter(l['outcome'] for l in fixes).items()) or 'none'}); "
                   f"{sum(1 for l in lines if l['kind'] == 'note_new')} notes with a new word or sentence; "
                   f"drift alerts: {drift}.")
        out.append(watch.summary(folder_of(world_id) / "review.jsonl"))
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
    final.add_argument("--watch-notes", action="store_true", help="a model checks each won note beside the desk (watch.py); off by default")
    play = commands.add_parser("play", help="play a practice world that something else moves (rehearse starts it)")
    play.add_argument("world")
    play.add_argument("--speed", type=float, default=1.0)
    play.add_argument("--variant", default=VARIANT)
    play.add_argument("--watch-notes", action="store_true", help="a model checks each won note beside the desk (watch.py); off by default")
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
    rehearsal.add_argument("--watch-notes", action="store_true", help="a model checks each won note beside the desk (watch.py); off by default")
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
