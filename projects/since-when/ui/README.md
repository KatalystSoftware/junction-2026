# Since When UI

The web page of Since When: for one topic, what the Finnish, Swedish and English Wikipedia articles
say differently, the date and the edit each difference began with, and the MariaDB statement behind
each screen, which the viewer can run.

A Svelte 5 single-page app built with Vite and TypeScript. Styles are component-scoped CSS on
Wikimedia's Codex design tokens (`@wikimedia/codex-design-tokens`, CSS variables only). It talks
only to `/api/*`; the contract is [`../docs/api.md`](../docs/api.md).

## Run

Node comes from the repo's dev shell: prefix the commands with `nix develop -c` from the repo root,
or run them inside `nix develop`. From this folder:

```sh
npm install
npm run dev
```

The dev server listens on <http://127.0.0.1:8079> and forwards `/api` to the data service at
`http://127.0.0.1:8077`. Set `SINCE_WHEN_API` to point it at another one.

## Build and check

```sh
npm run check   # svelte-check: types and Svelte diagnostics, no errors or warnings expected
npm run build   # writes the static bundle to dist/
```

`dist/` is plain files. `index.html` refers to its assets relatively, so the bundle can be served
from any path. The app calls the API at the absolute path `/api`, so the server that serves the
bundle must answer `/api/*` on the same origin. Routing is in the fragment (`#/…`), so the server
needs no fallback route.

`serve.py` and `fixtures/` belong to the previous plain-JavaScript page and are replaced in the next
step; they do not serve this app.

## Addresses

```
?q=<search>&lang=<fi|sv|en>&sql=<preset>,<values>#/<wikidata id>/<edition>/<edition>/<findings|timeline>
```

- `#/Q1412941/sv/en/findings` opens the differences of a topic, `…/timeline` when each one opened and
  closed. An address with `compare` or a trailing year opens the findings: the side-by-side view is gone.
- `?sql=asof,Q1412941,2026-10-22,sv` opens the SQL panel with that preset filled in. It never runs
  by itself; the viewer clicks Run. The presets are `nearest`, `asof` and `history`.
- `?q=` opens the topic list with that search. Search runs only when the form is submitted, because
  the first search makes the data service load its embedding model. Do not use it against the demo
  instance, which has no model and not enough memory for one: the request restarts the API container.

## Where things are

- `src/App.svelte`: the top bar, the topic's title and tabs, loading the topic.
- `src/Findings.svelte`, `src/FindingRow.svelte`: the headline difference, the editions' opening
  sentences, the list of differences.
- `src/Timeline.svelte`: each difference with the periods it held and the edit behind every turn.
- `src/SqlPanel.svelte`: the runnable presets and the queries each response reported.
- `src/TopicList.svelte`: the topic picker.
- `src/lib/`: the API types and fetch, the address state, the headline rule (`headline.ts`), text
  marking and sentence cutting (`text.ts`), dates and links (`format.ts`).

## Rules the page keeps

- Quotes are shown word for word. Text is shortened only at sentence boundaries, and the rest is
  one click away.
- A classifier's summary is labelled as a machine suggestion, and the page never says what an
  article should say.
- The page sends the API a preset name and its values, never SQL.
- The "Fixture data" badge appears when a response carries `"fixture": true`.
