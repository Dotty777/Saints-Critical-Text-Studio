"""Isolated Stage 1 regression tests for Greek NT/OT collation & adjudication,
Greek alphabetic numeral concordance tagging, Hebrew DSS cross-chapter guard,
and Latin i/j orthography normalization.

Sets CTS_DATA_DIR and CTS_OUTPUT_ROOT to a temporary sandbox BEFORE importing studio
so live data/studio.db is never touched (AGENTS.md Invariant #1).
"""

import os
import tempfile
import unittest
from pathlib import Path

if "CTS_DATA_DIR" not in os.environ:
    _SANDBOX_ROOT = Path(tempfile.mkdtemp(prefix="cts_stage1_grk_"))
    os.environ["CTS_DATA_DIR"] = str(_SANDBOX_ROOT / "data")
    os.environ["CTS_OUTPUT_ROOT"] = str(_SANDBOX_ROOT / "out")

from studio import catalog, db  # noqa: E402
from studio.brains.offline_philological import _latin_u_to_v, _strip_quotes  # noqa: E402
from studio.collator import align_versification  # noqa: E402
from studio.engine import CriticalTextEngine  # noqa: E402
from studio.lexica import greek as glx  # noqa: E402

_LIVE_DATA_DIR = (catalog.STUDIO_ROOT / "data").resolve()
assert _LIVE_DATA_DIR not in db.DB_PATH.resolve().parents, f"Sandbox isolation violated: {db.DB_PATH}"
assert db.DB_PATH.resolve().is_relative_to(Path(os.environ["CTS_DATA_DIR"]).resolve()), (
    f"Sandbox isolation violated: {db.DB_PATH} not under {os.environ['CTS_DATA_DIR']}"
)

_ENGINE = CriticalTextEngine()
_CHAPTER_CACHE: dict = {}


def _chapter_map(lang: str, slug: str, ch: int) -> dict:
    key = (lang, slug, ch)
    if key not in _CHAPTER_CACHE:
        res = _ENGINE.collate_and_adjudicate(lang, slug, ch)
        _CHAPTER_CACHE[key] = {v["verse"]: v for v in res["verses"]}
    return _CHAPTER_CACHE[key]


def _ct(lang: str, slug: str, ch: int, verse: int) -> str:
    return _chapter_map(lang, slug, ch)[verse]["critical_text"]


class TestStage1GreekNT(unittest.TestCase):
    def test_raised_dot_punctuation_splice_fixed(self) -> None:
        self.assertIn("πνεύματος Θεοῦ· ὥστε", _ct("greek", "romans", 15, 19))
        self.assertNotIn("πνεύματος· Θεοῦ", _ct("greek", "romans", 15, 19))

        self.assertIn("ἄλλα πέντε τάλαντα·", _ct("greek", "matthew", 25, 16))
        self.assertNotIn("πέντε· τάλαντα", _ct("greek", "matthew", 25, 16))

        self.assertIn("κυρίου ἐστίν ἐντολή·", _ct("greek", "1-corinthians", 14, 37))
        self.assertNotIn("ἐστίν· ἐντολή", _ct("greek", "1-corinthians", 14, 37))

        self.assertIn("αἰῶνας τῶν αἰώνων· ἀμήν.", _ct("greek", "hebrews", 13, 21))
        self.assertNotIn("αἰῶνας· τῶν", _ct("greek", "hebrews", 13, 21))

        self.assertIn("θυρωρός τῷ Πέτρῳ· Μὴ", _ct("greek", "john", 18, 17))
        self.assertNotIn("θυρωρός· τῷ", _ct("greek", "john", 18, 17))

        # Speech-introducing raised dots must remain untouched.
        self.assertIn("Ἰησοῦς· Τοσοῦτον", _ct("greek", "john", 14, 9))
        self.assertIn("αὐτῇ· Θύγατερ,", _ct("greek", "luke", 8, 48))
        self.assertIn("αὐτῷ· Κύριε,", _ct("greek", "matthew", 18, 21))
        self.assertIn("λέγων· Ἐλωί,", _ct("greek", "matthew", 27, 46))
        self.assertIn("αὐτοῖς· Πῶς", _ct("greek", "mark", 8, 21))

    def test_james_2_3_no_stray_closing_quote(self) -> None:
        self.assertEqual(_strip_quotes("“Σὺ στῆθι ἐκεῖ”,"), "Σὺ στῆθι ἐκεῖ,")
        v = _ct("greek", "james", 2, 3)
        self.assertIn("Σὺ στῆθι ἐκεῖ, ἢ κάθου", v)
        self.assertNotIn("”", v)

    def test_mark_6_23_recitative_hoti_no_premature_dot(self) -> None:
        v = _ct("greek", "mark", 6, 23)
        self.assertIn("ὤμοσεν αὐτῇ ὅτι Ὅ", v)
        self.assertNotIn("αὐτῇ· ὅτι", v)

    def test_nt_apostrophe_normalized_to_u02bc(self) -> None:
        for slug, ch, vn, expected in (
            ("romans", 14, 25, "κατʼ ἐπιταγὴν"),
            ("2-thessalonians", 2, 13, "ἀπʼ ἀρχῆς"),
        ):
            v = _ct("greek", slug, ch, vn)
            self.assertIn(expected, v)
            self.assertNotIn("\u2019", v)

    def test_nt_mechanical_and_orthographic_repairs(self) -> None:
        m23 = _ct("greek", "matthew", 23, 14)
        self.assertIn("προσευχόμενοι·", m23)
        self.assertNotIn(":", m23)
        self.assertIn("Γαββαθᾶ.", _ct("greek", "john", 19, 13))
        self.assertIn("Ῥαββουνί", _ct("greek", "john", 20, 16))


class TestStage1GreekOT(unittest.TestCase):
    def test_cross_chapter_misalignments_fixed(self) -> None:
        # Exod 39:15 no longer steals 40:8; 39:14 keeps Codex B's ark clause.
        self.assertIn("κιβωτὸν τῆς διαθήκης", _ct("greek", "exodus", 39, 14))
        e39_15 = _ct("greek", "exodus", 39, 15)
        self.assertEqual(e39_15, "καὶ τὸ θυσιαστήριον καὶ πάντα τὰ σκεύη αὐτοῦ,")
        self.assertNotIn("περιθήσεις", e39_15)
        self.assertTrue(_ct("greek", "exodus", 39, 16).startswith("καὶ τὸ ἔλαιον τῆς χρίσεως"))

        # 1 Chr 7:26 no longer steals 6:20 (Gershom); 1 Chr 6:43 & 6:54 align 1-to-1.
        c7_26 = _ct("greek", "1-chronicles", 7, 26)
        self.assertIn("Λαδδὰν", c7_26)
        self.assertNotIn("Γεδσών", c7_26)
        self.assertIn("Ἱεθθὰρ", _ct("greek", "1-chronicles", 6, 43))
        self.assertIn("Ἐγλὰμ", _ct("greek", "1-chronicles", 6, 54))
        self.assertIn("Γεθωρὼν", _ct("greek", "1-chronicles", 6, 54))

        # Non-regression: Gen 5:32 still splits cleanly from Swete 6:1.
        self.assertIn("Νῶε ἐτῶν πεντακοσίων", _ct("greek", "genesis", 5, 32))

    def test_chapter_boundary_duplicates_removed(self) -> None:
        self.assertNotIn(43, _chapter_map("greek", "1-samuel", 20))
        self.assertIn("ἀνέστη Δαυὶδ", _ct("greek", "1-samuel", 21, 1))

        self.assertNotIn(44, _chapter_map("greek", "numbers", 16))
        self.assertIn("ἐλάλησεν Κύριος πρὸς Μωυσῆν καὶ Ἀαρὼν λέγων", _ct("greek", "numbers", 17, 9))

        self.assertNotIn(45, _chapter_map("greek", "ezekiel", 20))
        self.assertIn("ἐγένετο λόγος Κυρίου", _ct("greek", "ezekiel", 21, 1))

        # Swete OCR Joel 3:15 (= Brenton 4:15, nb_hit=0.7273 due to αὐτῶυ + movable ν) must not leak into ch. 3.
        self.assertNotIn(15, _chapter_map("greek", "joel", 3))
        self.assertIn("συσκοτάσουσιν", _ct("greek", "joel", 4, 15))
        # Non-regression: genuine Greek OT extra verse 1 Sam 18:9 stays intact.
        self.assertIn(9, _chapter_map("greek", "1-samuel", 18))

    def test_ot_division_splits_no_duplication(self) -> None:
        self.assertNotIn("ἡγεμόνες Ἐδώμ", _ct("greek", "1-chronicles", 1, 48))
        self.assertIn("ἡγεμόνες Ἐδώμ", _ct("greek", "1-chronicles", 1, 51))

        self.assertNotIn("Ἰερμίας", _ct("greek", "1-chronicles", 12, 4))
        self.assertIn("Ἰερμίας", _ct("greek", "1-chronicles", 12, 5))

        self.assertNotIn("προσέρανεν", _ct("greek", "leviticus", 8, 28))
        self.assertIn("προσέρανεν", _ct("greek", "leviticus", 8, 29))
        self.assertNotIn("προσέῤῥνεν", _ct("greek", "leviticus", 8, 29))
        self.assertIn("Καὶ ἡγίασεν Ἀαρὼν", _ct("greek", "leviticus", 8, 30))

        self.assertIn("πρέσβεις", _ct("greek", "numbers", 21, 20))
        self.assertNotIn("πρέσβεις", _ct("greek", "numbers", 21, 21))

        self.assertNotIn("λαλήσεις", _ct("greek", "numbers", 27, 6))
        self.assertEqual(_ct("greek", "numbers", 27, 7), "καὶ τοῖς υἱοῖς Ἰσραὴλ λαλήσεις")

        self.assertNotIn("δοῦναι ἐκεῖ", _ct("greek", "1-kings", 6, 17))
        self.assertEqual(_ct("greek", "1-kings", 6, 19), "δοῦναι ἐκεῖ τὴν κιβωτὸν διαθήκης Κυρίου.")

        self.assertNotIn("ἐφημερίας", _ct("greek", "nehemiah", 12, 8))
        self.assertEqual(_ct("greek", "nehemiah", 12, 9), "εἰς τὰς ἐφημερίας.")

        self.assertNotIn("δέδοικας", _ct("greek", "job", 41, 1))
        self.assertIn("δέδοικας", _ct("greek", "job", 41, 2))
        self.assertNotIn("ἀντιστάς", _ct("greek", "job", 41, 3))

        self.assertIn("εἴπῃ ὁ ἐχθρός μου", _ct("greek", "psalms", 12, 4))
        self.assertNotIn("ὁ ἐχθρός μου", _ct("greek", "psalms", 12, 5))

        self.assertIn("δευτερώσεως", _ct("greek", "sirach", 41, 23))
        self.assertNotIn("δευτερώσεως", _ct("greek", "sirach", 41, 24))

        self.assertNotIn("Ῥαββὰθ", _ct("greek", "ezekiel", 21, 24))
        self.assertIn("Ῥαββὰθ", _ct("greek", "ezekiel", 21, 25))

    def test_ot_mechanical_polytonic_numeral_and_proper_name_repairs(self) -> None:
        self.assertNotIn("·.", _ct("greek", "exodus", 21, 22))
        self.assertNotIn("·.", _ct("greek", "1-samuel", 19, 21))
        self.assertIn("ὅσα ἂν εὕρῃ", _ct("greek", "judges", 9, 33))
        self.assertIn("εἴδοσαν", _ct("greek", "psalms", 106, 24))
        self.assertIn("εἶπεν δὲ Ἠσαύ", _ct("greek", "genesis", 25, 32))
        self.assertIn("πολλὴν γὰρ κακίαν", _ct("greek", "sirach", 30, 36))
        self.assertIn("πᾶς ποιῶν ταῦτα, πᾶς ποιῶν ἄδικον.", _ct("greek", "deuteronomy", 25, 16))
        self.assertIn("Κυρίου.", _ct("greek", "deuteronomy", 23, 3))
        self.assertIn("ὅτι οὐ λαλεῖ", _ct("greek", "1-kings", 22, 8))
        self.assertIn("ἑπτὰ", _ct("greek", "2-kings", 12, 1))
        self.assertIn("οὓς δ᾽ ἂν βούλωνται", _ct("greek", "1-maccabees", 8, 13))
        self.assertIn("νῦν οὖν", _ct("greek", "1-maccabees", 15, 5))
        self.assertIn("τὰ ἅρματα αὐτοῦ", _ct("greek", "jeremiah", 4, 13))
        self.assertIn("τῶν ἡμερῶν.", _ct("greek", "genesis", 49, 1))
        self.assertIn("Ἀναστὰς κατάβηθι", _ct("greek", "judges", 7, 9))
        self.assertIn("τῶν Λευειτῶν", _ct("greek", "1-chronicles", 28, 21))
        self.assertEqual(_ct("greek", "nehemiah", 11, 26), "καὶ ἐν Ἰησοῦ")

        # Numerals: Neh 7:41 properly formed ͵ασ᾽ (1,200); Ezra 2:37-38 & Neh 7:70 expanded to χίλιοι/χιλίους.
        self.assertIn("͵ασ᾽", _ct("greek", "nehemiah", 7, 41))
        self.assertIn("χίλιοι πεντήκοντα δύο", _ct("greek", "ezra", 2, 37))
        self.assertIn("χίλιοι διακόσιοι", _ct("greek", "ezra", 2, 38))
        self.assertIn("χιλίους", _ct("greek", "nehemiah", 7, 70))

        # Safe P1 proper names & Neh 12:19 dot.
        self.assertIn("Χαλδαίων.", _ct("greek", "2-kings", 25, 10))
        self.assertIn("Βασάν.", _ct("greek", "1-chronicles", 5, 12))
        self.assertIn("τῶν Λευειτῶν,", _ct("greek", "2-chronicles", 23, 18))
        self.assertIn("Φαραὼ", _ct("greek", "1-maccabees", 4, 9))
        self.assertIn("Βαροὺχ", _ct("greek", "jeremiah", 43, 10))
        self.assertIn("Βαλὰκ", _ct("greek", "micah", 6, 5))
        self.assertIn("Βαλγὰς,", _ct("greek", "nehemiah", 12, 18))
        self.assertIn("Ματθαναΐ·", _ct("greek", "nehemiah", 12, 19))
        self.assertIn("Καλλαΐ·", _ct("greek", "nehemiah", 12, 20))

    def test_phantom_psalm_headings_absent(self) -> None:
        self.assertNotIn(22, _chapter_map("greek", "psalms", 25))
        self.assertNotIn(10, _chapter_map("greek", "psalms", 116))
        self.assertNotIn(9, _chapter_map("greek", "psalms", 150))


class TestStage1GreekConcordanceNumerals(unittest.TestCase):
    def test_milesian_numeral_key_unit(self) -> None:
        self.assertIsNone(glx._milesian_numeral_key("δ᾽"))
        self.assertEqual(glx._milesian_numeral_key("δ᾽", "μηνῶν"), "G5064")
        self.assertIsNone(glx._milesian_numeral_key("δ᾽", "ἵνα"))
        self.assertIsNone(glx._milesian_numeral_key("δ᾽", "αὐτὸς"))
        self.assertEqual(glx._milesian_numeral_key("γ᾽", "καὶ"), "G5140")
        self.assertEqual(glx._milesian_numeral_key("͵α"), "G5507")
        self.assertEqual(glx._milesian_numeral_key("͵ασ᾽"), "G5507")
        self.assertEqual(glx._milesian_numeral_key("ας᾽"), "G5507")
        self.assertEqual(glx._milesian_numeral_key("μ᾽"), "G5062")

    def test_form_table_blocks_bare_numeral_fallback_to_hos(self) -> None:
        ft = glx._FormTable()
        ft.add("ἅ", "G3739", 100)
        ft.add("ἅς", "G3739", 100)
        self.assertEqual(ft.candidates("α"), {})
        self.assertEqual(ft.candidates("ας᾽"), {})
        self.assertEqual(ft.candidates("͵ασ᾽"), {})
        self.assertEqual(ft.candidates("τοβ᾽"), {})
        # Genuine accented relative pronouns still resolve normally.
        self.assertIn("G3739", ft.candidates("ἅ"))
        self.assertIn("G3739", ft.candidates("ἅς"))

    def test_tagger_numeral_verses(self) -> None:
        avail = glx.corpora_available()
        if not (avail["tagnt"] and avail["lxx_lemmas"]):
            self.skipTest("Greek gold corpora not present")
        prev_auto = glx.AUTO_PREPARE
        glx.AUTO_PREPARE = False
        try:
            tagger = glx.GreekTagger()
            j19 = {t.surface: t.lemma_key for t in tagger.tag_lxx_verse("judges", 19, 2, "καὶ ἦν ἐκεῖ ἡμέρας δ᾽ μηνῶν.")}
            self.assertEqual(j19["δ᾽"], "G5064")

            job1 = {t.surface: t.lemma_key for t in tagger.tag_lxx_verse(
                "job", 1, 17, "Οἱ ἱππεῖς ἐποίησαν ἡμῖν κεφαλὰς γ᾽, καὶ ἐκύκλωσαν τὰς καμήλους")}
            self.assertEqual(job1["γ᾽"], "G5140")

            # Non-regression: elided δ᾽ before vowel stays G1161 δέ.
            wis16 = {t.surface: t.lemma_key for t in tagger.tag_lxx_verse(
                "wisdom-of-solomon", 16, 23, "τοῦτο πάλιν δ᾽, ἵνα τραφῶσιν δίκαιοι")}
            self.assertEqual(wis16["δ᾽"], "G1161")

            for form in ("͵ασ᾽", "ας᾽"):
                n741 = {t.surface: t.lemma_key for t in tagger.tag_lxx_verse(
                    "nehemiah", 7, 41, f"υἱοὶ Φασεδούρ, {form} τεσσεράκοντα ἑπτά·")}
                self.assertEqual(n741[form], "G5507")

            for form in ("α", "͵α"):
                e237 = {t.surface: t.lemma_key for t in tagger.tag_lxx_verse(
                    "ezra", 2, 37, f"υἱοὶ Ἐμμήρ, {form} πεντήκοντα δύο·")}
                self.assertEqual(e237[form], "G5507")

            n770 = {t.surface: t.lemma_key for t in tagger.tag_lxx_verse(
                "nehemiah", 7, 70, "εἰς θησαυρὸν χρυσοῦς, α, φιάλας πεντήκοντα")}
            self.assertEqual(n770["α"], "G5507")

            e258 = {t.surface: t.lemma_key for t in tagger.tag_lxx_verse(
                "ezra", 2, 58, "πάντες οἱ Ναθεινὶν καὶ υἱοὶ Ἀσεδησελμὰ τοβ᾽.")}
            self.assertIsNone(e258["τοβ᾽"])
        finally:
            glx.AUTO_PREPARE = prev_auto


class TestStage1CrossLanguageGuards(unittest.TestCase):
    def test_hebrew_dss_cross_chapter_guard(self) -> None:
        d4 = _chapter_map("hebrew", "deuteronomy", 4)[40]
        self.assertNotIn("DSS-Torah (4Q)", d4["witness_readings"])
        d5 = _chapter_map("hebrew", "deuteronomy", 5)[16]
        self.assertIn("DSS-Torah (4Q)", d5["witness_readings"])

        p148 = _chapter_map("hebrew", "psalms", 148)[14]
        self.assertNotIn("11QPsᵃ (11Q5)", p148["witness_readings"])
        p149 = _chapter_map("hebrew", "psalms", 149)[9]
        self.assertIn("11QPsᵃ (11Q5)", p149["witness_readings"])

    def test_collator_cross_chapter_own_chapter_offset_protection(self) -> None:
        ref = {15: "καὶ τὸ θυσιαστήριον καὶ πάντα τὰ σκεύη αὐτοῦ"}
        nb_ref = {(40, 10): "καὶ χρίσεις τὸ θυσιαστήριον τῶν καρπωμάτων καὶ πάντα αὐτοῦ τὰ σκεύη"}
        cands = {(40, 8): "καὶ χρίσεις τὸ θυσιαστήριον τῶν καρπωμάτων καὶ πάντα αὐτοῦ τὰ σκεύη"}
        mapped, moved, _notes = align_versification(ref, 39, cands, "greek", neighbour_reference=nb_ref)
        self.assertNotIn(15, mapped)
        self.assertEqual(moved, {})

    def test_latin_ij_orthography_normalizer(self) -> None:
        expected = {
            "eius": "ejus",
            "Eius": "Ejus",
            "iam": "jam",
            "Iam": "Jam",
            "coniugem": "conjugem",
            "Iethran": "Jethran",
            "iecit": "jecit",
            "adiecit": "adjecit",
            # Non-regressions: must remain untouched
            "gladium": "gladium",
            "gradiuntur": "gradiuntur",
            "Israel": "Israel",
            "aer": "aer",
            "Seruit": "Seruit",
        }
        for src, want in expected.items():
            self.assertEqual(_latin_u_to_v(src), want, f"Failed on {src}")


if __name__ == "__main__":
    unittest.main()
