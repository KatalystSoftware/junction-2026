"""Reference trajectories rendered through the same tool interface, for SFT.

The scripted reference polls every minute (hundreds of calls a shift), which no context window
holds. A demo keeps its decisions and makes them fit:
- its one-minute idle waits become waits to the next check-in (every Q minutes), so it reacts
  only at times an agent could choose without knowing the future;
- `get_status` (free and not logged) is dropped, and one is added after every wait;
- on levels where queries are free, a `list_alerts` that shows the same alerts as the last one kept
  is dropped (it changes nothing in the action log).
The rendered calls are replayed in a fresh episode to get the outputs the agent would see, and the
demo's score is the environment's score of that replay.

python3 demos.py --levels 0,1,2 --seeds 1-12,200-299 --out cache/demos.jsonl
"""

import argparse
import json

import env
from env import incident, policies


def reference_log(seed, level, every):
    estate = incident.Estate(seed, level)
    log = []

    def raw(tool, **args):
        if tool == "wait" and args.get("minutes") == 1 and not any(at > estate.now for _, _, at in estate.ops):
            nxt = min(incident.HORIZON, (estate.now // every + 1) * every)
            args = {"minutes": max(1, nxt - estate.now)}
        result = estate.call(tool, args)
        log.append((tool, args, result))
        return result

    policies.reference(raw)
    return log


def alert_set(result):
    return sorted((a["service"], a["signal"]) for a in result.get("alerts", []))


def render(seed, level, every=10):
    """Turns of (tool calls) for one demo, and the replayed episode."""
    free = not incident.LEVELS[level]["query_min"]
    turns, last_alerts = [], None
    for tool, args, result in reference_log(seed, level, every):
        if tool == "get_status" or not result.get("ok"):
            continue
        if tool == "list_alerts" and free:
            if alert_set(result) == last_alerts:
                continue
            last_alerts = alert_set(result)
        if tool == "wait":
            turns.append([("wait", args), ("get_status", {})])
        else:
            turns.append([(tool, args)])
    ep = env.Episode(seed, level)
    messages = [{"role": "system", "content": env.system_prompt(level)}, {"role": "user", "content": env.USER}]
    for calls in turns:
        if ep.done:
            break
        messages.append({"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": n, "arguments": a}} for n, a in calls]})
        for n, a in calls:
            messages.append({"role": "tool", "name": n, "content": ep.step(n, a)})
    ep.end("cap")
    return messages, ep, len(turns)


def seeds_arg(text):
    out = []
    for part in text.split(","):
        lo, _, hi = part.partition("-")
        out += range(int(lo), int(hi or lo) + 1)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--levels", default="0,1,2")
    ap.add_argument("--seeds", default="1-12")
    ap.add_argument("--every", type=int, default=10)
    ap.add_argument("--min-score", type=float, default=0.8)
    ap.add_argument("--out")
    opts = ap.parse_args()
    held = set(range(101, 107))
    out = open(opts.out, "w") if opts.out else None
    for level in map(int, opts.levels.split(",")):
        scores, lens = [], []
        for seed in seeds_arg(opts.seeds):
            assert seed not in held, "held-out seeds never go into training data"
            messages, ep, n = render(seed, level, opts.every)
            s = ep.score()
            scores.append(s)
            lens.append(n)
            if out and s >= opts.min_score and n <= env.MAX_TURNS:
                out.write(json.dumps(dict(seed=seed, level=level, score=s, messages=messages)) + "\n")
        print(f"level {level}: demos {len(scores)} mean score {sum(scores) / len(scores):.3f} "
              f"min {min(scores):.3f} turns mean {sum(lens) / len(lens):.1f} max {max(lens)} "
              f"kept {sum(1 for s, n in zip(scores, lens) if s >= opts.min_score and n <= env.MAX_TURNS)}")
