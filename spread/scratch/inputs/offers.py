"""Scratch: which direct offers are read and accepted (offer_answered), by what the desk knows of the driver when it sends.

    SPREAD_DATA=... python scratch/inputs/offers.py [variant]

The policy offers to the drivers who looked at a gig or booked one today, nearest to the pickup first. It does not use
the answers: `expired` is an offer the driver did not read, `declined` one that was read and did not pay.
"""
from __future__ import annotations

import bisect
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

from lib import load

variant = sys.argv[1] if len(sys.argv) > 1 else "steep-notes-offers-8"
weeks = load(variant)
rows = []
for w in weeks:
    looks: dict[str, list[int]] = {}
    for d in w["days"]:
        for minute, driver in d["views"]:
            looks.setdefault(driver, []).append(d["day"] * 1440 + minute)
    for times in looks.values():
        times.sort()
    late = {o["id"]: o["late"] for o in w["orders"]}
    for o in w["offers"]:
        sent = o["at"] - 10  # no look that the offer itself caused counts
        times = looks.get(o["driver"], [])
        before = times[:bisect.bisect_left(times, sent)]
        today = [t for t in before if t // 1440 == sent // 1440]
        rows.append({**o, "seed": w["week"]["seed"], "looks_before": len(today), "since": sent - today[-1] if today else np.nan, "late": late.get(o["order"], False),
                     "looked_before_today": sum(1 for t in before if t // 1440 < sent // 1440)})
df = pd.DataFrame(rows)
n_weeks = df.seed.nunique()
df["read"], df["yes"] = df.answer != "expired", df.answer == "accepted"
print(f"{variant}: {len(df) / n_weeks:.0f} offers a week in {n_weeks} weeks, {df.read.mean():.1%} read, {df.yes.sum() / n_weeks:.1f} accepted a week, {df.yes.sum() / df.read.sum():.1%} of the read ones")


def table(name: str, groups) -> None:
    t = df.groupby(groups, observed=True).agg(offers_a_week=("read", lambda s: len(s) / n_weeks), read=("read", "mean"), yes_of_read=("yes", lambda s: s.sum() / max(df.loc[s.index, "read"].sum(), 1)),
                                              yes_per_100=("yes", lambda s: 100 * s.mean()), yes_a_week=("yes", lambda s: s.sum() / n_weeks))
    print(f"\n{name}\n{t.round(3).to_string()}")


table("Earlier offers to the driver today that expired unread", df.unread_today.clip(upper=3).astype(str) + " unread, " + df.read_today.clip(upper=1).astype(str) + " read")
table("Earlier offers to the driver today that were read", df.read_today.clip(upper=2))
table("Minutes since the driver's last look today, before the offer", pd.cut(df.since, [-1, 15, 30, 60, 120, 240, 480, 2000]).astype(str))
table("Looks by the driver today, before the offer", pd.cut(df.looks_before, [-1, 0, 1, 2, 4, 8, 1000]))
table("Hour the offer is sent", pd.cut(df.tod / 60, [0, 9, 11, 13, 15, 17, 19, 24]))
table("Minutes from the driver's home to the pickup", pd.cut(df.to_pk, [-1, 0, 30, 60, 120, 240, 10000]))
table("Minutes from the delivery to the driver's home", pd.cut(df.to_home, [-1, 0, 30, 60, 120, 240, 10000]))
table("Gigs of the desk that the driver has booked this week", df.holds.clip(upper=3))
table("Driver's rating", pd.cut(df.rating, [0, 4.2, 4.5, 4.8, 5.01]))
table("Driver's completed gigs", pd.cut(df.gigs, [-1, 5, 20, 50, 150, 100000]))
table("Driver's past drops", pd.cut(df.drops, [-1, 0, 1, 2, 4, 100]))
table("Hours left to lastPickupAt", pd.cut(df.hours_left, [-1000, 0, 2, 3, 5, 8, 1000]))
table("Weekday", df.day)

# How much better could the desk choose whom to offer to? A fit of "accepted" on what it knows, on seeds left out.
x = np.c_[np.log1p(df.since.fillna(2000)), np.log1p(df.looks_before), df.unread_today.clip(upper=3), df.read_today.clip(upper=2), np.log1p(df.to_pk), np.log1p(df.to_home), (df.to_home == 0),
          (df.to_pk == 0), df.holds.clip(upper=3), df.rating, np.log1p(df.gigs), np.log1p(df.drops), (df.tod < 660), (df.tod >= 900), (df.tod >= 1020), df.hours_left.clip(-5, 10)].astype(float)
for target in ("read", "yes"):
    y, p = df[target].values.astype(int), np.zeros(len(df))
    for train, test in GroupKFold(5).split(x, y, df.seed.values):
        p[test] = LogisticRegression(C=1, max_iter=3000).fit(x[train], y[train]).predict_proba(x[test])[:, 1]
    order = np.argsort(-p)
    print(f"\n{target}: AUC on seeds left out {roc_auc_score(y, p):.3f}. Share of all '{target}' among the offers ranked highest: "
          + ", ".join(f"top {int(s * 100)}% of offers {y[order[: int(len(y) * s)]].sum() / y.sum():.0%}" for s in (0.1, 0.25, 0.5)))
    df["p_" + target] = p
# The desk's offer slots: 3 open a gig. If the lowest-ranked half of the offers were not sent, how many acceptances remain?
keep = df.p_yes >= df.p_yes.median()
print(f"\nDropping the half of the offers least likely to be accepted keeps {df[keep].yes.sum() / df.yes.sum():.0%} of the acceptances "
      f"({df[keep].yes.sum() / n_weeks:.1f} of {df.yes.sum() / n_weeks:.1f} a week) with {keep.sum() / n_weeks:.0f} of {len(df) / n_weeks:.0f} offers.")
per_order = df.groupby(["seed", "order"]).agg(offers=("yes", "size"), yes=("yes", "max"), late=("late", "first"), first=("hours_left", "max"))
print(f"orders that got offers: {len(per_order) / n_weeks:.1f} a week, {per_order.yes.mean():.1%} took one, late {per_order.late.mean():.1%}; "
      f"late with an accepted offer {per_order[per_order.yes].late.mean():.1%}, without {per_order[~per_order.yes].late.mean():.1%}")
print(per_order.groupby(pd.cut(per_order.offers, [0, 3, 9, 30, 90, 1000])).agg(orders=("yes", "size"), took=("yes", "mean"), late=("late", "mean")).round(3).to_string())
