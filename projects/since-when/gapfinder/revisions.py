"""Every revision of a few topics' articles: fetch them, embed them, load them as system versions.

    python -m gapfinder.revisions fetch Q1412941 ...   every revision, into the disk cache
    python -m gapfinder.revisions embed Q1412941 fi    embed that edition's passages, into the disk cache
    python -m gapfinder.revisions load Q1412941 ...    replace those topics' article and chunk history

The cache (REVISIONS, default data/mariadb/revisions; its README.md has the layout) keeps every raw
API response, so a second fetch reads the disk, and every embedding under the hash of its passage,
so a second embed computes nothing. Embed before load: the load takes each passage's embedding from
the cache, so the database never holds a topic half embedded.
"""
import gzip
import hashlib
import json
import multiprocessing
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from . import wikitext
from .db import connect
from .embed import Embedder, vec_bytes
from .load import _context, _sha, _ts, load_article, priorities, snapshots

ROOT = pathlib.Path(os.environ.get("REVISIONS", "data/mariadb/revisions"))
AGENT = "junction2026-gap-finder/0.1 (https://github.com/katalystsoftware/junction2026)"
PAUSE = 1.0  # seconds between requests
BATCH = 50   # revision texts per request, the API's limit
FAR = datetime(2106, 1, 1)  # row_end of a current row is later than this
WORKERS = int(os.environ.get("WORKERS", 8))  # processes that split wikitext into passages
THREADS = int(os.environ.get("THREADS", 0)) or None  # of the embedding model; all cores when unset
# SINCE=2022-01-01 keeps every revision from that day on and the 1 January texts before it.
SINCE = os.environ.get("SINCE")
COLS = {"chunk": "id, wikidata_id, lang, page_id, ord, section, chunk_no, rev_id, sha, cites, row_start, row_end",
        "article": "lang, page_id, wikidata_id, title, rev_id, bytes, passages, refs, quality, row_start, row_end"}


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    tmp.rename(path)


def api(lang, **params):
    """One Action API call; an answer already on disk is read from there."""
    params = dict(sorted({"format": "json", "formatversion": "2", "maxlag": "5", **params}.items()))
    key = hashlib.sha1(json.dumps([lang, params]).encode()).hexdigest()
    path = ROOT / "raw" / lang / f"{key}.json"
    if path.exists():
        return json.loads(path.read_bytes())
    url = f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept-Encoding": "gzip"})
    for attempt in range(8):
        time.sleep(PAUSE)
        try:
            with urllib.request.urlopen(request, timeout=120) as r:
                body, wait = r.read(), r.headers.get("Retry-After")
                if r.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500:
                raise
            body, wait = None, e.headers.get("Retry-After")
        except (urllib.error.URLError, TimeoutError):
            body, wait = None, None
        data = json.loads(body) if body else None
        if data and "error" not in data:
            _write(path, body)
            with open(ROOT / "raw" / "requests.tsv", "a") as log:
                log.write(f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}\t{lang}\t{key}\t{json.dumps(params)}\n")
            return data
        if data and data["error"].get("code") != "maxlag":
            raise RuntimeError(f"{lang}: {data['error']}")
        wait = int(wait) if wait and wait.isdigit() else 5 * 2 ** attempt
        print(f"{lang}: backing off {wait} s", flush=True)
        time.sleep(wait)
    raise RuntimeError(f"{lang}: no answer after 8 tries: {params}")


def _all(lang, **params):
    """Every page of one query, following continue."""
    more = {}
    while True:
        data = api(lang, **params, **more)
        yield data
        if "continue" not in data:
            return
        more = data["continue"]


def fetch_article(qid, lang, page_id, title):
    started, sent = time.monotonic(), _requests()
    revs = [rv for data in _all(lang, action="query", prop="revisions", pageids=str(page_id), rvlimit="max",
                                rvdir="newer", rvprop="ids|timestamp|user|comment|sha1|size|flags")
            for rv in data["query"]["pages"][0].get("revisions", [])]
    texts = {}
    for i in range(0, len(revs), BATCH):
        ids = "|".join(str(rv["revid"]) for rv in revs[i:i + BATCH])
        for data in _all(lang, action="query", prop="revisions", revids=ids, rvprop="ids|content", rvslots="main"):
            for page in data["query"].get("pages", []):
                for rv in page.get("revisions", []):
                    content = rv.get("slots", {}).get("main", {}).get("content")
                    if content is not None:
                        texts[rv["revid"]] = content
        print(f"{qid} {lang}: {min(i + BATCH, len(revs))}/{len(revs)} texts", flush=True)
    lines = [json.dumps({"revid": rv["revid"], "parentid": rv.get("parentid"), "timestamp": rv["timestamp"],
                         "user": rv.get("user"), "comment": rv.get("comment"), "sha1": rv.get("sha1"),
                         "size": rv.get("size"), "minor": rv.get("minor", False),
                         "text": texts.get(rv["revid"])}, ensure_ascii=False) for rv in revs]
    _write(ROOT / qid / f"{lang}.jsonl.gz", gzip.compress(("\n".join(lines) + "\n").encode()))
    summary = {"page_id": page_id, "title": title, "revisions": len(revs), "with_text": len(texts),
               "first": revs[0]["timestamp"], "last": revs[-1]["timestamp"],
               "fetched_at": f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}"}
    _write(ROOT / qid / f"{lang}.json", json.dumps(summary, ensure_ascii=False, indent=1).encode())
    print(f"{qid} {lang}: {len(revs)} revisions, {len(texts)} with text, {_requests() - sent} requests, "
          f"{time.monotonic() - started:.0f} s", flush=True)


def _requests():
    log = ROOT / "raw" / "requests.tsv"
    return sum(1 for _ in open(log)) if log.exists() else 0


def _articles(cur, qid):
    cur.execute("SELECT lang, page_id, title FROM article WHERE wikidata_id = ? ORDER BY lang", (qid,))
    return cur.fetchall()


def fetch(qids):
    cur = connect().cursor()
    for qid in qids:
        for lang, page_id, title in _articles(cur, qid):
            fetch_article(qid, lang, page_id, title)


def versions(cur, qid, lang, page_id):
    """[(rev_id, time, wikitext)] oldest first: every revision that has text, up to the one the
    database holds as current, so the current passages stay as they are. Of revisions saved in the
    same second the last one stands."""
    cur.execute("SELECT rev_id FROM article WHERE lang = ? AND page_id = ?", (lang, page_id))
    current, out = cur.fetchone()[0], []
    with gzip.open(ROOT / qid / f"{lang}.jsonl.gz", "rt", encoding="utf-8") as f:
        for rv in map(json.loads, f):
            if rv["text"] is not None:
                row = (rv["revid"], _ts(rv["timestamp"]), rv["text"])
                if out and out[-1][1] >= row[1]:
                    out[-1] = (row[0], out[-1][1], row[2])
                else:
                    out.append(row)
            if rv["revid"] == current:
                break
        else:
            raise RuntimeError(f"{qid} {lang}: revision {current} is not in the cache")
    if SINCE:
        keep = {rev for rev, _ in snapshots([v[:2] for v in out])}
        out = [v for v in out if v[0] in keep or v[1] >= datetime.fromisoformat(SINCE)]
    return out


def _passages(text):
    # No edition: these topics keep the English language names ("Finnish: Suomen sota") in every
    # edition, as loaded on 14 Nov 2026. The classifier cache and the embedding cache are keyed on
    # passage text, and edition=lang rewrites the Swedish Finnish War introduction.
    return wikitext.passages(text, cites=True)


def split(versions):
    """[(rev_id, time, wikitext, passages)], as load_article takes them; splitting is the slow part."""
    with multiprocessing.Pool(WORKERS) as pool:
        parts = pool.map(_passages, [v[2] for v in versions], chunksize=8)
    return [v + (ps,) for v, ps in zip(versions, parts)]


def _vec(sha):
    return ROOT / "embeddings" / sha[:2] / f"{sha}.vec"


def embed(qid, langs):
    """Embed every passage of the topic's revisions that neither the cache nor the database has."""
    cur = connect().cursor()
    model = None
    for lang, page_id, _ in _articles(cur, qid):
        if langs and lang not in langs:
            continue
        started = time.monotonic()
        texts = {_sha(text).hex(): text for v in split(versions(cur, qid, lang, page_id)) for _, _, text, _ in v[3]}
        todo, have = [s for s in texts if not _vec(s).exists()], set()
        for i in range(0, len(todo), 500):
            part = todo[i:i + 500]
            cur.execute("SELECT sha FROM passage WHERE embedding IS NOT NULL AND sha IN (%s)" % ",".join("?" * len(part)),
                        [bytes.fromhex(s) for s in part])
            have |= {bytes(r[0]).hex() for r in cur.fetchall()}
        cached = len(texts) - len(todo)
        todo = sorted((s for s in todo if s not in have), key=lambda s: len(texts[s]))  # similar lengths in a batch
        words = sum(len(texts[s].split()) for s in todo)
        print(f"{qid} {lang}: {len(texts)} passages, {cached} in the cache, {len(have)} embedded in the database, "
              f"{len(todo)} to compute ({words} words), split in {time.monotonic() - started:.0f} s", flush=True)
        for i in range(0, len(todo), 64):
            model = model or Embedder(THREADS)
            part = todo[i:i + 64]
            for sha, v in zip(part, model([texts[s] for s in part])):
                _write(_vec(sha), vec_bytes(v))
            print(f"{qid} {lang}: {min(i + 64, len(todo))}/{len(todo)} embedded, {time.monotonic() - started:.0f} s", flush=True)
        print(f"{qid} {lang}: {len(todo)} embeddings computed, {time.monotonic() - started:.0f} s", flush=True)


def _current(cur, qids):
    cur.execute("SELECT id, sha, section, chunk_no FROM chunk WHERE wikidata_id IN (%s)" % ",".join("?" * len(qids)), qids)
    return {(r[0], bytes(r[1]), r[2], r[3]) for r in cur.fetchall()}


def load(qids):
    """Replace the topics' article and chunk history with every revision, in one transaction.

    History rows can only be deleted for a whole table (DELETE HISTORY), so the other topics'
    history is set aside in a1_keep_* first and put back inside the same transaction."""
    con, cur, _, topic = _context()
    started, marks = time.monotonic(), ",".join("?" * len(qids))
    before, todo = _current(cur, qids), []
    for qid in qids:
        for lang, page_id, title in _articles(cur, qid):
            todo.append((qid, lang, page_id, title, split(versions(cur, qid, lang, page_id))))
    print(f"split {sum(len(t[4]) for t in todo)} revisions, {time.monotonic() - started:.0f} s", flush=True)
    for table, cols in COLS.items():
        cur.execute(f"DROP TABLE IF EXISTS a1_keep_{table}")
        cur.execute(f"CREATE TABLE a1_keep_{table} AS SELECT {cols} FROM {table} FOR SYSTEM_TIME ALL "
                    f"WHERE row_end < ? AND wikidata_id NOT IN ({marks})", (FAR, *qids))
    for table, cols in COLS.items():
        cur.execute(f"DELETE FROM {table} WHERE wikidata_id IN ({marks})", qids)
        cur.execute(f"DELETE HISTORY FROM {table}")
        cur.execute(f"INSERT INTO {table} ({cols}) SELECT {cols} FROM a1_keep_{table}")
    for qid, lang, page_id, title, parts in todo:
        rows = load_article(cur, lang, page_id, qid, title, None, priorities(*topic[qid][:2]), parts)
        cur.execute("REPLACE INTO full_history (wikidata_id, lang, since) VALUES (?, ?, ?)",
                    (qid, lang, datetime.fromisoformat(SINCE) if SINCE else parts[0][1]))
        shas = {text for v in parts for _, _, text, _ in v[3]}
        print(f"{qid} {lang}: {len(parts)} article versions, {rows} chunk versions, {len(shas)} distinct passages",
              flush=True)
    cur.execute("SELECT DISTINCT p.sha FROM chunk FOR SYSTEM_TIME ALL AS c JOIN passage p ON p.sha = c.sha "
                f"WHERE c.wikidata_id IN ({marks}) AND p.embedding IS NULL", qids)
    missing = [bytes(r[0]) for r in cur.fetchall()]
    found = [(_vec(sha.hex()).read_bytes(), sha) for sha in missing if _vec(sha.hex()).exists()]
    if found:
        cur.executemany("UPDATE passage SET embedding = ? WHERE sha = ?", found)
    print(f"{len(found)} embeddings from the cache, {len(missing) - len(found)} passages without one", flush=True)
    # A current passage changes where today's wikitext.py reads the same revision differently from
    # the code that loaded it. The vector index's copy of the current passages follows.
    after = _current(cur, qids)
    changed = ",".join(str(i) for i in sorted({c[0] for c in before ^ after}))
    if changed:
        cur.execute(f"DELETE FROM chunk_now WHERE id IN ({changed})")
        cur.execute(f"""INSERT INTO chunk_now (id, wikidata_id, lang, section, embedding)
                        SELECT c.id, c.wikidata_id, c.lang, c.section, p.embedding
                        FROM chunk AS c JOIN passage AS p ON p.sha = c.sha
                        WHERE c.id IN ({changed}) AND p.embedding IS NOT NULL""")
    con.commit()
    for table in COLS:
        cur.execute(f"DROP TABLE a1_keep_{table}")
    print(f"loaded; {len(before & after)} of the {len(after)} current passages kept their ids and texts; "
          f"{time.monotonic() - started:.0f} s", flush=True)
    for name, rows in (("before", before - after), ("now", after - before)):
        for i, sha, section, no in sorted(rows):
            print(f"  changed, {name}: passage {i} ({section or 'lead'} {no}), sha {sha.hex()}", flush=True)


if __name__ == "__main__":
    step, args = sys.argv[1], sys.argv[2:]
    if step == "fetch":
        fetch(args)
    elif step == "embed":
        embed(args[0], args[1:])
    elif step == "load":
        load(args)
    else:
        sys.exit(__doc__)
