<script lang="ts">
  import type { Occasion } from './events'
  import Icon from './Icon.svelte'
  import Logo from './Logo.svelte'
  import Mark from './Mark.svelte'
  import { keep, kept, linksOf, me, startOver, type Match } from './person.svelte'
  import SiteIcon from './SiteIcon.svelte'
  import { nameOf } from './state.svelte'

  // The person's finished page, in the shape of the company's: who you are, what you are looking for,
  // and what happens next. It claims nothing that has not happened: in this demo the profile is sent
  // to nobody, so it says the profile is ready, not that the person is in. It promises only what the
  // event's own page says, and marks what Kutsu would add as a proposal.
  let { event, offered, url, seed }: { event: Occasion; offered: Match[]; url: string; seed: string } = $props()
  const m = $derived(me.is)
  const first = $derived(m.name.split(' ')[0] ?? '')
  const can = $derived(kept(m, m.can))
  const skills = $derived(kept(m, m.skills))
  const roles = $derived(kept(m, m.roles))
  const links = $derived(linksOf(m))
  const terms = $derived([m.level, m.place, m.finnish ? 'Works in Finnish too' : '', m.abroad ? 'Lives outside Finland now' : ''].filter(Boolean))
  const meet = $derived(offered.filter((x) => m.meet.includes(x.employer.brief.id)))
  const lines = $derived(can.length + skills.length + roles.length)
  const read = $derived(!m.typed && !m.sample)

  // what happens next: the dates are the event's own; what Kutsu would add is said to be a proposal
  const steps = $derived([
    {
      when: 'Now',
      what: 'Your profile is ready',
      detail: `${String(lines)} lines you kept. ${read ? 'What you gave was read once and not saved. ' : ''}This is a demo: your profile is in this browser tab only, and has not gone to Espoo or to any employer.`,
    },
    ...(event.dated
      ? [
          { when: 'By 18 Nov', what: 'Apply for a Networking Pass', detail: "That is the real sign-up, on Espoo's event page. Places in 1:1 meetings are limited and the organisers choose." },
          { when: '26–27 Nov', what: 'The event, online and free', detail: 'Company presentations on 26 Nov from 12:00 to 17:00, 1:1 meetings on both days.' },
        ]
      : [{ when: 'Next', what: 'The date is set', detail: 'The event is being planned. You choose whether to come once there is a date.' }]),
    {
      when: 'Proposed',
      what: 'An organiser introduces you',
      detail: 'Not yet promised by Espoo. The employers you ticked would see the lines you kept, without your name or links, until a person at Espoo introduces you. Nothing scores or ranks you.',
    },
  ])
  const change = () => {
    m.done = ''
    keep()
  }
  // forgetting cannot be undone, so it is asked twice
  let sure = $state(false)
  const forget = () => {
    if (sure) startOver()
    else sure = true
  }
  const hide = (href: string) => {
    m.hidden = [...m.hidden, href]
    keep()
  }
</script>

<section class="finished">
  <header>
    <h1>Your profile is ready{first ? `, ${first}` : ''}.</h1>
    <p class="event">{event.name}, {event.when}. This is a demo: nothing has been sent to Espoo or to any employer.</p>
    <p class="acts">
      {#if event.dated && url}<a href={url} target="_blank" rel="noopener">Apply for a Networking Pass<Icon name="out" size={16} /></a>{/if}
      <button onclick={change}><Icon name="undo" size={16} />Change my answers</button>
      <button onclick={forget} onblur={() => (sure = false)}><Icon name="x" size={16} />{sure ? 'Press again to forget everything' : 'Forget me'}</button>
    </p>
  </header>

  <article>
    <div class="who" style:--i={0}>
      <div class="plate mine"><Mark {seed} /></div>
      <h2>{m.name || 'You'}</h2>
      <p class="pitch">{m.headline}</p>
      <p class="facts">{[m.field, ...terms].filter(Boolean).join(' · ')}</p>
      {#if links.length}
        <ul class="links">
          {#each links as site (site.href)}
            <li>
              <a href={site.href} target="_blank" rel="noopener" title={site.name}><SiteIcon id={site.id} size={16} />{site.label}</a>
              <button aria-label="Take {site.label} off my profile" onclick={() => { hide(site.href) }}><Icon name="x" size={12} /></button>
            </li>
          {/each}
        </ul>
        <p class="seen">Your name and links are for the organiser. An employer would see them only once an organiser introduces you.</p>
      {/if}
      {#if can.length}
        <ul class="told">
          {#each can as f (f.id)}<li title={f.from ? `“${f.from}”` : undefined}><b>{f.text}</b></li>{/each}
        </ul>
      {/if}
      {#if skills.length}<p class="knows">{#each skills as f (f.id)}<span>{f.text}</span>{/each}</p>{/if}
      {#if roles.length}
        <ul class="worked">
          {#each roles as f (f.id)}<li>{f.text}{#if f.when}<small>{f.when}</small>{/if}</li>{/each}
        </ul>
      {/if}
    </div>

    <div class="looking" style:--i={1}>
      <h3>Looking for</h3>
      <ul>
        <li>
          <h4>{m.wants.join(', ') || 'Not said'}</h4>
          {#if m.looking}<p class="terms">“{m.looking}”</p>{/if}
          {#if terms.length}<p class="reach">{terms.join(' · ')}</p>{/if}
        </li>
      </ul>
      <h3 class="next">Would like to meet</h3>
      <ul class="meet">
        {#each meet as match (match.employer.brief.id)}
          <li>
            <h4><span class="tile"><Logo brief={match.employer.brief} small /></span>{nameOf(match.employer.brief)}</h4>
            <p class="terms">{match.role}</p>
            {#if match.reasons.length}<p class="reach">{match.reasons.join(' · ')}</p>{/if}
          </li>
        {:else}
          <li><p class="reach">Nobody ticked. Every employer at the event is still open to you.</p></li>
        {/each}
      </ul>
    </div>

    <div class="does" style:--i={2}>
      <h3>What happens next</h3>
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

  .acts a {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    min-height: 2.75rem;
    padding: 0 var(--s5);
    border-radius: 99px;
    background: var(--brand-ink);
    color: var(--brand);
    font-weight: 700;
    text-decoration: none;
    white-space: nowrap;
  }
  .plate.mine {
    width: 6rem;
    height: 6rem;
    padding: 0;
    background: none;
    border-radius: 22%;
    box-shadow: 0 0 0 1px var(--line);
  }
  .links {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s1) var(--s3);
    margin-top: var(--s3);
    font-size: var(--t-sm);
  }
  .links li {
    display: inline-flex;
    align-items: center;
  }
  .links a {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    min-height: 2.25rem;
    font-weight: 600;
    text-decoration: none;
  }
  .links a:hover {
    text-decoration: underline;
  }
  .links button {
    display: grid;
    place-items: center;
    width: 2rem;
    height: 2.25rem;
    border: 0;
    background: none;
    color: var(--ink-2);
  }
  .links button:hover {
    color: var(--ink);
  }
  .seen {
    font-size: var(--t-xs);
    color: var(--ink-2);
  }
  .knows {
    margin-top: var(--s4);
  }
  .worked {
    display: grid;
    gap: var(--s1);
    margin-top: var(--s4);
    font-size: var(--t-sm);
  }
  .worked small {
    margin-left: var(--s2);
    color: var(--ink-2);
  }
  h3.next {
    margin-top: var(--s6);
  }
  /* an employer the person would like to meet is quieter than what the person is looking for */
  .meet h4 {
    display: flex;
    align-items: center;
    gap: var(--s2);
    font-size: var(--t-lg);
    letter-spacing: -0.01em;
  }
  .tile {
    flex: none;
    width: 1.75rem;
    height: 1.75rem;
    padding: 3px;
    border-radius: 4px;
    overflow: hidden;
    background: #fff;
    box-shadow: 0 0 0 1px var(--line);
    font-size: 0.55rem;
  }
  .tile:has(:global(.dark)) {
    background: #14151a;
  }
</style>
