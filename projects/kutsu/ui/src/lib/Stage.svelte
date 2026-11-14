<script lang="ts">
  import { host } from './format'
  import Icon from './Icon.svelte'
  import Logo from './Logo.svelte'
  import { nameOf } from './state.svelte'
  import type { Brief } from './types'

  // The company's own ground: its logo at poster scale beside a field of its colour.
  let { brief }: { brief: Brief } = $props()
  const identity = $derived(brief.identity)
  const momentum = $derived(brief.card.momentum)
  const facts = $derived(
    [
      ['Field', identity?.industries[0]?.split(': ').pop()],
      ['Size', identity?.employees?.replace(' to ', '–')],
      ['Based in', [identity?.city, identity?.country].filter(Boolean).join(', ')],
      ['Open tech roles in Espoo', brief.in_espoo_data ? String(brief.open_roles) : ''],
    ].filter(([, value]) => value),
  )
  const ARROW = { growing: 'up', shrinking: 'down', steady: 'flat' } as const
</script>

<header class="stage">
  {#key brief.id}
    <div class="plate" class:dark={identity?.logo_on === 'dark'}>
      <div class="mark"><Logo {brief} /></div>
    </div>
    <div class="field">
      <div class="top">
        {#if momentum in ARROW}
          <span class="momentum"><Icon name={ARROW[momentum as keyof typeof ARROW]} size={16} />{momentum}</span>
        {/if}
        {#if brief.website}
          <a class="site" href={brief.website} target="_blank" rel="noopener">{host(brief.website)}<Icon name="out" size={14} /></a>
        {/if}
      </div>
      <h1>{nameOf(brief)}</h1>
      {#if brief.card.pitch || identity?.slogan}<p class="slogan">{brief.card.pitch || identity?.slogan}</p>{/if}
      {#if facts.length}
        <dl>
          {#each facts as [label, value] (label)}
            <div><dt>{label}</dt><dd>{value}</dd></div>
          {/each}
        </dl>
      {/if}
    </div>
  {/key}
</header>

<style>
  .stage {
    display: grid;
    grid-template-columns: minmax(12rem, 30%) 1fr;
    min-height: clamp(15rem, 38vh, 21rem);
    background: var(--brand);
  }
  .plate {
    display: grid;
    place-items: center;
    padding: var(--s6);
    overflow: hidden;
    background: #fff;
  }
  .plate.dark {
    background: #14151a;
  }
  .mark {
    width: min(100%, 16rem);
    height: clamp(5rem, 16vh, 9rem);
    font-size: 3rem;
    animation: arrive 0.7s var(--ease) backwards;
  }
  .mark :global(.logo) {
    background: none;
  }
  .field {
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    gap: var(--s3);
    padding: var(--s5) var(--s7) var(--s6) var(--s6);
    background: var(--brand);
    color: var(--brand-ink);
    animation: wipe 0.75s var(--ease) backwards;
  }
  .top {
    display: flex;
    align-items: center;
    gap: var(--s4);
    margin-bottom: auto;
    font-size: var(--t-sm);
    font-weight: 600;
  }
  .momentum {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    padding: var(--s1) var(--s3) var(--s1) var(--s2);
    border: 1px solid color-mix(in oklch, var(--brand-ink) 45%, transparent);
    border-radius: 99px;
    text-transform: capitalize;
  }
  .site {
    /* the demo's own button sits at the top right */
    margin-right: 4.5rem;
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    margin-left: auto;
    text-decoration: none;
  }
  .site:hover {
    text-decoration: underline;
  }
  h1 {
    font-size: var(--t-2xl);
    font-weight: 800;
    letter-spacing: -0.035em;
    line-height: 0.95;
  }
  .slogan {
    max-width: 46ch;
    font-size: var(--t-lg);
    line-height: 1.3;
    color: color-mix(in oklch, var(--brand-ink) 86%, var(--brand));
  }
  dl {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s2) var(--s6);
    margin-top: var(--s3);
    padding-top: var(--s4);
    border-top: 1px solid color-mix(in oklch, var(--brand-ink) 28%, transparent);
  }
  dt {
    font-size: var(--t-xs);
    color: color-mix(in oklch, var(--brand-ink) 78%, var(--brand));
  }
  dd {
    font-weight: 600;
  }
  :focus-visible {
    outline-color: var(--brand-ink);
  }
  @keyframes wipe {
    from {
      clip-path: inset(0 100% 0 0);
    }
    to {
      clip-path: inset(0);
    }
  }
  @keyframes arrive {
    from {
      opacity: 0;
      scale: 0.9;
    }
  }
  @media (max-width: 820px) {
    .stage {
      grid-template-columns: 1fr;
    }
    .plate {
      padding: var(--s5);
    }
    .field {
      padding: var(--s5);
    }
  }
</style>
