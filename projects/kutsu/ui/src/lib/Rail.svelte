<script lang="ts">
  import { untrack } from 'svelte'
  import { when } from './format'
  import Icon from './Icon.svelte'
  import Logo from './Logo.svelte'
  import { app, go, nameOf, research, reviewOf, route } from './state.svelte'
  import type { Brief, Status } from './types'

  // The city's side of the screen: which employers there are, and where each brief stands.
  // the chosen shortcut; -1 is none, which lists every company
  let group = $state(0)
  let query = $state('')

  const groups = $derived.by(() => {
    const preset = new Set(app.presets.flatMap((p) => p.ids))
    const find = (id: string) => app.briefs.find((b) => b.id === id)
    return [
      ...app.presets.map((p) => ({ label: p.title, items: p.ids.map(find).filter((b): b is Brief => !!b) })),
      { label: 'Hiring in Espoo', items: app.briefs.filter((b) => b.in_espoo_data && !preset.has(b.id)) },
      { label: 'Searched', items: app.briefs.filter((b) => !b.in_espoo_data && !preset.has(b.id)) },
    ].filter((g) => g.items.length)
  })
  const shown = $derived(group < 0 ? app.briefs : (groups[group]?.items ?? []))
  // follow the open company into its group, for example after a live search, unless every company is listed
  $effect(() => {
    const at = groups.findIndex((g) => g.items.some((b) => b.id === route().id))
    if (at >= 0 && untrack(() => group) >= 0) group = at
  })

  const SECTIONS: [Status, string][] = [['draft', 'To invite'], ['invited', 'Invited'], ['joined', 'Signed up']]
  const matches = (b: Brief) => nameOf(b).toLowerCase().includes(query.trim().toLowerCase())
  const sections = $derived(
    SECTIONS.map(([status, label]) => ({
      label,
      status,
      // fresh funding and growth news first: those are the companies to reach before they come looking
      items: shown
        .filter((b) => reviewOf(b).status === status && matches(b))
        .sort((a, b) => (fresh(b)?.date ?? '').localeCompare(fresh(a)?.date ?? '') || b.signals.length - a.signals.length),
    })).filter((s) => s.items.length),
  )
  const confirmed = $derived(shown.filter((b) => reviewOf(b).status === 'joined').length)
  /** The newest funding or growth statement, the reason to reach out now. */
  const fresh = (b: Brief) =>
    b.signals.filter((s) => (s.type === 'funding' || s.type === 'growth') && s.date).sort((x, y) => y.date.localeCompare(x.date))[0]
  const line = (b: Brief) => {
    const news = fresh(b)
    if (news) return `${news.type === 'funding' ? 'Funding' : 'Growth'}, ${when(news.date)}`
    return b.signals.length < 3 ? 'Little public record' : reviewOf(b).needs[0]?.title || 'No need drafted'
  }

  function submit(e: SubmitEvent) {
    e.preventDefault()
    const q = query.trim()
    const found = app.briefs.filter((b) => nameOf(b).toLowerCase() === q.toLowerCase())
    if (!q) return
    query = ''
    if (found.length === 1) go(found[0].id)
    else research(q)
  }
</script>

<aside>
  <div class="head">
    <a class="name" href="#/">Kutsu</a>
    <p>Plan the next event from the last ones: who to invite, and a sign-up that is already filled in.</p>
  </div>
  <a class="events" href="#/" aria-current={route().id ? undefined : 'page'}>Events</a>

  <form onsubmit={submit}>
    <Icon name="search" size={18} />
    <input bind:value={query} placeholder="Find or add any company" aria-label="Find or add any company" autocomplete="off" spellcheck="false" />
    {#if query.trim()}<button type="submit">Research</button>{/if}
  </form>

  <div class="groups">
    {#each groups as g, i}
      <button aria-pressed={i === group} title={i === group ? 'Show every company' : undefined} onclick={() => (group = i === group ? -1 : i)}>{g.label}<span>{g.items.length}</span></button>
    {/each}
  </div>
  <p class="count">{confirmed} of {shown.length} signed up</p>

  <nav>
    {#each sections as section (section.status)}
      <h2 class={section.status}>{section.label}<span>{section.items.length}</span></h2>
      <ul>
        {#each section.items as b (b.id)}
          <li>
            <a href="#/{encodeURIComponent(b.id)}" class:on={b.id === route().id} aria-current={b.id === route().id ? 'page' : undefined}>
              <span class="tile"><Logo brief={b} small /></span>
              <span class="who">
                <b>{nameOf(b)}</b>
                <small>{line(b)}</small>
              </span>
            </a>
          </li>
        {/each}
      </ul>
    {:else}
      <p class="empty">No company here is called “{query.trim()}”. Press Enter to research it.</p>
    {/each}
  </nav>
</aside>

<style>
  aside {
    position: sticky;
    top: 0;
    display: flex;
    flex-direction: column;
    gap: var(--s4);
    height: 100dvh;
    padding: var(--s5) var(--s4) 0;
    overflow-y: auto;
    background: var(--city);
    color: var(--city-ink);
    scrollbar-color: var(--city-line) transparent;
  }
  aside :focus-visible {
    outline-color: var(--city-ink);
  }
  .head {
    padding: 0 var(--s2);
  }
  .name {
    font: 800 1.5rem / 1 var(--display);
    letter-spacing: -0.03em;
    text-decoration: none;
  }
  .events {
    padding: var(--s2) var(--s3);
    border-radius: var(--r1);
    font-weight: 600;
    text-decoration: none;
  }
  .events:hover {
    background: var(--city-raise);
  }
  .events[aria-current] {
    background: var(--city-ink);
    color: var(--city);
  }
  .head p {
    margin-top: var(--s2);
    font-size: var(--t-sm);
    line-height: 1.35;
    color: var(--city-dim);
  }
  form {
    display: flex;
    align-items: center;
    gap: var(--s2);
    padding: 0 var(--s2) 0 var(--s3);
    border: 1px solid var(--city-line);
    border-radius: var(--r1);
    background: var(--city-raise);
    color: var(--city-dim);
  }
  form:focus-within {
    border-color: var(--city-ink);
    color: var(--city-ink);
  }
  input {
    flex: 1;
    min-width: 0;
    height: 2.75rem;
    border: 0;
    outline: 0;
    background: none;
    color: var(--city-ink);
  }
  input::placeholder {
    color: var(--city-dim);
  }
  form button {
    height: 2rem;
    padding: 0 var(--s3);
    border: 0;
    border-radius: 4px;
    background: var(--city-ink);
    color: var(--city);
    font-size: var(--t-sm);
    font-weight: 700;
  }
  .groups {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s1);
  }
  .groups button {
    display: inline-flex;
    align-items: baseline;
    gap: var(--s2);
    padding: var(--s1) var(--s3);
    border: 1px solid var(--city-line);
    border-radius: 99px;
    background: none;
    color: var(--city-dim);
    font-size: var(--t-sm);
    font-weight: 600;
  }
  .groups button:hover {
    color: var(--city-ink);
  }
  .groups button[aria-pressed='true'] {
    border-color: var(--city-ink);
    background: var(--city-ink);
    color: var(--city);
  }
  .groups span {
    font-size: var(--t-xs);
    opacity: 0.75;
  }
  .count {
    margin-top: calc(-1 * var(--s2));
    padding: 0 var(--s2);
    font-size: var(--t-xs);
    color: var(--city-dim);
  }
  nav {
    flex: 1;
    margin: 0 calc(-1 * var(--s2));
    padding-bottom: var(--s6);
  }
  h2 {
    display: flex;
    align-items: center;
    gap: var(--s2);
    margin-top: var(--s4);
    padding: var(--s2) var(--s4);
    font: 700 var(--t-xs) / 1 var(--text);
    letter-spacing: 0.02em;
    color: var(--city-dim);
  }
  h2::before {
    content: '';
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    border: 2px solid currentColor;
  }
  h2.invited::before {
    border-color: oklch(82% 0.15 80);
    background: oklch(82% 0.15 80);
  }
  h2.joined::before {
    border-color: oklch(80% 0.17 155);
    background: oklch(80% 0.17 155);
  }
  h2:first-child {
    margin-top: 0;
  }
  h2 span {
    margin-left: auto;
    font-weight: 500;
  }
  li a {
    display: grid;
    grid-template-columns: 2.75rem 1fr;
    align-items: center;
    gap: var(--s3);
    padding: var(--s2);
    border-radius: var(--r1);
    text-decoration: none;
    transition: background 0.12s;
  }
  li a:hover {
    background: var(--city-raise);
  }
  li a.on {
    background: var(--city-ink);
    color: var(--city);
  }
  .tile {
    width: 2.75rem;
    height: 2.75rem;
    padding: 5px;
    border-radius: var(--r1);
    overflow: hidden;
    background: #fff;
    font-size: 0.8rem;
  }
  .tile:has(:global(.dark)) {
    background: #14151a;
  }
  .who {
    display: grid;
    min-width: 0;
    line-height: 1.25;
  }
  .who b {
    font-weight: 600;
  }
  .who b,
  .who small {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
  .who small {
    font-size: var(--t-xs);
    color: var(--city-dim);
  }
  .on small {
    color: color-mix(in oklch, var(--city) 70%, var(--city-ink));
  }
  .empty {
    padding: var(--s4);
    font-size: var(--t-sm);
    color: var(--city-dim);
  }
  @media (max-width: 820px) {
    aside {
      position: static;
      height: auto;
      padding-bottom: var(--s3);
    }
    .head p,
    .count,
    h2 {
      display: none;
    }
    nav {
      display: flex;
      gap: var(--s1);
      margin: 0 calc(-1 * var(--s4));
      padding: 0 var(--s4) var(--s2);
      overflow-x: auto;
      scrollbar-width: none;
    }
    ul {
      display: flex;
      gap: var(--s1);
    }
    li a {
      grid-template-columns: 2.75rem;
      width: 5.5rem;
      justify-items: center;
      text-align: center;
    }
    .who small {
      display: none;
    }
    .who b {
      font-size: var(--t-xs);
    }
  }
</style>
