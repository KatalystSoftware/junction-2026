"""The talent brief app: the built page from ui/dist, stored briefs, live research and review state.

    npm --prefix ui ci && npm --prefix ui run build
    sops exec-env ../../secrets/secrets.yaml 'python3 serve.py'      # http://127.0.0.1:8046

GET  /brief?q=<company id, name or domain>  runs signals.brief, saves the result and returns it
GET  /progress?q=<same>                     the steps that research has taken so far
GET  /reviews.json                          every brief's sign-up state: status, the needs, what the company changed
POST /review?id=<brief id>                  replaces one of those (the officer's edits, or the company's sign-up)
POST /posting?id=<brief id>                 drafts a job posting for the need in the body

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
import urllib.parse

import lib
import signals

HOST, PORT = os.environ.get("HOST", "127.0.0.1"), 8046
LIVE_LIMIT = int(os.environ.get("LIVE_LIMIT", "300"))  # about $0.03 and 11 Context.dev credits each
DIST = lib.HERE / "ui" / "dist"
REVIEWS = lib.HERE / "reviews.json"
DATA = {"/signals.json": "signals.json", "/presets.json": "presets.json", "/reviews.json": "reviews.json"}
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
         ".svg": "image/svg+xml", ".woff2": "font/woff2", ".png": "image/png", ".ico": "image/x-icon"}
STATUSES = {"draft", "invited", "joined"}
COMPANIES, ROLES = signals.data()
saving = threading.Lock()
asked = {x.lower() for b in json.loads(signals.OUT.read_text()) for x in (b["id"], b["name"])}
START = len(asked)
researching = threading.BoundedSemaphore(4)
progress = {}  # query -> the steps its research has taken


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
        if url.path in DATA:
            path = lib.HERE / DATA[url.path]
            return self.reply(200, path.read_bytes() if path.exists() else b"{}", "application/json")
        if url.path == "/progress":
            return self.json(progress.get(q.lower(), []))
        if url.path == "/brief" and q:
            return self.research(q)
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
            return self.text(502, f"Research failed: {e}")
        finally:
            researching.release()
        if b is None:
            return self.text(502, "The model gave no answer for this company.")
        with saving:
            signals.save([b])
        self.json(b)

    def posting(self, brief, need):
        try:
            need = {"title": str(need["title"])[:120], "why": str(need["why"])[:300], "seniority": str(need["seniority"])[:40],
                    "skills": [str(k)[:60] for k in need["skills"]][:8]}
        except (KeyError, TypeError):
            need = None
        if not brief or not need or not need["title"].strip():
            return self.text(400, "A posting needs a known brief id and a need with a title.")
        if not researching.acquire(blocking=False):
            return self.text(429, "Busy. Try again in a minute.")
        try:
            draft = signals.posting(brief, need)
        except (SystemExit, KeyError) as e:
            return self.text(502, f"Drafting failed: {e}")
        finally:
            researching.release()
        self.json(draft) if draft else self.text(502, "The model gave no draft.")

    def do_POST(self):
        url = urllib.parse.urlsplit(self.path)
        brief_id = urllib.parse.parse_qs(url.query).get("id", [""])[0]
        length = int(self.headers.get("content-length") or 0)
        if url.path not in ("/review", "/posting") or not 0 < length < 50_000:
            return self.text(404, "not found")
        try:
            review = json.loads(self.rfile.read(length))
        except ValueError:
            return self.text(400, "The body is not JSON.")
        briefs = {b["id"]: b for b in json.loads(signals.OUT.read_text())}
        if url.path == "/posting":
            return self.posting(briefs.get(brief_id), review)
        known = set(briefs)
        if brief_id not in known or review.get("status") not in STATUSES or not isinstance(review.get("needs"), list):
            return self.text(400, "The review needs a known brief id, a status and a list of needs.")
        with saving:
            reviews = json.loads(REVIEWS.read_text()) if REVIEWS.exists() else {}
            reviews[brief_id] = {**review, "updated_at": lib.now_iso()}
            REVIEWS.write_text(json.dumps(reviews, ensure_ascii=False, indent=1))
        self.json(reviews[brief_id])


if __name__ == "__main__":
    print(f"http://{HOST}:{PORT}", file=sys.stderr)
    http.server.ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
