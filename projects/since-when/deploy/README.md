# Since When on the Verda machine

The public instance: <https://since-when.katalyst.fyi/> (also still on
<https://since-when.31-22-104-106.sslip.io/>). It runs on the shared machine `31.22.104.106` behind
the proxy in [`infra/verda/proxy`](../../../infra/verda/proxy/README.md), as its own compose project
with its own MariaDB.

Redeploy the committed code (from a checkout with SSH access to the machine):

    projects/since-when/deploy/deploy.sh

Load a database snapshot as well, into a new database the app then switches to (a `mariadb-dump --dump-history` of the scratch
database, such as the demo snapshot named in the [handoff note](../demo/HANDOFF.md)):

    projects/since-when/deploy/deploy.sh ~/junction2026-data/mariadb/snapshot-demo-20261114-0730/gapfinder.sql.zst

What the instance is:

- **Database:** MariaDB 11.8 in the same compose project, 2 GB of memory at most, loaded from the
  snapshot. Nothing rebuilds data on this machine.
- **Read-only:** `SINCE_WHEN_READ_ONLY=1` turns off `POST /api/findings/<id>/status`, the only
  endpoint that writes. The Run button uses a SELECT-only user with presets only, 5 seconds and
  500 rows.
- **No keys:** no API key is on the machine. With no embedding model there, search answers 503.
- **Passwords** are generated on the machine on the first run and stay in
  `/srv/katalyst/since-when/deploy/.env`.

The files land in `/srv/katalyst/since-when/`; the previous copy is kept beside it as
`since-when.old` until the next deploy.
