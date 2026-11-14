# Gemini Decision as the judge of the claim check

14 November 2026. A time-boxed experiment beside [`hero-verify-notes.md`](hero-verify-notes.md):
the same claims, the same hand labels ([`hero-labels.json`](hero-labels.json)), the same scorer
([`hero_score.py`](hero_score.py)), with `gemini-decision-1` as the judge
([`differences/decide.py`](../differences/decide.py)). The chat judges' code, files and the
`checked_finding` table are untouched. `V=~/junction2026-data/mariadb/classify/verify`; everything
of this experiment is in `$V/gemini-decision/`.

## Verdict

**Use Gemini Decision alongside Nemotron, as the gate for missing facts. Do not use it as the only
judge.**

- On missing facts it is as good as Haiku 5.5 and Nemotron 3.5 Lightning on the labels: it keeps
  all 10 real rows at a threshold of 0.5, and of the 5 false ones it removes 3 and turns one into
  a numbers row (whole article), or removes 4 and turns one (retrieved passages). Missing facts are
  670 of the 721 rows of the first run.
- On numbers it is worse than Haiku: at 0.5 it loses 2 of 9 real rows and keeps 2 of 11 false ones
  (Haiku: 0 and 1). It is about level with Lightning. No threshold fixes this.
- It writes no text. The quote can be asked for (a choice among sentences), but the note, what each
  side is about, and the two figures as written cannot, so a numbers finding judged by it has a
  templated note and no computed figure check ([`figures.py`](../differences/figures.py)).
- It judged the 730 classifier claims of the three topics, each against the whole other article, in
  36 seconds and 35 requests. Nemotron 3.5 Super VL on the Verda container takes about 5.5 minutes
  a call, six claims a call.

## The numbers, on the 75 labelled rows

Each cell is the count of labelled rows, then what became of them. For false rows: gone / moved /
kept. For real and unclear rows: kept / moved / gone. The Haiku and Lightning lines are copied from
`hero-verify-notes.md`; Nemotron 3.5 Super VL is still pending there. Every Gemini line is
`gemini-decision-1`, with the reverse check against the whole article in both variants. Framing is
not checked by any judge.

| Type | Judge | False: gone / moved / kept | Real: kept / moved / gone | Unclear: kept / moved / gone |
| --- | --- | --- | --- | --- |
| missing fact | Haiku 5.5 | 5: 3 / 1 / 1 | 10: 9 / 1 / 0 | 9: 4 / 2 / 3 |
| | Nemotron 3.5 Lightning | 5: 4 / 0 / 1 | 10: 9 / 1 / 0 | 9: 5 / 0 / 4 |
| | Gemini Decision, whole article, 0.5 | 5: 3 / 1 / 1 | 10: 10 / 0 / 0 | 9: 3 / 0 / 6 |
| | Gemini Decision, whole article, 0.7 | 5: 1 / 0 / 4 | 10: 10 / 0 / 0 | 9: 4 / 0 / 5 |
| | Gemini Decision, whole article, 0.9 | 5: 0 / 0 / 5 | 10: 10 / 0 / 0 | 9: 7 / 0 / 2 |
| | Gemini Decision, retrieved passages, 0.5 | 5: 4 / 1 / 0 | 10: 10 / 0 / 0 | 9: 3 / 0 / 6 |
| | Gemini Decision, retrieved passages, 0.7 | 5: 3 / 0 / 2 | 10: 10 / 0 / 0 | 9: 5 / 0 / 4 |
| | Gemini Decision, retrieved passages, 0.9 | 5: 0 / 0 / 5 | 10: 10 / 0 / 0 | 9: 6 / 0 / 3 |
| numbers | Haiku 5.5 | 11: 9 / 1 / 1 | 9: 8 / 1 / 0 | 3: 1 / 0 / 2 |
| | Nemotron 3.5 Lightning | 11: 9 / 1 / 1 | 9: 5 / 1 / 3 | 3: 2 / 0 / 1 |
| | Gemini Decision, whole article, 0.5 | 11: 8 / 1 / 2 | 9: 6 / 1 / 2 | 3: 0 / 0 / 3 |
| | Gemini Decision, whole article, 0.7 | 11: 10 / 1 / 0 | 9: 3 / 0 / 6 | 3: 0 / 0 / 3 |
| | Gemini Decision, whole article, 0.9 | 11: 11 / 0 / 0 | 9: 0 / 0 / 9 | 3: 0 / 0 / 3 |
| | Gemini Decision, retrieved passages, 0.5 | 11: 7 / 1 / 3 | 9: 5 / 1 / 3 | 3: 0 / 0 / 3 |
| | Gemini Decision, retrieved passages, 0.7 | 11: 10 / 1 / 0 | 9: 2 / 0 / 7 | 3: 0 / 0 / 3 |
| | Gemini Decision, retrieved passages, 0.9 | 11: 11 / 0 / 0 | 9: 0 / 0 / 9 | 3: 0 / 0 / 3 |
| contradiction | Haiku 5.5 | 2: 1 / 1 / 0 | none labelled real | 5: 2 / 0 / 3 |
| | Nemotron 3.5 Lightning | 2: 2 / 0 / 0 | | 5: 2 / 0 / 3 |
| | Gemini Decision, both variants, 0.5 to 0.9 | 2: 2 / 0 / 0 | | 5: 0 / 0 / 5 |

With the three rechecked labels applied (two "unclear" missing facts that the other edition does
state), Gemini Decision on the whole article at 0.5 removes 5 of 7 false missing facts and moves
one; Haiku removes 4 and moves two.

### The threshold

A claim is supported, or contradicted, when that answer's probability is at least the threshold,
and not mentioned otherwise. **Use 0.5.** The model's probabilities here are soft: of the 117
labelled and reverse claims, 84 have a supported or contradicted answer of 0.5 or more, 44 of 0.7
or more and 11 of 0.9 or more, none of those a contradiction. So 0.7 already keeps 4 of the 5 false
missing facts (whole article) and loses 6 of the 9 real numbers rows, and at 0.9 the check does
nothing: every missing fact is kept and every numbers row is gone. A higher threshold only keeps
more missing facts, so the real ones are safe at any of the three; the false ones are what a
higher threshold lets back in.

### Whole article or retrieved passages

No difference that 75 labels can show. With the whole article the judge keeps one false missing
fact that it removes with retrieved passages ("a general strike in November": supported 0.39
against not mentioned 0.49 in a 9-passage article), and on numbers it is one row better on each
side. The whole article needs no embedding of the claims and no search, and it was the cheaper of
the two here (558,479 input tokens against 819,541), because the article is sent once per request
and the retrieved passages once per claim. The search is still what gives the page its SQL
statement and the passage's rank, so it stays in the flow for what is shown.

### Where it is wrong

- **Figures that differ a little are called supported.** "1 000 men" against "1,100 Swedes" at
  Vaasa: supported 0.52 and 0.50. "About 12,000" against "12,600" marchers: supported 0.74 from the
  Swedish side, so the contradiction is not confirmed. The chat judges copy both figures and
  `figures.py` decides; this model cannot copy a figure.
- **Two different quantities are called another figure**: a law limited to five years against a
  party willing to accept three (0.74), 17 000 in the field army against 21,000 in fortresses
  (0.63). Haiku keeps the first of these too.
- **Unclear rows go**: 6 of the 9 unclear missing facts and all 8 unclear numbers and contradiction
  rows are removed. For the five contradictions "for a human" this is the same loss the notes
  describe for Haiku, and complete.

## The full run: every classifier claim of the three topics

`$V/gemini-decision/run1-article/t50/` (and `t70/`): the 730 claims behind the 721 rows of the
first run, each against the whole other article, without the figures the check lists itself.
`gemini-decision-1`, 0.5, over the 730 claims and the 53 reverse claims they led to: 428 not
mentioned, 265 supported, 90 contradicted.

| | Before | Haiku 5.5 (with listed figures) | Gemini Decision, 0.5 | Gemini Decision, 0.7 |
| --- | --- | --- | --- | --- |
| missing fact | 670 | 414 | 418 | 482 |
| numbers | 23 | 31 | 12 | 7 |
| contradiction | 7 | 5 | 3 | 1 |
| framing | 21 | 21 | 21 | 21 |
| set aside | | 228 stated elsewhere | 267 | 210 |

On the 670 missing-fact claims, Gemini Decision at 0.5 and Haiku give the same answer to "stated
elsewhere or not" for 577 (86%): both stated 184, both not 393, Haiku only 40, Gemini only 53. The
93 they disagree on have not been read by hand.

**Not loaded into `checked_finding`.** `python -m gapfinder.checked load
$V/gemini-decision/run1-article/t50` would run as it is: the folder has `differences.jsonl`,
`set-aside.jsonl` and `run.json` in the shape `claims.py` writes. It should not be run yet: a load
replaces the three topics' rows, which are the Haiku-judged run with its 9 extra numbers findings;
the notes of numbers rows here are two quotes side by side; and rows have no figures, no "about"
and no reverse evidence. What loading should take is the split below: load the chat judge's run,
with Gemini Decision's verdict on its missing facts.

## How Gemini Decision and Nemotron share the work

1. The classifier (Nemotron) proposes rows from pairs of passages, as now.
2. **Gemini Decision** takes every missing-fact claim, a whole article per request, and answers
   "stated elsewhere?" with a probability and the sentence that states it. At 0.5, 418 of the 670
   stay missing facts, in under a minute for three topics.
3. **Nemotron 3.5 Super VL** judges what needs reading and writing: the numbers and contradiction
   claims, the figures it lists itself, and the reverse checks, with the note and the two figures.
   That is 60 claims of the 730 plus the extracted figures, instead of all of them, which is the
   difference between a pass that finishes during the hackathon and one that does not.
4. The probability is kept with each row (`probabilities` in `verdicts.jsonl`), so the page can
   order missing facts by how sure the check is, and a missing fact near 0.5 can be sent to
   Nemotron as well.

This split is measured only in its parts. Step 2 is the table above; steps 3 and 4 are not built.

## The request

One small request first (`$V/gemini-decision/probe/`), then the schema below held for all others.
Google's reference is <https://aistudio.google.com/docs/decisions-api>; the yes/no type literal is
`noul`, as the launch post writes it, and the endpoint accepts it.

```sh
curl -X POST https://generativelanguage.googleapis.com/v1beta/decisions \
  -H "x-goog-api-key: $GEMINI_API_KEY" -H "Content-Type: application/json" -d @request.json
```

```json
{"model": "gemini-decision-1",
 "input": "<the brief, then the whole article as numbered passages>",
 "questions": {
   "c0": {"type": "choice",
          "instructions": "What does the article say about this claim's point?\n\nClaim, from …: \"…\"\n…",
          "criteria": {"supported": "…", "other_figure": "…", "other_fact": "…", "not_mentioned": "…"}},
   "c1": {"type": "noul", "instructions": "…",
          "criteria": {"true_description": "…", "false_description": "…"}}}}
```

```json
{"answers": {
   "c0": {"type": "choice", "choice": "other_figure", "confidence": 0.94,
          "probabilities": {"supported": 0.004, "other_figure": 0.94, "other_fact": 0.04, "not_mentioned": 0.008}},
   "c1": {"type": "noul", "noul": 0.98, "confidence": 0.98}},
 "usage": {"total_input_tokens": 327, "total_output_tokens": 0, "total_tokens": 327,
           "input_tokens_by_modality": [{"modality": "text", "tokens": 327}]}}
```

Question keys match `[A-Za-z0-9_-]+`, at most 64 characters; a choice has 2 to 255 options, which
is why the quote is found in two steps (a passage of at most 59, then a sentence of that passage).
`decide.py` asks three questions per claim, in three requests per article: the verdict as a
`choice` of four (`other_figure` and `other_fact` together are "contradicted"), the passage, the
sentence. `noul` was used only in the first request.

## Cost

| Run | Requests | Input tokens |
| --- | --- | --- |
| first request | 1 | 327 |
| labelled rows, whole article (86 claims and 31 reverse) | 35 | 558,479 |
| labelled rows, retrieved passages (86 and 27) | 34 | 819,541 |
| all classifier claims, whole article (730 and 53) | 35 | 1,988,954 |
| **total** | **105** | **3,367,301** |

No request failed or was retried. The largest request held 141 questions and 148,890 tokens. At the
$0.10 per million input tokens of the launch coverage (not checked against Google's price page)
that is about $0.34. Every answer is cached in `$V/gemini-decision/cache/` (104 files; the first
request's answer is in `probe/`), so the commands below send nothing now.

```sh
# from projects/since-when/; O=$V/gemini-decision, P=~/junction2026-data/mariadb/classify/agent4/pairs-run1.jsonl
export DIFFERENCES_DECIDE_CACHE=$O/cache
python3 -m differences.decide $V/labelled-haiku/evidence.jsonl $P $V/labelled-rows.jsonl \
    --articles $O/articles.jsonl --read article --threshold 0.5 0.7 0.9 --out $O/labelled-article --offline
python3 -m differences.decide $V/labelled-haiku/evidence.jsonl $P $V/labelled-rows.jsonl \
    --articles $O/articles.jsonl --read passages --threshold 0.5 0.7 0.9 --out $O/labelled-passages --offline
python3 -m differences.decide $O/run1-classifier-evidence.jsonl $P $V/run1-rows.jsonl \
    --articles $O/articles.jsonl --read article --threshold 0.5 0.7 --out $O/run1-article --offline
python3 demo/hero_score.py $O/labelled-article/t50/differences.jsonl -v
```

`articles.jsonl` is the 174 current passages of the nine articles, read from `chunk` and `passage`
in the scratch database with one SELECT; their text equals the evidence passages' text in all 448
cases. `labelled-haiku/evidence.jsonl` is used only for its claims and search results, which do
not depend on the judge.

## Not verified

- The moved rows of the Gemini runs and the unclear rows it removed were not read by hand; the
  counts are the scorer's.
- One run per setting. Whether the model gives the same probabilities twice was not tested, since
  every answer is cached.
- The full run was not hand-checked the way the Haiku run was (no sample of kept and set-aside rows
  read against the articles).
- Nemotron 3.5 Super VL has no line in the table: its pass was still running.
- All claims are dated 14 November 2026, so "the article as it stood at the claim's date" was the
  current article in every case. For an earlier date `articles.jsonl` needs
  `FOR SYSTEM_TIME AS OF`, as the search has.

## Why Gemini matters to Since When

Since When's findings are claims about whole articles, and a hand check found the classifier wrong
whenever it had seen only two passages; Gemini Decision reads the whole other article with every
claim about it in one request, and on the hand labels it kept all 10 real missing facts and let 1
of the 5 false ones through. It did this for the 730 claims of three topics in 36 seconds and 35
requests, about 2 million input tokens, where one call to our Nemotron judge takes 5.5 minutes for
six claims, so the check is cheap enough to run on more than three hand-picked topics. And it
answers with a probability, not prose, so each "missing in this edition" on the page carries how
sure the check is, while Nemotron writes the notes and judges the figures, where a calibrated
yes or no was measurably not enough.
