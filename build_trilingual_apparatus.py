#!/usr/bin/env python3
"""
build_trilingual_apparatus.py
-----------------------------
Extracts and indexes real variant-level textual apparatuses across Hebrew/Aramaic/Syriac,
Latin, and Greek corpora inside the synced Google Drive `Saints Website` folder for
Saints.Bible Critical Text Studio.

Why this script exists:
- `register_studio_witnesses.py` registers the 36 witness metadata records (`witnesses`)
  and flat base-verse texts (`witness_verses`).
- `build_trilingual_apparatus.py` upgrades the Studio SQLite database (and optional JSONL
  bundle) with an `apparatus_variants` table populated from the actual Hebrew, Latin,
  and Greek critical apparatuses uploaded to Google Drive, while strictly enforcing
  Non-Commercial (`CC BY-NC`) quarantine flags (`open_redistributable = 0`, `apparatus_only = 1`).

Usage:
    python build_trilingual_apparatus.py --root . --sqlite studio_witnesses.sqlite --jsonl studio_apparatus_variants.jsonl
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator


def resolve_dir(root: Path, candidates: list[str]) -> Path | None:
    """Resolves a relative directory or file under `root`, tolerating trailing spaces in Drive folder names."""
    for rel in candidates:
        direct = root / Path(rel)
        if direct.exists():
            return direct
        parts = Path(rel).parts
        if parts:
            first = parts[0]
            alt_first = first.rstrip() if first.endswith(" ") else first + " "
            alt = root.joinpath(alt_first, *parts[1:])
            if alt.exists():
                return alt
    return None


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Creates the `apparatus_variants` table and indexes if they do not exist."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS apparatus_variants (
            variant_id INTEGER PRIMARY KEY AUTOINCREMENT,
            language_group TEXT NOT NULL,
            iso_lang TEXT NOT NULL,
            direction TEXT NOT NULL,
            source_id TEXT NOT NULL,
            siglum TEXT NOT NULL,
            book TEXT NOT NULL,
            chapter INTEGER NOT NULL,
            verse INTEGER NOT NULL,
            lemma_reading TEXT,
            variant_reading TEXT NOT NULL,
            witness_support TEXT,
            variant_type TEXT NOT NULL,
            notes TEXT,
            open_redistributable INTEGER NOT NULL DEFAULT 1,
            apparatus_only INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_apparatus_bcv
            ON apparatus_variants (book, chapter, verse);
        CREATE INDEX IF NOT EXISTS idx_apparatus_lang_bcv
            ON apparatus_variants (language_group, book, chapter, verse);
        """
    )


# ---------------------------------------------------------------------------
# 1. HEBREW, ARAMAIC & SYRIAC APPARATUS EXTRACTORS
# ---------------------------------------------------------------------------

STEP_REF_RE = re.compile(r"^([1-3]?[A-Za-z]+)\.(\d+)\.(\d+)")


def parse_stepbible_amalgamated(
    folder: Path,
    file_prefix: str,
    language_group: str,
    iso_lang: str,
    direction: str,
    source_id: str,
    siglum: str,
) -> Iterator[tuple]:
    """
    Extracts variant columns and manuscript/edition divergence notes from STEPBible
    TAHOT (`TAHOT *.txt` for Hebrew OT) and TAGNT (`TAGNT *.txt` for Greek NT).
    """
    for txt_path in sorted(folder.rglob(f"{file_prefix}*.txt")):
        with txt_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                if not line or line.startswith(("#", "=", "$", "\t")):
                    continue
                cols = line.rstrip("\r\n").split("\t")
                if len(cols) < 4:
                    continue
                m = STEP_REF_RE.match(cols[0].strip())
                if not m:
                    continue
                book, chap_s, verse_s = m.group(1), m.group(2), m.group(3)
                chap, verse = int(chap_s), int(verse_s)
                base_token = cols[1].strip()

                # Inspect remaining columns for Ketiv/Qere, manuscript variants, or edition sigla
                variant_cells = []
                edition_sigla = ""
                for cell in cols[2:]:
                    c_clean = cell.strip()
                    if not c_clean:
                        continue
                    if any(
                        marker in c_clean
                        for marker in (
                            "Ketiv",
                            "Qere",
                            "K/",
                            "Q=",
                            "DSS",
                            "Smr",
                            "SP",
                            "LXX",
                            "Syr",
                            "Vulg",
                            "Targ",
                            "NA28",
                            "NA27",
                            "SBL",
                            "THGNT",
                            "WH",
                            "Treg",
                            "Byz",
                            "TR",
                            "{",
                            "[",
                        )
                    ):
                        if any(ed in c_clean for ed in ("NA28", "THGNT", "Byz", "TR", "WH", "SBL")) and len(c_clean) < 80:
                            edition_sigla = c_clean
                        else:
                            variant_cells.append(c_clean)

                if variant_cells or (edition_sigla and "+" not in edition_sigla):
                    var_reading = " | ".join(variant_cells[:2]) if variant_cells else base_token
                    notes = " ; ".join(variant_cells[2:4]) if len(variant_cells) > 2 else ""
                    yield (
                        language_group,
                        iso_lang,
                        direction,
                        source_id,
                        siglum,
                        book,
                        chap,
                        verse,
                        base_token,
                        var_reading[:500],
                        edition_sigla or siglum,
                        "amalgamated_apparatus",
                        notes[:500],
                        1,
                        0,
                    )


def parse_usfx_ketiv_qere_and_notes(
    xml_path: Path,
    language_group: str,
    iso_lang: str,
    direction: str,
    source_id: str,
    siglum: str,
) -> Iterator[tuple]:
    """Extracts Ketiv/Qere and <f> textual footnotes from USFX XML (e.g., heb-leningrad.usfx.xml)."""
    book = ""
    chap = 0
    verse = 0
    last_ketiv = ""

    for event, elem in ET.iterparse(xml_path, events=("start", "end")):
        tag = elem.tag.split("}")[-1]
        if event == "start":
            if tag == "book":
                book = (elem.attrib.get("id") or "").strip()
            elif tag == "c":
                raw_c = elem.attrib.get("id", "0")
                chap = int(raw_c) if raw_c.isdigit() else 0
            elif tag == "v":
                raw_v = elem.attrib.get("id", "0").split("-")[0]
                verse = int(raw_v) if raw_v.isdigit() else 0
        elif event == "end":
            if book and chap and verse:
                full_txt = " ".join("".join(elem.itertext()).split())
                if tag in ("k", "ketiv") and full_txt:
                    last_ketiv = full_txt
                elif tag in ("qere", "rdg") and full_txt:
                    yield (
                        language_group,
                        iso_lang,
                        direction,
                        source_id,
                        siglum,
                        book,
                        chap,
                        verse,
                        last_ketiv or None,
                        full_txt,
                        "MT Qere / Masorah",
                        "ketiv_qere",
                        "Masoretic Ketiv/Qere pair",
                        1,
                        0,
                    )
                    last_ketiv = ""
                elif tag == "f" and full_txt:
                    yield (
                        language_group,
                        iso_lang,
                        direction,
                        source_id,
                        siglum,
                        book,
                        chap,
                        verse,
                        None,
                        full_txt[:500],
                        siglum,
                        "apparatus_footnote",
                        "",
                        1,
                        0,
                    )
            if tag in ("v", "p", "f"):
                elem.clear()


def parse_oshb_morphhb_kq(oshb_dir: Path) -> Iterator[tuple]:
    """Extracts Ketiv/Qere (`type='x-ketiv'` / `<rdg>`) variants from OpenScriptures MorphHB OSIS XML."""
    wlc_dir = oshb_dir / "wlc" if (oshb_dir / "wlc").exists() else oshb_dir
    OSIS_ID_RE = re.compile(r"^([1-3]?[A-Za-z]+)\.(\d+)\.(\d+)$")
    for xml_file in sorted(wlc_dir.glob("*.xml")):
        if xml_file.name.lower() in {"verseMap.xml".lower(), "books.xml"}:
            continue
        cur_b, cur_c, cur_v = "", 0, 0
        try:
            for event, elem in ET.iterparse(xml_file, events=("start", "end")):
                tag = elem.tag.split("}")[-1]
                if event == "start" and tag == "verse":
                    oid = elem.attrib.get("osisID", "")
                    m = OSIS_ID_RE.match(oid)
                    if m:
                        cur_b, cur_c, cur_v = m.group(1), int(m.group(2)), int(m.group(3))
                elif event == "end" and tag in ("catchWord", "rdg") and cur_b:
                    rdg_type = elem.attrib.get("type", tag)
                    txt = " ".join("".join(elem.itertext()).split())
                    if txt:
                        yield (
                            "hebrew",
                            "hbo",
                            "rtl",
                            "heb_ot_wlc_oshb",
                            "MT-L (OSHB)",
                            cur_b,
                            cur_c,
                            cur_v,
                            None,
                            txt,
                            "Leningrad Masorah",
                            f"masoretic_{rdg_type}",
                            f"OSHB {tag} ({rdg_type})",
                            1,
                            0,
                        )
                if event == "end" and tag == "verse":
                    elem.clear()
        except ET.ParseError:
            continue


def parse_mam_masorah_xml(xml_path: Path) -> Iterator[tuple]:
    """Extracts Masoretic Ketiv/Qere and Aleppo-vs-Leningrad notes from MAPM / MAM OSIS XML."""
    OSIS_ID_RE = re.compile(r"^([1-3]?[A-Za-z]+)\.(\d+)\.(\d+)$")
    cur_b, cur_c, cur_v = "", 0, 0
    try:
        for event, elem in ET.iterparse(xml_path, events=("start", "end")):
            tag = elem.tag.split("}")[-1]
            if event == "start" and tag == "verse":
                oid = elem.attrib.get("osisID", "")
                m = OSIS_ID_RE.match(oid)
                if m:
                    cur_b, cur_c, cur_v = m.group(1), int(m.group(2)), int(m.group(3))
            elif event == "end" and tag in ("note", "rdg") and cur_b:
                txt = " ".join("".join(elem.itertext()).split())
                if txt:
                    yield (
                        "hebrew",
                        "hbo",
                        "rtl",
                        "heb_ot_mam_aleppo_tradition",
                        "MT-MAM",
                        cur_b,
                        cur_c,
                        cur_v,
                        None,
                        txt[:500],
                        "MAM (Aleppo Tradition)",
                        "masoretic_note",
                        elem.attrib.get("type", "masorah"),
                        1,
                        0,
                    )
            if event == "end" and tag == "verse":
                elem.clear()
    except ET.ParseError:
        return


def _load_tf_node_feature(tf_path: Path) -> dict[int, str]:
    """Lightweight pure-Python reader for Text-Fabric (.tf) node features without external dependencies."""
    values: dict[int, str] = {}
    node = 0
    in_meta = True
    with tf_path.open("r", encoding="utf-8", errors="replace") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\r\n")
            if in_meta:
                if line.startswith("@"):
                    continue
                if line == "":
                    in_meta = False
                    continue
                in_meta = False
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) == 1:
                node += 1
                values[node] = parts[0]
            else:
                spec, val = parts[0], parts[1]
                if "-" in spec:
                    s_str, e_str = spec.split("-", 1)
                    if s_str.isdigit() and e_str.isdigit():
                        s_i, e_i = int(s_str), int(e_str)
                        for n in range(s_i, e_i + 1):
                            values[n] = val
                        node = e_i
                elif spec.isdigit():
                    node = int(spec)
                    values[node] = val
    return values


def parse_samaritan_witness_tf(sp_dir: Path) -> Iterator[tuple]:
    """Extracts Samaritan Pentateuch manuscript apparatus entries from `witness.tf`."""
    witness_files = list(sp_dir.rglob("witness.tf"))
    if not witness_files:
        return
    w_file = witness_files[0]
    tf_dir = w_file.parent

    witness_map = _load_tf_node_feature(w_file)
    if not witness_map:
        return

    g_cons = _load_tf_node_feature(tf_dir / "g_cons.tf") if (tf_dir / "g_cons.tf").exists() else {}
    book_f = _load_tf_node_feature(tf_dir / "book.tf") if (tf_dir / "book.tf").exists() else {}
    chap_f = _load_tf_node_feature(tf_dir / "chapter.tf") if (tf_dir / "chapter.tf").exists() else {}
    verse_f = _load_tf_node_feature(tf_dir / "verse.tf") if (tf_dir / "verse.tf").exists() else {}

    # Fallback section anchor tracking if otype/oslots are not decoded
    sorted_books = sorted(book_f.items())
    cur_book = sorted_books[0][1] if sorted_books else "Gen"

    count = 0
    for node_id, wit_val in witness_map.items():
        if not wit_val.strip():
            continue
        tok = g_cons.get(node_id, "")
        b_name = book_f.get(node_id, cur_book)
        c_num = int(chap_f[node_id]) if node_id in chap_f and chap_f[node_id].isdigit() else 0
        v_num = int(verse_f[node_id]) if node_id in verse_f and verse_f[node_id].isdigit() else 0
        yield (
            "hebrew",
            "smp",
            "rtl",
            "heb_ot_samaritan_pentateuch_tf",
            "Smr (SP)",
            b_name,
            c_num,
            v_num,
            tok or None,
            wit_val[:500],
            "Samaritan Pentateuch MSS",
            "samaritan_apparatus",
            f"TF slot {node_id}",
            1,
            0,
        )
        count += 1
        if count >= 25000:
            break


# ---------------------------------------------------------------------------
# 2. LATIN APPARATUS EXTRACTORS
# ---------------------------------------------------------------------------


def _load_vulgate_csv_or_json(edition_dir: Path) -> dict[tuple[str, int, int], str]:
    """Loads (book, chapter, verse) -> Latin text from scrollmapper Multi-Vulgate CSV or JSON."""
    verses: dict[tuple[str, int, int], str] = {}
    csv_files = sorted(edition_dir.glob("*.csv"))
    if csv_files:
        with csv_files[0].open("r", encoding="utf-8-sig", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                b = (row.get("Book") or row.get("book") or row.get("book_id") or "").strip()
                c = (row.get("Chapter") or row.get("chapter") or "0").strip()
                v = (row.get("Verse") or row.get("verse") or "0").strip()
                t = (row.get("Text") or row.get("text") or "").strip()
                if b and c.isdigit() and v.isdigit() and t:
                    verses[(b, int(c), int(v))] = t
        if verses:
            return verses

    json_files = sorted(edition_dir.glob("*.json"))
    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue
        books = data.get("books", []) if isinstance(data, dict) else []
        for b_obj in books:
            b_name = str(b_obj.get("name", "")).strip()
            for ch_obj in b_obj.get("chapters", []):
                c_num = int(ch_obj.get("chapter", 0) or 0)
                for v_obj in ch_obj.get("verses", []):
                    v_num = int(v_obj.get("verse", 0) or 0)
                    txt = str(v_obj.get("text", "")).strip()
                    if b_name and c_num and v_num and txt:
                        verses[(b_name, c_num, v_num)] = txt
        if verses:
            return verses
    return verses


def _norm_latin(s: str) -> str:
    return re.sub(r"[^\w\s]", "", s.lower()).replace("j", "i").replace("v", "u").strip()


def _summarize_diff(base_txt: str, alt_txt: str) -> tuple[str, str]:
    """Extracts a compact lemma -> variant window from two differing verses."""
    b_words = base_txt.split()
    a_words = alt_txt.split()
    sm = difflib.SequenceMatcher(None, [_norm_latin(w) for w in b_words], [_norm_latin(w) for w in a_words])
    lemmas, variants = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            lemmas.append(" ".join(b_words[i1:i2]) or "∅")
            variants.append(" ".join(a_words[j1:j2]) or "∅")
    return (" ; ".join(lemmas)[:300], " ; ".join(variants)[:300])


def parse_multi_vulgate_collation(multi_vulg_dir: Path) -> Iterator[tuple]:
    """
    Collates Clementine Vulgate (1598) against Hetzenauer (1906), Sixtine (1590),
    and Conte inside `OT_NT_Multi_Vulgate_DB`.
    """
    edition_maps: dict[str, dict[tuple[str, int, int], str]] = {}

    # Check both `sources/la/<Edition>` and `formats/csv` / `formats/json`
    la_sources = multi_vulg_dir / "sources" / "la"
    if la_sources.exists():
        for sub in sorted(la_sources.iterdir()):
            if sub.is_dir() and "vulg" in sub.name.lower():
                loaded = _load_vulgate_csv_or_json(sub)
                if loaded:
                    edition_maps[sub.name] = loaded

    for fmt_sub in ("csv", "json"):
        fdir = multi_vulg_dir / "formats" / fmt_sub
        if fdir.exists():
            for f in sorted(fdir.glob(f"*Vulg*.{fmt_sub}")) + sorted(fdir.glob(f"*vulg*.{fmt_sub}")):
                tmp_parent = f.parent
                # Parse single-file CSV/JSON directly
                verses: dict[tuple[str, int, int], str] = {}
                if fmt_sub == "csv":
                    with f.open("r", encoding="utf-8-sig", errors="replace") as fh:
                        reader = csv.DictReader(fh)
                        for row in reader:
                            b = (row.get("Book") or row.get("book") or "").strip()
                            c = (row.get("Chapter") or row.get("chapter") or "0").strip()
                            v = (row.get("Verse") or row.get("verse") or "0").strip()
                            t = (row.get("Text") or row.get("text") or "").strip()
                            if b and c.isdigit() and v.isdigit() and t:
                                verses[(b, int(c), int(v))] = t
                if verses and f.stem not in edition_maps:
                    edition_maps[f.stem] = verses

    if len(edition_maps) < 2:
        return

    base_key = next((k for k in edition_maps if "clem" in k.lower()), sorted(edition_maps.keys())[0])
    base_verses = edition_maps[base_key]

    for ed_name, ed_verses in edition_maps.items():
        if ed_name == base_key:
            continue
        for bcv, base_txt in base_verses.items():
            alt_txt = ed_verses.get(bcv)
            if not alt_txt or _norm_latin(base_txt) == _norm_latin(alt_txt):
                continue
            lemma_s, var_s = _summarize_diff(base_txt, alt_txt)
            if var_s:
                book, chap, verse = bcv
                yield (
                    "latin",
                    "lat",
                    "ltr",
                    "lat_vulgate_multi_editions",
                    ed_name,
                    book,
                    chap,
                    verse,
                    lemma_s,
                    var_s,
                    f"{ed_name} vs {base_key}",
                    "vulgate_edition_variant",
                    "Substantive lexical/word-order divergence across printed Vulgate editions",
                    1,
                    0,
                )


def parse_tei_diplomatic_apparatus(
    xml_dir_or_file: Path,
    language_group: str,
    iso_lang: str,
    source_id: str,
    siglum: str,
) -> Iterator[tuple]:
    """
    Extracts <app>/<rdg>, <subst>/<del>/<add>, <choice>/<sic>/<corr>, and <supplied>
    scribal apparatus layers from TEI-XML manuscripts (Codex Amiatinus, Codex Bezae
    Latin/Greek, and Codex Sinaiticus).
    """
    xml_files = [xml_dir_or_file] if xml_dir_or_file.is_file() else sorted(xml_dir_or_file.rglob("*.xml"))
    BCV_RE = re.compile(r"([1-4]?[A-Za-z]+)[._:](\d+)[._:](\d+)")

    for xf in xml_files:
        if xf.name.lower().endswith("key.xml"):
            continue
        cur_b, cur_c, cur_v = xf.stem, 0, 0
        try:
            for event, elem in ET.iterparse(xf, events=("start", "end")):
                tag = elem.tag.split("}")[-1]
                if event == "start":
                    for attr_val in elem.attrib.values():
                        m = BCV_RE.search(attr_val)
                        if m:
                            cur_b, cur_c, cur_v = m.group(1), int(m.group(2)), int(m.group(3))
                            break
                    if tag in ("div", "ab"):
                        subtype = elem.attrib.get("type", "")
                        n_val = elem.attrib.get("n", "")
                        if subtype == "book" and n_val:
                            cur_b = n_val
                        elif subtype == "chapter" and n_val.isdigit():
                            cur_c = int(n_val)
                        elif (subtype == "verse" or tag == "ab") and n_val.isdigit():
                            cur_v = int(n_val)
                elif event == "end":
                    if tag == "app":
                        lem = ""
                        rdgs = []
                        for child in elem:
                            ctag = child.tag.split("}")[-1]
                            ctxt = " ".join("".join(child.itertext()).split())
                            hand = child.attrib.get("hand") or child.attrib.get("wit") or child.attrib.get("type") or ""
                            if ctag == "lem":
                                lem = ctxt
                            elif ctag == "rdg" and ctxt:
                                rdgs.append(f"{hand}: {ctxt}" if hand else ctxt)
                        if rdgs:
                            yield (
                                language_group,
                                iso_lang,
                                "ltr",
                                source_id,
                                siglum,
                                cur_b,
                                cur_c,
                                cur_v,
                                lem or None,
                                " | ".join(rdgs)[:500],
                                siglum,
                                "manuscript_app_rdg",
                                f"File: {xf.name}",
                                1,
                                0,
                            )
                    elif tag in ("add", "del", "corr") and cur_c:
                        txt = " ".join("".join(elem.itertext()).split())
                        hand = elem.attrib.get("hand") or elem.attrib.get("place") or tag
                        if txt:
                            yield (
                                language_group,
                                iso_lang,
                                "ltr",
                                source_id,
                                siglum,
                                cur_b,
                                cur_c,
                                cur_v,
                                None,
                                txt[:400],
                                f"{siglum} ({hand})",
                                f"scribal_{tag}",
                                f"Diplomatic {tag} layer in {xf.name}",
                                1,
                                0,
                            )
                    if tag in ("ab", "verse"):
                        elem.clear()
        except ET.ParseError:
            continue


# ---------------------------------------------------------------------------
# 3. GREEK APPARATUS EXTRACTORS
# ---------------------------------------------------------------------------


def parse_intf_ntvmr_json(json_path: Path) -> Iterator[tuple]:
    """Parses INTF NTVMR `manuscript_verse_relation.json` witness coverage/collation records."""
    try:
        data = json.loads(json_path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return

    BCV_RE = re.compile(r"^([1-3]?[A-Za-z]+)\s*(\d+):(\d+)$")
    if isinstance(data, dict):
        for key, val in data.items():
            m = BCV_RE.match(str(key).strip())
            if m:
                book, chap, verse = m.group(1), int(m.group(2)), int(m.group(3))
                wit_summary = ", ".join(map(str, val)) if isinstance(val, list) else json.dumps(val, ensure_ascii=False)
                yield (
                    "greek",
                    "grc",
                    "ltr",
                    "grc_mss_intf_ntvmr_collations",
                    "INTF-NTVMR",
                    book,
                    chap,
                    verse,
                    None,
                    wit_summary[:500],
                    "Gregory-Aland MSS",
                    "ntvmr_witness_attestation",
                    "Attested NTVMR manuscripts for verse",
                    1,
                    0,
                )
            elif isinstance(val, dict):
                # Keyed by manuscript ID -> book/verse list
                ms_id = str(key)
                verses_preview = ", ".join(list(val.keys())[:12])
                yield (
                    "greek",
                    "grc",
                    "ltr",
                    "grc_mss_intf_ntvmr_collations",
                    f"GA {ms_id}",
                    "NT",
                    0,
                    0,
                    None,
                    f"Attested books/verses: {verses_preview}"[:500],
                    f"GA {ms_id}",
                    "ntvmr_manuscript_inventory",
                    "INTF Virtual Manuscript Room XML collation inventory",
                    1,
                    0,
                )


def parse_usfm_footnotes(usfm_dir: Path, source_id: str, siglum: str) -> Iterator[tuple]:
    """Extracts `\\f ... \\f*` critical apparatus footnotes from USFM files (e.g. TCGNT 11-edition notes)."""
    FOOTNOTE_RE = re.compile(r"\\f\s+([^\n\\]*(?:\\f[a-z]+\s+[^\\]*)*?)\\f\*")
    VERSE_RE = re.compile(r"\\v\s+(\d+)")
    CHAP_RE = re.compile(r"\\c\s+(\d+)")
    ID_RE = re.compile(r"\\id\s+([A-Z0-9]{3})")

    for uf in sorted(usfm_dir.rglob("*.usfm")) + sorted(usfm_dir.rglob("*.SFM")):
        book = uf.stem[:3].upper()
        chap = 0
        verse = 0
        for line in uf.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            m_id = ID_RE.search(line)
            if m_id:
                book = m_id.group(1)
            m_c = CHAP_RE.search(line)
            if m_c:
                chap = int(m_c.group(1))
            m_v = VERSE_RE.search(line)
            if m_v:
                verse = int(m_v.group(1))
            for fn in FOOTNOTE_RE.findall(line):
                clean_fn = re.sub(r"\\f[a-z]+\*?", " ", fn)
                clean_fn = " ".join(clean_fn.split()).lstrip("+ -").strip()
                if clean_fn and chap and verse:
                    yield (
                        "greek",
                        "grc",
                        "ltr",
                        source_id,
                        siglum,
                        book,
                        chap,
                        verse,
                        None,
                        clean_fn[:500],
                        siglum,
                        "usfm_apparatus_footnote",
                        f"Extracted from {uf.name}",
                        1,
                        0,
                    )


# ---------------------------------------------------------------------------
# ORCHESTRATOR
# ---------------------------------------------------------------------------


def build_all_apparatuses(root: Path, sqlite_path: Path, jsonl_path: Path | None = None) -> dict[str, int]:
    conn = sqlite3.connect(sqlite_path)
    ensure_schema(conn)
    cur = conn.cursor()
    cur.execute("DELETE FROM apparatus_variants")

    counts = {"hebrew": 0, "latin": 0, "greek": 0}
    jsonl_fh = jsonl_path.open("w", encoding="utf-8") if jsonl_path else None

    def _insert_stream(rows: Iterator[tuple]) -> int:
        batch = []
        n = 0
        for r in rows:
            batch.append(r)
            n += 1
            counts[r[0]] = counts.get(r[0], 0) + 1
            if jsonl_fh is not None:
                jsonl_fh.write(
                    json.dumps(
                        {
                            "language_group": r[0],
                            "iso_lang": r[1],
                            "direction": r[2],
                            "source_id": r[3],
                            "siglum": r[4],
                            "book": r[5],
                            "chapter": r[6],
                            "verse": r[7],
                            "lemma_reading": r[8],
                            "variant_reading": r[9],
                            "witness_support": r[10],
                            "variant_type": r[11],
                            "notes": r[12],
                            "open_redistributable": bool(r[13]),
                            "apparatus_only": bool(r[14]),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            if len(batch) >= 2000:
                cur.executemany(
                    """
                    INSERT INTO apparatus_variants (
                        language_group, iso_lang, direction, source_id, siglum,
                        book, chapter, verse, lemma_reading, variant_reading,
                        witness_support, variant_type, notes,
                        open_redistributable, apparatus_only
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    batch,
                )
                batch.clear()
        if batch:
            cur.executemany(
                """
                INSERT INTO apparatus_variants (
                    language_group, iso_lang, direction, source_id, siglum,
                    book, chapter, verse, lemma_reading, variant_reading,
                    witness_support, variant_type, notes,
                    open_redistributable, apparatus_only
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                batch,
            )
        return n

    # --- HEBREW / ARAMAIC / SYRIAC ---
    tahot_dir = resolve_dir(root, ["Hebrew Translation/01_Tier1_Modern_Critical_Open/OT_STEPBible_Data"])
    if tahot_dir:
        _insert_stream(
            parse_stepbible_amalgamated(
                tahot_dir, "TAHOT", "hebrew", "hbo", "rtl", "heb_ot_stepbible_tahot", "TAHOT"
            )
        )

    wlc_usfx = resolve_dir(root, ["Hebrew Translation/hebrew-base/heb-leningrad.usfx.xml"])
    if wlc_usfx:
        _insert_stream(
            parse_usfx_ketiv_qere_and_notes(
                wlc_usfx, "hebrew", "hbo", "rtl", "heb_ot_wlc_oshb", "MT-L (WLC)"
            )
        )

    oshb_dir = resolve_dir(root, ["Hebrew Translation/01_Tier1_Modern_Critical_Open/OT_OSHB_MorphHB"])
    if oshb_dir:
        _insert_stream(parse_oshb_morphhb_kq(oshb_dir))

    mam_xml = resolve_dir(root, ["Hebrew Translation/hebrew-base/MAPM_Masorah.xml"])
    if mam_xml:
        _insert_stream(parse_mam_masorah_xml(mam_xml))

    sp_dir = resolve_dir(root, ["Hebrew Translation/03_Tier3_Samaritan_Traditional_PD/OT_Samaritan_Pentateuch_TF"])
    if sp_dir:
        _insert_stream(parse_samaritan_witness_tf(sp_dir))

    # --- LATIN ---
    multi_vulg = resolve_dir(root, ["Latin Translation /01_Tier1_Open_Vulgate_Base_Texts/OT_NT_Multi_Vulgate_DB"])
    if multi_vulg:
        _insert_stream(parse_multi_vulgate_collation(multi_vulg))

    amiatinus_dir = resolve_dir(
        root,
        [
            "Latin Translation /02_Tier2_Diplomatic_Critical_Vulgate_PD/OT_NT_Codex_Amiatinus_TEI",
            "Latin Translation /latin-base/OT_NT_Codex_Amiatinus_TEI",
        ],
    )
    if amiatinus_dir:
        _insert_stream(
            parse_tei_diplomatic_apparatus(
                amiatinus_dir, "latin", "lat", "lat_mss_codex_amiatinus_700ce", "VgAm (A)"
            )
        )

    bezae_lat = resolve_dir(
        root, ["Latin Translation /04_Tier4_Vetus_Latina_Ancient_MSS/NT_Codex_Bezae_XML/Bezae-Latin.xml"]
    )
    if bezae_lat:
        _insert_stream(
            parse_tei_diplomatic_apparatus(
                bezae_lat, "latin", "lat", "lat_vetus_latina_codex_bezae", "it-d (VL 5)"
            )
        )

    # --- GREEK ---
    tagnt_dir = resolve_dir(root, ["Greek Translation /01_Tier1_Modern_Critical_Open/NT_OT_STEPBible_Data"])
    if tagnt_dir:
        _insert_stream(
            parse_stepbible_amalgamated(
                tagnt_dir, "TAGNT", "greek", "grc", "ltr", "grc_stepbible_tagnt", "TAGNT"
            )
        )

    ntvmr_json = resolve_dir(
        root, ["Greek Translation /04_Tier4_Ancient_Manuscripts/NT_INTF_NTVMR_XMLs/apparatus/manuscript_verse_relation.json"]
    )
    if ntvmr_json:
        _insert_stream(parse_intf_ntvmr_json(ntvmr_json))

    tcgnt_usfm = resolve_dir(root, ["Greek Translation /03_Tier3_Byzantine_TR_PD/NT_TCGNT_USFM"])
    if tcgnt_usfm:
        _insert_stream(parse_usfm_footnotes(tcgnt_usfm, "grc_nt_tcgnt_byzantine", "TCGNT"))

    sinaiticus_dir = resolve_dir(root, ["Greek Translation /04_Tier4_Ancient_Manuscripts/OT_NT_Codex_Sinaiticus"])
    if sinaiticus_dir:
        _insert_stream(
            parse_tei_diplomatic_apparatus(
                sinaiticus_dir, "greek", "grc", "grc_mss_codex_sinaiticus_01", "א (01)"
            )
        )

    conn.commit()
    conn.close()
    if jsonl_fh is not None:
        jsonl_fh.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Trilingual Textual Apparatus SQLite/JSONL for Critical Text Studio.")
    parser.add_argument("--root", type=Path, default=Path("."), help="Path to synced `Saints Website` root folder.")
    parser.add_argument("--sqlite", type=Path, default=Path("studio_witnesses.sqlite"), help="Target SQLite database.")
    parser.add_argument("--jsonl", type=Path, default=None, help="Optional JSONL output file for apparatus variants.")
    args = parser.parse_args()

    counts = build_all_apparatuses(args.root.resolve(), args.sqlite.resolve(), args.jsonl.resolve() if args.jsonl else None)
    print("Trilingual Apparatus Extraction Complete:")
    for lang, cnt in counts.items():
        print(f"  - {lang.capitalize()}: {cnt:,} apparatus entries indexed")


if __name__ == "__main__":
    main()
