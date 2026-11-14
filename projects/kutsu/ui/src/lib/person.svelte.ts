import type { Invitee } from './events'
import { siteOf, type Site } from './sites'
import { nameOf } from './state.svelte'

// A person's sign-up. Everything about the person lives in this browser tab and nowhere else: the server
// reads what they hand over and answers, and keeps nothing. Closing the tab forgets it.

/** What `POST /person` answers when asked for a draft: the skill part of a profile, each item with the words it was read from. */
type Draft = {
  name: string | null
  headline: string
  field: string
  level: string
  can_do: { line: string; from: string }[]
  skills: { skill: string; from: string }[]
  experience: { title: string; organisation: string; years: string; from: string }[]
}
/** One line of the profile: what it says, the words it was read from, and which source they were in. A line the person typed has no source. */
export type Fact = { id: string; text: string; from: string; source: string; when?: string }
/** How reading one source went. */
export type Reading = { lines: number; found?: number } | { error: string }
export type Me = {
  /** the made-up person, chosen on purpose */
  sample: boolean
  /** the person chose to type their profile in, with nothing read */
  typed: boolean
  /** what they handed over: a LinkedIn username, any number of links, the text of a CV */
  linkedin: string
  links: string[]
  cv: string
  /** sources the person switched off without emptying them, and links they took off their profile */
  off: string[]
  hidden: string[]
  /** per source key: how reading it went, and what the inputs were when it was read */
  read: Record<string, Reading>
  read_from: string
  name: string
  headline: string
  field: string
  level: string
  can: Fact[]
  skills: Fact[]
  roles: Fact[]
  /** ids of lines the person took out */
  struck: string[]
  you_ok: boolean
  know_ok: boolean
  want_ok: boolean
  /** asked, never read: the fields they want to work in, what they look for, and the terms that suit them */
  wants: string[]
  looking: string
  place: string
  finnish: boolean
  abroad: boolean
  meet: string[]
  done: string
}

const KEY = 'kutsu-me-2'
/** A CV is read up to this many characters; the field says so when a longer one is pasted. */
export const CV_MOST = 20_000
const blank = (): Me => ({
  sample: false,
  typed: false,
  linkedin: '',
  links: [''],
  cv: '',
  off: [],
  hidden: [],
  read: {},
  read_from: '',
  name: '',
  headline: '',
  field: '',
  level: '',
  can: [],
  skills: [],
  roles: [],
  struck: [],
  you_ok: false,
  know_ok: false,
  want_ok: false,
  wants: [],
  looking: '',
  place: '',
  finnish: false,
  abroad: false,
  meet: [],
  done: '',
})
function stored(): Me {
  try {
    const saved = sessionStorage.getItem(KEY)
    return saved ? { ...blank(), ...(JSON.parse(saved) as Partial<Me>) } : blank()
  } catch {
    return blank()
  }
}
export const me = $state<{ is: Me }>({ is: stored() })
/** Where reading is, per source key, while it runs: "reading" the page, then "writing" it up. Not kept. */
export const progress = $state<{ at: Record<string, 'reading' | 'writing'> }>({ at: {} })
/** Keep the draft for this tab only: a reload does not lose it, closing the tab does. */
export function keep() {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(me.is))
  } catch {
    // a browser that refuses storage still runs the flow; a reload then starts again
  }
}
export function startOver(how: 'blank' | 'sample' | 'typed' = 'blank') {
  me.is = how === 'sample' ? SAMPLE() : { ...blank(), typed: how === 'typed' }
  progress.at = {}
  keep()
}

/** One thing to read: its key, what the server is asked, and what to call it in a sentence. */
export type Source = { key: string; kind: 'linkedin' | 'portfolio' | 'cv'; value: string; label: string; site?: Site }
const MOST_LINKS = 3
/** Everything the person handed over that can be read, whether switched on or not. */
export function sourcesOf(m: Me): Source[] {
  const out: Source[] = []
  if (m.linkedin) out.push({ key: 'linkedin', kind: 'linkedin', value: `https://www.linkedin.com/in/${m.linkedin}`, label: 'your LinkedIn' })
  for (const raw of m.links) {
    const site = siteOf(raw)
    // a social feed says little about work; it is shown on the profile and not read
    if (site?.read && site.id !== 'linkedin' && out.filter((s) => s.kind === 'portfolio').length < MOST_LINKS && !out.some((s) => s.value === site.href))
      out.push({ key: `link:${site.href}`, kind: 'portfolio', value: site.href, label: site.label, site })
  }
  if (m.cv.trim()) out.push({ key: 'cv', kind: 'cv', value: m.cv.slice(0, CV_MOST), label: 'your CV' })
  return out
}
export const chosen = (m: Me) => sourcesOf(m).filter((s) => !m.off.includes(s.key))
/** What the inputs were when they were last read: reading again is only needed when this changes. */
export const givenNow = (m: Me) => (m.sample ? 'sample' : chosen(m).map((s) => `${s.key}=${s.kind === 'cv' ? String(s.value.length) : s.value}`).join('|'))
/** The links on the person's profile: only the ones they gave and left there. */
export function linksOf(m: Me): Site[] {
  const all = [m.linkedin ? siteOf(`linkedin.com/in/${m.linkedin}`) : undefined, ...m.links.map(siteOf)].filter((s): s is Site => !!s)
  return all.filter((s, i) => all.findIndex((x) => x.href === s.href) === i && !m.hidden.includes(s.href))
}
export const sourceLabel = (m: Me, key: string) => (key === 'sample' ? 'the sample profile' : (sourcesOf(m).find((s) => s.key === key)?.label ?? 'what you gave'))
/** What the mark is drawn from: what the person entered on the first card, never shown and not readable back from the picture. */
export const seedOf = (m: Me) => (m.sample ? 'sample person' : [m.linkedin, ...m.links, m.cv.slice(0, 400), m.typed ? m.name : ''].join('|'))

async function ask(body: Record<string, unknown>): Promise<Draft & { material: string }> {
  const response = await fetch('person', { method: 'POST', body: JSON.stringify(body) }).catch(() => null)
  if (!response) throw new Error('The server could not be reached. Try again in a minute.')
  if (!response.ok) throw new Error((await response.text()).slice(0, 200) || 'This could not be read.')
  return (await response.json()) as Draft & { material: string }
}

const same = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase()
export const SHOWN = 3
/**
 * Read every source the person switched on, side by side. Each goes in two steps the page can show:
 * the source is read (its text comes back), then the text is written up as lines to check. What
 * arrives is added to the profile as it arrives.
 */
export async function readAll() {
  const m = me.is
  const sources = chosen(m)
  Object.assign(m, { read: {}, read_from: givenNow(m), name: '', headline: '', field: '', level: '', can: [], skills: [], roles: [], struck: [], you_ok: false, know_ok: false, want_ok: false, done: '' })
  await Promise.all(
    sources.map(async (source) => {
      try {
        progress.at[source.key] = 'reading'
        const material = source.kind === 'cv' ? source.value : (await ask({ kind: source.kind, value: source.value, draft: false })).material
        const lines = material.split('\n').filter((l) => l.trim()).length
        m.read[source.key] = { lines }
        if (material.trim().length < 200) throw new Error('There is too little text there to read a profile from.')
        progress.at[source.key] = 'writing'
        const got = await ask({ kind: 'cv', value: material })
        m.name ||= got.name ?? ''
        m.headline ||= got.headline
        m.field ||= got.field
        m.level ||= got.level
        const before = m.can.length + m.skills.length + m.roles.length
        for (const [i, c] of got.can_do.entries()) if (!m.can.some((x) => same(x.text, c.line))) m.can.push({ id: `can:${source.key}:${String(i)}`, text: c.line, from: c.from, source: source.key })
        for (const s of got.skills) if (!m.skills.some((x) => same(x.text, s.skill))) m.skills.push({ id: `skill:${s.skill.toLowerCase()}`, text: s.skill, from: s.from, source: source.key })
        for (const [i, r] of got.experience.entries()) {
          const text = [r.title, r.organisation].filter((x) => x.trim()).join(', ')
          if (text && !m.roles.some((x) => same(x.text, text))) m.roles.push({ id: `role:${source.key}:${String(i)}`, text, from: r.from, source: source.key, when: r.years })
        }
        m.read[source.key] = { lines, found: m.can.length + m.skills.length + m.roles.length - before }
      } catch (error) {
        m.read[source.key] = { error: error instanceof Error ? error.message : 'This could not be read.' }
      } finally {
        progress.at = Object.fromEntries(Object.entries(progress.at).filter(([key]) => key !== source.key))
      }
    }),
  )
  // three things the person can do are kept by default; the rest are theirs to add
  m.struck = m.can.slice(SHOWN).map((f) => f.id)
  m.wants = m.field ? [m.field] : []
  keep()
}

/** A line the person wrote themselves. */
export function addOwn(list: 'can' | 'skills' | 'roles', text: string) {
  const m = me.is
  const clean = text.replace(/\s+/g, ' ').trim()
  if (!clean || m[list].some((f) => same(f.text, clean))) return
  m[list].push({ id: `${list}:own:${String(Date.now())}`, text: clean, from: '', source: '' })
  keep()
}

/** The sample person. Made up: the name, the work and the page, whose address ends in .example so it can be nobody's. */
const SAMPLE = (): Me => {
  const fact = (id: string, text: string, from: string, when?: string): Fact => ({ id, text, from, source: 'sample', ...(when ? { when } : {}) })
  const can = [
    fact('can:sample:0', 'Runs thin-film deposition on production tools', 'Ran ALD and PECVD deposition on 200 mm production tools'),
    fact('can:sample:1', 'Finds the cause of yield loss from inline data', 'traced a yield excursion to chamber seasoning using SPC charts'),
    fact('can:sample:2', 'Writes process recipes and their control plans', 'wrote recipes and control plans for three new film stacks'),
    fact('can:sample:3', 'Trains operators on new cleanroom procedures', 'trained two shifts of operators on the new gowning procedure'),
  ]
  return {
    ...blank(),
    sample: true,
    links: ['olena-k.example'],
    read: { sample: { lines: 12, found: 11 } },
    read_from: 'sample',
    name: 'Olena K.',
    headline: 'Process engineer for thin films and cleanroom work',
    field: 'Semiconductors and photonics',
    level: 'Experienced',
    can,
    skills: ['Thin-film deposition', 'SPC', 'Cleanroom processes', 'Yield analysis', 'Python'].map((s) => fact(`skill:${s.toLowerCase()}`, s, 'Skills')),
    roles: [fact('role:sample:0', 'Process Engineer, a wafer fab', '', '2021–now'), fact('role:sample:1', 'Research Assistant, a university cleanroom', '', '2019–2021')],
    struck: can.slice(SHOWN).map((f) => f.id),
    wants: ['Semiconductors and photonics'],
  }
}

export const kept = (m: Me, facts: Fact[]) => facts.filter((f) => !m.struck.includes(f.id))

/** A skill's name without case, spaces or punctuation, so "Next.js" and "NextJS" are one. */
const plain = (skill: string) => skill.toLowerCase().replace(/[^a-z0-9+#]/g, '')
/** Why an employer and this person might want to meet: what the employer asks for, and what of that the person has. */
export type Match = { employer: Invitee; role: string; shared: string[]; reasons: string[] }
/** The event's employers that look for what the person does, those asking for most of what the person knows first. Employers are ordered here, never people. */
export function matches(m: Me, employers: Invitee[]): Match[] {
  const knows = kept(m, m.skills).map((s) => plain(s.text))
  const out: (Match & { score: number })[] = []
  for (const employer of employers) {
    let best: (Match & { score: number }) | undefined
    for (const role of employer.roles) {
      const shared = role.skills.filter((s) => knows.includes(plain(s)))
      const wanted = !!role.family && m.wants.includes(role.family)
      if (!shared.length && !wanted) continue
      const english = role.language !== 'Finnish needed' || m.finnish
      const reasons = [
        shared.length ? `Asks for ${shared.slice(0, 2).join(' and ')}, which you know` : role.skills.length ? `Asks for ${role.skills.slice(0, 2).join(' and ')}` : '',
        role.language ? (english ? (role.language === 'Finnish needed' ? 'Needs Finnish, which you have' : 'English is enough') : 'Needs Finnish') : '',
        role.workplace && m.place ? (role.workplace === m.place ? `${role.workplace}, as you prefer` : role.workplace) : '',
      ].filter(Boolean)
      const score = shared.length * 2 + (wanted ? 2 : 0) + (english ? 0 : -3)
      if (!best || score > best.score) best = { employer, role: role.title, shared, reasons, score }
    }
    if (best) out.push(best)
  }
  return out.sort((a, b) => b.score - a.score || nameOf(a.employer.brief).localeCompare(nameOf(b.employer.brief)))
}
