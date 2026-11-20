"""Offline tests for The Saints Concordance (Tab 5) — accuracy as well as plumbing.

Follows AGENTS.md Invariant #1: CTS_DATA_DIR / CTS_OUTPUT_ROOT point at a temporary sandbox (set up by
test_studio before ``studio`` is imported), so real data is never touched.

Rewritten 18 Nov 2026 with the gold-data build (studio/concordance_gold.py, studio/lexica/): the first
build's tests checked counts only and passed while 58 % of Hebrew tags were the wrong lemma, every רֹאשׁ
'head' was filed as רֵאשִׁית 'beginning', and Hebrew/Greek/Latin were paired by raw verse numbers.
The regression cases below come from that review.
"""

from __future__ import annotations

import ast
import gzip
import json
from pathlib import Path
import shutil
import sqlite3
import tkinter as tk
import unittest

try:
    from . import test_studio as _ts  # Share sandbox env initialized before studio import
except ImportError:
    import test_studio as _ts  # type: ignore[no-redef]

_SANDBOX = _ts._SANDBOX
_CONC_SUBDIR = Path(_SANDBOX) / "conc_isolated"
_CONC_SUBDIR.mkdir(parents=True, exist_ok=True)

from studio import db as studio_db  # noqa: E402
from studio.catalog import BOOKS, BOOKS_BY_SLUG, STUDIO_ROOT  # noqa: E402
from studio.concordance import (  # noqa: E402
    decode_delta_varints,
    encode_delta_varints,
    make_anchor_verse_id,
    parse_anchor_verse_id,
    render_english_sense,
)
from studio.db import get_conn  # noqa: E402
from studio.engine import CriticalTextEngine  # noqa: E402
from studio.lexica import tokenize_verse  # noqa: E402


def _corpora_available() -> bool:
    try:
        from studio.lexica import greek, hebrew, latin

        g = greek.corpora_available()
        ok_g = all(g.values()) if isinstance(g, dict) else bool(g)
        return bool(hebrew.corpora_available()) and ok_g and latin.ls_path().exists()
    except Exception:
        return False


CORPORA = _corpora_available()

# Real Studio critical-text verses (18 Nov 2026), each in its own language's numbering.
VERSES = [
    ("hebrew", "genesis", 1, 1, "בְּרֵאשִׁ֖ית בָּרָ֣א אֱלֹהִ֑ים אֵ֥ת הַשָּׁמַ֖יִם וְאֵ֥ת הָאָֽרֶץ׃"),
    ("greek", "genesis", 1, 1, "Ἐν ἀρχῇ ἐποίησεν ὁ θεὸς τὸν οὐρανὸν καὶ τὴν γῆν."),
    ("latin", "genesis", 1, 1, "In principio creavit Deus cælum et terram."),
    ("hebrew", "genesis", 3, 15, "וְאֵיבָ֣ה ׀ אָשִׁ֗ית בֵּֽינְךָ֙ וּבֵ֣ין הָֽאִשָּׁ֔ה וּבֵ֥ין זַרְעֲךָ֖ וּבֵ֣ין זַרְעָ֑הּ ה֚וּא יְשׁוּפְךָ֣ רֹ֔אשׁ וְאַתָּ֖ה תְּשׁוּפֶ֥נּוּ עָקֵֽב׃"),
    ("greek", "genesis", 3, 15, "καὶ ἔχθραν θήσω ἀνὰ μέσον σοῦ καὶ ἀνὰ μέσον τῆς γυναικός, καὶ ἀνὰ μέσον τοῦ σπέρματός σου καὶ ἀνὰ μέσον τοῦ σπέρματος αὐτῆς· αὐτός σοῦ τηρήσει κεφαλήν, καὶ σὺ τηρήσεις αὐτοῦ πτέρναν."),
    ("latin", "genesis", 3, 15, "Inimicitias ponam inter te et mulierem, et semen tuum et semen illius: ipsa conteret caput tuum, et tu insidiaberis calcaneo ejus."),
    ("hebrew", "psalms", 51, 3, "חׇנֵּ֣נִי אֱלֹהִ֣ים כְּחַסְדֶּ֑ךָ כְּרֹ֥ב רַ֝חֲמֶ֗יךָ מְחֵ֣ה פְשָׁעָֽי׃"),
    ("greek", "psalms", 50, 3, "Ἐλέησόν με, ὁ θεός, κατὰ τὸ μέγα ἔλεός σου, καὶ κατὰ τὸ πλῆθος τῶν οἰκτιρμῶν σου ἐξάλειψον τὸ ἀνόμημά μου·"),
    ("latin", "psalms", 50, 3, "Miserere mei, Deus, secundum magnam misericordiam tuam; et secundum multitudinem miserationum tuarum, dele iniquitatem meam."),
    ("latin", "1-chronicles", 5, 1, "Filii quoque Ruben primogeniti Israël. (Ipse quippe fuit primogenitus ejus: sed cum violasset thorum patris sui, data sunt primogenita ejus filiis Joseph filii Israël, et non est ille reputatus in primogenitum."),
]


def tearDownModule() -> None:
    shutil.rmtree(_CONC_SUBDIR, ignore_errors=True)


class TestConcordanceArchitectureInvariants(unittest.TestCase):
    def test_app_and_cli_only_talk_to_engine(self) -> None:
        """AGENTS.md: app.py and cli.py talk only to studio.engine.CriticalTextEngine."""
        for fname in ("app.py", "cli.py"):
            tree = ast.parse((STUDIO_ROOT / fname).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("studio"):
                    self.assertIn(node.module, {"studio.engine", "studio.catalog", "studio.brains.base"},
                                  f"{fname} imported disallowed internal module {node.module}")

    def test_verse_id_collision_immunity(self) -> None:
        self.assertNotEqual(make_anchor_verse_id(21, 101, 1, 0), make_anchor_verse_id(22, 1, 1, 0))
        self.assertLess(make_anchor_verse_id(70, 22, 21, 0), 2_147_483_647)
        self.assertEqual(parse_anchor_verse_id(make_anchor_verse_id(21, 119, 176, 0)), (21, 119, 176, 0))
        self.assertEqual(parse_anchor_verse_id(make_anchor_verse_id(22, 24, 22, 1)), (22, 24, 22, 1))

    def test_delta_varint_codec(self) -> None:
        ids = [make_anchor_verse_id(1, 1, v) for v in range(1, 32)] + [make_anchor_verse_id(70, 22, 21)]
        blob = encode_delta_varints(ids)
        self.assertEqual(decode_delta_varints(blob), sorted(ids))
        self.assertEqual(render_english_sense("headwater", "ENG:PL"), "headwaters")
        self.assertEqual(render_english_sense("beginning", "ENG:SG"), "beginning")

    def test_tokenizer_keeps_parenthesised_greek_and_latin(self) -> None:
        """The first build deleted every parenthesis from all languages (220 Latin, 25 Greek passages)."""
        toks = tokenize_verse(VERSES[-1][4], "latin")
        self.assertIn("Ipse", toks)
        self.assertIn("primogenitus", toks)
        self.assertIn("ὑποτάσσεται", tokenize_verse("(καὶ πνεύματα προφητῶν προφήταις ὑποτάσσεται,", "greek"))
        # Hebrew: the parenthesised ketiv goes, the pointed qere stays
        self.assertEqual(tokenize_verse("אֶת־לוּדִ֧ים (לודיים) וְאֶת", "hebrew"), ["אֶת", "לוּדִ֧ים", "וְאֶת"])

    def test_no_hard_coded_projections(self) -> None:
        src = (STUDIO_ROOT / "studio" / "concordance.py").read_text(encoding="utf-8")
        self.assertNotIn("3_600_000", src)
        self.assertNotIn("projected_savings_pct", src)

    def test_lex_concept_slug_never_collides(self) -> None:
        from studio.concordance_gold import _lex_concept_slug

        self.assertEqual(_lex_concept_slug("H7225"), "LEX_H7225")
        self.assertEqual(_lex_concept_slug("G0746"), "LEX_G0746")
        self.assertEqual(_lex_concept_slug("lat:dominus"), "LEX_LAT_DOMINUS")
        self.assertEqual(_lex_concept_slug("lat:dico#2"), "LEX_LAT_DICO_2")
        # Greek non-Strong's lemmas must not collapse onto 'LEX_GRC'
        s_ham = _lex_concept_slug("grc:Χαμ")
        s_japheth = _lex_concept_slug("grc:Ιαφεθ")
        self.assertNotEqual(s_ham, "LEX_GRC")
        self.assertNotEqual(s_ham, s_japheth)
        # Capitalised Latin proper names must not collapse onto lowercase common nouns
        self.assertNotEqual(_lex_concept_slug("lat:Paulus"), _lex_concept_slug("lat:paulus"))
        self.assertNotEqual(_lex_concept_slug("lat:Aquila"), _lex_concept_slug("lat:aquila"))


@unittest.skipUnless(CORPORA, "tagged corpora (OSHB, TAGNT/LXX lemmas, Lewis & Short) not available")
class TestGoldConcordanceBuild(unittest.TestCase):
    _orig_db_path: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls._orig_db_path = studio_db.DB_PATH
        studio_db.DB_PATH = _CONC_SUBDIR / "conc_studio.db"
        cls.engine = CriticalTextEngine()
        now = "2026-11-18T12:00:00Z"
        with get_conn() as conn:
            for lang, slug, ch, v, text in VERSES:
                row = conn.execute("SELECT id FROM chapters WHERE language = ? AND book_slug = ? AND chapter = ?",
                                   (lang, slug, ch)).fetchone()
                if row:
                    cid = int(row[0])
                else:
                    cid = int(conn.execute(
                        """INSERT INTO chapters (language, division, book_slug, book_title, chapter, status, ai_mode,
                               model_used, verse_count, variant_verse_count, updated_at)
                           VALUES (?, ?, ?, ?, ?, 'ADJUDICATED', 'offline_philological', 'Offline', 1, 0, ?)""",
                        (lang, BOOKS_BY_SLUG[slug].division, slug, BOOKS_BY_SLUG[slug].title, ch, now)).lastrowid)
                conn.execute(
                    """INSERT INTO verses (chapter_id, verse, critical_text, confidence, decision_source, witness_readings_json,
                           apparatus_json, disregarded_json, rationale, human_locked, updated_at)
                       VALUES (?, ?, ?, 0.99, 'Offline', '{}', '[]', '[]', 'ok', 0, ?)""",
                    (cid, v, text, now))
        cls.build = cls.engine.seed_concordance_lexicons()

    @classmethod
    def tearDownClass(cls) -> None:
        studio_db.DB_PATH = cls._orig_db_path

    def _tokens(self, slug: str, ch: int, vs: int) -> list:
        avid = make_anchor_verse_id(BOOKS_BY_SLUG[slug].order, ch, vs, 0)
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(
                """SELECT wa.lang_stream, sf.surface_text, ls.lemma_key, ls.canonical_stem, cr.root_key, cr.source_key,
                          st.is_content, im.morph_code AS infl_code, im.grammatical_fn AS infl_desc
                   FROM word_anchors wa JOIN stream_tokens st ON st.slot_id = wa.slot_id
                   JOIN surface_forms sf ON sf.form_id = st.form_id
                   JOIN lexical_stems ls ON ls.stem_id = st.stem_id
                   JOIN core_roots cr ON cr.root_id = ls.root_id
                   LEFT JOIN morpheme_catalog im ON im.morph_id = st.infl_morph_id
                   WHERE wa.anchor_verse_id = ? ORDER BY wa.lang_stream, wa.slot_seq""", (avid,))]

    def test_build_tags_every_language(self) -> None:
        langs = self.build["languages"]
        for lang in ("hebrew", "greek", "latin"):
            self.assertGreater(langs[lang]["indexed"], 0, lang)
            self.assertGreater(langs[lang]["content_words"], 0, lang)
            self.assertGreater(langs[lang]["function_words"], 0, lang)
            self.assertEqual(langs[lang]["indexed"], langs[lang]["content_words"] + langs[lang]["function_words"], lang)
            self.assertGreaterEqual(langs[lang]["indexed_share_of_tokens"], 0.90, lang)
        self.assertEqual(self.build["hub_links_missing"], [])

    def test_function_words_indexed_in_db_and_morph_parsed(self) -> None:
        toks = self._tokens("genesis", 1, 1)
        by_surface = {t["surface_text"]: t for t in toks}
        # Function words are indexed in studio.db with is_content = 0
        self.assertEqual(by_surface["καὶ"]["is_content"], 0)
        self.assertEqual(by_surface["ὁ"]["is_content"], 0)
        self.assertEqual(by_surface["et"]["is_content"], 0)
        self.assertEqual(by_surface["אֵ֥ת"]["is_content"], 0)
        # Real morph parses (not fallback H:WORD / L:WORD) are stored with descriptions
        self.assertTrue(str(by_surface["בְּרֵאשִׁ֖ית"]["infl_code"]).startswith("O:"))
        self.assertIn("Noun", str(by_surface["בְּרֵאשִׁ֖ית"]["infl_desc"]))
        self.assertTrue(str(by_surface["principio"]["infl_code"]).startswith("L:"))
        self.assertNotEqual(by_surface["principio"]["infl_code"], "L:WORD")
        # Greek OT gets GLAUx parses when the corpus is available
        from studio.lexica import glaux
        if glaux.corpus_available():
            self.assertTrue(str(by_surface["ἀρχῇ"]["infl_code"]).startswith("A:"))
            self.assertIn("dative", str(by_surface["ἀρχῇ"]["infl_desc"]).lower())

    def test_no_lex_concept_collisions_in_db(self) -> None:
        with get_conn() as conn:
            dups = conn.execute(
                """SELECT tc.concept_slug, COUNT(scl.stem_id) AS n
                   FROM trilingual_concepts tc
                   JOIN stem_concept_links scl ON scl.concept_id = tc.concept_id
                   WHERE tc.concept_slug LIKE 'LEX\\_%' ESCAPE '\\'
                   GROUP BY tc.concept_id HAVING n > 1"""
            ).fetchall()
            self.assertEqual(dups, [])

    def test_genesis_1_1_lemmas_and_roots(self) -> None:
        toks = self._tokens("genesis", 1, 1)
        by_surface = {t["surface_text"]: t for t in toks}
        self.assertTrue(str(by_surface["בְּרֵאשִׁ֖ית"]["lemma_key"]).startswith("H7225"))
        self.assertIn("ראש", by_surface["בְּרֵאשִׁ֖ית"]["source_key"].replace("ׁ", ""))
        self.assertEqual(by_surface["ἀρχῇ"]["lemma_key"], "G0746")
        self.assertEqual(by_surface["principio"]["canonical_stem"], "principium")
        self.assertEqual(by_surface["creavit"]["canonical_stem"], "creo")
        with get_conn() as conn:
            # Gen 1:1: Latin principium decides 'beginning'; every hub has its 'sense not yet chosen' row
            s11 = conn.execute(
                """SELECT ss.base_word FROM trilingual_alignments ta JOIN saints_senses ss ON ss.sense_id = ta.sense_id
                   WHERE ta.anchor_verse_id = ?""", (make_anchor_verse_id(1, 1, 1, 0),)).fetchone()
            self.assertEqual(s11[0], "beginning")
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM saints_senses WHERE sense_offset = 64 AND sense_role = 'unreviewed'").fetchone()[0], 7)

    def test_rosh_is_head_not_beginning(self) -> None:
        """Gemini filed 293 of 338 רֹאשׁ 'head' tokens under רֵאשִׁית 'beginning'."""
        toks = self._tokens("genesis", 3, 15)
        rosh = [t for t in toks if t["surface_text"] == "רֹ֔אשׁ"]
        self.assertEqual(len(rosh), 1)
        self.assertTrue(str(rosh[0]["lemma_key"]).startswith("H7218"))
        lat = {t["surface_text"]: t["canonical_stem"] for t in toks if t["lang_stream"] == "lat_bible"}
        self.assertEqual(lat.get("caput"), "caput")
        with get_conn() as conn:
            row = conn.execute(
                """SELECT ss.base_word, ta.alignment_state FROM trilingual_alignments ta
                   JOIN saints_senses ss ON ss.sense_id = ta.sense_id
                   JOIN trilingual_concepts tc ON tc.concept_id = ss.concept_id
                   WHERE ta.anchor_verse_id = ? AND tc.concept_slug = 'ORIGIN_HEAD_START'""",
                (make_anchor_verse_id(1, 3, 15, 0),)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "head")  # decided by Greek κεφαλή; not 'beginning'

    def test_hebrew_psalm_filed_under_saints_numbering(self) -> None:
        """Hebrew Ps 51:3 (MT) is Saints/Greek Ps 50:3; the first build filed it under Ps 51:3."""
        toks = self._tokens("psalms", 50, 3)
        streams = {t["lang_stream"] for t in toks}
        self.assertEqual(streams, {"heb_ot", "grc_ot", "lat_bible"})
        self.assertIn("חׇנֵּ֣נִי", {t["surface_text"] for t in toks})
        self.assertFalse(self._tokens("psalms", 51, 3))

    def test_parenthesised_latin_is_indexed(self) -> None:
        stems = {t["canonical_stem"] for t in self._tokens("1-chronicles", 5, 1)}
        self.assertIn("primogenitus", stems)

    def test_verse_breakdown_converts_workbench_numbering(self) -> None:
        info = self.engine.get_verse_concordance("psalms", 51, 3, language="hebrew")
        self.assertEqual(info["anchor_verse_id"], make_anchor_verse_id(BOOKS_BY_SLUG["psalms"].order, 50, 3, 0))
        self.assertEqual(info["tokens"][0]["lang_stream"], "heb_ot")

    def test_stats_are_measured(self) -> None:
        st = self.engine.get_concordance_stats()
        self.assertNotIn("projected_savings_pct", st)
        self.assertEqual(st["total_tokens"], sum(st["tokens_by_stream"].values()))

    def test_pack_export_attribution_and_licence_hygiene(self) -> None:
        res = self.engine.export_concordance_pack(out_dir=_CONC_SUBDIR / "pack")
        files = res["files"]
        for key in ("heb", "grc", "lat", "hubs", "decoder", "csv"):
            self.assertTrue(Path(files[key]).exists(), key)
        with gzip.open(files["heb"], "rt", encoding="utf-8") as fh:
            heb = json.load(fh)
        self.assertEqual(heb["schema"], "saints-concordance-pack/v3")
        self.assertTrue(any("CC BY 4.0" == a["licence"] for a in heb["attribution"]))
        self.assertIn("Changes made by Saints.Bible", heb["changes"])
        # every exported lemma has postings; postings decode to Saints anchors
        for lemma in heb["lemmas"]:
            self.assertIn(str(lemma[0]), heb["lemma_postings"])
            self.assertEqual(lemma[8], 1)
        # function words are indexed in studio.db but stay out of website pack postings
        with gzip.open(files["grc"], "rt", encoding="utf-8") as fh:
            grc = json.load(fh)
        grc_keys = {l[3] for l in grc["lemmas"]}
        self.assertNotIn("G2532", grc_keys)  # καί
        self.assertNotIn("G3588", grc_keys)  # ὁ
        with gzip.open(files["lat"], "rt", encoding="utf-8") as fh:
            lat = json.load(fh)
        lat_keys = {l[3] for l in lat["lemmas"]}
        self.assertNotIn("lat:et", lat_keys)
        # TBESH column 8 ('Meaning', Online Bible) must never reach the pack
        blob = "".join(gzip.open(files[k], "rt", encoding="utf-8").read() for k in ("heb", "grc", "lat", "hubs"))
        self.assertNotIn("light of heavenly luminaries", blob)
        self.assertNotIn("<br>", blob)

    def test_human_sense_edit_survives_rebuild_and_is_locked(self) -> None:
        with get_conn() as conn:
            row = conn.execute(
                """SELECT ta.align_id, ss.concept_id FROM trilingual_alignments ta
                   JOIN saints_senses ss ON ss.sense_id = ta.sense_id WHERE ta.anchor_verse_id = ?""",
                (make_anchor_verse_id(1, 1, 1, 0),)).fetchone()
            self.assertIsNotNone(row)
            align_id, concept_id = int(row[0]), int(row[1])
            start = int(conn.execute("SELECT sense_id FROM saints_senses WHERE concept_id = ? AND sense_offset = 2",
                                     (concept_id,)).fetchone()[0])
        self.engine.set_concordance_alignment_sense(align_id=align_id, new_sense_id=start, lock=True, rationale="test")
        self.engine.index_concordance_chapters(book_slug="genesis")
        with get_conn() as conn:
            kept = conn.execute("SELECT sense_id FROM trilingual_alignments WHERE align_id = ?", (align_id,)).fetchone()
            self.assertIsNotNone(kept)
            self.assertEqual(int(kept[0]), start)
            slot = conn.execute("SELECT slot_id FROM trilingual_alignment_slots WHERE align_id = ? LIMIT 1", (align_id,)).fetchone()
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE stream_tokens SET review_status = 'ai_advisory' WHERE slot_id = ?", (int(slot[0]),))

    def test_extra_site_verses_indexed_in_db_and_excluded_from_website_pack(self) -> None:
        orig = studio_db.DB_PATH
        studio_db.DB_PATH = _CONC_SUBDIR / "extra_site_studio.db"
        try:
            eng = CriticalTextEngine()
            now = "2026-11-19T12:00:00Z"
            extra_verses = [
                # Live Saints.Bible verse so pack export has non-empty postings
                ("hebrew", "genesis", 1, 1, VERSES[0][4]),
                ("greek", "genesis", 1, 1, VERSES[1][4]),
                ("latin", "genesis", 1, 1, VERSES[2][4]),
                # Extra-site non-duplicate verses: NT TR Matt 17:21 (Greek) + MT/Vulgate Ps 116:14 / 115:5
                ("greek", "matthew", 17, 21, "⟦Τοῦτο δὲ τὸ γένος οὐκ ἐκπορεύεται εἰ μὴ ἐν προσευχῇ καὶ νηστείᾳ.⟧"),
                ("hebrew", "psalms", 116, 14, "נְ֭דָרַי לַיהֹוָ֣ה אֲשַׁלֵּ֑ם נֶגְדָה־נָּ֝֗א לְכׇל־עַמּֽוֹ׃"),
                ("latin", "psalms", 115, 5, "Vota mea Domino reddam coram omni populo ejus."),
                # Confirmed duplicate & placeholder — must be skipped, never indexed
                ("greek", "psalms", 25, 22, "Τοῦ Δαυίδ."),
                ("latin", "sirach", 1, 15, "No aligned Latin source passage."),
            ]
            with get_conn() as conn:
                for lang, slug, ch, v, text in extra_verses:
                    row = conn.execute(
                        "SELECT id FROM chapters WHERE language = ? AND book_slug = ? AND chapter = ?",
                        (lang, slug, ch),
                    ).fetchone()
                    cid = int(row[0]) if row else int(conn.execute(
                        """INSERT INTO chapters (language, division, book_slug, book_title, chapter, status, ai_mode,
                               model_used, verse_count, variant_verse_count, updated_at)
                           VALUES (?, ?, ?, ?, ?, 'ADJUDICATED', 'offline_philological', 'Offline', 1, 0, ?)""",
                        (lang, BOOKS_BY_SLUG[slug].division, slug, BOOKS_BY_SLUG[slug].title, ch, now),
                    ).lastrowid)
                    conn.execute(
                        """INSERT INTO verses (chapter_id, verse, critical_text, confidence, decision_source,
                               witness_readings_json, apparatus_json, disregarded_json, rationale, human_locked, updated_at)
                           VALUES (?, ?, ?, 0.99, 'Offline', '{}', '[]', '[]', 'ok', 0, ?)""",
                        (cid, v, text, now),
                    )
            res = eng.seed_concordance_lexicons()
            langs = res["languages"]
            self.assertEqual(langs["hebrew"].get("unmapped_verses", 0), 0)
            self.assertEqual(langs["greek"].get("unmapped_verses", 0), 0)
            self.assertEqual(langs["latin"].get("unmapped_verses", 0), 0)
            self.assertEqual(langs["hebrew"].get("extra_site_verses", 0), 1)
            self.assertEqual(langs["greek"].get("extra_site_verses", 0), 1)
            self.assertEqual(langs["latin"].get("extra_site_verses", 0), 1)
            self.assertEqual(langs["greek"].get("skipped_duplicate_verses", 0), 1)
            self.assertEqual(langs["latin"].get("skipped_duplicate_verses", 0), 1)

            # Extra-site verses resolve through get_verse_concordance with subverse=9 and shared anchor
            m17 = eng.get_verse_concordance("matthew", 17, 21, language="greek")
            self.assertEqual(m17["anchor_verse_id"], make_anchor_verse_id(BOOKS_BY_SLUG["matthew"].order, 17, 21, 9))
            self.assertTrue(any(t["surface_text"] == "νηστείᾳ" for t in m17["tokens"]))
            ps_h = eng.get_verse_concordance("psalms", 116, 14, language="hebrew")
            ps_l = eng.get_verse_concordance("psalms", 115, 5, language="latin")
            self.assertEqual(ps_h["anchor_verse_id"], ps_l["anchor_verse_id"])
            self.assertEqual({t["lang_stream"] for t in ps_h["tokens"]}, {"heb_ot", "lat_bible"})
            # Reverse navigation works for extra-site anchors too
            self.assertEqual(eng.concordance_verse_in_language("hebrew", "psalms", 115, 5, subverse=9), [(116, 14)])
            # Duplicate / placeholder verses are not indexed
            self.assertIsNone(eng.get_verse_concordance("sirach", 1, 15, language="latin")["anchor_verse_id"])
            self.assertIsNone(eng.get_verse_concordance("psalms", 25, 22, language="greek")["anchor_verse_id"])

            # Website pack exports ONLY live Saints.Bible site verses (subverse == 0)
            pack = eng.export_concordance_pack(out_dir=_CONC_SUBDIR / "pack_extra")
            for key in ("heb", "grc", "lat"):
                with gzip.open(pack["files"][key], "rt", encoding="utf-8") as fh:
                    data = json.load(fh)
                for b64_blob in data["lemma_postings"].values():
                    import base64
                    for avid in decode_delta_varints(base64.b64decode(b64_blob)):
                        self.assertEqual(avid % 10, 0, (key, avid))
        finally:
            studio_db.DB_PATH = orig


class TestEditionGatekeeper(unittest.TestCase):
    def test_gatekeeper_triggers(self) -> None:
        orig = studio_db.DB_PATH
        studio_db.DB_PATH = _CONC_SUBDIR / "gate_studio.db"
        try:
            CriticalTextEngine()
            with get_conn() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM books_catalog").fetchone()[0], len(BOOKS))
                for bad_row in [
                    ("DBG_BHQ", "heb", "reference_only", "BHQ", "DBG", "DBG_LICENSED_NO_BULK_EXPORT", 1),
                    ("NC_WIT", "grc", "voting_witness", "NC", "Pub", "QUARANTINED_NC", 1),
                    ("APP_TR", "grc", "apparatus_only", "TR", "Pub", "OPEN_PD_CC0", 1),
                ]:
                    with self.assertRaises(sqlite3.IntegrityError):
                        conn.execute(
                            "INSERT INTO editions (code, lang, role, title, publisher, license_mode, is_active_prod) VALUES (?,?,?,?,?,?,?)",
                            bad_row)
                hubs = {str(r[0]): str(r[1]) for r in conn.execute(
                    "SELECT concept_slug, theme_colour FROM trilingual_concepts WHERE theme_colour IS NOT NULL")}
                self.assertEqual(len(hubs), 7)
                # colours follow the site's seven-colour key ('beginning' was indigo = judgment in the first build)
                from studio.concordance_gold import HUB_KEY, apply_hub_key_colours

                self.assertEqual(hubs, {slug: colour for slug, (colour, _theme) in HUB_KEY.items()})
                conn.execute("UPDATE trilingual_concepts SET theme_colour = 'indigo' WHERE concept_slug = 'ORIGIN_HEAD_START'")
                conn.execute("UPDATE trilingual_concepts SET theme_colour = 'blue' WHERE concept_slug = 'HOLY_SET_APART'")
                changed = apply_hub_key_colours(conn)
                self.assertEqual(changed, {"ORIGIN_HEAD_START": "indigo -> red"})  # a colour a person chose is kept
                conn.execute("UPDATE trilingual_concepts SET theme_colour = 'yellow' WHERE concept_slug = 'HOLY_SET_APART'")
                # the first build's seeder bolted unrelated 'contextual_sense' rows onto hubs ('profane' under head)
                from studio.concordance_gold import refresh_curated_hubs

                cid = int(conn.execute("SELECT concept_id FROM trilingual_concepts WHERE concept_slug = 'ORIGIN_HEAD_START'").fetchone()[0])
                conn.execute(
                    "INSERT INTO saints_senses (concept_id, sense_offset, base_word, sense_role, usage_nuance) "
                    "VALUES (?, 7, 'profane', 'contextual_sense', 'Contextual usage ''profane'' of to profane/begin (H2490H)')",
                    (cid,))
                conn.execute("UPDATE trilingual_concepts SET summary_note = 'One shared root-architecture' WHERE concept_id = ?", (cid,))
                rep = refresh_curated_hubs(conn)
                self.assertEqual(rep["auto_senses_removed"], 1)
                words = [r[0] for r in conn.execute(
                    "SELECT base_word FROM saints_senses WHERE concept_id = ? AND sense_offset < 64 ORDER BY sense_offset", (cid,))]
                self.assertEqual(words, ["beginning", "start", "headwater", "firstfruit", "head", "chief"])
                note = conn.execute("SELECT summary_note FROM trilingual_concepts WHERE concept_id = ?", (cid,)).fetchone()[0]
                self.assertIn("A shared meaning, not a shared root", note)
                # the seed no longer invents "human-locked" rows nobody verified
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM stream_tokens WHERE human_locked = 1").fetchone()[0], 0)
        finally:
            studio_db.DB_PATH = orig


class TestDesktopFifthTabGUI(unittest.TestCase):
    def test_fifth_tab_renders_cleanly(self) -> None:
        from app import CriticalTextDesktopApp

        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        root.withdraw()
        try:
            gui = CriticalTextDesktopApp(root)
            tabs = gui.notebook.tabs()
            self.assertEqual(len(tabs), 5)
            self.assertIn("5 · Saints Concordance", gui.notebook.tab(tabs[4], "text"))
            gui.notebook.select(gui.tab_concordance)
            root.update_idletasks()
            gui._draw_concordance_graph()
            self.assertGreater(len(gui.conc_canvas.find_all()), 0)
            self.assertNotIn("99.1", gui.conc_savings_badge_var.get())
            self.assertTrue(hasattr(gui, "conc_banner_submetrics_var"))
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
