"""English-to-original word alignment for the Saints Concordance (18 Nov 2026; spec docs/CONCORDANCE-SITE-SPEC.md).

Three streams, each an English column of the site aligned to the Studio words behind it:

* ``grc``  Bespoke Saints English (reading pages + Parallel ``saints`` column), Greek-Translation
  ``origin/main`` read with ``git show`` (the working tree of the local clone is stale), aligned to the
  Studio Greek (Septuagint + NT);
* ``heb``  the Parallel ``hebrew`` column (Hebrew-Translation repo, ``HEAD``), aligned to the Studio Hebrew;
* ``lat``  the Parallel ``latin`` column (Latin-Translation repo, ``origin/main``), aligned to the Studio Latin.

Original-language word positions come only from ``concordance_layer.saints_verses`` (every token, function
words included, numbered 1..n per Saints verse).  English word positions follow Word Notes exactly:
``WORD_RE`` over the unit text, 0-based word indexes, half-open ranges ``a..b``.

Method (a measured prototype of 18 Nov 2026, made production code):

1. English lemmatiser (suffix rules + irregular verbs/plurals) and a stop-list of English function words;
   stop words, words in square brackets (supplied English) and editorial prefixes are never linked.
2. Dictionaries, open data only: the Studio lemma glosses (``studio.lexica.*.load_lexicon``); for Greek
   STEPBible TAGNT per-word English (CC BY 4.0; also per NT token through ``TokenTag.src``), MACULA Greek
   ``english`` + ``gloss`` (CC BY 4.0 / Berean PD) and MACULA Hebrew ``english`` bridged to the Septuagint
   through its ``greekstrong`` column; for Hebrew STEPBible TAHOT per-morpheme English and MACULA Hebrew
   ``english`` + ``gloss``.  The MACULA ``domain``/``ln`` (MARBLE) fields are never read.  Latin uses the
   Lewis & Short glosses only.  Proper names without an English gloss are matched by transliteration.
3. IBM Model 1 in both directions over the whole stream (trained once per stream), a position prior, greedy
   one-to-one linking; light verbs (make, do, give, take, have, become) and English prepositions are held back
   and linked only on strong evidence (dictionary match and IBM >= 0.3 both ways); auxiliary 'have'/'do'
   ('have given', 'Do you not know') is never linked on its own; one source word extends over adjacent English
   words of its own dictionary phrase ('burnt offering', 'made holy', 'take heart') but never over a repeated
   word ('fear, fear') or a preposition; same-lemma links are re-paired monotonically (reading order, nearest
   occurrences to the diagonal); one hyphenated English word may take two neighbouring source words
   ('Beth-anoth', 'twenty-four').
4. Tiers: 1 = A (dictionary match and IBM posterior >= 0.3 in either direction), 2 = B (dictionary only),
   3 = C (IBM >= 0.5 both ways, no dictionary); B and C only when the relative positions differ by less than
   ``MAX_DISTANCE``; 4 = D (the rest).  ``EXPORT_TIERS`` holds the tiers whose cumulative precision on the
   hand-judged gold set of 18 Nov 2026 has a Wilson 95% lower bound >= 95%; ``links`` carries only those,
   ``all_links`` every tier.  Measured (links judged by hand, 300+ stratified verses per stream):

   ====  =====================  ====================  =====================  =================
   lang  A                      B                     C                      A+B+C (W95 low)
   ====  =====================  ====================  =====================  =================
   grc   2320/2344 = 98.98%     51/52 = 98.1%         152/165 = 92.1%        2523/2561 (97.97%)
   heb   2544/2563 = 99.26%     58/60 = 96.7%         73/81 = 90.1%          2675/2704 (98.46%)
   lat   2259/2280 = 99.08%     24/32 = 75.0%         250/266 = 94.0%        2533/2578 (97.67%)
   ====  =====================  ====================  =====================  =================

English units: lettered (``12:24a``) and range (``11:5–8``) units have no Studio verse of their own.  Units
and Studio verses are joined into groups (a unit belongs to every Studio verse its label names; a lettered
unit to its base verse), each group is aligned as one concatenation, and every link is recorded against its
own unit and its own Studio verse.  Placeholder cells ('No MT counterpart [...]', 'Earlier label ...',
'Corresponding Latin text: ...', empty, or only an editorial note in brackets) are left out of the unit list.
Units with no Studio verse keep no links; a unit repeating an earlier unit of its group verbatim (the Latin
column repeats Esther 10:3a in 10:3b-k) is aligned once, the copies keep no links.

Result of ``Aligner.align_book`` / ``align_book``::

    {"book": slug, "lang": "grc", "column": "saints",
     "english": [[label, text, sha1(text)[:10]], ...],
     "links":     [[enIdx, a, b, verseIdx, pos, tier], ...],   # tiers in EXPORT_TIERS[lang]
     "all_links": [[enIdx, a, b, verseIdx, pos, tier], ...],   # every tier, D included
     "stats": {...}}

``verseIdx`` is 0-based into the book's ``saints_verses`` list, ``pos`` the 1-based token position.
The unit text is the source text with whitespace runs collapsed to one space (Psalms keep line breaks in
the source; the page renders them as ``<br>``, which Word Notes reads as a space).

Licences: TAGNT/TAHOT CC BY 4.0 (STEPBible.org, Tyndale House Cambridge); MACULA Greek/Hebrew CC BY 4.0
(Biblica; English by Cherith, CC BY 4.0; Berean gloss PD).  ``SOURCES`` carries the attribution.
"""

from __future__ import annotations

import collections
import csv
import difflib
import glob
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .catalog import BOOKS, BOOKS_BY_SLUG

# ---------------------------------------------------------------------------
# Streams and sources
# ---------------------------------------------------------------------------

LANG_OF = {"grc": "greek", "heb": "hebrew", "lat": "latin", "greek": "greek", "hebrew": "hebrew", "latin": "latin"}
CODE_OF = {"greek": "grc", "hebrew": "heb", "latin": "lat"}
COLUMN_OF = {"grc": "saints", "heb": "hebrew", "lat": "latin"}

_HOME = Path(os.path.expanduser("~"))
DEFAULT_REPOS = {
    "grc": Path(os.environ.get("CTS_EN_GREEK_REPO", str(_HOME / "Documents" / "ChatGPT" / "Holy Bible Translation" / "Greek-Translation"))),
    "heb": Path(os.environ.get("CTS_EN_HEBREW_REPO", str(_HOME / "Website" / "translations" / "hebrew"))),
    "lat": Path(os.environ.get("CTS_EN_LATIN_REPO", str(_HOME / "Website" / "translations" / "latin"))),
}
DEFAULT_REFS = {"grc": "origin/main", "heb": "HEAD", "lat": "origin/main"}
TEXT_FIELD = {"grc": "text", "heb": "english", "lat": "english"}
# Commits the spec pins (18 Nov 2026); a different resolved commit is reported in stats['source'].
PINNED = {"grc": "08b48d75a4f917b4c6dd26d59c388e2352c9a23d", "heb": "97f3c85", "lat": "42587be"}

TIER_NAMES = {1: "A", 2: "B", 3: "C", 4: "D"}
MAX_DISTANCE = 0.3           # tiers B, C: |relative English position - relative source position| below this
# Tiers exported per stream: cumulative Wilson 95% lower bound >= 95% on the hand-judged gold set of
# 18 Nov 2026 (see tests/test_concordance_align.py and the build report).
# 18 Nov 2026 (integrator): per-tier reading of the spec after the independent check — only tier A clears
# a 95% Wilson lower bound on its own (grc 97.8% [96.9, 98.5], heb 99.4% [98.8, 99.7], lat 98.4% [97.5, 99.0]);
# tiers B and C measured 86-97% with lower bounds 65-92%.
EXPORT_TIERS: Dict[str, Tuple[int, ...]] = {"grc": (1,), "heb": (1,), "lat": (1,)}

SOURCES = {
    "TAGNT": "STEPBible TAGNT, Translators Amalgamated Greek NT (STEPBible.org / Tyndale House Cambridge, CC BY 4.0): "
             "per-word English used as alignment dictionary",
    "TAHOT": "STEPBible TAHOT, Translators Amalgamated Hebrew OT (STEPBible.org / Tyndale House Cambridge, CC BY 4.0): "
             "per-morpheme English used as alignment dictionary",
    "MACULA-G": "MACULA Greek SBLGNT (Biblica, CC BY 4.0; english by Cherith CC BY 4.0, gloss Berean PD): english/gloss columns",
    "MACULA-H": "MACULA Hebrew WLC (Biblica, CC BY 4.0; english by Cherith CC BY 4.0): english/gloss and greekstrong columns",
    "Studio": "Studio lemma glosses (OSHB/BDB, STEPBible TBESG/TBESH, Lewis & Short; see the taggers' sources)",
}

WORD_RE = re.compile(r"[^\W_]+(?:[’'-][^\W_]+)*")
_GLOSS_WORD = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")

# ---------------------------------------------------------------------------
# English lemmatiser
# ---------------------------------------------------------------------------

_VES = {"wolves": "wolf", "leaves": "leaf", "loaves": "loaf", "calves": "calf", "halves": "half",
        "sheaves": "sheaf", "thieves": "thief", "wives": "wife", "knives": "knife", "selves": "self",
        "shelves": "shelf", "lives": "life", "elves": "elf"}

_IRREGULAR = (
    "say said|speak spoke spoken spake|go went gone goes|come came comes|see saw seen|give gave given|take took taken|"
    "make made|know knew known|eat ate eaten|drink drank drunk|write wrote written|bring brought|buy bought|"
    "think thought|seek sought|teach taught|fight fought|catch caught|tell told|sell sold|find found|stand stood|"
    "understand understood|hear heard|keep kept|sleep slept|weep wept|leave left|feel felt|meet met|send sent|"
    "spend spent|build built|lose lost|hold held|sit sat|rise rose risen arose arisen|fall fell fallen|"
    "bear bore born borne|tear tore torn|wear wore worn|swear swore sworn|break broke broken|choose chose chosen|"
    "forget forgot forgotten|forgive forgave forgiven|get got gotten|begin began begun|run ran|sing sang sung|"
    "drive drove driven|ride rode ridden|strike struck stricken|hide hid hidden|bite bit bitten|shine shone|lead led|"
    "feed fed|flee fled|bleed bled|lay laid|pay paid|slay slew slain|draw drew drawn|grow grew grown|throw threw thrown|"
    "fly flew flown|blow blew blown|show showed shown|do did done does doth didst|have has had hath hast having|"
    "be is am are was were been being art|shake shook shaken|wake woke awoke awaken|become became|overcome overcame|"
    "smite smote smitten|abide abode|beget begot begotten begat|forsake forsook forsaken|tread trod trodden|bind bound|"
    "grind ground|dwell dwelt|burn burnt|learn learnt|man men|woman women|child children|brother brethren brothers|"
    "foot feet|tooth teeth|ox oxen|sheep|people|die dying died|lie lying|tie tying|stricken|lend lent|bend bent|"
    "shoot shot|win won|wring wrung|swim swam swum|cling clung|fling flung|sting stung|spring sprang sprung|"
    "steal stole stolen|freeze froze frozen|weave wove woven|light lit|kneel knelt|mean meant|deal dealt|dream dreamt|"
    "lead led|speed sped|quit|hit|cost|burst|thrust|shed|rid|split"
)
IRR: Dict[str, str] = {}
for _line in _IRREGULAR.split("|"):
    _w = _line.split()
    for _x in _w:
        IRR.setdefault(_x, _w[0])

STOP: Set[str] = set(
    "the a an and or but nor of to for from by with at as into unto upon on in out up down off over under about than "
    "then that this these those which who whom whose what when where while there here so not no be is am are was were "
    "been being will shall would should may might can could must let i me my mine you your yours thou thee thy thine "
    "ye he him his she her hers it its we us our ours they them their theirs himself herself itself themselves myself "
    "yourself yourselves ourselves o oh also even if because own s neither either whether some any".split())

# English key synonyms (applied to keys): the divine name and its renderings meet at 'lord'.
SYNONYMS = {"yhwh": "lord", "yahweh": "lord", "jehovah": "lord", "yah": "lord"}

LIGHT_VERBS = {"make", "do", "give", "take", "have", "becom"}
# English prepositions and connective adverbs: their sense depends on the construction, so like the light
# verbs they are linked only on strong evidence (dictionary match and IBM >= 0.3 both ways).
_WEAK = ("toward towards among amongst before after through throughout against within without beside besides between "
         "around round across beyond behind below above beneath underneath except unless until till near along amid "
         "amidst concerning according regarding instead therefore thus whenever wherever however one")

# gloss words that only describe grammar (ignored in the glosses of function-word tokens)
_GRAMMAR_GLOSS = set(
    "mark marker accusative nominative genitive dative article particle conjunction preposition pronoun "
    "relative interrogative definite object sign untranslatable untranslated emphatic demonstrative "
    "negative enclitic introduce introducing direct indirect clause sentence word etc i.e e.g self".split())


def lem(word: str) -> str:
    """Rough English lemma: irregular table, then suffix rules (prototype rules of 18 Nov 2026)."""
    w = word.lower().replace("’", "'")
    if w.endswith("'s"):
        w = w[:-2]
    w = w.rstrip("'")
    if w in IRR:
        return IRR[w]
    if len(w) <= 3:
        return w
    if w in _VES:
        return _VES[w]
    for suf, rep in (("ies", "y"), ("ied", "y"), ("sses", "ss"), ("ches", "ch"), ("shes", "sh"),
                     ("xes", "x")):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            return w[:-len(suf)] + rep
    if w.endswith("ing") and len(w) > 5:
        b = w[:-3]
        if len(b) > 2 and b[-1] == b[-2] and b[-1] not in "lsz":
            b = b[:-1]
        return b
    if w.endswith("eth") and len(w) > 5:
        return w[:-3]
    if w.endswith("est") and len(w) > 6:
        return w[:-3]
    if w.endswith("ed") and len(w) > 4:
        b = w[:-2]
        if len(b) > 2 and b[-1] == b[-2] and b[-1] not in "lsz":
            b = b[:-1]
        return b
    if w.endswith("es") and len(w) > 4 and w[-3] in "sxz":
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and not w.endswith("us") and len(w) > 3:
        b = w[:-1]
        return lem(b) if b.endswith("ing") else b      # offerings -> offering -> offer
    return w


def key(word: str) -> str:
    """Matching key: lemma with a final -e dropped (create/created/creating meet), synonyms folded."""
    k = lem(word)
    if len(k) > 4 and k.endswith("e"):
        k = k[:-1]
    return SYNONYMS.get(k, k)


WEAK_WORDS = {key(w) for w in _WEAK.split()} | LIGHT_VERBS


def is_participle(word: str) -> bool:
    """Past participle (or irregular past form): 'finished', 'given', 'been', 'made'."""
    w = word.lower().replace("’", "'")
    if w in IRR and IRR[w] != w:
        return True
    return len(w) > 3 and w.endswith("ed")


_AUX_SKIP = {"not", "never", "already", "also", "all", "just", "now", "ever", "both", "indeed", "truly"}


_DO_AUX_NEXT = {"not", "never", "you", "i", "we", "they", "he", "she", "ye", "thou", "it"}


def auxiliary_have(words: Sequence[str], wi: int) -> bool:
    """'have/has/had/having' followed by a past participle (adverbs and 'not' skipped) is an auxiliary, and so is
    'do/does/did' followed by 'not' or a subject pronoun ('Do you not know', 'did not die')."""
    k = key(words[wi])
    if k == "do":
        return wi + 1 < len(words) and words[wi + 1].lower() in _DO_AUX_NEXT
    if k != "have":
        return False
    for w in words[wi + 1:wi + 4]:
        lw = w.lower()
        if lw in _AUX_SKIP or lw.endswith("ly"):
            continue
        return is_participle(w)
    return False


def is_stop(word: str) -> bool:
    w = word.lower().replace("’", "'")
    if w.endswith("'s"):
        w = w[:-2]
    return w in STOP or w.isdigit()


def word_keys(word: str) -> Tuple[str, ...]:
    """The key of a word plus the keys of its hyphen parts ('burnt-offering' -> burnt-offer, burn, offer)."""
    out = [key(word)]
    if "-" in word:
        for p in word.split("-"):
            if p and not is_stop(p):
                k = key(p)
                if k not in out:
                    out.append(k)
    return tuple(out)


def text_keys(text: str) -> List[str]:
    """Content-word keys of a short English text (glosses, TAGNT/TAHOT renderings)."""
    text = re.sub(r"\([^)]*\)|\[[^\]]*\]|<[^>]*>|\{[^}]*\}", " ", text or "")
    return [key(t) for t in _GLOSS_WORD.findall(text) if not is_stop(t) and t.lower() != "to"]


def gloss_keys(gloss: str, grammar_filter: bool = False) -> Set[str]:
    out: Set[str] = set()
    g = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", gloss or "")
    for part in re.split(r"[;/,]| or ", g):
        for t in _GLOSS_WORD.findall(part):
            if is_stop(t) or t.lower() == "to" or len(t) < 2:
                continue
            if grammar_filter and t.lower() in _GRAMMAR_GLOSS:
                continue
            out.add(key(t))
    return out


# ---------------------------------------------------------------------------
# English units
# ---------------------------------------------------------------------------

_PLACEHOLDER = re.compile(r"^\s*(?:No MT counterpart\b|Earlier label\b|Corresponding Latin text\b)", re.I)
_EDITORIAL_NOTE = re.compile(r"\[(?:No |Related |Aramaic\]|aligned with |BHS )|no corresponding|counterpart", re.I)
_EDITORIAL_PREFIX = re.compile(r"^\s*\|\s*conventional\s+\d+:\d+\s*", re.I)
_REF = re.compile(r"^(?:(.*?)\s)?(\d+):(.+)$")
_PART = re.compile(r"^(?:(\d+):)?(\d+)([a-z]*)(?:\s*[–-]\s*(?:(\d+):)?(\d+)([a-z]*))?$")


@dataclass
class EnglishUnit:
    label: str
    text: str
    chapter: Optional[int]
    targets: List[Tuple[int, int]]          # Saints (chapter, verse) keys the unit belongs to
    lettered: bool = False
    placeholder: bool = False

    @property
    def sha(self) -> str:
        return text_hash(self.text)


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def normalise_text(text: str) -> str:
    return " ".join((text or "").split())


def is_placeholder(text: str) -> bool:
    t = (text or "").strip()
    if not t or _PLACEHOLDER.match(t):
        return True
    if not _EDITORIAL_NOTE.search(t):
        return False        # e.g. Rom 16:24 '[[The grace ...]]': scripture in brackets stays, unlinked
    free = [w for (s, e, w), ok in zip(english_words(t), linkable_mask(t)) if ok]
    # '[No corresponding Hebrew source unit ...]', 'H — [No corresponding text ...]': an editorial note
    return not free or (len(free) == 1 and len(free[0]) <= 2)


def english_words(text: str) -> List[Tuple[int, int, str]]:
    """Word Notes words: (start, end, word), 0-based order = word index."""
    return [(m.start(), m.end(), m.group()) for m in WORD_RE.finditer(text or "")]


def linkable_mask(text: str) -> List[bool]:
    """False for words inside square brackets (supplied English, editorial notes) or an editorial prefix."""
    blocked = bytearray(len(text) + 1)
    depth = 0
    for i, ch in enumerate(text):
        if ch == "[":
            depth += 1
        if depth > 0:
            blocked[i] = 1
        if ch == "]" and depth > 0:
            depth -= 1
    m = _EDITORIAL_PREFIX.match(text)
    if m:
        for i in range(m.start(), m.end()):
            blocked[i] = 1
    return [not any(blocked[s:e]) for s, e, _ in english_words(text)]


def parse_label(ref: str, chapter: Optional[int], book_title: str = "") -> Tuple[str, List[Tuple[int, int]], bool]:
    """'1 Kings 12:24a' -> ('12:24a', [(12, 24)], True); 'Esther 5:1d–1f; 5:2' -> ('5:1d–1f; 5:2', [(5,1),(5,2)], True).

    The chapter of the label is the file's chapter when the reference names another one (Susanna / Bel are
    Daniel 13 / 14 in the files but '1:7' in their references)."""
    ref = (ref or "").strip()
    m = _REF.match(ref)
    if not m:
        label = ref[len(book_title):].strip() if book_title and ref.startswith(book_title) else ref
        return label, [], False
    c = int(m.group(2))
    rest = m.group(3).strip()
    if chapter is not None and int(chapter) != c:
        c = int(chapter)
    label = f"{c}:{rest}"
    targets: List[Tuple[int, int]] = []
    lettered = False
    cur = c
    for part in rest.split(";"):
        pm = _PART.match(part.strip())
        if not pm:
            continue
        cc = int(pm.group(1)) if pm.group(1) else cur
        v1 = int(pm.group(2))
        if pm.group(3) or pm.group(6):
            lettered = True
        if pm.group(5):
            c2 = int(pm.group(4)) if pm.group(4) else cc
            v2 = int(pm.group(5)) if c2 == cc else v1
        else:
            v2 = v1
        for v in range(v1, max(v1, v2) + 1):
            if (cc, v) not in targets:
                targets.append((cc, v))
        cur = cc
    return label, targets, lettered


def _git() -> str:
    g = shutil.which("git")
    if g:
        return g
    for c in (r"C:\Program Files\Git\cmd\git.exe", r"C:\Program Files\Git\bin\git.exe"):
        if os.path.exists(c):
            return c
    return "git"


def _git_show(repo: Path, ref: str, path: str) -> Optional[bytes]:
    r = subprocess.run([_git(), "-C", str(repo), "show", f"{ref}:{path}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def resolve_ref(repo: Path, ref: str) -> Optional[str]:
    r = subprocess.run([_git(), "-C", str(repo), "rev-parse", ref], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def units_from_json(data, code: str) -> List[EnglishUnit]:
    """All units of one verses.json (dict with chapters, or the flat list of Leviticus-Deuteronomy)."""
    field_name = TEXT_FIELD[code]
    title = data.get("book", "") if isinstance(data, dict) else ""
    if isinstance(data, dict):
        rows = [(c.get("chapter"), v) for c in data.get("chapters", []) for v in c.get("verses", [])]
    else:
        rows = [(v.get("chapter"), v) for v in data]
    out: List[EnglishUnit] = []
    for ch, v in rows:
        raw = v.get(field_name) or ""
        cont = v.get("continuation_paragraphs") or []
        if cont:
            raw = raw + " " + " ".join(str(p) for p in cont)
        text = normalise_text(raw)
        ref = v.get("reference") or v.get("ref") or ""          # flat files (Lev-Deut): 'ref': '1:1'
        label, targets, lettered = parse_label(ref, ch if isinstance(ch, int) else None, title)
        out.append(EnglishUnit(label, text, ch if isinstance(ch, int) else None, targets, lettered,
                               is_placeholder(text)))
    return out


def load_english(code: str, book_slug: str, repo: Optional[Path] = None, ref: Optional[str] = None) -> List[EnglishUnit]:
    """Every unit (placeholders included, flagged) of one book of the stream's English column."""
    repo = Path(repo or DEFAULT_REPOS[code])
    ref = ref or DEFAULT_REFS[code]
    raw = _git_show(repo, ref, f"{book_slug}/verses.json")
    if raw is None:
        return []
    return units_from_json(json.loads(raw.decode("utf-8")), code)


# ---------------------------------------------------------------------------
# Dictionaries (open data only)
# ---------------------------------------------------------------------------

def _snum(s: str) -> Optional[int]:
    m = re.match(r"\s*[GH]?0*(\d+)", s or "")
    return int(m.group(1)) if m else None


def _strong_of(lemma_key: Optional[str]) -> Optional[int]:
    if not lemma_key:
        return None
    m = re.match(r"^[GH]0*(\d+)", lemma_key)
    return int(m.group(1)) if m else None


@dataclass
class Dictionaries:
    by_strong: Dict[int, collections.Counter] = field(default_factory=dict)
    by_token: Dict[str, Tuple[str, ...]] = field(default_factory=dict)       # TAGNT ref -> keys
    stats: Dict[str, int] = field(default_factory=dict)

    def add(self, n: int, keys: Iterable[str], w: float = 1.0) -> None:
        c = self.by_strong.get(n)
        if c is None:
            c = self.by_strong[n] = collections.Counter()
        for k in keys:
            c[k] += w


def _fs(path) -> str:
    from .lexica import greek
    return greek._fs(path)


def _stepbible_files(prefix: str) -> List[Path]:
    from .lexica import greek
    d = greek._step_dir() / "Translators Amalgamated OT+NT"
    return sorted(Path(p) for p in glob.glob(str(d / f"{prefix}*.txt")))


def _macula_greek_tsv() -> Optional[Path]:
    from .lexica import greek
    for base in (greek._open_dir(), greek._STUDIO_ROOT / "Saints-Greek-Critical-Text" / "01_Tier1_Modern_Critical_Open"):
        p = base / "NT_Macula_Greek" / "SBLGNT" / "tsv" / "macula-greek-SBLGNT.tsv"
        if os.path.exists(_fs(p)):
            return p
    return None


def _macula_hebrew_tsv() -> Optional[Path]:
    from .lexica import hebrew
    return hebrew.macula_tsv_path()


_TAGNT_REF = re.compile(r"^[1-3A-Z][a-z]{2}\.\d+\.\d+#")


def load_dictionaries(code: str) -> Dictionaries:
    D = Dictionaries()
    st = collections.Counter()
    if code == "grc":
        for f in _stepbible_files("TAGNT"):
            with open(_fs(f), encoding="utf-8") as fh:
                for line in fh:
                    p = line.rstrip("\n").split("\t")
                    if len(p) < 5 or not _TAGNT_REF.match(p[0]):
                        continue
                    st["tagnt_rows"] += 1
                    ks = text_keys(p[2])
                    ref = p[0].split("=")[0]
                    if ks:
                        D.by_token[ref] = tuple(ks)
                    for tag in p[3].split("+"):
                        n = _snum(tag.split("=")[0])
                        if n is not None:
                            D.add(n, ks)
        mg = _macula_greek_tsv()
        if mg:
            with open(_fs(mg), encoding="utf-8", newline="") as fh:
                for d in csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
                    st["macula_greek_rows"] += 1
                    n = _snum(d.get("strong") or "")
                    if n is None:
                        continue
                    D.add(n, text_keys(d.get("english") or ""))
                    D.add(n, text_keys(d.get("gloss") or ""), 0.5)
        mh = _macula_hebrew_tsv()
        if mh:
            with open(_fs(mh), encoding="utf-8", newline="") as fh:
                for d in csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
                    gs = (d.get("greekstrong") or "").strip()
                    if not gs:
                        continue
                    st["macula_hebrew_bridge_rows"] += 1
                    m = re.search(r"\d+", gs)
                    if m:
                        D.add(int(m.group()), text_keys(d.get("english") or ""), 0.5)
    elif code == "heb":
        for f in _stepbible_files("TAHOT"):
            with open(_fs(f), encoding="utf-8") as fh:
                for line in fh:
                    p = line.rstrip("\n").split("\t")
                    if len(p) < 5 or "#" not in p[0] or not _TAGNT_REF.match(p[0]):
                        continue
                    st["tahot_rows"] += 1
                    segs = p[3].split("/")
                    strs = p[4].split("/")
                    m = re.search(r"\{H0*(\d+)", p[4])
                    if not m:
                        continue
                    eng = p[3]
                    if len(segs) == len(strs):
                        for s, e in zip(strs, segs):
                            if "{" in s:
                                eng = e
                    D.add(int(m.group(1)), text_keys(eng))
        mh = _macula_hebrew_tsv()
        if mh:
            with open(_fs(mh), encoding="utf-8", newline="") as fh:
                for d in csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
                    st["macula_hebrew_rows"] += 1
                    n = _snum(d.get("strongnumberx") or "")
                    if n is None:
                        continue
                    D.add(n, text_keys(d.get("english") or ""))
                    D.add(n, text_keys(d.get("gloss") or ""), 0.5)
    D.stats = dict(st)
    return D


# ---------------------------------------------------------------------------
# Transliteration of names
# ---------------------------------------------------------------------------

_GR2LAT = {"α": "a", "β": "b", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": "e", "θ": "th", "ι": "i", "κ": "k",
           "λ": "l", "μ": "m", "ν": "n", "ξ": "x", "ο": "o", "π": "p", "ρ": "r", "σ": "s", "ς": "s", "τ": "t",
           "υ": "u", "φ": "ph", "χ": "ch", "ψ": "ps", "ω": "o"}


def _skeleton(latin: str) -> str:
    s = latin.lower()
    for a, b in (("ph", "f"), ("th", "t"), ("ch", "k"), ("kh", "k"), ("sh", "s"), ("ou", "u"), ("c", "k"),
                 ("q", "k"), ("j", "i"), ("y", "i"), ("w", "u"), ("v", "u"), ("ae", "e"), ("oe", "e")):
        s = s.replace(a, b)
    s = s.replace("h", "")
    s = re.sub(r"[^a-z]", "", s)
    return re.sub(r"(.)\1+", r"\1", s)


def translit(surface: str, lang: str) -> str:
    if lang == "greek":
        nfd = unicodedata.normalize("NFD", surface.lower())
        bare = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
        bare = bare.replace("γγ", "ng").replace("γκ", "nk")
        return _skeleton("".join(_GR2LAT.get(ch, "") for ch in bare))
    if lang == "latin":
        nfd = unicodedata.normalize("NFD", surface)
        return _skeleton("".join(ch for ch in nfd if unicodedata.category(ch) != "Mn"))
    return ""


def name_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


# ---------------------------------------------------------------------------
# IBM Model 1
# ---------------------------------------------------------------------------

NULL = 0


def model1(pairs: Sequence[Tuple[Sequence[int], Sequence[int]]], iterations: int = 5,
           prune: float = 1e-4) -> Dict[int, float]:
    """t(e|f) for integer ids (f = 0 is NULL), keyed ``f << 32 | e``; uniform start, plain EM."""
    t: Dict[int, float] = {}
    for it in range(iterations):
        cnt: Dict[int, float] = collections.defaultdict(float)
        tot: Dict[int, float] = collections.defaultdict(float)
        for es, fs in pairs:
            fs1 = list(fs) + [NULL]
            fk = [f << 32 for f in fs1]
            for e in es:
                if it == 0:
                    ps = [1.0] * len(fs1)
                else:
                    ps = [t.get(k | e, 0.0) for k in fk]
                z = sum(ps)
                if z <= 0:
                    continue
                for f, k, p in zip(fs1, fk, ps):
                    if p:
                        q = p / z
                        cnt[k | e] += q
                        tot[f] += q
        t = {k: v / tot[k >> 32] for k, v in cnt.items()}
    if prune:
        t = {k: v for k, v in t.items() if v >= prune}
    return t


# ---------------------------------------------------------------------------
# Groups (English units x Studio verses)
# ---------------------------------------------------------------------------

@dataclass
class Group:
    units: List[int]          # indexes into the book's English list
    verses: List[int]         # indexes into the book's saints_verses list


def build_groups(units: List[EnglishUnit], verse_keys: List[Tuple[int, int]]) -> Tuple[List[Group], Dict[str, int]]:
    """Union units and Studio verses that share a Saints key; return groups with both sides non-empty."""
    vidx = {k: i for i, k in enumerate(verse_keys)}
    parent: Dict[Tuple[str, int], Tuple[str, int]] = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    st = collections.Counter()
    for ui, u in enumerate(units):
        hits = [vidx[t] for t in u.targets if t in vidx]
        if not hits:
            st["units_without_studio_verse"] += 1
            continue
        for vi in hits:
            union(("u", ui), ("v", vi))
    members: Dict[Tuple[str, int], List[Tuple[str, int]]] = collections.defaultdict(list)
    for x in list(parent):
        members[find(x)].append(x)
    groups = []
    for _, ms in sorted(members.items(), key=lambda kv: min(i for kind, i in kv[1] if kind == "v") if any(k == "v" for k, _ in kv[1]) else 10 ** 9):
        us = sorted(i for kind, i in ms if kind == "u")
        vs = sorted(i for kind, i in ms if kind == "v")
        if us and vs:
            groups.append(Group(us, vs))
    linked_v = {v for g in groups for v in g.verses}
    st["studio_verses_without_english"] = sum(1 for i in range(len(verse_keys)) if i not in linked_v)
    st["groups"] = len(groups)
    st["groups_multi"] = sum(1 for g in groups if len(g.units) > 1 or len(g.verses) > 1)
    return groups, dict(st)


# ---------------------------------------------------------------------------
# The aligner
# ---------------------------------------------------------------------------

@dataclass
class _Tok:
    vi: int
    pos: int
    lemma_key: Optional[str]
    skey: str                 # IBM source key: lemma_key or 'u:<bare>'
    is_content: bool
    surface: str
    src: Optional[str]


@dataclass
class _Eng:
    ui: int
    wi: int
    word: str
    key: str
    keys: Tuple[str, ...]
    cap: bool
    weak: bool                 # light verb or preposition: linked on strong evidence only
    aux: bool = False          # auxiliary 'have': only ever part of its verb's phrase


class Aligner:
    """Trains the stream statistics once; ``align_book`` aligns one book with them."""

    def __init__(self, conn: Optional[sqlite3.Connection], lang: str, *, repo: Optional[Path] = None,
                 ref: Optional[str] = None, iterations: int = 5, verses_by_book: Optional[Dict[str, list]] = None,
                 english_by_book: Optional[Dict[str, List[EnglishUnit]]] = None,
                 lexicon: Optional[dict] = None, dictionaries: Optional[Dictionaries] = None,
                 say: Callable[[str], None] = lambda s: None):
        self.lang = LANG_OF[lang]
        self.code = CODE_OF[self.lang]
        self.column = COLUMN_OF[self.code]
        self.say = say
        self.repo = Path(repo or DEFAULT_REPOS[self.code])
        self.ref = ref or DEFAULT_REFS[self.code]
        t0 = time.time()
        self.source = {"repo": str(self.repo), "ref": self.ref,
                       "commit": resolve_ref(self.repo, self.ref) if english_by_book is None else None,
                       "pinned": PINNED[self.code]}
        if lexicon is None:
            from .concordance_layer import _module
            lexicon = _module(self.lang).load_lexicon()
        self.lexicon = lexicon
        self.dicts = dictionaries if dictionaries is not None else load_dictionaries(self.code)
        say(f"{self.code}: lexicon {len(self.lexicon)}, dictionaries {len(self.dicts.by_strong)} lemmas "
            f"({time.time() - t0:.0f}s)")
        self._lemma_info: Dict[str, tuple] = {}
        self._ext_cache: Dict[str, Tuple[collections.Counter, float]] = {}
        # verses: slug -> list of SaintsVerse-like objects; English: slug -> units
        if verses_by_book is None:
            from .concordance_layer import saints_verses
            verses_by_book = {}
            for slug, vs in saints_verses(conn, self.lang):
                verses_by_book[slug] = [self._compact(v) for v in vs]
        else:
            verses_by_book = {s: [self._compact(v) for v in vs] for s, vs in verses_by_book.items()}
        self.verses = verses_by_book
        self.english: Dict[str, List[EnglishUnit]] = {}
        for slug in self.verses:
            if english_by_book is not None:
                self.english[slug] = english_by_book.get(slug, [])
            else:
                self.english[slug] = load_english(self.code, slug, self.repo, self.ref)
        say(f"{self.code}: {sum(len(v) for v in self.verses.values())} Studio verses, "
            f"{sum(len(u) for u in self.english.values())} English units ({time.time() - t0:.0f}s)")
        self.vocab_e: Dict[str, int] = {}
        self.vocab_f: Dict[str, int] = {"<NULL>": NULL}
        self._train(iterations)
        self.train_seconds = round(time.time() - t0, 1)
        say(f"{self.code}: IBM trained ({self.train_seconds}s)")

    # -- data preparation -------------------------------------------------------------------

    @staticmethod
    def _compact(v) -> tuple:
        """(chapter, verse, [(pos, lemma_key, is_content, surface, src)])"""
        if isinstance(v, tuple):
            return v
        return (v.chapter, v.verse, [(t.index, t.lemma_key, bool(t.is_content), t.surface, getattr(t, "src", None))
                                     for t in v.tokens])

    def _bare(self, s: str) -> str:
        from .lexica import greek_bare, hebrew_consonants, latin_bare
        if self.lang == "greek":
            return greek_bare(s)
        if self.lang == "hebrew":
            return hebrew_consonants(s)
        return latin_bare(s)

    def lemma_info(self, lk: str, is_content: bool) -> tuple:
        """(gloss keys, name-like, candidate) for a lemma."""
        hit = self._lemma_info.get((lk, is_content))
        if hit is not None:
            return hit
        e = self.lexicon.get(lk)
        gloss = e.gloss if e else ""
        pos = e.pos if e else ""
        if pos == "PROPN" and ":" in gloss:
            gloss = gloss.split(":", 1)[0]      # 'Shammah: brother of David ...' -> the name only
        gk = gloss_keys(gloss, grammar_filter=not is_content)
        has_latin = bool(re.search(r"[A-Za-z]", gloss or ""))
        namelike = pos == "PROPN" or not has_latin
        cand = bool(gk) or (namelike and is_content)
        out = (frozenset(gk), namelike, cand)
        self._lemma_info[(lk, is_content)] = out
        return out

    def ext(self, lk: Optional[str]) -> Tuple[collections.Counter, float]:
        if not lk:
            return collections.Counter(), 0.0
        hit = self._ext_cache.get(lk)
        if hit is None:
            n = _strong_of(lk) if self.code in ("grc", "heb") else None
            c = self.dicts.by_strong.get(n, collections.Counter()) if n is not None else collections.Counter()
            hit = self._ext_cache[lk] = (c, float(sum(c.values())))
        return hit

    def _tokens(self, verse_rows: List[tuple], vis: List[int]) -> List[_Tok]:
        out = []
        for vi in vis:
            for pos, lk, ic, surf, src in verse_rows[vi][2]:
                if lk:
                    if not self.lemma_info(lk, ic)[2]:
                        continue
                    out.append(_Tok(vi, pos, lk, lk, ic, surf, src))
                else:
                    b = self._bare(surf)
                    if b:
                        out.append(_Tok(vi, pos, None, "u:" + b, True, surf, src))
        return out

    def _english(self, units: List[EnglishUnit], uis: List[int]) -> List[_Eng]:
        out = []
        seen: Set[str] = set()
        for ui in uis:
            u = units[ui]
            if u.placeholder or u.text in seen:
                continue        # a unit repeating an earlier unit of the group verbatim is aligned once only
            seen.add(u.text)
            words = english_words(u.text)
            plain = [w for _, _, w in words]
            mask = linkable_mask(u.text)
            for wi, ((s, e, w), ok) in enumerate(zip(words, mask)):
                if not ok or is_stop(w) or not re.search(r"[^\W\d_]", w):
                    continue
                k = key(w)
                out.append(_Eng(ui, wi, w, k, word_keys(w), w[:1].isupper(), k in WEAK_WORDS,
                                auxiliary_have(plain, wi)))
        return out

    def _groups(self, slug: str) -> Tuple[List[Group], Dict[str, int]]:
        rows = self.verses.get(slug, [])
        units = self.english.get(slug, [])
        keyed = [u if not u.placeholder else EnglishUnit(u.label, u.text, u.chapter, [], u.lettered, True)
                 for u in units]
        return build_groups(keyed, [(r[0], r[1]) for r in rows])

    def _ids(self, E: List[_Eng], F: List[_Tok], grow: bool) -> Tuple[List[int], List[int]]:
        es, fs = [], []
        for e in E:
            i = self.vocab_e.get(e.key)
            if i is None and grow:
                i = self.vocab_e[e.key] = len(self.vocab_e) + 1
            es.append(i or -1)
        for f in F:
            i = self.vocab_f.get(f.skey)
            if i is None and grow:
                i = self.vocab_f[f.skey] = len(self.vocab_f)
            fs.append(i if i is not None else -1)
        return es, fs

    def _train(self, iterations: int) -> None:
        pairs = []
        for slug in self.verses:
            groups, _ = self._groups(slug)
            units = self.english[slug]
            for g in groups:
                E = self._english(units, g.units)
                F = self._tokens(self.verses[slug], g.verses)
                if E and F:
                    es, fs = self._ids(E, F, True)
                    pairs.append((es, fs))
        self.n_pairs = len(pairs)
        self.t_ef = model1(pairs, iterations)
        self.t_fe = model1([(fs, es) for es, fs in pairs], iterations)

    # -- alignment --------------------------------------------------------------------------

    def _pef(self, e: int, f: int) -> float:
        return self.t_ef.get((f << 32) | e, 0.0) if e > 0 and f >= 0 else 0.0

    def _pfe(self, f: int, e: int) -> float:
        return self.t_fe.get((e << 32) | f, 0.0) if e > 0 and f >= 0 else 0.0

    def align_group(self, E: List[_Eng], F: List[_Tok]) -> List[dict]:
        """Links of one group: dicts with e (index into E), f (index into F), tier, score, why."""
        nE, nF = len(E), len(F)
        if not nE or not nF:
            return []
        es, fs = self._ids(E, F, False)
        # IBM posteriors
        zf = []
        for ei in es:
            zf.append(sum(self._pef(ei, fj) for fj in fs) + self._pef(ei, NULL) if ei > 0 else 0.0)
        zr = []
        for fj in fs:
            zr.append(sum(self._pfe(fj, ei) for ei in es) + (self.t_fe.get(fj, 0.0) if fj >= 0 else 0.0))
        # per-token dictionary facts
        finfo = []
        for f in F:
            if f.lemma_key:
                gk, namelike, _ = self.lemma_info(f.lemma_key, f.is_content)
            else:
                gk, namelike = frozenset(), True
            tk = frozenset(self.dicts.by_token.get(f.src[6:], ())) if f.src and f.src.startswith("tagnt:") else frozenset()
            c, tot = self.ext(f.lemma_key)
            tr = translit(f.surface, self.lang) if namelike and self.lang in ("greek", "latin") else ""
            finfo.append((gk, tk, c, tot, namelike, tr))
        eng_tr = [((_skeleton(e.word),) + tuple(_skeleton(p) for p in e.word.split("-") if len(p) > 2)
                   if e.cap else ()) for e in E]

        def dict_match(ci: int, j: int) -> Tuple[bool, float, str]:
            e = E[ci]
            gk, tk, c, tot, namelike, tr = finfo[j]
            why = ""
            dl = False
            for k in e.keys:
                if k in gk:
                    dl, why = True, "gloss"
                    break
                if k in tk:
                    dl, why = True, "token"
                    break
            share = 0.0
            if tot:
                share = max(c.get(k, 0.0) for k in e.keys) / tot
            if not dl and namelike and tr and eng_tr[ci]:
                if max(name_similarity(tr, x) for x in eng_tr[ci]) >= 0.75:
                    dl, why = True, "name"
            return dl, share, why

        cands = []
        facts = {}
        for ci, e in enumerate(E):
            for j, f in enumerate(F):
                dl, share, why = dict_match(ci, j)
                pef = self._pef(es[ci], fs[j]) / zf[ci] if zf[ci] else 0.0
                pfe = self._pfe(fs[j], es[ci]) / zr[j] if zr[j] else 0.0
                rp = abs((ci + 0.5) / nE - (j + 0.5) / nF)
                # dictionary evidence says the words can match; IBM says which of competing words do here
                sc = (1.5 if dl else 0.0) + min(1.0, share * 4) + 2.0 * (pef + pfe) - 0.6 * rp
                dok = dl or share >= 0.05
                facts[(ci, j)] = (dok, pef, pfe, sc, why or ("dict" if share >= 0.05 else ""), rp)
                cands.append((sc, ci, j))
        cands.sort(key=lambda x: (-x[0], x[1], x[2]))

        def tier_of(ci: int, j: int) -> int:
            dok, pef, pfe, sc, _, rp = facts[(ci, j)]
            if dok and (pef >= 0.3 or pfe >= 0.3):
                return 1
            # dictionary alone, or IBM alone (both ways), only near the diagonal: on the 18 Nov gold sets such
            # links 0.3 or more apart in relative position were right 12 times in 21 (B 2/5, C 10/16)
            if dok and rp < MAX_DISTANCE:
                return 2
            if pef >= 0.5 and pfe >= 0.5 and rp < MAX_DISTANCE:
                return 3
            return 4

        usedE: Dict[int, int] = {}
        usedF: Set[int] = set()
        links: Dict[int, dict] = {}
        pos_of = {(e.ui, e.wi): ci for ci, e in enumerate(E)}

        def extend(ci: int) -> None:
            """Adjacent English words of the same dictionary phrase ('unleavened bread', 'burnt offering',
            'made holy') join the link, unless the word is another source word's own dictionary word."""
            todo = [ci]
            while todo:
                c0 = todo.pop()
                j = links[c0]["f"]
                gk, tk = finfo[j][0], finfo[j][1]
                for nwi in (E[c0].wi - 1, E[c0].wi + 1):
                    cj = pos_of.get((E[c0].ui, nwi))
                    if cj is None or cj in usedE or E[cj].key == E[c0].key:     # 'fear, fear' is two renderings
                        continue
                    if E[cj].weak and E[cj].key not in LIGHT_VERBS:            # prepositions never extend a phrase
                        continue
                    if not any(k in gk or k in tk for k in E[cj].keys):
                        continue
                    if any(dict_match(cj, j2)[0] for j2 in range(nF) if F[j2].skey != F[j].skey):
                        continue
                    usedE[cj] = j
                    links[cj] = {"e": cj, "f": j, "tier": links[ci]["tier"], "score": round(facts[(cj, j)][3], 3),
                                 "why": "phrase"}
                    todo.append(cj)

        # pass 1: everything but light verbs and prepositions, each link taking its phrase neighbours at once
        for sc, ci, j in cands:
            if sc < 0.35:
                break
            if ci in usedE or j in usedF or E[ci].weak or E[ci].aux:
                continue
            usedE[ci] = j
            usedF.add(j)
            links[ci] = {"e": ci, "f": j, "tier": tier_of(ci, j), "score": round(sc, 3), "why": facts[(ci, j)][4]}
            extend(ci)
        # pass 3: light verbs and prepositions on strong evidence only
        for sc, ci, j in cands:
            if not E[ci].weak or E[ci].aux or ci in usedE or j in usedF or sc < 0.35:
                continue
            dok, pef, pfe, _, why, _ = facts[(ci, j)]
            if dok and pef >= 0.3 and pfe >= 0.3:
                usedE[ci] = j
                usedF.add(j)
                links[ci] = {"e": ci, "f": j, "tier": 1, "score": round(sc, 3), "why": why or "dict"}
        # same-lemma links re-paired in reading order: the English words linked to one lemma take, in order,
        # the occurrences of that lemma (linked or still free) that lie closest to the diagonal -- a monotone
        # assignment, kept unless it is further from the diagonal than the greedy one ('people ... people' in a
        # long verse, 'seen ... see', 'lodge ... lodge')
        by_lemma: Dict[str, List[dict]] = collections.defaultdict(list)
        for l in links.values():
            if l["why"] != "phrase":
                by_lemma[F[l["f"]].skey].append(l)

        def dist(e: int, f: int) -> float:
            return abs((e + 0.5) / nE - (f + 0.5) / nF)

        for skey, ls in by_lemma.items():
            ls.sort(key=lambda l: l["e"])
            own = {l["f"] for l in ls}
            toks = [j for j in range(nF) if F[j].skey == skey and (j in own or j not in usedF)]
            if len(toks) < 2:
                continue
            n, m = len(ls), len(toks)
            INF = float("inf")
            # best[i][k]: cost of placing the first i English words on tokens among the first k occurrences
            best = [[0.0] * (m + 1)] + [[INF] * (m + 1) for _ in range(n)]
            for i in range(1, n + 1):
                for k in range(1, m + 1):
                    best[i][k] = min(best[i][k - 1], best[i - 1][k - 1] + dist(ls[i - 1]["e"], toks[k - 1]))
            if best[n][m] == INF:
                continue
            chosen: List[int] = []
            i, k = n, m
            while i > 0:
                if best[i][k] == best[i][k - 1]:
                    k -= 1
                else:
                    chosen.append(toks[k - 1])
                    i, k = i - 1, k - 1
            chosen.reverse()
            before = sum(dist(l["e"], l["f"]) for l in ls)
            if best[n][m] <= before + 1e-9 and [l["f"] for l in ls] != chosen:
                for l in ls:
                    usedF.discard(l["f"])
                for l, j in zip(ls, chosen):
                    l["f"] = j
                    usedF.add(j)
                    if l["why"] not in ("phrase", "compound"):
                        l["tier"] = tier_of(l["e"], j) if not E[l["e"]].weak else l["tier"]
        # phrase links follow their head after re-pairing
        head_of = {}
        for ci, l in links.items():
            if l["why"] == "phrase":
                for nwi in (E[ci].wi - 1, E[ci].wi + 1, E[ci].wi - 2, E[ci].wi + 2):
                    h = pos_of.get((E[ci].ui, nwi))
                    if h is not None and h in links and links[h]["why"] != "phrase" and \
                            F[links[h]["f"]].skey == F[l["f"]].skey:
                        head_of[ci] = h
                        break
        for ci, h in head_of.items():
            links[ci]["f"] = links[h]["f"]
        # one hyphenated English word for two neighbouring source words ('Beth-anoth', 'twenty-four')
        extra: List[dict] = []
        at = {(f.vi, f.pos): j for j, f in enumerate(F)}
        for ci in sorted(links):
            l = links[ci]
            if "-" not in E[ci].word or l["why"] == "phrase":
                continue
            f = F[l["f"]]
            for npos in (f.pos - 1, f.pos + 1, f.pos + 2):
                j2 = at.get((f.vi, npos))
                if j2 is None or j2 in usedF:
                    continue
                if dict_match(ci, j2)[0]:
                    usedF.add(j2)
                    extra.append({"e": ci, "f": j2, "tier": l["tier"], "score": l["score"], "why": "compound"})
        return [links[ci] for ci in sorted(links)] + extra

    def align_book(self, book_slug: str, verses: Optional[list] = None) -> dict:
        t0 = time.time()
        if verses is not None:
            rows = [self._compact(v) for v in verses]
            self.verses[book_slug] = rows
        rows = self.verses.get(book_slug, [])
        units = self.english.get(book_slug)
        if units is None:
            units = self.english[book_slug] = load_english(self.code, book_slug, self.repo, self.ref)
        # English list without placeholders; map old unit index -> exported index
        export_idx: Dict[int, int] = {}
        english = []
        for ui, u in enumerate(units):
            if u.placeholder:
                continue
            export_idx[ui] = len(english)
            english.append([u.label, u.text, u.sha])
        groups, gst = self._groups(book_slug)
        all_links = []
        st = collections.Counter()
        for g in groups:
            E = self._english(units, g.units)
            F = self._tokens(rows, g.verses)
            for l in self.align_group(E, F):
                e, f = E[l["e"]], F[l["f"]]
                all_links.append([export_idx[e.ui], e.wi, e.wi + 1, f.vi, f.pos, l["tier"]])
        all_links = merge_ranges(all_links)
        keep = set(EXPORT_TIERS.get(self.code, ()))
        links = [l for l in all_links if l[5] in keep]
        st.update(gst)
        st.update(self.coverage(book_slug, all_links, english, rows))
        st["seconds"] = round(time.time() - t0, 2)
        return {"book": book_slug, "lang": self.code, "column": self.column, "english": english,
                "links": links, "all_links": all_links, "export_tiers": sorted(keep), "stats": dict(st),
                "source": self.source}

    def coverage(self, slug: str, all_links: List[list], english: List[list], rows: List[tuple]) -> Dict[str, int]:
        """Counts for coverage: English content words / source content tokens, linked at each tier or better."""
        st: Dict[str, int] = collections.Counter()
        # English content words of units that belong to a group
        groups, _ = self._groups(slug)
        units = self.english.get(slug, [])
        in_group = {ui for g in groups for ui in g.units}
        ex = {}
        n = 0
        for ui, u in enumerate(units):
            if u.placeholder:
                continue
            ex[ui] = n
            n += 1
        best_e: Dict[Tuple[int, int], int] = {}
        best_f: Dict[Tuple[int, int], int] = {}
        for en, a, b, vi, pos, tier in all_links:
            for w in range(a, b):
                best_e[(en, w)] = min(best_e.get((en, w), 9), tier)
            best_f[(vi, pos)] = min(best_f.get((vi, pos), 9), tier)
        for ui in in_group:
            u = units[ui]
            if u.placeholder:
                continue
            for wi, ((s, e, w), ok) in enumerate(zip(english_words(u.text), linkable_mask(u.text))):
                if not ok or is_stop(w) or not re.search(r"[^\W\d_]", w):
                    continue
                st["en_content"] += 1
                t = best_e.get((ex[ui], wi))
                for k in (1, 2, 3, 4):
                    if t is not None and t <= k:
                        st[f"en_linked_t{k}"] += 1
        in_group_v = {vi for g in groups for vi in g.verses}
        for vi in in_group_v:
            for pos, lk, ic, surf, src in rows[vi][2]:
                if not (lk and ic):
                    continue
                st["src_content"] += 1
                t = best_f.get((vi, pos))
                for k in (1, 2, 3, 4):
                    if t is not None and t <= k:
                        st[f"src_linked_t{k}"] += 1
        return st


def merge_ranges(links: List[list]) -> List[list]:
    """Join adjacent English words linked to the same token at the same tier into one half-open range."""
    links = sorted(links, key=lambda l: (l[3], l[4], l[0], l[1]))
    out: List[list] = []
    for l in links:
        if out:
            p = out[-1]
            if p[0] == l[0] and p[3] == l[3] and p[4] == l[4] and p[5] == l[5] and p[2] == l[1]:
                p[2] = l[2]
                continue
        out.append(list(l))
    out.sort(key=lambda l: (l[0], l[1], l[3], l[4]))
    return out


# ---------------------------------------------------------------------------
# Module API
# ---------------------------------------------------------------------------

_ALIGNERS: Dict[str, Aligner] = {}


def get_aligner(conn: sqlite3.Connection, lang: str, **kw) -> Aligner:
    code = CODE_OF[LANG_OF[lang]]
    a = _ALIGNERS.get(code)
    if a is None:
        a = _ALIGNERS[code] = Aligner(conn, lang, **kw)
    return a


def align_book(conn: sqlite3.Connection, lang: str, book_slug: str) -> dict:
    """One book in the spec's 'A' format plus its English unit list (statistics trained once per stream)."""
    return get_aligner(conn, lang).align_book(book_slug)


def align_all(conn: sqlite3.Connection, lang: str, say: Callable[[str], None] = lambda s: None) -> dict:
    """Every book of the stream, the statistics trained once; returns per-book results and corpus totals."""
    t0 = time.time()
    a = get_aligner(conn, lang, say=say)
    books: Dict[str, dict] = {}
    tot: Dict[str, int] = collections.Counter()
    tiers = collections.Counter()
    for slug in a.verses:
        r = a.align_book(slug)
        books[slug] = r
        for k, v in r["stats"].items():
            if isinstance(v, int):
                tot[k] += v
        for l in r["all_links"]:
            tiers[TIER_NAMES[l[5]]] += 1
    out = {"lang": a.code, "column": a.column, "books": books, "source": a.source,
           "export_tiers": list(EXPORT_TIERS.get(a.code, ())), "totals": dict(tot), "links_by_tier": dict(tiers),
           "train_pairs": a.n_pairs, "train_seconds": a.train_seconds, "seconds": round(time.time() - t0, 1)}
    out["coverage"] = coverage_summary(tot)
    return out


def coverage_summary(tot: Dict[str, int]) -> Dict[str, float]:
    out = {}
    for k in (1, 2, 3, 4):
        if tot.get("en_content"):
            out[f"en_{'ABCD'[:k]}"] = round(tot.get(f"en_linked_t{k}", 0) / tot["en_content"], 4)
        if tot.get("src_content"):
            out[f"src_{'ABCD'[:k]}"] = round(tot.get(f"src_linked_t{k}", 0) / tot["src_content"], 4)
    return out


def wilson(k: int, n: int, z: float = 1.959964) -> Tuple[float, float]:
    """Wilson score interval for k successes out of n."""
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))
