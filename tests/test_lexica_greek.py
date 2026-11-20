"""Tests for studio/lexica/greek.py (Greek lemma + root tagger of The Saints Concordance).

Offline.  They read the open corpora inside the Studio (STEPBible TAGNT/TBESG, Open Scriptures
LXX lemmas and Greek Word List, Strong's Greek XML, MorphGNT derivation data) and, read-only, the
live Studio database; each test skips cleanly when what it needs is missing.  The sandbox
environment of tests/test_studio.py is set up first (AGENTS.md invariant 1).
"""

from __future__ import annotations

import os
import re
import sqlite3
import unicodedata
import unittest
from pathlib import Path

try:
    from . import test_studio as _ts  # noqa: F401  (sets CTS_DATA_DIR / CTS_OUTPUT_ROOT first)
except ImportError:
    import test_studio as _ts  # type: ignore[no-redef]  # noqa: F401

from studio.lexica import TokenTag, tokenize_verse  # noqa: E402
from studio.lexica import greek  # noqa: E402

_AVAIL = greek.corpora_available()
_CORE = _AVAIL["tagnt"] and _AVAIL["tbesg"] and _AVAIL["lxx_lemmas"] and _AVAIL["greek_word_list"]
_LIVE_DB = Path(__file__).resolve().parents[1] / "data" / "studio.db"


def _keys(tags):
    return [t.lemma_key for t in tags]


def _tag_of(tags, surface):
    for t in tags:
        if t.surface == surface:
            return t
    raise AssertionError(f"{surface} not among {[t.surface for t in tags]}")


@unittest.skipUnless(_CORE, "Greek gold corpora (TAGNT, TBESG, LxxLemmas, Greek Word List) not present")
class TestGreekTagger(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        greek.AUTO_PREPARE = False          # never read the live DB implicitly in tests
        cls.tg = greek.get_tagger()
        cls.lex = greek.load_lexicon()

    # -- contract ------------------------------------------------------------------------------
    def test_one_tag_per_token_and_keys_in_lexicon(self) -> None:
        verses = {
            18: "ἀμὴν γὰρ λέγω ὑμῖν, ἕως ἂν παρέλθῃ ὁ οὐρανὸς καὶ ἡ γῆ, ἰῶτα ἓν ἢ μία κεραία οὐ μὴ παρέλθῃ "
                "ἀπὸ τοῦ νόμου, ἕως ἂν πάντα γένηται.",
            19: "",
        }
        res = greek.tag_chapter("matthew", 5, verses)
        self.assertEqual(set(res), {18, 19})
        self.assertEqual(res[19], [])
        toks = tokenize_verse(verses[18], "grc")
        self.assertEqual([t.surface for t in res[18]], toks)
        self.assertEqual([t.index for t in res[18]], list(range(1, len(toks) + 1)))
        for t in res[18]:
            self.assertIsInstance(t, TokenTag)
            if t.lemma_key is None:
                self.assertEqual(t.method, "untagged")
            else:
                self.assertIn(t.lemma_key, self.lex)
                self.assertIn(t.method, ("gold-aligned", "gold-form"))

    def test_lexicon_entries_are_well_formed(self) -> None:
        e = self.lex["G3056"]
        self.assertEqual((e.lang, e.lemma, e.pos, e.strongs), ("grc", "λόγος", "N", "G3056"))
        self.assertTrue(e.root_key.startswith("grc:"))
        self.assertIn("CC BY", e.source)
        for key, ent in list(self.lex.items())[:3000]:
            self.assertEqual(key, ent.lemma_key)
            self.assertIn(ent.pos, ("N", "V", "ADJ", "ADV", "PREP", "CONJ", "PRON", "ART", "PART", "NUM", "INTERJ", "PROPN"))
            self.assertTrue(ent.root_key.startswith("grc:") and not ent.root_key.startswith("grc:grc:"), ent)

    # -- New Testament -------------------------------------------------------------------------
    def test_nt_homographs_resolve_by_position(self) -> None:
        res = greek.tag_chapter("matthew", 5, {18: "ἀμὴν γὰρ λέγω ὑμῖν, ἕως ἂν παρέλθῃ ὁ οὐρανὸς καὶ ἡ γῆ, "
                                                    "ἰῶτα ἓν ἢ μία κεραία οὐ μὴ παρέλθῃ ἀπὸ τοῦ νόμου, ἕως ἂν πάντα γένηται."})[18]
        self.assertEqual(_tag_of(res, "ἡ").lemma_key, "G3588")      # article
        self.assertEqual(_tag_of(res, "ἢ").lemma_key, "G2228")      # 'or'
        self.assertEqual(_tag_of(res, "μία").lemma_key, "G1520")    # folded into εἷς
        self.assertEqual(_tag_of(res, "λέγω").lemma_key, "G3004")
        self.assertFalse(_tag_of(res, "γὰρ").is_content)
        self.assertTrue(_tag_of(res, "οὐρανὸς").is_content)

    def test_nt_dictionary_form_beats_family_number(self) -> None:
        # TAGNT files ἐμός under G1473 and ὤφθη under G3700 but names the true dictionary form
        res = greek.tag_chapter("john", 4, {34: "λέγει αὐτοῖς ὁ Ἰησοῦς· Ἐμὸν βρῶμά ἐστιν ἵνα ποιήσω τὸ θέλημα "
                                                "τοῦ πέμψαντός με καὶ τελειώσω αὐτοῦ τὸ ἔργον."})[34]
        self.assertEqual(_tag_of(res, "Ἐμὸν").lemma_key, "G1699")   # ἐμός, not ἐγώ
        self.assertEqual(_tag_of(res, "με").lemma_key, "G1473")     # μέ G3165 folded into ἐγώ
        res = greek.tag_chapter("luke", 24, {34: "λέγοντας ὅτι ὄντως ἠγέρθη ὁ κύριος καὶ ὤφθη Σίμωνι."})[34]
        self.assertEqual(_tag_of(res, "ὤφθη").lemma_key, "G3708")   # ὁράω

    def test_nt_romans_doxology_at_14_24(self) -> None:
        res = greek.tag_chapter("romans", 14, {24: "⟦Τῷ δὲ δυναμένῳ ὑμᾶς στηρίξαι κατὰ τὸ εὐαγγέλιόν μου καὶ τὸ "
                                                   "κήρυγμα Ἰησοῦ χριστοῦ, κατὰ ἀποκάλυψιν μυστηρίου χρόνοις αἰωνίοις σεσιγημένου,⟧"})[24]
        self.assertEqual(_tag_of(res, "σεσιγημένου").lemma_key, "G4601")   # σιγάω, from Rom.16.25{14.24}
        self.assertTrue(all(t.lemma_key for t in res))

    # -- Septuagint ----------------------------------------------------------------------------
    def test_lxx_genesis_1(self) -> None:
        res = greek.tag_chapter("genesis", 1, {
            1: "Ἐν ἀρχῇ ἐποίησεν ὁ θεὸς τὸν οὐρανὸν καὶ τὴν γῆν.",
            2: "ἡ δὲ γῆ ἦν ἀόρατος καὶ ἀκατασκεύαστος, καὶ σκότος ἐπάνω τῆς ἀβύσσου· καὶ πνεῦμα θεοῦ ἐπεφέρετο ἐπάνω τοῦ ὕδατος.",
        })
        self.assertEqual(_keys(res[1]), ["G1722", "G0746", "G4160", "G3588", "G2316", "G3588", "G3772", "G2532", "G3588", "G1093"])
        self.assertEqual(_tag_of(res[2], "ἦν").lemma_key, "G1510")
        self.assertEqual(_tag_of(res[2], "ἐπεφέρετο").lemma_key, "G2018")
        akat = _tag_of(res[2], "ἀκατασκεύαστος")
        self.assertIsNotNone(akat.lemma_key)              # an LXX-only word (TBESG extended number)
        self.assertEqual(self.lex[akat.lemma_key].lemma, "ἀκατασκεύαστος")

    def test_lxx_preposition_never_taken_by_a_compound(self) -> None:
        res = greek.tag_chapter("exodus", 28, {30: "καὶ ἐπιθήσεις ἐπὶ τὸ λόγιον τῆς κρίσεως τὴν δήλωσιν καὶ τὴν ἀλήθειαν· "
                                                   "καὶ ἔσται ἐπὶ τοῦ στήθους Ἀαρὼν ὅταν εἰσπορεύηται εἰς τὸ ἅγιον ἐναντίον Κυρίου· "
                                                   "καὶ οἴσει Ἀαρὼν τὰς κρίσεις τῶν υἱῶν Ἰσραὴλ ἐπὶ τοῦ στήθους ἐναντίον Κυρίου διὰ παντός."})[30]
        self.assertNotEqual(_tag_of(res, "ἐπιθήσεις").lemma_key, "G1909")
        self.assertEqual(_tag_of(res, "ἐπὶ").lemma_key, "G1909")
        self.assertEqual(_tag_of(res, "Κυρίου").lemma_key, "G2962")
        res = greek.tag_chapter("1-samuel", 20, {14: "καὶ μὲν ἔτι μου ζῶντος, καὶ ποιήσεις ἔλεος μετ᾽ ἐμοῦ· καὶ ἐὰν θανάτῳ ἀποθάνω,"})[14]
        self.assertNotEqual(_tag_of(res, "ἀποθάνω").lemma_key, "G0575")

    def test_lxx_elided_forms_resolve(self) -> None:
        res = greek.tag_chapter("2-maccabees", 4, {13: "ἦν δ᾽ οὕτως ἀκμὴ τοῦ Ἑλληνισμοῦ καὶ πρόσβασις ἀλλοφυλισμοῦ διὰ τὴν "
                                                      "τοῦ ἀσεβοῦς καὶ οὐκ ἀρχιερέως Ἰάσονος ὑπερβάλλουσαν ἀναγνείαν,"})[13]
        self.assertEqual(_tag_of(res, "δ᾽").lemma_key, "G1161")
        res = greek.tag_chapter("1-samuel", 20, {14: "καὶ μὲν ἔτι μου ζῶντος, καὶ ποιήσεις ἔλεος μετ᾽ ἐμοῦ· καὶ ἐὰν θανάτῳ ἀποθάνω,"})[14]
        self.assertEqual(_tag_of(res, "μετ᾽").lemma_key, "G3326")
        self.assertEqual(_tag_of(res, "μου").lemma_key, "G1473")   # OSSP's μου (G3450) folded into ἐγώ
        res = greek.tag_chapter("1-maccabees", 1, {1: "Καὶ ἐγένετο μετὰ τὸ πατάξαι Ἀλέξανδρον τὸν Φιλίππου τὸν Μακεδόνα, ὃς "
                                                      "ἐξῆλθεν ἐκ τῆς γῆς Χεττιείμ, καὶ ἐπάταξεν τὸν Δαρεῖον βασιλέα Περσῶν καὶ Μήδων, "
                                                      "καὶ ἐβασίλευσεν ἀντ᾽ αὐτοῦ πρότερον ἐπὶ τὴν Ἑλλάδα."})[1]
        self.assertEqual(_tag_of(res, "ἀντ᾽").lemma_key, "G0473")

    def test_lxx_letter_subverses_and_prologue_belong_to_their_verse(self) -> None:
        book = self.tg.lxx["Esth"]
        self.assertGreater(len(book.groups[(1, 1)]), 150)        # 1:1a-1:1s + 1:1
        self.assertIn("Esth.1.1a", book.refs[(1, 1)])
        sir = self.tg.lxx["Sir"]
        self.assertIn("Sir.Prolog.1", sir.refs[(1, 1)])

    def test_lowercase_oxen_are_not_boaz(self) -> None:
        res = greek.tag_chapter("genesis", 13, {5: "καὶ Λὼτ τῷ συμπορευομένῳ μετὰ Ἀβρὰμ ἦν πρόβατα καὶ βόες καὶ κτήνη."})[5]
        self.assertNotEqual(_tag_of(res, "βόες").lemma_key, "G1003")   # TAGNT's Βόες is Boaz
        self.assertEqual(_tag_of(res, "Ἀβρὰμ").lemma_key is not None, True)

    def test_untagged_rather_than_guessed(self) -> None:
        res = greek.tag_chapter("genesis", 1, {1: "Ἐν ἀρχῇ ξυζξυζεν ὁ θεὸς."})[1]
        t = _tag_of(res, "ξυζξυζεν")
        self.assertIsNone(t.lemma_key)
        self.assertEqual((t.method, t.confidence), ("untagged", 0.0))

    # -- form knowledge (accent / breathing aware) ------------------------------------------------
    def test_breathing_and_accent_keep_homographs_apart(self) -> None:
        tg = self.tg
        self.assertEqual(tg.known_keys("ἢ"), {"G2228"})
        self.assertEqual(tg.known_keys("Κυρίου"), {"G2962"})
        self.assertNotIn("G0863", tg.known_keys("ἁφή"))          # ἁφή 'plague' is not ἀφῇ (ἀφίημι)
        self.assertEqual(tg.known_keys("σου"), {"G4771"})
        self.assertEqual(tg.known_keys("σοῦ"), {"G4771"})        # enclitic accent does not matter
        self.assertEqual(tg.known_keys("δ᾽"), {"G1161"})
        self.assertEqual(tg.known_keys("ἐστι"), {"G1510"})        # movable ν
        table = greek._FormTable()
        table.add("γάζης", "G1047")
        self.assertEqual(table.lookup("γάζης", 0.95, 1), ("G1047", 1.0))
        self.assertIsNone(table.lookup("Γάζης", 0.95, 1))         # a capitalised token is not the noun

    def test_stem_similarity_regressions(self) -> None:
        sim = greek.stem_similarity
        self.assertGreaterEqual(sim("απεστειλεν", "αποστελλω"), 0.78)
        self.assertGreaterEqual(sim("επιθησεισ", "επιτιθημι"), 0.78)
        self.assertGreaterEqual(sim("αλλοφυλων", "αλλοφυλος"), 0.78)   # Word List keys end in ς
        self.assertGreaterEqual(sim("λευειται", "λευιτης"), 0.78)      # Codex B itacism
        self.assertLess(sim("ανηγγελη", "ανηρ"), 0.78)                 # not ἀνήρ
        self.assertLess(sim("ανηρημενοισ", "ανηρ"), 0.78)
        self.assertLess(sim("εφορα", "φορα"), 0.78)                    # no augment on a noun
        self.assertLess(sim("οριω", "οραω"), 0.78)

    # -- homographs, folds, roots ---------------------------------------------------------------
    def test_homographs_stay_distinct(self) -> None:
        lex = self.lex
        mountain = lex["G3735"]
        boundary = [e for e in lex.values() if e.lemma == "ὅρος"]
        self.assertEqual(mountain.lemma, "ὄρος")
        self.assertTrue(boundary)
        self.assertNotEqual(boundary[0].lemma_key, "G3735")
        self.assertNotEqual(boundary[0].root_key, mountain.root_key)
        go = [e for e in lex.values() if e.lemma == "εἶμι"]
        self.assertTrue(go)
        self.assertNotEqual(go[0].lemma_key, "G1510")
        self.assertNotEqual(go[0].root_key, lex["G1510"].root_key)

    def test_pronoun_and_copula_forms_fold(self) -> None:
        lx = self.tg.lex
        for num, base in (("G3450", "G1473"), ("G4675", "G4771"), ("G2257", "G1473"), ("G2258", "G1510"),
                          ("G1511", "G1510"), ("G3165", "G1473")):
            self.assertEqual(lx.canonical(num), base)
        for num in ("G1699", "G4674", "G4572", "G1683"):          # possessives / reflexives stay
            self.assertEqual(lx.canonical(num), num)

    @unittest.skipUnless(_AVAIL["strongs"], "Strong's Greek XML not present")
    def test_root_families_follow_derivation_data(self) -> None:
        lex = self.lex
        r = lambda k: lex[k].root_key  # noqa: E731
        self.assertEqual(r("G3056"), r("G3004"))      # λόγος < λέγω
        self.assertEqual(r("G4161"), r("G4160"))      # ποίημα < ποιέω
        self.assertEqual(r("G4863"), r("G0071"))      # συνάγω < σύν + ἄγω
        self.assertEqual(r("G0568"), "grc:G2192")     # ἀπέχω: family ἔχω
        self.assertIn("ἀπό", lex["G0568"].formula)
        self.assertEqual(lex["G0568"].root_source, "Strongs-CC0")
        self.assertEqual(r("G1577"), r("G2564"))      # ἐκκλησία < ἐκ + καλέω
        self.assertNotEqual(r("G3004"), r("G2036"))   # λέγω and εἶπον are separate primaries in Strong's
        self.assertNotEqual(r("G0080"), "grc:G0001")  # ἀδελφός is not filed under α (G1 as a prefix)
        self.assertNotEqual(r("G0549"), "grc:G0575")  # ἄπειμι 'go away': a preverb alone is no family
        self.assertEqual(lex["G2316"].root_source, "self")
        self.assertEqual(lex["G3004"].root_key, "grc:G3004")

    def test_root_families_are_closed(self) -> None:
        lex = self.lex
        for key, ent in lex.items():
            head = ent.root_key[4:]
            if head in lex:
                self.assertEqual(lex[head].root_key, ent.root_key, key)
        # Strong's derives μιμνήσκω from μνάομαι, the Word List μνάομαι from μιμνήσκω: one family
        self.assertEqual(lex["G3403"].root_key, lex["G3415"].root_key)
        self.assertEqual(lex["G3421"].root_key, lex["G3403"].root_key)     # μνημονεύω

    def test_function_words_are_not_content(self) -> None:
        lx = self.tg.lex
        for key in ("G3588", "G2532", "G1161", "G1063", "G3767", "G5037", "G0302", "G3303", "G1473",
                    "G4771", "G0846", "G3739", "G3756"):
            self.assertFalse(lx.is_content(key), key)
        for key in ("G2316", "G3004", "G3056", "G4160", "G3735"):
            self.assertTrue(lx.is_content(key), key)
        # the docstring's conjunctions that TBESG files as adverb / preposition (verifier 18 Nov)
        for key in ("G5613", "G2193", "G0891", "G3360", "G4250"):     # ὡς ἕως ἄχρι μέχρι πρίν
            self.assertFalse(lx.is_content(key), key)
        for key in ("G1722", "G1519", "G4314"):                       # prepositions stay content
            self.assertTrue(lx.is_content(key), key)

    # -- regressions from the 18 Nov independent verification ------------------------------------
    @unittest.skipUnless(_AVAIL["strongs"], "Strong's Greek XML not present")
    def test_hedged_strongs_links_are_not_followed(self) -> None:
        lex = self.lex
        # 'from G4314 and a probable derivative of G2965': προσκυνέω is not in the family of κύων
        self.assertNotEqual(lex["G4352"].root_key, lex["G2965"].root_key)
        self.assertNotIn("κύων", lex["G4352"].formula)
        # 'as if from G1538 and G5119': ἑκάστοτε is not filed under the particle τε
        self.assertNotEqual(lex["G1539"].root_key, lex["G5037"].root_key)

    @unittest.skipUnless(_AVAIL["strongs"], "Strong's Greek XML not present")
    def test_silver_is_not_in_the_family_of_work(self) -> None:
        lex = self.lex
        silver = lex["G0696"].root_key                                # ἄργυρος
        for key in ("G0694", "G0693", "G5366"):                       # ἀργύριον ἀργύρεος φιλάργυρος
            self.assertEqual(lex[key].root_key, silver, key)
        self.assertNotEqual(silver, lex["G2041"].root_key)            # ἔργον
        self.assertEqual(lex["G0692"].root_key, lex["G2041"].root_key)   # ἀργός 'idle' < α + ἔργον

    @unittest.skipUnless(_AVAIL["strongs"], "Strong's Greek XML not present")
    def test_speech_words_are_not_merged_with_light_words(self) -> None:
        lex = self.lex
        speech = lex["G5346"].root_key                                # φημί
        light = lex["G5457"].root_key                                 # φῶς
        self.assertNotEqual(speech, light)
        for key in ("G5456", "G4396", "G0987", "G5345"):              # φωνή προφήτης βλασφημέω φήμη
            self.assertEqual(lex[key].root_key, speech, key)
        # since the conservative family policy (18 Nov final check) φαίνω is no longer filed under
        # φῶς (Strong's 'prolongation for the base of G5457' is not visible in the word): two
        # light families, φῶς (φωστήρ φωτίζω) and φαίνω (φανερόω), neither with the speech words
        self.assertEqual(lex["G5458"].root_key, light)                # φωστήρ
        self.assertEqual(lex["G5319"].root_key, lex["G5316"].root_key)   # φανερόω / φαίνω
        self.assertNotEqual(lex["G5316"].root_key, speech)
        self.assertEqual(lex["G4392"].root_key, lex["G5316"].root_key)   # πρόφασις < προφαίνω
        # φημί's Word List 'src φάω' is not followed: Strong's hedges it ('properly, ...')
        self.assertEqual(lex["G5346"].root_source, "self")

    @unittest.skipUnless(_AVAIL["strongs"], "Strong's Greek XML not present")
    def test_strongs_slips_and_same_as_a_compound(self) -> None:
        lex = self.lex
        # Ἀρχέλαος 'from G757 and G2994' (Λαοδικεύς) means λαός G2992
        self.assertEqual(lex["G0745"].root_key, lex["G2992"].root_key)
        self.assertNotEqual(lex["G0745"].root_key, lex["G1349"].root_key)   # not δίκη
        # εὐπορέω 'from a compound of G2090 (ἑτοιμάζω) ...' means εὖ G2095
        self.assertNotIn("ἑτοιμάζω", lex["G2141"].formula)
        # πυκνός 'from the same as G4635' (σκηνοποιός, a compound) is not filed under ποιέω
        self.assertNotEqual(lex["G4437"].root_key, lex["G4160"].root_key)
        # a formula does not repeat a component ('χρή < χράω + χράω')
        for key in ("G5534", "G0568", "G4396"):
            for step in lex[key].formula.split(" < ")[1:]:
                parts = step.split(" + ")
                self.assertEqual(len(parts), len(set(parts)), lex[key].formula)

    def test_word_list_v_pointer_does_not_merge_headwords(self) -> None:
        lx = self.tg.lex
        self.assertNotEqual(lx.gwl_lemma_key("επισκευαζω"), "G0643")    # ἐπισκευάζω is not ἀποσκευάζω
        self.assertNotEqual(lx.gwl_lemma_key("δεος"), "G1169")          # δέος is not δειλός
        self.assertEqual(lx.gwl_lemma_key("χειμαρρους"), "G5493")       # spellings still join
        self.assertEqual(lx.gwl_lemma_key("ισσαχαρ"), "G2466")
        self.assertEqual(lx.gwl_lemma_key("ναιμαν"), "G3497")           # TBESG prints 'Νεεμάν, Ναιμάν'
        res = greek.tag_chapter("1-samuel", 3, {3: "καὶ ὁ λύχνος τοῦ θεοῦ πρὶν ἐπισκευασθῆναι, καὶ Σαμουὴλ "
                                                    "ἐκάθευδεν ἐν τῷ ναῷ οὗ ἡ κιβωτὸς τοῦ θεοῦ."})[3]
        self.assertNotEqual(_tag_of(res, "ἐπισκευασθῆναι").lemma_key, "G0643")

    def test_kidron_is_not_cedar(self) -> None:
        self.assertEqual(self.lex["G2748"].lemma, "Κεδρών")
        self.assertNotEqual(self.tg.lex.gwl_lemma_key("κεδρος"), "G2748")   # κέδρος 'cedar'

    def test_nt_variant_lemma_not_given_to_the_printed_word(self) -> None:
        # TAGNT tags NA's ἐπισκευασάμενοι with TR's ἀποσκευάζω and ἐπέλειχον with ἀπολείχω
        res = greek.tag_chapter("acts", 21, {15: "Μετὰ δὲ τὰς ἡμέρας ταύτας ἐπισκευασάμενοι ἀνεβαίνομεν εἰς Ἱεροσόλυμα·"})[15]
        self.assertNotEqual(_tag_of(res, "ἐπισκευασάμενοι").lemma_key, "G0643")
        res = greek.tag_chapter("luke", 16, {21: "καὶ ἐπιθυμῶν χορτασθῆναι ἀπὸ τῶν πιπτόντων ἀπὸ τῆς τραπέζης τοῦ "
                                                 "πλουσίου· ἀλλὰ καὶ οἱ κύνες ἐρχόμενοι ἐπέλειχον τὰ ἕλκη αὐτοῦ."})[21]
        self.assertNotEqual(_tag_of(res, "ἐπέλειχον").lemma_key, "G0621")
        # a listed 'spelling' that TAGNT prints elsewhere as its own word takes that word's lemma
        res = greek.tag_chapter("mark", 3, {4: "καὶ λέγει αὐτοῖς· Ἔξεστιν τοῖς σάββασιν ἀγαθοποιῆσαι ἢ κακοποιῆσαι, "
                                               "ψυχὴν σῶσαι ἢ ἀποκτεῖναι; οἱ δὲ ἐσιώπων."})[4]
        self.assertEqual(_tag_of(res, "ἀγαθοποιῆσαι").lemma_key, "G0015")
        # spellings of the same word keep TAGNT's lemma (Καφαρναούμ / Καπερναούμ)
        res = greek.tag_chapter("john", 2, {12: "Μετὰ τοῦτο κατέβη εἰς Καφαρναοὺμ αὐτὸς καὶ ἡ μήτηρ αὐτοῦ καὶ οἱ "
                                                "ἀδελφοὶ καὶ οἱ μαθηταὶ αὐτοῦ, καὶ ἐκεῖ ἔμειναν οὐ πολλὰς ἡμέρας."})[12]
        self.assertEqual(_tag_of(res, "Καφαρναοὺμ").lemma_key, "G2584")

    def test_gap_fill_needs_a_stem_match_except_for_names(self) -> None:
        res = greek.tag_chapter("sirach", 51, {6: "βασιλεῖ διαβολὴ γλώσσης ἀδίκου· ᾔνεσεν ἕως θανάτου ἡ ψυχή μου, "
                                                  "καὶ ἡ ζωή μου ἦν σύνεγγυς ᾅδου κάτω·"})[6]
        self.assertNotEqual(_tag_of(res, "ᾔνεσεν").lemma_key, "G1448")          # not ἐγγίζω (0.22)
        res = greek.tag_chapter("wisdom-of-solomon", 2, {19: "ὕβρει καὶ βασάνῳ ἐτάσωμεν αὐτόν, ἵνα γνῶμεν τὴν "
                                                             "ἐπιεικίαν αὐτοῦ καὶ δικάσωμεν τὴν ἀνεξικακίαν αὐτοῦ·"})[19]
        self.assertNotEqual(_tag_of(res, "δικάσωμεν").lemma_key, "G1381")       # not δοκιμάζω (0.13)
        res = greek.tag_chapter("genesis", 31, {49: "καὶ Ἡ ὅρασις, ἣν εἶπεν Ἐφίδοι ὁ θεὸς ἀνὰ μέσον ἐμοῦ καὶ σοῦ, "
                                                    "ὅτι ἀποστησόμεθα ἕτερος ἀπὸ τοῦ ἑτέρου."})[49]
        self.assertNotEqual(_tag_of(res, "Ἐφίδοι").lemma_key, "G1929")          # capitalised, but no name
        res = greek.tag_chapter("1-chronicles", 3, {1: "Καὶ οὗτοι ἦσαν υἱοὶ Δαυὶδ οἱ τεχθέντες αὐτῷ ἐν Χεβρών· ὁ "
                                                       "πρωτότοκος Ἀμνὼν τῇ Ἀχεινάαμ τῇ Ἰσραηλείτιδι, ὁ δεύτερος "
                                                       "Δαμνιὴλ τῇ Ἀβειγαίᾳ τῇ Καρμηλίᾳ,"})[1]
        self.assertEqual(_tag_of(res, "Δαμνιὴλ").lemma_key, "G1158")            # Codex B's name spelling
        res = greek.tag_chapter("isaiah", 36, {12: "καὶ εἶπεν Ῥαβσάκης πρὸς αὐτούς Μὴ πρὸς τὸν κύριον ὑμῶν ἢ πρὸς "
                                                   "ὑμᾶς ἀπέσταλκέν με ὁ κύριός μου λαλῆσαι τοὺς λόγους τούτους;"})[12]
        self.assertEqual(self.lex[_tag_of(res, "Ῥαβσάκης").lemma_key].lemma, "Ῥαψάκης")   # a title, capitalised
        # a lower-case suppletive form is paired when it shares a stem with a form TAGNT attests
        self.assertTrue(self.tg.continues_attested_form("ὀφθήτω", "G3708"))     # ὤφθη (ὁράω)
        self.assertTrue(self.tg.continues_attested_form("ἔφαγες", "G2068"))     # ἔφαγεν (φαγεῖν ~ ἐσθίω)
        self.assertFalse(self.tg.continues_attested_form("ᾔνεσεν", "G1448"))
        self.assertFalse(self.tg.continues_attested_form("ἐνεποίησεν", "G7133"))   # another preposition

    def test_capitalised_sentence_opener_is_not_filtered_as_a_name(self) -> None:
        table = greek._FormTable(common_noun=lambda k: k == "G1047")
        table.add("λάβε", "G2983")
        table.add("γάζης", "G1047")
        self.assertEqual(table.lookup("Λάβε", 0.95, 1), ("G2983", 1.0))    # a verb opening a sentence
        self.assertIsNone(table.lookup("Γάζης", 0.95, 1))                 # a common noun: not the city
        res = greek.tag_chapter("exodus", 1, {11: "καὶ ἐπέστησεν αὐτοῖς ἐπιστάτας τῶν ἔργων, ἵνα κακώσωσιν αὐτοὺς ἐν "
                                                  "τοῖς ἔργοις· καὶ ᾠκοδόμησαν πόλεις ὀχυρὰς τῷ Φαραώ, τήν τε Πειθὼ "
                                                  "καὶ Ῥαμεσσὴ καὶ Ὤν, ἥ ἐστιν Ἡλίου πόλις."})[11]
        self.assertNotEqual(_tag_of(res, "Ὤν").lemma_key, "G1510")         # the city On, not ὤν 'being'

    def test_preverb_alone_is_no_stem_match(self) -> None:
        sim = greek.stem_similarity
        self.assertLess(sim("προσοισει", "προσχεω"), 0.78)        # Lev 3:9: προσφέρω, not προσχέω
        self.assertGreaterEqual(sim("προσεχεαν", "προσχεω"), 0.78)
        self.assertGreaterEqual(sim("προσχεουσιν", "προσχεω"), 0.78)

    def test_relative_is_not_the_article(self) -> None:
        excl = greek._context_exclusions
        self.assertEqual(excl(["ὃ", "συνέταξεν"])[0], {"G3588"})
        self.assertEqual(excl(["οἵ", "τε", "ἄνδρες"])[0], set())       # article before an enclitic
        self.assertEqual(excl(["ὁ", "θεός"])[0], set())
        res = greek.tag_chapter("exodus", 39, {22: "ὃ συνέταξεν Κύριος Μωσῇ, οὕτως ἐποίησαν οἱ υἱοὶ Ἰσραὴλ πᾶσαν "
                                                   "τὴν ἀποσκευὴν."})[22]
        self.assertNotEqual(res[0].lemma_key, "G3588")
        res = greek.tag_chapter("psalms", 77, {54: "καὶ εἰσήγαγεν αὐτοὺς εἰς ὄρος ἁγιάσματος αὐτοῦ, ὄρος τοῦτο ὃ"})[54]
        self.assertNotEqual(res[-1].lemma_key, "G3588")
        self.assertEqual(_tag_of(res, "καὶ").lemma_key, "G2532")

    def test_oath_particle_is_not_or(self) -> None:
        tg = self.tg
        self.assertFalse(tg.head_accents_agree("ἦ", "η"))          # ἦ 'truly' vs ἤ 'or'
        self.assertTrue(tg.head_accents_agree("ἢ", "η"))
        self.assertTrue(tg.head_accents_agree("Εσθηρ", "εσθηρ"))   # unaccented headwords never object
        for slug, ch, vs, text in (
                ("exodus", 22, 7, "ἐὰν δὲ μὴ εὑρεθῇ ὁ κλέψας, προσελεύσεται ὁ κύριος τῆς οἰκίας ἐνώπιον τοῦ θεοῦ καὶ "
                                  "ὀμεῖται, ἦ μὴν μὴ αὐτὸν πεπονηρεῦσθαι ἐφ᾽ ὅλης τῆς παρακαταθήκης τοῦ πλησίον."),
                ("job", 25, 5, "ἦ σελήνῃ συντάσσει, καὶ οὐκ ἐπιφαύσκει· ἄστρα δὲ οὐ καθαρὰ ἐναντίον αὐτοῦ.")):
            res = greek.tag_chapter(slug, ch, {vs: text})[vs]
            self.assertNotEqual(_tag_of(res, "ἦ").lemma_key, "G2228", slug)
        res = greek.tag_chapter("matthew", 5, {18: "ἀμὴν γὰρ λέγω ὑμῖν, ἕως ἂν παρέλθῃ ὁ οὐρανὸς καὶ ἡ γῆ, ἰῶτα ἓν ἢ "
                                                    "μία κεραία οὐ μὴ παρέλθῃ ἀπὸ τοῦ νόμου, ἕως ἂν πάντα γένηται."})[18]
        self.assertEqual(_tag_of(res, "ἢ").lemma_key, "G2228")

    def test_lamentations_acrostic_letters_stay_untagged(self) -> None:
        res = greek.tag_chapter("lamentations", 1, {
            5: "Ἥ. Ἐγένοντο οἱ θλίβοντες αὐτὴν εἰς κεφαλήν, καὶ οἱ ἐχθροὶ αὐτῆς εὐθηνοῦσαν, ὅτι Κύριος ἐταπείνωσεν "
               "ἐπὶ τὸ πλῆθος τῶν ἀσεβειῶν αὐτῆς· τὰ νήπια αὐτῆς ἐπορεύθησαν ἐν αἰχμαλωσίᾳ κατὰ πρόσωπον θλίβοντος.",
            13: "Μήμ. Ἐξ ὕψους αὐτοῦ ἀπέστειλεν πῦρ, ἐν τοῖς ὀστέοις μου κατήγαγεν αὐτό· διεπέτασεν δίκτυον τοῖς "
                "ποσίν μου, ἀπέστρεψέν με εἰς τὰ ὀπίσω, ἔδωκέν με ἠφανισμένην, ὅλην τὴν ἡμέραν ὀδυνωμένην."})
        for vs, letter in ((5, "Ἥ"), (13, "Μήμ")):
            t = res[vs][0]
            self.assertEqual((t.surface, t.lemma_key, t.method), (letter, None, "untagged"))
            self.assertIn("acrostic letter name", t.notes)
        self.assertEqual(_tag_of(res[5], "Ἐγένοντο").lemma_key, "G1096")
        self.assertEqual(_tag_of(res[5], "οἱ").lemma_key, "G3588")
        # outside Lamentations 1-4 the rule does not apply
        self.assertIsNone(greek._acrostic_letter("psalms", 1, "Ἥ. Ἐγένοντο", ["Ἥ", "Ἐγένοντο"]))

    def test_more_elided_forms(self) -> None:
        tg = self.tg
        self.assertEqual(tg.known_keys("ἵν᾽"), {"G2443"})          # ἵνα
        self.assertEqual(tg.known_keys("εἶθ᾽"), {"G1534"})         # εἶτα
        self.assertIn("G4218", tg.known_keys("ποτ᾽"))             # ποτέ

    def test_ot_homographs_not_decided_by_the_form_tables(self) -> None:
        cases = (
            ("isaiah", 2, 6, "ἀνῆκεν", "G0433",            # ἀνίημι, not ἀνήκω
             "ἀνῆκεν γὰρ τὸν λαὸν αὐτοῦ τὸν οἶκον τοῦ Ἰσραήλ· ὅτι ἐνεπλήσθη ὡς τὸ ἀπ᾽ ἀρχῆς ἡ χώρα αὐτῶν "
             "κληδονισμῶν, ὡς ἡ τῶν ἀλλοφύλων, καὶ τέκνα πολλὰ ἀλλόφυλα ἐγενήθη αὐτοῖς."),
            ("numbers", 11, 23, "γνώσει", "G1108",           # future of γινώσκω, not γνῶσις
             "καὶ εἶπεν Κύριος πρὸς Μωυσῆν Μὴ χεὶρ Κυρίου οὐκ ἐξαρκέσει; ἤδη γνώσει εἰ ἐπικαταλήμψεταί σε ὁ "
             "λόγος μου ἢ οὔ."),
            ("deuteronomy", 25, 2, "ἀσεβῶν", "G0765",        # participle of ἀσεβέω, not ἀσεβής
             "καὶ ἔσται ἐὰν ἄξιος ᾖ πληγῶν ὁ ἀσεβῶν, καθιεῖς αὐτὸν ἐναντίον αὐτῶν."),
            ("2-samuel", 20, 3, "ζῶσαι", "G2224",            # 'living' (ζάω), not ζώννυμι
             "Καὶ εἰσῆλθεν Δαυὶδ εἰς τὸν οἶκον αὐτοῦ εἰς Ἰερουσαλήμ· καὶ ἔλαβεν ὁ βασιλεὺς τὰς δέκα γυναῖκας τὰς "
             "παλλακὰς αὐτοῦ, ἃς ἀφῆκεν φυλάσσειν τὸν οἶκον, καὶ ἔδωκεν αὐτὰς ἐν οἴκῳ φυλακῆς, καὶ διέθρεψεν "
             "αὐτὰς καὶ πρὸς αὐτὰς οὐκ εἰσῆλθεν, καὶ ἦσαν συνεχόμεναι ἕως ἡμέρας θανάτου αὐτῶν, χῆραι ζῶσαι."),
        )
        for slug, ch, vs, word, wrong, text in cases:
            t = _tag_of(greek.tag_chapter(slug, ch, {vs: text})[vs], word)
            self.assertNotEqual(t.lemma_key, wrong, f"{slug} {ch}:{vs} {word}")
        # the LXX-convention pair εἶδεν (TAGNT εἴδω, the LXX files ὁράω) is linked, not a contradiction
        self.assertTrue(self.tg.linked("G1492", "G3708"))
        self.assertFalse(self.tg.linked("G1108", "G1097"))       # γνῶσις / γινώσκω
        self.assertFalse(self.tg.linked("G0433", "G0447"))       # ἀνήκω / ἀνίημι

    # -- licence hygiene ------------------------------------------------------------------------
    def test_no_non_commercial_source_is_read(self) -> None:
        src = Path(greek.__file__).read_text(encoding="utf-8")
        code = "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("#"))
        body = code.split('"""', 2)[-1]          # ignore the module docstring
        for banned in ("LXX_RAHLFS", ".local-nc-only", "05_Tier5", "PROIEL", "BHSA", "witness-cache"):
            self.assertNotIn(banned, body)
        row = next(iter(self.tg.lex.tbesg.rows.values()))
        self.assertEqual(set(row), {"estrong", "dstrong", "relation", "target", "head", "raw_head", "translit", "morph", "gloss"})

    def test_long_windows_paths_are_opened(self) -> None:
        p = "C:/" + "x" * 260 + "/file.txt"
        s = greek._fs(p)
        if os.name == "nt":
            self.assertTrue(s.startswith("\\\\?\\"))

    # -- regressions from the 18 Nov FINAL check (reader-facing families, glosses, POS) ----------
    def _fam(self, key: str) -> str:
        return self.lex[key].root_key

    @unittest.skipUnless(_AVAIL["strongs"], "Strong's Greek XML not present")
    def test_fanciful_strongs_derivations_do_not_join_families(self) -> None:
        f = self._fam
        apart = [
            ("G4198", "G3984"), ("G4198", "G3985"),       # πορεύομαι / πεῖρα, πειράζω (Acts 9:28)
            ("G0740", "G0142"), ("G0706", "G0142"),       # ἄρτος, ἀριθμός / αἴρω (Exo 16:8, Jhn 13:18)
            ("G5204", "G5205"),                           # ὕδωρ / ὑετός < ὕω (Gen 24:43)
            ("G4762", "G5157"), ("G0654", "G5157"),       # στρέφω, ἀποστρέφω / τροπή < τρέπω (Ezk 3:18)
            ("G3778", "G0846"), ("G3779", "G0846"),       # οὗτος, οὕτως / αὐτός
            ("G1218", "G1210"), ("G1163", "G1210"), ("G1189", "G1210"), ("G3530", "G1210"),  # δῆμος δεῖ δέομαι Νικόδημος / δέω
            ("G5119", "G5037"), ("G3842", "G5037"),       # τότε, πάντοτε / τε (Mat 7:23)
            ("G5602", "G1161"), ("G3592", "G1161"),       # ὧδε, ὅδε / δέ (Mat 16:28)
            ("G2276", "G2556"), ("G5501", "G2556"),       # ἥττων, χείρων / κακός (Job 20:10)
            ("G1640", "G3398"), ("G1646", "G3398"),       # ἐλάσσων, ἐλάχιστος / μικρός (Jhn 3:30)
            ("G5115", "G5088"),                           # τόξον / τίκτω (Num 24:8)
            ("G4645", "G4628"), ("G4663", "G4628"),       # σκληρύνω, σκώληξ / σκέλος (σκολιός: MorphGNT keeps it)
            ("G0444", "G0435"),                           # ἄνθρωπος / ἀνήρ (Ecc 3:19)
            ("G3709", "G3713"), ("G3710", "G3713"),       # ὀργή, ὀργίζω / ὀρέγω
            ("G3694", "G1855"),                           # ὀπίσω and ἔξωθεν: no family headed by '-θεν'
            ("G4073", "G4074"),                           # πέτρα / the name Πέτρος (Luke 8:13)
            ("G5181", "G2962"),                           # Τύραννος is not in the family of κύριος
            ("G4006", "G3958"),                           # πεποίθησις / πάσχω (Strong's G3958 slip)
            ("G3071", "G3073"),                           # Λυκαονία / Λυκία
            ("G0318", "G0043"), ("G0045", "G0043"),       # ἀνάγκη, ἄγκυρα / ἀγκάλη
            ("G0898", "G0899"), ("G5444", "G5443"),       # βαθμός / βάθος (Abbott-Smith: < βαίνω); φύλλον / φυλή
            ("G4109", "G4111"), ("G0736", "G0737"),       # πλάξ / πλάσσω; ἀρτέμων / ἄρτι (hand checks)
        ]
        for a, b in apart:
            self.assertNotEqual(f(a), f(b), (self.lex[a].lemma, self.lex[b].lemma, self.lex[a].formula))
        self.assertEqual(self.lex["G4012"].root_source, "self")                     # περί (Deu 9:20)
        self.assertEqual(self.lex["G0740"].root_source, "self")
        self.assertEqual(self.lex["G2447"].root_source, "self")                     # ἰός is not < ἵημι
        for key in ("G2355", "G2351"):                                               # θρῆνος, θόρυβος
            self.assertNotEqual(self.lex[key].root_label, "θρόος", key)
        for key in ("G3694", "G1855"):                                               # no suffix heads
            self.assertFalse(self.lex[key].root_label.startswith("-"), self.lex[key])
        self.assertNotIn("ἀλέκτωρ", self.lex["G0223"].formula)                    # Ἀλέξανδρος
        # real families stay together
        same = [("G1994", "G4762"), ("G0654", "G4762"),                             # ἐπι-, ἀπο-στρέφω < στρέφω
                ("G0649", "G4724"), ("G0652", "G0649"), ("G1992", "G1989"),          # ἀποστέλλω, ἀπόστολος, ἐπιστολή
                ("G1342", "G1349"), ("G1343", "G1342"),                              # δίκαιος, δικαιοσύνη < δίκη
                ("G5590", "G5594"), ("G4151", "G4154"),                              # ψυχή < ψύχω, πνεῦμα < πνέω
                ("G0080", "G0079"), ("G2038", "G2041"),                              # ἀδελφός/ἀδελφή, ἐργάζομαι/ἔργον
                ("G1162", "G1189"), ("G3056", "G3004"), ("G1577", "G2564"),          # δέησις < δέομαι
                ("G1607", "G4198"), ("G1531", "G4198"), ("G4059", "G4061"),          # ἐκ-, εἰσπορεύομαι; περιτέμνω/περιτομή
                ("G5456", "G5346"), ("G0225", "G0227"), ("G2288", "G2348"),          # φωνή/φημί, ἀλήθεια/ἀληθής, θάνατος/θνῄσκω
                ("G0863", "G0859")]                                                  # ἀφίημι / ἄφεσις
        for a, b in same:
            self.assertEqual(f(a), f(b), (self.lex[a].lemma, self.lex[a].formula, self.lex[b].lemma, self.lex[b].formula))
        self.assertEqual(self.lex["G4198"].root_label, "πόρος")                     # Abbott-Smith '< πόρος'
        self.assertEqual(self.lex["G4059"].root_label, "τέμνω")                     # not τομώτερος
        self.assertNotIn("ἀκριβέστατος", self.lex["G0199"].formula)                # ἀκριβῶς
        self.assertNotIn("ἱκανός", self.lex["G0864"].formula)                      # ἀφικνέομαι
        self.assertNotIn("πέραν", self.lex["G4044"].formula)                       # περιπείρω
        self.assertIn("διά", self.lex["G1311"].formula)                            # διαφθείρω: Strong's G1225 slip
        self.assertNotIn("διαβάλλω", self.lex["G1311"].formula)
        self.assertNotIn("σπαράσσω", self.lex["G4787"].formula)                    # συγκινέω: G4682 slip

    def test_family_policy_tests_of_visibility(self) -> None:
        vis = greek._family_visible
        self.assertTrue(vis("αποστελλω", ["απο"], ["στελλω"]))
        self.assertTrue(vis("αποστολοσ", [], ["αποστελλω"]))           # ε/ο grade
        self.assertTrue(vis("αφιημι", ["απο"], ["ιημι"]))              # short stem: the word itself
        self.assertTrue(vis("συναγω", ["συν"], ["αγω"]))
        self.assertTrue(vis("φιλαδελφοσ", [], ["φιλοσ", "αδελφοσ"]))
        self.assertFalse(vis("αρτοσ", [], ["αιρω"]))
        self.assertFalse(vis("πορευομαι", [], ["πειρα"]))
        self.assertFalse(vis("στρεφω", [], ["τρεπω"]))
        self.assertFalse(vis("ουτοσ", [], ["ο", "αυτοσ"]))
        self.assertFalse(vis("δημοσ", [], ["δεω"]))
        self.assertFalse(vis("αγωγη", [], ["αγω"]))                     # short stem, not the word itself
        self.assertFalse(vis("δεξιοσ", [], ["δεχομαι"]))                # no consonant change on a 3-letter stem
        self.assertFalse(vis("τοξον", [], ["τικτω"]))

    def test_family_meaning_is_the_heads_own(self) -> None:
        lex = self.lex
        lx = self.tg.lex
        # every family's meaning is the head's meaning, the same for every member, never empty
        by_root = {}
        for key, e in lex.items():
            if e.gloss or e.root_source != "self":   # an unglossed LXX word (Κίτιοι) has no meaning to give
                self.assertTrue(e.root_gloss, (key, e.lemma, e.root_label))
            by_root.setdefault(e.root_key, set()).add(e.root_gloss)
        self.assertEqual([r for r, g in by_root.items() if len(g) > 1], [])
        for key, e in lex.items():
            head = e.root_key[4:]
            head = head if head in lex else e.root_key
            if head in lex:
                self.assertEqual(e.root_gloss, lx.root_meaning(head), key)
        # the checker's examples: a member's gloss is no longer the family meaning
        cases = {"G2041": ("to work", "to minister"),        # ἔργον < ἔργω (Num 4:3)
                 "G0080": ("womb", "sister"),                 # ἀδελφός < δελφύς
                 "G0863": ("to send", "understanding"),       # ἀφίημι < ἵημι (Mrk 15:37)
                 "G2962": ("suprem", "lord"),                 # κύριος < κῦρος 'supremacy' (Strong's)
                 "G0649": ("to set", "to avoid"),             # ἀποστέλλω < στέλλω
                 "G1342": ("justice", "condemnation"),        # δίκαιος < δίκη
                 "G5590": ("to breathe", "to cool"),          # ψυχή < ψύχω
                 "G2330": ("to heat", "to reap")}             # θέρος < θέρω
        for key, (want, never) in cases.items():
            self.assertIn(want, lex[key].root_gloss, (key, lex[key].root_label, lex[key].root_gloss))
            self.assertNotIn(never, lex[key].root_gloss)
        for key in ("G2068", "G0833", "G0417", "G2523", "G4892"):    # ἐσθίω αὐλή ἄνεμος καθίζω συνέδριον
            self.assertNotIn(lex[key].root_label, ("ἔδω", "ἄημι", "ἕδρα"), key)
        self.assertNotIn("buttock", lex["G1747"].root_gloss)          # ἐνέδρα < ἑδραῖος < ἕδρα 'seat'
        # labels without vowel-length marks (κόλλᾰ, ὕψῐ, ῥᾰπίς)
        for e in lex.values():
            self.assertNotIn("̆", unicodedata.normalize("NFD", e.root_label), e)
            self.assertNotIn("̄", unicodedata.normalize("NFD", e.root_label), e)

    def test_glosses_are_english_and_general(self) -> None:
        lex = self.lex
        g = lambda k: lex[k].gloss  # noqa: E731
        # STEP sense-suffix glosses give their general part
        self.assertEqual(g("G2962"), "lord")
        self.assertEqual(g("G4160"), "to do/make")
        self.assertEqual(g("G0906"), "to throw")
        self.assertEqual(g("G3708"), "to see")
        self.assertEqual(g("G2787"), "ark")                  # Noah's ark too (Gen 6:14)
        self.assertEqual(g("G1093"), "earth")
        self.assertIn("Hades", g("G0086"))
        bad = [(k, e.gloss) for k, e in lex.items() if re.search(r"[a-z]: [A-Za-z]", e.gloss or "")]
        self.assertEqual(bad, [])
        self.assertIn("know", g("G1492"))                   # εἴδω also files οἶδα 'to know'
        self.assertIn("become", g("G1096"))                 # γίνομαι
        self.assertIn("nation", g("G1484"))                 # ἔθνος: 845 LXX 'nations'
        self.assertIn("Joshua", g("G2424"))                 # Ἰησοῦς (1Ch 24:11)
        self.assertIn("Judah", g("G2455"))
        self.assertIn("Miriam", g("G3137"))                 # Exo 15:20
        self.assertIn("anointed", g("G5547"))               # 1Sa 2:10
        self.assertIn("olive", g("G1638"))                  # 1Sa 8:14 olive groves
        self.assertEqual(g("G2117"), "straight")            # not 'Straight'
        # Septuagint words that showed the Greek headword as their gloss
        lx = self.tg.lex
        for gk in ("περισποριον", "θυμιαζω", "πρωτογενημα", "ροα", "μιτρα", "αιλαμ.1", "μεχωνωθ", "ιν"):
            key = lx.gwl_lemma_key(gk)
            self.assertIn(key, lex, gk)
            self.assertRegex(lex[key].gloss, r"[A-Za-z]", (gk, key))
        # no non-name entry shows Greek letters as its gloss
        greekish = [k for k, e in lex.items() if e.gloss and re.search(r"[Ͱ-Ͽἀ-῿]", e.gloss)]
        self.assertEqual(greekish, [])

    def test_lxx_common_nouns_are_not_nt_names(self) -> None:
        lx = self.tg.lex
        for gk, name in (("τυραννος.1", "G5181"), ("δορκας.1", "G1393"), ("χλοη.1", "G5514"),
                         ("ευοδια.1", "G2136"), ("ρωμη", "G4516"), ("πετρος.1", "G4074"),
                         ("λιβανος", "G3030"), ("ποντος.1", "G4195")):
            self.assertNotEqual(lx.gwl_lemma_key(gk), name, gk)
        self.assertEqual(lx.gwl_lemma_key("σαββατιζω"), "G9043")          # a verb is never a name
        checks = [
            ("deuteronomy", 12, 15, "ἀλλ᾽ ἢ ἐν πάσῃ ἐπιθυμίᾳ σου θύσεις καὶ φάγῃ κρέα κατὰ τὴν εὐλογίαν Κυρίου τοῦ θεοῦ σου "
             "ἣν ἔδωκέν σοι ἐν πάσῃ πόλει· ὁ ἀκάθαρτος ἐν σοὶ καὶ ὁ καθαρὸς ἐπὶ τὸ αὐτό φάγεται αὐτό, ὡς δορκάδα ἤ ἔλαφον·",
             "δορκάδα", "G1393"),
            ("psalms", 22, 2, "εἰς τόπον χλόης, ἐκεῖ με κατεσκήνωσεν· ἐπὶ ὕδατος ἀναπαύσεως ἐξέθρεψέν με·", "χλόης", "G5514"),
            ("habakkuk", 1, 10, "καὶ αὐτὸς ἐν βασιλεῦσιν ἐντρυφήσει καὶ τύραννοι παίγνια αὐτοῦ, καὶ αὐτὸς εἰς πᾶν ὀχύρωμα "
             "ἐμπαίξεται, καὶ βαλεῖ χῶμα καὶ κρατήσει αὐτοῦ.", "τύραννοι", "G5181"),
        ]
        for slug, ch, vs, text, word, name in checks:
            t = _tag_of(greek.tag_chapter(slug, ch, {vs: text})[vs], word)
            self.assertNotEqual(t.lemma_key, name, (slug, ch, vs, word))
            if t.lemma_key:
                self.assertNotEqual(self.lex[t.lemma_key].pos, "PROPN", (word, t.lemma_key))
        t = _tag_of(greek.tag_chapter("psalms", 22, {2: checks[1][3]})[2], "χλόης")
        self.assertEqual(t.lemma_key, lx.gwl_lemma_key("χλοη.1"))         # grass, not untagged
        # Luke 21:5: TAGNT tags ἀναθήμασιν G0334 ἀνάθημα but names 'ἀνάθεμα' as dictionary form
        res = greek.tag_chapter("luke", 21, {5: "Καί τινων λεγόντων περὶ τοῦ ἱεροῦ, ὅτι λίθοις καλοῖς καὶ "
                                                "ἀναθήμασιν κεκόσμηται εἶπεν·"})[5]
        self.assertEqual(_tag_of(res, "ἀναθήμασιν").lemma_key, "G0334")

    def test_part_of_speech_fixes(self) -> None:
        lx = self.tg.lex
        lex = self.lex
        self.assertEqual(lex[lx.gwl_lemma_key("ιωναθαν")].pos, "PROPN")    # 1Ma 11:29, not NUM
        self.assertEqual(lex[lx.gwl_lemma_key("ιαβιν")].pos, "PROPN")
        for gk in ("κοιλας", "λοβος", "ναβλα", "οιφι", "τηγανον"):         # TBESG lower-case 'N:' words
            self.assertEqual(lex[lx.gwl_lemma_key(gk)].pos, "N", gk)
        self.assertEqual(lex["G1638"].pos, "N")                               # ἐλαιών
        self.assertEqual(lex[lx.gwl_lemma_key("περικυκλω")].pos, "ADV")      # περικύκλῳ
        self.assertEqual(lex[lx.gwl_lemma_key("ραψακης")].pos, "PROPN")      # the list's 'N' names (R section)

    def test_pronouns_are_not_content(self) -> None:
        lx = self.tg.lex
        for key in ("G3778", "G5101", "G5100", "G1565", "G1438", "G3745", "G3592", "G4572", "G1699",
                    "G0240", "G4674", "G5108", "G4169", "G4214", "G1683", "G2251"):
            self.assertEqual(lx.pos(key), "PRON", key)
            self.assertFalse(lx.is_content(key), key)
            self.assertTrue(self.tg.is_closed_class(key), key)              # the tagger's view is unchanged
        res = greek.tag_chapter("john", 4, {34: "λέγει αὐτοῖς ὁ Ἰησοῦς· Ἐμὸν βρῶμά ἐστιν ἵνα ποιήσω τὸ θέλημα "
                                                "τοῦ πέμψαντός με καὶ τελειώσω αὐτοῦ τὸ ἔργον."})[34]
        self.assertFalse(_tag_of(res, "Ἐμὸν").is_content)
        self.assertTrue(_tag_of(res, "βρῶμά").is_content)
        for key in ("G1722", "G2316", "G1451"):                               # prepositions, nouns stay content
            self.assertTrue(lx.is_content(key), key)

    def test_linked_keeps_the_permissive_walk(self) -> None:
        # GreekTagger.linked() (tagging) still sees the old chains; readers see the strict ones
        lx = self.tg.lex
        self.assertEqual(lx.root_of("G4198", strict=False)[0], lx.root_of("G3985", strict=False)[0])
        self.assertNotEqual(lx.root_of("G4198")[0], lx.root_of("G3985")[0])
        self.assertTrue(self.tg.linked("G3403", "G3415"))                    # μιμνήσκω / μνάομαι


@unittest.skipUnless(_CORE, "Greek gold corpora (TAGNT, TBESG, LxxLemmas, Greek Word List) not present")
class TestGreekParsing(unittest.TestCase):
    """TokenTag.morph / .src: the TAGNT parse of the aligned word (NT), None in the Septuagint."""

    @classmethod
    def setUpClass(cls) -> None:
        greek.AUTO_PREPARE = False
        cls.tg = greek.get_tagger()

    def _verse(self, slug: str, ch: int, vs: int, text: str):
        return greek.tag_chapter(slug, ch, {vs: text})[vs]

    def test_nt_tokens_carry_the_tagnt_parse_and_word_id(self) -> None:
        res = self._verse("john", 1, 1, "Ἐν ἀρχῇ ἦν ὁ λόγος, καὶ ὁ λόγος ἦν πρὸς τὸν θεόν, καὶ θεὸς ἦν ὁ λόγος.")
        self.assertEqual([t.morph for t in res[:5]], ["R:PREP", "R:N-DSF", "R:V-IAI-3S", "R:T-NSM", "R:N-NSM"])
        self.assertEqual([t.src for t in res[:3]], ["tagnt:Jhn.1.1#01", "tagnt:Jhn.1.1#02", "tagnt:Jhn.1.1#03"])
        self.assertEqual(_tag_of(res, "θεὸς").morph, "R:N-NSM-T")
        res = self._verse("matthew", 1, 1, "Βίβλος γενέσεως Ἰησοῦ χριστοῦ υἱοῦ Δαυὶδ υἱοῦ Ἀβραάμ.")
        self.assertEqual((res[0].morph, res[0].src), ("R:N-NSF", "tagnt:Mat.1.1#01"))
        self.assertEqual((res[2].morph, res[2].src), ("R:N-GSM-P", "tagnt:Mat.1.1#03"))
        for t in res:
            self.assertEqual(t.method, "gold-aligned")
            self.assertEqual(t.notes, [f"TAGNT {t.src[len('tagnt:'):]}"])     # src and the note agree

    def test_crasis_joins_the_parses(self) -> None:
        res = self._verse("matthew", 2, 8, "καὶ πέμψας αὐτοὺς εἰς Βηθλέεμ εἶπεν· Πορευθέντες ἐξετάσατε ἀκριβῶς περὶ "
                          "τοῦ παιδίου· ἐπὰν δὲ εὕρητε, ἀπαγγείλατέ μοι, ὅπως κἀγὼ ἐλθὼν προσκυνήσω αὐτῷ.")
        t = _tag_of(res, "κἀγὼ")
        self.assertEqual((t.morph, t.src), ("R:P-1NS+CONJ", "tagnt:Mat.2.8#19"))
        self.assertEqual(greek._tag_parse("G1473=P-1NS + G2532=CONJ"), "P-1NS+CONJ")
        self.assertEqual(greek._tag_parse("G0746=N-DSF"), "N-DSF")
        self.assertIsNone(greek._tag_parse("G0746"))

    def test_another_editions_word_has_its_own_parse(self) -> None:
        # NA28 prints υἱὸς (N-NSM) at Mat 9:27; the Studio's υἱὲ is the TR/Byz word, vocative
        res = self._verse("matthew", 9, 27, "Καὶ παράγοντι ἐκεῖθεν τῷ Ἰησοῦ ἠκολούθησαν αὐτῷ δύο τυφλοὶ κράζοντες "
                          "καὶ λέγοντες· Ἐλέησον ἡμᾶς, υἱὲ Δαυίδ.")
        t = _tag_of(res, "υἱὲ")
        self.assertEqual((t.morph, t.src), ("R:N-VSM", "tagnt:Mat.9.27#15"))
        w = next(w for w in self.tg.nt.verses[("matthew", 9, 27)] if w.ref == "Mat.9.27#15")
        self.assertEqual(w.parse, "N-NSM")                                    # the printed word's own

    def test_spelling_that_is_another_word_has_no_parse(self) -> None:
        # Mark 3:4: ἀγαθοποιῆσαι is listed as a 'spelling' of ποιῆσαι but is another word
        res = self._verse("mark", 3, 4, "καὶ λέγει αὐτοῖς· Ἔξεστιν τοῖς σάββασιν ἀγαθοποιῆσαι ἢ κακοποιῆσαι, ψυχὴν "
                          "σῶσαι ἢ ἀποκτεῖναι; οἱ δὲ ἐσιώπων.")
        t = _tag_of(res, "ἀγαθοποιῆσαι")
        self.assertEqual(t.lemma_key, "G0015")
        self.assertIsNone(t.morph)
        self.assertEqual(t.src, "tagnt:Mrk.3.4#08")
        self.assertEqual(_tag_of(res, "κακοποιῆσαι").morph, "R:V-AAN")

    def test_form_table_and_untagged_tokens_have_no_parse(self) -> None:
        res = self._verse("matthew", 1, 99, "λόγου ζζζ")                      # no TAGNT words for 1:99
        self.assertEqual((res[0].method, res[0].lemma_key, res[0].morph, res[0].src), ("gold-form", "G3056", None, None))
        self.assertEqual((res[1].method, res[1].morph, res[1].src), ("untagged", None, None))

    def test_septuagint_has_no_parse(self) -> None:
        res = self._verse("genesis", 1, 1, "Ἐν ἀρχῇ ἐποίησεν ὁ θεὸς τὸν οὐρανὸν καὶ τὴν γῆν.")
        self.assertTrue(all(t.lemma_key for t in res))
        self.assertEqual({(t.morph, t.src) for t in res}, {(None, None)})

    @unittest.skipUnless(greek._tegmc_file() is not None, "STEPBible TEGMC not present")
    def test_morph_legend(self) -> None:
        leg = greek.morph_legend(["R:N-DSF", "V-AAI-3S", "R:P-1NS+CONJ", "R:PRT-N", "R:NOT-A-CODE", ""])
        self.assertEqual(leg, {
            "R:N-DSF": "Noun Dative Singular Feminine",
            "R:P-1NS+CONJ": "Personal pronoun 1st Nominative Singular + Conjunction",
            "R:PRT-N": "Negative Particle Negative",                     # TEGMC repeats 'Negative'
            "R:V-AAI-3S": "Verb Aorist Active Indicative 3rd Singular",
        })
        full = greek.morph_legend()                                       # every parse TAGNT can give
        self.assertGreater(len(full), 1100)
        for code, text in full.items():
            self.assertTrue(code.startswith("R:"), code)
            self.assertTrue(text and text == text.strip() and '"' not in text, code)
        used = set()
        for words in self.tg.nt.verses.values():
            for w in words:
                used.update(f"R:{p}" for p in w.morphs.values() if p)
        self.assertEqual(used - set(full), set())                         # no code without a legend
        # every code a chapter emits is described
        res = greek.tag_chapter("john", 1, {1: "Ἐν ἀρχῇ ἦν ὁ λόγος, καὶ ὁ λόγος ἦν πρὸς τὸν θεόν, καὶ θεὸς ἦν ὁ λόγος."})
        self.assertTrue({t.morph for t in res[1]} <= set(full))


# A small Greek OT corpus in the Studio's schema (real Studio verses, 18 Nov 2026) for the LXX-wide
# form table: call-order independence and what the first pass may feed back.
_FIXTURE_VERSES = {
    ("genesis", 1): {
        1: "Ἐν ἀρχῇ ἐποίησεν ὁ θεὸς τὸν οὐρανὸν καὶ τὴν γῆν.",
        2: "ἡ δὲ γῆ ἦν ἀόρατος καὶ ἀκατασκεύαστος, καὶ σκότος ἐπάνω τῆς ἀβύσσου· καὶ πνεῦμα θεοῦ ἐπεφέρετο ἐπάνω τοῦ ὕδατος.",
    },
    ("leviticus", 3): {
        8: "καὶ ἐπιθήσει τὰς χεῖρας ἐπὶ τὴν κεφαλὴν τοῦ δώρου αὐτοῦ, καὶ σφάξει αὐτὸ παρὰ τὰς θύρας τῆς σκηνῆς τοῦ "
           "μαρτυρίου· καὶ προσχεοῦσιν οἱ υἱοὶ Ἀαρὼν οἱ ἱερεῖς τὸ αἷμα ἐπὶ τὸ θυσιαστήριον κύκλῳ·",
        9: "καὶ προσοίσει ἀπὸ τῆς θυσίας τοῦ σωτηρίου κάρπωμα τῷ θεῷ, τὸ στέαρ καὶ τὴν ὀσφὺν ἄμωμον· σὺν ταῖς ψόαις "
           "περιελεῖ αὐτό· καὶ τὸ στέαρ τῆς κοιλίας,",
    },
    ("numbers", 30): {
        3: "ἄνθρωπος ἄνθρωπος ὃς ἂν εὔξηται εὐχὴν Κυρίῳ ἢ ὀμόσῃ ὅρκον ὁρισμῷ ἢ ὁρίσηται περὶ τῆς ψυχῆς αὐτοῦ, οὐ "
           "βεβηλώσει τὸ ῥῆμα αὐτοῦ· πάντα ὅσα ἐὰν ἐξέλθῃ ἐκ τοῦ στόματος αὐτοῦ ποιήσει.",
    },
    ("exodus", 22): {
        7: "ἐὰν δὲ μὴ εὑρεθῇ ὁ κλέψας, προσελεύσεται ὁ κύριος τῆς οἰκίας ἐνώπιον τοῦ θεοῦ καὶ ὀμεῖται, ἦ μὴν μὴ "
           "αὐτὸν πεπονηρεῦσθαι ἐφ᾽ ὅλης τῆς παρακαταθήκης τοῦ πλησίον.",
    },
    ("matthew", 5): {
        18: "ἀμὴν γὰρ λέγω ὑμῖν, ἕως ἂν παρέλθῃ ὁ οὐρανὸς καὶ ἡ γῆ, ἰῶτα ἓν ἢ μία κεραία οὐ μὴ παρέλθῃ ἀπὸ τοῦ "
            "νόμου, ἕως ἂν πάντα γένηται.",
    },
}


def _fixture_db(folder: str) -> Path:
    path = Path(folder) / "greek_fixture.db"
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE chapters (id INTEGER PRIMARY KEY, language TEXT, book_slug TEXT, chapter INTEGER)")
    conn.execute("CREATE TABLE verses (id INTEGER PRIMARY KEY, chapter_id INTEGER, verse INTEGER, critical_text TEXT)")
    for n, ((slug, ch), verses) in enumerate(_FIXTURE_VERSES.items(), 1):
        conn.execute("INSERT INTO chapters VALUES (?, 'greek', ?, ?)", (n, slug, ch))
        for vs, text in verses.items():
            conn.execute("INSERT INTO verses (chapter_id, verse, critical_text) VALUES (?, ?, ?)", (n, vs, text))
    conn.commit()
    conn.close()
    return path


def _sig(res):
    return {vs: [(t.surface, t.lemma_key, t.method, t.confidence, tuple(t.notes)) for t in tags] for vs, tags in res.items()}


@unittest.skipUnless(_CORE, "Greek gold corpora (TAGNT, TBESG, LxxLemmas, Greek Word List) not present")
class TestGreekFormTablePreparation(unittest.TestCase):
    """The LXX-wide form table is fixed once per process; tags never depend on call order."""

    @classmethod
    def setUpClass(cls) -> None:
        import tempfile
        cls.tmp = tempfile.mkdtemp(prefix="greek_lexica_")
        cls.db = _fixture_db(cls.tmp)
        cls.tg = greek.get_tagger()

    @classmethod
    def tearDownClass(cls) -> None:
        import shutil
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self) -> None:
        tg = self.tg
        self._saved = (tg.lxx_table, tg._lxx_dict_ready, greek._studio_db_path, greek.AUTO_PREPARE)
        greek._studio_db_path = lambda: self.db         # the fixture stands in for data/studio.db
        greek.AUTO_PREPARE = True

    def tearDown(self) -> None:
        table, ready, greek._studio_db_path, greek.AUTO_PREPARE = self._saved
        self.tg._set_lxx_table(table, ready)

    def _reset(self) -> None:
        self.tg._set_lxx_table(greek._FormTable(), False)

    def test_tags_do_not_depend_on_call_order(self) -> None:
        verses = _FIXTURE_VERSES[("numbers", 30)]
        self._reset()
        first = _sig(greek.tag_chapter("numbers", 30, verses))        # builds the table itself
        self.assertTrue(self.tg._lxx_dict_ready)
        self.assertGreater(len(self.tg.lxx_table), 0)
        conn = sqlite3.connect(f"file:{self.db.as_posix()}?mode=ro", uri=True)
        try:
            self._reset()
            greek.prepare(conn)
            self.assertEqual(_sig(greek.tag_chapter("numbers", 30, verses)), first)
            self._reset()
            via_all = {(s, c): r for s, c, r in greek.tag_all(conn)}
            self.assertEqual(_sig(via_all[("numbers", 30)]), first)
            # once built, the table stays: prepare() again changes nothing
            greek.prepare()
            greek.prepare(conn)
            self.assertEqual(_sig(greek.tag_chapter("numbers", 30, verses)), first)
            # an NT chapter first does not fix an OT table
            self._reset()
            greek.tag_chapter("matthew", 5, _FIXTURE_VERSES[("matthew", 5)])
            self.assertFalse(self.tg._lxx_dict_ready)
            self.assertEqual(_sig(greek.tag_chapter("numbers", 30, verses)), first)
        finally:
            conn.close()

    def test_auto_prepare_off_still_fixes_one_table(self) -> None:
        greek.AUTO_PREPARE = False
        self._reset()
        verses = _FIXTURE_VERSES[("numbers", 30)]
        a = _sig(greek.tag_chapter("numbers", 30, verses))
        self.assertTrue(self.tg._lxx_dict_ready)
        self.assertEqual(len(self.tg.lxx_table), 0)
        conn = sqlite3.connect(f"file:{self.db.as_posix()}?mode=ro", uri=True)
        try:
            list(greek.tag_all(conn))                           # does not rebuild a fixed table
        finally:
            conn.close()
        self.assertEqual(_sig(greek.tag_chapter("numbers", 30, verses)), a)

    def test_first_pass_pairings_are_not_promoted(self) -> None:
        self._reset()
        greek.prepare()
        tg = self.tg
        table = tg.lxx_table
        self.assertNotIn("G8947", table.candidates("προσοίσει"))    # προσχέω (preverb-only match)
        self.assertNotIn("G2228", table.candidates("ἦ"))            # ἦ μήν is not ἤ
        self.assertIn("G0746", table.candidates("ἀρχῇ"))
        # Num 30:3 ὁρίσηται was paired with ὁρισμός by stem alone (0.88); a second-pass pairing
        # that rests on that table entry keeps 0.88 instead of the 0.98 of a TAGNT-attested form
        self.assertEqual(table.best_conf("ὁρίσηται", "G8547"), 0.88)
        self.assertEqual(tg.lxx_form_confidence("ὁρίσηται", "G8547"), 0.88)
        res = greek.tag_chapter("numbers", 30, _FIXTURE_VERSES[("numbers", 30)])[3]
        t = _tag_of(res, "ὁρίσηται")
        self.assertLessEqual(t.confidence, 0.88)
        for tags in greek.tag_chapter("leviticus", 3, _FIXTURE_VERSES[("leviticus", 3)]).values():
            for t in tags:
                if any("(LXX form)" in n for n in t.notes):
                    self.assertLessEqual(t.confidence, 0.93)


@unittest.skipUnless(_CORE and _LIVE_DB.exists(), "live Studio database or Greek corpora not present")
class TestGreekTaggerOnLiveText(unittest.TestCase):
    """Reads the real studio.db strictly read-only (mode=ro)."""

    @classmethod
    def setUpClass(cls) -> None:
        greek.AUTO_PREPARE = False
        cls.conn = sqlite3.connect(f"file:{_LIVE_DB.as_posix()}?mode=ro", uri=True)
        cls.tg = greek.get_tagger()
        cls.lex = greek.load_lexicon()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.conn.close()

    def _chapter(self, slug: str, ch: int):
        rows = self.conn.execute(
            "SELECT v.verse, v.critical_text FROM verses v JOIN chapters c ON c.id = v.chapter_id "
            "WHERE c.language = 'greek' AND c.book_slug = ? AND c.chapter = ?", (slug, ch)).fetchall()
        if not rows:
            self.skipTest(f"{slug} {ch} not in the database")
        return {int(v): t for v, t in rows}

    def test_live_chapters_tag_rates(self) -> None:
        for slug, ch, floor in (("john", 1, 0.99), ("romans", 16, 0.99), ("psalms", 1, 0.95),
                                ("genesis", 22, 0.95), ("esther", 1, 0.93), ("daniel", 3, 0.95), ("sirach", 1, 0.9)):
            verses = self._chapter(slug, ch)
            res = greek.tag_chapter(slug, ch, verses)
            tags = [t for vs in res.values() for t in vs]
            n = sum(len(tokenize_verse(t, "grc")) for t in verses.values())
            self.assertEqual(len(tags), n)
            rate = sum(1 for t in tags if t.lemma_key) / max(1, n)
            self.assertGreaterEqual(rate, floor, f"{slug} {ch}: {rate:.3f}")
            for t in tags:
                if t.lemma_key:
                    self.assertIn(t.lemma_key, self.lex)

    def test_live_nt_parsing_coverage(self) -> None:
        legend = greek.morph_legend() if greek._tegmc_file() is not None else None
        for slug, ch in (("john", 1), ("romans", 16), ("revelation", 22)):
            res = greek.tag_chapter(slug, ch, self._chapter(slug, ch))
            tags = [t for vs in res.values() for t in vs]
            aligned = [t for t in tags if t.method == "gold-aligned"]
            with_morph = [t for t in aligned if t.morph]
            self.assertGreaterEqual(len(with_morph) / max(1, len(aligned)), 0.995, f"{slug} {ch}")
            for t in tags:
                if t.method == "gold-aligned":
                    self.assertTrue(t.src and t.src.startswith("tagnt:"), (slug, ch, t.surface))
                    self.assertEqual(t.notes[0].split(" ")[1], t.src[len("tagnt:"):])
                else:
                    self.assertIsNone(t.morph)
                if t.morph:
                    self.assertRegex(t.morph, r"^R:[A-Z0-9]+(-[A-Z0-9]+)*(\+[A-Z0-9]+(-[A-Z0-9]+)*)*$")
                    if legend is not None:
                        self.assertIn(t.morph, legend)
        res = greek.tag_chapter("psalms", 1, self._chapter("psalms", 1))
        self.assertEqual({t.morph for vs in res.values() for t in vs}, {None})


@unittest.skipUnless(_CORE, "Greek gold corpora (TAGNT, TBESG, LxxLemmas, Greek Word List) not present")
class TestUntaggedResolutionFixes(unittest.TestCase):
    """Regressions for the 19 Nov 2026 Greek untagged-token pass (NT detached/compound/split, LXX stems/augments)."""

    @classmethod
    def setUpClass(cls) -> None:
        greek.AUTO_PREPARE = False
        cls.tg = greek.get_tagger()

    def test_nt_detached_variants_and_compounds(self) -> None:
        res = greek.tag_chapter("acts", 21, {15: "Μετὰ δὲ τὰς ἡμέρας ταύτας ἐπισκευασάμενοι ἀνεβαίνομεν εἰς Ἱεροσόλυμα·"})[15]
        t = _tag_of(res, "ἐπισκευασάμενοι")
        self.assertEqual(t.lemma_key, "G7447")
        self.assertEqual(t.morph, "R:V-ADP-NPM")

        res = greek.tag_chapter("luke", 16, {21: "καὶ ἐπιθυμῶν χορτασθῆναι ἀπὸ τῶν πιπτόντων ἀπὸ τῆς τραπέζης τοῦ πλουσίου· ἀλλὰ καὶ οἱ κύνες ἐρχόμενοι ἐπέλειχον τὰ ἕλκη αὐτοῦ."})[21]
        t = _tag_of(res, "ἐπέλειχον")
        self.assertEqual(t.lemma_key, "grc:ἐπιλείχω")
        self.assertEqual(t.morph, "R:V-IAI-3P")

        res = greek.tag_chapter("1-thessalonians", 3, {10: "νυκτὸς καὶ ἡμέρας ὑπερεκπερισσοῦ δεόμενοι εἰς τὸ ἰδεῖν ὑμῶν τὸ πρόσωπον καὶ καταρτίσαι τὰ ὑστερήματα τῆς πίστεως ὑμῶν;"})[10]
        self.assertEqual(_tag_of(res, "ὑπερεκπερισσοῦ").lemma_key, "G6087")

        res = greek.tag_chapter("1-corinthians", 16, {22: "εἴ τις οὐ φιλεῖ τὸν κύριον, ἤτω ἀνάθεμα. Μαράνα θά."})[22]
        self.assertEqual(_tag_of(res, "Μαράνα").lemma_key, "G3134")
        self.assertEqual(_tag_of(res, "θά").lemma_key, "G3134")

    def test_lxx_stems_and_temporal_augments(self) -> None:
        self.assertIn("οικισεν", greek._strip_augment("ωκισεν", "οικιζω"))
        self.assertIn("κραξαν", greek._strip_augment("εκεκραξαν", "κραζω"))
        self.assertIn("φαγ", greek._compute_stems("εσθιω"))
        self.assertIn("οισ", greek._compute_stems("φερω"))

    def test_nt_joined_enclitic_mege(self) -> None:
        res = greek.tag_chapter("matthew", 6, {1: "Προσέχετε δὲ τὴν δικαιοσύνην ὑμῶν μὴ ποιεῖν ἔμπροσθεν τῶν "
                                                  "ἀνθρώπων πρὸς τὸ θεαθῆναι αὐτοῖς· εἰ δὲ μήγε, μισθὸν οὐκ ἔχετε "
                                                  "παρὰ τῷ πατρὶ ὑμῶν τῷ ἐν τοῖς οὐρανοῖς."})[1]
        t = _tag_of(res, "μήγε")
        self.assertEqual(t.lemma_key, "G3361")
        self.assertEqual(t.morph, "R:PRT-N")

    def test_lxx_numerals_word_order_ortho_and_compounds(self) -> None:
        # Milesian alphabetic numerals
        self.assertEqual(greek._milesian_numeral_key("μ᾽"), "G5062")
        self.assertEqual(greek._milesian_numeral_key("ιβ᾽"), "G1427")
        self.assertIsNone(greek._milesian_numeral_key("δ᾽"))       # elided δέ, never numeral
        # Elided α-initial compound verb & double augment
        self.assertGreaterEqual(greek.stem_similarity("διηρπασεν", "διαρπαζω"), 0.85)
        self.assertGreaterEqual(greek.stem_similarity("εσυνεθετο", "συντιθημι"), 0.78)
        # Swapped word order in same verse (Hos 6:2 ἀναστησόμεθα, Isa 13:16 ῥάξουσιν)
        res = greek.tag_chapter("hosea", 6, {2: "ὑγιάσει ἡμᾶς μετὰ δύο ἡμέρας· ἐν τῇ ἡμέρᾳ τῇ τρίτῃ καὶ ἀναστησόμεθα,"})[2]
        self.assertEqual(_tag_of(res, "ἀναστησόμεθα").lemma_key, "G0450")
        res = greek.tag_chapter("isaiah", 13, {16: "καὶ τὰ τέκνα αὐτῶν ῥάξουσιν ἐνώπιον αὐτῶν, καὶ τὰς οἰκίας αὐτῶν "
                                                   "προνομεύσουσιν, καὶ τὰς γυναῖκας αὐτῶν ἕξουσιν."})[16]
        self.assertEqual(_tag_of(res, "ῥάξουσιν").lemma_key, "G9015")
        # 1-to-1 gap homograph (1 Sam 28:2 γνώσει -> γινώσκω, Mal 3:2 ποία -> πόα) & closed forms (Ezra 5:3 τοῖα)
        res = greek.tag_chapter("1-samuel", 28, {2: "καὶ εἶπεν Δαυὶδ πρὸς Ἀγχούς Οὕτω νῦν γνώσει ἃ ποιήσει ὁ δοῦλός σου·"})[2]
        self.assertEqual(_tag_of(res, "γνώσει").lemma_key, "G1097")
        res = greek.tag_chapter("ezra", 5, {3: "ἐν αὐτῷ τῷ καιρῷ ἦλθεν ἐπ᾽ αὐτοὺς Θαναναὶ ἔπαρχος πέραν τοῦ ποταμοῦ "
                                               "καὶ Σαθαρβουζανὰ καὶ οἱ σύνδουλοι αὐτῶν, καὶ τοῖα εἶπαν αὐτοῖς"})[3]
        self.assertEqual(_tag_of(res, "τοῖα").lemma_key, "G21422")
        # Smooth-breathing αὐταί (G0846), verse-boundary οἴῃ (G3633), aspirated ἐπεῖδον (G1896)
        res = greek.tag_chapter("psalms", 22, {4: "ἡ ῥάβδος σου καὶ ἡ βακτηρία σου, αὐταί με παρεκάλεσαν."})[4]
        self.assertEqual(_tag_of(res, "αὐταί").lemma_key, "G0846")
        res = greek.tag_chapter("job", 34, {12: "οἴῃ δὲ τὸν κύριον ἄτοπα ποιήσειν; ἢ ὁ παντοκράτωρ ταράξει κρίσιν,"})[12]
        self.assertEqual(_tag_of(res, "οἴῃ").lemma_key, "G3633")
        res = greek.tag_chapter("psalms", 111, {8: "ἐστήρικται ἡ καρδία αὐτοῦ, οὐ φοβηθήσεται, ἕως οὗ ἐφίδῃ τοὺς ἐχθροὺς αὐτοῦ."})[8]
        self.assertEqual(_tag_of(res, "ἐφίδῃ").lemma_key, "G1896")
        # Asseverative μήν (G3375), prepositional ἐξ οὗ (G3739), sentence-opener headword (Sir 18:30)
        res = greek.tag_chapter("job", 28, {13: "οὐκ οἶδεν βροτὸς ὁδὸν αὐτῆς, οὐδὲ μὴν εὑρέθη ἐν ἀνθρώποις."})[13]
        self.assertEqual(_tag_of(res, "μὴν").lemma_key, "G3375")
        res = greek.tag_chapter("micah", 5, {1: "ἐξ οὗ μοι ἐξελεύσεται τοῦ εἶναι εἰς ἄρχοντα τοῦ Ἰσραήλ"})[1]
        self.assertEqual(_tag_of(res, "οὗ").lemma_key, "G3739")
        res = greek.tag_chapter("sirach", 18, {30: "Ἐγκράτεια ψυχῆς. Ὀπίσω τῶν ἐπιθυμιῶν σου μὴ πορεύου, καὶ ἀπὸ τῶν ὀρέξεών σου κωλύου·"})[30]
        self.assertEqual(_tag_of(res, "Ἐγκράτεια").lemma_key, "G1466")
        # Split compound proper name (both halves tagged) and mid-verse Lam 3:45 Ἄιν acrostic stays untagged
        res = greek.tag_chapter("judges", 3, {3: "καὶ τὸν Εὐαῖον τὸν κατοικοῦντα τὸν Λίβανον ἀπὸ τοῦ ὄρους τοῦ "
                                                 "Ἀερμὼν ἕως Λαβὼ Ἑμάθ."})[3]
        self.assertIsNotNone(_tag_of(res, "Λαβὼ").lemma_key)
        self.assertEqual(_tag_of(res, "Λαβὼ").lemma_key, _tag_of(res, "Ἑμάθ").lemma_key)
        res = greek.tag_chapter("lamentations", 3, {45: "καμμύσαι με καὶ ἀπωσθῆναι. Ἄιν. Ἔθηκας ἡμᾶς ἐν μέσῳ τῶν λαῶν,"})[45]
        t_ain = _tag_of(res, "Ἄιν")
        self.assertIsNone(t_ain.lemma_key)
        self.assertIn("acrostic letter name", t_ain.notes)


if __name__ == "__main__":
    unittest.main()
