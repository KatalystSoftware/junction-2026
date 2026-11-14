<script lang="ts">
  import Cite from './Cite.svelte'
  import { text } from './editable'
  import Icon from './Icon.svelte'
  import type { Brief, Need, Posting } from './types'

  // One role, open for editing: its title, why now, and the six things it asks for. Values read
  // from a job post say so; what no public page can say is marked as the company's call.
  let { brief, need, change }: { brief: Brief; need: Need; change: (patch: Partial<Need>) => void } = $props()
  const number = (id: string) => brief.signals.findIndex((s) => s.id === id) + 1
  const typed = (e: FocusEvent) => (e.currentTarget as HTMLElement).innerText.replace(/\s+/g, ' ').trim()
  const enter = (e: KeyboardEvent) => e.key === 'Enter' && (e.preventDefault(), (e.currentTarget as HTMLElement).blur())
  const reword = (key: 'title' | 'why', e: FocusEvent) => typed(e) !== need[key] && change({ [key]: typed(e), by: 'company' })

  const ASKS: { key: 'seniority' | 'language' | 'workplace' | 'abroad'; label: string; options: [string | boolean, string][] }[] = [
    { key: 'seniority', label: 'Level', options: ['Early career', 'Experienced', 'Senior', 'Lead'].map((x) => [x, x]) },
    { key: 'language', label: 'Language', options: [['English is enough', 'English is enough'], ['Finnish needed', 'Finnish needed']] },
    { key: 'workplace', label: 'Where', options: ['On site', 'Hybrid', 'Remote'].map((x) => [x, x]) },
    { key: 'abroad', label: 'From abroad', options: [[true, 'Yes'], [false, 'Only in Finland']] },
  ]
  const tasks = $derived(need.can_do ?? [])
  const editTask = (j: number, e: FocusEvent) => {
    const next = tasks.map((t, k) => (k === j ? typed(e) : t)).filter(Boolean)
    if (next.join('|') !== tasks.join('|')) change({ can_do: next })
  }
  function addSkill(e: KeyboardEvent) {
    const input = e.currentTarget as HTMLInputElement
    if (e.key !== 'Enter' || !input.value.trim()) return
    e.stopPropagation()
    change({ skills: [...need.skills, input.value.trim()] })
    input.value = ''
  }

  let posting = $state<Posting | 'drafting' | 'failed' | null>(null)
  async function draft() {
    posting = 'drafting'
    const r = await fetch(`posting?id=${encodeURIComponent(brief.id)}`, { method: 'POST', body: JSON.stringify(need) }).catch(() => null)
    posting = r?.ok ? await r.json() : 'failed'
  }
</script>

<h2 role="textbox" tabindex="0" aria-label="Role" contenteditable="plaintext-only" spellcheck="false" data-placeholder="Who are you looking for?" onblur={(e) => reword('title', e)} onkeydown={enter} use:text={need.title}></h2>
{#if need.why || need.signals.length}
  <p class="why">
    <span role="textbox" tabindex="0" aria-label="Why now" contenteditable="plaintext-only" data-placeholder="Why now?" onblur={(e) => reword('why', e)} onkeydown={enter} use:text={need.why}></span><span class="cites">{#each need.signals.filter(number) as id}<Cite signal={brief.signals[number(id) - 1]} n={number(id)} />{/each}</span>
  </p>
{/if}
{#if need.roles.length}<p class="open">Open now: {need.roles.join(', ')}</p>{/if}

<dl>
  <div>
    <dt>Can do</dt>
    <dd>
      <ul class="tasks">
        {#each tasks as task, j (j)}
          <li>
            <span role="textbox" tabindex="0" aria-label="Something they must be able to do" contenteditable="plaintext-only" data-placeholder="Something they must be able to do" onblur={(e) => editTask(j, e)} onkeydown={enter} use:text={task}></span>
            <button aria-label="Remove this" onclick={() => change({ can_do: tasks.filter((_, k) => k !== j) })}><Icon name="x" size={14} /></button>
          </li>
        {/each}
      </ul>
      {#if tasks.length < 4}<button class="more" onclick={() => change({ can_do: [...tasks, ''] })}><Icon name="plus" size={14} />Add</button>{/if}
    </dd>
  </div>
  <div>
    <dt>Knows</dt>
    <dd class="chips">
      {#each need.skills as skill (skill)}
        <span class="chip">{skill}<button aria-label="Remove {skill}" onclick={() => change({ skills: need.skills.filter((s) => s !== skill) })}><Icon name="x" size={12} /></button></span>
      {/each}
      <input class="chip" placeholder="Add" aria-label="Add something they know" onkeydown={addSkill} />
    </dd>
  </div>
  {#each ASKS as ask (ask.key)}
    <div>
      <dt>{ask.label}</dt>
      <dd>
        <span class="seg" role="radiogroup" aria-label={ask.label}>
          {#each ask.options as [value, label]}
            <button role="radio" aria-checked={need[ask.key] === value} onclick={() => change({ [ask.key]: value })}>{label}</button>
          {/each}
        </span>
        {#if ask.key === 'workplace' && need.where}<span class="place">{need.where}</span>{/if}
        {#if need.sources?.[ask.key]}
          <span class="read" title={`“${need.sources[ask.key].quote}”`}>from your job post</span>
        {:else if need[ask.key] == null}
          <span class="yours">your call</span>
        {/if}
      </dd>
    </div>
  {/each}
</dl>

{#if posting && typeof posting === 'object'}
  <div class="posting">
    <h3>{posting.headline}</h3>
    <p>{posting.intro}</p>
    <h4>You will</h4>
    <ul>{#each posting.you_will as line}<li>{line}</li>{/each}</ul>
    <h4>You bring</h4>
    <ul>{#each posting.you_bring as line}<li>{line}</li>{/each}</ul>
    <p class="now">{posting.why_now}</p>
  </div>
{/if}
<button class="draft" disabled={posting === 'drafting'} onclick={draft}>
  {posting === 'drafting' ? 'Drafting the posting' : posting === 'failed' ? 'That did not come through. Try again' : posting ? 'Draft it again' : 'Draft a job posting for this'}
</button>

<style>
  h2 {
    font-size: var(--t-xl);
    font-weight: 800;
    letter-spacing: -0.03em;
    line-height: 1.05;
  }
  .why {
    margin-top: var(--s2);
    color: var(--ink-2);
  }
  .cites {
    white-space: nowrap;
  }
  .open {
    margin-top: var(--s2);
    font-size: var(--t-sm);
    font-weight: 600;
    color: var(--ok);
  }
  dl {
    display: grid;
    gap: var(--s2);
    margin-top: var(--s4);
  }
  dl > div {
    display: grid;
    grid-template-columns: 6.5rem 1fr;
    align-items: baseline;
    gap: var(--s3);
  }
  dt {
    font-size: var(--t-sm);
    font-weight: 600;
    color: var(--ink-2);
  }
  dd {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--s2) var(--s3);
    margin: 0;
  }
  [contenteditable] {
    border-radius: 4px;
    outline: none;
    transition: box-shadow 0.12s, background 0.12s;
  }
  [contenteditable]:hover {
    background: var(--wash);
    box-shadow: 0 0 0 4px var(--wash);
  }
  [contenteditable]:focus {
    background: var(--ground);
    box-shadow: 0 0 0 4px var(--ground), 0 0 0 6px var(--ink);
  }
  [contenteditable]:empty::before {
    content: attr(data-placeholder);
    color: color-mix(in oklch, var(--ink-2) 65%, var(--ground));
  }
  .tasks {
    display: grid;
    gap: var(--s1);
    width: 100%;
  }
  .tasks li {
    display: flex;
    align-items: baseline;
    gap: var(--s2);
  }
  .tasks li::before {
    content: '';
    flex: none;
    width: 0.375rem;
    height: 0.375rem;
    translate: 0 -0.15rem;
    border-radius: 50%;
    background: var(--brand);
  }
  .tasks button,
  .more {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    padding: 0.15rem;
    border: 0;
    border-radius: var(--r1);
    background: none;
    color: var(--ink-2);
    font-size: var(--t-sm);
    font-weight: 600;
  }
  .tasks button {
    opacity: 0;
    transition: opacity 0.12s;
  }
  .tasks li:hover button,
  .tasks button:focus-visible {
    opacity: 1;
  }
  .tasks button:hover {
    color: var(--stop);
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    min-height: 1.75rem;
    padding: 0 var(--s3);
    border: 1px solid var(--line);
    border-radius: 99px;
    background: var(--ground);
    font-size: var(--t-sm);
  }
  .chip button {
    display: grid;
    place-items: center;
    margin-right: -0.35rem;
    padding: 0.15rem;
    border: 0;
    border-radius: 50%;
    background: none;
    color: var(--ink-2);
  }
  .chip button:hover {
    background: var(--wash);
    color: var(--stop);
  }
  input.chip {
    width: 6rem;
    border-style: dashed;
    outline: none;
  }
  input.chip:focus {
    border-color: var(--ink);
    border-style: solid;
  }
  .seg {
    display: inline-flex;
    border: 1px solid var(--line);
    border-radius: 99px;
    overflow: hidden;
  }
  .seg button {
    min-height: 2rem;
    padding: 0 var(--s3);
    border: 0;
    background: none;
    color: var(--ink-2);
    font-size: var(--t-sm);
    font-weight: 600;
    transition: background 0.2s, color 0.2s;
  }
  .seg button + button {
    border-left: 1px solid var(--line);
  }
  .seg button:hover {
    color: var(--ink);
  }
  .seg button[aria-checked='true'] {
    background: var(--ink);
    color: var(--ground);
  }
  .place,
  .read {
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  .read {
    font-size: var(--t-xs);
    cursor: help;
  }
  .yours {
    padding: 0.05rem var(--s2);
    border-radius: 99px;
    background: color-mix(in srgb, var(--brand) 16%, #fff);
    font-size: var(--t-xs);
    font-weight: 600;
  }
  .draft {
    margin-top: var(--s4);
    padding: 0;
    border: 0;
    background: none;
    color: var(--ink-2);
    font-size: var(--t-sm);
    font-weight: 600;
  }
  .draft:hover:not(:disabled) {
    color: var(--ink);
  }
  .posting {
    margin-top: var(--s5);
    padding: var(--s5);
    border-radius: var(--r2);
    background: var(--wash);
    animation: rise 0.5s var(--ease);
  }
  .posting h3 {
    margin-bottom: var(--s2);
    font-size: var(--t-lg);
  }
  .posting h4 {
    margin: var(--s3) 0 var(--s1);
    font: 700 var(--t-sm) / 1.2 var(--text);
    color: var(--ink-2);
  }
  .posting ul {
    padding-left: var(--s4);
    list-style: disc;
  }
  .posting .now {
    margin-top: var(--s3);
    font-weight: 600;
  }
  @keyframes rise {
    from {
      opacity: 0;
      translate: 0 12px;
    }
  }
  @media (max-width: 640px) {
    dl > div {
      grid-template-columns: 1fr;
      gap: var(--s1);
    }
    .tasks button {
      opacity: 1;
    }
  }
</style>
