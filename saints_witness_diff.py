#!/usr/bin/env python3
"""
saints_witness_diff.py
======================
Automated Modern Critical Text Ingestion & Multi-Witness Diff Engine
for Saints Critical Text Studio (Saints.Bible).

Supports both local repository layouts automatically:
  1. Studio 7-Division Critical Editions (Saints-Critical-Text-Studio):
       - Saints-Greek-Critical-Text   (70 books)
       - Saints-Hebrew-Critical-Text  (38/39 Masoretic OT books)
       - Saints-Latin-Critical-Text   (70 Vulgate books)
  2. Standalone Translation Clones (Dotty777 layout):
       - Greek-Translation   (27 NT books + 43 LXX/Old Greek books = 70 books)
       - Hebrew-Translation  (39 Masoretic OT books)
       - Latin-Translation   (70 Vulgate books)

Key Principles:
  1. Non-Destructive Companion Layer: Never overwrites your Saints base source,
     Studio SQLite database, or English translation files. Outputs structured
     JSON apparatus sidecars and an AUDIT-style Markdown report.
  2. Pinned Commit SHAs + SHA-256 Lockfile: Pins every upstream critical corpus
     to an immutable Git commit SHA and records SHA-256 checksums for strict
     reproducibility.
  3. License Hygiene by Default:
       - Tier 'bundle' (default): Ingests ONLY Public Domain & CC BY 4.0 texts
         safe to bundle directly in open-source repositories (SRGNT, SBLGNT,
         STEPBible TAGNT/TAHOT/TVTMS, OpenScriptures WLC & MAPM).
       - Tier 'nc-local': Optionally fetches CC BY-NC-SA 4.0 corpora
         (LXX-Rahlfs-1935, PROIEL Critical Vulgate NT) into a git-ignored
         local cache strictly for offline scholarly comparison.
  4. Philological Normalization (Zero False-Positive Flood):
       - Greek: Separates substantive lexical/word-order variants from accent,
         breathing, movable-nu, elision, CNTR/TAGNT sigla (¶, ˚), and punctuation
         differences; decodes TAGNT edition brackets (NA28, THGNT, SBLGNT, WH,
         Treg, Byz, TR).
       - Hebrew: Avoids destructive Unicode NFC on pointed text; orders marks
         canonically (consonant -> shin/sin dot -> dagesh -> vowel -> meteg ->
         accents), normalizes typographic qamets-qatan vs qamets, and classifies
         Ketiv/Qere choices (including parenthesized MAM Ketiv notes) separately
         from consonantal or vocalization variants.
       - Latin: Separates lexical variants from u/v, i/j, and ae/oe orthography.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import difflib
import hashlib
import html.parser
import json
import os
import re
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# 1. Pinned Upstream Critical Corpora Registry
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class WitnessCorpusSpec:
    key: str
    title: str
    language: str  # "greek" | "hebrew" | "latin" | "versification"
    scope: str     # "nt" | "ot_mt" | "ot_lxx" | "all"
    repo: str      # "owner/repo"
    pinned_sha: str
    license_id: str
    redistributable_open: bool
    attribution: str
    file_globs: Tuple[str, ...]


UPSTREAM_CORPORA: Dict[str, WitnessCorpusSpec] = {
    "TVTMS": WitnessCorpusSpec(
        key="TVTMS",
        title="STEPBible Translators Versification Traditions (TVTMS)",
        language="versification",
        scope="all",
        repo="STEPBible/STEPBible-Data",
        pinned_sha="5de0a47f35f0fc13dfe1430d104e5db8a4285f9c",
        license_id="CC-BY-4.0",
        redistributable_open=True,
        attribution="STEPBible.org / Tyndale House Cambridge (CC BY 4.0)",
        file_globs=("Versification/TVTMS*.txt",),
    ),
    "SRGNT": WitnessCorpusSpec(
        key="SRGNT",
        title="Statistical Restoration Greek New Testament (CNTR)",
        language="greek",
        scope="nt",
        repo="Center-for-New-Testament-Restoration/SR",
        pinned_sha="4be18e67c6870388d317d38d2b10a70e8b5e8775",
        license_id="CC-BY-4.0",
        redistributable_open=True,
        attribution="Alan Bunning, Center for New Testament Restoration (2022, CC BY 4.0)",
        file_globs=("SR.txt",),
    ),
    "SBLGNT": WitnessCorpusSpec(
        key="SBLGNT",
        title="MorphGNT SBL Greek New Testament",
        language="greek",
        scope="nt",
        repo="morphgnt/sblgnt",
        pinned_sha="aaed91e57c8e4a8dc9a2383e129ca5e75fe6393d",
        license_id="CC-BY-4.0 (text) / CC-BY-SA-3.0 (morphology)",
        redistributable_open=True,
        attribution="Michael W. Holmes (SBLGNT) / James K. Tauber (MorphGNT v6.12)",
        file_globs=("*-morphgnt.txt",),
    ),
    "TAGNT": WitnessCorpusSpec(
        key="TAGNT",
        title="STEPBible Translators Amalgamated Greek NT (NA28/THGNT/SBLGNT/Byz/TR)",
        language="greek",
        scope="nt",
        repo="STEPBible/STEPBible-Data",
        pinned_sha="5de0a47f35f0fc13dfe1430d104e5db8a4285f9c",
        license_id="CC-BY-4.0",
        redistributable_open=True,
        attribution="STEPBible.org / Tyndale House Cambridge (CC BY 4.0)",
        file_globs=("Translators Amalgamated OT+NT/TAGNT*.txt",),
    ),
    "TAHOT": WitnessCorpusSpec(
        key="TAHOT",
        title="STEPBible Translators Amalgamated Hebrew OT (Scan-Corrected Leningrad)",
        language="hebrew",
        scope="ot_mt",
        repo="STEPBible/STEPBible-Data",
        pinned_sha="5de0a47f35f0fc13dfe1430d104e5db8a4285f9c",
        license_id="CC-BY-4.0",
        redistributable_open=True,
        attribution="STEPBible.org / Tyndale House Cambridge (CC BY 4.0)",
        file_globs=("Translators Amalgamated OT+NT/TAHOT*.txt",),
    ),
    "OSHB_WLC": WitnessCorpusSpec(
        key="OSHB_WLC",
        title="Open Scriptures Hebrew Bible — Westminster Leningrad Codex (WLC)",
        language="hebrew",
        scope="ot_mt",
        repo="openscriptures/morphhb",
        pinned_sha="db6c5c9b46b8f39346f10915ddb1a70dcd429901",
        license_id="Public Domain (WLC text) / CC-BY-4.0 (lemma & morphology)",
        redistributable_open=True,
        attribution="Open Scriptures Hebrew Bible Project (WLC Public Domain / CC BY 4.0)",
        file_globs=("wlc/*.xml",),
    ),
    "OSHB_MAPM": WitnessCorpusSpec(
        key="OSHB_MAPM",
        title="Miqra according to the Mesorah (Aleppo/Tiberian Masoretic Witness)",
        language="hebrew",
        scope="ot_mt",
        repo="openscriptures/morphhb",
        pinned_sha="db6c5c9b46b8f39346f10915ddb1a70dcd429901",
        license_id="CC-BY-SA / OpenScriptures MAPM",
        redistributable_open=True,
        attribution="Miqra according to the Mesorah / Rabbi Kadish / MAM-basics / OSHB",
        file_globs=("MAPM/MAPM.xml",),
    ),
    "LXX_RAHLFS": WitnessCorpusSpec(
        key="LXX_RAHLFS",
        title="Rahlfs 1935 Septuagint Unicode Database (Local Studio Witness)",
        language="greek",
        scope="ot_lxx",
        repo="eliranwong/LXX-Rahlfs-1935",
        pinned_sha="a1b5ff1c739f93cdd18dbab4c9e3fc6b1043141c",
        license_id="CC-BY-NC-SA-4.0 (CATSS derivative)",
        redistributable_open=False,
        attribution="Alfred Rahlfs (1935) / UPenn CATSS / Eliran Wong (CC BY-NC-SA 4.0)",
        file_globs=("11_end-users_files/*LXX_pre-final_2.csv", "01_wordlist_unicode/text_accented.csv", "01_wordlist_unicode/versification_original.csv"),
    ),
    "PROIEL_VULGATE_NT": WitnessCorpusSpec(
        key="PROIEL_VULGATE_NT",
        title="PROIEL Critical Jerome Vulgate New Testament (Local Studio Witness)",
        language="latin",
        scope="nt",
        repo="proiel/proiel-treebank",
        pinned_sha="8e388967a1335ed12335ddc655fe46993ee7d57a",
        license_id="CC-BY-NC-SA-4.0",
        redistributable_open=False,
        attribution="PROIEL Treebank / Marius Jøhndal / Oxford-Stuttgart Critical Vulgate NT",
        file_globs=("latin-nt.xml",),
    ),
}


# ---------------------------------------------------------------------------
# 2. Canon & Book Identifier Mapping (All 70 Books of Saints Working Edition)
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class BookMeta:
    code: str          # Standard 3-char STEPBible/UBS code (e.g., "Gen", "Jhn", "1Ma")
    osis: str          # OSIS code (e.g., "Gen", "John", "1Macc")
    slug: str          # Dotty777 / Studio repo slug (e.g., "genesis", "john", "1-maccabees")
    title: str
    section: str       # "ot_mt" | "ot_deut" | "nt"
    sr_num: Optional[int] = None       # CNTR SR 2-digit book number (40..66)
    morphgnt_prefix: Optional[str] = None  # MorphGNT prefix (61-Mt .. 87-Re)


BOOKS_70: Tuple[BookMeta, ...] = (
    # --- 39 Protocanonical OT Books ---
    BookMeta("Gen", "Gen", "genesis", "Genesis", "ot_mt"),
    BookMeta("Exo", "Exod", "exodus", "Exodus", "ot_mt"),
    BookMeta("Lev", "Lev", "leviticus", "Leviticus", "ot_mt"),
    BookMeta("Num", "Num", "numbers", "Numbers", "ot_mt"),
    BookMeta("Deu", "Deut", "deuteronomy", "Deuteronomy", "ot_mt"),
    BookMeta("Jos", "Josh", "joshua", "Joshua", "ot_mt"),
    BookMeta("Jdg", "Judg", "judges", "Judges", "ot_mt"),
    BookMeta("Rut", "Ruth", "ruth", "Ruth", "ot_mt"),
    BookMeta("1Sa", "1Sam", "1-samuel", "1 Samuel", "ot_mt"),
    BookMeta("2Sa", "2Sam", "2-samuel", "2 Samuel", "ot_mt"),
    BookMeta("1Ki", "1Kgs", "1-kings", "1 Kings", "ot_mt"),
    BookMeta("2Ki", "2Kgs", "2-kings", "2 Kings", "ot_mt"),
    BookMeta("1Ch", "1Chr", "1-chronicles", "1 Chronicles", "ot_mt"),
    BookMeta("2Ch", "2Chr", "2-chronicles", "2 Chronicles", "ot_mt"),
    BookMeta("Ezr", "Ezra", "ezra", "Ezra", "ot_mt"),
    BookMeta("Neh", "Neh", "nehemiah", "Nehemiah", "ot_mt"),
    BookMeta("Est", "Esth", "esther", "Esther", "ot_mt"),
    BookMeta("Job", "Job", "job", "Job", "ot_mt"),
    BookMeta("Psa", "Ps", "psalms", "Psalms", "ot_mt"),
    BookMeta("Pro", "Prov", "proverbs", "Proverbs", "ot_mt"),
    BookMeta("Ecc", "Eccl", "ecclesiastes", "Ecclesiastes", "ot_mt"),
    BookMeta("Sng", "Song", "song-of-solomon", "Song of Solomon", "ot_mt"),
    BookMeta("Isa", "Isa", "isaiah", "Isaiah", "ot_mt"),
    BookMeta("Jer", "Jer", "jeremiah", "Jeremiah", "ot_mt"),
    BookMeta("Lam", "Lam", "lamentations", "Lamentations", "ot_mt"),
    BookMeta("Ezk", "Ezek", "ezekiel", "Ezekiel", "ot_mt"),
    BookMeta("Dan", "Dan", "daniel", "Daniel", "ot_mt"),
    BookMeta("Hos", "Hos", "hosea", "Hosea", "ot_mt"),
    BookMeta("Jol", "Joel", "joel", "Joel", "ot_mt"),
    BookMeta("Amo", "Amos", "amos", "Amos", "ot_mt"),
    BookMeta("Oba", "Obad", "obadiah", "Obadiah", "ot_mt"),
    BookMeta("Jon", "Jonah", "jonah", "Jonah", "ot_mt"),
    BookMeta("Mic", "Mic", "micah", "Micah", "ot_mt"),
    BookMeta("Nam", "Nah", "nahum", "Nahum", "ot_mt"),
    BookMeta("Hab", "Hab", "habakkuk", "Habakkuk", "ot_mt"),
    BookMeta("Zep", "Zeph", "zephaniah", "Zephaniah", "ot_mt"),
    BookMeta("Hag", "Hag", "haggai", "Haggai", "ot_mt"),
    BookMeta("Zec", "Zech", "zechariah", "Zechariah", "ot_mt"),
    BookMeta("Mal", "Mal", "malachi", "Malachi", "ot_mt"),
    # --- 4 Additional OT Books in Saints 70-Book Working Edition ---
    BookMeta("1Ma", "1Macc", "1-maccabees", "1 Maccabees", "ot_deut"),
    BookMeta("2Ma", "2Macc", "2-maccabees", "2 Maccabees", "ot_deut"),
    BookMeta("Wis", "Wis", "wisdom-of-solomon", "Wisdom of Solomon", "ot_deut"),
    BookMeta("Sir", "Sir", "sirach", "Sirach", "ot_deut"),
    # --- 27 New Testament Books ---
    BookMeta("Mat", "Matt", "matthew", "Matthew", "nt", 40, "61-Mt"),
    BookMeta("Mrk", "Mark", "mark", "Mark", "nt", 41, "62-Mk"),
    BookMeta("Luk", "Luke", "luke", "Luke", "nt", 42, "63-Lk"),
    BookMeta("Jhn", "John", "john", "John", "nt", 43, "64-Jn"),
    BookMeta("Act", "Acts", "acts", "Acts", "nt", 44, "65-Ac"),
    BookMeta("Rom", "Rom", "romans", "Romans", "nt", 45, "66-Ro"),
    BookMeta("1Co", "1Cor", "1-corinthians", "1 Corinthians", "nt", 46, "67-1Co"),
    BookMeta("2Co", "2Cor", "2-corinthians", "2 Corinthians", "nt", 47, "68-2Co"),
    BookMeta("Gal", "Gal", "galatians", "Galatians", "nt", 48, "69-Ga"),
    BookMeta("Eph", "Eph", "ephesians", "Ephesians", "nt", 49, "70-Eph"),
    BookMeta("Php", "Phil", "philippians", "Philippians", "nt", 50, "71-Php"),
    BookMeta("Col", "Col", "colossians", "Colossians", "nt", 51, "72-Col"),
    BookMeta("1Th", "1Thess", "1-thessalonians", "1 Thessalonians", "nt", 52, "73-1Th"),
    BookMeta("2Th", "2Thess", "2-thessalonians", "2 Thessalonians", "nt", 53, "74-2Th"),
    BookMeta("1Ti", "1Tim", "1-timothy", "1 Timothy", "nt", 54, "75-1Ti"),
    BookMeta("2Ti", "2Tim", "2-timothy", "2 Timothy", "nt", 55, "76-2Ti"),
    BookMeta("Tit", "Titus", "titus", "Titus", "nt", 56, "77-Tit"),
    BookMeta("Phm", "Phlm", "philemon", "Philemon", "nt", 57, "78-Phm"),
    BookMeta("Heb", "Heb", "hebrews", "Hebrews", "nt", 58, "79-Heb"),
    BookMeta("Jas", "Jas", "james", "James", "nt", 59, "80-Jas"),
    BookMeta("1Pe", "1Pet", "1-peter", "1 Peter", "nt", 60, "81-1Pe"),
    BookMeta("2Pe", "2Pet", "2-peter", "2 Peter", "nt", 61, "82-2Pe"),
    BookMeta("1Jn", "1John", "1-john", "1 John", "nt", 62, "83-1Jn"),
    BookMeta("2Jn", "2John", "2-john", "2 John", "nt", 63, "84-2Jn"),
    BookMeta("3Jn", "3John", "3-john", "3 John", "nt", 64, "85-3Jn"),
    BookMeta("Jud", "Jude", "jude", "Jude", "nt", 65, "86-Jud"),
    BookMeta("Rev", "Rev", "revelation", "Revelation", "nt", 66, "87-Re"),
)

BOOK_BY_CODE: Dict[str, BookMeta] = {b.code: b for b in BOOKS_70}
BOOK_ALIAS_MAP: Dict[str, str] = {}

_EXTRA_BOOK_ALIASES = {
    "song-of-songs": "Sng",
    "canticles": "Sng",
    "wisdom": "Wis",
    "ecclesiasticus": "Sir",
    "ben-sira": "Sir",
    "psalm": "Psa",
    "1macc": "1Ma",
    "2macc": "2Ma",
    "matt": "Mat",
    "mark": "Mrk",
    "luke": "Luk",
    "john": "Jhn",
    "acts": "Act",
    "phil": "Php",
    "phlm": "Phm",
    "1pet": "1Pe",
    "2pet": "2Pe",
    "1john": "1Jn",
    "2john": "2Jn",
    "3john": "3Jn",
    "jude": "Jud",
    "qoheleth": "Ecc",
    # CATSS / Rahlfs LXX abbreviations
    "ge": "Gen", "ex": "Exo", "le": "Lev", "nu": "Num", "de": "Deu",
    "josh": "Jos", "judg": "Jdg", "ru": "Rut",
    "1sam": "1Sa", "2sam": "2Sa", "1reg": "1Sa", "2reg": "2Sa",
    "3reg": "1Ki", "4reg": "2Ki", "1kgs": "1Ki", "2kgs": "2Ki",
    "1chr": "1Ch", "2chr": "2Ch", "1par": "1Ch", "2par": "2Ch",
    "2esdr": "Ezr", "esdrb": "Ezr", "ps": "Psa", "prov": "Pro",
    "eccl": "Ecc", "cant": "Sng", "is": "Isa", "ezek": "Ezk",
    "danog": "Dan", "danth": "Dan", "sap": "Wis", "1mac": "1Ma", "2mac": "2Ma",
}

# MyBible numeric book IDs used in eliranwong/LXX-Rahlfs-1935
MYBIBLE_LXX_BOOK_MAP: Dict[int, str] = {
    10: "Gen", 20: "Exo", 30: "Lev", 40: "Num", 50: "Deu",
    60: "Jos", 70: "Jdg", 80: "Rut", 90: "1Sa", 100: "2Sa", 110: "1Ki", 120: "2Ki",
    130: "1Ch", 140: "2Ch", 150: "Ezr", 160: "Neh", 190: "Est",
    220: "Job", 230: "Psa", 240: "Pro", 250: "Ecc", 260: "Sng", 270: "Wis", 280: "Sir",
    290: "Isa", 300: "Jer", 310: "Lam", 330: "Ezk", 340: "Dan",
    350: "Hos", 360: "Jol", 370: "Amo", 380: "Oba", 390: "Jon", 400: "Mic",
    410: "Nam", 420: "Hab", 430: "Zep", 440: "Hag", 450: "Zec", 460: "Mal",
    462: "1Ma", 464: "2Ma",
}

for _b in BOOKS_70:
    for _k in (
        _b.code,
        _b.osis,
        _b.slug,
        _b.slug.replace("-", ""),
        _b.slug.replace("-", " "),
        _b.title,
    ):
        BOOK_ALIAS_MAP[_k.strip().lower()] = _b.code
    if _b.sr_num is not None:
        BOOK_ALIAS_MAP[str(_b.sr_num)] = _b.code
    if _b.morphgnt_prefix is not None:
        BOOK_ALIAS_MAP[_b.morphgnt_prefix.lower()] = _b.code
        BOOK_ALIAS_MAP[_b.morphgnt_prefix[:2]] = _b.code

for _alias, _target in _EXTRA_BOOK_ALIASES.items():
    BOOK_ALIAS_MAP[_alias.lower()] = _target


def resolve_book_code(raw: str) -> Optional[str]:
    cleaned = raw.strip().lower().replace("_", "-")
    # Strip Studio numeric folder prefixes such as "01-genesis", "09-1-samuel", or "44-matthew"
    cleaned = re.sub(r"^\d{2}-(?=[1-4]?[-a-z])", "", cleaned)
    if cleaned in BOOK_ALIAS_MAP:
        return BOOK_ALIAS_MAP[cleaned]
    compact = re.sub(r"[^a-z0-9]", "", cleaned)
    return BOOK_ALIAS_MAP.get(compact)


# ---------------------------------------------------------------------------
# 3. Versification Spine (LXX/Vulgate <-> MT/English Psalm & Chapter Remapping)
# ---------------------------------------------------------------------------

def lxx_psalm_to_mt(lxx_ch: int, lxx_v: int) -> Optional[Tuple[int, int]]:
    """
    Maps Septuagint / Gallican Vulgate Psalm numbering (used in Saints Greek &
    Latin editions) to Masoretic / standard Hebrew Psalm chapter numbers so
    cross-tradition witnesses align without false chapter shifts.
    """
    if 1 <= lxx_ch <= 8 or 148 <= lxx_ch <= 150:
        return (lxx_ch, lxx_v)
    if lxx_ch == 9:
        if lxx_v <= 21:
            return (9, lxx_v)
        return (10, lxx_v - 21)
    if 10 <= lxx_ch <= 112:
        return (lxx_ch + 1, lxx_v)
    if lxx_ch == 113:
        if lxx_v <= 8:
            return (114, lxx_v)
        return (115, lxx_v - 8)
    if lxx_ch == 114:
        return (116, lxx_v)
    if lxx_ch == 115:
        return (116, lxx_v + 9)
    if 116 <= lxx_ch <= 145:
        return (lxx_ch + 1, lxx_v)
    if lxx_ch == 146:
        return (147, lxx_v)
    if lxx_ch == 147:
        return (147, lxx_v + 11)
    return None  # e.g., Psalm 151 (LXX-only)


# ---------------------------------------------------------------------------
# 4. Language-Specific Philological Normalizers
# ---------------------------------------------------------------------------

class GreekNormalizer:
    """
    Normalizes polytonic Koine Greek across two tiers:
      - orthographic: strips editorial punctuation/brackets/sigla (including
        CNTR '¶'/'˚' and Studio '⟦⟧'), normalizes final grave -> acute (keeping
        breathings, accents, and iota-subscript intact).
      - lexical: strips all combining diacritics, lowercases, normalizes final
        sigma and apostrophes so only genuine word/spelling/order changes trigger.
    """
    _GRAVE_TO_ACUTE = str.maketrans({
        "ὰ": "ά", "ὲ": "έ", "ὴ": "ή", "ὶ": "ί", "ὸ": "ό", "ὺ": "ύ", "ὼ": "ώ",
        "ἂ": "ἄ", "ἒ": "ἔ", "ἢ": "ἤ", "ἲ": "ἴ", "ὂ": "ὄ", "ὓ": "ὕ", "ὢ": "ὤ",
        "ἃ": "ἅ", "ἓ": "ἕ", "ἣ": "ἥ", "ἳ": "ἵ", "ὃ": "ὅ", "ὣ": "ὥ",
        "ᾲ": "ᾴ", "ῂ": "ῄ", "ῲ": "ῴ",
    })
    _PUNCT_RE = re.compile(r"[\.,;:··!\?\(\)\[\]\{\}«»“”‘’\"—–\-⸀⸁⸂⸃⸄⸅¦|¶˚⟦⟧†]")
    _APOS_RE = re.compile(r"[’'ʼʽ᾿᾽′]")

    _ELISION_EQUIV: Dict[str, frozenset[str]] = {}
    for _group in (
        ("αλλα", "αλλ"),
        ("δια", "δι"),
        ("κατα", "κατ", "καθ"),
        ("μετα", "μετ", "μεθ"),
        ("επι", "επ", "εφ"),
        ("υπο", "υπ", "υφ"),
        ("απο", "απ", "αφ"),
        ("αντι", "αντ", "ανθ"),
        ("παρα", "παρ"),
        ("δε", "δ"),
        ("τε", "τ", "θ"),
        ("ου", "ουκ", "ουχ"),
        ("τουτο", "τουτ"),
        ("ταυτα", "ταυτ"),
    ):
        _fset = frozenset(_group)
        for _form in _group:
            _ELISION_EQUIV[_form] = _fset

    @classmethod
    def orthographic_tokens(cls, text: str) -> List[str]:
        s = unicodedata.normalize("NFC", text)
        s = re.sub(r"\{\{overline\|([^}]+)\}\}", r"\1", s)
        s = cls._APOS_RE.sub("ʼ", s)
        s = cls._PUNCT_RE.sub(" ", s)
        tokens = []
        for raw_tok in s.split():
            tok = raw_tok.translate(cls._GRAVE_TO_ACUTE)
            if tok and tok != "ʼ":
                tokens.append(tok)
        return tokens

    @classmethod
    def lexical_tokens(cls, text: str) -> List[str]:
        ortho = cls.orthographic_tokens(text)
        out: List[str] = []
        for tok in ortho:
            nfd = unicodedata.normalize("NFD", tok.lower())
            stripped = "".join(
                ch for ch in nfd
                if unicodedata.category(ch) != "Mn" and ch != "ʼ"
            )
            stripped = stripped.replace("ς", "σ").replace("ϲ", "σ")
            if stripped:
                out.append(stripped)
        return out

    @classmethod
    def is_only_movable_nu_or_elision(cls, a_lex: Sequence[str], b_lex: Sequence[str]) -> bool:
        if len(a_lex) != len(b_lex) or not a_lex:
            return False
        changed = False
        for x, y in zip(a_lex, b_lex):
            if x == y:
                continue
            if x + "ν" == y or y + "ν" == x:
                changed = True
                continue
            eq = cls._ELISION_EQUIV.get(x)
            if eq and y in eq:
                changed = True
                continue
            return False
        return changed


class HebrewNormalizer:
    """
    Normalizes Biblical Hebrew & Aramaic WITHOUT applying standard Unicode NFC
    (per Open Scriptures OSHB & SBL Hebrew Manual warnings).

    Canonical combining mark order per Hebrew base consonant:
      1. Shin/Sin dot (U+05C1, U+05C2)
      2. Dagesh / Mapiq (U+05BC)
      3. Rafe (U+05BF)
      4. Vowel points (U+05B0..U+05BB, U+05C7)
      5. Meteg / Silluq (U+05BD)
      6. Cantillation accents (U+0591..U+05AF)
    """
    _CONSONANT_SET = frozenset(chr(c) for c in range(0x05D0, 0x05EB))
    _CANTILLATION = frozenset(chr(c) for c in range(0x0591, 0x05B0))
    _VOWELS = frozenset(
        [chr(c) for c in range(0x05B0, 0x05BC)] + ["\u05C7"]
    )
    _EDITORIAL_RE = re.compile(r"[\*\[\]\{\}׃׀׆]")
    # Parenthesized Ketiv annotations in MAM / Studio Hebrew: "(לודיים)" or "(הוצא)"
    _PAREN_KETIV_RE = re.compile(r"\(([^)]+)\)")

    @classmethod
    def _mark_rank(cls, ch: str) -> int:
        code = ord(ch)
        if code in (0x05C1, 0x05C2):
            return 1  # shin / sin dot
        if code == 0x05BC:
            return 2  # dagesh / mapiq
        if code == 0x05BF:
            return 3  # rafe
        if ch in cls._VOWELS:
            return 4  # nikud vowels
        if code == 0x05BD:
            return 5  # meteg
        if ch in cls._CANTILLATION:
            return 6  # te'amim
        return 7

    @classmethod
    def canonicalize_hebrew(cls, text: str) -> str:
        expanded: List[str] = []
        for ch in text:
            if 0xFB1D <= ord(ch) <= 0xFB4F:
                expanded.append(unicodedata.normalize("NFD", ch))
            else:
                expanded.append(ch)
        raw = "".join(expanded)

        result: List[str] = []
        marks_buf: List[str] = []
        for ch in raw:
            if unicodedata.category(ch) == "Mn":
                marks_buf.append(ch)
            else:
                if marks_buf:
                    marks_buf.sort(key=cls._mark_rank)
                    result.extend(marks_buf)
                    marks_buf.clear()
                result.append(ch)
        if marks_buf:
            marks_buf.sort(key=cls._mark_rank)
            result.extend(marks_buf)
        return "".join(result)

    @classmethod
    def strip_parenthesized_ketiv(cls, text: str) -> str:
        """Removes inline parenthesized Ketiv notes '(...)' so Qere words are not doubled."""
        return cls._PAREN_KETIV_RE.sub(" ", text)

    @classmethod
    def substitute_parenthesized_ketiv(cls, text: str) -> Optional[str]:
        """Replaces adjacent '(ketiv) qere' or 'qere (ketiv)' pairs with the Ketiv reading."""
        if "(" not in text:
            return None
        # MAM prints either '(ketiv) qere' (Gen 8:17) or 'qere (ketiv)' (1 Chr 1:11)
        # Distinguish Ketiv (unpointed consonants inside parens) from pointed Qere neighbour
        s = re.sub(r"\(([^)]+)\)\s+\S+", lambda m: m.group(1).replace("_", " "), text)
        if s == text:
            s = re.sub(r"\S+\s+\(([^)]+)\)", lambda m: m.group(1).replace("_", " "), text)
        return s

    @classmethod
    def _clean_words(cls, text: str) -> List[str]:
        s = cls.canonicalize_hebrew(cls.strip_parenthesized_ketiv(text))
        s = re.sub(r"\{[פס]\}", " ", s)
        s = s.replace("/", "").replace("\u05BE", " ").replace("_", " ")
        s = cls._EDITORIAL_RE.sub(" ", s)
        s = s.replace("(", " ").replace(")", " ")
        words = []
        for w in s.split():
            if w in ("פ", "ס"):
                continue
            words.append(w)
        return words

    @classmethod
    def consonantal_tokens(cls, text: str) -> List[str]:
        tokens: List[str] = []
        for w in cls._clean_words(text):
            cons = "".join(ch for ch in w if ch in cls._CONSONANT_SET)
            if cons:
                tokens.append(cons)
        return tokens

    @classmethod
    def vocalized_tokens(cls, text: str, fold_qamets_qatan: bool = True) -> List[str]:
        """Preserves consonants, shin/sin dot, dagesh, and vowels; strips cantillation & meteg."""
        tokens: List[str] = []
        for w in cls._clean_words(text):
            voc = "".join(
                ch for ch in w
                if (
                    ch in cls._CONSONANT_SET
                    or ord(ch) in (0x05C1, 0x05C2, 0x05BC)
                    or ch in cls._VOWELS
                )
            )
            if fold_qamets_qatan:
                voc = voc.replace("\u05C7", "\u05B8")
            if voc:
                tokens.append(voc)
        return tokens


class LatinNormalizer:
    """
    Normalizes Latin biblical witnesses across two tiers:
      - orthographic: strips punctuation and editorial brackets, preserves
        u/v, i/j, ae/oe spelling conventions.
      - lexical: lowercases, expands ligatures (æ->ae, œ->oe), normalizes
        ramist letters (j->i, v->u), and strips macrons/accents.
    """
    _PUNCT_RE = re.compile(r"[\.,;:!\?\(\)\[\]\{\}«»“”‘’\"—–\-¦⟦⟧]")

    @classmethod
    def orthographic_tokens(cls, text: str) -> List[str]:
        s = unicodedata.normalize("NFC", text)
        s = cls._PUNCT_RE.sub(" ", s)
        return [tok for tok in s.split() if tok]

    @classmethod
    def lexical_tokens(cls, text: str) -> List[str]:
        out: List[str] = []
        for tok in cls.orthographic_tokens(text):
            low = tok.lower().replace("æ", "ae").replace("œ", "oe")
            nfd = unicodedata.normalize("NFD", low)
            base = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
            base = base.replace("j", "i").replace("v", "u")
            if base:
                out.append(base)
        return out


# ---------------------------------------------------------------------------
# 5. Upstream Critical Corpus Parsers
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class WitnessVerse:
    corpus_key: str
    book: str
    chapter: int
    verse: int
    text: str
    ketiv_text: Optional[str] = None
    qere_text: Optional[str] = None
    edition_tags: Optional[Dict[str, str]] = None


def parse_srgnt_text(content: str) -> Dict[Tuple[str, int, int], WitnessVerse]:
    verses: Dict[Tuple[str, int, int], WitnessVerse] = {}
    bbcccvvv_re = re.compile(r"^(\d{2})(\d{3})(\d{3})[\t ]+(.+)$")
    ref_re = re.compile(r"^([1-3]?[A-Za-z]+)[\. ]+(\d+):(\d+)[\t ]+(.+)$")

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        m = bbcccvvv_re.match(line)
        if m:
            b_num, ch_s, v_s, gk = m.groups()
            b_code = resolve_book_code(str(int(b_num)))
            if b_code:
                ch, v = int(ch_s), int(v_s)
                verses[(b_code, ch, v)] = WitnessVerse("SRGNT", b_code, ch, v, gk.strip())
            continue
        m2 = ref_re.match(line)
        if m2:
            b_raw, ch_s, v_s, gk = m2.groups()
            b_code = resolve_book_code(b_raw)
            if b_code:
                ch, v = int(ch_s), int(v_s)
                verses[(b_code, ch, v)] = WitnessVerse("SRGNT", b_code, ch, v, gk.strip())
    return verses


def parse_morphgnt_sblgnt(content: str, fallback_book: Optional[str] = None) -> Dict[Tuple[str, int, int], WitnessVerse]:
    nt_books = [b.code for b in BOOKS_70 if b.section == "nt"]
    words_by_ref: Dict[Tuple[str, int, int], List[str]] = defaultdict(list)

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 4 or len(parts[0]) != 6 or not parts[0].isdigit():
            continue
        bcv = parts[0]
        b_idx = int(bcv[:2]) - 1
        ch = int(bcv[2:4])
        v = int(bcv[4:6])
        b_code = nt_books[b_idx] if 0 <= b_idx < len(nt_books) else fallback_book
        if not b_code:
            continue
        words_by_ref[(b_code, ch, v)].append(parts[3])

    return {
        ref: WitnessVerse("SBLGNT", ref[0], ref[1], ref[2], " ".join(toks))
        for ref, toks in words_by_ref.items()
    }


def parse_stepbible_tagnt(content: str) -> Dict[Tuple[str, int, int], WitnessVerse]:
    tracked_editions = ("NA28", "Tyn", "SBL", "WH", "Treg", "Byz", "TR")
    ed_words: Dict[Tuple[str, int, int], Dict[str, List[str]]] = defaultdict(
        lambda: {ed: [] for ed in tracked_editions}
    )
    default_words: Dict[Tuple[str, int, int], List[str]] = defaultdict(list)

    ref_re = re.compile(r"^(?:\d+_)?([1-3]?[A-Za-z]+)\.(\d+)\.(\d+)(?:#\d+)?(?:=([A-Za-z\(\)]+))?$")

    for raw_line in content.splitlines():
        if not raw_line or raw_line.startswith("#") or raw_line.startswith("$"):
            continue
        cols = raw_line.split("\t")
        if len(cols) < 2:
            continue
        ref_cell = cols[0].strip()
        m = ref_re.match(ref_cell)
        if not m:
            continue
        b_raw, ch_s, v_s, marker = m.groups()
        b_code = resolve_book_code(b_raw)
        if not b_code:
            continue
        ch, v = int(ch_s), int(v_s)

        gk_cell = re.sub(r"\s*\([^)]*\)\s*", "", cols[1]).strip()
        if not gk_cell:
            continue

        joined_tail = "\t".join(cols[2:])
        present_eds = [ed for ed in tracked_editions if ed in joined_tail]

        if present_eds:
            for ed in present_eds:
                ed_words[(b_code, ch, v)][ed].append(gk_cell)
            if "NA28" in present_eds or "Tyn" in present_eds:
                default_words[(b_code, ch, v)].append(gk_cell)
        else:
            tag = (marker or "NKO").upper()
            if "N" in tag:
                default_words[(b_code, ch, v)].append(gk_cell)
                for ed in ("NA28", "Tyn", "SBL", "WH", "Treg"):
                    ed_words[(b_code, ch, v)][ed].append(gk_cell)
            if "K" in tag:
                for ed in ("Byz", "TR"):
                    ed_words[(b_code, ch, v)][ed].append(gk_cell)

    out: Dict[Tuple[str, int, int], WitnessVerse] = {}
    all_refs = set(default_words.keys()) | set(ed_words.keys())
    for ref in all_refs:
        ed_map = {
            ed: " ".join(wlist)
            for ed, wlist in ed_words[ref].items()
            if wlist
        }
        primary = ed_map.get("NA28") or ed_map.get("Tyn") or " ".join(default_words[ref])
        if primary:
            out[ref] = WitnessVerse(
                corpus_key="TAGNT",
                book=ref[0],
                chapter=ref[1],
                verse=ref[2],
                text=primary,
                edition_tags=ed_map,
            )
    return out


def parse_stepbible_tahot(content: str) -> Dict[Tuple[str, int, int], WitnessVerse]:
    ketiv_words: Dict[Tuple[str, int, int], List[str]] = defaultdict(list)
    qere_words: Dict[Tuple[str, int, int], List[str]] = defaultdict(list)
    ref_re = re.compile(r"^(?:\d+_)?([1-3]?[A-Za-z]+)\.(\d+)\.(\d+)(?:\([^)]*\))?(?:#\d+)?(?:=([A-Za-z]+))?$")

    for raw_line in content.splitlines():
        if not raw_line or raw_line.startswith("#") or raw_line.startswith("$"):
            continue
        cols = raw_line.split("\t")
        if len(cols) < 2:
            continue
        m = ref_re.match(cols[0].strip())
        if not m:
            continue
        b_raw, ch_s, v_s, marker = m.groups()
        tag = (marker or "L").upper()
        if "R" in tag and "L" not in tag:
            continue
        b_code = resolve_book_code(b_raw)
        if not b_code:
            continue
        ch, v = int(ch_s), int(v_s)
        heb_word = cols[1].strip().replace("/", "").replace("\\", "")
        if not heb_word:
            continue
        if "Q" in tag and "K" not in tag and "L" not in tag:
            qere_words[(b_code, ch, v)].append(heb_word)
        elif "K" in tag and "Q" not in tag:
            ketiv_words[(b_code, ch, v)].append(heb_word)
        else:
            ketiv_words[(b_code, ch, v)].append(heb_word)
            qere_words[(b_code, ch, v)].append(heb_word)

    out: Dict[Tuple[str, int, int], WitnessVerse] = {}
    for ref in set(ketiv_words.keys()) | set(qere_words.keys()):
        k_txt = " ".join(ketiv_words[ref])
        q_txt = " ".join(qere_words[ref])
        out[ref] = WitnessVerse(
            corpus_key="TAHOT",
            book=ref[0],
            chapter=ref[1],
            verse=ref[2],
            text=k_txt or q_txt,
            ketiv_text=k_txt if k_txt != q_txt else None,
            qere_text=q_txt if k_txt != q_txt else None,
        )
    return out


def parse_oshb_osis_xml(xml_text: str, corpus_key: str = "OSHB_WLC") -> Dict[Tuple[str, int, int], WitnessVerse]:
    """
    Parses Open Scriptures OSIS XML files:
      - Container `<verse osisID="...">...</verse>` (used in `wlc/*.xml`)
      - Milestone `<verse osisID="..." sID="..."/>...<verse eID="..."/>` (used in `MAPM/MAPM.xml`)
    Extracts both diplomatic Ketiv and Masoretic Qere readings per verse.
    """
    out: Dict[Tuple[str, int, int], WitnessVerse] = {}

    # 1. Check for milestone <verse osisID="..." sID="..."/> ... <verse eID="..."/> (MAPM.xml)
    if 'sID="' in xml_text and "<verse" in xml_text:
        milestone_pat = re.compile(
            r'<verse[^>]*\bosisID="([1-3]?[A-Za-z]+)\.(\d+)\.(\d+)"[^>]*/>(.*?)<verse[^>]*\beID="\1\.\2\.\3"\s*/>',
            re.DOTALL,
        )
        for m in milestone_pat.finditer(xml_text):
            b_code = resolve_book_code(m.group(1))
            if not b_code:
                continue
            ch, v = int(m.group(2)), int(m.group(3))
            body = re.sub(r"<note\b.*?</note>", "", m.group(4), flags=re.DOTALL).replace("♫", " ")
            body = re.sub(r'</?seg type="x-(?:big|small|suspended|large|reversednun|symbol|space)"[^>]*>', "", body)

            q_xml = re.sub(r'<seg type="x-ketiv">.*?</seg>', " ", body, flags=re.DOTALL)
            q_xml = re.sub(r"</?seg\b[^>]*>", "", q_xml)
            q_txt = " ".join(re.sub(r"<[^>]+>", " ", q_xml).split())

            k_xml = re.sub(r'<seg type="x-qere">.*?</seg>', " ", body, flags=re.DOTALL)
            k_xml = re.sub(r"</?seg\b[^>]*>", "", k_xml)
            k_txt = " ".join(re.sub(r"<[^>]+>", " ", k_xml).split())

            if q_txt or k_txt:
                primary = q_txt if corpus_key == "OSHB_MAPM" else (k_txt or q_txt)
                out[(b_code, ch, v)] = WitnessVerse(
                    corpus_key=corpus_key,
                    book=b_code,
                    chapter=ch,
                    verse=v,
                    text=primary,
                    ketiv_text=k_txt if k_txt != q_txt else None,
                    qere_text=q_txt if k_txt != q_txt else None,
                )
        if out:
            return out

    # 2. Container <verse osisID="...">...</verse> (wlc/*.xml)
    root = ET.fromstring(xml_text)

    def local_tag(elem: ET.Element) -> str:
        return elem.tag.split("}", 1)[-1] if "}" in elem.tag else elem.tag

    for verse_el in root.iter():
        if local_tag(verse_el) != "verse":
            continue
        osis_id = verse_el.attrib.get("osisID", "")
        if not osis_id:
            continue
        parts = osis_id.split(".")
        if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
            continue
        b_code = resolve_book_code(parts[0])
        if not b_code:
            continue
        ch, v = int(parts[1]), int(parts[2])

        k_tokens: List[str] = []
        q_tokens: List[str] = []

        for child in verse_el:
            ctag = local_tag(child)
            if ctag == "w":
                w_txt = (child.text or "").replace("/", "").strip()
                if w_txt:
                    k_tokens.append(w_txt)
                    q_tokens.append(w_txt)
            elif ctag == "seg":
                seg_type = child.attrib.get("type", "")
                seg_txt = "".join(child.itertext()).replace("/", "").strip()
                if seg_type == "x-maqqef":
                    if k_tokens:
                        k_tokens[-1] += "\u05BE"
                    if q_tokens:
                        q_tokens[-1] += "\u05BE"
                elif seg_type in ("x-ketiv", "ketiv"):
                    if seg_txt:
                        k_tokens.append(seg_txt)
                elif seg_type in ("x-qere", "qere"):
                    if seg_txt:
                        q_tokens.append(seg_txt)
            elif ctag == "rdg":
                rdg_type = child.attrib.get("type", "")
                rdg_txt = "".join(child.itertext()).replace("/", "").strip()
                if "ketiv" in rdg_type and rdg_txt:
                    k_tokens.append(rdg_txt)
                elif "qere" in rdg_type and rdg_txt:
                    q_tokens.append(rdg_txt)
            elif ctag in ("catchWord", "note"):
                for sub in child.iter():
                    if local_tag(sub) == "rdg":
                        sub_txt = "".join(sub.itertext()).replace("/", "").strip()
                        if sub_txt:
                            q_tokens.append(sub_txt)

        k_joined = re.sub(r"\u05BE\s+", "\u05BE", " ".join(k_tokens)).strip()
        q_joined = re.sub(r"\u05BE\s+", "\u05BE", " ".join(q_tokens)).strip()
        if k_joined or q_joined:
            out[(b_code, ch, v)] = WitnessVerse(
                corpus_key=corpus_key,
                book=b_code,
                chapter=ch,
                verse=v,
                text=k_joined or q_joined,
                ketiv_text=k_joined if k_joined != q_joined else None,
                qere_text=q_joined if k_joined != q_joined else None,
            )
    return out


def parse_proiel_latin_xml(xml_text: str) -> Dict[Tuple[str, int, int], WitnessVerse]:
    words_by_ref: Dict[Tuple[str, int, int], List[str]] = defaultdict(list)
    root = ET.fromstring(xml_text)
    cit_re = re.compile(r"^([1-3]?\s*[A-Za-z]+)\s+(\d+)\.(\d+)$")

    for tok_el in root.iter("token"):
        form = tok_el.attrib.get("form")
        cit = tok_el.attrib.get("citation-part", "").strip()
        if not form or not cit:
            continue
        m = cit_re.match(cit)
        if not m:
            continue
        b_raw, ch_s, v_s = m.groups()
        b_code = resolve_book_code(b_raw.replace(" ", ""))
        if not b_code:
            continue
        after = tok_el.attrib.get("presentation-after", " ")
        punct = "" if after.isspace() else after.strip()
        words_by_ref[(b_code, int(ch_s), int(v_s))].append(form + punct)

    return {
        ref: WitnessVerse("PROIEL_VULGATE_NT", ref[0], ref[1], ref[2], " ".join(w))
        for ref, w in words_by_ref.items()
    }


def parse_lxx_rahlfs_wordlist(content: str) -> Dict[Tuple[str, int, int], WitnessVerse]:
    """
    Parses Rahlfs 1935 Septuagint files from eliranwong/LXX-Rahlfs-1935:
      1. MyBible tagged verse rows (`†10.1.1\tἐν<S>...</S><m>...</m> ἀρχῇ...`)
      2. Plain verse-per-line (`Gen 1:1 ἐν ἀρχῇ...`) or token-per-line TSV.
    """
    words_by_ref: Dict[Tuple[str, int, int], List[str]] = defaultdict(list)
    mybible_re = re.compile(r"^†?(\d+)\.(\d+)\.(\d+)\t(.+)$")
    tag_strip_re = re.compile(r"<(?:S|m)>[^<]*</(?:S|m)>|<[^>]+>")
    verse_line_re = re.compile(r"^([1-4]?[A-Za-z]+)[\. ]+(\d+):(\d+)[\t ]+(.+)$")
    bcv_col_re = re.compile(r"^([1-4]?[A-Za-z]+)[\. /]+(\d+)[:\. ]+(\d+)$")

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        m_mb = mybible_re.match(line)
        if m_mb:
            b_num, ch_s, v_s, raw_gk = m_mb.groups()
            b_code = MYBIBLE_LXX_BOOK_MAP.get(int(b_num))
            if b_code:
                cleaned = " ".join(tag_strip_re.sub("", raw_gk).split())
                if cleaned:
                    words_by_ref[(b_code, int(ch_s), int(v_s))].append(cleaned)
            continue

        cols = line.split("\t")
        if len(cols) >= 4:
            if cols[1].isdigit() and cols[2].isdigit() and not cols[0].isdigit():
                b_code = resolve_book_code(cols[0])
                if b_code:
                    words_by_ref[(b_code, int(cols[1]), int(cols[2]))].append(cols[3].strip())
                    continue
            m_bcv = bcv_col_re.match(cols[0]) or (len(cols) > 1 and bcv_col_re.match(cols[1]))
            if m_bcv:
                b_code = resolve_book_code(m_bcv.group(1))
                if b_code:
                    gk_tok = cols[-1].strip()
                    words_by_ref[(b_code, int(m_bcv.group(2)), int(m_bcv.group(3)))].append(gk_tok)
                    continue

        m_vl = verse_line_re.match(line)
        if m_vl:
            b_code = resolve_book_code(m_vl.group(1))
            if b_code:
                words_by_ref[(b_code, int(m_vl.group(2)), int(m_vl.group(3)))].append(m_vl.group(4).strip())

    return {
        ref: WitnessVerse("LXX_RAHLFS", ref[0], ref[1], ref[2], " ".join(w))
        for ref, w in words_by_ref.items()
    }


# ---------------------------------------------------------------------------
# 6. Adaptive Loader for Local Saints Studio & Translation Repositories
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class SaintsLocalVerse:
    language: str   # "greek" | "hebrew" | "latin"
    book: str
    chapter: int
    verse: int
    source_text: str
    english_text: Optional[str] = None
    card_id: Optional[str] = None
    origin_file: Optional[str] = None


class _SimpleParallelHTMLParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._current_id: Optional[str] = None
        self._buf: List[str] = []
        self.blocks: List[Tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attr_dict = dict(attrs)
        el_id = attr_dict.get("id") or attr_dict.get("data-verse") or ""
        if re.search(r"(?:^|[-_])v?\d+[-_.:]\d+$", el_id):
            if self._current_id and self._buf:
                self.blocks.append((self._current_id, " ".join("".join(self._buf).split())))
            self._current_id = el_id
            self._buf = []

    def handle_data(self, data: str) -> None:
        if self._current_id is not None:
            self._buf.append(data)

    def close(self) -> None:
        super().close()
        if self._current_id and self._buf:
            self.blocks.append((self._current_id, " ".join("".join(self._buf).split())))


class SaintsRepoLoader:
    """
    Loads local verses from BOTH:
      1. Studio 7-Division Critical Text editions (`Saints-*-Critical-Text/<Division>/<Book>/*_Critical_Text.json`)
      2. Standalone Translation repositories (`<repo>/<book-slug>/verses.json`, `*.json`, `*.txt`, `*.html`)
    """

    SOURCE_KEY_CANDIDATES: Dict[str, Tuple[str, ...]] = {
        "greek": ("critical_text", "greek", "greek_text", "grc", "lxx", "gnt", "source", "source_text", "original"),
        "hebrew": ("critical_text", "hebrew", "hebrew_text", "heb", "masoretic", "mt", "wlc", "source", "source_text", "original"),
        "latin": ("critical_text", "latin", "latin_text", "lat", "vulgate", "vulg", "source", "source_text", "original"),
    }
    ENGLISH_KEY_CANDIDATES = ("english", "saints_english", "translation", "rendering", "target", "eng")

    _SKIP_DIRS = frozenset({
        "audit", "corrections", "staging-backups", "scripts", "witness-cache",
        "greek-base", "hebrew-base", "latin-base", "Latin", "saints-latin-column",
    })
    _STUDIO_DIVISION_RE = re.compile(r"^0[1-7]_[A-Za-z_]+$")

    @classmethod
    def load_repository(
        cls,
        repo_path: Path,
        language: str,
        book_filter: Optional[set[str]] = None,
    ) -> Dict[Tuple[str, int, int], SaintsLocalVerse]:
        results: Dict[Tuple[str, int, int], SaintsLocalVerse] = {}
        if not repo_path.exists():
            return results

        # Layout A: Studio 7-division folders (01_Law .. 07_Glory)
        division_dirs = [
            d for d in sorted(repo_path.iterdir())
            if d.is_dir() and cls._STUDIO_DIVISION_RE.match(d.name) and "_Tier" not in d.name
        ]
        if division_dirs:
            for div_dir in division_dirs:
                for book_dir in sorted(div_dir.iterdir()):
                    if not book_dir.is_dir():
                        continue
                    b_code = resolve_book_code(book_dir.name)
                    if not b_code:
                        continue
                    if book_filter and b_code not in book_filter:
                        continue
                    for jf in sorted(book_dir.glob("*_Critical_Text.json")):
                        cls._parse_studio_critical_json(jf, language, b_code, results)
            if results:
                return results

        # Layout B: Top-level book folders (<repo>/<book-slug>/verses.json | *.json | *.txt | *.html)
        for child in sorted(repo_path.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            if child.name in cls._SKIP_DIRS or "_Tier" in child.name:
                continue
            b_code = resolve_book_code(child.name)
            if not b_code:
                continue
            if book_filter and b_code not in book_filter:
                continue

            verses_json = child / "verses.json"
            if verses_json.is_file():
                cls._parse_json_file(verses_json, language, b_code, results)
                continue

            loaded_for_book = False
            for jf in sorted(child.glob("*.json")):
                cls._parse_json_file(jf, language, b_code, results)
                loaded_for_book = True
            if not loaded_for_book:
                for tf in sorted(child.glob("*.txt")):
                    cls._parse_txt_file(tf, language, b_code, results)
                    loaded_for_book = True
            if not loaded_for_book:
                for hf in sorted(child.glob("**/*.html")):
                    cls._parse_html_file(hf, language, b_code, results)

        return results

    @classmethod
    def _parse_studio_critical_json(
        cls,
        path: Path,
        language: str,
        fallback_book: str,
        dest: Dict[Tuple[str, int, int], SaintsLocalVerse],
    ) -> None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        b_code = resolve_book_code(str(payload.get("book_slug") or "")) or fallback_book
        ch = payload.get("chapter")
        if not isinstance(ch, int):
            return
        for vr in payload.get("verses", []):
            v = vr.get("verse")
            txt = (vr.get("critical_text") or "").strip()
            if isinstance(v, int) and txt:
                dest[(b_code, ch, v)] = SaintsLocalVerse(
                    language=language,
                    book=b_code,
                    chapter=ch,
                    verse=v,
                    source_text=txt,
                    origin_file=str(path),
                )

    @classmethod
    def _extract_source_and_english(cls, record: Dict[str, Any], language: str) -> Tuple[Optional[str], Optional[str]]:
        src_val: Optional[str] = None
        eng_val: Optional[str] = None
        lower_map = {k.lower(): v for k, v in record.items()}

        for cand in cls.SOURCE_KEY_CANDIDATES[language]:
            val = lower_map.get(cand)
            if isinstance(val, str) and val.strip():
                src_val = val.strip()
                break

        for cand in cls.ENGLISH_KEY_CANDIDATES:
            val = lower_map.get(cand)
            if isinstance(val, str) and val.strip():
                eng_val = val.strip()
                break

        return src_val, eng_val

    @classmethod
    def _parse_ref_from_record(
        cls,
        record: Dict[str, Any],
        default_book: str,
        fallback_chapter: Optional[int] = None,
    ) -> Optional[Tuple[str, int, int]]:
        ch = record.get("chapter") if record.get("chapter") is not None else (
            record.get("ch") if record.get("ch") is not None else fallback_chapter
        )
        v = record.get("verse") if record.get("verse") is not None else (
            record.get("v") if record.get("v") is not None else record.get("verse_number")
        )
        if isinstance(ch, (int, str)) and isinstance(v, (int, str)):
            try:
                return (default_book, int(str(ch).split(":")[0]), int(str(v).split("-")[0]))
            except ValueError:
                pass

        for ref_key in ("ref", "reference", "id", "card_id", "masoretic_ref", "bcv"):
            raw = record.get(ref_key)
            if isinstance(raw, str):
                m = re.search(r"(?:([1-4]?[A-Za-z\-]+)[\. _]+)?(\d+)[:\._\-](\d+)", raw)
                if m:
                    b_part, ch_s, v_s = m.groups()
                    b_code = resolve_book_code(b_part) if b_part else default_book
                    return (b_code or default_book, int(ch_s), int(v_s))
        return None

    @classmethod
    def _parse_json_file(
        cls,
        path: Path,
        language: str,
        book_code: str,
        dest: Dict[Tuple[str, int, int], SaintsLocalVerse],
    ) -> None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        def visit(node: Any, ch_hint: Optional[int] = None) -> None:
            if isinstance(node, list):
                for item in node:
                    visit(item, ch_hint)
            elif isinstance(node, dict):
                src, eng = cls._extract_source_and_english(node, language)
                if src:
                    ref = cls._parse_ref_from_record(node, book_code, ch_hint)
                    if ref:
                        dest[ref] = SaintsLocalVerse(
                            language=language,
                            book=ref[0],
                            chapter=ref[1],
                            verse=ref[2],
                            source_text=src,
                            english_text=eng,
                            card_id=str(node.get("id") or node.get("card_id") or ""),
                            origin_file=str(path),
                        )
                        return
                ch_from_obj = node.get("chapter") if isinstance(node.get("chapter"), int) else ch_hint
                for k, val in node.items():
                    next_ch = int(k) if str(k).isdigit() else ch_from_obj
                    if isinstance(val, dict) and re.match(r"^\d+[:\.]\d+$", str(k)):
                        ch_s, v_s = re.split(r"[:\.]", str(k), maxsplit=1)
                        v_src, v_eng = cls._extract_source_and_english(val, language)
                        if v_src:
                            ref = (book_code, int(ch_s), int(v_s))
                            dest[ref] = SaintsLocalVerse(
                                language=language,
                                book=book_code,
                                chapter=ref[1],
                                verse=ref[2],
                                source_text=v_src,
                                english_text=v_eng,
                                origin_file=str(path),
                            )
                            continue
                    if isinstance(val, (list, dict)):
                        visit(val, next_ch)

        visit(data)

    @classmethod
    def _parse_txt_file(
        cls,
        path: Path,
        language: str,
        book_code: str,
        dest: Dict[Tuple[str, int, int], SaintsLocalVerse],
    ) -> None:
        ch_match = re.search(r"(\d+)", path.stem)
        current_ch = int(ch_match.group(1)) if ch_match else 1
        ch_hdr_re = re.compile(r"^(?:chapter|psalm)\s+(\d+)\b", re.IGNORECASE)
        cv_re = re.compile(r"^(\d+):(\d+)[\t \.\-]+(.+)$")
        v_only_re = re.compile(r"^(\d+)[\t \.\-]+(.+)$")

        for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            mh = ch_hdr_re.match(line)
            if mh:
                current_ch = int(mh.group(1))
                continue
            m_cv = cv_re.match(line)
            if m_cv:
                ch, v, rest = int(m_cv.group(1)), int(m_cv.group(2)), m_cv.group(3)
            else:
                m_v = v_only_re.match(line)
                if not m_v:
                    continue
                ch, v, rest = current_ch, int(m_v.group(1)), m_v.group(2)

            parts = re.split(r"\t|\s+\|\s+", rest, maxsplit=1)
            candidate_src = parts[0].strip()
            candidate_eng = parts[1].strip() if len(parts) > 1 else None
            if cls._looks_like_language(candidate_src, language):
                dest[(book_code, ch, v)] = SaintsLocalVerse(
                    language=language,
                    book=book_code,
                    chapter=ch,
                    verse=v,
                    source_text=candidate_src,
                    english_text=candidate_eng,
                    origin_file=str(path),
                )

    @classmethod
    def _parse_html_file(
        cls,
        path: Path,
        language: str,
        book_code: str,
        dest: Dict[Tuple[str, int, int], SaintsLocalVerse],
    ) -> None:
        parser = _SimpleParallelHTMLParser()
        parser.feed(path.read_text(encoding="utf-8", errors="replace"))
        parser.close()
        for el_id, text in parser.blocks:
            m = re.search(r"(\d+)[-_.:](\d+)$", el_id)
            if not m:
                continue
            ch, v = int(m.group(1)), int(m.group(2))
            if cls._looks_like_language(text, language) and (book_code, ch, v) not in dest:
                dest[(book_code, ch, v)] = SaintsLocalVerse(
                    language=language,
                    book=book_code,
                    chapter=ch,
                    verse=v,
                    source_text=text,
                    card_id=el_id,
                    origin_file=str(path),
                )

    @staticmethod
    def _looks_like_language(text: str, language: str) -> bool:
        if language == "greek":
            return any(0x0370 <= ord(c) <= 0x03FF or 0x1F00 <= ord(c) <= 0x1FFF for c in text)
        if language == "hebrew":
            return any(0x0590 <= ord(c) <= 0x05FF or 0xFB1D <= ord(c) <= 0xFB4F for c in text)
        if language == "latin":
            return bool(re.search(r"[A-Za-z]", text))
        return False


# ---------------------------------------------------------------------------
# 7. Pinned GitHub Fetcher & SHA-256 Lockfile Manager
# ---------------------------------------------------------------------------

class WitnessCacheManager:
    def __init__(self, cache_root: Path, include_nc_local: bool = False) -> None:
        self.cache_root = cache_root
        self.open_dir = cache_root / "open-cc-by"
        self.nc_dir = cache_root / ".local-nc-only"
        self.lock_path = cache_root / "witness_lock.json"
        self.include_nc_local = include_nc_local

    def ensure_dirs_and_gitignore(self) -> None:
        self.open_dir.mkdir(parents=True, exist_ok=True)
        if self.include_nc_local:
            self.nc_dir.mkdir(parents=True, exist_ok=True)
            gitignore = self.cache_root / ".gitignore"
            guard_line = ".local-nc-only/\n"
            if not gitignore.exists() or guard_line not in gitignore.read_text(encoding="utf-8"):
                with gitignore.open("a", encoding="utf-8") as fh:
                    fh.write(
                        "# Guard: Do not commit CC BY-NC-SA corpora to public repos\n"
                        + guard_line
                    )

    @staticmethod
    def _sha256_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _glob_matches(rel_path: str, pattern: str) -> bool:
        from fnmatch import fnmatchcase
        return fnmatchcase(rel_path, pattern)

    def fetch_corpora(self, keys: Iterable[str], force_refresh: bool = False) -> Dict[str, List[Path]]:
        self.ensure_dirs_and_gitignore()
        lock_data: Dict[str, Any] = {}
        if self.lock_path.exists():
            try:
                lock_data = json.loads(self.lock_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                lock_data = {}
        lock_files = lock_data.setdefault("files", {})

        fetched_paths: Dict[str, List[Path]] = defaultdict(list)
        tree_cache: Dict[Tuple[str, str], List[str]] = {}

        for key in keys:
            spec = UPSTREAM_CORPORA[key]
            if not spec.redistributable_open and not self.include_nc_local:
                continue

            target_base = (self.open_dir if spec.redistributable_open else self.nc_dir) / key
            target_base.mkdir(parents=True, exist_ok=True)

            repo_key = (spec.repo, spec.pinned_sha)
            if repo_key not in tree_cache:
                tree_cache[repo_key] = self._list_repo_tree(spec.repo, spec.pinned_sha)

            matched_remote = [
                p for p in tree_cache[repo_key]
                if any(self._glob_matches(p, g) for g in spec.file_globs)
            ]

            for rel_remote in matched_remote:
                local_file = target_base / Path(rel_remote).name
                if local_file.exists() and not force_refresh:
                    fetched_paths[key].append(local_file)
                    continue

                quoted_path = "/".join(urllib.parse.quote(seg) for seg in rel_remote.split("/"))
                raw_url = f"https://raw.githubusercontent.com/{spec.repo}/{spec.pinned_sha}/{quoted_path}"
                req = urllib.request.Request(
                    raw_url,
                    headers={"User-Agent": "Saints-Studio-Witness-Diff/1.0"},
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    payload = resp.read()

                local_file.write_bytes(payload)
                digest = self._sha256_bytes(payload)
                lock_files[f"{key}/{local_file.name}"] = {
                    "corpus": key,
                    "repo": spec.repo,
                    "pinned_sha": spec.pinned_sha,
                    "remote_path": rel_remote,
                    "sha256": digest,
                    "license": spec.license_id,
                    "redistributable_open": spec.redistributable_open,
                    "fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                }
                fetched_paths[key].append(local_file)

        self.lock_path.write_text(
            json.dumps(lock_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return fetched_paths

    @staticmethod
    def _list_repo_tree(repo: str, sha: str) -> List[str]:
        api_url = f"https://api.github.com/repos/{repo}/git/trees/{sha}?recursive=1"
        headers = {"User-Agent": "Saints-Studio-Witness-Diff/1.0"}
        gh_token = os.environ.get("GITHUB_TOKEN")
        if gh_token:
            headers["Authorization"] = f"Bearer {gh_token}"
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=45) as resp:
            tree_json = json.loads(resp.read().decode("utf-8"))
        return [
            entry["path"]
            for entry in tree_json.get("tree", [])
            if entry.get("type") == "blob"
        ]


# ---------------------------------------------------------------------------
# 8. Multi-Witness Diff Engine & Classification
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class WitnessComparison:
    witness_key: str
    classification: str
    witness_text: str
    token_diff: str
    matching_editions: List[str] = dataclasses.field(default_factory=list)
    diverging_editions: List[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class VerseAuditEntry:
    language: str
    book: str
    chapter: int
    verse: int
    saints_source: str
    saints_english: Optional[str]
    highest_severity: str
    comparisons: List[WitnessComparison]
    mt_parallel_ref: Optional[str] = None


SEVERITY_ORDER = {
    "exact_match": 0,
    "cantillation_or_punctuation_only": 1,
    "orthographic_or_movable_nu": 2,
    "ketiv_qere_choice": 3,
    "vocalization_variant": 4,
    "substantive_variant": 5,
}


def inline_word_diff(base_tokens: Sequence[str], witness_tokens: Sequence[str]) -> str:
    matcher = difflib.SequenceMatcher(a=base_tokens, b=witness_tokens)
    chunks: List[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            span = base_tokens[i1:i2]
            if len(span) > 6:
                chunks.extend(span[:2])
                chunks.append("…")
                chunks.extend(span[-2:])
            else:
                chunks.extend(span)
        elif tag == "delete":
            chunks.append(f"[-{' '.join(base_tokens[i1:i2])}-]")
        elif tag == "insert":
            chunks.append(f"{{+{' '.join(witness_tokens[j1:j2])}+}}")
        elif tag == "replace":
            chunks.append(
                f"[-{' '.join(base_tokens[i1:i2])}-] {{+{' '.join(witness_tokens[j1:j2])}+}}"
            )
    return " ".join(chunks)


def compare_greek_verse(saints_text: str, wv: WitnessVerse) -> WitnessComparison:
    s_lex = GreekNormalizer.lexical_tokens(saints_text)
    w_lex = GreekNormalizer.lexical_tokens(wv.text)
    s_ortho = GreekNormalizer.orthographic_tokens(saints_text)
    w_ortho = GreekNormalizer.orthographic_tokens(wv.text)

    matching_eds: List[str] = []
    diverging_eds: List[str] = []
    if wv.edition_tags:
        for ed, ed_txt in wv.edition_tags.items():
            ed_lex = GreekNormalizer.lexical_tokens(ed_txt)
            if ed_lex == s_lex or GreekNormalizer.is_only_movable_nu_or_elision(s_lex, ed_lex):
                matching_eds.append(ed)
            else:
                diverging_eds.append(ed)

    if saints_text.strip() == wv.text.strip():
        cls_label = "exact_match"
        diff_str = ""
    elif s_ortho == w_ortho:
        cls_label = "cantillation_or_punctuation_only"
        diff_str = ""
    elif s_lex == w_lex or GreekNormalizer.is_only_movable_nu_or_elision(s_lex, w_lex):
        cls_label = "orthographic_or_movable_nu"
        diff_str = inline_word_diff(s_ortho, w_ortho)
    else:
        cls_label = "substantive_variant"
        diff_str = inline_word_diff(s_ortho, w_ortho)

    return WitnessComparison(
        witness_key=wv.corpus_key,
        classification=cls_label,
        witness_text=wv.text,
        token_diff=diff_str,
        matching_editions=matching_eds,
        diverging_editions=diverging_eds,
    )


def compare_hebrew_verse(saints_text: str, wv: WitnessVerse) -> WitnessComparison:
    s_qere_clean = HebrewNormalizer.strip_parenthesized_ketiv(saints_text)
    s_canon = HebrewNormalizer.canonicalize_hebrew(s_qere_clean)
    w_canon = HebrewNormalizer.canonicalize_hebrew(wv.text)

    s_cons = HebrewNormalizer.consonantal_tokens(saints_text)
    w_cons = HebrewNormalizer.consonantal_tokens(wv.text)
    s_voc = HebrewNormalizer.vocalized_tokens(saints_text)
    w_voc = HebrewNormalizer.vocalized_tokens(wv.text)

    if s_canon.strip() == w_canon.strip():
        return WitnessComparison(
            witness_key=wv.corpus_key,
            classification="exact_match",
            witness_text=wv.text,
            token_diff="",
        )
    if s_voc == w_voc:
        return WitnessComparison(
            witness_key=wv.corpus_key,
            classification="cantillation_or_punctuation_only",
            witness_text=wv.text,
            token_diff="",
        )

    # Check Ketiv vs Qere alignment when consonantal skeleton differs
    if s_cons != w_cons:
        s_ketiv_alt = HebrewNormalizer.substitute_parenthesized_ketiv(saints_text)
        s_ketiv_cons = HebrewNormalizer.consonantal_tokens(s_ketiv_alt) if s_ketiv_alt else []
        k_cons = HebrewNormalizer.consonantal_tokens(wv.ketiv_text) if wv.ketiv_text else []
        q_cons = HebrewNormalizer.consonantal_tokens(wv.qere_text) if wv.qere_text else []
        if (
            (q_cons and s_cons == q_cons)
            or (k_cons and s_cons == k_cons)
            or (s_ketiv_cons and (s_ketiv_cons == w_cons or (k_cons and s_ketiv_cons == k_cons)))
        ):
            return WitnessComparison(
                witness_key=wv.corpus_key,
                classification="ketiv_qere_choice",
                witness_text=wv.text,
                token_diff=inline_word_diff(s_voc, w_voc),
            )

    if s_cons == w_cons:
        cls_label = "vocalization_variant"
        diff_str = inline_word_diff(s_voc, w_voc)
    else:
        cls_label = "substantive_variant"
        diff_str = inline_word_diff(s_cons, w_cons)

    return WitnessComparison(
        witness_key=wv.corpus_key,
        classification=cls_label,
        witness_text=wv.text,
        token_diff=diff_str,
    )


def compare_latin_verse(saints_text: str, wv: WitnessVerse) -> WitnessComparison:
    s_lex = LatinNormalizer.lexical_tokens(saints_text)
    w_lex = LatinNormalizer.lexical_tokens(wv.text)
    s_ortho = LatinNormalizer.orthographic_tokens(saints_text)
    w_ortho = LatinNormalizer.orthographic_tokens(wv.text)

    if saints_text.strip() == wv.text.strip():
        cls_label = "exact_match"
        diff_str = ""
    elif s_ortho == w_ortho:
        cls_label = "cantillation_or_punctuation_only"
        diff_str = ""
    elif s_lex == w_lex:
        cls_label = "orthographic_or_movable_nu"
        diff_str = inline_word_diff(s_ortho, w_ortho)
    else:
        cls_label = "substantive_variant"
        diff_str = inline_word_diff(s_ortho, w_ortho)

    return WitnessComparison(
        witness_key=wv.corpus_key,
        classification=cls_label,
        witness_text=wv.text,
        token_diff=diff_str,
    )


# ---------------------------------------------------------------------------
# 9. Passage Filter & Report Writers (JSON Sidecars + Markdown Audit)
# ---------------------------------------------------------------------------

class PassageFilter:
    def __init__(self, spec: Optional[str]) -> None:
        self.allow_all = not bool(spec and spec.strip())
        self.books: set[str] = set()
        self._rules: List[Tuple[str, Optional[Tuple[int, int]], Optional[Tuple[int, int]]]] = []
        if self.allow_all:
            return

        for raw_token in (spec or "").split(","):
            tok = raw_token.strip()
            if not tok:
                continue
            m = re.match(
                r"^([1-4]?\s*[A-Za-z\-]+?)(?:[\. ]+(\d+)(?:-(\d+))?(?:[:\.](\d+)(?:-(\d+))?)?)?$",
                tok,
            )
            if not m:
                continue
            b_raw, ch1, ch2, v1, v2 = m.groups()
            b_code = resolve_book_code(b_raw)
            if not b_code:
                continue
            self.books.add(b_code)
            ch_range = (int(ch1), int(ch2 or ch1)) if ch1 else None
            v_range = (int(v1), int(v2 or v1)) if v1 else None
            self._rules.append((b_code, ch_range, v_range))

    def matches(self, book: str, ch: int, v: int) -> bool:
        if self.allow_all:
            return True
        for r_book, ch_r, v_r in self._rules:
            if r_book != book:
                continue
            if ch_r and not (ch_r[0] <= ch <= ch_r[1]):
                continue
            if v_r and not (v_r[0] <= v <= v_r[1]):
                continue
            return True
        return False


def write_audit_outputs(
    entries: Sequence[VerseAuditEntry],
    out_dir: Path,
    strict_orthography: bool = False,
) -> Tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    by_book_dir = out_dir / "witness_apparatus_by_book"
    by_book_dir.mkdir(parents=True, exist_ok=True)

    min_rank = (
        SEVERITY_ORDER["orthographic_or_movable_nu"]
        if strict_orthography
        else SEVERITY_ORDER["ketiv_qere_choice"]
    )

    flagged = [
        e for e in entries
        if SEVERITY_ORDER[e.highest_severity] >= min_rank
    ]

    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for e in flagged:
        grouped[(e.language, e.book)].append(dataclasses.asdict(e))

    for (lang, b_code), items in grouped.items():
        slug = BOOK_BY_CODE[b_code].slug
        sidecar = by_book_dir / f"{lang}_{slug}_witness_diff.json"
        sidecar.write_text(
            json.dumps(items, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    full_json = out_dir / "witness_diff_report.json"
    summary_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for e in entries:
        summary_counts[e.language]["total_checked"] += 1
        summary_counts[e.language][e.highest_severity] += 1

    full_payload = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "total_verses_checked": len(entries),
        "flagged_verses_count": len(flagged),
        "summary_by_language": {k: dict(v) for k, v in summary_counts.items()},
        "flagged_entries": [dataclasses.asdict(e) for e in flagged],
    }
    full_json.write_text(
        json.dumps(full_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    md_path = out_dir / "WITNESS_AUDIT_SUMMARY.md"
    lines: List[str] = [
        "# Saints Critical Text Studio — Multi-Witness Diff Report",
        "",
        f"- **Generated (UTC):** `{full_payload['generated_utc']}`",
        f"- **Total Verses Audited:** `{len(entries)}`",
        f"- **Flagged Verses (Substantive / Vocalization / Ketiv-Qere):** `{len(flagged)}`",
        "",
        "## 1. Summary by Language Stream",
        "",
        "| Language | Checked | Exact / Punct Only | Orthographic / Movable-Nu | Ketiv/Qere | Vocalization | Substantive Lexical |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for lang in ("greek", "hebrew", "latin"):
        if lang not in summary_counts:
            continue
        c = summary_counts[lang]
        exact_plus_punct = c.get("exact_match", 0) + c.get("cantillation_or_punctuation_only", 0)
        lines.append(
            f"| **{lang.capitalize()}** | {c.get('total_checked', 0)} | {exact_plus_punct} | "
            f"{c.get('orthographic_or_movable_nu', 0)} | {c.get('ketiv_qere_choice', 0)} | "
            f"{c.get('vocalization_variant', 0)} | **{c.get('substantive_variant', 0)}** |"
        )

    lines.extend([
        "",
        "## 2. Flagged Witness Divergences",
        "",
    ])

    if not flagged:
        lines.append("_No substantive variants detected in the audited scope._")
    else:
        for e in flagged[:250]:
            ref_label = f"{BOOK_BY_CODE[e.book].title} {e.chapter}:{e.verse}"
            lines.append(f"### [{e.language.upper()}] {ref_label} — `{e.highest_severity}`")
            lines.append(f"- **Saints Base Text:** `{e.saints_source}`")
            if e.saints_english:
                lines.append(f"- **Saints English:** {e.saints_english}")
            for comp in e.comparisons:
                if SEVERITY_ORDER[comp.classification] < min_rank:
                    continue
                ed_note = ""
                if comp.matching_editions or comp.diverging_editions:
                    ed_note = (
                        f" _(Saints matches: {', '.join(comp.matching_editions) or 'none'}; "
                        f"differs from: {', '.join(comp.diverging_editions) or 'none'})_"
                    )
                lines.append(
                    f"- **{comp.witness_key}** (`{comp.classification}`): "
                    f"{comp.token_diff or comp.witness_text}{ed_note}"
                )
            lines.append("")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return full_json, md_path


# ---------------------------------------------------------------------------
# 10. End-to-End Orchestrator & Built-in Offline Self-Test
# ---------------------------------------------------------------------------

def load_cached_witnesses(
    fetched_files: Dict[str, List[Path]],
) -> Dict[str, Dict[Tuple[str, int, int], WitnessVerse]]:
    witness_db: Dict[str, Dict[Tuple[str, int, int], WitnessVerse]] = defaultdict(dict)

    for key, paths in fetched_files.items():
        if key == "LXX_RAHLFS":
            # Prefer LXX_pre-final_2.csv (complete tagged verse rows across all 43 LXX books)
            preferred = [p for p in paths if p.name == "LXX_pre-final_2.csv"]
            target_paths = preferred if preferred else [
                p for p in paths
                if p.suffix.lower() in (".csv", ".txt")
                and "lexicon" not in p.name.lower()
                and "morphology" not in p.name.lower()
                and p.name not in ("01-04.csv", "LXX_pre-final_1.csv")
            ]
        else:
            target_paths = paths

        for p in target_paths:
            raw_text = p.read_text(encoding="utf-8", errors="replace")
            if key == "SRGNT":
                witness_db[key].update(parse_srgnt_text(raw_text))
            elif key == "SBLGNT":
                b_hint = resolve_book_code(p.name[:5])
                witness_db[key].update(parse_morphgnt_sblgnt(raw_text, b_hint))
            elif key == "TAGNT":
                witness_db[key].update(parse_stepbible_tagnt(raw_text))
            elif key == "TAHOT":
                witness_db[key].update(parse_stepbible_tahot(raw_text))
            elif key in ("OSHB_WLC", "OSHB_MAPM") and p.suffix.lower() == ".xml":
                witness_db[key].update(parse_oshb_osis_xml(raw_text, corpus_key=key))
            elif key == "PROIEL_VULGATE_NT" and p.suffix.lower() == ".xml":
                witness_db[key].update(parse_proiel_latin_xml(raw_text))
            elif key == "LXX_RAHLFS":
                witness_db[key].update(parse_lxx_rahlfs_wordlist(raw_text))

    return witness_db


def audit_all_streams(
    local_streams: Dict[str, Dict[Tuple[str, int, int], SaintsLocalVerse]],
    witness_db: Dict[str, Dict[Tuple[str, int, int], WitnessVerse]],
    pfilter: PassageFilter,
) -> List[VerseAuditEntry]:
    lang_witness_order = {
        "greek": ("SRGNT", "SBLGNT", "TAGNT", "LXX_RAHLFS"),
        "hebrew": ("TAHOT", "OSHB_WLC", "OSHB_MAPM"),
        "latin": ("PROIEL_VULGATE_NT",),
    }

    entries: List[VerseAuditEntry] = []

    for lang in ("greek", "hebrew", "latin"):
        verses_map = local_streams.get(lang, {})
        for (b_code, ch, v), sv in sorted(verses_map.items()):
            if not pfilter.matches(b_code, ch, v):
                continue

            comps: List[WitnessComparison] = []
            for w_key in lang_witness_order[lang]:
                w_map = witness_db.get(w_key)
                if not w_map:
                    continue
                wv = w_map.get((b_code, ch, v))
                if not wv:
                    continue
                if lang == "greek":
                    comps.append(compare_greek_verse(sv.source_text, wv))
                elif lang == "hebrew":
                    comps.append(compare_hebrew_verse(sv.source_text, wv))
                elif lang == "latin":
                    comps.append(compare_latin_verse(sv.source_text, wv))

            if not comps:
                continue

            top_sev = max(comps, key=lambda c: SEVERITY_ORDER[c.classification]).classification
            mt_ref_str: Optional[str] = None
            if b_code == "Psa" and lang in ("greek", "latin"):
                mapped = lxx_psalm_to_mt(ch, v)
                if mapped and mapped != (ch, v):
                    mt_ref_str = f"Psa.{mapped[0]}.{mapped[1]}"

            entries.append(
                VerseAuditEntry(
                    language=lang,
                    book=b_code,
                    chapter=ch,
                    verse=v,
                    saints_source=sv.source_text,
                    saints_english=sv.english_text,
                    highest_severity=top_sev,
                    comparisons=comps,
                    mt_parallel_ref=mt_ref_str,
                )
            )

    return entries


def _resolve_default_repo_path(workspace: Path, language: str) -> Path:
    """Finds either `<workspace>/<Lang>-Translation` or `<workspace>/Saints-<Lang>-Critical-Text`."""
    title = language.capitalize()
    candidates = (
        workspace / f"{title}-Translation",
        workspace / f"Saints-{title}-Critical-Text",
        workspace.parent / f"{title}-Translation",
    )
    for cand in candidates:
        if cand.is_dir():
            return cand
    return candidates[0]


def run_self_test() -> int:
    """
    Runs an offline end-to-end verification across Greek, Hebrew (including
    non-NFC pointing + Ketiv/Qere + milestone MAPM XML), Latin (Clementine vs
    Critical Jerome), CNTR/TAGNT sigla stripping, and LXX-MT Psalm mapping.
    """
    print("Running Saints Studio Multi-Witness Diff Engine self-test...")

    assert lxx_psalm_to_mt(22, 1) == (23, 1), "LXX Psalm 22:1 must map to MT Psalm 23:1"
    assert lxx_psalm_to_mt(9, 25) == (10, 4), "LXX Psalm 9:25 must map to MT Psalm 10:4"

    sample_sr = (
        "43001001 ¶Ἐν ἀρχῇ ἦν ὁ λόγος, καὶ ὁ λόγος ἦν πρὸς τὸν ˚Θεόν, καὶ ˚Θεὸς ἦν ὁ λόγος.\n"
        "43001018 ˚Θεὸν οὐδεὶς ἑώρακεν πώποτε· μονογενὴς ˚Θεὸς ὁ ὢν εἰς τὸν κόλπον τοῦ πατρὸς ἐκεῖνος ἐξηγήσατο.\n"
    )
    sample_sbl = (
        "040101 P- -------- Ἐν Ἐν ἐν ἐν\n"
        "040101 N- ----DSF- ἀρχῇ ἀρχῇ ἀρχῇ ἀρχή\n"
        "040101 V- 3IAI-S-- ἦν ἦν ἦν εἰμί\n"
        "040101 RA ----NSM- ὁ ὁ ὁ ὁ\n"
        "040101 N- ----NSM- λόγος, λόγος λόγος λόγος\n"
        "040101 C- -------- καὶ καὶ καί καί\n"
        "040101 RA ----NSM- ὁ ὁ ὁ ὁ\n"
        "040101 N- ----NSM- λόγος λόγος λόγος λόγος\n"
        "040101 V- 3IAI-S-- ἦν ἦν ἦν εἰμί\n"
        "040101 P- -------- πρὸς πρὸς πρός πρός\n"
        "040101 RA ----ASM- τὸν τὸν τόν ὁ\n"
        "040101 N- ----ASM- θεόν, θεόν θεόν θεός\n"
        "040101 C- -------- καὶ καὶ καί καί\n"
        "040101 N- ----NSM- θεὸς θεὸς θεός θεός\n"
        "040101 V- 3IAI-S-- ἦν ἦν ἦν εἰμί\n"
        "040101 RA ----NSM- ὁ ὁ ὁ ὁ\n"
        "040101 N- ----NSM- λόγος. λόγος λόγος λόγος\n"
    )
    sample_tagnt = (
        "Jhn.1.18#01=NKO\tθεὸν (theon)\t[God]\tG2316\tθεός\tNA28+Tyn+SBL+WH+Treg+Byz+TR\n"
        "Jhn.1.18#02=NKO\tοὐδεὶς (oudeis)\t[no one]\tG3762\tοὐδείς\tNA28+Tyn+SBL+WH+Treg+Byz+TR\n"
        "Jhn.1.18#03=NKO\tἑώρακεν (heōraken)\t[has seen]\tG3708\tὁράω\tNA28+Tyn+SBL+WH+Treg+Byz+TR\n"
        "Jhn.1.18#04=NKO\tπώποτε· (pōpote)\t[at any time]\tG4455\tπώποτε\tNA28+Tyn+SBL+WH+Treg+Byz+TR\n"
        "Jhn.1.18#05=K\tὁ (ho)\t[the]\tG3588\tὁ\tByz+TR\n"
        "Jhn.1.18#06=NKO\tμονογενὴς (monogenēs)\t[only-begotten]\tG3439\tμονογενής\tNA28+Tyn+SBL+WH+Treg+Byz+TR\n"
        "Jhn.1.18#07=N\tθεὸς (theos)\t[God]\tG2316\tθεός\tNA28+Tyn+WH+Treg\n"
        "Jhn.1.18#08=KO\tυἱὸς (huios)\t[Son]\tG5207\tυἱός\tSBL+Byz+TR\n"
        "Jhn.1.18#09=NKO\tὁ (ho)\t[who]\tG3588\tὁ\tNA28+Tyn+SBL+WH+Treg+Byz+TR\n"
        "Jhn.1.18#10=NKO\tὢν (ōn)\t[is]\tG1510\tεἰμί\tNA28+Tyn+SBL+WH+Treg+Byz+TR\n"
        "Jhn.1.18#11=NKO\tεἰς (eis)\t[in]\tG1519\tεἰς\tNA28+Tyn+SBL+WH+Treg+Byz+TR\n"
        "Jhn.1.18#12=NKO\tτὸν (ton)\t[the]\tG3588\tὁ\tNA28+Tyn+SBL+WH+Treg+Byz+TR\n"
        "Jhn.1.18#13=NKO\tκόλπον (kolpon)\t[bosom]\tG2859\tκόλπος\tNA28+Tyn+SBL+WH+Treg+Byz+TR\n"
        "Jhn.1.18#14=NKO\tτοῦ (tou)\t[of the]\tG3588\tὁ\tNA28+Tyn+SBL+WH+Treg+Byz+TR\n"
        "Jhn.1.18#15=NKO\tπατρὸς (patros)\t[Father]\tG3962\tπατήρ\tNA28+Tyn+SBL+WH+Treg+Byz+TR\n"
        "Jhn.1.18#16=NKO\tἐκεῖνος (ekeinos)\t[that one]\tG1565\tἐκεῖνος\tNA28+Tyn+SBL+WH+Treg+Byz+TR\n"
        "Jhn.1.18#17=NKO\tἐξηγήσατο.¶ (exēgēsato)\t[declared]\tG1834\tἐξηγέομαι\tNA28+Tyn+SBL+WH+Treg+Byz+TR\n"
    )
    sample_tahot = (
        "Psa.100.3#01=L\tדְּע֗וּ\tknow\n"
        "Psa.100.3#02=L\tכִּֽי\tthat\n"
        "Psa.100.3#03=L\tיְהוָה\tYHWH\n"
        "Psa.100.3#04=L\tה֤וּא\the\n"
        "Psa.100.3#05=L\tאֱלֹהִים\tGod\n"
        "Psa.100.3#06=L\tהֽוּא\the\n"
        "Psa.100.3#07=L\tעָשָׂנוּ\tmade us\n"
        "Psa.100.3#08=K\tוְלֹא\tand not\n"
        "Psa.100.3#09=Q\tוְלוֹ\tand his\n"
        "Psa.100.3#10=L\tאַנַחְנוּ\twe\n"
    )
    sample_mapm = (
        '<?xml version="1.0" encoding="utf-8"?><osis><osisText>'
        '<verse osisID="Ps.100.3" sID="Ps.100.3"/>דְּע֗וּ כִּֽי־יְהוָה ה֤וּא אֱלֹהִים '
        'הֽוּא עָשָׂנוּ <seg type="x-ketiv">ולא</seg> <seg type="x-qere">וְלוֹ</seg> אַנַחְנוּ'
        '<verse eID="Ps.100.3"/></osisText></osis>'
    )
    sample_proiel = """<?xml version="1.0" encoding="UTF-8"?>
    <proiel>
      <source id="latin-nt">
        <div>
          <sentence>
            <token form="in" citation-part="JOHN 1.1" presentation-after=" "/>
            <token form="principio" citation-part="JOHN 1.1" presentation-after=" "/>
            <token form="erat" citation-part="JOHN 1.1" presentation-after=" "/>
            <token form="uerbum" citation-part="JOHN 1.1" presentation-after=" "/>
          </sentence>
        </div>
      </source>
    </proiel>
    """

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        gk_repo = tmp_path / "Greek-Translation"
        hb_repo = tmp_path / "Hebrew-Translation"
        lt_repo = tmp_path / "Latin-Translation"

        (gk_repo / "john").mkdir(parents=True)
        (gk_repo / "john" / "verses.json").write_text(
            json.dumps([
                {
                    "chapter": 1,
                    "verse": 1,
                    "greek": "Ἐν ἀρχῇ ἦν ὁ Λόγος, καὶ ὁ Λόγος ἦν πρὸς τὸν Θεόν, καὶ Θεὸς ἦν ὁ Λόγος.",
                    "english": "In the beginning was the Word, and the Word was toward God, and God was the Word.",
                },
                {
                    "chapter": 1,
                    "verse": 18,
                    "greek": "Θεὸν οὐδεὶς ἑώρακε πώποτε· ὁ μονογενὴς υἱός, ὁ ὢν εἰς τὸν κόλπον τοῦ πατρός, ἐκεῖνος ἐξηγήσατο.",
                    "english": "No one has ever seen God; the only-begotten Son, who is in the bosom of the Father, he has made him known.",
                },
            ], ensure_ascii=False),
            encoding="utf-8",
        )

        (hb_repo / "psalms").mkdir(parents=True)
        (hb_repo / "psalms" / "verses.json").write_text(
            json.dumps([
                {
                    "chapter": 100,
                    "verse": 3,
                    "hebrew": "דְּעוּ כִּי יְהוָה הוּא אֱלֹהִים הוּא עָשָׂנוּ (ולא) וְלוֹ אַנַחְנוּ",
                    "english": "Know that the LORD, he is God; he made us, and we are his.",
                }
            ], ensure_ascii=False),
            encoding="utf-8",
        )

        (lt_repo / "john").mkdir(parents=True)
        (lt_repo / "john" / "verses.json").write_text(
            json.dumps([
                {
                    "chapter": 1,
                    "verse": 1,
                    "latin": "In principio erat Verbum,",
                    "english": "In the beginning was the Word,",
                }
            ], ensure_ascii=False),
            encoding="utf-8",
        )

        local_streams = {
            "greek": SaintsRepoLoader.load_repository(gk_repo, "greek"),
            "hebrew": SaintsRepoLoader.load_repository(hb_repo, "hebrew"),
            "latin": SaintsRepoLoader.load_repository(lt_repo, "latin"),
        }
        witness_db = {
            "SRGNT": parse_srgnt_text(sample_sr),
            "SBLGNT": parse_morphgnt_sblgnt(sample_sbl),
            "TAGNT": parse_stepbible_tagnt(sample_tagnt),
            "TAHOT": parse_stepbible_tahot(sample_tahot),
            "OSHB_MAPM": parse_oshb_osis_xml(sample_mapm, corpus_key="OSHB_MAPM"),
            "PROIEL_VULGATE_NT": parse_proiel_latin_xml(sample_proiel),
        }

        entries = audit_all_streams(local_streams, witness_db, PassageFilter(None))
        by_key = {(e.language, e.book, e.chapter, e.verse): e for e in entries}

        assert by_key[("greek", "Jhn", 1, 1)].highest_severity == "orthographic_or_movable_nu"

        j118 = by_key[("greek", "Jhn", 1, 18)]
        assert j118.highest_severity == "substantive_variant"
        tagnt_comp = [c for c in j118.comparisons if c.witness_key == "TAGNT"][0]
        assert "Byz" in tagnt_comp.matching_editions and "TR" in tagnt_comp.matching_editions
        assert "NA28" in tagnt_comp.diverging_editions

        psa100 = by_key[("hebrew", "Psa", 100, 3)]
        assert psa100.highest_severity == "ketiv_qere_choice"
        mapm_comp = [c for c in psa100.comparisons if c.witness_key == "OSHB_MAPM"][0]
        assert mapm_comp.classification == "cantillation_or_punctuation_only"

        assert by_key[("latin", "Jhn", 1, 1)].highest_severity == "orthographic_or_movable_nu"

        report_json, report_md = write_audit_outputs(entries, tmp_path / "out")
        assert report_json.is_file() and report_md.is_file()

    print("Self-test PASSED: All Greek, Hebrew, Latin, Ketiv/Qere, MAPM milestone, TAGNT edition-stream, and versification checks succeeded.")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Ingest pinned modern critical Bible witnesses and diff against Saints Studio repositories."
    )
    p.add_argument(
        "--workspace",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Studio root or parent folder containing Saints-*-Critical-Text or *-Translation (default: script dir).",
    )
    p.add_argument("--greek-repo", type=Path, default=None, help="Explicit path to Greek edition or repo.")
    p.add_argument("--hebrew-repo", type=Path, default=None, help="Explicit path to Hebrew edition or repo.")
    p.add_argument("--latin-repo", type=Path, default=None, help="Explicit path to Latin edition or repo.")
    p.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Directory for pinned upstream downloads and witness_lock.json (default: <workspace>/witness-cache).",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory for JSON apparatus sidecars and WITNESS_AUDIT_SUMMARY.md (default: <workspace>/witness-audit).",
    )
    p.add_argument(
        "--passages",
        type=str,
        default=None,
        help='Optional comma-separated filter, e.g. "Jhn.1.1,Jhn.2-3,Psa.22,Isa.53,1Ma.1,Rom.12.2".',
    )
    p.add_argument(
        "--license-tier",
        choices=("bundle", "nc-local"),
        default="bundle",
        help=(
            "'bundle' (default) downloads only CC BY 4.0 / Public Domain corpora safe for open-source distribution; "
            "'nc-local' also caches CC BY-NC-SA corpora (LXX-Rahlfs-1935, PROIEL Latin NT) in a git-ignored local folder."
        ),
    )
    p.add_argument(
        "--corpora",
        type=str,
        default="SRGNT,SBLGNT,TAGNT,TAHOT,OSHB_WLC,OSHB_MAPM,TVTMS",
        help="Comma-separated upstream witness keys to fetch and compare.",
    )
    p.add_argument(
        "--strict-orthography",
        action="store_true",
        help="Also include orthographic, accent, capitalization, movable-nu, and Latin u/v diffs in flagged reports.",
    )
    p.add_argument(
        "--offline",
        action="store_true",
        help="Use already-cached upstream files in --cache-dir without making network requests.",
    )
    p.add_argument(
        "--force-refresh",
        action="store_true",
        help="Re-download pinned upstream files even if already present in --cache-dir.",
    )
    p.add_argument(
        "--self-test",
        action="store_true",
        help="Run built-in offline verification suite and exit.",
    )
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.self_test:
        return run_self_test()

    workspace = args.workspace.resolve()
    gk_path = args.greek_repo or _resolve_default_repo_path(workspace, "greek")
    hb_path = args.hebrew_repo or _resolve_default_repo_path(workspace, "hebrew")
    lt_path = args.latin_repo or _resolve_default_repo_path(workspace, "latin")
    cache_dir = args.cache_dir or (workspace / "witness-cache")
    out_dir = args.out_dir or (workspace / "witness-audit")

    pfilter = PassageFilter(args.passages)
    book_subset = pfilter.books if not pfilter.allow_all else None

    print("1. Scanning local Saints Studio repositories...")
    local_streams = {
        "greek": SaintsRepoLoader.load_repository(gk_path, "greek", book_subset),
        "hebrew": SaintsRepoLoader.load_repository(hb_path, "hebrew", book_subset),
        "latin": SaintsRepoLoader.load_repository(lt_path, "latin", book_subset),
    }
    for lang, vmap in local_streams.items():
        src_dir = {"greek": gk_path, "hebrew": hb_path, "latin": lt_path}[lang]
        print(f"   - {lang.capitalize()} ({src_dir.name}): {len(vmap)} local verses loaded")

    requested_keys = [k.strip() for k in args.corpora.split(",") if k.strip() in UPSTREAM_CORPORA]
    include_nc = args.license_tier == "nc-local"
    if include_nc:
        for extra_nc in ("LXX_RAHLFS", "PROIEL_VULGATE_NT"):
            if extra_nc not in requested_keys:
                requested_keys.append(extra_nc)

    cache_mgr = WitnessCacheManager(cache_dir, include_nc_local=include_nc)
    if args.offline:
        print("2. Loading cached upstream critical texts (--offline)...")
        fetched_files: Dict[str, List[Path]] = defaultdict(list)
        for key in requested_keys:
            spec = UPSTREAM_CORPORA[key]
            base = (cache_mgr.open_dir if spec.redistributable_open else cache_mgr.nc_dir) / key
            if base.is_dir():
                fetched_files[key].extend(sorted(f for f in base.iterdir() if f.is_file()))
    else:
        print(f"2. Fetching pinned critical corpora ({', '.join(requested_keys)})...")
        try:
            fetched_files = cache_mgr.fetch_corpora(requested_keys, force_refresh=args.force_refresh)
        except urllib.error.URLError as exc:
            print(f"[ERROR] Network fetch failed: {exc}", file=sys.stderr)
            return 2

    print("3. Parsing critical witnesses and running philological alignment...")
    witness_db = load_cached_witnesses(fetched_files)
    for k, wmap in witness_db.items():
        print(f"   - {k}: {len(wmap)} witness verses parsed")

    entries = audit_all_streams(local_streams, witness_db, pfilter)
    full_json, summary_md = write_audit_outputs(
        entries,
        out_dir,
        strict_orthography=args.strict_orthography,
    )
    print(f"4. Complete! Wrote:\n   - {summary_md}\n   - {full_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
