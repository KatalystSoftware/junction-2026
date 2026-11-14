"""The outer search, run offline on the stand-in (sim.py): Optuna's TPE over the quote-side parameters of the per-decision
optimiser, on paired weeks, with the objective of sim.loss. Tunes on every other saved week and checks the best on the rest.
With `top10` the objective is J90 of sim.loss with at most 1 week in 20 under 90%, and the 90% rule's price can be off.
PYTHONPATH=. uv run --with numpy --with optuna python -u scratch/opt/search.py <data> <cache> [trials] [react] [top10]"""
import json, sys
from multiprocessing import Pool
import numpy as np
import optuna
from sim import Weeks, simulate, reference_rule, shadow_rule, loss

data, cache = sys.argv[1:3]
TRIALS = int(sys.argv[3]) if len(sys.argv) > 3 else 120
REACT = float(sys.argv[4]) if len(sys.argv) > 4 else 0.6
TOP10 = len(sys.argv) > 5 and sys.argv[5] == "top10"  # choose on mean margin with at most 1 week in 20 under 90%, in place of J
weeks = Weeks(data, cache)
everything = list(range(len(weeks.W)))
TUNE, HOLDOUT = everything[0::2], everything[1::2]
weeks.fit(TUNE)  # the late model sees the tune weeks only; each week keeps its own intercept, which stands for how hard its world is
HOURS = [[6, 1.55], [8, 1.35], [12, 1.3], [30, 1.2]]
NAMED = {
    "reference": None,
    "due-24-gate-25 (played: +688, 2 of 60 weeks under 91%)": dict(step_hours=24, gate=25),
    "hours-due-24-gate-25 (played: +479 on 10)": dict(cost=1.15, hours=HOURS, step_hours=24, gate=25),
}

def run(job):
    params, on = job
    return simulate(weeks, reference_rule if params is None else shadow_rule(weeks, **params), on, 0, react=REACT)

def evaluate(pool, params_list, on, ref):
    chunks = [on[i::2] for i in range(2)]
    parts = pool.map(run, [(p, c) for p in params_list for c in chunks])
    out = []
    for i in range(len(params_list)):
        rows = sorted(parts[2 * i] + parts[2 * i + 1], key=lambda r: r["w"])
        out.append(loss(rows, ref))
    return out

def suggest(trial):
    p = {"cost": trial.suggest_float("cost", 1.05, 1.35), "late_cost": trial.suggest_float("late_cost", 0, 400 if TOP10 else 300), "step": trial.suggest_float("step", 0.0, 0.05),
         "step_hours": trial.suggest_categorical("step_hours", [0, 24]), "gate": trial.suggest_categorical("gate", [15, 20, 25, 30, 40]),
         "min_on_time": trial.suggest_float("min_on_time", 0.93, 0.965), "rule_cost": trial.suggest_float("rule_cost", 200, 1500, log=True),
         "behind_gate": trial.suggest_categorical("behind_gate", [8, 12, 15])}
    if TOP10 and trial.suggest_categorical("guard", ["on", "off"]) == "off":
        p["min_on_time"] = 0.0
    return p


def value(r, n):
    """What the sampler maximises."""
    return r["J90"] - 2000 * max(0, r["under90"] - n // 20) if TOP10 else r["J"]

if __name__ == "__main__":
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    show = lambda name, r: print(f"{name:62} J {r['J']:+6.0f}  J90 {r['J90']:+6.0f}  margin {r['margin']:+6.0f}  orders {r['orders']:5.1f}  late {r['late']:4.1f}  lowest {100 * r['lowest']:.1f}%  weeks under 90/91/92%: {r['under90']}/{r['under91']}/{r['under92']}")
    with Pool(4) as pool:
        ref = {"tune": sorted(run((None, TUNE)), key=lambda r: r["w"]), "holdout": sorted(run((None, HOLDOUT)), key=lambda r: r["w"])}
        print(f"stand-in with react {REACT}; tune {len(TUNE)} weeks, holdout {len(HOLDOUT)} weeks; margins are differences to the reference, a week")
        for name, params in NAMED.items():
            show("tune     " + name, evaluate(pool, [params], TUNE, ref["tune"])[0]); show("holdout  " + name, evaluate(pool, [params], HOLDOUT, ref["holdout"])[0])
        study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(multivariate=True, n_startup_trials=24, seed=1, constant_liar=True))
        guard = {"guard": "on"} if TOP10 else {}
        study.enqueue_trial({"cost": 1.3, "late_cost": 0, "step": 0.04, "step_hours": 0, "gate": 15, "min_on_time": 0.93, "rule_cost": 200, "behind_gate": 15, **guard})
        study.enqueue_trial({"cost": 1.15, "late_cost": 100, "step": 0.02, "step_hours": 24, "gate": 25, "min_on_time": 0.95, "rule_cost": 600, "behind_gate": 12, **guard})
        if TOP10:
            study.enqueue_trial({"cost": 1.19, "late_cost": 225, "step": 0.02, "step_hours": 24, "gate": 40, "min_on_time": 0.93, "rule_cost": 900, "behind_gate": 12, "guard": "off"})
        done, log = 0, []
        while done < TRIALS:
            trials = [study.ask() for _ in range(2)]
            params = [suggest(t) for t in trials]
            for t, p, r in zip(trials, params, evaluate(pool, params, TUNE, ref["tune"])):
                study.tell(t, value(r, len(TUNE))); log.append((value(r, len(TUNE)), p, r)); done += 1
            if done % 20 == 0:
                print(f"  {done} trials, best on tune {study.best_value:+.0f}", flush=True)
        log.sort(key=lambda x: -x[0])
        print("\nthe 6 best on tune, then on the holdout weeks")
        top = log[:6]
        hold = evaluate(pool, [p for _, p, _ in top], HOLDOUT, ref["holdout"])
        for (j, p, r), h in zip(top, hold):
            print(json.dumps({k: round(v, 3) if isinstance(v, float) else v for k, v in p.items()}))
            show("  tune", r); show("  holdout", h)
        best = top[int(np.argmax([value(h, len(HOLDOUT)) for h in hold]))][1]
        print("\nwhat each part of the best-on-holdout point is worth, on the holdout weeks")
        variants = {"best": best, "without the 90% rule's price (rule_cost 0, same gates)": {**best, "min_on_time": 0.0},
                    "without the late cost": {**best, "late_cost": 0.0},
                    "behind: every order dearer instead (cost + 0.3), no rule price": None}
        for (name, p), r in zip(variants.items(), evaluate(pool, [p for p in variants.values() if p is not None], HOLDOUT, ref["holdout"])):
            show("  " + name, r)
        key = "under90" if TOP10 else "under91"
        print(f"\nfrontier on tune: the best margin at each count of weeks {key[:5]} {key[5:]}%")
        for k in sorted({r[key] for _, _, r in log}):
            j, p, r = max((x for x in log if x[2][key] == k), key=lambda x: x[2]["margin"])
            show(f"  {k} weeks {key[:5]} {key[5:]}%", r)
            print("    " + json.dumps({a: round(v, 3) if isinstance(v, float) else v for a, v in p.items()}))
        json.dump([{"value": j, "params": p, "result": r} for j, p, r in log], open(f"{cache}/offline-search{'-top10' if TOP10 else ''}.json", "w"), default=float)
