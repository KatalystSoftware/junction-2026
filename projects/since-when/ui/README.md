# Since When UI

The web page of Since When: for one topic, what the Finnish, Swedish and English Wikipedia articles
say differently, the date and the edit each difference began with, and the MariaDB statement behind
each screen, which the viewer can run.

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
?q=<search>&lang=<fi|sv|en>&sql=<preset>,<values>#/<wikidata id>/<edition>/<edition>/<findings|timeline>
```

- `#/Q1412941/sv/en/findings` opens the differences of a topic, `…/timeline` when each one opened and
  closed. An address with `compare` or a trailing year opens the findings: the side-by-side view is gone.
- `?sql=asof,Q1412941,2026-10-22,sv` opens the SQL panel with that preset filled in. It never runs
  by itself; the viewer clicks Run. The presets are `nearest`, `asof` and `history`.
- `?q=` opens the topic list with that search. Search runs only when the form is submitted, because
  the first search makes the server load its embedding model. A server with no model on disk answers
  503 and the app hides the search box, as on the demo instance.

## Where things are

- `src/App.svelte`: the top bar, the topic's title and tabs, loading the topic.
- `src/Findings.svelte`, `src/FindingRow.svelte`: the headline difference, the editions' opening
  sentences, the list of differences.
- `src/Timeline.svelte`: each difference with the periods it held and the edit behind every turn.
- `src/TypeChip.svelte`: the type of a difference ("Framing") as a chip.
- `src/SqlPanel.svelte`: the runnable presets and the queries each response reported, in a dialog.
- `src/TopicList.svelte`: the topic picker, in a dialog.
- `src/main.ts`, `src/app.css`: the Codex stylesheets the app imports, and the base styles.
- `src/lib/`: the API types and fetch, the address state, the headline rule (`headline.ts`), text
  marking and sentence cutting (`text.ts`), dates and links (`format.ts`).

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
| Selects, the date input, the topic search | Select, TextInput, SearchInput; Field and Label in the SQL form |
| Errors (`role="alert"`) | Message of the error type |
| Type of a difference | InfoChip |
| Result rows, article sizes | Table |
| `<details>` | Accordion |

Codex documents no CSS-only version of three things, and those stay native:

- A toggle button. A filter chip is a Codex button with `aria-pressed`.
- Tabs over links. Codex's CSS-only tabs are form buttons with `role="tab"`; Differences and
  Timeline are links to two addresses with `aria-current`, styled in `App.svelte`.
- A dialog. The SQL panel and the topic list are native `<dialog>` elements opened with
  `showModal()`, so the browser keeps focus inside, closes on Escape and returns focus to the
  button that opened it. A click on the backdrop closes them.

## Rules the page keeps

- Quotes are shown word for word. Text is shortened only at sentence boundaries, and the rest is
  one click away.
- A classifier's summary is labelled as a machine suggestion, and the page never says what an
  article should say.
- The page sends the API a preset name and its values, never SQL.
- The "Fixture data" badge appears when a response carries `"fixture": true`.
