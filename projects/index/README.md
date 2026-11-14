# Index page

The page at <https://katalyst.fyi/>: team Katalyst's Junction 2026 projects, each with a sentence or
two and a link to try it. Plain HTML, CSS and JavaScript in [`site/`](site/), with no build step.

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

The projects are the one list in [`site/projects.js`](site/projects.js); the comment at its top names
the fields. Edit `name` or `live` to rename or move one, copy an entry to add one, delete an entry to
drop one. An empty `live` shows the entry's `note` in place of the button. Then run `./deploy.sh`.

A screenshot is 1280 × 800 of the live app, scaled to 960 × 600 WebP, in `site/shots/`:

    chromium --headless --hide-scrollbars --window-size=1280,800 --screenshot=shot.png <address>
    cwebp -q 78 -resize 960 600 shot.png -o site/shots/<name>.webp

Both tools come from nixpkgs (`nix shell nixpkgs#chromium nixpkgs#libwebp`).

## Where each claim comes from

The page says nothing the repo does not, and quotes no numbers except the 120 minutes of the shift.

| Entry | Source |
| --- | --- |
| Since When | [`projects/since-when/README.md`](../since-when/README.md) |
| On-call incident response | [`spikes/aq-incident/README.md`](../../spikes/aq-incident/README.md) and its [`replay/README.md`](../../spikes/aq-incident/replay/README.md); "worse than a scripted expert" is the round 4 status in [`LOOP.md`](../../spikes/aq-incident/LOOP.md) |
| Kutsu | [`projects/kutsu/README.md`](../kutsu/README.md) |
| Spread desk | [`spread/README.md`](../../spread/README.md) and the [challenge brief](../../docs/challenges/main/bahn-express--spread.md) |

The source links point at this repository, which is private at the time of writing: they answer 404
for everyone outside the team until it is public.

The typeface is Archivo, under the SIL Open Font License ([`site/fonts/OFL.txt`](site/fonts/OFL.txt)).
