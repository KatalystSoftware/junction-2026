// Everything the index page says about the projects. index.html draws the page from this block.
//
// One group per challenge, one entry per tool. To merge two tools into one entry, delete one of
// the two and edit the other; to split a group, move an entry into a group of its own.
//
//   name    what the page calls it
//   live    the address the demo button opens; "" shows `note` instead of a button
//   source  folder in the repo, joined to `repo`
//   shot    file in shots/ (960 x 600 WebP from the live app); "" for none
//   what    one sentence a cold visitor reads first
//   detail  one or two more; every number is quoted from the file named in the README's table
window.KATALYST = {
  repo: "https://github.com/KatalystSoftware/junction2026",
  groups: [
    {
      partner: "MariaDB",
      challenge: "Wikipedia Through Time",
      about: "Two tools on the same challenge. Since When started as a fork of Edition Ledger.",
      entries: [
        {
          name: "Since When",
          live: "https://since-when.katalyst.fyi/",
          source: "projects/since-when",
          shot: "since-when.webp",
          what: "Pick a topic and see what the Finnish, Swedish and English Wikipedia articles say differently, with the date and the edit each difference began with.",
          detail: "Every screen shows the MariaDB statement behind it, and you can run it. Built on MariaDB 11.8 system-versioned tables and vector search.",
        },
        {
          name: "Edition Ledger",
          live: "https://gapfinder.katalyst.fyi/",
          source: "projects/mariadb-wikipedia",
          shot: "edition-ledger.webp",
          what: "Finds what the Finnish, Swedish and English Wikipedia articles on a topic say differently, and ranks the articles to improve by how many people read them.",
          detail: "Made for editors: it shows the quotes from both editions and since when each difference has existed, and never suggests what an article should say. First called the gap finder.",
        },
      ],
    },
    {
      partner: "AfterQuery",
      challenge: "Break the Agent",
      about: "",
      entries: [
        {
          name: "On-call incident response",
          live: "",
          source: "spikes/aq-incident",
          shot: "incident.webp",
          what: "A test for AI agents: the agent is paged at the start of a 120-minute on-call shift on a simulated estate of services, and is scored on what the shift cost.",
          detail: "On the hardest level Claude Opus 5.5 averages 0.57 of a scripted expert's score over four runs; Sonnet 5.5 scored 0.26 in one run and Gemini 3.1 Pro 0.00 in two. The replay shows an agent's shift next to the expert's on the same incident.",
          note: "The replay viewer is not on a public address yet.",
        },
      ],
    },
    {
      partner: "City of Espoo",
      challenge: "Rethinking Recruitment",
      about: "Two parts: one for the introductions at the event, one for getting employers to it.",
      entries: [
        {
          name: "Esittely",
          live: "https://esittely.duckymcduck2.workers.dev/",
          source: "projects/espoo-recruitment",
          shot: "esittely.webp",
          what: "A light layer on top of event registration: companies confirm in about a minute who they want to meet, candidates get a short list of stands worth visiting, and city organisers hand-pick the introductions.",
          detail: "Nothing scores or ranks people, and every overlap and gap is linked to its source. The demo runs on synthetic data: 360 candidates and 12 fictional companies.",
        },
        {
          name: "Kutsu",
          live: "",
          source: "projects/kutsu",
          shot: "kutsu.webp",
          what: "Finds a company worth inviting, reads what it has said in public, and sends it an event sign-up that is already filled in, so the company only ticks and corrects.",
          detail: "Kutsu is Finnish for invitation. Every stored fact carries the address it came from. Its eleventh run found 46 companies hiring for 208 tech roles, 182 of them in Espoo.",
          note: "Not on a secure public address yet.",
        },
      ],
    },
    {
      partner: "Bahn Express",
      challenge: "Spread",
      about: "",
      entries: [
        {
          name: "Spread desk",
          live: "",
          source: "spread",
          shot: "",
          what: "A pricing bot for a live competition: it runs a simulated car transport company for a week, quoting dealers a price for each car and setting the fee for the driver who delivers it.",
          detail: "Every quote is one formula with no model on the path, answered in 0.4 ms. In Saturday's test final it earned €1,401.25 on 68 orders, 97.1% of them on time.",
          note: "It plays against other teams on the organisers' server, so there is nothing public to open.",
        },
      ],
    },
  ],
};
