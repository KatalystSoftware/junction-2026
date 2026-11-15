"""Fits the stand-in's drivers on packed weeks (pack.py) and writes the weights the world plays with.

    python -m spreadlab.standin.fit --out weights.json [--variants a,b] [--limit n] [--hold-out fresh-13,fresh-14] [--drop "ln crowd,rise left"] [--jobs n]

What is fitted, all from what a played week shows:
- the chance a minute that an open gig is booked in the app (model.py), a Poisson regression over the slices of every gig;
- who books: the share of bookings by where the driver lives against the car's two ends;
- drops: in the hour after a booking, an hour of the day while a driver holds a gig, and in the first hour of the day the
  car is due, on an ordinary night and on a wave night (8 or more of the desk's gigs dropped in that hour);
- when a booked driver collects the car inside the time they have, and how long the drive takes against the map;
- direct offers: the share accepted by the offer's fee and where the driver lives;
- which option a dealer takes from each menu of quoted options.

`--hold-out` keeps the weeks of seeds with these prefixes out of the fit, for the checks in validate.py.
"""
from __future__ import annotations

import argparse
import bisect
import collections
import json
import math
import random
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from ..server import near_places, world_map
from . import model
from .pack import load_week, load_world, root

DAY, HOUR = 1440, 60
WAVE = 8  # drops of the desk's gigs in a day's first hour that make it a wave night
GEO: dict = {}


def geo() -> dict:
    if not GEO:
        map_ = world_map()
        GEO.update(minutes={(r["from"], r["to"]): r["minutes"] for r in map_["roads"]}, near=near_places(map_))
    return GEO


def home_class(home: str, pickup: str, delivery: str, near: dict) -> str:
    return "delivery" if home == delivery else "near delivery" if home in near[delivery] else "pickup" if home == pickup else "near pickup" if home in near[pickup] else "far"


def gig_static(world_requests: dict, homes: collections.Counter, drivers: int, gig: dict, minutes: dict, near: dict) -> dict | None:
    """What model.static wants for a gig, and its places; None for a gig whose orders the world file lacks."""
    pickups = [s for s in gig["stops"] if s["kind"] == "pickup"]
    reqs = [world_requests.get(s["orderId"]) for s in pickups]
    if not pickups or any(r is None for r in reqs):
        return None
    legs = [r["legs"][s["leg"]] for r, s in zip(reqs, pickups)]
    first, last = legs[0]["pickup"]["placeId"], legs[-1]["delivery"]["placeId"]
    drive = sum(minutes[(leg["pickup"]["placeId"], leg["delivery"]["placeId"])] for leg in legs)
    ref = sum(r["referenceFeeCents"] / len(r["legs"]) for r in reqs)
    return {"notified": sum(homes[p] for p in near[first]), "at_delivery": sum(homes[p] for p in near[last]), "drivers": drivers, "drive": drive,
            "experienced": gig["audience"]["experienced"], "manual": gig["audience"]["manualLicence"], "cars": len(pickups),
            "private": any(leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"] for leg in legs), "pickup": first, "delivery": last, "ref": ref,
            "ready": legs[0]["pickup"]["window"]["from"], "orders": list(dict.fromkeys(s["orderId"] for s in pickups))}


def wave_days(week: dict) -> dict[int, int]:
    """day -> the desk's gigs dropped in its first hour."""
    night = collections.Counter()
    for gig in week["gigs"]:
        for at, _, kind in gig["dropped"]:
            if kind == "gig_dropped" and at % DAY < HOUR:
                night[at // DAY] += 1
    return dict(night)


def week_rows(job: tuple[str, str]) -> dict:
    """One week's rows for every fit."""
    variant, seed = job
    week, world = load_week(variant, seed), load_world(seed)
    g = geo()
    minutes, near = g["minutes"], g["near"]
    requests = {r["id"]: r for r in world["requests"]}
    home = {d["id"]: d["homePlaceId"] for d in world["roster"]}
    homes = collections.Counter(home.values())
    orders, params = week["orders"], week.get("params") or {}
    night = wave_days(week)
    waves = {d for d, n in night.items() if n >= WAVE}
    first_post: dict = {}  # (order, leg) -> the minute of its first gig
    later: dict = collections.defaultdict(list)  # (order, leg) -> the minutes its gigs were posted
    gigs = sorted(week["gigs"], key=lambda x: x["postedAt"])
    for gig in gigs:
        for s in gig["stops"]:
            if s["kind"] == "pickup":
                first_post.setdefault((s["orderId"], s["leg"]), gig["postedAt"])
                later[(s["orderId"], s["leg"])].append(gig["postedAt"])
    # The stretches each gig was open, for the crowd around a pickup.
    spans, statics = {}, {}
    for gig in gigs:
        st = gig_static(requests, homes, week["drivers"], gig, minutes, near)
        if st is None or any(o not in orders for o in st["orders"]):
            continue
        statics[gig["id"]] = st
        opened, out, booked, dropped = gig["postedAt"], [], sorted(gig["booked"]), sorted(gig["dropped"])
        offers = {(at, driver) for at, driver, answer in gig["offers"] if answer == "accepted"}
        for at, driver, fee in booked:
            if opened is None:
                continue
            out.append((opened, at, "offer" if (at, driver) in offers else "booked", driver, fee))
            opened = next((d[0] for d in dropped if d[0] >= at), None)
        if opened is not None:
            cars = [(s["orderId"], s["leg"]) for s in gig["stops"] if s["kind"] == "pickup"]
            ends = [gig["expired"]] + [t for car in cars for t in later[car] if t > gig["postedAt"]] + [orders[o]["cancelled"] for o in st["orders"]]
            ends = [t for t in ends if t is not None and t >= opened]
            views = [v[0] for v in gig["views"] if v[0] >= opened]
            end = min(ends) if ends else (max(views) if views else opened) if gig["status"] in ("withdrawn", "open") else None
            if end is not None and end > opened:
                out.append((opened, end, "left", None, None))
        spans[gig["id"]] = out
    by_place = collections.defaultdict(lambda: ([], []))
    for gid, out in spans.items():
        for opened, end, *_ in out:
            for place in near[statics[gid]["pickup"]]:
                by_place[place][0].append(opened); by_place[place][1].append(end)
    for starts, ends in by_place.values():
        starts.sort(); ends.sort()

    X, expo, y, unit, who, leads, drives, drops, offers_out, menus = [], [], [], [], collections.Counter(), [], [], collections.Counter(), [], collections.Counter()
    rng = random.Random(seed + variant)
    for gig in gigs:
        st, out = statics.get(gig["id"]), spans.get(gig["id"])
        if st is None:
            continue
        static, views = model.static(st), sorted(gig["views"])
        view_at = [v[0] for v in views]
        order = orders[st["orders"][0]]
        last_pickup = min(orders[o]["lastPickupAt"] for o in st["orders"])
        top = max(s["feeCents"] for s in gig["schedule"])
        steps = [s["at"] for s in gig["schedule"]]
        first = min(first_post[(s["orderId"], s["leg"])] for s in gig["stops"] if s["kind"] == "pickup")
        starts, ends = by_place[st["pickup"]]

        def fee_now(minute: int) -> int:
            k = bisect.bisect_right(view_at, minute) - 1
            return views[k][2] if k >= 0 else model.fee_at(gig["schedule"], minute)

        for n, (opened, end, how, driver, fee) in enumerate(out):
            cuts = model.edges(opened, opened, end, steps) + [end]
            bounded = gig["postedAt"] <= last_pickup  # its stops end with the order's windows: no driver can book it once the last pickup has passed
            for a, b in zip(cuts, cuts[1:]):
                if bounded and a + 30 > last_pickup and not (b == end and how == "booked"):
                    continue
                crowd = bisect.bisect_right(starts, a) - bisect.bisect_right(ends, a) - 1
                X.append(model.features(static, a, opened, first, fee_now(a), top, st["ref"], last_pickup, st["ready"], n > 0, n == 0 and gig["postedAt"] > first,
                                        max(0, crowd), a // DAY in waves))
                expo.append(b - a)
                y.append(1.0 if b == end and how == "booked" else 0.0)
                unit.append(a)
            if how in ("booked", "offer") and driver in home:
                who[(how, home_class(home[driver], st["pickup"], st["delivery"], near))] += 1
            if how in ("booked", "offer"):
                # What the driver did with the booking: dropped it, or collected the car.
                drop = next((d for d in sorted(gig["dropped"]) if d[0] >= end), None)
                next_open = out[n + 1][0] if n + 1 < len(out) else None
                held_to = drop[0] if drop and (next_open is None or drop[0] <= next_open) else (gig["picked"][0][0] if gig["picked"] else None)
                if held_to is None:
                    continue
                dropped = drop is not None and held_to == drop[0] and drop[2] == "gig_dropped"
                due_day = held_to // DAY
                ratio = fee / st["ref"]
                band = "low" if ratio < 1.05 else "mid" if ratio < 1.3 else "high"
                # The hour after the booking, then each waking hour, then the first hour of the day it is due.
                drops[("first hour", band, "held")] += 1
                if dropped and held_to - end < HOUR:
                    drops[("first hour", band, "dropped")] += 1
                else:
                    waking = sum(1 for t in range(end + HOUR, held_to, HOUR) if 7 <= t % DAY // HOUR < 23)
                    drops[("hour", band, "held")] += waking
                    for day in range(end // DAY + 1, due_day + 1):
                        kind = ("wave night" if day in waves else "night") + (" due" if day == due_day else " ahead")
                        drops[(kind, band, "held")] += 1
                        if dropped and held_to // DAY == day and held_to % DAY < HOUR:
                            drops[(kind, band, "dropped")] += 1
                    if dropped and held_to % DAY >= HOUR:
                        drops[("hour", band, "dropped")] += 1
                if not dropped and gig["picked"] and gig["started"] is not None:
                    picked = gig["picked"][0][0]
                    earliest = max(end + 30, st["ready"])
                    latest = max(earliest, last_pickup)
                    leads.append((round((latest - earliest) / HOUR, 1), round((picked - earliest) / (latest - earliest), 3) if latest > earliest else None,
                                  picked - earliest, picked - gig["started"], end % DAY // HOUR))
                    if gig["delivered"] and st["cars"] == 1:
                        drives.append(round((gig["delivered"][-1][0] - picked) / max(st["drive"], 10), 3))
        offer_fee = params.get("offer_fee", 1.3)
        for at, driver, answer in gig["offers"]:
            sent = at if answer == "accepted" else at - 10
            if driver in home:
                ratio = max(offer_fee, fee_now(sent) / st["ref"])
                offers_out.append((home_class(home[driver], st["pickup"], st["delivery"], near), round(ratio, 2), sent % DAY // HOUR, answer, (last_pickup - sent) // HOUR))
    for rid, (quote, outcome, option) in week["quotes"].items():
        if outcome == "won" and quote:
            menus[("+".join(sorted(quote)), option)] += 1
    # The world's last pickup against the deadline less the drive, for one-car orders: how the world sets it.
    slack = collections.Counter()
    for oid, o in orders.items():
        r = requests.get(oid)
        if r is not None and len(r["legs"]) == 1 and not o["changed"]:
            leg = r["legs"][0]
            slack[o["deadline"] - minutes[(leg["pickup"]["placeId"], leg["delivery"]["placeId"])] - o["lastPickupAt"]] += 1
    keep = rng.random() < 1.0
    return {"X": np.array(X, dtype=np.float32) if keep else None, "expo": np.array(expo, dtype=np.float32), "y": np.array(y, dtype=np.float32),
            "at": np.array(unit, dtype=np.int64), "who": who, "leads": leads,
            "drives": drives, "drops": drops, "offers": offers_out, "menus": menus, "night": night, "slack": slack, "seed": seed, "variant": variant}


def poisson(X: np.ndarray, expo: np.ndarray, y: np.ndarray, ridge: float = 1.0) -> np.ndarray:
    """Weights of the chance a minute, intercept first: Newton steps on the Poisson log likelihood with a small ridge."""
    X = np.hstack([np.ones((len(X), 1), dtype=np.float64), X.astype(np.float64)])
    beta = np.zeros(X.shape[1])
    beta[0] = math.log(y.sum() / expo.sum())
    penalty = ridge * np.eye(X.shape[1]); penalty[0, 0] = 0
    for _ in range(40):
        mu = expo * np.exp(np.clip(X @ beta, -30, 5))
        step = np.linalg.solve(X.T @ (X * mu[:, None]) + penalty, X.T @ (y - mu) - penalty @ beta)
        beta += np.clip(step, -2, 2)
        if np.abs(step).max() < 1e-6:
            break
    return beta


def quantiles(values: list[float], n: int = 41) -> list[float]:
    values = sorted(values)
    return [round(values[min(len(values) - 1, int(q * (len(values) - 1) / (n - 1) + 0.5))], 3) for q in range(n)] if values else []


def lead_band(hours: float) -> str:
    return "0" if hours <= 0 else "<2" if hours < 2 else "<6" if hours < 6 else "<12" if hours < 12 else "<30" if hours < 30 else "30+"


def offer_band(ratio: float) -> str:
    return "<1.15" if ratio < 1.15 else "<1.45" if ratio < 1.45 else "1.45+"


def jobs_for(variants: list[str], limit: int, hold_out: list[str]) -> list[tuple[str, str]]:
    names = variants or sorted(p.name for p in (root() / "weeks").iterdir())
    jobs = []
    for name in names:
        seeds = sorted(p.name[: -len(".json.gz")] for p in (root() / "weeks" / name).glob("*.json.gz"))
        seeds = [s for s in seeds if not any(s.startswith(h) for h in hold_out)]
        jobs += [(name, s) for s in (seeds[:limit] if limit else seeds)]
    return jobs


def fit(jobs: list[tuple[str, str]], workers: int = 2, drop: list[str] = ()) -> dict:
    with Pool(workers) as pool:
        rows = pool.map(week_rows, jobs, chunksize=4)
    X = np.vstack([r["X"] for r in rows if r["X"] is not None and len(r["X"])])
    expo = np.concatenate([r["expo"] for r in rows if len(r["expo"])]); y = np.concatenate([r["y"] for r in rows if len(r["y"])])
    keep = [i for i, name in enumerate(model.NAMES) if name not in drop]
    beta = poisson(X[:, keep], expo, y)
    weights = dict.fromkeys(model.NAMES, 0.0)
    weights.update({model.NAMES[i]: round(float(b), 5) for i, b in zip(keep, beta[1:])})
    who, drops, menus, slack = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    for r in rows:
        who.update(r["who"]); drops.update(r["drops"]); menus.update(r["menus"]); slack.update(r["slack"])
    leads = collections.defaultdict(list)
    for r in rows:
        for hours, share, minutes_, _, _ in r["leads"]:
            leads[lead_band(hours)].append(minutes_ if share is None else share)
    offers = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        for cls, ratio, hour, answer, _ in r["offers"]:
            for key in ((cls, offer_band(ratio)), ("all", offer_band(ratio))):
                offers[key][0] += 1; offers[key][1] += answer == "accepted"
    rate = lambda kind, band: (drops[(kind, band, "dropped")] + 0.5) / (drops[(kind, band, "held")] + 20)
    kinds = ["first hour", "hour", "night due", "night ahead", "wave night due", "wave night ahead"]
    took = collections.defaultdict(dict)
    for (menu, option), n in menus.items():
        took[menu][option] = n
    return {
        "weeks": len(rows), "slices": int(len(y)), "bookings": int(y.sum()), "intercept": round(float(beta[0]), 5), "weights": weights,
        "who": {how: {cls: n for (h, cls), n in who.items() if h == how} for how in ("booked", "offer")},
        "drops": {kind: {band: round(rate(kind, band), 5) for band in ("low", "mid", "high")} for kind in kinds},
        "drop_counts": {f"{k}|{b}|{w}": n for (k, b, w), n in sorted(drops.items())},
        "leads": {band: quantiles(values) for band, values in leads.items()},
        "drives": quantiles([d for r in rows for d in r["drives"]], 201),
        "offers": {f"{cls}|{band}": [n, round(won / n, 4)] for (cls, band), (n, won) in sorted(offers.items())},
        "took": took, "last_pickup_slack": dict(slack.most_common(6)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True)
    parser.add_argument("--variants", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--hold-out", default="")
    parser.add_argument("--drop", default="", help="comma-separated feature names (model.NAMES) to leave out")
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    split = lambda text: [x for x in text.split(",") if x]
    jobs = jobs_for(split(args.variants), args.limit, split(args.hold_out))
    out = fit(jobs, args.jobs, split(args.drop))
    out["fitted_on"] = {"variants": sorted({v for v, _ in jobs}), "hold_out": split(args.hold_out), "dropped": split(args.drop)}
    Path(args.out).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(f"{out['weeks']} weeks, {out['slices']} slices, {out['bookings']} bookings in the app")
    print(f"intercept {out['intercept']}")
    for name, w in out["weights"].items():
        print(f"  {name:24} {w:+.3f}")
    for key in ("who", "drops", "offers", "last_pickup_slack"):
        print(key, json.dumps(out[key]))


if __name__ == "__main__":
    main()
