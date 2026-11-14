// The topic list: the API's queue, or its search when there is a query.
import { api, ApiError } from './api.svelte'
import { log, nav, syncSearch } from './nav.svelte'
import type { Database, QueueItem, SqlEntry } from './types'

const PAGE = 100

export const queue = $state({ items: [] as QueueItem[], total: 0, loading: true, error: '', searchable: true, database: null as Database | null })

let seq = 0

// Search returns each topic once, in its highest-scoring edition. Under an edition filter the row
// links to the chosen edition instead, and its count (which belongs to the other edition) is dropped.
function asEdition(i: QueueItem): QueueItem {
	if (nav.lang === 'all' || i.lang === nav.lang) return i
	return { ...i, lang: nav.lang, rich_lang: i.rich_lang === nav.lang ? i.lang : i.rich_lang, findings: 0 }
}

export async function loadQueue(more = false): Promise<void> {
	const token = ++seq
	queue.loading = true
	queue.error = ''
	try {
		const offset = more ? queue.items.length : 0
		const data = await api<{ items: QueueItem[]; total?: number; database?: Database; sql?: SqlEntry[] }>(
			nav.q ? `/search?q=${encodeURIComponent(nav.q)}&lang=${nav.lang}` : `/queue?lang=${nav.lang}&limit=${PAGE}&offset=${offset}`,
		)
		if (token !== seq) return
		const items = nav.q ? data.items.map(asEdition) : data.items
		queue.items = more ? [...queue.items, ...items] : items
		queue.total = data.total ?? queue.items.length
		queue.database = data.database ?? queue.database
		log.list = data.sql ?? []
		log.listLabel = nav.q ? 'Search' : 'Topic list'
	} catch (e) {
		if (token !== seq) return
		// A data service that does not offer search: drop the query and show the plain list.
		if (nav.q && e instanceof ApiError && [404, 501, 503].includes(e.status)) {
			queue.searchable = false
			nav.q = ''
			syncSearch()
			return loadQueue()
		}
		queue.error = e instanceof Error ? e.message : String(e)
	}
	queue.loading = false
}

export const pageSize = PAGE
