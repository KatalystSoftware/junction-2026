<script lang="ts">
	// Article text, word for word, with the quoted stretches and the loaded words marked.
	import { pieces } from './lib/text'

	let { text, quotes = [], terms = [], ranges = [] }: { text: string; quotes?: string[]; terms?: string[]; ranges?: [number, number][] } = $props()
</script>

{#each pieces(text, quotes, terms, ranges) as p}{#if p.mark}<mark class:term={p.mark === 'term'}>{p.text}</mark>{:else}{p.text}{/if}{/each}
