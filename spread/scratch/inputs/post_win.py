"""Scratch: what the events after the win say about a late order: looks without a booking (gig_viewed), the driver who
booked (the driver list's rating, completed gigs and drops), driver_late, no_show, offers (offer_answered).

    SPREAD_DATA=... python scratch/inputs/post_win.py [variant]
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from lib import load, orders

variant = sys.argv[1] if len(sys.argv) > 1 else "steep-notes-offers-8"
df = orders(load(variant))
df = df[~df.cancelled & df.post_delay.notna() & (df.kind == "")].copy()
weeks = df.seed.nunique()
print(f"{variant}: {len(df)} one-car dealer orders in {weeks} weeks, {df.late.mean():.2%} late")


def table(name: str, d: pd.DataFrame, groups, extra: dict | None = None) -> None:
    t = d.groupby(groups, observed=True).agg(n=("late", "size"), a_week=("late", lambda s: len(s) / weeks), fitted=("p_slow", "mean"), late=("late", "mean"), **(extra or {}))
    t["lates_a_week"] = t.late * t.a_week
    print(f"\n{name}\n{t.round(3).to_string()}")


unbooked15 = df[df.book_delay.isna() | (df.book_delay > 15)]
table("Not booked 15 minutes after the post, by distinct lookers in those 15 minutes", unbooked15, pd.cut(unbooked15.lookers15, [-1, 0, 1, 2, 4, 7, 12, 1000]),
      {"true_hours": ("true_hours", "median"), "notified": ("notified", "median")})
short = unbooked15[unbooked15.true_hours < 12]
table("... of those with under 12 hours to lastPickupAt", short, pd.cut(short.lookers15, [-1, 0, 2, 4, 7, 1000]))
unbooked60 = df[df.book_delay.isna() | (df.book_delay > 60)]
table("Not booked 60 minutes after the post, by distinct lookers in those 60 minutes", unbooked60, pd.cut(unbooked60.lookers60, [-1, 0, 2, 5, 10, 20, 1000]), {"true_hours": ("true_hours", "median")})
table("Booked or not within 15, 60 minutes", df, np.select([df.book_delay <= 15, df.book_delay <= 60, df.book_delay.notna()], ["a: 15 min", "b: 60 min", "c: later"], "d: never"))

b = df[df.d_drops.notna()].copy()
b["dropped"] = b.drops > 0
table("The first driver to book, by past drops on the driver list", b, pd.cut(b.d_drops, [-1, 0, 1, 2, 4, 100]), {"dropped": ("dropped", "mean"), "share": ("late", lambda s: len(s) / len(b))})
table("... by rating", b, pd.cut(b.d_rating, [0, 4.2, 4.5, 4.8, 5.01]), {"dropped": ("dropped", "mean")})
table("... by completed gigs", b, pd.cut(b.d_gigs, [-1, 5, 20, 50, 150, 100000]), {"dropped": ("dropped", "mean")})
table("... by home", b, np.select([b.d_home_dl, b.d_home_pk], ["delivery town", "pickup town"], "elsewhere"), {"dropped": ("dropped", "mean"), "fee": ("book_fee", "mean")})
tight = b[b.true_hours < 12]
table("... past drops, orders with under 12 hours to lastPickupAt", tight, pd.cut(tight.d_drops, [-1, 0, 1, 2, 4, 100]), {"dropped": ("dropped", "mean")})
table("Dropped orders", df, df.drops.clip(upper=3))
table("driver_late events on the order", df, df.driver_late.clip(upper=2))
table("no_show events on the order", df, df.no_show.clip(upper=1))
table("order_changed events on the order", df, df.changed.clip(upper=1))
table("Deadline warning", df, df.warned)
warned = df[df.warned]
table("Warned orders by direct offers read", warned, pd.cut(warned.offers_read, [-1, 0, 1, 3, 100]), {"offers": ("offers", "mean"), "yes": ("offers_yes", "mean")})
print(f"\noffers a week {df.offers.sum() / weeks:.0f}, read {df.offers_read.sum() / weeks:.0f}, accepted {df.offers_yes.sum() / weeks:.1f}")
