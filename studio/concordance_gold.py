"""Gold-data build of The Saints Concordance (18 Nov 2026).

Replaces the surface-form guessing of the first Concordance build (suffix stripping, first-match
lookups, raw verse numbers shared across languages) with:

* lemma tags from openly licensed word-by-word tagged editions (``studio/lexica``): OSHB for the
  Hebrew/Aramaic OT, STEPBible TAGNT for the Greek NT, the Open Scriptures Septuagint lemmas for
  the Greek OT, and a Lewis & Short driven lemmatiser for the Latin; a token that cannot be
  resolved stays out of the index instead of being guessed;
* root families from scholarly data (BDB roots via the OSHB lexical index, Strong's derivations,
  Lewis & Short etymologies) — a lemma without such data is its own family;
* one verse numbering for every language: the Saints.Bible (Greek/Septuagint) numbering, reached
  through ``studio/lexica/versification.py``, so a Hebrew or Latin word is filed under the verse
  that says the same thing on the site;
* trilingual alignment units only where a curated concept hub links the words (the seven colour
  hubs), with the alignment state computed from the languages that actually match.

The schema of ``studio/concordance.py`` is kept; three additive columns record the gold keys.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from collections import Counter, defaultdict
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .catalog import BOOKS, BOOKS_BY_SLUG, BookSpec

LANG_NAME_TO_CODE = {"hebrew": "heb", "greek": "grc", "latin": "lat"}
POS_MAP = {"ART": "PART"}  # lexical_stems.pos_tag has no ART

# The seven curated colour hubs: which gold lemmas belong to each, and the sense each lemma
# defaults to (sense offsets as seeded by _seed_flagship_trilingual_showcase).
# Lemmas are matched by Strong's number (Hebrew/Greek) or Latin headword.
UNREVIEWED_OFFSET = 64  # the hub sense used when no word of the verse decides the sense

# Members of the seven curated colour hubs: (lang, Strong's number or Latin headword, sense offset or
# None).  A sense offset is given only where the word itself decides the sense (ἄνεμος/ventus 'wind',
# κεφαλή 'head', ἀπαρχή/primitiae 'firstfruit', ἀμήν 'amen' ...).  Words that carry several of the hub's
# senses (דָּבָר, λόγος, רוּחַ, πνεῦμα, נֶפֶשׁ, ψυχή, רֹאשׁ, ἀρχή, ἅγιος ...) have None: a verse whose hub
# words are all of that kind gets the hub's 'sense not yet chosen' row instead of a guessed sense.
# (The first gold build gave every word one default sense; an independent check found about a third of
# the 4,301 hub units wrong for their verse, e.g. 'the wind passes over it' as 'The Spirit of God'.)
# The lists were completed on 18 Nov 2026 with the commonest same-meaning words the check found missing
# (קֹדֶשׁ, κεφαλή, sanctuarium, primitiae, Aramaic רֵאשׁ/רוּחַ ...).
CURATED_HUB_MEMBERS: Dict[str, List[Tuple[str, str, Optional[int]]]] = {
    "ORIGIN_HEAD_START": [
        ("heb", "H7225", None), ("heb", "H7218", None), ("heb", "H8462", 2), ("heb", "H7217", None),
        ("grc", "G0746", None), ("grc", "G0536", 4), ("grc", "G2776", 5),
        ("lat", "principium", 1), ("lat", "initium", 2), ("lat", "primitiae", 4), ("lat", "caput", None),
        ("lat", "princeps", 6),
    ],
    "WORD_LOGOS_SPEECH": [
        ("heb", "H1697", None), ("grc", "G3056", None), ("grc", "G4487", None),
        ("lat", "verbum", None), ("lat", "sermo", None),
    ],
    "SPIRIT_BREATH_WIND": [
        ("heb", "H7307", None), ("heb", "H7308", None), ("heb", "H5397", 2),
        ("grc", "G4151", None), ("grc", "G4157", 2), ("grc", "G0417", 3),
        ("lat", "spiritus", None), ("lat", "ventus", 3), ("lat", "flatus", 2),
    ],
    "LIGHT_DAWN_LAMP": [
        ("heb", "H0216", 1), ("heb", "H3974", None), ("grc", "G5457", 1), ("grc", "G5458", 2),
        ("lat", "lux", 1), ("lat", "lumen", None), ("lat", "luminare", 2),
    ],
    "FAITH_TRUST_AMEN": [
        ("heb", "H0530", 2), ("heb", "H0539", None), ("heb", "H0543", 3),
        ("grc", "G4102", 1), ("grc", "G4100", 1), ("grc", "G4103", 2), ("grc", "G0281", 3),
        ("lat", "fides", 1), ("lat", "credo", 1), ("lat", "fidelis", 2),
    ],
    "LIFE_SOUL_CREATURE": [
        ("heb", "H5315", None), ("grc", "G5590", None), ("grc", "G2222", 3),
        ("lat", "anima", None), ("lat", "vita", 3),
    ],
    "HOLY_SET_APART": [
        ("heb", "H6918", None), ("heb", "H6944", None), ("heb", "H4720", 3),
        ("grc", "G0040", None), ("grc", "G0039", 3),
        ("lat", "sanctus", None), ("lat", "sanctuarium", 3),
    ],
}

# Sense colours that differ from the hub colour in the site key: wind and breath are Creation (red),
# not 'Holy Spirit' (violet).
SENSE_COLOUR_OVERRIDES: Dict[Tuple[str, int], Tuple[str, str]] = {
    ("SPIRIT_BREATH_WIND", 2): ("red", "Creation"),
    ("SPIRIT_BREATH_WIND", 3): ("red", "Creation"),
}

# Colour and theme label of each hub in the site's fixed seven-colour key (saints-verse-themes.php;
# word-studies-2026-11-14/BRIEF.md "use these exact labels").  Chosen 18 Nov 2026 (owner: "apply color")
# from the key and from the colours the site's 6,295 word-study rows already give these words:
# πνεῦμα violet 77/110, πίστις green 49/72, ἅγιος yellow 31/73, λόγος green 27/77 (Teaching/Wisdom),
# φῶς green 13/23, ψυχή green 13/35 (the key lists 'life' under green), ἀρχή 'beginning' = Creation (red).
HUB_KEY: Dict[str, Tuple[str, str]] = {
    "ORIGIN_HEAD_START": ("red", "Creation"),
    "WORD_LOGOS_SPEECH": ("green", "Teaching/Wisdom"),
    "SPIRIT_BREATH_WIND": ("violet", "Holy Spirit"),
    "LIGHT_DAWN_LAMP": ("green", "Salvation"),
    "FAITH_TRUST_AMEN": ("green", "Faith"),
    "LIFE_SOUL_CREATURE": ("green", "Salvation"),
    "HOLY_SET_APART": ("yellow", "Worship"),
}
# The colours the first build gave the hubs (several contradicted the key, e.g. 'beginning' in indigo,
# the key's colour for judgment).  Only hubs still carrying these are recoloured, so a colour a person
# chose in Tab 5 is kept.
_FIRST_BUILD_HUB_COLOURS = {
    "ORIGIN_HEAD_START": "indigo", "WORD_LOGOS_SPEECH": "blue", "SPIRIT_BREATH_WIND": "violet",
    "LIGHT_DAWN_LAMP": "yellow", "FAITH_TRUST_AMEN": "orange", "LIFE_SOUL_CREATURE": "green", "HOLY_SET_APART": "red",
}


def apply_hub_key_colours(conn: sqlite3.Connection) -> Dict[str, str]:
    """Recolour hubs that still have the first build's colours to the site key's colours."""
    changed: Dict[str, str] = {}
    for slug, (colour, _theme) in HUB_KEY.items():
        row = conn.execute("SELECT theme_colour FROM trilingual_concepts WHERE concept_slug = ?", (slug,)).fetchone()
        if not row or row[0] == colour or row[0] != _FIRST_BUILD_HUB_COLOURS.get(slug):
            continue
        conn.execute("UPDATE trilingual_concepts SET theme_colour = ? WHERE concept_slug = ?", (colour, slug))
        conn.execute(
            """INSERT INTO studio_revisions (target_table, target_pk, field_changed, old_val, new_val, actor, review_mode, rationale)
               VALUES ('trilingual_concepts', ?, 'theme_colour', ?, ?, 'concordance_gold_build', 'deterministic', ?)""",
            (slug, row[0], colour, "Site seven-colour key (owner: 'apply color', 18 Nov 2026)"),
        )
        changed[slug] = f"{row[0]} -> {colour}"
    return changed


def refresh_curated_hubs(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Re-apply the curated hub texts (concordance.CURATED_HUBS) to hubs no person has edited, and drop
    the 'contextual_sense' rows the first build's seeder attached to them automatically (e.g. 'profane',
    'wounded' and 'count' under head/beginning, 'subdue' and 'because' under word, 'neck' under soul).
    Hubs touched in Tab 5 (a human_editor revision on the concept or its senses) are left alone."""
    from .concordance import CURATED_HUBS

    report: Dict[str, Any] = {"refreshed": [], "kept_human_edited": [], "auto_senses_removed": 0}
    for slug, eng_base, _colour, note, senses in CURATED_HUBS:
        row = conn.execute("SELECT concept_id FROM trilingual_concepts WHERE concept_slug = ?", (slug,)).fetchone()
        if not row:
            continue
        cid = int(row[0])
        human = conn.execute(
            """SELECT 1 FROM studio_revisions WHERE actor = 'human_editor'
               AND ((target_table = 'saints_senses' AND target_pk LIKE ?) OR (target_table = 'trilingual_concepts' AND target_pk = ?))
               LIMIT 1""",
            (f"{cid}:%", slug),
        ).fetchone()
        if human:
            report["kept_human_edited"].append(slug)
            continue
        conn.execute("UPDATE trilingual_concepts SET eng_base_word = ?, summary_note = ? WHERE concept_id = ?", (eng_base, note, cid))
        for off, word, role, nuance in senses:
            if conn.execute("SELECT 1 FROM saints_senses WHERE concept_id = ? AND sense_offset = ?", (cid, off)).fetchone():
                conn.execute(
                    "UPDATE saints_senses SET base_word = ?, sense_role = ?, usage_nuance = ? WHERE concept_id = ? AND sense_offset = ?",
                    (word, role, nuance, cid, off),
                )
            else:
                conn.execute(
                    "INSERT INTO saints_senses (concept_id, sense_offset, base_word, sense_role, usage_nuance) VALUES (?, ?, ?, ?, ?)",
                    (cid, off, word, role, nuance),
                )
        if not conn.execute("SELECT 1 FROM saints_senses WHERE concept_id = ? AND sense_offset = ?", (cid, UNREVIEWED_OFFSET)).fetchone():
            conn.execute(
                "INSERT INTO saints_senses (concept_id, sense_offset, base_word, sense_role, usage_nuance) VALUES (?, ?, ?, 'unreviewed', ?)",
                (cid, UNREVIEWED_OFFSET, eng_base,
                 "This verse has a word of the hub, but none of its words decides which sense; choose it in Tab 5."),
            )
        for (hslug, off), (colour, _theme) in SENSE_COLOUR_OVERRIDES.items():
            if hslug == slug:
                conn.execute("UPDATE saints_senses SET theme_colour_override = ? WHERE concept_id = ? AND sense_offset = ?",
                             (colour, cid, off))
        cur = conn.execute(
            """DELETE FROM saints_senses WHERE concept_id = ? AND sense_role = 'contextual_sense'
               AND usage_nuance LIKE 'Contextual usage %'
               AND sense_id NOT IN (SELECT sense_id FROM stream_tokens)
               AND sense_id NOT IN (SELECT sense_id FROM trilingual_alignments)
               AND sense_id NOT IN (SELECT default_sense_id FROM stem_concept_links)""",
            (cid,),
        )
        report["auto_senses_removed"] += cur.rowcount
        report["refreshed"].append(slug)
    return report


STREAM_BY_LANG = {"heb": "heb_ot", "arc": "heb_ot", "lat": "lat_bible"}


def _stream_for(lang_code: str, book: BookSpec) -> str:
    if lang_code == "grc":
        return "grc_nt" if book.testament == "NT" else "grc_ot"
    return STREAM_BY_LANG[lang_code]


def _modules() -> Dict[str, Any]:
    from .lexica import greek as lx_grc
    from .lexica import hebrew as lx_heb
    from .lexica import latin as lx_lat
    return {"hebrew": lx_heb, "greek": lx_grc, "latin": lx_lat}


def _versification():
    from .lexica import versification
    return versification


# ---------------------------------------------------------------------------
# Schema additions (additive, idempotent)
# ---------------------------------------------------------------------------

def _lex_concept_slug(lemma_key: str) -> str:
    """Unique concept_slug for a single gold lemma (never collapses non-ASCII Greek keys or
    case-distinct Latin proper names like 'lat:Paulus' vs 'lat:paulus')."""
    if re.fullmatch(r"[HG]\d+[A-Za-z]*", lemma_key):
        return f"LEX_{lemma_key.upper()}"
    base = re.sub(r"[^A-Za-z0-9]+", "_", lemma_key).strip("_").upper()
    if lemma_key.startswith("lat:") and re.fullmatch(r"lat:[a-z0-9_#]+", lemma_key):
        return f"LEX_{base}"
    digest = hashlib.sha1(lemma_key.encode("utf-8")).hexdigest()[:8].upper()
    if lemma_key.startswith("grc:"):
        raw_lemma = re.sub(r"\s+", "_", lemma_key[4:].strip())[:32]
        return f"LEX_GRC_{raw_lemma}_{digest}" if raw_lemma else f"LEX_GRC_{digest}"
    return f"LEX_{base}_{digest}" if base else f"LEX_{digest}"


def ensure_gold_schema(conn: sqlite3.Connection) -> None:
    def cols(table: str) -> set:
        return {str(r[1]) for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}

    if "source_key" not in cols("core_roots"):
        conn.execute("ALTER TABLE core_roots ADD COLUMN source_key TEXT")
    if "root_source" not in cols("core_roots"):
        conn.execute("ALTER TABLE core_roots ADD COLUMN root_source TEXT")
    stem_cols = cols("lexical_stems")
    if "lemma_key" not in stem_cols:
        conn.execute("ALTER TABLE lexical_stems ADD COLUMN lemma_key TEXT")
    if "lemma_source" not in stem_cols:
        conn.execute("ALTER TABLE lexical_stems ADD COLUMN lemma_source TEXT")
    if "is_content" not in stem_cols:
        conn.execute("ALTER TABLE lexical_stems ADD COLUMN is_content INTEGER NOT NULL DEFAULT 1")
    if "translit" not in stem_cols:
        conn.execute("ALTER TABLE lexical_stems ADD COLUMN translit TEXT")
    tok_cols = cols("stream_tokens")
    if "is_content" not in tok_cols:
        conn.execute("ALTER TABLE stream_tokens ADD COLUMN is_content INTEGER NOT NULL DEFAULT 1")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_roots_source_key ON core_roots(lang, source_key) WHERE source_key IS NOT NULL")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_stems_lemma_key ON lexical_stems(lemma_key) WHERE lemma_key IS NOT NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stream_tokens_content ON stream_tokens(is_content, stem_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stems_translit ON lexical_stems(translit) WHERE translit IS NOT NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_roots_translit ON core_roots(translit) WHERE translit IS NOT NULL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS concordance_build_log (
            build_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            scope        TEXT NOT NULL,
            started_at   TEXT NOT NULL,
            seconds      REAL NOT NULL,
            stats_json   TEXT NOT NULL
        )
        """
    )


def _repair_collided_lex_concepts(conn: sqlite3.Connection) -> Dict[str, int]:
    """Unlink stems attached to a collided machine LEX_ concept (e.g. 4,270 Greek 'grc:*' lemmas
    collapsed onto 'LEX_GRC', or capitalised Latin proper names collapsed with lowercase nouns),
    and remove the abandoned LEX_ concepts and senses when nothing references them."""
    stale_links = []
    stale_concepts = set()
    for r in conn.execute(
        """
        SELECT ls.stem_id, ls.lemma_key, scl.concept_id, scl.default_sense_id, tc.concept_slug
        FROM lexical_stems ls
        JOIN stem_concept_links scl ON scl.stem_id = ls.stem_id
        JOIN trilingual_concepts tc ON tc.concept_id = scl.concept_id
        WHERE ls.lemma_key IS NOT NULL
          AND tc.theme_colour IS NULL
          AND tc.concept_slug LIKE 'LEX\\_%' ESCAPE '\\'
        """
    ).fetchall():
        sid, lkey, cid, sense_id, cslug = int(r[0]), str(r[1]), int(r[2]), int(r[3]), str(r[4])
        if cslug != _lex_concept_slug(lkey):
            stale_links.append((sid, cid, sense_id))
            stale_concepts.add(cid)
    unlinked = 0
    for sid, cid, sense_id in stale_links:
        if conn.execute(
            "SELECT 1 FROM stream_tokens WHERE stem_id = ? AND sense_id = ? LIMIT 1", (sid, sense_id)
        ).fetchone():
            continue
        unlinked += conn.execute(
            "DELETE FROM stem_concept_links WHERE stem_id = ? AND concept_id = ?", (sid, cid)
        ).rowcount
    n_s = n_c = 0
    for cid in stale_concepts:
        if conn.execute("SELECT 1 FROM stem_concept_links WHERE concept_id = ? LIMIT 1", (cid,)).fetchone():
            continue
        if conn.execute(
            """SELECT 1 FROM saints_senses ss WHERE ss.concept_id = ?
               AND (ss.sense_id IN (SELECT sense_id FROM stream_tokens)
                 OR ss.sense_id IN (SELECT sense_id FROM trilingual_alignments)) LIMIT 1""",
            (cid,),
        ).fetchone():
            continue
        n_s += conn.execute("DELETE FROM saints_senses WHERE concept_id = ?", (cid,)).rowcount
        n_c += conn.execute("DELETE FROM trilingual_concepts WHERE concept_id = ?", (cid,)).rowcount
    return {"unlinked": unlinked, "senses_removed": n_s, "concepts_removed": n_c}


# ---------------------------------------------------------------------------
# Reset of machine-made rows (human edits are kept)
# ---------------------------------------------------------------------------

def prune_gold_orphans(conn: sqlite3.Connection) -> Dict[str, int]:
    """After a full build: drop gold lemma rows no token, hub or human edit uses any more (lemma keys a
    corrected tagger no longer emits), their machine LEX concepts, and roots no lemma points to."""
    out: Dict[str, int] = {}
    conn.execute(
        """CREATE TEMP TABLE IF NOT EXISTS _dead_stems AS SELECT stem_id FROM lexical_stems WHERE 0"""
    )
    conn.execute("DELETE FROM _dead_stems")
    conn.execute(
        """INSERT INTO _dead_stems
           SELECT ls.stem_id FROM lexical_stems ls
           WHERE ls.lemma_key IS NOT NULL
             AND ls.stem_id NOT IN (SELECT stem_id FROM stream_tokens)
             AND ls.stem_id NOT IN (SELECT scl.stem_id FROM stem_concept_links scl
                                    JOIN trilingual_concepts tc ON tc.concept_id = scl.concept_id
                                    WHERE tc.theme_colour IS NOT NULL)"""
    )
    dead_concepts = [int(r[0]) for r in conn.execute(
        """SELECT DISTINCT scl.concept_id FROM stem_concept_links scl JOIN trilingual_concepts tc ON tc.concept_id = scl.concept_id
           WHERE scl.stem_id IN (SELECT stem_id FROM _dead_stems) AND tc.concept_slug LIKE 'LEX\\_%' ESCAPE '\\'""")]
    out["stem_links"] = conn.execute("DELETE FROM stem_concept_links WHERE stem_id IN (SELECT stem_id FROM _dead_stems)").rowcount
    out["stems"] = conn.execute("DELETE FROM lexical_stems WHERE stem_id IN (SELECT stem_id FROM _dead_stems)").rowcount
    n_s = n_c = 0
    for cid in dead_concepts:
        if conn.execute("SELECT 1 FROM stem_concept_links WHERE concept_id = ? LIMIT 1", (cid,)).fetchone():
            continue
        if conn.execute("""SELECT 1 FROM saints_senses ss WHERE ss.concept_id = ? AND (ss.sense_id IN (SELECT sense_id FROM stream_tokens)
                           OR ss.sense_id IN (SELECT sense_id FROM trilingual_alignments)) LIMIT 1""", (cid,)).fetchone():
            continue
        n_s += conn.execute("DELETE FROM saints_senses WHERE concept_id = ?", (cid,)).rowcount
        n_c += conn.execute("DELETE FROM trilingual_concepts WHERE concept_id = ?", (cid,)).rowcount
    out["lex_senses"], out["lex_concepts"] = n_s, n_c
    out["roots"] = conn.execute(
        """DELETE FROM core_roots WHERE source_key IS NOT NULL
           AND root_id NOT IN (SELECT root_id FROM lexical_stems)
           AND root_id NOT IN (SELECT secondary_root_id FROM lexical_stems WHERE secondary_root_id IS NOT NULL)""").rowcount
    return out


def _human_alignment_ids(conn: sqlite3.Connection) -> set:
    ids = set()
    for r in conn.execute(
        "SELECT target_pk FROM studio_revisions WHERE target_table = 'trilingual_alignments' AND actor = 'human_editor'"
    ).fetchall():
        try:
            ids.add(int(r[0]))
        except (TypeError, ValueError):
            pass
    return ids


def reset_machine_rows(conn: sqlite3.Connection, book_orders: Optional[Sequence[int]] = None) -> Dict[str, int]:
    """Delete machine-made tokens/alignments (all, or those of the given books) and, on a full reset,
    the heuristic lexicon rows of the first build.  Alignments a human edited in Tab 5 (recorded in
    studio_revisions) and their tokens are kept."""
    keep_aligns = _human_alignment_ids(conn)
    keep_slots = set()
    if keep_aligns:
        q = ",".join("?" * len(keep_aligns))
        keep_slots = {int(r[0]) for r in conn.execute(
            f"SELECT slot_id FROM trilingual_alignment_slots WHERE align_id IN ({q})", tuple(keep_aligns)).fetchall()}

    where_anchor = ""
    params: Tuple[Any, ...] = ()
    if book_orders:
        ranges = " OR ".join("(anchor_verse_id BETWEEN ? AND ?)" for _ in book_orders)
        where_anchor = f" AND ({ranges})"
        params = tuple(x for bo in book_orders for x in (bo * 10_000_000, bo * 10_000_000 + 9_999_999))

    conn.execute("CREATE TEMP TABLE IF NOT EXISTS _keep_slots (slot_id INTEGER PRIMARY KEY)")
    conn.execute("DELETE FROM _keep_slots")
    conn.executemany("INSERT OR IGNORE INTO _keep_slots VALUES (?)", [(s,) for s in keep_slots])
    conn.execute("CREATE TEMP TABLE IF NOT EXISTS _keep_aligns (align_id INTEGER PRIMARY KEY)")
    conn.execute("DELETE FROM _keep_aligns")
    conn.executemany("INSERT OR IGNORE INTO _keep_aligns VALUES (?)", [(a,) for a in keep_aligns])

    removed: Dict[str, int] = {}
    cur = conn.execute(
        f"DELETE FROM trilingual_alignment_slots WHERE align_id NOT IN (SELECT align_id FROM _keep_aligns){where_anchor}", params)
    removed["alignment_slots"] = cur.rowcount
    cur = conn.execute(
        f"DELETE FROM trilingual_alignments WHERE align_id NOT IN (SELECT align_id FROM _keep_aligns){where_anchor}", params)
    removed["alignments"] = cur.rowcount
    cur = conn.execute(
        f"""DELETE FROM stream_tokens WHERE slot_id NOT IN (SELECT slot_id FROM _keep_slots)
            AND slot_id IN (SELECT slot_id FROM word_anchors WHERE 1=1{where_anchor})""", params)
    removed["tokens"] = cur.rowcount
    cur = conn.execute(
        f"DELETE FROM word_anchors WHERE slot_id NOT IN (SELECT slot_id FROM _keep_slots){where_anchor}", params)
    removed["word_anchors"] = cur.rowcount

    if not book_orders:
        # Heuristic lexicon of the first build: stems/roots/concepts without gold keys that no kept
        # token uses.  Curated colour hubs (theme_colour set) and their senses stay.
        conn.execute(
            """
            DELETE FROM stem_concept_links
            WHERE stem_id IN (SELECT stem_id FROM lexical_stems WHERE lemma_key IS NULL)
              AND stem_id NOT IN (SELECT stem_id FROM stream_tokens)
            """
        )
        cur = conn.execute(
            "DELETE FROM lexical_stems WHERE lemma_key IS NULL AND stem_id NOT IN (SELECT stem_id FROM stream_tokens)")
        removed["heuristic_stems"] = cur.rowcount
        cur = conn.execute(
            """
            DELETE FROM core_roots WHERE source_key IS NULL
              AND root_id NOT IN (SELECT root_id FROM lexical_stems)
              AND root_id NOT IN (SELECT secondary_root_id FROM lexical_stems WHERE secondary_root_id IS NOT NULL)
            """
        )
        removed["heuristic_roots"] = cur.rowcount
        cur = conn.execute(
            """
            DELETE FROM saints_senses WHERE concept_id IN (
                SELECT concept_id FROM trilingual_concepts
                WHERE theme_colour IS NULL AND concept_slug NOT LIKE 'LEX\\_%' ESCAPE '\\'
                  AND concept_id NOT IN (SELECT concept_id FROM stem_concept_links))
              AND sense_id NOT IN (SELECT sense_id FROM stream_tokens)
              AND sense_id NOT IN (SELECT sense_id FROM trilingual_alignments)
            """
        )
        removed["heuristic_senses"] = cur.rowcount
        cur = conn.execute(
            """
            DELETE FROM trilingual_concepts
            WHERE theme_colour IS NULL AND concept_slug NOT LIKE 'LEX\\_%' ESCAPE '\\'
              AND concept_id NOT IN (SELECT concept_id FROM stem_concept_links)
              AND concept_id NOT IN (SELECT concept_id FROM saints_senses)
            """
        )
        removed["heuristic_concepts"] = cur.rowcount
        cur = conn.execute(
            "DELETE FROM surface_forms WHERE form_id NOT IN (SELECT form_id FROM stream_tokens)")
        removed["surface_forms"] = cur.rowcount
    return removed


# ---------------------------------------------------------------------------
# Lexicon rows for gold lemmas (created lazily for lemmas that occur)
# ---------------------------------------------------------------------------

def _entry_translit(lang: str, text: str) -> Optional[str]:
    """English-friendly Latinized transliteration for Greek/Hebrew/Aramaic entries; None for Latin."""
    if lang not in ("heb", "arc", "grc") or not text:
        return None
    from .translit import transliterate

    tr = transliterate(text, lang).strip()
    return tr[:240] if tr else None


def backfill_transliterations(conn: sqlite3.Connection, force: bool = False) -> Dict[str, int]:
    """Populate ``core_roots.translit`` and ``lexical_stems.translit`` for all Greek/Hebrew/Aramaic rows."""
    ensure_gold_schema(conn)
    cond = "" if force else " AND (translit IS NULL OR TRIM(translit) = '')"
    root_updates = []
    for rid, lang, rkey in conn.execute(
        f"SELECT root_id, lang, root_key FROM core_roots WHERE lang IN ('heb', 'arc', 'grc'){cond}"
    ).fetchall():
        tr = _entry_translit(str(lang), str(rkey or ""))
        if tr:
            root_updates.append((tr, int(rid)))
    if root_updates:
        conn.executemany("UPDATE core_roots SET translit = ? WHERE root_id = ?", root_updates)

    stem_updates = []
    for sid, lang, stem in conn.execute(
        f"SELECT stem_id, lang, canonical_stem FROM lexical_stems WHERE lang IN ('heb', 'arc', 'grc'){cond}"
    ).fetchall():
        tr = _entry_translit(str(lang), str(stem or ""))
        if tr:
            stem_updates.append((tr, int(sid)))
    if stem_updates:
        conn.executemany("UPDATE lexical_stems SET translit = ? WHERE stem_id = ?", stem_updates)
    return {"roots_updated": len(root_updates), "stems_updated": len(stem_updates)}


class _LexiconWriter:
    def __init__(self, conn: sqlite3.Connection, lexicons: Dict[str, Dict[str, Any]]):
        self.conn = conn
        self.lexicons = lexicons  # lang name -> {lemma_key: LemmaEntry}
        self.root_ids: Dict[Tuple[str, str], int] = {
            (str(r[0]), str(r[1])): int(r[2])
            for r in conn.execute("SELECT lang, source_key, root_id FROM core_roots WHERE source_key IS NOT NULL")
        }
        self.stem_ids: Dict[str, Tuple[int, int, int]] = {}
        for r in conn.execute(
            """
            SELECT ls.lemma_key, ls.stem_id, scl.concept_id, scl.default_sense_id, tc.concept_slug
            FROM lexical_stems ls
            JOIN stem_concept_links scl ON scl.stem_id = ls.stem_id
            JOIN trilingual_concepts tc ON tc.concept_id = scl.concept_id
            WHERE ls.lemma_key IS NOT NULL AND tc.concept_slug LIKE 'LEX\\_%' ESCAPE '\\'
            """
        ):
            lkey = str(r[0])
            if str(r[4]) == _lex_concept_slug(lkey):
                self.stem_ids[lkey] = (int(r[1]), int(r[2]), int(r[3]))
        self.used_root_labels: Dict[Tuple[str, str], int] = {}
        for r in conn.execute("SELECT lang, root_key, MAX(homograph_no) FROM core_roots GROUP BY lang, root_key"):
            self.used_root_labels[(str(r[0]), str(r[1]))] = int(r[2])
        # Rows kept from an earlier build are refreshed from the current lexicon the first time this build
        # meets them (glosses, families, formulas and labels change when a tagger is corrected).
        self.fresh_roots: set = set()
        self.fresh_stems: set = set()

    def _refresh_root(self, rid: int, lang: str, e: Any) -> None:
        label = (e.root_label or e.root_key).strip() or e.root_key
        idea = (e.root_gloss or e.gloss or label)[:240]
        tr = _entry_translit(lang, label)
        row = self.conn.execute("SELECT root_key FROM core_roots WHERE root_id = ?", (rid,)).fetchone()
        if row and str(row[0]) != label:
            hom = self.used_root_labels.get((lang, label), 0) + 1
            self.used_root_labels[(lang, label)] = hom
            self.conn.execute("UPDATE core_roots SET root_key = ?, homograph_no = ? WHERE root_id = ?", (label, hom, rid))
        self.conn.execute("UPDATE core_roots SET translit = ?, core_idea = ?, root_source = ? WHERE root_id = ?", (tr, idea, e.root_source, rid))

    def _root_id(self, e: Any) -> int:
        lang = "arc" if e.lang == "arc" else e.lang
        key = (lang, e.root_key)
        if key in self.root_ids:
            rid = self.root_ids[key]
            if key not in self.fresh_roots:
                self._refresh_root(rid, lang, e)
                self.fresh_roots.add(key)
            return rid
        self.fresh_roots.add(key)
        label = (e.root_label or e.root_key).strip() or e.root_key
        hom = self.used_root_labels.get((lang, label), 0) + 1
        self.used_root_labels[(lang, label)] = hom
        tr = _entry_translit(lang, label)
        cur = self.conn.execute(
            "INSERT INTO core_roots (lang, root_key, homograph_no, translit, core_idea, source_key, root_source) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (lang, label, hom, tr, (e.root_gloss or e.gloss or label)[:240], e.root_key, e.root_source),
        )
        rid = int(cur.lastrowid)
        self.root_ids[key] = rid
        return rid

    def _refresh_stem(self, hit: Tuple[int, int, int], e: Any, is_content: Optional[bool] = None) -> None:
        sid, cid, sense = hit
        rid = self._root_id(e)
        pos = POS_MAP.get(e.pos, e.pos)
        if pos not in ("N", "V", "ADJ", "ADV", "PRON", "PREP", "CONJ", "PART", "NUM", "INTERJ", "PROPN"):
            pos = "PART"
        tr = _entry_translit(e.lang, e.lemma)
        if is_content is None:
            self.conn.execute(
                """UPDATE lexical_stems SET root_id = ?, canonical_stem = ?, pos_tag = ?, structural_formula = ?,
                   base_gloss = ?, lemma_source = ?, translit = ? WHERE stem_id = ?""",
                (rid, e.lemma, pos, e.formula or None, (e.gloss or e.lemma)[:240], e.source, tr, sid),
            )
        else:
            self.conn.execute(
                """UPDATE lexical_stems SET root_id = ?, canonical_stem = ?, pos_tag = ?, structural_formula = ?,
                   base_gloss = ?, lemma_source = ?, is_content = ?, translit = ? WHERE stem_id = ?""",
                (rid, e.lemma, pos, e.formula or None, (e.gloss or e.lemma)[:240], e.source,
                 1 if is_content else 0, tr, sid),
            )
        note = f"{e.lemma} ({e.strongs or e.lemma_key}) — family {e.root_label or e.root_key}"
        if e.root_gloss:
            note += f": {e.root_gloss}"
        note += f". Lemma source: {e.source}; family source: {e.root_source}."
        self.conn.execute(
            "UPDATE trilingual_concepts SET eng_base_word = ?, summary_note = ? WHERE concept_id = ? AND theme_colour IS NULL",
            ((e.gloss or e.lemma)[:120], note, cid),
        )
        self.conn.execute(
            """UPDATE saints_senses SET base_word = ?, usage_nuance = ?
               WHERE sense_id = ? AND sense_role = 'primary_sense' AND concept_id = ?""",
            ((e.gloss or e.lemma)[:120], f"Lexical gloss of {e.lemma} ({e.source})", sense, cid),
        )

    def stem_for(self, lemma_key: str, lang_name: str, is_content: Optional[bool] = None) -> Optional[Tuple[int, int, int]]:
        """(stem_id, concept_id, default_sense_id) for a gold lemma, created on first use."""
        hit = self.stem_ids.get(lemma_key)
        if hit and lemma_key in self.fresh_stems:
            return hit
        e = self.lexicons[lang_name].get(lemma_key)
        if e is None:
            return hit
        if hit:
            self._refresh_stem(hit, e, is_content=is_content)
            self.fresh_stems.add(lemma_key)
            return hit
        self.fresh_stems.add(lemma_key)
        rid = self._root_id(e)
        pos = POS_MAP.get(e.pos, e.pos)
        if pos not in ("N", "V", "ADJ", "ADV", "PRON", "PREP", "CONJ", "PART", "NUM", "INTERJ", "PROPN"):
            pos = "PART"
        ic_val = 1 if (is_content is None or is_content) else 0
        tr = _entry_translit(e.lang, e.lemma)
        row = self.conn.execute("SELECT stem_id FROM lexical_stems WHERE lemma_key = ?", (lemma_key,)).fetchone()
        if not row:
            # A row left by an older build with the same identity: adopt it rather than collide.
            row = self.conn.execute(
                """SELECT stem_id FROM lexical_stems WHERE lemma_key IS NULL AND lang = ? AND canonical_stem = ?
                   AND pos_tag = ? AND COALESCE(ext_strongs, '') = COALESCE(?, '')""",
                (e.lang, e.lemma, pos, lemma_key),
            ).fetchone()
            if row:
                self.conn.execute(
                    """UPDATE lexical_stems SET root_id = ?, secondary_root_id = NULL, affix_bundle_id = NULL,
                       stem_pattern_morph_id = NULL, deriv_suffix_morph_id = NULL, structural_formula = ?,
                       base_gloss = ?, lemma_key = ?, lemma_source = ?, is_content = ?, translit = ? WHERE stem_id = ?""",
                    (rid, e.formula or None, (e.gloss or e.lemma)[:240], lemma_key, e.source, ic_val, tr, int(row[0])),
                )
        if row:
            sid = int(row[0])
            self.conn.execute(
                """UPDATE lexical_stems SET root_id = ?, canonical_stem = ?, pos_tag = ?, structural_formula = ?,
                   base_gloss = ?, lemma_source = ?, is_content = ?, translit = ? WHERE stem_id = ?""",
                (rid, e.lemma, pos, e.formula or None, (e.gloss or e.lemma)[:240], e.source, ic_val, tr, sid),
            )
        else:
            cur = self.conn.execute(
                """
                INSERT INTO lexical_stems (lang, root_id, canonical_stem, pos_tag, ext_strongs,
                                           structural_formula, base_gloss, lemma_key, lemma_source, is_content, translit)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (e.lang, rid, e.lemma, pos, lemma_key, e.formula or None,
                 (e.gloss or e.lemma)[:240], lemma_key, e.source, ic_val, tr),
            )
            sid = int(cur.lastrowid)
        slug = _lex_concept_slug(lemma_key)
        crow = self.conn.execute("SELECT concept_id FROM trilingual_concepts WHERE concept_slug = ?", (slug,)).fetchone()
        if crow:
            cid = int(crow[0])
        else:
            note = f"{e.lemma} ({e.strongs or lemma_key}) — family {e.root_label or e.root_key}"
            if e.root_gloss:
                note += f": {e.root_gloss}"
            note += f". Lemma source: {e.source}; family source: {e.root_source}."
            cid = int(self.conn.execute(
                "INSERT INTO trilingual_concepts (concept_slug, eng_base_word, theme_colour, summary_note) VALUES (?, ?, NULL, ?)",
                (slug, (e.gloss or e.lemma)[:120], note),
            ).lastrowid)
        srow = self.conn.execute("SELECT sense_id FROM saints_senses WHERE concept_id = ? AND sense_offset = 1", (cid,)).fetchone()
        if srow:
            sense = int(srow[0])
        else:
            sense = int(self.conn.execute(
                "INSERT INTO saints_senses (concept_id, sense_offset, base_word, sense_role, usage_nuance) VALUES (?, 1, ?, 'primary_sense', ?)",
                (cid, (e.gloss or e.lemma)[:120], f"Lexical gloss of {e.lemma} ({e.source})"),
            ).lastrowid)
        self.conn.execute(
            "INSERT OR IGNORE INTO stem_concept_links (stem_id, concept_id, default_sense_id, link_weight) VALUES (?, ?, ?, 1.0)",
            (sid, cid, sense),
        )
        self.stem_ids[lemma_key] = (sid, cid, sense)
        return self.stem_ids[lemma_key]


# ---------------------------------------------------------------------------
# Curated hubs -> gold stems
# ---------------------------------------------------------------------------

def _lemma_index(lexicons: Dict[str, Dict[str, Any]]) -> Dict[Tuple[str, str], str]:
    """(lang, strongs-or-latin-headword) -> lemma_key."""
    idx: Dict[Tuple[str, str], str] = {}
    for lang_name, lex in lexicons.items():
        code = LANG_NAME_TO_CODE[lang_name]
        for key, e in lex.items():
            if e.strongs:
                s = str(e.strongs).upper()
                m = re.match(r"^([HG])0*(\d+)", s)
                if m:
                    norm = f"{m.group(1)}{int(m.group(2)):04d}"
                    idx.setdefault((code, norm), key)
            if code == "lat":
                idx.setdefault((code, str(e.lemma).lower()), key)
    return idx


def link_curated_hubs(conn: sqlite3.Connection, writer: _LexiconWriter,
                      lexicons: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Point the seven curated colour hubs at the gold stems of their member lemmas.  Returns
    {stem_id: [(concept_id, sense_id, decides_sense)]} for alignment building, plus a report."""
    idx = _lemma_index(lexicons)
    lang_name = {"heb": "hebrew", "grc": "greek", "lat": "latin"}
    hub_stems: Dict[int, List[Tuple[int, int, bool]]] = defaultdict(list)
    missing: List[str] = []
    for slug, members in CURATED_HUB_MEMBERS.items():
        row = conn.execute("SELECT concept_id FROM trilingual_concepts WHERE concept_slug = ?", (slug,)).fetchone()
        if not row:
            missing.append(f"hub {slug} not in DB")
            continue
        cid = int(row[0])
        senses = {int(r[0]): int(r[1]) for r in conn.execute(
            "SELECT sense_offset, sense_id FROM saints_senses WHERE concept_id = ?", (cid,))}
        unreviewed = senses.get(UNREVIEWED_OFFSET) or senses.get(1)
        for lang, key, off in members:
            norm = key.lower() if lang == "lat" else key
            lemma_key = idx.get((lang, norm))
            if not lemma_key:
                missing.append(f"{slug}: {lang} {key} not in the {lang_name[lang]} lexicon")
                continue
            hit = writer.stem_for(lemma_key, lang_name[lang])
            if not hit:
                missing.append(f"{slug}: {lang} {key} -> {lemma_key} has no lexicon entry")
                continue
            decides = off is not None and off in senses
            sense = senses[off] if decides else unreviewed
            conn.execute(
                "INSERT OR REPLACE INTO stem_concept_links (stem_id, concept_id, default_sense_id, link_weight) VALUES (?, ?, ?, 1.0)",
                (hit[0], cid, sense),
            )
            hub_stems[hit[0]].append((cid, sense, decides))
    return {"hub_stems": hub_stems, "missing": missing}


# ---------------------------------------------------------------------------
# The build
# ---------------------------------------------------------------------------

def build_gold_concordance(
    conn: sqlite3.Connection,
    book_slug: Optional[str] = None,
    max_chapters: int = 0,
    languages: Sequence[str] = ("hebrew", "greek", "latin"),
    progress: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Tag the saved critical texts with gold lemmas, file every token under its Saints.Bible verse,
    and rebuild the alignments and postings.  ``book_slug`` limits the run to one book;
    ``max_chapters`` (testing) to the first N Saints chapters of the selection."""
    from .concordance import (
        _ensure_affix_bundle,
        _morph_id,
        format_saints_ref,
        init_concordance_schema,
        make_anchor_verse_id,
        rebuild_concordance_postings,
    )

    t0 = time.time()
    say = progress or (lambda _m: None)
    init_concordance_schema(conn)
    ensure_gold_schema(conn)
    mods = _modules()
    vs = _versification()

    say("Loading lexicons")
    # Shallow-copy Latin only so dynamic verse-attested parallel PROPNs never mutate cached latin._LEXICON,
    # while keeping Greek's live dict reference so glaux.fill_untagged_lemmas() additions stay visible.
    lexicons = {
        name: (dict(mods[name].load_lexicon()) if name == "latin" else mods[name].load_lexicon())
        for name in languages
    }
    # Hub linking needs every language's lexicon even on a one-language run.
    for name in ("hebrew", "greek", "latin"):
        if name not in lexicons:
            lexicons[name] = dict(mods[name].load_lexicon()) if name == "latin" else mods[name].load_lexicon()

    books = [BOOKS_BY_SLUG[book_slug]] if book_slug else list(BOOKS)
    book_orders = [b.order for b in books] if book_slug else None
    # Rows of the first (heuristic) build anywhere in the database are removed on the first gold run,
    # even a one-book run: they were wrong in every book and their stems would collide with gold ones.
    heuristic_left = int(conn.execute("SELECT COUNT(*) FROM lexical_stems WHERE lemma_key IS NULL").fetchone()[0])
    say("Removing machine-made rows")
    removed = reset_machine_rows(conn, None if heuristic_left else book_orders)
    repaired_lex = _repair_collided_lex_concepts(conn)

    hub_colours_changed = apply_hub_key_colours(conn)
    hub_texts = refresh_curated_hubs(conn)
    writer = _LexiconWriter(conn, lexicons)
    hubs = link_curated_hubs(conn, writer, lexicons)
    hub_stems: Dict[int, List[Tuple[int, int, bool]]] = hubs["hub_stems"]

    word_morph = {"heb": _morph_id(conn, "heb", "H:WORD"), "arc": _morph_id(conn, "arc", "A:WORD"),
                  "grc": _morph_id(conn, "grc", "G:WORD"), "lat": _morph_id(conn, "lat", "L:WORD")}
    eng_sg = _morph_id(conn, "eng", "ENG:SG")
    morph_cache: Dict[Tuple[str, str], int] = {
        (str(r[0]), str(r[1])): int(r[2])
        for r in conn.execute("SELECT lang, morph_code, morph_id FROM morpheme_catalog")
    }
    try:
        from .lexica import glaux as _glaux_mod
        glaux_mod = _glaux_mod if _glaux_mod.corpus_available() else None
    except Exception:
        glaux_mod = None
    lat_morph_legend: Optional[Dict[str, str]] = None

    def _describe_morph(code: str, morph_code: str) -> str:
        nonlocal lat_morph_legend
        if morph_code.startswith("O:"):
            return mods["hebrew"].morph_description(morph_code) or morph_code
        if morph_code.startswith("R:"):
            return mods["greek"].morph_legend([morph_code]).get(morph_code) or morph_code
        if morph_code.startswith("A:") and glaux_mod is not None:
            return glaux_mod.describe_postag(morph_code) or morph_code
        if morph_code.startswith("L:"):
            if lat_morph_legend is None:
                lat_morph_legend = mods["latin"].morph_legend()
            if morph_code in lat_morph_legend:
                return lat_morph_legend[morph_code]
            if "," in morph_code:
                parts = [p if p.startswith("L:") else "L:" + p for p in morph_code.split(",")]
                texts = [lat_morph_legend.get(p, "") for p in parts]
                if any(texts):
                    return " | ".join(t or p for t, p in zip(texts, parts))
        return morph_code

    def morph_id_for(code: str, morph_code: Optional[str]) -> int:
        if not morph_code:
            return word_morph.get(code, word_morph["heb"])
        k = (code, morph_code)
        mid = morph_cache.get(k)
        if mid is None:
            desc = _describe_morph(code, morph_code)[:320]
            cur = conn.execute(
                "INSERT INTO morpheme_catalog (lang, morph_slot, morph_code, affix_form, grammatical_fn) VALUES (?, 'inflection', ?, NULL, ?)",
                (code, morph_code, desc),
            )
            mid = int(cur.lastrowid)
            morph_cache[k] = mid
        return mid

    bundle_cache: Dict[Tuple[str, Tuple[str, ...]], int] = {}
    form_cache: Dict[Tuple[str, str], int] = {
        (str(r[0]), str(r[1])): int(r[2]) for r in conn.execute("SELECT lang, surface_text, form_id FROM surface_forms")
    }

    def bundle(lang: str, codes: Tuple[str, ...]) -> int:
        if not codes:
            return 0
        k = (lang, codes)
        if k not in bundle_cache:
            bundle_cache[k] = _ensure_affix_bundle(conn, lang, list(codes))
        return bundle_cache[k]

    from .lexica import greek_bare, hebrew_consonants, latin_bare

    def form_id(lang: str, surface: str) -> int:
        k = (lang, surface)
        fid = form_cache.get(k)
        if fid is None:
            if lang in ("heb", "arc"):
                bare = hebrew_consonants(surface)
            elif lang == "grc":
                bare = greek_bare(surface)
            else:
                bare = latin_bare(surface)
            fid = int(conn.execute(
                "INSERT INTO surface_forms (lang, surface_text, bare_lookup_key) VALUES (?, ?, ?)",
                (lang, surface, bare or surface.lower()),
            ).lastrowid)
            form_cache[k] = fid
        return fid

    existing_anchors = {int(r[0]) for r in conn.execute("SELECT anchor_verse_id FROM versification_anchors")}
    # Words of alignments a person edited survive the reset; do not index them a second time.
    kept_words = {(int(r[0]), str(r[1]), int(r[2])) for r in conn.execute(
        "SELECT wa.anchor_verse_id, wa.lang_stream, st.stem_id FROM word_anchors wa JOIN stream_tokens st ON st.slot_id = wa.slot_id")}
    anchor_rows: Dict[int, Dict[str, Any]] = {}
    occupied = {(int(r[0]), str(r[1]), int(r[2])) for r in conn.execute(
        "SELECT anchor_verse_id, lang_stream, slot_seq FROM word_anchors")}

    stats: Dict[str, Any] = {"removed": removed, "repaired_lex_concepts": repaired_lex,
                             "hub_links_missing": hubs["missing"],
                             "hub_colours_changed": hub_colours_changed, "hub_texts": hub_texts, "languages": {}}
    next_slot = int(conn.execute("SELECT COALESCE(MAX(slot_id), 0) FROM word_anchors").fetchone()[0]) + 1
    # verse -> per stream -> list of (slot_id, stem_id)
    verse_hits: Dict[int, Dict[str, List[Tuple[int, int]]]] = defaultdict(lambda: defaultdict(list))

    for lang_name in languages:
        mod = mods[lang_name]
        lstat = Counter()
        unmapped_examples: List[str] = []
        sql = "SELECT id, book_slug, chapter FROM chapters WHERE language = ?"
        params: List[Any] = [lang_name]
        if book_slug:
            sql += " AND book_slug = ?"
            params.append(book_slug)
        sql += " ORDER BY book_slug, chapter"
        chapters = conn.execute(sql, params).fetchall()
        if max_chapters > 0:
            chapters = chapters[:max_chapters]
        say(f"Tagging {lang_name}: {len(chapters)} chapters")
        wa_rows: List[Tuple[int, int, str, int]] = []
        st_rows: List[Tuple[int, int, int, int, int, int, int, int]] = []

        # Group chapters by book so Greek OT books can be aligned to GLAUx once per book.
        chapters_by_book: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
        book_order_seen: List[str] = []
        for ch_row in chapters:
            slug = str(ch_row[1])
            if slug not in BOOKS_BY_SLUG:
                continue
            if slug not in chapters_by_book:
                book_order_seen.append(slug)
            chapters_by_book[slug].append((int(ch_row[0]), int(ch_row[2])))

        def _emit_verse_tokens(book: BookSpec, avid: int, tags: Sequence[Any]) -> None:
            nonlocal next_slot
            for t in tags:
                if t.lemma_key is None:
                    lstat["untagged"] += 1
                    continue
                is_cont = bool(t.is_content)
                e = lexicons[lang_name].get(t.lemma_key)
                if e is None:
                    lstat["lemma_missing_from_lexicon"] += 1
                    continue
                hit = writer.stem_for(t.lemma_key, lang_name, is_content=is_cont)
                if hit is None:
                    lstat["lemma_missing_from_lexicon"] += 1
                    continue
                stem_id, _cid, sense_id = hit
                code = e.lang
                stream = _stream_for("grc" if code == "grc" else code, book)
                if (avid, stream, stem_id) in kept_words:
                    kept_words.discard((avid, stream, stem_id))
                    lstat["kept_human_edited"] += 1
                    continue
                seq = t.index * 10
                while (avid, stream, seq) in occupied:
                    seq += 1  # two source verses filed under one Saints verse
                occupied.add((avid, stream, seq))
                slot = next_slot
                next_slot += 1
                tmorph = getattr(t, "morph", None)
                wa_rows.append((slot, avid, stream, seq))
                st_rows.append((slot, form_id(code, t.surface), bundle(code, tuple(t.prefixes)), stem_id,
                                morph_id_for(code, tmorph), sense_id, eng_sg, 1 if is_cont else 0))
                if is_cont:
                    verse_hits[avid][stream].append((slot, stem_id))
                    lstat["content_words"] += 1
                else:
                    lstat["function_words"] += 1
                if tmorph:
                    lstat["with_morph"] += 1
                lstat["indexed"] += 1
                lstat[f"method:{t.method}"] += 1

        pending_lat_verses: List[Tuple[BookSpec, int, str, List[Any]]] = []

        for slug in book_order_seen:
            book = BOOKS_BY_SLUG[slug]
            book_texts: Dict[int, Dict[int, str]] = {}
            for ch_id, ch in chapters_by_book[slug]:
                verses = {int(v[0]): str(v[1] or "") for v in conn.execute(
                    "SELECT verse, critical_text FROM verses WHERE chapter_id = ? ORDER BY verse", (ch_id,))}
                verses = {v: t for v, t in verses.items() if t.strip()}
                if verses:
                    book_texts[ch] = verses
            use_glaux = (
                glaux_mod is not None
                and lang_name == "greek"
                and book.testament != "NT"
                and slug in glaux_mod.BOOK_FILES
                and bool(book_texts)
            )
            for ch in sorted(book_texts):
                verses = book_texts[ch]
                tagged = mod.tag_chapter(slug, ch, verses)
                if use_glaux:
                    glaux_mod.fill_untagged_lemmas(slug, ch, tagged, book_texts)
                    glaux_mod.fill_chapter(slug, ch, tagged, book_texts)
                for vnum, tags in tagged.items():
                    targets = [(book.order, c, v) for (c, v) in (vs.to_saints(lang_name, slug, ch, vnum) or [])]
                    lstat["tokens"] += len(tags)
                    if targets:
                        # A source verse mapped to several Saints verses is filed under the first (its words are
                        # not split); the others are recorded in the anchor's ref columns.
                        bo, sc, sv = targets[0]
                        sub = 0
                    else:
                        extra = vs.to_extra_site_anchor(lang_name, slug, ch, vnum)
                        if extra is None:
                            if vs.is_duplicate_or_placeholder(lang_name, slug, ch, vnum):
                                lstat["skipped_duplicate_verses"] += 1
                                lstat["tokens_in_duplicate_verses"] += len(tags)
                            else:
                                lstat["tokens_in_unmapped_verses"] += len(tags)
                                lstat["unmapped_verses"] += 1
                                if len(unmapped_examples) < 40:
                                    unmapped_examples.append(f"{slug} {ch}:{vnum}")
                            continue
                        bo, sc, sv = book.order, extra[0], extra[1]
                        sub = vs.EXTRA_SITE_SUBVERSE
                        lstat["extra_site_verses"] += 1
                    lstat["verses"] += 1
                    try:
                        avid = make_anchor_verse_id(bo, sc, sv, sub)
                    except ValueError:
                        lstat["tokens_out_of_range"] += len(tags)
                        continue
                    src_ref = f"{book.usfm_code.title()}.{ch}.{vnum}"
                    ar = anchor_rows.setdefault(
                        avid, {"book": book, "ch": sc, "v": sv, "sub": sub, "heb": [], "grc": [], "lat": []}
                    )
                    ar[LANG_NAME_TO_CODE[lang_name]].append(src_ref)
                    if lang_name == "latin":
                        pending_lat_verses.append((book, avid, verses.get(vnum, ""), tags))
                    else:
                        _emit_verse_tokens(book, avid, tags)

        if lang_name == "latin" and pending_lat_verses:
            from .lexica import latin_parallel as _lp
            par_grc, par_heb = _lp.load_parallel_verses(conn)
            if par_grc or par_heb:
                say("Disambiguating untagged Latin against parallel Greek/Hebrew verses")
                tagged_by_avid: Dict[int, List[Tuple[str, List[Any]]]] = defaultdict(list)
                for _book, avid, vtext, tags in pending_lat_verses:
                    tagged_by_avid[avid].append((vtext, tags))
                existing_lat = _lp.load_existing_latin_lemmas(conn) if (book_slug or max_chapters > 0) else None
                dis = _lp.ParallelDisambiguator(par_grc, par_heb, lexicons["latin"])
                dis.fit_from_verses(tagged_by_avid, existing_lat)
                par_resolved = 0
                for _book, avid, vtext, tags in pending_lat_verses:
                    par_resolved += dis.disambiguate_verse(avid, tags, vtext)
                lstat["parallel_resolved"] = par_resolved
                for k, cnt in dis.stats.items():
                    lstat[f"parallel:{k}"] = int(cnt)
            for book, avid, _vtext, tags in pending_lat_verses:
                _emit_verse_tokens(book, avid, tags)
        # anchors first (FK)
        new_anchor_rows = []
        for avid, ar in anchor_rows.items():
            if avid in existing_anchors:
                continue
            existing_anchors.add(avid)
            b = ar["book"]
            sub = int(ar.get("sub", 0))
            sref = format_saints_ref(b, ar["ch"], ar["v"], 0) + ("*" if sub == vs.EXTRA_SITE_SUBVERSE else "")
            new_anchor_rows.append((
                avid, b.order, ar["ch"], ar["v"], sub, sref,
                ",".join(ar["heb"]) or None, ",".join(ar["grc"]) or None, ",".join(ar["lat"]) or None,
            ))
        conn.executemany(
            """INSERT OR IGNORE INTO versification_anchors
               (anchor_verse_id, book_order, chapter, verse, subverse, saints_ref, heb_ref, grc_ref, lat_ref)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            new_anchor_rows,
        )
        conn.executemany("INSERT INTO word_anchors (slot_id, anchor_verse_id, lang_stream, slot_seq) VALUES (?, ?, ?, ?)", wa_rows)
        conn.executemany(
            """INSERT INTO stream_tokens (slot_id, form_id, affix_bundle_id, stem_id, infl_morph_id,
                                          sense_id, eng_infl_morph_id, is_content, review_status, human_locked)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'auto', 0)""",
            st_rows,
        )
        lstat_d = dict(lstat)
        tok = max(lstat.get("tokens", 0), 1)
        idx_tok = max(lstat.get("indexed", 0), 1)
        lstat_d["indexed_share_of_tokens"] = round(lstat.get("indexed", 0) / tok, 4)
        lstat_d["content_share_of_tokens"] = round(lstat.get("content_words", 0) / tok, 4)
        lstat_d["morph_share_of_indexed"] = round(lstat.get("with_morph", 0) / idx_tok, 4)
        lstat_d["untagged_share_of_tokens"] = round(lstat.get("untagged", 0) / tok, 4)
        lstat_d["unmapped_examples"] = unmapped_examples
        stats["languages"][lang_name] = lstat_d

    # Refresh the source-ref columns of anchors that already existed
    for avid, ar in anchor_rows.items():
        conn.execute(
            "UPDATE versification_anchors SET heb_ref = ?, grc_ref = ?, lat_ref = ? WHERE anchor_verse_id = ?",
            (",".join(ar["heb"]) or None, ",".join(ar["grc"]) or None, ",".join(ar["lat"]) or None, avid),
        )

    if not book_slug:
        stats["pruned"] = prune_gold_orphans(conn)
    say("Building curated-hub alignments")
    stats["alignments"] = _build_hub_alignments(conn, verse_hits, hub_stems, eng_sg)
    say("Rebuilding postings")
    stats["postings"] = rebuild_concordance_postings(conn)
    stats["usage"] = _usage_aggregates(conn)
    stats["corpus_coverage"] = _corpus_coverage(conn)
    stats["seconds"] = round(time.time() - t0, 1)
    conn.execute(
        "INSERT INTO concordance_build_log (scope, started_at, seconds, stats_json) VALUES (?, strftime('%Y-%m-%dT%H:%M:%SZ','now'), ?, ?)",
        (book_slug or "all", stats["seconds"], json.dumps(stats, ensure_ascii=False, default=str)),
    )
    conn.execute(
        """
        INSERT INTO studio_revisions (target_table, target_pk, field_changed, old_val, new_val, actor, review_mode, rationale)
        VALUES ('stream_tokens', ?, 'gold_index', NULL, ?, 'concordance_gold_build', 'deterministic', ?)
        """,
        (book_slug or "all", json.dumps({k: v.get("indexed", 0) for k, v in stats["languages"].items()}),
         "Lemma tags from OSHB / STEPBible TAGNT / Open Scriptures LXX lemmas / Lewis & Short lemmatiser; Saints.Bible verse numbering."),
    )
    return stats


# ---------------------------------------------------------------------------
# Measured statistics (no projections)
# ---------------------------------------------------------------------------

def _usage_aggregates(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Whole-table aggregates (a few seconds on ~1.5M tokens): computed once per build and stored in
    the build log, so Tab 5 does not recount them on every refresh."""
    by_stream = {str(r[0]): int(r[1]) for r in conn.execute(
        "SELECT wa.lang_stream, COUNT(*) FROM stream_tokens st JOIN word_anchors wa ON wa.slot_id = st.slot_id GROUP BY wa.lang_stream")}
    by_content = {int(r[0]): int(r[1]) for r in conn.execute(
        "SELECT is_content, COUNT(*) FROM stream_tokens GROUP BY is_content")}
    lemmas_used = {str(r[0]): int(r[1]) for r in conn.execute(
        "SELECT ls.lang, COUNT(DISTINCT ls.stem_id) FROM stream_tokens st JOIN lexical_stems ls ON ls.stem_id = st.stem_id GROUP BY ls.lang")}
    roots_used = {str(r[0]): int(r[1]) for r in conn.execute(
        """SELECT cr.lang, COUNT(DISTINCT cr.root_id) FROM stream_tokens st
           JOIN lexical_stems ls ON ls.stem_id = st.stem_id JOIN core_roots cr ON cr.root_id = ls.root_id GROUP BY cr.lang""")}
    forms_used = {str(r[0]): int(r[1]) for r in conn.execute(
        "SELECT sf.lang, COUNT(DISTINCT sf.form_id) FROM stream_tokens st JOIN surface_forms sf ON sf.form_id = st.form_id GROUP BY sf.lang")}
    return {
        "tokens_by_stream": by_stream,
        "tokens_total": sum(by_stream.values()),
        "content_tokens_total": by_content.get(1, 0),
        "function_tokens_total": by_content.get(0, 0),
        "lemmas_used_by_lang": lemmas_used,
        "roots_used_by_lang": roots_used,
        "surface_forms_used_by_lang": forms_used,
    }


def _corpus_coverage(conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
    """Measure full-corpus coverage across all saved critical texts and indexed ``stream_tokens``
    directly from live database tables (never from a single-book build-log entry)."""
    from .concordance import make_anchor_verse_id
    from .lexica import tokenize_verse

    vs = _versification()

    # 1. Live indexed-token totals grouped by language from stream_tokens + word_anchors
    indexed_by_lang: Dict[str, Dict[str, int]] = {}
    for r in conn.execute(
        """
        SELECT
            CASE wa.lang_stream
                WHEN 'heb_ot' THEN 'hebrew'
                WHEN 'grc_ot' THEN 'greek'
                WHEN 'grc_nt' THEN 'greek'
                WHEN 'lat_bible' THEN 'latin'
                ELSE wa.lang_stream
            END AS lang_grp,
            COUNT(*) AS indexed,
            SUM(CASE WHEN st.is_content = 1 THEN 1 ELSE 0 END) AS content_words,
            SUM(CASE WHEN st.is_content = 0 THEN 1 ELSE 0 END) AS function_words,
            SUM(CASE WHEN mc.morph_code IS NOT NULL
                      AND mc.morph_code NOT IN ('H:WORD', 'A:WORD', 'G:WORD', 'L:WORD')
                     THEN 1 ELSE 0 END) AS with_morph
        FROM stream_tokens st
        JOIN word_anchors wa ON wa.slot_id = st.slot_id
        LEFT JOIN morpheme_catalog mc ON mc.morph_id = st.infl_morph_id
        GROUP BY lang_grp
        """
    ):
        indexed_by_lang[str(r[0])] = {
            "indexed": int(r[1] or 0),
            "content_words": int(r[2] or 0),
            "function_words": int(r[3] or 0),
            "with_morph": int(r[4] or 0),
        }

    # 2. Live critical-text token & verse counts across the full saved corpus
    text_by_lang: Dict[str, Dict[str, int]] = {}
    for lang_name in ("hebrew", "greek", "latin"):
        tokens = verses_n = extra_v = dup_v = dup_tok = unmapped_v = unmapped_tok = oor_tok = 0
        for slug, ch, vnum, txt in conn.execute(
            """
            SELECT c.book_slug, c.chapter, v.verse, v.critical_text
            FROM verses v
            JOIN chapters c ON c.id = v.chapter_id
            WHERE c.language = ?
            """,
            (lang_name,),
        ):
            slug_s = str(slug)
            if slug_s not in BOOKS_BY_SLUG:
                continue
            text = str(txt or "")
            if not text.strip():
                continue
            nt = len(tokenize_verse(text, lang_name))
            tokens += nt
            ch_i, v_i = int(ch), int(vnum)
            book = BOOKS_BY_SLUG[slug_s]
            targets = vs.to_saints(lang_name, slug_s, ch_i, v_i)
            if targets:
                sc, sv = targets[0]
                sub = 0
            else:
                extra = vs.to_extra_site_anchor(lang_name, slug_s, ch_i, v_i)
                if extra is None:
                    if vs.is_duplicate_or_placeholder(lang_name, slug_s, ch_i, v_i):
                        dup_v += 1
                        dup_tok += nt
                    else:
                        unmapped_v += 1
                        unmapped_tok += nt
                    continue
                sc, sv = extra
                sub = vs.EXTRA_SITE_SUBVERSE
                extra_v += 1
            verses_n += 1
            try:
                make_anchor_verse_id(book.order, sc, sv, sub)
            except ValueError:
                oor_tok += nt
        if tokens or lang_name in indexed_by_lang:
            text_by_lang[lang_name] = {
                "tokens": tokens,
                "verses": verses_n,
                "extra_site_verses": extra_v,
                "skipped_duplicate_verses": dup_v,
                "tokens_in_duplicate_verses": dup_tok,
                "unmapped_verses": unmapped_v,
                "tokens_in_unmapped_verses": unmapped_tok,
                "tokens_out_of_range": oor_tok,
            }

    coverage: Dict[str, Dict[str, Any]] = {}
    for lang_name in ("hebrew", "greek", "latin"):
        if lang_name not in text_by_lang and lang_name not in indexed_by_lang:
            continue
        tinfo = text_by_lang.get(lang_name, {})
        iinfo = indexed_by_lang.get(lang_name, {})
        indexed = int(iinfo.get("indexed", 0))
        content = int(iinfo.get("content_words", 0))
        func = int(iinfo.get("function_words", 0))
        with_morph = int(iinfo.get("with_morph", 0))
        dup_tok = int(tinfo.get("tokens_in_duplicate_verses", 0))
        unmapped_tok = int(tinfo.get("tokens_in_unmapped_verses", 0))
        oor_tok = int(tinfo.get("tokens_out_of_range", 0))
        tokens = int(tinfo.get("tokens", 0))
        if tokens == 0 and indexed > 0:
            tokens = indexed
        untagged = max(0, tokens - indexed - dup_tok - unmapped_tok - oor_tok)
        tok_den = max(tokens, 1)
        idx_den = max(indexed, 1)
        entry: Dict[str, Any] = {
            "tokens": tokens,
            "verses": int(tinfo.get("verses", 0)),
            "indexed": indexed,
            "content_words": content,
            "function_words": func,
            "with_morph": with_morph,
            "untagged": untagged,
            "extra_site_verses": int(tinfo.get("extra_site_verses", 0)),
            "skipped_duplicate_verses": int(tinfo.get("skipped_duplicate_verses", 0)),
            "tokens_in_duplicate_verses": dup_tok,
            "unmapped_verses": int(tinfo.get("unmapped_verses", 0)),
            "tokens_in_unmapped_verses": unmapped_tok,
            "indexed_share_of_tokens": round(indexed / tok_den, 4),
            "content_share_of_tokens": round(content / tok_den, 4),
            "morph_share_of_indexed": round(with_morph / idx_den, 4),
            "untagged_share_of_tokens": round(untagged / tok_den, 4),
        }
        if oor_tok:
            entry["tokens_out_of_range"] = oor_tok
        coverage[lang_name] = entry
    return coverage


def gold_stats(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Counts from the tables plus full-corpus coverage figures (aggregates cached by the build
    and recomputed whenever the token count no longer matches or full-corpus coverage is absent)."""
    ensure_gold_schema(conn)
    q = lambda sql, *a: conn.execute(sql, a).fetchone()[0]  # noqa: E731
    last = conn.execute("SELECT stats_json, seconds, started_at, scope FROM concordance_build_log ORDER BY build_id DESC LIMIT 1").fetchone()
    last_stats = json.loads(last[0]) if last else None
    tokens_now = int(q("SELECT COUNT(*) FROM stream_tokens"))
    usage = (last_stats or {}).get("usage")
    if not usage or int(usage.get("tokens_total", -1)) != tokens_now:
        usage = _usage_aggregates(conn)
    coverage = (last_stats or {}).get("corpus_coverage")
    if (
        not isinstance(coverage, dict)
        or not coverage
        or sum(int(c.get("indexed", 0)) for c in coverage.values()) != tokens_now
    ):
        coverage = _corpus_coverage(conn)
    return {
        **usage,
        "tokens_total": tokens_now,
        "alignments": int(q("SELECT COUNT(*) FROM trilingual_alignments")),
        "human_locked_tokens": int(q("SELECT COUNT(*) FROM stream_tokens WHERE human_locked = 1")),
        "coverage": coverage,
        "last_build": last_stats,
        "last_build_seconds": float(last[1]) if last else None,
        "last_build_at": str(last[2]) if last else None,
        "last_build_scope": str(last[3]) if last else None,
    }


def _build_hub_alignments(
    conn: sqlite3.Connection,
    verse_hits: Dict[int, Dict[str, List[Tuple[int, int]]]],
    hub_stems: Dict[int, List[Tuple[int, int, bool]]],
    eng_sg: int,
) -> Dict[str, int]:
    """One alignment unit per (Saints verse, curated hub) where words of the hub occur in at least two
    languages (or Greek+Latin in books without Hebrew).  The sense comes from the Hebrew word when
    present (its lemma is the most specific), else the Greek, else the Latin."""
    states = Counter()
    used_seq = defaultdict(set)
    for r in conn.execute("SELECT anchor_verse_id, unit_seq FROM trilingual_alignments"):
        used_seq[int(r[0])].add(int(r[1]))
    kept_units = {(int(r[0]), int(r[1])) for r in conn.execute(
        "SELECT ta.anchor_verse_id, ss.concept_id FROM trilingual_alignments ta JOIN saints_senses ss ON ss.sense_id = ta.sense_id")}
    unreviewed = {int(r[0]): int(r[1]) for r in conn.execute(
        "SELECT concept_id, sense_id FROM saints_senses WHERE sense_offset = ?", (UNREVIEWED_OFFSET,))}
    for avid, streams in verse_hits.items():
        by_hub: Dict[int, Dict[str, Tuple[int, int, bool]]] = defaultdict(dict)
        for stream, items in streams.items():
            for slot, stem in items:
                for cid, sense, decides in hub_stems.get(stem, []):
                    cur = by_hub[cid].get(stream)
                    if cur is None or (decides and not cur[2]):  # a sense-deciding word wins its stream
                        by_hub[cid][stream] = (slot, sense, decides)
        for cid, smap in by_hub.items():
            if (avid, cid) in kept_units:
                continue  # a person already set this verse's sense for this hub
            has_h = "heb_ot" in smap
            has_g = "grc_ot" in smap or "grc_nt" in smap
            has_l = "lat_bible" in smap
            if (has_h + has_g + has_l) < 2:
                continue
            if has_h and has_g and has_l:
                state = "unified"
            elif has_g and has_l:
                state = "grc_lat_only"
            elif has_h and has_g:
                state = "lat_divergent"
            else:
                state = "lxx_divergent"
            order = ["heb_ot", "grc_ot", "grc_nt", "lat_bible"]
            deciding = [smap[s][1] for s in order if s in smap and smap[s][2]]
            sense = deciding[0] if deciding else unreviewed.get(cid, next(smap[s][1] for s in order if s in smap))
            seq = 10
            while seq in used_seq[avid]:
                seq += 10
            used_seq[avid].add(seq)
            aid = int(conn.execute(
                """INSERT INTO trilingual_alignments (anchor_verse_id, unit_seq, sense_id, eng_infl_morph_id, alignment_state)
                   VALUES (?, ?, ?, ?, ?)""",
                (avid, seq, sense, eng_sg, state),
            ).lastrowid)
            conn.executemany(
                "INSERT INTO trilingual_alignment_slots (align_id, anchor_verse_id, lang_stream, slot_id, is_head_stem) VALUES (?, ?, ?, ?, 1)",
                [(aid, avid, s, slot) for s, (slot, _sense, _dec) in smap.items()],
            )
            states[state] += 1
    return dict(states)


# ---------------------------------------------------------------------------
# Website pack (one gzip file per language + the curated hubs)
# ---------------------------------------------------------------------------

PACK_SCHEMA = "saints-concordance-pack/v3"

ATTRIBUTION = [
    {"data": "Hebrew/Aramaic lemmas and morphology", "source": "OpenScriptures Hebrew Bible (OSHB) morphology of the WLC",
     "licence": "CC BY 4.0", "link": "https://hb.openscriptures.org"},
    {"data": "Hebrew roots (BDB) and lemma glosses", "source": "OpenScriptures Hebrew Lexicon (lexical index of Brown-Driver-Briggs)",
     "licence": "CC BY 4.0", "link": "https://github.com/openscriptures/HebrewLexicon"},
    {"data": "Greek NT lemmas", "source": "STEPBible TAGNT, Tyndale House Cambridge", "licence": "CC BY 4.0",
     "link": "https://STEPBible.github.io/STEPBible-Data"},
    {"data": "Brief lexicon glosses (Gloss column only)", "source": "STEPBible TBESH/TBESG, Tyndale House Cambridge",
     "licence": "CC BY 4.0", "link": "https://STEPBible.github.io/STEPBible-Data"},
    {"data": "Septuagint lemmas", "source": "Open Scriptures Septuagint Project (LxxLemmas)", "licence": "CC BY 4.0",
     "link": "https://github.com/openscriptures/GreekResources"},
    {"data": "Greek word families", "source": "Strong's Greek Dictionary in XML (U. Sandborg-Petersen)", "licence": "CC0",
     "link": "https://github.com/morphgnt/strongs-dictionary-xml"},
    {"data": "Latin lemmas and word families", "source": "Lewis & Short, A Latin Dictionary (Perseus Digital Library TEI)",
     "licence": "CC BY-SA 4.0", "link": "https://github.com/PerseusDL/lexica"},
    {"data": "Greek word families (derivations)", "source": "MorphGNT morphological-lexicon derivation.yaml (J. Tauber)",
     "licence": "CC BY-SA 3.0", "link": "https://github.com/morphgnt/morphological-lexicon"},
    {"data": "Greek lemma keys and word families (src field)", "source": "Open Scriptures Greek Word List (GreekResources)",
     "licence": "CC BY 4.0", "link": "https://github.com/openscriptures/GreekResources"},
    {"data": "Septuagint parsing (word layer)", "source": "GLAUx corpus, A. Keersmaekers (Keersmaekers 2021, LChange); "
             "LXX source texts from el.wikisource; aligned word by word to the Saints Critical Greek Text",
     "licence": "CC BY-SA 4.0 (source texts CC BY-SA 3.0)", "link": "https://github.com/alekkeersmaekers/glaux"},
    {"data": "Parsing of Hebrew and Greek NT words (word layer)", "source": "OSHB morphology; STEPBible TAGNT, TEHMC, TEGMC",
     "licence": "CC BY 4.0", "link": "https://STEPBible.github.io/STEPBible-Data"},
    {"data": "Latin and Hebrew proper names", "source": "STEPBible TIPNR, Tyndale House Cambridge", "licence": "CC BY 4.0",
     "link": "https://STEPBible.github.io/STEPBible-Data"},
    {"data": "Verse-number correspondences", "source": "OSHB VerseMap.xml, STEPBible TVTMS and the Saints.Bible verse map",
     "licence": "CC BY 4.0", "link": "https://STEPBible.github.io/STEPBible-Data"},
]

def _alignment_attribution() -> List[Dict[str, str]]:
    """English-word links (word layer): the dictionaries the aligner used, from concordance_align.SOURCES."""
    try:
        from .concordance_align import SOURCES
    except Exception:
        return []
    links = {"TAGNT": "https://STEPBible.github.io/STEPBible-Data", "TAHOT": "https://STEPBible.github.io/STEPBible-Data",
             "MACULA-G": "https://github.com/Clear-Bible/macula-greek",
             "MACULA-H": "https://github.com/Clear-Bible/macula-hebrew"}
    out = []
    for key, text in SOURCES.items():
        if key == "Studio":
            continue
        source, _, rest = text.partition(" (")
        licence = "CC BY 4.0" if "CC BY 4.0" in text else ""
        out.append({"data": "English-word links (alignment dictionary)", "source": source + (" (" + rest if rest else ""),
                    "licence": licence, "link": links.get(key, "")})
    return out


# Licence of each pack file: the Greek pack contains MorphGNT-derived families (CC BY-SA 3.0, compatible with
# 4.0) and the Latin pack Lewis & Short-derived lemmas, glosses and families (CC BY-SA 4.0), so both are
# share-alike; the decoder is Saints.Bible code.
PACK_LICENCES = {
    "heb": "CC BY 4.0", "grc": "CC BY-SA 4.0", "lat": "CC BY-SA 4.0", "hubs": "CC BY 4.0",
    "decoder": "MIT (Saints.Bible code)",
    "heb-lex": "CC BY 4.0", "grc-lex": "CC BY-SA 4.0", "lat-lex": "CC BY-SA 4.0",
}

CHANGES_NOTE = (
    "Changes made by Saints.Bible: lemma tags were aligned word by word to the Saints critical texts (which differ "
    "from the tagged editions in places; unmatched words are left untagged), verse numbers were converted to the "
    "Saints.Bible (Greek/Septuagint) numbering, Strong's numbers were reduced to base numbers for linking, and "
    "families were derived from the cited lexica. Only the brief 'Gloss' column of TBESH/TBESG is used."
)


DECODER_JS_V3 = r"""/**
 * Saints Concordance decoder for pack schema saints-concordance-pack/v3 (no dependencies, ES5).
 *
 *   var c = SaintsConcordance.create(hebPack, grcPack, latPack, hubsPack);   // any subset, parsed JSON
 *   c.findLemmas('ἀρχή')            -> [{id, lang, lemma, key, rootId, pos, gloss, formula}]
 *   c.lemmaVerses('G0746')          -> sorted anchor ids (book*10000000 + chapter*10000 + verse*10)
 *   c.rootVerses(rootId)            -> verses of every lemma of the family
 *   c.hubSenseVerses(senseId)       -> verses of a curated colour-hub sense
 *   c.ref(anchorId)                 -> {book, slug, chapter, verse, label}
 * Verse numbers are the Saints.Bible (Greek/Septuagint) numbers used by the site.
 */
(function (global) {
  'use strict';
  var SCHEMA = 'saints-concordance-pack/v3';

  function decodeVarints(b64) {
    if (!b64) return [];
    var bin = atob(b64), out = [], acc = 0, shift = 0, prev = 0, i, b;
    for (i = 0; i < bin.length; i++) {
      b = bin.charCodeAt(i);
      acc += (b & 0x7f) * Math.pow(2, shift);
      if (b & 0x80) {
        shift += 7;
      } else {
        prev = prev + acc;
        out.push(prev);
        acc = 0;
        shift = 0;
      }
    }
    return out;
  }

  function decodeAnchorVerseId(avid) {
    var book = Math.floor(avid / 10000000), rem = avid % 10000000;
    return { book: book, chapter: Math.floor(rem / 10000), verse: Math.floor((rem % 10000) / 10) };
  }

  function bare(s) {
    s = String(s || '').toLowerCase();
    if (s.normalize) s = s.normalize('NFD');
    return s.replace(/[̀-֑ͯ-ׇ]/g, '').replace(/ς/g, 'σ');
  }

  function Concordance() {
    this.books = {}; this.roots = {}; this.lemmas = {}; this.byKey = {}; this.rootMembers = {};
    this.postings = {}; this.hubs = []; this.senses = {}; this.sensePostings = {};
  }

  Concordance.prototype.addPack = function (pack) {
    var self = this, k;
    if (!pack || pack.schema !== SCHEMA) throw new Error('Saints Concordance: unsupported pack ' + (pack && pack.schema));
    (pack.books || []).forEach(function (b) { self.books[b[0]] = { order: b[0], slug: b[1], usfm: b[2], title: b[3] }; });
    (pack.roots || []).forEach(function (r) {
      self.roots[r[0]] = { id: r[0], lang: r[1], label: r[2], homograph: r[3], gloss: r[4], source: r[5], translit: r[6] || '' };
    });
    (pack.lemmas || []).forEach(function (l) {
      var o = { id: l[0], lang: l[1], lemma: l[2], key: l[3], rootId: l[4], pos: l[5], gloss: l[6], formula: l[7],
                content: l[8] !== 0, verseCount: l[9] || 0, translit: l[10] || '' };
      self.lemmas[o.id] = o;
      if (o.key) self.byKey[o.key] = o;
      (self.rootMembers[o.rootId] = self.rootMembers[o.rootId] || []).push(o.id);
    });
    for (k in (pack.lemma_postings || {})) if (pack.lemma_postings.hasOwnProperty(k)) self.postings[k] = pack.lemma_postings[k];
    (pack.hubs || []).forEach(function (h) {
      var hub = { id: h[0], slug: h[1], word: h[2], colour: h[3], note: h[4], senses: [], members: h[6] || [], theme: h[7] || '' };
      (h[5] || []).forEach(function (s) {
        var sense = { id: s[0], offset: s[1], word: s[2], role: s[3], nuance: s[4], hub: hub,
                      colour: s[5] || hub.colour, theme: s[6] || hub.theme, chosen: s[3] !== 'unreviewed' };
        hub.senses.push(sense);
        self.senses[sense.id] = sense;
      });
      self.hubs.push(hub);
    });
    for (k in (pack.sense_postings || {})) if (pack.sense_postings.hasOwnProperty(k)) self.sensePostings[k] = pack.sense_postings[k];
    return this;
  };

  Concordance.prototype.lemma = function (idOrKey) {
    return this.lemmas[idOrKey] || this.byKey[idOrKey] || null;
  };

  Concordance.prototype.lemmaVerses = function (idOrKey) {
    var l = this.lemma(idOrKey);
    return l ? decodeVarints(this.postings[String(l.id)]) : [];
  };

  Concordance.prototype.rootVerses = function (rootId) {
    var seen = {}, out = [], self = this;
    (this.rootMembers[rootId] || []).forEach(function (lid) {
      decodeVarints(self.postings[String(lid)]).forEach(function (v) { if (!seen[v]) { seen[v] = 1; out.push(v); } });
    });
    return out.sort(function (a, b) { return a - b; });
  };

  Concordance.prototype.hubSenseVerses = function (senseId) {
    return decodeVarints(this.sensePostings[String(senseId)]);
  };

  Concordance.prototype.findLemmas = function (query, limit) {
    var q = bare(query), out = [], id, l;
    if (!q) return out;
    for (id in this.lemmas) {
      if (!this.lemmas.hasOwnProperty(id)) continue;
      l = this.lemmas[id];
      if (bare(l.lemma).indexOf(q) === 0 || (l.translit && bare(l.translit).indexOf(q) === 0) ||
          String(l.key).toLowerCase() === q || bare(l.gloss).indexOf(q) !== -1) out.push(l);
      if (out.length >= (limit || 50)) break;
    }
    return out;
  };

  Concordance.prototype.ref = function (avid) {
    var d = decodeAnchorVerseId(avid), b = this.books[d.book] || {};
    return { book: b.title || String(d.book), slug: b.slug || '', chapter: d.chapter, verse: d.verse,
             label: (b.title || d.book) + ' ' + d.chapter + ':' + d.verse };
  };

  global.SaintsConcordance = {
    schema: SCHEMA,
    create: function () {
      var c = new Concordance(), i;
      for (i = 0; i < arguments.length; i++) if (arguments[i]) c.addPack(arguments[i]);
      return c;
    },
    decodeVarints: decodeVarints,
    decodeAnchorVerseId: decodeAnchorVerseId
  };
})(typeof window !== 'undefined' ? window : this);
"""


def _b64(blob: bytes) -> str:
    import base64
    return base64.b64encode(blob).decode("ascii")


def export_gold_pack(conn: sqlite3.Connection, out_dir: Optional[Any] = None,
                     extra_stem_ids: Optional[Sequence[int]] = None) -> Dict[str, Any]:
    """Write the website pack: per-language lemma/root tables with delta-varint verse postings, the curated
    colour hubs with their sense postings, the JS decoder, a Word Studies CSV for the curated hubs, and a
    report whose every number is measured from the files just written."""
    import gzip
    from pathlib import Path

    from .catalog import OUTPUT_ROOT
    from .concordance import (
        CONCORDANCE_PACK_DIR_NAME,
        encode_delta_varints,
        rebuild_concordance_postings,
    )

    ensure_gold_schema(conn)
    backfill_transliterations(conn)
    rebuild_concordance_postings(conn)
    target = Path(out_dir) if out_dir else (OUTPUT_ROOT / CONCORDANCE_PACK_DIR_NAME)
    target.mkdir(parents=True, exist_ok=True)

    books = [[b.order, b.slug, b.usfm_code, b.title] for b in BOOKS]
    lang_groups = {"heb": ("heb", "arc"), "grc": ("grc",), "lat": ("lat",)}
    written: Dict[str, Any] = {}
    measured: Dict[str, Any] = {}

    for pack_lang, langs in lang_groups.items():
        qmarks = ",".join("?" * len(langs))
        # Verse postings per lemma for content words only (function words stay indexed in studio.db,
        # but omitting their postings keeps the downloadable website packs compact and focused).
        post: Dict[int, set] = defaultdict(set)
        form_post: Dict[int, set] = defaultdict(set)
        occ = 0
        for r in conn.execute(
            f"""SELECT st.stem_id, wa.anchor_verse_id, st.form_id FROM stream_tokens st
                JOIN word_anchors wa ON wa.slot_id = st.slot_id
                JOIN versification_anchors va ON va.anchor_verse_id = wa.anchor_verse_id
                JOIN lexical_stems ls ON ls.stem_id = st.stem_id
                WHERE ls.lang IN ({qmarks}) AND st.is_content = 1 AND va.subverse = 0""", langs):
            post[int(r[0])].add(int(r[1]))
            form_post[int(r[2])].add(int(r[1]))
            occ += 1
        if not post:
            continue
        stem_rows = conn.execute(
            f"""SELECT ls.stem_id, ls.lang, ls.canonical_stem, ls.lemma_key, ls.root_id, ls.pos_tag,
                       ls.base_gloss, COALESCE(ls.structural_formula, ''), COALESCE(ls.translit, '')
                FROM lexical_stems ls WHERE ls.lang IN ({qmarks}) ORDER BY ls.stem_id""", langs).fetchall()
        # 9th field (idx 8): 1 = content word with verse postings, 0 = function word listed only so the per-book
        # word layer's lemma ids resolve; idx 9 = verse count; idx 10 = English-friendly Latinized transliteration
        extra = set(extra_stem_ids or ())
        lemmas = [[int(r[0]), str(r[1]), str(r[2]), str(r[3] or ""), int(r[4]), str(r[5]), str(r[6]), str(r[7]),
                   1 if int(r[0]) in post else 0, len(post.get(int(r[0]), ())), str(r[8] or "")]
                  for r in stem_rows if int(r[0]) in post or int(r[0]) in extra]
        root_ids = sorted({row[4] for row in lemmas})
        roots = []
        for rid in root_ids:
            rr = conn.execute(
                "SELECT root_id, lang, root_key, homograph_no, core_idea, COALESCE(root_source, ''), COALESCE(translit, '') FROM core_roots WHERE root_id = ?",
                (rid,)).fetchone()
            roots.append([int(rr[0]), str(rr[1]), str(rr[2]), int(rr[3]), str(rr[4]), str(rr[5]), str(rr[6])])
        lemma_postings = {str(k): _b64(encode_delta_varints(sorted(v))) for k, v in sorted(post.items())}
        payload = {
            "schema": PACK_SCHEMA,
            "language": pack_lang,
            "licence": PACK_LICENCES[pack_lang],
            "numbering": "Saints.Bible (Greek/Septuagint) verse numbering; anchor = book*10000000 + chapter*10000 + verse*10",
            "attribution": ATTRIBUTION,
            "changes": CHANGES_NOTE,
            "books": books,
            "roots": roots,
            "lemmas": lemmas,
            "lemma_postings": lemma_postings,
        }
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        gz_path = target / f"saints-concordance-{pack_lang}.json.gz"
        with gzip.open(gz_path, "wb", compresslevel=9) as fh:
            fh.write(raw)
        # Lemma-only index for search boxes and word cards (no postings; idx 9 = verse count, idx 10 = translit)
        lex_payload = dict(payload)
        lex_payload.pop("lemma_postings")
        lex_payload["schema"] = PACK_SCHEMA + ".lex"
        lex_payload["lemmas"] = lemmas
        lex_path = target / f"saints-concordance-{pack_lang}-lex.json.gz"
        with gzip.open(lex_path, "wb", compresslevel=9) as fh:
            fh.write(json.dumps(lex_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        written[f"{pack_lang}-lex"] = str(lex_path)
        # Honest baseline: the same postings keyed by surface form instead of lemma, same encoding
        surface_postings = {str(k): _b64(encode_delta_varints(sorted(v))) for k, v in form_post.items()}
        base_raw = json.dumps({"forms": len(form_post), "form_postings": surface_postings},
                              separators=(",", ":")).encode("utf-8")
        base_gz = len(gzip.compress(base_raw, compresslevel=9))
        written[pack_lang] = str(gz_path)
        measured[pack_lang] = {
            "indexed_tokens": occ,
            "lemmas": len(lemmas),
            "roots": len(roots),
            "surface_forms": len(form_post),
            "lemma_verse_pairs": sum(len(v) for v in post.values()),
            "surface_verse_pairs": sum(len(v) for v in form_post.values()),
            "raw_bytes": len(raw),
            "gz_bytes": gz_path.stat().st_size,
            "surface_baseline_postings_gz_bytes": base_gz,
        }

    # Curated colour hubs
    hubs = []
    hub_sense_post: Dict[int, set] = defaultdict(set)
    for r in conn.execute(
        """SELECT ta.sense_id, ta.anchor_verse_id FROM trilingual_alignments ta
           JOIN versification_anchors va ON va.anchor_verse_id = ta.anchor_verse_id
           WHERE va.subverse = 0"""
    ):
        hub_sense_post[int(r[0])].add(int(r[1]))
    for c in conn.execute(
        "SELECT concept_id, concept_slug, eng_base_word, theme_colour, summary_note FROM trilingual_concepts WHERE theme_colour IS NOT NULL ORDER BY concept_id"):
        cid = int(c[0])
        senses = [[int(s[0]), int(s[1]), str(s[2]), str(s[3]), str(s[4]), s[5],
                   SENSE_COLOUR_OVERRIDES.get((str(c[1]), int(s[1])), ("", ""))[1]] for s in conn.execute(
            "SELECT sense_id, sense_offset, base_word, sense_role, usage_nuance, theme_colour_override FROM saints_senses WHERE concept_id = ? ORDER BY sense_offset", (cid,))]
        members = [str(m[0]) for m in conn.execute(
            """SELECT ls.lemma_key FROM stem_concept_links scl JOIN lexical_stems ls ON ls.stem_id = scl.stem_id
               WHERE scl.concept_id = ? AND ls.lemma_key IS NOT NULL ORDER BY ls.lang, ls.lemma_key""", (cid,))]
        theme = HUB_KEY.get(str(c[1]), ("", ""))[1]
        hubs.append([cid, str(c[1]), str(c[2]), str(c[3]), str(c[4]), senses, members, theme])
    hub_payload = {
        "schema": PACK_SCHEMA,
        "licence": PACK_LICENCES["hubs"],
        "numbering": "Saints.Bible (Greek/Septuagint) verse numbering",
        "hubs": hubs,
        "sense_postings": {str(k): _b64(encode_delta_varints(sorted(v))) for k, v in sorted(hub_sense_post.items())},
    }
    hub_raw = json.dumps(hub_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    hub_path = target / "saints-concordance-hubs.json.gz"
    with gzip.open(hub_path, "wb", compresslevel=9) as fh:
        fh.write(hub_raw)
    written["hubs"] = str(hub_path)
    measured["hubs"] = {"hubs": len(hubs), "raw_bytes": len(hub_raw), "gz_bytes": hub_path.stat().st_size}

    js_path = target / "saints-concordance-decoder.js"
    js_path.write_text(DECODER_JS_V3, encoding="utf-8")
    written["decoder"] = str(js_path)

    # Not the saints-word-studies import format (that needs words present in the Saints English verse,
    # the site's theme labels and kinds): a review list of the colour-hub occurrences for editors.
    csv_path = target / "saints-concordance-hub-occurrences.csv"
    written["csv"] = str(csv_path)
    measured["csv_rows"] = _write_hub_csv(conn, csv_path)

    # Old v2 files from the first build are superseded
    removed_old = []
    for old in ("saints-concordance-pack.json", "saints-concordance-pack.min.json.gz", "saints-word-studies-concordance.csv"):
        p = target / old
        if p.exists():
            p.unlink()
            removed_old.append(old)

    stats = gold_stats(conn)
    # Always recompute full-corpus coverage live from DB tables during pack export so a single-book
    # incremental build in concordance_build_log can never overwrite full-corpus pack statistics.
    live_coverage = _corpus_coverage(conn)
    stats["coverage"] = live_coverage
    manifest = {
        "schema": PACK_SCHEMA,
        "files": {k: Path(v).name for k, v in written.items()},
        "licences": {Path(written[k]).name: PACK_LICENCES[k] for k in written if k in PACK_LICENCES},
        "measured": measured,
        "coverage": live_coverage,
        "attribution": ATTRIBUTION + _alignment_attribution(),
        "changes": CHANGES_NOTE,
    }
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    report = _report_markdown(measured, stats)
    (target / "CONCORDANCE_REPORT.md").write_text(report, encoding="utf-8")
    old_report = target / "CONCORDANCE_COMPRESSION_REPORT.md"
    if old_report.exists():
        old_report.unlink()
        removed_old.append(old_report.name)
    return {"pack_dir": str(target), "files": written, "measured": measured, "removed_old_files": removed_old,
            "report_path": str(target / "CONCORDANCE_REPORT.md"), "stats": stats}


def _write_hub_csv(conn: sqlite3.Connection, csv_path: Any) -> int:
    """Rows for the curated colour hubs only, one per (verse, hub), in the site's numbering."""
    import csv

    from .concordance import render_english_sense

    rows = conn.execute(
        """
        SELECT bc.title, va.chapter, va.verse, ss.base_word, em.morph_code,
               COALESCE(ss.theme_colour_override, tc.theme_colour) AS colour,
               tc.concept_slug, ss.sense_role, ta.alignment_state, tc.eng_base_word, ss.usage_nuance,
               ta.anchor_verse_id, ta.align_id, COALESCE(ta.translation_note_ref, ''), ss.sense_offset
        FROM trilingual_alignments ta
        JOIN versification_anchors va ON va.anchor_verse_id = ta.anchor_verse_id
        JOIN books_catalog bc ON bc.book_order = va.book_order
        JOIN saints_senses ss ON ss.sense_id = ta.sense_id
        JOIN trilingual_concepts tc ON tc.concept_id = ss.concept_id
        LEFT JOIN morpheme_catalog em ON em.morph_id = ta.eng_infl_morph_id
        WHERE tc.theme_colour IS NOT NULL AND va.subverse = 0
        ORDER BY ta.anchor_verse_id, ta.unit_seq
        """
    ).fetchall()
    n = 0
    with open(csv_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["book", "chapter", "verse", "word", "colour", "theme", "kind", "original", "literal", "note",
                    "alignment_state", "translation_note"])
        for r in rows:
            words = []
            for s in conn.execute(
                """SELECT tas.lang_stream, sf.surface_text, ls.canonical_stem, ls.lemma_key, cr.root_key
                   FROM trilingual_alignment_slots tas
                   JOIN stream_tokens st ON st.slot_id = tas.slot_id
                   JOIN surface_forms sf ON sf.form_id = st.form_id
                   JOIN lexical_stems ls ON ls.stem_id = st.stem_id
                   JOIN core_roots cr ON cr.root_id = ls.root_id
                   WHERE tas.align_id = ? ORDER BY tas.lang_stream""", (int(r[12]),)):
                words.append(f"{s[0]}={s[1]} ({s[2]} {s[3]}; root {s[4]})")
            w.writerow([r[0], r[1], r[2], render_english_sense(str(r[3]), r[4]), r[5],
                        SENSE_COLOUR_OVERRIDES.get((str(r[6]), int(r[14])), HUB_KEY.get(str(r[6]), ("", str(r[6]))))[1], r[7],
                        " | ".join(words), r[9], r[10], r[8], r[13]])
            n += 1
    return n


def _report_markdown(measured: Dict[str, Any], stats: Dict[str, Any]) -> str:
    lines = ["# Saints Concordance — build report", "",
             "Every number below is measured from the database and the files just written.", ""]
    cov = stats.get("coverage") or (stats.get("last_build") or {}).get("languages") or {}
    if cov:
        lines += ["## Coverage of the critical texts", "",
                  "| Language | Tokens | Indexed (all tagged) | Content words | Function words | Parsed (morph) | Untagged | Extra-site verses (studio.db) | Skipped dup/placeholder tokens |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for lang, c in cov.items():
            tok = int(c.get("tokens", 0))
            idx = int(c.get("indexed", 0))
            pct = (100.0 * idx / tok) if tok else 0.0
            cont = int(c.get("content_words", idx))
            func = int(c.get("function_words", 0))
            morph = int(c.get("with_morph", 0))
            lines.append(
                f"| {lang} | {tok:,} | {idx:,} ({pct:.1f}%) | {cont:,} | {func:,} | {morph:,} | "
                f"{c.get('untagged', 0):,} | {c.get('extra_site_verses', 0):,} | {c.get('tokens_in_duplicate_verses', 0):,} |"
            )
        lines += ["",
                  "All tagged tokens (content and function words) across every non-duplicate verse are indexed in `studio.db` "
                  "with their morphological parses; non-duplicate MT / TR / Theodotion / Vulgate verses absent from Saints.Bible "
                  "are stored under dedicated extra-site anchors (`subverse = 9`, marked `*`), while confirmed duplicate and "
                  "placeholder rows are skipped so no word is counted twice. The downloadable website packs below carry live "
                  "Saints.Bible (`subverse = 0`) content-word postings only so every published link resolves on the site.", ""]
    lines += ["## Pack files (content-word postings)", "",
              "| File | Lemmas | Roots | Surface forms | Lemma-verse pairs | Raw JSON | Gzip | Same postings keyed by surface form (gzip) |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for lang in ("heb", "grc", "lat"):
        m = measured.get(lang)
        if not m:
            continue
        lines.append(f"| saints-concordance-{lang}.json.gz | {m['lemmas']:,} | {m['roots']:,} | {m['surface_forms']:,} | "
                     f"{m['lemma_verse_pairs']:,} | {m['raw_bytes']:,} | {m['gz_bytes']:,} | {m['surface_baseline_postings_gz_bytes']:,} |")
    h = measured.get("hubs")
    if h:
        lines.append(f"| saints-concordance-hubs.json.gz | {h['hubs']} hubs | | | | {h['raw_bytes']:,} | {h['gz_bytes']:,} | |")
    lines += ["", f"Colour-hub occurrences for review (saints-concordance-hub-occurrences.csv, not the word-studies import "
              f"format): {measured.get('csv_rows', 0):,} rows", "",
              "Licences: " + "; ".join(f"{k} {v}" for k, v in PACK_LICENCES.items()) + ". Sources, links and the note "
              "of changes are listed in manifest.json.",
              "",
              "Colour-hub senses: a unit gets a specific sense only when one of its words decides it (e.g. ἄνεμος/ventus "
              "'wind', κεφαλή 'head'); otherwise it carries the hub's 'sense not yet chosen' row (offset 64) until a "
              "person sets it in Tab 5."]
    return "\n".join(lines) + "\n"
