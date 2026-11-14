"""Scratch: plays the weeks of a grid of variants and seeds that are not saved yet with the same parameters.

    SPREAD_KEY=... PYTHONPATH=. uv run python scratch/play_missing.py --variants steep-notes-offers-8,slow-step-gate-25 --seeds fresh-141,... --parallel 2

A sweep plays a saved week again when policy.py has changed since, because the fingerprint covers the file. An
edit that only adds a parameter, off at its default, plays the same weeks: the reference replays to the same scores
after each such edit. This keeps a saved week whose parameters are the ones asked for, whatever its fingerprint.
No week starts once data/STOP exists, so a run can be ended without leaving a practice world open.
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from spreadlab.play import line, load_score, play
from spreadlab.policy import DEFAULTS
from spreadlab.server import data_dir
from spreadlab.variants import VARIANTS


def same_parameters(saved: dict, params: dict) -> bool:
    # A parameter of a subclass (riskfee.py, daycap.py, ...) is not in DEFAULTS; a saved week has it in its params.
    return all(saved["params"].get(name, DEFAULTS.get(name)) == value for name, value in json.loads(json.dumps({**DEFAULTS, **params})).items())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", required=True)
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--parallel", type=int, default=2)
    args = parser.parse_args()
    variants, seeds = args.variants.split(","), args.seeds.split(",")
    todo = []
    for seed in seeds:  # seed by seed, so that a run that stops early has whole rows to compare
        for variant in variants:
            saved = load_score(variant, seed)
            if saved is None or not same_parameters(saved, VARIANTS[variant]):
                todo.append((variant, seed))
    print(f"{len(todo)} weeks to play, {len(variants) * len(seeds) - len(todo)} saved", flush=True)
    stop = data_dir() / "STOP"

    def week(variant: str, seed: str):
        return None if stop.exists() else play(variant, VARIANTS[variant], seed)

    with ThreadPoolExecutor(args.parallel) as pool:
        futures = {pool.submit(week, variant, seed): (variant, seed) for variant, seed in todo}
        for future in as_completed(futures):
            try:
                if future.result() is not None:
                    print(line(future.result()), flush=True)
            except Exception as error:  # one failed week does not stop the others
                print(f"{futures[future][0]} {futures[future][1]} FAILED: {error!r}", flush=True)


main()
