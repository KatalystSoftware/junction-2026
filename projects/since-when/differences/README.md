# differences

Marks the differences between two aligned passages from different language editions of Wikipedia
(fi, sv, en), with the exact quotes behind each one. It returns categories and quotes. It never
says which edition is right and never scores an edition's politics.

Python 3.11+, standard library only.

```bash
python -m differences classify pairs.jsonl > differences.jsonl   # one difference per line
python -m differences evaluate -v                                 # against the hand labels in eval/
python -m unittest differences.test_differences
```

```python
from differences import classify_pair, classify_pairs, TYPE_WEIGHT
rows = classify_pair(pair)                     # list of dicts, possibly empty
for rows in classify_pairs(pairs, workers=8):  # same order as the input
    ...
```

## Input: one aligned pair

Only matched pairs that are still far apart come here. Passages with no match at all are
coverage gaps, found on the alignment side.

```json
{"pair_id": "Q1412941:2026-01-01:fi:812:en:97", "wikidata_id": "Q1412941", "as_of": "2026-01-01",
 "a": {"lang": "fi", "title": "Lapuanliike", "section": "", "chunk_no": 0, "rev_id": 24266018, "text": "plain text"},
 "b": {"lang": "en", "title": "Lapua Movement", "section": "", "chunk_no": 0, "rev_id": 1383067871, "text": "plain text"}}
```

`text` is plain text with the wikitext already stripped. `section` is `""` for the lead. Other
keys, such as `distance` or `chunk_id`, are ignored.

## Output: one row per difference

```json
{"pair_id": "...", "wikidata_id": "Q1412941", "as_of": "2026-01-01",
 "type": "framing", "missing_in": null,
 "quote_a": "exact substring of a.text, or empty", "quote_b": "exact substring of b.text, or empty",
 "summary": "One neutral English sentence.", "terms": ["fascist", "pro-Nazi"],
 "source": "both", "model": "claude-haiku-5-5"}
```

| Field | Values |
| --- | --- |
| `type` | `missing_fact`: one passage states a fact the other leaves out although it covers the same ground. `contradiction`: both cannot be true. `framing`: the same thing under different labels, names or judgements. `numbers`: different figures for the same quantity. |
| `missing_in` | The language of the passage that lacks the fact, for `missing_fact` only; otherwise `null`. |
| `quote_a`, `quote_b` | Always exact substrings of the passages, so the UI can highlight them. A model quote that is not in the passage drops the whole row. At least one quote is set. |
| `terms` | Loaded words from the word list behind a framing row, such as `fascist`, `terror` or `War of Liberation`. Often empty. |
| `source` | `llm`, or `both` when a word-list hint backs a framing row. Rows from before 14 November may say `lexicon`: drop those. |

`TYPE_WEIGHT` suggests weights for the impact score: contradiction and framing 1.0, numbers 0.8,
missing fact 0.5.

## How it works

1. **Word list** ([lexicon.py](lexicon.py)): families of competing words for the same thing in
   fi, sv and en, such as *fascist / far right / nationalist* for a movement, *War of Liberation /
   civil war* for 1918, *concentration camp / prison camp*, *terror / political violence*,
   *coup / rebellion*. A loaded word counts only when the other passage names the same thing with
   another word of its family. When both passages open their article's lead, the first
   sentences are compared on their own first, because that sentence defines the subject.
   Capitalised Finnish and Swedish matches mid-sentence are names ("Vapaussodan Rintamamiesten
   Liitto") and are skipped. The hits are hints for the model only: on its own the word list
   paired sentences about different events (a fascist label against the Great Purge) and said
   an edition avoids a word it uses one sentence later, so it writes no rows.
2. **Model** ([llm.py](llm.py)): gets the pair and the word-list hints and returns up to eight
   differences as JSON. Any OpenAI-compatible chat completions endpoint works. The first
   provider in this table whose key is set is used, or the one named by `DIFFERENCES_PROVIDER`:

   | Provider | Key variable | Endpoint | Default model |
   | --- | --- | --- | --- |
   | `custom` | `DIFFERENCES_API_KEY` | `DIFFERENCES_BASE_URL`, else Anthropic | `claude-haiku-5-5` |
   | `nvidia` | `NVIDIA_API_KEY` | `https://integrate.api.nvidia.com/v1` (free tier, ~40 requests a minute) | `nvidia/nemotron-3.5-super-vl-120b-a12b` |
   | `anthropic` | `ANTHROPIC_API_KEY` | `https://api.anthropic.com/v1` | `claude-haiku-5-5` |
   | `verda` | `VERDA_INFERENCE_API_KEY` | `https://inference.verda.com/v1` | `deepseek-4-1-flash-1017` (also `kimi-k3-1-pro`) |
   | `vultr` | `VULTR_INFERENCE_API_KEY` | `https://api.vultrinference.com/v1` | `deepseek-v4.1-flash-1017` |

   `DIFFERENCES_BASE_URL` and `DIFFERENCES_MODEL` override either, for example
   `DIFFERENCES_MODEL=claude-sonnet-5-5`. With no key, no differences are written. To compare
   models: `DIFFERENCES_PROVIDER=nvidia python -m differences evaluate --workers 2`.
   The team's `NVIDIA_API_KEY` is in [`../secrets/secrets.yaml`](../secrets/README.md):
   `sops exec-env secrets/secrets.yaml 'python -m differences evaluate'`.

   It asks for strict JSON schema output and falls back to plain JSON mode, then to no format,
   when an endpoint refuses one. Answers are cached under `data/differences/cache/` (gitignored),
   keyed by prompt, model and passages, so re-runs over unchanged passages cost nothing.
   `evaluate` prints the tokens the run was billed for.
3. **Quote check**: each quote is matched against its passage, forgiving only changed white
   space, quote marks, dashes and a trailing "...". Rows whose quotes are not found are dropped.

A pair whose model call fails gets no rows and a warning on stderr; a re-run retries only those pairs.

## Cost

One call sends the instructions and two passages and gets up to five differences back. On the
evaluation pairs the prompt averages 4,900 characters, about 2,200 tokens (Finnish takes more
tokens per character than English); the answer is about 500 tokens. Estimated, not yet measured:

| Model (Anthropic list prices, Nov 2026) | Per call | 46 eval pairs | 10,000 pairs | 140,000 pairs |
| --- | --- | --- | --- | --- |
| Haiku 5.5 ($0.10 / $0.50 per M tokens) | $0.0005 | $0.02 | $5 | $66 |
| Sonnet 5.5 ($2 / $10) | $0.0094 | $0.43 | $94 | $1,320 |
| Opus 5.5 ($4 / $20) | $0.019 | $0.87 | $188 | $2,630 |
| Nemotron 3.5 Super VL on NVIDIA Build (free tier) | $0 | $0 | $0, ~4 h at 40/min | $0, ~2.5 days |
| DeepSeek V4.1 Flash on Verda ($0.15 / $0.60) | $0.0006 | $0.03 | $6 | $88 |
| Kimi K3.1 Pro on Verda ($2 / $10) | $0.0094 | $0.43 | $94 | $1,320 |

140,000 is a guess at a full run: the current text of all 2,919 shared topics at about 10 far
pairs per language pair (~88,000), plus yearly history for ~300 topics, where the cache skips
passages that did not change (~50,000). The Batch API halves every price but returns answers
within 24 hours. The real pair count comes from `python -m gapfinder pairs`. Kimi reasons at
maximum effort by default, and reasoning bills as output, so its real cost is likely higher.

## Evaluation

[eval/pairs.jsonl](eval/pairs.jsonl) holds 46 pairs: the leads of 16 Finnish history topics
(1914–1944) in fi, sv and en, compared fi–en, fi–sv and sv–en, current revisions of 13 November
2026. [eval/labels.json](eval/labels.json) holds the types each pair should get, labelled by hand
from the three texts, with a note on each. A type counts as found when the classifier returns at
least one row of it for the pair. `python differences/eval/fetch.py` rebuilds the pairs, but the
labels only fit the committed revisions.

Word list alone, no model (13 November 2026, before it became hints only; on these whole-lead pairs it looked precise, on the live chunk pairs it was not):

| Type | Labelled | Found | Right | Precision | Recall |
| --- | --- | --- | --- | --- | --- |
| framing | 22 | 13 | 13 | 1.00 | 0.59 |
| numbers | 11 | 0 | 0 | – | 0.00 |
| contradiction | 1 | 0 | 0 | – | 0.00 |
| missing_fact | 44 | 0 | 0 | – | 0.00 |

The word list finds no false framing, but only labelled words: the framing it misses is in whole
sentences, such as "Finland was not Germany's ally by law" against "fought by Finland and Nazi
Germany". Numbers, contradictions and missing facts need the model.

## Nemotron settings to compare

The NVIDIA model card recommends "temperature 1.0, top_p 0.95" for text, with reasoning mode
switched by `enable_thinking`. Each setting has its own cache entries, so the four runs below
do not overwrite each other (46 calls each):

```bash
for t in off on; do
  DIFFERENCES_THINKING=$t python -m differences evaluate --workers 8
  DIFFERENCES_THINKING=$t DIFFERENCES_TEMPERATURE=1.0 DIFFERENCES_TOP_P=0.95 python -m differences evaluate --workers 8
done
```

Keep the setting with the best precision on `numbers`, `contradiction` and `framing`, then
recall; reasoning bills more output tokens and takes longer per pair.

Results on 13 November 2026 with `PROMPT_VERSION = 1`, one run per setting, the four runs in
parallel at 8 workers each (precision / recall). Prompt v4 changed the instructions after these
runs, so rerun them before quoting the numbers for v4:

| Reasoning | Sampling | missing_fact | framing | numbers | contradiction (1 labelled) | Quotes kept | Time | Output tokens per call |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| off | temperature 0 | 1.00 / 0.71 | 0.86 / 0.27 | 1.00 / 0.45 | none found | 149 of 223 | 29 s | 526 |
| off | temperature 1.0, top_p 0.95 | 1.00 / 0.82 | 0.85 / 0.50 | 0.38 / 0.27 | none found | 157 of 216 | 27 s | 476 |
| **on** | **temperature 0** | **0.98 / 0.98** | 0.84 / **0.73** | 1.00 / 0.82 | 0.25 / 1.00 | **195 of 221** | 7.6 min | 9,112 |
| on | temperature 1.0, top_p 0.95 | 0.97 / 0.71 | 0.88 / 0.64 | 1.00 / 1.00 | 0.50 / 1.00 | 140 of 187 | 7.8 min | 9,389 |

Reasoning on at temperature 0 is the setting to keep, and it is what runs with no settings
given: with `DIFFERENCES_THINKING` unset, Nemotron reasons anyway (about 10,000 output tokens per
call). The precision rule above alone would pick reasoning at temperature 1.0, but its edge rests
on small counts (framing 14 of 16 right against 16 of 19; contradiction 1 of 2 against 1 of 4),
while it misses far more facts, keeps fewer quotes, and one of its answers ended mid-JSON, so that
pair got the word list only. Reasoning costs about 17 times the output tokens and 16 times the
time; on the NVIDIA Build free tier the tokens cost nothing. Each reasoning call takes 60 to 100
seconds, so reaching the free tier's 40 requests a minute takes about 50 workers.

The errors in these runs changed the prompt (versions 2 to 5), each version measured with
reasoning on at temperature 0:

- Long leads filled every slot with missing facts and crowded out the Lapua framing, so the
  model now lists contradictions, numbers and framing first, in up to 8 slots.
- The model called a figure only one edition gives a "contradiction" or "numbers"; such a row
  with one empty quote now becomes a `missing_fact`, in the prompt and in code.
- Framing caught neutral synonyms ("movement" against "organisation"), so only judgemental or
  politically charged words count now: framing precision went from 0.67 to 0.83.
- From clean-room testing: summaries keep hedges such as "has been claimed", framing reads as a
  difference in labels rather than an error, and both quotes must be about the same subject.
- Version 6, after the first 648 live pairs: 35% of missing-fact summaries said an edition or
  article "does not" mention something, although the model sees one passage of each. Summaries
  now describe the passages, and each passage is labelled with its part of the lead or section.
  Not re-measured on the 46 pairs: the change is to wording, not to which differences are found.
- Reasoning can use 15,000 tokens on a long pair, so `max_tokens` is 32,768, and a broken
  answer is asked again instead of cached.

`PROMPT_VERSION = 5`, reasoning on, temperature 0, one run: missing_fact 0.98 / 0.91,
contradiction 0.33 / 1.00, framing 0.83 / 0.86, numbers 0.75 / 0.82; 288 of 310 quotes kept;
about 13,300 output tokens per call.

Nemotron 3.5 Lightning 30B A3B (`DIFFERENCES_MODEL=nvidia/nemotron-3.5-lightning-30b-a3b`),
`PROMPT_VERSION = 6`, reasoning on, temperature 0, one run: missing_fact 0.97 / 0.71,
contradiction 0.33 / 1.00, framing 1.00 / 0.68, numbers 0.75 / 0.82; 128 of 224 quotes kept;
about 18,600 output tokens per call. It finds fewer differences than Super and misquotes more
often, but what it keeps is as precise. NVIDIA Build rate-limits each model separately, so a
large run can split its pairs between Super and Lightning to use both limits; each row's
`model` says which one wrote it.

## Submission text for the NVIDIA tech challenge (draft)

The challenge asks for "a short explanation identifying the model used, what it does, why it
matters, and how you improved its outputs". The numbers come from the prompt v5 run above.

> **Model:** NVIDIA Nemotron 3.5 Super VL (`nvidia/nemotron-3.5-super-vl-120b-a12b`) on NVIDIA
> Build, with reasoning on.
>
> **What it does:** the gap finder aligns passages about the same topic across the Finnish,
> Swedish and English Wikipedias. Nemotron reads each matched pair that still differs and labels
> what differs: a missing fact, a contradiction, different framing (such as "fascist" against
> "radical right-wing"), or different numbers, with the exact sentences from both editions.
> Those labels fill the editors' queue and the side-by-side view.
>
> **Why it matters:** an editor who reads two languages can see in seconds what one edition says
> that the other does not, with the quotes to check, instead of reading both articles in full.
> Nemotron gives categories and quotes, never a verdict on which edition is right.
>
> **How we improved its outputs:**
> - Every quote is checked against the article text; a label whose quote the model invented is
>   dropped, so nothing reaches an editor without evidence. On the evaluation pairs, 288 of the
>   model's 310 differences kept their quotes.
> - A word list of loaded terms in all three languages (fascist, terror, War of Liberation,
>   concentration camp, coup) gives the model hints. On its own it matched unrelated sentences, so
>   it no longer writes findings itself.
> - JSON schema output; an answer that does not parse is asked again rather than stored.
> - 46 pairs labelled by hand from 16 Finnish history topics measure precision and recall per
>   label. We compared reasoning on and off and NVIDIA's recommended sampling on them, then
>   revised the prompt four times from the errors: listing contradictions and numbers before
>   missing facts, and counting only charged words as framing, raised framing precision from
>   0.67 to 0.83. With reasoning on, precision / recall is 0.98 / 0.91 for missing facts,
>   0.83 / 0.86 for framing and 0.75 / 0.82 for numbers; with reasoning off (prompt v4), framing
>   recall is 0.59, numbers recall 0.64, and the one contradiction is missed.

## Findings for the demo

- **Lapua Movement, first sentence.** English: "a radical Finnish nationalist, fascist, pro-Nazi
  and anti-communist political movement". Swedish: "nationalistisk, fascistisk och
  antikommunistisk". Finnish: "antikommunistinen ja oikeistoradikaali kansanliike" (anti-communist
  and radical right-wing). The current Finnish lead does discuss fascism, but only in its last
  paragraph: the leaders denied being fascists, yet the movement meets nearly all common
  definitions of fascism. So the difference is where the label sits, not whether it appears.
- **Mäntsälä rebellion.** English calls it "a failed coup attempt by the Lapua Movement"; Finnish
  calls it a rebellion by the movement's supporters that began on local initiative; Swedish
  Svinhufvud calls it "det fascistinspirerade Mäntsäläupproret".
- **Finnish Civil War.** Finnish: "laajamittaista terroria" (large-scale terror); English:
  "Political violence". Swedish lists "frihetskrig" (War of Liberation) among its names. Deaths in
  total: Finnish and English about 38,000, Swedish about 36,000.
- **Kyösti Kallio's death.** Swedish: a stroke at the farewell ceremony; English: a heart attack.
- **1918 prison camps.** Finnish notes some camps have been called concentration camps; English
  calls them prison camps.

Wikipedia text in `eval/pairs.jsonl` is CC BY-SA 4.0; each passage carries its title and `rev_id`.
