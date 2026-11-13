"""Access to Bahn's server and to the data folder. Practice worlds only: nothing in the harness can
start a ranking run, because every world is created through `PracticeClient.create`."""
from __future__ import annotations

import gzip
import json
import math
import os
import time
from pathlib import Path
from typing import Any, Optional

from spread.client import Client, SpreadError, World

SERVER = "https://spread.bahnexpress.com"
PROJECT = Path(__file__).resolve().parent.parent
DAY, HOUR = 1440, 60
NOTIFY_KM = 30  # a driver's app notifies them of a gig whose first pickup is this near their home, in a straight line (RULES.md)


def data_dir() -> Path:
    """Scans and played runs: large, not committed. Set SPREAD_DATA to keep them outside the checkout."""
    return Path(os.environ.get("SPREAD_DATA") or PROJECT / "data")


class PracticeClient(Client):
    """The kit's client, limited to practice worlds. The team key comes from SPREAD_KEY."""

    def __init__(self) -> None:
        super().__init__(url=os.environ.get("SPREAD_URL") or SERVER)

    def create(self, level: int = 8, seed: Optional[str] = None, board: bool = False) -> World:
        if board:
            raise SpreadError(0, "The harness plays practice worlds only. A ranking run is a decision for a person")
        waited = 0
        while True:
            try:
                return super().create(level=level, seed=seed)
            except SpreadError as error:
                # All 8 practice slots are in use, by this sweep or by a teammate on the same key: wait for one.
                if error.status != 409 or waited >= 900:
                    raise
                time.sleep(5)
                waited += 5


def world_map(client: Optional[Client] = None) -> dict:
    """The map, read once and kept in the data folder: it is the same in every world. Only the first
    read needs the server, so analysis of saved weeks runs without the team key."""
    path = data_dir() / "map.json"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps((client or PracticeClient()).map(), ensure_ascii=False), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def near_places(map_: dict, km: float = NOTIFY_KM) -> dict[str, set[str]]:
    """For each place, the places within `km` of it in a straight line, itself included."""
    def distance(a: dict, b: dict) -> float:
        lat1, lat2 = math.radians(a["lat"]), math.radians(b["lat"])
        dlat, dlon = lat2 - lat1, math.radians(b["lon"] - a["lon"])
        h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 2 * 6371 * math.asin(math.sqrt(h))

    places = map_["places"]
    return {a["id"]: {b["id"] for b in places if distance(a, b) <= km} for a in places}


def drivers_near(roster: list[dict], near: dict[str, set[str]]) -> dict[str, int]:
    """For each place, the drivers whose home is near enough to be notified of a pickup there."""
    homes: dict[str, int] = {}
    for driver in roster:
        homes[driver["homePlaceId"]] = homes.get(driver["homePlaceId"], 0) + 1
    return {place: sum(homes.get(other, 0) for other in others) for place, others in near.items()}


def write_json_gz(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    with gzip.open(partial, "wt", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False)
    partial.replace(path)  # a reader never sees half a file


def read_json_gz(path: Path) -> Any:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)
