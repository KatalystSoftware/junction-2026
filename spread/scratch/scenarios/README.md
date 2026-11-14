# Scenario map: offline scripts

One-off analysis behind the "Spread scenario map" document of the team's Space: what the final can
throw at the desk, how often the saved weeks show it, and what it cost the reference
`steep-notes-offers-8`. None of these plays a week or needs the team key.

They are scratch: dense, and written to print tables.

## Run

From `spread/`, with the saved weeks unpacked into the data folder (see the main README):

```bash
S=scratch/scenarios; D="${SPREAD_DATA:-data}"; PY="uv run --with numpy python"; export PYTHONPATH=.

$PY $S/extract.py $D $D/ref.json steep-notes-offers-8   # one compact row set per week, for the others
$PY $S/scans.py $D                                      # writes $D/scans.json
$PY $S/freq.py $D/ref.json
$PY $S/market.py $D/ref.json                            # a minute; writes $D/ref-market.json
$PY $S/supply.py $D/ref.json
$PY $S/flu.py $D/ref.json
$PY $S/risk.py $D/ref.json
$PY $S/bar.py $D
```

## What each one asks

| Script | Question | Finding on the reference's 104 saved weeks |
| --- | --- | --- |
| `scans.py` | What does every world show before any decision? | 460 scans: rosters of 634 to 950 drivers, 17% under 680. No request before 08:00 or after 20:59. A bulk order of 30 to 40 cars every week, from a yard with under 5 drivers nearby in 12% of worlds. One or two snow forecasts a week, a day ahead. |
| `freq.py` | How often does each event come, and how late are the orders it touches? | 30 drops, 6 changed orders and 2.8 cancellations a week. Late: premium cars 14.6%, note deadlines 17.4%, snow 7.9%, Friday 8.2%, against 4.7% overall. |
| `market.py` | How far does the price level move, and what does learning it live lose? | Week level sd 0.067 in log price, worth 3,170 euros of margin per 0.10. One day a week is 0.24 lower. The day's live shift loses 85 euros a week in expected margin against knowing each day's shift; a carried week level and a war filter recover none of it. |
| `supply.py` | Which live signal marks a week short of drivers on Monday? | None beyond the roster size: Monday's bookings predict the later late share with a leave-one-out R2 of 0, the roster size 0.07. |
| `flu.py` | Is the flu day visible, and what can a controller still stop? | A day with under 0.75 of the usual lookers in 37% of weeks, about 0.9 more late orders; a detector on its first 10 cars flags 150 of 468 ordinary days. In the 10 worst weeks, 12.3 of 20.5 late orders are won after Tuesday 18:00 and 9.4 after Wednesday. |
| `risk.py` | What does one avoided late order cost when the riskiest orders go first? | 77 euros for the riskiest 2% of orders, 170 for the next 3%, 336 at 5 to 10%, 635 at 15 to 20%. |
| `bar.py` | How often would an archived variant clear a higher top-10 bar? | None clears the reference plus 3,400 euros on any shared seed; the best clears plus 1,500 in 20% of weeks. |

`stress-seeds.json` lists 70 scanned seeds by scenario (thin bulk yard, thin towns, few experienced
drivers, bulk order on Monday, thinnest rosters, highest price level, ordinary), none from the first
30 tune seeds, for sweeps that test a candidate where a scenario is strongest.

`market.py` is a replay in expected values with no drivers: read its differences, not its levels.

## What play said afterwards

Played by the policy thread on the seeds of `stress-seeds.json` and on the reference's 19 lowest worlds:

- The default `slow-friday-late-150-kinds-limits` makes 1,300 to 2,260 euros a week more than the reference
  in every stratum, with one week under 90% on time in 58 against one.
- A late cost of 400 that starts at the reference's 150th order rescues one of its four unranked weeks,
  and 800 there none. From the first order it rescues all four and costs 850 a week on ordinary worlds,
  where `risk.py` had 973. Inside the cost (225 inside 1.19) it pays on both sets.
- The day of the bulk order: a Monday bulk order is no weakness of the default (1 of 76 weeks under 90%,
  against 1 of 190 on the other days). A Thursday one may be: 5 of 57 weeks under 92% against 3 of 209.
