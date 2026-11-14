<script lang="ts">
  import Cite from './Cite.svelte'
  import { text } from './editable'
  import { host, terms, when } from './format'
  import Icon from './Icon.svelte'
  import Logo from './Logo.svelte'
  import { app, nameOf, reviewOf, saveReview } from './state.svelte'
  import type { Brief, Need, Posting, Review } from './types'

  // The company's sign-up for an event, already filled in from what it has said in public. Four
  // short steps: is this you, what we would say about you, who you want to meet, and you are in.
  let { brief }: { brief: Brief } = $props()
  const review = $derived(reviewOf(brief))
  const name = $derived(nameOf(brief))
  const event = $derived(app.presets.find((p) => p.ids.includes(brief.id)) ?? app.presets[0])
  const STEPS = ['You', 'Your news', 'Who you want', 'Done']
  let step = $state(-1) // -1 is the invitation itself
  let opened = $state('')
  // a company that already signed up lands on its finished page
  $effect(() => {
    if (opened !== brief.id) [opened, step] = [brief.id, reviewOf(brief).status === 'joined' ? 3 : -1]
  })

  const save = (patch: Partial<Review>) => saveReview(brief.id, { ...review, ...patch })

  // step 1: who they are, from the brand record, each line theirs to correct
  const identity = $derived(brief.identity)
  const about = $derived(
    (
      [
        ['Company', name],
        ['Website', host(brief.website)],
        ['What you do', brief.card.pitch || identity?.slogan || ''],
        ['Field', identity?.industries[0]?.split(': ').pop() ?? ''],
        ['People', identity?.employees?.replace(' to ', '–') ?? ''],
        ['Based in', [identity?.city, identity?.country].filter(Boolean).join(', ')],
      ] as [string, string][]
    ).map(([label, found]) => ({ label, found, value: review.about?.[label] ?? found })),
  )
  const fix = (label: string, e: FocusEvent) => {
    const value = (e.currentTarget as HTMLElement).innerText.replace(/\s+/g, ' ').trim()
    if (value !== (review.about?.[label] ?? about.find((a) => a.label === label)?.found)) save({ about: { ...review.about, [label]: value } })
  }

  // step 2: the few statements worth telling talent, the kinds they care about first and the newest first
  const WEIGHT = ['funding', 'growth', 'customers', 'product', 'partnership', 'technology', 'hiring']
  const news = $derived(
    brief.signals
      .filter((s) => WEIGHT.includes(s.type))
      .sort((a, b) => WEIGHT.indexOf(a.type) - WEIGHT.indexOf(b.type) || b.date.localeCompare(a.date))
      .slice(0, 4),
  )
  const kept = (id: string) => review.facts?.[id] !== false
  const keep = (id: string) => save({ facts: { ...review.facts, [id]: !kept(id) } })
  let quoted = $state<string | null>(null)

  // step 3: the roles, to tick, reword and extend
  const number = (id: string) => brief.signals.findIndex((s) => s.id === id) + 1
  const needs = (change: (list: Need[]) => Need[]) => save({ needs: change(review.needs) })
  const patch = (i: number, p: Partial<Need>) => needs((list) => list.map((n, j) => (j === i ? { ...n, ...p } : n)))
  const reword = (i: number, key: 'title' | 'why', e: FocusEvent) => {
    const value = (e.currentTarget as HTMLElement).innerText.replace(/\s+/g, ' ').trim()
    if (value !== review.needs[i][key]) patch(i, { [key]: value, by: 'company' })
  }
  // what a role asks for beyond its title: each a few fixed choices, prefilled where a job post says it
  const ASKS: { key: 'seniority' | 'language' | 'workplace' | 'abroad'; label: string; options: [string | boolean, string][] }[] = [
    { key: 'seniority', label: 'Level', options: ['Early career', 'Experienced', 'Senior', 'Lead'].map((x) => [x, x]) },
    { key: 'language', label: 'Working language', options: [['English is enough', 'English is enough'], ['Finnish needed', 'Finnish needed']] },
    { key: 'workplace', label: 'Where', options: ['On site', 'Hybrid', 'Remote'].map((x) => [x, x]) },
    { key: 'abroad', label: 'Hiring from abroad', options: [[true, 'Yes'], [false, 'Only people already in Finland']] },
  ]
  const answer = (i: number, key: string, value: string | boolean) => patch(i, { [key]: value, by: review.needs[i].by })
  const dropTask = (i: number, task: string) => patch(i, { can_do: review.needs[i].can_do.filter((t) => t !== task) })
  const editTask = (i: number, j: number, e: FocusEvent) => {
    const value = (e.currentTarget as HTMLElement).innerText.replace(/\s+/g, ' ').trim()
    const tasks = review.needs[i].can_do.map((t, k) => (k === j ? value : t)).filter(Boolean)
    if (tasks.join('|') !== review.needs[i].can_do.join('|')) patch(i, { can_do: tasks })
  }
  const addTask = (i: number) => patch(i, { can_do: [...(review.needs[i].can_do ?? []), ''] })
  const dropSkill = (i: number, skill: string) => patch(i, { skills: review.needs[i].skills.filter((s) => s !== skill) })
  function addSkill(i: number, e: KeyboardEvent) {
    const input = e.currentTarget as HTMLInputElement
    if (e.key !== 'Enter' || !input.value.trim()) return
    patch(i, { skills: [...review.needs[i].skills, input.value.trim()] })
    input.value = ''
  }
  const addNeed = () =>
    needs((list) => [...list, { title: '', why: '', can_do: [], skills: [], seniority: 'Experienced', signals: [], roles: [], by: 'company' }])
  const WANTS = ['1:1 meetings with candidates', 'A virtual booth', 'A company presentation']
  const wants = $derived(review.wants ?? [WANTS[0]])
  const want = (w: string) => save({ wants: wants.includes(w) ? wants.filter((x) => x !== w) : [...wants, w] })
  const chosen = $derived(review.needs.filter((n) => !n.off && n.title.trim()))
  const join = () => {
    save({ status: 'joined', joined_at: new Date().toISOString(), wants, needs: review.needs.filter((n) => n.title.trim()) })
    step = 3
  }
  const enter = (e: KeyboardEvent) => e.key === 'Enter' && (e.preventDefault(), (e.currentTarget as HTMLElement).blur())

  // step 4: a posting drafted per role, on request
  let postings = $state<Record<string, Posting | 'drafting' | 'failed'>>({})
  async function draft(need: Need) {
    postings[need.title] = 'drafting'
    const r = await fetch(`posting?id=${encodeURIComponent(brief.id)}`, { method: 'POST', body: JSON.stringify(need) }).catch(() => null)
    postings[need.title] = r?.ok ? await r.json() : 'failed'
  }
</script>

<div class="join" class:cover={step < 0}>
  <header>
    <span class="host">City of Espoo</span>
    <span class="event">{event?.title}{event ? `, ${event.note.split(',')[0]}` : ''}</span>
    {#if step >= 0}
      <ol class="steps" aria-label="Steps">
        {#each STEPS as label, i}
          <li class:done={i < step} class:now={i === step}>
            <button disabled={i > step || review.status === 'joined'} onclick={() => (step = i)}>{label}</button>
          </li>
        {/each}
      </ol>
    {/if}
  </header>

  {#key `${brief.id}:${step}`}
    {#if step < 0}
      <section class="invite">
        <div class="plate" class:dark={identity?.logo_on === 'dark'}><Logo {brief} /></div>
        <h1>
          {#each `${name}, you're invited.`.split(' ') as word, i}<span style:--i={i}>{word}&nbsp;</span>{/each}
        </h1>
        <p class="lead" style:--i={5}>
          {event?.title}, {event?.note.split(',')[0]}, online. International deep-tech professionals meet Finnish employers.
        </p>
        <p class="lead small" style:--i={6}>Your sign-up is already filled in from what {name} has said in public. Check it and you are in. It takes about a minute.</p>
        <button class="go" style:--i={7} onclick={() => (step = 0)}>Check my sign-up<Icon name="flat" size={20} /></button>
      </section>
    {:else if step === 0}
      <section>
        <h2>Is this you?</h2>
        <p class="lead">Read from your own site. Click a line to fix it.</p>
        <dl class="sheet">
          {#each about as row, i (row.label)}
            <div style:--i={i}>
              <dt>{row.label}</dt>
              <dd role="textbox" tabindex="0" aria-label={row.label} contenteditable="plaintext-only" spellcheck="false" data-placeholder="Add" onblur={(e) => fix(row.label, e)} onkeydown={enter} use:text={row.value}></dd>
              {#if row.value !== row.found}<span class="tag">Changed by you</span>{/if}
            </div>
          {/each}
        </dl>
        <button class="go" onclick={() => (step = 1)}>That's us<Icon name="flat" size={20} /></button>
      </section>
    {:else if step === 1}
      <section>
        <h2>What we'd tell talent about you</h2>
        <p class="lead">Each line is quoted from a public page. Untick anything we should leave out.</p>
        <ul class="sheet picks">
          {#each news as s, i (s.id)}
            <li class:on={kept(s.id)} style:--i={i}>
              <button class="tick" role="checkbox" aria-checked={kept(s.id)} aria-label="Tell talent this" onclick={() => keep(s.id)}>
                <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4.5 10.5 8.5 14.5 15.5 6" /></svg>
              </button>
              <div>
                <p class="claim">{s.claim}</p>
                <p class="source">
                  <a href={s.source_url} target="_blank" rel="noopener">{host(s.source_url)}</a>{s.date ? `, ${when(s.date)}` : ''}
                  <button class="link" onclick={() => (quoted = quoted === s.id ? null : s.id)}>{quoted === s.id ? 'Hide the sentence' : 'Show the sentence'}</button>
                </p>
                {#if quoted === s.id}<q>{s.quote}</q>{/if}
              </div>
            </li>
          {:else}
            <li class="none">We found little about {name} in public this year. That is fine: tell us who you want to meet on the next step.</li>
          {/each}
        </ul>
        <button class="go" onclick={() => (step = 2)}>Next<Icon name="flat" size={20} /></button>
      </section>
    {:else if step === 2}
      <section>
        <h2>Who do you want to meet?</h2>
        <p class="lead">Drafted from your news and open roles, including ones you may not have posted yet. Tick the ones that are right, and reword freely.</p>
        <ul class="roles">
          {#each review.needs as need, i (i)}
            <li class:on={!need.off} style:--i={i}>
              <button class="tick" role="checkbox" aria-checked={!need.off} aria-label="We want to meet these people" onclick={() => patch(i, { off: !need.off })}>
                <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4.5 10.5 8.5 14.5 15.5 6" /></svg>
              </button>
              <div class="role">
                <h3 role="textbox" tabindex="0" aria-label="Role" contenteditable="plaintext-only" spellcheck="false" data-placeholder="Who are you looking for?" onblur={(e) => reword(i, 'title', e)} onkeydown={enter} use:text={need.title}></h3>
                <p class="why">
                  <span role="textbox" tabindex="0" aria-label="Why" contenteditable="plaintext-only" data-placeholder="Why now? One line." onblur={(e) => reword(i, 'why', e)} onkeydown={enter} use:text={need.why}></span><span class="cites">{#each need.signals.filter(number) as id}<Cite signal={brief.signals[number(id) - 1]} n={number(id)} />{/each}</span>
                </p>
                {#if need.roles.length}<p class="open">Open now: {need.roles.join(', ')}</p>{/if}
                {#if !need.off}
                  <dl class="asks">
                    <div>
                      <dt>Can do</dt>
                      <dd>
                        <ul class="tasks">
                          {#each need.can_do ?? [] as task, j (j)}
                            <li>
                              <span role="textbox" tabindex="0" aria-label="Something they must be able to do" contenteditable="plaintext-only" data-placeholder="Something they must be able to do" onblur={(e) => editTask(i, j, e)} onkeydown={enter} use:text={task}></span>
                              <button aria-label="Remove this" onclick={() => dropTask(i, task)}><Icon name="x" size={14} /></button>
                            </li>
                          {/each}
                        </ul>
                        {#if (need.can_do ?? []).length < 4}<button class="more" onclick={() => addTask(i)}><Icon name="plus" size={14} />Add</button>{/if}
                      </dd>
                    </div>
                    <div>
                      <dt>Knows</dt>
                      <dd class="chips">
                        {#each need.skills as skill (skill)}
                          <span class="chip">{skill}<button aria-label="Remove {skill}" onclick={() => dropSkill(i, skill)}><Icon name="x" size={12} /></button></span>
                        {/each}
                        <input class="chip" placeholder="Add" aria-label="Add something they know" onkeydown={(e) => addSkill(i, e)} />
                      </dd>
                    </div>
                    {#each ASKS as ask (ask.key)}
                      <div>
                        <dt>{ask.label}</dt>
                        <dd>
                          <span class="seg" role="radiogroup" aria-label={ask.label}>
                            {#each ask.options as [value, label]}
                              <button role="radio" aria-checked={need[ask.key] === value} onclick={() => answer(i, ask.key, value)}>{label}</button>
                            {/each}
                          </span>
                          {#if ask.key === 'workplace' && need.where}<span class="place">{need.where}</span>{/if}
                          {#if need.sources?.[ask.key]}
                            <span class="read" title={`“${need.sources[ask.key].quote}”`}>from your job post</span>
                          {:else if need[ask.key] == null}
                            <span class="yours">your call</span>
                          {/if}
                        </dd>
                      </div>
                    {/each}
                  </dl>
                {/if}
              </div>
            </li>
          {/each}
        </ul>
        <button class="add" onclick={addNeed}><Icon name="plus" size={18} />Add someone we missed</button>

        <h2 class="second">At the event we would like</h2>
        <p class="chips wants">
          {#each WANTS as w}
            <button class="chip want" aria-pressed={wants.includes(w)} onclick={() => want(w)}>{#if wants.includes(w)}<Icon name="check" size={14} />{/if}{w}</button>
          {/each}
        </p>
        <button class="go" disabled={!chosen.length} onclick={join}><Icon name="check" size={20} />Sign {name} up</button>
        {#if !chosen.length}<p class="hint">Tick at least one kind of person to meet.</p>{/if}
      </section>
    {:else}
      <section class="done">
        <h2>You're in.</h2>
        <p class="lead">This is how talent will see {name} at the forum. Espoo has it too.</p>
        <article class="card">
          <div class="mark" class:dark={identity?.logo_on === 'dark'}><Logo {brief} /></div>
          <h3 style:--i={1}>{review.about?.Company ?? name}</h3>
          <p class="pitch" style:--i={2}>{review.about?.['What you do'] ?? (brief.card.pitch || identity?.slogan)}</p>
          {#if news.some((s) => kept(s.id))}
            <ul class="facts" style:--i={3}>
              {#each news.filter((s) => kept(s.id)) as s (s.id)}<li>{s.claim}</li>{/each}
            </ul>
          {/if}
          <p class="label" style:--i={4}>Wants to meet</p>
          <ul class="meet">
            {#each chosen as need, i (need.title)}
              <li style:--i={5 + i}>
                <div class="line">
                  <b>{need.title}</b>
                  <button class="link" disabled={postings[need.title] === 'drafting'} onclick={() => draft(need)}>
                    {postings[need.title] === 'drafting' ? 'Drafting…' : typeof postings[need.title] === 'object' ? 'Draft again' : 'Draft a job posting'}
                  </button>
                </div>
                <p class="terms">{terms(need).join(' · ')}</p>
                {#if need.can_do?.length}<ul class="can">{#each need.can_do as task}<li>{task}</li>{/each}</ul>{/if}
                <p class="chips">{#each need.skills as skill}<span class="chip">{skill}</span>{/each}</p>
                {#if postings[need.title] === 'failed'}
                  <p class="hint">The draft did not come through. Try again in a minute.</p>
                {:else if typeof postings[need.title] === 'object'}
                  {@const p = postings[need.title] as Posting}
                  <div class="posting">
                    <h4>{p.headline}</h4>
                    <p>{p.intro}</p>
                    <p class="label">You will</p>
                    <ul>{#each p.you_will as line}<li>{line}</li>{/each}</ul>
                    <p class="label">You bring</p>
                    <ul>{#each p.you_bring as line}<li>{line}</li>{/each}</ul>
                    <p class="now">{p.why_now}</p>
                    <p class="hint">A draft from your public statements. Edit it before you use it.</p>
                  </div>
                {/if}
              </li>
            {/each}
          </ul>
          <p class="asked" style:--i={9}>Asked for: {(review.wants ?? []).join(', ').toLowerCase() || 'nothing extra'}</p>
        </article>
        <button class="back" onclick={() => (save({ status: 'invited' }), (step = 2))}><Icon name="undo" size={16} />Change my answers</button>
      </section>
    {/if}
  {/key}
</div>

<style>
  .join {
    position: relative;
    min-height: 100dvh;
    padding: 0 clamp(1.25rem, 5vw, 5rem) var(--s8);
    background: var(--brand);
    color: var(--brand-ink);
    overflow: hidden;
  }
  /* the invitation opens on the logo's own ground, and the company's colour floods in from the logo */
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
  header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--s2) var(--s4);
    padding: var(--s4) 0;
    font-size: var(--t-sm);
  }
  .cover header {
    animation: fade 0.6s 1.1s backwards;
  }
  .host {
    font-weight: 700;
  }
  .event {
    color: color-mix(in oklch, var(--brand-ink) 80%, var(--brand));
  }
  .steps {
    display: flex;
    gap: var(--s1);
    margin-left: auto;
  }
  .steps button {
    padding: var(--s1) var(--s3);
    border: 0;
    border-bottom: 3px solid color-mix(in oklch, var(--brand-ink) 28%, transparent);
    background: none;
    color: color-mix(in oklch, var(--brand-ink) 70%, var(--brand));
    font-size: var(--t-sm);
    font-weight: 600;
    transition: border-color 0.4s, color 0.3s;
  }
  .steps button:disabled {
    cursor: default;
  }
  .steps .done button,
  .steps .now button {
    border-color: var(--brand-ink);
    color: var(--brand-ink);
  }

  section {
    max-width: 52rem;
    margin: clamp(1.5rem, 6vh, 4rem) auto 0;
  }
  h1,
  h2 {
    font-weight: 800;
    letter-spacing: -0.035em;
  }
  h1 {
    margin-top: var(--s6);
    font-size: clamp(2.75rem, 1.4rem + 5.6vw, 6rem);
    line-height: 0.95;
  }
  h1 span {
    display: inline-block;
    animation: rise 0.8s var(--ease) backwards;
    animation-delay: calc(var(--i) * 80ms + 0.9s);
  }
  h2 {
    font-size: clamp(2rem, 1.3rem + 2.8vw, 3.5rem);
    line-height: 1;
    animation: rise 0.6s var(--ease) backwards;
  }
  h2.second {
    margin-top: var(--s7);
    font-size: var(--t-xl);
    animation: none;
  }
  .lead {
    max-width: 44ch;
    margin: var(--s3) 0 var(--s5);
    font-size: var(--t-lg);
    line-height: 1.35;
    color: color-mix(in oklch, var(--brand-ink) 88%, var(--brand));
    animation: rise 0.6s var(--ease) 60ms backwards;
  }
  .invite .lead {
    margin: var(--s4) 0 0;
    font-size: clamp(1.1875rem, 1rem + 0.7vw, 1.5rem);
    color: var(--brand-ink);
    animation-delay: calc(var(--i) * 80ms + 0.9s);
  }
  .invite .lead.small {
    font-size: var(--t-lg);
    color: color-mix(in oklch, var(--brand-ink) 86%, var(--brand));
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
  .plate.dark {
    background: #14151a;
  }
  .plate :global(.logo) {
    background: none;
  }

  /* the one button that moves the sign-up on: ink on the company's colour, reversed */
  .go {
    display: inline-flex;
    align-items: center;
    gap: var(--s3);
    min-height: 3.5rem;
    margin-top: var(--s6);
    padding: 0 var(--s6);
    border: 0;
    border-radius: 99px;
    background: var(--brand-ink);
    color: var(--brand);
    font-size: var(--t-lg);
    font-weight: 700;
    animation: rise 0.6s var(--ease) 0.25s backwards;
    transition: transform 0.2s var(--ease), box-shadow 0.2s;
  }
  .invite .go {
    animation-delay: calc(var(--i) * 80ms + 0.9s);
  }
  .go:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 10px 24px -8px rgb(0 0 0 / 0.45);
  }
  .go:hover:not(:disabled) :global(svg) {
    translate: 4px 0;
  }
  .go :global(svg) {
    transition: translate 0.2s var(--ease);
  }
  .go:disabled {
    opacity: 0.45;
    cursor: default;
  }
  .hint {
    margin-top: var(--s2);
    font-size: var(--t-sm);
    opacity: 0.85;
  }

  /* answers sit on white sheets, so they read the same on any company colour */
  .sheet,
  .roles > li,
  .card {
    border-radius: var(--r2);
    background: var(--ground);
    color: var(--ink);
    box-shadow: var(--lift);
  }
  .sheet {
    padding: var(--s2) var(--s5);
  }
  .sheet > * {
    animation: rise 0.55s var(--ease) backwards;
    animation-delay: calc(var(--i) * 70ms + 0.15s);
  }
  dl div {
    display: grid;
    grid-template-columns: 8rem 1fr auto;
    align-items: baseline;
    gap: var(--s4);
    padding: var(--s3) 0;
  }
  dl div + div,
  .picks li + li {
    border-top: 1px solid var(--line);
  }
  dt {
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  dd {
    font-size: var(--t-lg);
    font-weight: 600;
  }
  .tag {
    padding: 0.1rem var(--s2);
    border-radius: var(--r1);
    background: var(--wash);
    font-size: var(--t-xs);
    color: var(--ink-2);
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

  .picks li,
  .roles > li {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: var(--s4);
  }
  .picks li {
    padding: var(--s4) 0;
    transition: opacity 0.3s;
  }
  .picks li:not(.on) .claim {
    text-decoration: line-through;
    color: var(--ink-2);
  }
  .picks .none {
    display: block;
    color: var(--ink-2);
  }
  .claim {
    font-size: var(--t-lg);
    line-height: 1.3;
    text-wrap: pretty;
  }
  .source {
    margin-top: var(--s1);
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  .link {
    margin-left: var(--s2);
    padding: 0;
    border: 0;
    background: none;
    color: var(--ink);
    font-size: var(--t-sm);
    font-weight: 600;
    text-decoration: underline;
    text-underline-offset: 0.2em;
  }
  .link:disabled {
    opacity: 0.6;
  }
  q {
    display: block;
    margin-top: var(--s2);
    padding: var(--s3) var(--s4);
    border-radius: var(--r1);
    background: var(--wash);
    quotes: '“' '”';
    animation: rise 0.3s var(--ease);
  }

  /* the tick draws itself, and its box takes the company's colour */
  .tick {
    display: grid;
    place-items: center;
    flex: none;
    width: 2rem;
    height: 2rem;
    margin-top: 0.15rem;
    border: 2px solid var(--line);
    border-radius: 8px;
    background: var(--ground);
    transition: background 0.25s, border-color 0.25s, scale 0.25s var(--ease);
  }
  .tick:hover {
    border-color: var(--ink-2);
  }
  .tick:active {
    scale: 0.9;
  }
  .tick svg {
    width: 1.25rem;
    fill: none;
    stroke: var(--brand-ink);
    stroke-width: 2.4;
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

  .roles {
    display: grid;
    gap: var(--s3);
  }
  .roles > li {
    position: relative;
    padding: var(--s5);
    overflow: hidden;
    animation: rise 0.6s var(--ease) backwards;
    animation-delay: calc(var(--i) * 90ms + 0.15s);
    transition: opacity 0.3s, box-shadow 0.3s;
  }
  .roles > li::before {
    content: '';
    position: absolute;
    inset: 0;
    background: color-mix(in srgb, var(--brand) 8%, #fff);
    transform-origin: left;
    scale: 0 1;
    transition: scale 0.5s var(--ease);
  }
  .roles > li.on::before {
    scale: 1 1;
  }
  .roles > li > * {
    position: relative;
  }
  .roles > li:not(.on) {
    box-shadow: none;
    opacity: 0.78;
  }
  .role h3 {
    font-size: var(--t-xl);
    line-height: 1.1;
  }
  .why {
    margin-top: var(--s2);
    max-width: 60ch;
    color: var(--ink-2);
  }
  .cites {
    white-space: nowrap;
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
    gap: var(--s1);
    min-height: 1.75rem;
    padding: 0 var(--s3);
    border: 1px solid var(--line);
    border-radius: 99px;
    background: var(--ground);
    color: var(--ink);
    font-size: var(--t-sm);
  }
  .chip button {
    display: grid;
    place-items: center;
    margin-right: -0.35rem;
    padding: 0.15rem;
    border: 0;
    border-radius: 50%;
    background: none;
    color: var(--ink-2);
  }
  .chip button:hover {
    background: var(--wash);
    color: var(--stop);
  }
  .chip.level {
    border-color: var(--ink);
    font-weight: 600;
  }
  input.chip {
    width: 8rem;
    border-style: dashed;
    outline: none;
  }
  input.chip:focus {
    border-color: var(--ink);
    border-style: solid;
  }
  .open {
    margin-top: var(--s3);
    font-size: var(--t-sm);
    font-weight: 600;
    color: var(--ok);
  }
  /* what the role asks for: a label column and its answer, one row each */
  .asks {
    display: grid;
    gap: var(--s3);
    margin-top: var(--s4);
    padding-top: var(--s4);
    border-top: 1px solid color-mix(in srgb, var(--ink) 12%, transparent);
  }
  .asks > div {
    display: grid;
    grid-template-columns: 9.5rem 1fr;
    align-items: baseline;
    gap: var(--s3);
    padding: 0;
    border: 0;
  }
  .asks dt {
    font-size: var(--t-sm);
    font-weight: 600;
    color: var(--ink-2);
  }
  .asks dd {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--s2) var(--s3);
    margin: 0;
    font-size: var(--t-md);
    font-weight: 400;
  }
  .asks .chips {
    margin-top: 0;
  }
  .tasks {
    display: grid;
    gap: var(--s1);
    width: 100%;
  }
  .tasks li {
    display: flex;
    align-items: baseline;
    gap: var(--s2);
  }
  .tasks li::before {
    content: '';
    flex: none;
    width: 0.375rem;
    height: 0.375rem;
    translate: 0 -0.15rem;
    border-radius: 50%;
    background: var(--brand);
  }
  .tasks button,
  .more {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    padding: 0.15rem;
    border: 0;
    border-radius: var(--r1);
    background: none;
    color: var(--ink-2);
    font-size: var(--t-sm);
    font-weight: 600;
  }
  .tasks button {
    opacity: 0;
    transition: opacity 0.12s;
  }
  .tasks li:hover button,
  .tasks button:focus-visible {
    opacity: 1;
  }
  .tasks button:hover {
    color: var(--stop);
  }
  .more:hover {
    color: var(--ink);
  }
  .seg {
    display: inline-flex;
    border: 1px solid var(--line);
    border-radius: 99px;
    background: var(--ground);
    overflow: hidden;
  }
  .seg button {
    min-height: 2rem;
    padding: 0 var(--s3);
    border: 0;
    background: none;
    color: var(--ink-2);
    font-size: var(--t-sm);
    font-weight: 600;
    transition: background 0.2s, color 0.2s;
  }
  .seg button + button {
    border-left: 1px solid var(--line);
  }
  .seg button:hover {
    color: var(--ink);
  }
  .seg button[aria-checked='true'] {
    background: var(--ink);
    color: var(--ground);
  }
  .place {
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  .read,
  .yours {
    font-size: var(--t-xs);
    color: var(--ink-2);
  }
  .read {
    text-decoration: underline dotted;
    text-underline-offset: 0.2em;
    cursor: help;
  }
  .yours {
    padding: 0.05rem var(--s2);
    border-radius: 99px;
    background: color-mix(in srgb, var(--brand) 16%, #fff);
    color: var(--ink);
    font-weight: 600;
  }
  .add,
  .back {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    margin-top: var(--s4);
    padding: var(--s2) var(--s3);
    border: 1px dashed color-mix(in oklch, var(--brand-ink) 55%, transparent);
    border-radius: 99px;
    background: none;
    color: var(--brand-ink);
    font-weight: 600;
  }
  .add:hover,
  .back:hover {
    border-style: solid;
  }
  .wants {
    margin-top: var(--s4);
  }
  .want {
    min-height: 2.5rem;
    padding: 0 var(--s4);
    border-color: color-mix(in oklch, var(--brand-ink) 45%, transparent);
    background: none;
    color: var(--brand-ink);
    font-size: var(--t-md);
    font-weight: 600;
    transition: background 0.2s, color 0.2s;
  }
  .want[aria-pressed='true'] {
    border-color: var(--brand-ink);
    background: var(--brand-ink);
    color: var(--brand);
  }

  /* the finished card puts itself together from what was just confirmed */
  .card {
    padding: var(--s6);
  }
  .card > *,
  .meet li {
    animation: rise 0.6s var(--ease) backwards;
    animation-delay: calc(var(--i, 0) * 110ms + 0.2s);
  }
  .mark {
    width: 11rem;
    height: 4.5rem;
    padding: var(--s3);
    border-radius: var(--r1);
    animation-name: land;
  }
  .mark.dark {
    background: #14151a;
  }
  .mark :global(.logo) {
    background: none;
  }
  .card h3 {
    margin-top: var(--s4);
    font-size: var(--t-2xl);
    font-weight: 800;
    letter-spacing: -0.035em;
  }
  .pitch {
    max-width: 52ch;
    margin-top: var(--s2);
    font-size: var(--t-lg);
    line-height: 1.35;
  }
  .facts {
    display: grid;
    gap: var(--s2);
    margin-top: var(--s4);
    padding-left: var(--s4);
    list-style: disc;
    color: var(--ink-2);
  }
  .label {
    margin-top: var(--s5);
    font-size: var(--t-sm);
    font-weight: 700;
    color: var(--ink-2);
  }
  .meet li {
    padding: var(--s4) 0;
    border-top: 1px solid var(--line);
  }
  .meet li:first-child {
    margin-top: var(--s2);
  }
  .line {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--s2) var(--s4);
  }
  .line b {
    font: 700 var(--t-xl) / 1.1 var(--display);
    letter-spacing: -0.025em;
  }
  .terms {
    margin-top: var(--s1);
    color: var(--ink-2);
  }
  .can {
    margin-top: var(--s3);
    padding-left: var(--s4);
    list-style: disc;
  }
  .line .link {
    margin-left: auto;
  }
  .posting {
    margin-top: var(--s4);
    padding: var(--s5);
    border-radius: var(--r1);
    background: var(--wash);
    animation: rise 0.5s var(--ease);
  }
  .posting h4 {
    margin: 0 0 var(--s2);
    font: 700 var(--t-lg) / 1.2 var(--display);
  }
  .posting ul {
    padding-left: var(--s4);
    list-style: disc;
  }
  .posting .label {
    margin-top: var(--s3);
  }
  .posting .now {
    margin-top: var(--s3);
    font-weight: 600;
  }
  .posting .hint,
  .card .hint {
    color: var(--ink-2);
  }
  .asked {
    margin-top: var(--s4);
    padding-top: var(--s4);
    border-top: 1px solid var(--line);
    font-size: var(--t-sm);
    color: var(--ink-2);
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
  @media (max-width: 640px) {
    .steps {
      width: 100%;
      margin-left: 0;
    }
    .steps li {
      flex: 1;
    }
    .steps button {
      width: 100%;
      padding-inline: 0;
      font-size: var(--t-xs);
    }
    dl div,
    .asks > div {
      grid-template-columns: 1fr;
      gap: var(--s1);
    }
    .tasks button {
      opacity: 1;
    }
    .roles > li {
      padding: var(--s4);
      gap: var(--s3);
    }
    .card {
      padding: var(--s5);
    }
    .line .link {
      margin-left: 0;
    }
  }
</style>
