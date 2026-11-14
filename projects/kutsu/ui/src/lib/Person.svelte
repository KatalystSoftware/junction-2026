<script lang="ts">
  import { flip } from 'svelte/animate'
  import { cubicOut } from 'svelte/easing'
  import { crossfade, fade } from 'svelte/transition'
  import { confetti } from './confetti'
  import { text } from './editable'
  import { occasionOf, plans } from './events'
  import Icon from './Icon.svelte'
  import Logo from './Logo.svelte'
  import Mark from './Mark.svelte'
  import { markOf } from './mark'
  import { keep, kept, matches, me, readAll, seedOf, SOURCE_NAME, startOver, type Fact, type Source } from './person.svelte'
  import { nameOf, route } from './state.svelte'
  import Yours from './Yours.svelte'

  // A person's sign-up, built from the same frame as the company's (flow.css): one card at a time in the
  // centre, one decision per card, and what is accepted travels to the side, so the profile assembles in
  // view. First what we may read, which the person decides; then who they are, what they know, what they
  // are looking for and whom they would like to meet. Skill is read from what they hand over, each line
  // with the words behind it. What they want and what suits them is asked, never read.
  const m = $derived(me.is)
  const plan = $derived(plans().find((p) => p.slug === route().event) ?? plans()[0])
  const event = $derived(occasionOf(plan))
  const mark = $derived(markOf(seedOf(m)))
  const first = $derived(m.name.split(' ')[0] ?? '')

  // the first card: one tick per source, and nothing is read before the person says so
  const SOURCES: { key: Source; label: string; hint: string }[] = [
    { key: 'linkedin', label: 'LinkedIn profile', hint: 'linkedin.com/in/your-name' },
    { key: 'portfolio', label: 'A page of yours', hint: 'A portfolio, a personal site, a GitHub profile' },
    { key: 'cv', label: 'Your CV', hint: 'Paste the text of your CV' },
  ]
  const chosen = $derived(SOURCES.map((s) => s.key).filter((k) => m.given[k].trim()))
  let reading = $state(false)
  const nothing = $derived(!reading && Object.keys(m.read).length > 0 && !m.can.length && !m.skills.length && !m.roles.length)
  async function readNow() {
    if (!chosen.length || reading) return
    reading = true
    await readAll(chosen)
    reading = false
  }

  // everything to decide, in order; the first undecided one is in the centre unless a line was opened
  const KEYS = ['read', 'you', 'know', 'want', 'meet'] as const
  type Key = (typeof KEYS)[number]
  const has = $derived(m.can.length + m.skills.length + m.roles.length > 0)
  const decided = (k: Key) => (k === 'read' ? has : k === 'you' ? m.you_ok : k === 'know' ? m.know_ok : k === 'want' ? m.wants.length > 0 && wanted : !!m.done)
  let wanted = $state(false)
  let opened = $state<Key | null>(null)
  let started = $state(me.is.sample || Object.keys(me.is.read).length > 0)
  const current = $derived<Key>(opened ?? KEYS.find((k) => !decided(k)) ?? 'meet')

  // who they are: three things they can do by default, the rest one press away
  const SHOWN = 3
  let more = $state(false)
  let detail = $state<string | null>(null)
  let editing = $state(false)
  const typed = (e: FocusEvent) => (e.currentTarget as HTMLElement).innerText.replace(/\s+/g, ' ').trim()
  const enter = (e: KeyboardEvent) => {
    if (e.key !== 'Enter') return
    e.preventDefault()
    ;(e.currentTarget as HTMLElement).blur()
  }
  const on = (f: Fact) => !m.struck.includes(f.id)
  /** The last line taken out, so one wrong press can be taken back. */
  let undo = $state<null | { said: string; id: string }>(null)
  function toggle(f: Fact) {
    if (on(f)) {
      m.struck = [...m.struck, f.id]
      undo = { said: `Took out “${f.text}”.`, id: f.id }
      detail = null
    } else {
      m.struck = m.struck.filter((id) => id !== f.id)
      undo = null
      detail = f.id
    }
    keep()
  }
  const takeBack = () => {
    if (!undo) return
    const id = undo.id
    m.struck = m.struck.filter((x) => x !== id)
    undo = null
    keep()
  }

  // what they are looking for and what suits them: asked, never read
  const fields = $derived([...new Set([m.field, ...(plan?.fields.map((f) => f.name) ?? [])].filter(Boolean))].slice(0, 8))
  const PLACES = ['On site', 'Hybrid', 'Remote']
  const want = (field: string) => {
    m.wants = m.wants.includes(field) ? m.wants.filter((f) => f !== field) : [...m.wants, field]
    keep()
  }
  // whom they might want to meet: this event's employers, each with why, the closest first and three ticked
  const found = $derived(matches(m, plan?.employers ?? []).slice(0, 6))
  const meet = $derived(m.meet.length || m.done ? m.meet : found.slice(0, 3).map((x) => x.employer.brief.id))
  const pick = (id: string) => {
    m.meet = meet.includes(id) ? meet.filter((x) => x !== id) : [...meet, id]
    keep()
  }

  function accept() {
    const k = current
    ;[opened, undo, editing] = [null, null, false]
    if (k === 'read') void readNow()
    else if (k === 'you') m.you_ok = true
    else if (k === 'know') m.know_ok = true
    else if (k === 'want') wanted = true
    else if (!m.done) {
      m.meet = meet
      m.done = new Date().toISOString()
      confetti([...mark.colours, '#ffffff'])
      scrollTo({ top: 0 })
    }
    keep()
  }
  const back = () => {
    const at = KEYS.indexOf(current)
    opened = KEYS[at - 1] ?? opened
  }
  function keys(e: KeyboardEvent) {
    const el = e.target as HTMLElement
    const typing = el.isContentEditable || ['INPUT', 'TEXTAREA'].includes(el.tagName)
    // Z, or Ctrl/Cmd+Z, takes back the last line taken out; inside a field, z is a letter and Ctrl+Z is the field's own undo
    if (e.key.toLowerCase() === 'z' && !e.altKey && !typing && undo) {
      e.preventDefault()
      takeBack()
      return
    }
    // Enter in a one-line field of the first card reads the sources; anywhere else a field keeps its keys
    if (typing && !(e.key === 'Enter' && el.tagName === 'INPUT' && current === 'read')) return
    if (e.metaKey || e.ctrlKey || e.altKey) return
    const choice = el.tagName === 'BUTTON' && 'choice' in el.dataset
    if (['BUTTON', 'A'].includes(el.tagName) && !(choice && e.key === 'Enter')) return
    if (e.key === 'Enter' || (e.key === ' ' && !typing)) {
      e.preventDefault()
      if (started) accept()
      else started = true
    } else if (started && e.key === 'ArrowLeft') back()
  }

  // what is already settled, at the sides; the one in the centre is not shown there
  const settled = $derived({
    you: m.you_ok && current !== 'you',
    can: m.you_ok && current !== 'you' ? kept(m, m.can) : [],
    know: m.know_ok && current !== 'know',
    want: wanted && current !== 'want',
  })
  const terms = $derived([m.level, m.finnish ? 'Finnish and English' : 'English', m.place, m.abroad ? 'Living abroad now' : ''].filter(Boolean))
  const calm = matchMedia('(prefers-reduced-motion: reduce)').matches
  const [send, receive] = crossfade({ duration: calm ? 0 : 560, easing: cubicOut, fallback: (node) => fade(node, { duration: calm ? 0 : 220 }) })
  const answer = $derived(
    current === 'read' ? (reading ? 'Reading' : 'Read these') : current === 'you' ? "That's me" : current === 'know' ? "That's right" : current === 'want' ? 'That is what I want' : 'Sign me up',
  )
  const ready = $derived(current === 'read' ? chosen.length > 0 && !reading : current === 'want' ? m.wants.length > 0 : true)
</script>

<svelte:window onkeydown={keys} />

<div class="join" class:cover={!started} style:--brand={has ? mark.colours[0] : 'var(--city)'} style:--brand-ink={has ? '#fff' : 'var(--city-ink)'}>
  <p class="host">City of Espoo <span>{event.name}, {event.when}</span></p>

  {#if !started}
    <section class="invite">
      <div class="plate mine"><Mark seed={event.slug || 'kutsu'} label="" /></div>
      <h1>{#each "You're invited.".split(' ') as word, i (i)}<span style:--i={i}>{word}&nbsp;</span>{/each}</h1>
      <p class="filled" style:--i={3}>{event.name}, {event.when}. {event.facts} Your sign-up fills itself in from what you choose to show us.</p>
      <button class="yes big" style:--i={4} onclick={() => (started = true)}>Start <kbd>Enter</kbd></button>
    </section>
  {:else if m.done}
    <Yours {event} {found} {meet} seed={seedOf(m)} />
  {:else}
    <div class="bench">
      <aside class="left" aria-label="About you">
        {#if settled.you}
          <h3>About you</h3>
          <button class="line you" onclick={() => (opened = 'you')} in:receive={{ key: 'you' }} out:send={{ key: 'you' }}>
            <span class="tile mine"><Mark seed={seedOf(m)} /></span>
            <b>{m.name || 'You'}</b>
            <span>{m.headline}</span>
          </button>
          {#each settled.can as f (f.id)}
            <button class="line" onclick={() => { opened = 'you'; detail = f.id }} in:fade={{ duration: 300, delay: 250 }} animate:flip={{ duration: 300 }}>
              <span class="fact">{f.text}</span>
              <span class="more">“{f.from}”</span>
            </button>
          {/each}
        {/if}
        {#if settled.know}
          <button class="line" onclick={() => (opened = 'know')} in:receive={{ key: 'know' }} out:send={{ key: 'know' }}>
            <b>You know</b>
            <span>{kept(m, m.skills).map((s) => s.text).join(' · ') || 'Nothing listed'}</span>
            <span class="more">{#each kept(m, m.roles) as r, k (r.id)}{#if k}<br />{/if}{r.text}{/each}</span>
          </button>
        {/if}
      </aside>

      <div class="centre">
        <!-- one keyed item, so a card that is leaving keeps its own content and key while it travels to the side -->
        {#each [current] as item (item)}
          <article class="card" in:receive={{ key: item }} out:send={{ key: item }}>
            {#if item === 'read'}
              <h2>What may we read?</h2>
              <p class="pitch">Nothing is read until you say so, and you see every line before anyone else does.</p>
              <ul class="tell" aria-label="What you let us read">
                {#each SOURCES as s (s.key)}
                  {@const state = m.read[s.key]}
                  <li class="source" class:on={!!m.given[s.key].trim()}>
                    <span class="tick shown" class:set={!!m.given[s.key].trim()} aria-hidden="true"><svg viewBox="0 0 20 20"><path d="M4.5 10.5 8.5 14.5 15.5 6" /></svg></span>
                    <label>
                      <b>{s.label}</b>
                      {#if s.key === 'cv'}
                        <textarea rows="2" placeholder={s.hint} bind:value={m.given.cv} oninput={keep} disabled={m.sample || reading}></textarea>
                      {:else}
                        <input placeholder={s.hint} bind:value={m.given[s.key]} oninput={keep} disabled={m.sample || reading} autocomplete="off" spellcheck="false" />
                      {/if}
                    </label>
                    {#if reading && m.given[s.key].trim() && !state}
                      <p class="drafting" role="status"><i></i>Reading</p>
                    {:else if state && 'error' in state}
                      <p class="failed" role="alert">{state.error}</p>
                    {:else if state}
                      <p class="behind">{state.lines} lines read</p>
                    {/if}
                  </li>
                {/each}
              </ul>
              {#if nothing}<p class="failed" role="alert">Nothing could be read into a profile. Try another source, or type it in on the next cards yourself.</p>{/if}
              <p class="facts">
                An address goes to Context.dev, which reads that page. The text goes to a language model (Anthropic), which turns it into lines for you to check. Our
                server keeps nothing. The draft stays in this browser tab and is gone when you close it. Never read into your profile: photo, age, gender, nationality.
              </p>
              {#if m.sample}
                <p class="sample"><b>This is a sample person.</b> Olena K. is made up, and so is everything about her. <button class="rest" onclick={() => { startOver() }}>Use my own instead</button></p>
              {:else}
                <button class="rest" onclick={() => { startOver(true) }}><Icon name="plus" size={14} />Try it with a sample person</button>
              {/if}
            {:else if item === 'you'}
              <button class="edit" aria-pressed={editing} onclick={() => (editing = !editing)}><Icon name={editing ? 'check' : 'pen'} size={16} />{editing ? 'Done' : 'Edit'}</button>
              <div class="band mine"><Mark seed={seedOf(m)} /></div>
              <h2 class:unnamed={!m.name && !editing} role={editing ? 'textbox' : undefined} aria-label={editing ? 'Your name' : undefined} contenteditable={editing ? 'plaintext-only' : undefined} spellcheck="false" data-placeholder="Your name" onblur={(e) => { m.name = typed(e); keep() }} onkeydown={enter} use:text={m.name}></h2>
              <p class="pitch" role={editing ? 'textbox' : undefined} aria-label={editing ? 'What you do' : undefined} contenteditable={editing ? 'plaintext-only' : undefined} data-placeholder="What you do, in a line" onblur={(e) => { m.headline = typed(e); keep() }} onkeydown={enter} use:text={m.headline}></p>
              <p class="facts">{[m.field, m.level].filter(Boolean).join(' · ')}</p>
              {#if m.can.length}
                <ul class="tell" aria-label="What you can do">
                  {#each m.can.filter((f, i) => i < SHOWN || more || (i >= SHOWN && on(f) && m.you_ok)) as f (f.id)}
                    <li class:on={on(f)}>
                      <button class="tick" role="checkbox" data-choice aria-checked={on(f)} aria-label="Keep this line" onclick={() => { toggle(f) }}>
                        <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4.5 10.5 8.5 14.5 15.5 6" /></svg>
                      </button>
                      <button class="say" aria-expanded={detail === f.id} onclick={() => (detail = detail === f.id ? null : f.id)}><b>{f.text}</b></button>
                      {#if detail === f.id}<p class="behind">From {SOURCE_NAME[f.source]}: “{f.from}”</p>{/if}
                    </li>
                  {/each}
                </ul>
                {#if m.can.length > SHOWN && !more}<button class="rest" onclick={() => (more = true)}><Icon name="plus" size={14} />{m.can.length - SHOWN} more we read</button>{/if}
              {/if}
            {:else if item === 'know'}
              <h2>What you know</h2>
              <p class="chips">
                {#each m.skills as f (f.id)}
                  <button class="chip want" data-choice aria-pressed={on(f)} title="From {SOURCE_NAME[f.source]}: “{f.from}”" onclick={() => { toggle(f) }}>{#if on(f)}<Icon name="check" size={14} />{/if}{f.text}</button>
                {:else}
                  <span class="chip">Nothing was named in what we read</span>
                {/each}
              </p>
              {#if m.roles.length}
                <h2 class="second">Where you have worked</h2>
                <ul class="tell" aria-label="Where you have worked">
                  {#each m.roles as f (f.id)}
                    <li class:on={on(f)}>
                      <button class="tick" role="checkbox" data-choice aria-checked={on(f)} aria-label="Keep this line" onclick={() => { toggle(f) }}>
                        <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4.5 10.5 8.5 14.5 15.5 6" /></svg>
                      </button>
                      <span class="say"><b>{f.text}</b><small>{f.from}</small></span>
                    </li>
                  {/each}
                </ul>
              {/if}
            {:else if item === 'want'}
              <h2>What are you looking for?</h2>
              <p class="chips">
                {#each fields as field (field)}
                  <button class="chip want" data-choice aria-pressed={m.wants.includes(field)} onclick={() => { want(field) }}>{#if m.wants.includes(field)}<Icon name="check" size={14} />{/if}{field}</button>
                {/each}
              </p>
              <form onsubmit={(e) => { e.preventDefault(); accept() }}>
                <input bind:value={m.looking} oninput={keep} placeholder="In a line, in your own words" aria-label="What you are looking for, in your own words" autocomplete="off" />
              </form>
              <h2 class="second">What suits you</h2>
              <p class="chips">
                {#each PLACES as place (place)}
                  <button class="chip want" data-choice aria-pressed={m.place === place} onclick={() => { m.place = m.place === place ? '' : place; keep() }}>{#if m.place === place}<Icon name="check" size={14} />{/if}{place}</button>
                {/each}
                <button class="chip want" data-choice aria-pressed={m.finnish} onclick={() => { m.finnish = !m.finnish; keep() }}>{#if m.finnish}<Icon name="check" size={14} />{/if}I work in Finnish too</button>
                <button class="chip want" data-choice aria-pressed={m.abroad} onclick={() => { m.abroad = !m.abroad; keep() }}>{#if m.abroad}<Icon name="check" size={14} />{/if}I live abroad now</button>
              </p>
            {:else}
              <h2>Who would you like to meet?</h2>
              {#if found.length}
                <ul class="tell meet" aria-label="Employers at this event">
                  {#each found as match (match.employer.brief.id)}
                    {@const id = match.employer.brief.id}
                    <li class:on={meet.includes(id)}>
                      <button class="tick" role="checkbox" data-choice aria-checked={meet.includes(id)} aria-label="Meet {nameOf(match.employer.brief)}" onclick={() => { pick(id) }}>
                        <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4.5 10.5 8.5 14.5 15.5 6" /></svg>
                      </button>
                      <span class="say"><b><span class="tile"><Logo brief={match.employer.brief} small /></span>{nameOf(match.employer.brief)}</b></span>
                      <p class="behind"><b>{match.role}</b>{#if match.reasons.length}<br />{match.reasons.join(' · ')}{/if}</p>
                    </li>
                  {/each}
                </ul>
              {:else}
                <p class="pitch">No employer at this event has said it looks for what you chose. You can still sign up, and visit anyone.</p>
              {/if}
            {/if}
          </article>
        {/each}
      </div>

      <aside class="right" aria-label="What you are looking for">
        {#if settled.want}
          <h3>You're looking for</h3>
          <button class="line" onclick={() => (opened = 'want')} in:receive={{ key: 'want' }} out:send={{ key: 'want' }}>
            <b>{m.wants.join(', ')}</b>
            <span>{terms.join(' · ')}</span>
            {#if m.looking}<span class="more">“{m.looking}”</span>{/if}
          </button>
        {/if}
      </aside>
    </div>

    <footer class="dock">
      <button class="back" onclick={back} disabled={current === 'read'} aria-label="Back"><Icon name="undo" size={16} /><kbd>←</kbd></button>
      <span class="dots" aria-label="Progress">
        {#each KEYS as k (k)}<i class:done={decided(k)} class:now={k === current}></i>{/each}
      </span>
      {#if undo}<button class="undo" onclick={takeBack}>{undo.said} Undo <kbd>Z</kbd></button>{/if}
      <span class="answers">
        <button class="yes" disabled={!ready} onclick={accept}>{answer}{first && current === 'meet' ? `, ${first}` : ''} <kbd>Enter</kbd></button>
      </span>
    </footer>
  {/if}
</div>

<style>
  @import './flow.css';

  /* the person's own pieces: their mark where a company has its logo, and the rows of the first card */
  .mine {
    padding: 0;
    background: none;
    box-shadow: none;
  }
  .plate.mine {
    width: clamp(6rem, 14vw, 9rem);
    height: clamp(6rem, 14vw, 9rem);
  }
  .band.mine {
    width: 5.5rem;
    height: 5.5rem;
    margin-bottom: var(--s4);
  }
  .unnamed {
    display: none;
  }
  .source {
    align-items: start;
  }
  .source label {
    display: grid;
    gap: var(--s1);
  }
  .source b {
    font-weight: 600;
  }
  .source input,
  .source textarea {
    width: 100%;
    min-height: 2.75rem;
    padding: var(--s2) var(--s3);
    border: 1px solid var(--line);
    border-radius: var(--r1);
    background: var(--ground);
    font: inherit;
    resize: vertical;
  }
  .source input:focus,
  .source textarea:focus {
    outline: 2px solid var(--brand);
    outline-offset: 1px;
  }
  .source .drafting,
  .source .failed,
  .source .behind {
    grid-column: 2;
    margin: var(--s1) 0 0;
  }
  .tick.shown {
    margin-top: 1.6rem;
    pointer-events: none;
  }
  .tick.shown.set {
    border-color: var(--ink);
    background: var(--ink);
  }
  .tick.shown.set svg {
    stroke-dashoffset: 0;
  }
  .sample {
    margin-top: var(--s4);
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  .sample b {
    color: var(--ink);
  }
  .meet .say b {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
  }
  .meet .tile {
    flex: none;
    width: 1.75rem;
    height: 1.75rem;
    margin: 0;
    padding: 2px;
    box-shadow: 0 0 0 1px var(--line);
  }
  .meet .behind b {
    font-weight: 600;
    color: var(--ink);
  }
  .meet .behind {
    grid-column: 2;
  }
</style>
