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

`fee-cap-1.2-drop-cost-1.3` is the reference for new ideas. On 20 seeds that no list holds
(`fresh-001` to `fresh-020`, every week ranked) it makes 9,053 against 5,816 for
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

```bash
uv run python -m spreadlab.sweep --variants explore --seeds explore-001,explore-002  # play random-price weeks
PYTHONPATH=. uv run python scratch/curve_rows.py                                     # one row per quote
PYTHONPATH=. uv run --with scikit-learn python scratch/curve_fit.py --write          # fit, test on unseen weeks, write curve.json
PYTHONPATH=. uv run --with scikit-learn python scratch/curve_live.py                 # what each live correction is worth
```

Random prices lose money on purpose, so `explore` is never a candidate. It is safe only because
practice weeks do not count for the ranking.

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
- [`curve.py`](spreadlab/curve.py), [`curve.json`](spreadlab/curve.json): the win curve, its best price and its live shift, and the fitted weights.
- [`play.py`](spreadlab/play.py), [`sweep.py`](spreadlab/sweep.py), [`report.py`](spreadlab/report.py): play, compare.
- [`ledger.py`](spreadlab/ledger.py): mistakes by variant and situation.

## Limits

- All systems on one team key share 8 open practice worlds and one request budget. A sweep uses 7
  worlds and waits when none is free.
- A sweep that is killed leaves its worlds open. `client.worlds()` lists them, and
  `client.world(id).delete()` frees one.
- The ledger does not label the price war, the outage or the flu yet.
