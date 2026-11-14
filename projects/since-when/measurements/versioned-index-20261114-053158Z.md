# Vector index on a system-versioned table: recall of AS OF searches

- Command: `python -m gapfinder measure --versioned-index mine_a3 --note 'scratch server: Docker container limited to 3.5 GB of memory and 4 CPUs'`
- Run at 2026-11-14 05:31:58 UTC, code at commit `2b88d65`.
- Database `gapfinder` on `gapfinder-scratch-db:3306` (server host name `5c1a2b8cf41d`), MariaDB 11.8.9-MariaDB-ubu2404.
- Server settings: buffer pool 2,048 MB (memory for table data), vector cache 512 MB (`mhnsw_max_cache_size`, memory for vector indexes), `mhnsw_ef_search` 20 by default.
- Machine running the command: AMD Ryzen 5 2600 Six-Core Processor, 12 cores, 15,924 MB of memory. One-minute load average: 1.37 at the start, 2.89 at the end, on 12 cores.
- Note: scratch server: Docker container limited to 3.5 GB of memory and 4 CPUs
- Times are from one run on this machine; recall does not depend on load.

The experiment tables live in the private database `mine_a3`; `gapfinder` is only read.

- **Versioned table**: 50,393 versions of 20,837 passages from 1,487 topics, each with its 1024-number embedding and the real edit times as `row_start` and `row_end`, in one table `WITH SYSTEM VERSIONING` and a vector index (`M=16 DISTANCE=cosine`). Built in 59 s.
- **Sample**: every stored version of every embedded passage of the topics with `CRC32(wikidata_id) % 2 = 0`, about one topic in 2, so that the index fits the scratch server's shared vector cache next to `chunk_now`; `--one-in 1` copies everything
- **Plain tables**: for each date, an ordinary table with only the rows visible at that date and the same vector index. This is what the tool does today with `chunk_now`.
- **Queries**: at each date, the 100 visible passages with the lowest `CRC32(id)`; each asks for its 10 nearest passages (`ORDER BY VEC_DISTANCE_COSINE(...) LIMIT 10`).
- **Recall@10**: of the 10 truly nearest rows visible at the date (found by comparing with every row, `IGNORE INDEX`), the share a search returned. 1.00 is the exact answer.

## Headline figures (`mhnsw_ef_search` = 20, the server default)

| Figure | Value | Measured over | What it means |
|---|---:|---|---|
| Plain table, rows now: recall@10 | 0.993 | 100 queries, 20,589 rows visible now | With only the 20,589 visible rows in the index, the index returns 9.9 of the 10 right answers on average. |
| Versioned table with the index, now: recall@10 | 0.965 | 100 queries, 20,589 rows visible now | The same question through the index that holds all 50,393 versions returns 9.7 of the 10 right answers on average. |
| Versioned table with the index, now: rows returned | 10.00 of 10 | 100 queries, 20,589 rows visible now | `LIMIT 10` came back with this many rows on average. Of the index's 10 nearest versions over all of history only 6.7 were visible now, so 10 rows means the search went on fetching versions until 10 passed the date filter. |
| Versioned table without the index, now: recall@10 | 1.000 | 100 queries, 20,589 rows visible now | With `IGNORE INDEX` the versioned table gives the exact answer, in 80 ms per search against 0.9 ms with the index. |
| Plain table, rows AS OF 2010-01-01: recall@10 | 0.999 | 100 queries, 1,543 rows visible AS OF 2010-01-01 | With only the 1,543 visible rows in the index, the index returns 10.0 of the 10 right answers on average. |
| Versioned table with the index, AS OF 2010-01-01: recall@10 | 0.951 | 100 queries, 1,543 rows visible AS OF 2010-01-01 | The same question through the index that holds all 50,393 versions returns 9.5 of the 10 right answers on average. |
| Versioned table with the index, AS OF 2010-01-01: rows returned | 10.00 of 10 | 100 queries, 1,543 rows visible AS OF 2010-01-01 | `LIMIT 10` came back with this many rows on average. Of the index's 10 nearest versions over all of history only 1.4 were visible AS OF 2010-01-01, so 10 rows means the search went on fetching versions until 10 passed the date filter. |
| Versioned table without the index, AS OF 2010-01-01: recall@10 | 1.000 | 100 queries, 1,543 rows visible AS OF 2010-01-01 | With `IGNORE INDEX` the versioned table gives the exact answer, in 53 ms per search against 4.7 ms with the index. |
| Plain table, rows AS OF 2020-01-01: recall@10 | 0.990 | 100 queries, 6,982 rows visible AS OF 2020-01-01 | With only the 6,982 visible rows in the index, the index returns 9.9 of the 10 right answers on average. |
| Versioned table with the index, AS OF 2020-01-01: recall@10 | 0.981 | 100 queries, 6,982 rows visible AS OF 2020-01-01 | The same question through the index that holds all 50,393 versions returns 9.8 of the 10 right answers on average. |
| Versioned table with the index, AS OF 2020-01-01: rows returned | 10.00 of 10 | 100 queries, 6,982 rows visible AS OF 2020-01-01 | `LIMIT 10` came back with this many rows on average. Of the index's 10 nearest versions over all of history only 2.9 were visible AS OF 2020-01-01, so 10 rows means the search went on fetching versions until 10 passed the date filter. |
| Versioned table without the index, AS OF 2020-01-01: recall@10 | 1.000 | 100 queries, 6,982 rows visible AS OF 2020-01-01 | With `IGNORE INDEX` the versioned table gives the exact answer, in 61 ms per search against 2.0 ms with the index. |

## Every setting

| Date | Rows visible | `mhnsw_ef_search` | Plain table recall@10 | Versioned + index recall@10 | Rows returned of 10 | Nearest 10 versions visible at the date | Plain ms | Versioned ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| now | 20,589 | 20 | 0.993 | 0.965 | 10.00 | 6.71 | 0.57 | 0.89 |
| now | 20,589 | 40 | 0.995 | 0.971 | 10.00 | 6.69 | 0.83 | 1.43 |
| now | 20,589 | 80 | 0.997 | 0.984 | 10.00 | 6.71 | 1.10 | 1.88 |
| now | 20,589 | 160 | 0.998 | 0.989 | 10.00 | 6.74 | 1.50 | 3.09 |
| now | 20,589 | 1000 | 0.999 | 0.996 | 10.00 | 6.73 | 4.08 | 9.26 |
| AS OF 2010-01-01 | 1,543 | 20 | 0.999 | 0.951 | 10.00 | 1.36 | 0.35 | 4.74 |
| AS OF 2010-01-01 | 1,543 | 40 | 0.999 | 0.962 | 10.00 | 1.36 | 0.44 | 6.35 |
| AS OF 2010-01-01 | 1,543 | 80 | 1.000 | 0.969 | 10.00 | 1.38 | 0.54 | 9.01 |
| AS OF 2010-01-01 | 1,543 | 160 | 1.000 | 0.978 | 10.00 | 1.38 | 0.66 | 16.77 |
| AS OF 2010-01-01 | 1,543 | 1000 | 0.999 | 0.997 | 10.00 | 1.38 | 1.13 | 74.82 |
| AS OF 2020-01-01 | 6,982 | 20 | 0.990 | 0.981 | 10.00 | 2.92 | 0.42 | 1.99 |
| AS OF 2020-01-01 | 6,982 | 40 | 0.997 | 0.989 | 10.00 | 3.00 | 0.54 | 2.73 |
| AS OF 2020-01-01 | 6,982 | 80 | 1.000 | 0.992 | 10.00 | 2.98 | 0.73 | 4.48 |
| AS OF 2020-01-01 | 6,982 | 160 | 1.000 | 0.996 | 10.00 | 3.00 | 1.02 | 7.07 |
| AS OF 2020-01-01 | 6,982 | 1000 | 1.000 | 0.998 | 10.00 | 2.95 | 2.62 | 30.08 |

- `mhnsw_ef_search`: how many candidates the index keeps while it searches; higher finds more and takes longer.
- Rows returned of 10: how many rows the `AS OF` search through the index gave back for `LIMIT 10`.
- Nearest 10 versions visible at the date: the index's 10 nearest versions over all of history (`FOR SYSTEM_TIME ALL`), and how many of them were visible at the date.
- Plain ms, Versioned ms: median time of one search through the index.

How MariaDB runs the versioned search (`EXPLAIN`, AS OF 2020-01-01):

- versioned table with the index: `[{"id": 1, "select_type": "SIMPLE", "table": "n", "type": "index", "possible_keys": null, "key": "embedding", "key_len": "4098", "ref": null, "rows": "10", "Extra": "Using where"}]`
- versioned table, IGNORE INDEX: `[{"id": 1, "select_type": "SIMPLE", "table": "n", "type": "ALL", "possible_keys": null, "key": null, "key_len": null, "ref": null, "rows": "30519", "Extra": "Using where; Using filesort"}]`
