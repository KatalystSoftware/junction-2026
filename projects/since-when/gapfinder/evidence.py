"""Evidence for a claim: the passages of another edition's whole article, as it stood at a date,
that are nearest to the claim by vector distance or that share its names and numbers.

The classifier sees two passages and its rows speak about two articles. Before a row becomes a
finding, its claim is looked up here in every passage of the other edition, in one statement:

    chunk FOR SYSTEM_TIME AS OF <date>      the article split into passages as it stood then
    VEC_DISTANCE_COSINE(sentence, claim)    how near each passage's nearest sentence is to the claim
    passage.text REGEXP <number or name>    which passages carry the claim's figures and names

A claim is one sentence and a passage is ten or twenty, so a passage's own vector says little
about one fact in it: the passage that states a claim ranked 12th to 15th of an article's 59 by
the passage vectors. The search therefore compares the claim with every sentence
(passage_sentence, filled here for the passages it meets) and ranks a passage by its nearest
sentence. The claim's vector (bge-m3, as for the passages) is kept in claim_vector, so the
statement can be run again as it is printed.

    python -m gapfinder.evidence schema
    python -m gapfinder.evidence search CLAIMS.jsonl > EVIDENCE.jsonl

CLAIMS.jsonl has one claim per line: wikidata_id, as_of (YYYY-MM-DD; today's date means now),
target_lang, text (what is embedded: the claim in its own language) and quote (where the names
and numbers are taken from; text when absent). `always` may list chunk ids of the target edition
to return whatever their rank, such as the passage the claim's own passage was paired with.
Each line is written back with an `evidence` object: the statement, its time, how many passages
it searched and the passages it returned.
"""

import functools
import hashlib
import json
import re
import sys
from datetime import date

from differences.claims import sentences
from differences.figures import MONTHS  # month names by number in fi, sv and en, as the start of the word

from .align import Run, as_of_sql, lit
from .db import LANGS

SCHEMA = (
    """
CREATE TABLE IF NOT EXISTS claim_vector (
  sha          BINARY(20) NOT NULL PRIMARY KEY,   -- SHA-1 of the text
  text         TEXT NOT NULL,                     -- the claim, in the language it was written in
  embedding    VECTOR(1024) NOT NULL              -- bge-m3, as passage.embedding
) CHARACTER SET utf8mb4""",
    """
CREATE TABLE IF NOT EXISTS passage_sentence (
  sha          BINARY(20) NOT NULL,               -- the passage: passage.sha, so every version of an
  no           SMALLINT UNSIGNED NOT NULL,        -- article that holds the passage shares its sentences
  text         TEXT NOT NULL,
  embedding    VECTOR(1024) NOT NULL,
  PRIMARY KEY (sha, no)
) CHARACTER SET utf8mb4""",
)
MIN_SENTENCE = 25  # characters; a shorter one joins the sentence before it

NEAREST = 4  # passages returned for their nearest sentence
BY_PASSAGE = 2  # more for the distance of the passage as a whole, which a claim of several facts is nearer to
BY_TERMS = 3  # more for the claim's names and numbers
MAX_TERMS = 12

_MONTH = {name: i for i, names in enumerate(MONTHS) for name in names}
ENGLISH = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)  # the only edition that writes the month first
_MONTH_WORD = "|".join(sorted(_MONTH, key=len, reverse=True))
_SPACE = "[ \u00a0\u202f]"
_SEP = "[ \u00a0\u202f.,]?"  # between thousands: 12 600, 12,600, 12.600, 12600
_NUMBER = re.compile(r"\d{1,3}(?:[ \u00a0\u202f.,]\d{3})+(?!\d)|\d+")
_DAY_MONTH = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\.?{_SPACE}(?:päivänä{_SPACE})?({_MONTH_WORD})", re.IGNORECASE)
_MONTH_DAY = re.compile(rf"\b({'|'.join(ENGLISH)}){_SPACE}(\d{{1,2}})(?:st|nd|rd|th)?\b", re.IGNORECASE)
_NAME = re.compile(r"(?<![.!?:]\s)(?<!^)\b[A-ZÅÄÖÜ][\w-]{3,}")


def terms(quote):
    """Regular expressions for the dates, numbers and names of a quote, at most MAX_TERMS.

    A date matches the same day and month in any of the three languages, a number matches
    whatever separates its thousands, and a name matches by its first letters, so "Kosolan" finds
    "Kosola". A name the other language writes differently ("Helsinkiin", "Helsingfors") is left to
    the vectors. Words that open a sentence are not taken for names.
    """
    out, dated = [], set()
    for m in list(_DAY_MONTH.finditer(quote)) + list(_MONTH_DAY.finditer(quote)):
        day, word = (m[1], m[2]) if m[1].isdigit() else (m[2], m[1])
        month = _MONTH[word.lower()] if word.lower() in _MONTH else ENGLISH.index(word.lower())
        out.append(
            rf"(?<![0-9]){day}(st|nd|rd|th)?\.?{_SPACE}(päivänä{_SPACE})?({'|'.join(MONTHS[month])})"
            rf"|{ENGLISH[month]}{_SPACE}{day}(?![0-9])"
        )
        dated.add(m.span(1) if m[1].isdigit() else m.span(2))
    for m in _NUMBER.finditer(quote):
        digits = re.sub(r"\D", "", m[0])
        if m.span() in dated or len(digits) < 2:
            continue  # the day of a date above; a single digit is in every passage
        head = len(digits) % 3 or 3
        groups = [digits[:head]] + [digits[i : i + 3] for i in range(head, len(digits), 3)]
        out.append("(?<![0-9])" + _SEP.join(groups) + "(?![0-9])")
    for m in _NAME.finditer(quote):
        word = m[0]
        if word.lower()[:6] in {n[:6] for n in _MONTH}:
            continue
        out.append(re.escape(word[: max(4, len(word) - 2)]))
    return list(dict.fromkeys(out))[:MAX_TERMS]


def sha(text):
    return hashlib.sha1(text.encode()).hexdigest()


def search_sql(qid, lang, as_of, claim_sha, patterns=(), always=()):
    """The passages of `lang`'s article on `qid` as of `as_of` (YYYY-MM-DD, None for now) nearest to
    the claim whose vector is stored under `claim_sha`, with those that match most of `patterns`."""
    hits = " + ".join(f"(p.text REGEXP {lit(t)})" for t in patterns) or "0"
    keep = "".join(f" OR id = {int(i)}" for i in always)
    return f"""
WITH sentences AS (
  SELECT c.id, c.ord, c.section, c.chunk_no, c.rev_id, c.sha, s.text AS sentence,
         VEC_DISTANCE_COSINE(s.embedding, q.embedding) AS distance,
         ROW_NUMBER() OVER (PARTITION BY c.id
                            ORDER BY VEC_DISTANCE_COSINE(s.embedding, q.embedding)) AS rn
  FROM chunk FOR SYSTEM_TIME AS OF {as_of_sql(as_of)} AS c
  JOIN passage_sentence AS s ON s.sha = c.sha
  JOIN claim_vector AS q ON q.sha = UNHEX({lit(claim_sha)})
  WHERE c.wikidata_id = {lit(qid)} AND c.lang = {lit(lang)}
), scored AS (
  SELECT n.id, n.ord, n.section, n.chunk_no, n.rev_id, n.sentence, n.distance, p.text,
         VEC_DISTANCE_COSINE(p.embedding, q.embedding) AS passage_distance,
         {hits} AS term_hits
  FROM sentences AS n JOIN passage AS p ON p.sha = n.sha
  JOIN claim_vector AS q ON q.sha = UNHEX({lit(claim_sha)})
  WHERE n.rn = 1
), ranked AS (
  SELECT scored.*, ROW_NUMBER() OVER (ORDER BY distance) AS by_vector,
         ROW_NUMBER() OVER (ORDER BY passage_distance) AS by_passage,
         ROW_NUMBER() OVER (ORDER BY term_hits DESC, distance) AS by_terms,
         COUNT(*) OVER () AS searched
  FROM scored
)
SELECT id, ord, section, chunk_no, rev_id, text, sentence, distance, passage_distance, term_hits,
       by_vector, by_passage, by_terms, searched
FROM ranked
WHERE by_vector <= {NEAREST} OR by_passage <= {BY_PASSAGE} OR (term_hits > 0 AND by_terms <= {BY_TERMS}){keep}
ORDER BY ord"""


def split(text):
    """The sentences of a passage, each at least MIN_SENTENCE characters where the passage allows."""
    out = []
    for start, end in sentences(text):
        piece = text[start:end].strip()
        if out and (len(piece) < MIN_SENTENCE or len(out[-1]) < MIN_SENTENCE):
            out[-1] += " " + piece
        else:
            out.append(piece)
    return out


@functools.cache
def _model():
    """The embedding model, loaded on first use: a run whose vectors are all stored needs none."""
    from .embed import Embedder

    return Embedder()


def embed(texts):
    return _model()(texts)


def store_sentences(con, scopes, embedder=embed):
    """Split and embed the passages of each (topic, edition, as_of) that passage_sentence lacks.
    Returns (passages, sentences) added."""
    cur = con.cursor()
    todo = {}
    for qid, lang, as_of in scopes:
        cur.execute(
            f"""SELECT c.sha, p.text FROM chunk FOR SYSTEM_TIME AS OF {as_of_sql(as_of)} AS c
                        JOIN passage AS p ON p.sha = c.sha
                        WHERE c.wikidata_id = ? AND c.lang = ?
                          AND NOT EXISTS (SELECT 1 FROM passage_sentence AS s WHERE s.sha = c.sha)""",
            (qid, lang),
        )
        todo.update(cur.fetchall())
    rows = [(key, no, text) for key, passage in todo.items() for no, text in enumerate(split(passage))]
    if rows:
        from .embed import vec_bytes

        for i in range(0, len(rows), 256):
            part = rows[i : i + 256]
            vectors = embedder([text for _, _, text in part])
            cur.executemany(
                "INSERT IGNORE INTO passage_sentence (sha, no, text, embedding) VALUES (?, ?, ?, ?)",
                [(key, no, text, vec_bytes(v)) for (key, no, text), v in zip(part, vectors)],
            )
            con.commit()
            print(f"evidence: {min(i + 256, len(rows))} of {len(rows)} sentences embedded", file=sys.stderr, flush=True)
    return len(todo), len(rows)


def store_vectors(con, texts, embedder=embed):
    """Embed the texts that claim_vector does not hold yet. Returns how many were embedded."""
    cur = con.cursor()
    todo = {}
    for text in texts:
        cur.execute("SELECT 1 FROM claim_vector WHERE sha = UNHEX(?)", (sha(text),))
        if not cur.fetchone():
            todo[sha(text)] = text
    if todo:
        from .embed import vec_bytes

        vectors = embedder(list(todo.values()))
        cur.executemany(
            "INSERT IGNORE INTO claim_vector (sha, text, embedding) VALUES (UNHEX(?), ?, ?)",
            [(key, text, vec_bytes(v)) for (key, text), v in zip(todo.items(), vectors)],
        )
        con.commit()
    return len(todo)


def _as_of(claim, today=None):
    """The claim's date as align.as_of_sql takes it: None, now, for a claim dated today."""
    return None if claim["as_of"] == (today or date.today().isoformat()) else claim["as_of"]


def search(r, claim, today=None):
    """The claim with its `evidence`: the statement run, and the passages it returned in article
    order, each with its nearest sentence."""
    if claim["target_lang"] not in LANGS:
        raise ValueError(f"unknown edition {claim['target_lang']!r}")
    as_of = _as_of(claim, today)
    patterns = terms(claim.get("quote") or claim["text"])
    sql = search_sql(
        claim["wikidata_id"], claim["target_lang"], as_of, sha(claim["text"]), patterns, claim.get("always") or ()
    )
    rows = r("evidence", sql)
    return dict(
        claim,
        evidence={
            "sql": sql.strip(),
            "ms": r.log[-1]["ms"],
            "terms": patterns,
            "searched": int(rows[0]["searched"]) if rows else 0,
            "passages": [
                {
                    "chunk_id": x["id"],
                    "ord": x["ord"],
                    "section": x["section"],
                    "chunk_no": x["chunk_no"],
                    "rev_id": x["rev_id"],
                    "text": x["text"],
                    "sentence": x["sentence"],
                    "distance": round(float(x["distance"]), 4),
                    "passage_distance": None
                    if x["passage_distance"] is None
                    else round(float(x["passage_distance"]), 4),
                    "term_hits": int(x["term_hits"]),
                    "by_vector": int(x["by_vector"]),
                    "by_passage": int(x["by_passage"]),
                    "by_terms": int(x["by_terms"]),
                }
                for x in rows
            ],
        },
    )


def main():
    from .db import connect

    if sys.argv[1:] == ["schema"]:
        con = connect()
        for statement in SCHEMA:
            con.cursor().execute(statement)
        con.commit()
        return
    if len(sys.argv) != 3 or sys.argv[1] != "search":
        sys.exit(__doc__)
    claims = [json.loads(line) for line in open(sys.argv[2], encoding="utf-8") if line.strip()]
    con = connect()
    for statement in SCHEMA:
        con.cursor().execute(statement)
    passages, added = store_sentences(con, {(c["wikidata_id"], c["target_lang"], _as_of(c)) for c in claims})
    embedded = store_vectors(con, list(dict.fromkeys(c["text"] for c in claims)))
    r = Run()
    r.log = _Last()
    for claim in claims:
        print(json.dumps(search(r, claim), ensure_ascii=False), flush=True)
    print(
        f"evidence: {len(claims)} claims searched, {embedded} claims embedded, "
        f"{added} sentences of {passages} passages embedded",
        file=sys.stderr,
    )


class _Last(list):
    """Run's log, keeping only the latest statement: a run over thousands of claims needs no more."""

    def append(self, item):
        self[:] = [item]


if __name__ == "__main__":
    main()
