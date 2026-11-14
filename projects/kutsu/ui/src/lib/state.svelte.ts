import type { Brief, Pool, Preset, Review, Status, Step, Watch } from './types'

/** Everything the page shows. Reviews are polled, so a company's reply arrives without a reload. */
export const app = $state({
  briefs: [] as Brief[],
  presets: [] as Preset[],
  reviews: {} as Record<string, Review>,
  pool: { note: '', people: 0, events: [], fields: {} } as Pool,
  watch: { watched: {}, changes: [], checked_at: '' } as Watch,
  hash: location.hash,
  ready: false,
  research: null as null | { query: string; steps: Step[]; error: string },
})

const get = (path: string) => fetch(path).then((r) => r.json())

export async function load() {
  const [briefs, presets, reviews, pool, watch] = await Promise.all(['signals.json', 'presets.json', 'reviews.json', 'pool.json', 'changes.json'].map(get))
  Object.assign(app, { briefs, presets, reviews, pool, watch, ready: true })
  // the server asks Context.dev at most every five minutes, so asking it once a minute is cheap
  setInterval(async () => (app.watch = await get('changes.json')), 60_000)
  addEventListener('hashchange', () => (app.hash = location.hash))
  // a field being typed in would lose its text to a poll, so polls wait for the typing to end
  setInterval(async () => {
    if (!(document.activeElement as HTMLElement | null)?.isContentEditable) app.reviews = await get('reviews.json')
  }, 3000)
}

/**
 * `#/` is Espoo's events, `#/event/<slug>` one event and `#/<brief id>` one employer. `#/join/<brief id>` is the
 * company's sign-up, `#/join/<brief id>/<event slug>` the same as an invitation to that event, and `#/join` lets a
 * company find itself.
 */
export const route = () => {
  const [, a = '', b = '', c = ''] = app.hash.split('/').map(decodeURIComponent)
  if (a === 'event') return { join: false, id: '', event: b }
  return a === 'join' || a === 'c' ? { join: true, id: b, event: c } : { join: false, id: a, event: '' }
}
export const go = (id: string) => (location.hash = `#/${encodeURIComponent(id)}`)
export const joinPath = (id: string, event = '') => `#/join/${encodeURIComponent(id)}${event ? `/${event}` : ''}`
export const joinLink = (id: string, event = '') => `${location.origin}${location.pathname}${joinPath(id, event)}`
/** Put a company's invitation link on the clipboard, which is how an invitation leaves this screen: a person sends it. */
export async function copyLink(id: string, event = '') {
  // the clipboard API needs https; on plain http fall back to selecting a hidden field
  try {
    await navigator.clipboard.writeText(joinLink(id, event))
  } catch {
    const field = Object.assign(document.createElement('textarea'), { value: joinLink(id, event) })
    document.body.append(field)
    field.select()
    document.execCommand('copy')
    field.remove()
  }
}

/** Whether a company is on an event's public page already. Then it is not invited: it is sent its profile to confirm. */
export const isComing = (id: string) => app.presets.some((p) => p.coming && p.ids.includes(id))
/** What the three states of a sign-up are called, for a company still to be invited or for one already coming. */
export const stateNames = (coming: boolean): Record<Status, string> =>
  coming ? { draft: 'Profile not sent', invited: 'Profile sent', joined: 'Profile confirmed' } : { draft: 'To invite', invited: 'Invited', joined: 'Signed up' }

/** The event's own name for a company, where the brand record calls it something else. */
export const nameOf = (b: Brief) =>
  app.presets.map((p) => p.names?.[b.id]).find(Boolean) ?? b.name.replace(/\s+(Oyj Abp|Oyj|Oy Ab|Oy|Ab|sr)$/i, '')

/** A company's sign-up so far, or the draft it starts from, where every drafted role gets its id. */
export const reviewOf = (b: Brief): Review =>
  app.reviews[b.id] ?? { status: 'draft', needs: b.card.needs.map((n, i) => ({ ...n, id: `n${String(i)}` })) }

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
