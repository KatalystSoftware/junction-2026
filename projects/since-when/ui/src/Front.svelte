<script lang="ts">
	// The front page: three topics to start from, each with its strongest difference and when each
	// edition took it up, and under them the whole list of topics.
	import { onMount } from 'svelte'
	import { api } from './lib/api.svelte'
	import { dating, lanes, leading, turns, type Difference, type Lane } from './lib/differences'
	import { modelName } from './lib/format'
	import { href, showSql, ui } from './lib/nav.svelte'
	import { queue } from './lib/queue.svelte'
	import { LANGS, type Timeline, type TimelineEvent, type Topic } from './lib/types'
	import Strip from './Strip.svelte'
	import TopicList from './TopicList.svelte'
	import Why from './Why.svelte'

	// Lapua Movement first: its difference is one word in each article's first sentence, which a
	// reader checks at a glance. Then the Finnish War and the Diet of Porvoo.
	const START = ['Q1412941', 'Q736268', 'Q2457646']

	// undefined while loading, null when the topic or a difference for it is not in this database.
	let cards = $state<Record<string, { topic: Topic; d: Difference; strip: Lane[] } | null>>({})

	async function load(qid: string) {
		try {
			const topic = await api<Topic>(`/topics/${qid}`)
			const d = leading(topic)
			if (!d) throw new Error('no difference')
			cards[qid] = { topic, d, strip: lanes(d, []) }
			// The edits that date it arrive after the topic, one request for each edition.
			const answers = await Promise.all(LANGS.map((l) => api<Timeline>(`/topics/${qid}/timeline?lang=${l}&rich_lang=${LANGS.find((x) => x !== l)}`).catch(() => null)))
			const by = new Map<number, TimelineEvent[]>()
			for (const e of answers.flatMap((a) => a?.events ?? [])) by.set(e.finding_id, [...(by.get(e.finding_id) ?? []), e])
			cards[qid] = { topic, d, strip: lanes(d, dating(turns(d, by))) }
		} catch {
			cards[qid] ??= null
		}
	}

	onMount(() => {
		ui.topics = false
		START.forEach(load)
	})
</script>

<h1>What three Wikipedias say differently, and since when</h1>
{#if queue.database}
	{@const db = queue.database}
	<p class="db">
		Every date here is read from MariaDB {db.version}: a system-versioned table, <code>{db.table}</code>, keeps
		<span class="num">{db.versions.toLocaleString('en')}</span> versions of
		<span class="num">{db.passages.toLocaleString('en')}</span> passages, each from the Wikipedia edit that wrote it (every revision for the three topics below, one a year for the rest).
		{#if ui.runnable}<button class="cdx-button cdx-button--action-progressive cdx-button--weight-quiet" aria-haspopup="dialog" onclick={() => showSql('history', { qid: START[0], lang: 'en' })}>See the versions of one passage</button>{/if}
	</p>
{/if}

<section class="start" aria-label="Topics to start from">
	<Why id="why-start" label="How these were found">A word in quotation marks comes from a fixed list of loaded words: it is in the first sentence of the editions dated on its strip and not in the others'. For the other differences, {modelName(null)} compared each topic's articles passage by passage and suggested them, then looked each one up in the whole other article and set aside those it found stated there. A person closed the ones found false on reading both articles. Open a topic to read each edition's own words.</Why>
	<p class="key small subtle" aria-hidden="true"><span class="dot"></span> the edit that put the quoted words there word for word, <span class="bar"></span> since then, <span class="bar past"></span> an earlier period; 2001 to today</p>
	<div class="cards">
		{#each START as qid}
			{@const c = cards[qid]}
			{#if c}
				<article class="card">
					<h2><a href={href(qid)}>{c.topic.topic}</a></h2>
					<p class="what" title={c.d.title}>{#if !c.d.who && c.d.what.startsWith('“')}{c.d.title}{:else}{#if c.d.who}<span class="subtle">{c.d.who}</span>{' '}{/if}{c.d.what}{/if}</p>
					<Strip lanes={c.strip} place="inside" />
				</article>
			{:else if c === undefined}
				<div class="card" aria-hidden="true"></div>
			{/if}
		{/each}
	</div>
</section>

<TopicList inline />

<style>
	h1 {
		margin: var(--spacing-150) 0 var(--spacing-100);
		line-height: 1.25;
	}

	.db {
		margin: 0 0 var(--spacing-100);
		color: var(--color-subtle);
	}

	.db button {
		margin-left: calc(-1 * var(--spacing-25));
	}

	.start {
		display: grid;
		justify-items: start;
		gap: var(--spacing-75);
		margin-bottom: var(--spacing-200);
	}

	.cards {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: var(--spacing-100);
		width: 100%;
	}

	/* The whole card opens the topic; the strip's dates stay links to their edits. */
	.card {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: var(--spacing-50);
		min-height: 11.5rem;
		padding: var(--spacing-100);
		border: 1px solid var(--border-color-subtle);
		border-top: 3px solid var(--border-color-interactive);
		border-radius: var(--border-radius-base);
		--lane-who: 3.25rem;
		--lane-track: minmax(0, 1fr);
		--lane-since: 5.5rem;
	}

	.card:hover {
		border-color: var(--border-color-progressive);
	}

	h2 {
		font-size: var(--font-size-x-large);
	}

	h2 a::after {
		content: '';
		position: absolute;
		inset: 0;
	}

	.what {
		flex: 1;
		font-size: var(--font-size-large);
		line-height: var(--line-height-small);
	}

	.card :global(.since a) {
		position: relative;
		z-index: 1;
	}

	@media (max-width: 720px) {
		.cards {
			grid-template-columns: 1fr;
		}

		.card {
			min-height: 0;
		}
	}

	/* The key to the time strips: the marks drawn as the strips draw them. */
	.key span {
		display: inline-block;
		vertical-align: middle;
		background: var(--border-color-warning);
	}
	.key .dot {
		width: 10px;
		height: 10px;
		border-radius: var(--border-radius-circle);
	}
	.key .bar {
		width: 18px;
		height: 6px;
	}
	.key .bar.past {
		height: 4px;
		background: var(--color-placeholder);
	}
</style>
