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

export const clock = (iso?: string) =>
  iso ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''
