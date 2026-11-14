"""Whether two figures, as two editions write them, can both be true.

The judge model (claims.py) finds the sentence about the same thing and copies each side's figure
as written: "omkring 12 000", "12,600", "noin 8000", "over 3,000", "21 November 1932",
"toukokuun alussa". Whether those two agree is arithmetic, and a small model gets it wrong one
time in three, so it is decided here:

    exact against exact      equal, or they differ
    about N against M        agree when M rounds to N at N's precision: about 12,000 agrees with
                             11,800 and not with 12,600; about 50 does not agree with 102
    over N against M         agree when M is N or more and below the next step of N's precision:
                             over 3,000 agrees with 3,600 and not with 4,100
    almost N against M       agree when M is below N by less than half a step: almost 7,000
                             agrees with 6,800 and not with 6,000
    date against date        agree when every part both give (day, month, year) is equal: May 1808
                             agrees with 6 May 1808; 3 May does not. Of a period or a date in
                             two calendars, each month's days are compared with the other's

compatible() is None when a figure cannot be read (a number in words, two units), and the model's
own verdict then stands. Finnish, Swedish and English.
"""

import re

MONTHS = [
    ("tammikuu", "januar"),
    ("helmikuu", "februar"),
    ("maaliskuu", "mars", "march"),
    ("huhtikuu", "april"),
    ("toukokuu", "maj", "may"),
    ("kesäkuu", "juni", "june"),
    ("heinäkuu", "juli", "july"),
    ("elokuu", "august"),
    ("syyskuu", "september"),
    ("lokakuu", "oktober", "october"),
    ("marraskuu", "november"),
    ("joulukuu", "december"),
]
_MONTH = {name: n for n, names in enumerate(MONTHS, 1) for name in names}
_MONTH_AT = re.compile(r"\b(" + "|".join(sorted(_MONTH, key=len, reverse=True)) + r")", re.IGNORECASE)

ABOUT = (
    "about",
    "around",
    "approximately",
    "roughly",
    "circa",
    "some",
    "noin",
    "suunnilleen",
    "arviolta",
    "omkring",
    "cirka",
    "ungefär",
    "runt",
    "ca",
    "c",
    "n",
)  # "n. 3 000", "c. 400", "ca 17 000"
OVER = (
    "over",
    "more than",
    "at least",
    "above",
    "upwards of",
    "yli",
    "vähintään",
    "runsaat",
    "runsas",
    "runsaan",
    "över",
    "minst",
    "mer än",
    "drygt",
)
ALMOST = (
    "almost",
    "nearly",
    "under",
    "less than",
    "up to",
    "at most",
    "close to",
    "lähes",
    "melkein",
    "alle",
    "enintään",
    "jopa",
    "vajaat",
    "vajaa",
    "nästan",
    "knappt",
    "högst",
    "upp till",
    "närmare",
)
_NUMBER = re.compile(r"\d{1,3}(?:[ \u00a0\u202f.,]\d{3})+(?!\d)|\d+")
_UNIT = re.compile(
    r"%|\bprosent|\bprocent|\bper ?cent|\bmilj|\bmillion|\bmrd|\bbillion|\btuhat|\btusen|\bthousand", re.IGNORECASE
)


def _hedge(text):
    """about, over, almost or exact, from the words before the number."""
    low = text.lower()
    for name, words in (("about", ABOUT), ("over", OVER), ("almost", ALMOST)):
        if any(
            re.search(
                rf"(?<!\w){re.escape(w)}\.?\s+(?:\w+\s+)?(?=\d)"
                if len(w) > 2
                else rf"(?<!\w){re.escape(w)}\.?\s*(?=\d)",
                low,
            )
            for w in words
        ):
            return name
    return "exact"


def read(text):
    """A figure as written: ("date", {"days": {month: {day, ..}}, "year": n}), ("count", (low, high),
    hedge, unit) or None when it cannot be read.

    A date may name several days: two calendars for one day ("22. maaliskuuta (J: 10. maaliskuuta)")
    or the two ends of a period ("between 25 March and 19 July"). Each day goes to its month: the
    month written after it, or before it where the text opens with the month ("March 25").
    """
    text = (text or "").strip()
    if not text:
        return None
    numbers = [(m.start(), int(re.sub(r"\D", "", m[0])), m[0]) for m in _NUMBER.finditer(text)]
    years = [n for _, n, raw in numbers if 1000 <= n <= 2100 and raw.isdigit()]
    months = [(m.start(), _MONTH[m[1].lower()]) for m in _MONTH_AT.finditer(text)]
    if months:
        tokens = sorted(months + [(at, -n) for at, n, raw in numbers if 1 <= n <= 31 and len(raw) <= 2])
        month_first = tokens[0][1] > 0
        days, waiting, last = {m: set() for _, m in months}, [], None
        for _, token in tokens:
            if token > 0:
                last = token
                if not month_first:
                    days[token].update(waiting)
                    waiting = []
            elif month_first:
                days[last].add(-token)
            else:
                waiting.append(-token)
        if waiting and last:  # "the 14th" after its month was named
            days[last].update(waiting)
        return ("date", {"days": days, "year": years[0] if years else None})
    if not numbers:
        return None
    if len(numbers) == 1 and years and not _UNIT.search(text) and _hedge(text) == "exact" and len(text) <= 12:
        return ("date", {"days": {}, "year": years[0]})  # a bare year
    unit = _UNIT.search(text)
    if unit and unit[0] != "%" and not unit[0].lower().startswith(("pros", "proc", "per")):
        return None  # "1,5 miljoonaa", "two thousand": not read
    values = [n for _, n, _ in numbers]
    if len(values) > 2:
        return None
    return ("count", (min(values), max(values)), _hedge(text), "%" if unit else "")


def _step(n):
    """The precision a round number is given at: 12000 -> 1000, 8000 -> 1000, 50 -> 10, 102 -> 1."""
    step = 1
    while n and n % (step * 10) == 0:
        step *= 10
    return step


def _covers(figure, value):
    """Whether a hedged or exact count agrees with an exact value."""
    (low, high), hedge = figure[1], figure[2]
    if low != high:
        return low <= value <= high
    step = _step(low)
    if hedge == "about":
        return abs(value - low) * 2 <= step if step > 1 else value == low
    if hedge == "over":
        return low <= value < low + max(step, 1) if step > 1 else value >= low
    if hedge == "almost":
        return low - step / 2 < value <= low if step > 1 else value <= low
    return value == low


def compatible(a, b):
    """True when the two figures as written can both hold, False when they differ, None when
    either cannot be read or they are of two kinds."""
    x, y = read(a), read(b)
    if not x or not y or x[0] != y[0]:
        return None
    if x[0] == "date":
        p, q = x[1], y[1]
        if p["year"] and q["year"] and p["year"] != q["year"]:
            return False
        shared = set(p["days"]) & set(q["days"])
        if p["days"] and q["days"] and not shared:
            return False  # no month in common
        # In every month both name, the days must meet: a day of one calendar, or one end of a period.
        return all(not (p["days"][m] and q["days"][m]) or bool(p["days"][m] & q["days"][m]) for m in shared)
    if x[3] != y[3]:
        return None
    (xl, xh), (yl, yh) = x[1], y[1]
    if xl != xh or yl != yh:  # a range agrees with what overlaps it
        return max(xl, yl) <= min(xh, yh) if xl != xh and yl != yh else (_covers(x, yl) if xl != xh else _covers(y, xl))
    if x[2] == "exact" and y[2] == "exact":
        return xl == yl
    return (
        _covers(x, yl) or _covers(y, xl)
        if x[2] != "exact" and y[2] != "exact"
        else (_covers(x, yl) if x[2] != "exact" else _covers(y, xl))
    )
