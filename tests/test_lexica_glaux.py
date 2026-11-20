"""Tests for studio/lexica/glaux.py (GLAUx machine parses for the Studio's Greek Old Testament).

Offline.  They read the GLAUx corpus inside the Studio (Saints-Greek-Critical-Text/06_Tier6_...
/Corpus_GLAUx_Annotated_XML) and skip cleanly when it is missing.  The concordance_layer hook test
also needs the Greek gold corpora of greek.py and builds its own in-memory database (the live
Studio database is never opened).  The sandbox environment of tests/test_studio.py is set up first
(AGENTS.md invariant 1).
"""

from __future__ import annotations

import sqlite3
import unittest

try:
    from . import test_studio as _ts  # noqa: F401  (sets CTS_DATA_DIR / CTS_OUTPUT_ROOT first)
except ImportError:
    import test_studio as _ts  # type: ignore[no-redef]  # noqa: F401

from studio.lexica import TokenTag, tokenize_verse  # noqa: E402
from studio.lexica import glaux  # noqa: E402

_HAVE = glaux.corpus_available()

GEN_1_1 = "Ἐν ἀρχῇ ἐποίησεν ὁ θεὸς τὸν οὐρανὸν καὶ τὴν γῆν."
EXOD_1_1 = ("Ταῦτα τὰ ὀνόματα τῶν υἱῶν Ἰσραὴλ τῶν εἰσπεπορευμένων εἰς Αἴγυπτον ἅμα Ἰακὼβ τῷ πατρὶ "
            "αὐτῶν· ἕκαστος πανοικὶ αὐτῶν εἰσήλθοσαν·")
OBAD_1_1 = ("Ὅρασις Ὀβδειού. Τάδε λέγει Κύριος ὁ θεὸς τῇ Ἰδουμαίᾳ Ἀκοὴν ἤκουσα παρὰ Κυρίου, καὶ "
            "περιοχὴν εἰς τὰ ἔθνη ἐξαπέστειλεν Ἀνάστητε καὶ ἐξαναστῶμεν ἐπ᾽ αὐτὴν εἰς πόλεμον.")
OBAD_1_2 = "ἰδοὺ ὀλιγοστὸν δέδωκά σε ἐν τοῖς ἔθνεσιν, ἠτιμωμένος σὺ εἶ σφόδρα·"
NEH_1_1 = ("Λόγοι Νεεμία υἱοῦ Χελκειά. Καὶ ἐγένετο ἐν μηνὶ Σεχεηλοὺ ἔτους εἰκοστοῦ καὶ ἐγὼ ἤμην ἐν "
           "Σουσὰν ἁβειρά·")
DAN_1_1 = ("Ἐν ἔτει τρίτῳ τῆς βασιλείας Ἰωακεὶμ βασιλέως Ἰούδα ἦλθεν Ναβουχοδονοσὸρ βασιλεὺς Βαβυλῶνος "
           "εἰς Ἰερουσαλὴμ καὶ ἐπολιόρκει αὐτήν.")


def _tags(text, keys=None):
    toks = tokenize_verse(text, "grc")
    keys = keys or {}
    return [TokenTag(i, t, keys.get(t), "untagged", 0.0) for i, t in enumerate(toks, start=1)]


class TestPureHelpers(unittest.TestCase):
    """No corpus needed."""

    def test_describe_postag(self) -> None:
        self.assertEqual(glaux.describe_postag("v3saia---"), "verb, 3rd person, singular, aorist, indicative, active")
        self.assertEqual(glaux.describe_postag("A:n-s---fd-"), "noun, singular, feminine, dative")
        self.assertEqual(glaux.describe_postag("a-p---mgc"), "adjective, plural, masculine, genitive, comparative")
        self.assertEqual(glaux.describe_postag("v-prpmmn-"), "verb, plural, perfect, participle, middle, masculine, nominative")
        self.assertIsNone(glaux.describe_postag("q--------"))
        self.assertIsNone(glaux.describe_postag("v3saia--"))
        self.assertEqual(glaux.morph_legend(["A:c--------", "l-s---mn-", "bad"]),
                         {"A:c--------": "conjunction", "A:l-s---mn-": "article, singular, masculine, nominative"})

    def test_licence_rule(self) -> None:
        for ok in ("CC-BY-SA 3.0", "CC BY-SA 4.0", "CC BY 4.0", "CC0", "Public domain"):
            self.assertTrue(glaux.licence_ok(ok), ok)
        for bad in ("CC BY-NC-SA 3.0", "CC-BY-NC 4.0", "CC BY-ND", "NA", "", "All rights reserved"):
            self.assertFalse(glaux.licence_ok(bad), bad)

    def test_forms_and_accents(self) -> None:
        self.assertTrue(glaux.forms_match("εἶπεν", "εἶπε"))          # movable nu
        self.assertTrue(glaux.forms_match("ἐπ᾽", "ἐπί"))             # elision
        self.assertTrue(glaux.forms_match("δ᾽", "δέ"))
        self.assertTrue(glaux.forms_match("Θεὸς", "θεός"))           # case and grave/acute
        self.assertFalse(glaux.forms_match("λόγος", "λόγου"))
        self.assertTrue(glaux.accents_compatible("εἶπεν", "εἶπε"))
        self.assertTrue(glaux.accents_compatible("ἄνθρωπός", "ἄνθρωπος"))   # enclitic throw-back
        self.assertTrue(glaux.accents_compatible("Ισραηλ", "Ἰσραήλ"))       # one side unmarked
        self.assertFalse(glaux.accents_compatible("ἡ", "ἤ"))
        self.assertFalse(glaux.accents_compatible("ἀλλά", "ἄλλα"))

    def test_spelling_variants(self) -> None:
        self.assertTrue(glaux.spelling_variant_forms("γεινώσκει", "γινώσκει"))
        self.assertTrue(glaux.spelling_variant_forms("λήμψεται", "λήψεται"))
        self.assertTrue(glaux.spelling_variant_forms("θάλασσαν", "θάλατταν"))
        self.assertFalse(glaux.spelling_variant_forms("λύει", "λύῃ"))       # ending differs: another form
        self.assertFalse(glaux.spelling_variant_forms("λύομεν", "λύωμεν"))
        self.assertFalse(glaux.spelling_variant_forms("καί", "καί"))

    def test_lemma_agreement(self) -> None:
        self.assertEqual(glaux.lemma_agreement("θεός", "θεός"), "same")
        self.assertEqual(glaux.lemma_agreement("λέγω", "εἶπον"), "suppletive")
        self.assertEqual(glaux.lemma_agreement("ὁράω", "εἴδω"), "suppletive")
        self.assertEqual(glaux.lemma_agreement("Μωυσῆς", "Μωσῆς"), "spelling")
        self.assertEqual(glaux.lemma_agreement("ὁ", "ἤ"), "conflict")
        self.assertEqual(glaux.lemma_agreement("ἤ", "εἰ"), "conflict")          # short words: identical only
        self.assertEqual(glaux.lemma_agreement("ποιέω", "λαμβάνω"), "conflict")

    def test_decide_guards(self) -> None:
        w = ("1", "ἡ", "η", "ὁ", "l-s---fn-", False)
        p = glaux.Pick(w, "exact", False, (1, 1, ""))
        self.assertEqual(glaux.decide(p, "ἤ")[1], "lemma-conflict")
        self.assertEqual(glaux.decide(p, None)[1], "accents-unconfirmed")
        parse, why = glaux.decide(p, "ὁ")
        self.assertEqual(why, "taken")
        self.assertEqual(parse.morph, "A:l-s---fn-")
        self.assertEqual(parse.src, "glaux:1")
        self.assertIn(glaux.NOTE_MACHINE, parse.notes)
        sp = glaux.Pick(("2", "γινώσκει", "γινωσκει", "γινώσκω", "v3spia---", True), "spelling", True, (1, 1, ""))
        self.assertEqual(glaux.decide(sp, None)[1], "spelling-unconfirmed")
        parse, why = glaux.decide(sp, "γινώσκω")
        self.assertEqual(why, "taken")
        self.assertNotIn(glaux.NOTE_MACHINE, parse.notes)               # manual sentence
        self.assertTrue(any("spelling variant" in n for n in parse.notes))
        self.assertEqual(glaux.decide(None, "γινώσκω"), (None, "no-pick"))


@unittest.skipUnless(_HAVE, "GLAUx corpus not present")
class TestGlauxCorpus(unittest.TestCase):

    def test_licences_of_mapped_files(self) -> None:
        rows = glaux.licence_report()
        self.assertEqual(len(rows), 57)
        for r in rows:
            if r["mapped"] == "yes":
                self.assertEqual(r["allowed"], "yes", r)
                self.assertIn("BY-SA", r["source_licence"])
                self.assertNotIn("NC", r["treebank"] + r["source_licence"])
        studio_books = {r["studio_book"] for r in rows if r["studio_book"]}
        self.assertTrue({"genesis", "psalms", "daniel"} <= {b for s in studio_books for b in s.split(",")})

    def test_legend_covers_every_postag(self) -> None:
        used = glaux.used_postags()
        legend = glaux.morph_legend()
        self.assertGreater(len(used), 300)
        self.assertEqual({f"A:{t}" for t in used} - set(legend), set())

    def test_genesis_manual_parse(self) -> None:
        res = glaux.morph_for("genesis", 1, 1, tokenize_verse(GEN_1_1, "grc"))
        toks = tokenize_verse(GEN_1_1, "grc")
        self.assertEqual(len(res), len(toks))
        got = {t: p for t, p in zip(toks, res)}
        self.assertEqual(got["ἐποίησεν"].morph, "A:v3saia---")
        self.assertTrue(got["ἐποίησεν"].src.startswith("glaux:"))
        self.assertEqual(got["ἀρχῇ"].morph, "A:n-s---fd-")
        self.assertNotIn(glaux.NOTE_MACHINE, got["ἐποίησεν"].notes)     # Pedalion Trees, manual
        self.assertTrue(all(p is not None for p in res))

    def test_exodus_machine_note_and_lemma_guard(self) -> None:
        tags = _tags(EXOD_1_1)
        res = glaux.morph_for("exodus", 1, 1, tags)
        parsed = [p for p in res if p is not None]
        self.assertGreaterEqual(len(parsed), len(tags) - 2)
        self.assertTrue(all(glaux.NOTE_MACHINE in p.notes for p in parsed))
        # a Studio lemma that is not the GLAUx lemma blocks the parse
        bad = _tags(EXOD_1_1)
        bad[0].lemma_key = "TEST-KEY"
        orig = glaux._studio_lemma
        try:
            glaux._studio_lemma = lambda k: "λαμβάνω" if k == "TEST-KEY" else orig(k)
            self.assertIsNone(glaux.morph_for("exodus", 1, 1, bad)[0])
        finally:
            glaux._studio_lemma = orig

    def test_mapping_nehemiah_and_daniel(self) -> None:
        chapters = {1: {1: NEH_1_1}}
        al = glaux.align_book("nehemiah", chapters)
        self.assertEqual(al[(1, 1)].group[:2], (11, 1))                 # 2 Esdras 11:1
        dan = glaux.align_book("daniel", {1: {1: DAN_1_1}})[(1, 1)]
        hits = sum(1 for p in dan.picks if p is not None)
        self.assertGreaterEqual(hits, len(dan.picks) - 2)               # Theodotion, not the Old Greek
        self.assertEqual(glaux.BOOK_FILES["daniel"][0], "0527-057")

    def test_each_glaux_word_used_once_per_book(self) -> None:
        chapters = {1: {1: OBAD_1_1, 2: OBAD_1_2}}
        al = glaux.align_book("obadiah", chapters)
        ids = [p.word[glaux.W_ID] for va in al.values() for p in va.picks if p is not None]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreater(len(ids), 30)

    def test_fill_chapter_keeps_existing_parse(self) -> None:
        chapters = {1: {1: OBAD_1_1, 2: OBAD_1_2}}
        tagged = {1: _tags(OBAD_1_1), 2: _tags(OBAD_1_2)}
        tagged[1][0].morph = "R:N-NSF"
        n = glaux.fill_chapter("obadiah", 1, tagged, chapters)
        self.assertGreater(n, 30)
        self.assertEqual(tagged[1][0].morph, "R:N-NSF")
        self.assertIsNone(tagged[1][0].src)
        filled = [t for tags in tagged.values() for t in tags if t.morph and t.morph.startswith("A:")]
        self.assertEqual(len(filled), n)
        for t in filled:
            self.assertTrue(t.src.startswith("glaux:"))
            self.assertIsNotNone(glaux.describe_postag(t.morph))
            self.assertIsNone(t.lemma_key)                              # lemma tags untouched
        self.assertEqual(glaux.fill_chapter("matthew", 1, {}, {}), 0)


def _greek_core() -> bool:
    try:
        from studio.lexica import greek
        a = greek.corpora_available()
        return a["tagnt"] and a["tbesg"] and a["lxx_lemmas"] and a["greek_word_list"]
    except Exception:
        return False


@unittest.skipUnless(_HAVE and _greek_core(), "GLAUx or the Greek gold corpora not present")
class TestConcordanceLayerHook(unittest.TestCase):

    def test_saints_verses_fills_greek_ot(self) -> None:
        from studio import concordance_layer as cl
        from studio.lexica import greek
        greek.AUTO_PREPARE = False                  # never read the live DB implicitly in tests
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE chapters (id INTEGER PRIMARY KEY, language TEXT, book_slug TEXT, chapter INTEGER)")
        conn.execute("CREATE TABLE verses (chapter_id INTEGER, verse INTEGER, critical_text TEXT)")
        conn.execute("INSERT INTO chapters VALUES (1, 'greek', 'obadiah', 1)")
        conn.executemany("INSERT INTO verses VALUES (1, ?, ?)", [(1, OBAD_1_1), (2, OBAD_1_2)])
        try:
            out = dict(cl.saints_verses(conn, "greek", "obadiah"))
        finally:
            conn.close()
        toks = [t for sv in out["obadiah"] for t in sv.tokens]
        self.assertEqual(len(toks), len(tokenize_verse(OBAD_1_1, "grc")) + len(tokenize_verse(OBAD_1_2, "grc")))
        parsed = [t for t in toks if t.morph and t.morph.startswith("A:")]
        self.assertGreater(len(parsed) / len(toks), 0.8)
        lex = greek.load_lexicon()
        for t in parsed:
            self.assertTrue(t.src.startswith("glaux:"))
            self.assertIn(glaux.NOTE_MACHINE, t.notes)
            if t.lemma_key:
                w = glaux.word_by_id(t.src[len(glaux.SRC_PREFIX):])
                self.assertNotEqual(glaux.lemma_agreement(w[glaux.W_LEMMA], lex[t.lemma_key].lemma), "conflict")

    def test_fill_untagged_lemmas_and_deo_guard(self) -> None:
        from studio.lexica import greek
        greek.AUTO_PREPARE = False
        # Ps 118:58 (LXX Ps 118): ἐδεήθην is δέομαι (G1189), never δέω 'bind' (G1210) even though GLAUx
        # lemmatises both under δέω without a homograph digit
        ps_txt = "ἐδεήθην τοῦ προσώπου σου ἐν ὅλῃ καρδίᾳ μου, ἐλέησόν με κατὰ τὸ λόγιόν σου."
        tagged = greek.tag_chapter("psalms", 118, {58: ps_txt})
        # Force ἐδεήθην untagged to exercise GLAUx fill_untagged_lemmas directly
        tok0 = tagged[58][0]
        self.assertEqual(tok0.surface, "ἐδεήθην")
        tok0.lemma_key = None
        tok0.method = "untagged"
        tok0.confidence = 0.0
        glaux.fill_untagged_lemmas("psalms", 118, tagged, {118: {58: ps_txt}})
        self.assertEqual(tok0.lemma_key, "G1189")
        # Acrostic letter names in Lamentations 1-4 remain untagged (opening and mid-verse)
        lam_txt = "Ἄλεφ. Πῶς ἐκάθισεν μόνη ἡ πόλις ἡ πεπληθυμένη λαῶν;"
        lam = greek.tag_chapter("lamentations", 1, {1: lam_txt})
        glaux.fill_untagged_lemmas("lamentations", 1, lam, {1: {1: lam_txt}})
        self.assertIsNone(lam[1][0].lemma_key)
        lam3_txt = "καμμύσαι με καὶ ἀπωσθῆναι. Ἄιν. Ἔθηκας ἡμᾶς ἐν μέσῳ τῶν λαῶν,"
        lam3 = greek.tag_chapter("lamentations", 3, {45: lam3_txt})
        glaux.fill_untagged_lemmas("lamentations", 3, lam3, {3: {45: lam3_txt}})
        ain = next(t for t in lam3[45] if t.surface == "Ἄιν")
        self.assertIsNone(ain.lemma_key)
        # Safe open-corpus orthographic norm: unassimilated nasals & Attic ττ/σσ normalise,
        # but doubled σσ never collapses (so νοσσοῖς never collides with νόσος)
        self.assertEqual(glaux._open_spell_norm("συνπεπλεγμενα"), "συμπεπλεγμενα")
        self.assertEqual(glaux._open_spell_norm("αλλαττουσασ"), "αλλασσουσασ")
        self.assertNotEqual(glaux._open_spell_norm("νοσσοισ"), glaux._open_spell_norm("νοσοισ"))
        # Form-guarded GLAUx lemmatiser fixes (δέω -> δέομαι on ἐδέετο; ὑπέρομαι -> ὕπερος on ὑπέρου)
        p_ed = glaux.Pick(("0", "ἐδέετο", "εδεετο", "δέω", "v3siim---", False), "exact", True, (19, 16, ""))
        self.assertEqual(glaux._resolve_glaux_lemma(p_ed, "ἐδέετο", set()), "G1189")
        p_up = glaux.Pick(("0", "ὑπέρου", "υπερου", "ὑπέρομαι", "v2spmm---", False), "exact", True, (23, 31, ""))
        self.assertEqual(glaux._resolve_glaux_lemma(p_up, "ὑπέρου", set()), "grc:ὕπερος")
        p_sy = glaux.Pick(("0", "συνηγμένος", "συνηγμενοσ", "σύνειμι", "v-srpmmn-", False), "exact", True, (9, 13, ""))
        self.assertEqual(glaux._resolve_glaux_lemma(p_sy, "συνηγμένος", set()), "G4863")


if __name__ == "__main__":
    unittest.main()
