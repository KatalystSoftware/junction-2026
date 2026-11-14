<script lang="ts">
  import { daysTo, news, some, suggested, upcoming } from './events'
  import { ago, when } from './format'
  import Icon from './Icon.svelte'
  import Logo from './Logo.svelte'
  import { applications, decisionOf, manage } from './manage.svelte'
  import Progress from './Progress.svelte'
  import { app, nameOf, reviewOf } from './state.svelte'
  import Wall from './Wall.svelte'

  // Where an organiser lands. The event being prepared is the whole upper half: how it is filling, each
  // number with what it is out of, and the one or two things to do next. Below it, smaller, three blocks
  // that each lead to one page: the events worth holding next, the pool, the companies. Nothing here is
  // a list in full, and a block with nothing in it says what to do about that.
  const plan = $derived(app.presets[0] ? upcoming(app.presets[0]) : undefined)
  const days = $derived(plan?.date ? daysTo(plan.date) : -1)
  const employers = $derived(plan?.employers ?? [])
  const confirmed = $derived(employers.filter((e) => reviewOf(e.brief).status === 'joined').length)
  const unsent = $derived(employers.filter((e) => reviewOf(e.brief).status === 'draft').length)
  const total = $derived(applications.list.length)
  const accepted = $derived(applications.list.filter((a) => decisionOf('espoo', a.id)?.d === 'accept').length)
  const declined = $derived(applications.list.filter((a) => decisionOf('espoo', a.id)?.d === 'decline').length)
  const waiting = $derived(total - accepted - declined)
  // what to do next, the most pressing first; the first is the screen's one primary action
  const next = $derived(
    [
      waiting > 0 && { label: `Review ${String(waiting)} ${waiting === 1 ? 'application' : 'applications'}`, href: '#/applications' },
      unsent > 0 && { label: `Send ${String(unsent)} ${unsent === 1 ? 'employer its' : 'employers their'} profile`, href: `#/event/${plan?.slug ?? ''}` },
      !manage.sent && { label: 'Invite people from the pool', href: `#/event/${plan?.slug ?? ''}` },
    ].filter((x) => !!x),
  )

  const ideas = $derived(suggested().slice(0, 3))
  const fields = $derived(
    Object.entries(app.pool.fields)
      .map(([name, f]) => ({ name, people: f.people }))
      .sort((a, b) => b.people - a.people)
      .slice(0, 3),
  )
  const most = $derived(Math.max(1, ...fields.map((f) => f.people)))
  // what the monitors caught lately, or, until they catch something, the newest news the companies would tell
  const changes = $derived(
    app.watch.changes
      .slice(0, 3)
      .map((c) => ({ id: c.id, brief: app.briefs.find((b) => b.id === c.brief), says: c.title, at: ago(c.detected_at) }))
      .filter((c) => !!c.brief),
  )
  const newest = $derived(
    app.briefs
      .map((brief) => ({ brief, told: news(brief) }))
      .filter((x) => !!x.told)
      .sort((a, b) => (b.told?.date ?? '').localeCompare(a.told?.date ?? ''))
      .slice(0, 3),
  )
</script>

<main>
  <h1>Home</h1>

  {#if plan}
    <section class="event">
      <p class="when">
        <span>{plan.when}</span>
        {#if days >= 0}<b>{days === 0 ? 'today' : days === 1 ? 'tomorrow' : `in ${String(days)} days`}</b>{/if}
      </p>
      <h2><a href="#/event/{plan.slug}">{plan.title}</a></h2>

      <dl>
        <div>
          <dt>Employers</dt>
          <dd><b>{employers.length}</b>{plan.coming ? 'coming' : 'to invite'}</dd>
          <dd class="of">{plan.coming ? "on Espoo's event page" : 'drafted from public sources'}</dd>
        </div>
        <div class="wide">
          <dt>Their profiles</dt>
          <dd><b>{confirmed}</b>of {employers.length} confirmed</dd>
          <dd class="bar"><Progress {employers} coming={plan.coming} legend={false} /></dd>
          <dd class="of">{employers.length - confirmed - unsent} sent and waiting, {unsent} not sent yet</dd>
        </div>
        <div>
          <dt>People invited</dt>
          <dd><b>{manage.sent ? some(manage.sent.n) : 0}</b>{manage.sent ? 'past attendees' : `of ${app.pool.people.toLocaleString('en')} in the pool`}</dd>
          <dd class="of">{manage.sent ? `sent ${when(manage.sent.at.slice(0, 10))}` : 'invitation not sent yet'}{manage.copies ? `, link copied ${String(manage.copies)} ${manage.copies === 1 ? 'time' : 'times'}` : ''}</dd>
        </div>
        <div>
          <dt>Applications</dt>
          <dd><b>{waiting}</b>of {total} waiting for you</dd>
          <dd class="of">{accepted} approved, {declined} declined</dd>
        </div>
      </dl>

      <p class="next">
        {#each next.slice(0, 2) as action, i (action.href + action.label)}
          <a class="btn" class:primary={i === 0} href={action.href}>{action.label}{#if i === 0}<Icon name="flat" size={18} />{/if}</a>
        {:else}
          <span class="clear">Nothing is waiting for you on this event.</span>
        {/each}
        <a class="manage" href="#/event/{plan.slug}">Manage event<Icon name="flat" size={16} /></a>
      </p>
      <div class="wall"><Wall briefs={employers.map((e) => e.brief)} /></div>
    </section>
  {:else}
    <section class="event none">
      <h2>No event is being prepared</h2>
      <p class="next"><a class="btn primary" href="#/events">See what is proposed<Icon name="flat" size={18} /></a></p>
    </section>
  {/if}

  <div class="blocks">
    <section>
      <h3><a href="#/events">Proposed events<Icon name="flat" size={16} /></a></h3>
      <ul class="rows">
        {#each ideas as idea (idea.slug)}
          <li><b>{idea.title}</b><span>{idea.employers.length} employers, {some(idea.fields[0]?.people.people ?? 0)} people</span></li>
        {:else}
          <li class="none">No field has both employers looking and people in the pool yet. Add companies to change that.</li>
        {/each}
      </ul>
    </section>

    <section>
      <h3><a href="#/pool">Talent pool<Icon name="flat" size={16} /></a></h3>
      {#if app.pool.people}
        <p class="big"><b>{app.pool.people.toLocaleString('en')}</b> people from {app.pool.events.length} past events <span class="sample">sample data</span></p>
        <ul class="bars">
          {#each fields as f (f.name)}
            <li><span>{f.name}</span><span class="meter"><span style:width="{(f.people / most) * 100}%"></span></span><b>{f.people}</b></li>
          {/each}
        </ul>
      {:else}
        <p class="none">Nobody is in the pool yet. It fills as people sign up for events.</p>
      {/if}
    </section>

    <section>
      <h3><a href="#/companies">Companies<Icon name="flat" size={16} /></a></h3>
      <ul class="rows news">
        {#each changes as change (change.id)}
          {#if change.brief}<li><span class="tile"><Logo brief={change.brief} small /></span><b>{nameOf(change.brief)}</b><span>{change.says}, {change.at}</span></li>{/if}
        {:else}
          {#each newest as { brief, told } (brief.id)}
            <li><span class="tile"><Logo {brief} small /></span><b>{nameOf(brief)}</b><span>{told?.line}{told ? `, ${when(told.date)}` : ''}</span></li>
          {:else}
            <li class="none">No company yet. Find or add one on the Companies page.</li>
          {/each}
        {/each}
      </ul>
    </section>
  </div>
</main>

<style>
  main {
    display: grid;
    gap: var(--s7);
    padding: 0 0 var(--s8);
  }
  /* the page is named by the navigation; here the event being prepared is the headline */
  h1 {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }

  /* the event being prepared, on a field of the city's colour: the one thing on this page that is large */
  .event {
    --ink: var(--city-ink);
    --ink-2: var(--city-dim);
    --line: var(--city-line);
    --brand: var(--city-ink);
    --brand-ink: var(--city);
    display: grid;
    gap: var(--s5);
    padding: var(--s6) var(--s7) var(--s6) var(--s6);
    background: var(--city-raise);
    color: var(--city-ink);
  }
  .event > * {
    max-width: 76rem;
  }
  .event :global(:focus-visible) {
    outline-color: var(--city-ink);
  }
  .when {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--s2) var(--s3);
    font-size: var(--t-lg);
    color: var(--city-dim);
  }
  .when b {
    padding: 0.1em 0.6em;
    border-radius: 99px;
    background: var(--city-ink);
    color: var(--city);
    font-size: var(--t-sm);
  }
  h2 {
    margin-top: calc(-1 * var(--s3));
    font: 800 var(--t-2xl) / 0.95 var(--display);
    letter-spacing: -0.035em;
  }
  h2 a {
    text-decoration: none;
  }
  /* four numbers, each with what it is out of */
  dl {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.6fr) minmax(0, 1.2fr) minmax(0, 1.2fr);
    gap: var(--s5) var(--s6);
    margin: var(--s2) 0 0;
    padding-top: var(--s5);
    border-top: 1px solid var(--city-line);
  }
  dt {
    font-size: var(--t-sm);
    font-weight: 600;
    color: var(--city-dim);
  }
  dd {
    line-height: 1.3;
  }
  dd b {
    margin-right: var(--s2);
    font: 800 var(--t-xl) / 1.1 var(--display);
    letter-spacing: -0.03em;
  }
  .of {
    font-size: var(--t-sm);
    color: var(--city-dim);
  }
  .bar {
    margin: var(--s2) 0;
  }
  .next {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--s3);
  }
  .next .btn:not(.primary) {
    border-color: var(--city-line);
    background: none;
    color: var(--city-ink);
    min-height: 2.75rem;
  }
  .manage {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    min-height: 2.75rem;
    margin-left: auto;
    font-weight: 600;
    text-decoration: none;
  }
  .manage:hover {
    text-decoration: underline;
  }
  .clear {
    color: var(--city-dim);
  }
  /* every employer of the event, small: the detail is one press away */
  .wall :global(ul) {
    grid-template-columns: repeat(auto-fill, minmax(2.5rem, 1fr));
    gap: var(--s1);
  }
  .event.none h2 {
    margin-top: 0;
  }

  /* three smaller blocks, each leading to one page */
  .blocks {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--s6) var(--s7);
    max-width: 82rem;
    padding: 0 var(--s7) 0 var(--s6);
  }
  h3 {
    font-size: var(--t-lg);
    letter-spacing: -0.01em;
  }
  h3 a {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    min-height: 2.75rem;
    text-decoration: none;
  }
  h3 a :global(svg) {
    color: var(--ink-2);
    transition: transform 0.2s var(--ease);
  }
  h3 a:hover :global(svg) {
    transform: translateX(4px);
    color: var(--ink);
  }
  .sample {
    margin-left: var(--s1);
    padding: 0.2em 0.6em;
    border-radius: 99px;
    background: var(--wash);
    font: 600 var(--t-xs) / 1.4 var(--text);
    color: var(--ink-2);
    white-space: nowrap;
  }
  .rows li {
    display: grid;
    gap: 0 var(--s3);
    align-content: center;
    min-height: 3.25rem;
    padding: var(--s2) 0;
    border-top: 1px solid var(--line);
    line-height: 1.3;
  }
  .rows span:not(.tile) {
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  .news li {
    grid-template-columns: 2rem minmax(0, 1fr);
  }
  .tile {
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
  .tile:has(:global(.dark)) {
    background: #14151a;
  }
  .none {
    display: block;
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  .big {
    padding-bottom: var(--s2);
    font-size: var(--t-sm);
    line-height: 1.5;
    color: var(--ink-2);
  }
  .big b {
    margin-right: var(--s1);
    font: 800 var(--t-xl) / 1 var(--display);
    letter-spacing: -0.03em;
    color: var(--ink);
  }
  .bars li {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 5rem 2.5rem;
    align-items: center;
    gap: var(--s3);
    min-height: 2.5rem;
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
  @media (max-width: 1100px) {
    dl {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .blocks {
      grid-template-columns: minmax(0, 1fr);
    }
  }
  @media (max-width: 820px) {
    main {
      gap: var(--s6);
    }
    .event {
      padding: var(--s5) var(--s4);
    }
    .blocks {
      padding: 0 var(--s4);
    }
    .manage {
      margin-left: 0;
    }
  }
</style>
