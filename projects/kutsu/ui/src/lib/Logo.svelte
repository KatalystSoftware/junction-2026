<script lang="ts">
  import type { Brief } from './types'
  import { logoSrc } from './logo'
  import { nameOf } from './state.svelte'

  // A logo on the ground it was drawn for. Without one, or when it fails to load, the initial.
  // `small` asks for the square icon, which stays legible in a list tile; lists load theirs as they scroll into view.
  let { brief, small = false }: { brief: Brief; small?: boolean } = $props()
  let failed = $state(false)
  const logo = $derived(failed ? null : small ? brief.identity?.icon : brief.identity?.logo)
  const on = $derived(small ? brief.identity?.icon_on : brief.identity?.logo_on)
  const size = $derived(small ? 128 : 512)
</script>

<span class="logo" class:dark={on === 'dark'}>
  {#if logo}
    <img src={logoSrc(logo, size)} alt="" width={size} height={size} loading={small ? 'lazy' : 'eager'} decoding="async" onerror={() => (failed = true)} />
  {:else}
    <span class="initial">{nameOf(brief).slice(0, 1)}</span>
  {/if}
</span>

<style>
  .logo {
    display: grid;
    grid-template: minmax(0, 1fr) / minmax(0, 1fr);
    place-items: center;
    width: 100%;
    height: 100%;
    min-height: 0;
    overflow: hidden;
    background: #fff;
    color: #14151a;
  }
  .logo.dark {
    background: #14151a;
    color: #fff;
  }
  img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }
  .initial {
    font: 700 1.6em / 1 var(--display);
  }
</style>
