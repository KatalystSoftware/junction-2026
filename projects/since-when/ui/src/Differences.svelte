<script lang="ts">
	// The topic's page: the few places where the editions say different things, each with its time
	// strip, then, collapsed, what each edition says that another leaves out.
	import { FIRST, differences, missing } from './lib/differences'
	import { DECADES, NAMES, articleUrl, list, plural, revisionUrl, rowDate, sectionLabel } from './lib/format'
	import { LANGS, type TimelineEvent, type Topic } from './lib/types'
	import Difference from './Difference.svelte'
	import Why from './Why.svelte'

	let { topic, events }: { topic: Topic; events: Map<number, TimelineEvent[]> } = $props()

	const SOME = 10
	let all = $state(false)
	let whole = $state<Record<string, boolean>>({})

	const editions = $derived(LANGS.filter((l) => topic.titles[l]))
	const found = $derived(differences(topic))
	const shown = $derived(all ? found : found.slice(0, FIRST))
	const left = $derived(missing(topic))
	const lacking = $derived(editions.filter((l) => left[l].length))
	const most = $derived(Math.max(1, ...lacking.map((l) => left[l].length)))
</script>

<section aria-labelledby="list-title">
	<header>
		<h2 id="list-title">{found.length ? plural(found.length, 'difference', 'differences') : 'No differences found'}</h2>
		{#if found.length}
			<Why id="why-list" label="Machine-suggested">A language model suggested these and nobody has checked them. The quotes are word for word: read them to judge.</Why>
			<!-- The scale of every strip below, labelled once. -->
			<div class="scale num" aria-hidden="true">
				<span>2001</span>
				{#each DECADES as y}<span style:left="{y.at}%">{y.year}</span>{/each}
			</div>
		{/if}
	</header>
	{#if found.length}
		<div class="rows">
			{#each shown as d, i (d.id)}
				<Difference {d} {topic} {events} open={i === 0} />
			{/each}
		</div>
		{#if found.length > shown.length}
			<button class="cdx-button rest" onclick={() => (all = true)}>Show all {found.length}</button>
		{/if}
	{/if}
</section>

{#if lacking.length}
	<section class="left" aria-labelledby="left-title">
		<header>
			<h2 id="left-title">Said in one edition, left out of another</h2>
			<Why id="why-left" label="Unchecked">Found by comparing passage with passage. Not yet checked against the whole of the other article, so some of these are there under another heading.</Why>
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
							<li>
								<blockquote lang={l}>{m.quote || m.row.summary}</blockquote>
								<p class="small subtle">
									<a href={rev ? revisionUrl(l, rev, m.section) : articleUrl(l, topic.titles[l] ?? '')} target="_blank" rel="noopener">{sectionLabel(m.section)}</a>
									<span class="num">{rowDate(m.row)}</span>
									<span>Not in {list(m.lacks.map((x) => NAMES[x]), 'or')}</span>
								</p>
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

	/* The first difference is open on arrival and has a wide first screen to itself. */
	@media (min-width: 641px) {
		.rows > :global(.row:first-child:has(> details[open])) {
			min-height: 35rem;
		}
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

	li p {
		display: flex;
		flex-wrap: wrap;
		gap: 0 var(--spacing-75);
	}

	@media (max-width: 640px) {
		.scale {
			display: none;
		}
	}
</style>
