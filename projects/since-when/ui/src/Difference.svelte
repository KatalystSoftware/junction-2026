<script lang="ts">
	// One difference: a sentence and its date; opened, each edition's own words side by side, the
	// edit that began it, and a way to read the text on that date in MariaDB.
	import { figureMarks, turns, type Difference } from './lib/differences'
	import { NAMES, articleUrl, dayAfter, diffUrl, list, plural, revisionUrl, rowDate, sectionLabel, sectionOf } from './lib/format'
	import { showSql, ui } from './lib/nav.svelte'
	import type { TimelineEvent, Topic } from './lib/types'
	import Marked from './Marked.svelte'

	let { d, topic, events, open = false }: { d: Difference; topic: Topic; events: Map<number, TimelineEvent[]>; open?: boolean } = $props()

	const terms = $derived([...new Set(d.members.flatMap((f) => f.terms ?? []))])
	const marks = $derived(figureMarks(d))
	const story = $derived(turns(d, events))
	const began = $derived(story[0])
	// The lines that date the difference itself: the row that speaks for it and, for a loaded word,
	// every edition's edit about that word. The rest are other rows about the same claim.
	const main = $derived(story.filter((t, i) => i === 0 || (began.term && t.term === began.term)))
	const related = $derived(story.filter((t) => !main.includes(t)))
	// An edit made in one edition dates that edition's quote; any other line goes under the quotes.
	const own = (t: (typeof story)[number]) => (t.edits.length === 1 && d.quotes.some((q) => q.lang === t.edits[0].lang) ? t.edits[0].lang : null)
	const under = $derived(main.filter((t) => !own(t)))
	const cap = (text: string) => text[0].toUpperCase() + text.slice(1)
</script>

{#snippet turn(t: (typeof story)[number])}
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
{/snippet}

<details class="cdx-accordion" {open}>
	<summary>
		<h3 class="cdx-accordion__header">
			<span class="cdx-accordion__header__title">{d.title}</span>
			<span class="date subtle small num">{rowDate(d.primary)}</span>
		</h3>
	</summary>
	<div class="cdx-accordion__content">
		<div class="quotes" class:two={d.quotes.length === 2}>
			{#each d.quotes as q (q.lang)}
				{@const section = q.from ? sectionOf(q.from, q.lang) : ''}
				{@const rev = q.from?.rev_ids?.[q.lang]}
				<figure>
					<figcaption class="small">
						<a class="edition" href={rev ? revisionUrl(q.lang, rev, section) : articleUrl(q.lang, topic.titles[q.lang] ?? '')} target="_blank" rel="noopener" title="Opens the {NAMES[q.lang]} article at {section ? `“${sectionLabel(section)}”` : 'its opening'}, as it was compared">{NAMES[q.lang]}</a>
						{#each main.filter((t) => own(t) === q.lang) as t (t.key)}
							<span class="num">
								<a href={diffUrl(q.lang, t.edits[0].rev, t.edits[0].old)} target="_blank" rel="noopener" title="Opens the edit: {t.what}">{t.date}</a>{#if t.earlier.length}<span class="subtle">, earlier {list(t.earlier)}</span>{/if}
							</span>
						{/each}
					</figcaption>
					<blockquote lang={q.lang}><Marked text={q.text} {terms} ranges={marks.get(q.lang) ?? []} /></blockquote>
				</figure>
			{/each}
		</div>
		{#each under as t (t.key)}<p class="line small">{@render turn(t)}</p>{/each}
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
				<summary><h4 class="cdx-accordion__header">{plural(related.length, 'more change', 'more changes')}</h4></summary>
				<ul class="cdx-accordion__content small">
					{#each related as t (t.key)}<li>{@render turn(t)}</li>{/each}
				</ul>
			</details>
		{/if}
	</div>
</details>

<style>
	/* The row's heading: the sentence, then its date. The sentence is set in the regular weight
	   instead of the bold of a Codex accordion title. */
	summary > h3.cdx-accordion__header {
		display: grid;
		grid-template-columns: 1fr auto;
		align-items: baseline;
		gap: var(--spacing-100);
		font-family: inherit;
		font-weight: var(--font-weight-normal);
	}

	details[open] > summary .cdx-accordion__header__title {
		font-family: var(--font-family-serif);
		font-size: 1.75rem;
		line-height: 1.3;
		color: var(--color-emphasized);
		text-wrap: balance;
	}

	.date {
		white-space: nowrap;
	}

	/* Open, each quote carries its own date. */
	details[open] > summary .date {
		display: none;
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

	/* The edition on one line, its date on the next, so the quotes start level. */
	figcaption {
		display: flex;
		flex-direction: column;
		min-height: calc(2 * var(--line-height-small));
	}

	.edition {
		align-self: flex-start;
		font-weight: var(--font-weight-bold);
	}

	blockquote {
		margin-top: var(--spacing-35);
		font-family: var(--font-family-serif);
		font-size: var(--font-size-x-large);
		line-height: var(--line-height-x-large);
		overflow-wrap: anywhere;
	}

	.line,
	.related li {
		display: flex;
		flex-wrap: wrap;
		gap: 0 var(--spacing-50);
	}

	.line {
		margin-top: var(--spacing-50);
	}

	.check {
		margin: var(--spacing-75) 0 0 calc(-1 * var(--spacing-75));
	}

	details[open] > .cdx-accordion__content {
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

	@media (max-width: 640px) {
		summary > h3.cdx-accordion__header {
			grid-template-columns: 1fr;
			gap: 0;
		}

		.quotes,
		.quotes.two {
			grid-template-columns: 1fr;
			gap: var(--spacing-50);
		}
	}
</style>
