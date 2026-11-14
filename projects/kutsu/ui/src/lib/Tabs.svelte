<script lang="ts">
  import type { Plan } from './events'
  import { applications } from './manage.svelte'

  // The two sides of managing one event: whom to invite, and the applications that came back from the regular invitation.
  let { plan, tab }: { plan: Plan; tab: 'invite' | 'applications' } = $props()
  const n = $derived(applications.list.length)
</script>

<nav class="tabs" aria-label="Event pages">
  <a href="#/event/{plan.slug}" class:on={tab === 'invite'}>Employers and people</a>
  <a href="#/event/{plan.slug}/applications" class:on={tab === 'applications'}>Applications{#if n}<span>{n}</span>{/if}</a>
</nav>

<style>
  .tabs {
    display: flex;
    gap: var(--s1);
    border-bottom: 1px solid var(--line);
  }
  .tabs a {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    margin-bottom: -1px;
    padding: var(--s2) var(--s3) var(--s3);
    border-bottom: 2px solid transparent;
    font-size: var(--t-sm);
    font-weight: 600;
    color: var(--ink-2);
    text-decoration: none;
  }
  .tabs a:hover {
    color: var(--ink);
  }
  .tabs a.on {
    color: var(--ink);
    border-bottom-color: var(--city);
  }
  .tabs span {
    padding: 0 0.5em;
    border-radius: 99px;
    background: var(--wash);
    font-size: var(--t-xs);
  }
</style>
