"""Tests of the parts that every comparison rests on: the seed lists, the policy's declines and the ledger's sums."""
from __future__ import annotations

import collections
import inspect

import pytest

from spreadlab import catalogue, ledger, play, policy, report

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
