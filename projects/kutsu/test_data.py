"""Checks on the data the page is built from, run before every deploy. No keys, no network.

  python3 test_data.py

1. Every list the page keys has unique, non-empty keys in the committed data. Svelte stops the whole
   page on a duplicate key, which is how a sign-up once crashed in public.
2. The server refuses a saved sign-up the page cannot key, including one in the shape older builds saved.
3. Reading a person's profile leaves nothing behind: no file in the request cache or anywhere else in
   the project, and nothing of the person in what the server prints. The same LinkedIn profile, written
   another way, is read once.
4. With a demo key set, as on the server: a sign-up is saved only with the key or the company's own link
   token, every sign-up is taken out only with the key, role drafts stop at their cap, and a sign-ups
   file that is not JSON is set aside instead of breaking every load.
"""
import contextlib
import http.server
import io
import json
import os
import pathlib
import sys
import tempfile
import threading
import urllib.request

import person
import serve
import signals

HERE = pathlib.Path(__file__).parent
failures = []


def unique(what, keys):
    keys = list(keys)
    seen, twice = set(), set()
    for key in keys:
        if not isinstance(key, str) or not key:
            failures.append(f"{what}: a key is missing or empty ({key!r})")
        elif key in seen:
            twice.add(key)
        seen.add(key)
    if twice:
        failures.append(f"{what}: repeated {sorted(twice)[:5]}")


# 1. the lists the page keys, as the page keys them
briefs = json.loads(signals.OUT.read_text())
unique("briefs by id", (b["id"] for b in briefs))
for brief in briefs:
    name = brief["name"]
    unique(f"{name}: statements by id", (s["id"] for s in brief["signals"]))
    unique(f"{name}: things to tell by id", (t["id"] for t in brief["card"]["tell"]))
    unique(f"{name}: role suggestions", brief["card"]["also"])
    known = {s["id"] for s in brief["signals"]}
    for told in brief["card"]["tell"]:
        unique(f"{name}: statements behind “{told['line']}”", told["signals"])
        if not set(told["signals"]) <= known:
            failures.append(f"{name}: “{told['line']}” cites a statement that is not there")
    for need in brief["card"]["needs"]:
        unique(f"{name}: skills of {need['title']}", need["skills"])
        unique(f"{name}: statements behind {need['title']}", need["signals"])
        if need.get("family") not in signals.FAMILIES:
            failures.append(f"{name}: {need['title']} has no known field ({need.get('family')!r})")
presets = json.loads((HERE / "presets.json").read_text())
unique("events by title", (p["title"] for p in presets))
for preset in presets:
    unique(f"{preset['title']}: employers", preset["ids"])
pool = json.loads((HERE / "pool.json").read_text())
unique("past events by id", (e["id"] for e in pool["events"]))
if set(pool["fields"]) - set(signals.FAMILIES):
    failures.append(f"the pool has fields the roles do not: {sorted(set(pool['fields']) - set(signals.FAMILIES))}")

# 2. sign-ups: what the server keeps and what it refuses
need = {"title": "Quantum engineers", "why": "", "can_do": [], "skills": [], "seniority": "Senior", "signals": [], "roles": []}
kept = {
    "as the page saves it": {"status": "joined", "needs": [{**need, "id": "n0", "ok": True}, {**need, "id": "n1"}], "signed": ["quantum"], "events": ["quantum"]},
    "with no roles left": {"status": "invited", "needs": []},
}
refused = {
    "as older builds saved it, roles without ids": {"status": "invited", "needs": [need, need]},
    "two roles with one id": {"status": "draft", "needs": [{**need, "id": "n0"}, {**need, "id": "n0"}]},
    "a role with an empty id": {"status": "draft", "needs": [{**need, "id": ""}]},
    "a status the page does not know": {"status": "confirmed", "needs": []},
    "no roles at all": {"status": "draft"},
}
for what, review in kept.items():
    if not serve.well_formed(review):
        failures.append(f"a sign-up {what} was refused")
for what, review in refused.items():
    if serve.well_formed(review):
        failures.append(f"a sign-up {what} was accepted")

# 3. a person's profile leaves no trace. The two outside services are stood in for, with a person who does not exist.
SECRET = "Xanthippe Quillfeather"
MATERIAL = f"Principal Cryogenic Weaver, Zzyzx Labs, 2019–now. Built dilution refrigerators for {SECRET} and led a team of nine."


def stand_in(url, body, headers):
    if "people/enrich" in url:
        return {"match": {"status": "candidate", "score": 100, "person": {
            "name": {"full": SECRET}, "bio": "", "skills": [], "education": [],
            "experience": [{"title": "Principal Cryogenic Weaver", "organization": {"name": "Zzyzx Labs"},
                            "start_date": {"year": 2019}, "is_current": True, "description": MATERIAL}]}}}
    return {"stop_reason": "end_turn", "content": [{"type": "text", "text": json.dumps({
        "headline": "Cryogenics engineer", "field": "Quantum", "level": "Lead",
        "can_do": [{"line": "Builds dilution refrigerators", "from": "Built dilution refrigerators"},
                   {"line": "Speaks nine languages", "from": "words that are not in the material"}],
        "name": "", "skills": [], "experience": [], "languages": []})}]}


def everything():
    return {str(p): p.stat().st_mtime_ns for p in HERE.rglob("*") if p.is_file() and "node_modules" not in p.parts and "__pycache__" not in p.parts}


calls = []


def counted(url, body, headers):
    calls.append(url)
    return stand_in(url, body, headers)


person.call = counted
# the stand-in never sends these; the code only needs them to be set
os.environ.setdefault("CONTEXT_DEV_API_KEY", "not-a-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "not-a-key")
before = everything()
printed = io.StringIO()
with contextlib.redirect_stderr(printed), contextlib.redirect_stdout(printed):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    request = urllib.request.Request(f"http://127.0.0.1:{server.server_address[1]}/person", method="POST",
                                     data=json.dumps({"kind": "linkedin", "value": "https://www.linkedin.com/in/xanthippe-quillfeather"}).encode())
    with urllib.request.urlopen(request, timeout=30) as response:
        answer = json.load(response)
    reads = sum("people/enrich" in url for url in calls)
    request = urllib.request.Request(f"http://127.0.0.1:{server.server_address[1]}/person", method="POST",
                                     data=json.dumps({"kind": "linkedin", "value": "linkedin.com/in/Xanthippe-Quillfeather/?trk=x"}).encode())
    with urllib.request.urlopen(request, timeout=30) as response:
        again = json.load(response)
    server.shutdown()
if again != answer or sum("people/enrich" in url for url in calls) != reads:
    failures.append("the same LinkedIn profile, written another way, was read twice")
if answer.get("name") != SECRET or [x["line"] for x in answer["can_do"]] != ["Builds dilution refrigerators"] or answer["dropped"] != 1:
    failures.append(f"the profile came back wrong: {answer}")
if everything() != before:
    changed = sorted(set(everything().items()) ^ set(before.items()))
    failures.append(f"reading a profile wrote to disk: {[path for path, _ in changed][:5]}")
for trace in (SECRET, "Quillfeather", "quillfeather", "Zzyzx", "dilution"):
    if trace in printed.getvalue():
        failures.append(f"reading a profile printed something of the person: {trace!r}")


# 4. what a stranger can no longer change, with a key set as on the server
serve.KEY = "a-test-key"
serve.REVIEWS = pathlib.Path(tempfile.mkdtemp()) / "reviews.json"
server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{server.server_address[1]}"


def status(method, path, body=None, **headers):
    request = urllib.request.Request(base + path, method=method, headers=headers,
                                     data=None if body is None else json.dumps(body).encode())
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


one, other = briefs[0]["id"], briefs[1]["id"]
signup = kept["as the page saves it"]
with contextlib.redirect_stderr(io.StringIO()):
    expected = {
        "a sign-up with neither key nor link": (status("POST", f"/review?id={one}", signup), 403),
        "a sign-up with another company's link": (status("POST", f"/review?id={one}", signup, **{"x-kutsu-link": serve.link_token(other)}), 403),
        "a sign-up with its own link": (status("POST", f"/review?id={one}", signup, **{"x-kutsu-link": serve.link_token(one)}), 200),
        "a sign-up with the key": (status("POST", f"/review?id={other}", signup, **{"x-kutsu-key": "a-test-key"}), 200),
        "taking every sign-up out without the key": (status("DELETE", "/reviews"), 403),
        "taking every sign-up out with a wrong key": (status("DELETE", "/reviews", **{"x-kutsu-key": "a-test-kez"}), 403),
        "unlocking with a wrong key": (status("GET", "/unlock", **{"x-kutsu-key": "nope"}), 403),
        "unlocking with the key": (status("GET", "/unlock", **{"x-kutsu-key": "a-test-key"}), 204),
    }
    if set(serve.reviews()) != {one, other}:
        failures.append(f"the sign-ups saved are not the two allowed: {sorted(serve.reviews())}")
    expected["taking every sign-up out with the key"] = (status("DELETE", "/reviews", **{"x-kutsu-key": "a-test-key"}), 200)
    if serve.reviews():
        failures.append("every sign-up was taken out, and some are still there")
    serve.ROLE_LIMIT, serve.roles["drafted"] = 0, 0
    expected["a role draft past the cap"] = (status("POST", f"/role?id={one}", {"line": "a quantum engineer"}), 429)
    serve.REVIEWS.write_text('{"shape": 3, "reviews": {"half')
    if serve.reviews() != {} or serve.REVIEWS.exists():
        failures.append("a sign-ups file that is not JSON was not set aside")
server.shutdown()
for what, (got, want) in expected.items():
    if got != want:
        failures.append(f"{what}: answered {got}, not {want}")

if failures:
    print("\n".join(failures), file=sys.stderr)
    sys.exit(1)
print(f"data: {len(briefs)} companies keyed uniquely, {len(kept) + len(refused)} sign-up shapes judged right, a profile read left no trace "
      f"and was read once, {len(expected)} writes with and without the key answered right")
