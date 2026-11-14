<script lang="ts">
  import { ago, clock } from './format'
  import Icon from './Icon.svelte'
  import Logo from './Logo.svelte'
  import { app, nameOf } from './state.svelte'
  import type { Brief } from './types'

  // What Context.dev's monitors saw change: a job opening on a careers page, or news that a company
  // is growing. For one employer when `brief` is given, otherwise for all of them, newest first.
  // This is the reason to invite someone that arrives by itself.
  let { brief }: { brief?: Brief } = $props()
  const MOST = 6

  const changes = $derived(
    app.watch.changes
      .filter((c) => (brief ? c.brief === brief.id : true))
      .map((c) => ({ ...c, of: app.briefs.find((b) => b.id === c.brief) }))
      .slice(0, MOST),
  )
  const watched = $derived(brief ? [app.watch.watched[brief.id] ?? {}] : Object.values(app.watch.watched))
  const careers = $derived(watched.filter((w) => w.careers).length)
  const news = $derived(watched.filter((w) => w.news).length)
  const next = $derived(watched.flatMap((w) => [w.careers?.next_run_at, w.news?.next_run_at]).filter((t): t is string => !!t && t > new Date().toISOString()).sort()[0])
  const watching = $derived(
    brief
      ? [careers && 'its careers page', news && 'news about it'].filter(Boolean).join(' and ')
      : `${String(careers)} careers pages and news about ${String(news)} employers`,
  )
</script>

{#if careers || news}
  <section>
    {#if changes.length}
      <h2>{brief ? 'Changed since the draft' : 'Changed lately'}</h2>
      <ul>
        {#each changes as change (change.id)}
          <li>
            {#if !brief && change.of}<a class="tile" href="#/{encodeURIComponent(change.brief)}" aria-label={nameOf(change.of)}><Logo brief={change.of} small /></a>{/if}
            <p>
              {#if !brief && change.of}<b>{nameOf(change.of)}</b>{/if}
              {change.title}
              <span>{change.summary}</span>
            </p>
            <a class="when" href={change.url} target="_blank" rel="noopener">{change.kind === 'careers' ? 'Careers page' : 'News'}, {ago(change.detected_at)}<Icon name="out" size={14} /></a>
          </li>
        {/each}
      </ul>
    {/if}
    <p class="watching">
      Watching {watching} for changes{next ? `, next at ${clock(next)}` : ''}.{changes.length ? '' : ' Nothing has changed yet.'}
    </p>
  </section>
{/if}

<style>
  h2 {
    font-size: var(--t-lg);
    letter-spacing: -0.01em;
  }
  ul {
    margin-top: var(--s3);
  }
  li {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    gap: var(--s2) var(--s4);
    align-items: start;
    padding: var(--s3) 0;
    border-top: 1px solid var(--line);
  }
  .tile {
    display: block;
    width: 2rem;
    height: 2rem;
    padding: 3px;
    border-radius: 4px;
    overflow: hidden;
    background: #fff;
    box-shadow: 0 0 0 1px var(--line);
    font-size: 0.6rem;
  }
  .tile:has(:global(.dark)) {
    background: #14151a;
  }
  li p {
    grid-column: 2;
    line-height: 1.4;
  }
  li b {
    margin-right: var(--s1);
  }
  li span {
    display: block;
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  .when {
    grid-column: 3;
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    min-height: 2rem;
    font-size: var(--t-sm);
    color: var(--ink-2);
    white-space: nowrap;
    text-decoration: none;
  }
  .when:hover {
    color: var(--ink);
  }
  .watching {
    margin-top: var(--s2);
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  @media (max-width: 820px) {
    .when {
      grid-column: 2;
    }
  }
</style>
