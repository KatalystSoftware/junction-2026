"""Tests of the parts that every comparison rests on: the seed lists, the policy's declines and the ledger's sums."""
from __future__ import annotations

import collections
import gzip
import json
import inspect
import math
import shutil

import pytest

from spreadlab import archive, catalogue, curve, ledger, notes, play, policy, report

MAP = {
    "places": [
        {"id": "helsinki", "name": "Helsinki", "lat": 60.17, "lon": 24.94},
        {"id": "vantaa", "name": "Vantaa", "lat": 60.29, "lon": 25.04},   # 15 km from Helsinki
        {"id": "tampere", "name": "Tampere", "lat": 61.50, "lon": 23.76},  # 160 km from Helsinki
    ],
    "roads": [{"from": a, "to": b, "km": 100.0, "minutes": 120} for a in ("helsinki", "vantaa", "tampere") for b in ("helsinki", "vantaa", "tampere")],
}
ROSTER = ([{"id": f"d{i}", "homePlaceId": "helsinki", "rating": 4.9, "licence": "manual", "completedGigs": 60} for i in range(8)]
          + [{"id": "t1", "homePlaceId": "tampere", "rating": 4.9, "licence": "manual", "completedGigs": 60}])


def stop(place: str, private: bool = False) -> dict:
    return {"placeId": place, "privateAddress": private, "window": {"from": 500, "to": 3000}, "hours": None}


def request(id_: str = "R1", pickup: str = "vantaa", options=(("same_day", 1200), ("next_day", 2640)), legs: int = 1, private: bool = False, **more) -> dict:
    leg = {"car": {"premium": False, "electric": False, "chargePercent": None}, "pickup": stop(pickup), "delivery": stop("helsinki", private)}
    return {"id": id_, "dealerId": "D01", "batchId": None, "arrivedAt": 500, "respondBy": 515, "legs": [leg] * legs,
            "options": [{"kind": kind, "deadline": deadline, "listPriceCents": 10000} for kind, deadline in options],
            "referenceFeeCents": 9000, "note": None, **more}


def desk(**params) -> policy.Policy:
    return policy.Policy(None, 8, 500, {"quote_share": 1, **params}, ROSTER, MAP)


def test_drivers_in_a_town_15_km_away_are_notified_and_160_km_away_are_not():
    notified = desk().notified
    assert notified == {"helsinki": 8, "vantaa": 8, "tampere": 1}


def test_policy_declines_by_a_quote_far_above_list_and_never_by_silence():
    d = desk()
    d.quote(request("R1", options=(("same_day", 1200),)))
    assert d.decisions["R1"]["declined"] == "same_day_only"
    assert d.outbox == [{"type": "quote", "requestId": "R1", "prices": {"same_day": 100000}}]


def test_policy_quotes_only_the_options_it_accepts():
    d = desk(price=1.5)
    d.quote(request("R1"))
    assert d.decisions["R1"] == {"declined": None, "prices": {"next_day": 15000}}


def test_same_day_is_quoted_dearer_only_beside_a_slower_option():
    d = desk(price=1.5, same_day=True, same_day_extra=0.1)
    d.quote(request("R1", options=(("same_day", 2640), ("next_day", 4080))))
    d.quote(request("R2", options=(("same_day", 2640),)))
    assert d.decisions["R1"]["prices"] == {"same_day": 16500, "next_day": 15000}
    assert d.decisions["R2"]["prices"] == {"same_day": 15000}


def test_floor_raises_only_the_quotes_that_are_under_it():
    # 1.5 x list is 15000. The typical fee of 9000 puts a floor of 1.5 at 13500, under the quote, and 12000 puts it at 18000, over it.
    d = desk(price=1.5, floor=1.5)
    d.quote(request("R1"))
    d.quote(request("R2", referenceFeeCents=12000))
    assert d.decisions["R1"]["prices"] == {"next_day": 15000}
    assert d.decisions["R2"]["prices"] == {"next_day": 18000}
    no_floor = desk(price=1.5)
    no_floor.quote(request("R2", referenceFeeCents=12000))
    assert no_floor.decisions["R2"]["prices"] == {"next_day": 15000}


def test_backlog_counts_the_won_cars_that_no_driver_holds_now():
    d = desk(max_unbooked=2)
    for id_ in ("R1", "R2"):
        d.quote(request(id_))
        d.win({"id": id_, "legs": request(id_)["legs"], "deliveredAt": [None], "deadline": 2640, "option": "next_day"})
    posts = [action for action in d.outbox if action["type"] == "post"]
    d.read_results(posts, [{"ok": True, "id": "G1"}, {"ok": True, "id": "G2"}])
    assert d.unbooked() == 2
    d.quote(request("R3"))
    assert d.decisions["R3"]["declined"] == "backlog"

    d.handle({"kind": "gig_booked", "gigId": "G1", "driverId": "d0", "at": 500})  # a booked car does not count
    d.quote(request("R4"))
    assert (d.unbooked(), d.decisions["R4"]["declined"]) == (1, None)
    d.handle({"kind": "gig_dropped", "gigId": "G1", "driverId": "d0", "at": 500})  # a dropped car counts again
    assert d.unbooked() == 2
    d.handle({"kind": "delivered", "orderId": "R2", "leg": 0, "at": 900})  # a delivered car never does
    assert d.unbooked() == 1


def test_a_tight_week_has_fewer_drivers_than_the_limit_and_takes_its_own_parameters():
    # The driver list has 9 drivers. A typical fee of 12000 puts a floor of 1.5 at 18000 and one of 1.7 at 20400.
    tight, at_limit = desk(floor=1.5, tight_drivers=10, when_tight={"floor": 1.7}), desk(floor=1.5, tight_drivers=9, when_tight={"floor": 1.7})
    for d in (tight, at_limit):
        d.quote(request("R1", referenceFeeCents=12000))
    assert (tight.tight, tight.decisions["R1"]["prices"]) == (True, {"next_day": 20400})
    assert (at_limit.tight, at_limit.decisions["R1"]["prices"]) == (False, {"next_day": 18000})


def won(d: policy.Policy, id_: str, deadline: int = 2640) -> None:
    d.quote(request(id_))
    d.win({"id": id_, "legs": request(id_)["legs"], "deliveredAt": [None], "deadline": deadline, "option": "next_day"})


def test_projected_on_time_share_counts_each_order_by_what_the_desk_sees_of_it():
    d = desk()
    assert d.on_time() == 1.0  # no orders yet
    for id_ in ("R1", "R2", "R3", "R4"):
        won(d, id_)
    posts = [action for action in d.outbox if action["type"] == "post"]
    d.read_results(posts, [{"ok": True, "id": f"G{n}"} for n in (1, 2, 3, 4)])
    assert d.on_time() == pytest.approx(1 - 4 * 0.15 / 4)  # four cars just won, no driver yet

    d.handle({"kind": "delivered", "orderId": "R1", "leg": 0, "at": 900})  # on time: no risk left
    d.handle({"kind": "delivered", "orderId": "R2", "leg": 0, "at": 950})  # before the deadline, but the account refunds it: late
    d.handle({"kind": "ledger", "at": 950, "line": {"kind": "late_refund", "cents": -3750, "orderId": "R2", "gigId": None}})
    d.handle({"kind": "gig_booked", "gigId": "G3", "driverId": "d0", "at": 500})  # a driver holds it
    assert d.on_time() == pytest.approx(1 - (0 + 1 + 0.03 + 0.15) / 4)

    d.now = 500 + 120  # R4 has waited two hours for a driver
    assert d.on_time() == pytest.approx(1 - (0 + 1 + 0.03 + 0.40) / 4)
    d.now = 2641  # past the deadline: the cars still out are late, whoever holds them
    assert d.on_time() == pytest.approx(1 - (0 + 1 + 1 + 1) / 4)


def test_a_desk_that_is_behind_takes_its_own_parameters_until_it_recovers():
    # One order waiting for a driver projects 85%. Behind under 97%, the desk stops quoting; a booking brings it to 97%.
    d = desk(min_on_time=0.97, when_behind={"quote_share": 0})
    won(d, "R1")
    d.read_results([action for action in d.outbox if action["type"] == "post"], [{"ok": True, "id": "G1"}])
    d.quote(request("R2"))
    assert d.decisions["R2"] == {"declined": "volume", "prices": {"same_day": 100000}, "onTime": 0.85}
    d.handle({"kind": "gig_booked", "gigId": "G1", "driverId": "d0", "at": 500})
    d.quote(request("R3"))
    assert d.decisions["R3"] == {"declined": None, "prices": {"next_day": 15000}, "onTime": 0.97}
    # The same order under a line of 85% is not behind: the line itself is allowed.
    calm = desk(min_on_time=0.85, when_behind={"quote_share": 0})
    won(calm, "R1")
    calm.quote(request("R2"))
    assert calm.decisions["R2"]["declined"] is None
    # With fewer orders than `behind_from`, one waiting order does not make the desk behind.
    few = desk(min_on_time=0.97, behind_from=2, when_behind={"quote_share": 0})
    won(few, "R1")
    few.quote(request("R2"))
    assert few.decisions["R2"]["declined"] is None
    won(few, "R3")
    few.quote(request("R4"))
    assert few.decisions["R4"]["declined"] == "volume"


def answer(d: policy.Policy, id_: str, win: bool, **more) -> None:
    """One serious quote and the dealer's answer to it."""
    d.quote(request(id_, **more))
    if win:
        d.handle({"kind": "order_won", "order": {"id": id_, "legs": request(id_)["legs"], "deliveredAt": [None], "deadline": 2640, "option": "next_day"}})
    else:
        d.handle({"kind": "order_lost", "requestId": id_})


def test_floor_follows_the_share_of_quotes_won_at_the_dealer_and_the_day():
    # The typical fee of 12000 puts the floors 1.5, 1.7 and 1.9 at 18000, 20400 and 22800. 1.5 x list is 15000.
    d = desk(price=1.5, floor=1.5, dealer_steps=[[0.2, 1.7], [0.4, 1.9]], day_floor={"1": 1.5})
    fee = {"referenceFeeCents": 12000}
    for n in range(4):
        answer(d, f"L{n}", False, **fee)
    answer(d, "W1", True, **fee)
    assert d.decisions["W1"]["prices"] == {"next_day": 18000}  # four answers are too few to count
    d.quote(request("R1", **fee))  # 1 of 5 won: the first step
    answer(d, "W2", True, dealerId="D02", **fee)  # another dealer's answers do not count here
    answer(d, "W3", True, **fee)
    d.quote(request("R2", **fee))  # 2 of 6 won, under 40%: still the first step
    answer(d, "W4", True, **fee)
    d.quote(request("R3", **fee))  # 3 of 7 won: the second step
    d.quote(request("R4", dealerId="D02", **fee))  # one answer at the other dealer
    d.quote(request("R5", arrivedAt=1440 + 500, respondBy=1440 + 515, **fee))  # Tuesday has its own floor
    assert [d.decisions[id_]["prices"]["next_day"] for id_ in ("R1", "R2", "R3", "R4", "R5")] == [20400, 20400, 22800, 18000, 18000]


def test_floor_rises_with_each_won_car_without_a_driver_beyond_the_first_ones():
    d = desk(price=1.5, floor=1.5, backlog_step=0.1, backlog_from=1)
    for id_ in ("R1", "R2", "R3"):
        won(d, id_)
    d.read_results([action for action in d.outbox if action["type"] == "post"], [{"ok": True, "id": f"G{n}"} for n in (1, 2, 3)])
    d.quote(request("R4", referenceFeeCents=12000))  # three cars wait, two beyond the first: 1.7 x 12000
    assert d.decisions["R4"]["prices"] == {"next_day": 20400}


def test_quote_rises_with_the_orders_the_dealer_had_on_time_and_a_late_one_halves_the_count():
    d = desk(price=1.5, trust=0.01)
    for id_ in ("R1", "R2", "R3"):
        won(d, id_)
        d.handle({"kind": "delivered", "orderId": id_, "leg": 0, "at": 2640})  # at the deadline is on time
    d.quote(request("R4"))
    d.quote(request("R5", dealerId="D02"))  # this dealer has had no order
    assert (d.trust, d.decisions["R4"]["prices"], d.decisions["R5"]["prices"]) == ({"D01": 3}, {"next_day": 15450}, {"next_day": 15000})
    won(d, "R6")
    d.handle({"kind": "delivered", "orderId": "R6", "leg": 0, "at": 2641})
    assert d.trust == {"D01": 1}
    for n in range(30):
        won(d, f"T{n}")
        d.handle({"kind": "delivered", "orderId": f"T{n}", "leg": 0, "at": 900})
    assert d.trust == {"D01": 25}


def test_random_quotes_stay_in_their_range_cover_it_and_differ_between_weeks():
    d = desk(explore=[1.1, 2.4], floor=1.3)
    multiples = []
    for n in range(200):
        d.quote(request(f"R{n}", referenceFeeCents=5000))  # the floor of 6500 is under every random quote
        multiples.append(d.decisions[f"R{n}"]["prices"]["next_day"] / 10000)
    assert 1.1 <= min(multiples) < 1.2 and 2.3 < max(multiples) <= 2.4
    assert d.decisions["R0"]["seen"] == {"trust": 0, "unbooked": 0, "answers": [0, 0], "shift": 0.0}
    other_week = desk(explore=[1.1, 2.4])
    other_week.quote(request("R0", arrivedAt=501, referenceFeeCents=5000))
    assert other_week.decisions["R0"]["prices"] != d.decisions["R0"]["prices"]
    floored = desk(explore=[1.1, 2.4], floor=3)
    floored.quote(request("R0"))
    assert floored.decisions["R0"]["prices"] == {"next_day": 27000}


def test_curve_quotes_where_the_margin_and_the_chance_balance_and_higher_for_a_dealer_with_orders_on_time():
    d = desk(curve=True, cost=1.4)
    d.quote(request("R1"))
    multiple = d.decisions["R1"]["prices"]["next_day"] / 10000
    # At the best price of a logistic curve, the margin is the price over (slope x the chance that the dealer does not buy).
    log_odds = curve.at_list(request("R1"), [{"kind": "next_day", "listPriceCents": 10000}], 0)
    assert multiple - 1.4 * 0.9 == pytest.approx(multiple / (curve.SLOPE * (1 - curve.chance(log_odds, multiple))), abs=0.02)
    dearer_to_serve = desk(curve=True, cost=1.6)
    dearer_to_serve.quote(request("R1"))
    assert dearer_to_serve.decisions["R1"]["prices"]["next_day"] > 10000 * multiple
    for n in range(10):
        won(d, f"T{n}")
        d.handle({"kind": "delivered", "orderId": f"T{n}", "leg": 0, "at": 900})
    d.quote(request("R2"))
    assert d.decisions["R2"]["prices"]["next_day"] > 10000 * multiple


def test_curve_price_follows_the_answers_of_the_day_and_starts_each_day_from_the_curve():
    plain, refused, bought, deaf = desk(curve=True, learn=0.16), desk(curve=True, learn=0.16), desk(curve=True, learn=0.16), desk(curve=True)
    for n in range(12):
        answer(refused, f"A{n}", False)
        answer(deaf, f"A{n}", False)
        answer(bought, f"A{n}", True, dealerId=f"D{n}")  # one order each, so that no dealer's quote rises by its orders
    for d in (plain, refused, bought, deaf):
        d.quote(request("R1", dealerId="D99"))
        d.quote(request("R2", dealerId="D99", arrivedAt=1440 + 500, respondBy=1440 + 515))
    price = lambda d, id_: d.decisions[id_]["prices"]["next_day"]
    assert price(refused, "R1") < price(plain, "R1") < price(bought, "R1")
    assert price(deaf, "R1") == price(plain, "R1")  # without `learn` the answers change nothing
    assert price(refused, "R2") == price(bought, "R2") == price(plain, "R2")  # Tuesday has no answers yet


def test_curve_price_follows_the_answers_for_the_pickup_town_on_top_of_those_of_the_day():
    day, town = desk(curve=True, learn=0.16), desk(curve=True, learn=0.16, learn_pickup=0.10)
    for d in (day, town):
        for n in range(12):  # today the dealers refuse cars from Vantaa and buy cars from Tampere
            answer(d, f"A{n}", False, dealerId=f"D{n}", pickup="vantaa")
            answer(d, f"B{n}", True, dealerId=f"E{n}", pickup="tampere")
        d.quote(request("R1", dealerId="D99", pickup="vantaa"))
        d.quote(request("R2", dealerId="D99", pickup="tampere"))
        d.quote(request("R3", dealerId="D99", pickup="helsinki"))  # no answers for cars from there: the day's level alone
    price = lambda d, id_: d.decisions[id_]["prices"]["next_day"]
    assert price(town, "R1") < price(day, "R1") and price(town, "R2") > price(day, "R2") and price(town, "R3") == price(day, "R3")


def test_cost_by_order_is_higher_for_a_long_lane_a_note_and_few_drivers():
    usual = curve.cost(curve.known(request(), [{"kind": "next_day"}], notified=80, unbooked=0))
    long_lane = curve.known(request(referenceFeeCents=25000), [{"kind": "next_day"}], notified=80, unbooked=0)
    few = curve.known(request(note={"text": "x"}), [{"kind": "next_day"}], notified=2, unbooked=0)
    assert 1.2 < usual < 1.4 < curve.cost(few) < curve.cost(long_lane) < 2.0
    assert curve.late(curve.known(request(), [{"kind": "next_day"}], 80, 0)) < 0.03 < 0.10 < curve.late(long_lane)
    flat, by_order = desk(curve=True), desk(curve=True, cost_by_order=True)
    for d in (flat, by_order):
        d.quote(request("R1", referenceFeeCents=7000))
        d.quote(request("R2", pickup="tampere", options=(("next_day", 2640),), note={"text": "x"}))  # one driver is notified there
    price = lambda d, id_: d.decisions[id_]["prices"]["next_day"]
    assert price(by_order, "R1") < price(flat, "R1")
    assert price(by_order, "R2") > price(flat, "R2")


def test_trust_value_lowers_the_quote_for_a_dealer_with_much_still_to_come_and_raises_it_where_a_late_order_would_cost_most():
    plain, d = desk(curve=True), desk(curve=True, trust_value=1)
    for desk_ in (plain, d):
        for n in range(12):
            desk_.quote(request(f"A{n}", arrivedAt=540, respondBy=555))  # a dealer with 12 requests in the first hour
        desk_.quote(request("B1", dealerId="D02", arrivedAt=540, respondBy=555))  # a dealer with one
        desk_.quote(request("C1", options=(("next_day", 7 * 1440 + 1200),), arrivedAt=4 * 1440 + 1080, respondBy=4 * 1440 + 1095))  # Friday 18:00: nothing is to come
    price = lambda desk_, id_: desk_.decisions[id_]["prices"]["next_day"]
    assert price(d, "A11") < price(d, "B1") < price(plain, "B1") == price(plain, "A11")
    assert price(d, "C1") == price(plain, "C1")
    # At 25 orders on time, one more adds nothing, and a late one halves the count.
    assert d.trust_worth(request("A0", arrivedAt=540), 25, 0.1, 10000) < 0 < d.trust_worth(request("A0", arrivedAt=540), 0, 0.1, 10000)


def test_shift_of_the_curve_is_found_from_answers_and_stays_near_zero_with_few():
    random = __import__("random").Random(1)
    quotes = [(2.0 - curve.SLOPE * math.log(random.uniform(1.1, 2.0))) for _ in range(4000)]
    answers = [(z, random.random() < curve.chance(2.0, math.exp((2.0 - z) / curve.SLOPE), 0.2)) for z in quotes]  # dealers accept 20% more
    assert curve.shift(answers, sd=1.0) == pytest.approx(0.2, abs=0.02)
    assert 0 < curve.shift(answers[:5], sd=0.05) < curve.shift(answers[:5], sd=1.0)


def posted(d: policy.Policy, last_pickup: int, id_: str = "R1") -> list[tuple[int, int]]:
    """The fees of the gig that the desk posts for a won order, as (minute, cents)."""
    d.quote(request(id_))
    d.win({"id": id_, "legs": request(id_)["legs"], "deliveredAt": [None], "deadline": last_pickup + 120, "option": "next_day", "lastPickupAt": last_pickup})
    return [(step["at"], step["feeCents"]) for step in d.outbox[-1]["schedule"]]


def test_fees_rise_to_the_cap_and_hold_and_jump_once_when_drivers_plan_the_day_of_the_last_pickup():
    day = 24 * 60
    assert posted(desk(fee=1.0), day + 14 * 60) == [(500 + 60 * k, 9000 + 900 * k) for k in range(6)]  # the starter's schedule
    assert posted(desk(fee=1.0, fee_cap=1.2), day + 14 * 60) == [(500, 9000), (560, 9900), (620, 10800)]
    assert posted(desk(fee=1.0, fee_cap=1.0), day + 14 * 60) == [(500, 9000)]
    # A last pickup after 10:00 is planned at 04:30 that morning, an earlier one at 16:00 the day before.
    assert posted(desk(fee=1.0, fee_cap=1.2, jump=1.5), day + 14 * 60) == [(500, 9000), (560, 9900), (620, 10800), (day + 270, 13500)]
    assert posted(desk(fee=1.0, fee_cap=1.2, jump=1.5), day + 9 * 60) == [(500, 9000), (560, 9900), (620, 10800), (960, 13500)]
    assert posted(desk(fee=1.0, fee_cap=1.2, jump=1.5), 14 * 60) == [(500, 9000), (560, 9900), (620, 10800)]  # that morning has passed
    assert posted(desk(fee=1.0, jump=1.2), day + 9 * 60) == [(500 + 60 * k, 9000 + 900 * k) for k in range(6)]  # a jump under the fee of that minute does nothing


def test_a_dropped_gig_starts_its_fees_again_unless_the_deadline_warning_has_come():
    d = desk(fee=1.0, drop_fee=1.1)
    assert "gig_dropped" in d.wake_on and "gig_dropped" not in desk().wake_on
    posted(d, 2000)
    d.read_results([d.outbox[-1]], [{"ok": True, "id": "G1"}])
    d.handle({"kind": "gig_booked", "gigId": "G1", "driverId": "d0", "at": 500})
    d.now, d.outbox = 1100, []
    d.handle({"kind": "gig_dropped", "gigId": "G1", "driverId": "d0", "at": 500})
    assert d.outbox == [{"type": "reprice", "gigId": "G1", "schedule": [{"at": 1100 + 60 * k, "feeCents": int(9900 * (1 + k / 10) + 0.5)} for k in range(6)]}]
    d.handle({"kind": "gig_booked", "gigId": "G1", "driverId": "d0", "at": 500})
    d.urgent.add("R1")
    d.outbox = []
    d.handle({"kind": "gig_dropped", "gigId": "G1", "driverId": "d0", "at": 500})
    assert d.outbox == [] and d.unbooked() == 1


def test_fees_and_cost_follow_the_usual_fee_of_a_known_lane(monkeypatch):
    monkeypatch.setattr(policy, "LANES", {"vantaa>helsinki": math.log(8000)})
    assert posted(desk(fee=1.0, fee_cap=1.0, lane_fee=True), 2000) == [(500, 8000)]
    assert posted(desk(fee=1.0, fee_cap=1.0), 2000) == [(500, 9000)]
    d = desk(fee=1.0, fee_cap=1.0, lane_fee=True, private=True)
    d.quote(request("R2", private=True))  # a lane that the table does not have keeps the request's typical fee
    d.win({"id": "R2", "legs": request("R2", private=True)["legs"], "deliveredAt": [None], "deadline": 2640, "option": "next_day", "lastPickupAt": 2000})
    assert d.outbox[-1]["schedule"] == [{"at": 500, "feeCents": 9000}]
    price = lambda **params: desk(curve=True, cost=1.2, **params)  # noqa: E731
    quotes = []
    for params in ({}, {"lane_fee": True}):
        d = price(**params)
        d.quote(request())
        quotes.append(d.decisions["R1"]["prices"]["next_day"])
    assert quotes[1] < quotes[0]  # the lane's usual fee is lower than this request's typical fee, so the order costs less


def test_long_drives_and_pickups_with_many_drivers_open_at_their_own_fee_and_long_drives_can_be_declined():
    assert posted(desk(fee=1.0, fee_cap=1.0, long_drive=100, long_fee=1.5), 2000) == [(500, 13500)]  # the roads of MAP take 120 minutes
    assert posted(desk(fee=1.0, fee_cap=1.0, long_drive=120, long_fee=1.5), 2000) == [(500, 9000)]
    assert posted(desk(fee=1.0, fee_cap=1.0, deep_drivers=8, deep_fee=0.9), 2000) == [(500, 8100), (560, 9000)]  # 8 drivers live near Vantaa; the cap is of the typical fee
    assert posted(desk(fee=1.0, fee_cap=1.0, deep_drivers=9, deep_fee=0.9), 2000) == [(500, 9000)]
    d = desk(max_drive=100)
    d.quote(request())
    assert d.decisions["R1"]["declined"] == "long"
    quotes = []
    for params in ({}, {"long_drive": 100, "long_cost": 1.7}):
        d = desk(curve=True, cost=1.2, **params)
        d.quote(request())
        quotes.append(d.decisions["R1"]["prices"]["next_day"])
    assert quotes[1] > quotes[0]
    quotes = []
    for params in ({}, {"private_cost": 1.7}):
        d = desk(curve=True, cost=1.2, private=True, **params)
        d.quote(request(private=True))
        quotes.append(d.decisions["R1"]["prices"]["next_day"])
    assert quotes[1] > quotes[0]


TUESDAY_NOON = 24 * 60 + 12 * 60


@pytest.mark.parametrize("text, pickup_from", [
    ("Huolto kesken, valmis huomenna klo 12.30. Haettava ennen klo 18.00", (2, 12, 30)),
    ("Noudettavissa aikaisintaan to klo 14. Soita ennen noutoa", (3, 14, 0)),
    ("Not ready before tmrw noon, not 1pm.", (2, 12, 0)),
    ("Car won't be ready until the day after tomorrow 3:30pm. Keys from reception", (3, 15, 30)),
    ("Auto valmis vasta huomenna puoli kymmeneltä, ei kun puoli yhdeksältä. Haettava ennen 18.00.", (2, 8, 30)),
    ("Voi noutaa huomenna klo 14.00 alkaen. Korjaus: klo 13.00. Vastaanottava liike auki arkisin klo 8.00 - 20.00.", (2, 13, 0)),
    ("Huolto kesken, valmis torstaina klo 14, ei kun perjantaina. Liike auki arkisin 9-19", (4, 14, 0)),
    ("Rahoitus vahvistuu huomenna puoli yhdeltä, vasta sitten saa hakea.", (2, 12, 30)),
    ("Lämnas ut efter betalning, tidigast i morgon kl 9.30", (2, 9, 30)),
    ("Buyer pays first, pickup from tomorrow 11:00, not 10:00.", (2, 11, 0)),
    ("Luovutus vasta kun maksettu, aikaisintaan klo 1600.", (1, 16, 0)),
    ("Asiakas noutaa huomenna kello 12, auton oltava silloin perillä. Soita 20 min ennen", None),
    ("Neljän jälkeen ei enää luovutuksia. Rengassarja takapenkillä, kulkee mukana.", None),
    ("Kohde auki arkisin 9-21. Valmis, voi hakea heti.", None),
    ("Toimitus perille viim. huomenna klo 19! Noudettavissa arkisin 7-20", None),
    ("Not ready before tmorrow 9:00. Collect before 21:00. Correction: 20:00", (2, 9, 0)),
    ("Hi there, ready for pickup from 12:30, booking ref 763890", (1, 12, 30)),
    ("Not ready before tomorrow 10:30, call the customer an hour before arrival!", (2, 10, 30)),  # the call names the delivery, not the ready time
    ("Huolto kesken, valmis torstaina klo 13.30. Korjaus: perjantaina.", (4, 13, 30)),  # a day corrected in a sentence of its own
    ("Valmiina huomenna puoli yhdeksästä alkaen, eikun ylihuomenna", (3, 8, 30)),
    ("Haettavissa ylihuomenna yhdeksän jälkeen. Pitää hakea ennen puolta neljää. Korjaus: puoli kolmelta!", (3, 9, 0)),  # corrects the closing time
    ("19.00 jalkeen ei enaa luovutuksia!", None),
])
def test_note_says_when_the_car_can_be_collected(text, pickup_from):
    expected = 0 if pickup_from is None else pickup_from[0] * 24 * 60 + pickup_from[1] * 60 + pickup_from[2]
    assert notes.read({"text": text}, TUESDAY_NOON).pickup_from == expected


@pytest.mark.parametrize("text, plates, manual", [
    ("Ei kilpiä, siirtokilvet mukaan.", True, False), ("Hello. Car has no pltaes, bring trade plates", True, False), ("inga skyltar på bilen.", True, False),
    ("Auto pihalla ruudussa 35, avain tiskiltä.", False, False), ("Huoltokirja ja rekisteriote autossa", False, False),
    ("Manuaalivaihteet, kuski tarvii manuaalikortin.", False, True), ("Automaattivaihteinen, ei manuaali", False, False), ("automaattivaihteinen, ei manuaail", False, False), ("manual gearbox", False, True),
    ("Huom mnuaali.", False, True), ("Hi. It's a maunal", False, True), ("käivaihteinen", False, True), ("Automatic, not a maanual", False, False),
    ("Poistettu rekisteristä, tarvitaan siirtokiilvet", True, False),
])
def test_note_says_plates_and_a_manual_licence(text, plates, manual):
    facts = notes.read({"text": text}, TUESDAY_NOON)
    assert (facts.plates, facts.manual) == (plates, manual)


def test_a_note_goes_into_the_first_posting_only_when_the_desk_reads_notes():
    note = {"text": "Ei kilpiä, siirtokilvet mukaan. Manuaali. Valmis huomenna klo 12. Haettava ennen klo 11.", "language": "fi"}
    for read in (False, True):
        d = desk(read_notes=read)
        d.quote(request(note=note))
        d.win({"id": "R1", "legs": request()["legs"], "deliveredAt": [None], "deadline": 4000, "option": "next_day", "lastPickupAt": 3800})
        action = d.outbox[-1]
        pickup = action["stops"][0]
        assert (pickup["withPlates"], action["audience"]["manualLicence"]) == (read, read)
        if read:  # ready on Tuesday at 12:00; the starter's closing time, 11:00 on Monday, would leave no time
            assert pickup["window"] == {"from": 24 * 60 + 12 * 60, "to": 3000}


def test_direct_offers_go_to_the_nearest_drivers_who_used_the_app_today_for_gigs_short_of_time():
    d = desk(fee=1.0, offer_hours=8, offer_fee=1.3)
    assert d.wake_at() == policy.NEVER
    posted(d, 500 + 6 * 60)  # the last pickup is 6 hours away
    d.read_results([d.outbox[-1]], [{"ok": True, "id": "G1"}])
    for driver in ("t1", "d0", "d1", "d2", "d3"):
        d.handle({"kind": "gig_viewed", "gigId": "G1", "driverId": driver, "at": 505})
    d.outbox = []
    d.look()
    assert d.outbox == [] and d.wake_at() == policy.NEVER  # the app has half an hour to find a driver first
    d.now = 530
    assert d.wake_at() == 545
    d.look()
    # 1.3 x the typical fee of 9000. The drivers in Helsinki are as near as each other, and nearer than the one in Tampere.
    assert d.outbox == [{"type": "offer", "gigId": "G1", "driverId": driver, "feeCents": 11700} for driver in ("d0", "d1", "d2")]
    d.now, d.outbox = 535, []
    d.look()
    assert d.outbox == []  # three offers are open
    d.now = 541
    d.look()
    assert [action["driverId"] for action in d.outbox] == ["d3", "t1"]  # nobody is asked twice for a gig
    d.handle({"kind": "gig_booked", "gigId": "G1", "driverId": "d3", "at": 542})
    assert d.wake_at() == policy.NEVER
    # At night nobody reads an offer: the desk looks again at 07:00.
    night = desk(fee=1.0, offer_hours=8)
    posted(night, 500 + 6 * 60)
    night.read_results([night.outbox[-1]], [{"ok": True, "id": "G1"}])
    night.handle({"kind": "gig_viewed", "gigId": "G1", "driverId": "d0", "at": 505})
    night.now, night.outbox = 23 * 60 + 5, []
    night.look()
    assert night.outbox == [] and night.wake_at() == 24 * 60 + 7 * 60
    # A gig whose last pickup is more than `offer_hours` away gets none.
    far = desk(fee=1.0, offer_hours=8)
    posted(far, 500 + 9 * 60)
    far.read_results([far.outbox[-1]], [{"ok": True, "id": "G1"}])
    far.handle({"kind": "gig_viewed", "gigId": "G1", "driverId": "d0", "at": 505})
    far.now, far.outbox = 540, []
    far.look()
    assert far.outbox == []
    far.now = 561  # now it is 8 hours away, and a driver who dropped the gig is not asked
    far.handle({"kind": "gig_booked", "gigId": "G1", "driverId": "d0", "at": 550})
    far.handle({"kind": "gig_dropped", "gigId": "G1", "driverId": "d0", "at": 555})
    far.handle({"kind": "gig_viewed", "gigId": "G1", "driverId": "d1", "at": 556})
    far.look()
    assert [action["driverId"] for action in far.outbox] == ["d1"]


def test_random_prices_for_a_kind_of_request_leave_the_other_requests_on_the_policy():
    d = desk(explore_private=[1.1, 2.4], explore_trade_in=[1.0, 2.0])
    d.quote(request("R1"))
    assert d.decisions["R1"] == {"declined": None, "prices": {"next_day": 15000}} and "R1" in d.asked
    d.quote(request("R2", private=True))
    d.quote(request("R3", private=True, legs=2))
    assert (d.decisions["R2"]["explored"], d.decisions["R3"]["explored"]) == ("private", "trade_in")
    assert 11700 <= d.decisions["R2"]["prices"]["next_day"] <= 24000 and 11700 <= d.decisions["R3"]["prices"]["next_day"] <= 20000
    assert "R2" not in d.asked and "R3" not in d.asked  # their answers do not move the day's level
    only = desk(explore_trade_in=[1.0, 2.0])
    only.quote(request("R2", private=True))
    only.quote(request("R3", private=True, legs=2))
    assert (only.decisions["R2"]["declined"], only.decisions["R3"]["declined"]) == ("private", None)


def test_a_rule_cannot_set_a_rule():
    with pytest.raises(ValueError, match="when_behind cannot set .*min_on_time"):
        desk(when_behind={"min_on_time": 0.5})
    with pytest.raises(ValueError, match="when_tight cannot set .*pirce"):
        desk(when_tight={"pirce": 1.4})


@pytest.mark.parametrize("params, made, reason", [
    ({}, {"legs": 2}, "trade_in"),
    ({}, {"private": True}, "private"),
    ({"min_notified": 5}, {"pickup": "tampere"}, "few_drivers"),
    # next_day leaves 2640 - 120 - 515 = 2005 minutes: one more is too much to ask
    ({"min_slack": 2006}, {}, "slack"),
    ({"quote_share": 0}, {}, "volume"),
])
def test_policy_decline_reasons(params, made, reason):
    d = desk(**params)
    d.quote(request("R1", **made))
    assert d.decisions["R1"]["declined"] == reason


def test_slack_of_a_trade_in_runs_to_the_customers_slot_and_does_not_wait_for_it():
    site = lambda place, start=500, end=3000: {"placeId": place, "privateAddress": False, "window": {"from": start, "to": end}, "hours": None}  # noqa: E731
    home = {"placeId": "helsinki", "privateAddress": True, "window": {"from": 900, "to": 960}, "hours": None}  # the customer is home from 15:00 to 16:00
    car = {"premium": False, "electric": False, "chargePercent": None}
    trade_in = request(options=(("same_day", 1200),))
    trade_in["legs"] = [{"car": car, "pickup": site("vantaa"), "delivery": home}, {"car": car, "pickup": home, "delivery": site("vantaa", 900, 1200)}]
    # A driver can set out at 08:35 and must by 14:00 to reach the slot's end after 120 minutes: 325 minutes.
    d = desk(trade_in=True, private=True, same_day=True)
    assert d.slack(trade_in, trade_in["options"][0]) == 325
    d.quote(trade_in)
    assert d.decisions["R1"]["declined"] is None
    tight = desk(trade_in=True, private=True, same_day=True, min_slack=330)
    tight.quote(trade_in)
    assert tight.decisions["R1"]["declined"] == "slack"


def test_a_kind_of_request_is_quoted_with_its_own_cost_fee_and_odds_and_a_trade_in_is_due_in_the_customers_slot():
    assert [policy.kind(q) for q in (request(), request(private=True), request(private=True, legs=2))] == ["", "private_delivery", "trade_in"]
    plain = desk(curve=True, cost=1.2)
    plain.quote(request("R1", private=True))
    assert plain.decisions["R1"]["declined"] == "private"
    price = {}
    for name, own in (("same", {}), ("dear", {"cost": 1.7}), ("unlikely", {"odds": -1.0})):
        d = desk(curve=True, cost=1.2, kinds={"private_delivery": own})
        d.quote(request("R1", private=True))
        d.quote(request("R2", private=True, legs=2))
        assert d.decisions["R2"]["declined"] == "trade_in"  # a kind that is not named stays declined
        price[name] = d.decisions["R1"]["prices"]["next_day"]
    assert price["dear"] > price["same"] > price["unlikely"]
    # The opening fee of the kind, and the customer's slot as the window of the new car's delivery.
    site = lambda place, start=500, end=3000: {"placeId": place, "privateAddress": False, "window": {"from": start, "to": end}, "hours": None}  # noqa: E731
    home = {"placeId": "helsinki", "privateAddress": True, "window": {"from": 900, "to": 960}, "hours": None}
    car = {"premium": False, "electric": False, "chargePercent": None}
    trade_in = request(options=(("same_day", 1200),))
    trade_in["legs"] = [{"car": car, "pickup": site("vantaa"), "delivery": home}, {"car": car, "pickup": home, "delivery": site("vantaa", 900, 1200)}]

    class World:
        def act(self, actions):
            return [{"ok": True, "id": "G1"} for _ in actions]

    d = desk(fee=1.0, fee_cap=1.0, same_day=True, read_notes=True, kinds={"trade_in": {"fee": 1.4}})
    d.world = World()
    d.quote(trade_in)
    assert d.decisions["R1"]["declined"] is None
    d.outbox = []
    sent = []
    d.read_results = lambda actions, results: sent.extend(actions) or policy.Desk.read_results(d, actions, results)
    d.win({"id": "R1", "legs": trade_in["legs"], "deliveredAt": [None, None], "deadline": 1200, "option": "same_day", "lastPickupAt": 840})
    stops = sent[0]["stops"]
    assert [stop["kind"] for stop in stops] == ["pickup", "delivery", "pickup", "delivery"]
    assert stops[1]["window"] == {"from": 900, "to": 960} and "window" not in stops[3]
    assert sent[0]["schedule"] == [{"at": 500, "feeCents": 12600}]  # one gig for both cars at 1.4 x the typical fee of 9000


def price(d: policy.Policy, id_: str = "R1", **more) -> dict:
    d.quote(request(id_, **more))
    return d.decisions[id_]["prices"]


def test_cost_follows_the_hours_to_find_a_driver_and_a_premium_car_costs_more():
    hours = [[6, 1.55], [8, 1.35], [12, 1.3], [30, 1.2]]
    # same_day by 1200 with a drive of 120 and an answer at 515 leaves 9.4 hours: the cost of 8 to 12 hours. next_day by 2640 leaves 33.4: `cost`.
    by_hours = desk(curve=True, same_day=True, cost=1.15, cost_hours=hours)
    assert price(by_hours) == price(desk(curve=True, same_day=True, cost=1.3))
    slow = (("next_day", 2640),)
    assert price(by_hours, "R2", options=slow) == price(desk(curve=True, same_day=True, cost=1.15), "R2", options=slow)
    short = (("same_day", 950),)  # 5.25 hours
    assert price(by_hours, "R3", options=short) == price(desk(curve=True, same_day=True, cost=1.55), "R3", options=short)
    assert price(by_hours, "R3", options=short) != price(desk(curve=True, same_day=True, cost=1.15), "R3", options=short)
    premium = request("R4", options=slow)
    premium["legs"] = [{**premium["legs"][0], "car": {"premium": True, "electric": False, "chargePercent": None}}]
    d = desk(curve=True, same_day=True, cost=1.15, cost_hours=hours, premium_cost=0.15)
    d.quote(premium)
    assert d.decisions["R4"]["prices"] == price(desk(curve=True, same_day=True, cost=1.3), "R4", options=slow)


def test_backlog_surcharge_counts_only_the_cars_due_within_its_hours():
    every, due = desk(curve=True, same_day=True, backlog_step=0.04), desk(curve=True, same_day=True, backlog_step=0.04, backlog_hours=24)
    for d in (every, due):
        for n, last in enumerate((600, 900, 5000, 6000)):  # two cars to collect within 24 hours of minute 500, two later
            won(d, f"T{n}")
            d.orders[f"T{n}"]["lastPickupAt"] = last
    assert every.unbooked() == 4 and due.unbooked(24) == 2
    assert price(every) == price(desk(curve=True, same_day=True, cost=1.4 + 0.16)) and price(due) == price(desk(curve=True, same_day=True, cost=1.4 + 0.08))
    assert price(every) != price(due)


def test_slack_at_the_limit_is_quoted():
    d = desk(min_slack=2005)
    d.quote(request("R1"))
    assert d.decisions["R1"]["declined"] is None


def test_unknown_parameter_is_an_error():
    with pytest.raises(ValueError, match="pirce"):
        desk(pirce=1.4)


def test_seed_lists_are_disjoint_cover_every_seed_and_mix_strata_in_every_prefix():
    # 90 weeks: tightness rises with the seed number and thin pickups cycle, so each of the 9 strata has 9 to 12 weeks.
    rows = [{"seed": f"s{i:02d}", "carsPerDriver": 1 + i / 100, "pickupShareFewNotified": (i % 9) / 10} for i in range(90)]
    lists = catalogue.split(rows)
    tune, holdout = lists["tune"], lists["holdout"]
    assert not set(tune) & set(holdout)
    assert sorted(tune + holdout) == [row["seed"] for row in rows]
    assert len(tune) == len(holdout) == 45
    tight = {row["seed"]: catalogue.tercile([r["carsPerDriver"] for r in rows], row["carsPerDriver"]) for row in rows}
    for seeds in (tune[:9], holdout[:9]):  # one walk through the strata: three weeks of each tightness
        assert collections.Counter(tight[seed] for seed in seeds) == {0: 3, 1: 3, 2: 3}


def run_of(lines: list[tuple[str, str, int]], won: list[str], quotes: dict[str, bool]) -> dict:
    """A played week of three requests, from account lines (order, kind, cents)."""
    requests = [request(id_) for id_ in ("R1", "R2", "R3")]
    events = [{"kind": "order_won", "at": 515, "order": {"id": id_, "option": "next_day", "priceCents": 15000}} for id_ in won]
    events += [{"kind": "gig_booked", "at": 520, "gigId": f"g{id_}", "driverId": "d1", "feeCents": 0} for id_ in won]
    events += [{"kind": "ledger", "at": 900, "line": {"kind": kind, "cents": cents, "orderId": id_, "gigId": None}} for id_, kind, cents in lines]
    truth = {"noteDeadline": None, "releasedAt": None, "needsPlates": False, "manualGearbox": False}
    margin = sum(cents for _, _, cents in lines)
    late = {id_ for id_, kind, _ in lines if kind == "late_refund"}
    return {
        "variant": "v", "seed": "s", "events": events, "roster": ROSTER,
        "gigs": [{"id": f"g{id_}", "stops": [{"orderId": id_}]} for id_ in won],
        "reveal": {"requests": [{"request": r, "outcome": "won" if r["id"] in won else "lost"} for r in requests],
                   "orders": [{"orderId": id_, "legs": [truth]} for id_ in won]},
        "decisions": {id_: {"declined": None if serious else "volume"} for id_, serious in quotes.items()},
        "score": {"marginCents": margin, "wonOrders": len(won), "onTimeShare": (len(won) - len(late)) / len(won), "ranked": len(late) / len(won) <= 0.1},
    }


NEAR = {"helsinki": {"helsinki", "vantaa"}, "vantaa": {"helsinki", "vantaa"}, "tampere": {"tampere"}}


def test_ledger_rows_give_the_score_again_and_name_each_mistake():
    # v: R1 on time under its fees, R2 late, R3 declined. w: R1 at a higher price and a lower fee, R3 delivered at a profit.
    v = ledger.week(run_of([("R1", "revenue", 15000), ("R1", "driver_fee", -16000), ("R2", "revenue", 15000), ("R2", "driver_fee", -9000), ("R2", "late_refund", -3750)],
                           won=["R1", "R2"], quotes={"R1": True, "R2": True, "R3": False}), NEAR)
    w_run = run_of([("R1", "revenue", 17000), ("R1", "driver_fee", -10000), ("R3", "revenue", 15000), ("R3", "driver_fee", -11000)],
                   won=["R1", "R3"], quotes={"R1": True, "R2": True, "R3": True})
    for event in w_run["events"]:
        if event["kind"] == "order_won" and event["order"]["id"] == "R1":
            event["order"]["priceCents"] = 17000
    w = ledger.week(w_run, NEAR)
    assert ledger.check(v) == [] and ledger.check(w) == []
    found = {(m["request"], m["mistake"]): m["cents"] for m in ledger.mistakes(v, [w])}
    assert found == {
        (None, "week_not_ranked"): 1250,       # 1 of 2 late: the week's margin does not count
        ("R1", "won_below_fees"): 1000,
        ("R1", "priced_too_low"): 2000,
        ("R1", "overpaid_driver"): 6000,
        ("R2", "late:other"): 3750,
        ("R3", "declined_good_car"): 4000,
    }
    # w lost R2, but v delivered it late: not a good car
    assert {(m["request"], m["mistake"]) for m in ledger.mistakes(w, [v])} == set()


def test_check_reports_a_margin_that_the_rows_do_not_explain():
    played = ledger.week(run_of([("R1", "revenue", 15000)], won=["R1"], quotes={"R1": True, "R2": True, "R3": True}), NEAR)
    played["score"]["marginCents"] += 1
    assert "margin" in ledger.check(played)[0]


def test_policy_is_given_no_seed():
    # What a policy is built from and what each call hands it: none of it names the week.
    assert list(inspect.signature(policy.Policy.__init__).parameters) == ["self", "world", "level", "now", "params", "roster", "map_"]
    assert "seed" not in policy.DEFAULTS
    d = desk()
    d.quote(request("R1"))
    assert "seed" not in repr(vars(d)).lower()


def test_interval_is_of_the_paired_difference():
    # Weeks from 0 to 90,000 that the variant always beats by 100: paired, the interval is exactly 100.
    # Drawing the two columns apart would give an interval of tens of thousands.
    reference = [week * 10000 for week in range(10)]
    assert report.interval([margin + 100 - margin for margin in reference]) == (100, 100)
    # Better in 9 weeks of 10 and far worse in one: the mean is +100 and the interval includes 0.
    low, high = report.interval([1000] * 9 + [-8000])
    assert low < 0 < high
    # Better by 500 to 1,400 in every week: every draw has a mean inside that range, above 0.
    low, high = report.interval([500 + 100 * week for week in range(10)])
    assert 500 < low < 950 < high < 1400


def test_a_missing_or_failed_week_is_named(tmp_path, monkeypatch):
    monkeypatch.setenv("SPREAD_DATA", str(tmp_path))
    scores = {"a": {"s1": {"score": {}}, "s2": None, "s3": None}, "b": {"s1": {"score": {}}, "s2": {"score": {}}, "s3": {"score": {}}}}
    path = play.failure_path("a", "s3")
    path.parent.mkdir(parents=True)
    path.write_text("{}")
    assert report.missing(["a", "b"], ["s1", "s2", "s3"], scores, 8) == ["Missing for a: s2, s3. Failed when played: s3"]


def test_ledger_counts_the_weeks_a_mistake_occurs_in():
    rows = [{"mistake": "late", "situation": "snow", "eurosPerWeek": 30.0, "weeks": ["s1", "s2"]},
            {"mistake": "late", "situation": "normal", "eurosPerWeek": 10.0, "weeks": ["s2", "s3"]},
            {"mistake": "fees", "situation": "normal", "eurosPerWeek": 90.0, "weeks": ["s1"]}]
    assert ledger.by(rows, "mistake") == [("fees", 90.0, 1), ("late", 40.0, 3)]  # s2 is one week, not two
    assert ledger.by(rows, "situation") == [("normal", 100.0, 3), ("snow", 30.0, 2)]


@pytest.mark.skipif(shutil.which("zstd") is None, reason="needs the zstd command")
def test_archive_packs_only_what_is_new_and_unpacks_the_newest_copy_of_each_file(tmp_path):
    data, bundles, fresh = tmp_path / "data", tmp_path / "bundles", tmp_path / "fresh"

    def save(name: str, text: str) -> None:
        path = data / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(text.encode()) if name.endswith(".gz") else text.encode())

    save("scans/s1-L8.json.gz", '{"events": [1]}')
    save("runs/a/s1-L8.json.gz", '{"played": "first"}')
    save("runs/a/s1-L8.score.json", '{"score": 1}')
    assert archive.pack(data, bundles, "1")[1] == 3
    assert archive.pack(data, bundles, "2") is None  # nothing changed, so no second bundle
    save("runs/a/s1-L8.json.gz", '{"played": "again"}')  # the same week, played again
    save("runs/b/s1-L8.json.gz", '{"played": "b"}')
    first = (bundles / "1.tar.zst").read_bytes()
    assert archive.pack(data, bundles, "2")[1] == 2  # the changed week and the new one, not the scan or the score
    assert (bundles / "1.tar.zst").read_bytes() == first  # a bundle is never rewritten
    assert [name for name, _ in archive.members(bundles / "1.tar.zst")] == ["scans/s1-L8.json.gz", "runs/a/s1-L8.json.gz", "runs/a/s1-L8.score.json"]

    assert archive.unpack(bundles, fresh) == 4
    assert gzip.decompress((fresh / "runs/a/s1-L8.json.gz").read_bytes()) == b'{"played": "again"}'  # from the newer bundle
    assert gzip.decompress((fresh / "scans/s1-L8.json.gz").read_bytes()) == b'{"events": [1]}'
    assert (fresh / "runs/a/s1-L8.score.json").read_text() == '{"score": 1}'  # not gzipped in the data folder, so not here

    (fresh / "runs/b/s1-L8.json.gz").write_bytes(b"local")
    (fresh / "scans/s1-L8.json.gz").unlink()
    assert archive.unpack(bundles, fresh) == 1  # only the missing scan
    assert (fresh / "runs/b/s1-L8.json.gz").read_bytes() == b"local"  # a file the folder has is kept
    assert archive.unpack(bundles, fresh, force=True) == 4
    assert gzip.decompress((fresh / "runs/b/s1-L8.json.gz").read_bytes()) == b'{"played": "b"}'


def test_a_week_notes_the_lowest_and_highest_share_of_the_bucket(monkeypatch):
    monkeypatch.setenv("SPREAD_KEY", "test")
    client = play.CountingClient()
    limits = iter(["180", "150", "175"])

    def send(method, path, payload, headers):
        limit = next(limits)
        return 200, {"RateLimit-Policy": f'"practice";q={limit};w=1', "RateLimit-Limit": limit, "RateLimit-Remaining": "3",
                     "RateLimit-Reset": "0"}, b"{}"

    monkeypatch.setattr(client, "_send", send)
    for _ in range(3):
        client.call("GET", "/v1/worlds/w1")
    assert client.calls == 3 and client.rates == (150, 180)


def test_a_paired_check_stops_only_when_its_answer_cannot_change(tmp_path, monkeypatch):
    from spreadlab import stopcheck

    monkeypatch.setenv("SPREAD_DATA", str(tmp_path))
    seeds = stopcheck.expand("s-01..60")
    assert seeds[0] == "s-01" and seeds[-1] == "s-60" and len(seeds) == 60

    def save(variant, seed, euros, ranked=True):
        path = play.score_path(variant, seed)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"score": {"marginCents": euros * 100, "ranked": ranked}}))

    for i, seed in enumerate(seeds):
        save("ref", seed, 10_000 + 37 * (i % 7))
    for seed in seeds[:9] + seeds[10:12]:  # 11 weeks, but the 10th seed is missing: no look yet
        save("worse", seed, 8_000)
    assert stopcheck.decide("worse", "ref", seeds)[0] is False
    save("worse", seeds[9], 8_000)
    stop, why = stopcheck.decide("worse", "ref", seeds)
    assert stop and why.startswith("stop: worse") and "first 10 of 60" in why

    for seed in seeds[:20]:  # far ahead: plays on, the 1-in-60 rule needs the whole list
        save("better", seed, 12_000)
    assert stopcheck.decide("better", "ref", seeds)[0] is False

    save("risky", seeds[0], 0, ranked=False)  # 60 seeds allow one week under 90% on time ...
    assert stopcheck.decide("risky", "ref", seeds)[0] is False
    save("risky", seeds[30], 0, ranked=False)  # ... and a second is out, wherever it is in the list
    assert stopcheck.decide("risky", "ref", seeds) == (True, "stop: out, 2 weeks under 90% on time where 60 seeds allow 1")


def test_merge_1_counts_every_waiting_car_only_in_a_week_with_a_short_driver_list():
    from spreadlab import play
    from spreadlab.variants import VARIANTS
    params = VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-all"]
    roster = lambda n: [{**ROSTER[0], "id": f"x{i}"} for i in range(n)]  # noqa: E731
    short, full = (play.policy_class(params)(None, 8, 0, params, roster(n), MAP) for n in (700, 800))
    assert short.params()["queue_hours"] == 0 and full.params()["queue_hours"] == 24


def test_step04_changes_only_weeks_with_760_drivers_or_more():
    from spreadlab import play
    from spreadlab.variants import VARIANTS
    roster = lambda n: [{**ROSTER[0], "id": f"x{i}"} for i in range(n)]  # noqa: E731

    def desk(params, n):  # the parameters the week plays with
        played = play.policy_class(params)(None, 8, 0, params, roster(n), MAP).params()
        return {k: v for k, v in played.items() if k != "when_tight"}
    for name, base in (("t760all-step04", "fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-all"),
                       ("t760-q48-step04", "fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48"),
                       ("t760all-onward-step04", "fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-all-onward-q10-d760")):
        assert desk(VARIANTS[name], 700) == desk(VARIANTS[base], 700), name
        assert desk(VARIANTS[name], 800) == {**desk(VARIANTS[base], 800), "slow_step": 0.4}, name


def test_agg_max_changes_only_weeks_with_760_drivers_or_more():
    from spreadlab import play
    from spreadlab.variants import VARIANTS
    a1 = VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02-cap62-late100"]
    heavy = VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02-cap62-late100-agg-max"]
    roster = lambda n: [{**ROSTER[0], "id": f"x{i}"} for i in range(n)]  # noqa: E731

    def desk(params, n):  # the parameters the week plays with
        played = play.policy_class(params)(None, 8, 0, params, roster(n), MAP).params()
        return {k: v for k, v in played.items() if k != "when_tight"}
    assert desk(heavy, 700) == desk(a1, 700)
    full, base = desk(heavy, 800), desk(a1, 800)
    assert {k for k in full if full[k] != base[k]} == {"slow_step", "cost", "queue_hours", "max_unbooked", "min_slack", "kinds"}
    assert (full["slow_step"], full["cost"], full["queue_hours"], full["max_unbooked"], full["min_slack"]) == (0.0, 1.05, 6, 40, 240)


def test_a_rich_week_takes_its_own_parameters_and_the_others_play_the_variant():
    from spreadlab import play
    from spreadlab.variants import VARIANTS
    a17 = VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02-cap62-late100"]
    rich = {**a17, "rich_drivers": 850, "when_rich": {"cost": 1.05, "max_unbooked": 40, "pair_onward_cost": 0.9}}
    roster = lambda n: [{**ROSTER[0], "id": f"x{i}"} for i in range(n)]  # noqa: E731

    def desk(params, n):  # the parameters the week plays with
        played = play.policy_class(params)(None, 8, 0, params, roster(n), MAP).params()
        return {k: v for k, v in played.items() if k not in ("when_tight", "rich_drivers", "when_rich")}
    for n in (700, 800, 849):  # a tight week, and one under the rich line, play the variant without it
        assert desk(rich, n) == desk(a17, n), n
    full, base = desk(rich, 900), desk(a17, 900)
    assert {k: full[k] for k in full if full[k] != base[k]} == {"cost": 1.05, "max_unbooked": 40, "pair_onward_cost": 0.9}


def test_the_rungs_from_820_850_and_900_drivers_play_a17_below_and_the_rung_above():
    from spreadlab import play
    from spreadlab.variants import VARIANTS
    a17 = "fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02-cap62-late100"
    roster = lambda n: [{**ROSTER[0], "id": f"x{i}"} for i in range(n)]  # noqa: E731

    def desk(name, n):  # the parameters the week plays with
        params = VARIANTS[name]
        played = play.policy_class(params)(None, 8, 0, params, roster(n), MAP).params()
        return {k: v for k, v in played.items() if k not in ("when_tight", "rich_drivers", "when_rich")}
    for rung in ("vol110", "vol105", "cost10"):
        for drivers in (820, 850, 900):
            name = f"{a17}-{rung}-from{drivers}"
            for n in (700, 760, drivers - 1):
                assert desk(name, n) == desk(a17, n), (name, n)
            assert desk(name, drivers) == desk(f"{a17}-{rung}", drivers), name


def test_late80_from_820_plays_the_head_below_820_drivers_and_only_a_lower_late_cost_above():
    from spreadlab import play
    from spreadlab.variants import VARIANTS
    head = "fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss04-cap62-kindfee-onward-all-late100-h30-c11"
    roster = lambda n: [{**ROSTER[0], "id": f"x{i}"} for i in range(n)]  # noqa: E731

    def desk(name, n):  # the parameters the week plays with
        params = VARIANTS[name]
        played = play.policy_class(params)(None, 8, 0, params, roster(n), MAP).params()
        return {k: v for k, v in played.items() if k not in ("when_tight", "rich_drivers", "when_rich")}
    for n in (700, 760, 819):
        assert desk(f"{head}-late80-from820", n) == desk(head, n), n
    rich, base = desk(f"{head}-late80-from820", 820), desk(head, 820)
    assert {k: rich[k] for k in rich if rich[k] != base[k]} == {"late_cost": 80}
    assert rich["cost"] == 1.1 and rich["cost_hours"] == [[30, 1.2]]


def test_row_12_changes_only_the_thin_pair_knobs_of_row_11():
    from spreadlab import play
    from spreadlab.variants import VARIANTS
    head = "fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss04-cap62-kindfee-onward-all-late100-h30-c11"
    roster = lambda n: [{**ROSTER[0], "id": f"x{i}"} for i in range(n)]  # noqa: E731

    def desk(name, n):  # the parameters the week plays with
        params = VARIANTS[name]
        played = play.policy_class(params)(None, 8, 0, params, roster(n), MAP).params()
        return {k: v for k, v in played.items() if k not in ("when_tight", "rich_drivers", "when_rich", "thin_play")}

    def changed(a, b):
        return {k: a[k] for k in a if a[k] != b[k]}
    row, base = f"{head}-late80-from820-thin-hold12-left6", f"{head}-late80-from820"
    assert desk(row, 800) == desk(base, 800)
    assert changed(desk(row, 700), desk(base, 700)) == {"pair_hold": 12, "pair_left": 6}


def test_each_m41_row_adds_one_part_on_its_own_side_of_760_drivers():
    from spreadlab import play
    from spreadlab.variants import VARIANTS
    roster = lambda n: [{**ROSTER[0], "id": f"x{i}"} for i in range(n)]  # noqa: E731

    def desk(name, n):  # the parameters the week plays with
        params = VARIANTS[name]
        played = play.policy_class(params)(None, 8, 0, params, roster(n), MAP).params()
        return {k: v for k, v in played.items() if k not in ("when_tight", "rich_drivers", "when_rich", "thin_play")}
    rows = [("fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss04", {}),
            ("m41-a-late100", {800: {"late_cost": 100}, 900: {"late_cost": 100}}),
            ("m41-b-cap62-onward-all", {700: {"pair_more_drivers": 0, "due_cap": 62, "pair_open": True, "pair_onward": 0.8,
                                              "pair_late": True, "pair_onward_cost": 1.0}, 800: {"pair_more_drivers": 0},
                                        900: {"pair_more_drivers": 0}}),
            ("m41-c-h30-c11", {d: {"cost": 1.1, "cost_hours": [[30, 1.2]]} for d in (800, 900)}),
            ("m41-d-late80-from820", {900: {"late_cost": 80}}),
            ("m41-e-thin-hold12-left6", {700: {"pair_hold": 12, "pair_left": 6}}),
            ("m41-f-h24", {d: {"cost_hours": [[24, 1.2]]} for d in (800, 900)}),
            ("m41-g-ss03-760", {800: {"slow_step": 0.3}}),
            ("m41-h-ss025-820", {900: {"slow_step": 0.25}}),
            ("m41-i-long300-c10", {d: {"long_drive": 300, "long_cost": 1.0} for d in (800, 900)}),
            ("m41-j-kindfee", {d: {"kind_fees": True} for d in (700, 800, 900)}),
            ("m41-k-q18-760", {800: {"queue_hours": 18}}),
            ("m41-l-onq08-820", {900: {"pair_onward_cost": 0.8}})]
    for (below, _), (row, part) in zip(rows, rows[1:]):
        for n in (700, 800, 900):
            new, old = desk(row, n), desk(below, n)
            assert {k: new[k] for k in new if new[k] != old.get(k)} == part.get(n, {}), (row, n)


def test_each_m41x_row_plays_trackb_merge_4_1_at_760_to_819_drivers():
    from spreadlab import play
    from spreadlab.variants import VARIANTS
    roster = lambda n: [{**ROSTER[0], "id": f"x{i}"} for i in range(n)]  # noqa: E731

    def desk(name, n):  # the parameters the week plays with
        params = VARIANTS[name]
        played = play.policy_class(params)(None, 8, 0, params, roster(n), MAP).params()
        return {k: v for k, v in played.items() if k not in ("when_tight", "rich_drivers", "when_rich", "thin_play")}
    onward = {"pair_more_drivers": 0}  # onward pairs are on from 760 drivers already; this only turns them on below
    rows = [("fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss04", {}),
            ("m41x-b-cap62-onward-all", {700: {**onward, "due_cap": 62, "pair_open": True, "pair_onward": 0.8,
                                               "pair_late": True, "pair_onward_cost": 1.0}, 800: onward, 900: onward}),
            ("m41x-e-thin-hold12-left6", {700: {"pair_hold": 12, "pair_left": 6}}),
            ("m41x-d-late80-from820", {900: {"late_cost": 80}}),
            ("m41x-h-ss025-820", {900: {"slow_step": 0.25}}),
            ("m41x-l-onq08-820", {900: {"pair_onward_cost": 0.8}}),
            ("m41x-c-h30-c11-820", {900: {"cost": 1.1, "cost_hours": [[30, 1.2]]}}),
            ("m41x-f-h24-820", {900: {"cost_hours": [[24, 1.2]]}}),
            ("m41x-i-long300-c10-820", {900: {"long_drive": 300, "long_cost": 1.0}}),
            ("m41x-j-kindfee-thin-820", {700: {"kind_fees": True}, 900: {"kind_fees": True}})]
    # m41y: on m41x-h without m41x-l, then late_cost 100 at 760-819 (m41y-j, kind_fees, never plays)
    rows_y = [rows[4]] + [(n.replace("m41x-", "m41y-"), part) for n, part in rows[6:9]] + [
        ("m41y-l-ftop11-820", {900: {"fee_rules": [[0, 10 ** 6, 16, 10 ** 6, 0.8, 0.1, 1.1]]}}),
        ("m41y-m-late100-760", {800: {"late_cost": 100}})]  # m41y-k is the same late_cost row on m41y-i
    for (below, _), (row, part) in [*zip(rows, rows[1:]), *zip(rows_y, rows_y[1:])]:
        for n in (700, 761, 819, 820, 900):
            new, old = desk(row, n), desk(below, n)
            want = part.get(n, {}) if n in (700, 900) else part.get(800, {}) if n < 820 else part.get(900, {})
            assert {k: new[k] for k in new if new[k] != old.get(k)} == want, (row, n)


def test_ftop10_from_820_plays_m41y_l_below_820_drivers_and_only_a_lower_ladder_top_above():
    from spreadlab import play
    from spreadlab.variants import VARIANTS
    roster = lambda n: [{**ROSTER[0], "id": f"x{i}"} for i in range(n)]  # noqa: E731
    base, part_ = "m41y-l-ftop11-820", "m41y-l-ftop11-820-ftop10"

    def desk(name, n):  # the parameters the week plays with
        params = VARIANTS[name]
        played = play.policy_class(params)(None, 8, 0, params, roster(n), MAP).params()
        return {k: v for k, v in played.items() if k not in ("when_tight", "rich_drivers", "when_rich", "thin_play")}
    for n in (700, 760, 819):
        assert desk(part_, n) == desk(base, n), n
    part, head = desk(part_, 820), desk(base, 820)
    assert {k: part[k] for k in part if part[k] != head[k]} == {"fee_rules": [[0, 10 ** 6, 16, 10 ** 6, 0.8, 0.1, 1.0]]}
