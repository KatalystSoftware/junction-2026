# The policy as an optimisation problem: offline scripts

One-off analysis for the "Spread optimisation formulation" document of the team's Space: what an order really costs, a
stand-in for a played week to price the saved weeks again under another cost rule, and the outer search run on it.
None of these plays a week or needs the team key. They are scratch: dense, and written to print tables.

## Run

From `spread/`, with the saved weeks unpacked into the data folder and the caches of `scratch/gap/` built for the
reference (`funnel.py`, `price.py`, `backlog.py`; see that folder's README):

```bash
O=scratch/opt; D="${SPREAD_DATA:-data}"; C="$D/gap-cache"; export PYTHONPATH=.
PY="uv run --with numpy python -u"

$PY $O/validate.py $D $C 2           # the stand-in against ten played variants, 2 draws, 3 minutes
$PY $O/calibrate.py $D $C trust      # what a late order costs in dealer trust
$PY $O/calibrate.py $D $C react 0.6  # the competitor's answer, fitted on the played variants
$PY $O/late_check.py $D $C           # the late model on weeks it was not fitted on
uv run python $O/marginal.py $D due-24-gate-25 step-2-gate-25   # where the margin of the extra orders goes in play
$PY $O/homes.py $D $C                # who books a gig, by where the driver lives
uv run --with numpy --with optuna python -u $O/search.py $D $C 120 0.6   # the outer search on the stand-in, 6 minutes on 4 cores
uv run --with numpy --with optuna python -u $O/search.py $D $C 120 0.6 top10   # the same, chosen on mean margin with at most 1 week in 20 under 90%
uv run python $O/confirm_check.py $D slow-friday-late-150-kinds-limits search-16-kinds   # a confirmation on the two unseen sets, from the saved scores
```

## What each one found, on the 104 saved weeks of `steep-notes-offers-8`

| Script | Question | Finding |
| --- | --- | --- |
| `sim.py` | The stand-in: the saved weeks priced again under a cost rule, with the backlog, the day's shift, trust and the projected on-time share fed back. | A new order ends late by a fitted chance and its week's own intercept, so a hard world stays hard. |
| `validate.py` | How far is the stand-in from play? | Extra late orders are right; extra orders are a half too high and extra margin two to five times too high without the competitor's answer. |
| `calibrate.py react` | How strongly does the competitor answer what the desk wins? | 0.6 in log price per unit of extra share at a dealer the day before: the margin error on eight played variants falls to 245 (root mean square). |
| `calibrate.py trust` | What does a late order cost in dealer trust? | 36 a late order on average (450 a week), next to 46 of refund. |
| `late_check.py` | Does the late chance hold on unseen weeks? | AUC 0.78; the riskiest tenth of orders is 21% late and holds 42% of the late orders. |
| `marginal.py` | What does an extra order earn in play? | About 14, against 40 on average: it sells at 1.42 x its typical fee and costs 1.23 x with refunds. |
| `homes.py` | Does a driver's home say what a gig costs them? | A driver who lives at the delivery place books 52% of their looks at the opening fee, one in the pickup town 16%, others 8 to 13%. |
| `search.py` | What does the outer search find on the stand-in? | cost 1.2, a late cost of 220 to 250, a small surcharge for cars due within 24 hours and no gate: +1,480 a week on 52 unseen weeks with no week under 91%. An upper bound: the stand-in draws lateness from the model that the rule prices with. |
| `search.py top10` | Does allowing 1 week in 20 under 90% buy margin? | No. The search turns the 90% rule's price off (cost 1.25 to 1.27, a late cost of 157 to 192, no gate): +1,514 to +1,586 on the unseen weeks with one or two of 52 under 90%, which is +1,106 to +1,353 once those count as no margin, against +1,480 for the point above. |
| `confirm_check.py` | Does the confirmation of the default hold in the saved scores? (Played weeks of the two unseen sets, not the 104.) | Yes. `slow-friday-late-150-kinds-limits` makes +1,601 (1,336 to 1,885) and +1,370 (1,120 to 1,634) a week over the reference on the two sets of 60, with no week under 90% and 1 and 2 under 92%. On the first set it is about +300 (95 to 506) above `search-16-kinds`; the intervals are bootstraps and move a little with the variants named. |
