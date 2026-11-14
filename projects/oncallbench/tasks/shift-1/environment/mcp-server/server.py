"""MCP sidecar: the only way to see or change the estate.

Every accepted call is appended to the action log; the signed log is rewritten after each call to
a volume the agent's container mounts read-only. The verifier replays it.
"""

import json
import os
import threading

from mcp.server.fastmcp import FastMCP

import incident

SEED = 101
LEVEL = 4
RECEIPT = "/ledger/receipt.json"

mcp = FastMCP("ops", host="0.0.0.0", port=8000, stateless_http=True, json_response=True)
estate = incident.Estate(SEED, LEVEL)
lock = threading.Lock()


def run(tool, **args):
    with lock:
        result = estate.call(tool, args)
        tmp = RECEIPT + ".tmp"
        with open(tmp, "w") as f:
            json.dump(estate.receipt(), f)
        os.replace(tmp, RECEIPT)
        return json.dumps(result)


@mcp.tool()
def get_status() -> str:
    """Current minute, minutes left on shift, error rate and revenue per minute of each
    customer-facing (edge) service, mitigations still in progress and throttles that are on."""
    return run("get_status")


@mcp.tool()
def get_topology() -> str:
    """Every service: tier (edge, app, data, or external for one hosted outside the estate), normal
    replica count, and which services it calls. A hard dependency passes all of its failures to the
    caller, a soft one about 30%. Where the instruction covers retries, also how many times callers
    retry a failed call to it; where it covers generated files, also the service it loads one from."""
    return run("get_topology")


def some(**args):
    return {key: value for key, value in args.items() if value is not None}


@mcp.tool()
def list_alerts(tier: str | None = None) -> str:
    """Alerts firing now: error_rate >= 0.05, cpu >= 0.9 or mem >= 0.9, with the minute each began.
    The instruction says whether the list is complete and whether `tier` (edge, app, data) applies."""
    return run("list_alerts", **some(tier=tier))


@mcp.tool()
def get_metrics(service: str, until_minute: int | None = None) -> str:
    """Recent metrics of one service: error_rate, p99_ms, rps, cpu, mem, replicas and restarts in
    the last 30 minutes. The instruction says how far one call reaches and whether `until_minute`
    (the minute the window ends, not in the future) applies."""
    return run("get_metrics", service=service, **some(until_minute=until_minute))


@mcp.tool()
def get_logs(service: str, until_minute: int | None = None) -> str:
    """Log lines of one service over 10 minutes, grouped by message with counts. The instruction
    says whether `until_minute` (the minute the window ends, not in the future) applies."""
    return run("get_logs", service=service, **some(until_minute=until_minute))


@mcp.tool()
def get_changes(service: str) -> str:
    """Deploys and config changes of one service in the last 24 hours (minutes are relative to
    the page, so negative means before it)."""
    return run("get_changes", service=service)


@mcp.tool()
def get_diff(service: str, change_id: str) -> str:
    """What one deploy or config change of a service did, by the id `get_changes` shows. The
    instruction says whether this tool applies."""
    return run("get_diff", service=service, change_id=change_id)


@mcp.tool()
def rollback(service: str) -> str:
    """Roll back the service's most recent live deploy. The instruction says how long it takes
    and how many requests fail meanwhile."""
    return run("rollback", service=service)


@mcp.tool()
def revert_config(service: str) -> str:
    """Revert the service's most recent live config change. Timing is in the instruction."""
    return run("revert_config", service=service)


@mcp.tool()
def restart(service: str) -> str:
    """Restart every instance of the service. The instruction says how long it takes and how
    many requests fail meanwhile; a data-tier service is fully down."""
    return run("restart", service=service)


@mcp.tool()
def scale(service: str, replicas: int) -> str:
    """Set the replica count (1 to 4x normal). Timing is in the instruction. Replicas above
    normal cost money for the rest of the shift."""
    return run("scale", service=service, replicas=replicas)


@mcp.tool()
def failover(service: str) -> str:
    """Promote the standby of a data-tier service. The service is fully down while it runs."""
    return run("failover", service=service)


@mcp.tool()
def throttle(service: str, percent: int) -> str:
    """Make the service reject this share of its requests up front (percent, 0 lifts it) until
    you change it. The instruction says whether this tool applies and what it costs."""
    return run("throttle", service=service, percent=percent)


@mcp.tool()
def wait(minutes: int) -> str:
    """Let simulated time pass. The instruction says which other tools take time."""
    return run("wait", minutes=minutes)


@mcp.tool()
def finish() -> str:
    """End the shift now. The rest of the shift is still simulated and charged."""
    return run("finish")


if __name__ == "__main__":
    run("get_status")
    mcp.run(transport="streamable-http")
