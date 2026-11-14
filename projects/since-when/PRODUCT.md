# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **The reader.** Someone who reads Wikipedia in more than one of Finnish, Swedish and English, or
  edits it. Their job: "Show me the few places where the editions really say different things about
  this topic, let me read the exact words side by side so I can judge for myself, and tell me when
  it started and which edit did it."
- **The judge.** A MariaDB engineer watching a two-minute demo. They need to see that the dates and
  the past texts come from the database, and to run a statement themselves.

## Product Purpose

Since When shows what the Finnish, Swedish and English Wikipedia articles on one topic say
differently, and since when. It is team Katalyst's entry for MariaDB's "Wikipedia Through Time"
challenge at Junction 2026. It works when a first-time viewer can say, from one screen, what
differs, which edition says what, and since when, and can then check the date in MariaDB.

## Positioning

Every date on the page is a row in a MariaDB system-versioned table, and the viewer can run the
statement that reads the article as it stood on that date. Other tools compare today's texts; this
one says when a difference began and links the edit that began it.

## Operating Context

- One page per topic (`#/<wikidata id>`), opened from a topic list or a link in the demo script
  (`demo/WALKTHROUGH.md`).
- The demo runs on a laptop at 1280×720, about two minutes, on three topics: Lapua Movement
  (Q1412941), Finnish War (Q736268), Diet of Porvoo (Q2457646).
- The reader follows links out to Wikipedia: the revision a quote was taken from, and the edit that
  began a difference.

## Capabilities and Constraints

- A **difference** is a place where two or three editions both say something and the words differ:
  a loaded word, a figure, or a conflicting account. A language model suggests them; nobody has
  checked them.
- A **statement left out** is something one edition says that was not found in another. It was
  found by comparing passage with passage and is not checked against the whole other article.
- Each difference carries each edition's quote, the date it began, the edit that began it and
  earlier periods when it also held.
- The SQL panel runs three presets (`asof`, `history`, `nearest`) as a read-only user. The app
  sends a preset name and values, never SQL, and nothing runs until Run is clicked.
- Old addresses keep working: `#/<id>/<lang>/<lang>/findings`, `…/timeline`, every `?sql=` link.
- The API has no short label for a difference, no creation date for an article and no date of the
  last comparison; the page derives what it shows from the rows it gets.

## Brand Commitments

- The look is the Wikipedia skin: Wikimedia Codex design tokens and Codex CSS-only components on
  native elements. No other fonts, palettes or decoration.
- Quotes are shown word for word.
- The page says that a language model suggested the differences and that the one-sided statements
  are unchecked, and never says what an article should say.

## Evidence on Hand

- The running demo instance with the three topics; `demo/WALKTHROUGH.md`, the demo script.
- `docs/api.md`, the API contract; `ui/README.md`, the map of the page's source.
- There are no user studies, testimonials or usage numbers.

## Product Principles

1. **The reader judges.** The page puts the editions' own words in front of the reader and stays
   out of the verdict.
2. **Show time as time.** When something began is drawn on a time scale; the exact date and the
   edit are one click away.
3. **Say it once, by structure.** Position, grouping and marks carry what a sentence would
   otherwise repeat; explanations wait behind a disclosure.
4. **Everything checkable.** Each date leads to the edit on Wikipedia and to the statement in
   MariaDB.
5. **Honest about the machine.** What a model suggested and what is unchecked is marked as such,
   compactly, wherever it appears.

## Accessibility & Inclusion

WCAG 2.1 AA: every control reachable by keyboard with a visible focus ring, text and meaningful
marks at AA contrast, nothing overflowing at 390 px. Quotes carry their language (`lang`).
