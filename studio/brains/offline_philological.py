"""100% Offline Philological Gatekeeper & Reasoned-Eclectic Text-Critical Brain.

Works completely air-gapped with zero internet and zero external dependencies.

Adjudication rules (deterministic, so every decision can be reproduced and audited):

1. Witnesses vote with their weights; digital copies of one printed edition (an "edition
   family") count once, at the highest weight in the family.
2. Orthographic differences never change the wording; they are logged as "disregarded surface
   noise" with the reason, and spelling/punctuation come from the language's orthographic base
   edition whenever it attests the adopted reading.
3. A whole verse that some extant witnesses lack (CNTR "-") or that an edition brackets as a
   later addition (SBLGNT ⟦ ⟧) gets a verse-level apparatus entry. If the weight of the witnesses
   lacking it is greater, the verse is printed inside ⟦ ⟧ rather than silently dropped.
4. Lectio brevior: in Greek and Latin, an omission supported by a witness of weight ≥ 0.96
   (Vaticanus, Sinaiticus, Amiatinus) receives a +0.12 bonus.
5. A word repeated by a single witness family against the rest is logged as dittography.
"""

from __future__ import annotations
import math
import re
import unicodedata
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from ..collator import (
    IOTA_SUBSCRIPT_NOTE,
    NOMINA_SACRA_STEMS,
    CollatedVerse,
    VariationSlot,
    canonical_compare_key,
    capitalize_first,
    is_letter_numeral,
    is_nomen_sacrum,
    is_orthographic_equivalence,
    join_words,
    normalize_critical_token,
    split_words,
    strip_punct,
    tokenize_for_alignment,
)
from ..catalog import independent_digitisations, stream_of
from ..lexicon import edit_distance
from ..parsers import DOUBTFUL_CLOSE, DOUBTFUL_OPEN
from .base import (
    ApparatusItem,
    CriticalBrainProvider,
    DisregardedItem,
    GatekeeperVerdict,
    VerseAdjudication,
)

LECTIO_BREVIOR_BONUS = 0.12
LECTIO_BREVIOR_MIN_WEIGHT = 0.96
# The base edition only breaks ties between equally supported spellings; its capitalisation and
# punctuation are used whenever it has the winning spelling (see _choose_best_surface_form).
ORTHOGRAPHIC_BASE_TIEBREAK = 0.5
IMPOSSIBLE_FORM_PENALTY = 3.0


def _inner_capital(raw: str) -> bool:
    """True if any word has a capital after its first letter while not being all caps (OCR damage,
    e.g. ἸάΦεθ). Checked word by word, so "ἐγέννησεν δὲ Νῶε" is not affected."""
    for word in raw.split():
        letters = [c for c in strip_punct(word) if c.isalpha()]
        if len(letters) > 1 and not all(c.isupper() for c in letters) and any(c.isupper() for c in letters[1:]):
            return True
    return False


def _shape_key(raw: str) -> str:
    """A form's letters, accents and breathings, ignoring capitalisation, punctuation and the
    positional grave/acute alternation on a single-accented oxytonic word's final vowel."""
    parts: List[str] = []
    for tok in raw.split():
        nfd = unicodedata.normalize("NFD", strip_punct(tok).lower())
        acc_pos = [i for i, c in enumerate(nfd) if c in ("\u0300", "\u0301", "\u0342")]
        if len(acc_pos) == 1 and nfd[acc_pos[0]] == "\u0300" and not any(c in "αεηιουω" for c in nfd[acc_pos[0] + 1:]):
            nfd = nfd[:acc_pos[0]] + "\u0301" + nfd[acc_pos[0] + 1:]
        parts.append(unicodedata.normalize("NFC", nfd).replace("ς", "σ"))
    return " ".join(parts)

# Explicit restrictive licences: always quarantine.
RESTRICTED_LICENSE_PATTERNS = [
    (r"\bby-nc(?:-sa|-nd)?\b|\bcc[\s\-]*by[\s\-]*nc\b", "Creative Commons NonCommercial (CC BY-NC*)"),
    (r"\bnon-?commercial\b", "NonCommercial restriction"),
    (r"\bno-?derivatives\b|\bby-nd\b|\bnoderivs\b", "NoDerivatives restriction (prohibits critical adaptation)"),
]
# Publisher / copyright mentions: quarantine only when no explicit open licence is stated
# (a CC BY-SA transcription may cite the Stuttgart Vulgate or say "All rights reserved. Released
# under CC BY-SA 4.0", as the CNTR files do).
PROTECTED_EDITION_PATTERNS = [
    (r"all rights reserved", "All Rights Reserved copyright notice"),
    (r"deutsche bibelgesellschaft", "Protected Deutsche Bibelgesellschaft edition (e.g., NA28/UBS5/Rahlfs-Hanhart/Stuttgart)"),
    (r"novum testamentum graece\s*2[678]", "Copyrighted Nestle-Aland edition"),
    (r"weber[\-–]gryson", "Copyrighted Stuttgart Vulgate apparatus/text"),
    (r"libreria editrice vaticana", "Copyrighted Nova Vulgata imprint"),
]

OPEN_LICENSE_PATTERNS = [
    (r"public domain|\bcc0\b|unlicense", "Public Domain / CC0"),
    (r"cc[\s\-]*by[\s\-]*sa[\s\-]*(?:3\.0|4\.0)|attribution[\s\-]*sharealike|licen[cs]es/by-sa/", "CC BY-SA"),
    (r"cc[\s\-]*by[\s\-]*(?:3\.0|4\.0)|licen[cs]es/by/", "CC BY"),
    (r"\bmit license\b|\bapache license\b", "Permissive Open Source (MIT/Apache)"),
]


def _script_ratio(text: str, language: str) -> Tuple[float, float, int]:
    """Return (expected_script_ratio, replacement_char_ratio, glued_token_count)."""
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0, 0.0, 0
    repl_count = text.count("�")
    lang = language.lower()
    good = 0
    for ch in letters:
        cp = ord(ch)
        if lang == "greek" and ((0x0370 <= cp <= 0x03FF) or (0x1F00 <= cp <= 0x1FFF)):
            good += 1
        elif lang == "hebrew" and (0x0590 <= cp <= 0x05FF or 0xFB1D <= cp <= 0xFB4F):
            good += 1
        elif lang == "latin" and (cp < 0x0250):
            good += 1

    plain = re.sub(r"<[^>]+>", " ", text)  # XML markup is not glued words
    glued = 0
    for tok in plain.split():
        if len(tok) > 38 and "http" not in tok:
            glued += 1
        elif lang == "hebrew" and "/" in tok and any(0x0590 <= ord(c) <= 0x05FF for c in tok):
            glued += 1
    return good / max(1, len(letters)), repl_count / max(1, len(text)), glued


def _edition_family(siglum: str) -> str:
    """Fallback grouping by siglum when the engine did not supply witness families."""
    s = siglum.lower()
    if "swete" in s or "1st1k" in s:
        return "swete_uncial_edition"
    if "clem" in s:
        return "sixto_clementine_edition"
    if "wlc" in s or "leningrad" in s:
        return "leningrad_codex"
    return siglum


def _family_weighted_sum(sigla: List[str], weights: Dict[str, float], families: Optional[Dict[str, str]] = None) -> float:
    by_fam: Dict[str, float] = {}
    for s in sigla:
        fam = (families or {}).get(s) or _edition_family(s)
        by_fam[fam] = max(by_fam.get(fam, 0.0), weights.get(s, 0.5))
    return sum(by_fam.values())


def _family_count(sigla: List[str], families: Optional[Dict[str, str]] = None) -> int:
    return len({(families or {}).get(s) or _edition_family(s) for s in sigla})


# Connectives and prepositions that Greek never writes twice in a row: a doubling found in one
# edition family is always a copying/OCR slip, however often stray doublings occur elsewhere.
NEVER_DOUBLED_GREEK = {"και", "δε", "γαρ", "ουν", "τε", "εν", "εισ", "εκ", "εξ", "απο", "προσ", "επι", "μετα", "κατα", "δια", "υπο", "περι"}

_ENCLITIC_PRONOUNS = {"σου", "μου", "σοι", "μοι", "με", "σε", "αυτου", "αυτω", "αυτον", "αυτησ", "αυτη", "αυτην",
                      "αυτων", "αυτοισ", "αυτουσ", "ημων", "υμων", "ημιν", "υμιν", "ημασ", "υμασ"}

# Words that open a clause: punctuation in front of them stays in front of them.
_CLAUSE_INITIAL = {
    "και", "η", "ο", "οι", "αι", "το", "τα", "τον", "την", "του", "τησ", "τω", "τη", "των", "τοισ", "ταισ",
    "τουσ", "τασ", "αλλα", "αλλ", "ουτε", "μητε", "ινα", "οτι", "ωσ", "ει", "εαν", "ουδε", "μηδε", "πωσ", "τισ",
    "τι", "ιδου", "ιδε", "ουχι", "ουκ", "ου", "μη", "ποτε", "που", "οταν", "καθωσ", "ωστε", "διο", "διοτι", "αμην",
    "et", "sed", "aut", "vel", "ut", "quia", "si", "nec", "neque", "atque", "ac", "quod", "cum", "ecce", "quomodo",
}

KNOWN_LEIPZIG_OCR_TYPOS = {
    "συστεματα": "συστηματα",
    "κορπιμον": "καρπιμον",
    "πατησ": "πασησ",
}


def _greek_token_defect_penalty(raw_tok: str) -> Tuple[float, str]:
    """Detect OCR typos, missing initial breathings, or impossible rough breathings on ἐξ-."""
    clean = strip_punct(raw_tok)
    if not clean or is_nomen_sacrum(clean) or is_letter_numeral(clean):
        return 0.0, ""
    if re.search(r"[A-Za-z0-9]", clean):
        return IMPOSSIBLE_FORM_PENALTY, "Latin letter or digit inside a Greek word (OCR defect, e.g. ’lσραὴλ)"
    nfd = unicodedata.normalize("NFD", clean)
    first_base = nfd[0].lower()
    has_any_mark = any(unicodedata.category(c) == "Mn" for c in nfd)
    if first_base in "αεηιουω" and not clean.isupper() and len(clean) > 1 and has_any_mark:
        marks = []
        for ch in nfd[1:]:
            if unicodedata.category(ch) == "Mn":
                marks.append(ord(ch))
            else:
                break
        # An accented edition always writes a breathing on an initial vowel (diphthongs carry it
        # on the second letter, so only flag when the word is not a diphthong-initial one).
        if 0x0313 not in marks and 0x0314 not in marks and not re.match(r"^(?:αι|ει|οι|υι|αυ|ευ|ου|ηυ)", strip_diacritics_lower(clean)):
            return IMPOSSIBLE_FORM_PENALTY, "Missing Greek breathing mark on initial vowel (OCR defect)"
        # The preposition/prefix ἐξ- never has a rough breathing; ἕξ/ἑξήκοντα/ἑξακόσιοι/ἑξῆς do, and
        # so do the future of ἔχω (ἕξω, ἕξει, ἕξουσιν…) and ἕξις.
        low = strip_diacritics_lower(clean).replace("ς", "σ")
        if 0x0314 in marks and low.startswith("εξ"):
            if not low.startswith(("εξη", "εξακ", "εξαμ")) and low not in _ROUGH_EX_OK:
                return IMPOSSIBLE_FORM_PENALTY, "Spurious rough breathing on ἐξ- prefix (OCR defect)"
    if strip_diacritics_lower(clean) == "καθ" and any(unicodedata.category(c) == "Mn" for c in nfd[2:]):
        # κἀθ᾽ (crasis-looking breathing on the alpha) is an OCR misreading of καθ᾽
        return IMPOSSIBLE_FORM_PENALTY, "Spurious crasis breathing on καθ’ (OCR defect)"
    if not re.search(r"[’'ʼ᾽-]$", raw_tok.strip()):
        reason = _greek_accent_defect(clean)
        if reason:
            return IMPOSSIBLE_FORM_PENALTY, reason
    return 0.0, ""


# ---------------------------------------------------------------------------
# Greek accentuation validity (catches OCR damage that still looks like Greek)
# ---------------------------------------------------------------------------
_GR_VOWELS = set("αεηιουω")
_GR_DIPHTHONGS = {"αι", "ει", "οι", "υι", "αυ", "ευ", "ου", "ηυ", "ωυ"}
_ACUTE, _GRAVE, _CIRC, _SMOOTH, _ROUGH, _DIAER, _YPOG = "\u0301", "\u0300", "\u0342", "\u0313", "\u0314", "\u0308", "\u0345"
_ACCENTS = {_ACUTE, _GRAVE, _CIRC}
# Enclitics and proclitics that are normally written without an accent.
_UNACCENTED_OK = {
    "ο", "η", "οι", "αι", "εν", "εισ", "εσ", "εκ", "εξ", "ου", "ουκ", "ουχ", "ωσ", "ει",
    "μου", "μοι", "με", "σου", "σοι", "σε", "του", "τω", "τινοσ", "τινι", "τινα", "τινεσ", "τινων", "τισι", "τισιν",
    "τινασ", "τισ", "τι", "εστι", "εστιν", "εισι", "εισιν", "εσμεν", "εστε", "φημι", "φησι", "φησιν", "φαμεν",
    "φατε", "φασι", "φασιν", "που", "ποι", "πη", "πωσ", "ποτε", "ποθεν", "περ", "γε", "τε", "τοι", "νυν", "θην",
    "ειμι", "εισ",
}
_ROUGH_EX_OK = {"εξ", "εξω", "εξεισ", "εξει", "εξομεν", "εξετε", "εξουσι", "εξουσιν", "εξειν", "εξεσθαι",
                "εξισ", "εξιν", "εξεωσ", "εξει"}


def _letter_segments(clean: str) -> List[List[Any]]:
    segs: List[List[Any]] = []
    for ch in unicodedata.normalize("NFD", clean):
        if unicodedata.category(ch) == "Mn":
            if segs:
                segs[-1][1].append(ch)
        else:
            segs.append([ch, []])
    return segs


def _greek_accent_defect(clean: str) -> str:
    """Return why an accented Greek word is impossible (OCR damage), or "" if it is well formed.

    Checks: accent or breathing on a consonant (ῥ excepted); iota subscript under ε/ι/ο/υ;
    circumflex on ε/ο; two accents on one vowel; breathing anywhere but the first vowel (initial
    diphthongs, ῤῥ and crasis after κ/τ/χ/θ excepted); grave not on the final syllable; accent
    before the antepenult; three accents, or two unless the second is an enclitic acute on the final
    syllable; and no accent at all on a word of two or more syllables that is not a clitic."""
    if not clean or clean.isupper() or is_nomen_sacrum(clean) or is_letter_numeral(clean):
        return ""
    segs = _letter_segments(clean)
    letters = [s[0].lower() for s in segs]
    if not any(l in _GR_VOWELS for l in letters) or not all(("Ͱ" <= l <= "Ͽ") or ("ἀ" <= l <= "῿") for l in letters):
        return ""
    if not any(m for _l, marks in segs for m in marks):
        return ""  # unaccented manuscript transcription: nothing to check
    nuclei: List[Tuple[int, int]] = []
    i = 0
    while i < len(segs):
        if letters[i] in _GR_VOWELS:
            if i + 1 < len(segs) and letters[i] + letters[i + 1] in _GR_DIPHTHONGS and _DIAER not in segs[i + 1][1]:
                nuclei.append((i, i + 1))
                i += 2
                continue
            nuclei.append((i, i))
        i += 1
    for idx, (raw_letter, marks) in enumerate(segs):
        letter = raw_letter.lower()
        ms = set(marks)
        if letter not in _GR_VOWELS:
            if (ms & _ACCENTS) or ((ms & {_SMOOTH, _ROUGH}) and letter != "ρ"):
                return "Accent or breathing on a consonant (OCR defect)"
            continue
        if _YPOG in ms and letter not in "αηω":
            return "Iota subscript under ε, ι, ο or υ (OCR defect)"
        if _CIRC in ms and letter in "εο":
            return "Circumflex on a short vowel ε/ο (OCR defect)"
        if len(ms & _ACCENTS) > 1:
            return "Two accents on one vowel (OCR defect)"
    first_vowel = next((n for n in nuclei), None)
    crasis = len(letters) > 1 and letters[0] in "κτχθ" and first_vowel is not None and first_vowel[0] == 1
    for idx, (raw_letter, marks) in enumerate(segs):
        letter = raw_letter.lower()
        if not ({_SMOOTH, _ROUGH} & set(marks)) or letter == "ρ":
            continue
        allowed = first_vowel is not None and idx in (first_vowel[0], first_vowel[1]) and (first_vowel[0] == 0 or crasis)
        if not allowed:
            return "Breathing on a non-initial letter (OCR defect)"
    accented = [n_i for n_i, (a, b) in enumerate(nuclei) if (set(segs[a][1]) | set(segs[b][1])) & _ACCENTS]
    n_syll = len(nuclei)
    if not accented:
        key = strip_diacritics_lower(clean).replace("ς", "σ")
        if n_syll >= 2 and key not in _UNACCENTED_OK:
            return "No accent on a word of two or more syllables (OCR defect)"
        return ""
    if len(accented) >= 3:
        return "Three accents on one word (OCR defect)"
    if len(accented) == 2:
        last = nuclei[accented[1]]
        if accented[1] != n_syll - 1 or _ACUTE not in (set(segs[last[0]][1]) | set(segs[last[1]][1])):
            return "Two accents that no enclitic can explain (OCR defect)"
    for n_i in accented:
        a, b = nuclei[n_i]
        marks = set(segs[a][1]) | set(segs[b][1])
        if _GRAVE in marks and n_i != n_syll - 1:
            return "Grave accent not on the final syllable (OCR defect)"
    if accented[0] < n_syll - 3:
        return "Accent before the antepenult (OCR defect)"
    if n_syll >= 2 and accented[0] == n_syll - 2:
        pa, pb = nuclei[-2]
        ua, ub = nuclei[-1]
        if _CIRC in (set(segs[pa][1]) | set(segs[pb][1])):
            u_str = letters[ua] if ua == ub else letters[ua] + letters[ub]
            u_marks = set(segs[ua][1]) | set(segs[ub][1])
            if u_str in ("η", "ω", "ου", "ει", "υι", "ηυ", "ωυ") or _YPOG in u_marks:
                return "Circumflex on penult before a naturally long ultima (OCR defect)"
    return ""


DIPLOMATIC_MSS = {"א (01)", "B (03)"}
_DOUBLED = re.compile(r"(.)\1")
# Letter pairs the Swete OCR confuses (o/α, ρ/π, υ/ν …); a change between them inside a word is a misreading.
_OCR_CONFUSABLE = {frozenset(p) for p in ("οα", "ρπ", "νυ", "τγ", "θο", "ηπ", "ιτ", "λα", "κχ", "ετ", "σο", "ωα", "μν", "ρε", "σα",
                                           "γπ", "γλ")}  # γπ: capital Γ / Π (Γαντοκράτωρ); γλ: ἄλλελον for ἄγγελον
_GREEK_PREFIXES = ("προσ", "προ", "εκ", "εξ", "εν", "εμ", "εγ", "δια", "συν", "συμ", "συγ", "επι", "απο", "αντι", "κατα",
                   "μετα", "παρα", "περι", "υπερ", "υπο", "ανα")


def _plain_greek(word: str) -> str:
    """Lower-case, accents and breathings dropped, iota subscript kept (τῇ → τῃ, Ἐν → εν)."""
    nfd = unicodedata.normalize("NFD", strip_punct(word).lower())
    return unicodedata.normalize("NFC", "".join(c for c in nfd if c not in "\u0300\u0301\u0342\u0313\u0314"))


# After these words a noun or adjective must be dative, so a following word that differs from the
# other edition only by a lost iota subscript (ἐν τῆ γῆ, τῇ ἡμέρα τῇ ἕκτη) is an OCR slip, whatever
# the word counts say (ἡμέρα and ἕκτη are common nominatives).
_DATIVE_GOVERNORS = frozenset(_plain_greek(w) for w in ("ἐν", "σύν", "τῇ", "τῷ"))


# Swete's υ-for-ν OCR signature can make another common form (οἶκου for οἶκον), which the counts
# cannot catch; right after the accusative article τόν / neuter τό a genitive noun is ungrammatical
# (1 Kgs 16:11 'τὸν οἶκου', 1 Kgs 7:45 'τὸ ἔργου'). Genitive pronouns and articles are excepted
# (τὸν αὐτοῦ οἶκον, τὸ τοῦ κυρίου).
_ACCUSATIVE_ARTICLES = frozenset(_plain_greek(w) for w in ("τόν", "τό"))
_GENITIVE_PRONOUNS = frozenset(
    canonical_compare_key(w, "greek") for w in (
        "τοῦ", "αὐτοῦ", "ἑαυτοῦ", "σεαυτοῦ", "ἐμαυτοῦ", "τούτου", "ἐκείνου", "ἐμοῦ", "σοῦ", "μου", "σου", "οὗ",
        "τινός", "ἑτέρου", "ἄλλου", "παντός", "ὅλου"))


def _article_agreement_slip(x: str, y: str, prev: str) -> str:
    """x (key) is Swete's υ-for-ν slip of y right after an accusative article, where only y is grammatical."""
    if not prev or _plain_greek(prev) not in _ACCUSATIVE_ARTICLES or x in _GENITIVE_PRONOUNS:
        return ""
    if len(x) > 3 and x.endswith("ου") and y == x[:-2] + "ον":
        return f"'{x}' for '{y}' (OCR υ for ν: after '{prev}' a genitive is ungrammatical)"
    return ""


def _lost_subscripts(a_words: List[str], b_words: List[str]) -> List[Tuple[int, str, str]]:
    """Positions where reading A lacks an iota subscript that reading B has, when that is the only
    difference between them (accent and capital differences aside). Empty if anything else differs
    or if A has a subscript B lacks (OCR loses subscripts; it does not add them)."""
    if len(a_words) != len(b_words):
        return []
    lost = []
    for i, (wa, wb) in enumerate(zip(a_words, b_words)):
        ca, cb = strip_punct(wa), strip_punct(wb)
        if ca == cb:
            continue
        if canonical_compare_key(ca, "greek") != canonical_compare_key(cb, "greek"):
            return []
        na = unicodedata.normalize("NFD", ca).count("\u0345")
        nb = unicodedata.normalize("NFD", cb).count("\u0345")
        if na > nb:
            return []
        if nb > na:
            lost.append((i, wa, wb))
    return lost


# Nouns Brenton capitalises out of reverence where Swete prints them in lower case. Only these are
# lowered when a word is repaired from Brenton: Swete's OCR often reads a capital Χ, Ο or Ι as a
# small letter, so its lower case says nothing about names.
_REVERENTIAL_CAPITALS = frozenset(
    canonical_compare_key(w, "greek") for w in (
        "θεός", "θεοῦ", "θεῷ", "θεόν", "θεέ", "θεοί", "θεῶν", "θεοῖς", "θεούς",
        "κύριος", "κυρίου", "κυρίῳ", "κύριον", "κύριε", "δεσπότης", "δεσπότου", "δεσπότῃ", "δεσπότην", "δέσποτα"))


_THEOS_FORMS = frozenset(canonical_compare_key(w, "greek") for w in
                         ("θεός", "θεοῦ", "θεῷ", "θεόν", "θεέ", "θεοί", "θεῶν", "θεοῖς", "θεούς"))
_ARTICLES = frozenset(canonical_compare_key(w, "greek") for w in
                      ("ὁ", "τοῦ", "τῷ", "τόν", "ὦ", "οἱ", "τῶν", "τοῖς", "τούς", "τό", "ἡ", "τῆς", "τῇ", "τήν"))


def _has_accent_marks(form: str) -> bool:
    """An accented or breathed spelling (not a bare transcription; a nomen-sacrum overline does not count)."""
    return any(c in "\u0300\u0301\u0342\u0313\u0314" for c in unicodedata.normalize("NFD", form))


def _spelt(word: str) -> str:
    """A word as spelt: lower case, breathings, circumflex and subscript kept, acute = grave (so
    'σπέρμα,' = 'σπέρμα' and καὶ = καί, but οὗ ≠ οὐ)."""
    nfd = unicodedata.normalize("NFD", strip_punct(word).lower())
    return unicodedata.normalize("NFC", "".join(c for c in nfd if c not in "\u0300\u0301"))


def _no_subscript_key(word: str) -> str:
    """The comparison key with iota subscripts ignored (κᾀγὼ = κἀγὼ)."""
    nfd = unicodedata.normalize("NFD", strip_punct(word))
    return canonical_compare_key(unicodedata.normalize("NFC", nfd.replace("\u0345", "")), "greek")


_SUBJUNCTIVE_MARKERS = frozenset(_plain_greek(w) for w in ("ἵνα", "ἐάν", "ὅταν", "ἄν", "ὅπως"))


def _final_accent(word: str) -> str:
    """The accent on the word's last vowel: '/' acute or grave, '~' circumflex, '' none."""
    for ch in reversed(unicodedata.normalize("NFD", strip_punct(word))):
        if ch in "\u0301\u0300":
            return "/"
        if ch == "\u0342":
            return "~"
        if unicodedata.category(ch) != "Mn" and ch.lower() in "αεηιουω":
            return ""
    return ""


def _b_doubled_consonant(x: str, y: str) -> bool:
    """x (the damaged edition's key) has a doubled consonant inside the word where y has a single one
    (παρενέβαλλον / παρενέβαλον): a spelling of B, not OCR. A doubled vowel or a doubled final letter
    (πάτεερ, πόλεμονν, στέφανοο) is an OCR stutter and is not protected; nor is a consonant y doubles."""
    if len(x) != len(y) + 1:
        return False
    for k in range(len(x) - 2):  # never the last pair: Greek words do not end in a doubled letter
        if x[k] == x[k + 1] and x[k] in "λρνμπτκσγ" and x[:k] + x[k + 1:] == y:
            return True
    return False


def _is_name_form(word: str) -> bool:
    """Capitalised and not one of Brenton's reverential capitals (θεός, κύριος), so treated as a name."""
    return bool(word[:1].isupper()) and canonical_compare_key(word, "greek") not in _REVERENTIAL_CAPITALS


def _same_but_subscript(word_a: str, word_b: str) -> bool:
    """The two spellings are identical apart from the iota subscript (accents and breathings included)."""
    def strip(w: str) -> str:
        return unicodedata.normalize("NFC", unicodedata.normalize("NFD", strip_punct(w)).replace("\u0345", ""))
    a, b = strip(word_a), strip(word_b)
    if a != b and _final_accent(word_b) == "":
        # a stray acute/grave the OCR put on the last vowel ('\u1f38\u03bf\u03c5\u03b4\u03b1\u03af\u1f70') is not another form
        nfd = unicodedata.normalize("NFD", a)
        k = max(i for i, c in enumerate(nfd) if unicodedata.category(c) != "Mn")
        a = unicodedata.normalize("NFC", nfd[:k + 1] + "".join(c for c in nfd[k + 1:] if c not in "\u0300\u0301"))
    return a == b


def _other_form_not_lost_subscript(word_a: str, word_b: str) -> bool:
    """The other edition's subscripted form is a different spelling, not this word with its subscript
    lost: a capitalised name whose accent changes (Φαραώ / Φαραῷ, indeclinable in B), or acute plus
    subscript on the last syllable, which no Greek dative has (Brenton's Φαραῴ, Μανασσῄ)."""
    b = strip_punct(word_b)
    if _is_name_form(b) and not _same_but_subscript(word_a, word_b):
        return True  # Φαραώ / Φαραῷ, Λοῦζα / Λουζᾷ, Ἀβιὰ / Ἀβίᾳ: Brenton declines what B leaves undeclined
    return _final_accent(word_b) == "/" and "\u0345" in unicodedata.normalize("NFD", b)[-3:]


def _subscript_needed(prev_raw: str, word_b: str, word_a: str = "", context: Any = (), lex: Any = None) -> str:
    """Why the word after ``prev_raw`` (the raw token, punctuation included) must carry the iota
    subscript the other edition prints, or ''. A capitalised name is refused when the accent changes
    type (Φαραώ → Φαραῷ, Θερσά, Ῥαμά: indeclinable in B), not when only the subscript is missing
    (Ῥεβέκκα → Ῥεβέκκᾳ, Ἰουδαία → Ἰουδαίᾳ, Μωυσῆ → Μωυσῇ after τῷ). Agreement only with an adjacent
    dative of the same ending (ὅλῃ γῆ → γῇ; ᾗ ἡμέρα → ἡμέρᾳ; not τῇ θύρᾳ τῆς, not βαλλαντίῳ,
    ἐπεσημήνω, not across punctuation). A subjunctive after ἐάν / ἄν / ἵνα / ὅταν / ὅπως anywhere
    earlier in the clause (``context``: the preceding raw tokens, oldest first)."""
    if not prev_raw:
        return ""
    if _is_name_form(strip_punct(word_b)) and (not word_a or not _same_but_subscript(word_a, word_b)):
        return ""  # a name that differs in more than its subscript is another (indeclinable) form
    nfd_b = unicodedata.normalize("NFD", strip_punct(word_b))
    if _final_accent(word_b) == "/" and "\u0345" in nfd_b[-3:]:
        return ""  # acute + subscript on the last syllable is no Greek dative (Brenton's Φαραῴ, Μανασσῄ)
    if not any(c in "\u0300\u0301\u0342" for c in nfd_b):
        return ""  # an unaccented form is the other edition's typo, not a word (Exod 33:22 'ᾑ')
    p, b = _plain_greek(prev_raw), _plain_greek(word_b)
    if p in _DATIVE_GOVERNORS:
        return f"after '{strip_punct(prev_raw)}' only the dative is grammatical"
    if re.search(r"[,.;·:!?’”]$", prev_raw.strip()):
        return ""  # a clause break: no agreement across it
    if p and b and p[-1] in "ᾳῃῳ" and (b[-1] == p[-1] or {p[-1], b[-1]} == {"ᾳ", "ῃ"}):
        return f"it agrees with the dative '{strip_punct(prev_raw)}'"
    if b.endswith(("ῃ", "ῃς")) and not strip_punct(word_b)[:1].isupper():  # not -ῷ: μνησθῶ is a 1st person
        for tok in reversed(list(context) + [prev_raw]):
            if _plain_greek(tok) in _SUBJUNCTIVE_MARKERS:
                return f"after '{strip_punct(tok)}' the subjunctive is expected"
            if re.search(r"[.;·:!?]$", tok.strip()):
                break  # the clause ends here
    return ""


def _broken_token(raw: str) -> bool:
    """A token no edition prints as a word: punctuation between its letters (σ,ήσω, δό,τα), a slash
    or the '(??)' doubt mark inside it (εἶ(??)εν, ὑμῶν./)."""
    if re.search(r"\w[,.;·:/()?]+\w", raw) or "/" in raw or "(??)" in raw:
        return True
    # A rough breathing inside a word (ὅσαἑ, μπἑπαιχα): Greek marks it only on an initial vowel or
    # the second letter of an initial diphthong (οἱ, εὑ); ῥ / ῤῥ are consonants and are left alone.
    pos = -1
    for ch in unicodedata.normalize("NFD", strip_punct(raw).lower()):
        if unicodedata.category(ch) != "Mn":
            pos += 1
            base = ch
        elif ch == "\u0314" and pos >= 2 and base in "αεηιουω":
            return True
    return False


def _prefix_change(x: str, y: str) -> bool:
    """x and y differ by a preverb added, dropped or exchanged, nested ones included (προέθηκεν /
    προσέθηκεν, ἐκθλίβοντες / θλίβοντες, ἐνκατέλειπον / ἐγκατέλιπον, ἐξεγέννησα / ἐγέννησα)."""
    px = [p for p in _GREEK_PREFIXES if x.startswith(p)] + [""]
    py = [p for p in _GREEK_PREFIXES if y.startswith(p)] + [""]
    for p in px:
        for q in py:
            if p == q:
                continue
            a, b = x[len(p):], y[len(q):]
            if a == b or (min(len(a), len(b)) > 3 and edit_distance(a, b, limit=2) <= 1):
                return True
    return False


def _article_run_in(raw: str, y_key: str) -> bool:
    """The token is an article with its rough breathing run into the next word (ὁθεός = ὁ θεός)."""
    nfd = unicodedata.normalize("NFD", strip_punct(raw).lower())
    if len(nfd) < 3 or nfd[0] not in "οη" or nfd[1] != "\u0314":
        return False
    rest = nfd[2:].lstrip("\u0300\u0301\u0342")
    if rest[:1] in "αεηιουω" and any(c in "\u0313\u0314" for c in rest[1:3]):
        return False  # 'ὁὡς': the next word's own breathing doubled by the OCR, not an article
    return canonical_compare_key(strip_punct(raw), "greek")[1:] == y_key


def _ei_i_spelling(x: str, y: str) -> bool:
    """x and y differ by an ει written for ι (or the reverse), apart from one confusable letter."""
    longer, shorter = (x, y) if len(x) > len(y) else (y, x)
    for k in range(len(longer) - 1):
        if longer[k:k + 2] == "ει":
            cut = longer[:k] + longer[k + 1:]
            if len(cut) == len(shorter):
                diffs = [(p, q) for p, q in zip(cut, shorter) if p != q]
                if len(diffs) <= 1 and all(frozenset(d) in _OCR_CONFUSABLE for d in diffs):
                    return True
    return False


def _closer_rival(x: str, y: str, fb: int, lex: Any) -> bool:
    """Is another word, made by changing only the damaged letter(s) of x — where x and the proposed
    repair y differ — and at least as common as y, an equally good reading of the damage? Then the
    repair is a guess (ἰὰν: ἐάν as well as ἄν). The damaged letter may be read as any confusable
    letter or, for a vowel, as any vowel; letters x shares with y are never changed (εον is not a
    rival 'τον' of ἐάν). Movable-ν spellings of y do not count."""
    if len(x) == len(y):
        positions = [i for i, (p, q) in enumerate(zip(x, y)) if p != q]
    elif len(x) == len(y) + 1:
        positions = [i for i in range(len(x)) if x[:i] + x[i + 1:] == y][:1]
    else:
        positions = []
    vowels = "αεηιουω"
    cands = set()
    for i in positions:
        ch = x[i]
        subs = {next(iter(pair - {ch}), ch) for pair in _OCR_CONFUSABLE if ch in pair}
        if ch in vowels and len(x) != len(y):
            subs |= set(vowels)  # a stray vowel may stand for any vowel (ἰὰν: ἐάν as well as ἄν)
        for s in subs:
            cands.add(x[:i] + s + x[i + 1:])
    cands -= {x, y, y + "ν", y[:-1] if y.endswith("ν") else y}
    return any(lex.key_count(c) >= fb for c in cands if c)


def _ocr_shaped(x: str, y: str) -> bool:
    """x can come from y by what OCR does to letters: at most two edits, every substitution a
    visually confusable pair, at most one letter dropped or added (σήσω for στήσω, ἀπεατέψαμεν for
    ἀπεστρέψαμεν), or two neighbouring letters swapped. Real spellings and forms (ἀπέκτεννεν /
    ἀπέκτεινεν, ἐστήρισται / ἐστήρικται, ἀπαρτίᾳ / ἁμαρτίᾳ) are not shaped like this."""
    if x == y:
        return False
    if len(x) == len(y):
        diffs = [i for i, (p, q) in enumerate(zip(x, y)) if p != q]
        if len(diffs) == 2 and diffs[1] == diffs[0] + 1 and x[diffs[0]] == y[diffs[1]] and x[diffs[1]] == y[diffs[0]]:
            return True
        return len(diffs) <= 2 and all(frozenset((x[i], y[i])) in _OCR_CONFUSABLE for i in diffs)
    if abs(len(x) - len(y)) != 1:
        return False
    longer, shorter = (x, y) if len(x) > len(y) else (y, x)
    for i in range(len(longer)):
        cut = longer[:i] + longer[i + 1:]
        diffs = [j for j, (p, q) in enumerate(zip(cut, shorter)) if p != q]
        if len(diffs) <= 1 and all(frozenset((cut[j], shorter[j])) in _OCR_CONFUSABLE for j in diffs):
            return True
    return False


def _itacism_key(key: str) -> str:
    """Letters with the itacistic and vowel-length confusions of Koine scribes merged."""
    k = key.replace("ει", "ι").replace("οι", "ι").replace("αι", "ε")
    return re.sub(r"[ηυ]", "ι", k).replace("ω", "ο")


def _conservation_key(word: str, language: str) -> str:
    """A word key that ignores spelling, for counting words across a verse: itacism, movable ν,
    doubled consonants, elision and aspirated prefixes in Greek (ἐφίσταται = ἐπίσταται); the
    spelling key with b = u in Latin; consonants only in Hebrew."""
    if language == "greek":
        from ..collator import _ELIDED
        k = _itacism_key(_ELIDED.get(word, word))
        k = re.sub(r"ν$", "", k)
        k = re.sub(r"(.)\1", r"\1", k)
        k = re.sub(r"^([εαυ])φ", r"\1π", k)
        k = re.sub(r"^(κα|με)θ", r"\1τ", k)
        return re.sub(r"^ανθ", "αντ", k)
    if language == "latin":
        from ..collator import _latin_ortho_key
        return _latin_ortho_key(word).replace("b", "u")
    if language == "hebrew":
        return "".join(ch for ch in word if "א" <= ch <= "ת") or word
    return word


def _ocr_signature_repairs(key: str) -> set:
    """Repairs of the recurring Swete OCR signatures: a spurious α (πρόσαωπον), υ read for ν
    (αὐτῶυ, ἐυ, σπεῦσου) and αο read for ω (δυνάμεαος)."""
    out = set()
    for i, ch in enumerate(key):
        if ch == "α":
            out.add(key[:i] + key[i + 1:])
        if ch == "υ":
            out.add(key[:i] + "ν" + key[i + 1:])
    out.add(key.replace("αο", "ω"))
    out.discard(key)
    return out


def _transplant_marks(base_raw: str, donor_raw: str) -> str:
    """Put the donor's letters and diacritics into the base token, keeping the base's capitalisation
    and punctuation (used when only the base edition's accents or breathing are wrong)."""
    m = re.match(r"^(\W*)(.*?)(\W*)$", base_raw)
    lead, core, trail = (m.group(1), m.group(2), m.group(3)) if m else ("", base_raw, "")
    donor_core = strip_punct(donor_raw)
    if not donor_core or strip_diacritics_lower(core) != strip_diacritics_lower(donor_core):
        return donor_raw
    # A spacing breathing or apostrophe in front of a bare capital (᾿Εξάγαγε, ’ιδοὺ) is OCR for the
    # breathing the donor now supplies: drop it so the word does not get two.
    lead = re.sub(r"[᾿῾´`’'ʼ᾽]+$", "", lead)
    new = capitalize_first(donor_core) if core[:1].isupper() else donor_core[:1].lower() + donor_core[1:]
    return f"{lead}{new}{trail}"


def _strip_quotes(raw: str) -> str:
    """Drop quotation marks an edition prints around speech (SRGNT “…”, ‘…’) from a borrowed form:
    the base edition's punctuation convention is kept, and a lone quote would be unpaired."""
    out = []
    for w in raw.split():
        w = re.sub(r"^[“‘«‟‛]+", "", w)
        w = re.sub(r"[”»]+$", "", w)
        w = re.sub(r"(?<=[.,;:·;!?])[’]+$", "", w)  # closing single quote after punctuation (not elision)
        if w:
            out.append(w)
    return " ".join(out)


_LATIN_HOMOGLYPH = str.maketrans("ABEHIKMNOPTXYZoaeikmnptuvxy",
                                 "ΑΒΕΗΙΚΜΝΟΡΤΧΥΖοαεικμνπτυνχυ")


_GREEK_CHAR = re.compile(r"[Ͱ-Ͽἀ-῿]")
_LATIN_TABLE = dict(zip("ABEHIKMNOPTXYZoaeikmnptuvxy", "ΑΒΕΗΙΚΜΝΟΡΤΧΥΖοαεικμνπτυνχυ"))
_CAPITAL_HOMOGLYPHS = set("ABEHIKMNOPTXYZ")


def _latin_damaged(w: str) -> bool:
    """A token with Latin letters (accented ones too: 'Áραρἀτ', 'ἐẃκεν') or a digit inside a Greek
    word (a footnote number glued to it: 'θρό9νου', or '1' read for Ι: '’1αμεὶν')."""
    nfd = unicodedata.normalize("NFD", w)
    return bool(re.search(r"[A-Za-z]", nfd) or (re.search(r"[0-9]", nfd) and _GREEK_CHAR.search(w)))


def _lacks_initial_breathing(word: str) -> bool:
    """A word that opens with a vowel but carries no breathing on its first two letters."""
    nfd = unicodedata.normalize("NFD", strip_punct(word))
    letters = [i for i, c in enumerate(nfd) if unicodedata.category(c) != "Mn"]
    if not letters or nfd[letters[0]].lower() not in "αεηιουω":
        return False
    end = letters[2] if len(letters) > 2 else len(nfd)
    return not any(c in "\u0313\u0314" for c in nfd[:end])


def _transliterate_latin(core: str) -> Tuple[str, str]:
    """Read OCR'd Latin look-alikes and footnote digits in a Greek token. Returns the Greek reading
    and the kind of damage: 'digits' (footnote numbers only, deleted: 'θρό9νου' → θρόνου), 'first'
    (a capital look-alike, or a quote standing for the breathing, at the start: 'Aἴνει' → Αἴνει,
    '’Aχεικὰμ' → Ἀχεικὰμ, '‘Yμεῖς' → Ὑμεῖς, '’1αμεὶν' → Ἰαμεὶν), 'stray' (a lower-case Latin letter
    before the word: 'nἐξαπέστειλεν'), 'inner' (inside the word: 'αm̓ὴν'), or 'latin' (letters
    with no Greek reading remain). The caller decides whether the reading is trustworthy."""
    nfd = unicodedata.normalize("NFD", core)
    m = re.match(r"^([’'ʼ᾿‘῾`]?)(.*)$", nfd, flags=re.S)
    mark, rest = (m.group(1), m.group(2)) if m else ("", nfd)
    one_as_iota = bool(re.match(r"^1(?=[Ͱ-Ͽἀ-῿])", rest))
    if one_as_iota:
        rest = "I" + rest[1:]
    if re.search(r"[0-9]", rest) and _GREEK_CHAR.search(rest):
        rest = re.sub(r"[0-9]", "", rest)  # footnote numbers are not part of the word
        if not re.search(r"[A-Za-z]", rest):
            return unicodedata.normalize("NFC", mark + rest), "digits"
    letters = [i for i, c in enumerate(rest) if unicodedata.category(c) != "Mn"]
    latin_at = [k for k, i in enumerate(letters) if re.match(r"[A-Za-z]", rest[i])]
    if not latin_at:
        return unicodedata.normalize("NFC", mark + rest), "none"
    if latin_at != [0]:
        kind = "inner"
    elif rest[0] in _CAPITAL_HOMOGLYPHS or mark or (rest[0] in "lI" and len(letters) > 1):
        kind = "first"
    else:
        kind = "stray"
    if kind == "stray":
        return unicodedata.normalize("NFC", rest[1:]), "stray"
    table = dict(_LATIN_TABLE, l="ι", I="Ι")
    chars = [table.get(c, c) for c in rest]
    if re.search(r"[A-Za-z]", "".join(chars)):
        return unicodedata.normalize("NFC", mark + "".join(chars)), "latin"
    iota_cap = rest[:1] in ("l", "I")
    if chars and (mark or iota_cap or rest[:1].isupper()):
        chars[0] = chars[0].upper()
    word = unicodedata.normalize("NFC", "".join(chars))
    if (mark or iota_cap) and word and _lacks_initial_breathing(word):
        breathing = "\u0314" if mark and mark in "‘῾`" else "\u0313"
        word = unicodedata.normalize("NFC", word[0] + breathing + word[1:])
    return word, kind


def _greek_reading(core: str, lex: Any, pool: Any = ()) -> str:
    """The Greek word a damaged token stands for, or '' when no reading is trustworthy. Footnote
    digits and a capital look-alike at the start need the word to be attested in the corpus; a
    stray lower-case letter in front ('nἐξαπέστειλεν') is dropped if what is left is attested;
    damage inside the word ('αm̓ὴν', which would read as ἀμήν) needs the other edition to print the
    same word in this unit. When the unit prints the word with its accents and the reading has
    lost them or its breathing ('Áραρἀτ'), or its exact spelling occurs nowhere ('Aἶμα' → Αἷμα), the
    unit's spelling is used."""
    if "0" in core:  # a zero inside a Greek word may be an omicron ('Τ0' = Τὸ) or a footnote digit ('π0λάκες')
        as_omicron = _greek_reading(core.replace("0", "ο"), lex, pool)
        if as_omicron and lex is not None and lex.key_count(canonical_compare_key(as_omicron, "greek")) >= 1:
            return as_omicron
    word, kind = _transliterate_latin(core)
    if kind in ("latin", "none") or not word or re.search(r"[A-Za-z0-9]", unicodedata.normalize("NFD", word)):
        return ""
    if kind == "stray" and len([c for c in word if c.isalpha()]) < 2:
        return ""  # 'nὗ': what is left is not a word; the unit's word is used instead
    key = canonical_compare_key(word, "greek")
    if not key:
        return ""
    same = next((strip_punct(p) for p in pool if canonical_compare_key(p, "greek") == key
                 and any(c.islower() for c in p)), "")  # an all-capitals heading ('ΝΟΥΝ') is no spelling model
    attested = lex is not None and lex.key_count(key) >= 1
    nfd = unicodedata.normalize("NFD", word)
    if kind == "first" and len(nfd) > 1 and nfd[0].lower() == next(
            (c for c in nfd[1:] if unicodedata.category(c) != "Mn"), "").lower():
        return ""  # a doubled first letter ('Κκαὶ'): the look-alike is a stray copy, not the letter
    ok = bool(same) if kind == "inner" else (attested or bool(same))
    if not ok:
        return ""
    unseen = lex is not None and lex.form_count(word) == 0  # this exact spelling occurs nowhere
    if same and (unseen or _lacks_initial_breathing(word) or not any(c in "\u0300\u0301\u0342" for c in nfd)):
        return capitalize_first(same) if word[:1].isupper() else same[:1].lower() + same[1:]
    return word


def _split_latin_token(w: str) -> Tuple[str, str, str]:
    """(lead, core, trail) of a token, keeping a quote that stands for a breathing before a Latin
    capital or digit ('‘Yμεῖς', '’1αμεὶν'), which strip_punct would throw away."""
    m = re.match(r"^(\W*?)([’'ʼ᾿‘῾`]?[A-Za-z0-9].*?|[^\W\d_].*?)([.,;·:!?·]*)$", unicodedata.normalize("NFC", w))
    if not m:
        return "", strip_punct(w), ""
    return m.group(1), m.group(2), m.group(3)


def _fix_latin_letters(surface: str, slot: VariationSlot, language: str, lex: Any = None) -> str:
    """Repair each damaged token in the printed reading (see _greek_reading for when the damaged
    edition's own letters are kept). Otherwise the closest word any witness prints in this unit is
    used (γυmῖκα → γυναῖκα). A token with no Greek letter at all becomes the word of the unit it
    reads as ('oaa' = ὅσα, 'cv' = ἐν, 'nal' = καὶ, 'Tt' = τί, 'To' = τὸ) or, if none, is dropped as a
    stray siglum or note ('B', 'ABBREV', 'us')."""
    pool = [w for f in slot.raw_forms if f != "om." for w in f.split() if not _latin_damaged(w)]
    out = []
    for w in surface.split():
        if not _latin_damaged(w):
            out.append(w)
            continue
        lead_q, qcore, qtrail = _split_latin_token(w)
        core = strip_punct(w)
        if not _GREEK_CHAR.search(core):
            flat = unicodedata.normalize("NFD", core)
            tkey = canonical_compare_key("".join(dict(_LATIN_TABLE, l="ι", I="Ι").get(c, c) for c in flat), language)  # nal = ναι ≈ καὶ
            best = None
            for p in pool:
                pk = canonical_compare_key(p, language)
                d = edit_distance(tkey, pk, limit=2)
                if len(tkey) >= 2 and d <= 1 and (best is None or d < best[0]):
                    best = (d, strip_punct(p))
            if best:
                rep = best[1]
                out.append(lead_q + (capitalize_first(rep) if core[:1].isupper() else rep) + qtrail)
            continue
        reading = _greek_reading(qcore, lex, pool)
        if reading:
            out.append(lead_q + reading + qtrail)
            continue
        greek = re.sub(r"[A-Za-z0-9]", "", core)
        trail = re.search(r"[.,;·:!?·]+$", w)
        best = None
        for cand in pool:
            ck = canonical_compare_key(cand, language)
            gk = canonical_compare_key(greek, language) if greek else ""
            d = edit_distance(canonical_compare_key(core.translate(_LATIN_HOMOGLYPH), language), ck, limit=3)
            d = min(d, edit_distance(gk, ck, limit=3) + 1) if gk else d
            if d <= 2 and (best is None or d < best[0]):
                best = (d, cand)
        if best:
            repl = re.sub(r"[.,;·:!?·]+$", "", best[1])
            repl = capitalize_first(repl) if core[:1].isupper() else repl[:1].lower() + repl[1:]
        else:
            repl = core.translate(_LATIN_HOMOGLYPH)
        out.append(repl + (trail.group(0) if trail else ""))
    return " ".join(out)


def _final_sigma(form: str) -> str:
    return re.sub(r"σ(?=$|\s|[.,;·:!?’])", "ς", form)


def _breathing_and_subscript(form: str) -> Tuple[Tuple[int, str], ...]:
    """Positions of breathings and iota subscripts (what separates ἴνα from ἵνα, ἧ from ᾗ)."""
    out = []
    idx = -1
    for ch in unicodedata.normalize("NFD", strip_punct(form).lower()):
        if unicodedata.category(ch) != "Mn":
            idx += 1
        elif ch in ("\u0313", "\u0314", "\u0345"):
            out.append((idx, ch))
    return tuple(out)


_LATIN_VOWELS = "aeiou"


def _latin_u_to_v(word: str) -> str:
    """Consonantal u written v, as the Clementine does: word-initial u before a vowel other than u
    (uobis → vobis, but uua stays), and u between vowels when the next vowel is not u
    (diluuii → diluvii, suauis → suavis, iuuenis → iuvenis)."""
    out = list(word)
    low = word.lower()
    for i, ch in enumerate(low):
        if ch != "u" or i + 1 >= len(low) or low[i + 1] not in _LATIN_VOWELS or low[i + 1] == "u":
            continue
        if i == 0 or (low[i - 1] in _LATIN_VOWELS and not (i >= 2 and low[i - 2] == "q")):
            out[i] = "V" if word[i].isupper() else "v"
    return "".join(out)


def _latin_base_spelling(chosen: str, cv: CollatedVerse, base_raw: str = "") -> str:
    """Re-spell an adopted non-base (Amiatinus) reading in the base edition's orthography, word by
    word: the base's own spelling of the same word in this verse (with its capitalisation when it
    is a name, i.e. capitalised away from a sentence start), else consonantal u as v. The reading
    itself never changes."""
    from ..collator import _latin_ortho_key

    def lookup_keys(w: str) -> List[str]:
        k = canonical_compare_key(w, "latin")
        ortho = _latin_ortho_key(k)
        return [k, "o:" + ortho, "b:" + ortho.replace("b", "u")]  # exact, spelling, spelling with b/u

    base_words: Dict[str, Tuple[str, bool]] = {}
    name_stems: List[str] = []
    toks = cv.witness_texts.get(cv.base_siglum, "").split()
    for i, t in enumerate(toks):
        w = strip_punct(t)
        if not w:
            continue
        sentence_start = i == 0 or bool(re.search(r"[.;:?!]$", toks[i - 1]))
        is_nm = w[:1].isupper() and not sentence_start
        if is_nm:
            nk = _latin_ortho_key(canonical_compare_key(w, "latin"))
            if len(nk) >= 3:
                name_stems.append(nk)
        for key in lookup_keys(w):
            if key not in base_words or is_nm:
                base_words[key] = (w, is_nm)
    chosen_toks = chosen.split()
    base_slot_toks = base_raw.split() if base_raw else []
    out = []
    for idx_w, tok in enumerate(chosen_toks):
        m = re.match(r"^(\W*)(\w+)(\W*)$", tok)
        if not m:
            out.append(tok)
            continue
        lead, core, trail = m.groups()
        hit = next((base_words[k] for k in lookup_keys(core) if k in base_words), None)
        if hit:
            word, is_name = hit
            if not is_name and core[:1].islower():
                word = word[:1].lower() + word[1:]
            elif is_name:
                word = capitalize_first(word)
        else:
            word = _latin_u_to_v(core)
            if core[:1].islower():
                ck = _latin_ortho_key(canonical_compare_key(core, "latin"))
                near_name = len(ck) >= 3 and any(
                    nk[0] == ck[0] and (
                        edit_distance(ck, nk, limit=3) <= (1 if min(len(ck), len(nk)) <= 4 else 2)
                        or (min(len(ck), len(nk)) >= 5 and ck[:5] == nk[:5])
                    )
                    for nk in name_stems
                )
                if not near_name and len(base_slot_toks) == len(chosen_toks) and idx_w < len(base_slot_toks):
                    bw = strip_punct(base_slot_toks[idx_w])
                    bk = _latin_ortho_key(canonical_compare_key(bw, "latin")) if bw else ""
                    if bw[:1].isupper() and bk and ck and bk[0] == ck[0] and edit_distance(ck, bk, limit=3) <= 2:
                        if any(base_words.get(k, ("", False))[1] for k in lookup_keys(bw)):
                            near_name = True
                if near_name:
                    word = capitalize_first(word)
        out.append(lead + word + trail)
    return " ".join(out)


def _fix_inner_caps(raw: str) -> str:
    return " ".join(w[:1] + w[1:].lower() if _inner_capital(w) else w for w in raw.split())


# ---------------------------------------------------------------------------
# Calibrated confidence (fitted on the Greek NT with a whole stream held out)
# ---------------------------------------------------------------------------
CONFIDENCE_K = 1.3
DEPENDENT_PAIRS = [("RP2018", "TR (KJTR)", 0.84)]  # Byzantine text and Textus Receptus share most errors
SINGULAR_EXCLUDED = ("א (01)",)                    # a singular Sinaiticus reading says little
SINGULAR_DOWNWEIGHT = {"B (03)": 0.3}


def calibrated_unit_confidence(groups: List[Tuple[str, List[str], str]], adopted_key: str, cv: CollatedVerse,
                               language: str) -> float:
    """Softmax over pooled reading classes of k × dependence-adjusted, family-deduplicated support.

    ``groups`` = [(canonical key, sigla, representative reading)]. Readings that differ only in
    spelling are pooled first; singular readings of the diplomatic manuscripts are discounted."""
    classes: List[Tuple[List[str], List[str]]] = []  # (keys, sigla)
    for key, sigla, rep in groups:
        placed = False
        for keys, csig in classes:
            if key != "om." and all(k != "om." for k in keys):
                if is_orthographic_equivalence([rep, next(r for kk, _s, r in groups if kk == keys[0])], language)[0]:
                    keys.append(key)
                    csig.extend(sigla)
                    placed = True
                    break
        if not placed:
            classes.append(([key], list(sigla)))

    def support(sigla: List[str]) -> float:
        by_fam: Dict[str, Tuple[float, str]] = {}
        for s in sigla:
            fam = (cv.witness_families or {}).get(s) or _edition_family(s)
            w = cv.witness_weights.get(s, 0.5)
            if fam not in by_fam or w > by_fam[fam][0]:
                by_fam[fam] = (w, s)
        reps = [s for _w, s in by_fam.values()]
        total = 0.0
        for w, s in by_fam.values():
            rho = sum(r for a, b, r in DEPENDENT_PAIRS for o in reps if o != s and (
                (s.startswith(a) and o.startswith(b)) or (s.startswith(b) and o.startswith(a))))
            total += w / (1.0 + rho)
        if len(reps) == 1 and reps[0] in SINGULAR_DOWNWEIGHT:
            total *= SINGULAR_DOWNWEIGHT[reps[0]]
        return total

    scored = []
    for keys, sigla in classes:
        if len(set(sigla)) == 1 and sigla[0] in SINGULAR_EXCLUDED and adopted_key not in keys:
            continue
        scored.append((adopted_key in keys, support(sigla)))
    if len(scored) <= 1:
        return 0.99
    exps = [(is_adopted, math.exp(CONFIDENCE_K * s)) for is_adopted, s in scored]
    total = sum(e for _a, e in exps)
    adopted = sum(e for a, e in exps if a)
    return round(min(0.99, adopted / total if total else 0.5), 3)


def strip_diacritics_lower(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def _token_jaccard(a: str, b: str, language: str) -> float:
    ta = {canonical_compare_key(t, language) for t in re.sub(r"<[^>]+>", " ", a).split()}
    tb = {canonical_compare_key(t, language) for t in re.sub(r"<[^>]+>", " ", b).split()}
    ta.discard("")
    tb.discard("")
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _has_marks(s: str) -> bool:
    return any(unicodedata.category(c) == "Mn" for c in unicodedata.normalize("NFD", s))


class OfflinePhilologicalBrain(CriticalBrainProvider):
    provider_id = "offline_philological"
    display_name = "Offline Philological Brain (Air-Gapped · Zero Internet)"
    requires_internet = False

    # ------------------------------------------------------------------
    # Stage A — Witness gatekeeper
    # ------------------------------------------------------------------
    def evaluate_witness(
        self,
        language: str,
        title: str,
        declared_license: str,
        sample_text: str,
        file_meta: Dict[str, Any],
        existing_samples: Dict[str, str],
    ) -> GatekeeperVerdict:
        reasons: List[str] = []
        combined_header = f"{title}\n{declared_license}\n{sample_text[:3500]}".lower()

        detected_lic = declared_license.strip() or "Unspecified (Requires Verification)"
        license_safe = 0.75
        restricted_hit = None
        for pat, desc in RESTRICTED_LICENSE_PATTERNS:
            if re.search(pat, combined_header, flags=re.IGNORECASE):
                restricted_hit = desc
                break
        open_hit = None
        if not restricted_hit:
            for pat, desc in OPEN_LICENSE_PATTERNS:
                if re.search(pat, combined_header, flags=re.IGNORECASE):
                    open_hit = desc
                    break
        if not restricted_hit and not open_hit:
            for pat, desc in PROTECTED_EDITION_PATTERNS:
                if re.search(pat, combined_header, flags=re.IGNORECASE):
                    restricted_hit = desc
                    break
        elif open_hit:
            protected_mentions = [desc for pat, desc in PROTECTED_EDITION_PATTERNS if re.search(pat, combined_header, flags=re.IGNORECASE)]
            if protected_mentions:
                reasons.append(
                    "Header also mentions " + "; ".join(protected_mentions)
                    + " — treated as a citation because an explicit open licence is stated. Verify before relying on it."
                )

        if restricted_hit:
            license_safe = 0.05
            detected_lic = restricted_hit
        elif open_hit:
            detected_lic = open_hit
            license_safe = 1.0
            reasons.append(f"Verified open license / public-domain status: {open_hit}.")
        elif declared_license.strip():
            reasons.append(f"User-declared license: {declared_license} (no restrictive NC/ND markers found).")
            license_safe = 0.85
        else:
            reasons.append("No explicit license tag found in header; defaulted to provisional caution.")

        body_probe = sample_text
        for marker in ("<body", "<osisText", "\\c 1", "<c id="):
            idx = sample_text.find(marker)
            if idx != -1:
                body_probe = sample_text[idx:]
                break

        script_ratio, repl_ratio, glued_count = _script_ratio(body_probe, language)
        quality = min(1.0, max(0.0, script_ratio * 1.05 - repl_ratio * 10.0 - min(0.85, glued_count * 0.12)))

        if not sample_text.strip():
            return GatekeeperVerdict(
                decision="DISREGARDED_CORRUPT",
                tier_assigned=0,
                recommended_weight=0.0,
                detected_license=detected_lic,
                detected_text_type="Empty / Unreadable File",
                confidence=0.99,
                scores={"license_safe": license_safe, "independence": 0.0, "quality": 0.0},
                summary="DISREGARDED: File is empty or unreadable.",
                reasons=["No readable text could be extracted from file."],
            )

        if restricted_hit:
            reasons.append(f"Restricted clause detected ({restricted_hit}); quarantined to Tier 5 Study-Only to keep the Critical Text 100% open-source.")
            return GatekeeperVerdict(
                decision="QUARANTINED_NC",
                tier_assigned=5,
                recommended_weight=0.0,
                detected_license=detected_lic,
                detected_text_type="Quarantined Study Reference",
                confidence=0.98,
                scores={"license_safe": license_safe, "independence": 0.75, "quality": round(quality, 2)},
                summary=f"QUARANTINED (Tier 5): Blocked from open Critical Text ingestion due to {restricted_hit}.",
                reasons=reasons,
            )

        if script_ratio < 0.25:
            reasons.append(
                f"Target script ratio for {language.title()} is only {script_ratio:.0%}; text appears to be English prose, wrong language, or severe OCR garbage."
            )
            return GatekeeperVerdict(
                decision="DISREGARDED_CORRUPT",
                tier_assigned=0,
                recommended_weight=0.0,
                detected_license=detected_lic,
                detected_text_type="Non-Target Script / Corrupt OCR",
                confidence=0.95,
                scores={"license_safe": license_safe, "independence": 0.2, "quality": round(quality, 2)},
                summary=f"DISREGARDED: Insufficient {language.title()} script density ({script_ratio:.0%}).",
                reasons=reasons,
            )

        if glued_count >= 5 or repl_ratio > 0.02:
            reasons.append(
                f"Detected {glued_count} glued/malformed tokens and {repl_ratio:.1%} encoding-replacement characters."
            )
            return GatekeeperVerdict(
                decision="DISREGARDED_CORRUPT",
                tier_assigned=0,
                recommended_weight=0.0,
                detected_license=detected_lic,
                detected_text_type="Defective Digital Transcription",
                confidence=0.96,
                scores={"license_safe": license_safe, "independence": 0.25, "quality": round(quality, 2)},
                summary="DISREGARDED: Word-boundary or character-encoding corruption detected.",
                reasons=reasons,
            )

        best_match_sig = ""
        best_sim = 0.0
        for sig, ex_sample in existing_samples.items():
            sim = _token_jaccard(body_probe[:3000], ex_sample[:3000], language)
            if sim > best_sim:
                best_sim = sim
                best_match_sig = sig

        independence = round(max(0.05, 1.0 - max(0.0, best_sim - 0.55) * 1.8), 2)
        if best_sim >= 0.985:
            reasons.append(
                f"Sample text is {best_sim:.1%} lexically identical to already-admitted witness '{best_match_sig}'; admitting it would double-count the same witness."
            )
            return GatekeeperVerdict(
                decision="DISREGARDED_DUPLICATE",
                tier_assigned=0,
                recommended_weight=0.0,
                detected_license=detected_lic,
                detected_text_type=f"Duplicate of {best_match_sig}",
                confidence=0.94,
                scores={"license_safe": license_safe, "independence": 0.05, "quality": round(quality, 2)},
                summary=f"DISREGARDED (Duplicate): {best_sim:.1%} overlap with existing witness {best_match_sig}.",
                reasons=reasons,
            )

        low_title = f"{title} {sample_text[:800]}".lower()
        if any(k in low_title for k in ["papyrus", "p45", "p46", "p66", "p75", "sinaiticus", "vaticanus", "alexandrinus", "amiatinus", "bezae", "dead sea", "qumran", "uncial"]):
            tier = 4 if language == "greek" else 2
            text_type = "Primary Ancient Manuscript Transcription"
            weight = 0.96
        elif any(k in low_title for k in ["byzantine", "robinson", "patriarchal", "receptus", "stephanus", "scrivener", "samaritan"]):
            tier = 3
            text_type = "Ecclesiastical / Traditional Stream"
            weight = 0.72
        elif any(k in low_title for k in ["westcott", "tischendorf", "nestle", "brenton", "sixtine", "hetzenauer", "wordsworth"]):
            tier = 2
            text_type = "Historic Critical / Diplomatic Edition (PD)"
            weight = 0.88
        else:
            tier = 1
            text_type = "Open Critical / Digital Base Witness"
            weight = 0.86
        if independence < 0.5:
            weight = round(weight * max(0.5, independence + 0.3), 2)
            reasons.append(f"Largely overlaps '{best_match_sig}' ({best_sim:.0%}); weight reduced to {weight:.2f} so it cannot double-count.")

        reasons.append(
            f"Clean {language.title()} script ({script_ratio:.0%} purity), format '{file_meta.get('detected_format', 'plain')}', assigned to Tier {tier} ({text_type}) with weight {weight:.2f}."
        )
        return GatekeeperVerdict(
            decision="ADMITTED",
            tier_assigned=tier,
            recommended_weight=weight,
            detected_license=detected_lic,
            detected_text_type=text_type,
            confidence=0.95,
            scores={"license_safe": license_safe, "independence": independence, "quality": round(quality, 2)},
            summary=f"ADMITTED (Tier {tier}, weight {weight:.2f}): Valid open {language.title()} witness ({text_type}).",
            reasons=reasons,
        )

    # ------------------------------------------------------------------
    # Stage B — Verse adjudication
    # ------------------------------------------------------------------
    def adjudicate_chapter(
        self,
        language: str,
        book_title: str,
        chapter: int,
        collated_verses: List[CollatedVerse],
    ) -> List[VerseAdjudication]:
        return [self._adjudicate_single_verse(language, cv) for cv in collated_verses]

    def _fam(self, sigla: List[str], cv: CollatedVerse) -> float:
        return _family_weighted_sum(sigla, cv.witness_weights, cv.witness_families)

    def _choose_best_surface_form(
        self,
        slot: VariationSlot,
        winning_sigla: List[str],
        cv: CollatedVerse,
        is_start: bool,
        language: str,
    ) -> str:
        """Pick the spelling of the adopted reading in two steps.

        1. The *letters, accents and breathings* go to the form with the most witness support
           (raw weights — two digitisations of one edition that disagree reveal an OCR slip, so
           they are not merged here), with a small tie-break for the orthographic base edition,
           a decisive penalty for impossible forms (κἀθ᾽, rough breathing on ἐξ-) and corpus
           frequency as a check on rare accent forms.
        2. *Capitalisation and punctuation* then come from the base edition when it has that
           form, so the text keeps one convention instead of mixing editions word by word.
        Never a nomen-sacrum contraction or letter-numeral when a written-out form exists."""
        support: Dict[str, float] = {}
        raw_by_shape: Dict[str, List[str]] = {}
        shape_sigla: Dict[str, List[str]] = {}
        for raw_form, sigla in slot.raw_forms.items():
            if raw_form == "om.":
                continue
            overlap = [s for s in sigla if s in winning_sigla]
            if not overlap:
                continue
            shape = _shape_key(raw_form)
            raw_by_shape.setdefault(shape, []).append(raw_form)
            shape_sigla.setdefault(shape, []).extend(overlap)
        if not raw_by_shape:
            return ""
        # One edition, one vote (invariant 4): two digitisations of Swete share their OCR accents.
        for shape, sigla in shape_sigla.items():
            support[shape] = self._fam(sigla, cv)

        def shape_score(shape: str) -> float:
            forms = raw_by_shape[shape]
            score = support[shape]
            if any(cv.base_siglum in slot.raw_forms[f] for f in forms):
                score += ORTHOGRAPHIC_BASE_TIEBREAK
            sample = forms[0]
            if language == "greek":
                if _has_marks(sample) and not is_nomen_sacrum(sample):
                    score += 0.35
                if sample.isupper() and len(strip_punct(sample)) > 1:
                    score -= 0.25
                if is_nomen_sacrum(sample) or is_letter_numeral(sample):
                    score -= 0.8
                if strip_punct(sample).lower() in ("ἴδεν", "ἴδον"):
                    score -= 0.20
                score -= max((_greek_token_defect_penalty(w)[0] for w in sample.split()), default=0.0)
                lex_ = cv.lexicon
                base_divides = (getattr(cv, "testament", "") != "NT"
                                and any(cv.base_siglum in slot.raw_forms[f]
                                        and all(_greek_token_defect_penalty(w)[0] == 0 for w in f.split())
                                        for f in forms))
                if lex_ is not None and len(sample.split()) > 1 and not base_divides:
                    joined = canonical_compare_key(sample.replace(" ", ""), language)
                    parts = [canonical_compare_key(w, language) for w in sample.split()]
                    # "αὖ. τοὺς" is the common word αὐτοὺς split by OCR; "κατάρασά. μένον" a rare one
                    # split into a non-word.
                    if lex_.key_count(joined) >= 20 or (lex_.key_count(joined) >= 1 and any(lex_.key_count(p) <= 1 for p in parts)):
                        score -= IMPOSSIBLE_FORM_PENALTY
            elif language == "latin" and sample[:1].isupper() and is_start:
                score += 0.15
            return score

        best_shape = max(support, key=lambda sh: (shape_score(sh), sh))
        forms = raw_by_shape[best_shape]
        if language == "greek":
            defect_free = [f for f in forms if all(_greek_token_defect_penalty(w)[0] == 0 for w in f.split())]
            if defect_free:
                forms = defect_free
        sane = [f for f in forms if not _inner_capital(f)]  # ἸάΦεθ: OCR capital inside a word
        if sane:
            forms = sane
        else:
            forms = [_fix_inner_caps(f) for f in forms]  # only the offending word is lowercased
        base_forms = [f for f in forms if cv.base_siglum in slot.raw_forms.get(f, [])]
        chosen = base_forms[0] if base_forms else max(forms, key=lambda f: (sum(cv.witness_weights.get(s, 0.5) for s in slot.raw_forms.get(f, [])), f))
        base_raw = next((f for f, sigs in slot.raw_forms.items() if cv.base_siglum in sigs and f != "om."), "")
        if not base_forms:
            chosen = _strip_quotes(chosen)
            if base_raw and len(base_raw.split()) == 1 == len(chosen.split()) and not base_raw.isupper():
                # Same letters, the base only had wrong accents/breathings: move the corrected marks
                # onto the base token, keeping its capitalisation and punctuation.
                chosen = _transplant_marks(_fix_inner_caps(base_raw), chosen)
                if (language == "greek" and getattr(cv, "testament", "") == "OT"
                        and base_raw.endswith(",") and chosen.endswith(".")
                        and edit_distance(canonical_compare_key(base_raw, "greek"), canonical_compare_key(chosen, "greek"), limit=3) <= 2):
                    chosen = chosen[:-1] + ","
            elif (language == "greek" and base_raw and len(base_raw.split()) == 1 and len(chosen.split()) == 2
                    and _greek_token_defect_penalty(base_raw)[0] > 0):
                w1, w2 = chosen.split()
                k1, k2 = canonical_compare_key(w1, "greek"), canonical_compare_key(w2, "greek")
                if not k1.endswith("ν") and k1 + "ν" + k2 == canonical_compare_key(base_raw, "greek"):
                    chosen = f"{w1}ν {w2}"  # preserve base edition's movable ν when ungluing (1 Sam 14:48 ἐπάταξεν τὸν)
            # Keep the base edition's capitalisation convention (Swete capitalises direct speech, the
            # Clementine names) even when its spelling lost; for a multi-word reading only at the start
            # of the verse, since the base's capital may belong to a name the reading does not contain.
            if (base_raw[:1].isupper() and not base_raw.isupper() and chosen[:1].islower()
                    and (len(chosen.split()) == 1 or is_start)):
                chosen = capitalize_first(chosen)

        if language == "greek":
            chosen = self._transliterate_token(chosen, cv)
        lex = cv.lexicon
        if language == "greek" and lex is not None and _has_marks(chosen) and not chosen.isupper() and " " not in chosen:
            # A rare accent/breathing form beside a common one with the same letters is an OCR slip
            # (ἴνα for ἵνα, ἧ for ᾗ, ἤξει for ἥξει). Clitics are left alone: their accent depends on context.
            own = lex.form_count(chosen)
            want = slot.form_keys.get(chosen, canonical_compare_key(chosen, language))
            defective = _greek_token_defect_penalty(chosen)[0] > 0
            alts = [f for f in slot.raw_forms if f not in ("om.", chosen) and slot.form_keys.get(f) == want
                    and _has_marks(f) and not f.isupper() and " " not in f and _greek_token_defect_penalty(f)[0] == 0]
            better = max(alts, key=lex.form_count, default="")
            # clitics: their accent depends on context, but a wrong breathing or subscript (οὖ for οὗ,
            # ἑν for ἐν) is still a misprint
            if better and (want not in _UNACCENTED_OK or defective
                           or _breathing_and_subscript(chosen) != _breathing_and_subscript(better)):
                # Only where the choice was the base edition's tie-break, never against a majority of
                # editions (an enclitic accent the editions agree on is context, not OCR).
                ch_support = support.get(_shape_key(chosen), 0.0)
                bt_support = support.get(_shape_key(better), self._fam(slot.raw_forms.get(better, []), cv))
                # A breathing that two independent digitisations of the edition print with exactly the same
                # marks (the keyed Swete transcription and the Swete OCR: Ἰεροσολύμων in Maccabees, αὐτὴ ἡ
                # ὁλοκαύτωσις) is the edition's own, not an OCR slip. Accents and iota subscripts are not
                # protected: the two share some misaccents (Κύριου, Amos 8:11).
                exact = unicodedata.normalize("NFC", strip_punct(chosen)).lower()
                same_marks = [s for f, sigs in slot.raw_forms.items() if f != "om."
                              and unicodedata.normalize("NFC", strip_punct(f)).lower() == exact for s in sigs]
                breathing = lambda f: tuple(m for m in _breathing_and_subscript(f) if m[1] != _YPOG)  # noqa: E731
                subscript = lambda f: tuple(m for m in _breathing_and_subscript(f) if m[1] == _YPOG)  # noqa: E731
                printed = (breathing(chosen) != breathing(better) and subscript(chosen) == subscript(better)
                           and independent_digitisations(same_marks) >= 2)
                if (ch_support <= bt_support + ORTHOGRAPHIC_BASE_TIEBREAK and not printed) or defective:
                    n_better = lex.form_count(better)
                    accent_only = _breathing_and_subscript(chosen) == _breathing_and_subscript(better)
                    ratio = 20 if accent_only else 5
                    if defective or (n_better >= 50 and n_better >= ratio * max(1, own)):
                        chosen = _transplant_marks(chosen, better)

        elided = bool(re.search(r"[’ʼ᾽']$", chosen))  # elided words (καθ’, ἀπ’) carry no accent
        all_caps = chosen.isupper() and len(strip_punct(chosen)) > 1  # a single capital letter (Ἧ) is not an incipit
        if language == "greek" and ((not _has_marks(chosen) and not elided) or all_caps or is_nomen_sacrum(chosen) or is_letter_numeral(chosen)):
            # Borrow a properly accented spelling of the same word from any witness in the verse
            # (unaccented manuscript forms, all-caps incipits, contractions).
            want = slot.form_keys.get(chosen, canonical_compare_key(chosen, language))
            alts = [
                f for f in slot.raw_forms
                if f != "om." and slot.form_keys.get(f) == want and _has_marks(f)
                and not f.isupper() and not is_nomen_sacrum(f) and not is_letter_numeral(f)
                and _greek_token_defect_penalty(f)[0] == 0
            ]
            if alts:
                alt = _strip_quotes(max(alts, key=lambda f: (cv.base_siglum in slot.raw_forms[f], self._fam(slot.raw_forms[f], cv))))
                if is_start and alt[:1].islower():
                    alt = capitalize_first(alt)
                chosen = alt
            elif lex is not None and (is_nomen_sacrum(chosen) or all_caps):
                # Contraction (ισ̅) or all-caps incipit (ΛΟΓΟΙ) with no written-out spelling in the
                # verse: use the corpus spelling of the word.
                key = slot.form_keys.get(chosen, canonical_compare_key(chosen, language))
                form = lex.best_form.get(key)
                if form and " " not in key:
                    trail = re.search(r"[.,;·:!?·]+$", chosen)
                    form = _final_sigma(form)
                    if is_start or (chosen.isupper() and len(strip_punct(chosen)) > 1):
                        form = capitalize_first(form)
                    chosen = form + (trail.group(0) if trail else "")
        if language == "greek" and lex is not None and " " in chosen and any(
                w.isupper() and len(strip_punct(w)) > 1 for w in chosen.split()):
            # All-caps incipit inside a multi-word reading (ὍΡΑΣΙΣ ἣν εἶδεν): normalise word by word.
            words = []
            for i, w in enumerate(chosen.split()):
                core = strip_punct(w)
                if w.isupper() and len(core) > 1:
                    form = lex.best_form.get(canonical_compare_key(core, language))
                    if form:
                        trail = re.search(r"[.,;·:!?·]+$", w)
                        form = _final_sigma(form)
                        w = (capitalize_first(form) if i == 0 else form) + (trail.group(0) if trail else "")
                words.append(w)
            chosen = " ".join(words)
        if language == "greek" and any(_greek_token_defect_penalty(w)[0] > 0 for w in chosen.split()):
            # Repair an accent/breathing defect in any word of a single- or multi-word unit (e.g. 2 Kgs 9:2
            # 'ὄψῃ ἐκει' where the verse itself attests 'ἐκεῖ', or a proper name attested cleanly in the lexicon).
            verse_pool: Dict[str, List[str]] = {}
            for txt_src in list(slot.raw_forms) + list(cv.witness_texts.values()):
                if txt_src == "om.":
                    continue
                for pw in txt_src.split():
                    pclean = strip_punct(pw)
                    if pclean and _has_marks(pclean) and not pclean.isupper() and _greek_token_defect_penalty(pw)[0] == 0:
                        verse_pool.setdefault(canonical_compare_key(pclean, language), []).append(pclean)
            repaired_words = []
            for w in chosen.split():
                if _greek_token_defect_penalty(w)[0] > 0 and not re.search(r"[’ʼ᾽']$", w):
                    wk = canonical_compare_key(w, language)
                    cands_w = verse_pool.get(wk, [])
                    donor = max(cands_w, key=lambda x: lex.form_count(x) if lex is not None else 1, default="")
                    if not donor and lex is not None:
                        bf = lex.best_form.get(wk, "")
                        if bf and _greek_token_defect_penalty(bf)[0] == 0 and lex.form_count(bf) >= 2:
                            donor = _final_sigma(bf)
                    if donor:
                        w = _transplant_marks(w, donor)
                repaired_words.append(w)
            chosen = " ".join(repaired_words)
        if not base_forms and cv.base_siglum:
            if language == "latin":
                chosen = _latin_base_spelling(chosen, cv, base_raw=base_raw)
            # The base edition's clause punctuation and closing parenthesis belong after the adopted words too
            # (Gen 1:16 Amiatinus "nocti" for the Clementine "nocti:"; Gen 44:14 "abierant" for "abierat)").
            trail = re.search(r"\)+[.,;:·;!?]*$|[.,;:·;!?]+[”’»]*$", base_raw)
            if trail and not re.search(r"[\).,;:·;!?][”’»]*$", chosen):
                chosen += re.sub(r"[”’»]+$", "", trail.group(0))
        return " ".join(
            normalize_critical_token(t, is_start and i == 0, language)
            for i, t in enumerate(chosen.split())
        ) if " " in chosen else normalize_critical_token(chosen, is_start, language)

    def _display_and_adopt_forms(self, rep: str, ckey: str, cv: CollatedVerse) -> Tuple[str, str]:
        """Show a manuscript reading as the manuscript writes it, with nomina sacra and letter-numerals
        expanded alongside (``χυ̅ (= χριστοῦ)``); the expanded form is what "adopt" inserts."""
        if rep == "om.":
            return rep, ""
        words, keys = rep.split(), ckey.split()
        if len(words) != len(keys) or not any(is_nomen_sacrum(w) for w in words):
            return rep, rep
        lex = cv.lexicon
        full = [
            ((lex.best_form.get(k) if lex is not None else None) or k) if is_nomen_sacrum(w) else w
            for w, k in zip(words, keys)
        ]
        adopt = " ".join(full)
        return f"{rep} (= {adopt})", adopt

    def _next_keys(self, cv: CollatedVerse, idx: int, language: str, n: int) -> List[str]:
        """Canonical keys of the next n words, each slot read as its best-supported reading."""
        out: List[str] = []
        for slot in cv.slots[idx + 1:]:
            forms = [(f, self._fam(sigs, cv)) for f, sigs in slot.raw_forms.items() if f != "om."]
            om = self._fam(slot.raw_forms.get("om.", []), cv) if "om." in slot.raw_forms else 0.0
            if not forms:
                continue
            best_form, w = max(forms, key=lambda p: p[1])
            if om > w:
                continue
            out.extend(k for k in (slot.form_keys.get(best_form) or canonical_compare_key(best_form, language)).split() if k)
            if len(out) >= n:
                break
        return out[:n]

    @staticmethod
    def _next_agreed_key(cv: CollatedVerse, idx: int, language: str) -> str:
        """Canonical key of the next word all witnesses agree on (unanimous or orthographic slot)."""
        for slot in cv.slots[idx + 1:]:
            if slot.kind in ("unanimous", "orthographic_noise"):
                form = next((f for f in slot.raw_forms if f != "om."), "")
                return slot.form_keys.get(form) or canonical_compare_key(form, language)
            return ""
        return ""

    def _internal_evidence(
        self,
        language: str,
        cv: CollatedVerse,
        slot: VariationSlot,
        idx: int,
        scored: List[Tuple[float, str, List[str], str]],
        preceding: List[str],
    ) -> Tuple[Dict[str, float], List[Dict[str, Any]]]:
        """Weight adjustments ({canonical key: delta}) and findings for one substantive unit.
        The deterministic brain has none; the Textual Analysis Brain overrides this."""
        return {}, []

    def _probable_transcription_error(self, scored: List[Tuple[float, str, List[str], str]], cv: CollatedVerse,
                                      slot: Optional[VariationSlot] = None, sentence_start: bool = False,
                                      prev_word: str = "") -> str:
        """Greek only: is the winning reading a digitisation slip of the runner-up?

        Guards (from testing against the whole corpus): the winning side must be a single edition
        family (otherwise it is a real reading attested by several editions — all 16 NT swaps
        without this guard were wrong); the runner-up must not be a singular reading of a diplomatic
        manuscript; the rare form must be rare and the other common (so αὐτοῦ/αὐτόν, τοῦ/τόν are
        never "repaired"); itacistic spellings, movable ν, elision and attested endings are not OCR.
        Multi-word units are checked word by word; every differing word must be a slip."""
        lex = cv.lexicon
        if lex is None or len(scored) != 2:
            return ""
        (_, a, a_sigla, _), (_, b, b_sigla, _) = scored
        if _family_count(a_sigla, cv.witness_families) != 1:
            return ""
        if len(b_sigla) == 1 and b_sigla[0] in DIPLOMATIC_MSS:
            return ""
        raw_of = lambda sigla: next((f for f, sigs in (slot.raw_forms.items() if slot else []) if set(sigs) & set(sigla) and f != "om."), "")
        if a != "om." and re.search(r"[a-z0-9]", a) and (b == "om." or not re.search(r"[a-z0-9]", b)):
            return self._latin_letter_damage(a, b, a_sigla, raw_of(a_sigla), lex)
        if "om." in (a, b):
            return ""
        a_words, b_words = a.split(), b.split()
        if len(a_words) != len(b_words) or not a_words:
            return ""
        a_raw_words, b_raw_words = raw_of(a_sigla).split(), raw_of(b_sigla).split()
        lost_sub = _lost_subscripts(a_raw_words, b_raw_words)
        if lost_sub:
            # ἧ for ᾗ, τῆ for τῇ: OCR loses iota subscripts (it does not add them). Every word that
            # differs must be a lost subscript that either makes a form found far less often, or
            # stands where grammar needs it: after ἐν / σύν / τῇ / τῷ, beside a dative it agrees with,
            # or a subjunctive after ἵνα / ἐάν (ἐν τῆ γῆ, τῇ ἡμέρα τῇ ἕκτη, ἐν ὅλῃ γῆ — ἡμέρα, ἕκτη
            # and γῆ are common nominatives, so counts alone cannot tell).
            lost = []
            for i, wa, wb in lost_sub:
                ca, cb = strip_punct(wa), strip_punct(wb)
                fa, fb = lex.form_count(ca), lex.form_count(cb)
                if _other_form_not_lost_subscript(wa, wb):
                    return ""
                why = _subscript_needed(b_raw_words[i - 1] if i else prev_word, wb, wa,
                                        list(getattr(self, "_clause_context", [])) + b_raw_words[:max(0, i - 1)], lex)
                if fb >= 50 and fb >= 10 * max(fa, 1):
                    lost.append(f"'{wa}' ({fa}×) for '{wb}' ({fb}×)")
                elif why:
                    lost.append(f"'{wa}' for '{wb}' ({why})")
                else:
                    return ""
            return f"Probable OCR slip in {', '.join(a_sigla)}: iota subscript lost: " + ", ".join(lost)
        if independent_digitisations(a_sigla) >= 2:
            # The keyed transcription and the OCR spell the word alike (Dan 3:77 θάλασσαι, Hos 14:2
            # ἠσθένησας): the edition prints it. A lost iota subscript (above) is still repaired.
            return ""
        aligned = len(a_raw_words) == len(a_words) and len(b_raw_words) == len(b_words)
        raw_keys = lambda words: [canonical_compare_key(strip_punct(w), "greek") for w in words]
        if aligned and raw_keys(a_raw_words) == raw_keys(b_raw_words):
            return ""  # only accents or subscripts differ, and OCR does not add subscripts (ἀθῴου ἀθῷος)
        if slot is not None and slot.notes == IOTA_SUBSCRIPT_NOTE:
            return ""
        if aligned:  # compare the words themselves, not slot keys carrying the internal subscript marker
            a_words, b_words = raw_keys(a_raw_words), raw_keys(b_raw_words)
        reasons = []
        for i, (x, y) in enumerate(zip(a_words, b_words)):
            if x == y:
                continue
            a_cap = i < len(a_raw_words) and strip_punct(a_raw_words[i])[:1].isupper()
            b_cap = i < len(b_raw_words) and strip_punct(b_raw_words[i])[:1].isupper()
            # A capital at the start of a verse or sentence is the edition's convention, not a name.
            name_pair = a_cap and b_cap and not (sentence_start and i == 0)
            prev = strip_punct(b_raw_words[i - 1]) if 0 < i <= len(b_raw_words) else (prev_word if i == 0 else "")
            if aligned and re.search(r"[’ʼ᾿']$", a_raw_words[i]) and not re.search(r"[’ʼ᾿']$", b_raw_words[i]):
                return ""  # an elided word against a full one (ποτʼ / πότε) is a spelling, never an OCR slip
            if aligned and _article_run_in(a_raw_words[i], y):
                return ""  # ὁθεός = ὁ θεός run together: a missing space, not a stray letter
            broken = aligned and _broken_token(a_raw_words[i]) and edit_distance(x, y, limit=3) <= 2
            why = ((f"'{a_raw_words[i]}' is a broken token (punctuation inside the word) for '{y}'" if broken else "")
                   or self._ocr_word_slip(x, y, lex, name_pair) or _article_agreement_slip(x, y, prev))
            if not why:
                return ""
            reasons.append(why)
        if not reasons:
            return ""
        return f"Probable OCR/transcription error in {', '.join(a_sigla)}: " + "; ".join(reasons)

    @staticmethod
    def _tidy_donor(surface: str, loser: Tuple[float, str, List[str], str], slot: VariationSlot,
                    cv: CollatedVerse, sentence_start: bool, dittography: bool = False, prev_token: str = "") -> str:
        """Small, safe touches to a word repaired from the other edition (Brenton):
        - the damaged edition's movable ν is kept (Swete 'εἶρεν' → εἶπεν, not Brenton's εἶπε);
        - Brenton's capitalised word printed without any accent in mid-sentence ('Ἀγγελον'), where
          the damaged Swete token was lower-case, takes the corpus's commonest accented spelling;
        - a capital is lowered when Swete's damaged token starts with a lower-case Greek letter
          (Swete's 'τῷ θεῷ' against Brenton's 'τῷ Θεῷ').
        Clitics, elided forms and accented words are never re-spelt (the corpus's best forms are
        lower-case comparison forms, so they are not used for anything else)."""
        lex = cv.lexicon
        l_raw = next((f for f, sigs in slot.raw_forms.items() if set(sigs) & set(loser[2]) and f != "om."), "")
        sw, lw = surface.split(), l_raw.split()
        if lex is None or len(sw) != len(lw):
            return surface
        out = []
        for i, (w, l) in enumerate(zip(sw, lw)):
            m = re.match(r"^(\W*)(.*?)(\W*)$", w)
            lead, core, trail = (m.group(1), m.group(2), m.group(3)) if m else ("", w, "")
            l_core = strip_punct(l)
            new = core
            lk = canonical_compare_key(l_core, "greek")
            ck = canonical_compare_key(core, "greek")
            if (core and lk.endswith("ν") and not core.endswith("ν") and core[-1:] in "εέὲιίὶ" and not dittography
                    and len(lk) >= 3 and not re.search(r"[’ʼ᾿']$", w)
                    and (lk[:-1] == ck or _ocr_shaped(lk[:-1], ck))):
                new = core + "ν"  # movable ν, as the damaged base token spells it (εἶρεν → εἶπεν)
            unaccented = core and not any(c in "\u0300\u0301\u0342" for c in unicodedata.normalize("NFD", core))
            best = lex.best_form.get(canonical_compare_key(core, "greek"), "") if core else ""
            if (unaccented and len(core) >= 4 and core[:1].isupper() and not (sentence_start and i == 0)
                    and l_core[:1].islower() and best and not re.search(r"[’ʼ᾿']", w)
                    and canonical_compare_key(core, "greek") not in _ENCLITIC_PRONOUNS):
                new = _final_sigma(best)
            # Swete's own case: Brenton capitalises θεός, κύριος and verse openings where Swete does
            # not (Exod 3:18 'τῷ θεῷ', 1 Kgs 18:12 'τὸν κύριον'). A Latin look-alike start ('lσμαὴλ')
            # says nothing about case and is left alone.
            l_first = next((c for c in l_core if c.isalpha()), "")
            before = sw[i - 1] if i else prev_token
            nkey = canonical_compare_key(new, "greek")
            articular = canonical_compare_key(before, "greek") in _ARTICLES if before else False
            if (new[:1].isupper() and l_first and _GREEK_CHAR.match(l_first) and l_first.islower()
                    and nkey in _REVERENTIAL_CAPITALS and not (sentence_start and i == 0)
                    and (nkey in _THEOS_FORMS or articular)):
                new = new[:1].lower() + new[1:]  # θεός always; κύριος only after its article (Swete's Κύριος alone)
            out.append(lead + new + trail)
        return " ".join(out)

    @staticmethod
    def _transliterate_token(token: str, cv: CollatedVerse) -> str:
        """Last pass over a printed token (any path, agreed words included): the OCR's slashes and
        '(??)' marks are removed from words ('/ὠσὶν', 'ὑμῶν./'), spacing breathings before bare Greek
        capital vowels ('ʼΩὰ' → 'Ὠὰ') and non-final diaeresis+grave ('Ἀσαῒας' → 'Ἀσαΐας') are normalised,
        and Latin look-alike letters that read as an attested Greek word, or are only a first letter,
        are written in Greek. Word counts never change here, so apparatus positions stay valid."""
        if not token:
            return token
        if "/" in token or "(??)" in token:
            token = " ".join((re.sub(r"/|\(\?\?\)", "", w) if _GREEK_CHAR.search(w) else w) for w in token.split())
        norm_words = []
        for w in token.split():
            # Spacing apostrophe/koronis before a bare Greek capital vowel ('ʼΩὰ', 'ʼΙεθρὰ', 'ʼΑμαλήκ')
            m_br = re.match(r"^([(\[⟦]*)([’'ʼ᾿‘῾`])([ΑΕΗΙΟΥΩ].*)$", unicodedata.normalize("NFD", w))
            if m_br and _lacks_initial_breathing(m_br.group(3)):
                br = "\u0314" if m_br.group(2) in "‘῾`" else "\u0313"
                rest = m_br.group(3)
                w = unicodedata.normalize("NFC", m_br.group(1) + rest[0] + br + rest[1:])
            # Non-final diaeresis + grave ('Ἀσαῒας', 'Σαραῒα'): grave cannot stand before a later vowel
            nfd_w = unicodedata.normalize("NFD", w)
            if "\u0308\u0300" in nfd_w or "\u0300\u0308" in nfd_w:
                nfd_w = re.sub("\u0308\u0300(?=.*[αεηιουωΑΕΗΙΟΥΩ])", "\u0308\u0301", nfd_w)
                nfd_w = re.sub("\u0300\u0308(?=.*[αεηιουωΑΕΗΙΟΥΩ])", "\u0308\u0301", nfd_w)
                w = unicodedata.normalize("NFC", nfd_w)
            norm_words.append(w)
        token = " ".join(norm_words)
        if not any(_latin_damaged(t) for t in token.split()):
            return token
        out = []
        for w in token.split():
            lead_q, qcore, qtrail = _split_latin_token(w)
            if _latin_damaged(qcore) and _GREEK_CHAR.search(qcore):
                reading = _greek_reading(qcore, cv.lexicon)  # no unit pool here: damage inside a word stays
                if reading:
                    w = lead_q + reading + qtrail
            out.append(w)
        return " ".join(out)

    @staticmethod
    def _latin_letter_damage(a: str, b: str, a_sigla: List[str], a_raw: str = "", lex: Any = None) -> str:
        """The winning reading has Latin letters or digits in it, which no Greek edition prints. Only a
        single damaged token can hand the unit to the other reading: when the Greek letters are close
        to it (Exod 17:10 'καἳ̀nρ' = καὶ Ὢρ), when it is one word against one word of similar shape
        (Gen 12:14 'Μrπτον' = Αἴγυπτον), or when it has no Greek letter at all against an omission
        (Gen 19:26 'D'). A token whose Latin letters simply transliterate ('Aἴνει', '’Aχεικὰμ') keeps the
        damaged edition's own letters, and a longer reading is repaired word by word at the surface,
        so the other edition's other words are never imported (Isa 36:6 ὃς, Exod 29:46 θεὸς)."""
        who = ", ".join(a_sigla)
        flat = a.replace(" ", "")
        ga = re.sub(r"[a-z0-9]", "", flat)
        if b == "om.":
            if not ga and " " not in a.strip():
                return f"OCR damage in {who}: '{a}' is a stray Latin letter, siglum or numeral, not Greek"
            return ""
        if " " in a.strip():
            return ""  # repaired word by word (_fix_latin_letters)
        _lead, core, _trail = _split_latin_token(a_raw) if a_raw else ("", "", "")
        if core and not _GREEK_CHAR.search(core):
            # no Greek letter at all ('us.' for Λευίταις, Num 7:6): not text. Handed over only for a
            # one-word rival; against a longer reading the surface repair finds the matching word
            # ('Tt' = τί, 2 Kgs 4:14), so Brenton's other words are not imported.
            if " " not in b.strip():
                return f"OCR damage in {who}: '{a_raw}' has no Greek letters; the other edition's word is printed"
            return ""
        if core and _greek_reading(core, lex, b.split()):
            return ""  # the damaged edition's own word, written in Greek letters at the surface
        gb = b.replace(" ", "")
        lim = max(2, len(gb) // 3)
        if edit_distance(ga, gb, limit=lim + 1) <= lim:
            return f"OCR damage in {who}: '{a}' mixes Latin letters or digits into Greek"
        if len(a.split()) == len(b.split()) == 1 and len(ga) >= 2:
            half = len(b) // 2
            if edit_distance(flat.translate(_LATIN_HOMOGLYPH), b, limit=half + 1) <= half:
                return f"OCR damage in {who}: '{a}' mixes Latin letters into Greek; no Greek word is closer than '{b}'"
        return ""

    def _repair_slip_words(self, surface: str, win_key: str, win_sigla: List[str],
                           runner: Tuple[float, str, List[str], str], slot: VariationSlot, cv: CollatedVerse,
                           prev_word: str = "") -> Tuple[str, str]:
        """Inside a multi-word reading won by one edition family, repair the words that are only OCR
        slips of the runner-up's words at the same position (Exod 12:21 'θύσετε τὸ πόσχα': πόσχα is
        repaired, the real variant θύσετε / θύσατε is kept and stays in the apparatus). Also word by
        word: a lost iota subscript where grammar or the counts need it (Deut 19:10 'ἐν τῆ γῇ ᾗ'),
        and a broken token with punctuation inside it (Exod 10:2 'δό,τα')."""
        lex = cv.lexicon
        if lex is None or _family_count(win_sigla, cv.witness_families) != 1:
            return surface, ""
        r_key, r_sigla = runner[1], runner[2]
        if r_key == "om." or (len(r_sigla) == 1 and r_sigla[0] in DIPLOMATIC_MSS):
            return surface, ""
        wk, rk, sw = win_key.split(), r_key.split(), surface.split()
        r_raw = next((f for f, sigs in slot.raw_forms.items() if set(sigs) & set(r_sigla) and f != "om."), "")
        rw = r_raw.split()
        if not (len(wk) == len(rk) == len(sw) == len(rw)) or len(wk) < 2:
            return surface, ""
        fixed = []
        for i, (x, y) in enumerate(zip(wk, rk)):
            if x == y:
                continue
            if re.search(r"[’ʼ᾿']$", sw[i]) and not re.search(r"[’ʼ᾿']$", rw[i]):
                continue  # an elided word (ἡνίκʼ) against a full one is a spelling, not a slip
            # judged on the printed word, which _fix_latin_letters has already transliterated where it
            # could (Exod 6:15 '’1αμεὶν' → Ἰαμεὶν, B's own spelling, not Brenton's Ἰαμεὶμ)
            xk = canonical_compare_key(strip_punct(sw[i]), "greek")
            yk = canonical_compare_key(strip_punct(rw[i]), "greek")
            latin = bool(re.search(r"[A-Za-z0-9]", strip_punct(sw[i]))) and not re.search(r"[A-Za-z0-9]", strip_punct(rw[i])) \
                and edit_distance(re.sub(r"[a-z0-9]", "", xk), yk, limit=3) <= 2
            broken = _broken_token(sw[i]) and edit_distance(xk, yk, limit=3) <= 2
            subscript = False
            if _lost_subscripts([sw[i]], [rw[i]]) and not _other_form_not_lost_subscript(sw[i], rw[i]):
                fa, fb = lex.form_count(strip_punct(sw[i])), lex.form_count(strip_punct(rw[i]))
                subscript = (fb >= 50 and fb >= 10 * max(fa, 1)) or bool(_subscript_needed(
                    sw[i - 1] if i else prev_word, rw[i], sw[i], list(getattr(self, "_clause_context", [])) + sw[:max(0, i - 1)], lex))
            if latin or broken or subscript or (xk and yk and xk != yk and self._ocr_shape_slip(
                    xk, yk, lex, name=i > 0 and strip_punct(sw[i])[:1].isupper())):
                trail = re.search(r"[.,;·:!?·]+$", sw[i])
                new = re.sub(r"[.,;·:!?·]+$", "", _strip_quotes(rw[i]))
                first = strip_punct(sw[i])[:1]
                damaged_initial = (bool(first) and bool(_GREEK_CHAR.match(first))  # a Latin capital still shows the case
                                   and _plain_greek(strip_punct(sw[i]))[:1] != _plain_greek(strip_punct(new))[:1])
                if not damaged_initial:  # Swete's case, unless the OCR damaged its first letter (ετταίου = Χετταίου)
                    new = capitalize_first(new) if sw[i][:1].isupper() else new[:1].lower() + new[1:]
                fixed.append((sw[i], new))
                sw[i] = new + (trail.group(0) if trail else "")
        if not fixed:
            return surface, ""
        return " ".join(sw), (f"OCR slip(s) inside a longer reading of {', '.join(win_sigla)} repaired from "
                              f"{', '.join(r_sigla)}: " + ", ".join(f"'{a}' → '{b}'" for a, b in fixed))

    @staticmethod
    def _ocr_shape_slip(x: str, y: str, lex: Any, name: bool = False) -> str:
        """Inside a longer reading only recognised OCR shapes are repaired: the Swete signatures, one
        visually confusable letter (πόσχα, κοὶ, ἀπγύριον), or two neighbouring letters swapped
        (ἀπέστελιεν) — and only when the damaged form is (almost) unattested or a recurring OCR form
        of a very common word. Never an ending, a prefix or another lemma (μακροχρόνιοι / -ος)."""
        fa, fb = lex.key_count(x), lex.key_count(y)
        if y in _ocr_signature_repairs(x) and not (x.endswith("α") and y == x[:-1]):
            return f"'{x}' → '{y}' (OCR signature)" if fa <= 2 and fb >= 20 else ""
        nu_ok = ("εν", "ιν") if name else ("ν",)  # a name has no movable ν (Ἰωνάθας is not Ἰωνάθαν)
        xs = x[:-1] if x.endswith(nu_ok) and not y.endswith("ν") and len(x) > 4 else x
        ys = y[:-1] if y.endswith(nu_ok) and not x.endswith("ν") and len(y) > 4 else y
        if (xs, ys) != (x, y) and _ocr_shaped(x, y) and (
                not _ocr_shaped(xs, ys) or edit_distance(x, y, limit=3) <= edit_distance(xs, ys, limit=3)):
            xs, ys = x, y  # the final ν is part of the damage, not a movable ν
        if (abs(len(xs) - len(ys)) == 1 and fa <= 1 and fb >= 20 and _ocr_shaped(xs, ys)
                and not _prefix_change(xs, ys) and min(len(xs), len(ys)) >= 4
                and not _ei_i_spelling(xs, ys)  # not an ει / ι spelling (Κουσεί / Χουσί)
                and not _b_doubled_consonant(xs, ys)  # not B's own doubled consonant (παρενέβαλλον)
                and not (xs[:1] == "ε" and xs[1:] == ys)):  # nor B's double augment (ἐπροσηύξατο)
            return f"'{x}' → '{y}' (a letter dropped or added; '{x}' occurs {fa}× in the corpus)"  # ἐβασλευσεν
        if len(x) != len(y) or len(x) < 3:
            return ""
        diffs = [(p, q) for p, q in zip(x, y) if p != q]
        common = next((i for i, (p, q) in enumerate(zip(x, y)) if p != q), len(x))
        rare = (fa <= 1 and fb >= 100) or (fa <= 200 and fb >= 500 * max(fa, 1))
        # The last two letters are an ending, never repaired here — except in a very common short
        # word whose damaged form recurs (κοὶ 147× for καί), which has no rival ending.
        not_ending = common < len(x) - 2 or (len(x) <= 4 and fb >= 1000)  # πεπὶ 3× for περί 4,018×
        if len(diffs) == 1 and frozenset(diffs[0]) in _OCR_CONFUSABLE and not_ending and rare:
            return f"'{x}' → '{y}' (letter misread)"
        if (len(diffs) == 2 and x[common:common + 2] == y[common:common + 2][::-1] and rare):
            return f"'{x}' → '{y}' (letters swapped)"
        return ""

    @staticmethod
    def _ocr_word_slip(x: str, y: str, lex: Any, name_pair: bool) -> str:
        fa, fb = lex.key_count(x), lex.key_count(y)
        if y in _ocr_signature_repairs(x) and not (x.endswith("α") and y == x[:-1]):
            # Recurring Swete signature (πρόσαωπον, αὐτῶυ, δυνάμεαος), only when the damaged form is
            # (almost) unattested and the repair common; a dropped final α is elision, not OCR.
            if fa <= 2 and fb >= max(20, 20 * max(fa, 1)):
                return f"'{x}' for '{y}' (recurring OCR signature: spurious α, υ for ν or αο for ω; {fa}× vs {fb}×)"
            return ""
        if len(x) == len(y) == 2 and sum(p != q for p, q in zip(x, y)) == 1 and fa <= 2 and fb >= 1000:
            # A two-letter form found once or twice beside a particle found thousands of times
            # (δὶ 1× for δέ 23,672×); real two-letter variants (ἐν / ἐκ, τό / τά) are all common.
            return f"'{x}' occurs {fa}× in the Greek corpus, '{y}' {fb}× (one letter apart)"
        if len(x) < 3:
            return ""
        # Movable ν is set aside before comparing (εἶρεν / εἶπε differ by one misread letter).
        xs, ys = x, y
        # (for a name only a real movable ν after ε / ι: Ἰωνάθαν, Ἀνά are not ν-forms of Ἰωνάθας, Ὠνάν)
        nu_ok = ("εν", "ιν") if name_pair else ("ν",)
        if x.endswith(nu_ok) and not y.endswith("ν") and len(x) > 3:
            xs = x[:-1]
        elif y.endswith(nu_ok) and not x.endswith("ν") and len(y) > 3:
            ys = y[:-1]
        if xs == ys:
            return ""  # movable ν (πέρα / πέραν)
        if (xs, ys) != (x, y) and _ocr_shaped(x, y) and (
                not _ocr_shaped(xs, ys) or edit_distance(x, y, limit=3) <= edit_distance(xs, ys, limit=3)):
            xs, ys = x, y  # the final ν is part of the damage (ζητῶνς, αὐτῶμ), not a movable ν
        dist = edit_distance(xs, ys, limit=2)
        if dist > (1 if len(xs) <= 4 else 2):
            return ""
        if _itacism_key(xs) == _itacism_key(ys):
            return ""  # a scribal spelling of the same word (ει/η/ι/οι/υ, ο/ω, αι/ε), not a misread letter
        if _prefix_change(xs, ys) or _DOUBLED.sub(r"\1", xs) == _DOUBLED.sub(r"\1", ys):
            return ""  # another compound (προέθηκεν / προσέθηκεν) or a doubled consonant (ἀπέκτεννεν): not a misread letter
        diffs = [(p, q) for p, q in zip(xs, ys) if p != q] if len(xs) == len(ys) else []
        one_confusable = len(diffs) == 1 and frozenset(diffs[0]) in _OCR_CONFUSABLE
        common = next((i for i, (p, q) in enumerate(zip(xs, ys)) if p != q), min(len(xs), len(ys)))
        swapped = len(diffs) == 2 and xs[common:common + 2] == ys[common:common + 2][::-1]
        dropped = len(xs) + 1 == len(ys) and dist == 1
        if name_pair:
            # A damaged name (Ἀβαὰμ, Ἀβρόμ for Ἅβραμ) only when the damage has an OCR shape — one
            # confusable letter, one letter dropped or two swapped; B's own rare name spellings
            # (Ἰωσαφάθ beside Ἰωσαφάτ) are readings, never repaired.
            first_letter = one_confusable and xs[1:] == ys[1:]  # Η / Π, Γ / Π at the start of a capitalised word
            if (fa <= 2 and fb >= 50 and (one_confusable or dropped or swapped)) or (
                    first_letter and fa <= 30 and fb >= 50 and fb >= 20 * max(fa, 1)):
                return f"'{x}' occurs {fa}× in the Greek corpus, '{y}' {fb}× (a damaged name: one letter misread, dropped or swapped)"
            return ""
        extreme = one_confusable and fa <= 5 and fb >= 200 * max(fa, 1)  # εἶρεν 5× / εἶπε 1,628×
        if (fa >= 2 and len(xs) > 4 and common >= max(len(xs), len(ys)) - 4 and not extreme
                and sorted(xs[common:]) != sorted(ys[common:])):  # swapped letters (απέστελιεν) are OCR, not an ending
            return ""  # an attested ending (Koine ἐφάγοσαν / ἔφαγον, φάγησθε / φάγητε): morphology, not OCR
        if not _ocr_shaped(xs, ys):
            # Counts cannot tell a garbled word from a genuine rare one: both occur once (στερεούς,
            # προέθηκεν, ἀπαρτίᾳ are real readings of B). Only an OCR-shaped change is repaired.
            return ""
        ok = ((fa <= 10 and fb >= max(20, 20 * fa)) or (fa <= 30 and fb >= 100 * fa)
              or (fa <= 200 and fb >= 500 * fa))  # a recurring OCR form of a very common word (κοὶ 149× for καί)
        if ok and _closer_rival(xs, ys, fb, lex):
            return ""  # another common word is as close to the damaged form (ἰὰν: ἐάν as well as ἄν)
        if ok:
            return f"'{x}' occurs {fa}× in the Greek corpus, '{y}' {fb}× (one or two letters apart)"
        return ""

    def _verse_level_item(self, cv: CollatedVerse) -> Tuple[Optional[ApparatusItem], bool, float, str]:
        """Apparatus entry for witnesses that lack the whole verse or bracket it."""
        lacking = sorted(set(cv.absent_witnesses) | set(cv.doubtful_witnesses))
        if not lacking and not cv.single_stream:
            return None, False, 1.0, ""
        present = [s for s in cv.witness_texts if s not in cv.doubtful_witnesses]
        w_lack = _family_weighted_sum(lacking, cv.witness_weights, cv.witness_families) if lacking else 0.0
        w_present = _family_weighted_sum(present, cv.witness_weights, cv.witness_families) if present else 0.0
        bracket = w_lack > w_present
        parts = []
        if cv.absent_witnesses:
            parts.append(f"absent from {', '.join(sorted(cv.absent_witnesses))}")
        if cv.doubtful_witnesses:
            parts.append(f"bracketed as a later addition by {', '.join(sorted(cv.doubtful_witnesses))}")
        detail = "; ".join(parts)
        if cv.single_stream:
            # Greek NT: a verse found in one text stream only (RP/TR's Acts 19:41, Rom 14:24–26) is
            # printed in brackets with low presence confidence, whatever the silent witnesses weigh.
            note = (cv.single_stream + (f" Verse {detail}." if detail else "")
                    + " Printed inside ⟦ ⟧ as doubtful, not deleted.")
            item = ApparatusItem(
                slot_index=-1, lemma="⟦verse⟧", lemma_witnesses=present,
                variants=[{"reading": "om. verse", "witnesses": lacking or ["all other witnesses"], "weight_sum": round(w_lack, 2)}],
                note=note, word_index=0, word_count=0, kind="verse",
            )
            conf = min(0.2, w_present / max(w_present + w_lack, 1e-9)) if lacking else 0.2
            return item, True, conf, note
        if bracket:
            note = (
                f"Verse {detail} (weight {w_lack:.2f}) against {', '.join(present) or 'no unbracketed witness'} "
                f"(weight {w_present:.2f}). Printed inside ⟦ ⟧ as a probable later addition, not deleted."
            )
        else:
            note = f"Verse {detail} (weight {w_lack:.2f}); retained on the weight of {', '.join(present)} ({w_present:.2f})."
        item = ApparatusItem(
            slot_index=-1,
            lemma="⟦verse⟧" if bracket else "verse",
            lemma_witnesses=present,
            variants=[{"reading": "om. verse", "witnesses": lacking, "weight_sum": round(w_lack, 2)}],
            note=note,
            word_index=0,
            word_count=0,
            kind="verse",
        )
        conf = w_present / max(w_present + w_lack, 1e-9)
        return item, bracket, conf, note

    # ------------------------------------------------------------------
    # Verse-level word bookkeeping (alignment safety nets)
    # ------------------------------------------------------------------
    @staticmethod
    def _witness_key_counts(cv: CollatedVerse, language: str) -> Dict[str, Counter]:
        """How often each canonical word occurs in each complete witness of the verse, read off the
        aligned slots (so contracted sacred names count as the full word and illegible words cast
        no vote). Fragmentary witnesses and witnesses without the verse are left out."""
        counts: Dict[str, Counter] = {
            s: Counter() for s, t in cv.witness_texts.items()
            if t.strip() and s not in cv.fragmentary_witnesses and s not in cv.absent_witnesses
        }
        for slot in cv.slots:
            for raw, sigs in slot.raw_forms.items():
                if raw == "om.":
                    continue
                key = slot.form_keys.get(raw) or " ".join(canonical_compare_key(t, language) for t in raw.split())
                words = [_conservation_key(k, language) for k in key.split() if k]
                for s in sigs:
                    if s in counts:
                        counts[s].update(words)
        return counts

    def _omission_credit(self, key_groups: Dict[str, List[Tuple[str, List[str]]]], counts: Dict[str, Counter],
                         cv: CollatedVerse, idx: int, language: str) -> Tuple[List[str], str]:
        """Witnesses in the omission group whose copy of the omitted words was aligned into another
        unit, where their reading loses (Mark 3:14: Sinaiticus's "ιβʹ οὓς καὶ ἀποστόλους ὠνόμασεν"
        sits in the δώδεκα unit), are not counted for "om." here — otherwise the words would vanish
        from the text. A witness whose copy of the words wins elsewhere has merely transposed them
        and keeps its vote. Needs at least two content words (≥4 letters) in one other unit."""
        if "om." not in key_groups or len(counts) < 2:
            return [], ""
        om_sigla = [s for _, sigs in key_groups["om."] for s in sigs]
        dropped: List[str] = []
        shown = ""
        for ckey, members in key_groups.items():
            if ckey == "om.":
                continue
            content = [k for k in ckey.split() if len(k) >= 4]
            if len(content) < 2:
                continue
            for o in om_sigla:
                if o in dropped or o not in counts:
                    continue
                if self._words_lost_elsewhere(cv, idx, o, content, language):
                    dropped.append(o)
                    shown = members[0][0]
        if not dropped:
            return [], ""
        note = (f"Not counted as omitting '{shown}': {', '.join(dropped)} ha{'ve' if len(dropped) > 1 else 's'} "
                f"these words in a neighbouring unit where the alignment put them (not an omission)")
        return dropped, note

    def _words_lost_elsewhere(self, cv: CollatedVerse, idx: int, siglum: str, content: List[str], language: str) -> bool:
        need = Counter(content)
        for j, other in enumerate(cv.slots):
            if j == idx:
                continue
            raw = next((f for f, sigs in other.raw_forms.items() if siglum in sigs and f != "om."), "")
            if not raw:
                continue
            key = other.form_keys.get(raw) or " ".join(canonical_compare_key(t, language) for t in raw.split())
            have = Counter(key.split())
            if sum(min(n, have[k]) for k, n in need.items()) < 0.8 * len(content):
                continue
            if other.kind != "substantive_variant":
                return False  # the words are printed there
            weights: Dict[str, List[str]] = {}
            for f, sigs in other.raw_forms.items():
                fk = "om." if f == "om." else (other.form_keys.get(f) or " ".join(canonical_compare_key(t, language) for t in f.split()))
                weights.setdefault(fk, []).extend(sigs)
            best = max(weights, key=lambda k: self._fam(weights[k], cv))
            return best != key  # credited only if this witness's copy of the words loses there
        return False

    # ------------------------------------------------------------------
    # Verse adjudication
    # ------------------------------------------------------------------
    def _adjudicate_single_verse(self, language: str, cv: CollatedVerse) -> VerseAdjudication:
        verse_item, bracket, verse_conf, verse_note = self._verse_level_item(cv)
        if not cv.slots:
            return VerseAdjudication(
                verse=cv.verse,
                critical_text="",
                confidence=0.0,
                decision_source=self.display_name,
                apparatus=[verse_item] if verse_item else [],
                rationale=verse_note or "No admitted witness has text for this verse.",
            )

        # Restoring words and omission credit are validated on the Greek NT, whose witnesses are
        # clean digital editions; in the OCR-damaged Septuagint files and the two-witness Hebrew and
        # Latin collations they would count misread letters as missing words, so they stay off there.
        # Removing a word printed more often than any witness has it is safe everywhere.
        safety_nets = language == "greek" and getattr(cv, "testament", "") == "NT"
        counts = self._witness_key_counts(cv, language)
        credit_counts = counts if safety_nets else {}
        forced: Dict[int, str] = {}
        forced_notes: Dict[int, str] = {}
        forced_conf: Dict[int, float] = {}
        self._forced_conf = forced_conf
        self._forced_canon: Dict[int, str] = {}
        core = self._adjudicate_core(language, cv, forced, forced_notes, credit_counts)
        # Conservation: a word the weighted majority of witnesses has may not vanish because its
        # support was split between two positions, and no content word may appear more often than
        # in any witness. Both are alignment artefacts, repaired by forcing the unit that carries
        # the word with the heaviest support. At most three passes; a unit is forced once.
        for _ in range(3):
            fix = self._conservation_fix(core, counts, forced, cv, language, deficit=safety_nets)
            if not fix:
                break
            idx, key, note, conf = fix
            forced[idx] = key
            forced_notes[idx] = note
            forced_conf[idx] = conf
            core = self._adjudicate_core(language, cv, forced, forced_notes, credit_counts)
        # Attested runs (Greek NT): units voted one by one may print a stretch that no witness
        # reads (John 14:7 'ἂν καὶ·' — a clause without its verb). Such a run is decided as a whole.
        for _ in range(2 if safety_nets else 0):
            run_fix = self._attested_run_fix(core, forced, cv)
            if not run_fix:
                break
            for idx, key in run_fix["keys"].items():
                forced[idx] = key
                forced_notes[idx] = run_fix["note"]
                forced_conf[idx] = run_fix["conf"]
                self._forced_canon[idx] = "alignment: attested combination"
            core = self._adjudicate_core(language, cv, forced, forced_notes, credit_counts)

        chosen_tokens = core["tokens"]
        apparatus_items: List[ApparatusItem] = core["apparatus"]
        disregarded_items: List[DisregardedItem] = core["disregarded"]
        rationale_notes: List[str] = core["notes"]
        unit_confs: List[float] = core["confidences"]

        for ext_note in cv.external_apparatus:
            rationale_notes.append(f"Reference apparatus (SBLGNT): {ext_note}")

        if language == "greek":
            chosen_tokens = [self._transliterate_token(t, cv) for t in chosen_tokens]
        critical_line = join_words([t for t in chosen_tokens if t], language)
        verse_confidence = 1.0
        for c in unit_confs:
            verse_confidence *= c
        verse_analysis: List[Dict[str, Any]] = []

        if verse_item:
            apparatus_items.insert(0, verse_item)
            rationale_notes.insert(0, verse_note)
            verse_confidence *= verse_conf
            if bracket and critical_line:
                critical_line = f"{DOUBTFUL_OPEN}{critical_line}{DOUBTFUL_CLOSE}"
                for item in apparatus_items[1:]:
                    item.word_index = -1  # positions shift inside the brackets; adopt by hand
        verse_confidence = round(max(0.0, min(0.99, verse_confidence)), 3)

        word_units = [a for a in apparatus_items if a.kind == "word"]
        if unit_confs or verse_item:
            calibrated = language == "greek" and getattr(cv, "testament", "") == "NT"
            basis = (
                "calibrated on the Greek NT (probability that a modern critical edition agrees, fitted with a whole "
                "stream of witnesses held out)" if calibrated else
                "not calibrated for this corpus (same formula as the Greek NT; read it as a relative measure)"
            )
            n_rule = core.get("rule_repairs", 0)
            n_forced = len(forced)
            parts = [f"{len(unit_confs)} unit confidence(s)"]
            if n_rule:
                parts.append(f"{n_rule} of them digitisation repairs counted at 90 %")
            if n_forced:
                parts.append(f"{n_forced} of them word-conservation repairs scored by presence × position (heuristic)")
            two_way = sum(1 for a in word_units if len(a.lemma_witnesses) == 1 and len(a.variants) == 1 and len(a.variants[0]["witnesses"]) == 1)
            if verse_confidence < 0.99 or word_units or verse_item:
                verse_analysis.append({
                    "canon": "confidence",
                    "note": (
                        f"Verse confidence {verse_confidence:.0%} = product of " + "; ".join(parts)
                        + (" × verse presence" if verse_item else "") + f"; {basis}."
                        + (f" {two_way} unit(s) are one witness against one, where any choice is weakly supported." if two_way else "")
                    ),
                    "favours": "neither",
                    "reading": "",
                    "strength": "info",
                    "key": "",
                })

        if cv.witness_refs:
            rationale_notes.append(
                "Versification: " + "; ".join(f"{s} numbers this verse {r}" for s, r in sorted(cv.witness_refs.items())) + " (re-aligned by content)."
            )
        if cv.fragmentary_witnesses:
            rationale_notes.append(f"Lacunose in this verse (omissions not counted): {', '.join(cv.fragmentary_witnesses)}.")

        witness_list = ", ".join(cv.witness_texts.keys())
        if not apparatus_items and not disregarded_items and not rationale_notes:
            rationale = f"Unanimous witness agreement across {witness_list} ({len(cv.witness_texts)} admitted witnesses; zero substantive divergence)."
        elif not apparatus_items:
            reasons = "; ".join(sorted({d.reason for d in disregarded_items}))
            rationale = f"Substantively unanimous across {witness_list}." + (f" Normalised {len(disregarded_items)} surface variation(s) ({reasons})." if disregarded_items else "")
            if rationale_notes:
                rationale += " " + " ".join(rationale_notes)
        else:
            rationale = " ".join(rationale_notes)
            if disregarded_items:
                rationale += f" Also normalised {len(disregarded_items)} orthographic/surface variation(s)."

        return VerseAdjudication(
            verse=cv.verse,
            critical_text=critical_line,
            confidence=verse_confidence,
            decision_source=self.display_name,
            apparatus=apparatus_items,
            disregarded=disregarded_items,
            rationale=rationale,
            analysis=verse_analysis,
        )

    def _attested_run_fix(self, core: Dict[str, Any], forced: Dict[int, str], cv: CollatedVerse
                          ) -> Optional[Dict[str, Any]]:
        """The first run of neighbouring variation units (no agreed word between them, at most five)
        whose separately chosen readings no witness reads together, or None. The run is then decided
        as a whole: each witness's own combination is weighed by edition family and the heaviest is
        printed. Units already forced or repaired as digitisation slips are left alone."""
        groups, chosen, noise = core["groups"], core["chosen_keys"], core.get("noise_slots", set())
        units = sorted(i for i, g in groups.items() if len(g) > 1 and i not in noise)
        runs: List[List[int]] = []
        for i in units:
            if runs and i == runs[-1][-1] + 1:
                runs[-1].append(i)
            else:
                runs.append([i])
        for run in runs:
            if len(run) < 2 or len(run) > 5 or any(i in forced for i in run):
                continue
            wkey = {i: {s: g[1] for g in groups[i] for s in g[2]} for i in run}
            rep = {i: {g[1]: g[3] for g in groups[i]} for i in run}
            sigla = set.intersection(*(set(wkey[i]) for i in run))  # witnesses voting in every unit
            if not sigla or any(all(wkey[i][s] == chosen.get(i) for i in run) for s in sigla):
                continue
            combos: Dict[Tuple[str, ...], List[str]] = {}
            for s in sorted(sigla):
                combos.setdefault(tuple(wkey[i][s] for i in run), []).append(s)

            def weigh(sg: List[str]) -> float:
                # RP2018 and TR share their errors: counted as one stream here, as in the confidence model
                w = self._fam(sg, cv)
                byz = [s for s in sg if stream_of(s).startswith("Byzantine")]
                if len(byz) > 1:
                    w -= sum(sorted(cv.witness_weights.get(s, 0.0) for s in byz)[:-1])
                return w

            ranked = sorted(((weigh(sg), combo, sg) for combo, sg in combos.items()), key=lambda t: (-t[0], t[1]))
            total = sum(t[0] for t in ranked)
            best_w, best, best_sigla = ranked[0]
            keys = {i: k for i, k in zip(run, best) if k != chosen.get(i)}
            share = round(best_w / total, 3) if total else 0.0  # computed once, used in the note and the score
            if not keys or not total or share < 0.3:
                continue
            if all(stream_of(s).startswith("Byzantine") for s in best_sigla):
                continue  # never replace the vote's text by a Byzantine-only wording

            def show(i: int, k: Optional[str]) -> str:
                return "(om.)" if not k or k == "om." else strip_punct(rep[i].get(k, k))

            hybrid = " ".join(show(i, chosen.get(i)) for i in run)
            note = (f"Decided together with the neighbouring unit(s): voted one by one these units would print "
                    f"'{hybrid}', which no witness reads as a whole; printed instead the wording of "
                    f"{', '.join(best_sigla)} ({share:.0%} of the weight of the witnesses' own combinations)")
            return {"keys": keys, "note": note, "conf": share}
        return None

    def _conservation_fix(self, core: Dict[str, Any], counts: Dict[str, Counter], forced: Dict[int, str],
                          cv: CollatedVerse, language: str = "greek", deficit: bool = True
                          ) -> Optional[Tuple[int, str, str, float]]:
        """One repair of the unit-by-unit text, or None. Words are compared by a spelling-tolerant key
        (ἐπίσταται = ἐφίσταται, Ἰερειχώ = Ἰεριχώ), so a spelling difference never counts as a missing
        or extra word.

        1. Deficit (Greek NT only): a word that a family-weighted majority of the complete witnesses
           has n times must appear n times — unless a unit already decided against it on the
           evidence of witnesses that really lack the word (a deliberate choice, e.g. the shorter
           reading). Otherwise the word's support was split between two positions by the alignment
           (Matt 20:30 κύριε at two places, each outvoted), and it is printed once, at the heavier
           position. A position backed by one witness only is used only when the word itself is
           near-certain (≥80 % of the weight has it), and never a singular reading of B or א.
        2. Excess (every language): a content word may not appear more often than in any single
           witness (a displaced phrase adopted at both positions). Units decided by an OCR or
           dittography repair are never reopened."""
        if len(counts) < 2:
            return None
        ck = lambda key: [] if key == "om." else [_conservation_key(w, language) for w in key.split() if w]  # noqa: E731
        crit = Counter(w for key in core["chosen_keys"].values() for w in ck(key))
        vocab = set().union(*counts.values())
        total = self._fam(list(counts), cv)
        noise = core.get("noise_slots", set())
        needs: Dict[str, int] = {}
        for k in vocab:
            need = 0
            for n in range(1, max(c[k] for c in counts.values()) + 1):
                if self._fam([s for s, c in counts.items() if c[k] >= n], cv) > 0.5 * total:
                    need = n
                else:
                    break
            needs[k] = need

        def shown(k: str) -> str:
            """A real spelling of the word for the note (never the internal comparison key)."""
            forms = [strip_punct(w) for groups in core["raw_groups"].values() for _w, _g, _s, rep in groups
                     for w in (rep or "").split()
                     if _conservation_key(canonical_compare_key(strip_punct(w), language), language) == k]
            marked = [f for f in forms if any(unicodedata.combining(c) for c in unicodedata.normalize("NFD", f))]
            return (marked or forms or [k])[0]

        def acceptable(gkey: str, chosen: str) -> bool:
            """Swapping ``chosen`` for ``gkey`` may only add words that are themselves missing and only
            drop words that stay at least as frequent as the majority has them (so "ὁ βασιλεὺς" is
            never forced over the adopted vocative βασιλεῦ just to restore ὁ), and must change more
            than spelling."""
            new, old = Counter(ck(gkey)), Counter(ck(chosen))
            if new == old:
                return False
            added, dropped = new - old, old - new
            return (all(needs.get(w, 0) >= crit[w] + n for w, n in added.items())
                    and all(crit[w] - n >= needs.get(w, 0) for w, n in dropped.items()))

        for k in (sorted(vocab) if deficit else []):
            need = needs[k]
            if need <= crit[k]:
                continue
            having = [s for s, c in counts.items() if c[k] >= need]
            lacking = [s for s, c in counts.items() if c[k] < need]
            w_having = self._fam(having, cv)
            presence = w_having / max(total, 1e-9)
            deliberate = False
            for idx, groups in core["raw_groups"].items():
                k_sigla = [s for _w, gkey, sigla, _r in groups if k in ck(gkey) for s in sigla]
                if not k_sigla or core["chosen_keys"].get(idx, "om.") != "om." and k in ck(core["chosen_keys"][idx]):
                    continue
                against = [s for _w, gkey, sigla, _r in groups if k not in ck(gkey) for s in sigla if s in lacking]
                # The unit weighed most of the word's witnesses, and the witnesses that truly lack the
                # word outweigh all that have it (with the shorter-reading bonus): a real decision, not a
                # split caused by alignment (Mark 3:14: Sinaiticus has the clause in the next unit).
                if (self._fam([s for s in k_sigla if s in having], cv) > 0.5 * w_having
                        and self._fam(against, cv) + LECTIO_BREVIOR_BONUS >= w_having):
                    deliberate = True
                    break
            if deliberate:
                continue
            best = None
            for idx, groups in core["raw_groups"].items():
                if idx in forced or idx in noise:
                    continue
                chosen = core["chosen_keys"].get(idx, "om.")
                cur = ck(chosen).count(k)
                for w, gkey, sigla, _rep in groups:
                    if gkey == "om." or ck(gkey).count(k) <= cur or not acceptable(gkey, chosen):
                        continue
                    if len(set(sigla)) == 1 and (sigla[0] in DIPLOMATIC_MSS or presence < 0.8):
                        continue
                    if best is None or w > best[0]:
                        best = (w, idx, gkey)
            if best:
                position = min(1.0, best[0] / max(w_having, 1e-9))
                conf = round(min(0.99, presence * (0.5 + 0.5 * position)), 3)
                return best[1], best[2], (
                    f"Restored by verse-level word conservation: witnesses with {presence:.0%} of the weight have "
                    f"'{shown(k)}' {need}× in this verse, but their support is split between positions, so the unit-by-unit "
                    f"vote printed it {crit[k]}×. Printed at the better-supported position; its place is uncertain."
                ), conf
        for k in sorted(vocab):
            most = max(c[k] for c in counts.values())
            if len(k) < 4 or crit[k] <= most:
                continue
            best = None
            for idx, groups in core["raw_groups"].items():
                if idx in forced or idx in noise:
                    continue
                chosen = core["chosen_keys"].get(idx, "om.")
                cur = ck(chosen).count(k)
                for w, gkey, sigla, _rep in groups:
                    if (cur > 0 and (gkey == "om." or ck(gkey).count(k) < cur) and acceptable(gkey, chosen)
                            and (best is None or w > best[0])):
                        best = (w, idx, gkey)
            if best:
                return best[1], best[2], (
                    f"Duplicate removed by verse-level word conservation: no witness has '{shown(k)}' more than {most}× in "
                    f"this verse, but the unit-by-unit choice printed it {crit[k]}× (a displaced phrase counted twice)."
                ), 0.9
        return None

    def _adjudicate_core(self, language: str, cv: CollatedVerse, forced: Dict[int, str],
                         forced_notes: Dict[int, str], counts: Dict[str, Counter]) -> Dict[str, Any]:
        chosen_tokens: List[str] = []
        apparatus_items: List[ApparatusItem] = []
        disregarded_items: List[DisregardedItem] = []
        rationale_notes: List[str] = []
        confidences: List[float] = []
        chosen_keys: Dict[int, str] = {}
        groups_by_slot: Dict[int, List[Tuple[float, str, List[str], str]]] = {}
        raw_groups_by_slot: Dict[int, List[Tuple[float, str, List[str], str]]] = {}
        noise_slots: set = set()
        rule_repairs = 0

        def word_pos() -> int:
            return sum(len(t.split()) for t in chosen_tokens)

        def key_of(slot: VariationSlot, raw: str) -> str:
            if raw == "om.":
                return "om."
            return slot.form_keys.get(raw) or " ".join(canonical_compare_key(t, language) for t in raw.split())

        for idx, slot in enumerate(cv.slots):
            is_start = not chosen_tokens
            prev_key = canonical_compare_key(chosen_tokens[-1], language) if chosen_tokens else ""
            slot_sigla = [s for sigs in slot.raw_forms.values() for s in sigs]

            if slot.kind == "unanimous":
                raw_form = next(iter(slot.raw_forms))
                chosen_keys[idx] = key_of(slot, raw_form)
                if raw_form != "om.":
                    norm_tok = self._choose_best_surface_form(slot, slot_sigla, cv, is_start, language)
                    if norm_tok and norm_tok != raw_form:
                        disregarded_items.append(DisregardedItem(
                            slot_index=idx, kept_form=norm_tok, disregarded_forms=[raw_form],
                            witnesses=slot_sigla,
                            reason="Diplomatic uncial orthography normalised to standard critical form",
                        ))
                    chosen_tokens.append(norm_tok or raw_form)
                continue

            if slot.kind == "orthographic_noise":
                kept = self._choose_best_surface_form(slot, slot_sigla, cv, is_start, language)
                other_forms = [f for f in slot.raw_forms if f != kept and f != "om." and strip_punct(f) != strip_punct(kept)]
                if not other_forms:
                    other_forms = [f for f in slot.raw_forms if f != kept and f != "om."]
                if other_forms:
                    disregarded_items.append(DisregardedItem(
                        slot_index=idx, kept_form=kept, disregarded_forms=other_forms,
                        witnesses=sorted({s for f in other_forms for s in slot.raw_forms.get(f, [])}),
                        reason=slot.notes or "Orthographic / punctuation surface variation",
                    ))
                chosen_keys[idx] = canonical_compare_key(kept, language) if kept else "om."
                if kept and " " in strip_punct(kept):
                    chosen_keys[idx] = " ".join(canonical_compare_key(t, language) for t in kept.split())
                if kept:
                    chosen_tokens.append(kept)
                continue

            # Disagreement *inside* one edition family (e.g. the Clementine USFX vs the Saints copy of
            # the same Clementine) is a digital-encoding difference, not a textual variant.
            slot_families = {(cv.witness_families or {}).get(s) or _edition_family(s) for s in slot_sigla}
            if len(slot_families) == 1 and len(slot_sigla) > 1:
                base_forms = [f for f, sigs in slot.raw_forms.items() if cv.base_siglum in sigs]
                keep_raw = base_forms[0] if base_forms else max(slot.raw_forms, key=lambda f: self._fam(slot.raw_forms[f], cv))
                if (keep_raw != "om." and "om." in slot.raw_forms and cv.base_siglum in slot.raw_forms.get(keep_raw, [])
                        and " " not in keep_raw
                        and self._base_adjacent_dup(cv, cv.base_siglum, key_of(slot, keep_raw), slot_sigla, language)):
                    keep_raw = "om."
                kept = "" if keep_raw == "om." else self._choose_best_surface_form(slot, slot.raw_forms[keep_raw], cv, is_start, language)
                chosen_keys[idx] = key_of(slot, keep_raw)
                if kept:
                    chosen_tokens.append(kept)
                disregarded_items.append(DisregardedItem(
                    slot_index=idx, kept_form=kept or "om.",
                    disregarded_forms=[f for f in slot.raw_forms if f != keep_raw],
                    witnesses=sorted({s for f, sigs in slot.raw_forms.items() if f != keep_raw for s in sigs}),
                    reason="Encoding difference between digital copies of the same printed edition (not a textual variant)",
                ))
                continue

            # Substantive: unite orthographic sub-variants by canonical key before weighing.
            key_groups: Dict[str, List[Tuple[str, List[str]]]] = {}
            for disp, sigla in slot.readings.items():
                ckey = slot.form_keys.get(disp) or ("om." if disp == "om." else " ".join(canonical_compare_key(t, language) for t in disp.split()))
                key_groups.setdefault(ckey, []).append((disp, sigla))
            key_groups, sister_note = self._sister_copy_split(key_groups, cv)
            if sister_note:
                disregarded_items.append(DisregardedItem(slot_index=idx, **sister_note))
            key_groups = self._pool_spellings(key_groups, cv, language)
            for kept_rep, forms, sigs in getattr(self, "_last_pool_merges", []):
                disregarded_items.append(DisregardedItem(
                    slot_index=idx, kept_form=kept_rep, disregarded_forms=forms, witnesses=sigs,
                    reason=(f"Spelling variant pooled before the vote with the reading '{strip_punct(kept_rep)}' (same word, "
                            "different spelling); whether that reading was adopted is shown in the apparatus"),
                ))

            def score_groups(groups: Dict[str, List[Tuple[str, List[str]]]]) -> List[Tuple[float, str, List[str], str]]:
                out: List[Tuple[float, str, List[str], str]] = []
                for ckey, members in groups.items():
                    group_sigla = [s for _, sigs in members for s in sigs]
                    if not group_sigla:
                        continue
                    w_sum = self._fam(group_sigla, cv)
                    if (
                        ckey == "om." and language in ("greek", "latin")
                        and any(cv.witness_weights.get(s, 0.0) >= LECTIO_BREVIOR_MIN_WEIGHT for s in group_sigla)
                    ):
                        w_sum += LECTIO_BREVIOR_BONUS
                    # (Accent/breathing defects affect only which spelling is printed, never which
                    # reading wins: see _choose_best_surface_form.)
                    if language == "greek" and ckey in KNOWN_LEIPZIG_OCR_TYPOS:
                        w_sum -= 0.75
                    # shown in an accented edition's spelling when one has it (ἐγνώκατε, not εγνωκατε)
                    rep = sorted(members, key=lambda m: ("\u0305" in m[0], not _has_accent_marks(m[0]),
                                                         -self._fam(m[1], cv), m[0]))[0][0]
                    out.append((w_sum, ckey, group_sigla, rep))
                out.sort(key=lambda g: (-g[0], g[1]))
                return out

            raw_scored = score_groups(key_groups)
            raw_groups_by_slot[idx] = raw_scored
            credit_note = ""
            if True:  # also for forced units, so the apparatus does not list a credited witness as omitting
                dropped, credit_note = self._omission_credit(key_groups, counts, cv, idx, language)
                if dropped:
                    key_groups = dict(key_groups)
                    key_groups["om."] = [(d, [s for s in sigs if s not in dropped]) for d, sigs in key_groups["om."]]
                    key_groups["om."] = [(d, sigs) for d, sigs in key_groups["om."] if sigs]
                    if not key_groups["om."]:
                        del key_groups["om."]
            scored = score_groups(key_groups) if credit_note else list(raw_scored)
            groups_by_slot[idx] = scored

            # Hook for subclasses (Textual Analysis Brain): internal evidence may adjust group
            # weights before the reading is chosen, and returns findings for the apparatus.
            deltas, findings = self._internal_evidence(language, cv, slot, idx, scored, chosen_tokens) if len(scored) > 1 else ({}, [])
            if deltas:
                scored = [(w + deltas.get(k, 0.0), k, sg, r) for (w, k, sg, r) in scored]
                scored.sort(key=lambda g: (-g[0], g[1]))
            if idx in forced:
                pick = next((g for g in scored if g[1] == forced[idx]), None)
                if pick is not None:
                    scored = [pick] + [g for g in scored if g is not pick]
            win_weight, win_key, win_sigla, win_rep = scored[0]

            noise_reason = ""
            donor_repair = False
            keys = {g[1] for g in scored}
            sentence_start = not chosen_tokens or bool(re.search(r"[.;·;!?][”’»]*$", chosen_tokens[-1]))
            self._clause_context = chosen_tokens[-8:]  # the clause so far (subjunctive markers)
            if language == "greek" and idx not in forced:
                ocr_reason = self._probable_transcription_error(
                    scored, cv, slot, sentence_start, chosen_tokens[-1] if chosen_tokens else "")
                if ocr_reason:
                    scored = [scored[1], scored[0]]
                    win_weight, win_key, win_sigla, win_rep = scored[0]
                    noise_reason = ocr_reason
                    donor_repair = True
            if language == "greek" and len(keys) == 2:
                for bad_k, good_k in KNOWN_LEIPZIG_OCR_TYPOS.items():
                    if keys == {bad_k, good_k} and win_key == good_k:
                        noise_reason = f"Upstream digital OCR character error ('{bad_k}' for '{good_k}')"
            if "om." in keys and len(keys) == 2 and not prev_key:
                # At the start of a verse, compare with the following word instead ("καὶ καὶ τὸ …").
                prev_key = self._next_agreed_key(cv, idx, language)
            if "om." in keys and len(keys) == 2 and idx not in forced and len(next(k for k in keys if k != "om.").split()) >= 2:
                # A phrase repeated by one edition family only (Swete's Gen 3:1 "τῶν θηρίων τῶν θηρίων"):
                # the added words are the very words that stand next to them.
                other_key = next(k for k in keys if k != "om.")
                added = other_key.split()
                other_sigla = [s for g in scored if g[1] == other_key for s in g[2]]
                om_sigla = [s for g in scored if g[1] == "om." for s in g[2]]
                before = [canonical_compare_key(t, language) for t in " ".join(chosen_tokens).split()][-len(added):]
                after = self._next_keys(cv, idx, language, len(added))
                if (_family_count(other_sigla, cv.witness_families) == 1 and om_sigla
                        and (before == added or after == added)):
                    scored = [next(g for g in scored if g[1] == "om."), next(g for g in scored if g[1] == other_key)]
                    win_weight, win_key, win_sigla, win_rep = scored[0]
                    noise_reason = (f"Probable dittography in {', '.join(other_sigla)}: the added words repeat "
                                    f"the neighbouring '{' '.join(added)}'")
            if "om." in keys and len(keys) == 2 and prev_key and idx not in forced and not noise_reason:
                other_key = next(k for k in keys if k != "om.")
                other_sigla = [s for g in scored if g[1] == other_key for s in g[2]]
                one_family = _family_count(other_sigla, cv.witness_families) == 1
                if other_key == prev_key and one_family and win_key == "om.":
                    noise_reason = f"Scribal adjacent-word dittography (repeated '{prev_key}' in one witness only)"
                elif (
                    other_key == prev_key and one_family and win_key == other_key
                    and cv.lexicon is not None
                    and (cv.lexicon.repeat_families.get(other_key, 0) <= 1 or other_key in NEVER_DOUBLED_GREEK)
                ):
                    # The doubling is found in one edition family only, and nowhere else in the whole
                    # corpus does any other edition double this word: an OCR/scribal dittography, even
                    # though that family outweighs the others (e.g. Swete's "ἡμέρα ἡμέρα ἕκτη").
                    scored = [next(g for g in scored if g[1] == "om."), next(g for g in scored if g[1] == other_key)]
                    win_weight, win_key, win_sigla, win_rep = scored[0]
                    noise_reason = (
                        f"Probable dittography in {', '.join(other_sigla)}: no other edition in the corpus doubles "
                        f"'{other_key}'"
                    )
            nxt = cv.slots[idx + 1] if idx + 1 < len(cv.slots) else None
            next_key = (key_of(nxt, next(iter(nxt.raw_forms))) if nxt is not None and nxt.kind != "substantive_variant"
                        and len({key_of(nxt, f) for f in nxt.raw_forms}) == 1 else "")
            next_raw = next(iter(nxt.raw_forms)) if next_key else ""
            win_raw = next((f for f, sigs in slot.raw_forms.items() if set(sigs) & set(win_sigla) and f != "om."), "")
            # The doubled copy matches the neighbouring word by key, unless both spellings are common
            # real words that differ in breathing or accent (οὗ is not οὐ, Ps 31:2; a damaged copy such
            # as ἐπτὰ for ἑπτὰ still counts), and the other reading must be another word, not a
            # spelling of it (κᾀγὼ / κἀγὼ, 1 Sam 12:2).
            nb_raw = chosen_tokens[-1] if chosen_tokens and win_key == prev_key else next_raw
            lexd = cv.lexicon
            both_common = (lexd is not None and _spelt(win_raw) != _spelt(nb_raw)
                           and lexd.form_count(strip_punct(win_raw)) >= 20 and lexd.form_count(strip_punct(nb_raw)) >= 20)
            same_word = bool(win_raw) and not both_common
            other_raw = (next((f for f, sigs in slot.raw_forms.items() if set(sigs) & set(scored[1][2]) and f != "om."), "")
                         if len(scored) == 2 else "")
            # The other edition repeats its own neighbouring word there too, spelt its own way (Gen 11:27
            # 'Θάρα· Θάρα' against Brenton's 'Θάῤῥα· Θάῤῥα'): a genuine repetition, not a dittography.
            other_repeats = False
            if len(scored) == 2 and win_key in (prev_key, next_key) and scored[1][1] != "om.":
                step = -1 if win_key == prev_key else 1
                other_sigs = set(scored[1][2])
                j = idx + step
                while 0 <= j < len(cv.slots):
                    nb_form = next((f for f, sigs in cv.slots[j].raw_forms.items() if f != "om." and set(sigs) & other_sigs), None)
                    if nb_form is not None:
                        other_repeats = key_of(cv.slots[j], nb_form) == scored[1][1]
                        break
                    j += step
            if (language == "greek" and len(scored) == 2 and idx not in forced and not noise_reason and same_word
                    and not other_repeats
                    and getattr(cv, "testament", "") != "NT" and win_key in (prev_key, next_key) and " " not in win_key
                    and win_key != "om." and scored[1][1] not in ("om.", prev_key, next_key) and " " not in scored[1][1]
                    and _no_subscript_key(other_raw) != _no_subscript_key(win_raw)
                    and _family_count(win_sigla, cv.witness_families) == 1):
                # Dittography with loss: one edition family prints the previous word again where the
                # other prints a different word (Gen 15:3 'σπέρμα, σπέρμα,' for 'σπέρμα, ἔδωκας';
                # Gen 24:40 'καὶ καὶ' for 'καὶ λήψῃ'): the doubled copy replaced the lost word.
                doubled, other = win_rep, scored[1]
                scored = [scored[1], scored[0]]
                win_weight, win_key, win_sigla, win_rep = scored[0]
                donor_repair = "punctuation"  # the doubled copy's punctuation belongs to the word it copies
                where = "before" if scored[1][1] == prev_key else "after"
                noise_reason = (f"Probable dittography with loss in {', '.join(scored[1][2])}: "
                                f"'{doubled}' repeats the word {where} it where {', '.join(other[2])} read '{other[3]}'")
            if language == "hebrew" and "om." in keys and win_key != "om." and chosen_tokens and chosen_tokens[-1].startswith("("):
                noise_reason = "Qere (read form) printed after the ketiv; the WLC export carries the ketiv only"

            chosen_keys[idx] = win_key
            if noise_reason:
                kept_surface = "" if win_key == "om." else self._choose_best_surface_form(slot, win_sigla, cv, is_start, language)
                if donor_repair and kept_surface:
                    kept_surface = self._tidy_donor(kept_surface, scored[1], slot, cv, is_start or sentence_start,
                                                    dittography=donor_repair == "punctuation",
                                                    prev_token=chosen_tokens[-1] if chosen_tokens else "")
                    if donor_repair == "punctuation":
                        donor_raw = next((f for f, sigs in slot.raw_forms.items() if set(sigs) & set(win_sigla) and f != "om."), "")
                        tail = re.search(r"[.,;·:!?·]+$", donor_raw)
                        kept_surface = re.sub(r"[.,;·:!?·]+$", "", kept_surface) + (tail.group(0) if tail else "")
                if kept_surface:
                    chosen_tokens.append(kept_surface)
                disregarded_items.append(DisregardedItem(
                    slot_index=idx,
                    kept_form=kept_surface or "om.",
                    disregarded_forms=[g[3] for g in scored[1:]],
                    witnesses=sorted({s for g in scored[1:] for s in g[2]}),
                    reason=noise_reason,
                ))
                # Rule-based repairs of digitisation slips: right about nine times in ten when checked.
                confidences.append(0.99 if language == "hebrew" else 0.9)
                noise_slots.add(idx)
                if language != "hebrew":
                    rule_repairs += 1
                continue

            if len(scored) == 1:
                # Every vote that disagreed was a misaligned witness: nothing left to weigh.
                surface = "" if win_key == "om." else (
                    self._choose_best_surface_form(slot, win_sigla, cv, is_start, language) or normalize_critical_token(win_rep, is_start, language))
                if surface:
                    chosen_tokens.append(surface)
                if credit_note:
                    disregarded_items.append(DisregardedItem(
                        slot_index=idx, kept_form=surface or "om.", disregarded_forms=["om."],
                        witnesses=sorted({s for g in raw_scored if g[1] == "om." for s in g[2]}),
                        reason=credit_note,
                    ))
                continue

            conf = calibrated_unit_confidence([(k, sg, r) for (_w, k, sg, r) in scored], win_key, cv, language)
            if idx in forced and idx in getattr(self, "_forced_conf", {}):
                conf = self._forced_conf[idx]  # presence × position, not this unit's minority vote
            confidences.append(conf)
            start_word = word_pos()
            if win_key != "om.":
                surface = self._choose_best_surface_form(slot, win_sigla, cv, is_start, language) or normalize_critical_token(win_rep, is_start, language)
                if language == "greek" and any(_latin_damaged(t) for t in surface.split()):
                    fixed = _fix_latin_letters(surface, slot, language, cv.lexicon)
                    if fixed != surface:
                        disregarded_items.append(DisregardedItem(
                            slot_index=idx, kept_form=fixed, disregarded_forms=[surface], witnesses=win_sigla,
                            reason="OCR damage: Latin letters inside a Greek word, repaired from the closest word in the unit",
                        ))
                        surface = fixed
                if language == "greek" and len(scored) > 1 and " " in win_key:
                    surface, slip_note = self._repair_slip_words(
                        surface, win_key, win_sigla, scored[1], slot, cv, chosen_tokens[-1] if chosen_tokens else "")
                    if slip_note:
                        disregarded_items.append(DisregardedItem(
                            slot_index=idx, kept_form=surface, disregarded_forms=[win_rep],
                            witnesses=win_sigla, reason=slip_note,
                        ))
                first_key = win_key.split()[0] if win_key.split() else ""
                first_word = unicodedata.normalize("NFD", strip_punct(surface.split()[0]).lower()) if surface.split() else ""
                clause_initial = first_key in _CLAUSE_INITIAL and not (
                    first_key == "η" and ("\u0342" in first_word or "\u0345" in first_word))  # ᾖ / ἦ are verbs, not ἤ / ἡ
                fams_ = cv.witness_families or {}
                # Words the base copy skipped but its own sister copies print: the mark goes where the sister copy has
                # it — after the previous word if it prints one there (Josh 18:28 'Γαβαωθιαρείμ, πόλεις'), else after
                # the restored words (Josh 10:35 'ἐφόνευσεν αὐτὴν … ἐφόνευσαν, ὃν τρόπον').
                sister_supplied = False
                witnesses_continue = False
                if chosen_tokens and chosen_tokens[-1].split() and surface.split():
                    prev_k = canonical_compare_key(strip_punct(chosen_tokens[-1].split()[-1]), language)
                    first_k = canonical_compare_key(strip_punct(surface.split()[0]), language)
                    for s in win_sigla:
                        if s == cv.base_siglum or not fams_.get(s) or fams_.get(s) != fams_.get(cv.base_siglum):
                            continue
                        toks = (cv.witness_texts.get(s) or "").split()
                        sister_supplied = sister_supplied or any(
                            canonical_compare_key(strip_punct(a), language) == prev_k
                            and canonical_compare_key(strip_punct(b), language) == first_k and a != strip_punct(a)
                            for a, b in zip(toks, toks[1:]))
                    if clause_initial and chosen_tokens[-1].endswith(".") and cv.base_siglum in slot.raw_forms.get("om.", []):
                        # If the base edition ends a sentence here only because it omits the following modifier
                        # (Luke 24:3 'τὸ σῶμα. [τοῦ Κυρίου Ἰησοῦ]'), check whether the punctuated editions that
                        # print these words continue without any stop after prev_k.
                        punct_sigs = [s for s in win_sigla if s not in DIPLOMATIC_MSS and s != cv.base_siglum]
                        cont_hits = 0
                        stop_hits = 0
                        for s in punct_sigs:
                            toks = (cv.witness_texts.get(s) or "").split()
                            for a, b in zip(toks, toks[1:]):
                                if (canonical_compare_key(strip_punct(a), language) == prev_k
                                        and canonical_compare_key(strip_punct(b), language) == first_k):
                                    if re.search(r"[.;··;:!?]$", a):
                                        stop_hits += 1
                                    else:
                                        cont_hits += 1
                        witnesses_continue = cont_hits > 0 and stop_hits == 0
                    if (len(chosen_tokens) >= 2 and chosen_tokens[-2].endswith(".")
                            and cv.base_siglum in slot.raw_forms.get("om.", [])
                            and canonical_compare_key(strip_punct(chosen_tokens[-1]), language) in ("και", "η", "ουδε", "μηδε", "τε")):
                        # Mark 7:24: SBLGNT's 'Τύρου. καὶ [εἰσελθὼν]' aligned its 'καὶ' with 'Τύρου καὶ Σιδῶνος. Καὶ',
                        # leaving a premature period on 'Τύρου.' before 'καὶ Σιδῶνος.'.
                        prev2_k = canonical_compare_key(strip_punct(chosen_tokens[-2].split()[-1]), language)
                        conj_k = canonical_compare_key(strip_punct(chosen_tokens[-1]), language)
                        punct_sigs = [s for s in win_sigla if s not in DIPLOMATIC_MSS and s != cv.base_siglum]
                        no_stop_3 = 0
                        has_stop_3 = 0
                        for s in punct_sigs:
                            toks = (cv.witness_texts.get(s) or "").split()
                            for a, b, c in zip(toks, toks[1:], toks[2:]):
                                if (canonical_compare_key(strip_punct(a), language) == prev2_k
                                        and canonical_compare_key(strip_punct(b), language) == conj_k
                                        and canonical_compare_key(strip_punct(c), language) == first_k):
                                    if re.search(r"[.,;··;:!?]$", a):
                                        has_stop_3 += 1
                                    else:
                                        no_stop_3 += 1
                        if no_stop_3 > 0 and has_stop_3 == 0:
                            chosen_tokens[-2] = chosen_tokens[-2][:-1]
                if (chosen_tokens and cv.base_siglum and cv.base_siglum in slot.raw_forms.get("om.", [])
                        and language != "hebrew" and (not clause_initial or witnesses_continue) and not sister_supplied):
                    # The base edition lacks these words, so its clause-final punctuation on the previous
                    # word belongs after them ("Ἰησοῦ χριστοῦ. Υἱοῦ θεοῦ" → "Ἰησοῦ χριστοῦ Υἱοῦ θεοῦ.").
                    # Not when the added words open a clause (καί, ἤ, an article, πῶς…): then the
                    # punctuation stays where it is. Speech-introducing raised dots and colons stay too.
                    # an enclitic pronoun (σου, μου, αὐτοῦ…) belongs before any clause mark, raised dot included
                    marks = r"[.··;;:,]+$" if first_key in _ENCLITIC_PRONOUNS and len(win_key.split()) == 1 else r"[.,;;]+$"
                    m = re.search(marks, chosen_tokens[-1])
                    if m:
                        chosen_tokens[-1] = chosen_tokens[-1][: m.start()]
                        surface = re.sub(r"[.··;;:,!?]+$", "", surface) + m.group(0)
                if language == "greek" and chosen_tokens and surface:
                    prev_tok = chosen_tokens[-1]
                    w0 = strip_punct(surface.split()[0]) if surface.split() else ""
                    if (w0 and w0[:1].isupper() and not w0.isupper()
                            and not re.search(r"[.··;;:!?][”’»]*$", prev_tok)
                            and not first_key.startswith(NOMINA_SACRA_STEMS)
                            and first_key not in _REVERENTIAL_CAPITALS):
                        # Lowercase a non-name speech/sentence capital when an earlier word was inserted
                        # after the stop (Mark 8:21 'αὐτοῖς· Πῶς Οὔπω' → 'Πῶς οὔπω') or when the base
                        # edition ended with a comma instead of a full stop (Luke 24:45 'γραφάς, Καὶ' → 'γραφάς, καὶ').
                        base_omits_here = bool(cv.base_siglum and cv.base_siglum in slot.raw_forms.get("om.", []))
                        base_had_stop_before = False
                        if cv.base_siglum and not base_omits_here:
                            btoks = (cv.witness_texts.get(cv.base_siglum) or "").split()
                            for bi, bt in enumerate(btoks):
                                if canonical_compare_key(strip_punct(bt), language) == first_key and strip_punct(bt)[:1].isupper():
                                    if bi == 0 or re.search(r"[.··;;:!?][”’»]*$", btoks[bi - 1]):
                                        base_had_stop_before = True
                                        break
                        no_punct_prev = not re.search(r"[,.;··;:!?][”’»]*$", prev_tok)
                        comma_kai = prev_tok.endswith(",") and base_omits_here and first_key == "και"
                        if ((no_punct_prev and base_had_stop_before) or comma_kai) and any(
                            strip_punct(wt)[:1].islower() and canonical_compare_key(strip_punct(wt), language) == first_key
                            for s, wtxt in cv.witness_texts.items() if s not in DIPLOMATIC_MSS
                            for wt in wtxt.split()
                        ):
                            surface = surface[:1].lower() + surface[1:]
                chosen_tokens.append(surface)
                lemma_display = strip_punct(surface) or surface
            else:
                lemma_display = "om."
            n_words = word_pos() - start_word

            variants_out = []
            for w_sum, ckey, g_sigla, g_rep in scored[1:]:
                display, adopt = self._display_and_adopt_forms(g_rep, ckey, cv)
                variants_out.append({"reading": display, "adopt_text": adopt, "witnesses": g_sigla, "weight_sum": round(w_sum, 2)})
            if variants_out:
                var_summary = "; ".join(f"{v['reading']} ({', '.join(v['witnesses'])})" for v in variants_out)
                prefix = (f"[{slot.notes}] " if slot.notes else "")
                if idx in forced_notes:
                    prefix += f"[{forced_notes[idx]}] "
                if credit_note:
                    prefix += f"[{credit_note}] "
                note = (
                    prefix
                    + f"Adopted '{lemma_display}' [{', '.join(win_sigla)}] (weight {win_weight:.2f}, confidence {conf:.0%}) "
                    f"over {var_summary}."
                )
                unit_findings = list(findings)
                run_forced = getattr(self, "_forced_canon", {}).get(idx) == "alignment: attested combination"
                if conf < 0.5:
                    # The vote counts each edition family once; the confidence model also discounts
                    # editions that share errors (RP2018 and TR) and pools spellings. When the two
                    # disagree the adopted reading is a narrow, uncertain choice: say so.
                    byz_in_lemma = [s for s in win_sigla if stream_of(s).startswith("Byzantine")]
                    rival_w = scored[1][0] if len(scored) > 1 else 0.0
                    if run_forced:
                        why_uncertain = (f"Decided together with its neighbouring units; that wording has only {conf:.0%} "
                                         "of the support of the witnesses' own combinations.")
                    elif idx in forced:
                        why_uncertain = (f"Restored by word conservation with a presence × position score of {conf:.0%}; "
                                         "its place in the verse is uncertain.")
                    elif win_key == "om." and win_weight - rival_w < LECTIO_BREVIOR_BONUS:
                        why_uncertain = (f"The omission was adopted only through the shorter-reading bonus for B / א; its "
                                         f"calibrated support is {conf:.0%}.")
                    elif len(byz_in_lemma) >= 2:
                        why_uncertain = (f"Adopted by the weighted vote, but its calibrated support is only {conf:.0%}: once "
                                         "the dependent editions RP2018 and TR are counted as one, the rival reading is as "
                                         "well or better supported.")
                    else:
                        why_uncertain = (f"Adopted by the weighted vote as the largest group, but its calibrated support is "
                                         f"only {conf:.0%}: the witnesses are divided among {len(scored)} readings and none "
                                         "has a clear majority.")
                    unit_findings.append({
                        "canon": "external: uncertain choice",
                        "note": why_uncertain + " Treat this unit as undecided.",
                        "favours": "neither", "reading": lemma_display, "strength": "weak", "key": win_key,
                    })
                if idx in forced_notes:
                    canon = getattr(self, "_forced_canon", {}).get(idx, "alignment: word conservation")
                    strength = "strong" if conf >= 0.85 else ("moderate" if conf >= 0.5 else "weak")
                    unit_findings.append({"canon": canon, "note": forced_notes[idx],
                                          "favours": "reading", "reading": lemma_display, "strength": strength,
                                          "key": win_key})
                apparatus_items.append(ApparatusItem(
                    slot_index=idx, lemma=lemma_display, lemma_witnesses=win_sigla,
                    variants=variants_out, note=note, word_index=start_word, word_count=n_words,
                    analysis=unit_findings, lemma_key=win_key, confidence=conf,
                    credited_witnesses=sorted(dropped) if credit_note else [],
                ))
                rationale_notes.append(note)

        return {
            "tokens": chosen_tokens,
            "apparatus": apparatus_items,
            "disregarded": disregarded_items,
            "notes": rationale_notes,
            "confidences": confidences,
            "chosen_keys": chosen_keys,
            "groups": groups_by_slot,
            "raw_groups": raw_groups_by_slot,
            "noise_slots": noise_slots,
            "rule_repairs": rule_repairs,
        }

    @staticmethod
    def _base_adjacent_dup(cv: CollatedVerse, base: str, word_key: str, sisters: List[str], language: str = "greek") -> bool:
        """True if ``base`` writes ``word_key`` twice in a row while a sister copy of the same edition writes
        it without that adjacent repetition (a keying dittography such as Josh 6:17 'ἐστὶν ἐστὶν')."""
        if not word_key or " " in word_key:
            return False
        b_keys = [canonical_compare_key(t, language) for t in (cv.witness_texts.get(base) or "").split()]
        if not any(a == word_key and b == word_key for a, b in zip(b_keys, b_keys[1:])):
            return False
        b_count = b_keys.count(word_key)
        for s in sisters:
            if s == base or s not in cv.witness_texts:
                continue
            s_keys = [canonical_compare_key(t, language) for t in (cv.witness_texts.get(s) or "").split()]
            if s_keys.count(word_key) < b_count and not any(a == word_key and b == word_key for a, b in zip(s_keys, s_keys[1:])):
                return True
        return False

    @staticmethod
    def _base_echoes(cv: CollatedVerse, base: str, word_key: str) -> bool:
        """The base copy writes the word right after a word ending in the same letters ('ἄνομος μος', Isa 48:8):
        a keying echo, not a word the other copies lost. A common word is never an echo ('κατὰ τὰ', Gen 10:32)."""
        if cv.lexicon is not None and cv.lexicon.key_count(word_key) >= 20:
            return False
        # Ordinary words can repeat the preceding ending: κατὰ τὰ is not an
        # accidental echo (Gen 10:32). Require a rare fragment, not just shape.
        if len(word_key) < 3 or cv.lexicon is None or cv.lexicon.key_count(word_key) > 1:
            return False
        keys = [canonical_compare_key(t, "greek") for t in (cv.witness_texts.get(base) or "").split()]
        return any(a.endswith(word_key) and b == word_key for a, b in zip(keys, keys[1:]) if a and b)

    def _sister_keep(self, sigs: List[str], key_of_sig: Dict[str, str], form_of_sig: Dict[str, str],
                     outside: set, cv: CollatedVerse) -> Tuple[str, str]:
        """Which reading of one edition's disagreeing digital copies stands for the edition, and why.

        1. the reading another edition shares (an omission shared with another edition does not outweigh one
           word of the base copy: Brenton's joined ἀναμέσον and an OCR copy's lost line, Josh 8:9 'μέσον');
        2. the reading that is another edition's in another spelling (Μαχεὶρ ~ Brenton's Μαχὶρ, 2 Sam 9:5);
        3. words against a gap, when another edition has substantially the same words (a phrase one copy skipped);
        4. not the base copy's form when it occurs nowhere else in the corpus and a sister copy's form, one
           or two letters away, is common (a keying slip: Ἰεδᾶε / Ἰωδᾶε, τὴς / τὴν);
        5. else the base copy, else the heavier copy."""
        base = cv.base_siglum if cv.base_siglum in sigs else ""
        keys = {key_of_sig[s] for s in sigs}
        worded = {k for k in keys if k != "om."}
        if base and key_of_sig[base] == "om." and len(worded) == 1:
            # A damaged pivot can place the other edition's corroborating
            # clause in neighbouring slots (Josh 18:28). Count only words that
            # edition has *in excess of* the base copy, so a word elsewhere in
            # the base cannot license an extra occurrence. Require a phrase
            # and two longer matching words, not a lone particle or OCR tail.
            missing = Counter(next(iter(worded)).split())
            if sum(missing.values()) >= 3:
                base_words = Counter(canonical_compare_key(t, "greek")
                                     for t in cv.witness_texts.get(base, "").split())
                for sig, text in cv.witness_texts.items():
                    if sig in sigs:
                        continue
                    excess = Counter(canonical_compare_key(t, "greek") for t in text.split()) - base_words
                    supported = missing & excess
                    if (2 * sum(supported.values()) >= sum(missing.values())
                            and sum(len(k) >= 5 for k in supported) >= 2):
                        return next(iter(worded)), ("the sister copy's extra phrase is corroborated by another "
                                                    "edition elsewhere in the aligned verse")
        if ("om." in keys and base and key_of_sig[base] != "om." and " " not in key_of_sig[base]
                and self._base_adjacent_dup(cv, base, key_of_sig[base], sigs)):
            bk = key_of_sig[base]
            sister_min = min(
                [canonical_compare_key(t, "greek") for t in (cv.witness_texts.get(s) or "").split()].count(bk)
                for s in sigs if s != base and s in cv.witness_texts
            )
            outside_max = max(
                ([canonical_compare_key(t, "greek") for t in (cv.witness_texts.get(s) or "").split()].count(bk)
                 for s in key_of_sig if s not in sigs and s in cv.witness_texts),
                default=0,
            )
            if outside_max <= sister_min:
                return "om.", f"the base copy repeats '{strip_punct(form_of_sig[base])}' where its sister copies and outside witnesses have it once"
        agree = {key_of_sig[s] for s in sigs if key_of_sig[s] in outside}
        if len(agree) == 1:
            k = next(iter(agree))
            if (k == "om." and base and key_of_sig[base] != "om." and " " not in key_of_sig[base]
                    and not self._base_echoes(cv, base, key_of_sig[base])
                    and not self._base_adjacent_dup(cv, base, key_of_sig[base], sigs)):
                # one word only: Brenton's joined ἀναμέσον / διαπαντὸς leaves Swete's μέσον / παντὸς without a partner;
                # a longer run is more likely the base copy's own verse division (Gen 24:18/19)
                return key_of_sig[base], "the base copy has the word; an omission is no evidence against it"
            if k == "om." and base and key_of_sig[base] == "om.":
                # The other edition only seems to omit: it prints the words in this verse's neighbouring units, and
                # the base copy skipped them (Josh 18:28, a half line). Not a doubling: the base copy lacks them.
                worded = {key_of_sig[s] for s in sigs if key_of_sig[s] != "om."}
                wk = next(iter(worded)).split() if len(worded) == 1 else []

                def share(sig: str) -> float:
                    have = {canonical_compare_key(t, "greek") for t in (cv.witness_texts.get(sig) or "").split()}
                    return sum(1 for w in wk if w in have) / len(wk) if wk else 0.0

                if len(wk) >= 3 and share(base) < 0.6 and any(
                        share(s) >= 0.6 for s in key_of_sig if s not in sigs and key_of_sig[s] == "om."):
                    return " ".join(wk), "a skip in the base copy; the other edition prints these words elsewhere in the verse"
            return k, "the sister copy agrees with the other editions"
        outside_forms = [form_of_sig[s] for s in key_of_sig if s not in sigs and key_of_sig[s] != "om."]
        equiv = {key_of_sig[s] for s in sigs if key_of_sig[s] != "om." and any(
            is_orthographic_equivalence([strip_punct(form_of_sig[s]), strip_punct(o)], "greek")[0] for o in outside_forms)}
        if len(equiv) == 1 and not agree:
            return next(iter(equiv)), "the sister copy is the other edition's reading in another spelling"
        if "om." in keys and len(worded) == 1:
            # only when another edition has substantially the same words, if spelt its own way (Josh 18:28
            # Γαβαωθιαρείμ / Γαβαὼθ καὶ Ἰαρὶμ), not merely some other word (Deut 12:11 OCR 'ἐῷ' / Brenton 'ὑμῶν')
            import difflib
            wk = next(iter(worded)).split()
            if any(k != "om." and (2 * len(set(wk) & set(k.split())) >= len(wk) or difflib.SequenceMatcher(
                    None, "".join(wk), k.replace(" ", ""), autojunk=False).ratio() >= 0.6) for k in outside):
                return next(iter(worded)), "a gap in one copy where the other copies and another edition have the words"
        lex = cv.lexicon
        if base and lex is not None and key_of_sig[base] != "om.":
            b_words = [strip_punct(w) for w in form_of_sig[base].split() if strip_punct(w)]
            others = {key_of_sig[s] for s in sigs if s != base}
            if b_words and len(others) == 1 and "om." not in others:
                o_sig = next(s for s in sigs if s != base)
                o_words = [strip_punct(w) for w in form_of_sig[o_sig].split() if strip_punct(w)]
                if len(b_words) == len(o_words):
                    slips = []
                    ok_all = True
                    for bw, ow in zip(b_words, o_words):
                        bk_w = canonical_compare_key(bw, "greek")
                        ok_w = canonical_compare_key(ow, "greek")
                        if bk_w == ok_w:
                            continue
                        b_cnt, o_cnt = lex.form_count(bw), lex.form_count(ow)
                        corrupt_shape = lex.key_count(bk_w) >= 500 and b_cnt * 200 <= lex.key_count(bk_w)
                        if (o_cnt >= 20 and (b_cnt <= 1 or corrupt_shape or (b_cnt <= 25 and o_cnt >= 500 * b_cnt))
                                and bw[:1].isupper() == ow[:1].isupper()
                                and edit_distance(bk_w, ok_w, limit=3) <= 2):
                            slips.append(f"'{bw}' ({b_cnt}×) for '{ow}' ({o_cnt}×)")
                        else:
                            ok_all = False
                            break
                    if ok_all and slips:
                        return key_of_sig[o_sig], "the base copy has a rare keying slip: " + ", ".join(slips)
        keep = base or max(sigs, key=lambda s: cv.witness_weights.get(s, 0.0))
        return key_of_sig[keep], "the base copy is kept"

    def _sister_copy_split(self, key_groups: Dict[str, List[Tuple[str, List[str]]]], cv: CollatedVerse
                           ) -> Tuple[Dict[str, List[Tuple[str, List[str]]]], Optional[Dict[str, Any]]]:
        """Two digital copies of one printed edition that disagree inside a unit where other editions
        also vote (Swete Clean 'Τύριον' against First1KGreek and Brenton 'Κύριον', Deut 31:12) — an
        encoding slip in one copy, not a variant (invariant 4). The copy that agrees with an edition
        outside the family is kept (else the base edition, else the heavier copy); the other copy's
        reading leaves the vote and is logged."""
        fams = cv.witness_families or {}
        key_of_sig = {s: k for k, members in key_groups.items() for _d, sigs in members for s in sigs}
        form_of_sig = {s: d for _k, members in key_groups.items() for d, sigs in members for s in sigs}
        by_family: Dict[str, List[str]] = {}
        for s in key_of_sig:
            by_family.setdefault(fams.get(s) or _edition_family(s), []).append(s)
        drop: Dict[str, str] = {}
        reasons: set = set()
        for fam, sigs in by_family.items():
            if len(sigs) < 2 or len({key_of_sig[s] for s in sigs}) < 2:
                continue
            outside = {key_of_sig[s] for s in key_of_sig if s not in sigs}
            if not outside:
                continue  # only this family votes here: handled as an encoding difference already
            keep_key, why = self._sister_keep(sigs, key_of_sig, form_of_sig, outside, cv)
            # _sister_keep already protects a genuine word of the base copy.
            # When it selects an omission, the family's rejected word must also
            # leave the vote; otherwise this one edition votes on both sides.
            for s in sigs:
                if key_of_sig[s] != keep_key:
                    drop[s] = keep_key
                    reasons.add(why)
        if not drop:
            return key_groups, None
        out: Dict[str, List[Tuple[str, List[str]]]] = {}
        forms: List[str] = []
        for k, members in key_groups.items():
            for d, sigs in members:
                kept = [s for s in sigs if s not in drop]
                if len(kept) < len(sigs):
                    forms.append(d)
                if kept:
                    out.setdefault(k, []).append((d, kept))
        kept_key = next(iter(drop.values()))
        kept_form = next((d for d, _s in key_groups.get(kept_key, [])), kept_key)
        return out, {
            "kept_form": kept_form, "disregarded_forms": forms, "witnesses": sorted(drop),
            "reason": "Encoding difference between digital copies of the same printed edition ("
                      + "; ".join(sorted(reasons)) + "); not counted as a variant",
        }

    def _pool_spellings(self, key_groups: Dict[str, List[Tuple[str, List[str]]]], cv: CollatedVerse,
                        language: str) -> Dict[str, List[Tuple[str, List[str]]]]:
        """Unite readings that differ only in spelling (γινώσκομεν / B's γεινωσκομεν) before the vote,
        as the confidence model does; otherwise an itacistic copy splits its own reading's support.
        The merged group keeps the key of its best-supported member; the printed spelling is still
        chosen by _choose_best_surface_form."""
        self._last_pool_merges: List[Tuple[str, List[str], List[str]]] = []
        keys = [k for k in key_groups if k != "om."]
        if len(keys) < 2:
            return key_groups
        weight = {k: self._fam([s for _d, sg in key_groups[k] for s in sg], cv) for k in keys}
        merged: Dict[str, List[Tuple[str, List[str]]]] = {}
        pooled = set()

        def may_pool(leading: str, rep: str) -> bool:
            if language == "greek":
                left_number = any(is_letter_numeral(w) for w in leading.split())
                right_number = any(is_letter_numeral(w) for w in rep.split())
                if left_number != right_number:
                    # Unambiguous numeral expansions already share a collation key.
                    # If their keys still differ, do not assign an ambiguous βʹ to
                    # both δύο and δευτέρᾳ and erase that grammatical distinction.
                    return False
            return is_orthographic_equivalence([leading, rep], language)[0]

        for k in sorted(keys, key=lambda k: (-weight[k], k)):
            rep = key_groups[k][0][0]
            # compared with the group's leading spelling (requiring equivalence with every member was
            # tried on 17 Nov: it only split spelling conventions such as ἀγαπᾶν / ἀγαπᾷν and
            # συλλαβεῖν / συνλαβεῖν into apparatus units, and changed no printed text)
            target = next((t for t in merged if len(t.split()) == len(k.split())
                           and may_pool(merged[t][0][0], rep)), None)
            if target is None:
                merged[k] = list(key_groups[k])
            else:
                merged[target] = merged[target] + list(key_groups[k])
                pooled.add(target)
        # The preferred displayed spelling can come from the newly merged group.
        # Log *all other* spellings once, including the old leading group, rather
        # than incorrectly listing the displayed spelling itself as discarded.
        for target, members in merged.items():
            if target in pooled:
                shown = next((d for d, _s in members if _has_accent_marks(d)), members[0][0])
                others = [(d, sg) for d, sg in members if d != shown]
                self._last_pool_merges.append((
                    shown, [d for d, _s in others], sorted({s for _d, sg in others for s in sg})))
        if "om." in key_groups:
            merged["om."] = key_groups["om."]
        return merged
