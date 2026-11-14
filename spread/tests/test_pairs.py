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
    assert d.world.sent == [] and "R1" in d.held and d.unbooked() == 0  # waits for a return, and counts as no backlog
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
    assert len(posts) == 1 and not d.held
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
    assert not d.held and [len(a["stops"]) for a in d.world.sent if a["type"] == "post"] == [2]


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
    assert not d.held and len([a for a in d.world.sent if a["type"] == "post"]) == 2
