<script lang="ts">
  import { upcoming } from './events'
  import { app, joinPath, reviewOf, route, saveReview } from './state.svelte'
  import type { Review } from './types'

  // The demo's own control, apart from the product: move between the three people Kutsu is for, and
  // put example sign-ups in or take every sign-up out. It stays visible, because someone trying the
  // demo alone has nobody to tell them the other two views exist.
  let open = $state(false)
  let busy = $state(false)
  const company = $derived(route().id || app.presets[0]?.ids[0] || '')
  $effect(() => {
    if (!open) sure = false
  })

  const ago = (hours: number) => new Date(Date.now() - hours * 36e5).toISOString()
  /** Mark some of the upcoming event's employers as sent their profile, and some as having confirmed it. Each is flagged as an example. */
  async function fill() {
    const preset = app.presets[0]
    if (!preset) return
    busy = true
    const waiting = upcoming(preset).employers.filter((e) => reviewOf(e.brief).status === 'draft')
    const saves: Promise<void>[] = []
    waiting.forEach(({ brief }, i) => {
      const draft = reviewOf(brief)
      const confirms = i % 5 === 1 && draft.needs.length > 0
      if (!confirms && i % 5 !== 0 && i % 5 !== 3) return
      const review: Review = confirms
        ? {
            ...draft,
            status: 'joined',
            needs: draft.needs.map((n) => ({ ...n, ok: true })),
            about_ok: true,
            told: brief.card.tell.slice(0, 3).map((t) => t.id),
            wants: i % 2 ? ['1:1 meetings with candidates', 'A virtual booth'] : ['1:1 meetings with candidates'],
            invited_at: ago(60 + i * 3),
            joined_at: ago(8 + i * 2),
            signed: [upcoming(preset).slug],
            example: true,
          }
        : { ...draft, status: 'invited', invited_at: ago(20 + i * 4), example: true }
      saves.push(saveReview(brief.id, review))
    })
    await Promise.all(saves)
    busy = false
    open = false
  }
  /** Take out every sign-up, real or example: each company is back to the draft it starts from. Asked twice, since it cannot be undone. */
  let sure = $state(false)
  async function reset() {
    if (!sure) return void (sure = true)
    sure = false
    busy = true
    await fetch('reviews', { method: 'DELETE' })
    app.reviews = {}
    busy = false
    open = false
  }
</script>

<svelte:window onkeydown={(e) => { if (e.key === 'Escape') open = false }} onclick={() => (open = false)} />

<div class="demo" role="presentation" onclick={(e) => { e.stopPropagation() }}>
  <button class="toggle" aria-expanded={open} onclick={() => (open = !open)}>Demo</button>
  {#if open}
    <div class="menu">
      <p>See it as</p>
      <a href="#/" onclick={() => (open = false)}>Espoo's organiser</a>
      <a href={joinPath(company)} onclick={() => (open = false)}>An invited company</a>
      <a href="./esittely/#/join" target="_blank" rel="noopener" onclick={() => (open = false)}>An invited person</a>
      <p>Sign-ups</p>
      <button disabled={busy} onclick={fill}>Fill in example sign-ups</button>
      <button disabled={busy} onclick={reset}>{sure ? 'Press again to clear them all' : 'Clear every sign-up'}</button>
    </div>
  {/if}
</div>

<style>
  .demo {
    position: fixed;
    top: var(--s3);
    right: var(--s3);
    z-index: 30;
    display: grid;
    justify-items: end;
    gap: var(--s2);
    font-size: var(--t-sm);
  }
  /* dark on any ground: this sits over the city's screen and over every company's colour */
  .toggle,
  .menu {
    border: 0;
    background: oklch(21% 0.03 264 / 0.9);
    color: #fff;
    backdrop-filter: blur(8px);
  }
  .toggle {
    min-height: 2rem;
    padding: 0 var(--s3);
    border-radius: 99px;
    font-weight: 700;
  }
  .toggle:focus-visible,
  .menu :focus-visible {
    outline-color: #fff;
  }
  .menu {
    display: grid;
    min-width: 14rem;
    padding: var(--s2);
    border-radius: var(--r2);
    box-shadow: var(--lift);
  }
  .menu p {
    padding: var(--s2) var(--s3) var(--s1);
    font-size: var(--t-xs);
    font-weight: 600;
    opacity: 0.7;
  }
  .menu a,
  .menu button {
    min-height: 2.5rem;
    padding: 0 var(--s3);
    border: 0;
    border-radius: var(--r1);
    background: none;
    color: inherit;
    font-weight: 600;
    line-height: 2.5rem;
    text-align: left;
    text-decoration: none;
  }
  .menu a:hover,
  .menu button:hover:not(:disabled) {
    background: oklch(100% 0 0 / 0.14);
  }
  .menu button:disabled {
    opacity: 0.5;
  }
</style>
