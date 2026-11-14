// Everything the index page says. index.html draws the page from this block.
//
//   repo     the public repository; "" hides every source link until there is one
//   lede     the opening words; each entry's `short` follows as a link to that entry
//   projects the submitted entries, in the order shown:
//     id      anchor on the page
//     short   the entry in a few words, for the opening sentence
//     name    what the page calls it
//     for     the challenge it answers
//     live    the address the button and the screenshot open
//     open    the button's words
//     more    further links beside the button, as [words, address]
//     source  folder in the repo, joined to `repo`
//     shot    file in shots/ (960 x 600 WebP of the live app)
//     logo    optional local SVG mark shown beside the project name
//     what    what it is; every claim and number is in the file the README's table names
//   also     work that is on the team's table but is not one of its entries
window.KATALYST = {
  repo: "",
  lede: "Three entries at Junction 2026:",
  projects: [
    {
      id: "incident",
      short: "an on-call shift that AI agents lose money on",
      name: "OnCallBench",
      logo: "logos/oncallbench.svg",
      for: "AfterQuery, Break the Agent",
      live: "https://incident.katalyst.fyi/",
      open: "Watch the replay",
      source: "spikes/aq-incident",
      shot: "incident.webp",
      what: "An AI agent is paged into a 120-minute shift on a simulated online shop: 60 services, several faults at once, and every failed request costs revenue. Claude Opus 5.5 finds the causes, then loses on judgment: over nine runs it averages 0.32 of what a scripted expert saves.",
    },
    {
      id: "since-when",
      short: "three Wikipedias compared through time",
      name: "Since When",
      for: "MariaDB, Wikipedia Through Time",
      live: "https://since-when.katalyst.fyi/",
      open: "Open Since When",
      source: "projects/since-when",
      shot: "since-when.webp",
      what: "For one topic, what the Finnish, Swedish and English Wikipedia articles say differently, and the date and the edit each difference began with. Every screen shows the MariaDB statement behind it, and you can run it.",
    },
    {
      id: "kutsu",
      short: "recruitment events that start from the last ones",
      name: "Kutsu",
      for: "City of Espoo, Rethinking Recruitment",
      live: "https://kutsu.katalyst.fyi/",
      open: "Open Kutsu",
      more: [
        ["A company's sign-up", "https://kutsu.katalyst.fyi/#/join/nitor.com"],
        ["A person's sign-up", "https://kutsu.katalyst.fyi/#/me"],
      ],
      source: "projects/kutsu",
      shot: "kutsu.webp",
      what: "Today every Espoo recruitment event starts from scratch, and companies and candidates each wait for the other to sign up. Kutsu keeps what past events taught and hands both an invitation that is already filled in, to agree with or correct.",
    },
  ],
  also: {
    name: "Also on our table: Spread desk",
    what: "A pricing desk for Bahn Express's Spread competition. It runs a simulated car transport company for a week, quoting dealers and paying drivers; every quote is one formula, with no model on the quote path.",
  },
};
