# A different strategy: offline scripts

One-off analysis of the saved weeks and scans: why the best teams on the level-8 board win about 450
orders a week at €42 an order and 97% on time, where our extra orders earn €9 each and run late once
16 cars wait, and what a desk that puts an order and its return in one gig could gain. None of these
plays a week or needs the team key. The findings and the three ranked proposals are in the "Spread
strategy alternatives" document of the team's Space.

They are scratch: dense, and written to print tables. Each takes its folders as arguments and reads
only the standard library, except `opt_days.py`, which needs numpy.

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
| `rows.py`, `opt_days.py` | Where does the `opt` rule earn and lose against `slow-step-gate-25`, and what late chance fits the orders won while cars wait? | On 38 seeds: +213, +178 and +118 euros on orders won Monday to Wednesday, -81 and -94 on Thursday and Friday. At 16 or more waiting cars 5.2 to 6.2% are late, the `friday` weights of `slow.py` say 2.5 to 3.9%, and the fit below says 6.0 to 9.9% on seeds it was not fitted on. |

## The late chance with the waiting cars

`opt_days.py` fits the 14 terms of `slow.py`, in its order, and three more for the won cars without a driver at the
quote, in tens and capped at 30: those due within 24 hours, those due later, and those due within 24 hours once more
when this order has under 12 hours. Fitted on 82,113 one-car dealer orders of 187 seeds and five variants, checked on
108,090 orders of the other seeds:

```python
WAITING = [-4.699, 1.577, 1.063, 0.756, 0.302, 0.557, 0.548, 1.499, 0.461, -0.631, 0.482, 0.191, 0.194, 0.887,  # slow.NAMES
           0.568, 0.623, 0.92]  # tens of waiting cars: due within 24 hours, due later, due within 24 hours for an order with under 12 hours
```

It is not wired into `slow.py`; a variant that uses it needs the two counts at the quote, which `Policy.unbooked(hours)` gives.

## Limits

- No dealer two-car gig exists in the saved weeks. The fee and the booking speed of a pair come from trade-ins, which
  have a private address and a booked hour.
- `pairs.py` takes the dealer to choose the fastest option quoted and checks windows, stated hours, deadlines and the
  12-hour limit by the road minutes; it does not model drivers.
- The late fit pools weeks of five policies, so part of its waiting-car terms is the policy and not the queue.
