<script lang="ts">
	// Article text, word for word, with the quoted stretches and the loaded words marked.
	import { pieces } from './lib/text'

	let { text, quotes = [], terms = [] }: { text: string; quotes?: string[]; terms?: string[] } = $props()
</script>

{#each pieces(text, quotes, terms) as p}{#if p.mark}<mark class:term={p.mark === 'term'}>{p.text}</mark>{:else}{p.text}{/if}{/each}
