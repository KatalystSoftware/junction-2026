export type Signal = {
  id: string
  type: string
  claim: string
  date: string
  quote: string
  source_url: string
  source_title: string
  published: string
}

/** A role as the pipeline drafts it: who the company seems to need, and what it asks of them. */
export type Draft = {
  title: string
  why: string
  /** what the person must be able to do, as work that can be shown */
  can_do: string[]
  /** tools, methods and fields they know */
  skills: string[]
  seniority: string
  language?: string | null
  workplace?: string | null
  where?: string | null
  /** whether the company hires people who are not yet in Finland; only the company can say */
  abroad?: boolean | null
  /** the sentence and page a value was read from, for those read from a job post */
  sources?: Record<string, { quote: string; url: string | null }>
  family?: string
  signals: string[]
  roles: string[]
}

/**
 * A role inside one sign-up. Its id is what lists are keyed by and what a card is followed by as it
 * moves, so it is required: a need without one once stopped the page.
 */
export type Need = Draft & {
  id: string
  /** the company has accepted it */
  ok?: boolean
  /** set once a person has written or changed it */
  by?: 'espoo' | 'company'
}

/** Something to tell candidates about the company: a short line, the sentence behind it, and the statements it rests on. */
export type Told = { id: string; line: string; detail: string; kind: string; date: string; signals: string[] }

export type Identity = {
  name: string | null
  domain: string
  slogan: string | null
  logo: string | null
  logo_on: 'dark' | 'light'
  icon: string | null
  icon_on: 'dark' | 'light'
  colors: string[]
  industries: string[]
  employees: string | null
  city: string | null
  country: string | null
}

export type Brief = {
  id: string
  name: string
  website: string | null
  in_espoo_data: boolean
  open_roles: number
  identity: Identity | null
  signals: Signal[]
  card: { pitch: string; momentum: string; tell: Told[]; left_out: { signal: string; why: string }[]; needs: Draft[]; also: string[] }
  generated_at: string
  stats: { results_read: number; signals_dropped: number }
}

export type Status = 'draft' | 'invited' | 'joined'
/** A brief on its way: Espoo's edits, then what the company confirmed, corrected and asked for when signing up. */
export type Review = {
  status: Status
  needs: Need[]
  /** the company has confirmed who it is */
  about_ok?: boolean
  about?: Record<string, string>
  /** the ids of the things the company agreed to tell candidates; absent until it has looked */
  told?: string[]
  wants?: string[]
  note?: string
  invited_at?: string
  joined_at?: string
  /** the events the company has been invited to, by slug; its profile is one and the same for all of them */
  events?: string[]
  /** the events the company has signed up for, by slug */
  signed?: string[]
  /** filled in by the demo control to show a screen in use; no company did this */
  example?: boolean
}
/** A named list of employers. `coming` says they are already on the event's public page, so nobody has to be invited: only their profiles confirmed. */
export type Preset = { title: string; note: string; url: string; date?: string; coming?: boolean; facts?: string; ids: string[]; names?: Record<string, string> }

/** One field of work in the sample pool, as counts. No row here is a person. */
export type PoolField = {
  people: number
  /** people who do other work today and want to move into this field */
  wanting: number
  levels: Record<string, number>
  english: number
  finnish: number
  abroad: number
  /** how many of them came to each past event, by event id */
  events: Record<string, number>
  /** how many know each skill employers ask for */
  skills: Record<string, number>
}
/** A real past event with its public page. `published` is a figure that page gives; `people` is how many of the sample pool came. */
export type PastEvent = { id: string; name: string; date: string; where: string; published: string; url: string; people: number }
export type Pool = { note: string; people: number; events: PastEvent[]; fields: Record<string, PoolField> }
/** Something a Context.dev monitor saw change for a company: a job opening on its careers page, or news about it. */
export type Change = { id: string; brief: string; kind: 'careers' | 'news'; title: string; summary: string; url: string; detected_at: string; importance: string }
type Watched = { last_run_at: string | null; next_run_at: string | null; last_change_at: string | null }
export type Watch = { watched: Record<string, { careers?: Watched; news?: Watched }>; changes: Change[]; checked_at: string }
/** One application to an event from the regular invitation, in the sample. `drafted` lines are the pipeline's reading of the
 * applicant's sources, left as drafted (the AI summary); `corrected`, `answers` and `own` are what the applicant explicitly did. */
export type Applicant = {
  id: string
  handle: string
  field: string
  level: string
  skills: { name: string; depth: 'work' | 'project' | 'learning'; years: number | null }[]
  finnish: string
  english: string
  city: string
  abroad: boolean
  permit: boolean
  wants: string[]
  applied_at: string
  sources: string[]
  ai_summary: string
  drafted: { kind: string; text: string; source: string; quote: string }[]
  corrected: { kind: string; text: string; was: string }[]
  answers: { q: string; a: string }[]
  own: { about: string; looking: string }
  project: { name: string } | null
}
export type Step = { stage: 'identity' | 'search' | 'careers' | 'read' | 'check' | 'card'; [fact: string]: unknown }
