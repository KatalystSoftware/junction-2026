import { app, nameOf, reviewOf } from './state.svelte'
import type { Brief, Need, PoolField, Preset, Signal, Told } from './types'

// An event as Espoo plans it: its employers, and the people in the pool who do the work those
// employers look for. The upcoming event comes from its list of employers; a suggested one from a
// field where the roles drafted for employers meet people who already came to earlier events.
//
// A role is drafted from what the employer said in public until the employer confirms it, so every
// count of employers carries how many of them have confirmed.

export type Invitee = { brief: Brief; roles: Need[]; news: Told | undefined }
/** One thing looked for, against what the pool has: a field of work, or a skill inside one field. */
export type Row = { label: string; asked: number; confirmed: number; have: number }
/** One field of work for some employers: which of them look for it, the pool's people in it, and the skills asked. */
export type Field = { name: string; employers: Invitee[]; people: PoolField; rows: Row[] }
export type Plan = {
  slug: string
  title: string
  kind: 'upcoming' | 'suggested'
  /** its employers are on the event's public page already */
  coming: boolean
  date: string
  /** its dates as the event's own page gives them */
  when: string
  url: string
  employers: Invitee[]
  /** the fields its employers look for, most asked first; a suggested event has one */
  fields: Field[]
}

const slugOf = (p: Preset) => slug(p.title)
export const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')

/** A count of people as a screen may show it. Under five is too easy to recognise as someone. */
export const some = (n: number) => (n < 5 ? 'fewer than 5' : n.toLocaleString('en'))

// "growth" also files a company that shrank, which is true of it and no reason to invite it
const SHRANK = /\b(down|fell|fall|falls|declin\w+|decreas\w+|loss(es)?|lay-?offs?|cuts?|redundanc\w+)\b/i
const month = (ms: number) => new Date(ms).toISOString().slice(0, 7)
/** The newest funding or growth news a company would tell: the reason to invite it now. */
export const news = (b: Brief): Told | undefined =>
  b.card.tell
    .filter((t) => (t.kind === 'funding' || t.kind === 'growth') && t.date && t.date.slice(0, 7) <= month(Date.now()) && !SHRANK.test(t.line))
    .sort((x, y) => y.date.localeCompare(x.date))[0]
export const recent = (i: Invitee) => (i.news?.date ?? '') >= month(Date.now() - 365 * 864e5)
/** The public statement an employer's news rests on. */
export const sourceOf = (i: Invitee): Signal | undefined => i.brief.signals.find((s) => s.id === i.news?.signals[0])
export const confirmed = (i: Invitee) => reviewOf(i.brief).status === 'joined'

const invitee = (brief: Brief): Invitee => ({ brief, roles: reviewOf(brief).needs, news: news(brief) })
// news first, newest on top; then by name, so the order does not move while people sign up
const byNews = (a: Invitee, b: Invitee) => (b.news?.date ?? '').localeCompare(a.news?.date ?? '') || nameOf(a.brief).localeCompare(nameOf(b.brief))

const NOBODY: PoolField = { people: 0, wanting: 0, levels: {}, english: 0, finnish: 0, abroad: 0, events: {}, skills: {} }

/** One field among some employers: those with a role in it, the pool's people, and the skills those roles ask for. */
function field(name: string, employers: Invitee[]): Field {
  const here = employers.map((e) => ({ ...e, roles: e.roles.filter((r) => r.family === name) })).filter((e) => e.roles.length)
  const people = app.pool.fields[name] ?? NOBODY
  const skills = new Map<string, Invitee[]>()
  for (const e of here) for (const skill of new Set(e.roles.flatMap((r) => r.skills))) skills.set(skill, [...(skills.get(skill) ?? []), e])
  const rows = [...skills]
    .sort((a, b) => b[1].length - a[1].length)
    // a skill one employer asks for says little about an event, unless there is little else
    .filter(([, asking], i) => asking.length > 1 || i < 6)
    .slice(0, 8)
    .map(([label, asking]) => ({ label, asked: asking.length, confirmed: asking.filter(confirmed).length, have: people.skills[label] ?? 0 }))
  return { name, employers: here, people, rows }
}

/** The fields some employers look for, most asked first. */
const fieldsOf = (employers: Invitee[]): Field[] =>
  [...new Set(employers.flatMap((e) => e.roles.map((r) => r.family).filter((f): f is string => !!f)))]
    .map((name) => field(name, employers))
    .sort((a, b) => b.employers.length - a.employers.length || a.name.localeCompare(b.name))

/** Fields where an event is worth holding: at least three employers look for it, and the pool has the people. Fresh news first. */
export const suggested = (): Plan[] =>
  fieldsOf(app.briefs.map(invitee))
    .filter((f) => f.employers.length >= 3 && f.people.people >= 5)
    .map((f): Plan => ({ slug: slug(f.name), title: f.name, kind: 'suggested', coming: false, date: '', when: '', url: '', employers: f.employers.sort(byNews), fields: [f] }))
    .sort((a, b) => b.employers.filter(recent).length - a.employers.filter(recent).length || (b.fields[0]?.people.people ?? 0) - (a.fields[0]?.people.people ?? 0))

/** An event that has its employers already. */
export const upcoming = (preset: Preset): Plan => {
  const employers = preset.ids
    .map((id) => app.briefs.find((b) => b.id === id))
    .filter((b): b is Brief => !!b)
    .map(invitee)
  return {
    slug: slugOf(preset),
    title: preset.title,
    kind: 'upcoming',
    coming: !!preset.coming,
    date: preset.date ?? '',
    when: preset.note.split(',')[0] ?? '',
    url: preset.url,
    employers: employers.sort(byNews),
    fields: fieldsOf(employers),
  }
}

export const plans = (): Plan[] => [...app.presets.map(upcoming), ...suggested()]

/** An event as the invited company reads it: its name, when it is, and what is settled about it. */
export type Occasion = { slug: string; name: string; when: string; facts: string; dated: boolean }
/** An event as an invitation names it. A suggested event has no date yet. */
export const occasionOf = (plan: Plan | undefined): Occasion =>
  !plan
    ? { slug: '', name: 'A talent event', when: 'date to be set', facts: '', dated: false }
    : plan.kind === 'upcoming'
      ? { slug: plan.slug, name: plan.title, when: plan.when, facts: app.presets.find((p) => slugOf(p) === plan.slug)?.facts ?? '', dated: true }
      : { slug: plan.slug, name: `${plan.title} talent event`, when: 'date to be set', facts: '', dated: false }
/**
 * The event a company's invitation is for: the one named in its link, else the event it is already
 * coming to, else the suggested event it would be invited to first.
 */
export function occasion(slug: string, brief: Brief): Occasion {
  const all = plans()
  const coming = all.find((p) => p.kind === 'upcoming' && (slug ? p.slug === slug : p.employers.some((e) => e.brief.id === brief.id)))
  return occasionOf(coming ?? all.find((p) => p.slug === slug) ?? all.find((p) => p.kind === 'suggested' && p.employers.some((e) => e.brief.id === brief.id)))
}

/** "9 employers, 2 confirmed": how many look for something, and how many of those said so themselves. */
export const asking = (n: number, sure: number) => `${String(n)} ${n === 1 ? 'employer' : 'employers'}${sure ? `, ${String(sure)} confirmed` : ''}`

/** Whole days from today until a date; negative once it has passed. */
export const daysTo = (date: string) => Math.ceil((new Date(date).getTime() - Date.now()) / 864e5)
