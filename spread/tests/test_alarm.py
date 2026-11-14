"""Tests of the alarm (alarm.py) and of the fence that keeps a second desk off a world (live.py)."""
from __future__ import annotations

import json

import pytest

from spreadlab import alarm, live, replay
from spreadlab.variants import VARIANTS

from test_harness import MAP, ROSTER, request


def beat(clock: float) -> dict:
    return {"kind": "beat", "minute": int(clock), "clock": clock, "seq": 0, "unbooked": 0}


def asked(request_id: str, respond_by: int) -> dict:
    return {"kind": "event", "replayed": False, "event": {"kind": "price_request", "at": respond_by - 15, "request": {"id": request_id, "respondBy": respond_by}}}


def quoted(request_id: str) -> dict:
    return {"kind": "action", "ok": True, "action": {"type": "quote", "requestId": request_id, "prices": {}}}


def test_the_alarm_rings_when_the_desk_falls_silent_or_its_log_cannot_be_read_and_says_when_it_is_back():
    watch = alarm.Watch(last_read=0.0, last_line=0.0)
    assert watch.lines([beat(500)], 0.0) == [] and watch.tick(0.0, True) == []
    assert watch.tick(alarm.SILENT - 1, True) == []
    assert [kind for _, kind, _ in watch.tick(alarm.SILENT, True)] == ["silent"]
    assert [level for level, _, _ in watch.lines([beat(530)], alarm.SILENT + 2)] == ["ok"]
    assert [kind for _, kind, _ in watch.tick(alarm.SILENT + 2 + alarm.UNREAD, False)] == ["unreadable"]


def test_the_alarm_rings_for_a_request_that_reaches_its_deadline_without_a_quote_and_only_for_it():
    watch = alarm.Watch(last_read=0.0, last_line=0.0)
    assert watch.lines([beat(500), asked("R1", 515), asked("R2", 515), quoted("R1")], 1.0) == []
    assert watch.lines([beat(514.9)], 3.0) == [], "not before its deadline"
    notices = watch.lines([beat(515.2)], 5.0)
    assert [(kind, "R2" in text, "R1" in text) for _, kind, text in notices] == [("missed", True, False)]
    assert watch.lines([beat(530)], 7.0) == [], "once"


def test_the_alarm_keeps_quiet_about_what_a_log_held_before_it_watched_and_rings_for_what_comes_after(tmp_path, monkeypatch):
    log = tmp_path / "w1" / "log.jsonl"
    log.parent.mkdir()
    old = [beat(500), asked("R1", 515), beat(600)]  # R1 went unquoted while the desk was down, before the alarm started
    log.write_text("".join(json.dumps(line) + "\n" for line in old))
    told, now, polls = [], [0.0], []

    def sleep(seconds):  # between the alarm's reads: R2 arrives and goes unquoted after the second read
        now[0] += 2
        polls.append(list(told))
        if len(polls) == 2:
            with open(log, "a") as f:
                f.write(json.dumps(asked("R2", 620)) + "\n" + json.dumps(beat(621)) + "\n")
    monkeypatch.setattr(alarm, "tell", lambda level, text, notify: told.append((level, text)))
    alarm.watch_log(alarm.Source(str(tmp_path)), None, clock=lambda: now[0], sleep=sleep, polls=3)  # the folder: the log written last
    assert [level for level, _ in polls[1]] == ["ok"], "only the line that says what it watches"
    assert [(level, "R2" in text, "R1" in text) for level, text in told[1:]] == [("alarm", True, False)]


def won(request_id: str, at: int, respond_by: int) -> list[dict]:
    r = request(request_id, arrivedAt=at - 15, respondBy=respond_by)
    order = {"id": request_id, "dealerId": "D01", "option": "next_day", "priceCents": 15000, "deadline": 2640 + at, "legs": r["legs"],
             "lastPickupAt": 2400 + at, "status": "waiting", "deliveredAt": [None]}
    return [{"at": at - 15, "kind": "price_request", "request": r}, {"at": at, "kind": "order_won", "order": order}]


def numbered(events: list[dict]) -> list[dict]:
    return [{"seq": i, **e} for i, e in enumerate(sorted(events, key=lambda e: e["at"]))]


def test_a_desk_that_comes_back_after_a_standby_took_the_world_over_stops_for_good(tmp_path):
    world = replay.Replay(numbered(won("R1", 515, 515) + won("R2", 590, 590)), ROSTER, ends_at=20000, start=500, speed=0.001)
    desk = lambda folder: live.Live(world, world.guard_act, world.minute, 8, VARIANTS[live.VARIANT], MAP, folder, echo=False)
    first = desk(tmp_path / "first")
    first.join()
    world.clock.saw(516)
    for event in world.events(after=first.desk.seq):
        first.desk.take(event)
    first.desk.send()  # g1
    first.store.save(first.desk)
    first.stop()  # its machine is lost

    world.clock.saw(700)  # a person starts the standby on another machine, without books; R2 was won meanwhile
    standby = desk(tmp_path / "standby")
    standby.join()
    standby.stop()
    assert sorted(world.gigs) == ["g1", "g2"] and world.gigs["g2"]["postedAt"] == 700

    again = desk(tmp_path / "first")  # the first machine is back, and its supervisor starts the desk again
    with pytest.raises(SystemExit, match="Fenced"):
        live.keep_going(again, "final")
    assert sorted(world.gigs) == ["g1", "g2"], "the fenced desk posts nothing"
    assert (tmp_path / "first" / "fenced").exists()
    with pytest.raises(SystemExit, match="Fenced"):  # and the next start stops at once
        live.keep_going(desk(tmp_path / "first"), "final")


def test_a_desk_that_died_as_the_world_took_its_post_after_a_quiet_stretch_is_not_fenced_by_its_own_gig(tmp_path):
    # Nothing happens from 506 to 900, so the books are from 506; the world takes the post of R1 at 901 as the desk dies.
    world = replay.Replay(numbered(won("R1", 900, 900)), ROSTER, ends_at=20000, start=506, speed=0.001)
    desk = lambda: live.Live(world, world.guard_act, world.minute, 8, VARIANTS[live.VARIANT], MAP, tmp_path, echo=False)
    first = desk()
    first.join()
    world.clock.saw(901)
    for event in world.events(after=first.desk.seq):
        first.desk.take(event)
    world.crash_next_act = True
    with pytest.raises(replay.Crash):
        first.desk.send()
    first.stop()
    second = desk()
    second.join()
    second.stop()
    assert list(world.gigs) == ["g1"] and second.desk.leg_gigs["R1"] == {0: "g1"}
    assert not (tmp_path / "fenced").exists()
