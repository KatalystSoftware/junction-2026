"""The note fallback: when the rules (notes.py) are likely to have read a won note wrong, a model picks the desk's next
step from a fixed set of actions, and each action must quote the note's own words. Off unless the desk runs with
`--note-actions` (live.py) or the variant has "note_actions" (play.py).

    uv run python -m spreadlab.fallback check "Vastaanotto klo 15 asti, kesärenkaat" --arrived 600   # one note: trigger, model, actions

When it asks. Only on a won note whose reading the rules are unsure of (`trigger`): a note with a word or sentence that
the archive has not seen, a note about a field the rules often miss (a deadline, the hours of either site, summer tyres)
whose reading the rules left empty, or a note on which the watcher's yes/no check named such a field.

What the model may do. One JSON object with a list of actions, each from ACTIONS and each with "cite", the words of the
note that state it. An action is kept only when the cited words are in the note, carry the time or the word that the
action needs, and make the post stricter than the rules' (`vet`): a site that opens later or closes earlier, a deadline
earlier than the order's, a later start, plates, a manual licence, summer tyres. "urgent" raises the opening fee by a
fixed step, and only with a word for haste in the cited words. "keep" leaves the rules' reading as it is. Nothing else
is read from the answer.

What the desk does with it. The kept actions merge into the rules' reading, field by field, always the stricter of the
two (`Fixes`). Deadlines and the fee cost margin when wrong, so they act only when named in `risky`; else they are
logged. A call that fails, times out or is refused leaves the rules' post as it is; the quote never waits for it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from . import notes, watch
from .policy import Policy

DAY, HOUR = 24 * 60, 60
VERSION = 1  # raise on each change to the prompt, the checks or the model: a sweep's fingerprint follows "note_actions"
ACTIONS = ("pickup_hours", "delivery_hours", "deadline", "delay", "plates", "manual", "summer_tyres", "urgent", "keep")
RISKY = ("deadline", "urgent")  # cost margin when wrong: they act only when the desk names them
FEE_STEP, FEE_CAP = 0.2, 1.4  # "urgent" adds this to the opening fee, as a multiple of the typical fee, up to the cap: the variant's highest kind fee
FIELDS = {"by", "closing", "hours", "delivery", "summer"}  # watch.topics that the rules read least well (scratch/note-actions)
TIMEOUT = 6.0  # seconds for one call; the post waits live.HOLD_SECONDS at most, and a sweep keeps only answers inside that
HOLD = 1.5

SYSTEM = """A rule-based reader read a note that a Finnish car dealer wrote on a car transport request. Notes are in Finnish, Swedish or English, with abbreviations and typos. The reader is unsure of this note. You decide what the transport desk does before it posts the car to drivers, by picking actions from a fixed list. Answer with one JSON object and nothing else: {"actions": [...]}.

Actions. Each has "cite": the exact words of the note that state it, copied character for character, including the time.
- {"action": "pickup_hours", "opens": "HH:MM" or null, "closes": "HH:MM" or null, "cite": ...}: the pickup site's hours, or a time by which the car must be collected that day.
- {"action": "delivery_hours", "opens": ..., "closes": ..., "cite": ...}: the receiving site's hours.
- {"action": "deadline", "day": ..., "time": ..., "cite": ...}: the car must be at its destination by then.
- {"action": "delay", "day": ..., "time": ..., "cite": ...}: the car cannot be collected before then.
- {"action": "plates", "cite": ...}: the car has no registration plates.
- {"action": "manual", "cite": ...}: the car has a manual gearbox.
- {"action": "summer_tyres", "cite": ...}: the car is on summer tyres.
- {"action": "urgent", "cite": ...}: the dealer says the transport is urgent.
- {"action": "keep"}: the reader's reading holds every operational fact the note states. Use it alone.

Pick an action only for a fact that the note states and that the reader's reading and the request lack. Spare tyres or wheels that travel with the car, keys, parking spots, calls before arrival, reference numbers and greetings are not facts. A note that repeats the request's own hours or deadline states nothing new. When unsure, keep.

Days: "today", "tomorrow", "day_after_tomorrow", "mon", "tue", "wed", "thu", "fri", "sat". A time with no day is "today". Give a weekday as the note names it.
Times: "HH:MM", 24-hour. Digits are the hour on a 24-hour clock unless am or pm follows. An hour written as a word is the working hour with that number, from 9 to 17: "kolmelta", "three" and "tre" are 15:00. "Half three", "puoli kolme" and "halv tre" are 14:30.
When the note corrects itself ("korjaus", "eiku", "ei kun", "sorry", "rättelse"), only the correction counts. A time that the note denies is not a fact."""


def site(opens: str, closes: str) -> dict:
    return {"weekdays": f"{opens}-{closes}", "saturday": "closed"}


SHOTS = [  # made up, as the handbook's examples are; none comes from the archive
    ("Vastaanotto sulkee perjantaisin jo klo 14. Kesärenkaat alla.",
     {"ready": None, "no_plates": False, "manual": False, "deadline": None, "pickup_hours": None, "delivery_hours": None},
     {"pickup_window": {"from": {"day": "today", "time": "12:00"}, "to": {"day": "thu", "time": "18:00"}}, "pickup_hours": site("08:00", "18:00"),
      "delivery_hours": site("08:00", "18:00"), "deadline": {"day": "fri", "time": "18:00"}},
     {"actions": [{"action": "delivery_hours", "opens": None, "closes": "14:00", "cite": "Vastaanotto sulkee perjantaisin jo klo 14"},
                  {"action": "summer_tyres", "cite": "Kesärenkaat alla"}]}),
    ("Customer is waiting, needs the car at the showroom tomorrow before 11. Spare wheels in the trunk.",
     {"ready": None, "no_plates": False, "manual": False, "deadline": None, "pickup_hours": None, "delivery_hours": None},
     {"pickup_window": {"from": {"day": "today", "time": "09:00"}, "to": {"day": "tomorrow", "time": "17:00"}}, "pickup_hours": site("08:00", "17:00"),
      "delivery_hours": site("09:00", "18:00"), "deadline": {"day": "tomorrow", "time": "18:00"}},
     {"actions": [{"action": "deadline", "day": "tomorrow", "time": "11:00", "cite": "tomorrow before 11"}]}),
    ("Hämtning vardagar 10-15, bilen står vid porten. Tack!",
     {"ready": None, "no_plates": False, "manual": False, "deadline": None, "pickup_hours": None, "delivery_hours": None},
     {"pickup_window": {"from": {"day": "today", "time": "13:00"}, "to": {"day": "wed", "time": "17:00"}}, "pickup_hours": site("08:00", "17:00"),
      "delivery_hours": site("08:00", "17:00"), "deadline": {"day": "wed", "time": "17:00"}},
     {"actions": [{"action": "pickup_hours", "opens": "10:00", "closes": "15:00", "cite": "Hämtning vardagar 10-15"}]}),
    ("Kiireellinen! Auto pitää olla perillä viimeistään huomenna klo 12. Avaimet tiskillä.",
     {"ready": None, "no_plates": False, "manual": False, "deadline": {"day": "tomorrow", "time": "12:00"}, "pickup_hours": None, "delivery_hours": None},
     {"pickup_window": {"from": {"day": "today", "time": "10:00"}, "to": {"day": "tomorrow", "time": "16:00"}}, "pickup_hours": site("08:00", "18:00"),
      "delivery_hours": site("08:00", "18:00"), "deadline": {"day": "tomorrow", "time": "18:00"}},
     {"actions": [{"action": "urgent", "cite": "Kiireellinen!"}]}),
    ("Soita 30 min ennen tuloa, talvirenkaat takakontissa. Kiitos",
     {"ready": None, "no_plates": False, "manual": False, "deadline": None, "pickup_hours": None, "delivery_hours": None},
     {"pickup_window": {"from": {"day": "today", "time": "11:00"}, "to": {"day": "tomorrow", "time": "18:00"}}, "pickup_hours": site("08:00", "18:00"),
      "delivery_hours": site("09:00", "17:00"), "deadline": {"day": "tomorrow", "time": "17:00"}},
     {"actions": [{"action": "keep"}]}),
    ("Paperwork clears thursday morning, not before 10. No plates on it, and it's a stick.",
     {"ready": {"day": "thu", "time": "10:00"}, "no_plates": True, "manual": False, "deadline": None, "pickup_hours": None, "delivery_hours": None},
     {"pickup_window": {"from": {"day": "today", "time": "14:00"}, "to": {"day": "fri", "time": "18:00"}}, "pickup_hours": site("08:00", "18:00"),
      "delivery_hours": site("08:00", "18:00"), "deadline": {"day": "fri", "time": "18:00"}},
     {"actions": [{"action": "manual", "cite": "it's a stick"}]}),
]


def clock(minute: int) -> str:
    return f"{minute // HOUR:02d}:{minute % HOUR:02d}"


def reading(facts: notes.Facts, limits: notes.Limits, arrived_at: int) -> dict:
    """What the rules read, in the prompt's words: the watcher's three facts and notes.limits."""
    hours = lambda h: None if h == (0, 0) else {"opens": clock(h[0]) if h[0] else None, "closes": clock(h[1]) if h[1] else None}
    return {**watch.reading(facts, arrived_at), "deadline": watch.day_time(limits.deadline, arrived_at) if limits.deadline else None,
            "pickup_hours": hours(limits.pickup_hours), "delivery_hours": hours(limits.delivery_hours)}


def messages(text: str, read: dict, known: dict) -> list[dict]:
    out = [{"role": "system", "content": SYSTEM}]
    for note, rules, request, answer in SHOTS + [(text, read, known, None)]:
        out.append({"role": "user", "content": f"Note: {note}\nRequest: {json.dumps(request, ensure_ascii=False)}\nReader: {json.dumps(rules, ensure_ascii=False)}"})
        if answer is not None:
            out.append({"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)})
    return out


def parse(content: Optional[str]) -> Optional[list[dict]]:
    """The actions of an answer, or None when it cannot be read. Unknown actions are dropped here."""
    try:
        answer = json.loads(re.search(r"\{.*\}", content or "", re.S)[0])
    except (TypeError, ValueError):
        return None
    if not isinstance(answer, dict) or not isinstance(answer.get("actions"), list):
        return None
    return [a for a in answer["actions"] if isinstance(a, dict) and a.get("action") in ACTIONS]


# The watcher's endpoint and key (NOTE_MODEL_URL, NOTE_MODEL, NOTE_MODEL_KEY); NOTE_ACTIONS_MODEL names another model.
# A Claude model goes to Anthropic's own API, which caches the prompt's fixed part (its OpenAI-style one does not).
def endpoint() -> tuple[str, str, Optional[str]]:
    model = os.environ.get("NOTE_ACTIONS_MODEL") or watch.MODEL
    claude = model.startswith("claude")
    key = os.environ.get(watch.KEY if claude == watch.MODEL.startswith("claude") else "ANTHROPIC_API_KEY" if claude else "")
    return ("https://api.anthropic.com/v1/messages" if model.startswith("claude") else watch.URL), model, key


def call(msgs: list[dict], timeout: float = TIMEOUT) -> dict:
    """One call: {"content", "seconds"}, or {"error", "seconds"}."""
    url, model, key = endpoint()
    if not key:
        return {"error": "no key", "seconds": 0.0}
    if "anthropic" in url:
        # Haiku 5.5 refuses `temperature`, and thinks unless told not to, which takes the whole 1.5 s. The system prompt
        # and the shots are the same on every call: cached, they halve the time to the first token.
        shots = [dict(m) for m in msgs[1:]]
        shots[-2] = {"role": shots[-2]["role"], "content": [{"type": "text", "text": shots[-2]["content"], "cache_control": {"type": "ephemeral"}}]}
        body = {"model": model, "system": msgs[0]["content"], "messages": shots, "max_tokens": 300, "thinking": {"type": "disabled"}}
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    else:
        body = {"model": model, "messages": msgs, "temperature": 0, "max_tokens": 300, "chat_template_kwargs": {"enable_thinking": False}}
        headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    started = time.monotonic()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, json.dumps(body).encode(), headers), timeout=timeout) as response:
            data = json.load(response)
        content = next(c["text"] for c in data["content"] if c["type"] == "text") if "anthropic" in url else data["choices"][0]["message"].get("content")
        return {"content": content, "seconds": round(time.monotonic() - started, 3)}
    except urllib.error.HTTPError as error:
        return {"error": f"HTTP {error.code}", "seconds": round(time.monotonic() - started, 3)}
    except Exception as error:  # a timeout, a lost connection, an answer without content
        return {"error": type(error).__name__, "seconds": round(time.monotonic() - started, 3)}


class Cache:
    """Answers on disk by model and prompt, so a week played again gives the same actions and the same seconds."""

    def __init__(self, path: Optional[Path]):
        self.path, self.lock, self.answers = path, threading.Lock(), {}
        if path is not None and path.exists():
            for line in open(path, encoding="utf-8"):
                entry = json.loads(line)
                self.answers[entry["key"]] = entry

    @staticmethod
    def key(msgs: list[dict]) -> str:
        return hashlib.sha256(json.dumps([endpoint()[1], VERSION, msgs[-1]["content"]], ensure_ascii=False).encode()).hexdigest()[:24]

    def ask(self, msgs: list[dict]) -> dict:
        key = self.key(msgs)
        if key in self.answers:
            return {**self.answers[key], "cached": True}
        answer = call(msgs)
        if answer.get("error") in (None, "unreadable") and self.path is not None:  # a failed call is asked again next time
            with self.lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"key": key, **answer}, ensure_ascii=False) + "\n")
        self.answers[key] = {"key": key, **answer}
        return {"key": key, **answer}


def trigger(text: str, arrived_at: int, facts: notes.Facts, limits: notes.Limits, news: dict, disagree: tuple = ()) -> list[str]:
    """Why the rules' reading of this note is unsure, or [] when it is not: new wording, a field the rules often miss and
    left empty here, or a field that the watcher's check named."""
    why = []
    if news.get("newWords") or news.get("newSentences"):
        why.append("new wording")
    said = watch.topics(text, arrived_at) & FIELDS
    if "summer" in said:
        why.append("summer tyres")
    if said & {"by", "delivery"} and not limits.deadline and limits.delivery_hours == (0, 0):
        why.append("deadline or delivery unread")
    if said & {"closing", "hours"} and limits.pickup_hours == (0, 0) and limits.delivery_hours == (0, 0):
        why.append("hours unread")
    why += [f"watcher: {fact}" for fact in disagree if fact in ("deadline", "pickup_hours", "delivery_hours", "summer_tyres", "other")]
    return why


def minutes_in(cite: str) -> set[int]:
    """The clock minutes that the cited words can mean: digits read with and without pm, hours in words, "half"."""
    text, found = cite.lower(), set()
    for match in re.finditer(r"(?<![\d.:])(\d{1,2})(?:[.:](\d{2}))?(?![\d])", text):
        hour, minute = int(match[1]), int(match[2] or 0)
        if hour <= 24 and minute < 60:
            found |= {hour * HOUR + minute} | ({(hour + 12) * HOUR + minute} if hour < 12 else set())
    tokens = notes.TOKEN.findall(text)
    for i, token in enumerate(tokens):
        hour = notes.hour_in_words(token) or notes.HOUR_CASES.get(token)
        if hour:
            found.add(hour * HOUR)
            if i and notes.tag(tokens[i - 1]) == "half":
                found.add(hour * HOUR - 30)
        if token.isdigit() and i and notes.tag(tokens[i - 1]) == "half":
            found.add(int(token) * HOUR - 30)
        if notes.tag(token) == "noon":
            found.add(12 * HOUR)
    return found


def normal(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip(" .,!")


URGENT = re.compile(r"kiire|urgent|asap|bråttom|brådsk|skyndsam|pikaisesti|pikaisest|hoppu|rush|as soon as|heti|snabbt|quickly|express")
SUMMER = re.compile(r"kesä|summer|sommar")
WORDS = {"plates": watch.ABOUT_PLATES, "manual": watch.ABOUT_GEARS, "summer_tyres": SUMMER, "urgent": URGENT}


def vet(actions: list[dict], text: str, request: dict, deadline: int, facts: notes.Facts, limits: notes.Limits) -> tuple[list[dict], list[dict]]:
    """The actions the desk may take, and those it drops, each with the reason. An action is kept when its cited words
    are in the note and carry what it states, and when it makes the post stricter than the rules' reading."""
    note, arrived, leg = normal(text), request["arrivedAt"], request["legs"][0]
    start = max(facts.pickup_from, min(l["pickup"]["window"]["from"] for l in request["legs"]))
    kept, dropped = [], []
    for action in actions:
        kind, cite = action["action"], normal(str(action.get("cite") or ""))
        why = None
        if kind == "keep":
            why = None
        elif len(cite) < 3 or cite not in note:
            why = "uncited"
        elif kind in WORDS and not WORDS[kind].search(cite):
            why = "cite lacks the word"
        elif kind in ("deadline", "delay"):
            at = watch.when(action.get("day"), action.get("time"), arrived)
            if at is None or at % DAY not in minutes_in(cite):
                why = "cite lacks the time"
            elif kind == "deadline" and not (request["arrivedAt"] < at < min(deadline, limits.deadline or deadline)):
                why = "not earlier than the deadline"
            elif kind == "delay" and not (start < at < leg["pickup"]["window"]["to"]):
                why = "not later than the rules' start"
            else:
                action = {**action, "at": at}
        elif kind in ("pickup_hours", "delivery_hours"):
            stop = leg["pickup" if kind == "pickup_hours" else "delivery"]
            hours, noted = stop.get("hours"), limits.pickup_hours if kind == "pickup_hours" else limits.delivery_hours
            opens, closes = watch.minute_of(action.get("opens")), watch.minute_of(action.get("closes"))
            stated = (max(hours["opens"], noted[0]), min(hours["closes"], noted[1] or DAY)) if hours else (noted[0], noted[1] or DAY)
            opens = opens if opens is not None and stated[0] < opens < stated[1] and opens in minutes_in(cite) else None
            closes = closes if closes is not None and stated[0] < closes < stated[1] and closes in minutes_in(cite) else None
            if opens is None and closes is None:
                why = "not narrower than the hours known, or not in the cite"
            elif (closes or stated[1]) - (opens or stated[0]) < HOUR:
                why = "leaves under an hour"
            else:
                action = {**action, "range": (opens or 0, closes or 0)}
        elif kind == "plates" and facts.plates or kind == "manual" and facts.manual:
            why = "the rules have it"
        (dropped if why else kept).append({**action, "why": why} if why else action)
    if any(a["action"] != "keep" for a in kept):
        kept = [a for a in kept if a["action"] != "keep"]
    return kept, dropped


def fix_of(kept: list[dict], risky: tuple = ()) -> dict:
    """The kept actions as the desk's fix: the keys of the watcher's fix (pickupFrom, plates, manual) and "limits",
    "summer", "fee". A risky action that the desk does not name stays out of the fix; it is logged."""
    fix: dict = {}
    for a in kept:
        kind = a["action"]
        if kind == "keep" or kind in RISKY and kind not in risky:
            continue
        if kind == "delay":
            fix["pickupFrom"] = max(fix.get("pickupFrom", 0), a["at"])
        elif kind in ("plates", "manual"):
            fix[kind] = True
        elif kind == "summer_tyres":
            fix["summer"] = True
        elif kind == "urgent":
            fix["fee"] = FEE_STEP
        elif kind == "deadline":
            limits = fix.setdefault("limits", {})
            limits["deadline"] = min(limits.get("deadline") or a["at"], a["at"])
        else:
            limits = fix.setdefault("limits", {})
            name = "pickupHours" if kind == "pickup_hours" else "deliveryHours"
            limits[name] = tighter(tuple(limits.get(name, (0, 0))), a["range"])
    return fix


def tighter(a: tuple[int, int], b: tuple[int, int]) -> tuple[int, int]:
    """The narrower of two site hours, where 0 is "as stated"."""
    return (max(a[0], b[0]), min(x for x in (a[1], b[1]) if x) if a[1] or b[1] else 0)


def combine(old: dict, new: dict) -> dict:
    """Two fixes of one order as one, each field the stricter: a later start, plates, a manual licence, summer tyres,
    the higher fee, the earlier deadline and the narrower hours. The watcher's fix keeps its three keys."""
    out = {**old, **{k: v for k, v in new.items() if k not in ("pickupFrom", "plates", "manual", "summer", "fee", "limits")}}
    if "pickupFrom" in old or "pickupFrom" in new:
        out["pickupFrom"] = max(old.get("pickupFrom", 0), new.get("pickupFrom", 0))
    for key in ("plates", "manual", "summer"):
        if key in old or key in new:
            out[key] = old.get(key, False) or new.get(key, False)
    if old.get("fee") or new.get("fee"):
        out["fee"] = max(old.get("fee", 0), new.get("fee", 0))
    a, b = old.get("limits") or {}, new.get("limits") or {}
    if a or b:
        deadlines = [x for x in (a.get("deadline"), b.get("deadline")) if x]
        out["limits"] = {**({"deadline": min(deadlines)} if deadlines else {}),
                         **{k: tighter(tuple(a.get(k, (0, 0))), tuple(b.get(k, (0, 0)))) for k in ("pickupHours", "deliveryHours") if k in a or k in b}}
    return out


def merge(rules: notes.Limits, fix: Optional[dict]) -> notes.Limits:
    """The rules' limits with the fallback's, each field the stricter of the two: never looser than the rules."""
    extra = (fix or {}).get("limits")
    if not extra:
        return rules
    deadline = min(x for x in (rules.deadline, extra.get("deadline", 0)) if x) if rules.deadline or extra.get("deadline") else 0
    return notes.Limits(deadline, tighter(rules.pickup_hours, tuple(extra.get("pickupHours", (0, 0)))),
                        tighter(rules.delivery_hours, tuple(extra.get("deliveryHours", (0, 0)))))


class Fixes:
    """What a desk with fallback fixes does differently: the note's limits merged with the fix, and a higher opening
    fee for an urgent car. Only for won orders with a fix in `self.fixes`; a quote comes before the win and reads the rules alone."""

    fixes: dict

    def limits(self, request, p: dict) -> notes.Limits:
        rules = super().limits(request, p)
        fix = self.fixes.get(request["id"]) if request and request["id"] in self.orders else None
        return merge(rules, fix) if fix and p["read_notes"] else rules

    def opening(self, request, p: dict) -> float:
        fee = super().opening(request, p)
        fix = self.fixes.get(request["id"]) if request["id"] in self.orders else None
        return min(max(fee, FEE_CAP), fee + fix["fee"]) if fix and fix.get("fee") else fee

    def with_fix(self, order, retry):
        """The post's Retry with the fix: plates, a manual licence, a later start, and for a car on summer tyres a start
        after the snow forecast at its pickup place, when that leaves the window open (a visit in snow fails: not ready)."""
        from spread.starter import Retry

        fix = self.fixes.get(order["id"])
        if not fix:
            return retry
        start = max(retry.pickup_from, fix.get("pickupFrom", 0))
        if fix.get("summer"):
            leg = order["legs"][0]
            for f in sorted(self.forecasts, key=lambda f: f["from"]):
                if leg["pickup"]["placeId"] in f["placeIds"] and f["from"] <= max(start, self.now, leg["pickup"]["window"]["from"]) < f["to"] \
                        and f["to"] < leg["pickup"]["window"]["to"] - HOUR:
                    start = f["to"]
        return Retry(start, retry.manual_licence or fix.get("manual", False), retry.plates or fix.get("plates", False))


class Decision:
    """One note through the fallback: the trigger, the call, the vetted actions and the fix. `line` is its review.jsonl entry."""

    def __init__(self, request: dict, deadline: int, facts: notes.Facts, news: dict, ask, risky: tuple = (), disagree: tuple = ()):
        text, arrived = request["note"]["text"], request["arrivedAt"]
        limits = notes.limits(request["note"], arrived)
        self.why = trigger(text, arrived, facts, limits, news, disagree)
        self.fix, self.line = {}, None
        if not self.why:
            return
        msgs = messages(text, reading(facts, limits, arrived), watch.stated(request, deadline))
        answer = ask(msgs)
        actions = parse(answer.get("content")) if not answer.get("error") else None
        error = answer.get("error") or (None if actions is not None else "unreadable")
        kept, dropped = vet(actions or [], text, request, deadline, facts, limits)
        self.fix = fix_of(kept, risky) if not error else {}
        self.line = {"source": "fallback", "orderId": request["id"], "text": text, "trigger": self.why, "actions": kept, "dropped": dropped,
                     "fix": self.fix, "cited": [a["cite"] for a in kept if a.get("cite")], "seconds": answer.get("seconds"), "error": error,
                     "cached": answer.get("cached", False)}


class ActionDesk(Fixes, Policy):
    """The policy of a practice week with the fallback (play.py, when the variant has "note_actions"). The model answers
    before the first post of a won note; an answer slower than HOLD seconds is dropped, as the live hold would post
    without it. The answers are cached in the data folder, so a week played again gives the same posts."""

    def __init__(self, world, level, now, params, roster, map_, ask=None):
        params = dict(params)
        self.version, self.risky = params.pop("note_actions"), tuple(params.pop("note_actions_risky", ()))
        super().__init__(world, level, now, params, roster, map_)
        self.p = {**self.p, "note_actions": self.version, **({"note_actions_risky": list(self.risky)} if self.risky else {})}
        if ask is None:
            from .server import data_dir
            ask = Cache(data_dir() / "note-actions" / "cache.jsonl").ask
        self.ask, self.fixes, self.decided, self.vocabulary = ask, {}, set(), watch.Vocabulary.load()
        self.review: list[dict] = []

    def post(self, order, legs, retry=None):
        from spread.starter import Retry
        retry = retry or Retry()
        request = self.requests.get(order["id"])
        if order["id"] not in self.decided and request and request.get("note") and self.p["read_notes"]:
            self.decided.add(order["id"])
            facts = notes.read(request["note"], request["arrivedAt"])
            decision = Decision(request, order["deadline"], facts, self.vocabulary.score(request["note"]["text"]), self.ask, self.risky)
            if decision.line:
                late = (decision.line["seconds"] or 0) > HOLD
                if decision.fix and not late:
                    self.fixes[order["id"]] = decision.fix
                self.review.append({**decision.line, "minute": self.now, "late": late})
        super().post(order, legs, self.with_fix(order, retry))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("check", help="the trigger, the model and the vetted actions on one note")
    one.add_argument("text")
    one.add_argument("--arrived", type=int, default=600, help="the minute the request arrived: 600 is Monday 10:00")
    one.add_argument("--deadline", type=int, default=2 * DAY + 17 * HOUR, help="the order's deadline: 3900 is Wednesday 17:00")
    args = parser.parse_args()
    hours = {"opens": 8 * HOUR, "closes": 18 * HOUR, "weekdays": [0, 1, 2, 3, 4], "saturday": None}
    request = {"id": "R1", "arrivedAt": args.arrived, "note": {"text": args.text},
               "legs": [{"pickup": {"window": {"from": args.arrived, "to": args.deadline}, "hours": hours, "privateAddress": False},
                         "delivery": {"hours": hours, "privateAddress": False}}]}
    decision = Decision(request, args.deadline, notes.read(request["note"], args.arrived), watch.Vocabulary.load().score(args.text),
                        lambda msgs: call(msgs), risky=RISKY)
    print(json.dumps(decision.line or {"trigger": [], "note": "the rules decide alone"}, ensure_ascii=False, indent=1, default=list))


if __name__ == "__main__":
    main()
