"""Local evaluation: scripted anchors on every seed, with the determinism and fuzz gates.

python3 eval.py [--level N] [--seeds 1,2,3] [--fuzz N]
"""

import argparse
import itertools
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "sim"))

import incident  # noqa: E402
import policies  # noqa: E402

BUILD_SEEDS = [1, 2, 3, 4, 5]
HELD_OUT_SEEDS = [101, 102, 103]
EXTRA_BUILD_SEEDS = [6, 7, 8, 9, 10, 11, 12]  # more seeds to tune on: --seeds 6,7,8,9,10,11,12


UNDOS = {}  # (seed, level) -> the changes the reference undid, each after reading its diff
TARGET, UNDER = 0.75, []  # reference/oracle target where views are partial, and the seeds that miss it
UNDO = {"rollback": "deploy", "revert_config": "config"}


def run(seed, level, policy):
    """Play a policy in-process, settle the shift, and check the replay recomputes the same cost.
    Where diffs can be read (level 3 and up) the reference may undo only a change whose diff it
    has read earlier in the shift: the latest live change of that type, as `get_changes` lists it.
    No exemption: what it has read is judged from its own calls, never from the hidden faults."""
    estate = incident.Estate(seed, level)
    read, undone = set(), []

    def call(tool, **args):
        if tool == "get_diff":
            read.add((args.get("service"), args.get("change_id")))
        if tool in UNDO and args.get("service") in estate.svc:
            live = [c for c in estate.get_changes(args["service"])["changes"]
                    if c["type"] == UNDO[tool] and c["status"] == "live"]
            if live:
                change = (args["service"], live[-1]["id"])
                assert change in read, f"seed {seed}: the reference undid {change} without reading its diff"
                undone.append(change)
        return estate.call(tool, args)

    checked = policy == "reference" and level >= 3
    policies.POLICIES[policy](call if checked else lambda tool, **args: estate.call(tool, args))
    if checked:
        UNDOS[seed, level] = undone
    receipt = json.dumps(estate.receipt(), sort_keys=True)
    estate.finish()
    again = incident.replay(seed, level, json.loads(receipt)["actions"])
    assert json.dumps(again.receipt(), sort_keys=True) == receipt, "replay changed the action log"
    assert again.total_cost() == estate.total_cost(), "replay changed the cost"
    return estate


FIX = {"bad_deploy": "rollback", "leak": "rollback", "bad_config": "revert_config", "primary_down": "failover",
       "bad_file": "revert_config"}


def oracle(seed, level, skip=None):
    """Not a policy: reads the hidden faults and starts each right mitigation as early as the
    simulator allows. `skip` leaves one fault alone. Returns the cheapest order's cost.
    Where callers retry it reads the hidden load too: a quiet service gets the capacity a
    disruptive fix needs first and gives it back after, and a storm that would outlive a fix is
    throttled for the minute the fix lands. A bad file is fixed at its publisher, and a storm on a
    consumer is throttled for the minute the next good file lands."""
    faults = [i for i in range(len(incident.Estate(seed, level).faults)) if i != skip]
    costs = []
    for order in itertools.permutations(faults):
        estate = incident.Estate(seed, level)
        todo, tick = [], itertools.count()  # (minute, tie-break, step): what follows a mitigation

        def later(minute, tool, **args):
            todo.append((minute, next(tick), lambda: estate.call(tool, args)))

        def flush(until):
            while todo and min(todo)[0] <= until:
                minute, _, step = min(todo)
                todo.remove(min(todo))
                if minute > estate.now:
                    estate.call("wait", {"minutes": minute - estate.now})
                if estate.done:
                    break
                step()

        def mitigate(f, spare):
            name, s = f["service"], estate.svc[f["service"]]
            args = {"service": name}
            if f["kind"] == "overload":
                args["replicas"] = math.ceil(f["load"] * s["replicas"] / s.get("cap", incident.HEADROOM))
            result = estate.call(FIX.get(f["kind"], "scale"), args)
            assert result["ok"]
            at = result["completes_at_minute"]
            if spare:
                later(at, "scale", service=name, replicas=s["replicas"])
            elif estate.storms and estate._state(at)[name][2] > 1:
                later(at - 1, "throttle", service=name, percent=min(90, math.ceil(100 * (1 - 1 / estate._state(at)[name][2]))))
                later(at, "throttle", service=name, percent=0)
            tick = incident.EVERY * math.ceil(at / incident.EVERY)
            for c in f.get("hits", ()):  # a storm outlives the bad file: one consumer after the other
                if estate._state(tick)[c][2] > 1:
                    later(tick - 1, "throttle", service=c, percent=min(90, math.ceil(100 * (1 - 1 / estate._state(tick)[c][2]))))
                    later(tick, "throttle", service=c, percent=0)
                    tick += 2

        for i in order:
            f = estate.faults[i]
            if f["kind"] != "leak" and f["start"] > estate.now:
                flush(f["start"] - 1)
                estate.call("wait", {"minutes": f["start"] - estate.now})
            flush(estate.now)
            s, tool = estate.svc[f["service"]], FIX.get(f["kind"], "scale")
            sev = estate.cfg.get("disrupt", {}).get(tool, incident.MITIGATIONS[tool][1])
            fail = estate._state(estate.now)[f["service"]][0] if estate.storms else 1
            need = (1 + s["retry"] * (1 - (1 - fail) * (1 - sev))) / s["cap"] if estate.storms else 0
            if sev and fail < 0.1 and need > 1:  # quiet, and its fix would tip it: capacity first
                at = estate.call("scale", {"service": f["service"], "replicas": math.ceil(need * s["replicas"])})
                todo.append((at["completes_at_minute"], next(tick), lambda f=f: mitigate(f, True)))
            else:
                mitigate(f, False)
        flush(incident.HORIZON)
        estate.finish()
        costs.append(estate.total_cost())
    return min(costs)


def evaluate(seed, level):
    cost = {name: run(seed, level, name).total_cost() for name in policies.POLICIES}
    null, ref = cost["nothing"], cost["reference"]
    return dict(seed=seed, level=level, cost_null=null, cost_ref=ref, cost=cost,
                score={name: round(incident.score(c, null, ref), 4) for name, c in cost.items()})


def versus_oracle(seed, level, result):
    """Share of the oracle's avoided cost the reference avoids, and the score of the oracle with
    each one fault left alone."""
    null, ref = result["cost_null"], result["cost_ref"]
    ratio = (null - ref) / (null - oracle(seed, level))
    skips = [round((null - oracle(seed, level, i)) / (null - ref), 2)
             for i in range(len(incident.Estate(seed, level).faults))]
    return ratio, skips


def fuzz(seed, level, episodes, calib):
    """Random legal and illegal calls: nothing may crash, and nothing may beat the reference."""
    best = 0.0
    for ep in range(episodes):
        r = random.Random(f"fuzz:{seed}:{level}:{ep}")
        estate = incident.Estate(seed, level)
        names = list(estate.svc) + ["nope", "", None, 3]
        for _ in range(r.randint(1, 40)):
            tool = r.choice(list(estate.TOOLS) + ["drop_table"])
            args = {}
            for key in estate.TOOLS.get(tool, ()):
                args[key] = r.choice(names) if key == "service" else r.choice([-1, 0, 1, 5, 12, 40, 500, True, "9", 2.5])
                if key == "percent":  # its own draw, so the other levels' episodes stay as they were
                    args[key] = random.Random(f"{seed}:{ep}:{len(estate.actions)}:{estate.now}").choice(
                        [-1, 0, 10, 35, 50, 90, 91, 500, True, "9", 2.5])
            if r.random() < 0.05:
                args["extra"] = 1
            estate.call(tool, args)
        replayed = incident.replay(seed, level, json.loads(json.dumps(estate.actions)))
        estate.finish()
        assert replayed.total_cost() == estate.total_cost()
        best = max(best, (calib["cost_null"] - estate.total_cost()) / (calib["cost_null"] - calib["cost_ref"]))
    return best


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=int, default=incident.SUBMITTED)
    ap.add_argument("--seeds", default=",".join(map(str, BUILD_SEEDS + HELD_OUT_SEEDS)))
    ap.add_argument("--fuzz", type=int, default=200)
    ap.add_argument("--json", action="store_true")
    opts = ap.parse_args()
    for seed in map(int, opts.seeds.split(",")):
        result = evaluate(seed, opts.level)
        if opts.json:
            print(json.dumps(result))
            continue
        faults = [(f["kind"], f["service"]) for f in incident.Estate(seed, opts.level).faults]
        best = fuzz(seed, opts.level, opts.fuzz, result)
        ratio, skips = versus_oracle(seed, opts.level, result)
        print(f"seed {seed:>3} null {result['cost_null']:>9.0f} ref {result['cost_ref']:>8.0f}  "
              + "  ".join(f"{k} {v:.2f}" for k, v in result["score"].items())
              + f"  fuzz-best {best:.2f}  ref/oracle {ratio:.3f}  skip-one {skips}  {faults}"
              + (f"  undos-read {len(UNDOS[seed, opts.level])}" if (seed, opts.level) in UNDOS else ""))
        score = result["score"]
        assert result["cost_null"] > result["cost_ref"] > 0
        assert score["stop-early"] <= 0.05 and score["exploiter"] < 0.9
        assert best <= 1.02, "a random policy beat the reference by more than rounding of replicas"
        partial = incident.LEVELS[opts.level].get("partial")
        # The target stays 0.75 where views are partial. A miss is printed, not hidden behind a lower
        # bar: the oracle pays nothing to look, the reference pays clock minutes for every log and
        # diff, and `generality.py` gives the whole distribution on seeds nobody tuned on.
        if partial and ratio < TARGET:
            UNDER.append((seed, round(ratio, 3)))
        assert ratio >= (0.5 if partial else 0.9), "the reference avoids too little of what the oracle avoids"
        if partial:  # as a share of what the oracle avoids: against the reference it would need ratio >= 0.9
            skips = [round(x * ratio, 2) for x in skips]
            assert skips[3] <= 0.75, "the quiet fault on the rich edge can be left alone for more than 0.75"
            assert score["trusting"] <= 0.85 and score["alerts-only"] <= 0.85 and score["shotgun"] < 0.9
        if incident.LEVELS[opts.level].get("storms"):
            assert score["no-drain"] <= 0.8 and score["forgetful"] < 0.95
            # a quiet fault that sits in a config needs no protection, so there is nothing to get wrong
            assert score["unprotected"] <= 0.9 or faults[-1][0] == "bad_config"
        if incident.LEVELS[opts.level].get("files"):
            assert skips[0] <= 0.8, "the bad file can be left alone for more than 0.8 of what the oracle avoids"
            assert max(score["consumer-fixer"], score["surge-responder"], score["drain-only"]) <= 0.8
        if opts.level >= 1:
            assert max(skips) <= 0.9, "one fault can be left alone for more than 0.9"
            assert score["one-fix"] <= 0.75 and score["no-late"] <= 0.9 and score["loudest-first"] < 0.95
    if UNDER:
        print(f"reference under {TARGET} of the oracle on {len(UNDER)} seed(s): {UNDER}")
