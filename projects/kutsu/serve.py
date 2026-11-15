"""The talent brief app: the built page from ui/dist, stored briefs, live research and review state.

    npm --prefix ui ci && npm --prefix ui run build
    sops exec-env ../../secrets/secrets.yaml 'python3 serve.py'      # http://127.0.0.1:8046

GET  /brief?q=<company id, name or domain>  runs signals.brief, saves the result and returns it
GET  /progress?q=<same>                     the steps that research has taken so far
GET  /reviews.json                          every brief's sign-up state: status, the needs, what the company changed
POST /review?id=<brief id>                  replaces one of those (the officer's edits, or the company's sign-up)
POST /role?id=<brief id>                    drafts a whole need from the one line in the body
POST /person                                a person's profile from their LinkedIn, a page of theirs or the text of a CV
DELETE /reviews                             takes out every sign-up (the demo's reset)
GET  /unlock                                204 when the x-kutsu-key header holds the demo key, or no key is set

Without keys the page still shows every brief already in signals.json, and anything in api-cache/
still answers.

The address is public, so everything that spends API credits is capped per process and shares one limit
of four at a time: research on companies not asked for before (LIVE_LIMIT), role drafts (ROLE_LIMIT) and
profile reads (PEOPLE_LIMIT; a LinkedIn profile read again is answered from memory, see `read_person`).

With KUTSU_KEY set, as on the server, a sign-up is saved only from Espoo's side unlocked with that key
(the x-kutsu-key header) or from a company's own invitation link, which carries a token signed with it
for that one company (x-kutsu-link). Taking every sign-up out needs the key. Anything else is answered
as before and is not saved. Without KUTSU_KEY, on a laptop, every write is open.
"""

import collections
import hashlib
import hmac
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
ROLE_LIMIT = int(os.environ.get("ROLE_LIMIT", "150"))  # one Haiku call each, about $0.01
KEY = os.environ.get("KUTSU_KEY", "")
DIST = lib.HERE / "ui" / "dist"
# The first version of the applicant's pages (projects/kutsu/esittely, once called Esittely; the product has one name,
# Kutsu), served under /apply/, with /esittely/ kept as a redirect, so the organiser's
# screen can open the invitation form: esittely/app in the repo, and deploy.sh copies that app itself to esittely/ on the server
ESITTELY = next((d for d in (lib.HERE / "esittely" / "app", lib.HERE / "esittely") if (d / "index.html").is_file()), None)
# The pitch deck (projects/kutsu/pitch), served under /pitch/
PITCH = lib.HERE / "pitch" if (lib.HERE / "pitch").is_dir() else None
REVIEWS = lib.HERE / "reviews.json"
DATA = {"/signals.json": "signals.json", "/presets.json": "presets.json", "/pool.json": "pool.json", "/applications.json": "applications.json"}
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
         ".svg": "image/svg+xml", ".woff2": "font/woff2", ".png": "image/png", ".jpg": "image/jpeg", ".pdf": "application/pdf", ".ico": "image/x-icon", ".md": "text/markdown; charset=utf-8"}
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
roles = {"drafted": 0}
# A LinkedIn profile already read in this process: by a hash of its username, the answer, so reading the same
# profile again spends nothing. Memory only, never written, gone at the next start, the oldest dropped past 200.
read_before = collections.OrderedDict()
watching = threading.Lock()
watch = {"read": 0.0, "seen": {"watched": {}, "changes": [], "checked_at": ""}}
progress = {}  # query -> the steps its research has taken


def reviews():
    """Every saved sign-up, by brief id. A file in another shape, or one that is not JSON, is moved aside and the result is empty."""
    if not REVIEWS.exists():
        return {}
    try:
        saved = json.loads(REVIEWS.read_text())
    except ValueError:
        saved = {"shape": "broken"}
    if not isinstance(saved, dict) or saved.get("shape") != REVIEW_SHAPE:
        aside = REVIEWS.with_name(f"reviews.shape-{saved.get('shape', 'unversioned') if isinstance(saved, dict) else 'broken'}-{int(time.time())}.json")
        REVIEWS.rename(aside)
        print(f"sign-ups saved in another shape were set aside as {aside.name}; starting with none", file=sys.stderr)
        return {}
    return saved["reviews"]


KEYS = ("EXA_API_KEY", "CONTEXT_DEV_API_KEY", "ANTHROPIC_API_KEY")


def missing_key(error):
    """The API key a request stopped on, when it stopped because this server runs without one."""
    name = error.args[0] if isinstance(error, KeyError) and error.args else ""
    return name if name in KEYS and not os.environ.get(name) else ""


def keep(saved):
    """Write every sign-up at once: to a file beside the real one, then put in its place, so a crash mid-write
    leaves the last whole file and never half of one."""
    part = REVIEWS.with_name(REVIEWS.name + ".part")
    with open(part, "w") as out:
        json.dump({"shape": REVIEW_SHAPE, "reviews": saved}, out, ensure_ascii=False, indent=1)
        out.flush()
        os.fsync(out.fileno())
    os.replace(part, REVIEWS)


def link_token(brief_id):
    """What a company's invitation link carries: the brief id signed with the key, so it opens that one sign-up only."""
    return hmac.new(KEY.encode(), f"join:{brief_id}".encode(), hashlib.sha256).hexdigest()[:24]


def linkedin_handle(value):
    """The username of a LinkedIn profile address, the same however it was written: case, scheme, www, a query or a trailing slash."""
    found = re.search(r"linkedin\.com/in/([^/?#\s]+)", str(value), re.I)
    return urllib.parse.unquote(found[1]).lower() if found else ""


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

    def organiser(self):
        """Espoo's side, unlocked with the demo key; on a laptop with no key set, anyone."""
        return not KEY or hmac.compare_digest(self.headers.get("x-kutsu-key", ""), KEY)

    def may_save(self, brief_id):
        """Espoo's side, or this company's own invitation link."""
        return self.organiser() or hmac.compare_digest(self.headers.get("x-kutsu-link", ""), link_token(brief_id))

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
        if url.path == "/unlock":
            return self.reply(204, b"", "text/plain") if self.organiser() else self.text(403, "That is not the demo key.")
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
        if url.path == "/pitch":
            self.send_response(301); self.send_header("location", "/pitch/"); self.end_headers(); return
        if url.path.startswith("/pitch/") and PITCH:
            rel = url.path[len("/pitch/"):] or "index.html"
            if rel.endswith("/"):  # a folder inside the deck (the light deck, /pitch/lite/)
                rel += "index.html"
            path = PITCH / rel
            if path.is_dir():  # /pitch/lite: relative links need the slash
                self.send_response(301); self.send_header("location", url.path + "/"); self.end_headers(); return
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
            if missing_key(e):
                return self.text(503, f"This server runs without {missing_key(e)}, so it can show only the companies already researched.")
            return self.text(502, "We could not research this company just now. Try again in a minute.")
        finally:
            researching.release()
        if b is None:
            return self.text(502, "The model gave no answer for this company.")
        with saving:
            signals.save([b])
        self.json(b)

    def person(self, handed):
        """A person's profile from what they handed over: {kind: linkedin | portfolio | cv, value, draft?}. Nothing of it is
        written or logged; a LinkedIn profile's answer is held in memory, see `read_before`."""
        if not isinstance(handed, dict):
            return self.text(400, "Choose your LinkedIn, a portfolio page or your CV.")
        draft = handed.get("draft") is not False
        handle = linkedin_handle(handed.get("value")) if handed.get("kind") == "linkedin" else ""
        known = hashlib.sha256(f"{handle}|{draft}".encode()).hexdigest() if handle else ""
        with saving:
            seen = read_before.get(known) if known else None
            if seen is not None:
                read_before.move_to_end(known)
        if seen is not None:
            return self.json(seen)
        with saving:
            if people["read"] >= PEOPLE_LIMIT:
                return self.text(429, "This demo has read as many profiles as it may. Type yours in instead.")
            people["read"] += 1
        if not researching.acquire(blocking=False):
            return self.text(429, "Busy. Try again in a minute.")
        try:
            answer = person.profile(handed.get("kind"), handed.get("value"), draft=draft)
            if known:
                with saving:
                    read_before[known] = answer
                    while len(read_before) > 200:
                        read_before.popitem(last=False)
            self.json(answer)
        except person.Unreadable as unreadable:
            self.text(422, str(unreadable))
        except (KeyError, OSError, ValueError, StopIteration) as error:  # a missing key, their side down, an answer in no shape
            print(f"a profile could not be read: {type(error).__name__}", file=sys.stderr)
            if missing_key(error):
                self.text(503, f"This server runs without {missing_key(error)}, so it cannot read a profile. Type yours in instead.")
            else:
                self.text(502, "We could not fill this in just now. Type it in yourself, or try again in a minute.")
        finally:
            researching.release()

    def draft(self, write):
        """One model draft, a few at a time and ROLE_LIMIT in all, as JSON."""
        with saving:
            if roles["drafted"] >= ROLE_LIMIT:
                return self.text(429, "This demo has drafted as many roles as it may. Write this one in yourself.")
            roles["drafted"] += 1
        if not researching.acquire(blocking=False):
            return self.text(429, "Busy. Try again in a minute.")
        try:
            draft = write()
        except (SystemExit, KeyError) as e:
            print(f"drafting failed: {e}", file=sys.stderr)
            if missing_key(e):
                return self.text(503, f"This server runs without {missing_key(e)}, so it cannot draft a role. Write it in yourself.")
            return self.text(502, "The draft did not come through.")
        finally:
            researching.release()
        self.json(draft) if draft else self.text(502, "The model gave no draft.")

    def do_DELETE(self):
        """Take out every saved sign-up: the demo's reset."""
        if urllib.parse.urlsplit(self.path).path != "/reviews":
            return self.text(404, "not found")
        if not self.organiser():
            return self.text(403, "Only Espoo's side, unlocked with the demo key, can take every sign-up out.")
        with saving:
            keep({})
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
        if not self.may_save(brief_id):
            return self.text(403, "Not saved: a sign-up is saved from the company's own invitation link, or from Espoo's side unlocked.")
        with saving:
            saved = reviews()
            saved[brief_id] = {**review, "updated_at": lib.now_iso()}
            keep(saved)
        self.json(saved[brief_id])


if __name__ == "__main__":
    reviews()  # sets a file of another shape aside now, at start, and says so
    print(f"http://{HOST}:{PORT}", file=sys.stderr)
    http.server.ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
