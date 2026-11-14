<script lang="ts">
  import { daysTo, upcoming } from './events'
  import Icon from './Icon.svelte'
  import Progress from './Progress.svelte'
  import { app } from './state.svelte'
  import Wall from './Wall.svelte'

  // The events being prepared, on a field of the city's colour: each one's name, every employer's logo
  // ringed by how far its sign-up is, and the way in to manage it. Shown on Home and at the top of Events.
  const next = $derived(app.presets.map(upcoming))
  const left = (date: string) => {
    const days = daysTo(date)
    return days > 1 ? `in ${String(days)} days` : days === 1 ? 'tomorrow' : days === 0 ? 'today' : ''
  }
</script>

<div class="upcoming">
  <h2 class="group">Upcoming events</h2>
  {#each next as plan (plan.slug)}
    <section class="next">
      <div class="title">
        <h2><a href="#/event/{plan.slug}">{plan.title}</a></h2>
        <p>{[plan.when, left(plan.date)].filter(Boolean).join(', ')}</p>
      </div>
      <div class="who">
        <Wall briefs={plan.employers.map((e) => e.brief)} />
        <Progress employers={plan.employers} coming={plan.coming} />
      </div>
      <a class="btn primary" href="#/event/{plan.slug}">Manage event<Icon name="flat" size={18} /></a>
    </section>
  {/each}
</div>

<style>
  /* the upcoming events share one field; their group heading sits at its top */
  .upcoming {
    background: var(--city-raise);
    color: var(--city-ink);
  }
  .group {
    padding: var(--s6) var(--s7) 0 var(--s6);
    font-size: var(--t-lg);
    letter-spacing: -0.01em;
    color: var(--city-dim);
  }
  /* a field of the city's colour, as an employer's page opens on a field of its own */
  .next {
    --ink: var(--city-ink);
    --ink-2: var(--city-dim);
    --line: var(--city-line);
    --brand: var(--city-ink);
    --brand-ink: var(--city);
    display: grid;
    gap: var(--s6);
    padding: var(--s4) var(--s7) var(--s7) var(--s6);
  }
  .next > * {
    max-width: 72rem;
  }
  .next :global(:focus-visible) {
    outline-color: var(--city-ink);
  }
  .next h2 {
    font: 800 var(--t-2xl) / 0.95 var(--display);
    letter-spacing: -0.035em;
  }
  .next h2 a {
    text-decoration: none;
  }
  .title p {
    margin-top: var(--s3);
    font-size: var(--t-lg);
    color: var(--ink-2);
  }
  .who {
    display: grid;
    gap: var(--s4);
  }
  .who :global(ul) {
    grid-template-columns: repeat(auto-fill, minmax(4.5rem, 1fr));
  }
  .next .btn {
    justify-self: start;
  }
  @media (max-width: 820px) {
    .group {
      padding: var(--s5) var(--s4) 0;
    }
    .next {
      padding: var(--s3) var(--s4) var(--s6);
      gap: var(--s5);
    }
    .who :global(ul) {
      grid-template-columns: repeat(auto-fill, minmax(3.25rem, 1fr));
    }
  }
</style>
