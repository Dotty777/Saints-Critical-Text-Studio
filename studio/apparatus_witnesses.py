"""Record the readings of apparatus-only witnesses (catalog.APPARATUS_ONLY) after the text is decided.

Apparatus witnesses include Majority/ecclesiastical editions, historic critical editions
(Westcott–Hort 1881, Tischendorf 8th), and direct manuscript transcriptions (CNTR early papyri/uncials
and INTF NTVMR XMLs). They are collated against the adopted text, never voted with. For each verse:

* where an apparatus unit already exists, the witness is added to the side it supports (the lemma,
  a listed variant, or a new variant of that unit);
* where it differs in substance from a text the voting editions agree on, a new unit records its reading;
* a spelling, accent, pointing, nomen-sacrum or numeral convention is logged once per verse in
  ``disregarded`` (Hebrew: an entry is made only when the consonants differ or a word is added or missing);
* a verse it lacks is added to the verse-level unit ("om. verse").

The adopted text, its confidence and the voting witnesses' units are never changed.
"""

import difflib
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from .brains.base import ApparatusItem, DisregardedItem
from .collator import (
    _movable_nu_stem,
    _resolve_letter_numerals,
    _resolve_nomina_sacra,
    canonical_compare_key,
    classify_forms,
    is_nomen_sacrum,
    strip_punct,
)
from .parsers import DOUBTFUL_CLOSE, DOUBTFUL_OPEN, GAP_WORD, LACUNA_MARK, VERSE_ABSENT

NOTE = "Reading of an apparatus witness (recorded in the apparatus; it does not vote on the text)."
_MAX_LOGGED_FORMS = 12
_GAP_KEY = "\x00gap"

# Standard Greek NT nomina sacra fallback expansions (unaccented canonical keys) for when a
# direct manuscript introduces a sacred name in a variant not written in full elsewhere in the verse.
_COMMON_NOMINA_SACRA: Dict[str, str] = {
    "θσ": "θεοσ", "θυ": "θεου", "θω": "θεω", "θν": "θεον", "θε": "θεε",
    "κσ": "κυριοσ", "κυ": "κυριου", "κω": "κυριω", "κν": "κυριον", "κε": "κυριε",
    "ισ": "ιησουσ", "ιησ": "ιησουσ", "ιυ": "ιησου", "ιηυ": "ιησου", "ιη": "ιησου", "ιν": "ιησουν", "ιην": "ιησουν",
    "χσ": "χριστοσ", "χρσ": "χριστοσ", "χυ": "χριστου", "χρυ": "χριστου", "χω": "χριστω", "χρω": "χριστω", "χν": "χριστον", "χρν": "χριστον",
    "πνα": "πνευμα", "πνσ": "πνευματοσ", "πνι": "πνευματι", "πντα": "πνευματα", "πνων": "πνευματων",
    "υς": "υιοσ", "υσ": "υιοσ", "υυ": "υιου", "υω": "υιω", "υν": "υιον", "υι": "υιοι", "υων": "υιων",
    "ανσ": "ανθρωποσ", "ανου": "ανθρωπου", "ανω": "ανθρωπω", "ανον": "ανθρωπον", "ανοι": "ανθρωποι", "ανων": "ανθρωπων", "ανοισ": "ανθρωποισ", "ανουσ": "ανθρωπουσ",
    "πηρ": "πατηρ", "πρσ": "πατροσ", "πρι": "πατρι", "πρα": "πατερα", "πρεσ": "πατερεσ", "πρων": "πατερων", "πρασ": "πατερασ",
    "μηρ": "μητηρ", "μρσ": "μητροσ", "μρι": "μητρι", "μρα": "μητερα",
    "δαδ": "δαυιδ", "δδ": "δαυιδ",
    "ιηλ": "ισραηλ", "ισλ": "ισραηλ", "ισρλ": "ισραηλ",
    "ιλημ": "ιερουσαλημ", "ιηλμ": "ιερουσαλημ", "ιελμ": "ιερουσαλημ",
    "ουνσ": "ουρανοσ", "ουνου": "ουρανου", "ουνω": "ουρανω", "ουνον": "ουρανον", "ουνοι": "ουρανοι", "ουνων": "ουρανων", "ουνοισ": "ουρανοισ", "ουνουσ": "ουρανουσ",
    "στσ": "σταυροσ", "στρου": "σταυρου", "στρω": "σταυρω", "στρον": "σταυρον", "στρν": "σταυρον",
    "σωρ": "σωτηρ", "σρσ": "σωτηροσ", "σρι": "σωτηρι", "σρα": "σωτηρα",
}


def _tokens(text: str, language: str, keep_gap: bool = False) -> Tuple[List[str], List[int]]:
    """Comparison tokens and, for each, the index of its word in ``text.split()``."""
    toks, word_of = [], []
    for i, w in enumerate(text.replace(DOUBTFUL_OPEN, "").replace(DOUBTFUL_CLOSE, "").split()):
        parts = w.replace("־", "־ ").split() if language == "hebrew" else [w]
        for p in parts:
            if p == LACUNA_MARK:
                continue
            if p == GAP_WORD:
                if keep_gap:
                    toks.append(GAP_WORD)
                    word_of.append(i)
                continue
            if not strip_punct(p) and p != "׀":
                continue
            toks.append(p)
            word_of.append(i)
    return toks, word_of


def _key(tok: str, language: str) -> str:
    if tok == GAP_WORD:
        return _GAP_KEY
    return canonical_compare_key(tok, language) or tok


def _consonants(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if "א" <= ch <= "ת")


# Hebrew letter names that head the acrostic stanzas (Lamentations, Psalm 118) in Swete and Brenton;
# the Orthodox Septuagint prints none. Keys as canonical_compare_key gives them.
_GREEK_LETTER_NAMES = {"αλεφ", "βηθ", "γιμελ", "δαλεθ", "η", "ουαυ", "ζαι", "ηθ", "τηθ", "ιωδ", "χαφ", "λαβδ",
                       "λαμεδ", "μημ", "νουν", "σαμχ", "αιν", "φη", "σαδη", "κωφ", "ρησ", "χσεν", "σεν", "θαυ"}
_KETIV = ("(", "[", "*")


def _drop_letter_names(words: List[str], language: str) -> List[str]:
    if language != "greek":
        return words
    return [w for w in words if not (strip_punct(w)[:1].isupper() and canonical_compare_key(w, "greek") in _GREEK_LETTER_NAMES
                                     and (w.endswith(".") or len(strip_punct(w)) > 2))]


def _hebrew_spelling(lemma: str, reading: str) -> str:
    """Why two Hebrew readings are the same words, or ''."""
    if _consonants(lemma) == _consonants(reading):
        return "Masoretic pointing / cantillation convention of the edition (same consonants)"
    # Ketiv / qere: MAM prints the written form in brackets before the form read; Ben Chayyim marks the written
    # form with * and the read form in brackets; others print only one of the two. Same words when one
    # side's form (whole, either part, or any single word) is the other side's, plene/defective aside.
    def defective(c: str) -> str:  # internal vav / yod (matres lectionis) dropped; a word-initial vav stays
        return "".join(ch for i, ch in enumerate(c) if not (i > 0 and ch in "וי"))

    def forms(t: str) -> set:
        words = t.split()
        marked = [w for w in words if w.startswith(_KETIV) or w.endswith(")")]
        rest = [w for w in words if w not in marked]
        cands = {_consonants(t), _consonants(" ".join(rest))} | {_consonants(w) for w in words}
        return {defective(c) for c in cands if c}

    if any(w.startswith(_KETIV) or w.endswith(")") for w in (lemma + " " + reading).split()) and forms(lemma) & forms(reading):
        return "Ketiv / qere presentation (the editions print the written and the read form differently)"

    lw, rw = lemma.split(), reading.split()
    if len(lw) == len(rw) and all(defective(_consonants(x)) == defective(_consonants(y)) for x, y in zip(lw, rw)):
        return "Plene / defective spelling (vav or yod as a vowel letter)"
    return ""


def _iota_adscript_key(word: str) -> str:
    """Normalise a Greek word with combining iota subscript (\u0345) expanded to adscript ``ι``."""
    nfd = unicodedata.normalize("NFD", strip_punct(word).lower()).replace("ς", "σ").replace("ϲ", "σ")
    out: List[str] = []
    for ch in nfd:
        if ch == "\u0345":
            out.append("ι")
        elif unicodedata.category(ch) != "Mn":
            out.append(ch)
    return "".join(out)


def _has_accent_marks(form: str) -> bool:
    return any(c in "\u0300\u0301\u0342\u0313\u0314" for c in unicodedata.normalize("NFD", form))


def _align_key(resolved_key: str, language: str) -> str:
    """Mildly orthography-tolerant key used ONLY to guide SequenceMatcher alignment."""
    if resolved_key == _GAP_KEY:
        return resolved_key
    if language == "hebrew":
        cons = _consonants(resolved_key)
        if not cons:
            return resolved_key
        # Align pointed Masoretic against unpointed Qumran/Samaritan Hebrew by consonants,
        # folding internal matres lectionis (ו/י) while keeping word-initial and word-final letters.
        return "".join(ch for i, ch in enumerate(cons) if i == 0 or i == len(cons) - 1 or ch not in "וי") or cons
    if language != "greek":
        return resolved_key
    k = resolved_key.replace("ει", "ι")
    k = re.sub(r"^(δα|λε)βι", r"\1υι", k)
    if k.endswith("ν") and _movable_nu_stem(k[:-1]):
        k = k[:-1]
    return k


def _is_spelling(lemma: str, reading: str, language: str) -> Tuple[bool, str]:
    """A difference of spelling, accent, pointing or layout only (not a variant)."""
    lw = _drop_letter_names(lemma.split(), language)
    rw = _drop_letter_names(reading.split(), language)
    if (lw, rw) != (lemma.split(), reading.split()):
        if not lw and not rw:
            return True, "Acrostic letter heading printed by one edition only"
        lemma, reading = " ".join(lw), " ".join(rw)
    if not lemma or not reading:
        if language == "hebrew":
            words = (lemma or reading).split()
            if all(w.strip("׃") == "׀" for w in words):
                return True, "Paseq / legarmeh stroke (an accent sign) printed by one edition only"
            if all(w.startswith(_KETIV) or w.endswith(")") for w in words):
                return True, "Ketiv / qere presentation (one edition prints the written form in brackets)"
        return False, ""
    if language == "hebrew":
        why = _hebrew_spelling(lemma, reading)
        return bool(why), why
    forms = [lemma, reading]
    keys = {f: " ".join(_key(t, language) for t in f.split()) for f in forms}
    if len(set(keys.values())) == 1:
        return True, "Accentuation / capitalisation / punctuation convention"
    if language == "greek":
        lw_s, rw_s = lemma.split(), reading.split()
        if len(lw_s) == len(rw_s) and all(_iota_adscript_key(x) == _iota_adscript_key(y) for x, y in zip(lw_s, rw_s)):
            return True, "Iota adscript / subscript orthographic convention (αὐτῷ / αυτωι type)"
    joined = {f: keys[f].replace(" ", "") for f in forms}
    if len(set(joined.values())) == 1:
        return True, "Word division differs (same letters written as one word or two)"
    if len(lemma.split()) != len(reading.split()):
        sp_ok, sp_why = _is_spelling(joined[lemma], joined[reading], language)
        if sp_ok and not (
            language == "greek"
            and "itacistic" in sp_why.lower()
            and min(len(j) for j in joined.values()) < 8
            and not any(len(strip_punct(w)) == 1 for f in forms for w in f.split())
        ):
            return True, "Word division differs, with a spelling difference"
    ok, reason = classify_forms(forms, keys, language)
    if ok:
        return ok, reason
    lw, rw = lemma.split(), reading.split()
    if len(lw) == len(rw) > 1:  # several words, each a spelling difference (ἐστὶν ῥήμασιν / ἐστὶ ρήμασι)
        reasons = [_is_spelling(x, y, language) for x, y in zip(lw, rw)]
        if all(r[0] for r in reasons):
            return True, "; ".join(sorted({r[1] for r in reasons}))
    return False, ""


def _pos_map(n: int, opcodes) -> List[int]:
    """For each boundary 0..n of the adopted text's tokens, the aligned boundary in the witness."""
    pos = [0] * (n + 1)
    for tag, i1, i2, j1, j2 in opcodes:
        for k in range(i1, i2 + 1):
            if tag == "equal":
                pos[k] = j1 + (k - i1)
            else:
                pos[k] = j1 + min(k - i1, j2 - j1) if k < i2 else j2
    return pos


_EXPANDED_SUFFIX = re.compile(r"\s*\(=\s*([^)]+)\)\s*$")


def _expand_ns_tokens(text: str, ns_map: Dict[str, str], lex: Any) -> Tuple[str, str]:
    """Return ``(display_reading, expanded_for_compare)`` for a Greek reading that may contain nomina sacra."""
    if not text or text == "om.":
        return text, text
    m = _EXPANDED_SUFFIX.search(text)
    if m:
        return text, m.group(1).strip()
    words = text.split()
    if not any(is_nomen_sacrum(w) for w in words):
        return text, text
    full_words: List[str] = []
    for w in words:
        if is_nomen_sacrum(w):
            ck = canonical_compare_key(w, "greek")
            exp_key = ns_map.get(ck) or _COMMON_NOMINA_SACRA.get(ck) or ck
            pretty = (lex.best_form.get(exp_key) if lex is not None else None) or exp_key
            full_words.append(pretty)
        else:
            full_words.append(w)
    expanded = " ".join(full_words)
    return f"{text} (= {expanded})", expanded


def _same(a: str, b: str, language: str, ns_map: Optional[Dict[str, str]] = None, lex: Any = None) -> bool:
    if a == b:
        return True
    if not a or not b or a == "om." or b == "om.":
        return (a in ("", "om.")) and (b in ("", "om."))
    if language == "greek":
        _, a = _expand_ns_tokens(a, ns_map or {}, lex)
        _, b = _expand_ns_tokens(b, ns_map or {}, lex)
        if a == b:
            return True
    return _is_spelling(a, b, language)[0]


def record_apparatus_witnesses(cv: Any, adj: Any, language: str) -> None:
    texts: Dict[str, str] = getattr(cv, "apparatus_texts", {}) or {}
    if not texts:
        return
    lang = language.lower()
    lex = getattr(cv, "lexicon", None)
    crit = adj.critical_text or ""
    c_toks, c_word = _tokens(crit, lang)
    c_keys = [_key(t, lang) for t in c_toks]
    n_words = len(crit.replace(DOUBTFUL_OPEN, "").replace(DOUBTFUL_CLOSE, "").split())
    first_tok = {}
    for t, w in enumerate(c_word):
        first_tok.setdefault(w, t)

    # Pre-tokenise apparatus witnesses (preserving GAP_WORD so illegible parchment never masquerades as om.)
    # and resolve Greek nomina sacra / letter-numerals against the verse's full-word vocabulary before alignment.
    app_toks_by_sig: Dict[str, List[str]] = {}
    app_keys_by_sig: Dict[str, List[str]] = {}
    ns_map: Dict[str, str] = {}
    for sig, x in texts.items():
        if x == VERSE_ABSENT:
            continue
        wt, _ = _tokens(x, lang, keep_gap=True)
        app_toks_by_sig[sig] = wt
        app_keys_by_sig[sig] = [_key(t, lang) for t in wt]

    if lang == "greek" and app_toks_by_sig:
        tokens_all: Dict[str, List[str]] = {"__crit__": list(c_toks)}
        keys_all: Dict[str, List[str]] = {"__crit__": list(c_keys)}
        for vsig, vtxt in (getattr(cv, "witness_texts", {}) or {}).items():
            vt, _ = _tokens(vtxt, lang)
            tokens_all[f"__v_{vsig}"] = vt
            keys_all[f"__v_{vsig}"] = [_key(t, lang) for t in vt]
        for sig, wt in app_toks_by_sig.items():
            tokens_all[sig] = wt
            keys_all[sig] = list(app_keys_by_sig[sig])
        _resolve_nomina_sacra(tokens_all, keys_all)
        _resolve_letter_numerals(tokens_all, keys_all)
        c_keys = keys_all["__crit__"]
        for sig in app_toks_by_sig:
            wt = app_toks_by_sig[sig]
            wk = keys_all[sig]
            for idx_t, (tok, rk) in enumerate(zip(wt, wk)):
                if is_nomen_sacrum(tok):
                    raw_ck = canonical_compare_key(tok, "greek")
                    if rk != raw_ck:
                        ns_map.setdefault(raw_ck, rk)
                    elif raw_ck in _COMMON_NOMINA_SACRA:
                        wk[idx_t] = _COMMON_NOMINA_SACRA[raw_ck]
                        ns_map.setdefault(raw_ck, wk[idx_t])
            app_keys_by_sig[sig] = wk

    def tok_range(item: ApparatusItem) -> Optional[Tuple[int, int]]:
        if item.kind != "word" or item.word_index < 0:
            return None
        a = first_tok.get(item.word_index, len(c_toks) if item.word_index >= n_words else None)
        if a is None:
            return None
        b = a
        while b < len(c_toks) and c_word[b] < item.word_index + item.word_count:
            b += 1
        return a, b

    voters = sorted(getattr(cv, "witness_texts", {}) or {})
    verse_item = next((it for it in adj.apparatus if it.kind == "verse"), None)
    spelling: Dict[str, Dict[str, Any]] = {}

    voter_ranges = [r for r in (tok_range(it) for it in adj.apparatus) if r is not None]
    aligned: Dict[str, Tuple[List[str], List[Any], List[int]]] = {}
    lost: Dict[str, Tuple[bool, bool, bool, int]] = {}

    # 1. Verse presence, and new units where the voting editions agree but an apparatus witness differs in substance.
    for sig in sorted(texts):
        x = texts[sig]
        if x == VERSE_ABSENT:
            if verse_item is None:
                verse_item = ApparatusItem(
                    slot_index=-1, lemma="verse", lemma_witnesses=voters,
                    variants=[], note="Verse lacking in an apparatus witness. " + NOTE,
                    word_index=0, word_count=0, kind="verse", lemma_key="verse")
                adj.apparatus.insert(0, verse_item)
            om = next((v for v in verse_item.variants if str(v.get("reading", "")).startswith("om.")), None)
            if om is None:
                om = {"reading": "om. verse", "witnesses": [], "weight_sum": 0.0}
                verse_item.variants.append(om)
            if sig not in om["witnesses"]:
                om["witnesses"].append(sig)
            continue
        if verse_item is not None and sig not in verse_item.lemma_witnesses:
            verse_item.lemma_witnesses.append(sig)
        w_toks = app_toks_by_sig[sig]
        w_keys = app_keys_by_sig[sig]
        c_align = [_align_key(k, lang) for k in c_keys]
        w_align = [_align_key(k, lang) for k in w_keys]
        ops = difflib.SequenceMatcher(a=c_align, b=w_align, autojunk=False).get_opcodes()
        aligned[sig] = (w_toks, ops, _pos_map(len(c_toks), ops))
        # Lost text ("…") is not evidence of omission: at the start or end of the verse it silences that
        # edge, inside the verse every omission (as in the collator's handling of fragmentary witnesses).
        parts = [t for t in x.split() if t]
        lost_inside = LACUNA_MARK in parts[1:-1]
        lost_start, lost_end = bool(parts) and parts[0] == LACUNA_MARK, bool(parts) and parts[-1] == LACUNA_MARK
        lost[sig] = (lost_inside, lost_start, lost_end, len(c_toks))
        for tag, i1, i2, j1, j2 in ops:
            if tag == "equal" or any(a <= i1 < b or a < i2 <= b or (a == b and i1 <= a <= i2) for a, b in voter_ranges):
                continue
            if tag == "delete" and (lost_inside or (lost_start and i1 == 0) or (lost_end and i2 == len(c_toks))):
                continue
            if any(t == GAP_WORD for t in w_toks[j1:j2]):
                continue  # illegible / editor-supplied parchment at this slot: neither for nor against
            lemma = " ".join(c_toks[i1:i2])
            reading = " ".join(w_toks[j1:j2])
            cmp_reading = _expand_ns_tokens(reading, ns_map, lex)[1] if lang == "greek" else reading
            is_sp, reason = _is_spelling(lemma, cmp_reading, lang)
            if is_sp:
                log = spelling.setdefault(reason, {"forms": [], "witnesses": set(), "count": 0})
                log["count"] += 1
                log["witnesses"].add(sig)
                if len(log["forms"]) < _MAX_LOGGED_FORMS:
                    log["forms"].append(f"{lemma} / {reading}")
                continue
            disp_reading = _expand_ns_tokens(reading, ns_map, lex)[0] if lang == "greek" and reading else reading
            w0 = c_word[i1] if i1 < len(c_word) else n_words
            w1 = (c_word[i2 - 1] + 1) if i2 > i1 else w0
            existing = next((it for it in adj.apparatus if it.kind == "word" and it.slot_index == -1
                             and it.word_index in (w0, -1) and it.word_count == w1 - w0 and it.note == NOTE
                             and it.lemma_key == (" ".join(c_keys[i1:i2]) or "om.")), None)
            if existing is None:
                existing = ApparatusItem(
                    slot_index=-1, lemma=lemma or "om.", lemma_witnesses=list(voters), variants=[], note=NOTE,
                    word_index=w0 if DOUBTFUL_OPEN not in crit else -1, word_count=w1 - w0, kind="word",
                    lemma_key=" ".join(c_keys[i1:i2]) or "om.", confidence=adj.confidence)
                existing._tok = (i1, i2)  # type: ignore[attr-defined]
                adj.apparatus.append(existing)
            var = next((v for v in existing.variants if _same(reading, str(v.get("reading", "")), lang, ns_map, lex)), None)
            if var is None:
                var = {"reading": disp_reading or "om.", "witnesses": [], "weight_sum": 0.0}
                existing.variants.append(var)
            elif lang == "greek" and reading and _has_accent_marks(reading) and "\u0305" not in reading:
                cur = str(var.get("reading", ""))
                if cur and cur != "om." and ("\u0305" in cur or not _has_accent_marks(cur)):
                    var["reading"] = reading
            if sig not in var["witnesses"]:
                var["witnesses"].append(sig)

    # 2. Every unit: put each witness on the side it supports (the lemma, a listed variant or a new variant).
    for sig, (w_toks, ops, pos) in aligned.items():
        for item in adj.apparatus:
            rng = getattr(item, "_tok", None) or tok_range(item)
            if rng is None:
                continue
            a, b = rng
            if a == b:  # an addition unit: what does the witness have at this point?
                seg = next((" ".join(w_toks[j1:j2]) for tag, i1, i2, j1, j2 in ops if tag == "insert" and i1 == a), "")
            else:
                seg = " ".join(w_toks[pos[a]:pos[b]])
                # If a witness has a leading insertion immediately before token ``a`` (e.g. "τὸν" before
                # "υἱὸν αὐτῆς τὸν πρωτότοκον" in Matt 1:25), include it when it matches an existing variant.
                lead_ins = next((" ".join(w_toks[j1:j2]) for tag, i1, i2, j1, j2 in ops if tag == "insert" and i1 == a), "")
                if lead_ins and seg:
                    with_lead = f"{lead_ins} {seg}"
                    if any(_same(with_lead, str(v.get("reading", "")), lang, ns_map, lex) for v in item.variants):
                        seg = with_lead
            if any(sig in v.get("witnesses", []) for v in item.variants) or sig in item.lemma_witnesses:
                continue
            if GAP_WORD in seg:
                continue  # illegible / editor-supplied parchment at this slot: neither for nor against
            inside, at_start, at_end, n_tok = lost[sig]
            if not seg and a < b and (inside or (at_start and pos[b] == 0) or (at_end and pos[a] == len(w_toks))):
                continue  # lost text in this witness (before first extant word or after last): neither for nor against
            if not seg and a == b and (inside or (at_start and pos[a] == 0) or (at_end and pos[a] == len(w_toks))):
                continue
            lemma = "" if item.lemma == "om." else " ".join(c_toks[a:b])
            if _same(seg, lemma, lang, ns_map, lex):
                item.lemma_witnesses.append(sig)
                continue
            target = next((v for v in item.variants if _same(seg, str(v.get("reading", "")), lang, ns_map, lex)), None)
            if target is None:
                disp_seg = _expand_ns_tokens(seg, ns_map, lex)[0] if lang == "greek" and seg else seg
                target = {"reading": disp_seg or "om.", "witnesses": [], "weight_sum": 0.0}
                item.variants.append(target)
                if NOTE not in item.note:
                    item.note = (item.note + " " if item.note else "") + f"[{NOTE}]"
            elif lang == "greek" and seg and _has_accent_marks(seg) and "\u0305" not in seg and item.slot_index == -1:
                cur = str(target.get("reading", ""))
                if cur and cur != "om." and ("\u0305" in cur or not _has_accent_marks(cur)):
                    target["reading"] = seg
            target["witnesses"].append(sig)

    for item in adj.apparatus:
        if hasattr(item, "_tok"):
            del item._tok

    for reason, log in spelling.items():
        more = log["count"] - len(log["forms"])
        adj.disregarded.append(DisregardedItem(
            slot_index=-1, kept_form="(adopted text)",
            disregarded_forms=log["forms"] + ([f"… and {more} more"] if more > 0 else []),
            witnesses=sorted(log["witnesses"]),
            reason=f"Apparatus witness, not a variant: {reason}"))
    adj.apparatus.sort(key=lambda it: (it.kind != "verse", it.word_index if it.word_index >= 0 else 10 ** 6))
