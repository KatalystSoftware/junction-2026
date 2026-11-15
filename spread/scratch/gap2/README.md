# Why we trail the top teams, and why the final came up €2,000 short

Offline scripts behind the gap study (Saturday evening to Sunday morning) and the final's post-analysis. All of them read
Bahn's public boards or our own saved data; none needs a team key. Run each with `python3 -I`.

| Script | What it reads | What it prints |
| --- | --- | --- |
| `round_table.py [--board FILE] [--drivers "Round=d1,..,d5"]` | the practice board (`/v1/leaderboards/practice?level=8`), fetched and saved to `boards/` without `--board` | per week of each round we finished: drivers, 5th's and 10th's margin and orders among that week's valid runs, ours with place, and 10th ÷ ours |
| `final_split.py DIR` | `log.jsonl` and `end.json` (score and reveal) of one desk week, as the live desk writes them to `data/live/<world>/` | requests, declines, wins and quote ÷ list by day; win rate by quote ÷ list and by quote ÷ reference fee; driver fee paid per order against the reference fee |
| `test_final_split.py LB.json` | the last `data:` message of the final stream (`GET /v1/leaderboard`, no key) | each team's revenue and cost an order, and the gap to a place split into volume, price and cost |
| `board.py`, `decomp.py`, `perrun.py` | a saved practice board | ranking per round, the gap split into volume and margin an order, per-week ranks |
| `risk_board.py`, `risk_top.py` | saved practice boards | weeks under 90% on time for the field and the top 20 |
| `risk_own.py`, `risk_sim.py` | the round row files (`origin/trackb-rounds:spread/scratch/rounds/*.csv`) | our weeks under 90% against orders per 100 drivers |
| `risk_archive.py ROOT`, `item1.py ROOT [variant]` | the stand-in's packed weeks (releases `spread-standin-data`, `spread-standin-screen`) | weeks under 90% across the archive; at what fee and lead time late cars booked |

The raw desk log of the final is not here; it stays on verda-hel in `spread/data/live/f08312f6894c3a962e71b/`.

## The final: 26th of 58, €2,000 short of 10th

`trackb-merge-8.3` (variant `m41u-b-bud-b-x720-819`, fingerprint `94782d66abf0`) played a world of 749 drivers:
€17,087.76 on 350 orders, 97.4% on time, all 1,034 requests quoted by the policy, no fallback, error or takeover.

| | Margin | Orders | Revenue an order | Cost an order | Margin an order | On time |
| --- | --- | --- | --- | --- | --- | --- |
| Us, 26th | €17,088 | 350 | €110.5 | €61.7 | €48.8 (1st of 58) | 97.4% |
| 10th, Evil Club | €19,084 | 443 | €100.8 | €57.7 | €43.1 | 97.5% |
| Top-10 mean | €19,822 | 461 | €104.8 | €60.5 | €44.2 | 96.6% |
| 1st, Juhus | €22,931 | 474 | €111.9 | €63.5 | €48.4 | 97.7% |

We kept the most of any team on each order and were 40th of 58 in orders. The €1,996 to 10th is volume +€4,540, price
−€4,323, cost +€1,778. Across the ranked field one more order went with about +€44 of margin, and revenue and cost an
order did not move with volume. Juhus sold at our price and still won 124 more orders, so which requests we lose matters
more than the price level.

**By day** (`final_split.py`):

| Day | Requests | Declined | Won | Win rate of quoted | Median quote ÷ list | Day correction |
| --- | --- | --- | --- | --- | --- | --- |
| Mon | 219 | 7 | 57 | 27% | 1.34 | −0.18 |
| Tue | 204 | 5 | 67 | 34% | 1.56 | 0.00 |
| Wed | 191 | 5 | 90 | 48% | 2.00 | +0.24 |
| Thu | 241 | 4 | 79 | 33% | 1.82 | +0.06 |
| Fri | 179 | 34 | 60 | 41% | 1.64 | +0.01 |

**By quote ÷ list** (our lowest option): under 1.2, 72% won; 1.2 to 2.2, 36 to 45%; **2.2 or more, 10 of 180 (6%)**.
Those 180 are the requests that are dear to serve (reference driver fee €115 against a list of €102), and our markup on
the driver cost carried them past the field.

**Where the missing orders are**, roughly, since the parts overlap:

| Source | Orders | Basis |
| --- | --- | --- |
| Quotes at 2.2 × list or more | about +55 | at the 1.8–2.2 band's win rate |
| Monday's low win rate | about +25 | at Tuesday to Friday's rate; may be the field, not us |
| Friday's day cap (30 requests from 15:18 to 17:54) | about +12 | at Friday's win rate |

About 90 orders, against the 93 that 10th won more.

**Not the cause:**
- **Driver fees:** €60.1 a won order, a median 0.80 of the reference fee, with 85 of 275 paid gigs carrying two or more orders.
- **Late refunds:** €560 on 9 orders.
- **The on-time budget:** it was off by design at 749 drivers (the 720–819 band plays `trackb-merge-4.1`), and 10th finished at the same 97.5% on time.
- **`km40`:** it was on (`pair_km` 40), and one week cannot measure it.

The final's board was not logged over time, so other teams' day curves are unknown; in the test final 94 of the 109
missing orders were already missing at the end of Thursday.

**The changes most likely to have closed the gap:**
1. Stop the quote rising with the driver cost at about 2 × list.
2. No day cap on the last day while on time is safely above 96%.
3. A cheaper Monday opening (the weakest evidence of the three).

## Before the final: the gap in the practice rounds

- **19:00 UTC round (merge 1, 32nd of 56):** 10th's margin an order was ours (€42 against €43); it won 402 orders a week to our 353.
  - At 760 drivers or more we won 38 to 41 orders per 100 drivers, the field 45 to 52.
  - 10th's lead was €2,762 a week at 760 or more and €1,786 under 760 (board read at 23:59 UTC).
- **Risk was not what bought the top teams their volume:** of the 20 highest margins of each round, 0 of 200 weeks fell under 90% on time.
- **Test final (merge 2, 20th of 41, 832 drivers):** the top 10 paid the same per order and sold €6.6 cheaper. The gap to their mean was volume +€5,035, price −€2,481, cost +€253.
- **RoutePulse in thin weeks** (stand-in, 6 seeds of 634 to 659 drivers):
  - 382 orders against our 254, at €90 an order against €107, with driver fees €49.5 against €67. The margin per order was the same.
  - It opens driver offers below the typical fee and raises them steeply only on late gigs.
