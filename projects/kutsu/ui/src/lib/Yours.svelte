<script lang="ts">
  import type { Occasion } from './events'
  import Icon from './Icon.svelte'
  import Logo from './Logo.svelte'
  import Mark from './Mark.svelte'
  import { keep, kept, me, startOver, type Match } from './person.svelte'
  import { nameOf } from './state.svelte'

  // The person's finished page, in the shape of the company's: who you are, what you are looking for,
  // and what happens next. It promises only what the event's own page says, and says plainly that in
  // this demo the profile has gone nowhere.
  let { event, found, meet, seed }: { event: Occasion; found: Match[]; meet: string[]; seed: string } = $props()
  const m = $derived(me.is)
  const first = $derived(m.name.split(' ')[0] ?? '')
  const can = $derived(kept(m, m.can))
  const skills = $derived(kept(m, m.skills))
  const terms = $derived([m.level, m.finnish ? 'Finnish and English' : 'English', m.place, m.abroad ? 'Living abroad now' : ''].filter(Boolean))
  const picked = $derived(found.filter((x) => meet.includes(x.employer.brief.id)))
  const lines = $derived(can.length + skills.length + kept(m, m.roles).length)

  // what happens next: the dates are the event's own; what Kutsu would add is said to be a proposal
  const steps = $derived([
    { when: 'Now', what: 'Your profile is ready', detail: `${String(lines)} lines, each checked by you. This is a demo: it stays in this browser tab and has been sent to nobody.` },
    ...(event.dated
      ? [
          { when: 'By 18 Nov', what: 'Apply for a Networking Pass', detail: "On Espoo's event page. Places in 1:1 meetings are limited and the organisers choose." },
          { when: '26–27 Nov', what: 'The event, online and free', detail: 'Company presentations on 26 Nov from 12:00 to 17:00, 1:1 meetings on both days.' },
        ]
      : [{ when: 'Next', what: 'You hear the date first', detail: 'The event is being planned. You choose whether to come once the date is set.' }]),
    { when: 'Proposed', what: 'The employers you picked see your profile first', detail: 'Only what you checked. A person at Espoo makes the introductions; nothing scores or ranks you.' },
  ])
  const change = () => {
    m.done = ''
    keep()
  }
</script>

<section class="finished">
  <header>
    <h1>You're in{first ? `, ${first}` : ''}.</h1>
    <p class="event">{event.name}, {event.when}</p>
    <p class="acts">
      <button onclick={change}><Icon name="undo" size={16} />Change my answers</button>
      <button onclick={() => { startOver() }}><Icon name="x" size={16} />Forget me and start over</button>
    </p>
  </header>

  <article>
    <div class="who" style:--i={0}>
      <div class="plate mine"><Mark {seed} /></div>
      <h2>{m.name || 'You'}</h2>
      <p class="pitch">{m.headline}</p>
      <p class="facts">{[m.field, ...terms].filter(Boolean).join(' · ')}</p>
      {#if can.length}
        <ul class="told">
          {#each can as f (f.id)}<li><b>{f.text}</b>“{f.from}”</li>{/each}
        </ul>
      {/if}
    </div>

    <div class="looking" style:--i={1}>
      <h3>Looking for</h3>
      <ul>
        <li>
          <h4>{m.wants.join(', ')}</h4>
          {#if m.looking}<p class="terms">“{m.looking}”</p>{/if}
          {#if skills.length}<p class="knows">{#each skills as f (f.id)}<span>{f.text}</span>{/each}</p>{/if}
        </li>
        {#each picked as match (match.employer.brief.id)}
          <li>
            <h4><span class="tile"><Logo brief={match.employer.brief} small /></span>{nameOf(match.employer.brief)}</h4>
            <p class="terms">{match.role}</p>
            {#if match.reasons.length}<p class="reach">{match.reasons.join(' · ')}</p>{/if}
          </li>
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

  .plate.mine {
    width: 6rem;
    height: 6rem;
    padding: 0;
    background: none;
    box-shadow: none;
  }
  h4 {
    display: flex;
    align-items: center;
    gap: var(--s2);
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
