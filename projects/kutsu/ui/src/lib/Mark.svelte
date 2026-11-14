<script lang="ts">
  import { markOf } from './mark'

  // A person's own mark: a small abstract mosaic drawn from a seed, in place of a photo. It is never a
  // face or a figure and says nothing about the person; the same seed always draws the same mark.
  let { seed, label = 'Your mark' }: { seed: string; label?: string } = $props()
  const mark = $derived(markOf(seed))
</script>

<svg class="mark" viewBox="0 0 {mark.size} {mark.size}" role="img" aria-label={label}>
  <rect width={mark.size} height={mark.size} fill={mark.ground} />
  {#each mark.tiles as tile, i (i)}
    <rect x={tile.x} y={tile.y} width="1" height="1" fill={tile.fill} />
    <!-- a quarter disc from one corner of the cell, or a full dot in its middle -->
    {#if tile.dot}
      <circle cx={tile.x + 0.5} cy={tile.y + 0.5} r="0.26" fill={tile.ink} />
    {:else}
      <path d="M{tile.cx} {tile.cy} L{tile.ax} {tile.ay} A1 1 0 0 {tile.sweep} {tile.bx} {tile.by} Z" fill={tile.ink} />
    {/if}
  {/each}
</svg>

<style>
  .mark {
    display: block;
    width: 100%;
    height: 100%;
    border-radius: 22%;
  }
</style>
