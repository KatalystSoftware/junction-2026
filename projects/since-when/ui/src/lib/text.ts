// Marking article text. Nothing here rewrites a quote: text is only wrapped in marks.

export interface Piece {
	text: string
	mark: null | 'quote' | 'term'
}

/**
 * Splits `text` into pieces, marking every occurrence of the quotes and of the terms. A term is one
 * of the API's loaded words in English ("fascist"); it is matched without case and runs to the end
 * of the word it starts, so it also marks "fascistisk". Terms win over the quote around them.
 */
export function pieces(text: string, quotes: string[] = [], terms: string[] = [], ranges: [number, number][] = []): Piece[] {
	const marks: [number, number, 'quote' | 'term'][] = ranges.map(([a, b]) => [a, b, 'term'])
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

/** The figures in a text, "12 000" and "12,600" each as one, with their digits as the value. */
export function figures(text: string): { start: number; end: number; value: string }[] {
	return [...text.matchAll(/\d+(?:[\u00a0\u202f ,.]\d{3}(?!\d))*/g)].map((m) => ({ start: m.index, end: m.index + m[0].length, value: m[0].replace(/\D/g, '') }))
}
