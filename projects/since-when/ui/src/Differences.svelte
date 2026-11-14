<script lang="ts">
	// The topic's page: the few places where the editions say different things, each with its time
	// strip, then, collapsed, what each edition says that another leaves out.
	import { FIRST, differences, missing, setAside, wordList, wording } from './lib/differences'
	import { DECADES, NAMES, articleUrl, day, linkParts, list, modelName, plural, revisionUrl, rowDate, sectionLabel, sourceOf } from './lib/format'
	import { LANGS, type TimelineEvent, type Topic } from './lib/types'
	import Difference from './Difference.svelte'
	import Why from './Why.svelte'

	let { topic, events }: { topic: Topic; events: Map<number, TimelineEvent[]> } = $props()

	const SOME = 10
	let all = $state(false)
	let whole = $state<Record<string, boolean>>({})

	const editions = $derived(LANGS.filter((l) => topic.titles[l]))
	const found = $derived(differences(topic))
	// Whether a language model has read this topic at all: the alignment alone writes coverage rows.
	const compared = $derived(!!topic.checked || topic.findings.some((f) => f.type !== 'coverage'))
	const shown = $derived(all ? found : found.slice(0, FIRST))
	const left = $derived(missing(topic))
	// On a topic the claim check has run on: the word list's loaded words, which lead the page, the
	// model's wording rows, which the check does not cover, and what the check set aside.
	const loaded = $derived(wordList(topic))
	const words = $derived(wording(topic))
	const aside = $derived(setAside(topic))
	const judge = $derived(topic.checked?.judge)
	let allAside = $state(false)
	let asideOpen = $state(false)
	// What the check did on this topic, in numbers: suggestions it looked up, those it set aside and
	// why, and those a person closed after reading both articles.
	const tally = $derived.by(() => {
		const c = topic.checked
		if (!c) return null
		const by = c.set_aside ?? {}
		const aside = Object.values(by).reduce((a, b) => a + b, 0)
		const looked = (c.kept ?? 0) + (c.changed ?? 0) + (c.new ?? 0) + aside
		const closed = topic.findings.filter((f) => f.outcome === 'not_real' && f.check).length
		return { looked, aside, by, closed }
	})
	const lacking = $derived(editions.filter((l) => left[l].length))
	const most = $derived(Math.max(1, ...lacking.map((l) => left[l].length)))
</script>

{#snippet key()}
	<p class="key small subtle" aria-hidden="true"><span class="dot"></span> edit that put these exact words there · <span class="bar"></span> said since · <span class="bar past"></span> said earlier · 2001 to today</p>
{/snippet}

{#snippet scale()}
	<!-- The scale of every strip below, labelled once. -->
	<div class="scale num" aria-hidden="true">
		<span>2001</span>
		{#each DECADES as y}<span style:left="{y.at}%">{y.year}</span>{/each}
	</div>
{/snippet}

{#if loaded.length}
	<section aria-labelledby="words-title">
		<header>
			<h2 id="words-title">Loaded words</h2>
			<Why id="why-words" label="Word list">Found by a fixed list of loaded words, not by a language model: the word is in the first sentence of the editions named and not in the others'. The sentences are quoted word for word.</Why>
			{@render scale()}
		</header>
		{@render key()}
		<div class="rows">
			{#each loaded as d, i (d.id)}
				<Difference {d} {topic} {events} open={i === 0} />
			{/each}
		</div>
	</section>
{/if}

<section class:left={loaded.length > 0} aria-labelledby="list-title">
	<header>
		<h2 id="list-title">{found.length ? plural(found.length, 'difference', 'differences') : compared ? 'No differences found' : 'Not compared yet'}</h2>
		{#if !found.length && !compared}
			<Why id="why-list" label="Alignment only">{modelName(null)} has not compared this topic's articles yet, so there are no differences of fact or wording to show. What follows comes from the vector alignment alone: passages of one edition with no close passage in another.</Why>
		{/if}
		{#if found.length}
			{#if judge}
				<Why id="why-list" label="Checked by Nemotron">{modelName(topic.checked?.model)} suggested these by comparing the articles passage by passage{#if modelName(topic.checked?.model) === modelName(judge)}, then looked each one up in the whole other article{:else}; {modelName(judge)} looked each one up in the whole other article{/if}. Rows that a further review, by language models reading both articles, found false are closed; no person has checked any of them. The quotes are word for word: read them to judge.{#if tally}<br /><br />{modelName(judge)} looked up {tally.looked} suggestions in the whole other article on {day(topic.checked!.as_of)} and set aside {tally.aside}{#if tally.aside}:
				{list([
					tally.by.stated_elsewhere ? `${tally.by.stated_elsewhere} where the other edition states the fact elsewhere` : '',
					tally.by.repeat ? `${plural(tally.by.repeat, 'repeat', 'repeats')} of another row` : '',
					tally.by.not_confirmed ? `${tally.by.not_confirmed} not confirmed from both sides` : '',
				].filter(Boolean))}{/if}.
			{#if aside.length}<a href="#aside-title" onclick={() => (asideOpen = true)}>{plural(aside.length, 'statement', 'statements')} the other edition states</a>, each with the passage that states it, are listed below; a statement set aside more than once is listed once.{/if}
			{#if tally.closed}That review closed {tally.closed} more.{/if}{/if}</Why>
			{:else}
				<Why id="why-list" label="Suggested by Nemotron">{modelName(null)} suggested these by comparing passage with passage. They have not been looked up in the whole other article, and no person has checked them. The quotes are word for word: read them to judge.</Why>
			{/if}
			{#if !loaded.length}{@render scale()}{/if}
		{/if}
	</header>
	{#if !loaded.length && found.length}{@render key()}{/if}
	{#if found.length}
		<div class="rows">
			{#each shown as d, i (d.id)}
				<Difference {d} {topic} {events} open={i === 0 && !loaded.length} />
			{/each}
		</div>
		{#if found.length > shown.length}
			<button class="cdx-button rest" onclick={() => (all = true)}>Show all {found.length}</button>
		{/if}
	{/if}
</section>

{#if words.length}
	<section class="left" aria-labelledby="wording-title">
		<header>
			<h2 id="wording-title">Wording</h2>
			<Why id="why-wording" label="Not checked">{modelName(null)} suggested these differences of wording. The check does not cover them, and no person has checked them.</Why>
		</header>
		<div class="rows">
			{#each words as d (d.id)}
				<Difference {d} {topic} {events} />
			{/each}
		</div>
	</section>
{/if}

{#if lacking.length}
	<section class="left" aria-labelledby="left-title">
		<header>
			<h2 id="left-title">Said in one edition, left out of another</h2>
			{#if judge}
				<Why id="why-left" label="Checked by Nemotron">{modelName(judge)} searched the whole other article for each of these and did not find it. A sentence with several facts is listed when any one of them is missing. No person has checked them.</Why>
			{:else}
				<Why id="why-left" label="Unchecked">Found by comparing passage with passage. Not yet checked against the whole of the other article, so some of these are there under another heading.</Why>
			{/if}
		</header>
		{#each lacking as l (l)}
			{@const items = left[l]}
			<details class="cdx-accordion">
				<summary>
					<h3 class="cdx-accordion__header" aria-label="{plural(items.length, 'statement', 'statements')} in the {NAMES[l]} article that another edition leaves out">
						<span>In {NAMES[l]}</span>
						<span class="count num">{items.length}</span>
						<span class="meter"><span style:width="{(items.length / most) * 100}%"></span></span>
					</h3>
				</summary>
				<div class="cdx-accordion__content">
					<ul>
						{#each whole[l] ? items : items.slice(0, SOME) as m (m.key)}
							{@const rev = m.row.rev_ids?.[l]}
							{@const src = sourceOf(m.row, l)}
							<li>
								<blockquote lang={l}>{m.quote || m.row.summary}</blockquote>
								<p class="small subtle">
									<a href={rev ? revisionUrl(l, rev, m.section) : articleUrl(l, topic.titles[l] ?? '')} target="_blank" rel="noopener">{sectionLabel(m.section)}</a>
									<span class="num">{rowDate(m.row)}</span>
									<span>Not in {list(m.lacks.map((x) => NAMES[x]), 'or')}</span>
								</p>
								{#if src?.text}
									<p class="small source"><span class="subtle">{src.where}:</span> {#each linkParts(src.text) as p}{#if p.url}<a href={p.part} target="_blank" rel="noopener">{p.part}</a>{:else}{p.part}{/if}{/each}</p>
								{/if}
							</li>
						{/each}
					</ul>
					{#if !whole[l] && items.length > SOME}
						<button class="cdx-button rest" onclick={() => (whole[l] = true)}>Show all {items.length}</button>
					{/if}
				</div>
			</details>
		{/each}
	</section>
{/if}

{#if aside.length}
	<section class="left" aria-labelledby="aside-title">
		<details class="cdx-accordion" bind:open={asideOpen}>
			<summary>
				<h2 id="aside-title" class="cdx-accordion__header" title="Suggested as missing or different; the check found the fact stated elsewhere in the other article">
					<span>Set aside by the check</span>
					<span class="count num">{aside.length}</span>
				</h2>
			</summary>
			<div class="cdx-accordion__content">
				<ul>
					{#each allAside ? aside : aside.slice(0, SOME) as a (a.key)}
						<li>
							<blockquote lang={a.lang}>{a.quote}</blockquote>
							<p class="small subtle">
								<span>{NAMES[a.evidence.lang]} states it too:</span>
								<a href={a.evidence.rev_id ? revisionUrl(a.evidence.lang, a.evidence.rev_id, a.evidence.section) : articleUrl(a.evidence.lang, topic.titles[a.evidence.lang] ?? '')} target="_blank" rel="noopener">{sectionLabel(a.evidence.section ?? '')}</a>
							</p>
							<blockquote lang={a.evidence.lang}>{a.evidence.passage ?? a.evidence.quote}</blockquote>
						</li>
					{/each}
				</ul>
				{#if !allAside && aside.length > SOME}
					<button class="cdx-button rest" onclick={() => (allAside = true)}>Show all {aside.length}</button>
				{/if}
			</div>
		</details>
	</section>
{/if}

<style>
	/* A list's heading, then the mark that says how far to trust the list. */
	header {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--spacing-25) var(--spacing-75);
		padding-bottom: var(--spacing-25);
		border-bottom: 1px solid var(--border-color-subtle);
	}

	h2 {
		font-size: var(--font-size-x-large);
		line-height: var(--line-height-x-large);
	}

	/* The years, over the tracks of the strips below: the same width, the same place. */
	.scale {
		position: relative;
		align-self: flex-end;
		width: var(--lane-track);
		height: var(--line-height-x-small);
		margin: 0 calc(var(--lane-since) + var(--spacing-50) + var(--spacing-75)) 0 auto;
		color: var(--color-subtle);
		font-size: var(--font-size-x-small);
		line-height: var(--line-height-x-small);
	}

	.scale span {
		position: absolute;
		transform: translateX(-50%);
	}

	.scale span:first-child {
		transform: none;
	}


	.rest {
		margin-top: var(--spacing-100);
	}


	.left {
		margin-top: var(--spacing-300);
	}

	/* An edition, how many statements, and the count as a length. */
	.left h3.cdx-accordion__header {
		display: grid;
		grid-template-columns: 6rem 2.5rem minmax(0, 20rem);
		align-items: center;
		gap: var(--spacing-75);
		font-family: inherit;
		font-weight: var(--font-weight-normal);
	}

	.count {
		text-align: right;
	}

	.meter span {
		display: block;
		min-width: 2px;
		height: 6px;
		background: var(--color-placeholder);
	}

	li + li {
		margin-top: var(--spacing-75);
	}

	blockquote {
		font-family: var(--font-family-serif);
		overflow-wrap: anywhere;
	}

	.source {
		overflow-wrap: anywhere;
	}

	li p:not(.source) {
		display: flex;
		flex-wrap: wrap;
		gap: 0 var(--spacing-75);
	}

	@media (max-width: 640px) {
		.scale {
			display: none;
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
