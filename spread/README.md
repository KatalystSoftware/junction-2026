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
- [`notes.py`](spreadlab/notes.py): what a dealer's note says about the first posting.
- [`lanes.json`](spreadlab/lanes.json): the lanes' usual driver fees, for `lane_fee`.
- [`play.py`](spreadlab/play.py), [`sweep.py`](spreadlab/sweep.py), [`report.py`](spreadlab/report.py): play, compare.
- [`ledger.py`](spreadlab/ledger.py): mistakes by variant and situation.

## Limits

- All systems on one team key share 8 open practice worlds and one request budget. A sweep uses 7
  worlds and waits when none is free.
- A sweep that is killed leaves its worlds open. `client.worlds()` lists them, and
  `client.world(id).delete()` frees one.
- The ledger does not label the price war, the outage or the flu yet.
