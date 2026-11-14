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

/** One talent need. `by` is set once a person has written or changed it; `off` once the company says no to it. */
export type Need = {
  /** stable within one sign-up, so a card can be followed as it moves */
  id?: string
  /** the company has accepted it */
  ok?: boolean
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
  by?: 'espoo' | 'company'
  off?: boolean
}
export type Posting = { headline: string; intro: string; you_will: string[]; you_bring: string[]; why_now: string }

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
  card: { pitch: string; momentum: string; needs: Need[]; also?: string[] }
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
  /** per statement: true to tell talent, false to leave out; absent while undecided */
  facts?: Record<string, boolean>
  /** the company has said there is no one else to add */
  added_done?: boolean
  wants?: string[]
  note?: string
  invited_at?: string
  joined_at?: string
}
export type Preset = { title: string; note: string; url: string; ids: string[]; names?: Record<string, string> }
export type Step = { stage: 'identity' | 'search' | 'careers' | 'read' | 'check' | 'card'; [fact: string]: unknown }
