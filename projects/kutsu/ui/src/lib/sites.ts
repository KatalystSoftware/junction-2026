// Which site an address belongs to, worked out from the address alone: a person pastes any link and
// the right icon appears beside it, with no list to choose a network from. Nothing is fetched to do
// this. The icons are drawn here, in the app's own line weight, so showing a profile asks no other
// site for anything. Most outlines follow Feather (MIT); the rest are drawn for this page.

export type Site = {
  id: string
  /** what the site is called */
  name: string
  /** where the link goes */
  href: string
  /** the short text shown beside the icon: a handle or a bare domain, never the whole address */
  label: string
  /** whether the page says something about a person's work that is worth reading into a profile */
  read: boolean
}

const circle = (cx: number, cy: number, r: number) => `M${String(cx - r)} ${String(cy)}a${String(r)} ${String(r)} 0 1 0 ${String(2 * r)} 0a${String(r)} ${String(r)} 0 1 0 ${String(-2 * r)} 0`
/** Outlines on a 24 unit grid, stroked. */
export const ICONS: Record<string, string[]> = {
  globe: [circle(12, 12, 10), 'M2 12h20', 'M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z'],
  linkedin: ['M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z', 'M2 9h4v12H2z', circle(4, 4, 2)],
  github: [
    'M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22',
  ],
  gitlab: [
    'M22.65 14.39L12 22.13 1.35 14.39a.84.84 0 0 1-.3-.94l1.22-3.78 2.44-7.51A.42.42 0 0 1 4.82 2a.43.43 0 0 1 .58 0 .42.42 0 0 1 .11.18l2.44 7.49h8.1l2.44-7.51A.42.42 0 0 1 18.6 2a.43.43 0 0 1 .58 0 .42.42 0 0 1 .11.18l2.44 7.51L23 13.45a.84.84 0 0 1-.35.94z',
  ],
  instagram: ['M7 2h10a5 5 0 0 1 5 5v10a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5V7a5 5 0 0 1 5-5z', 'M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z', 'M17.5 6.5h.01'],
  youtube: [
    'M22.54 6.42a2.78 2.78 0 0 0-1.94-2C18.88 4 12 4 12 4s-6.88 0-8.6.46a2.78 2.78 0 0 0-1.94 2A29 29 0 0 0 1 11.75a29 29 0 0 0 .46 5.33A2.78 2.78 0 0 0 3.4 19c1.72.46 8.6.46 8.6.46s6.88 0 8.6-.46a2.78 2.78 0 0 0 1.94-2 29 29 0 0 0 .46-5.25 29 29 0 0 0-.46-5.33z',
    'M9.75 15.02l5.75-3.27-5.75-3.27v6.54z',
  ],
  dribbble: [circle(12, 12, 10), 'M8.56 2.75c4.37 6.03 6.02 9.42 8.03 17.72m2.54-15.38c-3.72 4.35-8.94 5.66-16.88 5.85m19.5 1.9c-3.5-.93-6.63-.82-8.94 0-2.58.92-5.01 2.86-7.44 6.32'],
  behance: ['M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z', 'M3 9h18', 'M9 21V9'],
  scholar: ['M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z', 'M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z'],
  pdf: ['M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z', 'M14 2v6h6', 'M16 13H8', 'M16 17H8', 'M10 9H8'],
  threads: [circle(12, 12, 4), 'M16 8v5a3 3 0 0 0 6 0v-1a10 10 0 1 0-3.92 7.94'],
  x: ['M4 4l16 16', 'M20 4L4 20'],
  bluesky: [
    'M12 10.8C10.4 7.9 7.9 5.4 5.6 4.9c-1.2-.2-1.9.5-1.8 1.9l.5 3.6c.2 1.6 1.6 2.3 3.2 2.2-2 .5-2.9 1.7-1.8 3.1 1.6 1.9 4.3 1.9 6.3-2.6 2 4.5 4.7 4.5 6.3 2.6 1.1-1.4.2-2.6-1.8-3.1 1.6.1 3-.6 3.2-2.2l.5-3.6c.1-1.4-.6-2.1-1.8-1.9-2.3.5-4.8 3-6.4 5.9z',
  ],
  mastodon: [
    'M5 9.5C5 6.4 7 4.5 10 4.5h4c3 0 5 1.9 5 5v3.3c0 3-2 4.7-5 4.7h-3.5c.2 1.3 1.5 2 3.5 2-3.8.8-7-.2-8.3-2.5C5.200 16 5 14.5 5 13z',
    'M8.500 13.5V10c0-1.100.8-1.800 1.800-1.800s1.700.7 1.700 1.800v1.500m0-1.500c0-1.100.7-1.800 1.700-1.800s1.800.7 1.800 1.800v3.500',
  ],
  orcid: [circle(12, 12, 10), 'M8.500 9.500v7', 'M8.500 7h.01', 'M12 8.500h2.200a3.800 3.800 0 0 1 0 7.500H12z'],
  kaggle: ['M8 4v16', 'M8 14.500L16 6', 'M11.200 11.800L16.500 20'],
  stackoverflow: ['M5 14v6h14v-6', 'M8 17h8', 'M8.300 13.200l7.800 1.600', 'M9.400 9.500l7.100 3.400', 'M11.800 6l5.700 5.200'],
}

type Rule = { id: string; name: string; host: RegExp; read: boolean; label?: (path: string[], host: string) => string }
const first = (path: string[]) => path[0] ?? ''
const handle = (path: string[]) => `@${first(path).replace(/^@/, '')}`
// in order: the first rule whose host matches names the site
const RULES: Rule[] = [
  { id: 'linkedin', name: 'LinkedIn', host: /(^|\.)linkedin\.com$/, read: false, label: (p) => p[1] ?? first(p) },
  { id: 'github', name: 'GitHub', host: /^github\.com$/, read: true, label: first },
  { id: 'gitlab', name: 'GitLab', host: /^gitlab\.com$/, read: true, label: first },
  { id: 'behance', name: 'Behance', host: /^behance\.net$/, read: true, label: first },
  { id: 'dribbble', name: 'Dribbble', host: /^dribbble\.com$/, read: true, label: first },
  { id: 'scholar', name: 'Google Scholar', host: /^scholar\.google\./, read: true, label: () => 'Google Scholar' },
  { id: 'orcid', name: 'ORCID', host: /^orcid\.org$/, read: true, label: first },
  { id: 'kaggle', name: 'Kaggle', host: /^kaggle\.com$/, read: true, label: first },
  { id: 'stackoverflow', name: 'Stack Overflow', host: /^stackoverflow\.com$/, read: true, label: (p) => p[2] ?? 'Stack Overflow' },
  { id: 'x', name: 'X', host: /^(x|twitter)\.com$/, read: false, label: handle },
  { id: 'instagram', name: 'Instagram', host: /^instagram\.com$/, read: false, label: handle },
  { id: 'bluesky', name: 'Bluesky', host: /^bsky\.app$/, read: false, label: (p) => p[1] ?? first(p) },
  { id: 'threads', name: 'Threads', host: /^threads\.(net|com)$/, read: false, label: handle },
  { id: 'youtube', name: 'YouTube', host: /^(youtube\.com|youtu\.be)$/, read: false, label: (p) => first(p) || 'YouTube' },
  { id: 'mastodon', name: 'Mastodon', host: /(mastodon|mstdn|fosstodon|hachyderm|infosec\.exchange|\.social$)/, read: false, label: (p, host) => `${handle(p)}@${host}` },
]

/** The site an address belongs to, or nothing when what was typed is not an address. */
export function siteOf(raw: string): Site | undefined {
  let text = raw.trim()
  if (!text || /\s/.test(text)) return undefined
  // a handle pasted by itself: name.bsky.social is Bluesky, @name@host is Mastodon; a bare @name could be anywhere
  const mastodon = /^@?([\w.-]+)@([\w-]+(?:\.[\w-]+)+)$/.exec(text)
  if (mastodon) return { id: 'mastodon', name: 'Mastodon', href: `https://${mastodon[2] ?? ''}/@${mastodon[1] ?? ''}`, label: `@${mastodon[1] ?? ''}@${mastodon[2] ?? ''}`, read: false }
  text = text.replace(/^@/, '')
  if (/^[\w-]+\.bsky\.social$/i.test(text)) text = `bsky.app/profile/${text}`
  let url: URL
  try {
    url = new URL(/^https?:\/\//i.test(text) ? text : `https://${text}`)
  } catch {
    return undefined
  }
  const host = url.hostname.replace(/^www\./, '').toLowerCase()
  if (!/^[a-z0-9-]+(\.[a-z0-9-]+)+$/.test(host)) return undefined
  const path = url.pathname.split('/').filter(Boolean)
  const href = `https://${host}${url.pathname.replace(/\/$/, '')}${url.search}`
  if (/\.pdf$/i.test(url.pathname)) return { id: 'pdf', name: 'A PDF', href, label: path.at(-1) ?? host, read: true }
  const rule = RULES.find((r) => r.host.test(host))
  if (rule) return { id: rule.id, name: rule.name, href, label: rule.label?.(path, host) || host, read: rule.read }
  return { id: 'globe', name: 'A web page', href, label: host, read: true }
}
