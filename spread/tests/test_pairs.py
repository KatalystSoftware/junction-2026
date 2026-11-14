"""Out-and-back pairs (pairs.py): a held car, the return's quote, one gig for both cars, and two gigs again."""
from __future__ import annotations

import pytest

from spreadlab import pairs

MAP = {
    "places": [{"id": "helsinki", "lat": 60.17, "lon": 24.94}, {"id": "tampere", "lat": 61.50, "lon": 23.76}],
    "roads": [{"from": a, "to": b, "km": 100.0, "minutes": 25 if a == b else 120} for a in ("helsinki", "tampere") for b in ("helsinki", "tampere")],
}
ROSTER = [{"id": f"d{i}", "homePlaceId": "helsinki", "rating": 4.9, "licence": "manual", "completedGigs": 60} for i in range(8)]
MON_9 = 9 * 60  # Monday 09:00


class World:
    def __init__(self):
        self.sent, self.n = [], 0

    def act(self, actions):
        self.sent += actions
        out = []
        for action in actions:
            self.n += 1
            out.append({"ok": True, "id": f"G{self.n}"} if action["type"] == "post" else {"ok": True})
        return out


def request(id_, frm, to, at, deadline=2 * 1440 + 18 * 60, fee=10000):
    site = lambda place: {"placeId": place, "privateAddress": False, "window": {"from": at, "to": deadline}, "hours": None}  # noqa: E731
    leg = {"car": {"premium": False, "electric": False, "chargePercent": None}, "pickup": site(frm), "delivery": site(to)}
    return {"id": id_, "dealerId": "D01", "batchId": None, "arrivedAt": at, "respondBy": at + 15, "legs": [leg],
            "options": [{"kind": "next_day", "deadline": deadline, "listPriceCents": 15000}], "referenceFeeCents": fee, "note": None}


def order(req):
    return {"id": req["id"], "legs": req["legs"], "deliveredAt": [None], "deadline": req["options"][0]["deadline"],
            "option": "next_day", "lastPickupAt": req["options"][0]["deadline"] - 120}


def desk(monkeypatch, **params):
    monkeypatch.setattr(pairs, "RETURNS", {"helsinki>tampere": 20, "tampere>helsinki": 20})
    d = pairs.PairPolicy(World(), 8, MON_9, {"quote_share": 1, "curve": True, "cost": 1.2, "fee": 1.0, "fee_cap": 1.2, "pair_hold": 4, **params}, ROSTER, MAP)
    d.world = World()
    return d


def win(d, req, at):
    d.now = at
    d.quote(req)
    d.outbox = []
    d.handle({"kind": "order_won", "at": at, "order": order(req)})
    d.send()


def test_a_held_car_and_its_return_go_as_one_gig_at_the_pair_fee(monkeypatch):
    d = desk(monkeypatch, pair_fee=0.7, pair_cost=0.75)
    win(d, request("R1", "helsinki", "tampere", MON_9), MON_9 + 15)
    assert d.world.sent == [] and "R1" in d.pair_wait and d.unbooked() == 0  # waits for a return, and counts as no backlog
    # The return is quoted at the pair's cost: lower than the same request with no held car to go back with.
    back = request("R2", "tampere", "helsinki", MON_9 + 60)
    d.now = MON_9 + 60
    d.quote(back)
    alone = desk(monkeypatch, pair_fee=0.7, pair_cost=0.75)
    alone.now = MON_9 + 60
    alone.quote(back)
    assert d.decisions["R2"]["pair"] == "R1"
    assert d.decisions["R2"]["prices"]["next_day"] < alone.decisions["R2"]["prices"]["next_day"]
    d.outbox = []
    d.handle({"kind": "order_won", "at": MON_9 + 75, "order": order(back)})
    d.send()
    posts = [a for a in d.world.sent if a["type"] == "post"]
    assert len(posts) == 1 and not d.pair_wait
    stops = posts[0]["stops"]
    assert [(s["orderId"], s["kind"]) for s in stops] in (
        [("R1", "pickup"), ("R1", "delivery"), ("R2", "pickup"), ("R2", "delivery")],
        [("R2", "pickup"), ("R2", "delivery"), ("R1", "pickup"), ("R1", "delivery")])
    assert posts[0]["schedule"][0]["feeCents"] == 14000  # 0.7 x the two typical fees of 10000
    assert posts[0]["schedule"][-1]["feeCents"] == 20000  # rising to 1.0 x
    assert d.gigs_of("R1") == d.gigs_of("R2") == ["G1"]


def test_a_held_car_without_a_return_goes_alone_when_its_hold_ends(monkeypatch):
    d = desk(monkeypatch)
    win(d, request("R1", "helsinki", "tampere", MON_9), MON_9 + 15)
    assert d.wake_at() == MON_9 + 15 + 4 * 60
    d.now = MON_9 + 15 + 4 * 60
    d.look()
    d.send()
    assert not d.pair_wait and [len(a["stops"]) for a in d.world.sent if a["type"] == "post"] == [2]


@pytest.mark.parametrize("event", ["deadline_close", "gig_expired"])
def test_an_open_pair_gig_goes_again_as_two_gigs(monkeypatch, event):
    d = desk(monkeypatch)
    win(d, request("R1", "helsinki", "tampere", MON_9), MON_9 + 15)
    win(d, request("R2", "tampere", "helsinki", MON_9 + 60), MON_9 + 75)
    d.world.sent = []
    d.handle({"kind": event, "at": MON_9 + 90, "orderId": "R1", "gigId": "G1"})
    d.send()
    kinds = [a["type"] for a in d.world.sent]
    assert kinds.count("post") == 2 and kinds.count("withdraw") == (event == "deadline_close")
    assert {len(a["stops"]) for a in d.world.sent if a["type"] == "post"} == {2}
    assert d.gigs_of("R1") != d.gigs_of("R2") and not d.pair_gigs


def test_a_car_with_too_little_time_or_no_return_traffic_is_posted_at_once(monkeypatch):
    d = desk(monkeypatch)
    win(d, request("R1", "helsinki", "tampere", MON_9, deadline=MON_9 + 10 * 60), MON_9 + 15)  # under 16 hours to its last pickup
    win(d, request("R2", "helsinki", "helsinki", MON_9), MON_9 + 15)  # a lane without return traffic
    assert not d.pair_wait and len([a for a in d.world.sent if a["type"] == "post"]) == 2


class Refusing(World):
    """Refuses withdrawals: a driver booked the gig as the desk withdrew it."""

    def act(self, actions):
        return [{"ok": False, "reason": "Gig is not open"} if a["type"] == "withdraw" else r for a, r in zip(actions, super().act(actions))]


@pytest.mark.parametrize("world", [World, Refusing])
def test_a_return_pairs_with_a_car_whose_own_gig_is_still_open_only_once_that_gig_is_withdrawn(monkeypatch, world):
    d = desk(monkeypatch, pair_open=True, pair_slack=100)  # no car is held: R1 goes alone at once
    d.world = world()
    win(d, request("R1", "helsinki", "tampere", MON_9), MON_9 + 15)
    assert d.gigs_of("R1") == ["G1"] and not d.pair_wait
    win(d, request("R2", "tampere", "helsinki", MON_9 + 60), MON_9 + 75)
    sent = [(a["type"], a.get("gigId"), len(a.get("stops", []))) for a in d.world.sent]
    if world is World:
        assert sent == [("post", None, 2), ("withdraw", "G1", 0), ("post", None, 4)]
        assert d.gigs_of("R1") == d.gigs_of("R2") == ["G3"] and "G3" in d.pair_gigs
    else:  # the car stays on the gig a driver now holds, and the return goes alone
        assert sent == [("post", None, 2), ("withdraw", "G1", 0), ("post", None, 2)]
        assert d.gigs_of("R1") == ["G1"] and d.gigs_of("R2") == ["G3"] and not d.pair_gigs


def test_a_held_car_goes_onward_with_a_car_collected_where_it_is_delivered_at_the_onward_fee(monkeypatch):
    three = {"places": MAP["places"] + [{"id": "pori", "lat": 61.48, "lon": 21.80}],
             "roads": [{"from": a, "to": b, "km": 100.0, "minutes": 25 if a == b else 120} for a in ("helsinki", "tampere", "pori") for b in ("helsinki", "tampere", "pori")]}
    monkeypatch.setattr(pairs, "RETURNS", {"helsinki>tampere": 20})
    found = {}
    for onward in (0, 0.8):
        d = pairs.PairPolicy(World(), 8, MON_9, {"quote_share": 1, "curve": True, "cost": 1.2, "fee": 1.0, "fee_cap": 1.2, "pair_hold": 4,
                                                 "pair_onward": onward}, ROSTER, three)
        win(d, request("R1", "helsinki", "tampere", MON_9), MON_9 + 15)
        win(d, request("R2", "tampere", "pori", MON_9 + 60), MON_9 + 75)  # collected where R1 is delivered, going elsewhere
        found[onward] = [a for a in d.world.sent if a["type"] == "post"]
    assert found[0] == [] or all(len(a["stops"]) == 2 for a in found[0])  # without onward pairs R2 goes alone, R1 stays held
    (pair,) = found[0.8]
    assert [(s["orderId"], s["kind"]) for s in pair["stops"]] == [("R1", "pickup"), ("R1", "delivery"), ("R2", "pickup"), ("R2", "delivery")]
    assert pair["schedule"][0]["feeCents"] == 16000  # 0.8 x the two typical fees of 10000


def test_with_pair_late_an_onward_car_leaves_the_held_car_for_its_return_and_pairs_with_it_only_at_the_release(monkeypatch):
    three = {"places": MAP["places"] + [{"id": "pori", "lat": 61.48, "lon": 21.80}],
             "roads": [{"from": a, "to": b, "km": 100.0, "minutes": 25 if a == b else 120} for a in ("helsinki", "tampere", "pori") for b in ("helsinki", "tampere", "pori")]}
    monkeypatch.setattr(pairs, "RETURNS", {"helsinki>tampere": 20, "tampere>helsinki": 20})
    params = {"quote_share": 1, "curve": True, "cost": 1.2, "fee": 1.0, "fee_cap": 1.2, "pair_hold": 4, "pair_fee": 0.6, "pair_onward": 0.8, "pair_late": True}
    # The onward car comes first and goes alone; the return that comes later takes the held car at the pair fee.
    d = pairs.PairPolicy(World(), 8, MON_9, params, ROSTER, three)
    win(d, request("R1", "helsinki", "tampere", MON_9), MON_9 + 15)
    win(d, request("R2", "tampere", "pori", MON_9 + 60), MON_9 + 75)
    assert "R1" in d.pair_wait and [len(a["stops"]) for a in d.world.sent if a["type"] == "post"] == [2]
    win(d, request("R3", "tampere", "helsinki", MON_9 + 90), MON_9 + 105)
    pair = [a for a in d.world.sent if a["type"] == "post"][-1]
    assert {s["orderId"] for s in pair["stops"]} == {"R1", "R3"} and pair["schedule"][0]["feeCents"] == 12000  # 0.6 x 20000
    # With no return, the held car takes the onward car's open gig at its release, at the onward fee.
    d = pairs.PairPolicy(World(), 8, MON_9, params, ROSTER, three)
    win(d, request("R1", "helsinki", "tampere", MON_9), MON_9 + 15)
    win(d, request("R2", "tampere", "pori", MON_9 + 60), MON_9 + 75)
    d.now = MON_9 + 15 + 4 * 60
    d.look()
    d.send()
    sent = [(a["type"], a.get("gigId"), len(a.get("stops", []))) for a in d.world.sent]
    assert sent == [("post", None, 2), ("withdraw", "G1", 0), ("post", None, 4)] and not d.pair_wait
    assert d.gigs_of("R1") == d.gigs_of("R2") == ["G3"] and d.world.sent[-1]["schedule"][0]["feeCents"] == 16000


def test_with_pair_late_two_held_cars_released_together_go_once_as_one_onward_gig(monkeypatch):
    three = {"places": MAP["places"] + [{"id": "pori", "lat": 61.48, "lon": 21.80}],
             "roads": [{"from": a, "to": b, "km": 100.0, "minutes": 25 if a == b else 120} for a in ("helsinki", "tampere", "pori") for b in ("helsinki", "tampere", "pori")]}
    monkeypatch.setattr(pairs, "RETURNS", {"helsinki>tampere": 20, "tampere>pori": 20})
    d = pairs.PairPolicy(World(), 8, MON_9, {"quote_share": 1, "curve": True, "cost": 1.2, "fee": 1.0, "fee_cap": 1.2, "pair_hold": 4,
                                             "pair_onward": 0.8, "pair_late": True}, ROSTER, three)
    win(d, request("R1", "helsinki", "tampere", MON_9), MON_9 + 15)
    win(d, request("R2", "tampere", "pori", MON_9), MON_9 + 15)
    assert set(d.pair_wait) == {"R1", "R2"} and d.world.sent == []
    d.now = MON_9 + 15 + 4 * 60
    d.look()
    d.send()
    (post,) = d.world.sent
    assert [(s["orderId"], s["kind"]) for s in post["stops"]] == [("R1", "pickup"), ("R1", "delivery"), ("R2", "pickup"), ("R2", "delivery")]
    assert not d.pair_wait


def test_an_onward_request_is_quoted_at_the_onward_cost_and_once_won_waits_for_the_held_cars_release(monkeypatch):
    three = {"places": MAP["places"] + [{"id": "pori", "lat": 61.48, "lon": 21.80}],
             "roads": [{"from": a, "to": b, "km": 100.0, "minutes": 25 if a == b else 120} for a in ("helsinki", "tampere", "pori") for b in ("helsinki", "tampere", "pori")]}
    monkeypatch.setattr(pairs, "RETURNS", {"helsinki>tampere": 20})
    params = {"quote_share": 1, "curve": True, "cost": 1.2, "fee": 1.0, "fee_cap": 1.2, "pair_hold": 4, "pair_onward": 0.8, "pair_late": True}
    prices = {}
    for cost in (0, 0.9):
        d = pairs.PairPolicy(World(), 8, MON_9, {**params, "pair_onward_cost": cost}, ROSTER, three)
        win(d, request("R1", "helsinki", "tampere", MON_9), MON_9 + 15)
        win(d, request("R2", "tampere", "pori", MON_9 + 60), MON_9 + 75)  # collected where R1 is delivered, going elsewhere
        prices[cost] = d.decisions["R2"]["prices"]["next_day"]
        if cost:
            assert d.decisions["R2"]["onward"] == "R1" and set(d.pair_wait) == {"R1", "R2"} and d.world.sent == []
            d.now = MON_9 + 15 + 4 * 60
            d.look()
            d.send()
            (post,) = d.world.sent  # one gig for both, at the onward fee, and no withdrawal
            assert {s["orderId"] for s in post["stops"]} == {"R1", "R2"} and post["schedule"][0]["feeCents"] == 16000
            assert not d.pair_wait
        else:
            assert "onward" not in d.decisions["R2"] and "R2" not in d.pair_wait
    assert prices[0.9] < prices[0]
