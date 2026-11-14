<script lang="ts">
	// The timeline: for each difference, the periods it held and the edit behind every turn.
	import { onDestroy } from 'svelte'
	import { api, ApiError } from './lib/api.svelte'
	import { NAMES, TYPES, TYPE_ORDER, diffUrl, kb, revisionUrl, shortDay, when } from './lib/format'
	import { DIFFERS } from './lib/headline'
	import { log, type Route } from './lib/nav.svelte'
	import type { FindingType, Lang, Timeline, TimelineEvent, Topic } from './lib/types'
	import TypeChip from './TypeChip.svelte'

	let { topic, route, lang, rich }: { topic: Topic; route: Route; lang: Lang; rich: Lang } = $props()

	const FIRST = 10
	let data = $state<Timeline | null>(null)
	let failure = $state('')
	let only = $state<FindingType | null>(null)
	let all = $state(false)

	$effect(() => {
		let stale = false
		api<Timeline>(`/topics/${encodeURIComponent(route.qid)}/timeline?lang=${lang}&rich_lang=${rich}`).then(
			(t) => {
				if (stale) return
				data = t
				log.tab = t.sql ?? []
			},
			(e: Error) => {
				if (!stale) failure = e instanceof ApiError && e.status === 404 ? 'Not computed for this topic yet.' : e.message
			},
		)
		return () => (stale = true)
	})
	onDestroy(() => (log.tab = []))

	interface Story {
		id: number
		type?: FindingType
		summary: string
		pair: string
		events: TimelineEvent[]
		last: string
	}

	// The API lists events; the page tells one difference at a time, so they are grouped by finding.
	const stories = $derived.by((): Story[] => {
		const by = new Map<number, Story>()
		const known = new Map(topic.findings.map((f) => [f.id, f]))
		for (const e of data?.events ?? []) {
			let s = by.get(e.finding_id)
			if (!s) {
				const f = known.get(e.finding_id)
				s = { id: e.finding_id, type: e.type ?? f?.type, summary: e.summary, pair: f ? `${NAMES[f.lang]} and ${NAMES[f.other_lang]}` : '', events: [], last: '' }
				by.set(e.finding_id, s)
			}
			s.events.push(e)
		}
		const list = [...by.values()]
		for (const s of list) {
			s.events.sort((a, b) => a.date.localeCompare(b.date))
			s.last = s.events[s.events.length - 1].date
		}
		// Statements that differ before content one edition lacks, as on the findings screen; then the
		// newest change, and among the same day the difference with the longer history.
		const differs = (x: Story) => Number(!!x.type && DIFFERS.includes(x.type))
		return list.sort((a, b) => differs(b) - differs(a) || b.last.localeCompare(a.last) || b.events.length - a.events.length)
	})
	const types = $derived(TYPE_ORDER.filter((t) => stories.some((s) => s.type === t)))
	const listed = $derived(only ? stories.filter((s) => s.type === only) : stories)
	const shown = $derived(all ? listed : listed.slice(0, FIRST))

	// One time axis for every bar: from the year of the first event to today.
	const start = $derived(Date.UTC(+(data?.events.reduce((min, e) => (e.date < min ? e.date : min), '9999').slice(0, 4) ?? 2005), 0, 1))
	const end = Date.now()
	const at = (d: string) => Math.max(0, Math.min(100, ((Date.parse(d) - start) / (end - start)) * 100))
	const ticks = $derived.by(() => {
		const first = new Date(start).getUTCFullYear()
		const out: number[] = []
		for (let y = Math.ceil(first / 5) * 5; y <= new Date(end).getUTCFullYear(); y += 5) out.push(y)
		return out
	})

	// A period too short to see still gets a visible sliver, kept inside the bar.
	const span = (from: number, to: number) => {
		const width = Math.max(0.6, to - from)
		return { left: Math.min(from, 100 - width), width }
	}

	function spans(events: TimelineEvent[]): { left: number; width: number }[] {
		const out: { left: number; width: number }[] = []
		let from: string | null = null
		for (const e of events) {
			if (e.kind === 'opened' && from === null) from = e.date
			if (e.kind === 'closed' && from !== null) {
				out.push(span(at(from), at(e.date)))
				from = null
			}
		}
		if (from !== null) out.push(span(at(from), 100))
		return out
	}

	const years = (events: TimelineEvent[]) =>
		events
			.filter((e) => e.kind !== 'reviewed')
			.map((e) => `${e.kind} ${e.date.slice(0, 4)}`)
			.join(', ')
</script>

<section aria-labelledby="timeline-title">
	<h2 id="timeline-title">When each difference opened and closed</h2>
	{#if failure}
		<div class="cdx-message cdx-message--block cdx-message--error" role="alert"><span class="cdx-message__icon"></span><div class="cdx-message__content">{failure}</div></div>
	{:else if !data}
		<p class="state subtle">Reading the history…</p>
	{:else if !stories.length}
		<p class="state subtle">No differences recorded for the {NAMES[lang]} article.</p>
	{:else}
		<div class="tools">
			{#if types.length > 1}
				<div class="chips" role="group" aria-label="Type of difference">
					{#each types as t}
						<button class="cdx-button" aria-pressed={only === t} onclick={() => ((only = only === t ? null : t), (all = false))}>
							{TYPES[t]} <span class="count num">{stories.filter((s) => s.type === t).length}</span>
						</button>
					{/each}
				</div>
			{/if}
			<p class="small subtle">Machine-suggested summaries. Each revision links to its edit.</p>
		</div>

		<div class="axis small subtle num" aria-hidden="true">
			{#each ticks as y}<span style:left="{at(`${y}-01-01`)}%">{y}</span>{/each}
		</div>
		<ol class="stories">
			{#each shown as s (s.id)}
				<li class="story">
					<div class="sum">
						{#if s.type}<TypeChip type={s.type} />{/if}
						{s.summary}
					</div>
					<div class="bar" role="img" aria-label="Held: {years(s.events)}">
						{#each spans(s.events) as p}<i style:left="{p.left}%" style:width="{p.width}%"></i>{/each}
					</div>
					<ol class="turns small">
						{#each s.events as e}
							<li>
								<span class="kind {e.kind}">{e.kind}</span>
								<time class="num" datetime={e.date}>{when(e.after, e.date, shortDay)}</time>
								{#if e.diffs?.length}
									{#each e.diffs as d}
										<a class="num" href={diffUrl(d.lang, d.rev_id, d.old_rev_id)} target="_blank" rel="noopener" title="The {NAMES[d.lang]} edits between the two compared revisions">{d.lang} rev {d.rev_id}</a>
									{/each}
								{:else if e.rev_url}
									<a href={e.rev_url} target="_blank" rel="noopener">revision</a>
								{:else if e.rev_id}
									{@const l = e.rev_lang ?? lang}
									<a class="num" href={revisionUrl(l, e.rev_id)} target="_blank" rel="noopener">{l} rev {e.rev_id}</a>
								{/if}
							</li>
						{/each}
					</ol>
				</li>
			{/each}
		</ol>
		{#if listed.length > shown.length}
			<button class="cdx-button rest" onclick={() => (all = true)}>Show all {listed.length}</button>
		{/if}

		<details class="years small">
			<summary>Article size on each 1 January</summary>
			<div class="scroll">
				<table class="num">
					<thead>
						<tr><th scope="col">Year</th>{#each [lang, rich] as l}<th scope="col">{NAMES[l]}</th>{/each}<th scope="col">Open differences</th></tr>
					</thead>
					<tbody>
						{#each data.years.toReversed() as y}
							<tr><th scope="row">{y.year}</th>{#each [lang, rich] as l}<td>{y.size[l] ? kb(y.size[l]!) : '–'}</td>{/each}<td>{y.open_findings}</td></tr>
						{/each}
					</tbody>
				</table>
			</div>
		</details>
	{/if}
</section>

<style>
	section {
		padding-top: var(--spacing-150);
	}

	h2 {
		padding-bottom: var(--spacing-25);
		border-bottom: 1px solid var(--border-color-subtle);
		font-size: var(--font-size-xx-large);
		line-height: var(--line-height-xx-large);
	}

	.state {
		padding: var(--spacing-150) 0;
	}

	.cdx-message {
		margin-top: var(--spacing-100);
	}

	.tools {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--spacing-50) var(--spacing-100);
		padding: var(--spacing-75) 0;
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: var(--spacing-35);
	}

	.count {
		color: var(--color-subtle);
	}

	.axis {
		position: relative;
		height: var(--line-height-small);
		border-bottom: 1px solid var(--border-color-subtle);
	}

	.axis span {
		position: absolute;
		padding-left: var(--spacing-25);
		border-left: 1px solid var(--border-color-subtle);
	}

	.story {
		padding: var(--spacing-100) 0;
		border-bottom: 1px solid var(--border-color-muted);
	}

	.sum :global(.cdx-info-chip) {
		margin-right: var(--spacing-35);
	}

	/* The periods the difference held, on the axis above. */
	.bar {
		position: relative;
		height: var(--spacing-50);
		margin: var(--spacing-50) 0;
		border-radius: var(--border-radius-pill);
		background: var(--background-color-neutral);
	}

	.bar i {
		position: absolute;
		top: 0;
		bottom: 0;
		border-radius: var(--border-radius-pill);
		background: var(--color-warning);
	}

	.turns {
		display: flex;
		flex-wrap: wrap;
		gap: var(--spacing-25) var(--spacing-150);
	}

	.turns li {
		display: flex;
		flex-wrap: wrap;
		gap: 0 var(--spacing-35);
	}

	.kind {
		font-weight: var(--font-weight-bold);
		text-transform: capitalize;
	}

	.kind.opened {
		color: var(--color-warning);
	}

	.kind.closed {
		color: var(--color-success);
	}

	.rest {
		margin-top: var(--spacing-100);
	}

	.years {
		margin-top: var(--spacing-200);
	}

	.years summary {
		color: var(--color-subtle);
		cursor: pointer;
	}

	.scroll {
		overflow-x: auto;
	}

	table {
		margin-top: var(--spacing-50);
		border-collapse: collapse;
	}

	th,
	td {
		padding: var(--spacing-12) var(--spacing-100) var(--spacing-12) 0;
		text-align: right;
		font-weight: var(--font-weight-normal);
	}

	thead th {
		border-bottom: 1px solid var(--border-color-subtle);
		color: var(--color-subtle);
	}

	th:first-child {
		text-align: left;
	}
</style>
