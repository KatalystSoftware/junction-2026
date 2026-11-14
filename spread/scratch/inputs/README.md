# Input audit scripts

One-off analysis for the input audit: which inputs of the game the policy does not use, and what each
predicts. None of these plays a week or needs the team key. The findings are in the "Spread input
audit" document of the team's Space.

They are scratch: dense, and written to print tables.

## Run

From `spread/`, with the saved weeks unpacked into the data folder (see the main README):

```bash
export SPREAD_DATA="${SPREAD_DATA:-data}"
for v in steep-notes-offers-8 slow-step-gate-25; do PYTHONPATH=. uv run python scratch/inputs/rows.py --variant $v --out $SPREAD_DATA/inputs; done
PY="uv run --with numpy --with pandas --with scikit-learn python"
cd scratch/inputs && $PY late_inputs.py        # each script takes a variant as its argument; the default is the reference
```

`rows.py` reads every saved week of a variant once and writes one JSON file a week with a row for each
serious quote, won order, day and direct offer. The other scripts read those files through `lib.py`.

| Script | Question | Finding |
| --- | --- | --- |
| `late_inputs.py` | Which inputs that the late chance leaves out go with a late order? | Late share against the fitted chance by group, for 23 inputs. |
| `charging.py` | How do electric cars under 30% charge book and end, on routes that need no charging stop? | On routes of 200 km or less: 10.7% late where the late chance expects 4.3%, 52% booked within the hour against 80%. |
| `late_value.py` | What is a late chance with those inputs worth in the quote? | AUC 0.760 to 0.797 on seeds left out; +133 euros of objective a week in the replay, 1.6 fewer late orders. |
| `day_supply.py` | Does the day's booking speed mark a day short of drivers, and how early? | Yes, by 11:00 with 63% of slow days caught; lookers do not. |
| `morning_drops.py` | Do the drops before 08:00 mark a day short of drivers? | 7 or more come on 0.5 days a week; that day is 7.6% late where the late chance expects 5.2%, with or without a snow forecast. |
| `week_supply.py` | Do the driver list's attributes or Monday mark a hard week? | Nothing beyond the list's length. |
| `post_win.py` | What do lookers, the driver who booked, drops and offers say after the win? | Few lookers with little time: 40% late. |
| `offers.py` | Which direct offers are read and accepted? | Half of the offers hold 97% of the acceptances. |
| `market.py` (2 minutes) | Can the outage region, the price-war day and the dealer's level be read from the answers? | The outage in 70% of weeks by 10:45; the war day's prior and the dealer's earlier share are worth nothing. |
| `extras.py` | The bulk order, the cars that wait overnight, the desk's own history at a town, cars few drivers look at. | Each small. |

`late_value.py` and `market.py` are replays in expected values with no drivers. For the curve's slope,
play gave a third to a half of what such a replay gave.
