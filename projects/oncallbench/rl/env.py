"""Multi-turn text environment over the aq-incident simulator, in process, without Harbor or Docker.

The system prompt is the task's instruction with the level's briefing, the tools are the MCP
tools as JSON function schemas, and an episode ends at `finish`, at the shift's end, or when the
harness's call cap is reached (then the shift is finished for the agent: whatever is still broken
is charged to the end, as with `finish`). The reward is the environment's own score from the
signed action log, replayed:

    score = clip((cost_null - cost) / (cost_null - cost_ref), 0, 1)

The simulator is imported read-only from ../sim (or from AQ_SIM, a pinned snapshot).
"""

import hashlib
import json
import os
import re
import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIM = Path(os.environ.get("AQ_SIM", HERE.parent / "sim"))
TASK = Path(os.environ.get("AQ_TASK", HERE.parent / "task"))
sys.path.insert(0, str(SIM))

import incident  # noqa: E402
import policies  # noqa: E402

MAX_TURNS = int(os.environ.get("AQ_MAX_TURNS", 40))  # replies per episode; the MCP cap is 400 calls
CALLS_PER_TURN = 4  # tool calls executed per reply; the rest are refused
SIM_SHA = hashlib.sha256((SIM / "incident.py").read_bytes() + (SIM / "policies.py").read_bytes()).hexdigest()[:12]

DESCRIPTIONS = {
    "get_status": "Current minute, minutes left on shift, error rate and revenue per minute of each customer-facing "
                  "(edge) service, and mitigations still in progress.",
    "get_topology": "Every service: tier (edge, app, data), normal replica count, and which services it calls. A hard "
                    "dependency passes all of its failures to the caller, a soft one about 30%.",
    "list_alerts": "Alerts firing now: error_rate >= 0.05, cpu >= 0.9 or mem >= 0.9, with the minute each began.",
    "get_metrics": "Recent metrics of one service: error_rate, p99_ms, rps, cpu, mem, replicas and restarts in the "
                   "last 30 minutes.",
    "get_logs": "Log lines of one service over 10 minutes, grouped by message with counts.",
    "get_changes": "Deploys and config changes of one service in the last 24 hours (minutes are relative to the "
                   "page, so negative means before it).",
    "get_diff": "What one deploy or config change of a service did, by the id `get_changes` shows.",
    "rollback": "Roll back the service's most recent live deploy.",
    "revert_config": "Revert the service's most recent live config change.",
    "restart": "Restart every instance of the service.",
    "scale": "Set the replica count (1 to 4x normal). Replicas above normal cost money for the rest of the shift.",
    "failover": "Promote the standby of a data-tier service. The service is fully down while it runs.",
    "throttle": "Make the service reject this share of its requests up front (percent, 0 lifts it) until you "
                "change it.",
    "wait": "Let simulated time pass.",
    "finish": "End the shift now. The rest of the shift is still simulated and charged.",
}
ARG_TYPES = {"service": "string", "replicas": "integer", "minutes": "integer", "percent": "integer",
             "change_id": "string", "until_minute": "integer", "tier": "string"}


def tools(level):
    estate = incident.Estate(1, level)
    out = []
    for name, req in estate.TOOLS.items():
        opt = estate.OPTIONAL.get(name, ()) if estate.partial else ()
        props = {a: {"type": ARG_TYPES[a]} for a in (*req, *opt)}
        out.append({"type": "function", "function": {
            "name": name, "description": DESCRIPTIONS[name],
            "parameters": {"type": "object", "properties": props, "required": list(req)}}})
    return out


@lru_cache(maxsize=None)
def system_prompt(level):
    text = (TASK / "instruction.md").read_text()
    text = text.replace("<!-- BRIEFING -->", incident.briefing(level).strip())
    old = "A shift accepts at most 400 tool calls\n  (`get_status` does not count)."
    assert old in text, "instruction changed: update the call-cap sentence"
    text = text.replace(old, f"A shift accepts at most {MAX_TURNS} replies, each with up to {CALLS_PER_TURN} tool calls.")
    return text.strip()


USER = "You have been paged. Work the incident with the tools, one or more tool calls per reply."


_COSTS = {}
_COST_FILE = HERE / "cache" / f"costs-{SIM_SHA}.json"


def anchors(seed, level):
    """(cost_null, cost_ref) for an episode, cached on disk per simulator version."""
    key = f"{level}:{seed}"
    if not _COSTS and _COST_FILE.exists():
        _COSTS.update(json.loads(_COST_FILE.read_text()))
    if key not in _COSTS:
        null = incident.Estate(seed, level)
        null.finish()
        ref = incident.Estate(seed, level)
        policies.reference(lambda tool, **a: ref.call(tool, a))
        ref.finish()
        _COSTS[key] = (null.total_cost(), ref.total_cost())
        _COST_FILE.parent.mkdir(exist_ok=True)
        tmp = _COST_FILE.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(_COSTS))
        os.replace(tmp, _COST_FILE)
    return tuple(_COSTS[key])


def dumps(obj):
    return json.dumps(obj, separators=(",", ":"))


class Episode:
    def __init__(self, seed, level):
        self.seed, self.level = seed, level
        self.estate = incident.Estate(seed, level)
        self.calls = 0
        self.invalid = 0
        self.ended = None  # "finish" | "shift" | "cap" | "context"
        self.trace = []  # (tool, args, ok)

    @property
    def done(self):
        return self.ended is not None

    def step(self, name, args):
        """One tool call; returns the text the agent sees."""
        self.calls += 1
        if not isinstance(args, dict):
            args = {}
        result = self.estate.call(name, args)
        ok = bool(result.get("ok"))
        self.invalid += not ok
        self.trace.append((name, args, ok))
        if self.estate.done:
            self.ended = "finish" if name == "finish" else "shift"
        return dumps(result)

    def end(self, why):
        if self.ended is None:
            self.ended = why

    def cost(self):
        """Replay the accepted actions and settle the shift, as the verifier does."""
        return incident.replay(self.seed, self.level, json.loads(json.dumps(self.estate.actions))).total_cost()

    def raw_score(self):
        null, ref = anchors(self.seed, self.level)
        return (null - self.cost()) / (null - ref)

    def score(self):
        return incident.score(self.cost(), *anchors(self.seed, self.level))

    def actions(self):
        return [a for a in self.estate.actions if a[0] in incident.MITIGATIONS or a[0] in ("throttle", "finish")]


# --- tool-call parsing: Qwen's JSON (hermes) and XML (qwen3.5) forms, and Gemma 4's call:name{...} ---

JSON_CALL = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)
XML_CALL = re.compile(r"<function=([\w\-]+)>(.*?)</function>", re.S)
XML_PARAM = re.compile(r"<parameter=([\w\-]+)>\s*(.*?)\s*</parameter>", re.S)


def coerce(value):
    value = value.strip()
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return value


GEMMA_CALL = re.compile(r"<\|tool_call>call:([\w\-]+)\{(.*?)\}<tool_call\|>", re.S)
GEMMA_ARG = re.compile(r'(\w+):(?:<\|"\|>(.*?)<\|"\|>|([^,]*))', re.S)


def parse_calls(text):
    """Tool calls in a reply, in order: [(name, args)]. Unparseable calls come back as (None, error)."""
    calls = [(m[1], {k: q if q or not b else coerce(b) for k, q, b in GEMMA_ARG.findall(m[2])})
             for m in GEMMA_CALL.finditer(text)]
    if calls:
        return calls
    for m in XML_CALL.finditer(text):
        calls.append((m[1], {k: coerce(v) for k, v in XML_PARAM.findall(m[2])}))
    if calls:
        return calls
    for m in JSON_CALL.finditer(text):
        try:
            obj = json.loads(m[1])
            args = obj.get("arguments", obj.get("parameters", {}))
            if isinstance(args, str):
                args = json.loads(args)
            calls.append((obj["name"], args))
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as e:
            calls.append((None, f"could not parse tool call: {e}"))
    return calls
