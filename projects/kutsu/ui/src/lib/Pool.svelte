<script lang="ts">
  import { slug, some, suggested } from './events'
  import { when } from './format'
  import Icon from './Icon.svelte'
  import { app } from './state.svelte'

  // The talent pool: the people who came to Espoo's earlier events, as counts. Nobody is shown as a
  // person anywhere here: a field has how many do that work, how many more want to move into it, and how
  // many employers look for it, which is what a proposed event is made of.
  const ideas = $derived(suggested())
  const fields = $derived(
    Object.entries(app.pool.fields)
      .map(([name, f]) => ({ name, ...f, employers: ideas.find((p) => p.title === name)?.employers.length ?? 0 }))
      .sort((a, b) => b.people - a.people),
  )
  const most = $derived(Math.max(1, ...fields.map((f) => f.people)))
  const sum = (pick: (f: (typeof fields)[number]) => number) => fields.reduce((n, f) => n + pick(f), 0)
  const levels = $derived(Object.keys(fields[0]?.levels ?? {}).map((level) => ({ level, n: sum((f) => f.levels[level] ?? 0) })))
</script>

<main>
  <header>
    <h1>Talent pool</h1>
    <p><span class="sample">sample data</span></p>
  </header>

  <p class="total">
    <span><b>{app.pool.people.toLocaleString('en')}</b> people</span>
    <span><b>{some(sum((f) => f.english))}</b> work in English</span>
    <span><b>{some(sum((f) => f.finnish))}</b> in Finnish</span>
    <span><b>{some(sum((f) => f.abroad))}</b> live abroad</span>
  </p>
  {#if levels.length}
    <div class="levels" aria-hidden="true">
      {#each levels as { level, n }, i (level)}<span style:flex-grow={n} style:--step={i} title="{level}: {some(n)}"></span>{/each}
    </div>
    <p class="facts">{#each levels as { level, n } (level)}<span><b>{some(n)}</b> {level.toLowerCase()}</span>{/each}</p>
  {/if}

  <section>
    <h2>By field of work</h2>
    <ul class="fields">
      {#each fields as f (f.name)}
        <li>
          {#if f.employers}
            <a href="#/event/{slug(f.name)}">{f.name}<Icon name="flat" size={14} /></a>
          {:else}
            <span class="name">{f.name}</span>
          {/if}
          <small>{f.wanting ? `${some(f.wanting)} more want to move into it` : ''}{f.wanting && f.employers ? ' · ' : ''}{f.employers ? `${String(f.employers)} employers look for it` : ''}</small>
          <span class="meter"><span style:width="{(f.people / most) * 100}%"></span></span>
          <b>{f.people}</b>
        </li>
      {/each}
    </ul>
  </section>

  <section>
    <h2>They came to</h2>
    <ol class="past">
      {#each app.pool.events.toReversed() as event (event.id)}
        <li>
          <a href={event.url} target="_blank" rel="noopener">{event.name}<Icon name="out" size={14} /></a>
          <small>{[when(event.date), event.where === 'Online' ? 'online' : event.where, event.published].filter(Boolean).join(', ')}</small>
          <b>{event.people.toLocaleString('en')}</b>
        </li>
      {/each}
    </ol>
    <p class="note">{app.pool.note} The events are real and link to their pages.</p>
  </section>
</main>

<style>
  main {
    display: grid;
    gap: var(--s6);
    max-width: 68rem;
    padding: var(--s7) var(--s7) var(--s8) var(--s6);
  }
  header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--s3) var(--s4);
  }
  h1 {
    font: 800 var(--t-2xl) / 0.95 var(--display);
    letter-spacing: -0.035em;
  }
  h2 {
    font-size: var(--t-lg);
    letter-spacing: -0.01em;
  }
  .sample {
    padding: 0.2em 0.6em;
    border-radius: 99px;
    background: var(--wash);
    font: 600 var(--t-xs) / 1.4 var(--text);
    color: var(--ink-2);
    white-space: nowrap;
  }
  .total,
  .facts {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s1) var(--s5);
    color: var(--ink-2);
  }
  .total b {
    color: var(--ink);
  }
  .total span:first-child b {
    margin-right: var(--s1);
    font: 800 var(--t-xl) / 1 var(--display);
    letter-spacing: -0.03em;
  }
  .total span {
    align-self: baseline;
  }
  .levels {
    display: flex;
    gap: 2px;
    max-width: 40rem;
  }
  .levels span {
    flex-basis: 0;
    min-width: 4px;
    height: 0.625rem;
    border-radius: 3px;
    /* one hue, lighter to darker as the level rises */
    background: color-mix(in oklch, var(--city) calc(40% + var(--step) * 20%), var(--wash));
  }
  .facts {
    margin-top: calc(-1 * var(--s4));
    font-size: var(--t-sm);
  }
  .facts b {
    color: var(--ink);
  }
  .fields,
  .past {
    margin-top: var(--s3);
  }
  .fields li {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(6rem, 16rem) 3rem;
    align-items: center;
    gap: 0 var(--s4);
    min-height: 3.25rem;
    padding: var(--s2) 0;
    border-top: 1px solid var(--line);
    line-height: 1.25;
  }
  .fields a,
  .name {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    justify-self: start;
    font-weight: 600;
    text-decoration: none;
  }
  .fields a :global(svg) {
    color: var(--ink-2);
    transition: transform 0.2s var(--ease);
  }
  .fields a:hover :global(svg) {
    transform: translateX(3px);
    color: var(--ink);
  }
  .fields small {
    grid-column: 1;
    grid-row: 2;
    font-size: var(--t-xs);
    color: var(--ink-2);
  }
  .meter {
    grid-row: 1 / 3;
    grid-column: 2;
    height: 0.5rem;
    border-radius: 99px;
    background: var(--line);
  }
  .meter span {
    display: block;
    height: 100%;
    border-radius: 99px;
    background: var(--city);
  }
  .fields b {
    grid-row: 1 / 3;
    grid-column: 3;
    text-align: right;
  }
  .past li {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 0 var(--s4);
    padding: var(--s2) 0;
    border-top: 1px solid var(--line);
    line-height: 1.3;
  }
  .past a {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    justify-self: start;
    min-height: 2rem;
    font-weight: 600;
    text-decoration: none;
  }
  .past a:hover {
    text-decoration: underline;
  }
  .past small {
    grid-column: 1;
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  .past b {
    grid-row: 1 / 3;
    grid-column: 2;
  }
  .note {
    max-width: 70ch;
    margin-top: var(--s4);
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  @media (max-width: 820px) {
    main {
      padding: var(--s6) var(--s4) var(--s7);
    }
    .fields li {
      grid-template-columns: minmax(0, 1fr) 5rem 2.5rem;
    }
  }
</style>
