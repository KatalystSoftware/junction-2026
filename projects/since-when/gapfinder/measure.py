"""Numbers for the write-up: vector index recall and latency, and the time of the AS OF queries.

    python -m gapfinder measure [--queries 100] [--runs 3]
    python -m gapfinder measure --versioned-index mine_a3 [--one-in 2] [--keep]

Recall@10 of the vector index on chunk_now is measured against exact search on the same table
(IGNORE INDEX), with current passages as the queries, for several mhnsw_ef_search values.

--versioned-index DB repeats the experiment behind the schema's choice to keep the vector index
off the versioned table: in the private database DB it copies the embedded passage versions into
a system-versioned table with a vector index, and compares nearest-neighbour searches AS OF past
dates with the same searches on plain tables holding only the rows visible at each date.

Both write a JSON file and a Markdown table made from it (--out, default OUT).
"""

import json
import os
import pathlib
import re
import shlex
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime

from .align import Run, as_of_sql, nearest_sql

OUT = "measurements"
EF = (20, 40, 80, 160)
DATES = (("now", None), ("AS OF 2010-01-01", "2010-01-01"), ("AS OF 2020-01-01", "2020-01-01"))
SETTINGS = (
    "innodb_buffer_pool_size",
    "mhnsw_max_cache_size",
    "mhnsw_ef_search",
    "mhnsw_default_m",
    "innodb_log_file_size",
)
NAME = re.compile(r"^[a-z][a-z0-9_]*$")
TABLES = {
    "topic": "Wikidata items with an article in Finnish, Swedish and English.",
    "article": "One row per article and edition; older versions are the article on each 1 January.",
    "chunk": "One row per passage position in an article; older versions are the passages at earlier dates.",
    "passage": "Passage texts, stored once per distinct text.",
    "passage with a vector": "Passage texts that have an embedding, so they can be compared.",
    "chunk_now": "The current passages with their vectors: the only table with a vector index.",
    "coverage": "Alignment results per topic, pair of editions and date.",
    "difference": "The classifier's output, one row per difference in a pair of passages.",
    "finding": "One row per gap; older versions show when it opened, was reviewed or closed.",
    "pageviews": "Monthly page views per article.",
    "full_history": "Articles whose history holds every revision, not only the text on each 1 January.",
}


def _timed(cur, sql, args=()):
    t0 = time.perf_counter()
    cur.execute(sql, args)
    rows = cur.fetchall()
    return rows, (time.perf_counter() - t0) * 1000


def _load():
    try:
        return [float(x) for x in pathlib.Path("/proc/loadavg").read_text().split()[:3]]
    except OSError:
        return None


def _commit():
    """The code's commit: GAPFINDER_COMMIT (the Docker image has no git), else git."""
    if os.environ.get("GAPFINDER_COMMIT"):
        return os.environ["GAPFINDER_COMMIT"]
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                cwd=pathlib.Path(__file__).parent,
                check=False,
            ).stdout.strip()
            or None
        )
    except OSError:
        return None


def _environment(cur, note, provisional):
    """Where and when a run happened: enough to tell two result files apart."""
    cur.execute("SELECT VERSION(), DATABASE(), @@hostname")
    version, database, server = cur.fetchone()
    cur.execute("SHOW GLOBAL VARIABLES WHERE Variable_name IN ({})".format(",".join(f"'{s}'" for s in SETTINGS)))
    settings = {k: int(v) for k, v in cur.fetchall()}
    cpu = mem = None
    try:
        cpu = next(l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name"))
        mem = round(int(next(l for l in open("/proc/meminfo") if l.startswith("MemTotal")).split()[1]) / 1024)
    except (OSError, StopIteration):
        pass
    return {
        "time_utc": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "command": "python -m gapfinder " + shlex.join(sys.argv[1:]),
        "commit": _commit(),
        "database": {
            "name": database,
            "host": os.environ.get("DB_HOST", "127.0.0.1"),
            "port": int(os.environ.get("DB_PORT", "3306")),
            "server_hostname": server,
        },
        "mariadb": {"version": version, "settings": settings},
        "machine": {"cpu": cpu, "cores": os.cpu_count(), "memory_mb": mem, "load_start": _load()},
        "note": note,
        "latency_provisional": provisional,
    }


def _row_counts(cur):
    """Rows per table: what a plain SELECT sees, and every stored version of a versioned table."""
    cur.execute(
        "SELECT table_name, table_type FROM information_schema.tables "
        "WHERE table_schema = DATABASE() ORDER BY table_name"
    )
    out = []
    for name, kind in cur.fetchall():
        cur.execute(f"SELECT COUNT(*) FROM `{name}`")
        row = {"table": name, "current": cur.fetchone()[0], "all_versions": None}
        if kind == "SYSTEM VERSIONED":
            cur.execute(f"SELECT COUNT(*) FROM `{name}` FOR SYSTEM_TIME ALL")
            row["all_versions"] = cur.fetchone()[0]
        out.append(row)
        if name == "passage":
            cur.execute("SELECT COUNT(*) FROM passage WHERE embedding IS NOT NULL")
            out.append({"table": "passage with a vector", "current": cur.fetchone()[0], "all_versions": None})
    return out


def _save(out, kind, result, markdown):
    result["machine"]["load_end"] = _load()
    folder = pathlib.Path(out)
    folder.mkdir(parents=True, exist_ok=True)
    stem = folder / f"{kind}-{result['time_utc'].replace('-', '').replace(':', '').replace(' ', '-')}Z"
    stem.with_suffix(".json").write_text(json.dumps(result, indent=1, default=str) + "\n")
    stem.with_suffix(".md").write_text(markdown(result))
    print(f"saved {stem}.json and {stem}.md")


def _n(x):
    return f"{x:,}"


def _header(title, res):
    m, db, s = res["machine"], res["database"], res["mariadb"]["settings"]
    load = (
        "not known"
        if not m["load_start"]
        else f"{m['load_start'][0]:.2f} at the start, {m['load_end'][0]:.2f} at the end, on {m['cores']} cores"
    )
    lines = [
        f"# {title}",
        "",
        f"- Command: `{res['command']}`",
        f"- Run at {res['time_utc']} UTC, code at commit `{res['commit'] or 'unknown'}`.",
        (
            f"- Database `{db['name']}` on `{db['host']}:{db['port']}` (server host name `{db['server_hostname']}`), "
            f"MariaDB {res['mariadb']['version']}."
        ),
        (
            f"- Server settings: buffer pool {s['innodb_buffer_pool_size'] >> 20:,} MB (memory for table data), "
            f"vector cache {s['mhnsw_max_cache_size'] >> 20:,} MB (`mhnsw_max_cache_size`, memory for vector "
            f"indexes), `mhnsw_ef_search` {s['mhnsw_ef_search']} by default."
        ),
        (
            f"- Machine running the command: {m['cpu'] or 'unknown CPU'}, {m['cores']} cores, "
            f"{_n(m['memory_mb'] or 0)} MB of memory. One-minute load average: {load}."
        ),
    ]
    if res["note"]:
        lines.append(f"- Note: {res['note']}")
    lines.append(
        "- **Times are provisional**: other jobs were using the machine during this run. Recall "
        "does not depend on load."
        if res["latency_provisional"]
        else "- Times are from one run on this machine; recall does not depend on load."
    )
    return lines + [""]


def _markdown(res):
    rec, al = res["recall"], res["alignment"]
    q = f"{rec['queries']} current passages as queries"
    rows = [
        (
            "Exact search, median time",
            f"{rec['exact_median_ms']:.2f} ms",
            q,
            (
                f"Finding a passage's 10 nearest passages by comparing it with all {_n(rec['rows'])} rows of "
                "`chunk_now`, without the index: the correct answer that the index is checked against."
            ),
        )
    ]
    for e in rec["ef"]:
        rows.append(
            (
                f"Index, `mhnsw_ef_search` = {e['ef_search']}: recall@10",
                f"{e['recall_at_10']:.3f}",
                q,
                (
                    f"Of the 10 truly nearest passages, the index returned {e['recall_at_10'] * 10:.2f} on "
                    f"average when it keeps {e['ef_search']} candidates while searching (1.000 = the exact answer)."
                ),
            )
        )
        rows.append(
            (
                f"Index, `mhnsw_ef_search` = {e['ef_search']}: median time",
                f"{e['median_ms']:.2f} ms",
                q,
                (
                    f"The same search through the index takes this long, against {rec['exact_median_ms']:.0f} ms "
                    "for the exact search."
                ),
            )
        )
    for a in al:
        n = f"{a['topics']} topics, {a['runs']} runs each"
        rows.append(
            (
                f"Alignment {a['label']}: median time",
                f"{a['median_ms']:.2f} ms",
                n,
                (
                    f"One query compares every passage of a topic with every passage of its other two editions"
                    f"{'' if a['as_of'] is None else ' as the articles stood on ' + a['as_of']}, exactly and "
                    f"without an index; the median topic had {a['median_rows']:.0f} passages to match."
                ),
            )
        )
        rows.append(
            (
                f"Alignment {a['label']}: slowest topic",
                f"{a['max_ms']:.2f} ms",
                n,
                (
                    f"The slowest of the {a['topics']} topics (its median over {a['runs']} runs), so the worst "
                    "case a reader of the tool waits for."
                ),
            )
        )
    lines = _header("Gap finder: vector index recall and query times", res)
    lines += ["| Figure | Value | Measured over | What it means |", "|---|---:|---|---|"]
    lines += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows]
    lines += [
        "",
        (
            "The topics timed are the 20 with the most past dates aligned. The queries are the passages "
            "with the lowest `CRC32(id)`, so a second run asks the same questions."
        ),
        "",
        "## Rows per table",
        "",
        "| Table | Current rows | All versions | What it holds |",
        "|---|---:|---:|---|",
    ]
    lines += [
        f"| `{t['table']}` | {_n(t['current'])} | {'' if t['all_versions'] is None else _n(t['all_versions'])} "
        f"| {TABLES.get(t['table'], '')} |"
        for t in res["row_counts"]
    ]
    return "\n".join(lines) + "\n"


def run(queries=100, runs=3, out=OUT, note=None, provisional=False):
    r = Run()
    cur = r.cur
    res = _environment(cur, note, provisional)
    res["row_counts"] = _row_counts(cur)
    cur.execute("SELECT COUNT(*) FROM chunk_now")
    n = cur.fetchone()[0]
    # The lowest CRC32(id): a fixed spread of passages that stays put when other rows change.
    cur.execute("SELECT id FROM chunk_now ORDER BY CRC32(id), id LIMIT ?", (queries,))
    ids = [x[0] for x in cur.fetchall()]
    print(f"chunk_now: {n} passages, {len(ids)} queries, recall@10 against exact search")
    indexed = "SELECT n.id FROM chunk_now AS n ORDER BY VEC_DISTANCE_COSINE(n.embedding, @q) LIMIT 10"
    exact, t_exact = {}, []
    for i in ids:
        rows, ms = _timed(
            cur,
            "SELECT n.id FROM chunk_now AS n IGNORE INDEX (embedding) "
            "ORDER BY VEC_DISTANCE_COSINE(n.embedding, (SELECT embedding FROM chunk_now WHERE id = ?)) "
            "LIMIT 10",
            (i,),
        )
        exact[i] = {x[0] for x in rows}
        t_exact.append(ms)
        # One untimed search through the index, so the first setting is not charged for loading it.
        cur.execute("SET @q = (SELECT embedding FROM chunk_now WHERE id = ?)", (i,))
        _timed(cur, indexed)
    print(f"  exact          median {statistics.median(t_exact):7.2f} ms")
    res["recall"] = {
        "table": "chunk_now",
        "rows": n,
        "queries": len(ids),
        "exact_median_ms": round(statistics.median(t_exact), 2),
        "ef": [],
    }
    for ef in EF:
        cur.execute(f"SET mhnsw_ef_search = {ef}")
        hits, t = [], []
        for i in ids:
            cur.execute("SET @q = (SELECT embedding FROM chunk_now WHERE id = ?)", (i,))
            rows, ms = _timed(cur, indexed)
            hits.append(len(exact[i] & {x[0] for x in rows}) / 10)
            t.append(ms)
        print(f"  ef_search {ef:4d} median {statistics.median(t):7.2f} ms, recall@10 {statistics.mean(hits):.3f}")
        res["recall"]["ef"].append(
            {
                "ef_search": ef,
                "recall_at_10": round(statistics.mean(hits), 4),
                "median_ms": round(statistics.median(t), 2),
            }
        )
    cur.execute("SET mhnsw_ef_search = DEFAULT")

    # Alignment: one topic, every passage against every passage of the other editions, AS OF a date.
    cur.execute(
        "SELECT wikidata_id FROM coverage WHERE NOT is_current GROUP BY wikidata_id "
        "ORDER BY COUNT(*) DESC, wikidata_id LIMIT 20"
    )
    topics = [x[0] for x in cur.fetchall()]
    res["alignment"] = []
    for label, as_of in DATES:
        t, sizes = [], []
        for qid in topics:
            timed = [_timed(cur, nearest_sql(qid, as_of)) for _ in range(runs)]
            t.append(statistics.median(ms for _, ms in timed))
            sizes.append(len(timed[0][0]))
        if t:
            print(
                f"  alignment {label:17s} median {statistics.median(t):6.2f} ms, max {max(t):6.2f} ms "
                f"over {len(t)} topics, {runs} runs each"
            )
            res["alignment"].append(
                {
                    "label": label,
                    "as_of": as_of,
                    "topics": len(t),
                    "runs": runs,
                    "median_ms": round(statistics.median(t), 2),
                    "max_ms": round(max(t), 2),
                    "median_rows": statistics.median(sizes),
                }
            )
    _save(out, "measure", res, _markdown)


def _versioned_markdown(res):
    x = res["experiment"]
    lines = _header("Vector index on a system-versioned table: recall of AS OF searches", res)
    lines += [
        f"The experiment tables live in the private database `{x['database']}`; `{x['source']}` is only read.",
        "",
        (
            f"- **Versioned table**: {_n(x['versions'])} versions of {_n(x['ids'])} passages from {_n(x['topics'])} "
            f"topics, each with its 1024-number embedding and the real edit times as `row_start` and `row_end`, in "
            f"one table `WITH SYSTEM VERSIONING` and a vector index (`{x['index']}`). Built in {x['build_s']:.0f} s."
        ),
        f"- **Sample**: {x['sample']}",
        (
            "- **Plain tables**: for each date, an ordinary table with only the rows visible at that date and the "
            "same vector index. This is what the tool does today with `chunk_now`."
        ),
        (
            f"- **Queries**: at each date, the {res['dates'][0]['queries']} visible passages with the lowest "
            "`CRC32(id)`; each asks for its 10 nearest passages (`ORDER BY VEC_DISTANCE_COSINE(...) LIMIT 10`)."
        ),
        (
            "- **Recall@10**: of the 10 truly nearest rows visible at the date (found by comparing with every "
            "row, `IGNORE INDEX`), the share a search returned. 1.00 is the exact answer."
        ),
        "",
        "## Headline figures (`mhnsw_ef_search` = 20, the server default)",
        "",
        "| Figure | Value | Measured over | What it means |",
        "|---|---:|---|---|",
    ]
    for d in res["dates"]:
        e, when = d["ef"][0], d["label"]
        over = f"{d['queries']} queries, {_n(d['visible_rows'])} rows visible {when}"
        lines += [
            (
                f"| Plain table, rows {when}: recall@10 | {e['plain_recall']:.3f} | {over} | With only the "
                f"{_n(d['visible_rows'])} visible rows in the index, the index returns {e['plain_recall'] * 10:.1f} of "
                "the 10 right answers on average. |"
            ),
            (
                f"| Versioned table with the index, {when}: recall@10 | {e['versioned_recall']:.3f} | {over} | The same "
                f"question through the index that holds all {_n(x['versions'])} versions returns "
                f"{e['versioned_recall'] * 10:.1f} of the 10 right answers on average. |"
            ),
            (
                f"| Versioned table with the index, {when}: rows returned | {e['versioned_rows']:.2f} of 10 | {over} | "
                f"`LIMIT 10` came back with this many rows on average. Of the index's 10 nearest versions over all "
                f"of history only {e['all_versions_visible']:.1f} were visible {when}, so 10 rows means the search "
                "went on fetching versions until 10 passed the date filter. |"
            ),
            (
                f"| Versioned table without the index, {when}: recall@10 | {d['versioned_exact_recall']:.3f} | {over} | "
                f"With `IGNORE INDEX` the versioned table gives the exact answer, in {d['versioned_exact_ms']:.0f} ms "
                f"per search against {e['versioned_ms']:.1f} ms with the index. |"
            ),
        ]
    lines += [
        "",
        "## Every setting",
        "",
        (
            "| Date | Rows visible | `mhnsw_ef_search` | Plain table recall@10 | Versioned + index recall@10 | "
            "Rows returned of 10 | Nearest 10 versions visible at the date | Plain ms | Versioned ms |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for d in res["dates"]:
        lines += [
            f"| {d['label']} | {_n(d['visible_rows'])} | {e['ef_search']} | {e['plain_recall']:.3f} | "
            f"{e['versioned_recall']:.3f} | {e['versioned_rows']:.2f} | {e['all_versions_visible']:.2f} | "
            f"{e['plain_ms']:.2f} | {e['versioned_ms']:.2f} |"
            for e in d["ef"]
        ]
    lines += [
        "",
        (
            "- `mhnsw_ef_search`: how many candidates the index keeps while it searches; higher finds more and "
            "takes longer."
        ),
        "- Rows returned of 10: how many rows the `AS OF` search through the index gave back for `LIMIT 10`.",
        (
            "- Nearest 10 versions visible at the date: the index's 10 nearest versions over all of history "
            "(`FOR SYSTEM_TIME ALL`), and how many of them were visible at the date."
        ),
        "- Plain ms, Versioned ms: median time of one search through the index.",
        "",
        "How MariaDB runs the versioned search (`EXPLAIN`, " + res["dates"][-1]["label"] + "):",
        "",
    ]
    lines += [f"- {k}: `{json.dumps(v, default=str)}`" for k, v in res["dates"][-1]["explain"].items()]
    return "\n".join(lines) + "\n"


def versioned_index(db, queries=100, one_in=2, keep=False, out=OUT, note=None, provisional=False):
    """Does a vector index on a system-versioned table find the right rows AS OF a past date?"""
    r = Run()
    cur = r.cur
    res = _environment(cur, note, provisional)
    source = res["database"]["name"]
    if not NAME.match(db) or db == source:
        sys.exit(f"--versioned-index needs a private database, not {db!r}: it creates and drops tables there")
    v = f"{db}.passage_versioned"
    plain = {label: f"{db}.passage_plain_{(as_of or 'now')[:4]}" for label, as_of in DATES}
    index = "M=16 DISTANCE=cosine"
    cur.execute(f"DROP TABLE IF EXISTS {v}, {', '.join(plain.values())}")
    t0 = time.perf_counter()
    cur.execute(f"""CREATE TABLE {v} (
  id         BIGINT UNSIGNED NOT NULL PRIMARY KEY,
  embedding  VECTOR(1024) NOT NULL,
  row_start  TIMESTAMP(6) GENERATED ALWAYS AS ROW START INVISIBLE,
  row_end    TIMESTAMP(6) GENERATED ALWAYS AS ROW END INVISIBLE,
  PERIOD FOR SYSTEM_TIME (row_start, row_end),
  VECTOR INDEX (embedding) {index}
) WITH SYSTEM VERSIONING""")
    # Every stored version of every embedded passage of the sampled topics, oldest first, with the
    # edit times it has in chunk.
    cur.execute("SET system_versioning_insert_history = 1")
    cur.execute(f"""INSERT INTO {v} (id, embedding, row_start, row_end)
SELECT c.id, p.embedding, c.row_start, c.row_end
FROM chunk FOR SYSTEM_TIME ALL AS c JOIN passage AS p ON p.sha = c.sha
WHERE p.embedding IS NOT NULL AND CRC32(c.wikidata_id) % {int(one_in)} = 0
ORDER BY c.row_start, c.id""")
    cur.execute("SET system_versioning_insert_history = 0")
    build_s = time.perf_counter() - t0
    cur.execute(f"SELECT COUNT(*), COUNT(DISTINCT id) FROM {v} FOR SYSTEM_TIME ALL")
    versions, ids_n = cur.fetchone()
    cur.execute(
        f"SELECT COUNT(DISTINCT c.wikidata_id) FROM chunk FOR SYSTEM_TIME ALL AS c "
        f"JOIN passage AS p ON p.sha = c.sha "
        f"WHERE p.embedding IS NOT NULL AND CRC32(c.wikidata_id) % {int(one_in)} = 0"
    )
    topics = cur.fetchone()[0]
    print(f"{v}: {versions} versions of {ids_n} passages, vector index built in {build_s:.0f} s", flush=True)
    res["experiment"] = {
        "database": db,
        "source": source,
        "index": index,
        "versions": versions,
        "ids": ids_n,
        "topics": topics,
        "build_s": round(build_s, 1),
        "one_in": one_in,
        "sample": (
            "every stored version of every passage that has an embedding"
            if one_in == 1
            else f"every stored version of every embedded passage of the topics with "
            f"`CRC32(wikidata_id) % {one_in} = 0`, about one topic in {one_in}, so that the index fits "
            f"the scratch server's shared vector cache next to `chunk_now`; `--one-in 1` copies everything"
        ),
    }
    res["dates"] = []
    for label, as_of in DATES:
        clause = "" if as_of is None else f" FOR SYSTEM_TIME AS OF {as_of_sql(as_of)}"
        at = as_of_sql(as_of)
        cur.execute(
            f"CREATE TABLE {plain[label]} (id BIGINT UNSIGNED NOT NULL PRIMARY KEY, "
            f"embedding VECTOR(1024) NOT NULL, VECTOR INDEX (embedding) {index})"
        )
        cur.execute(f"INSERT INTO {plain[label]} SELECT id, embedding FROM {v}{clause} ORDER BY id")
        cur.execute(f"SELECT COUNT(*) FROM {plain[label]}")
        visible = cur.fetchone()[0]
        cur.execute(f"SELECT id FROM {plain[label]} ORDER BY CRC32(id), id LIMIT ?", (queries,))
        ids = [x[0] for x in cur.fetchall()]
        q_plain = f"SELECT n.id FROM {plain[label]} AS n%s ORDER BY VEC_DISTANCE_COSINE(n.embedding, @q) LIMIT 10"
        q_versioned = f"SELECT n.id FROM {v}{clause} AS n%s ORDER BY VEC_DISTANCE_COSINE(n.embedding, @q) LIMIT 10"
        q_all = (
            f"SELECT n.row_start <= {at} AND n.row_end > {at} FROM {v} FOR SYSTEM_TIME ALL AS n "
            "ORDER BY VEC_DISTANCE_COSINE(n.embedding, @q) LIMIT 10"
        )
        ignore = " IGNORE INDEX (embedding)"
        exact, t_plain, t_versioned, same = {}, [], [], []
        for i in ids:
            cur.execute(f"SET @q = (SELECT embedding FROM {plain[label]} WHERE id = ?)", (i,))
            rows, ms = _timed(cur, q_plain % ignore)
            exact[i] = {x[0] for x in rows}
            t_plain.append(ms)
            rows, ms = _timed(cur, q_versioned % ignore)
            same.append(len(exact[i] & {x[0] for x in rows}) / 10)
            t_versioned.append(ms)
            # One untimed search through each index, so the first setting is not charged for loading them.
            _timed(cur, q_plain % "")
            _timed(cur, q_versioned % "")
        d = {
            "label": label,
            "as_of": as_of,
            "visible_rows": visible,
            "queries": len(ids),
            "plain_exact_ms": round(statistics.median(t_plain), 2),
            "versioned_exact_ms": round(statistics.median(t_versioned), 2),
            "versioned_exact_recall": round(statistics.mean(same), 4),
            "explain": {},
            "ef": [],
        }
        for name, sql in (
            ("versioned table with the index", q_versioned % ""),
            ("versioned table, IGNORE INDEX", q_versioned % ignore),
        ):
            cur.execute("EXPLAIN " + sql)
            d["explain"][name] = [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]
        print(
            f"{label}: {visible} rows visible, {len(ids)} queries; versioned table without the index "
            f"recall@10 {d['versioned_exact_recall']:.3f}, median {d['versioned_exact_ms']:.2f} ms",
            flush=True,
        )
        for ef in EF + (1000,):
            cur.execute(f"SET mhnsw_ef_search = {ef}")
            m = {
                k: []
                for k in (
                    "plain_recall",
                    "plain_ms",
                    "versioned_recall",
                    "versioned_ms",
                    "versioned_rows",
                    "all_versions_visible",
                )
            }
            for i in ids:
                cur.execute(f"SET @q = (SELECT embedding FROM {plain[label]} WHERE id = ?)", (i,))
                rows, ms = _timed(cur, q_plain % "")
                m["plain_recall"].append(len(exact[i] & {x[0] for x in rows}) / 10)
                m["plain_ms"].append(ms)
                rows, ms = _timed(cur, q_versioned % "")
                m["versioned_recall"].append(len(exact[i] & {x[0] for x in rows}) / 10)
                m["versioned_ms"].append(ms)
                m["versioned_rows"].append(len(rows))
                cur.execute(q_all)
                m["all_versions_visible"].append(sum(x[0] for x in cur.fetchall()))
            e = {
                "ef_search": ef,
                **{
                    k: round(statistics.median(x) if k.endswith("_ms") else statistics.mean(x), 4) for k, x in m.items()
                },
            }
            d["ef"].append(e)
            print(
                f"  ef_search {ef:4d} recall@10: plain table {e['plain_recall']:.3f}, versioned table "
                f"{e['versioned_recall']:.3f} ({e['versioned_rows']:.2f} of 10 rows returned)",
                flush=True,
            )
        cur.execute("SET mhnsw_ef_search = DEFAULT")
        res["dates"].append(d)
    if not keep:
        cur.execute(f"DROP TABLE {v}, {', '.join(plain.values())}")
    _save(out, "versioned-index", res, _versioned_markdown)
