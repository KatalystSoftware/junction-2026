# Junction 2026

Prep and research for Junction 2026 (13–15 Nov 2026, Hype Areena, Espoo).

This codebase was built and is maintained by AI agents, directed by team Katalyst. The agents write
the code, tests, docs and commits; the team picks the problems, sets direction and reviews the results.

What we are doing right now: [`TODO.md`](TODO.md).

Layout: projects in `projects/<name>/`, experiments in `spikes/`; agent conventions in [`AGENTS.md`](AGENTS.md).

Setup: `direnv allow` (or `nix develop`) for the tools; secrets are sops-encrypted, see [`secrets/`](secrets/README.md).

- [`docs/event/`](docs/event/): participant guidebook (PDF + text extract) and the hackerpacks (credits and tools with claim steps).
- [`docs/partners/`](docs/partners/README.md): partner export and one research note per partner.
- [`docs/challenges/`](docs/challenges/README.md): all challenge briefs, brief-based scoring and ranking.
- [`docs/shortlist/`](docs/shortlist/README.md): the challenges we talked to, with chat notes and in-person scoring.
- [`docs/overnight-loop.md`](docs/overnight-loop.md): how we run unattended develop/test/verify/measure loops, with a brief template.
- [`spread/`](spread/README.md): harness for the Bahn Express "Spread" challenge: scan practice weeks, compare policy variants, find their mistakes.
- [`projects/espoo-recruitment/`](projects/espoo-recruitment/README.md): the first invitee pages of Kutsu (one product name; once called Esittely), the City of Espoo "Rethinking Recruitment" prototype: organisers hand-pick introductions with plain-language overlaps and gaps; no scores. Live: https://kutsu.duckymcduck2.workers.dev/
- [`projects/mariadb-wikipedia/cleanroom/`](projects/mariadb-wikipedia/cleanroom/README.md): clean-room test of [Edition Ledger](projects/mariadb-wikipedia/README.md), the MariaDB "Wikipedia Through Time" entry: an API check against live Wikipedia and four agent testers who see only what a user or judge sees.
