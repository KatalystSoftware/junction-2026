"""Scratch: do inputs that the late chance (slow.py, "friday") leaves out predict a late order?

    SPREAD_DATA=... python scratch/inputs/late_inputs.py [variant]

One-car orders between dealer sites of the saved weeks. Prints, for each candidate input, the late share by group at
equal fitted chance, and what each adds to a logistic fit on top of the fitted chance, tested on seeds left out.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold

from lib import load, logit, orders

variant = sys.argv[1] if len(sys.argv) > 1 else "steep-notes-offers-8"
df = orders(load(variant))
df = df[(df.kind == "") & ~df.cancelled].copy()
weeks = df.seed.nunique()
print(f"{variant}: {len(df)} one-car dealer orders in {weeks} weeks, {df.late.mean():.3%} late, {df.late.sum() / weeks:.1f} late a week")
df["z"] = logit(df.p_slow)
df["bin"] = pd.cut(df.p_slow, [0, .02, .03, .05, .08, .12, .2, 1])
print("\nCalibration of slow.py 'friday':")
print(df.groupby("bin", observed=True).agg(n=("late", "size"), fitted=("p_slow", "mean"), late=("late", "mean")).round(4))


def table(name: str, groups: pd.Series, min_n: int = 150) -> None:
    """Late share by group, beside the share the fitted chance expects for the same orders."""
    t = df.groupby(groups, observed=True).agg(n=("late", "size"), a_week=("late", lambda s: len(s) / weeks), fitted=("p_slow", "mean"), late=("late", "mean"))
    t = t[t.n >= min_n]
    t["ratio"] = t.late / t.fitted
    t["extra_late_a_week"] = (t.late - t.fitted) * t.a_week
    t["z"] = (t.late - t.fitted) / np.sqrt(t.fitted * (1 - t.fitted) / t.n)
    print(f"\n{name}")
    print(t.round(3).to_string())


table("Hours lost to the pickup site's stated hours (deadline - drive against lastPickupAt)", pd.cut(df.hours_lost, [-1, 0.01, 1, 2, 3, 5, 100]))
table("True hours from the win to lastPickupAt", pd.cut(df.true_hours, [-100, 2, 4, 6, 8, 12, 24, 48, 1000]))
table("Naive hours under 8, by hours lost", (df.naive_hours < 8).astype(str) + " naive<8, lost " + pd.cut(df.hours_lost, [-1, 0.01, 2, 100]).astype(str))
table("Hours until the car can first be collected (ready time and opening hours)", pd.cut(df.ready_in, [-1, 0.01, 2, 6, 14, 24, 1000]))
table("Hours in which the car can be collected (ready to lastPickupAt)", pd.cut(df.window, [-1000, 0, 2, 4, 6, 8, 12, 24, 1000]))
table("lastPickupAt weekday", df.last_dow)
table("lastPickupAt hour of day", pd.cut(df.last_tod, [0, 9, 11, 13, 15, 17, 24]))
table("Request's hour of arrival", pd.cut(df.hour, [0, 9, 10, 11, 12, 13, 14, 15, 16, 24]))
table("Weekday won", df.day % 7)
table("Premium by experienced drivers within 30 km", df.prem.astype(str) + " prem, exp " + pd.cut(df.exp_near, [-1, 0, 2, 5, 10, 1000]).astype(str))
table("Drivers living within 30 km of the delivery", pd.cut(df.dl_near, [-1, 0, 4, 9, 39, 99, 10000]))
table("Drivers living in the pickup town itself", pd.cut(df.pk_town, [-1, 0, 4, 9, 39, 99, 10000]))
table("Electric / low charge", df.elec.astype(str) + " elec, low " + df.low_charge.astype(str))
table("Bulk order (batchId)", df.batch)
table("Note language", df.lang.fillna("none"))
table("Snow forecast known at the win", df.snow)
table("Options quoted", df.nopt.astype(str) + " " + df.fast)
table("Option the dealer took", df.opt)
table("Won cars without a driver at the win", pd.cut(df.backlog, [-1, 0, 2, 4, 7, 10, 14, 100]))
table("Share of today's earlier orders booked within 30 minutes (5 or more)", pd.cut(df.today_fast.where(df.today_n >= 5), [-0.01, 0.4, 0.6, 0.75, 0.9, 1.0]))
table("Mean lookers in 15 minutes at today's earlier orders (5 or more)", pd.cut(df.today_look.where(df.today_n >= 5), [-0.01, 2, 4, 6, 9, 100]))
table("Price over list", pd.cut(df.price / df.list, [0, 1.3, 1.5, 1.7, 1.9, 5]))
table("Dealer's size (orders of the dealer in the week)", pd.cut(df.groupby(["seed", "dealer"]).id.transform("size"), [0, 5, 15, 30, 60, 1000]))

# What each input adds on top of the fitted chance, on seeds left out.
df["today_fast_f"] = df.today_fast.where(df.today_n >= 5).fillna(df.today_fast.where(df.today_n >= 5).mean())
df["today_look_f"] = np.log1p(df.today_look.where(df.today_n >= 5)).fillna(np.log1p(df.today_look.where(df.today_n >= 5)).mean())
FEATURES = {
    "site hours: hours lost, capped at 6": lambda d: np.c_[np.minimum(d.hours_lost, 6)],
    "true hours bands (lastPickupAt)": lambda d: np.c_[(d.true_hours < 4), (d.true_hours < 6), (d.true_hours < 8), (d.true_hours < 12), (d.true_hours < 24)].astype(float),
    "collectable window bands": lambda d: np.c_[(d.window < 2), (d.window < 4), (d.window < 8), (d.window < 24)].astype(float),
    "ready later": lambda d: np.c_[(d.ready_in > 0.01), np.minimum(d.ready_in, 48) / 24].astype(float),
    "lastPickupAt on Saturday or Monday": lambda d: np.c_[(d.last_dow == 5), (d.last_dow == 0)].astype(float),
    "premium x experienced nearby": lambda d: np.c_[d.prem * np.log1p(d.exp_near), d.prem * (d.exp_near < 3)].astype(float),
    "drivers at the delivery": lambda d: np.c_[np.log1p(d.dl_near)],
    "drivers notified, log": lambda d: np.c_[np.log1p(d.notified)],
    "electric, low charge": lambda d: np.c_[d.elec, d.low_charge].astype(float),
    "hour of arrival": lambda d: np.c_[(d.hour < 10), (d.hour >= 13), (d.hour >= 15)].astype(float),
    "weekday won": lambda d: np.c_[[(d.day % 7 == k) for k in range(1, 5)]].T.astype(float),
    "bulk order": lambda d: np.c_[d.batch].astype(float),
    "snow forecast": lambda d: np.c_[d.snow].astype(float),
    "backlog at the win": lambda d: np.c_[np.minimum(d.backlog, 20) / 10],
    "today's booking share so far": lambda d: np.c_[d.today_fast_f],
    "today's lookers so far": lambda d: np.c_[d.today_look_f],
}
y, groups = df.late.values.astype(int), df.seed.values
folds = list(GroupKFold(5).split(df, y, groups))


def cv(columns: np.ndarray) -> tuple[float, float, float, float]:
    """Out-of-fold AUC, log loss, and the late orders a week among the riskiest 5% and 10% of orders."""
    p = np.zeros(len(df))
    for train, test in folds:
        model = LogisticRegression(C=10, max_iter=2000).fit(columns[train], y[train])
        p[test] = model.predict_proba(columns[test])[:, 1]
    order = np.argsort(-p)
    top5, top10 = order[: len(df) // 20], order[: len(df) // 10]
    return roc_auc_score(y, p), log_loss(y, p), y[top5].sum() / weeks, y[top10].sum() / weeks


base = np.c_[df.z.values]
b = cv(base)
print(f"\nOn seeds left out. Base (the fitted chance alone): AUC {b[0]:.4f}, log loss {b[1]:.5f}, late orders a week in the riskiest 5% {b[2]:.2f}, 10% {b[3]:.2f}")
print(f"{'added input':45} {'AUC':>7} {'d AUC':>7} {'d loss x1000':>12} {'top 5%':>7} {'top 10%':>8}")
allcols = [base]
for name, make in FEATURES.items():
    cols = np.c_[base, make(df)]
    r = cv(cols)
    allcols.append(make(df))
    print(f"{name:45} {r[0]:7.4f} {r[0] - b[0]:+7.4f} {(r[1] - b[1]) * 1000:+12.3f} {r[2] - b[2]:+7.2f} {r[3] - b[3]:+8.2f}")
quote_time = [n for n in FEATURES if n not in ("backlog at the win", "today's booking share so far", "today's lookers so far", "snow forecast")]
r = cv(np.c_[base, *[FEATURES[n](df) for n in quote_time]])
print(f"{'all request and roster inputs':45} {r[0]:7.4f} {r[0] - b[0]:+7.4f} {(r[1] - b[1]) * 1000:+12.3f} {r[2] - b[2]:+7.2f} {r[3] - b[3]:+8.2f}")
r = cv(np.c_[tuple(allcols)])
print(f"{'all, with the day state and snow':45} {r[0]:7.4f} {r[0] - b[0]:+7.4f} {(r[1] - b[1]) * 1000:+12.3f} {r[2] - b[2]:+7.2f} {r[3] - b[3]:+8.2f}")
