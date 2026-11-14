# Run button in the SQL panel (builder 2, branch `feat/mariadb-live-sql`)

The SQL panel can now run three preset statements on MariaDB. The viewer picks a topic, a date
and editions; the page shows the exact statement, the rows and the time measured on the server.
There is no free-text SQL anywhere: `POST /api/sql/run` takes a preset name and parameters,
validates them and fills fixed templates on the server. Contract: `docs/gap-finder/api.md`.

## Deep links

Each opens the panel with the preset chosen and its fields filled in. Running is one click on
**Run** (a link never runs a statement by itself). On scratch the page is `http://127.0.0.1:8378`;
after promotion the same paths work on `https://31-22-104-106.sslip.io`.

| Preset | Link | What to do |
| --- | --- | --- |
| Time travel + vector search | `/?sql=nearest,Q1412941,2026-10-24,fi,en` | Run. Change the second edition to Swedish and run again. |
| `system_versioning_asof` | `/?sql=asof,Q1412941,2026-10-22,sv` | Run, change the date to 2026-10-24, run again. The previous run stays below the new one, so the two texts sit one above the other. |
| `FOR SYSTEM_TIME ALL` | `/?sql=history,Q1412941,en` | Run. Every version of the first passage with `row_start` and `row_end`, newest first. |

To open the panel on top of a topic page, add the page's hash, e.g.
`/?sql=asof,Q1412941,2026-10-22,sv#/Q1412941/sv/fi/findings`.

Fallback topics: pick them in the Topic field, or put the id in the link (`Q736268` Finnish War,
`Q2457646` Diet of Porvoo), e.g. `/?sql=history,Q736268,en`.

## What depends on builder 1's data

Checked on scratch at 04:41 EET through port 8378; builder 1's per-revision load had not landed.

- **`asof`, 2026-10-22 against 2026-10-24** returns the same revision (53401727) and the same
  text on both dates. The word "fascist" shows up only once every revision of the Swedish article
  is loaded. The query itself needs nothing changed: it reads `chunk` at `ord = 0`.
- **`history`** shows the yearly snapshots (13 versions for Lapua Movement in English, 12 for
  Finnish War, 17 for Diet of Porvoo). With every revision loaded it shows every edit of the
  passage; the result is capped at 500 rows.
- **`nearest`, default date 2026-10-24** works now (59 rows fi to en and fi to sv for Lapua
  Movement, 31 and 31 for Finnish War, 17 fi to en for Diet of Porvoo, 2 to 11 ms). Only the date's
  meaning changes with the per-revision data.
- **Diet of Porvoo with Swedish in the pair returns 0 rows** in `nearest`: its Swedish passages
  have no embeddings on scratch. Use fi and en for that topic unless builder 1's load adds them.

## For the integrator: promotion to live

Nothing here was run on live.

1. **Create the SELECT-only user.** On the server, in the deploy directory (where `.env` is).
   The password goes into `.env` and reaches the database container by name, never as a value on
   a command line.

   ```bash
   grep -q '^DB_RO_PASSWORD=' .env || printf 'DB_RO_USER=gapfinder_ro\nDB_RO_PASSWORD=%s\n' \
     "$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')" >> .env
   set -a; . ./.env; set +a
   docker exec -i -e DB_RO_USER -e DB_RO_PASSWORD gapfinder-db-1 sh -c 'exec mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" -e "
     CREATE USER IF NOT EXISTS \"$DB_RO_USER\"@\"%\" IDENTIFIED BY \"$DB_RO_PASSWORD\" WITH MAX_STATEMENT_TIME 5;
     GRANT SELECT ON \`gapfinder\`.* TO \"$DB_RO_USER\"@\"%\";
     GRANT SELECT ON \`gapfinder\\_%\`.* TO \"$DB_RO_USER\"@\"%\";
     SHOW GRANTS FOR \"$DB_RO_USER\"@\"%\";"'
   ```

   The same as plain SQL:

   ```sql
   CREATE USER IF NOT EXISTS 'gapfinder_ro'@'%' IDENTIFIED BY '<password>' WITH MAX_STATEMENT_TIME 5;
   GRANT SELECT ON `gapfinder`.* TO 'gapfinder_ro'@'%';
   GRANT SELECT ON `gapfinder\_%`.* TO 'gapfinder_ro'@'%';
   ```

   `deploy.sh` makes a new database `gapfinder_<date>_<time>` on every deploy. The second grant is
   a name pattern, so it covers the database live serves now (`gapfinder_20261114_0136`) and every
   later one, and the user needs no change on the next deploy. I ran exactly this command in a
   throwaway `mariadb:11.8` container (`gapfinder-a2-dbtest`, removed): the user reads
   `gapfinder`, `gapfinder_20261114_0136` and `gapfinder_20261115_0900`, gets error 1142 on
   `gapfinderXother`, on `other` and on an `INSERT`, and `SELECT SLEEP(20)` is cut off after 5.2 s
   with error 1969 without any session setting.

2. **Give the API the user.** `projects/mariadb-wikipedia/deploy/compose.yaml` is outside my row,
   so this is a request: add two lines to the `api` service's `environment`.

   ```yaml
         DB_RO_USER: ${DB_RO_USER:-}
         DB_RO_PASSWORD: ${DB_RO_PASSWORD:-}
   ```

   With both empty the endpoint is off and the page shows no Run section, so the lines are safe to
   add before the user exists. Then `docker compose up -d api`.

3. **Check.** `curl -s https://31-22-104-106.sslip.io/api/sql/presets` says `"enabled": true`,
   and the three deep links above return rows.

No change is needed in `ui/serve.py`, `index.html` or the Caddy config: the two new paths are
under `/api/`.

## Evidence

All on scratch, API in `gapfinder-a2-api` (port 8377, 1500 MB cap, no embedding model loaded, no
call to `/api/search`), page in `gapfinder-a2-ui` (port 8378, proxying to it). I removed both
containers when I finished; this starts them again from a checkout of the branch:

```bash
M=~/junction2026-data/mariadb; R=$PWD
docker run -d --name gapfinder-a2-api --network gapfinder-scratch-net --memory 1500m --cpus 4 \
  -p 127.0.0.1:8377:8377 --env-file $M/scratch.env -e DB_HOST=gapfinder-scratch-db -e DB_PORT=3306 \
  -v $R/gapfinder:/app/gapfinder:ro -v $R/differences:/app/differences:ro -v $R/ui:/app/ui:ro \
  gapfinder-app:live-09f2a79 python -m gapfinder serve --port 8377
docker run -d --name gapfinder-a2-ui --network gapfinder-scratch-net --memory 512m \
  -p 127.0.0.1:8378:8378 -e GAPFINDER_API=http://gapfinder-a2-api:8377 \
  -v $R/ui:/app/ui:ro gapfinder-app:live-09f2a79 python ui/serve.py --port 8378
```

```bash
for t in gapfinder.test_live_sql gapfinder.test_wikitext differences.test_differences; do
  docker exec gapfinder-a2-api python -m unittest $t; done      # 15, 2 and 4 tests, all OK
```

`gapfinder/test_live_sql.py`:

- `Refused`: an unknown preset, SQL text sent as a field, a write, parameters carrying SQL (also a
  trailing newline after a valid id), extra fields and a body that is not JSON all get 400 before
  any connection is opened; the templates contain no write keyword.
- `Off`: without `DB_RO_USER` the presets say `enabled: false` and a run is 503.
- `OnTheDatabase` (skipped without `DB_RO_USER`): `SELECT SLEEP(20)` on the endpoint's connection
  is cut off with error 1969 after about 5 s and the endpoint answers 504; `UPDATE`, `DELETE`,
  `INSERT`, `CREATE` and `DROP` are each denied by MariaDB with error 1142; a 100 000-row select
  returns 500 rows; every preset returns rows for the three demo topics; `asof` sends the same
  statement text on two dates.

The same from the command line, as the read-only user on scratch:

```bash
ro() { docker exec gapfinder-scratch-db sh -c 'exec mariadb -u"$DB_RO_USER" -p"$DB_RO_PASSWORD" "$MARIADB_DATABASE" -e "$0"' "$1"; }
ro "SET SESSION max_statement_time = 5; SELECT SLEEP(20)"
# ERROR 1969 (70100) at line 1: Query execution was interrupted (max_statement_time exceeded)
ro "UPDATE finding SET status = status WHERE id = 0"
# ERROR 1142 (42000) at line 1: UPDATE command denied to user 'gapfinder_ro'@'localhost' for table `gapfinder`.`finding`
ro "DROP TABLE finding"
# ERROR 1142 (42000) at line 1: DROP command denied to user 'gapfinder_ro'@'localhost' for table `gapfinder`.`finding`
ro "SET SESSION sql_select_limit = 500; SELECT seq FROM seq_1_to_100000" | wc -l
# 501  (the header and 500 rows)
```

Without the read-only user (a second API container started without `DB_RO_*`, and the page in
fixture mode): `GET /api/sql/presets` says `enabled: false` (404 from the fixtures), the panel has
no Run section, a `?sql=` link opens the panel as it is today and the page drops `sql=` from the
address.

At 1280x720 the document does not scroll sideways (1280 of 1280 px); the result table scrolls
inside its box (258 px visible of 2015 px for the history preset).

Not run: the clean-room check (`python3 -m cleanroom check`). It calls `/api/search`, which loads
the embedding model, and it posts finding outcomes; both are outside what I may do on scratch.

## Decisions

- **Limits are set on the session, not with `SET STATEMENT … FOR`.** Each run opens its own
  connection as the read-only user and sends `SET SESSION time_zone = '+00:00',
  max_statement_time = 5, sql_select_limit = 500` first. That keeps preset 2's query free of any
  prefix, so "a plain query with no time clause" is literally what the page shows.
- **Row cap 500**, reported as `capped: true` when reached. At most 4 runs at a time; a fifth
  gets 429.
- **Statuses:** 400 invalid input, 503 no read-only user, 429 busy, 504 cut off by the time limit,
  502 any other refusal by the database. The 502 carries MariaDB's own message.
- **Binding.** Presets 2 and 3 bind their values with `?`. Preset 1 is the text `nearest_sql`
  builds; that function writes its arguments into the text, and binding them would mean editing
  `align.py` (builder 1's file). So preset 1 gets values that have already passed the same
  validation: a `Q<digits>` id, a real date between 2001-01-15 and today, editions from fi, sv, en.
- **The statement shown is the one sent**, with the bound values written in place of `?` so it
  can be pasted into a client.
- **Preset 2 returns `@@system_versioning_asof` as its first column**, so the row itself shows
  which point in time the session was at. The text is the first 320 characters of the article's
  first passage; there is no first-sentence column. Preset 3 shows the first 200.
- **Preset 3 lists newest first.** A `row_end` in 2106 is marked "current".
- **The Topic field** lists the three demo topics and the topic of the page that is open. Other
  ids work through the link.
- **The previous run of a preset stays below the newest**, for the before and after of preset 2.
- **`sql=` is in the address only while the panel is open** and the API can run statements.
- **Two files outside the three named places:** the test `gapfinder/test_live_sql.py` (the
  done-check asks for one, and it sits beside `test_wikitext.py`) and one sentence in
  `ui/README.md` about `sql=` in the address.
- **`WITH MAX_STATEMENT_TIME 5` on the live user** is an extra on top of the session setting: a
  session can raise its own limit, but the viewer never sends SQL, so only the API's fixed
  statements run.
