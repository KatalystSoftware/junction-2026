<script lang="ts">
  import { host, when } from './format'
  import Icon from './Icon.svelte'
  import type { Brief } from './types'

  // What the company has said in public, one ruled row per statement. The numbers are the ones the
  // needs cite. A row opens to show the sentence it was read from.
  let { brief }: { brief: Brief } = $props()
  let open = $state<string | null>(null)
  const dropped = $derived(brief.stats.signals_dropped)
</script>

<section>
  <h2>Public record</h2>
  <p class="note">
    {brief.signals.length} statements, each found word for word on the page it links to.
    {#if dropped}{dropped} more {dropped === 1 ? 'was' : 'were'} dropped: the quote was not on the page, or it named a person.{/if}
  </p>
  <ol>
    {#each brief.signals as s, i (s.id)}
      <li class:open={open === s.id}>
        <button class="row" aria-expanded={open === s.id} onclick={() => (open = open === s.id ? null : s.id)}>
          <span class="n">{i + 1}</span>
          <span class="when">{when(s.date) || '—'}</span>
          <span class="type">{s.type}</span>
          <span class="claim">{s.claim}</span>
        </button>
        <a class="src" href={s.source_url} target="_blank" rel="noopener">{host(s.source_url)}<Icon name="out" size={14} /></a>
        {#if open === s.id}<q>{s.quote}</q>{/if}
      </li>
    {/each}
  </ol>
</section>

<style>
  h2 {
    font-size: var(--t-lg);
    letter-spacing: -0.01em;
  }
  .note {
    margin-top: var(--s1);
    max-width: 70ch;
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  ol {
    margin-top: var(--s4);
    border-bottom: 1px solid var(--line);
    font-size: var(--t-sm);
  }
  li {
    display: grid;
    grid-template-columns: 1fr auto;
    column-gap: var(--s4);
    border-top: 1px solid var(--line);
  }
  .row {
    display: grid;
    grid-template-columns: 1.5rem 5.25rem 6.5rem 1fr;
    column-gap: var(--s3);
    align-items: baseline;
    padding: var(--s3) 0;
    border: 0;
    background: none;
    text-align: left;
  }
  .row:hover .claim {
    text-decoration: underline;
    text-decoration-color: var(--line);
    text-underline-offset: 0.2em;
  }
  .n {
    font-weight: 700;
    color: var(--ink-2);
  }
  .when,
  .type {
    color: var(--ink-2);
  }
  .type {
    text-transform: capitalize;
  }
  .claim {
    color: var(--ink);
    text-wrap: pretty;
  }
  .src {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    align-self: baseline;
    padding: var(--s3) 0;
    color: var(--ink-2);
    text-decoration: none;
    white-space: nowrap;
  }
  .src:hover {
    color: var(--ink);
    text-decoration: underline;
  }
  q {
    grid-column: 1 / -1;
    margin: 0 0 var(--s4) calc(1.5rem + 5.25rem + 6.5rem + 3 * var(--s3));
    padding: var(--s3) var(--s4);
    max-width: 70ch;
    border-radius: var(--r1);
    background: var(--wash);
    font-size: var(--t-md);
    line-height: 1.45;
    quotes: '“' '”';
  }
  @media (max-width: 820px) {
    .row {
      grid-template-columns: 1.5rem 1fr;
    }
    .when,
    .type {
      display: none;
    }
    li {
      grid-template-columns: 1fr;
    }
    .src {
      padding: 0 0 var(--s3) calc(1.5rem + var(--s3));
    }
    q {
      margin-left: 0;
    }
  }
</style>
