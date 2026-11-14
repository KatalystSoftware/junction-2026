<script lang="ts">
  import Cite from './Cite.svelte'
  import { text } from './editable'
  import Icon from './Icon.svelte'
  import type { Brief, Need } from './types'

  // One role, as a proposal the company can accept in two seconds: who these people are, why we think
  // the company wants them, what they would do, and the practical terms as one line of facts. Editing is
  // reached for: "Edit" opens the wording, and a fact opens its choices when it is pressed.
  let { brief, need, change }: { brief: Brief; need: Need; change: (patch: Partial<Need>) => void } = $props()
  let editing = $state(false)
  type Key = 'seniority' | 'language' | 'workplace' | 'abroad'
  let asking = $state<Key | null>(null)

  const number = (id: string) => brief.signals.findIndex((s) => s.id === id) + 1
  const typed = (e: FocusEvent) => (e.currentTarget as HTMLElement).innerText.replace(/\s+/g, ' ').trim()
  const enter = (e: KeyboardEvent) => {
    if (e.key !== 'Enter') return
    e.preventDefault()
    ;(e.currentTarget as HTMLElement).blur()
  }
  const reword = (key: 'title' | 'why', e: FocusEvent) => {
    if (typed(e) !== need[key]) change({ [key]: typed(e), by: 'company' })
  }

  // the practical terms: what each is called when nobody has answered it, and how its answer reads
  const FACTS: { key: Key; ask: string; options: [string | boolean, string][] }[] = [
    { key: 'seniority', ask: 'Level?', options: ['Early career', 'Experienced', 'Senior', 'Lead'].map((x) => [x, x]) },
    { key: 'language', ask: 'Language?', options: [['English is enough', 'English is enough'], ['Finnish needed', 'Finnish needed']] },
    { key: 'workplace', ask: 'On site or remote?', options: ['On site', 'Hybrid', 'Remote'].map((x) => [x, x]) },
    { key: 'abroad', ask: 'Hiring from abroad?', options: [[true, 'Yes, from abroad too'], [false, 'Only people in Finland']] },
  ]
  const reads = (key: Key): string | null =>
    key === 'workplace' ? (need.workplace ? [need.workplace, need.where].filter(Boolean).join(', ') : null)
    : key === 'abroad' ? (need.abroad == null ? null : need.abroad ? 'Hires from abroad' : 'Only people in Finland')
    : (need[key] ?? null)
  const fromPost = $derived(Object.values(need.sources ?? {}).map((s) => `“${s.quote}”`).join(' '))

  const editTask = (j: number, e: FocusEvent) => {
    const next = need.can_do.map((t, k) => (k === j ? typed(e) : t)).filter(Boolean)
    if (next.join('|') !== need.can_do.join('|')) change({ can_do: next })
  }
  /** Keep what was typed as a skill: on Enter, and when the field is left, so nothing typed is lost. */
  function addSkill(e: KeyboardEvent | FocusEvent) {
    const input = e.currentTarget as HTMLInputElement
    if (('key' in e && e.key !== 'Enter') || !input.value.trim()) return
    e.stopPropagation()
    change({ skills: [...need.skills, input.value.trim()] })
    input.value = ''
  }
</script>

<div class="role" class:editing>
  <button class="edit" aria-pressed={editing} onclick={() => (editing = !editing)}>
    <Icon name={editing ? 'check' : 'pen'} size={16} />{editing ? 'Done' : 'Edit'}
  </button>
  <h2 role={editing ? 'textbox' : undefined} aria-label={editing ? 'Role' : undefined} contenteditable={editing ? 'plaintext-only' : undefined} spellcheck="false" data-placeholder="Who are you looking for?" onblur={(e) => { reword('title', e) }} onkeydown={enter} use:text={need.title}></h2>
  {#if need.why || need.signals.length || editing}
    <p class="why">
      <span role={editing ? 'textbox' : undefined} aria-label={editing ? 'Why now' : undefined} contenteditable={editing ? 'plaintext-only' : undefined} data-placeholder="Why now?" onblur={(e) => { reword('why', e) }} onkeydown={enter} use:text={need.why}></span><span class="cites">{#each need.signals.filter(number) as id, k (id)}<Cite signal={brief.signals[number(id) - 1]} n={k + 1} />{/each}</span>
    </p>
  {/if}

  <ul class="tasks">
    {#each need.can_do as task, j (j)}
      <li>
        <span role={editing ? 'textbox' : undefined} aria-label={editing ? 'Something they must be able to do' : undefined} contenteditable={editing ? 'plaintext-only' : undefined} data-placeholder="Something they must be able to do" onblur={(e) => { editTask(j, e) }} onkeydown={enter} use:text={task}></span>
        {#if editing}<button aria-label="Remove this" onclick={() => { change({ can_do: need.can_do.filter((_, k) => k !== j) }) }}><Icon name="x" size={14} /></button>{/if}
      </li>
    {/each}
    {#if editing && need.can_do.length < 4}
      <li class="plain"><button class="more" onclick={() => { change({ can_do: [...need.can_do, ''] }) }}><Icon name="plus" size={14} />Add something they must be able to do</button></li>
    {/if}
  </ul>

  {#if editing}
    <p class="chips">
      {#each need.skills as skill (skill)}
        <span class="chip">{skill}<button aria-label="Remove {skill}" onclick={() => { change({ skills: need.skills.filter((s) => s !== skill) }) }}><Icon name="x" size={12} /></button></span>
      {/each}
      <input class="chip" placeholder="Add a skill" aria-label="Add something they know" onkeydown={addSkill} onblur={addSkill} />
    </p>
  {:else if need.skills.length}
    <p class="knows">{need.skills.join(' · ')}</p>
  {/if}

  <p class="facts" role="group" aria-label="Practical details">
    {#each FACTS as fact (fact.key)}
      <button class:open={reads(fact.key) === null} aria-expanded={asking === fact.key} onclick={() => (asking = asking === fact.key ? null : fact.key)}>{reads(fact.key) ?? fact.ask}</button>
    {/each}
    {#if fromPost}<span class="read" title={fromPost}>from your job post</span>{/if}
  </p>
  {#each FACTS.filter((f) => f.key === asking) as fact (fact.key)}
    <p class="pick" role="radiogroup" aria-label={fact.ask}>
      {#each fact.options as [value, label] (label)}
        <button role="radio" data-choice aria-checked={need[fact.key] === value} onclick={() => { change({ [fact.key]: value }); asking = null }}>{label}</button>
      {/each}
    </p>
  {/each}
  {#if need.roles.length}<p class="posted">Open now: {need.roles.join(', ')}</p>{/if}
</div>

<style>
  .role {
    position: relative;
  }
  .edit {
    position: absolute;
    top: 0;
    right: 0;
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    min-height: 2rem;
    padding: 0 var(--s3);
    border: 0;
    border-radius: 99px;
    background: none;
    color: var(--ink-2);
    font-size: var(--t-sm);
    font-weight: 600;
  }
  .edit:hover,
  .edit[aria-pressed='true'] {
    background: var(--wash);
    color: var(--ink);
  }
  h2 {
    margin-right: 5rem;
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
  .tasks {
    display: grid;
    gap: var(--s1);
    margin-top: var(--s4);
    font-size: var(--t-lg);
    line-height: 1.3;
  }
  .tasks li {
    display: flex;
    align-items: baseline;
    gap: var(--s3);
  }
  .tasks li:not(.plain)::before {
    content: '';
    flex: none;
    width: 0.4rem;
    height: 0.4rem;
    translate: 0 -0.2rem;
    border-radius: 50%;
    background: var(--brand);
  }
  .tasks button {
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
  .tasks button:hover {
    color: var(--ink);
  }
  .knows {
    margin-top: var(--s3);
    font-size: var(--t-sm);
    color: var(--ink-2);
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s2);
    margin-top: var(--s3);
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
    field-sizing: content;
    min-width: 6.5rem;
    max-width: 100%;
    border-style: dashed;
    outline: none;
  }
  input.chip:focus {
    border-color: var(--ink);
    border-style: solid;
  }
  /* the practical terms: one line that reads as facts; each opens its choices when pressed */
  .facts {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--s2);
    margin-top: var(--s4);
    padding-top: var(--s4);
    border-top: 1px solid var(--line);
  }
  .facts button {
    min-height: 2rem;
    padding: 0 var(--s3);
    border: 1px solid transparent;
    border-radius: 99px;
    background: var(--wash);
    font-size: var(--t-sm);
    font-weight: 600;
  }
  .facts button:hover,
  .facts button[aria-expanded='true'] {
    border-color: var(--ink);
  }
  /* an unanswered one is a question in the same line, quieter than an answer */
  .facts button.open {
    border: 1px dashed var(--ink-2);
    background: none;
    color: var(--ink-2);
    font-weight: 500;
  }
  .read {
    font-size: var(--t-xs);
    color: var(--ink-2);
    cursor: help;
  }
  .pick {
    display: inline-flex;
    flex-wrap: wrap;
    margin-top: var(--s2);
    border: 1px solid var(--line);
    border-radius: 99px;
    overflow: hidden;
    animation: drop 0.25s var(--ease);
  }
  .pick button {
    min-height: 2.25rem;
    padding: 0 var(--s4);
    border: 0;
    background: none;
    color: var(--ink-2);
    font-size: var(--t-sm);
    font-weight: 600;
    transition: background 0.2s, color 0.2s;
  }
  .pick button + button {
    border-left: 1px solid var(--line);
  }
  .pick button:hover {
    color: var(--ink);
  }
  .pick button[aria-checked='true'] {
    background: var(--ink);
    color: var(--ground);
  }
  .posted {
    margin-top: var(--s3);
    font-size: var(--t-sm);
    font-weight: 600;
    color: var(--ok);
  }
  [contenteditable] {
    border-radius: 4px;
    outline: none;
    box-shadow: 0 0 0 4px var(--wash);
    background: var(--wash);
  }
  [contenteditable]:focus {
    background: var(--ground);
    box-shadow: 0 0 0 4px var(--ground), 0 0 0 6px var(--ink);
  }
  [contenteditable]:empty::before {
    content: attr(data-placeholder);
    color: color-mix(in oklch, var(--ink-2) 65%, var(--ground));
  }
  @keyframes drop {
    from {
      opacity: 0;
      translate: 0 -6px;
    }
  }
</style>
