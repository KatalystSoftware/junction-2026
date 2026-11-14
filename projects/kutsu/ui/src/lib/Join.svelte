<script lang="ts">
  import { tick } from 'svelte'
  import { flip } from 'svelte/animate'
  import { cubicOut } from 'svelte/easing'
  import { crossfade, fade } from 'svelte/transition'
  import Cite from './Cite.svelte'
  import { text } from './editable'
  import { host, terms, when } from './format'
  import Icon from './Icon.svelte'
  import Logo from './Logo.svelte'
  import Role from './Role.svelte'
  import { app, nameOf, reviewOf, saveReview } from './state.svelte'
  import type { Brief, Need, Review, Signal } from './types'

  // The company's sign-up, already filled in. One card at a time in the centre; what the company
  // accepts moves to the side and stays in view, so its page builds around the card: who it is on
  // the left, who it wants to meet on the right. Any line at the side opens again in the centre.
  let { brief }: { brief: Brief } = $props()
  const review = $derived(reviewOf(brief))
  const name = $derived(nameOf(brief))
  const identity = $derived(brief.identity)
  const event = $derived(app.presets.find((p) => p.ids.includes(brief.id)) ?? app.presets[0])
  const joined = $derived(review.status === 'joined')
  const save = (patch: Partial<Review>) => saveReview(brief.id, { ...review, ...patch })

  // who they are: the brand record, each value theirs to correct
  const found = $derived<Record<string, string>>({
    Company: name,
    'What you do': brief.card.pitch || identity?.slogan || '',
    Field: identity?.industries[0]?.split(': ').pop() ?? '',
    People: identity?.employees?.replace(' to ', '–') ?? '',
    'Based in': [identity?.city, identity?.country].filter(Boolean).join(', '),
    Website: host(brief.website),
  })
  const about = (key: string) => review.about?.[key] ?? found[key]
  const typed = (e: FocusEvent) => (e.currentTarget as HTMLElement).innerText.replace(/\s+/g, ' ').trim()
  const fix = (key: string, e: FocusEvent) => typed(e) !== about(key) && save({ about: { ...review.about, [key]: typed(e) } })
  const enter = (e: KeyboardEvent) => e.key === 'Enter' && (e.preventDefault(), (e.currentTarget as HTMLElement).blur())

  // their news: the few statements worth telling talent, the kinds they care about first, newest first
  const WEIGHT = ['funding', 'growth', 'customers', 'product', 'partnership', 'technology', 'hiring']
  const news = $derived(
    brief.signals
      .filter((s) => WEIGHT.includes(s.type))
      .sort((a, b) => WEIGHT.indexOf(a.type) - WEIGHT.indexOf(b.type) || b.date.localeCompare(a.date))
      .slice(0, 4),
  )
  const sourced = (s: Signal) => [host(s.source_url), when(s.date)].filter(Boolean).join(', ')

  // everything to decide, in order; the first undecided one is in the centre unless a line was opened
  type Item = { key: string; kind: 'you' | 'news' | 'role' | 'add' | 'finish'; signal?: Signal; need?: Need }
  const items = $derived<Item[]>([
    { key: 'you', kind: 'you' },
    ...news.map((signal) => ({ key: `news:${signal.id}`, kind: 'news' as const, signal })),
    ...review.needs.map((need) => ({ key: `role:${need.id}`, kind: 'role' as const, need })),
    { key: 'add', kind: 'add' },
    { key: 'finish', kind: 'finish' },
  ])
  const decided = (i: Item) =>
    i.kind === 'you' ? !!review.about_ok
    : i.kind === 'news' ? review.facts?.[i.signal!.id] !== undefined
    : i.kind === 'role' ? !!i.need!.ok
    : i.kind === 'add' ? !!review.added_done
    : joined
  let opened = $state<string | null>(null)
  let started = $state(false)
  let seen = $state('')
  $effect(() => {
    if (seen !== brief.id) [seen, opened, started] = [brief.id, null, !!reviewOf(brief).about_ok]
  })
  const current = $derived(items.find((i) => i.key === opened) ?? items.find((i) => !decided(i)) ?? items.at(-1)!)
  let bench = $state<HTMLElement>()
  let shown = ''
  // a new card starts at its top, also when the last one was read to its end on a phone
  $effect(() => {
    const key = current.key
    if (shown && shown !== key && bench && bench.getBoundingClientRect().top < 0) tick().then(() => bench?.scrollIntoView({ block: 'start' }))
    shown = key
  })

  const needs = (change: (list: Need[]) => Need[]) => save({ needs: change(review.needs) })
  const patch = (id: string | undefined, p: Partial<Need>) => needs((list) => list.map((n) => (n.id === id ? { ...n, ...p } : n)))
  const WANTS = ['1:1 meetings with candidates', 'A virtual booth', 'A company presentation']
  const wants = $derived(review.wants ?? [WANTS[0]])
  const want = (w: string) => save({ wants: wants.includes(w) ? wants.filter((x) => x !== w) : [...wants, w] })

  function accept() {
    const i = current
    ;[opened, undo] = [null, null]
    if (i.kind === 'you') save({ about_ok: true })
    else if (i.kind === 'news') save({ facts: { ...review.facts, [i.signal!.id]: true } })
    else if (i.kind === 'role') patch(i.need!.id, { ok: true })
    else if (i.kind === 'add') line.trim() ? draft(line) : save({ added_done: true })
    else if (!joined) save({ status: 'joined', joined_at: new Date().toISOString(), wants })
  }
  /** The last thing left out or removed, so one wrong key can be taken back. */
  let undo = $state<null | { said: string; restore: () => void }>(null)
  /** Leave a statement out, or remove a role entirely. */
  function skip() {
    const i = current
    opened = null
    if (i.kind === 'news') {
      const id = i.signal!.id
      save({ facts: { ...review.facts, [id]: false } })
      undo = { said: 'Left out.', restore: () => (save({ facts: Object.fromEntries(Object.entries(review.facts ?? {}).filter(([k]) => k !== id)) }), (opened = `news:${id}`)) }
    } else if (i.kind === 'role') {
      const need = i.need!, at = review.needs.findIndex((n) => n.id === need.id)
      needs((list) => list.filter((n) => n.id !== need.id))
      undo = { said: `Removed ${need.title || 'the role'}.`, restore: () => needs((list) => [...list.slice(0, at), { ...need, ok: false }, ...list.slice(at)]) }
    }
  }
  const takeBack = () => (undo?.restore(), (undo = null))
  const back = () => {
    const at = items.findIndex((i) => i.key === current.key)
    if (at > 0) opened = items[at - 1].key
  }
  function keys(e: KeyboardEvent) {
    const el = e.target as HTMLElement
    const choice = el.tagName === 'BUTTON' && 'choice' in el.dataset && e.key === 'Enter'
    if (!choice && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'BUTTON', 'A'].includes(el.tagName) || e.metaKey || e.ctrlKey || e.altKey)) return
    if (e.key === 'Enter') (e.preventDefault(), started ? accept() : (started = true))
    else if (!started) return
    else if (e.key === 'Backspace' || e.key === 'Delete') skip()
    else if (e.key === 'ArrowLeft') back()
  }

  // someone we missed: one line, or a suggestion, becomes a whole role
  let line = $state('')
  let drafting = $state('')
  let failed = $state('')
  const SUGGEST = ['Sales and account leads', 'Customer success managers', 'Data engineers', 'Product managers']
  let used = $state<string[]>([])
  const suggestions = $derived((brief.card.also?.length ? brief.card.also : SUGGEST).filter((s) => !used.includes(s) && !review.needs.some((n) => n.title === s)))
  async function draft(what: string) {
    ;[drafting, failed, line, used] = [what, '', '', [...used, what]]
    const r = await fetch(`role?id=${encodeURIComponent(brief.id)}`, { method: 'POST', body: JSON.stringify({ line: what }) }).catch(() => null)
    const drafted: Need | null = r?.ok ? await r.json() : null
    if (drafted) needs((list) => [...list, { ...drafted, id: `c${Date.now()}`, by: 'company' }])
    else failed = r?.status === 429 ? 'Busy just now. Try again in a minute.' : 'That did not come through. Try again.'
    drafting = ''
  }

  // what is already settled, at the sides; the one in the centre is not shown there
  const settled = $derived({
    you: !!review.about_ok && current.key !== 'you',
    news: news.filter((s) => review.facts?.[s.id] === true && current.key !== `news:${s.id}`),
    roles: review.needs.filter((n) => n.ok && current.key !== `role:${n.id}`),
  })
  /** How many of a role's practical questions nobody has answered yet. */
  const open = (n: Need) => [n.language, n.workplace, n.abroad].filter((v) => v == null).length
  const calm = matchMedia('(prefers-reduced-motion: reduce)').matches
  const [send, receive] = crossfade({ duration: calm ? 0 : 520, easing: cubicOut, fallback: (node) => fade(node, { duration: calm ? 0 : 200 }) })
</script>

<svelte:window onkeydown={keys} />

<div class="join" class:cover={!started}>
  <p class="host">City of Espoo <span>{event?.title}, {event?.note.split(',')[0]}</span></p>

  {#if !started}
    <section class="invite">
      <div class="plate" class:dark={identity?.logo_on === 'dark'}><Logo {brief} /></div>
      <h1>{#each `${name}, you're invited.`.split(' ') as word, i}<span style:--i={i}>{word}&nbsp;</span>{/each}</h1>
      <p class="filled" style:--i={5}>{event?.title}, {event?.note.split(',')[0]}. Online and free: deep-tech professionals from around the world meet Finnish employers. Your sign-up is already filled in.</p>
      <button class="yes big" style:--i={6} onclick={() => (started = true)}>Check it <kbd>Enter</kbd></button>
    </section>
  {:else}
    <div class="bench" bind:this={bench}>
      <aside class="left" aria-label="About you">
        {#if settled.you || settled.news.length}<h3>About you</h3>{/if}
        {#if settled.you}
          <button class="line you" onclick={() => (opened = 'you')} in:receive={{ key: 'you' }} out:send={{ key: 'you' }}>
            <span class="tile" class:dark={identity?.icon_on === 'dark'}><Logo {brief} small /></span>
            <b>{about('Company')}</b>
            <span class="more">{about('What you do')}</span>
            <span class="more">{[about('Field'), about('People') && `${about('People')} people`, about('Based in')].filter(Boolean).join(' · ')}</span>
          </button>
        {/if}
        {#each settled.news as s (s.id)}
          <button class="line" onclick={() => (opened = `news:${s.id}`)} in:receive={{ key: `news:${s.id}` }} out:send={{ key: `news:${s.id}` }} animate:flip={{ duration: 300 }}>
            <span class="clamp">{s.claim}</span>
            <span class="more">{sourced(s)}</span>
          </button>
        {/each}
      </aside>

      <div class="centre">
        {#key current.key}
          <article class="card" in:receive={{ key: current.key }} out:send={{ key: current.key }}>
            {#if current.kind === 'you'}
              <div class="band" class:dark={identity?.logo_on === 'dark'}><Logo {brief} /></div>
              <h2 role="textbox" tabindex="0" aria-label="Company" contenteditable="plaintext-only" spellcheck="false" onblur={(e) => fix('Company', e)} onkeydown={enter} use:text={about('Company')}></h2>
              <p class="pitch" role="textbox" tabindex="0" aria-label="What you do" contenteditable="plaintext-only" data-placeholder="What you do, in a line" onblur={(e) => fix('What you do', e)} onkeydown={enter} use:text={about('What you do')}></p>
              <p class="chips">
                {#each ['Field', 'People', 'Based in', 'Website'] as key}
                  <span class="chip"><small>{key}</small><span role="textbox" tabindex="0" aria-label={key} contenteditable="plaintext-only" data-placeholder="add" onblur={(e) => fix(key, e)} onkeydown={enter} use:text={about(key)}></span></span>
                {/each}
              </p>
              <div class="actions"><button class="yes" onclick={accept}>That's us <kbd>Enter</kbd></button></div>
            {:else if current.kind === 'news'}
              <h2 class="claim">{current.signal!.claim}</h2>
              <p class="chips"><Cite signal={current.signal!} label={sourced(current.signal!)} /></p>
              <div class="actions">
                <button class="yes" onclick={accept}>Show this to candidates <kbd>Enter</kbd></button>
                <button class="no" onclick={skip}>Leave it out <kbd>Backspace</kbd></button>
              </div>
            {:else if current.kind === 'role'}
              <Role {brief} need={current.need!} change={(p) => patch(current.need!.id, p)} />
              <div class="actions">
                <button class="yes" onclick={accept}>We want to meet them <kbd>Enter</kbd></button>
                <button class="no" onclick={skip}>Not us <kbd>Backspace</kbd></button>
              </div>
            {:else if current.kind === 'add'}
              <h2>Anyone else?</h2>
              {#if drafting}
                <p class="drafting" role="status"><i></i>Drafting “{drafting}”</p>
              {:else}
                <form onsubmit={(e) => (e.preventDefault(), line.trim() && draft(line))}>
                  <input bind:value={line} placeholder="Describe them in a line" aria-label="Describe who else you want to meet" autocomplete="off" />
                </form>
                <p class="chips">
                  {#each suggestions as s}<button class="chip pick" onclick={() => draft(s)}><Icon name="plus" size={14} />{s}</button>{/each}
                </p>
                {#if failed}<p class="failed" role="alert">{failed}</p>{/if}
                <div class="actions">
                  {#if line.trim()}
                    <button class="yes" onclick={() => draft(line)}>Draft this role <kbd>Enter</kbd></button>
                  {:else}
                    <button class="yes" onclick={accept}>No one else <kbd>Enter</kbd></button>
                  {/if}
                </div>
              {/if}
            {:else if joined}
              <h2 class="in">You're in.</h2>
              <p class="pitch">Candidates at the forum will see {about('Company')} as it stands on this page, and nothing you left out. Espoo's event team will be in touch before {event?.note.split(',')[0].split('–')[0]} November with your booking. Open any role you chose to change it or to draft its job posting.</p>
              <div class="actions"><button class="no" onclick={() => save({ status: 'invited' })}><Icon name="undo" size={16} />Change my answers</button></div>
            {:else}
              <h2>What would you like at the event?</h2>
              <p class="chips">
                {#each WANTS as w}
                  <button class="chip want" data-choice aria-pressed={wants.includes(w)} onclick={() => want(w)}>{#if wants.includes(w)}<Icon name="check" size={14} />{/if}{w}</button>
                {/each}
              </p>
              <div class="actions">
                <button class="yes" disabled={!review.needs.some((n) => n.ok)} onclick={accept}>Sign {about('Company')} up <kbd>Enter</kbd></button>
              </div>
            {/if}
          </article>
        {/key}

        <footer>
          <span class="dots" aria-label="Progress">
            {#each items as i (i.key)}<i class:done={decided(i)} class:now={i.key === current.key}></i>{/each}
          </span>
          {#if undo}<span class="undone">{undo.said} <button onclick={takeBack}>Undo</button></span>{/if}
          <button class="back" onclick={back} disabled={items[0].key === current.key}><Icon name="undo" size={14} />Back <kbd>←</kbd></button>
        </footer>
      </div>

      <aside class="right" aria-label="Who you want to meet">
        {#if settled.roles.length}<h3>You want to meet</h3>{/if}
        {#each settled.roles as n (n.id)}
          <button class="line" onclick={() => (opened = `role:${n.id}`)} in:receive={{ key: `role:${n.id}` }} out:send={{ key: `role:${n.id}` }} animate:flip={{ duration: 300 }}>
            <b>{n.title}</b>
            <span>{terms(n).join(' · ')}</span>
            {#if open(n)}<span class="todo">{open(n)} still to answer</span>{/if}
            {#each n.can_do ?? [] as task}<span class="more task">{task}</span>{/each}
          </button>
        {/each}
      </aside>
    </div>
  {/if}
</div>

<style>
  .join {
    position: relative;
    min-height: 100dvh;
    padding: 0 clamp(1rem, 3vw, 2.5rem) var(--s7);
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
    color: color-mix(in oklch, var(--brand-ink) 80%, var(--brand));
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
    max-width: 40ch;
    margin-top: var(--s4);
    font-size: clamp(1.125rem, 1rem + 0.5vw, 1.375rem);
    line-height: 1.35;
  }

  /* three columns: who you are, the card, who you want to meet */
  .bench {
    display: grid;
    grid-template-columns: minmax(12rem, 1fr) minmax(0, 36rem) minmax(12rem, 1fr);
    align-items: start;
    gap: clamp(1rem, 2.5vw, 2.5rem);
    max-width: 88rem;
    margin: clamp(0.5rem, 4vh, 3rem) auto 0;
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
    color: color-mix(in oklch, var(--brand-ink) 78%, var(--brand));
    animation: fade 0.4s;
  }
  /* a settled answer: written straight on the colour, so the card stays the only bright surface */
  .line {
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
    color: color-mix(in oklch, var(--brand-ink) 84%, var(--brand));
  }
  .line .clamp {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    font-size: var(--t-md);
    color: var(--brand-ink);
  }
  .line:hover .clamp,
  .line:focus-visible .clamp {
    -webkit-line-clamp: unset;
    line-clamp: unset;
  }
  /* more of a settled answer shows on hover or focus */
  .line .more {
    max-height: 0;
    overflow: hidden;
    opacity: 0;
    transition: max-height 0.3s var(--ease), opacity 0.2s;
  }
  .line:hover .more,
  .line:focus-visible .more {
    max-height: 6rem;
    opacity: 1;
  }
  .line .task::before {
    content: '· ';
  }
  .line .todo {
    font-weight: 700;
    color: var(--brand-ink);
  }
  .undone button {
    padding: 0 var(--s1);
    border: 0;
    background: none;
    color: inherit;
    font-weight: 700;
    text-decoration: underline;
    text-underline-offset: 0.2em;
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
    align-content: start;
  }
  .centre > * {
    grid-column: 1;
  }
  .card {
    grid-row: 1;
    display: flex;
    flex-direction: column;
    min-height: 21rem;
    padding: clamp(1.25rem, 3vw, 2.25rem);
    border-radius: 1.25rem;
    background: var(--ground);
    color: var(--ink);
    box-shadow: var(--lift);
  }
  .card :focus-visible {
    outline-color: var(--ink);
  }
  .band {
    height: clamp(6rem, 16vh, 9rem);
    margin-bottom: var(--s5);
    padding: var(--s5) 20%;
    border-radius: var(--r2);
    background: var(--wash);
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
  h2.claim {
    font-weight: 700;
    line-height: 1.15;
    text-wrap: pretty;
  }
  h2.in {
    font-size: var(--t-2xl);
  }
  .pitch {
    margin-top: var(--s2);
    font-size: var(--t-lg);
    line-height: 1.35;
    color: var(--ink-2);
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s2);
    margin-top: var(--s4);
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
    transition: border-color 0.15s, background 0.15s;
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
    transition: box-shadow 0.12s, background 0.12s;
  }
  [contenteditable]:hover {
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

  /* the two answers under every card, with the key that gives each */
  .actions {
    position: sticky;
    bottom: 0;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--s3);
    margin: auto calc(-1 * clamp(1.25rem, 3vw, 2.25rem)) calc(-1 * clamp(1.25rem, 3vw, 2.25rem));
    padding: var(--s4) clamp(1.25rem, 3vw, 2.25rem);
    border-radius: 0 0 1.25rem 1.25rem;
    background: var(--ground);
    box-shadow: 0 -1px 0 var(--line);
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

  footer {
    grid-row: 2;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--s4);
    padding: var(--s4) var(--s2) 0;
    font-size: var(--t-sm);
  }
  .dots {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }
  .dots i {
    width: 0.5rem;
    height: 0.5rem;
    border: 1.5px solid currentColor;
    border-radius: 50%;
    opacity: 0.45;
    transition: opacity 0.3s, background 0.3s, scale 0.3s var(--ease);
  }
  .dots i.done {
    background: currentColor;
    opacity: 0.9;
  }
  .dots i.now {
    opacity: 1;
    scale: 1.5;
  }
  .back {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    padding: var(--s1) var(--s2);
    border: 0;
    border-radius: var(--r1);
    background: none;
    color: inherit;
    font-weight: 600;
  }
  .back:disabled {
    visibility: hidden;
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
  /* narrow screens: the card first, then the page that is building under it */
  @media (max-width: 62rem) {
    .bench {
      grid-template-columns: minmax(0, 1fr);
    }
    .centre {
      order: -1;
    }
    aside {
      position: static;
    }
    .line .more {
      max-height: none;
      opacity: 1;
    }
    kbd {
      display: none;
    }
  }
</style>
