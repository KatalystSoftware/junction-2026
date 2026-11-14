<script lang="ts">
	// One difference: its summary on a line; opened, the two quotes word for word and where they sit.
	import { NAMES, articleUrl, revisionUrl, rowDate, sectionLabel, sectionOf, shortDay, since, when } from './lib/format'
	import type { Finding, Lang, Topic } from './lib/types'
	import Marked from './Marked.svelte'
	import TypeChip from './TypeChip.svelte'

	let { f, topic }: { f: Finding; topic: Topic } = $props()

	const sides = $derived([f.lang, f.other_lang])

	const quoteUrl = (l: Lang, section: string | undefined) => (f.rev_ids?.[l] ? revisionUrl(l, f.rev_ids[l]!, section) : articleUrl(l, topic.titles[l] ?? ''))

	// Finnish articles cite at paragraph ends, so a sentence without a reference falls back to its paragraph's.
	function citation(l: Lang): string {
		if (!f.citations || !(l in f.citations)) return ''
		if (f.citations[l]) return `Cites ${f.citations[l]}`
		if (f.paragraph_citations?.[l]) return `No reference on the sentence; its paragraph ends with ${f.paragraph_citations[l]}`
		return 'No reference on the sentence'
	}
</script>

<details class="cdx-accordion">
	<summary>
		<h3 class="cdx-accordion__header">
			<TypeChip type={f.type} />
			<span class="cdx-accordion__header__title">{f.summary}</span>
			<span class="date subtle small num">{rowDate(f)}</span>
		</h3>
	</summary>
	<div class="cdx-accordion__content">
		<div class="quotes">
			{#each sides as l}
				{@const section = sectionOf(f, l)}
				<figure>
					<figcaption class="small">
						<strong>{NAMES[l]}</strong>
						{#if section !== undefined}
							<a href={quoteUrl(l, section)} target="_blank" rel="noopener" title={section || 'Lead'}>{sectionLabel(section)}</a>
						{/if}
					</figcaption>
					{#if f.quotes[l]}
						<blockquote lang={l}><Marked text={f.quotes[l]!} terms={f.terms ?? []} /></blockquote>
						{#if citation(l)}<p class="cite small subtle">{citation(l)}</p>{/if}
					{:else}
						<p class="subtle">{f.type === 'coverage' && l === f.lang ? 'No close passage' : 'No quote stored'}</p>
					{/if}
				</figure>
			{/each}
		</div>
		<p class="ids small subtle num">
			<span>{since(f, shortDay)}{#if f.closed_at}; closed {when(f.closed_after, f.closed_at, shortDay)}{/if}</span>
			<span>finding {f.id}</span>
			{#each sides as l}
				{#if f.rev_ids?.[l]}<a href={revisionUrl(l, f.rev_ids[l]!)} target="_blank" rel="noopener">{l} revision {f.rev_ids[l]}</a>{/if}
			{/each}
			{#if f.distance != null}<span>distance {f.distance.toFixed(2)}</span>{/if}
		</p>
	</div>
</details>

<style>
	/* The row's heading on one line: the type, the summary, the date. The summary is a sentence, so
	   it is set in the regular weight instead of the bold of a Codex accordion title. */
	summary > .cdx-accordion__header {
		display: grid;
		grid-template-columns: 7.5rem 1fr auto;
		align-items: baseline;
		gap: var(--spacing-75);
		font-weight: var(--font-weight-normal);
	}

	.cdx-accordion__header :global(.cdx-info-chip) {
		justify-self: start;
	}

	.date {
		white-space: nowrap;
	}

	.quotes {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--spacing-150);
	}

	figure {
		margin: 0;
		min-width: 0;
	}

	figcaption {
		display: flex;
		flex-wrap: wrap;
		gap: 0 var(--spacing-50);
	}

	blockquote {
		padding-left: var(--spacing-75);
		border-left: 3px solid var(--border-color-subtle);
		overflow-wrap: anywhere;
	}

	.cite {
		padding: var(--spacing-25) 0 0 var(--spacing-75);
		overflow-wrap: anywhere;
	}

	.ids {
		display: flex;
		flex-wrap: wrap;
		gap: 0 var(--spacing-100);
		margin-top: var(--spacing-75);
	}

	@media (max-width: 640px) {
		summary > .cdx-accordion__header {
			grid-template-columns: 1fr auto;
			gap: var(--spacing-25) var(--spacing-75);
		}

		.cdx-accordion__header__title {
			grid-column: 1 / -1;
			grid-row: 2;
		}

		.quotes {
			grid-template-columns: 1fr;
			gap: var(--spacing-100);
		}
	}
</style>
