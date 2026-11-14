<script lang="ts">
  import { tick } from 'svelte'
  import type { Plan } from './events'
  import { concerns, fitCompany, rank, type Fit } from './fit'
  import { clock, when } from './format'
  import Icon from './Icon.svelte'
  import Logo from './Logo.svelte'
  import { applications, decide, decisionOf, undecide, type Decision } from './manage.svelte'
  import Mark from './Mark.svelte'
  import { app, copyText, nameOf, route } from './state.svelte'
  import Tabs from './Tabs.svelte'
  import type { Applicant } from './types'

  // An event's applications as a queue to work through. The list says who is waiting and where each
  // one stands without being read; one application shows the few facts that decide it first and the
  // rest on request. A decision takes three steps, in this order: approve or decline, a reason picked
  // from a few drafted for this applicant or written by hand, then record. The record says who decided,
  // when and why, and can be undone. Nobody is scored or ranked, and nobody has a photo.
  // Espoo sees the whole event; a company, by its own link, sees the applications that concern it.
  let { plan, company = '' }: { plan: Plan; company?: string } = $props()
  const brief = $derived(company ? app.briefs.find((b) => b.id === company) : undefined)
  const by = $derived(brief ? brief.id : 'espoo')
  const who = $derived(brief ? nameOf(brief) : 'City of Espoo')
  const list = $derived(brief ? applications.list.filter((a) => concerns(a, brief)) : applications.list)

  // ---- where each application stands
  type Status = 'waiting' | 'later' | 'accept' | 'decline'
  const STATUS: Record<Status, string> = { waiting: 'Waiting', later: 'Second look', accept: 'Approved', decline: 'Declined' }
  const statusOf = (a: Applicant): Status => decisionOf(by, a.id)?.d ?? 'waiting'
  const counts = $derived(Object.fromEntries((Object.keys(STATUS) as Status[]).map((s) => [s, list.filter((a) => statusOf(a) === s).length])) as Record<Status, number>)
  let filter = $state<Status | 'all'>('waiting')
  const shown = $derived(filter === 'all' ? list : list.filter((a) => statusOf(a) === filter))

  // ---- which one is open. On the Applications page it is in the address; inside an event's tab it is kept here.
  const paged = $derived(route().page === 'applications')
  let local = $state('')
  const openId = $derived(paged ? route().item : local)
  const current = $derived(list.find((a) => a.id === openId) ?? shown[0])
  const decision = $derived(current ? decisionOf(by, current.id) : undefined)
  function open(id: string) {
    if (paged) location.hash = id ? `#/applications/${encodeURIComponent(id)}` : '#/applications'
    else local = id
  }

  // ---- what decides it: the closest roles, without a score
  const fits = $derived<Fit[]>(current ? (brief ? fitCompany(current, brief) : rank(current, plan.employers)).slice(0, 3) : [])
  const field = $derived(current ? plan.fields.find((f) => f.name === current.field) : undefined)
  const asked = $derived(current ? plan.employers.filter((e) => current.wants.includes(e.brief.id)) : [])
  const skillsOf = (f: Fit, kind: 'overlap' | 'gap') => f.lines.filter((l) => l.kind === kind && !/^(Level|Finnish|English)/.test(l.text)).map((l) => l.text.split(':')[0] ?? '')
  const notes = (f: Fit) => f.lines.filter((l) => l.kind === 'check' || (l.kind !== 'overlap' && /^(Level|Finnish)/.test(l.text))).map((l) => l.text)
  const both = (items: string[]) => (items.length > 1 ? `${items.slice(0, -1).join(', ')} and ${items.at(-1) ?? ''}` : (items[0] ?? ''))

  // ---- the decision, in three steps
  type Choice = Decision['d']
  const VERB: Record<Choice, string> = { accept: 'Approve', decline: 'Decline', later: 'Second look' }
  const RECORD: Record<Choice, string> = { accept: 'Record approval', decline: 'Record decline', later: 'Set aside' }
  let choice = $state<Choice | ''>('')
  let picked = $state(0)
  let reason = $state('')
  let writing = $state<HTMLTextAreaElement>()
  let panel = $state<HTMLElement>()
  /** A few reasons for this applicant and this event, each written so that the applicant could be shown it. The organiser picks one, edits it or writes another. */
  function reasonsFor(a: Applicant, d: Choice): string[] {
    const top = fits[0]
    const shared = top ? skillsOf(top, 'overlap') : []
    const role = top ? (brief ? `Our ${top.need.title.toLowerCase()} role` : `${nameOf(top.brief)}'s ${top.need.title.toLowerCase()} role`) : ''
    const inField = field?.employers.length ?? 0
    const fieldName = a.field.toLowerCase()
    if (d === 'accept')
      return [
        shared.length ? `${role} asks for ${both(shared.slice(0, 2))}, which you have worked with.` : '',
        asked.length ? `You asked to meet ${both(asked.slice(0, 2).map((e) => nameOf(e.brief)))}, and ${asked.length > 1 ? 'they are' : 'it is'} at this event.` : '',
        inField ? `${String(inField)} ${inField === 1 ? 'employer' : 'employers'} at this event ${inField === 1 ? 'is' : 'are'} looking for people in ${fieldName}.` : '',
        'There is room at this event and your profile is complete.',
      ]
        .filter(Boolean)
        .slice(0, 3)
    if (d === 'decline') {
      const level = top?.lines.find((l) => l.kind === 'gap' && l.text.startsWith('Level'))
      return [
        !inField ? `No employer at this event has a role in ${fieldName} this time.` : '',
        level && top ? `The ${top.need.title.toLowerCase()} role closest to your profile asks for ${top.need.seniority.toLowerCase()} experience, and your profile says ${a.level.toLowerCase()}.` : '',
        a.skills.length < 3 ? 'Your profile names few tools or methods so far. Add what you have worked with and apply again.' : '',
        'The 1:1 meeting places at this event are full. The company presentations are open to everyone.',
        inField && !shared.length ? `The ${fieldName} roles at this event ask for skills your profile does not mention yet.` : '',
      ]
        .filter(Boolean)
        .slice(0, 3)
    }
    return [
      ...(top ? notes(top).slice(0, 1).map((n) => `To check first: ${n}.`) : []),
      top ? `Ask ${brief ? 'the hiring team' : nameOf(top.brief)} whether this profile is close enough for the ${top.need.title.toLowerCase()} role.` : '',
      !a.project ? 'Ask the applicant for a work sample before deciding.' : '',
    ]
      .filter(Boolean)
      .slice(0, 3)
  }
  const reasons = $derived(current && choice ? reasonsFor(current, choice) : [])
  function choose(d: Choice) {
    if (!current) return
    choice = d
    picked = 0
    reason = reasonsFor(current, d)[0] ?? ''
    // the reasons take room: the panel stops floating over the application and is brought into view instead
    void tick().then(() => panel?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }))
  }
  function pick(i: number) {
    picked = i
    reason = reasons[i] ?? ''
    if (i < 0) void tick().then(() => writing?.focus())
  }
  const cancel = () => ([choice, reason] = ['', ''])
  /** The last decision recorded, so one wrong press can be taken back. */
  let last = $state<null | { id: string; handle: string; d: Choice }>(null)
  function record() {
    const a = current
    if (!a || !choice || (choice !== 'later' && !reason.trim())) return
    // the next one still waiting, read before the decision lands and the list changes
    const at = shown.findIndex((x) => x.id === a.id)
    const next = [...shown.slice(at + 1), ...shown.slice(0, Math.max(at, 0))].find((x) => x.id !== a.id && statusOf(x) === 'waiting')
    decide(by, a.id, choice, reason.trim())
    last = { id: a.id, handle: a.handle, d: choice }
    cancel()
    open(filter === 'all' ? a.id : (next?.id ?? ''))
    scrollTo({ top: 0 })
  }
  function undo(id: string) {
    undecide(by, id)
    if (last?.id === id) last = null
  }
  const step = (n: number) => {
    const at = shown.findIndex((a) => a.id === current?.id)
    const to = shown[at + n]
    if (to) {
      cancel()
      open(to.id)
    }
  }
  function keys(e: KeyboardEvent) {
    const el = e.target as HTMLElement
    const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)
    if (typing) {
      // in the reason field, Ctrl or Cmd with Enter records; Escape leaves the field
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) record()
      else if (e.key === 'Escape') el.blur()
      return
    }
    if (e.metaKey || e.ctrlKey || e.altKey || !current) return
    const key = e.key.toLowerCase()
    if (key === 'z' && last) undo(last.id)
    else if (key === 'j' || e.key === 'ArrowDown') step(1)
    else if (key === 'k' || e.key === 'ArrowUp') step(-1)
    else if (decision) return
    else if (key === 'a') choose('accept')
    else if (key === 'd') choose('decline')
    else if (key === 'l') choose('later')
    else if (choice && /^[1-3]$/.test(key) && reasons[Number(key) - 1]) pick(Number(key) - 1)
    else if (choice && key === 'w') pick(-1)
    else if (choice && e.key === 'Enter') record()
    else if (choice && e.key === 'Escape') cancel()
    else return
    e.preventDefault()
  }

  // a company's own view of its applications, by link
  let linkFor = $state('')
  let copied = $state(false)
  async function copy() {
    if (!(await copyText(`${location.origin}${location.pathname}#/event/${plan.slug}/applications/${encodeURIComponent(linkFor)}`))) return
    copied = true
    setTimeout(() => (copied = false), 1600)
  }
  const srcTag = (src: string) => src.replace(/^linkedin$/i, 'LinkedIn').replace(/^github$/i, 'GitHub')
  const day = (iso: string) => when(iso.slice(0, 10))
</script>

<svelte:window onkeydown={keys} />

<main>
  {#if !paged}<a class="back" href="#/event/{plan.slug}"><Icon name="back" size={16} />{plan.title}</a>{/if}
  <header>
    <h1>Applications</h1>
    <p>
      <span>{#if paged}<a href="#/event/{plan.slug}">{plan.title}</a>{:else}{plan.title}{/if}, {plan.when}</span>
      {#if brief}<span class="as"><span class="tile"><Logo {brief} small /></span>as {who} sees them</span>{/if}
      <span class="sample">sample people</span>
    </p>
  </header>
  {#if !brief && !paged}<Tabs {plan} tab="applications" />{/if}

  <!-- where the applications stand, and the way to see each group -->
  <div class="filters" role="tablist" aria-label="Applications by status">
    {#each Object.keys(STATUS) as Status[] as s (s)}
      <button role="tab" aria-selected={filter === s} class={s} onclick={() => { filter = s; open('') }}><i></i>{STATUS[s]}<b>{counts[s]}</b></button>
    {/each}
    <button role="tab" aria-selected={filter === 'all'} onclick={() => { filter = 'all'; open('') }}>All<b>{list.length}</b></button>
  </div>

  {#if last}
    <p class="last" role="status">
      <span class="state {last.d}"><i></i>{last.handle}: {STATUS[last.d].toLowerCase()}</span>
      <button class="btn quiet" onclick={() => { if (last) undo(last.id) }}><Icon name="undo" size={16} />Undo <kbd>Z</kbd></button>
    </p>
  {/if}

  <div class="sides" class:opened={!!openId}>
    <ul class="queue" aria-label="Applications">
      {#each shown as a (a.id)}
        {@const s = statusOf(a)}
        <li>
          <button class:on={current?.id === a.id} aria-current={current?.id === a.id ? 'true' : undefined} onclick={() => { cancel(); open(a.id) }}>
            <span class="mark"><Mark seed={a.id} label="" /></span>
            <span class="who"><b>{a.handle}</b><small>{a.field} · {a.level}</small></span>
            <span class="state {s}" title={STATUS[s]}><i></i>{s === 'waiting' ? day(a.applied_at) : STATUS[s]}</span>
          </button>
        </li>
      {:else}
        <li class="none">
          {#if filter === 'waiting' && list.length}
            Nothing is waiting. {counts.accept} approved, {counts.decline} declined{counts.later ? `, ${String(counts.later)} set aside for a second look` : ''}.
          {:else if !list.length}
            No applications yet{brief ? ` that concern ${who}` : ''}. They arrive as people finish the invitation.
          {:else}
            None here.
          {/if}
        </li>
      {/each}
    </ul>

    {#if current}
      {@const s = statusOf(current)}
      <article class="one">
        <button class="all" onclick={() => { open('') }}><Icon name="back" size={16} />All applications</button>
        <header>
          <span class="mark"><Mark seed={current.id} label="" /></span>
          <div>
            <h2>{current.handle}<span class="state {s}"><i></i>{STATUS[s]}</span></h2>
            <p>{current.field} · {current.level} · {current.city}</p>
          </div>
        </header>
        <p class="chips">
          <span>English {current.english}</span><span>Finnish {current.finnish}</span>
          {#if current.abroad}<span>Lives abroad</span>{/if}
          {#if current.permit}<span>Needs work-permit support</span>{/if}
          {#if current.project}<span>Work sample: {current.project.name}</span>{/if}
          <span>Applied {day(current.applied_at)}</span>
        </p>

        {#if asked.length && !brief}
          <section>
            <h3>Asked to meet</h3>
            <p class="asked">{#each asked as e (e.brief.id)}<span><span class="tile"><Logo brief={e.brief} small /></span>{nameOf(e.brief)}</span>{/each}</p>
          </section>
        {/if}

        <section>
          <h3>{brief ? `Against ${who}'s roles` : 'Closest roles at this event'}</h3>
          {#if fits.length}
            <ul class="fits">
              {#each fits as f (f.brief.id + f.need.id)}
                <li>
                  <p class="role">{#if !brief}<span class="tile"><Logo brief={f.brief} small /></span>{/if}<b>{brief ? f.need.title : nameOf(f.brief)}</b>{#if !brief}<span>{f.need.title}</span>{/if}</p>
                  <p class="skills">
                    {#each skillsOf(f, 'overlap') as skill (skill)}<span class="has"><Icon name="check" size={12} />{skill}</span>{/each}
                    {#each skillsOf(f, 'gap') as skill (skill)}<span class="lacks">{skill}</span>{/each}
                  </p>
                  {#each notes(f) as note (note)}<p class="note">{note}</p>{/each}
                </li>
              {/each}
            </ul>
          {:else}
            <p class="note">{field ? 'No role at this event asks for what this profile names.' : `No employer at this event has a role in ${current.field.toLowerCase()}.`}</p>
          {/if}
        </section>

        <section>
          <h3>In their own words</h3>
          <blockquote>{current.own.about}<span>Looking for: {current.own.looking}</span></blockquote>
        </section>

        <details>
          <summary>The whole application<Icon name="plus" size={14} /></summary>
          <h3>Drafted from {current.sources.map(srcTag).join(' and ')}, read with consent, left as drafted</h3>
          <ul class="lines">
            {#each current.drafted as l, i (i)}<li title="“{l.quote}”">{l.text}<small>{srcTag(l.source)}</small></li>{/each}
          </ul>
          <h3>Answered, corrected or written by the applicant</h3>
          <ul class="lines">
            {#each current.corrected as l, i (i)}<li title="was: {l.was}">{l.text}<small>corrected</small></li>{/each}
            {#each current.answers.filter((qa) => qa.a) as qa, i (i)}<li>{qa.a}<small>{qa.q}</small></li>{/each}
          </ul>
        </details>

        <!-- the decision: approve or decline, then a reason, then record -->
        <footer class="decide" class:open={!!choice} bind:this={panel}>
          {#if decision}
            <div class="record">
              <p><span class="state {decision.d}"><i></i>{STATUS[decision.d]}</span> by {decision.by === 'espoo' ? 'City of Espoo' : who}, {day(decision.at)} at {clock(decision.at)}</p>
              {#if decision.reason}<blockquote>{decision.reason}</blockquote>{/if}
              <button class="btn quiet" onclick={() => { undo(current.id) }}><Icon name="undo" size={16} />Undo this decision</button>
            </div>
          {:else if !choice}
            <p class="steps"><b>1 Decide</b><span>2 Reason</span><span>3 Record</span></p>
            <div class="row">
              <button class="btn approve" onclick={() => { choose('accept') }}><Icon name="check" size={16} />Approve <kbd>A</kbd></button>
              <button class="btn decline" onclick={() => { choose('decline') }}><Icon name="x" size={16} />Decline <kbd>D</kbd></button>
              <button class="btn quiet" onclick={() => { choose('later') }}>Second look <kbd>L</kbd></button>
            </div>
          {:else}
            <p class="steps"><span>1 {VERB[choice]}</span><b>2 Reason</b><span>3 Record</span></p>
            <div class="reasons" role="radiogroup" aria-label="Reason">
              {#each reasons as r, i (r)}
                <button role="radio" aria-checked={picked === i} onclick={() => { pick(i) }}><kbd>{i + 1}</kbd>{r}</button>
              {/each}
              <button role="radio" aria-checked={picked < 0} onclick={() => { pick(-1) }}><kbd>W</kbd>Write my own</button>
            </div>
            <textarea bind:this={writing} bind:value={reason} rows="2" aria-label="The reason, as it will be recorded" placeholder={choice === 'later' ? 'What to look at again (optional)' : 'The reason, as it will be recorded'}></textarea>
            <div class="row">
              <button class="btn {choice === 'accept' ? 'approve' : choice === 'decline' ? 'decline' : ''}" disabled={choice !== 'later' && !reason.trim()} onclick={record}>{RECORD[choice]} <kbd>Enter</kbd></button>
              <button class="btn quiet" onclick={cancel}>Back <kbd>Esc</kbd></button>
              <span class="quiet">Recorded as decided by {who}. Nothing is sent to the applicant.</span>
            </div>
          {/if}
        </footer>
      </article>
    {/if}
  </div>

  {#if !brief}
    <details class="share">
      <summary>Share with a company<Icon name="plus" size={14} /></summary>
      <p>
        <select bind:value={linkFor} aria-label="Company">
          <option value="">Choose a company…</option>
          {#each plan.employers as e (e.brief.id)}<option value={e.brief.id}>{nameOf(e.brief)}</option>{/each}
        </select>
        <button class="btn" disabled={!linkFor} onclick={copy}><Icon name={copied ? 'check' : 'copy'} size={16} />{copied ? 'Link copied' : 'Copy its link'}</button>
        {#if linkFor}<a class="btn quiet" href="#/event/{plan.slug}/applications/{encodeURIComponent(linkFor)}">Open its view<Icon name="flat" size={14} /></a>{/if}
      </p>
    </details>
  {/if}
  <p class="foot"><kbd>J</kbd> <kbd>K</kbd> next and previous. {applications.note} Decisions are kept in this browser.</p>
</main>

<style>
  main {
    --brand: var(--city);
    --brand-ink: var(--city-ink);
    display: grid;
    gap: var(--s4);
    max-width: 82rem;
    padding: var(--s6) var(--s7) var(--s8) var(--s6);
  }
  .back,
  .all {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    justify-self: start;
    min-height: 2.75rem;
    padding: 0;
    border: 0;
    background: none;
    font-size: var(--t-sm);
    font-weight: 600;
    color: var(--ink-2);
    text-decoration: none;
  }
  .all {
    display: none;
  }
  h1 {
    font: 800 var(--t-2xl) / 0.95 var(--display);
    letter-spacing: -0.035em;
  }
  main > header p {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--s1) var(--s3);
    margin-top: var(--s2);
    color: var(--ink-2);
  }
  main > header a {
    font-weight: 600;
    color: var(--ink);
    text-decoration: none;
  }
  main > header a:hover {
    text-decoration: underline;
  }
  .as {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    font-weight: 600;
    color: var(--ink);
  }
  .sample {
    padding: 0.2em 0.6em;
    border-radius: 99px;
    background: var(--wash);
    font: 600 var(--t-xs) / 1.4 var(--text);
    white-space: nowrap;
  }
  kbd {
    padding: 0.05rem 0.35rem;
    border: 1px solid color-mix(in srgb, currentColor 40%, transparent);
    border-radius: 4px;
    font: 600 var(--t-xs) / 1.4 var(--text);
    opacity: 0.8;
  }

  /* status, read at a glance: a dot and a word, the same everywhere on this page */
  .state {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    font-size: var(--t-sm);
    font-weight: 600;
    white-space: nowrap;
  }
  .state i,
  .filters i {
    flex: none;
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    background: var(--wait);
  }
  .accept {
    color: var(--ok);
  }
  .accept i {
    background: var(--ok);
  }
  .decline {
    color: var(--stop);
  }
  .decline i {
    background: var(--stop);
  }
  .later i {
    background: none;
    box-shadow: inset 0 0 0 2px var(--ink-2);
  }
  .waiting,
  .later {
    color: var(--ink-2);
  }

  .filters {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s2);
  }
  .filters button {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    min-height: 2.75rem;
    padding: 0 var(--s4);
    border: 1px solid var(--line);
    border-radius: 99px;
    background: var(--ground);
    color: var(--ink);
    font-weight: 600;
  }
  .filters b {
    font-weight: 800;
  }
  .filters button[aria-selected='true'] {
    border-color: var(--ink);
    box-shadow: inset 0 0 0 1px var(--ink);
  }
  .last {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--s2) var(--s4);
    padding: var(--s1) var(--s4);
    border-radius: var(--r1);
    background: var(--wash);
  }

  .sides {
    display: grid;
    grid-template-columns: minmax(15rem, 20rem) minmax(0, 1fr);
    gap: var(--s6);
    align-items: start;
  }
  .queue {
    position: sticky;
    top: var(--s4);
    max-height: calc(100dvh - 2rem);
    overflow-y: auto;
    border-top: 1px solid var(--line);
  }
  .queue button {
    display: grid;
    grid-template-columns: 2rem minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--s3);
    width: 100%;
    min-height: 3.5rem;
    padding: var(--s2);
    border: 0;
    border-bottom: 1px solid var(--line);
    background: none;
    text-align: left;
  }
  .queue button:hover {
    background: var(--wash);
  }
  .queue button.on {
    background: var(--wash);
    box-shadow: inset 3px 0 0 var(--city);
  }
  .mark {
    display: block;
    width: 2rem;
    height: 2rem;
  }
  .who {
    display: grid;
    min-width: 0;
    line-height: 1.25;
  }
  .who small {
    overflow: hidden;
    font-size: var(--t-xs);
    color: var(--ink-2);
    white-space: nowrap;
    text-overflow: ellipsis;
  }
  .queue .state {
    font-size: var(--t-xs);
  }
  .none {
    padding: var(--s4) var(--s2);
    color: var(--ink-2);
  }

  /* one application: what decides it first, the rest on request */
  .one {
    display: grid;
    gap: var(--s5);
    min-width: 0;
  }
  .one > header {
    display: grid;
    grid-template-columns: 3.5rem minmax(0, 1fr);
    align-items: center;
    gap: var(--s4);
  }
  .one > header .mark {
    width: 3.5rem;
    height: 3.5rem;
  }
  h2 {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--s2) var(--s4);
    font-size: var(--t-xl);
  }
  .one > header p {
    margin-top: var(--s1);
    color: var(--ink-2);
  }
  .chips,
  .asked,
  .skills {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s2);
  }
  .chips {
    margin-top: calc(-1 * var(--s2));
  }
  .chips span,
  .skills span {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    padding: 0.2em 0.7em;
    border-radius: 99px;
    background: var(--wash);
    font-size: var(--t-sm);
  }
  h3 {
    margin-bottom: var(--s2);
    font: 600 var(--t-sm) / 1.3 var(--text);
    letter-spacing: 0;
    color: var(--ink-2);
  }
  .asked span {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    font-weight: 600;
  }
  .tile {
    display: inline-block;
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
  .fits li {
    display: grid;
    gap: var(--s2);
    padding: var(--s3) 0;
    border-top: 1px solid var(--line);
  }
  .role {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--s2) var(--s3);
  }
  .role span:not(.tile) {
    color: var(--ink-2);
  }
  .skills .has {
    background: color-mix(in oklch, var(--ok) 14%, var(--ground));
    font-weight: 600;
  }
  .skills .lacks {
    background: none;
    box-shadow: inset 0 0 0 1px var(--line);
    color: var(--ink-2);
  }
  .note {
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  blockquote {
    margin: 0;
    padding-left: var(--s4);
    box-shadow: inset 2px 0 0 var(--line);
    line-height: 1.45;
  }
  blockquote span {
    display: block;
    margin-top: var(--s1);
    color: var(--ink-2);
  }
  details summary {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    min-height: 2.75rem;
    font-size: var(--t-sm);
    font-weight: 600;
    color: var(--ink-2);
    cursor: pointer;
    list-style: none;
  }
  details summary::-webkit-details-marker {
    display: none;
  }
  details[open] summary {
    color: var(--ink);
  }
  details h3 {
    margin-top: var(--s3);
  }
  .lines li {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 0 var(--s4);
    padding: var(--s2) 0;
    border-top: 1px solid var(--line);
    font-size: var(--t-sm);
  }
  .lines small {
    color: var(--ink-2);
  }

  /* the decision stays in reach at the foot of the window while the application is read */
  .decide {
    position: sticky;
    bottom: var(--s3);
    display: grid;
    gap: var(--s3);
    padding: var(--s4);
    border-radius: var(--r2);
    background: var(--ground);
    box-shadow: 0 0 0 1px var(--line), var(--lift);
  }
  .decide.open {
    position: static;
  }
  .steps {
    display: flex;
    gap: var(--s4);
    font-size: var(--t-xs);
    font-weight: 600;
    color: var(--ink-2);
  }
  .steps b {
    color: var(--ink);
  }
  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--s2) var(--s3);
  }
  .decide .btn {
    min-height: 2.75rem;
  }
  .approve {
    border-color: transparent;
    background: var(--ok);
    color: #fff;
  }
  .btn.decline {
    border-color: transparent;
    background: var(--stop);
    color: #fff;
  }
  .btn.decline i,
  .btn.approve i {
    display: none;
  }
  .quiet {
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  .reasons {
    display: grid;
    gap: var(--s1);
  }
  .reasons button {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    align-items: start;
    gap: var(--s3);
    min-height: 2.75rem;
    padding: var(--s3);
    border: 1px solid var(--line);
    border-radius: var(--r1);
    background: var(--ground);
    line-height: 1.35;
    text-align: left;
  }
  .reasons button[aria-checked='true'] {
    border-color: var(--ink);
    box-shadow: inset 0 0 0 1px var(--ink);
  }
  textarea {
    width: 100%;
    padding: var(--s3);
    border: 1px solid var(--line);
    border-radius: var(--r1);
    background: var(--ground);
    font: inherit;
    line-height: 1.4;
    resize: vertical;
  }
  textarea:focus {
    outline: 2px solid var(--ink);
    outline-offset: 1px;
  }
  .record {
    display: grid;
    justify-items: start;
    gap: var(--s2);
  }
  .record p {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--s1) var(--s3);
  }
  .share p {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--s2) var(--s3);
  }
  select {
    min-height: 2.75rem;
    padding: 0 var(--s3);
    border: 1px solid var(--line);
    border-radius: var(--r1);
    background: var(--ground);
    font: inherit;
  }
  .foot {
    max-width: 80ch;
    font-size: var(--t-sm);
    color: var(--ink-2);
  }

  /* on a phone the queue and one application take turns */
  @media (max-width: 820px) {
    main {
      padding: var(--s5) var(--s4) var(--s7);
    }
    .sides {
      grid-template-columns: minmax(0, 1fr);
    }
    .queue {
      position: static;
      max-height: none;
    }
    .sides.opened .queue,
    .sides:not(.opened) .one {
      display: none;
    }
    .all {
      display: inline-flex;
    }
    /* the statuses stay in one row that can be swiped */
    .filters {
      flex-wrap: nowrap;
      margin: 0 calc(-1 * var(--s4));
      padding: 0 var(--s4);
      overflow-x: auto;
      scrollbar-width: none;
    }
    .filters button {
      flex: none;
      padding: 0 var(--s3);
      font-size: var(--t-sm);
    }
    .foot kbd,
    .decide kbd {
      display: none;
    }
  }
</style>
