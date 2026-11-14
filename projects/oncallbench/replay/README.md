# OnCallBench replay viewer

The on-call shift replay for the `aq-incident` task. One screen for the demo: an agent's on-call shift next to the scripted reference on the same seed.
The first screen has only what a passer-by needs: the two estates turning red and recovering, the
money each run has lost so far, what each run is doing now and why, play, and the timeline.
Everything else opens on a click or a hover.

Live at https://incident.katalyst.fyi/ (see Deploy).

## Run

```
xdg-open index.html   # macOS: open index.html
```

The page is static and has no dependencies; it opens straight from disk with the committed
bundles in `data/`. Level 4, seed 418 opens first; seeds 108 and 109 are the other tabs in the bar.

## Add or refresh an episode

An episode is one level and seed. Each is one bundle, `data/l<level>-s<seed>.js`, and
`data/index.js` lists them for the page: the episode `notes.json` names under `open` first, then
newest level first. The first one is what opens.

```
python3 export.py --level 5 --seeds 110 --jobs ../jobs   # add level 5: reference, scripted policies, trials found
python3 export.py                                        # every bundle again, with the current simulator
```

**A bundle is an answer key.** It holds the episode's faults and every call of the reference, and
the site is public. The exporter refuses the seeds of the shipped tasks at every level (101, 102
and 103, and any `SEED` under `../tasks/`), and refuses to run while a bundle of one sits in
`data/`. Levels of a seed share its estate and most of its faults, so a level-3 bundle of a
shipped seed gives the level-4 task away too. Use the fresh seeds 107 to 112: the task as shipped
was run once on each (round 13 in `../metrics.json`), and no task plays them.

That first line is all a new level needs: the exporter writes the bundle and rewrites
`data/index.js`, and the page picks it up as a new tab that opens by default. To caption it, add
an entry to `notes.json` (below) and run the second line. In this repo Python comes from the
flake: `nix develop -c python3 export.py ...`.

- `--jobs <folder>` adds the agent trials of that episode found in a Harbor jobs folder; `--trial
  <folder>` adds one trial. `--only a,b` keeps the trials whose job name contains one of the strings.
  A job run with several attempts gives one run per attempt, named `<job>-<attempt>`.
  Trials of `../run.sh`'s task copies (`aq-incident-<hash>__...`) and of exported tasks
  (`seed-<seed>__...`, from `../export-tasks.sh`, whose level and seed are read from the task's
  MCP server) are both recognised.
- `--policies a,b` picks the scripted policies shown next to the reference.
- A bundle keeps its trials' action logs and words, so later exports of the same episode keep them
  without the Harbor folders. `--fresh` drops them.
- `--sim` and `--policy-file` point at another copy of the simulator. `--out shift.json` writes
  plain JSON and no bundle.

`notes.json` holds, per episode:

- `title`: the tab's name; `order`: the trials in order, the first is the run that opens.
- `runs.<id>.what`: the sentence shown as the run's outcome when the shift is over, with a `source`.
- `runs.<id>.moments`: calls the story turns on, matched by `tool` and `service`. A moment can
  carry a `label` (named on the timeline), a `quote` from the agent's own closing message, and
  `told`: the first words of the sentence of the task instruction that covers the call. The
  exporter looks that sentence up in the instruction as shipped (`../task/instruction.md` with the
  level's briefing) and prints a note if it is not there.
- `headline`: where the level's result over all measured runs comes from (the regrade file and the
  receipts under `../loop-evidence/`). The exporter computes the mean, median and range from it,
  and replays each receipt to see whether capacity went on the quiet fault's service before the
  rollback. Its `fresh` entry adds the same model's runs on the fresh seeds from `../metrics.json`.
  The receipts are not exported, only each run's score and how it handled the quiet fault.
- `open` (top level): the episode that opens first.
- The first call of a run that has a `label` is its key moment (`pause=key`, "Go to the key
  moment"), so label the decisive call and leave earlier moments with a quote only.

## Test

```
python3 export.py && git diff --exit-code data/
```

Re-exports every bundle from its stored action logs. Every export checks itself: the per-minute
losses, replica costs and wasted mitigations must add up to the cost the simulator settles, a
trial's receipt must carry a valid signature, and every logged action must be accepted again on
replay. A clean diff means the simulator and the reference still give the bundled numbers.

## The bundles

Every number on the page comes from the simulator and reference on `main`. The results strip
matches the closing report at the top of `../LOOP.md`: level 4 as shipped (round 10's
instruction), graded against the round-11 reference.

Every episode is a seed no task ships, with one run made on the task as shipped. The runs on the
shipped seeds 101 to 103 are not replayed here: their bundles would be the tasks' answer keys.

| Episode | Run | What happened |
| --- | --- | --- |
| **Level 4, seed 418** (`data/l4-s418.js`), opens first | Claude Fable 5.2, 0.26 (round 15) | Level with the reference until minute 25. Then it rolled back media-svc without adding capacity first: retries overloaded it and admin-portal, which earns $19,300 a minute, went to 80% errors. Minutes 25 to 34 cost it $112,000, the reference $10,000. |
| Level 4, seed 109 (`data/l4-s109.js`) | Opus 5.5, 0.36 (round 13) | Level with the reference until minute 34. Then it rolled back search-svc without adding capacity first: retries overloaded it and web-storefront went to 72% errors. Minutes 34 to 46 cost it $163,000, the reference $42,000. |
| Level 4, seed 108 (`data/l4-s108.js`) | Opus 5.5, 0.34 (round 13) | The same mistake on checkout-svc, then a 50% throttle once the storm had started. Minutes 34 to 46 cost it $132,000, the reference $36,000. |

Seed 418 opens because it shows the level's decisive moment on the newest model: Fable 5.2
matches the reference until the quiet fault, rolls back unprotected ("I started the rollback
before checking its headroom"), and costs the most in the ten minutes after. Seed 109 is the
same mistake by Opus 5.5. The scripted baselines (unprotected rollbacks, do nothing and the others) are in
the run picker.

The strip in the bar shows all nine Opus scores on the shipped seeds (mean 0.32, median 0.18,
range 0.03 to 0.80); its sheet lists them by seed and by what the run did, then the six fresh-seed
runs (mean 0.55, 0.34 to 0.75). One number differs from the report's text: it gives the
unprotected runs as 0.03 to 0.59, which is the highest of them as run; graded against the
round-11 reference that run is 0.61, and the page shows the regraded score like the report's own
table.

## The scores band

Above the replay, one row per model: a dot for every run on the 24 common level-4 seeds 200000
to 200023 (Opus 5.5 twice per seed, the others once), its mean as a tick with the 95% interval as
a bar, and the numbers on the right. The reference's 1.00 and doing nothing's 0.00 are
the two walls. It shows the gap holds over repeated runs, not one seed and one run.

```
python3 export.py --spread && ./deploy.sh   # pick up new runs from ../metrics.json and ship them
```

- The runs are `../metrics.json` rows of round 16, level 4, with `run` = `opus`, `fable`,
  `gemma-base` or `gemma-ft`. Only Harbor trials count (a `trial` of `<job>/<trial>__<id>`):
  scores from another harness, such as `../rl/`'s own runner, are left out with a note. `notes.json` under `spread` sets the round, the seeds, the models
  in order with their labels, and the caption. A model with no runs yet has no row, and with no
  runs at all the band is not drawn, so the page looks as it did before. To drop a model, delete
  its line there. Runs on other seeds are left out, with a note.
- The mean counts each seed once. Its 95% interval comes from the seed means (Student's t, seeds
  minus one degrees of freedom), because the runs on one seed share its outage and are not
  independent. That is wider than a t-interval over every run would be.
- It carries scores only, no actions or faults, so it is safe for any seed.
- `--metrics <file>` reads another file of rows in the same shape, for a look at the band before
  the runs exist. The output is marked as a placeholder, the page says so in red, and `deploy.sh`
  refuses to ship it.
- `?spread=0` leaves the band out.

## Using the page

- First visit: a three-line intro (what this is, what to watch, the result). It is shown once;
  the "?" in the bar reopens it. A link to a moment skips it.
- Under each run's name: what it is doing now, and why. For the reference that is the runbook
  rule with the numbers it used; for the agent, its own words about that call from its closing
  message. When the shift is over the line becomes the run's outcome.
- Click a mark on the timeline for the details of that call: what it did to the faults, for the
  reference why, for the agent the sentence of the task instruction that covers it and its own
  words, and what the call returned. Hover a mark for the short version.
- "How the reference decides": its seven rules. The rule in use lights up as the shift plays.
- The strip in the bar: every measured run of the headline model on this level. Its sheet lists
  the scores by seed; the ones on this seed switch the view to that run.
- "Show each fault": one lane per fault with how long it stayed live in each run.
- "Key": every mark on the graphs and the timeline, and how the score is defined.
- Space plays and pauses. Drag the timeline to scrub. Left and right step through the agent's
  actions; with Shift they move five minutes. Home and End jump to the ends. Escape closes sheets.
- Hover a service for its name, error rate, callers and dependencies.
- "Go to the key moment" jumps to the call the agent's run turns on and pauses there. While that
  call holds the agent's line, the reference's line shows what it did at its own moment on the
  same service, so the two decisions sit side by side.
- Links to a moment: `index.html?session=l4-s108&run=<run id>&t=54`, `&a=<action index>` to open
  an action (`&side=ref` for the reference), `&lanes=1`, `&sheet=runbook|results|key`,
  `&intro=1` or `&intro=0`, `&speed=2`, `&still` to switch motion off for screenshots.

### For a screen recording

```
https://incident.katalyst.fyi/?seed=418&autoplay=1&seconds=25&pause=key&zoom=1
```

That plays seed 418 from 12 minutes before the page and stops at minute 28, three minutes after
Fable's unprotected rollback, with admin-portal at 70% errors against 4% for the reference.
`?seed=418&t=28&zoom=1` opens paused on that minute for a still. For Opus on seed 109 the same
moment is `?seed=109&t=37`.

- `seed=109` (with `level=4` if several levels share a seed) opens that episode; `run=<run id>`
  picks another run than the one that opens.
- `autoplay=1` plays at once and skips the intro.
- `seconds=25` plays what is left of the shift in that many seconds; `speed=1.5` sets a multiple
  of the default instead (1x plays the 132 minutes from the start in 33 seconds). `t=0` starts
  at the page instead of 12 minutes before it.
- `pause=key` stops the playback at the key moment (three minutes after the agent's decisive
  call, when its effect shows); `pause=44` stops at that minute. Space resumes.
- `t=44` alone opens paused on that minute, for a still.
- `zoom=1.1` enlarges all type for video compression. On seed 109 at 1920x1080, 1.1 places every
  label clear of the graph; at 1.15 the loyalty-svc caption lands on its neighbours, and at 1.2
  the bar runs out of room. With the scores band shown the graphs are shorter: use `zoom=1`,
  which keeps the labels clear, or add `spread=0`.

## Deploy

```
./deploy.sh
```

Copies the page, the logo, the font, the scores band and the bundles to the Verda machine, into the folder the team's shared
proxy serves as `https://incident.katalyst.fyi/` (`infra/verda/proxy/sites/incident.caddy`). It
replaces the `data/` folder there, copies files only and restarts nothing; the proxy does not
need a reload for new files. It needs SSH access to the machine (`VERDA_HOST`, or a
`junction-runner` entry in `~/.ssh/config`). A change to the site file itself goes out with
`infra/verda/proxy/deploy.sh`.

## Data

A bundle is JSON wrapped in a single assignment, because a page opened from disk may not fetch
files. Shape:

- `sessions[0]`: the episode (`seed`, `level`, `title`) with `cost_null` and `cost_ref`, the
  reference's `runbook` (seven lines) and the level's `headline` (every measured run's score).
- `services[]`: `name`, `tier`, `revenue`, `deps` (`[index, weight]`), the drawing position
  (`row`, `x`; a service no edge reaches has `slot` instead), and from level 4 `retries` (how
  often callers retry it) and `tight` (it runs close to capacity).
- `faults[]` and `decoy`: the hidden truth of the episode.
- `runs[]`: `cost`, `score`, `note`, and per minute from 30 minutes before the page to the end of
  the shift: `err` (`[service, error rate, own share]` in ten-thousandths, failing services only),
  `hot` (services with a CPU alert), `storm` (services over capacity on retries alone), `loss`
  (revenue lost in that minute) and `extra` (replica cost). `faults[].live` are the minutes each
  fault was failing, `throttles[]` what the run rejected up front and when.
- `runs[].actions[]`: the tool, arguments, result, the minutes before and after, for a mitigation
  whether it ended a fault or was wasted, for a throttle the span it was in force. The reference's
  actions carry `rule` (1 to 7) and, where it could be worked out, `why`. A trial's actions carry
  `say` or `think` (what the agent wrote at the time) and, on pinned moments, `label`, `quote` and
  `told`. A trial also has the agent's final `report`.

## Decisions

- **The simulator and the reference are imported, never changed.** The export reads a few of the
  simulator's internals (`_err`, `_own`, `_metrics`, `_fault_sev`, `_replicas`, `_load`, `_state`,
  `throttles`) to get the per-minute truth. Nothing in `sim/` has a hook for the viewer.
- **Why the reference acts is worked out in the exporter**, from the reference's own calls and
  what they returned, with the same arithmetic as `sim/policies.py`: the replicas a rollback's
  retried failures need, fresh traffic against the calm window, the share a storm sheds, the
  word a diff and a symptom share. A reason is kept only when it reproduces the call that was
  made (the replica count, the throttle share, a shared word). Otherwise the action has its
  rule number at most and the page shows the plain action. On eight episodes (levels 3 and 4,
  seeds 1 and 101 to 103) all 54 mitigations and throttles of the reference get a reason this way.
  On seeds 108, 109 and 418, 31 of 34 do: the rollback of a leaking deploy, which the reference finds
  from memory rather than from a log line that matches the diff, shows only its rule.
- **Details are on demand.** The first screen is the two estates, the counters, the line on what
  each run is doing, play and the timeline. The key, the score's definition, each fault's lane,
  the action details, the runbook and the nine-run results each open from one control.
- **The intro is a dialog, once.** It pauses the replay until it is dismissed, so the first thing
  a visitor reads is what they are about to watch. The dismissal is remembered in localStorage
  where the browser allows it.
- **The graph shows the truth, not the agent's view.** A cause is drawn differently from a service
  that fails because of one, and the quiet fault is marked even though its own telemetry is clean.
  What the agent could see is in the action details.
- **Two moments per fault, named the same everywhere.** "Fault removed" is the minute the cause is
  gone; "clear" adds that the retry storm it left has drained and every throttle is lifted.
- **A retry storm is its own state.** A service over capacity that no surge in customer traffic
  explains is in a storm: its outline is broken and circling, its lane is hatched after the cause
  is gone, and its caption says what set it off. A traffic-surge fault counts as live until
  capacity covers the customer traffic, so throttling it does not end it.
- **A throttle is an arc.** The blue arc around a service is as long as the share of requests the
  run turns away; the timeline shows how long it stayed on.
- **Protected or not is read off the action log.** A run of the headline model counts as
  "added capacity first" when a scale above the normal replica count was started on the quiet
  fault's service before its rollback.
- **Readable at 60 services.** Rows follow the longest call path from an edge, ordered to cut
  crossings, with edge services on top and data at the bottom. Only the services the story is
  about are named and ringed in ink. Services no edge reaches sit in their own block without links.
- **Edge services are bars.** Width grows with the square root of revenue (with a floor so the
  name fits); the red fill is the share of requests failing, the number is dollars lost a minute.
- **The counter is the scored cost**, labelled "Lost so far": lost revenue, extra replicas and
  wasted mitigations; hover it for the split. The 30 minutes before the page are shown but not
  charged, as in the simulator.
- **Playback glides, the data does not.** The simulator moves a minute at a time and the bundle is
  per minute. While playing, what changes by degree (the counter, an edge's bar and figures, how
  deep a failing service is coloured, how thick a failing link is, the playhead) moves evenly
  from one minute's value toward the next. Nothing is eased across a minute on which something
  happens in that run (an action starts or lands, a throttle goes on or off, a fault or a storm
  begins or ends): the value holds, and the new one eases in once its minute has come. What a
  service is and every caption change on their minute. Pausing lets the current minute finish
  (in a fifth of a second) and stops on the next whole minute, and scrubbing moves by whole
  minutes, so a paused page shows only the bundle's own numbers. With reduced motion, or
  `&still`, playback steps a minute at a time.
- **Start-up and frame cost.** Until the first picture is drawn the page shows one line, "Loading
  the shift", and it starts playing only after that picture is on screen. Only the episode that
  opens is fetched before the start; the others load behind it. Per frame, the script asks the
  browser for nothing that forces a style or layout pass (the root font size is read once per
  window size, text is measured when the graph is built), and nothing inside the graphs animates
  a transform: a rotating ring made the browser split each drawing into layers on every frame, so
  the ring's dashes travel instead. Under a four times slower CPU this took playback from about
  37 to about 50 frames a second and the start from 1.9 to 1.0 seconds.
- **The timeline is static.** It shows the whole of both runs at once. In the loss chart, what
  both runs lose is pale and what only the agent loses is full red: the red area is the gap.
- **Agent's words** during the run are matched to the receipt by walking the trajectory's tool
  calls in order. Quotes on pinned moments are from the run's closing message (in the bundle as
  its `report`), verbatim apart from a capital at the start and the bold and code markers.
- **Look.** A light page, because it is projected in a lit hall. Two inks: blue-black for what is,
  red for what is lost. Amber marks noise (the decoy), blue marks the run at work. One moving
  thing: failures flowing up the links toward the edge, as thick as the share of calls failing.
  Built with the `impeccable` skill's references; its launcher is not vendored, so there is no
  PRODUCT.md or DESIGN.md.
- **Known limits.** Where several story services sit close together their labels compete for room;
  at laptop width one label can end up over a link or a step away from its mark on a leader line.
  This round's restructuring (sheets, intro, reasons) has not been through an independent design
  review.
- **Font.** Archivo variable (width and weight axes), SIL OFL 1.1, vendored in `fonts/` from
  `@fontsource-variable/archivo@5.2.8`. Nothing loads from a network.
