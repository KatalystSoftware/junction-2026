<script lang="ts">
  import { host, terms, when } from './format'
  import Icon from './Icon.svelte'
  import Logo from './Logo.svelte'
  import type { Occasion } from './events'
  import { copyLink, saveReview } from './state.svelte'
  import type { Brief, Need, Review, Told } from './types'

  // The company's finished page: who it is, who it is looking for, and what Espoo does for it,
  // which follows from what it picked. This is what it would screenshot or pass on.
  let { brief, review, about, told, event }: { brief: Brief; review: Review; about: (key: string) => string; told: Told[]; event: Occasion } = $props()
  const identity = $derived(brief.identity)
  const roles = $derived(review.needs.filter((n) => n.ok))
  const source = (t: Told) => brief.signals.find((s) => t.signals.includes(s.id))
  const wants = $derived(review.wants ?? [])
  const count = (n: number, one: string) => `${String(n)} ${one}${n === 1 ? '' : 's'}`

  /** Who a role is shown to, from the language and the hiring-from-abroad answer. */
  const reach = (n: Need) => {
    const speaks = n.language === 'Finnish needed' ? ' who speak Finnish' : n.language ? ' who work in English' : ''
    const where = n.abroad === true ? ', in Finland and abroad' : n.abroad === false ? ', already in Finland' : ''
    return `Shown to candidates${speaks}${where}`
  }
  // what Espoo does next, by what the company asked for; the dates are the event's own
  const abroad = $derived(roles.filter((n) => n.abroad === true).length)
  const steps = $derived(
    [
      { when: 'Today', what: "Your page goes to Espoo's event team", detail: `${count(roles.length, 'role')} and ${count(told.length, 'thing')} about you, as you left them.` },
      event.dated
        ? { when: 'By 18 Nov', what: 'Your place is confirmed', detail: 'Meeting and booth places are limited. The organisers choose and tell you.' }
        : { when: 'Next', what: 'You hear the date first', detail: 'The event is being planned. You choose whether to come once the date is set.' },
      wants.some((w) => w.includes('meetings')) && {
        when: event.dated ? '26–27 Nov' : 'At the event',
        what: '1:1 meetings with candidates',
        detail: `Offered to candidates who fit your roles${abroad ? `, ${abroad} of them open to people abroad` : ''}.`,
      },
      wants.some((w) => w.includes('booth')) && { when: event.dated ? '26–27 Nov' : 'At the event', what: 'A virtual booth', detail: 'Built from this page. Nothing more to prepare.' },
      wants.some((w) => w.includes('presentation')) && {
        when: event.dated ? '26 Nov' : 'At the event',
        what: 'A company presentation',
        detail: event.dated ? 'You asked for a slot between 12:00 and 17:00. The organisers confirm it.' : 'You asked for a slot. The organisers confirm it.',
      },
    ].filter((s) => !!s),
  )

  let copied = $state(false)
  async function share() {
    if (!(await copyLink(brief.id, event.slug))) return
    copied = true
    setTimeout(() => (copied = false), 1600)
  }
</script>

<section class="finished">
  <header>
    <h1>You're in, {about('Company')}.</h1>
    <p class="event">{event.name}, {event.when}</p>
    <p class="acts">
      <button onclick={share}><Icon name={copied ? 'check' : 'copy'} size={16} />{copied ? 'Link copied' : 'Copy the link to this page'}</button>
      <button onclick={() => saveReview(brief.id, { ...review, status: 'invited' })}><Icon name="undo" size={16} />Change my answers</button>
    </p>
  </header>

  <article>
    <div class="who" style:--i={0}>
      <div class="plate" class:dark={identity?.logo_on === 'dark'}><Logo {brief} /></div>
      <h2>{about('Company')}</h2>
      <p class="pitch">{about('What you do')}</p>
      <p class="facts">{[about('Field'), about('People') && `${about('People')} people`, about('Based in'), about('Website')].filter(Boolean).join(' · ')}</p>
      {#if told.length}
        <ul class="told">
          {#each told as t (t.id)}
            <li><b>{t.line}</b>{t.detail} {#if source(t)}<a href={source(t)?.source_url} target="_blank" rel="noopener">{[host(source(t)?.source_url ?? null), when(t.date)].filter(Boolean).join(', ')}</a>{/if}</li>
          {/each}
        </ul>
      {/if}
    </div>

    <div class="looking" style:--i={1}>
      <h3>Looking for</h3>
      <ul>
        {#each roles as n (n.id)}
          <li>
            <h4>{n.title}</h4>
            <p class="terms">{terms(n).join(' · ')}</p>
            {#if n.can_do.length}<ul class="can">{#each n.can_do as task, j (j)}<li>{task}</li>{/each}</ul>{/if}
            {#if n.skills.length}<p class="knows">{#each n.skills as skill, j (j)}<span>{skill}</span>{/each}</p>{/if}
            <p class="reach">{reach(n)}</p>
          </li>
        {/each}
      </ul>
    </div>

    <div class="does" style:--i={2}>
      <h3>What Espoo does for you</h3>
      <ol>
        {#each steps as step (step.what)}
          <li><b>{step.when}</b><span><strong>{step.what}</strong>{step.detail}</span></li>
        {/each}
      </ol>
    </div>
  </article>
</section>

<style>
  @import './finished.css';

  /* only a company's page has these: a logo that needs a dark plate, a link to each statement's source, a role's tasks */
  .plate.dark {
    background: #14151a;
    box-shadow: none;
  }
  .told a {
    font-size: var(--t-sm);
    color: var(--ink-2);
    text-decoration: none;
    white-space: nowrap;
  }
  .told a:hover {
    color: var(--ink);
  }
  .can {
    display: grid;
    gap: 0.15rem;
    margin-top: var(--s3);
  }
  .can li {
    display: flex;
    gap: var(--s2);
    align-items: baseline;
  }
  .can li::before {
    content: '';
    flex: none;
    width: 0.375rem;
    height: 0.375rem;
    translate: 0 -0.15rem;
    border-radius: 50%;
    background: var(--brand);
  }
</style>
