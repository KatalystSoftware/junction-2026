# A joint search of the base's settings on the stand-in

The hill climb moves one setting at a time; this moves 17 together, in weeks with 760 drivers or more only, so a week with a
shorter driver list plays as the base to the cent (`spreadlab/standin/search.py`, `full_weeks`). `space.py` has the settings,
their ranges and the base (`trackb-merge-3`).

1. A round is a spec: `space.py design` (a Latin hypercube, the base's own point first) or `analyze.py --next` (a third around
   the model's best point, two thirds from the spread of the best played arms, as in CMA-ES). Commit it here.
2. Play it on half a, split over runners (each plays the base on the half's natural seeds and its share of arms on those with
   760+ drivers):

   ```bash
   for i in $(seq 0 15); do gh workflow run standin-search.yml --repo katalystsoftware/junction2026 --ref spread-search \
     -f ref=trackb-merge-3 -f spec=spread/scratch/search/r1.json -f half=a -f shard=$i/16; done
   ```

3. Download every shard's artifact into one folder and read it: `python3 analyze.py --spec r1.json [r2.json ...] --rows <folder>`.
   It prints each setting's swing in score, gain, orders and late orders with the others at the base, its good region, the
   pairs that interact, the best played arms and the model's best point.
4. A candidate is a named variant in `variants.py` on a branch off the base, screened with `standin-screen.yml` on half a and
   once on half b against the base: the merge gate of `spreadlab/standin/README.md`.

The search maximises `score`: the gain on natural worlds less 20 euros an extra order and 150 an extra late order a week. The
stand-in pays an extra order about twice what play does and reads late orders low. Two arms within 500 euros are a tie.
