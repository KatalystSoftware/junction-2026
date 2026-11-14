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
                             agrees with 6 May 1808; 3 May does not

compatible() is None when a figure cannot be read (a number in words, two units), and the model's
own verdict then stands. Finnish, Swedish and English.
"""
import re

MONTHS = [("tammikuu", "januar"), ("helmikuu", "februar"), ("maaliskuu", "mars", "march"),
          ("huhtikuu", "april"), ("toukokuu", "maj", "may"), ("kesäkuu", "juni", "june"),
          ("heinäkuu", "juli", "july"), ("elokuu", "august"), ("syyskuu", "september"),
          ("lokakuu", "oktober", "october"), ("marraskuu", "november"), ("joulukuu", "december")]
_MONTH = {name: n for n, names in enumerate(MONTHS, 1) for name in names}
_MONTH_AT = re.compile(r"\b(" + "|".join(sorted(_MONTH, key=len, reverse=True)) + r")", re.I)

ABOUT = ("about", "around", "approximately", "roughly", "circa", "some", "noin", "suunnilleen", "arviolta",
         "omkring", "cirka", "ungefär", "runt", "ca", "c", "n")   # "n. 3 000", "c. 400", "ca 17 000"
OVER = ("over", "more than", "at least", "above", "upwards of", "yli", "vähintään", "runsaat", "runsas", "runsaan",
        "över", "minst", "mer än", "drygt")
ALMOST = ("almost", "nearly", "under", "less than", "up to", "at most", "close to", "lähes", "melkein", "alle",
          "enintään", "jopa", "vajaat", "vajaa", "nästan", "knappt", "högst", "upp till", "närmare")
_NUMBER = re.compile(r"\d{1,3}(?:[ \u00a0\u202f.,]\d{3})+(?!\d)|\d+")
_UNIT = re.compile(r"%|\bprosent|\bprocent|\bper ?cent|\bmilj|\bmillion|\bmrd|\bbillion|\btuhat|\btusen|\bthousand", re.I)


def _hedge(text):
    """about, over, almost or exact, from the words before the number."""
    low = text.lower()
    for name, words in (("about", ABOUT), ("over", OVER), ("almost", ALMOST)):
        if any(re.search(rf"(?<!\w){re.escape(w)}\.?\s+(?:\w+\s+)?(?=\d)" if len(w) > 2
                         else rf"(?<!\w){re.escape(w)}\.?\s*(?=\d)", low) for w in words):
            return name
    return "exact"


def read(text):
    """A figure as written: ("date", {"day": {..}, "month": n, "year": n}), ("count", (low, high),
    hedge, unit) or None when it cannot be read."""
    text = (text or "").strip()
    if not text:
        return None
    month = _MONTH_AT.search(text)
    numbers = [(m.start(), int(re.sub(r"\D", "", m[0])), m[0]) for m in _NUMBER.finditer(text)]
    years = [n for _, n, raw in numbers if 1000 <= n <= 2100 and raw.isdigit()]
    if month:
        days = {n for at, n, raw in numbers if 1 <= n <= 31 and len(raw) <= 2}
        return ("date", {"day": days, "month": _MONTH[month[1].lower()], "year": years[0] if years else None})
    if not numbers:
        return None
    if len(numbers) == 1 and years and not _UNIT.search(text) and _hedge(text) == "exact" and len(text) <= 12:
        return ("date", {"day": set(), "month": None, "year": years[0]})   # a bare year
    unit = _UNIT.search(text)
    if unit and unit[0] != "%" and not unit[0].lower().startswith(("pros", "proc", "per")):
        return None   # "1,5 miljoonaa", "two thousand": not read
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
        for part in ("year", "month"):
            if p[part] and q[part] and p[part] != q[part]:
                return False
        if p["day"] and q["day"] and (not p["month"] or not q["month"]):
            return None   # a day without its month says nothing
        return not (p["day"] and q["day"] and not p["day"] & q["day"])
    if x[3] != y[3]:
        return None
    (xl, xh), (yl, yh) = x[1], y[1]
    if xl != xh or yl != yh:   # a range agrees with what overlaps it
        return max(xl, yl) <= min(xh, yh) if xl != xh and yl != yh else (_covers(x, yl) if xl != xh else _covers(y, xl))
    if x[2] == "exact" and y[2] == "exact":
        return xl == yl
    return _covers(x, yl) or _covers(y, xl) if x[2] != "exact" and y[2] != "exact" else (
        _covers(x, yl) if x[2] != "exact" else _covers(y, xl))
