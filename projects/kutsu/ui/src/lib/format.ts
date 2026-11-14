export const host = (url: string | null) => {
  try {
    return new URL(url ?? '').hostname.replace(/^www\./, '')
  } catch {
    return ''
  }
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "2026-09" or "2026-09-14" as "Sep 2026" or "14 Sep 2026"; anything else as it is. */
export const when = (date: string) => {
  const [, y, m, d] = /^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?/.exec(date) ?? []
  if (!y) return date
  return [d && Number(d), m && MONTHS[Number(m) - 1], y].filter(Boolean).join(' ')
}

/** A need's practical terms in one line: level, language, place, and whether they hire from abroad. */
export const terms = (n: { seniority: string; language?: string | null; workplace?: string | null; where?: string | null; abroad?: boolean | null }) =>
  [
    n.seniority,
    n.language,
    [n.workplace, n.where].filter(Boolean).join(', '),
    n.abroad == null ? '' : n.abroad ? 'Hires from abroad' : 'Only people already in Finland',
  ].filter(Boolean)

/** How long ago a moment was, in the coarsest unit that is still true: "20 min ago", "3 h ago", "2 days ago". */
export const ago = (iso: string) => {
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000))
  if (minutes < 60) return `${String(minutes)} min ago`
  if (minutes < 60 * 24) return `${String(Math.round(minutes / 60))} h ago`
  return `${String(Math.round(minutes / 1440))} days ago`
}

export const clock = (iso?: string) =>
  iso ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }) : ''
