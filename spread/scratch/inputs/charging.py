"""Scratch: electric cars under 30% charge. The desk plans a charging stop (`withCharging`) for each of them; RULES.md
needs one only on a route over 200 km. How do those orders book and end, on short and on long routes?

    SPREAD_DATA=... python scratch/inputs/charging.py [variant]

One-car orders between dealer sites. Prints the orders a week, the late share beside the fitted chance (slow.py), the
share booked within the hour, the fee paid over the typical fee and the lookers, by route length and charge. Then the
seeds with the most such orders on routes of 200 km or less, for a played check of the stop.
"""
from __future__ import annotations

import json
import sys

import pandas as pd

from lib import DATA, load

LIMIT_KM = 200  # RULES.md, Rules for handling cars, rule 3
variant = sys.argv[1] if len(sys.argv) > 1 else "steep-notes-offers-8"
KM = {(r["from"], r["to"]): r["km"] for r in json.loads((DATA.parent / "map.json").read_text())["roads"]}
rows = []
for w in load(variant):
    for o in w["orders"]:
        if o["kind"] or o["cancelled"] or o["post"] is None:
            continue
        rows.append({"seed": w["week"]["seed"], "low": bool(o["elec"] and o["charge"] is not None and o["charge"] < 30), "km": KM[(o["pk"], o["dl"])],
                     "late": o["late"], "p": o["p_slow"], "hour": o["book"] is not None and o["book"] - o["post"] <= 60,
                     "paid": None if o["book_fee"] is None else o["book_fee"] / o["fee"], "fee": o["fee"] / 100, "lookers": o["looks15"][1],
                     "dropped": o["drops"] > 0, "warned": o["warn"] is not None})
df = pd.DataFrame(rows)
n = df.seed.nunique()
df["route"] = df.km.map(lambda km: f"to {LIMIT_KM} km" if km <= LIMIT_KM else f"over {LIMIT_KM} km")
print(f"{variant}: {len(df)} one-car dealer orders in {n} weeks")
t = df.groupby(["route", "low"]).agg(a_week=("late", lambda s: len(s) / n), fitted=("p", "mean"), late=("late", "mean"), booked_in_an_hour=("hour", "mean"),
                                     fee_paid=("paid", "mean"), lookers_15_min=("lookers", "mean"), dropped=("dropped", "mean"), warned=("warned", "mean"))
t["extra_late_a_week"] = (t.late - t.fitted) * t.a_week
print(t.round(3).to_string())
short, others = df[df.low & (df.km <= LIMIT_KM)], df[~df.low & (df.km <= LIMIT_KM)]
booked, booked_others = short[short.paid.notna()], others[others.paid.notna()]  # euros paid over euros of typical fee, not the mean of the orders' ratios
overpay = ((booked.paid * booked.fee).sum() / booked.fee.sum() - (booked_others.paid * booked_others.fee).sum() / booked_others.fee.sum()) * booked.fee.sum() / n
print(f"\nunder 30% charge on routes of {LIMIT_KM} km or less: {len(short) / n:.1f} orders a week, {overpay:.0f} euros a week of fees above the other cars' rate, "
      f"{(short.late.mean() - short.p.mean()) * len(short) / n:.2f} late orders a week above the fitted chance")
print("\nseeds with the most such orders:")
print(short.groupby("seed").agg(orders=("late", "size"), late=("late", "sum")).sort_values("orders", ascending=False).head(12).to_string())
