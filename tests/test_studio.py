"""Automated offline test suite for Saints Critical Text Studio.

The suite never touches the real database or the Saints-*-Critical-Text folders: the
environment variables below point the Studio at a temporary folder *before* it is imported.
Tests that read the real research corpora skip themselves when the corpora are absent.
"""

from __future__ import annotations
import os
import shutil
import tempfile
import unicodedata
import unittest
from pathlib import Path

_SANDBOX = tempfile.mkdtemp(prefix="cts_tests_")
os.environ["CTS_DATA_DIR"] = os.path.join(_SANDBOX, "data")
os.environ["CTS_OUTPUT_ROOT"] = os.path.join(_SANDBOX, "out")

from studio.brains.base import (  # noqa: E402
    BrainConfig,
    GatekeeperVerdict,
    apply_model_gatekeeper_opinion,
    check_model_text_is_attested,
)
from studio.brains.gemini_cloud import CloudGeminiBrain  # noqa: E402
from studio.brains.local_llm import LocalOllamaBrain  # noqa: E402
from studio.brains.offline_philological import OfflinePhilologicalBrain  # noqa: E402
from studio.catalog import CRITICAL_OUTPUT_ROOTS, GREEK_RESEARCH_ROOT, HEBREW_RESEARCH_ROOT, LATIN_RESEARCH_ROOT  # noqa: E402
from studio.collator import (  # noqa: E402
    align_versification,
    align_witnesses_for_verse,
    canonical_compare_key,
    is_orthographic_equivalence,
)
from studio.parsers import (  # noqa: E402
    _apply_doubtful_brackets,
    _render_amiatinus_fragment,
    clean_cntr_mss_line,
    parse_usfm_book,
)

HAVE_CORPORA = (
    (GREEK_RESEARCH_ROOT / "01_Tier1_Modern_Critical_Open").exists()
    and (HEBREW_RESEARCH_ROOT / "hebrew-base").exists()
    and (LATIN_RESEARCH_ROOT / "latin-base").exists()
)


def tearDownModule() -> None:
    shutil.rmtree(_SANDBOX, ignore_errors=True)


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


class TestSandboxing(unittest.TestCase):
    def test_outputs_go_to_sandbox(self) -> None:
        for root in CRITICAL_OUTPUT_ROOTS.values():
            self.assertTrue(str(root).startswith(_SANDBOX), root)


class TestAirGapAndAIGuards(unittest.TestCase):
    def test_offline_lock_and_loopback(self) -> None:
        cloud = CloudGeminiBrain(BrainConfig(provider_id="cloud_gemini", offline_locked=True, gemini_api_key="dummy"))
        with self.assertRaises(PermissionError):
            cloud._check_online_allowed()
        local = LocalOllamaBrain(BrainConfig(provider_id="local_ollama", local_endpoint="https://example.com/api/chat"))
        with self.assertRaises(PermissionError):
            local._call_local_json("sys", "usr")

    def test_model_text_must_be_attested(self) -> None:
        witnesses = {"A": "καὶ εἶπεν ὁ θεός", "B": "εἶπεν δὲ ὁ θεὸς"}
        self.assertEqual(check_model_text_is_attested("καὶ εἶπεν ὁ θεός", witnesses, "greek"), "")
        self.assertIn("κύριος", check_model_text_is_attested("καὶ εἶπεν ὁ κύριος", witnesses, "greek"))
        self.assertNotEqual(check_model_text_is_attested("", witnesses, "greek"), "")

    def test_model_cannot_relax_gatekeeper(self) -> None:
        corrupt = GatekeeperVerdict("DISREGARDED_CORRUPT", 0, 0.0, "PD", "x", 0.9, {}, "corrupt")
        apply_model_gatekeeper_opinion(corrupt, {"decision": "ADMITTED", "tier_assigned": 1, "recommended_weight": 0.9}, "M")
        self.assertEqual(corrupt.decision, "DISREGARDED_CORRUPT")
        self.assertEqual(corrupt.recommended_weight, 0.0)
        admitted = GatekeeperVerdict("ADMITTED", 1, 0.86, "PD", "x", 0.9, {}, "ok")
        apply_model_gatekeeper_opinion(admitted, {"decision": "QUARANTINED_NC"}, "M")
        self.assertEqual((admitted.decision, admitted.tier_assigned, admitted.recommended_weight), ("QUARANTINED_NC", 5, 0.0))


class TestGatekeeper(unittest.TestCase):
    brain = OfflinePhilologicalBrain()
    clean_greek = "1:1 Ἐν ἀρχῇ ἦν ὁ λόγος, καὶ ὁ λόγος ἦν πρὸς τὸν θεόν, καὶ θεὸς ἦν ὁ λόγος."

    def verdict(self, **kw):
        args = dict(language="greek", title="Sample", declared_license="", sample_text=self.clean_greek,
                    file_meta={"detected_format": "plain_verse"}, existing_samples={})
        args.update(kw)
        return self.brain.evaluate_witness(**args)

    def test_decisions(self) -> None:
        v = self.verdict(title="Open Papyrus P66 Sample", declared_license="CC BY 4.0")
        self.assertEqual(v.decision, "ADMITTED")
        self.assertGreaterEqual(v.recommended_weight, 0.85)
        v = self.verdict(declared_license="CC BY-NC-ND 4.0")
        self.assertEqual((v.decision, v.tier_assigned, v.recommended_weight), ("QUARANTINED_NC", 5, 0.0))
        v = self.verdict(declared_license="Public Domain", sample_text="In the beginning God created the heaven and the earth.")
        self.assertEqual(v.decision, "DISREGARDED_CORRUPT")
        v = self.verdict(declared_license="Public Domain", existing_samples={"P66": self.clean_greek})
        self.assertEqual(v.decision, "DISREGARDED_DUPLICATE")

    def test_open_licence_with_publisher_mention_is_not_quarantined(self) -> None:
        # e.g. the CNTR files say "All rights reserved. Released under CC BY-SA 4.0", and the
        # Amiatinus TEI cites the Stuttgart Vulgate (Deutsche Bibelgesellschaft) in its bibliography.
        v = self.verdict(sample_text="Copyright Alan Bunning. All rights reserved. Released under the Creative Commons "
                                     "Attribution-ShareAlike 4.0 International License (CC BY-SA 4.0).\n" + self.clean_greek)
        self.assertEqual(v.decision, "ADMITTED")
        v = self.verdict(sample_text="Stuttgart: Deutsche Bibelgesellschaft, 2007.\n" + self.clean_greek)
        self.assertEqual(v.decision, "QUARANTINED_NC")


class TestParsers(unittest.TestCase):
    def test_matthew_1_18_keeps_uncorrected_sinaiticus_spelling(self) -> None:
        # CNTR 01.txt, 40001018: x is the original hand, the next group its correction.
        self.assertEqual(clean_cntr_mss_line("x{μνησ/στευθισησ} {μνησ/τευθεισησ}"), "μνησστευθισησ")

    def test_cntr_mes_markup(self) -> None:
        line = "\\1186βιβλοσ γενεσεωσ =ιυ =χυ /υιου δαυειδ γενε|αι $ιδ x{ι/σακ ισακ} {ι/σαακ ισαακ δε} το¯ {και} a{ϗ ελ/θον} ~του"
        out = clean_cntr_mss_line(line)
        self.assertTrue(out.startswith("βιβλοσ γενεσεωσ ιυ\u0305 χυ\u0305 υιου"), out)
        self.assertIn("γενεαι", out)               # column break removed inside the word
        self.assertIn("ιδ\u02b9", out)             # letter-numeral (NFC form of U+0374)
        self.assertIn("ισακ ισακ", out)            # first hand kept, correction dropped
        self.assertNotIn("ισαακ", out)
        self.assertIn("τον", out)                  # final-nu overline
        self.assertIn("και", out)
        self.assertNotIn("ελθον", out)             # corrector's insertion is not first-hand text
        self.assertTrue(out.endswith("…"), out)   # word supplied by the editor = lacuna
        for ch in "\\|/{}$~":
            self.assertNotIn(ch, out)

    def test_doubtful_brackets(self) -> None:
        rows = [(16, 8, "καὶ ... ἐφοβοῦντο γάρ. ⟦Πάντα δὲ ... σωτηρίας.⟧"), (16, 9, "⟦Ἀναστὰς δὲ πρωῒ"), (16, 10, "ἐκείνη πορευθεῖσα⟧"), (16, 11, "κἀκεῖνοι")]
        out = _apply_doubtful_brackets(rows, "⟦", "⟧")
        self.assertEqual(out[16][8], "καὶ ... ἐφοβοῦντο γάρ.")  # Shorter Ending dropped from 16:8
        self.assertTrue(out[16][9].startswith("⟦") and out[16][9].endswith("⟧"))
        self.assertTrue(out[16][10].startswith("⟦"))
        self.assertEqual(out[16][11], "κἀκεῖνοι")

    def test_amiatinus_reads_the_manuscript_not_the_editions(self) -> None:
        frag = ('et tenebrae <app><lem source="#c">erant</lem><rdg source="#s"/></app> super '
                'de fructu <choice><sic>edemus</sic><corr source="#s">uescemur</corr></choice> '
                'aromati<expan>b<am>’</am><ex>us</ex></expan> <supplied reason="omitted" source="#s">sic</supplied> '
                'creata<del rend="erased">e</del> <p rend="rubric">explicit liber genesis</p>')
        out = _render_amiatinus_fragment(frag)
        # a word the scribe left out (supplied by the transcription) is a gap that casts no vote,
        # never the Stuttgart editors' word
        self.assertEqual(out, "et tenebrae erant super de fructu edemus aromatibus […] creata")
        # letters supplied inside a word: the truncated word cannot vote either
        self.assertEqual(_render_amiatinus_fragment('sepeli<supplied reason="omitted">ui</supplied> eum'), "[…] eum")

    def test_swete_ocr_residue_and_kai_compendium(self) -> None:
        from studio.parsers import _attach_punct
        self.assertEqual(_attach_punct("καὶ εἶπεν (13) κα ἐγένετο ’φ’ οὕτως ·"), "καὶ εἶπεν καὶ ἐγένετο οὕτως·")
        self.assertEqual(_attach_punct("κα καὶ"), "κα καὶ", "κα before καί means text was lost: left visible")

    def test_usfm_psalm_title_and_offsets(self) -> None:
        tmp = Path(_SANDBOX) / "t.usfm"
        tmp.write_text("\\id PSA\n\\c 3\n\\d Ψαλμὸς τῷ Δαυίδ\n\\v 1 Κύριε τί ἐπληθύνθησαν\n\\p\n\\v 2 πολλοὶ\n\\f + note\\f*\n", encoding="utf-8")
        book = parse_usfm_book(tmp)
        self.assertEqual(book[3][1], "Ψαλμὸς τῷ Δαυίδ Κύριε τί ἐπληθύνθησαν")
        self.assertEqual(book[3][2], "πολλοὶ")

    def test_wlc_inline_special_letters_do_not_split_words(self) -> None:
        from studio.parsers import _wlc_index
        tmp = Path(_SANDBOX) / "wlc_shema.tsv"
        tmp.write_text(
            "DEU\t6\t4\t'l s=\"H8085\"'שְׁמַ֖'seg type=\"x-large\"'ע'seg''/l' יִשְׂרָאֵ֑ל "
            "'l s=\"H259\"'אֶחָֽ'seg type=\"x-large\"'ד'seg''/l'׃\n",
            encoding="utf-8",
        )
        parsed = _wlc_index(str(tmp), tmp.stat().st_mtime)
        self.assertEqual(parsed["DEU"][6][4], nfc("שְׁמַ֖ע יִשְׂרָאֵ֑ל אֶחָֽד׃"))
        self.assertNotIn("'", parsed["DEU"][6][4])

    def test_amiatinus_name_boundaries_and_cola_marks(self) -> None:
        frag = (
            'filii <name>d<choice><sic>o</sic><corr source="#s">a</corr></choice>dan</name>fuerunt '
            '<choice><orig>,<!-- MS dot --></orig><reg><lb/></reg></choice><name>amdan</name>'
        )
        self.assertEqual(_render_amiatinus_fragment(frag), "filii dodan fuerunt amdan")

    def test_latin_saints_json_duplicate_refs_and_editorial_tags(self) -> None:
        import json
        from studio.parsers import _parse_latin_saints_json
        tmp = Path(_SANDBOX) / "saints_lat_sample.json"
        tmp.write_text(json.dumps({"chapters": [{"chapter": 11, "verses": [
            {"card_id": "matthew-11-2", "reference": "Matthew 11:2", "latin": "[Joannes autem cum audisset,"},
            {"card_id": "matthew-11-3", "reference": "Matthew 11:2", "latin": "ait illi: Tu es?]"},
            {"card_id": "", "reference": "Matthew 11:3", "latin": ""},
            {"card_id": "john-6-51", "reference": "Matthew 11:5", "latin": "<Sponsus> Ego sum panis vivus."},
            {"card_id": "john-6-52", "reference": "Matthew 11:5", "latin": "Si quis manducaverit."},
        ]}]}), encoding="utf-8")
        out = _parse_latin_saints_json(tmp)
        self.assertEqual(out[11][2], "Joannes autem cum audisset,")
        self.assertEqual(out[11][3], "ait illi: Tu es?")
        self.assertEqual(out[11][5], "Ego sum panis vivus. Si quis manducaverit.")

    def test_swete_csv_transcription(self) -> None:
        from studio.catalog import BOOKS_BY_SLUG
        from studio.parsers import SWETE_CSV_VERSES, SWETE_CSV_WORDS, load_book_from_witness
        folder = Path(_SANDBOX) / "swete_csv"
        folder.mkdir(exist_ok=True)
        words = ["ΕΝ", "ἀρχῇ", "ἐποίησεν", "⸂⸆⸃", "πετόμεν[α]", "[τὰ", "με]γάλα·",   # Gen 1:1
                 "καὶ", "ἐγένετο", "[1]", "Καὶ", "ἔδωκεν", ".",                       # Gen 1:2 with sub-verse 2a
                 "",                                                                  # Gen 1:3 left empty
                 "λόγος", "(ὅτι", "τόπος)",                                           # Gen 1:4
                 "Λόγοι", "Νεεμία",                                                   # Neh 1:1
                 "πρόλογος"]                                                          # Sip 1:1 (prologue)
        (folder / SWETE_CSV_WORDS).write_text("".join(f"{i}\t{w}\n" for i, w in enumerate(words, 1)), encoding="utf-8")
        (folder / SWETE_CSV_VERSES).write_text("1\tGen.1:1\n8\tGen.1:2\n14\tGen.1:3\n15\tGen.1:4\n18\tNeh.1:1\n20\tSip.1:1\n",
                                               encoding="utf-8")
        row = {"parser_kind": "swete_csv", "file_path": str(folder)}
        gen = load_book_from_witness(row, BOOKS_BY_SLUG["genesis"])
        self.assertEqual(gen[1][1], "ΕΝ ἀρχῇ ἐποίησεν πετόμενα τὰ μεγάλα·")  # signs dropped, supplied letters kept
        self.assertEqual(gen[1][2], "καὶ ἐγένετο Καὶ ἔδωκεν.")  # sub-verse folded into its verse, like Brenton's \v 2a
        self.assertNotIn(3, gen[1], "an empty verse casts no vote")
        self.assertEqual(gen[1][4], "λόγος ὅτι τόπος")
        self.assertEqual(load_book_from_witness(row, BOOKS_BY_SLUG["nehemiah"]), {1: {1: "Λόγοι Νεεμία"}})
        self.assertEqual(load_book_from_witness(row, BOOKS_BY_SLUG["ezra"]), {}, "Ezra and Nehemiah are separate books")
        self.assertEqual(load_book_from_witness(row, BOOKS_BY_SLUG["sirach"]), {}, "Sirach's prologue is not a verse")

    def test_swete_copies_are_one_edition_and_the_transcription_leads(self) -> None:
        from studio.catalog import EDITION_FAMILIES, ORTHOGRAPHIC_BASE
        from studio.db import get_conn, init_db
        init_db()
        with get_conn() as conn:
            rows = {r["id"]: r for r in conn.execute("SELECT * FROM witnesses WHERE language = 'greek'")}
        swete = [wid for wid, fam in EDITION_FAMILIES.items() if fam == "swete_edition"]
        self.assertEqual(sorted(swete), ["grk-1st1k-lxx", "grk-swete-csv", "grk-swete-lxx"])
        self.assertEqual(max(swete, key=lambda wid: rows[wid]["weight"]), "grk-swete-csv")
        self.assertEqual(rows["grk-swete-csv"]["license"], "GPL-3.0")
        self.assertTrue(rows["grk-swete-csv"]["siglum"].startswith("Swete"), "the stream map keys on the siglum")
        self.assertEqual(ORTHOGRAPHIC_BASE[("greek", "OT")][0], "swete_csv")


class TestDocumentedSourceRepairs(unittest.TestCase):
    def test_repairs_are_scoped_logged_and_leave_raw_copy_unchanged(self) -> None:
        from studio.source_repairs import repair_documented_imports, _KINGS_PREFIX, _KINGS_TAIL
        raw = {23: {31: _KINGS_PREFIX + _KINGS_TAIL}}
        for wid, kind in (("grk-1st1k-lxx", "first1k_tei"), ("grk-swete-lxx", "swete_clean")):
            w = {"id": wid, "parser_kind": kind}
            fixed, notes = repair_documented_imports(w, "2-kings", raw)
            self.assertEqual(fixed[23][31], "… " + _KINGS_TAIL)
            self.assertIn(_KINGS_PREFIX.strip(), notes[23][0])
            self.assertIn("p. 797", notes[23][0])
            self.assertEqual(raw[23][31], _KINGS_PREFIX + _KINGS_TAIL)
            self.assertEqual(repair_documented_imports(w, "2-kings", fixed), (fixed, {}))
            self.assertIs(repair_documented_imports(w, "1-kings", raw)[0], raw)
            changed = {23: {31: _KINGS_PREFIX + _KINGS_TAIL + " added"}}
            self.assertIs(repair_documented_imports(w, "2-kings", changed)[0], changed)
        self.assertIs(repair_documented_imports(
            {"id": "custom", "parser_kind": "first1k_tei"}, "2-kings", raw)[0], raw)

    def test_misplaced_psalm_marker_requires_both_source_passages(self) -> None:
        from studio.source_repairs import repair_documented_imports, _PSALM_46, _PSALM_84
        w = {"id": "grk-1st1k-lxx", "parser_kind": "first1k_tei"}
        raw = {88: {46: _PSALM_46, 84: _PSALM_84, 49: "other διάψαλμα."}}
        fixed, notes = repair_documented_imports(w, "psalms", raw)
        self.assertEqual(fixed[88][46], _PSALM_46 + " διάψαλμα.")
        self.assertNotIn("διάψαλμα", fixed[88][84])
        self.assertEqual(fixed[88][49], raw[88][49])
        self.assertIn("88:46/84", notes[88][0])
        self.assertEqual(raw[88][84], _PSALM_84)
        incomplete = {88: {84: _PSALM_84}}
        self.assertIs(repair_documented_imports(w, "psalms", incomplete)[0], incomplete)

    def test_swete_slips_and_divisions_are_exact_scoped_and_idempotent(self) -> None:
        from studio.source_repairs import repair_documented_imports
        csv = {"id": "grk-swete-csv", "parser_kind": "swete_csv"}
        ocr = {"id": "grk-1st1k-lxx", "parser_kind": "first1k_tei"}
        raw = {4: {5: "εἰς μέσον τοῦ Ἰροδάνου, καὶ ἀνελόμενος"},
               12: {20: "βασιλέα Συμοών, βασιλέα Μαμρώθ, βασιλέα Ἀζείφ,",
                    21: "βασιλέα Κάδης, βασιλέα Ζακάχ, βασιλέα Μαρεδὼθ καὶ βασιλέα Ἰεκὸμ τοῦ Χερμέλ,"}}
        fixed, notes = repair_documented_imports(csv, "joshua", raw)
        self.assertEqual(fixed[4][5], "εἰς μέσον τοῦ […] καὶ ἀνελόμενος", "a misspelt word casts no vote")
        self.assertEqual(fixed[12][21], "βασιλέα Κάδης, βασιλέα Ζακάχ,")
        self.assertEqual(fixed[12][22], "βασιλέα Μαρεδὼθ καὶ βασιλέα Ἰεκὸμ τοῦ Χερμέλ,", "Brenton's division")
        self.assertIn("Ἰορδάνου", notes[4][0])
        self.assertEqual(raw[4][5], "εἰς μέσον τοῦ Ἰροδάνου, καὶ ἀνελόμενος", "the parser output is untouched")
        self.assertNotIn(22, raw[12])
        self.assertEqual(repair_documented_imports(csv, "joshua", fixed), (fixed, {}))
        self.assertIs(repair_documented_imports(ocr, "joshua", {4: {5: raw[4][5]}})[0].get(4, {}).get(5), raw[4][5],
                      "a transcription slip is not repaired in the OCR copy")
        reread = {4: {5: "εἰς μέσον τοῦ Ἰορδάνου, καὶ ἀνελόμενος"}}
        self.assertIs(repair_documented_imports(csv, "joshua", reread)[0], reread, "a copy that no longer reads so")
        # Daniel 3:77/78 are exchanged once, recognised by their content.
        dan = {3: {77: "εὐλογεῖτε, αἱ πηγαί, τὸν κύριον·", 78: "εὐλογεῖτε, θάλασσαι καὶ ποταμοί, τὸν κύριον·"}}
        swapped, _ = repair_documented_imports(ocr, "daniel", dan)
        self.assertIn("θάλασσαι", swapped[3][77])
        self.assertEqual(repair_documented_imports(ocr, "daniel", swapped), (swapped, {}))
        # Numbers 16:36–17:13 renumbered as Brenton numbers them, only when the whole run is there.
        num = {16: {v: f"16:{v}" for v in range(1, 51)}, 17: {v: f"17:{v}" for v in range(1, 14)}}
        renum, notes = repair_documented_imports(csv, "numbers", num)
        self.assertEqual((renum[17][1], renum[17][16], renum[17][28]), ("16:36", "17:1", "17:13"))
        self.assertEqual(max(renum[16]), 35)
        self.assertEqual(repair_documented_imports(csv, "numbers", renum), (renum, {}))
        partial = {16: {v: "x" for v in range(1, 40)}, 17: {1: "y"}}
        self.assertIs(repair_documented_imports(csv, "numbers", partial)[0], partial)

    def test_brenton_proverbs_takes_saints_numbering(self) -> None:
        # Saints.Bible numbers Proverbs 30 and 31:1-9 apart; the Brenton e-text runs them on as 24:22-62.
        from studio.source_repairs import repair_documented_imports, _SPLITS
        w = {"id": "grk-brenton-sixtine", "parser_kind": "brenton_usfm"}
        openings = _SPLITS[("grk-brenton-sixtine", "proverbs")][2]
        verse_22 = "Ἐξαίφνης γὰρ τίσονται. " + " ".join(f"{o} λόγος {n}." for n, o in enumerate(openings, 1))
        raw = {24: {22: verse_22, **{v: f"24:{v}" for v in range(23, 63)}}, 31: {v: f"31:{v}" for v in range(10, 32)}}
        fixed, notes = repair_documented_imports(w, "proverbs", raw)
        self.assertEqual(fixed[24][22], "Ἐξαίφνης γὰρ τίσονται.")
        self.assertEqual(sorted(fixed[30]), list(range(1, 34)))
        self.assertTrue(fixed[30][1].startswith("τοὺς ἐμοὺς λόγους") and fixed[30][14].endswith("λόγος 14."))
        self.assertEqual((fixed[30][15], fixed[30][33], fixed[31][1], fixed[31][9]), ("24:35", "24:53", "24:54", "24:62"))
        self.assertEqual(max(fixed[24]), 34)
        self.assertEqual(" ".join(raw[24][22].split()), raw[24][22], "the parser output is untouched")
        self.assertEqual(repair_documented_imports(w, "proverbs", fixed), (fixed, {}))
        self.assertIs(repair_documented_imports(w, "psalms", raw)[0], raw)

    def test_independent_digitisations(self) -> None:
        from studio.catalog import independent_digitisations
        self.assertEqual(independent_digitisations(["1st1K-LXX", "Swete (B/A/א)"]), 1, "one OCR, two copies")
        self.assertEqual(independent_digitisations(["Swete-Amicarelli", "Swete (B/A/א)"]), 2)
        self.assertEqual(independent_digitisations(["Sixtine/Brenton", "Swete-Amicarelli"]), 1)


class TestCollatorRules(unittest.TestCase):
    def test_numeral_equivalence_requires_equal_values_and_wording(self) -> None:
        for forms in (["χ΄", "τετρακόσιοι"], ["ν΄", "πεντηκονταεπτά"], ["η΄", "ὀκτωκαίδεκα"],
                      ["ιβ᾽", "οβ΄", "δώδεκα"], ["γʹ", "ἢ"], ["βʹ", "καί"],
                      ["γʹ σκηνάς", "σκηνὰς τρεῖς"], ["βʹ", "δύο", "δευτέρᾳ"]):
            self.assertFalse(is_orthographic_equivalence(forms, "greek")[0], forms)
        for forms in (["η᾽", "ἢ"], ["δʹ", "δ᾽"], ["ςʹ", "σʹ"]):
            self.assertFalse(is_orthographic_equivalence(forms, "greek")[0], forms)
            cv = align_witnesses_for_verse(1, dict(zip(("A", "B"), forms)), {"A": 0.9, "B": 0.8}, "greek")
            self.assertEqual(cv.slots[0].kind, "substantive_variant", forms)
            self.assertEqual(len(set(cv.slots[0].form_keys.values())), 2, forms)
        for forms in (["ιβ΄", "δώδεκα"], ["κ᾽", "κ΄", "εἴκοσι"], ["φ΄", "πεντακόσιοι"],
                      ["δʹ", "τεσσάρων"], ["͵β", "δισχίλιοι"], ["κθ΄", "εἰκοσιεννέα"],
                      ["δʹ", "τέσσαρας"], ["γʹ", "τρίτος"], ["δʹ", "τέταρτος"],
                      ["ιβʹ", "δωδέκατος"], ["μʹ", "τεσσαράκοντα", "τεσσεράκοντα"]):
            self.assertTrue(is_orthographic_equivalence(forms, "greek")[0], forms)

    def test_numerals_do_not_include_elisions_or_damaged_words(self) -> None:
        from studio.collator import is_letter_numeral, _greek_letter_value
        for token in ("δ᾽", "΄οὐκ", "ἀγχιστε΄πυσῃ", "κ΄δρου", "πα΄ντας", "βιʹ"):
            self.assertFalse(is_letter_numeral(token), token)
        self.assertEqual(_greek_letter_value("χ΄"), 600)
        self.assertEqual(_greek_letter_value("υ΄"), 400)
        self.assertEqual(_greek_letter_value("͵βκʹ"), 2020)
        self.assertTrue(is_orthographic_equivalence(["δ᾽", "δέ"], "greek")[0])

    def test_numerals_align_with_the_number_not_its_neighbour(self) -> None:
        cv = align_witnesses_for_verse(20, {"A": "δύο ἢ τρεῖς", "B": "δυο η γʹ"},
                                       {"A": 0.9, "B": 0.96}, "greek")
        self.assertEqual(len(cv.slots), 3)
        self.assertEqual(set(cv.slots[1].raw_forms), {"ἢ", "η"})
        self.assertEqual(set(cv.slots[2].raw_forms), {"τρεῖς", "γʹ"})
        self.assertTrue(all(s.kind == "orthographic_noise" for s in cv.slots))

    def test_combined_itacism_and_doubled_consonant(self) -> None:
        forms = ["μνηστευθείσης", "μνησστευθισησ"]
        for pair in (forms, forms[::-1], forms + ["μνηστευθισης"]):
            ok, reason = is_orthographic_equivalence(pair, "greek")
            self.assertTrue(ok, pair)
            self.assertIn("ει / ι", reason)
            self.assertIn("double", reason)
        # Morphological distinctions and other vowel/prefix changes remain substantive.
        for pair in (["βάλλειν", "βαλιν"], ["γέννησις", "γενεσισ"], ["γεννήματα", "γενηματα"],
                     ["ἡμεῖς", "ὑμῖς"], ["ἐκρίθη", "ἐγκρειθη"], ["μνηστευθείσης", ""],
                     ["χειμάρρων", "χιμάρων"], ["χείμαρροι", "χίμαροι"]):
            self.assertFalse(is_orthographic_equivalence(pair, "greek")[0], pair)

    def test_movable_nu_only_on_real_movable_nu(self) -> None:
        self.assertTrue(is_orthographic_equivalence(["ἐκάλεσεν", "ἐκάλεσε"], "greek")[0])
        self.assertTrue(is_orthographic_equivalence(["πᾶσιν", "πᾶσι"], "greek")[0])
        self.assertFalse(is_orthographic_equivalence(["αὐτόν", "αὐτό"], "greek")[0])  # masc. vs neut.

    def test_imperative_idete_is_not_rewritten(self) -> None:
        from studio.collator import normalize_critical_token
        self.assertEqual(normalize_critical_token("ἴδετε", False, "greek"), "ἴδετε")  # "see!", not "you saw"
        self.assertEqual(normalize_critical_token("ἴδεν", False, "greek"), "εἶδεν")

    def test_kath_words_are_not_merged(self) -> None:
        cv = align_witnesses_for_verse(1, {"A": "καθὼς γέγραπται", "B": "καθότι γέγραπται"}, {"A": 0.9, "B": 0.8}, "greek")
        self.assertEqual(cv.slots[0].kind, "substantive_variant")

    def test_nomina_sacra_resolve_to_full_words(self) -> None:
        cv = align_witnesses_for_verse(1, {"ed": "Ἰησοῦ Χριστοῦ υἱοῦ Δαυίδ", "ms": "ιυ\u0305 χυ\u0305 υιου δαδ\u0305"}, {"ed": 0.9, "ms": 0.98}, "greek")
        self.assertTrue(all(s.kind != "substantive_variant" for s in cv.slots), [(s.raw_forms, s.kind) for s in cv.slots])

    def test_hebrew_conventions(self) -> None:
        self.assertEqual(canonical_compare_key(nfc("כׇּל"), "hebrew"), canonical_compare_key(nfc("כָּל"), "hebrew"))
        self.assertEqual(canonical_compare_key(nfc("לַֽיהֹוָ֑ה"), "hebrew"), canonical_compare_key(nfc("לַֽיהוָ֑ה"), "hebrew"))
        self.assertEqual(canonical_compare_key(nfc("בִּירוּשָׁלַ֖\u200dִם"), "hebrew"), canonical_compare_key(nfc("בִּירוּשָׁלִַ֖ם"), "hebrew"))
        self.assertEqual(canonical_compare_key("(הוצא)", "hebrew"), canonical_compare_key("הוצא", "hebrew"))

    def test_hebrew_pointing_conventions(self) -> None:
        from studio.collator import hebrew_pointing_convention as conv
        self.assertTrue(conv([nfc("וַיִּשָּׁאֶר"), nfc("וַיִּשָׁאֶר")]))       # dagesh left out in L
        self.assertTrue(conv([nfc("אׇהֳלֹה"), "אהלה"]))                       # bare ketiv vs pointed form
        self.assertFalse(conv([nfc("אַל"), nfc("אֶל")]))                      # vowel quality: a real difference
        self.assertFalse(conv([nfc("לְדַעְתָּהּ"), nfc("לְדַעְתָּה")]))          # suffix mappiq: her / -
        self.assertFalse(conv([nfc("שָׂם"), nfc("שָׁם")]))                      # shin / sin
        ok, reason = is_orthographic_equivalence([nfc("וַיִּשָּׁאֶר"), nfc("וַיִּשָׁאֶר")], "hebrew")
        self.assertTrue(ok and "Pointing convention" in reason)

    def test_latin_spelling_conventions(self) -> None:
        for a, b in [("inluminent", "illuminent"), ("aput", "apud"), ("conpleuitque", "compleuitque"),
                     ("adquiesceret", "acquiesceret"), ("sescentorum", "sexcentorum"), ("temptauit", "tentavit")]:
            self.assertTrue(is_orthographic_equivalence([a, b], "latin")[0], (a, b))
        ok, reason = is_orthographic_equivalence(["corbum", "corvum"], "latin")
        self.assertTrue(ok and "betacism" in reason)
        self.assertFalse(is_orthographic_equivalence(["bibit", "vivit"], "latin")[0], "two different verbs")

    def test_versification_realignment(self) -> None:
        reference = {1: "Et erit post haec effundam spiritum meum super omnem carnem", 2: "sed et super servos meos"}
        candidates = {(2, 28): "Et erit post haec effundam spiritum meum super omnem carnem", (2, 29): "sed et super servos meos et ancillas",
                      (3, 1): "Quia ecce in diebus illis et in tempore illo", (3, 2): "congregabo omnes gentes"}
        mapped, moved, _ = align_versification(reference, 3, candidates, "latin")
        self.assertEqual(moved, {1: "2:28", 2: "2:29"})
        self.assertIn("effundam", mapped[1])

    def test_best_match_wins_in_formulaic_chapters(self) -> None:
        reference = {33: "triginta duo millia ducenti", 35: "triginta quinque millia quadringenti"}
        candidates = {(1, 33): "quadraginta millia quingenti", (1, 35): "triginta duo millia ducenti", (1, 37): "triginta quinque millia quadringenti"}
        mapped, moved, _ = align_versification(reference, 1, candidates, "latin")
        self.assertEqual(moved, {33: "1:35", 35: "1:37"})


class TestAdjudicationRules(unittest.TestCase):
    def test_ambiguous_numeral_does_not_pool_distinct_grammatical_forms(self) -> None:
        cv = align_witnesses_for_verse(1, {"A": "δύο", "B": "δευτέρᾳ", "C": "βʹ"},
                                       {"A": 0.7, "B": 0.8, "C": 0.98}, "greek")
        result = OfflinePhilologicalBrain().adjudicate_chapter("greek", "Test", 1, [cv])[0]
        self.assertEqual(len(result.apparatus), 1)
        self.assertEqual({v["reading"] for v in result.apparatus[0].variants}, {"δύο", "δευτέρᾳ"})

    def test_combined_spelling_is_logged_and_preserves_the_witness(self) -> None:
        from studio.brains.textual_analysis import TextualAnalysisBrain
        texts = {"SBLGNT": "μνηστευθείσης τῆς μητρὸς", "א (01)": "μνησστευθισησ τησ μητροσ"}
        cv = align_witnesses_for_verse(18, texts, {"SBLGNT": 0.9, "א (01)": 0.96}, "greek")
        cv.base_siglum = "SBLGNT"
        cv.testament = "NT"
        for brain in (OfflinePhilologicalBrain(), TextualAnalysisBrain()):
            result = brain.adjudicate_chapter("greek", "Matthew", 1, [cv])[0]
            self.assertEqual(result.critical_text, texts["SBLGNT"])
            self.assertEqual(result.apparatus, [])
            noise = next(d for d in result.disregarded if "μνησστευθισησ" in d.disregarded_forms)
            self.assertIn("א (01)", noise.witnesses)
            self.assertIn("ει / ι", noise.reason)
            self.assertEqual(cv.witness_texts["א (01)"], texts["א (01)"])

    def test_combined_spelling_pools_support_without_merging_other_readings(self) -> None:
        texts = {"A": "μνηστευθείσης", "B": "μνησστευθισησ", "C": "λυθείσης"}
        cv = align_witnesses_for_verse(1, texts, {"A": 0.7, "B": 0.7, "C": 0.98}, "greek")
        cv.base_siglum = "A"
        cv.testament = "NT"
        result = OfflinePhilologicalBrain().adjudicate_chapter("greek", "Test", 1, [cv])[0]
        self.assertEqual(result.critical_text, "μνηστευθείσης")
        self.assertEqual(len(result.apparatus), 1)
        unit = result.apparatus[0]
        self.assertEqual(set(unit.lemma_witnesses), {"A", "B"})
        self.assertEqual([v["reading"] for v in unit.variants], ["λυθείσης"])
        self.assertTrue(any("μνησστευθισησ" in d.disregarded_forms for d in result.disregarded))

    brain = OfflinePhilologicalBrain()

    def adjudicate(self, texts, weights, language="greek", **extra):
        cv = align_witnesses_for_verse(1, texts, weights, language)
        for k, v in extra.items():
            setattr(cv, k, v)
        return self.brain.adjudicate_chapter(language, "Test", 1, [cv])[0]

    def test_genuine_repetition_is_not_deleted(self) -> None:
        adj = self.adjudicate(
            {"A": "ἀμὴν ἀμὴν λέγω ὑμῖν", "B": "ἀμὴν ἀμὴν λέγω ὑμῖν", "C": "ἀμὴν λέγω ὑμῖν"},
            {"A": 0.95, "B": 0.94, "C": 0.72},
        )
        self.assertTrue(adj.critical_text.startswith("ἀμὴν ἀμὴν"), adj.critical_text)
        self.assertTrue(adj.apparatus, "the omission must stay visible in the apparatus")

    def test_sister_copy_omission_still_counts_as_one_edition(self) -> None:
        adj = self.adjudicate(
            {"CSV": "καὶ εἶπεν", "OCR": "καὶ μος εἶπεν", "Other": "καὶ λόγον εἶπεν"},
            {"CSV": 0.93, "OCR": 0.92, "Other": 0.84},
            witness_families={"CSV": "swete", "OCR": "swete", "Other": "other"},
            base_siglum="CSV", testament="OT")
        self.assertEqual(adj.critical_text, "καὶ εἶπεν")
        self.assertFalse(any(v["reading"] == "μος" for a in adj.apparatus for v in a.variants))
        self.assertTrue(any("μος" in d.disregarded_forms and "OCR" in d.witnesses for d in adj.disregarded))

    def test_verse_absent_from_heavier_witnesses_is_bracketed_not_deleted(self) -> None:
        adj = self.adjudicate(
            {"Byz": "Ἀναστὰς δὲ πρωῒ", "TR": "Ἀναστὰς δὲ πρωῒ"}, {"Byz": 0.72, "TR": 0.6},
            absent_witnesses=["B", "א"], witness_weights={"Byz": 0.72, "TR": 0.6, "B": 0.98, "א": 0.96},
        )
        self.assertTrue(adj.critical_text.startswith("⟦") and adj.critical_text.endswith("⟧"))
        self.assertEqual(adj.apparatus[0].kind, "verse")
        self.assertLess(adj.confidence, 0.5)

    def test_same_edition_disagreement_is_encoding_noise(self) -> None:
        adj = self.adjudicate(
            {"Clem1598-USFX": "Aleph Quomodo sedet sola", "Clem-Saints": "Quomodo sedet sola"},
            {"Clem1598-USFX": 0.88, "Clem-Saints": 0.86}, "latin",
            witness_families={"Clem1598-USFX": "clementine", "Clem-Saints": "clementine"}, base_siglum="Clem1598-USFX",
        )
        self.assertEqual(adj.apparatus, [])
        self.assertTrue(adj.disregarded)

    def test_apparatus_positions_point_at_the_lemma(self) -> None:
        adj = self.adjudicate(
            {"A": "καὶ ἐγέννησεν τὸν Ἀσάφ", "B": "καὶ ἐγέννησεν τὸν Ἀσάφ", "C": "καὶ ἐγέννησεν τὸν Ἀσά"},
            {"A": 0.95, "B": 0.94, "C": 0.72},
        )
        item = adj.apparatus[0]
        self.assertEqual(adj.critical_text.split()[item.word_index], "Ἀσάφ")

    class _Lex:
        """Minimal corpus-frequency stand-in."""
        def __init__(self, counts):
            self.counts = counts
            self.repeat_families = {}
            self.best_form = {}

        def key_count(self, k):
            return self.counts.get(canonical_compare_key(k, "greek") if " " not in k else k, 0)

        def form_count(self, f):
            return 1000

    def test_ocr_swap_only_inside_one_edition_family(self) -> None:
        lex = self._Lex({"λεγει": 3, "λεγε": 900})
        # the "rare" reading is printed by two independent editions: a real reading, never swapped
        adj = self.adjudicate({"A": "καὶ λέγει αὐτῷ", "B": "καὶ λέγει αὐτῷ", "C": "καὶ λέγε αὐτῷ"},
                              {"A": 0.95, "B": 0.94, "C": 0.72}, lexicon=lex,
                              witness_families={"A": "a", "B": "b", "C": "c"})
        self.assertIn("λέγει", adj.critical_text)
        # a singular reading of a diplomatic manuscript is never imported by the swap
        adj = self.adjudicate({"Swete": "καὶ λέγει αὐτῷ", "B (03)": "καὶ λέγε αὐτῷ"},
                              {"Swete": 0.92, "B (03)": 0.98 - 0.1}, lexicon=lex,
                              witness_families={"Swete": "s", "B (03)": "b"})
        self.assertIn("λέγει", adj.critical_text)

    def test_ocr_signature_is_repaired(self) -> None:
        lex = self._Lex({"προσωπον": 900})  # the damaged form is unattested, the repair common
        adj = self.adjudicate({"1st1K": "κατὰ πρόσαωπον αὐτοῦ", "Swete": "κατὰ πρόσαωπον αὐτοῦ", "Brenton": "κατὰ πρόσωπον αὐτοῦ"},
                              {"1st1K": 0.92, "Swete": 0.90, "Brenton": 0.84}, lexicon=lex,
                              witness_families={"1st1K": "swete", "Swete": "swete", "Brenton": "brenton"},
                              base_siglum="1st1K")
        self.assertIn("πρόσωπον", adj.critical_text)
        self.assertTrue(any("OCR signature" in d.reason for d in adj.disregarded))

    def test_lost_iota_subscript_needs_a_dative_context(self) -> None:
        # Gen 2:2: ἡμέρα and ἕκτη are common nominatives, so counts cannot tell; after τῇ only the
        # dative is grammatical, so the subscripts were lost in the OCR family.
        lex = self._Lex({})
        fam = {"1st1K": "swete", "Swete": "swete", "Brenton": "brenton"}
        w = {"1st1K": 0.92, "Swete": 0.90, "Brenton": 0.84}
        adj = self.adjudicate({"1st1K": "ἐν τῇ ἡμέρα τῇ ἕκτη τὰ ἔργα", "Swete": "ἐν τῇ ἡμέρα τῇ ἕκτη τὰ ἔργα",
                               "Brenton": "ἐν τῇ ἡμέρᾳ τῇ ἕκτῃ τὰ ἔργα"}, w, lexicon=lex, witness_families=fam,
                              base_siglum="1st1K")
        self.assertIn("ἡμέρᾳ τῇ ἕκτῃ", adj.critical_text)
        self.assertTrue(any("only the dative" in d.reason for d in adj.disregarded))
        # with no governing word the nominative may be real: the heavier family's reading stands
        adj = self.adjudicate({"1st1K": "καὶ ἡμέρα ἕκτη", "Swete": "καὶ ἡμέρα ἕκτη", "Brenton": "καὶ ἡμέρᾳ ἕκτῃ"},
                              w, lexicon=lex, witness_families=fam, base_siglum="1st1K")
        self.assertIn("ἡμέρα ἕκτη", adj.critical_text)

    def test_recurring_ocr_form_of_a_very_common_word(self) -> None:
        lex = self._Lex({"κοι": 147, "και": 159184, "λογοι": 3, "λογοσ": 5000})
        self.assertTrue(self.brain._ocr_shape_slip("κοι", "και", lex))  # κοὶ ἦλθεν (Gen 11:31)
        self.assertFalse(self.brain._ocr_shape_slip("ηλθεν", "ηλθον", lex))  # a real ending, never

    def test_only_ocr_shaped_changes_are_repaired(self) -> None:
        # Genuine rare readings of B occur once, exactly like OCR garbage: only the shape decides.
        from studio.brains.offline_philological import _ocr_shaped, _prefix_change
        lex = self._Lex({"απεκτεννεν": 1, "απεκτεινεν": 89, "ειρεν": 5, "ειπε": 1628, "εστηρισται": 1, "εστηρικται": 10})
        self.assertFalse(self.brain._ocr_word_slip("απεκτεννεν", "απεκτεινεν", lex, False))  # ν/ι: a spelling
        self.assertFalse(self.brain._ocr_word_slip("εστηρισται", "εστηρικται", lex, False))  # σ/κ: another form
        self.assertTrue(self.brain._ocr_word_slip("ειρεν", "ειπε", lex, False))  # ρ/π misread, movable ν aside
        self.assertTrue(_ocr_shaped("σησω", "στησω") and _ocr_shaped("απεατεψαμεν", "απεστρεψαμεν"))
        self.assertTrue(_prefix_change("προεθηκεν", "προσεθηκεν") and _prefix_change("ενκατελειπον", "εγκατελιπον"))

    def test_broken_tokens_and_stray_latin_letters(self) -> None:
        fam = {"1st1K": "swete", "Swete": "swete", "Brenton": "brenton"}
        w = {"1st1K": 0.92, "Swete": 0.90, "Brenton": 0.84}
        lex = self._Lex({"σησω": 1, "στησω": 19})
        adj = self.adjudicate({"1st1K": "καὶ σ,ήσω τὴν διαθήκην", "Swete": "καὶ σ,ήσω τὴν διαθήκην",
                               "Brenton": "καὶ στήσω τὴν διαθήκην"}, w, lexicon=lex, witness_families=fam, base_siglum="1st1K")
        self.assertIn("στήσω", adj.critical_text)
        adj = self.adjudicate({"1st1K": "εἰς D τὰ ὀπίσω", "Swete": "εἰς D τὰ ὀπίσω", "Brenton": "εἰς τὰ ὀπίσω"},
                              w, lexicon=lex, witness_families=fam, base_siglum="1st1K")
        self.assertEqual(adj.critical_text, "εἰς τὰ ὀπίσω")

    def test_dittography_with_loss(self) -> None:
        # Gen 15:3: the doubled σπέρμα stands where Brenton reads ἔδωκας (Greek OT, one family).
        fam = {"1st1K": "swete", "Swete": "swete", "Brenton": "brenton"}
        adj = self.adjudicate({"1st1K": "ἐμοὶ οὐκ σπέρμα σπέρμα ὁ δὲ", "Swete": "ἐμοὶ οὐκ σπέρμα σπέρμα ὁ δὲ",
                               "Brenton": "ἐμοὶ οὐκ ἔδωκας σπέρμα ὁ δὲ"}, {"1st1K": 0.92, "Swete": 0.90, "Brenton": 0.84},
                              lexicon=self._Lex({}), witness_families=fam, base_siglum="1st1K", testament="OT")
        self.assertIn("οὐκ ἔδωκας σπέρμα ὁ", adj.critical_text)

    def test_neighbouring_units_must_be_attested_together(self) -> None:
        # John 14:7: voted unit by unit the clause loses its verb ('ἂν καὶ·'), which no witness reads.
        texts = {
            "B (03)": "καὶ τὸν πατέρα μου ἂν ᾔδειτε ἀπʼ ἄρτι", "SBLGNT": "καὶ τὸν πατέρα μου ἂν ᾔδειτε· ἀπʼ ἄρτι",
            "Nestle1904": "καὶ τὸν πατέρα μου ἂν ᾔδειτε· ἀπʼ ἄρτι",
            "SRGNT": "καὶ τὸν πατέρα μου γνώσεσθε, καὶ ἀπʼ ἄρτι", "BHP": "καὶ τὸν πατέρα μου γνώσεσθε, καὶ ἀπʼ ἄρτι",
            "א (01)": "και τον πατερα μου γνωσεσθαι και απ αρτι",
            "RP2018": "καὶ τὸν πατέρα μου ἐγνώκειτε ἄν· καὶ ἀπʼ ἄρτι", "TR": "καὶ τὸν πατέρα μου ἐγνώκειτε ἂν· καὶ ἀπʼ ἄρτι",
        }
        weights = {"B (03)": 0.98, "SBLGNT": 0.94, "Nestle1904": 0.90, "SRGNT": 0.95, "BHP": 0.88, "א (01)": 0.96,
                   "RP2018": 0.72, "TR": 0.60}
        adj = self.adjudicate(texts, weights, witness_families={s: s for s in texts}, testament="NT")
        words = adj.critical_text.replace("·", "").replace(",", "").split()
        printed = " ".join(words[4:])
        readings = {" ".join(t.replace("·", "").replace(",", "").split()[4:]) for t in texts.values()}
        self.assertTrue(any(canonical_compare_key(printed, "greek") == canonical_compare_key(r, "greek") for r in readings),
                        adj.critical_text)

    def test_three_swete_copies_vote_once(self) -> None:
        fam = {"CSV": "swete", "1st1K": "swete", "Swete": "swete", "Brenton": "brenton"}
        w = {"CSV": 0.93, "1st1K": 0.92, "Swete": 0.90, "Brenton": 0.84}
        ot = dict(witness_families=fam, base_siglum="CSV", testament="OT", lexicon=self._Lex({}))
        # one word of the clean copy is not outvoted by the OCR copies' gap plus Brenton's joined form (Josh 8:9)
        adj = self.adjudicate({"CSV": "καὶ ἀσπὶς ἀνὰ μέσον τῶν ὤμων", "1st1K": "καὶ ἀσπὶς ἀνὰ τῶν ὤμων",
                               "Swete": "καὶ ἀσπὶς ἀνὰ τῶν ὤμων", "Brenton": "καὶ ἀσπὶς ἀναμέσον τῶν ὤμων"}, w, **ot)
        self.assertIn("ἀνὰ μέσον τῶν", adj.critical_text)
        # the copy that is the other edition's reading in another spelling stands for the edition (2 Sam 9:5)
        adj = self.adjudicate({"CSV": "τοῦ οἴκου Μαξεὶρ υἱοῦ", "1st1K": "τοῦ οἴκου Μαχεὶρ υἱοῦ",
                               "Swete": "τοῦ οἴκου Μαχεὶρ υἱοῦ", "Brenton": "τοῦ οἴκου Μαχὶρ υἱοῦ"}, w, **ot)
        self.assertIn("Μαχ", adj.critical_text)
        self.assertNotIn("Μαξ", adj.critical_text)
        # words one copy skipped stay when the other copies and another edition have words there (Josh 10:35)
        adj = self.adjudicate({"CSV": "καὶ ἐφόνευσεν ὃν τρόπον",
                               "1st1K": "καὶ ἐφόνευσεν αὐτὴν ἐν στόματι ξίφους ὃν τρόπον",
                               "Swete": "καὶ ἐφόνευσεν αὐτὴν ἐν στόματι ξίφους ὃν τρόπον",
                               "Brenton": "καὶ ἐφόνευσεν αὐτὴν ἐν στόματι ῥομφαίας ὃν τρόπον"}, w, **ot)
        self.assertIn("ἐν στόματι ξίφους", adj.critical_text)

        class _Forms(self._Lex):
            def form_count(self, f):
                return {"Ἰεδᾶε": 1}.get(f, 50)

        # the clean copy's form found nowhere else, one letter from the OCR copies' common form: a keying slip
        adj = self.adjudicate({"CSV": "μετ αὐτοῦ Ἰεδᾶε ὁ πατὴρ", "1st1K": "μετ αὐτοῦ Ἰωδᾶε ὁ πατὴρ",
                               "Swete": "μετ αὐτοῦ Ἰωδᾶε ὁ πατὴρ", "Brenton": "μετ αὐτοῦ Ἰωιαδὲ ὁ πατὴρ"},
                              w, **dict(ot, lexicon=_Forms({})))
        self.assertIn("Ἰωδᾶε", adj.critical_text)

    def test_sister_copy_slip_is_not_a_variant_and_pooling_is_logged(self) -> None:
        # Deut 31:12: Swete Clean's 'Τύριον' against First1KGreek and Brenton (invariant 4).
        fam = {"1st1K": "swete", "Swete": "swete", "Brenton": "brenton"}
        adj = self.adjudicate({"1st1K": "φοβεῖσθαι Κύριον τὸν θεόν", "Swete": "φοβεῖσθαι Τύριον τὸν θεόν",
                               "Brenton": "φοβεῖσθαι Κύριον τὸν θεόν"}, {"1st1K": 0.92, "Swete": 0.90, "Brenton": 0.84},
                              witness_families=fam, base_siglum="1st1K")
        self.assertEqual(adj.apparatus, [])
        self.assertIn("Κύριον", adj.critical_text)
        self.assertTrue(any("digital copies of the same printed edition" in d.reason for d in adj.disregarded))
        # B's itacistic spelling is pooled with its reading before the vote, and that is logged (invariant 7)
        adj = self.adjudicate({"A": "καὶ γινώσκομεν αὐτόν", "B (03)": "και γεινωσκομεν αυτον", "C": "καὶ ἐγνώκαμεν αὐτόν"},
                              {"A": 0.94, "B (03)": 0.98, "C": 0.72}, witness_families={"A": "a", "B (03)": "b", "C": "c"})
        self.assertTrue(any("pooled" in d.reason for d in adj.disregarded), [d.reason for d in adj.disregarded])

    def test_latin_lookalikes_keep_the_damaged_editions_own_word(self) -> None:
        from studio.brains.offline_philological import _transliterate_latin
        self.assertEqual(_transliterate_latin("‘Yμεῖς")[0], nfc("Ὑμεῖς"))
        self.assertEqual(_transliterate_latin("’Aχεικὰμ")[0], nfc("Ἀχεικὰμ"))
        self.assertEqual(_transliterate_latin("lωὰς")[0], nfc("Ἰωὰς"))
        self.assertEqual(_transliterate_latin("Aἴνει")[0], nfc("Αἴνει"))  # B's imperative, not Brenton's αἰνεῖ

    def test_subscript_grammar_guards(self) -> None:
        from studio.brains.offline_philological import _subscript_needed
        self.assertTrue(_subscript_needed("ὅλῃ", "γῇ", "γῆ"))           # Exod 5:12
        self.assertTrue(_subscript_needed("ᾗ", "ἡμέρᾳ", "ἡμέρα"))       # Num 7:1
        self.assertFalse(_subscript_needed("τῷ", "Φαραῷ", "Φαραώ"))     # an indeclinable name
        self.assertFalse(_subscript_needed("βαλλαντίῳ,", "ἐπεσημῄνω", "ἐπεσημήνω"))  # across a comma, a verb
        self.assertFalse(_subscript_needed("θύρᾳ", "τῇς", "τῆς"))       # a genitive article
        self.assertFalse(_subscript_needed("νόμῳ", "Μωυσῇ", "Μωυσῆ"))  # a capitalised genitive

    def test_b_spellings_and_names_are_not_repaired_from_brenton(self) -> None:
        from studio.brains.offline_philological import _b_doubled_consonant, _same_but_subscript, _subscript_needed
        self.assertTrue(_b_doubled_consonant("παρενεβαλλον", "παρενεβαλον"))   # B's doubled λ is kept
        self.assertFalse(_b_doubled_consonant("πολεμονν", "πολεμον"))         # a doubled final letter is OCR
        self.assertFalse(_b_doubled_consonant("πατεερ", "πατερ"))             # so is a doubled vowel
        self.assertTrue(_same_but_subscript("Ῥεβέκκα", "Ῥεβέκκᾳ"))           # only the subscript was lost
        self.assertFalse(_same_but_subscript("Λοῦζα", "Λουζᾷ"))              # Brenton declines B's indeclinable name
        self.assertTrue(_subscript_needed("τῇ", "Ῥεβέκκᾳ", "Ῥεβέκκα"))
        self.assertFalse(_subscript_needed("ἐν", "Λουζᾷ", "Λοῦζα"))
        self.assertFalse(_subscript_needed("τῷ", "Φαραῴ", "Φαραώ"))           # acute + subscript: no Greek dative
        self.assertFalse(_subscript_needed("ἵνα", "μνησθῷ", "μνησθῶ"))        # -ῶ may be a 1st person

    def test_spill_division_snaps_to_the_anchor(self) -> None:
        from studio.engine import _snap_division
        toks = "καὶ πονηρὸν ἐφάνη τὸ ῥῆμα ἐν ὀφθαλμοῖς κυρίου. Καὶ ἀπέστειλεν κύριος τὸν Ναθὰν".split()
        cut = _snap_division(toks, "καὶ πονηρὸν ἐφάνη τὸ ῥῆμα ἐν ὀφθαλμοῖς Κυρίου.",
                             "Καὶ ἀπέστειλε Κύριος τὸν Νάθαν τὸν προφήτην πρὸς Δαυίδ", "greek", 10)
        self.assertEqual(toks[cut], "Καὶ")  # the scored cut (two words late) is moved to the anchor's division
        # Deut 6:25 / 7:1: words the witness alone has at the break are a gap; a cut inside it is kept
        toks = "ἐὰν φυλασσώμεθα ποιεῖν ἐναντίον Κυρίου τοῦ θεοῦ ἡμῶν Κύριος. εἰσαγάγῃ σε κύριος".split()
        cut = _snap_division(toks, "ἐὰν φυλασσώμεθα ποιεῖν ἐναντίον Κυρίου τοῦ θεοῦ ἡμῶν",
                             "Ἐὰν δὲ εἰσαγάγῃ σε Κύριος", "greek", 9)
        self.assertEqual(cut, 9)

    def test_duplicated_tail_rule_leaves_a_different_division_alone(self) -> None:
        # Ezek 21:7: Swete ends the verse with a clause Brenton opens 21:8 with; Swete's 21:8 lacks it.
        from studio.engine import _drop_duplicated_tails
        mapped = {7: "καὶ ἐπίβλεψον ἐπὶ τὰ ἅγια αὐτῶν καὶ προφητεύσεις ἐπὶ τὴν γῆν τοῦ Ἰσραήλ",
                  8: "καὶ ἐρεῖς πρὸς τὴν γῆν τοῦ Ἰσραήλ ἰδοὺ ἐγὼ πρὸς σέ"}
        reference = {7: "καὶ ἐπίβλεψον ἐπὶ τὰ ἅγια αὐτῶν",
                     8: "καὶ προφητεύσεις ἐπὶ τὴν γῆν τοῦ Ἰσραὴλ καὶ ἐρεῖς πρὸς τὴν γῆν τοῦ Ἰσραὴλ ἰδοὺ ἐγὼ πρὸς σέ"}
        self.assertEqual(_drop_duplicated_tails(mapped, reference, "greek"), [])
        self.assertIn("προφητεύσεις", mapped[7])

    def test_duplicated_tail_is_cut(self) -> None:
        # Lev 19:30 in Swete ends with 19:31's clause, which its own 19:31 also has.
        from studio.engine import _drop_duplicated_tails
        mapped = {30: "τὰ σάββατά μου φυλάξεσθε καὶ ἀπὸ τῶν ἁγίων μου θοις καὶ τοῖς ἐπαοιδοῖς οὐ προσκολληθήσεσθε ἐκμιανθῆναι ἐν αὐτοῖς",
                  31: "οὐκ ἐπακολουθήσετε ἐγγαστριμύθοις καὶ τοῖς ἐπαοιδοῖς οὐ προσκολληθήσεσθε ἐκμιανθῆναι ἐν αὐτοῖς ἐγώ εἰμι κύριος"}
        reference = {30: "τὰ σάββατά μου φυλάξεσθε καὶ ἀπὸ τῶν ἁγίων μου φοβηθήσεσθε ἐγώ εἰμι κύριος",
                     31: "οὐκ ἐπακολουθήσετε ἐγγαστριμύθοις καὶ τοῖς ἐπαοιδοῖς οὐ προσκολληθήσεσθε ἐκμιανθῆναι ἐν αὐτοῖς ἐγώ εἰμι κύριος"}
        notes = _drop_duplicated_tails(mapped, reference, "greek")
        self.assertTrue(notes)
        self.assertNotIn("ἐπαοιδοῖς", mapped[30])
        self.assertIn("ἐπαοιδοῖς", mapped[31])

    def test_word_split_between_two_positions_is_printed_once(self) -> None:
        # κύριε stands at two places, each outvoted, though most of the weight has it (Matt 20:30)
        texts = {
            "B (03)": "ἐλέησον ἡμᾶς κύριε υἱὸς Δαυίδ", "SBLGNT": "ἐλέησον ἡμᾶς κύριε υἱὸς Δαυίδ",
            "Nestle1904": "ἐλέησον ἡμᾶς κύριε υἱὸς Δαυίδ",
            "BHP": "κύριε ἐλέησον ἡμᾶς υἱὸς Δαυίδ", "RP2018": "κύριε ἐλέησον ἡμᾶς υἱὸς Δαυίδ",
            "א (01)": "ἐλέησον ἡμᾶς υἱὸς Δαυίδ", "SRGNT": "ἐλέησον ἡμᾶς υἱὸς Δαυίδ",
        }
        weights = {"B (03)": 0.98, "SBLGNT": 0.94, "Nestle1904": 0.90, "BHP": 0.88, "RP2018": 0.72, "א (01)": 0.96, "SRGNT": 0.95}
        adj = self.adjudicate(texts, weights, witness_families={s: s for s in texts}, testament="NT")
        self.assertEqual(adj.critical_text.count("κύριε"), 1, adj.critical_text)
        notes = " ".join(a.note for a in adj.apparatus)
        self.assertIn("word conservation", notes)
        unit = next(a for a in adj.apparatus if "conservation" in a.note)
        self.assertLess(adj.confidence, 0.85)
        self.assertTrue(unit.analysis)
        lxx = self.adjudicate(texts, weights, witness_families={s: s for s in texts}, testament="OT")
        self.assertEqual(lxx.critical_text.count("κύριε"), 0, "off outside the Greek NT (OCR-damaged files)")

    def test_calibrated_confidence_is_explained(self) -> None:
        adj = self.adjudicate({"A": "καὶ εἶπεν αὐτῷ", "B": "καὶ εἶπεν αὐτῷ", "C": "καὶ εἶπεν αὐτοῖς"},
                              {"A": 0.95, "B": 0.94, "C": 0.72}, testament="NT",
                              witness_families={"A": "a", "B": "b", "C": "c"})
        self.assertTrue(0.5 < adj.confidence < 0.99)
        basis = next(f for f in adj.analysis if f["canon"] == "confidence")
        self.assertIn("calibrated on the Greek NT", basis["note"])

    def test_single_stream_nt_verse_is_bracketed(self) -> None:
        adj = self.adjudicate({"RP2018 (Byz)": "καὶ ταῦτα εἰπὼν ἀπέλυσε τὴν ἐκκλησίαν", "TR (KJTR)": "καὶ ταῦτα εἰπὼν ἀπέλυσε τὴν ἐκκλησίαν"},
                              {"RP2018 (Byz)": 0.72, "TR (KJTR)": 0.6}, testament="NT",
                              single_stream="Only one text stream (Byzantine / ecclesiastical) has this verse.")
        self.assertTrue(adj.critical_text.startswith("⟦"))
        self.assertLessEqual(adj.confidence, 0.2)

    def test_adjacent_units_with_same_witness_split_merge(self) -> None:
        cv = align_witnesses_for_verse(
            1, {"A": "ὁ ἔχων τὸν υἱὸν ἔχει τὴν ζωήν", "B": "ὁ ἔχων τὸν υἱὸν ἔχει τὴν ζωήν", "C": "ὁ ἔχων ζωήν"},
            {"A": 0.95, "B": 0.94, "C": 0.72}, "greek",
        )
        omissions = [s for s in cv.slots if s.kind == "substantive_variant"]
        self.assertEqual(len(omissions), 1, [s.raw_forms for s in cv.slots])
        self.assertIn("τὸν υἱὸν ἔχει τὴν", next(iter(f for f in omissions[0].raw_forms if f != "om.")))


class _FakeClaude:
    """Stands in for anthropic.Anthropic(): records requests, returns a canned structured answer."""

    def __init__(self, answer=None, stop_reason="end_turn"):
        import json as _json
        from types import SimpleNamespace as NS
        self.requests = []
        outer = self

        class _Messages:
            def create(self, **kwargs):
                outer.requests.append(kwargs)
                payload = _json.loads(kwargs["messages"][0]["content"])
                units = answer(payload) if callable(answer) else (answer or [])
                return NS(stop_reason=stop_reason, stop_details=NS(category="test") if stop_reason == "refusal" else None,
                          content=[NS(type="text", text=_json.dumps({"units": units}))])

        self.beta = NS(messages=_Messages())


class TestTextualAnalysisBrain(unittest.TestCase):
    def brain(self, **cfg):
        from studio.brains.textual_analysis import TextualAnalysisBrain
        config = BrainConfig(provider_id="textual_analysis", **cfg)
        return TextualAnalysisBrain(config)

    def chapter(self, brain, texts, weights, testament="NT", **ctx):
        cv = align_witnesses_for_verse(1, texts, weights, "greek")
        cv.witness_families = {s: s for s in texts}
        cv.testament = testament
        brain.set_context(book_slug="", testament=testament, **ctx)
        return brain.adjudicate_chapter("greek", "Test", 1, [cv])[0]

    TEXTS = {"A": "καὶ εἶπεν αὐτῷ ὁ λαός", "B": "καὶ εἶπεν αὐτῷ ὁ λαός", "C": "καὶ εἶπεν ὁ λαός"}
    WEIGHTS = {"A": 0.95, "B": 0.94, "C": 0.72}

    def test_homoeoteleuton_cancels_shorter_reading_bonus(self) -> None:
        texts = {"A": "τὸν πατέρα ἔχει ὁ ὁμολογῶν τὸν υἱὸν καὶ τὸν πατέρα ἔχει", "B": "τὸν πατέρα ἔχει"}
        adj = self.chapter(self.brain(), texts, {"A": 0.72, "B": 0.98})
        canons = [f["canon"] for a in adj.apparatus for f in a.analysis]
        self.assertIn("transcriptional: homoeoteleuton", canons)
        # without the lectio-brevior bonus B (0.98) still outweighs A (0.72): the analysis informs, it does not invent weight
        self.assertEqual(adj.critical_text, "τὸν πατέρα ἔχει")

    def test_eye_skip_is_nt_only_and_two_streams_are_labelled(self) -> None:
        texts = {"A": "τὸν πατέρα ἔχει ὁ ὁμολογῶν τὸν υἱὸν καὶ τὸν πατέρα ἔχει", "B": "τὸν πατέρα ἔχει"}
        adj = self.chapter(self.brain(), texts, {"A": 0.72, "B": 0.98}, testament="OT")
        canons = [f["canon"] for a in adj.apparatus for f in a.analysis]
        self.assertNotIn("transcriptional: homoeoteleuton", canons)

    def test_convention_pairs_are_not_harmonisations(self) -> None:
        from studio.brains.textual_analysis import _greek_convention_pair, _is_formula
        self.assertTrue(_greek_convention_pair("ενεκα", "ενεκεν"))
        self.assertTrue(_greek_convention_pair("ειπατε", "ειπετε"))
        self.assertTrue(_greek_convention_pair("εαυτον", "αυτον"))
        self.assertFalse(_greek_convention_pair("ειπεν", "ελεγεν"))
        self.assertTrue(_is_formula(["η", "χαρισ", "του", "κυριου"]))

    def test_claude_review_is_advisory_and_well_formed(self) -> None:
        def answer(payload):
            unit = payload["verses"][0]["units"][0]
            return [{"verse": 1, "unit": unit["unit"], "choice": 1, "confidence": 0.7, "canons": ["lectio brevior"], "rationale": "test"},
                    {"verse": 1, "unit": unit["unit"] + 50, "choice": 9, "confidence": 2, "canons": [], "rationale": "bogus"}]
        fake = _FakeClaude(answer)
        brain = self.brain(offline_locked=False, claude_review=True)
        adj = self.chapter(brain, self.TEXTS, self.WEIGHTS, claude_client=fake)
        req = fake.requests[0]
        self.assertEqual(req["model"], "claude-opus-5-5")
        self.assertEqual(req["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(req["output_config"]["effort"], "high")
        self.assertEqual(req["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(req["fallbacks"], "default")
        self.assertIn("server-side-fallback-2026-07-01", req["betas"])
        self.assertEqual(adj.critical_text, "καὶ εἶπεν αὐτῷ ὁ λαός", "Claude's opinion must not change the text")
        self.assertTrue(adj.needs_review)
        notes = [f["note"] for a in adj.apparatus for f in a.analysis if f["canon"] == "Claude review"]
        self.assertEqual(len(notes), 1, "out-of-range answers are discarded")
        self.assertIn("prefers", notes[0])

    def test_claude_review_respects_offline_lock_and_refusals(self) -> None:
        fake = _FakeClaude([])
        adj = self.chapter(self.brain(offline_locked=True, claude_review=True), self.TEXTS, self.WEIGHTS, claude_client=fake)
        self.assertEqual(fake.requests, [])
        self.assertTrue(any("not run: Strict Offline Lock" in f["note"] for f in adj.analysis))
        refusing = _FakeClaude([], stop_reason="refusal")
        adj = self.chapter(self.brain(offline_locked=False, claude_review=True), self.TEXTS, self.WEIGHTS, claude_client=refusing)
        self.assertTrue(any("declined" in f["note"] for f in adj.analysis))
        self.assertFalse(adj.needs_review)


@unittest.skipUnless(HAVE_CORPORA, "research corpora not present")
@unittest.skipUnless(HAVE_CORPORA, "research corpora not present")
class TestTextualAnalysisOnCorpus(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from studio.engine import CriticalTextEngine
        cls.engine = CriticalTextEngine()
        cls.engine.config.provider_id = "textual_analysis"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.engine.config.provider_id = "offline_philological"

    def findings(self, lang, slug, ch, verse):
        data = self.engine.collate_and_adjudicate(lang, slug, ch)
        v = next(x for x in data["verses"] if x["verse"] == verse)
        return v, [(a["lemma"], f["canon"], f["note"]) for a in v["apparatus"] for f in a.get("analysis", [])]

    def test_harmonisation_to_luke_in_matthew_1_25(self) -> None:
        _v, found = self.findings("greek", "matthew", 1, 25)
        self.assertTrue(any(c == "transcriptional: harmonisation" and "Luke 2:7" in n for _l, c, n in found), found)

    def test_homoeoteleuton_in_1_john_2_23(self) -> None:
        v, found = self.findings("greek", "1-john", 2, 23)
        self.assertTrue(any(c == "transcriptional: homoeoteleuton" for _l, c, _n in found), found)
        self.assertEqual(sum(1 for a in v["apparatus"] if a["kind"] == "word"), 1, "the omitted clause is one unit")

    def test_transposition_is_one_unit_in_matthew_1_18(self) -> None:
        v, _found = self.findings("greek", "matthew", 1, 18)
        self.assertTrue(any(a.get("variant_type") == "word-order transposition" for a in v["apparatus"]))


@unittest.skipUnless(HAVE_CORPORA, "research corpora not present")
class TestRealCorpus(unittest.TestCase):
    def test_source_repairs_reach_collation_and_export(self) -> None:
        result = self.engine.collate_and_adjudicate("greek", "2-kings", 23)
        verse = self.verse(result, 31)
        for sig in ("1st1K-LXX", "Swete (B/A/א)"):
            self.assertTrue(verse["witness_readings"][sig].startswith("… καὶ τρίμηνον"))
            self.assertNotIn("om τους", verse["witness_readings"][sig])
        import json
        exported = json.loads(Path(result["local_json_path"]).read_text(encoding="utf-8"))
        self.assertIn("Source import repair, 23:31", str(exported))
        result = self.engine.collate_and_adjudicate("greek", "psalms", 88)
        for sig in ("1st1K-LXX", "Swete (B/A/א)"):
            self.assertIn("διάψαλμα", self.verse(result, 46)["witness_readings"][sig])
            self.assertNotIn("διάψαλμα", self.verse(result, 48)["witness_readings"][sig])
            self.assertEqual(self.verse(result, 48)["witness_refs"][sig], "88:84")

    def test_coverage_messages_and_available_neighbours(self) -> None:
        for lang, book, ch, explanation in (
            ("hebrew", "sirach", 1, "source-coverage gap"),
            ("hebrew", "psalms", 151, "no chapter 151"),
            ("latin", "psalms", 151, "no chapter 151"),
        ):
            with self.assertRaisesRegex(LookupError, explanation):
                self.engine.build_collation(lang, book, ch)
        for lang, book, ch in (("greek", "psalms", 151), ("greek", "proverbs", 30), ("greek", "proverbs", 31),
                               ("hebrew", "psalms", 150), ("latin", "psalms", 150)):
            self.assertTrue(self.engine.build_collation(lang, book, ch)["collated"])

    def test_new_coverage_is_not_blocked_by_known_gap_explanation(self) -> None:
        from unittest.mock import patch
        with patch("studio.engine.load_book_from_witness", return_value={151: {1: "test source"}}):
            result = self.engine.build_collation("latin", "psalms", 151)
        self.assertEqual(result["collated"][0].verse, 1)

    def test_1_kings_8_does_not_repeat_the_end_of_chapter_7(self) -> None:
        verse = self.verse(self.engine.collate_and_adjudicate("greek", "1-kings", 8), 1)
        self.assertTrue(verse["critical_text"].startswith("Καὶ ἐγένετο"))
        self.assertFalse(any("ὅλον τὸν οἶκον αὐτοῦ" in t for t in verse["witness_readings"].values()))
        previous = self.verse(self.engine.collate_and_adjudicate("greek", "1-kings", 7), 50)
        self.assertIn("ὅλον τὸν οἶκον αὐτοῦ", previous["critical_text"])

    def test_2_kings_14_does_not_borrow_joash_from_previous_chapter(self) -> None:
        verse = self.verse(self.engine.collate_and_adjudicate("greek", "2-kings", 14), 29)
        self.assertNotIn("13:13", verse["witness_refs"].values())
        self.assertFalse(any("Ἰωὰς" in text for text in verse["witness_readings"].values()))
        # Keep the actual disagreement between the two editions visible;
        # the missing OCR verse is not an omission vote against the CSV.
        self.assertIn("Ἀμεσσείου", verse["critical_text"])
        self.assertTrue(any("Ζαχαρίας" in v["reading"]
                            for a in verse["apparatus"] for v in a["variants"]))

    def test_normal_base_word_is_not_a_suffix_echo(self) -> None:
        verse = self.verse(self.engine.collate_and_adjudicate("greek", "genesis", 10), 32)
        self.assertIn("κατὰ τὰ ἔθνη", verse["critical_text"])
        verse = self.verse(self.engine.collate_and_adjudicate("greek", "isaiah", 48), 8)
        self.assertNotIn("μος", verse["critical_text"].split())

    def test_joshua_18_does_not_borrow_zebulun_from_next_chapter(self) -> None:
        verse = self.verse(self.engine.collate_and_adjudicate("greek", "joshua", 18), 28)
        self.assertNotIn("Ζαβουλ", verse["witness_readings"]["Swete-Amicarelli"])
        self.assertNotIn("Ζαβουλ", verse["critical_text"])
        self.assertNotIn("Swete-Amicarelli", verse["witness_refs"])
        self.assertIn("Γαβαωθιαρείμ", verse["critical_text"])
        self.assertIn("πόλεις τρεῖς καὶ δέκα", verse["critical_text"])
        self.assertIn("ἡ κληρονομία υἱῶν Βενιαμεὶν", verse["critical_text"])

    def test_micah_6_7_distinct_words_are_not_spelling_noise(self) -> None:
        result = self.engine.collate_and_adjudicate("greek", "micah", 6)
        verse = self.verse(result, 7)
        self.assertTrue(any(a["lemma"] == "χειμάρρων" and any(v["reading"] == "χιμάρων" for v in a["variants"])
                            for a in verse["apparatus"]))

    def test_matthew_1_18_spelling_stays_in_noise_log(self) -> None:
        result = self.engine.collate_and_adjudicate("greek", "matthew", 1)
        verse = self.verse(result, 18)
        self.assertIn("μνηστευθείσης", verse["critical_text"])
        self.assertIn("μνησστευθισησ", verse["witness_readings"]["א (01)"])
        self.assertFalse(any("μνησστευθισησ" in v["reading"] for a in verse["apparatus"] for v in a["variants"]))
        self.assertTrue(any("μνησστευθισησ" in d["disregarded_forms"] and "double" in d["reason"]
                            for d in verse["disregarded"]))
        self.assertTrue(any(v["reading"] == "γέννησις" for a in verse["apparatus"] for v in a["variants"]))

    def test_numbers_26_different_numbers_stay_in_apparatus(self) -> None:
        result = self.engine.collate_and_adjudicate("greek", "numbers", 26)
        for vnum in (31, 47):
            verse = self.verse(result, vnum)
            self.assertTrue(any("τετρακόσιοι" in v["reading"] for a in verse["apparatus"] for v in a["variants"]), vnum)
            self.assertIn("χ", verse["critical_text"])

    def test_matthew_18_20_numeral_is_not_a_conjunction(self) -> None:
        result = self.engine.collate_and_adjudicate("greek", "matthew", 18)
        verse = self.verse(result, 20)
        self.assertIn("δύο ἢ τρεῖς", verse["critical_text"])
        self.assertFalse(any(d["kept_form"] == "ἢ" and any("γʹ" in f for f in d["disregarded_forms"])
                             for d in verse["disregarded"]))

    @classmethod
    def setUpClass(cls) -> None:
        from studio.engine import CriticalTextEngine
        cls.engine = CriticalTextEngine()

    def verse(self, data, n):
        return next(v for v in data["verses"] if v["verse"] == n)

    def test_greek_ot_genesis_1(self) -> None:
        res = self.engine.collate_and_adjudicate("greek", "genesis", 1)
        self.assertEqual(res["verse_count"], 31)
        self.assertTrue(self.verse(res, 1)["critical_text"].startswith("Ἐν ἀρχῇ"))
        self.assertIn("εἶδεν", self.verse(res, 4)["critical_text"])
        for key in ("local_md_path", "local_json_path", "local_tsv_path"):
            self.assertTrue(Path(res[key]).exists())
            self.assertTrue(res[key].startswith(_SANDBOX))

    def test_greek_nt_matthew_1_real_variants_only(self) -> None:
        res = self.engine.collate_and_adjudicate("greek", "matthew", 1)
        self.assertEqual(res["verse_count"], 25)
        v7 = self.verse(res, 7)
        self.assertIn("Ἀσάφ", v7["critical_text"])
        self.assertTrue(any("Ἀσά" == x["reading"] for a in v7["apparatus"] for x in a["variants"]))
        v6 = self.verse(res, 6)
        self.assertTrue(any("βασιλεὺς" in x["reading"] for a in v6["apparatus"] for x in a["variants"]))
        self.assertEqual(self.verse(res, 1)["apparatus"], [], "contracted Ἰησοῦ Χριστοῦ in B and Sinaiticus is not a variant")
        readings = [x["reading"] for v in res["verses"] for a in v["apparatus"] for x in a["variants"]]
        self.assertTrue(all("(= " in r for r in readings if chr(0x305) in r), "contracted names are shown expanded")
        self.assertFalse([r for r in readings if "|" in r or "$" in r], "MES markup leaked into readings")
        self.assertLess(sum(len(v["apparatus"]) for v in res["verses"]), 60)

    def test_byzantine_witness_is_loaded_for_every_nt_book(self) -> None:
        res = self.engine.collate_and_adjudicate("greek", "matthew", 1)
        self.assertIn("RP2018 (Byz)", self.verse(res, 1)["witness_readings"])

    def test_mark_16_long_ending_is_bracketed(self) -> None:
        res = self.engine.collate_and_adjudicate("greek", "mark", 16)
        v9 = self.verse(res, 9)
        self.assertTrue(v9["critical_text"].startswith("⟦"))
        self.assertIn("B (03)", v9["absent_witnesses"])
        self.assertFalse(self.verse(res, 8)["critical_text"].startswith("⟦"))

    def test_joel_and_nehemiah_versification(self) -> None:
        res = self.engine.collate_and_adjudicate("greek", "joel", 3)
        self.assertEqual(self.verse(res, 1)["witness_refs"].get("Swete (B/A/א)"), "2:28")
        neh = self.engine.collate_and_adjudicate("greek", "nehemiah", 1)
        self.assertIn("Νεεμία", self.verse(neh, 1)["witness_readings"]["Sixtine/Brenton"])

    def test_hebrew_genesis(self) -> None:
        heb = self.engine.collate_and_adjudicate("hebrew", "genesis", 1)
        self.assertEqual(heb["verse_count"], 31)
        self.assertTrue(self.verse(heb, 1)["critical_text"].startswith(nfc("בְּרֵאשִׁ֖ית")))
        # Once conventions (qamats qatan, divine-name pointing, paragraph marks) are normalised, the only
        # differences left between MAM (Aleppo) and WLC (Leningrad) in Genesis 1 are real pointing differences.
        notes = [a["note"] for v in heb["verses"] for a in v["apparatus"]]
        self.assertLessEqual(len(notes), 2, notes)
        self.assertTrue(all("Vocalisation" in n for n in notes), notes)
        gen8 = self.engine.collate_and_adjudicate("hebrew", "genesis", 8)
        self.assertIn(nfc("(הוצא) הַיְצֵ֣א"), self.verse(gen8, 17)["critical_text"])

    def test_latin_genesis(self) -> None:
        lat = self.engine.collate_and_adjudicate("latin", "genesis", 1)
        self.assertEqual(lat["verse_count"], 31)
        self.assertIn("erant", self.verse(lat, 2)["critical_text"])  # Amiatinus' own reading, not Stuttgart's
        self.assertGreaterEqual(lat["variant_verse_count"], 1)
        g50 = self.engine.collate_and_adjudicate("latin", "genesis", 50)
        self.assertNotIn("explicit", self.verse(g50, 26)["critical_text"])
        lam1 = self.engine.collate_and_adjudicate("latin", "lamentations", 1)
        self.assertEqual(self.verse(lam1, 1)["apparatus"], [], "acrostic and prologue formatting inside Clementine/Sixtine is not a variant")
        self.assertLessEqual(lam1["variant_verse_count"], 2, "only real VulgSistina 1590 variants (e.g. Iuda vs Judas in 1:3) appear")

    def test_adopt_variant_is_positional_and_locks(self) -> None:
        res = self.engine.collate_and_adjudicate("greek", "matthew", 1)
        v7 = self.verse(res, 7)
        a_idx = next(i for i, a in enumerate(v7["apparatus"]) if a["lemma"] == "Ἀσάφ")
        v_idx = next(i for i, x in enumerate(v7["apparatus"][a_idx]["variants"]) if x["reading"] == "Ἀσά")
        try:
            saved = self.engine.adopt_variant("greek", "matthew", 1, 7, a_idx, v_idx)
            new = self.verse(saved, 7)
            self.assertTrue(new["human_locked"])
            self.assertIn("Ἀσά,", new["critical_text"])
            self.assertNotIn("Ἀσάφ", new["critical_text"])
            self.assertEqual(new["critical_text"].count("Ἀβιὰ"), v7["critical_text"].count("Ἀβιὰ"))
            again = self.engine.collate_and_adjudicate("greek", "matthew", 1)
            self.assertTrue(self.verse(again, 7)["human_locked"], "re-collation must keep human-locked verses")
        finally:
            self.engine.override_verse("greek", "matthew", 1, 7, v7["critical_text"], v7["rationale"], lock=False)
            self.engine.collate_and_adjudicate("greek", "matthew", 1)

    def test_isaiah_leaves_out_ottleys_codex_a(self) -> None:
        data = self.engine.build_collation("greek", "isaiah", 1)
        sigla = {str(w["siglum"]) for w in data["admitted"]}
        self.assertNotIn("Swete (B/A/א)", sigla)
        self.assertIn("1st1K-LXX", sigla)
        self.assertIn("Swete-Amicarelli", sigla, "the transcription's Isaiah is Swete's own (B), so it votes")
        self.assertTrue(any("Ottley" in n for n in data["versification_notes"]))

    def test_witness_paths_stored_before_the_corpora_moved_still_load(self) -> None:
        from studio.catalog import BOOKS_BY_SLUG
        from studio.parsers import load_book_from_witness, resolve_corpus_path
        old = Path("C:/old place/Saints-Greek-Research-Texts/01_Tier1_Modern_Critical_Open/OT_LXX_Swete_CSV")
        self.assertEqual(resolve_corpus_path(old), GREEK_RESEARCH_ROOT / "01_Tier1_Modern_Critical_Open" / "OT_LXX_Swete_CSV")
        row = {"parser_kind": "swete_csv", "file_path": str(old)}
        self.assertIn(1, load_book_from_witness(row, BOOKS_BY_SLUG["ruth"]))

    def test_swete_transcription_numbering_and_spelling(self) -> None:
        # It reads Swete's text, numbered like Brenton: Wisdom 16 (First1KGreek calls it 17) and Sirach 30–36.
        wis = self.engine.build_collation("greek", "wisdom-of-solomon", 16)
        v1 = next(cv for cv in wis["collated"] if cv.verse == 1)
        self.assertNotIn("Swete-Amicarelli", v1.witness_refs, "same number as Brenton")
        self.assertEqual(v1.witness_refs.get("1st1K-LXX"), "17:1")
        sir = self.engine.build_collation("greek", "sirach", 30)
        self.assertNotIn("Swete-Amicarelli", next(cv for cv in sir["collated"] if cv.verse == 25).witness_refs)
        self.assertEqual(sir["base_siglum"], "Swete-Amicarelli")
        # An OCR line loss in the shared OCR (First1KGreek and Swete Clean print only "... τὴν περὶ αὐτοῦ")
        # no longer reaches the text.
        lev = self.engine.collate_and_adjudicate("greek", "leviticus", 1)
        self.assertIn("καρπώματος", self.verse(lev, 4)["critical_text"])
        # Theodotion's Dan 3: the transcription's Rahlfs-ordered 3:69–70 stand after φῶς καὶ σκότος, as Swete prints them.
        dan = self.engine.build_collation("greek", "daniel", 3)
        self.assertNotIn(69, [cv.verse for cv in dan["collated"]])
        self.assertIn("ψῦχος", next(cv for cv in dan["collated"] if cv.verse == 72).witness_texts["Swete-Amicarelli"])
        # Josh 18:28: the transcription skips half a line; Brenton prints those words in neighbouring units, so it
        # only seems to agree with the skip. The OCR copies' words stay.
        jos = self.engine.collate_and_adjudicate("greek", "joshua", 18)
        self.assertIn("πόλεις τρεῖς καὶ δέκα", self.verse(jos, 28)["critical_text"])

    def test_proverbs_is_numbered_as_saints_bible_numbers_it(self) -> None:
        # 24:1-34, 30:1-33 and 31:1-31, like the site; Swete's 24:24-77 and 29:28-49 are aligned by content.
        res = {ch: self.engine.collate_and_adjudicate("greek", "proverbs", ch)["verses"] for ch in (24, 30, 31)}
        self.assertEqual([len(res[24]), len(res[30]), len(res[31])], [34, 33, 31])
        self.assertTrue(self.verse({"verses": res[30]}, 1)["critical_text"].startswith("Τοὺς ἐμοὺς λόγους"))
        self.assertNotIn("Τοὺς ἐμοὺς λόγους", self.verse({"verses": res[24]}, 22)["critical_text"])
        self.assertEqual(self.verse({"verses": res[31]}, 1)["witness_refs"].get("Swete-Amicarelli"), "24:69")

    def test_rahlfs_check_repairs_reach_the_text(self) -> None:
        # docs/RAHLFS-CHECK-2026-11-17.md: keying slips of the transcription, Rahlfs-patched OCR words and
        # Swete's different verse divisions no longer reach the text.
        text = lambda book, ch, v: self.verse(self.engine.collate_and_adjudicate("greek", book, ch), v)["critical_text"]  # noqa: E731
        self.assertIn("Σαμουὴλ", text("1-samuel", 3, 20))
        self.assertIn("φυλάξεις φυλακὴν θεοῦ σου", text("1-kings", 2, 3))
        self.assertIn("τὸν βασιλέα", text("1-kings", 1, 51))
        prov26, prov27 = text("proverbs", 31, 26), text("proverbs", 31, 27)
        self.assertNotIn("στόμα", prov26, "Brenton's 31:27 is not printed twice")
        self.assertIn("σοφοῖς νομοθέσμως", prov27, "and 31:27 is Swete's wording")
        self.assertTrue(text("judges", 2, 14).rstrip(".").endswith("ἐξεπορεύοντο"))
        self.assertIn("Τί ὄψεσθε", text("song-of-songs", 7, 1))
        self.assertNotIn("Κύριος", text("sirach", 1, 8))
        self.assertNotIn("λέγων", text("numbers", 17, 1))
        dan = self.engine.collate_and_adjudicate("greek", "daniel", 3)
        self.assertIn("θάλασσαι", self.verse(dan, 77)["critical_text"])
        self.assertIn("πηγαί", self.verse(dan, 78)["critical_text"])
        self.assertIn("Ἰεροσολύμων", text("2-maccabees", 11, 5), "two digitisations of Swete agree on the breathing")
        self.assertIn("Ἰσραὴλ ἀγγέλους", text("judges", 11, 19))
        self.assertTrue(text("lamentations", 1, 1).startswith("Καὶ ἐγένετο"), "the whole prologue or none")

    def test_first1k_reads_swetes_sirach_and_joins_line_breaks(self) -> None:
        from studio.catalog import BOOKS_BY_SLUG
        from studio.parsers import _parse_first1k_tei, _swete_tei_file
        tlg = GREEK_RESEARCH_ROOT / "01_Tier1_Modern_Critical_Open" / "OT_LXX_First1KGreek_tlg0527" / "data" / "tlg0527"
        sirach = BOOKS_BY_SLUG["sirach"]
        self.assertIn("Swete", (_swete_tei_file(tlg / sirach.tlg_work).read_text(encoding="utf-8"))[:30000])
        gen = _parse_first1k_tei(tlg, BOOKS_BY_SLUG["genesis"])
        self.assertIn("κληρονομήσω", gen[15][8])

    def test_versification_duplicates_and_fillers(self) -> None:
        sir = self.engine.build_collation("greek", "sirach", 30)
        v25 = next(cv for cv in sir["collated"] if cv.verse == 25)
        self.assertEqual(v25.witness_refs.get("1st1K-LXX"), "33:25", "Sirach 30–36 order differs in Swete")
        ps = self.engine.build_collation("greek", "psalms", 14)
        self.assertNotIn(7, [cv.verse for cv in ps["collated"]], "Swete Clean's stray psalm title is not a verse")
        sam = self.engine.build_collation("hebrew", "1-samuel", 23)
        self.assertNotIn(29, [cv.verse for cv in sam["collated"]])
        self.assertTrue(any("24:1" in n for n in sam["versification_notes"]))
        gen = self.engine.build_collation("latin", "genesis", 5)
        self.assertNotIn(32, [cv.verse for cv in gen["collated"]], "the Saints filler copy of 5:31 is not a verse")

    def test_silent_editions_count_as_lacking_matthew_17_21(self) -> None:
        res = self.engine.collate_and_adjudicate("greek", "matthew", 17)
        v21 = self.verse(res, 21)
        self.assertTrue(v21["critical_text"].startswith("⟦"))
        self.assertIn("SBLGNT", v21["absent_witnesses"])

    def test_invalid_chapter_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.collate_and_adjudicate("greek", "jude", 2)

    def test_saints_branding_and_library_home(self) -> None:
        import json
        res = self.engine.collate_and_adjudicate("greek", "ruth", 1)
        md_path = Path(res["local_md_path"])
        js_path = Path(res["local_json_path"])
        self.assertIn("Saints-Greek-Critical-Text", str(md_path))
        md_text = md_path.read_text(encoding="utf-8")
        self.assertIn("Saints Greek Critical Text", md_text)
        self.assertNotIn("Gemini Greek Critical Text", md_text)
        js_obj = json.loads(js_path.read_text(encoding="utf-8"))
        self.assertEqual(js_obj["edition"], "Saints Greek Critical Text")
        home = self.engine.get_edition_home_summary("greek")
        self.assertEqual(home["edition_title"], "Saints Greek Critical Text")
        self.assertGreaterEqual(home["saved_chapter_count"], 1)

    def test_hebrew_special_letters_deuteronomy_6_4_and_leviticus_11_42(self) -> None:
        deu6 = self.engine.collate_and_adjudicate("hebrew", "deuteronomy", 6)
        v4 = self.verse(deu6, 4)
        self.assertNotIn("'", v4["witness_readings"]["WLC (L)"])
        self.assertIn(nfc("שְׁמַ֖ע"), v4["witness_readings"]["WLC (L)"])
        self.assertEqual(v4["apparatus"], [])
        lev11 = self.engine.collate_and_adjudicate("hebrew", "leviticus", 11)
        v42 = self.verse(lev11, 42)
        self.assertNotIn("'", v42["witness_readings"]["WLC (L)"])
        self.assertEqual(v42["apparatus"], [])

    def test_latin_restored_verses_and_editorial_cleanup(self) -> None:
        jhn6 = self.engine.collate_and_adjudicate("latin", "john", 6)
        v51 = self.verse(jhn6, 51)
        self.assertIn("Ego sum panis vivus", v51["critical_text"])
        self.assertIn("Si quis manducaverit", v51["critical_text"])

        mat11 = self.engine.collate_and_adjudicate("latin", "matthew", 11)
        self.assertIn("Joannes autem", self.verse(mat11, 2)["critical_text"])
        self.assertIn("Tu es, qui venturus es", self.verse(mat11, 3)["critical_text"])

        num6 = self.engine.collate_and_adjudicate("latin", "numbers", 6)
        v23 = self.verse(num6, 23)["critical_text"]
        self.assertTrue(v23.startswith("Loquere Aaron"), v23)
        self.assertIn("Invocabuntque nomen meum", v23)

        exo36 = self.engine.collate_and_adjudicate("latin", "exodus", 36)
        v10 = self.verse(exo36, 10)
        self.assertIn("Clem1598-USFX", v10["witness_readings"])
        self.assertEqual(v10["witness_refs"].get("Clem1598-USFX"), "39:3")

        sng1 = self.engine.collate_and_adjudicate("latin", "song-of-songs", 1)
        self.assertTrue(self.verse(sng1, 2)["critical_text"].startswith("Osculetur me"))

        jol4_col = self.engine.build_collation("latin", "joel", 4)
        self.assertEqual(jol4_col["base_siglum"], "Clem1598-USFX")
        jol4 = self.engine.collate_and_adjudicate("latin", "joel", 4)
        self.assertFalse(self.verse(jol4, 21)["critical_text"].endswith("]"))

        gen25 = self.engine.collate_and_adjudicate("latin", "genesis", 25)
        self.assertIn("filii Dodan fuerunt", self.verse(gen25, 3)["critical_text"])
        gen44 = self.engine.collate_and_adjudicate("latin", "genesis", 44)
        self.assertIn("(necdum enim de loco abierant)", self.verse(gen44, 14)["critical_text"])

    def test_trilingual_majority_witnesses_loaded_and_collated(self) -> None:
        # 1. Greek NT: Robinson-Pierpont, Boyd TCGNT, Antoniades 1904, KJTR, Scrivener 1894, Boyd TR
        jhn1 = self.engine.collate_and_adjudicate("greek", "john", 1)
        w_jhn1 = self.verse(jhn1, 1)["witness_readings"]
        for sig in ("RP2018 (Byz)", "TCGNT (Byz)", "PT1904 (Byz)", "TR (KJTR)", "TR-Scrivener (1894)", "TR-Boyd (Elz/Scr/Steph)"):
            self.assertIn(sig, w_jhn1)

        # 2. Greek OT: Orthodox Ecclesiastical Septuagint alongside Swete & Sixtine/Brenton
        gen1 = self.engine.collate_and_adjudicate("greek", "genesis", 1)
        self.assertIn("LXX-Orthodox (Οʹ)", self.verse(gen1, 1)["witness_readings"])

        # 3. Hebrew OT: Ben Chayyim (1525) & Letteris (1852) alongside MAM & WLC (Deut 23:2 דכא vs דכה)
        deu23 = self.engine.collate_and_adjudicate("hebrew", "deuteronomy", 23)
        v2 = self.verse(deu23, 2)
        self.assertIn("BenChayyim (1525)", v2["witness_readings"])
        self.assertIn("Letteris (1852)", v2["witness_readings"])
        self.assertTrue(v2["witness_readings"]["BenChayyim (1525)"].split()[1].endswith("א"))
        self.assertTrue(v2["disregarded"] or v2["apparatus"])

        # 4. Latin OT/NT: Hetzenauer (1906), Conte (2009), Sixtine (1590), plus Stuttgart quarantined
        lat_gen1 = self.engine.collate_and_adjudicate("latin", "genesis", 1)
        v2_lat = self.verse(lat_gen1, 2)
        for sig in ("VulgHetzenauer (1906)", "VulgConte (2009)", "VulgSistina (1590)"):
            self.assertIn(sig, v2_lat["witness_readings"])
        self.assertNotIn("Stuttgart-BSV [QUARANTINED]", v2_lat["witness_readings"])
        self.assertTrue(any("Domini" in x["reading"] for a in v2_lat["apparatus"] for x in a["variants"]))

    def test_majority_editions_are_apparatus_witnesses_that_never_vote(self) -> None:
        from studio.catalog import APPARATUS_ONLY
        self.assertIn("grk-nt-tcgnt", APPARATUS_ONLY)
        # Matt 6:13: the doxology stays out of the text and is recorded with all six Byzantine/TR editions.
        m6 = self.verse(self.engine.collate_and_adjudicate("greek", "matthew", 6), 13)
        self.assertNotIn("δύναμις", m6["critical_text"])
        doxology = [v for a in m6["apparatus"] for v in a["variants"] if "δύναμις" in v["reading"]]
        self.assertTrue(doxology and {"TCGNT (Byz)", "PT1904 (Byz)", "RP2018 (Byz)"} <= set(doxology[0]["witnesses"]))
        self.assertIn("TCGNT (Byz)", m6["witness_readings"])
        self.assertIn("TCGNT (Byz)", m6["apparatus_witnesses"])
        # John 1:18 keeps μονογενὴς θεός; the Byzantine/TR υἱός is in the apparatus.
        j1 = self.verse(self.engine.collate_and_adjudicate("greek", "john", 1), 18)
        self.assertIn("θεὸς", j1["critical_text"])
        # 1 Sam 17:12-31 (lacking in B, printed by the Orthodox LXX only) are not printed.
        s17 = self.engine.collate_and_adjudicate("greek", "1-samuel", 17)
        self.assertNotIn(12, [v["verse"] for v in s17["verses"]])
        # MAM's pointing stays (qamats qatan in כׇּל), and Letteris's consonantal variant is recorded.
        g1 = self.verse(self.engine.collate_and_adjudicate("hebrew", "genesis", 1), 21)
        self.assertIn("כׇּל", g1["critical_text"])
        d23 = self.verse(self.engine.collate_and_adjudicate("hebrew", "deuteronomy", 23), 2)
        unit = next(a for a in d23["apparatus"] if any("Letteris (1852)" in v["witnesses"] for v in a["variants"]))
        self.assertIn("BenChayyim (1525)", unit["lemma_witnesses"])
        # The Hetzenauer/Conte files lack Lamentations' prologue: not recorded as their omission.
        lam1 = self.verse(self.engine.collate_and_adjudicate("latin", "lamentations", 1), 1)
        self.assertFalse(any("VulgHetzenauer (1906)" in v["witnesses"] for a in lam1["apparatus"] for v in a["variants"]))

    def test_orthodox_septuagint_file_cleanup(self) -> None:
        from studio.catalog import BOOKS_BY_SLUG, WITNESS_BOOK_EXCLUSIONS
        from studio.parsers import load_book_from_witness
        self.assertIn(("grk-lxx-orthodox", "2-maccabees"), WITNESS_BOOK_EXCLUSIONS, "its 2MA file is 4 Maccabees")
        w = next(w for w in self.engine.list_witnesses("greek") if w["id"] == "grk-lxx-orthodox")
        deu = load_book_from_witness(w, BOOKS_BY_SLUG["deuteronomy"])
        self.assertTrue(deu[2][10].startswith("οἱ Ὀμμὶν"), "verse 10, run on inside 9 as '(10 …', is split out")
        self.assertNotIn("(10", deu[2][9])
        self.assertNotIn("Κεφ.", load_book_from_witness(w, BOOKS_BY_SLUG["exodus"])[36][8])
        self.assertNotRegex(load_book_from_witness(w, BOOKS_BY_SLUG["1-kings"])[2][35], r"\d")

    def test_greek_zephaniah_3_psalms_phantoms_and_orthographic_repairs(self) -> None:
        zep3 = self.engine.collate_and_adjudicate("greek", "zephaniah", 3)
        self.assertIn("ἐπιφανὴς", self.verse(zep3, 1)["critical_text"])
        self.assertNotIn("ἐπιφανὴς", self.verse(zep3, 2)["critical_text"])

        ps137 = self.engine.build_collation("greek", "psalms", 137)
        self.assertNotIn(9, [cv.verse for cv in ps137["collated"]])
        ps112 = self.engine.build_collation("greek", "psalms", 112)
        self.assertNotIn(10, [cv.verse for cv in ps112["collated"]])

        jos6 = self.engine.collate_and_adjudicate("greek", "joshua", 6)
        self.assertNotIn("ἐστὶν ἐστὶν", self.verse(jos6, 17)["critical_text"])

        sam14 = self.engine.collate_and_adjudicate("greek", "1-samuel", 14)
        self.assertIn("ἐπάταξεν τὸν Ἀμαλήκ", self.verse(sam14, 48)["critical_text"])

        kgs9 = self.engine.collate_and_adjudicate("greek", "2-kings", 9)
        self.assertNotIn("ἐκει ", self.verse(kgs9, 2)["critical_text"])

        mac16 = self.engine.collate_and_adjudicate("greek", "1-maccabees", 16)
        self.assertIn("εἰς τὴν Ἰουδαίαν", self.verse(mac16, 10)["critical_text"])

        mrk7 = self.engine.collate_and_adjudicate("greek", "mark", 7)
        self.assertIn("Τύρου καὶ Σιδῶνος.", self.verse(mrk7, 24)["critical_text"])
        mrk8 = self.engine.collate_and_adjudicate("greek", "mark", 8)
        self.assertIn("Πῶς οὔπω συνίετε;", self.verse(mrk8, 21)["critical_text"])
        luk24 = self.engine.collate_and_adjudicate("greek", "luke", 24)
        self.assertEqual(self.verse(luk24, 3)["critical_text"], "εἰσελθοῦσαι δὲ οὐχ εὗρον τὸ σῶμα τοῦ Κυρίου Ἰησοῦ.")
        self.assertIn("τὰς γραφάς, καὶ εἶπεν", self.verse(luk24, 45)["critical_text"])
        luk2 = self.engine.collate_and_adjudicate("greek", "luke", 2)
        self.assertIn("(αὕτη", self.verse(luk2, 36)["critical_text"])
        self.assertIn("τεσσάρων,)", self.verse(luk2, 37)["critical_text"])


class TestOpenAIReview(unittest.TestCase):
    """No real API calls; transport and output validation are exercised separately."""

    def setUp(self):
        from unittest.mock import patch
        # A mistakenly unmocked network call must fail, even if the host has credentials.
        self.network = patch("urllib.request.build_opener", side_effect=AssertionError("unexpected network"))
        self.network.start()
        self.addCleanup(self.network.stop)

    @staticmethod
    def response(units, **extra):
        import json
        return dict({"status": "completed", "id": "test-response", "model": "test-model",
                     "output": [{"type": "reasoning"}, {"type": "message", "content": [
                         {"type": "output_text", "text": json.dumps({"units": units})}]}]}, **extra)

    @staticmethod
    def answer(payload, choice=0):
        return [{"verse": v["verse"], "unit": u["unit"], "choice": choice,
                 "confidence": 0.7 if choice is not None else None,
                 "supporting_witnesses": u["readings"][choice]["witnesses"][:1] if choice is not None else [],
                 "canons": ["supplied external evidence"], "rationale": "Test rationale.",
                 "limitations": "Only the supplied transcriptions were inspected."}
                for v in payload["verses"] for u in v["units"]]

    def run_brain(self, transport, locked=False, verses=None):
        from studio.brains.openai_review import OpenAIReviewBrain
        from studio.brains.textual_analysis import TextualAnalysisBrain
        if verses is None:
            verses = [align_witnesses_for_verse(1, TestTextualAnalysisBrain.TEXTS,
                                               TestTextualAnalysisBrain.WEIGHTS, "greek")]
        for cv in verses:
            cv.testament = "NT"
            cv.witness_families = {s: s for s in cv.witness_texts}
        baseline = TextualAnalysisBrain()
        baseline.set_context(testament="NT")
        before = baseline.adjudicate_chapter("greek", "Test", 1, verses)
        brain = OpenAIReviewBrain(BrainConfig(offline_locked=locked))
        brain.set_context(testament="NT", openai_transport=transport)
        after = brain.adjudicate_chapter("greek", "Test", 1, verses)
        for b, a in zip(before, after):
            self.assertEqual((a.critical_text, a.confidence, a.decision_source, a.baseline_text),
                             (b.critical_text, b.confidence, b.decision_source, b.baseline_text))
            self.assertEqual([(u.lemma, u.word_index, u.word_count, u.variants) for u in a.apparatus],
                             [(u.lemma, u.word_index, u.word_count, u.variants) for u in b.apparatus])
        return after

    @staticmethod
    def reviews(adj):
        return [f for u in adj.apparatus for f in u.analysis if f["canon"] == "OpenAI review"]

    def test_agreement_disagreement_and_abstention_never_change_text(self):
        for choice, status in ((0, "agreed"), (1, "disagreed"), (None, "abstained")):
            with self.subTest(choice=choice):
                adj = self.run_brain(lambda cfg, p: self.response(self.answer(p, choice)))[0]
                review = self.reviews(adj)[0]
                self.assertEqual(review["status"], status)
                self.assertEqual(adj.needs_review, choice != 0)
                self.assertEqual(review["response_id"], "test-response")
                self.assertEqual(len(review["input_sha256"]), 64)
                self.assertIn("advisory only", adj.rationale)

    def test_lock_prevents_transport_and_is_visible_on_every_verse(self):
        from unittest.mock import Mock
        from studio.brains.openai_review import _request_review
        transport = Mock(side_effect=AssertionError("must not call"))
        verses = [align_witnesses_for_verse(v, TestTextualAnalysisBrain.TEXTS,
                                          TestTextualAnalysisBrain.WEIGHTS, "greek") for v in (1, 2)]
        for adj in self.run_brain(transport, locked=True, verses=verses):
            self.assertIn("Strict Offline Lock", adj.rationale)
            self.assertTrue(adj.needs_review)
        transport.assert_not_called()
        with self.assertRaises(PermissionError):
            _request_review(BrainConfig(offline_locked=True), {})

    def test_missing_credentials_are_visible_without_network(self):
        from unittest.mock import patch
        from studio.brains.openai_review import _request_review
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            adj = self.run_brain(_request_review)[0]
        self.assertIn("no OpenAI API key", adj.rationale)
        self.assertEqual(self.reviews(adj)[0]["status"], "not_reviewed")

    def test_invalid_choices_support_and_confidence_are_rejected(self):
        bad = [("choice", True), ("choice", 0.5), ("choice", "0"), ("choice", -1), ("choice", 999),
               ("supporting_witnesses", ["invented manuscript"]), ("supporting_witnesses", []),
               ("supporting_witnesses", ["C"]), ("confidence", float("nan")),
               ("confidence", float("inf")), ("confidence", True), ("confidence", 1.1),
               ("confidence", "0.7"), ("verse", True), ("unit", 0.0), ("rationale", ""),
               ("limitations", ""), ("canons", "not a list")]
        for field, value in bad:
            with self.subTest(field=field, value=value):
                def transport(cfg, p):
                    answers = self.answer(p)
                    answers[0][field] = value
                    return self.response(answers)
                adj = self.run_brain(transport)[0]
                self.assertIn("rejected", adj.rationale)
                self.assertEqual(self.reviews(adj)[0]["status"], "not_reviewed")

    def test_missing_duplicate_and_foreign_answers_are_visible(self):
        for mode in ("missing", "duplicate", "foreign"):
            def transport(cfg, p):
                answers = self.answer(p)
                if mode == "missing":
                    answers = []
                elif mode == "duplicate":
                    answers += answers
                else:
                    answers[0]["verse"] = 999
                return self.response(answers)
            with self.subTest(mode=mode):
                adj = self.run_brain(transport)[0]
                self.assertEqual(self.reviews(adj)[0]["status"], "not_reviewed")
                self.assertTrue(adj.needs_review)

    def test_refusal_incomplete_and_malformed_output_are_visible(self):
        responses = [self.response([], status="incomplete"), self.response([], status="failed"),
                     self.response([], output=[{"type": "message", "content": [{"type": "refusal"}]}]),
                     self.response([], output=[{"type": "message", "content": [{"type": "output_text", "text": "not JSON"}]}]),
                     self.response([], output=[None])]
        for response in responses:
            with self.subTest(response=response):
                adj = self.run_brain(lambda cfg, p: response)[0]
                self.assertEqual(self.reviews(adj)[0]["status"], "not_reviewed")

    def test_whole_verse_presence_and_uncontested_text_are_not_sent(self):
        from unittest.mock import Mock
        cv = align_witnesses_for_verse(1, {"A": "καὶ εἶπεν ὁ λαός"}, {"A": 0.5, "B": 1, "C": 1}, "greek")
        cv.absent_witnesses = ["B", "C"]
        transport = Mock(side_effect=AssertionError("must not call"))
        adj = self.run_brain(transport, verses=[cv])[0]
        self.assertTrue(any(a.kind == "verse" for a in adj.apparatus))
        self.assertIn("Whole-verse", adj.rationale)
        plain = align_witnesses_for_verse(1, {"A": "καὶ εἶπεν", "B": "καὶ εἶπεν"}, {"A": 1, "B": 1}, "greek")
        self.run_brain(transport, verses=[plain])
        transport.assert_not_called()

    def test_large_verse_is_split_and_answers_are_scoped_to_each_batch(self):
        from studio.brains.openai_review import _batches, _validate_answers, OpenAIReviewUnavailable, MAX_UNITS_PER_REQUEST
        units = [{"unit": i, "readings": [{"text": "a", "witnesses": ["A"]}]} for i in range(43)]
        batches = list(_batches([{"verse": 1, "units": units}]))
        self.assertTrue(all(sum(len(v["units"]) for v in b) <= MAX_UNITS_PER_REQUEST for b in batches))
        self.assertEqual([u["unit"] for b in batches for v in b for u in v["units"]], list(range(43)))
        answer = self.answer({"verses": batches[0]})[0]
        offered = {(v["verse"], u["unit"]): u for v in batches[1] for u in v["units"]}
        with self.assertRaises(OpenAIReviewUnavailable):
            _validate_answers({"units": [answer]}, offered)

    def test_later_batch_failure_preserves_earlier_reviews(self):
        from unittest.mock import patch
        from studio.brains.openai_review import OpenAIReviewUnavailable
        calls = []
        def transport(cfg, p):
            calls.append(p)
            if len(calls) == 2:
                raise OpenAIReviewUnavailable("network failure")
            return self.response(self.answer(p))
        verses = [align_witnesses_for_verse(v, TestTextualAnalysisBrain.TEXTS,
                                          TestTextualAnalysisBrain.WEIGHTS, "greek") for v in (1, 2)]
        with patch("studio.brains.openai_review.MAX_UNITS_PER_REQUEST", 1):
            first, second = self.run_brain(transport, verses=verses)
        self.assertEqual(self.reviews(first)[0]["status"], "agreed")
        self.assertEqual(self.reviews(second)[0]["status"], "not_reviewed")

    def test_transport_uses_structured_responses_and_does_not_log_secrets(self):
        import json
        import urllib.error
        from unittest.mock import Mock, patch
        from studio.brains.openai_review import _request_review, OpenAIReviewUnavailable, ENDPOINT, _NoRedirect
        config = BrainConfig(offline_locked=False, openai_api_key="test-secret")
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps(self.response([])).encode()
        opener = Mock()
        opener.open.return_value = response
        with patch("urllib.request.build_opener", return_value=opener):
            _request_review(config, {"verses": []})
            request = opener.open.call_args.args[0]
            body = json.loads(request.data)
            self.assertEqual(request.full_url, ENDPOINT)
            self.assertEqual(request.get_header("Authorization"), "Bearer test-secret")
            self.assertFalse(body["store"])
            self.assertTrue(body["text"]["format"]["strict"])
            self.assertEqual(body["reasoning"]["effort"], "high")
            self.assertNotIn("test-secret", str(body))
            for code in (401, 403, 404, 429, 500, 302):
                opener.open.side_effect = urllib.error.HTTPError(ENDPOINT, code, "test-secret", {}, None)
                with self.assertRaises(OpenAIReviewUnavailable) as caught:
                    _request_review(config, {})
                self.assertNotIn("test-secret", str(caught.exception))
        self.assertIsNone(_NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.com"))

    def test_http_errors_distinguish_credits_limits_and_rate(self):
        import io
        import json
        import urllib.error
        from studio.brains.openai_review import _http_failure, ENDPOINT
        for code, error_type, expected in (
            ("credit_balance_exhausted", "insufficient_quota", "API credits exhausted"),
            ("organization_usage_limit_exceeded", "insufficient_quota", "organization usage limit"),
            ("organization_spend_limit_exceeded", "insufficient_quota", "organization hard spend limit"),
            ("project_spend_limit_exceeded", "insufficient_quota", "project hard spend limit"),
            ("insufficient_quota", "insufficient_quota", "billing or quota unavailable"),
            ("rate_limit_exceeded", "rate_limit_error", "request or token rate limit"),
            ("slow_down", "rate_limit_error", "increased too quickly"),
        ):
            with self.subTest(code=code):
                stream = io.BytesIO(json.dumps({"error": {"code": code, "type": error_type,
                    "message": "private-key and account details", "param": "private-key"}}).encode())
                failure = _http_failure(urllib.error.HTTPError(ENDPOINT, 429, "private-key", {}, stream))
                self.assertEqual(failure.error_code, code)
                self.assertEqual(failure.http_status, 429)
                self.assertTrue(failure.halt_review)
                self.assertTrue(stream.closed)
                self.assertIn(expected, str(failure))
                self.assertNotIn("private-key", str(failure))

    def test_unrecognized_http_body_never_leaks_server_content(self):
        import io
        import urllib.error
        from studio.brains.openai_review import _http_failure, ENDPOINT
        for raw in (b'private-key is not JSON', b'[]', b'{"error":"private-key"}',
                    b'{"error":{"code":["private-key"],"message":"private-key"}}',
                    b'{"error":{"code":"private-key","message":"private-key"}}', b''):
            failure = _http_failure(urllib.error.HTTPError(ENDPOINT, 429, "private-key", {}, io.BytesIO(raw)))
            self.assertIn("no recognized error code", str(failure))
            self.assertEqual(failure.error_code, "")
            self.assertNotIn("private-key", str(failure))
        failure = _http_failure(urllib.error.HTTPError(ENDPOINT, 429, "", {}, io.BytesIO(
            b'{"error":{"code":null,"type":"insufficient_quota","message":"private-key"}}')))
        self.assertEqual(failure.error_code, "insufficient_quota")

    def test_billing_failure_stops_later_batches_but_keeps_prior_reviews(self):
        import io
        import urllib.error
        from unittest.mock import patch
        from studio.brains.openai_review import _http_failure, ENDPOINT
        calls = []
        def transport(cfg, payload):
            calls.append(payload)
            if len(calls) == 2:
                raise _http_failure(urllib.error.HTTPError(ENDPOINT, 429, "", {}, io.BytesIO(
                    b'{"error":{"code":"credit_balance_exhausted","type":"insufficient_quota"}}')))
            return self.response(self.answer(payload))
        verses = [align_witnesses_for_verse(v, TestTextualAnalysisBrain.TEXTS,
                                          TestTextualAnalysisBrain.WEIGHTS, "greek") for v in (1, 2, 3)]
        with patch("studio.brains.openai_review.MAX_UNITS_PER_REQUEST", 1):
            first, failed, skipped = self.run_brain(transport, verses=verses)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.reviews(first)[0]["status"], "agreed")
        for adj, sent in ((failed, True), (skipped, False)):
            review = self.reviews(adj)[0]
            self.assertEqual(review["status"], "not_reviewed")
            self.assertEqual(review["error_code"], "credit_balance_exhausted")
            self.assertEqual(review["http_status"], 429)
            self.assertEqual(review["request_sent"], sent)
            self.assertTrue(adj.needs_review)
            self.assertIn("API credits exhausted", adj.rationale)
        self.assertIn("batch not sent", self.reviews(skipped)[0]["note"])

    def test_settings_roundtrip_and_registry(self):
        import json
        from unittest.mock import patch
        from studio.brains import create_brain
        from studio.brains.openai_review import OpenAIReviewBrain
        from studio.engine import CriticalTextEngine
        with tempfile.TemporaryDirectory(dir=_SANDBOX) as folder:
            settings, secrets = Path(folder) / "settings.json", Path(folder) / "secrets.json"
            with patch("studio.engine.SETTINGS_PATH", settings), patch("studio.engine.SECRETS_PATH", secrets):
                engine = CriticalTextEngine()
                config = BrainConfig(provider_id="openai_review", openai_model="test-model", openai_effort="medium",
                                     openai_api_key="test-secret", gemini_api_key="gem-test", anthropic_api_key="ant-test")
                engine.save_settings(config)
                self.assertEqual(engine.load_settings(), config)
                self.assertNotIn("test-secret", settings.read_text())
                self.assertEqual(json.loads(secrets.read_text())["anthropic_api_key"], "ant-test")
                self.assertIsInstance(create_brain(config), OpenAIReviewBrain)
                settings.write_text('{"provider_id": "textual_analysis"}')
                self.assertEqual(engine.load_settings().openai_model, BrainConfig().openai_model)

    def test_gatekeeper_never_admits_quarantined_witness(self):
        from studio.brains.openai_review import OpenAIReviewBrain
        verdict = OpenAIReviewBrain().evaluate_witness("greek", "Restricted witness", "CC BY-NC-ND",
                                                      "ἐν ἀρχῇ ἦν ὁ λόγος", {}, {})
        self.assertEqual(verdict.decision, "QUARANTINED_NC")
        self.assertIn("offline", verdict.reasons[-1])

    @unittest.skipUnless(HAVE_CORPORA, "research corpora not present")
    def test_reviews_persist_in_exports_and_human_locks_survive(self):
        import json
        from unittest.mock import patch
        from studio.engine import CriticalTextEngine
        engine = CriticalTextEngine()
        engine.config = BrainConfig(provider_id="textual_analysis")
        baseline = engine.collate_and_adjudicate("latin", "genesis", 1, preserve_human_locks=False)
        engine.config = BrainConfig(provider_id="openai_review", offline_locked=False)
        def transport(cfg, payload):
            return self.response(self.answer(payload, 1))
        with patch("studio.brains.openai_review._request_review", side_effect=transport):
            reviewed = engine.collate_and_adjudicate("latin", "genesis", 1)
            self.assertEqual([v["critical_text"] for v in baseline["verses"]],
                             [v["critical_text"] for v in reviewed["verses"]])
            self.assertIn("OpenAI review", Path(reviewed["local_md_path"]).read_text(encoding="utf-8"))
            exported = json.loads(Path(reviewed["local_json_path"]).read_text(encoding="utf-8"))
            self.assertTrue(any(f.get("response_id") == "test-response"
                                for v in exported["verses"] for a in v["apparatus"] for f in a["analysis"]))
            engine.override_verse("latin", "genesis", 1, 9, "Human chosen wording", "Keep this decision.")
            again = engine.collate_and_adjudicate("latin", "genesis", 1)
            locked = next(v for v in again["verses"] if v["verse"] == 9)
            self.assertEqual(locked["critical_text"], "Human chosen wording")
            self.assertTrue(locked["human_locked"])
            self.assertFalse(locked["needs_review"])
        # Leave the shared sandbox chapter in its baseline state for unrelated tests.
        engine.config = BrainConfig()
        engine.collate_and_adjudicate("latin", "genesis", 1, preserve_human_locks=False)


if __name__ == "__main__":
    unittest.main()
