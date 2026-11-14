import { SvelteMap } from 'svelte/reactivity'
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

/** The demo's key, typed once into the Demo menu on Espoo's side and kept in this browser. With it a sign-up is
 *  saved from Espoo's side, every sign-up can be taken out, and each company's invitation link carries a token
 *  signed with it (`tokens`), so the company's own answers are saved too. Without it nothing on Espoo's side is saved. */
const KEY_KEPT = 'kutsu-demo-key'
export const demo = $state<{ key: string; tokens: Record<string, string> }>({ key: kept(), tokens: {} })
function kept() {
  try {
    return localStorage.getItem(KEY_KEPT) ?? ''
  } catch {
    return ''
  }
}
/** Check a key with the server, and keep it when it is right. */
export async function unlock(key: string) {
  const r = await fetch('unlock', { headers: { 'x-kutsu-key': key } }).catch(() => null)
  if (r?.status !== 204) return false
  demo.key = key
  try {
    localStorage.setItem(KEY_KEPT, key)
  } catch {
    // a browser that keeps nothing keeps the key until the tab closes
  }
  await signLinks()
  return true
}
/** The token each company's invitation link carries: its id signed with the key, as serve.py's link_token. */
async function signLinks() {
  if (!demo.key) return
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(demo.key), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'])
  for (const b of app.briefs) {
    if (demo.tokens[b.id]) continue
    const mac = new Uint8Array(await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(`join:${b.id}`)))
    demo.tokens[b.id] = [...mac].map((x) => x.toString(16).padStart(2, '0')).join('').slice(0, 24)
  }
}
/** What lets a write to one company's sign-up be saved: the key, or the token in the invitation link this page was opened from. */
const allowed = (id: string): Record<string, string> => {
  if (demo.key) return { 'x-kutsu-key': demo.key }
  const token = new URLSearchParams(app.hash.split('?')[1] ?? '').get('t')
  return token && route().id === id ? { 'x-kutsu-link': token } : {}
}
/** The demo key as a header, for what only Espoo's side may do. */
export const organiser = (): Record<string, string> => (demo.key ? { 'x-kutsu-key': demo.key } : {})

/** A JSON answer from our own server, as the type the caller names: the server and the page are built together. */
const get = <T>(path: string): Promise<T> => fetch(path).then((r) => r.json() as Promise<T>)

/** What only Espoo's and the companies' screens need: the sign-ups, what the monitors saw, the applications. */
let backOffice = false
async function loadBackOffice() {
  if (backOffice) return
  backOffice = true
  const [reviews, watch] = await Promise.all([get<Record<string, Review>>('reviews.json'), get<Watch>('changes.json')])
  Object.assign(app, { reviews, watch })
  void loadApplications()
}

export async function load() {
  // a person's own sign-up asks the server for nothing about anyone else: only the employers, the events and the pool's counts
  const [briefs, presets, pool] = await Promise.all([get<Brief[]>('signals.json'), get<Preset[]>('presets.json'), get<Pool>('pool.json')])
  if (!route().me) await loadBackOffice()
  Object.assign(app, { briefs, presets, pool, ready: true })
  void signLinks()
  addEventListener('hashchange', () => {
    if (!route().me) void loadBackOffice()
  })
  // the server asks Context.dev at most every five minutes, so asking it once a minute is cheap
  setInterval(() => {
    if (backOffice && !route().me) void get<Watch>('changes.json').then((seen) => (app.watch = seen))
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
    if (backOffice && !route().me && !(document.activeElement as HTMLElement | null)?.isContentEditable)
      app.reviews = { ...(await get<Record<string, Review>>('reviews.json')), ...Object.fromEntries(unsaved) }
  }, 3000)
}

/**
 * `#/` is Espoo's home, `#/events`, `#/companies`, `#/pool` and `#/applications` its sections, `#/event/<slug>` one
 * event and `#/<brief id>` one employer. `#/join/<brief id>` is the
 * company's sign-up, `#/join/<brief id>/<event slug>` the same as an invitation to that event, and `#/join` lets a
 * company find itself.
 */
const PAGES = ['events', 'companies', 'pool', 'applications']
export const route = () => {
  // an invitation link may end in `?t=<token>`, which is no part of the route
  const [, a = '', b = '', c = '', d = ''] = (app.hash.split('?')[0] ?? '').split('/').map(decodeURIComponent)
  if (a === 'event') return { join: false, me: false, page: '', item: '', id: '', event: b, tab: c, company: d }
  // `#/me` is a person's own sign-up, and `#/me/<event slug>` the same as an invitation to that event
  if (a === 'me') return { join: false, me: true, page: '', item: '', id: '', event: b, tab: '', company: '' }
  if (a === 'join' || a === 'c') return { join: true, me: false, page: '', item: '', id: b, event: c, tab: '', company: '' }
  // the sections of Espoo's side; anything else after `#/` is an employer's id, as it always was
  // a section can name one thing inside it: `#/applications/<application id>`
  if (PAGES.includes(a)) return { join: false, me: false, page: a, item: b, id: '', event: '', tab: '', company: '' }
  return { join: false, me: false, page: '', item: '', id: a, event: '', tab: '', company: '' }
}
export const go = (id: string) => (location.hash = `#/${encodeURIComponent(id)}`)
export const joinPath = (id: string, event = '') =>
  `#/join/${encodeURIComponent(id)}${event ? `/${event}` : ''}${demo.tokens[id] ? `?t=${demo.tokens[id]}` : ''}`
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

/** Sign-ups the server would not save (no key, no link of the company's own): this visitor's alone, kept over each poll until a reload. */
export const unsaved = new SvelteMap<string, Review>()
export async function saveReview(id: string, review: Review) {
  app.reviews[id] = review
  const r = await fetch(`review?id=${encodeURIComponent(id)}`, { method: 'POST', body: JSON.stringify(review), headers: allowed(id) }).catch(() => null)
  if (r?.ok) unsaved.delete(id)
  else unsaved.set(id, review)
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
    await signLinks()
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
