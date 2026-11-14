# Since When

Entry for MariaDB's "Wikipedia Through Time" challenge: for one topic, shows what the Finnish, Swedish and
English Wikipedia articles say differently, the date and the edit each difference began with, and the MariaDB
statement behind each screen, which the viewer can run. Built on MariaDB 11.8 system-versioned tables and
vector search.

It started as a fork of the gap finder (root `gapfinder/`, `differences/`, `ui/`) at commit `689a26d` and
shares no files with it. The Python package names are unchanged.

- [`gapfinder/`](gapfinder/): loader, schema and API ([contract](docs/api.md)).
- [`differences/`](differences/README.md): classifies the differences between two passages with Nemotron.
- [`ui/`](ui/README.md): the pages.
- [`demo/`](demo/HANDOFF.md): the handoff note, the [walkthrough script](demo/WALKTHROUGH.md) and the builders' notes.
- [`measurements/`](demo/measurements.md): recall and query times, with the runs they come from.

Run, from this directory on hestia, where the scratch database is (container `gapfinder-scratch-db`,
login in `~/junction2026-data/mariadb/scratch.env`):

    docker compose up --build -d                              # http://127.0.0.1:8078

Test, from this directory:

    docker compose run --rm api python -m unittest differences.test_differences gapfinder.test_wikitext gapfinder.test_live_sql

The database is Since When's own: the scratch instance and the demo snapshot named in the
[handoff note](demo/HANDOFF.md). Nothing here deploys to the gap finder's live server.
