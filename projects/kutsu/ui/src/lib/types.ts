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
}
export type Preset = { title: string; note: string; url: string; ids: string[]; names?: Record<string, string> }
export type Step = { stage: 'identity' | 'search' | 'careers' | 'read' | 'check' | 'card'; [fact: string]: unknown }
