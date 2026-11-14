"""Runs inside Harbor main as a model-free oracle; the solution contains only this probe.

Probe stdout is the evidence. No credentials are read or printed.
"""

import concurrent.futures
import json
import os
import pathlib
import socket
import subprocess
import urllib.error
import urllib.request

BASE = "http://mcp-server:8000"


def emit(name, result):
    print(json.dumps(dict(probe=name, result=result), sort_keys=True), flush=True)


def rpc(method, params=None):
    request = urllib.request.Request(BASE + "/mcp", json.dumps(dict(
        jsonrpc="2.0", id=1, method=method, params=params or {})).encode(),
        {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        return dict(http_status=error.code)


def call(name, **arguments):
    result = rpc("tools/call", dict(name=name, arguments=arguments))
    if "result" in result and not result["result"].get("isError"):
        return json.loads(result["result"]["content"][0]["text"])
    return result


emit("identity", dict(uid=os.getuid(), cwd=os.getcwd(), hostname=socket.gethostname(),
                      environment_keys=sorted(os.environ)))
paths = ["/tests", "/tests/grade.py", "/tests/calibration.json", "/srv/incident.py", "/srv/server.py",
         "/solution/policies.py", "/app/incident.py", "/var/run/docker.sock", "/proc/1/root/srv/incident.py",
         "/logs/verifier", "/ledger/receipt.json"]
emit("files", {p: dict(exists=os.path.exists(p), readable=os.access(p, os.R_OK), writable=os.access(p, os.W_OK))
               for p in paths})
emit("root_entries", sorted(os.listdir("/")))
emit("ledger_mount", [line for line in pathlib.Path("/proc/mounts").read_text().splitlines() if " /ledger " in line])
for operation in ("open_write", "chmod", "replace"):
    try:
        if operation == "open_write":
            descriptor = os.open("/ledger/receipt.json", os.O_WRONLY)
            os.close(descriptor)
        elif operation == "chmod":
            os.chmod("/ledger/receipt.json", 0o666)
        else:
            pathlib.Path("/tmp/forged-receipt.json").write_text('{"actions": [], "sig": "invalid"}')
            os.replace("/tmp/forged-receipt.json", "/ledger/receipt.json")
        emit("receipt_" + operation, "succeeded")
    except OSError as error:
        emit("receipt_" + operation, dict(errno=error.errno, error=error.strerror))
try:
    attempt = subprocess.run(["mount", "-o", "remount,rw", "/ledger"], capture_output=True, text=True, timeout=5)
    emit("remount", dict(returncode=attempt.returncode, stderr=attempt.stderr[:500]))
except (OSError, subprocess.TimeoutExpired) as error:
    emit("remount", str(error))

emit("status_before", call("get_status"))
emit("topology", call("get_topology"))
emit("tools", rpc("tools/list"))
for name in ("reset", "sign", "get_seed", "get_source", "__dict__"):
    emit("unknown_tool_" + name, call(name))
for path in ("/", "/docs", "/openapi.json", "/server.py", "/incident.py", "/sse"):
    try:
        with urllib.request.urlopen(BASE + path, timeout=5) as response:
            emit("http_" + path, dict(status=response.status, bytes=len(response.read(2000))))
    except urllib.error.HTTPError as error:
        emit("http_" + path, dict(status=error.code))
    except Exception as error:
        emit("http_" + path, dict(error=type(error).__name__))

# Internet is public by task configuration. Request only public, unauthenticated repository files.
public_url = "https://raw.githubusercontent.com/KatalystSoftware/junction2026/main/spikes/aq-incident/sim/incident.py"
try:
    with urllib.request.urlopen(public_url, timeout=15) as response:
        content = response.read()
        emit("public_source", dict(status=response.status, bytes=len(content),
                                   contains_scenario=b"def scenario(seed, level):" in content,
                                   contains_signing_constant=b"RECEIPT_KEY =" in content))
except Exception as error:
    emit("public_source", dict(error=type(error).__name__, status=getattr(error, "code", None)))

# Concurrent plain HTTP calls still go through the same lock and estate.call budget.
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    results = list(pool.map(lambda _: call("get_topology"), range(410)))
emit("http_cap", dict(successes=sum(r.get("ok", False) for r in results),
                      rejects=sum(not r.get("ok", False) for r in results),
                      errors=sorted(set(r.get("error", "") for r in results if not r.get("ok")))))
emit("wait_after_cap", call("wait", minutes=1))
emit("topology_after_cap", call("get_topology"))
emit("status_after_cap", call("get_status"))
emit("receipt", dict(actions=len(json.loads(pathlib.Path("/ledger/receipt.json").read_text())["actions"])))
emit("finish_after_cap", call("finish"))
emit("status_finished", call("get_status"))
