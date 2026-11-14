# Walkthrough: two and a half minutes, read aloud while clicking

Team Katalyst, MariaDB challenge "Wikipedia Through Time". The product name is "Since When"
(picked by Mikael on 14 Nov; UI title and pitch only, no code renames).

Runs against the public instance, <https://since-when.katalyst.fyi/>. Every step below was clicked
through there on 14 November 2026, after the last deploy. The same paths work on hestia's instance:
`ssh -N -L 8078:127.0.0.1:8078 hestia`, then `http://localhost:8078/` in place of the address.

Two things to know before clicking:

- A `?sql=` link opens the SQL panel with the fields filled in. It never runs by itself: click
  **Run**. So do **Check in MariaDB** and **How it was checked** on a difference.
- The part after `#` keeps the Lapua Movement page behind the panel. Without it the panel opens over
  the front page.

Lines marked **Say** are the spoken text. Everything else is what to click and what must be on
screen.

## 0. The front page (5 seconds, optional)

Open <https://since-when.katalyst.fyi/>

On screen: "What three Wikipedias say differently, and since when", a line that names MariaDB 11.8.9
and the system-versioned table `chunk` with 225,816 row versions of 39,330 passages, and three cards.
The first card is Lapua Movement, “fascist”, with a time strip: Swedish "23 Oct 2026", English
"30 May 2022". Click the card.

## 1. The difference, no SQL on screen (10 seconds)

Open <https://since-when.katalyst.fyi/#/Q1412941>

On screen: "Loaded words", marked "Word list", and under it “fascist”, open. Its time strip is on the
right: three lanes, Finnish, Swedish and English, from 2001 to today. The Finnish lane is empty. The
Swedish lane has a dot at its right end and "23 Oct 2026". The English lane has two grey bars
(2004–2006 and 2007–2009), then a bar from "30 May 2022" to today. Under it the three first
sentences side by side: the Swedish one has "fascistisk" marked, the English one "fascist" and
"pro-Nazi", the Finnish one nothing. Under each sentence is the source the article gives for it, or
a line saying it gives none.

> **Say:** We are Katalyst, and this is Since When. English and Swedish Wikipedia call the Lapua
> Movement fascist in their first sentence. Finnish Wikipedia calls it an anti-communist,
> radical-right popular movement. Swedish added the word three weeks ago, on 23 October. English
> dropped it in 2009, put it back in 2022 and added "pro-Nazi" this April.

## 2. Since when (15 seconds)

Stay on the page. Each date on the strip is a link: "23 Oct 2026" opens the Swedish edit that added
the word, on Wikipedia. Click **5 more edits** under the quotes: the list has "Since 7 April 2026
English Wikipedia added “pro-Nazi”" and the other edits about the same label, each a link to its
edit.

> **Say:** Each difference has the date it began, and the edit that did it. The dates come from
> MariaDB. Every revision of this article is a row version in a system-versioned table.

## 3. Run a query on the versioned table (30 seconds)

Click **Check in MariaDB** under the quotes (or open
<https://since-when.katalyst.fyi/?sql=asof,Q1412941,2022-05-31,en#/Q1412941>).

The panel shows the statement before anything runs: `SET SESSION system_versioning_asof =
'2022-05-31 00:00:00'`, then a `SELECT` from `chunk` with no time clause. Click **Run**. One row:
revision 1090675024, `row_start` 2022-05-30 19:24:45, "… a radical Finnish nationalist, fascist and
anti-communist political movement …". The `row_start` is the date on the page.

Click **Day before**, then **Run** again. One row: revision 1082481405, `row_start` 2022-04-13,
"… a radical Finnish nationalist and anti-communist political movement …". The panel shows one
result at a time.

> **Say:** This panel shows the SQL behind the page, and I can run it. I set the session to the day
> after that edit and read the English first passage with a plain query. "Fascist" is there, and the
> row started on 30 May 2022. Same query, one day earlier: no "fascist". MariaDB chose the row
> version; the query did not change.

The same on the Swedish article:
<https://since-when.katalyst.fyi/?sql=asof,Q1412941,2026-10-22,sv#/Q1412941>, **Run**: revision
59364242, "… utomparlamentarisk och antikommunistisk rörelse som startades 1929". **Day after**
twice, **Run**: revision 59790334, "… nationalistisk, fascistisk och antikommunistisk …".

## 4. Time travel and vector search in one statement (30 seconds)

Open <https://since-when.katalyst.fyi/?sql=nearest,Q1412941,2026-10-24,fi,en#/Q1412941>

Click **Run**. One statement: `FROM chunk FOR SYSTEM_TIME AS OF TIMESTAMP '2026-10-24 00:00:00'`
and `VEC_DISTANCE_COSINE(x.embedding, y.embedding)`. 59 rows in about ten milliseconds, one per
Finnish passage, with its nearest English passage, the distance and a status: 3 covered, 26 partly,
30 missing.

> **Say:** This is the comparison itself. One statement reads the article as of a date with FOR
> SYSTEM_TIME AS OF, and pairs each Finnish passage with its nearest English passage with
> VEC_DISTANCE_COSINE. 59 passages in about ten milliseconds. Thirty have no close match in English.

If there is time, the third statement:
<https://since-when.katalyst.fyi/?sql=history,Q1412941,en#/Q1412941>, **Run**.
`FOR SYSTEM_TIME ALL`: 51 versions of the English first passage, 2003 to today, newest first.
Nothing to say; it is the list the dates in step 2 come from.

## 5. A difference a model found, and how it was checked (25 seconds)

Close the panel and scroll to "7 differences", marked "Checked by Nemotron". The line under it says
NVIDIA Nemotron 3.5 Super VL looked up 212 suggestions in the whole other article and set aside 61,
and that a person closed 4 more. Open the first row, "English says some two thousand people attended
the assembly": the Finnish quote has "3 000" marked.

Click **Check in MariaDB**, then **Run**. The statement reads the quoted words into `@quote`, sets
the session to 14 November 2026 and returns one row: the English passage that holds "some two
thousand people", revision 1300142248, `row_start` 2025-07-12 14:03:45.

Click **How it was checked** on the same row, then **Run**. Two statements: the check's verdict for
this finding, then the statement the check ran, stored with it. 6 rows: the other article's
passages nearest the claim, each with its nearest sentence, the distance and how many of the
claim's numbers and names it matched.

> **Say:** Differences of fact are suggested by NVIDIA Nemotron and then checked by it: each claim is
> looked up in the whole other article, in one MariaDB statement that reads the article as of the
> day, ranks every sentence by vector distance and matches the numbers with REGEXP. What the other
> edition states elsewhere is set aside, with the passage that states it.

## 6. One measurement (25 seconds)

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

## The other two topics: the Finnish War and the Diet of Porvoo

Neither has a loaded word, so each page opens on its first checked difference. The steps are the
same; step 3 uses **Check in MariaDB** on that difference, which returns the passage holding its
quote on 14 November 2026.

> **Say (Finnish War):** Swedish Wikipedia says Turku fell on 22 March 1808. English Wikipedia says
> the Russian army took it on 21 March.

> **Say (Diet of Porvoo):** Finnish Wikipedia says the Diet of Porvoo was convened for 22 March
> 1809. Swedish and English Wikipedia give 25 March.

| Step | Finnish War (`Q736268`) | Diet of Porvoo (`Q2457646`) |
| --- | --- | --- |
| 1, 2, 3, 5 | <https://since-when.katalyst.fyi/#/Q736268> | <https://since-when.katalyst.fyi/#/Q2457646> |
| 4 | <https://since-when.katalyst.fyi/?sql=nearest,Q736268,2026-10-24,fi,en#/Q736268> | <https://since-when.katalyst.fyi/?sql=nearest,Q2457646,2026-10-24,fi,en#/Q2457646> |
| extra | <https://since-when.katalyst.fyi/?sql=history,Q736268,en#/Q736268> | <https://since-when.katalyst.fyi/?sql=history,Q2457646,en#/Q2457646> |

What is on screen:

- **Finnish War, step 1:** "18 differences", marked "Checked by Nemotron"; 356 suggestions looked up,
  78 set aside. The first, open, is headed "Finnish says Russia took Turku four days after 18 March".
  Finnish: "Neljä päivää myöhemmin … valloitti … Turun"; Swedish: "… den 18 mars och Åbo … föll den
  22:a"; English: "… on 21 March and on the same day the Russian army took Turku …". The Finnish and
  English lanes are dated "6 Oct 2012".
- **Finnish War, steps 3 and 5:** **Check in MariaDB**, **Run**: one row, the Finnish passage that
  holds the quote, `row_start` 2022-12-28 23:40:52. **How it was checked**, **Run**: 5 rows.
- **Diet of Porvoo, step 1:** "2 differences"; 90 suggestions looked up, 35 set aside. The first,
  open, is headed "Finnish gives the Diet's opening date as 22 March (10 March Old Style) 1809".
  Finnish: "… kutsuttu koolle 22. maaliskuuta (J: 10. maaliskuuta), ja ne päätettiin 19. heinäkuuta
  …"; Swedish: "Lantdagen sammanträdde 25 mars–18 juli 1809"; English: "between 25 March and 19 July
  1809". The Finnish and English lanes are dated "24 Jun 2025".
- **Diet of Porvoo, steps 3 and 5:** **Check in MariaDB**, **Run**: one row, the Finnish passage
  that holds the quote, `row_start` 2026-09-26 09:21:49. **How it was checked**, **Run**: 4 rows.
- **Step 4:** 31 rows for the Finnish War (4 covered, 19 partly, 8 missing), 17 for the Diet of
  Porvoo (1 covered, 4 partly, 12 missing). **Extra:** 43 and 39 versions.
- Step 6 does not change.

Not for the demo: further down each list some differences are weak. On the Finnish War the headline
of the first difference names only the Finnish wording; read the three quotes, not the headline.
