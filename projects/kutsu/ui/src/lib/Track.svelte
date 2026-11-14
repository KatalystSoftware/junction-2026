<script lang="ts">
  import { clock } from './format'
  import Icon from './Icon.svelte'
  import { copyLink, isComing, joinLink, nameOf, saveReview, stateNames } from './state.svelte'
  import type { Brief, Review } from './types'

  // Where the brief is on its way to the company and back, and the one thing to do next.
  let { brief, review }: { brief: Brief; review: Review } = $props()
  let copied = $state(false)
  const at = $derived({ draft: 0, invited: 1, joined: 2 }[review.status] ?? 0)
  const coming = $derived(isComing(brief.id))
  const names = $derived(stateNames(coming))
  const stops = $derived([
    ['Drafted', `from ${brief.stats.results_read} public pages`],
    [names.invited, review.invited_at ? `at ${clock(review.invited_at)}` : review.status === 'draft' ? 'not yet' : ''],
    // a company that reopened its answers is invited again, whatever time it first finished
    [names.joined, review.status !== 'joined' ? 'by the company' : review.example ? 'an example' : `at ${clock(review.joined_at)}`],
  ])
  const now = () => new Date().toISOString()
  // inviting only makes the link live here; a real one would send it by email
  const send = () => (saveReview(brief.id, { ...review, status: 'invited', invited_at: now() }), copy())
  const takeBack = () => saveReview(brief.id, { ...review, status: 'draft', invited_at: undefined, joined_at: undefined })
  async function copy() {
    await copyLink(brief.id)
    copied = true
    setTimeout(() => (copied = false), 1600)
  }
</script>

<div class="track">
  <ol>
    {#each stops as [label, detail], i}
      <li class:done={i < at || at === 2} class:now={i === at && at < 2} aria-current={i === at ? 'step' : undefined}>
        <span class="dot">{#if i < at || at === 2}<Icon name="check" size={14} />{/if}</span>
        <span class="text"><b>{label}</b><small>{detail}</small></span>
      </li>
    {/each}
  </ol>
  <div class="act">
    {#if review.status === 'draft'}
      <button class="btn primary" onclick={send}><Icon name="send" size={18} />{coming ? `Send ${nameOf(brief)} its profile` : `Invite ${nameOf(brief)}`}</button>
    {:else}
      <button class="btn" onclick={copy}><Icon name={copied ? 'check' : 'copy'} size={16} />{copied ? 'Link copied' : 'Copy the invitation link'}</button>
      <a class="btn" href={joinLink(brief.id)} target="_blank" rel="noopener">Open their sign-up<Icon name="out" size={16} /></a>
      <button class="btn quiet" onclick={takeBack}><Icon name="undo" size={16} />{review.status === 'joined' ? 'Reopen as a draft' : 'Take back'}</button>
    {/if}
  </div>
</div>

<style>
  .track {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--s4) var(--s6);
    padding: var(--s4) var(--s7) var(--s4) var(--s6);
    border-bottom: 1px solid var(--line);
    background: var(--ground);
  }
  ol {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--s3) var(--s5);
  }
  li {
    display: flex;
    align-items: center;
    gap: var(--s3);
    color: var(--ink-2);
  }
  li + li::before {
    content: '';
    width: var(--s6);
    height: 2px;
    margin-right: var(--s2);
    border-radius: 1px;
    background: var(--line);
    transition: background 0.4s;
  }
  li.done + li::before {
    background: var(--brand);
  }
  .dot {
    display: grid;
    place-items: center;
    flex: none;
    width: 1.5rem;
    height: 1.5rem;
    border: 2px solid var(--line);
    border-radius: 50%;
    transition: background 0.4s, border-color 0.4s;
  }
  .now .dot {
    border-color: var(--brand);
    box-shadow: inset 0 0 0 4px var(--ground), inset 0 0 0 99px var(--brand);
  }
  .done .dot {
    border-color: var(--brand);
    background: var(--brand);
    color: var(--brand-ink);
    animation: stamp 0.5s var(--ease);
  }
  .text {
    display: grid;
    line-height: 1.2;
  }
  b {
    font-weight: 600;
  }
  .now b,
  .done b {
    color: var(--ink);
  }
  small {
    font-size: var(--t-xs);
  }
  .act {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--s2);
  }
  @keyframes stamp {
    from {
      scale: 1.6;
    }
  }
  @media (max-width: 820px) {
    .track {
      padding: var(--s4) var(--s5);
    }
    li + li::before {
      width: var(--s4);
    }
  }
</style>
