"""Scratch: one pass over the saved weeks of a variant for the input audit. Writes, for each week, one JSON file with a
row for each serious quote, each won order, each day and the week, holding the inputs the policy does not use beside
those it does. The analysis scripts in this folder read these files.

    PYTHONPATH=. python scratch/inputs/rows.py --variant steep-notes-offers-8 --out $SPREAD_DATA/inputs

Reads only saved weeks. Plays nothing and needs no team key.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import multiprocessing
import os
from pathlib import Path

from spreadlab import curve, slow
from spreadlab.server import data_dir, drivers_near, near_places

DAY, HOUR = 1440, 60
MODEL = curve.MODELS["day"]
EXPERIENCED = (4.8, 50)
MAP = json.loads((data_dir() / "map.json").read_text())
NEAR = near_places(MAP)
MINUTES = {(r["from"], r["to"]): r["minutes"] for r in MAP["roads"]}


def kind(request) -> str:
    if len(request["legs"]) > 1:
        return "trade_in"
    leg = request["legs"][0]
    return "private_pickup" if leg["pickup"]["privateAddress"] else "private_delivery" if leg["delivery"]["privateAddress"] else ""


KM = {(r["from"], r["to"]): r["km"] for r in MAP["roads"]}


def open_on(day: int, hours: dict | None) -> tuple[int, int] | None:
    """The minutes a site with these stated hours is open on a day; a private address is always open."""
    if hours is None:
        return day * DAY, (day + 1) * DAY
    if day % 7 in hours["weekdays"]:
        return day * DAY + hours["opens"], day * DAY + hours["closes"]
    if day % 7 == 5 and hours.get("saturday"):
        return day * DAY + hours["saturday"]["opens"], day * DAY + hours["saturday"]["closes"]
    return None


def last_open(minute: int, hours: dict | None) -> int:
    """The last minute at or before `minute` when the site is open."""
    for day in range(minute // DAY, minute // DAY - 9, -1):
        span = open_on(day, hours)
        if span and min(minute, span[1] - 1) >= span[0]:
            return min(minute, span[1] - 1)
    return minute


def first_open(minute: int, hours: dict | None) -> int:
    for day in range(minute // DAY, minute // DAY + 9):
        span = open_on(day, hours)
        if span and max(minute, span[0]) < span[1]:
            return max(minute, span[0])
    return minute


def at_quote(q: dict, options: list[dict], roster_n: int, notified: dict, act_near: dict, exp_near: dict, homes: dict, forecasts: list[dict]) -> dict:
    """What a one-leg request says at the quote that the late chance (slow.py) leaves out, for the fastest option quoted."""
    leg, first = q["legs"][0], curve.fastest(options)
    pk, dl = leg["pickup"]["placeId"], leg["delivery"]["placeId"]
    drive = sum(MINUTES[(l["pickup"]["placeId"], l["delivery"]["placeId"])] for l in q["legs"])
    car = leg["car"]
    low = bool(car["electric"] and car["chargePercent"] is not None and car["chargePercent"] < 30)
    road = drive + (40 if low and KM[(pk, dl)] > 200 else 0)
    naive = first["deadline"] - drive
    t = first["deadline"] - road
    for _ in range(6):  # the last pickup minute with the pickup site open and the delivery site open on arrival
        t = last_open(t, leg["pickup"]["hours"])
        arrive = last_open(t + road, leg["delivery"]["hours"])
        if arrive == t + road:
            break
        t = arrive - road
    ready = first_open(max(q["respondBy"], leg["pickup"]["window"]["from"]), leg["pickup"]["hours"])
    note = min(notified[l["pickup"]["placeId"]] for l in q["legs"])
    kinds = [o["kind"] for o in options]
    return {"drive": drive, "notified": note, "prem": any(l["car"]["premium"] for l in q["legs"]), "note": q["note"] is not None, "elec": car["electric"], "low": low,
            "p_slow": round(slow.chance(slow.known(q, first, note, drive, roster_n), slow.MODELS["friday"]), 5),
            "h_naive": round((naive - q["respondBy"]) / HOUR, 2), "h_own": round((t - q["respondBy"]) / HOUR, 2), "ready_in": round(max(0, ready - q["respondBy"]) / HOUR, 2),
            "window": round((t - ready) / HOUR, 2), "own_last": t, "last_dow": t // DAY % 7, "nopt": len(options), "slowest": max(kinds, key=curve.SPEED.index),
            "dl_near": notified[dl], "pk_town": homes.get(pk, 0), "act_near": act_near[pk], "exp_near": exp_near[pk], "batch": q["batchId"] is not None,
            "hour": round(q["arrivedAt"] % DAY / HOUR, 2), "dow": q["arrivedAt"] // DAY % 7,
            "snow": any((pk in f["places"] or dl in f["places"]) and f["at"] <= q["arrivedAt"] and f["from"] < first["deadline"] and f["to"] > q["arrivedAt"] for f in forecasts)}


def week(path: str) -> dict | None:
    try:
        run = json.load(gzip.open(path))
    except Exception:
        return None
    events, roster = run["events"], run["roster"]
    by_id = {d["id"]: d for d in roster}
    notified = drivers_near(roster, NEAR)
    experienced = [d for d in roster if d["rating"] >= EXPERIENCED[0] and d["completedGigs"] >= EXPERIENCED[1]]
    exp_near = drivers_near(experienced, NEAR)
    act_near = drivers_near([d for d in roster if d["completedGigs"] >= 50], NEAR)
    known_forecasts = [{"at": e["at"], "from": e["from"], "to": e["to"], "places": e["placeIds"]} for e in events if e["kind"] == "forecast"]
    homes: dict[str, int] = {}
    for d in roster:
        homes[d["homePlaceId"]] = homes.get(d["homePlaceId"], 0) + 1
    requests = {e["request"]["id"]: e["request"] for e in events if e["kind"] == "price_request"}
    won = {e["order"]["id"]: e for e in events if e["kind"] == "order_won"}
    lost = {e["requestId"]: e for e in events if e["kind"] == "order_lost"}
    lates = {e["line"]["orderId"] for e in events if e["kind"] == "ledger" and e["line"]["kind"] in ("late_refund", "undelivered_penalty")}
    cancelled = {e["orderId"] for e in events if e["kind"] == "order_cancelled"}
    gig_order = {g["id"]: g["stops"][0]["orderId"] for g in run["gigs"]}
    gig_posted = {g["id"]: g["postedAt"] for g in run["gigs"]}
    gigs_of: dict[str, list[dict]] = {}
    for g in run["gigs"]:
        gigs_of.setdefault(g["stops"][0]["orderId"], []).append(g)
    decisions = run.get("decisions", {})

    # The dealer's count of orders on time, as the policy counts it, and the curve's log odds of each serious quote.
    trust: dict[str, int] = {}
    left: dict[str, int] = {}  # order id -> legs not yet delivered
    quotes, per_order = [], {}
    views: dict[str, list[tuple[int, str]]] = {}
    booked: dict[str, list[tuple[int, str, int]]] = {}
    drops: dict[str, list[tuple[int, str]]] = {}
    counts: dict[str, dict[str, int]] = {}
    warn: dict[str, int] = {}
    offers: dict[str, list[tuple[int, str, str]]] = {}
    day_rows: dict[int, dict] = {}
    forecasts, changed_at = [], {}
    batch_n: dict[str, int] = {}
    for q in requests.values():
        if q["batchId"]:
            batch_n[q["batchId"]] = batch_n.get(q["batchId"], 0) + 1
    # Each direct offer's answer, with what the desk knew of the driver when it sent the offer 10 minutes before.
    offer_rows = []
    seen_day: dict[str, tuple[int, int, int]] = {}  # driver -> day, looks that day, the minute of the last look
    answered: dict[str, tuple[int, int, int]] = {}  # driver -> day, offers that expired unread, offers read
    holds: dict[str, int] = {}  # driver -> gigs booked and not dropped so far
    order_of = {o["order"]["id"]: o["order"] for o in won.values()}

    def day_row(day: int) -> dict:
        return day_rows.setdefault(day, {"day": day, "views": [], "posts": 0, "drops": [], "books": [], "offers": {"accepted": 0, "declined": 0, "expired": 0},
                                         "warnings": 0, "late_refunds": 0, "no_show": 0, "driver_late": 0, "expired_gigs": 0})

    for e in events:
        k, at = e["kind"], e["at"]
        if k == "price_request":
            q = e["request"]
            decision = decisions.get(q["id"])
            if decision is None or decision.get("declined") or decision.get("explored"):
                continue
            options = [o for o in q["options"] if o["kind"] in decision["prices"]]
            if not options:
                continue
            first = curve.fastest(options)
            multiple = decision["prices"][first["kind"]] / first["listPriceCents"]
            on_time = trust.get(q["dealerId"], 0)
            z = curve.at_list(q, options, on_time, MODEL) - MODEL["slope"] * math.log(multiple)
            quotes.append({"id": q["id"], "at": q["arrivedAt"], "dealer": q["dealerId"], "pk": q["legs"][0]["pickup"]["placeId"], "dl": q["legs"][0]["delivery"]["placeId"],
                           "z": round(z, 4), "m": round(multiple, 4), "list": first["listPriceCents"], "fee": q["referenceFeeCents"], "trust": on_time,
                           "won": q["id"] in won, "kind": kind(q), "fast": first["kind"], "late": q["id"] in lates, "cancelled": q["id"] in cancelled,
                           "opt": won[q["id"]]["order"]["option"] if q["id"] in won else None,
                           "true_last": won[q["id"]]["order"]["lastPickupAt"] if q["id"] in won else None,
                           **at_quote(q, options, len(roster), notified, act_near, exp_near, homes, known_forecasts)})
        elif k == "order_won":
            left[e["order"]["id"]] = len(e["order"]["legs"])
        elif k == "delivered":
            order_id = e["orderId"]
            if order_id in left:
                left[order_id] -= 1
                if left[order_id] == 0 and order_id not in cancelled:
                    dealer = requests[order_id]["dealerId"]
                    count = trust.get(dealer, 0)
                    trust[dealer] = count // 2 if order_id in lates else min(25, count + 1)
        elif k == "gig_viewed":
            d0 = seen_day.get(e["driverId"], (-1, 0, 0))
            seen_day[e["driverId"]] = (at // DAY, (d0[1] if d0[0] == at // DAY else 0) + 1, at)
            views.setdefault(gig_order.get(e["gigId"], ""), []).append((at, e["driverId"]))
            day_row(at // DAY)["views"].append((at % DAY, e["driverId"]))
        elif k == "gig_booked":
            holds[e["driverId"]] = holds.get(e["driverId"], 0) + 1
            d0 = seen_day.get(e["driverId"], (-1, 0, 0))
            seen_day[e["driverId"]] = (at // DAY, (d0[1] if d0[0] == at // DAY else 0) + 1, at)
            booked.setdefault(gig_order.get(e["gigId"], ""), []).append((at, e["driverId"], e["feeCents"]))
            day_row(at // DAY)["books"].append((at % DAY, at - gig_posted.get(e["gigId"], at)))
        elif k == "gig_dropped":
            drops.setdefault(gig_order.get(e["gigId"], ""), []).append((at, e["driverId"]))
            day_row(at // DAY)["drops"].append(at % DAY)
        elif k in ("no_show", "driver_late", "gig_expired"):
            order_id = gig_order.get(e["gigId"], "")
            c = counts.setdefault(order_id, {})
            c[k] = c.get(k, 0) + 1
            day_row(at // DAY)[{"no_show": "no_show", "driver_late": "driver_late", "gig_expired": "expired_gigs"}[k]] += 1
        elif k == "visit_failed":
            c = counts.setdefault(e["orderId"], {})
            c["failed"] = c.get("failed", 0) + 1
        elif k == "order_changed":
            c = counts.setdefault(e["order"]["id"], {})
            c["changed"] = c.get("changed", 0) + 1
            changed_at.setdefault(e["order"]["id"], at)
        elif k == "deadline_close":
            warn.setdefault(e["orderId"], at)
            day_row(at // DAY)["warnings"] += 1
        elif k == "offer_answered":
            driver, order_id = by_id.get(e["driverId"]), gig_order.get(e["gigId"], "")
            order = order_of.get(order_id)
            if driver is not None and order is not None:
                sent = at - 10 if e["answer"] != "accepted" else at  # an acceptance comes inside the 10 minutes
                d0, a0 = seen_day.get(e["driverId"], (-1, 0, 0)), answered.get(e["driverId"], (-1, 0, 0))
                today = at // DAY
                pk, dl = order["legs"][0]["pickup"]["placeId"], order["legs"][0]["delivery"]["placeId"]
                offer_rows.append({"at": at, "tod": sent % DAY, "day": today, "answer": e["answer"], "driver": e["driverId"], "order": order_id,
                                   "to_pk": MINUTES.get((driver["homePlaceId"], pk), 0), "to_home": MINUTES.get((dl, driver["homePlaceId"]), 0),
                                   "looks_today": d0[1] if d0[0] == today else 0, "since_look": at - d0[2] if d0[0] == today else None,
                                   "unread_today": a0[1] if a0[0] == today else 0, "read_today": a0[2] if a0[0] == today else 0,
                                   "holds": holds.get(e["driverId"], 0), "rating": driver["rating"], "gigs": driver["completedGigs"], "drops": driver["drops"],
                                   "hours_left": (order["lastPickupAt"] - at) / HOUR, "drive": MINUTES.get((pk, dl), 0)})
                a0 = a0 if a0[0] == today else (today, 0, 0)
                answered[e["driverId"]] = (today, a0[1] + (e["answer"] == "expired"), a0[2] + (e["answer"] != "expired"))
            offers.setdefault(gig_order.get(e["gigId"], ""), []).append((at, e["driverId"], e["answer"]))
            day_row(at // DAY)["offers"][e["answer"]] += 1
        elif k == "forecast":
            forecasts.append({"at": at, "from": e["from"], "to": e["to"], "places": e["placeIds"]})
        elif k == "ledger" and e["line"]["kind"] in ("late_refund", "undelivered_penalty"):
            day_row(at // DAY)["late_refunds"] += 1
    for g in run["gigs"]:
        day_row(g["postedAt"] // DAY)["posts"] += 1

    orders = []
    for order_id, e in won.items():
        order, q, at = e["order"], requests[e["order"]["id"]], e["at"]
        leg = q["legs"][0]
        pk, dl = leg["pickup"]["placeId"], leg["delivery"]["placeId"]
        drive = sum(MINUTES[(l["pickup"]["placeId"], l["delivery"]["placeId"])] for l in q["legs"])
        decision = decisions.get(order_id, {})
        quoted = [o for o in q["options"] if o["kind"] in decision.get("prices", {})] or q["options"]
        fastest = curve.fastest(quoted)
        note = min(notified[l["pickup"]["placeId"]] for l in q["legs"])
        p_slow = slow.chance(slow.known(q, fastest, note, drive, len(roster)), slow.MODELS["friday"])
        v = sorted(views.get(order_id, []))
        b = sorted(booked.get(order_id, []))
        first_post = min((g["postedAt"] for g in gigs_of.get(order_id, [])), default=None)
        first_book = b[0][0] if b else None
        final = by_id.get(b[-1][1]) if b else None
        first = by_id.get(b[0][1]) if b else None

        def looks(minutes: int) -> tuple[int, int]:
            if first_post is None:
                return 0, 0
            inside = [d for t, d in v if t - first_post <= minutes and (first_book is None or t <= first_book)]
            return len(inside), len(set(inside))

        won_opt = next(o for o in q["options"] if o["kind"] == order["option"])
        c = counts.get(order_id, {})
        answers = offers.get(order_id, [])
        orders.append({
            "id": order_id, "at": q["arrivedAt"], "won_at": at, "dealer": q["dealerId"], "batch": q["batchId"] is not None, "batch_n": batch_n.get(q["batchId"], 0), "kind": kind(q),
            "prem": any(l["car"]["premium"] for l in q["legs"]), "elec": leg["car"]["electric"], "charge": leg["car"]["chargePercent"],
            "pk": pk, "dl": dl, "wf": leg["pickup"]["window"]["from"], "wt": leg["pickup"]["window"]["to"],
            "ph": leg["pickup"]["hours"], "dh": leg["delivery"]["hours"], "opt": order["option"], "price": order["priceCents"], "list": won_opt["listPriceCents"],
            "fee": q["referenceFeeCents"], "note": q["note"] is not None, "lang": q["note"]["language"] if q["note"] else None,
            "deadline": order["deadline"], "req_deadline": won_opt["deadline"], "last": order["lastPickupAt"], "fast_deadline": fastest["deadline"], "fast": fastest["kind"],
            "nopt": len(quoted), "drive": drive, "km": 0, "notified": note, "exp_near": min(exp_near[l["pickup"]["placeId"]] for l in q["legs"]),
            "dl_town": homes.get(dl, 0), "dl_near": notified[dl], "pk_town": homes.get(pk, 0), "roster": len(roster), "p_slow": round(p_slow, 4),
            "late": order_id in lates, "cancelled": order_id in cancelled, "changed": c.get("changed", 0), "changed_at": changed_at.get(order_id),
            "post": first_post, "book": first_book, "nbook": len(b), "looks15": looks(15), "looks60": looks(60), "views": len(v),
            "drops": len(drops.get(order_id, [])), "drop_at": [t for t, _ in drops.get(order_id, [])][:3], "driver_late": c.get("driver_late", 0), "no_show": c.get("no_show", 0),
            "failed": c.get("failed", 0), "expired": c.get("gig_expired", 0), "warn": warn.get(order_id),
            "offers": len(answers), "offers_read": sum(1 for _, _, a in answers if a != "expired"), "offers_yes": sum(1 for _, _, a in answers if a == "accepted"),
            "first_driver": ({"rating": first["rating"], "gigs": first["completedGigs"], "drops": first["drops"], "home": first["homePlaceId"]} if first else None),
            "final_driver": ({"rating": final["rating"], "gigs": final["completedGigs"], "drops": final["drops"], "home": final["homePlaceId"]} if final else None),
            "book_fee": b[0][2] if b else None,
        })
    for q in quotes:
        q["won"] = q["id"] in won
    week_row = {"seed": run["seed"], "variant": run["variant"], "score": run["score"], "roster": len(roster), "experienced": len(experienced),
                "manual": sum(1 for d in roster if d["licence"] == "manual"), "drops_mean": sum(d["drops"] for d in roster) / len(roster),
                "drops_any": sum(1 for d in roster if d["drops"] > 0) / len(roster), "gigs_mean": sum(d["completedGigs"] for d in roster) / len(roster),
                "rating_mean": sum(d["rating"] for d in roster) / len(roster), "homes": homes, "gigs50": sum(1 for d in roster if d["completedGigs"] >= 50),
                "gigs150": sum(1 for d in roster if d["completedGigs"] >= 150), "gigs5": sum(1 for d in roster if d["completedGigs"] <= 5),
                "req_notified": [notified[q["legs"][0]["pickup"]["placeId"]] for q in requests.values()],
                "req_active": [act_near[q["legs"][0]["pickup"]["placeId"]] for q in requests.values()], "requests": len(requests), "forecasts": forecasts,
                "batches": sorted({(q["batchId"], q["arrivedAt"] // DAY, q["legs"][0]["pickup"]["placeId"]) for q in requests.values() if q["batchId"]})}
    return {"week": week_row, "quotes": quotes, "orders": orders, "days": [day_rows[d] for d in sorted(day_rows)], "offers": offer_rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default="steep-notes-offers-8")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    paths = sorted(str(p) for p in (data_dir() / "runs" / args.variant).glob("*-L8.json.gz"))
    out = args.out / args.variant
    out.mkdir(parents=True, exist_ok=True)
    done = 0
    with multiprocessing.Pool(max(1, (os.cpu_count() or 2) - 1)) as pool:
        for result in pool.imap_unordered(week, paths, chunksize=4):
            if result is None:
                continue
            (out / f"{result['week']['seed']}.json").write_text(json.dumps(result, separators=(",", ":")))
            done += 1
    print(f"{done} of {len(paths)} weeks of {args.variant} written to {out}")


if __name__ == "__main__":
    main()
