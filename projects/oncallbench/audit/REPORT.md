# AfterQuery incident environment: independent audit

Audit date: 14 November 2026. Submitted level: **4**. This is a review of fairness,
generality, deterministic replay and the Harbor boundary, not an attempt to improve the score.
No model inference was used. Production source and task files were not edited.

The audited checkout was `aec3d09`. [provenance.json](provenance.json) records the exact hashes;
[source.tar.gz](source.tar.gz) preserves the files used by every test. The source, server and
verifier simulator copies were byte-identical, as were both policy copies. Tests ran from an
unchanged copy under ignored `audit/runtime/`: this both isolates the improvement loop and keeps
`run.sh`'s generated variants and jobs under the required audit directory. The report's source
line numbers refer to that snapshot. The original `run.sh` was executed, including its normal
sync, variant generation and calibration steps, inside that copy.

The final rebase incorporated the owner's concurrent `0ae514f` update: extra parity notes in
`LOOP.md` and a **level-5-only** briefing clarification that file generations land on minutes
divisible by five. [validation.json](validation.json) records the resulting source-hash
differences and verifies that every simulator AST node outside `briefing()` is unchanged and
the level-4 briefing is identical. The policies, scoring and level-4 test results remain
applicable. The source archive deliberately preserves the earlier snapshot rather than silently
substituting the newer files into the evidence.

## Verdict against the six requested checks

| Check | Result |
| --- | --- |
| Same information and tools | Same API and no private simulator input. One important generator-backed inference remains: selecting an unread twin change by elimination. Other thresholds are mostly ordinary heuristics over visible measurements; the inventory below distinguishes them. |
| No privileged policy paths or reverse engineering from failures | No policy-keyed simulator/server/verifier path found. Available history supports mechanism-driven reference development, but cannot establish the provenance of every heuristic. The task itself was explicitly tuned against observed model behavior. |
| Generalises to fresh level-4 seeds | See the completed 200-seed results below; the existing build/held-out claims must not stand in for this test. |
| Determinism and Harbor reliability | Random-call replay, three repetitions per requested seed and baseline, and direct-container probes are reported below. |
| Shell cannot bypass the task | Direct HTTP is reachable, but uses the same clock, accepted-call budget and signed ledger. The local source/seed/verifier boundary held in the probe. |
| Human runbook | Included below, with evidence read at every step and explicit qualifications for hindsight. |

## Findings, highest severity first

### High: the reference's generality claim fails on unseen seeds

<!-- GENERALITY_FINDING -->
**39/200 seeds (19.5%) fall below 0.75 of the shipped oracle's avoided cost.** The mean is 0.7798, median 0.7856, and range 0.3737–0.8562. The reference costs more than doing nothing on **0/200** seeds. Thus the sampled build/held-out range is not a valid lower bound on new estates.
<!-- END_GENERALITY_FINDING -->

The test calls the shipped `eval.evaluate()` and `eval.oracle()` unchanged, for all seeds
1000–1199 at level 4. This range overlaps neither build seeds 1–12 nor held-out seeds 101–106.
The ratio is **avoided cost**, `(null - reference) / (null - oracle)`, not raw reference cost
divided by oracle cost. Complete costs and all 17 policy scores are in
[generality.jsonl](generality.jsonl), with the distribution in
[generality-summary.json](generality-summary.json). Each `eval.run()` also asserts replay equality.

For a concrete search failure, seed **1016** starts a bad config on `profile-svc` at minute 47.
The reference never mitigates it. It finishes with `web-storefront` at 98.61% errors and
`admin-portal` at 95.90%. `get_logs(profile-svc)` visibly reports
`KeyError: 'currency' in price formatter`; the cause's alert is crowded out, including within
the app tier. `trace()` follows only the highest-count upstream line and aborts when that
service is already in the alert/error set (`policies.py:115–125`). The suspect calculation also
treats absent dependency alerts as zero (`:323–345`). Repeating queries to high-volume victims
never finds the root. This is a deterministic reference failure, not insufficient evidence in
the environment. [counterexamples.json](counterexamples.json) preserves the diagnosis queries,
fix times, remaining faults, final customer errors and cost components for every counterexample.

Seed **1077** illustrates delay rather than a permanently missed cause: `notifications-svc`
is overloaded before the page, but its scale does not land until minute **90**. The reference
first requests that service's metrics at minute 55 with the default window, long after the
pre-overload baseline has disappeared. Only at minute 84 does it request the historical window
ending at -7; it then scales at 86. Its reference/oracle ratio is 0.5971. `trace()` calls
`diagnose()` without the alert onset, so traced overloads can lose the useful baseline even
though the historical metrics tool can supply it.

On seed 1016, `no-late` finishes at minute **38**, before the fault starts at **47**, yet
receives **1.0** because its cost exactly matches the reference that never fixes the later fault.
`surge-responder` costs $178,765.79 versus the reference's $225,344.63 and also receives a clipped
1.0. This is a weak calibration anchor, not a shell or verifier exploit.
[no-late-full-score.json](no-late-full-score.json) distinguishes early exits from runs that
finish only after the late fault has already been handled.

**Suggested fix:** repair search and verification of unresolved customer errors using only
observed tool outputs, then validate on a new, reserved seed set. Do not filter the generator or
drop failing audit seeds to make the bar pass. Publish the lower tail, not only six selected
seeds. A reference can be an imperfect scoring anchor, but the claimed ≥0.75 generality gate
must be reported as failed wherever it fails.

### Medium: an unread twin change is selected using an undisclosed construction guarantee

`change_fix()` (`policies.py:50–60`) reads the latest live change of each type. If its first diff
does not share a symptom word, and the other change is within five minutes, Python's `or`
short-circuits: the policy selects the **other change without requesting its diff**. The
generator (`incident.py:343–374`) constructs exactly this situation for change-caused faults:
one harmful change, one ordinary change of the other type, at the same minute.

The timestamps and first diff are visible; the guarantee that the other change must be the
cause is not in the instruction or briefing. A human could reasonably *suspect* the other
change, but could not know it is harmful, or that no independent explanation exists, from this
screen. The reference benefits from a two-minute diagnosis saving each time this shortcut fires.
This is an inference shortcut, not a secret tool or a reward gate.

Across build seeds 1–12 and held-out 101–106, the unchanged reference selected **21 unread twin
changes on 14 of 18 seeds**. [unread-twins.json](unread-twins.json) records the visible change
lists, diff IDs actually read and selected revert; [inventory.py](inventory.py) reproduces it.
The policy does **not** contain the simulator's table of harmful or ordinary hunks.

**Suggested fix:** read and assess the other diff before claiming it is the cause. The alternative
is to state the release-train guarantee in the briefing, but that would make the task easier
and should be a deliberate benchmark design decision. An allowed hindsight-tuned threshold is
different from treating an undisclosed generator invariant as established evidence.

### Medium, conditional on submission packaging: the tracked task is not a runnable level-4 submission

The repository's `task/environment/mcp-server/server.py:15–16` still has `SEED = 1`, `LEVEL = 0`.
`task/instruction.md:23` still contains `<!-- BRIEFING -->`, and `task/tests/calibration.json` is
absent. `grade.py:13` loads calibration unconditionally. `run.sh:31–43` supplies all three things
only in `jobs/variants/aq-incident-<hash>/`. That generated variant is runnable; the raw tracked
`task/` is a template.

<!-- BARE_TASK_RESULT -->
A model-free Harbor `nop` run against the unmodified captured `task/` reproduced `FileNotFoundError: /tests/calibration.json`, followed by **RewardFileEmptyError**. [evidence/bare-verifier.txt](evidence/bare-verifier.txt) contains the full verifier errors; [evidence/bare-result.json](evidence/bare-result.json) records Harbor's exception. The 27 generated-variant runs did not have this failure.
<!-- END_BARE_TASK_RESULT -->

**Suggested fix:** explicitly package and validate the generated **level-4 variant** as the
submission artifact. If the judges receive the tracked `task/` instead, they get level 0 without
its rules and a verifier failure. The README does describe variants, so this is a packaging
hazard, not a claim that runs through `run.sh` use the wrong level.

### Low: the runner can conceal subprocess failures

`run.sh:57–61` backgrounds every Harbor run and finishes with argumentless `wait`. In Bash,
`wait` with no PID waits for all jobs and returns zero; it does not propagate each job's failure
(`bash -c 'false & true & wait'` exits zero). A successful outer command therefore does not
establish that the MCP server, agent or verifier succeeded. Harbor trial result files must also
be checked, since a finished job can contain trial errors.

**Suggested fix:** collect each PID's status and check every trial's completion, exception and
reward fields. This audit compares actual trial ledgers and signed receipts, rather than relying
on the shell exit status. No failure of the requested variant repetitions is inferred from this
runner weakness alone.

### Low: finite templates and tuned scenario structure limit what seed generality establishes

The eight `FLAVOURS` and fifteen `ORDINARY_DIFFS` are fixed (`incident.py:107–144`). Harmful
symptoms and diff hunks intentionally share words. The reference uses generic token intersection,
not this table, so a human can make the same semantic match. Nevertheless, new random seeds
reuse the same eight diagnoses; success on 200 new seeds is not evidence of generalisation to
unseen fault vocabulary or mechanisms. Level 4's quiet fault is always a bad deploy
(`:299–305`), while its local metrics/logs hide the fault. The reference still reads changes and
at least one diff; it does not explicitly bypass them using this invariant.

`LOOP.md:370–387` records rewording a symptom because a shared ordinary word made the reference
choose wrongly. `:440–447` records selecting hot-service capacity and increasing rich-edge
revenue so the intended quiet-fault decision remains difficult and valuable. These are visible
benchmark construction choices, not special treatment at runtime; they do constrain the claim.

**Suggested fix:** reserve held-out symptom/diff families and vary quiet-fault cause independently
of observability and revenue. Keep the existing frozen task for comparison and clearly label
its finite-template scope. Do not claim production incident-response generality from seed
variation alone.

## Every reference input: observations, constants and assumptions

`reference()` takes only `call(tool, **args)` and its documented local policy options. With the
default options, it calls `graph`, `trace`, `diagnose`, `change_fix`, `leak_fix`, `scale_fix`,
`guard_fix`, `drain_fix`, `words`, and its local scheduling/graph helpers. It imports no
`incident`, seed, level, faults, calibration or oracle. The default is `max_fixes=None`,
`leave_when_clear=False`, `thorough=False`, `descend=True`, `trusting=False`, `guess=False`,
`drain=True`, `protect=True`, `lift=True`, `files="fix"`. These select behavior, not hidden inputs.

Here **documented** means instruction + appended level-4 briefing or MCP tool description;
**observed** means a tool result; **heuristic** means a choice an engineer can make from those
facts without knowing the generator; **construction assumption** means an additional guarantee
the screen does not establish. Heuristics are allowed by the mentor's stated rule.

| Input or constant | Used for | Availability and assessment |
| --- | --- | --- |
| `get_topology.services`: `name`, `tier`, `normal_replicas`, `revenue_per_min`, `depends_on.service/kind`, `callers_retry` | Build dependencies and potential downstream revenue impact; choose capacity and retry protection | Observed. No fixed service-name vocabulary is used. Tier strings `edge/app/data`, hard/soft kinds and replica limit are documented. |
| Hard weight `1`, soft weight `0.3`; multiplication of successful shares | Explain inherited errors and compute the revenue a service can affect (`graph`, `own`, edge gap) | Documented failure propagation, with “about 30%” rounded to the model's exact 0.3. No hidden topology or revenue. |
| `get_status.minute`, `minutes_left`, `shift_over`, `edge.service/error_rate/revenue_per_min`, `operations_in_progress.service/completes_at_minute` | Clock, stopping, customer impact, outstanding mitigation timing | Observed; status is explicitly free. Default reference never ends merely because it has fixed a known number of faults. |
| `list_alerts.ok/minute/alerts/total`; each alert's `service`, `signal`, `value`, `firing_since_minute` | Infer paid-query behavior, truncation, signals and onset; re-query app/data tiers | Observed. Ten loudest, filters and signal thresholds are documented. No privileged full alert list. |
| Alert cutoffs `error_rate >= .05`, `cpu/mem >= .9`; top list length `10` | Interpret alerting, CPU headroom and tier truncation | MCP descriptions / briefing disclose them. The reference's literal .9 and 10 are not secret thresholds. |
| Healthy edge `<= .005`; unexplained edge gap `>= .01`; individual cause `>= .06`; own-failure floor `.05`; denominator safety `up > .02` | Decide whether to investigate; prevent unstable error subtraction | Heuristics. The instruction states healthy is well under 1%; .005 is a stricter working threshold, .06 adds a margin above alerting. `.02` is numerical protection, not a retrieved generator fact. |
| Suspect recheck `5` min, hidden-edge recheck `10` min; priority query-effort divisors `1/3/8/13` | Avoid repeat work and rank likely dollars saved per investigation time | Heuristics over visible impact and documented query duration. They encode tuning/experience, not access to faults. |
| `get_logs.lines[].message/level/count`; `ERROR/FATAL`, `upstream call to (\S+) failed ((...))`, highest count, trace depth `<10` | Follow failing calls, distinguish own failure, pick a suspect | Observed log format and severity. Parsing is legitimate; highest-count-only tracing is a lossy heuristic and explains failures on unseen graphs. Depth 10 is a search limit, not a promised graph depth. |
| Literal phrases `request queue full`, `heap above`, `out of memory`, `primary node unreachable`, `retry storm` | Identify overload, memory pressure, primary failure and retries | All are observable tool text with ordinary operational meaning. They are a finite parser vocabulary, not invisible facts. CPU alone is discounted when retries plus own error can explain it. |
| `first seen in build`, `setting loaded from` | Direct rollback/config identification on earlier levels | Observable where emitted. Level-4 change-caused faults have generic `FLAVOURS` symptoms instead, so these shortcuts do not identify their change. |
| `get_changes.changes`: `type/status/minute/id`, filtered live and latest of each type | Choose a revert target; leak treatment | Observed. Chronological lists and “latest live” mitigation semantics are documented. Summary text is not used to identify the harmful change. |
| Leak rule: any `mem` alert, or leak-like logs, implies a leaking build; latest live deploy `minute >= -240` means rollback, otherwise restart | `diagnose` → `leak_fix` | The deploy age is observable; “recent deploy first” is an allowed but weak operational heuristic. **The guarantee** that high memory only occurs on a leaking build, and that the latest such deploy is its cause, is generator-specific (`incident.py:213–215,575–595`). The reference does not verify a memory slope, onset correlation or a harmful leak diff. A human could suspect a leak; could not know these categorical guarantees from one alert. `-240` is not an exposed or required history limit: available telemetry is only 180 minutes, change history 24 hours. |
| `get_diff.diff` for a visible `change_id`; split text on non-alphanumeric, lowercase, retain words of length `>=3` | Match symptoms to source/config changes | Observed and human-readable. No lookup of `FLAVOURS`, `ORDINARY_DIFFS`, deployment notes, service-name lists or fault kinds. Generic lexical matching is brittle, but not privileged information. |
| Other change within `5` min after one unrelated diff | Select the unread other type | **Construction assumption**, finding above. The actual pair is observable; exactly one harmful member is not guaranteed to the agent. |
| `get_metrics.series[]`: `rps`, `retry_share`, `cpu`, `replicas`, `error_rate`; sampling step `5`, onset window `since+5` | Find a calm baseline and distinguish new traffic from retries | Observed. Thirty-minute window and historical lookup are documented; 5-minute sampling is apparent in the returned series. `p99_ms`, `mem`, `restarts_30m` are not read by the default reference's metric formulas; memory is consumed through alert/log evidence. |
| New demand = `rps * (1-retry_share)`; rise `>=1.3`; size at `.95` CPU, ceil replicas, at least current `+1` | `scale_fix` | Retry decomposition is documented. Thirty-percent demand rise and 95% target are allowed tuned heuristics over visible data. The generator's overload range 2–3× and exact normal RPS/sine phase are not read. |
| `DISRUPTS={rollback:(6,.3), restart:(3,.5)}` | Protect quiet services and schedule a drain | Exact level-4 timing and transient failure shares are in the briefing. No use of hidden `MITIGATIONS`. Data restart has a different documented 5-minute/100% effect; the helper's generic restart approximation is a limitation, not a privilege (default leaking builds roll back). |
| Backlog = `retry_share/(1-retry_share)`; inferred capacity = maximum `(1+backlog)/cpu`; current own failure ≈ backlog / `callers_retry` | Estimate whether a rollback/restart will trigger a storm | Derived from observable metrics and documented one-minute retry feedback. Background retry noise, inherited errors and capped CPU make this approximate; the policy does not read hidden `cap`, `HOT`, `HEADROOM` or `_state`. |
| Protection costs: `$3` per extra replica-minute; `5` minutes of scale wait; `minutes+8` replica duration; throttle safety `+1` percentage point, cap `90`; refuse a fix if projected cost exceeds the remaining loss | Choose scale vs throttle vs leaving a fault late in the shift | Price, 4-minute scale landing + 1-minute initiation, action duration and throttle cap are documented. The `+8` includes initiation/scheduled scale-down accounting; selecting this approximate model and the extra percentage point is heuristic, not undisclosed cost data. |
| Drain requires retry share `>.2`, CPU `>=.9`, inferred capacity `<=1.45`; throttle formula safety `+3` percentage points, cap `90` | Drain a residual storm for one minute after fixing its cause | Visible inputs and documented retry behavior. `.2`, `1.45`, `+3` are empirical heuristics. In particular **1.45 is not a disclosed physical boundary**: it happens to separate this generator's 1.32 and 1.6 capacity classes. A human could use it as a safety rule, but cannot infer that there are exactly two capacity classes from the instruction. No private capacity is fetched. |
| After a successful fix, own failure `>=.1` (including disruption) triggers timed drain; percent `ceil(100*(1-1/(1+retry*failing)))`, cap `90` | Clear retries as the fix lands, lift immediately afterward | The retry formula and next-minute throttle effect are documented; `.1` is a chosen significance threshold. Starts at `completes_at-1`, lift at completion; these timestamps are tool results, not known fault endpoints. |
| Timers: query reach `1`, wait reach `minutes-1`, action reach `0`; wait until scale landing, normal replicas restored at mitigation completion | Fit protection/drain/lift calls around paid calls | Deterministic scheduling derived from documented 2-minute queries and 1-minute actions. No alternate clock. Timers use only previously returned completion times and current status. |
| File-only inputs: topology `file_from`, file-size/limit regex; historical alert onset clamped to `-150`; generation tick `5`; early preparation with `minutes_left >=60`, replica safety factor `1.15`, maximum `4×`; hot-consumer onset difference `2`; publication/return offsets `3/4`, one-minute throttle/lift staggering | Level-5 generated-file handling | **Unreachable on level 4**: `file_from` is absent and the file symptom is not generated. On level 5, relation, generation period, history, replica cap and symptoms are disclosed/observed; 60, 1.15 and scheduling margins are heuristics. `-150 = -180+30` is the supported historical window endpoint, also reported by invalid-argument errors. No level-4 input is hidden in these branches. |
| `-99/-999/999`, empty sets/maps, `0`, `None`, `max/min`, retry defaults, booleans/options | Bookkeeping, “not seen yet”, defaults, conditionals | Internal sentinels, not environmental knowledge. |

Unused-by-default branches are not evidence of a privilege: `trusting` uses a `-90` recent-change
cutoff, `guess` cycles generic actions (double normal replicas), and `thorough` reads neighbours.
`files="surge"` doubles replicas and throttles 30%; consumer/drain variants intentionally ignore
publishers. None runs in the default level-4 reference. The exact number of faults, their future
start times, severity ranges, fault/edge selection pools, shuffled names, fixed vocabulary tables,
seed and submitted level are **not inputs to the reference**.

The distinction for a human expert is between “this measurement suggests a leak” (fair prior),
and “this alert can only be a leaking latest build” (not established by the screen). The clearest
unfair-information concern is the unread-twin inference; -240, 1.3, 1.45 and .9 are not themselves
secret reads. Of these, .9 is explicitly documented, while the others deserve heuristic labels.

## Policy isolation and development history

The case-insensitive search used was:

```sh
rg -n -i 'reference|policy|oracle|claude|opus|anthropic|solution|exploiter|stop.early' \
  sim/incident.py task/environment task/tests task/task.toml
```

No simulator or MCP server hit selects behavior by agent identity, policy name, environment
variable, special argument or log line. The matches are a comment about agent timeout in
`task.toml` and the verifier's reporting field `beats_reference`; the latter compares cost only.
`POLICY` is consumed by `solution/solve.sh` to choose a client, not by the server or verifier.
The sidecar's `run()` always calls the same `estate.call()` behind one lock. No method can import
or invoke `reference()` remotely. HTTP reference calls and OpenCode MCP calls use the same
public tool handlers. Both pay for `get_changes`, `get_diff`, headroom measurement and diagnosis;
neither can bypass protected-mitigation timing or wasted-mitigation charges by identity.

The reference does **not** embed a transcript, Claude response, seed test, list of expected
service names, known fault schedule or known diff hunks. The level-4 retry reference was authored
with the mechanic in `a6a90a9` (author timestamp 13:02:50 EET); the first recorded level-4 Opus
trial began at 13:02:56 in `metrics.json`. That commit landed later, at 13:23:59, so commit order
alone does not prove which edits predated which observations. Level-5 extensions subsequently
changed the same reference file (`241005c`), principally gated by visible file relations. The
pre-existing twin shortcut and -240 rule are present in the earlier level-3 implementation
(`0b06def`). The 1.3 sizing threshold is older still.

This supports a mechanism-driven policy, rather than a script of Claude's exact mistakes.
It does **not** establish an independent, pre-registered reference: `LOOP.md` explicitly says
the reference is strengthened when mechanics need it, and documents reviewing model transcripts
and tuning the environment around observed mistakes. The leak heuristic, paired-change shortcut
and finite vocabulary should be disclosed on that basis. No runtime “secret gate” was found;
the strong historical claim “no rule was ever influenced by a model failure” cannot be certified
from these files or Git history.

## Generality results and every counterexample

<!-- GENERALITY_TABLES -->
| Statistic | Reference / oracle avoided cost |
| --- | --- |
| min | 0.3737 |
| p05 | 0.7153 |
| p25 | 0.7585 |
| median | 0.7856 |
| mean | 0.7798 |
| p75 | 0.8085 |
| p95 | 0.8415 |
| max | 0.8562 |

**Worse than do-nothing seeds:** none.

All-policy score distribution across all 200 seeds (the benchmark score clipped to 0–1):

| Policy | Min | Median | Mean | Max |
| --- | --- | --- | --- | --- |
| nothing | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| stop-early | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| one-fix | 0.0000 | 0.1176 | 0.1437 | 0.5502 |
| reference | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| exploiter | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| shotgun | 0.0000 | 0.5418 | 0.4786 | 0.8116 |
| no-late | 0.4526 | 0.7589 | 0.7463 | 1.0000 |
| loudest-first | 0.0000 | 0.0000 | 0.0717 | 0.4592 |
| thorough | 0.1071 | 0.4379 | 0.4547 | 0.8163 |
| trusting | 0.0000 | 0.6462 | 0.5886 | 0.8159 |
| alerts-only | 0.4637 | 0.7423 | 0.7421 | 0.8242 |
| no-drain | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| unprotected | 0.2003 | 0.6248 | 0.6233 | 0.7540 |
| forgetful | 0.2187 | 0.3568 | 0.3798 | 0.6546 |
| consumer-fixer | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| surge-responder | 0.0466 | 0.8375 | 0.8179 | 1.0000 |
| drain-only | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

Every seed below 0.75, or worse than doing nothing, with its specific mitigation timing:

| Seed | Ratio | Initial loud causes: fix/scale minute | Quiet fix minute | Late start → fix | Why below bar |
| --- | --- | --- | --- | --- | --- |
| 1004 | 0.7396 | bundles-svc 14; disputes-svc 19 | sessions-svc 39 | 65 → 79 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1007 | 0.6924 | vouchers-svc 14; ledger-svc 27 | ranking-svc 43 | 50 → 60 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1010 | 0.7054 | payments-db 10; returns-svc 23 | search-index 43 | 56 → 66 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1013 | 0.7342 | fraud-svc 14; orders-db 33 | sms-svc 34 | 58 → 72 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1016 | 0.3737 | media-svc 14; images-svc 21 | audit-svc 37 | 47 → MISSED | Never finds profile-svc; truncated alerts / single-path tracing |
| 1023 | 0.6924 | pricing-cache 14; seo-svc 23 | sessions-cache 41 | 54 → 68 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1029 | 0.7485 | suggest-svc 18; search-index 23 | inventory-db 43 | 69 → 79 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1034 | 0.7170 | experiments-svc 18; consent-svc 27 | recommendations-svc 43 | 61 → 71 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1040 | 0.7220 | auth-svc 23; labels-svc 14 | events-queue 43 | 65 → 75 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1045 | 0.7207 | catalog-svc 10; pricing-svc 23 | flags-svc 39 | 75 → 85 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1048 | 0.7361 | auth-svc 14; sitemap-svc 37 | inventory-db 32 | 64 → 78 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1062 | 0.7279 | import-svc 25; pricing-svc 14 | bundles-svc 41 | 46 → 56 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1064 | 0.7172 | fraud-svc 14; sms-svc 19 | auth-svc 41 | 74 → 88 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1065 | 0.6831 | cart-svc 14; returns-svc 23 | risk-db 41 | 73 → 91 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1077 | 0.5971 | ledger-db 14; notifications-svc 90 | reviews-svc 34 | 53 → 77 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1078 | 0.7385 | pricing-cache 10; import-svc 23 | wishlist-svc 39 | 59 → 69 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1085 | 0.7315 | suggest-svc 14; couriers-svc 27 | inventory-db 43 | 70 → 80 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1086 | 0.7042 | address-svc 22; profile-svc 25 | recommendations-svc 46 | 56 → 66 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1087 | 0.7407 | experiments-svc 14; emails-svc 19 | sessions-svc 39 | 69 → 79 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1094 | 0.7451 | ledger-db 14; subscriptions-svc 21 | shipping-db 37 | 59 → 73 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1099 | 0.7413 | cart-svc 14; vouchers-svc 25 | payouts-svc 41 | 55 → 65 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1106 | 0.7273 | users-db 14; wishlist-svc 21 | events-queue 43 | 60 → 74 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1107 | 0.7156 | flags-svc 21; stock-svc 14 | sessions-cache 37 | 68 → 82 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1109 | 0.7455 | ledger-svc 10; search-svc 19 | events-queue 37 | 52 → 66 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1121 | 0.7437 | limits-svc 14; subscriptions-svc 19 | pricing-svc 41 | 63 → 73 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1130 | 0.7352 | profile-db 14; disputes-svc 43 | sessions-svc 34 | 70 → 80 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1131 | 0.7230 | emails-svc 14; checkout-svc 19 | thumbnails-svc 41 | 53 → 67 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1139 | 0.6911 | images-svc 18; experiments-svc 39 | sms-svc 34 | 74 → 88 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1140 | 0.7390 | suggest-svc 10; pricing-svc 19 | stock-svc 37 | 60 → 74 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1142 | 0.7098 | quotes-svc 16; geo-svc 25 | payouts-svc 45 | 60 → 70 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1156 | 0.7401 | geo-svc 23; ledger-svc 18 | promo-cache 43 | 47 → 57 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1165 | 0.7296 | loyalty-svc 14; bundles-svc 27 | seo-svc 43 | 47 → 61 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1172 | 0.7486 | inventory-db 10; ranking-svc 39 | feeds-svc 30 | 67 → 77 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1180 | 0.7344 | audit-log 14; payouts-svc 25 | sessions-cache 39 | 49 → 59 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1188 | 0.7363 | catalog-db 10; pricing-svc 23 | pricing-cache 43 | 70 → 80 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1191 | 0.7409 | refunds-svc 23; catalog-db 14 | auth-svc 41 | 52 → 66 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1193 | 0.7413 | import-svc 10; quotes-svc 23 | media-svc 39 | 69 → 79 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1197 | 0.7362 | tax-svc 14; stock-svc 19 | sessions-cache 37 | 49 → 63 | All causes treated; time lost in diagnosis/protection (fix times shown) |
| 1198 | 0.7014 | inventory-db 14; audit-svc 21 | pricing-cache 41 | 68 → 86 | All causes treated; time lost in diagnosis/protection (fix times shown) |

Cheap-policy scores on **each** of those seeds:

| Seed | stop-early | exploiter | shotgun | no-drain | unprotected | forgetful | alerts-only | no-late | surge-responder |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1004 | 0.0000 | 0.0000 | 0.5677 | 0.0000 | 0.5689 | 0.4634 | 0.7131 | 0.6316 | 0.7874 |
| 1007 | 0.0000 | 0.0000 | 0.7396 | 0.0000 | 0.5208 | 0.3027 | 0.7301 | 0.6696 | 0.8361 |
| 1010 | 0.0000 | 0.0000 | 0.5997 | 0.0000 | 0.5383 | 0.2918 | 0.7458 | 0.6392 | 0.8030 |
| 1013 | 0.0000 | 0.0000 | 0.6217 | 0.0000 | 0.5843 | 0.4359 | 0.6976 | 0.5409 | 0.2715 |
| 1016 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.2003 | 0.6016 | 0.4637 | 1.0000 | 1.0000 |
| 1023 | 0.0000 | 0.0000 | 0.5615 | 0.0000 | 0.4984 | 0.3136 | 0.7127 | 0.5954 | 0.8025 |
| 1029 | 0.0000 | 0.0000 | 0.5760 | 0.0000 | 0.6713 | 0.3036 | 0.7809 | 0.8397 | 0.7337 |
| 1034 | 0.0000 | 0.0000 | 0.4587 | 0.0000 | 0.5701 | 0.3961 | 0.7556 | 0.6673 | 0.6701 |
| 1040 | 0.0000 | 0.0000 | 0.5089 | 0.0000 | 0.5731 | 0.2802 | 0.7305 | 0.7448 | 0.7617 |
| 1045 | 0.0000 | 0.0000 | 0.7312 | 0.0000 | 0.5439 | 0.3322 | 0.7267 | 0.6089 | 0.8357 |
| 1048 | 0.0000 | 0.0000 | 0.3907 | 0.0000 | 0.5918 | 0.3485 | 0.7615 | 0.7503 | 0.8469 |
| 1062 | 0.0000 | 0.0000 | 0.5347 | 0.0000 | 0.5565 | 0.2872 | 0.7437 | 0.7828 | 0.7235 |
| 1064 | 0.0000 | 0.0000 | 0.4658 | 0.0000 | 0.5160 | 0.3243 | 0.7247 | 0.7499 | 0.8184 |
| 1065 | 0.0000 | 0.0000 | 0.2828 | 0.0000 | 0.5105 | 0.3250 | 0.7099 | 0.7835 | 0.7410 |
| 1077 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.4168 | 0.5119 | 0.7856 | 1.0000 | 0.8806 |
| 1078 | 0.0000 | 0.0000 | 0.6749 | 0.0000 | 0.5570 | 0.3230 | 0.7292 | 0.7974 | 0.8563 |
| 1085 | 0.0000 | 0.0000 | 0.7566 | 0.0000 | 0.6021 | 0.2851 | 0.7863 | 0.8419 | 0.7321 |
| 1086 | 0.0000 | 0.0000 | 0.6856 | 0.0000 | 0.6062 | 0.3387 | 0.7573 | 0.7763 | 0.8311 |
| 1087 | 0.0000 | 0.0000 | 0.6981 | 0.0000 | 0.5617 | 0.2989 | 0.7205 | 0.7156 | 0.8424 |
| 1094 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.5798 | 0.3347 | 0.6923 | 0.6941 | 0.8567 |
| 1099 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.6242 | 0.2717 | 0.7820 | 0.7072 | 0.7684 |
| 1106 | 0.0000 | 0.0000 | 0.0145 | 0.0000 | 0.6026 | 0.2407 | 0.7792 | 0.6810 | 0.7827 |
| 1107 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.5452 | 0.3241 | 0.6991 | 0.7264 | 0.8104 |
| 1109 | 0.0000 | 0.0000 | 0.5088 | 0.0000 | 0.5437 | 0.3643 | 0.7031 | 0.5792 | 0.7258 |
| 1121 | 0.0000 | 0.0000 | 0.4412 | 0.0000 | 0.6393 | 0.3225 | 0.6983 | 0.6268 | 0.7929 |
| 1130 | 0.0000 | 0.0000 | 0.4852 | 0.0000 | 0.5778 | 0.3759 | 0.7358 | 0.7743 | 0.8185 |
| 1131 | 0.0000 | 0.0000 | 0.5476 | 0.0000 | 0.5901 | 0.3469 | 0.7023 | 0.7308 | 0.8125 |
| 1139 | 0.0000 | 0.0000 | 0.3330 | 0.0000 | 0.5364 | 0.4097 | 0.7253 | 0.6831 | 0.7968 |
| 1140 | 0.0000 | 0.0000 | 0.4502 | 0.0000 | 0.5180 | 0.3410 | 0.6779 | 0.6576 | 0.9056 |
| 1142 | 0.0000 | 0.0000 | 0.0421 | 0.0000 | 0.5636 | 0.2578 | 0.7520 | 0.7462 | 0.7550 |
| 1156 | 0.0000 | 0.0000 | 0.7605 | 0.0000 | 0.6019 | 0.3412 | 0.7722 | 0.7415 | 0.7840 |
| 1165 | 0.0000 | 0.0000 | 0.6449 | 0.0000 | 0.5966 | 0.4791 | 0.7717 | 0.6628 | 0.7327 |
| 1172 | 0.0000 | 0.0000 | 0.6916 | 0.0000 | 0.5885 | 0.3896 | 0.7385 | 0.7316 | 0.8438 |
| 1180 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.5348 | 0.3139 | 0.7301 | 0.6511 | 0.8026 |
| 1188 | 0.0000 | 0.0000 | 0.5809 | 0.0000 | 0.5890 | 0.2730 | 0.7667 | 0.7847 | 0.8204 |
| 1191 | 0.0000 | 0.0000 | 0.1777 | 0.0000 | 0.6100 | 0.2652 | 0.7660 | 0.7244 | 0.8184 |
| 1193 | 0.0000 | 0.0000 | 0.7301 | 0.0000 | 0.5812 | 0.2783 | 0.7471 | 0.7813 | 0.8223 |
| 1197 | 0.0000 | 0.0000 | 0.3680 | 0.0000 | 0.6082 | 0.3290 | 0.6904 | 0.6068 | 0.8262 |
| 1198 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.5610 | 0.2993 | 0.7395 | 0.6624 | 0.6608 |

[counterexample-scores.csv](counterexample-scores.csv) contains all 17 policies on every counterexample, including one-fix, thorough, trusting, loudest-first and the file-policy aliases. Fix/scale times are completion times, not the minute diagnosis begins; an overload's first successful scale is shown even if a later correction was needed. Cost components, including wasted fines, and raw tool-query evidence are retained in counterexamples.json.
<!-- END_GENERALITY_TABLES -->

An overload fault's hidden `end` remains null after successful scaling by design; the diagnosis
does not count that as an unfixed overload. The replay's final customer errors and capacity
matter. The `oracle()` is the shipped hidden-state scheduler: it tries all fault orders with a
fixed mitigation strategy. It is a useful stronger baseline, **not a proved global optimum**
over every possible action log. No new “better oracle” or policy was substituted in this audit.

The `consumer-fixer` and `drain-only` policies reduce to the reference at level 4, since there are
no file faults to mishandle. Their score of 1 would not demonstrate a shortcut. `surge-responder`
still applies blanket capacity/throttles and is a different policy at this level. All 17 policy
scores, including these qualifications, are retained for every seed.

## Replay and Harbor reliability

[check.py](check.py) generated 200 independent level-4 random call streams on seeds 2000–2199,
including legal and illegal tools/arguments, nonexistent services, booleans/strings where
integers are expected, historical/future windows, extra arguments, mitigations and finish calls.
It compared every response against an independent estate, serialized accepted actions through
JSON, replayed them and checked receipt/signature, total cost, cost components and final status.
[replay.json](replay.json) records **13,346 response comparisons**, **1,651 accepted logged
actions**, **797 unlogged successful calls** (`get_status`) and **10,898 rejected calls**.
There were no mismatches or simulator exceptions. The fresh-seed evaluation separately replayed
each policy's accepted log with the shipped assertions. These tests establish repeatability for
the exercised streams, not a proof for all possible inputs.

The exact requested command ran **three times per seed**, for seeds 101, 104 and 105:

```sh
LEVEL=4 SEED=<n> ./run.sh reference nop stop-early
```

That is nine reference runs and 18 baseline runs, all with Harbor **0.25.0**, Docker and no model.
The only runner addition was a job prefix and quiet console output. At most four audit trials
were live together, including extra probes. Source files were identical across repetitions.

<!-- HARBOR_RESULTS -->
**27/27 trials matched in-process cost, score and signed receipt byte content; zero mismatches, timeouts, MCP startup failures or verifier errors.** The JSON receipt comparison ignores serialization whitespace while preserving every action, argument and signature.

| Seed | Policy | In-process cost | Harbor cost (all 3) | Score (all 3) |
| --- | --- | --- | --- | --- |
| 101 | nop | $232,523.28 | $232,523.28 | 0.00 |
| 101 | reference | $85,246.31 | $85,246.31 | 1.00 |
| 101 | stop-early | $232,523.28 | $232,523.28 | 0.00 |
| 104 | nop | $363,550.75 | $363,550.75 | 0.00 |
| 104 | reference | $150,590.38 | $150,590.38 | 1.00 |
| 104 | stop-early | $363,550.75 | $363,550.75 | 0.00 |
| 105 | nop | $248,253.37 | $248,253.37 | 0.00 |
| 105 | reference | $84,079.79 | $84,079.79 | 1.00 |
| 105 | stop-early | $248,253.37 | $248,253.37 | 0.00 |

[harbor-results.json](harbor-results.json) records every repetition; [evidence/](evidence/) holds an individual comparison per trial. Host evaluation used Python 3.14.10; the sidecar/verifier used the declared Python 3.12 images. Docker server was 29.9.2. This is a small reliability sample and does not exercise OpenCode installation or model latency.
<!-- END_HARBOR_RESULTS -->

The model-free oracle probe substitutes **only its own code** for `/solution`; it does not put
`policies.py` or simulator source in `main`. Harbor deliberately uploads `/solution` for its
oracle agent; OpenCode does not receive it. This distinction prevents mistaking the audit's
instrumentation for a source leak. The bare-template failure reported above is a separate
packaging test, not one of the 27 requested variant repetitions.

[integrity.py](integrity.py) also invokes the captured verifier directly: a valid reference
receipt scores 1; a missing receipt, missing signature, tampered action list and a correctly
signed but illegal action log all score 0. [integrity.json](integrity.json) preserves each result
and rejection message. Signing an illegal action does not exempt it from replay validation.

## Main-container shell and HTTP boundary

[probe.py](probe.py), run by [probe.sh](probe.sh), executed in Harbor's `main` container as uid 0.
[probe-results.jsonl](probe-results.jsonl) preserves the actual results and tool schemas;
[probe-reward.json](probe-reward.json) is its real verifier ledger.

| Probe | Observed result |
| --- | --- |
| Connect directly to `http://mcp-server:8000/mcp` with Python/HTTP | Allowed and unauthenticated, as the MCP client needs. This is the same tool interface, not a second state-changing API. |
| `tools/list`, unknown `reset/sign/get_seed/get_source/__dict__`, `/docs`, `/openapi.json`, `/server.py`, `/incident.py`, `/sse`, `/` | Only the 15 expected tools listed; unknown tools rejected and other routes returned 404. No signing/reset/source method. |
| 410 concurrent direct-HTTP topology calls after one accepted topology call | 399 succeeded, 11 were rejected. The accepted ledger had exactly 400 actions. `get_topology` is clock-free but counts against the accepted-call cap. |
| `wait(1)` and topology after the cap | Rejected with `call budget exhausted; call finish`. Concurrent calls use the same lock; opening new HTTP clients does not reset the episode. |
| `get_status` before/after the cap | Both available, minute remained 0 and estate unchanged; this free uncounted status is documented. |
| `finish` after the cap | Allowed, settles to minute 120 and charges the rest of the shift. Ledger has 401 actions because finish is the explicit budget exception; reward 0, true do-nothing cost $232,523.28. |
| Read seed, level, calibration, verifier or simulator on disk | `/tests`, `/tests/grade.py`, `/tests/calibration.json`, `/srv/incident.py`, `/srv/server.py`, `/app/incident.py` and `/proc/1/root/srv/incident.py` absent. No `SEED`/`LEVEL` environment variable or Docker socket. Topology/status/log output does not include a seed. |
| Read/write receipt | Readable; mount reports `ro`. Opening for write and chmod fail with `EROFS`; replacement fails across devices; remount fails with permission denied. Running as root in this container does not grant mount capability. |
| Fetch public simulator source from unauthenticated GitHub raw URL | HTTP 404 from inside main. Public networking exists, but this URL did not expose source in the tested run. This is not a guarantee about future repository visibility. |
| Agent-writable `/logs/verifier` | A detached Python process repeatedly overwrote both reward files with a fake score of 1 while making no estate calls. The separate verifier still returned reward 0 and the exact do-nothing cost. Harbor stops the agent environment and empties verifier output before trusted tests. |

Container configuration matches the probe: the main image copies no task code; the sidecar
image alone copies `incident.py`/`server.py`; `ledger:/ledger:ro` is main's mount;
`environment_mode="separate"` isolates verifier code and calibration. `network_mode="public"`
means writing an HTTP client is permitted, but it buys no free metric/log calls. The MCP server
does not serve its filesystem. Signed action logs contain actions, not the seed.

The HMAC key is a static spike constant shared by sidecar and verifier (`incident.py:79–80,966`).
It is **not** a defensible secret if the simulator becomes obtainable, and the signature does
not bind a per-episode nonce/seed. In the tested setup, knowing it still would not let main
replace the read-only artifact. This is a hardening limit, not a demonstrated signing bypass:
use a per-run server/verifier secret and bind the episode before relaxing that file boundary.

An agent can write a script that drives the normal tools or applies its own runbook. That is
automation within the task, not a scoring shortcut: it still pays every simulated minute and
replica/mitigation cost. No successful shell-only route around diagnosis, clock, cap or trusted
replay was demonstrated. The probe is targeted boundary testing, not an exhaustive container or
MCP-library security assessment.

The reward-file attack is reproducible with [reward_spoof.py](reward_spoof.py) and
[reward_spoof.sh](reward_spoof.sh); its trusted result is [spoof-reward.json](spoof-reward.json).

## The reference as a human on-call runbook

1. **Map dependencies and money.** Read `get_topology` for service names, dependencies,
   normal replicas, retries and edge revenue. Compute the edge revenue potentially affected
   by each service. Read `get_status` for the current minute, actual customer error rates and
   operations already running. Aim at dollars lost, not just the loudest alert.
2. **Separate causes from propagated failures.** Read `list_alerts`; when `total` exceeds the
   returned list, query app and data tiers as well. Compare each service's measured errors
   with the failures its visible dependencies explain, and retain memory-pressure suspects.
   Rank by estimated loss divided by diagnosis effort. These are estimates, especially when
   alerts are still truncated within a tier.
3. **Account for quiet customer errors.** Use `get_status.edge` to find errors above the
   healthy baseline that the alert set does not explain. Read that edge's `get_logs`; follow
   named failing upstream calls until a service reports its own error, or a caller names an
   error that the blamed service does not report. That second case is allowed by the briefing's
   differential-observability warning. The code follows only one upstream path at a time;
   a robust human must keep alternative branches open when the first one does not explain it.
4. **Identify the fix from evidence.** For a suspect, read `get_logs` for a failed primary,
   memory/GC failure, queue shedding or a concrete error symptom. Use `get_changes` and
   `get_diff` to connect a symptom to the deploy or config that changed the relevant behavior.
   For memory pressure, the code uses a recent-deploy rollback heuristic without measuring
   the full memory history. For twins, the code sometimes infers the second diff instead of
   reading it; this is the disputed shortcut, not advice an expert should mistake for proof.
5. **Distinguish demand from retries.** Read `get_metrics.rps/retry_share/cpu/replicas`. Compare
   fresh traffic, `rps*(1-retry_share)`, with a calm pre-onset sample; use a historical metrics
   window if needed. Scale for genuinely increased demand. A high CPU alone, or a retry warning
   beside a still-present application error, does not establish a traffic surge.
6. **Protect a quiet service before a disruptive fix.** Read its metrics, topology retry count,
   normal replicas and the briefing's rollback/restart disruption. Estimate whether retries of
   those failed requests would exceed capacity. Compare temporary spare replicas with the
   revenue rejected by a throttle. If scaling wins, start `scale`, read its returned completion
   time and wait until capacity lands before rolling back. The reference may begin preparation
   while reading diffs; a recent change alone is not proof to revert it.
7. **Mitigate and clear residual retries.** Use the diagnosed `rollback`, `revert_config`,
   `failover` or `scale`. Read `completes_at_minute`. If the predicted failure/retry load will
   hold the service down, apply a short `throttle` to be effective as the fix lands, then set
   it back to zero the next minute. If a fixed service is still CPU-bound, read fresh metrics
   and estimate whether it needs a residual drain; do not undo a correct fix merely because
   the backlog survives it.
8. **Return borrowed resources and verify customers.** Use the completion times and
   `get_status` to lift every throttle and scale temporary protection back to normal. Watch
   actual edge errors. Recheck explanations when they remain high; the current policy does
   not always do this successfully on unseen graphs.
9. **Remain on shift.** Read free `get_status` and use `wait` to advance to operations or the
   next minute. Re-enter triage when new customer errors appear. Continue to minute 120;
   early `finish` does not erase later faults or any remaining lost revenue.

The hindsight in this runbook is choosing useful prioritisation, demand-change, CPU, drain and
safety thresholds, plus recognising a fixed set of operational log forms. That is fair where
the **facts** are visible: revenue, dependency kinds, onset, RPS, retry share, CPU, changes and
diffs are available to the agent; timing, costs and retry feedback are disclosed. Neither an
engineer nor the reference needs a hidden fault list to make those decisions. Conversely, the
two-change certainty and “memory implies a recently leaking build” certainty are not facts shown
on the screen. They must be treated as uncertain priors or replaced by additional diagnosis.

## Reproduction

From the project root, use the declared Nix environment; no credentials are required:

```sh
nix develop -c python3 -B projects/oncallbench/audit/check.py
nix develop -c bash projects/oncallbench/audit/harbor.sh
nix develop -c bash projects/oncallbench/audit/probe.sh
nix develop -c bash projects/oncallbench/audit/reward_spoof.sh
nix develop -c uvx --from harbor==0.25.0 harbor run -p projects/oncallbench/audit/runtime/task -o projects/oncallbench/audit/runtime/bare-jobs --job-name bare-task-nop -a nop --quiet
nix develop -c python3 -B projects/oncallbench/audit/inventory.py
nix develop -c python3 -B projects/oncallbench/audit/diagnose.py
nix develop -c python3 -B projects/oncallbench/audit/collect_results.py
nix develop -c python3 -B projects/oncallbench/audit/integrity.py
nix develop -c python3 -B projects/oncallbench/audit/summarize.py
nix develop -c python3 -B projects/oncallbench/audit/validate.py
```

`check.py` without `--root` captures the current source. To reproduce the **audited** source
instead, first extract the committed archive into `audit/runtime`, then pass
`--root projects/oncallbench/audit/runtime` to `check.py`; this preserves the snapshot across
future improvements. Remove old runtime job/probe folders before repeating names. Raw console
logs are retained alongside the compact JSON evidence. Only files under `audit/` are committed.

[validation.json](validation.json) checks the 200 distinct fresh seeds, all 39 counterexample
records, all 27 unique Harbor repetitions, report links, source archive hashes and evidence
consistency. At audit completion, every original source hash still matched the snapshot.
After rebase, only the concurrent documentation/level-5 briefing changes described above differed;
simulator logic and the level-4 briefing still matched.
