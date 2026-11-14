"""Scratch: do the bookings that drivers give back before 08:00 (gig_dropped) mark a day short of drivers, such as a
flu day, before the day's first request?

    SPREAD_DATA=... python scratch/inputs/morning_drops.py [variant]

Tuesday to Friday, by the count of drops before 08:00: the day's booking speed (the share of its cars booked within 30
minutes, over that weekday's usual share), and the late share of the orders won that day beside the fitted chance
(slow.py). Then the same on the days without a snow forecast.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from lib import load

variant = sys.argv[1] if len(sys.argv) > 1 else "steep-notes-offers-8"
rows, days = [], []
for w in load(variant):
    seed, forecasts = w["week"]["seed"], w["week"]["forecasts"]
    for o in w["orders"]:
        if o["kind"] or o["cancelled"] or o["post"] is None:
            continue
        rows.append({"seed": seed, "day": o["won_at"] // 1440, "late": o["late"], "p": o["p_slow"], "fast": o["book"] is not None and o["book"] - o["post"] <= 30})
    for d in w["days"]:
        if 1 <= d["day"] <= 4:
            snow = any(f["from"] < (d["day"] + 1) * 1440 and f["to"] > d["day"] * 1440 for f in forecasts)
            days.append({"seed": seed, "day": d["day"], "drops": sum(1 for minute in d["drops"] if minute < 480), "snow": snow})
df, dd = pd.DataFrame(rows), pd.DataFrame(days)
n = df.seed.nunique()
df["usual"] = df.groupby("day").fast.transform("mean")
day = df.groupby(["seed", "day"]).agg(orders=("late", "size"), lates=("late", "sum"), fitted=("p", "sum"), fast=("fast", "sum"), usual=("usual", "sum")).reset_index()
j = dd.merge(day, on=["seed", "day"])
j["speed"] = j.fast / j.usual


def table(d: pd.DataFrame, bands: list[int]) -> pd.DataFrame:
    t = d.groupby(pd.cut(d.drops, bands), observed=True).agg(days_a_week=("speed", lambda s: len(s) / n), speed=("speed", "mean"), slow_day=("speed", lambda s: np.mean(s < 0.7)),
                                                              snow=("snow", "mean"), orders=("orders", "sum"), lates=("lates", "sum"), fitted=("fitted", "sum"))
    t["late"], t["fit"], t["extra_late_a_week"] = t.lates / t.orders, t.fitted / t.orders, (t.lates - t.fitted) / n
    return t[["days_a_week", "speed", "slow_day", "snow", "late", "fit", "extra_late_a_week"]].round(3)


print(f"{variant}: {n} weeks, {len(j)} days from Tuesday to Friday, {j.drops.mean():.2f} drops before 08:00 a day\n")
print(table(j, [-1, 0, 1, 2, 4, 6, 9, 100]).to_string())
print("\n7 or more against fewer:")
print(table(j, [-1, 6, 100]).to_string())
slow = j.speed < 0.7
print(f"\ndays with a booking speed under 0.7: {slow.sum()}; of them after 7 or more drops: {(slow & (j.drops >= 7)).sum()}; days with 7 or more drops: {(j.drops >= 7).sum()}")
print("\ndays without a snow forecast:")
print(table(j[~j.snow], [-1, 2, 4, 6, 100]).to_string())
