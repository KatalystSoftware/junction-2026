import { LANGS, type Finding, type FindingType, type Lang } from './types'

const inLead = (f: Finding) => f.section === '' && f.other_section === ''
// Types where both editions say something and the two differ, as opposed to one lacking content.
export const DIFFERS: FindingType[] = ['contradiction', 'numbers', 'framing']

/**
 * The one finding a topic's page leads with. Open findings only, in this order of preference:
 * both quotes in the lead (the page shows the leads side by side); a statement that differs over
 * content one edition lacks; a finding about the edition the address names first; the most recent.
 * The sort is stable, so the API's own order (score, then distance) settles what is left.
 */
export function pickHeadline(findings: Finding[], lang: string): Finding | null {
	const rank = (f: Finding) => [inLead(f), DIFFERS.includes(f.type), f.lang === lang || f.other_lang === lang, f.history !== false].map(Number)
	const open = findings.filter((f) => f.status === 'open')
	open.sort((a, b) => {
		const [ra, rb] = [rank(a), rank(b)]
		for (let i = 0; i < ra.length; i++) if (ra[i] !== rb[i]) return rb[i] - ra[i]
		return b.opened_at.localeCompare(a.opened_at)
	})
	return open[0] ?? null
}

/** The loaded words the open findings about the leads name, for marking the opening sentences. */
export const leadTerms = (findings: Finding[]) => [...new Set(findings.filter((f) => f.status === 'open' && inLead(f)).flatMap((f) => f.terms ?? []))]

export const isLeadFinding = inLead

/** The address names two editions; the third is shown beside them. */
export const thirdOf = (a: string, b: string): Lang | undefined => LANGS.find((l) => l !== a && l !== b)
