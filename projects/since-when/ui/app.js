// Gap finder UI: the queue, one topic's findings, the side-by-side passages, the timeline, and the
// SQL behind each screen. Talks only to /api/* (docs/gap-finder/api.md); ui/serve.py serves it.
'use strict'

const NAMES = { fi: 'Finnish', sv: 'Swedish', en: 'English' }
const TYPES = { coverage: 'Missing passage', missing_fact: 'Missing fact', contradiction: 'Contradiction', framing: 'Framing', numbers: 'Numbers differ' }
const STATUS = { covered: 'Covered', partly: 'Partly covered', missing: 'No match', pending: 'Not compared yet' }
const YEARS = Array.from({ length: 22 }, (_, i) => 2005 + i)
const el = { queue: document.getElementById('queue'), topic: document.getElementById('topic'), sql: document.getElementById('sql'), layout: document.querySelector('.layout') }
const LANGS = ['fi', 'sv', 'en']
const params = new URLSearchParams(location.search)
const state = { lang: LANGS.includes(params.get('lang')) ? params.get('lang') : localStorage.getItem('gapfinder.lang') || 'all', q: params.get('q') || '', items: [], total: 0, route: null, topic: null, compare: null, timeline: null, sql: {}, onlyGaps: false, open: new Set(), searchable: true, types: new Set(), editing: null }
let seq = 0

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])
const readers = (n) => (n ? `${fmt(n)} views/yr` : 'page views pending')
// A date on 1 January comes from the yearly snapshots: the change happened some time in the year before.
const dateLabel = (d) => (d.endsWith('-01-01') ? `by 1 Jan ${d.slice(0, 4)}` : d)
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const day = (d) => `${+d.slice(8, 10)} ${MONTHS[+d.slice(5, 7) - 1]} ${d.slice(0, 4)}`
// With the API's lower bound (the last 1 January compared without the change), a date is a range:
// the edit happened after `after` and no later than `at`. Without the field, fall back to the date alone.
function rangeLabel(after, at, hasBound) {
	if (!hasBound) return null
	return after ? `between ${day(after)} and ${day(at)}` : `known since ${day(at)}`
}
const sinceLabel = (d) => (!d.endsWith('-01-01') ? `since ${d}` : d.startsWith('2005') ? 'since before 2005' : `opened during ${+d.slice(0, 4) - 1}`)
const fmt = (n) => (n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1000 ? (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k' : String(n))
const kb = (b) => Math.max(1, Math.round(b / 1000)) + ' KB'
const pct = (x) => Math.round(x * 100) + '%'
const chip = (kind, label) => `<span class="chip ${kind}">${esc(label)}</span>`
const wpLink = (lang, title) => `https://${lang}.wikipedia.org/wiki/${encodeURIComponent(String(title).replace(/ /g, '_'))}`
const historyLink = (lang, title, date) => `https://${lang}.wikipedia.org/w/index.php?title=${encodeURIComponent(String(title).replace(/ /g, '_'))}&action=history&offset=${date.replace(/-/g, '')}000000&limit=20`
const sectionName = (s) => (s ? s : 'Lead')
const editLink = (lang, title) => `https://${lang}.wikipedia.org/w/index.php?title=${encodeURIComponent(String(title).replace(/ /g, '_'))}&action=edit`

// Outcomes the API refuses (a read-only deployment) are kept in this browser only.
const LOCAL = JSON.parse(localStorage.getItem('gapfinder.outcomes') || '{}')
function applyLocal(f) {
	if (LOCAL[f.id]) Object.assign(f, LOCAL[f.id], { local: true })
	return f
}

function syncUrl() {
	const p = new URLSearchParams()
	if (state.lang !== 'all') p.set('lang', state.lang)
	if (state.q) p.set('q', state.q)
	// The open SQL panel's preset and values, so the address reopens it; kept as given until the presets load.
	if (live.asked) p.set('sql', live.asked)
	else if (live.name && !el.sql.hidden) p.set('sql', [live.name, ...Object.values(live.values[live.name])].join(','))
	const qs = p.toString().replace(/%2C/g, ',')
	history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash)
}

async function api(path, opts) {
	const r = await fetch('/api' + path, opts)
	const data = await r.json().catch(() => ({}))
	if (!r.ok) throw Object.assign(new Error(data.error || r.statusText), { status: r.status })
	if (data.fixture) document.getElementById('fixture').hidden = false
	return data
}

// Wraps every occurrence of the given quotes and loaded terms in <mark>, escaping everything else.
function highlight(text, quotes = [], terms = []) {
	text = String(text ?? '')
	const marks = []
	const add = (needle, cls) => {
		if (!needle) return
		const low = text.toLowerCase(), n = needle.toLowerCase()
		for (let i = low.indexOf(n); i >= 0; i = low.indexOf(n, i + n.length)) {
			let e = i + n.length
			if (cls === 'term') while (e < text.length && /[\p{L}\p{N}-]/u.test(text[e])) e++   // the whole word: fascist → fascistisk
			marks.push([i, e, cls])
		}
	}
	quotes.forEach((q) => add(q, ''))
	terms.forEach((t) => add(t, 'term'))
	if (!marks.length) return esc(text)
	// Terms inside a quote are drawn on top: split into boundaries and pick the strongest class per piece.
	const cuts = [...new Set([0, text.length, ...marks.flatMap(([a, b]) => [a, b])])].sort((a, b) => a - b)
	const pieces = []
	for (let i = 0; i < cuts.length - 1; i++) {
		const [a, b] = [cuts[i], cuts[i + 1]]
		const hit = marks.filter(([s, e]) => s <= a && e >= b)
		const cls = !hit.length ? null : hit.some((m) => m[2] === 'term') ? 'term' : ''
		const last = pieces[pieces.length - 1]
		if (last && last.cls === cls) last.text += text.slice(a, b)
		else pieces.push({ cls, text: text.slice(a, b) })
	}
	return pieces.map((p) => (p.cls === null ? esc(p.text) : `<mark class="${p.cls}">${esc(p.text)}</mark>`)).join('')
}

// ---------- routing: #/<qid>/<edition to review>/<edition compared with, most passages>/<tab>/<as of year> ----------

function parseHash() {
	const [qid, lang, rich, tab = 'findings', asOf = ''] = location.hash.replace(/^#\/?/, '').split('/')
	return qid ? { qid, lang, rich, tab, asOf } : null
}
const href = (r, patch = {}) => {
	const x = { ...r, ...patch }
	return `#/${x.qid}/${x.lang}/${x.rich}/${x.tab}${x.tab === 'compare' && x.asOf ? '/' + x.asOf : ''}`
}

async function onRoute() {
	const r = parseHash()
	if (!r) {
		const top = state.items[0]
		if (top) location.replace(href({ qid: top.wikidata_id, lang: top.lang, rich: top.rich_lang, tab: 'findings' }))
		return
	}
	if (r.asOf && !(+r.asOf >= 2005 && +r.asOf <= 2026)) return void location.replace(href(r, { asOf: '' }))
	if (!['findings', 'compare', 'timeline'].includes(r.tab)) return void location.replace(href(r, { tab: 'findings' }))
	const prev = state.route
	state.route = r
	el.layout.classList.remove('queue-open')
	renderQueue()
	const token = ++seq
	try {
		if (!prev || prev.qid !== r.qid) {
			state.topic = null
			renderTopic()
			state.topic = await api(`/topics/${r.qid}`)
			state.topic.findings.forEach(applyLocal)
			state.sql.topic = state.topic.sql
		}
		if (!LANGS.includes(r.lang) || !LANGS.includes(r.rich) || r.lang === r.rich) {
			const f = state.topic.findings.find((x) => x.status === 'open' && (!LANGS.includes(r.lang) || x.lang === r.lang)) || state.topic.findings[0]
			const lang = LANGS.includes(r.lang) ? r.lang : f?.lang || 'en'
			const rich = f && f.lang === lang && f.other_lang ? f.other_lang : LANGS.find((l) => l !== lang && state.topic.titles[l])
			return void location.replace(href({ ...r, lang, rich }))
		}
		if (!prev || prev.qid !== r.qid || prev.lang !== r.lang || prev.rich !== r.rich) {
			state.compare = state.timeline = state.editing = null
			state.types.clear()
		}
		state.tabError = null
		if (r.tab === 'compare' && (!state.compare || state.compare.key !== `${r.asOf}`)) {
			state.compare = null
			renderTopic()
			const asOf = r.asOf ? `&as_of=${r.asOf}-01-01` : ''
			const [c, tl] = await Promise.all([
				api(`/topics/${r.qid}/compare?a=${r.rich}&b=${r.lang}${asOf}`),
				state.timeline ? state.timeline : api(`/topics/${r.qid}/timeline?lang=${r.lang}&rich_lang=${r.rich}`).catch(() => null),
			])
			state.compare = c
			state.timeline = tl
			state.compare.key = `${r.asOf}`
		}
		if (r.tab === 'timeline' && !state.timeline) {
			renderTopic()
			state.timeline = await api(`/topics/${r.qid}/timeline?lang=${r.lang}&rich_lang=${r.rich}`)
		}
	} catch (e) {
		if (token !== seq) return
		if (!state.topic) return void (el.topic.innerHTML = `<p class="empty error">Could not load the topic: ${esc(e.message)}</p>`)
		state.tabError = e
	}
	if (token !== seq) return
	state.sql.tab = r.tab === 'compare' ? state.compare?.sql : r.tab === 'timeline' ? state.timeline?.sql : null
	renderTopic()
	renderSql()
}

// ---------- queue ----------

const PAGE = 100
const QUALITY = { Suositeltu: 'featured article', 'Hyvä artikkeli': 'good article', Utmärkt: 'featured article', Bra: 'good article', Featured: 'featured article', Good: 'good article' }
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`
const qualityTag = (l, label) => `<span title="${esc(NAMES[l])} Wikipedia rates its article a ${esc(QUALITY[label] || label)}">${l} ${esc(label)}</span>`

// Search returns one row per topic, in its highest-scoring edition. Under an edition filter the
// topic is still wanted, so link it to that edition and leave the score out.
function asEdition(i, lang) {
	if (lang === 'all' || i.lang === lang) return i
	return { ...i, lang, rich_lang: i.rich_lang === lang ? i.lang : i.rich_lang, score: null, readers: null, coverage: null, findings: 0, other: i.lang }
}

async function loadQueue(more = false) {
	try {
		const offset = more ? state.items.length : 0
		const data = state.q
			? await api(`/search?q=${encodeURIComponent(state.q)}&lang=${state.lang}`)
			: await api(`/queue?lang=${state.lang}&limit=${PAGE}&offset=${offset}`)
		const items = state.q ? data.items.map((i) => asEdition(i, state.lang)) : data.items
		state.items = more ? state.items.concat(items) : items
		state.total = state.q ? state.items.length : data.total ?? state.items.length
		state.asOf = data.as_of || state.asOf
		state.sql.queue = data.sql
		state.sqlLabel = state.q ? 'Search: the rows are passages; the list groups them by topic' : 'Queue'
		if (!more) syncUrl()
	} catch (e) {
		if (state.q && e.status === 404) {
			state.searchable = false
			state.q = ''
			return loadQueue()
		}
		el.queue.innerHTML = `<p class="empty error">Could not load the queue: ${esc(e.message)}</p>`
		return
	}
	renderQueue()
	renderSql()
	if (!state.route) onRoute()
}

function scoreWhy(i) {
	if (i.score == null) return `Search match; open it to see the ${NAMES[i.lang]} differences`
	if (!i.readers) return 'Not ranked yet: page views are still loading'
	return `${fmt(i.readers)} views/yr × ${+(i.weight ?? i.score / i.readers).toFixed(2)}, the weight of its most checkable open difference (${TYPES[i.top_type] || i.top_type})`
}

function renderQueue() {
	const r = state.route
	const focused = document.activeElement?.id === 'q'
	el.queue.innerHTML = `
		<div class="pane-head">
			<div>
				<h2>Differences to review</h2>
				<p class="muted small">${state.q ? plural(state.total, 'matching topic', 'matching topics') : plural(state.total, 'article pair with an open difference', 'article pairs with an open difference')}${state.asOf ? `, data as of ${esc(state.asOf)}` : ''}.</p>
				<p class="muted small">Score = page views of the edition in the last 12 months × weight of its most checkable open difference. Dates come from the revision current on each 1 January, 2005–2026.</p>
			</div>
			<div class="seg" role="group" aria-label="The edition I write in">
				${['all', 'en', 'sv', 'fi'].map((l) => `<button data-lang="${l}" aria-pressed="${state.lang === l}">${l === 'all' ? 'Any edition' : NAMES[l]}</button>`).join('')}
			</div>
			${state.searchable ? `<input id="q" type="search" placeholder="Search topics, such as Lapua" value="${esc(state.q)}" autocomplete="off">` : ''}
		</div>
		<ol class="rows">
			${state.items.map((i) => {
				const cur = r && r.qid === i.wikidata_id && r.lang === i.lang
				return `<li><a href="${href({ qid: i.wikidata_id, lang: i.lang, rich: i.rich_lang, tab: r && cur ? r.tab : 'findings' })}" aria-current="${cur}">
					<span class="t">${esc(i.topic)} <span class="lang">${NAMES[i.lang]}</span></span>
					<span class="num score">${i.score == null ? '' : i.readers ? fmt(i.score) : '–'}</span>
					<span class="meta why">${esc(scoreWhy(i))}</span>
					<span class="meta">
						${i.coverage != null ? `<span class="bar" title="${pct(i.coverage)} of the ${NAMES[i.rich_lang]} passages have a close ${NAMES[i.lang]} match"><i style="width:${pct(i.coverage)}"></i></span><span>${pct(i.coverage)} of ${i.rich_lang}</span>` : ''}
						<span title="Article size now">${kb(i.size[i.lang])} vs ${i.rich_lang} ${kb(i.size[i.rich_lang])}</span>
						${[i.lang, i.rich_lang].filter((l) => i.quality?.[l]).map((l) => qualityTag(l, i.quality[l])).join('')}
						${i.findings ? chip('t-' + i.top_type, plural(i.findings, 'open difference', 'open differences')) : ''}
					</span>
				</a></li>`
			}).join('') || `<li class="empty">${state.q ? `No matching topics for “${esc(state.q)}”${state.lang !== 'all' ? ` with an open difference in the ${NAMES[state.lang]} article` : ''}.` : 'Nothing to review.'}</li>`}
		</ol>
		${!state.q && state.items.length < state.total ? `<p class="more-rows"><button class="btn sm outline" id="moreRows">Show ${Math.min(PAGE, state.total - state.items.length)} more of ${fmt(state.total - state.items.length)}</button></p>` : ''}`
	if (focused) {
		const q = document.getElementById('q')
		q.focus()
		q.setSelectionRange(q.value.length, q.value.length)
	}
}

// ---------- topic ----------

function renderTopic() {
	const t = state.topic, r = state.route
	if (!t) return void (el.topic.innerHTML = '<p class="empty">Loading…</p>')
	const third = LANGS.find((l) => l !== r.lang && l !== r.rich)
	document.title = `${t.topic} · ${NAMES[r.lang]} vs ${NAMES[r.rich]} · Since When`
	el.topic.innerHTML = `
		<div class="topic-head">
			<button class="btn sm outline narrow-only" id="showQueue">← All topics</button>
			<h2>${esc(t.topic)}</h2>
			<p>The <strong>${NAMES[r.lang]}</strong> article compared with the ${NAMES[r.rich]} one${t.readers[r.lang] ? `; the ${NAMES[r.lang]} one had ${fmt(t.readers[r.lang])} page views in the last 12 months` : ''}. <a href="${editLink(r.lang, t.titles[r.lang])}" target="_blank" rel="noopener" style="white-space:nowrap">Edit the ${NAMES[r.lang]} article</a></p>
			<div class="facts">
				<a href="https://www.wikidata.org/wiki/${t.wikidata_id}" target="_blank" rel="noopener">${t.wikidata_id}</a>
				${[r.lang, r.rich, third].filter((l) => t.titles[l]).map((l) => `<span><a href="${wpLink(l, t.titles[l])}" target="_blank" rel="noopener">${esc(t.titles[l])}</a> ${l} ${kb(t.size[l])}${t.refs?.[l] != null ? ` · ${t.refs[l]} refs` : ''}${t.quality?.[l] ? ' · ' + esc(t.quality[l]) : ''} · ${readers(t.readers[l])}</span>`).join('')}
			</div>
		</div>
		<nav class="tabs">
			${[['findings', 'Findings'], ['compare', 'Side by side'], ['timeline', 'Timeline']].map(([k, label]) => `<a href="${href(r, { tab: k, asOf: '' })}" aria-current="${r.tab === k}">${label}</a>`).join('')}
		</nav>
		<div id="tab">${state.tabError ? `<p class="empty error">${esc(state.tabError.status === 404 ? 'Not computed for this topic yet.' : state.tabError.message)}</p>` : r.tab === 'compare' ? compareView() : r.tab === 'timeline' ? timelineView() : findingsView(third)}</div>`
}

const TYPE_ORDER = ['contradiction', 'numbers', 'missing_fact', 'coverage', 'framing']
const OUTCOMES = {
	edited: ['Edited', 'closed'],
	talk: ['Raised on talk page', 'reviewed'],
	intentional: ['Intentional difference', 'closed'],
	not_real: ['Not a real difference', 'closed'],
}
const TALK = { en: 'Talk:', sv: 'Diskussion:', fi: 'Keskustelu:' }
const anchor = (section) => (section ? '#' + encodeURIComponent(section.split(' › ').pop().replace(/ /g, '_')) : '')
const ATTRIBUTION = {
	en: (from, title) => `Content in this edit is translated from the existing ${NAMES[from]} Wikipedia article at [[:${from}:${title}]]; see its history for attribution.`,
	sv: (from, title) => `Innehållet i denna redigering är översatt från den befintliga artikeln [[:${from}:${title}]] på ${{ fi: 'finskspråkiga', en: 'engelskspråkiga' }[from]} Wikipedia; se dess historik för attribution.`,
	fi: (from, title) => `Tämän muokkauksen sisältö on käännetty ${{ sv: 'ruotsinkielisen', en: 'englanninkielisen' }[from]} Wikipedian artikkelista [[:${from}:${title}]]; katso sen historia tekijätietoja varten.`,
}

function findingsView(third) {
	const t = state.topic, r = state.route
	// The address names the edition reviewed and the one it is compared with: show that pair, as the queue counts it.
	const order = (a, b) => TYPE_ORDER.indexOf(a.type) - TYPE_ORDER.indexOf(b.type) || (b.weight ?? 0) - (a.weight ?? 0) || b.score - a.score
	const all = t.findings.filter((f) => f.lang === r.lang && (!f.other_lang || f.other_lang === r.rich)).sort(order)
	const pair = all.filter((f) => f.status === 'open')
	const done = all.filter((f) => f.status !== 'open')
	const reverse = t.findings.filter((f) => f.lang === r.rich && f.other_lang === r.lang && f.status === 'open').sort(order)
	const types = TYPE_ORDER.filter((k) => pair.some((f) => f.type === k))
	const mine = pair.filter((f) => !state.types.size || state.types.has(f.type))
	const other = t.findings.filter((f) => !all.includes(f) && !reverse.includes(f))
	// The queue counts every open difference of the edition; name the ones against the third edition so the numbers add up.
	const sibling = third && t.findings.filter((f) => f.lang === r.lang && f.other_lang === third && f.status === 'open').length
	// Without a type filter, each type shows its strongest few, so the framing cards are not buried below dozens of facts.
	const PER_TYPE = 3
	const shown = state.types.size ? mine : types.flatMap((k) => {
		const of = mine.filter((f) => f.type === k)
		return of.length > PER_TYPE ? [...of.slice(0, PER_TYPE), { more: k, n: of.length }] : of
	})
	const quotesFor = (l) => t.findings.flatMap((f) => (f.quotes[l] ? [f.quotes[l]] : []))
	const terms = [...new Set(t.findings.flatMap((f) => f.terms || []))]
	const lead = (l) => `
		${!t.leads?.[l] ? '' : `<div class="lead ${l === r.lang ? 'fix' : ''}">
			<span class="label">${NAMES[l]} lead${t.quality?.[l] ? ` · <span title="${esc(NAMES[l])} Wikipedia rates its article a ${esc(QUALITY[t.quality[l]] || t.quality[l])}">${esc(t.quality[l])}</span>` : ''}</span>
			<p lang="${l}" class="clip lead-text ${state.open.has('lead-' + l) ? 'open' : ''}" data-clip="lead-${l}">${highlight(t.leads[l].text, quotesFor(l), terms)}</p>
			${t.leads[l].also ? `<p lang="${l}" class="muted small">… ${highlight(t.leads[l].also, quotesFor(l), terms)}</p>` : ''}
		</div>`}`
	return `
		<div class="leads">${[r.lang, r.rich, third].map(lead).join('')}</div>
		<div class="controls">
			<h3>${plural(pair.length, 'open difference', 'open differences')} between ${NAMES[r.lang]} and ${NAMES[r.rich]}${sibling ? ` <span class="muted small">· ${sibling} more against <a href="${href(r, { rich: third, tab: 'findings' })}">${NAMES[third]}</a></span>` : ''}</h3>
			<span class="grow"></span>
			${types.length > 1 ? `<span class="seg" role="group" aria-label="Type of difference">${types.map((k) => `<button data-type="${k}" aria-pressed="${state.types.has(k)}">${TYPES[k]} ${pair.filter((f) => f.type === k).length}</button>`).join('')}</span>` : ''}
		</div>
		<div class="findings">${shown.map((f) => (f.more ? `<button class="btn sm outline more-type" data-type="${f.more}">All ${f.n} · ${TYPES[f.more]}</button>` : findingCard(f))).join('') || `<p class="muted">No open differences ${state.types.size ? 'of this kind' : `in the ${NAMES[r.lang]} article against ${NAMES[r.rich]}`}${reverse.length ? '; see below for what the ' + NAMES[r.rich] + ' article lacks' : ''}.</p>`}</div>
		${reverse.length ? `<details class="more" ${pair.length ? '' : 'open'}><summary>${plural(reverse.length, 'open difference', 'open differences')} where ${NAMES[r.lang]} is the fuller side (to fix in the ${NAMES[r.rich]} article)</summary><div class="findings">${reverse.map(findingCard).join('')}</div></details>` : ''}
		${done.length ? `<details class="more" ${state.openDone ? 'open' : ''}><summary>${plural(done.length, 'difference', 'differences')} already reviewed or closed</summary><div class="findings">${done.map(findingCard).join('')}</div></details>` : ''}
		${other.length ? `<details class="more"><summary>${plural(other.length, 'difference', 'differences')} for other pairs of editions</summary><div class="findings">${other.map(findingCard).join('')}</div></details>` : ''}`
}

// Coverage findings name the section of the passage the other edition lacks; the edition to fix has none.
function sectionOf(f, l) {
	if (f.type === 'coverage') return l === f.lang ? undefined : f.section
	return l === f.lang ? f.section : f.other_section
}

function talkNote(f) {
	const t = state.topic
	return [f.other_lang, f.lang].filter((l) => f.quotes[l]).map((l) => `* [[:${l}:${t.titles[l]}${sectionOf(f, l) ? '#' + sectionOf(f, l).split(' › ').pop() : ''}]]: "${f.quotes[l]}"`).join('\n')
}

function findingCard(f) {
	const t = state.topic
	// Finnish puts references at paragraph ends, so a sentence without one is often still sourced:
	// fall back to the paragraph's reference, and warn only when the paragraph has none either.
	const cite = (l) => {
		if (!f.citations || !(l in f.citations)) return ''
		if (f.citations[l]) return `<p class="cite">Cites: ${esc(f.citations[l])}</p>`
		const para = f.paragraph_citations
		if (para && para[l]) return `<p class="cite">No citation on this sentence; the end of its paragraph cites ${esc(para[l])}</p>`
		if (para && l in para) return '<p class="cite none">No citation on this sentence or at the end of its paragraph</p>'
		return '<p class="cite">No citation on this sentence</p>'
	}
	const quote = (l, cls) => {
		const sec = sectionOf(f, l)
		const url = f.rev_ids?.[l] ? `https://${l}.wikipedia.org/w/index.php?oldid=${f.rev_ids[l]}${anchor(sec)}` : `${wpLink(l, t.titles[l])}${anchor(sec)}`
		const head = `<span class="label">${NAMES[l]} · <a href="${url}" target="_blank" rel="noopener" title="Open ${f.rev_ids?.[l] ? 'the revision this quote is from' : 'the article'} on ${NAMES[l]} Wikipedia">${sec === undefined ? 'article' : esc(sectionName(sec).split(' › ').pop())}</a></span>`
		if (!f.quotes[l]) return `<div class="quote ${cls}">${head}<p class="muted">${f.type === 'coverage' && l === f.lang ? 'No close passage' : 'No quote stored for this edition'}</p></div>`
		const cut = !/[.!?…:;"”»)]\s*$/.test(f.quotes[l]) && f.quotes[l].length > 200   // a quote cut short by the API, not a sentence fragment
		return `<div class="quote ${cls}">${head}<p lang="${l}">${highlight(f.quotes[l], [], f.terms || [])}${cut ? '…' : ''}</p>${cite(l)}</div>`
	}
	const outcome = f.outcome && OUTCOMES[f.outcome] ? OUTCOMES[f.outcome][0] : f.status === 'closed' ? 'Closed' : f.status === 'reviewed' ? 'Reviewed' : null
	const editing = state.editing === f.id
	return `
		<article class="finding ${f.status}">
			<div class="row">
				${chip('t-' + f.type, TYPES[f.type] || f.type)}
				${(f.terms || []).map((w) => `<span class="badge">${esc(w)}</span>`).join('')}
				<span class="muted small">${NAMES[f.lang]} vs ${NAMES[f.other_lang]} · ${esc(f.history === false ? 'in the current text; earlier years not compared yet' : rangeLabel(f.opened_after, f.opened_at, 'opened_after' in f) ? 'opened ' + rangeLabel(f.opened_after, f.opened_at, true) : sinceLabel(f.opened_at))}${f.closed_at && 'closed_after' in f ? esc(' · closed ' + rangeLabel(f.closed_after, f.closed_at, true)) : ''}</span>
				<span class="grow"></span>
				${[f.lang, f.other_lang].map((l) => `<a class="small" href="${wpLink(l, TALK[l] + t.titles[l])}" target="_blank" rel="noopener">${l} talk page</a>`).join(' · ')}
			</div>
			<div class="quotes">${quote(f.lang, 'fix')}${quote(f.other_lang, 'rich')}</div>
			<p class="suggestion"><span class="label">Machine suggestion</span> ${esc(f.summary)}</p>
			<div class="row actions">
				${outcome
					? `<span class="small">Outcome: <strong>${esc(outcome)}</strong>${f.rev_url ? ` · <a href="${esc(f.rev_url)}" target="_blank" rel="noopener">revision</a>` : ''}${f.local ? ' · <span class="muted" title="This site does not record outcomes for everyone">saved in this browser only</span>' : ''}</span><button class="btn sm outline" data-outcome="reopen" data-id="${f.id}">Reopen</button>`
					: editing
						? `<input class="rev" id="rev-${f.id}" placeholder="Link to your revision or diff" autocomplete="off"><button class="btn sm" data-outcome="edited" data-id="${f.id}">Save</button><button class="btn sm outline" data-cancel>Cancel</button>`
						: Object.entries(OUTCOMES).map(([k, [label]]) => `<button class="btn sm outline" data-outcome="${k}" data-id="${f.id}">${label}</button>`).join('')}
				<span class="grow"></span>
				<button class="btn sm outline" data-copy="attribution" data-id="${f.id}" title="Edit summary for content translated from the other edition">Copy attribution summary</button>
				<button class="btn sm outline" data-copy="note" data-id="${f.id}" title="The two quotes with links, for a talk page">Copy talk page note</button>
			</div>
		</article>`
}

// Years the timeline has coverage for; the address's own year stays selectable even when it has none.
function comparedYears(r) {
	const ys = state.timeline ? state.timeline.years.filter((p) => p.coverage != null).map((p) => p.year) : YEARS
	return r.asOf && !ys.includes(+r.asOf) ? [...ys, +r.asOf].sort() : ys
}

const revTag = (l, rev) => (rev ? ` · <a href="https://${l}.wikipedia.org/w/index.php?oldid=${rev}" target="_blank" rel="noopener">${l} revision ${rev}</a>` : '')

function compareView() {
	const c = state.compare, r = state.route
	if (!c) return '<p class="empty">Aligning passages…</p>'
	const counts = { covered: 0, partly: 0, missing: 0, pending: 0 }
	c.rows.forEach((x) => counts[x.status]++)
	const quotes = { [c.a]: state.topic.findings.flatMap((f) => (f.quotes[c.a] ? [f.quotes[c.a]] : [])), [c.b]: state.topic.findings.flatMap((f) => (f.quotes[c.b] ? [f.quotes[c.b]] : [])) }
	const terms = [...new Set(state.topic.findings.flatMap((f) => f.terms || []))]
	let last = null, body = ''
	c.rows.forEach((x, i) => {
		if (state.onlyGaps && (x.status === 'covered' || x.status === 'pending')) return
		const top = x.a.section.split(' › ')[0]
		if (top !== last) body += `<tr class="sec"><td colspan="3">${esc(sectionName(top))}</td></tr>`
		last = top
		const key = `${c.a}-${x.a.chunk_id}`
		body += `<tr>
			<td><div class="small muted">${esc(x.a.section.split(' › ').slice(1).join(' › '))}${revTag(c.a, x.a.rev_id)}</div><div class="clip ${state.open.has(key) ? 'open' : ''}" data-clip="${key}" lang="${c.a}">${highlight(x.a.text, quotes[c.a], terms)}</div></td>
			<td>${x.b ? `<div class="small muted">${esc(sectionName(x.b.section))}${revTag(c.b, x.b.rev_id)}</div><div class="clip ${state.open.has(key) ? 'open' : ''}" data-clip="${key}" lang="${c.b}">${highlight(x.b.text, quotes[c.b], terms)}</div>` : `<span class="none">${x.status === 'pending' ? `Not compared yet for this date` : `No close ${NAMES[c.b]} passage`}</span>`}</td>
			<td class="st">${chip('s-' + x.status, STATUS[x.status])}<div class="dist" title="Cosine distance between the two passages' bge-m3 vectors: 0 means the same meaning">${x.distance != null ? 'distance ' + x.distance.toFixed(2) : ''}</div></td>
		</tr>`
	})
	return `
		<div class="controls">
			<label>Both editions as of
				<select id="asof">
					<option value="">today</option>
					${comparedYears(r).slice().reverse().map((y) => `<option value="${y}" ${String(y) === r.asOf ? 'selected' : ''}>1 January ${y}${state.timeline && !state.timeline.years.some((p) => p.year === y && p.coverage != null) ? ' (not compared yet)' : ''}</option>`).join('')}
				</select>
			</label>
			<label><input type="checkbox" id="onlyGaps" ${state.onlyGaps ? 'checked' : ''}> Only gaps</label>
			<span class="grow"></span>
			<span class="small muted">${plural(c.rows.length, NAMES[c.a] + ' passage', NAMES[c.a] + ' passages')}: ${chip('s-covered', counts.covered + ' covered')} ${chip('s-partly', counts.partly + ' partly')} ${chip('s-missing', counts.missing + ' no match')}${counts.pending ? ' ' + chip('s-pending', counts.pending + ' not compared yet') : ''}</span>
		</div>
		<p class="small muted legend-line">Each ${NAMES[c.a]} passage with the ${NAMES[c.b]} passage nearest in meaning (bge-m3 vectors, cosine distance: 0 is the same meaning). Covered at 0.30 or less, partly at 0.38 or less. Click a passage to read it all; the revision links show the text as it stood.</p>
		${c.fixture_note ? `<p class="note">${esc(c.fixture_note)}</p>` : ''}
		${c.fixture ? '<p class="note">Fixture: the passages are real Wikipedia text, but the matches and distances are made by hand until bge-m3 distances come from MariaDB. Click a passage to read it all.</p>' : ''}
		<table class="align">
			<thead><tr><th>${NAMES[c.a]} passage</th><th>Closest ${NAMES[c.b]} passage</th><th class="st">Match</th></tr></thead>
			<tbody>${body}</tbody>
		</table>`
}

function lineChart({ series, max, yTicks, yFmt, events = [], height = 170 }) {
	const W = 720, L = 46, R = 70, T = 10, B = 22, H = height
	const x = (yr) => L + ((yr - 2005) / 21) * (W - L - R)
	const y = (v) => T + (1 - v / max) * (H - T - B)
	let s = ''
	for (const v of yTicks) s += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--grid)"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${yFmt(v)}</text>`
	for (const yr of [2005, 2010, 2015, 2020, 2026]) s += `<text x="${x(yr)}" y="${H - 4}" text-anchor="middle">${yr}</text>`
	for (const e of events) {
		const d = new Date(e.date), fx = x(d.getUTCFullYear() + (d - Date.UTC(d.getUTCFullYear(), 0, 1)) / 31557600000)
		s += `<line x1="${fx}" x2="${fx}" y1="${T}" y2="${H - B}" stroke="${e.kind === 'closed' ? '#15803d' : 'var(--term)'}" stroke-dasharray="3 3"><title>${esc('after' in e ? rangeLabel(e.after, e.date, true) : dateLabel(e.date))}: ${esc(e.summary)}</title></line>`
	}
	const ends = []
	for (const sr of series) {
		const pts = sr.values.map((v, i) => (v == null ? null : [x(2005 + i), y(v)]))
		const d = pts.map((p, i) => (p ? `${i && pts[i - 1] ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}` : '')).join('')
		s += `<path d="${d}" fill="none" stroke="${sr.color}" stroke-width="${sr.width || 1.5}"/>`
		const lastV = sr.values[sr.values.length - 1]
		if (lastV != null) ends.push({ label: sr.label, color: sr.color, y: y(lastV) })
	}
	ends.sort((a, b) => a.y - b.y)
	for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 21) ends[i].y = ends[i - 1].y + 21   // room for the larger phone labels
	const over = ends.length ? ends[ends.length - 1].y - (H - B - 4) : 0   // keep the bottom label above the year axis
	if (over > 0) ends.forEach((e) => (e.y -= over))
	for (const e of ends) s += `<text x="${W - R + 6}" y="${e.y + 4}" style="fill:${e.color}">${esc(e.label)}</text>`
	for (const yr of YEARS) s += `<rect class="yr" data-year="${yr}" x="${x(yr) - (W - L - R) / 42}" y="${T}" width="${(W - L - R) / 21}" height="${H - T - B}"><title>1 January ${yr}: compare side by side as of this date</title></rect>`
	return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img">${s}</svg>`
}

// A 1 January event names the revision current that day; a dated event names the edit itself.
function eventLinks(e, r) {
	const l = e.rev_lang || r.lang
	const links = []
	if (e.diffs?.length) {
		for (const d of e.diffs) links.push(`<a href="https://${d.lang}.wikipedia.org/w/index.php?diff=${d.rev_id}&oldid=${d.old_rev_id}" target="_blank" rel="noopener" title="All ${NAMES[d.lang]} edits between the two compared revisions">${d.lang} diff</a>`)
		return ` <span class="small">${links.join(' · ')}</span>`
	}
	if ('after' in e && !e.rev_url) {   // dated by the API: no diffs means it held at the first comparison
		if (e.rev_id) links.push(`<a href="https://${l}.wikipedia.org/w/index.php?oldid=${e.rev_id}" target="_blank" rel="noopener">${l} revision ${e.rev_id}</a>`)
		return links.length ? ` <span class="small">${links.join(' · ')}</span>` : ''
	}
	if (e.rev_url) links.push(`<a href="${esc(e.rev_url)}" target="_blank" rel="noopener">revision</a>`)
	if (e.rev_id && e.date.endsWith('-01-01')) {
		links.push(`<a href="https://${l}.wikipedia.org/w/index.php?oldid=${e.rev_id}" target="_blank" rel="noopener">${l} as of that day</a>`)
		links.push(`<a href="${historyLink(l, state.topic?.titles[l], e.date)}" target="_blank" rel="noopener">${l} edits before</a>`)
	} else if (e.rev_id) links.push(`<a href="https://${l}.wikipedia.org/w/index.php?diff=prev&oldid=${e.rev_id}" target="_blank" rel="noopener">${l} diff</a>`)
	else if (!e.rev_url) links.push(...[r.lang, r.rich].map((x) => `<a href="${historyLink(x, state.topic?.titles[x], e.date)}" target="_blank" rel="noopener">${x} edits before</a>`))
	return ` <span class="small">${links.join(' · ')}</span>`
}

function niceMax(v) {
	const step = v > 100000 ? 50000 : v > 40000 ? 20000 : v > 10000 ? 5000 : 2000
	return [Math.ceil(v / step) * step, step]
}

function timelineView() {
	const tl = state.timeline, r = state.route
	if (!tl) return '<p class="empty">Reading every 1 January…</p>'
	const color = (l) => (l === r.lang ? 'var(--fix)' : l === r.rich ? 'var(--rich)' : 'var(--context)')
	const [max, step] = niceMax(Math.max(...tl.years.flatMap((p) => Object.values(p.size))))
	const sizes = lineChart({
		series: ['fi', 'sv', 'en'].map((l) => ({ label: NAMES[l], color: color(l), width: l === r.lang ? 2.2 : 1.5, values: tl.years.map((p) => p.size[l]) })),
		max, yTicks: Array.from({ length: max / step + 1 }, (_, i) => i * step), yFmt: (v) => (v ? v / 1000 + ' KB' : '0'),
	})
	const cov = lineChart({
		series: [{ label: NAMES[r.lang], color: 'var(--fix)', width: 2.2, values: tl.years.map((p) => p.coverage) }],
		max: 1, yTicks: [0, 0.25, 0.5, 0.75, 1], yFmt: pct, events: tl.events, height: 150,
	})
	const findings = Object.fromEntries((state.topic?.findings || []).map((f) => [f.id, f]))
	return `
		<h3>Share of the ${NAMES[r.rich]} article with a close ${NAMES[r.lang]} passage, on each 1 January</h3>
		<div class="legend"><span><i style="background:var(--fix)"></i>coverage</span><span><i style="background:var(--term)"></i>a finding opened</span><span><i style="background:#15803d"></i>a finding closed</span><span>Click a year to compare the editions as they stood then.</span></div>
		${cov}
		<h3 class="section-title">Article size in each edition</h3>
		${sizes}
		<h3 class="section-title">When each difference opened and closed</h3>
		<ul class="events">
			${tl.events.map((e) => `<li>
				${'after' in e
					? `<span class="mono" title="The change is in the edits after the last 1 January compared without it, up to the revision that first shows it">${esc(rangeLabel(e.after, e.date, true))}</span>`
					: `<span class="mono" title="${e.date.endsWith('-01-01') ? 'Read from the revisions current on 1 January; the edit happened during the year before' : 'Date of the edit'}">${esc(dateLabel(e.date))}</span>`}
				<span class="kind-${e.kind}">${esc(e.kind)}</span>
				<span>${chip('t-' + (e.type || findings[e.finding_id]?.type || 'coverage'), TYPES[e.type || findings[e.finding_id]?.type] || 'Finding')} ${esc(e.summary)}${eventLinks(e, r)}</span>
			</li>`).join('') || '<li class="muted">No findings for this pair.</li>'}
		</ul>
		${tl.fixture ? '<p class="note" style="margin-top:12px">Fixture: sizes and the dated edits are real (MediaWiki API, revision current on each 1 January); coverage before 2026 is scaled from the size ratio until MariaDB computes it per year.</p>' : ''}`
}

// ---------- SQL panel ----------

function sqlHtml(q) {
	return esc(q).split('\n').map((line) => {
		const i = line.indexOf('--')
		const code = i >= 0 ? line.slice(0, i) : line, comment = i >= 0 ? line.slice(i) : ''
		return code
			.replace(/(&#39;[^&]*?&#39;)/g, '<span class="st">$1</span>')
			.replace(/\b(SELECT|FROM|WHERE|JOIN|LEFT|ON|AND|OR|AS|OF|FOR|SYSTEM_TIME|ALL|GROUP BY|ORDER BY|LIMIT|OFFSET|HAVING|SET|TIMESTAMP|UPDATE|WITH|OVER|PARTITION BY|COUNT|MIN|AVG|SUM|LEAST|ROUND|COALESCE|ROW_NUMBER|VEC_DISTANCE_COSINE|VEC_FromText|DESC|BY)\b/g, '<span class="kw">$1</span>')
			+ (comment ? `<span class="cm">${comment}</span>` : '')
	}).join('\n')
}

// Live SQL: three preset statements the API runs as a SELECT-only user (GET /api/sql/presets,
// POST /api/sql/run). Without that user the section is absent and the panel is the log alone.
const DEMO = { Q1412941: 'Lapua Movement', Q736268: 'Finnish War', Q2457646: 'Diet of Porvoo' }
const LIVE_LABEL = { qid: 'Topic', date: 'As of', lang: 'Edition', a: 'Passages in', b: 'Nearest in' }
const LIVE_OK = { qid: /^Q[0-9]+$/, date: /^\d{4}-\d\d-\d\d$/, lang: /^(fi|sv|en)$/ }
const live = { presets: [], name: null, values: {}, runs: {}, error: null, running: false, asked: params.get('sql') }

// ?sql=<preset>,<values in the preset's order> opens the panel with that preset filled in.
async function loadLive() {
	const asked = live.asked
	try {
		const d = await api('/sql/presets')
		if (!d.enabled) throw new Error('no read-only user')
		Object.assign(live, { presets: d.presets, limits: d.limits, asked: null })
	} catch {
		live.asked = null
		return syncUrl()
	}
	for (const p of live.presets) live.values[p.name] = Object.fromEntries(p.params.map((x) => [x.name, x.default]))
	const [name, ...given] = (asked || '').split(',')
	const p = live.presets.find((x) => x.name === name) || live.presets[0]
	live.name = p.name
	if (p.name === name) p.params.forEach((x, i) => { if (LIVE_OK[x.kind].test(given[i] || '')) live.values[name][x.name] = given[i] })
	asked === null ? renderSql() : toggleSql(true)
}

function liveField(x, v) {
	const at = `data-live="${x.name}"`
	if (x.kind === 'date') return `<label>${LIVE_LABEL[x.name]} <input type="date" ${at} value="${esc(v[x.name])}" min="2001-01-15" max="${new Date().toISOString().slice(0, 10)}" required></label>`
	const topics = { ...DEMO, ...(state.topic && state.route ? { [state.route.qid]: state.topic.titles.en || state.topic.titles.fi || state.route.qid } : {}) }
	const opts = x.kind === 'lang' ? LANGS.map((l) => [l, NAMES[l]]) : Object.entries({ ...topics, [v.qid]: topics[v.qid] || v.qid })
	return `<label>${LIVE_LABEL[x.name]} <select ${at}>${opts.map(([k, n]) => `<option value="${esc(k)}"${k === v[x.name] ? ' selected' : ''}>${esc(n)}</option>`).join('')}</select></label>`
}

function liveCell(col, x) {
	if (x === null) return '<td class="muted">NULL</td>'
	if (typeof x === 'number') return `<td class="num">${Number.isInteger(x) ? x : x.toFixed(4)}</td>`
	const s = String(x)
	// Datetimes wrap at the space, so a history's three columns leave room for the text in the drawer.
	if (/^\d{4}-\d\d-\d\dT/.test(s)) return `<td class="when">${esc(s.replace('T', ' '))}${col === 'row_end' && s.startsWith('2106-') ? ' <span class="muted">current</span>' : ''}</td>`
	return `<td${s.length > 40 ? ' class="txt"' : ''}>${esc(s)}</td>`
}

function liveRun(run, previous) {
	return `
		<p class="small ran">${previous ? '<span class="label">Previous run</span> ' : ''}<strong>${run.rows.length} row${run.rows.length === 1 ? '' : 's'}</strong> · <span class="num">${run.ms} ms</span> on the server · ${esc(Object.values(run.params).join(' · '))}${run.capped ? ` · first ${run.limits.rows} rows` : ''}</p>
		${previous ? '' : run.sql.map((q) => `
			<section class="q">
				<header><span><strong>${esc(q.label)}</strong></span><span class="muted num">${q.ms} ms · ${q.rows} rows</span></header>
				<pre>${sqlHtml(q.query)}</pre>
			</section>`).join('')}
		<div class="result" tabindex="0"><table>
			<thead><tr>${run.columns.map((c) => `<th>${esc(c)}</th>`).join('')}</tr></thead>
			<tbody>${run.rows.map((row) => `<tr>${row.map((x, i) => liveCell(run.columns[i], x)).join('')}</tr>`).join('') || `<tr><td class="muted" colspan="${run.columns.length}">No rows.</td></tr>`}</tbody>
		</table></div>`
}

function liveHtml() {
	if (!live.name) return ''
	const p = live.presets.find((x) => x.name === live.name), v = live.values[p.name]
	return `
		<section class="live">
			<h3>Run a statement on MariaDB</h3>
			<div class="seg">${live.presets.map((x) => `<button type="button" data-preset="${x.name}" aria-pressed="${x.name === p.name}">${esc(x.title)}</button>`).join('')}</div>
			<p class="small">${esc(p.description)}</p>
			<form id="liveForm" class="controls">
				${p.params.map((x) => liveField(x, v)).join('')}
				<button class="btn sm" type="submit"${live.running ? ' disabled' : ''}>${live.running ? 'Running…' : 'Run'}</button>
			</form>
			${live.error ? `<p class="small error">${esc(live.error)}</p>` : ''}
			${(live.runs[p.name] || []).map((run, i) => liveRun(run, i > 0)).join('')}
			<p class="muted small">Runs as a SELECT-only database user · stops after ${live.limits.seconds} s · ${live.limits.rows} rows at most.</p>
		</section>`
}

function renderSql() {
	if (el.sql.hidden) return
	const groups = [[state.sqlLabel || 'Queue', state.sql.queue], ['Topic', state.sql.topic], ['This tab', state.sql.tab], ['Last change', state.sql.action]]
	el.sql.innerHTML = `
		<div class="sqlhead"><h2>SQL behind this screen</h2><button class="btn sm outline" id="sqlClose">Close</button></div>
		${liveHtml()}
		<p class="muted small" style="margin-bottom:10px">Every query MariaDB ran for what you see, with its time and row count.</p>
		${groups.flatMap(([g, qs]) => (qs || []).map((q) => `
			<section class="q">
				<header><span><strong>${esc(q.label)}</strong> <span class="muted">${g}</span></span><span class="muted num">${q.ms} ms · ${q.rows} rows</span></header>
				<pre>${sqlHtml(q.query)}</pre>
			</section>`)).join('')}`
}

function toggleSql(open) {
	el.sql.hidden = !open
	el.layout.classList.toggle('with-sql', open)
	const b = document.getElementById('sqlToggle')
	b.setAttribute('aria-expanded', open)
	b.textContent = open ? 'Hide SQL' : 'Show SQL'
	syncUrl()
	renderSql()
}

// ---------- events ----------

let searchTimer
document.addEventListener('input', (e) => {
	if (e.target.id !== 'q') return
	clearTimeout(searchTimer)
	searchTimer = setTimeout(() => { state.q = e.target.value.trim(); loadQueue() }, 200)
})
document.addEventListener('keydown', (e) => {
	if (e.key === 'Enter' && e.target.classList.contains('rev')) e.target.nextElementSibling.click()
})
document.addEventListener('change', (e) => {
	if (e.target.id === 'asof') location.hash = href(state.route, { tab: 'compare', asOf: e.target.value })
	if (e.target.id === 'onlyGaps') { state.onlyGaps = e.target.checked; renderTopic() }
	const k = e.target.dataset.live
	if (k) {
		const v = live.values[live.name], was = v[k]
		v[k] = e.target.value
		syncUrl()
		// A pair never matches an edition with itself: picking the other side's language swaps the two.
		if (v.a && v.a === v.b) { v[k === 'a' ? 'b' : 'a'] = was; syncUrl(); renderSql() }
	}
})
document.addEventListener('submit', async (e) => {
	if (e.target.id !== 'liveForm') return
	e.preventDefault()
	const name = live.name
	Object.assign(live, { running: true, error: null })
	renderSql()
	try {
		const run = await api('/sql/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ preset: name, params: live.values[name] }) })
		live.runs[name] = [run, ...(live.runs[name] || [])].slice(0, 2)
	} catch (err) {
		live.error = err.message
	}
	live.running = false
	renderSql()
})
document.addEventListener('click', async (e) => {
	const t = e.target
	if (t.closest('#sqlToggle')) return toggleSql(el.sql.hidden)
	if (t.closest('#sqlClose')) return toggleSql(false)
	const preset = t.closest('[data-preset]')
	if (preset) { Object.assign(live, { name: preset.dataset.preset, error: null }); syncUrl(); return renderSql() }
	if (t.closest('#showQueue')) return void el.layout.classList.add('queue-open')
	const seg = t.closest('[data-lang]')
	if (seg) { state.lang = seg.dataset.lang; localStorage.setItem('gapfinder.lang', state.lang); return loadQueue() }
	if (t.closest('#moreRows')) return loadQueue(true)
	const yr = t.closest('.yr')
	if (yr) return void (location.hash = href(state.route, { tab: 'compare', asOf: yr.dataset.year }))
	const clip = t.closest('[data-clip]')
	if (clip && !t.closest('a')) {
		const k = clip.dataset.clip
		state.open.has(k) ? state.open.delete(k) : state.open.add(k)
		document.querySelectorAll(`[data-clip="${k}"]`).forEach((n) => n.classList.toggle('open'))
		return
	}
	const dn = t.closest('details.more > summary')
	if (dn && dn.textContent.includes('already')) state.openDone = !dn.parentElement.open
	const ty = t.closest('[data-type]')
	if (ty) {
		const k = ty.dataset.type
		state.types.has(k) ? state.types.delete(k) : state.types.add(k)
		return renderTopic()
	}
	if (t.closest('[data-cancel]')) { state.editing = null; return renderTopic() }
	const cp = t.closest('[data-copy]')
	if (cp) {
		const f = state.topic.findings.find((x) => x.id === +cp.dataset.id)
		const text = cp.dataset.copy === 'note' ? talkNote(f) : ATTRIBUTION[f.lang](f.other_lang, state.topic.titles[f.other_lang])
		await copy(text)
		const label = cp.textContent
		cp.textContent = 'Copied'
		return void setTimeout(() => (cp.textContent = label), 1200)
	}
	const oc = t.closest('[data-outcome]')
	if (oc) {
		const id = +oc.dataset.id, outcome = oc.dataset.outcome
		if (outcome === 'edited' && state.editing !== id) { state.editing = id; renderTopic(); return document.getElementById(`rev-${id}`)?.focus() }
		const body = outcome === 'reopen' ? { status: 'open', outcome: null } : { status: OUTCOMES[outcome][1], outcome }
		if (outcome === 'edited') body.rev_url = document.getElementById(`rev-${id}`)?.value.trim() || null
		oc.disabled = true
		try {
			const f = await api(`/findings/${id}/status`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
			state.sql.action = f.sql
			delete f.sql
			// Keep the outcome locally when the API does not return it yet.
			if (!('outcome' in f)) Object.assign(f, { outcome: body.outcome, rev_url: body.rev_url })
			const i = state.topic.findings.findIndex((x) => x.id === f.id)
			if (i >= 0) state.topic.findings[i] = f
			state.editing = null
			state.timeline = null
			renderTopic()
			renderSql()
			loadQueue()
		} catch (err) {
			oc.disabled = false
			if (![403, 405, 501].includes(err.status)) return alert('Could not save the outcome: ' + err.message)
			LOCAL[id] = { status: body.status, outcome: body.outcome, rev_url: body.rev_url || null }
			localStorage.setItem('gapfinder.outcomes', JSON.stringify(LOCAL))
			applyLocal(state.topic.findings.find((x) => x.id === id))
			state.editing = null
			renderTopic()
		}
	}
})

async function copy(text) {
	try {
		await navigator.clipboard.writeText(text)
	} catch {
		const ta = Object.assign(document.createElement('textarea'), { value: text })
		document.body.append(ta)
		ta.select()
		document.execCommand('copy')
		ta.remove()
	}
}
window.addEventListener('hashchange', onRoute)
loadQueue()
loadLive()
