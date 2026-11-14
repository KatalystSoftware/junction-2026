"""Tests of the quote's cost by the book's exposure to drops (`exposure`, exposure.py)."""
from __future__ import annotations

import pytest

from spreadlab import exposure, variants

from test_harness import MAP, request

DAY = 1440
# 700 drivers in Helsinki, so loads per 100 drivers are those of a practice world; next_day's last pickup (2520) falls on Tuesday and
# within_3_days' (5400) on Thursday: every road takes 120 minutes.
ROSTER = [{"id": f"d{i}", "homePlaceId": "helsinki", "rating": 4.9, "licence": "manual", "completedGigs": 60} for i in range(700)]
OPTIONS = (("next_day", 2640), ("within_3_days", 5520))


def desk(**params) -> exposure.ExposurePolicy:
    return exposure.ExposurePolicy(None, 8, 500, {**variants.VARIANTS["exposure-k4"], "quote_share": 1, **params}, ROSTER, MAP)


def win(d: exposure.ExposurePolicy, id_: str, last_pickup: int) -> None:
    req = request(id_)
    d.requests[id_] = req
    d.win({"id": id_, "legs": req["legs"], "deliveredAt": [None], "deadline": last_pickup + 120, "option": "next_day", "lastPickupAt": last_pickup})


def test_each_day_still_to_come_is_the_flu_day_as_likely_as_monday_which_the_desk_cannot_see():
    weights = exposure.weights({}, 12 * 60)  # Monday noon: Monday's night has passed with nothing held
    assert weights == pytest.approx({None: 0.2, 1: 0.2, 2: 0.2, 3: 0.2, 4: 0.2})


def test_a_wave_night_leaves_no_flu_day_to_come_and_a_calm_one_moves_its_weight_to_the_others():
    tuesday = DAY + 12 * 60
    after_wave = exposure.weights({1: (30, 10)}, tuesday)  # a third of Tuesday's held cars dropped in its first hour
    assert after_wave[None] > 0.999 and max(after_wave[d] for d in (2, 3, 4)) < 0.001
    after_calm = exposure.weights({1: (30, 1)}, tuesday)  # one of 30: a calm night
    assert after_calm[2] == pytest.approx(0.25, abs=0.01) and after_calm[None] == pytest.approx(0.25, abs=0.01)
    nothing_held = exposure.weights({1: (0, 0)}, tuesday)  # a night with nothing held tells nothing
    assert nothing_held[2] == pytest.approx(0.2) and nothing_held[None] == pytest.approx(0.4)


def test_exposure_refuses_the_rules_it_replaces():
    for clash in ({"slow_step": 0.8}, {"due_cap": 70}, {"late_cost": 150}, {"slow_model": "friday"}):
        with pytest.raises(ValueError):
            desk(**clash)


def test_an_empty_book_quotes_every_option():
    d = desk()
    d.quote(request("R1", options=OPTIONS))
    assert d.decisions["R1"]["prices"].keys() == {"next_day", "within_3_days"}


def test_a_crowded_day_that_may_be_the_flu_day_loses_its_option_to_the_slower_one():
    d = desk(max_unbooked=0)
    for k in range(120):  # 120 cars without a driver due on Tuesday, which may be the flu day
        win(d, f"W{k}", 2400)
    d.quote(request("R1", options=OPTIONS))
    assert d.decisions["R1"]["prices"].keys() == {"within_3_days"}
    book = d.book(d.params())
    tuesday = exposure.cost(book, 1, {**d.car(request("R2"), 2520, False, 0.0), "weight": 0.13}, 82, 4, 13000)
    thursday = exposure.cost(book, 3, {**d.car(request("R3"), 5400, False, 0.0), "weight": 0.13}, 82, 4, 13000)
    assert tuesday > thursday + 20


def test_the_nights_come_from_the_drops_of_held_cars_due_that_day():
    d = desk(max_unbooked=0)
    for k in range(3):
        win(d, f"W{k}", 2400)
    gigs = []
    for k, action in enumerate(a for a in d.outbox if a["type"] == "post"):  # the world accepts each post
        d.carry(action, f"g{k}")
        gigs.append(f"g{k}")
    for k, gig in enumerate(gigs):
        d.handle({"kind": "gig_booked", "gigId": gig, "driverId": f"d{k}", "feeCents": 9000, "at": 900, "seq": k})
    d.handle({"kind": "gig_dropped", "gigId": gigs[0], "driverId": "d0", "at": DAY + 10, "seq": 10})
    assert d.nights[1] == [3, 1]
    assert d.needs_since["W0"] == DAY + 10
