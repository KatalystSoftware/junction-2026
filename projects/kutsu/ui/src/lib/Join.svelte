<script lang="ts">
  import KutsuMark from './KutsuMark.svelte'
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
  import { occasion } from './events'
  import { nameOf, reviewOf, route, saveReview } from './state.svelte'
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
  const event = $derived(occasion(route().event, brief))
  // signed up for this event; a profile confirmed for another event is one press away from this one
  const joined = $derived(review.status === 'joined' && !!review.signed?.includes(event.slug))
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
    const card = bench
    if (shown && shown !== key && card && card.getBoundingClientRect().top < 0) void tick().then(() => { card.scrollIntoView({ block: 'start' }) })
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
      save({ status: 'joined', joined_at: new Date().toISOString(), wants, told, signed: [...new Set([...(review.signed ?? []), event.slug])] })
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
  <p class="host"><b class="kutsu"><KutsuMark size={16} />Kutsu</b>City of Espoo <span>{event.name}, {event.when}</span></p>

  {#if !started}
    <section class="invite">
      <div class="plate" class:dark={identity?.logo_on === 'dark'}><Logo {brief} /></div>
      <h1>{#each `${name}, you're invited.`.split(' ') as word, i (i)}<span style:--i={i}>{word}&nbsp;</span>{/each}</h1>
      <p class="filled" style:--i={5}>{event.name}, {event.when}. {event.facts} Your sign-up is already filled in.</p>
      <button class="yes big" style:--i={6} onclick={() => (started = true)}>Check it <kbd>Enter</kbd></button>
    </section>
  {:else if joined}
    <Finished {brief} {review} {about} {event} told={tell.filter((t) => told.includes(t.id))} />
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
              <Role {brief} need={item.need} change={(p: Partial<Need>) => { patch(item.need.id, p) }} />
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
  @import './flow.css';

  /* only a company has these: a logo that needs a dark plate, a role with questions still open, facts to edit in place,
     suggested roles to pick, and a role to turn down */
  .plate.dark,
  .band.dark,
  .tile.dark {
    background: #14151a;
  }
  .line .todo {
    font-weight: 700;
    color: var(--brand-ink);
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
  .chip [contenteditable] {
    background: none;
    box-shadow: none;
  }
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
  .no {
    padding: 0 var(--s4);
    background: none;
    color: var(--ink-2);
  }
  .no:hover {
    background: var(--wash);
    color: var(--ink);
  }
  @media (max-width: 40rem) {
    .no {
      padding: 0 var(--s4);
    }
  }
</style>
