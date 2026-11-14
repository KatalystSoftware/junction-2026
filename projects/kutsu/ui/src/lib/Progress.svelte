<script lang="ts">
  import type { Invitee } from './events'
  import { reviewOf, stateNames } from './state.svelte'
  import type { Status } from './types'

  // How far an event's sign-ups are: one bar in three parts, and the count of each beside its colour.
  // `legend` off draws the bar alone, for a place that says the counts in its own words
  let { employers, coming, legend = true }: { employers: Invitee[]; coming: boolean; legend?: boolean } = $props()
  const ORDER: Status[] = ['joined', 'invited', 'draft']
  const parts = $derived(
    ORDER.map((status) => ({
      status,
      n: employers.filter((e) => reviewOf(e.brief).status === status).length,
      label: stateNames(coming)[status].toLowerCase(),
    })),
  )
</script>

<div>
  <div class="bar" role="img" aria-label={parts.map((p) => `${String(p.n)} ${p.label}`).join(', ')}>
    {#each parts.filter((p) => p.n) as part (part.status)}<span class={part.status} style:flex-grow={part.n}></span>{/each}
  </div>
  {#if legend}
  <p>
    {#if coming}<span class="what">Profiles</span>{/if}{#each parts as part (part.status)}<span class={part.status}><b>{part.n}</b> {part.label}</span>{/each}
  </p>
  {/if}
</div>

<style>
  .bar {
    display: flex;
    gap: 2px;
    height: 0.625rem;
  }
  .bar span {
    border-radius: 3px;
    background: var(--line);
    transition: flex-grow 0.5s var(--ease);
  }
  .bar .joined {
    background: var(--ok);
  }
  .bar .invited {
    background: var(--wait);
  }
  p {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s1) var(--s5);
    margin-top: var(--s2);
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  p span:not(.what)::before {
    content: '';
    display: inline-block;
    width: 0.5rem;
    height: 0.5rem;
    margin-right: var(--s2);
    border-radius: 50%;
    background: var(--line);
  }
  p .joined::before {
    background: var(--ok);
  }
  p .invited::before {
    background: var(--wait);
  }
  b {
    color: var(--ink);
  }
</style>
