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

/** The fixed start of a LinkedIn profile's address, with or without scheme, country and www. */
const LINKEDIN = /^(https?:\/\/)?([a-z]{2,3}\.)?(www\.)?linkedin\.com\/(in\/)?/i
/** The username from a whole LinkedIn address, with or without scheme, www or a tail, or from the name itself. */
export const linkedinName = (raw: string) => raw.trim().replace(LINKEDIN, '').replace(/[/?#].*$/, '')
/** What is typed so far, as a LinkedIn address: 'whole' up to the username, 'starting' while it could still become one, or neither. */
export const linkedinTyped = (raw: string) => {
  const text = raw.trim().toLowerCase()
  if (/\/in\/$/.test(LINKEDIN.exec(text)?.[0] ?? '')) return 'whole'
  return text && ['https://www.', 'https://', 'http://www.', 'http://', 'www.', ''].some((s) => `${s}linkedin.com/in/`.startsWith(text)) ? 'starting' : ''
}
/** A web address once it is whole (pasted, or typed and the field left), without the scheme nobody should have to type. */
export const bare = (raw: string) =>
  raw
    .trim()
    .replace(/^https?:\/\//i, '')
    .replace(/^www\./i, '')
    .replace(/\/$/, '')
/** The domain, when what was typed is a web address ("https://www.nitor.com/en/careers" is "nitor.com"); otherwise the text as it is. */
export const asDomain = (raw: string) => /^(?:https?:\/\/)?(?:www\.)?((?:[a-z0-9-]+\.)+[a-z]{2,})(?:[/?#].*)?$/i.exec(raw.trim())?.[1]?.toLowerCase() ?? raw.trim()

export const clock = (iso?: string) =>
  iso ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }) : ''
