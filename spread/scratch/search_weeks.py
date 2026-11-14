"""Scratch: writes every week of search 1 to data/search/search1-weeks.csv, one row a week, so that another objective
can be read from the same trials without playing them again. Run it at any time; it writes the whole file anew.

    PYTHONPATH=. uv run --with optuna python scratch/search_weeks.py

Each row has the fingerprint of the policy it was played under and that of the reference's saved week on the seed.
`sameFingerprint` says whether they agree; where they do not, the policy file differed only in parameters that are
off at their default, and the reference replayed to the same margins after each such edit.
"""
from __future__ import annotations

import csv
import json
import statistics

import optuna

from spreadlab.play import load_score
from spreadlab.server import data_dir

REFERENCE = "steep-notes-offers-8"


def main() -> None:
    folder = data_dir() / "search"
    storage = f"sqlite:///{folder / 'search1.db'}"
    trials, seen = [], set()
    for name in ("search1d", "search1c", "search1b", "search1"):
        try:
            study = optuna.load_study(study_name=name, storage=storage)
        except KeyError:
            continue
        for trial in study.get_trials():
            variant = trial.user_attrs.get("variant")
            if variant and "rung1" in trial.user_attrs and variant not in seen:
                seen.add(variant)
                trials.append((name, trial))
    rows, frontier = [], []
    for study_name, trial in trials:
        variant, weeks = trial.user_attrs["variant"], []
        for path in sorted((data_dir() / "runs" / variant).glob("*-L8.score.json")):
            saved = json.loads(path.read_text(encoding="utf-8"))
            reference = load_score(REFERENCE, saved["seed"])
            score, base = saved["score"], reference["score"]
            weeks.append((score, base))
            rows.append({"study": study_name, "trial": trial.number, "state": trial.state.name, "variant": variant, "params": json.dumps(trial.params, sort_keys=True),
                         "rung": 2 if "full" in trial.user_attrs else 1, "seed": saved["seed"], "marginCents": score["marginCents"], "wonOrders": score["wonOrders"],
                         "onTimeShare": score["onTimeShare"], "ranked": score["ranked"], "fingerprint": saved["fingerprint"],
                         "referenceMarginCents": base["marginCents"], "referenceOnTimeShare": base["onTimeShare"], "referenceFingerprint": reference["fingerprint"],
                         "sameFingerprint": saved["fingerprint"] == reference["fingerprint"]})
        if "full" in trial.user_attrs and len(weeks) == 30:
            share = lambda times: statistics.mean(s["ranked"] and s["marginCents"] >= times * b["marginCents"] for s, b in weeks)  # noqa: E731
            j2 = statistics.mean(s["marginCents"] / 100 * (s["onTimeShare"] >= 0.90) - b["marginCents"] / 100 for s, b in weeks)
            frontier.append({**trial.user_attrs["full"], "j2": round(j2, 1), "trial": trial.number, "study": study_name, "variant": variant, "at1.2": round(share(1.2), 3),
                             "at1.3": round(share(1.3), 3), "params": trial.params})
    with open(folder / "search1-weeks.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} weeks of {len(trials)} trials -> {folder / 'search1-weeks.csv'}")
    print(f"{'trial':>9} {'J2':>7} {'margin':>7} {'vs ref':>7} {'orders':>6} {'late':>5} {'lowest':>6} {'<90':>3} {'<91':>3} {'<92':>3} {'>=1.2x':>6} {'>=1.3x':>6}  parameters")
    for row in sorted(frontier, key=lambda r: -r["j2"]):
        short = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in row["params"].items()}
        print(f"{row['study'][-2:]:>3}{row['trial']:>6} {row['j2']:7.0f} {row['margin']:7.0f} {row['vsReference']:+7.0f} {row['orders']:6.0f} {row['late']:5.1f} {row['lowest']:6.1f} "
              f"{row['under90']:3} {row['under91']:3} {row['under92']:3} {row['at1.2']:6.0%} {row['at1.3']:6.0%}  {json.dumps(short)}")


main()
