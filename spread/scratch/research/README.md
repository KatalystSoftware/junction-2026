# Offline research scripts

One-off analysis of the saved weeks: what holds in every world, and what each idea is worth before a
week is played. None of these plays a week or needs the team key. The findings and the played results
they led to are in the "Spread related research" document of the team's Space.

They are scratch: dense, and written to print tables. Each takes its inputs as arguments and writes
only to the paths it is given, except `views.py`, which writes `view_rows.json` into the data folder.

## Run

From `spread/`, with the saved weeks unpacked into the data folder (see the main README):

```bash
R=scratch/research; D="${SPREAD_DATA:-data}"; PY="uv run --with numpy --with scipy python"

# pricing: needs scratch/curve_rows.json (PYTHONPATH=. uv run python scratch/curve_rows.py)
$PY $R/shape.py scratch/curve_rows.json
$PY $R/filt.py scratch/curve_rows.json $D/base.npy        # also writes base.npy for the next three
$PY $R/filt_grid.py scratch/curve_rows.json $D/base.npy
$PY $R/levelvalue.py scratch/curve_rows.json $D/base.npy 1.3
$PY $R/outage.py scratch/curve_rows.json $D/base.npy $D/map.json $D/outage_q.npy

# drivers: build the rows once, then the tables
$PY $R/feenoise.py $D $D/lanefee.json
$PY $R/views.py $D $D/lanefee.json explore curve-live-surcharge curve-live gate-10
$PY $R/hazard.py $D/view_rows.json $D/hazard.npy
$PY $R/windows.py $D/view_rows.json $D/hazard.npy
```

## Pricing, on the random-price weeks

| Script | Question | Finding |
| --- | --- | --- |
| `shape.py` | Is the price response logistic in log price? | Yes. Slope 12.7 with a level per week and day; curvature and interactions add nothing; Monday is steeper. |
| `levels.py` (5 minutes) | How far does the level move by week, day, place, dealer? | Week sd 0.07, day 0.13, place 0.06, dealer 0.06 in log price; one day a week is 0.22 lower. |
| `filt.py`, `filt_grid.py` | Which live shifts predict unseen weeks best? | Day shift 0.2752 log loss; with place and pickup-today shifts 0.2654; a week-long dealer shift is worse. |
| `seeds.py` (2 minutes) | How many random-price weeks pin the slope? | Ten pin the best price to 1%; the model choice moves it five times more. |
| `outage.py` | Can a region that accepts higher prices today be flagged? | In 21 of 50 weeks, at a median of 11:50; no better than the pickup-today shift. |
| `sprint.py` (2 minutes) | Does paying for dealer trust early earn its cost? | No at 0.60 euros a remaining request; about +200 euros a week at 0.05 to 0.10. |
| `levelvalue.py` | What is perfect knowledge of the day's level worth? | 600 to 1,200 euros a week above the day shift in the replay, before drivers. |
| `cost_segments.py` | What does a won order cost over its typical fee, by segment? | 1.40 overall at an opening fee of 1.2; more for `next_day` only, notes and long lanes. |

`sprint.py` and `levelvalue.py` are replays in expected values with no drivers. For the slope, play gave
a third to a half of what the replay gave, so read their differences with that ratio.

## Drivers, on weeks that opened at 1.2 x the typical fee

| Script | Question | Finding |
| --- | --- | --- |
| `feenoise.py` | Is the typical fee the lane's fee plus noise? | Yes: sd 0.125 in log within a lane. Writes the lane fees. |
| `views.py` | Builds one row per driver look and one per order. | |
| `views_look.py`, `views_fit.py` | What makes a driver book on a look? | Fee over the lane's usual fee up to 1.22, then flat; first looks and the first minutes; little after a raise. |
| `orders_look.py` | What does a slow first booking cost? | Late share 1.5% when booked in 5 minutes, 27% after 4 to 8 hours. |
| `hazard.py`, `windows.py` | When do waiting orders get booked, and when is it too late? | 87% in the first hour; later mostly at 05:00 to 08:00. Unbooked 8 hours before the last pickup: 13% late; at 4 hours 60%. |
| `drops.py` | How fast is a dropped gig booked again? | 97% rebook; 78% within 5 minutes at a fee of 1.25 to 1.5, mostly slower at night. |
| `supplycheck.py` | Do town supply, weekday and long drives matter? | Yes: thin towns and drives over 400 minutes carry the late orders; booking falls through the week. |
| `weekrisk.py` | What marks a hard week on Monday morning? | The size of the driver list: 0.8 points more late orders per 100 fewer drivers. |
