"""The talent brief app: the built page from ui/dist, stored briefs, live research and review state.

    npm --prefix ui ci && npm --prefix ui run build
    sops exec-env ../../secrets/secrets.yaml 'python3 serve.py'      # http://127.0.0.1:8046

GET  /brief?q=<company id, name or domain>  runs signals.brief, saves the result and returns it
GET  /progress?q=<same>                     the steps that research has taken so far
GET  /reviews.json                          every brief's sign-up state: status, the needs, what the company changed
POST /review?id=<brief id>                  replaces one of those (the officer's edits, or the company's sign-up)
POST /role?id=<brief id>                    drafts a whole need from the one line in the body

Without keys the page still shows every brief already in signals.json, and anything in api-cache/
still answers.

On a public address (HOST=0.0.0.0, see deploy.sh) anyone can spend our API credits, so companies
not asked for before are capped at LIVE_LIMIT per process, a few at a time. Reviews are open to
anyone with the address too: this is a demo, and a real one would sign the company's link.
"""

import http.server
import json
import os
import re
import sys
import threading
import time
import urllib.parse

import lib
import monitors
import person
import signals

HOST, PORT = os.environ.get("HOST", "127.0.0.1"), 8046
LIVE_LIMIT = int(os.environ.get("LIVE_LIMIT", "300"))  # about $0.03 and 11 Context.dev credits each
DIST = lib.HERE / "ui" / "dist"
# The first version of the applicant's pages (projects/espoo-recruitment, once called Esittely; the product has one name,
# Kutsu), served under /apply/, with /esittely/ kept as a redirect, so the organiser's
# screen can open the invitation form: a copy next to this file on the server, the sibling project in the repo
ESITTELY = next((d for d in (lib.HERE / "esittely", lib.HERE.parent / "espoo-recruitment" / "app") if d.is_dir()), None)
REVIEWS = lib.HERE / "reviews.json"
DATA = {"/signals.json": "signals.json", "/presets.json": "presets.json", "/pool.json": "pool.json", "/applications.json": "applications.json"}
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
         ".svg": "image/svg+xml", ".woff2": "font/woff2", ".png": "image/png", ".ico": "image/x-icon", ".md": "text/markdown; charset=utf-8"}
STATUSES = {"draft", "invited", "joined"}
# What a saved sign-up holds. Raise it whenever that changes: a file saved in another shape is set aside
# at start, never read, because the page keys its lists by what is in it and must not meet an old one.
REVIEW_SHAPE = 3
COMPANIES, ROLES = signals.data()
saving = threading.Lock()
asked = {x.lower() for b in json.loads(signals.OUT.read_text()) for x in (b["id"], b["name"])}
START = len(asked)
researching = threading.BoundedSemaphore(4)
# a person's profile read costs up to 20 Context.dev credits, and the address is public: a small budget per start
PEOPLE_LIMIT = int(os.environ.get("PEOPLE_LIMIT", "60"))
people = {"read": 0}
watching = threading.Lock()
watch = {"read": 0.0, "seen": {"watched": {}, "changes": [], "checked_at": ""}}
progress = {}  # query -> the steps its research has taken


def reviews():
    """Every saved sign-up, by brief id. A file in another shape is moved aside and the result is empty."""
    if not REVIEWS.exists():
        return {}
    saved = json.loads(REVIEWS.read_text())
    if saved.get("shape") != REVIEW_SHAPE:
        aside = REVIEWS.with_name(f"reviews.shape-{saved.get('shape', 'unversioned')}.json")
        REVIEWS.rename(aside)
        print(f"sign-ups saved in another shape were set aside as {aside.name}; starting with none", file=sys.stderr)
        return {}
    return saved["reviews"]


def changes():
    """What Context.dev's monitors saw change, read from it at most every five minutes. Without a key nothing is watched."""
    with watching:
        if "CONTEXT_DEV_API_KEY" in os.environ and time.time() - watch["read"] > 300:
            watch["read"] = time.time()
            try:
                watch["seen"] = {**monitors.changes(), "checked_at": lib.now_iso()}
            except (RuntimeError, OSError) as error:  # their side is down: the last answer stands until the next try
                print(f"monitors: {error}", file=sys.stderr)
        return watch["seen"]


def well_formed(review):
    """A sign-up the page can show: a known status, and needs that each carry their own id and a title."""
    needs = review.get("needs")
    return (review.get("status") in STATUSES and isinstance(needs, list)
            and all(isinstance(n, dict) and isinstance(n.get("id"), str) and n["id"] and isinstance(n.get("title"), str)
                    for n in needs)
            and len({n["id"] for n in needs}) == len(needs))


class Handler(http.server.BaseHTTPRequestHandler):
    timeout = 30  # seconds a client may take to send its request

    def reply(self, status, body, content_type):
        self.send_response(status)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "max-age=31536000, immutable" if status == 200 and "/assets/" in self.path
                         else "no-store")
        self.end_headers()
        self.wfile.write(body)

    def text(self, status, message):
        self.reply(status, message.encode(), "text/plain; charset=utf-8")

    def json(self, value):
        self.reply(200, json.dumps(value, ensure_ascii=False).encode(), "application/json")

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        q = urllib.parse.parse_qs(url.query).get("q", [""])[0].strip()[:100]
        if url.path == "/reviews.json":
            return self.json(reviews())
        if url.path == "/changes.json":
            return self.json(changes())
        if url.path in DATA:
            return self.reply(200, (lib.HERE / DATA[url.path]).read_bytes(), "application/json")
        if url.path == "/progress":
            return self.json(progress.get(q.lower(), []))
        if url.path == "/brief" and q:
            return self.research(q)
        if url.path == "/apply" or url.path == "/esittely" or url.path.startswith("/esittely/"):
            rest = url.path[len("/esittely/"):] if url.path.startswith("/esittely/") else ""
            self.send_response(301); self.send_header("location", "/apply/" + rest); self.end_headers(); return
        if url.path.startswith("/apply/") and ESITTELY:
            rel = url.path[len("/apply/"):] or "index.html"
            path = ESITTELY / rel
            if not re.fullmatch(r"[\w.-]+(/[\w.-]+)*", rel) or ".." in rel or not path.is_file():
                return self.text(404, "not found")
            return self.reply(200, path.read_bytes(), TYPES.get(path.suffix, "application/octet-stream"))
        # the built page: index.html, and files under assets/ whose names the build chose
        name = "index.html" if url.path == "/" else url.path.lstrip("/")
        path = DIST / name
        if not re.fullmatch(r"index\.html|favicon\.svg|assets/[\w.-]+", name) or not path.is_file():
            return self.text(404, "not found")
        self.reply(200, path.read_bytes(), TYPES.get(path.suffix, "application/octet-stream"))

    def research(self, q):
        new = q.lower() not in asked
        if new and len(asked) >= LIVE_LIMIT + START:
            return self.text(429, "This demo has used up its live research budget.")
        if not researching.acquire(blocking=False):
            return self.text(429, "Busy with other searches. Try again in a minute.")
        steps = progress[q.lower()] = []
        try:
            asked.add(q.lower())
            b = signals.brief(q, COMPANIES, ROLES, lambda stage, facts: steps.append({"stage": stage, **facts}))
        except (SystemExit, KeyError) as e:  # an API turned the request down, or a key is not in the environment
            print(f"research failed for {q!r}: {e}", file=sys.stderr)
            return self.text(502, "We could not research this company just now. Try again in a minute.")
        finally:
            researching.release()
        if b is None:
            return self.text(502, "The model gave no answer for this company.")
        with saving:
            signals.save([b])
        self.json(b)

    def person(self, handed):
        """A person's profile from what they handed over: {kind: linkedin | portfolio | cv, value, draft?}. Nothing of it is kept or logged."""
        if not isinstance(handed, dict):
            return self.text(400, "Choose your LinkedIn, a portfolio page or your CV.")
        with saving:
            if people["read"] >= PEOPLE_LIMIT:
                return self.text(429, "This demo has read as many profiles as it may. Type yours in instead.")
            people["read"] += 1
        if not researching.acquire(blocking=False):
            return self.text(429, "Busy. Try again in a minute.")
        try:
            self.json(person.profile(handed.get("kind"), handed.get("value"), draft=handed.get("draft") is not False))
        except person.Unreadable as unreadable:
            self.text(422, str(unreadable))
        except (KeyError, OSError, ValueError, StopIteration) as error:  # a missing key, their side down, an answer in no shape
            print(f"a profile could not be read: {type(error).__name__}", file=sys.stderr)
            self.text(502, "We could not fill this in just now. Type it in yourself, or try again in a minute.")
        finally:
            researching.release()

    def draft(self, write):
        """One model draft, a few at a time, as JSON."""
        if not researching.acquire(blocking=False):
            return self.text(429, "Busy. Try again in a minute.")
        try:
            draft = write()
        except (SystemExit, KeyError) as e:
            print(f"drafting failed: {e}", file=sys.stderr)
            return self.text(502, "The draft did not come through.")
        finally:
            researching.release()
        self.json(draft) if draft else self.text(502, "The model gave no draft.")

    def do_DELETE(self):
        """Take out every saved sign-up: the demo's reset."""
        if urllib.parse.urlsplit(self.path).path != "/reviews":
            return self.text(404, "not found")
        with saving:
            REVIEWS.write_text(json.dumps({"shape": REVIEW_SHAPE, "reviews": {}}))
        self.json({})

    def do_POST(self):
        url = urllib.parse.urlsplit(self.path)
        brief_id = urllib.parse.parse_qs(url.query).get("id", [""])[0]
        length = int(self.headers.get("content-length") or 0)
        if url.path not in ("/review", "/role", "/person") or not 0 < length < 50_000:
            return self.text(404, "not found")
        try:
            review = json.loads(self.rfile.read(length))
        except ValueError:
            return self.text(400, "The body is not JSON.")
        if url.path == "/person":
            return self.person(review)
        briefs = {b["id"]: b for b in json.loads(signals.OUT.read_text())}
        if url.path == "/role":
            line = str(review.get("line") or "").strip()[:200] if isinstance(review, dict) else ""
            if not line or brief_id not in briefs:
                return self.text(400, "A role needs a known brief id and a line describing it.")
            return self.draft(lambda: signals.role(briefs[brief_id], line))
        if brief_id not in briefs or not isinstance(review, dict) or not well_formed(review):
            return self.text(400, "A sign-up needs a known brief id, a status, and needs that each have their own id and a title.")
        with saving:
            saved = reviews()
            saved[brief_id] = {**review, "updated_at": lib.now_iso()}
            REVIEWS.write_text(json.dumps({"shape": REVIEW_SHAPE, "reviews": saved}, ensure_ascii=False, indent=1))
        self.json(saved[brief_id])


if __name__ == "__main__":
    reviews()  # sets a file of another shape aside now, at start, and says so
    print(f"http://{HOST}:{PORT}", file=sys.stderr)
    http.server.ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
