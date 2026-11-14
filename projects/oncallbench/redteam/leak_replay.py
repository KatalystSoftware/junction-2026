"""Exploit: copy the reference's moves from the public replay site instead of working the incident.

The task's network is public (OpenCode needs it). https://incident.katalyst.fyi/ serves, for each
episode it shows, every fault (service and fix) and the full action log of the scripted reference.
The site shows level 4, seed 101, which is exactly `tasks/shift-1`. This script reads nothing
about the incident: it fingerprints the episode from the free `get_topology` (service names and
revenue), finds the matching bundle, and replays the reference's calls through the MCP tools.

Inside the task's main container (stdlib only, python3 is installed there):
    python3 leak_replay.py http://mcp-server:8000/mcp
In the simulator, scored next to the reference:
    python3 redteam/leak_replay.py --sim 101
"""

import json
import sys
import urllib.request
from pathlib import Path

SITE = "https://incident.katalyst.fyi/data/"


def fetch(name):
    req = urllib.request.Request(SITE + name, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode()


def bundles():
    index = fetch("index.js")
    names = json.loads(index[index.index("["):index.rindex("]") + 1])
    for name in names:
        text = fetch(name)
        yield json.loads(text[text.index(".push(") + 6:text.rindex(")")])


def matching_session(topology):
    """The episode whose estate has the same services earning the same revenue."""
    want = sorted((s["name"], s["revenue_per_min"]) for s in topology["services"])
    for bundle in bundles():
        for session in bundle["sessions"]:
            if sorted((s["name"], s["revenue"]) for s in session["services"]) == want:
                return session
    return None


def exploit(call):
    session = matching_session(call("get_topology"))
    if session is None:
        print("no published episode matches this estate")
        return None
    run = next(r for r in session["runs"] if r["id"] == "reference")
    print(f"matched level {session['level']} seed {session['seed']}: replaying {len(run['actions'])} reference calls")
    for a in run["actions"]:
        call(a["tool"], **a["args"])
    return session


def http_caller(url):
    def call(tool, **args):
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool, "arguments": args}}
        req = urllib.request.Request(url, json.dumps(body).encode(), {
            "Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            reply = json.load(resp)
        if "error" in reply or reply["result"].get("isError"):
            return {"ok": False}
        return json.loads(reply["result"]["content"][0]["text"])

    return call


if __name__ == "__main__":
    if sys.argv[1:2] == ["--sim"]:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sim"))
        import incident
        import policies

        seed, level = int(sys.argv[2]), 4

        def cost(policy):
            estate = incident.Estate(seed, level)
            policy(lambda tool, **args: estate.call(tool, args))
            return incident.replay(seed, level, [list(a) for a in estate.actions]).total_cost()

        null, ref, got = cost(policies.nothing), cost(policies.reference), cost(exploit)
        print(f"seed {seed}: reference {incident.score(ref, null, ref):.2f}  leak-replay {incident.score(got, null, ref):.2f}")
    else:
        exploit(http_caller(sys.argv[1] if len(sys.argv) > 1 else "http://mcp-server:8000/mcp"))
