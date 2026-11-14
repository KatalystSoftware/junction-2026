"""The ranking runner (scratch/ranking.py) plays a variant with the desk its practice weeks were played with."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from spreadlab import play
from spreadlab.variants import VARIANTS

MAP = {
    "places": [{"id": "helsinki", "lat": 60.17, "lon": 24.94}, {"id": "tampere", "lat": 61.50, "lon": 23.76}],
    "roads": [{"from": a, "to": b, "km": 100.0, "minutes": 25 if a == b else 120} for a in ("helsinki", "tampere") for b in ("helsinki", "tampere")],
}
ROSTER = [{"id": f"d{i}", "homePlaceId": "helsinki", "rating": 4.9, "licence": "manual", "completedGigs": 60} for i in range(8)]
WEEK = 7 * 1440


@pytest.fixture(scope="module")
def ranking():
    spec = importlib.util.spec_from_file_location("ranking", Path(__file__).parents[1] / "scratch" / "ranking.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EndedWorld:
    """A week that is over at its first minute: the runner builds its desk, plays no step and saves the run."""
    id = "W1"

    def snapshot(self):
        return {"now": WEEK, "startsAt": WEEK, "endsAt": WEEK, "events": [], "gigs": []}

    def roster(self):
        return ROSTER

    def score(self):
        return {"marginCents": 0, "wonOrders": 0, "onTimeShare": 1.0, "undeliveredShare": 0.0, "ranked": True}


# What each kind of variant is played with, by the parameter that asks for it. Written out here, not read from play.py.
DESKS = [
    ({}, "Policy"),
    ({"pair_hold": 4}, "PairPolicy"),
    ({"late_wide": True}, "WidePolicy"),
    ({"pair_hold": 4, "late_wide": True}, "WidePairPolicy"),
    ({"risk_fees": True}, "RiskFeePolicy"),
    ({"dealer_sd": 0.1}, "DealerPolicy"),
    ({"note_actions": True}, "ActionDesk"),
    ({"exposure": True}, "ExposurePolicy"),
]


@pytest.mark.parametrize("params, desk", DESKS)
def test_a_variant_s_parameters_name_its_desk(params, desk):
    assert play.policy_class(params).__name__ == desk


def first_variant(**wanted) -> str:
    """The first variant in variants.py whose parameters ask for exactly these of the desk-choosing ones."""
    keys = ("pair_hold", "late_wide", "risk_fees", "dealer_sd", "exposure")
    return next(name for name, p in VARIANTS.items()
                if "note_actions" not in p and all(bool(p.get(key)) == bool(wanted.get(key)) for key in keys))


@pytest.mark.parametrize("wanted, desk", [
    ({}, "Policy"),
    ({"pair_hold": True}, "PairPolicy"),
    ({"pair_hold": True, "late_wide": True}, "WidePairPolicy"),
])
def test_a_ranking_run_plays_the_desk_of_the_variant_s_practice_weeks(ranking, monkeypatch, tmp_path, wanted, desk):
    monkeypatch.setattr(ranking, "world_map", lambda client: MAP)
    variant = first_variant(**wanted)
    summary = ranking.play(None, EndedWorld(), variant, 8, tmp_path / "L8-run-1.json.gz", {"run": 1})
    # The plain policy refuses a pair variant's parameters or, worse, plays them as if they were not there.
    assert summary["desk"] == desk
    assert (tmp_path / "L8-run-1.score.json").exists()
