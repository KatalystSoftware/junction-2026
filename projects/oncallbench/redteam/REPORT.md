# Red team: ways to score without doing the task

Scope: OnCallBench level 4 as shipped (`tasks/shift-1..3`, seeds 101-103), the way the judges run
it (Harbor, task network public). Searched with scripted policies in the simulator first, then
confirmed through Harbor with a scripted agent (Harbor's `oracle` agent running our own
`solve.sh`, no LLM). Run everything from `projects/oncallbench`.

The scoring core held: nothing played inside the simulator beat or matched the reference without
doing its work. Both real exploits are information leaks over the public network: the answer key
is published, and the agent's container can download it.

## 1. High, live now: the public replay viewer serves shift 1's answer key

`https://incident.katalyst.fyi/data/l4-s101.js` is level 4, seed 101: the same episode as
`tasks/shift-1`. It lists every fault (service and fix) and the reference's every call. The task's
network is public, and the main container has `python3` and `curl`.

- **Exploit**: [`leak_replay.py`](leak_replay.py) reads the free `get_topology`, downloads the
  site's bundles, picks the one whose services and revenues match, and replays the reference's 98
  calls through the MCP tools. It reads no alert, log or diff.
- **Score**: shift 1 **1.00**, the same as the reference (cost $85,246.31 in both, to the cent).
  Harbor end to end: 66 s wall time, [reward](evidence/leak-replay-shift-1-reward.json),
  [agent output](evidence/leak-replay-shift-1-agent.txt),
  [signed log](evidence/leak-replay-shift-1-receipt.json). Shifts 2 and 3: 0.00, since only seed
  101 is published.
- **How fast a judge finds it**: 5-10 minutes. The URL is in `replay/README.md` and in the demo, and
  the bundle is plain JSON: a judge does not even need the replay. The faults read off by eye
  (rollback `sms-svc`, scale `pricing-svc`, revert `address-svc` at minute 47, rollback
  `quotes-svc`), and those four moves at the right times are the oracle.
- **Fix on this branch**: the main container maps `incident.katalyst.fyi` to 127.0.0.1
  (`extra_hosts` in `task/` and `tasks/shift-*/environment/docker-compose.yaml`). Rerunning the same
  Harbor job against the fixed task scores 0.00: the download is refused, only `get_topology` is
  logged, and the cost is the do-nothing $232,523.28 ([reward](evidence/leak-replay-shift-1-fixed-reward.json),
  [agent output](evidence/leak-replay-shift-1-fixed-agent.txt)). Regression check: `python3 redteam/test_redteam.py`.
- **That fix is not enough on its own.** A judge who reads the compose file can bypass it with
  `curl --resolve incident.katalyst.fyi:443:<ip>`, after a DNS-over-HTTPS lookup. The real fix is
  on the server: take the shipped seeds (101-103) off the public site, or put the site behind a
  password, until judging ends. The viewer opens from disk (`replay/README.md`), so the demo does not
  need the public URL. That is a deploy to the shared Verda host, so it is the team's call.
- **Changes reported numbers**: no. Nothing scored changes, and OpenCode never contacts that host.

## 2. High once the repository is public: the reference script itself

The submission plans a public repository. Once it is public, a script inside
the container can download `projects/oncallbench/sim/policies.py` from GitHub and run
`python3 policies.py reference http://mcp-server:8000/mcp`. That is exactly what
`harbor run -a oracle` does, so it scores **1.00 on every seed**, and the judges will have the
repository link open in front of them. With `sim/incident.py` an agent can also find its seed by
matching the free topology against `Estate(seed, 4)` and plan the oracle offline. The oracle
avoids more than the reference does, so that also scores 1.00 after clipping. `replay/data/` puts
the same answer keys in the repository.

- **Not run end to end**: the repository is private today (the GitHub raw URL returns 404 from the
  container, see `audit/REPORT.md`). The step after the download is the shipped oracle run, which
  scores 1.00.
- **How fast a judge finds it**: 2-5 minutes for a judge who thinks to try it.
- **Fix options, none applied**:
  1. Egress allowlist for the main container: only the model API and the hosts OpenCode's install
     needs (a proxy sidecar on an internal network). This is the only complete fix. It needs one
     OpenCode run to confirm the install and the API call still work, and I did not spend on one.
  2. Add `raw.githubusercontent.com`, `codeload.github.com` and `api.github.com` to the same
     `extra_hosts` block. It is cheap but leaky: jsdelivr and other mirrors serve GitHub content. It
     may also break the OpenCode install, which downloads from GitHub. Untested.
  3. Disclose it in the submission: with a public network and a public scripted reference, any
     agent can download the reference and run it. A benchmark at scale would keep its reference
     private.
- **Changes reported numbers**: no for any of these, provided OpenCode still installs and runs.

## 3. Low, perception: `eval.py` printed `drain-only 1.00` and `consumer-fixer 1.00`

This was the lead. These two are level-5 policies: they mishandle a bad generated file. Level 4
loads no files, so their file branch never fires, and **their action logs are byte-identical to the
reference** on seeds 1-5 and 101-103. They score 1.00 because they are the reference. A judge running
the README's test command would see a policy called "drain-only" tie the reference.

- **Fix on this branch**: `eval.py` leaves them out on levels without files (`FILE_ONLY`). The
  level-5 gate that bounds them at 0.8 is unchanged. `redteam/test_redteam.py` checks that their logs
  match the reference's at level 4.
- **Changes reported numbers**: no. Their rows disappear from the level-4 printout; every other
  number is the same.

## What did not work (checked)

Scores on held-out seeds 101 / 102 / 103 (reference 1.00 on each):

| Policy | Scores | What it is |
| --- | --- | --- |
| surge-responder | 0.90 / 0.87 / 0.82 | The full reference, plus doubling every CPU-alert service and a 30% throttle on failing edges. Does all the diagnosis; the extra moves cost money. |
| no-late, alerts-only | 0.77-0.82, 0.75-0.76 | The reference minus the end-of-shift watch, or minus the descent from the edge (misses the quiet fault). |
| unprotected, thorough, trusting, forgetful | 0.42-0.71 | The reference minus one judgment each. |
| shotgun | 0.62 / 0.02 / 0.00 | The reference's localisation, then mitigations cycled blind. 101 is luck of its cycle order. |
| one-fix, loudest-first, exploiter, stop-early, nothing | 0.00-0.13 | The short policies that skip diagnosis. |
| [`blind.py`](blind.py): alert-undo, rich-guess, scale-all | 0.00 on all three; at most 0.36 on build seeds 1-3 | New: a protected rollback on every unexplained error alert; a guess at the quiet fault from the latest change under the richest edge; capacity on everything that retries. They pay the $10,000 fines and miss the overload. |
| Random calls (`eval.py --fuzz`) | best 0.00 | Legal and illegal calls at random. |

On the "meaningful difficulty" question: the policies near 1.0 are not short heuristics. Each is the
290-line reference with one judgment removed, so their scores price that judgment: protecting a
rollback is worth about 0.3, watching for the late fault about 0.2. Every policy that actually
skips diagnosis scores 0.13 or less on held-out seeds. Opus's 0.32 sits where its transcripts say:
it finds the causes, then makes one of those judgments wrong.

Simulator rules reviewed by hand and with probes:

- **Out-of-range or odd arguments.** Rejected before any side effect, and never logged or replayed.
- **Undo loops.** A second rollback reverts an older, innocent change and is fined $10,000.
- **Pre-empting the late fault.** It cannot be fixed before it starts: a fault ends only if it has
  started and the matching change is reverted.
- **Leaving early, timing out, or crashing the agent.** Replay charges the rest of the shift.
- **Settlement.** Scaling below normal earns nothing. A throttle at an edge costs the revenue it
  rejects.
- **Rejected calls.** They are free (no clock, no budget) but reveal nothing that `get_changes`
  does not.
- **Ledger and verifier.** Out of reach, as `audit/REPORT.md` found: read-only mount, HMAC, replay
  in a separate verifier; a spoofed reward file is ignored.

Residual: the HMAC key is a constant in `sim/incident.py`. Once the repository is public, anyone can
sign an action log, but the agent still cannot write the ledger or the verifier's copy of it.

## Reproduce

```
python3 redteam/leak_replay.py --sim 101     # simulator: reference 1.00, leak-replay 1.00
python3 redteam/blind.py --seeds 101,102,103 # the blind shortcuts
python3 redteam/test_redteam.py              # regression checks for both fixes
# end to end: copy tasks/shift-1, put leak_replay.py in solution/ with a solve.sh that runs it
#   python3 "$(dirname "$0")/leak_replay.py" http://mcp-server:8000/mcp
# then: harbor run -p <copy> -a oracle
```
