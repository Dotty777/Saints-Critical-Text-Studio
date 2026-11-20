"""Unit, concordance-search, and headless GUI tests for Greek & Hebrew Latinized transliteration."""

from __future__ import annotations

import ast
import sqlite3
import sys
import tkinter as tk
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from studio.translit import (  # noqa: E402
    transliterate,
    transliterate_greek,
    transliterate_hebrew,
    transliterate_mixed,
)


class GreekTranslitTests(unittest.TestCase):
    def test_canonical_verses(self) -> None:
        self.assertEqual(
            transliterate_greek("Ἐν ἀρχῇ ἦν ὁ λόγος, καὶ ὁ λόγος ἦν πρὸς τὸν θεόν, καὶ θεὸς ἦν ὁ λόγος."),
            "En arche en ho logos, kai ho logos en pros ton theon, kai theos en ho logos.",
        )
        self.assertEqual(
            transliterate_greek("Ἐν ἀρχῇ ἐποίησεν ὁ θεὸς τὸν οὐρανὸν καὶ τὴν γῆν."),
            "En arche epoiesen ho theos ton ouranon kai ten gen.",
        )
        self.assertEqual(
            transliterate_greek("Βίβλος γενέσεως Ἰησοῦ χριστοῦ υἱοῦ Δαυὶδ υἱοῦ Ἀβραάμ."),
            "Biblos geneseos Iesou christou huiou Dauid huiou Abraam.",
        )

    def test_diphthongs_breathings_diaeresis_and_gamma_nasals(self) -> None:
        # Rough breathing on second vowel of diphthong puts 'h' before the diphthong
        self.assertEqual(transliterate_greek("οὗτος"), "houtos")
        self.assertEqual(transliterate_greek("Οὕτως"), "Houtos")
        self.assertEqual(transliterate_greek("εὑρίσκω"), "heurisko")
        self.assertEqual(transliterate_greek("υἱός"), "huios")
        self.assertEqual(transliterate_greek("Οἱ"), "Hoi")
        self.assertEqual(transliterate_greek("αἱ"), "hai")
        # Standalone upsilon -> y; diaeresis breaks diphthong
        self.assertEqual(transliterate_greek("ὕδωρ"), "hydor")
        self.assertEqual(transliterate_greek("πνεῦμα"), "pneuma")
        self.assertEqual(transliterate_greek("Μωϋσῆς"), "Moyses")
        self.assertEqual(transliterate_greek("Ἠσαΐας"), "Esaias")
        # Gamma nasals
        self.assertEqual(transliterate_greek("ἄγγελος"), "angelos")
        self.assertEqual(transliterate_greek("εὐαγγέλιον"), "euangelion")
        self.assertEqual(transliterate_greek("ἀνάγκη"), "ananke")
        self.assertEqual(transliterate_greek("σάλπιγξ"), "salpinx")
        self.assertEqual(transliterate_greek("ἐλέγχω"), "elencho")
        # Rho with rough breathing and double rho
        self.assertEqual(transliterate_greek("ῥῆμα"), "rhema")
        self.assertEqual(transliterate_greek("παῤῥησία"), "parrhesia")
        # Capitals, elision, Greek punctuation
        self.assertEqual(transliterate_greek("ΚΥΡΙΟΣ"), "KYRIOS")
        self.assertEqual(transliterate_greek("Χριστός"), "Christos")
        self.assertEqual(transliterate_greek("ἀλλʼ ἔχῃ· τί;"), "all' eche; ti?")


class HebrewTranslitTests(unittest.TestCase):
    def test_canonical_verses(self) -> None:
        self.assertEqual(
            transliterate_hebrew("בְּרֵאשִׁ֖ית בָּרָ֣א אֱלֹהִ֑ים אֵ֥ת הַשָּׁמַ֖יִם וְאֵ֥ת הָאָֽרֶץ׃"),
            "bereshit bara elohim et hashamayim ve'et ha'aretz.",
        )
        self.assertEqual(
            transliterate_hebrew(
                "וְהָאָ֗רֶץ הָיְתָ֥ה תֹ֙הוּ֙ וָבֹ֔הוּ וְחֹ֖שֶׁךְ עַל־פְּנֵ֣י תְה֑וֹם וְר֣וּחַ אֱלֹהִ֔ים מְרַחֶ֖פֶת עַל־פְּנֵ֥י הַמָּֽיִם׃"
            ),
            "veha'aretz hayetah tohu vavohu vechoshekh al-penei tehom veruach elohim merachefet al-penei hamayim.",
        )
        self.assertEqual(
            transliterate_hebrew("נֵר־לְרַגְלִ֥י דְבָרֶ֑ךָ וְ֝א֗וֹר לִנְתִיבָתִֽי׃"),
            "ner-leragli devarekha ve'or lintivati.",
        )

    def test_phonological_rules_and_roots(self) -> None:
        # Furtive patach
        self.assertEqual(transliterate_hebrew("רוּחַ"), "ruach")
        self.assertEqual(transliterate_hebrew("נֹחַ"), "noach")
        self.assertEqual(transliterate_hebrew("יֵשׁוּעַ"), "yeshua")
        # Qamatz qatan
        self.assertEqual(transliterate_hebrew("חָכְמָה"), "chokhmah")
        self.assertEqual(transliterate_hebrew("כָּל־הָאָרֶץ"), "kol-ha'aretz")
        self.assertEqual(transliterate_hebrew("קָדְשׁוֹ"), "kodsho")
        # Begadkefat, ָיו suffix, shin/sin, onset alef/ayin before vav mater
        self.assertEqual(transliterate_hebrew("דְּבָרָיו"), "devarav")
        self.assertEqual(transliterate_hebrew("מֶלֶךְ"), "melekh")
        self.assertEqual(transliterate_hebrew("בָּרוּךְ"), "barukh")
        self.assertEqual(transliterate_hebrew("יִשְׂרָאֵל"), "yisra'el")
        self.assertEqual(transliterate_hebrew("שָׁלוֹם"), "shalom")
        self.assertEqual(transliterate_hebrew("לְעוֹלָם"), "le'olam")
        self.assertEqual(transliterate_hebrew("בְּעוֹד"), "be'od")
        # Tetragrammaton
        self.assertEqual(transliterate_hebrew("יהוה"), "YHWH")
        self.assertEqual(transliterate_hebrew("יְהוָה"), "YHWH")
        self.assertEqual(transliterate_hebrew("יְהֹוָה"), "Yehovah")
        # Consonantal root notation
        self.assertEqual(transliterate_hebrew("ר-א-שׁ I"), "r-'-sh I")
        self.assertEqual(transliterate_hebrew("ח-ל-ל III"), "ch-l-l III")
        self.assertEqual(transliterate_hebrew("ד-ב-ר"), "d-b-r")
        self.assertEqual(transliterate_hebrew("א-מ-ן"), "'-m-n")


class DispatcherAndIntegrationTests(unittest.TestCase):
    def test_dispatcher_and_mixed(self) -> None:
        self.assertEqual(transliterate("In principio", "latin"), "In principio")
        self.assertEqual(transliterate("λόγος", "grc_nt"), "logos")
        self.assertEqual(transliterate("שָׁלוֹם", "heb_ot"), "shalom")
        self.assertEqual(transliterate("אֲרָמִית", "arc"), "aramit")
        self.assertEqual(transliterate_mixed("ἀρχή < ἄρχω"), "arche < archo")

    def test_app_still_talks_only_to_engine_not_translit(self) -> None:
        tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("studio"):
                self.assertIn(node.module, {"studio.engine", "studio.catalog", "studio.brains.base"})

    def test_concordance_backfill_and_search_by_translit(self) -> None:
        from studio.concordance import (
            get_concept_visual_graph,
            init_concordance_schema,
            list_roots_and_morphemes,
            search_concordance_concepts,
        )
        from studio.concordance_gold import backfill_transliterations

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_concordance_schema(conn)

        # Insert sample Hebrew & Greek roots/stems without translit and link them to curated concepts
        r_archo = int(conn.execute(
            "INSERT INTO core_roots (lang, root_key, homograph_no, translit, core_idea) VALUES ('grc', 'ἄρχω', 1, NULL, 'to begin')"
        ).lastrowid)
        r_lego = int(conn.execute(
            "INSERT INTO core_roots (lang, root_key, homograph_no, translit, core_idea) VALUES ('grc', 'λέγω', 1, NULL, 'to speak')"
        ).lastrowid)
        r_rosh = int(conn.execute(
            "INSERT INTO core_roots (lang, root_key, homograph_no, translit, core_idea) VALUES ('heb', 'ר-א-שׁ', 1, NULL, 'head')"
        ).lastrowid)
        s_logos = int(conn.execute(
            "INSERT INTO lexical_stems (lang, root_id, canonical_stem, pos_tag, ext_strongs, base_gloss) VALUES ('grc', ?, 'λόγος', 'N', 'G3056', 'word')",
            (r_lego,),
        ).lastrowid)
        s_reshit = int(conn.execute(
            "INSERT INTO lexical_stems (lang, root_id, canonical_stem, pos_tag, ext_strongs, base_gloss) VALUES ('heb', ?, 'רֵאשִׁית', 'N', 'H7225', 'beginning')",
            (r_rosh,),
        ).lastrowid)
        s_arche = int(conn.execute(
            "INSERT INTO lexical_stems (lang, root_id, canonical_stem, pos_tag, ext_strongs, base_gloss) VALUES ('grc', ?, 'ἀρχή', 'N', 'G0746', 'beginning')",
            (r_archo,),
        ).lastrowid)
        c_word = int(conn.execute("SELECT concept_id FROM trilingual_concepts WHERE concept_slug='WORD_LOGOS_SPEECH'").fetchone()[0])
        c_orig = int(conn.execute("SELECT concept_id FROM trilingual_concepts WHERE concept_slug='ORIGIN_HEAD_START'").fetchone()[0])
        ss_word = int(conn.execute("SELECT sense_id FROM saints_senses WHERE concept_id=? LIMIT 1", (c_word,)).fetchone()[0])
        ss_orig = int(conn.execute("SELECT sense_id FROM saints_senses WHERE concept_id=? LIMIT 1", (c_orig,)).fetchone()[0])
        conn.execute("INSERT INTO stem_concept_links (stem_id, concept_id, default_sense_id) VALUES (?, ?, ?)", (s_logos, c_word, ss_word))
        conn.execute("INSERT INTO stem_concept_links (stem_id, concept_id, default_sense_id) VALUES (?, ?, ?)", (s_reshit, c_orig, ss_orig))
        conn.execute("INSERT INTO stem_concept_links (stem_id, concept_id, default_sense_id) VALUES (?, ?, ?)", (s_arche, c_orig, ss_orig))

        res = backfill_transliterations(conn, force=True)
        self.assertEqual(res["roots_updated"], 3)
        self.assertEqual(res["stems_updated"], 3)

        # Search curated concepts by English-friendly Latinized transliteration
        logos_hits = search_concordance_concepts(conn, query="logos", limit=5)
        self.assertTrue(any(h["concept_slug"] == "WORD_LOGOS_SPEECH" for h in logos_hits), logos_hits)

        reshit_hits = search_concordance_concepts(conn, query="reshit", limit=5)
        self.assertTrue(any(h["concept_slug"] == "ORIGIN_HEAD_START" for h in reshit_hits), reshit_hits)

        # Concept graph returns stem_translit and root translit
        g = get_concept_visual_graph(conn, c_word)
        grc_stems = [s for s in g["stems"] if s["lang"] == "grc"]
        self.assertTrue(grc_stems)
        self.assertTrue(any(s.get("stem_translit") == "logos" for s in grc_stems), grc_stems)

        # Roots catalog populates translit and searches by translit
        roots = list_roots_and_morphemes(conn, kind="roots", lang_filter="grc", query="archo", limit=10)
        self.assertTrue(any(r.get("translit") == "archo" for r in roots), roots)
        conn.close()

    def test_gui_renders_transliteration_toggle_cleanly(self) -> None:
        from app import CriticalTextDesktopApp

        root = tk.Tk()
        root.withdraw()
        try:
            gui = CriticalTextDesktopApp(root)
            self.assertTrue(gui.show_translit_var.get())
            # Render sample Greek & Hebrew chapters in Workbench and Home Reader
            sample_grc = {
                "language": "greek",
                "book_slug": "john",
                "book_title": "John",
                "chapter": 1,
                "verse_count": 1,
                "variant_verse_count": 0,
                "updated_at": "2026-11-19T23:00:00Z",
                "verses": [{
                    "verse": 1,
                    "critical_text": "Ἐν ἀρχῇ ἦν ὁ λόγος.",
                    "confidence": 0.99,
                    "decision_source": "Offline",
                    "apparatus": [],
                    "disregarded": [],
                    "witness_readings": {"SBLGNT": "Ἐν ἀρχῇ ἦν ὁ λόγος."},
                    "rationale": "ok",
                    "human_locked": False,
                }],
            }
            gui.home_selected_chapter = sample_grc
            gui._render_home_reader()
            home_txt = gui.home_reader_text.get("1.0", "end")
            self.assertIn("En arche en ho logos.", home_txt)

            gui._render_chapter(sample_grc)
            insp_tr = gui.verse_translit_text.get("1.0", "end").strip()
            self.assertEqual(insp_tr, "En arche en ho logos.")

            # Toggle OFF and verify transliteration hides cleanly
            gui.show_translit_var.set(False)
            gui._on_translit_toggled()
            home_off = gui.home_reader_text.get("1.0", "end")
            self.assertNotIn("En arche en ho logos.", home_off)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
