<script lang="ts">
	// The findings screen: one difference in a sentence with its date, the editions' own words side
	// by side, then every difference between the two editions the address names.
	import { NAMES, TYPES, TYPE_ORDER, day, plural, revisionUrl, sectionLabel, sectionOf, since } from './lib/format'
	import { isLeadFinding, leadTerms, pickHeadline, thirdOf } from './lib/headline'
	import { href, type Route } from './lib/nav.svelte'
	import { hasTerm, opening } from './lib/text'
	import type { Finding, FindingType, Lang, Topic } from './lib/types'
	import FindingRow from './FindingRow.svelte'
	import Marked from './Marked.svelte'
	import TypeChip from './TypeChip.svelte'

	let { topic, route, lang, rich }: { topic: Topic; route: Route; lang: Lang; rich: Lang } = $props()

	const FIRST = 8
	let whole = $state(false) // the full leads instead of their opening sentences
	let only = $state<FindingType | null>(null)
	let all = $state(false)

	const headline = $derived(pickHeadline(topic.findings, lang))
	const fromLead = $derived(!headline || isLeadFinding(headline))

	interface Card {
		lang: Lang
		where: string
		rev?: number
		excerpts: string[]
		full?: string
		quotes: string[]
		terms: string[]
	}

	// A headline about the leads shows all three opening sentences; one from further down the
	// articles shows its own two quotes.
	const cards = $derived.by((): Card[] => {
		if (headline && !fromLead) {
			return [headline.lang, headline.other_lang]
				.filter((l) => headline.quotes[l])
				.map((l) => ({ lang: l, where: sectionOf(headline, l) ?? '', rev: headline.rev_ids?.[l], excerpts: [headline.quotes[l]!], quotes: [], terms: headline.terms ?? [] }))
		}
		const terms = leadTerms(topic.findings)
		return [lang, rich, thirdOf(lang, rich)!]
			.filter((l) => topic.leads?.[l])
			.map((l) => {
				const lead = topic.leads![l]!
				const quote = headline?.quotes[l]
				const excerpts = opening(lead.text, l, quote)
				// The quoted stretch is marked only where it singles something out: not when a word is
				// already marked, and not when it is the whole of what is shown.
				const shownLength = excerpts.join(' ').length
				const quotes = quote && !hasTerm(excerpts.join(' '), terms) && quote.length < 0.9 * shownLength ? [quote] : []
				return { lang: l, where: '', rev: lead.rev_id, excerpts, full: lead.also ? `${lead.text}\n\n${lead.also}` : lead.text, quotes, terms }
			})
	})
	const canExpand = $derived(cards.some((c) => c.full && c.full.trim() !== c.excerpts.join(' ')))

	const order = (a: Finding, b: Finding) => TYPE_ORDER.indexOf(a.type) - TYPE_ORDER.indexOf(b.type) || b.opened_at.localeCompare(a.opened_at)
	const between = $derived(topic.findings.filter((f) => (f.lang === lang && f.other_lang === rich) || (f.lang === rich && f.other_lang === lang)))
	const open = $derived(between.filter((f) => f.status === 'open').sort(order))
	const closed = $derived(between.filter((f) => f.status !== 'open').sort((a, b) => (b.closed_at ?? '').localeCompare(a.closed_at ?? '')))
	const types = $derived(TYPE_ORDER.filter((t) => open.some((f) => f.type === t)))
	const listed = $derived(only ? open.filter((f) => f.type === only) : open)
	const shown = $derived(all ? listed : listed.slice(0, FIRST))
</script>

<section class="hero" aria-labelledby="claim">
	{#if headline}
		<p class="when">
			<a href={href(route, { tab: 'timeline' })} title="See when each difference opened and closed">{since(headline, day)}</a>
		</p>
		<p id="claim" class="claim">{headline.summary}</p>
		<div class="label small subtle">Machine suggestion <TypeChip type={headline.type} /></div>
	{:else}
		<p id="claim" class="claim">No open difference found between these articles.</p>
	{/if}

	<div class="cards" class:two={cards.length === 2}>
		{#each cards as c (c.lang)}
			<article class="card" class:first={c.lang === lang}>
				<h2 class="small">
					{NAMES[c.lang]}{#if c.where}<span class="where subtle" title={c.where}>{sectionLabel(c.where)}</span>{/if}
				</h2>
				{#if whole && c.full}
					<p class="words whole" lang={c.lang}><Marked text={c.full} quotes={c.quotes} terms={c.terms} /></p>
				{:else}
					{#each c.excerpts as excerpt, i}
						<p class="words" lang={c.lang}>{#if i}<span class="subtle" title="Sentences left out">{'[…] '}</span>{/if}<Marked text={excerpt} quotes={c.quotes} terms={c.terms} /></p>
					{/each}
				{/if}
				{#if c.rev}
					<a class="rev small num" href={revisionUrl(c.lang, c.rev, c.where)} target="_blank" rel="noopener">rev {c.rev}</a>
				{/if}
			</article>
		{/each}
	</div>
	{#if canExpand}
		<button class="cdx-button cdx-button--action-progressive cdx-button--weight-quiet more" aria-expanded={whole} onclick={() => (whole = !whole)}>{whole ? 'Opening sentences only' : 'Show the full leads'}</button>
	{/if}
</section>

<section class="list" aria-labelledby="list-title">
	<h2 id="list-title">{plural(open.length, 'difference', 'differences')} between {NAMES[lang]} and {NAMES[rich]}</h2>
	{#if open.length}
		<div class="tools">
			{#if types.length > 1}
				<div class="chips" role="group" aria-label="Type of difference">
					{#each types as t}
						<button class="cdx-button" aria-pressed={only === t} onclick={() => ((only = only === t ? null : t), (all = false))}>
							{TYPES[t]} <span class="count num">{open.filter((f) => f.type === t).length}</span>
						</button>
					{/each}
				</div>
			{/if}
			<p class="small subtle">Machine-suggested summaries. Open one for the quotes.</p>
		</div>
		<ul>
			{#each shown as f (f.id)}
				<li><FindingRow {f} {topic} /></li>
			{/each}
		</ul>
		{#if listed.length > shown.length}
			<button class="cdx-button rest" onclick={() => (all = true)}>Show all {listed.length}</button>
		{/if}
	{/if}
	{#if closed.length}
		<details class="closed">
			<summary class="small">{closed.length} closed</summary>
			<ul>
				{#each closed as f (f.id)}
					<li><FindingRow {f} {topic} /></li>
				{/each}
			</ul>
		</details>
	{/if}
</section>

<style>
	.hero {
		padding: var(--spacing-200) 0 var(--spacing-150);
	}

	.when {
		font-size: var(--font-size-x-large);
		line-height: var(--line-height-x-large);
		font-weight: var(--font-weight-bold);
	}

	.claim {
		max-width: 46rem;
		margin-top: var(--spacing-25);
		font-family: var(--font-family-serif);
		font-size: 2rem;
		line-height: 1.25;
		color: var(--color-emphasized);
		text-wrap: balance;
	}

	.label {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--spacing-25) var(--spacing-50);
		margin-top: var(--spacing-50);
	}

	.where {
		margin-left: var(--spacing-50);
		font-weight: var(--font-weight-normal);
	}

	.cards {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: var(--spacing-100);
		margin-top: var(--spacing-150);
	}

	.cards.two {
		grid-template-columns: repeat(2, 1fr);
	}

	.card {
		display: flex;
		flex-direction: column;
		min-width: 0;
		padding: var(--spacing-75) var(--spacing-100);
		border: 1px solid var(--border-color-subtle);
		border-top: 3px solid var(--border-color-base);
		border-radius: var(--border-radius-base);
	}

	.card.first {
		border-top-color: var(--border-color-progressive);
	}

	.card h2 {
		margin-bottom: var(--spacing-25);
		font-family: var(--font-family-system-sans);
		font-weight: var(--font-weight-bold);
	}

	.words {
		font-family: var(--font-family-serif);
		font-size: var(--font-size-large);
		line-height: var(--line-height-large);
		overflow-wrap: anywhere;
	}

	.words + .words {
		margin-top: var(--spacing-50);
	}

	.words.whole {
		white-space: pre-line;
	}

	.rev {
		margin-top: auto;
		padding-top: var(--spacing-50);
		align-self: flex-start;
		color: var(--color-subtle);
	}

	.rev:visited {
		color: var(--color-subtle);
	}

	.more {
		margin-top: var(--spacing-50);
		margin-left: calc(-1 * var(--spacing-75));
	}

	.list h2 {
		padding-bottom: var(--spacing-25);
		border-bottom: 1px solid var(--border-color-subtle);
		font-size: var(--font-size-xx-large);
		line-height: var(--line-height-xx-large);
	}

	.tools {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--spacing-50) var(--spacing-100);
		padding: var(--spacing-75) 0 var(--spacing-25);
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: var(--spacing-35);
	}

	.count {
		color: var(--color-subtle);
	}

	.rest {
		margin-top: var(--spacing-100);
	}

	.closed {
		margin-top: var(--spacing-150);
	}

	.closed > summary {
		color: var(--color-subtle);
		cursor: pointer;
	}

	@media (max-width: 640px) {
		.hero {
			padding-top: var(--spacing-150);
		}

		.claim {
			font-size: var(--font-size-xx-large);
		}

		.cards,
		.cards.two {
			grid-template-columns: 1fr;
			gap: var(--spacing-75);
		}
	}
</style>
