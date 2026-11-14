// The geometry and colours of a person's mark, from a seed. Everything here is arithmetic on a hash of
// the seed, so nothing of what the person typed can be read back from the picture, and nothing is stored:
// the mark is drawn again from the seed whenever it is shown.

export type Tile = {
  x: number
  y: number
  fill: string
  ink: string
  dot: boolean
  /** the corner the quarter disc grows from, and the two ends of its arc */
  cx: number
  cy: number
  ax: number
  ay: number
  bx: number
  by: number
  sweep: 0 | 1
}
export type MarkShape = { size: number; ground: string; tiles: Tile[]; colours: string[] }

/** FNV-1a: a short text to 32 bits, spread evenly. */
function hash(text: string) {
  let h = 0x811c9dc5
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i)
    h = Math.imul(h, 0x01000193)
  }
  return h >>> 0
}
/** mulberry32: a repeatable stream of numbers in [0, 1) from 32 bits. */
function stream(seed: number) {
  let a = seed
  return () => {
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const SIZE = 3
// the four corners of a cell, and for each the arc's two ends, going round the corner
const CORNERS: [number, number, number, number, number, number, 0 | 1][] = [
  [0, 0, 1, 0, 0, 1, 1],
  [1, 0, 1, 1, 0, 0, 1],
  [1, 1, 0, 1, 1, 0, 1],
  [0, 1, 0, 0, 1, 1, 1],
]

export function markOf(seed: string): MarkShape {
  const next = stream(hash(seed || 'kutsu'))
  // Three colours a third of the wheel apart would look like a flag; these sit close in hue and far apart
  // in lightness, so the mark reads as one thing and its shapes stay apart for eyes that cannot tell hues.
  // The hues run from orange through green and blue to violet and stop short of pink and magenta, the
  // one band people read as a statement about a person.
  const hue = 25 + Math.floor(next() * 200)
  const turn = 18 + Math.floor(next() * 20)
  const colours = [
    `oklch(27% 0.1 ${String(hue)})`,
    `oklch(52% 0.16 ${String(hue + turn)})`,
    `oklch(76% 0.12 ${String(hue + 2 * turn)})`,
    `oklch(95% 0.03 ${String(hue)})`,
  ]
  const pick = () => colours[Math.floor(next() * colours.length)] ?? '#000'
  const tiles: Tile[] = []
  // at most one dot: two of them side by side would read as eyes
  const dotAt = next() < 0.6 ? Math.floor(next() * SIZE * SIZE) : -1
  for (let y = 0; y < SIZE; y++) {
    for (let x = 0; x < SIZE; x++) {
      const fill = pick()
      let ink = pick()
      while (ink === fill) ink = pick()
      const [cx, cy, ax, ay, bx, by, sweep] = CORNERS[Math.floor(next() * 4)] ?? [0, 0, 1, 0, 0, 1, 1]
      tiles.push({ x, y, fill, ink, dot: tiles.length === dotAt, cx: x + cx, cy: y + cy, ax: x + ax, ay: y + ay, bx: x + bx, by: y + by, sweep })
    }
  }
  return { size: SIZE, ground: colours[3] ?? '#fff', tiles, colours }
}
