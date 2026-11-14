# Since When

Entry for MariaDB's "Wikipedia Through Time" challenge: for one topic, shows what the Finnish, Swedish and
English Wikipedia articles say differently, the date and the edit each difference began with, and the MariaDB
statement behind each screen, which the viewer can run. Built on MariaDB 11.8 system-versioned tables and
vector search.

Public instance: <https://since-when.katalyst.fyi/>.

It takes on both tracks of the challenge together. System-versioned tables hold every loaded version of
every article and passage with Wikipedia's real edit times, vector search pairs passages across the three
editions, and [one statement](#how-this-meets-the-brief) does both: the nearest passage in another edition,
as the two articles stood on a past date.

It started as a fork of the gap finder (root `gapfinder/`, `differences/`, `ui/`) at commit `689a26d` and
shares no files with it. The Python package names are unchanged.

- [`gapfinder/`](gapfinder/): loader, schema, and the FastAPI server for the API ([contract](docs/api.md)) and the app.
- [`differences/`](differences/README.md): classifies the differences between two passages with Nemotron.
- [`ui/`](ui/README.md): the app, in Svelte.
- [`deploy/`](deploy/README.md): the public instance on the Verda machine.
- [`demo/`](demo/HANDOFF.md): the handoff note, the [walkthrough script](demo/WALKTHROUGH.md) and the builders' notes.
- [`measurements/`](demo/measurements.md): recall and query times, with the runs they come from.

Run, from this directory on hestia, where the scratch database is (container `gapfinder-scratch-db`,
login in `~/junction2026-data/mariadb/scratch.env`):

    docker compose up --build -d                              # http://127.0.0.1:8078

One container serves the app and the API. Without Docker or a database, `npm --prefix ui run build` and then
`SINCE_WHEN_FIXTURES=1 uv run python -m gapfinder serve` serves the app on fixture data.

Test, from this directory in the repo's dev shell (`nix develop`, which has uv, Node and MariaDB Connector/C):

    uv run ruff format --check && uv run ruff check && uv run ty check && uv run python -m unittest differences.test_differences differences.test_claims differences.test_decide differences.test_figures gapfinder.test_wikitext gapfinder.test_live_sql gapfinder.test_evidence gapfinder.test_checked && npm --prefix ui ci --silent && npm --prefix ui run check

The six tests that run the SQL presets skip without a database login; `docker compose run --rm app python -m unittest gapfinder.test_live_sql`
runs them against the scratch database. The torch and DuckDB wheels don't load on NixOS outside a container, so the
embedder and the loaders run in the image.

Dependencies are pinned in `uv.lock` and the image installs from it. `ty check` passes with 33 warnings (21 are listed here; the claim check's modules added the rest), left in
place because the fix is a restructure or ty is wrong ([`pyproject.toml`](pyproject.toml) keeps them as warnings
per file, so a new finding still fails):

- `gapfinder/api.py` (12) and `gapfinder/test_live_sql.py` (2): `PRESETS` keeps a title, a parameter list and a
  function per preset in one dict, and the timeline's per-year rows are mixed dicts; `findings_sql` takes either
  a topic or a finding id and ty sees `int(None)`.
- `gapfinder/align.py` (3): `max` over dates read from database rows that ty types as possibly `None`, and
  `max(near, key=near.get)`.
- `gapfinder/embed.py` (1), `gapfinder/wikitext.py` (1): ty misreads `AutoTokenizer.from_pretrained` and
  `"…".join(map(re.escape, …))`.
- `differences/evaluate.py` (2), `demo/hero_classify.py` (2): precision and recall stored as `None` in a dict of
  counts, and a script that swaps `llm._post` and `llm.RETRIES` to count calls.

## The data

Since When runs on MariaDB's provided datasets for its topics and its Finnish history, and on our own fetch
for the Swedish and English history, which MariaDB does not provide.

| What | Where it comes from | How much is loaded |
| --- | --- | --- |
| Topics | [Dataset S](https://github.com/MariaDB/mariadb-wikipedia-datasets) (`s-2026-10`): the topics it has in Finnish, Swedish and English | 2,919 topics, all of them |
| Finnish history | Dataset M (`m-2026-10`): every Finnish version, 862,076 in all | 48,461 versions of 2,919 articles: the one current on each 1 January from 2005 to 2026, and the latest |
| Swedish and English history | Fetched from the Wikimedia API ([`fetch_history.py`](../../spikes/mariadb-wikipedia/fetch_history.py)), because dataset M is Finnish only | 25,394 Swedish versions of 2,369 articles and 34,664 English versions of 2,365, at the same dates |
| Every revision, not one a year | The same sources | The three demo topics: Lapua Movement, Finnish War, Diet of Porvoo |

In MariaDB that is 108,519 article versions and 225,816 passage versions in system-versioned tables, 39,330
passages current today, 60,594 passage texts with a bge-m3 vector (1,024 dimensions), and 1.18 GB in all.

Not used: dataset S's own vectors, which are one per article where Since When needs one per passage (same
model, bge-m3), and dataset L, all of Finnish Wikipedia today. L has one edition and no history, so there is
nothing in it for Since When to compare.

Loading from the provided datasets is what the pipeline does. From this directory:

    gh release download s-2026-10 -R MariaDB/mariadb-wikipedia-datasets -D data/mariadb/s
    gh release download m-2026-10 -R MariaDB/mariadb-wikipedia-datasets -D data/mariadb/m
    python -m gapfinder schema && python -m gapfinder load && python -m gapfinder embed

`load` also reads the Swedish and English fetch from `data/mariadb/history/`. Embedding on CPU is the slow
step. A full load was not timed in this project, and loading all 862,076 Finnish versions of M instead of
one a year has not been tried.

## How this meets the brief

The brief is [`docs/challenges/main/mariadb--wikipedia-through-time.md`](../../docs/challenges/main/mariadb--wikipedia-through-time.md).
Each line points at something to click or run; the links open the public instance with the statement filled
in, and nothing runs before **Run** is clicked.

- **Use of MariaDB vector search and system-versioned tables.** Both in one statement:
  [the nearest English passage for each Finnish one, as of 24 October 2026](https://since-when.katalyst.fyi/?sql=nearest,Q1412941,2026-10-24,fi,en#/Q1412941).
  Shortened to its two parts:

  ```sql
  WITH c AS (
    SELECT c.id, c.lang, c.ord, p.embedding
    FROM chunk FOR SYSTEM_TIME AS OF TIMESTAMP '2026-10-24 00:00:00' AS c
    JOIN passage AS p ON p.sha = c.sha
    WHERE c.wikidata_id = 'Q1412941' AND p.embedding IS NOT NULL
  ), d AS (
    SELECT x.id, x.ord, y.id AS other_id,
           VEC_DISTANCE_COSINE(x.embedding, y.embedding) AS distance,
           ROW_NUMBER() OVER (PARTITION BY x.id ORDER BY VEC_DISTANCE_COSINE(x.embedding, y.embedding)) AS rn
    FROM c AS x JOIN c AS y ON x.lang = 'fi' AND y.lang = 'en'
  )
  SELECT id, ord, other_id, distance FROM d WHERE rn = 1 ORDER BY ord
  ```

  Also [an article as it stood on a date](https://since-when.katalyst.fyi/?sql=asof,Q1412941,2022-05-31,en#/Q1412941)
  through `system_versioning_asof`, and
  [every version of a passage](https://since-when.katalyst.fyi/?sql=history,Q1412941,en#/Q1412941) with
  `FOR SYSTEM_TIME ALL`.
- **Technical execution and scalability across the provided datasets.** The topics are dataset S's and the
  Finnish history is dataset M's ([the data](#the-data)). [`demo/measurements.md`](demo/measurements.md) has
  the numbers and the runs behind them: recall@10 of 0.987 at `mhnsw_ef_search` 20 with a median index
  search of 0.56 ms over 39,330 passages, and a topic aligned as of 2010 in a median of 4.7 ms. It also
  records what did not scale: a vector index on a versioned table answers past dates 5 to 14 times slower
  than on a plain one, so the index stays on the current rows and a past date searches one topic exactly.
- **Usefulness for readers and editors.** A reader sees each edition's exact words side by side, and the
  date links to the Wikipedia edit that began the difference:
  [Lapua Movement](https://since-when.katalyst.fyi/#/Q1412941), where Swedish and English Wikipedia say
  "fascist" in the first sentence and Finnish does not. NVIDIA Nemotron 3.5 Super VL suggests the
  differences and then checks each one against the whole other article, and the page says so;
  [`demo/hero-findings-notes.md`](demo/hero-findings-notes.md) and [`demo/hero-verify-notes.md`](demo/hero-verify-notes.md)
  are the hand checks of how often they are right before and after, and
  [`demo/nvidia-submission.md`](demo/nvidia-submission.md) the text for NVIDIA's prize.
- **Design and demo quality.** The [front page](https://since-when.katalyst.fyi/) leads with three topics,
  each difference shows since when as a time strip, and the look is Wikipedia's own (Wikimedia Codex).
  [`demo/WALKTHROUGH.md`](demo/WALKTHROUGH.md) is the two-minute script, link by link.
- **Originality.** It reads Wikipedia across language editions instead of within one: what one edition says
  that another does not, and since which edit. [`docs/research/mariadb-wikipedia.md`](../../docs/research/mariadb-wikipedia.md)
  is the survey of existing tools it was chosen against.

The database is Since When's own: the scratch instance and the demo snapshot named in the
[handoff note](demo/HANDOFF.md). Nothing here deploys to the gap finder's live server.
