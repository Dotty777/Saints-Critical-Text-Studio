-- ============================================================================
-- THE SAINTS CONCORDANCE — ZERO-BLOAT TRILINGUAL MORPHEME & ROOT SCHEMA (v2.0)
-- Target: Saints-Critical-Text-Studio & Saints.Bible (7-Division, 70-Book Canon)
-- Languages: Hebrew ('heb'), Biblical Aramaic ('arc'), Greek ('grc'),
--            Latin ('lat'), and Saints English ('eng')
--
-- Core Design Principle:
--   Store irreducible etymological roots + reusable morpheme recipes + 1-byte
--   contextual sense offsets ("beginning" / "start" / "headwater") instead of
--   duplicating inflected surface words across ~3.6M trilingual tokens.
--
-- Studio Invariants Enforced (per AGENTS.md):
--   1. Coexists cleanly with studio.db tables (witnesses, chapters, verses, meta).
--   2. License quarantine guard: QUARANTINED_NC, DISREGARDED_*,DBG_LICENSED_NO_BULK_EXPORT,
--      and apparatus_only editions can never be flagged is_active_prod = 1.
--   3. Collision-free 32-bit anchor_verse_id across all 70 books, Psalms 1–151,
--      Psalm 119:1–176, and lettered sub-verses (e.g., Prov 24:22a–e, Esth A–F).
--   4. Exact orthography preserved in interned surface_forms (BINARY collation,
--      raw NFD Hebrew ketiv/qere & cantillation order never NFC-collapsed),
--      while live Saints.Bible exports ship pure root/morpheme/sense IDs.
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ============================================================================
-- LAYER 1: 70-BOOK CANON, EDITION & VERSIFICATION REGISTRY
-- ============================================================================

-- Canonical 7-Division, 70-Book Saints.Bible structure (matches studio/catalog.py)
CREATE TABLE IF NOT EXISTS books_catalog (
    book_order      INTEGER PRIMARY KEY CHECK (book_order BETWEEN 1 AND 70),
    book_slug       TEXT UNIQUE NOT NULL, -- e.g., 'genesis', '1-maccabees', 'psalms', 'sirach'
    usfm_code       TEXT UNIQUE NOT NULL, -- e.g., 'GEN', '1MA', 'PSA', 'SIR', 'REV'
    title           TEXT NOT NULL,
    division_id     TEXT NOT NULL CHECK (division_id IN (
                        '01_Law', '02_Judgement', '03_Wisdom', '04_Providence',
                        '05_Salvation', '06_Discipleship', '07_Glory'
                    )),
    testament       TEXT NOT NULL CHECK (testament IN ('OT', 'NT')),
    chapter_count   INTEGER NOT NULL CHECK (chapter_count BETWEEN 1 AND 151),
    has_heb         INTEGER NOT NULL DEFAULT 1 CHECK (has_heb IN (0, 1)),
    has_grc         INTEGER NOT NULL DEFAULT 1 CHECK (has_grc IN (0, 1)),
    has_lat         INTEGER NOT NULL DEFAULT 1 CHECK (has_lat IN (0, 1))
);

-- Critical, voting, and apparatus editions (DBG / witness hot-swap ready)
CREATE TABLE IF NOT EXISTS editions (
    edition_id      INTEGER PRIMARY KEY,
    code            TEXT UNIQUE NOT NULL, -- e.g., 'SAINTS_HEB', 'SAINTS_GRC', 'SAINTS_LAT', 'MAM', 'WLC', 'SWETE_CSV'
    lang            TEXT NOT NULL CHECK (lang IN ('heb', 'arc', 'grc', 'lat', 'eng')),
    role            TEXT NOT NULL DEFAULT 'voting_witness' CHECK (role IN (
                        'saints_critical', 'voting_witness', 'apparatus_only', 'reference_only'
                    )),
    title           TEXT NOT NULL,
    publisher       TEXT,
    license_mode    TEXT NOT NULL CHECK (license_mode IN (
                        'SAINTS_OPEN_MIT', 'OPEN_PD_CC0', 'OPEN_CC_BY', 'OPEN_GPL3',
                        'DBG_LICENSED_NO_BULK_EXPORT', 'QUARANTINED_NC', 'DISREGARDED'
                    )),
    witness_id      TEXT,                 -- Optional link to studio.db witnesses(id)
    is_active_prod  INTEGER NOT NULL DEFAULT 0 CHECK (is_active_prod IN (0, 1))
);

-- Guard Trigger (AGENTS.md Invariants #3 & #17):
-- Quarantined, non-commercial, no-bulk-export, disregarded, and apparatus-only
-- editions may never be compiled into the live Saints.Bible production bundle.
CREATE TRIGGER IF NOT EXISTS trg_guard_prod_edition_license
BEFORE INSERT ON editions
WHEN NEW.is_active_prod = 1
  AND (
      NEW.license_mode IN ('DBG_LICENSED_NO_BULK_EXPORT', 'QUARANTINED_NC', 'DISREGARDED')
      OR NEW.role = 'apparatus_only'
  )
BEGIN
    SELECT RAISE(ABORT, 'Gatekeeper violation: non-open or apparatus-only edition cannot be marked is_active_prod=1');
END;

CREATE TRIGGER IF NOT EXISTS trg_guard_prod_edition_license_upd
BEFORE UPDATE OF is_active_prod, license_mode, role ON editions
WHEN NEW.is_active_prod = 1
  AND (
      NEW.license_mode IN ('DBG_LICENSED_NO_BULK_EXPORT', 'QUARANTINED_NC', 'DISREGARDED')
      OR NEW.role = 'apparatus_only'
  )
BEGIN
    SELECT RAISE(ABORT, 'Gatekeeper violation: non-open or apparatus-only edition cannot be marked is_active_prod=1');
END;

-- Collision-free 32-bit verse anchor across all 70 books, Psalms 1–151, Ps 119:176,
-- and lettered sub-verses (Prov 24:22a–e, Esther Greek A–F, Daniel additions):
--   anchor_verse_id = (book_order * 10000000) + (chapter * 10000) + (verse * 10) + subverse
--   Max value = 701,511,769 (fits signed 32-bit integer; zero overlap between Ps 101+ and Prov 1+)
CREATE TABLE IF NOT EXISTS versification_anchors (
    anchor_verse_id INTEGER PRIMARY KEY CHECK (anchor_verse_id BETWEEN 10000000 AND 709999999),
    book_order      INTEGER NOT NULL REFERENCES books_catalog(book_order),
    chapter         INTEGER NOT NULL CHECK (chapter BETWEEN 0 AND 151),
    verse           INTEGER NOT NULL CHECK (verse BETWEEN 0 AND 200),
    subverse        INTEGER NOT NULL DEFAULT 0 CHECK (subverse BETWEEN 0 AND 9), -- 0='', 1='a', 2='b'...
    saints_ref      TEXT UNIQUE NOT NULL, -- e.g., 'Gen.1.1', 'Gen.2.10', 'Psa.101.1', 'Pro.24.22a'
    heb_ref         TEXT,                 -- Masoretic (MAM / WLC) reference where extant/differing
    grc_ref         TEXT,                 -- Septuagint (Swete / Brenton) or GNT reference
    lat_ref         TEXT,                 -- Clementine / Amiatinus Vulgate reference
    CHECK (anchor_verse_id = (book_order * 10000000) + (chapter * 10000) + (verse * 10) + subverse),
    UNIQUE(book_order, chapter, verse, subverse)
);

-- ============================================================================
-- LAYER 2: ZERO-BLOAT MORPHEME, ROOT & COMPOSITIONAL STEM GRAPH
-- ============================================================================

-- Irreducible etymological roots (~4,200–4,800 rows across Heb/Arc/Grc/Lat).
-- homograph_no cleanly separates identically spelled distinct roots
-- (e.g., Heb ח-ל-ל I 'pierce/profane' vs. ח-ל-ל II 'begin/start').
CREATE TABLE IF NOT EXISTS core_roots (
    root_id         INTEGER PRIMARY KEY,
    lang            TEXT NOT NULL CHECK (lang IN ('heb', 'arc', 'grc', 'lat')),
    root_key        TEXT NOT NULL,        -- e.g., 'ר-א-שׁ', 'ἀρχ-', 'cap-', 'prim-'
    homograph_no    INTEGER NOT NULL DEFAULT 1 CHECK (homograph_no >= 1),
    translit        TEXT,                 -- Compact ASCII key: 'r-a-sh', 'arch', 'cap', 'prim'
    core_idea       TEXT NOT NULL,        -- Physical/concrete root image: 'head / topmost / origin point'
    UNIQUE(lang, root_key, homograph_no)
);

-- Reusable atomic morphemes (~250–350 rows across all 5 languages, including English
-- inflectional deltas so 'beginning'/'beginnings' & 'headwater'/'headwaters' never bloat).
CREATE TABLE IF NOT EXISTS morpheme_catalog (
    morph_id        INTEGER PRIMARY KEY,
    lang            TEXT NOT NULL CHECK (lang IN ('heb', 'arc', 'grc', 'lat', 'eng')),
    morph_slot      TEXT NOT NULL CHECK (morph_slot IN (
                        'proclitic',      -- Heb בְּ־, וְ־, הַ־, לְ־, מִ־
                        'preverb',        -- Grc ἐκ-, ἀπο-, συν-, κατα-; Lat in-, prae-, con-, re-
                        'stem_pattern',   -- Heb binyanim (Qal, Piel, Hiphil) & mishkalim; Grc reduplication
                        'deriv_suffix',   -- Heb -îṯ, -ôn; Grc -σις, -μα, -της; Lat -ium, -tio, -tor; Eng -ing, -er
                        'inflection',     -- OSHB / Robinson / Latin case-number-tense-voice-mood / Eng SG, PL, PAST
                        'enclitic_suffix' -- Heb pronominal suffixes (-וֹ, -הֶם); Grc τε; Lat -que, -ne, -ve
                    )),
    morph_code      TEXT NOT NULL,        -- Compact deterministic code, e.g., 'P:b', 'D:it', 'N-DSF', 'ENG:PL'
    affix_form      TEXT,                 -- Display morpheme, e.g., 'בְּ־', '-ִית', 'ἀπο-', '-ium', '-s'
    grammatical_fn  TEXT NOT NULL,        -- Concise gloss/rule: 'in / at / by', 'abstract / prime-state', 'plural'
    UNIQUE(lang, morph_code)
);

-- Interned multi-affix combinations (~600–800 attested combinations across the whole Bible).
-- Allows stacked prefixes + pronominal/enclitic suffixes (e.g., וּ + בְּ + [stem] + ־הֶם,
-- or συν + ἐκ + [stem]) to be referenced on any token by ONE 2-byte integer (bundle_id = 0 = bare).
CREATE TABLE IF NOT EXISTS affix_bundles (
    bundle_id       INTEGER PRIMARY KEY,
    lang            TEXT NOT NULL CHECK (lang IN ('heb', 'arc', 'grc', 'lat', 'eng')),
    bundle_code     TEXT NOT NULL,        -- Canonical chain signature, e.g., 'NONE', 'P:w+P:b|E:3mp', 'PV:apo'
    UNIQUE(lang, bundle_code)
);

CREATE TABLE IF NOT EXISTS affix_bundle_items (
    bundle_id       INTEGER NOT NULL REFERENCES affix_bundles(bundle_id) ON DELETE CASCADE,
    seq_no          INTEGER NOT NULL CHECK (seq_no BETWEEN 1 AND 8),
    morph_id        INTEGER NOT NULL REFERENCES morpheme_catalog(morph_id),
    PRIMARY KEY (bundle_id, seq_no)
) WITHOUT ROWID;

-- Compositional lexical stems built from roots + morpheme operations instead of prose duplication.
-- Supports single-root derivatives (רֵאשִׁית = ר-א-שׁ + -îṯ; ἀπαρχή = ἀπο- + ἀρχ-)
-- and two-root compounds (principium = prim- + cap- + -ium; οἰκονόμος = οἶκ- + νεμ-).
CREATE TABLE IF NOT EXISTS lexical_stems (
    stem_id                 INTEGER PRIMARY KEY,
    lang                    TEXT NOT NULL CHECK (lang IN ('heb', 'arc', 'grc', 'lat')),
    root_id                 INTEGER NOT NULL REFERENCES core_roots(root_id) ON UPDATE CASCADE,
    secondary_root_id       INTEGER REFERENCES core_roots(root_id) ON UPDATE CASCADE,
    affix_bundle_id         INTEGER REFERENCES affix_bundles(bundle_id),          -- Preverbs / derivational prefixes
    stem_pattern_morph_id   INTEGER REFERENCES morpheme_catalog(morph_id),        -- Binyan / vowel-grade / redup
    deriv_suffix_morph_id   INTEGER REFERENCES morpheme_catalog(morph_id),        -- Nominal/verbal stem formative
    canonical_stem          TEXT NOT NULL,        -- Citation stem/lemma: 'רֵאשִׁית', 'רֹאשׁ', 'ἀρχή', 'principium', 'caput'
    pos_tag                 TEXT NOT NULL CHECK (pos_tag IN (
                                'N', 'V', 'ADJ', 'ADV', 'PRON', 'PREP', 'CONJ', 'PART', 'NUM', 'INTERJ', 'PROPN'
                            )),
    ext_strongs             TEXT,                 -- Backward-compatible STEPBible TBESH/TBESG code ('H7225', 'H7218', 'G0746')
    structural_formula      TEXT,                 -- Compact human-readable formula: 'ר-א-שׁ + -îṯ', 'prim- + cap- + -ium'
    base_gloss              TEXT NOT NULL,
    UNIQUE(lang, canonical_stem, pos_tag, ext_strongs)
);

-- ============================================================================
-- LAYER 3: TRILINGUAL CONCEPT HUB & SAINTS SENSE DELTAS
--          ("Beginning / Start / Headwater" = 1 Base Word + Tiny Sense Offsets)
-- ============================================================================

-- Unifies Hebrew, Greek, and Latin stems into one core concept + one English base anchor,
-- wired directly to the 7 rainbow colours of Saints Word Studies & Verse Themes.
CREATE TABLE IF NOT EXISTS trilingual_concepts (
    concept_id      INTEGER PRIMARY KEY,
    concept_slug    TEXT UNIQUE NOT NULL, -- e.g., 'ORIGIN_HEAD_START'
    eng_base_word   TEXT NOT NULL,        -- Core English base word/anchor, e.g., 'head / origin'
    theme_colour    TEXT CHECK (theme_colour IS NULL OR theme_colour IN (
                        'red', 'orange', 'yellow', 'green', 'blue', 'indigo', 'violet'
                    )),
    summary_note    TEXT NOT NULL         -- Stored ONCE per trilingual family; never repeated per verse
);

-- Contextual usage offsets under a single concept.
-- Example under 'ORIGIN_HEAD_START':
--   offset 1 -> base_word='beginning'  (temporal/cosmic origin: Gen 1:1; John 1:1)
--   offset 2 -> base_word='start'      (actional/inaugural onset: Hos 1:2; Mark 1:1)
--   offset 3 -> base_word='headwater'  (hydrological source-head: Gen 2:10; + ENG:PL -> 'headwaters')
--   offset 4 -> base_word='firstfruit' (foremost offering portion: Exod 23:19; Rom 8:23)
--   offset 5 -> base_word='head'       (anatomical crown / capstone: Gen 3:15; Ps 118:22)
--   offset 6 -> base_word='chief'      (governing leader / ruler: Exod 6:14; Eph 1:21)
CREATE TABLE IF NOT EXISTS saints_senses (
    sense_id                INTEGER PRIMARY KEY,
    concept_id              INTEGER NOT NULL REFERENCES trilingual_concepts(concept_id) ON DELETE CASCADE ON UPDATE CASCADE,
    sense_offset            INTEGER NOT NULL CHECK (sense_offset BETWEEN 1 AND 64),
    base_word               TEXT NOT NULL,        -- Uninflected English base sense ('beginning', 'start', 'headwater')
    sense_role              TEXT NOT NULL,        -- Compact tag ('temporal_origin', 'actional_onset', 'spatial_source')
    usage_nuance            TEXT NOT NULL,        -- Concise Concordance distinction shown on tap
    theme_colour_override   TEXT CHECK (theme_colour_override IS NULL OR theme_colour_override IN (
                                'red', 'orange', 'yellow', 'green', 'blue', 'indigo', 'violet'
                            )),
    UNIQUE(concept_id, sense_offset),
    UNIQUE(sense_id, concept_id)          -- Enables composite FK validation from stem_concept_links
);

-- Many-to-many bridge linking Hebrew/Aramaic, Greek, and Latin stems to unified concepts.
CREATE TABLE IF NOT EXISTS stem_concept_links (
    stem_id             INTEGER NOT NULL REFERENCES lexical_stems(stem_id) ON DELETE CASCADE,
    concept_id          INTEGER NOT NULL REFERENCES trilingual_concepts(concept_id) ON DELETE CASCADE,
    default_sense_id    INTEGER NOT NULL,
    link_weight         REAL NOT NULL DEFAULT 1.0 CHECK (link_weight > 0.0 AND link_weight <= 1.0),
    PRIMARY KEY (stem_id, concept_id),
    FOREIGN KEY (default_sense_id, concept_id) REFERENCES saints_senses(sense_id, concept_id)
) WITHOUT ROWID;

-- ============================================================================
-- LAYER 4: DEDUPLICATED TOKEN STREAM, EDITION DELTAS & TRILINGUAL ALIGNMENT
-- ============================================================================

-- Interned unique surface orthography pool (for Studio collation & interlinear display).
-- Uses SQLite default BINARY collation so raw NFD Hebrew cantillation/pointing,
-- MAM ketiv/qere '(הוצא) הַיְצֵ֣א', and Greek accents are preserved byte-for-byte,
-- while avoiding 3.6M duplicate UTF-8 strings across token tables.
-- Note: Live Saints.Bible Concordance bundles do NOT need to ship this table!
CREATE TABLE IF NOT EXISTS surface_forms (
    form_id         INTEGER PRIMARY KEY,
    lang            TEXT NOT NULL CHECK (lang IN ('heb', 'arc', 'grc', 'lat', 'eng')),
    surface_text    TEXT NOT NULL,        -- Exact witness/critical orthography (never NFC-mangled)
    bare_lookup_key TEXT NOT NULL,        -- Stripped search key (unpointed consonants / unaccented lowercase)
    UNIQUE(lang, surface_text)
);

-- Immutable word-slot anchors across streams (stepped by 10: 10, 20, 30... so
-- apparatus insertions slot at 15 without renumbering existing IDs).
CREATE TABLE IF NOT EXISTS word_anchors (
    slot_id         INTEGER PRIMARY KEY,
    anchor_verse_id INTEGER NOT NULL REFERENCES versification_anchors(anchor_verse_id) ON DELETE CASCADE,
    lang_stream     TEXT NOT NULL CHECK (lang_stream IN ('heb_ot', 'grc_ot', 'grc_nt', 'lat_bible')),
    slot_seq        INTEGER NOT NULL CHECK (slot_seq > 0),
    ext_word_uid    TEXT,                 -- Optional OSHB / STEPBible / CNTR word UID
    UNIQUE(anchor_verse_id, lang_stream, slot_seq),
    UNIQUE(slot_id, anchor_verse_id, lang_stream)
);

-- Primary Saints Critical Text token stream (one compact integer row per word slot).
-- Every word is decomposed into: [affix_bundle_id] + [stem_id] + [infl_morph_id] -> [sense_id] + [eng_infl_morph_id].
CREATE TABLE IF NOT EXISTS stream_tokens (
    slot_id             INTEGER PRIMARY KEY REFERENCES word_anchors(slot_id) ON DELETE CASCADE,
    form_id             INTEGER NOT NULL REFERENCES surface_forms(form_id),
    affix_bundle_id     INTEGER NOT NULL DEFAULT 0 REFERENCES affix_bundles(bundle_id),
    stem_id             INTEGER NOT NULL REFERENCES lexical_stems(stem_id),
    infl_morph_id       INTEGER NOT NULL REFERENCES morpheme_catalog(morph_id),
    sense_id            INTEGER NOT NULL REFERENCES saints_senses(sense_id),
    eng_infl_morph_id   INTEGER REFERENCES morpheme_catalog(morph_id), -- e.g., ENG:PL turns 'headwater' -> 'headwaters'
    review_status       TEXT NOT NULL DEFAULT 'auto' CHECK (review_status IN (
                            'auto', 'ai_advisory', 'human_verified'
                        )),
    human_locked        INTEGER NOT NULL DEFAULT 0 CHECK (human_locked IN (0, 1))
) WITHOUT ROWID;

-- Guard Trigger (AGENTS.md Invariant #5 / #8):
-- Automated or AI-advisory passes may never overwrite a human-locked token's stem or sense
-- unless the update itself explicitly unlocks human_locked = 0.
CREATE TRIGGER IF NOT EXISTS trg_protect_human_locked_tokens
BEFORE UPDATE ON stream_tokens
WHEN OLD.human_locked = 1 AND NEW.human_locked = 1
  AND NEW.review_status != 'human_verified'
BEGIN
    SELECT RAISE(ABORT, 'Human lock active: automated/AI pass cannot overwrite locked Concordance token');
END;

-- Zero-Bloat Edition Deltas:
-- Secondary witnesses & licensed reference editions (WLC, Brenton, Amiatinus, DBG_*)
-- ONLY store rows where their reading, morphology, or stem differs from stream_tokens!
-- Cuts multi-edition database size by ~85%.
CREATE TABLE IF NOT EXISTS edition_token_deltas (
    edition_id          INTEGER NOT NULL REFERENCES editions(edition_id) ON DELETE CASCADE,
    slot_id             INTEGER NOT NULL REFERENCES word_anchors(slot_id) ON DELETE CASCADE,
    delta_kind          TEXT NOT NULL CHECK (delta_kind IN (
                            'orthographic', 'morph_only', 'lexical_variant', 'omission', 'addition'
                        )),
    form_id             INTEGER REFERENCES surface_forms(form_id),      -- NULL when delta_kind = 'omission'
    affix_bundle_id     INTEGER REFERENCES affix_bundles(bundle_id),
    stem_id             INTEGER REFERENCES lexical_stems(stem_id),
    infl_morph_id       INTEGER REFERENCES morpheme_catalog(morph_id),
    sense_id            INTEGER REFERENCES saints_senses(sense_id),
    PRIMARY KEY (edition_id, slot_id)
) WITHOUT ROWID;

-- Trilingual Alignment Units:
-- Connects the Hebrew, Greek, and Latin word slots that render the SAME phrase/word
-- inside a verse into one Saints English occurrence, while recording root divergences
-- when the Septuagint or Vulgate translates with a non-equivalent root.
CREATE TABLE IF NOT EXISTS trilingual_alignments (
    align_id            INTEGER PRIMARY KEY,
    anchor_verse_id     INTEGER NOT NULL REFERENCES versification_anchors(anchor_verse_id) ON DELETE CASCADE,
    unit_seq            INTEGER NOT NULL CHECK (unit_seq > 0),          -- 10, 20, 30... in Saints English reading order
    sense_id            INTEGER NOT NULL REFERENCES saints_senses(sense_id),
    eng_infl_morph_id   INTEGER REFERENCES morpheme_catalog(morph_id),  -- e.g., ENG:PL ('headwater' -> 'headwaters')
    eng_affix_bundle_id INTEGER REFERENCES affix_bundles(bundle_id),    -- e.g., leading 'in the ' / '-s' flags
    alignment_state     TEXT NOT NULL DEFAULT 'unified' CHECK (alignment_state IN (
                            'unified',           -- Heb, Grc & Lat use stems mapped to the same trilingual_concept
                            'lxx_divergent',     -- Greek LXX chooses a distinct concept/root from Hebrew MT
                            'lat_divergent',     -- Latin chooses a distinct concept/root
                            'three_way_split',   -- Each language uses a distinct root image
                            'grc_lat_only',      -- Deuterocanonical OT or Greek/Latin-only NT/additions
                            'heb_only'           -- Clauses absent in LXX/Old Greek
                        )),
    translation_note_ref TEXT,                   -- Optional anchor to Saints Word Study / research note
    UNIQUE(anchor_verse_id, unit_seq),
    UNIQUE(align_id, anchor_verse_id)
);

-- Binds each language's word slot(s) (e.g., Greek 'ἐν' + 'ἀρχῇ', Latin 'in' + 'principio',
-- Hebrew single-slot 'בְּרֵאשִׁית') to the shared trilingual_alignments unit.
CREATE TABLE IF NOT EXISTS trilingual_alignment_slots (
    align_id        INTEGER NOT NULL,
    anchor_verse_id INTEGER NOT NULL,
    lang_stream     TEXT NOT NULL CHECK (lang_stream IN ('heb_ot', 'grc_ot', 'grc_nt', 'lat_bible')),
    slot_id         INTEGER NOT NULL,
    is_head_stem    INTEGER NOT NULL DEFAULT 1 CHECK (is_head_stem IN (0, 1)), -- 1 = content root, 0 = auxiliary prep/article
    PRIMARY KEY (align_id, slot_id),
    FOREIGN KEY (align_id, anchor_verse_id) REFERENCES trilingual_alignments(align_id, anchor_verse_id) ON DELETE CASCADE,
    FOREIGN KEY (slot_id, anchor_verse_id, lang_stream) REFERENCES word_anchors(slot_id, anchor_verse_id, lang_stream) ON DELETE CASCADE
) WITHOUT ROWID;

-- ============================================================================
-- LAYER 5: SAINTS.BIBLE ZERO-BLOAT CONCORDANCE COMPILER & AUDIT TRAIL
-- ============================================================================

-- Pre-compiled Inverted Concordance Postings for Saints.Bible & saints-offline-staging.
-- Stores delta-varint packed anchor_verse_ids (BLOB, ~1.5–2 bytes per occurrence)
-- so the entire 70-book trilingual concordance ships in ~1.5–2.5 MB with ZERO surface-word bloat.
CREATE TABLE IF NOT EXISTS concordance_postings (
    target_kind     TEXT NOT NULL CHECK (target_kind IN ('concept', 'sense', 'root', 'stem')),
    target_id       INTEGER NOT NULL,
    hit_count       INTEGER NOT NULL CHECK (hit_count >= 0),
    verse_count     INTEGER NOT NULL CHECK (verse_count >= 0),
    delta_varint_blob BLOB NOT NULL,      -- Sorted ascending anchor_verse_id delta-varints
    sample_refs_csv TEXT,                 -- Top 5 canonical refs for instant preview ('Gen.1.1,Gen.2.10,...')
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (target_kind, target_id)
) WITHOUT ROWID;

-- Append-only changelog for human + multi-AI studio edits (feeds Saints.Bible Review Register)
CREATE TABLE IF NOT EXISTS studio_revisions (
    rev_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    target_table    TEXT NOT NULL,
    target_pk       TEXT NOT NULL,
    field_changed   TEXT NOT NULL,
    old_val         TEXT,
    new_val         TEXT,
    actor           TEXT NOT NULL,        -- e.g., 'human_editor', 'offline_philological', 'claude_advisory', 'openai_advisory', 'gemini_antigravity'
    review_mode     TEXT NOT NULL DEFAULT 'deterministic' CHECK (review_mode IN (
                        'human_locked', 'deterministic', 'ai_advisory'
                    )),
    rationale       TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ============================================================================
-- PERFORMANCE INDEXES (Covering Root, Strong's, Sense & Verse Lookups)
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_stems_root          ON lexical_stems(root_id);
CREATE INDEX IF NOT EXISTS idx_stems_sec_root      ON lexical_stems(secondary_root_id) WHERE secondary_root_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_stems_strongs       ON lexical_stems(ext_strongs) WHERE ext_strongs IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_senses_concept      ON saints_senses(concept_id, sense_offset);
CREATE INDEX IF NOT EXISTS idx_stem_links_concept  ON stem_concept_links(concept_id, stem_id);
CREATE INDEX IF NOT EXISTS idx_forms_bare_lookup   ON surface_forms(lang, bare_lookup_key);
CREATE INDEX IF NOT EXISTS idx_stream_tokens_stem  ON stream_tokens(stem_id, sense_id);
CREATE INDEX IF NOT EXISTS idx_stream_tokens_sense ON stream_tokens(sense_id);
CREATE INDEX IF NOT EXISTS idx_align_verse         ON trilingual_alignments(anchor_verse_id, unit_seq);
CREATE INDEX IF NOT EXISTS idx_align_sense         ON trilingual_alignments(sense_id, anchor_verse_id);

-- ============================================================================
-- PRODUCTION-SAFE VIEWS FOR SAINTS.BIBLE & SAINTS STUDY PLUGIN
-- ============================================================================

-- Compact Concordance Card View:
-- Shows how one unified concept connects Hebrew, Greek, and Latin roots/stems
-- to every contextual English sense ('beginning', 'start', 'headwater', ...) with zero prose duplication.
CREATE VIEW IF NOT EXISTS v_saints_concordance_cards AS
SELECT
    tc.concept_id,
    tc.concept_slug,
    tc.eng_base_word,
    COALESCE(ss.theme_colour_override, tc.theme_colour) AS effective_colour,
    ss.sense_id,
    ss.sense_offset,
    ss.base_word          AS saints_sense_word,
    ss.sense_role,
    ss.usage_nuance,
    tc.summary_note,
    (
        SELECT GROUP_CONCAT(
            cr.lang || ':' || cr.root_key
            || CASE WHEN cr.homograph_no > 1 THEN '[' || cr.homograph_no || ']' ELSE '' END
            || ' (' || ls.canonical_stem || ')',
            ' · '
        )
        FROM stem_concept_links scl
        JOIN lexical_stems ls ON ls.stem_id = scl.stem_id
        JOIN core_roots cr    ON cr.root_id = ls.root_id
        WHERE scl.concept_id = tc.concept_id
    ) AS trilingual_stems
FROM trilingual_concepts tc
JOIN saints_senses ss ON ss.concept_id = tc.concept_id;

-- Trilingual Aligned Occurrence View (Zero Surface-Word Dependency):
-- Reconstructs the exact English contextual usage (e.g., 'beginning' vs. 'headwaters')
-- alongside the underlying Hebrew, Greek, and Latin root + morpheme formulas at each verse.
CREATE VIEW IF NOT EXISTS v_saints_trilingual_occurrences AS
SELECT
    va.saints_ref,
    ta.anchor_verse_id,
    ta.unit_seq,
    tc.concept_slug,
    tc.eng_base_word,
    ss.sense_offset,
    CASE
        WHEN em.morph_code = 'ENG:PL' THEN ss.base_word || 's'
        ELSE ss.base_word
    END AS rendered_saints_word,
    ss.sense_role,
    ta.alignment_state,
    GROUP_CONCAT(
         CASE tas.is_head_stem
            WHEN 1 THEN tas.lang_stream || '='
                        || CASE WHEN st.affix_bundle_id > 0 THEN '(' || ab.bundle_code || '+)' ELSE '' END
                        || cr.root_key
                        || CASE WHEN cr.homograph_no > 1 THEN '[' || cr.homograph_no || ']' ELSE '' END
                        || COALESCE('{' || ls.structural_formula || '}', '')
                        || ':' || im.morph_code
            ELSE NULL
        END,
        ' | '
    ) AS trilingual_morpheme_trace
FROM trilingual_alignments ta
JOIN versification_anchors va      ON va.anchor_verse_id = ta.anchor_verse_id
JOIN saints_senses ss              ON ss.sense_id = ta.sense_id
JOIN trilingual_concepts tc        ON tc.concept_id = ss.concept_id
LEFT JOIN morpheme_catalog em      ON em.morph_id = ta.eng_infl_morph_id
LEFT JOIN trilingual_alignment_slots tas
                                   ON tas.align_id = ta.align_id
                                  AND tas.anchor_verse_id = ta.anchor_verse_id
LEFT JOIN stream_tokens st         ON st.slot_id = tas.slot_id
LEFT JOIN affix_bundles ab         ON ab.bundle_id = st.affix_bundle_id
LEFT JOIN lexical_stems ls         ON ls.stem_id = st.stem_id
LEFT JOIN core_roots cr            ON cr.root_id = ls.root_id
LEFT JOIN morpheme_catalog im      ON im.morph_id = st.infl_morph_id
GROUP BY ta.align_id;

-- ============================================================================
-- REFERENCE SEED SHOWCASE: "Beginning / Start / Headwater" (Idempotent)
-- Demonstrates one shared base root-family across Gen 1:1, Gen 2:10, Hos 1:2, Mark 1:1
-- ============================================================================

-- 1. Seed sample books from the 70-book Saints catalog
INSERT OR IGNORE INTO books_catalog (book_order, book_slug, usfm_code, title, division_id, testament, chapter_count, has_heb, has_grc, has_lat) VALUES
    (1,  'genesis', 'GEN', 'Genesis', '01_Law',        'OT', 50,  1, 1, 1),
    (21, 'psalms',  'PSA', 'Psalms',  '03_Wisdom',     'OT', 151, 1, 1, 1),
    (22, 'proverbs','PRO', 'Proverbs','03_Wisdom',     'OT', 31,  1, 1, 1),
    (32, 'hosea',   'HOS', 'Hosea',   '04_Providence', 'OT', 14,  1, 1, 1),
    (45, 'mark',    'MRK', 'Mark',    '05_Salvation',  'NT', 16,  0, 1, 1);

-- 2. Seed open Saints Critical Editions
INSERT OR IGNORE INTO editions (edition_id, code, lang, role, title, publisher, license_mode, is_active_prod) VALUES
    (1, 'SAINTS_HEB', 'heb', 'saints_critical', 'Saints Hebrew Critical Text', 'Saints.Bible', 'SAINTS_OPEN_MIT', 1),
    (2, 'SAINTS_GRC', 'grc', 'saints_critical', 'Saints Greek Critical Text',  'Saints.Bible', 'SAINTS_OPEN_MIT', 1),
    (3, 'SAINTS_LAT', 'lat', 'saints_critical', 'Saints Latin Critical Text',  'Saints.Bible', 'SAINTS_OPEN_MIT', 1);

-- 3. Seed collision-free versification anchors (note Ps 101:1 = 211010010 vs. Prov 1:1 = 220010010)
INSERT OR IGNORE INTO versification_anchors (anchor_verse_id, book_order, chapter, verse, subverse, saints_ref, heb_ref, grc_ref, lat_ref) VALUES
    (10010010,  1,  1,   1, 0, 'Gen.1.1',    'Gen.1.1',   'Gen.1.1',   'Gen.1.1'),
    (10020100,  1,  2,  10, 0, 'Gen.2.10',   'Gen.2.10',  'Gen.2.10',  'Gen.2.10'),
    (211010010, 21, 101, 1, 0, 'Psa.101.1',  'Psa.101.1', 'Psa.100.1', 'Psa.100.1'),
    (220010010, 22, 1,   1, 0, 'Pro.1.1',    'Pro.1.1',   'Pro.1.1',   'Pro.1.1'),
    (220240221, 22, 24, 22, 1, 'Pro.24.22a', NULL,        'Pro.24.22a','Pro.24.22a'),
    (320010020, 32, 1,   2, 0, 'Hos.1.2',    'Hos.1.2',   'Hos.1.2',   'Hos.1.2'),
    (450010010, 45, 1,   1, 0, 'Mrk.1.1',    NULL,        'Mrk.1.1',   'Mrk.1.1');

-- 4. Seed irreducible etymological roots
INSERT OR IGNORE INTO core_roots (root_id, lang, root_key, homograph_no, translit, core_idea) VALUES
    (1, 'heb', 'ר-א-שׁ', 1, 'r-a-sh', 'head / topmost point / origin'),
    (2, 'heb', 'ח-ל-ל', 1, 'ch-l-l', 'pierce / loosen / profane'),
    (3, 'heb', 'ח-ל-ל', 2, 'ch-l-l', 'open up / begin / start (Hiphil הֵחֵל)'),
    (4, 'grc', 'ἀρχ-',  1, 'arch',   'first-point / origin / lead'),
    (5, 'lat', 'cap-',  1, 'cap',    'head / take / grasp'),
    (6, 'lat', 'prim-', 1, 'prim',   'first / foremost'),
    (7, 'lat', 'i-',    1, 'i',      'go / enter (eo, ire)');

-- 5. Seed atomic morphemes (prefixes, derivational suffixes, inflections, English plural delta)
INSERT OR IGNORE INTO morpheme_catalog (morph_id, lang, morph_slot, morph_code, affix_form, grammatical_fn) VALUES
    (1,  'heb', 'proclitic',    'P:b',       'בְּ־',  'in / at / by'),
    (2,  'heb', 'proclitic',    'P:l',       'לְ־',   'to / into / for'),
    (3,  'heb', 'stem_pattern', 'B:Hiphil',  'הִקְטִיל','causative / inceptive stem'),
    (4,  'heb', 'deriv_suffix', 'D:it',      '-ִית',  'abstract / prime-state noun ending'),
    (5,  'heb', 'inflection',   'HNcfsa',    NULL,    'noun common fem. sg. absolute'),
    (6,  'heb', 'inflection',   'HNcmpa',    '-ִים',  'noun common masc. pl. absolute'),
    (7,  'heb', 'inflection',   'HNcmsc',    NULL,    'noun common masc. sg. construct'),
    (8,  'grc', 'preverb',      'PV:apo',    'ἀπο-',  'from / away / off'),
    (9,  'grc', 'deriv_suffix', 'D:e_f1',    '-ή',    '1st-declension state/action noun'),
    (10, 'grc', 'inflection',   'N-DSF',     '-ῇ',    'noun dative sg. feminine'),
    (11, 'grc', 'inflection',   'N-APF',     '-άς',   'noun accusative pl. feminine'),
    (12, 'grc', 'inflection',   'N-NSF',     '-ή',    'noun nominative sg. feminine'),
    (13, 'lat', 'preverb',      'PV:in',     'in-',   'in / into / upon'),
    (14, 'lat', 'deriv_suffix', 'D:ium',     '-ium',  'abstract neuter noun suffix'),
    (15, 'lat', 'inflection',   'L:N-AblSN', '-o',    'noun ablative sg. neuter'),
    (16, 'lat', 'inflection',   'L:N-AccPN', '-a',    'noun accusative pl. neuter'),
    (17, 'lat', 'inflection',   'L:N-NomSN', '-um',   'noun nominative sg. neuter'),
    (18, 'eng', 'inflection',   'ENG:SG',    NULL,    'singular base usage'),
    (19, 'eng', 'inflection',   'ENG:PL',    '-s',    'plural inflection of base sense');

-- 6. Seed affix bundles (0 = bare/none; 1 = Heb בְּ־; 2 = Grc ἀπο-; 3 = Lat in-)
INSERT OR IGNORE INTO affix_bundles (bundle_id, lang, bundle_code) VALUES
    (0, 'heb', 'NONE'),
    (1, 'heb', 'P:b'),
    (2, 'grc', 'PV:apo'),
    (3, 'lat', 'PV:in');

INSERT OR IGNORE INTO affix_bundle_items (bundle_id, seq_no, morph_id) VALUES
    (1, 1, 1),
    (2, 1, 8),
    (3, 1, 13);

-- 7. Seed compositional stems (root + morpheme recipe)
INSERT OR IGNORE INTO lexical_stems (
    stem_id, lang, root_id, secondary_root_id, affix_bundle_id,
    stem_pattern_morph_id, deriv_suffix_morph_id, canonical_stem, pos_tag,
    ext_strongs, structural_formula, base_gloss
) VALUES
    (1, 'heb', 1, NULL, NULL, NULL, 4,    'רֵאשִׁית',   'N', 'H7225', 'ר-א-שׁ + -îṯ',        'first-state / beginning / choicest'),
    (2, 'heb', 1, NULL, NULL, NULL, NULL, 'רֹאשׁ',      'N', 'H7218', 'ר-א-שׁ (bare)',       'head / top / river-head / chief'),
    (3, 'heb', 3, NULL, NULL, 3,    NULL, 'תְּחִלָּה',  'N', 'H8462', 'ח-ל-ל II + t-noun',   'opening / start'),
    (4, 'grc', 4, NULL, NULL, NULL, 9,    'ἀρχή',       'N', 'G0746', 'ἀρχ- + -ή',           'origin / beginning / headwater / rule'),
    (5, 'grc', 4, NULL, 2,    NULL, 9,    'ἀπαρχή',     'N', 'G0536', 'ἀπο- + ἀρχ- + -ή',    'firstfruits / fore-portion'),
    (6, 'lat', 5, 6,    NULL, NULL, 14,   'principium', 'N', NULL,    'prim- + cap- + -ium', 'first-taking / beginning / origin'),
    (7, 'lat', 5, NULL, NULL, NULL, NULL, 'caput',      'N', NULL,    'cap- (bare)',         'head / river-source / chief'),
    (8, 'lat', 7, NULL, 3,    NULL, 14,   'initium',    'N', NULL,    'in- + i- + -ium',     'entering-in / start');

-- 8. Seed ONE unified Trilingual Concept + contextual Saints Sense Offsets
INSERT OR IGNORE INTO trilingual_concepts (concept_id, concept_slug, eng_base_word, theme_colour, summary_note) VALUES
    (1, 'ORIGIN_HEAD_START', 'head / origin', 'indigo',
     'One shared root-architecture across Hebrew (ר-א-שׁ), Greek (ἀρχ-), and Latin (cap- / princip-): the head or foremost point from which creation, events, rivers, firstfruits, or authority proceed.');

INSERT OR IGNORE INTO saints_senses (sense_id, concept_id, sense_offset, base_word, sense_role, usage_nuance) VALUES
    (1, 1, 1, 'beginning',  'temporal_origin',  'Absolute or cosmic point of origin (Gen 1:1; John 1:1)'),
    (2, 1, 2, 'start',      'actional_onset',   'Inaugural onset of a word, ministry, or action (Hos 1:2; Mark 1:1)'),
    (3, 1, 3, 'headwater',  'spatial_source',   'Hydrological source-head where one river divides into branches (Gen 2:10)'),
    (4, 1, 4, 'firstfruit', 'choicest_portion', 'First and choicest portion offered to God (Exod 23:19; Rom 8:23)'),
    (5, 1, 5, 'head',       'anatomical_crown', 'Physical head, crown, or summit (Gen 3:15; Ps 118:22)'),
    (6, 1, 6, 'chief',      'ruling_rank',      'Foremost leader, magistrate, or ruler (Exod 6:14; Eph 1:21)');

INSERT OR IGNORE INTO stem_concept_links (stem_id, concept_id, default_sense_id, link_weight) VALUES
    (1, 1, 1, 1.0), -- רֵאשִׁית -> beginning (also used for firstfruit)
    (2, 1, 5, 1.0), -- רֹאשׁ    -> head (and headwater in Gen 2:10, chief in Exod 6:14)
    (3, 1, 2, 0.9), -- תְּחִלָּה -> start (Hos 1:2)
    (4, 1, 1, 1.0), -- ἀρχή     -> beginning / start / headwater / chief!
    (5, 1, 4, 1.0), -- ἀπαρχή   -> firstfruit
    (6, 1, 1, 1.0), -- principium -> beginning / start
    (7, 1, 5, 1.0), -- caput      -> head / headwater / chief
    (8, 1, 2, 0.9); -- initium    -> start (Mark 1:1)

-- 9. Seed Genesis 1:1 ('beginning'), Genesis 2:10 ('headwaters'), Hosea 1:2 & Mark 1:1 ('start')
INSERT OR IGNORE INTO surface_forms (form_id, lang, surface_text, bare_lookup_key) VALUES
    (1, 'heb', 'בְּרֵאשִׁית', 'בראשית'),
    (2, 'grc', 'ἀρχῇ',        'αρχη'),
    (3, 'lat', 'principio',   'principio'),
    (4, 'heb', 'רָאשִׁים',    'ראשים'),
    (5, 'grc', 'ἀρχάς',       'αρχας'),
    (6, 'lat', 'capita',      'capita'),
    (7, 'heb', 'תְּחִלַּת',   'תחלת'),
    (8, 'grc', 'Ἀρχὴ',        'αρχη'),
    (9, 'lat', 'Initium',     'initium'),
    (10,'lat', 'Principium',  'principium');

INSERT OR IGNORE INTO word_anchors (slot_id, anchor_verse_id, lang_stream, slot_seq, ext_word_uid) VALUES
    -- Gen 1:1 ('In [the] beginning')
    (1, 10010010,  'heb_ot',    10, '0100100101'),
    (2, 10010010,  'grc_ot',    20, NULL),
    (3, 10010010,  'lat_bible', 20, NULL),
    -- Gen 2:10 ('into four headwaters')
    (4, 10020100,  'heb_ot',    70, '0100201007'),
    (5, 10020100,  'grc_ot',    70, NULL),
    (6, 10020100,  'lat_bible', 70, NULL),
    -- Hos 1:2 ('Start of the word of the LORD')
    (7, 320010020, 'heb_ot',    10, '2800100201'),
    (8, 320010020, 'grc_ot',    10, NULL),
    (9, 320010020, 'lat_bible', 20, NULL),
    -- Mark 1:1 ('Start of the good news')
    (10, 450010010, 'grc_nt',    10, NULL),
    (11, 450010010, 'lat_bible', 10, NULL);

INSERT OR IGNORE INTO stream_tokens (slot_id, form_id, affix_bundle_id, stem_id, infl_morph_id, sense_id, eng_infl_morph_id, review_status, human_locked) VALUES
    -- Gen 1:1 -> Sense 1 ('beginning', singular)
    (1,  1, 1, 1, 5,  1, 18, 'human_verified', 1), -- בְּ + רֵאשִׁית
    (2,  2, 0, 4, 10, 1, 18, 'human_verified', 1), -- ἀρχῇ
    (3,  3, 0, 6, 15, 1, 18, 'human_verified', 1), -- principio
    -- Gen 2:10 -> Sense 3 ('headwater' + ENG:PL -> 'headwaters'!)
    (4,  4, 0, 2, 6,  3, 19, 'human_verified', 1), -- רָאשִׁים
    (5,  5, 0, 4, 11, 3, 19, 'human_verified', 1), -- ἀρχάς
    (6,  6, 0, 7, 16, 3, 19, 'human_verified', 1), -- capita
    -- Hos 1:2 -> Sense 2 ('start', singular)
    (7,  7, 0, 3, 7,  2, 18, 'human_verified', 1), -- תְּחִלַּת
    (8,  8, 0, 4, 12, 2, 18, 'human_verified', 1), -- Ἀρχὴ
    (9,  10, 0, 6, 17, 2, 18, 'human_verified', 1), -- Principium (Hos 1:2 Clementine Vulgate)
    -- Mark 1:1 -> Sense 2 ('start', singular; NT Greek + Latin)
    (10, 8, 0, 4, 12, 2, 18, 'human_verified', 1), -- Ἀρχὴ
    (11, 9, 0, 8, 17, 2, 18, 'human_verified', 1); -- Initium

INSERT OR IGNORE INTO trilingual_alignments (align_id, anchor_verse_id, unit_seq, sense_id, eng_infl_morph_id, alignment_state) VALUES
    (1, 10010010,  10, 1, 18, 'unified'),      -- Gen 1:1  -> 'beginning'
    (2, 10020100,  40, 3, 19, 'unified'),      -- Gen 2:10 -> 'headwaters'
    (3, 320010020, 10, 2, 18, 'unified'),      -- Hos 1:2  -> 'start'
    (4, 450010010, 10, 2, 18, 'grc_lat_only'); -- Mrk 1:1  -> 'start'

INSERT OR IGNORE INTO trilingual_alignment_slots (align_id, anchor_verse_id, lang_stream, slot_id, is_head_stem) VALUES
    (1, 10010010,  'heb_ot',    1,  1),
    (1, 10010010,  'grc_ot',    2,  1),
    (1, 10010010,  'lat_bible', 3,  1),
    (2, 10020100,  'heb_ot',    4,  1),
    (2, 10020100,  'grc_ot',    5,  1),
    (2, 10020100,  'lat_bible', 6,  1),
    (3, 320010020, 'heb_ot',    7,  1),
    (3, 320010020, 'grc_ot',    8,  1),
    (3, 320010020, 'lat_bible', 9,  1),
    (4, 450010010, 'grc_nt',    10, 1),
    (4, 450010010, 'lat_bible', 11, 1);
