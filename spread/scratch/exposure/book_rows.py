"""Scratch: the desk's book, replayed from saved weeks, for the exposure spec's fits and calibration checks.

Per saved week of each variant, from its events: a row for every one-car order at its win and at every drop of its gig (its features,
its due day, the hours from that minute to its last pickup, the cars without a driver due the same day and on other days, and whether it ended
late); and the book at 01:00 and 20:00 of every day (each car still to deliver: due day, held or not, hours left, picked up or not), with the
week's nights so far (held cars due that day as the night began, and drops in its first hour) and the orders resolved and late.

    PYTHONPATH=. uv run --with numpy python scratch/exposure/book_rows.py slow-friday-late-150-kinds-limits,steep-notes-offers-8,thin-premium-0.4

writes data/exposure/book-<variant>.pkl.
"""
from __future__ import annotations

import gzip
import json
import pickle
import sys
from multiprocessing import Pool

from spreadlab.server import data_dir, drivers_near, near_places

DAY, HOUR = 1440, 60
MAP = json.loads((data_dir() / "map.json").read_text())
NEAR = near_places(MAP)
MINUTES = {(r["from"], r["to"]): r["minutes"] for r in MAP["roads"]}


def week(path: str) -> dict | None:
    d = json.load(gzip.open(path))
    if not d["events"]:
        return None
    notified = drivers_near(d["roster"], NEAR)
    drivers = len(d["roster"])
    requests = {r["request"]["id"]: r["request"] for r in d["reveal"]["requests"]}
    one = {g["id"]: g["stops"][0]["orderId"] for g in d["gigs"] if len({s["orderId"] for s in g["stops"]}) == 1}
    cars, rows, snaps, late = {}, [], [], set()
    nights = {}  # day -> [held cars due that day as the night began, drops in its first hour]
    resolved = [0, 0]
    marks = sorted([(day * DAY + 60, day) for day in range(7)] + [(day * DAY + 20 * HOUR, day) for day in range(7)])

    def waiting(now, due, but=None):
        same = sum(1 for oid, c in cars.items() if not c["held"] and c["due"] == due and oid != but)
        return same, sum(1 for oid, c in cars.items() if not c["held"] and c["due"] != due and oid != but)

    def row(oid, now, dropped):
        c = cars[oid]
        same, other = waiting(now, c["due"], oid)
        rows.append({"order": oid, "at": now, "due": c["due"], "hours": (c["last"] - now) / HOUR, "dropped": dropped, "same": same, "other": other, **c["feats"]})

    def snap(now):
        snaps.append({"at": now, "cars": [(oid, c["due"], c["held"], (c["last"] - now) / HOUR, c["picked"]) for oid, c in cars.items()],
                      "nights": {k: tuple(v) for k, v in nights.items()}, "resolved": resolved[0], "late": resolved[1]})

    for e in d["events"]:
        at, k = e["at"], e["kind"]
        while marks and marks[0][0] <= at:
            snap(marks.pop(0)[0])
        if at // DAY not in nights and at % DAY < HOUR:
            day = at // DAY
            nights[day] = [sum(1 for c in cars.values() if c["held"] and c["due"] == day), 0]
        if k == "order_won" and len(e["order"]["legs"]) == 1:
            o = e["order"]
            q = requests[o["id"]]
            leg = q["legs"][0]
            drive = MINUTES[(leg["pickup"]["placeId"], leg["delivery"]["placeId"])]
            cars[o["id"]] = {"last": o["lastPickupAt"], "due": o["lastPickupAt"] // DAY, "held": False, "picked": False,
                             "feats": {"notified": notified[leg["pickup"]["placeId"]], "at_delivery": notified[leg["delivery"]["placeId"]],
                                       "last": o["lastPickupAt"], "premium": leg["car"]["premium"], "drive": drive,
                                       "note": q["note"] is not None, "drivers": drivers, "option": o["option"]}}
            row(o["id"], at, False)
        elif k == "order_changed" and e["order"]["id"] in cars:
            cars[e["order"]["id"]]["last"] = e["order"]["lastPickupAt"]
            cars[e["order"]["id"]]["due"] = e["order"]["lastPickupAt"] // DAY
        elif k == "gig_booked" and one.get(e["gigId"]) in cars:
            cars[one[e["gigId"]]]["held"] = True
        elif k in ("gig_dropped", "no_show") and one.get(e["gigId"]) in cars:
            oid = one[e["gigId"]]
            if at % DAY < HOUR and cars[oid]["due"] == at // DAY and at // DAY in nights:
                nights[at // DAY][1] += 1
            cars[oid]["held"] = False
            row(oid, at, True)
        elif k == "picked_up" and e["orderId"] in cars:
            cars[e["orderId"]]["picked"] = True
        elif k == "visit_failed" and e["orderId"] in cars:
            cars[e["orderId"]]["held"] = False
        elif k in ("delivered", "order_cancelled") and e["orderId"] in cars:
            cars.pop(e["orderId"])
            resolved[0] += 1
        elif k == "ledger" and e["line"]["kind"] in ("late_refund", "undelivered_penalty") and e["line"]["orderId"]:
            if e["line"]["orderId"] not in late:
                late.add(e["line"]["orderId"])
                resolved[1] += 1
    cancelled = {e["orderId"] for e in d["events"] if e["kind"] == "order_cancelled"}
    delivered = {e["orderId"] for e in d["events"] if e["kind"] == "delivered"}
    won = {e["order"]["id"]: e["order"]["lastPickupAt"] for e in d["events"] if e["kind"] == "order_won" and len(e["order"]["legs"]) == 1}
    fate = {oid: oid in late or (oid not in delivered and oid not in cancelled) for oid in won if oid not in cancelled}
    for r in rows:
        r["late"] = fate.get(r["order"])
    first_hour = {}
    for e in d["events"]:
        if e["kind"] in ("gig_dropped", "no_show") and e["at"] % DAY < HOUR and e["gigId"] in one:
            first_hour[e["at"] // DAY] = first_hour.get(e["at"] // DAY, 0) + 1
    score = d["score"].get("score", d["score"])
    return {"seed": d["seed"], "drivers": drivers, "rows": [r for r in rows if r["late"] is not None], "snaps": snaps, "fate": fate,
            "due": {oid: last // DAY for oid, last in won.items()}, "first_hour": first_hour, "on_time": score["onTimeShare"], "won": score["wonOrders"]}


def main() -> None:
    out = data_dir() / "exposure"
    out.mkdir(parents=True, exist_ok=True)
    for v in sys.argv[1].split(","):
        paths = sorted(str(p) for p in (data_dir() / "runs" / v).glob("*-L8.json.gz"))
        with Pool(2) as pool:
            weeks = [w for w in pool.imap(week, paths, chunksize=4) if w]
        pickle.dump(weeks, open(out / f"book-{v}.pkl", "wb"))
        print(f"{v}: {len(weeks)} weeks, {sum(len(w['rows']) for w in weeks)} rows", flush=True)


if __name__ == "__main__":
    main()
