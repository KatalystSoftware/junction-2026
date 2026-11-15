"""The benchmark table: every model and baseline on the 24 common level-4 seeds (200000-200023).

Reads metrics.json (round 16, Harbor + OpenCode runs; runs marked as infrastructure failures are
left out) and loop-evidence/common-scripted.json (scripted policies, from scripted_scores.py).
Writes results.json, which the README table and the deck render from, and prints the markdown.

    python3 results_table.py

Definitions for this table's calculations:
- score: (cost_do_nothing - cost) / (cost_do_nothing - cost_reference), clipped to 0..1.
- solve rate: share of runs scoring at least SOLVED (0.95) of the expert's score.
- worse than doing nothing: the run's cost is strictly above the do-nothing cost on its seed.
- a row needs runs on all 24 seeds; a partial set is listed under the table, not in it.
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

# Labels for the Harbor run names in metrics.json. Any other round-16 run name is shown as it is, so
# every model and adapter that ran appears; rows follow this order, unknown names last.
LABELS = {
    "fable": "Fable 5.2",
    "opus": "Opus 5.5",
    "gemma-base": "Gemma 4 26B-A4B, untrained",
    "nemotron-lightning": "Nemotron 3.5 Lightning 30B-A3B, untrained",
    "nemotron-super": "Nemotron 3.5 Super VL (NVFP4), untrained, served with vLLM",
    "gemma-ft": "Gemma 4 26B-A4B + our adapter (SFT, then RL on the score)",
    "gemma-sft-oc": "Gemma 4 26B-A4B + our adapter (SFT in OpenCode's format)",
}
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
    r = dict(label=label, harness=harness, runs=len(runs), seeds=len(by_seed),
             mean=st.mean(scores), ci95=[lo, hi], median=st.median(scores),
             solve_rate=sum(s >= SOLVED for s in scores) / len(scores),
             worse_than_nothing=sum(c > n + 1e-6 for _, _, c, n in runs) / len(runs))
    # Raw values above stay at full precision; display strings are rounded once, from the raw values.
    r["display"] = dict(mean=f"{r['mean']:.2f}", ci95=[f"{lo:.2f}", f"{hi:.2f}"], median=f"{r['median']:.2f}",
                        solve_rate=f"{100 * r['solve_rate']:.0f}%",
                        worse_than_nothing=f"{100 * r['worse_than_nothing']:.0f}%")
    return r


def main():
    scripted = {r["seed"]: r for r in json.loads((HERE / "loop-evidence" / "common-scripted.json").read_text())}
    scripted_rows = []
    for name, label in SCRIPTED:
        runs = [(s, scripted[s]["score"][name], scripted[s]["cost"][name], scripted[s]["cost_null"]) for s in SEEDS]
        scripted_rows.append(row(label, "scripted, replayed in the simulator", runs))

    metrics = json.loads((HERE / "metrics.json").read_text())
    names = sorted({m["run"] for m in metrics if m["round"] == 16},
                   key=lambda n: (list(LABELS).index(n) if n in LABELS else len(LABELS), n))
    model_rows, partial = [], []
    for name in names:
        runs = [(m["seed"], m["score"], m["sim_cost"], scripted[m["seed"]]["cost_null"]) for m in metrics
                if m["round"] == 16 and m["run"] == name and not m.get("failure", "").startswith("infrastructure")
                and m["seed"] in scripted]
        if not runs:
            continue
        r = row(LABELS.get(name, name), "Harbor + OpenCode", runs)
        if r["seeds"] == len(SEEDS):
            model_rows.append(r)
        else:
            partial.append(dict(label=r["label"], runs=r["runs"], seeds=r["seeds"], mean=r["mean"],
                                ci95=r["ci95"], display=r["display"]))

    rows = [scripted_rows[0], *model_rows, *scripted_rows[1:]]
    out = dict(level=4, seeds="200000-200023", solved_threshold=SOLVED,
               ci=f"cluster bootstrap over seeds, {RESAMPLES} resamples",
               definitions=__doc__.split("calculations:\n")[1].strip(), rows=rows, partial=partial)
    (HERE / "results.json").write_text(json.dumps(out, indent=1) + "\n")

    print("| Agent | Harness | Runs / seeds | Mean (95% CI) | Median | Solve rate | Worse than doing nothing |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for r in rows:
        d = r["display"]
        print(f"| {r['label']} | {r['harness']} | {r['runs']} / {r['seeds']} | {d['mean']} "
              f"({d['ci95'][0]}-{d['ci95'][1]}) | {d['median']} | {d['solve_rate']} | {d['worse_than_nothing']} |")
    for r in partial:
        print(f"\nPartial, so not in the table: {r['label']}, {r['runs']} runs on {r['seeds']} of {len(SEEDS)} "
              f"seeds (mean {r['display']['mean']}, 95% CI {r['display']['ci95'][0]}-{r['display']['ci95'][1]}).")


if __name__ == "__main__":
    main()
