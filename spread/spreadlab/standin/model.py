"""What the stand-in's drivers do with an open gig: the features of one stretch of its time on the board, shared by the
fit (fit.py) and the world (world.py), so the world draws from exactly what was fitted.

An open gig is cut into slices at fixed ages, at each full hour and at each fee step. Inside a slice the chance a minute
that some driver books the gig is exp(weights . features). The features are what a desk controls (the fee now against
the typical fee, how far the schedule still rises, when it posted) and what the car is (the hours left to collect it,
the day it is ready, the drivers who live near either end, the drive, who may drive it).
"""
from __future__ import annotations

import math

DAY, HOUR = 1440, 60
AGES = [0, 2, 5, 15, 60, 180, 720]            # minutes since the gig opened (or opened again after a drop)
HOURS = [0, 6, 9, 12, 16, 19, 23]             # the hour of the day; 23 to 6 is the night
LEFT = [-10**9, 0, 180, 480, 1440, 2880]      # minutes to the last pickup that is on time
NAMES = ([f"age {a}+" for a in AGES[1:]] + [f"hour {h}+" for h in HOURS[1:]] + [f"left {x}+" for x in LEFT[1:]]
         + ["ln fee", "ln fee, first 15 min", "ln fee squared", "rise left", "ready tomorrow", "ready later", "ln notified", "ln at delivery", "ln drivers/800",
            "ln drive/120", "experienced only", "manual only", "two cars", "private", "after a drop", "posted again", "ln order age h", "ln crowd",
            "saturday", "sunday", "last monday on", "wave day", "cannot be on time"])


def bucket(edges: list[int], value: float) -> int:
    k = 0
    for i, edge in enumerate(edges):
        if value >= edge:
            k = i
    return k


def static(gig: dict) -> dict:
    """The part of a gig's features that does not change while it is open. `gig` has: notified, at_delivery, drivers, drive,
    experienced, manual, cars, private."""
    return {"ln notified": math.log(1 + gig["notified"]), "ln at delivery": math.log(1 + gig["at_delivery"]), "ln drivers/800": math.log(gig["drivers"] / 800),
            "ln drive/120": math.log(max(gig["drive"], 10) / 120), "experienced only": float(gig["experienced"]), "manual only": float(gig["manual"]),
            "two cars": float(gig["cars"] > 1), "private": float(gig["private"])}


def features(st: dict, now: int, opened: int, first_posted: int, fee: float, top: float, ref: float, last_pickup: int, ready: int, reopened: bool,
             reposted: bool, crowd: int, wave: bool, feasible: bool = True) -> list[float]:
    """The features of the slice that starts at `now`, in the order of NAMES. `fee` is the fee in the app, `top` the highest fee
    of the schedule, `ref` the typical fee of the gig's cars; `ready` the first minute the first car can be collected."""
    x = [0.0] * len(NAMES)
    a, h, l = bucket(AGES, now - opened), bucket(HOURS, now % DAY // HOUR), bucket(LEFT, last_pickup - now)
    if now % DAY // HOUR >= 23:
        h = 0
    if a:
        x[a - 1] = 1.0
    if h:
        x[len(AGES) - 1 + h - 1] = 1.0
    if l:
        x[len(AGES) + len(HOURS) - 2 + l - 1] = 1.0
    i = len(AGES) + len(HOURS) + len(LEFT) - 3
    ln_fee = math.log(max(fee, 1) / ref)
    day, ready_day = now // DAY, max(ready, now) // DAY
    x[i:] = [ln_fee, ln_fee if now - opened < 15 else 0.0, ln_fee * ln_fee, max(0.0, math.log(max(top, fee, 1) / max(fee, 1))), float(ready_day == day + 1), float(ready_day > day + 1),
             st["ln notified"], st["ln at delivery"], st["ln drivers/800"], st["ln drive/120"], st["experienced only"], st["manual only"], st["two cars"], st["private"],
             float(reopened), float(reposted), math.log(1 + max(0, now - first_posted) / HOUR), math.log(1 + crowd),
             float(day % 7 == 5), float(day % 7 == 6), float(day >= 7), float(wave), float(not feasible)]
    return x


def edges(now: int, opened: int, until: int, steps: list[int]) -> list[int]:
    """The minutes at which the slices of a gig that is open from `now` to `until` start: `now`, then each age edge, full hour
    and fee step before `until`."""
    cuts = {now}
    cuts.update(opened + a for a in AGES if now < opened + a < until)
    cuts.update(s for s in steps if now < s < until)
    cuts.update(range((now // HOUR + 1) * HOUR, until, HOUR))
    return sorted(cuts)


def fee_at(schedule: list[dict], minute: int) -> int:
    """The fee in the app: the latest step that has started, or the first step before any has."""
    fee = schedule[0]["feeCents"]
    for step in schedule:
        if step["at"] <= minute:
            fee = step["feeCents"]
    return fee
