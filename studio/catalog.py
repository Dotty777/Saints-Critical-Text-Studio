"""Canonical 7-Division, 70-Book Saints.Bible Catalog & Witness Path Mappings."""

from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

# Paths are derived from this file's location so the Studio is 100% self-contained
# wherever the Saints-Critical-Text-Studio folder lives. Environment overrides (the
# test suite uses them so it never writes into the real critical-text folders or database):
#   CTS_REPO_ROOT    – folder holding the Saints-{Greek,Hebrew,Latin}-Critical-Text corpora
#   CTS_OUTPUT_ROOT  – folder that receives Saints-{Greek,Hebrew,Latin}-Critical-Text
#   CTS_DATA_DIR     – folder for studio.db, settings.json and user witnesses
STUDIO_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(os.environ.get("CTS_REPO_ROOT") or STUDIO_ROOT)
OUTPUT_ROOT = Path(os.environ.get("CTS_OUTPUT_ROOT") or STUDIO_ROOT)
DATA_DIR = Path(os.environ.get("CTS_DATA_DIR") or (STUDIO_ROOT / "data"))

# A folder that only the research corpus has, for each language.
_RESEARCH_MARKERS = {"Greek": "01_Tier1_Modern_Critical_Open", "Hebrew": "hebrew-base", "Latin": "latin-base"}


def research_root(language: str) -> Path:
    """Where a language's research corpus lives. All corpora live inside Saints-Critical-Text-Studio
    under Saints-<Language>-Critical-Text beside the chapter files; legacy external layouts remain
    supported as fallbacks when CTS_REPO_ROOT points elsewhere."""
    title = language.title()
    marker = _RESEARCH_MARKERS[title]
    candidates = [
        REPO_ROOT / f"Saints-{title}-Critical-Text",
        STUDIO_ROOT / f"Saints-{title}-Critical-Text",
        STUDIO_ROOT.parent / f"Saints-{title}-Critical-Text",
        REPO_ROOT / f"Saints-{title}-Research-Texts",
        STUDIO_ROOT.parent / f"Saints-{title}-Research-Texts",
    ]
    for cand in candidates:
        if (cand / marker).exists():
            return cand
    return candidates[0]


GREEK_RESEARCH_ROOT = research_root("greek")
HEBREW_RESEARCH_ROOT = research_root("hebrew")
LATIN_RESEARCH_ROOT = research_root("latin")


def _resolve_latin_column_root() -> Path:
    in_studio = LATIN_RESEARCH_ROOT / "saints-latin-column"
    if in_studio.exists():
        return in_studio
    for fallback in (REPO_ROOT / "Latin-Translation", STUDIO_ROOT.parent / "Latin-Translation"):
        if fallback.exists():
            return fallback
    return in_studio


LATIN_TRANSLATION_ROOT = _resolve_latin_column_root()

CRITICAL_OUTPUT_ROOTS = {
    "greek": OUTPUT_ROOT / "Saints-Greek-Critical-Text",
    "hebrew": OUTPUT_ROOT / "Saints-Hebrew-Critical-Text",
    "latin": OUTPUT_ROOT / "Saints-Latin-Critical-Text",
}

# Which witness (by parser kind, first one present wins) defines verse numbering
# for each language and testament. Every other witness is re-aligned to it by
# content, so editions that number chapters differently (Joel, Malachi, Daniel,
# Sirach, 1 Samuel 17, the Vulgate generally) are never collated verse-against-
# the-wrong-verse. Greek OT: Brenton/eBible (Saints.Bible numbering); NT: SBLGNT;
# Hebrew: WLC (MT numbering); Latin: the Saints Clementine JSON, which follows
# Saints.Bible numbering and records the Vulgate reference where it differs.
VERSIFICATION_ANCHORS = {
    ("greek", "OT"): ["brenton_usfm", "swete_csv", "swete_clean", "first1k_tei"],
    ("greek", "NT"): ["sblgnt_txt", "nestle_csv", "cntr_edition"],
    ("hebrew", "OT"): ["wlc_tsv", "mam_osis"],
    ("latin", "OT"): ["latin_saints_json", "usfx_xml"],
    ("latin", "NT"): ["latin_saints_json", "usfx_xml"],
}

# Which witness supplies spelling, accentuation, capitalisation and punctuation
# whenever it attests the adopted reading, so the critical text keeps one
# consistent orthography instead of mixing conventions word by word.
ORTHOGRAPHIC_BASE = {
    # The Swete CSV is a transcription, not OCR: where it has the chapter its spelling leads.
    ("greek", "OT"): ["swete_csv", "first1k_tei", "swete_clean", "brenton_usfm"],
    ("greek", "NT"): ["sblgnt_txt", "cntr_edition"],
    ("hebrew", "OT"): ["mam_osis", "wlc_tsv"],
    ("latin", "OT"): ["usfx_xml", "latin_saints_json"],
    ("latin", "NT"): ["usfx_xml", "latin_saints_json"],
}

# Digital copies of one printed edition vote once (max weight), never twice.
EDITION_FAMILIES = {
    "grk-swete-lxx": "swete_edition",          # Swete Clean is derived from First1KGreek tlg0527
    "grk-1st1k-lxx": "swete_edition",
    "grk-swete-csv": "swete_edition",          # independent transcription of the same edition (not OCR)
    "grk-nt-kjtr": "tr_edition",               # printed Textus Receptus editions vote once together
    "grk-nt-tr-scrivener": "tr_edition",
    "grk-nt-tr-boyd": "tr_edition",
    "lat-clementine-usfx": "clementine_edition",
    "lat-saints-staging": "clementine_edition",  # Saints Latin column = Clementine, renumbered
    "lat-vulg-hetzenauer": "clementine_edition", # Hetzenauer 1906 critical Sixto-Clementine
    "lat-vulg-conte": "clementine_edition",      # Conte 2009 Public Domain Sixto-Clementine
    "heb-wlc-tsv": "leningrad_codex",
    "heb-leningrad-usfx-corrupt": "leningrad_codex",
}

# Witness files that are not what their catalogue entry says for one book: (witness id, book slug)
# -> reason. They are left out of that book's collation and the reason is logged with the chapter.
WITNESS_BOOK_EXCLUSIONS = {
    ("grk-lxx-orthodox", "2-maccabees"): (
        "LXX-Orthodox is left out of 2 Maccabees: its file labelled 2MA (53-2MAgrclxx.usfm) is 4 Maccabees "
        "(title ΜΑΚΚΑΒΑΙΩΝ Δ, 18 chapters); the set has no 2 Maccabees."
    ),
    ("grk-swete-lxx", "isaiah"): (
        "Swete Clean is left out of Isaiah: its Isaiah file is Ottley's 1904 transcription of Codex "
        "Alexandrinus (A), a different text and OCR, not Swete (its build overwrote Swete's file). "
        "First1KGreek supplies Swete's Isaiah. Whether readings of A may vote is the owner's decision."
    ),
}

# How many chapters on each side a witness's verses may be re-aligned from (default 1). Sirach
# 30–36 stand in a different order in Swete and in Brenton, so its verses must be found up to six
# chapters away.
ALIGNMENT_WINDOW = {
    "sirach": 6,
    "proverbs": 7,               # Swete 24:22–37 = Brenton 30:1–14, Swete 29:28–49 = Brenton 31:10–31
    ("latin", "exodus"): 3,      # Saints/LXX Exodus 36:8–38 = Vulgate Exodus 39:1–31
    ("latin", "jeremiah"): 26,   # the Saints column follows the Septuagint order of Jeremiah 25–51
}

# Printed editions whose silence is a decision: when one of them has the verses on both sides of a
# verse (within two verses) but not the verse itself, it counts as lacking that verse. Manuscript
# transcriptions (01, 03), Swete and the OT editions are never counted this way — their silence can
# be a gap in the file, a homoeoteleuton in the codex or a different numbering.
SILENT_MEANS_ABSENT = {
    "grk-nt-sblgnt", "grk-nt-nestle1904", "grk-nt-rp2018", "grk-nt-tcgnt",
    "grk-nt-pt1904", "grk-nt-kjtr", "grk-nt-tr-scrivener", "grk-nt-tr-boyd",
}

# Text streams (independent lines of evidence), shared by the engine and the brains.
# Keys are witness sigla prefixes.
STREAM_OF_SIGLUM = [
    ("א (01)", "early manuscripts"), ("B (03)", "early manuscripts"),
    ("SRGNT", "modern critical editions"), ("BHP", "modern critical editions"),
    ("SBLGNT", "modern critical editions"), ("Nestle1904", "modern critical editions"),
    ("RP2018", "Byzantine / ecclesiastical"), ("TCGNT", "Byzantine / ecclesiastical"),
    ("PT1904", "Byzantine / ecclesiastical"), ("TR", "Byzantine / ecclesiastical"),
    ("Swete", "Vaticanus-based LXX (Swete)"), ("1st1K", "Vaticanus-based LXX (Swete)"),  # all three Swete copies
    ("Sixtine/Brenton", "Sixtine / Ecclesiastical LXX"), ("LXX-Orthodox", "Sixtine / Ecclesiastical LXX"),
    ("MAM", "Aleppo tradition (MAM)"), ("WLC", "Leningrad Codex (WLC)"),
    ("BenChayyim", "Medieval Masoretic Majority (Ben Chayyim)"),
    ("Letteris", "Medieval Masoretic Majority (Ben Chayyim)"),
    ("Amiatinus", "early Vulgate manuscript (Amiatinus)"),
    ("Clem", "Clementine Vulgate"), ("VulgHetzenauer", "Clementine Vulgate"), ("VulgConte", "Clementine Vulgate"),
    ("VulgSistina", "Sixtine Vulgate (1590)"),
]


# Majority and ecclesiastical editions collated for the apparatus only (added 17 Nov 2026). Each is
# re-aligned to the numbering anchor like every witness, and wherever it differs in substance from the
# edited text its reading is recorded in the apparatus (spelling and pointing conventions go to the
# disregarded log). They never vote on the text, choose a spelling or feed the corpus lexicon, so the
# edition keeps its basis: Swete's Codex Vaticanus in the Greek OT, reasoned eclecticism in the Greek
# NT (the Byzantine stream keeps its two votes, RP2018 and the TR), MAM's pointing in the Hebrew and
# the Saints Clementine in the Latin. A verse only they print is noted, not printed.
APPARATUS_ONLY = frozenset({
    "grk-lxx-orthodox", "grk-nt-tcgnt", "grk-nt-pt1904", "grk-nt-tr-scrivener", "grk-nt-tr-boyd",
    "heb-benchayyim-1525", "heb-letteris-1852",
    "lat-vulg-hetzenauer", "lat-vulg-conte", "lat-vulg-sistina",
})


def is_apparatus_only(w) -> bool:
    return str(w["id"]) in APPARATUS_ONLY


# Copies of one edition that were digitised independently of each other (keyed by siglum like the
# streams above). A spelling that two independent digitisations share is the edition's own printing,
# not a digitisation slip, so it is never "corrected" from another edition. The two OCR copies of
# Swete share one OCR and count once.
DIGITISATION_OF_SIGLUM = {
    "Swete-Amicarelli": "Swete keyed transcription",
    "1st1K-LXX": "Swete OCR",
    "Swete (B/A/א)": "Swete OCR",
}


def independent_digitisations(sigla) -> int:
    return len({DIGITISATION_OF_SIGLUM[s] for s in sigla if s in DIGITISATION_OF_SIGLUM})


def stream_of(siglum: str) -> str:
    for prefix, stream in STREAM_OF_SIGLUM:
        if siglum.startswith(prefix):
            return stream
    return f"other ({siglum})"


VERSIFICATION_NOTES = {
    "greek": "Septuagint numbering as in Brenton/eBible (the Saints.Bible numbering) for the OT; standard numbering for the NT. Witnesses that number differently (e.g. Swete in Joel and Malachi) are re-aligned by content. Proverbs is numbered as Saints.Bible numbers it: Hebrew chapter and verse numbers in the Greek order (24:1–22e, 30:1–14, 24:23–34, 30:15–33, 31:1–9, 25–29, 31:10–31), not as the Brenton e-text runs 30:1–31:9 on as 24:22–62.",
    "hebrew": "Masoretic (MT) numbering. Psalms 10–147 carry MT numbers, one higher than the Septuagint/Vulgate psalm numbers used by the Greek and Latin editions.",
    "latin": "Saints.Bible numbering (the Latin column's Greek/Hebrew numbering). Where the Clementine Vulgate numbers a verse differently it is re-aligned by content.",
}

# Google Drive parent folders inside "Saints Website" (1V_ObdWyPF8Z8JmfdC6XYSsZN8AGCyYnc)
GDRIVE_LANGUAGE_PARENTS = {
    "greek": "1C_lJ7UyCMtwDfaNk701cX0VFgZSEUTmb",   # Greek Translation
    "hebrew": "1wxecIfxAdMQ4AYLrJZtmsXeF9ToFP1ZC",  # Hebrew Translation
    "latin": "1pAxlmY7kMI9e-PJjVVs_XBOuTMhPg2a2",   # Latin Translation
}

DIVISIONS = [
    {"id": "01_Law", "label": "01 · Law (Books 1–5)"},
    {"id": "02_Judgement", "label": "02 · Judgement (Books 6–20)"},
    {"id": "03_Wisdom", "label": "03 · Wisdom (Books 21–27)"},
    {"id": "04_Providence", "label": "04 · Providence (Books 28–43)"},
    {"id": "05_Salvation", "label": "05 · Salvation (Books 44–47)"},
    {"id": "06_Discipleship", "label": "06 · Discipleship (Books 48–69)"},
    {"id": "07_Glory", "label": "07 · Glory (Book 70)"},
]


@dataclass(frozen=True)
class BookSpec:
    order: int
    slug: str
    folder_name: str
    title: str
    division: str
    testament: str  # "OT" or "NT"
    chapters: int
    usfm_code: str
    # Language availability in canonical sources
    has_greek: bool = True
    has_hebrew: bool = True
    has_latin: bool = True
    # Greek OT mappings
    swete_file: Optional[str] = None
    swete_chapter_offset: int = 0  # e.g. Nehemiah = Esdras_B ch 11..23 (offset +10)
    brenton_chapter_offset: int = 0  # Brenton's 16-EZR file is also 2 Esdras (Nehemiah = ch 11..23)
    tlg_work: Optional[str] = None
    brenton_file: Optional[str] = None
    # Greek NT mappings
    cntr_book: Optional[int] = None
    sbl_code: Optional[str] = None
    rp_code: Optional[str] = None
    ugnt_file: Optional[str] = None


BOOKS: List[BookSpec] = [
    # 01_Law (1-5)
    BookSpec(1, "genesis", "01_Genesis", "Genesis", "01_Law", "OT", 50, "GEN",
             swete_file="01.Genesis.txt", tlg_work="tlg001", brenton_file="02-GENgrcbrent.usfm"),
    BookSpec(2, "exodus", "02_Exodus", "Exodus", "01_Law", "OT", 40, "EXO",
             swete_file="02.Exodus.txt", tlg_work="tlg002", brenton_file="03-EXOgrcbrent.usfm"),
    BookSpec(3, "leviticus", "03_Leviticus", "Leviticus", "01_Law", "OT", 27, "LEV",
             swete_file="03.Leviticus.txt", tlg_work="tlg003", brenton_file="04-LEVgrcbrent.usfm"),
    BookSpec(4, "numbers", "04_Numbers", "Numbers", "01_Law", "OT", 36, "NUM",
             swete_file="04.Numeri.txt", tlg_work="tlg004", brenton_file="05-NUMgrcbrent.usfm"),
    BookSpec(5, "deuteronomy", "05_Deuteronomy", "Deuteronomy", "01_Law", "OT", 34, "DEU",
             swete_file="05.Deuteronomium.txt", tlg_work="tlg005", brenton_file="06-DEUgrcbrent.usfm"),

    # 02_Judgement (6-20)
    BookSpec(6, "joshua", "06_Joshua", "Joshua", "02_Judgement", "OT", 24, "JOS",
             swete_file="06.Josue.txt", tlg_work="tlg006", brenton_file="07-JOSgrcbrent.usfm"),
    BookSpec(7, "judges", "07_Judges", "Judges", "02_Judgement", "OT", 21, "JDG",
             swete_file="08.Judices.txt", tlg_work="tlg008", brenton_file="08-JDGgrcbrent.usfm"),
    BookSpec(8, "ruth", "08_Ruth", "Ruth", "02_Judgement", "OT", 4, "RUT",
             swete_file="10.Ruth.txt", tlg_work="tlg010", brenton_file="09-RUTgrcbrent.usfm"),
    BookSpec(9, "1-samuel", "09_1_Samuel", "1 Samuel (1 Kingdoms)", "02_Judgement", "OT", 31, "1SA",
             swete_file="11.Regnorum_I.txt", tlg_work="tlg011", brenton_file="10-1SAgrcbrent.usfm"),
    BookSpec(10, "2-samuel", "10_2_Samuel", "2 Samuel (2 Kingdoms)", "02_Judgement", "OT", 24, "2SA",
             swete_file="12.Regnorum_II.txt", tlg_work="tlg012", brenton_file="11-2SAgrcbrent.usfm"),
    BookSpec(11, "1-kings", "11_1_Kings", "1 Kings (3 Kingdoms)", "02_Judgement", "OT", 22, "1KI",
             swete_file="13.Regnorum_III.txt", tlg_work="tlg013", brenton_file="12-1KIgrcbrent.usfm"),
    BookSpec(12, "2-kings", "12_2_Kings", "2 Kings (4 Kingdoms)", "02_Judgement", "OT", 25, "2KI",
             swete_file="14.Regnorum_IV.txt", tlg_work="tlg014", brenton_file="13-2KIgrcbrent.usfm"),
    BookSpec(13, "1-chronicles", "13_1_Chronicles", "1 Chronicles", "02_Judgement", "OT", 29, "1CH",
             swete_file="15.Paralipomenon_I.txt", tlg_work="tlg015", brenton_file="14-1CHgrcbrent.usfm"),
    BookSpec(14, "2-chronicles", "14_2_Chronicles", "2 Chronicles", "02_Judgement", "OT", 36, "2CH",
             swete_file="16.Paralipomenon_II.txt", tlg_work="tlg016", brenton_file="15-2CHgrcbrent.usfm"),
    BookSpec(15, "ezra", "15_Ezra", "Ezra", "02_Judgement", "OT", 10, "EZR",
             swete_file="18.Esdras_B.txt", tlg_work="tlg018", brenton_file="16-EZRgrcbrent.usfm"),
    BookSpec(16, "nehemiah", "16_Nehemiah", "Nehemiah", "02_Judgement", "OT", 13, "NEH",
             swete_file="18.Esdras_B.txt", swete_chapter_offset=10, tlg_work="tlg018", brenton_file="16-EZRgrcbrent.usfm",
             brenton_chapter_offset=10),
    BookSpec(17, "esther", "17_Esther", "Esther", "02_Judgement", "OT", 10, "EST",
             swete_file="19.Esther.txt", tlg_work="tlg019", brenton_file="43-ESGgrcbrent.usfm"),
    BookSpec(18, "1-maccabees", "18_1_Maccabees", "1 Maccabees", "02_Judgement", "OT", 16, "1MA",
             has_hebrew=False, swete_file="23.Machabaeorum_i.txt", tlg_work="tlg023", brenton_file="52-1MAgrcbrent.usfm"),
    BookSpec(19, "2-maccabees", "19_2_Maccabees", "2 Maccabees", "02_Judgement", "OT", 15, "2MA",
             has_hebrew=False, swete_file="24.Machabaeorum_ii.txt", tlg_work="tlg024", brenton_file="53-2MAgrcbrent.usfm"),
    BookSpec(20, "job", "20_Job", "Job", "02_Judgement", "OT", 42, "JOB",
             swete_file="32.Job.txt", tlg_work="tlg032", brenton_file="19-JOBgrcbrent.usfm"),

    # 03_Wisdom (21-27)
    BookSpec(21, "psalms", "21_Psalms", "Psalms", "03_Wisdom", "OT", 151, "PSA",
             swete_file="27.Psalmi.txt", tlg_work="tlg027", brenton_file="20-PSAgrcbrent.usfm"),
    BookSpec(22, "proverbs", "22_Proverbs", "Proverbs", "03_Wisdom", "OT", 31, "PRO",
             swete_file="29.Proverbia.txt", tlg_work="tlg029", brenton_file="21-PROgrcbrent.usfm"),
    BookSpec(23, "ecclesiastes", "23_Ecclesiastes", "Ecclesiastes", "03_Wisdom", "OT", 12, "ECC",
             swete_file=None, tlg_work="tlg030", brenton_file="22-ECCgrcbrent.usfm"),
    BookSpec(24, "song-of-songs", "24_Song_of_Songs", "Song of Songs", "03_Wisdom", "OT", 8, "SNG",
             swete_file="31.Canticum.txt", tlg_work="tlg031", brenton_file="23-SNGgrcbrent.usfm"),
    BookSpec(25, "lamentations", "25_Lamentations", "Lamentations", "03_Wisdom", "OT", 5, "LAM",
             swete_file="51.Threni_seu_Lamentationes.txt", tlg_work="tlg051", brenton_file="26-LAMgrcbrent.usfm"),
    BookSpec(26, "wisdom-of-solomon", "26_Wisdom_of_Solomon", "Wisdom of Solomon", "03_Wisdom", "OT", 19, "WIS",
             has_hebrew=False, swete_file="33.Sapientia_Salomonis.txt", tlg_work="tlg033", brenton_file="45-WISgrcbrent.usfm"),
    BookSpec(27, "sirach", "27_Sirach", "Sirach", "03_Wisdom", "OT", 51, "SIR",
             has_hebrew=False, swete_file="34.Ecclesiasticus.txt", tlg_work="tlg034", brenton_file="46-SIRgrcbrent.usfm"),

    # 04_Providence (28-43)
    BookSpec(28, "isaiah", "28_Isaiah", "Isaiah", "04_Providence", "OT", 66, "ISA",
             swete_file="48.Isaias.txt", tlg_work="tlg048", brenton_file="24-ISAgrcbrent.usfm"),
    BookSpec(29, "jeremiah", "29_Jeremiah", "Jeremiah", "04_Providence", "OT", 52, "JER",
             swete_file="49.Jeremias.txt", tlg_work="tlg049", brenton_file="25-JERgrcbrent.usfm"),
    BookSpec(30, "ezekiel", "30_Ezekiel", "Ezekiel", "04_Providence", "OT", 48, "EZK",
             swete_file="53.Ezechiel.txt", tlg_work="tlg053", brenton_file="27-EZKgrcbrent.usfm"),
    BookSpec(31, "daniel", "31_Daniel", "Daniel", "04_Providence", "OT", 12, "DAN",
             # Theodotion (Swete 57 / tlg057): the version Brenton and the churches read. The Old Greek
             # (Swete 56) is a different translation, so collating it against Brenton produced false variants.
             swete_file="57.Daniel_Theodotionis_versio.txt", tlg_work="tlg057", brenton_file="66-DAGgrcbrent.usfm"),
    BookSpec(32, "hosea", "32_Hosea", "Hosea", "04_Providence", "OT", 14, "HOS",
             swete_file="36.Osee.txt", tlg_work="tlg036", brenton_file="29-HOSgrcbrent.usfm"),
    BookSpec(33, "joel", "33_Joel", "Joel", "04_Providence", "OT", 4, "JOL",
             swete_file="39.Joel.txt", tlg_work="tlg039", brenton_file="30-JOLgrcbrent.usfm"),
    BookSpec(34, "amos", "34_Amos", "Amos", "04_Providence", "OT", 9, "AMO",
             swete_file="37.Amos.txt", tlg_work="tlg037", brenton_file="31-AMOgrcbrent.usfm"),
    BookSpec(35, "obadiah", "35_Obadiah", "Obadiah", "04_Providence", "OT", 1, "OBA",
             swete_file="40.Abdias.txt", tlg_work="tlg040", brenton_file="32-OBAgrcbrent.usfm"),
    BookSpec(36, "jonah", "36_Jonah", "Jonah", "04_Providence", "OT", 4, "JON",
             swete_file="41.Jonas.txt", tlg_work="tlg041", brenton_file="33-JONgrcbrent.usfm"),
    BookSpec(37, "micah", "37_Micah", "Micah", "04_Providence", "OT", 7, "MIC",
             swete_file="38.Michaeas.txt", tlg_work="tlg038", brenton_file="34-MICgrcbrent.usfm"),
    BookSpec(38, "nahum", "38_Nahum", "Nahum", "04_Providence", "OT", 3, "NAM",
             swete_file="42.Nahum.txt", tlg_work="tlg042", brenton_file="35-NAMgrcbrent.usfm"),
    BookSpec(39, "habakkuk", "39_Habakkuk", "Habakkuk", "04_Providence", "OT", 3, "HAB",
             swete_file="43.Habacuc.txt", tlg_work="tlg043", brenton_file="36-HABgrcbrent.usfm"),
    BookSpec(40, "zephaniah", "40_Zephaniah", "Zephaniah", "04_Providence", "OT", 3, "ZEP",
             swete_file="44.Sophonias.txt", tlg_work="tlg044", brenton_file="37-ZEPgrcbrent.usfm"),
    BookSpec(41, "haggai", "41_Haggai", "Haggai", "04_Providence", "OT", 2, "HAG",
             swete_file="45.Aggaeus.txt", tlg_work="tlg045", brenton_file="38-HAGgrcbrent.usfm"),
    BookSpec(42, "zechariah", "42_Zechariah", "Zechariah", "04_Providence", "OT", 14, "ZEC",
             swete_file="46.Zacharias.txt", tlg_work="tlg046", brenton_file="39-ZECgrcbrent.usfm"),
    BookSpec(43, "malachi", "43_Malachi", "Malachi", "04_Providence", "OT", 3, "MAL",
             swete_file="47.Malachias.txt", tlg_work="tlg047", brenton_file="40-MALgrcbrent.usfm"),

    # 05_Salvation (44-47) - NT Gospels
    BookSpec(44, "matthew", "44_Matthew", "Matthew", "05_Salvation", "NT", 28, "MAT",
             has_hebrew=False, cntr_book=40, sbl_code="Matt", rp_code="MAT", ugnt_file="41-MAT.usfm"),
    BookSpec(45, "mark", "45_Mark", "Mark", "05_Salvation", "NT", 16, "MRK",
             has_hebrew=False, cntr_book=41, sbl_code="Mark", rp_code="MAR", ugnt_file="42-MRK.usfm"),
    BookSpec(46, "luke", "46_Luke", "Luke", "05_Salvation", "NT", 24, "LUK",
             has_hebrew=False, cntr_book=42, sbl_code="Luke", rp_code="LUK", ugnt_file="43-LUK.usfm"),
    BookSpec(47, "john", "47_John", "John", "05_Salvation", "NT", 21, "JHN",
             has_hebrew=False, cntr_book=43, sbl_code="John", rp_code="JOH", ugnt_file="44-JHN.usfm"),

    # 06_Discipleship (48-69)
    BookSpec(48, "acts", "48_Acts", "Acts", "06_Discipleship", "NT", 28, "ACT",
             has_hebrew=False, cntr_book=44, sbl_code="Acts", rp_code="ACT", ugnt_file="45-ACT.usfm"),
    BookSpec(49, "romans", "49_Romans", "Romans", "06_Discipleship", "NT", 16, "ROM",
             has_hebrew=False, cntr_book=45, sbl_code="Rom", rp_code="ROM", ugnt_file="46-ROM.usfm"),
    BookSpec(50, "1-corinthians", "50_1_Corinthians", "1 Corinthians", "06_Discipleship", "NT", 16, "1CO",
             has_hebrew=False, cntr_book=46, sbl_code="1Cor", rp_code="1CO", ugnt_file="47-1CO.usfm"),
    BookSpec(51, "2-corinthians", "51_2_Corinthians", "2 Corinthians", "06_Discipleship", "NT", 13, "2CO",
             has_hebrew=False, cntr_book=47, sbl_code="2Cor", rp_code="2CO", ugnt_file="48-2CO.usfm"),
    BookSpec(52, "galatians", "52_Galatians", "Galatians", "06_Discipleship", "NT", 6, "GAL",
             has_hebrew=False, cntr_book=48, sbl_code="Gal", rp_code="GAL", ugnt_file="49-GAL.usfm"),
    BookSpec(53, "ephesians", "53_Ephesians", "Ephesians", "06_Discipleship", "NT", 6, "EPH",
             has_hebrew=False, cntr_book=49, sbl_code="Eph", rp_code="EPH", ugnt_file="50-EPH.usfm"),
    BookSpec(54, "philippians", "54_Philippians", "Philippians", "06_Discipleship", "NT", 4, "PHP",
             has_hebrew=False, cntr_book=50, sbl_code="Phil", rp_code="PHP", ugnt_file="51-PHP.usfm"),
    BookSpec(55, "colossians", "55_Colossians", "Colossians", "06_Discipleship", "NT", 4, "COL",
             has_hebrew=False, cntr_book=51, sbl_code="Col", rp_code="COL", ugnt_file="52-COL.usfm"),
    BookSpec(56, "1-thessalonians", "56_1_Thessalonians", "1 Thessalonians", "06_Discipleship", "NT", 5, "1TH",
             has_hebrew=False, cntr_book=52, sbl_code="1Thess", rp_code="1TH", ugnt_file="53-1TH.usfm"),
    BookSpec(57, "2-thessalonians", "57_2_Thessalonians", "2 Thessalonians", "06_Discipleship", "NT", 3, "2TH",
             has_hebrew=False, cntr_book=53, sbl_code="2Thess", rp_code="2TH", ugnt_file="54-2TH.usfm"),
    BookSpec(58, "1-timothy", "58_1_Timothy", "1 Timothy", "06_Discipleship", "NT", 6, "1TI",
             has_hebrew=False, cntr_book=54, sbl_code="1Tim", rp_code="1TI", ugnt_file="55-1TI.usfm"),
    BookSpec(59, "2-timothy", "59_2_Timothy", "2 Timothy", "06_Discipleship", "NT", 4, "2TI",
             has_hebrew=False, cntr_book=55, sbl_code="2Tim", rp_code="2TI", ugnt_file="56-2TI.usfm"),
    BookSpec(60, "titus", "60_Titus", "Titus", "06_Discipleship", "NT", 3, "TIT",
             has_hebrew=False, cntr_book=56, sbl_code="Titus", rp_code="TIT", ugnt_file="57-TIT.usfm"),
    BookSpec(61, "philemon", "61_Philemon", "Philemon", "06_Discipleship", "NT", 1, "PHM",
             has_hebrew=False, cntr_book=57, sbl_code="Phlm", rp_code="PHM", ugnt_file="58-PHM.usfm"),
    BookSpec(62, "hebrews", "62_Hebrews", "Hebrews", "06_Discipleship", "NT", 13, "HEB",
             has_hebrew=False, cntr_book=58, sbl_code="Heb", rp_code="HEB", ugnt_file="59-HEB.usfm"),
    BookSpec(63, "james", "63_James", "James", "06_Discipleship", "NT", 5, "JAS",
             has_hebrew=False, cntr_book=59, sbl_code="Jas", rp_code="JAM", ugnt_file="60-JAS.usfm"),
    BookSpec(64, "1-peter", "64_1_Peter", "1 Peter", "06_Discipleship", "NT", 5, "1PE",
             has_hebrew=False, cntr_book=60, sbl_code="1Pet", rp_code="1PE", ugnt_file="61-1PE.usfm"),
    BookSpec(65, "2-peter", "65_2_Peter", "2 Peter", "06_Discipleship", "NT", 3, "2PE",
             has_hebrew=False, cntr_book=61, sbl_code="2Pet", rp_code="2PE", ugnt_file="62-2PE.usfm"),
    BookSpec(66, "1-john", "66_1_John", "1 John", "06_Discipleship", "NT", 5, "1JN",
             has_hebrew=False, cntr_book=62, sbl_code="1John", rp_code="1JO", ugnt_file="63-1JN.usfm"),
    BookSpec(67, "2-john", "67_2_John", "2 John", "06_Discipleship", "NT", 1, "2JN",
             has_hebrew=False, cntr_book=63, sbl_code="2John", rp_code="2JO", ugnt_file="64-2JN.usfm"),
    BookSpec(68, "3-john", "68_3_John", "3 John", "06_Discipleship", "NT", 1, "3JN",
             has_hebrew=False, cntr_book=64, sbl_code="3John", rp_code="3JO", ugnt_file="65-3JN.usfm"),
    BookSpec(69, "jude", "69_Jude", "Jude", "06_Discipleship", "NT", 1, "JUD",
             has_hebrew=False, cntr_book=65, sbl_code="Jude", rp_code="JUD", ugnt_file="66-JUD.usfm"),

    # 07_Glory (70)
    BookSpec(70, "revelation", "70_Revelation", "Revelation", "07_Glory", "NT", 22, "REV",
             has_hebrew=False, cntr_book=66, sbl_code="Rev", rp_code="REV", ugnt_file="67-REV.usfm"),
]

BOOKS_BY_SLUG: Dict[str, BookSpec] = {b.slug: b for b in BOOKS}
BOOKS_BY_USFM: Dict[str, BookSpec] = {b.usfm_code: b for b in BOOKS}


def get_books_for_language(language: str) -> List[BookSpec]:
    lang = language.lower()
    if lang == "hebrew":
        # Note: User can also upload Hebrew Ben Sira (Sirach) or Dead Sea Scrolls for other books!
        return [b for b in BOOKS if b.has_hebrew or b.slug == "sirach"]
    if lang == "latin":
        return [b for b in BOOKS if b.has_latin]
    return [b for b in BOOKS if b.has_greek]
