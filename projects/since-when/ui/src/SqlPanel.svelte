<script lang="ts">
	// The SQL behind the page, one statement at a time: the statement, its values, Run, the rows.
	// Four statements can be run; the server runs them as a SELECT-only user. The app sends a
	// preset name and its values, never SQL. The queries each response reported can be read too.
	import { onMount } from 'svelte'
	import { api } from './lib/api.svelte'
	import { NAMES, dayAfter, plural } from './lib/format'
	import { log, nav, syncSearch, ui } from './lib/nav.svelte'
	import { preview, sqlHtml } from './lib/sql'
	import { LANGS, type Preset, type Presets, type Run, type SqlEntry, type Topic } from './lib/types'
	import Why from './Why.svelte'

	let { topic }: { topic: Topic | null } = $props()

	// What each statement shows, in a line. The MariaDB feature is in the statement itself.
	const ABOUT: Record<string, [string, string]> = {
		asof: ['An article as it stood on a date', "The article at 00:00 UTC on the date: set the session's time, then a plain SELECT. Its first passage, or for a finding the passage that holds the quoted words."],
		history: ['Every version MariaDB has kept', "Every version of the article's first passage, with the time each one was current."],
		nearest: ['Editions compared on a date', 'Time travel and vector search in one statement: each passage with its nearest in the other edition.'],
		check: ['How a difference was checked', "The claim check's own statement, as stored with its verdict: the other article as it stands now (AS OF NOW(6), as the check ran it), every sentence ranked by vector distance to the claim, dates and numbers matched with REGEXP."],
	}
	const DEMO: Record<string, string> = { Q1412941: 'Lapua Movement', Q736268: 'Finnish War', Q2457646: 'Diet of Porvoo' }
	const LABEL: Record<string, string> = { qid: 'Topic', date: 'As of', lang: 'Edition', a: 'Passages in', b: 'Nearest in', finding: 'Finding' }
	const VALID = { qid: /^Q[0-9]+$/, date: /^\d{4}-\d\d-\d\d$/, lang: /^(fi|sv|en)$/, finding: /^-?[0-9]{1,9}$/ }
	const today = new Date().toISOString().slice(0, 10)

	let presets = $state<Preset[]>([])
	let limits = $state({ seconds: 5, rows: 500 })
	let name = $state('')
	let values = $state<Record<string, Record<string, string>>>({})
	let runs = $state<Record<string, Run>>({})
	let read = $state<SqlEntry | null>(null) // a query the page ran, chosen for reading
	let running = $state(false)
	let failure = $state('')
	let ready = $state(false) // the presets have answered, one way or the other
	let dialog: HTMLDialogElement

	const preset = $derived(presets.find((p) => p.name === name))
	const topics = $derived({ ...DEMO, ...(topic ? { [topic.wikidata_id]: topic.topic } : {}) })
	const groups = $derived(
		([[log.listLabel, log.list], ['This topic', log.topic], ['When each difference began', log.history]] as [string, SqlEntry[]][]).filter(([, qs]) => qs.length),
	)
	const ran = $derived(preset ? runs[preset.name] : undefined)
	// Once a statement has run with the values now in the form, the text is the one MariaDB was sent.
	const sent = $derived(ran && preset && preset.params.every((x) => ran.params[x.name] === values[preset.name][x.name]) ? ran : undefined)

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
			ui.runnable = true
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

	// A difference asks for a statement: it is filled in and shown, and waits for Run.
	$effect(() => {
		const ask = ui.ask
		if (!ask || !ready) return
		ui.ask = null
		const p = presets.find((x) => x.name === ask.preset)
		if (!p) return
		for (const x of p.params) if (VALID[x.kind].test(ask.values[x.name] ?? '')) values[p.name][x.name] = ask.values[x.name]
		name = p.name
		read = null
		failure = ''
	})

	function choose(value: string) {
		failure = ''
		const [kind, key] = value.split(':')
		if (kind === 'run') (name = key), (read = null)
		else read = groups.flatMap(([, qs]) => qs)[+key] ?? null
	}

	// The panel is a modal dialog: the browser keeps focus inside it, closes it on Escape and gives
	// focus back to the SQL button.
	$effect(() => {
		if (ui.sql && !dialog.open) dialog.showModal()
		if (!ui.sql && dialog.open) dialog.close()
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
			runs[which] = result
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

{#snippet statement(text: string)}
	<!-- svelte-ignore a11y_no_noninteractive_tabindex (a scrolling region has to take keyboard focus to be scrolled) -->
	<pre tabindex="0" aria-label="Statement">{@html sqlHtml(text)}</pre>
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

<!-- A click on the backdrop lands on the dialog element itself and closes it. -->
<dialog id="sql-panel" bind:this={dialog} aria-labelledby="sql-title" onclose={() => (ui.sql = false)} onclick={(e) => e.target === dialog && dialog.close()}>
	<div class="sheet">
		<header>
			<h2 id="sql-title">SQL behind this page</h2>
			<button class="cdx-button cdx-button--action-progressive cdx-button--weight-quiet" onclick={() => dialog.close()}>Close</button>
		</header>

		<div class="one">
			<div class="pick">
			<select class="cdx-select" aria-label="Statement" onchange={(e) => choose(e.currentTarget.value)}>
				{#if presets.length}
					<optgroup label="Run on MariaDB">
						{#each presets as p}<option value="run:{p.name}" selected={!read && p.name === name}>{ABOUT[p.name]?.[0] ?? p.title}</option>{/each}
					</optgroup>
				{/if}
				{#each groups as [group, qs], g}
					{@const before = groups.slice(0, g).reduce((n, [, x]) => n + x.length, 0)}
					<optgroup label="Read: {group}">
						{#each qs as q, i}<option value="log:{before + i}" selected={read === q}>{q.label}</option>{/each}
					</optgroup>
				{/each}
			</select>
			{#if !read && preset}
				<Why id="why-sql" label="Read-only">{ABOUT[preset.name]?.[1] ?? preset.description} Runs as a read-only user, for {limits.seconds} s and {limits.rows} rows at most.</Why>
			{/if}
			</div>

			{#if read}
				{@render statement(read.query)}
				<p class="ran"><strong class="num">{plural(read.rows, 'row', 'rows')}</strong> <strong class="num">{read.ms} ms</strong></p>
			{:else if preset}
				{@const v = values[preset.name]}
				{@render statement(sent ? sent.sql.map((q) => q.query.trim()).join(';\n\n') : preview(preset.name, v) || preset.description)}
				<form onsubmit={run}>
					{#each preset.params as x}
						<div class="cdx-field">
							<div class="cdx-label">
								<label class="cdx-label__label" for="sql-{x.name}"><span class="cdx-label__label__text">{LABEL[x.name] ?? x.name}</span></label>
							</div>
							<div class="cdx-field__control">
								{#if x.kind === 'finding'}
									<div class="cdx-text-input">
										<input id="sql-{x.name}" class="cdx-text-input__input" inputmode="numeric" pattern="-?[0-9]+" value={v[x.name]} required onchange={(e) => set(x.name, e.currentTarget.value)} />
									</div>
								{:else if x.kind === 'date'}
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
					{#if v.date}
						<span class="step">
							<button class="cdx-button cdx-button--weight-quiet" type="button" disabled={v.date <= '2001-01-15'} onclick={() => set('date', dayAfter(v.date, -1))}>Day before</button>
							<button class="cdx-button cdx-button--weight-quiet" type="button" disabled={v.date >= today} onclick={() => set('date', dayAfter(v.date))}>Day after</button>
						</span>
					{/if}
				</form>
				{#if failure}<div class="cdx-message cdx-message--inline cdx-message--error" role="alert"><span class="cdx-message__icon"></span><div class="cdx-message__content">{failure}</div></div>{/if}

				<div aria-live="polite">
					{#if ran}
						<p class="ran">
							<strong class="num">{plural(ran.rows.length, 'row', 'rows')}</strong>
							<strong class="num">{ran.ms} ms</strong>
							<!-- The values are named only when the form no longer holds the ones these rows are for. -->
							{#if !sent || ran.capped}<span class="small subtle">{[...(sent ? [] : Object.values(ran.params)), ...(ran.capped ? [`first ${ran.limits.rows} rows`] : [])].join(', ')}</span>{/if}
						</p>
						{@render result(ran)}
					{/if}
				</div>
			{/if}
		</div>
	</div>
</dialog>

<style>
	/* A sheet over the page's right edge. It is a modal dialog, so the browser keeps focus inside
	   it and closes it on Escape. */
	dialog {
		width: min(40rem, 100vw);
		max-width: none;
		height: 100dvh;
		max-height: none;
		margin: 0 0 0 auto;
		padding: 0;
		overscroll-behavior: contain;
		border: 0;
		border-left: 1px solid var(--border-color-subtle);
		background: var(--background-color-base);
		color: var(--color-base);
		box-shadow: var(--box-shadow-large);
	}

	dialog::backdrop {
		background: var(--background-color-backdrop-light);
	}

	.sheet {
		min-height: 100%;
		padding: var(--spacing-75) var(--spacing-125) var(--spacing-300);
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

	.one {
		display: flex;
		flex-direction: column;
		gap: var(--spacing-75);
	}

	/* The statement picker, then the mark that says what runs it. */
	.pick {
		display: flex;
		align-items: center;
		gap: var(--spacing-75);
	}

	.pick > .cdx-select {
		flex: 1;
		min-width: 0;
	}

	.step {
		display: flex;
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


	pre {
		margin: 0;
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

</style>
