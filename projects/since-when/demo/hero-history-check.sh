#!/bin/sh
# Checks the three hero topics' revision history through a gap finder API (curl and jq):
#   sh projects/mariadb-wikipedia/demo/hero-history-check.sh http://127.0.0.1:8277
# 1. Every topic page, timeline and compare view answers; no compare row is "not compared yet"
#    (status pending) on three past dates, for every ordered pair of editions.
# 2. The four dated facts about the Lapua Movement's first sentences.
# Exit status 1 when a check fails.
api=${1:-http://127.0.0.1:8277}
fail=0

get() { curl -sf "$api$1" || { echo "FAIL  GET $1" >&2; fail=1; echo '{}'; }; }

for qid in Q1412941 Q736268 Q2457646; do
  get "/api/topics/$qid" | jq -r '"\(.wikidata_id // "?")  \(.titles.en // .title_en // "")  findings: \(.findings | length)"'
  for pair in fi:sv fi:en sv:fi sv:en en:fi en:sv; do
    a=${pair%:*} b=${pair#*:}
    get "/api/topics/$qid/timeline?lang=$a&rich_lang=$b" > /dev/null
    for day in 2008-06-15 2015-06-15 2026-10-24; do
      set -- $(get "/api/topics/$qid/compare?a=$a&b=$b&as_of=$day" |
        jq -r '"\(.rows | length) \([.rows[]? | select(.b)] | length) \([.rows[]? | select(.status == "pending")] | length) \(.complete)"')
      if [ "$1" = 0 ]; then note="no $a or $b article on that day"
      elif [ "$3" != 0 ] || [ "$4" != true ]; then note="FAIL: $3 not compared yet"; fail=1
      else note="ok"; fi
      echo "  $qid $day $a-$b: $1 passages, $2 with a counterpart, $3 not compared yet  $note"
    done
  done
done

# The first sentence of an edition of the Lapua Movement on a day, and whether it has the word.
first() {   # lang other day pattern yes|no ("fascis" matches fascist, Fascism, fascistisk)
  text=$(get "/api/topics/Q1412941/compare?a=$1&b=$2&as_of=$3" |
    jq -r '.rows[0] | "rev \(.a.rev_id): \(.a.text | split(". ")[0])"')
  if printf %s "$text" | grep -qi "$4"; then has=yes; else has=no; fi
  [ "$has" = "$5" ] && mark=ok || { mark=FAIL; fail=1; }
  echo "  $mark  $1 $3 '$4' $has (expected $5)  $text"
}
echo "Lapua Movement, first sentences"
first sv en 2026-10-22 fascis no
first sv en 2026-10-24 fascis yes
first en sv 2009-01-01 fascis yes
first en sv 2014-03-28 fascis no
first en sv 2020-12-07 fascis no
first en sv 2022-12-25 fascis yes
first en sv 2026-04-06 pro-Nazi no
first en sv 2026-04-08 pro-Nazi yes
exit $fail
