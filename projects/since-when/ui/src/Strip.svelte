<script lang="ts">
	// Since when: one lane for each edition on one time scale, 2001 to today. A bar is a period the
	// edition has said what the difference is about; the one that still runs starts at a dot and
	// its day is printed at the end of the lane, as a link to the edit that began it.
	import type { Lane } from './lib/differences'
	import { DECADES, NAMES, day, diffUrl, list, onScale, shortDay } from './lib/format'

	// A row draws it twice: beside its headline, and inside the opened row for a narrow screen.
	// Beside the headline it lies over the row's summary, so a click on a track is handed back to
	// the row (`onpick`); the summary itself is what the keyboard uses.
	let { lanes, place, onpick }: { lanes: Lane[]; place: 'beside' | 'inside'; onpick?: () => void } = $props()

	const years = (from: string, to: string) => (from.slice(0, 4) === to.slice(0, 4) ? from.slice(0, 4) : `${from.slice(0, 4)}–${to.slice(0, 4)}`)
	// A lane in words, for a screen reader and for the pointer.
	function told(l: Lane): string {
		const past = l.spans.filter((s) => s.to).map((s) => years(s.from, s.to!))
		if (!l.since) return 'no dated change'
		return `${l.since.exact ? 'since' : 'by'} ${day(l.since.at)}${past.length ? `, earlier ${list(past)}` : ''}`
	}
</script>

<div class="strip {place}">
	{#each lanes as l (l.lang)}
		<div class="lane">
			<span class="who">{NAMES[l.lang]}</span>
			<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions (the row's summary is the control; this only keeps the pointer's click from being lost on the picture) -->
			<span class="track" class:pick={onpick} role="img" aria-label={told(l)} title="{NAMES[l.lang]}: {told(l)}" onclick={onpick}>
				{#each DECADES as y}<i style:left="{y.at}%"></i>{/each}
				{#each l.spans as s}
					<b class:past={s.to} style:left="{onScale(s.from)}%" style:right="{100 - onScale(s.to ?? Date.now())}%"></b>
				{/each}
			</span>
			<span class="since num">
				{#if l.since}
					{@const label = `${l.since.exact ? '' : 'by '}${shortDay(l.since.at)}`}
					{#if l.since.edit}
						<a href={diffUrl(l.lang, l.since.edit.rev, l.since.edit.old)} target="_blank" rel="noopener" title="Opens the {NAMES[l.lang]} edit{l.since.either ? ', one of two that day' : ''}" aria-label="{label}, the {NAMES[l.lang]} edit{l.since.either ? ', one of two that day' : ''}">{label}</a>
					{:else}
						{label}
					{/if}
				{:else if place === 'beside' || place === 'inside'}
					<span class="none">not said</span>
				{/if}
			</span>
		</div>
	{/each}
</div>

<style>
	/* The lane's name, its track, the day. The widths are shared with the scale above the list. */
	.strip {
		pointer-events: none;
	}

	.lane {
		display: grid;
		grid-template-columns: var(--lane-who) var(--lane-track) var(--lane-since);
		align-items: center;
		column-gap: var(--spacing-50);
		height: var(--lane-height);
	}

	.who {
		color: var(--color-subtle);
		font-size: var(--font-size-x-small);
		text-align: right;
	}

	/* The track is a hairline: an edition that has no bar has not changed in what is compared. */
	.track {
		position: relative;
		height: 100%;
		background: linear-gradient(var(--border-color-subtle) 0 0) 0 50% / 100% 1px no-repeat;
		pointer-events: auto;
	}

	.track.pick {
		cursor: pointer;
	}

	/* The decades, ticked on every lane. */
	i {
		position: absolute;
		top: calc(50% - 3px);
		width: 1px;
		height: 7px;
		background: var(--border-color-subtle);
	}

	b {
		position: absolute;
		top: calc(50% - 3px);
		min-width: 2px;
		height: 6px;
		background: var(--border-color-warning);
	}

	/* The period that still runs starts at a dot, so one that began last week can still be seen. */
	b:not(.past)::before {
		content: '';
		position: absolute;
		top: -2px;
		left: -5px;
		width: 10px;
		height: 10px;
		border-radius: var(--border-radius-circle);
		background: var(--border-color-warning);
	}

	/* A period that has ended. */
	b.past {
		top: calc(50% - 2px);
		height: 4px;
		background: var(--color-placeholder);
	}

	.since {
		font-size: var(--font-size-small);
		white-space: nowrap;
	}

	/* A taller target for a finger than the line it sits on. */
	.none {
		color: var(--color-subtle);
	}

	.since a {
		pointer-events: auto;
		display: inline-block;
		padding: 6px 0;
		margin: -6px 0;
	}

	@media (max-width: 640px) {
		.lane {
			grid-template-columns: var(--lane-who) minmax(0, 1fr) var(--lane-since);
		}
	}
</style>
