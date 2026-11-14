# Since When HTTP API

The contract between the data service (`gapfinder/`), the UI (`ui/`) and the differences
classifier (`differences/`). JSON over HTTP, all paths under `/api`. One FastAPI
server answers `/api/*` and serves the built app (`ui/dist/`) on the same origin, so it sends no
CORS headers. The routes are listed at `/api/docs`.

Run it from `projects/since-when/`:

```sh
python -m gapfinder serve --port 8078
```

With `SINCE_WHEN_FIXTURES=1` it needs no database: the queue, a topic and its timeline are answered
from `ui/fixtures/` with `"fixture": true`, and search and status changes answer 503.

With `SINCE_WHEN_READ_ONLY=1`, as on the public instance, status changes answer 403.

It reads `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` and `DB_NAME` from the environment
(defaults: `127.0.0.1`, `3306`, `gapfinder`, `gapfinder`, `gapfinder`). `DB_RO_USER` and
`DB_RO_PASSWORD` name a SELECT-only user for `POST /api/sql/run`; without them that endpoint is
off and everything else works as before.

## Conventions

- **Editions** are `fi`, `sv` and `en`. A topic is a Wikidata item (`Q1412941`) that has an
  article in all three.
- **Dates** are UTC. `as_of` is `YYYY-MM-DD` and means 00:00:00 UTC on that day. History exists
  for each 1 January from 2005 to 2026 plus the current text; other dates return the text that
  was current then.
- **`sql`**: every response carries the queries that produced it, for the SQL panel:
  `[{"label": str, "query": str, "ms": number, "rows": int}]`. `query` is the exact text sent to
  MariaDB with the parameters filled in.
- **Errors**: `{"error": str}` with status 400 (bad parameter) or 404 (unknown topic or
  finding).

## Finding types

One vocabulary for the database, the API and the classifier:

| `type` | Meaning | Comes from | Weight |
|---|---|---|---|
| `contradiction` | Matched passages state incompatible facts | classifier | 1.0 |
| `numbers` | Different figures for the same thing | classifier | 1.0 |
| `missing_fact` | Matched passages, but one states a fact the other lacks | classifier | 0.7 |
| `coverage` | A section of the richer edition has no close match in this one: its passages beyond 0.38 average more than 0.42 | alignment SQL | 0.5 |
| `framing` | Same subject, different label or framing ("fascist" in one, "radical right-wing" in the other) | classifier, word list | 0.25 |

The weight says how checkable a finding is: a contradiction or a figure is settled by the cited
source, while a framing difference is often settled consensus, so it ranks last. Every type but
framing is multiplied by 0.6 when the fuller side has no reference on the quoted sentence (for
`missing_fact` the side that has the fact; for `coverage` the missing passage).

No type carries a verdict on which edition is right, and there is no political score. A framing
difference with several loaded words becomes one finding per word, so the timeline shows when
each word entered or left. Every row in `sql` reports the rows that statement returned, which
can differ from the items in the response.

## Score

For one topic and one edition to fix (`lang`), against the richest other edition (`rich_lang`):

```
score = readers × weight of the most checkable open finding
```

`readers` is the user (not bot) page views of the `lang` article over the last 12 complete
months (0 until that article's page views are loaded). `coverage` is the share of `rich_lang`
passages with a close match in `lang`, a partly matched passage counting half. It is shown, not
scored: editors do not read a shorter article as a defect. The queue lists only pairs with an
open finding. The queue's answer also has `"database": {"version": "11.8.9", "table": "chunk",
"versions": 225816, "passages": 39330}`: every row version the system-versioned passage table has
kept (`FOR SYSTEM_TIME ALL`), and the passages current today. A finding's own score is `readers × weight`.

Passages match by cosine distance between their bge-m3 vectors: `covered` at most 0.30,
`partly` at most 0.38, else `missing` (calibrated on leads of the same topic against leads of
other topics). A coverage finding's `distance` is that section average, and its summary names
the section of `lang` the passages are nearest to. Findings with the same score are ordered by
distance, most distinct first.

## Endpoints

### `GET /api/queue?lang=all|fi|sv|en&limit=50&offset=0`

One row per (topic, edition to fix), sorted by `score` descending.

```json
{"as_of": "2026-11-13", "total": 8757,
 "items": [{"wikidata_id": "Q1412941", "topic": "Lapua Movement", "lang": "en", "rich_lang": "fi",
            "readers": 39666, "coverage": 0.31,
            "size": {"fi": 153937, "sv": 7747, "en": 20943},
            "score": 34269, "weight": 0.25, "findings": 5, "top_type": "framing", "status": "open",
            "quality": {"fi": "Suositeltu"}}],
 "sql": []}
```

- `topic` is the English title.
- `findings` counts open findings; `top_type` is the type with the highest weight among them, and
  `weight` that weight, so `score` = `readers` × `weight` (rounded).
- `status` is `open` while any finding of the pair is open, else `reviewed` or `closed`.
- `quality` names each edition's quality template (featured or good: `Suositeltu`, `Hyvä artikkeli`,
  `Utmärkt`, `Bra`, `Featured`, `Good`); editions without one are absent.

### `GET /api/topics/{qid}`

```json
{"wikidata_id": "Q1412941", "topic": "Lapua Movement",
 "titles": {"fi": "Lapuan liike", "sv": "Lapporörelsen", "en": "Lapua Movement"},
 "size": {"fi": 153937, "sv": 7747, "en": 20943},
 "readers": {"fi": 38890, "sv": 4133, "en": 39666},
 "refs": {"fi": 500, "sv": 21, "en": 30},
 "quality": {"fi": "Suositeltu"},
 "leads": {"fi": {"text": "…", "rev_id": 123, "also": "second lead passage, if any"}},
 "findings": [Finding],
 "checked": {"judge": "nemotron-3.5-super-vl", "model": "nemotron-3.5-super-vl", "as_of": "2026-11-14", "kept": 146, "changed": 3, "new": 2,
             "unchecked": 9, "set_aside": {"stated_elsewhere": 55, "not_confirmed": 1, "repeat": 5}},
 "sql": []}
```

`checked` is the claim check's totals for the topic (`checked_finding`, described in
[`differences/README.md`](../differences/README.md)), or `null` when the check has not run on it.
Each finding then has `check`: `null` when the check did not look at the row (the word list's
framing rows, coverage rows), else

```json
{"outcome": "kept", "reason": null, "verdict": "contradicted", "judge": "nemotron-3.5-super-vl",
 "as_of": "2026-11-14", "claim": {"lang": "sv", "quote": "…", "about": "…"}, "figures": ["102", "50"],
 "searched": 22, "read": 4,
 "evidence": {"lang": "en", "rev_id": 1383067871, "section": "…", "quote": "…", "passage": null}}
```

`outcome` is `kept`, `changed` (the finding is returned as the check rewrote it, under its own id
and dates), `new` (a difference the check found itself: a negative `id`, no history), `set_aside`
(with `reason` `stated_elsewhere`, `not_confirmed` or `repeat`; not a difference after all) or
`unchecked` (framing, passed through). `evidence.passage` is the whole passage, on a set-aside row only.
`checked.model` is the model that wrote the findings, `checked.judge` the one that checked them.

A row a person read and found false is closed with outcome `not_real`, a `new` row too
(`python -m gapfinder.checked hand demo/hand-checked.json`, which `deploy/up.sh` runs on every deploy).

A **Finding**:

```json
{"id": 7, "lang": "en", "other_lang": "fi", "type": "framing",
 "section": "", "other_section": "",
 "summary": "One neutral English sentence.",
 "quotes": {"en": "fascist, pro-Nazi", "fi": "oikeistoradikaali"},
 "citations": {"en": "Kotila, … Science & Society, 2006", "fi": null},
 "paragraph_citations": {"en": null, "fi": "Siltala 1985, s. 51–53."},
 "rev_ids": {"en": 1383067871, "fi": 24266018},
 "terms": ["fascist"], "distance": 0.31, "weight": 0.25, "score": 12000,
 "status": "open", "outcome": null, "rev_url": null,
 "opened_at": "2022-05-30", "opened_after": "2022-01-01", "closed_at": null, "closed_after": null,
 "history": true}
```

- `lang` is the edition to fix; `other_lang` the edition compared against.
- `section` is `""` for the lead. For `coverage`, `section` is the section of the passage missing
  from `lang` (in `other_lang`'s article) and `other_section` is `null`.
- Each `quotes` value is an exact substring of that edition's passage text, so the UI can
  highlight it. Either may be missing. A classifier quote that is not verbatim in the passage
  drops the difference before it becomes a finding.
- `citations` has a key for each quoted edition: the reference in or right after the quoted
  sentence, or `null` when it has none. For `coverage` the quote is the first sentence of the
  missing passage (an exact prefix of it, at most 400 characters) and the citation the reference
  on that sentence; the weight counts the passage as sourced when it has any reference.
- `paragraph_citations` has the same keys: the reference ending the quote's paragraph, or `null`
  when the paragraph doesn't end in one (Finnish articles usually cite at paragraph ends).
- `rev_ids` are the revisions the evidence was taken from.
- `status` is `open`, `reviewed` (raised on the talk page) or `closed` (any other outcome, or the
  alignment no longer sees the gap). `outcome` is the editor's: `edited`, `talk`, `intentional`,
  `not_real` or `null`; `rev_url` the link given with it.
- Dates come from the yearly history: one revision per edition per 1 January. The edit that
  opened the finding is after `opened_after`, the last compared 1 January on which it did not
  hold, and no later than `opened_at`, the edit date of the later of the two revisions in which it
  first held. `opened_after` is `null` when there is no earlier comparison; `opened_at` then only
  says since when the finding is known to hold. `closed_after` and `closed_at` bound the closing
  edit the same way, and are `null` while the finding is open. A finding that came back after a
  period without it reports its latest period.
- `history` is `false` when no earlier 1 January was compared for this finding (history not
  embedded yet, or a model finding on today's text only). Then `opened_at` only dates the current
  revision: show it as "in the current text; earlier years not compared", not as a start date.
- A framing finding is one loaded word in the edition that uses it, so its dates follow that
  word. A passage-level framing finding is dropped when the other edition's lead uses the word;
  first-sentence findings compare only the first sentences.

### `GET /api/topics/{qid}/compare?a=fi&b=en&as_of=2026-01-01`

The passage alignment returned by the `FOR SYSTEM_TIME AS OF` query for that date. `as_of` is
optional and defaults to now.

```json
{"as_of": "2026-01-01", "a": "fi", "b": "en",
 "rows": [{"a": {"chunk_id": 1, "section": "", "chunk_no": 0, "rev_id": 123, "text": "…"},
           "b": {"chunk_id": 9, "section": "", "chunk_no": 0, "rev_id": 456, "text": "…"},
           "distance": 0.21, "status": "covered"}],
 "sql": []}
```

- One row per passage of `a`, in article order, with its nearest passage of `b`.
- `status` is `covered`, `partly`, `missing` or `pending`; `b` is `null` unless covered or partly.
  `pending` means not compared yet: the passage, or some passage of `b` on that date, has no
  vector yet, so a far match cannot be called a gap. `complete` is `true` once both editions
  are fully embedded for that date.

### `GET /api/topics/{qid}/timeline?lang=en&rich_lang=fi`

One point per 1 January, 2005–2026.

```json
{"years": [{"year": 2008, "size": {"fi": 95519, "sv": 3000, "en": 6500},
            "coverage": 0.12, "open_findings": 3}],
 "events": [{"date": "2022-01-01", "finding_id": 7, "kind": "opened", "type": "coverage",
             "summary": "…", "after": "2021-01-01", "rev_id": 1062000000, "rev_lang": "fi",
             "diffs": [{"lang": "fi", "old_rev_id": 1050000000, "rev_id": 1062000000}]}],
 "sql": []}
```

`events` come from the system-versioned `finding` table: `opened`, `reviewed`, `closed`, each
with the finding's `type`. A year's `coverage` is `null` when that year is not aligned yet.
An `opened` or `closed` event's `date` is the edit date of the later revision of the pair that
showed the change, and `after` the last compared 1 January before it (`null`: none). `diffs` lists,
for each edition of the pair edited in between, the diff that contains the change
(`{"lang", "old_rev_id", "rev_id"}`, the revisions current on `after` and on `date`); it is empty
when `after` is `null`. `rev_id` and `rev_lang` repeat the last diff. Editor outcomes carry
`rev_url` instead.

### `POST /api/findings/{id}/status`

Body `{"outcome": "edited" | "talk" | "intentional" | "not_real" | null, "rev_url": str | null}`
(a `status` key is accepted and ignored; `null` reopens). Returns the updated Finding plus `sql`.
The change is an ordinary `UPDATE`, so the old outcome stays in the table's history.
`intentional` and `not_real` take the finding out of the queue and are kept as precision data.

### `GET /api/search?q=...&lang=all|fi|sv|en&limit=20`

Topics whose title in any edition contains the query (`LIKE`), an exact title first, then those
whose current passages are nearest to the query text, from the vector index on `chunk_now`:
`{"items": [QueueItem], "sql": []}`. Passages farther than cosine distance 0.55 from the query do not count,
so a query that matches nothing returns no items. One item per topic, nearest first: its row for `lang`, or with
`lang=all` (the default) its highest-scoring edition. A topic with no open finding in `lang` is
left out. The first search after a restart loads the model (about 10 s).
When the embedding model is not on disk (`HF_HOME`), search is by title alone and downloads nothing.

### `GET /api/sql/presets`

The statements the SQL panel's Run button can run:
`{"enabled": bool, "limits": {"seconds": 5, "rows": 500}, "presets": [Preset]}`.

```
Preset {
  "name": "nearest" | "asof" | "history" | "check",
  "title": str, "description": str,
  "params": [{"name": str, "kind": "qid" | "date" | "lang", "default": str}]
}
```

`enabled` is false when the service has no read-only database user (`DB_RO_USER`,
`DB_RO_PASSWORD`); the UI then shows no Run section and the panel is the log alone.

| Preset    | Parameters             | Statement |
|-----------|------------------------|-----------|
| `nearest` | `qid`, `date`, `a`, `b` | Time travel and vector search in one statement: the passages of `a` as of `date` (`chunk FOR SYSTEM_TIME AS OF`), each with its nearest passage in `b` (`VEC_DISTANCE_COSINE`). The query the aligner uses (`align.nearest_sql`). |
| `asof`    | `qid`, `date`, `lang`, `finding` | `SET SESSION system_versioning_asof` to `date`, then a plain `SELECT` with no time clause: the first passage, or with a `finding` (its id; `0` for none) the passage that holds the words the page quotes for that finding in `lang`, which are first read into `@quote` from the tables as they are today. Same statement, another date, another revision. |
| `history` | `qid`, `lang`          | Every version of the first passage (`chunk FOR SYSTEM_TIME ALL`) with its `row_start` and `row_end`, newest first. |
| `check`   | `finding`              | The claim check of one finding (its id, or a check-found row's negative id): its row of `checked_finding`, then the statement the check stored in `search_sql`, unchanged inside a `SELECT` of each passage's nearest sentence, its distance and its `REGEXP` hits. The other article `FOR SYSTEM_TIME AS OF` the day, each sentence ranked by `VEC_DISTANCE_COSINE` to the claim, dates, numbers and names counted with `REGEXP`. Its text comes from the table, never from the request. |

### `POST /api/sql/run`

Body `{"preset": str, "params": {name: str}}`. `params` is optional and a missing parameter takes
its default. The body carries no SQL: the statement text comes from fixed templates on the
server, and the only values that reach it are a Wikidata id (`Q` and digits), a date
(`YYYY-MM-DD`, from 2001-01-15 to today) and editions from `fi`, `sv`, `en` (`a` and `b` must
differ). Any other preset, parameter, value or body key is a 400 and opens no connection.

```
{
  "preset": "asof",
  "params": {"qid": "Q1412941", "date": "2026-10-22", "lang": "sv"},
  "columns": ["session_as_of", "rev_id", "row_start", "text"],
  "rows": [["2026-10-22 00:00:00.000000", 53401727, "2023-07-02T21:25:55", "Lapporörelsen var …"]],
  "capped": false,                       // true when the row limit cut the result
  "ms": 0.5,                             // all statements, measured on the server
  "limits": {"seconds": 5, "rows": 500},
  "sql": [{"label": str, "query": str, "ms": number, "rows": int}]   // as in every response
}
```

Each run opens its own connection as `DB_RO_USER`, which holds `SELECT` on the database and
nothing else, with `max_statement_time = 5` and `sql_select_limit = 500` set for the session.
Other statuses: 503 when no read-only user is configured, 429 when four runs are already in
progress, 504 when MariaDB cut the statement off at the time limit, 502 when it refused the
statement for another reason.

## Classifier interface

The alignment writes far-apart matched pairs as JSON lines; `python -m differences classify
pairs.jsonl > differences.jsonl` labels them.

Pair (input):

```json
{"pair_id": "Q1412941:2026-01-01:fi:12:en:40", "wikidata_id": "Q1412941", "as_of": "2026-01-01",
 "distance": 0.31,
 "a": {"chunk_id": 12, "lang": "fi", "title": "Lapuan liike", "section": "", "chunk_no": 0,
       "rev_id": 123, "text": "plain text"},
 "b": {"chunk_id": 40, "lang": "en", "...": "same fields"}}
```

Difference (output, zero or more per pair):

```json
{"pair_id": "…", "wikidata_id": "Q1412941", "as_of": "2026-01-01",
 "type": "missing_fact|contradiction|framing|numbers", "missing_in": "fi" ,
 "quote_a": "exact substring of a.text", "quote_b": "exact substring of b.text",
 "summary": "…", "terms": ["fascist"], "source": "llm|lexicon|both", "model": "…"}
```

`python -m gapfinder findings load differences.jsonl` writes them to the `finding` table.
