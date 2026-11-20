"""Corpus word-frequency lexicon built from the admitted witnesses of one language.

Used for two narrow, logged corrections in Greek, where the Old Testament has only two
independent digital witnesses (Swete — from OCR — and Brenton):

* a reading found (almost) nowhere else in the corpus that is one or two letters away from a
  common word is treated as an OCR/transcription slip rather than a textual variant;
* an accent form that occurs (almost) nowhere else (e.g. ``τοὺ`` for ``τοῦ``), or an all-caps
  incipit (``ΛΟΓΟΙ``), is spelled the way the rest of the corpus spells that word.

The lexicon is cached on disk (``lexicon_<language>.json`` in the data folder) and rebuilt
whenever the set of witnesses or their files change.
"""

from __future__ import annotations
import hashlib
import json
import threading
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .catalog import DATA_DIR, EDITION_FAMILIES, get_books_for_language
from .collator import canonical_compare_key, is_letter_numeral, is_nomen_sacrum, strip_punct, tokenize_for_alignment
from .parsers import load_book_from_witness, resolve_corpus_path

LEXICON_FORMAT = 4
_LOCK = threading.Lock()
_MEMORY: Dict[str, "Lexicon"] = {}


@dataclass
class Lexicon:
    language: str
    key_freq: Counter = field(default_factory=Counter)
    form_freq: Counter = field(default_factory=Counter)  # lower-case accented forms
    best_form: Dict[str, str] = field(default_factory=dict)
    # how many independent edition families ever write this word twice in a row (κύριε κύριε)
    repeat_families: Counter = field(default_factory=Counter)

    def key_count(self, key: str) -> int:
        return int(self.key_freq.get(key, 0))

    def form_count(self, form: str) -> int:
        return int(self.form_freq.get(surface_form_key(form), 0))


def surface_form_key(form: str) -> str:
    return unicodedata.normalize("NFC", strip_punct(form).lower()).replace("ς", "σ")


def _has_marks(s: str) -> bool:
    return any(unicodedata.category(c) == "Mn" for c in unicodedata.normalize("NFD", s))


def edit_distance(a: str, b: str, limit: int = 3) -> int:
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        if min(cur) > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def _signature(language: str, witnesses: Iterable[Dict[str, object]]) -> str:
    parts: List[str] = [str(LEXICON_FORMAT), language]
    for w in sorted(witnesses, key=lambda r: str(r["id"])):
        p = resolve_corpus_path(Path(str(w["file_path"])))
        try:
            mtime = p.stat().st_mtime_ns
        except OSError:
            mtime = 0
        parts.append(f"{w['id']}|{p}|{mtime}|{w['parser_kind']}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _build(language: str, witnesses: List[Dict[str, object]]) -> Lexicon:
    lex = Lexicon(language=language)
    books = get_books_for_language(language)
    seen_families = set()
    for w in sorted(witnesses, key=lambda r: -float(r.get("weight", 0) or 0)):
        # Digital copies of one edition share its OCR errors: count each edition once.
        family = EDITION_FAMILIES.get(str(w["id"]), str(w["id"]))
        if family in seen_families:
            continue
        seen_families.add(family)
        scope = str(w["testament_scope"])
        repeated_here = set()
        for book in books:
            if book.testament not in scope.split("/") and scope != "OT/NT":
                continue
            for verses in load_book_from_witness(w, book).values():
                for text in verses.values():
                    prev = ""
                    for tok in tokenize_for_alignment(text, language):
                        if is_nomen_sacrum(tok) or is_letter_numeral(tok):
                            prev = ""
                            continue
                        key = canonical_compare_key(tok, language)
                        if not key:
                            continue
                        lex.key_freq[key] += 1
                        if key == prev and _has_marks(tok):  # manuscripts' own slips don't count
                            repeated_here.add(key)
                        prev = key
                        if _has_marks(tok) and not tok.isupper():
                            lex.form_freq[surface_form_key(tok)] += 1
        for key in repeated_here:
            lex.repeat_families[key] += 1
    best: Dict[str, tuple] = {}
    for form, n in lex.form_freq.items():
        key = canonical_compare_key(form, language)
        if key and (key not in best or n > best[key][1]):
            best[key] = (form, n)
    lex.best_form = {k: v[0] for k, v in best.items()}
    return lex


def get_lexicon(language: str, witnesses: List[Dict[str, object]]) -> Optional[Lexicon]:
    """Return the cached lexicon for the admitted witnesses of ``language`` (Greek only for now)."""
    if language != "greek" or not witnesses:
        return None
    sig = _signature(language, witnesses)
    with _LOCK:
        cached = _MEMORY.get(sig)
        if cached:
            return cached
        path = DATA_DIR / f"lexicon_{language}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("signature") == sig:
                    lex = Lexicon(language, Counter(data["key_freq"]), Counter(data["form_freq"]), dict(data["best_form"]), Counter(data.get("repeat_families", {})))
                    _MEMORY[sig] = lex
                    return lex
            except (OSError, ValueError, KeyError):
                pass
        lex = _build(language, witnesses)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "signature": sig,
                "key_freq": lex.key_freq,
                "form_freq": lex.form_freq,
                "best_form": lex.best_form,
                "repeat_families": lex.repeat_families,
            }, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        _MEMORY[sig] = lex
        return lex
