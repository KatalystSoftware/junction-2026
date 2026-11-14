# Loop log

Working notes for whoever (or whichever agent) picks this up next. Newest round last.
Hard stop Sat 14 Nov 08:30 EET; final report starts 07:45.

## How to run a round

Plain `python3` is not on PATH and direnv is blocked in this worktree, so everything goes through
`nix develop <repo root> -c`. Two gitignored wrappers in `work/`:

- `work/py <script> ...`: `nix develop <root> -c python3 ...` (no secrets)
- `work/pys <script> ...`: the same inside `sops exec-env secrets/secrets.yaml`, with
  `SOPS_AGE_SSH_PRIVATE_KEY_FILE=$HOME/.ssh/id_ed25519_verda` (the key path the main checkout's
  `.envrc.local` uses; only the path is referenced)

```sh
(nohup work/pys pipeline.py --limit N > work/run-rK.log 2>&1 &)   # one crawling process at a time
rg -v warning work/run-rK.log | tail -c 400                        # wait for "wrote N companies, M roles"
work/py validate.py --apply                                        # drops fields whose quote is not in the source
work/py metrics.py rK                                              # appends a line to metrics.jsonl
git add spikes/espoo-companies && git commit && git push origin HEAD:spike/espoo-companies
```

- `--limit N` is cumulative over the seed list (123 curated first, then PRH registry order). Pages and
  model answers are cached, so a bigger limit only pays for the new companies.
- `ESPOO_OFFLINE=1 ESPOO_OUT=work/scratch work/py pipeline.py --limit N` re-runs the extractor from cache
  only (safe while a crawl is running). `ESPOO_OFFLINE=1 work/py debug.py <name>` shows one company.
- The rate limit is per process: never run two crawling processes at once.

## Decisions

- PRH gives no company size, so "larger first" is not possible from the data; registry order is kept.
- Links that also appear on the company homepage are navigation, not postings (they cost model calls and
  produced zero roles in round 1), so they are no longer read as posting candidates.
- `finish()` returns a drop reason; `diag.json` counts them per company (`drops`).
- Careers pages are followed one level down into the company's own careers subdomain or a hosted job
  board (`BOARDS` in `pipeline.py`); limits raised to 7 careers pages, 30 posting pages, 60 feed roles.
- New handlers that need no API: TalentAdore posting pages, the Jobylon embed script, Workday (the
  tenant's robots.txt names a sitemap of posting pages; only Finnish or remote places with a tech-looking
  title are opened; each page carries JSON-LD).
- Personio feeds without a description: the posting page is read and cited instead of the feed.
- A language-requirement quote must itself mention a language, otherwise the field is "not stated"
  (found a role marked "English is enough" on a quote about attention to detail). This tightens
  `finish()`; `validate.py` is untouched.
- Role family ids in `llm.FAMILIES` are exactly the keys of `roles` in the demo's `data.js` (checked),
  and skill ids are constrained to `data/skills.json`, so no mapping step is needed.
- `esittely.py` writes one demo-shaped entry per role: the `ad` text is built only from validated quotes
  and laid out for the demo's `extract()`; `size`, `stand`, `tradeoffs` and minimum experience are left
  out because nothing public grounds them.
- Spot-checks read the copy of the posting fetched during the crawl (`spot.py`), because the fixed rule
  says a cached URL is never fetched again; a posting page that only a feed pointed at is fetched once.
- SmartRecruiters' API is `Disallow`ed by its robots.txt, so it is not used.

## Rounds

| round | limit | companies | careers page or feed | hiring | tech roles | English enough | kept / dropped fields | LLM $ |
|---|---|---|---|---|---|---|---|---|
| r1 (previous agent) | 10 | 10 | - | 1 | 14 | - | - | 0.03 |
| r2 | 300 | 300 | 147 | 14 | 48 | 32 | 2741 / 17 | 0.51 |

### r2 notes (04:35)

- Roles by job system: teamtailor 24, personio 9, recruitee 3, none (company's own pages) 12.
- Job systems detected without a feed handler: talentadore 7, workday 8, jobylon 5, successfactors 5,
  oracle 4, laura 3, reachmee 2. These are where roles are lost.
- Careers pages link to their own careers subdomain in 25 companies and to teamtailor in 19; the
  crawler does not follow those yet (teamtailor on a custom domain has its feed at `<host>/jobs.rss`).
- r2 ran with the code from before the navigation filter, so its model spend includes navigation pages.

| r3 (not validated) | 650 | 650 | - | - | 55 raw | - | - | 0.57 |
| r4 | 1081 | 1081 | 276 | 29 | 74 | 44 | 9692 / 24 | 0.75 |
| r5 | 1081 | 1081 | 276 | 32 | 80 | 48 | 9803 / 24 | 0.76 |
| r6 | 1081 | 1081 | 276 | 32 | 90 | 52 | 9987 / 25 | 0.78 |
| r7 | 1081 | 1081 | 277 | 37 | 136 | 65 | 10840 / 25 | 1.34 |
| r8 | 1081 | 1081 | 277 | 38 | 120 (108 in Espoo) | 60 | 10597 / 27 | 1.99 |
| r9 | 1081 | 1081 | 278 | 43 | 204 (183 in Espoo) | 94 | 12458 / 29 | 2.11 |
| r10 | 1081 | 1081 | 278 | 47 | 213 (186 in Espoo) | 98 | 12587 / 29 | 2.13 |
| r11 | 1081 | 1081 | 278 | 46 | 208 (182 in Espoo) | 97 | 12487 / 28 | 2.13 |

### r4 and r5 notes (04:50)

- All 1,081 usable seeds are crawled; from here a round is a re-run over the cache with better discovery
  (about 1.5 minutes plus whatever new pages the new handlers open).
- r4 added board following, TalentAdore and Jobylon; r5 added the Workday sitemap (6 roles).
- 844 sites reachable, 276 with a careers page or feed, 49 with a public feed, 112 with a job system.
- Candidates dropped in r4: "not a job posting" 187, outside Finland 57, elsewhere in Finland 52, not a
  tech role 31, no location and company not in Espoo 18.
- Gaps: 159 companies have a careers page but no posting found. Feeds with Finnish jobs and no
  candidates (title filter?): M-Files (workable, 19), Housemarque, Efecte, Visma Solutions, Yousician.
  Big employers with nothing: Nokia, Fortum, Varjo, Futurice, Metso, Tieto, Orion, Elisa, Espoon
  kaupunki, Bittium, Enfuce (a research sub-agent is looking for listing URLs that plain GET can read).

### r6 notes (04:57)

- Job-system posting URLs (Workday, Jobylon) are now read before link-guessed pages and have their own
  cap of 60, so the 30-page cap no longer cuts them: Workday 6 -> 9 roles.
- Title filter: `driver` alone no longer rejects ("Driver Services" is software); HPC, consultant, R&D,
  sysadmin and "ylläpit" count as tech-looking. Feed titles that the filter skipped are in `diag.json`
  (`feed_titles_skipped`); M-Files, Efecte and Visma really have only sales and customer roles in Finland.
- Not yet in r6 (applied for r7): a Teamtailor career site on the company's own domain is recognised from
  `/jobs/<id>-<slug>` links and `<label>.teamtailor.com/jobs.rss` is tried for the JS widget.

### Spot-check 1 (r5 data, 15 random roles, seed 1; sub-agent read the crawl-time copy of each posting)

| field | correct / judged |
|---|---|
| title | 14 / 15 |
| location | 13 / 14 |
| workplace | 6 / 13 |
| language_requirement | 10 / 11 |
| seniority | 7 / 7 |
| employment_type | 3 / 5 |
| role_family | 12 / 15 |
| must_have items | 70 / 71 |
| nice_to_have items | 44 / 45 |
| skill_id | 68 / 72 |
| not a tech role | 0 of 15 |
| personal data | none |

What was wrong, and the fix planned for r7:

- workplace: "(not stated)" although the body, the benefits or the location string says hybrid, on-site
  or remote (6 roles); only the feed's header tag was read. Fix: the model reads workplace with a quote.
- role_family follows the title or the employer instead of the duties (3). Fix: prompt says duties decide.
- skill_id `sap` used for any ERP or finance system (4 items). Fix: prompt says an id only for the same skill.
- employment_type: "Full-time" in the header was not stored (2). Decision: employment_type stays
  contractual (permanent, fixed term, ...); "Full-time" is already kept in `working_time`, which the
  spot-check now shows.
- One title with a soft hyphen and a stray space; one workplace stored as 'none'. Fix in `finish()`.

## Big-employer listings that a plain GET can read (research sub-agent, robots.txt checked)

- Futurice: `careers.futurice.com/jobs.rss` (Teamtailor on own domain).
- Varjo: `apply.workable.com/api/v1/widget/accounts/659213?details=true`.
- Elisa: `ats.talentadore.com/positions/bdXi6SM/json?v=2&language=fi,en,sv&display_description=job_title&categories=tags_and_extras`.
- Espoon kaupunki: `www.kuntarekry.fi/fi/tyopaikat/?organisation=3&...&limit=100` (`<basic-job-card url title>`), postings have JSON-LD.
- Tieto: `careers.smartrecruiters.com/Tieto2?search=Finland` (HTML, not the API); postings `jobs.smartrecruiters.com/Tieto2/<id>-<slug>`.
- Orion and Nokia: Oracle HCM REST (`.../hcmRestApi/resources/latest/recruitingCEJobRequisitions?...siteNumber=OrionCareers` and
  `fa-evmr-...` `siteNumber=CX_1`); the public posting page is JS-only, so the detail JSON is the source.
- Metso: listing JSON in `metso.com/corporate/careers/open-jobs/`, but posting pages on successfactors.eu are
  disallowed by robots.txt: no posting text. Fortum: maintenance page. Enfuce: JS widget only.

## Portals: robots.txt and terms (sub-agent, 05:15). Decision: not used, not even for discovery

| portal | robots.txt | terms of use | listing a plain GET can read |
|---|---|---|---|
| The Hub | all allowed except `/startups/joblistwidget/` | thehub.io/terms: "You may not otherwise copy, save or otherwise reproduce, adapt, modify, transfer, assign, use or exploit the contents" without written consent; personal, non-commercial viewing only | `thehub.io/jobs?location=Espoo` (server-rendered) |
| Work in Finland | `Allow: /` | workinfinland.com/en/terms-of-use: use "for other than non-commercial purposes is prohibited without prior written permission"; copying or storing forbidden without permission | `/api/jobs/?limit=50&page=1&city=Espoo` (JSON, 316 jobs) |
| Job Market Finland | `/api/` and `/*/api/` disallowed | terms silent on crawlers; the official search API needs registration with KEHA-keskus | none: JS widget fed by the disallowed API |
| Duunitori | `Disallow: /` | not read | never fetched |

None of the terms mentions crawlers, but two forbid storing or reusing content without written
permission, so the portals stay in `DENY` and every role comes from the company's own site or job
system. With written permission, Work in Finland's 316 Espoo jobs would be the cheapest discovery source.

## r7 notes (05:25)

- 136 roles from 37 companies, 88 located in Espoo; English is enough in 65, Finnish required in 33,
  not stated in 36. By source: job-system feed 76, careers page 42, JSON-LD 18. By job system: teamtailor
  40, oracle 12, personio 10, workday 9, greenhouse 7, talentadore 6, recruitee 5, jobylon 2, lever 1,
  ashby 1, none 43 (27 of those are Tieto's SmartRecruiters posting pages, read as plain pages).
- The prompt changed (workplace, duties decide the role family, stricter must-have and skill id), so all
  613 postings were read again: spend went from $0.78 to $1.34.
- `KNOWN` in `pipeline.py` (keyed by seed name) holds the listings from the research sub-agent: Nokia and
  Orion (Oracle HCM REST; `ats.parse_oracle` drops the contact and hiring-manager keys before anything is
  stored), Tieto (SmartRecruiters HTML listing, 27 roles in the capital region or remote, 1 in Espoo),
  Varjo (Workable widget, 1), Futurice (Teamtailor rss, 5), Elisa (TalentAdore, 0: nothing in Espoo and
  Elisa is not registered here), City of Espoo (Kuntarekry: 48 open jobs, none tech-looking).
- Any page that references `ats.talentadore.com/positions/<id>/` now gets its positions JSON read
  (Digia: 3 roles in the capital region).
- Workplace is now read by the model with a quote: stated in 115 of 136 roles (before: mostly absent).
- The title filter no longer overrules the model: a posting the model read as a tech role is kept
  (Nokia's 6G and Wi-Fi standardisation researchers were dropped by it): 127 -> 136 roles.
- Orion: 15 jobs in Finland, 8 read, none is a tech role (lab, production, finance). True result.
- Still nothing: Teamtailor JS widgets with no rss (Innofactor, Bluefors, Granlund, Solteq, Citycon,
  Seaber), Workday tenants without Finnish tech jobs (KONE, Trimble), SuccessFactors (robots), Personio 3,
  Oracle 3 (Hansen, Futuremark, Diebold Nixdorf: site ids unknown), Housemarque (artists only).

## Spot-check 2 (r7 data, 15 random roles, seed 2; sub-agent, 05:32)

| field | correct / judged |
|---|---|
| title | 15 / 15 |
| location | 6 / 12 |
| workplace | 13 / 14 |
| language_requirement | 11 / 14 |
| seniority | 13 / 14 |
| employment_type | 13 / 13 |
| working_time | 7 / 12 |
| role_family | 10 / 15 |
| must_have | 64 / 65 |
| nice_to_have | 39 / 44 |
| skill_id | 38 / 43 |
| not a tech role after all | 2 of 15 (a product consultant, borderline; a course assistant) |
| personal data | none |

What was wrong, and the fix that went into r8:

- location empty or partial: Tieto's SmartRecruiters pages carry the place only in a
  `<spl-job-location formattedAddress=…>` attribute, so 26 of 27 Tieto roles had no location and were
  kept only because Tieto is registered in Espoo. r8 reads the attribute (kept only when the page text
  repeats it), so roles in Jyväskylä, Oulu, Tampere now drop as "elsewhere in Finland".
- remote roles abroad kept for Finnish companies ("Remote Germany Hessen", "Remote, US"): r8 drops a
  location that names another country and not Finland.
- a second required language ignored (German; "English and Finnish" read as english_enough): prompt now
  says Finnish plus English is finnish_required, and a new value `other_language_required`.
- working_time empty though the header says "Full-time" (page-read roles): the model now reads it.
- role_family: research and people-manager roles forced into a family: prompt now says `other`.
- unmarked requirements stored as nice_to_have; loose skill ids: prompt tightened ("when in doubt, none").

## r8 notes (05:50)

- Fewer roles than r7 (136 -> 120) and that is the honest number: the location fixes from spot-check 2 put
  Tieto at 10 roles instead of 27 (17 are elsewhere in Finland). Roles located in Espoo rose 88 -> 108.
- New listings: Qt Group 28 postings read -> 6 roles in Espoo (the listing's links carry `&amp;hsLang`, the
  first pattern missed them), Innofactor 1, Solteq 2, Bluefors 3 (Helsinki), Nokia 11.
- Read and nothing in scope: Ramboll 39 postings (38 not tech, 1 elsewhere), Granlund 16 (8 not tech,
  8 elsewhere), Citycon 0, Nightingale 0, Rejlers 5 links (construction roles).
- Roles by job system: teamtailor 43, oracle 12, talentadore 6, greenhouse 6, workday 5, recruitee 5,
  personio 5, jobylon 2, lever 1, company's own pages 35.
- Language: english_enough 60, finnish_required 21, other_language_required 1, not stated 35.
- Candidates dropped: not a job posting 178, not a tech role 121, elsewhere in Finland 98, outside Finland 73,
  no location and company not in Espoo 19.
- Research sub-agent (24 employers without candidates): Helvar is on HiBob (script only, 403/401); QPR,
  Ubisecure, Custobar, Savox, Sympa, Tiera, Seaber have no open jobs; the Oracle boards of Hansen (26 jobs),
  UL Solutions/Futuremark (447) and Diebold Nixdorf (177) have 0 jobs in Finland; NTT DATA Business
  Solutions (SuccessFactors) answers 503; Telia's data endpoint is blocked by robots.txt; SSH, Ensto,
  Nightingale and Citycon have readable feeds without tech roles. Of 26 Teamtailor companies without
  candidates only 6 lacked a feed (now in KNOWN); the rest have no tech roles in scope.
- Valmet (Workday, wd103): the handler missed the tenant because the careers URL itself is the Workday
  page; its site map has 100 postings, one in the capital region (a service mechanic). The 14 candidates
  it produced were off-site links to finanssivalvonta.fi, all refused by the model.
- Etteplan: the open-positions page loads its list by script, the 19 candidates were service pages.
  A second research sub-agent is looking for a readable listing for Etteplan, Basware, Tecnotree, Nixu,
  Sofigate, ICEYE, Rovio, Gofore and Okmetic (started 05:52).

## Spot-check 3 (r8 data, 15 random roles, seed 3; sub-agent, 05:53)

| field | correct / judged |
|---|---|
| title | 15 / 15 |
| location | 9 / 13 |
| workplace | 8 / 10 |
| language_requirement | 10 / 10 |
| seniority | 9 / 9 |
| employment_type | 4 / 4 |
| working_time | 3 / 3 |
| role_family | 12 / 15 |
| must_have | 68 / 72 |
| nice_to_have | 44 / 46 |
| skill_id | 54 / 59 |
| not a tech role after all | 2 of 15, both borderline (a doctoral researcher in human-centred security, a supply-chain development manager) |
| personal data | none |

What was wrong, and what r9 changes:

- location (4): two Qt and Personio roles say "Espoo" where the posting says "Espoo or Oulu" and "Espoo,
  Tampere": the job system names one office. Fix: when the model's reading holds the same office plus more
  places, the model's reading is kept. Two Frends roles say "Espoo, Finland" (the Teamtailor feed's office)
  while the posting page says "Finland, fully remote": left as is, the feed is the company's own statement
  and the role is also marked remote.
- workplace (2): the Teamtailor tag "fully" stored as the value. Fix: stored as `remote`, quote unchanged.
- role_family (3): one research role given `security`, two left empty (correct for `other`, counted wrong
  by the reviewer's strict reading). Not changed.
- must_have (4): "gives a good foundation" and "at least two of the following" read as hard requirements.
- skill_id (5): loose matches again (llm, security, iam, agile, projectmgmt). Not changed; the demo shows
  the quote next to every skill.
- Language, seniority, employment type and working time: no errors this time (language was 11 / 14 in
  spot-check 2).

## r9 notes (06:08)

- 204 roles at 43 companies (r8: 120 at 38); 183 located in Espoo; English is enough in 94 (46% of all
  roles, 78% of the 121 that state a language; 80 do not state one). Spend $2.11 of $10.
- New known listings (research sub-agent 2, robots.txt checked for each):
  - ICEYE: Ashby feed `api.ashbyhq.com/posting-api/job-board/iceye`, 199 jobs, 95 in Finland, 65 tech
    titles read, 60 roles in Espoo. `api.ashbyhq.com/robots.txt` answers 401 (no robots file), which
    RFC 9309 treats as "no restrictions". `MAX_FEED_ROLES` raised 60 -> 100 for this.
  - Etteplan: the listing is JSON inside the page (`__NEXT_DATA__`), each position with its country;
    Finland positions only, postings on Jobylon: 35 read, 5 tech roles in the capital region (2 Espoo).
  - Basware: own site unreachable for us; the Jobylon company-group embed is the listing (21 postings,
    15 abroad, 2 tech roles in Espoo). A known listing now stands in when the site cannot be read
    (`from_listing`; no `website` field is written then).
  - Gofore: own WordPress careers page, 23 links read, 8 roles (3 Espoo). Sofigate: 6 tech roles, none
    in Espoo and not registered there, so not written. Rovio: 3 open positions, none tech.
  - Not usable: Tecnotree (mailto only), Okmetic (empty list), Nixu/DNV (Oracle pages script-rendered).
- Location: when the job system names one office and the posting text lists that office plus others,
  the model's reading (with its quote) replaces it. Qt went 6 -> 12 roles because of this and the cap.
- Workplace spelling unified: `fully`, `telecommute` -> `remote`; `on-site` -> `onsite`.
- One company dominates: ICEYE has 60 of 204 roles. Without ICEYE: 144 roles at 42 companies.
- Role families: embedded 66, backend 28, devops 21, erp 12, security 11, data 10, product 9, ml 5,
  qa 4, frontend 3, support 3, other small; none 29. Workplace: hybrid 145, remote 20, onsite 17, not stated 22.

## Spot-check 4 (r9 data, 15 random roles, seed 4; sub-agent, 06:14)

| field | correct / judged |
|---|---|
| title | 15/15 |
| location | 13/15 |
| workplace | 14/14 |
| language_requirement | 8/10 |
| seniority | 9/9 |
| employment_type | 6/6 |
| working_time | 2/9 as judged; see below |
| role_family | 9/13 |
| must_have items | 85/86 |
| nice_to_have items | 46/49 |
| skill_id | 45/47 |
| not a tech role after all | 3 of 15 (all borderline: quantum training specialist, mechanical manufacturing engineer, engineering project manager) |
| personal data | none |

Errors:
- working_time: 7 values (`FullTime`, `FULL_TIME`) come from the job system's own employment-type field
  (Ashby feed, JSON-LD), which the reviewer's text copy does not show. The validator finds the quote in the
  stored feed, so the fact is grounded; the reviewer could not see it. Fixed the spelling: feeds' variants
  are stored as `full_time` or `part_time`, anything else (one feed said `Remote`) is not stored.
- role_family: three `embedded` that are mechanical tooling, project management and server infrastructure;
  one `erp` that is data warehousing. The family comes from title keywords; not fixed.
- location: one duplicate `Espoo, Finland; Espoo, Finland` (fixed: duplicates removed); one `Helsinki,
  Stockholm` where the posting says "either our Espoo or Stockholm Office" (model error).
- language_requirement: one `english_enough` where a Nordic language is also required; one `not_stated`
  where the posting asks for excellent English. Five more `not_stated` are English postings that ask for
  no language: we keep "not stated" there on purpose.
- nice_to_have: three items stored as pluses that the posting lists as plain expectations.
- skill_id: `terraform` for "version-controlled configurations", `sap` for Dynamics 365.

## r10 notes (06:35)

- Gap picked: Espoo-registered companies with a careers page and no candidates. 112 of them have no
  job system detected. A research sub-agent opened 47 by hand: 32 have no open tech role, 6 are
  script-only or down (Brightstar Lottery, Information SG, Organon R&D, Softera, Smart Pulse), 9 have
  open tech postings.
- Wired in `KNOWN`: GuideVision (4 postings, all dropped: 3 outside Finland, 1 elsewhere in Finland),
  Taito United (3 roles, all Espoo), Qevo (3 roles), TrueMed (2), KYOCERA Technologies (1, new `page`
  kind: the careers page is the posting). Net +9 roles, +4 companies.
- For hand-checked `links`/`page` listings the job title may be in a later `<h1>`/`<h2>` than the first
  `<h1>`; the first heading that passes `is_tech_title` is taken. Only for `KNOWN` URLs.
- Not wired, on purpose: STL Europe (3), Spectacular AI (2), NerdyNet (2) list several roles on one
  page with no page per role; one model read would mix facts from different roles. GTSoft (1) has no
  job-title heading at all. 8 roles left on the table.
- After spot-check 4: feed employment type is stored as `full_time`/`part_time` whatever the feed's
  spelling (`FullTime`, `FULL_TIME`); a location joined from several offices no longer repeats one.
- Run: 0 new fetches on the re-run (2,511 from cache), 837 postings read, spend $2.1254 (2,376 calls).
- `validate.py`: OK, 12,587 fields kept, 29 dropped in total.

## Spot-check 5 (r10 data, 15 random roles, seed 5; sub-agent, 06:39)

| field | correct / judged |
|---|---|
| title | 15/15 |
| location | 13/14 |
| workplace | 14/14 |
| language requirement | 6/6 |
| seniority | 8/9 |
| employment type | 9/9 |
| working time | 9/10 (6 of the 9 come from the job system's field, not visible in the text) |
| role family | 11/14 |
| must-have items | 65/67 |
| nice-to-have items | 35/36 |
| skill id | 45/46 |
| not a tech role | 1 of 15 (patent specialist, borderline) |
| personal data | none |

Errors:
- HeadPower Oy: its careers page links to a recruiter's board (`rekry.biisoni.fi`); the five roles are
  the recruiter's postings for its clients (S-Pankki, Insta Advance). Wrong employer. Fixed in r11.
- Frends: location `Espoo, Finland` comes from the feed's office tag; the posting says "Finland · Fully
  Remote". Workplace is stored as remote, so the record is grounded but the place is the office.
- Role family: `embedded` is the catch-all for hardware (RF, electronics, manufacturing, a Python
  simulation engineer). The demo's family list has no hardware family; left as is, said in the README.
- Neomore "Join our partner network" is a freelancer pool, stored as a role. Not fixed.
- Context read as a requirement: C# (the platform is built on it), ServiceNow (one of four examples).
- One "QA Engineer or Senior QA Engineer" stored as senior; one working time missed ("Kokoaikainen").

## r11 notes (06:45)

- New drop reason "posted on another company's job board": a kept role whose posting URL is on a
  domain that is neither the company's own (second-level label) nor a job-system vendor's, unless the
  listing is in `KNOWN`. Checked against r10 first: of 24 company/domain pairs only HeadPower was a
  foreign non-vendor domain. It drops HeadPower's 5 roles and 13 Supercell postings that Metacore's
  site links to (those never reached the output: Metacore is not in Espoo).
- No new fetches, no new model calls. Spend stays $2.1254.
- Result: 46 companies, 208 roles (182 in Espoo), 97 English is enough of 121 that state a language.
- `validate.py`: OK, 12,487 fields kept, 28 dropped in total.

## Next

Nothing is running. State at 06:45: r11 committed and pushed, README on r11 numbers.
Not done, in order of roles lost:
1. Multi-role careers pages (STL Europe, Spectacular AI, NerdyNet; 7 roles): split by heading before
   the model read.
2. Script-only job lists (HiBob, Oracle behind a custom domain): need a browser.
3. Prompt: do not promote context or "such as" examples to must-haves; reject talent pools.
