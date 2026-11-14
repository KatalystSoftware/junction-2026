"""Tests of the rules that keep slow cars out of the backlog and move the waiting ones out of it."""
from __future__ import annotations

from spreadlab import curve, policy, slow
from test_harness import desk, posted, request, won

SLOW_ONLY = (("next_day", 2640),)


def chance(options) -> float:
    """The chance of a late order for the harness's request: 8 drivers notified, a drive of 120 minutes, 9 drivers in all."""
    q = request(options=options)
    return slow.chance(slow.known(q, curve.fastest(q["options"]), 8, 120, 9))


def price(d, id_="R1", **more):
    d.quote(request(id_, **more))
    return d.decisions[id_]["prices"]


def test_chance_of_a_late_order_rises_with_less_time_fewer_drivers_and_a_premium_car():
    q = request(options=SLOW_ONLY)
    base = slow.chance(slow.known(q, q["options"][0], 100, 120, 760))
    assert 0.005 < base < 0.02  # 33 hours, many drivers, a short drive, Monday, no note
    short = request(options=(("same_day", 900),))  # 4.4 hours
    assert slow.chance(slow.known(short, short["options"][0], 100, 120, 760)) > 4 * base
    assert slow.chance(slow.known(q, q["options"][0], 5, 120, 760)) > 2 * base
    assert slow.chance(slow.known(q, q["options"][0], 100, 120, 660)) > base
    premium = {**q, "legs": [{**q["legs"][0], "car": {"premium": True, "electric": False, "chargePercent": None}}]}
    assert slow.chance(slow.known(premium, q["options"][0], 100, 120, 760)) > 3 * base


def test_the_bar_for_a_slow_car_falls_as_the_backlog_fills():
    fast, slower = chance(SLOW_ONLY), chance((("same_day", 1200), ("next_day", 2640)))
    assert fast < 0.2 < slower < 0.5
    d = desk(same_day=True, slow_bar=[[1, 0.2], [2, 0.1]])
    d.quote(request("R1"))
    assert d.decisions["R1"]["declined"] is None  # an empty backlog takes any car
    won(d, "T1")
    d.quote(request("R2"))
    d.quote(request("R3", options=SLOW_ONLY))
    assert d.decisions["R2"]["declined"] == "slow" and d.decisions["R3"]["declined"] is None
    won(d, "T2")
    d.quote(request("R4", options=SLOW_ONLY))
    assert d.decisions["R4"]["declined"] == "slow"
    assert desk(same_day=True).decisions == {}  # off at its default
    plain = desk(same_day=True)
    won(plain, "T1"), won(plain, "T2")
    plain.quote(request("R4"))
    assert plain.decisions["R4"]["declined"] is None


def test_the_cost_rises_with_the_backlog_by_the_chance_that_the_car_is_late():
    d = desk(curve=True, same_day=True, slow_step=0.1)
    assert price(d) == price(desk(curve=True, same_day=True))  # no backlog, no surcharge
    won(d, "T1"), won(d, "T2")
    both = (("same_day", 1200), ("next_day", 2640))
    assert price(d, "R2") == price(desk(curve=True, same_day=True, cost=1.4 + 0.2 * chance(both)), "R2")
    assert price(d, "R3", options=SLOW_ONLY) == price(desk(curve=True, same_day=True, cost=1.4 + 0.2 * chance(SLOW_ONLY)), "R3", options=SLOW_ONLY)


def test_other_parameters_apply_while_the_backlog_is_filling():
    d = desk(same_day=True, full_from=2, when_full={"same_day": False})
    short = (("same_day", 1200),)
    won(d, "T1")
    d.quote(request("R1", options=short))
    assert d.decisions["R1"]["declined"] is None
    won(d, "T2")
    d.quote(request("R2", options=short))
    assert d.decisions["R2"]["declined"] == "same_day_only"


def test_fees_follow_the_drivers_notified_and_the_hours_left():
    rules = [[0, 10, 0, 12, 1.2, 0.2, 1.6], [0, 1000, 12, 10 ** 6, 0.9, 0.05, 1.0]]  # 8 drivers are notified in Vantaa
    assert posted(desk(fee=1.0, fee_cap=1.2, fee_rules=rules), 500 + 10 * 60) == [(500, 10800), (560, 12600), (620, 14400)]
    assert posted(desk(fee=1.0, fee_cap=1.2, fee_rules=rules), 500 + 25 * 60) == [(500, 8100), (560, 8550), (620, 9000)]
    assert posted(desk(fee=1.0, fee_cap=1.2, fee_rules=rules[:1]), 500 + 25 * 60) == [(500, 9000), (560, 9900), (620, 10800)]  # no rule fits


def test_a_filling_backlog_raises_the_fee_of_the_open_gigs_that_are_short_of_time_once():
    d = desk(fee=1.0, fee_cap=1.2, push_from=2, push_hours=24, push_fee=1.4)
    posted(d, 1100)
    d.read_results([d.outbox[-1]], [{"ok": True, "id": "G1"}])
    assert d.outbox[-1]["type"] == "post"  # one car without a driver: nothing to push
    posted(d, 5000, "R2")
    assert d.outbox[-1] == {"type": "reprice", "gigId": "G1", "schedule": [{"at": 500, "feeCents": 12600}]}
    d.read_results(d.outbox[-2:], [{"ok": True, "id": "G2"}, {"ok": True}])
    sent = len(d.outbox)
    posted(d, 5000, "R3")
    assert [a["type"] for a in d.outbox[sent:]] == ["quote", "post"]  # G1 was pushed already, and G2 is not due within 24 hours


def test_a_steeper_slope_lowers_the_price():
    assert price(desk(curve=True, same_day=True, slope_by=1.3))["next_day"] < price(desk(curve=True, same_day=True))["next_day"]


def test_the_cost_carries_the_chance_of_a_late_order_in_euros_and_later_cars_have_a_surcharge_of_their_own():
    assert price(desk(curve=True, same_day=True, late_cost=100), options=SLOW_ONLY) == price(desk(curve=True, same_day=True, cost=1.4 + 100 * chance(SLOW_ONLY) / 90), options=SLOW_ONLY)  # the typical fee is 90 euros
    d = desk(curve=True, same_day=True, backlog_step=0.04, backlog_hours=24, backlog_later=0.01)
    for n, last in enumerate((600, 900, 5000)):  # two cars to collect within 24 hours of minute 500, one later
        won(d, f"T{n}")
        d.orders[f"T{n}"]["lastPickupAt"] = last
    assert price(d) == price(desk(curve=True, same_day=True, cost=1.4 + 0.08 + 0.01))


def test_the_rule_of_90_percent_makes_a_safe_order_cheaper_down_to_the_typical_fee():
    by_rule = desk(curve=True, same_day=True, rule_cost=300)
    late = chance(SLOW_ONLY)  # 0.18 with the harness's 9 drivers: riskier than the rule, so dearer
    assert late > 0.10
    assert price(by_rule, options=SLOW_ONLY) == price(desk(curve=True, same_day=True, cost=1.4 + 300 * (late - 0.10) / 90), options=SLOW_ONLY)
    cheap = desk(curve=True, same_day=True, cost=1.05, rule_cost=-300)  # a negative price stands in for a safe order here
    assert price(cheap, options=SLOW_ONLY) == price(desk(curve=True, same_day=True, cost=1.0), options=SLOW_ONLY)


def test_drivers_with_a_home_where_the_car_is_going_get_offers_at_the_posting_and_the_next_ones_when_those_end():
    d = desk(fee=1.0, fee_cap=1.2, home_offers=2, home_fee=0.9, home_rounds=2)
    assert d.wake_at() == policy.NEVER
    posted(d, 2000)  # the car goes to Helsinki, where 8 drivers live; one lives in Tampere
    d.read_results([d.outbox[-1]], [{"ok": True, "id": "G1"}])
    d.outbox = []
    d.look()
    assert d.outbox == [{"type": "offer", "gigId": "G1", "driverId": driver, "feeCents": 8100} for driver in ("d0", "d1")]
    assert d.wake_at() == 510  # the offers last 10 minutes
    d.look()
    assert len(d.outbox) == 2  # they are still open
    d.now = 510
    d.handle({"kind": "gig_viewed", "gigId": "G1", "driverId": "d7", "at": 505})
    d.look()
    assert [a["driverId"] for a in d.outbox[2:]] == ["d7", "d2"]  # a driver who used the app today comes first
    d.now = 520
    d.look()
    assert len(d.outbox) == 4 and d.wake_at() == policy.NEVER  # two rounds, no more
    d.handle({"kind": "gig_booked", "gigId": "G1", "driverId": "d7", "at": 520})
    d.handle({"kind": "gig_dropped", "gigId": "G1", "driverId": "d7", "at": 530})
    d.now = 530
    d.look()
    assert [a["driverId"] for a in d.outbox[4:]] == ["d3", "d4"]  # open again after a drop; never the driver who dropped it
    plain = desk(fee=1.0, fee_cap=1.2)
    posted(plain, 2000)
    plain.read_results([plain.outbox[-1]], [{"ok": True, "id": "G1"}])
    plain.outbox = []
    plain.look()
    assert plain.outbox == [] and plain.wake_at() == policy.NEVER  # off at its default


def test_the_friday_model_raises_the_chance_of_an_order_that_must_be_collected_on_a_friday_soon():
    friday = 4 * 1440
    more = {"arrivedAt": friday + 500, "respondBy": friday + 515, "options": (("same_day", friday + 1200),)}
    q = request(**more)  # 9.4 hours to find a driver, and the last pickup minute is on Friday
    known = slow.known(q, q["options"][0], 100, 120, 760)
    assert slow.chance(known, slow.MODELS["friday"]) > 1.15 * slow.chance(known)
    monday = request(options=(("same_day", 1200),))
    known = slow.known(monday, monday["options"][0], 100, 120, 760)
    assert abs(slow.chance(known, slow.MODELS["friday"]) - slow.chance(known)) < 0.01
    assert desk(slow_model="friday").slow(q, q["options"]) > desk().slow(q, q["options"])
