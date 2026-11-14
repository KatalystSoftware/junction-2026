# Walkthrough: two minutes, read aloud while clicking

Team Katalyst, MariaDB challenge "Wikipedia Through Time". The product name is "Since When"
(picked by Mikael on 14 Nov; UI title and pitch only, no code renames).

Runs against the instance on hestia. From a laptop, first
`ssh -N -L 8078:127.0.0.1:8078 hestia`, then every link below works as written.

Two things to know before clicking:

- A `?sql=` link opens the SQL panel with the fields filled in. It never runs by itself: click
  **Run**.
- The part after `#` keeps the Lapua Movement page behind the panel. Without it the panel opens over
  the first topic of the queue.

Lines marked **Say** are the spoken text, 264 words in all. Everything else is what to click and
what must be on screen.

## 1. The finding, no SQL on screen (10 seconds)

Open <http://localhost:8078/#/Q1412941/sv/en/findings>

On screen: three cards with the first sentence of the Swedish, English and Finnish article. The
Swedish card has "fascistisk" underlined, the English card "fascist" and "pro-Nazi".

> **Say:** We are Katalyst, and this is Since When. English and Swedish Wikipedia call the Lapua
> Movement fascist in their first sentence. Finnish Wikipedia calls it an anti-communist,
> radical-right popular movement. Swedish added the word three weeks ago, on 23 October. English
> dropped it in 2009, put it back in 2022 and added "pro-Nazi" this April.

## 2. Since when (15 seconds)

Open <http://localhost:8078/#/Q1412941/sv/en/timeline>

On screen: "When each difference opened and closed". The "fascist" difference between Swedish and
English closed on 2009-06-07, opened again on 2022-05-30 and closed on 2026-10-23; "pro-Nazi" opened
on 2026-04-07. Each date names the revision that caused it. The list also has the earlier turns of
the same word (opened 2004, closed 2006, opened 2007).

> **Say:** Each difference has a date it opened and a date it closed, and the edit that did it. The
> dates come from MariaDB. Every revision of this article is a row version in a system-versioned
> table.

## 3. Run a query on the versioned table (30 seconds)

Open <http://localhost:8078/?sql=asof,Q1412941,2026-10-22,sv#/Q1412941/sv/en/findings>

Click **Run**. The panel shows two statements: `SET SESSION system_versioning_asof = '2026-10-22
00:00:00'`, then a `SELECT` from `chunk` with no time clause. One row: revision 59364242, "…
utomparlamentarisk och antikommunistisk rörelse som startades 1929".

Change the date to **2026-10-24** and click **Run** again. One row: revision 59790334, "…
nationalistisk, fascistisk och antikommunistisk …". The first result stays below as "Previous run".

> **Say:** This panel shows the SQL behind the page, and I can run it. I set the session to 22
> October and read the Swedish first passage with a plain query. No "fascist". Same query, 24
> October: the word is there. MariaDB chose the row version; the query did not change.

## 4. Time travel and vector search in one statement (30 seconds)

Open <http://localhost:8078/?sql=nearest,Q1412941,2026-10-24,fi,en#/Q1412941/sv/en/findings>

Click **Run**. One statement: `FROM chunk FOR SYSTEM_TIME AS OF TIMESTAMP '2026-10-24 00:00:00'`
and `VEC_DISTANCE_COSINE(x.embedding, y.embedding)`. 59 rows in about ten milliseconds, one per
Finnish passage, with its nearest English passage, the distance and a status: 3 covered, 26 partly,
30 missing.

> **Say:** This is the comparison itself. One statement reads the article as of a date with FOR
> SYSTEM_TIME AS OF, and pairs each Finnish passage with its nearest English passage with
> VEC_DISTANCE_COSINE. 59 passages in about ten milliseconds. Thirty have no close match in English.

If there is time, the third preset: <http://localhost:8078/?sql=history,Q1412941,en#/Q1412941/sv/en/findings>,
**Run**. `FOR SYSTEM_TIME ALL`: 51 versions of the English first passage, 2003 to today, newest
first. Nothing to say; it is the list the dates in step 2 come from.

## 5. One measurement (25 seconds)

Stay on the panel.

> **Say:** We measured the vector index on the versioned table, on MariaDB 11.8.9. It works: recall
> is about 0.97 at the default setting. But it holds every version, and it is 5 to 14 times slower
> for past dates. So we keep the index on the current rows and search one topic exactly for the past.
> That is exact and takes milliseconds.

> **Say:** Every statement you saw is fixed on the server and runs as a read-only user with a time
> limit.

The numbers are in [`measurements.md`](measurements.md), "Rerun on a quiet machine": recall@10 of
0.95 to 0.98 at `mhnsw_ef_search` 20, 4.74 ms against 0.35 ms as of 2010 and 1.99 ms against
0.42 ms as of 2020, a median of 5 to 10 ms per topic for the exact search.

## Fallback: the Finnish War with the Diet of Porvoo

Same steps, same clicks. Only the opening sentence of step 1 changes:

> **Say:** We are Katalyst, and this is Since When. Swedish Wikipedia says the fortress of Sveaborg
> capitulated on 3 May 1808, English Wikipedia says 6 May, and Finnish Wikipedia says early May. The
> three editions also give three different sets of dates for the Diet of Porvoo.

| Step | Finnish War (`Q736268`) | Diet of Porvoo (`Q2457646`) |
| --- | --- | --- |
| 1 | <http://localhost:8078/#/Q736268/sv/en/findings> | <http://localhost:8078/#/Q2457646/en/fi/findings> |
| 2 | <http://localhost:8078/#/Q736268/sv/en/timeline> | <http://localhost:8078/#/Q2457646/en/fi/timeline> |
| 3 | <http://localhost:8078/?sql=asof,Q736268,2026-04-25,en#/Q736268/sv/en/findings> | <http://localhost:8078/?sql=asof,Q2457646,2026-11-05,sv#/Q2457646/en/fi/findings> |
| 4 | <http://localhost:8078/?sql=nearest,Q736268,2026-10-24,fi,en#/Q736268/sv/en/findings> | <http://localhost:8078/?sql=nearest,Q2457646,2026-10-24,fi,en#/Q2457646/en/fi/findings> |
| extra | <http://localhost:8078/?sql=history,Q736268,en#/Q736268/sv/en/findings> | <http://localhost:8078/?sql=history,Q2457646,en#/Q2457646/en/fi/findings> |

What comes back:

- Step 1, Finnish War: the list has the surrender of Sveaborg (3 May in Swedish, 6 May in English;
  finding 14353). Diet of Porvoo: the list has the dates of the diet (22 March to 19 July in
  Finnish, 25 March to 19 July in English, 25 March to 18 July in Swedish; finding 14115). The
  wording and quotes of both are in [`hero-findings.md`](hero-findings.md).
- Step 3, Finnish War: on 2026-04-25 the English first passage is revision 1259768954, "The Finnish
  War (Swedish: Finska kriget; Russian: …) was fought between …". Change the date to **2026-04-26**:
  revision 1351101732, "The Finnish War was fought between the Kingdom of Sweden and the Russian
  Empire from 21 February 1808 to 17 September 1809 …". The names in other languages are gone and
  the dates are in.
- Step 3, Diet of Porvoo: on 2026-11-05 the Swedish first passage is revision 46332373 from 2019;
  on **2026-11-06** it is revision 59835605. The first 320 characters are the same in both, so use
  the Finnish War for this step.
- Step 4: 31 rows for the Finnish War, 17 for the Diet of Porvoo.
- Step 5 does not change.
