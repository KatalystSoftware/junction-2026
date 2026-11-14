# Hero findings: notes of builder 4

Night of 2026-11-14, branch `feat/mariadb-hero-findings`. The shortlist is `hero-findings.md`
(written from `hero-findings.json` by `check_quotes.py --write`). This file says how the rows got
into the scratch database, how to put them back, what the two models said, and what I decided.

`M=~/junction2026-data/mariadb`, `R` = `projects/since-when/`, where the commands run. Topics: Lapua Movement `Q1412941`,
Finnish War `Q736268`, Diet of Porvoo `Q2457646`.

## Put my rows back after a fresh restore of the snapshot

No model is called and nothing is fetched: answers come from `$M/classify/nemotron/cache/` and the
rendered revisions from `$M/revisions/agent4/`. The whole replay takes under a minute.

```bash
R=$PWD; M=$HOME/junction2026-data/mariadb
run() { docker run --rm --network gapfinder-scratch-net --env-file $M/scratch.env -e DB_HOST=gapfinder-scratch-db -e DB_PORT=3306 \
  -v $R/gapfinder:/app/gapfinder:ro -v $R/differences:/app/differences:ro -v $M/classify:/classify:ro --memory 1500m "$@"; }

# 1. the aligned-but-different pairs of the three topics, as the database has them now
run --name gapfinder-a4-pairs since-when \
  python -m gapfinder pairs --only Q1412941 Q736268 Q2457646 > $M/classify/agent4/pairs.jsonl

# 2. Nemotron's answers from the disk cache; must print "this run sent 0 requests" and "0 pairs without an answer"
nix develop -c python3 demo/hero_classify.py nemotron $M/classify/agent4/pairs.jsonl --offline

# 3. remove the model's older rows of the three topics (the snapshot has Lapua rows of 2026-11-13,
#    and a pair that is no longer aligned would keep its rows); lexicon rows stay
echo "delete from difference where wikidata_id in ('Q1412941','Q736268','Q2457646') and source in ('llm','both')" | $M/bin/scratch-sql

# 4. insert the rows and rebuild the three topics' findings (6 s)
run --name gapfinder-a4-load since-when \
  python -m gapfinder findings load /classify/nemotron/differences.jsonl

# 5. the shortlist's quotes against the cached revisions
nix develop -c python3 demo/check_quotes.py --offline
```

If step 2 lists pairs without an answer, the passages changed since my last run (the cache key is
the prompt version, endpoint, model, settings and both passage texts; the pair id and date are not
in it). Classify those through the key, a few calls:

```bash
DIFFERENCES_RPM=12 nix develop -c sops exec-env ../../secrets/secrets.yaml \
  "python3 demo/hero_classify.py nemotron $M/classify/agent4/pairs.jsonl --workers 4"
```

The second opinion and the agreement counts, also from disk:

```bash
nix develop -c python3 demo/hero_classify.py haiku $M/classify/agent4/pairs.jsonl --offline
nix develop -c python3 demo/hero_agree.py     # writes $M/classify/agreement.json
```

Finding ids are stable inside one database (the key of a finding is topic, editions, type, section
and the quote), but a fresh restore or the live database numbers them anew. The shortlist's tool
links name the pair of editions and the finding id of my scratch database; after a restore find a
finding by its quote in `GET /api/topics/<QID>`.

## Where things are

| What | Where |
| --- | --- |
| Nemotron raw answers, one file per pair and prompt version | `$M/classify/nemotron/cache/<key>.json` |
| Which pair has which cache file (pair id, prompt version, revision ids, SHA-1 of both passage texts) | `$M/classify/nemotron/index.jsonl` |
| The rows loaded into `difference` | `$M/classify/nemotron/differences.jsonl` |
| Haiku, same layout, never loaded | `$M/classify/haiku/` |
| Nemotron's rows with Haiku's category for the same thing | `$M/classify/agreement.json` |
| Pairs files and run logs | `$M/classify/agent4/` |
| Rendered revisions for the quote check | `$M/revisions/agent4/<lang>/<rev>.parse.json`, `.info.json` |

## Calls and time

| Model | Requests | Answered | Tokens in / out | Time |
| --- | --- | --- | --- | --- |
| Nemotron `nvidia/nemotron-3.5-super-vl-120b-a12b`, prompt version 6 | 142 | 142 | 225,707 / 1,763,308 | 2789 s for 127 pairs, 114 s for 4 more, 261 s for 11 more |
| Haiku `claude-haiku-5-5`, prompt version 6 | 178 of the 300 allowed | 142 | 396,823 / 260,866 for the last 141 | 410 s for 126 pairs, 16 s for 4 more, 51 s for 11 more |

- Nemotron: one request per pair, 4 workers, `DIFFERENCES_RPM=12`; no 429, no failed pair. The
  count is in `$M/classify/nemotron/requests.json`, which the runner raises before every request.
- Haiku: the first 37 requests were a first try on Lapua Movement, most of them refused with HTTP
  400 (`temperature`, then the schema's `maxItems`; decision 6). They count against the 300.
  Count in `$M/classify/haiku/requests.json`.
- The 4 and the 11 extra requests per model: builder 1 changed the cleaned text of the English
  Lapua introduction at about 05:20 and of three fallback introductions at about 05:45
  (decisions 12 and 14).
- Replay from the cache: 1 s for the answers, 6 s for the load. A snapshot restore takes 141 s.
- Rendered revisions fetched from Wikipedia for the quote check: one `parse` and one `info`
  request per revision named in the shortlist, plus the ones I read to date the "fascist" wording;
  all under `$M/revisions/agent4/`.

## What is in scratch

After the last load (06:58 EET): 125 pairs (Lapua Movement 41, Finnish War 69, Diet of Porvoo 15),
735 rows, none dropped by the loader; the loader's quote check (verbatim in the passage) passed
for every row.

| Topic | missing fact | numbers | contradiction | framing | Open findings in the API of a type other than coverage |
| --- | --- | --- | --- | --- | --- |
| Lapua Movement | 235 | 6 | 0 | 12 | 219 |
| Diet of Porvoo | 87 | 4 | 1 | 3 | 92 |
| Finnish War | 366 | 13 | 5 | 3 | 354 |

All rows have `as_of` 2026-11-14 and `source` `llm`, or `both` where the word list found the same
(10 Lapua rows). 23 pairs got an empty answer from Nemotron (no difference).

Lapua Movement findings of a type other than framing that passed the quote check (done-check 2):
numbers 14096, 13531, 13596; missing fact 13980, 13988, 14087, 14059. They are open in
`GET /api/topics/Q1412941` and shown at `#/Q1412941/sv/en/findings` and `#/Q1412941/en/fi/findings`.

## Agreement between the two models

Both models answered all 125 pairs. Pairs: both found nothing 10; Nemotron nothing and Haiku
something 13; Nemotron something and Haiku nothing 4; both something 98. Haiku wrote 288 rows,
Nemotron 735.

Nemotron's rows, by what Haiku said about the same thing (two rows are about the same thing when
their quotes from one edition share half of the shorter quote's words):

| Nemotron | Rows | Haiku same category | contradiction | numbers | missing fact | framing | Haiku nothing |
| --- | --- | --- | --- | --- | --- | --- | --- |
| contradiction | 6 | 4 | 4 | 0 | 0 | 0 | 2 |
| numbers | 23 | 17 | 1 | 17 | 0 | 0 | 5 |
| missing fact | 688 | 147 | 7 | 1 | 147 | 1 | 532 |
| framing | 18 | 13 | 1 | 0 | 0 | 13 | 4 |

Haiku rows with no Nemotron row about the same thing: contradiction 13, numbers 5, missing fact
73, framing 5.

Read with care: agreement is not truth. Both models call the pledge date of Porvoo and the
five-or-three-years row "numbers", and both are wrong there. Of the 11 rows where the two give
different categories, Haiku says contradiction in 9.

## What I saw: false positives per category on the hero topics

Judged by hand from the quotes and, where a row says something is missing, a search of the whole
rendered article of the other edition. Counts are of Nemotron's rows of the first full run
(127 pairs, 721 rows).

| Category | Rows | Real or plausible | False | For a human / unclear |
| --- | --- | --- | --- | --- |
| numbers | 23 | 9 | 11 | 3 |
| contradiction | 7 | 0 | 2 | 5 |
| framing | 21 | 14 | 5 | 2 |
| missing fact (sample of 24 of 670, 8 per topic, seed 4) | 24 | 10 | 5 | 9 |

- **numbers.** Lapua 6: 3 real (ban date, 12,000 or 12,600 marchers, 102 or about 50 leaders),
  2 false (a law limited to five years against a party willing to accept three: two quantities;
  a founding meeting of November 1930 against an origin in November 1929: two events), 1 for a
  human (72 men, 9 April or 4 April). Diet of Porvoo 4: 1 real (22 or 25 March), 3 false (three
  rows that set the day the pledge was given, 29 March, against the date written in the document,
  "15th/27th day of March"; English has 29 March too). Finnish War 13: 5 real, 6 false or
  compatible (the brigade left Kuopio on the 15th and the Russians took it on the 16th; Finnish
  11 000 and Swedish 14 000 men under Moore each set against an English sentence about a
  hypothetical 10,000, while English has 14,000 elsewhere; "early May" against 6 May; 3 600
  against "over 3,000"), 2 unclear.
  The pattern: the model compares two numbers that stand near each other and are not about the
  same thing.
- **contradiction.** 2 false: the landing at Vaasa set against Gyllenbögel's landing of 1 August,
  and "Ernst von Vegesack" against "Eberhard von Vegesack", who is one man (Eberhard Ernst
  Gotthard). The other 5 are real disagreements between the texts that need the sources to settle;
  two are in the shortlist under "Needs a human look".
- **framing.** Lapua 14: 8 real or plausible, 5 false (four rows say Finnish calls Mäntsälä a
  "kapina" and English a "coup d'état", although the Finnish introduction says "aseellinen
  vallankaappausyritys" and English also says "Mäntsälä rebellion"; one sets two unrelated
  sentences against each other), 1 weak. Diet of Porvoo 3: none false. Finnish War 4: 3 plausible,
  1 weak.
- **missing fact.** 670 of the 721 rows, and 60 of them do not say which edition lacks the fact.
  Haiku reported the same thing for 144. In the sample 10 hold against the whole article, 5 are
  false and 9 are partly there or could not be settled by a search. Every false one is the same
  mistake: the fact is in the other edition, in a passage the pair did not include. Examples:
  "banned in 1944 on the orders of the Soviet Union" said to be missing in Finnish, which has
  "Puolue lakkautettiin Moskovan välirauhansopimuksen nojalla 23. syyskuuta 1944"; the general
  strike of November 1929 said to be missing in English, which has "A general strike was also
  declared in November"; a retreat at −40° said to be missing in Finnish, which has "pakkasta oli
  peräti 40 astetta"; the Finnish first sentence of Diet of Porvoo (a definition) said to be
  missing in English. Earlier checks found the same for the Ståhlberg kidnapping and the Peasant
  March, both "missing in Finnish" in the tool and both in the Finnish article.
  This is the tester's "about half are false" seen from inside: the classifier sees two passages
  and the claim is about two articles. A check of each missing fact's names and numbers against
  the other edition's full text before it becomes a finding would remove most of them; that is
  classifier work and out of my scope.

## Left out of the shortlist, and spares

- Lapua: the five-or-three-years row and the November 1930 or 1929 row (false, above); the
  Mäntsälä "kapina" rows; the Ståhlberg and Peasant March "missing in Finnish" findings.
- Diet of Porvoo: the pledge-date rows (false); "regentförsäkran upprepades" said to be missing
  in English, which has a section per successor; Jussila's "herruussopimus" (English cites
  Jussila); Swedish kept as the language of administration (Finnish mentions the position of
  Swedish among the petitions).
- Finnish War, spares that hold if one of the three has to go: 1 000 (sv) or 1,100 (en) men
  landed at Vaasa, numbers in both models; about 8 000 (fi) or 7 000 (sv) men in the retreat.
  Moore's force, 11 000 in Finnish and 14 000 in Swedish and English, is real, but the tool
  quotes the wrong English sentence for it.

## Decisions

1. **Plain text of a revision = the page as rendered** (`action=parse`), minus footnote markers,
   edit links, styles and scripts: what a reader sees at the permanent link. Builder 1's
   `revisions/<qid>/<lang>.jsonl.gz` holds wikitext and is read-only for others, so I fetched the
   rendered revisions under rule 7 and cached them under `$M/revisions/agent4/`.
2. **A shortlist quote may be a part of the classifier's quote**, or continue it inside the same
   passage, because gapfinder's cleaned passage text differs from the rendered page where
   templates are involved. Extra quotes from a third edition or from another finding of the same
   pair carry a note saying so.
3. **The checker makes no "absent" claims.** Where a statement says an edition does not mention
   something, I searched the whole rendered article by hand.
4. **Main list = both models give the same category and the two quotes are about the same
   thing.** Findings both models label the same but that compare two quantities or events are
   left out. A contradiction, or a disagreement between the models, is under "Needs a human look".
5. **Three main findings per fallback topic**, as asked; the Tikkanen 1847 quote is folded into
   the Diet of Porvoo name finding.
6. **Classifier code unchanged.** Haiku refuses a request that sets `temperature` and a schema
   with `maxItems` (HTTP 400), so `hero_classify.py` drops both for Haiku only. For the owner:
   `DIFFERENCES_PROVIDER=anthropic` with `claude-haiku-5-5` does not work as shipped.
7. **Nemotron ran once, 4 workers at 12 requests a minute**, on the shared free-tier key; no 429.
8. **Stale rows.** The snapshot had 149 Lapua model rows of 2026-11-13; left in place they make
   every finding look opened or closed today. I deleted the three topics' `llm` and `both` rows
   before the load and kept all `lexicon` rows (the history).
9. **The findings load ran without the heavy lock**: it takes 6 s and little memory, and waiting
   for the lock once took over ten minutes.
10. **Tool URL of a finding** = the UI route with the pair of editions plus the finding id in the
    API answer; the API has no route for one finding.
11. **Cache key.** `differences.classify` keys a cached answer on the prompt version, endpoint,
    model, settings and the full prompt, which holds both passage texts. `index.jsonl` maps every
    pair id to its key with the revision ids and the SHA-1 of each passage text.
12. **Builder 1 changed a passage during the night.** At about 05:20 the cleaned text of the
    English Lapua introduction changed (same revision 1383067871; the language template now reads
    "Finnish: Lapuanliike or Lapuan liike, Swedish: Lapporörelsen"), so four pairs had no cached
    answer and one pair was no longer aligned. Both models classified the four again (4 requests
    each), and I deleted the model rows and loaded again. The first pairs file is kept as
    `$M/classify/agent4/pairs-run1.jsonl`. The opening finding survived: both models still call
    the first sentences framing.
13. **`evaluate` not rerun**: no file under `differences/` changed, so its scores are those of
    `main`. `python3 -m unittest differences.test_differences` passes (4 tests).
14. **Builder 1 changed three more passages.** At about 05:45 the cleaned text of the Swedish
    Finnish War introduction and of the English Diet of Porvoo introduction changed (same
    revisions 59682754 and 1384285215; the language templates now read "Finnish: Suomen sota;
    Russian: ..." and "Finnish: Porvoon maapäivät, or unhistorically ..."). Eleven pairs had no
    cached answer and one Diet of Porvoo pair was no longer aligned. Both models classified the
    eleven (11 requests each), and I deleted the model rows and loaded again at 05:55: 125 pairs,
    735 rows. All 18 findings of the shortlist are still open with the same ids and quotes, and 51
    of 51 quotes pass. The pairs file before this is kept as `$M/classify/agent4/pairs-run2.jsonl`.
    The false-positive counts above are of the first full run and were not judged again.
15. **Last check at 06:58.** The pairs were unchanged since 05:55 (regenerated every ten minutes
    until 06:57). I ran the replay block at the top of this file once more as written: 125 pairs,
    0 requests, 735 rows loaded, 51 of 51 quotes pass, all 18 shortlist findings open under the
    same ids. A change builder 1 makes after 06:58 needs steps 1 to 5 again, and the key run
    for any pair step 2 lists as uncached.
16. **Containers removed at the end** (`gapfinder-a4-api`, `gapfinder-a4-ui`), as BUILDERS.md
    asks. The shortlist's tool links name ports 8577 and 8578; the findings and their ids are in
    the scratch database, so any API and UI on scratch show them. After a snapshot restore the
    ids may differ: find a finding by its quote.
