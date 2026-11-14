<script lang="ts">
	// The SQL behind the page: three preset statements the server runs as a SELECT-only user, and
	// the queries each response reported. The app sends a preset name and its values, never SQL.
	import { onMount, tick } from 'svelte'
	import { api } from './lib/api.svelte'
	import { NAMES, plural } from './lib/format'
	import { log, nav, syncSearch, ui } from './lib/nav.svelte'
	import { sqlHtml } from './lib/sql'
	import { LANGS, type Preset, type Presets, type Run, type SqlEntry, type Topic } from './lib/types'

	let { topic }: { topic: Topic | null } = $props()

	const DEMO: Record<string, string> = { Q1412941: 'Lapua Movement', Q736268: 'Finnish War', Q2457646: 'Diet of Porvoo' }
	const LABEL: Record<string, string> = { qid: 'Topic', date: 'As of', lang: 'Edition', a: 'Passages in', b: 'Nearest in' }
	const VALID = { qid: /^Q[0-9]+$/, date: /^\d{4}-\d\d-\d\d$/, lang: /^(fi|sv|en)$/ }
	const today = new Date().toISOString().slice(0, 10)

	let presets = $state<Preset[]>([])
	let limits = $state({ seconds: 5, rows: 500 })
	let name = $state('')
	let values = $state<Record<string, Record<string, string>>>({})
	let runs = $state<Record<string, Run[]>>({})
	let running = $state(false)
	let failure = $state('')
	let ready = $state(false) // the presets have answered, one way or the other
	let panel: HTMLElement

	const preset = $derived(presets.find((p) => p.name === name))
	const topics = $derived({ ...DEMO, ...(topic ? { [topic.wikidata_id]: topic.topic } : {}) })
	const groups = $derived(
		([[log.listLabel, log.list], ['Topic', log.topic], ['Timeline', log.tab]] as [string, SqlEntry[]][]).filter(([, qs]) => qs.length),
	)

	// ?sql=<preset>,<values in the preset's order> opens the panel with that preset filled in. It
	// only fills the form: nothing runs until Run is clicked.
	onMount(async () => {
		const asked = nav.sql
		try {
			const d = await api<Presets>('/sql/presets')
			if (!d.enabled) throw new Error('no read-only user')
			for (const p of d.presets) values[p.name] = Object.fromEntries(p.params.map((x) => [x.name, x.default]))
			const [wanted, ...given] = (asked ?? '').split(',')
			const p = d.presets.find((x) => x.name === wanted) ?? d.presets[0]
			if (p?.name === wanted) p.params.forEach((x, i) => VALID[x.kind].test(given[i] ?? '') && (values[p.name][x.name] = given[i]))
			limits = d.limits
			presets = d.presets
			name = p?.name ?? ''
			if (asked !== null && p) ui.sql = true
		} catch {
			// Without the read-only user the panel is the query log alone.
		}
		ready = true
	})

	// The open panel's preset and values live in the address, so the link reopens it as it is.
	$effect(() => {
		if (!ready) return
		nav.sql = ui.sql && preset ? [preset.name, ...preset.params.map((x) => values[preset.name][x.name])].join(',') : null
		syncSearch()
	})

	// Focus follows the panel: into it when it opens, back to its button when it closes.
	let wasOpen = false
	$effect(() => {
		if (ui.sql) void tick().then(() => panel?.focus())
		else if (wasOpen) document.querySelector<HTMLElement>('[aria-controls="sql-panel"]')?.focus()
		wasOpen = ui.sql
	})

	// A pair never matches an edition with itself: choosing the other side's edition swaps the two.
	function set(key: string, value: string) {
		const v = values[name]
		const was = v[key]
		v[key] = value
		if (v.a && v.a === v.b) v[key === 'a' ? 'b' : 'a'] = was
	}

	async function run(e: SubmitEvent) {
		e.preventDefault()
		const which = name
		running = true
		failure = ''
		try {
			const result = await api<Run>('/sql/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ preset: which, params: values[which] }) })
			runs[which] = [result, ...(runs[which] ?? [])].slice(0, 2)
		} catch (err) {
			failure = err instanceof Error ? err.message : String(err)
		}
		running = false
	}

	function cell(column: string, x: string | number | null): { text: string; cls: string; note?: string } {
		if (x === null) return { text: 'NULL', cls: 'null' }
		if (typeof x === 'number') return { text: Number.isInteger(x) ? String(x) : x.toFixed(4), cls: 'num' }
		if (/^\d{4}-\d\d-\d\dT/.test(x)) return { text: x.replace('T', ' '), cls: 'when', note: column === 'row_end' && x.startsWith('2106-') ? 'current' : undefined }
		return { text: x, cls: x.length > 40 ? 'txt' : '' }
	}
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && ui.sql && !document.querySelector('dialog[open]') && (ui.sql = false)} />

{#snippet statement(q: SqlEntry)}
	<pre>{@html sqlHtml(q.query)}</pre>
{/snippet}

{#snippet result(r: Run)}
	<!-- A column of numbers is set to the right, header and all. -->
	{@const numeric = r.columns.map((_, i) => r.rows.some((row) => typeof row[i] === 'number'))}
	<div class="cdx-table result">
		<!-- svelte-ignore a11y_no_noninteractive_tabindex (a scrolling region has to take keyboard focus to be scrolled) -->
		<div class="cdx-table__table-wrapper" tabindex="0" role="region" aria-label="Result rows">
			<table class="cdx-table__table">
				<caption>Result rows</caption>
				<thead>
					<tr>
						{#each r.columns as c, i}
							<th scope="col" class={[numeric[i] && 'cdx-table__table__cell--align-number']}><span class="cdx-table__th-content">{c}</span></th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each r.rows as row}
						<tr>
							{#each row as x, i}
								{@const c = cell(r.columns[i], x)}
								<td class={[c.cls, numeric[i] && 'cdx-table__table__cell--align-number']}>{c.text}{#if c.note}<span class="subtle"> {c.note}</span>{/if}</td>
							{/each}
						</tr>
					{:else}
						<tr class="cdx-table__table__empty-state"><td class="cdx-table__table__empty-state-content" colspan={r.columns.length}>No rows.</td></tr>
					{/each}
				</tbody>
			</table>
		</div>
	</div>
{/snippet}

<aside id="sql-panel" class="panel" class:open={ui.sql} hidden={!ui.sql} aria-labelledby="sql-title" tabindex="-1" bind:this={panel}>
	<header>
		<h2 id="sql-title">SQL behind this page</h2>
		<button class="cdx-button cdx-button--action-progressive cdx-button--weight-quiet" onclick={() => (ui.sql = false)}>Close</button>
	</header>

	{#if preset}
		<section class="live" aria-label="Run a statement on MariaDB">
			<div class="presets" role="group" aria-label="Statement">
				{#each presets as p}
					<button class="cdx-button" aria-pressed={p.name === name} onclick={() => ((name = p.name), (failure = ''))}>{p.title}</button>
				{/each}
			</div>
			<p class="small subtle">{preset.description}</p>
			<form onsubmit={run}>
				{#each preset.params as x}
					{@const v = values[preset.name]}
					<div class="cdx-field">
						<div class="cdx-label">
							<label class="cdx-label__label" for="sql-{x.name}"><span class="cdx-label__label__text">{LABEL[x.name] ?? x.name}</span></label>
						</div>
						<div class="cdx-field__control">
							{#if x.kind === 'date'}
								<div class="cdx-text-input">
									<input id="sql-{x.name}" class="cdx-text-input__input" type="date" value={v[x.name]} min="2001-01-15" max={today} required onchange={(e) => set(x.name, e.currentTarget.value)} />
								</div>
							{:else}
								<select id="sql-{x.name}" class="cdx-select" value={v[x.name]} onchange={(e) => set(x.name, e.currentTarget.value)}>
									{#if x.kind === 'lang'}
										{#each LANGS as l}<option value={l}>{NAMES[l]}</option>{/each}
									{:else}
										{#each Object.entries({ ...topics, [v.qid]: topics[v.qid] ?? v.qid }) as [id, title]}<option value={id}>{title}</option>{/each}
									{/if}
								</select>
							{/if}
						</div>
					</div>
				{/each}
				<button class="cdx-button cdx-button--action-progressive cdx-button--weight-primary" type="submit" disabled={running}>{running ? 'Running…' : 'Run'}</button>
			</form>
			{#if failure}<div class="cdx-message cdx-message--inline cdx-message--error" role="alert"><span class="cdx-message__icon"></span><div class="cdx-message__content">{failure}</div></div>{/if}

			<div aria-live="polite">
				{#each runs[preset.name] ?? [] as r, i}
					<div class="run" class:previous={i > 0}>
						{#if i > 0}<p class="label small">Previous run</p>{/if}
						<p class="ran">
							<strong class="num">{plural(r.rows.length, 'row', 'rows')}</strong>
							<strong class="num">{r.ms} ms</strong>
							<span class="small subtle">{Object.values(r.params).join(', ')}{r.capped ? `, first ${r.limits.rows} rows` : ''}</span>
						</p>
						{#if i === 0}
							{#each r.sql as q}
								<p class="qhead small"><span>{q.label}</span><span class="subtle num">{q.ms} ms, {plural(q.rows, 'row', 'rows')}</span></p>
								{@render statement(q)}
							{/each}
						{/if}
						{@render result(r)}
					</div>
				{/each}
			</div>
			<p class="small subtle">Runs as a read-only user, for {limits.seconds} s and {limits.rows} rows at most.</p>
		</section>
	{/if}

	{#if groups.length}
		<section class="log" aria-labelledby="log-title">
			<h3 id="log-title" class="small">Queries this page ran</h3>
			{#each groups as [group, qs]}
				{#each qs as q}
					<details class="cdx-accordion">
						<summary>
							<h4 class="cdx-accordion__header">
								<span class="cdx-accordion__header__title">{q.label} <span class="subtle">{group}</span></span>
								<span class="cdx-accordion__header__description num">{q.ms} ms, {plural(q.rows, 'row', 'rows')}</span>
							</h4>
						</summary>
						<div class="cdx-accordion__content">{@render statement(q)}</div>
					</details>
				{/each}
			{/each}
		</section>
	{/if}
</aside>

<style>
	/* Laid over the page's right edge, so opening it moves nothing underneath. */
	.panel {
		position: fixed;
		top: 0;
		right: 0;
		bottom: 0;
		z-index: var(--z-index-overlay);
		width: min(40rem, 100vw);
		padding: var(--spacing-75) var(--spacing-125) var(--spacing-300);
		overflow-y: auto;
		overscroll-behavior: contain;
		border-left: 1px solid var(--border-color-subtle);
		background: var(--background-color-base);
		box-shadow: var(--box-shadow-large);
	}

	.panel:focus-visible {
		outline-offset: -2px;
		border-radius: 0;
	}

	header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: var(--spacing-75);
	}

	h2 {
		font-size: var(--font-size-xx-large);
	}

	.live {
		display: flex;
		flex-direction: column;
		gap: var(--spacing-75);
	}

	.presets {
		display: flex;
		flex-wrap: wrap;
		gap: var(--spacing-35);
	}

	form {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-end;
		gap: var(--spacing-75);
	}

	/* The fields sit side by side, so Codex's space between stacked fields and its 256px minimum
	   width give way to the row. */
	form .cdx-field {
		margin: 0;
	}

	form .cdx-select,
	form .cdx-text-input {
		min-width: 9rem;
	}

	.run {
		margin-top: var(--spacing-50);
	}

	.run.previous {
		margin-top: var(--spacing-150);
		padding-top: var(--spacing-75);
		border-top: 1px solid var(--border-color-subtle);
	}

	.label {
		font-weight: var(--font-weight-bold);
		color: var(--color-subtle);
	}

	/* What an engineer looks for first: how many rows, how long. */
	.ran {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0 var(--spacing-100);
	}

	.ran strong {
		font-size: var(--font-size-xx-large);
		line-height: var(--line-height-xx-large);
		color: var(--color-emphasized);
	}

	.previous .ran strong {
		font-size: var(--font-size-medium);
		line-height: var(--line-height-medium);
	}

	.qhead {
		display: flex;
		justify-content: space-between;
		gap: var(--spacing-100);
		margin-top: var(--spacing-50);
		font-weight: var(--font-weight-bold);
	}

	.qhead .subtle {
		font-weight: var(--font-weight-normal);
		white-space: nowrap;
	}

	pre {
		margin: var(--spacing-25) 0 var(--spacing-50);
		padding: var(--spacing-50) var(--spacing-75);
		overflow-x: auto;
		border: 1px solid var(--border-color-muted);
		border-radius: var(--border-radius-base);
		background: var(--background-color-neutral-subtle);
		font-family: var(--font-family-monospace);
		font-size: var(--font-size-x-small);
		line-height: 1.5;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
	}

	pre :global(.kw) {
		color: var(--color-progressive--active);
		font-weight: var(--font-weight-bold);
	}

	pre :global(.st) {
		color: var(--color-success);
	}

	pre :global(.cm) {
		color: var(--color-subtle);
	}

	/* Codex's table, set tighter than its default: the panel is narrow and a result is read row
	   against row. It scrolls inside its own frame, under a header that stays in view. */
	.result .cdx-table__table-wrapper {
		max-height: 22rem;
		overflow: auto;
	}

	.result table {
		font-size: var(--font-size-x-small);
		line-height: var(--line-height-x-small);
	}

	.result th,
	.result td {
		padding: var(--spacing-25) var(--spacing-50);
	}

	.result thead th {
		position: sticky;
		top: 0;
		border-bottom: 0;
		background: var(--background-color-neutral-subtle);
		box-shadow: inset 0 -1px 0 var(--border-color-base);
	}

	td.null {
		color: var(--color-subtle);
	}

	td.when {
		min-width: 6.5rem;
		font-variant-numeric: tabular-nums;
	}

	td.txt {
		min-width: 14rem;
	}

	.log {
		margin-top: var(--spacing-200);
	}

	h3 {
		padding-bottom: var(--spacing-25);
		border-bottom: 1px solid var(--border-color-subtle);
		color: var(--color-subtle);
	}
</style>
