# Full revision history of the three hero topics (builder 1, branch `feat/mariadb-hero-history`)

`article` and `chunk` on scratch now hold every revision of the fi, sv and en articles of Lapua
Movement `Q1412941`, Finnish War `Q736268` and Diet of Porvoo `Q2457646`, each versioned with the
revision's own timestamp. `FOR SYSTEM_TIME AS OF` any moment gives the article as Wikipedia showed
it then, and a finding's open and close dates are the days of the edits that caused them.

All three topics got the full history (no fallback to "since 2022").

## Rebuild from a fresh restore of the snapshot

Nothing is refetched and no model runs: the revisions and the embeddings come from
`~/junction2026-data/mariadb/revisions/` (layout in its `README.md`). Run from `projects/since-when/`, on
this branch or a branch that has it merged.

```sh
M=~/junction2026-data/mariadb
run=demo/hero-history-run.sh   # <container suffix> <memory> <module and arguments>

# 1. The full_history table (idempotent).
sh $run schema 1500m gapfinder schema

# 2. Every revision into article and chunk, vectors from the disk cache into passage.
sh $run load 2g gapfinder.revisions load Q1412941 Q736268 Q2457646

# 3. Coverage on every 1 January and today, then the findings with dates from the revisions.
echo "DELETE FROM coverage WHERE wikidata_id IN ('Q1412941','Q736268','Q2457646') AND NOT is_current" | $M/bin/scratch-sql
sh $run align 1500m gapfinder align --only Q1412941 Q736268 Q2457646

# 4. Check through an API that reads the same database (mine ran on 8277, my pages on 8278).
sh demo/hero-history-check.sh http://127.0.0.1:8277
```

Order with builder 4's replay (`hero-findings-notes.md`): my steps 1 to 3 first, then theirs. Their
pairs come from the current passages and the coverage my step 3 writes, and their last step
(`gapfinder findings load`) rebuilds the three topics' findings, with the dates below once
`gapfinder/align.py` of this branch is merged. Step 3 loads no model (it compares stored vectors
in SQL), so it needs no `heavy.lock`.

The two steps that made the caches, for the record. A rerun of either does nothing new: `fetch`
reads `revisions/raw/` and sends no request, `embed` finds every vector on disk.

```sh
sh $run fetch 1500m gapfinder.revisions fetch Q1412941 Q736268 Q2457646
for q in Q1412941 Q736268 Q2457646; do for l in en fi sv; do
  flock $M/locks/heavy.lock sh $run embed 3g gapfinder.revisions embed $q $l
done; done
```

## The four facts about the Lapua Movement's first sentence

Base of the URLs: my API, `http://127.0.0.1:8277` (any API on the same database answers the same).
In a compare answer the first row (`rows[0].a`) is the introduction of edition `a`; its `text`
starts with the first sentence and its `rev_id` is the revision that wrote that text. The SQL for
all of them is this statement with the language and the moment changed (times are UTC):

```sql
SELECT c.rev_id, c.row_start, SUBSTRING_INDEX(p.text, '. ', 1) AS first_sentence
FROM chunk FOR SYSTEM_TIME AS OF TIMESTAMP '2026-10-22 00:00:00' AS c
JOIN passage AS p ON p.sha = c.sha
WHERE c.wikidata_id = 'Q1412941' AND c.lang = 'sv' AND c.ord = 0;
```

Run it with `$M/bin/scratch-sql` (SQL on stdin). What it returned on scratch on 2026-11-14:

| Fact | URL on the API | `lang`, `AS OF` | `rev_id`, `row_start` | First sentence |
| --- | --- | --- | --- | --- |
| 1. Swedish gains "fascist" on 2026-10-23 | `/api/topics/Q1412941/compare?a=sv&b=en&as_of=2026-10-22` | sv, `2026-10-22 00:00:00` | 59364242, 2026-06-04 12:14:10 | Lapporörelsen var en finländsk utomparlamentarisk och antikommunistisk rörelse som startades 1929 |
| | `/api/topics/Q1412941/compare?a=sv&b=en&as_of=2026-10-24` | sv, `2026-10-24 00:00:00` | 59790334, 2026-10-23 12:31:27 | Lapporörelsen var en finländsk nationalistisk, fascistisk och antikommunistisk utomparlamentarisk politisk rörelse som grundades 1929 i Lappo. |
| 2. English drops it on 2009-06-07 | `/api/topics/Q1412941/compare?a=en&b=sv&as_of=2009-06-06` | en, `2009-06-06 00:00:00` | 292260900, 2009-05-25 17:34:03 | The Lapua Movement (Finnish: Lapuan liike), sometimes referred to as "Lapua Fascism", named after the then municipality and modern days town of Lapua, was a political movement in Finland |
| | `/api/topics/Q1412941/compare?a=en&b=sv&as_of=2009-06-08` | en, `2009-06-08 00:00:00` | 294882000, 2009-06-07 00:29:51 | The Lapua Movement (Finnish: Lapuan liike), named after the then municipality and modern days town of Lapua, was a political movement in Finland. |
| (still without it at the two revisions of the brief) | `/api/topics/Q1412941/compare?a=en&b=sv&as_of=2014-03-28` | en, `2014-03-28 00:00:00` | 524011046, 2012-11-20 12:41:58 | The Lapua Movement (Finnish: Lapuan liike, Swedish: Lapporörelsen), was a Finnish radical nationalist and anti-communist political movement founded in and named after the town of Lapua |
| | `/api/topics/Q1412941/compare?a=en&b=sv&as_of=2020-12-07` | en, `2020-12-07 00:00:00` | 952023914, 2020-04-20 05:34:40 | The Lapua Movement (Finnish: Lapuan liike, Swedish: Lapporörelsen) was a radical Finnish nationalist and anti-communist political movement founded in and named after the town of Lapua |
| 3. English restores it on 2022-05-30 | `/api/topics/Q1412941/compare?a=en&b=sv&as_of=2022-05-29` | en, `2022-05-29 00:00:00` | 1082481405, 2022-04-13 11:54:46 | … was a radical Finnish nationalist and anti-communist political movement … |
| | `/api/topics/Q1412941/compare?a=en&b=sv&as_of=2022-05-31` | en, `2022-05-31 00:00:00` | 1090675024, 2022-05-30 19:24:45 | … was a radical Finnish nationalist, fascist and anti-communist political movement … |
| (and has it on 2022-12-24, as the brief says) | `/api/topics/Q1412941/compare?a=en&b=sv&as_of=2022-12-25` | en, `2022-12-25 00:00:00` | 1129221656, 2022-12-24 05:18:50 | … was a radical Finnish nationalist, fascist, pro-German and anti-communist political movement … |
| 4. English gains "pro-Nazi" on 2026-04-07 | `/api/topics/Q1412941/compare?a=en&b=sv&as_of=2026-04-06` | en, `2026-04-06 00:00:00` | 1275978086, 2025-02-16 05:02:13 | … was a radical Finnish nationalist, fascist, pro-German and anti-communist political movement … |
| | `/api/topics/Q1412941/compare?a=en&b=sv&as_of=2026-04-08` | en, `2026-04-08 00:00:00` | 1347550072, 2026-04-07 10:52:19 | … was a radical Finnish nationalist, fascist, pro-Nazi and anti-communist political movement … |

The exact revisions, each the first one whose first sentence differs:

- **Swedish gains "fascist"**: sv revision 59790252, 2026-10-23 11:25:13 UTC (as the brief says).
  Two more edits the same day (59790287 at 12:05:01, 59790334 at 12:31:27) reworded the
  introduction again, so the row of 2026-10-24 carries 59790334.
- **English drops it**: en revision **294882000, 2009-06-07 00:29:51 UTC**. It removed
  `sometimes referred to as "Lapua Fascism"`, which revision 136137173 (2007-06-05 20:15:42) had
  added. This is the exact date for the brief's "around 2009/2010". The brief's revisions
  601435088 (2014-03-27 00:30:55) and 992707385 (2020-12-06 18:10:47) are in `article`; neither
  touched the introduction, so `chunk.rev_id` on those days names the older revisions above.
- An earlier round that the yearly texts hid: from en revision 1142921 (2003-07-07) the English
  article opened with one long sentence ending "however soon turning into more of a Fascist
  movement", until en revision 75029215 (2006-09-11 03:08:28 UTC) cut it to "was a political
  movement in Finland".
- **English restores it**: en revision **1090675024, 2022-05-30 19:24:45 UTC** ("radical Finnish
  nationalist, fascist and anti-communist"), seven months before the brief's "by 2022-12-24".
  Revision 1129222214 (2022-12-24 05:23:28) is in `article` and has the word; the introduction it
  shows was written five minutes earlier by 1129221656.
- **English gains "pro-Nazi"**: en revision 1347550072, 2026-04-07 10:52:19 UTC (as the brief says).

The same edits as findings, on `/api/topics/Q1412941` (latest period of each finding) and, with
every period, on `/api/topics/Q1412941/timeline?lang=sv&rich_lang=en` and
`…/timeline?lang=en&rich_lang=fi`. `opened_after` is the day before the edit, `opened_at` its day:

| Finding | What | Opened (after, at) | Closed (after, at) | Edit |
| --- | --- | --- | --- | --- |
| 13072 sv/en framing "fascist" | English first sentence uses it, Swedish does not | 2022-05-29, 2022-05-30 | 2026-10-22, 2026-10-23 | en 1090675024, sv 59790252 |
| (earlier periods, timeline) | | 2004-06-29; 2007-06-04, 2007-06-05 | 2006-09-10, 2006-09-11; 2009-06-06, 2009-06-07 | en 75029215, 136137173, 294882000 |
| 13079 sv/fi framing "fascist" | Swedish first sentence uses it, Finnish does not | 2026-10-22, 2026-10-23 | open | sv 59790252 |
| 13069 en/fi framing "fascist" | English first sentence uses it, Finnish does not | 2022-05-29, 2022-05-30 | open | en 1090675024 |
| 13602 sv/en framing "pro-Nazi" | English first sentence uses it, Swedish does not | 2026-04-06, 2026-04-07 | open | en 1347550072 |
| 13095 en/fi framing "pro-Nazi" | English calls the movement pro-Nazi, Finnish does not | 2026-04-06, 2026-04-07 | open | en 1347550072 |

## Finding dates

`gapfinder/align.py` dates a finding with a test on the revisions, when `full_history` lists the
topic (`build_findings` reads that table, so run `gapfinder schema` before it on any database):

| Finding | Test replayed on every revision |
| --- | --- |
| framing from the word list, one term | the word list's own test on the first sentences (or on the sections): one edition uses the word, the other does not |
| other framing, numbers | every quote is still in its edition |
| missing fact | the fact's sentence is in the edition that has it |
| missing section (coverage) | the section is in the richer edition, under any title it was seen with |
| coverage of the introduction | none (stays on compared dates) |

- `opened_after` and `closed_after` are the day before the edit, `opened_at` and `closed_at` its
  day; a finding there since the article's first revision has no `opened_after`.
- A state shorter than a day is ignored (a vandal's two-minute introduction on 2025-02-16 opens
  and closes nothing).
- A finding that the compared dates (every 1 January and today) show as open stays open when the
  test agrees at both ends; a period that opened and closed between two compared dates is still
  not found, because the pairs are aligned only on those dates.
- A finding the test cannot place keeps the compared-date bounds it had before (the lists below
  name them all). The causes: a missing section that was there on the earlier compared date and
  then had a counterpart (coverage 47, 42, 8, 16 on Lapua Movement, the seven on Finnish War,
  2500 on Diet of Porvoo); coverage of the introduction, which has no test; and framing 13303 and
  13087, where the stored word-list rows call fi "oikeistoradikaali" `far right` and today's
  `differences/lexicon.py` calls it `radical right`, so no first sentence "uses" the row's term.
- A `difference` row that names no lacking side (`missing_in` empty) carries only the sentence of
  its own edition; the test then uses that sentence. Before this, 21 such findings on Finnish War
  had `history: false` and the date of the current revisions (2026-10-25, 2026-09-18).
- A finding whose quote is in no revision cannot be dated and gets `history: false` with the date
  of the current revisions. That happened to rows quoting a passage as the old code cleaned it
  (see "Passage ids"); builder 4 has classified those pairs again, and no finding of the three
  topics has `history: false` now.

After the last rebuild (06:00 EET, on builder 4's `difference` rows of 05:55), from
`/api/topics/<qid>` (latest period of each finding):

| Topic | Findings | Open | Closed | Opening dated to the edit's day | There from the first day, or from before 2005-01-01 | Opening between two compared dates | Closings: edit's day / between two compared dates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Lapua Movement | 258 | 239 | 19 | 245 | 7 | 6 | 16 / 3 |
| Finnish War | 379 | 365 | 14 | 372 | 0 | 7 | 14 / 0 |
| Diet of Porvoo | 117 | 109 | 8 | 112 | 2 | 3 | 5 / 3 |

- No finding carries the load date, and none says "before 2005" without a date: the nine without
  `opened_after` are dated to a real revision of 2004 or 2006.
  - Lapua Movement: missing facts 13488, 13507, 13509 (fi/en, 2004-06-22, the Finnish article's
    first day) and 14101, 14080 (sv/en, 2004-06-29, the Swedish article's first day); framing 13087
    (sv/fi, 2004-12-22) and coverage 1 (fi/en, 2004-12-28): seen on the first compared date,
    2005-01-01, and dated to the revision current then.
  - Diet of Porvoo: missing fact 14181 (sv/fi, 2006-02-23, the Swedish article's first day) and
    coverage 14543 (en/fi introduction, 2004-11-05, dated like coverage 1).
- Opening known only between two compared dates (`opened_after` a 1 January, `opened_at` the last
  edit before the next one): Lapua Movement coverage 47, 42, 8, 16, 40 and framing 13303; Finnish
  War coverage 5335, 5337, 13910, 13905, 13914, 13917, 13919; Diet of Porvoo coverage 2500, 14542,
  14546.
- Closing known only between two compared dates: Lapua Movement coverage 1, 40 and framing 13303
  (closed "2026-11-13", the day the word list last ran); Diet of Porvoo coverage 14542, 14543,
  14546.
- By type: Lapua Movement coverage 32, framing 16, missing fact 204, numbers 6; Finnish War
  contradiction 5, coverage 25, framing 3, missing fact 333, numbers 13; Diet of Porvoo
  contradiction 1, coverage 25, framing 3, missing fact 84, numbers 4.
- Latest openings per year, Lapua Movement: 2004 7, 2005 6, 2007 11, 2008 1, 2011 1, 2012 1,
  2013 2, 2015 2, 2017 1, 2020 36, 2021 91, 2022 12, 2023 3, 2024 44, 2025 2, 2026 38. Finnish
  War: 2004 1, 2005 5, 2006 20, 2007 5, 2008 74, 2009 62, 2010 6, 2011 1, 2012 15, 2013 7, 2015 16,
  2016 4, 2017 1, 2018 2, 2019 27, 2020 12, 2021 12, 2022 36, 2023 6, 2024 9, 2025 30, 2026 28.
  Diet of Porvoo: 2004 2, 2006 2, 2007 6, 2008 4, 2009 1, 2011 3, 2014 2, 2015 11, 2016 1, 2017 1,
  2019 3, 2020 3, 2021 2, 2022 7, 2023 2, 2024 21, 2025 11, 2026 35.

## Counts and times

| Topic | Lang | Revisions fetched | Requests | Fetch | Article versions | Chunk versions | Distinct passages | Embeddings already in the database | Embeddings computed | Embed |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Lapua Movement Q1412941 | en | 271 | 7 | 13 s | 271 | 175 | 144 | 52 | 92 | 108 s |
| | fi | 1200 | 27 | 80 s | 1200 | 4073 | 1441 | 290 | 1151 | 2031 s |
| | sv | 89 | 3 | 6 s | 89 | 66 | 55 | 15 | 40 | 67 s |
| Finnish War Q736268 | en | 769 | 18 | 43 s | 769 | 558 | 394 | 156 | 238 | 270 s |
| | fi | 810 | 19 | 50 s | 796 | 1352 | 507 | 182 | 325 | 484 s |
| | sv | 642 | 15 | 36 s | 642 | 474 | 275 | 91 | 184 | 201 s |
| Diet of Porvoo Q2457646 | en | 110 | 4 | 6 s | 110 | 79 | 60 | 7 | 53 | 67 s |
| | fi | 854 | 20 | 51 s | 848 | 1042 | 287 | 17 | 270 | 415 s |
| | sv | 57 | 3 | 5 s | 57 | 21 | 15 | 8 | 7 | 12 s |
| All | | 4802 | 116 | 290 s | 4782 | 7840 | 3178 | 818 | 2360 | 3655 s |

- An article version is one revision; a chunk version is one text of one passage position, with
  `row_start` the timestamp and `rev_id` the id of the revision that wrote it. Before: 23 article
  versions per article at most (1 January of each year).
- The Finnish articles of Finnish War and Diet of Porvoo have fewer article versions than
  revisions fetched (14 and 6 fewer): those revisions are later than the one current in the
  snapshot (24241686 and 24273336), where the load stops (decision 2).
- `full_history.since`, the first revision of each article: Lapua Movement en 2003-07-02, fi
  2004-06-22, sv 2004-06-29; Finnish War en 2003-06-14, fi 2004-04-14, sv 2003-02-08; Diet of
  Porvoo en 2004-04-12, fi 2004-06-27, sv 2006-02-23.
- Fetch: 116 requests, one at a time, 04:25 to 04:31 EET, no 429 and no `maxlag` answer.
- Embedding (bge-m3 on the CPU, about 105 words a second), each language under `heavy.lock`:
  Lapua Movement 2206 s (done 05:19 EET), the other two 1449 s (done 05:49 EET), 3655 s
  (61 minutes) in total for 2360 vectors. No job was killed. A rerun computes none.
- Load: Lapua Movement alone 45 s (29 s of it splitting 1,560 revisions into passages); all three
  71 s (58 s splitting 4,782 revisions; 1077 vectors copied from the disk cache on that run, no
  passage left without one).
- Align and findings: Lapua Movement 17 s (23 dates aligned in 5 s, 277 findings rebuilt); all
  three 9 s (69 dates aligned in 1 s, 739 findings rebuilt, 11262 finding rows of other topics
  kept); the last run, after builder 4's reload, 9 s (3 dates, 762 findings rebuilt).
- Snapshot restore (builder 4's figure): 141 s.

Counted with:

```sql
SELECT wikidata_id, lang, COUNT(*) FROM article FOR SYSTEM_TIME ALL
WHERE wikidata_id IN ('Q1412941','Q736268','Q2457646') GROUP BY 1, 2;
SELECT wikidata_id, lang, COUNT(*), COUNT(DISTINCT sha) FROM chunk FOR SYSTEM_TIME ALL
WHERE wikidata_id IN ('Q1412941','Q736268','Q2457646') GROUP BY 1, 2;
SELECT COUNT(DISTINCT c.sha) FROM chunk FOR SYSTEM_TIME ALL AS c JOIN passage AS p ON p.sha = c.sha
WHERE c.wikidata_id IN ('Q1412941','Q736268','Q2457646') AND p.embedding IS NULL;   -- 0
```

## Passage ids (for builder 4 and the integrator)

Passage ids are positions (`language, page, ord`), and the load ends at the revision that was
current in the snapshot, so every current passage kept its id. The load compares the current
passages before and after and prints any whose text changed.

**No id changed.** Five current passages kept their id and got a new text, sha, `chunk_now` row
and vector, because today's `gapfinder/wikitext.py` renders language templates that the code of
the live load dropped. The load reported every other current passage of the three topics as
unchanged.

| Passage id | Where | Written by revision | Old sha | New sha | What changed |
| --- | --- | --- | --- | --- | --- |
| `30002566030000` | en Lapua Movement, introduction | 1360078644 | `f46ba9a2…5287112` | `2bffee81b61f6b82a04d3753324945bc89f26660` | "(Finnish: Lapuanliike or Lapuan liike, Swedish: Lapporörelsen)" is back |
| `20000068610000` | sv Finnish War, introduction | 59222242 | `8a0df9d768aaf6917b69e533da97f256feaa6d0c` | `a92bfee56fda5de6ce59356cc536f6bc77020236` | adds "(Finnish: Suomen sota; Russian: Финляндская война)" |
| `30002461740003` | en Finnish War, Background, passage 2 | 1358109241 | `9973b8f32308bfb26d2e0ac83fabe1535683fa0f` | `c6ce9a60a6f729e3b7da0c79125973bc87e91bc2` | adds "Samuel Möller" |
| `30002461740012` | en Finnish War, War › August–September 1808, passage 1 | 1339517200 | `e38553194350c05ab00dbc627992d8330543a4b1` | `d51ad5b8e5dd0688bee85044852bc9ff230758c7` | adds "(Finnish: Lövön kahakka)" |
| `30005925090000` | en Diet of Porvoo, introduction | 1366299125 | `d2f5755f0afd227797bd7736abd87b9b3cde7772` | `4ce8be43ed4100c2e73840cf8b6b36f1f6711354` | "(Finnish: Porvoon maapäivät, or unhistorically Porvoon valtiopäivät; Swedish: Borgå lantdag; Russian: Боргоский сейм)" instead of "(, or unhistorically;; )" |

- The first changed at about 05:20 EET (the Lapua load), the other four at 05:50 (the load of all
  three). Builder 4 classified the affected pairs again both times (their notes, decisions 12 and
  14: 4 and 11 pairs) and loaded their rows at 05:23 and 05:55; their shortlist kept its ids.
- Their findings step ran the old `align.py` each time, so I ran my step 3 after it (last at
  06:00). Finding ids of the three topics did not change in those rebuilds.

## Checks

On the state after the 06:00 rebuild:

- `sh demo/hero-history-check.sh http://127.0.0.1:8277` and the same on
  `http://127.0.0.1:8278` (my pages, which pass `/api/*` on): exit 0, 62 lines `ok` (54 compare views, 8 first sentences), none
  `FAIL`. It asks the compare view for each topic, each of the six ordered language pairs and
  three dates (2008-06-15, 2015-06-15, 2026-10-24) and fails on any "not compared yet" row or
  empty answer, then checks the eight first sentences of the four facts.
- `http://127.0.0.1:8278/` answers 200; `docker logs gapfinder-a1-api` and `gapfinder-a1-ui`
  hold no traceback and no 5xx line.
- Tests, in the image with this checkout's `gapfinder/` and `differences/` mounted:
  `python -m unittest differences.test_differences gapfinder.test_wikitext`: 6 tests, OK; and
  `import gapfinder.align, gapfinder.revisions, gapfinder.load` succeeds.
- The counting SQL above: the article and chunk versions of the table, and 0 passages of the
  three topics without a vector.

## Decisions

1. **All three topics got every revision.** The estimate before embedding (`count.py`: passages
   and words left per article) was 54 minutes in total, under the two-hour limit; it took 61, and
   no job was killed. `SINCE=2022-01-01` on `embed` and `load` is the fallback and went unused.
2. **The history ends at the snapshot's current revision** (`article.rev_id`), although the files
   hold later revisions too: current passages keep their ids and texts, and builder 4's rows keep
   pointing at them. Bringing a topic up to date is the ordinary load's job.
3. **Texts are read with today's `gapfinder/wikitext.py`.** The live rows were loaded with older
   code; five current passages read differently now (above). I kept the ids, replaced their
   `chunk_now` rows and vectors, and told builder 4 through the load's output and this file.
4. **`chunk.rev_id` and `row_start` name the revision that wrote the text**, not the article's
   revision on that day. `article FOR SYSTEM_TIME AS OF` gives the article's revision. A
   `difference` row's `a_rev`/`b_rev` may name a later revision with the same passage text.
5. **Two revisions in the same second**: the later one stands (`row_start` must be unique per
   row). **Revisions whose text Wikipedia hides** are in the files with `text: null` and not in
   the database.
6. **Embed before load**, from files: `embed` writes one vector per distinct passage text to
   `revisions/embeddings/`, skipping texts that already have a vector in `passage`; `load` copies
   them in. A load therefore never waits for the model and a replay computes nothing.
7. **Load in one transaction.** `DELETE HISTORY` cannot filter by topic, so the load sets the
   other topics' `article` and `chunk` history aside in `a1_keep_article` and `a1_keep_chunk`,
   deletes, inserts the three topics and puts the rest back, all in one transaction; a failure
   rolls everything back. Readers see the old rows until the commit.
8. **Schema**: one new table, in `gapfinder/schema.sql`, idempotent:
   `CREATE TABLE IF NOT EXISTS full_history (wikidata_id, lang, since, PRIMARY KEY (wikidata_id, lang))`.
   One row per article loaded this way; `since` is the first moment the history is complete from
   (the article's first revision, or the `SINCE` day). `build_findings` dates by revisions only for
   topics listed there, so every other topic's findings are computed as before.
9. **Smallest change to the loader**: `load_article` takes an optional `split`, and `duckdb` is
   imported only where the dump is read (the image has no `duckdb`). The fetch and load of
   revisions are in a new file, `gapfinder/revisions.py`.
10. **Align needs no `heavy.lock`**: it compares stored vectors in SQL. It skips dates that have
    coverage rows, so the rebuild deletes the three topics' non-current coverage first.
11. **Rootless Docker**: no `--user` on the containers; with it the mounted folders were unreadable.
12. **No UI checks ran**: `ui/README.md` on my base lists none, and I changed nothing under `ui/`.
13. **A missing fact whose row names no lacking side** is dated by the one sentence the row
    quotes (`_evidence` in `align.py`); it was left undated before (21 findings on Finnish War).
14. **Dates are UTC days**, as the database stores them: an edit at 00:30 Finnish time is dated to
    the day before.

## For the integrator

- Run `python -m gapfinder schema` on any database before `align` or the findings step: the
  merged `build_findings` reads `full_history`.
- **Findings on scratch are whoever built them last.** Builder 4's `gapfinder findings load` on
  their branch runs the old `align.py` and writes year-bounded dates over mine, most with
  `history: false` (it happened at about 05:25 and 05:55; I ran my step 3 after each, last at
  06:00). The rule: after any `gapfinder findings load` on code without this branch's `align.py`,
  run my step 3 once more. On the merged code their findings step alone gives the edit dates.
  After the merge, replay in this order: my steps 1 to 3, builder 4's replay, then the check
  script.
- `gapfinder/align.py` is in builder 4's row as "the findings step"; I changed how a finding is
  dated there (`_Texts`, `_spans`, `_evidence`, `_dated`, `build_findings`). Builder 4's branch had
  not touched the file when I looked (06:02), so the merge should be clean.
- The stored word-list rows of the hero topics are older than `differences/lexicon.py`: they call
  fi "oikeistoradikaali" `far right`, today's list `radical right`, and their current rows are
  labelled 2026-11-13 while the model's are 2026-11-14. Running the word list again on the three
  topics (builder 4's step) would let findings 13303 and 13087 get edit dates too.
- On live, replaying my load changes the same five passages (table under "Passage ids"), so the
  model's rows for their pairs must be the ones builder 4 made after the change (their load of
  05:55 holds them all).
- The UI could say "on 23 October 2026" when `opened_after` is the day before `opened_at`; today
  it prints the two bounds (builder 2's files, not touched).
- `a1_keep_article` and `a1_keep_chunk` exist only during a load; if a load is killed they stay
  and the next load drops them.
