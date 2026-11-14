import { app, nameOf, reviewOf } from './state.svelte'
import type { Brief, Need, PoolField, Preset, Told } from './types'

// An event as Espoo plans it: the employers to invite, and the people in the pool who do the work
// those employers ask for. The upcoming event comes from its list of employers; a suggested one from
// a field where what employers say they need meets people who already came to earlier events.

export type Invitee = { brief: Brief; roles: Need[]; news: Told | undefined }
export type Row = { label: string; asked: number; have: number; href?: string }
export type Plan = {
  slug: string
  title: string
  kind: 'upcoming' | 'suggested'
  date: string
  fields: string[]
  employers: Invitee[]
  /** the pool's people in these fields. Only an event in one field shows it as a number: across many fields it is nearly everyone */
  people: PoolField
  /** what is asked for against what the pool has: fields for a whole event, skills for one field */
  rows: Row[]
}

export const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')

/** A count of people as a screen may show it. Under five is too easy to recognise as someone. */
export const some = (n: number) => (n < 5 ? 'fewer than 5' : n.toLocaleString('en'))

// "growth" also files a company that shrank, which is true of it and no reason to invite it
const SHRANK = /\b(down|fell|fall|falls|declin\w+|decreas\w+|loss(es)?|lay-?offs?|cuts?|redundanc\w+)\b/i
const today = () => new Date().toISOString().slice(0, 7)
/** The newest funding or growth news a company would tell: the reason to invite it now. */
export const news = (b: Brief): Told | undefined =>
  b.card.tell
    .filter((t) => (t.kind === 'funding' || t.kind === 'growth') && t.date && t.date.slice(0, 7) <= today() && !SHRANK.test(t.line))
    .sort((x, y) => y.date.localeCompare(x.date))[0]

const yearAgo = () => new Date(Date.now() - 365 * 864e5).toISOString().slice(0, 7)
export const recent = (i: Invitee) => (i.news?.date ?? '') >= yearAgo()

const invitee = (brief: Brief, roles: Need[]): Invitee => ({ brief, roles, news: news(brief) })
// news first, newest on top; then by name, so the order does not move while people sign up
const byNews = (a: Invitee, b: Invitee) => (b.news?.date ?? '').localeCompare(a.news?.date ?? '') || nameOf(a.brief).localeCompare(nameOf(b.brief))

const EMPTY: PoolField = { people: 0, wanting: 0, levels: {}, english: 0, finnish: 0, abroad: 0, events: {}, skills: {} }
const add = (a: Record<string, number>, b: Record<string, number>) => {
  const out = { ...a }
  for (const [k, v] of Object.entries(b)) out[k] = (out[k] ?? 0) + v
  return out
}
/** The pool's people in several fields, as one count. */
export const peopleIn = (fields: string[]): PoolField =>
  fields
    .map((f) => app.pool.fields[f])
    .filter((f): f is PoolField => !!f)
    .reduce(
      (a, f) => ({
        people: a.people + f.people,
        wanting: a.wanting + f.wanting,
        levels: add(a.levels, f.levels),
        english: a.english + f.english,
        finnish: a.finnish + f.finnish,
        abroad: a.abroad + f.abroad,
        events: add(a.events, f.events),
        skills: add(a.skills, f.skills),
      }),
      EMPTY,
    )

/** Every field of work, with the employers whose roles ask for it. A company's own answers count once it has given them. */
const asked = () => {
  const fields = new Map<string, Invitee[]>()
  for (const brief of app.briefs) {
    const roles = reviewOf(brief).needs
    for (const field of new Set(roles.map((n) => n.family).filter((f): f is string => !!f)))
      fields.set(field, [...(fields.get(field) ?? []), invitee(brief, roles.filter((n) => n.family === field))])
  }
  return fields
}

const counted = (names: string[]) => {
  const count = new Map<string, number>()
  for (const name of names) count.set(name, (count.get(name) ?? 0) + 1)
  return [...count].sort((a, b) => b[1] - a[1])
}

/** Fields where an event is worth holding: at least three employers ask, and the pool has the people. Fresh news first. */
export const suggested = (): Plan[] =>
  [...asked()]
    .filter(([field, employers]) => employers.length >= 3 && (app.pool.fields[field]?.people ?? 0) >= 5)
    .map(([field, employers]): Plan => {
      const people = peopleIn([field])
      return {
        slug: slug(field),
        title: field,
        kind: 'suggested',
        date: '',
        fields: [field],
        employers: employers.sort(byNews),
        people,
        // a skill asked by one employer only says little about an event
        rows: counted(employers.flatMap((e) => [...new Set(e.roles.flatMap((r) => r.skills))]))
          .filter(([, n], i) => n > 1 || i < 6)
          .slice(0, 8)
          .map(([label, n]) => ({ label, asked: n, have: people.skills[label] ?? 0 })),
      }
    })
    .sort((a, b) => b.employers.filter(recent).length - a.employers.filter(recent).length || b.people.people - a.people.people)

/** An event that has its employers already: the people to invite are those who do what these employers ask for. */
export const upcoming = (preset: Preset): Plan => {
  const employers = preset.ids
    .map((id) => app.briefs.find((b) => b.id === id))
    .filter((b): b is Brief => !!b)
    .map((b) => invitee(b, reviewOf(b).needs))
  const fields = counted(employers.flatMap((e) => [...new Set(e.roles.map((r) => r.family).filter((f): f is string => !!f))]))
  return {
    slug: slug(preset.title),
    title: preset.title,
    kind: 'upcoming',
    date: preset.date ?? '',
    fields: fields.map(([f]) => f),
    employers: employers.sort(byNews),
    people: peopleIn(fields.map(([f]) => f)),
    rows: fields.map(([label, n]) => ({ label, asked: n, have: app.pool.fields[label]?.people ?? 0, href: `#/event/${slug(label)}` })),
  }
}

export const plans = (): Plan[] => [...app.presets.map(upcoming), ...suggested()]

/** Whole days from today until a date; negative once it has passed. */
export const daysTo = (date: string) => Math.ceil((new Date(date).getTime() - Date.now()) / 864e5)
