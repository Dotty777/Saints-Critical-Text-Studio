"""Tests for the website critical-text export (studio/concordance_site.py + concordance_layer, 19 Nov 2026).

Spec: docs/CRITICAL-TEXT-AND-WORKSPACE-SPEC.md in the Saints Concordance plugin repo, sections 1 and 1b.

* the unplaced source verses (text present, ``to_saints`` gives []) are kept in source order, each after
  the Saints verse of the preceding placed source verse (``(0, 0)`` before the first);
* each critical-text verse is a string or one string per source reference, and ``" ".join`` of it equals
  the word-layer verse text (checked on the real Studio text of Psalms, 1 Kings, Esther, Sirach, Exodus
  and John in all three languages);
* the Studio Greek Sirach 1:1 is split into the translator's Prologue and site verse 1:1;
* the word-layer rows lose their text (``verses[i][3] == ""``) only where the critical text rebuilds it.

The real-data tests open the Studio database READ-ONLY (``CTS_REAL_DB`` overrides the path, e.g. a
sandbox copy) and skip when it is missing.  No tagger runs (``tag=False``): placement does not depend on
tagging.
"""

from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

try:
    from . import test_studio as _ts  # noqa: F401  (sandbox env before ``studio`` is imported)
except ImportError:
    import test_studio as _ts  # type: ignore[no-redef]  # noqa: F401

from studio import concordance_layer as cl  # noqa: E402
from studio import concordance_site as cs  # noqa: E402
from studio.catalog import BOOKS_BY_SLUG, STUDIO_ROOT  # noqa: E402

REAL_DB = Path(os.environ.get("CTS_REAL_DB") or (STUDIO_ROOT / "data" / "studio.db"))
LANG_CODE = {"hebrew": "heb", "greek": "grc", "latin": "lat"}
SAMPLE_BOOKS = ("psalms", "1-kings", "esther", "sirach", "exodus", "john")


def _real_conn() -> sqlite3.Connection:
    return sqlite3.connect(REAL_DB.resolve().as_uri() + "?mode=ro", uri=True)


def _mem_db(lang: str, book: str, chapters: dict) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE chapters (id INTEGER PRIMARY KEY, language TEXT, book_slug TEXT, chapter INTEGER)")
    conn.execute("CREATE TABLE verses (chapter_id INTEGER, verse INTEGER, critical_text TEXT)")
    for i, (ch, verses) in enumerate(sorted(chapters.items()), start=1):
        conn.execute("INSERT INTO chapters VALUES (?, ?, ?, ?)", (i, lang, book, ch))
        conn.executemany("INSERT INTO verses VALUES (?, ?, ?)", [(i, v, t) for v, t in verses.items()])
    return conn


def _roundtrip(payload: dict) -> dict:
    """Exactly what the browser gets: gzip JSON with the exporter's settings."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "x.json.gz"
        cs._gz(p, payload)
        return json.loads(gzip.decompress(p.read_bytes()).decode("utf-8"))


class TestUnplacedAttachment(unittest.TestCase):
    """The attachment rule on a fixed mapping (so the test does not move with versification edits)."""

    MAP = {(1, 1): [], (1, 2): [(1, 1)], (1, 3): [(1, 2)], (1, 4): [], (1, 5): [],
           (2, 1): [(1, 2)], (2, 2): [], (2, 3): [(2, 5), (2, 6)], (3, 1): [], (3, 2): [(3, 1)]}

    def _layers(self, tag=False):
        texts = {1: {1: "a1", 2: "b2", 3: "c3", 4: "d4", 5: "e5", 6: "   "},
                 2: {1: "f1", 2: "g2", 3: "h3"}, 3: {1: "i1", 2: "j2"}}
        conn = _mem_db("latin", "ruth", texts)

        def fake(lang, book, ch, v):
            return list(self.MAP.get((ch, v), [(ch, v)]))

        with mock.patch("studio.lexica.versification.to_saints", side_effect=fake):
            out = list(cl.saints_book_layers(conn, "latin", "ruth", tag=tag))
        conn.close()
        return out

    def test_unplaced_in_source_order_after_preceding_placed_verse(self):
        (layer,) = self._layers()
        self.assertEqual(layer.book, "ruth")
        got = [(u.src, u.after, u.text, u.reason) for u in layer.unplaced]
        self.assertEqual(got, [
            ("1:1", (0, 0), "a1", "no-site-verse"),      # before the first verse of the book
            ("1:4", (1, 2), "d4", "no-site-verse"),      # after 1:3's Saints verse 1:2
            ("1:5", (1, 2), "e5", "no-site-verse"),
            ("2:2", (1, 2), "g2", "no-site-verse"),      # 2:1 was merged into Saints 1:2
            ("3:1", (2, 5), "i1", "no-site-verse"),      # first target of a one-to-several verse
        ])
        # empty source verses are neither placed nor unplaced
        self.assertNotIn("1:6", [u.src for u in layer.unplaced])
        rows = [(sv.chapter, sv.verse, sv.src, sv.texts) for sv in layer.verses]
        self.assertEqual(rows, [(1, 1, [(1, 2)], ["b2"]), (1, 2, [(1, 3), (2, 1)], ["c3", "f1"]),
                                (2, 5, [(2, 3)], ["h3"]), (3, 1, [(3, 2)], ["j2"])])

    def test_saints_verses_keeps_its_old_output(self):
        texts = {1: {1: "a1", 2: "b2"}}
        conn = _mem_db("latin", "ruth", texts)
        with mock.patch("studio.lexica.versification.to_saints",
                        side_effect=lambda lang, b, c, v: [] if v == 1 else [(c, v)]):
            with mock.patch.object(cl, "_module") as mod:
                mod.return_value.tag_chapter.side_effect = lambda b, c, vs: {v: [] for v in vs}
                out = list(cl.saints_verses(conn, "latin", "ruth"))
        conn.close()
        self.assertEqual(len(out), 1)
        slug, verses = out[0]
        self.assertEqual(slug, "ruth")
        self.assertEqual([(sv.chapter, sv.verse, sv.texts) for sv in verses], [(1, 2, ["b2"])])

    def test_ct_payload_carries_unplaced_and_arrays(self):
        (layer,) = self._layers()
        payload, rows, stats = cs.critical_text_payload("lat", "ruth", 8, layer.verses, layer.unplaced)
        back = _roundtrip(payload)
        self.assertEqual(back["schema"], cs.CT_SCHEMA[cs.CT_LAYOUT])
        self.assertEqual(cs.expand_compact_ct(back), [[1, 1, "1:2", "b2"], [1, 2, "1:3,2:1", ["c3", "f1"]],
                                                      [2, 5, "2:3", "h3"], [3, 1, "3:2", "j2"]])
        self.assertEqual(back["unplaced"][0], [0, 0, "1:1", "a1", "no-site-verse"])
        self.assertEqual(back["unplaced"][-1], [2, 5, "3:1", "i1", "no-site-verse"])
        self.assertEqual(stats["unplaced"], 5)
        self.assertEqual(stats["multi"], 1)
        self.assertIn(cs.CT_NUMBERING_NOTE["lat"], back["notes"])


class TestCompactLayout(unittest.TestCase):

    def test_compact_round_trip(self):
        rows = [[1, 1, "1:1", "a"], [1, 2, "1:2", "b"], [1, 4, "1:3", "c"], [2, 1, "2:1,2:2", ["d", "e"]],
                [2, 2, "2:3", "f"], [10, 3, "10:3", "g"]]
        c = cs.compact_ct_rows(rows)
        self.assertEqual(c["start"], [[0, 1, 1], [2, 1, 4], [3, 2, 1], [5, 10, 3]])
        self.assertEqual(c["src"], {"2": "1:3", "3": "2:1,2:2", "4": "2:3"})
        self.assertEqual(cs.expand_compact_ct(_roundtrip(c)), rows)
        self.assertEqual(cs.expand_compact_ct({"verses": rows}), rows)


class TestWordLayerBlanking(unittest.TestCase):

    def test_text_blanked_only_where_ct_rebuilds_it(self):
        sv = cl.SaintsVerse
        verses = [sv("john", 1, 1, [(1, 1)], ["Ἐν ἀρχῇ ἦν ὁ λόγος,"], [object()] * 5),
                  sv("john", 1, 2, [(1, 2), (1, 3)], ["οὗτος ἦν", "πάντα δι’ αὐτοῦ"], [object()] * 5),
                  sv("john", 1, 4, [(1, 4)], ["ἐν αὐτῷ ζωὴ ἦν"], [object()] * 4)]
        ct_rows = [[1, 1, "1:1", "Ἐν ἀρχῇ ἦν ὁ λόγος,"], [1, 2, "1:2,1:3", ["οὗτος ἦν", "πάντα δι’ αὐτοῦ"]],
                   [1, 4, "1:4", "something else"]]
        rows, kept = cs.word_layer_rows(verses, ct_rows)
        self.assertEqual(rows, [[1, 1, "1:1", "", 5], [1, 2, "1:2,1:3", "", 5],
                                [1, 4, "1:4", "ἐν αὐτῷ ζωὴ ἦν", 4]])
        self.assertEqual(kept, 1)
        for r in rows:
            self.assertEqual(len(r), 5)   # the 5-tuple shape stays


class TestWordLayerLayout(unittest.TestCase):

    def _payload(self):
        return {"schema": "saints-concordance-book/v1", "lang": "grc", "book": "john", "order": 47,
                "lemma": [11, 12, 13], "verses": [[1, 1, "1:1", "", 3], [1, 2, "1:2,1:3", "", 2], [2, 1, "2:4", "", 1]],
                "L": [1, 2, 0, 3, 1, 2], "M": [1, 1, 0, 2, 1, 1], "F": [1, 2, 0, 1, 1, 2], "Ac": [[], [], [], [], []],
                "Atier": 1, "englishColumn": "saints"}

    def test_compact_round_trip(self):
        p = self._payload()
        c = cs.compact_word_layer(p, "compact")
        self.assertEqual(c["schema"], "saints-concordance-book/v2")
        self.assertNotIn("verses", c)
        self.assertNotIn("F", c)
        self.assertEqual(c["Fl"], [1, 2, 1])
        self.assertEqual(c["vstart"], [[0, 1, 1], [2, 2, 1]])
        self.assertEqual(c["vsrc"], {"1": "1:2,1:3", "2": "2:4"})
        self.assertEqual(c["vn"], [3, 2, 1])
        back = cs.expand_word_layer(_roundtrip(c))
        self.assertEqual(back["verses"], p["verses"])
        self.assertEqual(back["F"], p["F"])
        self.assertEqual({k: v for k, v in back.items() if k != "schema"},
                         {k: v for k, v in p.items() if k != "schema"})
        self.assertEqual(cs.compact_word_layer(p, "rows")["verses"], p["verses"])

    def test_inconsistent_flags_and_kept_text_fall_back(self):
        p = self._payload()
        p["F"] = [1, 2, 0, 1, 2, 2]          # lemma 1 is content once, function once
        p["verses"][1][3] = "kept text"
        c = cs.compact_word_layer(p, "compact")
        self.assertEqual(c["F"], p["F"])
        self.assertEqual(c["verses"], p["verses"])
        self.assertNotIn("Fl", c)
        self.assertNotIn("vn", c)
        self.assertEqual(cs.expand_word_layer(c)["F"], p["F"])


class TestSirachPrologue(unittest.TestCase):

    def test_split_synthetic(self):
        self.assertEqual(cs.split_sirach_prologue("Πολλῶν καὶ μεγάλων. " + cs.SIRACH_SPLIT + ", καὶ μετʼ αὐτοῦ."),
                         ("Πολλῶν καὶ μεγάλων.", cs.SIRACH_SPLIT + ", καὶ μετʼ αὐτοῦ."))
        self.assertIsNone(cs.split_sirach_prologue(cs.SIRACH_SPLIT + " only"))     # no Prologue before it
        self.assertIsNone(cs.split_sirach_prologue("no opening here"))
        self.assertIsNone(cs.split_sirach_prologue("x " + cs.SIRACH_SPLIT + " y " + cs.SIRACH_SPLIT))

    def test_split_constant_is_clean(self):
        self.assertEqual(cs.SIRACH_SPLIT, "Πᾶσα σοφία παρὰ Κυρίου")

    def test_prologue_row_when_verse_placed(self):
        """If versification ever files Greek Sir 1:1 under site 1:1, the ct file still splits it and the
        word layer keeps its (Prologue + 1:1) text, so the decoder never mixes the two."""
        sv = cl.SaintsVerse("sirach", 1, 1, [(1, 1)], ["Πρόλογος. " + cs.SIRACH_SPLIT + ", καὶ"], [object()] * 6)
        payload, rows, stats = cs.critical_text_payload("grc", "sirach", 26, [sv], [])
        self.assertEqual(rows, [[1, 1, "1:1", cs.SIRACH_SPLIT + ", καὶ"]])
        self.assertEqual(payload["unplaced"], [[0, 0, "Prologue", "Πρόλογος.", "prologue"]])
        wl, kept = cs.word_layer_rows([sv], rows)
        self.assertEqual(kept, 1)
        self.assertEqual(wl[0][3], sv.texts[0])


class TestCriticalTextsJson(unittest.TestCase):

    def test_editions_and_no_licence(self):
        d = json.loads(json.dumps(cs.critical_texts_json(), ensure_ascii=False))
        self.assertEqual(d["schema"], "saints-critical-texts/v1")
        self.assertEqual({c: e["name"] for c, e in d["editions"].items()},
                         {"heb": "Saints Hebrew Critical Text", "grc": "Saints Greek Critical Text",
                          "lat": "Saints Latin Critical Text"})
        self.assertIsNone(d["licence"])
        self.assertEqual(d["licenceNote"], "The licence of the edition texts has not been set yet.")
        for c, e in d["editions"].items():
            self.assertTrue(e["credits"] and e["legend"] and e["numbering"] and e["short"])
            for item in e["legend"]:
                self.assertEqual(len(item), 2)
        self.assertIn("ketiv", json.dumps(d["editions"]["heb"]["legend"]))
        self.assertTrue(any("MAM" in c for c in d["editions"]["heb"]["credits"]))


@unittest.skipUnless(REAL_DB.exists(), f"Studio database not found at {REAL_DB}")
class TestRealData(unittest.TestCase):
    """Real Studio text, read-only."""

    @classmethod
    def setUpClass(cls):
        cls.conn = _real_conn()
        cls.layers = {}
        for lang in ("hebrew", "greek", "latin"):
            for layer in cl.saints_book_layers(cls.conn, lang, books=SAMPLE_BOOKS, tag=False):
                cls.layers[(LANG_CODE[lang], layer.book)] = layer

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_sample_books_present(self):
        for slug in SAMPLE_BOOKS:
            for code in ("grc", "lat"):
                self.assertIn((code, slug), self.layers)
        for slug in ("psalms", "1-kings", "esther", "exodus"):
            self.assertIn(("heb", slug), self.layers)

    def test_join_invariant_and_blanking(self):
        for (code, slug), layer in sorted(self.layers.items()):
            with self.subTest(lang=code, book=slug):
                payload, rows, stats = cs.critical_text_payload(code, slug, BOOKS_BY_SLUG[slug].order,
                                                                layer.verses, layer.unplaced)
                back = _roundtrip(payload)
                ct = {(r[0], r[1]): r for r in cs.expand_compact_ct(back)}
                self.assertEqual(cs.expand_compact_ct(back), rows)
                # the same rows in the spec's v1 layout
                v1, _, _ = cs.critical_text_payload(code, slug, 1, layer.verses, layer.unplaced, layout="verses")
                self.assertEqual(v1["verses"], rows)
                wl, kept = cs.word_layer_rows(layer.verses, rows)
                self.assertEqual(kept, 0)
                for sv, w in zip(layer.verses, wl):
                    r = ct[(sv.chapter, sv.verse)]
                    self.assertEqual(w[3], "")
                    self.assertEqual(r[2], w[2])                       # same srcRefs string
                    srcs = r[2].split(",")
                    if len(srcs) == 1:
                        self.assertIsInstance(r[3], str)
                    else:
                        self.assertIsInstance(r[3], list)
                        self.assertEqual(len(r[3]), len(srcs))
                    self.assertEqual(cs.ct_join(r[3]), " ".join(sv.texts))   # what the decoder rebuilds
                # every unplaced entry hangs after (0, 0) or a verse of the file
                for u in back["unplaced"]:
                    self.assertEqual(len(u), 5)
                    self.assertIn(u[4], ("no-site-verse", "prologue"))
                    self.assertTrue((u[0], u[1]) == (0, 0) or (u[0], u[1]) in ct, u)
                    self.assertTrue(u[3].strip())
                # every source verse with text appears exactly once (placed or unplaced)
                n_src = sum(len(sv.src) for sv in layer.verses) + len(layer.unplaced)
                n_out = sum(len(r[2].split(",")) for r in rows) + len(back["unplaced"])
                extra = 1 if (code, slug) == ("grc", "sirach") and stats["prologue"] else 0
                self.assertEqual(n_out, n_src + extra)

    def test_hebrew_psalm_in_mt_numbering(self):
        payload, rows, _ = cs.critical_text_payload("heb", "psalms", 21, self.layers[("heb", "psalms")].verses,
                                                    self.layers[("heb", "psalms")].unplaced)
        by = {(r[0], r[1]): r for r in rows}
        self.assertEqual(by[(22, 1)][2], "23:1")              # site Ps 22 = MT Ps 23
        self.assertIn(cs.CT_NUMBERING_NOTE["heb"], payload["notes"])

    def test_multi_source_verses_are_arrays(self):
        """1 Kings (Hebrew merges such as MT 9:15, 9:17-22, 10:22 -> site 10:22) and Latin Esther 10:3."""
        found = 0
        for key in (("heb", "1-kings"), ("lat", "esther")):
            layer = self.layers[key]
            _, rows, stats = cs.critical_text_payload(key[0], key[1], 1, layer.verses, layer.unplaced)
            self.assertGreater(stats["multi"], 0, key)
            found += stats["multi"]
        self.assertGreater(found, 1)

    def test_sirach_greek_prologue_split_on_real_text(self):
        layer = self.layers[("grc", "sirach")]
        raw = self.conn.execute(
            "SELECT v.critical_text FROM verses v JOIN chapters c ON c.id = v.chapter_id "
            "WHERE c.language = 'greek' AND c.book_slug = 'sirach' AND c.chapter = 1 AND v.verse = 1").fetchone()[0]
        payload, rows, stats = cs.critical_text_payload("grc", "sirach", 26, layer.verses, layer.unplaced)
        back = _roundtrip(payload)
        self.assertEqual(stats["prologue"], 1)
        pro = [u for u in back["unplaced"] if u[4] == "prologue"]
        self.assertEqual(len(pro), 1)
        self.assertEqual(pro[0][:3], [0, 0, "Prologue"])
        self.assertTrue(pro[0][3].startswith("Πολλῶν καὶ μεγάλων ἡμῖν"))
        self.assertTrue(pro[0][3].endswith("ἐν νόμῳ βιοτεύειν."))
        v11 = [r for r in cs.expand_compact_ct(back) if (r[0], r[1]) == (1, 1)]
        self.assertEqual(len(v11), 1)
        self.assertEqual(v11[0][2], "1:1")
        self.assertEqual(v11[0][3], "Πᾶσα σοφία παρὰ Κυρίου, καὶ μετʼ αὐτοῦ ἐστιν εἰς τὸν αἰῶνα.")
        self.assertEqual(pro[0][3] + " " + v11[0][3], raw.strip())     # nothing lost or added
        self.assertEqual(cs.expand_compact_ct(back)[1][:2], [1, 2])     # 1:1 comes first, then 1:2
        self.assertNotIn("1:1", [u[2] for u in back["unplaced"]])
        self.assertIn(cs.CT_NOTES[("grc", "sirach")][0], back["notes"])

    def test_latin_sirach_has_no_prologue(self):
        layer = self.layers[("lat", "sirach")]
        _, rows, stats = cs.critical_text_payload("lat", "sirach", 26, layer.verses, layer.unplaced)
        self.assertEqual(stats["prologue"], 0)
        self.assertTrue(rows[0][3].startswith("Omnis sapientia"))

    def test_john_greek_is_plain(self):
        layer = self.layers[("grc", "john")]
        payload, rows, _ = cs.critical_text_payload("grc", "john", 47, layer.verses, layer.unplaced)
        self.assertEqual(rows[0][:3], [1, 1, "1:1"])
        self.assertTrue(rows[0][3].startswith("Ἐν ἀρχῇ ἦν ὁ λόγος"))
        self.assertEqual(payload["notes"], [])


if __name__ == "__main__":
    unittest.main()
