"""Tests of the live desk: the final's clock, the fallback quote, and a desk that dies and starts again."""
from __future__ import annotations

import pickle
import threading
import time

import pytest

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


def test_guard_quotes_the_fallback_only_for_a_request_the_desk_sends_no_quote_for_and_before_its_deadline(tmp_path):
    clock = live.Clock(minute=500, speed=10)  # 15 minutes are 0.45 seconds
    sent = []
    guard = live.Guard(lambda actions: sent.extend((clock.seconds_until(515), a) for a in actions) or [{"ok": True}] * len(actions),
                       clock, live.Log(tmp_path / "log.jsonl", echo=False), max_unbooked=15)
    guard.start()
    forgotten, taken = request("R1", options=(("same_day", 1200), ("next_day", 2640))), request("R2")
    for r in (forgotten, taken):
        guard.add(r)
    guard.claim(["R2"])  # the desk sends its own quote for R2
    time.sleep(0.6)
    guard.stopped.set()
    assert [a["requestId"] for _, a in sent] == ["R1"]
    left, action = sent[0]
    assert 0 < left < 0.45
    # No same_day, and 1.9 x the typical fee of 9000, which is over 1.5 x the list price of 10000.
    assert action["prices"] == {"next_day": 17100}


def test_a_desk_that_dies_after_the_world_took_its_post_keeps_the_gig_and_what_it_learned(tmp_path):
    won, lost = request("R1"), request("R2", arrivedAt=505, respondBy=520)
    unseen = request("R4", arrivedAt=517, respondBy=519)  # arrives and is lost while the desk is down: nobody quoted it
    late = request("R3", arrivedAt=521, respondBy=522)  # arrives while the desk is down; 0.3 s are left at the restart
    events = [{"seq": 0, "at": 500, "kind": "price_request", "request": won},
              {"seq": 1, "at": 505, "kind": "price_request", "request": lost},
              {"seq": 2, "at": 515, "kind": "order_won", "order": {"id": "R1", "dealerId": "D01", "option": "next_day", "priceCents": 15000,
                                                                     "deadline": 2640, "legs": won["legs"], "lastPickupAt": 2400,
                                                                     "status": "waiting", "deliveredAt": [None]}},
              {"seq": 3, "at": 517, "kind": "price_request", "request": unseen},
              {"seq": 4, "at": 519, "kind": "order_lost", "requestId": "R4"},
              {"seq": 5, "at": 520, "kind": "order_lost", "requestId": "R2"},
              {"seq": 6, "at": 521, "kind": "price_request", "request": late}]
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
    world.clock.saw(521)  # R4 comes and goes, R2 is lost and R3 arrives while the desk is down

    second = desk()
    second.join()  # from the books on disk, which do not know of the win or of g1
    assert list(world.gigs) == ["g1"], "the car of R1 is in one gig"
    assert second.desk.leg_gigs["R1"] == {0: "g1"}
    assert [won for _, won in second.desk.today[1]] == [True, False], "the day's correction counts the answers to the desk's quotes, once"
    time.sleep(0.4)  # past the minute at which the guard quotes a request that nobody answered
    assert [by for _, _, by in world.quotes["R1"] + world.quotes["R3"]] == ["desk", "desk"], "the guard replaces no quote of the desk"
    second.stop()


def test_the_desk_plays_no_ranking_run_and_no_final_outside_the_final_command():
    class Worlds:
        def worlds(self):
            return [{"worldId": "p", "kind": "practice", "boardRun": None}, {"worldId": "b", "kind": "practice", "boardRun": 2},
                    {"worldId": "f", "kind": "final", "boardRun": None}]

        def world(self, world_id):
            return world_id

    assert live.practice_world(Worlds(), "p") == "p"
    for world_id in ("b", "f", "unknown"):
        with pytest.raises(SystemExit):
            live.practice_world(Worlds(), world_id)


def test_a_desk_that_joins_from_the_history_alone_does_not_redo_a_change_that_was_handled(tmp_path):
    asked = request("R1")
    order = {"id": "R1", "dealerId": "D01", "option": "next_day", "priceCents": 15000, "deadline": 2640, "legs": asked["legs"],
             "lastPickupAt": 2400, "status": "waiting", "deliveredAt": [None]}
    moved = {**order, "legs": [{**asked["legs"][0], "delivery": {**asked["legs"][0]["delivery"], "placeId": "tampere"}}]}
    events = [{"seq": 0, "at": 500, "kind": "price_request", "request": asked},
              {"seq": 1, "at": 515, "kind": "order_won", "order": order},
              {"seq": 2, "at": 600, "kind": "order_changed", "order": moved}]
    world = replay.Replay(events, ROSTER, ends_at=20000, start=506, speed=0.001)
    desk = lambda folder: live.Live(world, world.guard_act, world.minute, 8, VARIANTS[live.VARIANT], MAP, folder, echo=False)
    first = desk(tmp_path / "first")
    first.join()
    for minute in (516, 601):  # the win, then the change: the desk posts g1, then takes it off and posts g2 to the new place
        world.clock.saw(minute)
        for event in world.events(after=first.desk.seq):
            first.desk.take(event)
        first.desk.send()
    first.stop()
    assert {gig_id: gig["status"] for gig_id, gig in world.gigs.items()} == {"g1": "withdrawn", "g2": "open"}

    second = desk(tmp_path / "second")  # no books: it learns the week from the world's history
    second.join()
    second.stop()
    assert {gig_id: gig["status"] for gig_id, gig in world.gigs.items()} == {"g1": "withdrawn", "g2": "open"}
    assert second.desk.leg_gigs["R1"] == {0: "g2"}


def test_a_desk_that_joins_from_the_history_books_an_order_by_the_deadline_of_its_note(tmp_path):
    asked = request("R1", note={"text": "Moi. Pitää olla perillä huomenna 17 mennessä!"})  # by Tuesday 17:00, minute 2460
    order = {"id": "R1", "dealerId": "D01", "option": "next_day", "priceCents": 15000, "deadline": 2640, "legs": asked["legs"],
             "lastPickupAt": 2520, "status": "waiting", "deliveredAt": [None]}
    events = [{"seq": 0, "at": 500, "kind": "price_request", "request": asked},
              {"seq": 1, "at": 515, "kind": "order_won", "order": order}]
    world = replay.Replay(events, ROSTER, ends_at=20000, start=600, speed=0.001)
    joined = live.Live(world, world.guard_act, world.minute, 8, VARIANTS[live.VARIANT], MAP, tmp_path, echo=False)
    joined.join()  # no books: it reads the win from the history, then takes the orders from the world
    joined.stop()
    assert joined.desk.orders["R1"]["deadline"] == 2460, "the world's order does not undo the note's earlier deadline"
    assert joined.desk.orders["R1"]["lastPickupAt"] < 2460


def test_a_replay_from_thursday_holds_a_pair_gig_with_both_cars_until_a_cancellation_shortens_it():
    won = lambda order_id, seq, at: {"seq": seq, "at": at, "kind": "order_won", "order": {  # noqa: E731
        "id": order_id, "dealerId": "D01", "option": "next_day", "priceCents": 15000, "deadline": 2640, "legs": request(order_id)["legs"],
        "lastPickupAt": 2400, "status": "waiting", "deliveredAt": [None]}}
    events = [won("R1", 0, 100), won("R2", 1, 110),
              {"seq": 2, "at": 700, "kind": "order_cancelled", "orderId": "R2", "gigs": [{"gigId": "g1", "outcome": "shortened"}]}]
    # The recording keeps a gig's last stops: the pair gig of R1 and R2 is left with R1's alone.
    recorded = [{"id": "g1", "postedAt": 110, "status": "done", "audience": {},
                 "stops": [{"orderId": "R1", "leg": 0, "kind": "pickup", "withPlates": False, "withCharging": False},
                           {"orderId": "R1", "leg": 0, "kind": "delivery"}]}]
    world = replay.Replay(events, ROSTER, ends_at=20000, start=506, speed=0.001)
    world.resume_from(recorded, 506)
    cars = lambda: {s["orderId"] for s in world.snapshot()["gigs"][0]["stops"]}  # noqa: E731
    assert cars() == {"R1", "R2"}, "a desk that joins on Thursday sees R2 on its gig, as the world showed it"
    world.clock.saw(701)
    assert cars() == {"R1"}


def test_a_desk_that_starts_again_from_books_older_code_wrote_gets_what_the_desk_has_gained_since(tmp_path):
    asked = request("R1")
    order = {"id": "R1", "dealerId": "D01", "option": "next_day", "priceCents": 15000, "deadline": 2640, "legs": asked["legs"],
             "lastPickupAt": 2400, "status": "waiting", "deliveredAt": [None]}
    events = [{"seq": 0, "at": 500, "kind": "price_request", "request": asked}, {"seq": 1, "at": 515, "kind": "order_won", "order": order}]
    world = replay.Replay(events, ROSTER, ends_at=20000, start=506, speed=0.001)
    params = {**VARIANTS[live.VARIANT], "charge_km": 1, "due_cap": 5}  # both read attributes that books from before them lack
    desk = lambda: live.Live(world, world.guard_act, world.minute, 8, params, MAP, tmp_path, echo=False)
    first = desk()
    first.join()
    first.stop()
    old = pickle.loads((tmp_path / "state.pickle").read_bytes())
    for name in ("km", "night_drops", "fixes", "foreign"):
        delattr(old, name)
    (tmp_path / "state.pickle").write_bytes(pickle.dumps(old))
    world.clock.saw(516)  # the win arrives while the desk is down
    second = desk()
    second.join()  # from the old books: it posts the car, which needs km and night_drops
    second.stop()
    assert second.desk.km == first.desk.km and second.desk.night_drops == {} and second.desk.fixes == {}
    assert [g["stops"][0]["orderId"] for g in world.gigs.values()] == ["R1"]


def test_guard_covers_a_request_that_the_desk_decided_and_did_not_send_in_time(tmp_path):
    # The desk takes the request up and is then held up before it sends, here by never sending at all.
    asked = request("R1", arrivedAt=506, respondBy=507)  # 0.3 s at the final's speed
    world = replay.Replay([{"seq": 0, "at": 506, "kind": "price_request", "request": asked}], ROSTER, ends_at=20000, start=506, speed=0.001)
    desk = live.Live(world, world.guard_act, world.minute, 8, VARIANTS[live.VARIANT], MAP, tmp_path, echo=False)
    desk.clock.saw(506, exact=True)
    desk.desk = live.LiveDesk(world, 8, 506, VARIANTS[live.VARIANT], ROSTER, MAP)
    desk.desk.attach(world, desk.log, desk.guard, desk.clock)
    desk.guard.add(asked)  # as the stream reader does when the request arrives
    desk.desk.take(world.events()[0])
    time.sleep(0.35)
    desk.stop()
    assert [by for _, _, by in world.quotes.get("R1", [])] == ["fallback"]


def test_guard_covers_a_request_that_arrives_while_the_desk_reads_the_history(tmp_path, monkeypatch):
    # A standby that joins from the world reads the week's history first, which takes seconds; a request at night gives 0.75.
    events = [{"seq": 0, "at": 500, "kind": "price_request", "request": request("R1")},
              {"seq": 1, "at": 508, "kind": "price_request", "request": request("R2", arrivedAt=508, respondBy=511)}]
    world = replay.Replay(events, ROSTER, ends_at=20000, start=506, speed=1)  # 0.3 s a minute: R2 comes in 0.6 s and gives 0.9 s
    catch_up = live.LiveDesk.catch_up
    monkeypatch.setattr(live.LiveDesk, "catch_up", lambda desk, missed: time.sleep(2) or catch_up(desk, missed))
    desk = live.Live(world, world.guard_act, world.minute, 8, VARIANTS[live.VARIANT], MAP, tmp_path, echo=False)
    desk.run(stop_at=514)
    desk.stop()
    assert [by for _, _, by in world.quotes.get("R2", [])] == ["fallback"]


def test_a_second_desk_on_the_same_world_stops_at_once(tmp_path):
    world = replay.Replay([], ROSTER, ends_at=20000, start=506, speed=0.001)
    first, second = (live.Live(world, world.guard_act, world.minute, 8, VARIANTS[live.VARIANT], MAP, tmp_path, echo=False) for _ in range(2))
    first.run = lambda: time.sleep(1)  # the first desk is still playing
    playing = threading.Thread(target=live.keep_going, args=(first, "final"))
    playing.start()
    time.sleep(0.2)
    with pytest.raises(SystemExit, match="Another desk"):
        live.keep_going(second, "final")
    playing.join()
    first.stop()


def test_a_desk_that_starts_again_posts_a_car_whose_visit_failed_while_it_was_down(tmp_path):
    # The world can keep the car on the driver's gig after the failed visit: the gig is still working.
    asked = request("R1", arrivedAt=500, respondBy=515)
    order = {"id": "R1", "dealerId": "D01", "option": "next_day", "priceCents": 15000, "deadline": 2640, "legs": asked["legs"],
             "lastPickupAt": 2400, "status": "waiting", "deliveredAt": [None]}
    events = [{"seq": 0, "at": 500, "kind": "price_request", "request": asked},
              {"seq": 1, "at": 515, "kind": "order_won", "order": order},
              {"seq": 2, "at": 520, "kind": "gig_booked", "gigId": "g1", "driverId": "d1", "feeCents": 9000},
              {"seq": 3, "at": 530, "kind": "gig_started", "gigId": "g1", "driverId": "d1"},
              {"seq": 4, "at": 600, "kind": "visit_failed", "gigId": "g1", "orderId": "R1", "leg": 0, "reason": "no_plates"}]
    world = replay.Replay(events, ROSTER, ends_at=20000, start=506, speed=0.001)
    desk = lambda: live.Live(world, world.guard_act, world.minute, 8, VARIANTS[live.VARIANT], MAP, tmp_path, echo=False)
    first = desk()
    first.join()
    for minute in (516, 531):  # the win and the start of the drive: the desk posts g1 and sees it booked
        world.clock.saw(minute)
        for event in world.events(after=first.desk.seq):
            first.desk.take(event)
        first.desk.send()
        first.store.save(first.desk)
    first.stop()
    world.clock.saw(601)  # the visit fails while the desk is down
    second = desk()
    second.join()
    second.stop()
    assert world.gigs["g1"]["status"] == "working" and list(world.gigs) == ["g1", "g2"]
    assert world.gigs["g2"]["stops"][0]["withPlates"] is True, "the car goes again, with plates"


@pytest.mark.parametrize("variant", ["slow-friday-late-150-kinds-limits-pairs-0.7", "fee16-wide-pairs-0.6-return-0.75"])
def test_a_pair_desk_that_dies_after_the_world_took_a_pair_gig_finds_both_cars_on_it(tmp_path, monkeypatch, variant):
    from spreadlab import pairs
    monkeypatch.setattr(pairs, "RETURNS", {"helsinki>tampere": 20, "tampere>helsinki": 20})
    out = request("R1", pickup="helsinki")
    out["legs"] = [{**out["legs"][0], "delivery": {**out["legs"][0]["delivery"], "placeId": "tampere"}}]
    back = request("R2", pickup="tampere", arrivedAt=520, respondBy=535, options=(("next_day", 2640),))
    won = lambda r, at: {"id": r["id"], "dealerId": "D01", "option": "next_day", "priceCents": 15000, "deadline": 2640,  # noqa: E731
                         "legs": r["legs"], "lastPickupAt": 2520, "status": "waiting", "deliveredAt": [None]}
    events = [{"seq": 0, "at": 500, "kind": "price_request", "request": out},
              {"seq": 1, "at": 515, "kind": "order_won", "order": won(out, 515)},
              {"seq": 2, "at": 520, "kind": "price_request", "request": back},
              {"seq": 3, "at": 535, "kind": "order_won", "order": won(back, 535)}]
    world = replay.Replay(events, ROSTER, ends_at=20000, start=506, speed=0.001)
    desk = lambda: live.Live(world, world.guard_act, world.minute, 8, VARIANTS[variant], MAP, tmp_path, echo=False)  # noqa: E731
    first = desk()
    first.join()
    assert isinstance(first.desk, live.LivePairDesk)
    world.clock.saw(516)  # R1 is won: its car waits for a return, with no gig
    for event in world.events(after=first.desk.seq):
        first.desk.take(event)
    first.desk.send()
    first.store.save(first.desk)
    assert list(world.gigs) == [] and "R1" in first.desk.pair_wait
    world.clock.saw(521)  # R2 runs back: its quote goes out
    for event in world.events(after=first.desk.seq):
        first.desk.take(event)
    first.desk.send()
    assert first.desk.decisions["R2"]["pair"] == "R1"
    world.clock.saw(536)  # R2 is won: both cars go in one gig, and the desk dies as the world takes it
    world.crash_next_act = True
    try:
        for event in world.events(after=first.desk.seq):
            first.desk.take(event)
        raise AssertionError("the desk should have died")
    except replay.Crash:
        first.stop()
    assert list(world.gigs) == ["g1"] and {s["orderId"] for s in world.gigs["g1"]["stops"]} == {"R1", "R2"}

    second = desk()
    second.join()  # from books that hold R1 and its hold, and know nothing of R2's win or of g1
    second.stop()
    assert type(second.desk) is type(first.desk), "the books bring back the same desk, with the wide late chance when the variant has it"
    assert list(world.gigs) == ["g1"], "no car of the pair gets a second gig"
    assert second.desk.gigs_of("R1") == second.desk.gigs_of("R2") == ["g1"]
    assert "g1" in second.desk.pair_gigs and not second.desk.pair_wait


def test_a_pair_desk_that_was_down_when_a_return_was_won_posts_the_pair_at_its_restart(tmp_path, monkeypatch):
    from spreadlab import pairs
    monkeypatch.setattr(pairs, "RETURNS", {"helsinki>tampere": 20, "tampere>helsinki": 20})
    out = request("R1", pickup="helsinki")
    out["legs"] = [{**out["legs"][0], "delivery": {**out["legs"][0]["delivery"], "placeId": "tampere"}}]
    back = request("R2", pickup="tampere", arrivedAt=520, respondBy=535, options=(("next_day", 2640),))
    won = lambda r: {"id": r["id"], "dealerId": "D01", "option": "next_day", "priceCents": 15000, "deadline": 2640,  # noqa: E731
                     "legs": r["legs"], "lastPickupAt": 2520, "status": "waiting", "deliveredAt": [None]}
    events = [{"seq": 0, "at": 500, "kind": "price_request", "request": out},
              {"seq": 1, "at": 515, "kind": "order_won", "order": won(out)},
              {"seq": 2, "at": 520, "kind": "price_request", "request": back},
              {"seq": 3, "at": 535, "kind": "order_won", "order": won(back)}]
    world = replay.Replay(events, ROSTER, ends_at=20000, start=506, speed=0.001)
    desk = lambda: live.Live(world, world.guard_act, world.minute, 8, VARIANTS["slow-friday-late-150-kinds-limits-pairs-0.7"], MAP, tmp_path, echo=False)  # noqa: E731
    first = desk()
    first.join()
    for minute in (516, 521):  # R1 is won and held; R2, which runs back, is quoted
        world.clock.saw(minute)
        for event in world.events(after=first.desk.seq):
            first.desk.take(event)
        first.desk.send()
    first.store.save(first.desk)
    first.stop()
    assert list(world.gigs) == [] and "R1" in first.desk.pair_wait
    world.clock.saw(536)  # R2 is won while the desk is down

    second = desk()
    second.join()  # reads R2's win from the history, with R1 still held
    second.stop()
    assert list(world.gigs) == ["g1"], "the two cars go in one gig, not alone"
    assert {s["orderId"] for s in world.gigs["g1"]["stops"]} == {"R1", "R2"}
    assert "g1" in second.desk.pair_gigs and not second.desk.pair_wait


def test_a_held_car_is_not_posted_at_a_restart_and_goes_alone_when_its_hold_ends(tmp_path, monkeypatch):
    from spreadlab import pairs
    monkeypatch.setattr(pairs, "RETURNS", {"helsinki>tampere": 20, "tampere>helsinki": 20})
    out = request("R1", pickup="helsinki")
    out["legs"] = [{**out["legs"][0], "delivery": {**out["legs"][0]["delivery"], "placeId": "tampere"}}]
    events = [{"seq": 0, "at": 500, "kind": "price_request", "request": out},
              {"seq": 1, "at": 515, "kind": "order_won", "order": {"id": "R1", "dealerId": "D01", "option": "next_day", "priceCents": 15000,
                                                                     "deadline": 2640, "legs": out["legs"], "lastPickupAt": 2520,
                                                                     "status": "waiting", "deliveredAt": [None]}}]
    world = replay.Replay(events, ROSTER, ends_at=20000, start=506, speed=0.001)
    desk = lambda: live.Live(world, world.guard_act, world.minute, 8, VARIANTS["slow-friday-late-150-kinds-limits-pairs-0.7"], MAP, tmp_path, echo=False)  # noqa: E731
    first = desk()
    first.join()
    world.clock.saw(516)
    for event in world.events(after=first.desk.seq):
        first.desk.take(event)
    first.desk.send()
    first.store.save(first.desk)
    first.stop()
    second = desk()
    second.join()
    assert list(world.gigs) == [] and second.desk.pair_wait == {"R1": 515 + 4 * HOUR}
    second.desk.now = 515 + 4 * HOUR
    second.desk.look()
    second.desk.send()
    second.stop()
    assert list(world.gigs) == ["g1"] and second.desk.gigs_of("R1") == ["g1"]


def test_a_pair_desk_that_joins_from_the_history_alone_does_not_post_a_car_held_and_delivered_before(tmp_path, monkeypatch):
    from spreadlab import pairs
    monkeypatch.setattr(pairs, "RETURNS", {"helsinki>tampere": 20, "tampere>helsinki": 20})
    out = request("R1", pickup="helsinki")
    out["legs"] = [{**out["legs"][0], "delivery": {**out["legs"][0]["delivery"], "placeId": "tampere"}}]
    events = [{"seq": 0, "at": 500, "kind": "price_request", "request": out},
              {"seq": 1, "at": 515, "kind": "order_won", "order": {"id": "R1", "dealerId": "D01", "option": "next_day", "priceCents": 15000,
                                                                     "deadline": 2640, "legs": out["legs"], "lastPickupAt": 2520,
                                                                     "status": "waiting", "deliveredAt": [None]}},
              {"seq": 2, "at": 760, "kind": "gig_booked", "gigId": "g1", "driverId": "d1", "feeCents": 9000},
              {"seq": 3, "at": 900, "kind": "delivered", "gigId": "g1", "orderId": "R1", "leg": 0, "placeId": "tampere"}]
    world = replay.Replay(events, ROSTER, ends_at=20000, start=506, speed=0.001)
    desk = lambda folder: live.Live(world, world.guard_act, world.minute, 8, VARIANTS["slow-friday-late-150-kinds-limits-pairs-0.7"], MAP, folder, echo=False)  # noqa: E731
    first = desk(tmp_path / "first")
    first.join()
    world.clock.saw(516)  # R1 is won and held for a return that never comes
    for event in world.events(after=first.desk.seq):
        first.desk.take(event)
    first.desk.send()
    world.clock.saw(515 + 4 * HOUR)  # its hold ends: it goes alone, as g1
    first.desk.now = 515 + 4 * HOUR
    first.desk.look()
    first.desk.send()
    first.stop()
    assert list(world.gigs) == ["g1"]
    world.clock.saw(1000)  # booked and delivered

    second = desk(tmp_path / "second")  # no books: it learns the week from the world's history, which wins R1 again
    second.join()
    second.desk.now = 1100  # past the end of the hold that the history replayed
    second.desk.look()
    second.desk.send()
    second.stop()
    assert list(world.gigs) == ["g1"], "a delivered car gets no second gig"
    assert not second.desk.pair_wait


def test_the_desk_sends_its_quotes_in_a_call_of_their_own_before_its_other_actions(tmp_path):
    # In the final each action costs a token (API.md, Limits): offers in the quote's call would make the kit wait for tokens first.
    asked = request("R1", arrivedAt=506, respondBy=521)
    world = replay.Replay([{"seq": 0, "at": 506, "kind": "price_request", "request": asked}], ROSTER, ends_at=20000, start=506, speed=0.001)
    desk = live.Live(world, world.guard_act, world.minute, 8, VARIANTS[live.VARIANT], MAP, tmp_path, echo=False)
    desk.clock.saw(506, exact=True)
    desk.desk = live.LiveDesk(world, 8, 506, VARIANTS[live.VARIANT], ROSTER, MAP)
    desk.desk.attach(world, desk.log, desk.guard, desk.clock)
    calls, act = [], world.act
    world.act = lambda actions, by="desk": calls.append([a["type"] for a in actions]) or act(actions, by)
    desk.desk.outbox = [{"type": "offer", "gigId": f"g{i}", "driverId": "d1"} for i in range(40)]
    desk.desk.take(world.events()[0])  # its quote joins the outbox behind the offers
    desk.desk.send()
    assert calls == [["quote"], ["offer"] * live.OFFER_BURST]
    assert [by for _, _, by in world.quotes["R1"]] == ["desk"]
    # The offers beyond the burst wait in the outbox, so the kit does not sleep for tokens, and go as the tokens come back.
    assert [a["gigId"] for a in desk.desk.outbox] == [f"g{i}" for i in range(live.OFFER_BURST, 40)]
    time.sleep(11 / live.OFFER_RATE)
    desk.desk.send()
    desk.stop()
    assert calls[2] == ["offer"] * 10 and desk.desk.outbox == []


def test_the_desk_counts_the_429_answers_that_the_kit_waits_out():
    client = live.Client(url="http://127.0.0.1:9", key="k")
    answers = iter([(429, {"Retry-After": "1"}, b""), (429, {"Retry-After": "1"}, b""), (200, {}, b"[]")])
    client._send = lambda *args: next(answers)
    before = live.THROTTLED.count
    assert live.THROTTLED.watch(client).worlds() == []
    assert live.THROTTLED.count - before == 2
