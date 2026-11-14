"""Scratch: which driver-list attributes and Monday signals mark a week that ends short of drivers, beyond the length of
the driver list (which the late chance already has).

    SPREAD_DATA=... python scratch/inputs/week_supply.py [variant]

Outcome: the week's late share, and whether it ends under 92% or 90% on time. Linear fits, tested on weeks left out.
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import KFold, cross_val_predict

from lib import load

variant = sys.argv[1] if len(sys.argv) > 1 else "steep-notes-offers-8"
weeks = load(variant)
MAP = json.loads((Path(os.environ.get("SPREAD_DATA", "data")) / "map.json").read_text())
POS = {p["id"]: (math.radians(p["lat"]), math.radians(p["lon"])) for p in MAP["places"]}


def km(a: str, b: str) -> float:
    (la, lo), (lb, lob) = POS[a], POS[b]
    return 2 * 6371 * math.asin(math.sqrt(math.sin((lb - la) / 2) ** 2 + math.cos(la) * math.cos(lb) * math.sin((lob - lo) / 2) ** 2))


NEAR = {p: [c for c in POS if km(p, c) <= 30] for p in POS}
freq: dict[str, float] = {}
for w in weeks:
    for o in w["orders"]:
        freq[o["pk"]] = freq.get(o["pk"], 0) + 1
total = sum(freq.values())
freq = {p: v / total for p, v in freq.items()}

rows = []
for w in weeks:
    k, homes = w["week"], w["week"]["homes"]
    notified = {p: sum(homes.get(c, 0) for c in NEAR[p]) for p in POS}
    shares = np.array(sorted(homes.values(), reverse=True)) / k["roster"]
    monday = next((d for d in w["days"] if d["day"] == 0), None)
    lookers = len({d for _, d in monday["views"]}) if monday else 0
    read = monday["offers"]["declined"] + monday["offers"]["accepted"] if monday else 0
    sent = read + monday["offers"]["expired"] if monday else 0
    mon = [o for o in w["orders"] if o["won_at"] < 1440 and o["post"] is not None]
    rows.append({"seed": k["seed"], "late": 1 - k["score"]["onTimeShare"], "orders": k["score"]["wonOrders"], "margin": k["score"]["marginCents"] / 100,
                 "roster": k["roster"], "experienced": k["experienced"], "gigs50": k["gigs50"], "gigs150": k["gigs150"], "newcomers": k["gigs5"] / k["roster"],
                 "dropped_before": k["drops_any"], "drops_mean": k["drops_mean"], "rating": k["rating_mean"], "manual": k["manual"] / k["roster"],
                 "top3_towns": shares[:3].sum(), "towns_eff": 1 / (shares ** 2).sum(),
                 "thin_usual": sum(f for p, f in freq.items() if notified[p] < 5), "log_notified_usual": sum(f * math.log1p(notified[p]) for p, f in freq.items()),
                 "thin_requests": float(np.mean(np.array(k["req_notified"]) < 5)), "log_active_requests": float(np.mean(np.log1p(k["req_active"]))),
                 "monday_lookers": lookers / k["roster"], "monday_fast": float(np.mean([o["book"] is not None and o["book"] - o["post"] <= 30 for o in mon])) if mon else np.nan,
                 "monday_looks_a_car": float(np.mean([o["looks15"][1] for o in mon])) if mon else np.nan, "monday_offers_read": read / sent if sent else np.nan})
df = pd.DataFrame(rows)
df = df.fillna(df.mean(numeric_only=True))
n = len(df)
print(f"{variant}: {n} weeks; late share mean {df.late.mean():.2%}, sd {df.late.std():.2%}; under 92% on time {np.mean(df.late > 0.08):.1%}, under 90% {np.mean(df.late > 0.10):.1%}; "
      f"under 720 drivers {np.mean(df.roster < 720):.0%} (the natural mix has 30%)")
known_monday = ["experienced", "gigs50", "gigs150", "newcomers", "dropped_before", "drops_mean", "rating", "manual", "top3_towns", "towns_eff", "thin_usual", "log_notified_usual"]
by_requests = ["thin_requests", "log_active_requests"]
monday = ["monday_lookers", "monday_fast", "monday_looks_a_car", "monday_offers_read"]
folds = KFold(10, shuffle=True, random_state=0)


def r2(columns: list[str]) -> float:
    p = cross_val_predict(LinearRegression(), df[columns].values, df.late.values, cv=folds)
    return 1 - ((df.late - p) ** 2).sum() / ((df.late - df.late.mean()) ** 2).sum()


def auc(columns: list[str], limit: float) -> float:
    y = (df.late > limit).astype(int).values
    x = (df[columns] - df[columns].mean()) / df[columns].std()
    p = cross_val_predict(LogisticRegression(C=1, max_iter=2000), x.values, y, cv=folds, method="predict_proba")[:, 1]
    return roc_auc_score(y, p)


base = r2(["roster"])
print(f"\nThe length of the driver list alone: R2 {base:.3f} on weeks left out; AUC for a week under 92% {auc(['roster'], 0.08):.3f}, under 90% {auc(['roster'], 0.10):.3f}")
print(f"{'input':24} {'corr with late share':>21} {'corr with roster':>17} {'R2 with roster':>15} {'gain':>7} {'AUC <92% with roster':>21}")
for name in known_monday + by_requests + monday:
    both = r2(["roster", name])
    print(f"{name:24} {np.corrcoef(df[name], df.late)[0, 1]:+21.2f} {np.corrcoef(df[name], df.roster)[0, 1]:+17.2f} {both:15.3f} {both - base:+7.3f} {auc(['roster', name], 0.08):21.3f}")
for name, cols in (("the driver list, all", ["roster"] + known_monday), ("... and the week's requests", ["roster"] + known_monday + by_requests), ("... and Monday's events", ["roster"] + known_monday + by_requests + monday)):
    print(f"{name:40} R2 {r2(cols):.3f}; AUC under 92% {auc(cols, 0.08):.3f}; under 90% {auc(cols, 0.10):.3f}")
print("\nWeeks under 92% on time by the experienced drivers on the list, inside bands of the list's length:")
df["rb"] = pd.cut(df.roster, [0, 660, 690, 720, 800, 2000])
df["eb"] = df.groupby("rb", observed=True).experienced.transform(lambda s: s > s.median())
print(df.groupby(["rb", "eb"], observed=True).agg(weeks=("late", "size"), experienced=("experienced", "mean"), late=("late", "mean"), under_92=("late", lambda s: np.mean(s > 0.08)), under_90=("late", lambda s: np.mean(s > 0.10))).round(3).to_string())
print("\n... and by the usual share of requests from towns with under 5 drivers within 30 km:")
df["tb"] = df.groupby("rb", observed=True).thin_usual.transform(lambda s: s > s.median())
print(df.groupby(["rb", "tb"], observed=True).agg(weeks=("late", "size"), thin=("thin_usual", "mean"), late=("late", "mean"), under_92=("late", lambda s: np.mean(s > 0.08)), under_90=("late", lambda s: np.mean(s > 0.10))).round(3).to_string())
