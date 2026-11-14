// What the topic page lists. The API returns one row per pair of editions and per passage; a
// reader wants one line per claim. This file merges the rows into differences, orders them, words
// them for a reader and collects the content one edition has and another leaves out.

import { NAMES, day, exact, list, when } from './format'
import { figures } from './text'
import { LANGS, type Finding, type FindingType, type Lang, type TimelineEvent, type Topic } from './types'

/** Rows where both editions say something and the two differ. The rest is content one edition lacks. */
const DIFFERS: FindingType[] = ['framing', 'numbers', 'contradiction']
/** Differences listed before "Show all". */
export const FIRST = 7

export interface Difference {
	id: number
	type: FindingType
	/** The row that titles and dates the difference. */
	primary: Finding
	/** Every row about the same claim, the primary first. */
	members: Finding[]
	/** The edition each shown quote comes from, with the row it was taken from. */
	quotes: { lang: Lang; text: string; from: Finding | null }[]
	/** The headline: a few words that tell this difference from the next, and the edition they are about. */
	who: string
	what: string
	/** The whole difference in one sentence, for a tooltip. */
	title: string
	lead: boolean
	/** A conflicting account whose two quotes are not plainly about the same thing: listed last. */
	unsure: boolean
}

const inLead = (f: Finding) => f.section === '' && f.other_section === ''
const dated = (f: Finding) => f.history !== false && !!f.opened_after && Date.parse(f.opened_at) - Date.parse(f.opened_after) <= 86_400_000
const squash = (s: string) => s.replace(/\s+/g, ' ').trim().toLowerCase()

// The same words: equal, or one quote inside the other and most of it. A clause inside a long
// sentence is not enough: one sentence can hold two claims.
const sameWords = (a: string, b: string) => a === b || (Math.min(a.length, b.length) >= 0.6 * Math.max(a.length, b.length) && (a.includes(b) || b.includes(a)))
const sharedQuote = (a: Finding, b: Finding) => LANGS.some((l) => a.quotes[l] && b.quotes[l] && sameWords(squash(a.quotes[l]!), squash(b.quotes[l]!)))

// The figures a row singles out in an edition: those of its quote that the other quote does not have.
function singled(f: Finding, l: Lang): string {
	const other = new Set(figures(f.quotes[l === f.lang ? f.other_lang : f.lang] ?? '').map((n) => n.value))
	return [...new Set(figures(f.quotes[l] ?? '').map((n) => n.value))].filter((v) => !other.has(v)).sort().join()
}
// Two rows about figures, between the same two editions, that single out the same figures on both sides.
const sameFigures = (a: Finding, b: Finding) =>
	a.type === 'numbers' && [a.lang, a.other_lang].every((l) => (l === b.lang || l === b.other_lang) && !!singled(a, l) && singled(a, l) === singled(b, l))

/**
 * Two rows are one claim when they are of one type and name the same loaded word, quote the same
 * words of an edition, or single out the same figures.
 */
const sameClaim = (a: Finding, b: Finding) => a.type === b.type && ((a.type === 'framing' && !!a.terms?.some((t) => b.terms?.includes(t))) || sharedQuote(a, b) || sameFigures(a, b))

// The lexicon writes one fixed sentence per loaded word.
const LEXICON = /^The (Finnish|Swedish|English) first sentence uses .+; the (Finnish|Swedish|English) first sentence uses other words for the same thing\.$/
const byName = (name: string) => LANGS.find((l) => NAMES[l] === name)!
/** For a row the lexicon wrote: the word, the edition that uses it and the one that does not. */
function word(f: Finding): { term: string; user: Lang; other: Lang } | null {
	const m = LEXICON.exec(f.summary)
	return m && f.terms?.[0] ? { term: f.terms[0], user: byName(m[1]), other: byName(m[2]) } : null
}

const SUBJECT = /\b[Tt]he (Finnish|Swedish|English) (?:passage|first sentence|article|lead|text|version)\b/g

/** A classifier summary in the reader's words: "the Swedish passage" becomes "Swedish Wikipedia". */
export function reword(summary: string): string {
	return summary
		.replace(/\b[Tt]he (Finnish|Swedish|English) and (Finnish|Swedish|English) (?:passages|first sentences|articles|leads|texts|versions)\b/g, '$1 and $2 Wikipedia')
		.replace(/\b[Tt]he (Finnish|Swedish|English) first sentence\b/g, "$1 Wikipedia's first sentence")
		.replace(SUBJECT, '$1 Wikipedia')
		.replace(/\s*\((?:political|loaded) label\)/g, '')
		.replace(/\b([Bb])oth passages\b/g, '$1oth editions')
		.replace(/\buses other words for the same thing\b/g, 'does not')
}

/** What a summary says about each edition, when it is written as one clause per edition. */
function clauses(summary: string): Partial<Record<Lang, string>> | null {
	const hits = [...summary.matchAll(SUBJECT)]
	if (hits.length !== 2 || hits[0].index !== 0 || hits[0][1] === hits[1][1]) return null
	const cut = (from: number, to: number) =>
		summary
			.slice(from, to)
			.replace(/[\s,;]*(?:\b(?:while|whereas|but|and)\b)?\s*$/, '')
			.replace(/\.$/, '')
			.trim()
	const first = cut(hits[0][0].length, hits[1].index)
	const second = cut(hits[1].index + hits[1][0].length, summary.length)
	return first && second ? { [byName(hits[0][1])]: first, [byName(hits[1][1])]: second } : null
}

function titleOf(primary: Finding, members: Finding[], third: Finding | null): string {
	const w = word(primary)
	if (w) {
		// Every row the lexicon wrote about this word: who uses it and who does not.
		const rows = members.map(word).filter((x) => x?.term === w.term)
		const users = LANGS.filter((l) => rows.some((x) => x!.user === l))
		const others = LANGS.filter((l) => !users.includes(l) && rows.some((x) => x!.other === l))
		const many = users.length > 1
		return `${list(users.map((l) => NAMES[l]))} Wikipedia ${many ? 'use' : 'uses'} “${w.term}” in ${many ? 'their' : 'its'} first sentence; ${list(others.map((l) => NAMES[l]))} Wikipedia ${others.length > 1 ? 'do' : 'does'} not.`
	}
	const title = reword(primary.summary)
	// A third edition's quote comes from another row; its clause is added when that row's summary has one.
	const extra = third && LANGS.find((l) => third.quotes[l] && l !== primary.lang && l !== primary.other_lang)
	const clause = extra && clauses(third.summary)?.[extra]
	return clause ? `${title.replace(/\.$/, '')}; ${NAMES[extra]} Wikipedia ${clause}.` : title
}

/**
 * The headline of a difference. A loaded word is its own headline. Otherwise it is what the summary
 * says about the edition it names first, without "Wikipedia": the quotes and the time strip carry
 * the other editions. A summary that is not written edition by edition is cut at its first break.
 */
function headline(primary: Finding, title: string): { who: string; what: string } {
	const w = word(primary)
	if (w) return { who: '', what: `“${w.term}”` }
	const first = [...primary.summary.matchAll(SUBJECT)][0]?.[1]
	const clause = first && clauses(primary.summary)?.[byName(first)]
	if (clause) return { who: first, what: clause }
	const cut = title
		.split(/[:;]|,? (?:while|whereas|but) /)[0]
		.replace(/\.$/, '')
		.trim()
	const m = /^((?:Finnish|Swedish|English)(?:(?:,| and) (?:Finnish|Swedish|English))*) Wikipedia(?:'s first sentence)? (.+)$/.exec(cut)
	return m ? { who: m[1], what: m[2] } : { who: '', what: cut }
}

// A conflicting account is believed only when both quotes are short and share a name or a figure.
function plain(f: Finding): boolean {
	const [a, b] = [f.quotes[f.lang], f.quotes[f.other_lang]]
	if (!a || !b || a.length > 80 || b.length > 80) return false
	const tokens = (s: string) => new Set(s.toLowerCase().match(/\p{L}{5,}|\d+/gu) ?? [])
	const other = tokens(b)
	return [...tokens(a)].some((t) => other.has(t))
}

/**
 * The topic's differences: open rows merged by claim. In order: a conflicting account that is not
 * plainly about one thing goes last; a claim quoted from three editions comes before one from two;
 * then the claim seen in more rows; the opening lines before the body; wording, then figures, then
 * conflicting accounts; and the longest-standing first.
 */
export function differences(topic: Topic): Difference[] {
	const rows = topic.findings.filter((f) => f.status === 'open' && DIFFERS.includes(f.type))
	const index = new Map(rows.map((f, i) => [f.id, i]))

	// Rows that are the same claim, directly or through another row, form one group.
	const group = rows.map((_, i) => i)
	const find = (i: number): number => (group[i] === i ? i : (group[i] = find(group[i])))
	rows.forEach((a, i) => rows.forEach((b, j) => j > i && sameClaim(a, b) && (group[find(i)] = find(j))))
	const groups = new Map<number, Finding[]>()
	rows.forEach((f, i) => groups.set(find(i), [...(groups.get(find(i)) ?? []), f]))

	const out = [...groups.values()].map((members): Difference => {
		// The row that speaks for the group: about the opening lines, dated by one edit, the oldest.
		members.sort((a, b) => +inLead(b) - +inLead(a) || +dated(b) - +dated(a) || a.opened_at.localeCompare(b.opened_at) || index.get(a.id)! - index.get(b.id)!)
		const primary = members[0]
		// One quote per edition: the primary's own two, then the third from the row closest to it.
		const near = [...members.slice(1).filter((f) => sharedQuote(f, primary)), ...members.slice(1)]
		const quotes = LANGS.map((lang) => {
				const from = primary.quotes[lang] ? primary : (near.find((f) => f.quotes[lang]) ?? null)
				return { lang, text: from?.quotes[lang] ?? '', from }
			})
			.filter((q) => q.text)
		const third = quotes.find((q) => q.from !== primary)?.from ?? null
		const title = titleOf(primary, members, third)
		return {
			id: primary.id,
			type: primary.type,
			primary,
			members,
			quotes,
			...headline(primary, title),
			title,
			lead: inLead(primary),
			unsure: primary.type === 'contradiction' && !plain(primary),
		}
	})

	const kind = (d: Difference) => DIFFERS.indexOf(d.type)
	return out.sort(
		(a, b) =>
			+a.unsure - +b.unsure ||
			b.quotes.length - a.quotes.length ||
			b.members.length - a.members.length ||
			+b.lead - +a.lead ||
			kind(a) - kind(b) ||
			a.primary.opened_at.localeCompare(b.primary.opened_at) ||
			index.get(a.id)! - index.get(b.id)!,
	)
}

/** For each quote of a difference, the stretches to mark: figures that are not in every quote. */
export function figureMarks(d: Difference): Map<Lang, [number, number][]> {
	const marks = new Map<Lang, [number, number][]>()
	if (d.type !== 'numbers') return marks
	const found = d.quotes.map((q) => figures(q.text))
	d.quotes.forEach((q, i) => {
		const elsewhere = found.filter((_, j) => j !== i)
		marks.set(
			q.lang,
			found[i].filter((n) => !elsewhere.every((other) => other.some((o) => o.value === n.value))).map((n) => [n.start, n.end]),
		)
	})
	return marks
}

export interface Turn {
	key: string
	/** "Since 30 May 2022", or the bounds when the edit is not known to the day. */
	date: string
	/** What happened, in the reader's words. */
	what: string
	/** The loaded word the row follows, when the lexicon wrote it. */
	term: string
	/** The edit (or the two candidates) that began it. */
	edits: { lang: Lang; rev: number; old: number }[]
	/** Earlier periods the same difference held, as years and as days. */
	earlier: string[]
	past: { from: string; to: string }[]
	/** For the as-of statement: the day of the edit and the edition it was made in. */
	at: string
	lang: Lang
	/** False when no earlier version was compared, so there is no day to draw. */
	known: boolean
	/** True when the day is that of one edit, false when it is only the latest it can be. */
	exact: boolean
	/** The two editions the row compares. */
	pair: [Lang, Lang]
}

const sinceWhen = (after: string | null | undefined, at: string) => {
	const text = when(after, at, day)
	return /^\d/.test(text) && after ? `since ${text}` : text
}
const years = (from: string, to: string) => (from.slice(0, 4) === to.slice(0, 4) ? from.slice(0, 4) : `${from.slice(0, 4)}–${to.slice(0, 4)}`)

/**
 * When a difference began: one line per row of the group, the primary's first, rows that began
 * with the same edit and word told once. `events` are the API's timeline events by finding.
 */
export function turns(d: Difference, events: Map<number, TimelineEvent[]>): Turn[] {
	const seen = new Set<string>()
	const out: Turn[] = []
	for (const f of d.members) {
		const es = [...(events.get(f.id) ?? [])].filter((e) => e.kind !== 'reviewed').sort((a, b) => a.date.localeCompare(b.date))
		const earlier: string[] = []
		const past: Turn['past'] = []
		let from: string | null = null
		let began: TimelineEvent | null = null
		for (const e of es) {
			if (e.kind === 'opened' && from === null) (from = e.date), (began = e)
			if (e.kind === 'closed' && from !== null) earlier.push(years(from, e.date)), past.push({ from, to: e.date }), (from = null), (began = null)
		}
		const edits = (began?.diffs ?? []).map((x) => ({ lang: x.lang, rev: x.rev_id, old: x.old_rev_id }))
		const w = word(f)
		const one = edits.length === 1 ? edits[0].lang : null
		const what = !edits.length
			? f.history === false || !f.opened_after
				? 'no earlier version was compared'
				: ''
			: w && one
				? `${NAMES[one]} Wikipedia ${one === w.user ? 'added' : 'dropped'} “${w.term}”`
				: `${w ? `“${w.term}”, ` : ''}an edit to ${list(edits.map((x) => NAMES[x.lang]), 'or')} Wikipedia`
		const key = `${f.opened_at}|${edits.map((x) => x.lang).join()}|${w?.term ?? ''}`
		if (seen.has(key)) continue
		seen.add(key)
		out.push({
			key,
			date: f.history === false ? 'In the current text' : sinceWhen(began?.after ?? f.opened_after, began?.date ?? f.opened_at),
			what,
			term: w?.term ?? '',
			edits,
			earlier,
			past,
			at: began?.date ?? f.opened_at,
			lang: one ?? edits[0]?.lang ?? f.other_lang,
			known: f.history !== false,
			exact: exact(began?.after ?? f.opened_after, began?.date ?? f.opened_at),
			pair: [f.lang, f.other_lang],
		})
	}
	return out
}

export interface Lane {
	lang: Lang
	/** The periods this edition has said what the difference is about, oldest first. `to` is null while it still does. */
	spans: { from: string; to: string | null }[]
	/** The day the period that still runs began, and the edit that began it when it is known. */
	since: { at: string; exact: boolean; edit: { rev: number; old: number } | null } | null
}

/**
 * The time strip of a difference: one lane for each quoted edition. An edit dates the lane of the
 * edition it was made in; when two editions were edited that day, both; when the edit is not known,
 * the two editions the row compares.
 */
export function lanes(d: Difference, main: Turn[]): Lane[] {
	const out = d.quotes.map((q): Lane => ({ lang: q.lang, spans: [], since: null }))
	for (const t of main) {
		if (!t.known) continue
		for (const lane of out) {
			const edit = t.edits.find((e) => e.lang === lane.lang)
			if (lane.since || (t.edits.length ? !edit : !t.pair.includes(lane.lang))) continue
			lane.spans = [...t.past, { from: t.at, to: null }]
			lane.since = { at: t.at, exact: t.exact, edit: edit ? { rev: edit.rev, old: edit.old } : null }
		}
	}
	return out
}

export interface Missing {
	key: string
	/** The edition that says it and the editions it was not found in. */
	has: Lang
	lacks: Lang[]
	quote: string
	section: string
	row: Finding
}

/** What each edition says that another leaves out: one item per quoted statement. */
export function missing(topic: Topic): Record<Lang, Missing[]> {
	const out: Record<Lang, Missing[]> = { fi: [], sv: [], en: [] }
	const seen = new Map<string, Missing>()
	for (const f of topic.findings) {
		if (f.status !== 'open' || DIFFERS.includes(f.type)) continue
		const quoted = LANGS.filter((l) => f.quotes[l])
		const has = quoted.length === 1 ? quoted[0] : f.other_lang
		const lacks = has === f.lang ? f.other_lang : f.lang
		const quote = f.quotes[has] ?? ''
		const key = `${has}|${quote ? squash(quote) : f.id}`
		const known = seen.get(key)
		if (known) {
			if (!known.lacks.includes(lacks)) known.lacks.push(lacks)
			continue
		}
		const item: Missing = { key, has, lacks: [lacks], quote, section: (has === f.lang ? f.section : f.type === 'coverage' ? f.section : f.other_section) ?? '', row: f }
		seen.set(key, item)
		out[has].push(item)
	}
	// What neither other edition has comes first.
	for (const l of LANGS) out[l].sort((a, b) => b.lacks.length - a.lacks.length)
	return out
}
