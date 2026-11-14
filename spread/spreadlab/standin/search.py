"""Plays many parameter sets around one base on the stand-in, for a joint search of the base's settings in weeks with a full
driver list (scratch/search/README.md says how a search runs and is read).

    python -m spreadlab.standin.search --spec batch.json --half a --shard 3/12 --out out

`batch.json` is {"baseline": <variant in variants.py>, "arms": {name: {parameter: value, ...}, ...}}. Each arm is the baseline
with these parameters in a week with `SHORT` drivers or more; in a shorter week `when_tight` puts back the baseline's values,
so that week plays as the baseline to the cent. The arms therefore play only the natural seeds with `SHORT` drivers or more:
the others would repeat the baseline's week. The baseline plays every natural seed of the half. A shard plays every n-th arm,
so several runners share a batch. `out/rows.csv` has the columns of screen.py, one row an arm, seed and draw.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import time
from pathlib import Path

from ..pairs import PARAMS as PAIR_PARAMS
from ..policy import DEFAULTS
from ..variants import VARIANTS
from . import pack, run, screen

HERE = Path(__file__).parent
SHORT = screen.SHORT
# Pair parameters that pairs.py itself switches off in a week under `pair_more_drivers`; when_tight cannot set pair parameters.
PAIR_SWITCHED = {"pair_open", "pair_onward", "pair_late", "pair_onward_cost"}


def full_weeks(base: dict, knobs: dict) -> dict:
    """The base with `knobs` in a week with `SHORT` drivers or more, and the base itself in a shorter week."""
    if base.get("tight_drivers") != SHORT:
        raise ValueError(f"the base must switch at {SHORT} drivers (tight_drivers), not {base.get('tight_drivers')}")
    for key in knobs:
        if key in PAIR_PARAMS and not (key in PAIR_SWITCHED and base.get("pair_more_drivers") == SHORT):
            raise ValueError(f"{key} would change weeks under {SHORT} drivers too: when_tight cannot set pair parameters")
        if key not in DEFAULTS and key not in PAIR_PARAMS or key in {"tight_drivers", "when_tight", "model"}:
            raise ValueError(f"{key} cannot be switched by the driver list")
    restore = {k: base.get(k, DEFAULTS[k]) for k in knobs if k in DEFAULTS}
    return {**base, **knobs, "when_tight": {**restore, **base.get("when_tight", {})}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--half", default="a", choices=["", "a", "b"])
    parser.add_argument("--shard", default="0/1", help="i/n: this runner plays arms i, i+n, i+2n, ...")
    parser.add_argument("--draws", type=int, default=1)
    parser.add_argument("--anchor", default="")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 2)
    parser.add_argument("--limit", type=int, default=0, help="at most this many seeds (a self-test)")
    parser.add_argument("--out", default="out")
    args = parser.parse_args()
    spec = json.loads(Path(args.spec).read_text())
    first = spec["baseline"]
    if first not in VARIANTS:
        raise SystemExit(f"Not in this checkout's variants.py: {first}")
    base = VARIANTS[first]
    index, count = map(int, args.shard.split("/"))
    arms = {name: full_weeks(base, knobs) for name, knobs in list(spec["arms"].items())[index::count]}
    seeds = [line.strip() for line in (HERE / "seeds-natural.txt").read_text().splitlines() if line.strip()]
    seeds = seeds[{"": slice(None), "a": slice(0, None, 2), "b": slice(1, None, 2)}[args.half]]
    seeds = seeds[: args.limit] if args.limit else seeds
    full = [s for s in seeds if len(pack.load_world(s)["roster"]) >= SHORT]
    started = time.time()
    weights = json.loads(run.WEIGHTS.read_text())
    anchor = args.anchor or screen.DEFAULT
    out = run.run({first: base}, seeds, anchor, weights, {}, args.draws, args.jobs)
    rows, errors = out["results"], list(out["errors"])
    if arms:
        more = run.run(arms, full, anchor, weights, {}, args.draws, args.jobs)
        rows.update(more["results"])
        errors += more["errors"]
    folder = Path(args.out)
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "rows.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(screen.COLUMNS)
        for arm, by_seed in rows.items():
            for seed, weeks in by_seed.items():
                for draw, w in enumerate(weeks):
                    writer.writerow([arm, seed, draw, "thin" if w["drivers"] < run.THIN else "natural", w["drivers"], w["orders"], w["late"], round(w["on_time"], 4),
                                     round(w["margin"]), round(run.ranked(w)), w["late_after"], w["gigs"], w["booked"], w["dropped"], w["expired"], w["refused"],
                                     " ".join(map(str, w["wave"])), round(w["ledger"].get("revenue", 0)), round(-w["ledger"].get("driver_fee", 0)),
                                     round(-w["ledger"].get("late_refund", 0))])
    (folder / "errors.txt").write_text("".join(f"{a} {s} draw {d}: {e}\n" for a, s, d, e in errors))
    print(f"{len(arms)} arms on {len(full)} of {len(seeds)} seeds ({SHORT}+ drivers), the baseline on all, {args.draws} draw(s): "
          f"{time.time() - started:.0f} s on {args.jobs} cores, {len(errors)} weeks failed")


if __name__ == "__main__":
    main()
