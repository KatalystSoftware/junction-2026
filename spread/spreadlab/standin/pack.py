"""Packs saved weeks for the stand-in: one small file a played week, and one a seed for what every team sees of it.

    python -m spreadlab.standin.pack [--variants a,b,...] [--limit n] [--jobs n] [--newer 2026-11-14T11:39]

A world file (`standin/worlds/<seed>.json.gz`) holds the seed's requests and driver list, which are the same whatever the
desk does. A week file (`standin/weeks/<variant>/<seed>.json.gz`) holds what that desk's week showed: its quotes and
their answers, its orders with what was true of them, and each gig with its views, bookings, drops and drives. The
stand-in is fitted on week files and plays on world files, so neither step needs the full recordings or the team key.
"""
from __future__ import annotations

import argparse
import calendar
import gzip
import json
import os
import time
from multiprocessing import Pool
from pathlib import Path

from ..server import data_dir, read_json_gz, write_json_gz


def root() -> Path:
    return Path(os.environ.get("STANDIN_DATA") or data_dir() / "standin")


def world_path(seed: str) -> Path:
    return root() / "worlds" / f"{seed}.json.gz"


def week_path(variant: str, seed: str) -> Path:
    return root() / "weeks" / variant / f"{seed}.json.gz"


def load_world(seed: str) -> dict:
    return read_json_gz(world_path(seed))


def load_week(variant: str, seed: str) -> dict:
    return read_json_gz(week_path(variant, seed))


def pack(run: dict) -> tuple[dict, dict]:
    """The world and the week of one recorded run."""
    reveal, events = run["reveal"], run["events"]
    world = {"seed": run["seed"], "level": run["level"], "requests": [r["request"] for r in reveal["requests"]], "roster": run["roster"],
             "forecasts": [e for e in events if e["kind"] == "forecast"]}
    gigs = {g["id"]: {"id": g["id"], "postedAt": g["postedAt"], "stops": g["stops"], "audience": g["audience"], "schedule": g["schedule"], "status": g["status"],
                      "views": [], "booked": [], "dropped": [], "started": None, "expired": None, "picked": [], "delivered": [], "failed": [], "offers": []}
            for g in run["gigs"]}
    orders, ledger, late = {}, [], set()
    for e in events:
        kind, gig = e["kind"], gigs.get(e.get("gigId", ""))
        if kind == "order_won":
            o = e["order"]
            orders[o["id"]] = {"wonAt": e["at"], "option": o["option"], "price": o["priceCents"], "deadline": o["deadline"], "lastPickupAt": o["lastPickupAt"],
                               "windows": [[leg["pickup"]["window"], leg["delivery"]["window"]] for leg in o["legs"]], "cancelled": None, "changed": []}
        elif kind == "order_changed" and e["order"]["id"] in orders:
            o = e["order"]
            orders[o["id"]]["changed"].append({"at": e["at"], "deadline": o["deadline"], "lastPickupAt": o["lastPickupAt"],
                                               "places": [[leg["pickup"]["placeId"], leg["delivery"]["placeId"]] for leg in o["legs"]]})
        elif kind == "order_cancelled" and e["orderId"] in orders:
            orders[e["orderId"]]["cancelled"] = e["at"]
        elif kind == "ledger":
            line = e["line"]
            ledger.append([line["at"], line["kind"], line["cents"], line["orderId"], line["gigId"]])
            if line["kind"] in ("late_refund", "undelivered_penalty") and line["orderId"]:
                late.add(line["orderId"])
        elif kind == "deadline_close" and e["orderId"] in orders:
            orders[e["orderId"]].setdefault("warned", []).append(e["at"])
        elif gig is None:
            continue
        elif kind == "gig_viewed":
            pass  # the reveal's views carry the fee
        elif kind == "gig_booked":
            gig["booked"].append([e["at"], e["driverId"], e["feeCents"]])
        elif kind in ("gig_dropped", "no_show"):
            gig["dropped"].append([e["at"], e["driverId"], kind])
        elif kind == "gig_started":
            gig["started"] = e["at"]
        elif kind == "gig_expired":
            gig["expired"] = e["at"]
        elif kind == "picked_up":
            gig["picked"].append([e["at"], e["orderId"], e["leg"]])
        elif kind == "delivered":
            gig["delivered"].append([e["at"], e["orderId"], e["leg"]])
        elif kind == "visit_failed":
            gig["failed"].append([e["at"], e["orderId"], e["leg"], e["reason"]])
        elif kind == "offer_answered":
            gig["offers"].append([e["at"], e["driverId"], e["answer"]])
        elif kind == "driver_late":
            gig.setdefault("late", []).append([e["at"], e.get("pickupAt")])
    for v in reveal["views"]:
        if v["gigId"] in gigs:
            gigs[v["gigId"]]["views"].append([v["at"], v["driverId"], v["feeCents"]])
    for truth in reveal["orders"]:
        if truth["orderId"] in orders:
            orders[truth["orderId"]]["legs"] = truth["legs"]
    for oid in late:
        if oid in orders:
            orders[oid]["late"] = True
    score = run["score"]
    week = {"seed": run["seed"], "variant": run["variant"], "drivers": len(run["roster"]), "fingerprint": run.get("fingerprint"), "params": run.get("params"),
            "score": {"margin": score["marginCents"], "orders": score["wonOrders"], "on_time": score["onTimeShare"]},
            "quotes": {r["request"]["id"]: [r["quote"], r["outcome"], r["option"]] for r in reveal["requests"]},
            "declined": {rid: d["declined"] for rid, d in run["decisions"].items() if d.get("declined")},
            "orders": orders, "gigs": list(gigs.values()), "ledger": ledger}
    return world, week


def pack_file(path: str) -> str:
    variant, seed = Path(path).parent.name, Path(path).name.split("-L")[0]
    out = week_path(variant, seed)
    if out.exists():
        return ""
    try:
        world, week = pack(read_json_gz(Path(path)))
    except Exception as error:  # a week saved by older code, or cut short
        return f"{path}: {error!r}"
    if not world_path(seed).exists():
        write_json_gz(world_path(seed), world)
    write_json_gz(out, week)
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variants", default="", help="comma-separated; all when empty")
    parser.add_argument("--limit", type=int, default=0, help="at most this many weeks a variant")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--newer", default="", help="only recordings written after this UTC time, as 2026-11-14T11:39")
    args = parser.parse_args()
    after = calendar.timegm(time.strptime(args.newer, "%Y-%m-%dT%H:%M")) if args.newer else 0
    names = [v for v in args.variants.split(",") if v] or sorted(p.name for p in (data_dir() / "runs").iterdir())
    files = []
    for name in names:
        found = sorted(f for f in (data_dir() / "runs" / name).glob("*-L8.json.gz") if f.stat().st_mtime > after)
        files += [str(f) for f in (found[: args.limit] if args.limit else found)]
    with Pool(args.jobs) as pool:
        for n, error in enumerate(pool.imap_unordered(pack_file, files, chunksize=4)):
            if error:
                print(error, flush=True)
            if n % 200 == 0:
                print(f"{n} of {len(files)}", flush=True)


if __name__ == "__main__":
    main()
