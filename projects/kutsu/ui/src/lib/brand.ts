// A company's colour for the stage: the most chromatic of the colours its brand record lists, and an
// ink that reads on it. Many records lead with black or white, which say nothing, so those lose to
// any real colour; a brand with none gets a near-black field.

type Rgb = [number, number, number]
const HEX = /^#[0-9a-f]{6}$/i
const rgb = (hex: string): Rgb => {
  const n = parseInt(hex.slice(1), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}
const luminance = (c: Rgb) => {
  const [r, g, b] = c.map((v) => (v / 255 <= 0.04045 ? v / 255 / 12.92 : ((v / 255 + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
const contrast = (a: Rgb, b: Rgb) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}
const saturation = ([r, g, b]: Rgb) => {
  const max = Math.max(r, g, b), min = Math.min(r, g, b)
  const l = (max + min) / 510
  return { s: max === min ? 0 : (max - min) / 255 / (1 - Math.abs(2 * l - 1)), l }
}

const WHITE: Rgb = [255, 255, 255]
const DARK = '#14151a'

export function brandOf(colors: string[] = []): { field: string; ink: string } {
  let field = DARK, best = 0
  for (const c of colors.filter((c) => HEX.test(c))) {
    const { s, l } = saturation(rgb(c))
    const score = s * (1 - Math.abs(l - 0.45))
    if (s > 0.25 && l > 0.12 && l < 0.82 && score > best) [field, best] = [c, score]
  }
  const ink = contrast(rgb(field), WHITE) >= contrast(rgb(field), rgb(DARK)) ? '#ffffff' : DARK
  return { field, ink }
}
