"""Scratch: does the day's booking speed so far (gig_booked against the posting) mark a day or a week that is short of
drivers (flu, snow, a thin world), and how early?

    SPREAD_DATA=... python scratch/inputs/day_supply.py [variant]

The signal at a minute: of today's cars posted at least 30 minutes ago, the share booked within 30 minutes, over the share
that the same cars book at in an average world (by drivers notified, weekday and hour, from the other weeks). The same
with lookers in the first 15 minutes (gig_viewed). Outcome: the late share of the orders won later, against the fitted
chance (slow.py).
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from lib import load, orders

variant = sys.argv[1] if len(sys.argv) > 1 else "steep-notes-offers-8"
weeks = load(variant)
df = orders(weeks)
df = df[~df.cancelled & df.post_delay.notna()].copy()
df["pday"], df["tod"] = df.t // 1440, df.t % 1440
df = df[df.pday <= 4]
df["nb"] = pd.cut(df.notified, [-1, 0, 4, 9, 19, 39, 69, 99, 149, 10000]).astype(str)
df["hb"] = pd.cut(df.tod, [0, 600, 720, 840, 960, 1440]).astype(str)
df["fast"] = (df.book_delay <= 30).astype(float)
# Expected values from the other weeks: leave the own seed out through fold means.
seeds = np.array(sorted(df.seed.unique()))
fold = {s: i % 5 for i, s in enumerate(seeds)}
df["fold"] = df.seed.map(fold)
df["exp_fast"], df["exp_look"] = np.nan, np.nan
for k in range(5):
    train, test = df[df.fold != k], df.fold == k
    table = train.groupby(["nb", "pday", "hb"]).agg(exp_fast=("fast", "mean"), exp_look=("lookers15", "mean"))
    joined = df.loc[test, ["nb", "pday", "hb"]].join(table, on=["nb", "pday", "hb"])
    df.loc[test, "exp_fast"], df.loc[test, "exp_look"] = joined.exp_fast.values, joined.exp_look.values
df["exp_fast"] = df.exp_fast.fillna(df.fast.mean())
df["exp_look"] = df.exp_look.fillna(df.lookers15.mean())
n_weeks = df.seed.nunique()

print(f"{variant}: {len(df)} orders in {n_weeks} weeks\n")
print("The whole day's booking speed against the day's late share (one row per week and day with 15 or more orders):")
day = df.groupby(["seed", "pday"]).agg(n=("id", "size"), fast=("fast", "sum"), exp=("exp_fast", "sum"), look=("lookers15", "sum"), exp_look=("exp_look", "sum"),
                                       late=("late", "mean"), p=("p_slow", "mean"), lates=("late", "sum"), roster=("roster", "first")).reset_index()
day = day[day.n >= 15]
day["s"], day["v"] = day.fast / day.exp, day.look / day.exp_look
for col, name in (("s", "booking speed over expected"), ("v", "lookers over expected")):
    t = day.groupby(pd.cut(day[col], [0, .6, .7, .8, .9, 1.1, 1.3, 9])).agg(days=("n", "size"), days_a_week=("n", lambda s: len(s) / n_weeks), orders=("n", "mean"), late=("late", "mean"), fitted=("p", "mean"),
                                                                           extra_late=("lates", lambda s: 0.0))
    t["extra_late_a_day"] = (t.late - t.fitted) * t.orders
    print(name)
    print(t.drop(columns="extra_late").round(3).to_string())
print(f"correlation of the day's booking speed with roster size {day[['s', 'roster']].corr().iloc[0, 1]:.2f}, with the day's lookers {day[['s', 'v']].corr().iloc[0, 1]:.2f}")
bad = day[day.s < 0.7]
print(f"days under 0.7: {len(bad) / n_weeks:.2f} a week, in {bad.seed.nunique() / n_weeks:.0%} of weeks; by weekday {bad.pday.value_counts().sort_index().to_dict()}")
print(f"days under 0.8: {(day.s < 0.8).sum() / n_weeks:.2f} a week, in {day[day.s < 0.8].seed.nunique() / n_weeks:.0%} of weeks")

print("\nHow early: the signal at a minute of the day, from the cars posted at least 30 minutes before, against the orders won after it that day.")
rows = []
for (seed, pday), g in df.groupby(["seed", "pday"]):
    whole = g.fast.sum() / g.exp_fast.sum() if len(g) >= 15 else np.nan
    for minute in (570, 600, 630, 660, 720, 780, 840):
        seen, later = g[g.tod + 30 <= minute], g[g.tod >= minute]
        if len(seen) < 5 or len(later) < 5:
            continue
        rows.append({"seed": seed, "pday": pday, "minute": minute, "n_seen": len(seen), "s": seen.fast.sum() / seen.exp_fast.sum(), "v": seen.lookers15.sum() / seen.exp_look.sum(),
                     "later": len(later), "lates": later.late.sum(), "fitted": later.p_slow.sum(), "whole": whole, "roster": g.roster.iloc[0],
                     "same_day": (later.opt == "same_day").sum(), "same_day_lates": later[later.opt == "same_day"].late.sum(), "same_day_fitted": later[later.opt == "same_day"].p_slow.sum()})
at = pd.DataFrame(rows)
print(f"{'time':>5} {'days':>5} {'cars seen':>9} {'corr with whole day':>20} {'flag<0.7 days/wk':>17} {'hit of bad days':>16} {'false of flags':>15} {'orders later':>13} {'late, flagged':>14} {'fitted':>7} {'late, others':>13} {'fitted':>7} {'extra late/wk':>14}")
for minute, g in at.groupby("minute"):
    flag = g[g.s < 0.7]
    truth = g.whole < 0.7
    hit = ((g.s < 0.7) & truth).sum() / max(truth.sum(), 1)
    false = ((g.s < 0.7) & ~(g.whole < 0.8)).sum() / max(len(flag), 1)
    rest = g[g.s >= 0.7]
    print(f"{minute // 60:02d}:{minute % 60:02d} {len(g):5d} {g.n_seen.mean():9.1f} {g[['s', 'whole']].corr().iloc[0, 1]:20.2f} {len(flag) / n_weeks:17.2f} {hit:16.0%} {false:15.0%} {flag.later.mean():13.1f} "
          f"{flag.lates.sum() / flag.later.sum():14.1%} {flag.fitted.sum() / flag.later.sum():7.1%} {rest.lates.sum() / rest.later.sum():13.1%} {rest.fitted.sum() / rest.later.sum():7.1%} "
          f"{(flag.lates.sum() - flag.fitted.sum()) / n_weeks:14.2f}")
print("\nThe same at 11:00 by band of the signal (late share of the orders won after 11:00, and of the same_day ones):")
g = at[at.minute == 660]
t = g.groupby(pd.cut(g.s, [0, .5, .6, .7, .8, .9, 1.1, 9])).agg(days=("s", "size"), later=("later", "sum"), lates=("lates", "sum"), fitted=("fitted", "sum"), sd=("same_day", "sum"), sd_l=("same_day_lates", "sum"), sd_f=("same_day_fitted", "sum"))
t["days_a_week"], t["late"], t["fit"], t["same_day_late"], t["same_day_fit"] = t.days / n_weeks, t.lates / t.later, t.fitted / t.later, t.sd_l / t.sd, t.sd_f / t.sd
t["extra_late_a_week"] = (t.lates - t.fitted) / n_weeks
print(t[["days_a_week", "later", "late", "fit", "same_day_late", "same_day_fit", "extra_late_a_week"]].round(3).to_string())
print("lookers at 11:00 instead:")
t = g.groupby(pd.cut(g.v, [0, .6, .7, .8, .9, 1.1, 1.3, 9])).agg(days=("s", "size"), later=("later", "sum"), lates=("lates", "sum"), fitted=("fitted", "sum"))
t["late"], t["fit"] = t.lates / t.later, t.fitted / t.later
print(t[["days", "late", "fit"]].round(3).to_string())

print("\nDoes one day's booking speed carry to the next (a thin week), and to the week's late share?")
piv = day.pivot(index="seed", columns="pday", values="s")
print("correlation between days:\n", piv.corr().round(2).to_string())
wk = df.groupby("seed").agg(late=("late", "mean"), p=("p_slow", "mean"), roster=("roster", "first"), n=("id", "size"))
for upto, name in ((0, "Monday"), (1, "Monday and Tuesday"), (2, "Monday to Wednesday")):
    part = df[df.pday <= upto].groupby("seed").agg(fast=("fast", "sum"), exp=("exp_fast", "sum"), late_so_far=("late", "mean"))
    rest = df[df.pday > upto].groupby("seed").agg(late_rest=("late", "mean"), p_rest=("p_slow", "mean"))
    j = wk.join(part).join(rest)
    j["s"] = j.fast / j.exp
    x = np.c_[np.ones(len(j)), j.roster, j.s]
    r2_roster = np.corrcoef(j.roster, j.late_rest)[0, 1] ** 2
    beta, *_ = np.linalg.lstsq(x, j.late_rest, rcond=None)
    r2_both = 1 - ((j.late_rest - x @ beta) ** 2).sum() / ((j.late_rest - j.late_rest.mean()) ** 2).sum()
    print(f"booking speed through {name}: correlation with the late share of the orders won after it {np.corrcoef(j.s, j.late_rest)[0, 1]:+.2f}; "
          f"R2 roster alone {r2_roster:.3f}, roster and speed {r2_both:.3f}; with the week's late share {np.corrcoef(j.s, j.late)[0, 1]:+.2f}")
    low = j[j.s < j.s.quantile(0.2)]
    print(f"    the slowest fifth of weeks by then: late share after it {low.late_rest.mean():.1%} against {j.late_rest.mean():.1%} for all, fitted {low.p_rest.mean():.1%} against {j.p_rest.mean():.1%}")
