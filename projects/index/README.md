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
drop one. Then run `./deploy.sh`.

A screenshot is 1280 × 800 of the live app, scaled to 960 × 600 WebP, in `site/shots/`:

    chromium --headless --hide-scrollbars --window-size=1280,800 --screenshot=shot.png <address>
    cwebp -q 78 -resize 960 600 shot.png -o site/shots/<name>.webp

Both tools come from nixpkgs (`nix shell nixpkgs#chromium nixpkgs#libwebp`).

An entry can set `logo` to a local asset shown beside its name. OnCallBench uses
`site/logos/oncallbench.svg`, copied from `projects/oncallbench/replay/logo.svg` (its favicon).

## Where each claim comes from

The page says nothing the repo does not. When one of these files changes, change the entry with it.

| Entry | Source |
| --- | --- |
| OnCallBench | [`projects/oncallbench/README.md`](../oncallbench/README.md): 120 minutes and 60 services under "What the agent has to do"; "finds the causes, then loses on judgment"; 0.45 and 21% worse than doing nothing in the "Common seeds" table (Opus 5.5, 48 runs on seeds 200000-200023), which the replay's header also shows |
| Since When | [`projects/since-when/README.md`](../since-when/README.md), first paragraph |
| Kutsu | [`projects/kutsu/README.md`](../kutsu/README.md): the first paragraphs, the two sign-up flows, and the Context.dev table (brand record, careers page) |
| Spread desk | [`spread/README.md`](../../spread/README.md), "How the desk decides" |

The screenshots are cropped to one readable moment: the replay at minute 34 of seed 200019
(`?session=l4-s200019&t=34&intro=0&still`), Since When at 760 × 475, Kutsu's invitation at 1280 × 800.

Source links are off: `repo` in `projects.js` is empty because this repository is private. Set it to
the public copy's address once `scripts/publish-public.sh` has pushed one, and every entry gets a
"Source" link to its folder.

The typeface is Archivo, under the SIL Open Font License ([`site/fonts/OFL.txt`](site/fonts/OFL.txt)).
