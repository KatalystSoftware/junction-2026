"""Compares variants on the weeks that all of them have played.

    python -m spreadlab.report --variants baseline,price-1.6 --list tune --count 10 [--weeks]

A week counts only when it is ranked: at least 90% of its won orders on time. The table therefore
shows the ranked weeks first, and the margin beside them. The difference to the reference (the
first variant) is paired: the same seeds, where every variant gets the same requests.

Weeks differ far more than variants do, so the table also reads each week against itself:
- "above zero": the weeks that are ranked and make more than declining every request, which makes 0.
- "95% interval": for the mean difference to the reference, from drawing the weeks again with
  replacement 10,000 times. An interval that includes 0 is not a finding: play more seeds.
- "better in": the weeks where the variant beats the reference.
A saved week replays to the same score, so one run per week and variant is enough.
"""
from __future__ import annotations

import argparse
import random
import statistics

from .catalogue import load_catalogue, load_seeds
from .play import failure_path, load_score
from .policy import fingerprint
from .variants import VARIANTS

RESAMPLES = 10_000


def interval(differences: list[float], resamples: int = RESAMPLES) -> tuple[float, float]:
    """The 95% interval of the mean paired difference, by the bootstrap over weeks. The draws are
    fixed, so the same weeks give the same interval."""
    draw = random.Random(0)
    means = sorted(statistics.fmean(draw.choices(differences, k=len(differences))) for _ in range(resamples))
    return means[int(0.025 * resamples)], means[int(0.975 * resamples) - 1]


def missing(variants: list[str], seeds: list[str], scores: dict, level: int) -> list[str]:
    """One line per variant with weeks that are not saved. They are left out of every number below,
    so they are named: a week that failed must not drop out of a comparison unseen."""
    lines = []
    for variant in variants:
        gone = [seed for seed in seeds if not scores[variant][seed]]
        failed = [seed for seed in gone if failure_path(variant, seed, level).exists()]
        if gone:
            lines.append(f"Missing for {variant}: {', '.join(gone)}" + (f". Failed when played: {', '.join(failed)}" if failed else ""))
    return lines


def euros(cents: float) -> str:
    return f"{cents / 100:,.0f}"


def compare(variants: list[str], seeds: list[str], level: int = 8, weeks: bool = False) -> None:
    scores = {variant: {seed: load_score(variant, seed, level) for seed in seeds} for variant in variants}
    for variant in variants:
        stale = [seed for seed, saved in scores[variant].items()
                 if saved and variant in VARIANTS and saved["fingerprint"] != fingerprint(VARIANTS[variant])]
        if stale:
            print(f"Note: {len(stale)} saved weeks of {variant} were played with other parameters or policy code. Run the sweep to play them again.")
    for line in missing(variants, seeds, scores, level):
        print(line)
    common = [seed for seed in seeds if all(scores[variant][seed] for variant in variants)]
    if not common:
        print("No week that every variant has played.")
        return
    print(f"{len(common)} of {len(seeds)} weeks played by every variant. Margins in euros; reference: {variants[0]}.")
    print(f"{'variant':16s} {'ranked':>7s} {'mean margin':>12s} {'worst':>9s} {'best':>9s} {'on time, lowest':>16s} {'mean':>6s} {'orders':>7s} {'above zero':>10s} {'vs reference':>13s} {'95% interval':>18s} {'better in':>10s}")
    reference = [scores[variants[0]][seed]["score"]["marginCents"] for seed in common]
    for variant in variants:
        rows = [scores[variant][seed]["score"] for seed in common]
        margins = [row["marginCents"] for row in rows]
        on_time = [row["onTimeShare"] for row in rows]
        differences = [m - r for m, r in zip(margins, reference)]
        paired = ""
        if variant != variants[0]:
            low, high = interval(differences)
            paired = f"{euros(statistics.mean(differences)):>13s} {euros(low) + ' to ' + euros(high):>18s} {sum(d > 0 for d in differences):>7d}/{len(common)}"
        above = sum(row["ranked"] and row["marginCents"] > 0 for row in rows)
        print(f"{variant:16s} {sum(row['ranked'] for row in rows):>4d}/{len(common):<2d} {euros(statistics.mean(margins)):>12s} {euros(min(margins)):>9s} {euros(max(margins)):>9s} "
              f"{min(on_time):>16.1%} {statistics.mean(on_time):>6.1%} {statistics.mean(row['wonOrders'] for row in rows):>7.0f} {above:>7d}/{len(common):<2d} {paired}")
    if weeks:
        catalogue = load_catalogue()
        print(f"\n{'seed':10s} {'cars/driver':>11s} {'few notified':>12s}" + "".join(f" {variant:>22s}" for variant in variants))
        for seed in common:
            week = catalogue.get(seed, {})
            cells = []
            for variant in variants:
                score = scores[variant][seed]["score"]
                cells.append(f"{euros(score['marginCents'])} {score['onTimeShare']:.1%}{'' if score['ranked'] else ' !'}")
            print(f"{seed:10s} {week.get('carsPerDriver', ''):>11} {week.get('pickupShareFewNotified', ''):>12}" + "".join(f" {cell:>22s}" for cell in cells))
        print("! marks a week that is not ranked.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variants", required=True)
    parser.add_argument("--list", default="tune")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--seeds")
    parser.add_argument("--level", type=int, default=8)
    parser.add_argument("--weeks", action="store_true", help="also one line per week")
    args = parser.parse_args()
    seeds = args.seeds.split(",") if args.seeds else load_seeds(args.list, args.count)
    compare(args.variants.split(","), seeds, args.level, args.weeks)


if __name__ == "__main__":
    main()
