"""Tests of the cap on the cars to collect on one day (`due_cap`, `due_cap_wave`) and of the charging stop by route (`charge_km`)."""
from __future__ import annotations

from spreadlab import policy

from test_harness import MAP, ROSTER, request

# Every road takes 120 minutes, so next_day's last pickup (2520) falls on Tuesday and within_3_days' (5400) on Thursday.
OPTIONS = ((("next_day", 2640), ("within_3_days", 5520)))
DAY = 1440


def desk(**params) -> policy.Policy:
    return policy.Policy(None, 8, 500, {"quote_share": 1, "price": 1.5, **params}, ROSTER, MAP)


def win(d: policy.Policy, id_: str, last_pickup: int) -> None:
    req = request(id_)
    d.quote(req)
    d.win({"id": id_, "legs": req["legs"], "deliveredAt": [None], "deadline": last_pickup + 120, "option": "next_day", "lastPickupAt": last_pickup})


def quoted(d: policy.Policy, id_: str, options=OPTIONS) -> dict:
    d.quote(request(id_, options=options))
    return d.decisions[id_]


def test_a_full_day_loses_only_its_own_option_until_a_car_is_delivered():
    d = desk(due_cap=2)
    win(d, "W1", 2500)
    assert quoted(d, "R1")["prices"].keys() == {"next_day", "within_3_days"}  # one order due on Tuesday: room for another
    win(d, "W2", 5000)  # an order due on Thursday does not count for Tuesday
    assert quoted(d, "R2")["prices"].keys() == {"next_day", "within_3_days"}
    win(d, "W3", 2000)
    assert quoted(d, "R3") == {"declined": None, "prices": {"within_3_days": 15000}}
    assert quoted(d, "R4", options=(("next_day", 2640),))["declined"] == "day_full"
    d.delivered("W1", 0, 1800)
    assert quoted(d, "R5")["prices"].keys() == {"next_day", "within_3_days"}


def test_a_cancelled_order_frees_its_day():
    d = desk(due_cap=1)
    win(d, "W1", 2500)
    assert quoted(d, "R1")["prices"].keys() == {"within_3_days"}
    d.handle({"kind": "order_cancelled", "orderId": "W1", "at": 900, "seq": 0})
    assert quoted(d, "R2")["prices"].keys() == {"next_day", "within_3_days"}


def test_the_cap_lifts_after_a_night_with_a_wave_of_drops_in_its_first_hour():
    d = desk(due_cap=1, due_cap_wave=3)
    win(d, "W1", 2500)
    drop = {"kind": "gig_dropped", "gigId": "g1", "driverId": "d1", "seq": 0}
    for at in (DAY + 59, DAY + 59, DAY + 60, 2 * DAY + 10):  # two in Tuesday's first hour, one after it, one on Wednesday's: no wave
        d.handle({**drop, "at": at})
    assert quoted(d, "R1")["prices"].keys() == {"within_3_days"}
    d.handle({**drop, "at": DAY + 30})  # the third in Tuesday's first hour
    assert quoted(d, "R2")["prices"].keys() == {"next_day", "within_3_days"}


def test_the_charging_stop_goes_only_on_routes_over_charge_km():
    def charging(**params) -> bool:
        d = desk(read_notes=True, **params)
        req = request("R1")
        req["legs"] = [{**req["legs"][0], "car": {"premium": False, "electric": True, "chargePercent": 20}}]
        d.quote(req)
        d.win({"id": "R1", "legs": req["legs"], "deliveredAt": [None], "deadline": 2640, "option": "next_day", "lastPickupAt": 2520})
        return next(s for s in d.outbox[-1]["stops"] if s["kind"] == "pickup")["withCharging"]
    # The harness's roads are 100 km
    assert charging() and charging(charge_km=90) and not charging(charge_km=100)
