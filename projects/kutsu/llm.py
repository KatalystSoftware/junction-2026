"""The reading step: one small-model call per job posting for the fields that need reading.

Stdlib only (the flake has no Anthropic SDK), so this is a plain HTTPS call to the Messages API.
The key comes from the environment (`sops exec-env secrets/secrets.yaml ...`) and is never
written anywhere. Every answer is cached under work/llm/ by prompt hash, and the spend is
tracked from the API's own usage numbers in work/spend.json with a hard stop below the $10 cap.
Without a key only cached answers are used.
"""

import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.request

import lib

MODEL = "claude-haiku-5-5"
USD_PER_MTOK_IN, USD_PER_MTOK_OUT = 0.10, 0.50
SPEND_STOP_USD = 9.0
API = "https://api.anthropic.com/v1/messages"
DIR = lib.HERE / "work" / "llm"
LEDGER = lib.HERE / "work" / "spend.json"
BODY_CHARS = 12000

FAMILIES = ["backend", "frontend", "mobile", "data", "ml", "devops", "qa", "embedded", "design",
            "product", "security", "support", "erp", "game", "other"]
SKILLS = json.loads((lib.HERE / "esittely" / "data" / "skills.json").read_text())
SKILL_IDS = [s["id"] for s in SKILLS]


def _vq(values):
    return {"type": "object", "additionalProperties": False, "required": ["value", "quote"],
            "properties": {"value": {"type": "string", "enum": values}, "quote": {"type": "string"}}}


_SKILL_ITEM = {"type": "object", "additionalProperties": False, "required": ["skill", "skill_id", "quote"],
               "properties": {"skill": {"type": "string"}, "skill_id": {"type": "string", "enum": SKILL_IDS + ["none"]},
                              "quote": {"type": "string"}}}
SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["is_job_posting", "is_tech_role", "role_family", "language_requirement", "seniority",
                 "employment_type", "working_time", "workplace", "location", "deadline", "must_have", "nice_to_have"],
    "properties": {
        "is_job_posting": {"type": "boolean"},
        "is_tech_role": {"type": "boolean"},
        "role_family": {"type": "string", "enum": FAMILIES},
        "language_requirement": _vq(["finnish_required", "other_language_required", "english_enough", "not_stated"]),
        "seniority": _vq(["intern", "junior", "mid", "senior", "lead", "not_stated"]),
        "employment_type": _vq(["permanent", "fixed_term", "internship", "thesis", "part_time", "freelance", "not_stated"]),
        "working_time": _vq(["full_time", "part_time", "not_stated"]),
        "workplace": _vq(["remote", "hybrid", "onsite", "not_stated"]),
        "location": {"type": "object", "additionalProperties": False, "required": ["value", "quote"],
                     "properties": {"value": {"type": "string"}, "quote": {"type": "string"}}},
        "deadline": {"type": "object", "additionalProperties": False, "required": ["value", "quote"],
                     "properties": {"value": {"type": "string"}, "quote": {"type": "string"}}},
        "must_have": {"type": "array", "items": _SKILL_ITEM},
        "nice_to_have": {"type": "array", "items": _SKILL_ITEM},
    },
}

SYSTEM = """You read one job posting and fill in a form about it. You are strict about evidence.

Every `quote` must be copied character for character from the posting text: one short contiguous \
span (at most about 200 characters), no paraphrase, no ellipsis, no joining of separate lines, \
nothing translated. If the posting does not say something, use "not_stated" (or an empty list) \
with an empty quote. Never guess. Never put a person's name, email address or phone number in \
any field; pick a different span.

Fields:
- is_job_posting: true only if the text is one specific open job advertisement (not a careers \
landing page, a list of jobs, a service description, a blog post or an open application).
- is_tech_role: true if the job is in software, data, AI, cloud, security, embedded or hardware \
or electronics engineering, QA and testing, UX/UI/service/product design, product management, or \
IT (support, administration, ERP and business systems, architecture). Technical research in those \
areas counts. Sales, marketing, HR, finance, legal, production operators, mechanical, civil, \
chemical or process engineering without a software or electronics core do not.
- role_family: the closest of backend (server software, general software), frontend, mobile, \
data (data engineering, analytics), ml (machine learning, AI, data science), devops (cloud, \
infrastructure, SRE), qa, embedded (embedded software, electronics, hardware, RF, chips), design, \
product (product and project management), security, support (IT support and administration), \
erp (SAP, ERP, CRM, business systems), game; otherwise other. The duties and the required skills \
decide, not the employer's industry or a single word in the title: a developer at a game studio \
who builds server software is backend, and a consultant who configures SAP is erp. Scientific or \
standards research is other unless the work is mostly building software or hardware, and a manager \
of people who does not do the team's technical work hands-on is other.
- language_requirement: finnish_required if the posting requires Finnish (fluent, native, \
excellent or good Finnish, "sujuva suomi", "suomen kielen taito"), also when it requires Finnish \
and English together. other_language_required if it requires a language other than Finnish or \
English (German, Swedish and so on) and not Finnish. english_enough if it states that English is \
the required or working language and requires no other language (Finnish or another language as \
a plus or an advantage is still english_enough). not_stated if the posting says nothing about language \
skills, whatever language it is written in. Quote the sentence part that states it.
- seniority: intern (interns, trainees, thesis workers, summer jobs), junior, mid, senior, lead \
(lead, principal, staff, head, manager of people). Quote the word or phrase that shows it (the \
title word or a years-of-experience phrase). not_stated if nothing shows it.
- employment_type: permanent, fixed_term, internship, thesis, part_time or freelance, only if \
stated. "Full-time" alone is not_stated.
- working_time: full_time or part_time, only if the posting states it ("Full-time", "kokoaikainen", \
"osa-aikainen", "100 %"), with the span that states it; otherwise not_stated.
- workplace: remote (fully remote work is offered), hybrid (office and remote days are mixed) or \
onsite (the work is done on site or at the office), only if the posting says so anywhere, \
including the benefits and the location line. Quote the span that says it; a place name alone is \
not_stated.
- location: every place of work the posting names, as written (all of them when several are \
listed, and the country when it is given), with the span that lists them as quote; empty strings \
if not written.
- deadline: the application deadline as YYYY-MM-DD in value and the span stating it in quote; \
empty strings if none is stated.
- must_have: up to 8 skills or qualifications the posting requires. `skill` is a short label \
(for example "Python", "5+ years of backend experience"), `quote` the span that requires it. \
Only real requirements: not duties, not benefits, not examples of what the team uses.
- nice_to_have: up to 8 that the posting itself marks as a plus, an advantage, a bonus or nice \
to have. A requirement without such a mark belongs in must_have.
- skill_id: for each must_have and nice_to_have item, the id from this list that names the same \
skill, or "none". Use an id only when the item names that very skill or technology: another \
product of the same kind (a different ERP, cloud, database or language) or a broad category is \
"none". When in doubt, "none". The ids: """ + "; ".join(f"{s['id']} = {s['label']}" for s in SKILLS)

_lock = threading.Lock()
_spend = None


def _ledger():
    global _spend
    if _spend is None:
        _spend = json.loads(LEDGER.read_text()) if LEDGER.exists() else {
            "model": MODEL, "calls": 0, "input_tokens": 0, "output_tokens": 0, "usd": 0.0, "errors": 0}
    return _spend


def spend():
    with _lock:
        return dict(_ledger())


def _call(body):
    req = urllib.request.Request(API, data=json.dumps(body).encode(), method="POST", headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
        "content-type": "application/json"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 529) and attempt < 4:
                time.sleep(float(e.headers.get("retry-after") or 2 ** attempt * 2))
                continue
            return {"error": f"http {e.code}", "detail": e.read(300).decode("utf-8", "replace")}
        except Exception as e:
            if attempt < 4:
                time.sleep(2 ** attempt)
                continue
            return {"error": type(e).__name__}


def read_posting(company, title, body):
    """Return the filled form for one posting (dict), or None if there is no answer."""
    text = f"Company: {company}\nJob title: {title}\n\nPosting text:\n{body[:BODY_CHARS]}"
    h = hashlib.sha256((MODEL + "\x00" + SYSTEM + "\x00" + text).encode()).hexdigest()
    path = DIR / f"{h}.json"
    if path.exists():
        return json.loads(path.read_text())
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    with _lock:
        if _ledger()["usd"] >= SPEND_STOP_USD:
            return None
    resp = _call({
        "model": MODEL, "max_tokens": 3000, "thinking": {"type": "disabled"},
        "output_config": {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        "system": SYSTEM, "messages": [{"role": "user", "content": text}]})
    out = None
    with _lock:
        led = _ledger()
        u = resp.get("usage") or {}
        tin = u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
        led["calls"] += 1
        led["input_tokens"] += tin
        led["output_tokens"] += u.get("output_tokens", 0)
        led["usd"] = round(led["input_tokens"] * USD_PER_MTOK_IN / 1e6 + led["output_tokens"] * USD_PER_MTOK_OUT / 1e6, 4)
        if resp.get("stop_reason") == "end_turn":
            try:
                out = json.loads(next(b["text"] for b in resp["content"] if b["type"] == "text"))
            except Exception:
                out = None
        if out is None:
            led["errors"] += 1
            led["last_error"] = str(resp.get("error") or resp.get("stop_reason"))[:80] + " " + str(resp.get("detail", ""))[:200]
        LEDGER.parent.mkdir(exist_ok=True)
        LEDGER.write_text(json.dumps(led))
    if out is not None:
        DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, ensure_ascii=False))
    return out
