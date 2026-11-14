"""Load topics, article history, passages and page views into MariaDB.

Sources, all under data/mariadb/:
- s/: dataset S, the topics shared by fi, sv and en, and the Finnish category tree;
- m/: dataset M, every Finnish version (wikitext);
- history/: history-{sv,en}.jsonl.gz and pageviews.jsonl from the history fetch, one
  wikitext snapshot per 1 January plus the latest revision.

Every article is loaded as the revisions current on 1 January 2005…2026 plus its latest one, with
Wikipedia's real edit times (system_versioning_insert_history). An article already in the
article table is skipped, so the loader can run again as more history arrives.
"""

import gzip
import hashlib
import json
import pathlib
import re
import time
from datetime import datetime, timezone

from . import wikitext
from .db import connect

DATA = pathlib.Path("data/mariadb")
YEARS = range(2005, 2027)
POLITICS_ROOTS = ["Suomen poliittinen historia", "Suomen sotahistoria", "Suomen ulkopolitiikka", "Suomen presidentit"]
# Demo topics are embedded and aligned first, history included.
DEMO = ["Q1412941"]  # Lapua Movement
LANG_NO = {"fi": 1, "sv": 2, "en": 3}
# Priority classes for embedding, lowest first.
DEMO_CLASS, CURRENT_CLASS, HISTORY_CLASS = 0, 1, 3


_LIST = re.compile(r"^(Lists? of|Timeline of|Index of|Outline of)\b|^Luettelo|^Lista över", re.I)
_OFFICE = re.compile(
    r"^((Prime |Deputy )?Minister (of|for)|(President|Speaker|Governor|Chancellor|Chief|"
    r"Commander|Ombudsman|Mayor|Archbishop)( [A-Z][a-z]+)* of)\b|ministeri$",
    re.I,
)


def kind(title_fi, title_en):
    """list or office, from the titles: such articles differ between editions by design."""
    if _LIST.search(title_en) or _LIST.search(title_fi):
        return "list"
    if _OFFICE.search(title_en) or _OFFICE.search(title_fi):
        return "office"
    return None


def topics(s_dir=DATA / "s"):
    """Fill topic with the 2,919 Wikidata items in all three editions."""
    import duckdb  # only these loaders need it; the app image has none

    db = duckdb.connect()
    db.execute(
        f"CREATE TABLE a AS SELECT lang, page_id, wikidata_id, title, length(text) AS n FROM '{s_dir}/articles-*.parquet'"
    )
    db.execute(f"CREATE TABLE cl AS SELECT * FROM read_csv('{s_dir}/category-links-fi.tsv', delim='\t', header=true)")
    db.execute(
        f"CREATE TABLE ac AS SELECT * FROM read_csv('{s_dir}/article-categories-fi.tsv', delim='\t', header=true)"
    )
    rows = db.execute(
        """
        WITH RECURSIVE cats(name) AS (
            SELECT unnest(?::VARCHAR[])
            UNION SELECT cl.child FROM cl JOIN cats ON cl.parent = cats.name),
        politics AS (SELECT DISTINCT a.wikidata_id FROM ac JOIN cats ON ac.category = cats.name
                     JOIN a ON a.lang = 'fi' AND a.page_id = ac.page_id),
        tri AS (SELECT wikidata_id, sum(n) AS n FROM a WHERE wikidata_id IS NOT NULL
                GROUP BY 1 HAVING count(DISTINCT lang) = 3)
        SELECT tri.wikidata_id,
               any_value(a.title) FILTER (a.lang = 'fi'), any_value(a.title) FILTER (a.lang = 'sv'),
               any_value(a.title) FILTER (a.lang = 'en'),
               CASE WHEN tri.wikidata_id IN (SELECT * FROM politics) THEN 0 ELSE 1 END AS tier, tri.n
        FROM tri JOIN a USING (wikidata_id) GROUP BY tri.wikidata_id, tri.n
        ORDER BY tier, tri.n DESC""",
        [POLITICS_ROOTS],
    ).fetchall()
    out = []
    for rank, (qid, fi, sv, en, tier, _) in enumerate(rows, 1):
        out.append((qid, fi, sv, en, tier, kind(fi, en), 0 if qid in DEMO else rank))
    con = connect()
    cur = con.cursor()
    cur.executemany(
        "REPLACE INTO topic (wikidata_id, title_fi, title_sv, title_en, tier, kind, priority) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        out,
    )
    con.commit()
    pages = db.execute(
        "SELECT lang, page_id, wikidata_id FROM a WHERE wikidata_id IN (SELECT unnest(?::VARCHAR[]))",
        [[r[0] for r in out]],
    ).fetchall()
    print(f"{len(out)} topics, {sum(1 for r in out if r[4] == 0)} in politics and war")
    return pages


def _ts(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def snapshots(revs):
    """revs: [(rev_id, time)] oldest first. Returns the distinct revisions current on each
    1 January of YEARS, then the latest, oldest first."""
    chosen, i = [], -1
    for year in YEARS:
        cut = datetime(year, 1, 1)
        while i + 1 < len(revs) and revs[i + 1][1] < cut:
            i += 1
        if i >= 0 and (not chosen or chosen[-1] != revs[i]):
            chosen.append(revs[i])
    if revs and (not chosen or chosen[-1] != revs[-1]):
        chosen.append(revs[-1])
    return chosen


def _sha(text):
    return hashlib.sha1(text.encode()).digest()


def load_article(cur, lang, page_id, qid, title, versions, priority, split=None):
    """versions: [(rev_id, time, wikitext)] oldest first, one per snapshot; or split, the same
    with each version's passages as a fourth item."""
    split = split or [(rev, t, text, wikitext.passages(text, cites=True, edition=lang)) for rev, t, text in versions]
    base = LANG_NO[lang] * 10**13 + page_id * 10**4
    hist, current, passages = [], [], {}
    # article rows
    a_hist, a_cur = [], []
    for k, (rev, t, text, ps) in enumerate(split):
        refs, quality = wikitext.stats(text)
        row = (lang, page_id, qid, title, rev, len(text.encode()), len(ps), refs, quality, t)
        if k + 1 < len(split):
            a_hist.append(row + (split[k + 1][1],))
        else:
            a_cur.append(row)
    # chunk rows: one per position and run of identical (section, chunk_no, text, citations).
    # A version starts when the passage's text or its references change.
    n = max(len(s[3]) for s in split)
    last = len(split) - 1
    for ord_ in range(n):
        run = None  # (start index, (section, chunk_no, sha, cites), rev)
        for k, (rev, t, _, ps) in enumerate(split):
            cell = None
            if ord_ < len(ps):
                section, chunk_no, text, cites = ps[ord_]
                sha = _sha(text)
                cell = (section[:512], chunk_no, sha, json.dumps(cites, ensure_ascii=False))
                prio = priority[0] if k == last else priority[1]
                words = min(len(text.split()), 65535)
                if sha not in passages or passages[sha][3] > prio:
                    passages[sha] = (sha, text, words, prio)
            if run and cell != run[1]:
                hist.append((base + ord_, qid, lang, page_id, ord_, *run[1], run[2], split[run[0]][1], t))
                run = None
            if cell and not run:
                run = (k, cell, rev)
        if run:
            current.append((base + ord_, qid, lang, page_id, ord_, *run[1], run[2], split[run[0]][1]))
    cur.executemany(
        "INSERT INTO passage (sha, text, words, priority) VALUES (?, ?, ?, ?) "
        "ON DUPLICATE KEY UPDATE priority = LEAST(priority, VALUES(priority))",
        list(passages.values()),
    )
    cols = "id, wikidata_id, lang, page_id, ord, section, chunk_no, sha, cites, rev_id, row_start"
    if hist:
        cur.executemany(f"INSERT INTO chunk ({cols}, row_end) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", hist)
    if current:
        cur.executemany(f"INSERT INTO chunk ({cols}) VALUES (?,?,?,?,?,?,?,?,?,?,?)", current)
    acols = "lang, page_id, wikidata_id, title, rev_id, bytes, passages, refs, quality, row_start"
    if a_hist:
        cur.executemany(f"INSERT INTO article ({acols}, row_end) VALUES (?,?,?,?,?,?,?,?,?,?,?)", a_hist)
    cur.executemany(f"INSERT INTO article ({acols}) VALUES (?,?,?,?,?,?,?,?,?,?)", a_cur)
    return len(hist) + len(current)


def _context():
    con = connect()
    cur = con.cursor()
    cur.execute("SET system_versioning_insert_history = 1")
    cur.execute("SELECT lang, page_id FROM article FOR SYSTEM_TIME ALL GROUP BY lang, page_id")
    loaded = set(cur.fetchall())
    cur.execute("SELECT wikidata_id, tier, priority, title_fi, title_sv, title_en FROM topic")
    topic = {r[0]: r[1:] for r in cur.fetchall()}
    return con, cur, loaded, topic


def priorities(tier, rank):
    """(priority of the current text, priority of the history) for a topic."""
    if rank == 0:
        return DEMO_CLASS, DEMO_CLASS
    return (CURRENT_CLASS + tier) * 10**4 + rank, (HISTORY_CLASS + tier) * 10**4 + rank


def load_fi(m_dir=DATA / "m", only=None):
    """Finnish history from dataset M, for the topics' Finnish articles."""
    con, cur, loaded, topic = _context()
    import duckdb  # only these loaders need it; the app image has none

    db = duckdb.connect()
    db.execute(
        f"CREATE TABLE p AS SELECT page_id, wikidata_id FROM '{DATA}/s/articles-fi.parquet' "
        "WHERE wikidata_id IN (SELECT unnest(?::VARCHAR[]))",
        [list(only or topic)],
    )
    todo = {pid: qid for pid, qid in db.execute("SELECT * FROM p").fetchall() if ("fi", pid) not in loaded}
    if not todo:
        return
    meta = db.execute(
        f"SELECT page_id, rev_id, timestamp FROM '{m_dir}/versions-*.parquet' "
        "WHERE page_id IN (SELECT unnest(?::UINTEGER[])) ORDER BY page_id, timestamp, rev_id",
        [list(todo)],
    ).fetchall()
    revs = {}
    for pid, rev, t in meta:
        revs.setdefault(pid, []).append((rev, _ts(t)))
    snaps = {pid: snapshots(r) for pid, r in revs.items()}
    wanted = [rev for s in snaps.values() for rev, _ in s]
    print(f"fi: {len(todo)} articles, {len(wanted)} snapshot texts", flush=True)
    db.execute("CREATE TABLE w AS SELECT unnest(?::UINTEGER[]) AS rev_id", [wanted])
    rel = db.execute(
        f"SELECT v.page_id, v.rev_id, v.text FROM '{m_dir}/versions-*.parquet' v "
        "SEMI JOIN w USING (rev_id) ORDER BY v.page_id"
    )
    texts, started, done, rows = {}, time.monotonic(), 0, 0

    def flush(pid):
        nonlocal done, rows
        qid = todo[pid]
        tier, rank, title = topic[qid][0], topic[qid][1], topic[qid][2]
        versions = [(rev, t, texts[rev]) for rev, t in snaps[pid] if rev in texts]
        if versions:
            rows += load_article(cur, "fi", pid, qid, title, versions, priorities(tier, rank))
            con.commit()
        done += 1
        if done % 100 == 0:
            print(f"fi: {done} articles, {rows} chunk rows, {time.monotonic() - started:.0f} s", flush=True)

    current = None
    while batch := rel.fetchmany(500):
        for pid, rev, text in batch:
            if current is not None and pid != current:
                flush(current)
                texts.clear()
            current = pid
            texts[rev] = text or ""
    if current is not None:
        flush(current)
    print(f"fi: {done} articles, {rows} chunk rows", flush=True)


def _records(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        try:
            for line in f:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    return
        except (EOFError, gzip.BadGzipFile, OSError):
            return  # a copy taken while the fetch was appending ends mid-record


def load_api_history(lang, path=None, only=None):
    """Swedish or English history from the fetch's history-{lang}.jsonl.gz."""
    path = path or DATA / "history" / f"history-{lang}.jsonl.gz"
    con, cur, loaded, topic = _context()
    started, done, rows = time.monotonic(), 0, 0
    for rec in _records(path):
        qid, pid = rec["wikidata_id"], rec["page_id"]
        if qid not in topic or (lang, pid) in loaded or (only and qid not in only) or not rec["revisions"]:
            continue
        revs = [(r["revid"], _ts(r["timestamp"])) for r in rec["revisions"]]
        texts = rec["texts"]
        versions = [(rev, t, texts[str(rev)]) for rev, t in snapshots(revs) if str(rev) in texts]
        if not versions:
            continue
        tier, rank = topic[qid][0], topic[qid][1]
        title = rec.get("current_title") or rec["title"]
        rows += load_article(cur, lang, pid, qid, title, versions, priorities(tier, rank))
        con.commit()
        loaded.add((lang, pid))
        done += 1
        if done % 100 == 0:
            print(f"{lang}: {done} articles, {rows} chunk rows, {time.monotonic() - started:.0f} s", flush=True)
    print(f"{lang}: {done} articles, {rows} chunk rows", flush=True)


def pageviews(path=None):
    """Monthly page views from the fetch: pageviews.jsonl.gz, or an older plain pageviews.jsonl."""
    gz = DATA / "history" / "pageviews.jsonl.gz"
    path = path or (gz if gz.exists() else DATA / "history" / "pageviews.jsonl")
    con = connect()
    cur = con.cursor()
    rows = []
    records = (
        _records(path)
        if str(path).endswith(".gz")
        else (json.loads(line) for line in open(path, encoding="utf-8") if line.strip().endswith("}"))
    )
    for rec in records:
        for ym, views in rec["monthly"].items():
            rows.append((rec["lang"], rec["page_id"], f"{ym[:4]}-{ym[4:6]}-01", views))
    for i in range(0, len(rows), 20000):
        cur.executemany("REPLACE INTO pageviews VALUES (?, ?, ?, ?)", rows[i : i + 20000])
    con.commit()
    print(f"pageviews: {len(rows)} monthly rows")
