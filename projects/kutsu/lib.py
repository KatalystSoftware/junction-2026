"""Polite cached fetcher and the canonical "raw text" used by the extractor and validate.py.

Rules this module enforces (see README.md):
- identifiable User-Agent, robots.txt obeyed per host (RFC 9309: 4xx on robots.txt means no
  rules, 5xx or unreachable means disallow), at most one request per second per host
- every response, including errors and redirects, is cached on disk under cache/ and a cached
  URL is never fetched again
"""

import hashlib
import html
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
UA = (
    "KatalystJunction2026-EspooSpike/0.1 "
    "(+https://github.com/KatalystSoftware/junction2026; Junction 2026 hackathon research, "
    "one request per second, obeys robots.txt)"
)
UA_TOKEN = "KatalystJunction2026-EspooSpike"
MIN_INTERVAL = 1.0
MAX_BYTES = 8_000_000
TIMEOUT = 20
# ESPOO_OFFLINE=1: cache only, for re-running the extractor while another process is crawling
OFFLINE = bool(os.environ.get("ESPOO_OFFLINE"))

_host_locks = {}
_host_last = {}
_robots = {}
_guard = threading.Lock()
stats = {"network": 0, "cache": 0, "robots_blocked": 0}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _paths(url):
    h = hashlib.sha256(url.encode()).hexdigest()
    return CACHE / h[:2] / f"{h}.body", CACHE / h[:2] / f"{h}.json"


def cached(url):
    """Return (meta, body) for a cached URL, or None."""
    body_p, meta_p = _paths(url)
    if not meta_p.exists():
        return None
    meta = json.loads(meta_p.read_text())
    body = body_p.read_bytes() if body_p.exists() else b""
    return meta, body


def _store(url, meta, body):
    body_p, meta_p = _paths(url)
    body_p.parent.mkdir(parents=True, exist_ok=True)
    body_p.write_bytes(body)
    meta_p.write_text(json.dumps(meta))


def _host_lock(host):
    with _guard:
        if host not in _host_locks:
            _host_locks[host] = threading.Lock()
        return _host_locks[host]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def _raw_get(url, accept=None):
    """One HTTP GET, no redirect following, rate limited per host. Returns (meta, body)."""
    host = urllib.parse.urlsplit(url).netloc.lower()
    with _host_lock(host):
        wait = _host_last.get(host, 0) + _crawl_delay(host) - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        headers = {"User-Agent": UA, "Accept-Language": "en,fi;q=0.8"}
        if accept:
            headers["Accept"] = accept
        req = urllib.request.Request(url, headers=headers)
        meta = {"url": url, "retrieved_at": now_iso()}
        body = b""
        try:
            with _opener.open(req, timeout=TIMEOUT) as r:
                body = r.read(MAX_BYTES)
                meta.update(status=r.status, content_type=r.headers.get("Content-Type", ""))
        except urllib.error.HTTPError as e:
            meta.update(status=e.code, content_type=e.headers.get("Content-Type", ""))
            loc = e.headers.get("Location")
            if e.code in (301, 302, 303, 307, 308) and loc:
                meta["location"] = urllib.parse.urljoin(url, loc)
            else:
                try:
                    body = e.read(200_000)
                except Exception:
                    pass
        except Exception as e:  # DNS, TLS, timeout
            meta.update(status=0, error=f"{type(e).__name__}: {e}"[:200])
        _host_last[host] = time.monotonic()
        stats["network"] += 1
    return meta, body


_delays = {}


def _crawl_delay(host):
    return max(MIN_INTERVAL, _delays.get(host, 0))


def _robots_for(scheme, host):
    key = f"{scheme}://{host}"
    with _guard:
        if key in _robots:
            return _robots[key]
    url = key + "/robots.txt"
    hit = cached(url)
    if hit is None:
        meta, body = _raw_get(url)
        hops = 0
        # robots.txt may redirect (RFC 9309 says follow at least five hops)
        while meta.get("location") and hops < 5:
            m2, body = _raw_get(meta["location"])
            meta = {**m2, "url": url, "final_url": m2["url"]}
            hops += 1
        _store(url, meta, body)
    else:
        meta, body = hit
    status = meta.get("status", 0)
    rp = urllib.robotparser.RobotFileParser()
    if 200 <= status < 300:
        text = body.decode("utf-8", "replace")
        # an HTML page served at /robots.txt is not a robots file
        if "<html" in text[:2000].lower():
            rp.parse([])
        else:
            rp.parse(text.splitlines())
            d = rp.crawl_delay(UA_TOKEN)
            if d:
                _delays[host] = float(d)
    elif 400 <= status < 500:
        rp.parse([])  # no robots file: everything allowed
    else:
        rp.parse(["User-agent: *", "Disallow: /"])  # unreachable: assume disallowed
    with _guard:
        _robots[key] = rp
    return rp


def allowed(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme not in ("http", "https") or not p.netloc:
        return False
    return _robots_for(p.scheme, p.netloc.lower()).can_fetch(UA_TOKEN, url)


def fetch(url, accept=None, max_hops=5):
    """GET with cache, robots and rate limit. Returns (meta, body).

    meta: url, final_url, status, content_type, retrieved_at. status -1 = blocked by robots.txt,
    0 = network error. Redirect hops are each checked against robots.txt and cached.
    """
    url = urllib.parse.urldefrag(url)[0]
    hit = cached(url)
    if hit is not None:
        stats["cache"] += 1
        return hit
    if OFFLINE:
        return {"url": url, "status": 0, "error": "offline"}, b""
    first = url
    cur = url
    meta, body = None, b""
    for _ in range(max_hops + 1):
        if not allowed(cur):
            stats["robots_blocked"] += 1
            meta, body = {"url": cur, "status": -1, "retrieved_at": now_iso(), "error": "robots.txt"}, b""
            break
        hit = cached(cur) if cur != first else None
        meta, body = hit if hit else _raw_get(cur, accept)
        if not hit and cur != first:
            _store(cur, {**meta, "final_url": cur}, body)
        if meta.get("location") and meta.get("status") in (301, 302, 303, 307, 308):
            cur = urllib.parse.urldefrag(meta["location"])[0]
            continue
        break
    meta = {**meta, "url": first, "final_url": meta.get("final_url", cur)}
    meta.pop("location", None)
    _store(first, meta, body)
    return meta, body


def ok(meta):
    return 200 <= meta.get("status", 0) < 300


# --- canonical raw text -----------------------------------------------------------------------

_WS = re.compile(r"\s+")
_TAG = re.compile(r"<[^>]{0,2000}>")
_DROP = re.compile(r"<(script|style|noscript|svg|template)\b[^>]*>.*?</\1\s*>", re.S | re.I)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_LD = re.compile(r"<script[^>]*type=[\"']?application/ld\+json[\"']?[^>]*>(.*?)</script>", re.S | re.I)
_ATTR = re.compile(r"\b(?:content|href|src|data-src|action|title|alt)\s*=\s*(\"[^\"]*\"|'[^']*')", re.I)


def norm(s):
    """Whitespace normalisation applied to both quotes and source text before comparing."""
    return _WS.sub(" ", s.replace("​", "").replace("﻿", "")).strip()


def strip_tags(s):
    s = s.replace("<![CDATA[", " ").replace("]]>", " ")
    s = _COMMENT.sub(" ", s)
    s = _DROP.sub(" ", s)
    s = _TAG.sub(" ", s)
    return html.unescape(s)


def _strings(obj, out):
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _strings(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _strings(v, out)


def json_text(obj):
    """All string values of a JSON value. Strings holding (escaped) HTML are unescaped and
    stripped; the untouched string is kept too so URLs and plain values match verbatim."""
    out = []
    _strings(obj, out)
    parts = []
    for s in out:
        parts.append(s)
        if "<" in s or "&" in s:
            parts.append(strip_tags(html.unescape(s)))
    return norm("\n".join(parts))


def ld_json(doc):
    """Parsed JSON-LD blocks of an HTML document."""
    out = []
    for m in _LD.finditer(doc):
        raw = m.group(1).strip()
        try:
            out.append(json.loads(raw))
        except Exception:
            try:
                out.append(json.loads(html.unescape(raw), strict=False))
            except Exception:
                pass
    return out


def html_text(doc):
    """Visible text, then attribute values (meta content, href, ...), then JSON-LD strings."""
    lds = ld_json(doc)
    attrs = [html.unescape(m.group(1)[1:-1]) for m in _ATTR.finditer(_DROP.sub(" ", doc))]
    first = strip_tags(doc)
    parts = [first, "\n".join(attrs)]
    if "<" in first:
        # entity-escaped HTML (RSS <description>) comes out of the first pass as literal tags
        parts.append(strip_tags(first))
    parts += [json_text(x) for x in lds]
    return norm("\n".join(parts))


def decode(body, content_type=""):
    m = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    enc = m.group(1) if m else None
    if not enc:
        m = re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", body[:4000], re.I)
        enc = m.group(1).decode() if m else "utf-8"
    try:
        return body.decode(enc, "replace")
    except LookupError:
        return body.decode("utf-8", "replace")


def raw_text(body, content_type=""):
    """The canonical text of a cached response. validate.py checks quotes against exactly this."""
    doc = decode(body, content_type)
    head = doc.lstrip()[:1]
    if "json" in (content_type or "").lower() or head in ("{", "["):
        try:
            return json_text(json.loads(doc))
        except Exception:
            pass
    return html_text(doc)


def source_text(url):
    """Canonical text of a cached URL, or None if it is not cached with a 2xx status."""
    hit = cached(url)
    if hit is None or not ok(hit[0]):
        return None
    return raw_text(hit[1], hit[0].get("content_type", ""))


# --- personal data ------------------------------------------------------------------------------

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"(?<![\w/=.-])(?:\+|00)?\d[\d\s().-]{7,}\d(?![\w/-])")
CONTACT = re.compile(
    r"\b(contact|reach out to|questions|lisätietoj|lisätietoa antaa|yhteyshenkil|yhteystied|tiedustelu|"
    r"recruiter|hiring manager|talent acquisition partner|rekrytoija|ota yhteytt|soita|call us|"
    r"tavoitat|vastaa mielellään|happy to answer|more information|for further information)",
    re.I,
)


DATE = re.compile(r"\d{1,2}\.\s?\d{1,2}\.\s?\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}")
NAME = re.compile(r"\b[A-ZÅÄÖ][a-zåäöé]+(?:-[A-ZÅÄÖ][a-zåäö]+)? [A-ZÅÄÖ][a-zåäöé]+\b")


def has_personal_data(s):
    """True if a string looks like it carries a contact person, an email or a phone number."""
    if EMAIL.search(s):
        return True
    for m in PHONE.finditer(DATE.sub(" ", s)):
        if sum(c.isdigit() for c in m.group()) >= 9:
            return True
    return bool(CONTACT.search(s) and NAME.search(s))
