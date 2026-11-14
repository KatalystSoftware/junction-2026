"""Replays spreadlab.stopcheck on the saved paired checks of the archive, as a launcher calls it before each challenger
week: the weeks each check would have played, and whether its answer (adopt or keep the reference) would change.

    PYTHONPATH=. uv run python scratch/stopcheck_replay.py      # after `python -m spreadlab.archive unpack`
"""
from __future__ import annotations

import math
import re
import statistics

from spreadlab import stopcheck
from spreadlab.play import load_score
from spreadlab.server import data_dir

REFS = ["slow-friday-late-150-kinds-limits", "steep-notes-offers-8", "slow-step-gate-25", "slow-step-gate-25-kinds"]


def order(seed: str):
    m = re.match(r"(.*?)-(\d+)$", seed)
    return (m.group(1), int(m.group(2))) if m else (seed, 0)


runs = data_dir() / "runs"
saved = {p.name: {f.name.split("-L8")[0] for f in p.glob("*.score.json")} for p in runs.iterdir()}
full_weeks = seq_weeks = flips = 0
for variant in sorted(saved):
    if variant == REFS[0]:
        continue
    ref = max((r for r in REFS if r != variant and r in saved), key=lambda r: len(saved[variant] & saved[r]))
    seeds = sorted(saved[variant] & saved[ref], key=order)
    if len(seeds) < 30:
        continue
    diffs = [stopcheck.counted(load_score(variant, s)) - stopcheck.counted(load_score(ref, s)) for s in seeds]
    z = statistics.fmean(diffs) / (statistics.stdev(diffs) / math.sqrt(len(diffs)))
    under = sum(1 for s in seeds if not load_score(variant, s)["score"]["ranked"])
    full = "out" if under > max(1, len(seeds) // 60) else "better" if z >= 1.96 else "worse" if z <= -1.96 else "open"
    played, why = len(seeds), "played all"
    for k in range(1, len(seeds) + 1):  # k challenger weeks saved, in list order
        shown = set(seeds[:k])
        stopcheck.load_score = lambda v, s, level=8: load_score(v, s, level) if v != variant or s in shown else None
        stop, text = stopcheck.decide(variant, ref, seeds)
        if stop and not text.startswith("stop: all"):
            played, why = k, text
            break
    seq = why.split(",")[0].replace("stop: ", "") if played < len(seeds) else full
    flip = (seq == "better") != (full == "better")
    flips += flip
    full_weeks += len(seeds)
    seq_weeks += played
    print(f"{variant[:44]:44s} {len(seeds):4d} {full:>7s} {statistics.fmean(diffs):+7.0f}  stops after {played:4d}: {why[:70]}{'  <- differs' if flip else ''}")
print(f"\nchallenger weeks: {seq_weeks} of {full_weeks} ({1 - seq_weeks / full_weeks:.0%} fewer); adopt-or-not answers that differ: {flips}")
