<script lang="ts">
  import { some, type Plan } from './events'
  import { concerns, fitCompany, rank, type Fit } from './fit'
  import { when } from './format'
  import Icon from './Icon.svelte'
  import Logo from './Logo.svelte'
  import { applications, decide, decisionOf, manage, undecide } from './manage.svelte'
  import { app, copyText, nameOf } from './state.svelte'
  import Tabs from './Tabs.svelte'
  import type { Applicant } from './types'

  // The applications that came back from the regular invitation, one at a time, as a one-page summary with two kinds
  // of lines kept apart: what the pipeline drafted from the applicant's sources (the AI summary) and what the applicant
  // explicitly answered, corrected or wrote. Espoo's view analyses fit against the whole event and the pool; a
  // company's view, reached by its own link, shows only the applications that concern it and fit against its roles.
  let { plan, company = '' }: { plan: Plan; company?: string } = $props()
  const brief = $derived(company ? app.briefs.find((b) => b.id === company) : undefined)
  const by = $derived(brief ? brief.id : 'espoo')
  const list = $derived(brief ? applications.list.filter((a) => concerns(a, brief)) : applications.list)
  const counts = $derived({
    accepted: list.filter((a) => decisionOf(by, a.id)?.d === 'accept').length,
    declined: list.filter((a) => decisionOf(by, a.id)?.d === 'decline').length,
  })
  let openId = $state('')
  let reason = $state('')
  let pick = $state<'accept' | 'decline' | ''>('')
  let copied = $state('')
  let linkFor = $state('')
  let error = $state('')
  const current = $derived(list.find((a) => a.id === openId) ?? list.find((a) => !decisionOf(by, a.id)) ?? list[0])
  const decision = $derived(current ? decisionOf(by, current.id) : undefined)
  // fit: Espoo sees the closest employers of the event; a company sees each of its roles
  const fits = $derived<Fit[]>(current ? (brief ? fitCompany(current, brief) : rank(current, plan.employers).slice(0, 4)) : [])
  const field = $derived(current ? plan.fields.find((f) => f.name === current.field) : undefined)
  const bestOf = (a: Applicant) => (brief ? fitCompany(a, brief)[0] : rank(a, plan.employers)[0])
  const link = (id: string) => `${location.origin}${location.pathname}#/event/${plan.slug}/applications/${encodeURIComponent(id)}`

  function open(id: string) {
    openId = id
    reason = ''
    pick = ''
    error = ''
  }
  function save() {
    if (!current) return
    if (!pick) return (error = 'Choose Accept or Decline first.')
    if (reason.trim().length < 8) return (error = 'Write one line explaining why: it is part of the record.')
    decide(by, current.id, pick, reason.trim())
    error = ''
    const next = list.find((a) => a.id !== current.id && !decisionOf(by, a.id))
    if (next) open(next.id)
  }
  async function copy(id: string) {
    await copyText(link(id))
    copied = id
    setTimeout(() => (copied = ''), 1600)
  }
  const kinds = { overlap: 'Overlap', gap: 'Gap', check: 'Check' }
</script>

<main>
  <a class="back" href="#/"><Icon name="back" size={16} />Events</a>
  <header>
    <h1>{plan.title}</h1>
    <p>{plan.when}. {brief ? `Applications as ${nameOf(brief)} sees them.` : 'Applications from the regular invitation.'} <span class="sample">sample data</span></p>
  </header>
  {#if !brief}<Tabs {plan} tab="applications" />{/if}

  {#if brief}
    <section class="as">
      <span class="tile"><Logo {brief} small /></span>
      <div>
        <b>Viewing as {nameOf(brief)}</b>
        <p>Only the people who asked to meet {nameOf(brief)} or fit one of its roles, and fit against those roles only. Espoo's organiser sees the whole event.</p>
      </div>
    </section>
  {/if}

  <section class="summary">
    <div><b>{list.length}</b><span>applications{brief ? ` for ${nameOf(brief)}` : ''}</span></div>
    <div><b>{counts.accepted}</b><span>accepted</span></div>
    <div><b>{counts.declined}</b><span>declined</span></div>
    <div><b>{list.length - counts.accepted - counts.declined}</b><span>to decide</span></div>
    {#if !brief}
      <div><b>{manage.golden ? some(manage.golden.n) : '0'}</b><span>golden tickets{manage.golden ? `, sent ${when(manage.golden.at.slice(0, 10))}` : ' sent'}</span></div>
      <div><b>{manage.copies}</b><span>regular link {manage.copies === 1 ? 'copy' : 'copies'}</span></div>
    {/if}
  </section>

  {#if !brief}
    <section class="share">
      <label>
        <span>A company's own view of its applications</span>
        <select bind:value={linkFor}>
          <option value="">Choose a company…</option>
          {#each plan.employers as e (e.brief.id)}<option value={e.brief.id}>{nameOf(e.brief)}</option>{/each}
        </select>
      </label>
      <button class="btn" disabled={!linkFor} onclick={() => copy(linkFor)}><Icon name={copied === linkFor && linkFor ? 'check' : 'copy'} size={16} />{copied === linkFor && linkFor ? 'Link copied' : 'Copy the link'}</button>
      {#if linkFor}<a class="see" href="#/event/{plan.slug}/applications/{encodeURIComponent(linkFor)}">Open it<Icon name="flat" size={14} /></a>{/if}
    </section>
  {/if}

  {#if !list.length}
    <p class="missing">No applications yet{brief ? ` that concern ${nameOf(brief)}` : ''}.</p>
  {:else}
    <div class="sides">
      <ul class="queue">
        {#each list as a (a.id)}
          {@const d = decisionOf(by, a.id)}
          {@const best = bestOf(a)}
          <li>
            <button class:on={current?.id === a.id} class:done={!!d} onclick={() => open(a.id)}>
              <span class="who"><b>{a.handle}</b><small>{a.field} · {a.level}</small></span>
              <span class="best">{best ? (brief ? best.need.title : nameOf(best.brief)) : 'no close role'}</span>
              {#if d}<span class="state {d.d}">{d.d === 'accept' ? 'Accepted' : 'Declined'}</span>{:else}<span class="state">To decide</span>{/if}
            </button>
          </li>
        {/each}
      </ul>

      {#if current}
        <article class="page">
          <header class="top">
            <div>
              <p class="eyebrow">Application · {when(current.applied_at.slice(0, 10))} · {current.sources.join(' and ')} read, with consent</p>
              <h2>{current.handle}</h2>
              <p class="facts">{current.field} · {current.level} · {current.city}{current.abroad ? ' (abroad)' : ''} · English {current.english}, Finnish {current.finnish}{current.project ? ` · work sample: ${current.project.name}` : ''}</p>
            </div>
            <p class="legend"><span class="tag ai">AI summary</span> drafted from the sources, left as drafted <span class="tag ok">Confirmed</span> answered, corrected or written by the applicant</p>
          </header>

          <section class="block ai">
            <h3><span class="tag ai">AI summary</span> Drafted from {current.sources.join(' and ')}</h3>
            <p class="sum">{current.ai_summary}</p>
            <ul class="lines">
              {#each current.drafted as l, i (i)}
                <li title={l.quote}><span>{l.text}</span><small>{l.source} · “{l.quote}”</small></li>
              {/each}
            </ul>
          </section>

          <section class="block ok">
            <h3><span class="tag ok">Confirmed</span> What the applicant answered, corrected or wrote</h3>
            {#if current.corrected.length}
              <ul class="lines">
                {#each current.corrected as l, i (i)}<li><span>{l.text}</span><small>corrected; was: {l.was}</small></li>{/each}
              </ul>
            {/if}
            <dl class="qa">
              {#each current.answers as qa, i (i)}<div><dt>{qa.q}</dt><dd>{qa.a || '—'}</dd></div>{/each}
            </dl>
            <blockquote>
              <p>“{current.own.about}”</p>
              <p><b>Looking for:</b> “{current.own.looking}”</p>
            </blockquote>
          </section>

          <section class="block fit">
            <h3>{brief ? `Fit against ${nameOf(brief)}'s roles` : 'Fit against the event and the pool'}</h3>
            {#if !brief && field}
              <p class="pool">
                <b>{field.name}:</b> {field.employers.length} {field.employers.length === 1 ? 'employer looks' : 'employers look'} for it at this event, and {some(field.people.people)} people in the pool already do this work
                {#if field.people.levels[current.level]}, {some(field.people.levels[current.level] ?? 0)} of them {current.level.toLowerCase()}{/if}.
                {#each current.skills.filter((s) => field.people.skills[s.name]) as s (s.name)}
                  <span class="chip">{s.name}: {some(field.people.skills[s.name] ?? 0)} in the pool</span>
                {/each}
              </p>
            {:else if !brief}
              <p class="pool">No employer at this event has a role in {current.field}; the pool is not asked for it here.</p>
            {/if}
            {#if fits.length}
              <ul class="roles">
                {#each fits as f (f.brief.id + f.need.id)}
                  <li>
                    <div class="role">{#if !brief}<span class="tile"><Logo brief={f.brief} small /></span>{/if}<div><b>{brief ? f.need.title : nameOf(f.brief)}</b><small>{brief ? f.need.seniority : f.need.title}</small></div></div>
                    <ul class="lines fitlines">
                      {#each f.lines as l, i (i)}<li class={l.kind}><em>{kinds[l.kind]}</em>{l.text}</li>{/each}
                    </ul>
                  </li>
                {/each}
              </ul>
            {:else}
              <p class="pool">Nothing in the drafted roles overlaps with this application.</p>
            {/if}
          </section>

          <footer class="decide">
            {#if decision}
              <p class="made"><span class="state {decision.d}">{decision.d === 'accept' ? 'Accepted' : 'Declined'}</span> by {decision.by === 'espoo' ? 'City of Espoo' : nameOf(brief ?? app.briefs[0]!)}, {when(decision.at.slice(0, 10))}: “{decision.reason}”</p>
              <button class="btn quiet" onclick={() => undecide(by, current.id)}>Change</button>
            {:else}
              <div class="pickrow">
                <button class="btn" class:primary={pick === 'accept'} onclick={() => (pick = 'accept')}><Icon name="check" size={16} />Accept</button>
                <button class="btn" class:primary={pick === 'decline'} onclick={() => (pick = 'decline')}><Icon name="x" size={16} />Decline</button>
                <input type="text" bind:value={reason} placeholder="Why, in one line (part of the record)" onkeydown={(e) => e.key === 'Enter' && save()} />
                <button class="btn primary" onclick={save}>Save and next</button>
              </div>
              {#if error}<p class="err">{error}</p>{/if}
            {/if}
          </footer>
        </article>
      {/if}
    </div>
  {/if}
  <p class="note">{applications.note} Decisions are kept in this browser.</p>
</main>

<style>
  main {
    --brand: var(--city);
    --brand-ink: var(--city-ink);
    display: grid;
    gap: var(--s5);
    max-width: 76rem;
    padding: var(--s6) var(--s7) var(--s8) var(--s6);
  }
  .back {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    justify-self: start;
    font-size: var(--t-sm);
    font-weight: 600;
    color: var(--ink-2);
    text-decoration: none;
  }
  h1 {
    font-size: var(--t-2xl);
  }
  header > p {
    margin-top: var(--s3);
    font-size: var(--t-lg);
    line-height: 1.4;
    color: var(--ink-2);
  }
  .sample {
    margin-left: var(--s2);
    padding: 0.2em 0.6em;
    border-radius: 99px;
    background: var(--wash);
    font: 600 var(--t-xs) / 1.4 var(--text);
    color: var(--ink-2);
    vertical-align: middle;
  }
  .as {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: var(--s4);
    align-items: center;
    padding: var(--s4) var(--s5);
    border-radius: var(--r2);
    background: var(--wash);
  }
  .as p {
    margin-top: 2px;
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  .summary {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s2) var(--s6);
  }
  .summary div {
    display: flex;
    align-items: baseline;
    gap: var(--s2);
  }
  .summary b {
    font: 800 var(--t-xl) / 1 var(--display);
    letter-spacing: -0.03em;
    color: var(--city);
  }
  .summary span {
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  .share {
    display: flex;
    flex-wrap: wrap;
    align-items: end;
    gap: var(--s3);
    padding: var(--s4) var(--s5);
    border: 1px solid var(--line);
    border-radius: var(--r2);
  }
  .share label {
    display: grid;
    gap: var(--s1);
    font-size: var(--t-sm);
    font-weight: 600;
  }
  .share select {
    min-height: 2.5rem;
    padding: 0 var(--s3);
    border: 1px solid var(--line);
    border-radius: var(--r1);
    font: inherit;
    font-size: var(--t-sm);
    background: var(--ground);
  }
  .see {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    min-height: 2.5rem;
    font-size: var(--t-sm);
    color: var(--ink-2);
    text-decoration: none;
  }
  .missing,
  .note {
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  .sides {
    display: grid;
    grid-template-columns: minmax(16rem, 0.8fr) minmax(0, 1.6fr);
    gap: var(--s6);
    align-items: start;
  }
  .queue {
    position: sticky;
    top: var(--s5);
    max-height: calc(100dvh - 2 * var(--s5));
    overflow: auto;
  }
  .queue button {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0 var(--s3);
    width: 100%;
    padding: var(--s3) var(--s3);
    border: 1px solid transparent;
    border-top-color: var(--line);
    border-radius: 0;
    background: none;
    text-align: left;
    font: inherit;
  }
  .queue button:hover {
    background: var(--wash);
  }
  .queue button.on {
    border-color: var(--city);
    border-radius: var(--r1);
    background: color-mix(in oklch, var(--city) 7%, var(--ground));
  }
  .queue .who b {
    display: block;
  }
  .queue .who small,
  .queue .best {
    font-size: var(--t-xs);
    color: var(--ink-2);
  }
  .queue .best {
    grid-column: 1;
    margin-top: 2px;
  }
  .queue .state {
    grid-column: 2;
    grid-row: 1 / span 2;
    align-self: start;
  }
  .tile {
    display: block;
    width: 2.5rem;
    height: 2.5rem;
    flex: none;
    border: 1px solid var(--line);
    border-radius: var(--r1);
    overflow: hidden;
  }
  .state {
    padding: 0.15em 0.6em;
    border-radius: 99px;
    background: var(--wash);
    font-size: var(--t-xs);
    font-weight: 700;
    color: var(--ink-2);
    white-space: nowrap;
  }
  .state.accept {
    background: color-mix(in oklch, var(--ok) 14%, white);
    color: var(--ok);
  }
  .state.decline {
    background: color-mix(in oklch, var(--stop) 10%, white);
    color: var(--stop);
  }
  .page {
    display: grid;
    gap: var(--s5);
    padding: var(--s5) var(--s6) var(--s6);
    border: 1px solid var(--line);
    border-radius: var(--r2);
    background: #fff;
    box-shadow: var(--lift);
  }
  .top {
    display: grid;
    gap: var(--s3);
  }
  .eyebrow {
    font-size: var(--t-xs);
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-2);
  }
  .page h2 {
    margin-top: var(--s1);
    font-size: var(--t-xl);
  }
  .facts {
    margin-top: var(--s1);
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  .legend {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--s2);
    font-size: var(--t-xs);
    color: var(--ink-2);
  }
  .tag {
    display: inline-block;
    padding: 0.1em 0.55em;
    border-radius: 4px;
    font-size: var(--t-xs);
    font-weight: 800;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    vertical-align: middle;
  }
  .tag.ai {
    background: oklch(94.5% 0.03 295);
    color: oklch(40% 0.12 295);
  }
  .tag.ok {
    background: color-mix(in oklch, var(--ok) 14%, white);
    color: var(--ok);
  }
  .block {
    padding: var(--s4) var(--s5);
    border-radius: var(--r2);
    border: 1px solid var(--line);
  }
  .block.ai {
    border-color: oklch(88% 0.05 295);
    background: oklch(98.5% 0.01 295);
  }
  .block.ok {
    border-color: color-mix(in oklch, var(--ok) 30%, white);
    background: color-mix(in oklch, var(--ok) 4%, white);
  }
  .block h3 {
    display: flex;
    align-items: center;
    gap: var(--s2);
    font-size: var(--t-sm);
    letter-spacing: 0;
  }
  .sum {
    margin-top: var(--s3);
    line-height: 1.45;
  }
  .lines {
    margin-top: var(--s3);
  }
  .lines li {
    display: grid;
    gap: 1px;
    padding: var(--s2) 0;
    border-top: 1px solid color-mix(in oklch, var(--line) 60%, transparent);
    font-size: var(--t-sm);
  }
  .lines small {
    font-size: var(--t-xs);
    color: var(--ink-2);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .qa {
    display: grid;
    gap: var(--s2);
    margin-top: var(--s3);
  }
  .qa div {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: var(--s3);
    font-size: var(--t-sm);
  }
  .qa dt {
    color: var(--ink-2);
  }
  .qa dd {
    font-weight: 600;
  }
  blockquote {
    margin: var(--s4) 0 0;
    padding-left: var(--s3);
    border-left: 3px solid var(--ok);
    font-size: var(--t-md);
    line-height: 1.45;
  }
  blockquote p + p {
    margin-top: var(--s1);
  }
  .pool {
    margin-top: var(--s3);
    font-size: var(--t-sm);
    line-height: 1.5;
    color: var(--ink-2);
  }
  .pool b {
    color: var(--ink);
  }
  .chip {
    display: inline-block;
    margin: var(--s1) var(--s1) 0 0;
    padding: 0.1em 0.6em;
    border-radius: 99px;
    background: var(--wash);
    font-size: var(--t-xs);
    color: var(--ink);
  }
  .roles {
    display: grid;
    gap: var(--s4);
    margin-top: var(--s4);
  }
  .role {
    display: flex;
    align-items: center;
    gap: var(--s3);
  }
  .role small {
    display: block;
    font-size: var(--t-xs);
    color: var(--ink-2);
  }
  .fitlines {
    margin-top: var(--s2);
  }
  .fitlines li {
    grid-template-columns: 4.5rem minmax(0, 1fr);
    border-top: 0;
    padding: 2px 0;
  }
  .fitlines em {
    font-style: normal;
    font-size: var(--t-xs);
    font-weight: 800;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .fitlines .overlap em {
    color: var(--ok);
  }
  .fitlines .gap em {
    color: var(--wait);
  }
  .fitlines .check em {
    color: oklch(45% 0.09 240);
  }
  .decide {
    padding-top: var(--s4);
    border-top: 1px solid var(--line);
  }
  .pickrow {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s2);
  }
  .pickrow input {
    flex: 1;
    min-width: 14rem;
    min-height: 2.5rem;
    padding: 0 var(--s3);
    border: 1px solid var(--line);
    border-radius: var(--r1);
    font: inherit;
    font-size: var(--t-sm);
  }
  .err {
    margin-top: var(--s2);
    font-size: var(--t-sm);
    color: var(--stop);
  }
  .made {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--s2);
    margin-bottom: var(--s2);
    font-size: var(--t-sm);
  }
  @media (max-width: 60rem) {
    .sides {
      grid-template-columns: 1fr;
    }
    .queue {
      position: static;
      max-height: none;
    }
    .qa div {
      grid-template-columns: 1fr;
    }
  }
</style>
