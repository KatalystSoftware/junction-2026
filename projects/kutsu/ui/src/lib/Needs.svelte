<script lang="ts">
  import { tick } from 'svelte'
  import Cite from './Cite.svelte'
  import { text } from './editable'
  import { terms } from './format'
  import Icon from './Icon.svelte'
  import { saveReview } from './state.svelte'
  import type { Brief, Need, Review } from './types'

  // The needs: the reason the page exists. Each is a line the reader can change, with the numbered
  // statements it rests on. `who` is the person editing, so their changes carry their name.
  let { brief, review, who, editable }: { brief: Brief; review: Review; who: 'espoo' | 'company'; editable: boolean } = $props()
  let list: HTMLOListElement
  const number = (id: string) => brief.signals.findIndex((s) => s.id === id) + 1
  const BY = { espoo: 'Edited by Espoo', company: 'Changed by the company' }
  const blank = (): Need => ({ id: `e${String(Date.now())}`, title: '', why: '', can_do: [], skills: [], seniority: 'Experienced', signals: [], roles: [], by: who })

  const save = (needs: Need[]) => saveReview(brief.id, { ...review, needs })

  function edit(i: number, key: 'title' | 'why', e: FocusEvent) {
    const text = (e.currentTarget as HTMLElement).innerText.replace(/\s+/g, ' ').trim()
    if (text === review.needs[i][key]) return
    save(review.needs.map((n, j) => (j === i ? { ...n, [key]: text, by: who } : n)))
  }
  const remove = (i: number) => save(review.needs.filter((_, j) => j !== i))
  async function add() {
    await save([...review.needs, blank()])
    await tick()
    list.querySelector<HTMLElement>('li:last-child h3')?.focus()
  }
  const enter = (e: KeyboardEvent) => e.key === 'Enter' && (e.preventDefault(), (e.currentTarget as HTMLElement).blur())
</script>

<ol bind:this={list} class:editable>
  {#each review.needs as need, i (i)}
    <li style:--i={i} class:off={need.off}>
      <h3 contenteditable={editable ? 'plaintext-only' : undefined} spellcheck="false" data-placeholder="Who do they need?" onblur={(e) => edit(i, 'title', e)} onkeydown={enter} use:text={need.title}></h3>
      <p class="why">
        <span role={editable ? 'textbox' : undefined} aria-label="Why" contenteditable={editable ? 'plaintext-only' : undefined} data-placeholder="Why? One line." onblur={(e) => edit(i, 'why', e)} onkeydown={enter} use:text={need.why}></span><span class="cites">{#each need.signals.filter(number) as id}<Cite signal={brief.signals[number(id) - 1]} n={number(id)} />{/each}</span>
      </p>
      {#if need.can_do?.length}<ul class="can">{#each need.can_do as task}<li>{task}</li>{/each}</ul>{/if}
      <p class="tags">
        <span class="level">{terms(need).join(' · ')}</span>
        {#each need.skills as skill}<span class="skill">{skill}</span>{/each}
        {#each need.roles as role}<span class="role">Hiring now: {role}</span>{/each}
        {#if need.off}<span class="by">The company said no</span>
        {:else if need.by}<span class="by">{need.signals.length ? BY[need.by] : need.by === 'espoo' ? 'Added by Espoo' : 'Added by the company'}</span>{/if}
      </p>
      {#if editable}
        <button class="remove" aria-label="Remove this need" title="Remove" onclick={() => remove(i)}><Icon name="x" size={16} /></button>
      {/if}
    </li>
  {:else}
    <li class="none">Nothing public points to a specific need yet.</li>
  {/each}
</ol>
{#if editable}
  <button class="btn quiet add" onclick={add}><Icon name="plus" size={16} />Add a need</button>
{/if}

<style>
  ol {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 24rem), 1fr));
    gap: 0 var(--s7);
  }
  li {
    position: relative;
    padding: var(--s5) var(--s6) var(--s5) 0;
    border-top: 1px solid var(--line);
    animation: rise 0.6s var(--ease) backwards;
    animation-delay: calc(var(--i) * 70ms + 180ms);
  }
  h3 {
    font-size: var(--t-xl);
    line-height: 1.08;
  }
  .why {
    margin-top: var(--s2);
    max-width: 58ch;
    color: var(--ink-2);
  }
  .cites {
    white-space: nowrap;
  }
  [contenteditable] {
    border-radius: 3px;
    outline: none;
    transition: box-shadow 0.12s, background 0.12s;
  }
  .editable [contenteditable]:hover {
    box-shadow: 0 0 0 4px var(--wash);
    background: var(--wash);
  }
  [contenteditable]:focus {
    box-shadow: 0 0 0 4px var(--ground), 0 0 0 6px var(--brand);
    background: var(--ground);
    color: var(--ink);
  }
  [contenteditable]:empty::before {
    content: attr(data-placeholder);
    color: color-mix(in oklch, var(--ink-2) 60%, var(--ground));
  }
  .tags {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s2);
    margin-top: var(--s3);
    font-size: var(--t-sm);
  }
  .can {
    margin-top: var(--s3);
    padding-left: var(--s4);
    max-width: 58ch;
    list-style: disc;
    font-size: var(--t-sm);
  }
  .level,
  .skill {
    padding: 0.1rem var(--s2);
    border: 1px solid var(--line);
    border-radius: var(--r1);
  }
  .level {
    border-color: var(--ink-2);
    font-weight: 600;
  }
  .off h3,
  .off .why {
    text-decoration: line-through;
    color: var(--ink-2);
  }
  .role {
    padding: 0.1rem var(--s2);
    border-radius: var(--r1);
    background: color-mix(in oklch, var(--ok) 12%, var(--ground));
    color: color-mix(in oklch, var(--ok) 70%, var(--ink));
    font-weight: 600;
  }
  .by {
    padding: 0.1rem var(--s2);
    border-radius: var(--r1);
    background: var(--wash);
    color: var(--ink-2);
  }
  .remove {
    position: absolute;
    top: var(--s5);
    right: 0;
    display: grid;
    place-items: center;
    width: 1.75rem;
    height: 1.75rem;
    border: 0;
    border-radius: var(--r1);
    background: none;
    color: var(--ink-2);
    opacity: 0;
    transition: opacity 0.12s, background 0.12s, color 0.12s;
  }
  li:hover .remove,
  .remove:focus-visible {
    opacity: 1;
  }
  .remove:hover {
    background: color-mix(in oklch, var(--stop) 12%, var(--ground));
    color: var(--stop);
  }
  .none {
    color: var(--ink-2);
    animation: none;
  }
  .add {
    margin-top: var(--s2);
    margin-left: calc(-1 * var(--s2));
  }
  @keyframes rise {
    from {
      opacity: 0;
      translate: 0 14px;
    }
  }
  @media (hover: none) {
    .remove {
      opacity: 1;
    }
  }
</style>
