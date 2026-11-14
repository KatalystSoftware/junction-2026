<script lang="ts">
  import { host, when } from './format'
  import Icon from './Icon.svelte'
  import type { Signal } from './types'

  // A numbered source. Hovering, focusing or tapping it shows the sentence the claim rests on.
  // With `label` it reads as a source chip ("qoco.aero, Sep 2026") instead of a number.
  let { signal, n = 0, label = '' }: { signal: Signal; n?: number; label?: string } = $props()
  let open = $state(false)
  let place = $state('')
  let button: HTMLButtonElement
  let closing: ReturnType<typeof setTimeout>

  function show() {
    clearTimeout(closing)
    const r = button.getBoundingClientRect()
    const width = Math.min(384, innerWidth - 24)
    const left = Math.max(12, Math.min(r.left - 24, innerWidth - width - 12))
    const vertical = r.top > innerHeight / 2 ? `bottom:${innerHeight - r.top + 8}px` : `top:${r.bottom + 8}px`
    place = `left:${left}px;width:${width}px;${vertical}`
    open = true
  }
  const hide = () => (closing = setTimeout(() => (open = false), 140))
</script>

<span class="cite" class:chip={!!label} role="presentation" onpointerenter={show} onpointerleave={hide} onfocusin={show} onfocusout={hide}>
  <button bind:this={button} aria-expanded={open} aria-label="Source{n ? ` ${String(n)}` : ''}, {host(signal.source_url)}" onclick={show}>{label || n}</button>
  {#if open}
    <span class="card" style={place}>
      <q>{signal.quote}</q>
      <span class="from">
        <b>{signal.source_title || host(signal.source_url)}</b>
        <span>{host(signal.source_url)}{signal.published ? `, ${when(signal.published)}` : ''}</span>
      </span>
      <a href={signal.source_url} target="_blank" rel="noopener">Open the page<Icon name="out" size={14} /></a>
    </span>
  {/if}
</span>

<style>
  .cite {
    position: relative;
    top: -0.45em;
    margin-left: 0.15em;
    font-size: 0.72rem;
    line-height: 0;
  }
  button {
    min-width: 1.35rem;
    height: 1.35rem;
    padding: 0 0.25rem;
    border: 1px solid var(--line);
    border-radius: 99px;
    background: var(--ground);
    color: var(--ink-2);
    font: 700 0.72rem / 1 var(--text);
    transition: background 0.12s, color 0.12s, border-color 0.12s;
  }
  .chip {
    top: 0;
    margin-left: 0;
    font-size: var(--t-sm);
    line-height: inherit;
  }
  .chip button {
    height: 1.75rem;
    padding: 0 var(--s3);
    font-size: var(--t-sm);
    font-weight: 600;
  }
  button:hover,
  button[aria-expanded='true'] {
    border-color: var(--brand);
    background: var(--brand);
    color: var(--brand-ink);
  }
  .card {
    position: fixed;
    z-index: 20;
    display: grid;
    gap: var(--s3);
    padding: var(--s4) var(--s4) var(--s3);
    border-radius: var(--r2);
    border-top: 4px solid var(--brand);
    background: var(--ground);
    box-shadow: var(--lift);
    font-size: var(--t-sm);
    line-height: 1.45;
    text-align: left;
    white-space: normal;
    animation: pop 0.18s var(--ease);
  }
  q {
    font-size: var(--t-md);
    line-height: 1.4;
    quotes: '“' '”';
  }
  .from {
    display: grid;
    color: var(--ink-2);
  }
  .from b {
    color: var(--ink);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  a {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    justify-self: start;
    min-height: 2rem;
    padding: 0 var(--s3);
    border: 1px solid var(--line);
    border-radius: 99px;
    color: var(--ink);
    font-weight: 600;
    text-decoration: none;
  }
  a:hover {
    border-color: var(--ink);
  }
  @keyframes pop {
    from {
      opacity: 0;
      translate: 0 4px;
    }
  }
</style>
