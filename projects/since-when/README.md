# Since When

Entry for MariaDB's "Wikipedia Through Time" challenge: for one topic, shows what the Finnish, Swedish and
English Wikipedia articles say differently, the date and the edit each difference began with, and the MariaDB
statement behind each screen, which the viewer can run. Built on MariaDB 11.8 system-versioned tables and
vector search.

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

    uv run ruff format --check && uv run ruff check && uv run ty check && uv run python -m unittest differences.test_differences gapfinder.test_wikitext gapfinder.test_live_sql && npm --prefix ui ci --silent && npm --prefix ui run check

The six tests that run the SQL presets skip without a database login; `docker compose run --rm app python -m unittest gapfinder.test_live_sql`
runs them against the scratch database. The torch and DuckDB wheels don't load on NixOS outside a container, so the
embedder and the loaders run in the image.

Dependencies are pinned in `uv.lock` and the image installs from it. `ty check` passes with 21 warnings, left in
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

The database is Since When's own: the scratch instance and the demo snapshot named in the
[handoff note](demo/HANDOFF.md). Nothing here deploys to the gap finder's live server.
