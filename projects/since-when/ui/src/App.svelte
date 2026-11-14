<script lang="ts">
	import { onMount } from 'svelte'
	import { api, flags } from './lib/api.svelte'
	import { NAMES, articleUrl, kb, wikidataUrl } from './lib/format'
	import { log, nav, ui } from './lib/nav.svelte'
	import { loadQueue } from './lib/queue.svelte'
	import { LANGS, type Timeline, type TimelineEvent, type Topic } from './lib/types'
	import Differences from './Differences.svelte'
	import Front from './Front.svelte'
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

	const largest = $derived(Math.max(1, ...Object.values(topic?.size ?? {})))
</script>

<svelte:head>
	<title>{topic ? `${topic.topic} | Since When` : 'Since When'}</title>
</svelte:head>

<header class="bar">
	<div class="inner">
		<a class="brand" href="#/"
			><svg class="mark" viewBox="3.5 3.5 25 25" aria-hidden="true">
				<!-- The mark without its tile (favicon.svg has it): the question mark's dot starts a bar on the time strip. -->
				<path d="M10.5 10a5.5 5.5 0 1 1 7.5 5.1c-1.3.6-2 1.4-2 2.9" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" />
				<path d="M5 25H27" stroke="#a2a9b1" stroke-width="2" />
				<path d="M16 25H27" stroke="#ab7f2a" stroke-width="3" />
				<circle cx="16" cy="25" r="3.3" fill="#ab7f2a" />
			</svg>Since When</a
		>
		{#if nav.route}<button class="cdx-button cdx-button--action-progressive cdx-button--weight-quiet" onclick={() => (ui.topics = true)}>Topics</button>{/if}
		<span class="grow"></span>
		{#if flags.fixture}<span class="fixture">Fixture data</span>{/if}
		<button class="cdx-button" aria-haspopup="dialog" onclick={() => (ui.sql = true)}>SQL</button>
	</div>
</header>

<main>
	{#if !nav.route}
		<Front />
	{:else if failure}
		<div class="cdx-message cdx-message--block cdx-message--error" role="alert"><span class="cdx-message__icon"></span><div class="cdx-message__content">Could not load this topic: {failure}</div></div>
	{:else if !topic}
		<p class="state subtle">Loading…</p>
	{:else}
		<h1>{topic.topic}</h1>
		{#key topic.wikidata_id}
			<Differences {topic} {events} />
		{/key}
		<section class="articles small" aria-labelledby="articles-title">
			<h2 id="articles-title">Articles</h2>
			<table>
				<thead>
					<tr><th scope="col">Edition</th><th scope="col">Article</th><th scope="col" class="n" colspan="2">Size</th><th scope="col" class="n">References</th><th scope="col" class="n">Views a year</th></tr>
				</thead>
				<tbody>
					{#each LANGS as l}
						{#if topic.titles[l]}
							<tr>
								<th scope="row">{NAMES[l]}</th>
								<td>
									<a href={articleUrl(l, topic.titles[l]!)} target="_blank" rel="noopener" lang={l}>{topic.titles[l]}</a>
									{#if topic.quality?.[l]}<span class="subtle" lang={l}>{topic.quality[l]}</span>{/if}
								</td>
								<td class="n num">{topic.size[l] ? kb(topic.size[l]!) : ''}</td>
								<td class="meter"><span style:width="{((topic.size[l] ?? 0) / largest) * 100}%"></span></td>
								<td class="n num" data-unit="references">{topic.refs?.[l] ?? ''}</td>
								<td class="n num" data-unit="views a year">{topic.readers[l] ? topic.readers[l]!.toLocaleString('en') : ''}</td>
							</tr>
						{/if}
					{/each}
				</tbody>
			</table>
			<a href={wikidataUrl(topic.wikidata_id)} target="_blank" rel="noopener">Wikidata {topic.wikidata_id}</a>
		</section>
	{/if}
</main>

{#if nav.route}<TopicList />{/if}
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
		display: inline-flex;
		align-items: center;
		gap: var(--spacing-50);
		font-family: var(--font-family-serif);
		font-size: var(--font-size-x-large);
		color: var(--color-emphasized);
	}

	.brand:hover {
		text-decoration: none;
	}

	.mark {
		width: 1.3em;
		height: 1.3em;
		flex: none;
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

	/* One row for each edition; the articles' sizes are also lengths, to compare at a glance. */
	.articles table {
		margin: var(--spacing-25) 0;
		border-collapse: collapse;
	}

	.articles th,
	.articles td {
		padding: 0 var(--spacing-150) 0 0;
		font-weight: var(--font-weight-normal);
		text-align: left;
		vertical-align: baseline;
	}

	.articles thead th,
	.articles tbody th {
		color: var(--color-subtle);
	}

	.articles .n {
		text-align: right;
	}

	.articles td.n + .meter {
		padding-left: 0;
	}

	.articles .meter {
		width: 8rem;
		vertical-align: middle;
	}

	.articles .meter span {
		display: block;
		min-width: 2px;
		height: 6px;
		margin-left: calc(-1 * var(--spacing-100));
		background: var(--color-placeholder);
	}

	@media (max-width: 640px) {
		/* Narrow: each edition's row wraps as a line of text, with the units the headings gave. */
		.articles thead,
		.articles .meter {
			display: none;
		}

		.articles tr {
			display: flex;
			flex-wrap: wrap;
		}

		.articles th,
		.articles td {
			padding-right: var(--spacing-50);
		}

		.articles td[data-unit]:not(:empty)::after {
			content: ' ' attr(data-unit);
		}

		.inner,
		main {
			padding-left: var(--spacing-100);
			padding-right: var(--spacing-100);
		}
	}
</style>
