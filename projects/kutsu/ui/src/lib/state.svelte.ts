import type { Brief, Preset, Review, Step } from './types'

/** Everything the page shows. Reviews are polled, so a company's reply arrives without a reload. */
export const app = $state({
  briefs: [] as Brief[],
  presets: [] as Preset[],
  reviews: {} as Record<string, Review>,
  hash: location.hash,
  ready: false,
  research: null as null | { query: string; steps: Step[]; error: string },
})

const get = (path: string) => fetch(path).then((r) => r.json())

export async function load() {
  const [briefs, presets, reviews] = await Promise.all([get('signals.json'), get('presets.json'), get('reviews.json')])
  Object.assign(app, { briefs, presets, reviews, ready: true })
  addEventListener('hashchange', () => (app.hash = location.hash))
  // a field being typed in would lose its text to a poll, so polls wait for the typing to end
  setInterval(async () => {
    if (!(document.activeElement as HTMLElement | null)?.isContentEditable) app.reviews = await get('reviews.json')
  }, 3000)
}

/** `#/<brief id>` is Espoo's screen; `#/join/<brief id>` is the company's sign-up, and `#/join` lets a company find itself. */
export const route = () => {
  const [, a = '', b = ''] = app.hash.split('/').map(decodeURIComponent)
  return a === 'join' || a === 'c' ? { join: true, id: b } : { join: false, id: a }
}
export const go = (id: string) => (location.hash = `#/${encodeURIComponent(id)}`)
export const joinPath = (id: string) => `#/join/${encodeURIComponent(id)}`
export const joinLink = (id: string) => `${location.origin}${location.pathname}${joinPath(id)}`

/** The event's own name for a company, where the brand record calls it something else. */
export const nameOf = (b: Brief) =>
  app.presets.map((p) => p.names?.[b.id]).find(Boolean) ?? b.name.replace(/\s+(Oyj Abp|Oyj|Oy Ab|Oy|Ab|sr)$/i, '')

export const reviewOf = (b: Brief): Review =>
  app.reviews[b.id] ?? { status: 'draft', needs: b.card.needs.map((n) => ({ ...n })) }

export async function saveReview(id: string, review: Review) {
  app.reviews[id] = review
  await fetch(`review?id=${encodeURIComponent(id)}`, { method: 'POST', body: JSON.stringify(review) })
}

let run = 0

/** Research any company by name or domain, showing each step as the server reports it, then open it with `open`. */
export async function research(query: string, open: (id: string) => void = go) {
  const mine = ++run
  app.research = { query, steps: [], error: '' }
  const poll = setInterval(async () => {
    const steps = await get(`progress?q=${encodeURIComponent(query)}`).catch(() => null)
    if (steps && run === mine && app.research) app.research.steps = steps
  }, 400)
  try {
    const r = await fetch(`brief?q=${encodeURIComponent(query)}`)
    if (!r.ok) throw new Error(await r.text())
    const brief: Brief = await r.json()
    app.briefs = [...app.briefs.filter((b) => b.id !== brief.id), brief]
    if (run === mine) {
      app.research = null
      open(brief.id)
    }
  } catch (e) {
    if (run === mine && app.research) app.research.error = e instanceof Error ? e.message : String(e)
  } finally {
    clearInterval(poll)
  }
}
