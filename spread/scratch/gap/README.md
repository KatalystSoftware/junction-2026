# Where the orders are: offline scripts

One-off analysis of the 60 saved weeks of the reference `steep-notes-offers-8` (20 catalogue seeds and
`fresh-001` to `fresh-040`): why the desk wins about 260 orders a week where the best teams on the
level-8 board win 370 to 460 at about the same margin an order. None of these plays a week or needs
the team key. The findings are in the "Spread order gap" document of the team's Space.

They are scratch: dense, and written to print tables. Each takes the data folder and a cache folder
as arguments. The first script to run loads a variant's weeks and saves them as one pickle in the
cache folder (about a minute for 60 weeks); the others start from it.

## Run

From `spread/`, with the saved weeks unpacked into the data folder (see the main README):

```bash
G=scratch/gap; D="${SPREAD_DATA:-data}"; C="$D/gap-cache"; V=steep-notes-offers-8
PY="uv run --with numpy python"; export PYTHONPATH=.

$PY $G/funnel.py $D $C $V          # builds the cache of the variant's weeks
$PY $G/price.py $D $C $V           # writes quotes-$V.pkl and levels-$V.json for the next three and the replay
$PY $G/orders.py $D $C $V
$PY $G/backlog.py $D $C $V         # writes state-$V.pkl
$PY $G/backlog_late.py $D $C $V
$PY $G/hours.py $D $C $V
$PY $G/replay.py $D $C $V 1        # 1 draw, 3 minutes; the default is 2
$PY $G/replay_sent.py $D $C $V     # the variants proposed for play, 2 draws, 4 minutes
```

`capacity.py`, `trust.py` (after `price.py`), `late.py`, `flags.py` and `bulk.py` take the same three
arguments. `offers.py` and `offers_known.py` take `$D $C` and one or more variants, `note_deadline.py`
takes `$D $V`, and `volume.py` takes `$D` and reads the score files of every variant.

## What each one asks

| Script | Question | Finding on the reference |
| --- | --- | --- |
| `funnel.py` | Where do a week's requests go? | 1,032 requests: 862 quoted and 262 won; 114 private and 21 trade-ins declined, 25 at the backlog gate, 12.5 for slack. |
| `price.py` | Why are quotes lost, and what does the curve give at another cost? | Lost on price: a lost quote needed a median cut of 13.5% for an even chance. With each day's level known and no surcharge, cost 1.3 gives 391 orders at 39.1 euros each and cost 1.2 gives 459 at 35.3, before any feedback. |
| `backlog.py` | What did the desk know at each quote, and what does the backlog surcharge do? | It rebuilds 98.5% of the quoted prices. 5.4 won cars have no driver at a quote, 3.1 of them due in over a day, and the surcharge averages 0.20 x the typical fee. Knowing each day's level from its first minute is worth 5 to 7 orders. |
| `backlog_late.py` | Which waiting cars predict that the new order ends late? | Log odds per car: +0.157 due in 8 to 24 hours, +0.075 due within 8, +0.030 (se 0.016) due later. |
| `hours.py` | What does an order cost by the hours the desk has to find a driver? | Fees, refunds and failed visits over the typical fee: 1.27 under 6 hours (15.2% late), 1.15 at 6 to 8, 1.13 at 8 to 12, 1.12 at 12 to 30, 1.11 beyond (2.2% late). All are quoted at the same cost. |
| `orders.py` | How do won orders find a driver? | Orders to collect on the day of the win are 6.7% late, the others 2.6%. Drives over 400 minutes are 18.7% late. |
| `late.py` | What happened to the late orders? | Of 11.5 a week, 5.8 had no driver at the last pickup minute; 68% of those were seen by 30 or more drivers, at a median highest fee of 2.5 x typical. 4.2 had a driver and still arrived late. |
| `flags.py` | Which requests end late more often? | Premium cars: 12 a week, 13.2% late, cost 1.27 x typical. Won on a Friday for a pickup that day: 15 a week, 14.5% late. |
| `capacity.py` | How many drivers are there to book? | Of 792 on the list, 596 look at a gig in the week and 143 drive one. On a weekday 205 to 307 look and 12 to 59 drive. |
| `trust.py` | When does dealer trust arrive, and what takes it away? | The largest dealer reaches a count of 25 on Wednesday at 14:00 (median); late orders halve it 3.8 times a week. 60% of quotes are made at a count under 5. |
| `offers.py`, `offers_known.py` | Who accepts a direct offer? | 6.4 of 1,155 a week. Half are sent with under 3 hours left or after the last pickup minute, where about 0.1% are accepted. A driver who looked at that order's gig before accepts 1.4%, others 0.27%. |
| `bulk.py` | How does the desk do on the bulk order? | It wins 11 of its 47 requests, 4.1% late, at the average margin. |
| `note_deadline.py` | Are a note's tighter deadlines met? | 6.3 orders a week carry one and 16% are late; 0.7 a week arrive after the note's deadline and by the order's. |
| `volume.py` | What did more orders cost in the sweeps that were played? | Cost 1.2 against 1.3 won 28 to 34 more orders, of which 6 to 10% were late. |

## The replay

`replay.py` plays the saved weeks again with other prices. What is won changes the backlog, the day's
live shift and each dealer's trust, and those change the next quotes. Each quote keeps one hidden
draw that agrees with its answer at the played price and trust, so the reference rules give the
played week back: 262 orders, 12.0 late and 10,685 euros, against 259, 11.5 and 10,449 played. An
order that the replay wins and the week also won keeps its own course; a new one takes the course of
a saved order with the same hours to find a driver.

It overstates. For cost 1.4 it says 44 orders fewer and about 1,300 euros less, where play gave 31.5
and 460. It leaves out drivers getting scarcer beyond the backlog fit of `backlog_late.py`, and the
competitor cutting prices where the desk wins most. Read its differences as half to four fifths in
orders and a third to a half in margin.

`replay_sent.py`, 2 draws of 60 weeks, margin against the reference with driver fees 0.026 x the
typical fee dearer per 100 more orders:

| Variant | What changes | Orders | Late | On time | Margin |
| --- | --- | --- | --- | --- | --- |
| reference | cost 1.3 + 0.04 a won car without a driver, gate at 15 | 262 | 12.0 | 95.4% | 10,685 |
| `step-2` | 0.02 a car | 306 | 14.8 | 95.2% | +960 |
| `step-2-gate-25` | and the gate at 25 | 320 | 15.7 | 95.1% | +1,628 |
| `due-24-gate-25` | 0.04 only for cars to collect within 24 hours, gate at 25 | 332 | 17.2 | 94.8% | +1,713 |
| `hours` | cost 1.55, 1.35, 1.3, 1.2 and 1.15 by the hours to find a driver | 299 | 13.2 | 95.6% | +799 |
| `hours-step-2-gate-25` | both | 368 | 18.6 | 94.9% | +2,210 |
| `hours-due-24-gate-25` | both | 391 | 19.7 | 94.9% | +2,447 |

These variants and the parameters they need (`cost_hours`, `backlog_hours`) are not in
`spreadlab/` at this commit: no week has been played with them.
