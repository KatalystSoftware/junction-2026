<script lang="ts">
  import Icon from './Icon.svelte'
  import { app, joinPath, nameOf, research } from './state.svelte'

  // The public way in: a company types its own name and its sign-up fills itself in.
  let query = $state('')
  const event = $derived(app.presets[0])
  function submit(e: SubmitEvent) {
    e.preventDefault()
    const q = query.trim()
    if (!q) return
    const known = app.briefs.find((b) => nameOf(b).toLowerCase() === q.toLowerCase())
    if (known) location.hash = joinPath(known.id)
    else void research(q, (id) => (location.hash = joinPath(id)))
  }
</script>

<section>
  <p class="host">City of Espoo</p>
  <h1>Sign your company up for the {event?.title}</h1>
  <p class="lead">{event?.note.split(',')[0]}, online. Type your company and we fill in the sign-up from what you have said in public. You only check it.</p>
  <form onsubmit={submit}>
    <input bind:value={query} placeholder="Company name or website" aria-label="Company name or website" autocomplete="off" spellcheck="false" />
    <button type="submit" disabled={!query.trim()}>Fill it in<Icon name="flat" size={20} /></button>
  </form>
</section>

<style>
  section {
    min-height: 100dvh;
    padding: clamp(2rem, 12vh, 8rem) clamp(1.25rem, 6vw, 6rem);
    background: var(--city);
    color: var(--city-ink);
  }
  .host {
    font-size: var(--t-sm);
    font-weight: 700;
  }
  h1 {
    max-width: 16ch;
    margin-top: var(--s5);
    font-size: clamp(2.5rem, 1.4rem + 4.6vw, 5rem);
    font-weight: 800;
    letter-spacing: -0.035em;
    line-height: 0.98;
  }
  .lead {
    max-width: 46ch;
    margin: var(--s4) 0 var(--s6);
    font-size: var(--t-lg);
    line-height: 1.35;
    color: var(--city-dim);
  }
  form {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s3);
    max-width: 40rem;
  }
  input {
    flex: 1;
    min-width: 14rem;
    height: 3.5rem;
    padding: 0 var(--s5);
    border: 2px solid var(--city-line);
    border-radius: 99px;
    outline: none;
    background: var(--city-raise);
    color: var(--city-ink);
    font-size: var(--t-lg);
  }
  input::placeholder {
    color: var(--city-dim);
  }
  input:focus {
    border-color: var(--city-ink);
  }
  button {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    height: 3.5rem;
    padding: 0 var(--s6);
    border: 0;
    border-radius: 99px;
    background: var(--city-ink);
    color: var(--city);
    font-size: var(--t-lg);
    font-weight: 700;
  }
  button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  :focus-visible {
    outline-color: var(--city-ink);
  }
</style>
