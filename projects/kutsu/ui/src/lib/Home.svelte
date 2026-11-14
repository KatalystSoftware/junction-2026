<script lang="ts">
  import { news, some, suggested, upcoming } from './events'
  import { ago, when } from './format'
  import Icon from './Icon.svelte'
  import Logo from './Logo.svelte'
  import { applications, decisionOf } from './manage.svelte'
  import { app, nameOf, reviewOf } from './state.svelte'
  import Upcoming from './Upcoming.svelte'

  // Where an organiser lands: the state of things at a glance, each block the few things that matter
  // now and the way to its full page. Nothing here is a list in full; the lists are one press away.
  const ideas = $derived(suggested().slice(0, 3))
  const fields = $derived(
    Object.entries(app.pool.fields)
      .map(([name, f]) => ({ name, people: f.people }))
      .sort((a, b) => b.people - a.people)
      .slice(0, 4),
  )
  const most = $derived(Math.max(1, ...fields.map((f) => f.people)))
  // what the monitors caught lately, or, until they catch something, the newest news the companies would tell
  const changes = $derived(app.watch.changes.slice(0, 3).map((c) => ({ id: c.id, brief: app.briefs.find((b) => b.id === c.brief), says: c.title, at: ago(c.detected_at) })))
  const newest = $derived(
    app.briefs
      .map((brief) => ({ brief, told: news(brief) }))
      .filter((x) => !!x.told)
      .sort((a, b) => (b.told?.date ?? '').localeCompare(a.told?.date ?? ''))
      .slice(0, 3),
  )
  const forum = $derived(app.presets[0] ? upcoming(app.presets[0]) : undefined)
  const toReview = $derived(applications.list.filter((a) => !decisionOf('espoo', a.id)).length)
  const sent = $derived(forum?.employers.filter((e) => reviewOf(e.brief).status === 'invited').length ?? 0)
  const unsent = $derived(forum?.employers.filter((e) => reviewOf(e.brief).status === 'draft').length ?? 0)
</script>

<main>
  <h1>Home</h1>
  <Upcoming />

  <div class="blocks">
    <section>
      <h2><a href="#/events">Proposed events<Icon name="flat" size={16} /></a></h2>
      <ul class="rows">
        {#each ideas as plan (plan.slug)}
          <li>
            <a href="#/event/{plan.slug}"><b>{plan.title}</b><span>{plan.employers.length} employers, {some(plan.fields[0]?.people.people ?? 0)} people</span></a>
          </li>
        {/each}
      </ul>
    </section>

    <section>
      <h2><a href="#/pool">Talent pool<Icon name="flat" size={16} /></a><span class="sample">sample data</span></h2>
      <p class="big"><b>{app.pool.people.toLocaleString('en')}</b> people came to earlier events</p>
      <ul class="bars">
        {#each fields as f (f.name)}
          <li><span>{f.name}</span><span class="meter"><span style:width="{(f.people / most) * 100}%"></span></span><b>{f.people}</b></li>
        {/each}
      </ul>
    </section>

    <section>
      <h2><a href="#/companies">Companies<Icon name="flat" size={16} /></a></h2>
      <ul class="rows news">
        {#if changes.length}
          {#each changes as change (change.id)}
            {#if change.brief}
              <li>
                <a href="#/{encodeURIComponent(change.brief.id)}"><span class="tile"><Logo brief={change.brief} small /></span><b>{nameOf(change.brief)}</b><span>{change.says}, {change.at}</span></a>
              </li>
            {/if}
          {/each}
        {:else}
          {#each newest as { brief, told } (brief.id)}
            <li>
              <a href="#/{encodeURIComponent(brief.id)}"><span class="tile"><Logo {brief} small /></span><b>{nameOf(brief)}</b><span>{told?.line}{told ? `, ${when(told.date)}` : ''}</span></a>
            </li>
          {/each}
        {/if}
      </ul>
    </section>

    <section>
      <h2>Waiting for you</h2>
      <ul class="rows">
        {#if toReview}<li><a href="#/applications"><b>{toReview} applications to review</b><span>{forum?.title}</span></a></li>{/if}
        {#if sent}<li><a href="#/event/{forum?.slug}"><b>{sent} profiles sent, not yet confirmed</b><span>{forum?.title}</span></a></li>{/if}
        {#if unsent}<li><a href="#/event/{forum?.slug}"><b>{unsent} employers not yet sent their profile</b><span>{forum?.title}</span></a></li>{/if}
        {#if !toReview && !sent && !unsent}<li class="none">Nothing is waiting.</li>{/if}
      </ul>
    </section>
  </div>
</main>

<style>
  main {
    --brand: var(--city);
    --brand-ink: var(--city-ink);
    display: grid;
    gap: var(--s7);
    padding: 0 0 var(--s8);
  }
  /* the page is named in the navigation; here the next event is the headline */
  h1 {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }
  .blocks {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--s7) var(--s8);
    max-width: 76rem;
    padding: 0 var(--s7) 0 var(--s6);
  }
  h2 {
    display: flex;
    align-items: center;
    gap: var(--s3);
    min-height: 2.75rem;
    font-size: var(--t-lg);
    letter-spacing: -0.01em;
  }
  h2 a {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    min-height: 2.75rem;
    text-decoration: none;
  }
  h2 a :global(svg) {
    color: var(--ink-2);
    transition: transform 0.2s var(--ease);
  }
  h2 a:hover :global(svg) {
    transform: translateX(4px);
    color: var(--ink);
  }
  .sample {
    padding: 0.2em 0.6em;
    border-radius: 99px;
    background: var(--wash);
    font: 600 var(--t-xs) / 1.4 var(--text);
    letter-spacing: 0;
    color: var(--ink-2);
    white-space: nowrap;
  }
  .rows li {
    border-top: 1px solid var(--line);
  }
  .rows a {
    display: grid;
    gap: 0 var(--s3);
    min-height: 3.25rem;
    align-content: center;
    padding: var(--s2) 0;
    line-height: 1.3;
    text-decoration: none;
  }
  .rows a:hover b {
    text-decoration: underline;
  }
  .rows span {
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  .news a {
    grid-template-columns: 2rem minmax(0, 1fr);
  }
  .news .tile {
    grid-row: 1 / 3;
    align-self: center;
    width: 2rem;
    height: 2rem;
    padding: 3px;
    border-radius: 4px;
    overflow: hidden;
    background: #fff;
    box-shadow: 0 0 0 1px var(--line);
    font-size: 0.6rem;
  }
  .news .tile:has(:global(.dark)) {
    background: #14151a;
  }
  .none {
    padding: var(--s3) 0;
    color: var(--ink-2);
  }
  .big {
    margin: var(--s1) 0 var(--s3);
    color: var(--ink-2);
  }
  .big b {
    margin-right: var(--s2);
    font: 800 var(--t-xl) / 1 var(--display);
    letter-spacing: -0.03em;
    color: var(--ink);
  }
  .bars li {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 6rem 2.5rem;
    align-items: center;
    gap: var(--s3);
    padding: var(--s2) 0;
    border-top: 1px solid var(--line);
    font-size: var(--t-sm);
  }
  .bars b {
    text-align: right;
  }
  .meter {
    height: 0.375rem;
    border-radius: 99px;
    background: var(--line);
  }
  .meter span {
    display: block;
    height: 100%;
    border-radius: 99px;
    background: var(--city);
  }
  @media (max-width: 820px) {
    main {
      gap: var(--s6);
    }
    .blocks {
      grid-template-columns: minmax(0, 1fr);
      gap: var(--s6);
      padding: 0 var(--s4);
    }
  }
</style>
