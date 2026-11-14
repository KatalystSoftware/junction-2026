"""Scratch: search 1, a joint search over the reference's constants with the late chance priced into each quote
(Optuna, TPE). Every trial plays the same practice seeds as the reference, in two rungs, and is scored against it.

    SPREAD_KEY=... PYTHONPATH=. uv run --with optuna python scratch/search.py --parallel 3 --until 11:43

The candidate for the final is chosen on its chance of a top-10 week with at most 1 week in 20 not ranked. No practice
world shows the bar of the top 10, so mean margin stands in for it:

    J2 = mean over the seeds of [margin x 1{on time >= 90%} - the reference's margin], in euros

A trial is within the limit with none of its 30 weeks under 90%: whatever plays a ranking round or the final may have
at most 1 week in 60 there. The sampler gets J2 - 2,000 for each week under 90%, and - 200 for each week from 90% to
under 92%, the aim: such a week is under 90% in 9% of the other full trials on the same seed, a tenth of the charge.
A trial stops after rung 1 (8 seeds, the 4 with the fewest drivers among them) when a week there is under 90%, or when
its margin against the reference there is more than 1,000 under the best so far: the 8 seeds are hard for every
variant, and a mean of 8 paired differences has a standard error of about 390.

The study is in data/search/search1.db and survives a restart: a trial that a stop cut short is queued again, and its
saved weeks are not played again. Stop it with `touch data/search/STOP` or --until. The first objective (J: a week
under 91% as no margin, and 300 for each point under 93%) scored the studies `search1` and `search1b` in the same file;
their trials started the study `search1c`.

`search1d` starts from its trials in turn and has the default (`slow-friday-late-150-kinds-limits`) to beat, not the
reference. J2 stays against the reference, so that the saved trials compare; each summary also has `vsDefault`, the
margin against the default on the same seeds. Three switches are parameters, off in every trial before it: the kinds,
the note's limits and the Friday late model. Seven points are played first, in full: the default, the best trial before
it with the three switches on, the default with one part of that trial each, and the default with the 90% rule's price. Every sampled trial has the three
switches on. The search stops when, after those and 30 sampled trials, no full trial is more than 300 above the
default: 60 unseen seeds cannot confirm a smaller gain.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import statistics
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor

import optuna

from spreadlab.catalogue import load_catalogue, load_seeds
from spreadlab.play import load_score, play
from spreadlab.policy import DEFAULTS, fingerprint
from spreadlab.server import data_dir
from spreadlab.variants import KINDS, REFERENCE, VARIANTS

REFERENCE_NAME = "steep-notes-offers-8"
PRUNE_UNDER = 1000  # a trial stops after rung 1 when its margin against the reference there is this far under the best so far
OVER_LIMIT = 2000  # what the sampler takes off J2 for each week under 90%
AIM, UNDER_AIM = 0.92, 200  # ... and for each week from 90% to under the aim
# The points to play first, as the search's parameters. `GUARD` is the mildest guard the ranges allow.
BASE = {"guard": "on", "cost": 1.3, "late_cost": 0.0, "backlog_step": 0.04, "slow_step": 0.0, "backlog_hours": 0, "max_unbooked": 15, "fee": 1.0, "fee_cap": 1.2, "f_short": 1.0, "offer_hours": 8}
GUARD = {"min_on_time": 0.93, "rule_cost": 200.0, "behind_max_unbooked": 15}
FIRST = [
    {**BASE, **GUARD},                                                   # the reference, with the mildest guard
    {**BASE, **GUARD, "backlog_hours": 24, "max_unbooked": 25},          # due-24-gate-25
    {**BASE, **GUARD, "cost": 1.15, "late_cost": 150.0},                 # the cost by the late chance in place of a flat 1.3
    {**BASE, "cost": 1.15, "late_cost": 100.0, "backlog_step": 0.02, "backlog_hours": 24, "max_unbooked": 25,
     "min_on_time": 0.95, "rule_cost": 600.0, "behind_max_unbooked": 12},  # aggressive, with a guard
]
# Queued when `slow_step` joined the search and `late_cost` went to 400.
SECOND = [
    {**BASE, **GUARD, "backlog_step": 0.0, "slow_step": 0.8, "max_unbooked": 25},  # slow-step-gate-25
    {**BASE, "cost": 1.19, "late_cost": 225.0, "backlog_step": 0.02, "backlog_hours": 24, "max_unbooked": 40, "min_on_time": 0.93, "rule_cost": 900.0, "behind_max_unbooked": 12},
    {**BASE, "cost": 1.19, "late_cost": 225.0, "backlog_step": 0.02, "backlog_hours": 24, "max_unbooked": 25, "min_on_time": 0.93, "rule_cost": 900.0, "behind_max_unbooked": 12},
    {**BASE, **GUARD, "cost": 1.20, "late_cost": 240.0},  # the late cost alone
]
# Queued when the objective became J2 and the guard got an off: the points without it. The guard's three parameters are then not read.
THIRD = [
    {**BASE, **GUARD, "guard": "off", "cost": 1.19, "late_cost": 225.0, "backlog_step": 0.02, "backlog_hours": 24, "max_unbooked": 40},
    {**BASE, **GUARD, "guard": "off", "backlog_step": 0.0, "slow_step": 0.8, "max_unbooked": 25},  # slow-step-gate-25 as it is in variants.py
]
# Queued when the switches joined the search (`search1d`), and played in full whatever their first rung: the default, the best
# trial before it with the switches on, and the default with one part of that trial each.
DEFAULT_NAME = "slow-friday-late-150-kinds-limits"
ON = {"kinds": "on", "note_limits": "on", "late_model": "friday"}
OFF = {"kinds": "off", "note_limits": "off", "late_model": "plain"}
DEFAULT = {**BASE, **GUARD, "guard": "off", "cost": 1.2, "late_cost": 150.0, "backlog_step": 0.0, "slow_step": 0.8, "max_unbooked": 25, **ON}
RULE_PRICE = {"guard": "on", "min_on_time": 0.93, "rule_cost": 900.0, "behind_max_unbooked": 12}  # the default with the 90% rule's price on while behind
BEST = "s1-a75fecb071"
PARTS = [["max_unbooked"], ["fee", "fee_cap", "f_short"], ["backlog_step", "backlog_hours"], ["cost", "late_cost"]]
ENOUGH, SAMPLED = 300, 30  # the search ends when no full trial is over ENOUGH above the default after the queued points and SAMPLED sampled trials


class Stopped(Exception):
    pass


Float, Choice = optuna.distributions.FloatDistribution, optuna.distributions.CategoricalDistribution
SPACE = {
    "guard": Choice(["on", "off"]),        # off: no `min_on_time`, no price of the 90% rule and no gate of its own while behind
    "cost": Float(1.05, 1.30),             # fees and failed visits per typical fee, without lateness
    "late_cost": Float(0, 400),            # euros for a late order: refund and trust
    "backlog_step": Float(0, 0.05),        # what a waiting car adds to the next order's cost
    "slow_step": Float(0, 1.5),            # ... and what it adds x the next order's late chance
    "backlog_hours": Choice([0, 24]),      # which waiting cars `backlog_step` counts
    "max_unbooked": Choice([15, 20, 25, 30, 40]),
    "min_on_time": Float(0.930, 0.965),    # the desk is behind under this projected on-time share
    "rule_cost": Float(200, 1500, log=True),  # the 90% rule's price while behind
    "behind_max_unbooked": Choice([8, 12, 15]),
    "fee": Float(0.95, 1.10),
    "fee_cap": Float(1.15, 1.50),
    "f_short": Float(1.0, 1.4),            # the opening fee of an order with under 8 hours to find a driver
    "offer_hours": Choice([8, 12, 24]),
    "kinds": Choice(["off", "on"]),        # on: private pickups, private deliveries and trade-ins are quoted (KINDS in variants.py)
    "note_limits": Choice(["off", "on"]),  # on: gigs are posted within the hours, the deadline and the ready time that the note gives
    "late_model": Choice(["plain", "friday"]),  # friday: the late chance knows the day of the week
}


def suggest(trial: optuna.Trial) -> dict:
    return {name: trial.suggest_categorical(name, d.choices) if isinstance(d, Choice) else trial.suggest_float(name, d.low, d.high, log=d.log) for name, d in SPACE.items()}


def build(t: dict) -> dict:
    """The policy's parameters for a point of the search."""
    params = {**REFERENCE, "cost": t["cost"], "late_cost": t["late_cost"], "backlog_step": t["backlog_step"], "slow_step": t["slow_step"], "backlog_hours": t["backlog_hours"],
              "max_unbooked": t["max_unbooked"], "fee": t["fee"], "fee_cap": t["fee_cap"], "offer_hours": t["offer_hours"]}
    if t["guard"] == "on":
        params.update({"min_on_time": t["min_on_time"], "behind_from": 40,
                       "when_behind": {"rule_cost": t["rule_cost"], "max_unbooked": t["behind_max_unbooked"], "backlog_hours": 0, "backlog_step": max(0.04, t["backlog_step"])}})
    if t["f_short"] > t["fee"]:  # an order with under 8 hours to find a driver opens higher; at or under `fee` it opens as the others
        params["fee_rules"] = [[0, 10 ** 6, 0, 8, t["f_short"], 0.1, max(t["f_short"], t["fee_cap"]) + 0.2]]
    if t.get("kinds") == "on":
        params["kinds"] = KINDS
    if t.get("note_limits") == "on":
        params["note_limits"] = True
    if t.get("late_model") == "friday":
        params["slow_model"] = "friday"
    return params


def first_points(best: dict) -> list[dict]:
    return [DEFAULT, {**best, **ON}] + [{**DEFAULT, **{name: best[name] for name in part}} for part in PARTS] + [{**DEFAULT, **RULE_PRICE}]


def name_of(t: dict) -> str:
    # A point with the guard and without `slow_step` keeps the name it had before those parameters joined the search, and so
    # its saved weeks. Without the guard, its three parameters are not read and not part of the name.
    # The default's point has the default's name, and so its saved weeks.
    if json.loads(json.dumps({**DEFAULTS, **build(t)})) == json.loads(json.dumps({**DEFAULTS, **VARIANTS[DEFAULT_NAME]})):
        return DEFAULT_NAME
    off = t["guard"] == "off"
    named = {k: v for k, v in t.items() if not (k == "slow_step" and not v) and not (k == "guard" and not off) and not (off and k in GUARD) and OFF.get(k) != v}
    return "s1-" + hashlib.sha256(json.dumps(named, sort_keys=True).encode()).hexdigest()[:10]


def same_parameters(saved: dict, params: dict) -> bool:
    """Whether a saved week of a trial was played with these parameters. The policy file has gained parameters since
    the first trials, each off at its default, so the fingerprint of an older week differs while the play is the same:
    the reference replays to the same margins after each such edit."""
    return all(saved["params"].get(name, DEFAULTS[name]) == value for name, value in json.loads(json.dumps({**DEFAULTS, **params})).items())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parallel", type=int, default=5, help="practice worlds at a time")
    parser.add_argument("--jobs", type=int, default=2, help="trials at a time")
    parser.add_argument("--trials", type=int, default=250)
    parser.add_argument("--until", default="", help="HH:MM UTC today: no week starts after it")
    args = parser.parse_args()
    folder = data_dir() / "search"
    folder.mkdir(parents=True, exist_ok=True)
    stop_file, requeued_file = folder / "STOP", folder / "search1d-requeued.json"
    until = None
    if args.until:
        hour, minute = map(int, args.until.split(":"))
        until = datetime.datetime.now(datetime.timezone.utc).replace(hour=hour, minute=minute, second=0, microsecond=0)

    def stopping() -> bool:
        return stop_file.exists() or (until is not None and datetime.datetime.now(datetime.timezone.utc) >= until)

    seeds = load_seeds("tune", 30)
    drivers = {seed: row["drivers"] for seed, row in load_catalogue().items() if seed in seeds}
    by_count = sorted(seeds, key=lambda s: drivers[s])
    median = statistics.median(drivers.values())
    rung1 = by_count[:4] + sorted(by_count[4:], key=lambda s: abs(drivers[s] - median))[:4]
    rung2 = [s for s in seeds if s not in rung1]
    pool = ThreadPoolExecutor(args.parallel)

    flying: dict[tuple[str, str], Future] = {}  # the weeks that are being played, so that no week is played twice at once
    flying_lock = threading.Lock()

    def week(name: str, params: dict, seed: str) -> dict:
        with flying_lock:
            mine = (name, seed) not in flying
            future = flying.setdefault((name, seed), Future())
        if not mine:
            return future.result()
        try:
            future.set_result(week_(name, params, seed))
        except BaseException as error:
            future.set_exception(error)
        finally:
            with flying_lock:
                del flying[(name, seed)]
        return future.result()

    def week_(name: str, params: dict, seed: str) -> dict:
        saved = load_score(name, seed)
        # A saved week with these parameters stands, the reference's too: it replays to the same margins after each edit of the policy file.
        if saved is not None and (saved["fingerprint"] == fingerprint(params) or same_parameters(saved, params)):
            return saved["score"]
        for attempt in range(2):
            if stopping():
                raise Stopped()
            try:
                return play(name, params, seed)["score"]
            except Exception as error:  # a week that failed is played once more
                if attempt:
                    raise
                print(f"{name} {seed} failed, once more: {error!r}", flush=True)
                time.sleep(5)

    def play_all(name: str, params: dict, some: list[str]) -> dict[str, dict]:
        return dict(zip(some, pool.map(lambda seed: week(name, params, seed), some)))

    print(f"rung 1: {[(s, drivers[s]) for s in rung1]}; rung 2: {len(rung2)} seeds; median {median} drivers", flush=True)
    reference = play_all(REFERENCE_NAME, REFERENCE, seeds)

    # The default's weeks so far; its trial, the first of the queue, plays the rest.
    default = {seed: row["score"] for seed in seeds if (row := load_score(DEFAULT_NAME, seed)) is not None and same_parameters(row, VARIANTS[DEFAULT_NAME])}

    def versus_default(scores: dict[str, dict]) -> float | None:
        if not all(s in default for s in scores):
            return None
        return round(statistics.mean((scores[s]["marginCents"] - default[s]["marginCents"]) / 100 for s in scores), 1)

    def under(scores: dict[str, dict], share: float = 0.90) -> int:
        return sum(r["onTimeShare"] < share for r in scores.values())

    def versus(scores: dict[str, dict]) -> float:
        """The mean margin against the reference on the same seeds, no week counted as lost."""
        return statistics.mean((scores[s]["marginCents"] - reference[s]["marginCents"]) / 100 for s in scores)

    def j2(scores: dict[str, dict]) -> float:
        return statistics.mean(scores[s]["marginCents"] / 100 * (scores[s]["onTimeShare"] >= 0.90) - reference[s]["marginCents"] / 100 for s in scores)

    def j(scores: dict[str, dict]) -> float:  # the first objective, kept in the summaries
        gain = statistics.mean(scores[s]["marginCents"] / 100 * (scores[s]["onTimeShare"] >= 0.91) - reference[s]["marginCents"] / 100 for s in scores)
        return gain - 300 * statistics.mean(max(0.0, 93 - 100 * scores[s]["onTimeShare"]) for s in scores)

    def summary(scores: dict[str, dict]) -> dict:
        at = lambda times: statistics.mean(scores[s]["ranked"] and scores[s]["marginCents"] >= times * reference[s]["marginCents"] for s in scores)  # noqa: E731
        return {"weeks": len(scores), "j2": round(j2(scores), 1), "j": round(j(scores), 1), "margin": round(statistics.mean(r["marginCents"] for r in scores.values()) / 100, 1),
                "vsReference": round(versus(scores), 1), "vsDefault": versus_default(scores),
                "orders": round(statistics.mean(r["wonOrders"] for r in scores.values()), 1),
                "late": round(statistics.mean((1 - r["onTimeShare"]) * r["wonOrders"] for r in scores.values()), 1),
                "lowest": round(100 * min(r["onTimeShare"] for r in scores.values()), 1), "under90": under(scores), "under91": under(scores, 0.91), "under92": under(scores, 0.92),
                "at1.2": round(at(1.2), 3), "at1.3": round(at(1.3), 3)}

    def value_of(scores: dict[str, dict]) -> float:
        return j2(scores) - OVER_LIMIT * under(scores) - UNDER_AIM * (under(scores, AIM) - under(scores))

    print(f"reference on S: {json.dumps(summary(reference))}; on rung 1: {json.dumps(summary({s: reference[s] for s in rung1}))}", flush=True)
    storage = f"sqlite:///{folder / 'search1.db'}"
    study = optuna.create_study(study_name="search1d", storage=storage, direction="maximize", load_if_exists=True)
    if not study.get_trials(deepcopy=False):
        # The trials of the study before it, with the switches off, scored again from their saved weeks. One that was played
        # in full is a full trial, one with its first rung a stopped trial; none is played on, because none has the switches.
        try:
            before = optuna.load_study(study_name="search1c", storage=storage).get_trials()
        except KeyError:
            before = []
        played, was = [], {}
        for trial in before:
            point = {**OFF, **trial.params}
            if set(point) != set(SPACE):
                continue
            name = name_of(point)
            was.setdefault(name, f"search1c {trial.number}")
            saved = {seed: load_score(name, seed) for seed in seeds}
            weeks = {seed: row["score"] for seed, row in saved.items() if row is not None and same_parameters(row, build(point))}
            played.append((point, name, weeks))
        seen = set()
        for point, name, weeks in played:
            if name in seen:
                continue
            seen.add(name)
            first = {s: weeks[s] for s in rung1 if s in weeks}
            if len(weeks) == len(seeds):
                study.add_trial(optuna.trial.create_trial(params=point, distributions=SPACE, value=value_of(weeks),
                                                          user_attrs={"was": was[name], "variant": name, "rung1": summary(first), "full": summary(weeks)}))
            elif len(first) == len(rung1):
                study.add_trial(optuna.trial.create_trial(state=optuna.trial.TrialState.PRUNED, params=point, distributions=SPACE, intermediate_values={0: versus(first)},
                                                          user_attrs={"was": was[name], "variant": name, "rung1": summary(first)}))
        points = {name: point for point, name, _ in played}
        for point in first_points(points[BEST]) if BEST in points else [DEFAULT] + [{**OFF, **point} for point in FIRST + SECOND + THIRD]:
            study.enqueue_trial(point)
    # A fixed seed draws the same points after every restart, so the seed follows the trials that the study has. The sampler
    # draws the numbers only: the three switches are on in every trial it draws.
    study.sampler = optuna.samplers.PartialFixedSampler(ON, optuna.samplers.TPESampler(multivariate=True, n_startup_trials=24, seed=1 + len(study.get_trials(deepcopy=False))))
    # After a restart: the trials that a stop cut short are queued again, once. Their saved weeks are not played again.
    requeued = set(json.loads(requeued_file.read_text())) if requeued_file.exists() else set()
    for trial in study.get_trials(deepcopy=False):
        cut = trial.state == optuna.trial.TrialState.RUNNING or (trial.state == optuna.trial.TrialState.FAIL and "full" not in trial.user_attrs)
        if cut and trial.number not in requeued and len(trial.params) == len(SPACE):
            if trial.state == optuna.trial.TrialState.RUNNING:
                study._storage.set_trial_state_values(trial._trial_id, state=optuna.trial.TrialState.FAIL)
            study.enqueue_trial(trial.params)
            requeued.add(trial.number)
    requeued_file.write_text(json.dumps(sorted(requeued)))
    start = next((t.params for t in study.get_trials(deepcopy=False) if t.user_attrs.get("variant") == BEST and len(t.params) == len(SPACE)), None)
    no_stop = {name_of(point) for point in first_points(start)} if start else {DEFAULT_NAME}
    lock = threading.Lock()
    done = [t for t in study.get_trials(deepcopy=False) if "rung1" in t.user_attrs]
    best = {"rung1": max((t.user_attrs["rung1"]["vsReference"] for t in done), default=float("-inf"))}

    def objective(trial: optuna.Trial) -> float:
        point = suggest(trial)
        name, params = name_of(point), build(point)
        trial.set_user_attr("variant", name)
        trial.set_user_attr("source", "queued" if name in no_stop else "sampled")
        first = play_all(name, params, rung1)
        value = versus(first)
        trial.set_user_attr("rung1", summary(first))
        trial.report(value, 0)
        with lock:
            pruned = name not in no_stop and (under(first) >= 1 or value < best["rung1"] - PRUNE_UNDER)
            best["rung1"] = max(best["rung1"], value)
        if pruned:
            print(f"trial {trial.number} {name} pruned  rung 1 {json.dumps(summary(first))}  {json.dumps(point)}", flush=True)
            raise optuna.TrialPruned()
        scores = {**first, **play_all(name, params, rung2)}
        if name == DEFAULT_NAME:
            default.update(scores)
        trial.set_user_attr("full", summary(scores))
        print(f"trial {trial.number} {name} full  {json.dumps(summary(scores))}  rung 1 vs reference {value:.0f}  {json.dumps(point)}", flush=True)
        return value_of(scores)

    def enough(trials: list[optuna.trial.FrozenTrial]) -> bool:
        """Whether the search has had its chance: the queue is empty, SAMPLED sampled trials are done, and no full trial is
        more than ENOUGH above the default."""
        ended = (optuna.trial.TrialState.COMPLETE, optuna.trial.TrialState.PRUNED)
        sampled = sum(t.user_attrs.get("source") == "sampled" and t.state in ended for t in trials)
        above = [t.user_attrs["full"]["vsDefault"] for t in trials if t.user_attrs.get("full", {}).get("vsDefault") is not None and t.user_attrs["variant"] != DEFAULT_NAME]
        return not any(t.state == optuna.trial.TrialState.WAITING for t in trials) and sampled >= SAMPLED and max(above, default=0) <= ENOUGH

    def stop_when_asked(study_: optuna.Study, trial: optuna.trial.FrozenTrial) -> None:
        if stopping():
            study_.stop()
        elif enough(study_.get_trials(deepcopy=False)):
            print(f"the search ends: after the queued points and {SAMPLED} sampled trials no full trial is more than {ENOUGH} above the default", flush=True)
            study_.stop()

    finished = sum(t.state in (optuna.trial.TrialState.COMPLETE, optuna.trial.TrialState.PRUNED) for t in study.get_trials(deepcopy=False))
    # The queued points one at a time: with SQLite two threads can take the same queued trial.
    waiting = sum(t.state == optuna.trial.TrialState.WAITING for t in study.get_trials(deepcopy=False))
    if not stopping() and waiting:
        study.optimize(objective, n_trials=waiting, n_jobs=1, catch=(Exception,), callbacks=[stop_when_asked])
    finished = sum(t.state in (optuna.trial.TrialState.COMPLETE, optuna.trial.TrialState.PRUNED) for t in study.get_trials(deepcopy=False))
    if not stopping() and finished < args.trials:
        study.optimize(objective, n_trials=args.trials - finished, n_jobs=args.jobs, catch=(Exception,), callbacks=[stop_when_asked])
    states = [t.state.name for t in study.get_trials(deepcopy=False)]
    print(f"stopped: {({s: states.count(s) for s in set(states)})}", flush=True)


main()
