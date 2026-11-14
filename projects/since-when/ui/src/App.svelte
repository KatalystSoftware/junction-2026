<script lang="ts">
	import { onMount } from 'svelte'
	import { api, flags } from './lib/api.svelte'
	import { NAMES, articleUrl, kb, wikidataUrl } from './lib/format'
	import { thirdOf } from './lib/headline'
	import { href, log, nav, ui } from './lib/nav.svelte'
	import { loadQueue, queue } from './lib/queue.svelte'
	import { LANGS, isLang, type Lang, type Topic } from './lib/types'
	import Findings from './Findings.svelte'
	import Timeline from './Timeline.svelte'
	import TopicList from './TopicList.svelte'

	let loaded = $state<{ qid: string; topic: Topic } | null>(null)
	let failure = $state('')
	let seq = 0

	const route = $derived(nav.route)
	const qid = $derived(nav.route?.qid)
	const topic = $derived(loaded && loaded.qid === qid ? loaded.topic : null)
	const pair = $derived(route && isLang(route.lang) && isLang(route.rich) && route.lang !== route.rich ? { lang: route.lang, rich: route.rich } : null)
	// The three pairs of editions, each keeping the order the address already has.
	const pairs = $derived.by((): [Lang, Lang][] => {
		if (!pair) return []
		const third = thirdOf(pair.lang, pair.rich)!
		return [[pair.lang, pair.rich], [pair.lang, third], [pair.rich, third]]
	})

	onMount(() => void loadQueue())

	$effect(() => {
		const id = qid
		if (!id) return
		const token = ++seq
		failure = ''
		log.topic = []
		api<Topic>(`/topics/${encodeURIComponent(id)}`).then(
			(t) => {
				if (token !== seq) return
				loaded = { qid: id, topic: t }
				log.topic = t.sql ?? []
			},
			(e: Error) => {
				if (token === seq) failure = e.message
			},
		)
	})

	// An address without a topic opens the first one in the list.
	$effect(() => {
		const top = queue.items[0]
		if (!nav.route && top) location.replace(href({ qid: top.wikidata_id, lang: top.lang, rich: top.rich_lang, tab: 'findings' }))
	})

	// An address without two editions takes them from the topic's first open finding.
	$effect(() => {
		if (!topic || !route || pair) return
		const f = topic.findings.find((x) => x.status === 'open' && (!isLang(route.lang) || x.lang === route.lang)) ?? topic.findings[0]
		const lang = isLang(route.lang) ? route.lang : (f?.lang ?? 'en')
		const rich = f && f.lang === lang ? f.other_lang : (LANGS.find((l) => l !== lang && topic.titles[l]) ?? thirdOf(lang, lang)!)
		location.replace(href({ ...route, lang, rich }))
	})

	const views = (n?: number) => (n ? `${n.toLocaleString('en')} views a year` : '')

	function choosePair(e: Event) {
		const [lang, rich] = (e.currentTarget as HTMLSelectElement).value.split('/')
		if (route) location.hash = href(route, { lang, rich })
	}
</script>

<svelte:head>
	<title>{topic && pair ? `${topic.topic} · ${NAMES[pair.lang]} vs ${NAMES[pair.rich]} · Since When` : 'Since When'}</title>
</svelte:head>

<header class="bar">
	<div class="inner">
		<span class="brand">Since When</span>
		<button class="btn quiet" onclick={() => (ui.topics = true)}>Topics</button>
		<span class="grow"></span>
		{#if flags.fixture}<span class="fixture">Fixture data</span>{/if}
		<button class="btn" aria-expanded={ui.sql} aria-controls="sql-panel" onclick={() => (ui.sql = !ui.sql)}>SQL</button>
	</div>
</header>

<main>
	{#if failure}
		<p class="state error" role="alert">Could not load this topic: {failure}</p>
	{:else if !route && !queue.loading && !queue.items.length}
		<p class="state">{queue.error ? `Could not load the topics: ${queue.error}` : 'No topics yet.'}</p>
	{:else if !topic || !route || !pair}
		<p class="state subtle">Loading…</p>
	{:else}
		<div class="title">
			<h1>{topic.topic}</h1>
			<details class="facts small">
				<summary>Details</summary>
				<ul>
					{#each [pair.lang, pair.rich, thirdOf(pair.lang, pair.rich)!] as l}
						{#if topic.titles[l]}
							<li>
								<a href={articleUrl(l, topic.titles[l]!)} target="_blank" rel="noopener" lang={l}>{topic.titles[l]}</a>
								<span class="subtle">{[NAMES[l], topic.size[l] ? kb(topic.size[l]!) : '', topic.refs?.[l] != null ? `${topic.refs[l]} references` : '', topic.quality?.[l] ?? '', views(topic.readers[l])].filter(Boolean).join(' · ')}</span>
							</li>
						{/if}
					{/each}
					<li><a href={wikidataUrl(topic.wikidata_id)} target="_blank" rel="noopener">Wikidata {topic.wikidata_id}</a></li>
				</ul>
			</details>
		</div>
		<nav class="tabs" aria-label="Views">
			<a href={href(route, { tab: 'findings' })} aria-current={route.tab === 'findings' ? 'page' : undefined}>Differences</a>
			<a href={href(route, { tab: 'timeline' })} aria-current={route.tab === 'timeline' ? 'page' : undefined}>Timeline</a>
			<span class="grow"></span>
			<label class="pair">
				<span class="sr-only">Editions compared</span>
				<select class="field" onchange={choosePair}>
					{#each pairs as [a, b]}
						<option value="{a}/{b}" selected={a === pair.lang && b === pair.rich}>{NAMES[a]} and {NAMES[b]}</option>
					{/each}
				</select>
			</label>
		</nav>
		{#key `${route.qid}/${pair.lang}/${pair.rich}`}
			{#if route.tab === 'timeline'}
				<Timeline {topic} {route} lang={pair.lang} rich={pair.rich} />
			{:else}
				<Findings {topic} {route} lang={pair.lang} rich={pair.rich} />
			{/if}
		{/key}
	{/if}
</main>

<TopicList />

<style>
	.bar {
		border-bottom: 1px solid var(--border-color-subtle);
		background: var(--background-color-base);
	}

	.inner,
	main {
		max-width: 62rem;
		margin: 0 auto;
		padding: 0 var(--spacing-150);
	}

	.inner {
		display: flex;
		align-items: center;
		gap: var(--spacing-75);
		min-height: 3rem;
	}

	.brand {
		font-family: var(--font-family-serif);
		font-size: var(--font-size-x-large);
		color: var(--color-emphasized);
	}

	.grow {
		flex: 1;
	}

	.fixture {
		padding: 0 var(--spacing-50);
		border: 1px solid var(--border-color-warning);
		border-radius: var(--border-radius-base);
		background: var(--background-color-warning-subtle);
		font-size: var(--font-size-small);
		font-weight: var(--font-weight-bold);
	}

	main {
		padding-top: var(--spacing-150);
		padding-bottom: var(--spacing-400);
	}

	.state {
		padding: var(--spacing-300) 0;
	}

	.title {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0 var(--spacing-100);
	}

	h1 {
		flex: 1;
		font-size: var(--font-size-xxx-large);
		line-height: var(--line-height-xxx-large);
	}

	.facts summary {
		color: var(--color-subtle);
		cursor: pointer;
	}

	/* Open, the list takes a full row under the title instead of squeezing beside it. */
	.facts[open] {
		flex-basis: 100%;
		order: 1;
	}

	.facts ul {
		padding: var(--spacing-50) 0 var(--spacing-25);
	}

	.facts li {
		display: flex;
		flex-wrap: wrap;
		gap: 0 var(--spacing-50);
	}

	.tabs {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0 var(--spacing-100);
		margin-top: var(--spacing-25);
		border-bottom: 1px solid var(--border-color-subtle);
	}

	.tabs a {
		padding: var(--spacing-35) 0;
		margin-bottom: -1px;
		border-bottom: 2px solid transparent;
		font-size: var(--font-size-small);
		font-weight: var(--font-weight-bold);
		color: var(--color-subtle);
	}

	.tabs a:hover {
		color: var(--color-progressive);
		text-decoration: none;
	}

	.tabs a[aria-current='page'] {
		border-bottom-color: var(--border-color-progressive);
		color: var(--color-progressive);
	}

	.pair {
		padding: var(--spacing-25) 0;
	}

	@media (max-width: 640px) {
		.inner,
		main {
			padding-left: var(--spacing-100);
			padding-right: var(--spacing-100);
		}
	}
</style>
