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

`archive/` holds a copy of the scans, the played weeks and the map, so they survive the machine that
played them. It is stored with [Git LFS](https://git-lfs.com): without it, the files are short text
pointers. The harness does not read `archive/`; copy it into the data folder first.

```bash
git lfs install && git lfs pull                                 # fetch the files
mkdir -p data && cp -rn archive/. "${SPREAD_DATA:-data}/"       # use them; keeps newer local files
rsync -a "${SPREAD_DATA:-data}"/{runs,scans,map.json} archive/  # add new weeks before a commit
```

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
3. Read the report: ranked weeks first, then the margin. A week under 90% on time scores nothing.
   - `above zero` counts the weeks that are ranked and beat `decline-all`. Declining every request
     makes 0 and is not ranked, because a week with no orders is not ranked.
   - `95% interval` is for the mean difference to the reference, from drawing the weeks again 10,000
     times. When it includes 0, play more seeds before believing the difference.
   - Weeks that are missing or failed are named above the table and left out of it. Play them again first.
4. Read the ledger for where the money went. `in weeks` tells a habit of the variant from one bad week.
5. Confirm on the `holdout` list before keeping the change.

## Results so far

Level 8, mean margin a week in euros on the first 10 seeds of each list. Every week of every row is ranked.

| Variant | What it adds | Tune | Holdout | Lowest on time |
| --- | --- | --- | --- | --- |
| `baseline` | 1.5 x list, 60% of acceptable requests, no `same_day` | 721 | not played | 95.1% |
| `with-same-day` | offers `same_day` | 1,669 | 1,857 | 91.7% |
| `floor-1.7` | never quotes under 1.7 x the typical driver fee | 3,472 | 3,579 | 91.8% |
| `gate-10` | quotes every acceptable request, but none while 10 won cars have no driver | 5,083 | 4,541 | 93.1% |

`gate-10` is the reference for new ideas. `floor-1.7-all` shows why the gate is needed: without it, one
tight week falls to 87.4% on time and is not ranked.

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
- [`play.py`](spreadlab/play.py), [`sweep.py`](spreadlab/sweep.py), [`report.py`](spreadlab/report.py): play, compare.
- [`ledger.py`](spreadlab/ledger.py): mistakes by variant and situation.

## Limits

- All systems on one team key share 8 open practice worlds and one request budget. A sweep uses 7
  worlds and waits when none is free.
- A sweep that is killed leaves its worlds open. `client.worlds()` lists them, and
  `client.world(id).delete()` frees one.
- The ledger does not label the price war, the outage or the flu yet.
