"""Website export of the Saints Concordance word layer (18 Nov 2026; spec docs/CONCORDANCE-SITE-SPEC.md).

Writes, next to the lemma packs of ``concordance_gold.export_gold_pack``:

* ``books.json``                         chapter URLs from the site's own books.json (english-numbering)
* ``morph-{heb,grc,lat}.json``           parse legends from the taggers' ``morph_legend()``
* ``book/en/{NN}-{slug}.json.gz``        the English columns of the book, by unit, with hashes
* ``book/{lang}/{NN}-{slug}.json.gz``    every word of the critical text of the book in Saints verse order
                                          (lemma, parse, content/function flag) + the English alignment

* ``book/ct-{lang}/{NN}-{slug}.json.gz`` the Saints Critical Text of the book (19 Nov 2026; spec
                                          docs/CRITICAL-TEXT-AND-WORKSPACE-SPEC.md in the plugin repo, 1-1b):
                                          every source verse with text, placed or not, with its own reference
* ``critical-texts.json``                editions, numbering, credits, legend (one small file)

Word positions come only from ``concordance_layer.saints_verses``; alignments from
``concordance_align``.  Lemmas are referred to by ``lexical_stems.stem_id`` (function-word lemmas get
lexicon rows here if the build has none, so every id resolves in the lemma packs).

Since 19 Nov 2026 the word-layer verse rows carry no text (``verses[i][3] == ""``): the decoder fills it
from the critical-text file of the same export (``" ".join`` of the segments).  A row keeps its text only
when the critical-text file cannot reproduce it exactly (counted as ``ct_text_kept``; 0 today).

Critical-text file layout (``CT_LAYOUT``).  ``"compact"`` (written; schema ``saints-critical-text/v2``)
saves about 0.5 MB gz over the spec's ``verses`` rows so the plugin ZIP stays under the upload limit::

    {"schema": "saints-critical-text/v2", "lang", "book", "order", "edition", "numbering", "notes",
     "start": [[i, ch, v], ...],   # verse i has Saints (ch, v); a verse not listed = previous verse + 1
     "src":   {"i": "23:1", ...},  # source refs where they differ from "ch:v"
     "text":  [str | [str, ...]],  # one entry per verse (array = one string per src ref)
     "unplaced": [[afterCh, afterV, src, text, reason], ...]}

``expand_compact_ct`` (and the decoder) turn it into the spec's v1 rows ``verses: [[ch, v, src, text]]``;
``CT_LAYOUT = "verses"`` writes those rows directly (schema ``saints-critical-text/v1``).

Word-layer layout (``WL_LAYOUT``).  ``"compact"`` (written; schema ``saints-concordance-book/v2``) saves
about 0.7 MB gz more (19 Nov 2026 the plugin ZIP was projected at 20.0 MB without it): the same fields as
v1 except

    "vstart": [[i, ch, v], ...], "vsrc": {"i": src}, "vn": [nTokens, ...]   instead of "verses"
        (rows rebuilt as [ch, v, src, "", n] exactly like the critical-text "start"/"src" above)
    "Fl": [flag per entry of "lemma"]                                       instead of "F"
        (F[i] = L[i] ? Fl[L[i] - 1] : 0; written only when every token of a lemma in the book has the
         same flag, else "F" stays)

``expand_word_layer`` (and the decoder) rebuild ``verses`` and ``F``; ``WL_LAYOUT = "rows"`` writes v1.
"""

from __future__ import annotations

import gzip
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .catalog import BOOKS, BOOKS_BY_SLUG

SITE_BOOKS_JSON = Path(
    os.environ.get(
        "SAINTS_SITE_BOOKS_JSON",
        str(Path.home() / "Website" / "english-numbering-2026-11-16" / "production" / "books.json"),
    )
)
LANGS = ("hebrew", "greek", "latin")
CODE = {"hebrew": "heb", "greek": "grc", "latin": "lat"}
EN_COLUMN = {"greek": "saints", "hebrew": "hebrew", "latin": "latin"}
LICENCE = {"heb": "CC BY 4.0", "grc": "CC BY-SA 4.0", "lat": "CC BY-SA 4.0"}
MORPH_SCHEME = {"heb": "O (OSHB)",
                "grc": "R (STEPBible TAGNT / Robinson; New Testament) + A (GLAUx AGDT postag; Septuagint, mostly machine-annotated)",
                "lat": "L (Latin paradigm class|ending)"}


# --- Saints Critical Texts (19 Nov 2026) -------------------------------------------------------------

CT_LAYOUT = "compact"            # or "verses" (spec v1 rows); see the module docstring
CT_SCHEMA = {"compact": "saints-critical-text/v2", "verses": "saints-critical-text/v1"}
CT_EDITION = {"heb": "Saints Hebrew Critical Text", "grc": "Saints Greek Critical Text",
              "lat": "Saints Latin Critical Text"}
CT_SHORT = {"heb": "Hebrew", "grc": "Greek", "lat": "Latin"}
CT_NUMBERING = {"heb": "Masoretic (MT) verse numbers",
                "grc": "Studio Greek verse numbers (Swete in the Old Testament)",
                "lat": "Saints Latin column verse numbers (Vulgate numbers in places)"}
# Prefix of a source reference shown beside a row ("MT 23:1")
CT_REF_LABEL = {"heb": "MT", "grc": "Gk", "lat": "Lat"}
# Added to a book's notes when at least one of its source references differs from the Saints verse
CT_NUMBERING_NOTE = {
    "heb": "Verse numbers are Masoretic (MT), so some verses of this book are numbered differently from the Saints.Bible row.",
    "grc": "Verse numbers are those of the Studio Greek (Swete in the Old Testament), so some verses of this book are numbered differently from the Saints.Bible row.",
    "lat": "Verse numbers are those of the Saints Latin column (Vulgate numbers in places), so some verses of this book are numbered differently from the Saints.Bible row.",
}
CT_NOTES = {
    ("grc", "daniel"): ["Theodotion; the Saints English beside it follows the Old Greek."],
    ("grc", "judges"): ["B text; the site follows the A text."],
    ("grc", "sirach"): ["The translator's Prologue stands before 1:1, without a verse number."],
    ("lat", "sirach"): ["The translator's Prologue stands before 1:1, without a verse number."],
}
CT_CREDITS = {
    "heb": ["Miqra according to the Masorah (MAM, Aleppo Codex tradition): spelling and pointing",
            "Westminster Leningrad Codex (WLC): verse numbering"],
    "grc": ["Old Testament: Swete's Septuagint (Amicarelli transcription) and the First1KGreek Septuagint",
            "New Testament: SBLGNT, Statistical Restoration GNT (SRGNT), Bunning Heuristic Prototype (BHP), "
            "Textus Receptus (CNTR KJTR collation), Codex Sinaiticus (01) and Vaticanus (03) transcriptions "
            "(CNTR), Nestle 1904, Robinson-Pierpont 2018"],
    "lat": ["Clementine Vulgate (1598)", "the Saints.Bible Latin column",
            "Codex Amiatinus (Digital Latin Library transcription; Genesis)"],
}
_BRACKETS = ["⟦ ⟧", "probably not original: bracketed by the weightier witnesses, printed for reference"]
_PARENS = ["( )", "ordinary punctuation: the words inside belong to the text"]
CT_LEGEND = {
    "heb": [["(…)", "written form (ketiv), followed by the read form (qere)"],
            ["_", "joins the words of one written form (ketiv)"],
            ["[…]", "read form (qere) with no written form (ketiv)"],
            _BRACKETS],
    "grc": [_BRACKETS, _PARENS],
    "lat": [_PARENS],
}
CT_ABOUT = ("Eclectic editions made with the Saints Critical Text Studio from openly licensed witnesses: "
            "each verse is weighed across the witnesses listed in the credits. The verse references beside "
            "the text are the edition's own numbering; verses the Saints.Bible text has no place for are "
            "listed after the verse they follow.")
CT_LICENCE_NOTE = "The licence of the edition texts has not been set yet."
# Studio Greek & native Vulgate Latin Sir 1:1 = the translator's Prologue followed by 1:1
SIRACH_SPLIT = "Πᾶσα σοφία παρὰ Κυρίου"
SIRACH_SPLIT_LAT = "Omnis sapientia a Domino Deo est"
SIRACH_SPLIT_BY_LANG = {"grc": SIRACH_SPLIT, "lat": SIRACH_SPLIT_LAT}


def split_sirach_prologue(text: str, code: str = "grc") -> Optional[tuple]:
    """(prologue, verse 1:1) of the Studio Greek or native Vulgate Latin Sir 1:1, or None when the
    1:1 opening is not found once after some Prologue text."""
    marker = SIRACH_SPLIT_BY_LANG.get(code, SIRACH_SPLIT)
    i = text.find(marker)
    if i <= 0 or text.find(marker, i + 1) != -1:
        return None
    prologue, rest = text[:i].strip(), text[i:].strip()
    return (prologue, rest) if prologue and rest else None


def _ct_text(texts: Sequence[str]) -> Any:
    return texts[0] if len(texts) == 1 else list(texts)


def ct_join(text: Any) -> str:
    """The word-layer verse text a critical-text entry stands for (what the decoder rebuilds)."""
    return " ".join(text) if isinstance(text, list) else str(text)


def critical_text_rows(code: str, slug: str, verses: Sequence[Any], unplaced: Sequence[Any]) -> tuple:
    """(rows, unplaced_rows, stats) of one book in Saints verse order: rows = [ch, v, src, text] with
    text a string (one source verse) or one string per source verse; unplaced_rows =
    [afterCh, afterV, src, text, reason] in source order.  The Studio Greek Sirach 1:1 is split into the
    Prologue (unplaced, src "Prologue", reason "prologue") and site verse 1:1."""
    by_key: Dict[tuple, list] = {}
    for sv in verses:
        src = ",".join(f"{c}:{v}" for c, v in sv.src)
        by_key[(sv.chapter, sv.verse)] = [sv.chapter, sv.verse, src, _ct_text(list(sv.texts))]
    un_rows: List[list] = []
    stats = {"prologue": 0}
    for u in unplaced:
        if code in SIRACH_SPLIT_BY_LANG and slug == "sirach" and (u.chapter, u.verse) == (1, 1):
            parts = split_sirach_prologue(u.text, code)
            if parts:
                un_rows.append([0, 0, "Prologue", parts[0], "prologue"])
                stats["prologue"] += 1
                if (1, 1) not in by_key:
                    by_key[(1, 1)] = [1, 1, "1:1", parts[1]]
                continue
        un_rows.append([u.after[0], u.after[1], u.src, u.text, u.reason])
    if code in SIRACH_SPLIT_BY_LANG and slug == "sirach" and not stats["prologue"]:
        # Sir 1:1 placed at site 1:1 (versification changed): keep the Prologue out of the verse anyway
        row = by_key.get((1, 1))
        if row:
            srcs = row[2].split(",")
            segs = row[3] if isinstance(row[3], list) else [row[3]]
            if "1:1" in srcs:
                k = srcs.index("1:1")
                parts = split_sirach_prologue(segs[k], code)
                if parts:
                    segs = list(segs)
                    segs[k] = parts[1]
                    row[3] = _ct_text(segs)
                    un_rows.insert(0, [0, 0, "Prologue", parts[0], "prologue"])
                    stats["prologue"] += 1
    rows = [by_key[k] for k in sorted(by_key)]
    return rows, un_rows, stats


def compact_ct_rows(rows: Sequence[list]) -> Dict[str, Any]:
    """[ch, v, src, text] rows -> {"start", "src", "text"} (see the module docstring)."""
    start: List[list] = []
    src: Dict[str, str] = {}
    text: List[Any] = []
    pc = pv = None
    for i, (ch, v, s, t) in enumerate(rows):
        if not (ch == pc and v == pv + 1):
            start.append([i, ch, v])
        pc, pv = ch, v
        if s != f"{ch}:{v}":
            src[str(i)] = s
        text.append(t)
    return {"start": start, "src": src, "text": text}


def expand_compact_ct(payload: Dict[str, Any]) -> List[list]:
    """The v1 rows of a critical-text payload in either layout (the decoder does the same)."""
    if "verses" in payload:
        return payload["verses"]
    starts = {s[0]: (s[1], s[2]) for s in payload["start"]}
    out: List[list] = []
    ch = v = 0
    for i, t in enumerate(payload["text"]):
        if i in starts:
            ch, v = starts[i]
        else:
            v += 1
        out.append([ch, v, payload["src"].get(str(i), f"{ch}:{v}"), t])
    return out


def critical_text_payload(code: str, slug: str, order: int, verses: Sequence[Any], unplaced: Sequence[Any],
                          layout: str = CT_LAYOUT) -> tuple:
    """(payload, rows, stats) of book/ct-{code}/{NN}-{slug}.json.gz."""
    rows, un_rows, stats = critical_text_rows(code, slug, verses, unplaced)
    notes = list(CT_NOTES.get((code, slug), []))
    if any(r[2] != f"{r[0]}:{r[1]}" for r in rows):
        notes.append(CT_NUMBERING_NOTE[code])
    payload: Dict[str, Any] = {"schema": CT_SCHEMA[layout], "lang": code, "book": slug, "order": order,
                               "edition": CT_EDITION[code], "numbering": CT_NUMBERING[code], "notes": notes}
    if layout == "compact":
        payload.update(compact_ct_rows(rows))
    else:
        payload["verses"] = rows
    payload["unplaced"] = un_rows
    stats.update({"verses": len(rows), "unplaced": len(un_rows),
                  "multi": sum(1 for r in rows if isinstance(r[3], list))})
    return payload, rows, stats


def word_layer_rows(verses: Sequence[Any], ct_rows: Sequence[list]) -> tuple:
    """([ch, v, src, text, nTokens] per Saints verse, kept): text is "" wherever the critical-text row of
    the same verse rebuilds it exactly (``ct_join``), else the full text is kept (``kept`` counts those)."""
    ct_text = {(r[0], r[1]): ct_join(r[3]) for r in ct_rows}
    out, kept = [], 0
    for sv in verses:
        src = ",".join(f"{c}:{v}" for c, v in sv.src)
        text = " ".join(sv.texts)
        if ct_text.get((sv.chapter, sv.verse)) == text:
            text = ""
        else:
            kept += 1
        out.append([sv.chapter, sv.verse, src, text, len(sv.tokens)])
    return out, kept


WL_LAYOUT = "compact"            # or "rows" (v1 word-layer files); see the module docstring
WL_SCHEMA = {"compact": "saints-concordance-book/v2", "rows": "saints-concordance-book/v1"}


def compact_word_layer(payload: Dict[str, Any], layout: Optional[str] = None) -> Dict[str, Any]:
    """The word-layer payload in ``layout`` (default ``WL_LAYOUT``); a new dict, key order kept."""
    layout = layout or WL_LAYOUT
    if layout != "compact":
        return {**payload, "schema": WL_SCHEMA["rows"]}
    rows = payload["verses"]
    c = compact_ct_rows([r[:3] + [None] for r in rows])
    L, F = payload["L"], payload["F"]
    fl: List[int] = [0] * len(payload["lemma"])
    consistent = True
    for lid, f in zip(L, F):
        if not lid:
            consistent = consistent and f == 0
        elif fl[lid - 1] in (0, f) and f:
            fl[lid - 1] = f
        else:
            consistent = False
    out: Dict[str, Any] = {}
    for k, v in payload.items():
        if k == "schema":
            out[k] = WL_SCHEMA["compact"]
        elif k == "verses":
            if any(r[3] for r in rows):     # text kept somewhere: the compact rows cannot carry it
                out[k] = v
            else:
                out["vstart"], out["vsrc"], out["vn"] = c["start"], c["src"], [r[4] for r in rows]
        elif k == "F":
            if consistent:
                out["Fl"] = fl
            else:
                out[k] = v
        else:
            out[k] = v
    return out


def expand_word_layer(payload: Dict[str, Any]) -> Dict[str, Any]:
    """v1 view (``verses`` rows and ``F``) of a word-layer payload in either layout (what the decoder does)."""
    out = dict(payload)
    if "verses" not in out:
        rows = expand_compact_ct({"start": out.pop("vstart"), "src": out.pop("vsrc"), "text": out["vn"]})
        out["verses"] = [[ch, v, s, "", n] for ch, v, s, n in rows]
        out.pop("vn")
    if "F" not in out:
        fl = out.pop("Fl")
        out["F"] = [fl[l - 1] if l else 0 for l in out["L"]]
    return out


def critical_texts_json() -> Dict[str, Any]:
    """data/critical-texts.json (spec 1b)."""
    editions = {c: {"name": CT_EDITION[c], "short": CT_SHORT[c], "numbering": CT_NUMBERING[c],
                    "refLabel": CT_REF_LABEL[c], "credits": CT_CREDITS[c], "legend": CT_LEGEND[c]}
                for c in ("heb", "grc", "lat")}
    return {"schema": "saints-critical-texts/v1", "editions": editions, "about": CT_ABOUT,
            "bookFiles": "book/ct-{lang}/{NN}-{slug}.json.gz", "bookSchema": CT_SCHEMA[CT_LAYOUT],
            "licence": None, "licenceNote": CT_LICENCE_NOTE}


def _gz(path: Path, obj: Any) -> int:
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wb", compresslevel=9) as fh:
        fh.write(raw)
    return path.stat().st_size


# Books whose English follows a different Greek text form than the Studio's Greek: links would point at
# words the English does not translate (independent check 18 Nov: Daniel 4:37-37c 3/30 right).
NO_LINKS = {("grc", "daniel"): "the Saints English follows the Old Greek; the Saints Critical Greek Text is Theodotion"}


def _safe_links(res: Dict[str, Any], code: str, slug: str, stats: Dict[str, Any]) -> List[list]:
    """Exported links minus those an independent check found unreliable: whole books with a text-form
    mismatch, and groups where one Studio verse meets several English units (lettered verses, merged
    verses: 79-88 % right) — only one-unit-to-one-verse pairs keep their links."""
    if (code, slug) in NO_LINKS:
        stats["links_dropped_textform"] = stats.get("links_dropped_textform", 0) + len(res["links"])
        return []
    units_of_verse: Dict[int, set] = {}
    verses_of_unit: Dict[int, set] = {}
    for l in res.get("all_links", res["links"]):
        units_of_verse.setdefault(l[3], set()).add(l[0])
        verses_of_unit.setdefault(l[0], set()).add(l[3])
    keep = []
    for l in res["links"]:
        if len(units_of_verse.get(l[3], ())) > 1 or len(verses_of_unit.get(l[0], ())) > 1:
            stats["links_dropped_groups"] = stats.get("links_dropped_groups", 0) + 1
            continue
        keep.append(l)
    return keep


def compact_links(links: List[list]) -> Dict[str, Any]:
    """[enIdx, a, b, verseIdx, pos, tier] rows -> five delta columns (about a quarter of the gzip size).
    The decoder (expandAc) rebuilds the rows; every exported link is tier A, so the tier is one field."""
    tiers = {l[5] for l in links}
    if len(tiers) > 1:
        raise ValueError(f"compact_links: mixed tiers {sorted(tiers)}")
    cols: List[List[int]] = [[], [], [], [], []]
    pe = pv = 0
    for en, a, b, vi, pos, _tier in links:
        cols[0].append(en - pe); pe = en
        cols[1].append(vi - pv); pv = vi
        cols[2].append(a); cols[3].append(b - a); cols[4].append(pos)
    return {"Ac": cols, "Atier": next(iter(tiers)) if tiers else 1}


def english_units_for_site(units: List[list]) -> List[list]:
    """Drop the per-unit hash (sha1 of the collapsed text, computed by the browser instead)."""
    return [[u[0], u[1]] + list(u[3:]) for u in units]


def books_json(site_books: Path = SITE_BOOKS_JSON) -> Dict[str, Any]:
    site = {b["slug"]: b for b in json.loads(site_books.read_text(encoding="utf-8"))["books"]}
    out = []
    for b in BOOKS:
        s = site.get(b.slug)
        if not s:
            continue
        chapters = {str(c): f"{s['base']}{s.get('chapterPrefix', 'chapter-')}{c}/" for c in s.get("chapters", [])}
        langs = [c for c, has in (("heb", b.has_hebrew), ("grc", b.has_greek), ("lat", b.has_latin)) if has]
        entry = {"order": b.order, "slug": b.slug, "title": b.title, "testament": b.testament,
                 "langs": langs, "chapters": chapters, "parallel": s.get("parallel", "")}
        # The site's own verse-anchor exceptions (verses inside range paragraphs, lettered verses,
        # verses absent from the page = null) and reference aliases ('jn', '1 kgs'), passed on as-is.
        if s.get("exceptions"):
            entry["exceptions"] = s["exceptions"]
        if s.get("aliases"):
            entry["aliases"] = s["aliases"]
        no_links = {c: r for (c, slug), r in NO_LINKS.items() if slug == b.slug}
        if no_links:
            entry["noLinks"] = no_links
        out.append(entry)
    return {"schema": "saints-concordance-books/v1", "books": out}


def export_site_layer(
    conn: sqlite3.Connection,
    out_dir: Path,
    books: Optional[Sequence[str]] = None,
    languages: Sequence[str] = LANGS,
    say=print,
) -> Dict[str, Any]:
    from . import concordance_align as al
    from .concordance_gold import _LexiconWriter, ensure_gold_schema, _modules
    from .concordance_layer import saints_book_layers

    t0 = time.time()
    ensure_gold_schema(conn)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report: Dict[str, Any] = {"files": {}, "sizes": {}, "langs": {}}
    (out_dir / "books.json").write_text(json.dumps(books_json(), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (out_dir / "critical-texts.json").write_text(
        json.dumps(critical_texts_json(), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    mods = _modules()
    lexicons = {n: mods[n].load_lexicon() for n in LANGS}
    writer = _LexiconWriter(conn, lexicons)
    english_cols: Dict[str, Dict[str, List[List[str]]]] = {}   # slug -> column -> units
    extra_stems: set = set()

    for lang in languages:
        code = CODE[lang]
        legend = getattr(mods[lang], "morph_legend", lambda: {})()
        used_codes: set = set()
        stats = {"books": 0, "tokens": 0, "with_morph": 0, "links": 0, "untagged": 0,
                 "ct_verses": 0, "ct_unplaced": 0, "ct_prologue": 0, "ct_multi": 0, "ct_text_kept": 0}
        say(f"{lang}: aligning and exporting")
        aligner = al.Aligner(conn, lang) if hasattr(al, "Aligner") else None
        for layer in saints_book_layers(conn, lang, books=books if books else None):
            slug, verses = layer.book, layer.verses
            book = BOOKS_BY_SLUG[slug]
            # The critical text of the book (every verse with text, placed or not), written in the same
            # pass so its text and the word positions below always come from the same database state.
            ct_payload, ct_rows, ct_stats = critical_text_payload(code, slug, book.order, verses, layer.unplaced)
            report["sizes"][f"ct-{code}/{slug}"] = _gz(
                out_dir / "book" / f"ct-{code}" / f"{book.order:02d}-{slug}.json.gz", ct_payload)
            for k in ("verses", "unplaced", "prologue", "multi"):
                stats[f"ct_{k}"] += ct_stats[k]
            vrows, kept = word_layer_rows(verses, ct_rows)
            stats["ct_text_kept"] += kept
            lemma_ids: List[int] = []
            lemma_pos: Dict[int, int] = {}
            morph_codes: List[str] = []
            morph_pos: Dict[str, int] = {}
            L: List[int] = []
            M: List[int] = []
            F: List[int] = []
            for sv in verses:
                for t in sv.tokens:
                    stats["tokens"] += 1
                    lid = 0
                    if t.lemma_key:
                        hit = writer.stem_for(t.lemma_key, lang)
                        if hit:
                            sid = hit[0]
                            if not t.is_content:
                                extra_stems.add(sid)
                            if sid not in lemma_pos:
                                lemma_ids.append(sid)
                                lemma_pos[sid] = len(lemma_ids)
                            lid = lemma_pos[sid]
                    if not lid:
                        stats["untagged"] += 1
                    mid = 0
                    if t.morph:
                        stats["with_morph"] += 1
                        used_codes.add(t.morph)
                        if t.morph not in morph_pos:
                            morph_codes.append(t.morph)
                            morph_pos[t.morph] = len(morph_codes)
                        mid = morph_pos[t.morph]
                    L.append(lid)
                    M.append(mid)
                    F.append(0 if not lid else (1 if t.is_content else 2))
            res = (aligner.align_book(slug, verses) if aligner else al.align_book(conn, lang, slug))
            english_cols.setdefault(slug, {})[EN_COLUMN[lang]] = res["english"]
            A = _safe_links(res, code, slug, stats)
            stats["links"] += len(A)
            payload = {"schema": "saints-concordance-book/v1", "lang": code, "book": slug, "order": book.order,
                       "licence": LICENCE[code], "morphScheme": MORPH_SCHEME[code], "morph": morph_codes,
                       "lemma": lemma_ids, "verses": vrows, "L": L, "M": M, "F": F, **compact_links(A),
                       "englishColumn": EN_COLUMN[lang]}
            payload = compact_word_layer(payload)
            if "F" in payload:
                stats["wl_F_kept"] = stats.get("wl_F_kept", 0) + 1
            path = out_dir / "book" / code / f"{book.order:02d}-{slug}.json.gz"
            report["sizes"][f"{code}/{slug}"] = _gz(path, payload)
            stats["books"] += 1
        if lang == "greek":
            try:
                from .lexica import glaux
                legend = {**legend, **glaux.morph_legend([c for c in used_codes if c.startswith("A:")])}
            except Exception:  # GLAUx absent: its codes stay undescribed and are counted below
                pass

        def describe(c: str) -> str:
            if legend.get(c):
                return legend[c]
            parts = [p if p.startswith(c[:2]) else c[:2] + p for p in c.split(",")] if "," in c else []
            texts = [legend.get(p, "") for p in parts]
            return " or ".join(t for t in texts if t) if parts and all(texts) else ""

        legend_out = {c: describe(c) for c in sorted(used_codes)}
        (out_dir / f"morph-{code}.json").write_text(
            json.dumps(legend_out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        legend = legend_out
        stats["legend_missing"] = sum(1 for c in used_codes if not legend.get(c))
        report["langs"][code] = stats

    for slug, cols in english_cols.items():
        book = BOOKS_BY_SLUG[slug]
        report["sizes"][f"en/{slug}"] = _gz(out_dir / "book" / "en" / f"{book.order:02d}-{slug}.json.gz",
                                            {"schema": "saints-concordance-english/v1", "book": slug,
                                             "cols": {k: english_units_for_site(v) for k, v in cols.items()}})
    report["extra_stems"] = sorted(extra_stems)
    report["seconds"] = round(time.time() - t0, 1)
    report["total_bytes"] = sum(report["sizes"].values())
    return report
