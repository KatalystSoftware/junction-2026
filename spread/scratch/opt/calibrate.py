"""Fits the one number of the stand-in that no reveal shows, the competitor's answer to what the desk wins (`react`), on
the played variants, and reports what lateness costs in dealer trust.
PYTHONPATH=. uv run --with numpy python -u scratch/opt/calibrate.py <data> <cache> react|trust"""
import glob, json, sys
from multiprocessing import Pool
import numpy as np
import sim
from sim import Weeks, simulate, reference_rule, shadow_rule

data, cache, what = sys.argv[1:4]
weeks = Weeks(data, cache)
everything = list(range(len(weeks.W)))
weeks.fit(everything)
HOURS = [[6, 1.55], [8, 1.35], [12, 1.3], [30, 1.2]]
RULES = {
    "steep-notes-offers-8-cost-1.4": dict(cost=1.4), "step-2": dict(step=0.02), "step-2-gate-25": dict(step=0.02, gate=25), "due-24-gate-20": dict(step_hours=24, gate=20),
    "due-24-gate-25": dict(step_hours=24, gate=25), "hours": dict(cost=1.15, hours=HOURS), "hours-step-2-gate-25": dict(cost=1.15, hours=HOURS, step=0.02, gate=25),
    "hours-due-24-gate-25": dict(cost=1.15, hours=HOURS, step_hours=24, gate=25),
}

def run(job):
    name, react, halve, on = job
    rule = reference_rule if name == "ref" else shadow_rule(weeks, **RULES[name])
    return simulate(weeks, rule, on, 0, react=react, halve=halve)

def played_scores(name):
    out = {}
    for f in glob.glob(f"{data}/runs/{name}/*.score.json"):
        d = json.load(open(f)); out[d["seed"]] = d["score"]
    return out

if __name__ == "__main__":
    with Pool(4) as pool:
        if what == "trust":
            chunks = [everything[i::4] for i in range(4)]
            for react in (0.0,):
                a = [r for part in pool.map(run, [("ref", react, True, c) for c in chunks]) for r in part]
                b = [r for part in pool.map(run, [("ref", react, False, c) for c in chunks]) for r in part]
                a.sort(key=lambda r: r["w"]); b.sort(key=lambda r: r["w"])
                d = np.array([y["margin"] - x["margin"] for x, y in zip(a, b)]); late = np.array([x["late"] for x in a])
                print(f"reference, {len(a)} weeks: without the halving of a dealer's count the week makes {d.mean():+.0f} more, on {np.mean([y['orders'] - x['orders'] for x, y in zip(a, b)]):+.1f} orders; "
                      f"late orders a week {late.mean():.1f}; that is {d.sum() / late.sum():.0f} a late order in trust; refunds are {np.mean([x['refund'] for x in a]) / 100 / late.mean():.0f} a late order")
        else:
            for react in [float(x) for x in sys.argv[4:]] or [0.0, 0.3, 0.6]:
                jobs, spans = [], {}
                for name in RULES:
                    scores = played_scores(name)
                    on = [wi for wi in everything if weeks.seeds[wi] in scores]
                    spans[name] = (on, scores)
                    jobs += [(name, react, True, on), ("ref", react, True, on)]
                results = pool.map(run, jobs)
                err_o = err_m = 0.0
                print(f"react {react}: variant | orders stand-in / played | late | margin")
                for i, name in enumerate(RULES):
                    on, scores = spans[name]
                    v, r = results[2 * i], results[2 * i + 1]
                    pv, pr = [scores[weeks.seeds[wi]] for wi in on], [weeks.played[wi] for wi in on]
                    do = np.mean([a["orders"] - b["orders"] for a, b in zip(v, r)]); dl = np.mean([a["late"] - b["late"] for a, b in zip(v, r)])
                    dm = np.mean([a["margin"] - 0.026 * max(0, a["orders"] - b["orders"]) / 100 * a["typ"] / 100 - b["margin"] for a, b in zip(v, r)])
                    po = np.mean([a["wonOrders"] - b["wonOrders"] for a, b in zip(pv, pr)]); pm = np.mean([a["marginCents"] - b["marginCents"] for a, b in zip(pv, pr)]) / 100
                    pl = np.mean([a["wonOrders"] * (1 - a["onTimeShare"]) - b["wonOrders"] * (1 - b["onTimeShare"]) for a, b in zip(pv, pr)])
                    err_o += (do - po) ** 2; err_m += (dm - pm) ** 2
                    print(f"  {name:30} {len(on):3} | {do:+6.1f} / {po:+6.1f} | {dl:+5.1f} / {pl:+5.1f} | {dm:+6.0f} / {pm:+6.0f} | under 91%: {sum(a['on_time'] < 0.91 for a in v)} / {sum(a['onTimeShare'] < 0.91 for a in pv)}")
                print(f"  root mean square error: orders {np.sqrt(err_o / len(RULES)):.1f}, margin {np.sqrt(err_m / len(RULES)):.0f}")
