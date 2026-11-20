"""Every word of the critical texts in Saints.Bible verse order (18 Nov 2026).

``saints_verses(conn, lang, book_slug=None)`` is the one place that decides which source words make up
a Saints.Bible verse and in which order, so the per-book word layer (positions + parsing), the English
alignment and the concordance build all count word positions the same way:

* source verses are tagged with ``studio.lexica.<lang>.tag_chapter`` (every token, function words and
  untagged words included, in ``tokenize_verse`` order); Greek Old Testament tokens without a parse
  then get the GLAUx machine parse (``studio.lexica.glaux.fill_chapter``, 'A:' codes, CC BY-SA);
* each source verse goes to the FIRST Saints verse ``versification.to_saints`` gives (the same rule as
  ``concordance_gold.build_gold_concordance``); verses without a Saints counterpart are dropped;
* when several source verses go to one Saints verse, they are concatenated in source order
  (chapter, verse) and the words are numbered 1..n across them.

Lettered site verses (35:22a, 1 Kgs 12:24a-z ...) have no anchors in the Studio: their words are part of
the base verse here.  Consumers that need the site's units split them with the English alignment.

``saints_book_layers(conn, lang, ...)`` (19 Nov 2026) is the same pass returning, per book, the placed
verses AND the source verses with text that map to no Saints verse (``UnplacedVerse``), in source order,
each attached after the Saints verse of the preceding placed source verse (``(0, 0)`` = before the first
verse of the book).  The website's critical-text files carry those so a reader sees every verse of the
edition; the word layer and the concordance still index placed verses only.  ``tag=False`` skips the
taggers (text-only pass: ``tokens`` stay empty).  ``saints_verses`` keeps its old signature and output.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

from .catalog import BOOKS, BOOKS_BY_SLUG

LANG_CODE = {"hebrew": "heb", "greek": "grc", "latin": "lat"}


@dataclass
class SaintsVerse:
    book: str                       # book slug
    chapter: int                    # Saints.Bible numbering
    verse: int
    src: List[Tuple[int, int]]      # source (chapter, verse) in the language's own Studio numbering, in order
    texts: List[str]                # the critical text of each source verse, same order
    tokens: List[object] = field(default_factory=list)   # TokenTag, .index renumbered 1..n across src

    @property
    def label(self) -> str:
        return f"{self.chapter}:{self.verse}"


@dataclass
class UnplacedVerse:
    """A source verse with text that ``versification.to_saints`` maps to no Saints verse."""
    book: str
    chapter: int                    # source numbering
    verse: int
    text: str
    after: Tuple[int, int]          # Saints verse it follows ((0, 0) = before the first verse of the book)
    reason: str = "no-site-verse"

    @property
    def src(self) -> str:
        return f"{self.chapter}:{self.verse}"


@dataclass
class BookLayer:
    book: str
    verses: List[SaintsVerse]       # sorted by Saints (chapter, verse)
    unplaced: List[UnplacedVerse]   # source order


def _module(lang: str):
    from .lexica import greek, hebrew, latin
    return {"hebrew": hebrew, "greek": greek, "latin": latin}[lang]


def saints_verses(conn: sqlite3.Connection, lang: str, book_slug: Optional[str] = None) -> Iterator[Tuple[str, List[SaintsVerse]]]:
    """Yield (book_slug, [SaintsVerse sorted by chapter, verse]) for every book of ``lang``."""
    for layer in saints_book_layers(conn, lang, book_slug):
        yield layer.book, layer.verses


def saints_book_layers(conn: sqlite3.Connection, lang: str, book_slug: Optional[str] = None,
                       books: Optional[Sequence[str]] = None, tag: bool = True) -> Iterator[BookLayer]:
    """Yield a ``BookLayer`` per book of ``lang`` (catalogue order).  ``book_slug`` or ``books`` limit the
    books; ``tag=False`` gives the texts without tagging (tokens empty)."""
    from .lexica import versification as vs

    mod = _module(lang) if tag else None
    if book_slug:
        books_list = [BOOKS_BY_SLUG[book_slug]]
    elif books is not None:
        wanted = set(books)
        books_list = [b for b in BOOKS if b.slug in wanted]
    else:
        books_list = list(BOOKS)
    for book in books_list:
        chapters = conn.execute(
            "SELECT id, chapter FROM chapters WHERE language = ? AND book_slug = ? ORDER BY chapter",
            (lang, book.slug)).fetchall()
        if not chapters:
            continue
        by_target: Dict[Tuple[int, int], SaintsVerse] = {}
        book_texts: Dict[int, Dict[int, str]] = {}
        for ch_id, ch in chapters:
            verses = {int(v): str(t or "") for v, t in conn.execute(
                "SELECT verse, critical_text FROM verses WHERE chapter_id = ? ORDER BY verse", (int(ch_id),))}
            verses = {v: t for v, t in verses.items() if t.strip()}
            if verses:
                book_texts[int(ch)] = verses
        # Greek OT: GLAUx parses (machine, CC BY-SA) for tokens without one, aligned per book
        glaux = None
        if tag and lang == "greek" and book.testament != "NT" and book_texts:
            from .lexica import glaux as _glaux
            if _glaux.corpus_available() and book.slug in _glaux.BOOK_FILES:
                glaux = _glaux
        unplaced: List[UnplacedVerse] = []
        last: Tuple[int, int] = (0, 0)      # Saints verse of the preceding placed source verse
        for ch in sorted(book_texts):
            verses = book_texts[ch]
            if tag:
                tagged = mod.tag_chapter(book.slug, int(ch), verses)
                if glaux is not None:
                    glaux.fill_untagged_lemmas(book.slug, int(ch), tagged, book_texts)
                    glaux.fill_chapter(book.slug, int(ch), tagged, book_texts)
            else:
                tagged = {v: [] for v in verses}
            for v in sorted(tagged):
                targets = vs.to_saints(lang, book.slug, int(ch), v) or []
                if not targets:
                    unplaced.append(UnplacedVerse(book.slug, int(ch), int(v), verses[v], last))
                    continue
                key = (int(targets[0][0]), int(targets[0][1]))
                last = key
                sv = by_target.get(key)
                if sv is None:
                    sv = by_target[key] = SaintsVerse(book.slug, key[0], key[1], [], [])
                sv.src.append((int(ch), v))
                sv.texts.append(verses[v])
                sv.tokens.extend(tagged[v])
        out = []
        for key in sorted(by_target):
            sv = by_target[key]
            for i, t in enumerate(sv.tokens, start=1):
                t.index = i
            out.append(sv)
        yield BookLayer(book.slug, out, unplaced)
