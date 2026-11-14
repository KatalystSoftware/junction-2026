# Spread harness

Tools for the Bahn Express "Spread" challenge: scan practice weeks, play policy variants on the same
seeds, and see where each variant loses money. The challenge brief is in
[`docs/challenges/main/bahn-express--spread.md`](../docs/challenges/main/bahn-express--spread.md).

The harness plays practice worlds only. It cannot start a ranking run: that is a decision for a person.

## Setup

Needs [uv](https://docs.astral.sh/uv/) and the team key from https://spread.bahnexpress.com/team.

```bash
cd spread
uv sync
export SPREAD_KEY=<team key>
uv run pytest
```

Scans and runs go to `data/`, which is not committed. Set `SPREAD_DATA` to keep them elsewhere.
The catalogue in `catalogue/` is committed, so everyone uses the same seed lists.

## Saved weeks

`archive/bundles/` holds the scans, the played weeks and the map, so they survive the machine that
played them. The harness does not read it; unpack it into the data folder first.

```bash
git lfs install && git lfs pull                # fetch the bundles; without Git LFS they are short text pointers
uv run python -m spreadlab.archive unpack      # write the files the data folder lacks; --force overwrites
uv run python -m spreadlab.archive pack        # before a commit: pack what no bundle holds yet, then commit archive/bundles
```

A bundle is one tar of the plain JSON, ordered by seed and compressed as a whole with `zstd`, which
both commands need. The weeks of a seed repeat its scan and each other, so a bundle is about a
seventh of the size of the same files gzipped one by one. A bundle is never changed, because Git LFS
stores a changed file again in full: each `pack` writes a new one, named by the UTC time, with a
`.sha256` list of its files beside it. A week that was played again goes into the new bundle, and
`unpack` takes each file from the newest bundle that holds it.

A sweep plays a saved week again when the policy code has changed since, so old weeks of a variant
are a record, not a cache. `scratch/` holds the one-off analysis scripts behind the results; run them
from this folder with `PYTHONPATH=. uv run --with scikit-learn python scratch/<name>.py`.

## Commands

| Command | What it does | Cost |
| --- | --- | --- |
| `uv run python -m spreadlab.scan --prefix cat- --count 300` | Plays each seed to its end with no actions and saves its requests, snow forecasts and drivers | 5 requests a week |
| `uv run python -m spreadlab.catalogue` | Builds `catalogue/catalogue.json` and the seed lists in `catalogue/seeds.json` from the scans | none |
| `uv run python -m spreadlab.play --variant baseline --seed cat-001` | Plays one week with a variant and saves the run | 900 to 1,200 requests |
| `uv run python -m spreadlab.sweep --variants baseline,price-1.6 --list tune --count 10` | Plays the variants on the first seeds of a list, 7 weeks at once, and prints the comparison | one week each |
| `uv run python -m spreadlab.report --variants ... --weeks` | Prints the comparison again, with one line per week | none |
| `uv run python -m spreadlab.ledger --variants ...` | Builds the mistake ledger of the variants | none |

A sweep skips a week that is saved with the same parameters and policy code, so it can be stopped
and started again.

## How to try an idea

1. Add a variant to [`spreadlab/variants.py`](spreadlab/variants.py), or a parameter and its rule to
   [`spreadlab/policy.py`](spreadlab/policy.py).
2. Sweep it against the reference variant (see "Results so far") on the `tune` list. The first variant named is the reference.
   Keep `gate-10` in the sweep too: the older results are differences to it.
3. Read the report: ranked weeks first, then the margin. A week under 90% on time scores nothing.
   - `above zero` counts the weeks that are ranked and beat `decline-all`. Declining every request
     makes 0 and is not ranked, because a week with no orders is not ranked.
   - `95% interval` is for the mean difference to the reference, from drawing the weeks again 10,000
     times. When it includes 0, play more seeds before believing the difference.
   - Weeks that are missing or failed are named above the table and left out of it. Play them again first.
4. Read the ledger for where the money went. `in weeks` tells a habit of the variant from one bad week.
5. Confirm on the `holdout` list before keeping the change, and then on seeds that no list holds:
   `uv run python -m spreadlab.scan --prefix fresh- --count 40` scans a batch, and `--seeds fresh-021,fresh-022,...` plays it.

## Results so far

Level 8, mean margin a week in euros on the first 10 seeds of each list. Every week of every row is ranked.

| Variant | What it adds | Tune | Holdout | Lowest on time |
| --- | --- | --- | --- | --- |
| `baseline` | 1.5 x list, 60% of acceptable requests, no `same_day` | 721 | not played | 95.1% |
| `with-same-day` | offers `same_day` | 1,669 | 1,857 | 91.7% |
| `floor-1.7` | never quotes under 1.7 x the typical driver fee | 3,472 | 3,579 | 91.8% |
| `gate-10` | quotes every acceptable request, but none while 10 won cars have no driver | 5,083 | 4,541 | 93.1% |
| `surcharge-4-gate-15` | the floor rises 0.04 x the typical fee for each won car without a driver; the gate moves to 15 | 5,743 | 5,032 | 91.9% |
| `curve` | the win curve sets the price (see "The win curve") | 5,490 | 4,627 | 93.1% |
| `curve-live` | the day's answers correct the curve | 6,487 | 5,609 | 92.2% |
| `curve-live-surcharge` | each won car without a driver adds 0.04 x the typical fee to the order's cost | 7,032 | 6,359 | 95.0% |
| `curve-fee-1.0-cost-1.3` | gigs open at the typical fee, not 1.2 x it, and an order is taken to cost 1.3 x it, not 1.4 | 10,009 | 8,933 | 94.2% |
| `fee-cap-1.2-drop-cost-1.3` | the fee rises to 1.2 x the typical fee and holds, and starts again after a drop (see "Driver fees") | 10,263 | 9,245 | 93.3% |
| `notes-offers-8` | reads the note before the first posting, and sends direct offers for gigs short of time (see "Notes and direct offers") | 10,975 | 10,070 | 93.7% |
| `steep-notes-offers-8` | prices by the curve fitted with a level for each day, which is steeper (see "The win curve") | 11,290 | 10,325 | 92.7% |

`steep-notes-offers-8` is the reference for new ideas. On 40 seeds that no list holds (`fresh-001`
to `fresh-040`, every week ranked) it makes 10,269 against 9,288 for `fee-cap-1.2-drop-cost-1.3`:
981 more (95% interval 689 to 1,279), better in 35 weeks of 40, lowest week 92.0% on time against
91.3%. The last 20 of those seeds were kept unplayed for this check: on them it makes 932 more (640
to 1,227), better in 19 of 20. Over all 60 weeks played, no week is under 92% and three are under 93%.

`fee-cap-1.2-drop-cost-1.3` makes 9,053 on the first 20 fresh seeds against 5,816 for
`curve-live-surcharge`: 3,237 more (95% interval 2,734 to 3,746), better in 20 weeks of 20. Its
lowest fresh week is 91.3% on time, in a world with 644 drivers, against 93.0% for
`curve-live-surcharge`: the lower fee buys margin with part of the distance to the 90% rule.

`curve-live-surcharge` makes 5,816 on the fresh seeds against 3,978 for `gate-10`: 1,838 more (95%
interval 1,355 to 2,359), better in 19 weeks of 20, lowest week 93.0% on time. Its three numbers are not
sensitive on the tuning seeds: a cost of 1.3 or 1.4, a day's correction of 0.10 to 0.25, a backlog
step of 0.04 or 0.08, and the gate at 10, 15 or off all land within 350 of each other, inside the
noise of 10 weeks. `floor-1.7-all` shows why `gate-10` needs its gate: without it, one tight week
falls to 87.4% on time and is not ranked.

Tried against `gate-10` and not kept, as the difference in mean margin (95% interval):

| Variant | Idea | Tune | Holdout or fresh |
| --- | --- | --- | --- |
| `tight-floor` | a higher floor in weeks with few drivers | not played | -968 (-1,539 to -354) on 12 holdout weeks |
| `tight-gate` | a lower gate in weeks with few drivers | not played | 0 on holdout, +65 (-5 to 157) on fresh |
| `gate-10-stop-93`, `gate-10-careful-93` | stop or dearer quotes while the projected on-time share is under 93% | not played | -308 and -35 on fresh |
| `gate-5`, `gate-15` | the gate at another level | -232, +81 | +107 (-160 to 388) and +14 on fresh; `gate-15` has one week under 90% |
| `dealer-ladder`, `monday-1.5`, `ladder` | the floor follows the win share at the dealer; 1.5 on Monday | +165, +154, +126 | +256 (-220 to 765) and -319 (-589 to -74) on holdout |
| `trust-0.5`, `trust-1.0` | the quote rises with the dealer's orders on time | +255, +106 | +136 (-364 to 681) on holdout |

The curve does what the last two rows try by hand, and measures it: the count of orders on time is
one of its terms, and the day's correction finds a cheap Monday or a price-war day from the answers.

## Driver fees

The kit's starter opens a gig at a multiple of the request's typical fee and raises it 10% of that
an hour, to 1.5 times. The policy opened at 1.2 x until `curve-live-surcharge`. What the weeks show:

- **Drivers book in the first minutes or wait for their planning hours.** In a gig's first 15
  minutes, 10%, 19%, 26%, 29% and 31% of the drivers who look at it book it at 0.9, 1.0, 1.1, 1.2
  and 1.3 x the typical fee. After that 2 to 7% book, at any fee up to 2 x.
- **Opening at the typical fee is worth about 2,000 a week, and pricing for it 1,000 more.** On the
  tuning seeds, fees paid fall from 1.30 to 1.09 x the typical fee, and 80% of orders are still
  booked within an hour of the win, against 88%. With the lower cost in the quote the desk wins
  more orders.
- **Lower than that loses the week.** At 0.9 x, 65% are booked within the hour and one holdout week
  is not ranked; at 0.8 x, 40%, and one tuning week is not ranked.
- **Rises after the first hour buy little.** A fee that rises a tenth of the typical fee an hour to
  1.2 x it and then holds (`fee_cap`) pays 0.05 x less with the same bookings in the first hour. No
  rise at all is too little: one tuning week is not ranked.
- **A dropped gig keeps its old fees,** which are at their top by then, though drivers are notified
  again and book it fast. `drop_fee` starts its fees again at 1.1 x the opening fee.

Mean margin a week against `curve-fee-1.0-cost-1.2` (opening 1.0, cost 1.2: 10,057 on tune, 8,709
on holdout), with the 95% interval, the lowest week on time, and fees paid over typical fees:

| Variant | What it changes | Tune | Holdout | Fees paid |
| --- | --- | --- | --- | --- |
| `curve-fee-0.9-cost-1.2` | opens at 0.9 x | +455 (-115 to 1,022), 93.2% | +481, one week not ranked | 1.03 |
| `curve-fee-1.0-cost-1.3` | cost 1.3 | -48 (-567 to 525), 94.6% | +223 (-394 to 787), 94.2% | 1.10 |
| `fee-drop` | fees start again after a drop | +64 (-45 to 167), 92.6% | not played | 1.11 |
| `fee-cap-1.2` | rises to 1.2 x and holds | +330 (-28 to 682), 93.0% | +595 (39 to 1,152), 93.0% | 1.07 |
| `fee-cap-1.2-drop` | both | +420 (187 to 623), 93.0% | +570 (148 to 982), 92.6% | 1.06 |
| `fee-cap-1.2-drop-cost-1.3` | both, cost 1.3 | +206 (-333 to 728), 93.3% | +535 (-28 to 1,148), 94.1% | 1.05 |
| `fee-flat` | no rise | -280 (-1,001 to 351), one week not ranked | not played | 1.04 |
| `fee-cap-1.2-jump`, `fee-flat-jump` | one step to 1.5 x at 04:30 or 16:00, when drivers plan | -23, +104 | -396 (-971 to 117) for the second | 1.08, 1.07 |
| `fee-lane`, `fee-lane-1.05` | the lane's usual fee as the base (`lanes.json`, from 200 scans) | +254 (-114 to 674), -1,136 | +193 (-230 to 618) for the first | 1.10, 1.15 |

On the fresh seeds, cost 1.2 has a week at 88.9% (`curve-fee-1.0-cost-1.2`) and the capped fees
with cost 1.2 one at 91.1%; with cost 1.3 the lowest is 91.3%. So the reference takes cost 1.3: it
wins about 25 orders a week fewer and leaves fewer cars without a driver in a tight week.

```bash
PYTHONPATH=. uv run python scratch/fee_report.py --variants curve-live-surcharge,fee-cap-1.2-drop-cost-1.3  # fees paid, bookings in the first hour, warnings, late orders
PYTHONPATH=. uv run python scratch/driver_views.py --variants curve-fee-0.9,curve-fee-1.0,curve-live-surcharge  # who books at which fee, by minutes open
PYTHONPATH=. uv run python scratch/lane_fit.py --write                                                       # the lanes' usual fees
```

**What the fees still pay over the typical fee** ([`scratch/fee_leak.py`](scratch/fee_leak.py), euros a week). The
clean-room figures, 2,773 for opening at 1.2 x and 1,915 for fees above 1.2 x on rebookings, reposts and overnight
gigs, are those of `curve-live-surcharge` and come out the same here. The fees above are what took most of them back.
On the variants with today's fee schedule (`slow-step-gate-25`, 167 weeks; `slow-step-gate-25-kinds`, 34), fees are
1.07 to 1.09 x the typical fee: 450 to 580 in openings over the typical fee (the kinds and the reposts), and 870 to 940
over the opening, of which 330 overnight, 300 to 330 on rises the same day, 130 on rebookings and 100 to 150 on reposts.

**Fees by each car's risk** (`risk-*`, [`riskfee.py`](spreadlab/riskfee.py), on the live default, not played yet). A
car with 16 hours or more to its last pickup and a late chance under 6% opens at 0.9 x (81% of one-car orders, 2.3%
late); a gig holds its opening fee until the car's late chance with the hours left reaches 4%, then rises as now:
22% of cars from the posting, 13% with under 24 hours left, 30% under 12, 17% under 8 and 18% under 6. `risk-hold` is the hold
alone, `risk-open` the lower opening alone, and `-due-24` counts only the waiting cars due within 24 hours in
`slow_step` and the gate.

Private addresses (`curve-private`, +246 on tune at the old fees; -38 with opening 1.0, lowest week
92.0%), a cost that follows the order (`curve-order-cost`, +193, -16 to 411) and counting what an
order on time is worth in the dealer's later prices (`curve-trust-0.3`, -126; `curve-trust-1`,
-1,655) were tried on `curve-live-surcharge` and not kept.

## Notes and direct offers

Both are about the orders that end late, not about the price. Of the late orders of
`fee-cap-1.2-drop-cost-1.3` over 40 weeks, 39% had no driver by the last minute to collect the car,
15% were dropped, and 14% had a failed visit.

**The note is read before the first posting** (`read_notes`, [`notes.py`](spreadlab/notes.py)). The
kit's starter reads clock times on the day the window starts and learns the rest from a failed
visit, which costs half the fee and often the deadline: every order whose car had no plates failed
once. The reader finds the first minute the car can be collected (day words, weekday names, hours in
words, "puoli", am and pm, corrections, denied times, payment notes), plates to bring and a manual
licence. Against the reveal, on 1,291 won orders with a note that it was not written against, the
pickup time was right on 1,290, plates on 41 of 41, and the licence on 26 of 26 with one false
alarm; both misses are fixed since. Failed visits fall from 8.8 to 1.2 a week, and their account
lines from 332 to 53 euros.

**Open gigs that are short of time get direct offers** (`offer_hours`). Once an order must be
collected within 8 hours and its gig has been in the app for half an hour, the desk sends three
offers at a time, at 1.3 x the typical fee or the fee in the app if that is higher, to the drivers
nearest the pickup among those who looked at one of its gigs or booked one that day: the driver list
does not show who works, and a look does. Of about 950 offers a week, 27% are read and 6 are
accepted, most of them before 15:00 and by drivers who live within half an hour of the pickup. That
is few, and they are the cars that would have had no driver: deadline warnings fall from 22 to 18 a
week on the fresh seeds.

Mean margin a week against `fee-cap-1.2-drop-cost-1.3`, with the 95% interval, and the lowest week
on time on the tune, holdout and first 20 fresh seeds:

| Variant | Tune | Holdout | Fresh, 20 | Lowest week on time |
| --- | --- | --- | --- | --- |
| `notes` | +261 (-135 to 648) | +683 (324 to 1,103) | +337 (-35 to 683) | 94.2%, 92.9%, 90.5% |
| `offers-24` | +423 (93 to 810) | +250 (-211 to 736) | +54 (-250 to 352) | 95.0%, 92.7%, 92.7% |
| `notes-offers-8` | +712 (202 to 1,204) | +825 (347 to 1,336) | +525 (58 to 951) | 95.5%, 93.7%, 92.6% |
| `notes-offers-24` | +687 (330 to 1,013) | +736 (398 to 1,106) | +669 (269 to 1,062) | 95.3%, 92.9%, 92.3% |

Notes alone leave one fresh week at 90.5%, and offers alone add little margin: together they earn
the margin of the notes and keep the lowest week over 92%. On `fresh-021` to `fresh-040`,
`notes-offers-8` is +308 (-5 to 606), lowest week 92.2%.

Tried for the weeks nearest the 90% rule and not kept, on the tune seeds unless stated:

| Variant | Idea | Result |
| --- | --- | --- |
| `tight-720`, `tight-720-mild` | gigs open at 1.2 x or 1.1 x in a week with under 720 drivers | -718 (-1,197 to -297) and -378 on fresh; lowest fresh week 92.7% and 92.4% |
| `guard-94`, `guard-95` | the same while the projected on-time share is under 94% or 95% | -275 and -273 |
| `long-decline`, `long-1.5` | decline drives of over 400 minutes, or open them at 1.5 x | -207 (-560 to 185) and -185 |
| `deep-0.9`, `deep-0.9-thin-1.05` | open at 0.9 x where 100 or more drivers are notified of the pickup | -262 (-658 to 166) and -496 |
| `offers-8-1.5` | offers at 1.5 x the typical fee | +138 (-65 to 335), as `offers-8` at 1.3 x (+134) |

```bash
PYTHONPATH=. uv run python scratch/notes_rows.py explore,gate-10 rows.jsonl   # one row for each won order with a note
PYTHONPATH=. uv run python scratch/notes_check.py rows.jsonl --show 20        # the reader against the reveal
PYTHONPATH=. uv run python scratch/late_causes.py --variant notes-offers-8    # why orders were late
```

**The note check** ([`notecheck.py`](spreadlab/notecheck.py)) scores the rules (`notes.read`, `notes.limits` and
`notes.summer_tyres`) against the reveal on every won note of the archive, field by field: 66,672 notes of 483
seeds in [`catalogue/note-truth.jsonl.gz`](catalogue/note-truth.jsonl.gz). A fifth of the wordings, chosen by a
hash of the text with its digits masked, is held out: rules are fixed from the other four fifths, and the held-out
fifth says whether a fix generalises. CI runs `--check`, which fails when any field misses more notes than
[`catalogue/note-misses.json`](catalogue/note-misses.json) allows. Misses before and after the fixes of 14 November:

| Field | Dev, 53,828 notes | Held out, 12,844 notes |
| --- | --- | --- |
| Ready time | 14 → 0 | 3 → 0 |
| Plates | 2 → 0 | 0 → 0 |
| Manual | 18 → 0 | 8 → 1 |
| Note deadline | 1 → 0 | 3 → 1 |
| Pickup hours | 12 → 0 | 6 → 3 |
| Delivery hours | 2 → 0 | 0 → 0 |
| Summer tyres | 550 → 0 | 173 → 0 |

Hours count only sites whose request states hours, and a note's deadline only when it is earlier than the order's.
The policy does not act on summer tyres yet; the field is read so that the desk can.

```bash
python3 -m spreadlab.notecheck                              # the table (plain python3, about 30 s)
python3 -m spreadlab.notecheck --check                      # what CI runs; add --write after an improvement
python3 -m spreadlab.notecheck --show 20 --field deadline   # the dev split's misses on one field
uv run python -m spreadlab.notecheck extract                # rebuild the truth from archive/bundles (git lfs pull first)
uv run python -m spreadlab.notelabel label data/llm-notes/unlabelled.jsonl --new --limit 1500   # Claude Opus labels notes without a reveal
uv run python -m spreadlab.notelabel report data/llm-notes/unlabelled.jsonl --show deadline     # where the rules disagree with the labels
```

`notelabel` needs `ANTHROPIC_API_KEY`. On 317 held-out won notes Claude Opus 5.5 (adaptive thinking, low effort)
missed one field against the reveal, a pickup closing time, so its labels stand in for the truth on wordings that no
won note has.

## The win curve

[`curve.py`](spreadlab/curve.py) gives the chance that a dealer buys at a price, and the policy
quotes the price with the highest (price - cost) x chance. The curve is fitted on 50 weeks that
quoted a random multiple of the list price on every request (variant `explore`, seeds `explore-001`
to `explore-050`, 41,306 quotes). What it holds, because it is the same in every world:

- The slope: a price 10% higher multiplies the odds of a sale by 0.42.
- The dealer's count of orders on time: each one raises the prices it accepts by about 1%, as RULES.md says.
- The options quoted, the typical fee over the list price, and the pickup and delivery places.

What differs by world and by day is not in the weights: the competitor's level, its day factor and
the price-war day. The desk measures it as one shift of the curve along the price, from the answers
it has had so far today (`learn`, the prior spread of a day's shift). On unseen weeks, read in time
order, the log loss falls from 0.350 without the shift to 0.280 with it. A shift per dealer makes it
worse (0.297 to 0.331): one shift per day is enough. The cost of an order is 1.4 x its typical fee,
the mean of fees, failed visits and refunds over the random-price weeks (1.28 to 1.59 by week).

**Inside a day the curve is steeper** (`model: "day"`, [`curve-day.json`](spreadlab/curve-day.json)).
Days differ in their price level, and a fit over all days takes that spread for a flatter curve. The
same weeks fitted with a level for each week and day give a slope of 12.5 where `curve.json` has 9.2:
a price 10% higher multiplies the odds by 0.30, not 0.42, and each order on time is worth 1.4% of
price, not 1.1%. The desk prices inside a day once it has the day's shift, so the steeper curve is
the right one there. It quotes lower and wins about 20 orders a week more.

Mean margin a week against `notes-offers-8`, which has the flatter curve and is otherwise the same:

| Variant | Tune | Holdout | Fresh 1 to 20 | Fresh 21 to 40 | Lowest week on time |
| --- | --- | --- | --- | --- | --- |
| `steep-notes-offers-8` | +315 (-555 to 1,072) | +255 (-260 to 756) | +506 (78 to 979) | +624 (371 to 866) | 93.8%, 92.7%, 92.0%, 92.0% |
| `steep-notes-offers-8-cost-1.4` | -100 (-672 to 391) | -124 (-590 to 308) | -17 (-367 to 377) | not played | 94.4%, 93.5%, 92.8% |
| `steep-notes-offers-8-guard-92` | +233 (-843 to 1,096) | +132 (-528 to 743) | +424 (33 to 794) | +479 (231 to 714) | 93.6%, 93.2%, 92.7%, 92.0% |
| `steep-notes-offers-8-guard-93` | +452 (-95 to 1,044) | +29 (-756 to 739) | +237 (-194 to 639) | not played | 93.7%, 92.0%, 91.6% |

The extra orders are what the steeper curve earns and what it costs: about 11 late orders a week
against 10, and a lowest week 0.2 to 1.7 points lower on each of the four seed sets. A cost of 1.4
in the quote gives the orders and the margin back. A guard that quotes no `same_day`, opens gigs at
1.2 x and counts a cost of 1.6 x while the projected on-time share is under 92% costs about 100 a
week; it lifts the lowest week by half a point on two seed sets and not on the last one. Without the note reader the steeper curve is within
noise on the tune seeds (`steep`, -202, -1,019 to 489; `steep-cost-1.2`, +507, -127 to 1,094, lowest
week 92.4%).

```bash
uv run python -m spreadlab.sweep --variants explore --seeds explore-001,explore-002  # play random-price weeks
PYTHONPATH=. uv run python scratch/curve_rows.py                                     # one row per quote
PYTHONPATH=. uv run --with scikit-learn python scratch/curve_fit.py --write          # fit, test on unseen weeks, write curve.json
PYTHONPATH=. uv run --with scikit-learn python scratch/curve_live.py                 # what each live correction is worth
PYTHONPATH=. uv run --with scikit-learn python scratch/curve_day.py --write          # the fit with a level for each day: curve-day.json
```

Random prices lose money on purpose, so `explore` is never a candidate. It is safe only because
practice weeks do not count for the ranking.

**An offset for each dealer adds little** (`dealer_sd`, `dealer_drift`, [`dealer.py`](spreadlab/dealer.py), variant
`slow-friday-late-150-kinds-limits-dealer`, not played). The day's shift and an offset for each dealer are fitted
together from the day's answers in one likelihood. A sale or a loss is a censored answer, and the curve's chance is its
likelihood. Each offset starts the week at N(0, 0.015²): a dealer with few answers stays at the market's level. Each
morning the day before's posterior carries over with 0.02² added, so a dealer's step never falls under the drift's.
Offline, on the weeks of `steep-notes-offers-8` (371 held-out weeks, the holdout list and the fresh seeds):

- Dealers differ little. Fitted in hindsight, the dealers' offsets over a week spread 0.035 in log price beyond the
  sampling noise. Inside a dealer's week the offset falls 0.05 (0.04 to 0.06) per unit of yesterday's win share there:
  the competitor's morning cut where the desk wins most.
- Log loss, quotes read in time order: 0.4721 with the day's shift alone, 0.4690 with the offsets (-3.1e-3, -3.7e-3 to
  -2.6e-3); on the three largest dealers' quotes on Monday and Tuesday, -1.6e-3. Wider priors are worse: 0.06 makes it 0.4734.
- Unbiased on the answers: on the three largest dealers' Monday and Tuesday quotes it predicts 31.42% sold, against 31.17%
  sold; per week +0.2 points (-0.1 to +0.5), as with the day's shift alone.
- In a closed-loop replay of the same weeks (`scratch/dealer_sim.py`, dealers answer by a known truth: the week's
  hindsight day levels with its price war, the dealer offsets, the morning cuts and the trust count), +26 a week (11 to
  41) with the hindsight offsets and +12 (-3 to 27) with drawn ones; +2 and +4 on the three largest dealers' Monday and
  Tuesday quotes. Sampling a price from the dealer's posterior while it is unsure costs 42 to 54 a week. A wrong start,
  the three largest dealers taken 5% dearer, loses 5 of their 78 Monday and Tuesday orders, 0.8 of their trust counts
  by Friday and 11 to 13 euros.
- The price war goes to the day's shift, not to the dealers: the threshold error on the day after the war is 0.000 with
  or without the offsets.

```bash
PYTHONPATH=. uv run python scratch/dealer_rows.py steep-notes-offers-8           # one row per quote, with the trust count at the quote
PYTHONPATH=. uv run --with numpy python scratch/dealer_filter.py 0.01,0.015 0.02  # log loss by prior sd and drift, tune and held-out weeks
PYTHONPATH=. uv run --with numpy python scratch/dealer_truth.py                   # how far dealers differ, and the morning cut
PYTHONPATH=. uv run --with numpy python scratch/dealer_sim.py                     # euros in the closed-loop replay
```

## Private addresses and trade-ins

The desk declines requests with a private address (11% of requests) and with two cars (2%). No curve
had answers for them, so two batches of weeks quoted them a random multiple of the list price and
kept the dealer requests on the reference (`learn-kinds`, `learn-kinds-2`, seeds `kinds-001` to
`kinds-020`). The second batch, 20 weeks, with private pickups opening at 1.2 x the typical fee and
trade-ins at 1.4 x:

| Kind | Won a week | Fees paid over typical | Booked within an hour | Late | Margin an order |
| --- | --- | --- | --- | --- | --- |
| dealer sites | 234.6 | 1.07 | 77.6% | 4.2% | +42.7 |
| private pickup | 26.1 | 1.57 | 71.4% | 9.2% | -8.3 |
| private delivery | 9.9 | 1.15 | 65.3% | 9.5% | +14.6 |
| trade-in | 8.0 | 1.84 | 58.1% | 25.6% | -7.9 |

- Dealers buy them about as dealer requests: 82% of private requests under 1.3 x list, 45% at 1.4 to
  1.5 x, 20% at 1.6 to 1.8 x. A trade-in's list price is 1.63 x its typical fee, and 79% are bought at
  1.2 to 1.3 x list.
- Drivers charge for them. At the reference's 1.0 x opening (first batch) a private pickup still paid
  1.35 x and a trade-in 1.6 x. A late private pickup is mostly a missed slot that the dealer rebooks
  for the next business day.
- A trade-in's new car is due in the customer's slot, not by the order's deadline. Posted without a
  window for that stop, 46% were late; with it, 26%: half of those had no driver before the slot.
- Only private deliveries pay by the order, so they got policy variants (`kinds`), priced by the curve
  at their own cost: `delivery-1.3` is -139 (-464 to 216) on tune and -8 (-353 to 374) on holdout,
  `delivery-1.4` +268 (5 to 522) and -93 (-368 to 215). They win 7 to 8 such orders a week at about
  36 to 40 an order, and the dealer orders give that back: the total stays at 275 and 253. Not kept.
- With the dealer curve and a cost of 1.5 x or 1.7 x for every private request (`private-1.5`,
  `private-1.7`): -112 and -232 on tune.
- Two won orders that run out and back between two places could go as one gig. There are 20 such
  pairs a week, but only 2.1 where the first still has no driver when the second is won
  (`scratch/pairs_count.py`, 60 weeks of the reference); the others would need the desk to hold
  postings for hours. Not built.

```bash
PYTHONPATH=. uv run python scratch/kinds_report.py --variant learn-kinds-2 --seeds kinds-001,...   # answers, fees and margin by kind
PYTHONPATH=. uv run python scratch/kinds_fit.py --seeds kinds-001,...                             # what the curve is off by for each kind
```

## Short time and the menu

Late orders are the ones with little time to find a driver. Under the reference, 13% of the orders
won with 5 to 6 hours between the first possible pickup and the last one that is on time are late
(14 orders a week), 7.6% of those with 6 to 8 hours (34 a week) and 3% of the rest. `same_day`
orders are 135 a week and 5.6% late, `next_day` 3.3%, `within_3_days` 0.8%
(`scratch/slack_report.py`, 40 fresh weeks). Two ways to win fewer of them, against
`steep-notes-offers-8`:

| Variant | Idea | Tune | Holdout | Fresh, 40 | Late orders a week | Lowest week on time |
| --- | --- | --- | --- | --- | --- | --- |
| reference | 5 hours at least | | | | 11.3, 12.6, 11.2 | 93.8%, 92.7%, 92.0% |
| `slack-6` | 6 hours at least | -274 (-680 to 89) | -190 (-860 to 396) | -100 (-339 to 150) | 8.3, 10.3, 8.8 | 95.0%, 92.8%, 91.6% |
| `slack-7` | 7 hours at least | -561 (-965 to -156) | -165 (-909 to 556) | -287 (-564 to 1) | 7.6, 7.5, 8.1 | 94.9%, 94.5%, 92.2% |
| `slack-8` | 8 hours at least | -745 (-1,679 to 167) | -732 (-1,638 to 167) | not played | 7.5, 7.6 | 95.3%, 94.0% |
| `same-day-5`, `same-day-10` | `same_day` quoted 5% or 10% over the slower options | -195 (-856 to 496) and -631 (-1,080 to -184) | not played | not played | 8.5 and 8.1 | 92.4% and 94.8% |

Neither is kept. More time lifts the mean on-time share by a point and costs 100 to 400 a week,
because those orders still earn about 34 each after their refunds. It does not lift the lowest
week on the fresh seeds, so it is no insurance for the 90% rule either: the lowest weeks are the
ones with few drivers, not the ones with many short orders. A dearer `same_day` loses the order
to the competitor more often than it moves the dealer to `next_day` (264 and 256 orders a week
against 275).

## The backlog surcharge and the gate

The reference adds 0.04 x the typical fee to an order's cost for each won car without a driver, and
quotes nothing while 15 wait. Over its weeks the surcharge averages 0.20, so orders are priced as if
they cost 1.5 x. Three in five of the cars it counts are not due for over a day. The variants below
lower the surcharge (`step-2`), count only the cars to collect within 24 hours (`backlog_hours`),
widen the gate, or make the cost follow the hours to find a driver (`cost_hours`: 1.55 x under 6
hours down to 1.15 x from 30). Mean margin a week against `steep-notes-offers-8`:

| Variant | Tune | Holdout | Fresh 1 to 40 | Orders, late a week (tune) | Lowest week on time |
| --- | --- | --- | --- | --- | --- |
| `step-2` | +321 (-143 to 765) | +132 (-515 to 718) | -99 (-409 to 191) | 306, 12.6 | 94.0%, 91.7%, 90.5% |
| `step-2-gate-25` | +798 (162 to 1,507) | +350 (-382 to 984) | +601 (347 to 848) | 315, 14.8 | 92.8%, 90.6%, 88.8% not ranked |
| `due-24` | +108 (-302 to 558) | -214 (-749 to 257) | not played | 308, 12.2 | 93.0%, 90.8% |
| `due-24-gate-20` | +671 (104 to 1,191) | +273 (-154 to 683) | +273 (-104 to 620) | 318, 13.4 | 91.9%, 91.4%, 90.4% |
| `due-24-gate-25` | +907 (250 to 1,476) | +460 (-122 to 1,125) | +690 (341 to 1,014) | 323, 13.9 | 91.4%, 91.5%, 90.7% |
| `hours` | +180 (-264 to 556) | not played | not played | 301, 11.5 | 93.7% |
| `hours-step-2-gate-25` | +734 (333 to 1,094) | +288 (-633 to 1,079) | not played | 344, 15.8 | 92.0%, 89.5% not ranked |
| `hours-due-24-gate-25` | +479 (-98 to 1,096) | not played | not played | 349, 17.4 | 90.2% |

They win 30 to 70 orders a week more and earn 300 to 900 more on average, and every one that was
played beyond the tune seeds ends a week near or under the 90% rule. None is kept. On 20 further seeds (`fresh-042` to
`fresh-061`) `due-24-gate-20` left three weeks unranked (89.0%, 89.1%, 89.7%) for +137.

- The weeks under 92% on the tune and holdout seeds all had 733 drivers or fewer, so
  `due-24-gate-25-tight-750` keeps the reference in a week with under 750 drivers. It is +489, +643
  and +457 on the tune, holdout and 40 fresh seeds with a lowest week of 91.7%, and on the 20
  further seeds +344 (71 to 625) with one week of 800 drivers at 89.5%, not ranked. The driver
  count does not mark the hard weeks well enough.
- That week shows what the gate is for. The reference declines 132 of its requests for backlog and
  still has 21 late orders (92.7%); with a gate of 25 it declines 18 and has 34 late.
- `hours-due-24-gate-25-premium` was not played: the variant it builds on fell to 90.2% on tune.

**The first look at this**, on 104 weeks, found every week ranked and the lowest at 90.1%; the larger
sample is in the next section.

## How close the reference is to the 90% rule

A week under 90% on time is not ranked. The reference's lowest weeks are the worlds with a short
driver list, so it was played on every world with under 720 drivers among 700 scanned seeds
(`scratch/thin_seeds.py`): 197 thin worlds, and 56 others from the seed lists.

| On time | Under 720 drivers, 197 weeks | 720 drivers or more, 56 weeks |
| --- | --- | --- |
| under 90%, not ranked | 3 (1.5%) | 0 |
| 90 to 91% | 8 | 0 |
| 91 to 92% | 16 | 0 |
| 92 to 93% | 19 | 5 |
| 93% and up | 151 | 51 |

- Thin worlds are 27% of the scanned seeds: 16% have under 680 drivers and 5% under 650. By driver
  count, 1 of 37 weeks with under 650 is not ranked, 2 of 79 with 650 to 679, and 0 of 81 with 680
  to 719.
- The three: `fresh-252` at 83.2% (113 orders), `fresh-410` at 89.5% (238) and `fresh-607` at 89.6%
  (144). Two are worlds where the desk wins 13% and 17% of its quotes, not 30%: a thin world's 15 to
  19 late orders then stand against half the usual orders. Of 8 thin weeks with under 180 orders, 2
  are not ranked.
- The weeks under 91% have as many drivers as the others (659 against 675). They have 21 late
  orders against 13, and 84 requests declined for backlog against 46.
- The late orders have no single source there. Pickups with under 5 drivers notified are 11% of the
  orders and 4 of the 21 late; premium cars are 12 orders a week and 17% late; orders with under 6
  hours to find a driver are 14 a week and 15% late.
- A thin world earns 10,128 a week against 10,790 for the others, at 94.4% on time against 95.7%.

**Rules for the thin worlds**, on the same 197 weeks, each only in a week with under 720 drivers
(`tight_drivers`, `when_tight`). `scratch/thin_report.py` prints the table.

| Variant | Margin against the reference | Orders, late a week | On time | Not ranked | 90 to 91% | 91 to 92% | Lowest |
| --- | --- | --- | --- | --- | --- | --- | --- |
| reference | 10,128 | 248, 13.6 | 94.4% | 3 | 8 | 16 | 83.2% |
| `thin-cost-1.4`: cost 1.4 in the quote | -226 (-364 to -87) | 223, 11.3 | 94.9% | 1 | 4 | 12 | 87.0% |
| `thin-gate-10`: quotes stop at 10 cars without a driver | -733 (-845 to -620) | 234, 11.6 | 94.9% | 2 | 1 | 7 | 86.1% |
| `thin-cost-1.4-gate-10`: both | -829 (-956 to -698) | 214, 10.1 | 95.2% | 3 | 2 | 7 | 83.7% |

- The dearer quote is the only one that pays for itself at all: +0.43 points on time (0.22 to 0.64),
  11 weeks under 91% become 5. `fresh-252` stays not ranked under every rule.
- A tighter gate wins fewer orders and loses nearly as many to lateness, so the share hardly moves
  where it matters, and it costs three times as much.
- The gain is under 680 drivers: there the dearer quote costs 100 a week and takes the weeks under
  91% from 10 to 5 and the weeks not ranked from 3 to 1, in 116 weeks. At 680 to 719 drivers it costs
  408 a week and there is one such week to remove. `thin-680-cost-1.4` applies it under 680 only.
  That limit was read off these weeks, so it has a check of its own below.

**A check on new worlds, and premium cars.** 72 more worlds with under 680 drivers (seeds 702 to 1201), which no rule was
chosen on, and the two rules for premium cars: a premium car may go only to an experienced driver, 12 of them are won a
week and 17% are late.

| Variant, in weeks with under 720 drivers | 197 worlds: margin, not ranked, under 92% | 72 new worlds: margin, not ranked, under 92% |
| --- | --- | --- |
| reference | 10,128, 3, 27 | 1 (`fresh-1123`, 88.0%), 15 |
| `thin-680-cost-1.4` | | -50, 2 |
| `thin-premium-0.4`: a premium car costs 0.4 more | +139 (25 to 255), 1 | +121 (-78 to 330), 1 |
| `thin-premium-0.4-slack-6`: and an option needs 6 hours of slack | +32 (-89 to 150), 1, 5 | +78 (-110 to 269), 1, 3 |

- The dearer quote under 680 drivers did not hold: 2 weeks not ranked against the reference's 1.
- `thin-premium-0.4-slack-6` is the best rule for thin worlds. Over all 269 thin weeks against the reference: not
  ranked 4 to 2, under 91% 17 to 5, under 92% 42 to 8, on time 94.4% to 95.4%, and no loss of margin. No rule rescues
  `fresh-252` or `fresh-1123`.
- The premium cost in every week (`premium-0.4`) made +146 (11 to 298) over 80 weeks of the seed lists, and then -72
  (-264 to 118) on 56 new worlds with 720 drivers or more, where it put `fresh-089` (764 drivers) at 87.9% against the
  reference's 90.9%. It is not kept outside thin weeks.
- In those 56 worlds the reference itself has one week that is not ranked: `fresh-122`, 724 drivers, 89.7%. The risk
  does not end at 720 drivers.

## Slow cars and the backlog

The gate of 15 keeps the desk from winning cars it cannot staff, and it also refuses good requests.
[`scratch/gate_report.py`](scratch/gate_report.py) reads this from 327 saved weeks of the reference
(58 worlds with 720 drivers or more, 269 with fewer).

| Requests declined for backlog a week | Mean | Median | 9 in 10 weeks under | Highest | Weeks with none | Weeks with 100 or more |
| --- | --- | --- | --- | --- | --- | --- |
| 720 drivers or more | 23.4 | 6.5 | 89 | 184 | 41% | 9% |
| under 720 drivers | 46.5 | 28 | 125 | 289 | 23% | 16% |

- The declined requests are easy ones: 43 hours to find a driver on average, 14 to 16% with under 8
  hours. The curve expects 14.5 euros from one (13.4 in a thin world) against 12.9 to 13.8 from the
  requests the desk quotes. That is about 300 a week forgone, and 580 in a thin world, before the late
  orders they would add.
- The gate does protect something: orders won with 10 to 14 cars waiting are 5.7% late (7.0% in a
  thin world) against 3.5% (4.7%) with 0 to 4.
- Of the cars that fill the gate, 53% are not due for over a day, 27% have waited over 12 hours, 22%
  have a pickup with under 10 drivers notified, 27 to 36% drive over 4 hours, 23 to 27% were dropped
  by a driver before, 11 to 14% are premium cars, and 31 to 39% end late.

**What makes a won car wait** (252 one-car orders a week):

| By | Group | Booked within an hour | Median wait | Late |
| --- | --- | --- | --- | --- |
| Drivers notified of the pickup | 100 or more | 80% | 2 min | 3.0% |
| | 10 to 39 | 70% | 12 min | 6.8% |
| | none | 64% | 21 min | 10.5% |
| Hours from the win to the last pickup minute | under 6 | 59% | | 18.7% |
| | over 24 | | | 3.4% |
| Drive | over 6.7 hours, 8 orders a week | 36% | 429 min | 18.3% |
| Car | premium, 12.7 a week | 50% | 61 min | 16.5% |
| | other | 76% | 5 min | 4.6% |
| Day won | Friday | 57% | 32 min | 8.5% |
| | Monday | 81% | 3 min | 3.4% |

Supply and time decide it together: under 10 drivers and under 8 hours is 21.8% late, 40 drivers or
more and under 8 hours 8.3%, 40 or more and over 24 hours 2.3%. The hour of the day matters little.
On a Friday it is the deadline that bites: an order that must be collected that Friday with under 6
hours is 24% late against 14% on Monday to Wednesday, and one that arrives on Friday for next week
is 2.8% late.

[`slow.py`](spreadlab/slow.py) turns this into the chance that a request's order ends late, from
what the desk knows at the quote: the hours to find a driver, the drivers notified, a premium car,
the drive beyond 4 hours, Friday, a note and the length of the driver list
([`scratch/slow_fit.py`](scratch/slow_fit.py), a logistic fit over 94,000 won orders). On the weeks
left out of the fit the orders it puts at 2 to 3% are 2.2% late, at 8 to 12% 10.6%, and at 12 to
20% 18.2%. Half the orders are under 3% and one in eight is over 10%.

**A price in place of the refusals.** With `slow_step`, each won car without a driver adds that
much times the new request's late chance to the cost in its quote, in place of the flat
`backlog_step`: a waiting car makes a risky request dearer and leaves a safe one alone, so the gate
can be wider. `slow-step-gate-25` is the reference with `slow_step` 0.8, no `backlog_step` and the
gate at 25. Against the reference on the same seeds, euros a week
([`scratch/thin_report.py`](scratch/thin_report.py)):

| Seeds | Margin | Orders, late a week | Weeks under 90% (reference) | Lowest week | Declined for backlog (reference) |
| --- | --- | --- | --- | --- | --- |
| first 10 tune seeds | +510 (28 to 1,061) | 304, 10.2 | 0 (0) | 94.7% | 8.6 (34.1) |
| 10 holdout seeds and `fresh-001` to `fresh-020` | +674 (317 to 1,054) | 283, 10.7 | 0 (0) | 93.0% | 4.3 |
| 96 worlds not chosen by driver count | +657 (455 to 864) | 301, 11.7 | 0 (1) | 90.9% | 5.4 (28.7) |
| 38 thin worlds, the reference's lowest among them | +987 (588 to 1,393) | 280, 13.5 | 1 (5) | 86.4% | 6.0 (60.5) |

The week at 90.9% (`fresh-053`) had 9 of its 20 Friday orders late, which is what the `"friday"`
late model (`slow_model`) adds terms for. Variants on this base, on the first 10 tune seeds only:

| Variant | What differs from `slow-step-gate-25` | Margin against the reference | Orders, late | Lowest week |
| --- | --- | --- | --- | --- |
| `slow-step-gate-40` | the gate at 40 | +687 (76 to 1,423) | 307, 10.5 | 94.7% |
| `slow-step-gate-25-kinds` | quotes private pickups, private deliveries and trade-ins (`kinds`) | +1,171 (674 to 1,665) | 316, 10.4 | 95.5% |
| `slow-step-gate-25-late-150` | `cost` 1.2 and `late_cost` 150: 150 euros times the late chance in every quote | +874 (436 to 1,367) | 310, 8.9 | 94.9% |
| `slow-step-gate-25-friday-late-150` | the same with the Friday late model | +905 (368 to 1,537) | 312, 8.5 | 94.9% |

The same on 40 seeds (10 tune, 10 holdout, `fresh-001` to `fresh-020`), where the reference makes
10,445 with 259 orders and 11.5 late. No week of any row is under 91%.

| Variant | Margin against the reference | Orders, late | Lowest week |
| --- | --- | --- | --- |
| `notes-limits` | +244 (-25 to 498) | 263, 9.6 | 92.2% |
| `slow-step-gate-25` | +633 (339 to 941) | 288, 10.6 | 93.0% |
| `slow-step-gate-40` | +740 (415 to 1,077) | 290, 10.7 | 93.0% |
| `slow-step-gate-25-friday-late-150` | +1,063 (772 to 1,388) | 298, 8.9 | 93.0% |
| `slow-step-gate-25-kinds` | +1,244 (955 to 1,531) | 300, 10.6 | 93.6% |
| `slow-step-gate-25-kinds-limits` | +1,211 (856 to 1,544) | 300, 10.6 | 93.5% |
| `slow-friday-late-150-kinds-limits`: the late cost, the Friday model, the kinds and the note limits | +1,479 (1,135 to 1,828) | 306, 9.8 | 92.3% |

- On the reference's 10 lowest worlds `slow-step-gate-25-friday-late-150` makes +2,854 (1,942 to
  3,929) with no week under 90% against 5, and a lowest week of 90.7%.
- The kinds were a wash on the reference, because the gate handed their wins back; on the wider
  gate they are not.
- **Note limits** (`note_limits`, [`notes.limits`](spreadlab/notes.py)): the note's own deadline and
  site hours count at the quote and in the posting. Against the revealed orders the reader finds 457
  of 457 deadlines, 347 of 347 delivery hours and 609 of 610 pickup hours on 10,374 notes, and 57 of
  57, 45 of 45 and 72 of 73 on 1,291 notes it was not written on. On the 40 seeds visits to a
  closed site go from 1.7 a week to none and waits from 0.9 to 0.2, for +244 (-25 to 498) on the
  reference. On top of the kinds the limits add nothing: -34 (-218 to 163)
  ([`scratch/notes_effect.py`](scratch/notes_effect.py)). With the kinds, 18 of the first 80 weeks
  failed: a private address has its own slot, and the desk posted a delivery window that ended
  before it. That is fixed, and the 18 weeks are in the numbers above.
- **`opt`** ([`optquote.py`](spreadlab/optquote.py)): the quote as one optimisation, with its own
  fits of an order's cost and late chance and a belief about the world's price level. On the tune
  seeds `opt-mu-0.2` makes +1,016 (623 to 1,416) with a lowest week of 92.4%, and
  `opt-mu-0.3-lambda-100` +988 (527 to 1,556) with 379 orders, 12.6 late and a lowest week of 94.5%.
  Its weights were fitted on saved weeks of 9 of those 10 seeds. On the 30 holdout and fresh seeds
  `opt-mu-0.3-lambda-100` makes +997 (619 to 1,373) with 16.2 late orders a week and one week at
  89.8%, and `opt-mu-0.2` +724 with two weeks under 90%. Its gate declines 51 requests a week
  against 4 for `slow-step-gate-25`: its price hardly moves with the backlog, so the gate sets its
  volume, and its late chance is too low for orders won with 16 or more cars waiting, which the
  weeks it was fitted on do not have. Not a candidate as built.
- **Offers to drivers who live at the destination** (`home_offers`) lose 86 to 152 a week on 40
  seeds at fees of 0.8 to 1.0, with one week at 89.6%. Not kept.
- `rescue-*` and `late-225-cost-1.19` switch a late cost on from a point of the week; they are there
  for a comparison and are not candidates.
- **Snow** (`snow_odds`, `snow_fee`). A `forecast` event names the places and hours of snow, from
  midnight the day before. An order whose pickup or delivery place has snow forecast at the quote, for
  hours between its first pickup minute and its deadline, is late about twice as often as `slow.py`
  says: 10.4% against 6.1% over the reference's 401 weeks (0.64 more log odds), 8.0% against 3.9% over
  167 weeks of `slow-step-gate-25` (0.79). That is 12 to 16 orders and 0.5 to 0.8 late orders a week.
  Orders whose snow was forecast only after the quote are not late more often. The late ones are slow to
  book: 68% were booked over an hour after the win and 60% only once the snow had started
  ([`scratch/snow_report.py`](scratch/snow_report.py)). `slow-friday-late-150-kinds-limits-snow` adds
  0.7 to the late chance's log odds there, so `late_cost` and `slow_step` price it; `-snow-fee-1.2` also
  pays 1.2 x the usual fee schedule for gigs whose order has snow forecast before its deadline.

**The default is `slow-friday-late-150-kinds-limits`** since Saturday 10:47 UTC. The rule for it: the highest mean margin
among the variants with at most 3 of 60 weeks under 90% on time on a set of seeds that nothing had
played, confirmed by at most 3 of 60 on a second such set. Six variants played the first set
(`fresh-1301` to `fresh-1360`); the best of them and the reference played the second (`fresh-1401`
to `fresh-1460`).

| Seeds | Variant | Margin against the reference | The same, a week under 90% as no margin | Orders, late | Weeks under 90% | Lowest week |
| --- | --- | --- | --- | --- | --- | --- |
| First 60 | reference | 11,093 | | 265, 12.1 | 1 | 87.7% |
| | `slow-step-gate-25` | +691 (472 to 943) | +475 (-7 to 853) | 296, 11.7 | 2 | 89.2% |
| | `slow-step-gate-25-kinds` | +1,171 (896 to 1,459) | +1,352 (941 to 1,873) | 307, 13.4 | 0 | 90.7% |
| | `search-16-kinds` | +1,301 (1,022 to 1,614) | +1,482 (1,050 to 2,030) | 310, 11.8 | 0 | 90.1% |
| | `slow-friday-late-150-kinds` | +1,354 (1,104 to 1,648) | +1,534 (1,136 to 2,064) | 314, 12.2 | 0 | 90.9% |
| | `slow-friday-late-150-kinds-limits` | +1,601 (1,341 to 1,894) | +1,782 (1,376 to 2,331) | 316, 11.2 | 0 | 90.5% |
| Second 60 | reference | 10,688 | | 259, 12.1 | 1 | 89.4% |
| | `slow-friday-late-150-kinds-limits` | +1,370 (1,118 to 1,636) | +1,463 (1,141 to 1,826) | 309, 11.2 | 0 | 91.5% |
| 38 thin worlds | reference | 10,153 | | 246, 16.0 | 5 | 83.2% |
| | `slow-friday-late-150-kinds-limits` | +1,830 (1,398 to 2,268) | +2,679 (1,783 to 3,765) | 292, 12.2 | 0 | 90.2% |

- The thin worlds are 38 worlds, 35 of them with under 720 drivers and the reference's lowest
  among them; they are reported beside the rule and are not part of it.
- On the first set the note limits add +247 (80 to 408) to `slow-friday-late-150-kinds`; on the 40
  seeds above they added nothing to the kinds.
- [`replay.py`](spreadlab/replay.py) with this default: `fresh-001` at 20 times the final's speed
  gives 1,030 of 1,030 quotes and 308 of 308 gigs equal to the recording, and with a crash at
  Tue 12:40 no request is missed while the desk runs and no car is in two live gigs.
- `steep-notes-offers-8` stays the reference that new ideas are compared with (`REFERENCE` in
  `variants.py`). `python -m spreadlab.live final --variant steep-notes-offers-8` plays it.

[`scratch/search.py`](scratch/search.py)
searches the parameters above together on 30 tune seeds; [`scratch/search_check.py`](scratch/search_check.py)
plays its best trials on other seeds. After 25 trials, 11 of them played in full, its best point is
of the same family (`search-16`: `slow_step` 0.8, the gate at 40, `cost` 1.22, a small late cost):
+1,192 with a lowest week of 93.6%. A late cost alone on the reference's backlog rules is worth +72.

## Out-and-back pairs (off by default, not played yet)

A one-way fee pays for the driver's trip home. A car that goes back the same way removes that trip, so one driver
delivers a won car and drives another back in one gig ([`pairs.py`](spreadlab/pairs.py), `PairPolicy`, variants
`slow-friday-late-150-kinds-limits-pairs-<fee>` and `...-pairs-<fee>-return-0.75`). The evidence is in
[`scratch/strategy/`](scratch/strategy/README.md): the world prices a trade-in, one car out and one back, at 26.3 cents a
drive minute against 47.2 for a one-car dealer request. And 296 of 887 one-car dealer requests a week are followed by a
return in time to drive both. The desk never paired them, because its cars book in six minutes.

- **Hold.** A won one-car dealer order with 16 hours or more to its last pickup, on a lane with 8 or more return requests
  a week ([`returns.json`](spreadlab/returns.json), [`scratch/pairs_returns.py`](scratch/pairs_returns.py), over 1,520 scans),
  waits up to 4 hours unposted. It is never held past 18:00 or within 10 hours of its last pickup. Held cars do not count in the
  backlog. On those lanes 40% to 93% of requests get a return within 4 hours, against 3% on lanes with under one a week.
- **The return's quote.** A request that can run back with a held car, both ends within 30 km of the held car's other
  ends, is quoted at a cost of 0.75 x its typical fee in place of 1.2 x (`pair_cost`, the `-return-0.75` variants only).
- **One gig.** When the return is won, both cars go in one gig in the order that leaves a driver the most time. It must
  stay on time by the road minutes, the stops' windows and the sites' hours for a driver who books it 10 hours from now,
  within the 12 hours of driving of a gig with more than one car. It opens at 0.6, 0.7 or 0.8 x the two typical fees and
  rises a tenth of them an hour to 1.0 x.
- **Two gigs again.** An open pair gig goes back to two gigs, each car alone at its own fee, 6 hours before its latest
  start, or when it expires, gets a deadline warning or its order changes. The same happens when a cancellation leaves one
  car in it. Direct offers go to cars alone only.

In a dry run on 8 recorded weeks, with fake drivers who book every single-car gig at once and 80% of pair gigs after
half an hour, the desk held 75 cars a week, paired 59 orders (30 gigs) and posted 41 held cars alone. The test plan:
the fee at 0.6, 0.7 and 0.8 on 10 tune seeds, then the return's quote on 30, then the two unseen sets.

```bash
uv run python -m spreadlab.sweep --variants slow-friday-late-150-kinds-limits,slow-friday-late-150-kinds-limits-pairs-0.6,slow-friday-late-150-kinds-limits-pairs-0.7,slow-friday-late-150-kinds-limits-pairs-0.8 --list tune --count 10
PYTHONPATH=. uv run python scratch/pairs_report.py --variants slow-friday-late-150-kinds-limits-pairs-0.6,slow-friday-late-150-kinds-limits-pairs-0.7,slow-friday-late-150-kinds-limits-pairs-0.8 --list tune --count 10
```

`pairs_report.py` prints the plan's checks: pair gigs booked within 1 and 2 hours, the fee paid, pair orders late, held
cars without a return against the same orders in the base variant, return quotes won, and the margin with its interval.
The live desk does not take `PairPolicy`: `live final --variant ...-pairs-...` stops at once with unknown parameters. A gig
with two orders is a new case for its restart logic, and must pass the replays of `replay.py` before it can play live.

## The final

[`live.py`](spreadlab/live.py) plays the final, or a test final, with the default variant (`VARIANT`) from the live stream.
Run it on the runner in Helsinki, from a clean checkout of `origin/main`, so no experiment in a working tree plays:

```bash
git worktree add ../final origin/main && cd ../final/spread && uv sync   # once; later: git fetch origin && git checkout --detach origin/main
export SPREAD_KEY=<team key>
while true; do uv run python -m spreadlab.live final; sleep 3; done      # in tmux; waits for the next final or test final
uv run python -m spreadlab.live report <world id>                        # afterwards: the evidence for the jury
```

Start it at any time before the start. The organisers set a test final 15 minutes before it begins (14:00 and
20:00 on Saturday), and the final at 07:30. The desk acts only on the world that `GET /v1/final` names. When it
stops, by Ctrl-C, a crash or a reboot, the world goes on, and the same command goes on from `data/live/<world id>/`.
`--variant <name>` plays another variant from `variants.py`; the default is `slow-friday-late-150-kinds-limits`. A second desk on
the same world and machine stops at once, so two terminals cannot both post the cars.

In the final the clock moves by itself, `advance` is closed, and a request gives 4.5 real seconds. What the live
desk adds to the policy, which is the same class as in the sweeps:

- **Quotes first, and a fallback.** It answers each event as it comes and sends the quotes ahead of the other
  actions. A guard thread, with its own connection, quotes 1.9 x the typical fee (no `same_day`, no trade-in or private
  address; a decline while 15 won cars have no driver) for a request that the desk has sent no quote for when a third
  of its time is left. A policy quote that is still in time replaces it, because the dealer takes the last quote. A quote that would arrive after the deadline is not sent, and its answer does not count in the day's correction.
- **Restarts.** The books go to disk every second. A desk that starts again reads the events it missed and learns
  from them without acting: the day's answers, the dealers' orders on time, who used the app, failed visits. It then
  takes the gigs and orders from the world's snapshot and acts on the world as it is: it posts the cars that have no
  gig, steepens the fees of orders that got a deadline warning, and quotes the open requests. A car never gets a
  second gig, also when the desk died after the world took its post and before it read the answer. Without books,
  for example on a new machine, it learns the same from the world's whole history.
- **Evidence.** `log.jsonl` holds every event with its delay, every action with its answer and the seconds left
  for a quote, each quote's decision with the day's correction, each note read at a win, fallbacks, joins and the
  score each world hour. `report` sums it up; `end.json` holds the final score and the reveal.

Tested offline with [`replay.py`](spreadlab/replay.py), which plays a recorded week of the reference on the final's
clock as a stand-in for Bahn's server, without the team key:

```bash
uv run python -m spreadlab.replay --seed fresh-001 --speed 10                     # ten times the final's speed
uv run python -m spreadlab.replay --seed fresh-002 --crash-at 2160 --down 20      # the desk dies on Tuesday 12:00 inside a batch of actions
uv run python -m spreadlab.replay --seed fresh-003 --start 4320                   # joins on Thursday from the world's history alone
uv run python -m spreadlab.replay --seed fresh-004 --speed 2 --slow 0.05          # the policy stalls on 5% of requests
```

What the replays showed, on the reference's recorded weeks:

| Replay | Requests | Policy quotes | Fallback | Missed while it ran | Unquoted while down | Same as the recording |
| --- | --- | --- | --- | --- | --- | --- |
| `fresh-001`, ten times the final's speed | 1,030 | 1,030 | 0 | 0 | - | every quote, all 285 gigs, all 1,283 offers |
| `fresh-003`, joins on Thursday from the history alone | 386 | 386 | 0 | 0 | - | every quote, all 243 gigs |
| `fresh-002`, dies on Tuesday 12:00, down 20 s | 1,039 | 1,025 | 0 | 0 | 14 | all 325 gigs |
| `fresh-005`, from Thursday, dies on Thursday 11:00 | 386 | 369 | 0 | 0 | 17 | no car in two gigs |
| `fresh-004`, the policy stalls 6 s on 5% of requests | 1,035 | 781 | 254 | 0 | - | all 234 gigs |

So the day's corrections, the note reader and the direct offers run on the live stream as in the sweeps: at ten
times the speed, 0.45 s for a request, every quote is the recorded one to the cent, with at least 0.43 s left. After
a crash the quotes differ from the recording on purpose: the desk does not learn from the answers to requests that
nobody quoted while it was down, and the recording quoted them. The fallback column counts the requests whose last
quote was the fallback, because the policy's own quote was too late to replace it. Deciding takes 0.4 ms for a request and 2 ms for a win; the books are 0.7 MB and
take 11 ms to save at the end of the week.

The replays found five faults, each fixed with a test. After a restart the guard sent its fallback over quotes
that the desk had sent before it stopped. The guard stopped covering a request once the desk started on it, so a
hold-up before the quote went out left the request without one. A join redid changes of plan that the desk had
already handled, and learned the day's prices from requests that nobody had quoted. And a car whose visit failed
while the desk was down was not posted again when the world still listed it on the driver's gig.

A rehearsal on a practice world moves its clock like the final's from a second process, so the desk meets Bahn's
real stream and limits. `--start 4320` begins on Thursday 00:00, as a test final does; `--kill-at` kills the desk at a
world minute and starts it again after `--down` seconds. It plays practice worlds only, never a ranking run.

```bash
uv run python -m spreadlab.live rehearse --seed fresh-041 --start 4320 --kill-at 5000 --down 20   # about 19 minutes
```

On the runner in Helsinki, with the desk killed at Thursday 11:20 and started again 20 s later, it quoted 371 of 386
requests with the policy, missed none while it ran and left 15 unquoted while it was down. It had no errors and no
lost connections, at least 1.16 s left at a quote, and the week was ranked at 97.0% on time. An action took 10 ms
there, 25 ms at the 99th percentile.

### The note watcher (`--watch-notes`, off by default)

[`watch.py`](spreadlab/watch.py) adds a second reader of the dealers' notes beside the desk. It needs
`NVIDIA_API_KEY` in the environment; without it, only the log of new notes and drift runs. `NOTE_MODEL_URL`,
`NOTE_MODEL`, `NOTE_MODEL_KEY` (the name of the variable with the key) and `NOTE_MODEL_RPM` point it at another
OpenAI-compatible endpoint, such as a dedicated container without the free tier's limit; only Lightning on
NVIDIA's endpoint has been measured.

```bash
uv run python -m spreadlab.live final --watch-notes                          # the same desk, with the note watcher
uv run python -m spreadlab.watch review <world id>                           # the notes the model said the rules missed, by fact
uv run python -m spreadlab.watch check "Registration tags are off, bring your own."   # one note: the rules, the model, the fix
```

- **The check.** For each won order with a note, Nemotron 3.5 Lightning gets the note, what the request states
  (pickup window, both sites' hours, the deadline) and what `notes.read` made of it. It answers yes or no: did the rules capture every operational fact in the note? On a no it names each
  missing or wrong fact. A no counts only when the fact it names would change what the desk knows. A no that names
  only "other" goes to the review queue, not as a no: the model puts spare tyres and parked cars there.
- **Safe fixes only.** The desk applies plates, a manual licence and a ready time later than the rules read, never
  earlier. A later ready time must also be a clock time that the rules find in the note, in a sentence that is not
  about the delivery or a closing site: the model calls "the customer collects at 12, the car must be there by
  then" a ready time. Deadlines, opening hours and summer tyres are logged, not acted on.
- **The first post waits, briefly.** A driver often books a gig within a world minute or two of its post, and a
  booked gig cannot be withdrawn. So the car's first post waits for the answer, at most 1.5 s and 5 world minutes;
  then it goes with the rules' reading. A later no withdraws the gig, alone and first, and posts the cars whose gig
  left the app again; when a driver holds the gig, the fix waits for the car's next post, a retry after a failed visit.
- **Never in the way of a quote.** The model runs on a thread of its own, 30 calls a minute at most, with a 6-second
  timeout and retries when the free tier answers 429. A check that has waited 2 minutes is dropped. A call that
  fails leaves the rules' post as it is. The books on disk keep the fixes and the notes still to check, so a desk
  that starts again checks those whose cars no driver holds yet.
- **The review queue.** Every no goes to `review.jsonl` in the world's folder with the note, the rules' reading and
  the model's answer. `report` and the end of the week print it by fact. It is what `notes.py` should learn next:
  in practice weeks, hand it to whoever extends the rules.
- **New notes and drift.** The thread also scores each request's note against the words and digit-masked sentence
  patterns of the archive's 202,579 notes ([`note-vocab.json`](spreadlab/note-vocab.json), built by
  `python -m spreadlab.watch build`). A word that is more than one typo from a known word, or a new sentence, goes
  to the log as `note_new`. It counts the share of the last 200 notes that mention a ready time, a closing time, a
  limit ("by", "ennen"), the delivery, opening hours, plates, a manual car, summer tyres or something new. When a
  share is more than twice the archive's, at 4 standard deviations or more, it prints a line and logs `note_drift`.
  In 60 archive weeks held out from the rest, 11% of notes have a word or sentence pattern that the other weeks lack.

What the rules leave out, by the reveal of every won note with one car in the archive (24,595 notes in 186
weeks, `scratch/llm-notes/verify.py misses`): 16.4% of the readings are incomplete. The note's deadline is missing
on 5.96%, pickup hours or a closing time on 5.91%, delivery hours on 3.33% and summer tyres on 1.18%. Ready times
(6 notes) and manual gearboxes (8) are read wrong almost never, and plates never.

What the check found offline against the reveal ([`verify.py`](scratch/llm-notes/verify.py), the prompt of the
live desk). It ran on 150 won notes drawn at random and on 124 notes of the study's sample: every third, and the 14 that
the rules misread:

| | Random notes | Study sample |
| --- | --- | --- |
| A no on a complete reading, as the model says it | 39% (48 of 124) | 27% (16 of 60) |
| A no on a complete reading, counted as the desk counts it | 4.8% (6 of 124), and 21% more that name only "other" | 8.3% (5 of 60), and 10% more |
| A no on an incomplete reading | 73% (19 of 26) | 65% (41 of 63) |
| Safe fixes made: mend, break | none | 7 (5 ready times, 2 manual gearboxes), 0 |

Most false no's name spare tyres in the boot ("other", or "summer tyres"). Before the checks of the note's own
words, the safe fixes broke three readings on these notes. They added plates to a note about spare tyres, took
"the customer collects at 12" for a ready time, and read "huomenna" as the day after tomorrow. A call took 0.4 s
at the median and 1.6 s at the 95th percentile. On this day, though, the free key, which the team's other projects
also use, refused half of all calls with 429: 552 calls for 273 answers.

On replays of `fresh-003` from Thursday, with every fourth won order given a note in words that the rules miss
(`replay.py --watch-notes --inject 4`), the watcher found every injected fact that got an answer: plates, a
manual gearbox, a later ready time. All 386 requests were still quoted by the policy, with at least 4.47 s left.
Of 19 held first posts, 9 went with the answer and 10 with the rules when it was late, the longest after 1.51 s.
With the watcher on and no model, `fresh-001` at ten times the final's speed matched the recording in every quote
and every gig.

## Rules for policy code

The final is one secret week. A policy may use only what the live system sees at that minute: the
request, the driver list, the map and its own history in the week.

- No seed, world id or request id in policy code.
- The reveal and the catalogue are for analysis and for fitting parameters, not for the policy to read while it plays.
- Tune on `tune`, select on `holdout`. Scan a fresh batch of seeds for the last check.

## What the comparison rests on

- The same seed gives the same requests to every variant, and the same variant replays a week to the
  same score, events and decisions (checked on 6 weeks). One run per week and variant is enough.
- The ledger's rows must add up to the week's score; `CHECK FAILED` means they do not.
- Weeks differ more than variants do: the reference makes -700 to +2,000 euros by seed. Compare
  variants week by week, never by the means of different seeds.

## Files

- [`server.py`](spreadlab/server.py): the practice-only client, the data folder, and which drivers are notified of a pickup.
- [`scan.py`](spreadlab/scan.py), [`catalogue.py`](spreadlab/catalogue.py): the scans, the table of what each week shows, and the seed lists.
- [`policy.py`](spreadlab/policy.py), [`variants.py`](spreadlab/variants.py): the policy on top of the kit's starter desk, and the named variants.
- [`curve.py`](spreadlab/curve.py), [`curve.json`](spreadlab/curve.json), [`curve-day.json`](spreadlab/curve-day.json): the win curve, its best price and its live shift, and the fitted weights.
- [`notes.py`](spreadlab/notes.py): what a dealer's note says about the first posting, and its own deadline and site hours.
- [`slow.py`](spreadlab/slow.py): the chance that an order ends late, from what the desk knows at the quote.
- [`optquote.py`](spreadlab/optquote.py), [`optquote.json`](spreadlab/optquote.json): the quote as one optimisation (`opt`), and its fitted weights.
- [`lanes.json`](spreadlab/lanes.json): the lanes' usual driver fees, for `lane_fee`.
- [`pairs.py`](spreadlab/pairs.py), [`returns.json`](spreadlab/returns.json): out-and-back pairs, and the return requests a week on each lane.
- [`play.py`](spreadlab/play.py), [`sweep.py`](spreadlab/sweep.py), [`report.py`](spreadlab/report.py): play, compare.
- [`ledger.py`](spreadlab/ledger.py): mistakes by variant and situation.
- [`live.py`](spreadlab/live.py), [`replay.py`](spreadlab/replay.py): the final from the live stream, and a recorded week as a stand-in for the server.

## Limits

- All systems on one team key share 8 open practice worlds and one request budget. A sweep uses 7
  worlds and waits when none is free.
- A sweep that is killed leaves its worlds open. `client.worlds()` lists them, and
  `client.world(id).delete()` frees one.
- The ledger does not label the price war, the outage or the flu yet.
