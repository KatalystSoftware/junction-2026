<script lang="ts">
  // Kutsu's mark, "meet halfway" (docs/design/marks/kutsu/c-meet-halfway-glyph.svg): two quarter discs reaching from
  // opposite corners, companies and people, each waiting for the other, nearly met. Drawn without its tile, so the
  // first takes the colour of the text beside it on any ground: the city's blue rail, or a company's own colour.
  let { size = 20 }: { size?: number } = $props()
</script>

<svg class="kutsu-mark" width={size} height={size} viewBox="4 4 24 24" aria-hidden="true">
  <path d="M6 7a1 1 0 0 1 1-1H19A13 13 0 0 1 6 19Z" fill="currentColor" />
  <path d="M26 25a1 1 0 0 1-1 1H13A13 13 0 0 1 26 13Z" fill="#8fa8f0" />
</svg>
