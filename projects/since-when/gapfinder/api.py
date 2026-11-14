"""The HTTP API the app calls (docs/api.md) and the built app itself, from one FastAPI server.
One MariaDB connection per request. Every response carries the SQL that produced it, as run.

    python -m gapfinder serve --port 8078
    SINCE_WHEN_FIXTURES=1 python -m gapfinder serve    # answers from ui/fixtures/, no database
"""

import decimal
import json
import os
import re
import threading
import time
from datetime import date, datetime

import mariadb
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles

from .align import DAY, QID, TYPE_WEIGHT, YEARS, Run, as_of_sql, lit, nearest_sql
from .db import DB, LANGS
from .embed import MODEL

HERE = os.path.dirname(os.path.abspath(__file__))
# The built app (npm run build in ui/) and the fixture answers for a server without a database.
UI = os.environ.get("SINCE_WHEN_UI") or os.path.join(HERE, "..", "ui", "dist")
FIXTURES = os.path.join(HERE, "..", "ui", "fixtures")
USE_FIXTURES = os.environ.get("SINCE_WHEN_FIXTURES") == "1"
# A public instance takes no writes.
READ_ONLY = os.environ.get("SINCE_WHEN_READ_ONLY") == "1"

SEQ = f"seq_{YEARS[0]}_to_{YEARS[-1]}"
# Editor outcomes: the API's name, the stored status, and the coarse status the UI also reads.
OUTCOMES = {
    "edited": ("edited", "closed"),
    "talk": ("raised_on_talk", "reviewed"),
    "intentional": ("intentional_difference", "closed"),
    "not_real": ("not_a_difference", "closed"),
}
FROM_DB = {db: (name, coarse) for name, (db, coarse) in OUTCOMES.items()}
QUALITY = {
    "featured": {"fi": "Suositeltu", "sv": "Utmärkt", "en": "Featured"},
    "good": {"fi": "Hyvä artikkeli", "sv": "Bra", "en": "Good"},
}

TYPE_ORDER = "FIELD(type, " + ", ".join(f"'{t}'" for t, _ in sorted(TYPE_WEIGHT.items(), key=lambda x: -x[1])) + ")"


def quality(rows):
    """{lang: label} from (lang, quality) pairs, for the editions with a quality template."""
    return {lang: QUALITY[q][lang] for lang, q in rows if q in QUALITY}


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def readers_cte(qids=None):
    """User page views of each article over the last 12 complete months."""
    where = f"\n    AND a.wikidata_id IN ({', '.join(map(lit, qids))})" if qids else ""
    return f"""readers AS (
  SELECT a.wikidata_id, a.lang, SUM(v.views) AS readers
  FROM article AS a
  JOIN pageviews AS v ON v.lang = a.lang AND v.page_id = a.page_id
  WHERE v.month >= DATE_FORMAT(CURDATE() - INTERVAL 12 MONTH, '%Y-%m-01')
    AND v.month < DATE_FORMAT(CURDATE(), '%Y-%m-01'){where}
  GROUP BY a.wikidata_id, a.lang
)"""


def queue_sql(lang=None, qids=None, limit=50, offset=0):
    where = []
    if lang:
        where.append(f"r.lang = {lit(lang)}")
    if qids:
        where.append(f"t.wikidata_id IN ({', '.join(map(lit, qids))})")
    where = ("\n  WHERE " + " AND ".join(where)) if where else ""
    return f"""
WITH rich AS (
  -- the richest other edition: the one with the most passages today
  SELECT a.wikidata_id, a.lang, b.lang AS rich_lang,
         ROW_NUMBER() OVER (PARTITION BY a.wikidata_id, a.lang ORDER BY b.passages DESC, b.lang) AS rn
  FROM article AS a JOIN article AS b ON b.wikidata_id = a.wikidata_id AND b.lang <> a.lang
), {readers_cte(qids)}, f AS (
  -- open findings; the most checkable one sets the weight
  SELECT wikidata_id, lang,
         SUM(status = 'open') AS findings,
         MAX(IF(status = 'open', weight, 0)) AS weight,
         SUBSTRING_INDEX(GROUP_CONCAT(IF(status = 'open', type, NULL) ORDER BY weight DESC, {TYPE_ORDER}), ',', 1) AS top_type,
         CASE WHEN SUM(status = 'open') > 0 THEN 'open'
              WHEN SUM(status = 'raised_on_talk') > 0 THEN 'reviewed' ELSE 'closed' END AS status
  FROM finding GROUP BY wikidata_id, lang
), q AS (
  -- coverage is shown, not scored: a shorter article is not a defect
  SELECT t.wikidata_id, t.title_en AS topic, r.lang, r.rich_lang,
         COALESCE(rd.readers, 0) AS readers, c.coverage,
         COALESCE(f.weight, 0) AS gap,
         COALESCE(f.findings, 0) AS findings, f.top_type, COALESCE(f.status, 'open') AS status
  FROM topic AS t
  JOIN rich AS r ON r.wikidata_id = t.wikidata_id AND r.rn = 1
  JOIN coverage AS c ON c.wikidata_id = r.wikidata_id AND c.lang = r.lang
                    AND c.rich_lang = r.rich_lang AND c.is_current
  LEFT JOIN readers AS rd ON rd.wikidata_id = r.wikidata_id AND rd.lang = r.lang
  LEFT JOIN f ON f.wikidata_id = r.wikidata_id AND f.lang = r.lang{where}
)
SELECT q.*, ROUND(q.readers * q.gap) AS score, COUNT(*) OVER () AS total,
       (SELECT JSON_OBJECTAGG(a.lang, a.bytes) FROM article AS a
        WHERE a.wikidata_id = q.wikidata_id) AS size,
       (SELECT JSON_OBJECTAGG(a.lang, a.quality) FROM article AS a
        WHERE a.wikidata_id = q.wikidata_id AND a.quality IS NOT NULL) AS quality
FROM q
WHERE q.findings > 0
ORDER BY score DESC, q.gap DESC, q.coverage, q.wikidata_id, q.lang
LIMIT {int(limit)} OFFSET {int(offset)}"""


def queue_item(x):
    return {
        "wikidata_id": x["wikidata_id"],
        "topic": x["topic"],
        "lang": x["lang"],
        "rich_lang": x["rich_lang"],
        "readers": int(x["readers"]),
        "coverage": round(float(x["coverage"]), 3),
        "size": json.loads(x["size"] or "{}"),
        "score": int(x["score"]),
        "weight": round(float(x["gap"]), 2),
        "findings": int(x["findings"]),
        "top_type": x["top_type"],
        "status": x["status"],
        "quality": quality(json.loads(x["quality"] or "{}").items()),
    }


def findings_sql(qid=None, fid=None):
    """The latest version of each finding. A finding whose last version ended (the alignment
    no longer sees the gap) is reported as closed."""
    where = f"f.wikidata_id = {lit(qid)}" if qid else f"f.id = {int(fid)}"
    readers_qids = [qid] if qid else None
    return f"""
WITH v AS (
  SELECT f.*, f.row_start, f.row_end,
         ROW_NUMBER() OVER (PARTITION BY f.id ORDER BY f.row_end DESC) AS rn
  FROM finding FOR SYSTEM_TIME ALL AS f
  WHERE {where}
), {readers_cte(readers_qids)}
SELECT v.id, v.wikidata_id, v.lang, v.other_lang, v.type, v.section, v.other_section, v.summary,
       v.quote, v.other_quote, v.citation, v.other_citation, v.paragraph_citation,
       v.other_paragraph_citation, v.rev_id, v.other_rev_id,
       v.terms, v.distance, v.weight, v.opened_at, v.opened_after, v.closed_at, v.closed_after, v.history,
       v.status, v.status_url,
       v.row_end < NOW(6) AS gone,
       ROUND(COALESCE(rd.readers, 0) * v.weight) AS score
FROM v LEFT JOIN readers AS rd ON rd.wikidata_id = v.wikidata_id AND rd.lang = v.lang
WHERE v.rn = 1
ORDER BY NOT gone AND v.status = 'open' DESC, score DESC, v.weight DESC, v.distance DESC, v.share DESC, v.id"""


def finding(x):
    quotes, citations, paragraph = {}, {}, {}
    for lang, quote, cite, par in (
        (x["lang"], x["quote"], x["citation"], x["paragraph_citation"]),
        (x["other_lang"], x["other_quote"], x["other_citation"], x["other_paragraph_citation"]),
    ):
        if quote:
            quotes[lang], citations[lang], paragraph[lang] = quote, cite, par
    outcome, coarse = FROM_DB.get(x["status"], (None, "open"))
    return {
        "id": x["id"],
        "lang": x["lang"],
        "other_lang": x["other_lang"],
        "type": x["type"],
        "section": x["section"],
        "other_section": x["other_section"],
        "summary": x["summary"],
        "quotes": quotes,
        "citations": citations,
        "paragraph_citations": paragraph,
        "rev_ids": {x["lang"]: x["rev_id"], x["other_lang"]: x["other_rev_id"]},
        "terms": json.loads(x["terms"] or "[]"),
        "distance": None if x["distance"] is None else round(float(x["distance"]), 3),
        "weight": round(float(x["weight"]), 2),
        "score": int(x["score"]),
        "status": "closed" if x["gone"] else coarse,
        "outcome": outcome,
        "rev_url": x["status_url"],
        "opened_at": x["opened_at"],
        "opened_after": x["opened_after"],
        "history": bool(x["history"]),
        "closed_at": x["closed_at"] if x["gone"] else None,
        "closed_after": x["closed_after"] if x["gone"] else None,
    }


# --- The claim check ---------------------------------------------------------------------------

CHECKS_SQL = """
SELECT id, finding_id, outcome, reason, {status} AS status, as_of, type, lang, other_lang, section, other_section, quote, other_quote,
       rev_id, other_rev_id, summary, verdict, claim_lang, claim_quote, claim_about, searched, read_passages,
       evidence_lang, evidence_rev_id, evidence_section, evidence_quote,
       IF(outcome = 'set_aside', evidence_passage, NULL) AS evidence_passage,
       claim_figure, evidence_figure, judge, model
FROM checked_finding
WHERE wikidata_id = {qid}
ORDER BY id"""


def check_of(k):
    """What the check found for one finding: its outcome, the verdict, the judge and the passage
    that settled it. A set-aside row carries that passage whole, since it is all the page shows."""
    evidence = None
    if k["evidence_quote"] or k["evidence_passage"]:
        evidence = {
            "lang": k["evidence_lang"],
            "rev_id": k["evidence_rev_id"],
            "section": k["evidence_section"],
            "quote": k["evidence_quote"],
            "passage": k["evidence_passage"],
        }
    return {
        "outcome": k["outcome"],
        "reason": k["reason"],
        "verdict": k["verdict"],
        "judge": k["judge"],
        "as_of": k["as_of"],
        "claim": {"lang": k["claim_lang"], "quote": k["claim_quote"], "about": k["claim_about"]},
        "figures": [k["claim_figure"], k["evidence_figure"]] if k["claim_figure"] or k["evidence_figure"] else None,
        "searched": k["searched"],
        "read": k["read_passages"],
        "evidence": evidence,
    }


def _as_checked(k):
    """The fields of a finding that the check rewrote, for a `changed` or `new` row."""
    quotes = {lang: q for lang, q in ((k["lang"], k["quote"]), (k["other_lang"], k["other_quote"])) if q}
    return {
        "lang": k["lang"],
        "other_lang": k["other_lang"],
        "type": k["type"],
        "section": k["section"],
        "other_section": k["other_section"],
        "summary": k["summary"],
        "quotes": quotes,
        "citations": {},
        "paragraph_citations": {},
        "rev_ids": {k["lang"]: k["rev_id"], k["other_lang"]: k["other_rev_id"]},
        "terms": [],
    }


def apply_checks(findings, checks):
    """The findings with the claim check applied, and the check's totals for the topic.

    Each finding gets `check`: None when the check did not look at it (the word list's framing rows,
    coverage rows), else check_of. A `changed` finding is shown as the check rewrote it, under its own
    id and dates. A difference the check found itself is added with a negative id and no history."""
    if not checks:
        return [dict(f, check=None) for f in findings], None
    by_finding = {k["finding_id"]: k for k in checks if k["finding_id"] is not None}
    out = []
    for f in findings:
        k = by_finding.get(f["id"])
        f = dict(f, check=check_of(k) if k else None)
        if k and k["outcome"] == "changed":
            f.update(_as_checked(k))
        out.append(f)
    for k in checks:
        if k["finding_id"] is None:
            out.append(
                {
                    "id": -k["id"],
                    **_as_checked(k),
                    "distance": None,
                    "weight": 0.0,
                    "score": 0,
                    # A person can close a row the check found itself (checked.py hand).
                    "status": "closed" if k["status"] == "not_a_difference" else "open",
                    "outcome": "not_real" if k["status"] == "not_a_difference" else None,
                    "rev_url": None,
                    "opened_at": k["as_of"],
                    "opened_after": None,
                    "history": False,
                    "closed_at": None,
                    "closed_after": None,
                    "check": check_of(k),
                }
            )
    totals = {"judge": checks[0]["judge"], "model": checks[0]["model"], "as_of": checks[0]["as_of"], "set_aside": {}}
    for k in checks:
        if k["outcome"] == "set_aside":
            totals["set_aside"][k["reason"]] = totals["set_aside"].get(k["reason"], 0) + 1
        else:
            totals[k["outcome"]] = totals.get(k["outcome"], 0) + 1
    return out, totals


def checks(r, qid):
    """The topic's rows of checked_finding; none on a database loaded before the check existed. A
    table made before its status column (checked.py hand adds it) reads as all open."""
    for status in ("status", "'open'"):
        try:
            return r("What the claim check made of each finding", CHECKS_SQL.format(qid=lit(qid), status=status))
        except mariadb.ProgrammingError as e:
            if "status" not in str(e):
                return []
    return []


# --- Endpoints ---------------------------------------------------------------------------------


def queue(r, q):
    lang = q.get("lang", "all")
    if lang not in LANGS + ("all",):
        raise ApiError(400, "lang must be all, fi, sv or en")
    rows = r(
        "Gap queue",
        queue_sql(
            None if lang == "all" else lang, limit=_int(q, "limit", 50, 1, 500), offset=_int(q, "offset", 0, 0, 10**6)
        ),
    )
    return {
        "as_of": date.today(),
        "total": int(rows[0]["total"]) if rows else 0,
        "items": [queue_item(x) for x in rows],
    }


def topic(r, qid):
    t = r("Topic", f"SELECT * FROM topic WHERE wikidata_id = {lit(qid)}")
    if not t:
        raise ApiError(404, f"unknown topic {qid}")
    t = t[0]
    arts = r(
        "Articles today, with readers",
        f"""
WITH {readers_cte([qid])}
SELECT a.lang, a.title, a.rev_id, a.bytes, a.passages, a.refs, a.quality, COALESCE(rd.readers, 0) AS readers
FROM article AS a
LEFT JOIN readers AS rd ON rd.wikidata_id = a.wikidata_id AND rd.lang = a.lang
WHERE a.wikidata_id = {lit(qid)}""",
    )
    leads = r(
        "Leads",
        f"""
SELECT c.lang, c.ord, c.rev_id, p.text
FROM chunk AS c JOIN passage AS p ON p.sha = c.sha
WHERE c.wikidata_id = {lit(qid)} AND c.section = ''
ORDER BY c.lang, c.ord""",
    )
    lead = {}
    for x in leads:
        if x["lang"] not in lead:
            lead[x["lang"]] = {"text": x["text"], "rev_id": x["rev_id"]}
        elif "also" not in lead[x["lang"]]:
            lead[x["lang"]]["also"] = x["text"]
    found = r("Findings (latest version of each)", findings_sql(qid))
    findings, checked = apply_checks([finding(x) for x in found], checks(r, qid))
    return {
        "wikidata_id": qid,
        "topic": t["title_en"],
        "titles": {lang: t["title_" + lang] for lang in LANGS},
        "size": {a["lang"]: a["bytes"] for a in arts},
        "readers": {a["lang"]: int(a["readers"]) for a in arts},
        "refs": {a["lang"]: a["refs"] for a in arts},
        "quality": quality((a["lang"], a["quality"]) for a in arts),
        "leads": lead,
        "findings": findings,
        "checked": checked,
    }


def compare(r, qid, q):
    a, b, as_of = q.get("a", "fi"), q.get("b", "en"), q.get("as_of") or None
    if a not in LANGS or b not in LANGS or a == b:
        raise ApiError(400, "a and b must be two different editions: fi, sv, en")
    if as_of and not DAY.match(as_of):
        raise ApiError(400, "as_of must be YYYY-MM-DD")
    near = {x["id"]: x for x in r(f"Nearest {b} passage for each {a} passage", nearest_sql(qid, as_of, a, b))}
    texts = r(
        "Passages of both editions",
        f"""
SELECT c.id, c.lang, c.ord, c.section, c.chunk_no, c.rev_id, p.text, p.embedding IS NOT NULL AS embedded
FROM chunk FOR SYSTEM_TIME AS OF {as_of_sql(as_of)} AS c
JOIN passage AS p ON p.sha = c.sha
WHERE c.wikidata_id = {lit(qid)} AND c.lang IN ({lit(a)}, {lit(b)})
ORDER BY c.lang, c.ord""",
    )
    by_id = {x["id"]: x for x in texts}
    side = lambda x: {k: x[k] for k in ("section", "chunk_no", "rev_id", "text")} | {"chunk_id": x["id"]}
    # A passage is only missing once every passage of b has a vector; until then a far or absent
    # match is reported as pending, not as a gap. A match found is a match either way.
    b_done = all(x["embedded"] for x in texts if x["lang"] == b)
    rows = []
    for x in texts:
        if x["lang"] != a:
            continue
        n = near.get(x["id"])
        status = n["status"] if n else "pending"
        if status == "missing" and not b_done:
            status = "pending"
        other = by_id.get(n["other_id"]) if n and status in ("covered", "partly") else None
        rows.append(
            {
                "a": side(x),
                "b": side(other) if other else None,
                "distance": None if not n else round(float(n["distance"]), 3),
                "status": status,
            }
        )
    return {
        "as_of": as_of or date.today(),
        "a": a,
        "b": b,
        "rows": rows,
        "complete": b_done and all(x["embedded"] for x in texts if x["lang"] == a),
    }


def timeline(r, qid, q):
    lang, rich = q.get("lang", "en"), q.get("rich_lang", "fi")
    if lang not in LANGS or rich not in LANGS:
        raise ApiError(400, "lang and rich_lang must be fi, sv or en")
    sizes = r(
        "Article size on each 1 January",
        f"""
SELECT y.seq AS year, a.lang, a.bytes
FROM {SEQ} AS y
JOIN article FOR SYSTEM_TIME ALL AS a
  ON a.row_start <= MAKEDATE(y.seq, 1) AND a.row_end > MAKEDATE(y.seq, 1)
WHERE a.wikidata_id = {lit(qid)}
ORDER BY y.seq, a.lang""",
    )
    cov = r(
        "Coverage on each 1 January",
        f"""
SELECT YEAR(as_of) AS year, coverage
FROM coverage
WHERE wikidata_id = {lit(qid)} AND lang = {lit(lang)} AND rich_lang = {lit(rich)} AND NOT is_current
ORDER BY as_of""",
    )
    opened = r(
        "Open findings on each 1 January",
        f"""
SELECT y.seq AS year, COUNT(f.id) AS open_findings
FROM {SEQ} AS y
LEFT JOIN finding FOR SYSTEM_TIME ALL AS f
  ON f.row_start <= MAKEDATE(y.seq, 1) AND f.row_end > MAKEDATE(y.seq, 1)
 AND f.wikidata_id = {lit(qid)} AND f.lang = {lit(lang)} AND f.status = 'open'
GROUP BY y.seq""",
    )
    versions = r(
        "Every version of the findings",
        f"""
SELECT id, type, summary, status, status_url, other_lang, opened_after, closed_after, row_start, row_end
FROM finding FOR SYSTEM_TIME ALL
WHERE wikidata_id = {lit(qid)} AND lang = {lit(lang)}
ORDER BY id, row_start""",
    )
    revs = r(
        "Every loaded revision of the articles",
        f"""
SELECT lang, rev_id, row_start, row_end
FROM article FOR SYSTEM_TIME ALL
WHERE wikidata_id = {lit(qid)}
ORDER BY lang, row_start""",
    )
    years = {y: {"year": y, "size": {}, "coverage": None, "open_findings": 0} for y in YEARS}
    for x in sizes:
        years[x["year"]]["size"][x["lang"]] = x["bytes"]
    for x in cov:
        years[x["year"]]["coverage"] = round(float(x["coverage"]), 3)
    for x in opened:
        years[x["year"]]["open_findings"] = int(x["open_findings"])

    def diffs(x, after, when):
        """For each edition of the finding's pair edited between `after` (the last compared date
        without the change; None: none) and `when`, the diff that contains the change: from the
        revision current at `after` to the one current at `when`."""
        if after is None:
            return []
        start = datetime.combine(after, datetime.min.time())
        out = []
        for edition in (x["other_lang"], lang):
            mine = [v for v in revs if v["lang"] == edition]
            old = next((v for v in mine if v["row_start"] <= start < v["row_end"]), None)
            new = next((v for v in mine if v["row_start"] <= when < v["row_end"]), None)
            if new and new["row_start"] > start and (not old or old["rev_id"] != new["rev_id"]):
                out.append({"lang": edition, "rev_id": new["rev_id"], "old_rev_id": old["rev_id"] if old else None})
        return out

    def event(x, when, kind, after=None):
        e = {"date": when.date(), "finding_id": x["id"], "kind": kind, "type": x["type"], "summary": x["summary"]}
        if kind in ("opened", "closed"):
            # The change happened after `after` and no later than `date`; each diff contains it.
            e["after"] = after
            e["diffs"] = diffs(x, after, when)
            if e["diffs"]:
                e.update(rev_id=e["diffs"][-1]["rev_id"], rev_lang=e["diffs"][-1]["lang"])
        if x["status_url"] and x["status"] != "open":
            e["rev_url"] = x["status_url"]
        return e

    def kind_of(status):
        return "opened" if status == "open" else ("reviewed" if FROM_DB[status][1] == "reviewed" else "closed")

    events, prev = [], None
    for x in versions:
        if prev and prev["id"] == x["id"] and x["row_start"] == prev["row_end"]:
            if x["status"] != prev["status"]:
                events.append(event(x, x["row_start"], kind_of(x["status"])))
        else:  # a new finding, or the same one again after a period without it
            if prev and prev["row_end"].year < 2100:
                events.append(event(prev, prev["row_end"], "closed", prev["closed_after"]))
            events.append(event(x, x["row_start"], "opened", x["opened_after"]))
        prev = x
    if prev and prev["row_end"].year < 2100:
        events.append(event(prev, prev["row_end"], "closed", prev["closed_after"]))
    events.sort(key=lambda e: (e["date"], e["finding_id"]))
    return {"years": list(years.values()), "events": events}


def set_status(r, fid, body):
    """Store an editor's outcome. Body: {"outcome": "edited|talk|intentional|not_real" | null,
    "rev_url": str | null}; a null outcome reopens. The old status stays in the table's history."""
    body = body or {}
    outcome = body.get("outcome")
    if outcome is None and body.get("status") not in (None, "open"):
        raise ApiError(400, "outcome must be edited, talk, intentional or not_real; null reopens")
    if outcome is not None and outcome not in OUTCOMES:
        raise ApiError(400, "outcome must be edited, talk, intentional or not_real; null reopens")
    url = body.get("rev_url") or None
    if url and not re.match(r"^https?://", url):
        raise ApiError(400, "rev_url must be an http(s) URL")
    status = OUTCOMES[outcome][0] if outcome else "open"
    r(
        "Store the outcome (the old one stays in the table's history)",
        f"""
UPDATE finding SET status = {lit(status)}, status_url = {lit(url if outcome else None)},
       status_at = {"NOW(6)" if outcome else "NULL"}
WHERE id = {int(fid)}""",
    )
    rows = r("The finding", findings_sql(fid=fid))
    if not rows:
        raise ApiError(404, f"unknown finding {fid}")
    return finding(rows[0])


_embedder = []
SEARCH_MAX_DISTANCE = 0.55


def search(r, q):
    text = (q.get("q") or "").strip()
    if not text:
        raise ApiError(400, "q is required")
    limit = _int(q, "limit", 20, 1, 100)
    lang = q.get("lang", "all")
    if lang not in LANGS + ("all",):
        raise ApiError(400, "lang must be all, fi, sv or en")
    if not _embedder:
        from .embed import Embedder

        _embedder.append(Embedder(threads=2))
    vec = _embedder[0]([text])[0]
    r.cur.execute("SET @q = VEC_FromText(?)", (json.dumps([round(v, 6) for v in vec]),))
    r.log.append(
        {
            "label": "The question's bge-m3 vector",
            "query": f"SET @q = VEC_FromText('[…1024 numbers…]')  -- {text}",
            "ms": 0,
            "rows": 0,
        }
    )
    hits = r(
        "Nearest current passages (vector index on chunk_now)",
        f"""
SELECT n.wikidata_id, n.lang, n.section, VEC_DISTANCE_COSINE(n.embedding, @q) AS distance
FROM chunk_now AS n
ORDER BY VEC_DISTANCE_COSINE(n.embedding, @q)
LIMIT {limit * 5}""",
    )
    # An exact title in any edition comes first: vectors favour passages over names.
    named = r(
        "Topics with this exact title",
        f"""
SELECT wikidata_id FROM topic
WHERE {lit(text)} IN (title_fi, title_sv, title_en)""",
    )
    # Farther than this, bge-m3 matches anything: "zzzzqqq" is 0.64 from its nearest passage and
    # "Olof Palme" (not a topic) 0.56, while "Talvisota" is 0.54 from Winter War.
    near = [h["wikidata_id"] for h in hits if float(h["distance"]) <= SEARCH_MAX_DISTANCE]
    order = list(dict.fromkeys([x["wikidata_id"] for x in named] + near))[:limit]
    if not order:
        return {"items": []}
    rows = r("Queue rows of those topics", queue_sql(None if lang == "all" else lang, qids=order, limit=3 * len(order)))
    best = {}
    for x in rows:
        best.setdefault(x["wikidata_id"], x)  # rows come sorted by score
    return {"items": [queue_item(best[qid]) for qid in order if qid in best]}


def _int(q, name, default, lo, hi):
    try:
        v = int(q.get(name, default))
    except ValueError:
        raise ApiError(400, f"{name} must be a number")
    return max(lo, min(hi, v))


# ---------- live SQL: four preset statements, run as the SELECT-only user ----------
# The caller picks a preset and its parameters, never SQL text. Every statement comes from the
# templates below and runs on a connection of DB_RO_USER with a time limit and a row cap.

LIVE_SECONDS, LIVE_ROWS = 5, 500
LIVE_SLOTS = threading.BoundedSemaphore(4)  # runs at once; the rest get 429
FIRST_DAY = "2001-01-15"  # Wikipedia's first day

ASOF_SET = "SET SESSION system_versioning_asof = ?"
ASOF_SQL = """
SELECT @@system_versioning_asof AS session_as_of, c.rev_id, c.row_start,
       LEFT(p.text, 320) AS text
FROM chunk AS c
JOIN passage AS p ON p.sha = c.sha
WHERE c.wikidata_id = ? AND c.lang = ? AND c.ord = 0"""
HISTORY_SQL = """
SELECT c.rev_id, c.row_start, c.row_end, LEFT(p.text, 200) AS text
FROM chunk FOR SYSTEM_TIME ALL AS c
JOIN passage AS p ON p.sha = c.sha
WHERE c.wikidata_id = ? AND c.lang = ? AND c.ord = 0
ORDER BY c.row_start DESC"""

CHECK_SQL = """
SELECT id, finding_id, outcome, verdict, claim_lang, claim_quote, evidence_lang, evidence_quote, judge, search_sql
FROM checked_finding
WHERE finding_id = ? OR (? < 0 AND id = -?)"""

# name -> title, description, [(parameter, kind, default)] and the statements to run, each
# (label, text, values to bind). `nearest` is the tool's own alignment query, its text built by
# align.py from the validated values; `asof` and `history` bind theirs. `check` runs the statement
# the claim check stored for a finding (evidence.search_sql), as the check ran it: its text comes
# from the table, written by the check's loader, never from the request.
PRESETS = {
    "nearest": {
        "title": "Time travel + vector search",
        "description": "One statement: the passages of a topic as they stood on a date "
        "(FOR SYSTEM_TIME AS OF), each matched to its nearest passage in the "
        "other edition (VEC_DISTANCE_COSINE). The query the tool aligns with.",
        "params": [
            ("qid", "qid", "Q1412941"),
            ("date", "date", "2026-10-24"),
            ("a", "lang", "fi"),
            ("b", "lang", "en"),
        ],
        "statements": lambda v: [
            (
                "Nearest passage in the other edition, as of the date",
                nearest_sql(v["qid"], v["date"], v["a"], v["b"]),
                (),
            )
        ],
    },
    "asof": {
        "title": "system_versioning_asof",
        "description": "Set the session variable to a date, then run a plain query with no time "
        "clause: it returns the first passage as it stood on that date. Change "
        "the date and run the same statement again.",
        "params": [("qid", "qid", "Q1412941"), ("date", "date", "2026-10-22"), ("lang", "lang", "sv")],
        "statements": lambda v: [
            ("Set the session's point in time", ASOF_SET, (v["date"] + " 00:00:00",)),
            ("First passage, no time clause", ASOF_SQL, (v["qid"], v["lang"])),
        ],
    },
    "history": {
        "title": "FOR SYSTEM_TIME ALL",
        "description": "Every version of a topic's first passage that the table has held, "
        "newest first, with the row_start and row_end MariaDB kept for it.",
        "params": [("qid", "qid", "Q1412941"), ("lang", "lang", "en")],
        "statements": lambda v: [("Every version of the first passage", HISTORY_SQL, (v["qid"], v["lang"]))],
    },
    "check": {
        "title": "The claim check",
        "description": "How a difference was checked: the other article as it stood on the day "
        "(FOR SYSTEM_TIME AS OF), each of its sentences ranked by VEC_DISTANCE_COSINE to the claim, "
        "and dates, numbers and names matched with REGEXP. The statement the check ran, from the "
        "table it stored it in.",
        "params": [("finding", "finding", "14115")],
        "statements": lambda v: [
            ("The claim, the verdict and the statement the check ran", CHECK_SQL, (int(v["finding"]),) * 3),
            ("The other article's passages nearest the claim, sentence by sentence", _stored, ()),
        ],
    },
}


def _stored(rows):
    """The statement the check stored, from the previous statement's last column, unchanged inside a
    SELECT that leads with what the judge read: each passage's nearest sentence, its distance to
    the claim and how many of the claim's dates, numbers and names it matched."""
    if not rows or not rows[0][-1]:
        raise ApiError(404, "the claim check has no statement for this finding")
    return f"""SELECT ord, section, sentence, distance, term_hits, by_vector, by_terms, searched
FROM (
{rows[0][-1].strip()}
) AS checked
ORDER BY distance"""


def live_enabled():
    return bool(os.environ.get("DB_RO_USER") and os.environ.get("DB_RO_PASSWORD"))


def live_connect():
    """A connection of the SELECT-only user; its session carries the time limit and the row cap."""
    con = mariadb.connect(
        **{**DB, "user": os.environ["DB_RO_USER"], "password": os.environ["DB_RO_PASSWORD"]}, autocommit=True
    )
    cur = con.cursor()
    cur.execute(
        f"SET SESSION time_zone = '+00:00', max_statement_time = {LIVE_SECONDS}, sql_select_limit = {LIVE_ROWS}"
    )
    cur.close()
    return con


def live_presets(body=None):
    return {
        "enabled": live_enabled(),
        "limits": {"seconds": LIVE_SECONDS, "rows": LIVE_ROWS},
        "presets": [
            {
                "name": name,
                "title": p["title"],
                "description": p["description"],
                "params": [{"name": n, "kind": kind, "default": default} for n, kind, default in p["params"]],
            }
            for name, p in PRESETS.items()
        ],
    }


def live_params(body):
    """(preset name, validated values) from a request body, or ApiError 400."""
    if not isinstance(body, dict) or set(body) - {"preset", "params"}:
        raise ApiError(400, 'body must be {"preset": name, "params": {...}} and nothing else')
    name = body.get("preset")
    if not isinstance(name, str) or name not in PRESETS:
        raise ApiError(400, f"preset must be one of {', '.join(PRESETS)}")
    given = body.get("params", {})
    spec = PRESETS[name]["params"]
    if not isinstance(given, dict) or set(given) - {n for n, _, _ in spec}:
        raise ApiError(400, f"params of {name} are {', '.join(n for n, _, _ in spec)} and nothing else")
    values = {}
    for n, kind, default in spec:
        v = given.get(n, default)
        if not isinstance(v, str):
            raise ApiError(400, f"{n} must be a string")
        if kind == "qid" and not QID.fullmatch(v):
            raise ApiError(400, f"{n} must be a Wikidata id like Q1412941")
        if kind == "finding" and not re.fullmatch(r"-?[0-9]{1,9}", v):
            raise ApiError(400, f"{n} must be a finding id like 14115")
        if kind == "lang" and v not in LANGS:
            raise ApiError(400, f"{n} must be one of {', '.join(LANGS)}")
        if kind == "date":
            try:
                ok = (
                    bool(DAY.fullmatch(v))
                    and FIRST_DAY <= date.fromisoformat(v).isoformat() <= date.today().isoformat()
                )
            except ValueError:
                ok = False
            if not ok:
                raise ApiError(400, f"{n} must be a date YYYY-MM-DD from {FIRST_DAY} to today")
        values[n] = v
    if name == "nearest" and values["a"] == values["b"]:
        raise ApiError(400, "a and b must be two different editions")
    return name, values


def live_run(body):
    if not live_enabled():
        raise ApiError(503, "live SQL is off: this API has no read-only database user (DB_RO_USER)")
    name, values = live_params(body)
    if not LIVE_SLOTS.acquire(blocking=False):
        raise ApiError(429, "too many statements running, try again in a moment")
    con = None
    try:
        con = live_connect()
        cur = con.cursor()
        log, columns, rows, got = [], [], [], []
        for label, sql, binds in PRESETS[name]["statements"](values):
            if callable(sql):  # a statement read from the previous one's rows
                sql = sql(got)
            t0 = time.perf_counter()
            cur.execute(sql, binds) if binds else cur.execute(sql)  # a stored REGEXP may hold a "?"
            got = cur.fetchall() if cur.description else []
            ms = round((time.perf_counter() - t0) * 1000, 1)
            # As sent: the connector writes the bound values into the text as literals.
            shown = (
                "".join(part + (lit(binds[i]) if i < len(binds) else "") for i, part in enumerate(sql.split("?")))
                if binds
                else sql
            )
            log.append({"label": label, "query": shown.strip(), "ms": ms, "rows": len(got)})
            if cur.description:
                columns, rows = [d[0] for d in cur.description], [list(x) for x in got]
    except mariadb.Error as e:
        if e.errno == 1969:
            raise ApiError(504, f"stopped by MariaDB after {LIVE_SECONDS} seconds (max_statement_time)")
        raise ApiError(502, f"MariaDB refused the statement: {e}")
    finally:
        if con:
            con.close()
        LIVE_SLOTS.release()
    return {
        "preset": name,
        "params": values,
        "columns": columns,
        "rows": rows,
        "capped": len(rows) >= LIVE_ROWS,
        "ms": round(sum(x["ms"] for x in log), 1),
        "limits": {"seconds": LIVE_SECONDS, "rows": LIVE_ROWS},
        "sql": log,
    }


def search_enabled():
    """Whether the embedding model is on disk. Without it a search would download it into the server."""
    home = os.environ.get("HF_HOME") or os.path.expanduser("~/.cache/huggingface")
    hub = os.environ.get("HF_HUB_CACHE") or os.path.join(home, "hub")
    return os.path.isdir(os.path.join(hub, "models--" + MODEL.replace("/", "--")))


def _json(v):
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (bytes, bytearray)):
        return v.hex()
    raise TypeError(type(v))


class Json(Response):
    media_type = "application/json; charset=utf-8"

    def render(self, content):
        return json.dumps(content, default=_json, ensure_ascii=False).encode()


def _answer(fn, *args):
    """What fn returns, on a connection of its own, with the SQL it ran."""
    r = Run()
    try:
        body = fn(r, *args)
        body["sql"] = r.log
        return Json(body)
    finally:
        r.con.close()


def _fixture(*parts):
    """A file of ui/fixtures/, for a server started with SINCE_WHEN_FIXTURES=1 and no database."""
    path = os.path.join(FIXTURES, *parts)
    if not os.path.isfile(path):
        raise ApiError(404, "not in the fixtures")
    with open(path) as f:
        return json.load(f)


async def _body(request):
    try:
        return json.loads(await request.body() or b"{}")
    except json.JSONDecodeError:
        raise ApiError(400, "body must be JSON")


def _no_route(request):
    return ApiError(404, f"no route for {request.method} {request.url.path}")


def _qid(request, qid):
    if not QID.match(qid):
        raise _no_route(request)
    return qid


app = FastAPI(title="Since When", docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)


@app.exception_handler(ApiError)
def _api_error(request: Request, e: ApiError):
    return Json({"error": str(e)}, status_code=e.status)


@app.exception_handler(Exception)
def _error(request: Request, e: Exception):  # report, keep serving; uvicorn logs the traceback
    return Json({"error": f"{type(e).__name__}: {e}"}, status_code=500)


@app.get("/api/queue")
def get_queue(request: Request):
    if USE_FIXTURES:
        data, q = _fixture("queue.json"), request.query_params
        items = [i for i in data["items"] if q.get("lang", "all") in ("all", i["lang"])]
        offset, limit = _int(q, "offset", 0, 0, 10**6), _int(q, "limit", 50, 1, 200)
        return Json({**data, "total": len(items), "items": items[offset : offset + limit]})
    return _answer(queue, dict(request.query_params))


@app.get("/api/search")
def get_search(request: Request):
    if USE_FIXTURES or not search_enabled():
        raise ApiError(503, "search is off: this API has no embedding model on disk")
    return _answer(search, dict(request.query_params))


@app.get("/api/topics/{qid}")
def get_topic(request: Request, qid: str):
    if USE_FIXTURES:
        return Json(_fixture("topics", _qid(request, qid) + ".json"))
    return _answer(topic, _qid(request, qid))


@app.get("/api/topics/{qid}/compare")
def get_compare(request: Request, qid: str):
    q = request.query_params
    if USE_FIXTURES:
        return Json(_fixture("topics", _qid(request, qid), f"compare-{q.get('a', 'fi')}-{q.get('b', 'en')}.json"))
    return _answer(compare, _qid(request, qid), dict(q))


@app.get("/api/topics/{qid}/timeline")
def get_timeline(request: Request, qid: str):
    q = request.query_params
    if USE_FIXTURES:
        name = f"timeline-{q.get('lang')}-{q.get('rich_lang')}.json"
        return Json(_fixture("topics", _qid(request, qid), name))
    return _answer(timeline, _qid(request, qid), dict(q))


@app.post("/api/findings/{fid}/status")
async def post_status(request: Request, fid: str):
    if not fid.isdigit():
        raise _no_route(request)
    if READ_ONLY:
        raise ApiError(403, "this instance is read-only")
    if USE_FIXTURES:
        raise ApiError(503, "the fixtures are read-only")
    return await run_in_threadpool(_answer, set_status, int(fid), await _body(request))


# The two live SQL routes take no connection of the app user.
@app.get("/api/sql/presets")
def get_presets():
    return Json(live_presets())


@app.post("/api/sql/run")
async def post_run(request: Request):
    return Json(await run_in_threadpool(live_run, await _body(request)))


@app.api_route("/api/{rest:path}", methods=["GET", "POST"], include_in_schema=False)
def no_route(request: Request):
    raise _no_route(request)


if os.path.isdir(UI):
    app.mount("/", StaticFiles(directory=UI, html=True), name="app")


def serve(host="127.0.0.1", port=8078):
    data = "the fixtures" if USE_FIXTURES else f"MariaDB at {DB['host']}"
    print(f"Since When on http://{host}:{port}/ ({data})", flush=True)
    uvicorn.run(app, host=host, port=port)
