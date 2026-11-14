# The claim check on the hero topics: what it does to the findings

14 November 2026. The claim check is described in
[`differences/README.md`](../differences/README.md#the-claim-check); this file has its measured
results on the three hero topics (Lapua Movement `Q1412941`, Finnish War `Q736268`, Diet of Porvoo
`Q2457646`), against the hand judgements of [`hero-findings-notes.md`](hero-findings-notes.md).
`M=~/junction2026-data/mariadb`; commands run from `projects/since-when/`.

The judge is **Nemotron 3.5 Super VL** on the Verda container unless a table says otherwise. Claude
Haiku 5.5 and Nemotron 3.5 Lightning judged the same claims as comparisons. `checked_finding` in
the scratch database holds the Super VL run of the current pairs.

Gemini Decision as the judge, measured on the same labels:
[`hero-verify-gemini-decision.md`](hero-verify-gemini-decision.md).

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
rows' own claims (`$M/classify/verify/labelled-<judge>/`), without the figures the check lists
itself.

| Type | Judge | False rows: gone / moved / kept | Real rows: kept / moved / gone | Unclear rows: kept / moved / gone |
| --- | --- | --- | --- | --- |
| missing fact | before | 5: 0 / 0 / 5 | 10: 10 / 0 / 0 | 9: 9 / 0 / 0 |
| | **Nemotron 3.5 Super VL** | 5: 2 / 1 / 2 | 10: 9 / 1 / 0 | 9: 5 / 1 / 3 |
| | Haiku 5.5 | 5: 3 / 1 / 1 | 10: 9 / 1 / 0 | 9: 4 / 2 / 3 |
| | Nemotron 3.5 Lightning | 5: 3 / 1 / 1 | 10: 9 / 1 / 0 | 9: 5 / 0 / 4 |
| numbers | before | 11: 0 / 0 / 11 | 9: 9 / 0 / 0 | 3: 3 / 0 / 0 |
| | **Nemotron 3.5 Super VL** | 11: 9 / 1 / 1 | 9: 9 / 0 / 0 | 3: 2 / 0 / 1 |
| | Haiku 5.5 | 11: 9 / 1 / 1 | 9: 8 / 1 / 0 | 3: 1 / 0 / 2 |
| | Nemotron 3.5 Lightning | 11: 9 / 1 / 1 | 9: 6 / 1 / 2 | 3: 2 / 0 / 1 |
| contradiction | before | 2: 0 / 0 / 2 | none labelled real | 5: 5 / 0 / 0 |
| | **Nemotron 3.5 Super VL** | 2: 1 / 1 / 0 | | 5: 1 / 0 / 4 |
| | Haiku 5.5 | 2: 1 / 1 / 0 | | 5: 2 / 0 / 3 |
| | Nemotron 3.5 Lightning | 2: 2 / 0 / 0 | | 5: 2 / 0 / 3 |
| framing | before and after | 5: 0 / 0 / 5 | 14: 14 / 0 / 0 | 2: 2 / 0 / 0 |

Framing is not checked, so its five false rows stay. Lightning loses two real numbers rows (102 or
about 50 leaders; 1 000 or 1,100 men): it finds the right sentence and calls the claim not
mentioned.

What the moved rows are, with Super VL:

- The false missing fact "the Finnish dates of the diet are missing in English" became a numbers
  row, 22 March in Finnish against 25 March in English: English has the dates, and they differ.
- The real missing fact "banned on 21 November 1932, missing in Finnish" became a numbers row
  against the Finnish sentence that dates the ban to 29 February: the same difference, as two
  dates.
- The false numbers row "11 000 under Moore against a hypothetical 10,000" became 11 000 against
  the English sentence that gives 14,000: the difference the notes said the tool should show.
- The false contradiction "the landing at Vaasa against another landing" became the numbers row
  1 000 against 1,100 men landed at Vaasa, which the notes list as real.
- The unclear missing fact "an assembly of some two thousand, missing in Finnish" became a
  numbers row against the Finnish "up to 3 000".

What stays wrong on the labels with Super VL: two false missing facts are kept (the general strike
of November 1929, and the retreat "at 40 degrees below": each sentence holds several facts, one of
them is in the other edition, and the verdict is not mentioned), and "five years against three
years" is kept as a numbers row (a law's term against the term one party would accept; the judge
calls it contradicted from both sides).

## The full run on the current pairs, judged by Super VL

`$M/classify/verify/current-super/`: the 125 pairs and 735 rows the scratch database holds, with
the figures the check lists itself. 1,569 claims (746 from the classifier's rows, 823 figures and
dates from 112 passages): 1,057 not mentioned, 366 supported, 146 contradicted. The statements
behind 126 contradicted claims were looked up back, and 91 held from both sides. Of 410 verdicts
with two readable figures, the arithmetic overruled the judge in 15.

| | Before | After, Super VL | After, Haiku 5.5 |
| --- | --- | --- | --- |
| missing fact | 688 | 493; 165 set aside as stated elsewhere, 13 became numbers or contradiction rows, the rest repeat one | 435; 224 set aside |
| numbers | 23 | 31: 13 of the classifier's, 10 that were missing facts, 8 from figures the check listed | 31 |
| contradiction | 6 | 6: 3 of the classifier's, 3 that were missing facts | 5 |
| framing | 18 | 18 | 18 |

Hand check, as the notes did it: every numbers and contradiction row read against both articles,
and a seeded sample of 24 kept missing facts and 20 set-aside ones searched in the whole other
article (`python3 demo/hero_sample.py`, seed 5).

| | Rows | Real or plausible | False | Unclear or partly there |
| --- | --- | --- | --- | --- |
| numbers, before (the notes) | 23 | 9 | 11 | 3 |
| numbers, after, Super VL | 31 | 24 | 4 | 3 |
| numbers, after, Haiku 5.5 (first run's pairs) | 33 | 25 | 5 | 3 |
| contradiction, before (the notes) | 7 | 0 | 2 | 5 |
| contradiction, after, Super VL | 6 | 2 | 1 | 3 |
| contradiction, after, Haiku 5.5 | 5 | 2 | 1 | 2 |
| missing fact kept, before (the notes' sample) | 24 | 10 | 5 | 9 |
| missing fact kept, after, Super VL (sample) | 24 | 16 | 3 | 5 |
| missing fact kept, after, Haiku 5.5 (sample) | 24 | 17 | 1 | 6 |
| missing fact set aside, Super VL (sample): was it right to set it aside? | 20 | 19 right | 0 wrong | 1 partly |
| missing fact set aside, Haiku 5.5 (sample) | 20 | 18 right | 0 wrong | 2 partly |

The Haiku hand check was made on the first run's pairs, before repeats were merged.

Numbers findings the old flow did not have, with Super VL: 7 700 or 11,000 men under Kamensky at
Kuortane; Klingspor took command on 1 or 2 March (Finnish and Swedish against English); Turku
fell on 21 or 22 March; the diet closed on 18 or 19 July; Gotland was taken with 1 600 or about
1 800 men; the first Lapua assembly had "some two thousand" or "up to 3 000" people; Moore's
force of 11 000 or 14 000, now against the right English and Swedish sentences. A new
contradiction: Finnish says Russia had no intention of annexing Finland before the war, Swedish
that the war was planned to incorporate it.

## What is still wrong

- **Two steps of one course of events set against each other** (2 of Super VL's 4 false numbers
  rows): a government that resigned on 2 July and its successor of 4 July; a landing on 14 May
  and the island retaken on the 16th. The prompt names the pattern; the judge calls these
  contradicted from both sides.
- **The same statement in two languages called a contradiction**: "before the end of the 1800s"
  against "before the late 19th century". One row, from a figure the check listed.
- **A term against a term**: the law limited to five years against the three years one party
  would accept.
- **One man under two forms of his name** ("Ernst" and "Eberhard" von Vegesack) is still a
  contradiction.
- **A sentence with several facts is one claim.** If one of its facts is in the other edition and
  another is not, the verdict is not mentioned and the row is kept: 5 of the 24 sampled kept rows
  are "partly there", and 2 of the 3 false ones are of this kind (the Grand Duchy "until 1917";
  Moore's army with its 62 transports).
- **The fact is in the passage next to the one the search returned.** English says the movement
  began with the attack on a communist youth parade in November 1929; the Finnish section on that
  event is two passages, the search returned the first and the attack is in the second. One of
  the 24.
- **Real disagreements of account are lost**: of the five contradictions the notes left "for a
  human", one survives on the labelled rows (who won at Pyhäjoki). In the full run the military
  establishment at Porvoo survives too, and Sandels at Toivala "until October" against a retreat
  after 26 September comes back as a numbers row. Who attacked at Siikajoki and who averted the
  threat to Stockholm are lost: they are not contradicted claim by claim, because each edition
  tells another part of the story. The verdict on such a row also changes with the other claims
  judged in the same call.
- **Framing is unchecked.** Its five false rows ("kapina" against "coup d'état", where the Finnish
  introduction says "vallankaappausyritys") need the same lookup for a word, not a claim.
- **A count against a list.** On the older labels the check loses "Speaker six times" against five
  listed years (see the older labels below). A classifier row whose sentence has three figures is
  still one claim, and the judge compares the first; the figure is found only when the check
  also lists it itself, and that list is capped at ten a passage.
- **Super VL sets aside fewer missing facts than Haiku** (165 against 224) and keeps more false
  ones in the sample (3 against 1 of 24). It asks for the whole sentence to be stated.

## The older labels in `differences/eval/`

The 46 lead pairs of 16 topics, labelled by type per pair. The classifier (prompt version 6)
ran on them again with Super VL on the Verda container, 331 rows
(`$M/classify/verify/eval/rows.jsonl`); `python -m differences.evaluate_rows` scores rows on
disk, precision / recall:

| | missing fact | contradiction (1 labelled) | framing | numbers |
| --- | --- | --- | --- | --- |
| classifier rows, before the check | 0.98 / 1.00 | 0.33 / 1.00 | 0.76 / 0.86 | 0.92 / 1.00 |
| after the check, Super VL | 1.00 / 0.93 | 0.33 / 1.00 | 0.76 / 0.86 | 0.57 / 0.73 |

`$M/classify/verify/eval-super/`: 850 claims against the 16 topics' articles as of 13 November
(`FOR SYSTEM_TIME AS OF TIMESTAMP '2026-11-13 00:00:00'`), 191 rows after the check.

**Numbers got worse by these labels**, and the two halves of that are different things:

- *Recall, 11 of 11 pairs to 8 of 11.* Three labelled differences are lost, two of them real
  losses: Kallio was Speaker "six times" in Finnish and English where Swedish lists five years,
  a count against a list, which the judge calls not mentioned (two pairs). The third, "about a
  tenth" of the territory against "9%", it calls supported, which is arguable. A fourth was lost
  until the last fix: the Reds who died in the camps, 11,652 in Finnish and about 12,500 in
  English, was hidden behind a vaguer row on the same English sentence.
- *Precision, 11 of 12 pairs to 8 of 14.* Six pairs now have a numbers row the labels do not.
  The labels say what two leads differ in; the check compares a lead's claims with the whole
  other article. Read by hand, five of the seven new rows are real differences the labels do not
  have: Finland declared war on 25 or 26 June 1941; the Lapua Movement was banned in May or on
  21 November 1932; about twenty or 52 people were sentenced to prison after Mäntsälä (two
  pairs); the defence forces were reorganised in 1933 or 1934. Two are doubtful (the leaders
  arrested "after a week" or the arrest ordered "two days later"; the king's election under the
  constitution of 1772 or the law of 1734).

Missing facts lose three pairs for the same reason, in the other direction: every fact the
classifier found missing in those leads is stated in the body of the other article. Framing
cannot change: the check does not touch it.

## Design choices

- **A missing fact that the other edition states elsewhere is set aside, not turned into a weaker
  "placed elsewhere" finding.** A quarter to a third of the missing facts are of this kind; as
  findings they would crowd the page with differences of structure, which the coverage findings
  already show. They are kept with the passage that states the fact (`set-aside.jsonl`, and
  `checked_finding` with `outcome = 'set_aside'`), so the page can say how many were dropped and
  show where the fact is.
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
- **One difference is one row.** A row that repeats a statement and its figure against a second
  sentence of the other edition is set aside as a repeat.
- **Claims of one passage are judged six to a call**: about 400 calls for the hero topics instead
  of 1,600.

## Models and calls

- NVIDIA Build refused most requests to Nemotron 3.5 Super VL on 14 November (HTTP 429 with
  `Nvcf-Error-Source: upstream_status`: the model's capacity, not the key's limit), and answered
  about three a minute for Lightning.
- The Verda container (`verda-super`) answered every request: about 5.5 minutes after it was sent
  while the gap finder's run shared it, under a minute later in the day. The full run took 50
  minutes with 24 workers.
- Haiku 5.5: the labelled rows take about a minute, the full run twelve, most of it embedding the
  claims.
- Every answer is cached under `$M/classify/verify/cache/<judge>/`; `sh demo/hero-verify.sh …
  --offline` rebuilds a run's files without a model call.
