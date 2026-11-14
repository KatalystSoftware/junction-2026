# Kutsu: the next event starts from the last ones

Kutsu is Finnish for invitation. It is for the people at the City of Espoo who organise and market
its recruitment events ("Rethinking Recruitment" challenge, Junction 2026).

Today every event starts from scratch, with a new survey for companies and another for candidates.
Each side waits for the other: companies ask which candidates will be there, and candidates sign up
once they know which companies come. Kutsu keeps what past events taught (who came, and what
employers said they need) and uses it to answer both before either has signed up:

- **Events** (`#/`): the event being prepared, suggested next events, and past events. A suggestion
  is a field of work where employers have said in public that they need people and the pool of past
  attendees already has them.
- **One event** (`#/event/<slug>`): the employers to invite, each with the news that makes now the
  moment, and the people to invite, as counts. It also writes the sentence each invitation can open
  with: how many such people there are, and which employers have said what they look for.
- **The company's sign-up** (`#/join/<id>`): an invitation in the company's own logo and colours that
  is already filled in. Who it is, what we would tell candidates about it, who it wants to meet, and
  on each role how many people in the pool do that work. The company agrees, corrects, and is in.

Live: <https://kutsu.katalyst.fyi/> (Espoo's screen) and <https://kutsu.katalyst.fyi/#/join/nitor.com>
(what a company sees). The candidate's side of the same idea is the team's other project, Esittely
(`../espoo-recruitment/`). `PRODUCT.md` says who Kutsu is for, `NEXT.md` what the Espoo mentors said
and what is open.

## Run and test

From this folder, inside the repo's dev shell (`nix develop`):

```sh
npm --prefix ui ci && npm --prefix ui run build                                            # the page (Svelte), into ui/dist
sops exec-env ../../secrets/secrets.yaml 'python3 serve.py'                                # run: http://127.0.0.1:8046
npm --prefix ui run check && npm --prefix ui run walk                                      # test: see below
sops exec-env ../../secrets/secrets.yaml 'python3 signals.py 2639822-1 Varjo wolt.com'     # research companies from the command line
python3 pool.py                                                                            # regenerate the sample pool
```

`serve.py` without `sops exec-env` still shows every stored company; only new searches need keys.

The test has two parts. `check` type-checks the page and fails on any warning; `deploy.sh` runs it
first and stops there if it fails. `walk` needs `serve.py` running: it opens every screen in a
headless Chromium, signs one company up by pressing Enter until the finished page, and fails on any
error the page reports. `npm --prefix ui run lint` is ESLint with typescript-eslint's strict
type-checked rules; it still reports 83 findings and is not part of the check yet.

The **Demo** button at the top right belongs to the demo, not the product. It moves between the
three people Kutsu is for (Espoo's organiser, an invited company, a candidate), fills in example
sign-ups so the screens can be seen in use, and clears every sign-up. An example sign-up is marked
as one wherever it shows: no company did it.

## What is real, what is sample, what is proposed

- **Real:** every employer, and every statement about one. Each statement was found word for word on
  the public page it links to, and statements that name a person are dropped.
- **Sample:** the pool of people. `pool.py` draws 1,140 people from a fixed seed and keeps only
  counts per field (`pool.json`); nobody in it is real, how many of them came to each past event is
  made up, and the screens mark these numbers as sample data. No screen shows a row for a person, and a count under five is shown as
  "fewer than 5".
- **Real past events:** TalentMatch (11 Oct 2022, 24 employers), Espoo TalentMatch (28 Mar 2025,
  Otaniemi), Finland TalentMatch x Tech and IT (4–5 Nov 2025, online, with five other cities) and
  Työnantajatreffit (8 Oct 2026). Each links to its public page, and the only figure shown for one is
  the figure that page gives. Espoo publishes no attendance numbers.
- **Real about the event:** the Deep Tech Talent Forum's dates, that it is online and free, its list
  of employers, the presentation times and that places are limited, all from Espoo's event page.
- **Drafted until confirmed:** the roles an employer looks for are drafted from its public
  statements. Counts of employers say how many have confirmed ("9 employers, 2 confirmed").
- **One profile, many events:** a company confirms its profile once. An invitation and a sign-up are
  for one event (`#/join/<company>/<event>`), and "Copy invitation" puts a short message on the
  clipboard, with the link, for a person to send.
- **Already coming:** the Deep Tech Talent Forum's 27 employers are the ones on Espoo's event page,
  so the screen does not invite them; it sends each its profile to confirm.
- **Proposed by us:** that Espoo keeps a pool across events at all, the suggested events, and on the
  company's finished page that its profile is shown to matching candidates and that its booth is
  built from the page. These describe what the product would do; Espoo has promised none of them.

## How it works

Espoo's screen opens on its events. The upcoming event shows how far its invitations are and every
employer's logo. Suggested events are computed in the page from the drafted roles of every employer
and the pool: a field is suggested when at least three employers ask for it and the pool has people
in it, and fields whose employers have funding or growth news from the last year come first. One
employer (`#/<id>`) shows its draft and sources, and hands out the invitation link; a person sends
it, as Espoo's account managers do today.

The company's sign-up shows one card at a time in the centre: who they are with three short things
we would tell candidates, then each drafted role, then "anyone else?", which drafts a whole role
from one line or a suggestion. Enter accepts, Backspace removes a role, Z takes that back, the left
arrow goes back. What they accept moves to the side and stays in view, who they are on the left and
who they want to meet on the right, and any line there opens again in the centre. It ends on the
company's finished page. `ui/` is the Svelte app; `serve.py` serves it and keeps sign-up state in
`reviews.json`.

A company is named by its id in `companies.json`, or by any name or domain. One that is not in our
data takes about 20 seconds; anything asked before answers at once.

It runs on the Verda runner as a systemd service on port 8046; the team's shared proxy serves it as
`https://kutsu.katalyst.fyi/` (`infra/verda/proxy/sites/kutsu.caddy`).
`sops exec-env ../../secrets/secrets.yaml ./deploy.sh` builds the page, puts the current code and cache
there and restarts it. Live searches for companies not asked before are capped at 300 per restart,
four at a time, because each one spends our credits.

## Context.dev endpoints: what each gives Kutsu and where you see it

Context.dev is the first call for every company and it decides how the whole sign-up looks. Three
endpoints are in the core flow, and monitors keep the picture current afterwards. All of these are
live in the demo; nothing below is only described.

| Endpoint | Why Kutsu calls it | Where a viewer sees it |
|---|---|---|
| `GET /v1/brand/search` | A person types "nitor" or "hamina wireless". This turns the words into the right company and its domain (Finnish matches first; a match must carry the first word typed). | The company's proper name appears within a second or two of pressing Enter, on `#/join` and in Espoo's search box. |
| `POST /v1/brand/retrieve` (by domain) | The company's identity: name, logo, square icon, brand colours, field, size, city, careers link. The domain it confirms also scopes every web search that follows, so namesakes stay out. | Everything branded: the invitation floods with the company's colour from its logo; "Is this you?" is this record, line by line; the square icons in Espoo's list; the logo on the finished card. |
| `POST /v1/web/scrape` (markdown) | Reads the company's careers page, script-rendered ones included, as one more page to quote from: what the company tells candidates itself. | Statements and needs that cite the company's own careers page, with the quoted sentence on hover. |
| `POST /v1/monitors` (page target, with instructions) | Watches each company's careers page for a job opening added or removed. 42 of the 74 companies have a careers link. 1 credit a run. | "Changed lately" on Espoo's events screen, and "Changed since the draft" on an employer. |
| `POST /v1/monitors` (search target) | Watches the web for news that a company is growing: funding, an acquisition, a new site, a hiring plan. One per company, 74. 2 credits a run. | The same two places. |
| `GET /v1/monitors`, `GET /v1/monitors/changes` | Reads back what is watched and what changed, at most every five minutes. | The line "Watching 42 careers pages and news about 74 employers, next at 20:34". |

Monitors (`monitors.py`): 116 of them, every six hours, tagged `kutsu`. One run of all costs 190
credits, 760 a day; `python3 monitors.py delete` removes them and should be run after the event. The
page polls instead of taking webhooks, so there is no public endpoint to protect. A change whose
title or summary names a person is dropped, as everywhere else. Not used: the LinkedIn profile read
for a candidate's prefill was tested once (`web/scrape` returns a public profile, 1 credit) and is
not built.

How it is used: every response is checked before use (`status` on the brand record, `success` on the
scrape output), and stored in `api-cache/` so no call is paid twice, as their brief advises. We keep
their default freshness instead of `maxAgeMs: 0`: for a live "type any company" moment a brand record
that is at most three months old in two seconds beats a fresh crawl in thirty. The plate shows the
record's SVG logo when it has one, because the first raster "logo" in a record can be a customer's
logo from the company's page (Cisco's on hamina.com).

## The other services

- **Exa `search`** with page text, four queries: news, funding and growth, interviews and talks, and
  the company's own site. Social networks are excluded because posts there are people speaking.
- **Claude Haiku 5.5**, three calls: one writes the statements, one lists the people named so those
  statements can be dropped, and one writes the card from the statements that passed: a one-line
  pitch, up to five things to tell candidates and at most four needs. A fourth drafts a whole role
  from one line when a company adds one.

What a need asks for, and where each value comes from:

| Field | What it is | From |
|---|---|---|
| Can do | two or three tasks the person must be able to do, written as work that can be shown | drafted from the statements and an open role's must-haves |
| Knows | up to five tools, methods or fields; no soft skills or traits of character | drafted |
| Level | early career, experienced, senior or lead | drafted |
| Working language | English is enough, or Finnish needed | the job post, with its sentence; otherwise the company |
| Where | on site, hybrid or remote, and the place | the job post, with its sentence; otherwise the company |
| Hiring from abroad | yes, or only people already in Finland | always the company: no post says it |

Four Exa searches, two or three Context.dev requests and three Haiku calls per company, about $0.03
and 11 to 13 credits. Every request and its raw response is stored in `api-cache/`, which is in git,
so a rerun is free for everyone and needs no keys. The cache holds third-party article text with
people's names in it: delete it (and its history) before this repository is made public. A statement
is kept only when its quote is found word for word in the page it cites and it names no person. Names
are found by a model call and a pattern, which is not a guarantee, so read new output before showing
it.

## Where the Espoo company list comes from

The 46 companies under "Hiring in Espoo" come from an overnight run that tested one claim: Espoo can
stop chasing companies for forms, because who is hiring can be read from the companies' own public job
posts.

**Result (round 11, Sat 14 Nov 06:43): 46 companies hiring for 208 tech roles, 182 of them located in
Espoo, and nobody filled in a form.** Every stored fact carries the URL it came from and, where it was
read from a page, a verbatim quote that `validate.py` finds in the stored copy of that page.

```sh
sops exec-env ../../secrets/secrets.yaml 'python3 pipeline.py --limit 1081'   # crawl and read; needs cache/ from the run, or re-crawls
python3 validate.py                                                           # every quote against its source; needs cache/ too
```

The run crawls (or re-reads from `cache/`) all 1,081 seed companies, reads each posting once with Claude
Haiku 5.5 and writes `work/*.raw.json`. A re-run over the cache takes about four minutes and costs only
the postings that are new. `validate.py` exits non-zero when any quote is not a verbatim substring of its
source; `validate.py --apply` drops such fields and writes `companies.json` and `roles.json`. Then
`python3 metrics.py <round>` appends a line to `metrics.jsonl` and `python3 esittely.py` rebuilds
`esittely-companies.json`. `seeds.py` rebuilds the seed list. `LOOP.md` is the round-by-round log. The
sections from "Headline numbers" on describe that run.

## Files

| file | what |
|---|---|
| `companies.json` | 1,009 companies: registry identity (PRH), website, careers page, job system, what they do |
| `roles.json` | 208 open tech roles: title, location, workplace, language requirement, seniority, contract, working time, role family, must-have and nice-to-have items with skill ids |
| `esittely-companies.json` | the same roles in the company and job-ad shape of `projects/espoo-recruitment/app/data.js` (role family ids and skill ids are the demo's own); `size`, `stand`, `tradeoffs` and minimum experience are left out because nothing public grounds them |
| `signals.json`, `signals.md` | per company: identity from Context.dev, what public sources state (claim, verbatim quote, URL) and, kept apart, the inferred card: a pitch and the needs, citing those statements |
| `ui/`, `serve.py` | the Kutsu app (Svelte) and the small server behind it: live research, progress, sign-up state, a role drafted from one line |
| `monitors.py` | creates, lists and deletes the Context.dev monitors, and reads back what changed |
| `presets.json` | named lists of employers shown first, such as the Deep Tech Talent Forum's |
| `pool.py`, `pool.json` | the sample pool: people who came to past events, as counts per field of work; seeded, nobody real |
| `metrics.jsonl` | one line per round |
| `LOOP.md` | what each round ran, decisions, spot-check tables, research notes |

## Headline numbers

| | |
|---|---|
| companies checked | 1,081 (123 hand-picked tech employers, the rest from the PRH register: Espoo, tech industry classes, website on record); 1,006 are registered in Espoo |
| website reachable | 844 (78%) |
| with a careers page or public job feed | 278 (26% of all, 33% of reachable sites) |
| with a job system we recognise | 124; 68 of them expose a public feed |
| careers pages with no open posting we could read | 161 of 278 |
| companies with open tech roles | 46 |
| open tech roles | 208, 182 located in Espoo (the rest are capital-region or remote roles of companies in Espoo) |
| English is enough | 97 roles: 47% of all, 80% of the 121 roles that state a language requirement. Finnish required 23, another language 1, not stated 84 |
| workplace | hybrid 146, remote 21, on-site 15, not stated 26 |
| fields | 12,487 kept, 278 "not stated", 28 dropped by the validator |
| postings read by the model | 837 in the last run (2,376 calls over all rounds) |

One company dominates: ICEYE has 60 of the 208 roles. Without ICEYE the count is 148 roles at 45
companies. Next are IQM 14, Qt 12, Nokia 11, Tieto 10, Gofore 8, AddSearch 6, VTT 6.

Role families: embedded 66, backend 30, devops 21, erp 12, security 11, data 9, product 9, ml 7, qa 6,
frontend 4, support 2, design 1, game 1, mobile 1, none 28. The demo's family list has no hardware
family, so `embedded` also holds RF, electronics and other hardware roles.

Why candidates were dropped (837 read): not a job posting 179, not a tech role 136, elsewhere in
Finland 96, outside Finland 92, posted on another company's job board 18, no location and company not in Espoo 19, title not tech 2.

## Per source

| how the posting was found | companies | roles |
|---|---|---|
| job-system feed (JSON, RSS or REST the vendor publishes) | 68 | 130 |
| JSON-LD `JobPosting` on the posting page | 28 | 36 |
| text of the company's own careers or posting page | 47 | 42 |
| nothing found | 938 | 0 |

## Per job system

| job system | companies using it | roles kept |
|---|---|---|
| Teamtailor | 51 | 38 |
| Ashby | 3 | 60 |
| Oracle Recruiting | 6 | 12 |
| Jobylon | 7 | 9 |
| Personio | 6 | 8 |
| TalentAdore | 10 | 6 |
| Greenhouse | 7 | 6 |
| Workday | 12 | 5 |
| Recruitee | 2 | 5 |
| Lever | 1 | 1 |
| SuccessFactors | 5 | 0 (posting pages disallowed by robots.txt) |
| Laura | 4 | 0 |
| SmartRecruiters | 3 | 0 here (API disallowed; Tieto's 10 roles come from its HTML pages and count below) |
| Workable, ReachMee, Breezy | 2 each | 0 |
| Pinpoint | 1 | 0 |
| none recorded (own pages) | 957 | 58 (includes Qt's 12, behind Greenhouse, and Tieto's 10) |

## Crawling rules and what each portal allowed

Identifiable User-Agent, robots.txt obeyed per host, at most one request per second per host, a cached
URL is never fetched again. No LinkedIn, nothing behind a login, no block bypassed. No recruiter names,
emails or phone numbers are stored (a field whose quote contains one is dropped).

| portal | robots.txt | terms of use | used |
|---|---|---|---|
| The Hub | all allowed except `/startups/joblistwidget/` | "You may not otherwise copy, save or otherwise reproduce, adapt, modify, transfer, assign, use or exploit the contents" without written consent | no |
| Work in Finland | `Allow: /` | use "for other than non-commercial purposes is prohibited without prior written permission"; no copying or storing | no |
| Job Market Finland | `/api/` and `/*/api/` disallowed | silent on crawlers; the official search API needs registration with KEHA-keskus | no |
| Duunitori | `Disallow: /` | not read | never fetched |

Two portals forbid storing or reusing content without written permission, so none was used, not even
for discovery. Every role comes from the company's own site or its job system. With written permission,
Work in Finland's JSON listing (316 Espoo jobs) would be the cheapest discovery source.

Job systems: SmartRecruiters' API and SuccessFactors posting pages are disallowed by robots.txt and were
not fetched. `api.ashbyhq.com/robots.txt` answers 401, which RFC 9309 treats as no restrictions.

## Spot-check precision

Every second round a fresh sub-agent compared 15 random roles with the posting text and judged each
field (correct / judged). Fixes followed each check, so the columns are not the same extractor.

| field | check 1 (r5) | check 2 (r7) | check 3 (r8) | check 4 (r9) | check 5 (r10) |
|---|---|---|---|---|---|
| title | 14/15 | 15/15 | 15/15 | 15/15 | 15/15 |
| location | 13/14 | 6/12 | 9/13 | 13/15 | 13/14 |
| workplace | 6/13 | 13/14 | 8/10 | 14/14 | 14/14 |
| language requirement | 10/11 | 11/14 | 10/10 | 8/10 | 6/6 |
| seniority | 7/7 | 13/14 | 9/9 | 9/9 | 8/9 |
| employment type | 3/5 | 13/13 | 4/4 | 6/6 | 9/9 |
| working time | n/a | 7/12 | 3/3 | 2/9 (see note) | 9/10 |
| role family | 12/15 | 10/15 | 12/15 | 9/13 | 11/14 |
| must-have items | 70/71 | 64/65 | 68/72 | 85/86 | 65/67 |
| nice-to-have items | 44/45 | 39/44 | 44/46 | 46/49 | 35/36 |
| skill id | 68/72 | 38/43 | 54/59 | 45/47 | 45/46 |
| not a tech role after all | 0 of 15 | 2 of 15 | 2 of 15 | 3 of 15 | 1 of 15 |
| personal data | none | none | none | none | none |

What the checks changed: workplace is read from the posting text, not only the feed tag (after 1);
Tieto's locations are read from the page, remote roles abroad are dropped, a second required language
is recorded (after 2); a posting that lists several offices keeps all of them, one spelling per
workplace mode (after 3). Weakest fields: location when a posting lists several places, and role family
for research and management roles. `LOOP.md` has the error lists.

Check 4 note: the seven working-time misses are `FullTime` values from the job system's own
employment-type field, which the reviewer's text copy did not show; the validator finds them in the stored
feed. They are now stored as `full_time`. The three "not tech" roles are borderline (quantum training
specialist, mechanical manufacturing engineer, engineering project manager).

Check 5 found one wrong employer: HeadPower's five roles were a recruiter's postings for its clients
(the careers page links to the recruiter's board). Round 11 drops any posting hosted on another
company's own domain, which removed those five. Still open after check 5: one freelancer pool stored as
a role (Neomore), and the model sometimes turns context into a requirement (the language a platform is
built in, a "such as" example).

## LLM spend

Claude Haiku 5.5 only: 2,376 calls, 15.7 M input and 1.1 M output tokens, **$2.13 of the $10 budget**,
0 errors. About $0.001 per posting; answers are cached by prompt hash, so a re-run costs nothing.

## What did not work

- Three in four companies give nothing: 237 sites unreachable, 568 reachable sites with no careers page,
  161 careers pages with no posting we could read (no open jobs, or a script-rendered list).
- A sub-agent opened 47 of those careers pages by hand: 32 have no open tech role, 6 are script-only
  or down, 9 have postings. Six of the nine are now wired; three list several roles on one page with no
  page per role (STL Europe, Spectacular AI, NerdyNet; 7 roles) and are skipped, because one model
  read of such a page would mix facts from different roles.
- Script-only job lists: Helvar (HiBob), Nixu/DNV (Oracle behind `jobs.dnv.com`), Job Market Finland.
  We do not run a browser.
- Blocked by robots.txt, so skipped: SmartRecruiters API, SuccessFactors posting pages (Metso, Kemira),
  Telia's job endpoint, all of Duunitori.
- Big employers with nothing in scope today: City of Espoo (48 jobs, none tech), Orion (none tech),
  Valmet (100 postings, 1 in the capital region, not tech), Ramboll (39 read) and Granlund (16 read)
  nothing in scope, Rovio (3 positions, none tech), KONE and Trimble (Workday, no candidates), Fortum
  (maintenance page), NTT DATA Business Solutions (503). Tecnotree has only a mailto, Okmetic an empty list.
- Location is the hardest field: feeds name one office while the text lists several; "Finland" alone
  (Aiven's 19 roles) cannot be placed in Espoo and is dropped as "elsewhere in Finland".
- The register (PRH) has no company size, so "larger employers first" is not possible from open data.
- Known listings are hand-wired: 27 employers needed a listing URL found by a research
  sub-agent (`KNOWN` in `pipeline.py`). Fourteen of them bring 121 of the 208 roles.
- Language: 84 of 208 postings never state a language requirement; we report "not stated", we do not
  guess from the posting's language.

## Worth saying in the pitch

1. "We found 46 companies in Espoo hiring for 208 tech roles last night, and nobody filled in a form."
   One overnight run, $2 of model spend, 1,081 companies checked.
2. Every fact is clickable: each field carries its source URL and the exact sentence it was read from,
   and a checker drops anything it cannot find in the source (28 of 12,515 fields). The company
   confirms a draft, it does not start from an empty form.
3. English is enough in 80% of the roles that state a language requirement (97 of 121). That is the
   number international talent in Espoo needs and no form asks for.
4. The public data is uneven, and that is the case for the product: 26% of companies have a careers
   page or feed, 68 expose a machine-readable feed, and those 68 give 63% of the roles. A
   "publish your jobs feed" nudge from the city would cover most of the rest without any form.
5. We stayed inside the rules: robots.txt obeyed, one request per second, no portals whose terms forbid
   reuse, no personal data. The city can run this itself without asking anyone's permission.
