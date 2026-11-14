// Everything the index page says. index.html draws the page from this block.
//
//   repo     the public repository; "" hides every source link until there is one
//   lede     the line under the team's name
//   projects the submitted entries, in the order shown; the header lists them too
//     id      anchor on the page
//     name    what the page calls it
//     short   the entry in a few words, for the list in the header
//     logo    optional local SVG mark shown beside the name
//     for     the challenges it answers, as [partner, challenge]
//     what    what it is; every claim and number is in the file the README's table names
//     live    the address the button and the screenshot open
//     open    the button's words
//     more    further links beside the button, as [words, address]
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
      short: "An on-call shift that AI agents still lose money on",
      logo: "logos/oncallbench.svg",
      for: [["AfterQuery", "Break the Agent"]],
      what: "An AI agent is paged into a 120-minute shift on a simulated online shop: 60 services, several faults at once, and every failed request costs revenue. Claude Opus 5.5 finds the causes, then loses on judgment. On 24 seeds no one tuned on it averages 0.45, where an expert script scores 1 and doing nothing 0, and one run in five ends worse than doing nothing.",
      live: "https://incident.katalyst.fyi/",
      open: "Watch the replay",
      source: "projects/oncallbench",
      shot: "incident.webp",
    },
    {
      id: "since-when",
      name: "Since When",
      short: "What three Wikipedias say differently, and since when",
      for: [["MariaDB", "Wikipedia Through Time"]],
      what: "For one topic, what the Finnish, Swedish and English Wikipedia articles say differently, and the date and the edit each difference began with. Every screen shows the MariaDB statement behind it, and you can run it.",
      live: "https://since-when.katalyst.fyi/",
      open: "Open Since When",
      source: "projects/since-when",
      shot: "since-when.webp",
    },
    {
      id: "kutsu",
      name: "Kutsu",
      short: "Recruitment event invitations that arrive filled in",
      for: [["City of Espoo", "Rethinking Recruitment"], ["Context.dev", "Fully Structured Web"]],
      what: "Every Espoo recruitment event starts from scratch, and companies and candidates each wait for the other to sign up. Kutsu keeps what past events taught and sends both an invitation already filled in, to agree with or correct; Context.dev supplies each company's details, brand colours and careers page.",
      live: "https://kutsu.katalyst.fyi/#/join/nitor.com",
      open: "See a company's invitation",
      more: [
        ["Espoo's screen", "https://kutsu.katalyst.fyi/"],
        ["A person's sign-up", "https://kutsu.katalyst.fyi/#/me"],
      ],
      source: "projects/kutsu",
      shot: "kutsu.webp",
    },
  ],
  also: {
    name: "Not one of the three: Spread desk.",
    what: "Our pricing desk in Bahn Express's Spread competition. It runs a simulated car transport company for a week, quoting dealers and paying drivers; every quote is one formula, with no model on the quote path.",
  },
};
