"""Scratch: the checks after search 1 (scratch/search.py). Plays trials of the study and the reference on seeds outside
the search, and prints each against the reference on the same seeds, a week under 90% on time counted as no margin.

    SPREAD_KEY=... PYTHONPATH=. uv run --with optuna python scratch/search_check.py --top 8 --seeds "$(cat seeds.txt)" --parallel 4
    ... --variants s1-606512f11c,s1-ec9048b9f5 --seeds ...     # these trials only
    ... --seeds ... --no-play                                  # the table from the saved weeks

--top takes the full trials with the highest J2 that have at most 1 of their 30 weeks under 90%, and adds the best
one with no week under 90% when it is not among them. A saved week is not played again. Stop it with
`touch data/search/STOP`.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import optuna

from spreadlab.play import load_score, play
from spreadlab.policy import fingerprint
from spreadlab.server import data_dir
from spreadlab.variants import REFERENCE

REFERENCE_NAME = "steep-notes-offers-8"
search = types.ModuleType("search")  # the search's points and how they become parameters, without running it
exec(compile(Path(__file__).with_name("search.py").read_text(encoding="utf-8").replace("\nmain()\n", "\n"), "search.py", "exec"), search.__dict__)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--top", type=int, default=0)
    parser.add_argument("--variants", default="", help="trial variants (s1-...), instead of --top")
    parser.add_argument("--parallel", type=int, default=4)
    parser.add_argument("--no-play", action="store_true")
    args = parser.parse_args()
    seeds = args.seeds.split(",")
    folder = data_dir() / "search"
    study = optuna.load_study(study_name="search1c", storage=f"sqlite:///{folder / 'search1.db'}")
    full = [t for t in study.get_trials() if "full" in t.user_attrs]
    by_name = {t.user_attrs["variant"]: t for t in full}
    if args.variants:
        chosen = [by_name[name] for name in args.variants.split(",")]
    else:
        within = sorted((t for t in full if t.user_attrs["full"]["under90"] <= 1), key=lambda t: -t.user_attrs["full"]["j2"])
        chosen = within[:args.top]
        clean = next((t for t in within if t.user_attrs["full"]["under90"] == 0), None)
        if clean is not None and clean not in chosen:
            chosen.append(clean)
    points = {REFERENCE_NAME: REFERENCE, **{t.user_attrs["variant"]: search.build(t.params) for t in chosen}}

    def week(name: str, seed: str):
        saved = load_score(name, seed)
        if saved is not None and (saved["fingerprint"] == fingerprint(points[name]) or search.same_parameters(saved, points[name])):
            return saved["score"]
        if args.no_play or (folder / "STOP").exists():
            return None
        try:
            return play(name, points[name], seed)["score"]
        except Exception as error:
            print(f"{name} {seed} failed: {error!r}", flush=True)
            return None

    todo = [(name, seed) for seed in seeds for name in points]
    with ThreadPoolExecutor(args.parallel) as pool:
        scores = dict(zip(todo, pool.map(lambda pair: week(*pair), todo)))
    print(f"{'trial':14} {'weeks':>5} {'margin':>7} {'<90% as 0, vs reference':>24} {'95% interval':>16} {'plain':>7} {'orders':>6} {'late':>5} {'<90':>4} {'<91':>4} {'lowest':>7} {'>=1.2x':>6} {'>=1.3x':>6}  search: J2, <90")
    for name in points:
        both = [s for s in seeds if scores[(name, s)] is not None and scores[(REFERENCE_NAME, s)] is not None]
        if not both:
            continue
        rows, base = [scores[(name, s)] for s in both], [scores[(REFERENCE_NAME, s)] for s in both]
        counted = [r["marginCents"] / 100 * (r["onTimeShare"] >= 0.90) - b["marginCents"] / 100 * (b["onTimeShare"] >= 0.90) for r, b in zip(rows, base)]
        plain = statistics.mean((r["marginCents"] - b["marginCents"]) / 100 for r, b in zip(rows, base))
        rng = random.Random(1)
        means = sorted(statistics.mean(rng.choices(counted, k=len(counted))) for _ in range(4000))
        at = lambda times: statistics.mean(r["ranked"] and r["marginCents"] >= times * b["marginCents"] for r, b in zip(rows, base))  # noqa: E731
        trial = by_name.get(name)
        print(f"{name:14} {len(both):5} {statistics.mean(r['marginCents'] for r in rows) / 100:7,.0f} {statistics.mean(counted):+24,.0f} {f'{means[100]:,.0f} to {means[3899]:,.0f}':>16} {plain:+7,.0f} "
              f"{statistics.mean(r['wonOrders'] for r in rows):6.0f} {statistics.mean((1 - r['onTimeShare']) * r['wonOrders'] for r in rows):5.1f} "
              f"{sum(r['onTimeShare'] < 0.90 for r in rows):4} {sum(r['onTimeShare'] < 0.91 for r in rows):4} {100 * min(r['onTimeShare'] for r in rows):6.1f}% {at(1.2):6.0%} {at(1.3):6.0%}"
              + (f"  {trial.user_attrs['full']['j2']:.0f}, {trial.user_attrs['full']['under90']}" if trial else ""))
    for name in points:
        if name != REFERENCE_NAME:
            print(name, json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in by_name[name].params.items()}))


main()
