"""Tests of the quote as an optimisation: what the belief over the market level keeps, and what the price follows."""
from __future__ import annotations

from spreadlab import optquote, policy

from test_harness import answer, desk, request

price = lambda d, id_: d.decisions[id_]["prices"]["next_day"]


def test_belief_follows_the_answers_and_keeps_the_worlds_part_for_the_next_morning():
    level = optquote.Level()
    assert -0.05 < level.mean() < 0  # one day in five is the price war, 0.21 under the world's level
    for _ in range(12):
        level.answer(3.0, 0.5, True)  # sales at 1.65 x the list price, where the mean world buys one time in 28
    monday = level.mean()
    level.start(1)
    assert 0.03 < level.mean() < monday  # the world's part stays; the day's part starts again


def test_price_rises_with_the_price_of_a_drivers_time_and_the_backlog_surcharge_counts_as_more_of_it():
    plain, dear, backlog = desk(opt=True), desk(opt=True, opt_mu=0.3), desk(opt=True, backlog_step=0.3)
    backlog.orders["T1"] = {"deliveredAt": [None], "lastPickupAt": 2000, "legs": request()["legs"]}  # one won car without a driver
    for d in (plain, dear, backlog):
        d.quote(request("R1"))
    assert price(plain, "R1") < price(dear, "R1") <= price(backlog, "R1")  # the same 0.3, and the order's own cost rises with the backlog


def test_price_of_the_90_percent_rule_raises_the_risky_order_and_lowers_the_safe_one():
    premium = [{**request()["legs"][0], "car": {"premium": True, "electric": False, "chargePercent": None}}]
    safe = request("S", options=(("next_day", 6000),))  # days to find a driver
    risky = request("K", options=(("next_day", 940),), legs=1, note={"text": "Nouto ennen klo 14", "language": "fi"})  # 5 hours, a note, a premium car
    risky["legs"] = premium
    plain, ruled = desk(opt=True), desk(opt=True, opt_lambda=300)
    for d in (plain, ruled):
        d.quote(safe)
        d.quote(risky)
    assert price(ruled, "S") < price(plain, "S")
    assert price(ruled, "K") > price(plain, "K")


def test_quote_follows_the_weeks_answers_into_the_next_morning_and_the_curve_is_untouched_without_opt():
    plain, refused = desk(opt=True), desk(opt=True)
    for n in range(12):
        answer(refused, f"A{n}", False)
    tuesday = dict(dealerId="D99", arrivedAt=1440 + 500, respondBy=1440 + 515)
    for d in (plain, refused):
        d.quote(request("R1", dealerId="D99"))
        d.quote(request("R2", **tuesday))
    assert price(refused, "R1") < price(plain, "R1")
    assert price(refused, "R2") < price(plain, "R2")  # the curve's shift starts again each morning; the belief keeps the world's level
    assert desk(curve=True).opt is None and policy.fingerprint({"opt": True}) != policy.fingerprint({})


def test_an_answer_to_a_quote_that_the_world_never_took_does_not_move_the_belief():
    plain, missed = desk(opt=True), desk(opt=True)
    for n in range(8):
        missed.quote(request(f"M{n}"))
        missed.asked.pop(f"M{n}")  # as the live desk does for a quote that came late, or for a request that it missed while it was down
        missed.handle({"kind": "order_lost", "requestId": f"M{n}"})
    for d in (plain, missed):
        d.quote(request("R1", dealerId="D99"))
    assert price(missed, "R1") == price(plain, "R1")
