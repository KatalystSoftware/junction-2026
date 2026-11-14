# The claim check on the hero topics: what it does to the findings

14 November 2026. The claim check is described in
[`differences/README.md`](../differences/README.md#the-claim-check); this file has its measured
results on the three hero topics (Lapua Movement `Q1412941`, Finnish War `Q736268`, Diet of Porvoo
`Q2457646`), against the hand judgements of [`hero-findings-notes.md`](hero-findings-notes.md).
`M=~/junction2026-data/mariadb`; commands run from `projects/since-when/`.

Gemini Decision as the judge, measured on the same labels:
[`hero-verify-gemini-decision.md`](hero-verify-gemini-decision.md).

**Pending:** the tables judged by Nemotron 3.5 Super VL. That run is in progress on the Verda
container. Until it is in, the tables below are judged by Claude Haiku 5.5 and Nemotron 3.5
Lightning, and `checked_finding` in the scratch database holds the Haiku-judged run.

## The labels

[`hero-labels.json`](hero-labels.json) holds the 75 rows of Nemotron's first full run (127 pairs,
721 rows) that the notes judged: all 23 numbers, 7 contradiction and 21 framing rows and the seeded
sample of 24 missing facts. The rows are rebuilt from the answer cache and
`$M/classify/agent4/pairs-run1.jsonl`; the sample is the same 24 rows the judge printed
(`random.seed(4)`). The counts per type equal the notes' table.

The notes name each numbers, contradiction and framing row. For the missing-fact sample they give
the totals (10 real, 5 false, 9 unclear) and name the five false rows; the judge's working summary
names four unclear ones. The split of the other 15 into 10 real and 5 unclear is rebuilt from the
judge's searches: each label says which of the three it rests on. Three labels carry a `recheck`,
where a search of the stored article contradicts them (two "unclear" rows are in fact stated in
the other edition); the scorer prints a second table with those applied.

`python3 demo/hero_score.py RUN/differences.jsonl -v` asks of each labelled row whether the run
still reports it: `kept` (same type, same quotes), `moved` (a row the check wrote that carries one
of its quotes, against other evidence or under another type) or `gone`.

## Before and after, on the 75 labelled rows

Before is the first full run as it was: every row present. The claim check ran on the labelled
rows' own claims, without the figures the check lists itself.

| Type | Judge | False rows: gone / moved / kept | Real rows: kept / moved / gone | Unclear rows: kept / moved / gone |
| --- | --- | --- | --- | --- |
| missing fact | before | 5: 0 / 0 / 5 | 10: 10 / 0 / 0 | 9: 9 / 0 / 0 |
| | Haiku 5.5 | 5: 3 / 1 / 1 | 10: 9 / 1 / 0 | 9: 4 / 2 / 3 |
| | Nemotron 3.5 Lightning | 5: 4 / 0 / 1 | 10: 9 / 1 / 0 | 9: 5 / 0 / 4 |
| | Nemotron 3.5 Super VL | pending | | |
| numbers | before | 11: 0 / 0 / 11 | 9: 9 / 0 / 0 | 3: 3 / 0 / 0 |
| | Haiku 5.5 | 11: 9 / 1 / 1 | 9: 8 / 1 / 0 | 3: 1 / 0 / 2 |
| | Nemotron 3.5 Lightning | 11: 9 / 1 / 1 | 9: 5 / 1 / 3 | 3: 2 / 0 / 1 |
| | Nemotron 3.5 Super VL | pending | | |
| contradiction | before | 2: 0 / 0 / 2 | none labelled real | 5: 5 / 0 / 0 |
| | Haiku 5.5 | 2: 1 / 1 / 0 | | 5: 2 / 0 / 3 |
| | Nemotron 3.5 Lightning | 2: 2 / 0 / 0 | | 5: 2 / 0 / 3 |
| | Nemotron 3.5 Super VL | pending | | |
| framing | before and after | 5: 0 / 0 / 5 | 14: 14 / 0 / 0 | 2: 2 / 0 / 0 |

Framing is not checked, so its five false rows stay.

What the moved rows are (Haiku):

- The false missing fact "the Finnish dates of the diet are missing in English" became a numbers
  row, 22 March in Finnish against 25 March in English: English has the dates, and they differ.
- The real missing fact "banned on 21 November 1932, missing in Finnish" became a numbers row
  against the Finnish sentence that dates the dissolution to 24 March and 28 May: the same
  difference, now as two dates. The labelled numbers row on the same ban moved to that sentence.
- The false numbers row "11 000 under Moore against a hypothetical 10,000" became 11 000 against
  the English sentence that gives 14,000: the difference the notes said the tool should show.
- The false contradiction "the landing at Vaasa against another landing" became the numbers row
  1 000 against 1,100 men landed at Vaasa, which the notes list as real.

What stays wrong on the labels, with both judges: the Swedish retreat "at 40 degrees below" is
kept as missing in Finnish (the sentence holds three facts and only the temperature is in
Finnish), and "five years against three years" is kept as a numbers row (a law's term against the
term one party would accept).

Lightning loses three real numbers rows (102 or about 50 leaders; 22 or 25 March; 1 000 or 1,100
men): it finds the right sentence and calls the claim not mentioned.

## The full run, judged by Haiku 5.5, and a hand check of rows the labels do not cover

`$M/classify/verify/run1-haiku/`: the first run's 127 pairs and 721 rows, with the figures the
check lists itself. 1,508 claims (730 from the classifier's rows, 778 figures and dates from 112
passages): 958 not mentioned, 421 supported, 129 contradicted. The statements behind 110 of the
contradicted ones were looked up back, and 77 held from both sides.

| | Before | After |
| --- | --- | --- |
| missing fact | 670 | 414; 228 set aside as stated elsewhere, the rest became numbers or contradiction rows or repeat one |
| numbers | 23 | 31 (22 from classifier rows, of which most were missing facts; 9 from figures the check listed) |
| contradiction | 7 | 5 |
| framing | 21 | 21 |

Hand check, as the notes did it: every numbers and contradiction row read against both articles,
a seeded sample of 24 kept missing facts and 20 set-aside ones searched in the whole other
article (`python3 demo/hero_sample.py`, seed 5). This check was made on the output before repeats
were merged, which had 33 numbers rows.

| | Rows | Real or plausible | False | Unclear or partly there |
| --- | --- | --- | --- | --- |
| numbers, before (the notes) | 23 | 9 | 11 | 3 |
| numbers, after | 33 | 25 | 5 | 3 |
| contradiction, before (the notes) | 7 | 0 | 2 | 5 |
| contradiction, after | 5 | 2 | 1 | 2 |
| missing fact kept, before (the notes' sample) | 24 | 10 | 5 | 9 |
| missing fact kept, after (sample) | 24 | 17 | 1 | 6 |
| missing fact set aside (sample): was it right to set it aside? | 20 | 18 right | 0 wrong | 2 partly |

New numbers findings the old flow did not have: 7 700 or 11,000 men under Kamensky at Kuortane;
Klingspor took command on 1 or 2 March; Turku fell on 21 or 22 March; the diet closed on 18 or 19
July; the first Lapua assembly had "some two thousand" or "up to 3 000" people.

## What is still wrong

- **Two steps of one course of events set against each other** (4 of the 5 false numbers rows):
  the Russians reached Revolax on 24 April and the battle was on the 27th; a decision to attack
  and the battle four days later; a landing on 14 May and the island retaken on the 16th; the
  diet sitting from 25 March and its invitation of 1 February. The judge calls these
  contradictions from both sides. The prompt names the pattern and Haiku does not hold to it.
- **One man under two forms of his name** ("Ernst" and "Eberhard" von Vegesack) is still a
  contradiction, now between Finnish and Swedish.
- **A sentence with several facts** is one claim. If one of its facts is in the other edition and
  another is not, the verdict is not mentioned and the row is kept; six of the 24 sampled kept
  rows are "partly there" for this reason.
- **Real disagreements of account are lost**: of the five contradictions the notes left "for a
  human", two survive. The other three (who attacked at Siikajoki; Sandels at Toivala until
  October; who averted the threat to Stockholm) are not contradicted claim by claim, because each
  edition tells another part of the story.
- **Framing is unchecked.** Its five false rows ("kapina" against "coup d'état", where the Finnish
  introduction says "vallankaappausyritys") need the same lookup for a word, not a claim.
- **The judge matters.** Lightning loses a third of the real numbers rows. Whether Super VL does
  better is the pending measurement.
- **Not measured:** the older labels in `differences/eval/` (46 pairs). The sentences of their 16
  topics are embedded in the database, but the classifier's rows for those pairs are in no cache
  here, and the Nemotron endpoints were too slow on the day to make them.

## Design choices

- **A missing fact that the other edition states elsewhere is set aside, not turned into a weaker
  "placed elsewhere" finding.** A third of the missing facts are of this kind; as findings they
  would crowd the page with differences of structure, which the coverage findings already show.
  They are kept with the passage that states the fact (`set-aside.jsonl`, and `checked_finding`
  with `outcome = 'set_aside'`), so the page can say how many were dropped and show where the
  fact is.
- **One engine for both changes.** A claim is looked up in the whole other article and gets one
  verdict; a missing fact is a claim that must come back not mentioned, a numbers or
  contradiction finding is a claim that comes back contradicted. The pair classifier stays as the
  proposer of missing facts and framing; for numbers the check also lists a passage's figures
  itself.
- **The search ranks passages by their nearest sentence**, in a table of sentence vectors, not by
  the passage vector. With passage vectors the passage that states a claim ranked 12th to 15th of
  59; with sentences it ranks first.
- **A contradiction must hold from both sides.** The statement that contradicts a claim is looked
  up back in the claim's own edition; if that edition says it too, there is no finding. This
  removes the rows where one edition gives two figures (the day a pledge was given, and the date
  written in the document).
- **Whether two figures agree is computed**, from the figures the judge copies: about 12,000
  against 12,600 differs, over 3,000 against 3,600 agrees, May 1808 against 6 May 1808 agrees.
- **Claims of one passage are judged six to a call.** A call per claim would be 1,600 calls for
  the hero topics.

## Models and calls

- NVIDIA Build refused most requests to Nemotron 3.5 Super VL on 14 November (HTTP 429 with
  `Nvcf-Error-Source: upstream_status`: the model's capacity, not the key's limit), and answered
  about three a minute for Lightning.
- The Verda container (`verda-super`) answers every request, about 5.5 minutes after it is sent
  when 12 are waiting.
- Haiku 5.5: the labelled rows take about a minute, the full run twelve, most of it embedding the
  claims.
- Every answer is cached under `$M/classify/verify/cache/<judge>/`; `sh demo/hero-verify.sh …
  --offline` rebuilds a run's files without a model call.
