"""Scans practice weeks: plays each to its end with no actions and saves its price requests, snow
forecasts and driver list. A scan costs five requests and about a second, and the requests of a
week do not depend on what a system does, so a scan shows what every variant will face.

    python -m spreadlab.scan --prefix cat- --count 300      seeds cat-001 to cat-300
    python -m spreadlab.scan --seeds probe-a,probe-b --level 7
"""
from __future__ import annotations

import argparse
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .server import PracticeClient, data_dir, read_json_gz, write_json_gz


def scan_path(seed: str, level: int = 8) -> Path:
    return data_dir() / "scans" / f"{seed}-L{level}.json.gz"


def load_scan(seed: str, level: int = 8) -> dict:
    return read_json_gz(scan_path(seed, level))


def scan(seed: str, level: int) -> str:
    path = scan_path(seed, level)
    if path.exists():
        return f"{seed} L{level} already scanned"
    started = time.time()
    world = PracticeClient().create(level=level, seed=seed)
    try:
        snapshot, roster = world.snapshot(), world.roster()
        events = world.advance(to=snapshot["endsAt"])["events"]
        write_json_gz(path, {"seed": seed, "level": level, "startsAt": snapshot["now"], "endsAt": snapshot["endsAt"],
                             "roster": roster, "events": events})
    finally:
        world.delete()  # the scan is on disk, and the same seed gives the same world again
    requests = sum(1 for e in events if e["kind"] == "price_request")
    return f"{seed} L{level} requests {requests} drivers {len(roster)} secs {time.time() - started:.1f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seeds", help="comma-separated seeds")
    parser.add_argument("--prefix", help="with --count: seeds <prefix>001, <prefix>002, ...")
    parser.add_argument("--count", type=int, default=0)
    parser.add_argument("--level", type=int, default=8)
    parser.add_argument("--parallel", type=int, default=4)
    args = parser.parse_args()
    seeds = args.seeds.split(",") if args.seeds else [f"{args.prefix}{i:03d}" for i in range(1, args.count + 1)]
    if not seeds:
        parser.error("give --seeds, or --prefix and --count")
    started = time.time()
    with ThreadPoolExecutor(args.parallel) as pool:
        for line in pool.map(lambda seed: scan(seed, args.level), seeds):
            print(line, flush=True)
    print(f"{len(seeds)} seeds in {time.time() - started:.0f} s")


if __name__ == "__main__":
    main()
