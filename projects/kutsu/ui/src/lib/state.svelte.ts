import { loadApplications } from './manage.svelte'
import type { Brief, Pool, Preset, Review, Status, Step, Watch } from './types'

/** Everything the page shows. Reviews are polled, so a company's reply arrives without a reload. */
type App = {
  briefs: Brief[]
  presets: Preset[]
  reviews: Record<string, Review>
  pool: Pool
  watch: Watch
  hash: string
  ready: boolean
  research: null | { query: string; steps: Step[]; error: string }
}
export const app = $state<App>({
  briefs: [],
  presets: [],
  reviews: {},
  pool: { note: '', people: 0, events: [], fields: {} },
  watch: { watched: {}, changes: [], checked_at: '' },
  hash: location.hash,
  ready: false,
  research: null,
})

/** A JSON answer from our own server, as the type the caller names: the server and the page are built together. */
const get = <T>(path: string): Promise<T> => fetch(path).then((r) => r.json() as Promise<T>)

export async function load() {
  const [briefs, presets, reviews, pool, watch] = await Promise.all([
    get<Brief[]>('signals.json'),
    get<Preset[]>('presets.json'),
    get<Record<string, Review>>('reviews.json'),
    get<Pool>('pool.json'),
    get<Watch>('changes.json'),
  ])
  Object.assign(app, { briefs, presets, reviews, pool, watch, ready: true })
  void loadApplications()
  // the server asks Context.dev at most every five minutes, so asking it once a minute is cheap
  setInterval(() => {
    void get<Watch>('changes.json').then((seen) => (app.watch = seen))
  }, 60_000)
  // A new screen starts at its top; back or forward through the browser's history returns to where the reader was.
  // Each history entry is numbered in history.state; the position of the current one follows the reader's scrolling,
  // and is not touched while a fresh render still moves the page.
  const scrolls: Record<number, number> = {}
  /** The number this page gave the current history entry, if it has given one. */
  const entry = () => (history.state as { i?: number } | null)?.i
  let at = entry() ?? 0
  let settling = false
  if (!history.state) history.replaceState({ i: at }, '')
  history.scrollRestoration = 'manual'
  addEventListener('scroll', () => { if (!settling) scrolls[at] = scrollY }, { passive: true })
  // the page jumps a little when a link is pressed, before the hash changes, so the position to come back to is the one at the press
  let pressed = -1
  let pressedAt = 0
  const press = () => { pressed = scrollY; pressedAt = performance.now() }
  addEventListener('pointerdown', press, true)
  addEventListener('keydown', press, true)
  const settle = (y: number, tries: number) => {
    scrollTo({ top: y })
    if (Math.abs(scrollY - y) > 2 && tries > 0) setTimeout(() => { settle(y, tries - 1) }, 50)
    else settling = false
  }
  addEventListener('hashchange', () => {
    if (pressed >= 0 && performance.now() - pressedAt < 1500) scrolls[at] = pressed
    pressed = -1
    settling = true
    const numbered = entry()
    const traverse = numbered !== undefined
    if (traverse) at = numbered
    else {
      at += 1
      history.replaceState({ i: at }, '')
    }
    app.hash = location.hash
    requestAnimationFrame(() => { settle(traverse ? (scrolls[at] ?? 0) : 0, traverse ? 10 : 0) })
  })
  // a field being typed in would lose its text to a poll, so polls wait for the typing to end
  setInterval(async () => {
    if (!(document.activeElement as HTMLElement | null)?.isContentEditable) app.reviews = await get<Record<string, Review>>('reviews.json')
  }, 3000)
}

/**
 * `#/` is Espoo's events, `#/event/<slug>` one event and `#/<brief id>` one employer. `#/join/<brief id>` is the
 * company's sign-up, `#/join/<brief id>/<event slug>` the same as an invitation to that event, and `#/join` lets a
 * company find itself.
 */
export const route = () => {
  const [, a = '', b = '', c = '', d = ''] = app.hash.split('/').map(decodeURIComponent)
  if (a === 'event') return { join: false, id: '', event: b, tab: c, company: d }
  return a === 'join' || a === 'c' ? { join: true, id: b, event: c, tab: '', company: '' } : { join: false, id: a, event: '', tab: '', company: '' }
}
export const go = (id: string) => (location.hash = `#/${encodeURIComponent(id)}`)
export const joinPath = (id: string, event = '') => `#/join/${encodeURIComponent(id)}${event ? `/${event}` : ''}`
export const joinLink = (id: string, event = '') => `${location.origin}${location.pathname}${joinPath(id, event)}`
/** Put a company's invitation link on the clipboard, which is how an invitation leaves this screen: a person sends it. */
export const copyLink = (id: string, event = '') => copyText(joinLink(id, event))
/** Put text on the clipboard. False when the browser refuses, so no screen says "copied" when nothing was. */
export async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}

/** Whether a company is on an event's public page already. Then it is not invited: it is sent its profile to confirm. */
export const isComing = (id: string) => app.presets.some((p) => p.coming && p.ids.includes(id))
/** What the three states of a sign-up are called, for a company still to be invited or for one already coming. */
export const stateNames = (coming: boolean): Record<Status, string> =>
  coming ? { draft: 'Not sent', invited: 'Sent', joined: 'Confirmed' } : { draft: 'To invite', invited: 'Invited', joined: 'Signed up' }

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
    const steps = await get<Step[]>(`progress?q=${encodeURIComponent(query)}`).catch(() => null)
    if (steps && run === mine && app.research) app.research.steps = steps
  }, 400)
  try {
    const r = await fetch(`brief?q=${encodeURIComponent(query)}`)
    if (!r.ok) throw new Error(await r.text())
    const brief = (await r.json()) as Brief
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
