import type { Finding, Lang } from './types'

export const NAMES: Record<Lang, string> = { fi: 'Finnish', sv: 'Swedish', en: 'English' }
/** "Finnish, Swedish and English". */
export const list = (names: string[], and = 'and') => (names.length < 2 ? names.join('') : `${names.slice(0, -1).join(', ')} ${and} ${names[names.length - 1]}`)

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
export const day = (d: string) => `${+d.slice(8, 10)} ${MONTHS[+d.slice(5, 7) - 1]} ${d.slice(0, 4)}`
export const shortDay = (d: string) => `${+d.slice(8, 10)} ${MONTHS[+d.slice(5, 7) - 1].slice(0, 3)} ${d.slice(0, 4)}`
export const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`
export const kb = (bytes: number) => `${Math.max(1, Math.round(bytes / 1000))} KB`

// The API bounds each change: it happened after `after` (the last date compared without it) and no
// later than `at`. One day apart, the date is exact.
export const exact = (after: string | null | undefined, at: string) => !!after && Date.parse(at) - Date.parse(after) <= 86_400_000

// The time strip's scale: from Wikipedia's first year to today, the same on every topic.
const START = Date.UTC(2001, 0, 1)
/** Where a day sits on the time strip, as a percentage of its width. */
export const onScale = (d: string | number) => Math.max(0, Math.min(100, (((typeof d === 'number' ? d : Date.parse(d)) - START) / (Date.now() - START)) * 100))
/** The years the strip marks. */
export const DECADES = [2010, 2020].map((year) => ({ year, at: onScale(Date.UTC(year, 0, 1)) }))

export function when(after: string | null | undefined, at: string, fmt = day): string {
	if (exact(after, at)) return fmt(at)
	return after ? `between ${fmt(after)} and ${fmt(at)}` : `${fmt(at)} or earlier`
}

/** One short date for a list row; the bounds are spelled out inside the row. */
export function rowDate(f: Finding): string {
	if (f.history === false) return 'In the current text'
	return `${exact(f.opened_after, f.opened_at) ? 'Since' : 'By'} ${shortDay(f.opened_at)}`
}

/** The day after, for reading a text as it stood once an edit of that day was in. Never past today. */
export function dayAfter(d: string, days = 1): string {
	const next = new Date(Date.parse(d) + days * 86_400_000).toISOString().slice(0, 10)
	const today = new Date().toISOString().slice(0, 10)
	return next > today ? today : next
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
