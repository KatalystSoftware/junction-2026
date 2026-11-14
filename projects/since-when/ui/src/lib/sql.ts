// Colours a statement for reading. The text is escaped first and only spans are added.

const esc = (s: string) => s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!)
const KEYWORDS =
	/\b(SELECT|FROM|WHERE|JOIN|LEFT|ON|AND|OR|AS|OF|FOR|SYSTEM_TIME|ALL|GROUP BY|ORDER BY|LIMIT|OFFSET|HAVING|SET|SESSION|TIMESTAMP|WITH|OVER|PARTITION BY|COUNT|MIN|AVG|SUM|LEAST|ROUND|COALESCE|ROW_NUMBER|VEC_DISTANCE_COSINE|VEC_FromText|REGEXP|UNHEX|DESC|BY)\b/g

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

/**
 * The statement a preset will run, for showing before Run is clicked. The server holds the real
 * templates (gapfinder/api.py, gapfinder/align.py) and never takes SQL from the app; once a
 * statement has run, the panel shows the text the server reports instead of this one.
 */
export function preview(preset: string, v: Record<string, string>): string {
	if (preset === 'asof' && v.finding && v.finding !== '0')
		return `-- The words the page quotes for finding ${v.finding}, read from the tables as they are today
SELECT IF(k.outcome IN ('changed', 'new'),
          IF(k.lang = '${v.lang}', k.quote, k.other_quote),
          IF(f.lang = '${v.lang}', f.quote, f.other_quote))
INTO @quote
FROM (SELECT ${v.finding} AS id) AS x
LEFT JOIN finding AS f ON f.id = x.id
LEFT JOIN checked_finding AS k ON k.finding_id = x.id OR (x.id < 0 AND k.id = -x.id);

SET SESSION system_versioning_asof = '${v.date} 00:00:00';

SELECT @@system_versioning_asof AS session_as_of, c.rev_id, c.row_start, c.section, p.text
FROM chunk AS c
JOIN passage AS p ON p.sha = c.sha
WHERE c.wikidata_id = '${v.qid}' AND c.lang = '${v.lang}'
  AND INSTR(LOWER(REGEXP_REPLACE(p.text, '(*UCP)\\\\W+', ' ')),
            TRIM(LOWER(REGEXP_REPLACE(@quote, '(*UCP)\\\\W+', ' ')))) > 0
ORDER BY c.ord
LIMIT 1`
	if (preset === 'asof')
		return `SET SESSION system_versioning_asof = '${v.date} 00:00:00';

SELECT @@system_versioning_asof AS session_as_of, c.rev_id, c.row_start,
       LEFT(p.text, 320) AS text
FROM chunk AS c
JOIN passage AS p ON p.sha = c.sha
WHERE c.wikidata_id = '${v.qid}' AND c.lang = '${v.lang}' AND c.ord = 0`
	if (preset === 'history')
		return `SELECT c.rev_id, c.row_start, c.row_end, LEFT(p.text, 200) AS text
FROM chunk FOR SYSTEM_TIME ALL AS c
JOIN passage AS p ON p.sha = c.sha
WHERE c.wikidata_id = '${v.qid}' AND c.lang = '${v.lang}' AND c.ord = 0
ORDER BY c.row_start DESC`
	if (preset === 'check')
		return `SELECT id, finding_id, outcome, verdict, claim_lang, claim_quote, evidence_lang, evidence_quote, judge, search_sql
FROM checked_finding
WHERE finding_id = ${v.finding} OR (${v.finding} < 0 AND id = -${v.finding});

-- Then the statement in search_sql, as the check ran it: the other article
-- FOR SYSTEM_TIME AS OF the day, each sentence ranked by VEC_DISTANCE_COSINE to the
-- claim's vector, and its dates, numbers and names matched with REGEXP.`
	if (preset === 'nearest')
		return `WITH c AS (
  SELECT c.id, c.lang, c.ord, c.section, c.chunk_no, c.rev_id, p.embedding
  FROM chunk FOR SYSTEM_TIME AS OF TIMESTAMP '${v.date} 00:00:00' AS c
  JOIN passage AS p ON p.sha = c.sha
  WHERE c.wikidata_id = '${v.qid}' AND p.embedding IS NOT NULL
), d AS (
  SELECT x.id, x.lang, x.ord, y.lang AS other_lang, y.id AS other_id,
         VEC_DISTANCE_COSINE(x.embedding, y.embedding) AS distance,
         ROW_NUMBER() OVER (PARTITION BY x.id, y.lang
                            ORDER BY VEC_DISTANCE_COSINE(x.embedding, y.embedding)) AS rn
  FROM c AS x JOIN c AS y ON y.lang <> x.lang
  AND x.lang = '${v.a}' AND y.lang = '${v.b}'
)
SELECT id, lang, ord, other_lang, other_id, distance,
       CASE WHEN distance <= 0.3 THEN 'covered'
            WHEN distance <= 0.38 THEN 'partly' ELSE 'missing' END AS status
FROM d WHERE rn = 1
ORDER BY lang, other_lang, ord`
	return ''
}
