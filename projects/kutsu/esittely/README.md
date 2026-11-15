# Kutsu, the invitee's pages: hand-picked introductions for Espoo recruitment events

Prototype for the City of Espoo challenge **"Rethinking Recruitment"** at Junction 2026.

**Live prototype:** https://kutsu.duckymcduck2.workers.dev/ is Kutsu, the one app (events, who to invite, applications; the Svelte app one folder up, in `projects/kutsu`). The pages in this folder are the first version of the invitee's side, kept under https://kutsu.duckymcduck2.workers.dev/apply/ ; they were first called Esittely, and the product has one name now, Kutsu. The pitch deck (`../pitch/`) is at https://kutsu.duckymcduck2.workers.dev/pitch/ ; a seven-slide short version, with its spoken script, is in [`../pitch/short/`](../pitch/short/pitch.md) and goes to /pitch/short/ with the next deploy. `tools/deploy.sh` publishes all three (the old address esittely.duckymcduck2.workers.dev keeps working).

**Principle: the AI pulls the information, and humans make the judgements.** Kutsu is a light layer on top of event registration:
- Companies confirm, in about a minute, who they want to meet. Their stand is then promoted to those attendees.
- Candidates answer a few concrete questions and get a short list of stands worth visiting.
- City organisers hand-pick introductions. Technical needs are translated into plain language, and every overlap and gap is linked to its source.
- Nothing scores or ranks people.

## Deliverables

- One-page concept: [`app/docs/concept.md`](app/docs/concept.md)
- Working prototype on synthetic data: [`app/`](app/), live at the link above
- 3-minute demo script: [`app/docs/demo.md`](app/docs/demo.md)
- Responsible-AI note (data, human checkpoints, bias safeguards, EU AI Act and GDPR): [`app/docs/responsible.md`](app/docs/responsible.md)
- Assumptions to check with the Espoo mentors: [`app/docs/mentors.md`](app/docs/mentors.md)

## What's in the prototype

**Working:**
- **Navigation**: the top bar links to the five phases in order (For companies, For job seekers, For organisers, Event day, Day after); `#/event` shows both sides the same planned conversations.
- **Organiser view** (`#/org`): plain-language needs with ESCO links; overlaps, gaps, checks and conversation starters with sources; organiser-chosen filters and sort; names hidden until a decision; a decision with a required reason; decision log and CSV export; aggregate fairness check.
- **One-minute employer confirmation** (`#/company/puro`): a draft from the public job ad, with each field's source line highlighted; "Is Finnish truly required?" with counts per answer; live anonymous count with numbers under 5 suppressed; what-if counts for each must-have; a "try another job ad" extractor that runs in the browser.
- **Applicant joining** (`#/join`): consented scan of the applicant's own sources (LinkedIn, CV, GitHub, portfolio; synthetic documents, and a judge can paste their own CV text), every gathered line shown with its source and confirmed, corrected or removed by the applicant, lines left out on purpose (school names, other languages), the three trade-offs and free text in their own words; the organiser then sees "checked by candidate" and the own words.
- **Demo controls**: a dropdown in the top bar jumps to each state of the demo (company draft or confirmed, applicant consent / check / confirmed, organiser list / review queue / introduced / fairness flag, event day, day after, reset).
- **Organiser review queue** (`#/org/<company>/review`): one candidate at a time against the company's needs, Introduce / Maybe later / Not this time with a required reason, skip, auto-advance, a live "still to decide" count, and a summary with the fairness check.
- **Candidate questionnaire by hand** (`#/cand`): a 6-step questionnaire on the same dimensions as the employer form; live "why answer" feedback from the pool; stand recommendations with reasons, with every stand still open; "How organisers see you" with logged corrections.

**Mock-ups:** work-sample review (`#/cand/evidence`) and the post-event relevance screen (`#/after`).

## Run

```
cd app && python3 -m http.server 8765    # open http://127.0.0.1:8765/
```

There is no build step and no backend. State is kept in the browser's localStorage, and **Reset demo** clears it.

## Test

```
node tools/test_logic.js
```

These are plain-node tests of the extractor, the live counts, the sources on facts and the recommendations. They need no dependencies.

The optional browser walk of the demo path, which needs `playwright-core` and a Chrome or Chromium:

```
CHROME=/path/to/chrome node tools/e2e.js
```

## Data

- `python3 tools/gen_data.py` regenerates the synthetic data (seed 2026: 360 candidates, 12 fictional companies).
- `python3 tools/esco_fetch.py` refreshes the ESCO skill links from the public ESCO API.

All companies, job ads and people are fictional.
