# Would an LLM read the dealer notes better?

Offline scripts behind the estimate that an LLM reader is not worth adding to `steep-notes-offers-8`.
None plays a week or needs the team key. They score the rule reader (`spreadlab/notes.py`) and three
Nemotron models against the reveal of the saved weeks, and count what note facts cost in the account.
The findings are in the document
[LLM note reader estimate]((a team document)).

What they found, on the archive as of `133de93`:

- The rules misread 14 of 24,655 won notes (ready time, plates, manual). In the reference's 104 saved
  weeks that cost €2.53 a week.
- As the only reader, Nemotron 3.5 Bolt misreads 10 and Lightning 3 of 330 notes that the rules read
  right, and each mends 10 or 11 of the rules' 14 misses.
- Closing times and the note's own deadline, which `notes.py` does not read, cost about €126 a week.

They are scratch: dense, and written to print tables.

## Run

From `spread/`. The extracts read the archive bundles directly, so the data folder need not be unpacked,
but the bundles must be real files (`git lfs pull`; see the main README). They write about 160 MB of
JSON lines to `data/llm-notes/`, which is not committed.

```bash
PYTHONPATH=. uv run python scratch/llm-notes/extract.py [bundles folder]    # rows, notes, runs: every won order and every note
PYTHONPATH=. uv run python scratch/llm-notes/extract2.py [bundles folder]   # ref_orders: the reference's orders with their account lines
PYTHONPATH=. uv run python scratch/llm-notes/<script>.py
```

| Script | What it prints |
| --- | --- |
| `analyse.py` | notes a week, languages, lengths, and how many won cars carry each note fact |
| `reader.py` | `notes.py` against the reveal on every won note, by seed list, with each misread note |
| `rule_cost.py` | the account lines of the reference's orders whose note the rules misread |
| `upside.py` | the reference's failed visits, waits and late orders by note fact and cause, a week |
| `starter_read.py` | what the kit's keyword match reads of closing times and note deadlines, and whether it had read the fact when a visit failed |
| `novelty.py` | how much of a new week's wording 25 to 400 known weeks have not shown |
| `rate.py` | notes a real minute on the final's clock, for all requests and for won orders |
| `llm_test.py` | `sample`, `run` and `score`: the model test (see its docstring) |
| `combine.py` | the rules with a model as second reader; `--show` lists each model's errors |
| `verify.py` | the live desk's note check (`spreadlab/watch.py`): the model's yes or no on the rules' reading against the reveal, and the facts the rules leave out of every won note |

## The model test

`sample.jsonl` holds 344 won orders with a note and what the reveal says was true: the 14 that the rules
misread, and 330 drawn by fact from the seeds played last. `answers.jsonl` holds every answer of the three
models, with its seconds and token counts. `llm_test.py score` and `combine.py` need only these two
files; `score` also writes each reader's wrong answers to `score.json`, which is not committed.

`llm_test.py run` calls NVIDIA's API with `NVIDIA_API_KEY` from the environment. The free endpoint
allows about 40 requests a minute, and Nemotron 3.5 Super VL returned 429 on most calls, so it has 64
answers where the other two have 344.
