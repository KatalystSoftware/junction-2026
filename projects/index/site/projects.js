// Everything the index page says. index.html draws the page from this block.
//
//   repo     the public repository; "" hides every source link until there is one
//   lede     the line under the team's name
//   projects the submitted entries, in the order shown; the header lists them too
//     id      anchor on the page
//     name    what the page calls it
//     short   the promise in one line: in the header's list, and under the entry's name
//     logo    optional local SVG mark shown beside the name
//     for     the challenges it answers, as [partner, challenge]
//     live    the address the button and the screenshot open
//     open    the button's words
//     more    further links beside the button, as [words, address]
//     result  optional figures shown as a row, as [figure, what it is]
//     what    how it works; every claim and number is in the file the README's table names
//     source  folder in the repo, joined to `repo`
//     shot    file in shots/ (960 x 600 WebP of the live app)
//   also     work that is on the team's table but is not one of its entries
window.KATALYST = {
  repo: "",
  lede: "Three entries at Junction 2026, each with a live demo.",
  projects: [
    {
      id: "oncallbench",
      name: "OnCallBench",
      short: "An on-call shift that AI agents still lose money on.",
      logo: "logos/oncallbench.svg",
      for: [["AfterQuery", "Break the Agent"]],
      live: "https://incident.katalyst.fyi/",
      open: "Watch the replay",
      result: [
        ["0.45", "Claude Opus 5.5, mean of 48 runs on 24 unseen seeds"],
        ["1.00", "an expert script; doing nothing scores 0"],
        ["21%", "of Opus runs end worse than doing nothing"],
      ],
      what: "An AI agent is paged into a 120-minute shift on a simulated online shop: 60 services, several faults at once, and every failed request costs revenue. Claude Opus 5.5 finds the causes, then loses on judgment.",
      source: "projects/oncallbench",
      shot: "incident.webp",
    },
    {
      id: "since-when",
      name: "Since When",
      short: "What three Wikipedias say differently, and since when.",
      for: [["MariaDB", "Wikipedia Through Time"]],
      live: "https://since-when.katalyst.fyi/",
      open: "Open Since When",
      what: "For a topic, what the Finnish, Swedish and English articles say differently, and the edit each difference began with: every revision for three topics, one version a year for the other 2,916. MariaDB 11.8 system-versioned tables keep every version, and one statement pairs passages across editions by vector search as they stood on a past date. The SQL button shows the statement behind each screen and runs it.",
      source: "projects/since-when",
      shot: "since-when.webp",
    },
    {
      id: "kutsu",
      name: "Kutsu",
      short: "Recruitment event invitations that arrive filled in.",
      for: [["City of Espoo", "Rethinking Recruitment"], ["Context.dev", "Fully Structured Web"]],
      live: "https://kutsu.katalyst.fyi/#/join/nitor.com/deep-tech-talent-forum",
      open: "See a company's invitation",
      more: [
        ["Espoo's screen", "https://kutsu.katalyst.fyi/"],
        ["A person's sign-up", "https://kutsu.katalyst.fyi/#/me"],
      ],
      what: "Today each Espoo recruitment event starts with a new survey for companies and another for candidates, and each side waits for the other to sign up. Kutsu keeps who came and what employers said they need, and sends both an invitation already filled in, to agree with or correct. Context.dev supplies each company's details, brand colours and careers page.",
      source: "projects/kutsu",
      shot: "kutsu.webp",
    },
  ],
  also: {
    name: "Also built: Spread desk.",
    what: "A pricing desk for Bahn Express's Spread competition. It runs a simulated car transport company for a week, quoting dealers and paying drivers; every quote is one formula, with no model on the quote path.",
  },
};
