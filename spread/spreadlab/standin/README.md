# The stand-in: screen a Spread variant offline before it costs play time

A simulated week that the real desk code plays. It reads saved weeks only: no team key, no practice world, no secret.
Use it to rank ideas and drop weak ones. It does not replace a played exam (see "How far to trust it").

## Screen a variant (one step)

Push the branch that has the variant in its `spread/spreadlab/variants.py`, then:

```bash
gh workflow run standin-screen.yml --repo katalystsoftware/junction2026 --ref spread-standin \
  -f ref=<your branch> -f arms=<variant>,<variant>,...
```

- It plays every arm and the baseline on the same 206 saved seeds (114 natural, 92 thin, under 720 drivers) on one
  32-core CRACI runner, with the desk code of `ref`. `-f baseline=<variant>` names what the arms are compared with; left
  out, it is merge 1 (`fee16-80-q24-wide-pairs-0.6-return-0.75`), which is no longer the base. `-f half=a` and
  `-f half=b` take every other seed, `-f draws=2` narrows the intervals.
- Time: 7 arms took 4 min 41 s to play (1,442 weeks), about 5.5 minutes with the runner's start. Two arms and the
  baseline take about 2.5 minutes. Several runs go at once, each on its own runner.
- Result: the run's summary page, and the artifact `standin-screen` with `rows.csv` (one row a variant, seed and draw,
  in the columns of the `trackb-rounds` row files plus the money lines) and `summary.md` (natural and thin apart, and for
  each arm PASS, FAIL or NEEDS PLAYED THIN WEEKS with its reasons: the merge gate below).

```bash
gh run list --repo katalystsoftware/junction2026 --workflow standin-screen.yml -L 3     # find the run
gh run download <run id> --repo katalystsoftware/junction2026 -n standin-screen -D out   # rows.csv, summary.md
```

On a machine with the packed weeks (release `spread-standin-screen`, unpacked into the data folder):

```bash
cd spread && uv run --with numpy python -m spreadlab.standin.screen --arms <variant> <variant> --out out
```

## The merge gate

A part merges onto the base on the stand-in alone; the base's played weeks judge it afterwards. The review thread owns
that rule. This is what the screen's line for each arm says about it:

```bash
git fetch origin && git merge origin/trackb-merged        # or rebase: your branch then has the base's variant and desk code
git push
gh workflow run standin-screen.yml --repo katalystsoftware/junction2026 --ref spread-standin \
  -f ref=<your branch> -f arms=<variant>,<variant> -f baseline=<base variant> -f half=a      # then the same with half=b
```

- **The baseline is the current base**, the variant `origin/trackb-merged` plays, and it moves with each merge. Without
  `-f baseline` the screen compares with merge 1 and counts the base's own parts as the arm's gain; the summary says so.
  A branch that lacks the base's variant stops at once with "Not in this checkout's variants.py".
- **PASS**, needed on half a and on half b: over 500 euros a week on natural worlds with the 95% interval above zero, no
  loss on thin worlds, and no more natural weeks under 90% than the base.
- **A gain on thin worlds (under 720 drivers) does not count.** Play returned 0.18 to 0.39 of a stand-in thin gain, and
  the stand-in sees about a third of play's thin weeks under 90%. It reads merge 1 at +2,650 a week over the base on
  thin worlds, with 27% more orders and as many weeks under 90%, where play has merge 1 under 90% in 3 thin weeks of 60
  and the base's all-hours count lifting those to 93 to 95%. A gate that counted thin gains would undo the base.
- **NEEDS PLAYED THIN WEEKS**: the arm does not fail, and on worlds under 760 drivers (the base's line for a short driver
  list) it wins over 3% more orders or has over 10% more late orders than the base. Such a part plays thin weeks before
  it merges, whatever the stand-in's on-time numbers say.
- **Weeks under 90%** are a tripwire on natural worlds, where the stand-in counts as many as play or more. On a half every
  desk has 0 or 1 of them, so an equal count is no evidence that a part is safe.
- 500 is not a noise margin: one half's gain has a standard error of 60 to 200 a week. The stand-in's errors are bias.
  Expect about three quarters of a natural-world gain in play, and about two thirds where the gain is more orders.

The stand-in cannot judge, so such parts still need played weeks:

- Margin and on-time on thin worlds.
- New pair shapes. No pair gig was in the weeks the drivers were fitted on, so a gig with two cars is booked like a
  one-car gig. On the pair ladder the order held (18 of 18 decided pairs) and the sizes read up to twice play's.
- Stacked merges. The accuracy below was measured one step from the default or from merge 1; no played week of merge 1 or
  a later base is in the fitted data yet.
- Note reading, cancelled and changed orders, failed visits, snow, the competitor's answer to what the desk wins.

## Climbing on it

A search that keeps the best of many variants on the same seeds fits those seeds and the stand-in's own errors.

- Climb on half the seeds (`-f half=a`, 57 natural and 46 thin) and confirm the winner once on the other half
  (`-f half=b`). A gain that does not hold on `b` was noise.
- A step counts when the merge gate passes it against the current best. Two variants within about 500 euros a week are a
  tie here: play did not decide such pairs either.
- Hold thin weeks under 92% at the baseline's count: that count did mark merge 1 as the riskiest of the pair ladder.
- What comes out of the climb goes through the merge gate like any lane's part.

## How it is built

- `world.py`: `StandIn` has the routes a desk uses of Bahn's practice world (`advance`, `act`, `snapshot`, `roster`,
  `score`). `play.policy_class` gives the same desk class that plays on Bahn's server, unchanged.
- Dealers: a quote wins by the team's win curve at each day's level, measured on the default desk's played week of the
  same seed. A request the played week answered keeps a hidden draw that agrees with that answer at that price.
- Drivers: an open gig is booked by a fitted chance a minute (`model.py`, `fit.py`: a Poisson regression on 4.6 million
  slices of 2,771 played weeks), moved by each day's own booking speed on the seed's played week. Drops, the night the
  drivers drop out, the time a booked driver collects the car and the drive come from fitted tables.
- Rules: fee schedules, stop windows, expiry, the deadline warning, direct offers and the account follow RULES.md.
- Not in it: cancelled and changed orders, failed visits, fines, snow's slower drives, and drivers as people with a day.
  No pair gig was in the weeks it was fitted on: a gig with two cars is booked like a one-car gig with its fee, drive
  and places.
- Parallel: each (variant, seed, draw) is one independent week in a process pool, one a core. A week takes 3 to 6 CPU
  seconds, 97% of it in the desk's own code (`notes.near` most of all) and 3% in the world.

`pack.py` packs recordings into the small files it reads, `run.py` compares arms, `check.py` sets one arm beside its
played weeks, `validate.py` scores it on played paired checks, `screen.py` is the lanes' entry.
`.github/workflows/standin.yml` fits and checks each design of `designs.json` on its own runner (push to `standin-ci`).

## How far to trust it

Measured on seeds the fit never saw (`fresh-`), on 150 played paired checks of 60 policies against two baselines,
1,658 and 1,434 played weeks (CI run 43635516836, design `react-0-fee-common`, which is what ships), and on the window
ladder's seven pair variants (`ladder1-rows.csv`, 40 played weeks; the stand-in played other seeds, 206).

| Question | Natural worlds | Thin worlds |
| --- | --- | --- |
| Which of two policies is ahead, where play decides it (played 95% interval excludes zero) | 43 of 46 and 35 of 35 pairs agree | 18 of 21 and 6 of 9 |
| The same on the ladder's pair variants | 17 of 17 (19 of 21 with the undecided) | 13 of 13 (20 of 21) |
| Keep or reject (gain above zero, at most 1 week in 60 under 90%) | 92% and 86% agree | 92% and 78% |
| Size of the gain: correlation with play, played gain per unit of stand-in gain | 0.96 to 0.97, 0.78 to 0.80 | 0.37, 0.18 to 0.39 |
| Typical miss of a gain, euros a week | 880 to 910 | 1,200 to 1,450 |
| Weeks under 90% per 60, played against stand-in | 0.33 against 0.42, 0.14 against 0.88 | 2.30 against 0.72, 1.05 against 0.66 |
| Weeks under 92% per 60, played against stand-in | 1.59 against 1.34, 1.16 against 3.06 | 8.78 against 5.04, 4.75 against 3.96 |
| One week against the played week of the same policy and seed: margin | off by 1,290 to 1,330 (13%), correlation 0.90 to 0.91 | off by 1,440 to 1,740 (16 to 19%), correlation 0.82 to 0.86 |
| ... orders | off by 22 to 24, correlation 0.92 | off by 21 to 23, correlation 0.88 to 0.91 |
| ... on-time share | off by 2.0 points, correlation 0.11 to 0.13 | off by 1.9 to 2.0 points, correlation 0.26 to 0.27 |

**Our own progress, played again from scratch** (run 43637692288, `scratch/standin/progress_check.py`): 14 milestones
from `baseline` to merge 1 on 266 seeds, each beside its played weeks on the same seeds. Gain over the reference
`steep-notes-offers-8`, euros a week:

| Milestone | Seeds | Played (95% interval) | Stand-in | Orders, played / stand-in |
| --- | --- | --- | --- | --- |
| `baseline` | 15 | -10,773 (-11,910 to -9,567) | -11,735 | 153 / 166 |
| `gate-10` | 42 | -6,068 (-6,541 to -5,569) | -7,221 | 190 / 159 |
| `curve-live-surcharge` | 40 | -4,189 (-4,541 to -3,831) | -5,847 | 226 / 182 |
| `curve-fee-1.0-cost-1.2` | 40 | -1,593 (-2,011 to -1,212) | -3,449 | 266 / 229 |
| `fee-cap-1.2-drop-cost-1.3` | 45 | -1,029 (-1,320 to -723) | -809 | 229 / 229 |
| `notes-offers-8` | 45 | -418 (-699 to -108) | -766 | 237 / 230 |
| `steep-notes` | 40 | -155 (-328 to +24) | -266 | 256 / 255 |
| `slow-step-gate-25` | 151 | +890 (+592 to +1,255) | +609 | 290 / 292 |
| `slow-step-gate-25-kinds` | 100 | +1,309 (+1,032 to +1,639) | +886 | 304 / 302 |
| `slow-step-gate-25-kinds-limits` | 40 | +1,211 (+851 to +1,594) | +608 | 300 / 296 |
| `slow-friday-late-150-kinds` | 60 | +1,534 (+1,152 to +2,072) | +1,423 | 314 / 314 |
| `slow-friday-late-150-kinds-limits` (default) | 265 | +1,731 (+1,465 to +2,007) | +1,195 | 306 / 304 |

Every milestone is on the same side of the reference as in play, 12 of 12, and the chain comes out in play's order. From
the fee cap on, the desk family the stand-in was built around, a variant's margin a week is within 500 of play's and its
orders within 7; the steps since the reference read 7 to 50% low, most on thin worlds (default: +990 against +1,776).
The three early desks read 1,000 to 1,900 too low, with 14 to 19% too few orders: far from today's prices and fee
schedules the sizes are off. The default's own played weeks are what each seed's market is measured on, so its row is
not an independent check. Merge 1 and the first distillation have no played week on these seeds: the stand-in has them
+3,891 and +1,392 over the reference, where play's two steps on other seeds add to about +3,900 and +2,770.

Trust it for:
- **Order.** Which of two variants is ahead, when the stand-in's gap is clear. On natural worlds it agreed with every
  pair play decided against the reference and 93% against the default; on the pair ladder with all of them.
- **Dropping a variant that loses or does nothing.**

A single stand-in week says little: it is 13 to 19% off in margin, and its on-time share barely follows the played week's
(the week-by-week rows are 3,092 weeks of CI run 43636949086, the base policy's own weeks left out). The agreement is in
paired differences over many seeds. A second calibration round of 14 designs found none clearly nearer to play; two draws a
seed raise the natural ranking agreement to 44 of 46 and 34 of 35.

Do not trust it for:
- **The size of a gain.** Between pair variants it reads gaps about twice as wide as play (fee16 to q24: 2,486 against
  876). Against the default it reads q24, q12 and merge 1 at 2,692, 3,169 and 2,740 where play has 1,914, 2,121 and
  2,167, and the all-hours ladder at 206 where play has 1,038. Two variants within about 500 of each other in the
  stand-in are a tie: it puts q12 first where play has merge 1 46 ahead, undecided.
- **Thin worlds' sizes.** The order holds, the numbers do not (correlation 0.37).
- **Weeks under 90% on thin worlds.** It sees about a third of play's. Merge 1 has 1 thin week in 92 under 90% here and
  3 in 60 in its played exam. It does mark merge 1 as the riskiest of the ladder by thin weeks under 92% (11 of 92
  against the default's 4), so read that count against the baseline's, and keep the played exam for the 90% rule.
- **Anything it has no mechanism for**: note reading, failed visits, cancellations, snow, the competitor's answer to
  what the desk wins (off by default: with it the gains were about 700 a week further from play's).
