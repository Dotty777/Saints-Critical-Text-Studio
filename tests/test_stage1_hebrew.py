"""Isolated Stage 1 regression tests for Hebrew/Aramaic parsers, apparatus_witnesses,
Hebrew/Aramaic OSHB lexica corrections, and Swete Clean phantom Psalm heading fixes.

Sets CTS_DATA_DIR and CTS_OUTPUT_ROOT to a temporary sandbox BEFORE importing studio
so live data/studio.db is never touched (AGENTS.md Invariant #1).
"""

import os
import re
import tempfile
import unittest
from pathlib import Path

if "CTS_DATA_DIR" not in os.environ:
    _SANDBOX_ROOT = Path(tempfile.mkdtemp(prefix="cts_stage1_heb_"))
    os.environ["CTS_DATA_DIR"] = str(_SANDBOX_ROOT / "data")
    os.environ["CTS_OUTPUT_ROOT"] = str(_SANDBOX_ROOT / "out")

from studio import apparatus_witnesses as aw
from studio import catalog, collator, db, parsers
from studio.brains.base import ApparatusItem, VerseAdjudication
from studio.brains.textual_analysis import TextualAnalysisBrain
from studio.lexica import hebrew as heb_lex
from studio.lexica import tokenize_verse

assert catalog.STUDIO_ROOT.resolve() not in db.DB_PATH.resolve().parents, (
    f"Sandbox isolation violated: {db.DB_PATH}"
)
db.init_db()
with db.get_conn() as _conn:
    _WIT_BY_ID = {r["id"]: dict(r) for r in _conn.execute("SELECT * FROM witnesses").fetchall()}

BOOK_BY_SLUG = {b.slug: b for b in catalog.BOOKS}


def _wit_dict(wid: str) -> dict:
    return dict(_WIT_BY_ID[wid])


class TestStage1HebrewParsers(unittest.TestCase):
    def test_mam_job_7_5_nested_small_in_ketiv(self) -> None:
        mam = parsers.load_book_from_witness(_wit_dict("heb-mam-aleppo"), BOOK_BY_SLUG["job"])
        v = mam[7][5]
        self.assertIn("(וגיש) וְג֣וּשׁ", v)
        self.assertNotIn("(וג)יש", v)
        # Tokenizer drops (וגיש) and leaves zero bare 'יש' residue
        toks = tokenize_verse(v, "hebrew")
        self.assertNotIn("יש", toks)
        if heb_lex.corpora_available():
            tags = heb_lex.tag_chapter("job", 7, {5: v})[5]
            self.assertEqual([t.surface for t in tags if t.lemma_key is None], [])

    def test_mam_ketiv_wela_qere_no_double_parens_and_2kgs_5_18(self) -> None:
        targets = [
            ("2-samuel", 13, 33, "(אם)"),
            ("2-samuel", 15, 21, "(אם)"),
            ("2-kings", 5, 18, "יִסְלַח־(נא)־יְהֹוָ֥ה"),
            ("jeremiah", 38, 16, "(את)"),
            ("jeremiah", 39, 12, "(אם)"),
            ("jeremiah", 51, 3, "(ידרך)"),
            ("ezekiel", 48, 16, "(חמש)"),
            ("ruth", 3, 12, "(אם)"),
        ]
        mam_w = _wit_dict("heb-mam-aleppo")
        for slug, ch, vnum, expected in targets:
            txt = parsers.load_book_from_witness(mam_w, BOOK_BY_SLUG[slug])[ch][vnum]
            self.assertIn(expected, txt, f"{slug} {ch}:{vnum}")
            self.assertNotIn("((", txt, f"{slug} {ch}:{vnum}")
            self.assertNotIn("))", txt, f"{slug} {ch}:{vnum}")
        # Verify 2 Kgs 5:18 still tokenizes cleanly with zero stray tokens
        txt_5_18 = parsers.load_book_from_witness(mam_w, BOOK_BY_SLUG["2-kings"])[5][18]
        toks = tokenize_verse(txt_5_18, "hebrew")
        self.assertIn("יִסְלַח", toks)
        self.assertIn("יְהֹוָ֥ה", toks)
        self.assertNotIn("נא", toks)

    def test_bhsa_strips_inverted_nun_in_psalm_107(self) -> None:
        bhsa_w = _wit_dict("heb-bhsa-bhs")
        if not Path(bhsa_w["file_path"]).exists():
            self.skipTest("BHSA TF corpus not present")
        ps = parsers.load_book_from_witness(bhsa_w, BOOK_BY_SLUG["psalms"])
        for vnum in (20, 21, 22, 23, 24, 25, 39):
            self.assertNotIn("\u05c6", ps[107][vnum], f"Ps 107:{vnum}")

    def test_letteris_strips_bare_niqqud_qere_wela_ketiv(self) -> None:
        lt_w = _wit_dict("heb-letteris-1852")
        if not Path(lt_w["file_path"]).exists():
            self.skipTest("Letteris corpus not present")
        cases = [
            ("judges", 20, 13), ("ruth", 3, 5), ("ruth", 3, 17),
            ("2-samuel", 8, 3), ("2-samuel", 16, 23), ("2-samuel", 18, 20),
            ("2-kings", 19, 31), ("2-kings", 19, 37),
            ("jeremiah", 31, 37), ("jeremiah", 50, 29),
        ]
        for slug, ch, vnum in cases:
            txt = parsers.load_book_from_witness(lt_w, BOOK_BY_SLUG[slug]).get(ch, {}).get(vnum, "")
            self.assertTrue(txt, f"{slug} {ch}:{vnum} empty")
            for part in collator.split_words(txt, "hebrew"):
                if part == "׀":
                    continue
                self.assertTrue(
                    any("\u05d0" <= c <= "\u05ea" for c in part),
                    f"Bare niqqud token {part!r} survived in Letteris {slug} {ch}:{vnum}: {txt!r}",
                )
        # 2 Sam 8:3 keeps its verse-final sof pasuq on בִּנְהַר׃
        txt_8_3 = parsers.load_book_from_witness(lt_w, BOOK_BY_SLUG["2-samuel"])[8][3]
        self.assertTrue(txt_8_3.endswith("׃"), txt_8_3)

    def test_benchayyim_strips_asterisks_ascii_colon_and_bare_tokens(self) -> None:
        bc_w = _wit_dict("heb-benchayyim-1525")
        if not Path(bc_w["file_path"]).exists():
            self.skipTest("BenChayyim corpus not present")
        ex = parsers.load_book_from_witness(bc_w, BOOK_BY_SLUG["exodus"])[2][5]
        self.assertNotIn(":", ex)
        self.assertTrue(ex.endswith("׃"))
        k2 = parsers.load_book_from_witness(bc_w, BOOK_BY_SLUG["2-kings"])[14][7]
        self.assertNotIn("*", k2)
        jsh = parsers.load_book_from_witness(bc_w, BOOK_BY_SLUG["joshua"])[18][19]
        self.assertNotIn("׀)", jsh)
        jdg = parsers.load_book_from_witness(bc_w, BOOK_BY_SLUG["judges"])[20][13]
        self.assertNotIn("*", jdg)
        rth = parsers.load_book_from_witness(bc_w, BOOK_BY_SLUG["ruth"])[3][12]
        self.assertNotIn("()", rth)
        ps = parsers.load_book_from_witness(bc_w, BOOK_BY_SLUG["psalms"])[27][13]
        self.assertNotIn("\u0323", ps)

    def test_dss_strips_editorial_marginal_anchors(self) -> None:
        qisaa_w = _wit_dict("heb-dss-1qisaa")
        qjer_w = _wit_dict("heb-dss-4qjer")
        if not Path(qisaa_w["file_path"]).exists():
            self.skipTest("ETCBC DSS TF not present")
        isa = parsers.load_book_from_witness(qisaa_w, BOOK_BY_SLUG["isaiah"])
        for ch, vnum in ((34, 17), (35, 2), (37, 6)):
            self.assertNotIn("-", isa[ch][vnum], f"1QIsa-a Isa {ch}:{vnum}: {isa[ch][vnum]!r}")
        jer = parsers.load_book_from_witness(qjer_w, BOOK_BY_SLUG["jeremiah"])
        for ch, vnum in ((7, 30), (7, 31), (7, 33)):
            self.assertNotIn("-", jer[ch][vnum], f"4QJer Jer {ch}:{vnum}: {jer[ch][vnum]!r}")

    def test_swete_clean_no_phantom_psalm_headings(self) -> None:
        sw_w = next(dict(w) for w in _WIT_BY_ID.values() if w["parser_kind"] == "swete_clean")
        if not Path(sw_w["file_path"]).exists():
            self.skipTest("Swete Clean corpus not present")
        ps = parsers.load_book_from_witness(sw_w, BOOK_BY_SLUG["psalms"])
        phantoms = [(25, 22), (27, 14), (71, 24), (102, 29), (114, 26), (116, 10), (136, 26), (149, 14), (150, 9)]
        for ch, vnum in phantoms:
            self.assertNotIn(vnum, ps.get(ch, {}), f"Phantom heading survived at Swete Ps {ch}:{vnum}")
        # Titles now properly open verse 1, matching First1K TEI / Brenton / Swete CSV
        self.assertTrue(ps[25][1].startswith("Τοῦ Δαυείδ."), ps[25][1])
        self.assertTrue(ps[71][1].startswith("Εἰς Σολομών."), ps[71][1])
        self.assertTrue(ps[150][1].startswith("Ἁλληλουιά."), ps[150][1])
        # Mid-psalm collision also resolved (Ps 15 title is on 15:1, not prepended to 15:5)
        self.assertTrue(ps[15][1].startswith("Στηλογραφία τῷ Δαυείδ."), ps[15][1])
        self.assertNotIn("Στηλογραφία", ps[15][5])
        # Non-title continuation books still append to previous chapter's last verse
        job = parsers.load_book_from_witness(sw_w, BOOK_BY_SLUG["job"])
        self.assertIn("δόλον", job[15][35])

    def test_amiatinus_parser_obeys_invariant_6(self) -> None:
        frag = (
            "<app><lem>et <choice><sic>non</sic><corr>om.</corr></choice> "
            "<surplus>erat</surplus> <supplied>panis</supplied></lem>"
            "<rdg source='#s'>et erat panis</rdg></app>"
        )
        out = parsers._render_amiatinus_fragment(frag)
        self.assertIn("non", out)
        self.assertIn("erat", out)
        self.assertIn(parsers.GAP_WORD, out)
        self.assertNotIn("om.", out)


class TestStage1HebrewApparatusWitnesses(unittest.TestCase):
    def _run_hebrew_verse(self, slug: str, ch: int, vnum: int):
        mam_w = _wit_dict("heb-mam-aleppo")
        wlc_w = _wit_dict("heb-wlc-tsv")
        app_ids = ["heb-bhsa-bhs", "heb-benchayyim-1525", "heb-letteris-1852"]
        if slug in ("genesis", "exodus", "leviticus", "numbers", "deuteronomy"):
            app_ids.extend(["heb-samaritan-tf", "heb-dss-torah"])
        elif slug in ("1-samuel", "2-samuel"):
            app_ids.append("heb-dss-4qsama")
        elif slug == "psalms":
            app_ids.append("heb-dss-11qpsa")

        b = BOOK_BY_SLUG[slug]
        mam_t = parsers.load_book_from_witness(mam_w, b)[ch][vnum]
        wlc_t = parsers.load_book_from_witness(wlc_w, b)[ch][vnum]
        cv = collator.align_witnesses_for_verse(
            verse_num=vnum,
            witness_texts={mam_w["siglum"]: mam_t, wlc_w["siglum"]: wlc_t},
            witness_weights={mam_w["siglum"]: mam_w["weight"], wlc_w["siglum"]: wlc_w["weight"]},
            language="hebrew",
            pivot_preference=[mam_w["siglum"]],
            book_slug=slug,
            chapter=ch,
        )
        cv.base_siglum = mam_w["siglum"]
        app_texts = {}
        for wid in app_ids:
            wd = _wit_dict(wid)
            if not Path(wd["file_path"]).exists():
                continue
            t = parsers.load_book_from_witness(wd, b).get(ch, {}).get(vnum)
            if t:
                app_texts[wd["siglum"]] = t
        cv.apparatus_texts = app_texts
        brain = TextualAnalysisBrain()
        adj = brain._adjudicate_single_verse("hebrew", cv)
        aw.record_apparatus_witnesses(cv, adj, "hebrew")
        return adj

    def test_maqaf_word_index_no_shift_or_duplicate_contradiction(self) -> None:
        # 2 Sam 7:22 previously reported BHS/BenChayyim reading 'כִּֽי־ אֵ֣ין' for 'יְהֹוָ֣ה אֱלֹהִ֑ים'
        adj_2sam = self._run_hebrew_verse("2-samuel", 7, 22)
        voting = [it for it in adj_2sam.apparatus if it.slot_index >= 0]
        self.assertEqual(len(voting), 1)
        all_var_readings = [str(vr["reading"]) for vr in voting[0].variants]
        self.assertFalse(any("כִּֽי" in r for r in all_var_readings), all_var_readings)

        # 2 Kgs 6:25 previously reported BHS/Letteris reading 'בַּחֲמִשָּׁה־ כָֽסֶף׃' for 'דִּב יוֹנִ֖ים'
        adj_2kgs = self._run_hebrew_verse("2-kings", 6, 25)
        voting_k = [it for it in adj_2kgs.apparatus if it.slot_index >= 0]
        self.assertEqual(len(voting_k), 1)
        var_readings_k = [str(vr["reading"]) for vr in voting_k[0].variants]
        self.assertFalse(any("בַּחֲמִשָּׁה" in r for r in var_readings_k), var_readings_k)

        # Duplicate-contradiction verses: no witness on opposite sides across duplicate units
        for slug, ch, vnum in (("nehemiah", 11, 17), ("2-samuel", 6, 6), ("ruth", 2, 6), ("ezekiel", 31, 8), ("job", 22, 24)):
            adj = self._run_hebrew_verse(slug, ch, vnum)
            v_units = [it for it in adj.apparatus if it.slot_index >= 0]
            self.assertEqual(len(v_units), 1, f"{slug} {ch}:{vnum}")
            v_widx = v_units[0].word_index
            dup_app = [
                it for it in adj.apparatus
                if it.slot_index == -1 and it.word_index == v_widx
            ]
            self.assertEqual(dup_app, [], f"Duplicate app unit at same word_index in {slug} {ch}:{vnum}: {dup_app}")

    def test_unpointed_witnesses_never_credited_on_vocalic_voting_units(self) -> None:
        # Gen 30:37 & Deut 3:22 (plene/defective SP): purely vocalic -> SP must NOT appear in lemma_witnesses
        for slug, ch, vnum in (("genesis", 30, 37), ("deuteronomy", 3, 22)):
            adj = self._run_hebrew_verse(slug, ch, vnum)
            voting = [it for it in adj.apparatus if it.slot_index >= 0]
            self.assertEqual(len(voting), 1, f"{slug} {ch}:{vnum}")
            self.assertNotIn("SP (Samaritan)", voting[0].lemma_witnesses, f"{slug} {ch}:{vnum}")
            self.assertFalse(any("SP (Samaritan)" in vr["witnesses"] for vr in voting[0].variants))

        # 2 Chr 1:5: MAM שָׁ֕ם (shin) vs WLC שָׂ֕ם (sin) -> BHS (BHSA) reads שָׂם so it must align with WLC, not MAM
        adj_chr = self._run_hebrew_verse("2-chronicles", 1, 5)
        voting_c = [it for it in adj_chr.apparatus if it.slot_index >= 0]
        self.assertEqual(len(voting_c), 1)
        if "BHS (BHSA)" in (voting_c[0].lemma_witnesses + [w for vr in voting_c[0].variants for w in vr["witnesses"]]):
            wlc_var = next(vr for vr in voting_c[0].variants if "WLC (L)" in vr["witnesses"])
            self.assertIn("BHS (BHSA)", wlc_var["witnesses"])
            self.assertNotIn("BHS (BHSA)", voting_c[0].lemma_witnesses)

        # Deut 31:21: SP genuinely reads consonantal 'לאבתיו' against נִשְׁבַּעְתִּי/נִשְׁבָּעְתִּי -> SP MUST stay recorded
        adj_dt = self._run_hebrew_verse("deuteronomy", 31, 21)
        voting_d = [it for it in adj_dt.apparatus if it.slot_index >= 0]
        self.assertEqual(len(voting_d), 1)
        sp_vars = [vr for vr in voting_d[0].variants if "SP (Samaritan)" in vr["witnesses"]]
        self.assertTrue(sp_vars, "Genuine consonantal SP variant in Deut 31:21 was dropped")

    def test_kq_qere_omission_suppressed_and_real_omission_kept(self) -> None:
        # 1 Kgs 4:7, 1 Kgs 6:10, Ps 71:20 must not emit noisy BHS/Letteris 'om.' on the Qere or bare '׀'
        for slug, ch, vnum in (("1-kings", 4, 7), ("1-kings", 6, 10), ("psalms", 71, 20)):
            adj = self._run_hebrew_verse(slug, ch, vnum)
            for it in adj.apparatus:
                for vr in it.variants:
                    self.assertNotEqual(vr["reading"], "׀", f"Paseq leaked in {slug} {ch}:{vnum}")
                    if it.slot_index == -1 and vr["reading"] == "om.":
                        self.fail(f"Noisy K/Q om. in {slug} {ch}:{vnum}: lemma={it.lemma!r} wits={vr['witnesses']}")

        # Synthetic check: genuine omission of BOTH (ketiv) and qere MUST still be reported!
        class _DummyCV:
            witness_texts = {"MAM (Aleppo)": "דָּבָר (ותראה) וַתֵּרֶא שָׁלוֹם", "WLC (L)": "דָּבָר ותראה שָׁלוֹם"}
            apparatus_texts = {"1QTest": "דבר שלום"}
            lexicon = None

        adj_syn = VerseAdjudication(
            verse=1,
            critical_text="דָּבָר (ותראה) וַתֵּרֶא שָׁלוֹם",
            confidence=0.99, decision_source="test", apparatus=[], disregarded=[], rationale="test",
        )
        aw.record_apparatus_witnesses(_DummyCV(), adj_syn, "hebrew")
        self.assertTrue(
            any(vr["reading"] == "om." and "1QTest" in vr["witnesses"] for it in adj_syn.apparatus for vr in it.variants),
            "Genuine omission of whole K/Q pair was wrongly suppressed",
        )

    def test_double_space_lemma_normalized(self) -> None:
        adj = self._run_hebrew_verse("job", 38, 1)
        for it in adj.apparatus:
            self.assertNotIn("  ", it.lemma, f"Double space in lemma: {it.lemma!r}")


class TestStage1HebrewLexicaCorrections(unittest.TestCase):
    def test_five_heb_arc_cross_tags_corrected(self) -> None:
        if not heb_lex.corpora_available():
            self.skipTest("OSHB corpora not present")
        lex = heb_lex.load_lexicon()
        mam_w = _wit_dict("heb-mam-aleppo")
        checks = [
            ("1-kings", 22, 21, "במה", "H4100", "heb"),
            ("psalms", 60, 7, "וענני", "H6030b", "heb"),
            ("hosea", 10, 11, "צוארה", "H6677a", "heb"),
            ("ezra", 7, 18, "עלך", "H5922", "arc"),
            ("daniel", 7, 19, "כלהין", "H3606", "arc"),
        ]
        for slug, ch, vnum, bare_cons, expected_key, expected_lang in checks:
            txt = parsers.load_book_from_witness(mam_w, BOOK_BY_SLUG[slug])[ch][vnum]
            tags = heb_lex.tag_chapter(slug, ch, {vnum: txt})[vnum]
            hits = [t for t in tags if re.sub(r"[^א-ת]", "", t.surface).translate(str.maketrans("ךםןףץ", "כמנפצ")) == bare_cons.translate(str.maketrans("ךםןףץ", "כמנפצ"))]
            self.assertTrue(hits, f"{slug} {ch}:{vnum} token {bare_cons} not found in {tags}")
            self.assertEqual(hits[0].lemma_key, expected_key, f"{slug} {ch}:{vnum}")
            self.assertEqual(lex[hits[0].lemma_key].lang, expected_lang, f"{slug} {ch}:{vnum}")


if __name__ == "__main__":
    unittest.main()
