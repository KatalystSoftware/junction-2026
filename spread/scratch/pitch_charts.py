"""Scratch: the numbers behind the charts of the jury pitch, from the saved weeks in the data folder.

    PYTHONPATH=. uv run python scratch/pitch_charts.py > pitch-charts.json

Unpack the archive first (README, "Saved weeks"). It prints one JSON object:

- `steps`: mean margin a week of each step of the policy on the first 10 tune and holdout seeds.
- `days`: each day of the 20 tune and holdout weeks that `curve` and `curve-live` both played. `share` is the win share of
  `curve`, which prices every day alike, so it reads the day's market; `price` is how much higher `curve-live` quoted the
  same requests that day, in percent, after the day's answers had moved its curve.
- `notes`: failed visits a week without and with the note reader, on the seeds both played.
- `thin`: the on-time share and margin of the reference and of the late chance in the price, on the reference's 10
  lowest weeks among the seeds that both played.
"""
from __future__ import annotations

import json
import math
import statistics

from spreadlab.catalogue import load_seeds
from spreadlab.play import load_run, run_path

DAY = 1440
STEPS = ["baseline", "with-same-day", "floor-1.7", "gate-10", "curve", "curve-live", "curve-live-surcharge",
         "fee-cap-1.2-drop-cost-1.3", "notes-offers-8", "steep-notes-offers-8"]
REFERENCE, LATE = "steep-notes-offers-8", "slow-step-gate-25-friday-late-150"


def both(a: str, b: str) -> list[str]:
    return sorted(path.name.removesuffix("-L8.json.gz") for path in run_path(a, "x").parent.glob("*-L8.json.gz")
                  if run_path(b, path.name.removesuffix("-L8.json.gz")).exists())


def steps() -> dict:
    out = {}
    for name in ("tune", "holdout"):
        seeds = load_seeds(name, 10)
        out[name] = {v: round(statistics.mean(load_run(v, s)["score"]["marginCents"] for s in seeds) / 100)
                     for v in STEPS if all(run_path(v, s).exists() for s in seeds)}
    return out


def days() -> list[dict]:
    rows = []
    for seed in load_seeds("tune", 10) + load_seeds("holdout", 10):
        fixed, live = load_run("curve", seed), load_run("curve-live", seed)
        won = {e["order"]["id"] for e in fixed["events"] if e["kind"] == "order_won"}
        arrived = {e["request"]["id"]: e["request"]["arrivedAt"] // DAY for e in fixed["events"] if e["kind"] == "price_request"}
        for day in range(5):
            quoted = [r for r, d in fixed["decisions"].items() if arrived.get(r) == day and not d["declined"]]
            ratios = [math.log(live["decisions"][r]["prices"][k] / p) for r in quoted if not live["decisions"].get(r, {}).get("declined", True)
                      for k, p in fixed["decisions"][r]["prices"].items() if k in live["decisions"][r]["prices"]]
            if quoted and ratios:
                rows.append({"seed": seed, "day": day, "share": round(sum(r in won for r in quoted) / len(quoted), 3),
                             "price": round(100 * (math.exp(statistics.mean(ratios)) - 1), 1)})
    return rows


def failed(variant: str, seed: str) -> int:
    return sum(e["kind"] == "visit_failed" for e in load_run(variant, seed)["events"])


def notes() -> dict:
    seeds = both("fee-cap-1.2-drop-cost-1.3", "notes")
    return {"weeks": len(seeds), **{v: round(statistics.mean(failed(v, s) for s in seeds), 1) for v in ("fee-cap-1.2-drop-cost-1.3", "notes")}}


def thin() -> list[dict]:
    """The reference's 10 lowest weeks among the seeds that both played."""
    rows = []
    for seed in both(REFERENCE, LATE):
        runs = {v: load_run(v, seed) for v in (REFERENCE, LATE)}
        rows.append({"seed": seed, "drivers": len(runs[REFERENCE]["roster"]), **{v: round(100 * r["score"]["onTimeShare"], 1) for v, r in runs.items()},
                     **{v + " margin": round(r["score"]["marginCents"] / 100) for v, r in runs.items()}})
    return sorted(rows, key=lambda row: row[REFERENCE])[:10]


def main() -> None:
    print(json.dumps({"steps": steps(), "days": days(), "notes": notes(), "thin": thin()}, indent=1))


if __name__ == "__main__":
    main()
