"""Reads a dealer's note for what the first posting needs: the first minute the car can be collected, plates to
bring, and a manual licence. The kit's starter learns these from a failed visit, which costs half a fee and often
the deadline. RULES.md (Notes and changes of plan) says how days and times read; scratch/notes_check.py measures this
reader against what the reveal says was true.

Notes have typos, so a word counts when it is one edit from a known word.
"""
from __future__ import annotations

import re
from typing import NamedTuple, Optional

DAY, HOUR = 24 * 60, 60


class Facts(NamedTuple):
    pickup_from: int = 0  # the first minute the car can be collected, when the note says one; else 0
    plates: bool = False  # the car has no plates: the driver fetches transfer plates
    manual: bool = False  # the driver needs a licence for manual cars


# Words by what they say. A word of five letters or more also counts with one typo.
WORDS = {
    "tomorrow": ["huomenna", "huomen", "tomorrow", "tmrw", "imorgon", "morgon", "imorron", "huomiseen"],
    "overmorrow": ["ylihuomenna", "övermorgon", "iövermorgon"],
    "today": ["tänään", "today", "idag"],
    # The car can be collected from this time on.
    "from": ["valmis", "valmiina", "valmistuu", "aikaisintaan", "jälkeen", "alkaen", "vasta", "ready", "earliest", "after", "from", "klar",
             "först", "tidigast", "efter", "framåt", "noudettavissa", "vahvistuu", "saa", "noutaa", "onwards", "färdig", "hämtas", "tidigare",
             "clears", "paid", "payment", "pays", "maksu", "maksun", "maksaa", "maksettu", "betalning", "betalt", "betalar", "released", "luovutus", "luovutetaan"],
    # The time is a limit: a deadline or a closing time.
    "by": ["mennessä", "viimeistään", "ennen", "before", "by", "latest", "senast", "före", "asti", "until", "saakka", "innan", "till", "viim"],
    "not": ["ei", "not", "inte", "ej", "no", "won", "wont", "cannot", "isn", "isnt"],
    # The sentence is about the delivery, or about the customer who waits for the car.
    "there": ["perillä", "perille", "perilla", "toimitus", "toimitettava", "kohde", "kohteessa", "destination", "arrival", "arrive", "delivered", "delivery",
              "deliver", "framme", "leverans", "levereras", "mottagning", "vastaanotto", "vastaanottava", "receiving", "there", "där", "silloin"],
    "closed": ["enää", "anymore", "ingen", "längre", "stänger", "sulkee", "sulkeutuu", "closes", "kiinni", "ketään", "nobody"],
    "correction": ["korjaus", "correction", "sorry", "rättelse", "siis", "eiku", "eikun", "nej", "anteeksi", "oikeasti", "tarkoitan", "mean", "förlåt", "korjaan"],
    "half": ["puoli", "half", "halv"],
    "clock": ["klo", "kello", "kl", "klockan", "at"],
    "noon": ["noon", "midday", "keskipäivällä", "middag"],
}
WEEKDAYS = [["maanantai", "ma", "monday", "mon", "måndag", "mån"], ["tiistai", "ti", "tuesday", "tue", "tues", "tisdag", "tis"],
            ["keskiviikko", "ke", "wednesday", "wed", "onsdag", "ons"], ["torstai", "to", "thursday", "thu", "thur", "thurs", "torsdag", "tors"],
            ["perjantai", "pe", "friday", "fri", "fredag", "fre"], ["lauantai", "la", "saturday", "sat", "lördag", "lör"]]
# An hour in words is the working hour with that number, from 9 to 17 (RULES.md). Stems, the longest first.
HOURS = [("kahdentoista", 12), ("kahdeltatoista", 12), ("kahdestatoista", 12), ("kaksitoista", 12), ("yhdentoista", 11), ("yhdeltätoista", 11),
         ("yhdestätoista", 11), ("yksitoista", 11), ("kahdeksa", 8), ("yhdeksä", 9), ("kymmene", 10), ("seitsemä", 7),
         ("yhde", 13), ("yksi", 13), ("kahde", 14), ("kaksi", 14), ("kolme", 15), ("neljä", 16), ("viide", 17), ("viisi", 17),
         ("twelve", 12), ("eleven", 11), ("ten", 10), ("nine", 9), ("eight", 8), ("one", 13), ("two", 14), ("three", 15), ("four", 16), ("five", 17),
         ("tolv", 12), ("elva", 11), ("tio", 10), ("nio", 9), ("åtta", 8), ("ett", 13), ("två", 14), ("tre", 15), ("fyra", 16), ("fem", 17)]
ENDINGS = ("ltä", "lta", "stä", "sta", "een", "en", "n", "ksi", "")  # the Finnish cases a clock time comes in
PLATES = re.compile(r"kilv|kilp|kill?p|ilman k\w{0,2}[il]\w{0,3}ä|rekkar|skylt|\bsk\w{0,2}lt(?:ar|en)|plate|plt|unregist|rekisteröim|rekisterikilv|oregistr|rek\.?kilv")
HAS_PLATES = re.compile(r"kilvet (?:on |ovat )?(?:paikallaan|kiinni|autossa)|plates (?:are )?on\b|skyltar(?:na)? (?:sitter|finns)")
MANUAL = re.compile(r"m\w?anua|manau|mnaua|manual|manuell|käsiva|keppivaiht|stick shift|ei automaat|inte automat|not automatic|not an automatic")
NOT_MANUAL = re.compile(r"ei m\w?anua|ei manau|ei mnaua|inte manuell|not (?:a )?manual|no manual")
TOKEN = re.compile(r"\d{1,2}[.:]\d{2}|\d+|[a-zåäö]+|,")


def near(word: str, known: str) -> bool:
    """The same word, or one typo away: a letter changed, added, dropped or swapped with its neighbour."""
    if word == known:
        return True
    if len(known) < 5 or abs(len(word) - len(known)) > 1:
        return False
    if len(word) == len(known):
        diff = [i for i in range(len(word)) if word[i] != known[i]]
        return len(diff) == 1 or (len(diff) == 2 and diff[1] == diff[0] + 1 and word[diff[0]] == known[diff[1]] and word[diff[1]] == known[diff[0]])
    long, short = (word, known) if len(word) > len(known) else (known, word)
    return any(long[:i] + long[i + 1:] == short for i in range(len(long)))


def tag(word: str) -> Optional[str]:
    return next((name for name, words in WORDS.items() if any(near(word, known) for known in words)), None)


def weekday(word: str) -> Optional[int]:
    """The weekday that a word names, also in a Finnish case ("torstaina") or with a typo; 0 is Monday."""
    for day, names in enumerate(WEEKDAYS):
        for name in names:
            if word == name or (len(name) >= 5 and (near(word, name) or any(near(word, name + end) for end in ("na", "hin", "sta", "en", "s", "ksi")))):
                return day
    return None


def hour_in_words(word: str) -> Optional[int]:
    for stem, hour in HOURS:
        if any(word == stem + end or (len(stem + end) >= 6 and near(word, stem + end)) for end in ENDINGS):
            return hour
    return None


class Time(NamedTuple):
    at: int  # the index of its first token
    end: int  # the index after its last token
    minute: int  # of the day
    day: Optional[int]  # days after the request arrived; None when the note names no day


def times(tokens: list[str], arrived_day: int) -> list[Time]:
    """The clock times in a note, each with the day named just before or after it."""
    found: list[Time] = []
    i = 0
    while i < len(tokens):
        token, minute, end = tokens[i], None, i + 1
        match = re.fullmatch(r"(\d{1,2})[.:](\d{2})", token)
        if match and int(match[1]) <= 24 and int(match[2]) < 60:
            minute = int(match[1]) * HOUR + int(match[2])
        elif token.isdigit() and len(token) == 4 and int(token[:2]) <= 24 and int(token[2:]) < 60 and i and tag(tokens[i - 1]) in ("clock", "from", "by", "tomorrow", "today"):
            minute = int(token[:2]) * HOUR + int(token[2:])  # "klo 1600"
        elif token.isdigit() and len(token) <= 2 and int(token) <= 24:
            before, after = tokens[i - 1] if i else "", tokens[i + 1] if i + 1 < len(tokens) else ""
            # A bare number is a time after "klo", before "am" or "pm" or a Finnish case ending ("11:stä"), or next to a day or a word of time.
            if tag(before) in ("clock", "from", "by", "tomorrow", "today", "overmorrow") or weekday(before) is not None or after in ("am", "pm", "stä", "sta", "ltä", "lta", "een", "ksi") \
                    or tag(after) in ("from", "by"):
                minute = int(token) * HOUR
        elif tag(token) == "noon":
            minute = 12 * HOUR
        elif tag(token) == "half" and i + 1 < len(tokens) and (hour_in_words(tokens[i + 1]) is not None or (tokens[i + 1].isdigit() and int(tokens[i + 1]) <= 24)):
            hour = hour_in_words(tokens[i + 1]) if hour_in_words(tokens[i + 1]) is not None else int(tokens[i + 1])
            minute, end = hour * HOUR - 30, i + 2  # "half three" is half an hour before three
        elif hour_in_words(token) is not None and (i and (tag(tokens[i - 1]) in ("clock", "tomorrow", "today", "overmorrow", "from", "by") or weekday(tokens[i - 1]) is not None)
                                                   or token.endswith(("ltä", "lta", "toista")) or (i + 1 < len(tokens) and tag(tokens[i + 1]) == "from")):
            minute = hour_in_words(token) * HOUR
        if minute is None:
            i += 1
            continue
        if end < len(tokens) and tokens[end] in ("am", "pm"):
            if tokens[end] == "pm" and minute < 12 * HOUR:
                minute += 12 * HOUR
            end += 1
        elif end < len(tokens) and tokens[end] in ("stä", "sta", "ltä", "lta", "een", "ksi"):
            end += 1
        # The day: the nearest day word in the three tokens before the time, or the one right after it.
        day = None
        for j in list(range(i - 1, max(-1, i - 4), -1)) + [end]:
            if not 0 <= j < len(tokens) or any(t.at <= j < t.end for t in found):
                continue
            named, word = weekday(tokens[j]), tag(tokens[j])
            if word in ("today", "tomorrow", "overmorrow"):
                day = ("today", "tomorrow", "overmorrow").index(word)
            elif named is not None and not (j + 1 < len(tokens) and weekday(tokens[j + 1]) is not None) and not (j and weekday(tokens[j - 1]) is not None):
                day = (named - arrived_day - 2) % 7 + 2  # a weekday name is that weekday 2 to 6 days after the request (a range "ma-pe" names no day)
            if day is not None:
                break
        found.append(Time(i, end, minute, day))
        i = end
    return found


# Opening hours: "9-16", "klo 9.00 - 14.30", "8am - 5pm", "8:sta 20:een", and the days they hold on, "ma-pe".
RANGE = re.compile(r"\b\d{1,2}(?:[.:]\d{2})?\s*(?:am|pm)?\s*[-–]\s*\d{1,2}(?:[.:]\d{2})?\s*(?:am|pm)?\b|\b\d{1,2}:st[aä]\s+\d{1,2}:een\b"
                   r"|\b(?:ma|mån|mon|må)\s*[-–]\s*(?:pe|fre|fri|la|lör|sat)\b")
# A full stop after one of these does not end a sentence.
SHORT = re.compile(r"\b(viim|kl|klo|n|ma|ti|ke|to|pe|la|mån|tis|ons|tors|fre|lör|mon|tue|tues|wed|thu|thur|thurs|fri|sat|tmrw|ref|nro|puh|tel|esim|ca|min|approx)\.")
SENTENCE = re.compile(r"[.!?;]+(?:\s+|$)|\n|\s[/|]\s")


def read(note: Optional[dict], arrived_at: int) -> Facts:
    if not note:
        return Facts()
    text = note["text"].lower()
    plates = bool(PLATES.search(text)) and not HAS_PLATES.search(text)
    manual = bool(MANUAL.search(text)) and not NOT_MANUAL.search(text)
    text = re.sub(r"(?:the )?day after t\w+", "ylihuomenna", text)
    text = re.sub(r"\b(?:hi|hello|hey) there\b", " ", text)  # a greeting, not the delivery place
    picks: list[Time] = []  # of each sentence that says when the car can be collected, the time it says
    last_is_pick = False  # whether the last time of the sentences so far is the last of `picks`
    for sentence in SENTENCE.split(SHORT.sub(r"\1 ", RANGE.sub(" ", text))):
        tokens = TOKEN.findall(sentence)
        tags = [tag(token) for token in tokens]
        found = times(tokens, arrived_at // DAY % 7)
        about_pickup = "there" not in tags and "closed" not in tags  # not the delivery, and not when the site stops handing cars over

        def corrects(at: int) -> bool:
            """Whether the words before token `at` say that it corrects what came before: "korjaus: klo 12", "ei kun klo 12", "eikun to"."""
            words = [t for t in tokens[max(0, at - 5):at] if t != "," and tag(t) != "clock"][-3:]
            return any(tag(t) == "correction" for t in words) or any(a == "ei" and b in ("kun", "ku") for a, b in zip(words, words[1:]))

        chosen: Optional[Time] = None
        for time in found:
            before = tags[max(0, time.at - 2):time.at]
            if corrects(time.at) and (chosen is not None or time is found[0]):
                if chosen is not None:
                    chosen = Time(time.at, time.end, time.minute, time.day if time.day is not None else chosen.day)
                elif last_is_pick:
                    picks[-1] = Time(time.at, time.end, time.minute, time.day if time.day is not None else picks[-1].day)
                continue
            last_is_pick = False
            if not about_pickup or (before and before[-1] == "not") or before[-2:] == ["not", "clock"]:
                continue  # "ei klo 15": a time that the note denies
            # The nearest word that says what the time is: a limit ("ennen", "by") or a start ("aikaisintaan", "from").
            # A word before the time is nearer than one as far after it, and a comma is as far as three words.
            def far(j: int) -> float:
                low, high = (j, time.at) if j < time.at else (time.end, j + 1)
                return high - low + 3 * tokens[low:high].count(",") + (0.5 if j >= time.end else 0)
            kinds = [(far(j), tags[j], j) for j in range(len(tokens)) if tags[j] in ("from", "by") and not any(t.at <= j < t.end for t in found)]
            if not kinds:
                continue
            _, kind, j = min(kinds)
            if kind == "by" and "not" in tags[max(0, j - 4):j]:
                kind = "from"  # "ei ennen", "not ready before", "inte före", "won't be ready until"
            if kind == "from":
                chosen = time
        if chosen is not None:
            # A day alone can be corrected too: "valmis torstaina klo 14, ei kun perjantaina".
            for j, token in enumerate(tokens):
                named = weekday(token)
                if j > chosen.end and named is not None and corrects(j) and not any(t.at - 3 <= j <= t.end for t in found if t.at > chosen.at):
                    chosen = chosen._replace(day=(named - arrived_at // DAY % 7 - 2) % 7 + 2)
            picks.append(chosen)
            last_is_pick = found[-1].at <= chosen.at or corrects(found[-1].at)
    pickup_from = max(((arrived_at // DAY + (pick.day or 0)) * DAY + pick.minute for pick in picks), default=0)
    return Facts(pickup_from, plates, manual)


class Limits(NamedTuple):
    deadline: int = 0  # the minute by which the note wants the car delivered, when it says one; else 0
    pickup_hours: tuple[int, int] = (0, 0)  # the minutes of the day the pickup site opens and closes, where the note says so; 0 where it does not
    delivery_hours: tuple[int, int] = (0, 0)  # the same for the delivery site


# The words of a note's own limits. A word of five letters or more also counts with one typo.
LIMIT_WORDS = {
    "delivery": ["perillä", "perille", "perilla", "kohde", "kohteessa", "kohteen", "destination", "vastaanotto", "vastaanottava", "vastaanotetaan", "receiving", "receiver",
                 "mottagaren", "mottagning", "framme", "plats", "toimitus", "toimitukset", "toimitusosoite", "delivery", "deliver", "delivered", "leverans", "levereras",
                 "arrival", "arrive"],
    "shut": ["kiinni", "sulkee", "sulkeutuu", "suljetaan", "close", "closes", "closed", "stänger", "stängt", "nobody", "ketään", "ingen", "enää", "anymore", "längre"],
    "until": ["asti", "until", "saakka", "till"],
    "latest": ["viim", "viimeistään", "viimeistaan", "mennessä", "mennessa", "latest", "by", "senast", "later"],
    "before": ["ennen", "before", "före", "innan"],
    "collect": ["haettava", "nouto", "noudettava", "nouda", "haku", "hakea", "collect", "pickup", "pick", "hämtas", "hämta", "avhämtning"],
    "customer": ["asiakas", "kunden", "customer"],
    "fetches": ["noutaa", "hämtar", "picks", "hakee"],
}
HOURS_RANGE = re.compile(r"\b(\d{1,2})(?:[.:](\d{2}))?\s*(am|pm)?\s*[-–]\s*(\d{1,2})(?:[.:](\d{2}))?\s*(am|pm)?\b|\b(\d{1,2}):st[aä]\s+(\d{1,2}):(?:een|ään|aan)\b")
# Finnish hours in the cases a limit comes in ("ennen kahta", "kolmeen asti", "neljän jälkeen"), which `times` reads only after a word of time.
HOUR_CASES = {"yhtä": 13, "yhteen": 13, "kahta": 14, "kahteen": 14, "kahden": 14, "kolmea": 15, "kolmeen": 15, "kolmen": 15, "neljää": 16, "neljään": 16, "neljän": 16,
              "viittä": 17, "viiteen": 17, "viiden": 17, "kuutta": 18, "kuuteen": 18, "kuuden": 18}
HOUR_CASE = re.compile(r"(?<!puoli )\b(" + "|".join(HOUR_CASES) + r")\b")


def limits(note: Optional[dict], arrived_at: int) -> Limits:
    """The limits that a note sets on top of the request: a deadline for the delivery ("perillä huomenna klo 17 mennessä",
    "at destination Monday 13:30 latest", "customer picks it up tomorrow 4pm"), and the hours of a site ("open weekdays
    10:00 - 15:00", "we close at 14:30", "haettava ennen klo 16", "kohde sulkee klo 16.30", "receiving until 16:30 only").
    A clause is about the delivery site when it names it; else about the pickup site. A correction replaces the limit before it."""
    if not note:
        return Limits()
    text = re.sub(r"(?:the )?day after t\w+", "ylihuomenna", note["text"].lower())
    text = re.sub(r"\b(?:hi|hello|hey) there\b", " ", text)
    today, weekday_ = arrived_at // DAY, arrived_at // DAY % 7
    deadline, hours = 0, {"pickup": [0, 0], "delivery": [0, 0]}
    last: Optional[tuple] = None  # the last limit read, which a correction replaces: ("deadline", day) or ("closes", site)
    correcting = False  # the clause before was a correction without a time: "nej förlåt, kl 18"
    for sentence in SENTENCE.split(SHORT.sub(r"\1 ", text)):
        for clause in sentence.split(","):
            for match in HOURS_RANGE.finditer(clause):
                if match[7]:
                    opens, closes = int(match[7]) * HOUR, int(match[8]) * HOUR
                else:
                    opens, closes = int(match[1]) * HOUR + int(match[2] or 0), int(match[4]) * HOUR + int(match[5] or 0)
                    opens += 12 * HOUR if match[3] == "pm" and opens < 12 * HOUR else 0
                    closes += 12 * HOUR if match[6] == "pm" and closes < 12 * HOUR else 0
                break
            else:
                opens = closes = 0
            plain = HOUR_CASE.sub(lambda m: f"klo {HOUR_CASES[m[1]]}", re.sub(r"\b(\d{1,2}):(?:aan|ään|een)\b", r"klo \1", HOURS_RANGE.sub(" ", clause)))
            words = TOKEN.findall(plain)
            tags = [tag(word) for word in words]
            said = {name for name, known in LIMIT_WORDS.items() if any(near(word, k) for word in words for k in known)}
            site = "delivery" if "delivery" in said else "pickup"
            if 5 * HOUR <= opens < closes <= 23 * HOUR and closes - opens >= 4 * HOUR:  # opening hours, not a slot of an hour or two
                hours[site] = [opens, closes]
            found = times(words, weekday_)
            corrects = correcting or any(t == "correction" for t in tags) or any(a == "ei" and b in ("kun", "ku") for a, b in zip(words, words[1:]))
            named = next((weekday(word) for word in words if weekday(word) is not None), None)
            correcting = corrects and not found and named is None
            if corrects and not last:
                continue  # it corrects a time that is not a limit
            if corrects:
                if last[0] == "closes" and found:
                    hours[last[1]][1] = found[0].minute
                elif last[0] == "deadline":
                    day = found[0].day if found and found[0].day is not None else (named - weekday_ - 2) % 7 + 2 if named is not None and not found else last[1]
                    deadline, last = (today + day) * DAY + (found[0].minute if found else deadline % DAY), ("deadline", day)
                continue
            if any(tags[j] == "by" and "not" in tags[max(0, j - 4):j] for j in range(len(tags))):
                continue  # the first minute the car is ready, not a limit: "not ready before tomorrow 7:00", "ei ennen", "won't be ready until"
            for time in found:
                before = tags[max(0, time.at - 2):time.at]
                if (before and before[-1] == "not") or before[-2:] == ["not", "clock"]:
                    continue  # a time that the note denies
                if "shut" in said or "until" in said or (site == "pickup" and time.day is None and "collect" in said and ("before" in said or "latest" in said)):
                    hours[site][1], last = time.minute, ("closes", site)
                elif (site == "delivery" and "latest" in said) or ("customer" in said and "fetches" in said):
                    deadline, last = (today + (time.day or 0)) * DAY + time.minute, ("deadline", time.day or 0)
                else:
                    last = None  # another time, such as when the car is ready: a correction after it is not about a limit
    return Limits(deadline, tuple(hours["pickup"]), tuple(hours["delivery"]))
