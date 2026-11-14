"""Tests of the note watcher (watch.py): what it corrects by itself, and that the desk never waits for it."""
from __future__ import annotations

import json
import time

from spreadlab import live, notes, replay, watch
from spreadlab.variants import VARIANTS

from test_harness import MAP, ROSTER, request

DAY, HOUR = 1440, 60
VOCABULARY = watch.Vocabulary({"words": ["auto", "valmis", "huomenna", "klo", "kilvet", "manuaali"], "patterns": [watch.pattern_hash("auto valmis huomenna klo 00")],
                               "topics": {"closing": 0.02}})


def test_a_fix_adds_plates_and_a_manual_licence_and_moves_the_pickup_later_never_earlier():
    asked = request("R1", arrivedAt=600, note={"text": "Valmis ensi tiistaina klo 9, ei aiemmin, manuaali. Asiakas odottaa perillä keskiviikkona klo 16."})
    asked["legs"][0]["pickup"]["window"] = {"from": 600, "to": 2000}  # Monday 10:00 on
    rules = notes.Facts(pickup_from=DAY + 12 * HOUR, plates=True)  # Tuesday 12:00, plates
    earlier = [{"fact": "ready", "day": "today", "time": "15:00"}, {"fact": "no_plates", "value": False}, {"fact": "manual", "value": False}]
    assert watch.safe_fix(earlier, rules, asked) == {}, "a fix never moves the pickup earlier and never takes plates or a licence away"
    # A weekday name is that weekday 2 to 6 days after the request (RULES.md): "tue" on a Monday is the Tuesday after next.
    later = [{"fact": "ready", "day": "tue", "time": "09:00"}, {"fact": "manual", "value": True}, {"fact": "deadline", "day": "wed", "time": "16:00"}]
    assert watch.safe_fix(later, rules, asked) == {"pickupFrom": 8 * DAY + 9 * HOUR, "manual": True}
    # On a day that the note does not name, it is no ready time either.
    assert watch.safe_fix([{"fact": "ready", "day": "thu", "time": "09:00"}], rules, asked) == {}
    # A time that the note gives for the delivery is no ready time, whatever the model says.
    delivery = [{"fact": "ready", "day": "wed", "time": "16:00"}]
    assert watch.safe_fix(delivery, rules, asked) == {}
    # Plates and a manual gearbox need the note's own words: here it has words for the gearbox and none for plates.
    asked["note"] = {"text": "Kolme polkimea ja kytkin. Avain tiskiltä, auto ruudussa 22."}
    assert watch.safe_fix([{"fact": "no_plates", "value": True}, {"fact": "manual", "value": True}], notes.Facts(), asked) == {"manual": True}


def test_an_answer_counts_only_as_a_yes_or_a_no_with_known_facts():
    assert watch.parse("Sure! I think so.") is None
    assert watch.parse('{"answer": "maybe"}') is None
    assert watch.parse('{"answer": "Yes", "problems": [{"fact": "manual", "value": true}]}') == {"answer": "yes", "problems": []}
    assert watch.parse('```json\n{"answer": "no", "problems": [{"fact": "manual", "value": true}, {"fact": "colour"}]}\n```') == \
        {"answer": "no", "problems": [{"fact": "manual", "value": True}]}


def test_a_claude_model_is_asked_without_a_temperature_which_it_refuses_and_the_others_with_zero(monkeypatch):
    sent = []

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": '{"answer": "yes"}'}}]}).encode()

    monkeypatch.setattr(watch.urllib.request, "urlopen", lambda req, timeout: sent.append(json.loads(req.data)) or Reply())
    for model in ("claude-haiku-5-5", "nvidia/nemotron-3.5-lightning-30b-a3b"):
        assert watch.ask("Auto valmis.", {}, {}, "key", model=model)["answer"] == "yes"
    assert "temperature" not in sent[0] and sent[1]["temperature"] == 0


def test_vocabulary_tells_a_typo_from_a_new_word_and_a_new_sentence_from_a_known_one():
    news = VOCABULARY.score("Auto valmis huomenna klo 14. Kilvett puuttuu, manuaali.")
    assert news == {"typos": ["kilvett"], "newWords": ["puuttuu"], "newSentences": ["kilvett puuttuu, manuaali."]}


def test_drift_alerts_when_notes_talk_about_a_topic_far_more_than_in_the_archive_and_again_only_when_it_grows_by_half():
    drift = watch.Drift({"closing": 0.02})
    alerts = [drift.add(set()) for _ in range(60)] + [drift.add({"closing"}) for _ in range(12)] + [drift.add(set()) for _ in range(20)]
    raised = [(a["topic"], a["with"], a["notes"]) for found in alerts for a in found]
    assert raised == [("closing", 6, 66), ("closing", 10, 70)]  # 9% against 2%; then 14%, half as much again
    assert drift.end_day()["shares"] == {"closing": round(12 / 92, 4)}


def won_note(text: str):
    asked = request("R1", note={"text": text})
    order = {"id": "R1", "dealerId": "D01", "option": "next_day", "priceCents": 15000, "deadline": 2640, "legs": asked["legs"],
             "lastPickupAt": 2400, "status": "waiting", "deliveredAt": [None]}
    return [{"seq": 0, "at": 500, "kind": "price_request", "request": asked}, {"seq": 1, "at": 515, "kind": "order_won", "order": order}]


def says_no_plates(seconds: float):
    def verify(text, read, known):
        time.sleep(seconds)
        return {"answer": "no", "problems": [{"fact": "no_plates", "value": True}], "seconds": seconds}
    return verify


def step(desk: live.Live, world: replay.Replay, minute: int) -> None:
    world.clock.saw(minute)
    for event in world.events(after=desk.desk.seq):
        desk.desk.take(event)
    desk.desk.send()


def answers(desk: live.Live, wait: float = 4.0) -> None:
    """The desk's loop, as far as the note watcher goes: until its first answer."""
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        desk.desk.release_due()
        desk.desk.send()
        for result in desk.watcher.results():
            desk.desk.correct(result)
            desk.desk.send()
            return
        time.sleep(0.02)
    raise AssertionError("the watcher did not answer")


def test_a_won_notes_first_post_waits_for_the_answer_and_goes_with_plates(tmp_path):
    world = replay.Replay(won_note("Registration tags are off this one."), ROSTER, ends_at=20000, start=506, speed=0.001)
    desk = live.Live(world, world.guard_act, world.minute, 8, VARIANTS[live.VARIANT], MAP, tmp_path, echo=False,
                     watcher=lambda log, folder: watch.Watcher(log, folder, says_no_plates(0.3), VOCABULARY, echo=False))
    desk.join()
    step(desk, world, 516)
    assert not world.gigs, "the first post waits for the model"
    answers(desk)
    desk.stop()
    assert list(world.gigs) == ["g1"] and world.gigs["g1"]["stops"][0]["withPlates"] is True


def test_when_the_answer_is_late_the_rules_post_goes_and_a_no_posts_the_car_again_with_plates(tmp_path):
    world = replay.Replay(won_note("Registration tags are off this one."), ROSTER, ends_at=20000, start=506, speed=0.001)
    desk = live.Live(world, world.guard_act, world.minute, 8, VARIANTS[live.VARIANT], MAP, tmp_path, echo=False,
                     watcher=lambda log, folder: watch.Watcher(log, folder, says_no_plates(live.HOLD_SECONDS + 0.5), VOCABULARY, echo=False))
    desk.join()
    step(desk, world, 516)
    time.sleep(live.HOLD_SECONDS + 0.1)
    desk.desk.release_due()
    desk.desk.send()
    assert list(world.gigs) == ["g1"] and world.gigs["g1"]["stops"][0]["withPlates"] is False, "a late answer leaves the rules' post"
    answers(desk)
    desk.stop()
    assert world.gigs["g1"]["status"] == "withdrawn" and world.gigs["g2"]["stops"][0]["withPlates"] is True
    review = [json.loads(line) for line in open(tmp_path / "review.jsonl")]
    assert [(r["orderId"], r["rules"]["no_plates"], r["problems"], r["fix"]) for r in review] == \
        [("R1", False, [{"fact": "no_plates", "value": True}], {"plates": True})]


def test_a_note_that_was_not_checked_when_the_desk_stopped_is_checked_when_it_starts_again(tmp_path):
    world = replay.Replay(won_note("Registration tags are off this one."), ROSTER, ends_at=20000, start=506, speed=0.001)
    desk = lambda verify: live.Live(world, world.guard_act, world.minute, 8, VARIANTS[live.VARIANT], MAP, tmp_path, echo=False,
                                    watcher=lambda log, folder: watch.Watcher(log, folder, verify, VOCABULARY, echo=False))
    first = desk(says_no_plates(30))  # the model has not answered when the desk stops
    first.join()
    step(first, world, 516)
    first.store.save(first.desk)
    first.stop()
    second = desk(says_no_plates(0))
    second.join()
    answers(second)
    second.stop()
    assert world.gigs["g1"]["status"] == "withdrawn" and world.gigs["g2"]["stops"][0]["withPlates"] is True


def test_a_fix_that_comes_after_a_driver_booked_the_gig_waits_for_the_cars_next_post(tmp_path):
    events = won_note("Registration tags are off this one.") + [{"seq": 2, "at": 520, "kind": "gig_booked", "gigId": "g1", "driverId": "d1", "feeCents": 9000}]
    world = replay.Replay(events, ROSTER, ends_at=20000, start=506, speed=0.001)
    desk = live.Live(world, world.guard_act, world.minute, 8, VARIANTS[live.VARIANT], MAP, tmp_path, echo=False,
                     watcher=lambda log, folder: watch.Watcher(log, folder, says_no_plates(live.HOLD_SECONDS + 0.5), VOCABULARY, echo=False))
    desk.join()
    step(desk, world, 516)
    time.sleep(live.HOLD_SECONDS + 0.1)
    desk.desk.release_due()  # the answer is late: the rules' post goes
    desk.desk.send()
    step(desk, world, 521)  # a driver books g1 before the model answers
    answers(desk)
    desk.stop()
    assert list(world.gigs) == ["g1"] and world.gigs["g1"]["status"] == "booked", "a booked gig is not taken from its driver"
    desk.desk.post(desk.desk.orders["R1"], [0])  # its next post, after a failed visit, brings plates
    assert desk.desk.outbox[-1]["stops"][0]["withPlates"] is True


def test_a_driver_who_books_the_gig_as_the_desk_withdraws_it_keeps_the_car_and_no_second_gig_is_posted(tmp_path):
    events = won_note("Registration tags are off this one.") + [{"seq": 2, "at": 520, "kind": "gig_booked", "gigId": "g1", "driverId": "d1", "feeCents": 9000}]
    world = replay.Replay(events, ROSTER, ends_at=20000, start=506, speed=0.001)
    desk = live.Live(world, world.guard_act, world.minute, 8, VARIANTS[live.VARIANT], MAP, tmp_path, echo=False,
                     watcher=lambda log, folder: watch.Watcher(log, folder, says_no_plates(live.HOLD_SECONDS + 0.5), VOCABULARY, echo=False))
    desk.join()
    step(desk, world, 516)
    time.sleep(live.HOLD_SECONDS + 0.1)
    desk.desk.release_due()  # the answer is late: the rules' post goes
    desk.desk.send()
    world.clock.saw(521)  # the world has the booking; the desk has not read it when the model answers
    world.events()
    answers(desk)
    desk.stop()
    assert list(world.gigs) == ["g1"] and world.gigs["g1"]["status"] == "booked", "the booked car gets no second gig"
    assert desk.desk.fixes["R1"]["plates"] is True
