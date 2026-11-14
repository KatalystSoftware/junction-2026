// The address is the state: ?q=…&lang=sv&sql=<preset>,<values>#/<wikidata id>/<edition>/<edition>/<findings|timeline>
import { isLang, type Lang, type SqlEntry } from './types'

export type Tab = 'findings' | 'timeline'
export interface Route {
	qid: string
	lang: string
	rich: string
	tab: Tab
}

export const href = (r: Route, patch: Partial<Route> = {}) => {
	const x = { ...r, ...patch }
	return `#/${x.qid}/${x.lang}/${x.rich}/${x.tab}`
}

// `compare` (the side-by-side view this app no longer has), an unknown tab or a trailing year all
// land on the findings; the address is rewritten so the link a visitor copies is one the app keeps.
function parseHash(): Route | null {
	const [qid, lang = '', rich = '', tab = 'findings', ...rest] = location.hash.replace(/^#\/?/, '').split('/')
	if (!qid) return null
	const route: Route = { qid, lang, rich, tab: tab === 'timeline' ? 'timeline' : 'findings' }
	if (lang && rich && (tab !== route.tab || rest.length)) history.replaceState(null, '', location.pathname + location.search + href(route))
	return route
}

const params = new URLSearchParams(location.search)
const lang = params.get('lang')

export const nav = $state({
	route: parseHash(),
	q: params.get('q') ?? '',
	lang: (isLang(lang) ? lang : 'all') as Lang | 'all',
	sql: params.get('sql'),
})

// What is open on top of the page.
export const ui = $state({ topics: params.has('q'), sql: false })

// The queries behind what is on screen, for the SQL panel.
export const log = $state({ listLabel: 'Topic list', list: [] as SqlEntry[], topic: [] as SqlEntry[], tab: [] as SqlEntry[] })

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
