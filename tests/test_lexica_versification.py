"""Tests for studio/lexica/versification.py (Hebrew / Latin / Studio Greek -> live Saints.Bible numbering).

Offline and fast.  The live-database tests open data/studio.db read-only and skip when it is missing; the
site tests read the Saints.Bible books.json and the site English (Greek-Translation verses.json) and skip
when those folders are missing.
Run:  py -3 -m unittest tests.test_lexica_versification -v
"""

import json
import os
import re
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from studio.lexica import greek_bare, hebrew_consonants  # noqa: E402
from studio.lexica import versification as vz  # noqa: E402

DB = os.path.join(ROOT, "data", "studio.db")
SITE_BOOKS = os.environ.get(
    "SAINTS_SITE_BOOKS_JSON",
    os.path.join(os.path.expanduser("~"), "Website", "english-numbering-2026-11-16", "production", "books.json"),
)
SITE_ENGLISH = os.environ.get(
    "SAINTS_SITE_ENGLISH_DIR",
    os.path.join(os.path.expanduser("~"), "Documents", "ChatGPT", "Holy Bible Translation", "Greek-Translation"),
)


def _ro_conn():
    return sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)


class TableIntegrity(unittest.TestCase):
    def test_rules_parse_and_targets_exist(self):
        for lang in ("hebrew", "latin"):
            table = vz._rule_table(lang)
            self.assertGreater(len(table), 100, lang)
            for (book, c, v), targets in table.items():
                for t in targets:  # Studio-Greek-level tables point into the Studio Greek
                    self.assertTrue(vz.studio_greek_has(book, *t), "%s %s %d:%d -> %r" % (lang, book, c, v, t))
            for (book, c, v), targets in vz._site_rule_table(lang).items():
                for t in targets:
                    self.assertTrue(vz.saints_has(book, *t), "site %s %s %d:%d -> %r" % (lang, book, c, v, t))
        for (book, c, v), targets in vz._rule_table("greek").items():
            self.assertTrue(vz.studio_greek_has(book, c, v), ("greek rule source", book, c, v))
            for t in targets:
                self.assertTrue(vz.saints_has(book, *t), ("greek", book, c, v, t))

    def test_every_snapshot_verse_maps_only_to_existing_saints_verses(self):
        for lang in ("hebrew", "latin", "greek"):
            for book, chapters in vz.inventory(lang).items():
                for c, vs in chapters.items():
                    for v in vs:
                        for t in vz.to_saints(lang, book, c, v):
                            self.assertTrue(vz.saints_has(book, *t), (lang, book, c, v, t))

    def test_from_saints_is_the_inverse_of_to_saints(self):
        for lang in ("hebrew", "latin", "greek"):
            for book, chapters in vz.inventory(lang).items():
                for c, vs in chapters.items():
                    for v in vs:
                        for t in vz.to_saints(lang, book, c, v):
                            self.assertIn((c, v), vz.from_saints(lang, book, *t), (lang, book, c, v, t))

    def test_greek_identity_where_the_site_agrees_and_language_aliases(self):
        self.assertEqual(vz.to_saints("greek", "psalms", 50, 3), [(50, 3)])
        self.assertEqual(vz.to_saints("grc", "john", 3, 16), [(3, 16)])
        self.assertEqual(vz.to_saints("heb", "genesis", 1, 1), [(1, 1)])
        self.assertEqual(vz.from_saints("greek", "john", 3, 16), [(3, 16)])
        self.assertEqual(vz.to_studio_greek("greek", "deuteronomy", 29, 1), [(29, 1)])
        with self.assertRaises(ValueError):
            vz.to_saints("syriac", "genesis", 1, 1)

    def test_books_a_language_lacks_map_to_nothing(self):
        self.assertEqual(vz.to_saints("hebrew", "matthew", 1, 1), [])
        self.assertEqual(vz.to_saints("hebrew", "sirach", 1, 1), [])
        self.assertEqual(vz.from_saints("hebrew", "matthew", 1, 1), [])
        self.assertEqual(vz.to_saints("greek", "tobit", 1, 1), [])

    def test_site_inventory_folds_lettered_and_combined_verses(self):
        self.assertTrue(vz.saints_has("1-kings", 2, 35))       # 2:35a-o folded into 2:35
        self.assertTrue(vz.saints_has("jeremiah", 25, 13))     # combined anchor '13-32-13'
        self.assertTrue(vz.saints_has("jeremiah", 25, 14))     # combined anchor '14-25-20'
        self.assertFalse(vz.saints_has("jeremiah", 25, 20))
        self.assertTrue(vz.saints_has("esther", 5, 1))         # '1-1c'
        self.assertFalse(vz.saints_has("daniel", 4, 1))        # Old Greek lacks it
        self.assertFalse(vz.saints_has("matthew", 17, 21))
        self.assertTrue(vz.saints_has("2-chronicles", 3, 12))  # only the site has it


class StudioGreekToSaints(unittest.TestCase):
    """The Studio Greek (Swete) is not the live numbering; each case read against the site's Greek/English."""

    CASES = [
        ("deuteronomy", (29, 1), [(28, 69)]),       # Studio KJV-style, site Rahlfs-style
        ("deuteronomy", (29, 2), [(29, 1)]),
        ("deuteronomy", (29, 29), [(29, 28)]),
        ("deuteronomy", (5, 17), [(5, 18)]),        # site has adultery first
        ("genesis", (32, 1), [(32, 1)]),            # identity where the site agrees
        ("genesis", (47, 4), [(47, 5), (47, 4)]),   # 29 of its 46 words are site 47:5
        ("exodus", (39, 14), [(39, 13), (39, 14)]),  # Stage 1 restored ark clause to 39:14 (majority = 39:13)
        ("exodus", (39, 15), [(39, 15)]),           # Stage 1 repaired 39:15 to altar + utensils (= site 39:15a)
        ("leviticus", (8, 19), [(8, 20), (8, 21)]), # Stage 1 moved washing clause into 8:19 (majority = 8:20)
        ("leviticus", (11, 15), [(11, 16)]),        # the Studio Greek lacks the raven verse
        ("numbers", (21, 20), [(21, 21)]),          # Stage 1 repaired 21:20 (envoys) = site 21:21
        ("numbers", (21, 21), [(21, 22)]),          # Stage 1 removed duplicate envoys clause; 21:21 = site 21:22a
        ("numbers", (27, 4), [(27, 5)]),
        ("numbers", (16, 44), []),                  # Studio copy of 17:9
        ("1-samuel", (20, 43), []),                 # Studio copy of 21:1
        ("1-kings", (4, 33), [(5, 14)]),            # 'Solomon built Gezer' = site 5:14b
        ("1-chronicles", (12, 4), [(12, 4)]),       # Stage 1 separated 12:4 and 12:5 cleanly
        ("1-chronicles", (12, 5), [(12, 5)]),
        ("nehemiah", (12, 17), [(12, 17)]),         # Stage 1 realigned priestly pairs 12:17-19 to identity
        ("nehemiah", (12, 18), [(12, 18)]),
        ("nehemiah", (12, 19), [(12, 19)]),
        ("psalms", (12, 2), [(12, 3)]),
        ("psalms", (25, 22), []),                   # stray title 'Tou Dauid'
        ("proverbs", (31, 25), [(31, 26)]),
        ("wisdom-of-solomon", (17, 11), [(17, 10)]),
        ("sirach", (34, 12), [(31, 12)]),           # 'Epi trapezes megales' = site 31:12
        ("sirach", (30, 25), [(33, 17), (33, 16)]),  # 'en eulogiai Kyriou ephthasa' = 33:17
        ("sirach", (33, 1), [(36, 1)]),
        ("sirach", (19, 1), [(19, 1)]),
        ("sirach", (41, 23), [(41, 26)]),           # Stage 1 separated 41:23 (= 41:26) and 41:24 (= 41:27)
        ("sirach", (41, 24), [(41, 27)]),
        ("jeremiah", (25, 20), [(25, 14)]),         # site anchor '14-25-20'
        ("jeremiah", (23, 40), [(23, 8), (23, 40), (23, 7)]),  # most of its words are 23:8
        ("daniel", (3, 54), [(3, 55)]),             # Theodotion order vs the site's Old Greek order
        ("daniel", (4, 1), [(4, 37)]),              # the king's letter = Old Greek 4:37c
        ("daniel", (4, 6), []),                     # the Old Greek lacks it
        ("matthew", (17, 21), []),                  # bracketed verse the site omits
        ("romans", (14, 24), []),                   # doxology: the site has it at 16:25
        ("romans", (16, 25), [(16, 25)]),
    ]

    def test_cases(self):
        for book, (c, v), want in self.CASES:
            with self.subTest(book=book, ref=(c, v)):
                self.assertEqual(vz.to_saints("greek", book, c, v), want)

    def test_from_saints_greek(self):
        self.assertEqual(vz.from_saints("greek", "sirach", 31, 12), [(34, 12)])
        self.assertEqual(vz.from_saints("greek", "deuteronomy", 28, 69), [(29, 1)])
        self.assertEqual(vz.from_saints("greek", "2-chronicles", 3, 12), [])
        self.assertEqual(vz.from_saints("greek", "jeremiah", 25, 14), [(25, 14), (25, 20)])


class HebrewRegressions(unittest.TestCase):
    """Verse pairs read in Hebrew and Greek; each guards a renumbering block.  (book, MT ref, Saints refs)."""

    CASES = [
        ("genesis", (32, 1), [(32, 1)]),
        ("genesis", (32, 33), [(32, 33)]),
        ("genesis", (31, 51), [(31, 48)]),
        ("genesis", (47, 4), [(47, 4)]),
        ("exodus", (7, 26), [(7, 26)]),
        ("exodus", (20, 13), [(20, 15)]),
        ("exodus", (36, 8), [(37, 1)]),
        ("exodus", (39, 1), [(36, 8)]),
        ("exodus", (39, 35), [(39, 14)]),           # ark and poles: the site has it, the Studio Greek not
        ("leviticus", (8, 19), [(8, 19)]),
        ("leviticus", (8, 30), [(8, 30)]),
        ("leviticus", (11, 5), [(11, 6)]),          # hyrax (shafan) = site 11:6
        ("leviticus", (11, 6), [(11, 5)]),          # hare (arnebet) = site 11:5 'dasypous'
        ("leviticus", (11, 15), [(11, 15)]),        # raven
        ("numbers", (21, 20), [(21, 20)]),
        ("numbers", (27, 4), [(27, 4)]),
        ("deuteronomy", (5, 17), [(5, 18)]),
        ("deuteronomy", (5, 18), [(5, 17)]),
        ("deuteronomy", (28, 69), [(28, 69)]),      # site numbering (the Studio Greek has 29:1)
        ("deuteronomy", (29, 1), [(29, 1)]),
        ("deuteronomy", (14, 14), [(14, 14)]),
        ("joshua", (8, 30), [(9, 2)]),
        ("1-samuel", (17, 12), []),
        ("1-samuel", (21, 1), [(21, 1)]),
        ("1-kings", (5, 1), [(2, 46)]),
        ("1-kings", (7, 26), [(7, 12)]),
        ("1-kings", (7, 47), [(7, 32)]),
        ("1-kings", (7, 19), [(7, 8)]),
        ("1-kings", (20, 1), [(21, 1)]),
        ("2-chronicles", (3, 12), [(3, 12)]),
        ("job", (35, 3), [(35, 3)]),
        ("psalms", (10, 1), [(9, 22)]),
        ("psalms", (13, 2), [(12, 2)]),
        ("psalms", (51, 3), [(50, 3)]),
        ("psalms", (116, 14), []),
        ("proverbs", (1, 16), [(1, 16)]),
        ("proverbs", (16, 4), [(16, 9)]),
        ("proverbs", (16, 6), [(15, 27)]),
        ("proverbs", (16, 9), [(15, 29)]),
        ("proverbs", (20, 21), [(20, 9)]),
        ("proverbs", (24, 23), [(24, 23)]),
        ("isaiah", (40, 8), [(40, 8), (40, 7)]),
        ("jeremiah", (23, 7), [(23, 7)]),
        ("jeremiah", (25, 13), [(25, 13), (25, 14)]),
        ("jeremiah", (31, 31), [(38, 31)]),
        ("jeremiah", (33, 14), []),
        ("jeremiah", (49, 34), [(25, 14)]),
        ("ezekiel", (11, 11), [(11, 11)]),
        ("daniel", (3, 31), [(4, 37)]),
        ("daniel", (4, 1), [(4, 4)]),
        ("daniel", (4, 3), []),                     # Theodotion 4:6, absent from the Old Greek
        ("daniel", (5, 25), [(5, 17)]),
        ("malachi", (3, 22), [(3, 24)]),
    ]

    STUDIO_GREEK = [  # to_studio_greek: the first step, kept from the first build plus the review fixes
        ("deuteronomy", (28, 69), [(29, 1)]),
        ("leviticus", (8, 19), [(8, 18)]),
        ("leviticus", (11, 5), [(11, 6)]),
        ("leviticus", (11, 15), []),
        ("leviticus", (11, 16), [(11, 15), (11, 16)]),
        ("proverbs", (16, 4), [(16, 9)]),
        ("proverbs", (16, 8), [(15, 29)]),
        ("jeremiah", (25, 13), [(25, 13), (25, 14)]),
        ("jeremiah", (49, 34), [(25, 20), (25, 14)]),
        ("1-kings", (7, 18), [(7, 6)]),
        ("psalms", (13, 2), [(12, 1)]),
    ]

    def test_cases(self):
        for book, (c, v), want in self.CASES:
            with self.subTest(book=book, ref=(c, v)):
                self.assertEqual(vz.to_saints("hebrew", book, c, v), want)

    def test_studio_greek_step(self):
        for book, (c, v), want in self.STUDIO_GREEK:
            with self.subTest(book=book, ref=(c, v)):
                self.assertEqual(vz.to_studio_greek("hebrew", book, c, v), want)


class LatinRegressions(unittest.TestCase):
    CASES = [
        ("genesis", (31, 55), [(32, 1)]),           # native Vulgate numbering
        ("genesis", (32, 1), [(32, 2)]),
        ("exodus", (39, 22), [(36, 31)]),           # pomegranates of the robe (Vulgate 39:22 = MT 39:24)
        ("exodus", (39, 24), [(36, 33)]),           # bell and pomegranate (Vulgate 39:24 = MT 39:26)
        ("exodus", (39, 37), [(39, 15)]),           # golden altar, oil, incense (Vulgate 39:37 = MT 39:38)
        ("exodus", (39, 34), [(39, 14)]),           # ark, poles (Vulgate 39:34 = MT 39:35)
        ("leviticus", (11, 5), [(11, 6)]),          # Choerogryllus
        ("leviticus", (11, 6), [(11, 5)]),          # Lepus
        ("leviticus", (11, 15), [(11, 15)]),        # corvini generis
        ("numbers", (1, 28), [(1, 26)]),            # native Vulgate MT order (1:28 Issachar -> Saints 1:26)
        ("numbers", (1, 30), [(1, 28)]),            # 1:30 Zabulon -> Saints 1:28
        ("numbers", (1, 32), [(1, 30)]),            # 1:32 Ephraim -> Saints 1:30
        ("numbers", (6, 27), [(6, 23)]),            # Priestly blessing conclusion folded into Saints 6:23
        ("numbers", (27, 3), [(27, 3), (27, 4)]),   # native Vulgate splits 27:3-8 cleanly
        ("deuteronomy", (5, 17), [(5, 18)]),        # native Vulgate Non occides -> Saints 5:18
        ("deuteronomy", (5, 18), [(5, 17)]),        # native Vulgate Neque moechaberis -> Saints 5:17
        ("deuteronomy", (29, 1), [(28, 69)]),       # words of the covenant -> Saints 28:69
        ("deuteronomy", (29, 2), [(29, 1)]),        # Moses called -> Saints 29:1
        ("nehemiah", (7, 68), [(7, 68)]),           # horses and mules: only the site has it
        ("esther", (5, 2), [(5, 2)]),               # restored native Esth 5:2
        ("esther", (11, 1), [(10, 3)]),             # Add F colophon
        ("esther", (11, 2), [(1, 1)]),              # Add A dream
        ("esther", (13, 1), [(3, 13)]),             # Add B decree
        ("esther", (13, 8), [(4, 17)]),             # Add C Mordecai's prayer
        ("esther", (15, 4), [(5, 1)]),              # Add D Esther before king
        ("esther", (16, 1), [(8, 12)]),             # Add E second decree
        ("psalms", (12, 5), [(12, 5)]),
        ("daniel", (3, 54), [(3, 54)]),
        ("daniel", (3, 67), [(3, 67)]),
        ("daniel", (3, 98), [(4, 37)]),
        ("daniel", (13, 1), []),                    # Susanna (native Dan 13) is not in site navigation
        ("daniel", (14, 1), []),                    # Bel & Dragon (native Dan 14) is not in site navigation
        ("malachi", (4, 4), [(3, 24)]),             # native Mal 4:4-6 -> Saints 3:24, 3:22-23
        ("malachi", (4, 5), [(3, 22)]),
        ("sirach", (31, 12), [(31, 12)]),           # Studio Greek 34:12
        ("sirach", (19, 1), [(19, 1)]),             # '-' rules re-tested by reading
        ("sirach", (42, 4), [(42, 4)]),
        ("sirach", (6, 25), [(6, 24)]),
        ("sirach", (9, 1), [(9, 1)]),
        ("sirach", (14, 2), [(14, 2)]),
        ("sirach", (47, 18), [(47, 17)]),
        ("sirach", (3, 22), [(3, 21)]),
        ("sirach", (22, 8), [(22, 9)]),
        ("sirach", (38, 36), [(38, 32)]),
        ("sirach", (43, 33), [(43, 30)]),
        ("sirach", (33, 22), [(33, 22)]),
        ("sirach", (36, 21), [(36, 19)]),
        ("sirach", (1, 15), []),                    # native Greek II plus (no longer an English placeholder)
        ("sirach", (29, 16), [(29, 13)]),           # native Vulgate 3-verse split -> Saints 29:13
        ("sirach", (29, 17), [(29, 13)]),
        ("sirach", (29, 18), [(29, 13)]),
        ("luke", (4, 19), [(4, 18), (4, 19)]),
        ("matthew", (5, 4), [(5, 5)]),              # native Vulgate beatitude order
        ("matthew", (5, 5), [(5, 4)]),
        ("matthew", (17, 14), [(17, 15), (17, 14)]),  # 'dicens: Domine, miserere filio meo ...' = 17:15
        ("matthew", (17, 20), []),                  # 'Hoc autem genus...' = TR 17:21 (extra-site)
        ("acts", (9, 6), []),
        ("john", (3, 16), [(3, 16)]),
    ]

    def test_cases(self):
        for book, (c, v), want in self.CASES:
            with self.subTest(book=book, ref=(c, v)):
                self.assertEqual(vz.to_saints("latin", book, c, v), want)


# Every one-to-several mapping, as re-read on 18 Nov 2026 (second review): the concordance files ALL the
# words of a source verse under the FIRST target, so the first must be the site verse holding most of the
# source verse's indexed words.  "book c:v>first c:v ..." per language.  A change to any of these, or a new
# one-to-several mapping, must be read again and recorded here.
REVIEWED_FIRST_TARGETS = {
    "hebrew": """
exodus 37:18>38:15 38:30>39:9 39:40>39:19
ezekiel 7:5>7:10
isaiah 40:8>40:8
jeremiah 7:28>7:27 25:13>25:13
proverbs 31:26>31:28
""",
    "latin": """
1-chronicles 11:32>11:32 12:4>12:4 20:7>20:8
1-maccabees 1:23>1:22 1:24>1:23 1:51>1:48
2-corinthians 1:23>1:24
2-timothy 4:8>4:8
3-john 1:14>1:14
acts 7:55>7:55 9:7>9:6 14:6>14:6
deuteronomy 6:13>6:12
exodus 37:18>38:15 38:30>39:9 39:17>36:24 39:18>36:26 39:39>39:15 39:40>39:21 40:13>40:15
ezekiel 2:9>2:10 7:5>7:10
genesis 5:31>5:31 50:22>50:23
hosea 6:3>6:3
isaiah 40:8>40:8
jeremiah 7:28>7:27 25:13>25:13 37:4>44:5
job 42:16>42:16
john 11:56>11:56
joshua 21:36>21:36 21:37>21:38
judges 21:24>21:25
leviticus 26:45>26:45
luke 4:19>4:18 9:44>9:44
mark 4:40>4:41
matthew 17:14>17:15
micah 5:11>5:10
nehemiah 3:30>3:30 7:44>7:43 7:48>7:47 12:33>12:34
numbers 3:10>3:10 11:34>11:34 27:3>27:3 28:30>28:31
proverbs 15:5>15:5 31:26>31:28
psalms 4:6>4:6 4:7>4:7 12:1>12:2 15:10>15:11 43:22>43:23 55:11>55:11 72:23>72:22 108:18>108:18 110:7>110:7 129:4>129:5
revelation 20:7>20:8 20:9>20:10
sirach 4:32>4:27 6:35>6:35 12:13>12:13 14:25>14:25 18:1>18:1 18:8>18:10 19:5>19:6 20:1>20:2 24:15>24:11 32:2>32:2 32:11>32:8 32:25>32:20 33:10>33:9 33:15>33:15 33:28>33:27 33:31>33:32 35:15>35:12 35:21>35:17 35:22>35:19 35:23>35:21 36:19>36:17 36:28>36:26 37:21>37:18 38:37>38:33 38:38>38:34 41:5>41:3 41:24>41:20 41:25>41:22 41:26>41:23 41:27>41:23 42:1>41:27 45:31>45:26 47:16>47:14 47:17>47:16 51:2>51:2 51:15>51:10
song-of-songs 7:1>7:2
wisdom-of-solomon 2:3>2:4 19:13>19:14 19:20>19:22
""",
    "greek": """
1-chronicles 28:14>28:14
1-kings 6:17>6:17 22:5>22:5
2-kings 25:9>25:9
amos 8:1>8:2
exodus 39:14>39:13 39:16>39:15 39:21>39:20
ezekiel 7:9>7:9
genesis 47:4>47:5
jeremiah 10:5>10:9 10:9>10:9 23:40>23:8
leviticus 8:18>8:18 8:19>8:20
numbers 21:19>21:20 27:3>27:3
proverbs 15:5>15:6 31:24>31:25
psalms 12:1>12:2
sirach 6:2>5:15 23:16>23:17 29:18>29:17 30:25>33:17 30:40>33:32 32:12>35:12 32:17>35:17 32:18>35:21 32:19>35:22 36:16>36:10 36:22>36:16 36:31>36:26 39:17>39:17 40:5>40:5 41:3>41:3 41:18>41:19 41:19>41:20 41:20>41:21 41:21>41:23 41:22>41:25 43:17>43:17 46:6>46:6 47:23>47:23 51:12>51:12
wisdom-of-solomon 4:18>4:19
""",
}


def _parse_reviewed(text):
    out = {}
    for line in text.strip().splitlines():
        parts = line.split()
        for item in parts[1:]:
            src, dst = item.split(">")
            c, v = map(int, src.split(":"))
            out[(parts[0], c, v)] = tuple(map(int, dst.split(":")))
    return out


class OneToSeveralOrder(unittest.TestCase):
    """The first target of every one-to-several mapping is the reviewed one (all words are filed there)."""

    def test_every_one_to_several_mapping_was_reviewed(self):
        for lang in vz.LANGS:
            reviewed = _parse_reviewed(REVIEWED_FIRST_TARGETS[lang])
            current = {}
            for book, chapters in vz.inventory(lang).items():
                for c, vs in chapters.items():
                    for v in vs:
                        ts = vz.to_saints(lang, book, c, v)
                        if len(ts) > 1:
                            current[(book, c, v)] = ts[0]
            with self.subTest(lang=lang):
                self.assertEqual(sorted(current), sorted(reviewed))
                for key, first in reviewed.items():
                    self.assertEqual(current.get(key), first, (lang,) + key)


class FinalCheckRegressions(unittest.TestCase):
    """The concrete examples of the final check of the live concordance build (18 Nov 2026)."""

    CASES = [  # (lang, book, source ref, expected to_saints)
        # Hebrew one-to-several verses filed whole under the wrong first target
        ("hebrew", "ecclesiastes", (8, 1), [(8, 1)]),          # 'Who knows ... wisdom lights up his face'
        ("hebrew", "1-kings", (20, 3), [(21, 3)]),             # 'Thus says Ben-hadad: your silver and gold'
        ("hebrew", "exodus", (38, 30), [(39, 9), (39, 7)]),    # bronze altar, grating, utensils = 39:9
        ("hebrew", "ezekiel", (7, 5), [(7, 10), (7, 9)]),      # 'disaster ... behold it comes' = 7:10
        ("hebrew", "proverbs", (31, 26), [(31, 28), (31, 25)]),  # 'wisely ... law ... mercy' = 31:28
        ("hebrew", "proverbs", (15, 5), [(15, 5)]),            # MT lacks the LXX plus that opens site 15:6
        ("hebrew", "jeremiah", (25, 13), [(25, 13), (25, 14)]),  # kept: site 25:13 holds it
        # Latin verses straddling a Greek/site boundary (native Vulgate numbering)
        ("latin", "psalms", (110, 7), [(110, 7), (110, 6)]),   # 'Opera manuum ejus veritas et judicium'
        ("latin", "psalms", (110, 8), [(110, 8)]),
        ("latin", "mark", (4, 40), [(4, 41), (4, 40)]),        # 'et timuerunt timore magno ...'
        ("latin", "genesis", (50, 22), [(50, 23), (50, 22)]),
        ("latin", "psalms", (108, 18), [(108, 18), (108, 17)]),
        ("latin", "hosea", (6, 3), [(6, 3), (6, 2)]),
        ("latin", "revelation", (20, 7), [(20, 8), (20, 7)]),
        ("latin", "revelation", (20, 9), [(20, 10), (20, 9)]),
        ("latin", "numbers", (35, 13), [(35, 13)]),            # native Vulgate un-merges 35:13-15 cleanly
        ("latin", "numbers", (35, 22), [(35, 22)]),            # native Vulgate un-merges 35:22-25 cleanly
        ("latin", "sirach", (37, 21), [(37, 18), (37, 17), (37, 19)]),
        ("latin", "sirach", (45, 31), [(45, 26), (45, 25)]),
        ("latin", "exodus", (38, 25), [(39, 3)]),              # 'a viginti annis ... sexcentis tribus millibus'
        ("latin", "exodus", (38, 26), [(39, 4)]),              # 'centum talenta argenti e quibus conflatae sunt bases'
        ("latin", "exodus", (38, 27), [(39, 4)]),              # 'Centum bases factae sunt de talentis centum'
        ("latin", "wisdom-of-solomon", (2, 3), [(2, 4), (2, 3)]),  # 'transibit vita nostra ... vestigium nubis'
        ("latin", "proverbs", (31, 26), [(31, 28), (31, 25)]),
        ("latin", "ezekiel", (7, 5), [(7, 10), (7, 9)]),       # = Hebrew 7:5
        ("latin", "sirach", (41, 5), [(41, 3), (41, 4)]),      # Latin divides 41:3/4 unlike the Studio Greek
        ("latin", "proverbs", (15, 5), [(15, 5), (15, 6)]),    # the Vulgate has the plus, but 15:5 holds most
        ("latin", "sirach", (1, 1), []),                       # native USFX Sir 1:1 carries the Prologue (233/247 wds)
        # kept after reading: the first target holds most of the Latin verse's indexed words
        ("latin", "1-samuel", (20, 22), [(20, 21)]),           # 9 words of site 20:21b vs 8 of 20:22
        ("latin", "luke", (4, 19), [(4, 18), (4, 19)]),
        ("latin", "john", (11, 56), [(11, 56), (11, 57)]),
        ("latin", "acts", (7, 55), [(7, 55), (7, 56)]),
        ("latin", "3-john", (1, 14), [(1, 14), (1, 15)]),
        ("latin", "deuteronomy", (6, 13), [(6, 12), (6, 13)]),
        ("latin", "sirach", (34, 20), [(34, 17)]),
        ("latin", "sirach", (1, 2), [(1, 2)]),
        ("latin", "sirach", (42, 1), [(41, 27), (41, 26), (42, 1)]),  # preserves all 3 clauses (41:26 + 41:27 + 42:1)
        # Studio Greek spans and post-Stage-1 repairs
        ("greek", "exodus", (39, 14), [(39, 13), (39, 14)]),
        ("greek", "exodus", (39, 15), [(39, 15)]),
        ("greek", "numbers", (21, 19), [(21, 20), (21, 19)]),  # Bamoth ... plain of Moab ... wilderness
        ("greek", "numbers", (21, 20), [(21, 21)]),            # Stage 1 separated envoys (21:20 = site 21:21)
        ("greek", "numbers", (21, 21), [(21, 22)]),            # Stage 1 removed duplicate envoys; 21:21 = 21:22a
        ("greek", "numbers", (27, 3), [(27, 3), (27, 4)]),
        ("greek", "leviticus", (8, 18), [(8, 18), (8, 19)]),
        ("greek", "leviticus", (8, 19), [(8, 20), (8, 21)]),   # Stage 1 moved washing clause into 8:19
        ("greek", "1-chronicles", (12, 4), [(12, 4)]),
        ("greek", "1-chronicles", (12, 5), [(12, 5)]),
        ("greek", "nehemiah", (12, 17), [(12, 17)]),
        ("greek", "nehemiah", (12, 18), [(12, 18)]),
        ("greek", "sirach", (41, 23), [(41, 26)]),
        ("greek", "sirach", (41, 24), [(41, 27)]),
        ("greek", "psalms", (12, 1), [(12, 2), (12, 1)]),
        ("greek", "psalms", (12, 4), [(12, 5)]),                # Stage 1 fixed Swete's 12:4/12:5 duplication
        ("greek", "psalms", (12, 5), [(12, 6)]),
        ("greek", "psalms", (12, 6), [(12, 6)]),
        ("greek", "sirach", (1, 1), []),                        # the Prologue (no site verse number)
        ("greek", "sirach", (1, 2), [(1, 2)]),
        ("greek", "sirach", (29, 18), [(29, 17), (29, 18)]),
        ("greek", "sirach", (23, 16), [(23, 17), (23, 16)]),
        ("greek", "sirach", (32, 18), [(35, 21), (35, 18), (35, 19), (35, 20)]),
        ("greek", "sirach", (39, 17), [(39, 17), (39, 16)]),
        ("greek", "sirach", (41, 18), [(41, 19), (41, 18)]),
        ("greek", "sirach", (41, 22), [(41, 25), (41, 24)]),
        ("greek", "wisdom-of-solomon", (4, 18), [(4, 19), (4, 18)]),
        ("greek", "proverbs", (15, 5), [(15, 6), (15, 5)]),
        ("greek", "amos", (8, 1), [(8, 2), (8, 1)]),
        ("greek", "1-kings", (22, 5), [(22, 5), (22, 4)]),
        ("greek", "psalms", (26, 1), [(26, 1)]),                # its title is in the verse (25:22 is a copy)
        # Daniel: Theodotion (Studio) -> Old Greek (site), paired by content
        ("greek", "daniel", (4, 10), [(4, 10)]),                # the tree in the midst of the earth
        ("greek", "daniel", (4, 1), [(4, 37)]),
        ("greek", "daniel", (4, 6), []),
        ("greek", "daniel", (4, 35), []),
        ("greek", "daniel", (5, 14), []),
        ("greek", "daniel", (5, 24), []),
        ("greek", "daniel", (5, 25), [(5, 17)]),                # the inscription = OG 'This is the writing'
        ("greek", "daniel", (6, 16), []),                       # the Medes-and-Persians reminder: not in OG
        ("greek", "daniel", (6, 17), [(6, 17)]),
        ("hebrew", "daniel", (5, 25), [(5, 17)]),
        ("hebrew", "daniel", (6, 16), []),
        ("latin", "daniel", (6, 15), []),                       # native Vulgate 6:15 = MT/Theod 6:16 (not in OG)
        ("latin", "daniel", (6, 16), [(6, 17)]),                # native Vulgate 6:16 = MT/OG 6:17
        # Judges: B text (Studio) and A text (site) share their verse divisions
        ("greek", "judges", (4, 10), [(4, 10)]),
        ("greek", "judges", (6, 7), [(6, 7)]),
        ("greek", "judges", (5, 13), [(5, 13)]),
    ]

    def test_cases(self):
        for lang, book, (c, v), want in self.CASES:
            with self.subTest(lang=lang, book=book, ref=(c, v)):
                self.assertEqual(vz.to_saints(lang, book, c, v), want)

    def test_reverse_lookups(self):
        self.assertIn((8, 1), vz.from_saints("hebrew", "ecclesiastes", 8, 1))
        self.assertNotIn((8, 1), vz.from_saints("hebrew", "ecclesiastes", 7, 29))
        self.assertEqual(vz.from_saints("greek", "daniel", 5, 17), [(5, 17), (5, 25)])
        self.assertEqual(vz.from_saints("greek", "sirach", 1, 1), [])
        self.assertEqual(vz.from_saints("latin", "sirach", 1, 1), [])  # native USFX Sir 1:1 is Prologue+1:1
        self.assertEqual(vz.to_extra_site_anchor("latin", "sirach", 1, 1), (1, 1))


class LivePageRegressions(unittest.TestCase):
    """Third review (19 Nov 2026): placements checked against every live Parallel Reader page.

    FIXED: the live row (by the native Hebrew / Latin column's own reference) and the content agree.
    KEPT: the live column follows the verse number, not the content; the table follows the content."""

    FIXED = [  # (lang, book, Studio ref, expected to_saints)
        # a Hebrew / Latin verse the site prints inside a lettered row of another verse
        ("hebrew", "exodus", (35, 15), [(35, 12)]),     # incense altar, anointing oil, incense = site 35:12a
        ("latin", "exodus", (35, 15), [(35, 12)]),      # 'altare thymiamatis ... oleum unctionis'
        ("hebrew", "exodus", (37, 4), [(38, 11)]),      # poles of acacia overlaid with gold = site 38:11a
        ("latin", "exodus", (37, 4), [(38, 11)]),       # 'Vectes quoque fecit de lignis setim'
        ("hebrew", "exodus", (38, 5), [(38, 24)]),      # four rings for the grating = site 38:24b
        # a renumbering block one verse out of step (the lampstand)
        ("hebrew", "exodus", (37, 17), [(38, 13)]),
        ("hebrew", "exodus", (37, 18), [(38, 15), (38, 14)]),  # 'three ... and three' = site 38:15
        ("hebrew", "exodus", (37, 19), [(38, 16)]),     # cups like almond blossoms = 'nut-shaped'
        ("latin", "exodus", (37, 19), [(38, 16)]),      # native Vulgate: 'tres scyphi in nucis modum'
        ("latin", "exodus", (37, 18), [(38, 15), (38, 14)]),  # native Vulgate: 'sex in utroque latere, tres ... et tres'
        # Latin native Vulgate matches Hebrew MT in Exodus 38
        ("latin", "exodus", (38, 1), [(38, 22)]),       # 'Fecit et altare holocausti' (not 'Bezalel made the ark')
        ("latin", "exodus", (38, 2), []),               # horns of the altar: no site verse (Hebrew 38:2 alike)
        ("latin", "exodus", (38, 6), []),               # the altar's poles
        ("latin", "exodus", (38, 7), []),               # the hollow altar
        ("latin", "proverbs", (16, 7), [(15, 28)]),     # 'Cum placuerint Domino viae hominis' = site 15:28a
        ("latin", "proverbs", (16, 8), [(15, 29)]),     # 'Melius est parum cum justitia' = site 15:29a
    ]

    KEPT = [
        ("hebrew", "genesis", (32, 2), [(32, 2)]),      # live Hebrew column is one verse behind in Gen 32
        ("latin", "genesis", (32, 1), [(32, 2)]),       # 'Jacob quoque abiit' = site 32:2, live row 32:1
        ("hebrew", "exodus", (20, 13), [(20, 15)]),     # 'You shall not murder' = site 20:15 (Greek order)
        ("hebrew", "deuteronomy", (5, 21), [(5, 21)]),  # live Hebrew numbers this 5:18 (17a-d division)
        ("latin", "exodus", (39, 22), [(36, 31)]),      # pomegranates of the robe (Vulgate 39:22 = MT 39:24)
        ("latin", "exodus", (38, 20), [(37, 18)]),      # the bronze pegs (the Hebrew 38:20 alike)
        ("latin", "1-kings", (7, 1), [(7, 38)]),        # 'Domum autem suam aedificavit Salomon'
        ("latin", "nehemiah", (7, 46), [(7, 45)]),      # the gatekeepers
        ("latin", "sirach", (12, 5), [(12, 7)]),        # 'Da bono, et non receperis peccatorem'
        ("hebrew", "1-kings", (7, 20), [(7, 6)]),       # the pomegranates of the second capital
    ]

    def test_fixed(self):
        for lang, book, (c, v), want in self.FIXED:
            with self.subTest(lang=lang, book=book, ref=(c, v)):
                self.assertEqual(vz.to_saints(lang, book, c, v), want)

    def test_kept(self):
        for lang, book, (c, v), want in self.KEPT:
            with self.subTest(lang=lang, book=book, ref=(c, v)):
                self.assertEqual(vz.to_saints(lang, book, c, v), want)

    def test_hebrew_and_latin_agree_on_the_fixed_verses(self):
        for book, (c, v) in [("exodus", (35, 15)), ("exodus", (37, 4))]:
            self.assertEqual(vz.to_saints("hebrew", book, c, v), vz.to_saints("latin", book, c, v))
        self.assertEqual(vz.to_saints("latin", "proverbs", 16, 7), vz.to_saints("hebrew", "proverbs", 16, 7))
        self.assertEqual(vz.to_saints("latin", "proverbs", 16, 8), vz.to_saints("hebrew", "proverbs", 16, 8))

    def test_reverse_lookups(self):
        self.assertIn((35, 15), vz.from_saints("hebrew", "exodus", 35, 12))
        self.assertIn((37, 4), vz.from_saints("latin", "exodus", 38, 11))
        self.assertIn((38, 1), vz.from_saints("latin", "exodus", 38, 22))
        self.assertNotIn((38, 1), vz.from_saints("latin", "exodus", 38, 1))
        self.assertEqual(vz.from_saints("hebrew", "exodus", 38, 14), [(37, 18)])


@unittest.skipUnless(os.path.exists(SITE_BOOKS), "Saints.Bible books.json not present")
class SiteInventory(unittest.TestCase):
    def test_embedded_inventory_matches_books_json(self):
        with open(SITE_BOOKS, encoding="utf-8") as fh:
            d = json.load(fh)
        inv = vz.inventory("saints")
        self.assertEqual(sorted(inv), sorted(b["slug"] for b in d["books"]))
        for b in d["books"]:
            exc = b.get("exceptions") or {}
            for c, vmax in zip(b["chapters"], b["verseMax"]):
                e = exc.get(str(c), {})
                want = {v for v in range(1, vmax + 1) if not (str(v) in e and e[str(v)] is None)}
                for lab, url in e.items():
                    m = re.match(r"(\d+)", lab)
                    if url and m:
                        want.add(int(m.group(1)))
                self.assertEqual(set(inv[b["slug"]][c]), want, (b["slug"], c))


@unittest.skipUnless(os.path.isdir(SITE_ENGLISH), "site English (Greek-Translation) not present")
class SiteEnglish(unittest.TestCase):
    """The mapped Saints verse holds the content: checked against the site's own English."""

    @classmethod
    def setUpClass(cls):
        cls.en = {}
        for book in ("leviticus", "deuteronomy", "sirach", "2-chronicles", "numbers", "proverbs", "daniel",
                     "jeremiah", "ecclesiastes", "1-kings", "exodus", "ezekiel", "psalms", "mark",
                     "wisdom-of-solomon", "genesis", "hosea", "revelation", "amos"):
            with open(os.path.join(SITE_ENGLISH, book, "verses.json"), encoding="utf-8") as fh:
                d = json.load(fh)
            if isinstance(d, list):
                for v in d:
                    m = re.match(r"(\d+):(\d+)", v.get("ref") or "")
                    if m:
                        cls.en.setdefault((book, int(m.group(1)), int(m.group(2))), []).append(v["text"])
                continue
            for ch in d["chapters"]:
                for v in ch["verses"]:
                    m = re.match(r"v(\d+)-(\d+)", v.get("id") or "")
                    if m and not (book == "daniel" and ch.get("chapter") in (13, 14)):
                        cls.en.setdefault((book, int(m.group(1)), int(m.group(2))), []).append(
                            v.get("display_text") or v.get("text") or "")

    def test_pairs(self):
        pairs = [  # (lang, book, Studio ref, english word expected in the mapped site verse)
            ("greek", "sirach", (34, 12), "great table"),
            ("latin", "sirach", (31, 12), "great table"),
            ("greek", "deuteronomy", (29, 1), "words of the covenant"),
            ("hebrew", "deuteronomy", (28, 69), "words of the covenant"),
            ("latin", "deuteronomy", (29, 1), "words of the covenant"),
            ("latin", "deuteronomy", (29, 2), "Moses called"),
            ("hebrew", "leviticus", (11, 6), "hare"),
            ("hebrew", "leviticus", (11, 15), "raven"),
            ("hebrew", "deuteronomy", (14, 14), "raven"),
            ("hebrew", "2-chronicles", (3, 12), "cherub"),
            ("latin", "numbers", (1, 30), "Zebulun"),
            ("latin", "numbers", (1, 32), "Ephraim"),
            ("greek", "numbers", (27, 4), "brought their case"),
            ("hebrew", "proverbs", (16, 6), "mercy and faithfulness"),
            ("hebrew", "proverbs", (16, 4), "evil day"),
            ("latin", "daniel", (3, 54), "throne"),
            ("greek", "daniel", (3, 55), "throne"),
            ("hebrew", "jeremiah", (49, 34), "Zedekiah"),
        ]
        for lang, book, src, word in pairs:
            with self.subTest(lang=lang, book=book, src=src):
                ts = vz.to_saints(lang, book, *src)
                self.assertTrue(ts)
                text = " ".join(" ".join(self.en.get((book,) + t, [])) for t in ts)
                self.assertIn(word.lower(), text.lower())

    def test_first_target_holds_the_words(self):
        """All words are filed under the first target: its site English must carry the source's content."""
        pairs = [  # (lang, book, Studio ref, english expected in the FIRST target)
            ("hebrew", "ecclesiastes", (8, 1), "light up his face"),
            ("hebrew", "1-kings", (20, 3), "silver and gold"),
            ("hebrew", "exodus", (38, 30), "grating"),
            ("hebrew", "ezekiel", (7, 5), "behold"),
            ("hebrew", "proverbs", (31, 26), "wisely"),
            ("latin", "psalms", (110, 7), "works of his hands"),
            ("latin", "mark", (4, 40), "afraid"),
            ("latin", "exodus", (38, 25), "twenty years"),
            ("latin", "exodus", (38, 26), "hundred talents of silver"),
            ("latin", "exodus", (38, 27), "talent per capital"),
            ("latin", "wisdom-of-solomon", (2, 3), "cloud"),
            ("latin", "sirach", (37, 21), "tongue"),
            ("latin", "genesis", (50, 22), "machir"),
            ("latin", "hosea", (6, 3), "dawn"),
            ("latin", "revelation", (20, 7), "gog"),
            ("greek", "numbers", (21, 19), "plain of moab"),
            ("greek", "sirach", (23, 16), "heated soul"),
            ("greek", "wisdom-of-solomon", (4, 18), "dishonored corpse"),
            ("greek", "amos", (8, 1), "what do you see"),
            ("greek", "daniel", (5, 25), "this is the writing"),
            ("greek", "daniel", (4, 10), "tree"),
            ("greek", "daniel", (6, 1), "received the kingdom"),
            ("greek", "sirach", (34, 12), "great table"),
        ]
        for lang, book, src, word in pairs:
            with self.subTest(lang=lang, book=book, src=src):
                ts = vz.to_saints(lang, book, *src)
                self.assertTrue(ts)
                first = " ".join(self.en.get((book,) + ts[0], [])).lower()
                self.assertIn(word, first)


@unittest.skipUnless(os.path.exists(DB), "Studio database not present")
class LiveDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = _ro_conn()
        cls.text = {}
        for lang, book, c, v, t in cls.conn.execute(
                "SELECT ch.language, ch.book_slug, ch.chapter, v.verse, v.critical_text "
                "FROM verses v JOIN chapters ch ON ch.id = v.chapter_id"):
            cls.text[(lang, book, c, v)] = t or ""
        cls.report = vz.coverage_report(cls.conn)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_snapshot_inventories_match_the_database(self):
        for lang in vz.LANGS:
            tot = self.report[lang]["totals"]
            self.assertEqual(tot.get("not_in_snapshot", 0), 0, lang)
            self.assertEqual(tot.get("snapshot_not_in_db", 0), 0, lang)

    def test_every_target_exists(self):
        for lang in vz.LANGS:
            tot = self.report[lang]["totals"]
            self.assertEqual(tot.get("target_missing_on_site", 0), 0, lang)
            self.assertEqual(tot.get("studio_greek_target_missing_in_db", 0), 0, lang)

    def test_coverage(self):
        self.assertGreaterEqual(self.report["greek"]["totals"]["share_mapped"], 0.998)
        self.assertGreaterEqual(self.report["hebrew"]["totals"]["share_mapped"], 0.985)
        self.assertGreaterEqual(self.report["latin"]["totals"]["share_mapped"], 0.985)

    def test_greek_differences_are_reported(self):
        books = self.report["greek"]["books"]
        self.assertIn("29:1>28:69", books["deuteronomy"]["renumbered_refs"])
        self.assertIn("34:12>31:12", books["sirach"]["renumbered_refs"])
        self.assertIn("3:12", books["2-chronicles"]["site_only_refs"])
        self.assertIn("3:67", books["daniel"]["site_only_refs"])
        self.assertIn("17:21", books["matthew"]["unmapped_refs"])

    def _greek(self, book, c, v):
        return greek_bare(self.text.get(("greek", book, c, v), ""))

    def test_content_of_studio_greek_pairs(self):
        # (lang, book, src ref, Studio Greek ref, word in the source text, word in the Greek text)
        pairs = [
            ("hebrew", "genesis", (32, 2), (32, 2), "יעקב", "ιακωβαπηλθεν"),
            ("hebrew", "deuteronomy", (29, 1), (29, 2), "ויקרא", "εκαλεσενμωυσησ"),
            ("hebrew", "leviticus", (8, 20), (8, 19), "האיל", "κριον"),
            ("hebrew", "jeremiah", (31, 31), (38, 31), "ברית", "διαθηκην"),
            ("hebrew", "psalms", (23, 1), (22, 1), "רעי", "ποιμαινει"),
            ("hebrew", "daniel", (4, 1), (4, 4), "נבוכדנצר", "ναβουχοδονοσορ"),
            ("hebrew", "1-kings", (20, 1), (21, 1), "הדד", "αδερ"),
            ("hebrew", "malachi", (3, 23), (3, 22), "אליה", "ηλιαν"),
            ("hebrew", "1-kings", (8, 12), (8, 53), "בערפל", "γνοφου"),
            ("hebrew", "joshua", (19, 47), (19, 48), "לשם", "λαχεισ"),
            ("hebrew", "deuteronomy", (5, 17), (5, 17), "רצח", "φονευσεισ"),
            ("hebrew", "leviticus", (11, 6), (11, 5), "ארנבת", "δασυποδα"),
            ("hebrew", "proverbs", (20, 20), (20, 9), "אמו", "μητερα"),
            ("hebrew", "1-kings", (7, 26), (7, 12), "כוס", "ποτηριου"),
            ("hebrew", "jeremiah", (25, 13), (25, 13), "בספר", "βιβλιω"),
            ("latin", "deuteronomy", (5, 17), (5, 17), "occides", "φονευσεισ"),
            ("latin", "deuteronomy", (5, 18), (5, 18), "moechaberis", "μοιχευσεισ"),
            ("latin", "exodus", (39, 22), (36, 31), "mala punica", "ροασ"),
            ("latin", "genesis", (31, 55), (32, 1), "laban", "λαβαν"),
            ("latin", "sirach", (31, 12), (34, 12), "mensam", "τραπεζησ"),
            ("latin", "sirach", (19, 1), (19, 1), "ebriosus", "μεθυσοσ"),
            ("latin", "esther", (10, 4), (10, 3), "mardochaeus", "μαρδοχαιοσ"),
            ("latin", "numbers", (1, 32), (1, 30), "ephraim", "εφραιμ"),
            ("latin", "leviticus", (11, 6), (11, 5), "lepus", "δασυποδα"),
        ]
        from studio.lexica import latin_bare
        for lang, book, src, dst, src_word, grk_word in pairs:
            with self.subTest(lang=lang, book=book, src=src):
                self.assertIn(dst, vz.to_studio_greek(lang, book, *src))
                raw = self.text[(lang, book) + src]
                if lang == "hebrew":
                    self.assertIn(hebrew_consonants(src_word), hebrew_consonants(raw))
                else:
                    self.assertIn(latin_bare(src_word), latin_bare(raw))
                self.assertIn(grk_word, self._greek(book, *dst))

    def test_content_behind_the_second_review(self):
        from studio.lexica import latin_bare
        # Studio Greek Sir 1:1 is the Prologue followed by 1:1: mapped to nothing
        self.assertIn("πολλωνκαιμεγαλων", self._greek("sirach", 1, 1))
        self.assertTrue(self._greek("sirach", 1, 1).endswith("πασασοφιαπαρακυριουκαιμεταυτουεστινειστοναιωνα"))
        self.assertEqual(vz.to_saints("greek", "sirach", 1, 1), [])
        # Studio Greek Ps 12:4-5 cleanly separated after Stage 1 repair (12:4 = site 12:5, 12:5 = site 12:6a)
        self.assertIn("ισχυσαπροσαυτον", self._greek("psalms", 12, 4))
        self.assertNotIn("ισχυσαπροσαυτον", self._greek("psalms", 12, 5))
        self.assertIn("ελεεισου", self._greek("psalms", 12, 5))
        # Theodotion Dan 5:25 is the inscription; 6:16 the law of the Medes and Persians
        self.assertIn("μανη", self._greek("daniel", 5, 25))
        self.assertIn("μηδοισκαιπερσαισ", self._greek("daniel", 6, 16))
        # Studio Greek 1 Kgs 21:2 ends with 'Thus says the son of Ader'; Ecc 7:29 with 'Who knows the wise?'
        self.assertTrue(self._greek("1-kings", 21, 2).endswith("ταδελεγειυιοσαδερ"))
        self.assertIn("τισοιδενσοφουσ", self._greek("ecclesiastes", 7, 29))
        # Latin verses whose main content lies in the neighbouring site verse
        self.assertIn("operamanuum", latin_bare(self.text[("latin", "psalms", 110, 7)]))
        self.assertIn("timuerunttimoremagno", latin_bare(self.text[("latin", "mark", 4, 40)]))
        self.assertIn("sexcentistribusmillibus", latin_bare(self.text[("latin", "exodus", 38, 25)]))
        self.assertIn("centumtalentaargenti", latin_bare(self.text[("latin", "exodus", 38, 26)]))
        self.assertIn("detalentiscentum", latin_bare(self.text[("latin", "exodus", 38, 27)]))
        self.assertEqual(vz.to_studio_greek("latin", "exodus", 38, 25), [(39, 3)])
        self.assertEqual(vz.to_studio_greek("latin", "exodus", 38, 26), [(39, 4)])
        self.assertEqual(vz.to_studio_greek("latin", "exodus", 38, 27), [(39, 5)])
        self.assertEqual(vz.from_saints("latin", "exodus", 39, 2), [])
        self.assertEqual(vz.from_saints("latin", "exodus", 39, 3), [(38, 25)])
        self.assertEqual(vz.from_saints("latin", "exodus", 39, 4), [(38, 26), (38, 27)])
        self.assertIn("uestigiumnubis", latin_bare(self.text[("latin", "wisdom-of-solomon", 2, 3)]))


class UnmappedVerseResolution(unittest.TestCase):
    """Part A newly mapped Saints.Bible verses and Part B extra-site anchor / duplicate invariants."""

    NEW_SAINTS_CASES = [
        # Hebrew + Latin Exodus & 1 Kings lettered-verse folds & Exod 38:27 / 38:18
        ("hebrew", "exodus", (28, 24), [(28, 29)]),
        ("hebrew", "exodus", (28, 25), [(28, 29)]),
        ("hebrew", "exodus", (35, 17), [(35, 12)]),
        ("hebrew", "exodus", (36, 34), [(38, 18)]),
        ("hebrew", "exodus", (40, 31), [(38, 27)]),
        ("hebrew", "exodus", (40, 32), [(38, 27)]),
        ("hebrew", "1-kings", (14, 1), [(12, 24)]),
        ("hebrew", "1-kings", (14, 10), [(12, 24)]),
        ("hebrew", "1-kings", (14, 18), [(12, 24)]),
        ("hebrew", "1-kings", (14, 7), []),
        ("hebrew", "1-kings", (14, 15), []),
        ("hebrew", "1-kings", (14, 20), []),
        ("hebrew", "1-kings", (22, 47), [(16, 28)]),
        ("hebrew", "1-kings", (22, 50), [(16, 28)]),
        ("latin", "exodus", (28, 24), [(28, 29)]),
        ("latin", "exodus", (35, 17), [(35, 12)]),
        ("latin", "exodus", (40, 29), [(38, 27)]),
        ("latin", "exodus", (40, 30), [(38, 27)]),
        ("latin", "1-kings", (4, 27), [(5, 1)]),
        ("latin", "1-kings", (4, 28), [(5, 1)]),
        ("latin", "1-kings", (14, 4), [(12, 24)]),
        ("latin", "1-kings", (22, 49), [(16, 28)]),
        ("latin", "2-maccabees", (12, 46), [(12, 45)]),
        ("latin", "proverbs", (20, 20), [(20, 9)]),
        ("latin", "proverbs", (20, 22), [(20, 9)]),
        # Latin Sirach Vulgate-split continuations
        ("latin", "sirach", (1, 32), [(1, 25)]),
        ("latin", "sirach", (1, 35), [(1, 27)]),
        ("latin", "sirach", (1, 40), [(1, 30)]),
        ("latin", "sirach", (2, 23), [(2, 18)]),
        ("latin", "sirach", (3, 25), [(3, 23)]),
        ("latin", "sirach", (5, 17), [(5, 14)]),
        ("latin", "sirach", (6, 1), [(5, 15)]),
        ("latin", "sirach", (9, 19), [(9, 13)]),
        ("latin", "sirach", (9, 20), [(9, 13)]),
        ("latin", "sirach", (13, 27), [(13, 22)]),
        ("latin", "sirach", (13, 29), [(13, 23)]),
        ("latin", "sirach", (22, 8), [(22, 9)]),
        ("latin", "sirach", (22, 29), [(22, 23)]),
        ("latin", "sirach", (23, 28), [(23, 19)]),
        ("latin", "sirach", (24, 43), [(24, 31)]),
        ("latin", "sirach", (25, 30), [(25, 22)]),
        ("latin", "sirach", (25, 32), [(25, 23)]),
        ("latin", "sirach", (25, 36), [(25, 26)]),
        ("latin", "sirach", (26, 20), [(26, 15)]),
        ("latin", "sirach", (26, 26), [(26, 28)]),
        ("latin", "sirach", (26, 27), [(26, 28)]),
        ("latin", "sirach", (31, 33), [(31, 27)]),
        ("latin", "sirach", (31, 35), [(31, 27)]),
        ("latin", "sirach", (31, 39), [(31, 29)]),
        ("latin", "sirach", (31, 42), [(31, 31)]),
        ("latin", "sirach", (34, 27), [(34, 22)]),
        ("latin", "sirach", (43, 34), [(43, 30)]),
        ("latin", "sirach", (45, 29), [(45, 23)]),
        ("latin", "sirach", (47, 27), [(47, 23)]),
        ("latin", "sirach", (47, 28), [(47, 23)]),
        ("latin", "sirach", (49, 18), [(49, 15)]),
    ]

    def test_newly_mapped_saints_verses(self):
        for lang, book, (c, v), want in self.NEW_SAINTS_CASES:
            with self.subTest(lang=lang, book=book, ref=(c, v)):
                self.assertEqual(vz.to_saints(lang, book, c, v), want)

    def test_extra_site_anchors_cover_all_non_duplicate_unmapped_verses(self):
        for lang in vz.LANGS:
            for book, chapters in vz.inventory(lang).items():
                for c, vs in chapters.items():
                    for v in vs:
                        if vz.to_saints(lang, book, c, v):
                            self.assertIsNone(vz.to_extra_site_anchor(lang, book, c, v))
                            continue
                        if vz.is_duplicate_or_placeholder(lang, book, c, v):
                            self.assertIsNone(vz.to_extra_site_anchor(lang, book, c, v))
                        else:
                            anc = vz.to_extra_site_anchor(lang, book, c, v)
                            self.assertIsNotNone(anc, (lang, book, c, v))
                            self.assertIn((c, v), vz.from_extra_site_anchor(lang, book, *anc))

    def test_extra_site_cross_language_alignment_and_duplicates(self):
        # Theodotion Daniel 4:6 aligns Hebrew 4:3, Greek 4:6, and Latin 4:3 onto one anchor
        self.assertEqual(vz.to_extra_site_anchor("hebrew", "daniel", 4, 3), (4, 6))
        self.assertEqual(vz.to_extra_site_anchor("greek", "daniel", 4, 6), (4, 6))
        self.assertEqual(vz.to_extra_site_anchor("latin", "daniel", 4, 3), (4, 6))
        self.assertEqual(vz.from_extra_site_anchor("hebrew", "daniel", 4, 6), [(4, 3)])
        # MT Ps 116:14 and Vulgate Ps 115:5 share extra-site anchor (115, 5)
        self.assertEqual(vz.to_extra_site_anchor("hebrew", "psalms", 116, 14), (115, 5))
        self.assertEqual(vz.to_extra_site_anchor("latin", "psalms", 115, 5), (115, 5))
        self.assertEqual(vz.from_extra_site_anchor("hebrew", "psalms", 115, 5), [(116, 14)])
        # NT TR and MT-only verses share anchors across languages
        self.assertEqual(vz.to_extra_site_anchor("greek", "matthew", 18, 11), (18, 11))
        self.assertEqual(vz.to_extra_site_anchor("latin", "matthew", 18, 11), (18, 11))
        self.assertEqual(vz.to_extra_site_anchor("hebrew", "1-samuel", 17, 12), (17, 12))
        self.assertEqual(vz.to_extra_site_anchor("latin", "1-samuel", 17, 12), (17, 12))
        # Confirmed duplicates and placeholders are excluded
        for lang, book, c, v in [
            ("greek", "psalms", 25, 22),
            ("greek", "romans", 14, 24),
            ("latin", "sirach", 19, 6),
        ]:
            self.assertTrue(vz.is_duplicate_or_placeholder(lang, book, c, v))
            self.assertIsNone(vz.to_extra_site_anchor(lang, book, c, v))
        # Former Clem-Saints Latin placeholders/duplicates are real native Vulgate verses now
        for book, c, v in [("sirach", 1, 15), ("numbers", 16, 36), ("jeremiah", 29, 30), ("ezekiel", 20, 45)]:
            self.assertFalse(vz.is_duplicate_or_placeholder("latin", book, c, v))


if __name__ == "__main__":
    unittest.main()
