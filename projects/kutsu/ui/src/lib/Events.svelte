<script lang="ts">
  import Cite from './Cite.svelte'
  import { asking, confirmed, daysTo, recent, some, sourceOf, suggested, upcoming } from './events'
  import { when } from './format'
  import Icon from './Icon.svelte'
  import Logo from './Logo.svelte'
  import Progress from './Progress.svelte'
  import { app, nameOf } from './state.svelte'
  import Wall from './Wall.svelte'

  // Where Espoo starts: the event being prepared, the events worth holding next, and the past events
  // whose people make up the pool every suggestion draws on.
  let all = $state(false)
  const next = $derived(app.presets.map(upcoming))
  const ideas = $derived(suggested())
  const left = (date: string) => {
    const days = daysTo(date)
    return days > 1 ? `in ${String(days)} days` : days === 1 ? 'tomorrow' : days === 0 ? 'today' : ''
  }
</script>

<main>
  <h1>Events</h1>

  {#each next as plan (plan.slug)}
    <section class="next">
      <div class="title">
        <h2><a href="#/event/{plan.slug}">{plan.title}</a></h2>
        <p>{[when(plan.date), left(plan.date)].filter(Boolean).join(', ')}</p>
      </div>
      <ul class="asked">
        {#each plan.fields.slice(0, 3) as f (f.name)}
          <li><b>{f.name}</b><span>{asking(f.employers.length, f.employers.filter(confirmed).length)}, {some(f.people.people)} people</span></li>
        {/each}
        <li><span class="sample">people are sample data</span></li>
      </ul>
      <div class="who">
        <Wall briefs={plan.employers.map((e) => e.brief)} />
        <Progress employers={plan.employers} coming={plan.coming} />
      </div>
      <a class="btn primary" href="#/event/{plan.slug}">Open the event<Icon name="flat" size={18} /></a>
    </section>
  {/each}

  <section>
    <h2>Suggested next</h2>
    <ul class="ideas">
      {#each ideas.slice(0, all ? ideas.length : 3) as plan (plan.slug)}
        <li>
          <div>
            <a class="field" href="#/event/{plan.slug}">{plan.title}<Icon name="flat" size={18} /></a>
            <p class="numbers"><b>{plan.employers.length}</b> employers, <b>{some(plan.fields[0]?.people.people ?? 0)}</b> people</p>
          </div>
          <ul class="news">
            {#each plan.employers.filter(recent).slice(0, 2) as e (e.brief.id)}
              {@const source = sourceOf(e)}
              <li>
                <span class="tile"><Logo brief={e.brief} small /></span>
                <span><b>{nameOf(e.brief)}</b> {e.news?.line}{#if source && e.news}{' '}<Cite signal={source} label={when(e.news.date)} />{/if}</span>
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
    {#if ideas.length > 3 && !all}
      <button class="btn quiet" onclick={() => (all = true)}><Icon name="plus" size={16} />{ideas.length - 3} more fields</button>
    {/if}
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
    gap: var(--s8);
    max-width: 76rem;
    padding: var(--s7) var(--s7) var(--s8) var(--s6);
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

  /* the event being prepared: its name, every employer's logo, and how far the sign-ups are */
  .next {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: var(--s6) var(--s7);
    align-items: start;
  }
  .next h2 {
    font: 800 var(--t-2xl) / 0.95 var(--display);
    letter-spacing: -0.035em;
  }
  .next h2 a {
    text-decoration: none;
  }
  .title p {
    margin-top: var(--s3);
    font-size: var(--t-lg);
    color: var(--ink-2);
  }
  .asked {
    display: grid;
    gap: var(--s2);
    padding-top: var(--s2);
    font-size: var(--t-sm);
    line-height: 1.3;
  }
  .asked li {
    display: grid;
    justify-items: start;
  }
  .asked span {
    color: var(--ink-2);
  }
  .who {
    grid-column: 1 / -1;
    display: grid;
    gap: var(--s4);
  }
  .next .btn {
    justify-self: start;
  }
  .asked .sample {
    margin-top: var(--s1);
    padding: 0.2em 0.6em;
    border-radius: 99px;
    background: var(--wash);
    font: 600 var(--t-xs) / 1.4 var(--text);
    white-space: nowrap;
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
  .news :global(.cite) {
    white-space: nowrap;
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
  .ideas + .btn {
    margin-left: calc(-1 * var(--s2));
  }

  .past {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: var(--s5);
    margin-top: var(--s4);
  }
  .past li {
    display: grid;
    align-content: start;
    padding-top: var(--s2);
    border-top: 2px solid var(--city);
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
      padding: var(--s6) var(--s4) var(--s7);
      gap: var(--s7);
    }
    .next {
      grid-template-columns: 1fr;
      gap: var(--s5);
    }
    .ideas > li {
      grid-template-columns: 1fr;
    }
    .news {
      grid-row: auto;
    }
    .past {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
</style>
