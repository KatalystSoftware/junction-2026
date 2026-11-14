<script lang="ts">
  import Cite from './Cite.svelte'
  import { daysTo, some, type Invitee, type Plan } from './events'
  import { when } from './format'
  import Icon from './Icon.svelte'
  import Logo from './Logo.svelte'
  import { app, copyLink, joinLink, nameOf, reviewOf, saveReview } from './state.svelte'

  // One event, as the two lists Espoo has to build for it: the employers to invite, each with the
  // reason to invite it now, and the people in the pool who do the work those employers ask for.
  // The people side is counts only. Each side is what the other asks about before it commits.
  let { plan }: { plan: Plan } = $props()
  let copied = $state('')

  const people = $derived(plan.people)
  const joined = $derived(plan.employers.filter((e) => reviewOf(e.brief).status === 'joined').length)
  const levels = $derived(Object.entries(people.levels).filter(([, n]) => n))
  const events = $derived(app.pool.events.map((e) => ({ ...e, came: people.events[e.id] ?? 0 })).filter((e) => e.came).sort((a, b) => b.came - a.came))
  const most = $derived(Math.max(1, ...plan.rows.map((r) => r.have)))
  const names = $derived(plan.employers.slice(0, 3).map((e) => nameOf(e.brief)))
  const work = $derived(plan.kind === 'suggested' ? plan.title.toLowerCase() : 'the work these employers ask for')
  // what each side asks before it commits, answered from the other side
  const toEmployers = $derived(
    `${some(people.people)} people who came to Espoo's events work in ${work}` +
      (events[0] ? `; ${some(events[0].came)} of them came to ${events[0].name} in ${when(events[0].date.slice(0, 7))}.` : '.'),
  )
  const toPeople = $derived(
    `${String(plan.employers.length)} employers have said what they are looking for` + (names.length ? `, among them ${names.join(', ')}.` : '.'),
  )

  const signal = (e: Invitee) => e.brief.signals.find((s) => s.id === e.news?.signals[0])
  async function invite(e: Invitee) {
    const review = reviewOf(e.brief)
    if (review.status === 'draft') await saveReview(e.brief.id, { ...review, status: 'invited', invited_at: new Date().toISOString() })
    await copyLink(e.brief.id)
    copied = e.brief.id
    setTimeout(() => (copied = ''), 1600)
  }
</script>

<main>
  <a class="back" href="#/"><Icon name="back" size={16} />Events</a>
  <header>
    <h1>{plan.title}</h1>
    <p>
      {#if plan.kind === 'upcoming'}
        {when(plan.date)}{daysTo(plan.date) > 1 ? `, in ${String(daysTo(plan.date))} days` : ''}. {joined} of {plan.employers.length} employers have signed up.
      {:else}
        {plan.employers.length} employers have said they need these people. {some(people.people)} people in the pool do this work{people.wanting ? `, and ${some(people.wanting)} more want to move into it` : ''}.
      {/if}
    </p>
  </header>

  <div class="sides">
    <section>
      <h2>Employers to invite <span>{plan.employers.length}</span></h2>
      <ul class="employers">
        {#each plan.employers as e (e.brief.id)}
          {@const status = reviewOf(e.brief).status}
          {@const source = signal(e)}
          <li>
            <a class="tile" href="#/{encodeURIComponent(e.brief.id)}" aria-label={nameOf(e.brief)}><Logo brief={e.brief} small /></a>
            <div class="who">
              <a class="name" href="#/{encodeURIComponent(e.brief.id)}">{nameOf(e.brief)}</a>
              <p class="roles">{e.roles.map((r) => r.title).join(', ') || 'No role drafted yet'}</p>
              {#if e.news}
                <p class="why">{e.news.line}{#if source}<Cite signal={source} label={when(e.news.date)} />{/if}</p>
              {/if}
            </div>
            <div class="act">
              {#if status === 'joined'}
                <span class="state joined"><Icon name="check" size={14} />Signed up</span>
              {:else}
                <button class="btn" onclick={() => invite(e)}>
                  <Icon name={copied === e.brief.id ? 'check' : status === 'draft' ? 'send' : 'copy'} size={16} />{copied === e.brief.id ? 'Link copied' : status === 'draft' ? 'Invite' : 'Copy link'}
                </button>
              {/if}
              <a class="see" href={joinLink(e.brief.id)} target="_blank" rel="noopener">Their sign-up<Icon name="out" size={14} /></a>
            </div>
          </li>
        {/each}
      </ul>
    </section>

    <section class="people">
      <h2>People to invite <span class="sample">sample data</span></h2>
      <p class="count"><b>{some(people.people)}</b> {plan.kind === 'upcoming' ? 'do what these employers ask for' : 'do this work'}{#if people.wanting}<span>+{some(people.wanting)} want to move into it</span>{/if}</p>

      {#if levels.length}
        <div class="levels" aria-hidden="true">
          {#each levels as [level, n], i (level)}<span style:flex-grow={n} style:--step={i} title="{level}: {some(n)}"></span>{/each}
        </div>
        <p class="facts">
          {#each levels as [level, n] (level)}<span><b>{some(n)}</b> {level.toLowerCase()}</span>{/each}
        </p>
      {/if}

      <p class="facts">
        <span><b>{some(people.english)}</b> work in English</span>
        <span><b>{some(people.finnish)}</b> in Finnish</span>
        <span><b>{some(people.abroad)}</b> live abroad</span>
      </p>

      {#if plan.rows.length}
        <h3>{plan.kind === 'upcoming' ? 'By field' : 'What employers ask for'}</h3>
        <ul class="rows">
          {#each plan.rows as row (row.label)}
            <li>
              {#if row.href}<a href={row.href}>{row.label}</a>{:else}<span>{row.label}</span>{/if}
              <small>{row.asked} {row.asked === 1 ? 'employer asks' : 'employers ask'}</small>
              <span class="meter" title="{row.have} in the pool"><span style:width="{(row.have / most) * 100}%"></span></span>
              <b class:few={row.have < 5}>{row.have < 5 ? 'few' : row.have}</b>
            </li>
          {/each}
        </ul>
      {/if}

      {#if events.length}
        <h3>They came to</h3>
        <ul class="came">
          {#each events as event (event.id)}
            <li><b>{some(event.came)}</b><a href={event.url} target="_blank" rel="noopener">{event.name}</a>, {when(event.date.slice(0, 7))}</li>
          {/each}
        </ul>
      {/if}
    </section>
  </div>

  <section class="say">
    <h2>What each invitation can say</h2>
    <div>
      <p><b>To an employer asking who will be there</b>{toEmployers}</p>
      <p><b>To a person asking which employers come</b>{toPeople}</p>
    </div>
    <p class="note">
      Each employer's invitation is already filled in; press "Their sign-up" to see it. A person's invitation works the same way in
      <a href="https://esittely.duckymcduck2.workers.dev/#/cand" target="_blank" rel="noopener">Esittely</a>. {app.pool.note}
    </p>
  </section>
</main>

<style>
  main {
    --brand: var(--city);
    --brand-ink: var(--city-ink);
    display: grid;
    gap: var(--s6);
    max-width: 78rem;
    padding: var(--s6) var(--s7) var(--s8) var(--s6);
  }
  .back {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    justify-self: start;
    font-size: var(--t-sm);
    font-weight: 600;
    color: var(--ink-2);
    text-decoration: none;
  }
  .back:hover {
    color: var(--ink);
  }
  h1 {
    font-size: var(--t-2xl);
  }
  header p {
    max-width: 60ch;
    margin-top: var(--s3);
    font-size: var(--t-lg);
    line-height: 1.4;
    color: var(--ink-2);
  }
  h2 {
    font-size: var(--t-lg);
    letter-spacing: -0.01em;
  }
  h2 > span:not(.sample) {
    margin-left: var(--s1);
    font-weight: 500;
    color: var(--ink-2);
  }
  h3 {
    margin: var(--s5) 0 var(--s2);
    font: 600 var(--t-sm) / 1.3 var(--text);
    letter-spacing: 0;
    color: var(--ink-2);
  }
  .sides {
    display: grid;
    grid-template-columns: minmax(0, 1.25fr) minmax(19rem, 1fr);
    gap: var(--s7);
    align-items: start;
  }

  .employers {
    margin-top: var(--s3);
  }
  .employers li {
    display: grid;
    grid-template-columns: 3rem minmax(0, 1fr) auto;
    gap: var(--s4);
    align-items: start;
    padding: var(--s4) 0;
    border-top: 1px solid var(--line);
  }
  .tile {
    display: block;
    width: 3rem;
    height: 3rem;
    padding: 6px;
    border-radius: var(--r1);
    overflow: hidden;
    background: #fff;
    box-shadow: 0 0 0 1px var(--line);
  }
  .tile:has(:global(.dark)) {
    background: #14151a;
  }
  .name {
    font-weight: 700;
    font-size: var(--t-lg);
    letter-spacing: -0.01em;
    line-height: 1.2;
    text-decoration: none;
  }
  .name:hover {
    text-decoration: underline;
  }
  .roles {
    margin-top: 2px;
    line-height: 1.35;
  }
  .why {
    margin-top: var(--s1);
    font-size: var(--t-sm);
    line-height: 1.4;
    color: var(--ink-2);
  }
  .why :global(.cite) {
    margin-left: var(--s2);
    white-space: nowrap;
  }
  .act {
    display: grid;
    justify-items: end;
    gap: var(--s2);
  }
  .state {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    min-height: 2.5rem;
    font-size: var(--t-sm);
    font-weight: 600;
    color: var(--ok);
  }
  .see {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    font-size: var(--t-sm);
    color: var(--ink-2);
    text-decoration: none;
  }
  .see:hover {
    color: var(--ink);
  }

  /* the people side is numbers, never rows */
  .people {
    position: sticky;
    top: var(--s5);
    padding: var(--s5);
    border-radius: var(--r2);
    background: var(--wash);
  }
  .sample {
    margin-left: var(--s2);
    padding: 0.2em 0.6em;
    border-radius: 99px;
    background: var(--ground);
    font: 600 var(--t-xs) / 1.4 var(--text);
    letter-spacing: 0;
    color: var(--ink-2);
    vertical-align: middle;
  }
  .count {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0 var(--s2);
    margin-top: var(--s3);
    font-size: var(--t-lg);
  }
  .count b {
    font: 800 var(--t-2xl) / 1 var(--display);
    letter-spacing: -0.03em;
    color: var(--city);
  }
  .count span {
    flex-basis: 100%;
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  .levels {
    display: flex;
    gap: 2px;
    margin-top: var(--s4);
  }
  .levels span {
    flex-basis: 0;
    min-width: 4px;
    height: 0.625rem;
    border-radius: 3px;
    /* one hue, lighter to darker as the level rises */
    background: color-mix(in oklch, var(--city) calc(40% + var(--step) * 20%), var(--wash));
  }
  .levels + .facts {
    margin-top: var(--s2);
  }
  .facts {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s1) var(--s4);
    margin-top: var(--s4);
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  .facts b {
    color: var(--ink);
  }
  .rows li {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 5rem 2.25rem;
    gap: 0 var(--s3);
    align-items: center;
    padding: var(--s2) 0;
    border-top: 1px solid var(--line);
    line-height: 1.25;
  }
  .rows a {
    text-decoration: none;
  }
  .rows a:hover {
    text-decoration: underline;
  }
  .rows li > :first-child {
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .rows small {
    grid-column: 1;
    grid-row: 2;
    font-size: var(--t-xs);
    color: var(--ink-2);
  }
  .meter {
    grid-row: 1 / 3;
    grid-column: 2;
    height: 0.5rem;
    border-radius: 99px;
    background: var(--line);
  }
  .meter span {
    display: block;
    min-width: 2px;
    height: 100%;
    border-radius: 99px;
    background: var(--city);
  }
  .rows b {
    grid-row: 1 / 3;
    grid-column: 3;
    text-align: right;
    font-size: var(--t-sm);
  }
  .rows b.few {
    font-weight: 600;
    color: var(--stop);
  }
  .came {
    display: grid;
    gap: var(--s1);
    font-size: var(--t-sm);
  }
  .came a {
    text-decoration: none;
  }
  .came a:hover {
    text-decoration: underline;
  }
  .came b {
    display: inline-block;
    min-width: 2.25rem;
    margin-right: var(--s2);
  }

  .say {
    padding-top: var(--s5);
    border-top: 1px solid var(--line);
  }
  .say div {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--s6);
    margin-top: var(--s4);
  }
  .say div p {
    max-width: 46ch;
    font-size: var(--t-lg);
    line-height: 1.4;
  }
  .say div b {
    display: block;
    margin-bottom: var(--s1);
    font-size: var(--t-sm);
    font-weight: 600;
    color: var(--ink-2);
  }
  .note {
    max-width: 78ch;
    margin-top: var(--s5);
    font-size: var(--t-sm);
    color: var(--ink-2);
  }

  @media (max-width: 1100px) {
    .sides {
      grid-template-columns: 1fr;
      gap: var(--s6);
    }
    .people {
      position: static;
      order: -1;
    }
  }
  @media (max-width: 820px) {
    main {
      padding: var(--s5) var(--s4) var(--s7);
    }
    .employers li {
      grid-template-columns: 2.5rem minmax(0, 1fr);
    }
    .tile {
      width: 2.5rem;
      height: 2.5rem;
    }
    .act {
      grid-column: 2;
      grid-auto-flow: column;
      justify-content: start;
      align-items: center;
      gap: var(--s4);
    }
    .say div {
      grid-template-columns: 1fr;
      gap: var(--s4);
    }
  }
</style>
