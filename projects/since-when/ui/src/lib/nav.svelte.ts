// The address is the state: ?q=…&lang=sv&sql=<preset>,<values>#/<wikidata id>
import { isLang, type Lang, type SqlEntry } from './types'

export interface Route {
	qid: string
}

export const href = (qid: string) => `#/${qid}`

// Older addresses named two editions and a tab (#/Q1/sv/en/findings, …/timeline, …/compare/2020).
// They open the topic's page, and the address is rewritten to the one the app keeps.
function parseHash(): Route | null {
	const [qid, ...rest] = location.hash.replace(/^#\/?/, '').split('/')
	if (!qid) return null
	if (rest.length) history.replaceState(null, '', location.pathname + location.search + href(qid))
	return { qid }
}

const params = new URLSearchParams(location.search)
const lang = params.get('lang')

export const nav = $state({
	route: parseHash(),
	q: params.get('q') ?? '',
	lang: (isLang(lang) ? lang : 'all') as Lang | 'all',
	sql: params.get('sql'),
})

// What is open on top of the page. `runnable` is set once the server says it runs statements;
// `ask` is a statement a difference wants shown in the SQL panel.
export const ui = $state({ topics: params.has('q'), sql: false, runnable: false, ask: null as { preset: string; values: Record<string, string> } | null })

/** Opens the SQL panel with a statement filled in. Nothing runs until Run is clicked. */
export function showSql(preset: string, values: Record<string, string>) {
	ui.ask = { preset, values }
	ui.sql = true
}

// The queries behind what is on screen, for the SQL panel.
export const log = $state({ listLabel: 'Topic list', list: [] as SqlEntry[], topic: [] as SqlEntry[], history: [] as SqlEntry[] })

addEventListener('hashchange', () => {
	nav.route = parseHash()
})

export function syncSearch() {
	const p = new URLSearchParams()
	if (nav.lang !== 'all') p.set('lang', nav.lang)
	if (nav.q) p.set('q', nav.q)
	if (nav.sql) p.set('sql', nav.sql)
	const qs = p.toString().replace(/%2C/g, ',')
	history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash)
}
