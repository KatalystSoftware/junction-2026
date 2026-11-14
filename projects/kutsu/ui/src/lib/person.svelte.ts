import type { Invitee } from './events'
import { nameOf } from './state.svelte'

// A person's sign-up. Everything about the person lives in this browser tab and nowhere else: the server
// reads what they hand over and answers, and keeps nothing. Closing the tab forgets it.

export type Source = 'linkedin' | 'portfolio' | 'cv'
/** What `POST /person` answers: the skill part of a profile, each item with the words it was read from. */
export type Read = {
  name: string | null
  headline: string
  field: string
  level: string
  can_do: { line: string; from: string }[]
  skills: { skill: string; from: string }[]
  experience: { title: string; organisation: string; years: string; from: string }[]
  languages: { language: string; from: string }[]
}
/** One line of the profile, with where it was read and the words behind it. */
export type Fact = { id: string; text: string; from: string; source: Source | 'sample' }
export type Me = {
  /** the made-up person, chosen on purpose */
  sample: boolean
  given: Record<Source, string>
  /** per source: how it went */
  read: Partial<Record<Source, { lines: number } | { error: string }>>
  name: string
  headline: string
  field: string
  level: string
  can: Fact[]
  skills: Fact[]
  roles: Fact[]
  speaks: string[]
  /** ids of lines the person took out */
  struck: string[]
  you_ok: boolean
  know_ok: boolean
  /** asked, never read: the fields they want to work in, what they look for, and the terms that suit them */
  wants: string[]
  looking: string
  place: string
  finnish: boolean
  abroad: boolean
  meet: string[]
  done: string
}

const KEY = 'kutsu-me'
const blank = (): Me => ({
  sample: false,
  given: { linkedin: '', portfolio: '', cv: '' },
  read: {},
  name: '',
  headline: '',
  field: '',
  level: '',
  can: [],
  skills: [],
  roles: [],
  speaks: [],
  struck: [],
  you_ok: false,
  know_ok: false,
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
/** Keep the draft for this tab only: a reload does not lose it, closing the tab does. */
export function keep() {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(me.is))
  } catch {
    // a browser that refuses storage still runs the flow; a reload then starts again
  }
}
export function startOver(sample = false) {
  me.is = sample ? SAMPLE() : blank()
  keep()
}

export const SOURCE_NAME: Record<Source | 'sample', string> = { linkedin: 'your LinkedIn', portfolio: 'your page', cv: 'your CV', sample: 'the sample profile' }
/** What the mark is drawn from: what the person entered on the first card, never shown and not readable back from the picture. */
export const seedOf = (m: Me) => (m.sample ? 'sample person' : [m.given.linkedin, m.given.portfolio, m.given.cv.slice(0, 400)].join('|'))

/** Read one source through the server. The answer is the only copy: the server keeps nothing. */
async function read(source: Source, value: string): Promise<Read> {
  const response = await fetch('person', { method: 'POST', body: JSON.stringify({ kind: source, value }) }).catch(() => null)
  if (!response) throw new Error('The server could not be reached. Try again in a minute.')
  if (!response.ok) throw new Error((await response.text()).slice(0, 200) || 'This could not be read.')
  return (await response.json()) as Read
}

const same = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase()
/** Read every source the person ticked, side by side, and put what came back into one profile. */
export async function readAll(sources: Source[]) {
  const m = me.is
  m.read = {}
  Object.assign(m, { name: '', headline: '', field: '', level: '', can: [], skills: [], roles: [], speaks: [], struck: [], you_ok: false, know_ok: false, done: '' })
  await Promise.all(
    sources.map(async (source) => {
      try {
        const got = await read(source, m.given[source])
        m.read[source] = { lines: got.can_do.length + got.skills.length + got.experience.length }
        m.name ||= got.name ?? ''
        m.headline ||= got.headline
        m.field ||= got.field
        m.level ||= got.level
        for (const [i, c] of got.can_do.entries()) if (!m.can.some((x) => same(x.text, c.line))) m.can.push({ id: `can:${source}:${String(i)}`, text: c.line, from: c.from, source })
        for (const s of got.skills) if (!m.skills.some((x) => same(x.text, s.skill))) m.skills.push({ id: `skill:${s.skill.toLowerCase()}`, text: s.skill, from: s.from, source })
        for (const [i, r] of got.experience.entries())
          if (!m.roles.some((x) => same(x.text, `${r.title}, ${r.organisation}`)))
            m.roles.push({ id: `role:${source}:${String(i)}`, text: `${r.title}, ${r.organisation}`, from: r.years || r.from, source })
        for (const l of got.languages) if (!m.speaks.some((x) => same(x, l.language))) m.speaks.push(l.language)
      } catch (error) {
        m.read[source] = { error: error instanceof Error ? error.message : 'This could not be read.' }
      }
    }),
  )
  m.wants = m.field ? [m.field] : []
  m.finnish = m.speaks.some((l) => /finnish|suomi/i.test(l))
  keep()
}

/** The sample person. Made up: the name, the work and the addresses, which end in .example so they can be nobody's. */
const SAMPLE = (): Me => {
  const fact = (id: string, text: string, from: string): Fact => ({ id, text, from, source: 'sample' })
  return {
    ...blank(),
    sample: true,
    given: { linkedin: 'olena-k.example/linkedin', portfolio: 'olena-k.example', cv: '' },
    read: { linkedin: { lines: 9 }, portfolio: { lines: 3 } },
    name: 'Olena K.',
    headline: 'Process engineer for thin films and cleanroom work',
    field: 'Semiconductors and photonics',
    level: 'Experienced',
    can: [
      fact('can:sample:0', 'Runs thin-film deposition on production tools', 'Ran ALD and PECVD deposition on 200 mm production tools'),
      fact('can:sample:1', 'Finds the cause of yield loss from inline data', 'traced a yield excursion to chamber seasoning using SPC charts'),
      fact('can:sample:2', 'Writes process recipes and their control plans', 'wrote recipes and control plans for three new film stacks'),
      fact('can:sample:3', 'Trains operators on new cleanroom procedures', 'trained two shifts of operators on the new gowning procedure'),
    ],
    skills: ['Thin-film deposition', 'SPC', 'Cleanroom processes', 'Yield analysis', 'Python'].map((s) => fact(`skill:${s.toLowerCase()}`, s, 'Skills')),
    roles: [fact('role:sample:0', 'Process Engineer, a wafer fab', '2021–now'), fact('role:sample:1', 'Research Assistant, a university cleanroom', '2019–2021')],
    speaks: ['English', 'Ukrainian'],
    wants: ['Semiconductors and photonics'],
  }
}

export const kept = (m: Me, facts: Fact[]) => facts.filter((f) => !m.struck.includes(f.id))

/** Why an employer and this person might want to meet, one short reason for each of skill, wish and fit. */
/** A skill's name without case, spaces or punctuation, so "Next.js" and "NextJS" are one. */
const plain = (skill: string) => skill.toLowerCase().replace(/[^a-z0-9+#]/g, '')
export type Match = { employer: Invitee; role: string; reasons: string[] }
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
      // one short reason each for skill and for fit; the wish is why the employer is on the list at all
      const reasons = [
        shared.length ? `Asks for ${shared.slice(0, 2).join(' and ')}, which you know` : role.skills.length ? `Asks for ${role.skills.slice(0, 2).join(' and ')}` : '',
        role.language ? (english ? (role.language === 'Finnish needed' ? 'Needs Finnish, which you have' : 'English is enough') : 'Needs Finnish') : '',
        role.workplace && m.place ? (role.workplace === m.place ? `${role.workplace}, as you prefer` : role.workplace) : '',
      ].filter(Boolean)
      const score = shared.length * 2 + (wanted ? 2 : 0) + (english ? 0 : -3)
      if (!best || score > best.score) best = { employer, role: role.title, reasons, score }
    }
    if (best) out.push(best)
  }
  return out.sort((a, b) => b.score - a.score || nameOf(a.employer.brief).localeCompare(nameOf(b.employer.brief)))
}
