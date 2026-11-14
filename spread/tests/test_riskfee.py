"""Tests of the driver fees by each car's risk of ending late (riskfee.py)."""
from __future__ import annotations

from spreadlab import policy, riskfee

from test_harness import MAP, request

DAY = 1440
# A full driver list in Helsinki: a pickup in Vantaa has 800 drivers notified, one in Tampere none.
ROSTER = [{"id": f"d{i}", "homePlaceId": "helsinki", "rating": 4.9, "licence": "manual", "completedGigs": 60} for i in range(800)]
FEES = {"quote_share": 1, "fee": 1.0, "fee_cap": 1.2, "slow_model": "friday"}


def posted(d: policy.Policy, last_pickup: int, id_: str = "R1", pickup: str = "vantaa", premium: bool = False) -> list[tuple[int, int]]:
    """The fees of the gig that the desk posts at minute 500 for a won one-car order, as (minute, cents)."""
    req = request(id_, pickup=pickup)
    req["legs"] = [{**req["legs"][0], "car": {"premium": premium, "electric": False, "chargePercent": None}}]
    d.quote(req)
    d.win({"id": id_, "legs": req["legs"], "deliveredAt": [None], "deadline": last_pickup + 120, "option": "next_day", "lastPickupAt": last_pickup})
    return [(step["at"], step["feeCents"]) for step in d.outbox[-1]["schedule"]]


def desk(**params) -> riskfee.RiskFeePolicy:
    return riskfee.RiskFeePolicy(None, 8, 500, {**FEES, **params}, ROSTER, MAP)


def test_without_risk_fees_the_fees_are_the_policys():
    plain = policy.Policy(None, 8, 500, FEES, ROSTER, MAP)
    assert posted(desk(), DAY + 14 * 60) == posted(plain, DAY + 14 * 60) == [(500, 9000), (560, 9900), (620, 10800)]


def test_a_safe_car_opens_lower_and_holds_its_fee_until_the_hours_left_put_it_at_risk():
    # 30 hours left, 800 drivers notified: slow.py puts it at 1.0% late now, 1.5% with under 24 hours left, 2.2% with under
    # 12, 3.4% with under 8 and 5.7% with under 6. At 4% the gig rises from 6 hours before the last pickup, a tenth an hour.
    last = DAY + 14 * 60
    assert posted(desk(risk_fees=True), last) == [(500, 8100), (last - 299, 9000), (last - 239, 9900), (last - 179, 10800)]
    assert posted(desk(risk_fees=True, risk_raise_late=0.02), last) == [(500, 8100), (last - 659, 9000), (last - 599, 9900), (last - 539, 10800)]
    assert posted(desk(risk_fees=True, risk_raise_late=0.06), last) == [(500, 8100)]  # never at risk: the deadline warning and the offers take over
    # Under 16 hours left it opens at the policy's fee
    assert posted(desk(risk_fees=True), 500 + 15 * 60)[0] == (500, 9000)


def test_a_risky_car_gets_the_policys_fees_from_the_posting():
    # A premium car with no driver notified of its pickup: 9.3% late with 30 hours left
    last = DAY + 14 * 60
    plain = policy.Policy(None, 8, 500, FEES, ROSTER, MAP)
    assert posted(desk(risk_fees=True), last, pickup="tampere", premium=True) == posted(plain, last, pickup="tampere", premium=True)


def test_the_waiting_cars_can_count_only_those_due_within_hours():
    every, due = desk(risk_fees=True), desk(risk_fees=True, risk_queue_hours=24)
    for d in (every, due):
        for n, last in enumerate((600, 900, 5000, 6000)):  # two cars to collect within 24 hours of minute 500, two later
            posted(d, last, f"T{n}")
    assert every.unbooked() == 4 and due.unbooked() == 2 and due.unbooked(100) == 4
