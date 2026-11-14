"""Scratch: what the backlog gate declines, what the cars that fill it look like, and what makes a won car wait
for a driver. From every saved week of one variant; weeks with a short driver list and the others apart.

    PYTHONPATH=. uv run python scratch/gate_report.py --variant steep-notes-offers-8

The desk's backlog is rebuilt from the events: a won car counts while it is not delivered and no driver holds a gig
of its order. "Curve" is the margin the win curve expects from a request at the reference's price without the backlog
surcharge: chance x (price - 1.3 x typical fee), with the dealer's count of orders on time and no correction for the day.
"""
from __future__ import annotations

import argparse
import collections
import statistics

from spreadlab import curve
from spreadlab.play import load_run
from spreadlab.policy import kind
from spreadlab.server import data_dir, drivers_near, near_places, world_map

DAY, HOUR = 1440, 60
MODEL = curve.MODELS["day"]


def band(value: float, edges: list[tuple[float, str]], last: str) -> str:
    return next((name for edge, name in edges if value < edge), last)


SUPPLY = [(1, "0 drivers"), (5, "1-4"), (10, "5-9"), (40, "10-39"), (100, "40-99")]
SLACK = [(6, "under 6 h"), (8, "6-8 h"), (12, "8-12 h"), (24, "12-24 h")]
DRIVE = [(60, "under 1 h"), (120, "1-2 h"), (240, "2-4 h"), (400, "4-6.7 h")]
CLOCK = [(10, "before 10"), (13, "10-13"), (16, "13-16")]
DUE = [(0, "past the last pickup"), (3, "under 3 h"), (8, "3-8 h"), (24, "8-24 h")]
BACKLOG = [(5, "0-4"), (10, "5-9"), (15, "10-14")]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default="steep-notes-offers-8")
    parser.add_argument("--thin", type=int, default=720)
    args = parser.parse_args()
    map_ = world_map()
    near = near_places(map_)
    minutes = {(r["from"], r["to"]): r["minutes"] for r in map_["roads"]}
    seeds = sorted(p.name[:-len("-L8.score.json")] for p in (data_dir() / "runs" / args.variant).glob("*-L8.score.json"))
    weeks = collections.Counter()
    declines = collections.defaultdict(list)                       # group -> declines in each week
    asked = collections.defaultdict(collections.Counter)           # (group, what) -> sums over requests
    blockers = collections.defaultdict(collections.Counter)        # (group, feature, band) -> counts over snapshots
    waits = collections.defaultdict(lambda: collections.defaultdict(list))  # (feature, band) -> lists
    for seed in seeds:
        try:
            run = load_run(args.variant, seed)
        except Exception:  # a week that is being written
            continue
        group = "thin" if len(run["roster"]) < args.thin else "normal"
        weeks[group] += 1
        notified = drivers_near(run["roster"], near)
        order_of = {g["id"]: g["stops"][0]["orderId"] for g in run["gigs"]}
        gigs_of = collections.defaultdict(list)
        for gig, order in order_of.items():
            gigs_of[order].append(gig)
        requests, orders, won_at, open_since = {}, {}, {}, {}
        booked: set[str] = set()
        first_booked, dropped, late, money, trust = {}, collections.Counter(), set(), collections.Counter(), {}
        quoted = {}  # request id -> (backlog, curve margin)
        snapshots = []  # (order ids without a driver, minute) at each decline for backlog
        count = 0
        drive = lambda q: minutes[(q["legs"][0]["pickup"]["placeId"], q["legs"][0]["delivery"]["placeId"])]  # noqa: E731

        def unbooked() -> list[str]:
            return [id_ for id_ in orders if not any(g in booked for g in gigs_of[id_])]

        for event in sorted(run["events"], key=lambda e: e["seq"]):
            what, at = event["kind"], event["at"]
            if what == "price_request":
                q = event["request"]
                requests[q["id"]] = q
                decision = run["decisions"].get(q["id"])
                if decision is None or kind(q) or decision["declined"] not in (None, "backlog"):
                    continue
                waiting = unbooked()
                ready = max(q["respondBy"], q["legs"][0]["pickup"]["window"]["from"])
                options = [o for o in q["options"] if o["deadline"] - drive(q) - ready >= 300]
                if not options:
                    continue
                fee, first = q["referenceFeeCents"], curve.fastest(options)
                at_list = curve.at_list(q, options, trust.get(q["dealerId"], 0), MODEL)
                multiple = curve.best(at_list, 0.0, first["listPriceCents"], fee * 1.3, MODEL["slope"])
                expect = curve.chance(at_list, multiple, 0.0, MODEL["slope"]) * (multiple * first["listPriceCents"] - fee * 1.3)
                slack = (first["deadline"] - drive(q) - ready) / HOUR
                key = (group, "declined for backlog" if decision["declined"] else "quoted, backlog " + band(len(waiting), BACKLOG, "15 or more"))
                row = asked[key]
                row["n"] += 1
                row["curve"] += expect
                row["list"] += first["listPriceCents"] / fee
                row["fee"] += fee
                row["slack"] += slack
                row["short"] += slack < 8
                row["thin town"] += notified[q["legs"][0]["pickup"]["placeId"]] < 10
                row["trust"] += trust.get(q["dealerId"], 0)
                if decision["declined"]:
                    count += 1
                    snapshots.append((waiting, at))
                else:
                    quoted[q["id"]] = key
            elif what == "order_won":
                order = event["order"]
                orders[order["id"]], won_at[order["id"]], open_since[order["id"]] = order, at, at
            elif what == "order_changed" and event["order"]["id"] in orders:
                orders[event["order"]["id"]] = event["order"]
            elif what == "order_cancelled":
                orders.pop(event["orderId"], None)
            elif what == "gig_booked":
                booked.add(event["gigId"])
                first_booked.setdefault(order_of[event["gigId"]], at)
            elif what in ("gig_dropped", "no_show"):
                booked.discard(event["gigId"])
                dropped[order_of[event["gigId"]]] += 1
                open_since[order_of[event["gigId"]]] = at
            elif what == "delivered":
                order = orders.pop(event["orderId"], None)
                if order is not None:
                    dealer = requests[order["id"]]["dealerId"]
                    trust[dealer] = min(25, trust.get(dealer, 0) + 1) if at <= order["deadline"] else trust.get(dealer, 0) // 2
            elif what == "ledger" and event["line"].get("orderId"):
                money[event["line"]["orderId"]] += event["line"]["cents"]
                if event["line"]["kind"] in ("late_refund", "undelivered_penalty"):
                    late.add(event["line"]["orderId"])
        declines[group].append(count)
        for id_, key in quoted.items():
            if id_ in won_at:
                row = asked[key]
                row["won"] += 1
                row["late"] += id_ in late
                row["money"] += money[id_]
        # The cars that filled the gate, at each decline. `open_since` is the last value, so a wait is read from the win.
        last_pickup = {}
        for event in run["events"]:
            if event["kind"] in ("order_won", "order_changed"):
                last_pickup[event["order"]["id"]] = event["order"]["lastPickupAt"]
        for waiting, at in snapshots:
            for id_ in waiting:
                q = requests[id_]
                for feature, name in (("due", band((last_pickup[id_] - at) / HOUR, DUE, "over 24 h")),
                                      ("supply", band(notified[q["legs"][0]["pickup"]["placeId"]], SUPPLY, "100 or more")),
                                      ("drive", band(drive(q), DRIVE, "over 6.7 h")),
                                      ("waiting", band((at - won_at[id_]) / HOUR, [(1, "under 1 h"), (4, "1-4 h"), (12, "4-12 h")], "over 12 h")),
                                      ("was dropped", str(dropped[id_] > 0)), ("premium", str(q["legs"][0]["car"]["premium"])),
                                      ("ends late", str(id_ in late)), ("all", "")):
                    blockers[(group, feature, name)]["n"] += 1
                blockers[(group, "fee", "")]["sum"] += q["referenceFeeCents"]
        # What makes a won car wait.
        for id_, at in won_at.items():
            q = requests[id_]
            if kind(q) or id_ not in last_pickup:
                continue
            wait = first_booked.get(id_, 10 ** 6) - at
            for feature, name in (("supply", band(notified[q["legs"][0]["pickup"]["placeId"]], SUPPLY, "100 or more")),
                                  ("hours to the last pickup", band((last_pickup[id_] - at) / HOUR, SLACK, "over 24 h")),
                                  ("drive", band(drive(q), DRIVE, "over 6.7 h")),
                                  ("won at", band(at % DAY / HOUR, CLOCK, "16 or later")),
                                  ("day", "Mon Tue Wed Thu Fri Sat Sun".split()[at // DAY % 7]),
                                  ("premium", str(q["legs"][0]["car"]["premium"])), ("note", str(q["note"] is not None)),
                                  ("supply x hours", band(notified[q["legs"][0]["pickup"]["placeId"]], [(10, "under 10 drivers"), (40, "10-39")], "40 or more")
                                   + ", " + band((last_pickup[id_] - at) / HOUR, [(8, "under 8 h"), (24, "8-24 h")], "over 24 h"))):
                rows = waits[(feature, name)]
                rows["wait"].append(wait)
                rows["late"].append(id_ in late)
                rows["none"].append(first_booked.get(id_, 10 ** 6) > last_pickup[id_])
    total = sum(weeks.values())
    print(f"{args.variant}: {total} weeks, {weeks['thin']} with under {args.thin} drivers and {weeks['normal']} others")
    print("\nRequests declined for backlog, a week")
    for group in ("normal", "thin"):
        v = sorted(declines[group])
        if v:
            print(f"  {group:6} mean {statistics.mean(v):5.1f}  median {statistics.median(v):5.1f}  9 in 10 weeks under {v[int(0.9 * len(v))]:4}  highest {v[-1]:4}  weeks with none {100 * sum(x == 0 for x in v) / len(v):3.0f}%  weeks with 100 or more {100 * sum(x >= 100 for x in v) / len(v):3.0f}%")
    print("\nThe requests, by the backlog at the quote: a week; what the curve expects of one; list price over typical fee; typical fee; hours to find a driver;"
          "\nunder 8 h; pickups with under 10 drivers; the dealer's count; and for the quoted: won, late of the won, margin a won order, margin a request")
    for group in ("normal", "thin"):
        for key in sorted(k for k in asked if k[0] == group):
            r = asked[key]
            n = r["n"]
            line = (f"  {group:6} {key[1]:26} {n / weeks[group]:6.1f}  curve {r['curve'] / n / 100:5.1f}  list/fee {r['list'] / n:4.2f}  fee {r['fee'] / n / 100:5.1f}  slack {r['slack'] / n:5.1f} h"
                    f"  short {100 * r['short'] / n:3.0f}%  thin town {100 * r['thin town'] / n:3.0f}%  count {r['trust'] / n:4.1f}")
            if r["won"]:
                line += f"  | won {100 * r['won'] / n:3.0f}%  late {100 * r['late'] / r['won']:4.1f}%  {r['money'] / r['won'] / 100:5.1f} an order  {r['money'] / n / 100:5.1f} a request"
            print(line)
    print("\nThe cars without a driver while the gate declines, share of them")
    for group in ("normal", "thin"):
        every = blockers[(group, "all", "")]["n"]
        if not every:
            continue
        print(f"  {group}: typical fee {blockers[(group, 'fee', '')]['sum'] / every / 100:.1f}")
        for feature in ("due", "waiting", "supply", "drive", "was dropped", "premium", "ends late"):
            names = [k[2] for k in blockers if k[0] == group and k[1] == feature]
            print(f"    {feature:12} " + "  ".join(f"{name}: {100 * blockers[(group, feature, name)]['n'] / every:.0f}%" for name in sorted(names, key=lambda x: -blockers[(group, feature, x)]["n"])))
    print("\nWhat makes a won car wait: orders a week, booked within an hour, within 4 hours, median minutes to the first booking, no driver by the last pickup, late")
    for feature in ("supply", "hours to the last pickup", "supply x hours", "drive", "won at", "day", "premium", "note"):
        for key in sorted((k for k in waits if k[0] == feature), key=lambda k: -len(waits[k]["wait"])):
            w = waits[key]
            n = len(w["wait"])
            print(f"  {feature:24} {key[1]:28} {n / total:6.1f}  1 h {100 * sum(x <= 60 for x in w['wait']) / n:3.0f}%  4 h {100 * sum(x <= 240 for x in w['wait']) / n:3.0f}%"
                  f"  median {statistics.median(w['wait']):5.0f} min  none {100 * sum(w['none']) / n:4.1f}%  late {100 * sum(w['late']) / n:4.1f}%")


main()
