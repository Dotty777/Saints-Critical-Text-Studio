"""GLAUx parses for the Studio's Greek Old Testament (Saints Concordance, added 18 Nov 2026).

The Saints Critical Greek Text of the Old Testament (the Studio's Swete / Codex B stream) has
lemma tags from ``greek.py`` but no openly licensed word-by-word parsing.  GLAUx (Keersmaekers
2021) annotates the el.wikisource Septuagint (CC BY-SA 3.0) with a lemma and an AGDT 9-position
part-of-speech tag per word.  The owner approved GLAUx for Septuagint parsing on 18 Nov 2026.
This module aligns every Studio Greek OT token to a GLAUx word and gives the token that word's
parse when, and only when, the two are the same word:

* Source: ``Corpus_GLAUx_Annotated_XML/xml/0527-*.xml`` (the 57 Septuagint files).  Only the
  files of books the Studio prints are read (``BOOK_FILES``); every one of them has
  SOURCE_LICENSE 'CC-BY-SA 3.0' in metadata.txt (el.wikisource), and the only manual treebank
  annotations among them (Pedalion Trees, Genesis; Harrington Trees, Susanna, not used) are
  CC BY-SA 4.0.  ``licence_report()`` re-reads metadata.txt and refuses any file whose source
  licence is not CC BY-SA / CC BY / CC0 / public domain (an NC / ND licence is skipped).
* Mapping: GLAUx files are in el.wikisource (Rahlfs-like) numbering; the Studio prints Saints
  numbering.  Instead of a hand-made verse table the mapping is established by content, verse by
  verse: candidates are the GLAUx verse with the same label (``BOOK_FILES`` gives chapter
  offsets, e.g. Nehemiah = 2 Esdras 11-23), the verses right after the previous match, and the
  three best verses of the whole book by shared rare words (the book-level fallback that finds
  moved chapters, Esther's additions, Sirach's prologue, Proverbs 24-31 and the Psalms).  The
  best candidate and its neighbours (a +-1 verse window, extended forward while the Studio verse
  is longer) are aligned to the Studio tokens.  ``mapping_report()`` summarises per book how
  often the chosen GLAUx verse has the Studio verse's own label.
* Alignment: an order-preserving sequence alignment by accent-insensitive form (``greek_bare``
  of NFC text), movable nu (ἐστιν / ἐστι) and elision (δ᾽ / δέ) allowed.  A GLAUx word is used
  by at most one Studio token per book.  The parse is taken ONLY on such a form match.  A second
  pass pairs left-over tokens with left-over GLAUx words in the same gap when the forms differ
  only by spelling (ει/ι, doubled consonants, σσ/ττ, μψ/ψ, μφ/φ, in the stem; the ending must be
  identical); such a pair is taken only when the GLAUx lemma is the Studio lemma.
* Lemma guard: a parse is never taken when the GLAUx lemma conflicts with the Studio lemma
  (compared with ``greek_bare`` of the headwords, spelling variants and the suppletive
  principal parts λέγω/εἶπον, ὁράω/εἶδον ... counting as the same lemma).  A form match whose
  accents disagree (ἡ / ἤ, ἀλλά / ἄλλα) is taken only when the Studio lemma confirms it.
* Output: ``TokenTag.morph = 'A:' + postag`` ('A:v3saia---'), ``TokenTag.src = 'glaux:' +
  word id``, and the note ``'machine parse (GLAUx, automatic)'`` when the GLAUx sentence is not
  manually annotated (everything except most of Genesis).  ``morph_legend()`` expands every
  postag into English.  Lemma tags are never changed here.

GLAUx's automatic morphology is about 97.2% accurate (README); its tagger was trained partly on
treebanks under non-commercial licences (PROIEL, Gorman), but the GLAUx annotations themselves
are released under CC BY-SA 4.0 and are used here under that licence.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from . import TokenTag, greek_bare, tokenize_verse

MORPH_SCHEME = "A"            # TokenTag.morph prefix of GLAUx / AGDT parses: 'A:v3saia---'
SRC_PREFIX = "glaux:"
NOTE_MACHINE = "machine parse (GLAUx, automatic)"
NOTE_SPELLING = "GLAUx parse of a spelling variant ({form})"

ATTRIBUTION = (
    "Septuagint parsing: GLAUx (the Greek Language Automated), Alek Keersmaekers, "
    "https://github.com/alekkeersmaekers/glaux, CC BY-SA 4.0. Keersmaekers, A. (2021): The GLAUx "
    "corpus: methodological issues in designing a long-term, diverse, multi-layered corpus of "
    "Ancient Greek. Proceedings of the 2nd International Workshop on Computational Approaches to "
    "Historical Language Change 2021, 39-50. doi:10.18653/v1/2021.lchange-1.6. Source texts: "
    "Septuagint from el.wikisource.org (CC BY-SA 3.0); Genesis manual annotation from the Pedalion "
    "Trees (Jonas Roose, Alek Keersmaekers, Toon Van Hal; CC BY-SA 4.0). Parses are aligned to the "
    "Saints Critical Greek Text automatically and are machine parses unless marked otherwise."
)
SRC_GLAUX = "GLAUx 0527-* Septuagint (Keersmaekers 2021; CC BY-SA 4.0; texts el.wikisource CC BY-SA 3.0)"

_OPEN_LICENCE = re.compile(r"^(CC[- ]?BY(-SA)?|CC0|PUBLIC ?DOMAIN|PD)\b", re.I)
_CLOSED_LICENCE = re.compile(r"\b(NC|ND)\b", re.I)

# ---------------------------------------------------------------------------
# Studio book -> GLAUx file: (file id, first GLAUx chapter, last GLAUx chapter, chapter offset)
# Studio chapter = GLAUx chapter - offset.  Chapters outside [first, last] are not read.
# ---------------------------------------------------------------------------

_ALL = (None, None, 0)
BOOK_FILES: Dict[str, Tuple[str, Optional[int], Optional[int], int]] = {
    "genesis": ("0527-001",) + _ALL, "exodus": ("0527-002",) + _ALL,
    "leviticus": ("0527-003",) + _ALL, "numbers": ("0527-004",) + _ALL,
    "deuteronomy": ("0527-005",) + _ALL, "joshua": ("0527-006",) + _ALL,
    "judges": ("0527-009",) + _ALL,             # the B-type text (διὰ τοῦ κυρίου, 1:1), like Swete
    "ruth": ("0527-010",) + _ALL,
    "1-samuel": ("0527-011",) + _ALL, "2-samuel": ("0527-012",) + _ALL,
    "1-kings": ("0527-013",) + _ALL, "2-kings": ("0527-014",) + _ALL,
    "1-chronicles": ("0527-015",) + _ALL, "2-chronicles": ("0527-016",) + _ALL,
    "ezra": ("0527-018", 1, 10, 0),             # 2 Esdras 1-10
    "nehemiah": ("0527-018", 11, 23, 10),       # 2 Esdras 11-23 = Nehemiah 1-13
    "esther": ("0527-019",) + _ALL, "1-maccabees": ("0527-023",) + _ALL,
    "2-maccabees": ("0527-024",) + _ALL, "psalms": ("0527-027",) + _ALL,
    "proverbs": ("0527-029",) + _ALL, "ecclesiastes": ("0527-030",) + _ALL,
    "song-of-songs": ("0527-031",) + _ALL, "job": ("0527-032",) + _ALL,
    "wisdom-of-solomon": ("0527-033",) + _ALL, "sirach": ("0527-034",) + _ALL,
    "hosea": ("0527-036",) + _ALL, "amos": ("0527-037",) + _ALL, "micah": ("0527-038",) + _ALL,
    "joel": ("0527-039",) + _ALL, "obadiah": ("0527-040",) + _ALL, "jonah": ("0527-041",) + _ALL,
    "nahum": ("0527-042",) + _ALL, "habakkuk": ("0527-043",) + _ALL,
    "zephaniah": ("0527-044",) + _ALL, "haggai": ("0527-045",) + _ALL,
    "zechariah": ("0527-046",) + _ALL, "malachi": ("0527-047",) + _ALL,
    "isaiah": ("0527-048",) + _ALL, "jeremiah": ("0527-049",) + _ALL,
    "lamentations": ("0527-051",) + _ALL, "ezekiel": ("0527-053",) + _ALL,
    "daniel": ("0527-057",) + _ALL,             # Theodotion (0527-056 is the Old Greek)
    # outside the Studio's 70-book canon, kept so the module works if they are added
    "1-esdras": ("0527-017",) + _ALL, "judith": ("0527-020",) + _ALL,
    "tobit": ("0527-022",) + _ALL,              # the long (Sinaiticus) text; 0527-021 is BA
    "3-maccabees": ("0527-025",) + _ALL, "4-maccabees": ("0527-026",) + _ALL,
    "psalms-of-solomon": ("0527-035",) + _ALL, "baruch": ("0527-050",) + _ALL,
    "letter-of-jeremiah": ("0527-052",) + _ALL, "susanna": ("0527-055",) + _ALL,
    "bel-and-the-dragon": ("0527-059",) + _ALL,
}

# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

_STUDIO_ROOT = Path(__file__).resolve().parents[2]
_GLAUX_SUBDIR = Path("06_Tier6_Associated_SecondTemple_Patristic") / "Corpus_GLAUx_Annotated_XML"


def glaux_dir() -> Path:
    """The GLAUx corpus folder (holding README.md, metadata.txt and xml/)."""
    cands = []
    try:
        from ..catalog import GREEK_RESEARCH_ROOT  # respects CTS_REPO_ROOT
        cands.append(Path(GREEK_RESEARCH_ROOT) / _GLAUX_SUBDIR)
    except Exception:  # pragma: no cover - catalog problems must not hide the corpus
        pass
    cands.append(_STUDIO_ROOT / "Saints-Greek-Critical-Text" / _GLAUX_SUBDIR)
    for c in cands:
        if (c / "metadata.txt").exists():
            return c
    return cands[-1]


def corpus_available() -> bool:
    d = glaux_dir()
    return (d / "metadata.txt").exists() and (d / "xml" / "0527-001.xml").exists()


# ---------------------------------------------------------------------------
# Licences (metadata.txt)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _metadata() -> Dict[str, Dict[str, str]]:
    path = glaux_dir() / "metadata.txt"
    out: Dict[str, Dict[str, str]] = {}
    with open(path, encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            row = dict(zip(header, line.rstrip("\n").split("\t")))
            tlg = row.get("TLG", "")
            if tlg.startswith("0527-"):
                out[tlg] = row
    return out


def licence_ok(licence: str) -> bool:
    """CC BY-SA, CC BY, CC0 or public domain; anything NC / ND (or unknown) is refused."""
    lic = (licence or "").strip()
    return bool(_OPEN_LICENCE.match(lic)) and not _CLOSED_LICENCE.search(lic)


def licence_report() -> List[Dict[str, str]]:
    """One row per 0527-* text in metadata.txt: id, title, source, source licence, treebank
    (manual annotation project or 'NA'), whether its licence allows use here, and whether the
    Studio uses it (``BOOK_FILES``)."""
    used = {v[0] for v in BOOK_FILES.values()}
    studio = _studio_book_files()
    rows = []
    for tlg, r in sorted(_metadata().items()):
        tb = r.get("TREEBANK_ANNOTATIONS", "NA")
        ok = licence_ok(r.get("SOURCE_LICENSE", ""))
        rows.append({
            "file": tlg, "title": r.get("TITLE_STANDARD", ""), "source": r.get("SOURCE", ""),
            "source_licence": r.get("SOURCE_LICENSE", ""), "treebank": tb,
            "allowed": "yes" if ok else "no", "mapped": "yes" if tlg in used else "no",
            "studio_book": ",".join(sorted(s for s, f in studio.items() if f == tlg)),
        })
    return rows


def _studio_book_files() -> Dict[str, str]:
    return {slug: v[0] for slug, v in BOOK_FILES.items()}


def _file_allowed(file_id: str) -> bool:
    row = _metadata().get(file_id)
    return bool(row) and licence_ok(row.get("SOURCE_LICENSE", ""))


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

_ELISION_MARKS = "᾽’'ʼ᾿"
_GRAVE = "̀"
_ACUTE = "́"
_CIRC = "͂"
_BREATHINGS = ("̓", "̔")

# Elided spellings of function words (bare letters): bare -> full bare forms.
_ELIDED = {
    "δ": ["δε"], "τ": ["τε"], "γ": ["γε"],
    "απ": ["απο"], "αφ": ["απο"], "κατ": ["κατα"], "καθ": ["κατα"], "μετ": ["μετα"], "μεθ": ["μετα"],
    "επ": ["επι"], "εφ": ["επι"], "υπ": ["υπο"], "υφ": ["υπο"], "παρ": ["παρα"], "αλλ": ["αλλα"],
    "δι": ["δια"], "αντ": ["αντι"], "ανθ": ["αντι"], "αν": ["ανα"], "ουδ": ["ουδε"], "μηδ": ["μηδε"],
    "ουτ": ["ουτε"], "μητ": ["μητε"], "τουτ": ["τουτο"], "ταυτ": ["ταυτα"], "εστ": ["εστι"],
    "ιν": ["ινα"], "ειτ": ["ειτα"], "ειθ": ["ειτα"], "ποτ": ["ποτε"], "ποθ": ["ποτε"],
    "εγωγ": ["εγωγε"], "ταυθ": ["ταυτα"], "τουθ": ["τουτο"],
}


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _nu_variants(bare: str) -> List[str]:
    """Movable ν and οὕτω(ς): the other spelling of the same form."""
    out = []
    if len(bare) > 2 and bare.endswith("ν") and bare[-2] in "ει":
        out.append(bare[:-1])
    elif len(bare) > 2 and bare[-1] in "ει" and not bare.endswith("ει"):
        out.append(bare + "ν")
    if bare == "ουτωσ":
        out.append("ουτω")
    elif bare == "ουτω":
        out.append("ουτωσ")
    return out


def _has_elision(token: str) -> bool:
    return bool(token) and token[-1] in _ELISION_MARKS


def form_keys(token: str) -> List[str]:
    """Bare lookup keys of a form: the bare form, its movable-ν twin, the unelided form."""
    b = greek_bare(token)
    keys = [b] if b else []
    keys += [k for k in _nu_variants(b) if k not in keys]
    if b in _ELIDED and (_has_elision(token) or len(b) <= 4):
        keys += [k for k in _ELIDED[b] if k not in keys]
    return keys


def forms_match(a: str, b: str) -> bool:
    """Same form, accent-insensitively, allowing movable ν and elision."""
    ka, kb = form_keys(a), form_keys(b)
    return bool(ka and kb) and (ka[0] in kb or kb[0] in ka)


def accent_sig(text: str) -> Tuple[str, Tuple[Tuple[int, str], ...]]:
    """(breathing of the first letters, accents as (letter position from the start, kind)); grave
    counts as acute.  Counted from the start so that movable ν (εἶπεν / εἶπε) does not move it."""
    letters: List[str] = []
    breath = ""
    accents: List[Tuple[int, str]] = []
    for ch in unicodedata.normalize("NFD", text.lower()):
        if unicodedata.category(ch) == "Mn":
            if ch in _BREATHINGS and len(letters) <= 2:
                breath = ch
            elif ch in (_ACUTE, _GRAVE, _CIRC) and letters:
                accents.append((len(letters) - 1, _CIRC if ch == _CIRC else _ACUTE))
            continue
        if "α" <= ch <= "ω" or ch == "ς":
            letters.append(ch)
    return breath, tuple(sorted(accents))


def accents_compatible(a: str, b: str) -> bool:
    """Same word as far as breathings and accents show: identical, one side without marks, or an
    extra accent thrown back by an enclitic.  ἡ/ἤ, ἀλλά/ἄλλα, ὅ/ὃ (same) / οὗ/οὐ are told apart."""
    ba, aa = accent_sig(a)
    bb, ab = accent_sig(b)
    if ba and bb and ba != bb:
        return False
    if not aa or not ab or aa == ab:
        return True
    if len(aa) == 2 and len(ab) == 1:       # ἄνθρωπός τις: the second accent is the enclitic's
        return ab[0] == aa[0]
    if len(ab) == 2 and len(aa) == 1:
        return aa[0] == ab[0]
    return False


def _spelling_accents_compatible(a: str, b: str) -> bool:
    """Accent compatibility for a spelling-variant pair (ει/ι, doubled consonant, unassimilated
    nasal): compare initial breathing and accent positions counted from the end (since the
    inflectional ending is identical, stem length shifts like ει/ι do not disturb it)."""
    if accents_compatible(a, b):
        return True
    ba, _ = accent_sig(a)
    bb, _ = accent_sig(b)
    if ba and bb and ba != bb:
        return False

    def _end_accents(text: str) -> Tuple[Tuple[int, str], ...]:
        letters: List[str] = []
        accs: List[Tuple[int, str]] = []
        for ch in unicodedata.normalize("NFD", text.lower()):
            if unicodedata.category(ch) == "Mn":
                if ch in (_ACUTE, _GRAVE, _CIRC) and letters:
                    accs.append((len(letters) - 1, _CIRC if ch == _CIRC else _ACUTE))
                continue
            if "α" <= ch <= "ω" or ch == "ς":
                letters.append(ch)
        n = len(letters)
        return tuple(sorted((n - 1 - pos, kind) for pos, kind in accs))

    ea, eb = _end_accents(a), _end_accents(b)
    if not ea or not eb or ea == eb:
        return True
    if len(ea) == 2 and len(eb) == 1:
        return eb[0] == ea[1]
    if len(eb) == 2 and len(ea) == 1:
        return ea[0] == eb[1]
    return False


_NASAL_VELAR = re.compile(r"ν(?=[κγχξ])")
_NASAL_LABIAL = re.compile(r"ν(?=[πβφψμ])")


def _spell_norm(bare: str) -> str:
    b = bare.replace("ει", "ι").replace("γιγν", "γιν").replace("ολοθρ", "ολεθρ")
    b = _NASAL_VELAR.sub("γ", b)
    b = _NASAL_LABIAL.sub("μ", b)
    b = b.replace("νλ", "λλ").replace("συνσ", "συσ").replace("μπτ", "πτ").replace("μψ", "ψ").replace("μφ", "φ").replace("ττ", "σσ")
    return re.sub(r"([βγδζθκλμνξπρστφχψ])\1", r"\1", b)


def spelling_variant_forms(a: str, b: str) -> bool:
    """Two forms that differ only in the spelling of the stem (ει/ι, doubled consonants, σσ/ττ,
    μψ/ψ, μφ/φ) with the same last two letters, so the same inflection."""
    x, y = greek_bare(a), greek_bare(b)
    if x == y or len(x) < 4 or len(y) < 4:
        return False
    if x[-2:] != y[-2:]:                    # the inflectional ending itself must be identical
        return False
    return _spell_norm(x) == _spell_norm(y)


# One lexeme under two headword conventions: suppletive principal parts (λέγω / εἶπον), comparatives
# listed under their positive (πρέσβυς / πρεσβύτερος), -νυμι / -ω verbs, epic / contracted / Attic
# spellings (φάος / φῶς, ἐθέλω / θέλω, μείς / μήν) and the names the two sources spell differently
# (Ἱεροσόλυμα / Ἱερουσαλήμ, Σαῦλος / Σαούλ).  Taken from the most frequent GLAUx-Studio lemma
# disagreements over the whole Greek OT (18 Nov 2026), only where both name the same word.
_SUPPLETIVE_GROUPS = [
    ("λεγω", "ειπον", "επω", "ερω", "ερεω", "ειρω", "ρεω"), ("οραω", "ειδον", "ειδω", "οιδα", "οπτομαι", "οπτανομαι"),
    ("ερχομαι", "ηλθον", "ελευθω"), ("φερω", "ενεγκω", "οιω"), ("εσθιω", "φαγω", "φαγειν", "εδω"),
    ("τρεχω", "δραμω"), ("αιρεω", "ελω", "ειλον"), ("πασχω", "πενθω"), ("πινω", "πιω"),
    ("γινομαι", "γιγνομαι"), ("γινωσκω", "γιγνωσκω"), ("εγω", "ημεισ"), ("συ", "υμεισ"),
    ("τισ", "τι"), ("ωνεομαι", "πριαμαι"),
    ("μεγασ", "μειζων", "μεγιστοσ", "μεγαλωσ"), ("πολυσ", "πλειων", "πλειστοσ"),
    ("αγαθοσ", "βελτιων", "κρεισσων", "αριστοσ", "κρειττων", "κρατυσ"),
    ("κακοσ", "χειρων", "ηττων", "ησσων"), ("μικροσ", "ελασσων", "ελαχιστοσ", "ελαττων", "ελαχυσ"),
    ("ενεκα", "ενεκεν", "εινεκεν"), ("πρεσβυσ", "πρεσβυτεροσ"), ("μαλα", "μαλλον", "μαλιστα"),
    ("ταχυσ", "ταχεωσ"), ("ου", "ουχι", "ουκ"), ("δεω", "δει", "δεομαι"), ("υπαρχω", "υπαρχοντα"),
    ("απολλυμι", "απολλυω"), ("ανοιγνυμι", "ανοιγω"), ("διανοιγνυμι", "διανοιγω"),
    ("δεικνυμι", "δεικνυω"), ("διασκεδαννυμι", "διασκεδαζω"), ("κρεμαννυμι", "κρεμαω"),
    ("πιμπλημι", "πληθω"), ("εμπιμπρημι", "εμπρηθω"), ("ρυομαι", "ρυω", "ερυω"),
    ("επισκοπεω", "επισκεπτομαι"), ("εθελω", "θελω"), ("φαοσ", "φωσ"), ("μεισ", "μην"),
    ("αοιδη", "ωδη"), ("αειδω", "αδω"), ("δακρυον", "δακρυ"), ("νεομηνια", "νουμηνια"),
    ("ορεινη", "ορεινοσ"), ("κυκλοσ", "κυκλω"), ("περικυκλοσ", "περικυκλω"), ("ιλαοσ", "ιλεωσ"),
    ("ιεροσολυμα", "ιερουσαλημ"), ("σολομων", "σαλωμων", "σολομων"), ("σαυλοσ", "σαυλιοσ", "σαουλ"),
    ("ιωναθησ", "ιωναθαν"),
]
_SUPPLETIVE: Dict[str, int] = {}
for _gi, _grp in enumerate(_SUPPLETIVE_GROUPS):
    for _w in _grp:
        _SUPPLETIVE[greek_bare(_w)] = _gi


def _lemma_norm(lemma: str) -> str:
    b = greek_bare(re.sub(r"\d+$", "", lemma or ""))
    if b.endswith("ομαι"):
        b = b[:-4] + "ω"
    return _spell_norm(b.replace("ω", "ο").replace("η", "ι").replace("υ", "ι"))


def _edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return prev[-1]


def lemma_agreement(glaux_lemma: str, studio_lemma: str) -> str:
    """'same' (greek_bare equal), 'spelling' (headword spelling / ending variant: Μωυσῆς/Μωσῆς,
    πετεινόν/πετεινός), 'suppletive' (λέγω/εἶπον) or 'conflict'."""
    a = greek_bare(re.sub(r"\d+$", "", glaux_lemma or ""))
    b = greek_bare(re.sub(r"\d+$", "", studio_lemma or ""))
    if not a or not b:
        return "conflict"
    if a == b:
        return "same"
    ga, gb = _SUPPLETIVE.get(a), _SUPPLETIVE.get(b)
    if ga is not None and ga == gb:
        return "suppletive"
    if len(a) < 4 or len(b) < 4:            # short words: only identical headwords agree
        return "conflict"
    na, nb = _lemma_norm(a), _lemma_norm(b)
    if na == nb:
        return "spelling"
    if _edit_distance(na, nb) > 1 or na[:2] != nb[:2]:
        return "conflict"
    # one edit apart: proper names (Ἰωσίας / Ιωσια), or a noun / adjective whose headwords differ
    # only in the ending (πετεινόν / πετεινός, ὠδίς / ὠδίν); never two verbs (πειράω / πειράζω)
    proper = (glaux_lemma or "")[:1].isupper() or (studio_lemma or "")[:1].isupper()
    verb = any(x.endswith(("ω", "μαι", "μι")) for x in (a, b))
    lcp = next((i for i, (x, y) in enumerate(zip(na, nb)) if x != y), min(len(na), len(nb)))
    tail = lcp >= min(len(na), len(nb)) - 1
    if proper or (tail and not verb):
        return "spelling"
    return "conflict"


# ---------------------------------------------------------------------------
# GLAUx files
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"<word ([^>]*)/>")
_SENT_RE = re.compile(r"<sentence ([^>]*)>")
_ATTR_RE = re.compile(r'(\w+)="([^"]*)"')
_SECTION_RE = re.compile(r"^(\d+)([^\d.]*)\.(\d+)(.*)$")
_SECTION1_RE = re.compile(r"^(\d+)(.*)$")
_GREEK_LETTER = re.compile(r"[Ͱ-Ͽἀ-῿]")

# word tuple fields
W_ID, W_FORM, W_BARE, W_LEMMA, W_POSTAG, W_MANUAL = range(6)


@dataclass
class Group:
    """One GLAUx verse (div_section) in file order."""
    label: Tuple[int, int, str]          # (chapter, verse, letter suffixes) in GLAUx numbering
    section: str                         # the raw div_section ('1.1', '24b.3', '1.1α')
    words: List[tuple] = field(default_factory=list)   # (id, form NFC, bare, lemma NFC, postag, manual)


def _label(chapter: Optional[str], section: str) -> Optional[Tuple[int, int, str]]:
    m = _SECTION_RE.match(section)
    if m:
        return int(m.group(1)), int(m.group(3)), (m.group(2) + m.group(4)).strip()
    m = _SECTION1_RE.match(section)
    if m:
        ch = int(chapter) if chapter and chapter.isdigit() else 1
        return ch, int(m.group(1)), m.group(2).strip()
    return None


@lru_cache(maxsize=6)
def load_file(file_id: str) -> Tuple[Group, ...]:
    """Every verse group of one GLAUx file, words in order.  Punctuation and artificial
    (elliptic) nodes are dropped.  Refuses files whose source licence is not open."""
    if not _file_allowed(file_id):
        raise PermissionError(f"GLAUx {file_id}: source licence not open (see licence_report())")
    path = glaux_dir() / "xml" / f"{file_id}.xml"
    with open(path, encoding="utf-8") as fh:
        data = fh.read()
    groups: List[Group] = []
    by_section: Dict[str, Group] = {}
    manual = False
    sent_iter = list(_SENT_RE.finditer(data))
    si = 0
    for m in _WORD_RE.finditer(data):
        while si < len(sent_iter) and sent_iter[si].start() < m.start():
            sattrs = dict(_ATTR_RE.findall(sent_iter[si].group(1)))
            manual = sattrs.get("analysis") == "manual"
            si += 1
        a = dict(_ATTR_RE.findall(m.group(1)))
        if a.get("artificial"):
            continue
        form = _nfc(a.get("form", ""))
        postag = a.get("postag", "")
        if not form or not _GREEK_LETTER.search(form) or postag.startswith("u"):
            continue
        section = a.get("div_section", "")
        chapter = a.get("div_chapter") or a.get("div_psalm") or a.get("div_ode")
        g = by_section.get(section)
        if g is None:
            lab = _label(chapter, section)
            if lab is None:
                continue
            g = by_section[section] = Group(lab, section)
            groups.append(g)
        g.words.append((a.get("id", ""), form, greek_bare(form), _nfc(a.get("lemma", "")), postag, manual))
    return tuple(groups)


@lru_cache(maxsize=8)
def _id_index(file_id: str) -> Dict[str, tuple]:
    return {w[W_ID]: w for g in load_file(file_id) for w in g.words}


_LAST_WORD_FILE: Optional[str] = None


def word_by_id(word_id: str, file_id: Optional[str] = None) -> Optional[tuple]:
    """The GLAUx word tuple (W_* fields) with this id ('glaux:' prefix allowed); ``file_id``
    narrows the search to one file, otherwise every mapped file is searched."""
    global _LAST_WORD_FILE
    if word_id.startswith(SRC_PREFIX):
        word_id = word_id[len(SRC_PREFIX):]
    if file_id:
        files = [file_id]
    else:
        files = sorted({v[0] for v in BOOK_FILES.values()})
        if _LAST_WORD_FILE and _LAST_WORD_FILE in files:
            files = [_LAST_WORD_FILE] + [f for f in files if f != _LAST_WORD_FILE]
    for f in files:
        if _file_allowed(f):
            w = _id_index(f).get(word_id)
            if w is not None:
                _LAST_WORD_FILE = f
                return w
    return None


# ---------------------------------------------------------------------------
# Book index and alignment
# ---------------------------------------------------------------------------

@dataclass
class Pick:
    """The GLAUx word a Studio token was aligned to."""
    word: tuple                 # GLAUx word tuple (W_* fields)
    kind: str                   # 'exact' (form match) | 'spelling' (stem spelling variant; lemma must agree)
    accents_ok: bool            # breathings/accents compatible
    group: Tuple[int, int, str]  # GLAUx label of the word's verse
    gi: int = -1                # index of that verse in BookIndex.groups

    @property
    def morph(self) -> str:
        return f"{MORPH_SCHEME}:{self.word[W_POSTAG]}"

    @property
    def src(self) -> str:
        return SRC_PREFIX + self.word[W_ID]

    @property
    def lemma(self) -> str:
        return self.word[W_LEMMA]

    @property
    def manual(self) -> bool:
        return bool(self.word[W_MANUAL])


class BookIndex:
    """GLAUx verse groups of one Studio book with a rare-word index for the book-level search."""

    def __init__(self, slug: str) -> None:
        file_id, first, last, offset = BOOK_FILES[slug]
        self.slug = slug
        self.file_id = file_id
        self.offset = offset
        groups = [g for g in load_file(file_id)
                  if (first is None or g.label[0] >= first) and (last is None or g.label[0] <= last)]
        self.groups: List[Group] = groups
        self.by_label: Dict[Tuple[int, int], List[int]] = defaultdict(list)
        self.counts: List[Counter] = []
        postings: Dict[str, List[int]] = defaultdict(list)
        for gi, g in enumerate(groups):
            self.by_label[(g.label[0] - offset, g.label[1])].append(gi)
            c = Counter()
            for w in g.words:
                c[w[W_BARE]] += 1
            self.counts.append(c)
            for b in c:
                postings[b].append(gi)
        n = max(1, len(groups))
        cap = max(40, int(n * 0.03))
        self.postings = {b: gis for b, gis in postings.items() if len(gis) <= cap}
        self.idf = {b: math.log(n / len(gis)) for b, gis in self.postings.items()}

    def search(self, keys: Sequence[str], k: int = 3) -> List[int]:
        score: Dict[int, float] = defaultdict(float)
        for b in set(keys):
            gis = self.postings.get(b)
            if gis:
                w = self.idf[b]
                for gi in gis:
                    score[gi] += w
        return [gi for gi, _ in sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))[:k]]


@lru_cache(maxsize=8)
def book_index(slug: str) -> BookIndex:
    return BookIndex(slug)


def _overlap(keys: List[List[str]], counts: Counter) -> int:
    c = Counter(counts)
    n = 0
    for ks in keys:
        for k in ks:
            if c.get(k, 0) > 0:
                c[k] -= 1
                n += 1
                break
    return n


def _align(tokens: List[str], keys: List[List[str]], words: List[tuple], weights: List[float]
           ) -> List[Tuple[int, int]]:
    """Order-preserving alignment maximising the summed weight of form matches."""
    n, m = len(tokens), len(words)
    if not n or not m:
        return []
    W = [[0.0] * m for _ in range(n)]
    wbare = [w[W_BARE] for w in words]
    wk = [_wkeys(w) for w in words]
    for i in range(n):
        ks = keys[i]
        if not ks:
            continue
        k0 = ks[0]
        Wi = W[i]
        for j in range(m):
            wb = wbare[j]
            if wb == k0:
                Wi[j] = weights[j] + 0.002
            elif wb in ks or k0 in wk[j]:
                Wi[j] = weights[j]
    D = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        Wi = W[i - 1]
        Di, Dp = D[i], D[i - 1]
        for j in range(1, m + 1):
            best = Dp[j] if Dp[j] >= Di[j - 1] else Di[j - 1]
            w = Wi[j - 1]
            if w > 0.0 and Dp[j - 1] + w > best:
                best = Dp[j - 1] + w
            Di[j] = best
    out = []
    i, j = n, m
    while i > 0 and j > 0:
        w = W[i - 1][j - 1]
        if w > 0.0 and abs(D[i][j] - (D[i - 1][j - 1] + w)) < 1e-9:
            out.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif D[i - 1][j] >= D[i][j - 1]:
            i -= 1
        else:
            j -= 1
    out.reverse()
    return out


@lru_cache(maxsize=200000)
def _wkeys_form(form: str) -> Tuple[str, ...]:
    return tuple(form_keys(form))


def _wkeys(w: tuple) -> Tuple[str, ...]:
    return _wkeys_form(w[W_FORM])


@dataclass
class VerseAlignment:
    tokens: List[str]                    # tokenize_verse(text, 'grc')
    picks: List[Optional[Pick]]          # one per token
    group: Optional[Tuple[int, int, str]]  # GLAUx label of the best verse (None: nothing found)
    how: str                             # 'label' | 'next' | 'search' | 'none'


class _BookAligner:
    def __init__(self, idx: BookIndex) -> None:
        self.idx = idx
        self.used: Set[str] = set()
        self.used_counts: Dict[int, Counter] = defaultdict(Counter)
        self.cursor = -1

    def align_verse(self, ch: int, vs: int, text: str, consume: bool = True) -> VerseAlignment:
        idx = self.idx
        tokens = tokenize_verse(text, "grc")
        picks: List[Optional[Pick]] = [None] * len(tokens)
        if not tokens or not idx.groups:
            return VerseAlignment(tokens, picks, None, "none")
        keys = [form_keys(t) for t in tokens]
        flat = [k for ks in keys for k in ks]
        # candidate spans of GLAUx verses: the verse(s) with the same label (lettered sub-verses
        # 8:12a-x form one span), the verses after the previous match, the book-level search
        label = sorted(idx.by_label.get((ch, vs), []))
        cands: Dict[Tuple[int, int], str] = {}
        if label and label[-1] - label[0] + 1 <= len(label) + 2:
            cands[(label[0], label[-1])] = "label"
        else:
            for gi in label:
                cands.setdefault((gi, gi), "label")
        if self.cursor >= 0:
            for gi in range(self.cursor, min(len(idx.groups), self.cursor + 3)):
                cands.setdefault((gi, gi), "next")
        for gi in idx.search(flat, 3):
            cands.setdefault((gi, gi), "search")
        if not cands:
            return VerseAlignment(tokens, picks, None, "none")
        rank = {"label": 2, "next": 1, "search": 0}
        span, best_score = None, -1.0
        for (a, z), how in cands.items():
            avail: Counter = Counter()
            for gi in range(a, z + 1):
                avail.update(idx.counts[gi])
                if gi in self.used_counts:
                    avail.subtract(self.used_counts[gi])
            s = _overlap(keys, avail) + 0.1 * rank[how]
            if s > best_score:
                span, best_score = (a, z), s
        how = cands[span]
        best = span[0]
        # window: one verse before, the best span, further verses while the Studio verse is longer,
        # and one verse after
        lo = max(0, best - 1)
        hi = span[1]
        size = sum(len(idx.groups[gi].words) for gi in range(best, hi + 1))
        while hi + 1 < len(idx.groups) and size < len(tokens) * 1.15 and hi - best < 60:
            hi += 1
            size += len(idx.groups[hi].words)
        core_hi = hi
        hi = min(len(idx.groups) - 1, hi + 1)
        words: List[tuple] = []
        weights: List[float] = []
        gl: List[int] = []
        for gi in range(lo, hi + 1):
            core = best <= gi <= core_hi
            for w in idx.groups[gi].words:
                if w[W_ID] in self.used:
                    continue
                words.append(w)
                weights.append(1.0 if core else 0.9)
                gl.append(gi)
        pairs = _align(tokens, keys, words, weights)
        for i, j in pairs:
            w = words[j]
            picks[i] = Pick(w, "exact", accents_compatible(tokens[i], w[W_FORM]), idx.groups[gl[j]].label)
            picks[i].gi = gl[j]
        # second pass: spelling variants in the gaps between matched pairs
        bounds = [(-1, -1)] + pairs + [(len(tokens), len(words))]
        taken_j = {j for _, j in pairs}
        for (i0, j0), (i1, j1) in zip(bounds, bounds[1:]):
            if i1 - i0 <= 1 or j1 - j0 <= 1:
                continue
            for i in range(i0 + 1, i1):
                for j in range(j0 + 1, j1):
                    if j in taken_j:
                        continue
                    w = words[j]
                    if spelling_variant_forms(tokens[i], w[W_FORM]):
                        picks[i] = Pick(w, "spelling", _spelling_accents_compatible(tokens[i], w[W_FORM]),
                                        idx.groups[gl[j]].label)
                        picks[i].gi = gl[j]
                        taken_j.add(j)
                        j0 = j
                        break
        if consume:
            for p in picks:
                if p is not None:
                    self.used.add(p.word[W_ID])
                    self.used_counts[p.gi][p.word[W_BARE]] += 1
            self.cursor = max(best, max((p.gi for p in picks if p is not None), default=best))
        return VerseAlignment(tokens, picks, idx.groups[best].label, how)


_BOOK_CACHE: "OrderedDict[Tuple[str, str], Dict[Tuple[int, int], VerseAlignment]]" = OrderedDict()


def _digest(chapters: Dict[int, Dict[int, str]]) -> str:
    h = hashlib.sha1()
    for ch in sorted(chapters):
        for v in sorted(chapters[ch]):
            h.update(f"{ch}:{v}:{chapters[ch][v]}\n".encode("utf-8"))
    return h.hexdigest()


def align_book(book_slug: str, chapters: Dict[int, Dict[int, str]]) -> Dict[Tuple[int, int], VerseAlignment]:
    """Align a whole Studio Greek OT book (``{chapter: {verse: critical text}}``, Studio numbering)
    to GLAUx, verses in Studio order.  Cached per book and text (the last 4 books)."""
    if book_slug not in BOOK_FILES or not corpus_available():
        return {}
    key = (book_slug, _digest(chapters))
    hit = _BOOK_CACHE.get(key)
    if hit is not None:
        _BOOK_CACHE.move_to_end(key)
        return hit
    aligner = _BookAligner(book_index(book_slug))
    out: Dict[Tuple[int, int], VerseAlignment] = {}
    for ch in sorted(chapters):
        for vs in sorted(chapters[ch]):
            out[(ch, vs)] = aligner.align_verse(ch, vs, chapters[ch][vs] or "")
    _BOOK_CACHE[key] = out
    while len(_BOOK_CACHE) > 4:
        _BOOK_CACHE.popitem(last=False)
    return out


# ---------------------------------------------------------------------------
# Decisions (lemma guard) and the public API
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _lexicon():
    from . import greek
    return greek.load_lexicon()


def _studio_lemma(lemma_key: Optional[str]) -> Optional[str]:
    if not lemma_key:
        return None
    e = _lexicon().get(lemma_key)
    return e.lemma if e is not None else None


@dataclass
class Parse:
    morph: str
    src: str
    notes: List[str]
    glaux_lemma: str
    kind: str                  # 'exact' | 'spelling'
    lemma_agreement: str       # 'same' | 'spelling' | 'suppletive' | 'no-studio-lemma'


def decide(pick: Optional[Pick], studio_lemma: Optional[str]) -> Tuple[Optional[Parse], str]:
    """Take or refuse a pick.  Returns (Parse or None, reason): 'taken', 'no-pick',
    'lemma-conflict', 'accents-unconfirmed' (accents disagree and no Studio lemma confirms),
    'spelling-unconfirmed' (spelling pair whose lemma is not the Studio lemma)."""
    if pick is None:
        return None, "no-pick"
    if studio_lemma:
        agree = lemma_agreement(pick.lemma, studio_lemma)
        if agree == "conflict":
            return None, "lemma-conflict"
    else:
        agree = "no-studio-lemma"
        if not pick.accents_ok:
            return None, "accents-unconfirmed"
    notes: List[str] = []
    if pick.kind == "spelling":
        if agree not in ("same", "spelling"):
            return None, "spelling-unconfirmed"
        notes.append(NOTE_SPELLING.format(form=pick.word[W_FORM]))
    if not pick.manual:
        notes.append(NOTE_MACHINE)
    return Parse(pick.morph, pick.src, notes, pick.lemma, pick.kind, agree), "taken"


def _token_text(t) -> str:
    return t.surface if isinstance(t, TokenTag) else str(t)


def morph_for(book_slug: str, chapter: int, verse_number: int, tokens: Sequence,
              book_chapters: Optional[Dict[int, Dict[int, str]]] = None) -> List[Optional[Parse]]:
    """GLAUx parse of each token of one Studio Greek OT verse (Studio numbering), or None.

    ``tokens``: the verse's TokenTags (their lemma_key guards the parse) or token strings (no
    lemma guard; accent-incompatible matches are refused).  ``book_chapters``: the whole book's
    text ``{chapter: {verse: text}}``; given, the verse is read from the cached book alignment
    (each GLAUx word used once in the book); otherwise the verse is aligned on its own."""
    n = len(tokens)
    if book_slug not in BOOK_FILES or not corpus_available() or not n:
        return [None] * n
    texts = [_nfc(_token_text(t)) for t in tokens]
    va: Optional[VerseAlignment] = None
    if book_chapters is not None and verse_number in book_chapters.get(chapter, {}):
        va = align_book(book_slug, book_chapters).get((chapter, verse_number))
        if va is not None and [_nfc(x) for x in va.tokens] != texts:
            va = None                      # the tokens are not that verse's: align them on their own
    if va is None:
        va = _BookAligner(book_index(book_slug)).align_verse(chapter, verse_number, " ".join(texts), consume=False)
        if len(va.picks) != n:
            return [None] * n
    out: List[Optional[Parse]] = []
    for t, pick in zip(tokens, va.picks):
        lemma = _studio_lemma(t.lemma_key) if isinstance(t, TokenTag) else None
        parse, _ = decide(pick, lemma)
        out.append(parse)
    return out


STATS: Counter = Counter()      # running counts of fill_chapter decisions (reset with STATS.clear())


def fill_chapter(book_slug: str, chapter: int, tagged: Dict[int, List[TokenTag]],
                 book_chapters: Dict[int, Dict[int, str]]) -> int:
    """Give every token of ``tagged`` (one Studio Greek OT chapter, as returned by
    ``greek.tag_chapter``) whose ``morph`` is None the GLAUx parse, src and machine note.  Lemma
    tags are not touched.  Returns the number of tokens filled; a no-op without the corpus."""
    if book_slug not in BOOK_FILES or not corpus_available():
        return 0
    book = align_book(book_slug, book_chapters)
    filled = 0
    for vs, tags in tagged.items():
        va = book.get((chapter, vs))
        if va is None:
            continue
        if [_nfc(x) for x in va.tokens] != [_nfc(t.surface) for t in tags]:
            STATS["verse-token-mismatch"] += len(tags)
            continue
        for t, pick in zip(tags, va.picks):
            if t.morph is not None:
                STATS["already-parsed"] += 1
                continue
            parse, why = decide(pick, _studio_lemma(t.lemma_key))
            STATS[why] += 1
            if parse is None:
                continue
            t.morph = parse.morph
            t.src = parse.src
            for note in parse.notes:
                if note not in t.notes:
                    t.notes.append(note)
            filled += 1
    return filled


# Attic / Perseus GLAUx headwords whose Studio (TBESG / GWL) Koine headword differs,
# plus confirmed GLAUx automatic-lemmatiser typos on Septuagint forms.
_GLAUX_TO_STUDIO_HEAD: Dict[str, str] = {
    "αειδω": "ᾄδω", "αοιδη": "ᾠδή", "αειρω": "αἴρω", "μεισ": "μήν",
    "οιμοι": "οἴμμοι", "οιδα": "εἴδω", "εφοραω": "ἐπεῖδον", "συνοραω": "συνεῖδον",
    "πιμπλημι": "πλήθω", "εμπιμπρημι": "ἐμπρήθω", "απολλυμι": "ἀπολλύω",
    "κρεμαννυμι": "κρεμάω", "διασκεδαννυμι": "διασκεδάζω", "εθελω": "θέλω",
    "φαοσ": "φῶς", "νεομηνια": "νουμηνία", "ιλαοσ": "ἵλεως",
    "κρατυσ": "κρείσσων", "ελαχυσ": "ἐλάχιστος", "παρανοχλεω": "παρενοχλέω",
    "ενωπιοσ": "ἐνώπιον", "δακρυον": "δάκρυ", "βορεασ": "βορρᾶς",
    "τιρυμι": "ῥύομαι", "ευρνυμι": "εὑρίσκω", "συνζωννυμι": "συζώννυμι",
    "στορεννυμι": "στρώννυμι", "απεαρα": "ἀπαίρω", "κατηιρνω": "καταράομαι",
    "ρινι": "ῥίς",
    "συνιεω": "συνίημι", "αποκταμω": "ἀποκτείνω", "ανοχλεω": "ἐνοχλέω",
    "διεγγελαω": "διαγγέλλω", "συνηλαμαι": "συνελαύνω", "αποφηναμαι": "ἀποφαίνω",
    "οσφραντιθημι": "ὀσφραίνομαι", "οσφιμρανκω": "ὀσφραίνομαι",
    "εισμικρυνω": "σμικρύνω", "διφαγωμι": "ἐσθίω", "κοσμοω": "κοσμέω",
    "αδωνασ": "Ἀδωναΐ",
    "ιξηρημι": "ἐξαίρω", "αποστρεβλοω": "ἀποστρεβαλόομαι", "θεειμ": "θεΐμ",
    "διαθαζω": "διατίθημι", "ρυαννυμι": "ῥέω", "ρυιημι": "ῥέω",
    "ηδυναζομαι": "δύναμαι", "ροαι": "ῥόα", "επαγαω": "πήγνυμι",
    "ενεπαγαω": "ἐμπήγνυμι", "προαομαι": "προΐημι", "διανοισσω": "διανοίγω",
    "διαδιαιταω": "διαιτάω", "αποσχαω": "ἀπέχω", "πιεω": "πίνω",
    "παρανηλοω": "παραναλίσκω", "υπερομαι": "ὕπερος", "πιοσ": "πίων",
    "κατασχυω": "καταισχύνω", "εξαρψανω": "ἐξέρπω",
    "υποστορεννυμι": "ὑποστρωννύω", "πιμπλαω": "πλήθω",
    "εξαποσταλαω": "ἐξαποστέλλω", "επιμωκεομαι": "μωκάομαι",
    "εξαειρω": "ἐξαίρω", "αμαρτεω": "ἁμαρτάνω", "παρακατεθομαι": "παρακατατίθημι",
}

_AGDT_POS_HINT: Dict[str, str] = {
    "v": "V", "n": "N", "a": "ADJ", "d": "ADV", "p": "PRON", "l": "ART",
    "r": "PREP", "c": "CONJ", "b": "CONJ", "g": "PART", "m": "NUM", "i": "INTERJ", "e": "INTERJ",
}

# Swete print breathing/accent variants on unambiguous lowercase words where no competing Greek word exists.
_SWETE_LOWER_ACCENT_OK = frozenset({"ὄτι", "οὗν", "ἃν", "νηί", "δρύος", "ὀδοὺς", "κυρίᾳ", "ἠχοῦς"})

_AGDT_COMPAT_POS: Dict[str, Set[str]] = {
    "v": {"V"},
    "n": {"N", "PROPN"},
    "a": {"ADJ", "N", "PROPN"},
    "d": {"ADV", "PREP", "PART", "CONJ"},
    "p": {"PRON", "ADJ"},
    "l": {"ART", "PRON"},
    "r": {"PREP", "ADV"},
    "c": {"CONJ", "PART", "ADV"},
    "b": {"CONJ", "PART", "ADV"},
    "g": {"PART", "CONJ", "ADV"},
    "m": {"NUM", "ADJ", "ADV"},
    "i": {"INTERJ", "PART"},
    "e": {"INTERJ", "PART"},
}


@lru_cache(maxsize=1)
def _studio_lex_index():
    from . import greek
    lex = greek.load_lexicon()
    by_acc: Dict[str, List[Tuple[str, object]]] = defaultdict(list)
    by_bare: Dict[str, List[Tuple[str, object]]] = defaultdict(list)
    for k, e in lex.items():
        by_acc[greek.accent_key(e.lemma)].append((k, e))
        by_bare[greek_bare(e.lemma)].append((k, e))
    return lex, dict(by_acc), dict(by_bare)


def _koine_bare_variants(gb: str, is_verb: bool) -> List[str]:
    """Regular Attic -> Koine headword variants of a GLAUx bare lemma."""
    cands: List[str] = []

    def add(s: str) -> None:
        if s and s != gb and s not in cands:
            cands.append(s)

    if "γιγν" in gb:
        add(gb.replace("γιγν", "γιν"))
    if "ειγν" in gb:
        add(gb.replace("ειγν", "ιγν"))
    if "ττ" in gb:
        add(gb.replace("ττ", "σσ"))
    if "σσ" in gb:
        add(gb.replace("σσ", "ττ"))
    if is_verb:
        for base in [gb] + list(cands):
            if base.endswith("ομαι"):
                add(base[:-4] + "ω")
            elif base.endswith("ουμαι"):
                add(base[:-5] + "εω")
                add(base[:-5] + "οω")
            elif base.endswith("ωμαι"):
                add(base[:-4] + "αω")
            elif base.endswith("ω"):
                add(base[:-1] + "ομαι")
            if base.endswith("νυμαι"):
                add(base[:-5] + "νυμι")
                add(base[:-5] + "νυω")
            if base.endswith("νυμι"):
                add(base[:-4] + "νυω")
            if base.endswith("γνυμι"):
                add(base[:-5] + "γω")
            if base.endswith("ννυμι"):
                add(base[:-5] + "ζω")
    return cands


def _resolve_glaux_lemma(pick: Pick, surface: str, excl: Set[str]) -> Optional[str]:
    """Map a GLAUx Pick's lemma to a unique Studio Greek lexicon key, or None when ambiguous or
    absent from the Studio lexicon."""
    from . import greek
    raw = re.sub(r"\d+$", "", pick.lemma or "").strip()
    if not raw:
        return None
    _lex, by_acc, by_bare = _studio_lex_index()
    postag = pick.word[W_POSTAG] or ""
    p0 = postag[:1]
    compat = _AGDT_COMPAT_POS.get(p0)
    surf_cap = bool(surface[:1].isupper())
    gl_cap = bool(raw[:1].isupper())

    def _filter(hits: List[Tuple[str, object]]) -> Optional[str]:
        if not hits:
            return None
        cands = [(k, e) for k, e in hits if k not in excl]
        if not surf_cap:
            cands = [(k, e) for k, e in cands if getattr(e, "pos", "") != "PROPN"]
        if len(cands) > 1 and compat:
            pos_ok = [(k, e) for k, e in cands if getattr(e, "pos", "") in compat]
            if pos_ok:
                cands = pos_ok
        if len(cands) > 1:
            # Prefer proper vs common matching GLAUx's own capitalisation (Ῥώμη vs ῥώμη)
            case_ok = [(k, e) for k, e in cands if (getattr(e, "pos", "") == "PROPN") == gl_cap]
            if case_ok:
                cands = case_ok
        return cands[0][0] if len(cands) == 1 else None

    # GLAUx lemmatises homograph verbs together: disambiguate strictly by morphology/accents.
    gb = greek_bare(raw)
    sb = greek_bare(surface)
    if gb == "δεω":
        if sb.startswith(("δεη", "εδεη", "δεομ", "δεωμ", "δεου", "δεει", "δεῃ", "εδειτ", "δειτ", "εδεετ", "εδεοντ")):
            return "G1189" if "G1189" not in excl and "G1189" in _lex else None
        if sb in ("δει", "εδει", "δεον", "δεοι", "δεησει"):
            return "G1163" if "G1163" not in excl and "G1163" in _lex else None
        if sb.startswith(("δησ", "εδησ", "δεδ", "δεθ", "εδεθ")):
            return "G1210" if "G1210" not in excl and "G1210" in _lex else None
        return None
    if gb == "απτω" and len(postag) >= 5:
        if postag[4] in ("m", "p", "e") and "G0680" not in excl and "G0680" in _lex:
            return "G0680"
        if postag[4] == "a" and "G0681" not in excl and "G0681" in _lex:
            return "G0681"
    if gb == "χραω" and len(postag) >= 5:
        if postag[4] in ("m", "p", "e") and "G5530" not in excl and "G5530" in _lex:
            return "G5530"
        if postag[4] == "a" and "G5531" not in excl and "G5531" in _lex:
            return "G5531"
    if gb == "που":
        if "ῦ" in surface.lower() or "͂" in unicodedata.normalize("NFD", surface.lower()):
            return "G4226" if "G4226" not in excl and "G4226" in _lex else None
        return "G4225" if "G4225" not in excl and "G4225" in _lex else None
    if gb == "απειμι" and sb.startswith(("απεστ", "απη", "απω", "απουσ", "απον")):
        return "G0548" if "G0548" not in excl and "G0548" in _lex else None
    if gb == "συνειμι" and sb.startswith(("συνεστ", "συνη", "συνω", "συνουσ", "συνον")) and not sb.startswith("συνηγμ"):
        return "G4895" if "G4895" not in excl and "G4895" in _lex else None
    # Form-guarded GLAUx automatic-lemmatiser slips
    if gb in ("ραω", "ρω", "ρηθοομαι") and sb.startswith("ρηθ"):
        raw, gb = "λέγω", "λεγω"
    elif gb == "ααω" and sb.startswith(("ασα", "ασο", "ασω")):
        raw, gb = "ᾄδω", "αδω"
    elif gb == "ιαζω" and sb.startswith("ιασ"):
        raw, gb = "ἰάομαι", "ιαομαι"
    elif gb == "αχθεω" and sb.startswith("ηχθ"):
        raw, gb = "ἄγω", "αγω"
    elif gb == "εξοσ" and sb.startswith("εξωτατ"):
        raw, gb = "ἐξώτερος", "εξωτεροσ"
    elif gb == "υπερομαι" and sb == "υπερου":
        raw, gb, p0 = "ὕπερος", "υπεροσ", "n"
        compat = _AGDT_COMPAT_POS.get(p0)
    elif gb == "αρ" and sb == "ατηρ":
        raw, gb = "Ἀτήρ", "ατηρ"
    elif gb == "συνειμι" and sb.startswith("συνηγμ"):
        raw, gb = "συνάγω", "συναγω"
    # 1. Exact accented match in Studio lexicon
    key = _filter(by_acc.get(greek.accent_key(raw), []))
    if key is not None:
        return key
    # 2. Explicit Attic -> Koine / lemmatiser-fix headword map
    mapped = _GLAUX_TO_STUDIO_HEAD.get(gb)
    if mapped:
        key = _filter(by_acc.get(greek.accent_key(mapped), []))
        if key is not None:
            return key
        key = _filter(by_bare.get(greek_bare(mapped), []))
        if key is not None:
            return key
    # 3. Regular Attic -> Koine bare variants
    for vb in _koine_bare_variants(gb, p0 == "v"):
        key = _filter(by_bare.get(vb, []))
        if key is not None:
            return key
    # 4. Unique bare match in existing Studio lexicon
    key = _filter(by_bare.get(gb, []))
    if key is not None:
        return key
    # 4b. Lowercase Swete print of a proper name / ethnonym (χαλδαίων -> Χαλδαῖος, ἀδωναὶ -> Ἀδωναΐ)
    # when GLAUx capitalises the word and no lowercase common-word entry has the same letters.
    if not surf_cap and gl_cap and p0 == "n":
        for cand_b in [gb] + ([greek_bare(mapped)] if mapped else []):
            raw_hits = [(k, e) for k, e in by_bare.get(cand_b, []) if k not in excl]
            if raw_hits and all(getattr(e, "pos", "") == "PROPN" for _, e in raw_hits) and len(raw_hits) == 1:
                return raw_hits[0][0]
    # 5. Open lexical sources (TBESG / GWL / TFLSJ-extra / Perseus LSJ) not yet seen in TAGNT / LxxLemmas
    tagger = greek.get_tagger()
    pos_hint = _AGDT_POS_HINT.get(p0)
    for cand_head in [raw] + ([mapped] if mapped else []):
        ext = tagger.lex.resolve_external_lemma(cand_head, pos_hint=pos_hint, allow_propn=surf_cap, allow_lsj=True)
        if ext is not None and ext not in excl:
            return ext
    # 6. Proper-name spelling variant against an already-known Studio PROPN entry
    if surf_cap and gl_cap and p0 == "n" and len(gb) >= 4:
        pn = greek._propn_norm(gb)
        propn_hits = [k for k, e in _lex.items()
                      if getattr(e, "pos", "") == "PROPN" and greek._propn_norm(greek_bare(e.lemma)) == pn
                      and k not in excl]
        if len(propn_hits) == 1:
            return propn_hits[0]
    # 7. GLAUx-attested Codex B proper name or indeclinable Hebrew transliteration absent from
    #    Rahlfs / GWL / TBESG (e.g. Ζαφωΐν, Γασιών, Isa 19:18 πόλις ἀσεδέκ)
    if ((surf_cap and gl_cap and p0 == "n") or (postag == "n--------" and sb == gb and len(gb) >= 5)) and (
            len(gb) >= 3 and re.fullmatch(r"[Ͱ-Ͽἀ-῿]+", raw)):
        lk = "grc:" + raw
        if lk not in excl:
            tagger.lex.ensure_entry(lk, head=raw, pos="PROPN" if surf_cap else "N", source=SRC_GLAUX)
            return lk
    return None


_GLAUX_FORM_AMBIG_SHORT = frozenset({
    "η", "ο", "ω", "ει", "αν", "εν", "ων", "μη", "ου", "μην", "δει", "πασ", "παν", "τισ", "τι", "δε", "τε", "γε",
})


@lru_cache(maxsize=1)
def _glaux_form_table():
    """Corpus-wide accent-aware form -> (lemma, postag_prefix) counts built lazily from the
    open-licensed 0527-* Septuagint files in BOOK_FILES."""
    from . import greek
    by_acc: Dict[Tuple[str, bool], Counter] = defaultdict(Counter)
    by_breath: Dict[Tuple[str, bool], Set[str]] = defaultdict(set)
    by_spell: Dict[Tuple[str, bool], Counter] = defaultdict(Counter)
    for file_id in sorted({v[0] for v in BOOK_FILES.values()}):
        if not _file_allowed(file_id):
            continue
        for g in load_file(file_id):
            for w in g.words:
                form = w[W_FORM]
                lem = re.sub(r"\d+$", "", w[W_LEMMA] or "").strip()
                pt = w[W_POSTAG] or ""
                if not form or not lem or not pt or pt.startswith("u"):
                    continue
                bare = w[W_BARE]
                if len(bare) < 3:
                    continue
                is_cap = form[:1].isupper()
                ak = greek.accent_key(form)
                if not ak:
                    continue
                val = (lem, pt[:5])
                by_acc[(ak, is_cap)][val] += 1
                bk = greek._accent_sig(ak)[0]
                by_breath[(bk, is_cap)].add(ak)
                if len(bare) >= 6:
                    by_spell[(_spell_norm(bare), is_cap)][val] += 1
    return dict(by_acc), dict(by_breath), dict(by_spell)


def _glaux_corpus_form_lookup(surface: str, excl: Set[str]) -> Optional[Tuple[str, str, int, int]]:
    """Fallback lookup in the open-licensed GLAUx Septuagint form table when verse alignment had
    no pick (e.g. Swete vs Rahlfs textual variants).  Requires >= 95% single-lemma unanimity and
    exact accent/breathing compatibility (or >= 6-letter orthographic equivalence)."""
    from . import greek
    bare = greek_bare(surface)
    if len(bare) < 3 or bare in _GLAUX_FORM_AMBIG_SHORT:
        return None
    ak = greek.accent_key(surface)
    if not ak:
        return None
    is_cap = surface[:1].isupper()
    by_acc, by_breath, by_spell = _glaux_form_table()
    # Check exact accent key (+ movable nu) for same case; for capitalised sentence-openers also
    # allow lowercase verb/adjective/adverb forms (never common nouns -> capitalised names).
    case_tries = [is_cap] + ([False] if is_cap else [])
    c = Counter()
    used_lower_for_cap = False
    for cap_flag in case_tries:
        for a_try in [ak] + greek._nu_twins(ak):
            hit = by_acc.get((a_try, cap_flag))
            if hit:
                c.update(hit)
        if not c:
            bk, tpos = greek._accent_sig(ak)
            for b_try in [bk] + greek._nu_twins(bk):
                for other_ak in by_breath.get((b_try, cap_flag), ()):
                    if greek._accents_compatible(tpos, greek._accent_sig(other_ak)[1]):
                        c.update(by_acc.get((other_ak, cap_flag), ()))
        if not c and len(bare) >= 6:
            sp_hit = by_spell.get((_spell_norm(bare), cap_flag))
            if sp_hit:
                c.update(sp_hit)
        if c:
            used_lower_for_cap = is_cap and not cap_flag
            break
    if not c:
        return None
    # Collapse counts by lemma (keeping most frequent postag prefix for each lemma)
    by_lem: Counter = Counter()
    best_pt: Dict[str, Tuple[int, str]] = {}
    for (lem, pt5), n in c.items():
        if used_lower_for_cap and pt5.startswith("n"):
            continue  # never map a capitalised token onto a lowercase common noun
        if not is_cap and lem[:1].isupper() and greek_bare(lem) != "βορεασ":
            continue  # never map a lowercase token onto a capitalised proper name
        by_lem[lem] += n
        if lem not in best_pt or n > best_pt[lem][0]:
            best_pt[lem] = (n, pt5)
    if not by_lem:
        return None
    top_lem, n = by_lem.most_common(1)[0]
    tot = sum(by_lem.values())
    min_cnt = 5 if len(bare) <= 3 else (2 if len(bare) <= 4 else 1)
    min_share = 1.0 if len(bare) <= 3 else 0.95
    if n < min_cnt or (n / tot) < min_share:
        return None
    pt5 = best_pt[top_lem][1]
    fake_pick = Pick(("0", surface, bare, top_lem, pt5.ljust(9, "-"), False), "exact", True, (0, 0, ""))
    key = _resolve_glaux_lemma(fake_pick, surface, excl)
    if key is None:
        return None
    return key, top_lem, n, tot


_OPEN_WORD_RE = re.compile(r'form="([^"]+)"[^>]*lemma="([^"]+)"[^>]*postag="([^"]+)"')
_OPEN_CLOSED_PT = frozenset("lprcbgiexu")
USE_OPEN_CORPUS: bool = True


def _open_spell_norm(bare: str) -> str:
    """Safe Koine/Attic orthographic normalisation for open-corpus lookup: unassimilated nasals
    (νκ/νπ/νλ/συνσ), nasal-labial μψ/μφ/μπτ, Attic ττ/σσ and γιγν/γιν ONLY — never collapses
    doubled consonants (so νοσσοῖς never collides with νόσος) or ει/ι."""
    b = bare.replace("γιγν", "γιν").replace("ττ", "σσ")
    if "ν" in b:
        b = _NASAL_VELAR.sub("γ", b)
        b = _NASAL_LABIAL.sub("μ", b)
        b = b.replace("νλ", "λλ").replace("συνσ", "συσ")
    if "μ" in b:
        b = b.replace("μπτ", "πτ").replace("μφ", "φ").replace("μψ", "ψ")
    return b


@lru_cache(maxsize=1)
def _open_corpus_tables():
    """Lazy form -> (lemma, postag_prefix) tables over all open-licensed non-0527 GLAUx Greek
    texts (strictly CC BY-SA / CC BY / CC0 / public domain, with no NC/ND source or treebank
    annotations).  Built once only when a Swete textual variant is absent from LxxLemmas, TAGNT,
    lxx_table and 0527-* GLAUx."""
    from . import greek
    gdir = glaux_dir()
    meta_path = gdir / "metadata.txt"
    open_files: List[str] = []
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as fh:
            hdr = fh.readline().rstrip("\n").split("\t")
            for line in fh:
                row = dict(zip(hdr, line.rstrip("\n").split("\t")))
                tlg = row.get("TLG", "")
                if not tlg or tlg.startswith("0527-"):
                    continue
                if licence_ok(row.get("SOURCE_LICENSE", "")) and not _CLOSED_LICENCE.search(
                        row.get("TREEBANK_ANNOTATIONS", "")):
                    open_files.append(tlg)
    raw_counts: Dict[str, Counter] = defaultdict(Counter)
    for fid in open_files:
        fp = gdir / "xml" / f"{fid}.xml"
        if not fp.exists():
            continue
        data = fp.read_text(encoding="utf-8")
        for form, lem, pt in _OPEN_WORD_RE.findall(data):
            if len(form) < 3 or not lem or not pt or pt[0] == "u" or form[0].isupper():
                continue
            if lem[0].isupper() and greek_bare(lem) != "βορεασ":
                continue
            raw_counts[form][(lem, pt[:5])] += 1
    by_acc: Dict[str, Counter] = defaultdict(Counter)
    by_osp: Dict[str, Counter] = defaultdict(Counter)
    by_bare: Dict[str, Counter] = defaultdict(Counter)
    for form, cnts in raw_counts.items():
        ak = greek.accent_key(form)
        b = greek_bare(form)
        if not ak or len(b) < 3:
            continue
        osp = _open_spell_norm(b) if len(b) >= 6 else ""
        for (lem, pt5), n in cnts.items():
            lc = _nfc(re.sub(r"\d+$", "", lem).strip())
            if not lc:
                continue
            if lc[0].isupper() and greek_bare(lc) != "βορεασ":
                continue
            by_acc[ak][(lc, pt5)] += n
            by_bare[b][(lc, pt5)] += n
            if osp:
                by_osp[osp][(lc, pt5)] += n
    # Also fold open-licensed 0527-* Septuagint forms into by_bare for simplex compound lookup
    for (ak, is_cap), cnts in _glaux_form_table()[0].items():
        if is_cap:
            continue
        b = greek_bare(ak)
        if len(b) >= 4:
            for (lc, pt5), n in cnts.items():
                if lc and not lc[0].isupper():
                    by_bare[b][(lc, pt5)] += n
    return dict(by_acc), dict(by_osp), dict(by_bare)


def _open_corpus_lookup(surface: str, excl: Set[str]) -> Optional[Tuple[str, str, int, int, str]]:
    """Fallback lookup in the open-licensed non-0527 GLAUx Greek corpus (exact accent key, or
    safe nasal/Attic orthographic match for len >= 6).  Requires >= 95% single-lemma unanimity."""
    from . import greek
    bare = greek_bare(surface)
    if len(bare) < 3 or bare in _GLAUX_FORM_AMBIG_SHORT:
        return None
    is_cap = surface[:1].isupper()
    tagger = greek.get_tagger()
    if is_cap and tagger._has_propn_bare(bare):
        return None
    ak = greek.accent_key(surface)
    if not ak:
        return None
    by_acc, by_osp, _by_bare = _open_corpus_tables()
    c: Counter = Counter()
    for a_try in [ak] + greek._nu_twins(ak):
        hit = by_acc.get(a_try)
        if hit:
            c.update(hit)
    if not c and len(bare) >= 6 and not is_cap:
        osp = _open_spell_norm(bare)
        for sp_try in [osp] + [_open_spell_norm(nv) for nv in _nu_variants(bare)]:
            hit = by_osp.get(sp_try)
            if hit:
                c.update(hit)
    if not c:
        return None
    by_lem: Counter = Counter()
    best_pt: Dict[str, Tuple[int, str]] = {}
    for (lem, pt5), n in c.items():
        if is_cap and not pt5.startswith("v"):
            continue
        by_lem[lem] += n
        if lem not in best_pt or n > best_pt[lem][0]:
            best_pt[lem] = (n, pt5)
    if not by_lem:
        return None
    top_lem, n = by_lem.most_common(1)[0]
    tot = sum(by_lem.values())
    min_cnt = 5 if len(bare) <= 3 else (2 if len(bare) <= 4 else 1)
    min_share = 1.0 if len(bare) <= 3 else 0.95
    if n < min_cnt or (n / tot) < min_share:
        return None
    pt5 = best_pt[top_lem][1]
    fake_pick = Pick(("0", surface, bare, top_lem, pt5.ljust(9, "-"), False), "exact", True, (0, 0, ""))
    key = _resolve_glaux_lemma(fake_pick, surface, excl)
    if key is None:
        return None
    return key, top_lem, n, tot, f"GLAUx open corpus ({top_lem}, {n}/{tot})"


_SMOOTH_VOWEL_PVS = frozenset({
    "αντι", "αντ", "ανθ", "απο", "απ", "αφ", "ανα", "αν",
    "εισ", "εκ", "εξ", "εν", "εμ", "εγ", "ελ", "επι", "επ", "εφ", "ευ",
})


def _open_compound_lookup(surface: str, excl: Set[str]) -> Optional[Tuple[str, str]]:
    """Compositional preverb + open-GLAUx-attested simplex fallback: peels a standard Greek
    preverb, verifies the remainder against attested open-class forms in open-licensed GLAUx
    (0527-* + open non-0527), and accepts ONLY when the recomposed Greek compound headword
    already exists in TBESG, GWL, TFLSJ-extra, or Perseus LSJ."""
    from . import greek
    bare = greek_bare(surface)
    if len(bare) < 6:
        return None
    is_cap = surface[:1].isupper()
    tagger = greek.get_tagger()
    if is_cap and tagger._has_propn_bare(bare):
        return None
    has_rough = "̔" in unicodedata.normalize("NFD", surface.lower())[:4]
    _by_acc, _by_osp, by_bare = _open_corpus_tables()
    pv_fams = (
        ("αντι", ("αντι", "αντ", "ανθ")), ("απο", ("απο", "απ", "αφ")),
        ("ανα", ("ανα", "αν")), ("δια", ("δια", "δι")), ("εισ", ("εισ",)),
        ("εκ", ("εξ", "εκ")), ("εν", ("εν", "εμ", "εγ", "ελ")),
        ("επι", ("επι", "επ", "εφ")), ("κατα", ("κατα", "κατ", "καθ")),
        ("μετα", ("μετα", "μετ", "μεθ")), ("παρα", ("παρα", "παρ")),
        ("περι", ("περι",)), ("προσ", ("προσ",)), ("προ", ("προ",)),
        ("συν", ("συν", "συμ", "συγ", "συλ", "συσ", "συ")),
        ("υπερ", ("υπερ",)), ("υπο", ("υπο", "υπ", "υφ")), ("ευ", ("ευ",)),
    )
    head_pvs = {
        "αντι": ("αντι", "αντ", "ανθ"), "απο": ("απο", "απ", "αφ"),
        "ανα": ("ανα", "αν"), "δια": ("δια", "δι"), "εισ": ("εισ",),
        "εκ": ("εκ", "εξ"), "εν": ("εν", "εμ", "εγ", "ελ"),
        "επι": ("επι", "επ", "εφ"), "κατα": ("κατα", "κατ", "καθ"),
        "μετα": ("μετα", "μετ", "μεθ"), "παρα": ("παρα", "παρ"),
        "περι": ("περι",), "προσ": ("προσ",), "προ": ("προ",),
        "συν": ("συν", "συμ", "συγ", "συλ", "συσ", "συ"),
        "υπερ": ("υπερ",), "υπο": ("υπο", "υπ", "υφ"), "ευ": ("ευ",),
    }
    matches: Dict[str, str] = {}
    for canon_pv, forms in pv_fams:
        for fv in forms:
            if not bare.startswith(fv) or len(bare) < len(fv) + 4:
                continue
            if has_rough and fv in _SMOOTH_VOWEL_PVS:
                continue
            rem = bare[len(fv):]
            rem_tries: List[Tuple[str, bool]] = [(rem, is_cap)]
            for nv in _nu_variants(rem):
                rem_tries.append((nv, is_cap))
            if rem.startswith("ε") and len(rem) >= 5:
                for x in [rem[1:]] + _nu_variants(rem[1:]):
                    rem_tries.append((x, True))
            elif rem[:2] == "ηυ" and len(rem) >= 6:
                rem_tries.append(("ευ" + rem[2:], True))
                rem_tries.append(("αυ" + rem[2:], True))
            elif rem.startswith("η") and len(rem) >= 5:
                for v in ("α", "ε", "αι", "ει"):
                    for x in [v + rem[1:]] + _nu_variants(v + rem[1:]):
                        rem_tries.append((x, True))
            elif rem.startswith("ω") and len(rem) >= 5:
                for v in ("ο", "οι"):
                    rem_tries.append((v + rem[1:], True))
            if rem[0] not in "αεηιουω":
                for x in ["ε" + rem] + _nu_variants("ε" + rem):
                    rem_tries.append((x, True))
            sim_lem, sim_p0 = None, ""
            for sb, need_v in rem_tries:
                cnts = by_bare.get(sb)
                if not cnts:
                    continue
                by_l: Counter = Counter()
                pt_of: Dict[str, Tuple[int, str]] = {}
                for (lc, pt5), n in cnts.items():
                    if not pt5 or pt5[0] in _OPEN_CLOSED_PT:
                        continue
                    if need_v and pt5[0] != "v":
                        continue
                    by_l[lc] += n
                    if lc not in pt_of or n > pt_of[lc][0]:
                        pt_of[lc] = (n, pt5[0])
                if not by_l:
                    continue
                top_l, n = by_l.most_common(1)[0]
                tot = sum(by_l.values())
                if n / tot >= 0.90:
                    sim_lem, sim_p0 = top_l, pt_of[top_l][1]
                    break
            if not sim_lem:
                continue
            sim_b = greek_bare(sim_lem)
            sim_pos = _AGDT_POS_HINT.get(sim_p0)
            base_heads = [sim_b]
            if "γιγν" in sim_b:
                base_heads.append(sim_b.replace("γιγν", "γιν"))
            if "ττ" in sim_b:
                base_heads.append(sim_b.replace("ττ", "σσ"))
            alt_heads: List[str] = []
            for sh0 in base_heads:
                if sh0.endswith("ομαι"):
                    alt_heads.append(sh0[:-4] + "ω")
                elif sh0.endswith("ω"):
                    alt_heads.append(sh0[:-1] + "ομαι")
            for head_tier in (base_heads, alt_heads):
                tier_hits: Dict[str, str] = {}
                for hpv in head_pvs[canon_pv]:
                    for sh in head_tier:
                        cands = [hpv + sh]
                        if sh.startswith("ρ") and hpv[-1] in "αεηιουω":
                            cands.append(hpv + "ρ" + sh)
                        for ch_b in cands:
                            rk = tagger.lex.resolve_external_lemma(
                                ch_b, pos_hint=sim_pos, allow_propn=False, allow_lsj=True)
                            if rk and rk not in excl:
                                tier_hits[rk] = f"GLAUx open corpus compound ({canon_pv}+{sim_lem})"
                if tier_hits:
                    matches.update(tier_hits)
                    break
            break
    if len(matches) == 1:
        k, note = next(iter(matches.items()))
        return k, note
    return None


def fill_untagged_lemmas(book_slug: str, chapter: int, tagged: Dict[int, List[TokenTag]],
                         book_chapters: Dict[int, Dict[int, str]]) -> int:
    """Resolve remaining untagged Greek OT tokens (``lemma_key is None``) using the aligned
    GLAUx word's lemma when accents agree and the lemma maps uniquely to a Studio Greek lexicon
    entry, falling back to the open-licensed GLAUx Septuagint corpus form table (and, when
    ``USE_OPEN_CORPUS`` is enabled, the open-licensed non-0527 GLAUx Greek corpus) when a Swete
    reading has no aligned GLAUx word in that verse.  Acrostic letter names and context-excluded
    keys are never touched.  Intended to run before ``fill_chapter`` in concordance builds; leaves
    ``fill_chapter``'s own contract intact."""
    if book_slug not in BOOK_FILES or not corpus_available():
        return 0
    from . import greek
    tagger = greek.get_tagger()
    book = align_book(book_slug, book_chapters)
    filled = 0
    for vs, tags in tagged.items():
        if all(t.lemma_key is not None for t in tags):
            continue
        va = book.get((chapter, vs))
        if va is None:
            continue
        if [_nfc(x) for x in va.tokens] != [_nfc(t.surface) for t in tags]:
            continue
        excls = greek._context_exclusions([t.surface for t in tags])
        for t, pick, ex in zip(tags, va.picks, excls):
            if t.lemma_key is not None or "*" in ex or "acrostic letter name" in t.notes:
                continue
            if pick is not None:
                if not pick.accents_ok:
                    # Indeclinable / transliterated proper names never contrast by accent or breathing
                    # position (Γάβερ / Γαβέρ, Χανάαν / Χαναάν, Ἰεροσόλυμα / Ἱεροσόλυμα); also allow
                    # unambiguous Swete print breathing slips (ὄτι, οὗν, ἃν, νηί, δρύος, ὀδοὺς, κυρίᾳ, ἠχοῦς).
                    is_propn_pair = (t.surface[:1].isupper() and pick.word[W_FORM][:1].isupper()
                                     and pick.word[W_POSTAG].startswith("n") and len(greek_bare(t.surface)) >= 4)
                    is_swete_slip = (t.surface.lower() in _SWETE_LOWER_ACCENT_OK
                                     and (greek_bare(t.surface) == pick.word[W_BARE] or pick.kind == "spelling"))
                    if not (is_propn_pair or is_swete_slip):
                        continue
                key = _resolve_glaux_lemma(pick, t.surface, ex)
                if key is not None:
                    t.lemma_key = key
                    t.method = "glaux-aligned"
                    t.confidence = 0.90 if pick.manual else 0.85
                    t.is_content = tagger.is_content(key)
                    note = f"GLAUx lemma ({pick.lemma})"
                    if note not in t.notes:
                        t.notes.append(note)
                    if not pick.manual and NOTE_MACHINE not in t.notes:
                        t.notes.append(NOTE_MACHINE)
                    filled += 1
                    continue
            else:
                got = _glaux_corpus_form_lookup(t.surface, ex)
                if got is not None:
                    key, glem, n, tot = got
                    t.lemma_key = key
                    t.method = "glaux-form"
                    t.confidence = 0.82
                    t.is_content = tagger.is_content(key)
                    note = f"GLAUx corpus form table ({glem}, {n}/{tot})"
                    if note not in t.notes:
                        t.notes.append(note)
                    if NOTE_MACHINE not in t.notes:
                        t.notes.append(NOTE_MACHINE)
                    filled += 1
                    continue
                if USE_OPEN_CORPUS:
                    og = _open_corpus_lookup(t.surface, ex)
                    if og is not None:
                        key, _glem, _n, _tot, note = og
                        t.lemma_key = key
                        t.method = "glaux-form"
                        t.confidence = 0.80
                        t.is_content = tagger.is_content(key)
                        if note not in t.notes:
                            t.notes.append(note)
                        if NOTE_MACHINE not in t.notes:
                            t.notes.append(NOTE_MACHINE)
                        filled += 1
                        continue
                    oc = _open_compound_lookup(t.surface, ex)
                    if oc is not None:
                        key, note = oc
                        t.lemma_key = key
                        t.method = "glaux-form"
                        t.confidence = 0.80
                        t.is_content = tagger.is_content(key)
                        if note not in t.notes:
                            t.notes.append(note)
                        if NOTE_MACHINE not in t.notes:
                            t.notes.append(NOTE_MACHINE)
                        filled += 1
    return filled


def mapping_report(alignments: Dict[Tuple[int, int], VerseAlignment], offset: int = 0) -> Dict[str, object]:
    """How the Studio verses of one book map onto GLAUx verses: counts of verses whose best GLAUx
    verse has the same label, a shifted label (by verse / chapter) or was found by the book search,
    and the most common (studio chapter, glaux chapter) pairs where they differ."""
    c: Counter = Counter()
    shifts: Counter = Counter()
    for (ch, vs), va in alignments.items():
        if va.group is None:
            c["no-match"] += 1
            continue
        gch, gvs = va.group[0] - offset, va.group[1]
        if (gch, gvs) == (ch, vs):
            c["same-label"] += 1
        elif gch == ch:
            c["same-chapter-other-verse"] += 1
            shifts[(ch, gch, gvs - vs)] += 1
        else:
            c["other-chapter"] += 1
            shifts[(ch, gch, None)] += 1
    return {"counts": dict(c), "top_differences": shifts.most_common(12)}


# ---------------------------------------------------------------------------
# AGDT postag legend
# ---------------------------------------------------------------------------

_POS = {"n": "noun", "v": "verb", "a": "adjective", "d": "adverb", "l": "article", "g": "particle",
        "c": "conjunction", "b": "conjunction (coordinating)", "r": "preposition", "p": "pronoun",
        "m": "numeral", "i": "interjection", "e": "exclamation", "u": "punctuation",
        "x": "irregular", "z": "elliptic node"}
_PERSON = {"1": "1st person", "2": "2nd person", "3": "3rd person"}
_NUMBER = {"s": "singular", "p": "plural", "d": "dual"}
_TENSE = {"p": "present", "i": "imperfect", "r": "perfect", "l": "pluperfect", "t": "future perfect",
          "f": "future", "a": "aorist"}
_MOOD = {"i": "indicative", "s": "subjunctive", "o": "optative", "n": "infinitive", "m": "imperative",
         "p": "participle"}
_VOICE = {"a": "active", "p": "passive", "m": "middle", "e": "middle-passive"}
_GENDER = {"m": "masculine", "f": "feminine", "n": "neuter", "c": "common gender"}
_CASE = {"n": "nominative", "g": "genitive", "d": "dative", "a": "accusative", "v": "vocative",
         "l": "locative"}
_DEGREE = {"c": "comparative", "s": "superlative"}
_SLOTS = (_PERSON, _NUMBER, _TENSE, _MOOD, _VOICE, _GENDER, _CASE, _DEGREE)


def describe_postag(postag: str) -> Optional[str]:
    """'v3saia---' -> 'verb, 3rd person, singular, aorist, indicative, active'; None if a
    position holds a value the AGDT scheme does not define."""
    tag = postag[len(MORPH_SCHEME) + 1:] if postag.startswith(MORPH_SCHEME + ":") else postag
    if len(tag) != 9 or tag[0] not in _POS:
        return None
    parts = [_POS[tag[0]]]
    for ch, table in zip(tag[1:], _SLOTS):
        if ch == "-":
            continue
        if ch not in table:
            return None
        parts.append(table[ch])
    return ", ".join(parts)


def used_postags() -> Set[str]:
    """Every postag of the GLAUx words of the books in BOOK_FILES whose licence is open."""
    out: Set[str] = set()
    for file_id in sorted({v[0] for v in BOOK_FILES.values()}):
        if not _file_allowed(file_id):
            continue
        for g in load_file(file_id):
            out.update(w[W_POSTAG] for w in g.words)
    return out


def morph_legend(codes: Optional[Iterable[str]] = None) -> Dict[str, str]:
    """English description of GLAUx parse codes keyed as ``TokenTag.morph`` ('A:v3saia---').
    ``codes`` with or without the 'A:' prefix; None = every postag of the mapped GLAUx files.
    A code the AGDT scheme cannot describe is left out (``set(codes) - set(result)``)."""
    if codes is None:
        codes = used_postags()
    out: Dict[str, str] = {}
    for code in codes:
        if not code:
            continue
        bare = code[len(MORPH_SCHEME) + 1:] if code.startswith(MORPH_SCHEME + ":") else code
        d = describe_postag(bare)
        if d is not None:
            out[f"{MORPH_SCHEME}:{bare}"] = d
    return dict(sorted(out.items()))
