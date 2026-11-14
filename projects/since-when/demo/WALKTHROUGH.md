# Walkthrough: two and a half minutes, read aloud while clicking

Team Katalyst, MariaDB challenge "Wikipedia Through Time". The product name is "Since When"
(picked by Mikael on 14 Nov; UI title and pitch only, no code renames).

Runs against the public instance, <https://since-when.katalyst.fyi/>. Every step below was clicked
through there late on 14 November 2026, after the last deploy of the review rounds (`main` at
`7fe0368`).

Two things to know before clicking:

- A `?sql=` link opens the SQL panel with the fields filled in. It never runs by itself: click
  **Run**. So do **Check in MariaDB** and **How it was checked** on a difference.
- The part after `#` keeps the topic's page behind the panel. Without it the panel opens over the
  front page.

Lines marked **Say** are the spoken text. Everything else is what to click and what must be on
screen. The order is the story's: MariaDB's history and search do the work; the language model only
suggests what to look at.

## 0. The front page (5 seconds, optional)

Open <https://since-when.katalyst.fyi/>

On screen: "What three Wikipedias say differently, and since when", a chip "How these were found",
a key ("● edit that put the word or the quoted words there · said since · said earlier · 2001 to today"), and
three cards. The first is Lapua Movement: "Swedish and English Wikipedia use “fascist” in their
first sentence; Finnish Wikipedia does not.", with a time strip: Finnish "not said", Swedish
"23 Oct 2026", English "30 May 2022". Under the cards: "Every date here is read from MariaDB 11.8.9: a
system-versioned table keeps 225,816 versions of 39,330 passages, each from the Wikipedia edit that
wrote it …". Click the Lapua card.

## 1. The difference, no SQL on screen (10 seconds)

Open <https://since-when.katalyst.fyi/#/Q1412941>

On screen: "Loaded words", marked "Word list", the strip key, and under them “fascist”, open. Its
time strip is on the right: three lanes, Finnish, Swedish and English, from 2001 to today. The
Finnish lane says "not said". The Swedish lane has a dot at its right end and "23 Oct 2026". The
English lane has two grey bars (2004–2006 and 2007–2009), then a bar from "30 May 2022" to today.
Under it the three first sentences side by side: the Swedish one has "fascistisk" marked, the
English one "fascist" and "pro-Nazi", the Finnish one nothing. Under each sentence is the source the
article gives for it, or a line saying it gives none.

> **Say:** We are Katalyst, and this is Since When. English and Swedish Wikipedia call the Lapua
> Movement fascist in their first sentence. Finnish Wikipedia's first sentence calls it an
> anti-communist, radical-right popular movement. Swedish added the word three weeks ago, on
> 23 October. English dropped it in 2009, put it back in 2022 and added "pro-Nazi" this April.

"In their first sentence" matters: the Finnish introduction goes on to say the movement meets
almost all common definitions of fascism.

## 2. Since when (15 seconds)

Stay on the page. Each date on the strip is a link to that edit on Wikipedia, against its parent
revision: "23 Oct 2026" opens the Swedish edit that put the word there. Click **5 more edits** under
the quotes: the list starts with "Since 7 April 2026 English Wikipedia added “pro-Nazi”", and the
other edits about the same labels follow, each a link.

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
and `VEC_DISTANCE_COSINE(x.embedding, y.embedding)`. 59 rows, one per Finnish passage, with the id of
its nearest English passage, the distance and a status: 3 covered, 26 partly, 30 missing. It takes
about 130 to 250 ms on the public machine.

> **Say:** This is the comparison itself. One statement reads the article as of a date with FOR
> SYSTEM_TIME AS OF, and pairs each Finnish passage with its nearest English passage with
> VEC_DISTANCE_COSINE. Thirty Finnish passages have no close match in English.

If there is time, the third statement:
<https://since-when.katalyst.fyi/?sql=history,Q1412941,en#/Q1412941>, **Run**.
`FOR SYSTEM_TIME ALL`: 51 versions of the English first passage, 2003 to today, newest first; the
current one's `row_end` reads "still current". Nothing to say; it is the list the dates in step 2
come from.

## 5. A difference of fact, and how it was checked (25 seconds)

Open <https://since-when.katalyst.fyi/#/Q736268> (Finnish War).

On screen: "12 differences", marked "Checked by Nemotron". The first, open, is headed "Finnish says
Russia took Turku four days after 18 March; English says the Russian army took Turku on 21 March".
Finnish: "Neljä päivää myöhemmin … valloitti … Turun"; Swedish: "… den 18 mars och Åbo … föll den
22:a", with 18 and 22 marked; English: "… on 21 March and on the same day the Russian army took
Turku …", with 21 marked. The strip: Finnish "8 May 2011", Swedish "26 Dec 2009", English
"6 Mar 2025".

Click **Check in MariaDB**, then **Run**. The statement reads the quoted words into `@quote`, sets
the session to 9 May 2011 and returns one row: the Finnish passage that holds them, revision
10153708, `row_start` 2011-05-08 11:48:31. **Day before**, **Run**: "No rows." The words were not
there yet.

Click **How it was checked**, then **Run**: the statement the check stored with its verdict, run as
it is. 5 rows: the English article's passages nearest the claim, each with its nearest sentence, the
distance and how many of the claim's numbers and names it matched. Those are the passages the
judge was given; its verdict and the sentence it settled on are on the page, under "Checked by
Nemotron".

> **Say:** Differences of fact are suggested by NVIDIA Nemotron and checked by it against the whole
> other article, in one MariaDB statement that ranks every passage by vector distance and matches
> the numbers with REGEXP. Here Swedish says Turku fell on the 22nd, English the 21st, and the
> versioned table shows when each edition's words arrived.

The strip dates mark when an edition's quoted words took their present form, word for word. An
older wording of the same claim can be earlier: say so if asked.

## 6. One measurement (25 seconds)

Stay on the panel.

> **Say:** We measured the vector index on the versioned table, on MariaDB 11.8.9. It works: recall
> is about 0.97 at the default setting. But it holds every version, and it is 5 to 14 times slower
> for past dates. So we keep the index on the current rows and search one topic exactly for the past.
> That is exact and takes milliseconds per topic.

> **Say:** Every statement you saw is fixed on the server and runs as a read-only user with a time
> limit.

The numbers are in [`measurements.md`](measurements.md), "Rerun on a quiet machine": recall@10 of
0.95 to 0.98 at `mhnsw_ef_search` 20, 4.74 ms against 0.35 ms as of 2010 and 1.99 ms against
0.42 ms as of 2020. They were measured offline; no statement on the site uses the index.

## What is on the other pages

- **Lapua Movement:** under "Loaded words", "1 difference" marked "Checked by Nemotron": Swedish
  says 102 leaders were imprisoned after the trial, English about 50. Then "Wording" (not checked),
  the statements one edition leaves out, and "Set aside by the check".
- **Finnish War:** "12 differences"; step 5 uses the first. Step 4 on this topic:
  <https://since-when.katalyst.fyi/?sql=nearest,Q736268,2026-10-24,fi,en#/Q736268>, 31 rows.
- **Diet of Porvoo:** "1 difference": English says the Diet sat from 25 March to 19 July 1809,
  Swedish to 18 July. Its strip: Swedish "24 Aug 2026", English "18 Mar 2025". Step 4:
  <https://since-when.katalyst.fyi/?sql=nearest,Q2457646,2026-10-24,fi,en#/Q2457646>, 17 rows.
- The chips say how far to trust each list: a row a further review by language models found false
  is closed, and no person has checked any of them. The reasons are in
  [`hand-checked.json`](hand-checked.json).

Not for the demo: further down the Finnish War list some differences are weaker (figures a few
hundred apart). Read the three quotes, not only the headline.
