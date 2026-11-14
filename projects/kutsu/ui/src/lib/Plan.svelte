<script lang="ts">
  import Cite from './Cite.svelte'
  import { asking, daysTo, some, sourceOf, type Invitee, type Plan } from './events'
  import { when } from './format'
  import Icon from './Icon.svelte'
  import { applications, countCopy, manage } from './manage.svelte'
  import SendModal from './SendModal.svelte'
  import Tabs from './Tabs.svelte'
  import Logo from './Logo.svelte'
  import Progress from './Progress.svelte'
  import { app, copyText, joinLink, nameOf, reviewOf, saveReview } from './state.svelte'
  import type { Status } from './types'
  import Wall from './Wall.svelte'

  // One event, as the two lists Espoo has to build for it: its employers, each with the news that
  // makes now the moment, and the people in the pool who do the work those employers look for.
  // The people side is counts only. An event across many fields has no single count of people, so
  // it lists its fields and each opens in place.
  let { plan }: { plan: Plan } = $props()
  const FIRST = 6
  let all = $state(false)
  let open = $state('')
  let copied = $state('')
  let sending = $state(false)
  // the person's invitation is their own sign-up in this app, for this event
  const invitation = $derived(`#/me/${plan.slug}`)
  // the invitation is an open link; copying it is how it leaves this screen
  const regularLink = $derived(`${location.origin}${location.pathname}${invitation}`)
  // whom a send reaches before the organiser narrows it in the modal: everyone in the pool who came to an earlier event and
  // works in one of this event's fields (a person who came twice is counted twice; the pool keeps counts, not people)
  const reach = $derived(plan.fields.reduce((sum, f) => sum + Object.values(f.people.events).reduce((a, b) => a + b, 0), 0))
  async function copyRegular() {
    await copyText(regularLink)
    countCopy()
    copied = 'regular'
    setTimeout(() => (copied = ''), 1600)
  }

  // the forum's employers are coming already, so their link needs no event; any other invitation names its own
  const link = $derived(plan.coming ? '' : plan.slug)
  /** Where an employer stands for this event, in words: its profile is one for all events, an invitation and a sign-up are for this one. */
  const standing = (e: Invitee): { status: Status; says: string } | undefined => {
    const review = reviewOf(e.brief)
    if (plan.coming) return review.status === 'joined' ? { status: 'joined', says: 'Profile confirmed' } : review.status === 'invited' ? { status: 'invited', says: 'Profile sent' } : undefined
    if (review.status === 'joined' && review.signed?.includes(plan.slug)) return { status: 'joined', says: 'Signed up' }
    if (review.events?.includes(plan.slug)) return { status: 'invited', says: 'Invited' }
    return review.status === 'joined' ? { status: 'joined', says: 'Profile confirmed' } : undefined
  }
  /** Nothing left to send: signed up for this event, or, for an event whose employers are already coming, profile confirmed. */
  const settled = (e: Invitee) => {
    const at = standing(e)
    return !!at && (at.says === 'Signed up' || (plan.coming && at.says === 'Profile confirmed'))
  }
  /** What the person pastes into their own message: why now, and the link to a sign-up that is already filled in. */
  const message = (e: Invitee) =>
    plan.coming
      ? `Your profile for the ${plan.title} (${plan.when}) is filled in from what ${nameOf(e.brief)} has said in public. Checking it takes a minute: ${joinLink(e.brief.id, link)}`
      : `The City of Espoo is planning a ${plan.title.replace(/^[A-Z](?=[a-z])/, (c) => c.toLowerCase())} talent event. ${some(field?.people.people ?? 0)} people who came to our earlier events work in this field. Your sign-up is filled in from what ${nameOf(e.brief)} has said in public: ${joinLink(e.brief.id, link)}`
  const listed = $derived(all ? plan.employers : plan.employers.slice(0, FIRST))
  const rest = $derived(all ? [] : plan.employers.slice(FIRST))
  // the one field whose people are shown: the event's own, or the one opened from its list
  const field = $derived(plan.fields.length === 1 ? plan.fields[0] : plan.fields.find((f) => f.name === open))
  const people = $derived(field?.people)
  const levels = $derived(Object.entries(people?.levels ?? {}).filter(([, n]) => n))
  const came = $derived(app.pool.events.map((e) => ({ ...e, n: people?.events[e.id] ?? 0 })).filter((e) => e.n).sort((a, b) => b.n - a.n))
  const most = $derived(Math.max(1, ...(field ? field.rows.map((r) => r.have) : plan.fields.map((f) => f.people.people))))

  /** An invitation leaves this screen as text to paste: a person sends it. Copying it is what marks the employer as invited. */
  async function invite(e: Invitee) {
    const review = reviewOf(e.brief)
    const events = plan.coming ? review.events : [...new Set([...(review.events ?? []), plan.slug])]
    if (review.status === 'draft') await saveReview(e.brief.id, { ...review, status: 'invited', invited_at: new Date().toISOString(), events })
    else if (!plan.coming && !review.events?.includes(plan.slug)) await saveReview(e.brief.id, { ...review, events })
    if (!(await copyText(message(e)))) return
    copied = e.brief.id
    setTimeout(() => (copied = ''), 1600)
  }
</script>

<main>
  <a class="back" href="#/"><Icon name="back" size={16} />Events</a>
  <header>
    <h1>{plan.title}</h1>
    {#if plan.date}
      <p>
        {plan.when}{daysTo(plan.date) > 1 ? `, in ${String(daysTo(plan.date))} days` : ''}
        {#if plan.url}<a href={plan.url} target="_blank" rel="noopener">Espoo's event page<Icon name="out" size={14} /></a>{/if}
      </p>
    {/if}
  </header>
  <Tabs {plan} tab="invite" />

  <div class="sides">
    <section>
      <h2>{plan.coming ? 'Employers coming' : 'Employers to invite'} <span>{plan.employers.length}</span></h2>
      {#if plan.coming}<div class="progress"><Progress employers={plan.employers} coming /></div>{/if}
      <ul class="employers">
        {#each listed as e (e.brief.id)}
          {@const status = standing(e)}
          {@const source = sourceOf(e)}
          <li>
            <a class="tile" href="#/{encodeURIComponent(e.brief.id)}" aria-label={nameOf(e.brief)}><Logo brief={e.brief} small /></a>
            <div>
              <a class="name" href="#/{encodeURIComponent(e.brief.id)}">{nameOf(e.brief)}</a>
              <p class="roles" title={e.roles.map((r) => r.title).join(', ')}>
                {e.roles[0]?.title ?? 'No role drafted'}{#if e.roles.length > 1}<span>+{e.roles.length - 1}</span>{/if}
              </p>
              {#if e.news}<p class="why">{e.news.line}, {when(e.news.date)}{#if source}<Cite signal={source} n={1} />{/if}</p>{/if}
              <a class="see" href={joinLink(e.brief.id, link)} target="_blank" rel="noopener">Their sign-up<Icon name="out" size={14} /></a>
            </div>
            <div class="act">
              {#if status}<span class="state {status.status}">{status.says}</span>{/if}
              {#if !settled(e)}
                <button class="btn" onclick={() => invite(e)}>
                  <Icon name={copied === e.brief.id ? 'check' : 'copy'} size={16} />{copied === e.brief.id ? 'Copied, ready to paste' : 'Copy invitation'}
                </button>
              {/if}
            </div>
          </li>
        {/each}
      </ul>
      {#if rest.length}
        <div class="rest">
          <Wall briefs={rest.map((e) => e.brief)} />
          <button class="btn quiet" onclick={() => (all = true)}><Icon name="plus" size={16} />List all {plan.employers.length}</button>
        </div>
      {/if}
    </section>

    <section class="people">
      <h2>People to invite <span class="sample">sample data</span></h2>
      <div class="inv">
        <div class="kind">
          <div class="what"><b>Invitation</b><small>An open link to apply, drafted from what the person agrees we may read. Share the link, or send it to the people who came to Espoo's earlier events; you choose which events and fields first. Every application is reviewed separately.</small></div>
          <div class="go">
            <a class="btn" href={invitation} target="_blank" rel="noopener"><Icon name="out" size={16} />Preview form</a>
            <button class="btn" onclick={copyRegular}><Icon name={copied === 'regular' ? 'check' : 'copy'} size={16} />{copied === 'regular' ? 'Link copied' : 'Copy link'}</button>
            <button class="btn primary wide" onclick={() => (sending = true)}><Icon name="send" size={16} />{manage.sent ? 'Send again to past attendees…' : `Send to ${some(reach)} past attendees…`}</button>
          </div>
          <p class="sentnote quiet">{manage.sent ? `Sent to ${some(manage.sent.n)} people, ${when(manage.sent.at.slice(0, 10))}. ` : ''}{manage.copies ? `Link copied ${String(manage.copies)} ${manage.copies === 1 ? 'time' : 'times'}. ` : ''}{applications.list.length} applications so far, each reviewed separately. <a href="#/event/{plan.slug}/applications">Manage them<Icon name="flat" size={12} /></a></p>
        </div>
      </div>

      {#if field && people}
        {#if plan.fields.length > 1}
          <button class="up" onclick={() => (open = '')}><Icon name="back" size={16} />{field.name}</button>
        {/if}
        <p class="count"><b>{some(people.people)}</b> do this work{#if people.wanting}<span>+{some(people.wanting)} want to move into it</span>{/if}</p>

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

        {#if field.rows.length}
          <h3>Skills the roles ask for</h3>
          <ul class="rows">
            {#each field.rows as row (row.label)}
              <li>
                <span>{row.label}</span>
                <small>{asking(row.asked, row.confirmed)}</small>
                <span class="meter"><span style:width="{(row.have / most) * 100}%"></span></span>
                <b class:few={row.have < 5}>{row.have < 5 ? 'few' : row.have}</b>
              </li>
            {/each}
          </ul>
        {/if}

        {#if came.length}
          <h3>They came to</h3>
          <ul class="came">
            {#each came as event (event.id)}
              <li><b>{some(event.n)}</b><a href={event.url} target="_blank" rel="noopener">{event.name}</a>, {when(event.date.slice(0, 7))}</li>
            {/each}
          </ul>
        {/if}
      {:else}
        <ul class="rows fields">
          {#each plan.fields as f (f.name)}
            <li>
              <button onclick={() => (open = f.name)}>{f.name}<Icon name="flat" size={14} /></button>
              <small>{asking(f.employers.length, f.employers.filter((e) => reviewOf(e.brief).status === 'joined').length)}</small>
              <span class="meter"><span style:width="{(f.people.people / most) * 100}%"></span></span>
              <b>{f.people.people}</b>
            </li>
          {/each}
        </ul>
      {/if}

    </section>
  </div>
</main>
{#if sending}<SendModal {plan} onclose={() => (sending = false)} />{/if}

<style>
  main {
    --brand: var(--city);
    --brand-ink: var(--city-ink);
    display: grid;
    gap: var(--s6);
    max-width: 76rem;
    padding: var(--s6) var(--s7) var(--s8) var(--s6);
  }
  .back {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    justify-self: start;
    min-height: 2.75rem;
    font-size: var(--t-sm);
    font-weight: 600;
    color: var(--ink-2);
    text-decoration: none;
  }
  .back:hover {
    color: var(--ink);
  }
  h1 {
    font: 800 var(--t-2xl) / 0.95 var(--display);
    letter-spacing: -0.035em;
  }
  header p {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--s1) var(--s5);
    margin-top: var(--s3);
    font-size: var(--t-lg);
    color: var(--ink-2);
  }
  header a {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    min-height: 2.75rem;
    font-size: var(--t-sm);
    font-weight: 600;
    text-decoration: none;
  }
  header a:hover {
    color: var(--ink);
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

  .progress {
    margin-top: var(--s3);
  }
  .employers {
    margin-top: var(--s4);
  }
  .employers li {
    display: grid;
    grid-template-columns: 4rem minmax(0, 1fr) auto;
    gap: var(--s4);
    align-items: start;
    padding: var(--s4) 0;
    border-top: 1px solid var(--line);
  }
  .tile {
    display: block;
    width: 4rem;
    height: 4rem;
    padding: 8px;
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
  .roles span {
    margin-left: 0.35em;
    color: var(--ink-2);
  }
  .see {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    min-height: 2rem;
    font-size: var(--t-sm);
    color: var(--ink-2);
    text-decoration: none;
  }
  .see:hover {
    color: var(--ink);
  }
  .why {
    margin-top: var(--s1);
    font-size: var(--t-sm);
    line-height: 1.4;
    color: var(--ink-2);
  }
  .act {
    display: flex;
    flex-wrap: wrap;
    justify-content: end;
    align-items: center;
    gap: var(--s2) var(--s3);
  }
  .state {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    padding: 0 var(--s2);
    min-height: 2.25rem;
    font-size: var(--t-sm);
    font-weight: 600;
  }
  .state::before {
    content: '';
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    background: var(--wait);
  }
  .state.joined {
    color: var(--ok);
  }
  .state.joined::before {
    background: var(--ok);
  }
  .rest {
    display: grid;
    justify-items: start;
    gap: var(--s3);
    padding-top: var(--s4);
    border-top: 1px solid var(--line);
  }
  .rest > :global(ul) {
    width: 100%;
  }
  .rest .btn {
    margin-left: calc(-1 * var(--s2));
  }

  /* the people side is numbers, never rows */
  .people {
    position: sticky;
    top: var(--s5);
  }
  /* the two actions of the people side, one row, the same size, the send as the city's step */
  .go {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(7.5rem, 1fr));
    gap: var(--s2);
  }
  .go .btn,
  .go .btn.primary {
    min-width: 0;
    justify-content: center;
    min-height: 2.5rem;
    padding: 0 var(--s3);
    font-size: var(--t-sm);
    background-color: var(--ground);
  }
  .go .btn.primary {
    background-color: var(--brand);
  }
  .go .wide {
    grid-column: 1 / -1;
  }
  .sentnote {
    margin-top: var(--s2);
    font-size: var(--t-xs);
    line-height: 1.4;
    color: var(--ink-2);
  }
  .sentnote a {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    color: var(--ink);
  }
  /* the invitation block */
  .inv {
    display: grid;
    gap: var(--s3);
    margin: var(--s3) 0 var(--s4);
  }
  .kind {
    padding: var(--s3) var(--s4);
    border: 1px solid var(--line);
    border-radius: var(--r2);
    background: var(--ground);
  }
  .what b {
    display: block;
    font-size: var(--t-md);
  }
  .what small {
    display: block;
    margin-bottom: var(--s3);
    font-size: var(--t-xs);
    line-height: 1.4;
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
    white-space: nowrap;
  }
  .up {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    min-height: 2.75rem;
    margin: var(--s2) 0 0 calc(-1 * var(--s1));
    padding: 0 var(--s1);
    border: 0;
    background: none;
    font-weight: 700;
  }
  .count {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0 var(--s2);
    margin-top: var(--s3);
    font-size: var(--t-lg);
  }
  .up + .count {
    margin-top: 0;
  }
  .count b {
    font: 800 var(--t-xl) / 1 var(--display);
    letter-spacing: -0.03em;
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
  .rows.fields {
    margin-top: var(--s3);
  }
  .rows li {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0 var(--s3);
    align-items: center;
    padding: var(--s2) 0 var(--s3);
    border-top: 1px solid var(--line);
    line-height: 1.25;
  }
  .rows li > :first-child {
    font-weight: 600;
  }
  .rows button {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    width: 100%;
    min-height: 2.25rem;
    padding: 0;
    border: 0;
    background: none;
    text-align: left;
  }
  .rows button :global(svg) {
    flex: none;
    color: var(--ink-2);
    transition: transform 0.2s var(--ease);
  }
  .rows button:hover :global(svg) {
    transform: translateX(3px);
    color: var(--ink);
  }
  .rows.fields li {
    min-height: 2.75rem;
  }
  .rows small {
    grid-column: 1 / -1;
    grid-row: 2;
    font-size: var(--t-xs);
    color: var(--ink-2);
  }
  .meter {
    grid-row: 3;
    grid-column: 1 / -1;
    margin-top: var(--s2);
    height: 0.375rem;
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
    grid-row: 1;
    grid-column: 2;
    text-align: right;
    font-size: var(--t-sm);
  }
  .rows b.few {
    font-weight: 500;
    color: var(--ink-2);
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

  @media (max-width: 1100px) {
    .sides {
      grid-template-columns: 1fr;
      gap: var(--s6);
    }
    .people {
      position: static;
    }
  }
  @media (max-width: 820px) {
    main {
      padding: var(--s5) var(--s4) var(--s7);
    }
    .employers li {
      grid-template-columns: 3rem minmax(0, 1fr);
    }
    .tile {
      width: 3rem;
      height: 3rem;
      padding: 6px;
    }
    .act {
      grid-column: 2;
      justify-content: start;
    }
    .act .btn,
    .see {
      min-height: 2.75rem;
    }
  }
</style>
