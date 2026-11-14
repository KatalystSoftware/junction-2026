# Evidence behind LOOP.md

Small files copied out of the ignored `jobs/` folder so that the report can be checked without
rerunning anything. Trial names match `metrics.json` and the quotes in `LOOP.md`.

- `receipts/<job>__<trial>.json`: the signed action log of every recorded run, agents and scripted
  anchors. `incident.replay(seed, level, actions)` reproduces its cost; the regrade in round 11 was
  done from these.
- `final-messages/<job>__<trial>.md`: each agent's closing message, verbatim. The failure taxonomy
  quotes come from here. Full transcripts stayed in `jobs/` (83 MB); one is committed under `runs/`.
- `regrade-l4.json`: every stored level-4 agent run scored against the round-11 reference, with the
  score as run.
- `generality/gen-final-<first>.jsonl`: the final reference against the oracle, one row per seed,
  on the audit set (1000-1199) and the two reserved sets (2000-2199, 3000-3199).
  `gen-before-2000.jsonl` is the reference before round 11 on 2000-2199. Reproduce with
  `python3 generality.py --seeds 3000-3199`.
- `patches/`: the two levers that were built and reverted before any agent run, as diffs against the
  tree of their round: the traffic campaign (round 5) and the failover onto a small standby
  (round 8). They do not apply to the current tree without work.
- `patches/round12-level6.patch`: level 6 of round 12 (a shared resolver fault and a node pool
  where a scale stays pending), as a diff of `sim/` and `eval.py` against b3aa86c. It applies to
  the current tree (`git apply`, then `./sync.sh`). The `r12-l6-*` receipts and closing messages
  are nine Opus runs and three scripted anchors on that level; they replay only with the patch
  applied.
- `round12-review.md`: the GPT 6.1 Sol review of that level, verbatim. Its disposition is revert.

Not here on purpose: Harbor's job `config.json` files, which record the environment passed to the
agent, including API keys in plain text for the Gemini runs.
