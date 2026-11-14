"""Scratch: loads the rows that rows.py wrote, as pandas frames, with the features the audit tests."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd

DAY, HOUR = 1440, 60
DATA = Path(os.environ.get("SPREAD_DATA", "data")) / "inputs"


def load(variant: str = "steep-notes-offers-8") -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted((DATA / variant).glob("*.json"))]


def open_from(minute: int, hours: dict | None) -> int:
    """The first minute at or after `minute` when a site with these stated hours is open."""
    if hours is None:
        return minute
    for day in range(minute // DAY, minute // DAY + 9):
        weekday = day % 7
        if weekday in hours["weekdays"]:
            opens, closes = hours["opens"], hours["closes"]
        elif weekday == 5 and hours.get("saturday"):
            opens, closes = hours["saturday"]["opens"], hours["saturday"]["closes"]
        else:
            continue
        start = max(minute, day * DAY + opens)
        if start < day * DAY + closes:
            return start
    return minute


def orders(weeks: list[dict]) -> pd.DataFrame:
    rows = []
    for w in weeks:
        seed, forecasts = w["week"]["seed"], w["week"]["forecasts"]
        os_ = sorted(w["orders"], key=lambda o: o["won_at"])
        posted = [(o["post"], o["book"], o["looks15"][1], o["pk"]) for o in os_ if o["post"] is not None]
        for o in os_:
            t = o["won_at"]
            naive_last = o["deadline"] - o["drive"]
            ready = open_from(max(t, o["wf"]), o["ph"])
            earlier = [(p, b, l, pk) for p, b, l, pk in posted if p // DAY == t // DAY and p + 30 <= t]
            before = [(p, b, l, pk) for p, b, l, pk in posted if p + 30 <= t]
            backlog = sum(1 for p, b, l, pk in posted if p < t and (b is None or b > t))
            snow = any((o["pk"] in f["places"] or o["dl"] in f["places"]) and f["at"] <= t and f["from"] < o["deadline"] and f["to"] > t for f in forecasts)
            rows.append({
                **{k: o[k] for k in ("id", "dealer", "batch", "kind", "prem", "elec", "pk", "dl", "opt", "price", "list", "fee", "note", "lang", "drive", "notified",
                                     "exp_near", "dl_town", "dl_near", "pk_town", "roster", "p_slow", "late", "cancelled", "changed", "drops", "driver_late", "no_show",
                                     "failed", "expired", "offers", "offers_read", "offers_yes", "views", "nbook", "fast", "nopt")},
                "seed": seed, "t": t, "day": t // DAY, "hour": (o["at"] % DAY) / HOUR, "low_charge": bool(o["elec"] and o["charge"] is not None and o["charge"] < 30),
                "naive_hours": (naive_last - t) / HOUR, "true_hours": (o["last"] - t) / HOUR, "hours_lost": max(0, naive_last - o["last"]) / HOUR,
                "ready_in": max(0, ready - t) / HOUR, "window": (o["last"] - ready) / HOUR, "last_dow": o["last"] // DAY % 7, "last_tod": o["last"] % DAY / HOUR,
                "post_delay": None if o["post"] is None else o["post"] - t, "book_delay": None if o["book"] is None or o["post"] is None else o["book"] - o["post"],
                "lookers15": o["looks15"][1], "views15": o["looks15"][0], "lookers60": o["looks60"][1], "warned": o["warn"] is not None,
                "today_n": len(earlier), "today_fast": np.mean([b is not None and b - p <= 30 for p, b, l, pk in earlier]) if earlier else np.nan,
                "today_look": np.mean([l for p, b, l, pk in earlier]) if earlier else np.nan,
                "week_n": len(before), "week_fast": np.mean([b is not None and b - p <= 30 for p, b, l, pk in before]) if before else np.nan,
                "backlog": backlog, "snow": snow,
                "d_rating": (o["first_driver"] or {}).get("rating"), "d_gigs": (o["first_driver"] or {}).get("gigs"), "d_drops": (o["first_driver"] or {}).get("drops"),
                "d_home_dl": (o["first_driver"] or {}).get("home") == o["dl"], "d_home_pk": (o["first_driver"] or {}).get("home") == o["pk"],
                "book_fee": None if o["book_fee"] is None else o["book_fee"] / o["fee"],
            })
    return pd.DataFrame(rows)


def logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def fmt(x: float, digits: int = 1) -> str:
    return f"{x:.{digits}f}"


def se_prop(p: float, n: int) -> float:
    return math.sqrt(max(p * (1 - p), 1e-9) / max(n, 1))
