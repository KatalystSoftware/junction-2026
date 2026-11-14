<script lang="ts">
	// A compact mark with its explanation one click away: a Codex info chip that is a button, and a
	// native popover. The browser closes it on Escape or a click outside and returns focus.
	import type { Snippet } from 'svelte'

	let { id, label, children }: { id: string; label: string; children: Snippet } = $props()
</script>

<button class="cdx-info-chip" type="button" popovertarget={id} style:anchor-name="--{id}">
	<span class="cdx-info-chip__icon"></span>
	<span class="cdx-info-chip__text">{label}</span>
</button>
<div {id} popover class="small" style:position-anchor="--{id}">{@render children()}</div>

<style>
	button {
		flex: none;
		cursor: pointer;
	}

	button:hover {
		background-color: var(--background-color-interactive--hover);
	}

	/* Under the chip, from its left edge; flipped when there is no room. Where anchors are not
	   supported the browser centres it. */
	[popover] {
		/* Its own width, so that near the right edge it flips instead of being squeezed. */
		width: max-content;
		max-width: min(24rem, calc(100vw - 2 * var(--spacing-100)));
		padding: var(--spacing-50) var(--spacing-75);
		border: 1px solid var(--border-color-base);
		border-radius: var(--border-radius-base);
		background: var(--background-color-base);
		box-shadow: var(--box-shadow-medium);
		color: var(--color-base);
	}

	@supports (top: anchor(bottom)) {
		[popover] {
			inset: auto;
			top: calc(anchor(bottom) + var(--spacing-25));
			left: anchor(left);
			margin: 0;
			position-try-fallbacks: flip-inline, flip-block;
		}

		/* Narrow: under the chip, from one side of the screen to the other. */
		@media (max-width: 640px) {
			[popover] {
				left: var(--spacing-100);
				right: var(--spacing-100);
				width: auto;
				max-width: none;
			}
		}
	}
</style>
