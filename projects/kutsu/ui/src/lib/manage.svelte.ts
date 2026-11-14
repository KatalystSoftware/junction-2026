import type { Applicant } from './types'

/**
 * What the organiser does with an event's applications and invitations, kept in this browser (localStorage): the
 * golden-ticket send, how often the regular link was copied, and each decision, keyed by who took it (Espoo, or a
 * company by its id) and the application. Sample data; nothing leaves the browser.
 */
export type Decision = { d: 'accept' | 'decline'; reason: string; by: string; at: string }
export type Golden = { at: string; n: number; events: string[]; fields: string[]; message: string }
type Manage = { golden: Golden | null; copies: number; decisions: Record<string, Decision> }

const KEY = 'kutsu-manage-v1'
const read = (): Manage | null => {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? (JSON.parse(raw) as Manage) : null
  } catch {
    return null
  }
}
export const manage = $state<Manage>(read() ?? { golden: null, copies: 0, decisions: {} })
export const persist = () => {
  try {
    localStorage.setItem(KEY, JSON.stringify(manage))
  } catch {
    /* a private window may refuse; the screen still works for this visit */
  }
}

export const decisionKey = (by: string, id: string) => `${by}:${id}`
export const decisionOf = (by: string, id: string): Decision | undefined => manage.decisions[decisionKey(by, id)]
export function decide(by: string, id: string, d: 'accept' | 'decline', reason: string) {
  manage.decisions[decisionKey(by, id)] = { d, reason, by, at: new Date().toISOString() }
  persist()
}
export function undecide(by: string, id: string) {
  delete manage.decisions[decisionKey(by, id)]
  persist()
}
export function sendGolden(g: Omit<Golden, 'at'>) {
  manage.golden = { ...g, at: new Date().toISOString() }
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
