# Espoo companies: who is hiring, from their own job posts

Spike for the City of Espoo "Rethinking Recruitment" challenge. The claim it tests: Espoo can stop
chasing companies for forms. We find who is hiring from the companies' own public job posts and draft
their profile; the company only confirms.

**Result (round 11, Sat 14 Nov 06:43): 46 companies hiring for 208 tech roles, 182 of them located in
Espoo, and nobody filled in a form.** Every stored fact carries the URL it came from and, where it was
read from a page, a verbatim quote that `validate.py` finds in the stored copy of that page.

## Run and test

From the repo root, inside the project's nix shell:

```sh
sops exec-env secrets/secrets.yaml 'python3 spikes/espoo-companies/pipeline.py --limit 1081'   # run
python3 spikes/espoo-companies/validate.py                                                      # test
```

The run crawls (or re-reads from `cache/`) all 1,081 seed companies, reads each posting once with Claude
Haiku 5.5 and writes `work/*.raw.json`. A re-run over the cache takes about four minutes and costs only
the postings that are new. `validate.py` exits non-zero when any quote is not a verbatim substring of its
source; `validate.py --apply` drops such fields and writes `companies.json` and `roles.json`. Then
`python3 metrics.py <round>` appends a line to `metrics.jsonl` and `python3 esittely.py` rebuilds
`esittely-companies.json`. `seeds.py` rebuilds the seed list. `LOOP.md` is the round-by-round log.

### Talent brief: public-image signals for any company

From this folder:

```sh
npm --prefix ui ci && npm --prefix ui run build                                            # the page (Svelte), into ui/dist
sops exec-env ../../secrets/secrets.yaml 'python3 serve.py'                                # app with live research, http://127.0.0.1:8046
sops exec-env ../../secrets/secrets.yaml 'python3 signals.py 2639822-1 Varjo wolt.com'     # research from the command line
npm --prefix ui run check                                                                  # type-check the page
```

There are two screens. The company's sign-up (`#/join/<id>`, or `#/join` to find yourself) is an
invitation to an event that is already filled in: who they are, what we would tell talent about them,
and who they want to meet, each to tick or correct, ending on their finished card with a job posting
drafted per role. Espoo's screen (`#/<id>`) lists employers by how fresh their funding and growth news
is, shows the draft and its sources, and hands out the invitation link. `PRODUCT.md` says who it is
for and `NEXT.md` what the Espoo mentors said; `ui/` is the Svelte app; `serve.py` serves it and keeps
sign-up state in `reviews.json`.

An argument is a company id from `companies.json`, or the name or domain of any company. Typing a
company that is not in our data takes about 20 seconds; anything asked before answers at once.
`serve.py` without `sops exec-env` still shows every stored brief.

It is live at <http://31.22.104.106:8046> on the Verda runner (plain http: ports 80 and 443 there
belong to the gap finder). `sops exec-env ../../secrets/secrets.yaml ./deploy.sh` puts the current code
and cache there and restarts it. Live searches for companies not asked before are capped at 300 per
restart, four at a time, because each one spends our credits.

Which API does what, and why:

- **Context.dev `brand/retrieve`** opens every brief. By domain it gives the name, slogan, logo, brand
  colour, industry, size and careers link shown in the header; by name (with Finland as the country
  hint) it also finds the domain, which is what lets someone type any company. The domain then scopes
  the web searches, so namesakes stay out. 10 credits.
- **Context.dev `web/scrape`** (markdown) reads the careers page from that record, script-rendered
  ones included, as one more page to quote from: what the company tells candidates itself. 1 credit.
- **Exa `search`** with page text, four queries: news, funding and growth, interviews and talks, and
  the company's own site. Social networks are excluded because posts there are people speaking.
- **Claude Haiku 5.5**, three calls: one writes the statements, one lists the people named so those
  statements can be dropped, and one writes the card from the statements that passed: a one-line
  pitch and at most four needs, each a short title, one reason, a few skills and a level. A fourth
  drafts a job posting when a company asks for one.

Four Exa searches, two or three Context.dev requests and three Haiku calls per company, about $0.03
and 11 to 13 credits. Every request and its raw response
is stored in `api-cache/`, which is in git, so a rerun is free for everyone and needs no keys. The
cache holds third-party article text with people's names in it: delete it (and its history) before
this repository is made public. Signals whose quote is not in the cited search result, or that name a
person, are dropped. Names are found by a second model call and a pattern, which is not a guarantee,
so read new output before showing it.

All 46 hiring companies are done: 399 signals kept (20 of them from careers pages), 69 dropped,
$1.29 on Exa, $0.17 on Anthropic and 506 Context.dev credits. Varjo is in `signals.json` as the
example of a company from outside our data.

## Files

| file | what |
|---|---|
| `companies.json` | 1,009 companies: registry identity (PRH), website, careers page, job system, what they do |
| `roles.json` | 208 open tech roles: title, location, workplace, language requirement, seniority, contract, working time, role family, must-have and nice-to-have items with skill ids |
| `esittely-companies.json` | the same roles in the company and job-ad shape of `projects/espoo-recruitment/app/data.js` (role family ids and skill ids are the demo's own); `size`, `stand`, `tradeoffs` and minimum experience are left out because nothing public grounds them |
| `signals.json`, `signals.md` | per company: identity from Context.dev, what public sources state (claim, verbatim quote, URL) and, kept apart, our inferred talent outlook citing those signals |
| `ui/`, `serve.py` | the talent brief app (Svelte) and the small server behind it: live research, progress, review state |
| `presets.json` | named lists of employers shown first, such as the Deep Tech Talent Forum's |
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
