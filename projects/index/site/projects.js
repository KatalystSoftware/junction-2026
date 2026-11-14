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
//     result  optional figures shown as a row, as [figure, what it is], with resultNote under them
//     what    what it does, in a sentence or two; every claim and number is in the file the README's table names
//     how     optional technical note, folded under "How it works"
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
      short: "A simulated on-call shift that AI agents still lose money on.",
      logo: "logos/oncallbench.svg",
      for: [["AfterQuery", "Break the Agent"]],
      live: "https://incident.katalyst.fyi/",
      open: "Watch the replay",
      more: [["See what one rollback cost", "https://incident.katalyst.fyi/?session=l4-s200019&t=42&intro=0"]],
      result: [
        ["45%", "of an expert script's savings, on average"],
        ["21%", "of runs cost more than doing nothing"],
        ["2%", "of runs come within 5% of the expert"],
      ],
      resultNote: "Claude Opus 5.5, 48 runs on 24 seeds no one tuned on.",
      what: "An AI agent is paged into a 120-minute shift on a simulated online shop: 60 services, several faults at once, and every failed request costs revenue. Claude Opus 5.5 finds the causes, then loses on judgment.",
      source: "projects/oncallbench",
      shot: "incident.webp",
    },
    {
      id: "since-when",
      name: "Since When",
      short: "What three Wikipedias say differently, and since when.",
      logo: "logos/since-when.svg",
      for: [["MariaDB", "Wikipedia Through Time"]],
      live: "https://since-when.katalyst.fyi/",
      open: "Open Since When",
      more: [["See one difference: Lapua Movement", "https://since-when.katalyst.fyi/#/Q1412941"]],
      what: "Pick a topic and see what the Finnish, Swedish and English articles say differently, and since when: the exact edit for three fully loaded topics, the year for the other 2,916.",
      how: "MariaDB 11.8 system-versioned tables keep every loaded version of every passage, with Wikipedia's own edit times. One statement pairs passages across the editions by vector search, as the articles stood on a past date. The SQL button opens a statement like it, ready to run.",
      source: "projects/since-when",
      shot: "since-when.webp",
    },
    {
      id: "kutsu",
      name: "Kutsu",
      short: "Recruitment event invitations that arrive filled in.",
      logo: "logos/kutsu.svg",
      for: [["City of Espoo", "Rethinking Recruitment"], ["Context.dev", "Fully Structured Web"]],
      live: "https://kutsu.katalyst.fyi/#/join/2912625-6/deep-tech-talent-forum",
      open: "See a company's invitation",
      more: [
        ["Espoo's screen", "https://kutsu.katalyst.fyi/"],
        ["A person's sign-up", "https://kutsu.katalyst.fyi/#/me"],
      ],
      what: "Each Espoo recruitment event starts with new surveys, and companies and candidates each wait for the other to sign up. Kutsu keeps who came and what employers said they need, and drafts each side an invitation already filled in, to agree with or correct. The companies are real; the people in the demo are sample data.",
      how: "Context.dev reads each company's brand record and careers page; each statement about a company links to the public page it was found on, and the company agrees with it or corrects it. About a person, Kutsu reads only what they hand over in their own sign-up, and it submits nothing.",
      source: "projects/kutsu",
      shot: "kutsu.webp",
    },
  ],
  also: {
    name: "Also built: Spread desk.",
    what: "A pricing desk for Bahn Express's Spread competition. It runs a simulated car transport company for a week, quoting dealers and paying drivers; every quote is one formula, with no model on the quote path.",
  },
};
