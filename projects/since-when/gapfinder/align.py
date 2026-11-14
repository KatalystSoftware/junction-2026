"""Align passages across editions, compute coverage per year, and build the finding table.

For one topic and one date, every passage of each edition is compared with every passage of
the same topic in the other two editions, exactly, with VEC_DISTANCE_COSINE inside MariaDB.
A topic has a few hundred passages at most, so no vector index is needed, and the chunk table
answers FOR SYSTEM_TIME AS OF any date.

    covered   nearest passage in the other edition within COVERED
    partly    within PARTLY
    missing   farther: a coverage gap
"""

import json
import re
import statistics
import sys
import time
from datetime import date, datetime, timedelta

from .db import LANGS, connect
from .wikitext import cited, paragraph_cited
from differences.lexicon import find_concepts, sentence_at

YEARS = range(2005, 2027)
# Cosine distance thresholds for bge-m3 across languages, calibrated on leads of the same topic
# against the nearest lead of another topic.
COVERED, PARTLY = 0.30, 0.38
# How checkable a finding is, most first. A contradiction or a figure is settled by the cited
# source; a framing difference is often settled consensus, so it ranks last. A finding whose
# fuller side has no reference is demoted. The score is readers × weight; coverage is shown, not
# scored, because a shorter article is not a defect.
TYPE_WEIGHT = {"contradiction": 1.0, "numbers": 1.0, "missing_fact": 0.7, "coverage": 0.5, "framing": 0.25}
UNCITED = 0.6
LIST_COVERAGE = 0.2
# A section is a coverage gap only when its passages that count as missing average more than this
# distance. Passage matching alone flagged sections the other edition covers under another title
# (fi "Kunnianosoitukset", en "Honours"); on 22 hand-labelled top findings this rule kept 5 of 6
# real gaps and dropped 9 of 12 covered ones. A small sample: recheck on more labels.
MISSING_SECTION = 0.42


_SENTENCE_END = re.compile(r"[.!?](?=\s+[\"“(]?[A-ZÅÄÖÜ0-9])")


def first_sentence(text, low=40, high=400):
    """The passage's first sentence, an exact prefix of it: cut at the first sentence end after
    `low` characters (so abbreviations such as \"s. 12\" rarely cut it short), else at the last
    one within `high`, else at a word boundary."""
    para = text.split("\n")[0]
    ends = [m.end() for m in _SENTENCE_END.finditer(para)]
    end = next((e for e in ends if e >= low), None)
    if end is None and len(para) <= high:
        return para
    if end is None or end > high:
        within = [e for e in ends if e <= high]
        end = within[-1] if within else para.rfind(" ", 0, high)
    return para[:end] if end > 0 else para[:high]


def weight(type_, cited):
    return TYPE_WEIGHT[type_] * (1 if cited or type_ == "framing" else UNCITED)


QID = re.compile(r"^Q[0-9]+$")
DAY = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def lit(value):
    """A value as an SQL literal. Queries are run exactly as shown in the SQL panel, so values
    are written into the text; every caller validates them first."""
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"


def as_of_sql(as_of):
    """`as_of` (YYYY-MM-DD or None for now) as the FOR SYSTEM_TIME clause's expression."""
    return "NOW(6)" if as_of is None else f"TIMESTAMP {lit(as_of + ' 00:00:00')}"


class Run:
    """Runs queries and keeps their text, time and row count for the API's sql array."""

    def __init__(self, con=None):
        self.con = con or connect(autocommit=True)
        self.cur = self.con.cursor()
        self.log = []

    def __call__(self, label, sql, dicts=True):
        t0 = time.perf_counter()
        self.cur.execute(sql)
        rows = self.cur.fetchall() if self.cur.description else []
        if dicts and self.cur.description:
            names = [d[0] for d in self.cur.description]
            rows = [dict(zip(names, r)) for r in rows]
        ms = round((time.perf_counter() - t0) * 1000, 2)
        self.log.append({"label": label, "query": sql.strip(), "ms": ms, "rows": len(rows)})
        return rows


def nearest_sql(qid, as_of=None, a=None, b=None):
    """For every passage of a topic at a date, its nearest passage in each other edition."""
    pair = f"\n  AND x.lang = {lit(a)} AND y.lang = {lit(b)}" if a else ""
    return f"""
WITH c AS (
  SELECT c.id, c.lang, c.ord, c.section, c.chunk_no, c.rev_id, p.embedding
  FROM chunk FOR SYSTEM_TIME AS OF {as_of_sql(as_of)} AS c
  JOIN passage AS p ON p.sha = c.sha
  WHERE c.wikidata_id = {lit(qid)} AND p.embedding IS NOT NULL
), d AS (
  SELECT x.id, x.lang, x.ord, y.lang AS other_lang, y.id AS other_id,
         VEC_DISTANCE_COSINE(x.embedding, y.embedding) AS distance,
         ROW_NUMBER() OVER (PARTITION BY x.id, y.lang
                            ORDER BY VEC_DISTANCE_COSINE(x.embedding, y.embedding)) AS rn
  FROM c AS x JOIN c AS y ON y.lang <> x.lang{pair}
)
SELECT id, lang, ord, other_lang, other_id, distance,
       CASE WHEN distance <= {COVERED} THEN 'covered'
            WHEN distance <= {PARTLY} THEN 'partly' ELSE 'missing' END AS status
FROM d WHERE rn = 1
ORDER BY lang, other_lang, ord"""


def missing_vectors_sql(qid, as_of=None):
    return f"""
SELECT COUNT(*) AS n FROM chunk FOR SYSTEM_TIME AS OF {as_of_sql(as_of)} AS c
JOIN passage AS p ON p.sha = c.sha
WHERE c.wikidata_id = {lit(qid)} AND p.embedding IS NULL"""


def coverage_rows(rows):
    """{(lang, rich_lang): (passages of rich_lang, covered, coverage)} from nearest rows.
    Coverage counts a covered passage as 1 and a partly covered one as 0.5."""
    out = {}
    for r in rows:
        key = (r["other_lang"], r["lang"])
        n, full, part = out.get(key, (0, 0, 0))
        out[key] = (n + 1, full + (r["status"] == "covered"), part + (r["status"] == "partly"))
    return {k: (n, full, (full + 0.5 * part) / n) for k, (n, full, part) in out.items()}


def align_topic(run, qid, as_of=None):
    """Coverage rows for one topic and date, or None when some passage has no vector yet."""
    if run("Passages without a vector", missing_vectors_sql(qid, as_of))[0]["n"]:
        return None
    rows = run("Nearest passage in each other edition", nearest_sql(qid, as_of))
    return rows, coverage_rows(rows)


def run(only=None, history=True):
    """Fill the coverage table for every topic whose passages are embedded, then rebuild the
    findings. Years already in the table are skipped; the current text is always recomputed."""
    r = Run()
    topics = [
        t["wikidata_id"]
        for t in r("topics", "SELECT wikidata_id FROM topic ORDER BY priority")
        if not only or t["wikidata_id"] in only
    ]
    done = {
        (x["wikidata_id"], str(x["as_of"]))
        for x in r("done", "SELECT DISTINCT wikidata_id, as_of FROM coverage WHERE NOT is_current")
    }
    today = date.today().isoformat()
    started, n_topics, n_dates = time.monotonic(), 0, 0
    for qid in topics:
        dates = [None] + ([f"{y}-01-01" for y in YEARS] if history else [])
        aligned = False
        for as_of in dates:
            if as_of and (qid, as_of) in done:
                continue
            r.log.clear()
            res = align_topic(r, qid, as_of)
            if res is None:
                continue
            _, cov = res
            r.cur.execute(
                f"DELETE FROM coverage WHERE wikidata_id = {lit(qid)} AND "
                + ("is_current" if as_of is None else f"as_of = {lit(as_of)}")
            )
            if cov:
                r.cur.executemany(
                    "INSERT INTO coverage VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (qid, lang, rich, as_of or today, as_of is None, n, full, c)
                        for (lang, rich), (n, full, c) in cov.items()
                    ],
                )
            n_dates += 1
            aligned = True
        n_topics += aligned
        if n_topics and n_topics % 100 == 0 and aligned:
            print(f"aligned {n_topics} topics, {n_dates} dates, {time.monotonic() - started:.0f} s", flush=True)
    print(f"aligned {n_topics} topics, {n_dates} dates, {time.monotonic() - started:.0f} s", flush=True)
    build_findings(only)
    if not only:
        refresh_now()


def refresh_now():
    """Copy the current embedded passages into chunk_now, the table with the vector index."""
    con = connect()
    cur = con.cursor()
    # Without this, INSERT … SELECT share-locks passage rows the embedding workers hold.
    cur.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
    cur.execute("DELETE FROM chunk_now")
    cur.execute("""INSERT INTO chunk_now (id, wikidata_id, lang, section, embedding)
                   SELECT c.id, c.wikidata_id, c.lang, c.section, p.embedding
                   FROM chunk AS c JOIN passage AS p ON p.sha = c.sha
                   WHERE p.embedding IS NOT NULL""")
    con.commit()
    cur.execute("SELECT COUNT(*) FROM chunk_now")
    print(f"chunk_now: {cur.fetchone()[0]} passages", flush=True)


# --- Findings ---------------------------------------------------------------------------------


def rich_lang_sql(qid=None):
    """The richest other edition (most passages) for each topic and edition, today."""
    where = f"WHERE a.wikidata_id = {lit(qid)}" if qid else ""
    return f"""
SELECT a.wikidata_id, a.lang,
       (SELECT b.lang FROM article AS b
        WHERE b.wikidata_id = a.wikidata_id AND b.lang <> a.lang
        ORDER BY b.passages DESC, b.lang LIMIT 1) AS rich_lang
FROM article AS a {where}"""


# --- Dating -----------------------------------------------------------------------------------
# History keeps one revision per edition per 1 January, the one current then, with its edit time.
# A finding first seen on compared date t and not on the compared date p before it began with an
# edit after p and no later than e, the edit time of the later of the two revisions current at t:
# the pair has not changed since e. The diff from the revision current at p to the one current at
# t therefore contains the change. Without an earlier compared date, e only says since when the
# finding is known to hold. The same goes for closing. The current text counts as date today.


def _revisions(r, qid):
    """{lang: [{rev_id, row_start, row_end}]}: every loaded revision of the topic's articles."""
    revs = {}
    for v in r(
        "revisions",
        f"""SELECT lang, rev_id, row_start, row_end FROM article FOR SYSTEM_TIME ALL
                                WHERE wikidata_id = {lit(qid)} ORDER BY lang, row_start""",
    ):
        revs.setdefault(v["lang"], []).append(v)
    return revs


def _at(label):
    """The moment a compared date stands for: midnight of a 1 January, or now for today."""
    return datetime.now() if label >= date.today() else datetime.combine(label, datetime.min.time())


def _pair_time(revs, langs, label):
    """Edit time of the later of the revisions of `langs` current at `label`."""
    at = _at(label)
    times = [v["row_start"] for lang in langs for v in revs.get(lang, []) if v["row_start"] <= at < v["row_end"]]
    return max(times, default=at)


# Where every revision is loaded (full_history), the edit itself can be found. A finding's
# evidence is a test on the texts: the word is in the first sentence, the quoted sentence is in
# the article, the section exists. The test is run at every edit time of the pair, and the
# period of edits over which it holds, around the compared date that showed the finding, gives
# the opening and the closing edit. When the test disagrees with what the compared dates showed
# (it fails on the date the finding was seen, or holds on the date before), the dates above stay.
# A finding whose evidence is still in the texts stays open on a later date that did not show it.

BLIP = timedelta(days=1)  # a text that lasts less is taken for vandalism and its revert


class _Texts:
    """Every passage version of a topic's articles: which texts each edition had, and when.
    since: {lang: the time from which every revision is loaded}."""

    def __init__(self, r, qid, since):
        self.since, self.rows, self.memo, self.concepts = since, {}, {}, {}
        for c in r(
            "passage versions",
            f"""
                SELECT lang, section, chunk_no, sha, row_start, row_end FROM chunk FOR SYSTEM_TIME ALL
                WHERE wikidata_id = {lit(qid)}""",
        ):
            self.rows.setdefault(c["lang"], []).append(c)
        self.text = {
            p["sha"]: p["text"]
            for p in r(
                "passage texts",
                f"""
            SELECT sha, text FROM passage
            WHERE sha IN (SELECT sha FROM chunk FOR SYSTEM_TIME ALL WHERE wikidata_id = {lit(qid)})""",
            )
        }

    def when(self, lang, name, test):
        """A function of a time: whether some passage of `lang` current then passes
        test(section, chunk_no, text). `name` identifies the test."""
        if (lang, name) not in self.memo:
            spans = []
            for s, e in sorted(
                (c["row_start"], c["row_end"])
                for c in self.rows.get(lang, [])
                if test(c["section"], c["chunk_no"], self.text[c["sha"]])
            ):
                if spans and s <= spans[-1][1]:
                    spans[-1][1] = max(spans[-1][1], e)
                else:
                    spans.append([s, e])
            self.memo[lang, name] = spans
        spans = self.memo[lang, name]
        return lambda t: any(s <= t < e for s, e in spans)

    def found(self, lang, text):
        if (lang, text) not in self.concepts:
            self.concepts[lang, text] = find_concepts(text, lang)
        return self.concepts[lang, text]


def _spans(revs, langs, holds, since):
    """([start, end] periods over which holds(t) was true, the time they are known from, whether
    that is the time both articles exist from). t runs over the edit times of both editions; end
    None: it still holds. A break shorter than BLIP does not end a period."""
    if not holds or not all(revs.get(lang) and lang in since for lang in langs):
        return [], None, True
    born = max(revs[lang][0]["row_start"] for lang in langs)
    floor = max([born] + [since[lang] for lang in langs])
    out = []
    for t in sorted({floor} | {v["row_start"] for lang in langs for v in revs[lang] if v["row_start"] > floor}):
        if not holds(t):
            if out and out[-1][1] is None:
                out[-1][1] = t
        elif out and out[-1][1] is not None and t - out[-1][1] < BLIP:
            out[-1][1] = None
        elif not out or out[-1][1] is not None:
            out.append([t, None])
    return out, floor, floor == born


def _top(section):
    return (section or "").split(" › ")[0]


def _evidence(f, texts):
    """holds(t) for a difference finding: whether its evidence was in the texts at time t.
    None when the finding gives nothing to test."""
    quotes = [(lang, q) for lang, q in ((f["lang"], f["quote"]), (f["other_lang"], f["other_quote"])) if q]
    term = f["terms"][0] if f["type"] == "framing" and len(f["terms"]) == 1 else None
    user = next(
        (
            (lang, family)
            for lang, q in quotes
            for family, concepts in find_concepts(q, lang).items()
            if term in concepts
        ),
        None,
    )
    if user:  # a loaded word: the test the word list ran, on the first sentences or on the sections
        (user, family), first = user, "first sentence" in f["summary"]
        rest = f["other_lang"] if user == f["lang"] else f["lang"]
        tops = {f["lang"]: _top(f["section"]), f["other_lang"]: _top(f["other_section"])}

        def has(lang, word, top):  # word None: any word of the family
            def test(section, chunk_no, text):
                if first and (section or chunk_no) or not first and _top(section) != top:
                    return False
                concepts = texts.found(lang, sentence_at(text, 0) if first else text).get(family, {})
                return word in concepts if word else bool(concepts)

            return texts.when(lang, (family, word, first, top), test)

        uses, some = has(user, term, tops[user]), has(rest, None, tops[rest])
        same = has(rest, term, tops[rest] if first else "")  # the other first sentence, or lead, uses it too
        return lambda t: uses(t) and some(t) and not same(t)
    if f["type"] == "missing_fact":  # held from the day the fact's sentence entered the edition that has it
        quotes = quotes[-1:]  # the other edition's sentence; a row that names no lacking side quotes its own
    tests = [texts.when(lang, q, lambda section, chunk_no, text, q=q: q in text) for lang, q in quotes]
    return (lambda t: all(test(t) for test in tests)) if tests else None


def _dated(f, revs, checked, seen, texts=None, holds=None):
    """Finding f once per period it held: each run of compared dates (`checked`) on which it was
    `seen`, with opened_at, opened_after, closed_at and closed_after as datetimes or dates.
    holds(t): whether the finding's evidence was in the texts at edit time t, when that can be told."""
    langs = (f["lang"], f["other_lang"])
    # Whether any earlier 1 January was compared; if not, opened_at only dates today's revision.
    history = any((label.month, label.day) == (1, 1) for label in checked)
    spans, born, whole = _spans(revs, langs, holds, texts.since) if texts else ([], None, True)

    def span(label):
        t = _at(label)
        return next((s for s in spans if s[0] <= t and (s[1] is None or t < s[1])), None)

    out, first, before, prev, last = [], None, None, None, None
    for label in sorted(checked) + [None]:
        if label is not None and label in seen:
            if first is None:
                first, before = label, prev
            last = label
        elif first is not None and label is not None and span(last) and span(last) == span(label):
            pass  # the evidence is still in the texts: this date's comparison missed it, no edit closed it
        elif first is not None:
            start = _pair_time(revs, langs, first)
            if before is not None and start <= _at(before):  # no edit between: the pipeline changed
                start = _at(before) + timedelta(seconds=1)
            after, known = before, history
            s = span(first)
            # The edit that brought the evidence; a period that held at `born` began at an unknown time,
            # unless the articles began then.
            if s and (before is None or s[0] > _at(before)) and (whole or s[0] > born):
                start, known = s[0], True
                if start > born:  # the day before it; the first text of the pair has no "before"
                    after = max(start.date() - timedelta(days=1), before or date.min)
            stop, till = None, None
            if label is not None:
                stop, till = max(_pair_time(revs, langs, label), _at(last) + timedelta(seconds=1)), last
                s = span(last)
                if s and s[1] and s[1] <= _at(label):  # the edit that took the evidence away
                    stop, till = s[1], max(s[1].date() - timedelta(days=1), last)
            out.append(dict(f, opened_at=start, opened_after=after, closed_at=stop, closed_after=till, history=known))
            first = None
        prev = label
    return out


def _renamed(old, new):
    """Whether section title `new` looks like `old` renamed: they share half the words of the longer."""
    a, b = (set(re.findall(r"\w+", t.lower())) for t in (old, new))
    return bool(a and b) and len(a & b) * 2 >= max(len(a), len(b))


def _coverage_findings(r, qid, rich, revs, history, texts=None):
    """Coverage findings for one topic: one per top-level section of the richer edition that has
    no close counterpart, once per period it held. A section renamed between two dates stays the
    same finding when most of its passages are unchanged. revs: {lang: current rev_id}."""
    dates = [
        x["as_of"]
        for x in r(
            "dates",
            f"""
        SELECT as_of FROM coverage WHERE wikidata_id = {lit(qid)} AND NOT is_current
        GROUP BY as_of ORDER BY as_of""",
        )
    ]
    by_key, seen_on, shas, canon = {}, {}, {}, {}
    checked, prev_seen = [], set()
    timeline = [(d.isoformat(), d) for d in dates] + [(None, date.today())]
    current_ok = False  # today's text is aligned (all its passages have vectors)
    for as_of, label in timeline:
        res = align_topic(r, qid, as_of)
        if res is None:
            continue
        current_ok = current_ok or as_of is None
        checked.append(label)
        rows, _ = res
        missing = [
            x
            for x in rows  # x is a passage of the richer edition, x["lang"]
            if rich.get(x["other_lang"]) == x["lang"] and x["status"] == "missing"
        ]
        chunks = (
            {
                c["id"]: c
                for c in r(
                    "passages",
                    f"""
            SELECT c.id, c.lang, c.section, c.ord, c.rev_id, c.sha, c.cites, p.text, p.words
            FROM chunk FOR SYSTEM_TIME AS OF {as_of_sql(as_of)} AS c JOIN passage p ON p.sha = c.sha
            WHERE c.wikidata_id = {lit(qid)}""",
                )
            }
            if missing
            else {}
        )
        totals, groups = {}, {}
        for c in chunks.values():
            totals[c["lang"]] = totals.get(c["lang"], 0) + c["words"]
        for x in missing:
            top = chunks[x["id"]]["section"].split(" › ")[0]
            groups.setdefault((x["other_lang"], x["lang"], top), []).append(x)
        seen = {}  # key -> shas of its passages on this date
        for (lang, other, top), xs in groups.items():
            dist = statistics.mean(float(x["distance"]) for x in xs)
            if dist <= MISSING_SECTION:
                continue
            raw = f"{qid}:{lang}:{other}:coverage:{top}"
            here = {chunks[x["id"]]["sha"] for x in xs}
            key = canon.get(raw)
            if key is None:  # a renamed section: the finding last seen whose passages it mostly keeps
                gone = [
                    k
                    for k in prev_seen
                    if k not in seen
                    and k.split(":")[1:3] == [lang, other]
                    and (len(shas[k] & here) * 2 >= min(len(shas[k]), len(here)) or _renamed(by_key[k]["section"], top))
                ]
                key = canon[raw] = gone[0] if gone else raw
            seen[key] = here
            f = by_key.setdefault(
                key,
                {
                    "key": key,
                    "wikidata_id": qid,
                    "lang": lang,
                    "other_lang": other,
                    "type": "coverage",
                    "words": 0,
                    "passages": set(),
                    "quote": None,
                    "other_quote": None,
                    "other_citation": None,
                    "distance": None,
                },
            )
            f["section"] = top
            f.setdefault("titles", set()).add(top)
            if as_of is not None:
                continue
            near = {}  # the sections of `lang` its passages are nearest to, by words
            for x in xs:
                c = chunks[x["id"]]
                f["words"] += c["words"]
                f["passages"].add(c["ord"])
                n = chunks[x["other_id"]]["section"].split(" › ")[0]
                near[n] = near.get(n, 0) + c["words"]
            f["share"] = f["words"] / max(totals.get(other, 0), 1)
            f["distance"] = dist
            f["near_section"] = max(near, key=near.get)
            f["rev_id"], f["other_rev_id"] = revs.get(lang), revs.get(other)
            c = chunks[xs[0]["id"]]
            cites = json.loads(c["cites"])
            f["other_quote"] = first_sentence(c["text"])
            f["other_citation"] = cited(c["text"], cites, f["other_quote"])
            f["other_paragraph_citation"] = paragraph_cited(c["text"], cites, f["other_quote"])
        for key, here in seen.items():
            seen_on.setdefault(key, set()).add(label)
            shas[key] = here
        prev_seen = set(seen)
    out = []
    for key, f in by_key.items():
        if max(seen_on[key]) == checked[-1] and not f["passages"] and current_ok:
            continue
        section = f["section"] or "the lead"
        near = f.pop("near_section", None)
        near = "the lead" if near == "" else f'"{near}"'
        summary = (
            f'The {f["other_lang"]} article\'s section "{section}" ({len(f["passages"])} passages, '
            f"{f['words']} words) has no close counterpart in the {f['lang']} article; its passages "
            f"are nearest to {near} (cosine distance {f['distance']:.2f})."
            if f["passages"]
            else f'A section "{section}" of the {f["other_lang"]} article '
            f"had no close counterpart in the {f['lang']} article."
        )
        # Sourced when the quoted sentence, or the end of its paragraph, carries a reference.
        f.update(
            summary=summary,
            other_section=None,
            source="align",
            terms=[],
            model=None,
            citation=None,
            weight=weight("coverage", bool(f["other_citation"] or f.get("other_paragraph_citation"))),
        )
        # Held while the richer edition has the section, under any title it was seen with.
        titles = f.pop("titles")
        holds = (
            texts
            and "" not in titles
            and texts.when(
                f["other_lang"], tuple(sorted(titles)), lambda section, chunk_no, text: _top(section) in titles
            )
        )
        out += _dated(f, history, checked, seen_on[key], texts, holds)
    return out


def _uses(d, term):
    """The edition whose quote carries the loaded word `term`, or None (model terms are free text)."""
    for s in ("a", "b"):
        if any(term in concepts for concepts in find_concepts(d["quote_" + s] or "", d[s + "_lang"]).values()):
            return d[s + "_lang"]
    return None


def _difference_findings(r, qid, size, history, texts=None):
    """Classifier differences as findings, once per period each held. A missing fact belongs to
    the edition that lacks it; the other types to the poorer edition of the pair, as coverage
    does, with no verdict. A framing finding is one loaded word in the edition that uses it, so
    "Swedish says fascist" and "English says fascist" are two findings with their own dates."""
    # Word-list rows first, so on a date both classifiers saw, the model's evidence is kept.
    rows = r(
        "differences", f"SELECT * FROM difference WHERE wikidata_id = {lit(qid)} ORDER BY as_of, source <> 'lexicon'"
    )
    # History is compared on 1 January only, so a row of any other date classified the current
    # text, which has not changed since the load. Rows the model wrote on 13 Nov and the word list
    # on 14 Nov are the same comparison; as two dates, 13 Nov opened the Lapua framing findings.
    today = date.today()
    for d in rows:
        if (d["as_of"].month, d["as_of"].day) != (1, 1):
            d["as_of"] = today
    rows.sort(key=lambda d: (d["as_of"], d["source"] != "lexicon"))
    # Dates each classifier compared this topic on. A finding the word list never produced is
    # dated by the model's dates only, so a date only the word list looked at cannot open or close it.
    # A date with no difference at all for the topic is not known to have been compared.
    by_model = {d["as_of"] for d in rows if d["source"] != "lexicon"}
    by_list = {d["as_of"] for d in rows}
    # One framing finding per word-list word, so the timeline shows when each word came and went.
    # A model row stays one finding: its one summary covers all its terms, and a card per term
    # repeated that summary.
    expanded = []
    for d in rows:
        terms = json.loads(d["terms"])
        if d["type"] == "framing" and len(terms) > 1 and d["source"] == "lexicon":
            expanded += [dict(d, terms=json.dumps([t])) for t in terms]
        else:
            expanded.append(d)
    leads = {}

    def lead_uses(lang, as_of, term):
        """Whether `lang`'s lead on `as_of` has the loaded word `term` anywhere."""
        if (lang, as_of) not in leads:
            t = as_of_sql(None if as_of >= date.today() else as_of.isoformat())
            leads[(lang, as_of)] = " ".join(
                x["text"]
                for x in r(
                    "lead",
                    f"""
                SELECT p.text FROM chunk FOR SYSTEM_TIME AS OF {t} AS c JOIN passage AS p ON p.sha = c.sha
                WHERE c.wikidata_id = {lit(qid)} AND c.lang = {lit(lang)} AND c.section = ''""",
                )
            )
        return any(term in c for c in find_concepts(leads[(lang, as_of)], lang).values())

    by_key, seen_on, listed = {}, {}, set()
    for d in expanded:
        terms = json.loads(d["terms"])
        if d["type"] == "framing" and len(terms) == 1 and "first sentence" not in d["summary"]:
            # "The other passage uses other words" is false for the article when the other
            # edition's lead uses the word (the Finnish lead says "vallankaappausyritys").
            user = _uses(d, terms[0])
            other = d["b_lang"] if user == d["a_lang"] else d["a_lang"] if user else None
            if other and lead_uses(other, d["as_of"], terms[0]):
                continue
        poorer = d["a_lang"] if size.get(d["a_lang"], 0) < size.get(d["b_lang"], 0) else d["b_lang"]
        lang = d["missing_in"] or poorer
        a_side = lang == d["a_lang"]
        s, o = ("a", "b") if a_side else ("b", "a")
        terms = json.loads(d["terms"])
        quote, other_quote = d["quote_" + s] or None, d["quote_" + o] or None
        section = d[s + "_section"]
        ident = ",".join(sorted(terms)) or (quote or other_quote or "")[:80]
        if d["type"] == "framing" and len(terms) == 1:
            ident = f"{_uses(d, terms[0]) or '?'}={ident}"
        key = f"{qid}:{lang}:{d[o + '_lang']}:{d['type']}:{section.split(' › ')[0]}:{ident}"
        cite, other_cite = d[s + "_citation"], d[o + "_citation"]
        par, other_par = d[s + "_par_citation"], d[o + "_par_citation"]
        # Missing fact: the side that has it must be cited. Others: either side.
        cited = bool(other_cite) if d["type"] == "missing_fact" else bool(cite or other_cite)
        by_key[key] = {  # the latest sighting's evidence
            "key": key,
            "wikidata_id": qid,
            "lang": lang,
            "other_lang": d[o + "_lang"],
            "type": d["type"],
            "section": section,
            "other_section": d[o + "_section"],
            "quote": quote,
            "other_quote": other_quote,
            "summary": d["summary"],
            "terms": terms,
            "distance": d["distance"],
            "share": None,
            "weight": weight(d["type"], cited),
            "rev_id": d[s + "_rev"],
            "other_rev_id": d[o + "_rev"],
            "citation": cite,
            "other_citation": other_cite,
            "paragraph_citation": par,
            "other_paragraph_citation": other_par,
            "source": d["source"],
            "model": d["model"],
        }
        seen_on.setdefault(key, set()).add(d["as_of"])
        if d["source"] == "lexicon":
            listed.add(key)
    out = []
    for key, f in by_key.items():
        out += _dated(
            f, history, by_list if key in listed else by_model, seen_on[key], texts, texts and _evidence(f, texts)
        )
    return out


FINDING_COLS = (
    "id",
    "wikidata_id",
    "lang",
    "other_lang",
    "type",
    "section",
    "other_section",
    "quote",
    "other_quote",
    "summary",
    "terms",
    "distance",
    "share",
    "weight",
    "rev_id",
    "other_rev_id",
    "citation",
    "other_citation",
    "paragraph_citation",
    "other_paragraph_citation",
    "source",
    "model",
    "status",
    "status_url",
    "status_at",
    "opened_at",
    "opened_after",
    "closed_at",
    "closed_after",
    "history",
    "key",
)
FAR = datetime(2106, 1, 1)


def _write_finding(cur, f):
    """Insert one period of a finding: open from the edit that opened it, then the editor's outcome
    from the moment it was set, until the edit after which the alignment no longer sees the gap."""
    cols = ", ".join(f"`{c}`" for c in FINDING_COLS)
    marks = ", ".join("?" * len(FINDING_COLS))
    start, end = f["opened_at"], f["closed_at"]
    f = dict(f, opened_at=start.date(), closed_at=end.date() if end else None)
    plain = dict(f, status="open", status_url=None, status_at=None)
    periods = [(plain, start, end)]
    if f.get("status", "open") != "open" and f.get("status_at") and (not end or f["status_at"] < end):
        at = max(f["status_at"], start + timedelta(microseconds=1))
        periods = [(plain, start, at), (f, at, end)]
    for g, s, e in periods:
        vals = [g.get(c) for c in FINDING_COLS]
        vals[FINDING_COLS.index("terms")] = json.dumps(g.get("terms") or [], ensure_ascii=False)
        if e:
            cur.execute(f"INSERT INTO finding ({cols}, row_start, row_end) VALUES ({marks}, ?, ?)", vals + [s, e])
        else:
            cur.execute(f"INSERT INTO finding ({cols}, row_start) VALUES ({marks}, ?)", vals + [s])


def build_findings(only=None):
    """Rebuild the finding table. Each period of a finding is a history row from the edit that
    opened it to the edit that closed it (system_versioning_insert_history), so finding FOR
    SYSTEM_TIME AS OF a date lists the gaps open then. Editor outcomes are carried over by key,
    with the time they were set."""
    r = Run()
    rich, revs = {}, {}
    for x in r("rich", rich_lang_sql()):
        rich.setdefault(x["wikidata_id"], {})[x["lang"]] = x["rich_lang"]
    size = {}
    for x in r("revs", "SELECT wikidata_id, lang, rev_id, passages FROM article"):
        revs.setdefault(x["wikidata_id"], {})[x["lang"]] = x["rev_id"]
        size.setdefault(x["wikidata_id"], {})[x["lang"]] = x["passages"]
    topics = [
        t["wikidata_id"]
        for t in r("t", "SELECT DISTINCT wikidata_id FROM coverage")
        if not only or t["wikidata_id"] in only
    ]
    kinds = {x["wikidata_id"]: x["kind"] for x in r("k", "SELECT wikidata_id, kind FROM topic WHERE kind IS NOT NULL")}
    outcome = {
        x["key"]: x for x in r("s", "SELECT `key`, status, status_url, status_at FROM finding WHERE status <> 'open'")
    }
    ids = {x["key"]: x["id"] for x in r("i", "SELECT `key`, id FROM finding FOR SYSTEM_TIME ALL GROUP BY `key`, id")}
    next_id = max(ids.values(), default=0) + 1
    full = {}  # {topic: {lang: the time from which every revision is loaded}}
    for x in r("full", "SELECT wikidata_id, lang, since FROM full_history"):
        full.setdefault(x["wikidata_id"], {})[x["lang"]] = x["since"]
    rows = []
    for qid in topics:
        r.log.clear()
        history = _revisions(r, qid)
        texts = _Texts(r, qid, full[qid]) if qid in full else None
        for f in _coverage_findings(
            r, qid, rich.get(qid, {}), revs.get(qid, {}), history, texts
        ) + _difference_findings(r, qid, size.get(qid, {}), history, texts):
            if f["key"] not in ids:
                ids[f["key"]] = next_id
                next_id += 1
            f["id"] = ids[f["key"]]
            if f["type"] == "coverage" and qid in kinds:
                f["weight"] *= LIST_COVERAGE  # lists and offices differ in structure by design
            f.update(outcome.get(f["key"], {"status": "open", "status_url": None, "status_at": None}))
            rows.append(f)
    # Rebuild: purge the table and its history (DELETE HISTORY cannot filter by topic), then write
    # the rebuilt topics and every other topic's rows back with their periods.
    con = r.con
    con.autocommit = False
    cur = con.cursor()
    cur.execute("SET system_versioning_insert_history = 1")
    keep = (
        []
        if not only
        else [
            x
            for x in r("keep", "SELECT *, row_start, row_end FROM finding FOR SYSTEM_TIME ALL")
            if x["wikidata_id"] not in only
        ]
    )
    cur.execute("DELETE FROM finding")
    cur.execute("DELETE HISTORY FROM finding")
    cols = ", ".join(f"`{c}`" for c in FINDING_COLS)
    marks = ", ".join("?" * len(FINDING_COLS))
    for x in keep:
        vals = [x[c] for c in FINDING_COLS]
        if x["row_end"] >= FAR:
            cur.execute(f"INSERT INTO finding ({cols}, row_start) VALUES ({marks}, ?)", vals + [x["row_start"]])
        else:
            cur.execute(
                f"INSERT INTO finding ({cols}, row_start, row_end) VALUES ({marks}, ?, ?)",
                vals + [x["row_start"], x["row_end"]],
            )
    for f in rows:
        _write_finding(cur, f)
    con.commit()
    print(f"findings: {len(rows)} rebuilt, {len(keep)} rows kept", flush=True)


# --- Classifier input and output --------------------------------------------------------------


def pairs(only=None, history=False, out=sys.stdout):
    """Matched passage pairs for the classifier, as JSON lines: the three leads of each topic
    against each other, and every partly covered passage with its nearest counterpart, today
    and, with history, on each 1 January."""
    r = Run()
    topics = [
        t
        for t in r("topics", "SELECT wikidata_id, title_fi, title_sv, title_en FROM topic ORDER BY priority")
        if not only or t["wikidata_id"] in only
    ]
    n = 0
    for t in topics:
        for as_of in [None] + ([f"{y}-01-01" for y in YEARS] if history else []):
            n += _pairs_at(r, t, as_of, out)
    print(f"{n} pairs", file=sys.stderr)


def _pairs_at(r, t, as_of, out):
    qid = t["wikidata_id"]
    label = as_of or date.today().isoformat()
    n = 0
    res = align_topic(r, qid, as_of)
    if res is None:
        return 0
    rows, _ = res
    chunks = {
        c["id"]: c
        for c in r(
            "chunks",
            f"""
        SELECT c.id, c.lang, c.ord, c.section, c.chunk_no, a.rev_id, p.text
        FROM chunk FOR SYSTEM_TIME AS OF {as_of_sql(as_of)} AS c JOIN passage AS p ON p.sha = c.sha
        JOIN article FOR SYSTEM_TIME AS OF {as_of_sql(as_of)} AS a ON a.lang = c.lang AND a.page_id = c.page_id
        WHERE c.wikidata_id = {lit(qid)}""",
        )
    }
    want = {}
    for x in rows:
        a, b = chunks[x["id"]], chunks[x["other_id"]]
        lead = a["ord"] == 0 and b["ord"] == 0
        if lead or x["status"] == "partly":
            first, second = sorted([a, b], key=lambda c: LANGS.index(c["lang"]))
            want[(first["id"], second["id"])] = (first, second, x["distance"])
    for first, second, dist in want.values():
        side = lambda c: {
            "chunk_id": c["id"],
            "lang": c["lang"],
            "title": t["title_" + c["lang"]],
            "section": c["section"],
            "chunk_no": c["chunk_no"],
            "rev_id": c["rev_id"],
            "text": c["text"],
        }
        pid = f"{qid}:{label}:{first['lang']}:{first['id']}:{second['lang']}:{second['id']}"
        out.write(
            json.dumps(
                {
                    "pair_id": pid,
                    "wikidata_id": qid,
                    "as_of": label,
                    "distance": round(dist, 4),
                    "a": side(first),
                    "b": side(second),
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        n += 1
    return n


def lexicon_rows(path, out=sys.stdout):
    """Word-list framing rows for a pairs file, as findings load reads them. Only rows comparing
    the two leads' first sentences are written: they date when a label appeared on every 1 January,
    where the model has classified only today's text."""
    from differences.lexicon import compare

    n = 0
    for line in open(path, encoding="utf-8"):
        p = json.loads(line)
        for d in compare(p["a"], p["b"]):
            if "first sentence" in d["summary"]:
                out.write(
                    json.dumps(
                        dict(
                            d,
                            pair_id=p["pair_id"],
                            wikidata_id=p["wikidata_id"],
                            as_of=p["as_of"],
                            distance=p["distance"],
                            source="lexicon",
                            model="lexicon",
                        ),
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                n += 1
    print(f"lexicon: {n} rows", file=sys.stderr)


def load_differences(path):
    """Store the classifier's output (differences.jsonl): each quote with the revision it was
    taken from and the reference behind it. A difference whose quote is no longer a verbatim
    substring of its passage is dropped. Then rebuild those topics' findings."""
    con = connect()
    cur = con.cursor()
    today = date.today().isoformat()
    rows, topics, pairs, dropped = [], set(), set(), 0
    for line in open(path, encoding="utf-8"):
        d = json.loads(line)
        qid, as_of, a_lang, a_id, b_lang, b_id = d["pair_id"].split(":")
        pairs.add((d["pair_id"], d.get("source") == "lexicon"))
        topics.add(qid)
        # The word list alone pairs whole passages about different things (the Swedish "fascistiska"
        # sentence with an English one on Stalin's purges); only its lead first sentences, which
        # define the same subject, are kept. Word-list rows tell since when a word has been there;
        # the model's rows of the same pair carry the evidence shown.
        if d.get("source") == "lexicon" and "first sentence" not in (d.get("summary") or ""):
            continue
        if not (d.get("summary") or "").strip():  # a broken model answer: nothing to show
            dropped += 1
            continue
        t = as_of_sql(None if as_of == today else as_of)
        cur.execute(
            f"""SELECT c.id, c.section, a.rev_id, c.cites, p.text
                        FROM chunk FOR SYSTEM_TIME AS OF {t} AS c
                        JOIN article FOR SYSTEM_TIME AS OF {t} AS a ON a.lang = c.lang AND a.page_id = c.page_id
                        JOIN passage AS p ON p.sha = c.sha WHERE c.id IN (?, ?)""",
            (int(a_id), int(b_id)),
        )
        side = {r[0]: r[1:] for r in cur.fetchall()}
        a, b = side.get(int(a_id)), side.get(int(b_id))
        qa, qb = d.get("quote_a") or "", d.get("quote_b") or ""
        if not a or not b or (qa and qa not in a[3]) or (qb and qb not in b[3]):
            dropped += 1
            continue
        rows.append(
            (
                d["pair_id"],
                qid,
                as_of,
                a_lang,
                a[0],
                b_lang,
                b[0],
                d["type"],
                d.get("missing_in"),
                qa,
                qb,
                a[1],
                b[1],
                cited(a[3], json.loads(a[2]), qa),
                cited(b[3], json.loads(b[2]), qb),
                paragraph_cited(a[3], json.loads(a[2]), qa),
                paragraph_cited(b[3], json.loads(b[2]), qb),
                d.get("summary") or "",
                json.dumps(d.get("terms") or [], ensure_ascii=False),
                d.get("distance"),
                d.get("source") or "llm",
                d.get("model"),
            )
        )
    # A pair in this file replaces what the same kind of classifier (word list or model) stored for
    # it before, even when none of its new rows survives the verbatim check.
    if pairs:
        cur.executemany("DELETE FROM difference WHERE pair_id = ? AND (source = 'lexicon') = ?", sorted(pairs))
    if rows:
        cur.executemany(
            "INSERT INTO difference (pair_id, wikidata_id, as_of, a_lang, a_section, b_lang, b_section, "
            "type, missing_in, quote_a, quote_b, a_rev, b_rev, a_citation, b_citation, a_par_citation, "
            "b_par_citation, summary, terms, distance, source, model) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
    con.commit()
    print(
        f"{len(rows)} differences for {len(topics)} topics, {dropped} dropped (no summary, or quote not verbatim)",
        flush=True,
    )
    build_findings(topics)
