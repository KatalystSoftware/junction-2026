<script lang="ts">
  import { daysTo, recent, some, suggested, upcoming } from './events'
  import { when } from './format'
  import Icon from './Icon.svelte'
  import Logo from './Logo.svelte'
  import { app, nameOf, reviewOf } from './state.svelte'
  import type { Status } from './types'

  // Where Espoo starts: the event being prepared, the events worth holding next, and the past events
  // whose people make up the pool every suggestion draws on.
  const next = $derived(app.presets.map(upcoming))
  const ideas = $derived(suggested().slice(0, 6))
  const tallest = $derived(Math.max(1, ...app.pool.events.map((e) => e.people)))

  const STATES: [Status, string][] = [['joined', 'signed up'], ['invited', 'invited'], ['draft', 'to invite']]
  const left = (date: string) => {
    const days = daysTo(date)
    return days > 1 ? `in ${String(days)} days` : days === 1 ? 'tomorrow' : days === 0 ? 'today' : ''
  }
</script>

<main>
  <header>
    <h1>Events</h1>
    <p>
      {app.pool.people.toLocaleString('en')} people have come to Espoo's events. Each new event starts from them, and from what employers
      have said in public.
    </p>
  </header>

  {#each next as plan (plan.slug)}
    {@const by = (status: Status) => plan.employers.filter((e) => reviewOf(e.brief).status === status)}
    <section class="next">
      <div class="title">
        <h2><a href="#/event/{plan.slug}">{plan.title}</a></h2>
        <p>{[when(plan.date), left(plan.date)].filter(Boolean).join(', ')}</p>
      </div>
      <dl>
        <div><dt>employers</dt><dd>{plan.employers.length}</dd></div>
        <div><dt>people in the pool do what they ask for</dt><dd>{some(plan.people.people)}</dd></div>
      </dl>
      <div class="progress">
        <div class="bar" role="img" aria-label={STATES.map(([s, label]) => `${String(by(s).length)} ${label}`).join(', ')}>
          {#each STATES as [status] (status)}
            {#if by(status).length}<span class={status} style:flex-grow={by(status).length}></span>{/if}
          {/each}
        </div>
        <p>
          {#each STATES as [status, label] (status)}<span class={status}><b>{by(status).length}</b> {label}</span>{/each}
        </p>
      </div>
      <ul class="wall">
        {#each plan.employers as { brief } (brief.id)}
          <li>
            <a href="#/{encodeURIComponent(brief.id)}" class={reviewOf(brief).status} title="{nameOf(brief)}, {STATES.find(([s]) => s === reviewOf(brief).status)?.[1]}">
              <Logo {brief} small />
            </a>
          </li>
        {/each}
      </ul>
      <a class="btn primary" href="#/event/{plan.slug}">Who to invite<Icon name="flat" size={18} /></a>
    </section>
  {/each}

  <section>
    <h2>Suggested next</h2>
    <p class="how">Fields where employers have said they need people and the pool already has them. Those with fresh funding or growth news come first.</p>
    <ul class="ideas">
      {#each ideas as plan (plan.slug)}
        <li>
          <a href="#/event/{plan.slug}">
            <h3>{plan.title}</h3>
            <p class="numbers">
              <span><b>{plan.employers.length}</b> employers ask</span>
              <span><b>{some(plan.people.people)}</b> people do it</span>
            </p>
            <ul class="news">
              {#each plan.employers.filter(recent).slice(0, 2) as { brief, news } (brief.id)}
                <li><span class="tile"><Logo {brief} small /></span><span><b>{nameOf(brief)}</b> {news?.line}</span></li>
              {/each}
            </ul>
            <p class="more">
              {#each plan.employers.slice(0, 7) as { brief } (brief.id)}<span class="tile"><Logo {brief} small /></span>{/each}
              {#if plan.employers.length > 7}<span class="rest">+{plan.employers.length - 7}</span>{/if}
            </p>
          </a>
        </li>
      {/each}
    </ul>
  </section>

  <section>
    <h2>Past events <span class="sample">sample data</span></h2>
    <ol class="past">
      {#each app.pool.events as event (event.id)}
        <li title="{event.name}: {event.people} people, {event.employers} employers">
          <span class="column"><span style:height="{(event.people / tallest) * 100}%"></span></span>
          <b>{event.people}</b>
          <span class="name">{event.name}</span>
          <small>{when(event.date)}, {event.where === 'Online' ? 'online' : event.where}, {event.employers} employers</small>
        </li>
      {/each}
    </ol>
    <p class="note">{app.pool.note} Employers, and everything quoted from them, are real.</p>
  </section>
</main>

<style>
  main {
    --brand: var(--city);
    --brand-ink: var(--city-ink);
    display: grid;
    gap: var(--s7);
    max-width: 68rem;
    padding: var(--s7) var(--s7) var(--s8) var(--s6);
  }
  header p {
    max-width: 56ch;
    margin-top: var(--s3);
    font-size: var(--t-lg);
    line-height: 1.4;
    color: var(--ink-2);
  }
  h1 {
    font-size: var(--t-2xl);
  }
  h2 {
    font-size: var(--t-xl);
  }
  h2 a {
    text-decoration: none;
  }
  h2 a:hover {
    text-decoration: underline;
  }

  /* the event being prepared: its name, how far the invitations are, and every employer's logo */
  .next {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: var(--s5) var(--s7);
    align-items: end;
    padding: var(--s6);
    border-radius: var(--r2);
    background: var(--wash);
  }
  .title p {
    margin-top: var(--s2);
    color: var(--ink-2);
  }
  dl {
    display: flex;
    gap: var(--s6);
    margin: 0;
  }
  dl div {
    display: flex;
    flex-direction: column-reverse;
    max-width: 11rem;
  }
  dd {
    font: 700 var(--t-xl) / 1 var(--display);
    letter-spacing: -0.02em;
  }
  dt {
    margin-top: var(--s1);
    font-size: var(--t-sm);
    line-height: 1.3;
    color: var(--ink-2);
  }
  .progress,
  .wall {
    grid-column: 1 / -1;
  }
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
  .progress p {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s2) var(--s5);
    margin-top: var(--s2);
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  .progress p span::before {
    content: '';
    display: inline-block;
    width: 0.5rem;
    height: 0.5rem;
    margin-right: var(--s2);
    border-radius: 50%;
    background: var(--line);
  }
  .progress p .joined::before {
    background: var(--ok);
  }
  .progress p .invited::before {
    background: var(--wait);
  }
  .progress b {
    color: var(--ink);
  }
  .wall {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s2);
  }
  .wall a {
    display: block;
    width: 3rem;
    height: 3rem;
    padding: 6px;
    border-radius: var(--r1);
    overflow: hidden;
    background: #fff;
    box-shadow: 0 0 0 1px var(--line);
    transition: transform 0.15s var(--ease), box-shadow 0.15s;
  }
  .wall a:has(:global(.dark)),
  .tile:has(:global(.dark)) {
    background: #14151a;
  }
  .wall a:hover {
    transform: translateY(-2px);
    box-shadow: 0 0 0 1px var(--ink-2);
  }
  .wall a.invited {
    box-shadow: 0 0 0 2px var(--wait);
  }
  .wall a.joined {
    box-shadow: 0 0 0 2px var(--ok);
  }
  .next .btn {
    justify-self: start;
  }

  .how {
    max-width: 62ch;
    margin: var(--s2) 0 var(--s5);
    color: var(--ink-2);
  }
  .ideas {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--s4);
  }
  .ideas > li > a {
    display: grid;
    grid-template-rows: auto auto 1fr auto;
    gap: var(--s4);
    height: 100%;
    padding: var(--s5);
    border: 1px solid var(--line);
    border-radius: var(--r2);
    text-decoration: none;
    transition: border-color 0.15s, transform 0.2s var(--ease), box-shadow 0.2s;
  }
  .ideas > li > a:hover {
    border-color: var(--city);
    transform: translateY(-2px);
    box-shadow: var(--lift);
  }
  h3 {
    font-size: var(--t-lg);
    letter-spacing: -0.015em;
    line-height: 1.15;
  }
  .numbers {
    display: flex;
    gap: var(--s5);
    font-size: var(--t-sm);
    line-height: 1.3;
    color: var(--ink-2);
  }
  .numbers span {
    display: grid;
  }
  .numbers b {
    font: 700 var(--t-xl) / 1.05 var(--display);
    letter-spacing: -0.02em;
    color: var(--ink);
  }
  .news {
    display: grid;
    align-content: start;
    gap: var(--s3);
    font-size: var(--t-sm);
    line-height: 1.35;
  }
  .news li {
    display: grid;
    grid-template-columns: 1.5rem 1fr;
    gap: var(--s2);
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
  .more {
    display: flex;
    align-items: center;
    gap: var(--s1);
  }
  .rest {
    margin-left: var(--s1);
    font-size: var(--t-sm);
    color: var(--ink-2);
  }

  .sample {
    margin-left: var(--s2);
    padding: 0.2em 0.6em;
    border-radius: 99px;
    background: var(--wash);
    font: 600 var(--t-xs) / 1.4 var(--text);
    letter-spacing: 0;
    color: var(--ink-2);
    vertical-align: middle;
  }
  .past {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: var(--s5);
    margin-top: var(--s5);
  }
  .past li {
    display: grid;
    line-height: 1.3;
  }
  .column {
    display: flex;
    align-items: flex-end;
    height: 5rem;
    margin-bottom: var(--s2);
    border-bottom: 1px solid var(--line);
  }
  .column span {
    width: 2.5rem;
    border-radius: 4px 4px 0 0;
    background: var(--city);
  }
  .past b {
    font: 700 var(--t-lg) / 1.2 var(--display);
  }
  .past small {
    font-size: var(--t-xs);
    color: var(--ink-2);
  }
  .name {
    font-weight: 600;
  }
  .note {
    max-width: 70ch;
    margin-top: var(--s5);
    font-size: var(--t-sm);
    color: var(--ink-2);
  }

  @media (max-width: 820px) {
    main {
      padding: var(--s6) var(--s4) var(--s7);
      gap: var(--s6);
    }
    .next {
      grid-template-columns: 1fr;
      padding: var(--s5) var(--s4);
    }
    .past {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .ideas {
      grid-template-columns: 1fr;
    }
  }
  @media (min-width: 821px) and (max-width: 1180px) {
    .ideas {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
</style>
