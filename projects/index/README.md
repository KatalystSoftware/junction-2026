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
`site/logos/oncallbench.svg`, copied from `projects/oncallbench/replay/logo.svg` (its favicon), and Kutsu
`site/logos/kutsu.svg`, the same file as `projects/kutsu/ui/public/favicon.svg` (its mark, "meet halfway"),
and Since When `site/logos/since-when.svg`, the same file as `projects/since-when/ui/public/favicon.svg`
(its mark, "Since when?": the question mark's dot starts a bar on a time strip).

## The Spread pitch

[`site/spread/index.html`](site/spread/index.html), at <https://spread.katalyst.fyi/>, is the Spread desk's
jury deck: one self-contained page in the site's typeface on the deck's own dark colours, five slides by default. `#7`, `#9`
or `#10` in the address opens a longer cut; the arrow keys step through it, and Print or Save as PDF gives
one 16:9 slide a page. The "See the pitch" link under "Also built" points at it.

It ships with the rest of `site/` (`./deploy.sh`). The proxy serves it on its own name through
[`infra/verda/proxy/sites/spread.caddy`](../../infra/verda/proxy/sites/spread.caddy), which reads the same
folder, and sends the first address, `katalyst.fyi/spread/`, there.

## Where each claim comes from

The page says nothing the repo does not. When one of these files changes, change the entry with it.

| Entry | Source |
| --- | --- |
| OnCallBench | [`projects/oncallbench/README.md`](../oncallbench/README.md): 120 minutes and 60 services under "What the agent has to do"; "finds the causes, then loses on judgment"; 0.45 (shown as 45%), 21% worse than doing nothing and the 2% solve rate (a run solves at 0.95 of the expert) in the "Common seeds" table (Opus 5.5, 48 runs on seeds 200000-200023), which the replay's header also shows |
| Since When | [`projects/since-when/README.md`](../since-when/README.md): the first two paragraphs, and the loading table (2,919 topics; every revision for three, one version a year for the rest); Lapua Movement is `#/Q1412941` |
| Kutsu | [`projects/kutsu/README.md`](../kutsu/README.md): the first paragraphs (new surveys each time; who came and what employers said they need), the two sign-up flows, and the Context.dev table (brand record, careers page), and "What is real, what is sample" (statements quoted from the page they link to; the pool is sample data), and "About a person" (only what they hand over; the sign-up submits nothing) |
| Spread desk | [`spread/README.md`](../../spread/README.md), "How the desk decides" |
| Spread pitch | [`spread/README.md`](../../spread/README.md) holds €12,376, 0.4 ms, the 94,000-order late fit, 441 against 332 orders at €41.6 and €41.4, and merge 1's +€2,180. The fee ladder's +€604, the first version's +€949, the CRACI run (1,442 stand-in weeks in 4 min 41 s; 1 h 53 min from idea to joint search) and the estimates for merges 2 to 4.1 come from the team's submission text and candidate comparison, which are not in the repo; the slide marks the merges as estimates |

The screenshots are cropped to one readable moment: the replay at minute 42 of seed 200019
(`?session=l4-s200019&t=42&intro=0&still`: the rollback at minute 33 and what it has cost by 42), Since When's first card at 520 px wide, and Kutsu's
invitation for IQM (`#/join/2912625-6/deep-tech-talent-forum`, the company the Kutsu video uses) at 1280 × 800; all taken at twice the pixel density.

Source links are off: `repo` in `projects.js` is empty because this repository is private. Set it to
the public copy's address once `scripts/publish-public.sh` has pushed one, and every entry gets a
"Source" link to its folder.

The typeface is Archivo, under the SIL Open Font License ([`site/fonts/OFL.txt`](site/fonts/OFL.txt)).
