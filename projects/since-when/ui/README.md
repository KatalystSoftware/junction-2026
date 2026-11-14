# Gap finder UI

The editor-facing page: candidate differences ranked by readers, one topic's differences as
verbatim quotes from both editions (with section, talk page and citation links), the passages of
two editions side by side as of any 1 January, the timeline of when each difference opened and
closed, and the SQL behind each screen.

It shows evidence and hands over to the wiki; it never suggests what an article should say. The
classifier's one-sentence summary is labelled as a machine suggestion. An editor records one of
four outcomes (edited, raised on talk page, intentional difference, not a real difference) and can
copy an attribution edit summary or a talk page note made only of the two quotes and their links.
When the API refuses to record outcomes (403, 405 or 501, as on a read-only public deployment),
the page keeps them in the browser's local storage and marks them "saved in this browser only".

Addresses are shareable: `?q=…&lang=sv#/<wikidata id>/<edition to review>/<edition compared
with>/<findings|compare|timeline>/<year>`. While the SQL panel is open on an API that can run
statements, `sql=<preset>,<its values>` is in the address too and reopens the panel with them
filled in, e.g. `?sql=asof,Q1412941,2026-10-22,sv`.

```bash
python3 ui/serve.py                                       # fixture data, http://localhost:8078
GAPFINDER_API=http://localhost:8077 python3 ui/serve.py   # proxy /api/* to the real server
```

Plain HTML, CSS and JavaScript with no build step. `serve.py` uses only the Python standard
library. The API contract is `docs/gap-finder/api.md`.

## Fixtures

`fixtures/` answers the API until MariaDB does, with 11 History of Finland topics.

- **Real:** titles, leads and current text (MediaWiki API, 13 Nov 2026), page views
  (Nov 2025 to Oct 2026), article sizes on each 1 January 2005–2026, and the quotes, dates and
  revision IDs behind each Lapua Movement finding.
- **Stand-ins:** the Finnish–English and Finnish–Swedish passage matches for Lapua Movement are
  made by hand from the section contents, and their distances are placeholders. Coverage for the
  other topics and for earlier years is a size ratio. SQL timings are invented.

The page shows a "Fixture data" badge whenever a response carries `"fixture": true`.
