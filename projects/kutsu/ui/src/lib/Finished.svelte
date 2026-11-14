<script lang="ts">
  import { host, terms, when } from './format'
  import Icon from './Icon.svelte'
  import Logo from './Logo.svelte'
  import { app, joinLink, saveReview } from './state.svelte'
  import type { Brief, Need, Review, Signal } from './types'

  // The company's finished page: who it is, who it is looking for, and what Espoo does for it,
  // which follows from what it picked. This is what it would screenshot or pass on.
  let { brief, review, about, news }: { brief: Brief; review: Review; about: (key: string) => string; news: Signal[] } = $props()
  const identity = $derived(brief.identity)
  const event = $derived(app.presets.find((p) => p.ids.includes(brief.id)) ?? app.presets[0])
  const roles = $derived(review.needs.filter((n) => n.ok))
  const told = $derived(news.filter((s) => review.facts?.[s.id] === true))
  const wants = $derived(review.wants ?? [])
  const count = (n: number, one: string) => `${n} ${one}${n === 1 ? '' : 's'}`

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
      { when: 'By 18 Nov', what: 'Your place is confirmed', detail: 'Meeting and booth places are limited. The organisers choose and tell you.' },
      wants.some((w) => w.includes('meetings')) && {
        when: '26–27 Nov',
        what: '1:1 meetings with candidates',
        detail: `Offered to candidates who fit your roles${abroad ? `, ${abroad} of them open to people abroad` : ''}.`,
      },
      wants.some((w) => w.includes('booth')) && { when: '26–27 Nov', what: 'A virtual booth', detail: 'Built from this page. Nothing more to prepare.' },
      wants.some((w) => w.includes('presentation')) && { when: '26 Nov', what: 'A company presentation', detail: 'You asked for a slot between 12:00 and 17:00. The organisers confirm it.' },
    ].filter((s) => !!s),
  )

  let copied = $state(false)
  async function share() {
    try {
      await navigator.clipboard.writeText(joinLink(brief.id))
    } catch {
      const field = Object.assign(document.createElement('textarea'), { value: joinLink(brief.id) })
      document.body.append(field)
      field.select()
      document.execCommand('copy')
      field.remove()
    }
    copied = true
    setTimeout(() => (copied = false), 1600)
  }
</script>

<section class="finished">
  <header>
    <h1>You're in, {about('Company')}.</h1>
    <p class="event">{event?.title}, {event?.note.split(',')[0]}</p>
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
          {#each told as s (s.id)}
            <li>{s.claim} <a href={s.source_url} target="_blank" rel="noopener">{[host(s.source_url), when(s.date)].filter(Boolean).join(', ')}</a></li>
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
            {#if n.can_do?.length}<ul class="can">{#each n.can_do as task}<li>{task}</li>{/each}</ul>{/if}
            {#if n.skills.length}<p class="knows">{#each n.skills as skill}<span>{skill}</span>{/each}</p>{/if}
            <p class="reach">{reach(n)}</p>
          </li>
        {/each}
      </ul>
    </div>

    <div class="does" style:--i={2}>
      <h3>What Espoo does for you</h3>
      <ol>
        {#each steps as step}
          <li><b>{step.when}</b><span><strong>{step.what}</strong>{step.detail}</span></li>
        {/each}
      </ol>
    </div>
  </article>
</section>

<style>
  .finished {
    max-width: 84rem;
    margin: 0 auto;
    padding: clamp(0.5rem, 3vh, 2rem) 0 var(--s7);
  }
  header {
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: end;
    gap: var(--s2) var(--s5);
    animation: rise 0.7s var(--ease) backwards;
  }
  header .event {
    grid-column: 1;
  }
  header .acts {
    grid-column: 2;
    grid-row: 1 / span 2;
    margin: 0;
  }
  @media (max-width: 52rem) {
    header {
      grid-template-columns: 1fr;
    }
    header .acts {
      grid-column: 1;
      grid-row: auto;
      margin-top: var(--s3);
    }
  }
  h1 {
    font-size: clamp(2.5rem, 1.4rem + 3.6vw, 4.5rem);
    font-weight: 800;
    letter-spacing: -0.035em;
    line-height: 0.95;
  }
  .event {
    margin-top: var(--s3);
    font-size: var(--t-lg);
    color: color-mix(in oklch, var(--brand-ink) 86%, var(--brand));
  }
  .acts {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s2);
    margin-top: var(--s4);
  }
  .acts button {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    min-height: 2.5rem;
    padding: 0 var(--s4);
    border: 1px solid color-mix(in srgb, var(--brand-ink) 45%, transparent);
    border-radius: 99px;
    background: none;
    color: var(--brand-ink);
    font-weight: 600;
    transition: background 0.15s, color 0.15s;
  }
  .acts button:first-child,
  .acts button:hover {
    border-color: var(--brand-ink);
    background: var(--brand-ink);
    color: var(--brand);
  }

  /* the page itself: one white sheet. who you are, who you are looking for, and in the company's
     colour what Espoo does for you: side by side when there is room, so it reads as one answer */
  article {
    display: grid;
    grid-template-columns: minmax(0, 4fr) minmax(0, 5fr) minmax(0, 3.2fr);
    margin-top: var(--s5);
    border-radius: 1.5rem;
    background: var(--ground);
    color: var(--ink);
    box-shadow: var(--lift);
    overflow: hidden;
    animation: rise 0.8s var(--ease) 0.15s backwards;
  }
  article :focus-visible {
    outline-color: var(--ink);
  }
  article > div {
    padding: clamp(1.25rem, 3vw, 2.5rem);
  }
  article > div > * {
    animation: rise 0.7s var(--ease) backwards;
    animation-delay: calc(var(--i) * 140ms + 0.35s);
  }
  .who,
  .looking {
    border-right: 1px solid var(--line);
  }
  .plate {
    height: clamp(5rem, 14vh, 8rem);
    padding: var(--s4) 12%;
    border-radius: var(--r2);
    box-shadow: inset 0 0 0 1px var(--line);
  }
  .plate.dark {
    background: #14151a;
    box-shadow: none;
  }
  .plate :global(.logo) {
    background: none;
  }
  h2 {
    margin-top: var(--s5);
    font-size: var(--t-2xl);
    font-weight: 800;
    letter-spacing: -0.035em;
    line-height: 0.98;
  }
  .pitch {
    margin-top: var(--s3);
    font-size: var(--t-lg);
    line-height: 1.35;
  }
  .facts {
    margin-top: var(--s3);
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  .told {
    display: grid;
    gap: var(--s3);
    margin-top: var(--s5);
    padding-top: var(--s5);
    border-top: 1px solid var(--line);
  }
  .told li {
    line-height: 1.4;
    text-wrap: pretty;
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
  h3 {
    font: 700 var(--t-sm) / 1.2 var(--text);
    letter-spacing: 0;
    color: var(--ink-2);
  }
  .looking > ul > li {
    padding: var(--s4) 0;
    border-bottom: 1px solid var(--line);
  }
  .looking > ul > li:last-child {
    padding-bottom: 0;
    border-bottom: 0;
  }
  h4 {
    margin: 0;
    font: 800 var(--t-xl) / 1.08 var(--display);
    letter-spacing: -0.03em;
  }
  .terms {
    margin-top: var(--s1);
    font-size: var(--t-sm);
    font-weight: 600;
    color: var(--ink-2);
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
  .knows {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s1);
    margin-top: var(--s3);
  }
  .knows span {
    padding: 0.1rem var(--s3);
    border: 1px solid var(--line);
    border-radius: 99px;
    font-size: var(--t-sm);
  }
  .reach {
    margin-top: var(--s3);
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  /* what happens next, in the company's colour: the promise at the foot of the page */
  .does {
    background: color-mix(in srgb, var(--brand) 92%, #000);
    color: var(--brand-ink);
  }
  .does h3 {
    color: color-mix(in oklch, var(--brand-ink) 84%, var(--brand));
  }
  ol {
    display: grid;
    margin-top: var(--s3);
  }
  ol li {
    display: grid;
    gap: 0.1rem;
    padding: var(--s3) 0;
    border-top: 1px solid color-mix(in srgb, var(--brand-ink) 28%, transparent);
    line-height: 1.35;
  }
  ol b {
    font-size: var(--t-sm);
    font-weight: 800;
  }
  ol strong {
    display: block;
    font-size: var(--t-lg);
    font-weight: 700;
    letter-spacing: -0.015em;
  }
  ol span {
    color: color-mix(in oklch, var(--brand-ink) 88%, var(--brand));
  }
  ol strong {
    color: var(--brand-ink);
  }
  @keyframes rise {
    from {
      opacity: 0;
      translate: 0 22px;
    }
  }
  /* less room: the promise becomes a band across the foot, its steps side by side */
  @media (max-width: 72rem) {
    article {
      grid-template-columns: minmax(0, 5fr) minmax(0, 7fr);
    }
    .does {
      grid-column: 1 / -1;
    }
    ol {
      grid-template-columns: repeat(auto-fit, minmax(min(100%, 17rem), 1fr));
      column-gap: var(--s6);
    }
  }
  @media (max-width: 52rem) {
    article {
      grid-template-columns: minmax(0, 1fr);
    }
    .who {
      border-right: 0;
      border-bottom: 1px solid var(--line);
    }
  }
</style>
