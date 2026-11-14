# Since When UI

The web page of Since When: for one topic, the few places where the Finnish, Swedish and English
Wikipedia articles say different things, each with the editions' own words side by side, the date
and the edit it began with, and the MariaDB statement that shows the text on that date, which the
viewer can run.

A Svelte 5 single-page app built with Vite and TypeScript. The controls are Wikimedia Codex's
CSS-only components on native HTML elements (see [Controls](#controls)); layout is
component-scoped CSS on the Codex design tokens (`@wikimedia/codex-design-tokens`, CSS variables
only). It talks only to `/api/*`; the contract is [`../docs/api.md`](../docs/api.md).

## Run

Node comes from the repo's dev shell: prefix the commands with `nix develop -c` from the repo root,
or run them inside `nix develop`. From this folder:

```sh
npm install
npm run dev
```

The dev server listens on <http://127.0.0.1:8079> and forwards `/api` to the server at
`http://127.0.0.1:8078`. Set `SINCE_WHEN_API` to point it at another one.

## Build and check

```sh
npm run check   # svelte-check: types and Svelte diagnostics, no errors or warnings expected
npm run build   # writes the static bundle to dist/
```

`dist/` is plain files. `index.html` refers to its assets relatively, so the bundle can be served
from any path. The app calls the API at the absolute path `/api`, so the server that serves the
bundle must answer `/api/*` on the same origin. Routing is in the fragment (`#/…`), so the server
needs no fallback route.

`python -m gapfinder serve` is that server: it serves `dist/` next to the API, and the Docker image
builds the bundle in a Node stage. `fixtures/` holds the answers it gives when started with
`SINCE_WHEN_FIXTURES=1`, for working on the app without a database.

## Addresses

```
?q=<search>&lang=<fi|sv|en>&sql=<preset>,<values>#/<wikidata id>
```

- `#/Q1412941` opens a topic's page. There is one page per topic. Older addresses that name two
  editions and a view (`#/Q1412941/sv/en/findings`, `…/timeline`, `…/compare/2020`) open the same
  page and are rewritten to the short form.
- `?sql=asof,Q1412941,2026-10-22,sv` opens the SQL panel with that preset filled in. It never runs
  by itself; the viewer clicks Run. The presets are `nearest`, `asof` and `history`. "Check in
  MariaDB" on a difference opens the same panel with `asof` filled in for the day after the edit
  that began the difference, in the edition that was edited.
- `?q=` opens the topic list with that search. Search runs only when the form is submitted, because
  the first search makes the server load its embedding model. A server with no model on disk answers
  503 and the app hides the search box, as on the demo instance.

## Where things are

- `src/App.svelte`: the top bar, the topic's title, loading the topic and the edits behind its
  differences (the API's timeline, asked once for each edition), the articles' links.
- `src/Differences.svelte`: the list of differences, then what one edition says and another leaves
  out, collapsed for each edition.
- `src/Difference.svelte`: one difference: its sentence and date; opened, each edition's quote with
  the differing words marked, the edit that began it and the periods it held.
- `src/SqlPanel.svelte`: one statement at a time, in a dialog: the statement, its values, Run, the
  rows. The three presets can be run; the queries each response reported can be read.
- `src/TopicList.svelte`: the topic picker, in a dialog.
- `src/main.ts`, `src/app.css`: the Codex stylesheets the app imports, and the base styles.
- `src/lib/differences.ts`: how the API's rows become the page's differences (next section).
- `src/lib/`: the API types and fetch, the address state, text marking and sentence cutting
  (`text.ts`), dates and links (`format.ts`), statement colouring and the preview of a preset's
  statement (`sql.ts`).

## What the page lists

The API returns one row for each pair of editions and each pair of passages. The page shows one
line for each claim (`src/lib/differences.ts`):

- **A difference** is made of the open rows where both editions say something and the two differ
  (the API's `framing`, `numbers` and `contradiction`). Rows are one difference when they are of the
  same type and name the same loaded word, quote the same words of an edition (the same quote, or
  one inside the other and most of it), or single out the same figures between the same two
  editions. It shows one quote for each edition, up to three.
- **Its sentence** is the classifier's summary with "the Swedish passage" turned into "Swedish
  Wikipedia". When a third edition's quote comes from another row, that row's clause is added. For
  a loaded word the lexicon found, the sentence is built from the rows: who uses the word and who
  does not.
- **Its date** is that of the row about the articles' opening lines if there is one, dated to one
  edit if possible, the oldest first. An edit made in one edition dates that edition's quote.
- **The order**: a conflicting account whose quotes are not short and sharing a name or a figure
  goes last; then three editions before two; the claim seen in more rows; the opening lines before
  the body; wording, figures, conflicting accounts; the longest-standing first. Seven are listed
  before "Show all", and the first is open.
- **Marked words** are the API's loaded words (matched from the start of a word, so "fascist" marks
  "fascistisk") and, in a difference about figures, the figures that are not in every quote.
- **Left out**: the other open rows (`missing_fact`, `coverage`) are counted once for each quoted
  statement and listed under the edition that says it, closed until asked for.

Every count on the page is the number of items in the list it heads.

## Controls

A control is a native element with the markup and classes Codex documents under "CSS-only version"
on the component's page at <https://doc.wikimedia.org/codex/latest/>. `@wikimedia/codex` is a dev
dependency for its stylesheets alone: `src/main.ts` imports one stylesheet for each component in
use, and none of Codex's Vue code is in the bundle. A new kind of control needs its stylesheet
imported there.

| Control | Codex component |
| --- | --- |
| Buttons | Button: default, progressive quiet for text buttons, progressive primary for Run |
| Filter chips (`aria-pressed`) | Button, with one rule in `app.css` for the switched-on state |
| The statement picker, selects, the date input, the topic search | Select, TextInput, SearchInput; Field and Label in the SQL form |
| Errors (`role="alert"`) | Message of the error type |
| Result rows | Table |
| `<details>` | Accordion |

Codex documents no CSS-only version of two things, and those stay native:

- A toggle button. A filter chip is a Codex button with `aria-pressed`.
- A dialog. The SQL panel and the topic list are native `<dialog>` elements opened with
  `showModal()`, so the browser keeps focus inside, closes on Escape and returns focus to the
  button that opened it. A click on the backdrop closes them.

## Rules the page keeps

- Quotes are shown word for word, as the API stores them, each linking to the revision it was
  taken from.
- The list is labelled as a language model's suggestion, and the page never says what an article
  should say. What one edition leaves out is labelled as not checked against the whole article.
- The page sends the API a preset name and its values, never SQL. The statement shown before Run is
  a copy of the server's template for reading; after Run the panel shows the text the server reports.
- Nothing in the SQL panel runs until Run is clicked.
- The first screen of a topic at 1280×720 holds 110 words or fewer.
- The "Fixture data" badge appears when a response carries `"fixture": true`.
