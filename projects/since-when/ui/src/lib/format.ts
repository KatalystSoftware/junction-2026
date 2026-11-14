import type { Finding, FindingType, Lang } from './types'

export const NAMES: Record<Lang, string> = { fi: 'Finnish', sv: 'Swedish', en: 'English' }
export const TYPES: Record<FindingType, string> = {
	contradiction: 'Contradiction',
	numbers: 'Numbers',
	framing: 'Framing',
	missing_fact: 'Missing fact',
	coverage: 'Missing passage',
}
// Statements that differ come before content one edition lacks.
export const TYPE_ORDER: FindingType[] = ['contradiction', 'numbers', 'framing', 'missing_fact', 'coverage']

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
export const day = (d: string) => `${+d.slice(8, 10)} ${MONTHS[+d.slice(5, 7) - 1]} ${d.slice(0, 4)}`
export const shortDay = (d: string) => `${+d.slice(8, 10)} ${MONTHS[+d.slice(5, 7) - 1].slice(0, 3)} ${d.slice(0, 4)}`
export const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`
export const kb = (bytes: number) => `${Math.max(1, Math.round(bytes / 1000))} KB`

// The API bounds each change: it happened after `after` (the last date compared without it) and no
// later than `at`. One day apart, the date is exact.
const exact = (after: string | null | undefined, at: string) => !!after && Date.parse(at) - Date.parse(after) <= 86_400_000

export function when(after: string | null | undefined, at: string, fmt = day): string {
	if (exact(after, at)) return fmt(at)
	return after ? `between ${fmt(after)} and ${fmt(at)}` : `${fmt(at)} or earlier`
}

export function since(f: Finding, fmt = day): string {
	if (f.history === false) return 'In the current text; earlier years not compared'
	return `Since ${when(f.opened_after, f.opened_at, fmt)}`
}

/** One short date for a list row; the bounds are spelled out inside the row. */
export function rowDate(f: Finding): string {
	if (f.status !== 'open' && f.closed_at) return `closed ${shortDay(f.closed_at)}`
	if (f.history === false) return 'current text'
	return exact(f.opened_after, f.opened_at) ? shortDay(f.opened_at) : `by ${shortDay(f.opened_at)}`
}

const slug = (title: string) => encodeURIComponent(title.replace(/ /g, '_'))
const anchor = (section?: string | null) => (section ? '#' + slug(section.split(' › ').pop()!) : '')

export const articleUrl = (lang: Lang, title: string) => `https://${lang}.wikipedia.org/wiki/${slug(title)}`
export const revisionUrl = (lang: Lang, rev: number, section?: string | null) => `https://${lang}.wikipedia.org/w/index.php?oldid=${rev}${anchor(section)}`
export const diffUrl = (lang: Lang, rev: number, old: number) => `https://${lang}.wikipedia.org/w/index.php?diff=${rev}&oldid=${old}`
export const wikidataUrl = (qid: string) => `https://www.wikidata.org/wiki/${qid}`

/** Where a finding's quote sits in an edition: '' is the lead, undefined when that side has no passage. */
export function sectionOf(f: Finding, l: Lang): string | undefined {
	if (f.type === 'coverage') return l === f.lang ? undefined : (f.section ?? '')
	return (l === f.lang ? f.section : f.other_section) ?? ''
}

export const sectionLabel = (s: string) => (s ? s.split(' › ').pop()! : 'Lead')
