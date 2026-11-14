<script lang="ts">
  // One stroke weight, 20px grid, drawn for this page.
  const PATHS = {
    check: 'M4.5 10.5 8.5 14.5 15.5 6',
    plus: 'M10 4.5v11M4.5 10h11',
    x: 'M5.5 5.5l9 9M14.5 5.5l-9 9',
    send: 'M17 3 9 11M17 3l-5 14-3-6-6-3z',
    out: 'M8 5h7v7M15 5 6 14',
    copy: 'M7.5 7.5V4.5h8v8h-3M4.5 7.5h8v8h-8z',
    up: 'M10 15.5v-11M5 9l5-5 5 5',
    down: 'M10 4.5v11M5 11l5 5 5-5',
    flat: 'M4 10h12M12 6l4 4-4 4',
    search: 'M13 13l4 4M9 14.5a5.5 5.5 0 1 1 0-11 5.5 5.5 0 0 1 0 11z',
    undo: 'M7 5 3.5 8.5 7 12M3.5 8.5H12a4.5 4.5 0 0 1 0 9H9',
  }
  let { name, size = 20 }: { name: keyof typeof PATHS; size?: number } = $props()
</script>

<svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d={PATHS[name]} />
</svg>
