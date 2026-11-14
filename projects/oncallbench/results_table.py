"""The benchmark table: every model and baseline on the 24 common level-4 seeds (200000-200023).

Reads metrics.json (round 16, Harbor + OpenCode runs; runs marked as infrastructure failures are
left out) and loop-evidence/common-scripted.json (scripted policies, from scripted_scores.py).
Writes results.json, which the README table and the deck render from, and prints the markdown.

    python3 results_table.py

Definitions, fixed before the numbers were computed:
- score: (cost_do_nothing - cost) / (cost_do_nothing - cost_reference), clipped to 0..1.
- solve rate: share of runs scoring at least SOLVED (0.95) of the expert's score.
- worse than doing nothing: the run's cost is strictly above the do-nothing cost on its seed.
- 95% CI: cluster bootstrap over seeds (draw seeds with replacement, keep every run of each drawn
  seed), 10,000 resamples, fixed random seed; runs on one seed are not independent.
"""

import json
import random
import statistics as st
from pathlib import Path

HERE = Path(__file__).parent
SEEDS = range(200000, 200024)
SOLVED = 0.95
RESAMPLES = 10_000

MODELS = [  # metrics.json run name, label
    ("fable", "Fable 5.2"),
    ("opus", "Opus 5.5"),
    ("gemma-base", "Gemma 4 26B-A4B, untrained"),
    ("gemma-ft", "Gemma 4 26B-A4B + our adapter"),
]
# Measured on other seeds or with another harness, so never in the main table's columns
# (rl/RESULTS.md). Replaced by Harbor rows on the common seeds once those runs land.
SEPARATE = [
    dict(label="Gemma 4 26B-A4B, untrained", harness="Harbor + OpenCode", seeds="101-103", runs=9, mean=0.06,
         note="the seeds the level was built on; Opus 5.5 scores 0.32 there"),
    dict(label="Gemma 4 26B-A4B + our adapter", harness="Harbor + OpenCode", seeds="101-103", runs=9, mean=0.26,
         note="the seeds the level was built on; Opus 5.5 scores 0.32 there"),
    dict(label="Gemma 4 26B-A4B, untrained", harness="own runner (rl/env.py), not comparable with Harbor",
         seeds="200000-200023", runs=96, mean=0.067, note="4 samples per seed"),
    dict(label="Gemma 4 26B-A4B + our adapter", harness="own runner (rl/env.py), not comparable with Harbor",
         seeds="200000-200023", runs=96, mean=0.587, note="4 samples per seed"),
]
SCRIPTED = [("reference", "Reference (expert script)"), ("shotgun", "`shotgun` script: finds the cause, guesses the fix"),
            ("nothing", "Do-nothing")]


def bootstrap(by_seed):
    rng = random.Random(0)
    seeds = sorted(by_seed)
    means = []
    for _ in range(RESAMPLES):
        draw = [x for s in (rng.choice(seeds) for _ in seeds) for x in by_seed[s]]
        means.append(sum(draw) / len(draw))
    means.sort()
    return means[int(0.025 * RESAMPLES)], means[int(0.975 * RESAMPLES) - 1]


def row(label, harness, runs):
    """runs: list of (seed, score, cost, cost_null)."""
    by_seed = {}
    for seed, score, _, _ in runs:
        by_seed.setdefault(seed, []).append(score)
    scores = [r[1] for r in runs]
    lo, hi = bootstrap(by_seed)
    return dict(label=label, harness=harness, runs=len(runs), seeds=len(by_seed),
                mean=round(st.mean(scores), 3), ci95=[round(lo, 3), round(hi, 3)],
                median=round(st.median(scores), 3),
                solve_rate=round(sum(s >= SOLVED for s in scores) / len(scores), 3),
                worse_than_nothing=round(sum(c > n + 1e-6 for _, _, c, n in runs) / len(runs), 3))


def main():
    scripted = {r["seed"]: r for r in json.loads((HERE / "loop-evidence" / "common-scripted.json").read_text())}
    rows = []
    for name, label in SCRIPTED:
        runs = [(s, scripted[s]["score"][name], scripted[s]["cost"][name], scripted[s]["cost_null"]) for s in SEEDS]
        rows.append(row(label, "scripted, replayed in the simulator", runs))
    metrics = json.loads((HERE / "metrics.json").read_text())
    for name, label in MODELS:
        runs = [(m["seed"], m["score"], m["sim_cost"], scripted[m["seed"]]["cost_null"]) for m in metrics
                if m["round"] == 16 and m["run"] == name and not m.get("failure", "").startswith("infrastructure")
                and m["seed"] in scripted]
        if runs:
            rows.append(row(label, "Harbor + OpenCode", runs))
    order = {label: i for i, (_, label) in enumerate([SCRIPTED[0], *MODELS, *SCRIPTED[1:]])}
    rows.sort(key=lambda r: order[r["label"]])
    out = dict(level=4, seeds="200000-200023", solved_threshold=SOLVED, ci="cluster bootstrap over seeds, "
               f"{RESAMPLES} resamples", definitions=__doc__.split("Definitions, fixed before the numbers were "
               "computed:\n")[1].strip(), rows=rows, separate=SEPARATE)
    (HERE / "results.json").write_text(json.dumps(out, indent=1) + "\n")
    print("| Agent | Harness | Runs / seeds | Mean (95% CI) | Median | Solve rate | Worse than doing nothing |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for r in rows:
        print(f"| {r['label']} | {r['harness']} | {r['runs']} / {r['seeds']} | {r['mean']:.2f} "
              f"({r['ci95'][0]:.2f}-{r['ci95'][1]:.2f}) | {r['median']:.2f} | {100 * r['solve_rate']:.0f}% | "
              f"{100 * r['worse_than_nothing']:.0f}% |")


if __name__ == "__main__":
    main()
