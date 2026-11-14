"""Checks a confirmation from the unpacked archive: each variant against the reference on the two unseen sets of 60 seeds, from
the saved score of every played week. Prints the margin a week with its 95% interval, the same with a week under 90% on time
counted as no margin, the weeks under 90%, 91% and 92%, the lowest week and the share of weeks that are ranked and at or above
1.2 x and 1.3 x the reference. With two or more variants it also prints the paired difference of the first to the second.
Plays nothing.
uv run python scratch/opt/confirm_check.py <data> <variant> [<variant> ...]"""
import glob, json, random, statistics as st, sys

data, names = sys.argv[1], sys.argv[2:]
REFERENCE = "steep-notes-offers-8"
SETS = {"unseen 1 (fresh-1301 to 1360)": range(1301, 1361), "unseen 2 (fresh-1401 to 1460)": range(1401, 1461)}


def scores(variant):
    """The score of each saved level-8 week of a variant, by seed."""
    out = {}
    for path in glob.glob(f"{data}/runs/{variant}/*-L8.score.json"):
        week = json.load(open(path))
        out[week["seed"]] = week["score"]
    return out


def interval(values, draws=10000):
    """A 95% bootstrap interval of the mean."""
    means = sorted(st.mean(random.choices(values, k=len(values))) for _ in range(draws))
    return means[int(0.025 * draws)], means[int(0.975 * draws)]


def in_set(seed, numbers):
    return seed.startswith("fresh-") and seed[6:].isdigit() and int(seed[6:]) in numbers


margin = lambda s: s["marginCents"] / 100
on_time = lambda s: s["onTimeShare"]
counted = lambda s: margin(s) if on_time(s) >= 0.90 else 0.0  # a week under 90% on time is not ranked
under = lambda played, seeds, bar: sum(on_time(played[s]) < bar for s in seeds)

if __name__ == "__main__":
    random.seed(1)
    ref = scores(REFERENCE)
    for name in names:
        played = scores(name)
        print(f"\n{name}: {len(played)} weeks, {len(set(played) & set(ref))} shared with the reference")
        for label, numbers in SETS.items():
            seeds = sorted(s for s in played if in_set(s, numbers) and s in ref)
            if not seeds:
                continue
            plain = [margin(played[s]) - margin(ref[s]) for s in seeds]
            ranked = [counted(played[s]) - counted(ref[s]) for s in seeds]
            (lo, hi), (lo9, hi9) = interval(plain), interval(ranked)
            at = lambda k: 100 * st.mean(on_time(played[s]) >= 0.90 and margin(played[s]) >= k * margin(ref[s]) for s in seeds)
            print(f"  {label}: {len(seeds)} seeds  reference {st.mean(margin(ref[s]) for s in seeds):,.0f}  margin {st.mean(plain):+,.0f} ({lo:,.0f} to {hi:,.0f})"
                  f"  under 90% as no margin {st.mean(ranked):+,.0f} ({lo9:,.0f} to {hi9:,.0f})  ahead in {sum(x > 0 for x in plain)} of {len(plain)}"
                  f"  lowest {100 * min(on_time(played[s]) for s in seeds):.1f}% (reference {100 * min(on_time(ref[s]) for s in seeds):.1f}%)"
                  f"  weeks under 90/91/92%: {under(played, seeds, 0.90)}/{under(played, seeds, 0.91)}/{under(played, seeds, 0.92)}"
                  f" (reference {under(ref, seeds, 0.90)}/{under(ref, seeds, 0.91)}/{under(ref, seeds, 0.92)})  at 1.2 x / 1.3 x: {at(1.2):.0f}% / {at(1.3):.0f}%")
    if len(names) >= 2:
        first, second = scores(names[0]), scores(names[1])
        for label, numbers in SETS.items():
            seeds = sorted(s for s in first if in_set(s, numbers) and s in second)
            if seeds:
                diff = [margin(first[s]) - margin(second[s]) for s in seeds]
                lo, hi = interval(diff)
                print(f"\npaired, {names[0]} against {names[1]}, {label}: {st.mean(diff):+,.0f} ({lo:,.0f} to {hi:,.0f}) on {len(seeds)} seeds")
