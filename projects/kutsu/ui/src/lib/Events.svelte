<script lang="ts">
  import Cite from './Cite.svelte'
  import { recent, some, sourceOf, suggested, type Invitee, type Plan } from './events'
  import { when } from './format'
  import Icon from './Icon.svelte'
  import Logo from './Logo.svelte'
  import { app, nameOf } from './state.svelte'
  import Upcoming from './Upcoming.svelte'

  // Every event in full: the ones being prepared, every field where one is worth holding next, and the
  // past events whose people make up the pool each suggestion draws on.
  // each suggestion with up to two employers' news as its reason; one employer's news is a reason only once
  const ideas = $derived.by(() => {
    const used: string[] = []
    return suggested().map((plan): { plan: Plan; reasons: Invitee[] } => {
      const reasons = plan.employers.filter((e) => recent(e) && !used.includes(e.brief.id)).slice(0, 2)
      used.push(...reasons.map((e) => e.brief.id))
      return { plan, reasons }
    })
  })
</script>

<main>
  <h1>Events</h1>

  <Upcoming />

  <section>
    <h2>Proposed events</h2>
    <ul class="ideas">
      {#each ideas as { plan, reasons } (plan.slug)}
        <li>
          <div>
            <a class="field" href="#/event/{plan.slug}">{plan.title}<Icon name="flat" size={18} /></a>
            <p class="numbers"><b>{plan.employers.length}</b> employers, <b>{some(plan.fields[0]?.people.people ?? 0)}</b> people</p>
          </div>
          <ul class="news">
            {#each reasons as e (e.brief.id)}
              {@const source = sourceOf(e)}
              <li>
                <span class="tile"><Logo brief={e.brief} small /></span>
                <span><b>{nameOf(e.brief)}</b> {e.news?.line}{#if e.news}, {when(e.news.date)}{/if}{#if source}<Cite signal={source} n={1} />{/if}</span>
              </li>
            {/each}
          </ul>
          <p class="more">
            {#each plan.employers.slice(0, 6) as { brief } (brief.id)}<span class="tile"><Logo {brief} small /></span>{/each}
            {#if plan.employers.length > 6}<span class="rest">+{plan.employers.length - 6}</span>{/if}
          </p>
        </li>
      {/each}
    </ul>
  </section>

  <section>
    <h2>Past events</h2>
    <ol class="past">
      {#each app.pool.events.toReversed() as event (event.id)}
        <li>
          <a href={event.url} target="_blank" rel="noopener">{event.name}<Icon name="out" size={14} /></a>
          <small>{[when(event.date), event.where === 'Online' ? 'online' : event.where, event.published].filter(Boolean).join(', ')}</small>
        </li>
      {/each}
    </ol>
  </section>

</main>

<style>
  main {
    --brand: var(--city);
    --brand-ink: var(--city-ink);
    display: grid;
    gap: var(--s7);
    padding: 0 0 var(--s8);
  }
  main > section {
    max-width: 76rem;
    padding: 0 var(--s7) 0 var(--s6);
  }
  /* the screen is named in the rail; here the next event is the headline */
  h1 {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }
  section > h2 {
    font-size: var(--t-lg);
    letter-spacing: -0.01em;
  }

  /* suggestions are a ruled list, one line of reasoning each: the field, why now, who */
  .ideas {
    margin-top: var(--s3);
  }
  .ideas > li {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.5fr) auto;
    gap: var(--s4) var(--s6);
    align-items: start;
    padding: var(--s5) 0;
    border-top: 1px solid var(--line);
  }
  .field {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    min-height: 2.75rem;
    font: 700 var(--t-xl) / 1.05 var(--display);
    letter-spacing: -0.025em;
    text-decoration: none;
  }
  .field :global(svg) {
    flex: none;
    color: var(--ink-2);
    transition: transform 0.2s var(--ease);
  }
  .field:hover :global(svg) {
    transform: translateX(4px);
    color: var(--ink);
  }
  .numbers {
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  .numbers b {
    color: var(--ink);
  }
  .news {
    display: grid;
    gap: var(--s3);
    padding-top: var(--s2);
    line-height: 1.4;
  }
  .news li {
    display: grid;
    grid-template-columns: 1.5rem 1fr;
    gap: var(--s3);
  }
  .news b {
    font-weight: 600;
  }
  .tile {
    flex: none;
    width: 1.5rem;
    height: 1.5rem;
    padding: 2px;
    border-radius: 4px;
    overflow: hidden;
    background: #fff;
    box-shadow: 0 0 0 1px var(--line);
    font-size: 0.5rem;
  }
  .tile:has(:global(.dark)) {
    background: #14151a;
  }
  .more {
    display: flex;
    align-items: center;
    gap: var(--s1);
    padding-top: var(--s2);
  }
  .rest {
    margin-left: var(--s1);
    font-size: var(--t-sm);
    color: var(--ink-2);
  }

  .past {
    margin-top: var(--s3);
  }
  .past li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0 var(--s4);
    border-top: 1px solid var(--line);
    line-height: 1.3;
  }
  .past a {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    min-height: 2.75rem;
    font-weight: 600;
    text-decoration: none;
  }
  .past a:hover {
    text-decoration: underline;
  }
  .past small {
    font-size: var(--t-sm);
    color: var(--ink-2);
  }

  @media (max-width: 1100px) {
    .ideas > li {
      grid-template-columns: minmax(0, 1fr) auto;
    }
    .news {
      grid-column: 1 / -1;
      grid-row: 2;
      padding-top: 0;
    }
  }
  @media (max-width: 820px) {
    main {
      gap: var(--s6);
    }
    main > section {
      padding: 0 var(--s4);
    }
    .ideas > li {
      grid-template-columns: 1fr;
    }
    .news {
      grid-row: auto;
    }
  }
</style>
