"""What an agent did, read off its signed action log: every acting step with its minute, the
number of queries before it, the tool's reply, whether it was charged as wasted, and the edge
error rates after it. The failure classes in LOOP.md were assigned from this and the agent's
closing message.

python3 explain.py <seed> <level> <receipt.json> [--all]     (--all prints the queries too)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "sim"))

import incident  # noqa: E402

HIDE = ("ok", "minute", "service", "series", "lines", "alerts", "services", "edge", "changes")
PLAIN = ("ok", "minute", "minutes_left", "shift_over", "edge", "operations_in_progress", "throttles")

if __name__ == "__main__":
    seed, level, path = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    estate = incident.Estate(seed, level)
    print("faults:", [(f["kind"], f["service"], f["start"], f.get("change")) for f in estate.faults])
    acting, queries = set(incident.MITIGATIONS) | {"throttle", "finish"}, 0
    for tool, args in json.loads(Path(path).read_text())["actions"]:
        before, wasted = estate.now, estate.wasted
        reply = estate.call(tool, args)
        if tool not in acting and "--all" not in sys.argv:
            queries += 1
            continue
        status = estate.get_status()
        edge = " ".join(f"{e['service'].split('-')[0]}={e['error_rate']:.2f}" for e in status["edge"])
        keep = {k: v for k, v in reply.items() if k not in HIDE}
        if tool == "get_logs":
            keep["lines"] = [line["message"][:70] for line in reply.get("lines", [])][:6]
        if tool == "get_diff":
            keep = {"diff": reply.get("diff", "")[:160]}
        extra = {k: v for k, v in status.items() if k not in PLAIN and v}
        print(f"m{before:>3} (+{queries}q) {tool} {args} -> {keep}{'  WASTED' if estate.wasted > wasted else ''}"
              f" | {edge} {extra or ''}")
        queries = 0
    estate.finish()
    print("cost", estate.total_cost(), estate._cost(),
          "left", [(f["kind"], f["service"]) for f in estate.faults if f["end"] is None and f["kind"] != "overload"])
