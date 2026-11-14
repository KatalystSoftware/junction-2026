# Handoff: MariaDB walkthrough, Saturday 14 November 2026

Written by the integrator (builder 5) between 07:01 and 09:00 EET. Branch `demo/mariadb-overnight`.
All times are EET unless they say UTC. `M` is `~/junction2026-data/mariadb` on hestia.

## The two commands

**1. Open the walkthrough instance from a laptop.**

```sh
ssh -N -L 8078:127.0.0.1:8078 hestia
```

Then open <http://localhost:8078>. Port 8078 is enough: the pages pass `/api/*` on to the API.
The script to read aloud is [`WALKTHROUGH.md`](WALKTHROUGH.md).

**2. Promote the demo snapshot to live.** Read "Promote or not" below first: I recommend not
running it before the walkthrough.

```sh
sh projects/mariadb-wikipedia/demo/promote.sh --run
```

Run it from a checkout of this branch on hestia. Without `--run` it prints each action and changes
nothing. To go back:

```sh
sh projects/mariadb-wikipedia/demo/promote.sh --rollback --run
```

What `--run` changes on live (`31.22.104.106`):

- Copies into `~/promote/`: the snapshot (520 MB), its checksum, `code.tar` (`gapfinder/`,
  `differences/`, `ui/` and `deploy.sh`, `compose.yaml`, `Dockerfile` of this branch) and the
  script.
- Saves the name of the database live serves now in `~/promote/db-before` and the present code in
  `~/promote/code-before.tgz`, once.
- Unpacks `code.tar` over live's checkout, so `git status` there shows changed files.
- Appends `DB_RO_USER` and `DB_RO_PASSWORD` to the deploy `.env` and creates the database user
  `gapfinder_ro` (SELECT only, 5 second limit). The Run button needs it.
- Runs `deploy.sh` with the snapshot: builds the image, loads the snapshot into a new database
  `gapfinder_<UTC time>`, points the API at it, restarts the containers. `deploy.sh` keeps the new
  database and the one served until then, and drops the other `gapfinder_*` databases. Today that
  drops `gapfinder_20261114_0411`.
- Checks that `/api/sql/presets` says `"enabled": true` and runs `hero-history-check.sh` on live.

What `--rollback --run` does: restores the code from `code-before.tgz`, sets `DB_NAME` back to the
name in `db-before`, runs `deploy.sh` without a snapshot. The promoted database, the `gapfinder_ro`
user and the two `.env` lines stay.

The brief named `gapfinder_20261114_0136` as the database to go back to. It no longer exists on
live, so the rollback goes to whatever live served at the moment of promotion.

**The script has never run on live.** Checked: `sh -n`, shellcheck, the dry run, `bash -n` on the
part that runs on live, and the copy steps of an earlier version against a stand-in for ssh in
`/tmp`. Not checked, because live is read-only for me: that `$M/bin/live-ssh` reaches live, that
the API container on live was started from `projects/mariadb-wikipedia/deploy` (the script stops
if not), and that live has room for 520 MB plus a second database. The copy and the load are not
timed; restoring the same amount on hestia took 141 s.

## State

### What works on scratch

The instance runs in two containers, `gapfinder-demo-api` (8077) and `gapfinder-demo-ui` (8078),
both bound to `127.0.0.1`, both `--restart unless-stopped`, reading the scratch database
(`gapfinder-scratch-db`, database `gapfinder`). They mount this worktree read-only
(`~/.t3/worktrees/junction2026/t3-9fef3258`), so the worktree must stay where it is until after
the walkthrough.

| What | Where | Checked with |
| --- | --- | --- |
| Lapua Movement findings, first sentences of three editions | <http://localhost:8078/#/Q1412941/sv/en/findings> | browser, screenshot 1 |
| The four dates of the first-sentence finding: Swedish gains "fascist" in 59790252 on 2026-10-23; English drops it in 294882000 on 2009-06-07, restores it in 1090675024 on 2022-05-30, gains "pro-Nazi" in 1347550072 on 2026-04-07 | <http://localhost:8078/#/Q1412941/sv/en/timeline> | browser and `/api/topics/Q1412941/timeline?lang=sv&rich_lang=en` |
| Every revision of the three hero topics, 54 compare views, 8 first sentences | all routes of the three topics | `sh projects/mariadb-wikipedia/demo/hero-history-check.sh http://127.0.0.1:8078` (rc 0 at 07:37) |
| Run button, three presets, SELECT-only user, 5 s and 500 rows | <http://localhost:8078/?sql=asof,Q1412941,2026-10-22,sv#/Q1412941/sv/en/findings> | `curl http://127.0.0.1:8078/api/sql/presets` says `"enabled": true`; screenshot 2 |
| Shortlist of 17 findings, each opens in the tool | links in [`hero-findings.md`](hero-findings.md) | each tool id fetched from `/api/topics/<qid>`: exists, open, right pair, quote matches; 0 problems |
| Every quote of the shortlist is in the article text | | `nix develop -c python3 projects/mariadb-wikipedia/demo/check_quotes.py --offline`: 51 of 51 quotes pass |
| Fallback topics | links in `WALKTHROUGH.md`, "Fallback" | each link opened, row counts in the script |

Search (`/api/search`) is not part of this instance: the API container has no embedding model. The
pages never call it; do not open it by hand, it would start a 2.2 GB download.

Screenshots (outside git):
`~/junction2026-data/mariadb/screenshots/01-first-step-lapua-findings.png` and
`~/junction2026-data/mariadb/screenshots/02-run-panel-asof.png`.

If a container is gone, start it again from the repo root of this worktree:

```sh
R=$(git rev-parse --show-toplevel); M=$HOME/junction2026-data/mariadb
docker run -d --name gapfinder-demo-api --restart unless-stopped --network gapfinder-scratch-net \
  --memory 1500m --cpus 4 -p 127.0.0.1:8077:8077 --env-file $M/scratch.env \
  -e DB_HOST=gapfinder-scratch-db -e DB_PORT=3306 \
  -v $R/gapfinder:/app/gapfinder:ro -v $R/differences:/app/differences:ro -v $R/ui:/app/ui:ro \
  gapfinder-app:live-09f2a79 python -m gapfinder serve --port 8077
docker run -d --name gapfinder-demo-ui --restart unless-stopped --network gapfinder-scratch-net \
  --memory 512m -p 127.0.0.1:8078:8078 -e GAPFINDER_API=http://gapfinder-demo-api:8077 \
  -v $R/ui:/app/ui:ro gapfinder-app:live-09f2a79 python ui/serve.py --port 8078
```

### Demo snapshot

| | |
| --- | --- |
| Path | `~/junction2026-data/mariadb/snapshot-demo-20261114-0730/gapfinder.sql.zst` |
| Taken | 07:30:34 to 07:30:48, right after the check script passed |
| Size | 544,577,548 bytes |
| sha256 | `4934f2dbcb29ea4c69be56aa6560ceb4faaac69e1e1fd529fb112b25443e5fdd` (also in `SHA256SUMS` beside it) |

Dumped with history (`--dump-history`), like the 03:54 snapshot. The only thing written to the
scratch server after it is the measurement rerun's private database `mine_a3`, dropped again.

Two more snapshots, to go back on scratch:

- Scratch before my writes: `$M/snapshot-scratch-20261114-0708/gapfinder.sql.zst`, sha256
  `aee797839a0ba72932c88afd7946d0c4710dee88e26491cb5e71395836838b9c`.
- Live as dumped at 03:54: `$M/snapshot-live-20261114-0354/gapfinder.sql.zst`, sha256
  `8984a0d0c68a3abc0ce07288aaa8b40643b7f9a53cd3f1eca5d2c49606b9432e`.

### Branches merged

Onto `origin/main` at `ce7ab73`, in this order, then `origin/main` at `133de93` on top:

| Branch | Head | Builder's notes |
| --- | --- | --- |
| `feat/mariadb-hero-history` | `e1a318d` | [`hero-history.md`](hero-history.md) |
| `feat/mariadb-live-sql` | `2632b78` | [`live-sql.md`](live-sql.md) |
| `feat/mariadb-measurements` | `745bacf` | [`measurements.md`](measurements.md) |
| `feat/mariadb-hero-findings` | `c5a914f` | [`hero-findings-notes.md`](hero-findings-notes.md) |

### Tests, on the merged branch at 07:37

- Unit tests: `Ran 24 tests in 11.181s`, `OK`. Run in the app image, because the nix shell has
  neither `mwparserfromhell` nor `mariadb`, so `nix develop -c python3 -m unittest …` fails on
  import:

  ```sh
  docker run --rm --network gapfinder-scratch-net --env-file $M/scratch.env \
    -e DB_HOST=gapfinder-scratch-db -e DB_PORT=3306 \
    -v $R/gapfinder:/app/gapfinder:ro -v $R/differences:/app/differences:ro -v $R/ui:/app/ui:ro \
    -w /app --memory 1500m gapfinder-app:live-09f2a79 \
    python -m unittest differences.test_differences gapfinder.test_wikitext gapfinder.test_live_sql
  ```

- CI lint, both rc 0: `nix run nixpkgs#shellcheck -- scripts/*.sh spikes/*/*.sh` and
  `nix develop -c python3 -m compileall -q spikes gapfinder differences ui projects`.
  `promote.sh` also passes shellcheck. Builder 1's `hero-history-check.sh` and
  `hero-history-run.sh` get one warning and a few notes; CI does not lint that folder and I left
  them.
- UI checks: `ui/README.md` lists none. I opened every link of `WALKTHROUGH.md` in a browser
  instead.

### How the scratch data was made

On the 03:54 snapshot of live, builders 1 and 4 loaded every revision of the three hero topics
and the classifier's findings. I then redid the findings and their dates with the merged code,
from the repo root:

```sh
R=$(git rev-parse --show-toplevel); M=$HOME/junction2026-data/mariadb
run=projects/mariadb-wikipedia/demo/hero-history-run.sh
app="--network gapfinder-scratch-net --env-file $M/scratch.env -e DB_HOST=gapfinder-scratch-db -e DB_PORT=3306
  -v $R/gapfinder:/app/gapfinder:ro -v $R/differences:/app/differences:ro -v $M/classify:/classify:ro
  --memory 1500m gapfinder-app:live-09f2a79"

sh $run schema 1500m gapfinder schema
docker run --rm --name gapfinder-demo-pairs $app \
  python -m gapfinder pairs --only Q1412941 Q736268 Q2457646 > $M/classify/agent4/pairs.jsonl
nix develop -c python3 projects/mariadb-wikipedia/demo/hero_classify.py nemotron $M/classify/agent4/pairs.jsonl --offline
echo "delete from difference where wikidata_id in ('Q1412941','Q736268','Q2457646') and source in ('llm','both')" | $M/bin/scratch-sql
docker run --rm --name gapfinder-demo-load $app \
  python -m gapfinder findings load /classify/nemotron/differences.jsonl
echo "DELETE FROM coverage WHERE wikidata_id IN ('Q1412941','Q736268','Q2457646') AND NOT is_current" | $M/bin/scratch-sql
sh $run align 1500m gapfinder align --only Q1412941 Q736268 Q2457646
```

No model was called: `--offline` replays the Nemotron answers from the disk cache, and no pair
was left uncached.

## What was cut

Mine:

- **The promotion was not run** (by the rules), and its last version was never run end to end,
  even against the stand-in.
- **The revisions load was not rerun with the merged code.** The articles, passages and vectors
  on scratch are builder 1's load from their branch. All 174 current passages of the hero topics
  hash the same with the merged cleaner, so the texts agree; a rerun would have left 818
  historical passages waiting for the model.
- **Extra 4, proving the replay on a fresh restore of the 03:54 snapshot, was not run.** The
  commands above ran on the scratch database as the builders left it, not on a fresh restore.
- **The word list was not rerun for the hero topics** (builder 1's note): findings 13303 and 13087
  keep year-bounded dates.
- **The tool prints two bounds for a date** ("between revision A and revision B"), not "on 23
  October 2026" (builder 1's note). The walkthrough says the date aloud.

Builders', from their notes:

- Builder 1 (`hero-history.md`): the history ends at the revision current in the snapshot, later
  revisions are in the files and not in the database; no UI checks.
- Builder 2 (`live-sql.md`): the clean-room check was not run by the builder; I ran it as extra 2
  (below).
- Builder 3 (`measurements.md`): why a too-small vector cache costs recall and not only time is
  not established; table sizes in MB are left out (`information_schema` reported 0).
- Builder 4 (`hero-findings-notes.md`, "Left out of the shortlist, and spares"): rows the
  classifier got wrong (Lapua "five or three years" and November 1930 or 1929; the Porvoo pledge
  dates) and spare findings for the Finnish War (Vaasa 1,000 or 1,100; the retreat 8,000 or
  7,000; Moore's force, which quotes the wrong English sentence).

Extras:

- Extra 3, the quiet measurement rerun: done at 07:31 with load 1.4, in `measurements.md`, "Rerun
  on a quiet machine".
- Extra 1, the three places that quote 0.13 to 0.23: done in commit `aa8f137` (see "The recall
  correction").
- Extra 2, the clean-room check: run at 07:46 to 07:54, without `--write`. **203 passed, 8 failed,
  4 warnings.** None stops the walkthrough; one is visible on its first screen. See "The clean-room
  check" below.
- Extra 4: cut (above).

### The clean-room check

Report: `~/junction2026-data/mariadb/checks/cleanroom-integrator-20261114-0545Z/check.md` (and
`check.json`), outside git. The report has no blocker or major levels, only pass, fail and warning;
the reading of each failure below is mine.

The 8 failures:

- **The English first sentence of the Lapua Movement is not word for word what Wikipedia shows**
  (2 failures: 5 of 275 quotes are near and not exact in the revision they cite, 4 of 273 are in no
  passage of the compare view). Findings 13069, 13095, 13303 and 13602 quote "The Lapua Movement
  (Lapuan liike) was a radical Finnish nationalist, fascist, pro-Nazi and …". Wikipedia, and the
  tool's own lead text, read "The Lapua Movement (Finnish: Lapuanliike or Lapuan liike, Swedish:
  Lapporörelsen) was a radical …". Only the parenthesis differs; "fascist" and "pro-Nazi" are
  there. This is the English card of the walkthrough's step 1. Not fixed: it needs a change in how
  the first sentence is cleaned and a reload of the findings. Finding 13072 (closed) differs the
  same way at 94%.
- **Dates that are not a 1 January** (3 failures: 246 of 258 Lapua findings, 51 of 57 and 136 of
  145 timeline events). The check expects each date to be bounded by a yearly snapshot
  (`cleanroom/check.py`, line 61). The hero topics now hold every revision, so the bound is the day
  before the edit. The check is behind the data, not the other way round. One row I did not look
  into: the timeline event for finding 13069 on 2004-06-22 links a Finnish diff "None→24037" that
  the check says is not of this article.
- **Swedish lead text of the Winter War and the Continuation War** is near and not exact in the
  revision it cites (87% and 96%; 2 failures). Not hero topics, not in the walkthrough.
- **Search returns a result for nonsense** ("zzzzqqq xkcdvw" gives "Runestone U 582"; 1 failure).
  Search has no distance limit. Not in the walkthrough.

The 4 warnings: one queue row names the smaller edition as the richer one (Alexander III of
Russia); for 16 of 258 Lapua findings and 6 of 49 Winter War findings the quote was not in the
edition on the day the finding is said to have opened, so the quote cannot confirm the date; and 12
of 59 search answers carry fewer rows than their SQL counts (search only).

How it was run, from `projects/mariadb-wikipedia`, under the heavy lock. The search checks load the
embedding model, and the walkthrough API has neither the model nor the memory for it, so the check
ran against a second API on port 8079 with the same code and the same scratch database, removed
afterwards:

```sh
R=$(git rev-parse --show-toplevel); M=$HOME/junction2026-data/mariadb
docker run -d --name gapfinder-cleanroom-api --network gapfinder-scratch-net --memory 3g --cpus 4 \
  -p 127.0.0.1:8079:8079 --env-file $M/scratch.env -e DB_HOST=gapfinder-scratch-db -e DB_PORT=3306 \
  -v $R/gapfinder:/app/gapfinder:ro -v $R/differences:/app/differences:ro -v $R/ui:/app/ui:ro \
  -v gapfinder-scratch-models:/models gapfinder-app:live-09f2a79 python -m gapfinder serve --port 8079
CLEANROOM_CACHE=$M/checks/cleanroom-wiki-cache nix develop $R -c python3 -m cleanroom check \
  --base http://127.0.0.1:8079 --out $M/checks/cleanroom-integrator-20261114-0545Z
docker rm -f gapfinder-cleanroom-api
```

## Open choices for Mikael

### Promote or not

**My recommendation: show the walkthrough from hestia through the tunnel and do not promote
before it.**

Live moved on during the night. At 07:33 (SELECTs through `$M/bin/live-sql` with
`LIVE_DB=gapfinder_20261114_0448`, and GETs):

- Live serves `gapfinder_20261114_0448`, created at 06:49. `gapfinder_20261114_0411` (06:11) is
  beside it. `gapfinder_20261114_0136`, which scratch was copied from, is gone.
- Live has no Run button (`/api/sql/presets` is not there), no `gapfinder_ro` user and no
  `full_history` table.
- Live has more data than the demo snapshot:

  | | Live `…_0448` | Demo snapshot |
  | --- | ---: | ---: |
  | Topics | 2,919 | 2,919 |
  | Topics with coverage | 2,919 | 2,369 |
  | Articles (current) | 8,752 | 7,653 |
  | Current passages (`chunk_now`) | 45,664 | 39,330 |
  | Passages with a vector | 101,306 | 60,594 |
  | Findings (current rows) | 15,268 | 11,082 |
  | Rows in `difference` | 2,110 | 813 |

So promoting swaps live's data of 06:49 for the data of 03:54 plus the hero work: the three hero
topics gain their full history and the Run button, and 550 topics lose their coverage. The
rollback brings the 06:49 data back.

The other way is to replay the hero work onto live's current database (builder 1's "Rebuild"
steps, then the commands under "How the scratch data was made"). That needs writes on live and
the embedding model for whatever live's cleaner made differently, so it was not mine to do.

### Hero topic

- **Lapua Movement** (`Q1412941`): one word, four dated edits, the Swedish one three weeks old.
  `WALKTHROUGH.md` is written for it.
- **Finnish War with the Diet of Porvoo** (`Q736268`, `Q2457646`): dates that disagree between
  editions (Sveaborg 3 or 6 May 1808; three sets of dates for the diet). The fallback section of
  `WALKTHROUGH.md` has its links and its opening sentence.

### Name

"Since When", picked by Mikael on the morning of 14 Nov. Applied to the UI title and the walkthrough
script only; no code renames. The other options were "Wiki Ledger" and "Rinnakkain".

## The recall correction

The research note, `HACKING.md` and the spike's docstring said a vector index on a
system-versioned table has recall 0.13 to 0.23. **As a claim about versioning this is wrong.**
All three are corrected on this branch and point to `measurements.md`:
`docs/research/mariadb-wikipedia.md` (moment 3 and "Biggest risk"),
`spikes/mariadb-wikipedia/HACKING.md` and the docstring of
`spikes/mariadb-wikipedia/svt_vector_recall.py`. Main still has the old text.

What the measurement found (`measurements.md`; figures from the quiet rerun at 07:31):

- The spike compared a plain index over 3,000 vectors with a versioned one over 48,000, on random
  vectors of 64 numbers. The collapse appears when `mhnsw_max_cache_size` is 16 MB, also without
  versioning, and is gone at 512 MB. Live has 1,024 MB.
- On our data (50,393 versions of 20,837 passages, MariaDB 11.8.9), the index on the versioned
  table has recall@10 of 0.95 to 0.98 at the default `mhnsw_ef_search` of 20, against 0.99 to
  1.00 for an index on the current rows only. At 1000 both are above 0.995.
- It costs time for past dates: 4.74 ms against 0.35 ms as of 2010 (14 times), 1.99 ms against
  0.42 ms as of 2020 (5 times), because the index holds every version and the past rows are
  filtered afterwards.
- The exact search of one topic as of a date, which the tool uses, takes a median of 5 to 10 ms.

The sentence to say:

> An index on the versioned table works on 11.8.9, with recall of 0.95 to 0.98 at the default
> setting, but it carries every version and is 5 to 14 times slower for past dates. We keep the
> index on the current rows and search one topic exactly for the past, which is exact and takes
> milliseconds.

## Decisions

### The integrator's

1. **Merged onto current main, not onto `09f2a79`.** Main at 07:01 was `ce7ab73`. Two merges
   needed a hand: `load_article` in the hero-history merge (it takes builder 1's pre-split
   versions and keeps main's `edition=lang` for every other topic; commit `be30545`) and
   `gapfinder/__main__.py` in the measurements merge. At 07:35 I merged main again (`133de93`):
   its one change under the tool's folders is `gapfinder/embed.py` (workers reconnect after a
   dropped connection), and without it a promotion would have taken that fix away from live.
2. **Live's state decides the promotion advice** (above). `promote.sh` records the database live
   serves at promotion instead of naming one.
3. **`promote.sh` ships code with `git archive`** and finds live's deploy directory from the
   compose label of `gapfinder-api-1`, so it needs no git access on live and no path written down.
4. **Tests run in the app image**, shellcheck through `nix run nixpkgs#shellcheck` (hestia has
   neither `python3` nor `shellcheck` outside nix).
5. **A snapshot of scratch before my first write** (path above).
6. **Findings redone with the merged code, articles not** (see "What was cut"). I ran `align`
   after `findings load`, as builder 1's note asks.
7. **The regenerated `pairs.jsonl` and `differences.jsonl` are byte-identical** to builder 4's.
   The files before my run are beside them as `*.before-integrator.jsonl`.
8. **Main's block that dates findings again in `_difference_findings` stays as merged**: the four
   Lapua dates come out right with it.
9. **`revisions._passages` stays without an edition argument**, as builder 1 wrote it. Main's
   cleaner then gives the same text as scratch for all 174 current passages of the hero topics;
   with `edition=lang` the Swedish introduction of the Finnish War changes, and the classifier
   and embedding caches would no longer match.
10. **The counts of dated periods differ a little from builder 1's notes** after my rerun: Lapua
    Movement 265 periods (240 open), Diet of Porvoo 118 (109), Finnish War 379 (365). Their notes
    keep their figures.
11. **The ordinary `gapfinder load` does not skip topics listed in `full_history`.** Running it
    on a hero topic would write year-end versions over the full history. Not changed.
12. **Containers are named `gapfinder-demo-api` and `gapfinder-demo-ui`**; the API is on 8077
    though only 8078 needs forwarding.
13. **Shortlist links point at `http://localhost:8078`**, and finding 1's note says the dates now
    show in the tool.
14. **The walkthrough opens on the Swedish and English pair**, so all four dates are on one
    timeline. Its `?sql=` links carry the topic after `#`, so the Lapua page stays behind the
    panel.
15. **The `asof` preset shows time travel through `system_versioning_asof`**; the literal `FOR
    SYSTEM_TIME AS OF` with `VEC_DISTANCE_COSINE` is in the `nearest` preset. The walkthrough
    shows both.
16. **The fallback's step 3 uses the Finnish War** (English, 2026-04-25 to 2026-04-26): the Diet
    of Porvoo's Swedish first passage reads the same on both sides of its edit.
17. **The demo snapshot was taken before the measurement rerun**, which writes only its own
    database.
18. **The walkthrough's measurement figures follow the quiet rerun** ("about 0.97", "5 to 14
    times"), not the builder's provisional runs.
19. **The clean-room check ran against a temporary API on port 8079** (3 GB, with the model
    volume, under the heavy lock), not against the walkthrough instance, which has no model. Same
    code, same database. The container is removed.
20. **The clean-room failure on the English first sentence is recorded, not fixed.** A fix changes
    the cleaner and reloads the hero findings an hour before the walkthrough.

### The builders'

Each is in the notes' "Decisions" section: `hero-history.md` (14), `live-sql.md`,
`measurements.md`, `hero-findings-notes.md`.

### The orchestrator's

- Builders started from `09f2a79`, because live was redeployed at 03:36.
- One shared rules file (`$M/BUILDERS.md`) fixed ports, container prefixes and which scratch
  tables each builder writes.
- A lock for heavy jobs (`$M/locks/heavy.lock`), because hestia had 4.4 GB available at 04:14,
  less than the 9 GB assumed.
- Builder deadline 07:15/07:30; the integrator started at 07:00 once all four had pushed.
- Scratch holds live's database `gapfinder_20261114_0136` as dumped at 03:54, with history.
- Builders 1 and 4 both wrote findings for the same topics. Builder 4's loads reverted builder
  1's dates three times, so the integrator redid the dating with the merged code.
- The 0.13 to 0.23 references are corrected on the demo branch only.
- `feat/gap-kinds` stayed out; no folders moved; live was not redeployed.
