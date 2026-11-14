"""Tests of the live desk: the final's clock, the fallback quote, and a desk that dies and starts again."""
from __future__ import annotations

import time

from spreadlab import live, replay
from spreadlab.variants import VARIANTS

from test_harness import MAP, ROSTER, request

DAY, HOUR = 1440, 60


def test_the_final_takes_34_minutes_and_a_test_final_from_thursday_19():
    # API.md, The final: an hour takes 18 s from 06:00 to 22:00 on weekdays, 6 s on Saturday, 9 s on the last Monday,
    # and 3 s at night, on Sunday and after the last Monday. The world ends on the second Wednesday at 22:00.
    weekday, saturday, sunday, last_monday = 16 * 18 + 8 * 3, 16 * 6 + 8 * 3, 24 * 3, 16 * 9 + 8 * 3
    after = 24 * 3 + 22 * 3  # the last Tuesday, and the Wednesday to 22:00
    ends_at = 9 * DAY + 22 * HOUR
    seconds = lambda start: sum(live.seconds_per_minute(m) for m in range(start, ends_at))
    assert round(seconds(0)) == 5 * weekday + saturday + sunday + last_monday + after == 2058  # "about 34 minutes"
    assert round(seconds(3 * DAY)) == 2 * weekday + saturday + sunday + last_monday + after == 1122  # "about 19 minutes"
    clock = live.Clock(minute=10 * HOUR)  # Monday 10:00: a request's 15 minutes are 4.5 seconds
    assert abs(clock.seconds_until(10 * HOUR + 15) - 4.5) < 0.05
    waiting = live.Clock(minute=3 * DAY)  # a test final is set 15 minutes before its start, on Thursday 00:00
    waiting.start_at(time.time() + 900)
    assert waiting.now() == 3 * DAY and abs(waiting.seconds_until(3 * DAY + 1) - 900.05) < 0.05


def test_guard_quotes_the_fallback_only_for_a_request_the_desk_has_not_taken_up_and_before_its_deadline(tmp_path):
    clock = live.Clock(minute=500, speed=10)  # 15 minutes are 0.45 seconds
    sent = []
    guard = live.Guard(lambda actions: sent.extend((clock.seconds_until(515), a) for a in actions) or [{"ok": True}] * len(actions),
                       clock, live.Log(tmp_path / "log.jsonl", echo=False), max_unbooked=15)
    guard.start()
    forgotten, taken = request("R1", options=(("same_day", 1200), ("next_day", 2640))), request("R2")
    for r in (forgotten, taken):
        guard.add(r)
    guard.claim("R2")
    time.sleep(0.6)
    guard.stopped.set()
    assert [a["requestId"] for _, a in sent] == ["R1"]
    left, action = sent[0]
    assert 0 < left < 0.45
    # No same_day, and 1.9 x the typical fee of 9000, which is over 1.5 x the list price of 10000.
    assert action["prices"] == {"next_day": 17100}


def test_a_desk_that_dies_after_the_world_took_its_post_keeps_the_gig_and_what_it_learned(tmp_path):
    won, lost = request("R1"), request("R2", arrivedAt=505, respondBy=520)
    late = request("R3", arrivedAt=521, respondBy=522)  # arrives while the desk is down; 0.3 s are left at the restart
    events = [{"seq": 0, "at": 500, "kind": "price_request", "request": won},
              {"seq": 1, "at": 505, "kind": "price_request", "request": lost},
              {"seq": 2, "at": 515, "kind": "order_won", "order": {"id": "R1", "dealerId": "D01", "option": "next_day", "priceCents": 15000,
                                                                     "deadline": 2640, "legs": won["legs"], "lastPickupAt": 2400,
                                                                     "status": "waiting", "deliveredAt": [None]}},
              {"seq": 3, "at": 520, "kind": "order_lost", "requestId": "R2"},
              {"seq": 4, "at": 521, "kind": "price_request", "request": late}]
    world = replay.Replay(events, ROSTER, ends_at=20000, start=506, speed=0.001)  # the world's clock stands nearly still
    desk = lambda: live.Live(world, world.guard_act, world.minute, 8, VARIANTS[live.VARIANT], MAP, tmp_path, echo=False)
    first = desk()
    first.join()  # both requests are open: it quotes them
    assert sorted(world.quotes) == ["R1", "R2"]
    world.clock.saw(516)  # R1 is won
    for event in world.events(after=first.desk.seq):
        first.desk.take(event)
    world.crash_next_act = True
    try:
        first.desk.send()  # the world takes the post of R1, and the desk dies before it reads the answer
        raise AssertionError("the desk should have died")
    except replay.Crash:
        first.stop()
    assert list(world.gigs) == ["g1"]
    world.clock.saw(521)  # R2 is lost and R3 arrives while the desk is down

    second = desk()
    second.join()  # from the books on disk, which do not know of the win or of g1
    assert list(world.gigs) == ["g1"], "the car of R1 is in one gig"
    assert second.desk.leg_gigs["R1"] == {0: "g1"}
    assert [won for _, won in second.desk.today[1]] == [True, False], "the day's correction counts both answers once"
    time.sleep(0.4)  # past the minute at which the guard quotes a request that nobody answered
    assert [by for _, _, by in world.quotes["R1"] + world.quotes["R3"]] == ["desk", "desk"], "the guard replaces no quote of the desk"
    second.stop()
