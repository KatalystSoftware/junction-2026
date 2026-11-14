# Inputs against merge 1

One-off analysis: which inputs of the game merge 1 (`fee16-80-q24-wide-pairs-0.6-return-0.75`) leaves unused, and what
each is worth. Nothing here plays a week or needs the team key. The findings are in the "Spread inputs against merge 1"
document. Scratch: dense, written to print tables.

Run from `spread/`, with the saved weeks unpacked into the data folder (see the main README):

```bash
export SPREAD_DATA="${SPREAD_DATA:-data}" PYTHONPATH=.
V=slow-friday-late-150-kinds-limits   # or any variants with saved weeks, comma-separated
uv run python scratch/inputs2/homeward.py $V                                   # share won, cost and late share by where drivers live
uv run python scratch/inputs2/passes.py /tmp/a.json $V && uv run python scratch/inputs2/read.py /tmp/a.json                  # the flu night, driver positions
uv run python scratch/inputs2/passes2.py /tmp/b.json $V && uv run --with numpy python scratch/inputs2/read2.py /tmp/b.json   # Monday's signs, snow, cost by supply, trust
# weeks.py reads the played weeks' rows, one CSV a set, from a folder:
mkdir -p /tmp/rows && for f in exam ladder1 q1; do git show origin/trackb-rounds:spread/scratch/rounds/$f-rows.csv > /tmp/rows/$f.csv; done
git show origin/topten-push:spread/scratch/topten/weeks/cand-fresh-1701-1760.csv > /tmp/rows/cand-nat.csv
git show origin/topten-push:spread/scratch/topten/weeks/cand-thin-reserve.csv > /tmp/rows/cand-thin.csv
uv run --with pandas --with scikit-learn --with statsmodels python scratch/inputs2/weeks.py /tmp/rows
```

For merge 1, set `V=fee16-80-q24-wide-pairs-0.6-return-0.75` where its weeks are saved. `homeward.py` then gives the first row of
the document's ranked table on merge 1's own orders, and `read2.py` section (a) its fourth. The findings below are from 266
weeks of the old default and 197 weeks of 13 high-volume desks (the `HV` list in the main README's exposure section), since
the archive holds no weeks of merge 1.

| Script | Question | Finding |
| --- | --- | --- |
| `weeks.py` | Which week-level inputs go with merge 1's low weeks, over its 200 played weeks? | All 4 weeks under 90% had a night of 10 or more first-hour drops (4 of 83 against 0 of 117); 3 of 4 had 678 to 687 drivers. |
| `homeward.py` | Where does the desk win least, and what do those orders cost? | Requests that end where 100 or more drivers live and start where under 40 do: 143 a week, 18% won, 1.6% late, the lowest fees. High-volume desks win 30% of them at 2.3% late. |
| `passes.py`, `read.py` | What ends late on a flu day, and do the positions of the desk's own drivers help? | A wave day has 1.9 more late orders (2.9 in thin worlds), mostly the dropped cars. Offers to a driver who just delivered nearby: 0.18% accepted against 0.32%. |
| `passes2.py`, `read2.py` | Do the first days mark a bad week; snow; cost by supply; the dealer's trust count. | At 350 orders a week Monday's numbers put 9 of 12 weeks under 92% in the worst-looking fifth; at 306 orders they say nothing. Snow at the win: 21 orders a week, 5.9 to 7.8% late against 3.2 to 4.1%. A late order costs 10 to 12 euros in the dealer's later prices, 30 to 34 at a count of 20 or more. |
