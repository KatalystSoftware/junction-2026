<script lang="ts">
	// The type of a difference, as a Codex InfoChip. The label carries the meaning; the status
	// colour only groups: statements that disagree, statements that lean, content one edition lacks.
	import { TYPES } from './lib/format'
	import type { FindingType } from './lib/types'

	let { type }: { type: FindingType } = $props()

	const STATUS: Partial<Record<FindingType, string>> = { contradiction: 'error', numbers: 'error', framing: 'warning' }
</script>

<div class="cdx-info-chip cdx-info-chip--{STATUS[type] ?? 'notice'}">
	<span class="cdx-info-chip__text">{TYPES[type] ?? type}</span>
</div>
