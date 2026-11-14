"""What a won one-car dealer order costs all in, by the hours from its win to its last pickup minute, from saved weeks.

All in = driver fees + release fees + late refunds + undelivered penalties of the order, over its typical fee. A pair gig's
fee is split over its orders by their typical fees. Prints, per band: orders a week, mean cost x typical, late share.

    python3 -I scratch/cost_bands.py data/runs/<variant> [seed prefix, e.g. fresh-35]

On the default's 29 saved weeks of fresh-1301 to 1329: 1.17 x under 8 hours, 1.11 at 24 to 30, 1.06 to 1.09 from 30 on,
against the quote's flat 1.2. Feeds `cost_hours`.
"""
import collections
import gzip
import json
import sys
from pathlib import Path

BANDS = [6, 8, 12, 16, 24, 30, 36, 48, 10 ** 6]


def band(hours):
    lo = 0
    for hi in BANDS:
        if hours < hi:
            return f"{lo}-{hi if hi < 10 ** 6 else ''}"
        lo = hi


def week(path):
    w = json.load(gzip.open(path))
    ref, won, cost, late, kinds = {}, {}, collections.Counter(), set(), {}
    for e in w["events"]:
        if e["kind"] == "price_request":
            r = e["request"]
            ref[r["id"]] = r["referenceFeeCents"]
            kinds[r["id"]] = len(r["legs"]) == 1 and not any(l["pickup"]["privateAddress"] or l["delivery"]["privateAddress"] for l in r["legs"])
        elif e["kind"] == "order_won":
            o = e["order"]
            won[o["id"]] = (o["lastPickupAt"] - e["at"]) / 60
    orders_of = {g["id"]: sorted({s["orderId"] for s in g["stops"]}) for g in w["gigs"]}
    for e in w["events"]:
        if e["kind"] != "ledger":
            continue
        line = e["line"]
        if line["kind"] in ("late_refund", "undelivered_penalty") and line["orderId"]:
            late.add(line["orderId"])
        if line["kind"] in ("driver_fee", "release_fee") and line.get("gigId") in orders_of and len(orders_of[line["gigId"]]) > 1:
            ids = orders_of[line["gigId"]]
            total = sum(ref.get(i, 0) for i in ids) or 1
            for i in ids:
                cost[i] -= line["cents"] * ref.get(i, 0) / total
        elif line["kind"] in ("driver_fee", "release_fee", "late_refund", "undelivered_penalty") and line["orderId"]:
            cost[line["orderId"]] -= line["cents"]
    return [(band(h), cost[i] / ref[i], i in late) for i, h in won.items() if kinds.get(i) and ref.get(i)]


def main():
    folder, prefix = Path(sys.argv[1]), (sys.argv[2] if len(sys.argv) > 2 else "")
    files = sorted(p for p in folder.glob(f"{prefix}*-L8.json.gz"))
    rows = [r for p in files for r in week(p)]
    n = len(files)
    print(f"{folder.name}: {n} weeks, {len(rows) / n:.1f} one-car dealer orders a week")
    print("| hours from win to last pickup | orders a week | cost x typical, all in | late |")
    print("| --- | --- | --- | --- |")
    by = collections.defaultdict(list)
    for b, c, l in rows:
        by[b].append((c, l))
    for hi in BANDS:
        b = band(hi - 0.01)
        xs = by.get(b, [])
        if xs:
            print(f"| {b} | {len(xs) / n:.1f} | {sum(c for c, _ in xs) / len(xs):.3f} | {100 * sum(l for _, l in xs) / len(xs):.1f}% |")


if __name__ == "__main__":
    main()
