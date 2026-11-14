"""Scratch: three smaller checks for the input audit.

    SPREAD_DATA=... python scratch/inputs/extras.py [variant]

1. The bulk order (a batchId shared by 20 requests or more) against the late chance.
2. Before the day's first request: do the cars that waited overnight and the night's drops say how the day will book?
3. The desk's own history at a pickup town this week (bookings and lookers at its earlier cars from there) as a live
   measure of the town's drivers, on top of the late chance.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

from lib import load, logit

variant = sys.argv[1] if len(sys.argv) > 1 else "steep-notes-offers-8"
weeks = load(variant)
rows, days = [], []
for w in weeks:
    seed = w["week"]["seed"]
    orders = sorted((o for o in w["orders"] if not o["cancelled"] and o["post"] is not None and o["kind"] == ""), key=lambda o: o["won_at"])
    hist: dict[str, list[tuple[int, bool, int]]] = {}
    for o in orders:
        t = o["won_at"]
        fast = o["book"] is not None and o["book"] - o["post"] <= 30
        before = [(f, l) for p, f, l in hist.get(o["pk"], []) if p + 30 <= t]
        rows.append({"seed": seed, "late": o["late"], "p": o["p_slow"], "bulk": o["batch_n"] >= 20, "batch": o["batch_n"], "day": t // 1440, "tod": t % 1440, "fast": fast,
                     "notified": o["notified"], "pk_n": len(before), "pk_fast": np.mean([f for f, _ in before]) if before else np.nan, "pk_look": np.mean([l for _, l in before]) if before else np.nan,
                     "lookers": o["looks15"][1], "hours": (o["last"] - t) / 60, "warned": o["warn"] is not None, "offers": o["offers"], "yes": o["offers_yes"],
                     "wait": None if o["book"] is None else o["book"] - o["post"], "unbooked15": o["book"] is None or o["book"] - o["post"] > 15})
        hist.setdefault(o["pk"], []).append((o["post"], fast, o["looks15"][1]))
    for d in range(1, 5):
        start = d * 1440
        waiting = [o for o in orders if o["post"] < start + 240 and (o["book"] is None or o["book"] > start + 240) and o["last"] > start + 480]
        took = sum(1 for o in waiting if o["book"] is not None and o["book"] <= start + 480)
        night = next((x for x in w["days"] if x["day"] == d), {"drops": []})
        days.append({"seed": seed, "day": d, "waiting": len(waiting), "took": took, "night_drops": sum(1 for m in night["drops"] if m < 480)})
df, dd = pd.DataFrame(rows), pd.DataFrame(days)
n = df.seed.nunique()

print(f"{variant}: {n} weeks\n\n1. THE BULK ORDER")
t = df.groupby("bulk").agg(a_week=("late", lambda s: len(s) / n), fitted=("p", "mean"), late=("late", "mean"), booked_in_30=("fast", "mean"))
print(t.round(3).to_string())
print(f"requests with a batchId shared by 2 to 19: {np.mean((df.batch >= 2) & (df.batch < 20)):.0%} of won orders")

print("\n2. BEFORE 08:00")
cells = df.assign(nb=pd.cut(df.notified, [-1, 0, 4, 9, 19, 39, 69, 99, 149, 10000]).astype(str), hb=pd.cut(df.tod, [0, 600, 720, 840, 960, 1440]).astype(str))
cells["exp"] = cells.groupby(["nb", "day", "hb"]).fast.transform("mean")
speed = cells.groupby(["seed", "day"]).agg(orders=("fast", "size"), fast=("fast", "sum"), exp=("exp", "sum"), late=("late", "mean"), p=("p", "mean")).reset_index()
speed["s"] = speed.fast / speed.exp
j = dd.merge(speed[speed.orders >= 15], on=["seed", "day"])
j["share"] = j.took / j.waiting.clip(lower=1)
ok = j[j.waiting >= 4]
print(f"days with 4 or more cars waiting at 04:00: {len(ok) / n:.1f} a week, {ok.waiting.mean():.1f} cars, {ok.share.mean():.0%} booked by 08:00")
print(f"correlation of that share with the day's booking speed {np.corrcoef(ok.share, ok.s)[0, 1]:+.2f}, with the day's late share less its fitted share {np.corrcoef(ok.share, ok.late - ok.p)[0, 1]:+.2f}")
print(f"correlation of the drops before 08:00 with the day's booking speed {np.corrcoef(j.night_drops, j.s)[0, 1]:+.2f} ({j.night_drops.mean():.2f} drops a night)")
print(ok.groupby(pd.cut(ok.share, [-0.01, 0.1, 0.3, 0.5, 0.7, 1.0])).agg(days=("s", "size"), speed=("s", "mean"), slow_day=("s", lambda s: np.mean(s < 0.7)), late=("late", "mean"), fitted=("p", "mean")).round(3).to_string())

print("\n3. THE DESK'S OWN HISTORY AT THE PICKUP TOWN THIS WEEK")
has = df[df.pk_n >= 3]
print(f"orders with 3 or more earlier cars from the same town: {len(has) / len(df):.0%}")
print(has.groupby(pd.cut(has.pk_fast, [-0.01, 0.3, 0.5, 0.7, 0.85, 1.0])).agg(a_week=("late", lambda s: len(s) / n), notified=("notified", "median"), fitted=("p", "mean"), late=("late", "mean")).round(3).to_string())
y, z = df.late.values.astype(int), logit(df.p)
feature = np.where(df.pk_n >= 3, df.pk_fast.fillna(0) - has.pk_fast.mean(), 0.0)
look = np.where(df.pk_n >= 3, np.log1p(df.pk_look.fillna(0)) - np.log1p(has.pk_look).mean(), 0.0)


def cv(x: np.ndarray) -> float:
    p = np.zeros(len(df))
    for train, test in GroupKFold(5).split(x, y, df.seed.values):
        p[test] = LogisticRegression(C=10, max_iter=2000).fit(x[train], y[train]).predict_proba(x[test])[:, 1]
    return roc_auc_score(y, p)


base = cv(np.c_[z])
print(f"AUC on seeds left out: the late chance {base:.4f}; with the town's share booked in 30 minutes {cv(np.c_[z, feature, df.pk_n >= 3]):.4f}; "
      f"with its lookers {cv(np.c_[z, look, df.pk_n >= 3]):.4f}; with drivers notified, log {cv(np.c_[z, np.log1p(df.notified)]):.4f}; with both {cv(np.c_[z, feature, df.pk_n >= 3, np.log1p(df.notified)]):.4f}")

print("\n4. CARS THAT FEW DRIVERS LOOK AT: not booked 15 minutes after the post, under 12 hours to lastPickupAt, 2 lookers or fewer")
g = df[df.unbooked15 & (df.hours < 12) & (df.lookers <= 2)]
print(f"{len(g) / n:.1f} a week, {g.late.mean():.0%} late ({g.late.sum() / n:.1f} late a week), fitted {g.p.mean():.0%}; hours left at the win {g.hours.median():.1f} (median); "
      f"deadline warning {g.warned.mean():.0%}; got offers {np.mean(g.offers > 0):.0%}, {g.offers.mean():.0f} offers each, accepted one {np.mean(g.yes > 0):.0%}; "
      f"late with an accepted offer {g[g.yes > 0].late.mean():.0%}, without {g[g.yes == 0].late.mean():.0%}; median wait of those booked {g.wait.median():.0f} minutes")
