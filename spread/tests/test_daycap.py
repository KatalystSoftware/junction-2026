"""Tests of the cap on the cars to collect on one day (daycap.py)."""
from __future__ import annotations

from spreadlab import daycap, policy

from test_harness import MAP, ROSTER, request

# Every road takes 120 minutes, so next_day's last pickup (2520) falls on Tuesday and within_3_days' (5400) on Thursday.
OPTIONS = (("next_day", 2640), ("within_3_days", 5520))


def desk(**params) -> daycap.DayCapPolicy:
    return daycap.DayCapPolicy(None, 8, 500, {"quote_share": 1, "price": 1.5, **params}, ROSTER, MAP)


def win(d: policy.Policy, id_: str, last_pickup: int) -> None:
    req = request(id_)
    d.quote(req)
    d.win({"id": id_, "legs": req["legs"], "deliveredAt": [None], "deadline": last_pickup + 120, "option": "next_day", "lastPickupAt": last_pickup})


def quoted(d: policy.Policy, id_: str, options=OPTIONS) -> dict:
    d.quote(request(id_, options=options))
    return d.decisions[id_]


def test_without_a_cap_the_quotes_are_the_policys():
    plain, capped = policy.Policy(None, 8, 500, {"quote_share": 1, "price": 1.5}, ROSTER, MAP), desk()
    for d in (plain, capped):
        win(d, "W1", 2500)
    assert quoted(capped, "R1") == quoted(plain, "R1") == {"declined": None, "prices": {"next_day": 15000, "within_3_days": 15000}}


def test_a_full_day_loses_only_its_own_option_until_a_car_is_delivered():
    d = desk(day_cap=2)
    win(d, "W1", 2500)
    assert quoted(d, "R1")["prices"].keys() == {"next_day", "within_3_days"}  # one order due on Tuesday: room for another
    win(d, "W2", 5000)  # an order due on Thursday does not count for Tuesday
    assert quoted(d, "R2")["prices"].keys() == {"next_day", "within_3_days"}
    win(d, "W3", 2000)
    assert quoted(d, "R3") == {"declined": None, "prices": {"within_3_days": 15000}}
    assert quoted(d, "R4", options=(("next_day", 2640),))["declined"] == "day_full"
    d.delivered("W1", 0, 1800)
    assert quoted(d, "R5")["prices"].keys() == {"next_day", "within_3_days"}
