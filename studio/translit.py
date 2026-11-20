"""English-friendly Latinized transliteration for Biblical Greek, Hebrew & Aramaic.

100% offline, stdlib-only, deterministic.  Designed so English speakers studying the
Saints Critical Text Studio (Library Reader, Collation Workbench, and Saints Concordance)
can pronounce Greek, Hebrew, and Aramaic verses, lemmas, and consonantal roots directly in
plain Latin letters—and search the Concordance by transliteration (e.g. ``logos``,
``bereshit``, ``ruach``, ``elohim``, ``agape``, ``pneuma``, ``shalom``).
"""

from __future__ import annotations

import re
import unicodedata
from typing import List, Tuple

# ===========================================================================
# 1. BIBLICAL GREEK -> ENGLISH-FRIENDLY LATINIZED ALPHABET
# ===========================================================================

_GRC_COMB_ROUGH = "\u0314"       # combining reversed comma above (dasia / rough breathing)
_GRC_COMB_SMOOTH = "\u0313"      # combining comma above (psili / smooth breathing)
_GRC_COMB_DIAERESIS = "\u0308"   # combining diaeresis (breaks diphthong)
_GRC_COMB_IOTA_SUB = "\u0345"    # combining ypogegrammeni (iota subscript)

_GRC_SINGLE = {
    "α": "a", "β": "b", "γ": "g", "δ": "d", "ε": "e", "ζ": "z",
    "η": "e", "θ": "th", "ι": "i", "κ": "k", "λ": "l", "μ": "m",
    "ν": "n", "ξ": "x", "ο": "o", "π": "p", "ρ": "r", "σ": "s",
    "ς": "s", "τ": "t", "υ": "y", "φ": "ph", "χ": "ch", "ψ": "ps",
    "ω": "o",
    # Rare archaic letters / stigma if encountered in numerals
    "ϝ": "w", "ϛ": "st", "ϟ": "q", "ϡ": "s",
}

_GRC_DIPHTHONGS = {
    ("α", "ι"): "ai",
    ("ε", "ι"): "ei",
    ("ο", "ι"): "oi",
    ("υ", "ι"): "ui",
    ("α", "υ"): "au",
    ("ε", "υ"): "eu",
    ("η", "υ"): "eu",
    ("ο", "υ"): "ou",
}

_GRC_GAMMA_NASAL_NEXT = frozenset({"γ", "κ", "ξ", "χ"})

_GRC_WORD_RE = re.compile(r"[\u0370-\u03FF\u1F00-\u1FFF]+")


def _decompose_greek_clusters(word: str) -> List[Tuple[str, bool, bool, bool]]:
    """Split a Greek word into (base_lower, is_upper, has_rough, has_diaeresis) clusters."""
    nfd = unicodedata.normalize("NFD", word)
    clusters: List[Tuple[str, bool, bool, bool]] = []
    i = 0
    n = len(nfd)
    while i < n:
        ch = nfd[i]
        if unicodedata.combining(ch):
            i += 1
            continue
        is_up = ch.isupper()
        base = ch.lower()
        rough = False
        diaer = False
        i += 1
        while i < n and unicodedata.combining(nfd[i]):
            m = nfd[i]
            if m == _GRC_COMB_ROUGH:
                rough = True
            elif m == _GRC_COMB_DIAERESIS:
                diaer = True
            i += 1
        clusters.append((base, is_up, rough, diaer))
    return clusters


def _apply_case(piece: str, first_upper: bool, all_upper: bool) -> str:
    if not piece:
        return piece
    if all_upper:
        return piece.upper()
    if first_upper:
        return piece[0].upper() + piece[1:]
    return piece


def _translit_greek_word(word: str) -> str:
    clusters = _decompose_greek_clusters(word)
    if not clusters:
        return word
    alpha_clusters = [c for c in clusters if c[0] in _GRC_SINGLE]
    all_upper = len(alpha_clusters) >= 2 and all(c[1] for c in alpha_clusters)

    out: List[str] = []
    i = 0
    n = len(clusters)
    while i < n:
        base, is_up, rough, _diaer = clusters[i]
        if base not in _GRC_SINGLE:
            out.append(base.upper() if is_up else base)
            i += 1
            continue

        # 1. Diphthongs (second vowel carries no diaeresis; rough breathing sits on second vowel)
        if i + 1 < n:
            b2, up2, r2, d2 = clusters[i + 1]
            diph = _GRC_DIPHTHONGS.get((base, b2))
            if diph is not None and not d2:
                has_h = rough or r2
                piece = ("h" + diph) if has_h else diph
                out.append(_apply_case(piece, is_up, all_upper or (is_up and up2)))
                i += 2
                continue

        # 2. Gamma nasal (γγ -> ng, γκ -> nk, γξ -> nx, γχ -> nch)
        if base == "γ" and i + 1 < n and clusters[i + 1][0] in _GRC_GAMMA_NASAL_NEXT:
            out.append(_apply_case("n", is_up, all_upper))
            i += 1
            continue

        # 3. Rho with rough breathing (initial ῥ -> rh; medial ῤῥ -> rrh)
        if base == "ρ":
            if rough:
                out.append(_apply_case("rh", is_up, all_upper))
            else:
                out.append(_apply_case("r", is_up, all_upper))
            i += 1
            continue

        # 4. Standard Greek letter (+ leading 'h' if vowel has rough breathing)
        mapped = _GRC_SINGLE[base]
        if rough:
            mapped = "h" + mapped
        out.append(_apply_case(mapped, is_up, all_upper))
        i += 1

    return "".join(out)


def transliterate_greek(text: str) -> str:
    """Transliterate Biblical Greek text into clean, readable Latin letters."""
    if not text:
        return ""
    res = _GRC_WORD_RE.sub(lambda m: _translit_greek_word(m.group(0)), text)
    # Map Greek-specific punctuation to familiar English equivalents:
    # 1. Greek question mark (U+037E or ASCII ';' after Greek text) -> '?' FIRST,
    #    before ano teleia ('·') becomes ';'!
    res = res.replace("\u037E", "?")
    if ";" in text and _GRC_WORD_RE.search(text):
        res = re.sub(r"(?<=[A-Za-z]);", "?", res)
    # 2. Greek ano teleia (middle dot) -> ';'
    res = res.replace("\u0387", ";").replace("\u00B7", ";")
    # 3. Modifier letter apostrophe / koronis used for Greek elision (ἀλλʼ -> all')
    res = res.replace("\u02BC", "'").replace("\u1FBD", "'").replace("\u2019", "'")
    return res


# ===========================================================================
# 2. BIBLICAL HEBREW & ARAMAIC -> ENGLISH-FRIENDLY LATINIZED ALPHABET
# ===========================================================================

_HEB_CONSONANTS = frozenset("אבגדהוזחטיךכלםמןנסעףפץצקרשת")
_HEB_RUN_RE = re.compile(r"[\u0590-\u05FF]+(?:[\u05BE\-][\u0590-\u05FF]+)*")

# Unicode Hebrew combining marks
_HEB_SHEVA = "\u05B0"
_HEB_HATAF_SEGOL = "\u05B1"
_HEB_HATAF_PATAH = "\u05B2"
_HEB_HATAF_QAMATS = "\u05B3"
_HEB_HIRIQ = "\u05B4"
_HEB_TSERE = "\u05B5"
_HEB_SEGOL = "\u05B6"
_HEB_PATAH = "\u05B7"
_HEB_QAMATS = "\u05B8"
_HEB_HOLAM = "\u05B9"
_HEB_HOLAM_HASER = "\u05BA"
_HEB_QUBUTS = "\u05BB"
_HEB_DAGESH = "\u05BC"
_HEB_METEG = "\u05BD"
_HEB_MAQAF = "\u05BE"
_HEB_RAFE = "\u05BF"
_HEB_PASEQ = "\u05C0"
_HEB_SHIN_DOT = "\u05C1"
_HEB_SIN_DOT = "\u05C2"
_HEB_SOF_PASUQ = "\u05C3"
_HEB_QAMATS_QATAN = "\u05C7"

_HEB_VOWEL_MAP = {
    _HEB_HATAF_SEGOL: "e",
    _HEB_HATAF_PATAH: "a",
    _HEB_HATAF_QAMATS: "o",
    _HEB_HIRIQ: "i",
    _HEB_TSERE: "e",
    _HEB_SEGOL: "e",
    _HEB_PATAH: "a",
    _HEB_QAMATS: "a",
    _HEB_HOLAM: "o",
    _HEB_HOLAM_HASER: "o",
    _HEB_QUBUTS: "u",
    _HEB_QAMATS_QATAN: "o",
}

_HEB_LONG_VOWELS = frozenset({_HEB_TSERE, _HEB_QAMATS, _HEB_HOLAM, _HEB_HOLAM_HASER})
_HEB_SHORT_VOWELS = frozenset({_HEB_PATAH, _HEB_SEGOL, _HEB_HIRIQ, _HEB_QUBUTS, _HEB_QAMATS_QATAN})
_HEB_HATAF_VOWELS = frozenset({_HEB_HATAF_SEGOL, _HEB_HATAF_PATAH, _HEB_HATAF_QAMATS})

_HEB_ROOT_RADICAL = {
    "א": "'", "ב": "b", "ג": "g", "ד": "d", "ה": "h", "ו": "v",
    "ז": "z", "ח": "ch", "ט": "t", "י": "y", "כ": "k", "ך": "k",
    "ל": "l", "מ": "m", "ם": "m", "נ": "n", "ן": "n", "ס": "s",
    "ע": "'", "פ": "p", "ף": "p", "צ": "tz", "ץ": "tz", "ק": "k",
    "ר": "r", "ש": "sh", "ת": "t",
}


def _parse_heb_clusters(word: str) -> List[dict]:
    """Parse a single Hebrew/Aramaic word into consonant + marks dicts."""
    clusters: List[dict] = []
    for ch in word:
        if ch in _HEB_CONSONANTS:
            clusters.append({
                "c": ch,
                "dagesh": False,
                "shin": False,
                "sin": False,
                "sheva": False,
                "vowel": "",
                "meteg": False,
            })
        elif clusters:
            cur = clusters[-1]
            if ch == _HEB_DAGESH:
                cur["dagesh"] = True
            elif ch == _HEB_SHIN_DOT:
                cur["shin"] = True
            elif ch == _HEB_SIN_DOT:
                cur["sin"] = True
            elif ch == _HEB_SHEVA:
                cur["sheva"] = True
            elif ch == _HEB_METEG:
                cur["meteg"] = True
            elif ch in _HEB_VOWEL_MAP:
                # Keep the primary vowel; hatef/qamatz qatan take precedence if both appear
                if not cur["vowel"] or ch in (_HEB_QAMATS_QATAN, _HEB_HATAF_QAMATS, _HEB_HATAF_PATAH, _HEB_HATAF_SEGOL):
                    cur["vowel"] = ch
            # Cantillation marks (U+0591-05AF) and rafe are ignored
    return clusters


def _has_any_niqqud(clusters: List[dict]) -> bool:
    return any(cl["vowel"] or cl["sheva"] or cl["dagesh"] for cl in clusters)


def _translit_heb_root_part(part: str) -> str:
    """Transliterate an unpointed consonantal root radical cluster (e.g. 'ר-א-שׁ')."""
    clusters = _parse_heb_clusters(part)
    out: List[str] = []
    for cl in clusters:
        c = cl["c"]
        if c == "ש":
            out.append("s" if cl["sin"] else "sh")
        else:
            out.append(_HEB_ROOT_RADICAL.get(c, c))
    return "".join(out)


def _heb_cons_sound(cl: dict, is_first: bool, is_last: bool, prev_had_vowel: bool) -> str:
    c = cl["c"]
    dag = cl["dagesh"]
    if c == "א":
        # Silent at word edges; clean glottal break only between vowels
        return "" if (is_first or is_last or not prev_had_vowel) else "'"
    if c == "ע":
        return "" if (is_first or is_last or not prev_had_vowel) else "'"
    if c == "ב":
        return "b" if dag else "v"
    if c == "ג":
        return "g"
    if c == "ד":
        return "d"
    if c == "ה":
        return "h"
    if c == "ו":
        return "v"
    if c == "ז":
        return "z"
    if c == "ח":
        return "ch"
    if c == "ט":
        return "t"
    if c == "י":
        return "y"
    if c in ("כ", "ך"):
        return "k" if dag else "kh"
    if c == "ל":
        return "l"
    if c in ("מ", "ם"):
        return "m"
    if c in ("נ", "ן"):
        return "n"
    if c == "ס":
        return "s"
    if c in ("פ", "ף"):
        return "p" if dag else "f"
    if c in ("צ", "ץ"):
        return "tz"
    if c == "ק":
        return "k"
    if c == "ר":
        return "r"
    if c == "ש":
        return "s" if cl["sin"] else "sh"
    if c == "ת":
        return "t"
    return c


def _translit_hebrew_word(word: str, followed_by_maqaf: bool = False) -> str:
    """Transliterate a single Hebrew/Aramaic word (pointed or unpointed)."""
    # Strip trailing sof-pasuq / paseq handled by caller
    clusters = _parse_heb_clusters(word)
    if not clusters:
        return ""

    bare = "".join(cl["c"] for cl in clusters)
    # Tetragrammaton: unpointed 'יהוה' or Leningrad perpetual-qere 'יְהוָה' (no vowel on ה) -> YHWH;
    # explicit holam 'יְהֹוָה' -> Yehovah
    if bare == "יהוה":
        if not _has_any_niqqud(clusters) or not clusters[1]["vowel"]:
            return "YHWH"
        if clusters[1]["vowel"] in (_HEB_HOLAM, _HEB_HOLAM_HASER):
            return "Yehovah"
    # Unpointed word (e.g. ketiv reading or bare stem)
    if not _has_any_niqqud(clusters):
        return _translit_heb_root_part(word)

    n = len(clusters)
    out: List[str] = []
    i = 0
    prev_vowel_code = ""
    prev_was_vocal_sheva = False
    prev_ended_in_vowel = False

    while i < n:
        cl = clusters[i]
        c = cl["c"]
        v = cl["vowel"]
        sh = cl["sheva"]
        dag = cl["dagesh"]
        is_first = (i == 0)
        is_last = (i == n - 1)

        # ---- Special case 1: Word-final 3ms plural suffix ָיו (-av, e.g. דְּבָרָיו -> devarav) ----
        if (
            v == _HEB_QAMATS
            and i + 2 == n - 1
            and clusters[i + 1]["c"] == "י"
            and not clusters[i + 1]["vowel"]
            and not clusters[i + 1]["sheva"]
            and clusters[i + 2]["c"] == "ו"
            and not clusters[i + 2]["vowel"]
            and not clusters[i + 2]["dagesh"]
        ):
            cons = _heb_cons_sound(cl, is_first, False, prev_ended_in_vowel)
            out.append(cons + "av")
            break

        # ---- Special case 2: Vav as vowel mater (shuruq וּ -> u; holam male וֹ -> o) ----
        if c == "ו" and dag and not v and not sh:
            # Shuruq: initial וּ (u-) or after consonant without its own vowel (רוּחַ, תֹהוּ)
            if is_first or not prev_ended_in_vowel:
                out.append("u")
                prev_vowel_code = _HEB_QUBUTS
                prev_was_vocal_sheva = False
                prev_ended_in_vowel = True
                i += 1
                continue
        if c == "ו" and v in (_HEB_HOLAM, _HEB_HOLAM_HASER) and not dag and not sh:
            if not is_first and not prev_ended_in_vowel:
                out.append("o")
                prev_vowel_code = _HEB_HOLAM
                prev_was_vocal_sheva = False
                prev_ended_in_vowel = True
                i += 1
                continue

        # ---- Special case 3: Silent Yod mater lectionis after previous vowel ----
        if c == "י" and not v and not sh and not dag and not is_first and prev_ended_in_vowel:
            if prev_vowel_code == _HEB_HIRIQ:
                # ִי -> i (already emitted 'i')
                i += 1
                continue
            if prev_vowel_code in (_HEB_TSERE, _HEB_SEGOL):
                # ֵי / ֶי -> ei (append 'i' after 'e')
                out.append("i")
                i += 1
                continue
            if prev_vowel_code in (_HEB_HOLAM, _HEB_HOLAM_HASER):
                # וֹי -> oi
                out.append("i")
                i += 1
                continue
            if prev_vowel_code in (_HEB_PATAH, _HEB_QAMATS):
                # ַי / ָי at word end -> ai (e.g. אֲדֹנָי -> adonai, חַי -> chai)
                out.append("i" if is_last else "y")
                prev_ended_in_vowel = is_last
                i += 1
                continue

        # ---- Special case 4: Silent Alef / Ayin before Vav mater & He mater lectionis ----
        if c in ("א", "ע") and not v and not sh:
            # Onset alef/ayin before holam-male / shuruq (אוֹר -> or, וְאוֹר -> ve'or, לְעוֹלָם -> le'olam)
            nxt_is_vav_mater = (
                i + 1 < n
                and clusters[i + 1]["c"] == "ו"
                and (
                    (clusters[i + 1]["dagesh"] and not clusters[i + 1]["vowel"] and not clusters[i + 1]["sheva"])
                    or (clusters[i + 1]["vowel"] in (_HEB_HOLAM, _HEB_HOLAM_HASER) and not clusters[i + 1]["dagesh"])
                )
            )
            if nxt_is_vav_mater:
                if not is_first and prev_ended_in_vowel and not (out and out[-1].endswith("'")):
                    out.append("'")
                prev_ended_in_vowel = False
                i += 1
                continue
            if c == "א" and not is_first:
                # Quiescent alef (בָּרָא -> bara, רֵאשִׁית -> reshit, מָצָאתִי -> matzati)
                i += 1
                continue
        if c == "ה" and is_last and not v and not sh:
            # Final mater lectionis ה (תּוֹרָה -> torah, הָיְתָה -> hayetah, מֹשֶׁה -> mosheh)
            if prev_ended_in_vowel or dag:
                out.append("h")
            i += 1
            continue

        # ---- Special case 5: Furtive Patach on word-final חַ, עַ, הַּ ----
        if (
            is_last
            and v == _HEB_PATAH
            and c in ("ח", "ע", "ה")
            and (c != "ה" or dag)
            and prev_ended_in_vowel
            and prev_vowel_code not in (_HEB_PATAH, _HEB_QAMATS, _HEB_HATAF_PATAH)
        ):
            out.append("a")
            if c == "ח":
                out.append("ch")
            elif c == "ה":
                out.append("h")
            # For word-final עַ (יֵשׁוּעַ -> yeshua, שָׁמֵעַ -> shamea), 'a' is the glide sound
            i += 1
            continue

        # ---- Normal consonant + vowel/sheva emission ----
        cons = _heb_cons_sound(cl, is_first, is_last, prev_ended_in_vowel)
        # Avoid double apostrophe or apostrophe before a silent consonant
        if cons == "'" and (not v and not sh):
            cons = ""
        if cons == "'" and out and out[-1].endswith("'"):
            cons = ""

        # Determine vowel text
        v_txt = ""
        v_code_out = v
        is_vocal_sh = False

        if v:
            if v == _HEB_QAMATS:
                # Qamatz Qatan -> 'o' in closed unstressed syllable:
                # (1) before hatef-qamatz (פָּעֳלוֹ -> po'olo)
                # (2) before consonant with silent sheva and no meteg (חָכְמָה -> chokhmah, קָדְשׁוֹ -> kodsho)
                # (3) closed monosyllable before maqaf (כָּל־ -> kol-)
                is_qatan = False
                if not cl["meteg"]:
                    if i + 1 < n and clusters[i + 1]["vowel"] == _HEB_HATAF_QAMATS:
                        is_qatan = True
                    elif (
                        i + 1 < n
                        and clusters[i + 1]["sheva"]
                        and not clusters[i + 1]["dagesh"]
                        and i + 2 < n
                        and not clusters[i + 2]["sheva"]
                        and c not in ("א", "ה", "ו", "י")
                    ):
                        # Distinguish true qamatz-qatan (חָכְמָה, קָדְשׁוֹ, אָכְלָה) from verb 3fs (הָיְתָה, אָמְרָה)
                        # In 3fs verbs ending in -תָה / -רָה after open qamatz, sheva is vocal -> stays 'a'
                        if not (i + 2 == n - 1 and clusters[i + 2]["c"] == "ה") and not (
                            i + 2 < n and clusters[i + 1]["c"] == "י"
                        ):
                            is_qatan = True
                    elif followed_by_maqaf and n == 2 and i == 0 and not clusters[1]["vowel"]:
                        is_qatan = True
                v_txt = "o" if is_qatan else "a"
                v_code_out = _HEB_QAMATS_QATAN if is_qatan else _HEB_QAMATS
            else:
                v_txt = _HEB_VOWEL_MAP.get(v, "")
        elif sh:
            # Vocal vs. silent sheva rules
            if is_last:
                is_vocal_sh = False
            elif i == n - 2 and clusters[n - 1]["sheva"]:
                # Double final sheva (אַתְּ / וַיֵּשְׁתְּ): both silent
                is_vocal_sh = False
            elif is_first:
                is_vocal_sh = True
            elif prev_was_vocal_sheva:
                is_vocal_sh = False
            elif i > 0 and clusters[i - 1]["sheva"]:
                # Second of two consecutive shevas is vocal (יִשְׁמְרוּ -> yishmeru)
                is_vocal_sh = True
            elif dag and prev_vowel_code in _HEB_SHORT_VOWELS:
                # Sheva under dagesh forte is vocal (וַיְדַבְּרוּ -> vayedaberu)
                is_vocal_sh = True
            elif prev_vowel_code in _HEB_LONG_VOWELS:
                # Sheva after an unaccented long vowel is vocal (הָיְתָה -> hayetah, שֹׁמְרִים -> shomerim)
                is_vocal_sh = True
            else:
                is_vocal_sh = False
            if is_vocal_sh:
                v_txt = "e"

        out.append(cons + v_txt)
        if v_txt:
            prev_vowel_code = v_code_out
            prev_was_vocal_sheva = is_vocal_sh
            prev_ended_in_vowel = True
        else:
            prev_vowel_code = ""
            prev_was_vocal_sheva = False
            prev_ended_in_vowel = False
        i += 1

    res = "".join(out)
    # Clean any stray leading/trailing apostrophe
    res = res.strip("'")
    return res


def _translit_hebrew_run(run: str) -> str:
    """Transliterate a contiguous Hebrew/Aramaic run (possibly hyphen/maqaf joined)."""
    # Strip paseq; preserve sof pasuq as '.'
    trailing_period = ""
    if run.endswith(_HEB_SOF_PASUQ):
        run = run[:-1]
        trailing_period = "."
    run = run.replace(_HEB_PASEQ, "")
    if not run:
        return trailing_period

    # Hyphenated unpointed consonantal root notation (e.g. 'ר-א-שׁ', 'ד-ב-ר', 'ח-ל-ל')
    if "-" in run and _HEB_MAQAF not in run:
        parts = run.split("-")
        if all(not _has_any_niqqud(_parse_heb_clusters(p)) for p in parts if p):
            return "-".join(_translit_heb_root_part(p) for p in parts) + trailing_period

    # Maqaf-joined words (e.g. עַל־פְּנֵי -> al-penei, כָּל־הָאָרֶץ -> kol-ha'aretz)
    if _HEB_MAQAF in run:
        parts = run.split(_HEB_MAQAF)
        out_parts = [
            _translit_hebrew_word(p, followed_by_maqaf=(idx < len(parts) - 1))
            for idx, p in enumerate(parts)
        ]
        return "-".join(out_parts) + trailing_period

    return _translit_hebrew_word(run, followed_by_maqaf=False) + trailing_period


def transliterate_hebrew(text: str) -> str:
    """Transliterate Biblical Hebrew/Aramaic text or consonantal roots into readable Latin letters."""
    if not text:
        return ""
    res = _HEB_RUN_RE.sub(lambda m: _translit_hebrew_run(m.group(0)), text)
    # Collapse stray spaces before periods created by paseq removal
    res = re.sub(r"\s+\.", ".", res)
    res = re.sub(r" {2,}", " ", res)
    return res.strip() if text == text.strip() else res


# ===========================================================================
# 3. PUBLIC DISPATCHERS
# ===========================================================================

def transliterate(text: str, language: str) -> str:
    """Transliterate ``text`` according to ``language`` (Greek, Hebrew/Aramaic, or pass-through Latin)."""
    if not text:
        return ""
    code = (language or "").strip().lower()
    if code in ("greek", "grc", "grc_ot", "grc_nt"):
        return transliterate_greek(text)
    if code in ("hebrew", "heb", "arc", "aramaic", "heb_ot"):
        return transliterate_hebrew(text)
    return text


def transliterate_mixed(text: str) -> str:
    """Transliterate any Greek and Hebrew spans embedded in a mixed string (formulas, notes, etc.)."""
    if not text:
        return ""
    out = transliterate_greek(text)
    out = transliterate_hebrew(out)
    return out
