# A different strategy: offline scripts

One-off analysis of the saved weeks and scans: why the best teams on the level-8 board win about 450
orders a week at €42 an order and 97% on time, where our extra orders earn €9 each and run late once
16 cars wait, and what a desk that puts an order and its return in one gig could gain. None of these
plays a week or needs the team key. The findings and the three ranked proposals are in the "Spread
strategy alternatives" document of the team's Space.

They are scratch: dense, and written to print tables. Each takes its folders as arguments and reads
only the standard library, except `opt_days.py` and `late_fit.py`, which need numpy.

## Run

From `spread/`, with the saved weeks unpacked into the data folder (see the main README):

```bash
S=scratch/strategy; D="${SPREAD_DATA:-data}"; C=/tmp/strategy-cache; PY="python3 -I"

$PY $S/pairs.py $D 120 30 4        # out-and-back pairs in 120 scans: ends within 30 km, a hold of at most 4 hours
$PY $S/pairs.py $D 120 0           # the same on exact reverse lanes, held until a car has 8 hours left
$PY $S/tradein.py $D learn-kinds learn-kinds-2 curve-trade-in slow-step-gate-25-kinds
$PY $S/tradein_fee.py $D learn-kinds learn-kinds-2 curve-trade-in trade-in-1.9 trade-in-2.1 trade-in-2.3 slow-step-gate-25-kinds

# The others read compact pickles of the weeks, one a week, which cache.py writes.
$PY $S/cache.py $D $C steep-notes-offers-8 slow-step-gate-25 slow-step-gate-25-kinds opt-mu-0.3-lambda-100 opt-mu-0.2 \
    curve-fee-0.8 curve-fee-0.9 curve-fee-0.9-cost-1.2 curve-fee-1.0 curve-fee-1.0-cost-1.2 deep-0.9 home-0.8 home-0.9 home-1.0
$PY $S/looks.py $C $D/map.json curve-fee-0.8 curve-fee-0.9 curve-fee-0.9-cost-1.2 deep-0.9
$PY $S/own_return.py $C $D/map.json steep-notes-offers-8
$PY $S/offers_own.py $C $D/map.json steep-notes-offers-8 slow-step-gate-25
$PY $S/fee_slack.py $C curve-fee-0.9-cost-1.2 curve-fee-1.0-cost-1.2
$PY $S/rows.py $C $D/map.json $C/rows.pkl steep-notes-offers-8 slow-step-gate-25 slow-step-gate-25-kinds opt-mu-0.3-lambda-100 opt-mu-0.2
uv run --no-project --with numpy python -I $S/opt_days.py $C/rows.pkl
```

## What each one showed

| Script | Question | Finding |
| --- | --- | --- |
| `pairs.py` | How many one-car dealer requests have a return that one driver can run with them as one gig? | Of 887 a week, 296 are followed by a return to within 30 km while the first car can still wait (175 on the exact reverse lane), a median 1.6 hours later. A desk that wins a lone request with chance 0.30 and the return of a held car with 0.55 holds 15.5 pairs a week on exact lanes with a hold of at most 4 hours, 34.6 within 30 km, and 50.1 within 30 km when it holds until a car has 8 hours left. 7 to 23 of the returns are orders it would not have won. |
| `tradein.py` | What does the world take an out-and-back to cost? | A trade-in's typical fee is 26.3 cents a drive minute, a one-car dealer request's 47.2 (299 and 19,301 played gigs). |
| `tradein_fee.py` | At what fee do drivers book a two-car out-and-back? | 407 trade-in gigs that opened at 1.25 to 1.45 x their typical fee: 82% booked within the hour, 92% within four. 42 at 1.05 x or under: 48% and 81%, all booked, paid 1.10 x. |
| `looks.py` | What is a way home worth to a driver? | In 70 weeks that opened at 0.8 to 0.9 x, drivers who live where the car is going booked 43% of their looks at 0.85 to 0.95 x and 31% under 0.85 x; drivers who live at the pickup 4.8% and 1.4%. |
| `own_return.py` | How often is a won order a way home for a driver who already holds one of our cars bound for its pickup? | 37 of 264 won orders a week, and that driver drives 0.9 of them. |
| `offers_own.py` | Do direct offers reach those drivers? | Drivers who hold one of our cars read half of their offers and accept 0.4 to 1.4%. The pair has to be one gig. |
| `fee_slack.py` | Where does an opening fee of 0.9 x cost on-time share? | On 40 seeds, cars with 16 hours or more to the last pickup were paid 1.07 to 1.08 x against 1.16 to 1.18 x and were late as often; cars with under 16 hours were 1.4 points later. |
| `rows.py`, `opt_days.py` | Where does the `opt` rule earn and lose against `slow-step-gate-25`, and what late chance fits the orders won while cars wait? | On 38 seeds: +213, +178 and +118 euros on orders won Monday to Wednesday, -81 and -94 on Thursday and Friday. At 16 or more waiting cars 5.2 to 6.2% are late, the `friday` weights of `slow.py` say 2.5 to 3.9%, and a fit with three terms for the waiting cars says 6.0 to 9.9% on seeds it was not fitted on. `late_wide.py` replaces that fit. |

## One late chance: the waiting cars and the request's own fields

[`late_wide.py`](late_wide.py) is the chance that an order arrives late, in the shape of `spreadlab/slow.py`: `known(...)` gives
what the desk knows at the quote and `chance(known)` the chance. It has slow.py's 14 terms, three for the won cars without a
driver (those due within 24 hours, those due later, and those due within 24 hours once more for an order with under 12 hours;
in tens, capped at 30), and 17 for fields that slow.py leaves out, which the input audit named: the last pickup minute by the
sites' stated hours, the ready time, the slower options quoted, a charge under 30%, the drivers who live at the delivery and in
the pickup town, the weekday and the hour. It replaces the 17-weight fit of `opt_days.py`.

[`late_fit.py`](late_fit.py) fits it and checks it:

```bash
$PY $S/cache.py $D $C steep-notes-offers-8 $(ls $D/runs | grep -E '^(slow-step|opt-mu|s1-|due-24|step-2|hours-)')
uv run --no-project --with numpy python -I $S/late_fit.py $C $D/map.json steep-notes-offers-8 $(ls $C | grep -E '^(slow-step|opt-mu|s1-|due-24|step-2|hours-)')
```

Over 404,374 one-car dealer orders of 1,356 weeks, 37 variants and 401 seeds, fitted on half of the seeds and read on the
249,757 orders of the other half:

| Chance | AUC | Log loss | At 16 or more waiting cars, in the four families with 1,700 orders or more there: chance, where 4.6 to 6.6% are late |
| --- | --- | --- | --- |
| slow.py's `friday` weights, as played | 0.739 | 0.1578 | 2.5 to 4.2% |
| The same 14 terms with the waiting cars | 0.750 | 0.1560 | 5.4 to 8.9% |
| All of `late_wide.py`'s terms | 0.774 | 0.1514 | 5.7 to 8.9% |

- By family of variants the AUC goes from 0.712 to 0.761 on the `slow-step` weeks, from 0.710 to 0.769 on those with a late cost,
  from 0.725 to 0.775 on the `opt` weeks and from 0.758 to 0.787 on the reference.
- By band of the new chance, the late share is 1.2% where it says 1.2%, 8.1% where it says 9.1%, 24.1% where it says 25.7% and
  38.9% where it says 46.3%. The `friday` weights give the last three bands 6.9%, 15.1% and 26.2%.
- It moves 24.0 orders a week up by 5 points or more (17.2% late, `friday` says 8.3%) and 5.0 down (8.5% late, `friday` says 16.7%).
- The world's `lastPickupAt` is the last pickup minute by the sites' hours for 98.7% of orders.

### The seeds of the fit, and weights without `confirm-30`

[`late-fit-seeds.txt`](late-fit-seeds.txt) lists the 401 seeds whose weeks `WEIGHTS` was fitted on. They are the seeds of the
reference's 401 saved weeks: 40 catalogue seeds, `fresh-001` to `fresh-141` except `fresh-041`, and 221 seeds between
`fresh-147` and `fresh-1191`. A result of a variant that prices with `WEIGHTS` on any of them is in-sample for the late chance.

| Seed set | In the fit | Share of the fitted orders |
| --- | --- | --- |
| [`confirm-30.txt`](confirm-30.txt): the first 10 of the catalogue's holdout list and `fresh-001` to `fresh-020` | 30 of 30 | 18.2% |
| The first 30 of the catalogue's tune list, which `scratch/search.py` plays | 30 of 30 | 46.4% |
| `fresh-1301` to `fresh-1360` and `fresh-1401` to `fresh-1460` | none | |
| `fresh-1901` to `fresh-2020`, and every seed from `fresh-2101` on | none | |

`late_wide.WEIGHTS_WITHOUT_CONFIRM_30` is the same fit over the other 371 seeds (330,894 orders of 1,115 weeks), for a variant
that is screened on `confirm-30`: `chance(known, late_wide.WEIGHTS_WITHOUT_CONFIRM_30)`. `late_fit.py --without $S/confirm-30.txt`
prints it, before the other arguments. On the 73,480 orders of those 30 seeds (4.8% late):

| Chance | AUC | Log loss |
| --- | --- | --- |
| slow.py's `friday` weights, as played | 0.723 | 0.1763 |
| `WEIGHTS`, fitted on every seed | 0.777 | 0.1648 |
| `WEIGHTS_WITHOUT_CONFIRM_30` | 0.773 | 0.1658 |

The two fits differ there by 0.23 points of chance on an average order and by 2.1 at the 99th percentile; the largest
change of a weight is 0.13. What that does to a played week is not measured.

### Wiring

It is not wired into the policy, because a change to `policy.py` makes every sweep play its saved weeks again. A variant needs
one branch in `Policy.slow` for a request with one car, and keeps slow.py for a trade-in:

```python
soon = self.unbooked(24)
late_wide.chance(late_wide.known(request, options, self.notified, at_home, self.drive(request), len(self.roster), soon, self.unbooked() - soon), odds=odds)
```

`at_home` is the count of the driver list's `homePlaceId`, and `odds` the policy's `snow_odds` as today.

## Limits

- No dealer two-car gig exists in the saved weeks. The fee and the booking speed of a pair come from trade-ins, which
  have a private address and a booked hour.
- `pairs.py` takes the dealer to choose the fastest option quoted and checks windows, stated hours, deadlines and the
  12-hour limit by the road minutes; it does not model drivers.
- The late fit pools weeks of 37 policies, so part of its waiting-car terms is the policy and not the queue. It is high at 16 or
  more waiting cars (5.7 to 8.9% where 4.6 to 6.6% are late; 5.3% where 2.6% of 385 orders are late on the weeks with a late cost)
  and low at 6 to 15 waiting cars on those weeks (4.0% where 5.1% are late). The archive holds no week of the default `slow-friday-late-150-kinds-limits`.
- The fit counts a waiting order once; the policy's `unbooked` counts a trade-in's two cars.
