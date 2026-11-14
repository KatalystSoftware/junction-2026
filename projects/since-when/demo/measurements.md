# Measurements: notes for the integrator (builder 3)

Branch `feat/mariadb-measurements`. Code: `gapfinder/measure.py` and its options in
`gapfinder/__main__.py`. Result files: `projects/mariadb-wikipedia/measurements/`.

## The two commands to rerun on a quiet machine

Run from the checkout root. Both read the shared `gapfinder` database on scratch; the second
writes only `mine_a3`. Each saves `<kind>-<UTC time>.json` and `.md` under
`projects/mariadb-wikipedia/measurements/` and prints the file names. Tonight's runs carry
`--provisional`, which marks the times as taken on a loaded machine; leave it off on a quiet one.

```bash
M=~/junction2026-data/mariadb; R=$PWD
run() {  # run <container name> <measure options...>
  name=$1; shift
  docker run --rm --name $name --memory 1500m --network gapfinder-scratch-net \
    --env-file $M/scratch.env -e DB_HOST=gapfinder-scratch-db -e DB_PORT=3306 \
    -e GAPFINDER_COMMIT=$(git rev-parse --short HEAD) \
    -v $R/gapfinder:/app/gapfinder:ro -v $R/differences:/app/differences:ro -v $R/ui:/app/ui:ro \
    -v $R/projects/mariadb-wikipedia/measurements:/app/projects/mariadb-wikipedia/measurements \
    gapfinder-app:live-09f2a79 python -m gapfinder measure "$@" \
    --note "scratch server: Docker container limited to 3.5 GB of memory and 4 CPUs"
}

# 1. Recall and query times of the tool as it runs: about 40 s.
run gapfinder-a3-measure

# 2. The versioned-index experiment: about 2.5 min, of which 1 min builds the index.
docker exec -i gapfinder-scratch-db sh -c 'exec mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" -e "
  CREATE DATABASE IF NOT EXISTS mine_a3; GRANT ALL ON mine_a3.* TO \"$MARIADB_USER\"@\"%\";"'
( flock 9; run gapfinder-a3-versioned --versioned-index mine_a3 ) 9<$M/locks/heavy.lock
docker exec -i gapfinder-scratch-db sh -c 'exec mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" -e "
  DROP DATABASE IF EXISTS mine_a3"'
```

The experiment creates its four tables in `mine_a3` from the shared tables each time and drops
them at the end (`--keep` leaves them), so a fresh restore of the snapshot needs nothing else.
Docker here is rootless: run without `--user`, the files come out owned by you. The image has no
git, hence `GAPFINDER_COMMIT`.

Options added to `measure`: `--queries N` (default 100), `--runs N` (alignment timings per topic,
default 3), `--versioned-index DB`, `--one-in N` (default 2), `--keep`, `--out DIR`, `--note TEXT`,
`--provisional`.

## What was measured

All on scratch (MariaDB 11.8.9, buffer pool 2 GB, vector cache 512 MB, container capped at 3.5 GB
and 4 CPUs) with a one-minute load of about 13 on 12 cores. **Every time below is provisional**,
except in the next section.

### Rerun on a quiet machine (integrator, 07:31 EET, commit `2b88d65`)

Both commands, without `--provisional`, after the hero topics got their full history. One-minute
load 1.4 at the start of each; the index build raised it to 2.9 by the end of the second. Files
`measure-20261114-053142Z` and `versioned-index-20261114-053158Z`. **Quote these.**

| Figure | Value |
|---|---|
| `chunk_now` index, recall@10 at `mhnsw_ef_search` 20 / 40 / 80 / 160 | 0.987 / 0.993 / 0.995 / 0.997 |
| median time of an index search at 20 / 40 / 80 / 160 | 0.56 / 0.92 / 1.34 / 1.98 ms |
| exact search over the 39,330 rows of `chunk_now`, median | 91 ms |
| alignment of a topic now, median / slowest | 34 / 131 ms |
| alignment AS OF 2010-01-01, median / slowest | 4.7 / 59 ms |
| alignment AS OF 2020-01-01, median / slowest | 9.8 / 84 ms |

The versioned sample is larger than in runs 1 and 2, because half of the hero articles' revisions
are in it: 50,393 versions of 20,837 passages (was 44,743 of 20,835), index built in 59 s. Each
cell is recall@10, plain table / versioned table.

| `mhnsw_ef_search` | now (20,589 rows visible) | AS OF 2010-01-01 (1,543) | AS OF 2020-01-01 (6,982) |
|---:|---:|---:|---:|
| 20 (default) | 0.993 / 0.965 | 0.999 / 0.951 | 0.990 / 0.981 |
| 40 | 0.995 / 0.971 | 0.999 / 0.962 | 0.997 / 0.989 |
| 80 | 0.997 / 0.984 | 1.000 / 0.969 | 1.000 / 0.992 |
| 160 | 0.998 / 0.989 | 1.000 / 0.978 | 1.000 / 0.996 |
| 1000 | 0.999 / 0.996 | 0.999 / 0.997 | 1.000 / 0.998 |
| median time at 20, plain / versioned | 0.57 / 0.89 ms | 0.35 / 4.74 ms | 0.42 / 1.99 ms |
| median time at 1000, plain / versioned | 4.08 / 9.26 ms | 1.13 / 74.8 ms | 2.62 / 30.1 ms |
| versioned table without the index, median time | 80 ms | 53 ms | 61 ms |

10 of 10 rows everywhere and 1.000 without the index, as before. Against runs 1 and 2: recall at
the default setting is 0.95 to 0.98 (was 0.96 to 0.98; AS OF 2010 moved from 0.963 to 0.951, within
the tolerance below), the versioned index is 14 times slower AS OF 2010 and 5 times AS OF 2020 (was
14 and 4), and the tool's own exact alignment AS OF takes a median of 5 to 10 ms per topic (was 6
to 16 under load). The sections below keep the figures of runs 1 and 2 as written that night.

### `measure` (files `measure-20261114-025051Z`, `-025128Z`, `-031936Z`)

| Figure | Run 1, 02:50 UTC | Run 2, 02:51 | Run 3, 03:19 |
|---|---:|---:|---:|
| recall@10 at `mhnsw_ef_search` 20 / 40 / 80 / 160 | 0.987 / 0.993 / 0.995 / 0.997 | the same | the same |
| median time of an index search at 20 / 40 / 80 / 160 | 0.85 / 1.37 / 1.84 / 3.15 ms | 0.72 / 1.39 / 1.92 / 2.97 ms | 0.60 / 1.03 / 1.89 / 2.64 ms |
| exact search over the 39,330 rows of `chunk_now`, median | 138 ms | 141 ms | 95 ms |
| alignment of a topic now, median / slowest | 183 / 479 ms | 180 / 513 ms | 196 / 528 ms |
| alignment AS OF 2010-01-01, median / slowest | 5.9 / 95 ms | 7.2 / 90 ms | 6.4 / 69 ms |
| alignment AS OF 2020-01-01, median / slowest | 16.3 / 411 ms | 15.5 / 420 ms | 11.6 / 356 ms |

100 queries; 20 topics, 3 runs each. Recall is the same number in every run: the queries are
chosen by `CRC32(id)` and the index does not change between runs. It will move when builder 1's
load changes `chunk_now`.

### `measure --versioned-index mine_a3`

Sample: every stored version of every embedded passage of half the topics
(`CRC32(wikidata_id) % 2 = 0`): 44,743 versions of 20,835 passages from 1,487 topics, in one
system-versioned table with a vector index (built in 59 s). Beside it, for each date, a plain
indexed table holding exactly the rows visible at that date. 100 queries per date; each cell is
recall@10 against exact search over the rows of that date, plain table / versioned table.

Run 1, file `versioned-index-20261114-022539Z` (02:25 UTC, commit `313d722`):

| `mhnsw_ef_search` | now (20,589 rows visible) | AS OF 2010-01-01 (1,542) | AS OF 2020-01-01 (6,981) |
|---:|---:|---:|---:|
| 20 (default) | 0.990 / 0.972 | 0.997 / 0.975 | 0.992 / 0.973 |
| 40 | 0.995 / 0.979 | 0.999 / 0.983 | 0.999 / 0.984 |
| 80 | 0.997 / 0.984 | 0.999 / 0.989 | 0.999 / 0.987 |
| 160 | 0.999 / 0.993 | 1.000 / 0.995 | 1.000 / 0.994 |
| 1000 | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 0.999 |
| median time at 20, plain / versioned | 1.49 / 3.31 ms | 0.35 / 4.58 ms | 0.64 / 1.88 ms |
| median time at 1000, plain / versioned | 3.99 / 9.51 ms | 1.15 / 68.7 ms | 2.76 / 28.5 ms |
| versioned table without the index, median time | 74 ms | 47 ms | 59 ms |

The versioned query returned 10 of 10 rows for every query at every setting, and the versioned
table searched without the index (`IGNORE INDEX`) agreed with the plain table exactly (1.000).

Run 2, file `versioned-index-20261114-031555Z` (03:15 UTC, commit `f1c5c38`), tables rebuilt from scratch:

| `mhnsw_ef_search` | now (20,589 rows visible) | AS OF 2010-01-01 (1,542) | AS OF 2020-01-01 (6,981) |
|---:|---:|---:|---:|
| 20 (default) | 0.992 / 0.974 | 0.999 / 0.963 | 0.989 / 0.976 |
| 40 | 0.995 / 0.983 | 1.000 / 0.972 | 0.997 / 0.989 |
| 80 | 0.996 / 0.988 | 0.999 / 0.982 | 0.999 / 0.991 |
| 160 | 0.999 / 0.993 | 0.999 / 0.989 | 0.999 / 0.996 |
| 1000 | 1.000 / 0.997 | 1.000 / 1.000 | 0.999 / 1.000 |
| median time at 20, plain / versioned | 0.56 / 0.91 ms | 0.34 / 4.70 ms | 0.44 / 1.87 ms |
| median time at 1000, plain / versioned | 4.61 / 10.5 ms | 1.17 / 69.5 ms | 2.82 / 27.2 ms |
| versioned table without the index, median time | 80 ms | 53 ms | 61 ms |

Again 10 of 10 rows everywhere and 1.000 without the index.

**Tolerance: 0.015 on the versioned figures, 0.005 on the plain ones.** The two runs copy the same
44,743 rows and ask the same 100 questions, but each run builds its indexes anew, and the build
places every vector on a randomly drawn layer of the graph, so no two builds are the same index.
The largest difference between the runs is 0.012 (versioned, AS OF 2010, ef 20: 0.975 and
0.963, which is 12 neighbours out of 1,000) and 0.003 on the plain tables. The times at ef 20 of
run 1 include loading the index into memory; run 2 has the untimed warm-up and is the one to read.

## The remembered figure against the measured one

Remembered, from `spikes/mariadb-wikipedia/svt_vector_recall.py` (documented as MariaDB 11.8.6):
recall@10 of 0.99 on a plain table, **0.13 to 0.23** on a versioned table `AS OF` a past date,
0.24 to 0.30 with `mhnsw_ef_search` raised to 1000.

Measured tonight on real passages: **0.96 to 0.98 at the default setting, 0.99 at 160, 1.00 at
1000**, one to four points under a plain table that holds only the rows of that date. The query returns
10 of 10 rows. The finding as remembered does not reproduce. The measured number is the one for
the walkthrough.

Why they differ. I reran the spike script unchanged, and then put its data in a plain table:

| Spike script, unchanged (recall@10, 30 queries, ef 80) | plain, current | versioned, now | plain, 2012 | versioned AS OF 2012 | AS OF 2012, ef 1000 |
|---|---:|---:|---:|---:|---:|
| as documented in the spike | 0.99 | 0.17 to 0.22 | 0.98 to 0.99 | 0.13 to 0.23 | 0.24 to 0.30 |
| scratch, 11.8.9, vector cache 512 MB | 0.98 | 0.78 | 0.99 | 0.87 | 1.00 |
| throwaway 11.8.6, vector cache 512 MB | 0.99 | 0.84 | 0.98 | 0.89 | 0.99 |
| throwaway 11.8.6, vector cache 16 MB (MariaDB's default) | 0.99 | 0.43 | 0.98 | 0.32 | 0.40 |

| `measurements/cache_check.py`: the spike's 48,000 vectors in a table **without** versioning | ef 80, all rows | ef 80, `WHERE ver = 2` | ef 1000, all rows | ef 1000, `WHERE ver = 2` |
|---|---:|---:|---:|---:|
| throwaway 11.8.6, vector cache 512 MB | 0.75 | 0.85 | 0.99 | 0.99 |
| throwaway 11.8.6, vector cache 16 MB (MariaDB's default) | 0.49 | 0.43 | 0.52 | 0.49 |

What this shows:

1. The spike compares a plain index over 3,000 vectors with a versioned index over 48,000
   (3,000 ids, 16 versions each). A plain table of the same 48,000 vectors scores the same as
   the versioned one (0.75 to 0.85 at ef 80, 0.99 at ef 1000). The gap in the spike is the size
   of the index, not versioning.
2. Its vectors are random, 64 numbers each, and every version of an id is unrelated to the one
   before. Random vectors have no near neighbours, which is the hard case for this kind of index.
   Real passages, where an edit moves a vector slightly, score 0.96 to 0.98 at the default setting.
3. The collapse to 0.3 to 0.5, where even ef 1000 does not help, appears with the 16 MB default
   of `mhnsw_max_cache_size` and goes away at 512 MB, on the same MariaDB version, and it hits
   the table without versioning just the same (0.43 to 0.52). The settings
   of the server the spike first ran on were not recorded, so that this is what happened then is
   my inference. I did not establish why a too-small cache costs recall instead of only time.

What still holds for the tool's design, with figures from the run above:

- The index on a versioned table holds every version: 44,743 entries for 20,589 current passages
  in the sample, 2.2 times the size, against a vector cache that everything shares.
- The fewer rows are visible at the date, the more the search fetches and throws away: at the
  default setting 4.7 ms AS OF 2010 against 0.34 ms on a plain table of that date (14 times), 1.9
  against 0.44 ms AS OF 2020 (4 times). At ef 1000 it is 69 ms for 2010, slower than the 53 ms of
  searching the versioned table without the index. Of the index's 10 nearest over all of
  history, 1.4 were visible in 2010.
- Recall drops sharply, with or without versioning, when an index outgrows
  `mhnsw_max_cache_size` (the 16 MB rows of both tables), and an index that carries every
  version gets there sooner. The live server has 1,024 MB.
- The tool's own versioned query needs none of this: it compares the passages of one topic
  exactly, so its recall is 1.0 by construction, in a median of 6 to 16 ms per topic AS OF.

So the sentence for the walkthrough is no longer "the index returns wrong rows AS OF a past
date". It is: "an index on the versioned table works on 11.8.9 (0.95 to 0.98 recall at the default
setting) but carries every version and is 5 to 14 times slower for past dates; we keep the
index on the current rows and search one topic exactly for the past, which is exact and takes
milliseconds."

## Reproducing the spike checks

```bash
# the spike on scratch (1 min)
docker run --rm --name gapfinder-a3-spike --memory 1500m --network gapfinder-scratch-net \
  --env-file $M/scratch.env -e DB_HOST=gapfinder-scratch-db -e DB_PORT=3306 -e DB_NAME=mine_a3 \
  -v $R/spikes/mariadb-wikipedia:/spike:ro -w /spike gapfinder-app:live-09f2a79 python svt_vector_recall.py

# a throwaway 11.8.6 server; add --mhnsw-max-cache-size=536870912 after the image name for 512 MB
docker run -d --name gapfinder-a3-db1186 --memory 1g --network gapfinder-scratch-net \
  -e MARIADB_RANDOM_ROOT_PASSWORD=1 -e MARIADB_DATABASE=wikihistory -e MARIADB_USER=wikihistory \
  -e MARIADB_PASSWORD=wikihistory mariadb:11.8.6
# the spike against it (1 min at 512 MB, 3.5 min at 16 MB), then the plain-table check
docker run --rm --name gapfinder-a3-spike --memory 1500m --network gapfinder-scratch-net \
  -e DB_HOST=gapfinder-a3-db1186 -e DB_PORT=3306 \
  -v $R/spikes/mariadb-wikipedia:/spike:ro -w /spike gapfinder-app:live-09f2a79 python svt_vector_recall.py
docker run --rm --name gapfinder-a3-spike --memory 1500m --network gapfinder-scratch-net \
  -e DB_HOST=gapfinder-a3-db1186 -e DB_USER=wikihistory -e DB_PASSWORD=wikihistory -e DB_NAME=wikihistory \
  -v $R/projects/mariadb-wikipedia/measurements:/m:ro gapfinder-app:live-09f2a79 python /m/cache_check.py
docker rm -f gapfinder-a3-db1186
```

The `wikihistory` name and password are the spike's public defaults, used only for that container.

## Decisions

- **`--versioned-index DB` is an option of `measure`**, not a new subcommand: one entry in
  `__main__.py`. It refuses the database it reads from.
- **Sample: half the topics**, those with `CRC32(wikidata_id) % 2 = 0`, every stored version of
  every embedded passage: 44,743 vectors. The full copy would be about 90,000 vectors of 1,024
  numbers plus three plain copies, next to `chunk_now` in a 512 MB cache shared with three other
  builders. `--one-in 1` copies everything.
- **Dates**: now, 2010-01-01 and 2020-01-01, the same three in both commands. The plain-table
  figure beside each versioned one comes from a plain indexed table holding exactly the rows
  visible at that date, so both are asked the same question.
- **Queries are chosen by `CRC32(id)`**, not `RAND(1)` as before, so a second run asks the same
  questions whatever the row order. The figures of the old printout are therefore not comparable
  one to one.
- **Alignment time is the median of 3 runs per topic** (`--runs`), over the 20 topics with the
  most past dates aligned. The printed line now ends `over 20 topics, 3 runs each`; apart from
  that and the `saved ...` lines the output of plain `measure` is what it was.
- **One untimed search before timing**, so the first setting is not charged for loading the
  index into memory (the first run showed ef 20 slower than ef 40 for this reason). The first
  versioned-index file (commit `313d722`) predates this; its ef 20 times include the loading.
- **ef 1000 is added to the experiment** because the spike used it.
- **Files are named by kind and UTC time** and never overwritten. The Markdown is made from the
  JSON by `measure._markdown` and `measure._versioned_markdown`.
- **`--provisional` and `--note`** put the load warning and the container limits in the file;
  the load average at the start and end of the run is recorded either way.
- **Table sizes in MB are left out**: `information_schema` reported 0 for these tables.
- The index build and `cache_check.py` ran under `heavy.lock`. The default `measure` builds
  nothing and loads no model, so it ran without the lock.
- I pulled `mariadb:11.8.6` and ran it as `gapfinder-a3-db1186` (1 GB cap) to test the version
  the spike names. Removed at the end; the image stays on the machine.

## For the integrator

1. Rerun the two commands above on a quiet machine without `--provisional`, commit the new
   files, and quote the times from those.
2. These still state 0.13 to 0.23 as the finding and are outside my row:
   `spikes/mariadb-wikipedia/HACKING.md` lines 51 to 53, `docs/research/mariadb-wikipedia.md`
   lines 283 and 428, and the docstring of `spikes/mariadb-wikipedia/svt_vector_recall.py`.
3. Builder 1's new table `full_history` (`wikidata_id`, `lang`, `since`; empty at 03:19 UTC)
   already shows in run 3 with an empty description. Give it, and any other new table, a sentence
   in `TABLES` in `gapfinder/measure.py`; I did not guess at its meaning.
4. Row counts in the files are those at the time printed in each; builder 1 was loading.
