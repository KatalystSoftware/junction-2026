// Colours a statement for reading. The text is escaped first and only spans are added.

const esc = (s: string) => s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!)
const KEYWORDS =
	/\b(SELECT|FROM|WHERE|JOIN|LEFT|ON|AND|OR|AS|OF|FOR|SYSTEM_TIME|ALL|GROUP BY|ORDER BY|LIMIT|OFFSET|HAVING|SET|SESSION|TIMESTAMP|WITH|OVER|PARTITION BY|COUNT|MIN|AVG|SUM|LEAST|ROUND|COALESCE|ROW_NUMBER|VEC_DISTANCE_COSINE|VEC_FromText|DESC|BY)\b/g

export function sqlHtml(query: string): string {
	return esc(query)
		.split('\n')
		.map((line) => {
			const i = line.indexOf('--')
			const code = i >= 0 ? line.slice(0, i) : line
			const comment = i >= 0 ? line.slice(i) : ''
			return code.replace(/(&#39;[^&]*?&#39;)/g, '<span class="st">$1</span>').replace(KEYWORDS, '<span class="kw">$1</span>') + (comment ? `<span class="cm">${comment}</span>` : '')
		})
		.join('\n')
}
