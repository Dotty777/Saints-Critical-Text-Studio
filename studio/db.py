"""SQLite Persistence & Initial Corpus Discovery for Saints Critical Text Studio."""

from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, Iterator, List, Optional

from .catalog import (
    CRITICAL_OUTPUT_ROOTS,
    DATA_DIR,
    GREEK_RESEARCH_ROOT,
    HEBREW_RESEARCH_ROOT,
    LATIN_RESEARCH_ROOT,
    LATIN_TRANSLATION_ROOT,
)
from .concordance import init_concordance_schema
from .parsers import resolve_corpus_path

DB_PATH = DATA_DIR / "studio.db"

# Bump when the built-in witness descriptions or self-contained Studio paths below change.
SEED_VERSION = 7


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS witnesses (
                id TEXT PRIMARY KEY,
                language TEXT NOT NULL,
                testament_scope TEXT NOT NULL,
                siglum TEXT NOT NULL,
                title TEXT NOT NULL,
                tier INTEGER NOT NULL,
                status TEXT NOT NULL,
                license TEXT NOT NULL,
                date_range TEXT NOT NULL,
                text_type TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 0.85,
                parser_kind TEXT NOT NULL,
                file_path TEXT NOT NULL,
                gatekeeper_summary TEXT NOT NULL,
                gatekeeper_json TEXT NOT NULL DEFAULT '{}',
                human_override INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                language TEXT NOT NULL,
                division TEXT NOT NULL,
                book_slug TEXT NOT NULL,
                book_title TEXT NOT NULL,
                chapter INTEGER NOT NULL,
                status TEXT NOT NULL,
                ai_mode TEXT NOT NULL,
                model_used TEXT NOT NULL,
                verse_count INTEGER NOT NULL DEFAULT 0,
                variant_verse_count INTEGER NOT NULL DEFAULT 0,
                local_md_path TEXT DEFAULT '',
                local_json_path TEXT DEFAULT '',
                local_tsv_path TEXT DEFAULT '',
                drive_doc_id TEXT DEFAULT '',
                drive_url TEXT DEFAULT '',
                updated_at TEXT NOT NULL,
                UNIQUE(language, book_slug, chapter)
            );

            CREATE TABLE IF NOT EXISTS verses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
                verse INTEGER NOT NULL,
                critical_text TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.95,
                decision_source TEXT NOT NULL,
                witness_readings_json TEXT NOT NULL,
                apparatus_json TEXT NOT NULL,
                disregarded_json TEXT NOT NULL,
                rationale TEXT NOT NULL,
                human_locked INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                UNIQUE(chapter_id, verse)
            );

            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS gatekeeper_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                language TEXT NOT NULL,
                witness_title TEXT NOT NULL,
                file_path TEXT NOT NULL,
                decision TEXT NOT NULL,
                tier_assigned INTEGER NOT NULL,
                confidence REAL NOT NULL,
                model_used TEXT NOT NULL,
                summary TEXT NOT NULL,
                details_json TEXT NOT NULL
            );
            """
        )
        verse_cols = {r["name"] for r in conn.execute("PRAGMA table_info(verses)")}
        if "analysis_json" not in verse_cols:  # added with the Textual Analysis Brain
            conn.execute("ALTER TABLE verses ADD COLUMN analysis_json TEXT NOT NULL DEFAULT '[]'")
        if "needs_review" not in verse_cols:
            conn.execute("ALTER TABLE verses ADD COLUMN needs_review INTEGER NOT NULL DEFAULT 0")
        seed_default_witnesses(conn)
        _migrate_in_studio_paths(conn)
        init_concordance_schema(conn)


def _migrate_single_edition_path(raw_path: str, language: str) -> str:
    if not raw_path:
        return raw_path
    p = Path(raw_path)
    if p.exists():
        return str(p)
    out_root = CRITICAL_OUTPUT_ROOTS.get(language.lower())
    if out_root:
        parts = p.parts
        for i, part in enumerate(parts):
            if re.fullmatch(r"(?:Gemini|Saints)-(Greek|Hebrew|Latin)-Critical-Text", part):
                cand = out_root.joinpath(*parts[i + 1:])
                return str(cand)
    return raw_path


def _migrate_in_studio_paths(conn: sqlite3.Connection) -> None:
    """Keep witness and saved-chapter file_paths pointed inside Saints-Critical-Text-Studio."""
    for row in conn.execute("SELECT id, file_path, gatekeeper_summary FROM witnesses").fetchall():
        resolved = resolve_corpus_path(Path(str(row["file_path"])))
        new_summary = str(row["gatekeeper_summary"]).replace("Gemini Critical Text", "Saints Critical Text")
        if str(resolved) != str(row["file_path"]) or new_summary != str(row["gatekeeper_summary"]):
            conn.execute(
                "UPDATE witnesses SET file_path = ?, gatekeeper_summary = ? WHERE id = ?",
                (str(resolved), new_summary, row["id"]),
            )
    for ch in conn.execute("SELECT id, language, local_md_path, local_json_path, local_tsv_path FROM chapters").fetchall():
        lang = str(ch["language"])
        md_p = _migrate_single_edition_path(str(ch["local_md_path"] or ""), lang)
        js_p = _migrate_single_edition_path(str(ch["local_json_path"] or ""), lang)
        ts_p = _migrate_single_edition_path(str(ch["local_tsv_path"] or ""), lang)
        if (md_p, js_p, ts_p) != (ch["local_md_path"], ch["local_json_path"], ch["local_tsv_path"]):
            conn.execute(
                "UPDATE chapters SET local_md_path = ?, local_json_path = ?, local_tsv_path = ? WHERE id = ?",
                (md_p, js_p, ts_p, ch["id"]),
            )


def _seed_row(
    conn: sqlite3.Connection,
    wid: str,
    language: str,
    scope: str,
    siglum: str,
    title: str,
    tier: int,
    status: str,
    license_str: str,
    date_range: str,
    text_type: str,
    weight: float,
    parser_kind: str,
    file_path: Path,
    summary: str,
    scores: Dict[str, Any],
    refresh: bool = False,
) -> None:
    now = utc_now()
    existing = conn.execute("SELECT id, human_override FROM witnesses WHERE id = ?", (wid,)).fetchone()
    gk_json = json.dumps(scores, ensure_ascii=False)
    if existing:
        if refresh and not int(existing["human_override"]):
            conn.execute(
                """
                UPDATE witnesses SET testament_scope = ?, siglum = ?, title = ?, tier = ?, status = ?,
                    license = ?, date_range = ?, text_type = ?, weight = ?, parser_kind = ?, file_path = ?,
                    gatekeeper_summary = ?, gatekeeper_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (scope, siglum, title, tier, status, license_str, date_range, text_type, weight,
                 parser_kind, str(file_path), summary, gk_json, now, wid),
            )
        return
    conn.execute(
        """
        INSERT INTO witnesses (
            id, language, testament_scope, siglum, title, tier, status, license,
            date_range, text_type, weight, parser_kind, file_path,
            gatekeeper_summary, gatekeeper_json, human_override, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (
            wid,
            language,
            scope,
            siglum,
            title,
            tier,
            status,
            license_str,
            date_range,
            text_type,
            weight,
            parser_kind,
            str(file_path),
            summary,
            gk_json,
            now,
            now,
        ),
    )
    conn.execute(
        """
        INSERT INTO gatekeeper_log (
            created_at, language, witness_title, file_path, decision,
            tier_assigned, confidence, model_used, summary, details_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now,
            language,
            f"{siglum} — {title}",
            str(file_path),
            status,
            tier,
            scores.get("confidence", 0.96),
            "Initial Corpus Audit",
            summary,
            gk_json,
        ),
    )


def seed_default_witnesses(conn: sqlite3.Connection) -> None:
    """Register existing workspace witnesses and quarantine Tier 5 NC/copyrighted files."""
    seeds = [
        # === GREEK OT ADMITTED (Tiers 1-4) ===
        (
            "grk-swete-lxx",
            "greek",
            "OT",
            "Swete (B/A/א)",
            "Swete Septuagint Diplomatic Uncial Text (Cambridge 1909–1930)",
            1,
            "ADMITTED",
            "Public Domain / CC BY-SA 4.0",
            "4th–5th c. CE Uncials (ed. 1909–1930)",
            "Diplomatic Uncial (Codex Vaticanus B; Alexandrinus A in Gen 1:1–46:28a)",
            0.90,
            "swete_clean",
            GREEK_RESEARCH_ROOT / "01_Tier1_Modern_Critical_Open" / "OT_LXX_Swete_Clean" / "data",
            "ADMITTED (Tier 1, weighted just below First1KGreek): a converted copy of the First1KGreek Swete files, so the two count as one edition. Swete prints Codex Vaticanus (B), with Alexandrinus (A) where B is lost. Its conversion adds a few slips of its own (Τυρίου for Κυρίου, split words, stray psalm-title verses), so the Amicarelli transcription (Swete-Amicarelli), then First1KGreek, supplies the spelling. In Isaiah its file is Ottley's Codex A, so it is left out of Isaiah.",
            {"license_safe": 1.0, "independence": 0.96, "quality": 0.98, "confidence": 0.98},
        ),
        (
            "grk-1st1k-lxx",
            "greek",
            "OT",
            "1st1K-LXX",
            "First1KGreek Septuagint EpiDoc TEI-XML (tlg0527)",
            1,
            "ADMITTED",
            "CC BY-SA 4.0",
            "4th–5th c. CE (Leipzig EpiDoc 2015)",
            "Diplomatic Uncial TEI-XML with Marginal Witness Sigla",
            0.92,
            "first1k_tei",
            GREEK_RESEARCH_ROOT / "01_Tier1_Modern_Critical_Open" / "OT_LXX_First1KGreek_tlg0527" / "data" / "tlg0527",
            "ADMITTED (Tier 1 XML Witness): Open-license EpiDoc TEI-XML of Swete's edition — the source from which Swete Clean is derived, so the two count as one edition and never double-vote.",
            {"license_safe": 0.98, "independence": 0.85, "quality": 0.97, "confidence": 0.96},
        ),
        (
            "grk-swete-csv",
            "greek",
            "OT",
            "Swete-Amicarelli",
            "Swete Septuagint — Amicarelli transcription (BibleWorks text; LXX-Swete-1930 CSV)",
            1,
            "ADMITTED",
            "GPL-3.0",
            "4th–5th c. CE Uncials (ed. 1909–1930; digital transcription by P. Amicarelli)",
            "Diplomatic Uncial (Codex Vaticanus B; Alexandrinus A in Gen 1:1–46:28a) — keyed transcription, not OCR",
            0.93,
            "swete_csv",
            GREEK_RESEARCH_ROOT / "01_Tier1_Modern_Critical_Open" / "OT_LXX_Swete_CSV",
            "ADMITTED (Tier 1, highest weight of the Swete edition; GPL-3.0 accepted by the owner on 17 Nov 2026): an independent transcription of Swete's edition, keyed rather than OCR'd, so it does not share the misreadings of First1KGreek and Swete Clean. The three are one edition and vote once; this copy supplies the spelling where it has the chapter, and where the copies disagree the one another edition supports is kept (else this one). Its Isaiah is Swete's own (Codex B), so it votes in Isaiah. Not used: books outside the catalogue, the Old Greek Daniel, Sirach's prologue, and verses it leaves empty.",
            {"license_safe": 0.95, "independence": 0.97, "quality": 0.99, "confidence": 0.97},
        ),
        (
            "grk-brenton-sixtine",
            "greek",
            "OT",
            "Sixtine/Brenton",
            "Sixtine-Vaticanus Septuagint (1587 / Brenton 1851 USFM)",
            2,
            "ADMITTED",
            "Public Domain",
            "1587 Sixtine / 1851 Brenton",
            "Sixtine Ecclesiastical & Vaticanus Printed Tradition",
            0.84,
            "brenton_usfm",
            GREEK_RESEARCH_ROOT / "02_Tier2_Historic_Critical_PD" / "OT_Brenton_LXX_USFM",
            "ADMITTED (Tier 2 Historic Printed Witness): Public-domain Sixtine/Brenton edition supplying Vaticanus-family & minuscules readings where Codex Alexandrinus diverges (crucial in Genesis 1–46 where Vaticanus is lacunose!).",
            {"license_safe": 1.0, "independence": 0.91, "quality": 0.95, "confidence": 0.97},
        ),
        (
            "grk-lxx-orthodox",
            "greek",
            "OT",
            "LXX-Orthodox (Οʹ)",
            "Orthodox Ecclesiastical Septuagint (Η Παλαιά Διαθήκη κατά τους Εβδομήκοντα)",
            3,
            "ADMITTED",
            "Public Domain",
            "1587 Sixtine / Athens Ecclesiastical Majority Tradition",
            "Greek Orthodox Ecclesiastical / Majority Septuagint",
            0.42,
            "ebible_usfm_dir",
            GREEK_RESEARCH_ROOT / "03_Tier3_Byzantine_TR_PD" / "OT_LXX_Orthodox_Ecclesiastical_USFM",
            "ADMITTED (Tier 3 Ecclesiastical LXX Majority Witness): Public-domain polytonic Greek Orthodox Septuagint across all 43 Old Greek and Deuterocanonical books, preserving Athens/Sixtine ecclesiastical and Lucianic-attested readings in the apparatus while weighted alongside Brenton below 4th-c. Vaticanus (Swete).",
            {"license_safe": 1.0, "independence": 0.86, "quality": 0.96, "confidence": 0.97},
        ),
        # === GREEK NT ADMITTED (Tiers 1-4) ===
        (
            "grk-nt-cntr-01",
            "greek",
            "NT",
            "א (01)",
            "Codex Sinaiticus Direct Transcription (CNTR Early MSS)",
            4,
            "ADMITTED",
            "CC BY-SA 4.0",
            "4th c. CE (c. 330–360 CE)",
            "Alexandrian / Western Mixed Uncial",
            0.96,
            "cntr_mss",
            GREEK_RESEARCH_ROOT / "04_Tier4_Ancient_Manuscripts" / "NT_CNTR_Early_MSS" / "class 1" / "01.txt",
            "ADMITTED (Tier 4 Primary Uncial): Direct open-license transcription of 4th-century Codex Sinaiticus across the New Testament.",
            {"license_safe": 0.98, "independence": 0.99, "quality": 0.96, "confidence": 0.99},
        ),
        (
            "grk-nt-cntr-03",
            "greek",
            "NT",
            "B (03)",
            "Codex Vaticanus Direct Transcription (CNTR Early MSS)",
            4,
            "ADMITTED",
            "CC BY-SA 4.0",
            "4th c. CE (c. 300–325 CE)",
            "Premier Alexandrian Uncial",
            0.98,
            "cntr_mss",
            GREEK_RESEARCH_ROOT / "04_Tier4_Ancient_Manuscripts" / "NT_CNTR_Early_MSS" / "class 1" / "03.txt",
            "ADMITTED (Tier 4 Premier Uncial): Highest-weight 4th-century Alexandrian manuscript transcription (Codex Vaticanus).",
            {"license_safe": 0.98, "independence": 1.0, "quality": 0.97, "confidence": 0.99},
        ),
        (
            "grk-nt-srgnt",
            "greek",
            "NT",
            "SRGNT",
            "Statistical Restoration Greek New Testament (CNTR 2022)",
            1,
            "ADMITTED",
            "CC BY 4.0",
            "2022 Modern Critical",
            "Earliest-Manuscript Statistical Critical Edition",
            0.95,
            "cntr_edition",
            GREEK_RESEARCH_ROOT / "01_Tier1_Modern_Critical_Open" / "NT_SRGNT_CNTR" / "SR.txt",
            "ADMITTED (Tier 1 Critical Edition): Fully open CC BY 4.0 critical NT reconstructed directly from pre-400 CE papyri and uncials.",
            {"license_safe": 1.0, "independence": 0.94, "quality": 0.99, "confidence": 0.99},
        ),
        (
            "grk-nt-sblgnt",
            "greek",
            "NT",
            "SBLGNT",
            "SBL Greek New Testament & Apparatus (Holmes 2010)",
            1,
            "ADMITTED",
            "CC BY 4.0",
            "2010 Modern Critical",
            "Reasoned Eclectic Critical Edition",
            0.94,
            "sblgnt_txt",
            GREEK_RESEARCH_ROOT / "01_Tier1_Modern_Critical_Open" / "NT_SBLGNT_Logos" / "data" / "sblgnt" / "text",
            "ADMITTED (Tier 1 Reasoned Eclectic Edition): CC BY 4.0 reasoned-eclectic edition with full variant apparatus.",
            {"license_safe": 1.0, "independence": 0.93, "quality": 0.99, "confidence": 0.98},
        ),
        (
            "grk-nt-nestle1904",
            "greek",
            "NT",
            "Nestle1904",
            "Eberhard Nestle Greek New Testament (1904)",
            2,
            "ADMITTED",
            "Public Domain",
            "1904 Consensus Critical",
            "Tischendorf / Westcott-Hort / Weymouth Consensus",
            0.90,
            "nestle_csv",
            GREEK_RESEARCH_ROOT / "02_Tier2_Historic_Critical_PD" / "NT_Nestle_1904" / "morph" / "Nestle1904.csv",
            "ADMITTED (Tier 2 Historic Critical Witness): Public-domain consensus critical text of Tischendorf, Westcott-Hort, and Weymouth.",
            {"license_safe": 1.0, "independence": 0.90, "quality": 0.98, "confidence": 0.97},
        ),
        (
            "grk-nt-bhp",
            "greek",
            "NT",
            "BHP",
            "Bunning Heuristic Prototype GNT (CNTR)",
            1,
            "ADMITTED",
            "CC BY 4.0",
            "2022 Algorithmic Critical",
            "Algorithmic Alexandrian/Early Witness Reconstruction",
            0.88,
            "cntr_edition",
            GREEK_RESEARCH_ROOT / "01_Tier1_Modern_Critical_Open" / "NT_BHP_CNTR" / "BHP.txt",
            "ADMITTED (Tier 1 Secondary Critical Check): Independent CC BY 4.0 heuristic reconstruction.",
            {"license_safe": 1.0, "independence": 0.85, "quality": 0.97, "confidence": 0.96},
        ),
        (
            "grk-nt-rp2018",
            "greek",
            "NT",
            "RP2018 (Byz)",
            "Robinson–Pierpont Byzantine Textform (2018)",
            3,
            "ADMITTED",
            "Public Domain / Unlicense",
            "2018 Byzantine Majority",
            "Byzantine / Majority Ecclesiastical Tradition",
            0.72,
            "rp_csv",
            GREEK_RESEARCH_ROOT / "03_Tier3_Byzantine_TR_PD" / "NT_Robinson_Pierpont_2018" / "csv-unicode" / "ccat" / "no-variants",
            "ADMITTED (Tier 3 Byzantine Witness): Public-domain representative of the Byzantine Majority stream; weighted lower than 4th-c. Alexandrian codices under Reasoned Eclecticism, recorded systematically in apparatus.",
            {"license_safe": 1.0, "independence": 0.92, "quality": 0.98, "confidence": 0.98},
        ),
        (
            "grk-nt-tcgnt",
            "greek",
            "NT",
            "TCGNT (Byz)",
            "The Text-Critical Greek New Testament: Byzantine Text (Robert Adam Boyd)",
            3,
            "ADMITTED",
            "Public Domain",
            "2024–2026 Byzantine Majority",
            "Byzantine Majority Manuscript Collation (TuT / ECM / Hoskier)",
            0.68,
            "ebible_usfm_dir",
            GREEK_RESEARCH_ROOT / "03_Tier3_Byzantine_TR_PD" / "NT_TCGNT_USFM",
            "ADMITTED (Tier 3 Byzantine Majority Witness): Public-domain polytonic Byzantine Majority GNT compiled from Text und Textwert, ECM, and Hoskier collations rather than Von Soden's apparatus.",
            {"license_safe": 1.0, "independence": 0.90, "quality": 0.99, "confidence": 0.98},
        ),
        (
            "grk-nt-pt1904",
            "greek",
            "NT",
            "PT1904 (Byz)",
            "1904 Ecumenical Patriarchal Greek New Testament (Basileios Antoniades)",
            3,
            "ADMITTED",
            "Public Domain",
            "1904 / 1912 Patriarchal Majority",
            "Constantinopolitan Lectionary & Byzantine Ecclesiastical Majority",
            0.65,
            "ebible_usfm_dir",
            GREEK_RESEARCH_ROOT / "03_Tier3_Byzantine_TR_PD" / "NT_Patriarchal_1904_USFM",
            "ADMITTED (Tier 3 Orthodox Patriarchal Majority Witness): Official 1904/1912 polytonic Greek New Testament of the Ecumenical Patriarchate of Constantinople (Antoniades), representing the Constantinopolitan lectionary and ecclesiastical Byzantine tradition.",
            {"license_safe": 1.0, "independence": 0.89, "quality": 0.98, "confidence": 0.98},
        ),
        (
            "grk-nt-kjtr",
            "greek",
            "NT",
            "TR (KJTR)",
            "Textus Receptus (CNTR KJTR Collation)",
            3,
            "ADMITTED",
            "CC BY 4.0",
            "16th–19th c. Printed TR",
            "Reformation Textus Receptus Tradition",
            0.60,
            "cntr_edition",
            GREEK_RESEARCH_ROOT / "03_Tier3_Byzantine_TR_PD" / "NT_KJTR_CNTR" / "KJTR.txt",
            "ADMITTED (Tier 3 TR Apparatus Witness): Open CC BY 4.0 Textus Receptus witness retained for apparatus documentation of historic TR readings; votes once in the tr_edition family.",
            {"license_safe": 1.0, "independence": 0.78, "quality": 0.97, "confidence": 0.97},
        ),
        (
            "grk-nt-tr-scrivener",
            "greek",
            "NT",
            "TR-Scrivener (1894)",
            "Scrivener Textus Receptus (Cambridge 1894 Polytonic Edition)",
            3,
            "ADMITTED",
            "Public Domain / GPL-3.0",
            "1881–1894 Printed TR",
            "Beza 1598 / KJV-Underlying Textus Receptus",
            0.59,
            "scrivener_json",
            GREEK_RESEARCH_ROOT / "03_Tier3_Byzantine_TR_PD" / "NT_TR_Scrivener_1894_Polytonic" / "gnt.flat.json",
            "ADMITTED (Tier 3 Printed TR Witness): F. H. A. Scrivener's 1894 polytonic Textus Receptus; grouped in tr_edition so the printed Textus Receptus family votes once.",
            {"license_safe": 0.96, "independence": 0.76, "quality": 0.98, "confidence": 0.97},
        ),
        (
            "grk-nt-tr-boyd",
            "greek",
            "NT",
            "TR-Boyd (Elz/Scr/Steph)",
            "Polytonic Textus Receptus (Stephanus 1550 / Elzevir 1624 / Scrivener 1894)",
            3,
            "ADMITTED",
            "Public Domain",
            "1550–1894 Printed TR",
            "Reformation Printed Textus Receptus",
            0.58,
            "ebible_usfm_dir",
            GREEK_RESEARCH_ROOT / "03_Tier3_Byzantine_TR_PD" / "NT_TR_Boyd_USFM",
            "ADMITTED (Tier 3 Printed TR Witness): Public-domain polytonic Textus Receptus prepared by Adam Boyd; grouped in tr_edition so the printed TR family votes once.",
            {"license_safe": 1.0, "independence": 0.75, "quality": 0.98, "confidence": 0.97},
        ),

        # === GREEK QUARANTINED / DISREGARDED BY GATEKEEPER (Tier 5) ===
        (
            "grk-quarantine-rahlfs",
            "greek",
            "OT",
            "Rahlfs1935 [QUARANTINED]",
            "Rahlfs Septuaginta 1935 Suite (Deutsche Bibelgesellschaft)",
            5,
            "QUARANTINED_NC",
            "Copyrighted / Study-Only (Tier 5)",
            "1935 Printed Edition",
            "Eclectic LXX (Restricted License)",
            0.0,
            "quarantined",
            GREEK_RESEARCH_ROOT / "05_Tier5_Quarantined_Study_Only" / "OT_LXX_Rahlfs_1935_Suite",
            "DISREGARDED FROM OPEN CRITICAL TEXT (Tier 5 Quarantine): Protected editorial edition (Deutsche Bibelgesellschaft). Blocked from direct ingestion to guarantee 100% clean open-source copyright status for the Saints Critical Text.",
            {"license_safe": 0.05, "independence": 0.90, "quality": 0.95, "confidence": 0.99},
        ),
        (
            "grk-quarantine-pickering",
            "greek",
            "NT",
            "Pickering-f35 [QUARANTINED]",
            "Pickering Family 35 Greek NT (CC BY-NC-ND)",
            5,
            "QUARANTINED_NC",
            "CC BY-NC-ND (NonCommercial-NoDerivatives)",
            "2020 Family 35 Minuscules",
            "Kr / Family 35 Byzantine Sub-type",
            0.0,
            "quarantined",
            GREEK_RESEARCH_ROOT / "05_Tier5_Quarantined_Study_Only" / "NT_Pickering_Family35_NC_ND",
            "DISREGARDED FROM OPEN CRITICAL TEXT (Tier 5 Quarantine): Carries NonCommercial-NoDerivatives (CC BY-NC-ND) restriction prohibiting derivative critical editions.",
            {"license_safe": 0.0, "independence": 0.70, "quality": 0.92, "confidence": 0.99},
        ),
        (
            "grk-quarantine-sinaiticus-xml",
            "greek",
            "OT/NT",
            "CSP-XML [NC-NOTICE]",
            "Codex Sinaiticus Project Full TEI-XML v1.95 (CC BY-NC-SA Header)",
            5,
            "QUARANTINED_NC",
            "CC BY-NC-SA (Header Notice Detected)",
            "4th c. CE MS / 2024 XML",
            "Full Pandect TEI-XML",
            0.0,
            "sinaiticus_tei",
            GREEK_RESEARCH_ROOT / "04_Tier4_Ancient_Manuscripts" / "OT_NT_Codex_Sinaiticus" / "sinaiticus_full_v195.xml",
            "AI GATEKEEPER CATCH — QUARANTINED BY DEFAULT: Although placed in Tier 4, XML header <availability> declares CC BY-NC-SA (NonCommercial). CNTR CC BY-SA 01.txt is used instead for clean open-license NT Sinaiticus collation; enable only if ShareAlike/NC is acceptable.",
            {"license_safe": 0.25, "independence": 0.99, "quality": 0.98, "confidence": 0.97},
        ),

        # === HEBREW ADMITTED & GATEKEEPER CATCHES (Priority 2) ===
        (
            "heb-mam-aleppo",
            "hebrew",
            "OT",
            "MAM (Aleppo)",
            "Miqra 'al-pi ha-Mesorah (Aleppo Codex Tradition, OSIS XML)",
            1,
            "ADMITTED",
            "CC BY-SA 3.0",
            "c. 920 CE Aleppo Codex / Tiberian Masorah",
            "Ben Asher Tiberian Masoretic (Aleppo-Weighted)",
            0.98,
            "mam_osis",
            HEBREW_RESEARCH_ROOT / "hebrew-base" / "MAPM_Masorah.xml",
            "ADMITTED (Tier 1 Premier Masoretic Witness): Open-license critical Masoretic edition anchored on the Aleppo Codex (Keter Aram Tzova) and close Tiberian codices, preserving Masoretic large/small letters and Ketiv/Qere.",
            {"license_safe": 0.98, "independence": 0.99, "quality": 0.99, "confidence": 0.99},
        ),
        (
            "heb-wlc-tsv",
            "hebrew",
            "OT",
            "WLC (L)",
            "Westminster Leningrad Codex (Firkovich B 19A, 1008 CE)",
            1,
            "ADMITTED",
            "Public Domain",
            "1008 CE Tiberian Masoretic Codex",
            "Ben Asher Tiberian Masoretic (Leningradensis)",
            0.96,
            "wlc_tsv",
            HEBREW_RESEARCH_ROOT / "hebrew-base" / "OT_WLC_39Books_Raw.tsv",
            "ADMITTED (Tier 1 Complete Dated Codex): Public-domain diplomatic transcription of Codex Leningradensis (1008 CE), essential where Aleppo leaves are missing (e.g., Torah).",
            {"license_safe": 1.0, "independence": 0.96, "quality": 0.99, "confidence": 0.99},
        ),
        (
            "heb-benchayyim-1525",
            "hebrew",
            "OT",
            "BenChayyim (1525)",
            "Jacob ben Chayyim Masoretic Majority Text (Second Rabbinic Bible Tradition)",
            3,
            "ADMITTED",
            "Public Domain",
            "1524–1525 Venice Bomberg / Medieval Masoretic Majority",
            "Medieval Masoretic Majority / Rabbinic Bible Textus Receptus",
            0.78,
            "ebible_hebrew_usfm_dir",
            HEBREW_RESEARCH_ROOT / "03_Tier3_Samaritan_Traditional_PD" / "OT_BenChayyim_Masoretic_USFM",
            "ADMITTED (Tier 3 Masoretic Majority Witness): Public-domain pointed and cantillated Masoretic text following Jacob ben Chayyim's Second Rabbinic Bible (1524–1525), representing the late medieval Hebrew manuscript majority (e.g. דַּכָּא in Deut 23:2).",
            {"license_safe": 1.0, "independence": 0.90, "quality": 0.97, "confidence": 0.98},
        ),
        (
            "heb-letteris-1852",
            "hebrew",
            "OT",
            "Letteris (1852)",
            "Meir Halevi Letteris Masoretic Hebrew Bible (1852 / 1866 Edition)",
            3,
            "ADMITTED",
            "Public Domain / GPL-3.0",
            "1852–1866 Traditional Masoretic Majority",
            "Van der Hooght / Ben Chayyim / Erfurt Masoretic Majority",
            0.76,
            "letteris_utf8",
            HEBREW_RESEARCH_ROOT / "03_Tier3_Samaritan_Traditional_PD" / "OT_Letteris_1852_UTF8",
            "ADMITTED (Tier 3 Traditional Masoretic Majority Witness): Meir Halevi Letteris's classic 1852/1866 pointed and cantillated Hebrew Bible across all 39 books, bridging the Ben Chayyim/Van der Hooght majority print tradition and medieval codices.",
            {"license_safe": 0.96, "independence": 0.88, "quality": 0.98, "confidence": 0.98},
        ),
        (
            "heb-leningrad-usfx-corrupt",
            "hebrew",
            "OT",
            "Leningrad-USFX [DISREGARDED]",
            "eBible Leningrad USFX Build (heb-leningrad.usfx.xml)",
            0,
            "DISREGARDED_CORRUPT",
            "Public Domain",
            "1008 CE (Defective XML Export)",
            "Corrupted Word-Boundary Export",
            0.0,
            "usfx_xml",
            HEBREW_RESEARCH_ROOT / "hebrew-base" / "heb-leningrad.usfx.xml",
            "AI GATEKEEPER CATCH — DISREGARDED (Corrupt Transcription): Word-boundary spaces were stripped during upstream USFX export and '/' morpheme dividers remain glued inside tokens (e.g., בִּ/שְׁנַ֤תשְׁתַּ֙יִם֙). Superseded by clean WLC TSV and MAM OSIS XML.",
            {"license_safe": 1.0, "independence": 0.15, "quality": 0.12, "confidence": 0.99},
        ),

        # === LATIN ADMITTED (Priority 3) ===
        (
            "lat-amiatinus",
            "latin",
            "OT/NT",
            "Amiatinus (A)",
            "Codex Amiatinus — Digital Latin Library TEI transcription (Genesis only)",
            2,
            "ADMITTED",
            "CC BY-SA 4.0 (Digital Latin Library transcription)",
            "c. 700 CE Northumbrian Hieronymian Pandect",
            "Early Hieronymian Vulgate (Pre-Sixto-Clementine)",
            0.97,
            "amiatinus_tei",
            LATIN_RESEARCH_ROOT / "latin-base" / "0011r-genesis.xml",
            "ADMITTED (Tier 2 Premier Early Vulgate Pandect): Oldest surviving complete Latin Bible manuscript (c. 700 CE); the local transcription covers Genesis only. In this file the source sigla #c, #r and #s name printed editions (Hetzenauer's Clementine 1906, the Rome Vulgate 1926–95, the Stuttgart Vulgate 2007), not scribal hands; the Studio reads the manuscript's own text (<lem>, <sic>/<orig>, scribal additions) and never substitutes an edition's reading or editor-supplied text.",
            {"license_safe": 0.99, "independence": 1.0, "quality": 0.98, "confidence": 0.99},
        ),
        (
            "lat-clementine-usfx",
            "latin",
            "OT/NT",
            "Clem1598-USFX",
            "Sixto-Clementine Vulgate (1598 Official Edition, USFX)",
            1,
            "ADMITTED",
            "Public Domain",
            "1592–1598 CE Printed Ecclesiastical Edition",
            "Sixto-Clementine Ecclesiastical Majority Vulgate",
            0.88,
            "usfx_xml",
            LATIN_RESEARCH_ROOT / "latin-base" / "lat-clementine.usfx.xml",
            "ADMITTED (Tier 1 Complete 70-Book Latin Majority Witness): Public-domain Sixto-Clementine Vulgate covering all 70 books; leads the clementine_edition family.",
            {"license_safe": 1.0, "independence": 0.92, "quality": 0.97, "confidence": 0.98},
        ),
        (
            "lat-vulg-hetzenauer",
            "latin",
            "OT/NT",
            "VulgHetzenauer (1906)",
            "Vulgata Clementina — Michael Hetzenauer Critical Edition (Innsbruck 1906)",
            1,
            "ADMITTED",
            "Public Domain",
            "1592 / 1906 Critical Sixto-Clementine",
            "Sixto-Clementine Ecclesiastical Majority Vulgate",
            0.53,
            "scrollmapper_csv",
            LATIN_RESEARCH_ROOT / "01_Tier1_Open_Vulgate_Base_Texts" / "OT_NT_Multi_Vulgate_DB" / "formats" / "csv" / "VulgHetzenauer.csv",
            "ADMITTED (Tier 1 Critical Clementine Majority Witness): Michael Hetzenauer's 1906 critical edition of the Sixto-Clementine Majority Vulgate across all 70 books; votes once in clementine_edition.",
            {"license_safe": 1.0, "independence": 0.85, "quality": 0.99, "confidence": 0.98},
        ),
        (
            "lat-saints-staging",
            "latin",
            "OT/NT",
            "Clem-Saints",
            "Saints.Bible Latin column (Clementine Vulgate, Saints.Bible numbering)",
            1,
            "ADMITTED",
            "Public Domain",
            "1598 / 2026 Audited",
            "Sixto-Clementine (VulSearch Normalized)",
            0.86,
            "latin_saints_json",
            LATIN_TRANSLATION_ROOT,
            "ADMITTED (Tier 1 numbering anchor): The Clementine Latin as shown on Saints.Bible, numbered like the site. Same edition as Clem1598-USFX, so the family votes once together; it defines Latin verse numbering and other Latin witnesses are re-aligned to it by content.",
            {"license_safe": 1.0, "independence": 0.80, "quality": 0.98, "confidence": 0.97},
        ),
        (
            "lat-vulg-conte",
            "latin",
            "OT/NT",
            "VulgConte (2009)",
            "Vulgata Clementina — Conte SacredBible Edition (2009)",
            3,
            "ADMITTED",
            "Public Domain",
            "1598 / 2009 Public Domain Clementine",
            "Sixto-Clementine Ecclesiastical Majority Vulgate",
            0.51,
            "scrollmapper_csv",
            LATIN_RESEARCH_ROOT / "01_Tier1_Open_Vulgate_Base_Texts" / "OT_NT_Multi_Vulgate_DB" / "formats" / "csv" / "VulgConte.csv",
            "ADMITTED (Tier 3 Clementine Majority Check): Ronald L. Conte Jr.'s Public Domain Sixto-Clementine Vulgate across all 70 books; votes once in clementine_edition.",
            {"license_safe": 1.0, "independence": 0.78, "quality": 0.97, "confidence": 0.97},
        ),
        (
            "lat-vulg-sistina",
            "latin",
            "OT/NT",
            "VulgSistina (1590)",
            "Vulgata Sistina (Pope Sixtus V Official Edition, Rome 1590)",
            3,
            "ADMITTED",
            "Public Domain",
            "1590 Pre-Clementine Printed Vulgate",
            "Sixtine / Louvain-Tridentine Latin Vulgate Tradition",
            0.42,
            "scrollmapper_csv",
            LATIN_RESEARCH_ROOT / "01_Tier1_Open_Vulgate_Base_Texts" / "OT_NT_Multi_Vulgate_DB" / "formats" / "csv" / "VulgSistine.csv",
            "ADMITTED (Tier 3 Historic Vulgate Witness): Pope Sixtus V's independent 1590 Rome Vulgate across all 70 books, documenting pre-1592 Sixtine/Louvain readings (e.g. Gen 1:2 Spiritus Domini, Lam 1:3 Iuda) in the apparatus.",
            {"license_safe": 1.0, "independence": 0.88, "quality": 0.96, "confidence": 0.97},
        ),
        (
            "lat-quarantine-stuttgart",
            "latin",
            "OT/NT",
            "Stuttgart-BSV [QUARANTINED]",
            "Unpunctuated Critical Vulgate CSV (Weber–Gryson Stuttgart Text Detected)",
            5,
            "QUARANTINED_NC",
            "Copyrighted Edition Detected (Tier 5)",
            "20th–21st c. Critical Edition",
            "Weber–Gryson Stuttgart Critical Vulgate",
            0.0,
            "quarantined",
            LATIN_RESEARCH_ROOT / "01_Tier1_Open_Vulgate_Base_Texts" / "OT_NT_Multi_Vulgate_DB" / "formats" / "csv" / "Vulgate.csv",
            "AI GATEKEEPER CATCH — QUARANTINED BY DEFAULT: Although upstream database metadata labelled Vulgate.csv Public Domain, test loci (Gen 1:2, Gen 3:15, Matt 6:13, 1 John 5:7–8) match the copyrighted Deutsche Bibelgesellschaft Stuttgart Vulgate. Blocked from open collation.",
            {"license_safe": 0.05, "independence": 0.95, "quality": 0.98, "confidence": 0.99},
        ),
    ]

    stored = conn.execute("SELECT value FROM meta WHERE key = 'seed_version'").fetchone()
    stored_version = int(stored["value"]) if stored else 0
    has_rows = conn.execute("SELECT COUNT(*) AS n FROM witnesses").fetchone()["n"] > 0
    refresh = has_rows and stored_version < SEED_VERSION
    for row in seeds:
        _seed_row(conn, *row, refresh=refresh)
    if refresh:
        conn.execute(
            """
            INSERT INTO gatekeeper_log (
                created_at, language, witness_title, file_path, decision,
                tier_assigned, confidence, model_used, summary, details_json
            ) VALUES (?, 'all', 'Built-in witness catalogue', '', 'CATALOGUE_REFRESH', 0, 1.0, 'Studio upgrade', ?, '{}')
            """,
            (
                utc_now(),
                f"Built-in witness descriptions refreshed to catalogue v{SEED_VERSION} "
                "(v7: the Majority/Ecclesiastical editions are apparatus-only witnesses (catalog.APPARATUS_ONLY), so the weights changed for them in v6 are restored: Sixtine/Brenton 0.84, Clem1598-USFX 0.88, Clem-Saints 0.86, Amiatinus 0.97; v6: added trilingual Majority/Ecclesiastical witnesses — Greek TCGNT, Patriarchal 1904, "
                "Scrivener 1894 TR, Boyd TR, and Orthodox LXX; Hebrew Ben Chayyim 1525 and Letteris 1852; "
                "Latin Hetzenauer 1906, Conte 2009, and Sixtine 1590, plus Gatekeeper quarantine on Stuttgart CSV). "
                "Witnesses with a human override were left unchanged.",
            ),
        )
    conn.execute(
        "INSERT INTO meta (key, value) VALUES ('seed_version', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(SEED_VERSION),),
    )
