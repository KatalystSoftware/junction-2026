<script lang="ts">
  import KutsuMark from './KutsuMark.svelte'
  import { flip } from 'svelte/animate'
  import { cubicOut } from 'svelte/easing'
  import { crossfade, fade } from 'svelte/transition'
  import { confetti } from './confetti'
  import { text } from './editable'
  import { occasionOf, plans } from './events'
  import { pdfText, Unread } from './cv'
  import { bare, linkedinName, linkedinTyped } from './format'
  import Icon from './Icon.svelte'
  import Logo from './Logo.svelte'
  import Mark from './Mark.svelte'
  import { markOf } from './mark'
  import { tick } from 'svelte'
  import { addOwn, chosen, cleared, CV_MOST, givenNow, keep, kept, linksOf, matches, me, progress, readAll, seedOf, SHOWN, sourceLabel, sourcesOf, startOver, type Fact } from './person.svelte'
  import SiteIcon from './SiteIcon.svelte'
  import { siteOf } from './sites'
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

  // ---- the first card: what may we read. Nothing is read before the person says so.
  const reading = $derived(Object.keys(progress.at).length > 0)
  const has = $derived(m.typed || m.can.length + m.skills.length + m.roles.length > 0)
  const fresh = $derived(m.read_from === givenNow(m))
  const all = $derived(sourcesOf(m))
  const picked = $derived(chosen(m))
  const found = $derived(m.can.length + m.skills.length + m.roles.length)
  const nothing = $derived(!reading && !m.sample && Object.keys(m.read).length > 0 && found === 0)
  /** What was typed or pasted, cut down to what the field holds: a username for LinkedIn, an address without its scheme for a link. */
  // A field is never rewritten under the person's fingers: a key typed or deleted stays as it is, slashes included, or
  // "https://github.com/name" could not be typed at all. An address is tidied when it arrives whole (pasted, dropped,
  // filled in by the browser) and when the field is left.
  type Typed = Event & { currentTarget: HTMLInputElement }
  const typing = (e: Event) => e.type === 'input' && /^(insertText|insertCompositionText|delete)/.test((e as InputEvent).inputType || '')
  function setLinkedin(e: Typed) {
    const field = e.currentTarget
    // the one thing done while typing: a whole address typed up to the username gives way to the fixed prefix beside the field
    const value = !typing(e) || linkedinTyped(field.value) === 'whole' ? linkedinName(field.value) : field.value
    if (field.value !== value) {
      const caret = Math.max(0, (field.selectionStart ?? 0) - (field.value.length - value.length))
      field.value = value
      if (document.activeElement === field) field.setSelectionRange(caret, caret)
    }
    m.linkedin = value
    keep()
  }
  function setLink(i: number, e: Typed) {
    const field = e.currentTarget
    let value = typing(e) ? field.value : bare(field.value)
    // a LinkedIn address pasted among the links belongs in the field above them
    if (!typing(e) && /linkedin\.com\/in\/./i.test(value)) {
      m.linkedin = linkedinName(value)
      value = ''
    }
    m.links[i] = value
    if (field.value !== value) field.value = value
    keep()
  }
  // ---- a CV: a PDF, read in this browser, or its text pasted. Either way the text in the field is what gets read.
  /** the text field opened by hand, or by a file that could not be read */
  let pasting = $state(false)
  let extracting = $state(false)
  let dropping = $state(false)
  let cvWrong = $state('')
  let picker = $state<HTMLInputElement>()
  let cvText = $state<HTMLTextAreaElement>()
  async function takeCv(file: File | undefined) {
    if (!file || reading || extracting) return
    cvWrong = ''
    extracting = true
    try {
      m.cv = await pdfText(file)
      m.cvFile = file.name
    } catch (error) {
      // what was there before stays; the text field is the way on
      cvWrong = error instanceof Unread ? error.message : 'That file could not be read. Paste the text of your CV instead.'
      pasting = true
    }
    extracting = false
    // the same file can be chosen again
    if (picker) picker.value = ''
    keep()
  }
  function removeCv() {
    ;[m.cv, m.cvFile, cvWrong, pasting] = ['', '', '', false]
    keep()
  }
  async function pasteInstead() {
    pasting = true
    await tick()
    cvText?.focus()
  }
  // a file dropped anywhere on the card is taken, so one that misses the box does not open in the tab instead
  const carriesFile = (e: DragEvent) => !!picker && !!e.dataTransfer?.types.includes('Files')
  function drag(e: DragEvent) {
    if (!carriesFile(e)) return
    e.preventDefault()
    dropping = true
  }
  function drop(e: DragEvent) {
    if (!carriesFile(e)) return
    e.preventDefault()
    dropping = false
    void takeCv(e.dataTransfer?.files[0])
  }
  // an obviously wrong value is caught here, before a lookup is spent on it
  const wrongLinkedin = $derived(
    !m.linkedin
      ? ''
      : /[\s@]/.test(m.linkedin)
        ? 'A LinkedIn username has no spaces and no @. It is the last part of your profile’s address.'
        : /[/:]|\.[a-z]{2,}$/i.test(m.linkedin)
          ? 'That looks like the address of another site. It goes among the links below.'
          : '',
  )
  const wrongLink = (raw: string) => (!raw.trim() || siteOf(raw) ? '' : /^@[\w.-]+$/.test(raw.trim()) ? 'Add the site too, for example x.com/yourname.' : 'That does not look like a web address. It should read like yoursite.com.')
  const wrong = $derived(!!wrongLinkedin || m.links.some((l) => wrongLink(l)))
  const sourceOn = (key: string) => !m.off.includes(key)
  const switchSource = (key: string) => {
    m.off = sourceOn(key) ? [...m.off, key] : m.off.filter((k) => k !== key)
    keep()
  }
  /** How one source is doing, in a short true line. */
  const status = (key: string, label: string) => {
    const at = progress.at[key]
    const was = m.read[key]
    if (at === 'reading') return { kind: 'busy', says: key === 'cv' ? 'Reading your CV' : `Reading ${label} through Context.dev` }
    if (at === 'writing') return { kind: 'busy', says: `${was && 'lines' in was ? String(was.lines) : 'Some'} lines read. Writing them up for you to check` }
    if (!was || !fresh) return undefined
    return 'error' in was ? { kind: 'failed', says: was.error } : { kind: 'done', says: `${String(was.lines)} lines read, ${String(was.found ?? 0)} things found` }
  }
  // while the lines are being written up, say what that work is: every line here is something that is happening
  const DOING = ['Looking for what you have built and run', 'Picking out the tools you named', 'Keeping the words each line comes from', 'Leaving out age, gender and nationality', 'Saving nothing while this runs']
  let doing = $state(0)
  $effect(() => {
    if (!reading) return
    const turn = setInterval(() => (doing = (doing + 1) % DOING.length), 1900)
    return () => {
      clearInterval(turn)
    }
  })
  let where = $state(false)

  // ---- everything to decide, in order; the first undecided one is in the centre unless a line was opened
  const KEYS = ['read', 'you', 'know', 'want', 'meet'] as const
  type Key = (typeof KEYS)[number]
  const decided = (k: Key) => (k === 'read' ? has && !reading && (fresh || m.typed) : k === 'you' ? m.you_ok : k === 'know' ? m.know_ok : k === 'want' ? m.want_ok : !!m.done)
  let opened = $state<Key | null>(null)
  let started = $state(me.is.sample || me.is.typed || Object.keys(me.is.read).length > 0)
  const current = $derived<Key>(opened ?? KEYS.find((k) => !decided(k)) ?? 'meet')

  const on = (f: Fact) => !m.struck.includes(f.id)
  // who they are: three things they can do are kept by default, the rest one press away
  let more = $state(false)
  let detail = $state<string | null>(null)
  let pressed = $state(false)
  // a profile typed in by hand is open for typing from the start
  const editing = $derived(pressed || m.typed)
  const hidden = $derived(m.can.filter((f, i) => i >= SHOWN && !on(f)).length)
  const typed = (e: FocusEvent) => (e.currentTarget as HTMLElement).innerText.replace(/\s+/g, ' ').trim()
  const enter = (e: KeyboardEvent) => {
    if (e.key !== 'Enter') return
    e.preventDefault()
    ;(e.currentTarget as HTMLElement).blur()
  }
  /** The last line taken out, so one wrong press can be taken back. */
  let undo = $state<null | { id: string }>(null)
  function toggle(f: Fact) {
    if (on(f)) {
      m.struck = [...m.struck, f.id]
      undo = { id: f.id }
      detail = null
    } else {
      m.struck = m.struck.filter((id) => id !== f.id)
      undo = null
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
  const reword = (f: Fact, e: FocusEvent) => {
    const now = typed(e)
    if (now && now !== f.text) f.text = now
    keep()
  }
  let own = $state('')
  const add = (list: 'can' | 'skills' | 'roles') => {
    addOwn(list, own)
    own = ''
  }
  const FIELDS = $derived([...new Set([m.field, ...(plan?.fields.map((f) => f.name) ?? [])].filter(Boolean))].slice(0, 8))
  const LEVELS = ['Early career', 'Experienced', 'Senior', 'Lead']
  const PLACES = ['On site', 'Hybrid', 'Remote']
  const want = (field: string) => {
    m.wants = m.wants.includes(field) ? m.wants.filter((f) => f !== field) : [...m.wants, field]
    keep()
  }
  // whom they might want to meet: this event's employers that look for what they do, each with why. None is ticked for them.
  const offered = $derived(matches(m, plan?.employers ?? []).slice(0, 6))
  const pick = (id: string) => {
    m.meet = m.meet.includes(id) ? m.meet.filter((x) => x !== id) : [...m.meet, id]
    keep()
  }

  function accept() {
    const k = current
    ;[opened, undo, pressed, own] = [null, null, false, '']
    if (k === 'read') {
      if (!(has && (fresh || m.typed)) && picked.length && !wrong && !reading) void readAll()
    } else if (k === 'you') m.you_ok = true
    else if (k === 'know') m.know_ok = true
    else if (k === 'want') m.want_ok = true
    else if (!m.done) {
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
    // the file chooser keeps its own keys: Enter and Space open it
    if (el instanceof HTMLInputElement && el.type === 'file') return
    const typing = el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)
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
    if (['BUTTON', 'A', 'SUMMARY'].includes(el.tagName) && !(choice && e.key === 'Enter')) return
    if (e.key === 'Enter' || (e.key === ' ' && !typing)) {
      e.preventDefault()
      if (!started) started = true
      else if (ready) accept()
    } else if (started && e.key === 'ArrowLeft') back()
  }

  // ---- what is already settled, at the sides; the one in the centre is not shown there
  const settled = $derived({
    you: m.you_ok && current !== 'you',
    can: m.you_ok && current !== 'you' ? kept(m, m.can) : [],
    know: m.know_ok && current !== 'know',
    want: m.want_ok && current !== 'want',
  })
  const links = $derived(linksOf(m))
  const terms = $derived([m.level, m.place, m.finnish ? 'Works in Finnish too' : '', m.abroad ? 'Lives outside Finland now' : ''].filter(Boolean))
  const calm = matchMedia('(prefers-reduced-motion: reduce)').matches
  const [send, receive] = crossfade({ duration: calm ? 0 : 560, easing: cubicOut, fallback: (node) => fade(node, { duration: calm ? 0 : 220 }) })
  const answer = $derived(
    current === 'read'
      ? reading
        ? 'Reading'
        : has && (fresh || m.typed)
          ? 'Continue'
          : 'Read these'
      : current === 'you'
        ? "That's me"
        : current === 'know'
          ? "That's right"
          : current === 'want'
            ? "That's what I want"
            : 'My profile is ready',
  )
  const ready = $derived(
    current === 'read'
      ? !reading && !wrong && ((has && (fresh || m.typed)) || picked.length > 0)
      : current === 'you'
        ? !m.typed || (!!m.name.trim() && kept(m, m.can).length > 0)
        : current === 'want'
          ? m.wants.length > 0 || !!m.looking.trim()
          : true,
  )
  // a new card starts at its top, also when the last one was read to its end on a phone
  let bench = $state<HTMLElement>()
  let shown = ''
  $effect(() => {
    const key = current
    const card = bench
    if (shown && shown !== key && card && card.getBoundingClientRect().top < 0) void tick().then(() => { card.scrollIntoView({ block: 'start' }) })
    shown = key
  })
  // clearing everything goes back to the invitation
  let wiped = cleared.n
  $effect(() => {
    if (cleared.n !== wiped) [wiped, started, opened, more, pressed] = [cleared.n, false, null, false, false]
  })
</script>

<svelte:window onkeydown={keys} ondragover={drag} ondrop={drop} ondragleave={(e: DragEvent) => { if (!e.relatedTarget) dropping = false }} />

{#snippet says(state: { kind: string; says: string } | undefined)}
  {#if state?.kind === 'busy'}<p class="drafting" role="status"><i></i>{state.says}</p>{:else if state}<p class={state.kind} role={state.kind === 'failed' ? 'alert' : undefined}>{state.says}</p>{/if}
{/snippet}

<div class="join" class:cover={!started} style:--brand="var(--city)" style:--brand-ink="var(--city-ink)">
  <p class="host"><b class="kutsu"><KutsuMark size={16} />Kutsu</b>City of Espoo <span>{event.name}, {event.when} · demonstration{m.sample ? ' with a sample person, made up' : ''}</span></p>

  {#if !started}
    <section class="invite">
      <h1>{#each "You're invited.".split(' ') as word, i (i)}<span style:--i={i}>{word}&nbsp;</span>{/each}</h1>
      <p class="filled" style:--i={3}>{event.name}, {event.when}. {event.facts} Your profile fills itself in from what you choose to show us.</p>
      <p class="filled demo" style:--i={4}>This is a demonstration. Nothing you enter here reaches Espoo or an employer; the real sign-up is on Espoo's event page.</p>
      <button class="yes big" style:--i={5} onclick={() => (started = true)}>Start <kbd>Enter</kbd></button>
    </section>
  {:else if m.done}
    <Yours {event} {offered} url={plan?.url ?? ''} seed={seedOf(m)} />
  {:else}
    <div class="bench" bind:this={bench}>
      <aside class="left" aria-label="About you">
        {#if settled.you}
          <h3>About you</h3>
          <button class="line you" onclick={() => (opened = 'you')} in:receive={{ key: 'you' }} out:send={{ key: 'you' }}>
            <span class="tile mine"><Mark seed={seedOf(m)} /></span>
            <b>{m.name || 'You'}</b>
            <span>{m.headline}</span>
            {#if links.length}<span class="sites">{#each links as site (site.href)}<SiteIcon id={site.id} size={16} />{/each}</span>{/if}
          </button>
          {#each settled.can as f (f.id)}
            <button class="line" onclick={() => { opened = 'you'; detail = f.id }} in:fade={{ duration: 300, delay: 250 }} animate:flip={{ duration: 300 }}>
              <span class="fact">{f.text}</span>
              {#if f.from}<span class="more">“{f.from}”</span>{/if}
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
              {#if reading || (found > 0 && fresh)}
                <!-- what has arrived so far: the page is never still while it works -->
                <p class="live" role="status">
                  <span class="tile mine"><Mark seed={seedOf(m)} /></span>
                  <b>{m.name || (reading ? 'Reading what you chose' : 'Read')}</b>
                  <span>{reading ? DOING[doing] : `${String(found)} things found. Every one is yours to keep or take out.`}</span>
                </p>
              {:else}
                <p class="pitch">Nothing is read until you say so.</p>
              {/if}

              {#if m.sample}
                <p class="sample"><b>This is a sample person.</b> Olena K. is made up, and so is everything about her. <button class="rest" onclick={() => { startOver() }}>Use my own instead</button></p>
              {:else}
                <ul class="tell sources" aria-label="What you let us read">
                  <li class="source" class:on={!!m.linkedin && sourceOn('linkedin')}>
                    <button class="tick" role="checkbox" data-choice aria-checked={!!m.linkedin && sourceOn('linkedin')} aria-label="Read my LinkedIn profile" disabled={!m.linkedin || reading} onclick={() => { switchSource('linkedin') }}>
                      <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4.5 10.5 8.5 14.5 15.5 6" /></svg>
                    </button>
                    <!-- the fixed part of the address is part of the field; only the username is typed, and a pasted address is cut down to it -->
                    <label class="field prefixed">
                      <span aria-hidden="true">linkedin.com/in/</span>
                      <input aria-label="Your LinkedIn username" placeholder="your-name" value={m.linkedin} oninput={setLinkedin} onchange={setLinkedin} disabled={reading} autocomplete="off" autocapitalize="none" spellcheck="false" />
                    </label>
                    <!-- a LinkedIn address still being typed is not called a mistake: it cannot be read yet, and nothing is said -->
                    {#if wrongLinkedin && !linkedinTyped(m.linkedin)}<p class="failed" role="alert">{wrongLinkedin}</p>{:else}{@render says(status('linkedin', 'your LinkedIn'))}{/if}
                  </li>
                  {#each m.links as raw, i (i)}
                    {@const site = siteOf(raw)}
                    {@const key = site ? `link:${site.href}` : ''}
                    {@const readable = !!site && all.some((s) => s.key === key)}
                    {@const state = readable ? status(key, site.label) : undefined}
                    <li class="source" class:on={readable && sourceOn(key)}>
                      <button class="tick" role="checkbox" data-choice aria-checked={readable && sourceOn(key)} aria-label="Read this page" disabled={!readable || reading} onclick={() => { switchSource(key) }}>
                        <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4.5 10.5 8.5 14.5 15.5 6" /></svg>
                      </button>
                      <!-- the icon follows the address: nothing to choose, nothing fetched -->
                      <label class="field prefixed">
                        <span class="site" class:known={!!site} aria-hidden="true"><SiteIcon id={site?.id ?? 'globe'} /></span>
                        <input aria-label="A link of yours" placeholder={i ? 'Another page about you' : 'A page about you: a site, GitHub, a portfolio'} value={raw} oninput={(e) => { setLink(i, e) }} onchange={(e) => { setLink(i, e) }} disabled={reading} inputmode="url" autocomplete="off" autocapitalize="none" spellcheck="false" />
                      </label>
                      {#if wrongLink(raw)}
                        <p class="failed" role="alert">{wrongLink(raw)}</p>
                      {:else if state}
                        {@render says(state)}
                      {:else if site && !readable}
                        <p class="done">{site.name}: shown on your profile, not read.</p>
                      {/if}
                    </li>
                  {/each}
                  {#if m.links.every((l) => l.trim()) && m.links.length < 6}
                    <li class="another"><button class="rest" onclick={() => { m.links.push(''); keep() }}><Icon name="plus" size={14} />Another link</button></li>
                  {/if}
                  <li class="source" class:on={!!m.cv.trim() && sourceOn('cv')}>
                    <button class="tick" role="checkbox" data-choice aria-checked={!!m.cv.trim() && sourceOn('cv')} aria-label="Read my CV" disabled={!m.cv.trim() || reading} onclick={() => { switchSource('cv') }}>
                      <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4.5 10.5 8.5 14.5 15.5 6" /></svg>
                    </button>
                    <!-- the file is read in this browser and never sent; the text below it, which the person can change, is what gets read -->
                    {#if m.cvFile}
                      <div class="field file">
                        <span class="site known" aria-hidden="true"><Icon name="file" /></span>
                        <span class="name" title={m.cvFile}>{m.cvFile}</span>
                        <label class="pick">Replace<input bind:this={picker} type="file" accept=".pdf,application/pdf" aria-label="Replace the PDF of your CV" onchange={(e) => { void takeCv(e.currentTarget.files?.[0]) }} disabled={reading || extracting} /></label>
                        <button class="pick" onclick={removeCv} disabled={reading}>Remove</button>
                      </div>
                    {:else}
                      <label class="field drop" class:over={dropping}>
                        <span class="site known" aria-hidden="true"><Icon name={extracting ? 'file' : 'up'} /></span>
                        <span class="ask"><b>{extracting ? 'Reading the PDF in your browser' : 'Add your CV as a PDF'}</b><small>Choose a file or drop it here. It is read in your browser; the file is not sent.</small></span>
                        <input bind:this={picker} type="file" accept=".pdf,application/pdf" aria-label="Add your CV as a PDF" onchange={(e) => { void takeCv(e.currentTarget.files?.[0]) }} disabled={reading || extracting} />
                      </label>
                    {/if}
                    {#if cvWrong}<p class="failed" role="alert">{cvWrong}</p>{/if}
                    {#if m.cvFile || pasting || m.cv}
                      <label class="field text"><textarea bind:this={cvText} rows={m.cvFile ? 5 : 3} aria-label="The text of your CV" placeholder="Paste the text of your CV" bind:value={m.cv} oninput={() => { cvWrong = ''; keep() }} disabled={reading}></textarea></label>
                      {#if m.cvFile}<p class="done">Read from the file. Change anything that came out wrong: this text, not the file, is what gets read.</p>{/if}
                    {:else}
                      <p><button class="rest" onclick={pasteInstead}><Icon name="pen" size={14} />Paste CV text instead</button></p>
                    {/if}
                    {#if m.cv.length > CV_MOST}<p class="done">Only the first {CV_MOST.toLocaleString('en')} characters are read.</p>{:else}{@render says(status('cv', 'your CV'))}{/if}
                  </li>
                </ul>
                {#if nothing}<p class="failed" role="alert">Nothing in that could be read into a profile, and nothing has been filled in. Try another source, or type your profile in yourself.</p>{/if}
              {/if}

              <ul class="promise">
                <li><b>Not saved</b>by this site</li>
                <li><b>Your lines</b>to keep or take out</li>
                <li><b>Kept off your profile</b>photo, age, gender, nationality</li>
              </ul>
              <button class="rest" aria-expanded={where} onclick={() => (where = !where)}><Icon name={where ? 'x' : 'plus'} size={14} />Where it goes</button>
              {#if where}
                <p class="facts where">
                  What you give is sent to this site's server (the text of a CV up to {CV_MOST.toLocaleString('en')} characters; a PDF is read in your browser and the file itself is never
                  sent), which keeps none of it: no file, no log. An
                  address is read by Context.dev, a service that fetches public pages; a LinkedIn profile comes from its own record of it. The text, all of it, then goes to
                  a language model run by Anthropic, which writes the lines. So give only what you want read, and only pages about you. Those two companies receive it, and
                  this demo cannot make them delete it. Your draft lives in this browser tab and is gone when you close it. Employer logos come from this site's server,
                  which keeps its own copies of Context.dev's; only if one cannot be fetched does your browser load it from Context.dev's image server (media.brand.dev).
                </p>
              {/if}
              {#if !m.sample && !reading}
                <p class="other">
                  <button class="rest" onclick={() => { startOver('typed') }}><Icon name="pen" size={14} />Type it in myself</button>
                  <button class="rest" onclick={() => { startOver('sample') }}><Icon name="plus" size={14} />Try it with a sample person</button>
                </p>
              {/if}
            {:else if item === 'you'}
              {#if !m.typed}<button class="edit" aria-pressed={editing} onclick={() => (pressed = !pressed)}><Icon name={editing ? 'check' : 'pen'} size={16} />{editing ? 'Done' : 'Edit'}</button>{/if}
              <div class="band mine"><Mark seed={seedOf(m)} /></div>
              <h2 class:unnamed={!m.name && !editing} role={editing ? 'textbox' : undefined} aria-label={editing ? 'Your name' : undefined} contenteditable={editing ? 'plaintext-only' : undefined} spellcheck="false" data-placeholder="Your name" onblur={(e) => { m.name = typed(e); keep() }} onkeydown={enter} use:text={m.name}></h2>
              <p class="pitch" role={editing ? 'textbox' : undefined} aria-label={editing ? 'What you do' : undefined} contenteditable={editing ? 'plaintext-only' : undefined} data-placeholder="What you do, in a line" onblur={(e) => { m.headline = typed(e); keep() }} onkeydown={enter} use:text={m.headline}></p>
              {#if editing}
                <p class="chips">
                  {#each LEVELS as level (level)}
                    <button class="chip want" data-choice aria-pressed={m.level === level} onclick={() => { m.level = level; keep() }}>{#if m.level === level}<Icon name="check" size={14} />{/if}{level}</button>
                  {/each}
                </p>
              {:else if m.field || m.level}
                <p class="facts">{[m.field, m.level].filter(Boolean).join(' · ')}{#if !m.typed}<span class="guess">our reading, yours to change with Edit</span>{/if}</p>
              {/if}
              {#if links.length}
                <p class="links">
                  {#each links as site (site.href)}<a href={site.href} target="_blank" rel="noopener" title={site.name}><SiteIcon id={site.id} size={16} />{site.label}</a>{/each}
                </p>
              {/if}
              {#if m.can.length}
                <ul class="tell" aria-label="What you can do">
                  {#each m.can.filter((f, i) => i < SHOWN || more || on(f)) as f (f.id)}
                    <li class:on={on(f)}>
                      <button class="tick" role="checkbox" data-choice aria-checked={on(f)} aria-label="Keep this line" onclick={() => { toggle(f) }}>
                        <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4.5 10.5 8.5 14.5 15.5 6" /></svg>
                      </button>
                      {#if editing}
                        <span class="say"><b role="textbox" tabindex="0" aria-label="Reword this line" contenteditable="plaintext-only" spellcheck="false" onblur={(e) => { reword(f, e) }} onkeydown={enter} use:text={f.text}></b></span>
                      {:else}
                        <button class="say" aria-expanded={detail === f.id} disabled={!f.from} onclick={() => (detail = detail === f.id ? null : f.id)}><b>{f.text}</b></button>
                      {/if}
                      {#if detail === f.id && f.from}<p class="behind">From {sourceLabel(m, f.source)}: “{f.from}”</p>{/if}
                    </li>
                  {/each}
                </ul>
                {#if hidden && !more}
                  <button class="rest" onclick={() => (more = true)}><Icon name="plus" size={14} />{hidden} more we read. Not on your profile unless you tick {hidden === 1 ? 'it' : 'them'}</button>
                {/if}
              {/if}
              {#if editing || m.typed || more}
                <form onsubmit={(e) => { e.preventDefault(); add('can') }}>
                  <input bind:value={own} placeholder="Add something you can do, in your own words" aria-label="Add something you can do" autocomplete="off" />
                </form>
              {/if}
            {:else if item === 'know'}
              <h2>What you know</h2>
              <p class="chips">
                {#each m.skills as f (f.id)}
                  <button class="chip want known" data-choice aria-pressed={on(f)} title={f.from ? `From ${sourceLabel(m, f.source)}: “${f.from}”` : 'Added by you'} onclick={() => { toggle(f) }}>{#if on(f)}<Icon name="check" size={14} />{/if}{f.text}</button>
                {/each}
              </p>
              <form onsubmit={(e) => { e.preventDefault(); add('skills') }}>
                <input bind:value={own} placeholder="Add a tool, a method or a technology" aria-label="Add something you know" autocomplete="off" />
              </form>
              {#if m.roles.length}
                <h2 class="second">Work and projects</h2>
                <ul class="tell" aria-label="Work and projects">
                  {#each m.roles as f (f.id)}
                    <li class:on={on(f)}>
                      <button class="tick" role="checkbox" data-choice aria-checked={on(f)} aria-label="Keep this line" onclick={() => { toggle(f) }}>
                        <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4.5 10.5 8.5 14.5 15.5 6" /></svg>
                      </button>
                      <span class="say"><b>{f.text}</b>{#if f.when}<small>{f.when}</small>{/if}</span>
                    </li>
                  {/each}
                </ul>
              {/if}
            {:else if item === 'want'}
              <h2>What are you looking for?</h2>
              <p class="chips">
                {#each FIELDS as field (field)}
                  <button class="chip want" data-choice aria-pressed={m.wants.includes(field)} onclick={() => { want(field) }}>{#if m.wants.includes(field)}<Icon name="check" size={14} />{/if}{field}</button>
                {/each}
              </p>
              <label class="field words"><textarea rows="2" bind:value={m.looking} oninput={keep} placeholder="In your own words, if you like" aria-label="What you are looking for, in your own words"></textarea></label>
              <h2 class="second">What suits you</h2>
              <p class="chips">
                {#each LEVELS as level (level)}
                  <button class="chip want" data-choice aria-pressed={m.level === level} onclick={() => { m.level = m.level === level ? '' : level; keep() }}>{#if m.level === level}<Icon name="check" size={14} />{/if}{level}</button>
                {/each}
              </p>
              <p class="chips">
                {#each PLACES as place (place)}
                  <button class="chip want" data-choice aria-pressed={m.place === place} onclick={() => { m.place = m.place === place ? '' : place; keep() }}>{#if m.place === place}<Icon name="check" size={14} />{/if}{place}</button>
                {/each}
                <button class="chip want" data-choice aria-pressed={m.finnish} onclick={() => { m.finnish = !m.finnish; keep() }}>{#if m.finnish}<Icon name="check" size={14} />{/if}I work in Finnish too</button>
                <button class="chip want" data-choice aria-pressed={m.abroad} onclick={() => { m.abroad = !m.abroad; keep() }}>{#if m.abroad}<Icon name="check" size={14} />{/if}I live outside Finland now</button>
              </p>
            {:else}
              <h2>Who would you like to meet?</h2>
              {#if offered.length}
                <p class="facts">
                  {#if offered.some((x) => x.shared.length)}
                    Employers at this event with a role that asks for something you know, those asking for most of it first. Tick any, or none.
                  {:else}
                    No employer at this event has a role asking for what you listed. These have a role in a field you chose. Tick any, or none.
                  {/if}
                </p>
                <ul class="tell meet" aria-label="Employers at this event">
                  {#each offered as match (match.employer.brief.id)}
                    {@const id = match.employer.brief.id}
                    <li class:on={m.meet.includes(id)}>
                      <button class="tick" role="checkbox" data-choice aria-checked={m.meet.includes(id)} aria-label="Meet {nameOf(match.employer.brief)}" onclick={() => { pick(id) }}>
                        <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4.5 10.5 8.5 14.5 15.5 6" /></svg>
                      </button>
                      <span class="say">
                        <button class="name" data-choice onclick={() => { pick(id) }}><span class="tile"><Logo brief={match.employer.brief} small /></span>{nameOf(match.employer.brief)}</button>
                        {#if match.employer.brief.website}<a href={match.employer.brief.website} target="_blank" rel="noopener" aria-label="{nameOf(match.employer.brief)}'s own site"><Icon name="out" size={14} /></a>{/if}
                      </span>
                      <p class="behind"><b>{match.role}</b>{#if match.reasons.length}<br />{match.reasons.join(' · ')}{/if}</p>
                    </li>
                  {/each}
                </ul>
              {:else}
                <p class="pitch">No employer at this event has a role in the fields you chose. You can still finish, and visit anyone.</p>
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
            {#if terms.length}<span>{terms.join(' · ')}</span>{/if}
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
      {#if undo}<button class="undo" onclick={takeBack}>Undo <kbd>Z</kbd></button>{/if}
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
    box-shadow: 0 0 0 1px color-mix(in srgb, currentColor 22%, transparent);
    border-radius: 22%;
  }
  .band.mine {
    width: 5.5rem;
    height: 5.5rem;
    margin-bottom: var(--s4);
  }
  .unnamed {
    display: none;
  }
  .guess {
    margin-left: var(--s2);
    padding: 0.15em 0.55em;
    border-radius: 99px;
    background: var(--wash);
    font-size: var(--t-xs);
    white-space: nowrap;
  }
  .links,
  .sites {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s2) var(--s4);
  }
  .links {
    margin-top: var(--s3);
    font-size: var(--t-sm);
  }
  .links a {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    min-height: 2rem;
    font-weight: 600;
    text-decoration: none;
  }
  .links a:hover {
    text-decoration: underline;
  }
  .sites {
    margin-top: var(--s2);
    opacity: 0.85;
  }

  /* what has arrived so far, while the reading runs */
  .live {
    display: grid;
    grid-template-columns: 3rem 1fr;
    align-items: center;
    column-gap: var(--s3);
    margin-top: var(--s3);
    line-height: 1.3;
  }
  .live .tile {
    grid-row: 1 / 3;
    margin: 0;
  }
  .live b {
    font-size: var(--t-lg);
    letter-spacing: -0.01em;
  }
  .live span:last-child {
    color: var(--ink-2);
  }

  .sources {
    margin-top: var(--s4);
  }
  .source {
    align-items: start;
  }
  /* here the tick is centred on its field, which is taller than a line of text */
  .source .tick {
    margin-top: calc((3.25rem + 4px - 1.5rem) / 2);
  }
  .rest {
    text-align: left;
  }
  /* a field of this flow, in the shape of the company flow's own line of text */
  .field {
    display: flex;
    align-items: center;
    gap: var(--s2);
    min-height: 3.25rem;
    padding: 0 var(--s4);
    border: 2px solid var(--line);
    border-radius: var(--r2);
    background: var(--ground);
    color: var(--ink-2);
    font-size: var(--t-lg);
  }
  .field:focus-within {
    border-color: var(--ink);
  }
  .field input,
  .field textarea {
    flex: 1;
    min-width: 0;
    padding: var(--s3) 0;
    border: 0;
    outline: 0;
    background: none;
    color: var(--ink);
    font: inherit;
    resize: vertical;
  }
  .field textarea {
    font-size: var(--t-md);
    line-height: 1.4;
  }
  /* a field whose first part is fixed: the prefix sits in the same box, quieter, and cannot be typed over */
  .prefixed {
    gap: 0;
  }
  .site {
    display: grid;
    margin-right: var(--s2);
    opacity: 0.45;
  }
  .site.known {
    opacity: 1;
    color: var(--ink);
  }
  .words {
    margin-top: var(--s4);
  }
  /* a CV: the box that takes a file, the file once taken, and the text under either, all in the tick's second column */
  .source > .text,
  .source > .field ~ .field {
    grid-column: 2;
    margin-top: var(--s2);
  }
  .drop,
  .file {
    position: relative;
  }
  .drop {
    border-style: dashed;
    cursor: pointer;
  }
  .drop.over {
    border-color: var(--ink);
    border-style: solid;
  }
  .ask {
    display: grid;
    gap: 2px;
    min-width: 0;
    padding: var(--s3) 0;
    line-height: 1.3;
  }
  .ask b {
    color: var(--ink);
    font-size: var(--t-md);
    font-weight: 600;
  }
  .ask small {
    font-size: var(--t-sm);
  }
  /* the chooser itself is not drawn, and is still what the keyboard lands on and a screen reader names */
  .field input[type='file'] {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    opacity: 0;
    pointer-events: none;
  }
  .name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    color: var(--ink);
    font-size: var(--t-md);
    font-weight: 600;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .pick {
    flex: none;
    min-height: 2.75rem;
    display: inline-flex;
    align-items: center;
    padding: 0 var(--s2);
    border: 0;
    border-radius: var(--r1);
    background: none;
    color: var(--ink-2);
    font-size: var(--t-sm);
    font-weight: 600;
    cursor: pointer;
  }
  .pick:hover,
  .pick:focus-within,
  .pick:focus-visible {
    color: var(--ink);
    text-decoration: underline;
  }
  .source p {
    grid-column: 2;
    margin: var(--s1) 0 0;
    font-size: var(--t-sm);
  }
  .done {
    color: var(--ink-2);
  }
  .source .drafting {
    gap: var(--s2);
  }
  .source .drafting i {
    width: 0.5rem;
    height: 0.5rem;
  }
  .tick:disabled {
    opacity: 0.45;
    cursor: default;
  }

  .promise {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--s3);
    margin-top: var(--s5);
    font-size: var(--t-sm);
    line-height: 1.3;
    color: var(--ink-2);
  }
  .promise b {
    display: block;
    color: var(--ink);
  }
  .where {
    max-width: 62ch;
    line-height: 1.5;
  }
  .other {
    display: flex;
    flex-wrap: wrap;
    gap: 0 var(--s5);
    margin-top: var(--s2);
  }
  .sample {
    margin-top: var(--s4);
    color: var(--ink-2);
  }
  .sample b {
    color: var(--ink);
  }
  /* what a person knows is many small things: kept ones are outlined, not filled, so ten of them are not a wall */
  .known[aria-pressed='true'] {
    border-color: var(--ink);
    background: var(--ground);
    color: var(--ink);
  }
  .meet .say {
    justify-content: flex-start;
  }
  /* an employer's name is as dark ticked or not, and pressing it ticks the row */
  .meet .name {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    padding: 0;
    border: 0;
    background: none;
    font-size: var(--t-lg);
    font-weight: 600;
    letter-spacing: -0.01em;
    line-height: 1.25;
    text-align: left;
    color: var(--ink);
  }
  .another {
    border-bottom: 0;
    padding: 0 0 0 calc(1.5rem + var(--s3));
  }
  .demo {
    max-width: 44ch;
    font-size: var(--t-md);
    opacity: 0.85;
  }
  .meet .say a {
    display: grid;
    place-items: center;
    width: 2rem;
    height: 2rem;
    color: var(--ink-2);
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
  @media (max-width: 40rem) {
    .promise {
      grid-template-columns: 1fr;
      gap: var(--s2);
    }
    .promise b {
      display: inline;
      margin-right: var(--s2);
    }
    .field {
      font-size: var(--t-md);
    }
    /* a file's name has the line to itself; what can be done with the file goes under it */
    .file {
      flex-wrap: wrap;
      row-gap: 0;
      padding-top: var(--s1);
    }
    .name {
      flex-basis: calc(100% - 3rem);
    }
    .file .pick:first-of-type {
      padding-left: 0;
    }
  }
</style>
