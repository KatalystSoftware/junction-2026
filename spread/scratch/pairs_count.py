"""Counts, in saved weeks, the pairs of won one-car dealer orders that run out and back between two places and
could go as one gig: how many exist at all, and how many are both without a driver at the same minute."""
import argparse
import collections
import json

from spreadlab.play import load_run
from spreadlab.policy import kind

HOUR, DAY = 60, 1440


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", required=True)
    parser.add_argument("--seeds", required=True)
    args = parser.parse_args()
    seeds = args.seeds.split(",")
    count = collections.Counter()
    minutes = None
    for seed in seeds:
        run = load_run(args.variant, seed)
        if minutes is None:
            minutes = {(r["from"], r["to"]): r["minutes"] for r in json.load(open("data/map.json"))["roads"]}
        requests = {x["request"]["id"]: x["request"] for x in run["reveal"]["requests"]}
        order_of = {g["id"]: g["stops"][0]["orderId"] for g in run["gigs"]}
        won, won_at, booked_at = {}, {}, {}
        for e in run["events"]:
            if e["kind"] == "order_won":
                won[e["order"]["id"]], won_at[e["order"]["id"]] = e["order"], e["at"]
            elif e["kind"] == "gig_booked":
                booked_at.setdefault(order_of[e["gigId"]], e["at"])
        orders = [o for id_, o in won.items() if kind(requests[id_]) == ""]
        count["orders"] += len(orders)
        by_lane = collections.defaultdict(list)
        for o in orders:
            leg = o["legs"][0]
            by_lane[(leg["pickup"]["placeId"], leg["delivery"]["placeId"])].append(o)
        used = {hold: set() for hold in (0, 1, 2, 4, 8, 99)}
        for (a, b), outs in by_lane.items():
            if a >= b or a == b:
                continue
            drive = minutes[(a, b)] + minutes[(b, a)]
            for out in outs:
                for back in by_lane.get((b, a), []):
                    for first, second in ((out, back), (back, out)):
                        l1, l2 = first["legs"][0], second["legs"][0]
                        d1, d2 = minutes[(l1["pickup"]["placeId"], l1["delivery"]["placeId"])], minutes[(l2["pickup"]["placeId"], l2["delivery"]["placeId"])]
                        both = max(won_at[first["id"]], won_at[second["id"]])
                        # The earliest feasible run from the minute both are won: collect the first, deliver, collect the second, deliver.
                        start = max(both, l1["pickup"]["window"]["from"])
                        if start > l1["pickup"]["window"]["to"]:
                            continue
                        arrive = start + d1
                        collect = max(arrive, l2["pickup"]["window"]["from"])
                        if collect > l2["pickup"]["window"]["to"] or arrive > first["deadline"] or collect + d2 > second["deadline"]:
                            continue
                        if collect + d2 - start > 12 * HOUR:
                            continue
                        # The latest start that still makes it, for the slack.
                        latest = min(l1["pickup"]["window"]["to"], first["deadline"] - d1, l2["pickup"]["window"]["to"] - d1, second["deadline"] - d2 - d1)
                        slack = latest - both
                        if slack < 3 * HOUR:
                            continue
                        early, late_ = sorted((first, second), key=lambda o: won_at[o["id"]])
                        gap = won_at[late_["id"]] - won_at[early["id"]]
                        open_ = booked_at.get(early["id"], 10 ** 9) > won_at[late_["id"]]
                        for hold in used:
                            ok = open_ if hold == 0 else gap <= hold * HOUR
                            if ok and first["id"] not in used[hold] and second["id"] not in used[hold]:
                                used[hold] |= {first["id"], second["id"]}
                                count[f"pairs hold {hold}"] += 1
                                if hold == 99:
                                    count["drive minutes"] += drive
                                    count["slack hours"] += slack // HOUR
    n = len(seeds)
    print(f"{args.variant}: {n} weeks, {count['orders'] / n:.1f} one-car dealer orders a week")
    print(f"  pairs of any timing (feasible out and back, 3 h or more of slack once both are won): {count['pairs hold 99'] / n:.1f} a week")
    print(f"  of which the earlier order is still without a driver when the later is won: {count['pairs hold 0'] / n:.1f}")
    for hold in (1, 2, 4, 8):
        print(f"  of which the later order is won within {hold} h of the earlier: {count[f'pairs hold {hold}'] / n:.1f}")
    if count["pairs hold 99"]:
        print(f"  mean round trip {count['drive minutes'] / count['pairs hold 99']:.0f} min, mean slack {count['slack hours'] / count['pairs hold 99']:.0f} h")


main()
