<script lang="ts">
	// A plain way to pick a topic: the API's list, a search box and the edition filter. It is a
	// sheet over a topic's page, and on the front page (`inline`) a section of the page itself.
	import { NAMES } from './lib/format'
	import { href, nav, syncSearch, ui } from './lib/nav.svelte'
	import { loadQueue, pageSize, queue } from './lib/queue.svelte'
	import type { Lang } from './lib/types'

	let { inline = false }: { inline?: boolean } = $props()
	let dialog = $state<HTMLDialogElement>()
	const FILTERS: (Lang | 'all')[] = ['all', 'en', 'sv', 'fi']

	$effect(() => {
		if (!dialog) return
		if (ui.topics && !dialog.open) dialog.showModal()
		if (!ui.topics && dialog.open) dialog.close()
	})

	// Search runs when the form is submitted, not on each keystroke: the first search after a restart
	// makes the data service load its embedding model, which is too heavy to start by accident.
	function search(e: SubmitEvent) {
		e.preventDefault()
		const value = String(new FormData(e.currentTarget as HTMLFormElement).get('q') ?? '').trim()
		if (value === nav.q) return
		nav.q = value
		syncSearch()
		void loadQueue()
	}

	// The API lists a topic once for each edition; the page is about the topic, so it is listed once.
	// Topics with differences to show come first; the rest are marked "not compared yet".
	const topics = $derived(queue.items.filter((i, n, all) => all.findIndex((x) => x.wikidata_id === i.wikidata_id) === n))

	function filter(l: Lang | 'all') {
		nav.lang = l
		syncSearch()
		void loadQueue()
	}
</script>

{#snippet body()}
		{#if queue.searchable}
			<form role="search" onsubmit={search}>
				<div class="cdx-search-input cdx-search-input--has-end-button">
					<div class="cdx-search-input__input-wrapper">
						<div class="cdx-text-input cdx-text-input--has-start-icon">
							<input class="cdx-text-input__input" type="search" name="q" placeholder="Search topics" aria-label="Search topics" value={nav.q} autocomplete="off" />
							<span class="cdx-text-input__icon cdx-text-input__start-icon"></span>
						</div>
					</div>
					<button class="cdx-button cdx-search-input__end-button" type="submit">Search</button>
				</div>
			</form>
		{/if}
		<div class="filters" role="group" aria-label="Edition">
			{#each FILTERS as l}
				<button class="cdx-button" aria-pressed={nav.lang === l} onclick={() => filter(l)}>{l === 'all' ? 'All' : NAMES[l]}</button>
			{/each}
		</div>
		{#if queue.error}
			<div class="cdx-message cdx-message--block cdx-message--error" role="alert"><span class="cdx-message__icon"></span><div class="cdx-message__content">Could not load the topics: {queue.error}</div></div>
		{:else if !queue.items.length}
			<p class="note subtle">{queue.loading ? 'Loading…' : nav.q ? `No topic matches "${nav.q}".` : 'No topics yet.'}</p>
		{/if}
		<ul>
			{#each topics as i (i.wikidata_id)}
				<li>
					<a href={href(i.wikidata_id)} aria-current={nav.route?.qid === i.wikidata_id ? 'page' : undefined} onclick={() => dialog?.close()}>
						<span class="name">{i.topic}</span>
						{#if i.compared === false}<span class="small subtle">not compared yet</span>{/if}
					</a>
				</li>
			{/each}
		</ul>
		{#if !nav.q && queue.items.length < queue.total}
			<button class="cdx-button more" disabled={queue.loading} onclick={() => loadQueue(true)}>Show {Math.min(pageSize, queue.total - queue.items.length)} more</button>
		{/if}
{/snippet}

{#if inline}
	<section class="sheet inline" aria-labelledby="all-topics-title">
		<h2 id="all-topics-title">All topics</h2>
		{@render body()}
	</section>
{:else}
	<!-- A click on the backdrop lands on the dialog element itself and closes it. -->
	<dialog bind:this={dialog} aria-labelledby="topics-title" onclose={() => (ui.topics = false)} onclick={(e) => e.target === dialog && dialog?.close()}>
		<div class="sheet">
			<header>
				<h2 id="topics-title">Topics</h2>
				<button class="cdx-button cdx-button--action-progressive cdx-button--weight-quiet" onclick={() => dialog?.close()}>Close</button>
			</header>
			{@render body()}
		</div>
	</dialog>
{/if}

<style>
	dialog {
		width: min(26rem, 100vw);
		max-width: none;
		height: 100dvh;
		max-height: none;
		margin: 0;
		padding: 0;
		border: 0;
		border-right: 1px solid var(--border-color-subtle);
		background: var(--background-color-base);
		color: var(--color-base);
		box-shadow: var(--box-shadow-large);
	}

	dialog::backdrop {
		background: var(--background-color-backdrop-light);
	}

	.sheet {
		display: flex;
		flex-direction: column;
		gap: var(--spacing-75);
		min-height: 100%;
		padding: var(--spacing-100) var(--spacing-125) var(--spacing-200);
	}

	header {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	h2 {
		font-size: var(--font-size-xx-large);
	}

	/* On the front page: part of the page, as wide as the sheet. */
	.inline {
		max-width: 26rem;
		min-height: 0;
		padding: 0;
	}

	.inline h2 {
		font-size: var(--font-size-x-large);
	}

	.filters {
		display: flex;
		gap: var(--spacing-35);
	}

	.filters .cdx-button {
		flex: 1;
	}

	li a {
		display: grid;
		grid-template-columns: 1fr auto;
		align-items: baseline;
		gap: var(--spacing-50);
		padding: var(--spacing-35) var(--spacing-50);
		margin: 0 calc(-1 * var(--spacing-50));
		border-radius: var(--border-radius-base);
	}

	li a:hover {
		background: var(--background-color-interactive-subtle);
		text-decoration: none;
	}

	li a[aria-current='page'] {
		background: var(--background-color-progressive-subtle);
	}

	.more {
		align-self: flex-start;
	}
</style>
