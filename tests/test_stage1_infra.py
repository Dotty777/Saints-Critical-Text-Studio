"""Stage 1 infrastructure regression tests (AGENTS.md Invariant #1 compliant).

Sets CTS_DATA_DIR and CTS_OUTPUT_ROOT to an isolated temporary sandbox BEFORE importing
``studio``, so real data/studio.db and Saints-*-Critical-Text/ are never modified.

Covers:
1. studio/exporter.py open-licence Tier-5 scrubber (chapter + verse-level fields including
   verses[*].apparatus_witnesses, witness_readings, absent_witnesses, witness_refs,
   apparatus, disregarded, versification_notes, MD/JSON/TSV), while preserving local full exports.
2. studio/concordance_gold.py + studio/concordance.py full-corpus coverage in manifest.json,
   CONCORDANCE_REPORT.md, and dashboard stats even after a single-book incremental build.
3. studio/concordance_align.py git ancestry verification helper (is_ancestor / resolve_ref).
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

# AGENTS.md Invariant #1: point Studio at an isolated sandbox BEFORE importing studio.
_OWN_SANDBOX: str | None = None
if "CTS_DATA_DIR" not in os.environ or "CTS_OUTPUT_ROOT" not in os.environ:
    _OWN_SANDBOX = tempfile.mkdtemp(prefix="cts_stage1_infra_")
    os.environ["CTS_DATA_DIR"] = os.path.join(_OWN_SANDBOX, "data")
    os.environ["CTS_OUTPUT_ROOT"] = os.path.join(_OWN_SANDBOX, "out")

_TEST_WORKDIR = Path(tempfile.mkdtemp(prefix="cts_stage1_infra_work_"))

from studio import concordance_align as al  # noqa: E402
from studio import db as studio_db  # noqa: E402
from studio.catalog import BOOKS_BY_SLUG, STUDIO_ROOT  # noqa: E402
from studio.concordance_gold import _corpus_coverage, gold_stats  # noqa: E402
from studio.db import get_conn  # noqa: E402
from studio.engine import CriticalTextEngine  # noqa: E402
from studio.exporter import (  # noqa: E402
    KNOWN_TIER5_SIGLA,
    TIER5_EXCLUDED_STATUS,
    export_chapter_files,
    is_tier5_witness,
    scrub_chapter_for_open_export,
    scrub_chapter_json_for_open_export,
)


def tearDownModule() -> None:
    shutil.rmtree(_TEST_WORKDIR, ignore_errors=True)
    if _OWN_SANDBOX:
        shutil.rmtree(_OWN_SANDBOX, ignore_errors=True)


def _corpora_available() -> bool:
    try:
        from studio.lexica import greek, hebrew, latin

        g = greek.corpora_available()
        ok_g = all(g.values()) if isinstance(g, dict) else bool(g)
        return bool(hebrew.corpora_available()) and ok_g and latin.ls_path().exists()
    except Exception:
        return False


CORPORA = _corpora_available()


class TestOpenLicenceExporterScrubbing(unittest.TestCase):
    def _sample_chapter_inputs(self):
        admitted = [
            {
                "siglum": "Clem1598-USFX",
                "title": "Sixto-Clementine Vulgate (1598)",
                "tier": 1,
                "weight": 0.88,
                "license": "Public Domain",
                "text_type": "Sixto-Clementine",
                "status": "ADMITTED",
            },
            {
                "siglum": "Clem-Saints",
                "title": "Saints.Bible Latin column",
                "tier": 1,
                "weight": 0.86,
                "license": "Public Domain",
                "text_type": "Sixto-Clementine",
                "status": "ADMITTED",
            },
        ]
        apparatus = [
            {
                "siglum": "Amiatinus (A)",
                "title": "Codex Amiatinus",
                "tier": 2,
                "license": "CC BY-SA 4.0",
                "text_type": "Early Vulgate",
                "status": "ADMITTED",
            },
            {
                "siglum": "VulgHetzenauer (1906)",
                "title": "Hetzenauer Clementina 1906",
                "tier": 1,
                "license": "Public Domain",
                "text_type": "Sixto-Clementine",
                "status": "ADMITTED",
            },
            {
                "siglum": "Stuttgart-BSV",
                "title": "Weber-Gryson Stuttgart Vulgate",
                "tier": 5,
                "license": "Copyrighted Edition (Tier 5)",
                "text_type": "Critical Vulgate",
                "status": "ADMITTED",
            },
            {
                "siglum": "VL 5 (d)",
                "title": "Codex Bezae Old Latin",
                "tier": 5,
                "license": "CC BY-NC-SA 3.0",
                "text_type": "Old Latin",
                "status": "ADMITTED",
            },
            {
                "siglum": "VL 2 (e)",
                "title": "Codex Palatinus Old Latin John",
                "tier": 5,
                "license": "CC BY-NC-SA",
                "text_type": "Old Latin",
                "status": "ADMITTED",
            },
            {
                "siglum": "Custom-NC-Witness",
                "title": "Hypothetical Future Tier 5 Witness",
                "tier": 5,
                "license": "CC BY-NC 4.0",
                "text_type": "Study-Only",
                "status": "ADMITTED",
            },
        ]
        vers_notes = [
            "Amiatinus (A): 1:2 re-aligned by content",
            "VL 2 (e): 1:44 not collated (wording does not match)",
            "Stuttgart-BSV: orthographic spacing note",
            "Custom-NC-Witness: 1:1 split note",
        ]
        verse_rows = [
            {
                "id": 1,
                "verse": 1,
                "critical_text": "In principio erat Verbum.",
                "confidence": 0.99,
                "decision_source": "Textual Analysis Brain",
                "witness_readings": {
                    "Clem1598-USFX": "In principio erat Verbum.",
                    "Clem-Saints": "In principio erat Verbum.",
                    "Amiatinus (A)": "In principio erat uerbum.",
                    "VulgHetzenauer (1906)": "In principio erat Verbum.",
                    "Stuttgart-BSV": "in principio erat Verbum",
                    "VL 5 (d)": "in principio erat sermo",
                    "VL 2 (e)": "in principio erat sermo",
                    "Custom-NC-Witness": "in principio fuit verbum",
                },
                "absent_witnesses": ["VL 14 (r¹)"],
                "witness_refs": {"Amiatinus (A)": "1:1", "Stuttgart-BSV": "1:1", "VL 5 (d)": "1:1"},
                "apparatus_witnesses": [
                    "Amiatinus (A)",
                    "Custom-NC-Witness",
                    "Stuttgart-BSV",
                    "VL 2 (e)",
                    "VL 5 (d)",
                    "VulgHetzenauer (1906)",
                ],
                "apparatus": [
                    {
                        "lemma": "Verbum",
                        "lemma_witnesses": ["Clem1598-USFX", "Clem-Saints", "Stuttgart-BSV"],
                        "variants": [
                            {"reading": "sermo", "witnesses": ["VL 5 (d)", "VL 2 (e)"]},
                        ],
                        "variant_type": "lexical",
                        "credited_witnesses": ["Stuttgart-BSV"],
                        "analysis": [],
                    },
                    {
                        "lemma": "erat",
                        "lemma_witnesses": ["Clem1598-USFX", "Clem-Saints", "Stuttgart-BSV"],
                        "variants": [
                            {"reading": "fuit", "witnesses": ["Amiatinus (A)", "Custom-NC-Witness"]},
                            {"reading": "est", "witnesses": ["VL 5 (d)"]},
                        ],
                        "variant_type": "lexical",
                        "analysis": [],
                    },
                ],
                "disregarded": [
                    {
                        "kept_form": "Verbum",
                        "disregarded_forms": ["uerbum"],
                        "witnesses": ["Amiatinus (A)", "Stuttgart-BSV"],
                        "reason": "u/v orthography",
                    },
                    {
                        "kept_form": "In",
                        "disregarded_forms": ["in"],
                        "witnesses": ["Stuttgart-BSV"],
                        "reason": "case",
                    },
                ],
                "rationale": "Unanimous across Clem1598-USFX, Clem-Saints.",
                "human_locked": False,
                "analysis": [],
                "needs_review": False,
            }
        ]
        return admitted, apparatus, vers_notes, verse_rows

    def test_is_tier5_witness_classification(self) -> None:
        self.assertTrue(is_tier5_witness({"siglum": "Stuttgart-BSV", "tier": 5, "license": "Copyrighted"}))
        self.assertTrue(is_tier5_witness({"siglum": "Rahlfs (1935)", "tier": 1, "license": "Public Domain"}))
        self.assertTrue(is_tier5_witness({"siglum": "X", "tier": 3, "license": "CC BY-NC-SA 4.0"}))
        self.assertTrue(is_tier5_witness({"siglum": "X", "tier": 1, "status": "QUARANTINED_NC", "license": "PD"}))
        self.assertFalse(is_tier5_witness({"siglum": "Amiatinus (A)", "tier": 2, "license": "CC BY-SA 4.0", "status": "ADMITTED"}))
        # Open-licence file mentioning publisher copyright string is still open (not "copyrighted")
        self.assertFalse(is_tier5_witness({
            "siglum": "B (03)",
            "tier": 4,
            "license": "Copyright Alan Bunning. Released under CC BY-SA 4.0",
            "status": "ADMITTED",
        }))

    def test_open_licence_export_strips_all_tier5_and_preserves_local_export(self) -> None:
        book = BOOKS_BY_SLUG["john"]
        admitted, apparatus, vers_notes, verse_rows = self._sample_chapter_inputs()
        snapshot_before = json.dumps(verse_rows, ensure_ascii=False, sort_keys=True)

        open_root = _TEST_WORKDIR / "open_export"
        local_root = _TEST_WORKDIR / "local_export"

        open_md, open_json, open_tsv = export_chapter_files(
            language="latin",
            book=book,
            chapter=1,
            admitted_witnesses=admitted,
            apparatus_witnesses=apparatus,
            quarantined_witnesses=[],
            verse_rows=verse_rows,
            model_used="Textual Analysis Brain",
            anchor_siglum="Clem1598-USFX",
            base_siglum="Clem1598-USFX",
            versification_notes=vers_notes,
            open_licence_only=True,
            output_root=open_root,
        )
        # Caller inputs must not be mutated
        self.assertEqual(json.dumps(verse_rows, ensure_ascii=False, sort_keys=True), snapshot_before)

        local_md, local_json, local_tsv = export_chapter_files(
            language="latin",
            book=book,
            chapter=1,
            admitted_witnesses=admitted,
            apparatus_witnesses=apparatus,
            quarantined_witnesses=[],
            verse_rows=verse_rows,
            model_used="Textual Analysis Brain",
            anchor_siglum="Clem1598-USFX",
            base_siglum="Clem1598-USFX",
            versification_notes=vers_notes,
            open_licence_only=False,
            output_root=local_root,
        )

        # 1. Open JSON must contain ZERO Tier-5 sigla anywhere (chapter OR verse level)
        open_raw = open_json.read_text(encoding="utf-8")
        forbidden = [
            "Stuttgart-BSV", "VL 5 (d)", "VL 2 (e)", "VL 14 (r¹)", "Custom-NC-Witness",
            "Rahlfs (1935)", "BHS (BHSA)", "Tregelles (1879)", "Pickering-f35", "א (01) [CSP-OT]",
        ]
        for sig in forbidden:
            self.assertNotIn(sig, open_raw, f"Tier-5 siglum {sig!r} leaked into open JSON")

        open_doc = json.loads(open_raw)
        self.assertEqual(
            [w["siglum"] for w in open_doc["apparatus_witnesses"]],
            ["Amiatinus (A)", "VulgHetzenauer (1906)"],
        )
        self.assertEqual(open_doc["versification_notes"], ["Amiatinus (A): 1:2 re-aligned by content"])
        v1 = open_doc["verses"][0]
        self.assertEqual(v1["apparatus_witnesses"], ["Amiatinus (A)", "VulgHetzenauer (1906)"])
        self.assertEqual(v1["absent_witnesses"], [])
        self.assertEqual(v1["witness_refs"], {"Amiatinus (A)": "1:1"})
        self.assertEqual(
            sorted(v1["witness_readings"]),
            ["Amiatinus (A)", "Clem-Saints", "Clem1598-USFX", "VulgHetzenauer (1906)"],
        )
        # Tier-5-only apparatus unit ('Verbum' / 'sermo') was pruned; mixed unit kept only Amiatinus (A)
        self.assertEqual(len(v1["apparatus"]), 1)
        self.assertEqual(v1["apparatus"][0]["lemma"], "erat")
        self.assertEqual(v1["apparatus"][0]["lemma_witnesses"], ["Clem1598-USFX", "Clem-Saints"])
        self.assertEqual(v1["apparatus"][0]["variants"], [{"reading": "fuit", "witnesses": ["Amiatinus (A)"]}])
        # Tier-5-only disregarded entry pruned; mixed kept only Amiatinus (A)
        self.assertEqual(len(v1["disregarded"]), 1)
        self.assertEqual(v1["disregarded"][0]["witnesses"], ["Amiatinus (A)"])

        # 2. Open TSV reflects scrubbed Substantive_Variants count (1 instead of 2)
        with open_tsv.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh, delimiter="\t"))
        self.assertEqual(int(rows[0]["Substantive_Variants"]), 1)

        # 3. Open MD declares excluded Tier-5 witnesses ONLY in Section I Quarantine table, nowhere in II/III/IV
        md_text = open_md.read_text(encoding="utf-8")
        sec1, sec_rest = md_text.split("## Section II", 1)
        self.assertIn(TIER5_EXCLUDED_STATUS, sec1)
        for sig in ("Stuttgart-BSV", "VL 5 (d)", "VL 2 (e)", "Custom-NC-Witness"):
            self.assertIn(f"| {sig} | `{TIER5_EXCLUDED_STATUS}` |", sec1)
            self.assertNotIn(sig, sec_rest, f"Tier-5 siglum {sig!r} leaked into MD Sections II-IV")
        self.assertNotIn("VL 14 (r¹)", sec_rest)

        # 4. Local full export (open_licence_only=False) stays intact
        local_doc = json.loads(local_json.read_text(encoding="utf-8"))
        self.assertIn("Stuttgart-BSV", local_doc["verses"][0]["apparatus_witnesses"])
        self.assertIn("VL 5 (d)", local_doc["verses"][0]["witness_readings"])
        self.assertEqual(len(local_doc["verses"][0]["apparatus"]), 2)
        with local_tsv.open(encoding="utf-8") as fh:
            lrows = list(csv.DictReader(fh, delimiter="\t"))
        self.assertEqual(int(lrows[0]["Substantive_Variants"]), 2)
        self.assertIn("Stuttgart-BSV", local_md.read_text(encoding="utf-8"))

    def test_scrub_chapter_json_fixes_verse_level_apparatus_witnesses_leak(self) -> None:
        # Simulates the exact #14 P1 #2 bug: top-level apparatus_witnesses already scrubbed,
        # but verses[*].apparatus_witnesses still carries Stuttgart-BSV / VL 5 (d) / Rahlfs / BHS / etc.
        leaked_payload = {
            "edition": "Saints Latin Critical Text",
            "language": "latin",
            "admitted_witnesses": [{"siglum": "Clem1598-USFX", "tier": 1, "license": "Public Domain"}],
            "apparatus_witnesses": [{"siglum": "Amiatinus (A)", "tier": 2, "license": "CC BY-SA 4.0"}],
            "versification_notes": [
                "Amiatinus (A): note",
                "Rahlfs (1935): leaked note",
                "BHS (BHSA): leaked note",
            ],
            "verses": [
                {
                    "verse": 1,
                    "critical_text": "In principio",
                    "witness_readings": {"Clem1598-USFX": "In principio", "Amiatinus (A)": "In principio"},
                    "absent_witnesses": ["Pickering-f35"],
                    "witness_refs": {"Tregelles (1879)": "1:1"},
                    "apparatus_witnesses": [
                        "Amiatinus (A)",
                        "Stuttgart-BSV",
                        "VL 5 (d)",
                        "VL 2 (e)",
                        "VL 15 (aur)",
                        "Rahlfs (1935)",
                        "BHS (BHSA)",
                        "Tregelles (1879)",
                        "Pickering-f35",
                        "א (01) [CSP-OT]",
                    ],
                    "apparatus": [],
                    "disregarded": [],
                }
            ],
        }
        cleaned = scrub_chapter_json_for_open_export(leaked_payload)
        raw = json.dumps(cleaned, ensure_ascii=False)
        for sig in KNOWN_TIER5_SIGLA:
            self.assertNotIn(sig, raw, sig)
        self.assertEqual(cleaned["verses"][0]["apparatus_witnesses"], ["Amiatinus (A)"])
        self.assertEqual(cleaned["verses"][0]["absent_witnesses"], [])
        self.assertEqual(cleaned["verses"][0]["witness_refs"], {})
        self.assertEqual(cleaned["versification_notes"], ["Amiatinus (A): note"])

    def test_scrub_real_local_john1_json_zero_tier5_leaks(self) -> None:
        sample = STUDIO_ROOT / "Saints-Latin-Critical-Text" / "05_Salvation" / "47_John" / "47_John_01_Critical_Text.json"
        if not sample.exists():
            self.skipTest("Local Saints-Latin-Critical-Text John 1 JSON not present")
        payload = json.loads(sample.read_text(encoding="utf-8"))
        cleaned = scrub_chapter_json_for_open_export(payload)
        raw = json.dumps(cleaned, ensure_ascii=False)
        for sig in KNOWN_TIER5_SIGLA:
            self.assertNotIn(sig, raw, f"Tier-5 siglum {sig!r} survived scrubbing real John 1 JSON")
        # Open witnesses remain intact
        self.assertIn("Amiatinus (A)", raw)
        self.assertIn("VulgHetzenauer (1906)", raw)


@unittest.skipUnless(CORPORA, "tagged corpora (OSHB, TAGNT/LXX lemmas, Lewis & Short) not available")
class TestConcordancePackFullCorpusCoverage(unittest.TestCase):
    _orig_db_path: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls._orig_db_path = studio_db.DB_PATH
        cls._db_file = _TEST_WORKDIR / "stage1_conc_studio.db"
        studio_db.DB_PATH = cls._db_file
        cls.engine = CriticalTextEngine()
        now = "2026-11-24T12:00:00Z"
        sample_verses = [
            # Book 1: Genesis (will be rebuilt singly afterwards)
            ("hebrew", "genesis", 1, 1, "בְּרֵאשִׁ֖ית בָּרָ֣א אֱלֹהִ֑ים אֵ֥ת הַשָּׁמַ֖יִם וְאֵ֥ת הָאָֽרֶץ׃"),
            ("greek", "genesis", 1, 1, "Ἐν ἀρχῇ ἐποίησεν ὁ θεὸς τὸν οὐρανὸν καὶ τὴν γῆν."),
            ("latin", "genesis", 1, 1, "In principio creavit Deus cælum et terram."),
            # Book 2: Psalms (NOT touched by the single-book Genesis rebuild)
            ("hebrew", "psalms", 51, 3, "חׇנֵּ֣נִי אֱלֹהִ֣ים כְּחַסְדֶּ֑ךָ כְּרֹ֥ב רַ֝חֲמֶ֗יךָ מְחֵ֣ה פְשָׁעָֽי׃"),
            ("greek", "psalms", 50, 3, "Ἐλέησόν με, ὁ θεός, κατὰ τὸ μέγα ἔλεός σου, καὶ κατὰ τὸ πλῆθος τῶν οἰκτιρμῶν σου ἐξάλειψον τὸ ἀνόμημά μου·"),
            ("latin", "psalms", 50, 3, "Miserere mei, Deus, secundum magnam misericordiam tuam; et secundum multitudinem miserationum tuarum, dele iniquitatem meam."),
            # Book 3: Extra-site verse + confirmed duplicate/placeholder in another book
            ("greek", "matthew", 17, 21, "⟦Τοῦτο δὲ τὸ γένος οὐκ ἐκπορεύεται εἰ μὴ ἐν προσευχῇ καὶ νηστείᾳ.⟧"),
            ("hebrew", "psalms", 116, 14, "נְ֭דָרַי לַיהֹוָ֣ה אֲשַׁלֵּ֑ם נֶגְדָה־נָּ֝֗א לְכׇל־עַמּֽוֹ׃"),
            ("latin", "psalms", 115, 5, "Vota mea Domino reddam coram omni populo ejus."),
            ("greek", "psalms", 25, 22, "Τοῦ Δαυίδ."),
            ("latin", "sirach", 19, 6, "Qui odit loquacitatem, extinguit malitiam."),
        ]
        with get_conn() as conn:
            for lang, slug, ch, v, text in sample_verses:
                row = conn.execute(
                    "SELECT id FROM chapters WHERE language = ? AND book_slug = ? AND chapter = ?",
                    (lang, slug, ch),
                ).fetchone()
                if row:
                    cid = int(row[0])
                else:
                    cid = int(
                        conn.execute(
                            """INSERT INTO chapters (language, division, book_slug, book_title, chapter, status, ai_mode,
                                   model_used, verse_count, variant_verse_count, updated_at)
                               VALUES (?, ?, ?, ?, ?, 'ADJUDICATED', 'offline_philological', 'Offline', 1, 0, ?)""",
                            (lang, BOOKS_BY_SLUG[slug].division, slug, BOOKS_BY_SLUG[slug].title, ch, now),
                        ).lastrowid
                    )
                conn.execute(
                    """INSERT INTO verses (chapter_id, verse, critical_text, confidence, decision_source,
                           witness_readings_json, apparatus_json, disregarded_json, rationale, human_locked, updated_at)
                       VALUES (?, ?, ?, 0.99, 'Offline', '{}', '[]', '[]', 'ok', 0, ?)""",
                    (cid, v, text, now),
                )
        cls.full_build = cls.engine.seed_concordance_lexicons()

    @classmethod
    def tearDownClass(cls) -> None:
        studio_db.DB_PATH = cls._orig_db_path

    def test_pack_manifest_and_report_preserve_full_corpus_after_single_book_build(self) -> None:
        full_langs = self.full_build["languages"]

        # Trigger single-book incremental build (genesis only)
        single = self.engine.index_concordance_chapters(book_slug="genesis")
        for lang in ("hebrew", "greek", "latin"):
            self.assertLess(single["languages"][lang]["tokens"], full_langs[lang]["tokens"], lang)
            self.assertLess(single["languages"][lang]["indexed"], full_langs[lang]["indexed"], lang)

        # Export pack right after the single-book build
        pack_dir = _TEST_WORKDIR / "pack_after_single"
        self.engine.export_concordance_pack(out_dir=pack_dir)

        manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
        report = (pack_dir / "CONCORDANCE_REPORT.md").read_text(encoding="utf-8")

        for lang in ("hebrew", "greek", "latin"):
            cov = manifest["coverage"][lang]
            self.assertEqual(cov["tokens"], full_langs[lang]["tokens"], lang)
            self.assertEqual(cov["indexed"], full_langs[lang]["indexed"], lang)
            self.assertEqual(cov["content_words"], full_langs[lang]["content_words"], lang)
            self.assertEqual(cov["function_words"], full_langs[lang]["function_words"], lang)
            self.assertEqual(cov["with_morph"], full_langs[lang]["with_morph"], lang)
            self.assertEqual(cov["extra_site_verses"], full_langs[lang].get("extra_site_verses", 0), lang)
            self.assertEqual(
                cov["tokens_in_duplicate_verses"],
                full_langs[lang].get("tokens_in_duplicate_verses", 0),
                lang,
            )
            # CONCORDANCE_REPORT.md table must print the full-corpus token & indexed totals
            self.assertIn(f"| {lang} | {cov['tokens']:,} | {cov['indexed']:,} (", report)

        # Dashboard stats also show full-corpus coverage while honestly keeping last_build_scope='genesis'
        dash = self.engine.get_concordance_stats()
        self.assertEqual(dash["last_build_scope"], "genesis")
        for lang in ("hebrew", "greek", "latin"):
            self.assertEqual(dash["coverage"][lang]["tokens"], full_langs[lang]["tokens"], lang)
            self.assertEqual(dash["coverage"][lang]["indexed"], full_langs[lang]["indexed"], lang)

    def test_legacy_single_book_build_log_without_corpus_coverage_still_reports_full_corpus(self) -> None:
        """Simulates an existing DB whose latest concordance_build_log row was written before
        corpus_coverage existed (e.g. build_id=16 scope='genesis' in pre-Stage-1 studio.db)."""
        full_langs = self.full_build["languages"]
        with get_conn() as conn:
            row = conn.execute(
                "SELECT build_id, stats_json FROM concordance_build_log ORDER BY build_id DESC LIMIT 1"
            ).fetchone()
            legacy_stats = json.loads(row[1])
            legacy_stats.pop("corpus_coverage", None)
            conn.execute(
                "UPDATE concordance_build_log SET stats_json = ? WHERE build_id = ?",
                (json.dumps(legacy_stats, ensure_ascii=False), int(row[0])),
            )
            gs = gold_stats(conn)
            for lang in ("hebrew", "greek", "latin"):
                self.assertEqual(gs["coverage"][lang]["tokens"], full_langs[lang]["tokens"], lang)
                self.assertEqual(gs["coverage"][lang]["indexed"], full_langs[lang]["indexed"], lang)

        pack_dir = _TEST_WORKDIR / "pack_legacy_log"
        self.engine.export_concordance_pack(out_dir=pack_dir)
        manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
        for lang in ("hebrew", "greek", "latin"):
            self.assertEqual(manifest["coverage"][lang]["tokens"], full_langs[lang]["tokens"], lang)
            self.assertEqual(manifest["coverage"][lang]["indexed"], full_langs[lang]["indexed"], lang)


class TestConcordanceAlignGitHelpers(unittest.TestCase):
    def test_is_ancestor_and_resolve_ref_on_temp_git_repo(self) -> None:
        repo = _TEST_WORKDIR / "git_align_test"
        repo.mkdir(parents=True, exist_ok=True)
        git = al._git()

        def run_git(*args: str) -> str:
            r = subprocess.run([git, "-C", str(repo), *args], capture_output=True, text=True, check=True)
            return r.stdout.strip()

        run_git("init", "-b", "main")
        run_git("config", "user.email", "test@saints.local")
        run_git("config", "user.name", "Test")

        (repo / "a.txt").write_text("v1\n", encoding="utf-8")
        run_git("add", "a.txt")
        run_git("commit", "-m", "c1")
        c1 = al.resolve_ref(repo, "HEAD")
        self.assertTrue(c1 and len(c1) == 40)

        (repo / "a.txt").write_text("v2\n", encoding="utf-8")
        run_git("add", "a.txt")
        run_git("commit", "-m", "c2")
        c2 = al.resolve_ref(repo, "HEAD")
        self.assertTrue(c2 and len(c2) == 40 and c2 != c1)

        # Unrelated orphan commit
        run_git("checkout", "--orphan", "other")
        run_git("rm", "-rf", ".")
        (repo / "b.txt").write_text("other\n", encoding="utf-8")
        run_git("add", "b.txt")
        run_git("commit", "-m", "c3")
        c3 = al.resolve_ref(repo, "HEAD")
        self.assertTrue(c3 and len(c3) == 40)

        self.assertTrue(al.is_ancestor(repo, c1, c1))
        self.assertTrue(al.is_ancestor(repo, c1, c2))
        self.assertFalse(al.is_ancestor(repo, c2, c1))
        self.assertFalse(al.is_ancestor(repo, c1, c3))


if __name__ == "__main__":
    unittest.main()
