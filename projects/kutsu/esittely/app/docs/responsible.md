# Responsible-AI note

**Principle:** the software gathers, translates and lays out information. It never scores, ranks or labels a person as a good or bad fit. A named City of Espoo organiser decides each introduction and writes down why.

## What the software does, and what it never does

| Does | Never does |
|---|---|
| Drafts a company's needs from that company's own public job ad (information about a job, not a person) | Searches the web or social media for people, or scrapes profiles |
| Drafts an applicant's profile from sources the applicant chose and consented to (their LinkedIn, CV, GitHub, portfolio), read once; the applicant confirms, corrects or removes every line before anyone sees it, and the raw files are deleted after drafting | Uses anything the applicant did not confirm, or keeps the raw documents |
| Translates technical terms into plain language and links them to the EU ESCO skills taxonomy | Gives a person a score, a rank, a match percentage or a label |
| Lays out where a candidate's own answers overlap with a company's stated needs, and where they don't, each with its source | Orders people by an AI judgement. The list order is only the sort the organiser chose, such as registration time. |
| Summarises a work sample the candidate chose to share, after which the candidate approves or edits the summary | Infers personal traits, personality, "potential" or "culture fit" |
| Shows companies and candidates aggregate counts computed from the pool | Shows any count under 5 exactly, or shows a list of people to companies before an organiser introduces them |

## Data used, and nothing more

| Data | From | Why | Who sees it | Kept |
|---|---|---|---|---|
| Field, experience band, tools with depth, working languages, practicalities, 3 trade-offs, a few sentences in their own words | Drafted from sources the candidate chose, then confirmed line by line by the candidate (or typed by hand) | To compare with stated needs | The candidate and organisers. Companies only see people introduced to them. | 30 days after the event, unless the candidate opts in to the next one |
| Optional work-sample link and approved summary | Candidate, by choice | To show concrete work | Same as above, and only after the candidate approves it | Same |
| Optional "needs work-permit support" | Candidate, by choice | To point them to companies that offer support, and to let Espoo's international recruitment advisers help the company | The candidate and organisers | Same |
| Name and contact details | The existing registration | To run the event | Organisers, after a decision. The company gets them only when the candidate agrees at the event. | Under the registration tool's own policy |
| Company needs | Public job ad, plus the company's confirmation | To promote the stand and plan introductions | Everyone at the event | Until the event ends |
| Decisions and reasons | Organiser | Accountability | Organisers. Each candidate can ask to see the decisions about them. | 12 months, as an audit record |

**Never collected:** photo, age, gender, nationality, ethnicity, school or university names, CV files, or languages other than the ones the companies work in. The scan skips these lines on purpose and shows the applicant what it left out.

## Human checkpoints

1. **The company confirms its own draft**, and corrects any field. An unconfirmed draft is visibly flagged as unconfirmed everywhere.
2. **The candidate approves** any summary before anyone else sees it, and can correct their description at any time. Corrections are logged, and organisers can see that the candidate checked.
3. **The organiser chooses** the filters and the sort. The criteria in use are always shown on screen.
4. **The organiser decides** every introduction, with a one-line reason that is saved with their name and the time. The decision log can be exported.
5. **Both sides rate** each conversation's relevance after the event. The answers feed only aggregate statistics.

## Bias safeguards

- **Names hidden by default.** The organiser sees what the person can do and reveals the name only after deciding. This counters name-based bias around nationality and gender.
- **No education or nationality data.** A career changer or a self-taught developer is described by what they have done, not by where they studied.
- **The language requirement is challenged.** Companies are asked whether Finnish is truly required. They see how many attendees each answer includes, and they confirm it. A Finnish requirement copied from the job ad is marked "not confirmed".
- **Relevance, not quality.**
  - Every gap is phrased as a difference between a stated need and a stated answer, such as "must-have Kubernetes: not mentioned", never as a judgement of the person.
  - Missing nice-to-haves are not shown as gaps.
  - Having no portfolio is never shown at all.
- **Work-permit needs are framed as a practical check with help offered**, never as a reason by itself to skip someone.
- **Fairness check.**
  - For each company it compares, in aggregate only, the share of candidates without working Finnish, career changers and people needing permit support among those who asked to meet the company, against those the organisers introduced.
  - A gap of 15 percentage points or more prompts a second look.
- **Nobody is blocked.** Recommendations only guide candidates. Any candidate can visit any stand, and can ask to be introduced to any company.

## The EU AI Act and GDPR in a real deployment

- **Where recruitment AI sits in the Act.** AI used in recruitment is listed in Annex III, point 4(a), as high-risk. That covers placing targeted job ads, analysing and filtering applications, and evaluating candidates.
- **The honest position.**
  - **Close to the line:** promoting a company's stand to attendees whose answers fit, and recommending stands to candidates, comes close to "targeted job advertisements".
  - **What reduces the risk:**
    - These are simple, visible rules over answers the people gave themselves, for an event they chose to attend.
    - Every stand stays visible to everyone, nobody is filtered out, and no decision about a person is made by the system.
    - The decisions that matter, the introductions, are made by a named organiser with a written reason.
  - **Other tasks are narrow or preparatory** (AI Act Art. 6(3)(a) and (d)): drafting from a public job ad, translating terms, and laying out a candidate's own stated facts.
  - **No profiling.** The system makes no evaluation or prediction about a person's performance or personal aspects. Under Art. 6(3), profiling would always make the system high-risk.
- **Before a pilot, Espoo documents this assessment** in writing (Art. 6(4)). Given how close the stand promotion is, the safe course is to run the pilot as if the system were high-risk. The prototype already contains the core of what that requires:
  - human oversight (Art. 14)
  - logs of every decision (Art. 12)
  - clear information for the people operating it (Art. 13)
  - a fundamental-rights impact assessment, which a public body must do (Art. 27)
- **AI-written text is labelled** as drafts and summaries (Art. 50).
- **Organisers get short AI-literacy training** (Art. 4).
- **GDPR:**
  - Legal basis: Espoo's statutory employment-service task (public employment services moved to municipalities on 1 January 2025) for the core questionnaire, and consent for the optional work sample and permit question.
  - No solely automated decisions (GDPR Art. 22).
  - A data-protection impact assessment before the pilot (Art. 35).
  - Data minimised as in the table above, and stored in the EU.
  - Any language model is EU-hosted, gets no training rights, and only sees job ads and pages the candidate shared.

## Prototype limits, stated honestly

- **The data is synthetic.** All companies and people are fictional, and none of the figures are statistics about real people. Numbers on the post-event screen are labelled illustrative.
- **The job-ad draft in the prototype comes from transparent rules** that run in the browser. A pilot would add a language model, and the company would still confirm the draft.
- **Work-sample summaries in the prototype are pre-written** to show the flow.
- **The fairness check is a prompt for reflection, not a guarantee.** The pilot should review its thresholds with Espoo's equality experts.
