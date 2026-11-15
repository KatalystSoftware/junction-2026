import type { Invitee } from './events'
import { nameOf, reviewOf } from './state.svelte'
import type { Applicant, Brief, Need } from './types'

/**
 * How an applicant fits a drafted role, line by line, the way the first organiser screen (projects/kutsu/esittely) reads a pair: what
 * overlaps, what is missing, and what is worth checking in person. No score is shown to anyone; the number here
 * only orders the roles so the closest comes first.
 */
export type FitLine = { kind: 'overlap' | 'gap' | 'check'; text: string }
export type Fit = { brief: Brief; need: Need; score: number; lines: FitLine[] }

const LEVELS = ['Early career', 'Experienced', 'Senior', 'Lead']
const depthText = (s: Applicant['skills'][number]) =>
  s.depth === 'work' ? `used at work${s.years ? `, ${String(s.years)} yr` : ''}` : s.depth === 'project' ? 'own projects' : 'learning it now'

export function fitNeed(a: Applicant, brief: Brief, need: Need): Fit {
  const have = new Map(a.skills.map((s) => [s.name.toLowerCase(), s]))
  const lines: FitLine[] = []
  let score = 0
  for (const sk of need.skills) {
    const s = have.get(sk.toLowerCase())
    if (s) {
      score += s.depth === 'work' ? 2 : 1
      lines.push({ kind: 'overlap', text: `${sk}: ${depthText(s)}` })
    } else lines.push({ kind: 'gap', text: `${sk}: not mentioned` })
  }
  const want = LEVELS.indexOf(need.seniority)
  const has = LEVELS.indexOf(a.level)
  if (want >= 0 && has >= 0) {
    const diff = has - want
    if (diff >= 0) {
      score += 1
      lines.push({ kind: 'overlap', text: `Level: ${a.level}; the role asks for ${need.seniority.toLowerCase()}` })
    } else if (diff === -1) lines.push({ kind: 'check', text: `Level: ${a.level}, one step below ${need.seniority.toLowerCase()}; worth a conversation` })
    else lines.push({ kind: 'gap', text: `Level: ${a.level}; the role asks for ${need.seniority.toLowerCase()}` })
  }
  if (need.language && /finnish/i.test(need.language)) {
    if (a.finnish === 'fluent' || a.finnish === 'working level') {
      score += 1
      lines.push({ kind: 'overlap', text: `Finnish needed at work; the applicant's Finnish is ${a.finnish}` })
    } else lines.push({ kind: 'gap', text: `Finnish needed at work; the applicant's Finnish is ${a.finnish}` })
  } else if (need.language) lines.push({ kind: 'overlap', text: `${need.language}; the applicant works in English` })
  if (need.workplace === 'On site' && a.abroad) lines.push({ kind: 'check', text: `On site${need.where ? ` in ${need.where}` : ''}; the applicant lives in ${a.city} now` })
  else if (a.abroad) lines.push({ kind: 'check', text: `Lives in ${a.city}${need.workplace ? `; the role is ${need.workplace.toLowerCase()}` : ''}` })
  if (a.permit) lines.push({ kind: 'check', text: 'Would need work-permit support; Espoo\'s advisers help companies with this' })
  return { brief, need, score, lines }
}

/** Every role of one company against the applicant, closest first. */
export const fitCompany = (a: Applicant, brief: Brief): Fit[] =>
  reviewOf(brief)
    .needs.map((need) => fitNeed(a, brief, need))
    .sort((x, y) => y.score - x.score)

/** The closest role at each employer of the event, closest employers first, only where something overlaps. */
export const rank = (a: Applicant, employers: Invitee[]): Fit[] =>
  employers
    .map((e) => fitCompany(a, e.brief)[0])
    .filter((f): f is Fit => !!f && f.score > 0)
    .sort((x, y) => y.score - x.score || nameOf(x.brief).localeCompare(nameOf(y.brief)))

/** Whether an application is for this company to see: the applicant asked to meet it, or clearly fits one of its roles
 * (more than one incidental skill in common). */
export const concerns = (a: Applicant, brief: Brief) => a.wants.includes(brief.id) || (fitCompany(a, brief)[0]?.score ?? 0) >= 3
