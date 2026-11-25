"""Tests for the English-to-original word alignment (studio/concordance_align.py, 18 Nov 2026).

AGENTS.md invariant 1: CTS_DATA_DIR / CTS_OUTPUT_ROOT point at a temporary folder before studio is
imported.  The offline tests use synthetic data only.  The live tests read the Studio database read-only
(``mode=ro``) and the English column repositories through ``git show`` (nothing is written); they skip when
the database, the repositories or the corpora are missing.

The regression cases come from the hand-judged gold sets of 18 Nov 2026 (2,561 Greek, 2,704 Hebrew and
2,578 Latin links of tiers A-C in 300+ stratified verses per stream): auxiliary 'have' linked to a verb,
repeated words swallowed by a phrase ('fear, fear'), Latin cells repeating one passage ten times
(Esther 10:3a-k), placeholder cells, and IBM-only links far from the diagonal.
"""

from __future__ import annotations

import collections
import hashlib
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

_SANDBOX = tempfile.mkdtemp(prefix="cts_align_")
os.environ.setdefault("CTS_DATA_DIR", os.path.join(_SANDBOX, "data"))
os.environ.setdefault("CTS_OUTPUT_ROOT", os.path.join(_SANDBOX, "out"))

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from studio import concordance_align as al  # noqa: E402
from studio.lexica import LemmaEntry  # noqa: E402

LIVE_DB = ROOT / "data" / "studio.db"


def tearDownModule() -> None:
    shutil.rmtree(_SANDBOX, ignore_errors=True)


def _words(text):
    return [w for _, _, w in al.english_words(text)]


# ---------------------------------------------------------------------------
# English words, keys, units
# ---------------------------------------------------------------------------

class TestEnglishWords(unittest.TestCase):
    def test_word_notes_regex(self):
        # hyphens and inner apostrophes join, a final possessive apostrophe and dashes do not
        self.assertEqual(_words("the Lord’s house, fruit-bearing trees; the sons’ wives—all of them"),
                         ["the", "Lord’s", "house", "fruit-bearing", "trees", "the", "sons", "wives", "all", "of",
                          "them"])
        self.assertEqual(_words("1:1In the beginning"), ["1", "1In", "the", "beginning"])

    def test_keys(self):
        self.assertEqual(al.key("offerings"), al.key("offering"))
        self.assertEqual(al.key("believes"), al.key("believe"))          # not 'belief'
        self.assertEqual(al.key("wolves"), "wolf")
        self.assertEqual(al.key("YHWH"), al.key("LORD"))
        self.assertEqual(al.key("Lord’s"), "lord")
        self.assertEqual(al.key("having"), "have")
        self.assertEqual(al.key("made"), "make")
        self.assertIn("burn", al.word_keys("burnt-offering"))

    def test_stop_and_weak_words(self):
        for w in ("the", "of", "him", "neither", "some", "any"):
            self.assertTrue(al.is_stop(w), w)
        for w in ("toward", "before", "one", "make", "have"):
            self.assertIn(al.key(w), al.WEAK_WORDS, w)
        self.assertNotIn(al.key("king"), al.WEAK_WORDS)

    def test_auxiliaries(self):
        self.assertTrue(al.auxiliary_have(_words("I have given you every plant"), 1))
        self.assertTrue(al.auxiliary_have(_words("when the scribes have finished speaking"), 3))
        self.assertTrue(al.auxiliary_have(_words("Do you not know what I have done"), 0))
        self.assertFalse(al.auxiliary_have(_words("you have faith and I have works"), 1))
        self.assertFalse(al.auxiliary_have(_words("do this and live"), 0))

    def test_linkable_mask(self):
        t = "Love is kind; [love] does not boast"
        mask = dict(zip(_words(t), al.linkable_mask(t)))
        self.assertFalse(mask["love"])
        self.assertTrue(mask["Love"])
        t = "[[The grace of our Lord be with you all.]]"
        self.assertFalse(any(al.linkable_mask(t)))
        t = "| conventional 4:1 When Sanballat heard"
        self.assertEqual(al.linkable_mask(t), [False, False, False, True, True, True])     # conventional 4 1

    def test_placeholders(self):
        for t in ("", "No MT counterpart [No Hebrew counterpart at this location.]",
                  "H — [No corresponding text in the displayed Hebrew main text.]",
                  "— [No corresponding Hebrew source unit.]",
                  "[The Hebrew book ends at 10:3; no corresponding Hebrew passage.]",
                  "Corresponding Latin text: 33:31. The complete verse is displayed in its own card.",
                  "Earlier label 35:16a — see this chapter’s reading text"):
            self.assertTrue(al.is_placeholder(t), t)
        # scripture printed in brackets stays (unlinked), it is not an editorial note
        self.assertFalse(al.is_placeholder("[[The grace of our Lord Jesus Christ be with you all. Amen.]]"))
        self.assertFalse(al.is_placeholder("[BHS 1:1] In the beginning God created"))
        self.assertFalse(al.is_placeholder("For Christ did not enter holy places made by hands, counterparts"))

    def test_parse_label(self):
        p = al.parse_label
        self.assertEqual(p("Genesis 1:1", 1), ("1:1", [(1, 1)], False))
        self.assertEqual(p("1:1", 1), ("1:1", [(1, 1)], False))                     # flat Leviticus files
        self.assertEqual(p("1 Kings 12:24a", 12), ("12:24a", [(12, 24)], True))
        self.assertEqual(p("1 Kings 11:5–8", 11), ("11:5–8", [(11, 5), (11, 6), (11, 7), (11, 8)], False))
        self.assertEqual(p("Esther 5:1d–1f; 5:2", 5), ("5:1d–1f; 5:2", [(5, 1), (5, 2)], True))
        self.assertEqual(p("Esther 5:1–1c", 5), ("5:1–1c", [(5, 1)], True))
        self.assertEqual(p("Jeremiah 25:13; 32:13", 25)[1], [(25, 13), (32, 13)])
        self.assertEqual(p("Susanna 1:7–8", 13), ("13:7–8", [(13, 7), (13, 8)], False))
        self.assertEqual(p("Daniel 5:preface", 5), ("5:preface", [], False))
        self.assertEqual(p("Sirach Prologue 1a", 0, "Sirach"), ("Prologue 1a", [], False))

    def test_units_from_json(self):
        flat = [{"chapter": 1, "ref": "1:1", "id": "v1-1", "text": "And He called unto Moses,"}]
        u = al.units_from_json(flat, "grc")
        self.assertEqual((u[0].label, u[0].targets), ("1:1", [(1, 1)]))
        data = {"book": "Esther", "chapters": [{"chapter": 5, "verses": [
            {"reference": "Esther 5:1–1c", "text": "On the third day\nshe rose.",
             "continuation_paragraphs": ["Having made herself splendid,", "she stood before the king."]},
            {"reference": "Esther 5:3", "text": ""}]}]}
        u = al.units_from_json(data, "grc")
        self.assertEqual(u[0].text, "On the third day she rose. Having made herself splendid, she stood before "
                                    "the king.")
        self.assertEqual(u[0].sha, hashlib.sha1(u[0].text.encode("utf-8")).hexdigest()[:10])
        self.assertTrue(u[1].placeholder)


class TestGroups(unittest.TestCase):
    def test_lettered_and_range_units(self):
        U = al.EnglishUnit
        units = [U("12:23", "a", 12, [(12, 23)]), U("12:24", "b", 12, [(12, 24)]),
                 U("12:24a", "c", 12, [(12, 24)], True), U("12:24b", "d", 12, [(12, 24)], True),
                 U("12:25–26", "e", 12, [(12, 25), (12, 26)]), U("5:preface", "f", 12, [])]
        verses = [(12, 23), (12, 24), (12, 25), (12, 26), (12, 27)]
        groups, st = al.build_groups(units, verses)
        self.assertEqual([(g.units, g.verses) for g in groups], [([0], [0]), ([1, 2, 3], [1]), ([4], [2, 3])])
        self.assertEqual(st["units_without_studio_verse"], 1)
        self.assertEqual(st["studio_verses_without_english"], 1)

    def test_merge_ranges(self):
        links = [[0, 3, 4, 0, 5, 1], [0, 2, 3, 0, 5, 1], [0, 7, 8, 0, 6, 2], [1, 0, 1, 1, 1, 1]]
        self.assertEqual(al.merge_ranges(links), [[0, 2, 4, 0, 5, 1], [0, 7, 8, 0, 6, 2], [1, 0, 1, 1, 1, 1]])

    def test_wilson(self):
        lo, hi = al.wilson(2523, 2561)
        self.assertAlmostEqual(lo, 0.9797, places=3)
        self.assertGreater(hi, 0.985)
        self.assertEqual(al.wilson(0, 0), (0.0, 1.0))


class TestModel1(unittest.TestCase):
    def test_learns_cooccurrence(self):
        # e ids: 1 house, 2 king, 3 great ; f ids: 1 domus, 2 rex, 3 magnus
        pairs = [([1, 2], [1, 2]), ([1, 3], [1, 3]), ([2, 3], [2, 3]), ([2], [2]), ([1], [1])] * 3
        t = al.model1(pairs, iterations=8)
        p = lambda e, f: t.get((f << 32) | e, 0.0)
        self.assertGreater(p(1, 1), p(2, 1))
        self.assertGreater(p(2, 2), p(3, 2))
        self.assertGreater(p(3, 3), p(1, 3))


# ---------------------------------------------------------------------------
# The aligner on a synthetic Latin corpus (no database, no repositories)
# ---------------------------------------------------------------------------

def _entry(key, lemma, gloss, pos="N"):
    return LemmaEntry("lat", key, lemma, gloss, pos, None, key, lemma, gloss, "self", lemma, "test")


LEX = {k: _entry(k, k[4:], g, p) for k, g, p in [
    ("lat:rex", "king", "N"), ("lat:magnus", "great, large", "ADJ"), ("lat:domus", "house, home", "N"),
    ("lat:video", "to see", "V"), ("lat:timor", "fear", "N"), ("lat:audio", "to hear", "V"),
    ("lat:David", "David: king of Israel, son of Jesse", "PROPN"), ("lat:et", "and", "CONJ"),
    ("lat:vox", "voice, sound", "N"), ("lat:holocaustum", "burnt offering, holocaust", "N"),
    ("lat:offero", "to offer, bring", "V"), ("lat:populus", "people, nation", "N")]}
FUNC = {"lat:et"}


def _verse(ch, v, words):
    """(chapter, verse, [(pos, lemma_key, is_content, surface, src)])"""
    return (ch, v, [(i, f"lat:{lk}" if lk else None, f"lat:{lk}" not in FUNC, s, None)
                    for i, (s, lk) in enumerate(words, start=1)])


class TestAlignerSynthetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        U = al.EnglishUnit
        verses, english = [], []
        base = [("rex", "rex"), ("magnus", "magnus"), ("vidit", "video"), ("domum", "domus")]
        for v in range(1, 9):                     # a little corpus so that IBM has something to learn
            verses.append(_verse(1, v, base))
            english.append(U(f"1:{v}", "The great king saw the house.", 1, [(1, v)]))
        verses.append(_verse(2, 1, [("vox", "vox"), ("timoris", "timor"), ("timor", "timor"), ("et", "et"),
                                     ("audivit", "audio")]))
        english.append(U("2:1", "A voice of fear, fear, and [he] heard it.", 2, [(2, 1)]))
        verses.append(_verse(2, 2, [("David", "David"), ("obtulit", "offero"), ("holocaustum", "holocaustum")]))
        english.append(U("2:2", "David offered a burnt offering.", 2, [(2, 2)]))
        english.append(U("2:2a", "David offered a burnt offering.", 2, [(2, 2)], True))   # verbatim copy
        english.append(U("2:2b", "No MT counterpart [No Hebrew counterpart here.]", 2, [(2, 2)], True, True))
        verses.append(_verse(2, 3, [("populus", "populus")]))
        english.append(U("2:3", "The people", 2, [(2, 3)]))
        english.append(U("2:3a", "and their king", 2, [(2, 3)], True))
        cls.A = al.Aligner(None, "latin", verses_by_book={"genesis": verses}, english_by_book={"genesis": english},
                           lexicon=LEX, dictionaries=al.Dictionaries(), iterations=6)
        cls.res = cls.A.align_book("genesis")
        cls.units = english

    def _links_of(self, label):
        en = [u[0] for u in self.res["english"]].index(label)
        return [l for l in self.res["all_links"] if l[0] == en]

    def test_format(self):
        r = self.res
        self.assertEqual(r["lang"], "lat")
        self.assertEqual(r["column"], "latin")
        self.assertNotIn("2:2b", [u[0] for u in r["english"]])                 # placeholder left out
        for label, text, sha in r["english"]:
            self.assertEqual(sha, hashlib.sha1(text.encode("utf-8")).hexdigest()[:10])
        for en, a, b, vi, pos, tier in r["all_links"]:
            self.assertLess(a, b)
            self.assertLessEqual(b, len(al.english_words(r["english"][en][1])))
            self.assertIn(tier, (1, 2, 3, 4))
            self.assertGreaterEqual(pos, 1)
        self.assertEqual(r["links"], [l for l in r["all_links"] if l[5] in al.EXPORT_TIERS["lat"]])

    def test_simple_verse(self):
        got = {(a, pos) for _, a, b, vi, pos, t in self._links_of("1:1")}
        # The0 great1 king2 saw3 the4 house5 : rex1 magnus2 vidit3 domum4
        self.assertTrue({(1, 2), (2, 1), (3, 3), (5, 4)} <= got)

    def test_repeated_word_and_brackets(self):
        links = self._links_of("2:1")
        by_word = collections.defaultdict(set)
        for _, a, b, vi, pos, t in links:
            for w in range(a, b):
                by_word[w].add(pos)
        # A0 voice1 of2 fear3 fear4 and5 he6 heard7 it8 : 'fear, fear' are two renderings, '[he]' is supplied
        if 3 in by_word and 4 in by_word:
            self.assertNotEqual(by_word[3], by_word[4])
        self.assertNotIn(6, by_word)

    def test_phrase_and_verbatim_copy(self):
        links = self._links_of("2:2")
        spans = {pos: (a, b) for _, a, b, vi, pos, t in links}
        # David0 offered1 a2 burnt3 offering4 : 'burnt offering' is one link to holocaustum (pos 3)
        if 3 in spans:
            self.assertEqual(spans[3], (3, 5))
        self.assertEqual(self._links_of("2:2a"), [])                              # the copy keeps no links

    def test_lettered_unit_keeps_its_own_index(self):
        r = self.res
        vi = [i for i, row in enumerate(self.A.verses["genesis"]) if row[:2] == (2, 3)][0]
        for en, a, b, v, pos, t in r["all_links"]:
            if r["english"][en][0] in ("2:3", "2:3a"):
                self.assertEqual(v, vi)
        self.assertTrue(all(l[3] == vi for l in self._links_of("2:3a")))

    def test_deterministic(self):
        again = al.Aligner(None, "latin", verses_by_book={"genesis": self.A.verses["genesis"]},
                           english_by_book={"genesis": self.units}, lexicon=LEX, dictionaries=al.Dictionaries(),
                           iterations=6).align_book("genesis")
        self.assertEqual(again["all_links"], self.res["all_links"])


# ---------------------------------------------------------------------------
# Live data (read-only)
# ---------------------------------------------------------------------------

def _repo_ok(code):
    return al.resolve_ref(al.DEFAULT_REPOS[code], al.DEFAULT_REFS[code]) is not None


@unittest.skipUnless(_repo_ok("grc") and _repo_ok("heb") and _repo_ok("lat"), "English column repositories missing")
class TestLiveEnglish(unittest.TestCase):
    def test_greek_translation_origin_main(self):
        units = al.load_english("grc", "john")
        self.assertEqual(units[0].label, "1:1")
        self.assertTrue(units[0].text.startswith("In the beginning"))
        self.assertGreater(len(units), 850)
        lev = al.load_english("grc", "leviticus")                                # flat-list file
        self.assertEqual((lev[0].label, lev[0].targets), ("1:1", [(1, 1)]))
        kings = {u.label: u for u in al.load_english("grc", "1-kings")}
        self.assertIn("12:24z", kings)
        self.assertEqual(kings["12:24z"].targets, [(12, 24)])

    def test_hebrew_and_latin_columns(self):
        heb = al.load_english("heb", "1-kings")
        self.assertTrue(any(u.placeholder and u.text.startswith("No MT counterpart") for u in heb))
        lat = {u.label: u for u in al.load_english("lat", "sirach")}
        self.assertTrue(lat["33:32"].placeholder)                                # 'Corresponding Latin text'


@unittest.skipUnless(LIVE_DB.exists() and _repo_ok("heb"), "live Studio database or Hebrew column missing")
class TestLiveHebrew(unittest.TestCase):
    """Trains the whole Hebrew stream (about a minute) and checks gold-set links that were judged correct."""

    @classmethod
    def setUpClass(cls):
        from studio.lexica import hebrew
        if not hebrew.corpora_available():
            raise unittest.SkipTest("OSHB corpora missing")
        cls.conn = sqlite3.connect(f"file:{LIVE_DB.as_posix()}?mode=ro", uri=True)
        cls.A = al.Aligner(cls.conn, "hebrew")
        cls.gen = cls.A.align_book("genesis")

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def _pairs(self, res, label):
        en = [u[0] for u in res["english"]].index(label)
        text = res["english"][en][1]
        words = [w for _, _, w in al.english_words(text)]
        vrows = self.A.verses[res["book"]]
        out = set()
        for e, a, b, vi, pos, t in res["links"]:
            if e == en:
                surf = [x[3] for x in vrows[vi][2] if x[0] == pos][0]
                out.add((" ".join(words[a:b]), surf))
        return out

    def test_genesis_1_1(self):
        got = {(w, "".join(ch for ch in s if "א" <= ch <= "ת")) for w, s in self._pairs(self.gen, "1:1")}
        for pair in [("beginning", "בראשית"), ("God", "אלהים"), ("created", "ברא"), ("heavens", "השמים"),
                     ("earth", "הארץ")]:
            self.assertIn(pair, got)

    def test_gold_regressions(self):
        # Deut 16:3: 'unleavened bread' is one word (מַצּוֹת), 'bread of affliction' is לֶחֶם
        deu = self.A.align_book("deuteronomy")
        got = {(w, "".join(ch for ch in s if "א" <= ch <= "ת")) for w, s in self._pairs(deu, "16:3")}
        self.assertIn(("unleavened bread", "מצות"), got)
        self.assertIn(("bread", "לחם"), got)
        self.assertNotIn(("food", "לחם"), got)

    def test_stream_statistics(self):
        st = self.gen["stats"]
        self.assertGreater(st["en_linked_t3"] / st["en_content"], 0.7)
        self.assertGreater(st["src_linked_t3"] / st["src_content"], 0.8)
        commit = self.gen["source"]["commit"]
        self.assertTrue(commit and len(commit) == 40, commit)
        self.assertEqual(commit, al.resolve_ref(self.A.repo, self.A.ref))
        self.assertEqual(self.gen["source"]["pinned"], al.PINNED["heb"])
        self.assertTrue(
            al.is_ancestor(self.A.repo, al.PINNED["heb"], commit),
            f"live commit {commit[:7]} is not at or descended from pinned {al.PINNED['heb']}",
        )
        self.assertTrue(set(self.gen["export_tiers"]) <= {1, 2, 3})


if __name__ == "__main__":
    unittest.main()
