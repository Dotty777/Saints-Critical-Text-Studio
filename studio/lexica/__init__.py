"""Gold-data lemma and root taggers for The Saints Concordance (Hebrew, Greek, Latin).

Added 18 Nov 2026 to replace the surface-form guessing in ``studio/concordance.py``
(suffix stripping, first-match lookups) with lemma tags taken from openly licensed,
word-by-word tagged editions and scholarly root data.

Contract shared by ``hebrew.py``, ``greek.py`` and ``latin.py``:

* ``load_lexicon() -> Dict[str, LemmaEntry]``  every lemma the tagger can emit, keyed by
  ``LemmaEntry.lemma_key``, with its root family.
* ``tag_chapter(book_slug, chapter, verses) -> Dict[int, List[TokenTag]]``  ``verses`` maps the
  verse numbers *as stored in the Studio for that language* to the verse's critical text; the
  result gives, per verse, one ``TokenTag`` per token of ``tokenize_verse(text, lang)``.
* A token the tagger cannot resolve with confidence gets ``lemma_key=None``: never guess.
* Only openly licensed sources may be read here.  Non-commercial / quarantined data
  (PROIEL, Rahlfs/CCAT, ETCBC BHSA, anything in ``05_Tier5_Quarantined_Study_Only`` or
  ``witness-cache/.local-nc-only``) may be used by evaluation scripts outside ``studio/`` only.

``versification.py`` maps a verse in a language's own numbering to the live Saints.Bible
numbering (Septuagint order, Rahlfs-style).  The Studio's Greek stream (Swete) mostly shares it but not
everywhere (Deut 29, Gen 31-32, Lev 8, Num 21/27, Ps 12, Sirach 30-36, site-only verses), so even
``to_saints('greek', ...)`` is not simply the identity.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

LANGS = ("heb", "arc", "grc", "lat")

# Part-of-speech tags used in LemmaEntry.pos
POS_TAGS = ("N", "V", "ADJ", "ADV", "PREP", "CONJ", "PRON", "ART", "PART", "NUM", "INTERJ", "PROPN")


@dataclass(frozen=True)
class LemmaEntry:
    lang: str                 # 'heb' | 'arc' | 'grc' | 'lat'
    lemma_key: str            # stable unique key: 'H7225' (OSHB/Strong), 'G0746', 'lat:principium'
    lemma: str                # dictionary headword with its diacritics: רֵאשִׁית, ἀρχή, principium
    gloss: str                # short English gloss from an openly licensed source
    pos: str                  # one of POS_TAGS
    strongs: Optional[str]    # 'H7225' / 'G0746' or None
    root_key: str             # family key: 'heb:ראש' (BDB root), 'grc:G0757' (ultimate base lemma), 'lat:capio'
    root_label: str           # display form: 'ר-א-ש', 'ἄρχω', 'capio'
    root_gloss: str           # short meaning of the root/family head
    root_source: str          # 'OSHB-BDB' | 'Strongs-CC0' | 'MorphGNT-derivation' | 'LewisShort-etym' | 'self'
    formula: str              # readable decomposition, e.g. 'ר-א-ש + -ִית', 'ἀπό + ἄρχω', 'in + eo'
    source: str               # where the lemma came from, with licence, e.g. 'OSHB MorphHB (CC BY 4.0)'


@dataclass
class TokenTag:
    index: int                          # 1-based position in tokenize_verse(text, lang)
    surface: str                        # the token as printed in the critical text
    lemma_key: Optional[str]            # None = not resolved (never a guess)
    method: str                         # 'gold-aligned' | 'gold-form' | 'paradigm' | 'untagged'
    confidence: float                   # 0..1
    prefixes: Tuple[str, ...] = ()      # morpheme codes of proclitics/enclitics: ('P:w', 'P:b'), ('E:que',)
    is_content: bool = True             # False for article / conjunction / particle / bare-pronoun tokens
    notes: List[str] = field(default_factory=list)
    # Parsing of this token, prefixed with its scheme (added 18 Nov 2026 for the per-book word layer):
    # 'O:HR/Ncfsa' (OSHB), 'R:N-DSF' (STEPBible TAGNT / Robinson), 'L:V3|unt' (Latin paradigm class|ending,
    # a class and ending, not one cell).  None when no open source gives one (e.g. the Septuagint).
    morph: Optional[str] = None
    # Id of the gold word the tag came from ('oshb:01xeN', 'tagnt:Mat.1.1#01'), for traceability.
    src: Optional[str] = None


# ---------------------------------------------------------------------------
# One tokenizer for every module and for the indexer, so token indexes agree.
# ---------------------------------------------------------------------------

_HEB_LETTER = re.compile(r"[א-ת]")
_GRC_LETTER = re.compile(r"[Ͱ-Ͽἀ-῿]")
_LAT_LETTER = re.compile(r"[A-Za-zÀ-ÿĀ-žæœÆŒ]")
_KETIV = re.compile(r"\([^()]*\)")          # Hebrew only: the Studio prints the ketiv in parentheses after the qere
_EDGE_PUNCT = ".,;·:!?;׃׀«»\"'“”‘’()[]{}⟦⟧—–-_‍‌"


def tokenize_verse(text: str, lang: str) -> List[str]:
    """Split a Studio critical-text verse into word tokens.

    Hebrew: the parenthesised ketiv is dropped (the pointed qere before it is kept), words are split
    at spaces and maqqef.  Greek/Latin: parentheses are ordinary punctuation (they enclose real text),
    so nothing inside them is dropped; the Greek elision mark (᾽ ’ ') stays on its word.
    """
    if not text:
        return []
    lang = lang.lower()
    if lang in ("heb", "arc", "hebrew"):
        cleaned = _KETIV.sub(" ", text)
        raw = re.split(r"[\s־/]+", cleaned)
        letter = _HEB_LETTER
        edge = _EDGE_PUNCT
    elif lang in ("grc", "greek"):
        raw = re.split(r"\s+", text)
        letter = _GRC_LETTER
        edge = _EDGE_PUNCT.replace("'", "").replace("’", "")
    else:
        raw = re.split(r"[\s\-–—]+", text)
        letter = _LAT_LETTER
        edge = _EDGE_PUNCT
    out: List[str] = []
    for tok in raw:
        t = tok.strip(edge)
        if t and letter.search(t):
            out.append(t)
    return out


def hebrew_consonants(text: str, normalize_finals: bool = True) -> str:
    """Consonants only (א-ת); final forms folded to medial forms when ``normalize_finals``."""
    cons = "".join(ch for ch in text if "א" <= ch <= "ת")
    if normalize_finals:
        cons = cons.translate(str.maketrans({"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"}))
    return cons


def greek_bare(text: str) -> str:
    """Lower-case Greek without accents/breathings/iota subscripts; final sigma folded to σ."""
    nfd = unicodedata.normalize("NFD", text)
    bare = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    bare = unicodedata.normalize("NFC", bare).lower().replace("ς", "σ")
    return re.sub(r"[^α-ω]", "", bare)


def latin_bare(text: str) -> str:
    """Lower-case ASCII Latin key: æ→ae, œ→oe, j→i, v→u, diacritics (ë, á) removed."""
    t = text.lower().replace("æ", "ae").replace("œ", "oe")
    nfd = unicodedata.normalize("NFD", t)
    t = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    t = t.replace("j", "i").replace("v", "u")
    return re.sub(r"[^a-z]", "", t)
