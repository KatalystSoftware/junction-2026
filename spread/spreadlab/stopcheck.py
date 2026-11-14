"""Says whether a paired check can stop before its last seed, so its remaining weeks go to another check.

    python -m spreadlab.stopcheck --variant fee16 --reference slow-friday-late-150-kinds-limits --seeds fresh-1901..1960

Exit status 0: stop, nothing more to learn from this list. Exit status 1: play on. A launcher runs it before each week
of the challenger and stops the check on 0. It reads saved score files only and never calls the server.

A check stops for one of two reasons:
- **out**: the challenger already has more weeks under 90% on time than the 1-in-60 rule allows on the whole list,
  max(1, seeds // 60). Exact: more weeks cannot take one back.
- **worse**: at a look, the paired difference is below an O'Brien-Fleming bound, z <= -2.05 * sqrt(seeds / n). Looks
  are on the first 10, 20, 30, ... seeds of the list, taken only once both arms have every one of them, so the answer does
  not depend on which week finished first. 2.05 holds the chance of stopping a challenger that is in fact as good as the
  reference under 2.5% for up to 6 looks; at the last look the bound is z <= -2.05, a little stricter than a 95% interval.
A challenger that is ahead is never stopped: it plays the whole list, which the 1-in-60 rule needs.

Margins count a week under 90% on time as 0, as `alloc.py done` does. On the saved paired checks of the archive (14
challengers, 844 weeks), these stops play 390 of the 844 weeks (54% fewer) and change no answer of adopt or keep the reference
(scratch/stopcheck_replay.py).
"""
from __future__ import annotations

import argparse
import math
import re
import statistics
import sys

from .play import load_score

LOOK = 10  # weeks between looks
BOUND = 2.05  # O'Brien-Fleming constant for up to 6 equally spaced looks, one side at 2.5%


def expand(text: str) -> list[str]:
    """Seeds from a list such as "fresh-1901..1960, cat-001..038": each range keeps the width of its first number."""
    seeds = []
    for part in (p.strip() for p in text.split(",") if p.strip()):
        found = re.fullmatch(r"(.*?)(\d+)\.\.(\d+)", part)
        if not found:
            seeds.append(part)
            continue
        prefix, first, last = found.groups()
        seeds += [f"{prefix}{n:0{len(first)}d}" for n in range(int(first), int(last) + 1)]
    return seeds


def counted(saved: dict) -> float:
    """The week's margin in euros, 0 for a week under 90% on time."""
    return saved["score"]["marginCents"] / 100 if saved["score"]["ranked"] else 0.0


def decide(variant: str, reference: str, seeds: list[str], level: int = 8) -> tuple[bool, str]:
    """(stop, why) for the challenger `variant` against `reference` on `seeds`, from the saved weeks."""
    mine = {seed: load_score(variant, seed, level) for seed in seeds}
    theirs = {seed: load_score(reference, seed, level) for seed in seeds}
    under = sum(1 for saved in mine.values() if saved and not saved["score"]["ranked"])
    allowed = max(1, len(seeds) // 60)
    if under > allowed:
        return True, f"stop: out, {under} weeks under 90% on time where {len(seeds)} seeds allow {allowed}"
    both = next((i for i, seed in enumerate(seeds) if not (mine[seed] and theirs[seed])), len(seeds))
    if both == len(seeds):
        return True, f"stop: all {len(seeds)} seeds played; read the answer with spreadlab.report"
    n = both // LOOK * LOOK
    if n < LOOK:
        return False, f"play on: {both} of {len(seeds)} seeds paired, the first look is at {LOOK}"
    differences = [counted(mine[seed]) - counted(theirs[seed]) for seed in seeds[:n]]
    mean = statistics.fmean(differences)
    spread = statistics.stdev(differences) or 1e-9
    z, bound = mean / (spread / math.sqrt(n)), -BOUND * math.sqrt(len(seeds) / n)
    verdict = f"€{mean:+,.0f} a week on the first {n} of {len(seeds)} seeds (z {z:+.1f}, stop below {bound:+.1f})"
    if z <= bound:
        return True, f"stop: worse, {verdict}"
    return False, f"play on: {verdict}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variant", required=True, help="the challenger")
    parser.add_argument("--reference", required=True)
    parser.add_argument("--seeds", required=True, help='the check\'s whole list in play order, such as "fresh-1901..1960"')
    parser.add_argument("--level", type=int, default=8)
    args = parser.parse_args()
    stop, why = decide(args.variant, args.reference, expand(args.seeds), args.level)
    print(why)
    sys.exit(0 if stop else 1)


if __name__ == "__main__":
    main()
