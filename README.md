# Team Katalyst at Junction 2026

What team Katalyst built at Junction 2026 (13-15 November 2026, Espoo). Every project here was
written by AI agents, directed by the team: the agents wrote the code, tests, documentation and
commits; the team chose the problems, set the direction and reviewed the results.

All our projects, with a link to try each: <https://katalyst.fyi/>.

## Our entries

| Entry | Challenge | What it is | Try it |
| --- | --- | --- | --- |
| [OnCallBench](projects/oncallbench/README.md) | AfterQuery, Break the Agent | An environment that puts an AI agent on call for a simulated online shop. A frontier agent finds the causes of the outage and loses on judgment: it rolls back a busy service without making room first, and the retries flood it. Scored by replaying the agent's action log; one command per shift reruns the reference, both baselines and the agent. | <https://incident.katalyst.fyi/> |
| [Since When](projects/since-when/README.md) | MariaDB, Wikipedia Through Time | What Finnish, Swedish and English Wikipedia say differently about a topic, and the edit each difference began with. Built on MariaDB system-versioned tables and vector search; every screen shows the SQL behind it, which you can run. | <https://since-when.katalyst.fyi/> |
| [Kutsu](projects/kutsu/README.md) | City of Espoo, Rethinking Recruitment; Context.dev, The Web Is Your Real-Time Database | Plans the City of Espoo's recruitment events from public data and invites companies with a sign-up that is already filled in, every line linked to the sentence it came from. People are sample data; a person makes every decision. | <https://kutsu.katalyst.fyi/> |

Each entry's README says what it is, how to run it with one command, and how to test it. The first
invitee pages of Kutsu, and its pitch deck, are in [`projects/espoo-recruitment/`](projects/espoo-recruitment/README.md).

## Other work in this repository

- [`projects/mariadb-wikipedia/`](projects/mariadb-wikipedia/README.md), with the root `gapfinder/`,
  `differences/` and `ui/`: Edition Ledger, the MariaDB tool Since When was forked from.
- [`spread/`](spread/README.md), `projects/spread-alloc/` and `projects/spread-factory/`: a car-delivery
  desk and its test harness for the Bahn Express "Spread" challenge.
- [`projects/index/`](projects/index/README.md): the page at <https://katalyst.fyi/>.
- `spikes/`: experiments we tried and did not submit, such as other domains we probed for AfterQuery.
- `infra/`: OpenTofu for the machines and the shared proxy the live demos run on.

## Working in it

The tools come from Nix: `direnv allow`, or `nix develop`. How the agents work in this repository, and
where things go: [`AGENTS.md`](AGENTS.md).
