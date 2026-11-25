"""Isolated Stage 1 regression tests for Latin D1/D2 policy, language-specific chapter counts,
coordinated source_repairs.py fixes (Latin, Hebrew, Greek), and native-Vulgate versification.

Sets CTS_DATA_DIR and CTS_OUTPUT_ROOT to a fresh temporary directory BEFORE importing ``studio``
so live data/studio.db and exports are never touched (AGENTS.md #1).
"""

import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SANDBOX = tempfile.mkdtemp(prefix="cts_stage1_latin_")
os.environ["CTS_DATA_DIR"] = os.path.join(_SANDBOX, "data")
os.environ["CTS_OUTPUT_ROOT"] = os.path.join(_SANDBOX, "output")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from studio.catalog import (  # noqa: E402
    APPARATUS_ONLY,
    BOOKS_BY_SLUG,
    VERSIFICATION_ANCHORS,
    chapters_for_language,
)
from studio.db import SEED_VERSION  # noqa: E402
from studio.engine import CriticalTextEngine  # noqa: E402
from studio.lexica import versification as vz  # noqa: E402
from studio.source_repairs import _REPAIRABLE_COPIES, _SLIPS, repair_documented_imports  # noqa: E402


def tearDownModule() -> None:
    shutil.rmtree(_SANDBOX, ignore_errors=True)


class TestStage1LatinD1D2(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = CriticalTextEngine()
        cls.engine.config.provider_id = "textual_analysis"

    def _ch(self, lang: str, book: str, chapter: int):
        res = self.engine.collate_and_adjudicate(lang, book, chapter)
        return res, {v["verse"]: v for v in res["verses"]}

    def test_catalog_and_db_d1_d2_policy(self) -> None:
        self.assertEqual(VERSIFICATION_ANCHORS[("latin", "OT")][0], "usfx_xml")
        self.assertEqual(VERSIFICATION_ANCHORS[("latin", "NT")][0], "usfx_xml")
        self.assertIn("lat-amiatinus", APPARATUS_ONLY)
        self.assertIn("lat-amiatinus-nt", APPARATUS_ONLY)
        self.assertIn("lat-saints-staging", APPARATUS_ONLY)
        self.assertEqual(SEED_VERSION, 10)

    def test_chapters_for_language_isolates_native_vulgate_counts(self) -> None:
        self.assertEqual(chapters_for_language(BOOKS_BY_SLUG["esther"], "latin"), 16)
        self.assertEqual(chapters_for_language(BOOKS_BY_SLUG["esther"], "greek"), 10)
        self.assertEqual(chapters_for_language(BOOKS_BY_SLUG["esther"], "hebrew"), 10)
        self.assertEqual(chapters_for_language(BOOKS_BY_SLUG["daniel"], "latin"), 14)
        self.assertEqual(chapters_for_language(BOOKS_BY_SLUG["daniel"], "greek"), 12)
        self.assertEqual(chapters_for_language(BOOKS_BY_SLUG["daniel"], "hebrew"), 12)
        self.assertEqual(chapters_for_language(BOOKS_BY_SLUG["joel"], "latin"), 3)
        self.assertEqual(chapters_for_language(BOOKS_BY_SLUG["joel"], "greek"), 4)
        self.assertEqual(chapters_for_language(BOOKS_BY_SLUG["malachi"], "latin"), 4)
        self.assertEqual(chapters_for_language(BOOKS_BY_SLUG["malachi"], "greek"), 3)
        # Psalms stays 151 in BookSpec so Psalms 151 LookupError gap tests keep working
        self.assertEqual(chapters_for_language(BOOKS_BY_SLUG["psalms"], "latin"), 151)

    def test_d1_native_vulgate_order_and_restored_chapters(self) -> None:
        # Deut 5:17-18: native Vulgate murder before adultery
        _, d5 = self._ch("latin", "deuteronomy", 5)
        self.assertIn("occides", d5[17]["critical_text"])
        self.assertIn("mœchaberis", d5[18]["critical_text"])

        # Num 6:23-27: native 6:27 restored
        _, n6 = self._ch("latin", "numbers", 6)
        self.assertIn(27, n6)
        self.assertIn("Invocabuntque nomen meum", n6[27]["critical_text"])

        # Num 1:24-37: native MT/Vulgate tribe order (no Greek reordering hack)
        _, n1 = self._ch("latin", "numbers", 1)
        self.assertIn("Gad", n1[24]["critical_text"])
        self.assertIn("Issachar", n1[28]["critical_text"])
        self.assertIn("Zabulon", n1[30]["critical_text"])
        self.assertIn("Ephraim", n1[32]["critical_text"])
        self.assertIn("Benjamin", n1[36]["critical_text"])

        # Matt 5:4-5 beatitude order & Matt 17:20 (TR 17:21)
        _, m5 = self._ch("latin", "matthew", 5)
        self.assertIn("mites", m5[4]["critical_text"])
        self.assertIn("lugent", m5[5]["critical_text"])
        _, m17 = self._ch("latin", "matthew", 17)
        self.assertIn("orationem et jejunium", m17[20]["critical_text"])

        # Native Esther 11-16 (Additions) & Daniel 1/13/14 (Susanna & Bel cleanly separated)
        r_e11, e11 = self._ch("latin", "esther", 11)
        self.assertEqual(r_e11["verse_count"], 12)
        self.assertIn("Ptolemæo et Cleopatra", e11[1]["critical_text"])
        r_e16, e16 = self._ch("latin", "esther", 16)
        self.assertEqual(r_e16["verse_count"], 24)
        self.assertIn("Artaxerxes", e16[1]["critical_text"])

        r_d1, _ = self._ch("latin", "daniel", 1)
        self.assertEqual(r_d1["verse_count"], 21)  # no Susanna/Bel mashed into Dan 1
        r_d13, d13 = self._ch("latin", "daniel", 13)
        self.assertEqual(r_d13["verse_count"], 65)
        self.assertIn("Susanna", d13[2]["critical_text"])
        r_d14, d14 = self._ch("latin", "daniel", 14)
        self.assertEqual(r_d14["verse_count"], 42)
        self.assertIn("Bel", d14[2]["critical_text"])

        # Native Malachi 4 & Joel 3 & Ezekiel 20:45-49
        r_mal4, mal4 = self._ch("latin", "malachi", 4)
        self.assertEqual(r_mal4["verse_count"], 6)
        self.assertIn("Eliam", mal4[5]["critical_text"])
        r_joel3, _ = self._ch("latin", "joel", 3)
        self.assertEqual(r_joel3["verse_count"], 21)
        r_ez20, ez20 = self._ch("latin", "ezekiel", 20)
        self.assertEqual(r_ez20["verse_count"], 49)
        self.assertIn("meridiani", ez20[46]["critical_text"])

        # Sirach 1:15, 22:17, 42:1: zero English placeholder strings anywhere in text or apparatus
        for ch, v in [(1, 15), (22, 17), (42, 1)]:
            _, s = self._ch("latin", "sirach", ch)
            self.assertNotIn("No aligned Latin", s[v]["critical_text"])
            for a in s[v]["apparatus"]:
                for var in a["variants"]:
                    self.assertNotIn("No aligned Latin", var["reading"])

    def test_d2_amiatinus_apparatus_only_and_latin_typo_repairs(self) -> None:
        # Genesis follows Clementine uniformly, with Amiatinus (A) in apparatus
        _, g41 = self._ch("latin", "genesis", 41)
        self.assertIn("septem anni inopiæ", g41[54]["critical_text"])
        self.assertIn("Amiatinus (A)", g41[54]["witness_readings"])
        self.assertGreaterEqual(g41[54]["confidence"], 0.90)

        # Gen 20:2 USFX uxore suo -> uxore sua
        _, g20 = self._ch("latin", "genesis", 20)
        self.assertIn("uxore sua", g20[2]["critical_text"])
        self.assertNotIn("uxore suo", g20[2]["critical_text"])

        # All 5 non-word 1598 printing typos + Hos 2:13 inaure + Dan 5:2-3 Jerusalem
        checks = [
            ("nehemiah", 4, 18, "ædificantium", "ædificentium"),
            ("daniel", 5, 2, "Jerusalem", "Ierusalem"),
            ("daniel", 5, 3, "Jerusalem", "Ierusalem"),
            ("hosea", 2, 13, "inaure sua", "in aure sua"),
            ("amos", 8, 8, "ejicietur", "ejicicetur"),
            ("micah", 3, 7, "vultus", "vultos"),
            ("luke", 8, 2, "infirmitatibus", "infirmatibus"),
            ("2-corinthians", 1, 23, "vestræ", "vestæ"),
        ]
        for book, ch, v, want, bad in checks:
            with self.subTest(book=book, ch=ch, v=v):
                _, cm = self._ch("latin", book, ch)
                self.assertIn(want, cm[v]["critical_text"])
                self.assertNotIn(bad, cm[v]["critical_text"])

    def test_d2_preserves_all_14_historic_sixto_clementine_readings(self) -> None:
        # Attested historic Sixto-Clementine [different reading] forms MUST remain untouched
        historic = [
            ("ruth", 3, 10, "est secuta"),
            ("1-samuel", 4, 21, "vocabit"),
            ("2-kings", 8, 11, "Stetique"),
            ("1-chronicles", 16, 36, "omnis populo"),
            ("1-chronicles", 26, 6, "Semei"),
            ("isaiah", 1, 19, "comeditis"),
            ("isaiah", 2, 6, "augeres"),
            ("isaiah", 3, 1, "robor"),
            ("isaiah", 5, 25, "non est adversus"),
            ("isaiah", 9, 5, "omnis violentia"),
            ("wisdom-of-solomon", 18, 21, "Prosperans"),
            ("numbers", 11, 31, "arreptans"),
            ("luke", 6, 22, "ejicerint"),
            ("acts", 16, 5, "abundabunt"),
        ]
        for book, ch, v, expected in historic:
            with self.subTest(book=book, ch=ch, v=v):
                _, cm = self._ch("latin", book, ch)
                self.assertIn(expected, cm[v]["critical_text"])

    def test_all_source_repairs_slips_fire_and_are_idempotent(self) -> None:
        self.assertGreaterEqual(len(_SLIPS), 57)
        for wids, book, ch, v, old, new, _why in _SLIPS:
            sample = old.lstrip("^").rstrip("$")
            for wid in wids:
                with self.subTest(wid=wid, book=book, ch=ch, v=v):
                    w = {"id": wid, "parser_kind": _REPAIRABLE_COPIES[wid]}
                    repaired, notes = repair_documented_imports(w, book, {ch: {v: sample}})
                    self.assertEqual(repaired[ch][v], new)
                    self.assertTrue(notes.get(ch))
                    repaired2, notes2 = repair_documented_imports(w, book, repaired)
                    self.assertEqual(repaired2[ch][v], new)
                    self.assertEqual(notes2, {})

    def test_versification_native_vulgate_and_preserved_extra_site_rules(self) -> None:
        # Native Vulgate -> Saints key Principle 2 mappings
        self.assertEqual(vz.to_saints("latin", "deuteronomy", 5, 17), [(5, 18)])
        self.assertEqual(vz.to_saints("latin", "deuteronomy", 5, 18), [(5, 17)])
        self.assertEqual(vz.to_saints("latin", "numbers", 6, 27), [(6, 23)])
        self.assertEqual(vz.to_saints("latin", "numbers", 1, 28), [(1, 26)])
        self.assertEqual(vz.to_saints("latin", "numbers", 1, 32), [(1, 30)])
        self.assertEqual(vz.to_saints("latin", "malachi", 4, 4), [(3, 24)])
        self.assertEqual(vz.to_saints("latin", "joel", 3, 1), [(4, 1)])
        self.assertEqual(vz.to_saints("latin", "ezekiel", 20, 45), [(21, 1)])
        self.assertEqual(vz.to_saints("latin", "esther", 16, 1), [(8, 12)])
        self.assertEqual(vz.to_saints("latin", "daniel", 13, 1), [])
        self.assertEqual(vz.to_extra_site_anchor("latin", "daniel", 13, 1), (13, 1))
        self.assertEqual(vz.to_saints("latin", "daniel", 14, 1), [])
        self.assertEqual(vz.to_extra_site_anchor("latin", "daniel", 14, 1), (14, 1))
        # Confirmed kept extra-site anchors across all 3 languages (site 2 Kgs 25:10 & Dan 6:16 hold unrelated text)
        self.assertEqual(vz.to_saints("hebrew", "2-kings", 25, 10), [])
        self.assertEqual(vz.to_saints("latin", "2-kings", 25, 10), [])
        self.assertEqual(vz.to_extra_site_anchor("hebrew", "2-kings", 25, 10), (25, 10))
        self.assertEqual(vz.to_extra_site_anchor("latin", "2-kings", 25, 10), (25, 10))
        self.assertEqual(vz.to_saints("hebrew", "daniel", 6, 16), [])
        self.assertEqual(vz.to_saints("latin", "daniel", 6, 15), [])
        self.assertEqual(vz.to_extra_site_anchor("hebrew", "daniel", 6, 16), (6, 16))
        self.assertEqual(vz.to_extra_site_anchor("latin", "daniel", 6, 15), (6, 16))


if __name__ == "__main__":
    unittest.main()
