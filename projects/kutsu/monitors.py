"""Watch every company Kutsu knows, with Context.dev monitors, so "who to invite" has a reason that updates by itself.

Each company gets up to two monitors:
  careers  its careers page (a page monitor, 1 credit a run): a job opening added or removed
  news     a web search for it (a search monitor, 2 credits a run): funding, growth, expansion

Context.dev runs them on a schedule and keeps what changed; `changes()` reads that back for the page.
Nothing here is cached: monitors are live state on Context.dev's side.

  sops exec-env ../../secrets/secrets.yaml 'python3 monitors.py create'   # one per company and kind; skips those that exist
  sops exec-env ../../secrets/secrets.yaml 'python3 monitors.py status'   # how many, what they cost, what changed
  sops exec-env ../../secrets/secrets.yaml 'python3 monitors.py delete'   # remove them all, after the event
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import signals

TAG = "kutsu"
HOURS = 6  # between runs
COST = {"careers": 1, "news": 2}  # credits a run
CAREERS = ("Report when a job opening is added to or removed from this page, and name the role. "
           "Ignore changes to layout, banners, images and wording that do not add or remove an opening.")
NEWS = ("Report only a new development about the company {name} ({domain}) that shows it is growing or changing size: "
        "funding, an acquisition, a new site or office, a large order or customer, a hiring plan, lay-offs. "
        "Ignore results about other companies and results with nothing new. Do not name any person.")


def call(method, path, body=None):
    request = urllib.request.Request(
        f"{signals.CONTEXT}{path}", data=None if body is None else json.dumps(body).encode(), method=method,
        headers={"authorization": f"Bearer {os.environ['CONTEXT_DEV_API_KEY']}", "content-type": "application/json", "user-agent": "kutsu"})
    for wait in (2, 5, 15, None):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response) if response.status != 204 else {}
        except urllib.error.HTTPError as error:
            if error.code != 429 or wait is None:
                raise RuntimeError(f"{method} {path}: HTTP {error.code} {error.read()[:300].decode('utf8', 'replace')}") from None
            time.sleep(wait)


def every(path, **query):
    """All items of a list endpoint, following its cursor."""
    items, cursor = [], None
    while True:
        page = call("GET", f"{path}?{urllib.parse.urlencode({**query, 'limit': 100, **({'cursor': cursor} if cursor else {})})}")
        items += page["data"]
        if not page.get("has_more"):
            return items
        cursor = page["next_cursor"]


def of(monitor):
    """(brief id, kind) of one of our monitors, read from its tags."""
    tags = monitor.get("tags") or []
    return next((t[3:] for t in tags if t.startswith("id:")), ""), next((t for t in tags if t in COST), "")


def wanted(brief):
    """The monitors a company should have: {kind: request body}."""
    identity = brief.get("identity") or {}
    # the name the press uses, not the one in the trade register
    name = identity.get("name") or re.sub(r"\s+(Oyj Abp|Oyj|Oy Ab|Oy|Ab|sr)$", "", brief["name"], flags=re.I)
    domain = identity.get("domain") or urllib.parse.urlsplit(brief.get("website") or "").hostname or ""
    tags = lambda kind: [TAG, kind, f"id:{brief['id']}"[:50]]
    schedule = {"type": "interval", "frequency": HOURS, "unit": "hours"}
    out = {"news": {"name": f"{name}: news"[:200], "tags": tags("news"), "schedule": schedule,
                    "target": {"type": "search", "query": f'"{name}" funding OR investment OR expansion OR hiring OR acquisition',
                               "instructions": NEWS.format(name=name, domain=domain)}}}
    if identity.get("careers"):
        out["careers"] = {"name": f"{name}: careers page"[:200], "tags": tags("careers"), "schedule": schedule,
                          "target": {"type": "page", "url": identity["careers"], "instructions": CAREERS}}
    return out


def create():
    have = {of(m) for m in every("/monitors", tag=TAG)}
    made = spent = 0
    for brief in json.loads(signals.OUT.read_text()):
        for kind, body in wanted(brief).items():
            if (brief["id"], kind) in have:
                continue
            try:
                answer = call("POST", "/monitors", body)
            except RuntimeError as error:
                print(f"  {brief['name']} {kind}: {error}", file=sys.stderr)
                continue
            made += 1
            spent += (answer.get("key_metadata") or {}).get("credits_consumed", 0)
    print(f"created {made} monitors ({len(have)} were there already); {spent} credits for their first runs")


def changes(since=None):
    """What the monitors saw change, newest first, and what is watched, by brief id."""
    watched = {}
    for monitor in every("/monitors", tag=TAG):
        brief, kind = of(monitor)
        watched.setdefault(brief, {})[kind] = {"last_run_at": monitor.get("last_run_at"), "next_run_at": monitor.get("next_run_at"),
                                               "last_change_at": monitor.get("last_change_at")}
    seen = []
    for change in every("/monitors/changes", tag=TAG, **({"since": since} if since else {})):
        brief, kind = of(change)
        text = f"{change.get('title') or ''}. {change.get('summary') or ''}"
        if signals.PERSON.search(text):  # the same rule as everywhere else: nothing that names a person
            continue
        seen.append({"id": change["id"], "brief": brief, "kind": kind, "title": change.get("title") or "", "summary": change.get("summary") or "",
                     "url": change.get("url") or "", "detected_at": change.get("detected_at") or "", "importance": change.get("importance") or ""})
    return {"watched": watched, "changes": seen}


def status():
    monitors = every("/monitors", tag=TAG)
    kinds = [of(m)[1] for m in monitors]
    per_run = sum(COST.get(k, 0) for k in kinds)
    print(f"{len(monitors)} monitors: {kinds.count('careers')} careers pages, {kinds.count('news')} news searches, every {HOURS} hours")
    print(f"{per_run} credits for one run of all of them, {per_run * 24 // HOURS} a day")
    print(f"limits: {json.dumps({k: v for k, v in call('GET', '/monitors/limits').items() if k != 'request_id'})}")
    seen = changes()["changes"]
    print(f"{len(seen)} changes so far")
    for change in seen[:10]:
        print(f"  {change['detected_at'][:16]} {change['brief']} {change['kind']}: {change['title']}")


def delete():
    monitors = every("/monitors", tag=TAG)
    for monitor in monitors:
        call("DELETE", f"/monitors/{monitor['id']}")
    print(f"deleted {len(monitors)} monitors")


if __name__ == "__main__":
    {"create": create, "status": status, "delete": delete}[sys.argv[1] if len(sys.argv) > 1 else "status"]()
