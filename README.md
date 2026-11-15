# Team Katalyst at Junction 2026

What team Katalyst built at Junction 2026 (13-15 November 2026, Espoo): three entries, each running
live.

All our projects, with a link to try each: <https://katalyst.fyi/>. All the videos: [one Drive folder](https://drive.google.com/drive/folders/1ZvjuwvxUiQuxcSLc5QU5W5LgKgM31Kpz).

## Our entries

Each entry's README says what it is, how to run it with one command, and how to test it.

### <img src="projects/index/site/logos/oncallbench.svg" width="32" height="32" alt=""> [OnCallBench](projects/oncallbench/README.md): an on-call shift that AI agents still lose money on

For AfterQuery's **Break the Agent**. ▶ [Video, 1:24](https://drive.google.com/file/d/1LLFac0BTz1-NQPbWwD01wSXNc8atQUeQ/view) · [Step through the shift yourself](https://incident.katalyst.fyi/) · [Source](projects/oncallbench/README.md)

[![OnCallBench replay: Claude Opus 5.5 rolls back geo-svc and sets off a retry storm; partner-api fails 55% of requests](https://storage.googleapis.com/katalyst-fyi-models/shots/oncallbench.gif)](https://incident.katalyst.fyi/?seed=200019&t=32&pause=key&zoom=1.1)

An AI agent is paged into a 120-minute shift on a simulated online shop: 60 services, several faults
at once, and every failed request costs revenue. Claude Opus 5.5 finds the causes, then loses on
judgment: it rolls back a busy service without making room first, and the retries flood it. Opus 5.5
averages 0.45 on 24 fresh seeds: all 48 runs below the expert, and 10 cost more than doing nothing,
every one through an unprotected rollback. Scored by replaying the agent's action log; one command per
shift reruns the reference, both baselines and the agent. Gemma 4 26B-A4B, which we trained on it,
went from 0.05 to 0.44: [statistically indistinguishable from Opus](projects/oncallbench/README.md#a-smaller-model-learns-from-it).

### <img src="projects/index/site/logos/since-when.svg" width="32" height="32" alt=""> [Since When](projects/since-when/README.md): what three Wikipedias say differently, and since when

For MariaDB's **Wikipedia Through Time**. ▶ [Video, 1:16](https://drive.google.com/file/d/1K0Nr7LWR8XBzMgtPlUPCEZ1KFA06I424/view) · [Open Since When](https://since-when.katalyst.fyi/#/Q1412941) · [Source](projects/since-when/README.md)

[![Since When: the Lapua Movement, called fascist in the first sentence of Swedish Wikipedia since 23 October 2026 and of English Wikipedia since 30 May 2022, not in Finnish](https://storage.googleapis.com/katalyst-fyi-models/shots/since-when.gif)](https://since-when.katalyst.fyi/#/Q1412941)

Swedish Wikipedia began calling the Lapua Movement “fascist” on 23 October 2026, English in 2022;
the Finnish first sentence still does not. For a topic, what the Finnish, Swedish and English articles say differently, and the edit each
difference began with. MariaDB 11.8 system-versioned tables keep every loaded version, and one
statement pairs passages across editions by vector search as they stood on a past date. Every screen
shows the SQL behind it, and you can run it.

### <img src="projects/index/site/logos/kutsu.svg" width="32" height="32" alt=""> [Kutsu](projects/kutsu/README.md): recruitment event invitations that arrive filled in

For the City of Espoo's **Rethinking Recruitment** and Context.dev's **The Web Is Your Real-Time
Database**.
▶ Videos: [for Espoo, 0:41](https://drive.google.com/file/d/1cdSGMa33-0_t015rzm84aLsCupmzFP6o/view) · [for Context.dev, 0:43](https://drive.google.com/file/d/1AHWZPTAmzVQuI-QcckK_smcDKy68OEuO/view) · [A company's invitation](https://kutsu.katalyst.fyi/#/join/nitor.com/deep-tech-talent-forum) · [Espoo's screen](https://kutsu.katalyst.fyi/) · [Source](projects/kutsu/README.md)

[![Kutsu: Nitor's invitation to an Espoo recruitment event, filled in from public sources, asking whom else it wants to meet](https://storage.googleapis.com/katalyst-fyi-models/shots/kutsu.gif)](https://kutsu.katalyst.fyi/#/join/nitor.com/deep-tech-talent-forum)

Each Espoo recruitment event starts with a new survey for companies and another for candidates, and
each side waits for the other. Kutsu keeps who came and what employers said they need, and sends an
invitation already filled in, every line linked to the sentence it came from, to agree with or
correct. Context.dev fills in each company's sign-up from the live web, and its monitors on 74
employers tell Espoo what changed. People are sample data, and a person makes every decision. Its first invitee pages are in
[`projects/kutsu/esittely/`](projects/kutsu/esittely/README.md), its pitch decks in [`projects/kutsu/pitch/`](projects/kutsu/pitch/).

## What we built on

| Partner tech | What it does here | Entry |
| --- | --- | --- |
| **Verda** | The server behind every live demo and the agent evaluations; GPUs rented through the API to train Gemma and Qwen; the container serving Nemotron. Machines defined with Verda's official OpenTofu provider ([how we used Verda](infra/verda/README.md)) | All |
| **Gemma** | Gemma 4 26B-A4B, post-trained by us on OnCallBench: 0.05 → 0.44, level with Opus 5.5 | OnCallBench |
| **Modal** | Gemma's evaluations, audit and RL on H200s; the post-trained Gemma served live from Modal | OnCallBench |
| **Gemini** | Gemini 3.1 Pro, one of the two frontier models each level was made harder against | OnCallBench |
| **NVIDIA Nemotron** | Nemotron 3.5 Super VL names what each pair of passages says differently, then checks every claim against the whole other article | Since When |
| **MariaDB** | 11.8 system-versioned tables and vector search: the nearest passage in another edition, as both stood on a past date, in one statement | Since When |
| **Context.dev** | Brand search and retrieve fill in each company's sign-up; web scrape reads careers pages; 116 monitors watch 74 employers | Kutsu |
| **OpenAI Codex** | Fresh GPT 6.1 Sol reviewers checked each round of the environment and of the page | OnCallBench, Since When |
| **CRACI** | Our CI runs on CRACI runners, including a job that downloads, verifies and runs the published Gemma adapter | All |

## Also here

- [`projects/index/`](projects/index/README.md): the page at <https://katalyst.fyi/>.
- [`infra/verda/`](infra/verda/main.tf): the Verda machines the demos and evaluations run on, defined
  with Verda's official OpenTofu provider, and the [proxy](infra/verda/proxy/README.md) every demo
  sits behind; [how we used Verda](infra/verda/README.md).

This repository holds the projects we submitted, with their history. Our notes, experiments and other
work from the event stay in the team's private repository.

## Working in it

The tools come from Nix: `direnv allow`, or `nix develop`. Each project's README has its own run and test
commands; anything that needs the team's API keys says so and has a no-key path.
