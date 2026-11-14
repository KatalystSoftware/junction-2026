"""Scratch: the late share and the margin of won orders by the slack the desk saw at the quote."""
import argparse
import collections
import json

from spreadlab.play import load_run
from spreadlab.policy import kind

HOUR, DAY = 60, 1440
BANDS = [5, 6, 7, 8, 10, 12, 16, 24, 36, 48, 10 ** 6]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", required=True)
    parser.add_argument("--seeds", required=True)
    args = parser.parse_args()
    seeds = args.seeds.split(",")
    minutes = {(r["from"], r["to"]): r["minutes"] for r in json.load(open("data/map.json"))["roads"]}
    rows = collections.defaultdict(lambda: collections.Counter())
    for seed in seeds:
        run = load_run(args.variant, seed)
        requests = {x["request"]["id"]: x["request"] for x in run["reveal"]["requests"]}
        won, late, money = {}, set(), collections.Counter()
        for e in run["events"]:
            if e["kind"] == "order_won":
                won[e["order"]["id"]] = e["order"]
            elif e["kind"] == "ledger" and e["line"].get("orderId"):
                money[e["line"]["orderId"]] += e["line"]["cents"]
                if e["line"]["kind"] in ("late_refund", "undelivered_penalty"):
                    late.add(e["line"]["orderId"])
        for id_, order in won.items():
            request = requests[id_]
            if kind(request):
                continue
            leg = request["legs"][0]
            drive = minutes[(leg["pickup"]["placeId"], leg["delivery"]["placeId"])]
            slack = (order["deadline"] - drive - max(request["respondBy"], leg["pickup"]["window"]["from"])) / HOUR
            band = next(b for b in BANDS if slack < b)
            hour = request["arrivedAt"] % DAY // HOUR
            for key in (("slack", band), ("option", order.get("option", order.get("kind", "?"))), ("hour", hour), ("all", 0)):
                row = rows[key]
                row["n"] += 1
                row["late"] += id_ in late
                row["money"] += money[id_]
                row["fee"] += request["referenceFeeCents"]
    n = len(seeds)
    for key in sorted(rows, key=str):
        row = rows[key]
        print(f"{key[0]:>7} {str(key[1]):>14}  {row['n'] / n:6.1f} a week  late {100 * row['late'] / row['n']:5.1f}%  margin an order {row['money'] / row['n'] / 100:6.1f}  typical fee {row['fee'] / row['n'] / 100:6.1f}")


main()
