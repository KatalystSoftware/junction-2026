"""Tests of the day's correction with an offset for each dealer (dealer.py)."""
from __future__ import annotations

from spreadlab import dealer, policy

from test_harness import MAP, ROSTER, answer, request

DAY = 1440
price = lambda d, id_: d.decisions[id_]["prices"]["next_day"]


def desk(**params) -> dealer.DealerPolicy:
    return dealer.DealerPolicy(None, 8, 500, {"quote_share": 1, "curve": True, "learn": 0.16, **params}, ROSTER, MAP)


def test_without_dealer_sd_the_quotes_are_the_policys():
    plain, base = desk(), policy.Policy(None, 8, 500, {"quote_share": 1, "curve": True, "learn": 0.16}, ROSTER, MAP)
    for d in (plain, base):
        for n in range(6):
            answer(d, f"A{n}", n % 2 == 0, dealerId=f"D0{n % 2}")
        d.quote(request("R1", dealerId="D00"))
    assert price(plain, "R1") == price(base, "R1")


def test_a_dealer_that_refuses_gets_lower_quotes_than_one_that_buys_and_keeps_part_of_it_the_next_morning():
    d, day_only = desk(dealer_sd=0.03, dealer_drift=0.02), desk()
    for x in (d, day_only):
        for n in range(12):  # the same day's answers: D01 refuses everything, D02 buys everything
            answer(x, f"A{n}", False, dealerId="D01")
            answer(x, f"B{n}", True, dealerId="D02")
        for who in ("D01", "D02", "D99"):
            x.quote(request(f"M{who}", dealerId=who))
        for who in ("D01", "D02", "D99"):
            x.quote(request(f"T{who}", dealerId=who, arrivedAt=DAY + 500, respondBy=DAY + 515, referenceFeeCents=5000))  # a cheap car: its price follows the shift closely
    assert price(d, "MD01") < price(day_only, "MD01") == price(day_only, "MD02") < price(d, "MD02")
    # Tuesday has no answers yet: the day's level starts again, the dealers keep their offsets, and a new dealer is at the market's level
    assert price(day_only, "TD01") == price(day_only, "TD99") == price(d, "TD99")
    assert price(d, "TD01") < price(d, "TD99") < price(d, "TD02")


def test_the_day_level_takes_what_all_dealers_share_so_an_offset_is_not_counted_twice():
    shared, day_only = desk(dealer_sd=0.03), desk()
    for x in (shared, day_only):
        for n in range(24):  # every dealer refuses alike: the day is dear, no dealer is
            answer(x, f"A{n}", False, dealerId=f"D{n % 4}")
        x.quote(request("R1", dealerId="D0"))
    # the dealer's quote moves no further than the day's correction alone would move it, give or take a step of the price grid
    assert abs(price(shared, "R1") - price(day_only, "R1")) <= 200
