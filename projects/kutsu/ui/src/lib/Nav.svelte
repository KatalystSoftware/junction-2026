<script lang="ts">
  import { applications, decisionOf } from './manage.svelte'
  import { app, route } from './state.svelte'

  // The primary navigation of Espoo's side: what the product holds, in the order an organiser thinks.
  // Each item is a real page with its own address, and the one you are in is marked. The name is the
  // way home, as on most sites, so home has no item of its own. The two sign-ups are not here: a company
  // or a person opening an invitation sees their own flow, not the back office.
  const at = $derived(route())
  const here = $derived(
    at.page === 'applications' || at.tab === 'applications'
      ? 'applications'
      : at.page === 'events' || at.event
        ? 'events'
        : at.page === 'companies' || at.id
          ? 'companies'
          : at.page === 'pool'
            ? 'pool'
            : 'home',
  )
  const waiting = $derived(applications.list.filter((a) => !decisionOf('espoo', a.id)).length)
  const items = $derived([
    { key: 'events', label: 'Events', href: '#/events', count: '' },
    { key: 'companies', label: 'Companies', href: '#/companies', count: String(app.briefs.length) },
    { key: 'pool', label: 'Talent pool', href: '#/pool', count: app.pool.people ? app.pool.people.toLocaleString('en') : '' },
    { key: 'applications', label: 'Applications', href: '#/applications', count: waiting ? String(waiting) : '' },
  ])
</script>

<nav aria-label="Kutsu">
  <a class="name" href="#/" aria-current={here === 'home' ? 'page' : undefined} aria-label="Kutsu, home">Kutsu</a>
  <ul>
    {#each items as item (item.key)}
      <li>
        <a href={item.href} aria-current={here === item.key ? 'page' : undefined}>{item.label}{#if item.count}<span>{item.count}</span>{/if}</a>
      </li>
    {/each}
  </ul>
  <p>City of Espoo, recruitment events</p>
</nav>

<style>
  nav {
    position: sticky;
    top: 0;
    display: flex;
    flex-direction: column;
    gap: var(--s5);
    height: 100dvh;
    padding: var(--s5) var(--s3) var(--s4);
    background: var(--city);
    color: var(--city-ink);
  }
  nav :focus-visible {
    outline-color: var(--city-ink);
  }
  .name {
    padding: 0 var(--s3);
    font: 800 1.5rem / 1 var(--display);
    letter-spacing: -0.03em;
    text-decoration: none;
  }
  ul {
    display: grid;
    gap: 2px;
  }
  li a {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--s3);
    min-height: 2.75rem;
    padding: var(--s3);
    border-radius: var(--r1);
    font-weight: 600;
    line-height: 1.2;
    text-decoration: none;
    transition: background 0.12s;
  }
  li a:hover {
    background: var(--city-raise);
  }
  li a[aria-current] {
    background: var(--city-ink);
    color: var(--city);
  }
  li span {
    font-size: var(--t-xs);
    font-weight: 500;
    opacity: 0.75;
  }
  p {
    margin-top: auto;
    padding: 0 var(--s3);
    font-size: var(--t-xs);
    color: var(--city-dim);
  }
  /* on a phone the navigation is a bar across the top, its items in one row that scrolls */
  @media (max-width: 820px) {
    nav {
      position: static;
      flex-direction: row;
      align-items: center;
      gap: var(--s3);
      height: auto;
      /* the demo's own button sits at the top right */
      padding: var(--s2) 4.75rem var(--s2) var(--s3);
    }
    .name {
      padding: 0 var(--s1);
      font-size: 1.25rem;
    }
    ul {
      display: flex;
      flex: 1;
      min-width: 0;
      overflow-x: auto;
      scrollbar-width: none;
    }
    li a {
      white-space: nowrap;
      padding: var(--s2) var(--s3);
    }
    li span,
    p {
      display: none;
    }
  }
</style>
