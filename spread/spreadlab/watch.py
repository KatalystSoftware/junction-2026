"""The note watcher of the live desk: a second reader that checks the rules' reading of each won note, and a log of
what the notes say through the week. Off unless `live.py` runs with `--watch-notes`.

    uv run python -m spreadlab.watch check "Valmis vasta to klo 14, ei kilpiä" --arrived 600   # one note: the rules, the model, the fix
    uv run python -m spreadlab.watch review <world id>                                       # the notes the model said the rules missed
    uv run python -m spreadlab.watch build                                                   # note-vocab.json from the archive's notes

For each won order with a note, a small model gets the note and what `notes.read` made of it, and answers yes or no:
did the rules capture every operational fact in the note? On a no it names each missing or wrong fact. The desk then
applies only the corrections that make a post safer: plates to bring, a manual licence, or a ready time later than
the rules read, never earlier. The car's first post waits for the answer briefly (live.HOLD_SECONDS); a later answer
withdraws the gig and posts it again, as after a change of plan, or, when a driver has booked the gig already, waits
for the next post of the car.

The model runs on a thread of its own, so no quote waits for it. A call that fails or runs out of time leaves the
rules' post as it is. Every no goes to review.jsonl in the world's folder with the note, the rules' reading and the
model's answer: what `notes.py` should learn next.

The same thread scores each request's note against the words and sentences of the archive's 200,000 notes, and
counts what the notes say (ready times, closing times, deadlines, plates, manual cars): a note with a word or a
sentence that the archive has not seen, and a fact that notes mention far more often than in the archive, go to the
log and the console.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import json
import math
import os
import queue
import re
import threading
import time
import urllib.error
import urllib.request
from collections import Counter, deque
from pathlib import Path
from typing import Callable, Optional

from . import notes

DAY, HOUR = 24 * 60, 60
WEEK = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
VOCAB = Path(__file__).with_name("note-vocab.json")

# NVIDIA's free endpoint, as in the note study (scratch/llm-notes): Lightning answered in 1.0 s at the median and 2.5 s
# at the 95th percentile, and read the fewest notes wrong of the three models tried. The free tier takes about 40 calls a minute.
# Another OpenAI-compatible endpoint, such as a dedicated container without the free tier's limit, comes from the
# environment: NOTE_MODEL_URL (the base URL), NOTE_MODEL, NOTE_MODEL_KEY (the name of the variable that holds its key)
# and NOTE_MODEL_RPM. Only Lightning on NVIDIA's endpoint has been measured (scratch/llm-notes/verify.py).
URL = os.environ.get("NOTE_MODEL_URL", "https://integrate.api.nvidia.com/v1").rstrip("/") + "/chat/completions"
MODEL = os.environ.get("NOTE_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
KEY = os.environ.get("NOTE_MODEL_KEY", "NVIDIA_API_KEY")
TIMEOUT = 6.0  # seconds for one call; a held post goes with the rules after live.HOLD_SECONDS whatever the call does
PER_MINUTE = int(os.environ.get("NOTE_MODEL_RPM", "30"))  # calls a minute, under the free tier's 40
STALE = 120.0  # real seconds after the win: a check that has waited this long for the rate limit is dropped

FACTS = ("ready", "no_plates", "manual", "deadline", "pickup_hours", "delivery_hours", "summer_tyres", "other")
SYSTEM = """A rule-based reader extracted facts from a note that a Finnish car dealer wrote on a car transport request. Notes are in Finnish, Swedish or English, with abbreviations and typos. You check whether the extraction captured every operational fact that the note states. Answer with one JSON object and nothing else.

The reader extracts only three facts:
- "ready": the first day and time the car can be collected: when it is ready, or when it is handed over after payment. Null when the note states none.
- "no_plates": true when the car has no registration plates.
- "manual": true when the car has a manual gearbox.

The operational facts of a note are those three, and:
- "deadline": a time by which the car must be at its destination.
- "pickup_hours": opening or closing hours of the pickup site, or a time by which the car must be collected.
- "delivery_hours": opening or closing hours of the receiving site.
- "summer_tyres": the car is on summer tyres.
- "other": anything else that changes when or how a driver can collect, drive or deliver the car.
Spare tyres or other things that travel with the car, where the car is parked, keys, calls, reference numbers, greetings and thanks are not operational facts.

You also get what the request itself states: the pickup window, the opening hours of both sites, and the deadline at the destination. A note that repeats them, or states a time inside them that changes nothing, states no new fact.

When the extraction holds every operational fact that the note states beyond the request, and nothing that the note does not state, answer {"answer": "yes"}.
Otherwise answer {"answer": "no", "problems": [...]}, with one entry for each fact that the extraction misses or has wrong:
- "ready" and "deadline": {"fact": ..., "day": ..., "time": ...}, as the note states it.
- "pickup_hours" and "delivery_hours": {"fact": ..., "opens": ..., "closes": ...}.
- "no_plates", "manual" and "summer_tyres": {"fact": ..., "value": true or false}, as the note states it.
- "other": {"fact": "other", "value": "a few words"}.

Days: "today", "tomorrow", "day_after_tomorrow", "mon", "tue", "wed", "thu", "fri", "sat", or null. A time with no day is "today". Give a weekday as the note names it; do not convert it.
Times: "HH:MM" on a 24-hour clock. Digits are the hour on a 24-hour clock unless am or pm follows. An hour written as a word is the working hour with that number, from 9 to 17: "kolmelta", "three" and "tre" are 15:00, "yhdeksältä" is 09:00, "kahdeltatoista" is 12:00. "Half three", "puoli kolme" and "halv tre" are 14:30: half an hour before three.
When the note corrects itself ("korjaus", "eiku", "ei kun", "sorry", "rättelse"), the correction counts. A corrected day keeps the earlier time, and a corrected time keeps the earlier day. A time that the note denies ("not 3pm") is not a fact."""
def site(opens: str, closes: str, saturday: Optional[tuple[str, str]] = None) -> dict:
    return {"weekdays": f"{opens}-{closes}", "saturday": f"{saturday[0]}-{saturday[1]}" if saturday else "closed"}


SHOTS = [  # made up, as the handbook's examples are
    ("Klar först på onsdag kl 12. Bilen saknar skyltar.", {"ready": {"day": "wed", "time": "12:00"}, "no_plates": True, "manual": False},
     {"pickup_window": {"from": {"day": "today", "time": "14:00"}, "to": {"day": "thu", "time": "18:00"}}, "pickup_hours": site("08:00", "18:00"),
      "delivery_hours": site("09:00", "17:00"), "deadline": {"day": "fri", "time": "17:00"}}, {"answer": "yes"}),
    ("Moi, auto valmis huomenna kolmelta, eiku ylihuomenna. Viite 55120.", {"ready": {"day": "tomorrow", "time": "15:00"}, "no_plates": False, "manual": False},
     {"pickup_window": {"from": {"day": "today", "time": "11:00"}, "to": {"day": "fri", "time": "20:00"}}, "pickup_hours": site("08:00", "20:00", ("10:00", "16:00")),
      "delivery_hours": "private address", "deadline": {"day": "sat", "time": "12:00"}},
     {"answer": "no", "problems": [{"fact": "ready", "day": "day_after_tomorrow", "time": "15:00"}]}),
    ("Must be at destination by tomorrow 5pm. Stick shift. Call 15 min before. Spare wheels in the boot.", {"ready": None, "no_plates": False, "manual": True},
     {"pickup_window": {"from": {"day": "today", "time": "09:00"}, "to": {"day": "tomorrow", "time": "20:00"}}, "pickup_hours": site("08:00", "20:00"),
      "delivery_hours": site("08:00", "20:00"), "deadline": {"day": "tomorrow", "time": "20:00"}},
     {"answer": "no", "problems": [{"fact": "deadline", "day": "tomorrow", "time": "17:00"}]}),
    ("Avaimet tiskiltä, soita 20 min ennen. Talvirenkaat takakontissa. Vastaanotto arkisin 9-17. Kiitos!", {"ready": None, "no_plates": False, "manual": False},
     {"pickup_window": {"from": {"day": "today", "time": "13:00"}, "to": {"day": "tomorrow", "time": "18:00"}}, "pickup_hours": site("09:00", "18:00"),
      "delivery_hours": site("09:00", "17:00"), "deadline": {"day": "tomorrow", "time": "17:00"}}, {"answer": "yes"}),
    ("Nouto arkisin 9-15.30. Vielä kesärenkaat, ilman kilpiä.", {"ready": None, "no_plates": False, "manual": False},
     {"pickup_window": {"from": {"day": "tomorrow", "time": "08:00"}, "to": {"day": "thu", "time": "17:00"}}, "pickup_hours": site("08:00", "17:00"),
      "delivery_hours": site("09:00", "18:00", ("10:00", "14:00")), "deadline": {"day": "fri", "time": "18:00"}},
     {"answer": "no", "problems": [{"fact": "pickup_hours", "opens": "09:00", "closes": "15:30"}, {"fact": "summer_tyres", "value": True},
                                   {"fact": "no_plates", "value": True}]}),
    ("Maksun jälkeen, ei ennen klo 13.30. Automaatti.", {"ready": {"day": "today", "time": "13:30"}, "no_plates": False, "manual": True},
     {"pickup_window": {"from": {"day": "today", "time": "10:00"}, "to": {"day": "tomorrow", "time": "17:00"}}, "pickup_hours": site("08:00", "17:00"),
      "delivery_hours": site("08:00", "17:00"), "deadline": {"day": "tomorrow", "time": "17:00"}},
     {"answer": "no", "problems": [{"fact": "manual", "value": False}]}),
]


def clock(minute: int) -> str:
    return f"{minute % DAY // HOUR:02d}:{minute % HOUR:02d}"


def day_time(minute: int, arrived_at: int) -> dict:
    """A world minute in the prompt's words: a day counted from the request's arrival, and a clock time."""
    offset = minute // DAY - arrived_at // DAY
    return {"day": ["today", "tomorrow", "day_after_tomorrow"][offset] if 0 <= offset < 3 else WEEK[minute // DAY % 7], "time": clock(minute)}


def reading(facts: notes.Facts, arrived_at: int) -> dict:
    """What the rules read, in the words of the prompt."""
    return {"ready": day_time(facts.pickup_from, arrived_at) if facts.pickup_from else None, "no_plates": facts.plates, "manual": facts.manual}


def stated(request: dict, deadline: int) -> dict:
    """What the request itself states, which a note may repeat: the first car's pickup window, the sites' hours and the deadline."""
    leg, arrived = request["legs"][0], request["arrivedAt"]

    def hours(stop: dict):
        h = stop.get("hours")
        if stop.get("privateAddress") or not h:
            return "private address"
        saturday = h.get("saturday")
        return {"weekdays": f"{clock(h['opens'])}-{clock(h['closes'])}", "saturday": f"{clock(saturday['opens'])}-{clock(saturday['closes'])}" if saturday else "closed"}
    window = leg["pickup"]["window"]
    return {"pickup_window": {"from": day_time(window["from"], arrived), "to": day_time(window["to"], arrived)}, "pickup_hours": hours(leg["pickup"]),
            "delivery_hours": hours(leg["delivery"]), "deadline": day_time(deadline, arrived)}


def messages(text: str, read: dict, known: dict) -> list[dict]:
    out = [{"role": "system", "content": SYSTEM}]
    for note, facts, request, answer in SHOTS + [(text, read, known, None)]:
        out.append({"role": "user", "content": f"Note: {note}\nRequest: {json.dumps(request, ensure_ascii=False)}\nExtraction: {json.dumps(facts, ensure_ascii=False)}"})
        if answer is not None:
            out.append({"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)})
    return out


def parse(content: Optional[str]) -> Optional[dict]:
    """The model's answer: {"answer": "yes" or "no", "problems": [...]}, or None when it cannot be read."""
    try:
        answer = json.loads(re.search(r"\{.*\}", content or "", re.S)[0])
    except (TypeError, ValueError):
        return None
    verdict = str(answer.get("answer", "")).strip().lower() if isinstance(answer, dict) else ""
    if verdict not in ("yes", "no"):
        return None
    problems = [p for p in answer.get("problems") or [] if isinstance(p, dict) and p.get("fact") in FACTS] if verdict == "no" else []
    return {"answer": verdict, "problems": problems}


def ask(text: str, read: dict, known: dict, key: str, model: str = MODEL, timeout: float = TIMEOUT) -> dict:
    """One call: {"answer", "problems", "seconds"}, with "error" when the call failed and "answer" None."""
    # Claude models refuse a temperature (HTTP 400 "temperature is deprecated for this model"), and Haiku 5.5 thinks
    # unless told not to: 1.2 s at the median and 1.9 s at p95, against 0.8 s without. The others get a temperature of 0.
    body = json.dumps({"model": model, "messages": messages(text, read, known), "max_tokens": 300,
                       **({"thinking": {"type": "disabled"}} if model.startswith("claude") else {"temperature": 0}),
                       "chat_template_kwargs": {"enable_thinking": False}}).encode()
    request = urllib.request.Request(URL, body, {"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content = json.load(response)["choices"][0]["message"].get("content")
    except urllib.error.HTTPError as error:
        return {"answer": None, "problems": [], "seconds": round(time.monotonic() - started, 3), "error": f"HTTP {error.code}"}
    except Exception as error:  # a timeout, a lost connection, an answer without choices
        return {"answer": None, "problems": [], "seconds": round(time.monotonic() - started, 3), "error": type(error).__name__}
    parsed = parse(content) or {"answer": None, "problems": [], "error": "unreadable"}
    return {**parsed, "seconds": round(time.monotonic() - started, 3), "content": content}


def minute_of(clock) -> Optional[int]:
    match = re.fullmatch(r"(\d{1,2})[:.](\d{2})", clock.strip()) if isinstance(clock, str) else None
    return int(match[1]) * HOUR + int(match[2]) if match and int(match[1]) <= 24 and int(match[2]) < 60 else None


def when(day, clock, arrived_at: int) -> Optional[int]:
    """The world minute of a day word and a clock time, read as RULES.md says; None when there is no time."""
    minute = minute_of(clock)
    if minute is None:
        return None
    day = day.lower() if isinstance(day, str) else "today"
    offsets = {"today": 0, "tomorrow": 1, "day_after_tomorrow": 2}
    if day in offsets:
        offset = offsets[day]
    elif day[:3] in WEEK:
        offset = (WEEK.index(day[:3]) - arrived_at // DAY % 7 - 2) % 7 + 2  # a weekday name is 2 to 6 days after the request
    else:
        return None
    return (arrived_at // DAY + offset) * DAY + minute


def material(problems: list[dict], facts: notes.Facts, request: dict, deadline: int) -> list[dict]:
    """The problems that would change what the desk knows: a ready time other than the one it posts from, a deadline
    before the order's, site hours narrower than the request's, plates or a manual gearbox other than the rules read,
    summer tyres, and anything else. A model often names a fact that the request or the rules already hold."""
    leg, arrived = request["legs"][0], request["arrivedAt"]
    start = min(l["pickup"]["window"]["from"] for l in request["legs"])
    kept = []
    for problem in problems:
        fact = problem["fact"]
        if fact == "ready":
            at = when(problem.get("day"), problem.get("time"), arrived)
            keep = at is not None and max(start, at) != max(start, facts.pickup_from)
        elif fact == "deadline":
            at = when(problem.get("day"), problem.get("time"), arrived)
            keep = at is not None and at < deadline
        elif fact in ("pickup_hours", "delivery_hours"):
            stop = leg["pickup" if fact == "pickup_hours" else "delivery"]
            hours = stop.get("hours") or {}
            opens, closes = minute_of(problem.get("opens")), minute_of(problem.get("closes"))
            keep = bool(hours) and ((opens is not None and opens > hours["opens"]) or (closes is not None and closes < hours["closes"]))
        elif fact in ("no_plates", "manual"):
            keep = isinstance(problem.get("value"), bool) and problem["value"] != (facts.plates if fact == "no_plates" else facts.manual)
        elif fact == "summer_tyres":
            keep = problem.get("value") is True
        else:
            keep = bool(problem.get("value"))
        if keep:
            kept.append(problem)
    return kept


tag = functools.lru_cache(maxsize=50_000)(notes.tag)  # notes have few distinct words, and each tag is a search through the rules' word lists


CUSTOMER = re.compile(r"asiaka|asiakk|customer|client|kund")  # "the customer collects at 12": a time at the delivery


def about_pickup(text: str, minute: int, arrived_at: int) -> bool:
    """Whether the note states this time in a clause about the pickup, on a day that the note names. A clause is about
    the pickup when it has no word for the delivery, a site that closes or the customer: a model calls "the customer
    collects at 12, the car must be there by then" a ready time. The day can come from a correction elsewhere in the
    note ("eikun ylihuomenna"); a model has read "huomenna" as the day after tomorrow."""
    text = notes.SHORT.sub(r"\1 ", notes.RANGE.sub(" ", text.lower()))
    arrived_day = arrived_at // DAY % 7
    days = set()  # the days that the note names, counted from the request's arrival
    for token in notes.TOKEN.findall(text):
        word, named = tag(token), notes.weekday(token)
        if word in ("today", "tomorrow", "overmorrow"):
            days.add(("today", "tomorrow", "overmorrow").index(word))
        elif named is not None:
            days.add((named - arrived_day - 2) % 7 + 2)
    offset = minute // DAY - arrived_at // DAY
    if offset not in days and (days or offset != 0):
        return False
    for clause in re.split(r",|\s[-–]\s", " ".join(notes.SENTENCE.split(text))):
        tokens = notes.TOKEN.findall(clause)
        tags = {tag(token) for token in tokens}
        if "there" in tags or "closed" in tags or CUSTOMER.search(clause):
            continue
        if any(t.minute == minute % DAY for t in notes.times(tokens, arrived_day)):
            return True
    return False


# A fix of plates or of the gearbox needs a word about them in the note, also one that the rules do not read: the model
# has added plates to a note about spare tyres and a parking bay.
ABOUT_PLATES = re.compile(r"plate|plaat|tags?\b|regist|rekist|rek\.|kilp|kilv|skylt")  # not "number": notes give order numbers
ABOUT_GEARS = re.compile(r"manu|clutch|pedal|gear|stick|shift|vaiht|kytkin|koppling|växel|kepp")


def safe_fix(problems: list[dict], facts: notes.Facts, request: dict) -> dict:
    """The corrections that the desk applies by itself: plates, a manual licence, and a ready time later than the
    rules' and the request's window, stated in a sentence about the pickup. Each needs the note's own words for it. A
    fact that the model says the rules have and the note does not is not undone."""
    fix, start = {}, max(facts.pickup_from, min(leg["pickup"]["window"]["from"] for leg in request["legs"]))
    text = (request.get("note") or {}).get("text", "").lower()
    for problem in problems:
        if problem["fact"] == "ready":
            at = when(problem.get("day"), problem.get("time"), request["arrivedAt"])
            if at is not None and at > start and about_pickup(text, at, request["arrivedAt"]):
                fix["pickupFrom"] = max(fix.get("pickupFrom", 0), at)
        elif problem["fact"] == "no_plates" and problem.get("value") is True and not facts.plates and ABOUT_PLATES.search(text):
            fix["plates"] = True
        elif problem["fact"] == "manual" and problem.get("value") is True and not facts.manual and ABOUT_GEARS.search(text):
            fix["manual"] = True
    return fix


# What a note talks about, by the rules' words, for the drift log. Each request's note counts once for each.
SAYS = {"ready": "a ready time", "closing": "a closing time", "by": "a limit (by, ennen, senast)", "delivery": "the delivery", "hours": "opening hours",
        "plates": "plates", "manual": "a manual car", "summer": "summer tyres", "new": "a new word or sentence"}
SUMMER = re.compile(r"kesär|kesäre|summer ?tyre|summer ?tire|sommardäck|sommarhjul")


def topics(text: str, arrived_at: int) -> set[str]:
    facts = notes.read({"text": text}, arrived_at)
    tags = {tag(token) for token in notes.TOKEN.findall(text.lower())}
    found = {name for name, on in (("ready", facts.pickup_from > 0), ("plates", facts.plates), ("manual", facts.manual),
                                   ("closing", "closed" in tags), ("by", "by" in tags), ("delivery", "there" in tags),
                                   ("hours", bool(notes.RANGE.search(text.lower()))), ("summer", bool(SUMMER.search(text.lower())))) if on}
    return found


def sentences(text: str) -> list[str]:
    """The note's sentences, digits masked: the patterns of the note study (scratch/llm-notes/novelty.py)."""
    text = re.sub(r"\d", "0", text.lower())
    return [s.strip() for s in re.split(r"[.!?;/|]+\s+|\n", text) if s.strip()]


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-zåäö]+", text.lower()))


def pattern_hash(sentence: str) -> str:
    return hashlib.blake2b(sentence.encode(), digest_size=4).hexdigest()


class Vocabulary:
    """The words and sentence patterns of the archive's notes, and how often a note talks about each topic."""

    def __init__(self, data: dict):
        self.words = set(data["words"])
        self.patterns = set(data["patterns"])
        self.topics = data["topics"]  # topic -> share of notes
        self.by_length: dict[int, list[str]] = {}
        for word in self.words:
            self.by_length.setdefault(len(word), []).append(word)

    @classmethod
    def load(cls, path: Path = VOCAB) -> "Vocabulary":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def score(self, text: str) -> dict:
        """The words that the archive has not seen, split into typos (one edit from a known word) and new words, and
        the sentences whose pattern it has not seen."""
        unseen = sorted(words(text) - self.words)
        typos = [w for w in unseen if any(notes.near(w, k) for n in (len(w) - 1, len(w), len(w) + 1) for k in self.by_length.get(n, ()))]
        new_sentences = [s for s in sentences(text) if pattern_hash(s) not in self.patterns]
        return {"typos": typos, "newWords": [w for w in unseen if w not in typos], "newSentences": new_sentences}


def build(out: Path = VOCAB) -> None:
    """note-vocab.json from the archive's notes (data/llm-notes/notes.jsonl, which scratch/llm-notes/extract.py writes)."""
    from .server import data_dir

    rows = [json.loads(line) for line in open(data_dir() / "llm-notes" / "notes.jsonl", encoding="utf-8")]
    # How often a new week's note has a new word or sentence: 60 weeks held out against the archive's other weeks.
    seeds = sorted({row["seed"] for row in rows})
    held = set(seeds[::len(seeds) // 60][:60])
    known = Vocabulary({"words": sorted({w for row in rows if row["seed"] not in held for w in words(row["note"]["text"])}),
                        "patterns": sorted({pattern_hash(s) for row in rows if row["seed"] not in held for s in sentences(row["note"]["text"])}), "topics": {}})
    test = [row["note"]["text"] for row in rows if row["seed"] in held]
    new = sum(1 for text in test if (lambda news: news["newWords"] or news["newSentences"])(known.score(text)))
    seen_words, patterns, counts = set(), set(), Counter({"new": new * len(rows) / len(test)})
    for text, n in Counter(row["note"]["text"] for row in rows).items():  # a ready time reads the same whatever the day it arrives
        seen_words |= words(text)
        patterns |= {pattern_hash(s) for s in sentences(text)}
        for topic in topics(text, 600):
            counts[topic] += n
    data = {"notes": len(rows), "weeks": len({row["seed"] for row in rows}), "words": sorted(seen_words), "patterns": sorted(patterns),
            "topics": {topic: round(counts[topic] / len(rows), 5) for topic in sorted(counts)}}
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{out.name}: {data['notes']} notes of {data['weeks']} weeks, {len(seen_words)} words, {len(patterns)} sentence patterns; "
          f"topics {data['topics']}")


class Drift:
    """The share of the last notes that talk about each topic, against the archive's. A topic that notes mention far
    more often than they used to is news: the week may be one in which notes carry more than the rules read."""

    WINDOW, LEAST, FACTOR, Z = 200, 6, 2.0, 4.0

    def __init__(self, base: dict[str, float]):
        self.base, self.last = base, deque(maxlen=self.WINDOW)
        self.day: Counter = Counter()
        self.day_notes = 0
        self.alerted: dict[str, float] = {}  # topic -> the share at its last alert

    def add(self, found: set[str]) -> list[dict]:
        self.last.append(found)
        self.day.update(found)
        self.day_notes += 1
        n, alerts = len(self.last), []
        if n < 50:
            return alerts
        for topic in found:
            k, p = sum(1 for f in self.last if topic in f), self.base.get(topic, 0.0)
            share, z = k / n, (k - n * p) / math.sqrt(max(n * p * (1 - p), 1e-9))
            if k >= self.LEAST and share >= self.FACTOR * p + 0.02 and z >= self.Z and share >= 1.5 * self.alerted.get(topic, 0):
                self.alerted[topic] = share
                alerts.append({"topic": topic, "notes": n, "with": k, "share": round(share, 4), "archive": p, "z": round(z, 1)})
        return alerts

    def end_day(self) -> dict:
        shares = {topic: round(self.day[topic] / self.day_notes, 4) for topic in sorted(self.day)} if self.day_notes else {}
        line = {"notes": self.day_notes, "shares": shares}
        self.day, self.day_notes = Counter(), 0
        self.alerted = {t: s / 1.5 for t, s in self.alerted.items()}  # a new day can alert again at the same level
        return line


class Watcher(threading.Thread):
    """The thread that reads the notes beside the desk. The desk hands it work and takes its answers; it never waits."""

    def __init__(self, log, folder: Path, verify: Optional[Callable[[str, dict], dict]] = None, vocabulary: Optional[Vocabulary] = None,
                 per_minute: int = PER_MINUTE, echo: bool = True):
        super().__init__(daemon=True, name="notes")
        self.log, self.verify, self.vocabulary, self.echo = log, verify, vocabulary or Vocabulary.load(), echo
        self.review = folder / "review.jsonl"
        self.inbox: queue.PriorityQueue = queue.PriorityQueue()
        self.out: queue.Queue = queue.Queue()
        self.drift = Drift(self.vocabulary.topics)
        self.gap, self.next_call = 60.0 / per_minute, 0.0
        self.inflight: set[str] = set()
        self.count, self.stopped, self.lock = Counter(), threading.Event(), threading.Lock()

    # The desk's side: each returns at once.

    def observe(self, request: dict) -> None:
        """A price request with a note: scored for news, counted for drift."""
        self.inbox.put((1, time.monotonic(), "observe", request))

    def check(self, order_id: str, request: dict, deadline: int, facts: notes.Facts, minute: int) -> None:
        """A won order with a note, after the rules' post: the model checks the rules' reading."""
        with self.lock:
            if order_id in self.inflight:
                return
            self.inflight.add(order_id)
        self.inbox.put((0, time.monotonic(), "check", (order_id, request, deadline, facts, minute)))

    def results(self) -> list[dict]:
        found = []
        while True:
            try:
                found.append(self.out.get_nowait())
            except queue.Empty:
                return found

    def end_day(self, day: int) -> None:
        self.inbox.put((2, time.monotonic(), "day", day))

    # The thread's side.

    def run(self) -> None:
        while not self.stopped.is_set():
            try:
                _, queued, kind, item = self.inbox.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                if kind == "observe":
                    self.see(item)
                elif kind == "check":
                    self.answer(queued, *item)
                else:
                    self.log.write("note_day", day=item, **self.drift.end_day())
            except Exception as error:  # the watcher must not stop: the desk plays on without it
                self.log.write("watch_error", kind=kind, error=repr(error))
                if kind == "check":
                    with self.lock:
                        self.inflight.discard(item[0])

    def see(self, request: dict) -> None:
        text = request["note"]["text"]
        news = self.vocabulary.score(text)
        found = topics(text, request["arrivedAt"])
        if news["newWords"] or news["newSentences"]:
            found.add("new")
            self.count["new"] += 1
            self.log.write("note_new", requestId=request["id"], text=text, **news)
        self.count["seen"] += 1
        for alert in self.drift.add(found):
            self.log.write("note_drift", minute=request["arrivedAt"], **alert)
            self.say(f"Notes: {alert['with']} of the last {alert['notes']} notes mention {SAYS.get(alert['topic'], alert['topic'])} ({alert['share']:.0%}), "
                     f"against {alert['archive']:.1%} in the archive. They may carry more than the rules read: see review.jsonl.")

    def answer(self, queued: float, order_id: str, request: dict, deadline: int, facts: notes.Facts, minute: int) -> None:
        read, known, text = reading(facts, request["arrivedAt"]), stated(request, deadline), request["note"]["text"]
        news = self.vocabulary.score(text)
        verdict = {"answer": None, "problems": [], "error": "no model"}
        for attempt in range(3) if self.verify is not None else ():
            wait = max(0.0, self.next_call - time.monotonic())
            if time.monotonic() - queued + wait > STALE:
                verdict = {"answer": None, "problems": [], "error": "stale"}
                break
            time.sleep(wait)
            self.next_call = time.monotonic() + self.gap
            verdict = self.verify(text, read, known)
            if verdict.get("error") not in ("HTTP 429", "HTTP 503"):
                break
            self.next_call = time.monotonic() + 5 * (attempt + 1)  # the free tier's limit: wait, and try again while the check is fresh
        said = verdict["problems"]
        if verdict["answer"] == "no":  # a no counts when it names a fact that would change what the desk knows
            problems = material(said, facts, request, deadline)
            # "other" alone goes to the review queue, not as a no: the model names spare tyres and parked cars there.
            verdict = {**verdict, "problems": problems, "answer": "no" if any(p["fact"] != "other" for p in problems) else "other" if problems else "yes"}
        fix = safe_fix(verdict["problems"], facts, request) if verdict["answer"] == "no" else {}
        self.count[verdict["answer"] or "unchecked"] += 1
        self.count["fixed"] += bool(fix)
        line = {"orderId": order_id, "minute": minute, "text": text, "rules": read, "answer": verdict["answer"], "problems": verdict["problems"],
                "said": said, "fix": fix, "seconds": verdict.get("seconds"), "error": verdict.get("error"), **news}
        self.log.write("note_check", **line)
        if verdict["answer"] in ("no", "other"):
            with open(self.review, "a", encoding="utf-8") as f:
                f.write(json.dumps({"wall": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **line}, ensure_ascii=False) + "\n")
        with self.lock:
            self.inflight.discard(order_id)
        self.out.put({"orderId": order_id, "fix": fix, "answer": verdict["answer"], "problems": verdict["problems"]})

    def say(self, text: str) -> None:
        self.log.say(text) if self.echo else self.log.write("say", text=text)

    def day_line(self) -> str:
        c = self.count
        return (f"Notes so far: {c['seen']} seen, {c['new']} with a new word or sentence; {c['yes'] + c['no'] + c['other']} won notes checked, "
                f"{c['no']} no, {c['other']} only 'other', {c['fixed']} fixed, {c['unchecked']} unchecked.")


def summary(review: Path, examples: int = 2) -> str:
    """The no answers by the fact that the model named: what notes.py should learn next."""
    if not review.exists():
        return "Review queue: empty."
    lines = [json.loads(line) for line in open(review, encoding="utf-8")]
    by = Counter(p["fact"] for line in lines for p in line["problems"])
    out = [f"Review queue: {len(lines)} notes in which the model found a fact the rules missed ({sum(1 for l in lines if l['answer'] == 'other')} only "
           f"'other', which is often noise); {sum(1 for l in lines if l['fix'])} fixed by the desk."]
    for fact, n in by.most_common():
        shown = [line for line in lines if any(p["fact"] == fact for p in line["problems"])][:examples]
        out.append(f"  {fact:<15} {n:>4}   e.g. " + " | ".join(f"\"{line['text'][:90]}\" -> " + json.dumps(next(p for p in line["problems"] if p["fact"] == fact),
                                                                                                    ensure_ascii=False) for line in shown))
    return "\n".join(out)


def model_verifier() -> Optional[Callable[[str, dict], dict]]:
    """The model, when its key is in the environment; else None, and the rules read alone."""
    key = os.environ.get(KEY)
    return (lambda text, read, known: ask(text, read, known, key)) if key else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build", help="note-vocab.json from the archive's notes")
    one = commands.add_parser("check", help="the rules and the model on one note")
    one.add_argument("text")
    one.add_argument("--arrived", type=int, default=600, help="the minute the request arrived: 600 is Monday 10:00")
    one.add_argument("--deadline", type=int, default=2 * DAY + 17 * HOUR, help="the order's deadline: 3900 is Wednesday 17:00")
    review = commands.add_parser("review", help="the review queue of a live run")
    review.add_argument("world")
    args = parser.parse_args()
    if args.command == "build":
        build()
    elif args.command == "review":
        from .live import folder_of
        print(summary(folder_of(args.world) / "review.jsonl", examples=5))
    else:
        verify = model_verifier()
        if verify is None:
            raise SystemExit(f"{KEY} is not set.")
        facts = notes.read({"text": args.text}, args.arrived)
        read = reading(facts, args.arrived)
        hours = {"opens": 8 * HOUR, "closes": 18 * HOUR, "weekdays": [0, 1, 2, 3, 4], "saturday": None}
        request = {"arrivedAt": args.arrived, "legs": [{"pickup": {"window": {"from": args.arrived, "to": args.deadline}, "hours": hours, "privateAddress": False},
                                                         "delivery": {"hours": hours, "privateAddress": False}}]}
        verdict = verify(args.text, read, stated(request, args.deadline))
        print(json.dumps({"rules": read, "model": verdict, "fix": safe_fix(verdict["problems"], facts, request) if verdict["answer"] == "no" else {},
                          "news": Vocabulary.load().score(args.text)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
