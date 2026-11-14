"""Scratch: what the inputs that the late chance (slow.py, "friday") leaves out are worth in the quote.

    SPREAD_DATA=... python scratch/inputs/late_value.py [variant]

Fits the late chance again with each family of quote-time inputs added, on the won one-car dealer orders, and predicts
every serious quote of the seeds left out. Then prices every quote again in expected values, as the best policy does:
the multiple with the highest chance x (price - 1.2 x fee - 150 euros x late chance), with the day's shift known. The
value of a family is the expected objective of pricing with its late chance less that of pricing with slow.py's, both
judged by the late chance with every family added. There are no drivers in this replay: for the curve's slope, play
gave a third to a half of what such a replay gave.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

from lib import load, logit

SLOPE, SD, COST, LATE_EUR, REAL_LATE_EUR = 12.5405, 0.16, 1.2, 150, 82
variant = sys.argv[1] if len(sys.argv) > 1 else "steep-notes-offers-8"
weeks = load(variant)
q = pd.DataFrame([{**row, "seed": w["week"]["seed"], "roster": w["week"]["roster"]} for w in weeks for row in w["quotes"] if row["kind"] == ""])
n_weeks = q.seed.nunique()
q["day"] = q["at"] // 1440
q["z0"] = logit(q.p_slow)
q["next_week"] = (q.own_last // 1440 >= 7).astype(float)
q["sat"] = (q.own_last // 1440 == 5).astype(float)
won = q.won & ~q.cancelled
print(f"{variant}: {len(q) / n_weeks:.0f} serious one-car dealer quotes a week in {n_weeks} weeks, {won.sum() / n_weeks:.0f} won, {q[won].late.mean():.2%} late")
check = q[won & (q.opt == q.fast)]
print(f"own last pickup minute against the world's lastPickupAt, orders won at the fastest option: equal {np.mean(check.own_last == check.true_last):.1%}, "
      f"within 30 minutes {np.mean(abs(check.own_last - check.true_last) <= 30):.1%}; naive (deadline - drive) equal {np.mean((check.own_last + (check.h_naive - check.h_own) * 60).round() == check.true_last):.1%}")

FAMILIES = {
    "site hours in the hours left": lambda d: np.c_[d.h_own < 6, d.h_own < 8, d.h_own < 12, d.h_own < 24, np.minimum(d.h_naive - d.h_own, 6)],
    "when the car can first be collected": lambda d: np.c_[d.ready_in > 0.3, np.minimum(d.ready_in, 48) / 24, d.window < 4, d.window < 8, d.window < 24],
    "due next week or on Saturday": lambda d: np.c_[d.next_week, d.sat],
    "slower options quoted too": lambda d: np.c_[d.nopt >= 2, d.nopt >= 3, d.slowest == "within_3_days", (d.fast == "next_day") & (d.nopt == 1)],
    "electric car under 30% charge": lambda d: np.c_[d.low, d.elec],
    "drivers living at the delivery": lambda d: np.c_[np.log1p(d.dl_near), d.dl_near >= 100],
    "drivers in the pickup town, active drivers nearby": lambda d: np.c_[d.pk_town == 0, np.log1p(d.pk_town), np.log1p(d.act_near), np.log1p(d.notified)],
    "weekday and hour of arrival": lambda d: np.c_[d.dow == 0, d.dow == 1, d.dow == 2, d.dow == 3, d.hour < 10, d.hour >= 13, d.hour >= 15],
    "bulk order": lambda d: np.c_[d.batch],
    "snow forecast (being built)": lambda d: np.c_[d.snow],
}
groups = q.seed.values
folds = list(GroupKFold(5).split(q, groups=groups))
y = q.late.values.astype(int)
mask = won.values


def predict(columns: np.ndarray) -> np.ndarray:
    """The late chance of every quote, from a fit on the won orders of the other seeds."""
    p = np.zeros(len(q))
    columns = columns.astype(float)
    for train, test in folds:
        train = train[mask[train]]
        p[test] = LogisticRegression(C=10, max_iter=3000).fit(columns[train], y[train]).predict_proba(columns[test])[:, 1]
    return p


base = np.c_[q.z0.values]
chances = {"slow.py as it is": q.p_slow.values}
for name, make in FAMILIES.items():
    chances[name] = predict(np.c_[base, make(q)])
not_snow = [n for n in FAMILIES if "snow" not in n]
chances["all of the above but snow"] = predict(np.c_[base, *[FAMILIES[n](q) for n in not_snow]])
chances["all"] = predict(np.c_[base, *[make(q) for make in FAMILIES.values()]])
truth = chances["all"]

# The day's shift, in hindsight, from every answer of the day.
q["at_list"] = q.z + SLOPE * np.log(q.m)
shift = np.zeros(len(q))
for _, index in q.groupby(["seed", "day"]).indices.items():
    z, w_, d = q.z.values[index], q.won.values[index].astype(float), 0.0
    for _ in range(8):
        c = 1 / (1 + np.exp(-(z + SLOPE * d)))
        d += np.clip((SLOPE * (w_ - c).sum() - d / SD**2) / (SLOPE**2 * (c * (1 - c)).sum() + 1 / SD**2), -0.3, 0.3)
    shift[index] = d
multiples = np.arange(1.0, 2.4001, 0.02)
log_m = np.log(multiples)[None, :]
at_list, list_, fee = q.at_list.values[:, None], q["list"].values[:, None] / 100, q.fee.values[:, None] / 100
chance = 1 / (1 + np.exp(-(at_list - SLOPE * (log_m - shift[:, None]))))
revenue = multiples[None, :] * list_


def replay(p: np.ndarray) -> dict:
    """Prices every quote with the late chance `p`; judges it by `truth`."""
    best = np.argmax(chance * (revenue - COST * fee - LATE_EUR * p[:, None]), axis=1)
    rows = np.arange(len(q))
    win, price = chance[rows, best], revenue[rows, best]
    return {"objective": (win * (price - COST * fee[:, 0] - LATE_EUR * truth)).sum() / n_weeks, "margin": (win * (price - COST * fee[:, 0] - REAL_LATE_EUR * truth)).sum() / n_weeks,
            "orders": win.sum() / n_weeks, "late": (win * truth).sum() / n_weeks, "multiple": float(np.average(multiples[best], weights=win))}


ref = replay(chances["slow.py as it is"])
print(f"\nPriced with slow.py as it is: {ref['orders']:.0f} orders a week, {ref['late']:.1f} expected late, objective {ref['objective']:,.0f} euros")
print(f"{'late chance with':52} {'AUC':>6} {'objective':>10} {'margin at 82 a late order':>26} {'orders':>7} {'late orders':>12} {'late share':>11}")
for name, p in chances.items():
    r = replay(p)
    auc = roc_auc_score(y[mask], p[mask])
    print(f"{name:52} {auc:6.3f} {r['objective'] - ref['objective']:+10.0f} {r['margin'] - ref['margin']:+26.0f} {r['orders'] - ref['orders']:+7.1f} {r['late'] - ref['late']:+12.2f} {r['late'] / r['orders']:11.2%}")

# Where the two late chances differ most: the quotes that the richer one makes dearer or cheaper.
p0, p1 = chances["slow.py as it is"], chances["all of the above but snow"]
diff = pd.Series(pd.cut(p1 - p0, [-1, -0.05, -0.02, -0.01, 0.01, 0.02, 0.05, 1]), index=q.index)
t = q[mask].groupby(diff[mask], observed=True).agg(orders_a_week=("late", lambda s: len(s) / n_weeks), slow_py=("p_slow", "mean"), late=("late", "mean"))
t["richer"] = pd.Series(p1[mask], index=q.index[mask]).groupby(diff[mask], observed=True).mean()
print("\nWon orders by how far the richer late chance is from slow.py's (seeds left out):")
print(t.round(4).to_string())
print("\nCalibration of the richer late chance on seeds left out:")
bands = pd.Series(pd.cut(p1, [0, .01, .02, .03, .05, .08, .12, .2, 1]), index=q.index)[mask]
cal = q[mask].groupby(bands, observed=True).agg(n=("late", "size"), late=("late", "mean"))
cal["fitted"] = pd.Series(p1[mask], index=q.index[mask]).groupby(bands, observed=True).mean()
print(cal.round(4).to_string())
weights = LogisticRegression(C=10, max_iter=3000).fit(np.c_[base, *[FAMILIES[n](q) for n in not_snow]].astype(float)[mask], y[mask])
names = ["logit of slow.py"] + [f"{n} [{i}]" for n in not_snow for i in range(FAMILIES[n](q[:5]).shape[1])]
print("\nWeights of the fit on all weeks (log odds):")
for n, w_ in zip(names, weights.coef_[0]):
    print(f"  {n:60} {w_:+.3f}")
print(f"  intercept {weights.intercept_[0]:+.3f}")
