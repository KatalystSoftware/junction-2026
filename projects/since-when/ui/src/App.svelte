<script lang="ts">
	import { onMount } from 'svelte'
	import { api, flags } from './lib/api.svelte'
	import { NAMES, articleUrl, kb, wikidataUrl } from './lib/format'
	import { href, log, nav, ui } from './lib/nav.svelte'
	import { loadQueue, queue } from './lib/queue.svelte'
	import { LANGS, type Timeline, type TimelineEvent, type Topic } from './lib/types'
	import Differences from './Differences.svelte'
	import SqlPanel from './SqlPanel.svelte'
	import TopicList from './TopicList.svelte'

	let loaded = $state<{ qid: string; topic: Topic } | null>(null)
	// The edits behind each difference, by finding. They arrive after the topic; until then a
	// difference shows its date without the link to the edit.
	let events = $state(new Map<number, TimelineEvent[]>())
	let failure = $state('')
	let seq = 0

	const qid = $derived(nav.route?.qid)
	const topic = $derived(loaded && loaded.qid === qid ? loaded.topic : null)

	onMount(() => void loadQueue())

	$effect(() => {
		const id = qid
		if (!id) return
		const token = ++seq
		failure = ''
		log.topic = []
		log.history = []
		events = new Map()
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
		// The API answers the history of one edition's rows at a time, so it is asked once for each.
		Promise.all(LANGS.map((l) => api<Timeline>(`/topics/${encodeURIComponent(id)}/timeline?lang=${l}&rich_lang=${LANGS.find((x) => x !== l)}`).catch(() => null))).then((answers) => {
			if (token !== seq) return
			const by = new Map<number, TimelineEvent[]>()
			for (const e of answers.flatMap((a) => a?.events ?? [])) by.set(e.finding_id, [...(by.get(e.finding_id) ?? []), e])
			events = by
			log.history = answers.flatMap((a, i) => (a?.sql ?? []).map((q) => ({ ...q, label: `${q.label} (${NAMES[LANGS[i]]})` })))
		})
	})

	// An address without a topic opens the first one in the list.
	$effect(() => {
		const top = queue.items[0]
		if (!nav.route && top) location.replace(href(top.wikidata_id))
	})

	const views = (n?: number) => (n ? `${n.toLocaleString('en')} views a year` : '')
</script>

<svelte:head>
	<title>{topic ? `${topic.topic} | Since When` : 'Since When'}</title>
</svelte:head>

<header class="bar">
	<div class="inner">
		<span class="brand">Since When</span>
		<button class="cdx-button cdx-button--action-progressive cdx-button--weight-quiet" onclick={() => (ui.topics = true)}>Topics</button>
		<span class="grow"></span>
		{#if flags.fixture}<span class="fixture">Fixture data</span>{/if}
		<button class="cdx-button" aria-haspopup="dialog" onclick={() => (ui.sql = true)}>SQL</button>
	</div>
</header>

<main>
	{#if failure}
		<div class="cdx-message cdx-message--block cdx-message--error" role="alert"><span class="cdx-message__icon"></span><div class="cdx-message__content">Could not load this topic: {failure}</div></div>
	{:else if !nav.route && !queue.loading && !queue.items.length}
		<p class="state">{queue.error ? `Could not load the topics: ${queue.error}` : 'No topics yet.'}</p>
	{:else if !topic}
		<p class="state subtle">Loading…</p>
	{:else}
		<h1>{topic.topic}</h1>
		{#key topic.wikidata_id}
			<Differences {topic} {events} />
		{/key}
		<section class="articles small" aria-labelledby="articles-title">
			<h2 id="articles-title">The articles compared</h2>
			<ul>
				{#each LANGS as l}
					{#if topic.titles[l]}
						<li>
							<a href={articleUrl(l, topic.titles[l]!)} target="_blank" rel="noopener" lang={l}>{topic.titles[l]}</a>
							<span class="subtle">{[NAMES[l], topic.size[l] ? kb(topic.size[l]!) : '', topic.refs?.[l] != null ? `${topic.refs[l]} references` : '', topic.quality?.[l] ?? '', views(topic.readers[l])].filter(Boolean).join(', ')}</span>
						</li>
					{/if}
				{/each}
				<li><a href={wikidataUrl(topic.wikidata_id)} target="_blank" rel="noopener">Wikidata {topic.wikidata_id}</a></li>
			</ul>
		</section>
	{/if}
</main>

<TopicList />
<SqlPanel {topic} />

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

	h1 {
		margin-bottom: var(--spacing-100);
		font-size: var(--font-size-xxx-large);
		line-height: var(--line-height-xxx-large);
	}

	.articles {
		margin-top: var(--spacing-300);
	}

	.articles h2 {
		font-family: inherit;
		font-size: inherit;
		font-weight: var(--font-weight-bold);
	}

	.articles li {
		display: flex;
		flex-wrap: wrap;
		gap: 0 var(--spacing-50);
	}

	@media (max-width: 640px) {
		.inner,
		main {
			padding-left: var(--spacing-100);
			padding-right: var(--spacing-100);
		}
	}
</style>
