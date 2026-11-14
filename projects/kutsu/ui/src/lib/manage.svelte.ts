import type { Applicant } from './types'

/**
 * What the organiser does with an event's applications and invitation, kept in this browser (localStorage): the send to
 * past attendees, how often the invitation link was copied, and each decision, keyed by who took it (Espoo, or a
 * company by its id) and the application. Sample data; nothing leaves the browser.
 */
export type Decision = { d: 'accept' | 'decline'; reason: string; by: string; at: string }
export type Sent = { at: string; n: number; events: string[]; fields: string[]; message: string }
type Manage = { sent: Sent | null; copies: number; decisions: Record<string, Decision> }

const KEY = 'kutsu-manage-v1'
const read = (): Manage | null => {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? (JSON.parse(raw) as Manage) : null
  } catch {
    return null
  }
}
export const manage = $state<Manage>({ sent: null, copies: 0, decisions: {}, ...read() })
export const persist = () => {
  try {
    localStorage.setItem(KEY, JSON.stringify(manage))
  } catch {
    /* a private window may refuse; the screen still works for this visit */
  }
}

// a timestamp for the record; the lint prefers SvelteDate for anything held in state, but this is read once and stored as text
const now = () => new Date(Date.now()).toISOString()
export const decisionKey = (by: string, id: string) => `${by}:${id}`
export const decisionOf = (by: string, id: string): Decision | undefined => manage.decisions[decisionKey(by, id)]
export function decide(by: string, id: string, d: 'accept' | 'decline', reason: string) {
  manage.decisions[decisionKey(by, id)] = { d, reason, by, at: now() }
  persist()
}
export function undecide(by: string, id: string) {
  manage.decisions = Object.fromEntries(Object.entries(manage.decisions).filter(([k]) => k !== decisionKey(by, id)))
  persist()
}
export function sendInvitation(g: Omit<Sent, 'at'>) {
  manage.sent = { ...g, at: now() }
  persist()
}
export function countCopy() {
  manage.copies += 1
  persist()
}

export const applications = $state({ list: [] as Applicant[], note: '' })
export async function loadApplications() {
  try {
    const r = await fetch('applications.json')
    if (!r.ok) return
    const j = (await r.json()) as { note: string; applicants: Applicant[] }
    applications.list = j.applicants
    applications.note = j.note
  } catch {
    /* the screen says there are none */
  }
}
