<script lang="ts">
  import Icon from './Icon.svelte'
  import { app } from './state.svelte'
  import type { Step } from './types'

  // Research as it happens: each line is something the server has actually just done.
  const run = $derived(app.research!)
  const last = (stage: Step['stage']) => run.steps.findLast((s) => s.stage === stage)
  const identity = $derived(last('identity'))
  const search = $derived(last('search'))
  const careers = $derived(last('careers'))
  const read = $derived(last('read'))
  const check = $derived(last('check'))
  const card = $derived(last('card'))
  const lines = $derived([
    {
      done: !!identity,
      now: !identity,
      text: identity ? (identity.name ? `This is ${identity.name}, ${identity.domain}` : 'No brand record found, searching by name') : 'Finding out who this is',
    },
    {
      done: !!(careers || read),
      now: !!search && !careers && !read,
      text: careers || read
        ? `${(careers ?? read)!.pages} pages found on the open web`
        : search
          ? `Searching the web, ${Number(search.done) + 1} of ${search.of}: ${search.pages} pages so far`
          : 'Search the open web',
    },
    { done: !!check, now: !!read && !check, text: read ? `Reading ${read.pages} pages` : 'Read every page' },
    {
      done: !!card,
      now: !!check && !card,
      text: check ? `Checking ${check.statements} statements word for word against their pages` : 'Check every quote against its page',
    },
    { done: false, now: !!card, text: card ? `Drafting who they need from ${card.statements} checked statements` : 'Draft who they need' },
  ])
</script>

<section class="research">
  <div class="plate" class:dark={identity?.logo_on === 'dark'}>
    {#if identity?.logo}<img src={String(identity.logo)} alt="" />{/if}
  </div>
  <div class="body">
    <h1>{identity?.name ?? run.query}</h1>
    {#if identity?.slogan}<p class="slogan">{identity.slogan}</p>{/if}
    {#if run.error}
      <p class="error" role="alert">{run.error}</p>
      <button class="btn" onclick={() => (app.research = null)}>Back to the list</button>
    {:else}
      <ol aria-live="polite">
        {#each lines as line}
          <li class:done={line.done} class:now={line.now}>
            <span class="dot">{#if line.done}<Icon name="check" size={14} />{/if}</span>{line.text}
          </li>
        {/each}
      </ol>
    {/if}
  </div>
</section>

<style>
  .research {
    display: grid;
    grid-template-columns: minmax(12rem, 30%) 1fr;
    min-height: 100dvh;
    background: var(--brand);
    color: var(--brand-ink);
    transition: background 0.8s var(--ease), color 0.4s;
  }
  .plate {
    display: grid;
    place-items: center;
    padding: var(--s6);
    background: #fff;
    transition: background 0.4s;
  }
  .plate.dark {
    background: #14151a;
  }
  img {
    max-width: min(100%, 17rem);
    max-height: 7.5rem;
    animation: arrive 0.7s var(--ease);
  }
  .body {
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: var(--s4);
    padding: var(--s7);
  }
  h1 {
    font-size: var(--t-2xl);
    font-weight: 800;
    letter-spacing: -0.035em;
    line-height: 0.95;
  }
  .slogan {
    max-width: 46ch;
    font-size: var(--t-lg);
    color: color-mix(in oklch, var(--brand-ink) 86%, var(--brand));
  }
  ol {
    display: grid;
    gap: var(--s3);
    margin-top: var(--s5);
    font-size: var(--t-lg);
  }
  li {
    display: flex;
    align-items: center;
    gap: var(--s3);
    color: color-mix(in oklch, var(--brand-ink) 55%, var(--brand));
    transition: color 0.3s;
  }
  li.done,
  li.now {
    color: var(--brand-ink);
  }
  .dot {
    display: grid;
    place-items: center;
    flex: none;
    width: 1.5rem;
    height: 1.5rem;
    border: 2px solid currentColor;
    border-radius: 50%;
  }
  .done .dot {
    background: var(--brand-ink);
    color: var(--brand);
    border-color: var(--brand-ink);
  }
  .now .dot {
    animation: pulse 1s ease-in-out infinite alternate;
  }
  .error {
    max-width: 50ch;
    font-size: var(--t-lg);
  }
  .btn {
    align-self: flex-start;
    color: var(--ink);
  }
  @keyframes pulse {
    to {
      box-shadow: 0 0 0 6px color-mix(in oklch, var(--brand-ink) 25%, transparent);
    }
  }
  @keyframes arrive {
    from {
      opacity: 0;
      scale: 0.9;
    }
  }
  @media (max-width: 820px) {
    .research {
      grid-template-columns: 1fr;
      grid-template-rows: 9rem 1fr;
      min-height: 70dvh;
    }
    .body {
      padding: var(--s5);
      justify-content: flex-start;
    }
  }
</style>
