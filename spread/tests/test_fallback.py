"""Tests of the note fallback (fallback.py): only cited actions that make the post stricter act, they never loosen the
rules' reading, quotes never see them, and a late or failed answer leaves the rules' post."""
from __future__ import annotations

import copy
import json

from spreadlab import fallback, notes, policy
from test_harness import MAP, ROSTER, request

DAY, HOUR = 1440, 60
HOURS = {"opens": 8 * HOUR, "closes": 18 * HOUR, "weekdays": [0, 1, 2, 3, 4], "saturday": None}
PARAMS = {"quote_share": 1, "read_notes": True, "note_limits": True, "fee": 1.0}


def asked(text: str) -> dict:
    """A request on Monday 10:00 with stated hours 8-18 at both sites, collectable until Wednesday 17:00."""
    r = copy.deepcopy(request("R1", arrivedAt=600, note={"text": text}))
    leg = copy.deepcopy(r["legs"][0])
    for end in ("pickup", "delivery"):
        leg[end] = {**leg[end], "hours": HOURS, "window": {"from": 600, "to": 2 * DAY + 17 * HOUR}}
    return {**r, "legs": [leg], "respondBy": 615, "options": [{"kind": "next_day", "deadline": 2 * DAY + 17 * HOUR, "listPriceCents": 10000}]}


def vet(text: str, actions: list[dict], deadline: int = 2 * DAY + 17 * HOUR):
    r = asked(text)
    kept, dropped = fallback.vet(actions, text, r, deadline, notes.read(r["note"], 600), notes.limits(r["note"], 600))
    return [a["action"] for a in kept], {a["action"]: a["why"] for a in dropped}


def test_an_action_acts_only_with_the_notes_own_words_for_it_and_only_when_it_makes_the_post_stricter():
    text = "Drop-off point stops taking vehicles at 15 on weekdays. Kesäkiekot alla vielä. Customer waits, there by Tuesday 12."
    kept, dropped = vet(text, [{"action": "delivery_hours", "closes": "15:00", "cite": "stops taking vehicles at 15"},
                               {"action": "summer_tyres", "cite": "kesäkiekot alla vielä"},  # wording that notes.summer_tyres does not read
                               {"action": "plates", "cite": "Kesäkiekot alla"},  # cited, but no word about plates
                               {"action": "manual", "cite": "it is a stick shift"},  # not in the note
                               {"action": "urgent", "cite": "Customer waits"}])  # no word for haste
    assert kept == ["delivery_hours", "summer_tyres"]
    assert dropped == {"plates": "cite lacks the word", "manual": "uncited", "urgent": "cite lacks the word"}
    # Tyres that travel in the car are not tyres on it, and summer tyres that the rules read need no action.
    assert vet("Kesäkiekot tavaratilassa, kulkee mukana.", [{"action": "summer_tyres", "cite": "Kesäkiekot tavaratilassa"}])[1] == \
        {"summer_tyres": "tyres carried, not on the car"}
    assert vet("Lisäksi 4 kesäkiekkoa tavratilassa.", [{"action": "summer_tyres", "cite": "4 kesäkiekkoa"}])[1] == \
        {"summer_tyres": "tyres carried, not on the car"}, "the boot is read in the cite's clause, with a typo"
    assert vet("Still on summer tyres.", [{"action": "summer_tyres", "cite": "summer tyres"}])[1] == {"summer_tyres": "the rules have it"}
    # Hours in a clause that names the other site are that site's.
    assert vet("Nouto arkisin klo 15 asti.", [{"action": "delivery_hours", "closes": "15:00", "cite": "Nouto arkisin klo 15 asti"}])[1] == \
        {"delivery_hours": "hours of the other site"}
    # A time that the cited words do not carry, or that opens the site later than it closes, or a deadline after the order's.
    _, dropped = vet(text, [{"action": "delivery_hours", "closes": "13:00", "cite": "stops taking vehicles at 15"},
                            {"action": "pickup_hours", "opens": "19:00", "cite": "stops taking vehicles at 15"}])
    assert set(dropped) == {"delivery_hours", "pickup_hours"}
    _, dropped = vet(text, [{"action": "deadline", "day": "tue", "time": "12:00", "cite": "there by Tuesday 12"}], deadline=7 * DAY + 10 * HOUR)
    assert dropped == {"deadline": "not earlier than the deadline"}  # "tue" on a Monday is the Tuesday after next: 8 days on
    kept, _ = vet(text, [{"action": "keep"}, {"action": "summer_tyres", "cite": "Kesäkiekot alla"}])
    assert kept == ["summer_tyres"], "keep is dropped beside another action"
    assert fallback.parse('Sure: {"actions": [{"action": "summer_tyres", "cite": "x"}, {"action": "cancel_order"}]}') == [{"action": "summer_tyres", "cite": "x"}]
    assert fallback.parse("I would keep it as it is.") is None


def test_a_fix_never_loosens_what_the_rules_read():
    rules = notes.Limits(2000, (0, 15 * HOUR), (0, 0))
    fix = {"limits": {"deadline": 2100, "pickupHours": (9 * HOUR, 16 * HOUR), "deliveryHours": (0, 14 * HOUR)}}
    assert fallback.merge(rules, fix) == notes.Limits(2000, (9 * HOUR, 15 * HOUR), (0, 14 * HOUR))
    assert fallback.merge(rules, {"plates": True}) == rules
    # The deadline and haste cost margin when wrong: they act only when the desk names them.
    kept = [{"action": "deadline", "at": 1900}, {"action": "urgent"}, {"action": "plates"}]
    assert fallback.fix_of(kept) == {"plates": True}
    assert fallback.fix_of(kept, fallback.RISKY) == {"plates": True, "limits": {"deadline": 1900}, "fee": fallback.FEE_STEP}


def answering(content: str, seconds: float = 0.4, error: str = None):
    calls = []

    def ask(msgs):
        calls.append(msgs)
        return {"content": content, "seconds": seconds, **({"error": error} if error else {})}
    return ask, calls


def played(desk, text: str):
    r = asked(text)
    desk.quote(r)
    quote = desk.outbox[-1]
    desk.win({"id": "R1", "legs": r["legs"], "deliveredAt": [None], "deadline": 2 * DAY + 17 * HOUR, "option": "next_day", "lastPickupAt": 2 * DAY + 15 * HOUR})
    return quote, desk.outbox[-1]


def test_the_desk_posts_with_the_fix_and_quotes_and_posts_as_the_rules_when_the_answer_is_late_or_fails():
    text = "Drop-off point stops taking vehicles at 15 on weekdays. Kesäkiekot alla vielä."
    answer = json.dumps({"actions": [{"action": "delivery_hours", "closes": "15:00", "cite": "stops taking vehicles at 15"}]})
    plain_quote, plain_post = played(policy.Policy(None, 8, 500, PARAMS, ROSTER, MAP), text)
    ask, calls = answering(answer)
    quote, post = played(fallback.ActionDesk(None, 8, 500, {**PARAMS, "note_actions": 1}, ROSTER, MAP, ask=ask), text)
    assert quote == plain_quote, "the quote comes before the win and reads the rules alone"
    assert len(calls) == 1
    delivery = next(s for s in post["stops"] if s["kind"] == "delivery")["window"]
    assert delivery["to"] % DAY <= 15 * HOUR < next(s for s in plain_post["stops"] if s["kind"] == "delivery").get("window", {"to": 18 * HOUR})["to"] % DAY
    for ask in (answering(answer, seconds=fallback.HOLD + 0.2)[0], answering("", error="HTTP 503")[0], answering("not json")[0]):
        _, post = played(fallback.ActionDesk(None, 8, 500, {**PARAMS, "note_actions": 1}, ROSTER, MAP, ask=ask), text)
        assert post == plain_post
    # A note that the rules are sure of is never sent.
    ask, calls = answering(answer)
    played(fallback.ActionDesk(None, 8, 500, {**PARAMS, "note_actions": 1}, ROSTER, MAP, ask=ask), "Nycklar i receptionen.")
    assert calls == []


def test_a_car_on_summer_tyres_is_collected_after_the_snow_forecast_at_its_pickup():
    text = "Kesäkiekot alla vielä."
    answer = json.dumps({"actions": [{"action": "summer_tyres", "cite": "Kesäkiekot alla"}]})
    desk = fallback.ActionDesk(None, 8, 500, {**PARAMS, "note_actions": 1}, ROSTER, MAP, ask=answering(answer)[0])
    desk.forecasts.append({"from": 500, "to": DAY + 6 * HOUR, "placeIds": ["vantaa"]})
    _, post = played(desk, text)
    assert next(s for s in post["stops"] if s["kind"] == "pickup")["window"]["from"] >= DAY + 6 * HOUR

