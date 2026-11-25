"""Token-Level Multi-Witness Collation & Substantive vs. Noise Classifier.

Each verse is aligned word-by-word against the highest-weight witness (the pivot). Every
variation slot is then classified as unanimous, orthographic noise (logged, never hidden), or a
substantive variant (goes to the apparatus). Comparison uses a *canonical key* per token:

* Greek – lower case, final/lunate sigma unified, all accents/breathings removed (so unaccented
  manuscripts compare with accented editions); nomina sacra (``ιυ̅``) are resolved to the full word
  attested elsewhere in the verse; letter-numerals (``ιδʹ``) are recognised.
* Hebrew – cantillation, meteg, rafe, paseq and dots removed; qamats qatan = qamats; the
  Tetragrammaton compares by consonants (MAM writes a holem that the WLC omits); a ketiv in
  parentheses compares as the ketiv.
* Latin – u/v, i/j, æ/ae, œ/oe and diacritics unified.
"""

from __future__ import annotations
import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .parsers import DOUBTFUL_CLOSE, DOUBTFUL_OPEN, GAP_WORD, LACUNA_MARK

PUNCT_RE = re.compile(r"[.,;··;:!?\"'«»“”‘’ʼ᾽()\[\]{}⟨⟩⟦⟧⸀⸁⸂⸃⸄⸅¶˚¦־׃׀—–\-᾿῾]+")
NOMEN_SACRUM_MARK = "̅"   # combining overline used by the CNTR transcriptions
NUMERAL_MARK = "ʹ"        # Greek numeral sign (letter-numerals such as ιδʹ = 14)

# Full-word stems that early manuscripts contract as nomina sacra.
NOMINA_SACRA_STEMS = (
    "θε", "κυρι", "ιησ", "χριστ", "χρηστ", "πνευμ", "ανθρωπ", "υι", "πατηρ", "πατερ", "πατρ",
    "μητηρ", "μητερ", "μητρ", "σταυρ", "δαυιδ", "δαυειδ", "ισραηλ", "ιερουσαλημ", "ουραν", "σωτηρ",
)

# Known Koine / uncial itacisms (Swete prints Vaticanus's spelling) normalised in the critical text.
# Keys are lower-case forms; the grave/acute of the source is preserved for Δαυείδ.
# Diplomatic itacisms of one and the same form only. Never ἴδετε → εἴδετε: ἴδετε is the aorist
# imperative ("see!", Matt 28:6, Gal 6:11, Deut 32:39), εἴδετε the indicative ("you saw").
GREEK_ITACISM_CANONICAL = {
    "ἴδεν": "εἶδεν",
    "ἴδον": "εἶδον",
    "ἴδαμεν": "εἴδομεν",
    "δαυεὶδ": "Δαυὶδ",
    "δαυείδ": "Δαυίδ",
}

# Uncial / drop-cap incipits in Swete and Brenton that have no accented counterpart in the verse
_GREEK_INCIPIT_FALLBACK = {"ΕΝ": "Ἐν", "ἘΝ": "Ἐν", "ΑΡΧΗ": "ἀρχῇ", "ΚΑΙ": "Καὶ"}

_DOUBLE_CONSONANT = re.compile(r"([λνμρσπτκ])\1")

# Movable final sigma: these words appear with and without it.
_MOVABLE_SIGMA = {"ουτω", "αχρι", "μεχρι", "αντικρυ"}


@dataclass
class VariationSlot:
    index: int
    readings: Dict[str, List[str]]   # punctuation-stripped reading -> witness sigla
    raw_forms: Dict[str, List[str]]  # exact raw form -> witness sigla
    kind: str                        # "unanimous", "orthographic_noise", "substantive_variant"
    notes: str = ""
    form_keys: Dict[str, str] = field(default_factory=dict)  # raw form / reading -> canonical key
    is_insertion: bool = False


@dataclass
class CollatedVerse:
    verse: int
    witness_texts: Dict[str, str]           # siglum -> verbatim text
    witness_weights: Dict[str, float]       # siglum -> weight
    slots: List[VariationSlot] = field(default_factory=list)
    external_apparatus: List[str] = field(default_factory=list)
    absent_witnesses: List[str] = field(default_factory=list)     # extant but lacking the verse
    doubtful_witnesses: List[str] = field(default_factory=list)   # edition brackets the verse ⟦ ⟧
    fragmentary_witnesses: List[str] = field(default_factory=list)  # lacuna inside the verse
    witness_refs: Dict[str, str] = field(default_factory=dict)     # siglum -> own "ch:v" when re-aligned
    witness_families: Dict[str, str] = field(default_factory=dict)  # siglum -> edition family
    base_siglum: str = ""                   # orthographic base edition
    lexicon: Any = None                     # corpus frequencies (studio.lexicon.Lexicon) or None
    testament: str = ""                     # "OT" / "NT"
    single_stream: str = ""                 # note when only one text stream has the verse (Greek NT)
    # Apparatus-only witnesses (catalog.APPARATUS_ONLY): their re-aligned text ("" = no such verse) and own
    # "ch:v" when re-aligned. They are not in witness_texts and never vote.
    apparatus_texts: Dict[str, str] = field(default_factory=dict)
    apparatus_refs: Dict[str, str] = field(default_factory=dict)
    book_slug: str = ""
    chapter: int = 0
    open_apparatus_sigla: Set[str] = field(default_factory=set)


def strip_punct(token: str) -> str:
    return PUNCT_RE.sub("", token).strip()


def strip_diacritics(s: str) -> str:
    nfd = unicodedata.normalize("NFD", s)
    base = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", base)


def is_nomen_sacrum(token: str) -> bool:
    return NOMEN_SACRUM_MARK in token


def is_letter_numeral(token: str) -> bool:
    if _greek_letter_value(token) is None:
        return False
    # A plain apostrophe can also mark elision (δ᾽ = δέ, not necessarily four).
    # Explicit keraia/thousands marks are unambiguous; tolerate Swete's koronis
    # only when this is not an ordinary elided word.
    return (any(m in token for m in (NUMERAL_MARK, "ʹ", "͵", "΄", "´"))
            or canonical_compare_key(token, "greek") not in _ELIDED)


_GREEK_DIGITS = dict(zip("αβγδεϛζηθικλμνξοπϟρστυφχψωϡ", (1, 2, 3, 4, 5, 6, 7, 8, 9,
                       10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 200, 300, 400, 500, 600, 700, 800, 900)))
_GREEK_DIGITS.update({"ς": 6, "ϝ": 6, "ϙ": 90})


def _greek_letter_value(token: str) -> Optional[int]:
    """Read a strictly formed alphabetic numeral; never guess from an accent alone."""
    raw = token.strip(".,;··;:!?\"«»“”()[]⟦⟧").lower()
    # 1st1K-LXX / Swete OCR sometimes places a bare smooth breathing on vowel-initial numerals (ἰδ’, ἰβ’).
    # Strip ONLY smooth breathing (\u0313) when no accent or rough breathing is present.
    nfd_r = unicodedata.normalize("NFD", raw)
    if "\u0313" in nfd_r and not any(c in "\u0300\u0301\u0342\u0314" for c in nfd_r):
        raw = unicodedata.normalize("NFC", nfd_r.replace("\u0313", ""))
    match = re.fullmatch(r"(͵?[α-ωϛϝϟϙϡ]+)[ʹʹ΄´᾽’']", raw)
    if match:
        digits = match[1]
    elif re.fullmatch(r"͵[α-θϛϝ][α-ωϛϝϟϙϡ]*", raw):
        digits = raw
    else:
        return None
    thousands = digits.startswith("͵")
    if thousands:
        digits = digits[1:]
    values = [_GREEK_DIGITS.get(c, 0) for c in digits]
    if not values or 0 in values:
        return None
    if thousands:
        if values[0] > 9:
            return None
        values[0] *= 1000
    # One digit per place, in descending order: ιβ = 12, not βι or ας = 201.
    places = [len(str(v)) for v in values]
    if any(a <= b for a, b in zip(places, places[1:])):
        return None
    return sum(values)


_GREEK_NUMBER_WORDS = {
    "δυο": 2, "δυσι": 2, "δυσιν": 2, "δυοιν": 2,
    "τρεισ": 3, "τρια": 3, "τριων": 3, "τρισι": 3, "τρισιν": 3,
    "τεσσαρεσ": 4, "τεσσερεσ": 4, "τεσσαρα": 4, "τεσσερα": 4, "τεσσαρων": 4, "τεσσερων": 4,
    "τεσσαρασ": 4, "τεσσερασ": 4,
    "πεντε": 5, "εξ": 6, "επτα": 7, "οκτω": 8, "εννεα": 9, "δεκα": 10,
    "ενδεκα": 11, "δωδεκα": 12, "δεκαδυο": 12, "δεκατρεισ": 13, "δεκατρια": 13,
    "δεκατεσσαρεσ": 14, "δεκατεσσαρα": 14, "δεκατεσσερεσ": 14, "δεκατεσσερα": 14,
    "δεκατεσσαρασ": 14, "δεκατεσσερασ": 14, "δεκατεσσαρων": 14, "δεκατεσσερων": 14,
    "δεκαπεντε": 15, "δεκαεξ": 16, "δεκαεπτα": 17, "δεκαοκτω": 18, "οκτωκαιδεκα": 18,
    "δεκαεννεα": 19, "εννεακαιδεκα": 19,
    "εικοσι": 20, "εικοσιν": 20, "τριακοντα": 30, "τεσσαρακοντα": 40, "τεσσερακοντα": 40,
    "πεντηκοντα": 50, "εξηκοντα": 60, "εβδομηκοντα": 70, "ογδοηκοντα": 80, "ενενηκοντα": 90, "εννενηκοντα": 90,
    "εκατον": 100,
}


def _greek_number_word_value(token: str) -> Optional[int]:
    """Recognised single-word number forms only; unknowns remain textual variants."""
    k = canonical_compare_key(token, "greek")
    if k in _GREEK_NUMBER_WORDS:
        # ἐξ is the preposition; only accented ἕξ (or an unaccented transcription)
        # may provide the written-out counterpart of a numeral six.
        if k == "εξ" and "ἐ" in token.lower():
            return None
        return _GREEK_NUMBER_WORDS[k]
    for stem, value in (("διακοσ", 200), ("τριακοσ", 300), ("τετρακοσ", 400),
                        ("πεντακοσ", 500), ("εξακοσ", 600), ("επτακοσ", 700),
                        ("οκτακοσ", 800), ("εννακοσ", 900), ("εννεακοσ", 900),
                        ("χιλ", 1000), ("δισχιλ", 2000)):
        if k.startswith(stem) and k[len(stem):] in {"ιοι", "ιαι", "ια", "ιουσ", "ιασ", "ιων", "ιοισ", "ιαισ"}:
            return value
    # Fused cardinals: πεντηκονταεπτά = 57, εἰκοσιεννέα = 29.
    for prefix, value in _GREEK_NUMBER_WORDS.items():
        if 20 <= value <= 90 and k.startswith(prefix):
            rest = k[len(prefix):].removeprefix("και")
            tail = _GREEK_NUMBER_WORDS.get(rest)
            if tail is not None and 2 <= tail <= 9:
                return value + tail
    # A numeral can abbreviate an ordinal; keep differing written-out forms
    # separate in classify_forms, even when their numeric values agree.
    for stem, value in (("πρωτ", 1), ("δευτερ", 2), ("τριτ", 3), ("τεταρτ", 4),
                        ("πεμπτ", 5), ("εκτ", 6), ("εβδομ", 7), ("ογδο", 8),
                        ("ενατ", 9), ("εννατ", 9), ("δεκατ", 10), ("ενδεκατ", 11), ("δωδεκατ", 12)):
        if k.startswith(stem) and k[len(stem):] in {"οσ", "ον", "η", "α", "ου", "ησ", "ασ", "ω", "ην", "αν"}:
            return value
    return None


def _greek_number_phrase_value(phrase: str) -> Optional[int]:
    """Strict exact integer value of a Greek numeral phrase (letter-numerals, spelled-out cardinals,
    or mixed e.g. 'ν᾽ ἑπτά' = 57, 'η᾽ καὶ ι᾽' = 18, 'διακοσίους πεντήκοντα' = 250,
    'τέσσαρας καὶ δέκα' = 14). Returns None if any non-καί token is not a recognised number."""
    toks = [t for t in phrase.split() if strip_punct(t)]
    if not toks:
        return None
    total = 0
    seen_num = False
    prev_was_kai = False
    for t in toks:
        k = canonical_compare_key(t, "greek")
        if k == "και":
            if not seen_num or prev_was_kai:
                return None
            prev_was_kai = True
            continue
        prev_was_kai = False
        if is_letter_numeral(t):
            val = _greek_letter_value(t)
        else:
            val = _greek_number_word_value(t)
        if val is None or val <= 0:
            return None
        total += val
        seen_num = True
    if not seen_num or prev_was_kai:
        return None
    return total


# ---------------------------------------------------------------------------
# Latin Roman-numeral vs. spelled-out number recognition (e.g. Amiatinus Gen 5)
# ---------------------------------------------------------------------------
_LATIN_ROMAN_RE = re.compile(r"^(?:m{0,4})(?:cm|cd|d?c{0,4})(?:xc|xl|l?x{0,4})(?:ix|iv|v?i{0,4})$")
_LATIN_ROMAN_VALS = {"m": 1000, "d": 500, "c": 100, "l": 50, "x": 10, "v": 5, "i": 1}
_LATIN_ROMAN_FALSE_FRIENDS = frozenset({"dii", "di", "mi", "vi", "vim", "id", "ii", "ci", "li"})

_LATIN_NUMBER_EXACT: Dict[str, int] = {
    "unus": 1, "una": 1, "unum": 1, "uno": 1, "uni": 1, "unius": 1, "unam": 1,
    "duo": 2, "duae": 2, "duas": 2, "duos": 2, "duorum": 2, "duarum": 2, "duobus": 2, "duabus": 2,
    "tres": 3, "tria": 3, "trium": 3, "tribus": 3,
    "quatuor": 4, "quattuor": 4, "quinque": 5, "sex": 6, "septem": 7, "octo": 8, "nouem": 9,
    "decem": 10, "undecim": 11, "duodecim": 12, "tredecim": 13,
    "quatuordecim": 14, "quattuordecim": 14, "quindecim": 15, "sedecim": 16, "septendecim": 17,
    "duodeuiginti": 18, "octodecim": 18, "undeuiginti": 19, "nouendecim": 19,
    "uiginti": 20, "triginta": 30, "quadraginta": 40, "quinquaginta": 50,
    "sexaginta": 60, "septuaginta": 70, "octoginta": 80, "nonaginta": 90,
    "centum": 100, "mille": 1000,
}
_LATIN_HUNDRED_STEMS: Tuple[Tuple[str, int], ...] = (
    ("ducent", 200), ("trecent", 300), ("quadringent", 400), ("quingent", 500),
    ("sexcent", 600), ("sescent", 600), ("septingent", 700), ("octingent", 800), ("nongent", 900),
)
_LATIN_HUNDRED_ENDS = frozenset({"i", "ae", "a", "orum", "arum", "is", "os", "as"})


def _latin_roman_token_value(token: str) -> Optional[int]:
    """Parse one strict Roman-numeral token (classical or medieval additive dcccc/cccc/iiii)."""
    core = strip_punct(token).lower()
    if not core or not _LATIN_ROMAN_RE.match(core) or core in _LATIN_ROMAN_FALSE_FRIENDS:
        return None
    total = 0
    prev = 0
    for ch in reversed(core):
        v = _LATIN_ROMAN_VALS[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total if total > 0 else None


def is_latin_roman_numeral(phrase: str, *, allow_single_letter: bool = False) -> bool:
    """True if ``phrase`` is a Roman-numeral abbreviation (e.g. ``cxxx``, ``dcccc xxx``, ``dccc xcv``).

    Single-letter tokens (``i``, ``v``, ``x``...) are accepted only inside a descending multi-token
    numeral (``dcccc x``) or when ``allow_single_letter=True`` (used only when paired with a
    spelled-out Latin cardinal of the exact same integer value, e.g. ``x`` vs ``decem``)."""
    toks = [strip_punct(t).lower() for t in phrase.split() if strip_punct(t)]
    if not toks:
        return False
    if len(toks) == 1 and len(toks[0]) < 2 and not allow_single_letter:
        return False
    vals = [_latin_roman_token_value(t) for t in toks]
    if any(v is None for v in vals):
        return False
    return all(a > b for a, b in zip(vals, vals[1:]))  # type: ignore[operator]


def _latin_number_phrase_value(phrase: str, *, allow_single_letter: bool = False) -> Optional[int]:
    """Integer value of either a Roman-numeral abbreviation or a spelled-out Latin cardinal phrase."""
    if is_latin_roman_numeral(phrase, allow_single_letter=allow_single_letter):
        vals = [_latin_roman_token_value(t) for t in phrase.split() if strip_punct(t)]
        return sum(v for v in vals if v is not None)
    toks = [canonical_compare_key(t, "latin") for t in phrase.split() if strip_punct(t)]
    if not toks:
        return None
    total = 0
    cur = 0
    seen_num = False
    for k in toks:
        if k == "et":
            continue
        if k in ("milia", "millia"):
            if cur == 0:
                return None
            total += cur * 1000
            cur = 0
            seen_num = True
            continue
        val = _LATIN_NUMBER_EXACT.get(k)
        if val is None:
            for stem, hval in _LATIN_HUNDRED_STEMS:
                if k.startswith(stem) and k[len(stem):] in _LATIN_HUNDRED_ENDS:
                    val = hval
                    break
        if val is None:
            return None
        cur += val
        seen_num = True
    return (total + cur) if seen_num and (total + cur) > 0 else None


def _hebrew_key(clean: str) -> str:
    # MAM writes Jerusalem's patah+hiriq with a zero-width joiner / grapheme joiner between them.
    nfd = unicodedata.normalize("NFD", clean.replace("‍", "").replace("͏", ""))
    kept = []
    for ch in nfd:
        cp = ord(ch)
        if 0x0591 <= cp <= 0x05AF or cp in (0x05BD, 0x05BF, 0x05C0, 0x05C4, 0x05C5):
            continue
        kept.append("ָ" if cp == 0x05C7 else ch)  # qamats qatan -> qamats
        if cp == 0x05BA:
            kept[-1] = "ֹ"  # holem haser for vav = holem
    key = re.sub(r"\u05b8{2,}", "\u05b8", "".join(kept))
    consonants = "".join(ch for ch in key if "א" <= ch <= "ת")
    if "יהוה" in consonants or "יהוִה" in key:
        # The divine name is pointed differently by different editions (MAM writes a holem);
        # compare it by consonants.
        key = consonants
    return unicodedata.normalize("NFC", key)


def canonical_compare_key(token: str, language: str) -> str:
    """Key that groups pure capitalisation, punctuation, accent and encoding differences."""
    clean = strip_punct(token)
    if not clean:
        return ""
    lang = language.lower()
    if lang == "greek":
        low = unicodedata.normalize("NFC", clean.lower()).replace("ς", "σ").replace("ϲ", "σ")
        return strip_diacritics(low)
    if lang == "latin":
        low = clean.lower().replace("æ", "ae").replace("œ", "oe").replace("ę", "ae").replace("j", "i").replace("v", "u")
        return strip_diacritics(low)
    if lang == "hebrew":
        return _hebrew_key(clean)
    return clean.lower()


# ---------------------------------------------------------------------------
# Secondary (orthographic) keys
# ---------------------------------------------------------------------------

def _latin_ortho_key(k: str) -> str:
    """Spelling-level Latin normalisation (Amiatinus vs Clementine conventions)."""
    s = k.replace("michi", "mihi").replace("nichil", "nihil")
    if s in ("aput", "adque"):
        s = {"aput": "apud", "adque": "atque"}[s]
    s = {"cherubin": "cherubim", "seraphin": "seraphim", "turrem": "turrim"}.get(s, s)
    s = re.sub(r"^adp", "app", s)
    s = re.sub(r"^ad([cfglnqrst])", r"a\1\1", s)
    s = re.sub(r"^acq", "aq", s)                      # adquiesco / acquiesco
    s = re.sub(r"^in([mp])", r"im\1", s)
    s = re.sub(r"^in([lr])", r"i\1\1", s)            # inluminent / illuminent, inrigans / irrigans
    s = re.sub(r"^con([lmr])", r"co\1\1", s)
    s = re.sub(r"^con([pb])", r"com\1", s)            # conpleuit / compleuit
    s = re.sub(r"^ob([cfgp])", r"o\1\1", s)          # obcumberet / occumberet, obfero / offero, obpono / oppono
    s = re.sub(r"^sub([cfgmpr])", r"su\1\1", s)      # subripuit / surripuit, submitto / summitto
    s = re.sub(r"^exs", "ex", s)
    s = re.sub(r"^adulesc", "adolesc", s)
    s = re.sub(r"^sescent", "sexcent", s)
    s = re.sub(r"^intelleg", "intellig", s)
    s = re.sub(r"^(at)?temp?t", r"\1tent", s)         # temptauit / temtauit / tentauit
    s = s.replace("quicqu", "quidqu").replace("md", "nd").replace("ncx", "nx")  # quicquam/quidquam, eorundem, tincxerunt/tinxerunt
    # Strictly verified classical / late-Latin pure orthographic doublets (same lexeme & inflection).
    s = {"cotidie": "quotidie", "bubus": "bobus", "reliquid": "reliquit"}.get(s, s)
    s = re.sub(r"^caerimoni", "caeremoni", s)         # caerimonias / caeremonias
    s = re.sub(r"^botyr", "butyr", s)                 # botyrum / butyrum
    s = re.sub(r"^formons", "formos", s)              # formonsae / formosae
    s = re.sub(r"^deuert", "diuert", s)               # deverterent / diverterent (v->u in canonical key)
    s = re.sub(r"^armell", "armill", s)               # armellas / armillas
    s = re.sub(r"^uended", "uendid", s)               # vendedit / vendidit (v->u in canonical key)
    s = re.sub(r"^sterel", "steril", s)               # stereles / steriles
    # Aspiration first, so Israhel / Israël and Ismahel / Ismaël meet before ae → e.
    s = s.replace("ph", "f").replace("th", "t").replace("ch", "c").replace("h", "")
    s = s.replace("ae", "e").replace("oe", "e").replace("y", "i")
    s = re.sub(r"ci(?=[aeiou])", "ti", s)
    s = s.replace("mpt", "mt").replace("mps", "ms").replace("quu", "qu")
    # Doubled consonants and ii only: doubled u is consonantal u + u (paruum = parvum ≠ parum, suum ≠ sum).
    s = re.sub(r"([^aeiou])\1", r"\1", s).replace("ii", "i")
    return s


# Distinct Latin words that the spelling key would otherwise merge.
_LATIN_DISTINCT = {
    frozenset(p) for p in (
        ("summus", "sumus"), ("annus", "anus"), ("anni", "ani"), ("annos", "anos"), ("hos", "os"),
        ("hora", "ora"), ("horam", "oram"), ("hostium", "ostium"), ("hostia", "ostia"), ("coepit", "cepit"),
        ("habeam", "abeam"), ("habes", "abes"), ("habet", "abet"), ("habit", "abit"), ("mitte", "mite"),
        ("aes", "es"), ("aeris", "eris"), ("ferrum", "ferum"), ("cella", "cela"), ("callis", "calis"),
        ("vallis", "valis"), ("pullus", "pulus"), ("hic", "ic"), ("haec", "ec"), ("hoc", "oc"),
        ("hostis", "ostis"), ("aequus", "equus"), ("aequum", "equum"), ("caelum", "celum"),
    )
}


def _latin_distinct(keys: Iterable[str]) -> bool:
    words = [k.split() for k in keys]
    for column in zip(*words) if len({len(w) for w in words}) == 1 else []:
        for a in column:
            for b in column:
                if a != b and frozenset((a, b)) in _LATIN_DISTINCT:
                    return True
    return False


def _hebrew_matres_key(raw: str) -> str:
    """Hebrew key with matres lectionis folded (plene vs defective spelling)."""
    k = unicodedata.normalize("NFD", _hebrew_key(strip_punct(raw)))
    k = re.sub("וֹ", "ֹ", k)              # holem male -> holem
    k = re.sub("(?<=.)וּ", "ֻ", k)         # shuruq (not word-initial) -> qibbuts
    # qibbuts (+ optional dagesh/shin-sin) + bare vav -> qibbuts (e.g. נְאֻום / פִקֻּודֶיךָ)
    k = re.sub("(\u05bb)([\u05bc\u05c1\u05c2]*)ו(?![\u05b0-\u05bc\u05c1\u05c2\u05c7])", r"\1\2", k)
    # matres lectionis adjacent to quiescent alef (רִאישֹׁנָה / רִיאשֹׁנָה; מֵחַטֹּאות / מֵחַטֹּאת)
    k = re.sub("(\u05b4)([\u05bc\u05c1\u05c2]*)א(?![\u05b0-\u05bc\u05c1\u05c2\u05c7])י(?![\u05b0-\u05bc\u05c1\u05c2\u05c7])", r"\1\2א", k)
    k = re.sub("(\u05b9)([\u05bc\u05c1\u05c2]*)א(?![\u05b0-\u05bc\u05c1\u05c2\u05c7])ו(?![\u05b0-\u05bc\u05c1\u05c2\u05c7])", r"\1\2א", k)
    # hiriq/tsere (+ dagesh or shin/sin dot, which NFD may order after the vowel) + yod -> vowel
    k = re.sub("([ִֵ])([ּׁׂ]*)י(?![ְ-ּׁׂ])", r"\1\2", k)
    # Strictly 3fp/2fp verb ending -ֶינָה / -ֶנָה (NEVER fold -ֶךָ/-ֶיךָ or -ֶהָ/-ֶיהָ noun suffixes!)
    k = re.sub("\u05b6([\u05bc\u05c1\u05c2]*)ינ\u05b8ה$", "\u05b6\\1נ\u05b8ה", k)
    return unicodedata.normalize("NFC", k)


def _latin_betacism(forms: List[str]) -> bool:
    """b/u(v) interchange only (corbum / corvum, delebit / delevit): same length, every difference
    a b against a u/v. Compared after the spelling key, so an assimilation plus a b/u difference
    (conportavis / comportabis) is caught too."""
    keys = [_latin_ortho_key(canonical_compare_key(f, "latin")) for f in forms]
    if len({len(k) for k in keys}) != 1 or len(set(keys)) < 2 or any(" " in k for k in keys):
        return False
    first = keys[0]
    for other in keys[1:]:
        diffs = [(a, b) for a, b in zip(first, other) if a != b]
        # one interchange per word only: bibit / uiuit are two different verbs
        if len(diffs) != 1 or {diffs[0][0], diffs[0][1]} != {"b", "u"}:
            return False
    return True


_HEB_SHEWA, _HEB_DAGESH, _HEB_HOLEM, _HEB_PATAH = "\u05b0", "\u05bc", "\u05b9", "\u05b7"
_HEB_HATAF = {"\u05b1": "\u05b6", "\u05b2": "\u05b7", "\u05b3": "\u05b8"}
_HEB_SHIN_SIN = ("\u05c1", "\u05c2")
_HEB_VOWELS = frozenset("\u05b0\u05b1\u05b2\u05b3\u05b4\u05b5\u05b6\u05b7\u05b8\u05b9\u05ba\u05bb\u05c7")


def _hebrew_consonants(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if "\u05d0" <= ch <= "\u05ea")


def _is_hebrew_ketiv_token(token: str) -> bool:
    t = token.strip()
    if not t:
        return False
    return any(w.startswith("(") or w.rstrip("׃־").endswith(")") for w in t.split())


def _hebrew_ketiv_defective(word: str) -> str:
    """Consonantal skeleton of a Hebrew ketiv with internal matres ו/י folded (initial & final letters kept)."""
    cons = _hebrew_consonants(word)
    if len(cons) <= 2:
        return cons
    return cons[0] + "".join(ch for ch in cons[1:-1] if ch not in "וי") + cons[-1]


def _is_hebrew_defective_subset(short_word: str, long_word: str) -> bool:
    """True if ``short_word``'s consonants are obtained from ``long_word``'s consonants strictly by
    omitting internal matres ו/י (never substituting ו↔י as in Prov 23:24 יָגִיל vs יגול)."""
    sc, lc = _hebrew_consonants(short_word), _hebrew_consonants(long_word)
    if not sc or not lc or len(sc) >= len(lc) or sc[0] != lc[0] or sc[-1] != lc[-1]:
        return False
    i = 1
    for ch in lc[1:-1]:
        if i < len(sc) - 1 and sc[i] == ch:
            i += 1
        elif ch not in "וי":
            return False
    return i == len(sc) - 1


def is_biblical_aramaic_verse(book_slug: str, chapter: int, verse: int) -> bool:
    """True iff (book_slug, chapter, verse) lies inside one of the 5 MT Biblical Aramaic pericopes
    (Gen 31:47, Jer 10:11, Ezra 4:8–6:18, Ezra 7:12–26, Dan 2:4–7:28). Fails closed on empty context."""
    slug = (book_slug or "").lower()
    if slug == "genesis":
        return chapter == 31 and verse == 47
    if slug == "jeremiah":
        return chapter == 10 and verse == 11
    if slug == "ezra":
        return ((chapter == 4 and verse >= 8)
                or chapter == 5
                or (chapter == 6 and verse <= 18)
                or (chapter == 7 and 12 <= verse <= 26))
    if slug == "daniel":
        return ((chapter == 2 and verse >= 4)
                or (3 <= chapter <= 6)
                or (chapter == 7 and verse <= 28))
    return False


def _aramaic_final_alef_he(forms: List[str]) -> bool:
    """Biblical Aramaic word-final -ָא/-ָה and -ֵא/-ֵה mater lectionis alternation (Aleppo vs Leningrad).
    Strictly rejects mappiq (הּ), vowel-bearing final ה/א, and any difference outside the final mater."""
    words = [f.split() for f in forms]
    if len({len(w) for w in words}) != 1:
        return False
    saw_swap = False
    for column in zip(*words):
        if len({_hebrew_key(strip_punct(w)) for w in column}) == 1:
            continue
        clusters = [_hebrew_clusters(w) for w in column]
        if len({len(cl) for cl in clusters}) != 1 or len(clusters[0]) < 2:
            return False
        # Every non-final consonant & its vowel marks must agree (or pass pointing convention).
        if any(len({cl[p][0] for cl in clusters}) != 1 for p in range(len(clusters[0]) - 1)):
            return False
        if any(len({frozenset(cl[p][1]) for cl in clusters}) != 1 for p in range(len(clusters[0]) - 1)):
            return False
        # Preceding consonant must carry qamats (ָ) or tsere (ֵ) in every form (never unpointed ketiv).
        prev_vowels = [cl[-2][1] & {"\u05b8", "\u05b5"} for cl in clusters]
        if any(not pv for pv in prev_vowels) or len({frozenset(pv) for pv in prev_vowels}) != 1:
            return False
        finals = [cl[-1] for cl in clusters]
        if {c for c, _m in finals} != {"א", "ה"}:
            return False
        # Strictly NO mappiq (ּ) or vowel on final ה/א (preserves Dan 3:29 אֱלָהּ / אֱלָה!).
        if any(m & ({_HEB_DAGESH} | _HEB_VOWELS) for _c, m in finals):
            return False
        saw_swap = True
    return saw_swap


def _hebrew_clusters(word: str) -> List[Tuple[str, Set[str]]]:
    out: List[Tuple[str, Set[str]]] = []
    for ch in unicodedata.normalize("NFD", _hebrew_key(strip_punct(word))):
        if "\u05d0" <= ch <= "\u05ea":
            out.append((ch, set()))
        elif out and unicodedata.category(ch) == "Mn":
            out[-1][1].add(ch)
    return out


def hebrew_pointing_convention(forms: List[str]) -> str:
    """Same consonants, and every pointing difference is one the Aleppo-tradition and Leningrad
    editions handle by convention: dagesh (other than a suffix mappiq or shuruq), vocal/silent shewa,
    hataf against the full vowel, holem placement, Decalogue double-vocalisation, Jerusalem dual-vowel
    ordering, adjacent-yod vowel placement, or a point one edition leaves out. Vowel-quality
    differences (אַל / אֶל), a suffix mappiq (לְדַעְתָּהּ / לְדַעְתָּה) and shin/sin swaps return ""
    (they stay in the apparatus). Returns the reason, or "" when it is not a convention."""
    words = [f.split() for f in forms]
    if len({len(w) for w in words}) != 1:
        return ""
    kinds: Set[str] = set()
    dots = set(_HEB_SHIN_SIN)
    for column in zip(*words):
        clusters = [_hebrew_clusters(w) for w in column]
        if len({tuple(c for c, _m in cl) for cl in clusters}) != 1:
            return ""
        if len({tuple(frozenset(m) for _c, m in cl) for cl in clusters}) == 1:
            continue
        if any(all(not m for _c, m in cl) for cl in clusters):
            kinds.add("bare consonants (ketiv) against the pointed form")
            continue
        # Holem placement (on the vav or on the letter before it) is a convention only when both
        # forms write the same number of holems.
        holem_free = len({sum(_HEB_HOLEM in m for _c, m in cl) for cl in clusters}) == 1
        cons_str = "".join(c for c, _m in clusters[0])
        is_jerusalem = cons_str.endswith("ירושלם") and len(cons_str) <= 8
        last = len(clusters[0]) - 1
        pos = 0
        while pos <= last:
            letters = [cl[pos] for cl in clusters]
            letter = letters[0][0]
            raw = [set(m) for _c, m in letters]
            if len({frozenset(r) for r in raw}) == 1:
                pos += 1
                continue
            # Adjacent-yod vowel placement (Gen 4:18 וּמְחִיָּיאֵל / וּמְחִיּיָאֵל): two consecutive י
            # carrying the identical single vowel on the first vs the second י (dagesh aside).
            if letter == "י" and pos + 1 <= last and clusters[0][pos + 1][0] == "י":
                pair_vows = [
                    (cl[pos][1] - {_HEB_DAGESH}, cl[pos + 1][1] - {_HEB_DAGESH})
                    for cl in clusters
                ]
                if (all((bool(v1) != bool(v2)) for v1, v2 in pair_vows)
                        and len({frozenset(v1 | v2) for v1, v2 in pair_vows}) == 1):
                    kinds.add("adjacent-yod vowel placement")
                    pos += 2
                    continue
            mappiq = {pos == last and letter == "ה" and _HEB_DAGESH in r and _HEB_PATAH not in r for r in raw}
            if len(mappiq) > 1:
                return ""  # suffix mappiq marks the suffix (her / its): a real difference
            # A dot in vav is shuruq (a vowel) unless EVERY form also carries another vowel mark on
            # that vav (consonantal vav with dagesh forte, e.g. Gen 46:13 וּפֻוָּה, Song 5:2 קְוֻּצּוֹתַי).
            drop_dagesh = letter != "ו" or all(r & _HEB_VOWELS for r in raw)
            drop = ({_HEB_DAGESH} if drop_dagesh else set()) | ({_HEB_HOLEM} if holem_free else set())
            base = [r - drop for r in raw]
            shin = [b & dots for b in base]
            if all(shin) and len({frozenset(d) for d in shin}) > 1:
                return ""  # shin / sin
            vow = [b - dots for b in base]
            diff = set().union(*raw) - set.intersection(*raw)
            if len({frozenset(v) for v in vow}) == 1:
                if _HEB_DAGESH in diff:
                    kinds.add("dagesh")
                if _HEB_HOLEM in diff:
                    kinds.add("holem placement")
                if diff & dots:
                    kinds.add("shin/sin dot left out")
                pos += 1
                continue
            # Song 5:11 (קְוֻצּוֹתָיו / קְוּצּוֹתָיו): consonantal vav after shewa written with shuruq vs qibbuts
            if (letter == "ו" and pos > 0 and _HEB_SHEWA in clusters[0][pos - 1][1]
                    and {frozenset(r) for r in raw} == {frozenset({_HEB_DAGESH}), frozenset({"\u05bb"})}):
                kinds.add("consonantal vav shuruq / qibbuts")
                pos += 1
                continue
            # Jerusalem Qere Perpetuum dual-vowel ordering (יְרוּשָׁלִַם / יְרוּשָׁלִָם / וִירוּשָׁלָם)
            if (is_jerusalem and letter == "ל" and pos == last - 1
                    and all(v and v <= {_HEB_PATAH, "\u05b8", "\u05b4"} and (v & {_HEB_PATAH, "\u05b8"}) for v in vow)):
                kinds.add("Jerusalem dual-vowel Qere Perpetuum")
                pos += 1
                continue
            # Decalogue double vocalisation (Ta'am Elyon/Tachton: patah+qamats vs single patah/qamats, Exod 20:4, Deut 5:8)
            dual_pq = {_HEB_PATAH, "\u05b8"}
            if any(v == dual_pq for v in vow) and all(v and v <= dual_pq for v in vow):
                kinds.add("double vocalisation (Ta'am Elyon / Tachton)")
                pos += 1
                continue
            reduced = {_HEB_SHEWA} | set(_HEB_HATAF)
            if len({frozenset(_HEB_HATAF.get(x, x) for x in v) for v in vow}) == 1:
                kinds.add("hataf against the full vowel")  # חֲ / חַ
                pos += 1
                continue
            if all(v <= reduced for v in vow):
                kinds.add("shewa / hataf")  # vocal or silent shewa, or hataf, against shewa or nothing
                pos += 1
                continue
            if any(not r for r in raw):
                kinds.add("a vowel point left out by one edition")  # one edition leaves the letter bare
                pos += 1
                continue
            return ""  # different vowels, or shewa against a full vowel (שְׁמַע / שָׁמַע)
    if not kinds:
        return ""
    return "Pointing convention, Aleppo tradition (MAM) vs Leningrad (WLC): " + ", ".join(sorted(kinds))


def _greek_koine_spelling_key(k: str) -> str:
    """Strictly unambiguous Koine spelling doublets (never collapses -αν/-ον, ἐάν/ἄν, ἑαυτοῦ/αὐτοῦ,
    γένημα/γέννημα, or ἴδετε/εἴδετε)."""
    s = k
    s = re.sub(r"εξ([οω])λοθρ", r"εξ\1λεθρ", s)       # ἐξολεθρ- / ἐξολοθρ-, ἐξωλεθρ- / ἐξωλοθρ-
    s = re.sub(r"^(ου|μη)θ(εισ|εν|ενοσ|ενι|ενα|εμια|εμιασ|εμιαν)$", r"\1δ\2", s)  # οὐθείς/οὐδείς, μηθείς/μηδείς
    if s == "εχθεσ":
        s = "χθεσ"                                    # ἐχθές / χθές
    s = re.sub(r"^εννατ([οηαω])", r"ενατ\1", s)       # ἔνατος / ἔννατος
    s = re.sub(r"^εννενηκοντ", "ενενηκοντ", s)        # ἐνενήκοντα / ἐννενήκοντα
    s = re.sub(r"^τεσσερ", "τεσσαρ", s)               # τεσσαρ- / τεσσερ-
    s = s.replace("γιγν", "γιν")                      # γίγνομαι/γίνομαι, γιγνώσκω/γινώσκω
    s = s.replace("τετρααρχ", "τετραρχ")              # τετραάρχ- / τετράρχ-
    s = re.sub(r"^αλι(?=εισ|εων|ευ|εα)", "αλε", s)    # ἁλεεῖς / ἁλιεῖς
    return s


_GREEK_CRASIS: Dict[str, Tuple[str, str]] = {
    "καγω": ("και", "εγω"),
    "καμοι": ("και", "εμοι"),
    "καμε": ("και", "εμε"),
    "κακει": ("και", "εκει"),
    "κακειθεν": ("και", "εκειθεν"),
    "κακεινοσ": ("και", "εκεινοσ"),
    "κακεινη": ("και", "εκεινη"),
    "κακεινο": ("και", "εκεινο"),
    "κακεινοι": ("και", "εκεινοι"),
    "κακειναι": ("και", "εκειναι"),
    "κακεινα": ("και", "εκεινα"),
    "κακεινουσ": ("και", "εκεινουσ"),
    "κακεινασ": ("και", "εκεινασ"),
    "κακεινων": ("και", "εκεινων"),
    "κακεινον": ("και", "εκεινον"),
    "κακεινην": ("και", "εκεινην"),
    "κακεινω": ("και", "εκεινω"),
    "κακεινησ": ("και", "εκεινησ"),
    "κακεινου": ("και", "εκεινου"),
}


def _greek_ortho_variant(keys: Set[str], raw_forms: Optional[Iterable[str]] = None) -> str:
    """Return a reason if the differing Greek keys are a recognised spelling variant."""
    if len(keys) < 2:
        return ""
    # Morphological distinctness guard: ἴδετε (aorist imperative "see!") vs εἴδετε (aorist indicative "you saw")
    if keys == {"ιδετε", "ειδετε"}:
        return ""
    if (all(_greek_number_word_value(k) is not None for k in keys)
            and len({k.replace("τεσσερ", "τεσσαρ") for k in keys}) == 1):
        return "Number-word spelling convention (τεσσαρ- / τεσσερ-)"
    if len({_greek_koine_spelling_key(k) for k in keys}) == 1:
        return "Koine orthographic doublet (ἐξολεθρ-/οὐθείς/ἔνατος/γιγν-/τετραάρχ-/ἁλεεῖς type)"
    stems = {re.sub(r"ν$", "", k) for k in keys}
    if len(stems) == 1 and _movable_nu_stem(next(iter(stems))):
        return "Euphonic movable-nu (-ν) variation"
    if {re.sub(r"σ$", "", k) for k in keys} <= _MOVABLE_SIGMA and len({re.sub(r"σ$", "", k) for k in keys}) == 1:
        return "Movable final sigma (οὕτω/οὕτως type)"
    if len({k.replace("ει", "ι") for k in keys}) == 1:
        return "Koine/Uncial itacistic spelling (ει / ι equivalence)"
    # Single-edit εει ↔ ει guard (e.g. Σεμεεὶ / Σεμεῒ): strictly requires diaeresis ϊ/ΐ/ῒ OR
    # min(len) >= 4 (never an unbounded while-loop; never collapses short forms like δέει [4] / δεῖ [3]).
    if (any("εει" in k for k in keys)
            and len({k.replace("εει", "ει") for k in keys}) == 1
            and (min(len(k) for k in keys) >= 4
                 or (raw_forms is not None and any("\u0308" in unicodedata.normalize("NFD", f) for f in raw_forms)))):
        return "Koine/Uncial itacistic spelling (εει / ει equivalence)"
    if len({re.sub(r"^(δα|λε)β(ει|ι)", r"\1υ\2", k).replace("ει", "ι") for k in keys}) == 1:
        return "Semitic proper-name transliteration convention (Δαυίδ / Δαυεὶδ / Δαβίδ, Λευί / Λεβί)"
    combined = {re.sub(r"ν$", "", k.replace("ει", "ι")) for k in keys}
    if (len(combined) == 1 and min(len(k) for k in keys) >= 3
            and all(_movable_nu_stem(re.sub(r"ν$", "", k)) or not k.endswith("ν") for k in keys)
            and any(_movable_nu_stem(re.sub(r"ν$", "", k)) for k in keys)):
        return "Itacistic spelling with movable ν (ἴδεν / εἶδε type)"
    if len({k.replace("μψ", "ψ").replace("μφθ", "φθ") for k in keys}) == 1:
        return "Nasal spelling (λημψ- / ληψ-)"
    if len({_greek_assimilate(k) for k in keys}) == 1:
        return "Prefix assimilation spelling (συνπ-/συμπ-, ἐνκ-/ἐγκ-, συνζ-/συζ-, Κενχρ-/Κεγχρ- type)"
    # Doubled ρ/π/κ/σ, and νν only in Ἰωάννης/Ἄννα: λλ and other doublings separate tenses and words
    # (βάλλειν / βαλεῖν, ἀποστέλλει / ἀποστελεῖ, μέλλει / μέλει, γέννημα / γένημα).
    if min(len(k) for k in keys) >= 5 and len({_DOUBLE_SPELLING.sub(r"\1", k) for k in keys}) == 1:
        return "Single / double consonant spelling (Ἰωάνης / Ἰωάννης type)"
    if len({_greek_ν_names(k) for k in keys}) == 1 and any("νν" in k for k in keys):
        return "Single / double consonant spelling (Ἰωάνης / Ἰωάννης type)"
    # A witness can combine both conventions in one word: Sinaiticus's first hand
    # has μνησστευθισησ in Matt 1:18 (σσ + ι for ει). Compose only the existing
    # restricted ρ/π/κ/σ doubling rule with ει/ι; λλ/νν and other vowels can
    # distinguish tenses or words and must not be collapsed by this rule.
    # χειμάρρων (torrents) / χιμάρων (young goats), Mic 6:7, is a lexical
    # contrast despite matching after both substitutions.
    if (min(len(k) for k in keys) >= 5
            and not any(k.startswith(("χειμαρ", "χιμαρ")) for k in keys)
            and len({_DOUBLE_SPELLING.sub(r"\1", k).replace("ει", "ι") for k in keys}) == 1):
        return "Combined single / double consonant and itacistic spelling (ει / ι)"
    full = {_ELIDED.get(k, k) for k in keys}
    if len(full) == 1:
        return "Elision (κατὰ / κατ’ type)"
    return ""


_DOUBLE_SPELLING = re.compile(r"([ρπκσ])\1")
_ELIDABLE = ("δια", "κατα", "μετα", "παρα", "αλλα", "απο", "επι", "υπο", "ινα", "ουδε", "μηδε", "αντι",
             "αμφι", "δε", "τε", "γε", "ουτε", "μητε")
_ELIDED = {w[:-1]: w for w in _ELIDABLE}
_ELIDED.update({"καθ": "κατα", "μεθ": "μετα", "αφ": "απο", "εφ": "επι", "υφ": "υπο", "ανθ": "αντι"})


def _movable_nu_stem(stem: str) -> bool:
    """Movable ν follows -σι/-ξι/-ψι (dative plural, 3rd plural -ουσι), a verb ending in -ε
    (ἔλεγε, εἶπε), -εστι (ἐστί, ἔξεστι, πάρεστι, ἔνεστι), and εἴκοσι — never -ει, where
    λέγει / λέγειν are two forms (3rd singular, infinitive)."""
    if len(stem) < 3:
        return False
    return (stem.endswith(("σι", "ξι", "ψι", "εστι"))
            or stem == "εικοσι"
            or (stem.endswith("ε") and not stem.endswith("ει")))


def _greek_ν_names(k: str) -> str:
    return re.sub(r"^ιωανν", "ιωαν", k)


def _greek_assimilate(k: str) -> str:
    """Spell nasal prefixes & velar nasals the assimilated way (B and Swete often leave συν-/ἐν- unassimilated)."""
    k = re.sub(r"^(συ|ε|παλι)ν(?=[πβφψμ])", r"\1μ", k)
    k = re.sub(r"^(συ|ε|παλι)ν(?=[κγχξ])", r"\1γ", k)
    k = re.sub(r"^συν(?=λ)", "συλ", k)
    k = re.sub(r"^συν(?=ρ)", "συρ", k)
    k = re.sub(r"^συν(?=σ)", "συσ", k)
    k = re.sub(r"^συν(?=ζ)", "συ", k)        # συνζητεῖν / συζητεῖν
    k = re.sub(r"ν(?=[χγ])", "γ", k)         # Κενχρεαῖς / Κεγχρεαῖς
    return k


IOTA_SUBSCRIPT_NOTE = "Iota subscript differs (a case difference such as γῆ / γῇ, not an accent convention)"


def _subscript_positions(form: str) -> Tuple[int, ...]:
    """Letters that carry an iota subscript, ignoring a capital first letter (editions write the
    capital's iota differently: Ἧ, ᾟ, Ἧι), so only a lower-case difference counts."""
    out, idx = [], -1
    letters = strip_punct(form)
    for ch in unicodedata.normalize("NFD", letters):
        if unicodedata.category(ch) != "Mn":
            idx += 1
        elif ch == "ͅ" and not (idx == 0 and letters[:1].isupper()):
            out.append(idx)
    return tuple(out)


_AIRO_AORIST_RE = re.compile(r"^(απ|επ|εξ|δι|κατ|μετ|παρ|συν|υπερ|αν)?ηρ(?:α|ασ|ε|εν|αμεν|ατε|αν)$")
_ZOO_NOUN_KEYS = frozenset({"ζωον", "ζωου", "ζωω", "ζωα", "ζωων", "ζωοισ"})
_ODE_NOUN_KEYS = frozenset({"ωδη", "ωδησ", "ωδην", "ωδαι", "ωδων", "ωδαισ", "ωδασ"})


def _non_morphological_iota_subscript(accented_forms: List[str]) -> bool:
    """True iff the ONLY iota-subscript difference among ``accented_forms`` (which share the exact
    same letters) lies on a strictly non-morphological 19th-c. orthographic stem position:
    αἴρω aorist augment (ἀπῆραν/ἀπῇραν, ἦραν/ᾖραν, ἦρα/ᾖρα, ἐξῆρεν/ἐξῇρεν), crasis κἀγώ/κᾀγώ,
    or lexical stems ἀθῷος/ἀθῶος, ζῷον/ζῶον, ᾠδή/ὠδή, σῴζω/σώζω.
    Every case/mood ending difference (γῆ/γῇ, ᾖ/ἡ, ᾗ/ἡ, τῇ/τῆ, ᾠδή/ᾠδῇ, ζῶ/ζῷ, declined names)
    returns False and stays substantive."""
    if not accented_forms or any(" " in f.strip() for f in accented_forms):
        return False
    key = canonical_compare_key(accented_forms[0], "greek")
    if not key:
        return False
    pos_sets = [set(_subscript_positions(f)) for f in accented_forms]
    diff_pos = set().union(*pos_sets) - set.intersection(*pos_sets)
    if not diff_pos:
        return False
    if key == "καγω":
        return diff_pos == {1}
    m = _AIRO_AORIST_RE.match(key)
    if m:
        return diff_pos == {len(m.group(1) or "")}
    if key.startswith("αθω") and len(key) >= 4:
        return diff_pos == {2}
    if key in _ZOO_NOUN_KEYS:
        return diff_pos == {1}
    if key in _ODE_NOUN_KEYS:
        return diff_pos == {0}
    if "σωζ" in key:
        return diff_pos == {key.index("σωζ") + 1}
    return False


def classify_forms(
    raw_forms: Iterable[str],
    keys: Dict[str, str],
    language: str,
    *,
    is_aramaic: bool = False,
) -> Tuple[bool, str]:
    """Decide whether differing surface forms are orthographic noise.

    ``raw_forms`` excludes omissions; ``keys`` maps each raw form to its canonical key."""
    forms = list(raw_forms)
    form_keys = {keys.get(f, canonical_compare_key(f, language)) for f in forms}
    if language == "greek" and any(is_letter_numeral(t) for f in forms for t in f.split()):
        # Check numbers before punctuation/diacritic equivalence: η᾽ (eight)
        # and ἢ (or) otherwise share a key. Elided δ᾽ is not a numeral four.
        words = [f.split() for f in forms]
        if len({len(w) for w in words}) == 1:
            equivalent = True
            for column in zip(*words):
                if not any(is_letter_numeral(t) for t in column):
                    continue
                values = [_greek_letter_value(t) if is_letter_numeral(t)
                          else _greek_number_word_value(t) for t in column]
                written = {canonical_compare_key(t, language) for t in column if not is_letter_numeral(t)}
                if (None in values or len(set(values)) != 1
                        or (len(written) > 1 and not _greek_ortho_variant(written))):
                    equivalent = False
                    break
            # Phrases must also have identical aligned wording and order.
            if equivalent and (len(words[0]) == 1 or len(form_keys) == 1):
                return True, "Letter-numeral abbreviation matched to an attested number of the same value"
        # Multi-word Greek numeral phrases (e.g. Exod 30:23 σν᾽ = διακοσίους πεντήκοντα,
        # Num 2:31 ν᾽ ἑπτὰ = πεντηκονταεπτά, Num 29:15 ιδ᾽ = τέσσαρας καὶ δέκα, Judg 20:25 η᾽ καὶ ι᾽ = ὀκτωκαίδεκα).
        # Strict exact-integer match only; at least one side must be fully spelled out.
        spelled_forms = [f for f in forms if not any(is_letter_numeral(t) for t in f.split())]
        if spelled_forms:
            vals = [_greek_number_phrase_value(f) for f in forms]
            if None not in vals and len(set(vals)) == 1:
                spelled_keys = {keys.get(f, " ".join(canonical_compare_key(t, language) for t in f.split())) for f in spelled_forms}
                if len(spelled_keys) <= 1 or _greek_ortho_variant(spelled_keys, spelled_forms):
                    return True, "Letter-numeral abbreviation matched to an attested number of the same value"
        return False, "Numeral readings differ in value, wording, or cannot be verified as equivalent"
    if language == "latin" and any(is_latin_roman_numeral(f, allow_single_letter=True) for f in forms):
        has_spelled = any(not is_latin_roman_numeral(f, allow_single_letter=True) for f in forms)
        if has_spelled:
            vals = [_latin_number_phrase_value(f, allow_single_letter=True) for f in forms]
            if None not in vals and len(set(vals)) == 1:
                return True, "Roman-numeral abbreviation matched to an attested spelled-out Latin number of the same value"
    if len({strip_punct(f) for f in forms}) <= 1:
        return True, "Punctuation / spacing difference only"
    if len(form_keys) == 1:
        if language == "greek":
            if any(f.isupper() and len(strip_punct(f)) > 1 for f in forms):
                return True, "Diplomatic uncial capitalisation vs. critical mixed-case accentuation"
            if any(is_nomen_sacrum(f) for f in forms):
                return True, "Nomen sacrum (contracted sacred name) for the full word"
            accented = [f for f in forms if any(unicodedata.category(c) == "Mn" for c in unicodedata.normalize("NFD", f))]
            # Iota subscript marks the dative (γῆ / γῇ, μεγάλη / μεγάλῃ): a difference of case, not of accent.
            # Exclude strictly non-morphological stem subscripts (αἴρω aorist, κἀγώ, ἀθῷος, ζῷον, ᾠδή, σῴζω).
            if len(accented) > 1 and len({_subscript_positions(f) for f in accented}) > 1:
                if _non_morphological_iota_subscript(accented):
                    return True, "Non-morphological iota-subscript convention (αἴρω aorist / κἀγώ / ἀθῷος / ζῷον / ᾠδή / σῴζω)"
                return False, IOTA_SUBSCRIPT_NOTE
            acute_only = {unicodedata.normalize("NFC", unicodedata.normalize("NFD", strip_punct(f).lower()).replace("̀", "́")) for f in accented}
            if len(acute_only) > 1:
                return True, "Accent or breathing differs between accented editions (editorial interpretation)"
            return True, "Accentuation / capitalisation / breathing convention"
        if language == "latin":
            return True, "Latin orthographic convention (u/v, i/j, æ/ae, capitalisation)"
        if language == "hebrew":
            if any(_is_hebrew_ketiv_token(f) for f in forms):
                return True, "Ketiv (written form) given by both; MAM also prints the qere"
            return True, "Masoretic cantillation / meteg / qamats-qatan / divine-name pointing convention"
        return True, "Capitalisation / diacritic convention"

    words_per_form = {len(f.split()) for f in forms}
    if len(words_per_form) != 1:
        joined = {k.replace(" ", "") for k in form_keys}
        if len(joined) == 1:
            # Same letters, different word division (Greek OCR "αὖ. τοὺς" for αὐτοὺς; Hebrew פַּת בַּג / פַּתְבַּג)
            return True, "Word division differs (same letters written as one word or two)"
        if language == "hebrew":
            joined_raw = [f.replace(" ", "") for f in forms]
            if hebrew_pointing_convention(joined_raw):
                return True, "Word division differs (same letters written as one word or two, with boundary pointing convention)"
            if any(_is_hebrew_ketiv_token(f) for f in forms) and len({_hebrew_consonants(f) for f in forms}) == 1:
                return True, "Ketiv (written form) word division differs"
        if language == "greek":
            if words_per_form == {1, 2}:
                crasis_expanded = {
                    (" ".join(_GREEK_CRASIS[k]) if k in _GREEK_CRASIS else k)
                    for k in form_keys
                }
                if len(crasis_expanded) == 1:
                    return True, "Greek crasis (καὶ ἐγώ / κἀγώ type)"
                one_w = {k for k in form_keys if " " not in k}
                two_w = [k.split() for k in form_keys if len(k.split()) == 2]
                if two_w and all(_movable_nu_stem(re.sub(r"ν$", "", a)) for a, _b in two_w):
                    expanded = {re.sub(r"ν$", "", a) + mid + b for a, b in two_w for mid in ("", "ν")}
                    if one_w <= expanded and len({(re.sub(r"ν$", "", a), b) for a, b in two_w}) == 1:
                        return True, "Word division differs with movable ν (e.g. ἐπάταξεντὸν / ἐπάταξε τὸν)"
            ortho_reason = _greek_ortho_variant(joined, forms)
            if ortho_reason:
                if (
                    "itacistic" in ortho_reason.lower()
                    and min(len(j) for j in joined) < 8
                    and not any(len(strip_punct(w)) == 1 for f in forms for w in f.split())
                ):
                    return False, ""
                return True, f"Word division differs with spelling convention ({ortho_reason})"
        return False, ""
    if language == "greek":
        if all(len(f.split()) == 1 for f in forms):
            reason = _greek_ortho_variant(form_keys, forms)
            if reason:
                return True, reason
        else:
            raw_cols = list(zip(*[f.split() for f in forms]))
            key_cols = list(zip(*[keys.get(f, " ".join(canonical_compare_key(t, language) for t in f.split())).split() for f in forms]))
            if len(raw_cols) == len(key_cols):
                col_reasons: List[str] = []
                ok_all = True
                for rcol, kcol in zip(raw_cols, key_cols):
                    kset = set(kcol)
                    if len(kset) <= 1:
                        acc = [w for w in rcol if any(unicodedata.category(c) == "Mn" for c in unicodedata.normalize("NFD", w))]
                        if len(acc) > 1 and len({_subscript_positions(w) for w in acc}) > 1 and not _non_morphological_iota_subscript(acc):
                            ok_all = False
                            break
                        continue
                    r = _greek_ortho_variant(kset, rcol)
                    if not r:
                        ok_all = False
                        break
                    col_reasons.append(r)
                if ok_all and col_reasons:
                    return True, "; ".join(sorted(set(col_reasons)))
    elif language == "latin":
        if _latin_distinct(form_keys):
            return False, ""
        if len({" ".join(_latin_ortho_key(w) for w in k.split()) for k in form_keys}) == 1:
            return True, "Latin spelling variation (assimilation, aspiration, ae/e, -ci-/-ti- type)"
        if _latin_betacism(forms):
            return True, "b/u interchange (betacism); the Clementine spelling is printed — check the tense where it differs (delebit / delevit)"
    elif language == "hebrew":
        if len({_hebrew_matres_key(f) for f in forms}) == 1:
            return True, "Plene / defective spelling (mater lectionis)"
        reason = hebrew_pointing_convention(forms)
        if reason:
            return True, reason
        matres_forms = [" ".join(_hebrew_matres_key(w) for w in f.split()) for f in forms]
        matres_reason = hebrew_pointing_convention(matres_forms)
        if matres_reason:
            return True, "Plene / defective spelling with " + matres_reason[0].lower() + matres_reason[1:]
        # Pentateuchal Qere Perpetuum: (וְ|הַ)?הִוא vs (וְ|הַ)?הִיא (hiriq on ה — never masculine הוּא!)
        if all(len(f.split()) == 1 for f in forms):
            qp_keys = {re.sub(r"^(וְ|הַ|וְהַ)?הִוא$", r"\1הִיא", _hebrew_key(strip_punct(f))) for f in forms}
            if len(qp_keys) == 1 and any("הִוא" in _hebrew_key(strip_punct(f)) for f in forms):
                return True, "Pentateuchal Qere Perpetuum (הִוא / הִיא)"
        # Ketiv plene/defective match when one witness carries a parenthesised (ketiv) token
        if any(_is_hebrew_ketiv_token(f) for f in forms):
            wcols = list(zip(*[f.split() for f in forms]))
            if wcols and all(len({_hebrew_ketiv_defective(w) for w in col}) == 1 for col in wcols):
                return True, "Ketiv (written form) plene/defective spelling convention"
        # WLC bare unpointed ketiv that is a strict defective subset of MAM's pointed form (never ו↔י swap!)
        if all(len(f.split()) == len(forms[0].split()) for f in forms) and len(forms) == 2:
            w1s, w2s = forms[0].split(), forms[1].split()
            has_unpointed = (not _has_hebrew_niqqud(forms[0])) != (not _has_hebrew_niqqud(forms[1]))
            if has_unpointed:
                unp_ws, ptd_ws = (w1s, w2s) if not _has_hebrew_niqqud(forms[0]) else (w2s, w1s)
                if all(
                    _hebrew_consonants(u) == _hebrew_consonants(p) or _is_hebrew_defective_subset(u, p)
                    for u, p in zip(unp_ws, ptd_ws)
                ):
                    return True, "Unpointed defective ketiv against pointed qere (same consonants modulo internal matres)"
        # Biblical Aramaic final -א/-ה mater lectionis ONLY inside the 5 Biblical Aramaic pericopes!
        if is_aramaic and _aramaic_final_alef_he(forms):
            return True, "Biblical Aramaic final א/ה mater lectionis convention"
    return False, ""


def is_orthographic_equivalence(forms: List[str], language: str, *, is_aramaic: bool = False) -> Tuple[bool, str]:
    """Backwards-compatible wrapper: True if the forms differ only orthographically.
    An empty form means one witness omits the word, which is never orthographic."""
    if any(not strip_punct(f) for f in forms):
        return False, ""
    return classify_forms(
        forms,
        {f: " ".join(canonical_compare_key(t, language) for t in f.split()) for f in forms},
        language,
        is_aramaic=is_aramaic,
    )


def normalize_critical_token(raw_tok: str, is_sentence_start: bool, language: str, next_tok: str = "") -> str:
    """Normalise a few known uncial incipits and itacisms into standard critical orthography."""
    if language != "greek":
        return raw_tok
    m = re.match(r"^(\[?)([^\s.,;·:!?]+?)(\]?)([.,;·:!?]*)$", raw_tok)
    if not m:
        return raw_tok
    lbr, core, rbr, punct = m.groups()
    if core in _GREEK_INCIPIT_FALLBACK:
        repl = _GREEK_INCIPIT_FALLBACK[core]
        core = repl if is_sentence_start else repl[0].lower() + repl[1:]
    elif core.lower() in GREEK_ITACISM_CANONICAL:
        repl = GREEK_ITACISM_CANONICAL[core.lower()]
        if core[0].isupper() and not repl[0].isupper():
            repl = capitalize_first(repl)
        core = repl
    return f"{lbr}{core}{rbr}{punct}"


def capitalize_first(s: str) -> str:
    """Capitalise the first letter. str.title() on one character keeps ᾗ/ᾧ as one letter (ᾟ),
    where str.upper() would give two (ἯΙ)."""
    return s[:1].title() + s[1:] if s else s


def tokenize_for_alignment(text: str, language: str) -> List[str]:
    text = text.replace(DOUBTFUL_OPEN, " ").replace(DOUBTFUL_CLOSE, " ")
    if language == "hebrew":
        # Editions differ on whether words are joined by maqaf; compare word by word and keep
        # the maqaf on the first word (the brain rejoins "X־ Y" as "X־Y").
        text = text.replace("־", "־ ")
    return [t for t in text.split() if t and t != LACUNA_MARK and strip_punct(t) != "" or (t and language == "hebrew" and t == "׀")]


def split_words(text: str, language: str) -> List[str]:
    """Words as the apparatus counts them (Hebrew maqaf compounds count as separate words)."""
    if language == "hebrew":
        text = text.replace("־", "־ ")
    return text.split()


def join_words(words: List[str], language: str) -> str:
    line = " ".join(w for w in words if w).strip()
    if language == "hebrew":
        line = line.replace("־ ", "־")
    return line


def _resolve_nomina_sacra(tokens_by_sig: Dict[str, List[str]], keys_by_sig: Dict[str, List[str]]) -> None:
    """Replace the key of each contracted sacred name with the full-word key attested in the verse.

    A contraction such as ``ιυ`` matches a full word that starts with a nomen-sacrum stem
    (``ιησ…``), begins with the contraction's first letter, ends with its last letter, and contains
    the contraction's letters in order (``ιησου``)."""
    vocab: Dict[str, int] = {}
    for sig, toks in tokens_by_sig.items():
        for t, k in zip(toks, keys_by_sig[sig]):
            if not is_nomen_sacrum(t) and k.startswith(NOMINA_SACRA_STEMS):
                vocab[k] = vocab.get(k, 0) + 1

    def is_subseq(short: str, long: str) -> bool:
        it = iter(long)
        return all(c in it for c in short)

    for sig, toks in tokens_by_sig.items():
        for i, t in enumerate(toks):
            if not is_nomen_sacrum(t):
                continue
            c = keys_by_sig[sig][i]
            if len(c) < 2:
                continue
            matches = [w for w in vocab if w[0] == c[0] and w[-1] == c[-1] and len(w) > len(c) and is_subseq(c, w)]
            if matches:
                keys_by_sig[sig][i] = max(matches, key=lambda w: (vocab[w], -len(w)))


def _resolve_letter_numerals(tokens_by_sig: Dict[str, List[str]], keys_by_sig: Dict[str, List[str]]) -> None:
    """Align an abbreviation to its attested expansion, never to a different value.

    Distinct grammatical forms of the same number are ambiguous: leave the
    abbreviation unresolved instead of guessing its grammatical role. Known
    spelling equivalents such as τεσσαράκοντα / τεσσεράκοντα can share a key.
    """
    vocab: Dict[int, Set[str]] = {}
    for sig, tokens in tokens_by_sig.items():
        for token, key in zip(tokens, keys_by_sig[sig]):
            if not is_letter_numeral(token):
                value = _greek_number_word_value(token)
                if value is not None:
                    vocab.setdefault(value, set()).add(key)
    for sig, tokens in tokens_by_sig.items():
        for i, token in enumerate(tokens):
            if is_letter_numeral(token):
                matches = vocab.get(_greek_letter_value(token), set())
                if len(matches) == 1 or (matches and _greek_ortho_variant(matches)):
                    keys_by_sig[sig][i] = min(matches)
                else:
                    # Keep an unresolved numeral distinct from ordinary letters
                    # (η᾽ / ἢ) and from a different value (ςʹ = 6 / σʹ = 200).
                    keys_by_sig[sig][i] = f"num:{_greek_letter_value(token)}"


def _mark_hebrew_ketiv_qere_slots(built: List[Tuple[VariationSlot, Dict[str, Tuple[str, str]], bool]]) -> None:
    """Pre-merge pass for Hebrew Ketiv/Qere presentation (both '(ketiv) qere' and 'qere (ketiv)',
    including multi-word ketivs/qeres and 'Prov 31:27' where WLC prints only the qere).

    Runs strictly BEFORE _merge_variation_units() so unhandled Qere/Ketiv slots cannot glue onto
    adjacent genuine variants. Never folds non-omission Ketiv divergences (2 Kgs 6:25, Prov 23:24,
    Dan 3:5, Dan 7:23)."""
    n = len(built)
    if n < 2:
        return

    def is_paseq_or_bracket(sl: VariationSlot) -> bool:
        if sl.kind != "orthographic_noise" or "om." not in sl.raw_forms:
            return False
        pres = [f for f in sl.raw_forms if f != "om."]
        return all(
            all(w == "׀" or (w.startswith("[") and w.rstrip("׃").endswith("]")) for w in f.split())
            for f in pres
        )

    def ketiv_holders(sl: VariationSlot) -> Set[str]:
        return {s for f, sigs in sl.raw_forms.items() if f != "om." and _is_hebrew_ketiv_token(f) for s in sigs}

    def is_matched_ketiv(sl: VariationSlot) -> bool:
        return sl.kind != "substantive_variant" and "om." not in sl.raw_forms and bool(ketiv_holders(sl))

    def is_qere_om_slot(sl: VariationSlot, holders: Set[str]) -> bool:
        if sl.kind != "substantive_variant" or "om." not in sl.raw_forms:
            return False
        pres = [f for f in sl.raw_forms if f != "om."]
        if not pres or any(_is_hebrew_ketiv_token(f) for f in pres):
            return False
        pres_sigla = {s for f in pres for s in sl.raw_forms[f]}
        om_sigla = set(sl.raw_forms["om."])
        return bool(pres_sigla) and pres_sigla <= holders and bool(om_sigla - holders)

    # 1. Ketiv-only slot where WLC prints the Qere directly (e.g. Prov 31:27 '(הילכת)' vs 'om.' before 'הֲלִיכ֣וֹת')
    for i, (sl, _e, _ins) in enumerate(built):
        if sl.kind != "substantive_variant" or "om." not in sl.raw_forms:
            continue
        pres = [f for f in sl.raw_forms if f != "om."]
        if not pres or not all(all(_is_hebrew_ketiv_token(w) for w in f.split()) for f in pres):
            continue
        # Require an adjacent agreed slot (unanimous or orthographic non-omission) where the other witness prints Qere
        adj_agreed = False
        for step in (-1, 1):
            j = i + step
            while 0 <= j < n and is_paseq_or_bracket(built[j][0]):
                j += step
            if 0 <= j < n and built[j][0].kind != "substantive_variant" and "om." not in built[j][0].raw_forms:
                adj_agreed = True
                break
        if adj_agreed:
            sl.kind = "orthographic_noise"
            sl.notes = "Ketiv / qere presentation: MAM prints both ketiv and qere; WLC prints qere only"

    # 2. Contiguous matched Ketiv spans: mark adjacent Qere 'om.' slots (after or before, up to max(2, span_len) words)
    i = 0
    while i < n:
        if not is_matched_ketiv(built[i][0]):
            i += 1
            continue
        ks = i
        holders = ketiv_holders(built[i][0])
        while i + 1 < n and is_matched_ketiv(built[i + 1][0]) and (ketiv_holders(built[i + 1][0]) & holders):
            holders |= ketiv_holders(built[i + 1][0])
            i += 1
        ke = i
        max_qere = max(2, ke - ks + 1)
        # Prefer right side ((ketiv) qere), else left side (qere (ketiv))
        marked_any = False
        for step, start in ((1, ke + 1), (-1, ks - 1)):
            j = start
            taken = 0
            while 0 <= j < n and taken < max_qere:
                if is_paseq_or_bracket(built[j][0]):
                    j += step
                    continue
                if is_qere_om_slot(built[j][0], holders):
                    built[j][0].kind = "orthographic_noise"
                    built[j][0].notes = "Ketiv / qere presentation: MAM prints both written and read forms; WLC export carries ketiv only"
                    taken += 1
                    marked_any = True
                    j += step
                else:
                    break
            if marked_any:
                break
        i += 1


def align_witnesses_for_verse(
    verse_num: int,
    witness_texts: Dict[str, str],
    witness_weights: Dict[str, float],
    language: str,
    external_apparatus: List[str] | None = None,
    pivot_preference: Optional[List[str]] = None,
    book_slug: str = "",
    chapter: int = 0,
) -> CollatedVerse:
    """Align all witness texts for one verse into word/phrase variation slots."""
    cv = CollatedVerse(
        verse=verse_num,
        witness_texts=witness_texts,
        witness_weights=witness_weights,
        external_apparatus=external_apparatus or [],
        book_slug=book_slug,
        chapter=chapter,
    )
    if not witness_texts:
        return cv

    is_aramaic = language == "hebrew" and is_biblical_aramaic_verse(book_slug, chapter, verse_num)
    tokens_by_sig = {sig: tokenize_for_alignment(txt, language) for sig, txt in witness_texts.items()}
    keys_by_sig = {sig: [canonical_compare_key(t, language) for t in toks] for sig, toks in tokens_by_sig.items()}
    if language == "greek":
        _resolve_nomina_sacra(tokens_by_sig, keys_by_sig)
        _resolve_letter_numerals(tokens_by_sig, keys_by_sig)
    # "…" = lost text of unknown extent (the witness's omissions in this verse are not evidence);
    # "[…]" = one known lost/illegible word, handled per slot below.
    fragmentary = {sig for sig, txt in witness_texts.items() if LACUNA_MARK in txt.replace(GAP_WORD, "")}
    # A lacuna only at the start or end of a witness's verse (words lost at a chapter break) silences
    # just that edge: the witness's omissions elsewhere in the verse still count.
    edge: Dict[str, Tuple[bool, bool]] = {}
    for sig in list(fragmentary):
        toks = [t for t in witness_texts[sig].replace(GAP_WORD, "").split() if t]
        inner = toks[1:-1] if len(toks) > 1 else []
        if toks and LACUNA_MARK not in inner and any(t != LACUNA_MARK for t in toks):
            edge[sig] = (toks[0] == LACUNA_MARK, toks[-1] == LACUNA_MARK and len(toks) > 1)
            fragmentary.discard(sig)
    cv.fragmentary_witnesses = sorted(fragmentary)

    ordered_sigla = sorted(witness_texts.keys(), key=lambda s: (-witness_weights.get(s, 0.5), s))
    preferred = [s for s in (pivot_preference or []) if s in tokens_by_sig and tokens_by_sig[s]]
    preferred_clean = [s for s in preferred if GAP_WORD not in tokens_by_sig[s]]
    complete = [s for s in ordered_sigla if s not in fragmentary and tokens_by_sig[s]]
    complete_clean = [s for s in complete if GAP_WORD not in tokens_by_sig[s]]
    pivot_sig = (preferred_clean or complete_clean or preferred or complete or ordered_sigla)[0]
    others = [s for s in ordered_sigla if s != pivot_sig]
    pivot_tokens = tokens_by_sig[pivot_sig]
    pivot_keys = keys_by_sig[pivot_sig]

    n = len(pivot_tokens)
    pos_map: List[Dict[str, Tuple[str, str]]] = [{pivot_sig: (pivot_tokens[i], pivot_keys[i])} for i in range(n)]
    ins_map: List[Dict[str, Tuple[str, str]]] = [{} for _ in range(n + 1)]

    for sig in others:
        w_tokens, w_keys = tokens_by_sig[sig], keys_by_sig[sig]
        matcher = difflib.SequenceMatcher(a=pivot_keys, b=w_keys, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for off in range(i2 - i1):
                    pos_map[i1 + off][sig] = (w_tokens[j1 + off], w_keys[j1 + off])
            elif tag == "replace":
                p_len, w_len = i2 - i1, j2 - j1
                w_slice = w_tokens[j1:j2]
                wk_slice = w_keys[j1:j2]
                # Never fabricate an omission vote or discard a witness's readable word when a
                # replace span contains GAP_WORD ([…]) — fixes Gen 40:13, Gen 1:29, Gen 9:19.
                if GAP_WORD in w_slice:
                    if p_len > w_len:
                        # Align leading non-gap tokens from left, trailing non-gap tokens from right,
                        # and fill the remaining pivot positions with GAP_WORD (no vote), never "".
                        left = 0
                        while left < w_len and w_slice[left] != GAP_WORD:
                            pos_map[i1 + left][sig] = (w_slice[left], wk_slice[left])
                            left += 1
                        right = 0
                        while right < w_len - left and w_slice[w_len - 1 - right] != GAP_WORD:
                            pos_map[i2 - 1 - right][sig] = (w_slice[w_len - 1 - right], wk_slice[w_len - 1 - right])
                            right += 1
                        for pos_idx in range(i1 + left, i2 - right):
                            pos_map[pos_idx][sig] = (GAP_WORD, GAP_WORD)
                    elif w_len > p_len and w_slice[-1] == GAP_WORD and p_len >= 2:
                        # Trailing gap pairs with the last pivot slot; preceding non-gap words stay intact (Gen 1:29)
                        pos_map[i2 - 1][sig] = (GAP_WORD, GAP_WORD)
                        rem_p = p_len - 1
                        rem_w = w_len - 1
                        common_r = min(rem_p, rem_w)
                        for off in range(common_r):
                            pos_map[i1 + off][sig] = (w_slice[off], wk_slice[off])
                        if rem_w > rem_p:
                            target = i1 + common_r - 1
                            tok, key = pos_map[target][sig]
                            extra_t = " ".join(w_slice[common_r:rem_w])
                            extra_k = " ".join(wk_slice[common_r:rem_w])
                            pos_map[target][sig] = ((tok + " " + extra_t).strip(), (key + " " + extra_k).strip())
                    elif w_len > p_len and w_slice[0] == GAP_WORD and p_len == 1 and sig not in ins_map[i2]:
                        # Leading gap covers the pivot word; readable trailing word(s) sit as insertion (Gen 9:19)
                        pos_map[i1][sig] = (GAP_WORD, GAP_WORD)
                        ins_map[i2][sig] = (" ".join(w_slice[1:]), " ".join(wk_slice[1:]))
                    elif w_len > p_len and w_slice[0] == GAP_WORD and p_len >= 2:
                        pos_map[i1][sig] = (GAP_WORD, GAP_WORD)
                        rem_p = p_len - 1
                        rem_w = w_len - 1
                        common_r = min(rem_p, rem_w)
                        for off in range(common_r):
                            pos_map[i1 + 1 + off][sig] = (w_slice[1 + off], wk_slice[1 + off])
                        if rem_w > rem_p:
                            target = i1 + common_r
                            tok, key = pos_map[target][sig]
                            extra_t = " ".join(w_slice[1 + common_r:])
                            extra_k = " ".join(wk_slice[1 + common_r:])
                            pos_map[target][sig] = ((tok + " " + extra_t).strip(), (key + " " + extra_k).strip())
                    else:
                        common = min(p_len, w_len)
                        for off in range(common):
                            pos_map[i1 + off][sig] = (w_slice[off], wk_slice[off])
                        if w_len > p_len:
                            target = i1 + common - 1
                            tok, key = pos_map[target][sig]
                            extra_t = " ".join(w_slice[common:])
                            extra_k = " ".join(wk_slice[common:])
                            pos_map[target][sig] = ((tok + " " + extra_t).strip(), (key + " " + extra_k).strip())
                elif (language == "hebrew" and p_len >= 2 and w_len == 1
                        and _is_hebrew_ketiv_token(pivot_tokens[i2 - 1])
                        and _hebrew_ketiv_defective(pivot_tokens[i2 - 1]) == _hebrew_ketiv_defective(w_slice[0])):
                    # Hebrew 'qere (ketiv)' vs plene/defective WLC ketiv (e.g. Judg 1:27, Ps 105:28,
                    # Ezek 16:25, 2 Kgs 18:27): align WLC's ketiv onto the pivot's (ketiv) slot.
                    for off in range(p_len - 1):
                        pos_map[i1 + off][sig] = ("", "")
                    pos_map[i2 - 1][sig] = (w_slice[0], wk_slice[0])
                else:
                    common = min(p_len, w_len)
                    for off in range(common):
                        pos_map[i1 + off][sig] = (w_tokens[j1 + off], w_keys[j1 + off])
                    if p_len > w_len:
                        for off in range(common, p_len):
                            pos_map[i1 + off][sig] = ("", "")
                    elif w_len > p_len:
                        # Attach the extra words to the last replaced token so phrase variants stay coherent
                        target = i1 + common - 1
                        tok, key = pos_map[target][sig]
                        extra_t = " ".join(w_tokens[j1 + common: j2])
                        extra_k = " ".join(w_keys[j1 + common: j2])
                        pos_map[target][sig] = ((tok + " " + extra_t).strip(), (key + " " + extra_k).strip())
            elif tag == "delete":
                for i in range(i1, i2):
                    pos_map[i][sig] = ("", "")
            elif tag == "insert":
                ins_map[i1][sig] = (" ".join(w_tokens[j1:j2]), " ".join(w_keys[j1:j2]))

    def build_slot(entries: Dict[str, Tuple[str, str]], idx: int, insertion: bool) -> Optional[VariationSlot]:
        raw_by_form: Dict[str, List[str]] = {}
        stripped_by_form: Dict[str, List[str]] = {}
        form_keys: Dict[str, str] = {}
        skip = set(entries.get(_SKIP_KEY, ("", ""))[0].split("|")) if _SKIP_KEY in entries else set()
        for sig in ordered_sigla:
            if sig in skip or (sig not in entries and not insertion):
                continue
            raw, key = entries.get(sig, ("", ""))
            if not raw and sig in fragmentary:
                continue  # a lacuna is not evidence of omission
            if GAP_WORD in raw:
                continue  # an illegible or editor-supplied word casts no vote
            disp_raw = raw or "om."
            raw_by_form.setdefault(disp_raw, []).append(sig)
            stripped = " ".join(strip_punct(x) for x in raw.split()).strip() if raw else "om."
            stripped = stripped or raw or "om."
            stripped_by_form.setdefault(stripped, []).append(sig)
            form_keys[disp_raw] = key if raw else "om."
            form_keys[stripped] = key if raw else "om."
        if not raw_by_form or (insertion and set(raw_by_form) == {"om."}):
            return None
        present = [f for f in raw_by_form if f != "om."]
        if len(raw_by_form) == 1:
            kind, note = "unanimous", ""
        elif language == "hebrew" and "om." in raw_by_form and all(set(f.split()) <= {"׀"} for f in present):
            kind, note = "orthographic_noise", "Paseq / legarmeh stroke (an accent sign) printed by one edition only"
        elif language == "hebrew" and "om." in raw_by_form and all(
            all(w.startswith("[") and w.rstrip("׃").endswith("]") for w in f.split()) for f in present
        ):
            kind, note = "orthographic_noise", "Qere wela ketiv (read but not written): MAM prints it in brackets, the WLC export omits it"
        elif "om." in raw_by_form:
            kind = "substantive_variant"
            note = "Addition / omission between witnesses" if insertion else "Omission in some witnesses"
        else:
            is_ortho, reason = classify_forms(raw_by_form.keys(), form_keys, language, is_aramaic=is_aramaic)
            kind, note = ("orthographic_noise", reason) if is_ortho else ("substantive_variant", "Lexical, morphological, or word-order variant")
            if reason == IOTA_SUBSCRIPT_NOTE:
                # Same letters, but the subscript makes it another case: give it its own key so it is weighed.
                note = reason
                for f in list(raw_by_form):
                    if _subscript_positions(f):
                        stripped_f = " ".join(strip_punct(x) for x in f.split()).strip() or f
                        words, wkeys = f.split(), form_keys.get(f, "").split()
                        if len(words) == len(wkeys):
                            # mark each word that carries a subscript, so τῆ ἡμέρᾳ and τῇ ἡμέρᾳ stay apart
                            form_keys[f] = " ".join(k + ("ι" if _subscript_positions(w) else "") for w, k in zip(words, wkeys))
                        else:
                            form_keys[f] = form_keys.get(f, "") + "ι"
                        form_keys[stripped_f] = form_keys[f]
            if not is_ortho and language == "hebrew":
                skeletons = {"".join(c for c in strip_punct(f) if "א" <= c <= "ת") for f in raw_by_form}
                if len(skeletons) == 1:
                    note = "Vocalisation / pointing difference (same consonantal text)"
        return VariationSlot(index=idx, readings=stripped_by_form, raw_forms=raw_by_form, kind=kind, notes=note, form_keys=form_keys, is_insertion=insertion)

    # The edge region of each edge-lacuna witness: pivot positions before its first word / after its last.
    first_pos: Dict[str, int] = {}
    last_pos: Dict[str, int] = {}
    for sig in edge:
        here = [i for i in range(n) if pos_map[i].get(sig, ("", ""))[0]]
        first_pos[sig], last_pos[sig] = (here[0], here[-1]) if here else (n, -1)

    def silence(entries: Dict[str, Tuple[str, str]], i: int, insertion: bool) -> Dict[str, Tuple[str, str]]:
        quiet = []
        for sig, (at_start, at_end) in edge.items():
            raw, key = entries.get(sig, ("", ""))
            if raw:
                # a word cut off at the lacuna (Gen 8:22 'κατα' for καταπαύσουσι) is no evidence either
                others = [k for s2, (r2, k2) in entries.items() if s2 != sig and s2 != _SKIP_KEY and r2 for k in [k2]]
                nu = lambda w: re.sub(r"ν$", "", w)  # noqa: E731
                kw = key.split()
                cut_end = at_end and not insertion and i == last_pos[sig] and len(key) >= 3 and any(
                    o != key and (o.split()[0].startswith(kw[-1])
                                  # the others go on past the witness's last word (Exod 5:23 ἐκάκωσεν | ἐκάκωσε τὸν λαὸν…)
                                  or (len(o.split()) > len(kw) and [nu(w) for w in o.split()[:len(kw)]] == [nu(w) for w in kw]))
                    for o in others if o)
                cut_start = at_start and not insertion and i == first_pos[sig] and len(key) >= 3 and any(
                    o != key and o.split()[-1].endswith(key.split()[0]) for o in others if o)
                if cut_end or cut_start:
                    quiet.append(sig)
                continue
            lead = at_start and (i <= first_pos[sig] if insertion else i < first_pos[sig])
            trail = at_end and i > last_pos[sig]
            if lead or trail:
                quiet.append(sig)
        if not quiet:
            return entries
        out = {k: v for k, v in entries.items() if k not in quiet}
        out[_SKIP_KEY] = ("|".join(quiet), "")
        return out

    slot_entries: List[Tuple[Dict[str, Tuple[str, str]], bool]] = []
    for i in range(n + 1):
        if ins_map[i] or (edge and i in (0, n)):
            ins = silence(ins_map[i], i, True) if edge else ins_map[i]
            if ins_map[i]:
                slot_entries.append((ins, True))
        if i == n:
            break
        slot_entries.append((silence(pos_map[i], i, False) if edge else pos_map[i], False))

    built = [(build_slot(e, 0, insertion=ins), e, ins) for e, ins in slot_entries]
    built = [(s, e, ins) for s, e, ins in built if s]
    if language == "hebrew":
        _mark_hebrew_ketiv_qere_slots(built)
    merged = _merge_variation_units(built, ordered_sigla, fragmentary, build_slot)
    for slot_idx, slot in enumerate(merged):
        slot.index = slot_idx
        cv.slots.append(slot)
    return cv


MAX_MERGED_UNIT_WORDS = 8
_SKIP_KEY = "<silent>"  # entries key listing witnesses that cast no vote in a slot (edge lacuna)


def _partition(entries: Dict[str, Tuple[str, str]], sigla: List[str], insertion: bool) -> Optional[frozenset]:
    groups: Dict[str, Set[str]] = {}
    for sig in sigla:
        if sig not in entries and not insertion:
            return None
        _raw, key = entries.get(sig, ("", ""))
        groups.setdefault(key or "om.", set()).add(sig)
    return frozenset(frozenset(g) for g in groups.values())


def _merge_variation_units(built, sigla: List[str], fragmentary: Set[str], build_slot) -> List[VariationSlot]:
    """Join neighbouring substantive slots that divide the witnesses in exactly the same way into
    one variation unit, as a printed apparatus does — also across one agreed word between them.

    Without this, an omitted clause becomes one unit per word (1 John 2:23), a transposition becomes
    an addition plus an omission (Matthew 1:18), and eye-skip or parallels cannot be recognised."""
    usable = [s for s in sigla if s not in fragmentary]
    out: List[VariationSlot] = []
    i = 0
    while i < len(built):
        slot, entries, ins = built[i]
        if slot.kind != "substantive_variant":
            out.append(slot)
            i += 1
            continue
        part = _partition(entries, usable, ins)
        acc = dict(entries)
        j = i
        while part is not None:
            nxt = built[j + 1] if j + 1 < len(built) else None
            after = built[j + 2] if j + 2 < len(built) else None
            take: List[Tuple[Dict[str, Tuple[str, str]], bool]] = []
            if nxt and nxt[0].kind == "substantive_variant" and _partition(nxt[1], usable, nxt[2]) == part:
                take = [(nxt[1], nxt[2])]
            elif (
                nxt and after and nxt[0].kind != "substantive_variant" and after[0].kind == "substantive_variant"
                and _partition(after[1], usable, after[2]) == part
            ):
                take = [(nxt[1], nxt[2]), (after[1], after[2])]
            if not take:
                break
            candidate = dict(acc)
            for e, e_ins in take:
                for sig in sigla:
                    a_raw, a_key = candidate.get(sig, ("", ""))
                    b_raw, b_key = e.get(sig, ("", ""))
                    candidate[sig] = ((a_raw + " " + b_raw).strip(), (a_key + " " + b_key).strip())
                # a witness silenced at a lacuna stays silent only if it is silent in both parts
                both = set(candidate.get(_SKIP_KEY, ("", ""))[0].split("|")) & set(e.get(_SKIP_KEY, ("", ""))[0].split("|"))
                both.discard("")
                candidate.pop(_SKIP_KEY, None)
                if both:
                    candidate[_SKIP_KEY] = ("|".join(sorted(both)), "")
                for sig in both:
                    candidate.pop(sig, None)
            longest = max((len(v[0].split()) for v in candidate.values()), default=0)
            if longest > MAX_MERGED_UNIT_WORDS:
                break
            acc = candidate
            j += len(take)
        if j > i:
            merged = build_slot(acc, 0, insertion=True)
            if merged:
                if merged.kind == "substantive_variant":
                    merged.notes = "Variation unit spanning several words"
                out.append(merged)
            i = j + 1
        else:
            out.append(slot)
            i += 1
    return out


# ---------------------------------------------------------------------------
# Verse-number (versification) alignment between witnesses
# ---------------------------------------------------------------------------

_KEYSET_MEMO: Dict[Tuple[str, str], frozenset] = {}


def _keyset(text: str, language: str) -> frozenset:
    memo_key = (language, text)
    ks = _KEYSET_MEMO.get(memo_key)
    if ks is None:
        if len(_KEYSET_MEMO) > 50000:
            _KEYSET_MEMO.clear()
        ks = frozenset(
            k for t in text.split()
            if t not in (LACUNA_MARK, GAP_WORD)
            for k in (canonical_compare_key(t, language),) if k
        )
        _KEYSET_MEMO[memo_key] = ks
    return ks


def _hebrew_consonant_keyset(text: str) -> frozenset:
    """Consonantal word set for aligning unpointed Hebrew witnesses (DSS, Samaritan Pentateuch, Ben Sira)
    against pointed Masoretic anchors without losing maqqef-joined words."""
    words: Set[str] = set()
    for w in text.replace("־", " ").split():
        cons = "".join(ch for ch in unicodedata.normalize("NFD", w) if "\u05d0" <= ch <= "\u05ea")
        if cons:
            # Fold internal matres lectionis (keeping initial and final letters) so Qumran plene spelling aligns cleanly.
            folded = "".join(ch for i, ch in enumerate(cons) if i == 0 or i == len(cons) - 1 or ch not in "וי")
            words.add(folded or cons)
    return frozenset(words)


def _has_hebrew_niqqud(text: str) -> bool:
    # Only Hebrew vowel points (U+05B0–U+05BB, U+05C7); never sof pasuq (U+05C3) or maqqef (U+05BE).
    return any((0x05B0 <= ord(ch) <= 0x05BB) or ord(ch) == 0x05C7 for ch in text)


def verse_similarity(a: str, b: str, language: str) -> float:
    """Dice coefficient on canonical word keys (0..1)."""
    if language.lower() == "hebrew" and (_has_hebrew_niqqud(a) != _has_hebrew_niqqud(b) or not _has_hebrew_niqqud(a)):
        ka, kb = _hebrew_consonant_keyset(a), _hebrew_consonant_keyset(b)
    else:
        ka, kb = _keyset(a, language), _keyset(b, language)
    if not ka or not kb:
        return 0.0
    return 2 * len(ka & kb) / (len(ka) + len(kb))


REMAP_MIN = 0.5             # content match needed to move a verse to a different number
SAME_NUMBER_BONUS = 0.1     # a same-numbered verse must be beaten by this much to be displaced
SAME_NUMBER_FLOOR = 0.15    # below this, a same-numbered verse is treated as a different verse


def align_versification(
    reference: Dict[int, str],
    chapter: int,
    candidates: Dict[Tuple[int, int], str],
    language: str,
    same_number_floor: float = SAME_NUMBER_FLOOR,
    neighbour_reference: Optional[Dict[Tuple[int, int], str]] = None,
) -> Tuple[Dict[int, str], Dict[int, str], List[str]]:
    """Map one witness's verses onto the reference chapter's verse numbers by content.

    ``candidates`` holds the witness's verses from this and neighbouring chapters keyed by
    ``(chapter, verse)``. Every (reference verse, candidate verse) pair is scored by word overlap,
    with a small bonus for the same number, and pairs are assigned best-first so a near-identical
    match always wins over a merely similar one (formulaic chapters such as the census lists of
    Numbers 1). Absent markers (empty strings) only map to the same number.
    Returns ``(mapped_texts, own_refs_for_moved_verses, notes)``."""
    mapped: Dict[int, str] = {}
    moved: Dict[int, str] = {}
    notes: List[str] = []
    used: Set[Tuple[int, int]] = set()
    # Formulaic verses can resemble a different chapter more than a damaged
    # same-numbered transcription does. A strong, better match to any verse in
    # the neighbour's own anchor chapter (even when that chapter has an internal
    # verse-number offset, e.g. Exod 40:8 -> 40:10, 1 Chr 6:20 -> 6:5, or DSS
    # scrolls Deut 5:16 / Ps 149:9) protects it from being stolen across chapters.
    nb_by_ch: Dict[int, List[str]] = {}
    for (nc, _nv), ntxt in (neighbour_reference or {}).items():
        if ntxt:
            nb_by_ch.setdefault(nc, []).append(ntxt)
    own_scores: Dict[Tuple[int, int], float] = {}
    for ck, txt in candidates.items():
        if ck[0] != chapter and txt:
            same_num = (neighbour_reference or {}).get(ck, "")
            s_exact = verse_similarity(txt, same_num, language) if same_num else 0.0
            s_ch = max((verse_similarity(txt, ntxt, language) for ntxt in nb_by_ch.get(ck[0], ())), default=0.0)
            own_scores[ck] = max(s_exact, s_ch)
    cross_nb_scores: Dict[Tuple[int, int], float] = {}
    if neighbour_reference:
        same_ch_v = [v for c, v in candidates if c == chapter and candidates[(c, v)]]
        edge_v = ({min(same_ch_v), max(same_ch_v)} if same_ch_v else set())
        for v_edge in edge_v:
            txt_edge = candidates[(chapter, v_edge)]
            cross_nb_scores[(chapter, v_edge)] = max(
                (verse_similarity(txt_edge, nb_txt, language) for nb_txt in neighbour_reference.values() if nb_txt),
                default=0.0,
            )
    protected: Set[Tuple[int, int]] = set()

    pairs: List[Tuple[float, int, int, Tuple[int, int]]] = []
    for v, ref_txt in reference.items():
        if not ref_txt:
            continue
        for ck, txt in candidates.items():
            if not txt:
                continue
            same = ck == (chapter, v)
            s = verse_similarity(ref_txt, txt, language)
            if own_scores.get(ck, 0.0) >= 0.6 and own_scores[ck] > s:
                protected.add(ck)
                continue
            if cross_nb_scores.get(ck, 0.0) >= 0.85 and s < 0.5 and cross_nb_scores[ck] > s + SAME_NUMBER_BONUS:
                protected.add(ck)
                continue
            if (same and s >= same_number_floor) or s >= REMAP_MIN:
                pairs.append((s + (SAME_NUMBER_BONUS if same else 0.0), 1 if same else 0, v, ck))
    target_of: Dict[Tuple[int, int], int] = {}
    for _score, _same, v, ck in sorted(pairs, key=lambda p: (-p[0], -p[1], p[2])):
        if v in mapped or ck in used:
            continue
        mapped[v] = candidates[ck]
        used.add(ck)
        target_of[ck] = v
        if ck != (chapter, v):
            moved[v] = f"{ck[0]}:{ck[1]}"
    # Protected neighbours must not re-enter through leftover/folding repairs.
    candidates = {ck: txt for ck, txt in candidates.items() if ck not in protected or ck in used}
    notes.extend(f"{c}:{v} kept in its own chapter (stronger match to its own reference verse)"
                 for c, v in sorted(protected - used))

    # A witness verse left without a partner whose words the reference prints inside the verse its
    # neighbour was matched to (the witness divides the text more finely: Swete's Joshua 9:3-8 are
    # Brenton's 9:2, RP's 2 Cor 13:13 is SBLGNT's 13:12b): fold it into that verse instead of
    # dropping it, so the witness is not counted as omitting words it prints.
    def fold(order: List[Tuple[int, int]], step: int) -> None:
        for ck in order:
            txt = candidates.get(ck, "")
            if ck in used or not txt:
                continue
            # the nearest non-empty neighbour (Swete's Prov 24:23 is empty between 24:22 and 24:24)
            nb = (ck[0], ck[1] - step)
            if nb not in target_of and not candidates.get(nb) and (ck[0], ck[1] - 2 * step) in target_of:
                nb = (ck[0], ck[1] - 2 * step)
            if nb not in target_of and step == 1 and ck[1] == 1:
                # across the chapter break: the previous chapter's last verse
                prev_ch = [v for c, v in candidates if c == ck[0] - 1]
                nb = (ck[0] - 1, max(prev_ch)) if prev_ch else nb
            if nb not in target_of and step == -1 and not any(c == ck[0] and v > ck[1] for c, v in candidates):
                nb = (ck[0] + 1, 1)
            u = target_of.get(nb)
            if u is None or not reference.get(u):
                continue
            keys, ref_keys = _keyset(txt, language), _keyset(reference[u], language)
            if not keys or len(keys & ref_keys) / len(keys) < 0.6:
                continue
            joined = f"{mapped[u]} {txt}" if step == 1 else f"{txt} {mapped[u]}"
            if verse_similarity(reference[u], joined, language) <= verse_similarity(reference[u], mapped[u], language):
                continue
            mapped[u] = joined
            used.add(ck)
            target_of[ck] = u
            if nb != (chapter, u):
                moved.setdefault(u, f"{nb[0]}:{nb[1]}")
            notes.append(f"{ck[0]}:{ck[1]} folded into verse {u} (the reference prints these words there)")

    fold(sorted(candidates), 1)
    fold(sorted(candidates, reverse=True), -1)

    # A short leftover whose words one reference verse prints and the witness's copy of that verse
    # lacks (Swete's Sir 33:16 "Κἀγὼ ἔσχατος ἠγρύπνησα" is the start of Brenton's 36:16).
    for ck in sorted(candidates):
        txt = candidates.get(ck, "")
        if ck in used or not txt:
            continue
        keys = _keyset(txt, language)
        if len(keys) < 2 or len(txt.split()) > 25:
            continue
        best_u = None
        for u, ref_txt in reference.items():
            if not ref_txt or u not in mapped or not mapped[u]:
                continue
            ref_keys, have = _keyset(ref_txt, language), _keyset(mapped[u], language)
            if len(keys & ref_keys) / len(keys) >= 0.7 and len(keys & have) / len(keys) < 0.5:
                gain = max(verse_similarity(ref_txt, f"{txt} {mapped[u]}", language),
                           verse_similarity(ref_txt, f"{mapped[u]} {txt}", language)) - verse_similarity(ref_txt, mapped[u], language)
                if gain > 0 and (best_u is None or gain > best_u[0]):
                    best_u = (gain, u)
        if best_u:
            u = best_u[1]
            rk_seq = [k for k in (canonical_compare_key(w, language) for w in reference[u].split()) if k]
            b_seq = [k for k in (canonical_compare_key(w, language) for w in f"{txt} {mapped[u]}".split()) if k]
            a_seq = [k for k in (canonical_compare_key(w, language) for w in f"{mapped[u]} {txt}".split()) if k]
            before = difflib.SequenceMatcher(a=rk_seq, b=b_seq, autojunk=False).ratio()
            after = difflib.SequenceMatcher(a=rk_seq, b=a_seq, autojunk=False).ratio()
            mapped[u] = f"{txt} {mapped[u]}" if before > after else f"{mapped[u]} {txt}"
            used.add(ck)
            target_of[ck] = u
            notes.append(f"{ck[0]}:{ck[1]} folded into verse {u} (the reference prints these words there)")

    for v, ref_txt in reference.items():
        if v in mapped:
            continue
        ck = (chapter, v)
        if ck in used or ck not in candidates:
            continue
        txt = candidates[ck]
        if txt == "" or ref_txt == "":
            mapped[v] = txt  # verse-absent marker, or nothing to compare against
            used.add(ck)
        else:
            notes.append(f"{chapter}:{v} not collated (wording does not match the reference verse)")

    # Verses of this chapter the reference does not have at all (e.g. Romans 16:25–27); never a "verse 0".
    # Skip chapter-boundary leftovers whose wording already appears as an anchor verse in an adjacent
    # chapter (e.g. Swete 1 Sam 20:43 = Brenton 21:1, Num 16:44 = 17:9, Ezek 20:45 = 21:1, Joel 3:15 = 4:15).
    for (c, v), txt in candidates.items():
        if c == chapter and v > 0 and (c, v) not in used and v not in reference and v not in mapped:
            if neighbour_reference and txt:
                nb_hit = max(
                    (verse_similarity(txt, nb_t, language) for nb_t in neighbour_reference.values() if nb_t),
                    default=0.0,
                )
                if nb_hit >= 0.65:
                    notes.append(f"{c}:{v} kept for its neighbouring chapter (matches anchor verse there)")
                    continue
            mapped[v] = txt
            used.add((c, v))
    # Nothing disappears silently: a verse of this chapter that found no place is logged.
    for (c, v), txt in sorted(candidates.items()):
        if c == chapter and txt and (c, v) not in used and not any(n.startswith(f"{c}:{v} ") for n in notes):
            notes.append(f"{c}:{v} not collated (no verse of the reference matches its wording)")
    return mapped, moved, notes
