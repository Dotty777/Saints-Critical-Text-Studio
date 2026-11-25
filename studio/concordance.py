"""The Saints Concordance — schema, queries and curation API (Tab 5).

Every word of the Hebrew (+ Biblical Aramaic), Greek (LXX + NT) and Latin critical texts is filed by
lemma and root family under its Saints.Bible verse, so the website can ship lemma/root postings instead
of per-word data; seven curated colour hubs link words of the three languages that share a meaning.
The build itself lives in ``concordance_gold.py`` and ``lexica/`` (tagged editions, see AGENTS.md
invariant 18); this module keeps Gemini's 18 Nov 2026 schema, the posting codec and the Tab 5 queries.

Invariants (per AGENTS.md):
- Zero mandatory third-party dependencies (Python standard library only); offline; no network.
- Lemmas come from tagged, openly licensed editions; unresolved words stay untagged.
- One verse numbering (Saints.Bible) for all three languages.
- STEPBible TBESH/TBESG: columns 1-7 only ('Meaning' needs Online Bible permission).
"""

from __future__ import annotations

import base64
import csv
import gzip
import json
import os
from pathlib import Path
import re
import sqlite3
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .catalog import (
    BOOKS,
    BOOKS_BY_SLUG,
    BOOKS_BY_USFM,
    DATA_DIR,
    OUTPUT_ROOT,
    STUDIO_ROOT,
    BookSpec,
)

CONCORDANCE_PACK_DIR_NAME = "Saints-Concordance-Pack"
SAINTS_COLOURS = ("red", "orange", "yellow", "green", "blue", "indigo", "violet")
LANG_CODES = ("heb", "arc", "grc", "lat", "eng")

# Hebrew final-letter normalization for consonantal root extraction
_HEB_FINAL_MAP = str.maketrans({"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"})
_TO_FINAL_MAP = {"כ": "ך", "מ": "ם", "נ": "ן", "פ": "ף", "צ": "ץ"}

# ---------------------------------------------------------------------------
# SQLite DDL — 5-Layer Zero-Bloat Concordance Schema (Matches updated SQL v2.0)
# ---------------------------------------------------------------------------

CONCORDANCE_DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS books_catalog (
    book_order      INTEGER PRIMARY KEY CHECK (book_order BETWEEN 1 AND 70),
    book_slug       TEXT UNIQUE NOT NULL,
    usfm_code       TEXT UNIQUE NOT NULL,
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

CREATE TABLE IF NOT EXISTS editions (
    edition_id      INTEGER PRIMARY KEY,
    code            TEXT UNIQUE NOT NULL,
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
    witness_id      TEXT,
    is_active_prod  INTEGER NOT NULL DEFAULT 0 CHECK (is_active_prod IN (0, 1))
);

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

CREATE TABLE IF NOT EXISTS versification_anchors (
    anchor_verse_id INTEGER PRIMARY KEY CHECK (anchor_verse_id BETWEEN 10000000 AND 709999999),
    book_order      INTEGER NOT NULL REFERENCES books_catalog(book_order),
    chapter         INTEGER NOT NULL CHECK (chapter BETWEEN 0 AND 151),
    verse           INTEGER NOT NULL CHECK (verse BETWEEN 0 AND 200),
    subverse        INTEGER NOT NULL DEFAULT 0 CHECK (subverse BETWEEN 0 AND 9),
    saints_ref      TEXT UNIQUE NOT NULL,
    heb_ref         TEXT,
    grc_ref         TEXT,
    lat_ref         TEXT,
    CHECK (anchor_verse_id = (book_order * 10000000) + (chapter * 10000) + (verse * 10) + subverse),
    UNIQUE(book_order, chapter, verse, subverse)
);

CREATE TABLE IF NOT EXISTS core_roots (
    root_id         INTEGER PRIMARY KEY,
    lang            TEXT NOT NULL CHECK (lang IN ('heb', 'arc', 'grc', 'lat')),
    root_key        TEXT NOT NULL,
    homograph_no    INTEGER NOT NULL DEFAULT 1 CHECK (homograph_no >= 1),
    translit        TEXT,
    core_idea       TEXT NOT NULL,
    UNIQUE(lang, root_key, homograph_no)
);

CREATE TABLE IF NOT EXISTS morpheme_catalog (
    morph_id        INTEGER PRIMARY KEY,
    lang            TEXT NOT NULL CHECK (lang IN ('heb', 'arc', 'grc', 'lat', 'eng')),
    morph_slot      TEXT NOT NULL CHECK (morph_slot IN (
                        'proclitic', 'preverb', 'stem_pattern',
                        'deriv_suffix', 'inflection', 'enclitic_suffix'
                    )),
    morph_code      TEXT NOT NULL,
    affix_form      TEXT,
    grammatical_fn  TEXT NOT NULL,
    UNIQUE(lang, morph_code)
);

CREATE TABLE IF NOT EXISTS affix_bundles (
    bundle_id       INTEGER PRIMARY KEY,
    lang            TEXT NOT NULL CHECK (lang IN ('heb', 'arc', 'grc', 'lat', 'eng')),
    bundle_code     TEXT NOT NULL,
    UNIQUE(lang, bundle_code)
);

CREATE TABLE IF NOT EXISTS affix_bundle_items (
    bundle_id       INTEGER NOT NULL REFERENCES affix_bundles(bundle_id) ON DELETE CASCADE,
    seq_no          INTEGER NOT NULL CHECK (seq_no BETWEEN 1 AND 8),
    morph_id        INTEGER NOT NULL REFERENCES morpheme_catalog(morph_id),
    PRIMARY KEY (bundle_id, seq_no)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS lexical_stems (
    stem_id                 INTEGER PRIMARY KEY,
    lang                    TEXT NOT NULL CHECK (lang IN ('heb', 'arc', 'grc', 'lat')),
    root_id                 INTEGER NOT NULL REFERENCES core_roots(root_id) ON UPDATE CASCADE,
    secondary_root_id       INTEGER REFERENCES core_roots(root_id) ON UPDATE CASCADE,
    affix_bundle_id         INTEGER REFERENCES affix_bundles(bundle_id),
    stem_pattern_morph_id   INTEGER REFERENCES morpheme_catalog(morph_id),
    deriv_suffix_morph_id   INTEGER REFERENCES morpheme_catalog(morph_id),
    canonical_stem          TEXT NOT NULL,
    pos_tag                 TEXT NOT NULL CHECK (pos_tag IN (
                                'N', 'V', 'ADJ', 'ADV', 'PRON', 'PREP', 'CONJ', 'PART', 'NUM', 'INTERJ', 'PROPN'
                            )),
    ext_strongs             TEXT,
    structural_formula      TEXT,
    base_gloss              TEXT NOT NULL,
    UNIQUE(lang, canonical_stem, pos_tag, ext_strongs)
);

CREATE TABLE IF NOT EXISTS trilingual_concepts (
    concept_id      INTEGER PRIMARY KEY,
    concept_slug    TEXT UNIQUE NOT NULL,
    eng_base_word   TEXT NOT NULL,
    theme_colour    TEXT CHECK (theme_colour IS NULL OR theme_colour IN (
                        'red', 'orange', 'yellow', 'green', 'blue', 'indigo', 'violet'
                    )),
    summary_note    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS saints_senses (
    sense_id                INTEGER PRIMARY KEY,
    concept_id              INTEGER NOT NULL REFERENCES trilingual_concepts(concept_id) ON DELETE CASCADE ON UPDATE CASCADE,
    sense_offset            INTEGER NOT NULL CHECK (sense_offset BETWEEN 1 AND 64),
    base_word               TEXT NOT NULL,
    sense_role              TEXT NOT NULL,
    usage_nuance            TEXT NOT NULL,
    theme_colour_override   TEXT CHECK (theme_colour_override IS NULL OR theme_colour_override IN (
                                'red', 'orange', 'yellow', 'green', 'blue', 'indigo', 'violet'
                            )),
    UNIQUE(concept_id, sense_offset),
    UNIQUE(sense_id, concept_id)
);

CREATE TABLE IF NOT EXISTS stem_concept_links (
    stem_id             INTEGER NOT NULL REFERENCES lexical_stems(stem_id) ON DELETE CASCADE,
    concept_id          INTEGER NOT NULL REFERENCES trilingual_concepts(concept_id) ON DELETE CASCADE,
    default_sense_id    INTEGER NOT NULL,
    link_weight         REAL NOT NULL DEFAULT 1.0 CHECK (link_weight > 0.0 AND link_weight <= 1.0),
    PRIMARY KEY (stem_id, concept_id),
    FOREIGN KEY (default_sense_id, concept_id) REFERENCES saints_senses(sense_id, concept_id)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS surface_forms (
    form_id         INTEGER PRIMARY KEY,
    lang            TEXT NOT NULL CHECK (lang IN ('heb', 'arc', 'grc', 'lat', 'eng')),
    surface_text    TEXT NOT NULL,
    bare_lookup_key TEXT NOT NULL,
    UNIQUE(lang, surface_text)
);

CREATE TABLE IF NOT EXISTS word_anchors (
    slot_id         INTEGER PRIMARY KEY,
    anchor_verse_id INTEGER NOT NULL REFERENCES versification_anchors(anchor_verse_id) ON DELETE CASCADE,
    lang_stream     TEXT NOT NULL CHECK (lang_stream IN ('heb_ot', 'grc_ot', 'grc_nt', 'lat_bible')),
    slot_seq        INTEGER NOT NULL CHECK (slot_seq > 0),
    ext_word_uid    TEXT,
    UNIQUE(anchor_verse_id, lang_stream, slot_seq),
    UNIQUE(slot_id, anchor_verse_id, lang_stream)
);

CREATE TABLE IF NOT EXISTS stream_tokens (
    slot_id             INTEGER PRIMARY KEY REFERENCES word_anchors(slot_id) ON DELETE CASCADE,
    form_id             INTEGER NOT NULL REFERENCES surface_forms(form_id),
    affix_bundle_id     INTEGER NOT NULL DEFAULT 0 REFERENCES affix_bundles(bundle_id),
    stem_id             INTEGER NOT NULL REFERENCES lexical_stems(stem_id),
    infl_morph_id       INTEGER NOT NULL REFERENCES morpheme_catalog(morph_id),
    sense_id            INTEGER NOT NULL REFERENCES saints_senses(sense_id),
    eng_infl_morph_id   INTEGER REFERENCES morpheme_catalog(morph_id),
    review_status       TEXT NOT NULL DEFAULT 'auto' CHECK (review_status IN (
                            'auto', 'ai_advisory', 'human_verified'
                        )),
    human_locked        INTEGER NOT NULL DEFAULT 0 CHECK (human_locked IN (0, 1))
) WITHOUT ROWID;

CREATE TRIGGER IF NOT EXISTS trg_protect_human_locked_tokens
BEFORE UPDATE ON stream_tokens
WHEN OLD.human_locked = 1 AND NEW.human_locked = 1
  AND NEW.review_status != 'human_verified'
BEGIN
    SELECT RAISE(ABORT, 'Human lock active: automated/AI pass cannot overwrite locked Concordance token');
END;

CREATE TABLE IF NOT EXISTS edition_token_deltas (
    edition_id          INTEGER NOT NULL REFERENCES editions(edition_id) ON DELETE CASCADE,
    slot_id             INTEGER NOT NULL REFERENCES word_anchors(slot_id) ON DELETE CASCADE,
    delta_kind          TEXT NOT NULL CHECK (delta_kind IN (
                            'orthographic', 'morph_only', 'lexical_variant', 'omission', 'addition'
                        )),
    form_id             INTEGER REFERENCES surface_forms(form_id),
    affix_bundle_id     INTEGER REFERENCES affix_bundles(bundle_id),
    stem_id             INTEGER REFERENCES lexical_stems(stem_id),
    infl_morph_id       INTEGER REFERENCES morpheme_catalog(morph_id),
    sense_id            INTEGER REFERENCES saints_senses(sense_id),
    PRIMARY KEY (edition_id, slot_id)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS trilingual_alignments (
    align_id            INTEGER PRIMARY KEY,
    anchor_verse_id     INTEGER NOT NULL REFERENCES versification_anchors(anchor_verse_id) ON DELETE CASCADE,
    unit_seq            INTEGER NOT NULL CHECK (unit_seq > 0),
    sense_id            INTEGER NOT NULL REFERENCES saints_senses(sense_id),
    eng_infl_morph_id   INTEGER REFERENCES morpheme_catalog(morph_id),
    eng_affix_bundle_id INTEGER REFERENCES affix_bundles(bundle_id),
    alignment_state     TEXT NOT NULL DEFAULT 'unified' CHECK (alignment_state IN (
                            'unified', 'lxx_divergent', 'lat_divergent',
                            'three_way_split', 'grc_lat_only', 'heb_only'
                        )),
    translation_note_ref TEXT,
    UNIQUE(anchor_verse_id, unit_seq),
    UNIQUE(align_id, anchor_verse_id)
);

CREATE TABLE IF NOT EXISTS trilingual_alignment_slots (
    align_id        INTEGER NOT NULL,
    anchor_verse_id INTEGER NOT NULL,
    lang_stream     TEXT NOT NULL CHECK (lang_stream IN ('heb_ot', 'grc_ot', 'grc_nt', 'lat_bible')),
    slot_id         INTEGER NOT NULL,
    is_head_stem    INTEGER NOT NULL DEFAULT 1 CHECK (is_head_stem IN (0, 1)),
    PRIMARY KEY (align_id, slot_id),
    FOREIGN KEY (align_id, anchor_verse_id) REFERENCES trilingual_alignments(align_id, anchor_verse_id) ON DELETE CASCADE,
    FOREIGN KEY (slot_id, anchor_verse_id, lang_stream) REFERENCES word_anchors(slot_id, anchor_verse_id, lang_stream) ON DELETE CASCADE
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS concordance_postings (
    target_kind     TEXT NOT NULL CHECK (target_kind IN ('concept', 'sense', 'root', 'stem')),
    target_id       INTEGER NOT NULL,
    hit_count       INTEGER NOT NULL CHECK (hit_count >= 0),
    verse_count     INTEGER NOT NULL CHECK (verse_count >= 0),
    delta_varint_blob BLOB NOT NULL,
    sample_refs_csv TEXT,
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (target_kind, target_id)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS studio_revisions (
    rev_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    target_table    TEXT NOT NULL,
    target_pk       TEXT NOT NULL,
    field_changed   TEXT NOT NULL,
    old_val         TEXT,
    new_val         TEXT,
    actor           TEXT NOT NULL,
    review_mode     TEXT NOT NULL DEFAULT 'deterministic' CHECK (review_mode IN (
                        'human_locked', 'deterministic', 'ai_advisory'
                    )),
    rationale       TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_stems_root          ON lexical_stems(root_id);
CREATE INDEX IF NOT EXISTS idx_stems_sec_root      ON lexical_stems(secondary_root_id) WHERE secondary_root_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_stems_strongs       ON lexical_stems(ext_strongs) WHERE ext_strongs IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_stems_bare_lang     ON lexical_stems(lang, canonical_stem);
CREATE INDEX IF NOT EXISTS idx_senses_concept      ON saints_senses(concept_id, sense_offset);
CREATE INDEX IF NOT EXISTS idx_stem_links_concept  ON stem_concept_links(concept_id, stem_id);
CREATE INDEX IF NOT EXISTS idx_forms_bare_lookup   ON surface_forms(lang, bare_lookup_key);
CREATE INDEX IF NOT EXISTS idx_stream_tokens_stem  ON stream_tokens(stem_id, sense_id);
CREATE INDEX IF NOT EXISTS idx_stream_tokens_sense ON stream_tokens(sense_id);
CREATE INDEX IF NOT EXISTS idx_align_verse         ON trilingual_alignments(anchor_verse_id, unit_seq);
CREATE INDEX IF NOT EXISTS idx_align_sense         ON trilingual_alignments(sense_id, anchor_verse_id);

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
"""


# ---------------------------------------------------------------------------
# Collision-Free 32-Bit Anchor Verse ID & Delta-Varint Binary Codec
# ---------------------------------------------------------------------------

def make_anchor_verse_id(book_order: int, chapter: int, verse: int, subverse: int = 0) -> int:
    """Encode (book 1..70, ch 0..151, vs 0..200, sub 0..9) into a 32-bit integer."""
    if not (1 <= book_order <= 70 and 0 <= chapter <= 151 and 0 <= verse <= 200 and 0 <= subverse <= 9):
        raise ValueError(f"Out-of-range verse coordinates: book={book_order}, ch={chapter}, vs={verse}, sub={subverse}")
    return (book_order * 10_000_000) + (chapter * 10_000) + (verse * 10) + subverse


def parse_anchor_verse_id(anchor_verse_id: int) -> Tuple[int, int, int, int]:
    """Decode anchor_verse_id -> (book_order, chapter, verse, subverse)."""
    book_order, rem = divmod(int(anchor_verse_id), 10_000_000)
    chapter, rem = divmod(rem, 10_000)
    verse, subverse = divmod(rem, 10)
    return book_order, chapter, verse, subverse


def format_saints_ref(book: BookSpec, chapter: int, verse: int, subverse: int = 0) -> str:
    sub_suffix = chr(ord("a") + subverse - 1) if 1 <= subverse <= 9 else ""
    code = book.usfm_code.title()
    # Keep canonical readable abbreviations matching STEPBible/Saints refs
    pretty_map = {
        "1Sa": "1Sa", "2Sa": "2Sa", "1Ki": "1Ki", "2Ki": "2Ki",
        "1Ch": "1Ch", "2Ch": "2Ch", "1Ma": "1Ma", "2Ma": "2Ma",
        "1Co": "1Co", "2Co": "2Co", "1Th": "1Th", "2Th": "2Th",
        "1Ti": "1Ti", "2Ti": "2Ti", "1Pe": "1Pe", "2Pe": "2Pe",
        "1Jn": "1Jn", "2Jn": "2Jn", "3Jn": "3Jn",
    }
    prefix = pretty_map.get(code, code)
    return f"{prefix}.{chapter}.{verse}{sub_suffix}"


def encode_delta_varints(ids: Iterable[int]) -> bytes:
    """Pack sorted unique positive integers into unsigned LEB128 delta-varint bytes (~1.5–2 B/hit)."""
    unique_sorted = sorted({int(x) for x in ids if int(x) > 0})
    out = bytearray()
    prev = 0
    for val in unique_sorted:
        delta = val - prev
        prev = val
        while True:
            byte = delta & 0x7F
            delta >>= 7
            if delta:
                out.append(byte | 0x80)
            else:
                out.append(byte)
                break
    return bytes(out)


def decode_delta_varints(blob: bytes) -> List[int]:
    """Unpack unsigned LEB128 delta-varint bytes back into sorted anchor_verse_ids."""
    if not blob:
        return []
    out: List[int] = []
    acc = 0
    shift = 0
    prev = 0
    for b in blob:
        acc |= (b & 0x7F) << shift
        if b & 0x80:
            shift += 7
        else:
            val = prev + acc
            out.append(val)
            prev = val
            acc = 0
            shift = 0
    return out


# ---------------------------------------------------------------------------
# English & Trilingual Morphological Helpers
# ---------------------------------------------------------------------------

_IRREGULAR_ENG_PLURALS = {
    "life": "lives",
    "leaf": "leaves",
    "man": "men",
    "woman": "women",
    "child": "children",
    "foot": "feet",
    "tooth": "teeth",
    "person": "people",
}


def render_english_sense(base_word: str, morph_code: Optional[str] = None) -> str:
    """Render an uninflected English base sense with its compact inflection delta."""
    w = base_word.strip()
    if not w or not morph_code or morph_code == "ENG:SG":
        return w
    low = w.lower()
    if morph_code == "ENG:PL":
        if low in _IRREGULAR_ENG_PLURALS:
            irr = _IRREGULAR_ENG_PLURALS[low]
            return irr.capitalize() if w[0].isupper() else irr
        if len(w) > 2 and low.endswith("y") and low[-2] not in "aeiou":
            return w[:-1] + "ies"
        if low.endswith(("s", "x", "z", "ch", "sh")):
            return w + "es"
        return w + "s"
    if morph_code == "ENG:ING":
        if len(w) > 2 and low.endswith("e") and not low.endswith("ee"):
            return w[:-1] + "ing"
        return w + "ing"
    if morph_code == "ENG:ED":
        if low.endswith("e"):
            return w + "d"
        if len(w) > 2 and low.endswith("y") and low[-2] not in "aeiou":
            return w[:-1] + "ied"
        return w + "ed"
    return w


def strip_hebrew_marks(text: str, normalize_finals: bool = False) -> str:
    """Keep Hebrew consonants only (preserving NFD surface_text separately in surface_forms)."""
    # Remove cantillation, niqqud, maqqef, paseq, sof pasuq, ketiv parens
    cleaned = "".join(ch for ch in text if "\u05D0" <= ch <= "\u05EA")
    if normalize_finals:
        cleaned = cleaned.translate(_HEB_FINAL_MAP)
    return cleaned


def format_hebrew_root_key(consonants: str) -> str:
    """Format normalized consonants 'ראש' -> 'ר-א-שׁ' or 'קדש' -> 'ק-ד-ש'."""
    c = consonants.translate(_HEB_FINAL_MAP)
    if not c:
        return consonants
    chars = list(c)
    if chars[-1] in _TO_FINAL_MAP:
        chars[-1] = _TO_FINAL_MAP[chars[-1]]
    return "-".join(chars)


def strip_greek_marks(text: str) -> str:
    """Lowercase unaccented Greek bare lookup key."""
    nfd = unicodedata.normalize("NFD", text)
    bare = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    bare = unicodedata.normalize("NFC", bare).lower()
    bare = re.sub(r"[^\u0370-\u03ff\u1f00-\u1fff]", "", bare)
    if bare.endswith("ς"):
        return bare
    return bare


def strip_latin_marks(text: str) -> str:
    """Lowercase ASCII-normalized Latin lookup key (æ->ae, œ->oe, j->i, v->v)."""
    t = text.lower().replace("æ", "ae").replace("œ", "oe")
    nfd = unicodedata.normalize("NFD", t)
    bare = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z]", "", bare)


# ---------------------------------------------------------------------------
# Built-In Foundational Morphemes, Vulgate Roots & Flagship Concept Showcase
# ---------------------------------------------------------------------------

CORE_MORPHEME_SEEDS: List[Tuple[str, str, str, Optional[str], str]] = [
    # Hebrew proclitics, binyanim, nominal suffixes, inflections, pronominal suffixes
    ("heb", "proclitic", "P:b", "בְּ־", "in / at / by"),
    ("heb", "proclitic", "P:l", "לְ־", "to / into / for"),
    ("heb", "proclitic", "P:k", "כְּ־", "like / as / according to"),
    ("heb", "proclitic", "P:m", "מִ־", "from / out of"),
    ("heb", "proclitic", "P:w", "וְ־", "and / then"),
    ("heb", "proclitic", "P:h", "הַ־", "the (definite article)"),
    ("heb", "proclitic", "P:sh", "שֶׁ־", "who / which / that"),
    ("heb", "stem_pattern", "B:Qal", "קָטַל", "simple active/stative stem"),
    ("heb", "stem_pattern", "B:Niphal", "נִקְטַל", "passive / reflexive / middle stem"),
    ("heb", "stem_pattern", "B:Piel", "קִטֵּל", "intensive / factitive stem"),
    ("heb", "stem_pattern", "B:Pual", "קֻטַּל", "intensive passive stem"),
    ("heb", "stem_pattern", "B:Hiphil", "הִקְטִיל", "causative / inceptive stem"),
    ("heb", "stem_pattern", "B:Hophal", "הׇקְטַל", "causative passive stem"),
    ("heb", "stem_pattern", "B:Hithpael", "הִתְקַטֵּל", "reflexive / reciprocal stem"),
    ("heb", "stem_pattern", "M:miqtal", "מִקְטָל", "place / instrument / abstract noun preformative מ־"),
    ("heb", "stem_pattern", "M:taqtul", "תַּקְטוּל", "action / state noun preformative ת־"),
    ("heb", "deriv_suffix", "D:it", "-ִית", "abstract / prime-state noun ending"),
    ("heb", "deriv_suffix", "D:on", "-וֹן", "abstract / diminutive / adjectival -ôn"),
    ("heb", "deriv_suffix", "D:ut", "-וּת", "abstract quality -ûṯ"),
    ("heb", "deriv_suffix", "D:ah", "-ָה", "feminine / verbal-noun -āh"),
    ("heb", "inflection", "HNcfsa", None, "noun common fem. sg. absolute"),
    ("heb", "inflection", "HNcfsc", None, "noun common fem. sg. construct"),
    ("heb", "inflection", "HNcmsa", None, "noun common masc. sg. absolute"),
    ("heb", "inflection", "HNcmsc", None, "noun common masc. sg. construct"),
    ("heb", "inflection", "HNcmpa", "-ִים", "noun common masc. pl. absolute"),
    ("heb", "inflection", "HNcfpa", "-וֹת", "noun common fem. pl. absolute"),
    ("heb", "inflection", "HVqp3ms", None, "verb Qal perfect 3rd masc. sg."),
    ("heb", "inflection", "H:WORD", None, "attested Hebrew corpus form"),
    ("heb", "enclitic_suffix", "E:3ms", "-וֹ", "his / its (3ms pronominal suffix)"),
    ("heb", "enclitic_suffix", "E:3mp", "-הֶם", "their (3mp pronominal suffix)"),
    # Aramaic
    ("arc", "deriv_suffix", "D:a_emph", "-ָא", "Aramaic emphatic / definite state"),
    ("arc", "inflection", "A:WORD", None, "attested Biblical Aramaic form"),
    # Greek preverbs, derivational suffixes, inflections
    ("grc", "preverb", "PV:apo", "ἀπο-", "from / away / off"),
    ("grc", "preverb", "PV:ek", "ἐκ-", "out of / forth"),
    ("grc", "preverb", "PV:eis", "εἰσ-", "into / toward"),
    ("grc", "preverb", "PV:en", "ἐν-", "in / within"),
    ("grc", "preverb", "PV:syn", "συν-", "with / together"),
    ("grc", "preverb", "PV:kata", "κατα-", "down / according to / thoroughly"),
    ("grc", "preverb", "PV:ana", "ἀνα-", "up / again"),
    ("grc", "preverb", "PV:dia", "δια-", "through / across"),
    ("grc", "preverb", "PV:para", "παρα-", "beside / alongside"),
    ("grc", "preverb", "PV:peri", "περι-", "around / concerning"),
    ("grc", "preverb", "PV:pro", "προ-", "before / forth"),
    ("grc", "preverb", "PV:pros", "προσ-", "toward / to"),
    ("grc", "preverb", "PV:hyper", "ὑπερ-", "over / above / beyond"),
    ("grc", "preverb", "PV:hypo", "ὑπο-", "under / beneath"),
    ("grc", "preverb", "PV:anti", "ἀντι-", "over against / instead of"),
    ("grc", "preverb", "PV:meta", "μετα-", "with / after / change"),
    ("grc", "preverb", "PV:epi", "ἐπι-", "upon / over / at"),
    ("grc", "preverb", "PV:a_priv", "ἀ-", "alpha-privative (un- / without)"),
    ("grc", "deriv_suffix", "D:e_f1", "-ή", "1st-declension state/action noun"),
    ("grc", "deriv_suffix", "D:sis", "-σις", "verbal action/process noun"),
    ("grc", "deriv_suffix", "D:ma", "-μα", "result/object of action noun"),
    ("grc", "deriv_suffix", "D:tes", "-της", "agent / quality noun"),
    ("grc", "deriv_suffix", "D:ia", "-ία", "abstract state/quality noun"),
    ("grc", "deriv_suffix", "D:os", "-ος", "2nd-declension thematic stem"),
    ("grc", "inflection", "N-DSF", "-ῇ", "noun dative sg. feminine"),
    ("grc", "inflection", "N-APF", "-άς", "noun accusative pl. feminine"),
    ("grc", "inflection", "N-NSF", "-ή", "noun nominative sg. feminine"),
    ("grc", "inflection", "N-NSM", "-ος", "noun nominative sg. masculine"),
    ("grc", "inflection", "N-NSN", "-ον", "noun nominative sg. neuter"),
    ("grc", "inflection", "G:WORD", None, "attested Greek corpus form"),
    # Latin preverbs, derivational suffixes, inflections, enclitics
    ("lat", "preverb", "PV:in", "in-", "in / into / upon (or privative un-)"),
    ("lat", "preverb", "PV:ad", "ad-", "to / toward"),
    ("lat", "preverb", "PV:con", "con-", "with / together / completely"),
    ("lat", "preverb", "PV:de", "de-", "down / from / concerning"),
    ("lat", "preverb", "PV:ex", "ex-", "out of / forth"),
    ("lat", "preverb", "PV:prae", "prae-", "before / ahead / in front"),
    ("lat", "preverb", "PV:pro", "pro-", "forth / before / on behalf of"),
    ("lat", "preverb", "PV:re", "re-", "back / again"),
    ("lat", "preverb", "PV:sub", "sub-", "under / up from beneath"),
    ("lat", "preverb", "PV:per", "per-", "through / thoroughly"),
    ("lat", "preverb", "PV:trans", "trans-", "across / beyond"),
    ("lat", "preverb", "PV:inter", "inter-", "between / among"),
    ("lat", "preverb", "PV:ob", "ob-", "toward / against"),
    ("lat", "deriv_suffix", "D:ium", "-ium", "abstract / collective neuter noun"),
    ("lat", "deriv_suffix", "D:tio", "-tio", "verbal action/process noun"),
    ("lat", "deriv_suffix", "D:tor", "-tor", "agent noun"),
    ("lat", "deriv_suffix", "D:tas", "-tas", "abstract quality noun"),
    ("lat", "deriv_suffix", "D:mentum", "-mentum", "instrument / result noun"),
    ("lat", "inflection", "L:N-AblSN", "-o", "noun ablative sg. neuter"),
    ("lat", "inflection", "L:N-AccPN", "-a", "noun accusative pl. neuter"),
    ("lat", "inflection", "L:N-NomSN", "-um", "noun nominative sg. neuter"),
    ("lat", "inflection", "L:N-NomSM", "-us", "noun nominative sg. masculine"),
    ("lat", "inflection", "L:N-NomSF", "-a", "noun nominative sg. feminine"),
    ("lat", "inflection", "L:WORD", None, "attested Latin corpus form"),
    ("lat", "enclitic_suffix", "E:que", "-que", "and (enclitic conjunction)"),
    ("lat", "enclitic_suffix", "E:ne", "-ne", "interrogative enclitic"),
    ("lat", "enclitic_suffix", "E:ve", "-ve", "or (enclitic)"),
    # English inflectional deltas (zero duplicate dictionary entries!)
    ("eng", "inflection", "ENG:SG", None, "singular / base form"),
    ("eng", "inflection", "ENG:PL", "-s", "plural inflection of base sense"),
    ("eng", "inflection", "ENG:ED", "-ed", "past / participial inflection"),
    ("eng", "inflection", "ENG:ING", "-ing", "progressive / gerundive inflection"),
]


# (The first build's 29-root hand-written LATIN_CORE_LIBRARY was removed on 18 Nov 2026: it merged
# caput 'head' with capio 'take' under one 'cap-' root, filed dilectio under am- 'love', and covered
# 1.8 % of Vulgate tokens.  Latin lemmas and families now come from studio/lexica/latin.py, built on
# Lewis & Short.)


def init_concordance_schema(conn: sqlite3.Connection) -> None:
    """Idempotently initialize all 5 Concordance layers, 70 books, and flagship showcase."""
    conn.executescript(CONCORDANCE_DDL)

    # 1. Seed all 70 canonical Saints books from studio.catalog.BOOKS
    conn.executemany(
        """
        INSERT OR IGNORE INTO books_catalog (
            book_order, book_slug, usfm_code, title, division_id,
            testament, chapter_count, has_heb, has_grc, has_lat
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                b.order,
                b.slug,
                b.usfm_code,
                b.title,
                b.division,
                b.testament,
                b.chapters,
                1 if (b.has_hebrew or b.slug == "sirach") else 0,
                1 if b.has_greek else 0,
                1 if b.has_latin else 0,
            )
            for b in BOOKS
        ],
    )

    # 2. Seed open Saints Critical Editions
    conn.executemany(
        """
        INSERT OR IGNORE INTO editions (edition_id, code, lang, role, title, publisher, license_mode, is_active_prod)
        VALUES (?, ?, ?, 'saints_critical', ?, 'Saints.Bible', 'SAINTS_OPEN_MIT', 1)
        """,
        [
            (1, "SAINTS_HEB", "heb", "Saints Hebrew Critical Text"),
            (2, "SAINTS_GRC", "grc", "Saints Greek Critical Text"),
            (3, "SAINTS_LAT", "lat", "Saints Latin Critical Text"),
        ],
    )

    # 3. Seed foundational morpheme catalog & bare bundle (bundle_id = 0)
    conn.executemany(
        """
        INSERT OR IGNORE INTO morpheme_catalog (lang, morph_slot, morph_code, affix_form, grammatical_fn)
        VALUES (?, ?, ?, ?, ?)
        """,
        CORE_MORPHEME_SEEDS,
    )
    conn.execute("INSERT OR IGNORE INTO affix_bundles (bundle_id, lang, bundle_code) VALUES (0, 'heb', 'NONE')")

    # Only run the flagship showcase seed once so user edits are never overwritten
    already_seeded = conn.execute("SELECT COUNT(*) FROM trilingual_concepts").fetchone()[0]
    if not already_seeded:
        _seed_flagship_trilingual_showcase(conn)

    # Without this index every DELETE/lookup of alignment slots by slot_id scanned the whole table,
    # which made a whole-Bible index take 47 minutes (34 s with it).
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_align_slots_slot ON trilingual_alignment_slots(slot_id, anchor_verse_id, lang_stream)"
    )
    from .concordance_gold import ensure_gold_schema

    ensure_gold_schema(conn)
    _SCHEMA_READY.add(_db_identity(conn))


_SCHEMA_READY: set = set()


def _db_identity(conn: sqlite3.Connection) -> str:
    try:
        row = conn.execute("PRAGMA database_list").fetchone()
        return str(row[2] or ":memory:") + f"#{id(conn) if not row[2] else ''}"
    except sqlite3.Error:
        return f":memory:#{id(conn)}"


def _ensure_schema_ready(conn: sqlite3.Connection) -> None:
    """Read helpers call this instead of init_concordance_schema: the DDL and seed INSERTs run once per
    database per process (init_db already does it at start-up), so a Tab 5 click never needs the
    write lock while a background build holds it."""
    if _db_identity(conn) not in _SCHEMA_READY:
        init_concordance_schema(conn)


def _morph_id(conn: sqlite3.Connection, lang: str, code: str) -> int:
    row = conn.execute(
        "SELECT morph_id FROM morpheme_catalog WHERE lang = ? AND morph_code = ?",
        (lang, code),
    ).fetchone()
    if row:
        return int(row[0])
    cur = conn.execute(
        "INSERT INTO morpheme_catalog (lang, morph_slot, morph_code, affix_form, grammatical_fn) VALUES (?, 'inflection', ?, NULL, ?)",
        (lang, code, code),
    )
    return int(cur.lastrowid)


def _ensure_affix_bundle(conn: sqlite3.Connection, lang: str, morph_codes: Sequence[str]) -> int:
    if not morph_codes:
        return 0
    bundle_code = "+".join(morph_codes)
    row = conn.execute(
        "SELECT bundle_id FROM affix_bundles WHERE lang = ? AND bundle_code = ?",
        (lang, bundle_code),
    ).fetchone()
    if row:
        return int(row[0])
    cur = conn.execute(
        "INSERT INTO affix_bundles (lang, bundle_code) VALUES (?, ?)",
        (lang, bundle_code),
    )
    bid = int(cur.lastrowid)
    for seq, mc in enumerate(morph_codes, start=1):
        if seq > 8:
            break
        mid = _morph_id(conn, lang, mc)
        conn.execute(
            "INSERT OR IGNORE INTO affix_bundle_items (bundle_id, seq_no, morph_id) VALUES (?, ?, ?)",
            (bid, seq, mid),
        )
    return bid


def _ensure_root(
    conn: sqlite3.Connection,
    lang: str,
    root_key: str,
    core_idea: str,
    homograph_no: int = 1,
    translit: Optional[str] = None,
) -> int:
    row = conn.execute(
        "SELECT root_id FROM core_roots WHERE lang = ? AND root_key = ? AND homograph_no = ?",
        (lang, root_key, homograph_no),
    ).fetchone()
    if row:
        return int(row[0])
    cur = conn.execute(
        "INSERT INTO core_roots (lang, root_key, homograph_no, translit, core_idea) VALUES (?, ?, ?, ?, ?)",
        (lang, root_key, homograph_no, translit, core_idea),
    )
    return int(cur.lastrowid)


def _ensure_stem(
    conn: sqlite3.Connection,
    lang: str,
    root_id: int,
    canonical_stem: str,
    pos_tag: str,
    base_gloss: str,
    ext_strongs: Optional[str] = None,
    secondary_root_id: Optional[int] = None,
    affix_bundle_id: Optional[int] = None,
    stem_pattern_morph_id: Optional[int] = None,
    deriv_suffix_morph_id: Optional[int] = None,
    structural_formula: Optional[str] = None,
) -> int:
    row = conn.execute(
        """
        SELECT stem_id FROM lexical_stems
        WHERE lang = ? AND canonical_stem = ? AND pos_tag = ?
          AND COALESCE(ext_strongs, '') = COALESCE(?, '')
        """,
        (lang, canonical_stem, pos_tag, ext_strongs),
    ).fetchone()
    if row:
        return int(row[0])
    cur = conn.execute(
        """
        INSERT INTO lexical_stems (
            lang, root_id, secondary_root_id, affix_bundle_id,
            stem_pattern_morph_id, deriv_suffix_morph_id, canonical_stem,
            pos_tag, ext_strongs, structural_formula, base_gloss
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lang,
            root_id,
            secondary_root_id,
            affix_bundle_id,
            stem_pattern_morph_id,
            deriv_suffix_morph_id,
            canonical_stem,
            pos_tag,
            ext_strongs,
            structural_formula,
            base_gloss,
        ),
    )
    return int(cur.lastrowid)


def _ensure_anchor_verse(
    conn: sqlite3.Connection,
    book_order: int,
    chapter: int,
    verse: int,
    subverse: int = 0,
    heb_ref: Optional[str] = None,
    grc_ref: Optional[str] = None,
    lat_ref: Optional[str] = None,
) -> int:
    avid = make_anchor_verse_id(book_order, chapter, verse, subverse)
    row = conn.execute("SELECT anchor_verse_id FROM versification_anchors WHERE anchor_verse_id = ?", (avid,)).fetchone()
    if row:
        return avid
    book = next(b for b in BOOKS if b.order == book_order)
    sref = format_saints_ref(book, chapter, verse, subverse)
    conn.execute(
        """
        INSERT OR IGNORE INTO versification_anchors (
            anchor_verse_id, book_order, chapter, verse, subverse, saints_ref, heb_ref, grc_ref, lat_ref
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            avid,
            book_order,
            chapter,
            verse,
            subverse,
            sref,
            heb_ref or (sref if book.has_hebrew else None),
            grc_ref or sref,
            lat_ref or sref,
        ),
    )
    return avid


def _ensure_surface_form(conn: sqlite3.Connection, lang: str, surface_text: str) -> int:
    row = conn.execute(
        "SELECT form_id FROM surface_forms WHERE lang = ? AND surface_text = ?",
        (lang, surface_text),
    ).fetchone()
    if row:
        return int(row[0])
    if lang in ("heb", "arc"):
        bare = strip_hebrew_marks(surface_text, normalize_finals=True)
    elif lang == "grc":
        bare = strip_greek_marks(surface_text)
    else:
        bare = strip_latin_marks(surface_text)
    cur = conn.execute(
        "INSERT INTO surface_forms (lang, surface_text, bare_lookup_key) VALUES (?, ?, ?)",
        (lang, surface_text, bare or surface_text.lower()),
    )
    return int(cur.lastrowid)


# The seven curated colour hubs: slug, English base word, colour (site key), note, senses (offset, word,
# role, nuance).  Seeded on an empty database and re-applied by the gold build unless a person has edited
# the hub in Tab 5 (concordance_gold.refresh_curated_hubs).
# Colours follow the site's fixed seven-colour key (saints-verse-themes.php / word-studies BRIEF.md); see
# concordance_gold.HUB_KEY for the theme label of each hub and the evidence.
CURATED_HUBS: List[Tuple[str, str, str, str, List[Tuple[int, str, str, str]]]] = [
    (
        "ORIGIN_HEAD_START", "head / origin", "red",
        "Head, beginning and first portion: Hebrew רֵאשִׁית / רֹאשׁ (BDB root ראשׁ) and תְּחִלָּה (root חלל II), "
        "Greek ἀρχή / ἀπαρχή (family of ἄρχω), Latin principium, initium and caput (three different Latin roots). "
        "A shared meaning, not a shared root.",
        [
            (1, "beginning", "temporal_origin", "Absolute or cosmic point of origin (Gen 1:1; John 1:1)"),
            (2, "start", "actional_onset", "Inaugural onset of a word, ministry, or action (Hos 1:2; Mark 1:1)"),
            (3, "headwater", "spatial_source", "Hydrological source-head where one river divides into branches (Gen 2:10)"),
            (4, "firstfruit", "choicest_portion", "First and choicest portion offered to God (Exod 23:19; Rom 8:23)"),
            (5, "head", "anatomical_crown", "Physical head, crown, or summit (Gen 3:15; Ps 117:22 [Eng. 118:22])"),
            (6, "chief", "ruling_rank", "Foremost leader, magistrate, or ruler (Exod 6:14; Eph 1:21)"),
        ],
    ),
    (
        "WORD_LOGOS_SPEECH", "word / speech", "green",
        "Spoken word, matter and account: Hebrew דָּבָר (root דבר), Greek λόγος (family of λέγω), Latin verbum.",
        [
            (1, "word", "divine_utterance", "Spoken or revealed message of God (John 1:1; Ps 32:6 [Eng. 33:6])"),
            (2, "matter", "concrete_affair", "Thing, event, or case spoken about (Gen 15:1; Luke 1:4)"),
            (3, "account", "reckoning_reason", "Reckoning, statement, or reasoned report (Matt 12:36; 1 Pet 3:15)"),
        ],
    ),
    (
        "SPIRIT_BREATH_WIND", "breath / spirit", "violet",
        "Unseen moving air as wind, living breath, or the Holy Spirit: Hebrew רוּחַ, Greek πνεῦμα (family of πνέω), "
        "Latin spiritus (family of spiro).",
        [
            (1, "Spirit", "divine_spirit", "The Spirit of God moving, anointing, and indwelling (Gen 1:2; Rom 8:9)"),
            (2, "breath", "vital_respiration", "Vital breath animating flesh (Gen 6:17; Jas 2:26)"),
            (3, "wind", "moving_air", "Blowing wind of heaven (Gen 8:1; John 3:8)"),
        ],
    ),
    (
        "LIGHT_DAWN_LAMP", "light / shine", "green",
        "Light and light-bearers: Hebrew אוֹר and מָאוֹר (root אור), Greek φῶς and φωστήρ, Latin lux and lumen.",
        [
            (1, "light", "uncreated_or_cosmic_light", "Light itself shining in darkness (Gen 1:3; John 1:4)"),
            (2, "luminary", "celestial_vessel", "Sun, moon, or star bearing light in the sky-vault (Gen 1:14; Phil 2:15)"),
            (3, "dawn", "morning_break", "First break of morning daylight (Judg 16:2)"),
        ],
    ),
    (
        "FAITH_TRUST_AMEN", "firm / trust", "green",
        "Firmness, trust and faithfulness: Hebrew אָמַן, אֱמוּנָה and אָמֵן (root אמן), Greek πίστις (family of πείθω) "
        "and ἀμήν (borrowed from Hebrew), Latin fides.",
        [
            (1, "faith", "trusting_allegiance", "Active reliance and covenantal trust in God (Gen 15:6; Hab 2:4; Rom 1:17)"),
            (2, "faithfulness", "steadfast_fidelity", "Unwavering reliability and covenantal loyalty (Lam 3:23; Gal 5:22)"),
            (3, "amen", "solemn_affirmation", "Liturgical confirmation: 'truly / it stands firm' (Deut 27:15; Rev 3:14)"),
        ],
    ),
    (
        "LIFE_SOUL_CREATURE", "life / breathing-being", "green",
        "Soul, living being and life: Hebrew נֶפֶשׁ, Greek ψυχή, Latin anima.",
        [
            (1, "soul", "inner_person", "Whole inner life, self, and seat of desire (Ps 41:2 [Eng. 42:1]; Matt 10:28)"),
            (2, "creature", "breathing_animal", "Embodied living being ('living soul/creature', Gen 1:20; Gen 2:7)"),
            (3, "life", "mortal_vitality", "One's physical life laid down or preserved (Exod 21:23; Mark 10:45)"),
        ],
    ),
    (
        "HOLY_SET_APART", "set-apart / holy", "yellow",
        "Holiness and the holy place: Hebrew קָדוֹשׁ and מִקְדָּשׁ (root קדשׁ), Greek ἅγιος, Latin sanctus.",
        [
            (1, "holy", "sacred_attribute", "Transcendent purity of God and things belonging to Him (Exod 15:11; Isa 6:3)"),
            (2, "saint", "consecrated_person", "God's set-apart covenant people (Ps 33:10 [Eng. 34:9]; Eph 1:1)"),
            (3, "sanctuary", "sacred_dwelling", "Consecrated dwelling-place where God meets His people (Exod 15:17; Heb 8:2)"),
        ],
    ),
]


def _seed_flagship_trilingual_showcase(conn: sqlite3.Connection) -> None:
    """Seed the seven curated colour hubs (concept + English senses) once, on an empty database.

    A hub groups words of the three languages that share a MEANING; their roots differ (BDB ראשׁ,
    Greek ἄρχω, Latin caput/princeps are unrelated roots).  Member lemmas and their default senses
    are listed in studio/concordance_gold.CURATED_HUB_MEMBERS and linked by the gold build; alignment
    units are made by that build wherever members of a hub occur in two or more languages of the same
    Saints.Bible verse.  References in the sense notes use the Saints.Bible (Greek) numbering, with
    the English numbering in brackets where it differs.

    (The first build also wrote hand-made stems and five "human-locked" alignment rows here; no person
    had verified them, several formulas were wrong — e.g. a Hiphil verb pattern on the noun תְּחִלָּה,
    one Latin root for caput 'head' and capio 'take' — and the lock stopped the rest of those verses
    from ever being indexed.  They are no longer created.)"""
    hubs = CURATED_HUBS
    for slug, eng_base, col, note, senses in hubs:
        conn.execute(
            "INSERT OR IGNORE INTO trilingual_concepts (concept_slug, eng_base_word, theme_colour, summary_note) VALUES (?, ?, ?, ?)",
            (slug, eng_base, col, note),
        )
        cid = int(conn.execute("SELECT concept_id FROM trilingual_concepts WHERE concept_slug = ?", (slug,)).fetchone()[0])
        conn.executemany(
            "INSERT OR IGNORE INTO saints_senses (concept_id, sense_offset, base_word, sense_role, usage_nuance) VALUES (?, ?, ?, ?, ?)",
            [(cid, off, bw, role, nuance) for off, bw, role, nuance in senses],
        )


# ---------------------------------------------------------------------------
# Posting Compiler — Delta-Varint Inverted Index Builder
# ---------------------------------------------------------------------------

def rebuild_concordance_postings(conn: sqlite3.Connection) -> Dict[str, int]:
    """Compile sorted anchor_verse_id delta-varint BLOBs for all concepts, senses, roots, and stems."""
    ref_lookup = {
        int(r[0]): str(r[1])
        for r in conn.execute("SELECT anchor_verse_id, saints_ref FROM versification_anchors").fetchall()
    }

    def _pack_rows(kind: str, pairs: Sequence[Tuple[int, int]]) -> List[Tuple[str, int, int, int, bytes, str]]:
        by_target: Dict[int, List[int]] = {}
        for tid, avid in pairs:
            by_target.setdefault(int(tid), []).append(int(avid))
        rows_out = []
        for tid, avids in by_target.items():
            uniq = sorted(set(avids))
            blob = encode_delta_varints(uniq)
            samples = ",".join(ref_lookup.get(v, str(v)) for v in uniq[:5])
            rows_out.append((kind, tid, len(avids), len(uniq), blob, samples))
        return rows_out

    sense_hits = conn.execute(
        """
        SELECT sense_id, anchor_verse_id FROM trilingual_alignments
        UNION ALL
        SELECT st.sense_id, wa.anchor_verse_id
        FROM stream_tokens st
        JOIN word_anchors wa ON wa.slot_id = st.slot_id
        WHERE NOT EXISTS (
            SELECT 1 FROM trilingual_alignment_slots tas WHERE tas.slot_id = st.slot_id
        )
        """
    ).fetchall()

    concept_hits = conn.execute(
        """
        SELECT ss.concept_id, ta.anchor_verse_id
        FROM trilingual_alignments ta
        JOIN saints_senses ss ON ss.sense_id = ta.sense_id
        UNION ALL
        SELECT ss.concept_id, wa.anchor_verse_id
        FROM stream_tokens st
        JOIN word_anchors wa ON wa.slot_id = st.slot_id
        JOIN saints_senses ss ON ss.sense_id = st.sense_id
        WHERE NOT EXISTS (
            SELECT 1 FROM trilingual_alignment_slots tas WHERE tas.slot_id = st.slot_id
        )
        """
    ).fetchall()

    stem_hits = conn.execute(
        """
        SELECT st.stem_id, wa.anchor_verse_id
        FROM stream_tokens st
        JOIN word_anchors wa ON wa.slot_id = st.slot_id
        """
    ).fetchall()

    root_hits = conn.execute(
        """
        SELECT ls.root_id, wa.anchor_verse_id
        FROM stream_tokens st
        JOIN word_anchors wa ON wa.slot_id = st.slot_id
        JOIN lexical_stems ls ON ls.stem_id = st.stem_id
        """
    ).fetchall()

    all_packed = (
        _pack_rows("sense", sense_hits)
        + _pack_rows("concept", concept_hits)
        + _pack_rows("stem", stem_hits)
        + _pack_rows("root", root_hits)
    )

    conn.execute("DELETE FROM concordance_postings")
    conn.executemany(
        """
        INSERT INTO concordance_postings (
            target_kind, target_id, hit_count, verse_count, delta_varint_blob, sample_refs_csv
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        all_packed,
    )
    return {
        "total_posting_rows": len(all_packed),
        "total_varint_bytes": sum(len(r[4]) for r in all_packed),
    }


# ---------------------------------------------------------------------------
# Building the concordance: gold lemma tags (studio/concordance_gold.py, studio/lexica/)
# ---------------------------------------------------------------------------
# The first build (Gemini, 18 Nov 2026) derived roots by stripping endings from surface forms and
# looked words up by unpointed consonants / accentless Greek / naive Latin stems, first match wins;
# it paired the three languages by raw verse number although each is stored in its own numbering,
# and deleted every parenthesis from Greek and Latin text.  Measured against TAHOT, TAGNT and the
# Rahlfs/PROIEL yardsticks it indexed ~22 % of tokens with 42 % (Hebrew) to ~80 % (Greek) lemma
# precision.  Both entry points below now run the gold build instead; the old heuristics are gone.


def seed_stepbible_and_latin_lexicons(
    conn: sqlite3.Connection,
    stepbible_root: Optional[Path] = None,
    include_proper_nouns: bool = False,
) -> Dict[str, Any]:
    """Build the whole concordance from the gold-tagged editions (kept for the CLI 'seed' action and
    the Tab 5 button).  ``stepbible_root`` / ``include_proper_nouns`` are accepted for compatibility:
    the lexica modules locate their own corpora, and proper nouns are always indexed (as PROPN)."""
    _ensure_schema_ready(conn)
    from .concordance_gold import build_gold_concordance

    return build_gold_concordance(conn)


def index_saved_critical_texts(
    conn: sqlite3.Connection,
    book_slug: Optional[str] = None,
    max_chapters: int = 0,
) -> Dict[str, Any]:
    """Index the saved critical texts (one book, or all) with gold lemma tags, filed under the
    Saints.Bible verse numbering.  Raises KeyError for an unknown book slug."""
    _ensure_schema_ready(conn)
    if book_slug and book_slug not in BOOKS_BY_SLUG:
        raise KeyError(f"Unknown book slug: {book_slug!r}")
    from .concordance_gold import build_gold_concordance

    return build_gold_concordance(conn, book_slug=book_slug, max_chapters=max_chapters)
# ---------------------------------------------------------------------------
# Space-Savings Telemetry, Visual Graph Queries & Scholarly Curation API
# ---------------------------------------------------------------------------

def get_concordance_dashboard_stats(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Live counts from the tables and the exported pack — measurements only, no projections.

    (The first build reported "841.1 MB naive -> 7.24 MB, 99.1 % bloat eliminated" from constants
    typed into this function; those figures were never measured and have been removed.)"""
    _ensure_schema_ready(conn)
    from .concordance_gold import gold_stats

    roots_by_lang = {
        str(r[0]): int(r[1])
        for r in conn.execute("SELECT lang, COUNT(*) FROM core_roots GROUP BY lang").fetchall()
    }
    q = lambda sql: int(conn.execute(sql).fetchone()[0])  # noqa: E731
    gs = gold_stats(conn)
    pack_dir = OUTPUT_ROOT / CONCORDANCE_PACK_DIR_NAME
    pack_files = sorted(pack_dir.glob("saints-concordance-*.json.gz")) if pack_dir.exists() else []
    exported_gz_bytes = sum(p.stat().st_size for p in pack_files)
    coverage = {}
    for lang, c in (gs.get("coverage") or (gs.get("last_build") or {}).get("languages") or {}).items():
        coverage[lang] = {
            "tokens": c.get("tokens", 0),
            "indexed": c.get("indexed", 0),
            "content_words": c.get("content_words", c.get("indexed", 0)),
            "function_words": c.get("function_words", 0),
            "with_morph": c.get("with_morph", 0),
            "untagged": c.get("untagged", 0),
            "unmapped_verse_tokens": c.get("tokens_in_unmapped_verses", 0),
        }
    return {
        "roots_by_lang": roots_by_lang,
        "total_roots": sum(roots_by_lang.values()),
        "total_morphemes": q("SELECT COUNT(*) FROM morpheme_catalog"),
        "total_bundles": q("SELECT COUNT(*) FROM affix_bundles"),
        "total_stems": q("SELECT COUNT(*) FROM lexical_stems"),
        "total_concepts": q("SELECT COUNT(*) FROM trilingual_concepts"),
        "total_senses": q("SELECT COUNT(*) FROM saints_senses"),
        "total_tokens": q("SELECT COUNT(*) FROM stream_tokens"),
        "content_tokens_total": gs.get("content_tokens_total", 0),
        "function_tokens_total": gs.get("function_tokens_total", 0),
        "total_alignments": q("SELECT COUNT(*) FROM trilingual_alignments"),
        "locked_tokens": q("SELECT COUNT(*) FROM stream_tokens WHERE human_locked = 1"),
        "varint_bytes": q("SELECT COALESCE(SUM(LENGTH(delta_varint_blob)), 0) FROM concordance_postings"),
        "tokens_by_stream": gs["tokens_by_stream"],
        "lemmas_used_by_lang": gs["lemmas_used_by_lang"],
        "roots_used_by_lang": gs["roots_used_by_lang"],
        "surface_forms_used_by_lang": gs["surface_forms_used_by_lang"],
        "coverage": coverage,
        "last_build_at": gs["last_build_at"],
        "last_build_seconds": gs["last_build_seconds"],
        "last_build_scope": gs["last_build_scope"],
        "exported_gz_bytes": exported_gz_bytes,
        "pack_dir": str(pack_dir),
    }


def search_concordance_concepts(
    conn: sqlite3.Connection,
    query: str = "",
    lang_filter: str = "all",
    colour_filter: str = "all",
    limit: int = 250,
) -> List[Dict[str, Any]]:
    """Search unified concepts by English sense ('headwater'), root ('ר-א-שׁ', 'ἀρχ', 'cap'), or Strong's ('H7225')."""
    _ensure_schema_ready(conn)
    q = query.strip()
    where = ["1=1"]
    params: List[Any] = []

    if colour_filter and colour_filter != "all":
        if colour_filter == "curated_rainbow":
            where.append("tc.theme_colour IS NOT NULL")
        else:
            where.append("tc.theme_colour = ?")
            params.append(colour_filter)

    if lang_filter and lang_filter != "all":
        where.append(
            """
            EXISTS (
                SELECT 1 FROM stem_concept_links scl
                JOIN lexical_stems ls ON ls.stem_id = scl.stem_id
                WHERE scl.concept_id = tc.concept_id AND ls.lang = ?
            )
            """
        )
        params.append(lang_filter)

    if q:
        like = f"%{q}%"
        bare_h = strip_hebrew_marks(q, normalize_finals=True)
        bare_g = strip_greek_marks(q)
        where.append(
            """
            (
                tc.concept_slug LIKE ?
                OR tc.eng_base_word LIKE ?
                OR tc.summary_note LIKE ?
                OR EXISTS (
                    SELECT 1 FROM saints_senses ss
                    WHERE ss.concept_id = tc.concept_id
                      AND (ss.base_word LIKE ? OR ss.usage_nuance LIKE ? OR ss.sense_role LIKE ?)
                )
                OR EXISTS (
                    SELECT 1 FROM stem_concept_links scl
                    JOIN lexical_stems ls ON ls.stem_id = scl.stem_id
                    JOIN core_roots cr ON cr.root_id = ls.root_id
                    WHERE scl.concept_id = tc.concept_id
                      AND (
                          ls.canonical_stem LIKE ?
                          OR COALESCE(ls.translit, '') LIKE ?
                          OR ls.ext_strongs LIKE ?
                          OR ls.base_gloss LIKE ?
                          OR cr.root_key LIKE ?
                          OR COALESCE(cr.translit, '') LIKE ?
                          OR (? != '' AND REPLACE(cr.root_key, '-', '') LIKE ?)
                          OR (? != '' AND ls.canonical_stem LIKE ?)
                      )
                )
            )
            """
        )
        params.extend([
            like, like, like,
            like, like, like,
            like, like, like, like, like, like,
            bare_h, f"%{bare_h}%",
            bare_g, f"%{bare_g}%",
        ])

    if q:
        order_sql = """
            CASE WHEN EXISTS (
                     SELECT 1 FROM stem_concept_links scl
                     JOIN lexical_stems ls ON ls.stem_id = scl.stem_id
                     JOIN core_roots cr ON cr.root_id = ls.root_id
                     WHERE scl.concept_id = tc.concept_id
                       AND (LOWER(COALESCE(ls.ext_strongs, '')) = LOWER(?)
                            OR LOWER(ls.canonical_stem) = LOWER(?)
                            OR LOWER(COALESCE(ls.translit, '')) = LOWER(?)
                            OR LOWER(COALESCE(cr.translit, '')) = LOWER(?))
                 ) OR UPPER(tc.concept_slug) = UPPER(?) THEN 0 ELSE 1 END,
            CASE WHEN tc.theme_colour IS NOT NULL THEN 0 ELSE 1 END,
            lang_span DESC,
            hit_count DESC,
            tc.concept_id ASC
        """
        params.extend([q, q, q, q, q])
    else:
        order_sql = """
            CASE WHEN tc.theme_colour IS NOT NULL THEN 0
                 WHEN COALESCE(has_content, 1) = 1 THEN 1
                 ELSE 2 END,
            lang_span DESC,
            hit_count DESC,
            tc.concept_id ASC
        """

    params.append(int(limit))
    rows = conn.execute(
        f"""
        SELECT
            tc.concept_id,
            tc.concept_slug,
            tc.eng_base_word,
            tc.theme_colour,
            tc.summary_note,
            (SELECT COUNT(*) FROM saints_senses ss WHERE ss.concept_id = tc.concept_id) AS sense_count,
            (SELECT COUNT(DISTINCT ls.lang) FROM stem_concept_links scl
             JOIN lexical_stems ls ON ls.stem_id = scl.stem_id
             WHERE scl.concept_id = tc.concept_id) AS lang_span,
            COALESCE((SELECT MAX(ls.is_content) FROM stem_concept_links scl
             JOIN lexical_stems ls ON ls.stem_id = scl.stem_id
             WHERE scl.concept_id = tc.concept_id), 1) AS has_content,
            COALESCE(cp.hit_count, 0) AS hit_count,
            COALESCE(cp.verse_count, 0) AS verse_count
        FROM trilingual_concepts tc
        LEFT JOIN concordance_postings cp
               ON cp.target_kind = 'concept' AND cp.target_id = tc.concept_id
        WHERE {' AND '.join(where)}
        ORDER BY {order_sql}
        LIMIT ?
        """,
        params,
    ).fetchall()

    out: List[Dict[str, Any]] = []
    for r in rows:
        cid = int(r["concept_id"])
        senses = [
            dict(sr)
            for sr in conn.execute(
                """
                SELECT ss.sense_id, ss.sense_offset, ss.base_word, ss.sense_role, ss.usage_nuance,
                       COALESCE(cp.hit_count, 0) AS hit_count
                FROM saints_senses ss
                LEFT JOIN concordance_postings cp
                       ON cp.target_kind = 'sense' AND cp.target_id = ss.sense_id
                WHERE ss.concept_id = ?
                ORDER BY ss.sense_offset ASC
                """,
                (cid,),
            ).fetchall()
        ]
        out.append({**dict(r), "senses": senses})
    return out


def get_concept_visual_graph(conn: sqlite3.Connection, concept_id: int) -> Dict[str, Any]:
    """Return the complete Root -> Morpheme Stem -> Unified Concept -> Sense Offsets + Occurrences graph."""
    _ensure_schema_ready(conn)
    tc = conn.execute("SELECT * FROM trilingual_concepts WHERE concept_id = ?", (concept_id,)).fetchone()
    if not tc:
        raise KeyError(f"Concept {concept_id} not found.")

    from .translit import transliterate as _tr

    stems = [
        dict(r)
        for r in conn.execute(
            """
            SELECT
                ls.stem_id, ls.lang, ls.canonical_stem, ls.pos_tag, ls.ext_strongs,
                ls.structural_formula, ls.base_gloss, COALESCE(ls.translit, '') AS stem_translit,
                cr.root_id, cr.root_key, cr.homograph_no, cr.core_idea, COALESCE(cr.translit, '') AS translit,
                cr2.root_key AS secondary_root_key,
                ab.bundle_code AS prefix_bundle_code,
                mp.morph_code AS pattern_code,
                ms.affix_form AS suffix_form,
                scl.default_sense_id, scl.link_weight,
                COALESCE(cp.hit_count, 0) AS hit_count
            FROM stem_concept_links scl
            JOIN lexical_stems ls ON ls.stem_id = scl.stem_id
            JOIN core_roots cr ON cr.root_id = ls.root_id
            LEFT JOIN core_roots cr2 ON cr2.root_id = ls.secondary_root_id
            LEFT JOIN affix_bundles ab ON ab.bundle_id = ls.affix_bundle_id
            LEFT JOIN morpheme_catalog mp ON mp.morph_id = ls.stem_pattern_morph_id
            LEFT JOIN morpheme_catalog ms ON ms.morph_id = ls.deriv_suffix_morph_id
            LEFT JOIN concordance_postings cp ON cp.target_kind = 'stem' AND cp.target_id = ls.stem_id
            WHERE scl.concept_id = ?
            ORDER BY CASE ls.lang WHEN 'heb' THEN 1 WHEN 'arc' THEN 2 WHEN 'grc' THEN 3 ELSE 4 END, ls.stem_id ASC
            """,
            (concept_id,),
        ).fetchall()
    ]

    # Deduplicated roots participating in this concept (ensure translit for heb/arc/grc even on pre-backfill DBs)
    roots_seen: Dict[int, Dict[str, Any]] = {}
    for st in stems:
        slang = str(st["lang"])
        if slang in ("heb", "arc", "grc"):
            if not st.get("stem_translit"):
                st["stem_translit"] = _tr(str(st["canonical_stem"]), slang)
            if not st.get("translit"):
                st["translit"] = _tr(str(st["root_key"]), slang)
        rid = int(st["root_id"])
        if rid not in roots_seen:
            roots_seen[rid] = {
                "root_id": rid,
                "lang": slang,
                "root_key": st["root_key"],
                "homograph_no": st["homograph_no"],
                "core_idea": st["core_idea"],
                "translit": st["translit"],
            }

    senses = []
    for sr in conn.execute(
        """
        SELECT ss.*, COALESCE(cp.hit_count, 0) AS hit_count,
               COALESCE(cp.verse_count, 0) AS verse_count,
               cp.delta_varint_blob, cp.sample_refs_csv
        FROM saints_senses ss
        LEFT JOIN concordance_postings cp ON cp.target_kind = 'sense' AND cp.target_id = ss.sense_id
        WHERE ss.concept_id = ?
        ORDER BY ss.sense_offset ASC
        """,
        (concept_id,),
    ).fetchall():
        d = dict(sr)
        blob = d.pop("delta_varint_blob", None) or b""
        d["varint_byte_len"] = len(blob)
        d["decoded_verse_ids"] = decode_delta_varints(blob)[:25]
        senses.append(d)

    # Aligned & single-stream occurrences for this concept
    occurrences = []
    for orow in conn.execute(
        """
        SELECT
            ta.align_id,
            va.saints_ref,
            va.book_order,
            bc.book_slug,
            va.chapter,
            va.verse,
            va.subverse,
            ta.anchor_verse_id,
            ta.sense_id,
            ss.sense_offset,
            ss.base_word,
            ss.sense_role,
            em.morph_code AS eng_morph_code,
            ta.alignment_state
        FROM trilingual_alignments ta
        JOIN saints_senses ss ON ss.sense_id = ta.sense_id
        JOIN versification_anchors va ON va.anchor_verse_id = ta.anchor_verse_id
        JOIN books_catalog bc ON bc.book_order = va.book_order
        LEFT JOIN morpheme_catalog em ON em.morph_id = ta.eng_infl_morph_id
        WHERE ss.concept_id = ?
        ORDER BY ta.anchor_verse_id ASC, ta.unit_seq ASC
        LIMIT 300
        """,
        (concept_id,),
    ).fetchall():
        od = dict(orow)
        od["rendered_word"] = render_english_sense(str(od["base_word"]), od.get("eng_morph_code"))
        # Gather per-language stream breakdown for this alignment unit
        slot_rows = conn.execute(
            """
            SELECT
                tas.lang_stream,
                sf.surface_text,
                ab.bundle_code,
                cr.root_key,
                cr.homograph_no,
                ls.canonical_stem,
                ls.structural_formula,
                im.morph_code AS infl_code,
                st.human_locked,
                st.slot_id
            FROM trilingual_alignment_slots tas
            JOIN stream_tokens st ON st.slot_id = tas.slot_id
            JOIN surface_forms sf ON sf.form_id = st.form_id
            JOIN lexical_stems ls ON ls.stem_id = st.stem_id
            JOIN core_roots cr ON cr.root_id = ls.root_id
            LEFT JOIN affix_bundles ab ON ab.bundle_id = st.affix_bundle_id
            LEFT JOIN morpheme_catalog im ON im.morph_id = st.infl_morph_id
            WHERE tas.align_id = ?
            """,
            (od["align_id"],),
        ).fetchall()
        streams_fmt: Dict[str, str] = {}
        streams_fmt_tr: Dict[str, str] = {}
        human_locked = False
        for sl in slot_rows:
            pfx = f"({sl['bundle_code']}+)" if sl["bundle_code"] and sl["bundle_code"] != "NONE" else ""
            hno = f"[{sl['homograph_no']}]" if int(sl["homograph_no"]) > 1 else ""
            formula = sl["structural_formula"] or sl["root_key"]
            ls_name = str(sl["lang_stream"])
            streams_fmt[ls_name] = f"{sl['surface_text']}  [{pfx}{formula}{hno} · {sl['infl_code']}]"
            if ls_name in ("heb_ot", "grc_ot", "grc_nt"):
                surf_tr = _tr(str(sl["surface_text"]), ls_name)
                tr_part = f" ({surf_tr})" if surf_tr and surf_tr != sl["surface_text"] else ""
                streams_fmt_tr[ls_name] = f"{sl['surface_text']}{tr_part}  [{pfx}{formula}{hno} · {sl['infl_code']}]"
            else:
                streams_fmt_tr[ls_name] = streams_fmt[ls_name]
            if int(sl["human_locked"]):
                human_locked = True
        od["heb_formula"] = streams_fmt.get("heb_ot", "—")
        od["grc_formula"] = streams_fmt.get("grc_ot") or streams_fmt.get("grc_nt", "—")
        od["lat_formula"] = streams_fmt.get("lat_bible", "—")
        od["heb_formula_translit"] = streams_fmt_tr.get("heb_ot", "—")
        od["grc_formula_translit"] = streams_fmt_tr.get("grc_ot") or streams_fmt_tr.get("grc_nt", "—")
        od["human_locked"] = human_locked
        od["occ_key"] = f"occ:{od['align_id']}"
        od["lang_stream"] = next(iter(streams_fmt), "")
        occurrences.append(od)

    # Lemma concepts (one language, no alignment units): list the verses where their words occur.
    if not occurrences:
        for trow in conn.execute(
            """
            SELECT st.slot_id, wa.lang_stream, va.saints_ref, va.book_order, bc.book_slug, va.chapter, va.verse, va.subverse,
                   wa.anchor_verse_id, st.sense_id, ss.sense_offset, ss.base_word, ss.sense_role,
                   em.morph_code AS eng_morph_code, sf.surface_text, ab.bundle_code,
                   ls.structural_formula, cr.root_key, cr.homograph_no, im.morph_code AS infl_code, st.human_locked,
                   va.heb_ref, va.grc_ref, va.lat_ref
            FROM stem_concept_links scl
            JOIN stream_tokens st ON st.stem_id = scl.stem_id
            JOIN word_anchors wa ON wa.slot_id = st.slot_id
            JOIN versification_anchors va ON va.anchor_verse_id = wa.anchor_verse_id
            JOIN books_catalog bc ON bc.book_order = va.book_order
            JOIN saints_senses ss ON ss.sense_id = st.sense_id
            JOIN surface_forms sf ON sf.form_id = st.form_id
            JOIN lexical_stems ls ON ls.stem_id = st.stem_id
            JOIN core_roots cr ON cr.root_id = ls.root_id
            LEFT JOIN affix_bundles ab ON ab.bundle_id = st.affix_bundle_id
            LEFT JOIN morpheme_catalog im ON im.morph_id = st.infl_morph_id
            LEFT JOIN morpheme_catalog em ON em.morph_id = st.eng_infl_morph_id
            WHERE scl.concept_id = ?
            ORDER BY wa.anchor_verse_id, wa.lang_stream, wa.slot_seq
            LIMIT 300
            """,
            (concept_id,),
        ).fetchall():
            td = dict(trow)
            pfx = f"({td['bundle_code']}+)" if td["bundle_code"] and td["bundle_code"] != "NONE" else ""
            hno = f"[{td['homograph_no']}]" if int(td["homograph_no"]) > 1 else ""
            infl = f" · {td['infl_code']}" if td.get("infl_code") else ""
            stream = str(td["lang_stream"])
            cell = f"{td['surface_text']}  [{pfx}{td['structural_formula'] or td['root_key']}{hno}{infl}]"
            if stream in ("heb_ot", "grc_ot", "grc_nt"):
                surf_tr = _tr(str(td["surface_text"]), stream)
                tr_part = f" ({surf_tr})" if surf_tr and surf_tr != td["surface_text"] else ""
                cell_tr = f"{td['surface_text']}{tr_part}  [{pfx}{td['structural_formula'] or td['root_key']}{hno}{infl}]"
            else:
                cell_tr = cell
            source_ref = {"heb_ot": td["heb_ref"], "lat_bible": td["lat_ref"]}.get(stream) or td["grc_ref"]
            occurrences.append({
                "align_id": None,
                "occ_key": f"tok:{td['slot_id']}",
                "slot_id": td["slot_id"],
                "lang_stream": stream,
                "source_ref": source_ref,
                "saints_ref": td["saints_ref"],
                "book_order": td["book_order"],
                "book_slug": td["book_slug"],
                "chapter": td["chapter"],
                "verse": td["verse"],
                "subverse": td["subverse"],
                "anchor_verse_id": td["anchor_verse_id"],
                "sense_id": td["sense_id"],
                "sense_offset": td["sense_offset"],
                "base_word": td["base_word"],
                "sense_role": td["sense_role"],
                "eng_morph_code": td["eng_morph_code"],
                "alignment_state": "single_stream",
                "rendered_word": render_english_sense(str(td["base_word"]), td["eng_morph_code"]),
                "heb_formula": cell if stream == "heb_ot" else "—",
                "grc_formula": cell if stream in ("grc_ot", "grc_nt") else "—",
                "lat_formula": cell if stream == "lat_bible" else "—",
                "heb_formula_translit": cell_tr if stream == "heb_ot" else "—",
                "grc_formula_translit": cell_tr if stream in ("grc_ot", "grc_nt") else "—",
                "human_locked": bool(td["human_locked"]),
            })

    return {
        "concept": dict(tc),
        "roots": list(roots_seen.values()),
        "stems": stems,
        "senses": senses,
        "occurrences": occurrences,
    }


def list_roots_and_morphemes(
    conn: sqlite3.Connection,
    kind: str = "roots",
    lang_filter: str = "all",
    query: str = "",
    limit: int = 300,
) -> List[Dict[str, Any]]:
    """Browse atomic roots or morpheme building blocks in Tab 5."""
    _ensure_schema_ready(conn)
    q = query.strip()
    params: List[Any] = []
    if kind == "morphemes":
        where = ["1=1"]
        if lang_filter != "all":
            where.append("lang = ?")
            params.append(lang_filter)
        if q:
            like = f"%{q}%"
            where.append("(morph_code LIKE ? OR COALESCE(affix_form, '') LIKE ? OR grammatical_fn LIKE ?)")
            params.extend([like, like, like])
        params.append(int(limit))
        return [
            dict(r)
            for r in conn.execute(
                f"""
                SELECT morph_id, lang, morph_slot, morph_code, COALESCE(affix_form, '—') AS affix_form, grammatical_fn
                FROM morpheme_catalog
                WHERE {' AND '.join(where)}
                ORDER BY
                    CASE morph_slot
                        WHEN 'proclitic' THEN 1
                        WHEN 'preverb' THEN 2
                        WHEN 'stem_pattern' THEN 3
                        WHEN 'deriv_suffix' THEN 4
                        WHEN 'enclitic_suffix' THEN 5
                        ELSE 6
                    END,
                    lang,
                    morph_code
                LIMIT ?
                """,
                params,
            ).fetchall()
        ]

    where = ["1=1"]
    if lang_filter != "all":
        where.append("cr.lang = ?")
        params.append(lang_filter)
    if q:
        like = f"%{q}%"
        bare_h = strip_hebrew_marks(q, normalize_finals=True)
        where.append(
            "(cr.root_key LIKE ? OR COALESCE(cr.translit, '') LIKE ? OR cr.core_idea LIKE ? OR (? != '' AND REPLACE(cr.root_key, '-', '') LIKE ?))"
        )
        params.extend([like, like, like, bare_h, f"%{bare_h}%"])
    params.append(int(limit))
    from .translit import transliterate as _tr

    root_rows = [
        dict(r)
        for r in conn.execute(
            f"""
            SELECT cr.root_id, cr.lang, cr.root_key, cr.homograph_no,
                   COALESCE(cr.translit, '') AS translit, cr.core_idea,
                   (SELECT COUNT(*) FROM lexical_stems ls WHERE ls.root_id = cr.root_id) AS stem_count,
                   COALESCE(cp.hit_count, 0) AS hit_count
            FROM core_roots cr
            LEFT JOIN concordance_postings cp ON cp.target_kind = 'root' AND cp.target_id = cr.root_id
            WHERE {' AND '.join(where)}
            ORDER BY stem_count DESC, hit_count DESC, cr.root_id ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
    ]
    for r in root_rows:
        if not r["translit"] and r["lang"] in ("heb", "arc", "grc"):
            r["translit"] = _tr(str(r["root_key"]), str(r["lang"]))
    return root_rows


def get_verse_concordance_breakdown(
    conn: sqlite3.Connection,
    book_slug: str,
    chapter: int,
    verse: int,
    language: str = "greek",
) -> Dict[str, Any]:
    """Return the Concordance tokens and aligned concepts of a verse (Workbench <-> Concordance bridge).

    ``chapter``/``verse`` are in the numbering of ``language`` as stored in the Studio (Hebrew = MT,
    Latin = Latin column, Greek = Saints.Bible); they are converted to the Saints.Bible verse the
    concordance files every token under."""
    _ensure_schema_ready(conn)
    if book_slug not in BOOKS_BY_SLUG:
        raise KeyError(f"Unknown book slug: {book_slug}")
    book = BOOKS_BY_SLUG[book_slug]
    from .lexica import versification

    targets = versification.to_saints(language, book_slug, int(chapter), int(verse))
    if targets:
        s_ch, s_vs = targets[0]
        sub = 0
    else:
        extra = versification.to_extra_site_anchor(language, book_slug, int(chapter), int(verse))
        if extra is None:
            reason = (
                "duplicate or placeholder — not indexed"
                if versification.is_duplicate_or_placeholder(language, book_slug, int(chapter), int(verse))
                else "no Saints.Bible counterpart"
            )
            return {
                "anchor_verse_id": None,
                "saints_ref": f"{format_saints_ref(book, chapter, verse)} ({language} numbering: {reason})",
                "tokens": [],
            }
        s_ch, s_vs = extra
        sub = versification.EXTRA_SITE_SUBVERSE
    avid = make_anchor_verse_id(book.order, s_ch, s_vs, sub)
    tokens = [
        dict(r)
        for r in conn.execute(
            """
            SELECT
                wa.lang_stream, wa.slot_seq, sf.surface_text,
                ab.bundle_code, cr.lang AS root_lang, cr.root_key, cr.homograph_no,
                ls.canonical_stem, ls.structural_formula, ls.ext_strongs,
                im.morph_code AS infl_code, im.grammatical_fn AS infl_desc,
                ss.sense_id, ss.sense_offset, ss.base_word, ss.sense_role,
                em.morph_code AS eng_morph_code,
                tc.concept_id, tc.concept_slug, tc.theme_colour,
                st.is_content, st.human_locked
            FROM word_anchors wa
            JOIN stream_tokens st ON st.slot_id = wa.slot_id
            JOIN surface_forms sf ON sf.form_id = st.form_id
            JOIN lexical_stems ls ON ls.stem_id = st.stem_id
            JOIN core_roots cr ON cr.root_id = ls.root_id
            JOIN saints_senses ss ON ss.sense_id = st.sense_id
            JOIN trilingual_concepts tc ON tc.concept_id = ss.concept_id
            LEFT JOIN affix_bundles ab ON ab.bundle_id = st.affix_bundle_id
            LEFT JOIN morpheme_catalog im ON im.morph_id = st.infl_morph_id
            LEFT JOIN morpheme_catalog em ON em.morph_id = st.eng_infl_morph_id
            WHERE wa.anchor_verse_id = ?
            ORDER BY wa.lang_stream, wa.slot_seq
            """,
            (avid,),
        ).fetchall()
    ]
    stream_of_lang = {"hebrew": "heb_ot", "latin": "lat_bible"}.get(language)
    if stream_of_lang is None:
        stream_of_lang = "grc_nt" if book.testament == "NT" else "grc_ot"
    # The Workbench language's own words first
    tokens.sort(key=lambda t: (0 if t["lang_stream"] == stream_of_lang else 1, str(t["lang_stream"]), int(t["slot_seq"])))
    from .translit import transliterate as _tr

    for t in tokens:
        t["rendered_word"] = render_english_sense(str(t["base_word"]), t.get("eng_morph_code"))
        ls_name = str(t["lang_stream"])
        rlang = str(t["root_lang"])
        if ls_name in ("heb_ot", "grc_ot", "grc_nt"):
            t["surface_translit"] = _tr(str(t["surface_text"]), ls_name)
            t["stem_translit"] = _tr(str(t["canonical_stem"]), rlang)
            t["root_translit"] = _tr(str(t["root_key"]), rlang)
        else:
            t["surface_translit"] = ""
            t["stem_translit"] = ""
            t["root_translit"] = ""
    ref = format_saints_ref(book, s_ch, s_vs) + ("*" if sub == versification.EXTRA_SITE_SUBVERSE else "")
    if sub == versification.EXTRA_SITE_SUBVERSE:
        ref += f" ({language.title()} {chapter}:{verse}, extra-site)"
    elif (s_ch, s_vs) != (int(chapter), int(verse)):
        ref += f" (= {language.title()} {chapter}:{verse})"
    return {"anchor_verse_id": avid, "saints_ref": ref, "tokens": tokens}


def upsert_concept_and_sense(
    conn: sqlite3.Connection,
    concept_slug: str,
    eng_base_word: str,
    summary_note: str,
    sense_offset: int,
    sense_base_word: str,
    sense_role: str,
    usage_nuance: str,
    theme_colour: Optional[str] = None,
) -> Dict[str, int]:
    """Create or update a Trilingual Concept and a Contextual Sense Offset, recording a studio_revisions entry."""
    _ensure_schema_ready(conn)
    slug = re.sub(r"[^A-Z0-9_]+", "_", concept_slug.strip().upper()).strip("_")
    if not slug:
        raise ValueError("Concept slug cannot be empty.")
    col = theme_colour if theme_colour in SAINTS_COLOURS else None

    row = conn.execute("SELECT concept_id FROM trilingual_concepts WHERE concept_slug = ?", (slug,)).fetchone()
    if row:
        cid = int(row[0])
        conn.execute(
            "UPDATE trilingual_concepts SET eng_base_word = ?, theme_colour = ?, summary_note = ? WHERE concept_id = ?",
            (eng_base_word.strip(), col, summary_note.strip(), cid),
        )
    else:
        cur = conn.execute(
            "INSERT INTO trilingual_concepts (concept_slug, eng_base_word, theme_colour, summary_note) VALUES (?, ?, ?, ?)",
            (slug, eng_base_word.strip(), col, summary_note.strip()),
        )
        cid = int(cur.lastrowid)

    srow = conn.execute(
        "SELECT sense_id, base_word FROM saints_senses WHERE concept_id = ? AND sense_offset = ?",
        (cid, int(sense_offset)),
    ).fetchone()
    old_val = str(srow["base_word"]) if srow else None
    if srow:
        sid = int(srow["sense_id"])
        conn.execute(
            "UPDATE saints_senses SET base_word = ?, sense_role = ?, usage_nuance = ? WHERE sense_id = ?",
            (sense_base_word.strip(), sense_role.strip(), usage_nuance.strip(), sid),
        )
    else:
        cur_s = conn.execute(
            "INSERT INTO saints_senses (concept_id, sense_offset, base_word, sense_role, usage_nuance) VALUES (?, ?, ?, ?, ?)",
            (cid, int(sense_offset), sense_base_word.strip(), sense_role.strip(), usage_nuance.strip()),
        )
        sid = int(cur_s.lastrowid)

    conn.execute(
        """
        INSERT INTO studio_revisions (target_table, target_pk, field_changed, old_val, new_val, actor, review_mode, rationale)
        VALUES ('saints_senses', ?, 'base_word+usage_nuance', ?, ?, 'human_editor', 'human_locked', ?)
        """,
        (f"{cid}:{sense_offset}", old_val, sense_base_word.strip(), usage_nuance.strip()),
    )
    return {"concept_id": cid, "sense_id": sid}


def update_alignment_sense_and_lock(
    conn: sqlite3.Connection,
    align_id: int,
    new_sense_id: int,
    eng_plural: bool = False,
    lock: bool = True,
    rationale: str = "",
) -> None:
    """Update a verse alignment unit's contextual sense offset (e.g. 'beginning' -> 'headwater') and lock its tokens."""
    _ensure_schema_ready(conn)
    m_eng = _morph_id(conn, "eng", "ENG:PL" if eng_plural else "ENG:SG")
    old = conn.execute("SELECT sense_id FROM trilingual_alignments WHERE align_id = ?", (align_id,)).fetchone()
    if not old:
        raise KeyError(f"Alignment {align_id} not found.")
    conn.execute(
        "UPDATE trilingual_alignments SET sense_id = ?, eng_infl_morph_id = ? WHERE align_id = ?",
        (new_sense_id, m_eng, align_id),
    )
    # Unlock first if unlocking, else update with review_status='human_verified' so trigger permits it
    slot_ids = [
        int(r[0])
        for r in conn.execute("SELECT slot_id FROM trilingual_alignment_slots WHERE align_id = ?", (align_id,)).fetchall()
    ]
    for sl_id in slot_ids:
        conn.execute(
            """
            UPDATE stream_tokens
            SET sense_id = ?, eng_infl_morph_id = ?,
                review_status = ?, human_locked = ?
            WHERE slot_id = ?
            """,
            (new_sense_id, m_eng, "human_verified" if lock else "auto", 1 if lock else 0, sl_id),
        )
    conn.execute(
        """
        INSERT INTO studio_revisions (target_table, target_pk, field_changed, old_val, new_val, actor, review_mode, rationale)
        VALUES ('trilingual_alignments', ?, 'sense_id', ?, ?, 'human_editor', 'human_locked', ?)
        """,
        (str(align_id), str(old[0]), str(new_sense_id), rationale or "Scholarly Concordance sense override"),
    )
    rebuild_concordance_postings(conn)


# ---------------------------------------------------------------------------
# Saints.Bible website pack
# ---------------------------------------------------------------------------
# The first build's single 4.4 MB pack was 99.8 % lexicon dump (every seeded lemma, used or not) with
# no root or lemma postings.  The pack is now written by studio/concordance_gold.export_gold_pack:
# one gzip file per language holding only the lemmas and roots that occur, with delta-varint verse
# postings per lemma (a root's verses are the union of its lemmas'), the curated colour hubs, the
# decoder below and a report whose numbers are measured from the files written.

from .concordance_gold import DECODER_JS_V3 as SAINTS_CONCORDANCE_DECODER_JS  # noqa: E402


def export_saints_bible_pack(conn: sqlite3.Connection, out_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Export the Saints.Bible concordance pack (see studio/concordance_gold.export_gold_pack)."""
    _ensure_schema_ready(conn)
    from .concordance_gold import export_gold_pack

    return export_gold_pack(conn, out_dir=out_dir)
