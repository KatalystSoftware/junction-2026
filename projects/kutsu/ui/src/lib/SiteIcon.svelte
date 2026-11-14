<script lang="ts">
  import { ICONS } from './sites'

  // The icon of the site a link belongs to, drawn here in the app's own line weight. Nothing is fetched.
  let { id, size = 18 }: { id: string; size?: number } = $props()
  const paths = $derived(ICONS[id] ?? ICONS.globe ?? [])
</script>

<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  {#each paths as d, i (i)}<path {d} />{/each}
</svg>
