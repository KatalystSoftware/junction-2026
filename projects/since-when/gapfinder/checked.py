"""The checked findings: what the claim check (differences/claims.py) made of each classifier
finding, in a table the API can join to `finding` by id.

    python -m gapfinder.checked schema
    python -m gapfinder.checked load DIR      # DIR as demo/hero-verify.sh wrote it
    python -m gapfinder.checked hand FILE     # FILE as demo/hand-checked.json, or - for stdin

`load` reads DIR/differences.jsonl, DIR/set-aside.jsonl and DIR/run.json and replaces the rows of their topics
in checked_finding: one row per finding the check kept, changed, found itself or set aside. The
table and its columns are described in differences/README.md. Existing tables are only read:
`finding` to find the id of the finding a row is about, `chunk`, `passage` and `article` as of
the run's date for sections, revisions and the passage that settled a check.

`hand` applies what a person decided after reading both articles: it closes the rows found false
(finding.status, or checked_finding.status for a row the check found itself) and puts back a
summary or a quote. Rows are found by their quotes, so it works on any restore; run it after every load.
"""

import json
import sys
from datetime import date
from pathlib import Path

from .align import Run, as_of_sql
from .api import apply_checks, checks, finding, findings_sql
from .db import connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS checked_finding (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  wikidata_id   VARCHAR(16) NOT NULL,
  as_of         DATE NOT NULL,                     -- the day the editions were compared and searched
  finding_id    INT UNSIGNED NULL,                 -- finding.id this row is about; NULL: the check found it itself
  outcome       ENUM('kept','changed','new','set_aside','unchecked') NOT NULL,
  reason        ENUM('stated_elsewhere','not_confirmed','repeat') NULL,   -- why a row was set aside
  status        ENUM('open','not_a_difference') NOT NULL DEFAULT 'open',  -- a person's verdict on a `new` row
  -- The finding as it stands after the check, in finding's columns: `lang` is the edition to look
  -- at (the one lacking a missing fact, else the one with fewer passages).
  type          ENUM('missing_fact','contradiction','framing','numbers') NOT NULL,
  lang          CHAR(2) NOT NULL,
  other_lang    CHAR(2) NOT NULL,
  section       VARCHAR(512) NULL,
  other_section VARCHAR(512) NULL,
  quote         TEXT NULL,                         -- exact substring of lang's passage
  other_quote   TEXT NULL,
  rev_id        INT UNSIGNED NULL,                 -- the revisions the quotes are in
  other_rev_id  INT UNSIGNED NULL,
  summary       TEXT NOT NULL,
  -- The check: one claim of one edition, looked up in every passage of the other.
  verdict       ENUM('not_mentioned','contradicted','supported','unchecked') NULL,   -- NULL: not checked (framing)
  claim_lang    CHAR(2) NULL,
  claim_quote   TEXT NULL,
  claim_about   TEXT NULL,                         -- what the claim is about, in the judge's words
  claim_origin  VARCHAR(16) NULL,                  -- classifier: a row's quote; extract: a figure the check listed
  searched      SMALLINT UNSIGNED NULL,            -- passages of the other edition the search covered
  read_passages SMALLINT UNSIGNED NULL,            -- of them, read by the judge
  search_sql    MEDIUMTEXT NULL,                   -- the statement that picked them, runnable as it is
  -- The passage that settled it: where the fact is stated (supported), what contradicts the
  -- claim (contradicted), or where it would belong (not_mentioned; often NULL).
  evidence_lang     CHAR(2) NULL,
  evidence_chunk_id BIGINT UNSIGNED NULL,
  evidence_rev_id   INT UNSIGNED NULL,
  evidence_section  VARCHAR(512) NULL,
  evidence_quote    TEXT NULL,                     -- exact substring of evidence_passage
  evidence_passage  TEXT NULL,                     -- the passage's exact text
  evidence_distance FLOAT NULL,                    -- cosine distance of its nearest sentence to the claim
  claim_figure      VARCHAR(255) NULL,             -- the two figures as written, when the point is a figure
  evidence_figure   VARCHAR(255) NULL,
  reverse_verdict   ENUM('not_mentioned','contradicted','supported','unchecked') NULL,   -- the evidence, looked up back
  reverse_quote     TEXT NULL,
  judge         VARCHAR(64) NOT NULL,              -- the model that gave the verdicts
  model         VARCHAR(64) NULL,                  -- the model that wrote the finding
  run           VARCHAR(64) NOT NULL,              -- the folder the rows were loaded from
  loaded_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY (wikidata_id, outcome),
  UNIQUE KEY (finding_id)
) CHARACTER SET utf8mb4"""

COLUMNS = [
    "wikidata_id",
    "as_of",
    "finding_id",
    "outcome",
    "reason",
    "type",
    "lang",
    "other_lang",
    "section",
    "other_section",
    "quote",
    "other_quote",
    "rev_id",
    "other_rev_id",
    "summary",
    "verdict",
    "claim_lang",
    "claim_quote",
    "claim_about",
    "claim_origin",
    "searched",
    "read_passages",
    "search_sql",
    "evidence_lang",
    "evidence_chunk_id",
    "evidence_rev_id",
    "evidence_section",
    "evidence_quote",
    "evidence_passage",
    "evidence_distance",
    "claim_figure",
    "evidence_figure",
    "reverse_verdict",
    "reverse_quote",
    "judge",
    "model",
    "run",
]
# When two rows are about one finding (the classifier reported one sentence from two pairs), the
# one that found something wins: another statement, then the fact stated elsewhere.
RANK = {
    "changed": 0,
    "set_aside:stated_elsewhere": 1,
    "kept": 2,
    "set_aside:repeat": 3,
    "set_aside:not_confirmed": 4,
    "unchecked": 5,
}


def _read(path):
    return [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]


class Topic:
    """One topic's articles as of a date: passages by chunk id, revisions and sizes by edition, and
    its findings by their key and by their quotes."""

    def __init__(self, cur, qid, as_of):
        t = as_of_sql(None if as_of == date.today().isoformat() else as_of)
        cur.execute(
            f"""SELECT c.id, c.lang, c.section, p.text FROM chunk FOR SYSTEM_TIME AS OF {t} AS c
                JOIN passage AS p ON p.sha = c.sha WHERE c.wikidata_id = ?""",
            (qid,),
        )
        self.chunks = {row[0]: {"lang": row[1], "section": row[2], "text": row[3]} for row in cur.fetchall()}
        cur.execute(
            f"SELECT lang, rev_id, passages FROM article FOR SYSTEM_TIME AS OF {t} WHERE wikidata_id = ?", (qid,)
        )
        self.rev, self.size = {}, {}
        for lang, rev, passages in cur.fetchall():
            self.rev[lang], self.size[lang] = rev, passages
        cur.execute(
            "SELECT id, `key`, type, lang, other_lang, quote, other_quote FROM finding WHERE wikidata_id = ?", (qid,)
        )
        self.by_key, self.by_quotes = {}, {}
        for fid, key, type_, lang, other, quote, other_quote in cur.fetchall():
            self.by_key[key] = (fid, lang)
            self.by_quotes[(type_, frozenset({(lang, quote or ""), (other, other_quote or "")}))] = (fid, lang)

    def finding(self, qid, row):
        """(finding id, its `lang`) for a classifier row: by the key align.py gives it (topic,
        editions, type, top section and the quote's first 80 characters), and else, for framing
        rows keyed by their words, by its two quotes. (None, the edition align.py would name) when
        it has no finding."""
        _, _, a_lang, a_id, b_lang, b_id = row["pair_id"].split(":")
        quotes = {a_lang: row.get("quote_a") or "", b_lang: row.get("quote_b") or ""}
        poorer = a_lang if self.size.get(a_lang, 0) < self.size.get(b_lang, 0) else b_lang
        # The check corrects a missing fact that named the wrong edition; the finding was keyed
        # before that, under the edition the classifier named.
        lang = row.get("classifier_missing_in", row.get("missing_in")) or poorer
        other = b_lang if lang == a_lang else a_lang
        section = (self.chunks.get(int(a_id if lang == a_lang else b_id)) or {}).get("section") or ""
        ident = (quotes[lang] or quotes[other])[:80]
        hit = self.by_key.get(f"{qid}:{lang}:{other}:{row['type']}:{section.split(' › ')[0]}:{ident}")
        return hit or self.by_quotes.get((row["type"], frozenset(quotes.items()))) or (None, lang)


def record(topic, row, outcome, reason, run, judge):
    """One checked_finding row for a row of differences.jsonl or set-aside.jsonl."""
    qid = row["wikidata_id"]
    _, _, a_lang, a_id, b_lang, b_id = row["pair_id"].split(":")
    fid, lang = (None, None)
    if outcome != "new":
        fid, lang = topic.finding(qid, row.get("original") or row)
    if lang not in (a_lang, b_lang) or outcome in ("changed", "new"):
        # A row the check wrote: a missing fact belongs to the edition lacking it, the rest to the
        # edition with fewer passages, as align.py assigns them.
        poorer = a_lang if topic.size.get(a_lang, 0) < topic.size.get(b_lang, 0) else b_lang
        lang = (row.get("missing_in") if row["type"] == "missing_fact" else None) or poorer
    mine, theirs = ("a", "b") if lang == a_lang else ("b", "a")
    chunk = {"a": topic.chunks.get(int(a_id)) or {}, "b": topic.chunks.get(int(b_id)) or {}}
    other = b_lang if lang == a_lang else a_lang
    claim, checked, e = row.get("claim") or {}, row.get("checked") or {}, row.get("evidence") or {}
    both, back = row.get("figures") or {}, row.get("reverse") or {}
    passage = topic.chunks.get(e.get("chunk_id")) or {}
    verdict = row.get("verdict")
    return {
        "wikidata_id": qid,
        "as_of": row["as_of"],
        "finding_id": fid,
        "outcome": outcome,
        "reason": reason,
        "type": row["type"],
        "lang": lang,
        "other_lang": other,
        "section": chunk[mine].get("section"),
        "other_section": chunk[theirs].get("section"),
        "quote": row.get("quote_" + mine) or None,
        "other_quote": row.get("quote_" + theirs) or None,
        "rev_id": topic.rev.get(lang),
        "other_rev_id": topic.rev.get(other),
        "summary": row["summary"],
        "verdict": verdict if verdict in ("not_mentioned", "contradicted", "supported", "unchecked") else None,
        "claim_lang": claim.get("lang"),
        "claim_quote": claim.get("quote"),
        "claim_about": claim.get("about") or None,
        "claim_origin": claim.get("origin"),
        "searched": checked.get("searched"),
        "read_passages": checked.get("read"),
        "search_sql": checked.get("sql"),
        "evidence_lang": e.get("lang"),
        "evidence_chunk_id": e.get("chunk_id"),
        "evidence_rev_id": topic.rev.get(e.get("lang")) if e else None,
        "evidence_section": e.get("section"),
        "evidence_quote": e.get("quote") or None,
        "evidence_passage": passage.get("text"),
        "evidence_distance": e.get("distance"),
        "claim_figure": (both.get("claim") or "")[:255] or None,
        "evidence_figure": (both.get("evidence") or "")[:255] or None,
        "reverse_verdict": back.get("verdict"),
        "reverse_quote": (back.get("evidence") or {}).get("quote"),
        "judge": judge,
        "model": row.get("model"),
        "run": run,
    }


def records(cur, kept, aside, run):
    """The table's rows for one run: at most one per finding, and the rows with no finding."""
    judge = json.loads((Path(run) / "run.json").read_text())["judge"]
    topics, out = {}, []
    for row, set_aside in [(r, False) for r in kept] + [(r, True) for r in aside]:
        claim = row.get("claim") or {}
        if set_aside and claim.get("origin") != "classifier":
            continue  # a figure the check listed and did not confirm: never a finding
        if set_aside and row.get("aside") == "repeat":
            outcome, reason = "set_aside", "repeat"
        elif set_aside:
            outcome, reason = "set_aside", "stated_elsewhere" if row.get("verdict") == "supported" else "not_confirmed"
        elif not row.get("verdict"):
            outcome, reason = "unchecked", None
        elif not row.get("from_pair"):
            outcome, reason = "kept", None
        elif row.get("original"):
            first = row["original"]
            same = row["type"] == first["type"] and {row["quote_a"], row["quote_b"]} == {
                first["quote_a"],
                first["quote_b"],
            }
            outcome, reason = "kept" if same else "changed", None
        else:
            outcome, reason = "new", None
        key = (row["wikidata_id"], row["as_of"])
        if key not in topics:
            topics[key] = Topic(cur, *key)
        out.append(record(topics[key], row, outcome, reason, Path(run).name, judge))
    best = {}
    for r in out:
        rank = RANK[r["outcome"] + (":" + r["reason"] if r["reason"] else "")] if r["outcome"] != "new" else 0
        if r["finding_id"] is None:
            best[id(r)] = (rank, r)
        elif r["finding_id"] not in best or rank < best[r["finding_id"]][0]:
            best[r["finding_id"]] = (rank, r)
    return [r for _, r in best.values()], len(out) - len(best)


def load(run):
    kept, aside = _read(Path(run) / "differences.jsonl"), _read(Path(run) / "set-aside.jsonl")
    con = connect()
    cur = con.cursor()
    cur.execute(SCHEMA)
    rows, merged = records(cur, kept, aside, run)
    for qid in sorted({r["wikidata_id"] for r in rows}):
        cur.execute("DELETE FROM checked_finding WHERE wikidata_id = ?", (qid,))
    cur.executemany(
        f"INSERT INTO checked_finding ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})",
        [tuple(r[c] for c in COLUMNS) for r in rows],
    )
    con.commit()
    counts = {}
    for r in rows:
        name = r["outcome"] + (" " + r["reason"] if r["reason"] else "")
        counts[name] = counts.get(name, 0) + 1
    unlinked = sum(1 for r in rows if r["finding_id"] is None and r["outcome"] != "new")
    print(
        f"checked_finding: {len(rows)} rows for {len({r['wikidata_id'] for r in rows})} topics ("
        + ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
        + f"); {merged} more were about a finding another row already covers; "
        f"{unlinked} classifier rows have no finding (finding_id NULL)"
    )


# Tables made before the status column existed get it here.
STATUS = (
    "ALTER TABLE checked_finding ADD COLUMN IF NOT EXISTS "
    "status ENUM('open','not_a_difference') NOT NULL DEFAULT 'open' AFTER reason"
)


def hand(path):
    rows = json.load(sys.stdin if path == "-" else open(path, encoding="utf-8"))["rows"]
    con = connect(autocommit=True)
    cur = con.cursor()
    cur.execute(SCHEMA)
    cur.execute(STATUS)
    r = Run(con)
    for qid in sorted({x["topic"] for x in rows}):
        # The rows as the page shows them: a changed row with the check's quotes.
        shown, _ = apply_checks([finding(x) for x in r("findings", findings_sql(qid))], checks(r, qid))
        for x in (x for x in rows if x["topic"] == qid):
            hits = [
                f
                for f in shown
                if f["type"] == x["type"] and all(w in (f["quotes"].get(lang) or "") for lang, w in x["quotes"].items())
            ]
            if not hits:
                print(f"{qid}: no {x['type']} row quotes {x['quotes']}")
            for f in hits:
                ours = f["id"] < 0 or (f["check"] or {}).get("outcome") == "changed"
                where = f"id = {-f['id']}" if f["id"] < 0 else f"finding_id = {f['id']}"
                if "close" in x and f["id"] < 0:
                    cur.execute(f"UPDATE checked_finding SET status = 'not_a_difference' WHERE {where}")
                elif "close" in x:
                    cur.execute(
                        "UPDATE finding SET status = 'not_a_difference', status_url = NULL, status_at = NOW(6) "
                        "WHERE id = ? AND status <> 'not_a_difference'",
                        (f["id"],),
                    )
                for lang, words in x.get("quote", {}).items():
                    column = "quote" if f["lang"] == lang else "other_quote"
                    table, key = ("checked_finding", where) if ours else ("finding", f"id = {f['id']}")
                    cur.execute(f"UPDATE {table} SET {column} = ? WHERE {key} AND {column} <> ?", (words, words))
                if "summary" in x and ours:
                    cur.execute(f"UPDATE checked_finding SET summary = ? WHERE {where}", (x["summary"],))
                elif "summary" in x:
                    cur.execute("UPDATE finding SET summary = ? WHERE id = ?", (x["summary"], f["id"]))
                done = "closed" if "close" in x else "summary of" if "summary" in x else "quote of"
                print(f"{qid}: {done} {f['id']} {f['type']}: {f['summary'][:90]}")
    con.close()


def main():
    if sys.argv[1:] == ["schema"]:
        con = connect()
        con.cursor().execute(SCHEMA)
        con.commit()
    elif len(sys.argv) == 3 and sys.argv[1] == "load":
        load(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "hand":
        hand(sys.argv[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
