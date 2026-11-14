# Esittely: hand-picked introductions for Espoo recruitment events

Prototype for the City of Espoo challenge **"Rethinking Recruitment"** at Junction 2026.

**Live prototype:** https://esittely.duckymcduck2.workers.dev/

**Principle: the AI pulls the information, and humans make the judgements.** Esittely is a light layer on top of event registration:
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
- **Navigation is a horizontal timeline** of one event: 1 Company (3 weeks before), 2 Candidate (2 weeks before), 3 Organiser (1 week before), 4 Event day (`#/event`: both sides see the same planned conversations), 5 Day after. Each tab is one flow.
- **Organiser view** (`#/org`): plain-language needs with ESCO links; overlaps, gaps, checks and conversation starters with sources; organiser-chosen filters and sort; names hidden until a decision; a decision with a required reason; decision log and CSV export; aggregate fairness check.
- **One-minute employer confirmation** (`#/company/puro`): a draft from the public job ad, with each field's source line highlighted; "Is Finnish truly required?" with counts per answer; live anonymous count with numbers under 5 suppressed; what-if counts for each must-have; a "try another job ad" extractor that runs in the browser.
- **Candidate** (`#/cand`): a 6-step questionnaire on the same dimensions as the employer form; live "why answer" feedback from the pool; stand recommendations with reasons, with every stand still open; "How organisers see you" with logged corrections.

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
