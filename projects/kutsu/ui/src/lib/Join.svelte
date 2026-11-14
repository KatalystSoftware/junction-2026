<script lang="ts">
  import { tick } from 'svelte'
  import { flip } from 'svelte/animate'
  import { cubicOut } from 'svelte/easing'
  import { crossfade, fade } from 'svelte/transition'
  import Cite from './Cite.svelte'
  import { confetti } from './confetti'
  import { text } from './editable'
  import Finished from './Finished.svelte'
  import { host, terms, when } from './format'
  import Icon from './Icon.svelte'
  import Logo from './Logo.svelte'
  import Role from './Role.svelte'
  import { app, nameOf, reviewOf, saveReview } from './state.svelte'
  import type { Brief, Need, Review, Signal } from './types'

  // The company's sign-up, already filled in. One card at a time in the centre, one decision per
  // card: who you are (with what we would tell candidates), then each drafted role, then anyone
  // else and what you want at the event. What the company accepts travels to the side and stays in
  // view, so its page builds around the card: who it is on the left, who it wants to meet on the
  // right. Any line at the side opens again in the centre. The answers and their keys sit in a dock
  // at the foot of the window, so they never move.
  let { brief }: { brief: Brief } = $props()
  const review = $derived(reviewOf(brief))
  const name = $derived(nameOf(brief))
  const identity = $derived(brief.identity)
  const event = $derived(app.presets.find((p) => p.ids.includes(brief.id)) ?? app.presets[0])
  const dates = $derived(event?.note.split(',')[0] ?? '')
  const joined = $derived(review.status === 'joined')
  const save = (patch: Partial<Review>) => void saveReview(brief.id, { ...review, ...patch })

  // who they are: the brand record, each value theirs to correct
  const found = $derived<Record<string, string>>({
    Company: name,
    'What you do': brief.card.pitch || (identity?.slogan ?? ''),
    Field: identity?.industries[0]?.split(': ').pop() ?? '',
    People: identity?.employees?.replace(' to ', '–') ?? '',
    'Based in': [identity?.city, identity?.country].filter(Boolean).join(', '),
    Website: host(brief.website),
  })
  const about = (key: string): string => review.about?.[key] ?? found[key] ?? ''
  const typed = (e: FocusEvent) => (e.currentTarget as HTMLElement).innerText.replace(/\s+/g, ' ').trim()
  const fix = (key: string, e: FocusEvent) => {
    if (typed(e) !== about(key)) save({ about: { ...review.about, [key]: typed(e) } })
  }
  const enter = (e: KeyboardEvent) => {
    if (e.key !== 'Enter') return
    e.preventDefault()
    ;(e.currentTarget as HTMLElement).blur()
  }
  let editing = $state(false)

  // what we would tell candidates: three short lines by default, the rest one press away
  const SHOWN = 3
  const tell = $derived(brief.card.tell)
  const told = $derived(review.told ?? tell.slice(0, SHOWN).map((t) => t.id))
  let more = $state(false)
  let detail = $state<string | null>(null)
  const sources = (ids: string[]): Signal[] => brief.signals.filter((s) => ids.includes(s.id))
  /** Saying yes to a line opens what is behind it; saying no closes it. */
  function toggle(id: string) {
    const on = !told.includes(id)
    save({ told: on ? [...told, id] : told.filter((t) => t !== id) })
    detail = on ? id : null
  }

  // everything to decide, in order; the first undecided one is in the centre unless a line was opened
  type Item = { key: string; kind: 'you' } | { key: string; kind: 'role'; need: Need } | { key: string; kind: 'finish' }
  const items = $derived<Item[]>([
    { key: 'you', kind: 'you' },
    ...review.needs.map((need) => ({ key: `role:${need.id}`, kind: 'role' as const, need })),
    { key: 'finish', kind: 'finish' },
  ])
  const FINISH: Item = { key: 'finish', kind: 'finish' }
  const decided = (i: Item) => (i.kind === 'you' ? !!review.about_ok : i.kind === 'role' ? !!i.need.ok : joined)
  let opened = $state<string | null>(null)
  let started = $state(false)
  let seen = $state('')
  $effect(() => {
    if (seen !== brief.id) [seen, opened, started, editing, more, detail] = [brief.id, null, !!reviewOf(brief).about_ok, false, false, null]
  })
  const current = $derived(items.find((i) => i.key === opened) ?? items.find((i) => !decided(i)) ?? FINISH)
  let bench = $state<HTMLElement>()
  let shown = ''
  // a new card starts at its top, also when the last one was read to its end on a phone
  $effect(() => {
    const key = current.key
    if (shown && shown !== key && bench && bench.getBoundingClientRect().top < 0) void tick().then(() => bench?.scrollIntoView({ block: 'start' }))
    shown = key
  })

  const needs = (change: (list: Need[]) => Need[]) => { save({ needs: change(review.needs) }) }
  const patch = (id: string, p: Partial<Need>) => { needs((list) => list.map((n) => (n.id === id ? { ...n, ...p } : n))) }
  const WANTS = ['1:1 meetings with candidates', 'A virtual booth', 'A company presentation']
  const wants = $derived(review.wants ?? WANTS.slice(0, 1))
  const want = (w: string) => { save({ wants: wants.includes(w) ? wants.filter((x) => x !== w) : [...wants, w] }) }

  /** The last role removed, so one wrong key can be taken back. */
  let undo = $state<null | { said: string; restore: () => void }>(null)
  function accept() {
    const i = current
    ;[opened, undo] = [null, null]
    if (i.kind === 'you') save({ about_ok: true, told })
    else if (i.kind === 'role') patch(i.need.id, { ok: true })
    else if (line.trim()) void draft(line)
    else if (!joined) {
      save({ status: 'joined', joined_at: new Date().toISOString(), wants, told })
      confetti([...new Set([...(identity?.colors ?? []), '#ffffff', '#14151a'])])
      scrollTo({ top: 0 })
    }
  }
  /** Remove a role entirely. */
  function skip() {
    const i = current
    if (i.kind !== 'role') return
    opened = null
    const need = i.need, at = review.needs.findIndex((n) => n.id === need.id)
    needs((list) => list.filter((n) => n.id !== need.id))
    undo = { said: `Removed ${need.title || 'the role'}.`, restore: () => { needs((list) => [...list.slice(0, at), { ...need, ok: false }, ...list.slice(at)]) } }
  }
  const takeBack = () => {
    undo?.restore()
    undo = null
  }
  const back = () => {
    const at = items.findIndex((i) => i.key === current.key)
    opened = items[at - 1]?.key ?? opened
  }
  function keys(e: KeyboardEvent) {
    const el = e.target as HTMLElement
    const typing = el.isContentEditable || ['INPUT', 'TEXTAREA'].includes(el.tagName)
    const z = e.key.toLowerCase() === 'z' && !e.altKey
    // Z, or Ctrl/Cmd+Z, takes back the last removal; inside a field, z is a letter and Ctrl+Z is the field's own undo
    if (z && !typing && undo) {
      e.preventDefault()
      takeBack()
      return
    }
    if (e.metaKey || e.ctrlKey || e.altKey || typing) return
    // Enter from a choice just clicked accepts the card; Space is what changes a choice
    const choice = el.tagName === 'BUTTON' && 'choice' in el.dataset
    if (['BUTTON', 'A'].includes(el.tagName) && !(choice && e.key === 'Enter')) return
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      if (started) accept()
      else started = true
    } else if (!started) return
    else if (e.key === 'Backspace' || e.key === 'Delete') skip()
    else if (e.key === 'ArrowLeft') back()
  }

  // someone we missed: one line, or a suggestion, becomes a whole role
  let line = $state('')
  let drafting = $state('')
  let failed = $state('')
  let used = $state<string[]>([])
  const suggestions = $derived(brief.card.also.filter((s) => !used.includes(s) && !review.needs.some((n) => n.title === s)))
  async function draft(what: string) {
    ;[drafting, failed, line, used] = [what, '', '', [...used, what]]
    const r = await fetch(`role?id=${encodeURIComponent(brief.id)}`, { method: 'POST', body: JSON.stringify({ line: what }) }).catch(() => null)
    const drafted = r?.ok ? ((await r.json()) as Omit<Need, 'id'>) : null
    if (drafted) needs((list) => [...list, { ...drafted, id: `c${String(Date.now())}`, by: 'company' }])
    else failed = r?.status === 429 ? 'Busy just now. Try again in a minute.' : 'That did not come through. Try again in a minute, or carry on without it.'
    drafting = ''
  }

  // what is already settled, at the sides; the one in the centre is not shown there
  const settled = $derived({
    you: !!review.about_ok && current.key !== 'you',
    told: review.about_ok && current.key !== 'you' ? tell.filter((t) => told.includes(t.id)) : [],
    roles: review.needs.filter((n) => n.ok && current.key !== `role:${n.id}`),
  })
  /** How many of a role's practical questions nobody has answered yet. */
  const unanswered = (n: Need) => [n.language, n.workplace, n.abroad].filter((v) => v == null).length
  const calm = matchMedia('(prefers-reduced-motion: reduce)').matches
  const [send, receive] = crossfade({ duration: calm ? 0 : 560, easing: cubicOut, fallback: (node) => fade(node, { duration: calm ? 0 : 220 }) })

  const answer = $derived(
    current.kind === 'you' ? "That's us"
    : current.kind === 'role' ? 'We want to meet them'
    : line.trim() ? 'Draft this role'
    : `Sign ${about('Company')} up`,
  )
</script>

<svelte:window onkeydown={keys} />

<div class="join" class:cover={!started}>
  <p class="host">City of Espoo <span>{event?.title}, {dates}</span></p>

  {#if !started}
    <section class="invite">
      <div class="plate" class:dark={identity?.logo_on === 'dark'}><Logo {brief} /></div>
      <h1>{#each `${name}, you're invited.`.split(' ') as word, i (i)}<span style:--i={i}>{word}&nbsp;</span>{/each}</h1>
      <p class="filled" style:--i={5}>{event?.title}, {dates}. Online and free. Your sign-up is already filled in.</p>
      <button class="yes big" style:--i={6} onclick={() => (started = true)}>Check it <kbd>Enter</kbd></button>
    </section>
  {:else if joined}
    <Finished {brief} {review} {about} told={tell.filter((t) => told.includes(t.id))} />
  {:else}
    <div class="bench" bind:this={bench}>
      <aside class="left" aria-label="About you">
        {#if settled.you}
          <h3>About you</h3>
          <button class="line you" onclick={() => (opened = 'you')} in:receive={{ key: 'you' }} out:send={{ key: 'you' }}>
            <span class="tile" class:dark={identity?.icon_on === 'dark'}><Logo {brief} small /></span>
            <b>{about('Company')}</b>
            <span>{about('What you do')}</span>
          </button>
          {#each settled.told as t (t.id)}
            <button class="line" onclick={() => { opened = 'you'; detail = t.id }} in:fade={{ duration: 300, delay: 250 }} animate:flip={{ duration: 300 }}>
              <span class="fact">{t.line}</span>
              <span class="more">{t.detail}</span>
            </button>
          {/each}
        {/if}
      </aside>

      <div class="centre">
        <!-- one keyed item, so a card that is leaving keeps its own content and key while it travels to the side -->
        {#each [current] as item (item.key)}
          <article class="card" in:receive={{ key: item.key }} out:send={{ key: item.key }}>
            {#if item.kind === 'you'}
              <button class="edit" aria-pressed={editing} onclick={() => (editing = !editing)}><Icon name={editing ? 'check' : 'pen'} size={16} />{editing ? 'Done' : 'Edit'}</button>
              <div class="band" class:dark={identity?.logo_on === 'dark'}><Logo {brief} /></div>
              <h2 role={editing ? 'textbox' : undefined} aria-label={editing ? 'Company' : undefined} contenteditable={editing ? 'plaintext-only' : undefined} spellcheck="false" onblur={(e) => { fix('Company', e) }} onkeydown={enter} use:text={about('Company')}></h2>
              <p class="pitch" role={editing ? 'textbox' : undefined} aria-label={editing ? 'What you do' : undefined} contenteditable={editing ? 'plaintext-only' : undefined} data-placeholder="What you do, in a line" onblur={(e) => { fix('What you do', e) }} onkeydown={enter} use:text={about('What you do')}></p>
              {#if editing}
                <p class="chips">
                  {#each ['Field', 'People', 'Based in', 'Website'] as key (key)}
                    <span class="chip"><small>{key}</small><span role="textbox" tabindex="0" aria-label={key} contenteditable="plaintext-only" data-placeholder="add" onblur={(e) => { fix(key, e) }} onkeydown={enter} use:text={about(key)}></span></span>
                  {/each}
                </p>
              {:else}
                <p class="facts">{[about('Field'), about('People') && `${about('People')} people`, about('Based in'), about('Website')].filter(Boolean).join(' · ')}</p>
              {/if}

              {#if tell.length}
                <ul class="tell" aria-label="What we would tell candidates">
                  {#each tell.filter((t, i) => i < SHOWN || more || told.includes(t.id)) as t (t.id)}
                    <li class:on={told.includes(t.id)}>
                      <button class="tick" role="checkbox" data-choice aria-checked={told.includes(t.id)} aria-label="Tell candidates this" onclick={() => { toggle(t.id) }}>
                        <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4.5 10.5 8.5 14.5 15.5 6" /></svg>
                      </button>
                      <button class="say" aria-expanded={detail === t.id} onclick={() => (detail = detail === t.id ? null : t.id)}>
                        <b>{t.line}</b><small>{when(t.date)}</small>
                      </button>
                      {#if detail === t.id}
                        <p class="behind">{t.detail} {#each sources(t.signals) as s (s.id)}<Cite signal={s} label={host(s.source_url)} />{/each}</p>
                      {/if}
                    </li>
                  {/each}
                </ul>
                {#if tell.length > SHOWN && !more}<button class="rest" onclick={() => (more = true)}><Icon name="plus" size={14} />{tell.length - SHOWN} more we could tell</button>{/if}
              {/if}
            {:else if item.kind === 'role'}
              <Role {brief} need={item.need} change={(p) => { patch(item.need.id, p) }} />
            {:else}
              <h2>Anyone else?</h2>
              {#if drafting}
                <p class="drafting" role="status"><i></i>Drafting “{drafting}”</p>
              {:else}
                <form onsubmit={(e) => { e.preventDefault(); if (line.trim()) void draft(line) }}>
                  <input bind:value={line} placeholder="Describe them in a line" aria-label="Describe who else you want to meet" autocomplete="off" />
                </form>
                {#if suggestions.length}
                  <p class="chips">
                    {#each suggestions as s (s)}<button class="chip pick" onclick={() => void draft(s)}><Icon name="plus" size={14} />{s}</button>{/each}
                  </p>
                {/if}
                {#if failed}<p class="failed" role="alert">{failed}</p>{/if}
              {/if}
              <h2 class="second">At the event</h2>
              <p class="chips">
                {#each WANTS as w (w)}
                  <button class="chip want" data-choice aria-pressed={wants.includes(w)} onclick={() => { want(w) }}>{#if wants.includes(w)}<Icon name="check" size={14} />{/if}{w}</button>
                {/each}
              </p>
            {/if}
          </article>
        {/each}
      </div>

      <aside class="right" aria-label="Who you want to meet">
        {#if settled.roles.length}<h3>You want to meet</h3>{/if}
        {#each settled.roles as n (n.id)}
          <button class="line" onclick={() => (opened = `role:${n.id}`)} in:receive={{ key: `role:${n.id}` }} out:send={{ key: `role:${n.id}` }} animate:flip={{ duration: 300 }}>
            <b>{n.title}</b>
            <span>{terms(n).join(' · ')}</span>
            {#if unanswered(n)}<span class="todo">{unanswered(n)} still to answer</span>{/if}
            {#if n.can_do.length}<span class="more">{#each n.can_do as task, k (k)}{#if k}<br />{/if}{task}{/each}</span>{/if}
          </button>
        {/each}
      </aside>
    </div>

    <footer class="dock">
      <button class="back" onclick={back} disabled={items[0]?.key === current.key} aria-label="Back"><Icon name="undo" size={16} /><kbd>←</kbd></button>
      <span class="dots" aria-label="Progress">
        {#each items as i (i.key)}<i class:done={decided(i)} class:now={i.key === current.key}></i>{/each}
      </span>
      {#if undo}<button class="undo" onclick={takeBack}>{undo.said} Undo <kbd>Z</kbd></button>{/if}
      <span class="answers">
        {#if current.kind === 'role'}<button class="no" onclick={skip}>Not us <kbd>Backspace</kbd></button>{/if}
        <button class="yes" disabled={!!drafting || (current.kind === 'finish' && !line.trim() && !review.needs.some((n) => n.ok))} onclick={accept}>{answer} <kbd>Enter</kbd></button>
      </span>
    </footer>
  {/if}
</div>

<style>
  .join {
    position: relative;
    min-height: 100dvh;
    padding: 0 clamp(1rem, 3vw, 2.5rem) 7rem;
    background: var(--brand);
    color: var(--brand-ink);
    overflow: clip;
  }
  /* the invitation opens on white, and the company's colour floods in from its logo */
  .join.cover {
    background: var(--ground);
  }
  .join.cover::before {
    content: '';
    position: absolute;
    inset: 0;
    background: var(--brand);
    clip-path: circle(0% at 12rem 14rem);
    animation: flood 1.2s var(--ease) 0.45s forwards;
  }
  .join > * {
    position: relative;
  }
  .join :focus-visible {
    outline-color: var(--brand-ink);
  }
  .host {
    padding: var(--s4) 0;
    font-size: var(--t-sm);
    font-weight: 700;
  }
  .host span {
    margin-left: var(--s3);
    font-weight: 400;
    color: color-mix(in oklch, var(--brand-ink) 90%, var(--brand));
  }
  .cover .host {
    animation: fade 0.6s 1.1s backwards;
  }
  kbd {
    padding: 0.05rem 0.4rem;
    border: 1px solid color-mix(in srgb, currentColor 45%, transparent);
    border-radius: 5px;
    font: 600 var(--t-xs) / 1.4 var(--text);
    opacity: 0.85;
  }

  .invite {
    max-width: 52rem;
    margin: clamp(1.5rem, 8vh, 5rem) auto 0;
  }
  .plate {
    width: min(100%, 20rem);
    height: clamp(7rem, 20vh, 11rem);
    padding: var(--s5);
    border-radius: var(--r2);
    background: #fff;
    box-shadow: var(--lift);
    animation: land 0.9s var(--ease) backwards;
  }
  .plate.dark,
  .band.dark,
  .tile.dark {
    background: #14151a;
  }
  .plate :global(.logo),
  .band :global(.logo),
  .tile :global(.logo) {
    background: none;
  }
  h1 {
    margin-top: var(--s6);
    font-size: clamp(2.75rem, 1.4rem + 5.6vw, 6rem);
    font-weight: 800;
    letter-spacing: -0.035em;
    line-height: 0.95;
  }
  h1 span,
  .filled,
  .invite .yes {
    display: inline-block;
    animation: rise 0.8s var(--ease) backwards;
    animation-delay: calc(var(--i) * 80ms + 0.9s);
  }
  .filled {
    display: block;
    max-width: 34ch;
    margin-top: var(--s4);
    font-size: clamp(1.125rem, 1rem + 0.5vw, 1.375rem);
    line-height: 1.35;
  }

  /* three columns: who you are, the card, who you want to meet. the card sits in the middle of the
     space between the header and the dock */
  .bench {
    display: grid;
    grid-template-columns: minmax(12rem, 1fr) minmax(0, 36rem) minmax(12rem, 1fr);
    align-items: start;
    gap: clamp(1rem, 2.5vw, 2.5rem);
    max-width: 88rem;
    min-height: calc(100dvh - 11.5rem);
    margin: 0 auto;
  }
  aside {
    position: sticky;
    top: var(--s4);
    display: grid;
    gap: var(--s1);
    align-content: start;
  }
  aside h3 {
    padding: 0 var(--s3) var(--s2);
    font: 700 var(--t-sm) / 1.2 var(--text);
    letter-spacing: 0;
    color: color-mix(in oklch, var(--brand-ink) 90%, var(--brand));
    animation: fade 0.4s;
  }
  /* a settled answer: written straight on the colour, so the card stays the only bright surface */
  .line {
    position: relative;
    display: grid;
    gap: 0.15rem;
    padding: var(--s3);
    border: 0;
    border-radius: var(--r2);
    background: none;
    color: inherit;
    text-align: left;
    line-height: 1.3;
    transition: background 0.15s;
  }
  .line:hover,
  .line:focus-visible {
    background: color-mix(in srgb, var(--brand-ink) 12%, transparent);
  }
  .line b {
    font-size: var(--t-lg);
    font-weight: 700;
    letter-spacing: -0.015em;
  }
  .line > span {
    font-size: var(--t-sm);
    color: color-mix(in oklch, var(--brand-ink) 92%, var(--brand));
  }
  .line .fact {
    font-size: var(--t-md);
    font-weight: 600;
    color: var(--brand-ink);
  }
  .line .todo {
    font-weight: 700;
    color: var(--brand-ink);
  }
  /* more of a settled answer opens over what is below it on hover or focus, and pushes nothing */
  .line .more {
    position: absolute;
    top: calc(100% - var(--s2));
    left: var(--s2);
    right: var(--s2);
    z-index: 5;
    padding: var(--s3);
    border-radius: var(--r2);
    background: var(--brand-ink);
    color: var(--brand);
    line-height: 1.4;
    box-shadow: var(--lift);
    opacity: 0;
    visibility: hidden;
    translate: 0 -4px;
    transition: opacity 0.18s, translate 0.25s var(--ease), visibility 0.18s;
  }
  .line:hover .more,
  .line:focus-visible .more {
    opacity: 1;
    visibility: visible;
    translate: 0;
  }
  .tile {
    width: 3rem;
    height: 3rem;
    margin-bottom: var(--s2);
    padding: 6px;
    border-radius: var(--r1);
    background: #fff;
    font-size: 0.8rem;
  }

  .centre {
    display: grid;
    align-self: center;
  }
  .card {
    position: relative;
    grid-area: 1 / 1;
    padding: clamp(1.25rem, 3vw, 2.25rem);
    border-radius: 1.25rem;
    background: var(--ground);
    color: var(--ink);
    box-shadow: var(--lift);
  }
  .card :focus-visible {
    outline-color: var(--ink);
  }
  .edit {
    position: absolute;
    top: var(--s3);
    right: var(--s3);
    z-index: 1;
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    min-height: 2rem;
    padding: 0 var(--s3);
    border: 0;
    border-radius: 99px;
    background: var(--ground);
    color: var(--ink-2);
    font-size: var(--t-sm);
    font-weight: 600;
  }
  .edit:hover,
  .edit[aria-pressed='true'] {
    background: var(--wash);
    color: var(--ink);
  }
  .band {
    height: clamp(5.5rem, 14vh, 8rem);
    margin-bottom: var(--s5);
    padding: var(--s4) 22%;
    border-radius: var(--r2);
  }
  .band:not(.dark) {
    background: #fff;
    box-shadow: inset 0 0 0 1px var(--line);
  }
  h2 {
    font-size: var(--t-xl);
    font-weight: 800;
    letter-spacing: -0.03em;
    line-height: 1.05;
  }
  h2.second {
    margin-top: var(--s6);
    font-size: var(--t-lg);
    letter-spacing: -0.015em;
  }
  .pitch {
    margin-top: var(--s2);
    font-size: var(--t-lg);
    line-height: 1.35;
  }
  .facts {
    margin-top: var(--s2);
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  /* what we would tell candidates: a short line each; the sentence and its source open on request */
  .tell {
    display: grid;
    margin-top: var(--s5);
    border-top: 1px solid var(--line);
  }
  .tell li {
    display: grid;
    grid-template-columns: auto 1fr;
    align-items: center;
    column-gap: var(--s3);
    padding: var(--s2) 0;
    border-bottom: 1px solid var(--line);
  }
  .say {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--s3);
    min-height: 2.25rem;
    padding: 0;
    border: 0;
    background: none;
    text-align: left;
  }
  .say b {
    font-size: var(--t-lg);
    font-weight: 600;
    letter-spacing: -0.01em;
    line-height: 1.25;
  }
  .say small {
    flex: none;
    font-size: var(--t-xs);
    color: var(--ink-2);
  }
  .tell li:not(.on) .say b {
    color: var(--ink-2);
    font-weight: 500;
  }
  .behind {
    grid-column: 2;
    padding: 0 0 var(--s2);
    color: var(--ink-2);
    line-height: 1.45;
    animation: rise 0.3s var(--ease);
  }
  .rest {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    margin-top: var(--s2);
    padding: var(--s1) 0;
    border: 0;
    background: none;
    color: var(--ink-2);
    font-size: var(--t-sm);
    font-weight: 600;
  }
  .rest:hover {
    color: var(--ink);
  }
  /* the tick draws itself, and its box takes the company's colour */
  .tick {
    display: grid;
    place-items: center;
    width: 1.5rem;
    height: 1.5rem;
    border: 2px solid var(--line);
    border-radius: 6px;
    background: var(--ground);
    transition: background 0.25s, border-color 0.25s, scale 0.25s var(--ease);
  }
  .tick:active {
    scale: 0.9;
  }
  .tick svg {
    width: 1rem;
    fill: none;
    stroke: var(--brand-ink);
    stroke-width: 2.6;
    stroke-linecap: round;
    stroke-linejoin: round;
    stroke-dasharray: 18;
    stroke-dashoffset: 18;
    transition: stroke-dashoffset 0.35s var(--ease) 0.05s;
  }
  .on > .tick {
    border-color: var(--brand);
    background: var(--brand);
  }
  .on > .tick svg {
    stroke-dashoffset: 0;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s2);
    margin-top: var(--s3);
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    min-height: 2.25rem;
    padding: 0 var(--s3);
    border: 1px solid var(--line);
    border-radius: 99px;
    background: var(--ground);
    color: var(--ink);
    font-weight: 600;
  }
  .chip small {
    font-size: var(--t-xs);
    font-weight: 500;
    color: var(--ink-2);
  }
  .pick {
    border-style: dashed;
    font-size: var(--t-sm);
    transition: border-color 0.15s;
  }
  .pick:hover {
    border-style: solid;
    border-color: var(--ink);
  }
  .want {
    transition: background 0.2s, color 0.2s;
  }
  .want[aria-pressed='true'] {
    border-color: var(--ink);
    background: var(--ink);
    color: var(--ground);
  }
  [contenteditable] {
    border-radius: 4px;
    outline: none;
    background: var(--wash);
    box-shadow: 0 0 0 4px var(--wash);
  }
  [contenteditable]:focus {
    background: var(--ground);
    box-shadow: 0 0 0 4px var(--ground), 0 0 0 6px var(--ink);
  }
  [contenteditable]:empty::before {
    content: attr(data-placeholder);
    color: color-mix(in oklch, var(--ink-2) 65%, var(--ground));
  }
  .chip [contenteditable] {
    background: none;
    box-shadow: none;
  }
  form input {
    width: 100%;
    height: 3.25rem;
    margin-top: var(--s4);
    padding: 0 var(--s4);
    border: 2px solid var(--line);
    border-radius: var(--r2);
    outline: none;
    background: var(--ground);
    font-size: var(--t-lg);
  }
  form input:focus {
    border-color: var(--ink);
  }
  .drafting {
    display: flex;
    align-items: center;
    gap: var(--s3);
    margin-top: var(--s4);
    font-size: var(--t-lg);
    color: var(--ink-2);
  }
  .drafting i {
    width: 0.75rem;
    height: 0.75rem;
    border-radius: 50%;
    background: var(--brand);
    animation: pulse 0.8s ease-in-out infinite alternate;
  }
  .failed {
    margin-top: var(--s3);
    color: var(--stop);
  }

  /* the dock: the answers, their keys and the progress, fixed at the foot of the window so nothing the
     hand needs ever moves */
  .dock {
    position: fixed;
    left: 50%;
    bottom: var(--s4);
    z-index: 10;
    display: flex;
    align-items: center;
    gap: var(--s3);
    width: min(100% - 2rem, 46rem);
    min-height: 4rem;
    padding: var(--s2) var(--s2) var(--s2) var(--s3);
    border-radius: 99px;
    background: var(--ground);
    color: var(--ink);
    box-shadow: var(--lift);
    translate: -50% 0;
    animation: rise 0.5s var(--ease) backwards;
  }
  .dock :focus-visible {
    outline-color: var(--ink);
  }
  .answers {
    display: flex;
    align-items: center;
    gap: var(--s1);
    margin-left: auto;
  }
  .yes,
  .no {
    display: inline-flex;
    align-items: center;
    gap: var(--s3);
    min-height: 3rem;
    padding: 0 var(--s5);
    border: 0;
    border-radius: 99px;
    font-weight: 700;
    white-space: nowrap;
    transition: transform 0.2s var(--ease), box-shadow 0.2s, background 0.15s;
  }
  .yes {
    background: var(--ink);
    color: var(--ground);
  }
  .yes:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 10px 24px -10px rgb(0 0 0 / 0.5);
  }
  .yes:disabled {
    opacity: 0.4;
    cursor: default;
  }
  .yes.big {
    min-height: 3.5rem;
    margin-top: var(--s6);
    padding: 0 var(--s6);
    background: var(--brand-ink);
    color: var(--brand);
    font-size: var(--t-lg);
  }
  .no {
    padding: 0 var(--s4);
    background: none;
    color: var(--ink-2);
  }
  .no:hover {
    background: var(--wash);
    color: var(--ink);
  }
  .dots {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    max-width: 8rem;
  }
  .dots i {
    width: 0.45rem;
    height: 0.45rem;
    border: 1.5px solid currentColor;
    border-radius: 50%;
    opacity: 0.4;
    transition: opacity 0.3s, background 0.3s, scale 0.3s var(--ease);
  }
  .dots i.done {
    background: currentColor;
    opacity: 0.85;
  }
  .dots i.now {
    border-color: var(--brand);
    background: var(--brand);
    opacity: 1;
    scale: 1.5;
  }
  .back,
  .undo {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    min-height: 3rem;
    padding: 0 var(--s3);
    border: 0;
    border-radius: 99px;
    background: none;
    color: var(--ink-2);
    font-size: var(--t-sm);
    font-weight: 600;
    white-space: nowrap;
  }
  .back:hover:not(:disabled),
  .undo:hover {
    background: var(--wash);
    color: var(--ink);
  }
  .back:disabled {
    opacity: 0.3;
    cursor: default;
  }

  @keyframes flood {
    to {
      clip-path: circle(150% at 12rem 14rem);
    }
  }
  @keyframes land {
    from {
      opacity: 0;
      scale: 0.8;
      translate: 0 20px;
    }
  }
  @keyframes rise {
    from {
      opacity: 0;
      translate: 0 18px;
    }
  }
  @keyframes fade {
    from {
      opacity: 0;
    }
  }
  @keyframes pulse {
    to {
      scale: 1.5;
      opacity: 0.5;
    }
  }
  /* less room: the card first, then the page that is building under it */
  @media (max-width: 72rem) {
    .bench {
      grid-template-columns: minmax(0, 1fr);
      min-height: 0;
    }
    .centre {
      order: -1;
    }
    aside {
      position: static;
    }
    .line .more {
      position: static;
      padding: 0;
      background: none;
      color: inherit;
      box-shadow: none;
      opacity: 1;
      visibility: visible;
      translate: 0;
    }
  }
  @media (max-width: 40rem) {
    kbd,
    .dots {
      display: none;
    }
    .dock {
      bottom: 0;
      width: 100%;
      min-height: 0;
      padding: var(--s2) var(--s3) calc(var(--s2) + env(safe-area-inset-bottom));
      border-radius: 1.25rem 1.25rem 0 0;
    }
    .answers {
      flex: 1;
      justify-content: flex-end;
    }
    .yes,
    .no {
      padding: 0 var(--s4);
    }
  }
</style>
