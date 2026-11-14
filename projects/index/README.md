# Index page

The page at <https://katalyst.fyi/>: one address for submissions, judges and peer voters, with a short
introduction to each of team Katalyst's Junction 2026 projects and a link to try it. Plain HTML, CSS and
JavaScript in [`site/`](site/), with no build step.

Run (the page opens straight from disk):

    xdg-open site/index.html        # macOS: open site/index.html

Test, after a deploy: every address in [`site/projects.js`](site/projects.js) must answer.

    grep -o 'live: "http[^"]*"' site/projects.js | cut -d'"' -f2 | xargs -n1 curl -s -o /dev/null -w '%{http_code} %{url}\n'

## Deploy

    ./deploy.sh

It copies `site/` to `/srv/katalyst/proxy/static/index` on the Verda machine and restarts nothing. The
shared proxy serves that folder on the bare domain, and sends `www` there, through
[`infra/verda/proxy/sites/index.caddy`](../../infra/verda/proxy/sites/index.caddy); that file changes
only when the address does, and is applied with `infra/verda/proxy/deploy.sh`.

## Add or change a project

Everything the page says about the projects is the one block in [`site/projects.js`](site/projects.js):
a group per challenge, an entry per tool. The comment at its top names the fields.

- **A new name or address:** edit `name` or `live` on its entry.
- **A demo goes public:** set `live`. The entry gets its button and a row in the list at the top of the
  page, and its `note` is no longer shown. An empty `live` shows the `note` and the source link only.
- **A new project:** copy an entry. Two tools becoming one submission: delete one entry and edit the
  other. The page states no count and no decision about which tools are submitted together.
- **A screenshot:** 1280 × 800 of the live app, scaled to 960 × 600 WebP, in `site/shots/`:

      chromium --headless --hide-scrollbars --window-size=1280,800 --screenshot=shot.png <address>
      cwebp -q 78 -resize 960 600 shot.png -o site/shots/<name>.webp

  Both tools come from nixpkgs (`nix shell nixpkgs#chromium nixpkgs#libwebp`).

Then run `./deploy.sh`.

## Where each claim comes from

The page says nothing the repo does not. When one of these files changes, change the entry with it.

| Entry | Source |
| --- | --- |
| Since When | [`projects/since-when/README.md`](../since-when/README.md), first paragraphs |
| Edition Ledger | [`projects/mariadb-wikipedia/README.md`](../mariadb-wikipedia/README.md) and [`ui/README.md`](../../ui/README.md) |
| On-call incident response | [`spikes/aq-incident/README.md`](../../spikes/aq-incident/README.md); the scores (0.57, 0.26, 0.00 and their run counts) are the status of round 4, level 4, in [`LOOP.md`](../../spikes/aq-incident/LOOP.md) |
| Esittely | [`projects/espoo-recruitment/README.md`](../espoo-recruitment/README.md); 360 candidates and 12 companies are under "Data" |
| Kutsu | [`projects/kutsu/README.md`](../kutsu/README.md); 46, 208 and 182 are its "Result (round 11)" |
| Spread desk | [`spread/README.md`](../../spread/README.md): 0.4 ms under "How the desk decides", €1,401.25, 68 orders and 97.1% in the "Test final" row of its results |
| The team | the root [`README.md`](../../README.md) |

The source links on the page point at this repository, which is private at the time of writing: they
open for the team and answer 404 for everyone else until the repository is public.

The typeface is Archivo, under the SIL Open Font License ([`site/fonts/OFL.txt`](site/fonts/OFL.txt)).
