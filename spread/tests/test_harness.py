"""Tests of the parts that every comparison rests on: the seed lists, the policy's declines and the ledger's sums."""
from __future__ import annotations

import collections
import gzip
import inspect
import math
import shutil

import pytest

from spreadlab import archive, catalogue, curve, ledger, play, policy, report

MAP = {
    "places": [
        {"id": "helsinki", "name": "Helsinki", "lat": 60.17, "lon": 24.94},
        {"id": "vantaa", "name": "Vantaa", "lat": 60.29, "lon": 25.04},   # 15 km from Helsinki
        {"id": "tampere", "name": "Tampere", "lat": 61.50, "lon": 23.76},  # 160 km from Helsinki
    ],
    "roads": [{"from": a, "to": b, "km": 100.0, "minutes": 120} for a in ("helsinki", "vantaa", "tampere") for b in ("helsinki", "vantaa", "tampere")],
}
ROSTER = [{"id": f"d{i}", "homePlaceId": "helsinki"} for i in range(8)] + [{"id": "t1", "homePlaceId": "tampere"}]


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

    d.handle({"kind": "gig_booked", "gigId": "G1"})  # a booked car does not count
    d.quote(request("R4"))
    assert (d.unbooked(), d.decisions["R4"]["declined"]) == (1, None)
    d.handle({"kind": "gig_dropped", "gigId": "G1"})  # a dropped car counts again
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
    d.handle({"kind": "gig_booked", "gigId": "G3"})  # a driver holds it
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
    d.handle({"kind": "gig_booked", "gigId": "G1"})
    d.quote(request("R3"))
    assert d.decisions["R3"] == {"declined": None, "prices": {"next_day": 15000}, "onTime": 0.97}
    # The same order under a line of 85% is not behind: the line itself is allowed.
    calm = desk(min_on_time=0.85, when_behind={"quote_share": 0})
    won(calm, "R1")
    calm.quote(request("R2"))
    assert calm.decisions["R2"]["declined"] is None


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
    assert d.decisions["R0"]["seen"] == {"trust": 0, "unbooked": 0, "answers": [0, 0]}
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


def test_shift_of_the_curve_is_found_from_answers_and_stays_near_zero_with_few():
    random = __import__("random").Random(1)
    quotes = [(2.0 - curve.SLOPE * math.log(random.uniform(1.1, 2.0))) for _ in range(4000)]
    answers = [(z, random.random() < curve.chance(2.0, math.exp((2.0 - z) / curve.SLOPE), 0.2)) for z in quotes]  # dealers accept 20% more
    assert curve.shift(answers, sd=1.0) == pytest.approx(0.2, abs=0.02)
    assert 0 < curve.shift(answers[:5], sd=0.05) < curve.shift(answers[:5], sd=1.0)


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
