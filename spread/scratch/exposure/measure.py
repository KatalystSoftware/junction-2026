"""Scratch: the inputs of a quote rule that prices the risk of drops in flight, measured on saved weeks.

For every booking of a one-car gig of the desk: how long a driver held it, whether it ended in a drop (gig_dropped or
no_show) and when; for every night: how many of the desk's booked gigs were dropped in its first hour (a wave is 10 or
more, scratch/drop_waves.py); for every drop: whether and how fast the car found another driver and whether the order
ended late, by the hours left to its last pickup, the drivers notified near the pickup and the cars waiting at the drop.

    PYTHONPATH=. uv run --with numpy python scratch/exposure/measure.py rows slow-friday-late-150-kinds-limits,steep-notes-offers-8
    PYTHONPATH=. uv run --with numpy python scratch/exposure/measure.py report

`rows` writes data/exposure/<variant>.pkl; `report` prints the tables from every saved one.
"""
from __future__ import annotations

import collections
import gzip
import json
import pickle
import sys
from multiprocessing import Pool

import numpy as np

from spreadlab.server import data_dir, drivers_near, near_places

DAY, HOUR, WAVE = 1440, 60, 10
OUT = data_dir() / "exposure"
MAP = json.loads((data_dir() / "map.json").read_text())
NEAR = near_places(MAP)


def week(path: str) -> dict | None:
    d = json.load(gzip.open(path))
    if not d["events"]:
        return None
    notified = drivers_near(d["roster"], NEAR)
    record = {r["id"]: r.get("drops", 0) for r in d["roster"]}
    gig_orders = {g["id"]: sorted({s["orderId"] for s in g["stops"]}) for g in d["gigs"]}
    one = {g: o[0] for g, o in gig_orders.items() if len(o) == 1}
    orders, late, held, bookings, drops = {}, set(), {}, [], []
    open_at = {}  # order -> the minute its car became unbooked (won, dropped), while it waits
    first_hour = collections.Counter()
    booked_at_night = {}  # day -> (booked gigs at 00:00, of them due that day)
    for e in d["events"]:
        k, at = e["kind"], e["at"]
        day = at // DAY
        while (len(booked_at_night)) <= day and len(booked_at_night) < 5:  # the gigs a driver holds as each night starts
            n = len(booked_at_night)
            mine = [g for g, h in held.items() if g in one]
            booked_at_night[n] = (len(mine), sum(orders[one[g]]["last"] // DAY == n for g in mine if one[g] in orders))
        if k == "order_won":
            o = e["order"]
            if len(o["legs"]) == 1:
                leg = o["legs"][0]
                orders[o["id"]] = {"won": at, "last": o["lastPickupAt"], "near": notified[leg["pickup"]["placeId"]], "premium": leg["car"]["premium"],
                                   "drops": 0, "delivered": None, "cancelled": False}
                open_at[o["id"]] = at
        elif k == "order_changed" and e["order"]["id"] in orders:
            orders[e["order"]["id"]]["last"] = e["order"]["lastPickupAt"]
        elif k == "order_cancelled" and e["orderId"] in orders:
            orders[e["orderId"]]["cancelled"] = True
            open_at.pop(e["orderId"], None)
        elif k == "gig_booked" and e["gigId"] in one:
            held[e["gigId"]] = (at, e["driverId"])
            oid = one[e["gigId"]]
            if oid in open_at:
                start = open_at.pop(oid)
                for dr in drops:
                    if dr["order"] == oid and dr["rebooked"] is None:
                        dr["rebooked"] = at - dr["at"]
        elif k in ("gig_dropped", "no_show") and e["gigId"] in one:
            oid = one[e["gigId"]]
            since, driver = held.pop(e["gigId"], (None, e["driverId"]))
            if since is not None:
                bookings.append({"from": since, "to": at, "end": k, "record": record.get(driver, 0), "last": orders.get(oid, {}).get("last")})
            if at % DAY < HOUR:
                first_hour[day] += 1
            if oid in orders:
                o = orders[oid]
                o["drops"] += 1
                waiting = len(open_at)
                open_at[oid] = at
                drops.append({"order": oid, "at": at, "kind": k, "left": o["last"] - at, "near": o["near"], "premium": o["premium"], "waiting": waiting,
                              "night": at % DAY < HOUR, "rebooked": None, "record": record.get(driver, 0)})
        elif k == "gig_started" and e["gigId"] in one:
            since, driver = held.pop(e["gigId"], (None, None))
            if since is not None:
                bookings.append({"from": since, "to": at, "end": "started", "record": record.get(driver, 0), "last": orders.get(one[e["gigId"]], {}).get("last")})
        elif k == "delivered" and e["orderId"] in orders:
            orders[e["orderId"]]["delivered"] = at
        elif k == "ledger" and e["line"]["kind"] in ("late_refund", "undelivered_penalty") and e["line"]["orderId"]:
            late.add(e["line"]["orderId"])
    for dr in drops:
        o = orders[dr["order"]]
        dr["late"] = dr["order"] in late or (o["delivered"] is None and not o["cancelled"])
        dr["cancelled"] = o["cancelled"]
    for o_id, o in orders.items():
        o["late"] = o_id in late or (o["delivered"] is None and not o["cancelled"])
    score = d["score"].get("score", d["score"])
    return {"seed": d["seed"], "drivers": len(d["roster"]), "record": collections.Counter(min(r.get("drops", 0), 5) for r in d["roster"]),
            "first_hour": dict(first_hour), "night": booked_at_night, "bookings": bookings, "drops": drops,
            "orders": [{k: o[k] for k in ("won", "last", "near", "premium", "drops", "late", "cancelled")} for o in orders.values()],
            "on_time": score["onTimeShare"], "won": score["wonOrders"]}


def rows(variants: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for v in variants:
        folder = data_dir() / "runs" / v
        paths = sorted(str(p) for p in folder.glob("*-L8.json.gz"))
        with Pool(2) as pool:
            weeks = [w for w in pool.imap(week, paths, chunksize=4) if w]
        pickle.dump(weeks, open(OUT / f"{v}.pkl", "wb"))
        print(f"{v}: {len(weeks)} weeks", flush=True)


def report() -> None:
    bases = {p.stem: pickle.load(open(p, "rb")) for p in sorted(OUT.glob("*.pkl"))}
    for name, weeks in bases.items():
        print(f"\n=== {name}: {len(weeks)} weeks")
        n = len(weeks)
        # 1. waves: per night, drops of the desk's gigs in the first hour against the gigs a driver held as it started
        nights = [(w["seed"], day, w["first_hour"].get(day, 0), *w["night"].get(day, (0, 0))) for w in weeks for day in range(1, 5)]
        wave = [x for x in nights if x[2] >= WAVE]
        calm = [x for x in nights if x[2] < WAVE]
        print(f"waves: {len(wave)} nights in {n} weeks ({len({x[0] for x in wave}) / n:.1%} of weeks); by weekday Tue-Fri {[sum(x[1] == d for x in wave) for d in range(1, 5)]};"
              f" weeks with two: {sum(c >= 2 for c in collections.Counter(x[0] for x in wave).values())}")
        for label, xs in (("calm", calm), ("wave", wave)):
            if not xs:
                continue
            drops, held, due = (np.array([x[i] for x in xs], float) for i in (2, 3, 4))
            share = drops / np.maximum(held, 1)
            print(f"  {label} nights: first-hour drops mean {drops.mean():.2f} (q50 {np.median(drops):.0f}, q90 {np.quantile(drops, .9):.0f}, max {drops.max():.0f});"
                  f" gigs held at 00:00 {held.mean():.1f}, due that day {due.mean():.1f}; share dropped {drops.sum() / held.sum():.3f}"
                  f" (q10 {np.quantile(share, .1):.3f} q50 {np.median(share):.3f} q90 {np.quantile(share, .9):.3f})")
        if len(wave) > 5:
            drops, held = (np.array([x[i] for x in wave], float) for i in (2, 3))
            print(f"  wave drops against held: corr {np.corrcoef(drops, held)[0, 1]:.2f}; slope through 0 {drops @ held / (held @ held):.3f}")
        # 2. normal drops: hazard per held hour, outside the first hours of the nights
        b = [x for w in weeks for x in w["bookings"]]
        hours = sum((x["to"] - x["from"]) / HOUR for x in b)
        night_drops = sum(x["end"] != "started" and x["to"] % DAY < HOUR for x in b)
        other = sum(x["end"] == "gig_dropped" and x["to"] % DAY >= HOUR for x in b)
        noshow = sum(x["end"] == "no_show" for x in b)
        print(f"bookings: {len(b) / n:.0f} a week, held {hours / max(1, len(b)):.1f} h on average; ended in a drop {sum(x['end'] != 'started' for x in b) / len(b):.3f}"
              f" (first hour of a night {night_drops / len(b):.3f}, other drops {other / len(b):.3f}, no-show {noshow / len(b):.3f});"
              f" outside the nights' first hour {other / hours * 24:.4f} drops a held day")
        by_rec = collections.defaultdict(lambda: [0, 0, 0.0])
        for x in b:
            c = by_rec[min(x["record"], 3)]
            c[0] += 1; c[1] += x["end"] == "gig_dropped" and x["to"] % DAY >= HOUR; c[2] += (x["to"] - x["from"]) / HOUR
        print("  other drops a held day by the driver's drop record (0,1,2,3+): " + "  ".join(f"{r}: {c[1] / c[2] * 24:.4f} (n={c[0]})" for r, c in sorted(by_rec.items())))
        noshow_rec = collections.defaultdict(lambda: [0, 0])
        for x in b:
            noshow_rec[min(x["record"], 3)][0] += 1; noshow_rec[min(x["record"], 3)][1] += x["end"] == "no_show"
        print("  no-show a booking by the driver's record: " + "  ".join(f"{r}: {c[1] / c[0]:.4f}" for r, c in sorted(noshow_rec.items())))
        # 3. after a drop: re-booked in time?
        dr = [x for w in weeks for x in w["drops"] if not x["cancelled"]]
        wave_nights = {(w["seed"], day) for w in weeks for day, c in w["first_hour"].items() if c >= WAVE}
        for x, w in ((x, w) for w in weeks for x in w["drops"]):
            x["wave"] = (w["seed"], x["at"] // DAY) in wave_nights and x["night"]
        print(f"drops: {len(dr) / n:.1f} a week; late after a drop {np.mean([x['late'] for x in dr]):.3f}; never re-booked {np.mean([x['rebooked'] is None for x in dr]):.3f};"
              f" minutes to re-book q50/q90 {np.quantile([x['rebooked'] for x in dr if x['rebooked'] is not None], [.5, .9]).round(0)}")
        bands = [(-99, 2), (2, 4), (4, 8), (8, 16), (16, 30), (30, 999)]
        for label, keep in (("calm", lambda x: not x["wave"]), ("wave night", lambda x: x["wave"])):
            xs = [x for x in dr if keep(x)]
            print(f"  {label}: {len(xs)} drops; late by hours left at the drop: " + "  ".join(
                f"{a}-{b}h {np.mean([x['late'] for x in xs if a <= x['left'] / 60 < b]):.2f} (n={sum(a <= x['left'] / 60 < b for x in xs)})" for a, b in bands))
        for lo, hi in ((0, 20), (20, 60), (60, 150), (150, 9999)):
            xs = [x for x in dr if lo <= x["near"] < hi]
            print(f"  drivers notified {lo}-{hi}: late by hours left " + "  ".join(
                f"{a}-{b}h {np.mean([x['late'] for x in xs if a <= x['left'] / 60 < b]) if any(a <= x['left'] / 60 < b for x in xs) else float('nan'):.2f}"
                f"({sum(a <= x['left'] / 60 < b for x in xs)})" for a, b in bands))
        for lo, hi in ((0, 5), (5, 15), (15, 30), (30, 999)):
            xs = [x for x in dr if lo <= x["waiting"] < hi]
            print(f"  cars waiting at the drop {lo}-{hi}: late by hours left " + "  ".join(
                f"{a}-{b}h {np.mean([x['late'] for x in xs if a <= x['left'] / 60 < b]) if any(a <= x['left'] / 60 < b for x in xs) else float('nan'):.2f}"
                f"({sum(a <= x['left'] / 60 < b for x in xs)})" for a, b in bands))
        # 4. late share of orders with and without a drop
        o = [x for w in weeks for x in w["orders"] if not x["cancelled"]]
        print(f"orders: {len(o) / n:.0f} a week; late {np.mean([x['late'] for x in o]):.3f}; with a drop {np.mean([x['drops'] > 0 for x in o]):.3f},"
              f" of them late {np.mean([x['late'] for x in o if x['drops']]):.3f}, without {np.mean([x['late'] for x in o if not x['drops']]):.3f};"
              f" late orders with a drop: {sum(x['late'] and x['drops'] > 0 for x in o) / max(1, sum(x['late'] for x in o)):.2f}")
        rec = sum((w["record"] for w in weeks), collections.Counter())
        print(f"roster drop record 0..5+: {[round(rec[i] / sum(rec.values()), 3) for i in range(6)]}")


if __name__ == "__main__":
    if sys.argv[1] == "rows":
        rows(sys.argv[2].split(","))
    else:
        report()
