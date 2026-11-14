<script lang="ts">
  import { brandOf } from './lib/brand'
  import Demo from './lib/Demo.svelte'
  import Events from './lib/Events.svelte'
  import { plans } from './lib/events'
  import Find from './lib/Find.svelte'
  import Join from './lib/Join.svelte'
  import Ledger from './lib/Ledger.svelte'
  import Needs from './lib/Needs.svelte'
  import Plan from './lib/Plan.svelte'
  import Rail from './lib/Rail.svelte'
  import Research from './lib/Research.svelte'
  import Stage from './lib/Stage.svelte'
  import Track from './lib/Track.svelte'
  import Watch from './lib/Watch.svelte'
  import { app, load, reviewOf, route } from './lib/state.svelte'

  load()

  const at = $derived(route())
  // with no employer chosen, Espoo's screen shows its events
  const brief = $derived(app.briefs.find((b) => b.id === at.id))
  const plan = $derived(at.event ? plans().find((p) => p.slug === at.event) : undefined)
  const review = $derived(brief && reviewOf(brief))
  const brand = $derived(
    brandOf(app.research ? ((app.research.steps.findLast((s) => s.stage === 'identity')?.colors as string[]) ?? []) : brief?.identity?.colors),
  )
  const state = $derived(
    review?.status === 'joined'
      ? review.example
        ? 'An example sign-up, filled in for the demo. The company has not seen it.'
        : 'Signed up. These are the company\'s own answers.'
      : review?.status === 'invited'
        ? 'Invited. Waiting for the company to sign up.'
        : `Drafted from ${brief?.signals.length} public ${brief?.signals.length === 1 ? 'statement' : 'statements'}. Not confirmed by the company.`,
  )
</script>

{#if app.ready}
  <Demo />
  <div class="page" style:--brand={brand.field} style:--brand-ink={brand.ink}>
    {#if at.join}
      {#if app.research}<Research />{:else if brief}<Join {brief} />{:else if at.id}<p class="missing">This invitation does not point to a company we know.</p>{:else}<Find />{/if}
    {:else}
      <div class="shell">
        <Rail />
        <div class="work">
          {#if app.research}
            <Research />
          {:else if plan}
            {#key plan.slug}<Plan {plan} />{/key}
          {:else if !brief || !review}
            <Events />
          {:else}
            <Stage {brief} />
            <Track {brief} {review} />
            <main>
              {#key brief.id}
                <section class="needs">
                  <h2>Looking for</h2>
                  <p class="state {review.status}">{state}</p>
                  <Needs {brief} {review} who="espoo" editable={review.status === 'draft'} />
                  {#if review.status === 'joined'}
                    <p class="reply">
                      <b>At the event they would like:</b> {(review.wants ?? []).join(', ').toLowerCase() || 'nothing extra'}.
                      {#each Object.entries(review.about ?? {}) as [label, value]}<br /><b>{label}, corrected:</b> {value}{/each}
                    </p>
                  {/if}
                </section>
                <Watch {brief} />
                {#if brief.signals.length}<Ledger {brief} />{/if}
              {/key}
            </main>
          {/if}
        </div>
      </div>
    {/if}
  </div>
{/if}

<style>
  .shell {
    display: grid;
    grid-template-columns: var(--rail) minmax(0, 1fr);
    min-height: 100dvh;
  }
  main {
    display: grid;
    gap: var(--s8);
    max-width: 76rem;
    padding: var(--s7) var(--s7) var(--s8) var(--s6);
  }
  .needs h2 {
    font-size: var(--t-lg);
    letter-spacing: -0.01em;
  }
  .state {
    display: flex;
    align-items: center;
    gap: var(--s2);
    margin: var(--s1) 0 var(--s5);
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  .state::before {
    content: '';
    flex: none;
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    background: var(--ink-2);
  }
  .state.invited::before {
    background: var(--wait);
  }
  .state.joined {
    color: var(--ok);
    font-weight: 600;
  }
  .state.joined::before {
    background: var(--ok);
  }
  .reply {
    max-width: 62ch;
    margin-top: var(--s5);
    padding: var(--s4);
    border-radius: var(--r1);
    background: var(--wash);
  }
  .missing {
    padding: var(--s7);
    font-size: var(--t-lg);
  }
  @media (max-width: 820px) {
    .shell {
      grid-template-columns: 1fr;
    }
    main {
      padding: var(--s6) var(--s5) var(--s7);
      gap: var(--s7);
    }
  }
</style>
