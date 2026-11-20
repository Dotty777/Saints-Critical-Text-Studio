"""Record the readings of apparatus-only witnesses (catalog.APPARATUS_ONLY) after the text is decided.

The Majority and ecclesiastical editions (Greek: the Orthodox Septuagint, Boyd's TCGNT, the 1904 Patriarchal
text, Scrivener's and Boyd's TR; Hebrew: Ben Chayyim 1525, Letteris 1852; Latin: Hetzenauer 1906, Conte 2009,
the Sixtine Vulgate 1590) are collated against the adopted text, never voted with. For each verse:

* where an apparatus unit already exists, the edition is added to the side it supports (the lemma, a listed
  variant, or a new variant of that unit);
* where it differs in substance from a text the voting editions agree on, a new unit records its reading;
* a spelling, accent or pointing difference is logged once per verse in ``disregarded`` (Hebrew: an entry
  is made only when the consonants differ or a word is added or missing);
* a verse it lacks is added to the verse-level unit ("om. verse").

The adopted text, its confidence and the voting witnesses' units are never changed.
"""

import difflib
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from .brains.base import ApparatusItem, DisregardedItem
from .collator import canonical_compare_key, classify_forms, strip_punct
from .parsers import DOUBTFUL_CLOSE, DOUBTFUL_OPEN, GAP_WORD, LACUNA_MARK, VERSE_ABSENT

NOTE = ("Reading of an apparatus witness (a Majority or ecclesiastical edition): recorded here, "
        "it does not vote on the text.")
_MAX_LOGGED_FORMS = 12


def _tokens(text: str, language: str) -> Tuple[List[str], List[int]]:
    """Comparison tokens and, for each, the index of its word in ``text.split()``."""
    toks, word_of = [], []
    for i, w in enumerate(text.replace(DOUBTFUL_OPEN, "").replace(DOUBTFUL_CLOSE, "").split()):
        parts = w.replace("־", "־ ").split() if language == "hebrew" else [w]
        for p in parts:
            if p in (LACUNA_MARK, GAP_WORD) or (not strip_punct(p) and p != "׀"):
                continue
            toks.append(p)
            word_of.append(i)
    return toks, word_of


def _key(tok: str, language: str) -> str:
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
    joined = {f: keys[f].replace(" ", "") for f in forms}
    if len(set(joined.values())) == 1:
        return True, "Word division differs (same letters written as one word or two)"
    if len(lemma.split()) != len(reading.split()) and _is_spelling(joined[lemma], joined[reading], language)[0]:
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


def _same(a: str, b: str, language: str) -> bool:
    if a == b:
        return True
    if not a or not b or a == "om." or b == "om.":
        return (a in ("", "om.")) and (b in ("", "om."))
    return _is_spelling(a, b, language)[0]


def record_apparatus_witnesses(cv: Any, adj: Any, language: str) -> None:
    texts: Dict[str, str] = getattr(cv, "apparatus_texts", {}) or {}
    if not texts:
        return
    lang = language.lower()
    crit = adj.critical_text or ""
    c_toks, c_word = _tokens(crit, lang)
    c_keys = [_key(t, lang) for t in c_toks]
    n_words = len(crit.replace(DOUBTFUL_OPEN, "").replace(DOUBTFUL_CLOSE, "").split())
    first_tok = {}
    for t, w in enumerate(c_word):
        first_tok.setdefault(w, t)

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

    # 1. Verse presence, and new units where the voting editions agree but an edition differs in substance.
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
        w_toks, _ = _tokens(x, lang)
        w_keys = [_key(t, lang) for t in w_toks]
        ops = difflib.SequenceMatcher(a=c_keys, b=w_keys, autojunk=False).get_opcodes()
        aligned[sig] = (w_toks, ops, _pos_map(len(c_toks), ops))
        # Lost text ("…") is not evidence of omission: at the start or end of the verse it silences that
        # edge, inside the verse every omission (as in the collator's handling of fragmentary witnesses).
        parts = [t for t in x.split() if t]
        lost_inside = LACUNA_MARK in parts[1:-1]
        lost_start, lost_end = bool(parts) and parts[0] == LACUNA_MARK, bool(parts) and parts[-1] == LACUNA_MARK
        lost[sig] = (lost_inside, lost_start, lost_end, len(c_toks))
        for tag, i1, i2, j1, j2 in ops:
            if tag == "equal" or any(a <= i1 < b or a < i2 <= b or (a == b == i1) for a, b in voter_ranges):
                continue
            if tag == "delete" and (lost_inside or (lost_start and i1 == 0) or (lost_end and i2 == len(c_toks))):
                continue
            lemma = " ".join(c_toks[i1:i2])
            reading = " ".join(w_toks[j1:j2])
            is_sp, reason = _is_spelling(lemma, reading, lang)
            if is_sp:
                log = spelling.setdefault(reason, {"forms": [], "witnesses": set(), "count": 0})
                log["count"] += 1
                log["witnesses"].add(sig)
                if len(log["forms"]) < _MAX_LOGGED_FORMS:
                    log["forms"].append(f"{lemma} / {reading}")
                continue
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
            var = next((v for v in existing.variants if _same(reading, str(v.get("reading", "")), lang)), None)
            if var is None:
                var = {"reading": reading or "om.", "witnesses": [], "weight_sum": 0.0}
                existing.variants.append(var)
            if sig not in var["witnesses"]:
                var["witnesses"].append(sig)

    # 2. Every unit: put each edition on the side it supports (the lemma, a listed variant or a new variant).
    for sig, (w_toks, ops, pos) in aligned.items():
        for item in adj.apparatus:
            rng = getattr(item, "_tok", None) or tok_range(item)
            if rng is None:
                continue
            a, b = rng
            if a == b:  # an addition unit: what does the edition have at this point?
                seg = next((" ".join(w_toks[j1:j2]) for tag, i1, i2, j1, j2 in ops if tag == "insert" and i1 == a), "")
            else:
                seg = " ".join(w_toks[pos[a]:pos[b]])
            if any(sig in v.get("witnesses", []) for v in item.variants) or sig in item.lemma_witnesses:
                continue
            inside, at_start, at_end, n_tok = lost[sig]
            if not seg and a < b and (inside or (at_start and a == 0) or (at_end and b == n_tok)):
                continue  # lost text in this edition's file: neither for nor against
            lemma = "" if item.lemma == "om." else " ".join(c_toks[a:b])
            if _same(seg, lemma, lang):
                item.lemma_witnesses.append(sig)
                continue
            target = next((v for v in item.variants if _same(seg, str(v.get("reading", "")), lang)), None)
            if target is None:
                target = {"reading": seg or "om.", "witnesses": [], "weight_sum": 0.0}
                item.variants.append(target)
                if NOTE not in item.note:
                    item.note = (item.note + " " if item.note else "") + f"[{NOTE}]"
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
