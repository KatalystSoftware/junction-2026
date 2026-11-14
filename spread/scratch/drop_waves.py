"""Scratch: the nights when many drivers drop their gigs, the bulk order, and what a cap on one day's cars would cut,
from saved weeks.

A wave is 10 or more drops in a day's first hour (on other nights there are about 2). For each variant it prints the
weeks with a wave on each weekday, the late share of the orders due on a Friday by how many were due and whether a wave
came that night, the late share of the orders won from the week's largest batch against all orders, the lowest weeks,
and, with --caps, the orders that a cap on one day's cars (`due_cap`) would have declined: those won while their day
already had that many orders with a car still to deliver. That last count leaves out what the desk would have done
instead, so it is an upper bound on the margin a cap costs.

    PYTHONPATH=. uv run python scratch/drop_waves.py --variants slow-friday-late-150-kinds-limits --seeds fresh-1301,... --caps 70,80
"""
from __future__ import annotations

import argparse
import collections

from spreadlab.play import load_run, run_path

DAY, WAVE = 1440, 10


def week(run: dict) -> dict:
    requests = {r["request"]["id"]: r["request"] for r in run["reveal"]["requests"]}
    batch = collections.Counter(r["batchId"] for r in requests.values() if r["batchId"]).most_common(1)[0][0]
    won, late, delivered, money, first_hour = [], set(), {}, collections.Counter(), collections.Counter()
    for e in run["events"]:
        if e["kind"] == "order_won":
            won.append((e["at"], e["order"]["id"], e["order"]["lastPickupAt"] // DAY))
        elif e["kind"] == "delivered":
            delivered[e["orderId"]] = max(delivered.get(e["orderId"], 0), e["at"])
        elif e["kind"] == "ledger" and e["line"]["orderId"]:
            money[e["line"]["orderId"]] += e["line"]["cents"] / 100
            late |= {e["line"]["orderId"]} if e["line"]["kind"] in ("late_refund", "undelivered_penalty") else set()
        elif e["kind"] in ("gig_dropped", "no_show") and e["at"] % DAY < 60:
            first_hour[e["at"] // DAY] += 1
    score = run["score"].get("score", run["score"])
    return {"won": sorted(won), "late": late, "delivered": delivered, "money": money, "first_hour": first_hour,
            "bulk": {i for i, r in requests.items() if r["batchId"] == batch}, "on_time": score["onTimeShare"]}


def cut(w: dict, cap: int) -> set[str]:
    kept, out = [], set()
    for at, id_, day in w["won"]:
        if sum(1 for at_, other, day_ in kept if day_ == day and w["delivered"].get(other, 10**9) > at) >= cap:
            out.add(id_)
        else:
            kept.append((at, id_, day))
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", required=True)
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--caps", default="")
    args = parser.parse_args()
    for variant in args.variants.split(","):
        weeks = {s: week(load_run(variant, s)) for s in args.seeds.split(",") if run_path(variant, s).exists()}
        n = len(weeks)
        print(f"{variant}: {n} weeks")
        print("  weeks with a wave, Monday to Friday:", [sum(1 for w in weeks.values() if w["first_hour"][d] >= WAVE) for d in range(5)])
        cells = collections.defaultdict(lambda: [0, 0, 0])
        for w in weeks.values():
            friday = [id_ for _, id_, day in w["won"] if day == 4]
            cell = cells[(w["first_hour"][4] >= WAVE, "under 50" if len(friday) < 50 else "50 to 99" if len(friday) < 100 else "100 or more")]
            cell[0] += 1
            cell[1] += len(friday)
            cell[2] += len(set(friday) & w["late"])
        for (wave, due), (k, orders, late) in sorted(cells.items()):
            print(f"  due on Friday {due:12s} {'wave' if wave else 'no wave':8s} {k:4d} weeks, {late / orders:6.1%} late")
        bulk = [(id_ in w["late"]) for w in weeks.values() for _, id_, _ in w["won"] if id_ in w["bulk"]]
        every = [(id_ in w["late"]) for w in weeks.values() for _, id_, _ in w["won"]]
        print(f"  orders from the largest batch: {len(bulk) / n:.1f} a week, {sum(bulk) / max(1, len(bulk)):.1%} late; all orders {sum(every) / len(every):.1%} late")
        lowest = sorted(weeks.items(), key=lambda kv: kv[1]["on_time"])[:5]
        print("  lowest:", ", ".join(f"{s} {w['on_time']:.1%} (Friday's first hour: {w['first_hour'][4]} drops)" for s, w in lowest))
        for cap in [int(c) for c in args.caps.split(",") if c]:
            gone = {s: cut(w, cap) for s, w in weeks.items()}
            after = {s: 1 - len((w["late"] - gone[s]) & {i for _, i, _ in w["won"]}) / max(1, len(w["won"]) - len(gone[s])) for s, w in weeks.items()}
            print(f"  cap {cap}: {sum(map(len, gone.values())) / n:.1f} orders a week, {sum(len(g & weeks[s]['late']) for s, g in gone.items()) / n:.2f} of them late,"
                  f" margin {sum(weeks[s]['money'][i] for s, g in gone.items() for i in g) / n:.0f} a week; weeks under 90%"
                  f" {sum(w['on_time'] < 0.9 for w in weeks.values())} -> {sum(v < 0.9 for v in after.values())}")


if __name__ == "__main__":
    main()
