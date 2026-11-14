// The projects on the index page, in the order shown. index.html draws the page from this block.
//
//   name    what the page calls it
//   for     the challenge it answers
//   live    the address the button opens; "" shows `note` instead
//   open    the button's words; "Open <name>" when left out
//   source  folder in the repo, joined to `repo`
//   shot    file in shots/ (960 x 600 WebP from the live app); "" for none
//   what    what it is, in a sentence or two taken from the project's README
window.KATALYST = {
  repo: "https://github.com/KatalystSoftware/junction2026",
  projects: [
    {
      name: "Since When",
      for: "MariaDB, Wikipedia Through Time",
      live: "https://since-when.katalyst.fyi/",
      source: "projects/since-when",
      shot: "since-when.webp",
      what: "What the Finnish, Swedish and English Wikipedia articles on a topic say differently, and the date and edit each difference began with.",
    },
    {
      name: "On-call incident response",
      for: "AfterQuery, Break the Agent",
      live: "https://incident.katalyst.fyi/",
      open: "Watch the replay",
      source: "spikes/aq-incident",
      shot: "incident.webp",
      what: "A simulated 120-minute on-call shift that AI agents handle worse than a scripted expert. The replay puts an agent's shift next to the expert's: each action, what the agent saw and what it wrote.",
    },
    {
      name: "Esittely",
      for: "City of Espoo, Rethinking Recruitment",
      live: "https://esittely.duckymcduck2.workers.dev/",
      source: "projects/espoo-recruitment",
      shot: "esittely.webp",
      what: "Organisers hand-pick the introductions at a recruitment event from what companies and candidates said. Nothing scores or ranks people.",
    },
    {
      name: "Kutsu",
      for: "City of Espoo, Rethinking Recruitment",
      live: "",
      source: "projects/kutsu",
      shot: "kutsu.webp",
      what: "Finds a company worth inviting and sends it an event sign-up that is already filled in.",
      note: "Not on a secure address yet.",
    },
    {
      name: "Spread desk",
      for: "Bahn Express, Spread",
      live: "",
      source: "spread",
      shot: "",
      what: "A pricing bot that runs a simulated car transport company for a week in a live competition.",
      note: "Nothing public to open.",
    },
  ],
};
