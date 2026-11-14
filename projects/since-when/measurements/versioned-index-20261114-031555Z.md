# Vector index on a system-versioned table: recall of AS OF searches

- Command: `python -m gapfinder measure --versioned-index mine_a3 --provisional --note 'scratch server: Docker container limited to 3.5 GB of memory and 4 CPUs'`
- Run at 2026-11-14 03:15:55 UTC, code at commit `f1c5c38`.
- Database `gapfinder` on `gapfinder-scratch-db:3306` (server host name `5c1a2b8cf41d`), MariaDB 11.8.9-MariaDB-ubu2404.
- Server settings: buffer pool 2,048 MB (memory for table data), vector cache 512 MB (`mhnsw_max_cache_size`, memory for vector indexes), `mhnsw_ef_search` 20 by default.
- Machine running the command: AMD Ryzen 5 2600 Six-Core Processor, 12 cores, 15,924 MB of memory. One-minute load average: 11.61 at the start, 3.13 at the end, on 12 cores.
- Note: scratch server: Docker container limited to 3.5 GB of memory and 4 CPUs
- **Times are provisional**: other jobs were using the machine during this run. Recall does not depend on load.

The experiment tables live in the private database `mine_a3`; `gapfinder` is only read.

- **Versioned table**: 44,743 versions of 20,835 passages from 1,487 topics, each with its 1024-number embedding and the real edit times as `row_start` and `row_end`, in one table `WITH SYSTEM VERSIONING` and a vector index (`M=16 DISTANCE=cosine`). Built in 57 s.
- **Sample**: every stored version of every embedded passage of the topics with `CRC32(wikidata_id) % 2 = 0`, about one topic in 2, so that the index fits the scratch server's shared vector cache next to `chunk_now`; `--one-in 1` copies everything
- **Plain tables**: for each date, an ordinary table with only the rows visible at that date and the same vector index. This is what the tool does today with `chunk_now`.
- **Queries**: at each date, the 100 visible passages with the lowest `CRC32(id)`; each asks for its 10 nearest passages (`ORDER BY VEC_DISTANCE_COSINE(...) LIMIT 10`).
- **Recall@10**: of the 10 truly nearest rows visible at the date (found by comparing with every row, `IGNORE INDEX`), the share a search returned. 1.00 is the exact answer.

## Headline figures (`mhnsw_ef_search` = 20, the server default)

| Figure | Value | Measured over | What it means |
|---|---:|---|---|
| Plain table, rows now: recall@10 | 0.992 | 100 queries, 20,589 rows visible now | With only the 20,589 visible rows in the index, the index returns 9.9 of the 10 right answers on average. |
| Versioned table with the index, now: recall@10 | 0.974 | 100 queries, 20,589 rows visible now | The same question through the index that holds all 44,743 versions returns 9.7 of the 10 right answers on average. |
| Versioned table with the index, now: rows returned | 10.00 of 10 | 100 queries, 20,589 rows visible now | `LIMIT 10` came back with this many rows on average. Of the index's 10 nearest versions over all of history only 6.7 were visible now, so 10 rows means the search went on fetching versions until 10 passed the date filter. |
| Versioned table without the index, now: recall@10 | 1.000 | 100 queries, 20,589 rows visible now | With `IGNORE INDEX` the versioned table gives the exact answer, in 80 ms per search against 0.9 ms with the index. |
| Plain table, rows AS OF 2010-01-01: recall@10 | 0.999 | 100 queries, 1,542 rows visible AS OF 2010-01-01 | With only the 1,542 visible rows in the index, the index returns 10.0 of the 10 right answers on average. |
| Versioned table with the index, AS OF 2010-01-01: recall@10 | 0.963 | 100 queries, 1,542 rows visible AS OF 2010-01-01 | The same question through the index that holds all 44,743 versions returns 9.6 of the 10 right answers on average. |
| Versioned table with the index, AS OF 2010-01-01: rows returned | 10.00 of 10 | 100 queries, 1,542 rows visible AS OF 2010-01-01 | `LIMIT 10` came back with this many rows on average. Of the index's 10 nearest versions over all of history only 1.4 were visible AS OF 2010-01-01, so 10 rows means the search went on fetching versions until 10 passed the date filter. |
| Versioned table without the index, AS OF 2010-01-01: recall@10 | 1.000 | 100 queries, 1,542 rows visible AS OF 2010-01-01 | With `IGNORE INDEX` the versioned table gives the exact answer, in 53 ms per search against 4.7 ms with the index. |
| Plain table, rows AS OF 2020-01-01: recall@10 | 0.989 | 100 queries, 6,981 rows visible AS OF 2020-01-01 | With only the 6,981 visible rows in the index, the index returns 9.9 of the 10 right answers on average. |
| Versioned table with the index, AS OF 2020-01-01: recall@10 | 0.976 | 100 queries, 6,981 rows visible AS OF 2020-01-01 | The same question through the index that holds all 44,743 versions returns 9.8 of the 10 right answers on average. |
| Versioned table with the index, AS OF 2020-01-01: rows returned | 10.00 of 10 | 100 queries, 6,981 rows visible AS OF 2020-01-01 | `LIMIT 10` came back with this many rows on average. Of the index's 10 nearest versions over all of history only 2.9 were visible AS OF 2020-01-01, so 10 rows means the search went on fetching versions until 10 passed the date filter. |
| Versioned table without the index, AS OF 2020-01-01: recall@10 | 1.000 | 100 queries, 6,981 rows visible AS OF 2020-01-01 | With `IGNORE INDEX` the versioned table gives the exact answer, in 61 ms per search against 1.9 ms with the index. |

## Every setting

| Date | Rows visible | `mhnsw_ef_search` | Plain table recall@10 | Versioned + index recall@10 | Rows returned of 10 | Nearest 10 versions visible at the date | Plain ms | Versioned ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| now | 20,589 | 20 | 0.992 | 0.974 | 10.00 | 6.72 | 0.56 | 0.91 |
| now | 20,589 | 40 | 0.995 | 0.983 | 10.00 | 6.77 | 0.94 | 1.57 |
| now | 20,589 | 80 | 0.996 | 0.988 | 10.00 | 6.73 | 1.32 | 2.13 |
| now | 20,589 | 160 | 0.999 | 0.993 | 10.00 | 6.74 | 1.73 | 3.16 |
| now | 20,589 | 1000 | 1.000 | 0.997 | 10.00 | 6.77 | 4.61 | 10.50 |
| AS OF 2010-01-01 | 1,542 | 20 | 0.999 | 0.963 | 10.00 | 1.35 | 0.34 | 4.70 |
| AS OF 2010-01-01 | 1,542 | 40 | 1.000 | 0.972 | 10.00 | 1.35 | 0.41 | 6.13 |
| AS OF 2010-01-01 | 1,542 | 80 | 0.999 | 0.982 | 10.00 | 1.36 | 0.51 | 9.75 |
| AS OF 2010-01-01 | 1,542 | 160 | 0.999 | 0.989 | 10.00 | 1.37 | 0.66 | 17.51 |
| AS OF 2010-01-01 | 1,542 | 1000 | 1.000 | 1.000 | 10.00 | 1.38 | 1.17 | 69.47 |
| AS OF 2020-01-01 | 6,981 | 20 | 0.989 | 0.976 | 10.00 | 2.92 | 0.44 | 1.87 |
| AS OF 2020-01-01 | 6,981 | 40 | 0.997 | 0.989 | 10.00 | 2.91 | 0.59 | 2.55 |
| AS OF 2020-01-01 | 6,981 | 80 | 0.999 | 0.991 | 10.00 | 2.96 | 0.77 | 4.13 |
| AS OF 2020-01-01 | 6,981 | 160 | 0.999 | 0.996 | 10.00 | 2.94 | 1.14 | 6.62 |
| AS OF 2020-01-01 | 6,981 | 1000 | 0.999 | 1.000 | 10.00 | 2.98 | 2.82 | 27.22 |

- `mhnsw_ef_search`: how many candidates the index keeps while it searches; higher finds more and takes longer.
- Rows returned of 10: how many rows the `AS OF` search through the index gave back for `LIMIT 10`.
- Nearest 10 versions visible at the date: the index's 10 nearest versions over all of history (`FOR SYSTEM_TIME ALL`), and how many of them were visible at the date.
- Plain ms, Versioned ms: median time of one search through the index.

How MariaDB runs the versioned search (`EXPLAIN`, AS OF 2020-01-01):

- versioned table with the index: `[{"id": 1, "select_type": "SIMPLE", "table": "n", "type": "index", "possible_keys": null, "key": "embedding", "key_len": "4098", "ref": null, "rows": "10", "Extra": "Using where"}]`
- versioned table, IGNORE INDEX: `[{"id": 1, "select_type": "SIMPLE", "table": "n", "type": "ALL", "possible_keys": null, "key": null, "key_len": null, "ref": null, "rows": "30765", "Extra": "Using where; Using filesort"}]`
