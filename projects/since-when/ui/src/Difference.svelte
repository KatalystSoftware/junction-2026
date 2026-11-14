<script lang="ts">
	// One difference: a headline and its time strip; opened, each edition's own words side by side
	// and a way to read the text on that date in MariaDB.
	import { dating, figureMarks, lanes, turns, type Difference } from './lib/differences'
	import { NAMES, articleUrl, dayAfter, diffUrl, list, plural, revisionUrl, sectionLabel, sectionOf } from './lib/format'
	import { showSql, ui } from './lib/nav.svelte'
	import type { TimelineEvent, Topic } from './lib/types'
	import Marked from './Marked.svelte'
	import Strip from './Strip.svelte'

	let { d, topic, events, open = false }: { d: Difference; topic: Topic; events: Map<number, TimelineEvent[]>; open?: boolean } = $props()

	const terms = $derived([...new Set(d.members.flatMap((f) => f.terms ?? []))])
	const marks = $derived(figureMarks(d))
	const story = $derived(turns(d, events))
	const began = $derived(story[0])
	const main = $derived(dating(story))
	const related = $derived(story.filter((t) => !main.includes(t)))
	// The strip is drawn once the edits have arrived: before that a day has no edition to sit on.
	const strip = $derived(lanes(d, events.size ? main : []))
	const cap = (text: string) => text[0].toUpperCase() + text.slice(1)
	let row: HTMLDetailsElement
</script>

<div class="row" style:--lanes={strip.length}>
	<details class="cdx-accordion" {open} bind:this={row}>
		<summary>
			<h3 class="cdx-accordion__header">
				<span class="cdx-accordion__header__title" title={d.title}>{#if d.who}<span class="subtle">{d.who}</span>{' '}{/if}{d.what}</span>
			</h3>
		</summary>
		<div class="cdx-accordion__content">
			<Strip lanes={strip} place="inside" />
			<div class="quotes" class:two={d.quotes.length === 2}>
				{#each d.quotes as q (q.lang)}
					{@const section = q.from ? sectionOf(q.from, q.lang) : ''}
					{@const rev = q.from?.rev_ids?.[q.lang]}
					<figure>
						<figcaption class="small">
							<a href={rev ? revisionUrl(q.lang, rev, section) : articleUrl(q.lang, topic.titles[q.lang] ?? '')} target="_blank" rel="noopener" title="Opens the {NAMES[q.lang]} article at {section ? `“${sectionLabel(section)}”` : 'its opening'}, as it was compared">{NAMES[q.lang]}</a>
						</figcaption>
						<blockquote lang={q.lang}><Marked text={q.text} {terms} ranges={marks.get(q.lang) ?? []} /></blockquote>
					</figure>
				{/each}
			</div>
			{#if !began.known}<p class="line small" title="No earlier version was compared">In the current text</p>{/if}
			{#if ui.runnable}
				<button
					class="cdx-button cdx-button--action-progressive cdx-button--weight-quiet check"
					aria-haspopup="dialog"
					title="Opens the statement that reads the {NAMES[began.lang]} article as it stood after that day. Nothing runs until you click Run."
					onclick={() => showSql('asof', { qid: topic.wikidata_id, date: dayAfter(began.at), lang: began.lang })}>Check in MariaDB</button
				>
			{/if}
			{#if related.length}
				<details class="cdx-accordion cdx-accordion--separation-minimal related">
					<summary><h4 class="cdx-accordion__header">{plural(related.length, 'more edit', 'more edits')}</h4></summary>
					<ul class="cdx-accordion__content small">
						{#each related as t (t.key)}
							<li>
								<strong class="num">{cap(t.date)}</strong>
								{#if t.edits.length === 1}
									<a href={diffUrl(t.edits[0].lang, t.edits[0].rev, t.edits[0].old)} target="_blank" rel="noopener">{t.what}</a>
								{:else}
									{#if t.term}<span>“{t.term}”</span>{/if}
									{#each t.edits as e, i}
										<a href={diffUrl(e.lang, e.rev, e.old)} target="_blank" rel="noopener">{i ? 'or the' : 'the'} {NAMES[e.lang]} edit</a>
									{:else}
										<span>{t.what}</span>
									{/each}
								{/if}
								{#if t.earlier.length}<span class="subtle">earlier too, {list(t.earlier)}</span>{/if}
							</li>
						{/each}
					</ul>
				</details>
			{/if}
		</div>
	</details>
	<Strip lanes={strip} place="beside" onpick={() => (row.open = !row.open)} />
</div>

<style>
	/* A row: the headline on the left, its time strip on the right, in the same column down the
	   list. The strip lies over the summary's right end and lets a click through to it, so its
	   links are not inside the summary. */
	.row {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		border-bottom: 1px solid var(--border-color-subtle);
	}

	.row > details {
		grid-area: 1 / 1 / 2 / 3;
		min-width: 0;
	}

	.row > :global(.strip) {
		grid-area: 1 / 2;
		align-self: start;
		margin: var(--spacing-75) var(--spacing-75) 0 0;
	}

	/* The strip's second place, for a narrow screen: under the headline of an opened row. */
	.row :global(.strip.inside) {
		display: none;
	}

	.row > details > summary {
		align-items: center;
		min-height: calc(var(--lanes) * var(--lane-height) + 2 * var(--spacing-75));
		padding-right: calc(var(--lane-who) + var(--lane-track) + var(--lane-since) + 2 * var(--spacing-50) + 2 * var(--spacing-75));
	}

	/* The headline is set in the regular weight instead of the bold of a Codex accordion title. */
	summary > h3.cdx-accordion__header {
		font-family: inherit;
		font-weight: var(--font-weight-normal);
	}

	.row > details[open] > summary .cdx-accordion__header__title {
		font-family: var(--font-family-serif);
		font-size: var(--font-size-xxx-large);
		line-height: var(--line-height-xxx-large);
		color: var(--color-emphasized);
		text-wrap: balance;
	}

	.quotes {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: var(--spacing-100);
	}

	.quotes.two {
		grid-template-columns: repeat(2, 1fr);
	}

	figure {
		min-width: 0;
		margin: 0;
		padding: var(--spacing-50) var(--spacing-75) var(--spacing-75);
		border-top: 3px solid var(--border-color-base);
		background: var(--background-color-neutral-subtle);
	}

	figcaption {
		font-weight: var(--font-weight-bold);
	}

	blockquote {
		margin-top: var(--spacing-25);
		font-family: var(--font-family-serif);
		font-size: var(--font-size-x-large);
		line-height: var(--line-height-x-large);
		overflow-wrap: anywhere;
	}

	.line {
		margin-top: var(--spacing-50);
	}

	.related li {
		display: flex;
		flex-wrap: wrap;
		gap: 0 var(--spacing-50);
	}

	.check {
		margin: var(--spacing-75) 0 0 calc(-1 * var(--spacing-75));
	}

	.row > details[open] > .cdx-accordion__content {
		padding-top: var(--spacing-75);
		padding-bottom: var(--spacing-150);
	}

	.related {
		margin-top: var(--spacing-25);
	}

	.related h4.cdx-accordion__header {
		font-family: inherit;
		font-size: var(--font-size-small);
		font-weight: var(--font-weight-normal);
		color: var(--color-subtle);
	}

	.related ul {
		padding-top: 0;
	}

	/* Narrow: the strip goes under the row and takes its width; the quotes stack. */
	@media (max-width: 640px) {
		.row {
			grid-template-columns: minmax(0, 1fr);
		}

		.row > details {
			grid-area: auto;
		}

		.row > :global(.strip) {
			grid-area: auto;
			margin: 0 var(--spacing-75) var(--spacing-75);
		}

		.row > details[open] :global(.strip.inside) {
			display: block;
			margin-bottom: var(--spacing-75);
		}

		.row > details[open] + :global(.strip) {
			display: none;
		}

		.row > details[open] > .cdx-accordion__content {
			padding-top: 0;
		}

		.row > details > summary {
			min-height: 0;
			padding-right: var(--spacing-75);
			padding-bottom: var(--spacing-50);
		}

		.quotes,
		.quotes.two {
			grid-template-columns: 1fr;
			gap: var(--spacing-50);
		}
	}
</style>
