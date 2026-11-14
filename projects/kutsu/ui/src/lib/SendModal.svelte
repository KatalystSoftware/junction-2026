<script lang="ts">
  import { some, type Plan } from './events'
  import { when } from './format'
  import Icon from './Icon.svelte'
  import { sendInvitation } from './manage.svelte'
  import { app } from './state.svelte'

  // Sending the invitation to the people who came to earlier events. The organiser picks which past events and which
  // fields, reads the message, and sends. Everyone applies through the same link, and every application is reviewed
  // separately on the Applications tab. Sample data: the count is of the sample pool, and nothing is sent.
  let { plan, onclose }: { plan: Plan; onclose: () => void } = $props()
  // the modal opens for one plan; its initial choices are taken from the plan once
  // svelte-ignore state_referenced_locally
  const start = { fields: plan.fields.map((f) => f.name), title: plan.title, when: plan.when }
  let events = $state(app.pool.events.map((e) => e.id))
  let fields = $state(start.fields)
  let message = $state(
    `You came to one of Espoo's talent events before, so here is an invitation to apply to the ${start.title}${start.when ? ` (${start.when})` : ''}: short 1:1 conversations with employers who look for what you do. Your application is drafted from what you agree we may read, you check every line, and a named organiser tells you their decision with a reason.`,
  )
  const toggle = (list: string[], id: string) => (list.includes(id) ? list.filter((x) => x !== id) : [...list, id])
  // a person who came to two events is counted in each; the pool keeps no rows, only counts per field and event
  const n = $derived(plan.fields.filter((f) => fields.includes(f.name)).reduce((sum, f) => sum + events.reduce((s, e) => s + (f.people.events[e] ?? 0), 0), 0))
  function send() {
    sendInvitation({ n, events, fields, message })
    onclose()
  }
  const keys = (e: KeyboardEvent) => {
    if (e.key === 'Escape') onclose()
  }
</script>

<svelte:window onkeydown={keys} />

<!-- the veil closes on a click outside the box; the keyboard closes with Escape (window handler above) -->
<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="veil" onclick={(e) => e.target === e.currentTarget && onclose()}>
  <div class="box" role="dialog" aria-modal="true" aria-labelledby="send-title" tabindex="-1">
    <header>
      <h2 id="send-title">Send the invitation</h2>
      <button class="btn quiet" onclick={onclose} aria-label="Close"><Icon name="x" size={16} /></button>
    </header>
    <p class="lead">To the people who came to Espoo's earlier events. Choose whom, read the message, send. Everyone applies through the same link, and each application is reviewed separately.</p>

    <div class="cols">
      <fieldset>
        <legend>Who came to</legend>
        {#each app.pool.events as e (e.id)}
          <label><input type="checkbox" checked={events.includes(e.id)} onchange={() => (events = toggle(events, e.id))} />{e.name}, {when(e.date.slice(0, 7))}<small>{some(e.people)} people</small></label>
        {/each}
      </fieldset>
      <fieldset>
        <legend>Who work in</legend>
        {#each plan.fields as f (f.name)}
          <label><input type="checkbox" checked={fields.includes(f.name)} onchange={() => (fields = toggle(fields, f.name))} />{f.name}<small>{some(f.people.people)} people</small></label>
        {/each}
      </fieldset>
    </div>

    <label class="msg">
      <span>The message</span>
      <textarea bind:value={message} rows="4"></textarea>
    </label>
    <p class="note">Each person's invitation opens on their own name with their application drafted from what they agreed we may read. Sample data: nobody is written to.</p>

    <footer>
      <span class="count"><b>{some(n)}</b> people</span>
      <button class="btn primary" onclick={send} disabled={!n}><Icon name="send" size={16} />Send to {some(n)} people</button>
    </footer>
  </div>
</div>

<style>
  .veil {
    position: fixed;
    inset: 0;
    z-index: 30;
    display: grid;
    place-items: center;
    padding: var(--s4);
    background: oklch(21% 0.03 264 / 0.45);
  }
  .box {
    width: min(42rem, 100%);
    max-height: calc(100dvh - 2 * var(--s4));
    overflow: auto;
    padding: var(--s5) var(--s6) var(--s6);
    border-radius: var(--r2);
    background: var(--ground);
    box-shadow: var(--lift);
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--s3);
  }
  h2 {
    font-size: var(--t-xl);
  }
  .lead {
    margin-top: var(--s2);
    color: var(--ink-2);
  }
  .cols {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--s5);
    margin-top: var(--s5);
  }
  fieldset {
    margin: 0;
    padding: 0;
    border: 0;
    min-width: 0;
  }
  legend {
    padding: 0;
    margin-bottom: var(--s2);
    font-size: var(--t-sm);
    font-weight: 700;
  }
  fieldset label {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: var(--s2);
    align-items: center;
    padding: var(--s1) 0;
    font-size: var(--t-sm);
  }
  fieldset small {
    color: var(--ink-2);
  }
  .msg {
    display: block;
    margin-top: var(--s5);
  }
  .msg span {
    display: block;
    margin-bottom: var(--s2);
    font-size: var(--t-sm);
    font-weight: 700;
  }
  textarea {
    width: 100%;
    padding: var(--s3);
    border: 1px solid var(--line);
    border-radius: var(--r1);
    font: inherit;
    font-size: var(--t-sm);
    line-height: 1.45;
    resize: vertical;
  }
  .note {
    margin-top: var(--s2);
    font-size: var(--t-xs);
    color: var(--ink-2);
  }
  footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--s3);
    margin-top: var(--s5);
  }
  .count b {
    font-size: var(--t-xl);
    font-weight: 800;
    letter-spacing: -0.03em;
    color: var(--city);
  }
  @media (max-width: 40rem) {
    .cols {
      grid-template-columns: 1fr;
    }
  }
</style>
