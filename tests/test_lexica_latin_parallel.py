"""Unit and integration tests for studio.lexica.latin_parallel.

Offline, stdlib-only: tests every resolver family (Big-5 parallel syntax, -e vocatives vs.
adverbs, lexical homographs via bipartite PMI/POS/open-gloss, and parallel PROPN linking)
plus precision regression guards and end-to-end build_gold_concordance integration on an
in-memory SQLite database.
"""

from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path
from typing import List, Optional, Tuple

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from studio.lexica import latin as L  # noqa: E402
from studio.lexica import latin_parallel as LP  # noqa: E402
from studio.lexica.latin_parallel import ParToken, ParallelDisambiguator  # noqa: E402

HAVE_LS = L.ls_path().exists()
_LIVE_DB = ROOT / "data" / "studio.db"
_ORIG_DB_PATH = L.db_path
HAVE_DB = _LIVE_DB.exists()


def setUpModule() -> None:
    if HAVE_DB and L.db_path() != _LIVE_DB:
        L.db_path = lambda: _LIVE_DB  # type: ignore[assignment]
        L.reset_cache()


def tearDownModule() -> None:
    if L.db_path is not _ORIG_DB_PATH:
        L.db_path = _ORIG_DB_PATH  # type: ignore[assignment]
        L.reset_cache()


def _pt(seq: int, key: str, stem: str, pos: str, gloss: str = "", morph: str = "") -> ParToken:
    return ParToken(
        seq=seq,
        key=key,
        base_key=LP._base_strongs(key),
        stem=stem,
        pos=pos,
        gloss=gloss,
        morph=morph,
        eng_words=LP._eng_words(gloss),
    )


def _run_one(
    lat_text: str,
    grc: Optional[List[ParToken]] = None,
    heb: Optional[List[ParToken]] = None,
    book: str = "genesis",
    chapter: int = 1,
    verse: int = 1,
    fit_verses: Optional[List[Tuple[int, str, List[ParToken], List[ParToken]]]] = None,
):
    avid = 9990010010
    par_grc = {avid: list(grc or [])}
    par_heb = {avid: list(heb or [])}
    tagged_by_avid = {}
    if fit_verses:
        for fid, ftext, fgrc, fheb in fit_verses:
            par_grc[fid] = list(fgrc)
            par_heb[fid] = list(fheb)
            ftags = L.tag_chapter(book, chapter, {verse: ftext})[verse]
            tagged_by_avid[fid] = [(ftext, ftags)]
    lex = dict(L.load_lexicon())
    tags = L.tag_chapter(book, chapter, {verse: lat_text})[verse]
    tagged_by_avid[avid] = [(lat_text, tags)]
    dis = ParallelDisambiguator(par_grc, par_heb, lex)
    dis.fit_from_verses(tagged_by_avid)
    dis.disambiguate_verse(avid, tags, lat_text)
    return tags, lex, dis


def _tok(tags, surface: str):
    hits = [t for t in tags if t.surface == surface]
    assert hits, f"token {surface!r} not in {[t.surface for t in tags]}"
    return hits[0]


class ContractTests(unittest.TestCase):
    def test_no_quarantined_data_in_module(self) -> None:
        src = (ROOT / "studio" / "lexica" / "latin_parallel.py").read_text(encoding="utf-8").lower()
        for bad in ("quarantine", "non-commercial", "by-nc", "perseus_nc", "tflsj"):
            self.assertNotIn(bad, src)

    def test_base_strongs_normalisation(self) -> None:
        self.assertEqual(LP._base_strongs("H0834a"), "H0834")
        self.assertEqual(LP._base_strongs("H3588b"), "H3588")
        self.assertEqual(LP._base_strongs("H4480a"), "H4480")
        self.assertEqual(LP._base_strongs("G3754"), "G3754")
        self.assertEqual(LP._base_strongs("grc:Μωαβ"), "grc:Μωαβ")


@unittest.skipUnless(HAVE_LS, "Lewis & Short TEI lexicon not available")
class Big5ParallelTests(unittest.TestCase):
    def test_quod_conjunction_vs_relative_and_conflict_withholding(self) -> None:
        # Conjunction via G3754 ὅτι
        tags, _lex, _dis = _run_one(
            "Putavi quod odisses eam",
            grc=[_pt(10, "G1380", "δοκέω", "V"), _pt(20, "G3754", "ὅτι", "CONJ"), _pt(30, "G3404", "μισέω", "V")],
        )
        t = _tok(tags, "quod")
        self.assertEqual(t.lemma_key, "lat:quod#1")
        self.assertEqual(t.method, "parallel-aligned")
        self.assertFalse(t.is_content)

        # Relative via G3739 ὅς
        tags, _lex, _dis = _run_one(
            "quod vidimus et audivimus",
            grc=[_pt(10, "G3739", "ὅς", "PRON", morph="R:R-ASN"), _pt(20, "G3708", "ὁράω", "V"), _pt(30, "G0191", "ἀκούω", "V")],
        )
        t = _tok(tags, "quod")
        self.assertEqual(t.lemma_key, "lat:qui#1")
        self.assertEqual(t.method, "parallel-aligned")

        # Both conj AND rel in the same tight local window -> MUST withhold (never guess)
        # ('fecit ei quod viderat' leaves 'quod' untagged standalone; parallel sees conflicting G3754 + G3739)
        tags, _lex, _dis = _run_one(
            "fecit ei quod viderat",
            grc=[_pt(10, "G4160", "ποιέω", "V"), _pt(20, "G3754", "ὅτι", "CONJ"), _pt(30, "G3739", "ὅς", "PRON", morph="R:R-ASN"), _pt(40, "G3708", "ὁράω", "V")],
        )
        self.assertIsNone(_tok(tags, "quod").lemma_key)

    def test_cum_prep_vs_conj_and_grammatical_impossibility_guard(self) -> None:
        # Preposition via G3326 μετά ('cum duodecim')
        tags, _lex, _dis = _run_one(
            "venit cum duodecim",
            grc=[_pt(10, "G2064", "ἔρχομαι", "V"), _pt(20, "G3326", "μετά", "PREP"), _pt(30, "G1427", "δώδεκα", "NUM")],
        )
        self.assertEqual(_tok(tags, "cum").lemma_key, "lat:cum#1")

        # Conjunction via G3752 ὅταν ('cum accusatores tui venerint')
        tags, _lex, _dis = _run_one(
            "Audiam te cum accusatores tui venerint",
            grc=[_pt(10, "G0191", "ἀκούω", "V"), _pt(20, "G3752", "ὅταν", "CONJ"), _pt(30, "G2064", "ἔρχομαι", "V")],
        )
        self.assertEqual(_tok(tags, "cum").lemma_key, "lat:cum#2")

        # Grammatical impossibility guard: 'cum Omnipotentem invocassent' must NEVER pick prep cum#1
        # even when G3326 μετά appears elsewhere in the same verse!
        tags, _lex, _dis = _run_one(
            "cum Omnipotentem invocassent cum lacrimis",
            grc=[_pt(10, "G1941", "ἐπικαλέω", "V", morph="A:v-papamn-"),
                 _pt(20, "G3841", "παντοκράτωρ", "N"),
                 _pt(30, "G3326", "μετά", "PREP"),
                 _pt(40, "G1144", "δάκρυον", "N")],
        )
        first_cum = [t for t in tags if t.surface == "cum"][0]
        self.assertEqual(first_cum.lemma_key, "lat:cum#2")

    def test_quam_does_not_misread_hebrew_min_from_as_comparative(self) -> None:
        # 1 Sam 17:40 regression: Hebrew H4480a מִן־ ('from the brook') must NOT force 'quam habebat' into comparative!
        tags, _lex, _dis = _run_one(
            "elegit lapides de torrente et misit eos in peram pastoralem quam habebat secum",
            heb=[
                _pt(10, "H0977", "בָּחַר", "V"),
                _pt(20, "H0068", "אֶבֶן", "N"),
                _pt(30, "H4480a", "מִן־", "PREP"),
                _pt(40, "H5158a", "נַחַל", "N"),
                _pt(50, "H7760a", "שׂוּם", "V"),
                _pt(60, "H3627", "כְּלִי", "N"),
                _pt(70, "H0834a", "אֲשֶׁר", "PART"),
            ],
        )
        self.assertEqual(_tok(tags, "quam").lemma_key, "lat:qui#1")

    def test_vestrum_possessive_g5212_vs_partitive_g4771(self) -> None:
        # Luke 16:12 regression: 'quod vestrum est' -> G5212 ὑμέτερος -> lat:vester (not lat:vos!)
        tags, _lex, _dis = _run_one(
            "quod vestrum est quis dabit vobis",
            grc=[_pt(10, "G3588", "ὁ", "PART"), _pt(20, "G5212", "ὑμέτερος", "ADJ", "your"), _pt(30, "G5101", "τίς", "PRON")],
        )
        self.assertEqual(_tok(tags, "vestrum").lemma_key, "lat:vester")

        # John 1:26: 'medius autem vestrum stetit' -> G3319 μέσος + G4771 gen -> lat:vos
        tags, _lex, _dis = _run_one(
            "medius autem vestrum stetit",
            grc=[_pt(10, "G3319", "μέσος", "ADJ"), _pt(20, "G4771", "σύ", "PRON", morph="R:P-2GP"), _pt(30, "G2476", "ἵστημι", "V")],
        )
        self.assertEqual(_tok(tags, "vestrum").lemma_key, "lat:vos")

    def test_big5_never_falls_through_to_lexical_pmi(self) -> None:
        # James 3:5 regression: 'quam' with G2245 ἡλίκος -> comparative lat:quam, never relative lat:qui#1
        tags, _lex, _dis = _run_one(
            "Ecce quantus ignis quam magnam silvam incendit",
            grc=[_pt(10, "G2400", "ἰδού", "INTERJ"), _pt(20, "G2245", "ἡλίκος", "ADJ"),
                 _pt(30, "G4442", "πῦρ", "N"), _pt(40, "G2245", "ἡλίκος", "ADJ"), _pt(50, "G5208", "ὕλη", "N")],
        )
        self.assertEqual(_tok(tags, "quam").lemma_key, "lat:quam")


@unittest.skipUnless(HAVE_LS, "Lewis & Short TEI lexicon not available")
class AdvVocativeTests(unittest.TestCase):
    def test_standalone_leaves_recte_untagged_while_parallel_resolves_it(self) -> None:
        # Standalone latin.py contract MUST remain untouched
        standalone = L.tag_chapter("luke", 7, {43: "recte judicasti"})[43]
        self.assertIsNone(_tok(standalone, "recte").lemma_key)

        # Parallel pass resolves 'recte' against G3723 ὀρθῶς
        tags, lex, _dis = _run_one(
            "recte judicasti",
            grc=[_pt(10, "G3723", "ὀρθῶς", "ADV", "rightly"), _pt(20, "G2919", "κρίνω", "V", "judge")],
        )
        t = _tok(tags, "recte")
        self.assertEqual(t.lemma_key, "lat:recte")
        self.assertEqual(t.method, "parallel-aligned")
        self.assertEqual(t.morph, "L:ADV|head")
        self.assertIn("lat:recte", lex)

    def test_true_vocative_vs_superlative_adverb(self) -> None:
        # Mark 9:25: 'Surde et mute spiritus' with Greek vocative -> lat:mutus
        tags, _lex, _dis = _run_one(
            "Surde et mute spiritus",
            grc=[_pt(10, "G2974", "κωφός", "ADJ", "deaf", "R:A-VSN"),
                 _pt(20, "G0216", "ἄλαλος", "ADJ", "mute", "R:A-VSN"),
                 _pt(30, "G4151", "πνεῦμα", "N", "spirit", "R:N-VSN")],
        )
        self.assertEqual(_tok(tags, "mute").lemma_key, "lat:mutus")

        # Superlative adverb 'certissime'
        tags, _lex, _dis = _run_one(
            "Certissime ergo sciat omnis domus",
            grc=[_pt(10, "G0806", "ἀσφαλῶς", "ADV", "assuredly"), _pt(20, "G1097", "γινώσκω", "V", "know")],
        )
        t = _tok(tags, "Certissime")
        self.assertEqual(t.lemma_key, "lat:certus")
        self.assertEqual(t.morph, "L:ADV|head")


@unittest.skipUnless(HAVE_LS, "Lewis & Short TEI lexicon not available")
class LexicalAndPropnTests(unittest.TestCase):
    def test_shared_root_pos_and_gloss_content_pos_guard(self) -> None:
        # 'multum' ADV vs ADJ via Greek adverbial neuter G4183 πολύς
        tags, _lex, _dis = _run_one(
            "dilexit multum",
            grc=[_pt(10, "G0025", "ἀγαπάω", "V", "love"),
                 _pt(20, "G4183", "πολύς", "ADJ", "much, many", "R:A-ASN")],
        )
        self.assertEqual(_tok(tags, "multum").lemma_key, "lat:multum")

        # Content-POS guard: preposition G1223 διά ("through, because of") must NEVER trigger
        # false gloss overlap on a Latin verb or noun!
        tags, _lex, _dis = _run_one(
            "incidisti in manus",
            grc=[_pt(10, "G1223", "διά", "PREP", "through, fall, cut"), _pt(20, "G5495", "χείρ", "N", "hand")],
        )
        self.assertIsNone(_tok(tags, "incidisti").lemma_key)

    def test_preposition_governed_nominal_guard(self) -> None:
        # Luke 13:15 regression: 'a praesepio' must NEVER be mis-tagged as verb lat:praesaepio!
        tags, _lex, _dis = _run_one(
            "solvit bovem suum a praesepio",
            grc=[_pt(10, "G3089", "λύω", "V", "loose"),
                 _pt(20, "G1016", "βοῦς", "N", "ox"),
                 _pt(30, "G0575", "ἀπό", "PREP", "from"),
                 _pt(40, "G5336", "φάτνη", "N", "manger, stall")],
        )
        self.assertNotEqual(_tok(tags, "praesepio").lemma_key, "lat:praesaepio")

        # Judges 17:10 / Prov 27:27 regression: 'ad victum' resolves to noun lat:victus#2, NOT verb lat:vivo!
        tags, _lex, _dis = _run_one(
            "quae ad victum sunt necessaria",
            grc=[_pt(10, "G3739", "ὅς", "PRON"),
                 _pt(20, "G1519", "εἰς", "PREP", "to"),
                 _pt(30, "G2222", "ζωή", "N", "life, sustenance"),
                 _pt(40, "G1510", "εἰμί", "V", "be")],
        )
        self.assertEqual(_tok(tags, "victum").lemma_key, "lat:victus#2")

    def test_propn_linking_and_false_classical_guards(self) -> None:
        # Daniel 2:17: 'Ananiæque' -> lat:Ananias + E:que (NEVER lat:Chanaan!)
        tags, _lex, _dis = _run_one(
            "Et ingressus est domum suam Ananiæque et Misaëli",
            grc=[_pt(10, "G0367", "Ἀνανίας", "PROPN", "Hananiah"), _pt(20, "grc:Μισαηλ", "Μισαηλ", "PROPN", "Mishael")],
        )
        t = _tok(tags, "Ananiæque")
        self.assertEqual(t.lemma_key, "lat:Ananias")
        self.assertIn("E:que", t.prefixes)

        # Acts 6:5: 'Prochorum' -> verse-attested lat:Prochorus (NEVER classical Roman king lat:Proca!)
        tags, lex, _dis = _run_one(
            "et elegerunt Stephanum et Philippum et Prochorum",
            grc=[_pt(10, "G4736", "Στέφανος", "PROPN", "Stephen"),
                 _pt(20, "G5376", "Φίλιππος", "PROPN", "Philip"),
                 _pt(30, "G4402", "Πρόχορος", "PROPN", "Prochorus")],
        )
        t = _tok(tags, "Prochorum")
        self.assertEqual(t.lemma_key, "lat:Prochorus")
        self.assertIn("lat:Prochorus", lex)

        # 1 Macc 8:8: 'Lydos' -> NEVER falsely linked to Judean town lat:Lydda!
        tags, lex, _dis = _run_one(
            "et Medos et Lydos de optimis regionibus",
            grc=[_pt(10, "grc:Μηδία", "Μηδία", "PROPN", "Media"),
                 _pt(20, "G3070", "Λυδία", "PROPN", "Lydia")],
        )
        t = _tok(tags, "Lydos")
        self.assertNotEqual(t.lemma_key, "lat:Lydda")
        self.assertIsNotNone(t.lemma_key)
        self.assertIn(t.lemma_key, lex)

    def test_acrostic_letters_never_touched(self) -> None:
        tags, _lex, _dis = _run_one(
            "Aleph Quomodo sedet sola civitas",
            grc=[_pt(10, "G4459", "πῶς", "ADV"), _pt(20, "G2521", "κάθημαι", "V")],
            book="lamentations",
            chapter=1,
            verse=1,
        )
        self.assertIsNone(_tok(tags, "Aleph").lemma_key)

    def test_every_emitted_morph_code_exists_in_legend(self) -> None:
        legend = L.morph_legend()
        cases = [
            ("recte judicasti", [_pt(10, "G3723", "ὀρθῶς", "ADV", "rightly")], []),
            ("Ananiæque et Misaëli", [_pt(10, "G0367", "Ἀνανίας", "PROPN", "Hananiah")], []),
            ("et Prochorum", [_pt(10, "G4402", "Πρόχορος", "PROPN", "Prochorus")], []),
            ("quod vestrum est", [_pt(10, "G5212", "ὑμέτερος", "ADJ", "your")], []),
            ("venit cum duodecim", [_pt(10, "G3326", "μετά", "PREP")], []),
        ]
        for text, grc, heb in cases:
            tags, lex, _dis = _run_one(text, grc=grc, heb=heb)
            for t in tags:
                if t.lemma_key is not None:
                    self.assertIn(t.lemma_key, lex, t)
                    self.assertTrue(t.morph, f"missing morph on {t}")
                    for part in str(t.morph).split(","):
                        code = part if part.startswith("L:") else "L:" + part
                        self.assertIn(code, legend, f"unknown morph {code!r} on {t}")


@unittest.skipUnless(HAVE_LS, "Lewis & Short TEI lexicon not available")
class EndToEndConcordanceBuildTests(unittest.TestCase):
    def test_build_gold_concordance_runs_parallel_pass_without_mutating_cached_lexicon(self) -> None:
        from studio.catalog import BOOKS_BY_SLUG
        from studio.concordance import init_concordance_schema, make_anchor_verse_id
        from studio.concordance_gold import build_gold_concordance

        before_lex_size = len(L.load_lexicon())
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                language TEXT NOT NULL, division TEXT NOT NULL, book_slug TEXT NOT NULL,
                book_title TEXT NOT NULL, chapter INTEGER NOT NULL, status TEXT NOT NULL,
                ai_mode TEXT NOT NULL, model_used TEXT NOT NULL, verse_count INTEGER NOT NULL,
                variant_verse_count INTEGER NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE verses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chapter_id INTEGER NOT NULL, verse INTEGER NOT NULL, critical_text TEXT NOT NULL,
                confidence REAL NOT NULL, decision_source TEXT NOT NULL, witness_readings_json TEXT NOT NULL,
                apparatus_json TEXT NOT NULL, disregarded_json TEXT NOT NULL, rationale TEXT NOT NULL,
                human_locked INTEGER NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE studio_revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_table TEXT NOT NULL, target_pk TEXT NOT NULL, field_changed TEXT NOT NULL,
                old_val TEXT, new_val TEXT, actor TEXT NOT NULL, review_mode TEXT NOT NULL,
                rationale TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        init_concordance_schema(conn)
        now = "2026-11-19T18:00:00Z"

        # Seed Acts 6:5 (Greek + Latin), Luke 7:43 (Greek + Latin), and 2 Macc 12:35 (unlisted PROPN Bacenoris)
        verses = [
            ("greek", "acts", 6, 5, "καὶ ἐξελέξαντο Στέφανον, καὶ Φίλιππον καὶ Πρόχορον."),
            ("latin", "acts", 6, 5, "et elegerunt Stephanum et Philippum et Prochorum."),
            ("greek", "luke", 7, 43, "ὁ δὲ εἶπεν αὐτῷ· Ὀρθῶς ἔκρινας."),
            ("latin", "luke", 7, 43, "At ille dixit ei: Recte judicasti."),
            ("greek", "2-maccabees", 12, 35, "τῶν δὲ τοῦ Βακήνορος ἱππεύς τις."),
            ("latin", "2-maccabees", 12, 35, "quidam de Bacenoris eques vir fortis."),
        ]
        for lang, slug, ch, v, txt in verses:
            b = BOOKS_BY_SLUG[slug]
            cid = int(conn.execute(
                """INSERT INTO chapters (language, division, book_slug, book_title, chapter, status, ai_mode,
                       model_used, verse_count, variant_verse_count, updated_at)
                   VALUES (?, ?, ?, ?, ?, 'ADJUDICATED', 'offline_philological', 'Offline', 1, 0, ?)""",
                (lang, b.division, slug, b.title, ch, now),
            ).lastrowid)
            conn.execute(
                """INSERT INTO verses (chapter_id, verse, critical_text, confidence, decision_source,
                       witness_readings_json, apparatus_json, disregarded_json, rationale, human_locked, updated_at)
                   VALUES (?, ?, ?, 0.99, 'Offline', '{}', '[]', '[]', 'ok', 0, ?)""",
                (cid, v, txt, now),
            )

        stats = build_gold_concordance(conn, languages=("greek", "latin"))
        self.assertEqual(stats["languages"]["greek"].get("lemma_missing_from_lexicon", 0), 0)
        lstat = stats["languages"]["latin"]
        self.assertEqual(lstat.get("lemma_missing_from_lexicon", 0), 0)
        self.assertGreaterEqual(lstat.get("parallel_resolved", 0), 3)
        self.assertGreaterEqual(lstat.get("method:parallel-aligned", 0), 3)

        # Verify Prochorum -> lat:Prochorus, Recte -> lat:recte, and dynamic Bacenoris -> lat:Bacenoris landed in DB
        avid_acts = make_anchor_verse_id(BOOKS_BY_SLUG["acts"].order, 6, 5, 0)
        avid_luke = make_anchor_verse_id(BOOKS_BY_SLUG["luke"].order, 7, 43, 0)
        avid_2mac = make_anchor_verse_id(BOOKS_BY_SLUG["2-maccabees"].order, 12, 35, 0)
        rows = {
            (int(r[0]), str(r[1])): str(r[2])
            for r in conn.execute(
                """SELECT wa.anchor_verse_id, sf.surface_text, ls.lemma_key
                   FROM word_anchors wa
                   JOIN stream_tokens st ON st.slot_id = wa.slot_id
                   JOIN surface_forms sf ON sf.form_id = st.form_id
                   JOIN lexical_stems ls ON ls.stem_id = st.stem_id
                   WHERE wa.lang_stream = 'lat_bible'"""
            )
        }
        self.assertEqual(rows.get((avid_acts, "Prochorum")), "lat:Prochorus")
        self.assertEqual(rows.get((avid_luke, "Recte")), "lat:recte")
        self.assertEqual(rows.get((avid_2mac, "Bacenoris")), "lat:Bacenoris")

        # Module-level cached Latin lexicon MUST NOT have been mutated by dynamic parallel PROPNs!
        self.assertEqual(len(L.load_lexicon()), before_lex_size)
        self.assertNotIn("lat:Bacenoris", L.load_lexicon())
        conn.close()


if __name__ == "__main__":
    unittest.main()
