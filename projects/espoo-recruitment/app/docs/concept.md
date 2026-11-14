# Esittely: hand-picked introductions for Espoo recruitment events

**One line:** a light layer on top of event registration. It pulls the information out of companies and candidates before the event, translates it into plain language, and lets City of Espoo organisers hand-pick the conversations that are worth having.

**How it differs from matchmaking platforms:** matchmaking platforms let an algorithm score and rank people. Esittely gives the organiser the domain understanding to make the introduction themselves, and records the reason.

## The problem today

- **Recruiters:** they don't describe their needs, or they describe them too late. They also doubt that a free public service has relevant candidates. After the event they complain about noise: too many approaches that weren't relevant.
- **Candidates:** they struggle to say what they can actually do. CVs are increasingly written by AI, so CV text is a weak signal.
- **Organisers:** they have the capacity to hand-pick who meets whom. What they lack is the technical knowledge to judge fit for tech roles.
- **The current platform:** it feels cumbersome, and it crashes when everyone logs in at the start of the event.

## Who uses it, and when

| Who | When | Effort | What they get |
|---|---|---|---|
| **Company recruiter** | 3 weeks before the event | About 1 minute | A draft of their needs made from their own public job ad, to confirm or correct. A live, anonymous count of registered attendees who fit, and their stand promoted to those people. A short list of hand-picked introductions, each with the organiser's reason. |
| **Candidate** | 2 weeks before, on their phone, at their own pace | About 3 minutes | 6 concrete questions. A short list of stands worth visiting, each with a reason. Every stand stays open to them. They can see and correct exactly how organisers see them. |
| **City organiser** | 1 week before | 15–30 minutes per company: the must-have filter narrows, for example, 72 requests to 10 to read closely | Each company's needs in plain language, linked to ESCO. For each possible introduction: overlaps, gaps and practical checks, each linked to its source answer. Their own choice of filters and sort, plus a decision with a one-line reason. |
| **Both sides** | The day after | One tap | "Was this conversation relevant?" The answers become proof of quality for the next event. |

## How it works: the AI pulls the information, humans make the judgements

1. **Company input is framed as promotion, not filtering.** "Tell us who you want to meet, and we'll promote your stand to them."
   - The draft comes from the company's public job ad, and every field shows the sentence it came from.
   - The company is asked directly whether Finnish is truly required. Each answer shows how many attendees would fit.
   - If the company never answers, the draft is used and marked as unconfirmed.
2. **Candidates answer the same dimensions companies answer**, so the two sides can be compared directly:
   - field and experience
   - tools, each with a depth and an optional concrete example
   - working languages
   - practicalities
   - three forced trade-offs

   Forced choices and specifics replace free text that an AI could have written.
3. **An optional work sample.** The candidate shares a link, the system summarises what it shows, and the candidate approves the summary before anyone sees it. There is an alternative route for people without public work, and having no portfolio is never shown as a gap.
4. **The organiser decides.**
   - Facts are laid out side by side, with sources.
   - Names are hidden until the organiser decides.
   - There are no scores, and the list order is only the sort the organiser picked.
   - Each decision needs a one-line reason, which goes to the company with the introduction.
   - A fairness check compares who was introduced with who asked, in aggregate only.

## Why it beats today's process

| Today | With Esittely |
|---|---|
| Companies send needs late, or not at all | A draft from the company's own job ad. One minute to confirm. Promotion as the reward. |
| "There are no relevant candidates in a public service" | A live count from this event's registrations shows the relevant people exist, before the company commits time. |
| Noise at the stands | Planned conversations, each with a written reason. Candidates see which stands fit them and why. |
| AI-written CVs | Concrete answers, forced trade-offs and candidate-approved evidence. No CV parsing at all. |
| Organisers can't judge tech fit | Plain-language explanations, ESCO links, and overlaps and gaps with sources. |
| "Fluent Finnish required" by habit | The company is asked whether Finnish is truly required, and sees how many good people the requirement excludes. |
| Platform crashes at login rush | A static site, filled in beforehand at each person's own pace, so nothing happens at the opening minute. |

## Feasibility

- **Pilot:** one Espoo tech recruitment event with 10–15 companies.
- **Data in:** the registration tool's export as input, with no new event platform. Job ads come from the companies' own pages or from Job Market Finland.
- **Running it:** two organisers.
- **Build:** a static web app plus a small EU-hosted API. Drafts and summaries come from an EU-hosted language model, and every draft is human-confirmed.
- **Feedback:** the post-event relevance question gives the pilot its success metric.

## What the prototype shows

All data is synthetic (360 candidates, 12 fictional companies).

- **Organiser view:** working.
- **One-minute employer confirmation:** working. The job-ad extractor runs live in the browser.
- **Candidate questionnaire and stand recommendations:** working.
- **Work-sample review and post-event screen:** mock-ups.
