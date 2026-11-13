"""Builds the catalogue from scanned weeks: what each week shows before any decision, and the seed
lists to tune on and to hold out.

    python -m spreadlab.catalogue --prefix cat-

Writes catalogue/catalogue.json (one row per seed) and catalogue/seeds.json (`tune` and `holdout`).
Both lists are ordered so that their first 10, 20 or 40 seeds cover tight and easy weeks alike.
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics

from .scan import load_scan
from .server import DAY, PROJECT, data_dir, drivers_near, near_places, world_map

CATALOGUE = PROJECT / "catalogue"
THIN = 5  # a pickup is thin when at most this many drivers are notified of it


def features(scan: dict, near: dict[str, set[str]]) -> dict:
    """What a scan shows of a week. It does not show the competitor's prices, the price war, the outage or the flu."""
    requests = [e["request"] for e in scan["events"] if e["kind"] == "price_request"]
    forecasts = [e for e in scan["events"] if e["kind"] == "forecast"]
    roster = scan["roster"]
    homes = collections.Counter(d["homePlaceId"] for d in roster)
    notified = drivers_near(roster, near)
    pickups = collections.Counter(leg["pickup"]["placeId"] for r in requests for leg in r["legs"])
    cars = sum(pickups.values())
    dealers = collections.Counter(r["dealerId"] for r in requests)
    bulk_id, bulk_size = collections.Counter(r["batchId"] for r in requests if r["batchId"]).most_common(1)[0]
    bulk = [r for r in requests if r["batchId"] == bulk_id]
    return {
        "seed": scan["seed"],
        "level": scan["level"],
        "requests": len(requests),
        "cars": cars,
        "drivers": len(roster),
        "carsPerDriver": round(cars / len(roster), 3),
        "helsinkiShare": round(homes["helsinki"] / len(roster), 3),
        "townsUnder3Drivers": sum(1 for town in pickups if homes[town] <= 2),
        "pickupShareInThinTowns": round(sum(n for town, n in pickups.items() if homes[town] <= THIN) / cars, 3),
        "pickupShareFewNotified": round(sum(n for town, n in pickups.items() if notified[town] <= THIN) / cars, 3),
        "top2DealerShare": round(sum(n for _, n in dealers.most_common(2)) / len(requests), 3),
        "bulkSize": bulk_size,
        "bulkDay": min(r["arrivedAt"] for r in bulk) // DAY,
        "bulkDealer": bulk[0]["dealerId"],
        "bulkPickup": collections.Counter(leg["pickup"]["placeId"] for r in bulk for leg in r["legs"]).most_common(1)[0][0],
        "snow": [{"day": f["from"] // DAY, "hours": (f["to"] - f["from"]) // 60, "places": f["placeIds"], "announcedDay": f["at"] // DAY} for f in forecasts],
        "noteShare": round(sum(1 for r in requests if r["note"]) / len(requests), 3),
        "privateShare": round(sum(1 for r in requests if any(leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"] for leg in r["legs"])) / len(requests), 3),
        "tradeInShare": round(sum(1 for r in requests if len(r["legs"]) > 1) / len(requests), 3),
        "sameDayShare": round(sum(1 for r in requests if any(o["kind"] == "same_day" for o in r["options"])) / len(requests), 3),
        "requestsPerDay": [sum(1 for r in requests if r["arrivedAt"] // DAY == d) for d in range(5)],
    }


def tercile(values: list[float], value: float) -> int:
    ordered = sorted(values)
    return (value >= ordered[len(ordered) // 3]) + (value >= ordered[2 * len(ordered) // 3])


def split(rows: list[dict]) -> dict[str, list[str]]:
    """Two seed lists with the same mix of weeks. A week's stratum is its tercile of cars per driver
    and its tercile of pickups that few drivers are notified of: the two measures of how hard the
    week's deliveries are. Each list takes every second seed of each stratum, and walks the strata in
    turn, so that a prefix of a list has the same mix as the whole."""
    tight = [r["carsPerDriver"] for r in rows]
    thin = [r["pickupShareFewNotified"] for r in rows]
    strata: dict[tuple[int, int], list[str]] = collections.defaultdict(list)
    for row in sorted(rows, key=lambda r: r["seed"]):
        strata[(tercile(tight, row["carsPerDriver"]), tercile(thin, row["pickupShareFewNotified"]))].append(row["seed"])
    halves: dict[str, list[list[str]]] = {"tune": [], "holdout": []}
    odd = 0  # the strata so far with an odd number of seeds: their extra seed goes to each list in turn
    for key in sorted(strata):
        first, second = ("tune", "holdout") if odd % 2 == 0 else ("holdout", "tune")
        odd += len(strata[key]) % 2
        halves[first].append(strata[key][0::2])
        halves[second].append(strata[key][1::2])
    lists: dict[str, list[str]] = {}
    for name, columns in halves.items():
        lists[name] = [column[i] for i in range(max(map(len, columns))) for column in columns if i < len(column)]
    return lists


def load_seeds(name: str, count: int = 0) -> list[str]:
    """A seed list of the catalogue, or its first `count` seeds."""
    seeds = json.loads((CATALOGUE / "seeds.json").read_text(encoding="utf-8"))[name]
    return seeds[:count] if count else seeds


def load_catalogue() -> dict[str, dict]:
    return {row["seed"]: row for row in json.loads((CATALOGUE / "catalogue.json").read_text(encoding="utf-8"))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prefix", default="cat-")
    parser.add_argument("--level", type=int, default=8)
    args = parser.parse_args()
    near = near_places(world_map())
    paths = sorted((data_dir() / "scans").glob(f"{args.prefix}*-L{args.level}.json.gz"))
    rows = [features(load_scan(path.name.removesuffix(f"-L{args.level}.json.gz"), args.level), near) for path in paths]
    lists = split(rows)
    CATALOGUE.mkdir(exist_ok=True)
    (CATALOGUE / "catalogue.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (CATALOGUE / "seeds.json").write_text(json.dumps(lists, indent=1) + "\n", encoding="utf-8")

    print(f"{len(rows)} level {args.level} weeks: tune {len(lists['tune'])}, holdout {len(lists['holdout'])}")
    by_seed = {row["seed"]: row for row in rows}
    groups = {"all": rows, "tune": [by_seed[s] for s in lists["tune"]], "holdout": [by_seed[s] for s in lists["holdout"]],
              "tune, first 10": [by_seed[s] for s in lists["tune"][:10]], "holdout, first 10": [by_seed[s] for s in lists["holdout"][:10]]}
    keys = ("requests", "drivers", "carsPerDriver", "pickupShareFewNotified", "pickupShareInThinTowns", "townsUnder3Drivers",
            "top2DealerShare", "bulkSize", "noteShare", "privateShare", "tradeInShare", "sameDayShare")
    print(f"{'lowest / median / highest':28s}" + "".join(f"{name:>24s}" for name in groups))
    for key in keys:
        cells = []
        for group in groups.values():
            values = sorted(row[key] for row in group)
            cells.append(f"{values[0]:g} / {statistics.median(values):g} / {values[-1]:g}")
        print(f"{key:28s}" + "".join(f"{cell:>24s}" for cell in cells))
    print("bulk order day:", sorted(collections.Counter(r["bulkDay"] for r in rows).items()))
    print("snow events per week:", sorted(collections.Counter(len(r["snow"]) for r in rows).items()))
    print("snow day:", sorted(collections.Counter(s["day"] for r in rows for s in r["snow"]).items()))


if __name__ == "__main__":
    main()
