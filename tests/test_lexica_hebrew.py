"""Offline tests for the Hebrew/Aramaic gold lemma tagger (studio/lexica/hebrew.py).

AGENTS.md invariant 1: CTS_DATA_DIR / CTS_OUTPUT_ROOT point at a temporary folder before studio is
imported (unless another test module already did so).  The live Studio database is only ever
opened read-only (``mode=ro``) through an explicit path, for the whole-OT coverage test.

The tests need the OSHB corpora inside Saints-Critical-Text-Studio (OT_OSHB_MorphHB and
OT_OSHB_HebrewLexicon); they skip cleanly when those are missing.  Verse texts below are the
Studio's critical text of 18 Nov 2026, kept literally so the regressions stay pinned.
``TestReviewFixes`` / ``TestLxxFunctionWordNoise`` pin the fixes for the independent review's
examples (interrogative הֲ, 2 Chr 1:5 שָׁם, Ps 123:4 qere, OSHB lemma slips, TBESH glosses, root
glosses, particles, BDB root placement, LXX article noise).  ``TestFinalCheckFixes`` pins the
independent final check's examples (name glosses from the right TBESH row: Sharon, Rumah, Micaiah;
misleading glosses: לִקְרַאת, חֵיל, יֵשׁ ...; gloss residue and typos; pronouns as function words;
POS / gloss clashes; unique root labels; BDB links of תִּירוֹשׁ, עֲלָמוֹת, כַּרְמֶל).
"""

from __future__ import annotations

import os
import re
import shutil
import sqlite3
import sys
import tempfile
import unicodedata
import unittest
from collections import Counter
from pathlib import Path

_SANDBOX = tempfile.mkdtemp(prefix="cts_lexica_heb_")
os.environ.setdefault("CTS_DATA_DIR", os.path.join(_SANDBOX, "data"))
os.environ.setdefault("CTS_OUTPUT_ROOT", os.path.join(_SANDBOX, "out"))

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from studio.lexica import POS_TAGS, tokenize_verse  # noqa: E402
from studio.lexica import hebrew as H  # noqa: E402

HAVE_OSHB = H.corpora_available()
HAVE_MACULA = H.macula_tsv_path() is not None
LIVE_DB = ROOT / "data" / "studio.db"


def tearDownModule() -> None:
    shutil.rmtree(_SANDBOX, ignore_errors=True)


GEN_1_1 = "בְּרֵאשִׁ֖ית בָּרָ֣א אֱלֹהִ֑ים אֵ֥ת הַשָּׁמַ֖יִם וְאֵ֥ת הָאָֽרֶץ׃"
GEN_8_17 = ("כׇּל־הַחַיָּ֨ה אֲשֶֽׁר־אִתְּךָ֜ מִכׇּל־בָּשָׂ֗ר בָּע֧וֹף וּבַבְּהֵמָ֛ה וּבְכׇל־הָרֶ֛מֶשׂ הָרֹמֵ֥שׂ "
            "עַל־הָאָ֖רֶץ (הוצא) הַיְצֵ֣א אִתָּ֑ךְ וְשָֽׁרְצ֣וּ בָאָ֔רֶץ וּפָר֥וּ וְרָב֖וּ עַל־הָאָֽרֶץ׃")
NUM_23_13 = ("וַיֹּ֨אמֶר אֵלָ֜יו בָּלָ֗ק לְךָ־נָּ֨א אִתִּ֜י אֶל־מָק֤וֹם אַחֵר֙ אֲשֶׁ֣ר תִּרְאֶ֣נּוּ מִשָּׁ֔ם "
             "אֶ֚פֶס קָצֵ֣הוּ תִרְאֶ֔ה וְכֻלּ֖וֹ לֹ֣א תִרְאֶ֑ה וְקׇבְנוֹ־לִ֖י מִשָּֽׁם׃")
KGS2_6_25 = ("וַיְהִ֨י רָעָ֤ב גָּדוֹל֙ בְּשֹׁ֣מְר֔וֹן וְהִנֵּ֖ה צָרִ֣ים עָלֶ֑יהָ עַ֣ד הֱי֤וֹת רֹאשׁ־חֲמוֹר֙ "
             "בִּשְׁמֹנִ֣ים כֶּ֔סֶף וְרֹ֛בַע הַקַּ֥ב (חרי) דִּב־יוֹנִ֖ים בַּחֲמִשָּׁה־כָֽסֶף׃")
DAN_1_13 = ("וְיֵרָא֤וּ לְפָנֶ֙יךָ֙ מַרְאֵ֔ינוּ וּמַרְאֵה֙ הַיְלָדִ֔ים הָאֹ֣כְלִ֔ים אֵ֖ת פַּת־בַּ֣ג הַמֶּ֑לֶךְ "
            "וְכַאֲשֶׁ֣ר תִּרְאֵ֔ה עֲשֵׂ֖ה עִם־עֲבָדֶֽיךָ׃")
JOB_7_5 = "לָ֘בַ֤שׁ בְּשָׂרִ֣י רִ֭מָּה (וג)יש וְג֣וּשׁ עָפָ֑ר עוֹרִ֥י רָ֝גַ֗ע וַיִּמָּאֵֽס׃"
KGS2_18_17 = ("וַיִּשְׁלַ֣ח מֶלֶךְ־אַשּׁ֡וּר אֶת־תַּרְתָּ֣ן וְאֶת־רַב־סָרִ֣יס ׀ וְאֶת־רַבְשָׁקֵ֨ה מִן־לָכִ֜ישׁ "
              "אֶל־הַמֶּ֧לֶךְ חִזְקִיָּ֛הוּ בְּחֵ֥יל כָּבֵ֖ד יְרוּשָׁלָ֑‍ִם וַֽיַּעֲלוּ֙ וַיָּבֹ֣אוּ יְרוּשָׁלַ֔‍ִם "
              "וַיַּעֲל֣וּ וַיָּבֹ֗אוּ וַיַּֽעַמְדוּ֙ בִּתְעָלַת֙ הַבְּרֵכָ֣ה הָעֶלְיוֹנָ֔ה אֲשֶׁ֕ר בִּמְסִלַּ֖ת שְׂדֵ֥ה כֹבֵֽס׃")
PS_102_4 = "כִּֽי־כָל֣וּ בְעָשָׁ֣ן יָמָ֑י וְ֝עַצְמוֹתַ֗י כְּמוֹקֵ֥ד נִחָֽרוּ׃"
JOB_36_12 = "וְאִם־לֹ֣א יִ֭שְׁמְעוּ בְּשֶׁ֣לַח יַעֲבֹ֑רוּ וְ֝יִגְוְע֗וּ בִּבְלִי־דָֽעַת׃"
DAN_2_5 = ("עָנֵ֤ה מַלְכָּא֙ וְאָמַ֣ר (לכשדיא) לְכַשְׂדָּאֵ֔י מִלְּתָ֖ה מִנִּ֣י אַזְדָּ֑א הֵ֣ן לָ֤א "
           "תְהֽוֹדְעוּנַּ֙נִי֙ חֶלְמָ֣א וּפִשְׁרֵ֔הּ הַדָּמִין֙ תִּתְעַבְד֔וּן וּבָתֵּיכ֖וֹן נְוָלִ֥י יִתְּשָׂמֽוּן׃")
DAN_2_12 = "כׇּל־קֳבֵ֣ל דְּנָ֔ה מַלְכָּ֕א בְּנַ֖ס וּקְצַ֣ף שַׂגִּ֑יא וַאֲמַר֙ לְה֣וֹבָדָ֔ה לְכֹ֖ל חַכִּימֵ֥י בָבֶֽל׃"
GEN_45_15 = "וַיְנַשֵּׁ֥ק לְכׇל־אֶחָ֖יו וַיֵּ֣בְךְּ עֲלֵהֶ֑ם וְאַ֣חֲרֵי כֵ֔ן דִּבְּר֥וּ אֶחָ֖יו אִתּֽוֹ׃"
EZK_40_34 = ("וְאֵלַמָּ֗ו לֶחָצֵר֙ הַחִ֣יצוֹנָ֔ה וְתִמֹרִ֥ים אֶל־אֵלָ֖ו מִפּ֣וֹ וּמִפּ֑וֹ וּשְׁמֹנֶ֥ה מַעֲל֖וֹת "
             "מַעֲלָֽו׃")
DEU_17_12 = ("וְהָאִ֞ישׁ אֲשֶׁר־יַעֲשֶׂ֣ה בְזָד֗וֹן לְבִלְתִּ֨י שְׁמֹ֤עַ אֶל־הַכֹּהֵן֙ הָעֹמֵ֞ד לְשָׁ֤רֶת שָׁם֙ "
             "אֶת־יְהֹוָ֣ה אֱלֹהֶ֔יךָ א֖וֹ אֶל־הַשֹּׁפֵ֑ט וּמֵת֙ הָאִ֣ישׁ הַה֔וּא וּבִֽעַרְתָּ֥ הָרָ֖ע מִיִּשְׂרָאֵֽל׃")
# Verses of the independent review's examples (fix round of 18 Nov 2026)
SAM1_15_22 = ("וַיֹּ֣אמֶר שְׁמוּאֵ֗ל הַחֵ֤פֶץ לַֽיהֹוָה֙ בְּעֹל֣וֹת וּזְבָחִ֔ים "
              "כִּשְׁמֹ֖עַ בְּק֣וֹל יְהֹוָ֑ה הִנֵּ֤ה שְׁמֹ֙עַ֙ מִזֶּ֣בַח ט֔וֹב "
              "לְהַקְשִׁ֖יב מֵחֵ֥לֶב אֵילִֽים׃")
CHR2_1_5 = ("וּמִזְבַּ֣ח הַנְּחֹ֗שֶׁת אֲשֶׁ֤ר עָשָׂה֙ בְּצַלְאֵל֙ בֶּן־אוּרִ֣י "
            "בֶן־ח֔וּר שָׁ֕ם לִפְנֵ֖י מִשְׁכַּ֣ן יְהֹוָ֑ה וַיִּדְרְשֵׁ֥הוּ "
            "שְׁלֹמֹ֖ה וְהַקָּהָֽל׃")
PS_123_4 = ("רַבַּת֮ שָֽׂבְעָה־לָּ֢הּ נַ֫פְשֵׁ֥נוּ הַלַּ֥עַג הַשַּֽׁאֲנַנִּ֑ים "
            "הַ֝בּ֗וּז (לגאיונים) לִגְאֵ֥י יוֹנִֽים׃")
SAM2_18_4 = ("וַיֹּ֤אמֶר אֲלֵיהֶם֙ הַמֶּ֔לֶךְ אֲשֶׁר־יִיטַ֥ב בְּעֵינֵיכֶ֖ם אֶעֱשֶׂ֑ה "
             "וַיַּעֲמֹ֤ד הַמֶּ֙לֶךְ֙ אֶל־יַ֣ד הַשַּׁ֔עַר וְכׇל־הָעָם֙ יָֽצְא֔וּ "
             "לְמֵא֖וֹת וְלַאֲלָפִֽים׃")
EXO_17_15 = "וַיִּ֥בֶן מֹשֶׁ֖ה מִזְבֵּ֑חַ וַיִּקְרָ֥א שְׁמ֖וֹ יְהֹוָ֥ה ׀ נִסִּֽי׃"
ISA_19_5 = "וְנִשְּׁתוּ־מַ֖יִם מֵֽהַיָּ֑ם וְנָהָ֖ר יֶחֱרַ֥ב וְיָבֵֽשׁ׃"
# Verses of the independent final check's examples (fix round 2, 18 Nov 2026)
SONG_2_1 = "אֲנִי֙ חֲבַצֶּ֣לֶת הַשָּׁר֔וֹן שֽׁוֹשַׁנַּ֖ת הָעֲמָקִֽים׃"
JOS_12_18 = "מֶ֤לֶךְ אֲפֵק֙ אֶחָ֔ד מֶ֥לֶךְ לַשָּׁר֖וֹן אֶחָֽד׃"
KGS2_23_36 = ("בֶּן־עֶשְׂרִ֨ים וְחָמֵ֤שׁ שָׁנָה֙ יְהוֹיָקִ֣ים בְּמׇלְכ֔וֹ וְאַחַ֤ת עֶשְׂרֵה֙ שָׁנָ֔ה מָלַ֖ךְ "
              "בִּירוּשָׁלָ֑‍ִם וְשֵׁ֣ם אִמּ֔וֹ (זבידה) זְבוּדָּ֥ה בַת־פְּדָיָ֖ה מִן־רוּמָֽה׃")
KGS1_22_8 = ("וַיֹּ֣אמֶר מֶלֶךְ־יִשְׂרָאֵ֣ל ׀ אֶֽל־יְהוֹשָׁפָ֡ט ע֣וֹד אִישׁ־אֶחָ֡ד לִדְרֹשׁ֩ אֶת־יְהֹוָ֨ה מֵאֹת֜וֹ "
             "וַאֲנִ֣י שְׂנֵאתִ֗יו כִּ֠י לֹא־יִתְנַבֵּ֨א עָלַ֥י טוֹב֙ כִּ֣י אִם־רָ֔ע מִיכָ֖יְהוּ בֶּן־יִמְלָ֑ה "
             "וַיֹּ֙אמֶר֙ יְה֣וֹשָׁפָ֔ט אַל־יֹאמַ֥ר הַמֶּ֖לֶךְ כֵּֽן׃")
GEN_14_17 = ("וַיֵּצֵ֣א מֶֽלֶךְ־סְדֹם֮ לִקְרָאתוֹ֒ אַחֲרֵ֣י שׁוּב֗וֹ מֵֽהַכּוֹת֙ אֶת־כְּדׇרְלָעֹ֔מֶר וְאֶת־הַמְּלָכִ֖ים "
             "אֲשֶׁ֣ר אִתּ֑וֹ אֶל־עֵ֣מֶק שָׁוֵ֔ה ה֖וּא עֵ֥מֶק הַמֶּֽלֶךְ׃")
GEN_19_29 = ("וַיְהִ֗י בְּשַׁחֵ֤ת אֱלֹהִים֙ אֶת־עָרֵ֣י הַכִּכָּ֔ר וַיִּזְכֹּ֥ר אֱלֹהִ֖ים אֶת־אַבְרָהָ֑ם וַיְשַׁלַּ֤ח "
             "אֶת־לוֹט֙ מִתּ֣וֹךְ הַהֲפֵכָ֔ה בַּהֲפֹךְ֙ אֶת־הֶ֣עָרִ֔ים אֲשֶׁר־יָשַׁ֥ב בָּהֵ֖ן לֽוֹט׃")
ISA_3_24 = ("וְהָיָה֩ תַ֨חַת בֹּ֜שֶׂם מַ֣ק יִֽהְיֶ֗ה וְתַ֨חַת חֲגוֹרָ֤ה נִקְפָּה֙ וְתַ֨חַת מַעֲשֶׂ֤ה מִקְשֶׁה֙ "
            "קׇרְחָ֔ה וְתַ֥חַת פְּתִיגִ֖יל מַֽחֲגֹ֣רֶת שָׂ֑ק כִּי־תַ֖חַת יֹֽפִי׃")
GEN_13_7 = ("וַֽיְהִי־רִ֗יב בֵּ֚ין רֹעֵ֣י מִקְנֵֽה־אַבְרָ֔ם וּבֵ֖ין רֹעֵ֣י מִקְנֵה־ל֑וֹט וְהַֽכְּנַעֲנִי֙ "
            "וְהַפְּרִזִּ֔י אָ֖ז יֹשֵׁ֥ב בָּאָֽרֶץ׃")
NUM_23_8 = "מָ֣ה אֶקֹּ֔ב לֹ֥א קַבֹּ֖ה אֵ֑ל וּמָ֣ה אֶזְעֹ֔ם לֹ֥א זָעַ֖ם יְהֹוָה׃"
NEH_11_8 = "וְאַחֲרָ֖יו גַּבַּ֣י סַלָּ֑י תְּשַׁ֥ע מֵא֖וֹת עֶשְׂרִ֥ים וּשְׁמֹנָֽה׃"
JDG_4_21 = ("וַתִּקַּ֣ח יָעֵ֣ל אֵֽשֶׁת־חֶ֠בֶר אֶת־יְתַ֨ד הָאֹ֜הֶל וַתָּ֧שֶׂם אֶת־הַמַּקֶּ֣בֶת בְּיָדָ֗הּ וַתָּב֤וֹא "
            "אֵלָיו֙ בַּלָּ֔אט וַתִּתְקַ֤ע אֶת־הַיָּתֵד֙ בְּרַקָּת֔וֹ וַתִּצְנַ֖ח בָּאָ֑רֶץ וְהֽוּא־נִרְדָּ֥ם וַיָּ֖עַף "
            "וַיָּמֹֽת׃")
# Verses of the parsing layer (TokenTag.morph / src, 18 Nov 2026)
PS_8_4 = "כִּֽי־אֶרְאֶ֣ה שָׁ֭מֶיךָ מַעֲשֵׂ֣ה אֶצְבְּעֹתֶ֑יךָ יָרֵ֥חַ וְ֝כוֹכָבִ֗ים אֲשֶׁ֣ר כּוֹנָֽנְתָּה׃"
JDG_19_4 = ("וַיַּחֲזֶק־בּ֤וֹ חֹתְנוֹ֙ אֲבִ֣י הַֽנַּעֲרָ֔ה וַיֵּ֥שֶׁב אִתּ֖וֹ שְׁלֹ֣שֶׁת יָמִ֑ים וַיֹּאכְלוּ֙ וַיִּשְׁתּ֔וּ "
            "וַיָּלִ֖ינוּ שָֽׁם׃")
PS_35_21 = "וַיַּרְחִ֥יבוּ עָלַ֗י פִּ֫יהֶ֥ם אָ֭מְרוּ הֶאָ֣ח ׀ הֶאָ֑ח רָֽאֲתָ֥ה עֵינֵֽנוּ׃"
PS_37_23 = "מֵ֭יְהֹוָה מִֽצְעֲדֵי־גֶ֥בֶר כּוֹנָ֗נוּ וְדַרְכּ֥וֹ יֶחְפָּֽץ׃"
PRO_7_15 = "עַל־כֵּ֭ן יָצָ֣אתִי לִקְרָאתֶ֑ךָ לְשַׁחֵ֥ר פָּ֝נֶ֗יךָ אֶמְצָאֶֽךָּ׃"


def tag(slug: str, ch: int, v: int, text: str):
    return H.tag_chapter(slug, ch, {v: text})[v]


def nfd(text: str) -> str:
    """Canonical order of the points (the lexicon and a typed literal may order dagesh / vowel
    differently)."""
    return unicodedata.normalize("NFD", text)


def by_surface(tags, surface_consonants: str):
    """The tags whose surface has these consonants (finals folded)."""
    from studio.lexica import hebrew_consonants
    want = hebrew_consonants(surface_consonants)
    return [t for t in tags if hebrew_consonants(t.surface) == want]


@unittest.skipUnless(HAVE_OSHB, "OSHB MorphHB / Hebrew Lexicon not present")
class TestContract(unittest.TestCase):
    def test_genesis_1_1(self) -> None:
        tags = tag("genesis", 1, 1, GEN_1_1)
        self.assertEqual([t.surface for t in tags], tokenize_verse(GEN_1_1, "heb"))
        self.assertEqual([t.index for t in tags], list(range(1, 8)))
        self.assertEqual([t.lemma_key for t in tags],
                         ["H7225", "H1254a", "H0430", "H0853", "H8064", "H0853", "H0776"])
        self.assertTrue(all(t.method == "gold-aligned" and t.confidence == 1.0 for t in tags))
        self.assertEqual(tags[0].prefixes, ("P:b",))
        self.assertEqual(tags[4].prefixes, ("P:h",))
        self.assertEqual(tags[5].prefixes, ("P:w",))
        self.assertEqual(tags[6].prefixes, ("P:h",))
        self.assertFalse(tags[3].is_content)      # object marker
        self.assertTrue(tags[2].is_content)

    def test_one_tag_per_token_and_keys_in_lexicon(self) -> None:
        lex = H.load_lexicon()
        for slug, ch, v, text in (("genesis", 8, 17, GEN_8_17), ("daniel", 2, 5, DAN_2_5),
                                  ("2-kings", 18, 17, KGS2_18_17), ("job", 7, 5, JOB_7_5)):
            tags = tag(slug, ch, v, text)
            self.assertEqual([t.surface for t in tags], tokenize_verse(text, "heb"))
            self.assertEqual([t.index for t in tags], list(range(1, len(tags) + 1)))
            for t in tags:
                if t.lemma_key is None:
                    self.assertEqual(t.method, "untagged")
                else:
                    self.assertIn(t.lemma_key, lex)

    def test_lexicon_fields(self) -> None:
        lex = H.load_lexicon()
        self.assertGreater(len(lex), 9000)
        for key, e in lex.items():
            self.assertEqual(e.lemma_key, key)
            self.assertIn(e.lang, ("heb", "arc"))
            self.assertIn(e.pos, POS_TAGS)
            self.assertIn(e.root_source, ("OSHB-BDB", "self"))
            self.assertIn("CC BY 4.0", e.source)
            self.assertTrue(e.root_key.startswith(("heb:", "arc:")), key)
            self.assertTrue(e.lemma)

    def test_ketiv_dropped_qere_tagged(self) -> None:
        tags = tag("genesis", 8, 17, GEN_8_17)
        self.assertFalse(by_surface(tags, "הוצא"))
        q = by_surface(tags, "היצא")
        self.assertEqual(len(q), 1)
        self.assertEqual(q[0].lemma_key, "H3318")
        self.assertIn("qere", q[0].notes)


@unittest.skipUnless(HAVE_OSHB, "OSHB MorphHB / Hebrew Lexicon not present")
class TestRegressions(unittest.TestCase):
    """Wrong tags found while building the tagger (18 Nov 2026) must stay fixed."""

    def test_studio_reading_unlike_wlc_not_guessed_from_dictionary(self) -> None:
        # WLC לְכָה "come!" (H1980); the Studio prints לְךָ, which elsewhere is "to you" (H9005)
        t = by_surface(tag("numbers", 23, 13, NUM_23_13), "לך")
        self.assertEqual(len(t), 1)
        self.assertIsNone(t[0].lemma_key)

    def test_split_compound_pieces_not_tagged_as_other_words(self) -> None:
        tags = tag("2-kings", 6, 25, KGS2_6_25)
        for piece in ("דב", "יונים"):     # WLC דִּבְיוֹנִים (H1686); not "bear" / "doves"
            t = by_surface(tags, piece)
            self.assertEqual(len(t), 1)
            self.assertNotIn(t[0].lemma_key, ("H1677", "H3123"))
            self.assertIsNone(t[0].lemma_key)
        tags = tag("daniel", 1, 13, DAN_1_13)
        self.assertIsNone(by_surface(tags, "פת")[0].lemma_key)     # not H6595a "morsel"
        self.assertEqual(by_surface(tags, "בג")[0].lemma_key, "H6598")

    def test_ketiv_residue_untagged(self) -> None:
        t = by_surface(tag("job", 7, 5, JOB_7_5), "יש")      # "(וג)יש": text defect, not יֵשׁ
        self.assertEqual(len(t), 1)
        self.assertIsNone(t[0].lemma_key)

    def test_merged_name_tagged_two_lemmas_not(self) -> None:
        t = by_surface(tag("2-kings", 18, 17, KGS2_18_17), "רבשקה")   # WLC רַב־שָׁקֵה
        self.assertEqual(t[0].lemma_key, "H7262")
        t = by_surface(tag("psalms", 102, 4, PS_102_4), "כמוקד")      # WLC כְּמוֹ קֵד: two lemmas
        self.assertIsNone(t[0].lemma_key)

    def test_prefixes_follow_studio_letters(self) -> None:
        t = by_surface(tag("job", 36, 12, JOB_36_12), "בבלי")         # WLC כִּבְלִי
        self.assertEqual(t[0].lemma_key, "H1097")
        self.assertEqual(t[0].prefixes, ("P:b",))

    def test_aramaic_final_aleph_he(self) -> None:
        tags = tag("daniel", 2, 5, DAN_2_5)
        self.assertEqual(by_surface(tags, "מלתה")[0].lemma_key, "H4406")   # WLC מִלְּתָא
        self.assertFalse(by_surface(tags, "לכשדיא"))                         # ketiv dropped
        self.assertEqual(by_surface(tags, "לכשדאי")[0].lemma_key, "H3779")

    def test_plene_defective_and_aligned_lemma_wins(self) -> None:
        t = by_surface(tag("genesis", 45, 15, GEN_45_15), "עלהם")     # WLC עֲלֵיהֶם
        self.assertEqual((t[0].lemma_key, t[0].confidence), ("H5921a", 0.95))
        t = by_surface(tag("ezekiel", 40, 34, EZK_40_34), "אלו")      # WLC אֵלָיו: pillars, not "to him"
        self.assertEqual(t[0].lemma_key, "H0352b")

    def test_bare_strongs_number_left_untagged_when_ambiguous(self) -> None:
        t = by_surface(tag("deuteronomy", 17, 12, DEU_17_12), "הרע")  # OSHB "7451" (a/b/c)
        self.assertIsNone(t[0].lemma_key)

    def test_aramaic_kol(self) -> None:
        t = by_surface(tag("daniel", 2, 12, DAN_2_12), "כל")
        self.assertEqual(t[0].lemma_key, "H3606")
        self.assertEqual(H.load_lexicon()["H3606"].lang, "arc")

    def test_form_dictionary_pointed_and_language_filtered(self) -> None:
        self.assertEqual(H.form_lookup("כָּל", "arc")[0], "H3606")
        self.assertEqual(H.form_lookup("כָּל", "heb")[0], "H3605")
        self.assertIsNone(H.form_lookup("דֻּבֻּר")[0])   # consonants attested, pointing not: no guess


@unittest.skipUnless(HAVE_OSHB, "OSHB MorphHB / Hebrew Lexicon not present")
class TestRoots(unittest.TestCase):
    def setUp(self) -> None:
        self.lex = H.load_lexicon()

    def test_bdb_families(self) -> None:
        lex = self.lex
        self.assertEqual(lex["H7225"].root_key, lex["H7218a"].root_key)
        self.assertEqual(lex["H7218a"].root_label, "ר-א-שׁ I")
        self.assertEqual(lex["H1697"].root_key, lex["H1696"].root_key)
        self.assertEqual(lex["H3212"].root_key, lex["H1980"].root_key)
        self.assertEqual(lex["H6918"].root_key, lex["H4720"].root_key)
        self.assertEqual(lex["H1697"].root_source, "OSHB-BDB")

    def test_homographs_kept_apart(self) -> None:
        lex = self.lex
        self.assertNotEqual(lex["H1254a"].root_key, lex["H1254b"].root_key)   # I / II ברא
        self.assertNotEqual(lex["H3372"].root_key, lex["H3384a"].root_key)    # fear / shoot
        self.assertNotEqual(lex["H2654a"].root_key, lex["H2654b"].root_key)   # delight / bend
        self.assertNotIn(".", lex["H1697"].root_key)

    def test_self_family_and_aramaic(self) -> None:
        lex = self.lex
        self.assertEqual((lex["H9005"].root_key, lex["H9005"].root_source), ("heb:H9005", "self"))
        self.assertEqual(lex["H0426"].lang, "arc")
        self.assertTrue(lex["H4406"].root_key.startswith("arc:"))
        self.assertEqual(lex["arc:H9005"].lang, "arc")
        self.assertEqual(H.hyphenate_root("ראשׁ"), "ר-א-שׁ")


@unittest.skipUnless(HAVE_OSHB, "OSHB MorphHB / Hebrew Lexicon not present")
class TestFunctionWords(unittest.TestCase):
    def test_lists(self) -> None:
        fk = set(H.function_word_keys())
        for k in ("H0853", "H0834a", "H3808", "H0413", "H9005", "H1931", "H5921a", "H3588a", "H8478"):
            self.assertIn(k, fk)
        for k in ("H0430", "H1697", "H3068", "H3818", "H0516", "H7225"):
            self.assertNotIn(k, fk)


@unittest.skipUnless(HAVE_OSHB, "OSHB MorphHB / Hebrew Lexicon not present")
class TestLicenceHygiene(unittest.TestCase):
    def test_no_quarantined_sources(self) -> None:
        src = (ROOT / "studio" / "lexica" / "hebrew.py").read_text(encoding="utf-8")
        for name in ("BHSA", "ETCBC", "PROIEL", "Rahlfs", "CCAT", "05_Tier5", "local-nc-only"):
            self.assertNotIn(name, src)

    def test_tbesh_gloss_is_column_7(self) -> None:
        if H.tbesh_path() is None:
            self.skipTest("TBESH not present")
        self.assertEqual(H._tbesh_glosses().get("H0001"), "father")


@unittest.skipUnless(HAVE_OSHB and HAVE_MACULA, "OSHB or MACULA Hebrew not present")
class TestLxxEquivalents(unittest.TestCase):
    def test_known_equivalents(self) -> None:
        lx = H.lxx_equivalents()
        lex = H.load_lexicon()
        self.assertIn("G0746", lx["H7225"])
        self.assertEqual(lx["H0430"].most_common(1)[0][0], "G2316")
        self.assertEqual(lx["H3068"].most_common(1)[0][0], "G2962")
        self.assertEqual(lx["H7307"].most_common(1)[0][0], "G4151")
        self.assertTrue(set(lx) <= set(lex))
        self.assertTrue(all(re.fullmatch(r"G\d{4}", g) for c in lx.values() for g in c))


@unittest.skipUnless(HAVE_OSHB and LIVE_DB.exists(), "OSHB corpora or the Studio database not present")
class TestWholeOldTestament(unittest.TestCase):
    def test_coverage_on_live_db(self) -> None:
        conn = H.open_studio_db_readonly(LIVE_DB)
        try:
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute("CREATE TABLE _must_not_exist (x)")
            lex = H.load_lexicon()
            legend = H.morph_legend()
            methods: Counter = Counter()
            parsed: Counter = Counter()
            chapters = 0
            for slug, ch, verses in H.iter_all(conn):
                chapters += 1
                for v, tags in verses.items():
                    self.assertEqual([t.index for t in tags], list(range(1, len(tags) + 1)))
                    for t in tags:
                        methods[t.method] += 1
                        if t.lemma_key is not None:
                            self.assertIn(t.lemma_key, lex)
                        if t.morph is not None:
                            parsed[t.method] += 1
                            self.assertTrue(t.morph.startswith("O:"), t.morph)
                            self.assertTrue(legend.get(t.morph), t.morph)       # every code has English
                            self.assertTrue((t.src or "").startswith("oshb:"), (slug, ch, v, t.surface))
                            self.assertIsNotNone(t.lemma_key)
                        if t.method == "untagged":
                            self.assertIsNone(t.morph)
        finally:
            conn.close()
        total = sum(methods.values())
        self.assertEqual(chapters, 929)
        self.assertGreater(total, 300000)
        self.assertGreaterEqual(methods["gold-aligned"] / total, 0.995)
        self.assertLessEqual(methods["untagged"] / total, 0.0005)
        # 18 Nov 2026: 305,139 of 305,476 tokens carry an OSHB parse (99.89 %)
        self.assertGreaterEqual(sum(parsed.values()) / total, 0.998)


@unittest.skipUnless(HAVE_OSHB, "OSHB MorphHB / Hebrew Lexicon not present")
class TestReviewFixes(unittest.TestCase):
    """The independent review of 18 Nov 2026 (minor issues / refuted claims) must stay fixed."""

    def test_interrogative_he_coded_from_morphology(self) -> None:
        # OSHB lemma 'd/2656' (article letter) but morph 'HTi/...': interrogative, not the article
        self.assertEqual(H._analyse("d/2656", "HTi/Ncmsa", "heb")[1], ("P:i",))
        self.assertEqual(H._analyse("d/2656", "HTd/Ncmsa", "heb")[1], ("P:h",))
        self.assertEqual(H._analyse("i/2962", "HTd/D", "heb")[1], ("P:i",))     # lemma 'i' stays P:i
        t = by_surface(tag("1-samuel", 15, 22, SAM1_15_22), "החפץ")
        self.assertEqual((t[0].lemma_key, t[0].prefixes), ("H2656", ("P:i",)))
        # every OSHB word with lemma prefix 'd' and morph 'Ti' (82 Studio tokens in the review) is P:i
        corpus = H.oshb_corpus()
        n = 0
        for words in corpus.reading.values():
            for w in words:
                parts = [p.strip() for p in w.lemma.split("/") if p.strip()]
                segs = w.morph[1:].split("/") if w.morph else []
                if any(p == "d" and i < len(segs) and segs[i] == "Ti" for i, p in enumerate(parts[:-1])):
                    n += 1
                    self.assertIn("P:i", w.prefixes, w.wid)
                    self.assertNotIn("P:h", w.prefixes, w.wid)
        self.assertGreater(n, 80)

    def test_studio_pointing_of_another_word(self) -> None:
        # 2 Chr 1:5: Studio שָׁם "there", WLC שָׂם "put" (H7760a) -- the Studio's vowels decide
        t = by_surface(tag("2-chronicles", 1, 5, CHR2_1_5), "שם")
        self.assertEqual((t[0].lemma_key, t[0].method), ("H8033", "gold-form"))
        self.assertIn("other vowels", t[0].notes[0])
        # Exod 17:15: יְהֹוָה (Studio) / יְהוָה (WLC) are both H3068 elsewhere, so the name
        # יְהוָה נִסִּי keeps OSHB's H3071
        t = by_surface(tag("exodus", 17, 15, EXO_17_15), "יהוה")
        self.assertEqual((t[0].lemma_key, t[0].method), ("H3071", "gold-aligned"))

    def test_qere_pieces_of_a_joined_ketiv_not_tagged_with_its_lemma(self) -> None:
        # Ps 123:4: ketiv לגאיונים (גַּאֲיוֹן H1349, one word in WLC), qere לִגְאֵי יוֹנִים
        tags = tag("psalms", 123, 4, PS_123_4)
        for piece in ("לגאי", "יונים"):
            t = by_surface(tags, piece)
            self.assertEqual(len(t), 1)
            self.assertIsNone(t[0].lemma_key)
            self.assertEqual(t[0].method, "untagged")
        self.assertFalse(by_surface(tags, "לגאיונים"))
        # a split that is no qere still takes the WLC lemma (Dan 1:13 בַּג = פַּתְבַּג)
        self.assertEqual(by_surface(tag("daniel", 1, 13, DAN_1_13), "בג")[0].lemma_key, "H6598")

    def test_oshb_lemma_corrections(self) -> None:
        expected = {"10V7e": "H3318", "04g9U": "H7311a", "04dCx": "H6944", "10bEm": "H6455", "11s71": "H8193",
                    "04yhZ": "H4994", "09QUD": "H4994", "13nVn": "H3824", "13rN2": "H8003", "231W5": "H5405",
                    "23Fm5": "H3001", "24FGD": "H1121a", "234TA": "H6726"}
        corpus = H.oshb_corpus()
        lex = H.load_lexicon()
        found = {}
        for words in corpus.all_words.values():
            for w in words:
                if w.wid in H.OSHB_LEMMA_CORRECTIONS:
                    found[w.wid] = w
        self.assertEqual(set(found), set(H.OSHB_LEMMA_CORRECTIONS))
        for wid, w in found.items():
            self.assertIn(w.key, lex, wid)
            if wid in expected:
                self.assertEqual(w.key, expected[wid], wid)
        t = by_surface(tag("2-samuel", 18, 4, SAM2_18_4), "יצאו")       # not יָרַד "come down"
        self.assertEqual(t[0].lemma_key, "H3318")
        self.assertTrue(any("corrected" in n for n in t[0].notes))
        t = by_surface(tag("numbers", 23, 13, NUM_23_13), "נא")          # not יָלַךְ "walk"
        self.assertEqual(t[0].lemma_key, "H4994")
        tags = tag("isaiah", 19, 5, ISA_19_5)                            # OSHB swapped the two verbs
        self.assertEqual(by_surface(tags, "ונשתו")[0].lemma_key, "H5405")
        self.assertEqual(by_surface(tags, "ויבש")[0].lemma_key, "H3001")

    def test_display_glosses_from_tbesh(self) -> None:
        lex = H.load_lexicon()
        if H.tbesh_path() is not None:
            want = {"H0430": "God", "H1961": "to be", "H0559": "to say", "H1697": "word", "H3068": "LORD",
                    "H3588a": "for", "H0996": "between", "H4428": "king", "H7586": "Saul",
                    "H3227b": "Benjaminite", "H5483b": "horse"}
            for key, gloss in want.items():
                self.assertEqual(lex[key].gloss, gloss, key)
                self.assertIn("TBESH col. 7 Gloss", lex[key].source)
            self.assertNotIn(lex["H0681"].gloss, ("conjunction",))   # אֵצֶל
            self.assertNotIn(lex["H3587"].gloss, ("burning",))       # כִּי "branding"
            self.assertEqual(lex["H3881"].gloss, "Levite")           # TBESH only has 'a Name of' Levi
            self.assertEqual(lex["H0853"].gloss, "mark of the accusative")   # TBESH '[Obj.]' is no gloss
        self.assertTrue(all(e.gloss for e in lex.values()))
        invisible = re.compile("[͏​-‏⁠﻿­]")
        self.assertFalse([k for k, e in lex.items() if invisible.search(e.lemma + e.root_label + e.formula)])
        self.assertNotIn("͏", lex["H3389"].lemma)                 # Jerusalem had a grapheme joiner
        self.assertEqual(H.pointed_key(lex["H3389"].lemma), H.pointed_key("יְרוּשָׁלִַם"))

    def test_one_root_gloss_per_family_and_none_empty(self) -> None:
        lex = H.load_lexicon()
        by_key = {}
        for e in lex.values():
            by_key.setdefault(e.root_key, set()).add(e.root_gloss)
        self.assertEqual([k for k, g in by_key.items() if len(g) > 1], [])
        self.assertEqual([k for k, e in lex.items() if e.root_source == "OSHB-BDB" and not e.root_gloss], [])
        for key in ("H7307", "H5315", "H6944", "H6664"):           # BDB 'new' roots רוח נפשׁ קדשׁ צדק
            self.assertTrue(lex[key].root_gloss, key)
        self.assertEqual(lex["H4428"].root_gloss, lex["H4427a"].gloss)    # מלך I: the verb, not BDB's cognate
        self.assertEqual(lex["H1323"].root_gloss, lex["H1121a"].gloss)    # בַּת in the family of בֵּן

    def test_function_word_particles(self) -> None:
        fk = set(H.function_word_keys())
        for k in ("H3605", "H3606", "H2088", "H2063", "H0428", "H4100", "H4310", "H2009", "H2005", "H1571",
                  "H3651c", "H0389", "H7535", "H0637"):
            self.assertIn(k, fk)
        for k in ("H3651a", "H7534", "H3426"):                # כֵּן "honest", רַק "thin", יֵשׁ
            self.assertNotIn(k, fk)
        self.assertIn("H2004", fk)                             # הֵן "they (fem.)": a pronoun (final check)
        t = by_surface(tag("genesis", 8, 17, GEN_8_17), "כל")
        self.assertTrue(t and not any(x.is_content for x in t))
        self.assertEqual(H.load_lexicon()["H4136"].pos, "PREP")   # מוּל: the index says PROPN, OSHB says R

    def test_root_families_follow_bdb(self) -> None:
        lex = H.load_lexicon()
        self.assertEqual(lex["H0258"].root_key, lex["H2300a"].root_key)    # אָחַד filed under חָדַד
        self.assertNotEqual(lex["H8638"].root_key, lex["H7275"].root_key)  # תִּרְגֵּם is no רָגַם "stone"
        self.assertEqual(lex["H8638"].root_source, "self")
        self.assertNotEqual(lex["H3736"].root_key, lex["H3525"].root_key)  # כרבל / כֶּבֶל
        self.assertNotEqual(lex["H7876"].root_key, lex["H5382"].root_key)  # שָׁיָה / נָשָׁה
        self.assertNotEqual(lex["H5094a"].root_key, lex["H5103"].root_key)  # Aramaic "light" / "river"
        self.assertEqual(lex["H5094a"].root_key, lex["H5094b"].root_key)
        for k in ("H0739", "H0740", "H0691"):                             # with אֲרִי "lion" (I ארה)
            self.assertEqual(lex[k].root_key, lex["H0738a"].root_key, k)
        self.assertEqual(lex["H0741"].root_key, lex["H2025"].root_key)     # II ארה "hearth"
        self.assertNotEqual(lex["H0741"].root_key, lex["H0739"].root_key)
        self.assertEqual(lex["H0824"].root_key, lex["H8172"].root_key)     # אֶשְׁעָן under שָׁעַן
        # BDB heads the "fire" family with אֵשׁ itself; the index's root אנש is not BDB's
        self.assertEqual((lex["H0800"].root_key, lex["H0801"].root_key), ("heb:H0784", "heb:H0784"))
        self.assertEqual(lex["H0784"].root_label, lex["H0784"].lemma)
        # BDB's "I. אֵל" (these) numbers the word: no 'I' on the root, apart from אֱלֹהִים's א-ל-ה I
        # (and, since the final check, the head word tells it from the family of אֵלֶּה "these")
        self.assertEqual(lex["H0430"].root_label, "א-ל-ה I")
        self.assertEqual(nfd(lex["H0411"].root_label), nfd("א-ל-ה (these, אֵל)"))
        self.assertEqual(nfd(lex["H0428"].root_label), nfd("א-ל-ה (these, אֵלֶּה)"))
        self.assertNotEqual(lex["H0411"].root_key, lex["H0430"].root_key)
        self.assertNotEqual(lex["H0853"].root_key, lex["H0225"].root_key)
        self.assertTrue(H.root_notes("H0258"))
        # no family spans two of BDB's Hebrew root sections any more
        bdbx, _roots = H._bdb_index()
        sections = {}
        for k, e in lex.items():
            li = H._entry_for_key(k)
            b = bdbx.get(li.bdb) if li is not None else None
            if b is not None and b.lang == "heb" and b.section:
                sections.setdefault(e.root_key, set()).add(b.section)
        self.assertEqual(sorted(rk for rk, s in sections.items() if len(s) > 1), [])


@unittest.skipUnless(HAVE_OSHB and HAVE_MACULA, "OSHB or MACULA Hebrew not present")
class TestLxxFunctionWordNoise(unittest.TestCase):
    def test_content_lemmas_not_ranked_by_greek_article(self) -> None:
        lx = H.lxx_equivalents()
        fk = set(H.function_word_keys())
        bad = [k for k, c in lx.items() if k not in fk and c.most_common(1)[0][0] in H.GREEK_FUNCTION_STRONGS]
        self.assertEqual(bad, [])
        self.assertEqual(lx["H7453"].most_common(1)[0][0], "G4139")   # רֵעַ: πλησίον, not ὁ
        self.assertEqual(lx["H0136"].most_common(1)[0][0], "G2962")   # אֲדֹנָי: κύριος
        self.assertEqual(lx["H8065"].most_common(1)[0][0], "G3772")   # Aramaic שָׁמַיִן: οὐρανός
        self.assertNotIn("G3588", lx["H0430"])


_RESIDUE = re.compile(r"Compare|See also|\bSee\b|margin|correction|including the article|\d|`|\(\s*\)")


@unittest.skipUnless(HAVE_OSHB, "OSHB MorphHB / Hebrew Lexicon not present")
class TestFinalCheckFixes(unittest.TestCase):
    """The independent final check of 18 Nov 2026 (reader-facing glosses, labels, families) must
    stay fixed.  Lemma tags are not touched by these fixes."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.lex = H.load_lexicon()
        cls.fk = set(H.function_word_keys())

    def gloss_of(self, slug: str, ch: int, v: int, text: str, surface: str) -> str:
        """The display gloss of the lemma of the token(s) with these consonants (one lemma)."""
        t = by_surface(tag(slug, ch, v, text), surface)
        self.assertTrue(t, surface)
        self.assertEqual(len({x.lemma_key for x in t}), 1, surface)
        self.assertIsNotNone(t[0].lemma_key, surface)
        return self.lex[t[0].lemma_key].gloss

    # (1) proper names: the TBESH row of the bearer the occurrences belong to
    def test_name_rows_chosen_by_occurrences(self) -> None:
        if H.tbesh_path() is None or H.tipnr_path() is None:
            self.skipTest("TBESH / TIPNR not present")
        lex = self.lex
        self.assertEqual(lex["H8289"].gloss, "Sharon")                 # not TBESH's first row 'Lasharon'
        self.assertEqual(lex["H7316"].gloss, "Rumah")                  # not 'Dumah' (Josh 15:52 reads דּוּמָה)
        self.assertEqual(lex["H4321"].gloss, "Micaiah")                # 1 Kgs 22:8, x19; not 'Micah'
        self.assertEqual(lex["H7586"].gloss, "Saul")                   # still the king, not 'Shaul'
        self.assertEqual(lex["H1954"].gloss, "Hoshea")                 # 13 of 16 (Hosea the prophet: 3)
        self.assertEqual(lex["H3169"].gloss, "Jehizkiah")              # 2 Chr 28:12, not 'Hezekiah'
        self.assertIn("TIPNR", lex["H8289"].source)
        self.assertIn("TBESH col. 7 Gloss", lex["H8289"].source)
        self.assertEqual(self.gloss_of("song-of-songs", 2, 1, SONG_2_1, "השרון"), "Sharon")
        self.assertEqual(self.gloss_of("joshua", 12, 18, JOS_12_18, "לשרון"), "Sharon")   # one lemma: majority
        self.assertEqual(self.gloss_of("2-kings", 23, 36, KGS2_23_36, "רומה"), "Rumah")
        self.assertEqual(self.gloss_of("1-kings", 22, 8, KGS1_22_8, "מיכיהו"), "Micaiah")
        self.assertTrue(H._tipnr_refs().get("H8289I"))                 # TIPNR read (path past MAX_PATH)

    def test_names_not_translations_or_emendations(self) -> None:
        lex = self.lex
        want = {"H7886": "Shiloh", "H5722": "Adino", "H0401": "Ucal", "H1373": "Gabbai", "H7218b": "Rosh",
                "H8483": "Tahtim-hodshi", "H1689": "Diblah", "H7384a": "Diphath", "H1419b": "Haggedolim",
                "H3429": "Josheb-basshebeth", "H1719b": "Dedan"}
        for key, gloss in want.items():
            self.assertEqual(lex[key].gloss, gloss, key)
            self.assertEqual(lex[key].pos, "PROPN", key)
        self.assertIn("Rodanim", lex["H1721"].gloss)                     # 1 Chr 1:7 רוֹדָנִים
        self.assertIn("Dodanim", lex["H1721"].gloss)                     # Gen 10:4 דֹדָנִים
        self.assertEqual(self.gloss_of("nehemiah", 11, 8, NEH_11_8, "גבי"), "Gabbai")
        # headwords are the words of the text
        self.assertEqual(lex["H1719b"].lemma, "דְּדָן")                    # Ezek 27:15, not BDB's רֹדָן
        self.assertEqual((lex["H4325"].lemma, lex["H4325"].gloss), ("מַיִם", "water"))
        self.assertEqual(lex["H6440"].lemma, "פָּנִים")
        self.assertEqual(lex["H6440"].formula, "פ-נ-ה → פָּנִים")
        # no proper name is glossed with a TBESH translation in backticks
        if H.tbesh_path() is not None:
            for key, rows in H._tbesh_rows().items():
                for row in rows:
                    if row[2].startswith("`") and key in lex and lex[key].pos == "PROPN":
                        self.assertNotEqual(lex[key].gloss, row[2].strip("`"), key)
        lower = sorted(k for k, e in lex.items() if e.pos == "PROPN" and e.gloss[:1].islower())
        self.assertLessEqual(len(lower), 10, lower)                      # TBESH's own renderings ('governors')

    # (2) misleading lemma-level glosses
    def test_misleading_glosses_corrected(self) -> None:
        lex = self.lex
        self.assertEqual(lex["H7125"].gloss, "meeting; toward")          # לִקְרַאת, not 'befall'
        self.assertIn("army", lex["H2426"].gloss)                        # חֵיל 'army of'
        self.assertIn("put to shame", lex["H3001"].gloss)                # הֹבִישׁ
        self.assertIn("curse", lex["H5344a"].gloss)                      # אֶקֹּב
        self.assertIn("hot", lex["H3179"].gloss)                         # 1 Kgs 1:1 יִחַם
        self.assertIn("weary", lex["H5774a"].gloss)                      # Judg 4:21 וַיָּעַף
        self.assertIn("full", lex["H4395"].gloss.split(";")[0])          # Isa 1:21 מְלֵאֲתִי
        self.assertEqual(lex["H3426"].gloss, "there is")                 # יֵשׁ
        self.assertTrue(lex["H0410"].gloss.startswith("God"))            # אֵל: 205 of 245 name God
        self.assertEqual(lex["H0430"].gloss, "God")
        self.assertEqual(self.gloss_of("genesis", 14, 17, GEN_14_17, "לקראתו"), "meeting; toward")
        self.assertIn("curse", self.gloss_of("numbers", 23, 8, NUM_23_8, "אקב"))
        self.assertIn("weary", self.gloss_of("judges", 4, 21, JDG_4_21, "ויעף"))
        # the root's own meaning stays the family meaning
        self.assertEqual(lex["H3001"].root_gloss, "to dry up")
        self.assertEqual(lex["H5774a"].root_gloss, "to fly")
        for key, (gloss, pos, why) in H.GLOSS_OVERRIDES.items():
            self.assertIn(key, lex, key)
            self.assertEqual(lex[key].gloss, gloss, key)
            self.assertTrue(why, key)
            self.assertIn("GLOSS_OVERRIDES", lex[key].source, key)
            if pos:
                self.assertEqual(lex[key].pos, pos, key)

    # (3) residue and typos
    def test_no_gloss_residue_or_typos(self) -> None:
        lex = self.lex
        self.assertEqual([k for k, e in lex.items() if _RESIDUE.search(e.gloss)], [])
        self.assertEqual(lex["H2361"].gloss, "Hiram")                    # was 'Huram. Compare'
        self.assertEqual(lex["H3060"].gloss, "Jehoash")
        self.assertEqual(lex["H8020"].gloss, "Shalman")                  # Hos 10:14
        self.assertEqual(lex["H4319"].gloss, "Micaiah")                  # was 'Micaiah (2 Chronicles 18:8)'
        self.assertEqual(lex["H3265"].gloss, "Jair")                     # was 'Jair(from the margin)'
        self.assertEqual(lex["H8445"].gloss, "Tikvath")                  # was 'Tikvath (by correction for )'
        self.assertEqual(lex["H4447"].gloss, "Hammoleketh")
        self.assertEqual(lex["H5626"].gloss, "Sirah")
        self.assertEqual(lex["H8240a"].gloss, "ash heap")                # TBESH 'ash heep'
        self.assertEqual(lex["H0671b"].gloss, "governors")               # TBESH 'govenors'
        self.assertEqual(H._clean_def("Iddo (from the margin) See"), "Iddo")
        self.assertEqual(H._clean_def("Rôsh", is_name=True), "Rosh")

    # (4) function words and POS / gloss clashes
    def test_function_word_policy(self) -> None:
        fk = self.fk
        for k in ("H2004", "H0581a", "H1454", "H7945"):                 # pronouns: הֵן, אִנּוּן, גֵּה, שֶׁל
            self.assertIn(k, fk)
        for k in ("H3587", "H0176b"):                                    # nouns כִּי "branding", אוֹ "desire"
            self.assertNotIn(k, fk)
        for k, e in self.lex.items():
            li = H._entry_for_key(k)
            if li is not None and li.pos in H.FUNCTION_LEX_POS and H.oshb_corpus().key_freq[k]:
                self.assertIn(k, fk, k)
        t = by_surface(tag("genesis", 19, 29, GEN_19_29), "בהן")        # "in them"
        self.assertEqual((t[0].lemma_key, t[0].is_content), ("H2004", False))
        t = by_surface(tag("isaiah", 3, 24, ISA_3_24), "כי")             # "branding instead of beauty"
        self.assertEqual((t[0].lemma_key, t[0].is_content), ("H3587", True))

    def test_pos_gloss_clashes(self) -> None:
        lex = self.lex
        self.assertEqual((lex["H7473"].pos, lex["H7473"].gloss), ("N", "herdsman, shepherd"))
        self.assertEqual(lex["H7207"].pos, "N")
        self.assertEqual((lex["H7202"].pos, lex["H7202"].gloss), ("ADJ", "seeing"))
        self.assertEqual(lex["H5542"].pos, "INTERJ")                     # סֶלָה
        self.assertEqual([k for k, e in lex.items() if e.pos in ("N", "ADJ") and e.gloss.startswith("to ")], [])
        self.assertEqual(self.gloss_of("genesis", 13, 7, GEN_13_7, "רעי").split(",")[0], "herdsman")

    # (5) root display labels
    def test_root_labels_unique_within_a_language(self) -> None:
        lex = self.lex
        seen = {}
        for e in lex.values():
            seen.setdefault((e.lang, e.root_label), set()).add(e.root_key)
        self.assertEqual(sorted(k for k, v in seen.items() if len(v) > 1), [])
        self.assertEqual(lex["H7307"].root_label, "ר-ו-ח (to smell)")    # רוּחַ, רֵיחַ
        self.assertEqual(lex["H7305"].root_label, "ר-ו-ח (be wide)")     # רֶוַח
        self.assertEqual(lex["H7307"].formula, "ר-ו-ח → רוּחַ")           # the formula keeps the bare letters
        self.assertNotEqual(lex["H2654a"].root_label, lex["H2654b"].root_label)   # ח-פ-ץ
        self.assertNotEqual(lex["H1116"].root_label, lex["H1117"].root_label)     # בָּמָה
        self.assertEqual(lex["H7218a"].root_label, "ר-א-שׁ I")             # unique labels stay as they were
        self.assertEqual(lex["H0784"].root_label, lex["H0784"].lemma)

    # (6) BDB placements the lexical index leaves out
    def test_missed_bdb_links(self) -> None:
        lex = self.lex
        self.assertEqual(lex["H8492"].root_key, lex["H3423"].root_key)   # תִּירוֹשׁ under יָרַשׁ
        self.assertEqual(lex["H5961"].root_key, lex["H5959"].root_key)   # עֲלָמוֹת under עַלְמָה (II עלם)
        self.assertEqual(lex["H3759"].root_key, lex["H3754"].root_key)   # כַּרְמֶל I under כֶּרֶם
        self.assertEqual(nfd(lex["H8492"].formula), nfd("י-ר-שׁ → תִּירוֹשׁ"))
        for key in H.BDB_FAMILY_LINKS:
            self.assertEqual(lex[key].root_source, "OSHB-BDB", key)
            self.assertTrue(H.root_notes(key), key)
        self.assertEqual(lex["H3760"].root_source, "self")               # Carmel the place: names stay apart
        # already linked before the final check (the reviewer's other examples)
        self.assertEqual(lex["H0801"].root_key, lex["H0784"].root_key)   # אִשֶּׁה with אֵשׁ
        self.assertEqual(lex["H3119"].root_key, lex["H3117"].root_key)   # יוֹמָם with יוֹם


class TestParseKey(unittest.TestCase):
    """``parse_key`` ignores only what cannot change a parse."""

    def test_plene_defective_equal(self) -> None:
        pk = H.parse_key
        self.assertEqual(pk("וַֽאֲדֹמִים"), pk("וַֽאֲדוֹמִים"))          # holam male / haser
        self.assertEqual(pk("כְּפִירֶיהָ"), pk("כְּפִרֶיהָ"))             # hiriq yod
        self.assertEqual(pk("וּגְדֻלָּתְךָ"), pk("וּגְדוּלָּתְךָ"))        # qubuts / shureq
        self.assertEqual(pk("מִבְרָחָו"), pk("מִבְרָחָיו"))               # the silent י of -ָיו
        self.assertEqual(pk("תֹּאכְלֶנּוּ"), pk("תֹּאכֲלֶנּוּ"))           # hataf for shewa
        self.assertEqual(pk("בְּחַרְבּוֹ"), pk("בְּחַרְבוֹ"))              # dagesh

    def test_number_and_stem_kept_apart(self) -> None:
        pk = H.parse_key
        self.assertNotEqual(pk("עֵינֵנוּ"), pk("עֵינֵינוּ"))             # our eye / our eyes
        self.assertNotEqual(pk("כַּפֶּךָ"), pk("כַּפֶּיךָ"))               # your palm / your palms
        self.assertNotEqual(pk("בְּרַגְלַהּ"), pk("בְּרַגְלַיהּ"))         # consonantal י after patah
        self.assertNotEqual(pk("מַעֲשֵׂה"), pk("מַעֲשֵׂי"))
        self.assertNotEqual(pk("וַיַּחֲזֶק"), pk("וַיֶּחֱזַק"))           # Hiphil / Qal pointing
        self.assertNotEqual(pk("שָׁם"), pk("שָׂם"))                       # shin / sin


@unittest.skipUnless(HAVE_OSHB, "OSHB MorphHB / Hebrew Lexicon not present")
class TestParsing(unittest.TestCase):
    """TokenTag.morph = 'O:' + OSHB morph (prefixes included), TokenTag.src = 'oshb:' + OSHB word id."""

    def test_genesis_1_1(self) -> None:
        tags = tag("genesis", 1, 1, GEN_1_1)
        self.assertEqual([t.morph for t in tags], ["O:HR/Ncfsa", "O:HVqp3ms", "O:HNcmpa", "O:HTo", "O:HTd/Ncmpa",
                                                   "O:HC/To", "O:HTd/Ncbsa"])
        self.assertEqual(tags[0].src, "oshb:01xeN")
        self.assertTrue(all(re.fullmatch(r"oshb:\w+", t.src or "") for t in tags))
        self.assertEqual(len({t.src for t in tags}), len(tags))

    def test_studio_spelling_with_the_same_parse(self) -> None:
        # plene / defective with the WLC parse; YHWH with the Studio's holam (form attested)
        ez = {t.surface: t for t in tag("ezekiel", 40, 34, EZK_40_34)}
        self.assertEqual(ez["וְאֵלַמָּ֗ו"].morph, "O:HC/Ncmpc/Sp3ms")        # WLC וְאֵלַמָּיו
        deu = tag("deuteronomy", 17, 12, DEU_17_12)
        self.assertEqual(next(t for t in deu if t.lemma_key == "H3068").morph, "O:HNp")
        # a name with other vowels than WLC (מֵיְהֹוָה, WLC מֵיְהוָה): the parse of a name stays Np
        self.assertEqual(tag("psalms", 37, 23, PS_37_23)[0].morph, "O:HR/Np")

    def test_parse_withheld_when_the_studio_reads_otherwise(self) -> None:
        t = tag("psalms", 8, 4, PS_8_4)[3]                  # Studio מַעֲשֵׂה (sg.), WLC מַעֲשֵׂי (pl.)
        self.assertEqual((t.lemma_key, t.method), ("H4639", "gold-aligned"))
        self.assertIsNone(t.morph)
        self.assertTrue(t.src.startswith("oshb:"))
        self.assertTrue(any("HNcmpc" in n and "not given" in n for n in t.notes))
        t = tag("judges", 19, 4, JDG_19_4)[0]               # Studio Hiphil pointing, WLC Qal
        self.assertEqual(t.lemma_key, "H2388")
        self.assertIsNone(t.morph)
        t = tag("psalms", 35, 21, PS_35_21)[-1]             # Studio עֵינֵנוּ "our eye", WLC dual
        self.assertEqual(t.surface, "עֵינֵֽנוּ")
        self.assertIsNone(t.morph)
        t = tag("proverbs", 7, 15, PRO_7_15)[-1]            # WLC וָאֶמְצָאֶךָּ has a vav the Studio lacks
        self.assertIsNone(t.morph)
        self.assertTrue(any("proclitics differ" in n for n in t.notes))

    def test_no_parse_without_one_owning_word(self) -> None:
        kings = {t.surface: t for t in tag("2-kings", 18, 17, KGS2_18_17)}
        merged = kings["רַבְשָׁקֵ֨ה"]                          # one token for WLC רַב שָׁקֵה
        self.assertEqual(merged.lemma_key, "H7262")
        self.assertIsNone(merged.morph)
        self.assertIsNone(merged.src)
        self.assertEqual((kings["רַב"].morph, kings["סָרִ֣יס"].morph), ("O:HNcmsc", "O:HNcmsa"))
        dan = {t.surface: t for t in tag("daniel", 1, 13, DAN_1_13)}
        piece = dan["בַּ֣ג"]                                   # piece of WLC פַּתְבַּג
        self.assertEqual(piece.lemma_key, "H6598")
        self.assertIsNone(piece.morph)
        self.assertTrue(piece.src.startswith("oshb:"))
        self.assertEqual((dan["פַּת"].method, dan["פַּת"].morph, dan["פַּת"].src), ("untagged", None, None))
        # pointed-form dictionary decisions and ketiv residue carry no parse
        for t in tag("job", 7, 5, JOB_7_5) + tag("2-chronicles", 1, 5, CHR2_1_5):
            if t.method == "untagged" or (t.method == "gold-form" and not (t.notes and t.notes[0].startswith("OSHB gives"))):
                self.assertIsNone(t.morph, t.surface)
        sham = next(t for t in tag("2-chronicles", 1, 5, CHR2_1_5) if t.lemma_key == "H8033")
        self.assertEqual((sham.method, sham.morph, sham.src), ("gold-form", None, None))

    def test_aramaic_and_ketiv(self) -> None:
        dan = tag("daniel", 2, 12, DAN_2_12)
        self.assertTrue(all((t.morph or "O:A").startswith("O:A") for t in dan))
        self.assertTrue(sum(1 for t in dan if t.morph) >= len(dan) - 1)

    def test_lemma_choices_unchanged_by_parsing(self) -> None:
        tags = tag("genesis", 1, 1, GEN_1_1)
        self.assertEqual([t.lemma_key for t in tags], ["H7225", "H1254a", "H0430", "H0853", "H8064", "H0853", "H0776"])
        self.assertEqual([t.prefixes for t in tags], [("P:b",), (), (), (), ("P:h",), ("P:w",), ("P:h",)])


@unittest.skipUnless(HAVE_OSHB and H.oshm_path() is not None, "OSHB MorphHB parsing/Oshm.xml not present")
class TestMorphLegend(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.legend = H.morph_legend()

    def test_known_codes(self) -> None:
        lg = self.legend
        self.assertEqual(lg["O:HR/Ncfsa"], "Hebrew: Preposition + Noun common feminine singular absolute")
        self.assertEqual(lg["O:HC/Vqw3ms"],
                         "Hebrew: Conjunction + Verb qal sequential imperfect third person masculine singular")
        self.assertEqual(lg["O:HNp"], "Hebrew: Noun proper name")
        self.assertTrue(lg["O:AVqp3ms"].startswith("Aramaic: Verb peal perfect"))
        self.assertEqual(lg["O:HAabsa"], "Hebrew: Adjective both singular absolute")    # not 'Adjective adjective'
        self.assertNotIn("  ", "".join(lg.values()))

    def test_codes_missing_from_the_key_are_composed(self) -> None:
        self.assertNotIn("HTd/Sp3fs", H._oshm()[0])
        self.assertEqual(self.legend["O:HTd/Sp3fs"],
                         "Hebrew: Particle definite article + Suffix pronominal third person feminine singular")
        self.assertIsNone(H.morph_description("HXq"))

    def test_composition_agrees_with_the_key(self) -> None:
        full = H._oshm()[0]
        checked = 0
        for code, text in full.items():
            if code.endswith("/"):
                continue    # 'AC/Ncmpc/', 'HVtv2fs/': stray slash in the key
            label, _sep, rest = text.partition(":")
            want = f"{label.strip()}: " + " + ".join(H._clean_morph_text(s) for s in rest.split(";"))
            self.assertEqual(H.morph_description(code), want, code)
            checked += 1
        self.assertGreater(checked, 3400)

    def test_every_oshb_code_has_english(self) -> None:
        codes = {w.morph for ws in H.oshb_corpus().all_words.values() for w in ws if w.morph}
        self.assertGreater(len(codes), 3400)
        self.assertEqual(sorted(c for c in codes if not self.legend.get("O:" + c)), [])

    def test_licence(self) -> None:
        self.assertIn("CC BY 4.0", H.SRC_MORPH_LEGEND)
        self.assertIn("OT_OSHB_MorphHB", str(H.oshm_path()))


@unittest.skipUnless(HAVE_OSHB, "OSHB MorphHB / Hebrew Lexicon not present")
class TestUntaggedResolutionFixes(unittest.TestCase):
    """Regressions for the 19 Nov 2026 untagged-token pass (שׂ/ס, quiescent א, morph-POS bare Strong's, merges)."""

    def test_orthographic_sin_samekh_and_quiescent_aleph(self) -> None:
        t = by_surface(tag("isaiah", 44, 25,
                           "מֵפֵר֙ אֹת֣וֹת בַּדִּ֔ים וְקֹסְמִ֖ים יְהוֹלֵ֑ל מֵשִׁ֧יב חֲכָמִ֛ים אָח֖וֹר וְדַעְתָּ֥ם יְסַכֵּֽל׃"),
                       "יסכל")
        self.assertEqual(t[0].lemma_key, "H5528")
        t = by_surface(tag("isaiah", 30, 5,
                           "כֹּ֣ל הֹבִ֔אישׁ עַל־עַ֖ם לֹא־יוֹעִ֣ילוּ לָ֑מוֹ לֹ֤א לְעֵ֨זֶר֙ וְלֹ֣א לְהוֹעִ֔יל כִּ֥י לְבֹ֖שֶׁת וְגַם־לְחֶרְפָּֽה׃"),
                       "הבאיש")
        self.assertEqual(t[0].lemma_key, "H0954")

    def test_bare_strongs_disambiguated_by_oshb_morph(self) -> None:
        t = by_surface(tag("1-kings", 12, 33,
                           "וַיַּ֜עַל עַֽל־הַמִּזְבֵּ֣חַ ׀ אֲשֶׁר־עָשָׂ֣ה בְּבֵֽית־אֵ֗ל בַּחֲמִשָּׁ֨ה עָשָׂ֥ר יוֹם֙ בַּחֹ֣דֶשׁ הַשְּׁמִינִ֔י בַּחֹ֖דֶשׁ אֲשֶׁר־בָּדָ֣א (מלבד) מִלִּבּ֑וֹ וַיַּ֤עַשׂ חָג֙ לִבְנֵ֣י יִשְׂרָאֵ֔ל וַיַּ֥עַל עַל־הַמִּזְבֵּ֖חַ לְהַקְטִֽיר׃"),
                       "מלבו")
        self.assertEqual(t[0].lemma_key, "H3820a")
        t = by_surface(tag("leviticus", 5, 23,
                           "וְהָיָה֮ כִּֽי־יֶחֱטָ֣א וְאָשֵׁם֒ וְהֵשִׁ֨יב אֶת־הַגְּזֵלָ֜ה אֲשֶׁ֣ר גָּזָ֗ל א֤וֹ אֶת־הָעֹ֙שֶׁק֙ אֲשֶׁ֣ר עָשָׁ֔ק א֚וֹ אֶת־הַפִּקָּד֔וֹן אֲשֶׁ֥ר הׇפְקַ֖ד אִתּ֑וֹ א֥וֹ אֶת־הָאֲבֵדָ֖ה אֲשֶׁ֥ר מָצָֽא׃"),
                       "הפקד")
        self.assertEqual(t[0].lemma_key, "H6485a")
        # Deut 17:12 הָרָע (H7451a adj. vs H7451b noun) stays untagged
        deu = by_surface(tag("deuteronomy", 17, 12, DEU_17_12), "הרע")
        self.assertIsNone(deu[0].lemma_key)

    def test_oshb_attested_compound_name_merges(self) -> None:
        t = by_surface(tag("2-samuel", 2, 30,
                           "וְיוֹאָ֗ב שָׁ֚ב מֵאַחֲרֵ֣י אַבְנֵ֔ר וַיִּקְבֹּ֖ץ אֶת־כׇּל־הָעָ֑ם וַיִּפָּ֨קְד֜וּ מֵעַבְדֵ֥י דָוִ֛ד תִּשְׁעָה־עָשָׂ֥ר אִ֖ישׁ וַעֲשָׂהאֵֽל׃"),
                       "ועשהאל")
        self.assertEqual(t[0].lemma_key, "H6214")
        t = by_surface(tag("2-samuel", 21, 7,
                           "וַיַּחְמֹ֣ל הַמֶּ֔לֶךְ עַל־מְפִיבֹ֖שֶׁת בֶּן־יְהוֹנָתָ֣ן בֶּן־שָׁא֑וּל עַל־שְׁבֻעַ֤ת יְהֹוָה֙ אֲשֶׁ֣ר בֵּינֹתָ֔ם בֵּ֣ין דָּוִ֔ד וּבֵ֖ין יְהוֹנָתָ֥ן בֶּן־שָׁאֽוּל׃"),
                       "מפיבשת")
        self.assertEqual(t[0].lemma_key, "H4648")

    def test_remaining_resolvable_hebrew_tokens(self) -> None:
        # Ps 57:10 בַּלְאֻמִּים: WLC mis-split בַּל H1077 + אֻמִּים H3816 -> P:b + H3816
        t = by_surface(tag("psalms", 57, 10,
                           "אוֹדְךָ֖ בָעַמִּ֥ים ׀ אֲדֹנָ֑י אֲ֝זַמֶּרְךָ֗ בַּלְאֻמִּֽים׃"),
                       "בלאמים")
        self.assertEqual((t[0].lemma_key, t[0].prefixes), ("H3816", ("P:b",)))
        # 2 Kgs 12:22 וְיוֹזָכָר matches H3108's own lexicon headword יוֹזָכָר (WLC reads וְיוֹזָבָד)
        t = by_surface(tag("2-kings", 12, 22,
                           "וְיוֹזָכָ֣ר בֶּן־שִׁ֠מְעָ֠ת וִיהוֹזָבָ֨ד בֶּן־שֹׁמֵ֤ר ׀ עֲבָדָיו֙ הִכֻּ֣הוּ וַיָּמֹ֔ת וַיִּקְבְּר֥וּ אֹת֛וֹ עִם־אֲבֹתָ֖יו בְּעִ֣יר דָּוִ֑ד וַיִּמְלֹ֛ךְ אֲמַצְיָ֥ה בְנ֖וֹ תַּחְתָּֽיו׃"),
                       "ויוזכר")
        self.assertEqual((t[0].lemma_key, t[0].prefixes), ("H3108", ("P:w",)))
        # Proper-name final א/ה sister spellings attested in OSHB
        t = by_surface(tag("2-samuel", 6, 6,
                           "וַיָּבֹ֖אוּ עַד־גֹּ֣רֶן נָכ֑וֹן וַיִּשְׁלַ֨ח עֻזָּ֜ה אֶל־אֲר֤וֹן הָֽאֱלֹהִים֙ וַיֹּ֣אחֶז בּ֔וֹ כִּ֥י שָֽׁמְט֖וּ הַבָּקָֽר׃"),
                       "עזה")
        self.assertEqual(t[0].lemma_key, "H5798b")
        t = by_surface(tag("2-samuel", 23, 11,
                           "וְאַחֲרָ֛יו שַׁמָּ֥ה בֶן־אָגֵ֖א הָרָרִ֑י וַיֵּאָסְפ֨וּ פְלִשְׁתִּ֜ים לַחַיָּ֗ה וַתְּהִי־שָׁ֞ם חֶלְקַ֤ת הַשָּׂדֶה֙ מְלֵאָ֣ה עֲדָשִׁ֔ים וְהָעָ֥ם נָ֖ס מִפְּנֵ֥י פְלִשְׁתִּֽים׃"),
                       "שמה")
        self.assertEqual(t[0].lemma_key, "H8048")
        t = by_surface(tag("nehemiah", 11, 17,
                           "וּמַתַּנְיָ֣ה בֶן־מִ֠יכָ֠א בֶּן־זַבְדִּ֨י בֶן־אָסָ֜ף רֹ֗אשׁ הַתְּחִלָּה֙ יְהוֹדֶ֣ה לַתְּפִלָּ֔ה וּבַקְבֻּקְיָ֖ה מִשְׁנֶ֣ה מֵאֶחָ֑יו וְעַבְדָּא֙ בֶּן־שַׁמּ֔וּעַ בֶּן־גָּלָ֖ל בֶּן־יְדוּתֽוּן (ידיתון)׃"),
                       "מיכא")
        self.assertEqual(t[0].lemma_key, "H4316")
        # 2 Sam 16:12 בְּעֵינִי: bare H5869 disambiguated by core עֵינִי (29/29) & cons (165/165) -> H5869a
        t = by_surface(tag("2-samuel", 16, 12,
                           "אוּלַ֛י יִרְאֶ֥ה יְהֹוָ֖ה (בעוני) בְּעֵינִ֑י וְהֵשִׁ֨יב יְהֹוָ֥ה לִי֙ טוֹבָ֔ה תַּ֥חַת קִלְלָת֖וֹ הַיּ֥וֹם הַזֶּֽה׃"),
                       "בעיני")
        self.assertEqual(t[0].lemma_key, "H5869a")
        # Isa 27:2 חֶמֶר: unique pointed lexicon headword H2561 (wine), same POS (N) as WLC חֶמֶד
        t = by_surface(tag("isaiah", 27, 2, "בַּיּ֖וֹם הַה֑וּא כֶּ֥רֶם חֶ֖מֶר עַנּוּ־לָֽהּ׃"), "חמר")
        self.assertEqual(t[0].lemma_key, "H2561")


if __name__ == "__main__":
    unittest.main()
