// Marking and shortening article text. Nothing here rewrites a quote: text is only cut at sentence
// boundaries and wrapped in marks.

export interface Piece {
	text: string
	mark: null | 'quote' | 'term'
}

/**
 * Splits `text` into pieces, marking every occurrence of the quotes and of the terms. A term is one
 * of the API's loaded words in English ("fascist"); it is matched without case and runs to the end
 * of the word it starts, so it also marks "fascistisk". Terms win over the quote around them.
 */
export function pieces(text: string, quotes: string[] = [], terms: string[] = []): Piece[] {
	const marks: [number, number, 'quote' | 'term'][] = []
	const low = text.toLowerCase()
	const add = (needle: string, kind: 'quote' | 'term') => {
		const n = needle.toLowerCase()
		if (!n) return
		for (let i = low.indexOf(n); i >= 0; i = low.indexOf(n, i + n.length)) {
			let end = i + n.length
			if (kind === 'term') while (end < text.length && /[\p{L}\p{N}-]/u.test(text[end])) end++
			marks.push([i, end, kind])
		}
	}
	quotes.forEach((q) => add(q, 'quote'))
	terms.forEach((t) => add(t, 'term'))
	if (!marks.length) return [{ text, mark: null }]
	const cuts = [...new Set([0, text.length, ...marks.flatMap(([a, b]) => [a, b])])].sort((a, b) => a - b)
	const out: Piece[] = []
	for (let i = 0; i < cuts.length - 1; i++) {
		const [a, b] = [cuts[i], cuts[i + 1]]
		const hit = marks.filter(([s, e]) => s <= a && e >= b)
		const mark = !hit.length ? null : hit.some((m) => m[2] === 'term') ? 'term' : 'quote'
		const last = out[out.length - 1]
		if (last && last.mark === mark) last.text += text.slice(a, b)
		else out.push({ text: text.slice(a, b), mark })
	}
	return out
}

export const hasTerm = (text: string, terms: string[]) => terms.some((t) => t && text.toLowerCase().includes(t.toLowerCase()))

/**
 * The opening of a passage: its first sentence, and the sentences holding `quote` when the quote
 * sits further in. Returns one or two excerpts; a second one means sentences were left out between.
 */
export function opening(text: string, lang: string, quote?: string): string[] {
	const segmenter = new Intl.Segmenter(lang, { granularity: 'sentence' })
	const ss = [...segmenter.segment(text)].map((s) => ({ start: s.index, end: s.index + s.segment.length })).filter((s) => text.slice(s.start, s.end).trim())
	if (!ss.length) return []
	const cut = (a: number, b: number) => text.slice(ss[a].start, ss[b].end).trim()
	const at = quote ? text.indexOf(quote) : -1
	if (at < 0) return [cut(0, 0)]
	const first = ss.findIndex((s) => at < s.end)
	const found = ss.findIndex((s) => at + quote!.length <= s.end)
	const last = found < 0 ? ss.length - 1 : found
	return first <= 1 ? [cut(0, last)] : [cut(0, 0), cut(first, last)]
}
