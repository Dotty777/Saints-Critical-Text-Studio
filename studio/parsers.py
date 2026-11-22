"""Multi-Format Biblical Witness Parsers & Future-Upload Auto-Detector.

Every parser reads a whole book once and returns ``{chapter: {verse: text}}``; results are
cached per process (keyed on the file's modification time), so collating a chapter can also
look at the neighbouring chapters of every witness when it re-aligns verse numbering.

Conventions shared by all parsers
---------------------------------
* Text is NFC-normalised with collapsed whitespace.
* ``VERSE_ABSENT`` (an empty string) means the witness is extant at this point but
  deliberately lacks the verse (CNTR "-" lines, e.g. Mark 16:9–20 in Sinaiticus and
  Vaticanus). A verse that is simply missing from the dictionary means the witness is not
  extant there (lacuna, book not present) and casts no vote.
* ``LACUNA_MARK`` ("…") stands where a manuscript has lost text inside a verse; the
  collator treats that witness's apparent omissions in the verse as non-evidence.
* Verses an edition prints inside double brackets as later additions (SBLGNT ⟦ ⟧) keep the
  brackets around the whole verse so the collator can count them as "absent" votes.
"""

from __future__ import annotations
import csv
import functools
import html
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .catalog import BookSpec, GREEK_RESEARCH_ROOT, LATIN_TRANSLATION_ROOT, STUDIO_ROOT, research_root

BookText = Dict[int, Dict[int, str]]

VERSE_ABSENT = ""
LACUNA_MARK = "…"
DOUBTFUL_OPEN, DOUBTFUL_CLOSE = "⟦", "⟧"

# OSIS book ID map for MAPM_Masorah.xml and general OSIS files
OSIS_TO_USFM = {
    "Gen": "GEN", "Exod": "EXO", "Lev": "LEV", "Num": "NUM", "Deut": "DEU",
    "Josh": "JOS", "Judg": "JDG", "Ruth": "RUT", "1Sam": "1SA", "2Sam": "2SA",
    "1Kgs": "1KI", "2Kgs": "2KI", "1Chr": "1CH", "2Chr": "2CH", "Ezra": "EZR",
    "Neh": "NEH", "Esth": "EST", "Job": "JOB", "Ps": "PSA", "Prov": "PRO",
    "Eccl": "ECC", "Song": "SNG", "Isa": "ISA", "Jer": "JER", "Lam": "LAM",
    "Ezek": "EZK", "Dan": "DAN", "Hos": "HOS", "Joel": "JOL", "Amos": "AMO",
    "Obad": "OBA", "Jonah": "JON", "Mic": "MIC", "Nah": "NAM", "Hab": "HAB",
    "Zeph": "ZEP", "Hag": "HAG", "Zech": "ZEC", "Mal": "MAL",
    "Matt": "MAT", "Mark": "MRK", "Luke": "LUK", "John": "JHN", "Acts": "ACT",
    "Rom": "ROM", "1Cor": "1CO", "2Cor": "2CO", "Gal": "GAL", "Eph": "EPH",
    "Phil": "PHP", "Col": "COL", "1Thess": "1TH", "2Thess": "2TH",
    "1Tim": "1TI", "2Tim": "2TI", "Titus": "TIT", "Phlm": "PHM", "Heb": "HEB",
    "Jas": "JAS", "1Pet": "1PE", "2Pet": "2PE", "1John": "1JN", "2John": "2JN",
    "3John": "3JN", "Jude": "JUD", "Rev": "REV",
}
USFM_TO_OSIS = {v: k for k, v in OSIS_TO_USFM.items()}

# Swete's and Brenton's "2 Esdras" files hold Ezra (ch. 1–10) and Nehemiah (ch. 11–23).
_ESDRAS_B_EZRA_LAST_CHAPTER = 10


def norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def _mtime_key(path: Path) -> Tuple[str, int]:
    try:
        return str(path), path.stat().st_mtime_ns
    except OSError:
        return str(path), 0


@functools.lru_cache(maxsize=64)
def _read_text_cached(path_str: str, _mtime: int) -> str:
    return Path(path_str).read_text(encoding="utf-8", errors="replace")


def read_text(path: Path) -> str:
    return _read_text_cached(*_mtime_key(path))


def clear_caches() -> None:
    _read_text_cached.cache_clear()
    _load_book_cached.cache_clear()
    _nestle_index.cache_clear()
    _wlc_index.cache_clear()
    _mam_index.cache_clear()
    _usfx_index.cache_clear()
    _swete_csv_index.cache_clear()
    _scrivener_json_index.cache_clear()
    _scrollmapper_csv_index.cache_clear()
    _tischendorf_osis_index.cache_clear()
    _intf_ntvmr_index.cache_clear()
    _compaul_latin_index.cache_clear()
    _bensira_tei_index.cache_clear()
    _rahlfs_csv_index.cache_clear()
    _sinaiticus_tei_index.cache_clear()
    _tagnt_edition_index.cache_clear()
    _tregelles_txt_index.cache_clear()
    _bhsa_tf_index.cache_clear()
    _samaritan_tf_index.cache_clear()
    _dss_tf_index.cache_clear()
    _vl_john_synopsis_index.cache_clear()


def _split_2esdras(book: BookSpec, chapters: BookText, offset: int) -> BookText:
    """Map a shared 2 Esdras file onto Ezra (1–10) or Nehemiah (11–23 → 1–13)."""
    if offset:
        return {c - offset: v for c, v in chapters.items() if c > offset}
    if book.slug == "ezra":
        return {c: v for c, v in chapters.items() if c <= _ESDRAS_B_EZRA_LAST_CHAPTER}
    return chapters


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def resolve_corpus_path(path: Path) -> Path:
    """Resolve any witness path (including legacy external or pre-rebrand paths) to its current
    self-contained home inside Saints-Critical-Text-Studio."""
    if path.exists():
        return path
    parts = path.parts
    for i, part in enumerate(parts):
        m = re.fullmatch(r"(?:Saints|Gemini)-(Greek|Hebrew|Latin)-(?:Research-Texts|Critical-Text)", part)
        if m:
            moved = research_root(m.group(1)).joinpath(*parts[i + 1:])
            if moved.exists():
                return moved
        if part == "Latin-Translation":
            moved_lat = LATIN_TRANSLATION_ROOT.joinpath(*parts[i + 1:])
            if moved_lat.exists():
                return moved_lat
        if part in ("Gemini-Critical-Text-Studio", "Saints-Critical-Text-Studio"):
            moved_st = STUDIO_ROOT.joinpath(*parts[i + 1:])
            if moved_st.exists():
                return moved_st
    return path


def load_book_from_witness(witness_row: Dict[str, object], book: BookSpec) -> BookText:
    """Return ``{chapter: {verse: text}}`` for one witness and book (cached)."""
    kind = str(witness_row["parser_kind"])
    base_path = resolve_corpus_path(Path(str(witness_row["file_path"])))
    if kind == "quarantined" or not base_path.exists():
        return {}
    path_str, mtime = _mtime_key(base_path)
    return _load_book_cached(kind, path_str, mtime, book)


def load_chapter_from_witness(
    witness_row: Dict[str, object],
    book: BookSpec,
    chapter: int,
) -> Dict[int, str]:
    """Return ``{verse: text}`` for a single witness, book, and chapter (absent verses = "")."""
    return dict(load_book_from_witness(witness_row, book).get(chapter, {}))


@functools.lru_cache(maxsize=512)
def _load_book_cached(kind: str, path_str: str, _mtime: int, book: BookSpec) -> BookText:
    base_path = Path(path_str)
    if kind == "swete_clean":
        return _parse_swete_clean(base_path, book)
    if kind == "first1k_tei":
        return _parse_first1k_tei(base_path, book)
    if kind == "swete_csv":
        abbr = SWETE_CSV_BOOKS.get(book.slug)
        return _swete_csv_index(*_mtime_key(base_path / SWETE_CSV_WORDS)).get(abbr, {}) if abbr else {}
    if kind == "brenton_usfm":
        if not book.brenton_file:
            return {}
        return _split_2esdras(book, parse_usfm_book(base_path / book.brenton_file, drop_square_brackets=True),
                              book.brenton_chapter_offset)
    if kind == "cntr_edition":
        return _parse_cntr_file(base_path, book.cntr_book, clean=_clean_cntr_edition_line) if book.cntr_book else {}
    if kind == "cntr_mss":
        return _parse_cntr_file(base_path, book.cntr_book, clean=clean_cntr_mss_line) if book.cntr_book else {}
    if kind == "sblgnt_txt":
        return _parse_sblgnt_txt(base_path / f"{book.sbl_code}.txt") if book.sbl_code else {}
    if kind == "nestle_csv":
        return _nestle_index(*_mtime_key(base_path)).get(book.sbl_code or "", {}) if book.sbl_code else {}
    if kind == "rp_csv":
        return _parse_rp_csv(base_path / f"{book.rp_code}.csv") if book.rp_code else {}
    if kind == "wlc_tsv":
        return _wlc_index(*_mtime_key(base_path)).get(book.usfm_code, {})
    if kind == "mam_osis":
        return _mam_index(*_mtime_key(base_path)).get(book.usfm_code, {})
    if kind == "usfx_xml":
        return _usfx_index(*_mtime_key(base_path)).get(book.usfm_code, {})
    if kind == "latin_saints_json":
        return _parse_latin_saints_json(base_path / book.slug / "verses.json")
    if kind == "amiatinus_tei":
        return _parse_amiatinus_tei(base_path, book)
    if kind == "ebible_usfm_dir":
        return _parse_ebible_usfm_dir(base_path, book)
    if kind == "ebible_hebrew_usfm_dir":
        return _parse_ebible_hebrew_usfm_dir(base_path, book)
    if kind == "scrivener_json":
        return _scrivener_json_index(*_mtime_key(base_path)).get(book.usfm_code, {})
    if kind == "letteris_utf8":
        return _parse_letteris_book(base_path, book)
    if kind == "scrollmapper_csv":
        return _scrollmapper_csv_index(*_mtime_key(base_path)).get(book.usfm_code, {})
    if kind == "tischendorf_osis":
        return _tischendorf_osis_index(*_mtime_key(base_path)).get(book.usfm_code, {})
    if kind == "intf_ntvmr_xml":
        return _parse_intf_ntvmr_book(base_path, book)
    if kind == "igntp_paul_xml":
        return _parse_igntp_paul_xml(base_path, book)
    if kind == "compaul_latin_tei":
        return _parse_compaul_latin_tei(base_path, book)
    if kind == "bensira_tei":
        if book.slug != "sirach":
            return {}
        return _bensira_tei_index(*_mtime_key(base_path))
    if kind == "rahlfs_csv":
        return _rahlfs_csv_index(*_mtime_key(base_path)).get(book.usfm_code, {})
    if kind == "sinaiticus_tei":
        return _sinaiticus_tei_index(*_mtime_key(base_path)).get(book.usfm_code, {})
    if kind == "first1k_og_daniel":
        return _parse_first1k_og_daniel(base_path, book)
    if kind == "ottley_isaiah":
        if book.slug != "isaiah":
            return {}
        raw_bk = _parse_swete_clean(base_path, book)
        return {
            ch: {v: norm_ws(re.sub(r"[<>]", "", t)) for v, t in vs.items() if norm_ws(re.sub(r"[<>]", "", t))}
            for ch, vs in raw_bk.items()
        }
    if kind == "tagnt_na28":
        return _tagnt_edition_index(*_mtime_key(base_path), "NA28").get(book.usfm_code, {})
    if kind == "tagnt_thgnt":
        return _tagnt_edition_index(*_mtime_key(base_path), "Tyn").get(book.usfm_code, {})
    if kind == "tregelles_txt":
        return _tregelles_txt_index(*_mtime_key(base_path)).get(book.usfm_code, {})
    if kind == "elzevir_uel":
        return _parse_elzevir_uel(base_path, book)
    if kind == "bhsa_tf":
        return _bhsa_tf_index(*_mtime_key(base_path)).get(book.usfm_code, {})
    if kind == "samaritan_tf":
        return _samaritan_tf_index(*_mtime_key(base_path)).get(book.usfm_code, {})
    if kind.startswith("dss_"):
        return _parse_dss_scroll(base_path, kind, book)
    if kind.startswith("vl_john_"):
        if book.slug != "john":
            return {}
        return _vl_john_synopsis_index(*_mtime_key(base_path)).get(kind[len("vl_john_"):], {})
    if kind == "divinum_psalter":
        if book.slug != "psalms":
            return {}
        return _parse_divinum_psalter(base_path)
    if kind == "custom_auto":
        return parse_custom_witness_book(base_path, book)
    return {}


# ---------------------------------------------------------------------------
# Greek Old Testament
# ---------------------------------------------------------------------------

_SUFFIXED_VERSE = re.compile(r"(\d+)([A-Za-z]+\d*)")  # Swete's 9a, 35I, 11s, and Esther's "1a1" (= C11)
_CONTINUES_PREVIOUS = "+"  # pseudo verse id: words that continue the verse written before them
# Books whose First1K chapters open with a title outside the verse divs (checked over every book; elsewhere
# such text is the end of the previous chapter, e.g. Job 16, Song of Songs 7).
_CHAPTER_TITLE_BOOKS = frozenset({"psalms", "isaiah", "lamentations", "obadiah"})


def _parse_swete_clean(data_dir: Path, book: BookSpec) -> BookText:
    """Swete (via First1KGreek) one-word-per-line files: ``book.chapter.verse word``.

    Suffixed verses (Job 2:9a–d, 3 Kingdoms 2:35a–o …) and Esther's Additions are placed by
    ``_place_swete_verses``, so the pluses Swete prints are kept."""
    if not book.swete_file:
        return {}
    fp = data_dir / book.swete_file
    if not fp.exists():
        return {}
    pieces: List[Tuple[str, str, List[str]]] = []  # (chapter id, verse id, words) in file order
    for line in read_text(fp).splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) < 2:
            continue
        ref = parts[0].split(".")
        if len(ref) < 3:
            continue
        if pieces and pieces[-1][0] == ref[1] and pieces[-1][1] == ref[2]:
            pieces[-1][2].append(parts[1])
        else:
            pieces.append((ref[1], ref[2], [parts[1]]))
    seq = [
        (ch_id, v_id, _clean_swete_piece(norm_ws(" ".join(ws).replace("•", "·")), ch_id, v_id))
        for ch_id, v_id, ws in pieces
    ]
    return _split_2esdras(book, _place_swete_verses(seq, book), book.swete_chapter_offset)


def _esther_addition_slot(ch_id: str, v_id: str) -> Optional[Tuple[int, int]]:
    """Where Brenton (the Greek OT versification anchor) prints the Esther Additions that Swete
    numbers in a series of their own. Additions B, C and E (Swete 3:1a–7a, 4:1a–30a, 8:1a–24a,
    printed after 3:13, 4:17 and 8:12) are placed by the general rule in ``_place_swete_verses``."""
    if ch_id == "prologue":  # Addition A (A1–17): Brenton 1:1, 1b–1r, before the canonical 1:1 (Brenton 1s)
        return 1, 1
    m = re.fullmatch(r"(\d+)b", v_id)
    if ch_id == "4" and m:  # Addition D (D1–16): Brenton 5:1, 1a–1f (D1–11) and 5:2, 2a–2b (D12–16)
        return 5, (1 if int(m.group(1)) <= 11 else 2)
    if ch_id == "10" and v_id.isdigit():  # Addition F (F1–11) = Brenton 10:3a–3l; Swete prints 10:1–3 as 1a–3a
        return 10, 3
    return None


def _place_swete_verses(seq: List[Tuple[str, str, str]], book: BookSpec) -> BookText:
    """Assign Swete/First1K pieces ``(chapter id, verse id, text)``, in document order, to verses.

    A plain verse id keeps its number. A suffixed id (2:9a) is added to its base verse, as
    ``parse_usfm_book`` folds Brenton's ``\\v 9a`` into 9, with two exceptions that keep the words
    where Swete prints them: a suffixed id whose base lies *behind* the verse just written starts a
    run that stays with that verse (Swete's own series for an addition, e.g. Esther 3:1a–7a after
    3:13, or a displaced half-verse such as Sirach 7:16b after 7:17a, which Brenton prints as 7:17a);
    and a base at or beyond the next plain verse is a misprint (Proverbs 25 "29a" between 20 and 21
    is 20a). A non-numeric verse id ("head" in Isaiah 32: the end of 31:9 printed above the chapter
    number) or ``_CONTINUES_PREVIOUS`` continues the verse written before it."""
    special = [_esther_addition_slot(ch_id, v_id) if book.slug == "esther" else None for ch_id, v_id, _t in seq]
    next_plain: List[Optional[int]] = [None] * len(seq)
    upcoming: Dict[str, int] = {}
    for i in range(len(seq) - 1, -1, -1):
        next_plain[i] = upcoming.get(seq[i][0])
        if seq[i][1].isdigit() and special[i] is None:
            upcoming[seq[i][0]] = int(seq[i][1])
    verses: Dict[int, Dict[int, List[str]]] = {}
    last: Optional[Tuple[int, int]] = None  # the verse most recently written, in any chapter
    held: List[str] = []  # continuation text met before any verse: it goes in front of the next one
    cur_ch: Optional[str] = None
    cur: Optional[int] = None  # the verse most recently written in the current chapter
    run = False
    prev: Optional[Tuple[int, int]] = None  # the previous chapter's last verse
    for i, (ch_id, v_id, text) in enumerate(seq):
        if ch_id != cur_ch:
            prev = (int(cur_ch), cur) if cur_ch is not None and cur_ch.isdigit() and cur is not None else None
            cur_ch, cur, run = ch_id, None, False
        slot = special[i]
        if slot is None:
            m = _SUFFIXED_VERSE.fullmatch(v_id)
            if not (v_id.isdigit() or m):
                if last is not None:
                    verses[last[0]][last[1]].append(text)
                else:
                    held.append(text)
                continue
            base = int(v_id) if v_id.isdigit() else int(m.group(1))
            if not ch_id.isdigit() or int(ch_id) < 1 or base < 1:
                continue  # deliberately skipped: prologues (Sirach 0.0) and Odes' "iva"/"ivb" are not verses
            if v_id.isdigit() and cur is None and prev and base == prev[1] > 1 and book.slug not in _CHAPTER_TITLE_BOOKS:
                # Swete Clean's form of the same continuation: the end of the previous chapter's last verse,
                # labelled with that verse's number at the head of the next chapter (Job 16 "35", Song 7 "12")
                verses[prev[0]][prev[1]].append(text)
                last = prev
                continue
            if v_id.isdigit():
                v, run = base, False
            elif cur is not None and (run or base < cur or (next_plain[i] is not None and base >= next_plain[i])):
                v, run = cur, run or base < cur
            else:
                v = base
            slot = (int(ch_id), v)
        bucket = verses.setdefault(slot[0], {}).setdefault(slot[1], [])
        if held:
            bucket.extend(held)
            held = []
        bucket.append(text)
        last = slot
        if str(slot[0]) == ch_id:
            cur = slot[1]
    out: BookText = {}
    for ch, vs in verses.items():
        for v, texts in vs.items():
            joined = _attach_free_punct(norm_ws(" ".join(texts)))
            if joined:
                out.setdefault(ch, {})[v] = joined
    return out


# Characters built with chr(): NFC would fold the ano teleia and Greek question mark into '·' and ';', and
# combining accents are invisible in source.
_PUNCT_CLASS = chr(0xB7) + chr(0x387) + ";" + chr(0x37E) + ",.:!?"
_GREEK_CHARS = chr(0x370) + "-" + chr(0x3FF) + chr(0x1F00) + "-" + chr(0x1FFF)
_COMBINING = chr(0x300) + "-" + chr(0x36F)
_SWETE_JUNK = re.compile(
    r"[’'‘ʼ᾽][^\s’'‘ʼ᾽]?[’'‘ʼ᾽]?"       # stray marginal marks such as ’φ’
    r"|\*?\(?[0-9][0-9,]*\)?|[⁰¹²³⁴⁵⁶⁷⁸⁹]+"   # inline verse numbers: 13, (13), (5,6), *30, ²⁵
    r"|[ᵃᵇᶜᵈᵉ]+"                              # a sub-verse letter standing alone ('ᵃ ὥραν', Job 36:28a)
    r"|\(\?\?\)|[|+¶*]+|bb"                 # sigla and markup residue (a lone * stands in 3 Kgdms 2:35a–o)
    rf"|[IVXLC]+[{_PUNCT_CLASS}]?"          # a bare chapter numeral (XXVIII before Gen 28) or margin mark: never Greek
)
# Inline verse numbers in parentheses anywhere in a verse: '(22)εἰς', '(17b-19)', 'Ἰακώβ,(26)καὶ', '⁽2)καὶ',
# and the orphan ',23)' or '()' left where the opening part or a superscript digit was lost.
_INLINE_VERSE_NO = re.compile(r"[(⁽]{1,2}(?:\d+[a-z]?(?:[,\-–]\d+[a-z]?)*)?[)⁾]|(?<!\S),?\d+[a-z]?[)⁾]")
_ROMAN_DIGITS = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def _roman_value(numeral: str) -> int:
    vals = [_ROMAN_DIGITS[c] for c in numeral]
    return sum(-v if i + 1 < len(vals) and vals[i + 1] > v else v for i, v in enumerate(vals))


def _clean_swete_piece(text: str, ch_id: str, v_id: str) -> str:
    """Clean one Swete/First1K verse or sub-verse, knowing the source's own chapter and verse ids."""
    m = _SUFFIXED_VERSE.fullmatch(v_id)
    if m:
        # the sub-verse letter printed before the first word: 'aὥσπερ' (Prov 25:20a), 'a Κἀγὼ' (Sir 33:16a),
        # 'a ¹⁶aἐκ' (Prov 3:16a), and a Greek look-alike standing alone ('α ἐν ταῖς', 2 Chr 36:5a)
        letter = m.group(2)[0].lower()
        alike = {"a": "α", "b": "β"}.get(letter, letter)
        text = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹ᵃᵇ]+(?=\S)", "", text)
        text = re.sub(rf"^(?:[{letter}{alike}]\s+|{letter})+(?=[{_GREEK_CHARS}])", "", text)
    # a non-numeric id (Isaiah 32 "head", a continuation) stands before verse 1 of its chapter
    verse = int(v_id) if v_id.isdigit() else int(m.group(1)) if m else 0
    return _attach_punct(text, int(ch_id) if ch_id.isdigit() else None, verse)


def _clean_swete_token(t: str, at_start: bool, at_end: bool, chapter: Optional[int], verse: Optional[int]) -> str:
    """OCR residue inside one token: a Latin o for omicron, chapter numerals and verse numbers glued to a word."""
    if re.search(f"[{_GREEK_CHARS}]", t):
        t = t.replace("o", "ο").replace("O", "Ο")  # Latin o among Greek letters is an OCR omicron ('oἱ', '20oὐ')
    if chapter is not None:
        # the chapter numeral glued to the first word of the chapter or the last word before it ('IXκαὶ' at 9:1,
        # 'καταIX' at 8:22); other Latin capitals stand for Greek letters ('Xανάαν', Joshua 14:1) and are left alone
        for pat, here in ((rf"^([IVXLC]+)(?=[{_GREEK_CHARS}])", at_start),
                          (rf"(?<=[{_GREEK_CHARS}{_COMBINING}])([IVXLC]+)$", at_end)):
            g = re.search(pat, t) if here else None
            if g and _roman_value(g.group(1)) in (chapter, chapter + 1):
                # The OCR often lost words where the chapter numeral stood: leave a lacuna mark, which the
                # engine removes again if those words turn up in the neighbouring verse.
                t = (LACUNA_MARK + " " + t[g.end():]) if g.start() == 0 else (t[: g.start()] + " " + LACUNA_MARK)
    g = re.match(rf"(\d+)(?=[{_GREEK_CHARS}])", t)
    if g and verse is not None:
        own, nxt = str(verse), str(verse + 1)
        # a verse number glued to a word ('20οὐ', '8Ἐξομολογεῖσθε'), sometimes without its first digit ('9ἰδοὺ'
        # for 19); at the start of a verse any digits are its number. Other digits are OCR letters ('2διήλ').
        if at_start or g.group(1) in (own, nxt) or (len(g.group(1)) < len(nxt) and nxt.endswith(g.group(1))):
            t = t[g.end():]
    g = re.search(rf"(?<=[{_PUNCT_CLASS}])(\d+)$", t)  # the next verse number glued after the last word: 'ἡμῖν;43'
    if g and verse is not None and g.group(1) in (str(verse), str(verse + 1)):
        t = t[: g.start()]
    return t


def _attach_punct(text: str, chapter: Optional[int] = None, verse: Optional[int] = None) -> str:
    """Clean a Swete/First1KGreek verse: attach free-standing punctuation ("οὐρανοῦ · καὶ"),
    drop OCR residue (’φ’, inline verse numbers, chapter numerals, ¶, |, +), strip superscript numbers
    glued to words, and restore καί where only the "κα" of the καί compendium survived the OCR.
    ``chapter`` and ``verse`` (the source's own numbers) let numbers glued to words be recognised."""
    text = text.replace("¶", " ").replace("̣", "")  # a dot below a letter is OCR noise in these prints
    text = re.sub(r"(?<=\S)[⁰¹²³⁴⁵⁶⁷⁸⁹ᵃᵇ]+|[⁰¹²³⁴⁵⁶⁷⁸⁹ᵃᵇ]+(?=\S)", "", text)
    text = _INLINE_VERSE_NO.sub(" ", text)
    toks: List[str] = []
    raw_toks = text.split()
    for i, raw_tok in enumerate(raw_toks):
        t = _clean_swete_token(raw_tok, not toks, i == len(raw_toks) - 1, chapter, verse)
        bare = re.fullmatch(rf"([IVXLC]+)[{_PUNCT_CLASS}]?", t or "")
        if (bare and chapter is not None and _roman_value(bare.group(1)) in (chapter, chapter + 1)
                and (not toks or i == len(raw_toks) - 1)):
            toks.append(LACUNA_MARK)  # a chapter numeral at the edge of a verse: words may be lost there
            continue
        if t and not _SWETE_JUNK.fullmatch(t):
            toks.append(t)
    for i, t in enumerate(toks):
        nxt = toks[i + 1] if i + 1 < len(toks) else ""
        nxt_base = "".join(c for c in unicodedata.normalize("NFD", nxt.lower()) if unicodedata.category(c) != "Mn")
        nxt_core = re.sub(r"[^\w]", "", nxt_base)
        if t in ("κα", "Κα") and nxt_core == "ι":  # a split καί ('κα ὶ', Gen 38:14) is one word
            toks[i] = ("καὶ" if t == "κα" else "Καὶ") + re.sub(rf"^[^\W\d_]+[{_COMBINING}]*", "", nxt)
            toks[i + 1] = ""
        elif t in ("κα", "Κα") and nxt and nxt_core != "και" and re.search(r"[αεηιουω]", nxt_core):
            toks[i] = "καὶ" if t == "κα" else "Καὶ"  # (κα before καί or a vowel-less fragment = text lost: leave it)
    return _attach_free_punct(" ".join(t for t in toks if t))


def _attach_free_punct(text: str) -> str:
    return re.sub(r"\s+([··;;,.:!?])(?=\s|$)", r"\1", text)


def _tei_text_without_notes(elem: ET.Element) -> str:
    """Concatenate an element's text, skipping <note> subtrees but keeping their tails."""
    chunks: List[str] = []

    def walk(e: ET.Element) -> None:
        if e.text:
            chunks.append(e.text)
        for child in e:
            if child.tag.split("}")[-1] != "note":
                walk(child)
            if child.tail:
                chunks.append(child.tail)

    walk(elem)
    return " ".join(chunks)


def _parse_first1k_tei(tlg_dir: Path, book: BookSpec) -> BookText:
    if not book.tlg_work:
        return {}
    work_dir = tlg_dir / book.tlg_work
    xml_file = _swete_tei_file(work_dir) if work_dir.exists() else None
    if not xml_file:
        return {}
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}
    try:
        root = ET.fromstring(read_text(xml_file).encode("utf-8"))
    except ET.ParseError:
        return {}

    def clean(raw_txt: str, ch_id: str, v_id: str) -> str:
        # § marks a section start and [ ] enclose letters the transcriber supplied; keep the letters.
        # NFC first, so an accent stored as a combining mark does not stop the join below ('βού-\nτυρον').
        raw_txt = unicodedata.normalize("NFC", raw_txt.replace("•", "·").replace("§", " "))
        # A word broken across a printed line ("κλη-<lb/> ρονομήσω", "θάλασ- ’σαν") is one word.
        raw_txt = re.sub(rf"(?<=[^\W\d_]|[{_COMBINING}])-\s+[’'‘ʼ᾽]?(?=[^\W\d_])", "", raw_txt)
        return _clean_swete_piece(norm_ws(re.sub(r"[\[\]]", "", raw_txt)), ch_id, v_id)

    seq: List[Tuple[str, str, str]] = []  # (chapter id, verse id, text) in document order
    verse_tag = "{http://www.tei-c.org/ns/1.0}div"
    for ch_div in root.findall(".//tei:div[@subtype='chapter']", ns):
        ch_str = ch_div.attrib.get("n", "")
        # Text before the first verse div. In Psalms, Isaiah's oracles, Lamentations and Obadiah it is a
        # title that Brenton prints in verse 1 (Psalm 14: <lg> after <head>); elsewhere it is the end of
        # the previous chapter's last verse printed after the chapter number (Job 16 holds the end of 15:35,
        # Song of Songs 7 the end of 6:12).
        prelude: List[str] = []
        for child in ch_div:
            tag = child.tag.split("}")[-1]
            if child.tag == verse_tag and child.attrib.get("subtype") == "verse":
                break
            if tag in ("lg", "p", "l", "ab"):
                prelude.append(_tei_text_without_notes(child))
        if prelude:
            title = book.slug in _CHAPTER_TITLE_BOOKS
            seq.append((ch_str, "1" if title else _CONTINUES_PREVIOUS,
                        clean(" ".join(prelude), ch_str, "0" if title else _CONTINUES_PREVIOUS)))
        for v_div in ch_div.findall(".//tei:div[@subtype='verse']", ns):
            v_str = v_div.attrib.get("n", "")
            seq.append((ch_str, v_str, clean(_tei_text_without_notes(v_div), ch_str, v_str)))
    return _split_2esdras(book, _place_swete_verses(seq, book), book.swete_chapter_offset)


def _swete_tei_file(work_dir: Path) -> Optional[Path]:
    """First1KGreek sometimes holds two Greek editions of a book (Sirach: Hart's minuscule 248 and
    Swete; Isaiah: Swete and Ottley's Codex A). Pick the one whose header names Swete."""
    files = sorted(work_dir.glob("*.1st1K-grc*.xml"))
    for fp in files:
        if "Swete" in read_text(fp)[:30000]:
            return fp
    return files[0] if files else None


# Swete's edition in an independent transcription: Pasquale Amicarelli's text (first a BibleWorks module),
# published as CSV files by the LXX-Swete-1930 project (GPL-3.0). It is not OCR, so it does not share the
# misreadings of First1KGreek and Swete Clean, which are one OCR in two conversions.
SWETE_CSV_WORDS = "01-Swete_word_with_punctuations.csv"   # running index <TAB> word (with punctuation)
SWETE_CSV_VERSES = "00-Swete_versification.csv"          # index of a verse's first word <TAB> Book.ch:v
# Its book abbreviations → catalogue slugs. Daniel is Theodotion ("Dat"; "Dan" is the Old Greek), as for the
# other Swete copies. Ezra and Nehemiah are separate books here (no 2 Esdras offset). Left out: books outside
# the catalogue, Swete's Old Greek Daniel and Susanna/Bel, and Sirach's prologue ("Sip"), which the other Swete
# copies skip too.
SWETE_CSV_BOOKS = {
    "genesis": "Gen", "exodus": "Exo", "leviticus": "Lev", "numbers": "Num", "deuteronomy": "Deu",
    "joshua": "Jos", "judges": "Jdg", "ruth": "Rut", "1-samuel": "1Sa", "2-samuel": "2Sa", "1-kings": "1Ki",
    "2-kings": "2Ki", "1-chronicles": "1Ch", "2-chronicles": "2Ch", "ezra": "Ezr", "nehemiah": "Neh",
    "esther": "Est", "1-maccabees": "1Ma", "2-maccabees": "2Ma", "job": "Job", "psalms": "Psa",
    "proverbs": "Pro", "ecclesiastes": "Ecc", "song-of-songs": "Sol", "lamentations": "Lam",
    "wisdom-of-solomon": "Wis", "sirach": "Sir", "isaiah": "Isa", "jeremiah": "Jer", "ezekiel": "Eze",
    "daniel": "Dat", "hosea": "Hos", "joel": "Joe", "amos": "Amo", "obadiah": "Oba", "jonah": "Jon",
    "micah": "Mic", "nahum": "Nah", "habakkuk": "Hab", "zephaniah": "Zep", "haggai": "Hag",
    "zechariah": "Zec", "malachi": "Mal",
}
# Not words: the sub-verse numbers Swete prints inside a verse ("[1]" = 2:35a, "[2]" = 2:35b …, folded into
# the verse as Brenton's \v 35a is) and the transcription's editorial signs ⸂ ⸃ ⸆.
_SWETE_CSV_MARKS = re.compile(r"\[\d+[a-z]?\]|[⸂⸃⸆]")
# Places where the transcription numbers and orders verses as Rahlfs does, not as Swete prints them: (book, chapter,
# verse) → the verse they are appended to, in this order. Theodotion's Dan 3: Swete prints ψῦχος καὶ καῦμα and
# πάχνη καὶ χιόνες after φῶς καὶ σκότος (3:72; Brenton's 72a–b), the transcription before νύκτες (3:69–70).
_SWETE_CSV_MOVES = {("Dat", 3, 69): (3, 72), ("Dat", 3, 70): (3, 72)}
# Words the transcription marks ⸂ ⸃ and prints at Rahlfs's place, where Swete prints them in another verse: the
# marked span is moved there. Jer 10:5b ("αἰρόμενα ἀρθήσονται … ἐν αὐτοῖς") stands after 10:9 in Swete (B), as in
# First1KGreek, Swete Clean and, for its second half, Brenton.
_SWETE_CSV_SPAN_MOVES = {("Jer", 10, 5): (10, 9)}


@functools.lru_cache(maxsize=2)
def _swete_csv_index(words_path: str, _mtime: int) -> Dict[str, BookText]:
    """The Swete CSV pair → ``{book abbreviation: {chapter: {verse: text}}}``.

    Its numbering is Swete's: suffixed verses are folded into their base verse (Job 2:9 holds 9a–d, Esther 3:13
    holds Addition B) and Sirach 30–36 stand in the conventional order, so Brenton and this text number alike
    almost everywhere; Joel, Malachi and Proverbs 24–31 differ and are re-aligned by content like the other
    copies. Square brackets enclose letters Swete supplies where Alexandrinus is damaged (Genesis): the
    letters are kept, as in First1KGreek. Verses the transcription leaves empty (Swete prints the number with
    no text, e.g. 1 Sam 17:12–31, Jer 10:6–8 — B lacks them — or a numbering gap) are left out: like the
    silence of the other Swete copies, they cast no vote."""
    fp = Path(words_path)
    vfp = fp.with_name(SWETE_CSV_VERSES)
    if not fp.exists() or not vfp.exists():
        return {}
    words: List[str] = [""]  # 1-based running index
    with fp.open(encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            idx, _tab, word = line.rstrip("\r\n").partition("\t")
            if idx.strip().isdigit():
                n = int(idx)
                if n >= len(words):
                    words.extend([""] * (n + 1 - len(words)))
                words[n] = word
    starts: List[Tuple[int, str, int, int]] = []
    with vfp.open(encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            idx, _tab, ref = line.rstrip("\r\n").partition("\t")
            m = re.fullmatch(r"([1-4]?[A-Za-z]+)\.(\d+):(\d+)", ref.strip())
            if idx.strip().isdigit() and m:
                starts.append((int(idx), m.group(1), int(m.group(2)), int(m.group(3))))
    starts.sort()
    wanted = set(SWETE_CSV_BOOKS.values())
    out: Dict[str, BookText] = {}
    moved_spans: List[Tuple[str, Tuple[int, int], str]] = []
    for k, (first, abbr, ch, v) in enumerate(starts):
        if abbr not in wanted:
            continue
        last = starts[k + 1][0] if k + 1 < len(starts) else len(words)
        raw = " ".join(w for w in words[first:last] if w)
        if (abbr, ch, v) in _SWETE_CSV_SPAN_MOVES:
            span = re.search(r"⸂([^⸃]*)⸃", raw)
            if span:
                moved_spans.append((abbr, _SWETE_CSV_SPAN_MOVES[(abbr, ch, v)], span.group(1)))
                raw = raw[: span.start()] + " " + raw[span.end():]
        raw = _SWETE_CSV_MARKS.sub(" ", unicodedata.normalize("NFC", raw))
        # a space missing after punctuation between two words ('Σωφάρ,Γοθὸμ', Gen 36:11) is spacing, not a reading
        raw = re.sub(rf"(?<=[{_GREEK_CHARS}{_COMBINING}])([,.;·:{chr(0x387)}])(?=[{_GREEK_CHARS}])", r"\1 ", raw)
        text = _attach_free_punct(norm_ws(re.sub(r"[\[\]()]", "", raw)))
        if text:
            out.setdefault(abbr, {}).setdefault(ch, {})[v] = text
    for abbr, (tch, tv), span_text in moved_spans:
        span_text = _attach_free_punct(norm_ws(_SWETE_CSV_MARKS.sub(" ", unicodedata.normalize("NFC", span_text))))
        target = out.setdefault(abbr, {}).setdefault(tch, {})
        target[tv] = (target.get(tv, "") + " " + span_text).strip()
    for (abbr, ch, v), (tch, tv) in sorted(_SWETE_CSV_MOVES.items()):
        moved = out.get(abbr, {}).get(ch, {}).pop(v, "")
        if moved and out[abbr].get(tch, {}).get(tv):
            out[abbr][tch][tv] += " " + moved
        elif moved:
            out[abbr][ch][v] = moved  # target missing: leave the verse where it was rather than lose it
    return out


_USFM_DROP_LINES = re.compile(r"^\\(?:id|ide|h|toc\d*|mt\d*|ms\d*|mr|r|s\d*|sr|ip|is\d*|io\d*|imt\d*|rem|cl|sp|sts)\b.*$", re.M)


def _move_heading_into_chapter(m: "re.Match[str]") -> str:
    """Brenton's USFM prints a chapter's capitalised Greek heading as the last paragraph of the
    previous chapter ('\\p ΤΟ ῬΗΜΑ ΤΟ ΚΑΤΑ ΔΑΜΑΣΚΟΥ.' just before '\\c 17' in Isaiah). Such an
    all-capitals Greek paragraph belongs to the chapter that follows: it is moved after the chapter
    marker, so it opens verse 1 there (as Swete prints it) instead of closing the previous verse."""
    text = m.group(1)
    greek = [c for c in text if "Ͱ" <= c <= "Ͽ" or "ἀ" <= c <= "῿"]
    letters = [c for c in greek if c.isalpha()]
    if len(letters) >= 4 and not any(c.islower() for c in letters):
        return f"{m.group(2)}\\p {text}\n"
    return m.group(0)


def _move_heading_into_verse(m: "re.Match[str]") -> str:
    """An all-capitals Greek '\\p' heading right before '\\v N' is printed at the start of verse N."""
    text = m.group(1)
    letters = [c for c in text if ("Ͱ" <= c <= "Ͽ" or "ἀ" <= c <= "῿") and c.isalpha()]
    if len(letters) >= 4 and not any(c.islower() for c in letters):
        return f"{m.group(2)}{text} "
    return m.group(0)


def parse_usfm_book(fp: Path, drop_square_brackets: bool = False) -> BookText:
    """Parse a USFM file into chapters and verses (footnotes, cross-refs and headings removed).

    ``drop_square_brackets`` removes an edition's editorial [ ] marks but keeps the words inside
    (Brenton brackets Proverbs 24:22a–e and Amos 2:3 "ἄρχοντας"; they are not part of the text)."""
    if not fp.exists():
        return {}
    raw = read_text(fp)
    if drop_square_brackets:
        raw = re.sub(r"[\[\]]", " ", raw)
    raw = re.sub(r"\\f\s.*?\\f\*", " ", raw, flags=re.DOTALL)
    raw = re.sub(r"\\x\s.*?\\x\*", " ", raw, flags=re.DOTALL)
    raw = re.sub(r"\\\+?w\s+([^|\\]+?)(?:\|[^\\]*)?\\\+?w\*", r"\1", raw)
    raw = _USFM_DROP_LINES.sub(" ", raw)
    raw = re.sub(r"\\p[ \t]+([^\\\n]+?)[ \t]*\n(\s*\\c\s+\d+[^\n]*\n)", _move_heading_into_chapter, raw)
    # the same inside a chapter: an all-capitals heading paragraph opens the verse that follows it
    # (Isa 21:11 'ΤΟ ὍΡΑΜΑ ΤΗΣ ἸΔΟΥΜΑΙΑΣ', Sirach's 'ἘΓΚΡΑΤΕΙΑ ΨΥΧΗΣ'), not the end of the one before
    raw = re.sub(r"\\p[ \t]+([^\\\n]+?)[ \t]*\n((?:[ \t]*\\p[ \t]*\n)*\s*\\v\s+\d+[a-z]?\s)", _move_heading_into_verse, raw)
    out: BookText = {}
    for ch_match in re.finditer(r"\\c\s+(\d+)(.*?)(?=\\c\s+\d+|\Z)", raw, flags=re.DOTALL):
        ch = int(ch_match.group(1))
        body = ch_match.group(2)
        pieces = re.split(r"\\v\s+(\d+)[a-z]?\s", body)
        preface = pieces[0]  # e.g. a psalm title given in \d before \v 1
        verses: Dict[int, List[str]] = {}
        for i in range(1, len(pieces) - 1, 2):
            verses.setdefault(int(pieces[i]), []).append(pieces[i + 1])
        title = norm_ws(re.sub(r"\\[a-z]+\d*\*?", " ", preface))
        if title and 1 in verses:
            verses[1].insert(0, title)
        cleaned = {
            v: norm_ws(re.sub(r"\\[a-z]+\d*\*?", " ", " ".join(parts)))
            for v, parts in verses.items()
        }
        out[ch] = {v: t for v, t in cleaned.items() if t}
    return out


def parse_usfm_chapter(fp: Path, chapter: int) -> Dict[int, str]:
    return parse_usfm_book(fp).get(chapter, {})


# ---------------------------------------------------------------------------
# Greek New Testament
# ---------------------------------------------------------------------------

def _parse_cntr_file(fp: Path, book_num: int, clean) -> BookText:
    """CNTR ``BBCCCVVV text`` files (editions and manuscript transcriptions)."""
    if not fp.exists():
        return {}
    prefix = f"{book_num:02d}"
    out: BookText = {}
    for line in read_text(fp).splitlines():
        if not line.startswith(prefix):
            continue
        parts = line.strip().split(" ", 1)
        ref = parts[0]
        if len(ref) != 8 or not ref.isdigit():
            continue
        ch, v = int(ref[2:5]), int(ref[5:8])
        body = parts[1].strip() if len(parts) > 1 else ""
        if body == "-":
            out.setdefault(ch, {})[v] = VERSE_ABSENT
            continue
        if body in ("", "+"):  # "+" alone = verse present but not transcribed
            continue
        cleaned = clean(body)
        if cleaned:
            out.setdefault(ch, {})[v] = cleaned
    return out


def _clean_cntr_edition_line(raw: str) -> str:
    # ¶ paragraph, ˚ nomen-sacrum flag, ¦ and ⋄ (alternate verse division), and $ numeral prefix are layout marks.
    return norm_ws(raw.replace("¶", " ").replace("˚", "").replace("¦", " ").replace("⋄", " ").replace("$", ""))


GAP_WORD = "[…]"  # one word known to be lost or unreadable at this point: casts no vote in its slot


_MES_GROUP = r"[xab]?\{[^{}]*\}"


def _resolve_mes_corrections(txt: str) -> str:
    """Keep the first hand in MES correction runs: ``x{orig} {corr} a{corr2}`` → ``orig``."""

    def keep_first(m: re.Match[str]) -> str:
        groups = re.findall(r"([xab]?)\{([^{}]*)\}", m.group(0))
        is_correction_run = len(groups) > 1 and (groups[0][0] == "x" or any(p in ("a", "b") for p, _ in groups[1:]))
        if is_correction_run:
            return " " + groups[0][1] + " "
        if len(groups) == 1 and groups[0][0] in ("a", "b"):
            return " "  # corrector-only insertion: not first-hand text
        return " ".join(body for _, body in groups)

    return re.sub(rf"{_MES_GROUP}(?:\s*{_MES_GROUP})*", keep_first, txt)


def clean_cntr_mss_line(raw: str) -> str:
    """Render a CNTR Manuscript Encoding Specification line as first-hand text.

    Nomina sacra keep their contraction with a combining overline (``ιυ̅``) and letter-numerals
    get the Greek numeral sign (``ιδʹ``); the collator recognises both. Lost text becomes "…".
    """
    txt = re.sub(r"\\\d*", "", raw)  # page breaks (\1186)
    txt = _resolve_mes_corrections(txt)
    txt = txt.replace("", "μου")  # CNTR's μου ligature (γα = γάμου, κοσ = κόσμου)
    txt = re.sub(r"~[^\s{}]+", f" {LACUNA_MARK} ", txt)  # words supplied by the editor (not extant)
    txt = re.sub(r"\S*�\S*", f" {GAP_WORD} ", txt)  # illegible word: a gap, not a reading
    txt = re.sub(r"[&*]", f" {LACUNA_MARK} ", txt)  # line / verse remnants in lacuna
    txt = re.sub(r"[0-9]", "", txt)  # stray section numbers
    txt = re.sub(r"[/|_⋄%^+\[\]]", "", txt)  # line/column breaks, damage & supply marks
    txt = txt.replace("¯", "ν")  # overline for final nu
    txt = txt.replace("ϗ", "και")  # kai compendium
    txt = re.sub(r"=([α-ωϲ]+)", lambda m: m.group(1) + "\u0305", txt)  # nomina sacra
    txt = re.sub(r"\$([α-ω]+)", lambda m: m.group(1) + "\u0374", txt)  # letter-numerals
    txt = txt.replace("$", "")
    txt = re.sub(rf"(?:\s*{LACUNA_MARK})+", f" {LACUNA_MARK}", txt)
    return norm_ws(txt)


# Kept for backwards compatibility with earlier imports.
_clean_cntr_mss_line = clean_cntr_mss_line

_SBLGNT_SIGLA = re.compile(r"[⸀⸁⸂⸃⸄⸅\[\]]")


def _apply_doubtful_brackets(ordered: List[Tuple[int, int, str]], open_tok: str, close_tok: str) -> BookText:
    """Resolve double brackets that an edition uses for later additions (SBLGNT ⟦ ⟧, Nestle [[ ]]).

    A verse lying wholly inside brackets is returned wrapped in ⟦ ⟧ (the collator counts it as
    an "absent" vote for that edition). Bracketed text inside an otherwise unbracketed verse —
    e.g. the Shorter Ending printed after Mark 16:8 — is dropped from that verse."""
    out: BookText = {}
    inside = False
    for ch, v, body in ordered:
        main: List[str] = []
        doubtful: List[str] = []
        for i, seg in enumerate(re.split(rf"({re.escape(open_tok)}|{re.escape(close_tok)})", body)):
            if seg == open_tok:
                inside = True
            elif seg == close_tok:
                inside = False
            elif seg.strip():
                (doubtful if inside else main).append(seg)
        main_txt, doubt_txt = norm_ws(" ".join(main)), norm_ws(" ".join(doubtful))
        if main_txt:
            out.setdefault(ch, {})[v] = main_txt
        elif doubt_txt:
            out.setdefault(ch, {})[v] = f"{DOUBTFUL_OPEN}{doubt_txt}{DOUBTFUL_CLOSE}"
    return out


def _parse_sblgnt_txt(fp: Path) -> BookText:
    """SBLGNT ``Book C:V<TAB>text`` files with apparatus sigla (⸀ ⸂ ⸃ …) removed."""
    if not fp.exists():
        return {}
    ordered: List[Tuple[int, int, str]] = []
    for line in read_text(fp).splitlines():
        m = re.match(r"^[1-3]?[A-Za-z]+\s+(\d+):(\d+)\t(.*)$", line.rstrip("\r\n"))
        if m:
            ordered.append((int(m.group(1)), int(m.group(2)), _SBLGNT_SIGLA.sub("", m.group(3))))
    return _apply_doubtful_brackets(ordered, DOUBTFUL_OPEN, DOUBTFUL_CLOSE)


def load_sblgnt_apparatus(sbl_code: Optional[str], chapter: int) -> Dict[int, List[str]]:
    if not sbl_code:
        return {}
    fp = GREEK_RESEARCH_ROOT / "01_Tier1_Modern_Critical_Open" / "NT_SBLGNT_Logos" / "data" / "sblgntapp" / "text" / f"{sbl_code}.txt"
    if not fp.exists():
        return {}
    notes: Dict[int, List[str]] = {}
    cur_v: Optional[int] = None
    for raw_line in read_text(fp).splitlines():
        line = raw_line.strip().replace("\xa0", " ")
        if not line:
            continue
        m_hdr = re.match(rf"^{chapter}:(\d+)\s+(.*)$", line)
        if m_hdr:
            cur_v = int(m_hdr.group(1))
            notes.setdefault(cur_v, []).append(norm_ws(m_hdr.group(2)))
        elif line.startswith("•") and cur_v is not None:
            notes.setdefault(cur_v, []).append(norm_ws(line.lstrip("• ")))
        elif re.match(r"^\d+:\d+\s+", line):
            cur_v = None
    return notes


@functools.lru_cache(maxsize=4)
def _nestle_index(path_str: str, _mtime: int) -> Dict[str, BookText]:
    """Nestle 1904 morphology CSV (one word per row) → {sbl_code: {ch: {v: text}}}.
    Mark 16:99 (the Shorter Ending, which Nestle prints after 16:8) is not a verse and is skipped."""
    fp = Path(path_str)
    if not fp.exists():
        return {}
    words: Dict[str, Dict[int, Dict[int, List[str]]]] = {}
    with fp.open(encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            cols = line.rstrip("\r\n").split("\t")
            if len(cols) < 2:
                continue
            m = re.match(r"^([1-3]?[A-Za-z]+) (\d+):(\d+)$", cols[0])
            if not m:
                continue
            ch, v = int(m.group(2)), int(m.group(3))
            if v >= 99:
                continue
            words.setdefault(m.group(1), {}).setdefault(ch, {}).setdefault(v, []).append(cols[1])
    out: Dict[str, BookText] = {}
    for b, chs in words.items():
        ordered = [
            (ch, v, " ".join(ws).replace("[[", " [[ ").replace("]]", " ]] "))
            for ch in sorted(chs) for v, ws in sorted(chs[ch].items())
        ]
        out[b] = _apply_doubtful_brackets(ordered, "[[", "]]")
    return out


def _parse_rp_csv(fp: Path) -> BookText:
    if not fp.exists():
        return {}
    out: BookText = {}
    for row in csv.DictReader(read_text(fp).splitlines()):
        try:
            ch, v = int(row.get("chapter") or 0), int(row.get("verse") or 0)
        except ValueError:
            continue
        txt = norm_ws((row.get("text") or "").replace("¶", " "))
        if ch and v and txt:
            out.setdefault(ch, {})[v] = txt
    return out


# ---------------------------------------------------------------------------
# Hebrew
# ---------------------------------------------------------------------------

# Paragraph markers (petuha/setuma) and the inverted nun are layout, not words.
_HEBREW_LAYOUT_TOKENS = {"פ", "ס", "׆", "{פ}", "{ס}", "{ש}", "{ר}"}


def _strip_hebrew_layout(text: str) -> str:
    text = re.sub(r"\{[פסשר]\}", " ", text)
    text = re.sub(r"\s*־\s*", "־", text)  # the WLC export has stray spaces around maqaf
    return " ".join(t for t in text.split() if t not in _HEBREW_LAYOUT_TOKENS)


@functools.lru_cache(maxsize=4)
def _wlc_index(path_str: str, _mtime: int) -> Dict[str, BookText]:
    fp = Path(path_str)
    if not fp.exists():
        return {}
    out: Dict[str, BookText] = {}
    for line in read_text(fp).splitlines():
        cols = line.split("\t", 3)
        if len(cols) == 4 and cols[1].isdigit() and cols[2].isdigit():
            # Inline Masoretic large/small/suspended letter tags ('l s="H..."'...'seg type="x-large"'ע'seg''/l')
            # wrap single letters inside a word: unwrap without spaces so the word is not split.
            raw_txt = re.sub(
                r"'?(?:l s=\"H[^\"]*\"|seg type=\"x-[a-z\-]+\"|</?seg[^>]*>|/l\b|\bseg\b)'?",
                "",
                cols[3],
            )
            txt = norm_ws(_strip_hebrew_layout(raw_txt))
            if txt:
                out.setdefault(cols[0], {}).setdefault(int(cols[1]), {})[int(cols[2])] = txt
    return out


@functools.lru_cache(maxsize=4)
def _mam_index(path_str: str, _mtime: int) -> Dict[str, BookText]:
    """MAM / OSIS milestone verses → {usfm: {ch: {v: text}}}.

    A ketiv is rendered in parentheses before its qere, as MAM prints it: ``(הוצא) הַיְצֵ֣א``.
    The collator compares the ketiv with witnesses that only carry the ketiv (the WLC export)."""
    fp = Path(path_str)
    if not fp.exists():
        return {}
    raw = read_text(fp)
    out: Dict[str, BookText] = {}
    pat = re.compile(
        r'<verse[^>]*\bosisID="([1-3]?[A-Za-z]+)\.(\d+)\.(\d+)"[^>]*/>(.*?)<verse[^>]*\beID="\1\.\2\.\3"\s*/>',
        re.DOTALL,
    )
    for m in pat.finditer(raw):
        usfm = OSIS_TO_USFM.get(m.group(1))
        if not usfm:
            continue
        v_xml = re.sub(r"<note\b.*?</note>", "", m.group(4), flags=re.DOTALL)
        # Large/small/suspended letters are inline <seg>s, sometimes nested inside a ketiv: unwrap
        # them first so the ketiv seg is matched whole.
        v_xml = re.sub(r'</?seg type="x-(?:big|small|suspended|large|reversednun|symbol|space)"[^>]*>', "", v_xml)
        v_xml = v_xml.replace("♫", " ")
        v_xml = re.sub(r'<seg type="x-ketiv">(.*?)</seg>', lambda k: "(" + " ".join(re.sub(r"<[^>]+>", "", k.group(1)).split()) + ")", v_xml, flags=re.DOTALL)
        v_xml = re.sub(r"</?seg\b[^>]*>", "", v_xml)  # inline: large/small/suspended letters stay in the word
        v_txt = norm_ws(_strip_hebrew_layout(re.sub(r"<[^>]+>", " ", v_xml)))
        if v_txt:
            out.setdefault(usfm, {}).setdefault(int(m.group(2)), {})[int(m.group(3))] = v_txt
    return out


# ---------------------------------------------------------------------------
# Latin
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=4)
def _usfx_index(path_str: str, _mtime: int) -> Dict[str, BookText]:
    fp = Path(path_str)
    if not fp.exists():
        return {}
    raw = read_text(fp)
    out: Dict[str, BookText] = {}
    for b in re.finditer(r'<book id="([0-9A-Z]{3})"(.*?)</book>', raw, flags=re.DOTALL):
        book_id = b.group(1)
        book_chunk = b.group(2)
        chapters: BookText = {}
        for c in re.finditer(r'<c id="(\d+)"\s*/>(.*?)(?=<c id="\d+"\s*/>|\Z)', book_chunk, flags=re.DOTALL):
            verses: Dict[int, str] = {}
            for m in re.finditer(r'<v id="(\d+)"[^>]*/>(.*?)<ve\s*/>', c.group(2), flags=re.DOTALL):
                inner = re.sub(r"<f\b.*?</f>", " ", m.group(2), flags=re.DOTALL)
                inner = re.sub(r"<x\b.*?</x>", " ", inner, flags=re.DOTALL)
                inner = re.sub(r"<[^>]+>", "", inner)
                inner = re.sub(r"\s+([:;?!])", r"\1", inner)  # French-style spacing before punctuation
                inner = re.sub(r"^\s*Prologus\s+", "", inner)  # heading word inlined into Lamentations 1:1
                if book_id == "SNG":
                    # VulSearch speaker rubrics inlined into Song of Songs (never in Exodus 4:26 or Lamentations)
                    inner = re.sub(
                        r"(?:^\s*|(?<=[.?!:;])\s+)(?:Sponsa|Sponsus|Chorus(?:\s+(?:Adolescentularum|Fratrum))?)\s+(?=[A-ZÆŒ])",
                        lambda r: " " if r.start() > 0 else "",
                        inner,
                    )
                txt = norm_ws(inner)
                if txt:
                    verses[int(m.group(1))] = txt
            if verses:
                chapters[int(c.group(1))] = verses
        out[book_id] = chapters
    return out


def _parse_latin_saints_json(fp: Path) -> BookText:
    if not fp.exists():
        return {}
    data = json.loads(read_text(fp))
    out: BookText = {}
    raw_entries: List[Tuple[int, int, str, str]] = []
    for ch_obj in data.get("chapters", []):
        try:
            ch = int(ch_obj.get("chapter", 0))
        except (TypeError, ValueError):
            continue
        for v in ch_obj.get("verses", []):
            m = re.search(r":(\d+)$", str(v.get("reference", "")))
            lat = (v.get("latin") or "").strip()
            # 244 verses (Sirach, 1–2 Maccabees) carry an English "· Translation note. …" for the site
            # inside the Latin field: it is not part of the Latin text.
            lat = re.split(r"\s*·?\s*Translation note\b", lat)[0].strip()
            # Strip VulSearch editorial speaker/acrostic tags (<Sponsus>, <Aleph>) and poetry block brackets ([ ]).
            lat = norm_ws(re.sub(r"<[^>]+>|[\[\]]", " ", lat))
            if m and lat:
                raw_entries.append((ch, int(m.group(1)), str(v.get("card_id") or ""), lat))
    # Where two entries share one reference string while the second entry's own canonical card slot is
    # empty (e.g. matthew-11-3 labelled Matthew 11:2 with 11:3 empty, or revelation-20-8 labelled 20:9
    # with 20:8 absent), restore the entry to its own verse number instead of overwriting its neighbour.
    slot_counts: Dict[Tuple[int, int], int] = {}
    for ch, vn, _card, _lat in raw_entries:
        slot_counts[(ch, vn)] = slot_counts.get((ch, vn), 0) + 1
    occupied = set(slot_counts)
    entries: List[Tuple[int, int, str, str]] = []
    for ch, vn, card, lat in raw_entries:
        if slot_counts.get((ch, vn), 0) > 1 and card and not card.startswith(("vg-", "vl-")):
            cm = re.search(r"-(\d+)-(\d+)$", card)
            if cm and int(cm.group(1)) == ch:
                v_card = int(cm.group(2))
                if v_card != vn and (ch, v_card) not in occupied:
                    vn = v_card
                    occupied.add((ch, v_card))
        entries.append((ch, vn, card, lat))
    # The Saints column pads a few places with a copy of another verse (Gen 5:32 repeats 5:31, 49:32
    # repeats 49:30, 50:23 repeats 50:22); both entries carry the same card_id. Keep the entry whose
    # own reference is the card's and drop the filler copy, so the edition's real verse can take
    # its place.
    by_card: Dict[str, List[Tuple[int, int]]] = {}
    for ch, vn, card, _lat in entries:
        if card:
            by_card.setdefault(card, []).append((ch, vn))
    text_of = {(ch, vn): lat for ch, vn, _card, lat in entries}
    fillers = set()
    for card, refs in by_card.items():
        if len(refs) < 2:
            continue
        cm = re.search(r"-(\d+)-(\d+)$", card)
        own = (int(cm.group(1)), int(cm.group(2))) if cm else None
        keep = own if own in refs else refs[0]
        # only a verbatim copy is a filler; a verse the Saints numbering split off keeps its own text
        fillers.update(r for r in refs if r != keep and norm_ws(text_of[r]) == norm_ws(text_of[keep]))
    card_of: Dict[Tuple[int, int], str] = {}
    for ch, vn, card, lat in entries:
        if (ch, vn) in fillers:
            continue
        clean = norm_ws(re.sub(r"\s+([:;?!])", r"\1", lat))
        prev = out.get(ch, {}).get(vn)
        if prev:
            prev_card = card_of.get((ch, vn), "")
            c1 = re.search(r"-(\d+)-(\d+)$", prev_card)
            c2 = re.search(r"-(\d+)-(\d+)$", card)
            # Two Vulgate verses of the same chapter combined into one Saints verse (John 6:51 = 6:51+52,
            # Luke 9:42 = 9:42+43, Numbers 6:23 = 6:23+27): concatenate rather than overwrite, provided
            # they are nearby in the chapter (not an unmapped Exodus 39:20 stub beside 39:34).
            unique_cards = len(by_card.get(prev_card, [])) <= 1 and len(by_card.get(card, [])) <= 1
            if (c1 and c2 and c1.group(1) == c2.group(1) and abs(int(c1.group(2)) - int(c2.group(2))) <= 5
                    and clean != prev and unique_cards):
                out[ch][vn] = f"{prev} {clean}"
                card_of[(ch, vn)] = card
                continue
        out.setdefault(ch, {})[vn] = clean
        card_of[(ch, vn)] = card
    return out


def _render_amiatinus_fragment(xml_frag: str) -> str:
    """Render the Digital Latin Library transcription of Codex Amiatinus as the manuscript reads.

    In this file ``@source`` values name printed editions, not scribal hands: ``#c`` Hetzenauer's
    Clementine (1906), ``#r`` the Rome Benedictine Vulgate (1926–95), ``#s`` the Stuttgart Vulgate
    (Weber–Gryson, 2007). ``<lem>`` carries the manuscript's text; ``<rdg>`` records an edition that
    prints otherwise, so it is dropped. Editorial corrections (``<corr>``, ``<reg>``), editor-supplied
    text (``<supplied>``), erasures (``<del>``) and abbreviation marks (``<am>``) are not manuscript
    text; ``<sic>``/``<orig>`` (what the scribe wrote), ``<add>`` and ``<surplus>`` are."""
    s = re.sub(r"<!--.*?-->", "", xml_frag, flags=re.DOTALL)
    s = re.sub(r'<p\b[^>]*rend="rubric"[^>]*>.*?</p>', " ", s, flags=re.DOTALL)  # titles / colophons
    s = re.sub(r"<label\b[^>/]*>.*?</label>", " ", s, flags=re.DOTALL)  # capitulum numbers (layout)
    # Words the scribe left out and the transcription supplies (from the Stuttgart edition): the
    # manuscript has a gap there, which must not count as an omission vote. One gap per supplied word;
    # letters supplied inside a word make the whole word a gap (truncated word).
    def _supplied_to_gap(m: re.Match[str]) -> str:
        words = re.sub(r"<[^>]+>", " ", m.group(1)).split()
        return ("§GAP" + str(len(words)) + "§") if words else " "

    s = re.sub(r"<supplied\b[^>]*>(.*?)</supplied>", _supplied_to_gap, s, flags=re.DOTALL)
    for tag in ("fw", "note", "del", "am", "corr", "reg", "rdg", "listTranspose"):
        s = re.sub(rf"<{tag}\b[^>]*/>", "", s)
        s = re.sub(rf"<{tag}\b.*?</{tag}>", "", s, flags=re.DOTALL)
    # Standalone <gap/> outside <del> marks illegible manuscript text (casts no vote).
    s = re.sub(r"<gap\b[^>]*/>", " §GAP1§ ", s)
    s = re.sub(r'\s*<lb\b[^>]*break="no"[^>]*/\s*>\s*', "", s)  # word-internal line break
    s = re.sub(r"<(?:lb|pb|cb|gb|space|label|supplied|g)\b[^>]*/\s*>", " ", s)
    # <name> / <placeName> wrap whole proper nouns (Gen 25:3 "</name>fuerunt"): keep a word boundary outside them.
    s = re.sub(r"(?<=\w)<(?:name|placeName)\b[^>]*>", " ", s)
    s = re.sub(r"</(?:name|placeName)>(?=\w)", " ", s)
    s = re.sub(r"<[^>]+>", "", s)
    out: List[str] = []
    for tok in norm_ws(s).split():
        m = re.fullmatch(r"§GAP(\d+)§", tok)
        if m:
            out.extend([GAP_WORD] * int(m.group(1)))
        elif "§GAP" in tok:
            out.append(GAP_WORD)  # truncated word
        elif re.match(r"^[,.;:!?]+$", tok):
            # Amiatinus XML encodes scribal cola/line-division dots as '<orig>,</orig>' against '<reg><lb/></reg>':
            # do not inject modern commas into an unpunctuated manuscript transcription.
            pass
        elif re.match(r"^[,.;:!?]+[A-Za-z]", tok):
            out.append(tok.lstrip(",.;:!?"))
        else:
            out.append(tok)
    return " ".join(out)


_AMIATINUS_BOOK_FILES: Dict[str, str] = {
    "genesis": "0011r-genesis.xml",
    "matthew": "0805r-mattheum.xml",
    "mark": "0832v-marcum.xml",
    "luke": "0852r-lucam.xml",
    "john": "0883r-iohannem.xml",
    "acts": "0905v-actus-apostolorum.xml",
    "romans": "0938r-romanos.xml",
    "1-corinthians": "0949v-corintheos-i.xml",
    "2-corinthians": "0960v-corintheos-ii.xml",
    "galatians": "0968v-galatas.xml",
    "ephesians": "0972v-ephesios.xml",
    "philippians": "0976v-philippenses.xml",
    "colossians": "0979v-colossenes.xml",
    "1-thessalonians": "0982v-thessalonicenses-i.xml",
    "2-thessalonians": "0985r-thessalonicenses-ii.xml",
    "1-timothy": "0986v-timotheum-i.xml",
    "2-timothy": "0990r-timotheum-ii.xml",
    "titus": "0992v-titum.xml",
    "philemon": "0993v-philemonem.xml",
    "hebrews": "0995r-hebraeos.xml",
    "james": "1003v-iacobi.xml",
    "1-peter": "1006v-petri-i.xml",
    "2-peter": "1009v-petri-ii.xml",
    "1-john": "1012r-iohannis-i.xml",
    "2-john": "1014v-iohannis-ii.xml",
    "3-john": "1015r-iohannis-iii.xml",
    "jude": "1015v-iudae.xml",
    "revelation": "1016v-apocalypsis-iohannis.xml",
}


def _parse_amiatinus_tei(fp: Path, book: BookSpec) -> BookText:
    target_fp: Optional[Path] = None
    mapped_name = _AMIATINUS_BOOK_FILES.get(book.slug)
    if fp.is_dir():
        if mapped_name and (fp / mapped_name).exists():
            target_fp = fp / mapped_name
        elif mapped_name and (fp / "text" / mapped_name).exists():
            target_fp = fp / "text" / mapped_name
        else:
            search_dir = fp / "text" if (fp / "text").is_dir() else fp
            target_fp = next(
                (p for p in sorted(search_dir.glob("*.xml"))
                 if not re.search(r"-(cap|prol|praef)\.xml$", p.name)
                 and p.stem.lower().split("-", 1)[-1] == book.slug),
                None,
            )
    elif fp.is_file():
        if book.slug in fp.stem.lower().split("-", 1)[-1] or (mapped_name and fp.name == mapped_name):
            target_fp = fp
        elif mapped_name and (fp.parent / mapped_name).exists():
            target_fp = fp.parent / mapped_name
        elif fp.parent.exists():
            target_fp = next((p for p in sorted(fp.parent.glob("*.xml")) if p.stem.lower().split("-", 1)[-1] == book.slug), None)
    if not target_fp or not target_fp.exists():
        return {}
    raw = read_text(target_fp)
    if "<TEI" not in raw[:5000]:
        return {}
    # Multi-chapter books use n="1.1"; single-chapter books (Philemon, 2–3 John, Jude) use n="1".
    marks = list(re.finditer(r'<milestone\s+unit="v"\s+n="(?:(\d+)\.)?(\d+)"\s*/>', raw))
    out: BookText = {}
    for idx, m in enumerate(marks):
        start = m.end()
        end = marks[idx + 1].start() if idx + 1 < len(marks) else raw.find("</body>", start)
        text = _render_amiatinus_fragment(raw[start: (end if end != -1 else len(raw))])
        if text:
            ch_num = int(m.group(1)) if m.group(1) else 1
            out.setdefault(ch_num, {})[int(m.group(2))] = text
    return out


# ---------------------------------------------------------------------------
# Majority / Ecclesiastical & Received Text Suites (Greek, Hebrew, Latin)
# ---------------------------------------------------------------------------

_USFM_CODE_FALLBACKS: Dict[str, Tuple[str, ...]] = {
    "EZR": ("EZR", "2ES"),
    "EST": ("EST", "ESG"),
    "DAN": ("DAN", "DAG"),
}


def _find_ebible_usfm(base_dir: Path, usfm_code: str) -> Optional[Path]:
    if not base_dir.is_dir():
        return None
    for code in _USFM_CODE_FALLBACKS.get(usfm_code, (usfm_code,)):
        matches = sorted(base_dir.glob(f"*-{code}*.usfm"))
        if matches:
            return matches[0]
    return None


# Numbering apparatus printed inside the verse text of the Orthodox Septuagint files: cross-references to
# another chapter division ("(Κεφ. ΛΘ 1)", "(Μασ. Ι, 6)"), lettered verse labels the parser leaves in the
# text ("12α", "22ε"), and a verse number given in running text inside a parenthesis ("… κληρονομεῖν.
# (10 οἱ Ὀμμὶν …" = Deut 2:10, whose \v marker is missing).
_EBIBLE_CROSS_NUMBER = re.compile(r"\((?:Κεφ|Μασ)\.[^()]{0,40}\)\.?")
_EBIBLE_LETTER_LABEL = re.compile(r"(?<!\S)\d+[α-ω](?!\S)")
_EBIBLE_INLINE_VERSE = re.compile(r"\((\d+) ")


_EBIBLE_DIGITS = re.compile(r"\d+(?:[·.:,]\d+)*[α-ω]?")  # 3 Kgdms 2:35's "35·1" … "35·14", stray numbers


def _strip_ebible_digits(text: str) -> str:
    """Greek text writes numbers as words or letter numerals: any digits left are numbering labels."""
    return norm_ws(_EBIBLE_DIGITS.sub(" ", text))


def _clean_ebible_numbering(chapters: BookText) -> BookText:
    out: BookText = {}
    for ch, verses in chapters.items():
        new: Dict[int, str] = {}
        for v in sorted(verses):
            text = norm_ws(_EBIBLE_LETTER_LABEL.sub(" ", _EBIBLE_CROSS_NUMBER.sub(" ", verses[v])))
            m = _EBIBLE_INLINE_VERSE.search(text)
            n = int(m.group(1)) if m else 0
            if m and n == v + 1 and n not in verses:
                new[v] = _strip_ebible_digits(text[: m.start()])
                new[n] = _strip_ebible_digits(text[m.end():])
            elif text:
                new[v] = _strip_ebible_digits(text)
        out[ch] = {v: t for v, t in new.items() if t}
    return out


def _parse_ebible_usfm_dir(base_dir: Path, book: BookSpec) -> BookText:
    """Parse an eBible/Haiola USFM folder (TCGNT, Patriarchal 1904, Boyd TR, Orthodox LXX)."""
    fp = _find_ebible_usfm(base_dir, book.usfm_code)
    if not fp:
        return {}
    chapters = _clean_ebible_numbering(parse_usfm_book(fp, drop_square_brackets=True))
    # If an edition marks doubtful interpolations with ⟦ … ⟧ (e.g. Antoniades 1904 in 1 John 5:7–8),
    # resolve them by the same rule as SBLGNT.
    if any(DOUBTFUL_OPEN in txt or DOUBTFUL_CLOSE in txt for vv in chapters.values() for txt in vv.values()):
        ordered = [(ch, v, txt) for ch in sorted(chapters) for v, txt in sorted(chapters[ch].items())]
        return _apply_doubtful_brackets(ordered, DOUBTFUL_OPEN, DOUBTFUL_CLOSE)
    return chapters


# Pre-Unicode-5.0 Hebrew files place holam (\u05B9) + optional cantillation BEFORE vav (\u05D5) in
# holam-male words (תְהֹ֑ום, אֹ֑ור). Re-order onto vav (\u05D5\u05B9) to match MAM and WLC.
_LEGACY_HOLAM_VAV = re.compile(
    r"([\u0591-\u05AF\u05B0-\u05B8\u05BA-\u05BD\u05BF\u05C1\u05C2\u05C7]*)"
    r"\u05B9([\u0591-\u05AF\u05BD]*)\u05D5(?![\u05B0-\u05BC\u05C7])"
)


def _normalize_legacy_hebrew_verse(raw: str) -> str:
    s = raw.replace("\u05AF", "").replace("\xa0", " ")
    s = _LEGACY_HOLAM_VAV.sub(lambda m: m.group(1) + m.group(2) + "\u05D5\u05B9", s)
    return norm_ws(_strip_hebrew_layout(s))


def _parse_ebible_hebrew_usfm_dir(base_dir: Path, book: BookSpec) -> BookText:
    """Parse Ben Chayyim / Masoretic Majority USFM files, normalizing holam-vav order."""
    fp = _find_ebible_usfm(base_dir, book.usfm_code)
    if not fp:
        return {}
    raw_book = parse_usfm_book(fp, drop_square_brackets=True)
    out: BookText = {}
    for ch, vv in raw_book.items():
        cleaned_vv = {v: _normalize_legacy_hebrew_verse(txt) for v, txt in vv.items()}
        cleaned_vv = {v: t for v, t in cleaned_vv.items() if t}
        if cleaned_vv:
            out[ch] = cleaned_vv
    return out


@functools.lru_cache(maxsize=2)
def _scrivener_json_index(path_str: str, _mtime: int) -> Dict[str, BookText]:
    """Scrivener 1894 polytonic Textus Receptus flat JSON (gnt.flat.json) → {usfm: {ch: {v: text}}}."""
    fp = Path(path_str)
    if not fp.exists():
        return {}
    data = json.loads(read_text(fp))
    out: Dict[str, BookText] = {}
    for row in data:
        usfm = OSIS_TO_USFM.get(str(row.get("book_name_osis", "")))
        ch, v = row.get("chapter"), row.get("verse")
        txt = norm_ws(str(row.get("greek_text") or ""))
        if usfm and isinstance(ch, int) and isinstance(v, int) and txt:
            out.setdefault(usfm, {}).setdefault(ch, {})[v] = txt
    return out


_LETTERIS_BOOK_FILES: Dict[str, str] = {
    "GEN": "Genesis.utf8_txt", "EXO": "Exodus.utf8_txt", "LEV": "Leviticus.utf8_txt",
    "NUM": "Numbers.utf8_txt", "DEU": "Deuteronomy.utf8_txt", "JOS": "Joshua.utf8_txt",
    "JDG": "Judges.utf8_txt", "RUT": "Ruth.utf8_txt", "1SA": "1Samuel.utf8_txt",
    "2SA": "2Samuel.utf8_txt", "1KI": "1Kings.utf8_txt", "2KI": "2Kings.utf8_txt",
    "1CH": "1Chronicles.utf8_txt", "2CH": "2Chronicles.utf8_txt", "EZR": "Ezra.utf8_txt",
    "NEH": "Nehemiah.utf8_txt", "EST": "Esther.utf8_txt", "JOB": "Job.utf8_txt",
    "PSA": "Psalms.utf8_txt", "PRO": "Proverbs.utf8_txt", "ECC": "Ecclesiastes.utf8_txt",
    "SNG": "Sos.utf8_txt", "ISA": "Isaiah.utf8_txt", "JER": "Jeremiah.utf8_txt",
    "LAM": "Lamentations.utf8_txt", "EZK": "Ezekiel.utf8_txt", "DAN": "Daniel.utf8_txt",
    "HOS": "Hosea.utf8_txt", "JOL": "Joel.utf8_txt", "AMO": "Amos.utf8_txt",
    "OBA": "Obadiah.utf8_txt", "JON": "Jonah.utf8_txt", "MIC": "Micah.utf8_txt",
    "NAM": "Nahum.utf8_txt", "HAB": "Habakkuk.utf8_txt", "ZEP": "Zephaniah.utf8_txt",
    "HAG": "Haggai.utf8_txt", "ZEC": "Zechariah.utf8_txt", "MAL": "Malachi.utf8_txt",
}


def _parse_letteris_book(base_dir: Path, book: BookSpec) -> BookText:
    """Meir Halevi Letteris 1852/1866 Masoretic Hebrew Bible UTF-8 TSV files."""
    fname = _LETTERIS_BOOK_FILES.get(book.usfm_code)
    if not fname:
        return {}
    fp = base_dir / fname
    if not fp.exists():
        return {}
    out: BookText = {}
    for line in read_text(fp).lstrip("\ufeff").splitlines():
        cols = line.split("\t")
        if len(cols) >= 6 and cols[1].isdigit() and cols[2].isdigit():
            txt = _normalize_legacy_hebrew_verse(cols[5])
            if txt:
                ch, v = int(cols[1]), int(cols[2])
                prev = out.get(ch, {}).get(v)
                out.setdefault(ch, {})[v] = f"{prev} {txt}" if prev else txt
    return out


_SCROLLMAPPER_BOOK_TO_USFM: Dict[str, str] = {
    "Genesis": "GEN", "Exodus": "EXO", "Leviticus": "LEV", "Numbers": "NUM", "Deuteronomy": "DEU",
    "Joshua": "JOS", "Judges": "JDG", "Ruth": "RUT", "I Samuel": "1SA", "II Samuel": "2SA",
    "I Kings": "1KI", "II Kings": "2KI", "I Chronicles": "1CH", "II Chronicles": "2CH",
    "Ezra": "EZR", "Nehemiah": "NEH", "Esther": "EST", "Job": "JOB", "Psalms": "PSA",
    "Proverbs": "PRO", "Ecclesiastes": "ECC", "Song of Solomon": "SNG", "Wisdom": "WIS",
    "Sirach": "SIR", "Isaiah": "ISA", "Jeremiah": "JER", "Lamentations": "LAM", "Ezekiel": "EZK",
    "Daniel": "DAN", "Hosea": "HOS", "Joel": "JOL", "Amos": "AMO", "Obadiah": "OBA",
    "Jonah": "JON", "Micah": "MIC", "Nahum": "NAM", "Habakkuk": "HAB", "Zephaniah": "ZEP",
    "Haggai": "HAG", "Zechariah": "ZEC", "Malachi": "MAL",
    "I Maccabees": "1MA", "II Maccabees": "2MA",
    "Matthew": "MAT", "Mark": "MRK", "Luke": "LUK", "John": "JHN", "Acts": "ACT",
    "Romans": "ROM", "I Corinthians": "1CO", "II Corinthians": "2CO", "Galatians": "GAL",
    "Ephesians": "EPH", "Philippians": "PHP", "Colossians": "COL",
    "I Thessalonians": "1TH", "II Thessalonians": "2TH", "I Timothy": "1TI", "II Timothy": "2TI",
    "Titus": "TIT", "Philemon": "PHM", "Hebrews": "HEB", "James": "JAS",
    "I Peter": "1PE", "II Peter": "2PE", "I John": "1JN", "II John": "2JN", "III John": "3JN",
    "Jude": "JUD", "Revelation of John": "REV",
}

_LATIN_LAM_ACROSTIC = re.compile(
    r"^(?:ALEPH|BETH|GHIMEL|GIMEL|DALETH|HE|VAU|ZAIN|HETH|TETH|IOD|JOD|CAPH|LAMED|MEM|NUN|"
    r"SAMECH|AIN|PHE|SADE|COPH|RES|SIN|SEN|THAU)\.?\s+",
    re.IGNORECASE,
)


@functools.lru_cache(maxsize=6)
def _scrollmapper_csv_index(path_str: str, _mtime: int) -> Dict[str, BookText]:
    """Parse a Book,Chapter,Verse,Text CSV Vulgate edition (Hetzenauer, Conte, Sistina)."""
    fp = Path(path_str)
    if not fp.exists():
        return {}
    out: Dict[str, BookText] = {}
    with fp.open(encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.DictReader(f):
            usfm = _SCROLLMAPPER_BOOK_TO_USFM.get(str(row.get("Book") or "").strip())
            if not usfm:
                continue
            ch_s, v_s = str(row.get("Chapter") or ""), str(row.get("Verse") or "")
            if not (ch_s.isdigit() and v_s.isdigit()):
                continue
            txt = norm_ws(str(row.get("Text") or ""))
            if usfm == "LAM":
                txt = _LATIN_LAM_ACROSTIC.sub(lambda m: m.group(0).rstrip(". ").capitalize() + " ", txt)
            if txt:
                out.setdefault(usfm, {}).setdefault(int(ch_s), {})[int(v_s)] = txt
    return out


# ---------------------------------------------------------------------------
# Historic Critical & INTF NTVMR Direct Manuscript Parsers (Greek NT)
# ---------------------------------------------------------------------------

_TISCHENDORF_OSIS_TO_USFM: Dict[str, str] = {
    "Matt": "MAT", "Mark": "MRK", "Luke": "LUK", "John": "JHN", "Acts": "ACT",
    "Rom": "ROM", "1Cor": "1CO", "2Cor": "2CO", "Gal": "GAL", "Eph": "EPH",
    "Phil": "PHP", "Col": "COL", "1Thess": "1TH", "2Thess": "2TH", "1Tim": "1TI",
    "2Tim": "2TI", "Titus": "TIT", "Phlm": "PHM", "Heb": "HEB", "Jas": "JAS",
    "1Pet": "1PE", "2Pet": "2PE", "1John": "1JN", "2John": "2JN", "3John": "3JN",
    "Jude": "JUD", "Rev": "REV",
}


@functools.lru_cache(maxsize=4)
def _tischendorf_osis_index(path_str: str, _mtime: int) -> Dict[str, BookText]:
    """Parse Tischendorf 8th Edition polytonic OSIS-XML (``tischendorfmorph.OSIS.xml``)."""
    fp = Path(path_str)
    if not fp.exists():
        return {}
    raw = read_text(fp)
    out: Dict[str, BookText] = {}
    for m in re.finditer(
        r'<verse\s+osisID="([1-3]?[A-Za-z]+)\.(\d+)\.(\d+)"\s+sID="[^"]+"\s*/>(.*?)<verse\s+eID="[^"]+"\s*/>',
        raw,
        flags=re.DOTALL,
    ):
        usfm = _TISCHENDORF_OSIS_TO_USFM.get(m.group(1))
        if not usfm:
            continue
        ch, v = int(m.group(2)), int(m.group(3))
        words = re.findall(r"<w\b[^>]*>(.*?)</w>", m.group(4), flags=re.DOTALL)
        if not words:
            continue
        # Strip Tischendorf's single editorial uncertainty brackets while preserving the attested words.
        cleaned = [re.sub(r"[\[\]]", "", re.sub(r"<[^>]+>", "", w)).strip() for w in words]
        txt = norm_ws(" ".join(w for w in cleaned if w))
        if txt:
            out.setdefault(usfm, {}).setdefault(ch, {})[v] = txt
    return out


_INTF_GREEK_DIGIT_PLACES: Dict[str, int] = {
    **{c: 1 for c in "αβγδεϛςϝζηθ"},
    **{c: 2 for c in "ικλμνξοπϙ"},
    **{c: 3 for c in "ρστυφχψωϡ"},
}


def _is_valid_greek_numeral_digits(letters: str) -> bool:
    """True when ``letters`` is a well-formed Greek alphabetic numeral (strictly descending places)."""
    s = letters.strip("͵ʹʹ΄´᾽’'").lower()
    if not s or len(s) > 4:
        return False
    places = [_INTF_GREEK_DIGIT_PLACES.get(ch, 0) for ch in s]
    if 0 in places:
        return False
    return all(a > b for a, b in zip(places, places[1:]))


def _resolve_intf_app(m: "re.Match[str]") -> str:
    """Keep only the firsthand reading inside an INTF/IGNTP/COMPAUL TEI-NTMSS ``<app>`` element."""
    body = m.group(1)
    # 1. Explicit self-closing firsthand omission (<rdg type="orig" hand="firsthand"/>) must be checked
    #    before paired <rdg> matching so '[^>]' never crosses a '/>' into a following corrector <rdg>.
    if re.search(r'<rdg\b[^>]*\btype="orig"[^>]*/\s*>', body):
        return ""
    orig = re.search(r'<rdg\b(?:[^>/]|/(?!>))*\btype="orig"(?:[^>/]|/(?!>))*>(.*?)</rdg>', body, flags=re.DOTALL)
    if orig:
        return orig.group(1)
    # 2. Untyped <rdg> (when INTF omitted type="orig" on the base reading alongside a corrector <rdg>).
    for rdg in re.finditer(r"<rdg\b((?:[^>/]|/(?!>))*)>(.*?)</rdg>", body, flags=re.DOTALL):
        attrs = rdg.group(1)
        if 'type="corr"' not in attrs and 'type="comm"' not in attrs and 'type="alt"' not in attrs:
            return rdg.group(2)
    return ""


def _render_intf_abbr(m: "re.Match[str]") -> str:
    kind = m.group(1)
    inner = m.group(2)
    if "<supplied" in inner or "<gap" in inner:
        return " §GAP1§ "
    inner = re.sub(r'\s*<pb\b[^>]*break="no"[^>]*/\s*>(?:\s*<cb\b[^>]*/\s*>)?(?:\s*<lb\b[^>]*/\s*>)?\s*', "", inner)
    inner = re.sub(r'\s*<lb\b[^>]*break="no"[^>]*/\s*>\s*', "", inner)
    letters = norm_ws(re.sub(r"<[^>]+>", "", inner)).replace(" ", "").lower()
    if not letters:
        return ""
    if kind == "num" and _is_valid_greek_numeral_digits(letters):
        return letters + "\u0374"
    return letters + "\u0305"


def _finalize_gap_tokens(text: str) -> str:
    """Resolve internal §GAPn§ / §LAC§ sentinels into Studio GAP_WORD / LACUNA_MARK tokens."""
    out: List[str] = []
    for tok in norm_ws(text).split():
        if tok == "§LAC§":
            if not out or out[-1] != LACUNA_MARK:
                out.append(LACUNA_MARK)
            continue
        mg = re.fullmatch(r"§GAP(\d+)§", tok)
        if mg:
            out.extend([GAP_WORD] * int(mg.group(1)))
            continue
        if "§LAC§" in tok:
            if not out or out[-1] != LACUNA_MARK:
                out.append(LACUNA_MARK)
            continue
        if "§GAP" in tok:
            out.append(GAP_WORD)
            continue
        out.append(tok)
    if not any(t not in (LACUNA_MARK, GAP_WORD) for t in out):
        return ""
    return " ".join(out)


def _clean_intf_ab_fragment(frag: str) -> str:
    """Render an INTF/IGNTP TEI-NTMSS ``<ab>`` verse body as first-hand Greek manuscript text."""
    s = re.sub(r"<!--.*?-->", "", frag, flags=re.DOTALL)
    # Strip marginal paratext (running headers, Vatican/Eusebian numbers, Latin chapter headings).
    s = re.sub(r'<seg\b[^>]*\btype="margin"[^>]*>.*?</seg>', " ", s, flags=re.DOTALL)
    s = re.sub(r'<num\b[^>]*\btype="chapNum"[^>]*>.*?</num>', " ", s, flags=re.DOTALL)
    s = re.sub(r"<app\b[^>]*>(.*?)</app>", _resolve_intf_app, s, flags=re.DOTALL)
    for tag in ("note", "fw", "pc"):
        if tag == "note":
            # Keep word-internal <note type="hyphen"/> joined with zero space (e.g. Codex Sinaiticus v195).
            s = re.sub(r'<note\b[^>]*\btype="hyphen"[^>]*/\s*>', "", s)
        s = re.sub(rf"<{tag}\b[^>]*/>", " ", s)
        s = re.sub(rf"<{tag}\b.*?</{tag}>", " ", s, flags=re.DOTALL)
    # Word-internal page/column/line breaks join the two halves of the word cleanly.
    s = re.sub(r'\s*<pb\b[^>]*break="no"[^>]*/\s*>(?:\s*<cb\b[^>]*/\s*>)?(?:\s*<lb\b[^>]*/\s*>)?\s*', "", s)
    s = re.sub(r'\s*<lb\b[^>]*break="no"[^>]*/\s*>\s*', "", s)
    s = re.sub(r"<(?:lb|pb|cb)\b[^>]*/\s*>", " ", s)
    # Nomina sacra and numerals before stripping <hi>/<unclear>.
    s = re.sub(r'<abbr\b[^>]*type="(nomSac|num)"[^>]*>(.*?)</abbr>', _render_intf_abbr, s, flags=re.DOTALL)

    # Editor-supplied text over lacunae/illegible parchment casts no vote (never invent MS readings).
    def _repl_supplied(m: "re.Match[str]") -> str:
        inner = m.group(1)
        plain = norm_ws(re.sub(r"<[^>]+>", " ", inner))
        wc = len(plain.split())
        if wc >= 3:
            return " §LAC§ "
        return f"§GAP{max(1, wc)}§"

    s = re.sub(r"<supplied\b[^>]*>(.*?)</supplied>", _repl_supplied, s, flags=re.DOTALL)

    def _repl_gap(m: "re.Match[str]") -> str:
        attrs = m.group(1)
        if re.search(r'unit="(?:line|verse|page|chapter)"', attrs):
            return " §LAC§ "
        return "§GAP1§"

    s = re.sub(r"<gap\b([^>]*)/?>", _repl_gap, s)
    # Ensure every <w> keeps a word boundary even across stripped <app>/<seg> elements.
    s = re.sub(r"</w>", "</w> ", s)
    s = re.sub(r"<[^>]+>", "", s)
    return _finalize_gap_tokens(s)


_IGNTP_BOOK_NUM: Dict[str, int] = {
    "Matt": 1, "Mark": 2, "Luke": 3, "John": 4, "Acts": 5,
    "Rom": 6, "1Cor": 7, "2Cor": 8, "Gal": 9, "Eph": 10, "Phil": 11, "Col": 12,
    "1Thess": 13, "2Thess": 14, "1Tim": 15, "2Tim": 16, "Titus": 17, "Phlm": 18,
    "Heb": 19, "Jas": 20, "1Pet": 21, "2Pet": 22, "1John": 23, "2John": 24, "3John": 25,
    "Jude": 26, "Rev": 27,
}

_IGNTP_PAUL_BOOK_LAYOUT: Dict[str, Tuple[str, str, str]] = {
    "romans": ("Romans", "ecm_romans", "Rom"),
    "1-corinthians": ("1Corinthians", "ecm_1corinthians", "1Cor"),
    "2-corinthians": ("2Corinthians", "ecm_2corinthians", "2Cor"),
    "galatians": ("Galatians", "ecm_galatians", "Gal"),
    "ephesians": ("Ephesians", "ecm_ephesians", "Eph"),
    "philippians": ("Philippians", "ecm_philippians", "Phil"),
    "colossians": ("Colossians", "ecm_colossians", "Col"),
}

_TEI_NTMSS_AB_RE = re.compile(
    r'<ab\b([^>]*\bn="(?:B(\d{2})K(\d+)V(\d+)|([1-3]?[A-Za-z]+)\.(\d+)\.(\d+))"[^>]*)>'
)


def _extract_tei_ntmss_chunks(body: str) -> Dict[Tuple[int, int, int], List[List[Tuple[str, str]]]]:
    """Group ``<ab>`` verse chunks by ``(nt_book_1..27, chapter, verse)``, keeping separate non-part
    occurrences (e.g. catena lemma repetitions or duplicated book transcriptions) in distinct lists."""
    matches = list(_TEI_NTMSS_AB_RE.finditer(body))
    grouped: Dict[Tuple[int, int, int], List[List[Tuple[str, str]]]] = {}
    for idx, m in enumerate(matches):
        attrs = m.group(1)
        if m.group(2) is not None:
            bnum, ch, v = int(m.group(2)), int(m.group(3)), int(m.group(4))
        else:
            bnum = _IGNTP_BOOK_NUM.get(m.group(5) or "", 0)
            ch, v = int(m.group(6)), int(m.group(7))
        if bnum < 1 or bnum > 27 or ch <= 0 or v <= 0:
            continue
        pm = re.search(r'\bpart="([IMF])"', attrs)
        part = pm.group(1) if pm else ""
        start = m.end()
        next_ab = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        chunk = body[start:next_ab]
        stop = len(chunk)
        for stopper in ("</ab>", "<div ", "</body>"):
            pos = chunk.find(stopper)
            if pos != -1 and pos < stop:
                stop = pos
        key = (bnum, ch, v)
        runs = grouped.setdefault(key, [])
        if runs and part in ("M", "F") and runs[-1][-1][0] in ("I", "M"):
            runs[-1].append((part, chunk[:stop]))
        else:
            runs.append([(part, chunk[:stop])])
    return grouped


def _stitch_tei_ntmss_run(chunks: List[Tuple[str, str]], cleaner) -> str:
    first_part = chunks[0][0]
    last_part = chunks[-1][0]
    stitched = chunks[0][1]
    for _part, nxt in chunks[1:]:
        if re.search(r'<w\b[^>]*\bpart="[IM]"[^>]*>(?:(?!</w>).)*</w>\s*$', stitched, re.DOTALL) and re.match(
            r'^\s*<w\b[^>]*\bpart="[MF]"[^>]*>', nxt
        ):
            stitched = re.sub(r"</w>\s*$", "", stitched) + re.sub(r'^\s*<w\b[^>]*\bpart="[MF]"[^>]*>', "", nxt, count=1)
        else:
            stitched = stitched + " " + nxt
    if first_part in ("M", "F"):
        stitched = re.sub(r'^\s*<w\b[^>]*\bpart="[MF]"[^>]*>(?:(?!</w>).)*(?:</w>)?', " §GAP1§ ", stitched, count=1, flags=re.DOTALL)
    if last_part in ("I", "M"):
        stitched = re.sub(r'<w\b[^>]*\bpart="[IM]"[^>]*>(?:(?!</w>).)*(?:</w>)?\s*$', " §GAP1§ ", stitched, count=1, flags=re.DOTALL)
    text = cleaner(stitched)
    if not text:
        return ""
    if first_part in ("M", "F") and not text.startswith(LACUNA_MARK):
        text = f"{LACUNA_MARK} {text}"
    if last_part in ("I", "M") and not text.endswith(LACUNA_MARK):
        text = f"{text} {LACUNA_MARK}"
    return text


def _pick_tei_ntmss_run(runs: List[List[Tuple[str, str]]], cleaner) -> str:
    """Keep the first transcription of a verse (never concatenating a duplicate book copy as in 30033.xml),
    unless a later catena lemma expands the exact opening words into a strictly longer complete verse
    (as in Codex Zacynthius Luke 1:2, 1:36, 6:24, 6:43, 7:28)."""
    best = _stitch_tei_ntmss_run(runs[0], cleaner)
    if len(runs) == 1:
        return best
    best_words = [w for w in best.split() if w not in (LACUNA_MARK, GAP_WORD)]
    for run in runs[1:]:
        cand = _stitch_tei_ntmss_run(run, cleaner)
        if not cand:
            continue
        if not best:
            best = cand
            best_words = [w for w in best.split() if w not in (LACUNA_MARK, GAP_WORD)]
            continue
        cand_words = [w for w in cand.split() if w not in (LACUNA_MARK, GAP_WORD)]
        if len(cand_words) > len(best_words) + 1 and best_words:
            # Verify shared opening words (catena lemma expansion, not an unrelated second copy).
            lead = min(2, len(best_words))
            if [re.sub(r"[^\w]", "", w).lower() for w in cand_words[:lead]] == [
                re.sub(r"[^\w]", "", w).lower() for w in best_words[:lead]
            ]:
                best, best_words = cand, cand_words
    return best


@functools.lru_cache(maxsize=48)
def _intf_ntvmr_index(path_str: str, _mtime: int) -> Dict[int, BookText]:
    """Parse an INTF NTVMR / IGNTP TEI-NTMSS XML manuscript file into ``{nt_book_1..27: {ch: {v: text}}}``.

    Uses boundary slicing on ``<ab n="B..K..V..">`` or ``<ab n="Rom.1.7">`` rather than strict DOM
    parsing so upstream INTF files with unclosed ``part="M"`` / ``part="F"`` folio-break tags (such
    as Minuscule 33 and Minuscule 1739) parse cleanly without losing verses. Incomplete ``part="I"``
    / ``part="F"`` verses whose other half is missing on a lost folio receive edge lacuna marks."""
    fp = Path(path_str)
    if not fp.exists():
        return {}
    raw = read_text(fp)
    body_start = raw.find("<body>")
    if body_start == -1:
        return {}
    grouped = _extract_tei_ntmss_chunks(raw[body_start:])
    out: Dict[int, BookText] = {}
    for (bnum, ch, v), runs in grouped.items():
        text = _pick_tei_ntmss_run(runs, _clean_intf_ab_fragment)
        if text:
            out.setdefault(bnum, {}).setdefault(ch, {})[v] = text
    return out


def _igntp_sibling_for_ga(igntp_root: Path, ga_num: str, book: BookSpec) -> Optional[Path]:
    spec = _IGNTP_PAUL_BOOK_LAYOUT.get(book.slug)
    if not spec:
        return None
    folder, sub, abbr = spec
    cand = igntp_root / folder / sub / f"NT_GRC_{ga_num}_{abbr}.xml"
    return cand if cand.exists() else None


def _parse_intf_ntvmr_book(base_path: Path, book: BookSpec) -> BookText:
    if not book.cntr_book or book.cntr_book < 40:
        return {}
    bnum = book.cntr_book - 39
    primary = _intf_ntvmr_index(*_mtime_key(base_path)).get(bnum, {})
    # Upgrade incomplete INTF NTVMR Pauline books (e.g. 30033.xml missing Ephesians & 23 verses of
    # Romans; 31739.xml missing Galatians, Ephesians & Romans 7–16) from IGNTP CC BY 4.0 Pauline XMLs.
    if book.slug in _IGNTP_PAUL_BOOK_LAYOUT:
        m = re.fullmatch(r"([1-3])(\d{4})\.xml", base_path.name)
        if m:
            prefix, num_str = m.group(1), m.group(2)
            ga = f"P{int(num_str)}" if prefix == "1" else (f"0{int(num_str)}" if prefix == "2" else str(int(num_str)))
            igntp_root = GREEK_RESEARCH_ROOT / "04_Tier4_Ancient_Manuscripts" / "NT_IGNTP_Paul_XMLs"
            sib = _igntp_sibling_for_ga(igntp_root, ga, book)
            if sib is not None:
                igntp_bk = _intf_ntvmr_index(*_mtime_key(sib)).get(bnum, {})
                prim_n = sum(len(vs) for vs in primary.values())
                ign_n = sum(len(vs) for vs in igntp_bk.values())
                if ign_n > prim_n:
                    return igntp_bk
    return primary


def _parse_igntp_paul_xml(base_path: Path, book: BookSpec) -> BookText:
    """Resolve an IGNTP Pauline witness across Romans, Galatians, Ephesians (and future Pauline folders)
    from its anchor Romans XML path (e.g. ``.../NT_IGNTP_Paul_XMLs/Romans/ecm_romans/NT_GRC_06_Rom.xml``)."""
    if not book.cntr_book or book.cntr_book < 40 or book.slug not in _IGNTP_PAUL_BOOK_LAYOUT:
        return {}
    m = re.match(r"^NT_GRC_([^_]+)_[A-Za-z0-9]+\.xml$", base_path.name)
    if not m:
        return _intf_ntvmr_index(*_mtime_key(base_path)).get(book.cntr_book - 39, {})
    ga = m.group(1)
    # base_path = <igntp_root>/<BookDir>/<ecm_book>/NT_GRC_<GA>_<Abbr>.xml
    igntp_root = base_path.parents[2] if len(base_path.parents) >= 3 else base_path.parent
    target = _igntp_sibling_for_ga(igntp_root, ga, book)
    if target is None:
        return {}
    return _intf_ntvmr_index(*_mtime_key(target)).get(book.cntr_book - 39, {})


# ---------------------------------------------------------------------------
# COMPAUL Old Latin (Vetus Latina) Pauline TEI-NTMSS (CC BY 4.0)
# ---------------------------------------------------------------------------

_COMPAUL_BOOK_LAYOUT: Dict[str, Tuple[str, str]] = {
    "romans": ("Romans", "06"),
    "1-corinthians": ("1Corinthians", "07"),
    "2-corinthians": ("2Corinthians", "08"),
    "galatians": ("Galatians", "09"),
}

# Verified Latin nomina sacra expansions used in COMPAUL Old Latin manuscripts.
# Ordinary Latin words occasionally mis-tagged <abbr type="nomSac"> upstream are left unexpanded.
_LATIN_NOMINA_SACRA: Dict[str, str] = {
    "ds": "deus", "di": "dei", "do": "deo", "dm": "deum", "dem": "deum",
    "dns": "dominus", "dms": "dominus",
    "dni": "domini", "dmi": "domini",
    "dno": "domino", "dmo": "domino",
    "dnm": "dominum", "dmm": "dominum", "dom": "dominum",
    "dne": "domine", "dme": "domine",
    "ihs": "iesus", "ihc": "iesus", "ius": "iesus", "ies": "iesus",
    "ihu": "iesu", "iu": "iesu",
    "ihm": "iesum", "ihn": "iesum", "ism": "iesum", "ium": "iesum",
    "xps": "christus", "xpc": "christus", "chs": "christus", "xrs": "christus",
    "xpi": "christi", "chi": "christi", "xri": "christi",
    "xpo": "christo", "cho": "christo", "xro": "christo",
    "xpm": "christum", "chm": "christum", "xrm": "christum",
    "xpe": "christe",
    "sps": "spiritus", "spc": "spiritus", "spus": "spiritus",
    "spui": "spiritui", "spu": "spiritu", "sspu": "spiritu",
    "spm": "spiritum", "spum": "spiritum", "spuum": "spirituum",
    "scs": "sanctus", "scus": "sanctus", "sci": "sancti", "sco": "sancto", "scm": "sanctum",
    "isrl": "israhel", "irl": "israhel", "isrhl": "israhel",
}


def _render_compaul_abbr(m: "re.Match[str]") -> str:
    kind = m.group(1)
    inner = m.group(2)
    if "<supplied" in inner or "<gap" in inner:
        return " §GAP1§ "
    inner = re.sub(r'\s*<pb\b[^>]*break="no"[^>]*/\s*>(?:\s*<cb\b[^>]*/\s*>)?(?:\s*<lb\b[^>]*/\s*>)?\s*', "", inner)
    inner = re.sub(r'\s*<lb\b[^>]*break="no"[^>]*/\s*>\s*', "", inner)
    letters = re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", html.unescape(inner)))
    if not letters:
        return ""
    if kind == "nomSac":
        exp = _LATIN_NOMINA_SACRA.get(letters.lower())
        if exp:
            return exp.capitalize() if letters[:1].isupper() else exp
    return letters


def _clean_compaul_ab_fragment(frag: str) -> str:
    """Render a COMPAUL / Vetus Latina / Codex Bezae TEI-NTMSS ``<ab>`` or ``<rdg>`` body as first-hand Latin text."""
    s = re.sub(r"<!--.*?-->", "", frag, flags=re.DOTALL)
    s = re.sub(r'<seg\b[^>]*\btype="margin"[^>]*>.*?</seg>', " ", s, flags=re.DOTALL)
    s = re.sub(r'<num\b[^>]*\btype="(?:chapNum|AmmSec|EusCan)"[^>]*>.*?</num>', " ", s, flags=re.DOTALL)
    s = re.sub(r"<app\b[^>]*>(.*?)</app>", _resolve_intf_app, s, flags=re.DOTALL)
    for tag in ("note", "fw", "pc"):
        if tag == "note":
            s = re.sub(r'<note\b[^>]*\btype="hyphen"[^>]*/\s*>', "", s)
        s = re.sub(rf"<{tag}\b[^>]*/>", " ", s)
        s = re.sub(rf"<{tag}\b.*?</{tag}>", " ", s, flags=re.DOTALL)
    s = re.sub(r'\s*<pb\b[^>]*break="no"[^>]*/\s*>(?:\s*<cb\b[^>]*/\s*>)?(?:\s*<lb\b[^>]*/\s*>)?\s*', "", s)
    s = re.sub(r'\s*<lb\b[^>]*break="no"[^>]*/\s*>\s*', "", s)
    s = re.sub(r"<(?:lb|pb|cb)\b[^>]*/\s*>", " ", s)
    s = re.sub(r'<abbr\b[^>]*type="(nomSac|num)"[^>]*>(.*?)</abbr>', _render_compaul_abbr, s, flags=re.DOTALL)

    def _repl_supplied(m: "re.Match[str]") -> str:
        plain = norm_ws(re.sub(r"<[^>]+>", " ", m.group(1)))
        wc = len(plain.split())
        if wc >= 3:
            return " §LAC§ "
        return f"§GAP{max(1, wc)}§"

    s = re.sub(r"<supplied\b[^>]*>(.*?)</supplied>", _repl_supplied, s, flags=re.DOTALL)

    def _repl_gap(m: "re.Match[str]") -> str:
        if re.search(r'unit="(?:line|verse|page|chapter)"', m.group(1)):
            return " §LAC§ "
        return "§GAP1§"

    s = re.sub(r"<gap\b([^>]*)/?>", _repl_gap, s)
    # Keep inner expansion letters of <ex> (e.g. o<ex>m</ex>nib<ex>us</ex> -> omnibus).
    s = re.sub(r"</?ex\b[^>]*>", "", s)
    s = re.sub(r"</w>", "</w> ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    # Medieval Vetus Latina abbreviation symbols: ÷ (nasal final -m, e.g. uerbu÷ -> uerbum), ¬ (suspension).
    s = re.sub(r"([aeiouAEIOU])÷", r"\1m", s).replace("÷", "").replace("¬", "")
    return _finalize_gap_tokens(s)


@functools.lru_cache(maxsize=48)
def _compaul_latin_index(path_str: str, _mtime: int) -> Dict[int, BookText]:
    fp = Path(path_str)
    if not fp.exists():
        return {}
    raw = read_text(fp)
    body_start = raw.find("<body>")
    if body_start == -1:
        return {}
    grouped = _extract_tei_ntmss_chunks(raw[body_start:])
    out: Dict[int, BookText] = {}
    for (bnum, ch, v), runs in grouped.items():
        text = _pick_tei_ntmss_run(runs, _clean_compaul_ab_fragment)
        if text:
            out.setdefault(bnum, {}).setdefault(ch, {})[v] = text
    return out


def _parse_compaul_latin_tei(base_path: Path, book: BookSpec) -> BookText:
    """Resolve either a single-file Old Latin TEI-NTMSS manuscript (e.g. ``Bezae-Latin.xml`` across
    Gospels & Acts) or a multi-book COMPAUL Pauline witness anchored on its Romans XML."""
    if not book.cntr_book or book.cntr_book < 40:
        return {}
    m = re.match(r"^\d+_(.+)\.xml$", base_path.name)
    if not m:
        return _compaul_latin_index(*_mtime_key(base_path)).get(book.cntr_book - 39, {})
    if book.slug not in _COMPAUL_BOOK_LAYOUT:
        return {}
    sig = m.group(1)
    folder, prefix = _COMPAUL_BOOK_LAYOUT[book.slug]
    compaul_root = base_path.parents[1] if len(base_path.parents) >= 2 else base_path.parent
    target = compaul_root / folder / f"{prefix}_{sig}.xml"
    if not target.exists():
        return {}
    return _compaul_latin_index(*_mtime_key(target)).get(book.cntr_book - 39, {})


# ---------------------------------------------------------------------------
# Hebrew Ben Sira (Sirach) TEI-XML — Rey & Reymond 2024 (CC BY-SA 4.0)
# ---------------------------------------------------------------------------

_HEB_WIDE_LETTERS = str.maketrans({
    "\ufb21": "א", "\ufb22": "ד", "\ufb23": "ה", "\ufb24": "כ",
    "\ufb25": "ל", "\ufb26": "ם", "\ufb27": "ר", "\ufb28": "ת",
})
_BENSIRA_STRIP_RE = re.compile(r"[\u0307\u0308\u030a\u059f\u05af\u200d\u2219{}.]")


def _clean_bensira_word(w_el: ET.Element) -> str:
    """Return an extant Hebrew word from a Ben Sira ``<w>`` element, or ``GAP_WORD`` if any part
    is editorially reconstructed, broken (``]``), illegible trace (``◦``), or alternate-letter (``/``).
    Never invents letters."""
    has_rec_g = any(
        (ch.tag.split("}")[-1] == "g" and ch.attrib.get("type") == "reconstructed")
        for ch in w_el
    )
    parts: List[str] = []
    if w_el.text:
        parts.append(w_el.text)
    for ch in w_el:
        ctag = ch.tag.split("}")[-1]
        if ctag == "g" and ch.attrib.get("type") == "reconstructed":
            pass
        elif ctag not in ("margin", "del"):
            parts.append("".join(ch.itertext()))
        if ch.tail:
            parts.append(ch.tail)
    raw_ext = "".join(parts)
    if has_rec_g or "]" in raw_ext or "[" in raw_ext or "\u25e6" in raw_ext or "/" in raw_ext:
        return GAP_WORD
    # Delete scribal strikethrough characters (letter + U+0336).
    cleaned = re.sub(r".\u0336", "", raw_ext)
    cleaned = cleaned.translate(_HEB_WIDE_LETTERS)
    cleaned = _BENSIRA_STRIP_RE.sub("", cleaned)
    cleaned = cleaned.replace(":", "׃").strip()
    if not any("\u05d0" <= ch <= "\u05ea" for ch in cleaned):
        return ""
    return unicodedata.normalize("NFC", cleaned)


@functools.lru_cache(maxsize=16)
def _bensira_tei_index(path_str: str, _mtime: int) -> BookText:
    """Parse one Rey & Reymond (2024) Hebrew Ben Sira TEI-XML manuscript into ``{chapter: {verse: text}}``.

    Excludes ``<margin>`` marginal variants and ``<del>`` scribal deletions; converts editorially
    reconstructed or broken words to ``GAP_WORD`` (collapsing 3+ consecutive gaps to ``LACUNA_MARK``),
    and drops verses with zero extant Hebrew words."""
    fp = Path(path_str)
    if not fp.exists():
        return {}
    try:
        root = ET.parse(fp).getroot()
    except ET.ParseError:
        return {}
    out: BookText = {}

    def _collect_words(el: ET.Element, buf: List[str]) -> None:
        tag = el.tag.split("}")[-1]
        if tag in ("margin", "del"):
            return
        if tag == "w":
            tok = _clean_bensira_word(el)
            if tok:
                buf.append(tok)
            return
        for ch in el:
            _collect_words(ch, buf)

    for cdiv in root.iter():
        if cdiv.tag.split("}")[-1] != "div" or cdiv.attrib.get("type") != "chap":
            continue
        cn = cdiv.attrib.get("n", "").strip()
        if not cn.isdigit():
            continue
        ch_num = int(cn)
        if not 1 <= ch_num <= 51:
            continue
        last_v: Optional[int] = None
        for vdiv in cdiv:
            if vdiv.tag.split("}")[-1] != "div" or vdiv.attrib.get("type") != "verse":
                continue
            vn = vdiv.attrib.get("n", "").strip()
            vm = re.match(r"^\[?(\d+)", vn)
            if vm:
                v_num = int(vm.group(1))
                last_v = v_num
            elif last_v is not None and re.fullmatch(r"[a-z]+", vn):
                v_num = last_v
            else:
                continue
            if v_num <= 0:
                continue
            buf: List[str] = []
            _collect_words(vdiv, buf)
            if not any(t != GAP_WORD for t in buf):
                continue
            # Collapse runs of 3+ consecutive GAP_WORD into LACUNA_MARK.
            collapsed: List[str] = []
            i = 0
            while i < len(buf):
                if buf[i] == GAP_WORD:
                    j = i
                    while j < len(buf) and buf[j] == GAP_WORD:
                        j += 1
                    if j - i >= 3:
                        if not collapsed or collapsed[-1] != LACUNA_MARK:
                            collapsed.append(LACUNA_MARK)
                    else:
                        collapsed.extend([GAP_WORD] * (j - i))
                    i = j
                else:
                    collapsed.append(buf[i])
                    i += 1
            text = norm_ws(" ".join(collapsed))
            if not text:
                continue
            ch_map = out.setdefault(ch_num, {})
            if v_num in ch_map:
                ch_map[v_num] = norm_ws(f"{ch_map[v_num]} {text}")
            else:
                ch_map[v_num] = text
    return out


# ---------------------------------------------------------------------------
# Phase 2/3 & Owner-Authorized Study-Archive Parsers
# (Rahlfs 1935, Sinaiticus OT XML, OG Daniel, TAGNT NA28/THGNT, Tregelles 1879,
#  Elzevir 1624, ETCBC BHSA, Samaritan Pentateuch TF, Dead Sea Scrolls TF,
#  Vetus Latina Iohannes Synopsis, DivinumOfficium Pianum Psalter)
# ---------------------------------------------------------------------------

_RAHLFS_BOOK_TO_USFM: Dict[str, str] = {
    "Gen": "GEN", "Exod": "EXO", "Lev": "LEV", "Num": "NUM", "Deut": "DEU",
    "JoshB": "JOS", "JudgB": "JDG", "Ruth": "RUT",
    "1Sam": "1SA", "2Sam": "2SA", "1Kgs": "1KI", "2Kgs": "2KI",
    "1Chr": "1CH", "2Chr": "2CH", "Esth": "EST", "1Macc": "1MA", "2Macc": "2MA",
    "Job": "JOB", "Ps": "PSA", "Prov": "PRO", "Eccl": "ECC", "Song": "SNG",
    "Lam": "LAM", "Wis": "WIS", "Sir": "SIR",
    "Isa": "ISA", "Jer": "JER", "Ezek": "EZK", "DanTh": "DAN",
    "Hos": "HOS", "Joel": "JOL", "Amos": "AMO", "Obad": "OBA", "Jonah": "JON",
    "Mic": "MIC", "Nah": "NAM", "Hab": "HAB", "Zeph": "ZEP", "Hag": "HAG",
    "Zech": "ZEC", "Mal": "MAL",
}


@functools.lru_cache(maxsize=2)
def _rahlfs_csv_index(path_str: str, _mtime: int) -> Dict[str, BookText]:
    """Parse Rahlfs 1935 polytonic Septuaginta CSV suite across all 43 Saints canonical Greek OT books."""
    base = Path(path_str)
    csv_root = base / "LXX_Rahlfs_1935_CSV" if (base / "LXX_Rahlfs_1935_CSV").exists() else base
    vfile = csv_root / "08_versification" / "001_verse_c_modified_KEEP.csv"
    wfile = csv_root / "01_wordlist_unicode" / "text_accented.csv"
    if not (vfile.exists() and wfile.exists()):
        return {}
    words: Dict[int, str] = {}
    max_wid = 0
    for line in read_text(wfile).splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].isdigit():
            wid = int(parts[0])
            words[wid] = parts[-1]
            if wid > max_wid:
                max_wid = wid
    starts: List[Tuple[int, str]] = []
    for line in read_text(vfile).splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1].isdigit():
            starts.append((int(parts[1]), parts[0].strip()))
    out: Dict[str, BookText] = {}
    n_words = max_wid + 1
    for idx, (start_i, ref) in enumerate(starts):
        end_i = starts[idx + 1][0] if idx + 1 < len(starts) else n_words
        if start_i >= end_i or start_i < 1:
            continue
        ref_parts = ref.split(".")
        if len(ref_parts) < 3:
            continue
        bk, ch_s, v_s = ref_parts[0], ref_parts[1], ref_parts[2]
        if not ch_s.isdigit():
            continue
        vm = re.match(r"^(\d+)", v_s)
        if not vm:
            continue
        ch, v = int(ch_s), int(vm.group(1))
        if ch <= 0 or v <= 0:
            continue
        if bk == "2Esdr":
            usfm = "EZR" if ch <= _ESDRAS_B_EZRA_LAST_CHAPTER else "NEH"
            if usfm == "NEH":
                ch -= _ESDRAS_B_EZRA_LAST_CHAPTER
        else:
            usfm = _RAHLFS_BOOK_TO_USFM.get(bk)
        if not usfm:
            continue
        txt = norm_ws(" ".join(words[k] for k in range(start_i, min(end_i, n_words)) if k in words))
        if not txt:
            continue
        ch_map = out.setdefault(usfm, {}).setdefault(ch, {})
        ch_map[v] = norm_ws(f"{ch_map[v]} {txt}") if v in ch_map else txt
    return out


_SINAITICUS_BOOK_TO_USFM: Dict[str, str] = {
    "01-GEN": "GEN", "02-LEV": "LEV", "03-NUM": "NUM", "04-DEUT": "DEU",
    "05-JOSH": "JOS", "06-JUDG": "JDG", "07-1CHR": "1CH",
    "09-EST": "EST", "12-1MACC": "1MA",
    "14-ISA": "ISA", "15-JER": "JER", "16-LAM": "LAM",
    "17-JOEL": "JOL", "18-OBAD": "OBA", "19-JONAH": "JON", "20-NAH": "NAM",
    "21-HAB": "HAB", "22-ZEPH": "ZEP", "23-HAG": "HAG", "24-ZECH": "ZEC", "25-MAL": "MAL",
    "26-PS": "PSA", "27-PROV": "PRO", "28-ECCL": "ECC", "29-CANT": "SNG",
    "30-WIS": "WIS", "31-SIR": "SIR", "32-JOB": "JOB",
    "33-MATT": "MAT", "34-MARK": "MRK", "35-LUKE": "LUK", "36-JOHN": "JHN",
    "37-ROM": "ROM", "38-1COR": "1CO", "39-2COR": "2CO", "40-GAL": "GAL",
    "41-EPH": "EPH", "42-PHIL": "PHP", "43-COL": "COL", "44-1THESS": "1TH",
    "45-2THESS": "2TH", "46-HEB": "HEB", "47-1TIM": "1TI", "48-2TIM": "2TI",
    "49-TITUS": "TIT", "50-PHLM": "PHM", "51-ACTS": "ACT", "52-JAS": "JAS",
    "53-1PET": "1PE", "54-2PET": "2PE", "55-1JOHN": "1JN", "56-2JOHN": "2JN",
    "57-3JOHN": "3JN", "58-JUDE": "JUD", "59-REV": "REV",
}

_SINAITICUS_AB_RE = re.compile(
    r'<ab\b[^>]*\bxml:id="V-B\d+K(\d+)V(\d+)-(\d+-[A-Z0-9]+)"[^>]*>(.*?)</ab>',
    re.DOTALL,
)


@functools.lru_cache(maxsize=2)
def _sinaiticus_tei_index(path_str: str, _mtime: int) -> Dict[str, BookText]:
    """Parse Codex Sinaiticus Project full TEI-XML v1.95 (first-hand readings, OT & NT)."""
    fp = Path(path_str)
    if not fp.exists():
        return {}
    raw = read_text(fp)
    out: Dict[str, BookText] = {}
    for m in _SINAITICUS_AB_RE.finditer(raw):
        ch, v, code, inner = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)
        if ch <= 0 or v <= 0:
            continue
        if code == "08-2ESD":
            usfm = "EZR" if ch <= _ESDRAS_B_EZRA_LAST_CHAPTER else "NEH"
            if usfm == "NEH":
                ch -= _ESDRAS_B_EZRA_LAST_CHAPTER
        else:
            usfm = _SINAITICUS_BOOK_TO_USFM.get(code)
        if not usfm:
            continue
        txt = _clean_intf_ab_fragment(inner)
        if not txt:
            continue
        ch_map = out.setdefault(usfm, {}).setdefault(ch, {})
        ch_map[v] = norm_ws(f"{ch_map[v]} {txt}") if v in ch_map else txt
    return out


def _parse_first1k_og_daniel(tlg_dir: Path, book: BookSpec) -> BookText:
    """Parse Old Greek (Septuagint) Daniel (``tlg056``) from First1KGreek."""
    if book.slug != "daniel":
        return {}
    from dataclasses import replace
    return _parse_first1k_tei(tlg_dir, replace(book, tlg_work="tlg056"))


_TAGNT_BOOK_TO_USFM: Dict[str, str] = {
    "Mat": "MAT", "Mrk": "MRK", "Luk": "LUK", "Jhn": "JHN", "Act": "ACT",
    "Rom": "ROM", "1Co": "1CO", "2Co": "2CO", "Gal": "GAL", "Eph": "EPH",
    "Php": "PHP", "Col": "COL", "1Th": "1TH", "2Th": "2TH", "1Ti": "1TI",
    "2Ti": "2TI", "Tit": "TIT", "Phm": "PHM", "Heb": "HEB", "Jas": "JAS",
    "1Pe": "1PE", "2Pe": "2PE", "1Jn": "1JN", "2Jn": "2JN", "3Jn": "3JN",
    "Jud": "JUD", "Rev": "REV",
}


def _tagnt_match_ed_group(eg: str, target_ed: str) -> Optional[int]:
    """Return word-order offset (0, +N for '>N:', -N for '<N:') if ``target_ed`` appears in ``eg``, else None."""
    parts = re.split(r"([<>]\d+:)", eg)
    offset = 0
    for part in parts:
        mm = re.fullmatch(r"([<>])(\d+):", part)
        if mm:
            offset = int(mm.group(2)) if mm.group(1) == ">" else -int(mm.group(2))
            continue
        if target_ed in re.split(r"[+\s]+", part):
            return offset
    return None


def _tagnt_pick_word(grk: str, eds: str, sp: str, mv: str, target_ed: str) -> Optional[Tuple[str, int]]:
    """Return ``(word, order_offset)`` attested by ``target_ed`` (``NA28`` or ``Tyn``) on one TAGNT row."""
    grk = grk.replace("¶", "").strip()
    ed_groups = re.split(r"\s*[;,]\s*", eds)
    sp_groups = re.split(r"\s*[;,]\s*", sp) if sp else []
    for idx, eg in enumerate(ed_groups):
        off = _tagnt_match_ed_group(eg, target_ed)
        if off is not None:
            if idx == 0:
                return grk, off
            if idx < len(sp_groups) and sp_groups[idx]:
                sp_form = sp_groups[idx].replace("¶", "").strip()
                # Keep trailing sentence punctuation from primary Greek surface form if any.
                trail = re.search(r"[.,;··;:!?]+$", grk)
                return (sp_form + (trail.group(0) if trail and sp_form[-1:] not in ".,;··;:!?" else "")), off
            return grk, off
    if mv and target_ed in mv:
        for entry in re.split(r"[‖¦|]", mv):
            parts = [p.strip() for p in entry.split("=")]
            if len(parts) >= 2 and target_ed in parts[0]:
                m_eds = re.split(r"\s*[;,]\s*", parts[0])
                m_forms = re.split(r"\s*[;,]\s*", parts[1])
                for idx, eg in enumerate(m_eds):
                    off = _tagnt_match_ed_group(eg, target_ed)
                    if off is not None:
                        form = m_forms[idx] if idx < len(m_forms) else m_forms[0]
                        form = form.replace("¶", "").strip()
                        if form and form != "-":
                            return form, off
    return None


@functools.lru_cache(maxsize=4)
def _tagnt_edition_index(path_str: str, _mtime: int, target_ed: str) -> Dict[str, BookText]:
    """Extract a specific Greek NT edition (``NA28`` or ``Tyn`` = THGNT) from STEPBible TAGNT (CC BY 4.0)."""
    base = Path(path_str)
    folder = base.parent if base.is_file() else base
    files = sorted(folder.glob("TAGNT *.txt"))
    if not files:
        return {}
    buckets: Dict[Tuple[str, int, int], List[Tuple[int, int, str]]] = {}
    row_seq: Dict[Tuple[str, int, int], int] = {}
    ref_re = re.compile(r"^\d+_([1-3]?[A-Za-z]{2,3})\.(\d+)\.(\d+)$")
    for fp in files:
        for line in read_text(fp).splitlines():
            if not line or line.startswith("#") or "\t" not in line:
                continue
            cols = line.split("\t")
            if len(cols) < 9:
                continue
            rm = ref_re.match(cols[0].strip())
            if not rm:
                continue
            usfm = _TAGNT_BOOK_TO_USFM.get(rm.group(1))
            if not usfm:
                continue
            key = (usfm, int(rm.group(2)), int(rm.group(3)))
            r_idx = row_seq.get(key, 0) + 1
            row_seq[key] = r_idx
            picked = _tagnt_pick_word(
                cols[2].strip(),
                cols[8].strip(),
                cols[9].strip() if len(cols) > 9 else "",
                cols[10].strip() if len(cols) > 10 else "",
                target_ed,
            )
            if picked:
                w, off = picked
                if w:
                    buckets.setdefault(key, []).append((r_idx + off, r_idx, w))
    out: Dict[str, BookText] = {}
    for (usfm, ch, v), items in buckets.items():
        items.sort(key=lambda t: (t[0], t[1]))
        txt = norm_ws(" ".join(w for _, _, w in items))
        if txt:
            out.setdefault(usfm, {}).setdefault(ch, {})[v] = txt
    return out


_TREGELLES_BOOK_TO_USFM: Dict[str, str] = {
    **_TAGNT_BOOK_TO_USFM,
    "Mar": "MRK", "Mark": "MRK", "Luke": "LUK", "Joh": "JHN", "John": "JHN",
    "Acts": "ACT", "Phi": "PHP", "Phl": "PHM",
    "1Pet": "1PE", "2Pet": "2PE", "1John": "1JN", "2John": "2JN", "3John": "3JN", "Jude": "JUD",
}


@functools.lru_cache(maxsize=2)
def _tregelles_txt_index(path_str: str, _mtime: int) -> Dict[str, BookText]:
    """Parse Tyndale House verse-per-line Tregelles 1857–1879 GNT (``verse-per-line/TNT.txt``)."""
    fp = Path(path_str)
    if not fp.exists():
        return {}
    out: Dict[str, BookText] = {}
    line_re = re.compile(r"^([1-3]?[A-Za-z]{2,6})\.(\d+):(\d+)\s+(.*)$")
    for line in read_text(fp).splitlines():
        m = line_re.match(line.strip())
        if not m:
            continue
        usfm = _TREGELLES_BOOK_TO_USFM.get(m.group(1))
        if not usfm:
            continue
        # Strip Tregelles's marginal alternate-reading brackets where single brackets enclose uncertain text.
        txt = norm_ws(re.sub(r"[\[\]]", "", m.group(4)))
        if txt:
            out.setdefault(usfm, {}).setdefault(int(m.group(2)), {})[int(m.group(3))] = txt
    return out


_ROBINSON_GREEK_MAP = str.maketrans({
    "a": "α", "b": "β", "g": "γ", "d": "δ", "e": "ε", "z": "ζ", "h": "η", "q": "θ",
    "i": "ι", "k": "κ", "l": "λ", "m": "μ", "n": "ν", "x": "ξ", "o": "ο", "p": "π",
    "r": "ρ", "s": "σ", "v": "ς", "t": "τ", "u": "υ", "f": "φ", "c": "χ", "y": "ψ", "w": "ω",
})

_ELZEVIR_USFM_TO_FILE: Dict[str, str] = {
    "MAT": "MT.UEL", "MRK": "MR.UEL", "LUK": "LU.UEL", "JHN": "JOH.UEL", "ACT": "AC.UEL",
    "ROM": "RO.UEL", "1CO": "1CO.UEL", "2CO": "2CO.UEL", "GAL": "GA.UEL", "EPH": "EPH.UEL",
    "PHP": "PHP.UEL", "COL": "COL.UEL", "1TH": "1TH.UEL", "2TH": "2TH.UEL",
    "1TI": "1TI.UEL", "2TI": "2TI.UEL", "TIT": "TIT.UEL", "PHM": "PHM.UEL", "HEB": "HEB.UEL",
    "JAS": "JAS.UEL", "1PE": "1PE.UEL", "2PE": "2PE.UEL",
    "1JN": "1JO.UEL", "2JN": "2JO.UEL", "3JN": "3JO.UEL", "JUD": "JUDE.UEL", "REV": "RE.UEL",
}


def _parse_elzevir_uel(base_dir: Path, book: BookSpec) -> BookText:
    """Parse Public-Domain Elzevir 1624 Textus Receptus Robinson ``.UEL`` files."""
    fname = _ELZEVIR_USFM_TO_FILE.get(book.usfm_code)
    if not fname:
        return {}
    fp = base_dir / fname
    if not fp.exists():
        fp = base_dir / "parsed" / fname
    if not fp.exists():
        return {}
    raw = read_text(fp)
    # Strip Strong's numbers, morph tags {N-NSM}, and variant markers; split on chapter:verse headers.
    out: Dict[int, Dict[int, List[str]]] = {}
    cur_ch, cur_v = 0, 0
    for line in raw.splitlines():
        s = re.sub(r"\{[^}]*\}", " ", line)
        for tok in s.split():
            cv = re.fullmatch(r"(\d+):(\d+)", tok)
            if cv:
                cur_ch, cur_v = int(cv.group(1)), int(cv.group(2))
                continue
            if not cur_ch or tok.isdigit() or not re.fullmatch(r"[a-zA-Z]+", tok):
                continue
            w = tok.lower().translate(_ROBINSON_GREEK_MAP)
            if w.endswith("σ"):
                w = w[:-1] + "ς"
            out.setdefault(cur_ch, {}).setdefault(cur_v, []).append(w)
    return {ch: {v: norm_ws(" ".join(ws)) for v, ws in vs.items() if ws} for ch, vs in out.items()}


def _load_tf_feature(fp: Path) -> Dict[int, str]:
    """Minimal stdlib Text-Fabric ``.tf`` node-feature reader (preserves empty-string data lines)."""
    out: Dict[int, str] = {}
    cur = 1
    in_data = False
    for line in read_text(fp).splitlines():
        if not in_data:
            if not line.strip():
                in_data = True
            continue
        if "\t" in line:
            left, val = line.split("\t", 1)
            if "-" in left:
                a, b = left.split("-", 1)
                for n in range(int(a), int(b) + 1):
                    out[n] = val
                cur = int(b) + 1
            else:
                n = int(left)
                out[n] = val
                cur = n + 1
        else:
            out[cur] = line
            cur += 1
    return out


def _tf_slot_bounds(spec: str) -> Tuple[int, int]:
    parts = spec.split(",")
    return int(parts[0].split("-")[0]), int(parts[-1].split("-")[-1])


_BHSA_BOOK_TO_USFM: Dict[str, str] = {
    "Genesis": "GEN", "Exodus": "EXO", "Leviticus": "LEV", "Numeri": "NUM", "Deuteronomium": "DEU",
    "Josua": "JOS", "Judices": "JDG", "Ruth": "RUT",
    "Samuel_I": "1SA", "Samuel_II": "2SA", "Reges_I": "1KI", "Reges_II": "2KI",
    "Chronica_I": "1CH", "Chronica_II": "2CH", "Esra": "EZR", "Nehemia": "NEH", "Esther": "EST",
    "Iob": "JOB", "Psalmi": "PSA", "Proverbia": "PRO", "Ecclesiastes": "ECC", "Canticum": "SNG",
    "Jesaia": "ISA", "Jeremia": "JER", "Threni": "LAM", "Ezechiel": "EZK", "Daniel": "DAN",
    "Hosea": "HOS", "Joel": "JOL", "Amos": "AMO", "Obadia": "OBA", "Jona": "JON",
    "Micha": "MIC", "Nahum": "NAM", "Habakuk": "HAB", "Zephania": "ZEP",
    "Haggai": "HAG", "Sacharia": "ZEC", "Maleachi": "MAL",
}


@functools.lru_cache(maxsize=2)
def _bhsa_tf_index(path_str: str, _mtime: int) -> Dict[str, BookText]:
    """Parse ETCBC BHSA 2021 Text-Fabric (Biblia Hebraica Stuttgartensia, 39 Hebrew OT books)."""
    tfd = Path(path_str)
    if not (tfd / "g_word_utf8.tf").exists():
        return {}
    otype = _load_tf_feature(tfd / "otype.tf")
    oslots = _load_tf_feature(tfd / "oslots.tf")
    book_f = _load_tf_feature(tfd / "book.tf")
    chap_f = _load_tf_feature(tfd / "chapter.tf")
    verse_f = _load_tf_feature(tfd / "verse.tf")
    gword = _load_tf_feature(tfd / "g_word_utf8.tf")
    trailer = _load_tf_feature(tfd / "trailer_utf8.tf")

    # Map slot ranges -> (book, chapter) via book/chapter nodes.
    books_by_slot: List[Tuple[int, int, str]] = []
    chaps_by_slot: List[Tuple[int, int, int]] = []
    verse_nodes: List[int] = []
    for n, ot in otype.items():
        if ot == "book":
            usfm = _BHSA_BOOK_TO_USFM.get(book_f.get(n, ""))
            if usfm and n in oslots:
                lo, hi = _tf_slot_bounds(oslots[n])
                books_by_slot.append((lo, hi, usfm))
        elif ot == "chapter":
            cs = chap_f.get(n, "")
            if cs.isdigit() and n in oslots:
                lo, hi = _tf_slot_bounds(oslots[n])
                chaps_by_slot.append((lo, hi, int(cs)))
        elif ot == "verse":
            verse_nodes.append(n)
    books_by_slot.sort()
    chaps_by_slot.sort()
    verse_nodes.sort()

    out: Dict[str, BookText] = {}
    bi = ci = 0
    for vn in verse_nodes:
        vs = verse_f.get(vn, "")
        if not vs.isdigit() or vn not in oslots:
            continue
        lo, hi = _tf_slot_bounds(oslots[vn])
        while bi < len(books_by_slot) and books_by_slot[bi][1] < lo:
            bi += 1
        while ci < len(chaps_by_slot) and chaps_by_slot[ci][1] < lo:
            ci += 1
        if bi >= len(books_by_slot) or ci >= len(chaps_by_slot):
            continue
        usfm = books_by_slot[bi][2]
        ch = chaps_by_slot[ci][2]
        raw_v = "".join(gword.get(s, "") + trailer.get(s, "") for s in range(lo, hi + 1))
        # Strip BHSA Masoretic parashah (פ / ס) and inverted-nun (נ) section markers (both mid-verse and final).
        txt = norm_ws(re.sub(r"(?:^|\s)[פסנ](?=\s|$)", " ", raw_v))
        if txt:
            out.setdefault(usfm, {}).setdefault(ch, {})[int(vs)] = txt
    return out


_SP_BOOK_TO_USFM: Dict[str, str] = {
    "Genesis": "GEN", "Exodus": "EXO", "Leviticus": "LEV", "Numbers": "NUM", "Deuteronomy": "DEU",
}


@functools.lru_cache(maxsize=2)
def _samaritan_tf_index(path_str: str, _mtime: int) -> Dict[str, BookText]:
    """Parse CACCHT/ETCBC Samaritan Pentateuch Text-Fabric v7.5.0 (Genesis–Deuteronomy)."""
    tfd = Path(path_str)
    if not (tfd / "sign.tf").exists():
        return {}
    otype = _load_tf_feature(tfd / "otype.tf")
    oslots = _load_tf_feature(tfd / "oslots.tf")
    book_f = _load_tf_feature(tfd / "book.tf")
    chap_f = _load_tf_feature(tfd / "chapter.tf")
    verse_f = _load_tf_feature(tfd / "verse.tf")
    sign_f = _load_tf_feature(tfd / "sign.tf")

    books_by_slot: List[Tuple[int, int, str]] = []
    chaps_by_slot: List[Tuple[int, int, int]] = []
    verse_nodes: List[int] = []
    for n, ot in otype.items():
        if ot == "book":
            usfm = _SP_BOOK_TO_USFM.get(book_f.get(n, ""))
            if usfm and n in oslots:
                lo, hi = _tf_slot_bounds(oslots[n])
                books_by_slot.append((lo, hi, usfm))
        elif ot == "chapter":
            cs = chap_f.get(n, "")
            if cs.isdigit() and n in oslots:
                lo, hi = _tf_slot_bounds(oslots[n])
                chaps_by_slot.append((lo, hi, int(cs)))
        elif ot == "verse":
            verse_nodes.append(n)
    books_by_slot.sort()
    chaps_by_slot.sort()
    verse_nodes.sort()

    out: Dict[str, BookText] = {}
    bi = ci = 0
    for vn in verse_nodes:
        vs = verse_f.get(vn, "")
        if not vs.isdigit() or vn not in oslots:
            continue
        lo, hi = _tf_slot_bounds(oslots[vn])
        while bi < len(books_by_slot) and books_by_slot[bi][1] < lo:
            bi += 1
        while ci < len(chaps_by_slot) and chaps_by_slot[ci][1] < lo:
            ci += 1
        if bi >= len(books_by_slot) or ci >= len(chaps_by_slot):
            continue
        txt = norm_ws("".join(sign_f.get(s, "") for s in range(lo, hi + 1)))
        if txt:
            out.setdefault(books_by_slot[bi][2], {}).setdefault(chaps_by_slot[ci][2], {})[int(vs)] = txt
    return out


_DSS_BOOK_TO_USFM: Dict[str, str] = {
    "Gen": "GEN", "Ex": "EXO", "Lev": "LEV", "Num": "NUM", "Deut": "DEU",
    "Josh": "JOS", "Judg": "JDG", "Ruth": "RUT", "1Sam": "1SA", "2Sam": "2SA",
    "1Kgs": "1KI", "2Kgs": "2KI", "Ezra": "EZR", "Job": "JOB", "Ps": "PSA",
    "Prov": "PRO", "Eccl": "ECC", "Song": "SNG", "Is": "ISA", "Jer": "JER",
    "Lam": "LAM", "Ezek": "EZK", "Dan": "DAN", "Hos": "HOS", "Joel": "JOL",
    "Amos": "AMO", "Obad": "OBA", "Jonah": "JON", "Mic": "MIC", "Nah": "NAM",
    "Hab": "HAB", "Zeph": "ZEP", "Hag": "HAG", "Zech": "ZEC", "Mal": "MAL",
}

_DSS_TARGET_SCROLLS = frozenset({
    "1Qisaa", "1Q8", "4Q51", "4Q70", "4Q71", "4Q72", "11Q5", "4Q22", "4Q27", "4Q41", "4Q44",
})

_DSS_KIND_TO_SCROLLS: Dict[str, Tuple[str, ...]] = {
    "dss_1qisaa": ("1Qisaa",),
    "dss_1qisab": ("1Q8",),
    "dss_4qsama": ("4Q51",),
    "dss_4qjer": ("4Q71", "4Q72", "4Q70"),
    "dss_11qpsa": ("11Q5",),
    "dss_torah": ("4Q22", "4Q27", "4Q41", "4Q44"),
}


def _clean_dss_word_stream(raw_chunks: List[Tuple[str, str]]) -> str:
    """Assemble DSS morpheme stream ``(full, after)`` into clean Hebrew words (reconstructed/broken -> GAP_WORD)."""
    # First join morphemes whose 'after' is empty into whole surface words.
    joined_words: List[str] = []
    cur: List[str] = []
    for full, after in raw_chunks:
        if full == "׃":
            if cur:
                joined_words.append("".join(cur) + "׃")
                cur = []
            elif joined_words and not joined_words[-1].endswith("׃"):
                joined_words[-1] += "׃"
            continue
        cur.append(full)
        # Standalone preposition מן (even when supralinearly corrected as מ(^ ן ^)) separates from the next word.
        bare = re.sub(r"[(\^\)\s]", "", full)
        if after or bare == "מן":
            joined_words.append("".join(cur))
            cur = []
    if cur:
        joined_words.append("".join(cur))

    out: List[str] = []
    for raw_w in joined_words:
        # Remove scribal erasures {{ ... }}.
        w = re.sub(r"\{\{.*?\}\}", "", raw_w)
        # Reconstructed brackets [...] or missing-word epsilon -> GAP_WORD (never invent Qumran text).
        if "[" in w or "]" in w or "ε" in w or "◦" in w:
            out.append(GAP_WORD)
            continue
        # Keep supralinear scribal insertions (^ ... ^), strip markup punctuation & morpheme geresh.
        w = w.replace("(^", "").replace("^)", "")
        w = re.sub(r"[׳#?╱\\/<>(){}\s]+", "", w)
        if not any("\u05d0" <= ch <= "\u05ea" for ch in w):
            continue
        out.append(unicodedata.normalize("NFC", w))

    if not any(t != GAP_WORD for t in out):
        return ""
    # Collapse runs of 3+ GAP_WORD to LACUNA_MARK.
    collapsed: List[str] = []
    i = 0
    while i < len(out):
        if out[i] == GAP_WORD:
            j = i
            while j < len(out) and out[j] == GAP_WORD:
                j += 1
            if j - i >= 3:
                if not collapsed or collapsed[-1] != LACUNA_MARK:
                    collapsed.append(LACUNA_MARK)
            else:
                collapsed.extend([GAP_WORD] * (j - i))
            i = j
        else:
            collapsed.append(out[i])
            i += 1
    return norm_ws(" ".join(collapsed))


@functools.lru_cache(maxsize=2)
def _dss_tf_index(path_str: str, _mtime: int) -> Tuple[Dict[str, Dict[str, BookText]], Dict[int, str]]:
    """Parse premier Biblical Dead Sea Scrolls (plus 11Q5 Col. XXVIII Hebrew Psalm 151) from ETCBC DSS TF."""
    tfd = Path(path_str)
    if not (tfd / "full.tf").exists():
        return {}, {}
    otype = _load_tf_feature(tfd / "otype.tf")
    oslots = _load_tf_feature(tfd / "oslots.tf")
    scroll_f = _load_tf_feature(tfd / "scroll.tf")
    book_f = _load_tf_feature(tfd / "book.tf")
    chap_f = _load_tf_feature(tfd / "chapter.tf")
    verse_f = _load_tf_feature(tfd / "verse.tf")
    full_f = _load_tf_feature(tfd / "full.tf")
    after_f = _load_tf_feature(tfd / "after.tf")

    # Map slot intervals for target scrolls (note: 11Q5 has both biblical and non-biblical scroll nodes).
    target_ranges: List[Tuple[int, int, str]] = []
    for n, ot in otype.items():
        if ot == "scroll":
            sn = scroll_f.get(n, "")
            if sn in _DSS_TARGET_SCROLLS and n in oslots:
                lo, hi = _tf_slot_bounds(oslots[n])
                target_ranges.append((lo, hi, sn))
    target_ranges.sort()

    word_nodes = sorted(n for n, ot in otype.items() if ot == "word")
    buckets: Dict[Tuple[str, str, int, int], List[Tuple[str, str]]] = {}
    q5_nonbib_words: List[Tuple[int, str, str]] = []

    import bisect
    starts = [r[0] for r in target_ranges]
    for w in word_nodes:
        sp = oslots.get(w)
        if not sp:
            continue
        wlo = int(sp.split(",")[0].split("-")[0])
        idx = bisect.bisect_right(starts, wlo) - 1
        if idx < 0:
            continue
        lo, hi, sname = target_ranges[idx]
        if wlo > hi:
            continue
        full = full_f.get(w, "")
        if not full:
            continue
        after = after_f.get(w, "")
        bk = book_f.get(w, "")
        if bk:
            usfm = _DSS_BOOK_TO_USFM.get(bk)
            ch_s, v_s = chap_f.get(w, ""), verse_f.get(w, "")
            if usfm and ch_s.isdigit() and v_s.isdigit():
                buckets.setdefault((sname, usfm, int(ch_s), int(v_s)), []).append((full, after))
        elif sname == "11Q5":
            q5_nonbib_words.append((w, full, after))

    out: Dict[str, Dict[str, BookText]] = {}
    for (sname, usfm, ch, v), chunks in buckets.items():
        txt = _clean_dss_word_stream(chunks)
        if txt:
            out.setdefault(sname, {}).setdefault(usfm, {}).setdefault(ch, {})[v] = txt

    # Extract Hebrew Psalm 151 (11Q5 Col. XXVIII) by exact incipit anchor ("הללו יה ל דויד בן ישי קטן הייתי").
    ps151: Dict[int, str] = {}
    for i in range(len(q5_nonbib_words) - 8):
        if (
            q5_nonbib_words[i][1] == "הללו"
            and q5_nonbib_words[i + 6][1] == "קטן"
            and q5_nonbib_words[i + 7][1] == "הייתי"
        ):
            # Split into canonical Psalm 151A (vv. 1–6) + 151B opening (v. 7) at the scroll's sof pasuq boundaries.
            tail = q5_nonbib_words[i:i + 185]
            clauses: List[List[Tuple[str, str]]] = [[]]
            for _wn, f, a in tail:
                clauses[-1].append((f, a))
                if f == "׃":
                    clauses.append([])
            # Map the 11 sof-pasuq strophes of 11Q5 Col. XXVIII onto standard LXX/Saints.Bible Psalm 151 vv. 1–7:
            # v1 = [0] (superscription + small among brothers), v2 = [1] (hands made pipe),
            # v3 = [2]+[3] (mountains/trees), v4 = [4]+[5] (who will declare / God saw all),
            # v5 = [6]+[7] (sent Samuel / brothers tall & handsome), v6 = [8]+[9] (took from flock & anointed),
            # v7 = [10]+[11] (Psalm 151B opening — Goliath/Philistine).
            groups = [[0], [1], [2, 3], [4, 5], [6, 7], [8, 9], [10, 11]]
            for vnum, idxs in enumerate(groups, start=1):
                seg: List[Tuple[str, str]] = []
                for ci in idxs:
                    if ci < len(clauses):
                        seg.extend(clauses[ci])
                txt = _clean_dss_word_stream(seg)
                if txt:
                    ps151[vnum] = txt
            break
    return out, ps151


def _parse_dss_scroll(base_path: Path, kind: str, book: BookSpec) -> BookText:
    scroll_map, ps151 = _dss_tf_index(*_mtime_key(base_path))
    if kind == "dss_11qpsa_ps151":
        if book.slug == "psalms" and ps151:
            return {151: dict(ps151)}
        return {}
    scrolls = _DSS_KIND_TO_SCROLLS.get(kind, ())
    merged: BookText = {}
    for sn in scrolls:
        bk = scroll_map.get(sn, {}).get(book.usfm_code, {})
        for ch, vs in bk.items():
            dest = merged.setdefault(ch, {})
            for v, txt in vs.items():
                if v not in dest:
                    dest[v] = txt
    return merged


_VL_JOHN_WITS = frozenset({"2", "3", "4", "6", "8", "10", "14", "15"})


@functools.lru_cache(maxsize=2)
def _vl_john_synopsis_index(path_str: str, _mtime: int) -> Dict[str, BookText]:
    """Parse ITSEE Vetus Latina Iohannes XML Synopsis (``VLsynopsis.xml``) for premier Old Latin John codices."""
    fp = Path(path_str)
    if not fp.exists():
        return {}
    raw = read_text(fp)
    out: Dict[str, BookText] = {}
    app_re = re.compile(r'<app\b[^>]*\bn="B04K(\d+)V(\d+)"[^>]*>(.*?)</app>', re.DOTALL)
    rdg_re = re.compile(r'<rdg\b[^>]*\bwit="([^"]+)"[^>]*>(.*?)</rdg>', re.DOTALL)
    for am in app_re.finditer(raw):
        ch, v = int(am.group(1)), int(am.group(2))
        if ch <= 0 or v <= 0:
            continue
        # Collect first-hand (N* preferred over undivided N; skip corrector NC).
        per_wit: Dict[str, Tuple[int, str]] = {}
        for rm in rdg_re.finditer(am.group(3)):
            wtag = rm.group(1).strip()
            base = wtag.rstrip("*")
            if base not in _VL_JOHN_WITS:
                continue
            prio = 2 if wtag.endswith("*") else 1
            if base in per_wit and per_wit[base][0] >= prio:
                continue
            txt = _clean_compaul_ab_fragment(rm.group(2))
            if txt:
                per_wit[base] = (prio, txt)
        for base, (_p, txt) in per_wit.items():
            out.setdefault(base, {}).setdefault(ch, {})[v] = txt
    return out


def _parse_divinum_psalter(psalm_dir: Path) -> BookText:
    """Parse Public-Domain DivinumOfficium Latin Psalter folder (e.g. ``Latin-Bea`` = 1945 *Psalterium Pianum*)."""
    if not psalm_dir.exists():
        return {}
    out: BookText = {}
    v_re = re.compile(r"^(\d+):(\d+)[a-z]?\s+(.*)$")
    for ch in range(1, 151):
        fp = psalm_dir / f"Psalm{ch}.txt"
        if not fp.exists():
            continue
        vs: Dict[int, List[str]] = {}
        for line in read_text(fp).splitlines():
            s = line.strip()
            if not s or s.startswith("("):
                continue
            m = v_re.match(s)
            if not m:
                continue
            v = int(m.group(2))
            # Remove liturgical flex (†) and mediant (*) pause markers.
            body = norm_ws(re.sub(r"[*†]", " ", m.group(3)))
            if body:
                vs.setdefault(v, []).append(body)
        if vs:
            out[ch] = {v: norm_ws(" ".join(parts)) for v, parts in vs.items()}
    return out


# ---------------------------------------------------------------------------
# User-supplied witnesses
# ---------------------------------------------------------------------------

def extract_text_preview(fp: Path, max_chars: int = 8000) -> Tuple[str, Dict[str, object]]:
    """Extract sample text & structural diagnostics from any uploaded witness file (including PDF)."""
    ext = fp.suffix.lower()
    meta: Dict[str, object] = {
        "extension": ext,
        "size_bytes": fp.stat().st_size if fp.exists() else 0,
        "detected_format": "unknown",
    }
    if not fp.exists():
        return "", meta

    if ext == ".pdf":
        meta["detected_format"] = "pdf"
        try:
            try:
                import pymupdf as fitz  # type: ignore
            except ImportError:
                import fitz  # type: ignore  # older PyMuPDF
            doc = fitz.open(str(fp))
            meta["page_count"] = len(doc)
            pages = [doc[i].get_text("text") for i in range(min(5, len(doc)))]
            doc.close()
            return "\n".join(pages)[:max_chars], meta
        except Exception as exc:
            meta["parse_error"] = str(exc)
            return "", meta

    raw = fp.read_text(encoding="utf-8", errors="replace")
    sample = raw[:max_chars]

    if ext in (".usfm", ".sfm") or "\\id " in sample or "\\v " in sample:
        meta["detected_format"] = "usfm"
    elif ext in (".xml", ".tei", ".osis", ".usfx") or sample.lstrip().startswith("<?xml") or "<TEI" in sample:
        if "<osis" in sample:
            meta["detected_format"] = "osis_xml"
        elif "<usfx" in sample or "<ve/>" in sample:
            meta["detected_format"] = "usfx_xml"
        else:
            meta["detected_format"] = "tei_xml"
    elif ext == ".json":
        meta["detected_format"] = "json"
    elif ext in (".tsv", ".csv"):
        meta["detected_format"] = "tabular"
    else:
        meta["detected_format"] = "plain_verse"
    return sample, meta


def parse_custom_witness_book(fp: Path, book: BookSpec) -> BookText:
    """Auto-parse a user-uploaded witness (.usfm, .usfx, .osis, .json, .tsv, .csv, .txt)."""
    if not fp.exists():
        return {}
    _sample, meta = extract_text_preview(fp, max_chars=4096)
    fmt = meta.get("detected_format")
    if fmt == "usfm":
        return parse_usfm_book(fp)
    if fmt == "usfx_xml":
        return _usfx_index(*_mtime_key(fp)).get(book.usfm_code, {})
    if fmt == "osis_xml":
        if book.testament == "NT" and 'osisIDWork="GK.' in _sample:
            return _tischendorf_osis_index(*_mtime_key(fp)).get(book.usfm_code, {})
        return _mam_index(*_mtime_key(fp)).get(book.usfm_code, {})
    if fmt == "tei_xml":
        if "COMPAUL" in _sample or 'xml:id="VL' in _sample:
            if not book.cntr_book or book.cntr_book < 40:
                return {}
            return _compaul_latin_index(*_mtime_key(fp)).get(book.cntr_book - 39, {})
        if "TEI-NTMSS" in _sample or 'type="nomSac"' in _sample or re.search(r'<ab\b[^>]*\bn="(?:B\d{2}K|[1-3]?[A-Za-z]+\.\d+\.)', _sample):
            if not book.cntr_book or book.cntr_book < 40:
                return {}
            return _intf_ntvmr_index(*_mtime_key(fp)).get(book.cntr_book - 39, {})
        if "<ms name=" in _sample and 'type="chap"' in _sample:
            return _bensira_tei_index(*_mtime_key(fp)) if book.slug == "sirach" else {}
        if "Amiatinus" in _sample or '<milestone unit="v"' in _sample:
            return _parse_amiatinus_tei(fp, book)

    raw = read_text(fp)
    out: BookText = {}
    if fmt == "json":
        try:
            obj = json.loads(raw)
        except ValueError:
            obj = None
        if isinstance(obj, dict) and "chapters" in obj:
            return _parse_latin_saints_json(fp)
        if isinstance(obj, dict):
            # {"1": {"1": "text"}}  (chapter → verse → text)
            for ch_key, ch_obj in obj.items():
                if str(ch_key).isdigit() and isinstance(ch_obj, dict):
                    for v_key, txt in ch_obj.items():
                        if str(v_key).isdigit() and str(txt).strip():
                            out.setdefault(int(ch_key), {})[int(v_key)] = norm_ws(str(txt))
            if out:
                return out

    book_aliases = {
        book.usfm_code.lower(),
        book.slug.lower(),
        book.title.lower().split("(")[0].strip(),
        (book.sbl_code or "").lower(),
    }
    book_aliases.discard("")
    for line in raw.splitlines():
        line_s = line.strip()
        if not line_s or line_s.startswith("#"):
            continue
        cols = line_s.split("\t")
        if len(cols) >= 4 and cols[1].isdigit() and cols[2].isdigit():  # BOOK \t CH \t V \t TEXT
            if cols[0].strip().lower() in book_aliases:
                out.setdefault(int(cols[1]), {})[int(cols[2])] = norm_ws(cols[3])
            continue
        m_bcv = re.match(r"^(\d{2})(\d{3})(\d{3})\s+(.*)$", line_s)  # CNTR 40001001 text
        if m_bcv:
            if book.cntr_book and int(m_bcv.group(1)) == book.cntr_book:
                body = m_bcv.group(4).strip()
                if body == "-":
                    out.setdefault(int(m_bcv.group(2)), {})[int(m_bcv.group(3))] = VERSE_ABSENT
                elif body and body != "+":
                    cleaned = clean_cntr_mss_line(body) if any(c in body for c in ("=", "/", "\\", "~", "{", "¯")) else _clean_cntr_edition_line(body)
                    if cleaned:
                        out.setdefault(int(m_bcv.group(2)), {})[int(m_bcv.group(3))] = cleaned
            continue
        m_ref = re.match(r"^([1-3]?\s*[A-Za-z][A-Za-z\- ]*?)\s+(\d+):(\d+)\s+(.*)$", line_s)  # Book C:V text
        if m_ref:
            if m_ref.group(1).strip().lower() in book_aliases:
                out.setdefault(int(m_ref.group(2)), {})[int(m_ref.group(3))] = norm_ws(m_ref.group(4))
            continue
        m_cv = re.match(r"^(\d+):(\d+)\s+(.*)$", line_s)  # C:V text
        if m_cv:
            out.setdefault(int(m_cv.group(1)), {})[int(m_cv.group(2))] = norm_ws(m_cv.group(3))
    return out


def parse_custom_witness_chapter(fp: Path, book: BookSpec, chapter: int) -> Dict[int, str]:
    return parse_custom_witness_book(fp, book).get(chapter, {})
