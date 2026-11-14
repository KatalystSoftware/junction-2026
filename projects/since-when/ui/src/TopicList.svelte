<script lang="ts">
	// A plain way to pick a topic: the API's list, a search box and the edition filter.
	import { NAMES, plural } from './lib/format'
	import { href, nav, syncSearch, ui } from './lib/nav.svelte'
	import { loadQueue, pageSize, queue } from './lib/queue.svelte'
	import type { Lang } from './lib/types'

	let dialog: HTMLDialogElement
	const FILTERS: (Lang | 'all')[] = ['all', 'en', 'sv', 'fi']

	$effect(() => {
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

	function filter(l: Lang | 'all') {
		nav.lang = l
		syncSearch()
		void loadQueue()
	}
</script>

<!-- A click on the backdrop lands on the dialog element itself and closes it. -->
<dialog bind:this={dialog} aria-labelledby="topics-title" onclose={() => (ui.topics = false)} onclick={(e) => e.target === dialog && dialog.close()}>
	<div class="sheet">
		<header>
			<h2 id="topics-title">Topics</h2>
			<button class="btn quiet" onclick={() => dialog.close()}>Close</button>
		</header>
		{#if queue.searchable}
			<form role="search" onsubmit={search}>
				<input class="field" type="search" name="q" placeholder="Search topics" aria-label="Search topics" value={nav.q} autocomplete="off" />
				<button class="btn" type="submit">Search</button>
			</form>
		{/if}
		<div class="filters" role="group" aria-label="Edition">
			{#each FILTERS as l}
				<button class="btn" aria-pressed={nav.lang === l} onclick={() => filter(l)}>{l === 'all' ? 'All' : NAMES[l]}</button>
			{/each}
		</div>
		{#if queue.error}
			<p class="note error" role="alert">Could not load the topics: {queue.error}</p>
		{:else if !queue.items.length}
			<p class="note subtle">{queue.loading ? 'Loading…' : nav.q ? `No topic matches “${nav.q}”.` : 'No topics yet.'}</p>
		{/if}
		<ul>
			{#each queue.items as i (i.wikidata_id + i.lang)}
				{@const current = nav.route?.qid === i.wikidata_id && nav.route?.lang === i.lang}
				<li>
					<a href={href({ qid: i.wikidata_id, lang: i.lang, rich: i.rich_lang, tab: 'findings' })} aria-current={current ? 'page' : undefined} onclick={() => dialog.close()}>
						<span class="name">{i.topic}</span>
						<span class="edition small subtle">{NAMES[i.lang]}</span>
						{#if i.findings}<span class="count small num" title={plural(i.findings, 'open difference', 'open differences')}>{i.findings}</span>{/if}
					</a>
				</li>
			{/each}
		</ul>
		{#if !nav.q && queue.items.length < queue.total}
			<button class="btn more" disabled={queue.loading} onclick={() => loadQueue(true)}>Show {Math.min(pageSize, queue.total - queue.items.length)} more</button>
		{/if}
	</div>
</dialog>

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

	form {
		display: flex;
		gap: var(--spacing-35);
	}

	form .field {
		flex: 1;
		min-width: 0;
	}

	.filters {
		display: flex;
		gap: var(--spacing-35);
	}

	.filters .btn {
		flex: 1;
		font-weight: var(--font-weight-normal);
	}

	li a {
		display: grid;
		grid-template-columns: 1fr auto 2.5rem;
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

	.count {
		grid-column: 3;
		text-align: right;
		color: var(--color-base);
	}

	.more {
		align-self: flex-start;
	}
</style>
