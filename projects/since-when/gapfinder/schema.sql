-- Gap finder schema, MariaDB 11.8. Every statement is idempotent: python -m gapfinder schema
-- All times are UTC (the loader and the API set time_zone = '+00:00').

-- A topic is a Wikidata item with an article in Finnish, Swedish and English.
CREATE TABLE IF NOT EXISTS topic (
  wikidata_id  VARCHAR(16) NOT NULL PRIMARY KEY,
  title_fi     VARCHAR(255) NOT NULL,
  title_sv     VARCHAR(255) NOT NULL,
  title_en     VARCHAR(255) NOT NULL,
  tier         TINYINT NOT NULL,      -- 0 politics and war, 1 other shared topics
  kind         VARCHAR(8) NULL,       -- list or office: editions differ in structure by design
  priority     INT NOT NULL           -- lower is embedded and aligned first
) CHARACTER SET utf8mb4;

-- One row per article and edition: the revision Wikipedia showed, versioned with Wikipedia's
-- real edit times, so FOR SYSTEM_TIME AS OF '2008-01-01' gives the article's size and revision
-- on that day. History is one snapshot per 1 January plus the latest revision.
CREATE TABLE IF NOT EXISTS article (
  lang         CHAR(2) NOT NULL,
  page_id      INT UNSIGNED NOT NULL,
  wikidata_id  VARCHAR(16) NOT NULL,
  title        VARCHAR(255) NOT NULL,
  rev_id       INT UNSIGNED NOT NULL,
  bytes        INT UNSIGNED NOT NULL,
  passages     SMALLINT UNSIGNED NOT NULL,
  refs         SMALLINT UNSIGNED NOT NULL,        -- <ref> tags in the wikitext
  quality      VARCHAR(8) NULL,                   -- featured, good, or NULL
  row_start    TIMESTAMP(6) GENERATED ALWAYS AS ROW START INVISIBLE,
  row_end      TIMESTAMP(6) GENERATED ALWAYS AS ROW END INVISIBLE,
  PERIOD FOR SYSTEM_TIME (row_start, row_end),
  PRIMARY KEY (lang, page_id),
  KEY topic_key (wikidata_id, lang),
  KEY start_key (lang, page_id, row_start)
) CHARACTER SET utf8mb4 WITH SYSTEM VERSIONING;

-- Passage text and its bge-m3 vector, stored once per distinct text. Most passages do not change
-- from one year to the next, so the history shares rows with the current text.
-- No vector index: alignment compares a topic's passages exactly (VEC_DISTANCE_COSINE).
CREATE TABLE IF NOT EXISTS passage (
  sha          BINARY(20) NOT NULL PRIMARY KEY,   -- SHA-1 of the text
  text         TEXT NOT NULL,
  words        SMALLINT UNSIGNED NOT NULL,
  priority     INT NOT NULL,                      -- the lowest priority of any chunk using it
  embedding    VECTOR(1024) NULL,                 -- NULL until embedded
  claimed_until DATETIME NULL,                    -- an embedding worker's lease
  KEY todo (embedding_done, priority),
  embedding_done BOOL AS (embedding IS NOT NULL) PERSISTENT
) CHARACTER SET utf8mb4;

-- One row per passage position in an article. Versioned with the real edit times of the
-- revisions it came from: chunk FOR SYSTEM_TIME AS OF @t is the article split into passages as
-- it stood at @t. id is stable for (lang, page_id, ord).
CREATE TABLE IF NOT EXISTS chunk (
  id           BIGINT UNSIGNED NOT NULL PRIMARY KEY,
  wikidata_id  VARCHAR(16) NOT NULL,
  lang         CHAR(2) NOT NULL,
  page_id      INT UNSIGNED NOT NULL,
  ord          SMALLINT UNSIGNED NOT NULL,        -- position in the article
  section      VARCHAR(512) NOT NULL,             -- heading path, '' for the lead
  chunk_no     SMALLINT UNSIGNED NOT NULL,        -- position in the section
  rev_id       INT UNSIGNED NOT NULL,
  sha          BINARY(20) NOT NULL,
  cites        JSON NOT NULL,                     -- [[offset in the text, citation]]
  row_start    TIMESTAMP(6) GENERATED ALWAYS AS ROW START INVISIBLE,
  row_end      TIMESTAMP(6) GENERATED ALWAYS AS ROW END INVISIBLE,
  PERIOD FOR SYSTEM_TIME (row_start, row_end),
  KEY topic_key (wikidata_id, lang, ord),
  KEY start_key (wikidata_id, row_start),
  KEY (sha)
) CHARACTER SET utf8mb4 WITH SYSTEM VERSIONING;

-- The current passages with a vector index, for search across all topics. A vector index on
-- chunk would hold every historical version, and AS OF searches through it lose recall.
CREATE TABLE IF NOT EXISTS chunk_now (
  id           BIGINT UNSIGNED NOT NULL PRIMARY KEY,
  wikidata_id  VARCHAR(16) NOT NULL,
  lang         CHAR(2) NOT NULL,
  section      VARCHAR(512) NOT NULL,
  embedding    VECTOR(1024) NOT NULL,
  VECTOR INDEX (embedding) M=16 DISTANCE=cosine
) CHARACTER SET utf8mb4;

-- Monthly user (not bot) page views since July 2015.
CREATE TABLE IF NOT EXISTS pageviews (
  lang         CHAR(2) NOT NULL,
  page_id      INT UNSIGNED NOT NULL,
  month        DATE NOT NULL,
  views        INT UNSIGNED NOT NULL,
  PRIMARY KEY (lang, page_id, month)
) CHARACTER SET utf8mb4;

-- Alignment result per topic, pair of editions and date: how much of rich_lang's text has a
-- close match in lang. as_of is 1 January of each year, or the load date for the current text.
CREATE TABLE IF NOT EXISTS coverage (
  wikidata_id  VARCHAR(16) NOT NULL,
  lang         CHAR(2) NOT NULL,
  rich_lang    CHAR(2) NOT NULL,
  as_of        DATE NOT NULL,
  is_current   BOOL NOT NULL,
  rich_passages SMALLINT UNSIGNED NOT NULL,
  covered      SMALLINT UNSIGNED NOT NULL,
  coverage     FLOAT NOT NULL,
  PRIMARY KEY (wikidata_id, lang, rich_lang, as_of),
  KEY (is_current, lang)
) CHARACTER SET utf8mb4;

-- The classifier's output (python -m differences classify), one row per difference in a pair.
-- build_findings turns these into findings.
CREATE TABLE IF NOT EXISTS difference (
  id           INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  pair_id      VARCHAR(128) NOT NULL,
  wikidata_id  VARCHAR(16) NOT NULL,
  as_of        DATE NOT NULL,
  a_lang       CHAR(2) NOT NULL,
  a_section    VARCHAR(512) NOT NULL,
  b_lang       CHAR(2) NOT NULL,
  b_section    VARCHAR(512) NOT NULL,
  type         ENUM('missing_fact','contradiction','framing','numbers') NOT NULL,
  missing_in   CHAR(2) NULL,
  quote_a      TEXT NOT NULL,
  quote_b      TEXT NOT NULL,
  a_rev        INT UNSIGNED NULL,                 -- revisions the quotes come from
  b_rev        INT UNSIGNED NULL,
  a_citation   TEXT NULL,                         -- the reference in or right after the quote
  b_citation   TEXT NULL,
  a_par_citation TEXT NULL,                       -- the reference ending the quote's paragraph
  b_par_citation TEXT NULL,
  summary      TEXT NOT NULL,
  terms        JSON NOT NULL,
  distance     FLOAT NULL,
  source       VARCHAR(16) NOT NULL,
  model        VARCHAR(64) NULL,
  KEY (pair_id),
  KEY (wikidata_id, as_of)
) CHARACTER SET utf8mb4;

-- One row per gap: a topic, the edition to fix, the edition it differs from, and the evidence.
-- Versioned: the history shows when a gap opened (first 1 January it held), when an editor
-- marked it reviewed, and when it closed.
CREATE TABLE IF NOT EXISTS finding (
  id           INT UNSIGNED NOT NULL PRIMARY KEY,
  wikidata_id  VARCHAR(16) NOT NULL,
  lang         CHAR(2) NOT NULL,                   -- edition to fix
  other_lang   CHAR(2) NOT NULL,
  type         ENUM('coverage','missing_fact','contradiction','framing','numbers') NOT NULL,
  section      VARCHAR(512) NOT NULL,
  other_section VARCHAR(512) NULL,
  quote        TEXT NULL,                          -- exact substring of lang's passage
  other_quote  TEXT NULL,                          -- exact substring of other_lang's passage
  summary      TEXT NOT NULL,
  terms        JSON NOT NULL DEFAULT '[]',
  distance     FLOAT NULL,
  share        FLOAT NULL,                         -- coverage: share of other_lang's words missing
  weight       FLOAT NOT NULL,                     -- how checkable: type, and whether it is cited
  rev_id       INT UNSIGNED NULL,                  -- revisions the evidence comes from
  other_rev_id INT UNSIGNED NULL,
  citation     TEXT NULL,                          -- reference behind lang's quote, if any
  other_citation TEXT NULL,                        -- reference behind other_lang's quote or passage
  paragraph_citation TEXT NULL,                    -- reference ending the paragraph of lang's quote
  other_paragraph_citation TEXT NULL,
  source       VARCHAR(16) NOT NULL,               -- align, llm, lexicon, both
  model        VARCHAR(64) NULL,
  -- An editor's outcome. A gap the alignment no longer sees ends the row's history instead.
  status       ENUM('open','edited','raised_on_talk','intentional_difference','not_a_difference')
               NOT NULL DEFAULT 'open',
  status_url   VARCHAR(512) NULL,                  -- the edit or the talk page section
  status_at    DATETIME(6) NULL,
  -- The edit that opened the finding is after opened_after, the last compared 1 January that did
  -- not show it (NULL: no earlier comparison), and no later than opened_at, the time of the later
  -- of the two revisions that first showed it. The same for closing. row_start and row_end are
  -- those two edit times.
  opened_at    DATE NOT NULL,
  opened_after DATE NULL,
  closed_at    DATE NULL,
  closed_after DATE NULL,
  history      BOOL NOT NULL DEFAULT FALSE,        -- dates come from compared 1 Januaries, not only today
  `key`        VARCHAR(255) NOT NULL,              -- identity across reloads
  row_start    TIMESTAMP(6) GENERATED ALWAYS AS ROW START INVISIBLE,
  row_end      TIMESTAMP(6) GENERATED ALWAYS AS ROW END INVISIBLE,
  PERIOD FOR SYSTEM_TIME (row_start, row_end),
  KEY topic_key (wikidata_id, lang),
  KEY (`key`)
) CHARACTER SET utf8mb4 WITH SYSTEM VERSIONING;

-- Articles whose article and chunk history holds every revision from `since` on, not only the
-- 1 January texts (python -m gapfinder.revisions load). build_findings dates their findings to
-- the edit that opened or closed them.
CREATE TABLE IF NOT EXISTS full_history (
  wikidata_id VARCHAR(16) NOT NULL,
  lang        CHAR(2) NOT NULL,
  since       DATETIME(6) NOT NULL,
  PRIMARY KEY (wikidata_id, lang)
) CHARACTER SET utf8mb4;

-- Columns added after the first load: no-ops on a table created above.
SET @@system_versioning_alter_history = KEEP;
ALTER TABLE finding ADD COLUMN IF NOT EXISTS opened_after DATE NULL AFTER opened_at,
                    ADD COLUMN IF NOT EXISTS closed_after DATE NULL AFTER closed_at,
                    ADD COLUMN IF NOT EXISTS history BOOL NOT NULL DEFAULT FALSE AFTER closed_after;
