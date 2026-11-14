// The shapes the API returns (../docs/api.md). Only the fields the app reads are listed.

export type Lang = 'fi' | 'sv' | 'en'
export const LANGS: Lang[] = ['fi', 'sv', 'en']
export const isLang = (x: unknown): x is Lang => LANGS.includes(x as Lang)

export type FindingType = 'contradiction' | 'numbers' | 'framing' | 'missing_fact' | 'coverage'
type PerLang<T> = Partial<Record<Lang, T>>

export interface SqlEntry {
	label: string
	query: string
	ms: number
	rows: number
}

export interface QueueItem {
	wikidata_id: string
	topic: string
	lang: Lang
	rich_lang: Lang
	findings: number
}

/** What the claim check made of a finding: looked up in every passage of the other edition by a second model. */
export interface Check {
	outcome: 'kept' | 'changed' | 'new' | 'set_aside' | 'unchecked'
	reason: 'stated_elsewhere' | 'not_confirmed' | 'repeat' | null
	verdict: 'not_mentioned' | 'contradicted' | 'supported' | 'unchecked' | null
	judge: string
	as_of: string
	claim: { lang: Lang | null; quote: string | null; about: string | null }
	searched: number | null
	read: number | null
	/** The passage that settled it; `passage` is its whole text, on a set-aside row only. */
	evidence: { lang: Lang; rev_id: number | null; section: string | null; quote: string | null; passage: string | null } | null
}

export interface Finding {
	id: number
	lang: Lang
	other_lang: Lang
	type: FindingType
	section: string | null
	other_section: string | null
	summary: string
	quotes: PerLang<string>
	citations?: PerLang<string | null>
	paragraph_citations?: PerLang<string | null>
	rev_ids?: PerLang<number>
	terms?: string[]
	distance: number | null
	weight: number | null
	status: 'open' | 'reviewed' | 'closed'
	/** An editor's or a hand check's outcome; `not_real`: a person found it is not a difference. */
	outcome?: 'edited' | 'talk' | 'intentional' | 'not_real' | null
	opened_at: string
	opened_after: string | null
	closed_at: string | null
	closed_after: string | null
	history?: boolean
	/** null: the check did not look at this row. Absent on a database without the check. */
	check?: Check | null
}

export interface Lead {
	text: string
	rev_id?: number
	also?: string
}

export interface Topic {
	wikidata_id: string
	topic: string
	titles: PerLang<string>
	size: PerLang<number>
	readers: PerLang<number>
	refs?: PerLang<number>
	quality?: PerLang<string>
	leads?: PerLang<Lead>
	findings: Finding[]
	/** The check's totals for the topic; null when it has not run on it. */
	checked?: { judge: string; model?: string | null; as_of: string; kept?: number; changed?: number; new?: number; set_aside: Record<string, number> } | null
	sql: SqlEntry[]
}

export interface TimelineEvent {
	date: string
	after?: string | null
	finding_id: number
	kind: 'opened' | 'closed' | 'reviewed'
	type?: FindingType
	summary: string
	rev_id?: number | null
	rev_lang?: Lang | null
	rev_url?: string | null
	diffs?: { lang: Lang; old_rev_id: number; rev_id: number }[]
}

export interface Timeline {
	years: { year: number; size: PerLang<number>; coverage: number | null; open_findings: number }[]
	events: TimelineEvent[]
	sql: SqlEntry[]
}

export interface Preset {
	name: string
	title: string
	description: string
	params: { name: string; kind: 'qid' | 'date' | 'lang' | 'finding'; default: string }[]
}

export interface Presets {
	enabled: boolean
	limits: { seconds: number; rows: number }
	presets: Preset[]
}

export interface Run {
	preset: string
	params: Record<string, string>
	columns: string[]
	rows: (string | number | null)[][]
	capped: boolean
	ms: number
	limits: { seconds: number; rows: number }
	sql: SqlEntry[]
}
