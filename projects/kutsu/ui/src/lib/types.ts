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
  title: string
  why: string
  skills: string[]
  seniority: string
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
  card: { pitch: string; momentum: string; needs: Need[] }
  generated_at: string
  stats: { results_read: number; signals_dropped: number }
}

export type Status = 'draft' | 'invited' | 'joined'
/** A brief on its way: Espoo's edits, then what the company confirmed, corrected and asked for when signing up. */
export type Review = {
  status: Status
  needs: Need[]
  about?: Record<string, string>
  facts?: Record<string, boolean>
  wants?: string[]
  note?: string
  invited_at?: string
  joined_at?: string
}
export type Preset = { title: string; note: string; url: string; ids: string[]; names?: Record<string, string> }
export type Step = { stage: 'identity' | 'search' | 'careers' | 'read' | 'check' | 'card'; [fact: string]: unknown }
