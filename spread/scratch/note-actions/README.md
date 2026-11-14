# The note fallback, offline

Scripts behind the offline numbers of `spreadlab/fallback.py` (see the main README, "The note fallback"). They score
the fallback's cited actions against the reveal of the archive's won notes, split by wording as
`spreadlab.notecheck.held_out` draws it, and run the self-healing loop. From `spread/`, after
`scratch/llm-notes/extract.py` has written `data/llm-notes/`:

| Script | What it does |
| --- | --- |
| `eval.py trigger <split>` | how often the trigger asks, and which of the rules' misses it covers |
| `eval.py run <split> [n]` | asks the model (`NOTE_ACTIONS_MODEL`) on the triggered notes: every miss and n others; answers cached in `data/note-actions/` |
| `eval.py score <split>` | per field: fixed, broken, wrong actions, € saved and lost a week, latency; `TRIGGERS="new wording"` scores version 4's trigger |
| `eval.py inject <split> --ask` | notes in wording the archive lacks, with known facts, on held-out requests |
| `misses.py <split>` | the notes whose posted reading the rules get wrong, by field |
| `heal.py cases/propose/check/rate [rules]` | self-healing: dev misses, Opus 5.5's candidate rules, the gates, the fallback's rate under each version of the rules |

`notes_before.py` is `notes.py` before the note-check fixes (`8ccb2b5^`): `heal.py ... notes_before` replays the loop on
the misses those fixes mended by hand. `candidates.jsonl` holds Opus 5.5's rules from that replay.
