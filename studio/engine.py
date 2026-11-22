"""High-Level Critical Text Studio Engine (Shared by Native Desktop GUI & Headless CLI)."""

from __future__ import annotations
from dataclasses import asdict
import difflib
import hashlib
import json
from collections import Counter
import re
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .brains import BrainConfig, create_brain
from .brains.base import GatekeeperVerdict
from .brains.offline_philological import OfflinePhilologicalBrain, _edition_family
from .catalog import (
    BOOKS_BY_SLUG,
    CRITICAL_OUTPUT_ROOTS,
    DATA_DIR,
    EDITION_FAMILIES,
    ORTHOGRAPHIC_BASE,
    ALIGNMENT_WINDOW,
    SILENT_MEANS_ABSENT,
    VERSIFICATION_ANCHORS,
    WITNESS_BOOK_EXCLUSIONS,
    BookSpec,
    is_apparatus_only,
    get_books_for_language,
    stream_of,
)
from .collator import (
    REMAP_MIN,
    SAME_NUMBER_FLOOR,
    _keyset,
    canonical_compare_key,
    align_versification,
    align_witnesses_for_verse,
    join_words,
    split_words,
    strip_punct,
    verse_similarity,
)
from .concordance import (
    export_saints_bible_pack,
    get_concept_visual_graph,
    get_concordance_dashboard_stats,
    get_verse_concordance_breakdown,
    index_saved_critical_texts,
    list_roots_and_morphemes,
    search_concordance_concepts,
    seed_stepbible_and_latin_lexicons,
    update_alignment_sense_and_lock,
    upsert_concept_and_sense,
)
from .db import get_conn, init_db, utc_now
from .exporter import ensure_repository_scaffold, export_chapter_files, sync_chapter_to_gdrive
from .lexicon import get_lexicon
from .source_repairs import coverage_gap_detail, repair_documented_imports
from .apparatus_witnesses import record_apparatus_witnesses
from .parsers import (
    DOUBTFUL_CLOSE,
    DOUBTFUL_OPEN,
    LACUNA_MARK,
    VERSE_ABSENT,
    extract_text_preview,
    load_book_from_witness,
    load_chapter_from_witness,
    load_sblgnt_apparatus,
)

SETTINGS_PATH = DATA_DIR / "settings.json"
SECRETS_PATH = DATA_DIR / ".local_secrets.json"
USER_WITNESS_DIR = DATA_DIR / "user_witnesses"


def witness_family(w: Dict[str, Any]) -> str:
    return EDITION_FAMILIES.get(str(w["id"])) or _edition_family(str(w["siglum"]))


def _in_scope(w: Dict[str, Any], book: BookSpec) -> bool:
    scope = str(w["testament_scope"])
    return book.testament in scope.split("/") or scope == "OT/NT"


def _strip_doubtful(text: str) -> str:
    return text.replace(DOUBTFUL_OPEN, "").replace(DOUBTFUL_CLOSE, "")


def _seq_keys(text: str, lang: str) -> List[str]:
    return [re.sub(r"ν$", "", k) for k in (canonical_compare_key(w, lang) for w in _strip_doubtful(text).split()) if k]


def _prefix_match(part: str, whole: str, lang: str, at_start: bool) -> float:
    """How well ``part`` matches the start (or end) of ``whole`` word for word, in order (0..1)."""
    pk, wk = _seq_keys(part, lang), _seq_keys(whole, lang)
    if not pk or not wk:
        return 0.0
    window = wk[: len(pk)] if at_start else wk[-len(pk):]
    return difflib.SequenceMatcher(a=pk, b=window, autojunk=False).ratio()


def _spill_split(x_txt: str, pos: str, a_txt: str, b_txt: str, other: str, ka: frozenset, kb: frozenset,
                 keys, sim, cont, lang: str = "greek") -> Optional[Tuple[str, str]]:
    """The witness's verse X carries its own anchor verse plus words that the anchor prints at the
    start of the next verse (or the end of the previous one), and the witness's neighbouring verse
    lacks them (2 Sam 11:27 / 12:1 in Swete). The moved words must match the neighbouring anchor
    verse's opening (or close) word for word and be words that verse has and this one does not.
    Returns the re-divided (verse i, verse j) or None."""
    toks = x_txt.split()
    own_txt, own_keys = (a_txt, ka) if pos == "i" else (b_txt, kb)
    nb_txt, nb_keys = (b_txt, kb) if pos == "i" else (a_txt, ka)
    unique = nb_keys - own_keys
    if len(toks) < 6 or cont(own_keys, keys(x_txt)) < 0.8 or not unique:
        return None
    base = sim(own_txt, x_txt)
    best = None
    for k in range(2, len(toks) - 2):
        if pos == "i":
            keep, give = " ".join(toks[:len(toks) - k]), " ".join(toks[len(toks) - k:])
        else:
            give, keep = " ".join(toks[:k]), " ".join(toks[k:])
        gk = keys(give)
        if len(gk & unique) < 2 or cont(gk, nb_keys) < 0.8 or (other and cont(gk, keys(other)) >= 0.5):
            continue
        order = _prefix_match(give, nb_txt, lang, at_start=(pos == "i"))
        if order < 0.6:
            continue
        s = sim(own_txt, keep)
        if s >= max(0.6, base + 0.03) and (best is None or s + order > best[0]):
            best = (s + order, keep, give)
    if not best:
        return None
    _s, keep, give = best
    # Snap the cut to the anchor's own division: the set-based scores above can move a repeated or
    # common word across it (2 Sam 11:27 'Καὶ ἀπέστειλεν', Ezek 38:3 'κύριος Κύριος').
    cut = len(keep.split()) if pos == "i" else len(give.split())
    snapped = _snap_division(toks, a_txt, b_txt, lang, cut)
    if snapped is not None and snapped != cut and abs(snapped - cut) <= 3 and 1 <= snapped <= len(toks) - 1:
        if pos == "i":
            keep, give = " ".join(toks[:snapped]), " ".join(toks[snapped:])
        else:
            give, keep = " ".join(toks[:snapped]), " ".join(toks[snapped:])
    # words the OCR printed on both sides of the division are given only once (1 Sam 12:7 / 12:8)
    gw, ow = give.split(), other.split()
    gk_seq = [re.sub(r"ν$", "", canonical_compare_key(t, lang)) for t in gw]
    ok_seq = [re.sub(r"ν$", "", canonical_compare_key(t, lang)) for t in ow]
    for n in range(min(len(gw) - 1, len(ow)), 0, -1):
        if pos == "i" and gk_seq[-n:] == ok_seq[:n] and (n >= 2 or len(gk_seq[-1]) >= 4):
            give = " ".join(gw[:-n])
            break
        if pos == "j" and ok_seq[-n:] == gk_seq[:n] and (n >= 2 or len(gk_seq[0]) >= 4):
            give = " ".join(gw[n:])
            break
    if pos == "i":
        return keep, (f"{give} {other}" if other else give)
    return (f"{other} {give}" if other else give), keep


def _snap_division(toks: List[str], a_txt: str, b_txt: str, lang: str, cut: int) -> Optional[int]:
    """Where the anchor's division between verses a and b falls among the witness's tokens (the
    number of witness tokens before it), by aligning the witness's words with a + b in order (final
    ν kept: τοῦτον is not τοῦτο, Jer 7:27). If the division falls inside a matched stretch, that is
    the answer. If it falls in an unmatched gap (words one edition lacks or OCR lost at the break,
    Deut 6:25 / 7:1), a scored cut inside the gap is kept and a cut outside it is moved to its edge.
    None if nothing on either side is matched."""
    def key(t: str) -> str:
        return canonical_compare_key(t, lang)

    wk = [key(t) or f"\x00{i}" for i, t in enumerate(toks)]
    ak = [k for k in (key(w) for w in _strip_doubtful(a_txt).split()) if k]
    bk = [k for k in (key(w) for w in _strip_doubtful(b_txt).split()) if k]
    if not ak or not bk:
        return None
    d = len(ak)
    blocks = [b for b in difflib.SequenceMatcher(a=ak + bk, b=wk, autojunk=False).get_matching_blocks() if b.size]
    for blk in blocks:
        if blk.a < d < blk.a + blk.size:
            return blk.b + (d - blk.a)
    ends_a = [blk.b + blk.size for blk in blocks if blk.a + blk.size <= d]
    starts_b = [blk.b for blk in blocks if blk.a >= d]
    if not ends_a or not starts_b:
        return None
    gap_start, gap_end = max(ends_a), min(starts_b)
    if gap_start > gap_end:
        return None
    if gap_start <= cut <= gap_end:
        return cut
    return gap_start if cut < gap_start else gap_end


def _split_merged_verses(
    anchor_book: Dict[int, Dict[int, str]], wit_book: Dict[int, Dict[int, str]], chapter: int, lang: str,
) -> Tuple[Dict[int, Dict[int, str]], List[str]]:
    """Re-divide a witness verse that runs across one of the anchor's verse divisions, so each part
    is collated with its own verse (otherwise the anchor's verse stands alone while the same words
    are printed again in the neighbouring verse). Cases: Swete's Gen 3:1 = Brenton's 2:25 + 3:1 and
    MAM's Num 26:1 = WLC's 25:19 + 26:1 (the other number is empty in the witness); Swete's Ezra 6:19
    = Brenton's 6:19 + 6:20; Swete's Ezek 1:2 = Brenton's 1:2 + the start of 1:3.

    Guards (from the second review): the witness verse must contain the anchor verse that carries
    its own number (so a one-off numbering is never "re-divided"); the witness's other verse, if
    any, must not be a whole verse of its own (it matches no anchor verse within two numbers); a
    number the witness marks as absent is never filled; and the part handed to the other verse must
    carry at least half of that verse's own words, so a shared refrain (Ps 117:3/4) is never cut.
    Deterministic, so neighbouring chapters divide alike."""
    chs = [c for c in (chapter - 1, chapter, chapter + 1) if c in anchor_book]
    seq = [(c, v) for c in chs for v in sorted(anchor_book[c]) if anchor_book[c][v]]
    out = wit_book
    notes: List[str] = []

    def keys(t: str) -> frozenset:
        return _keyset(_strip_doubtful(t), lang)

    def sim(a: str, b: str) -> float:
        return verse_similarity(_strip_doubtful(a), _strip_doubtful(b), lang) if a and b else 0.0

    def cont(ka: frozenset, kx: frozenset) -> float:
        return len(ka & kx) / len(ka) if ka else 0.0

    def other_is_elsewhere(txt: str, nb_chapter: int) -> bool:
        """The witness's other verse is its copy of an anchor verse in a different chapter (Swete's
        Zeph 3:1 is Brenton's 2:15): then nothing may be appended to it. A one-verse offset inside
        the chapter (Exod 39–40, Ezek 42, Isa 38) is left to the chain of spills."""
        best = max(((sim(anchor_book[c][v], txt), c) for c, v in seq), default=(0.0, nb_chapter))
        return best[0] >= 0.5 and best[1] != nb_chapter

    def whole_verse_elsewhere(txt: str, i: int) -> bool:
        near = seq[max(0, i - 2): i + 4]
        return any(sim(anchor_book[c][v], txt) >= 0.5 for c, v in near)

    for i in range(len(seq) - 1):
        (ci, vi), (cj, vj) = seq[i], seq[i + 1]
        if ci != cj:
            xi_b, xj_b = out.get(ci, {}).get(vi, ""), out.get(cj, {}).get(vj, "")
            if vi not in out.get(ci, {}) and xj_b and sim(anchor_book[ci][vi], xj_b) >= 0.85 and sim(anchor_book[cj][vj], xj_b) < 0.4:
                if out is wit_book:
                    out = dict(wit_book)
                out[ci] = dict(out.get(ci, {}))
                out[cj] = dict(out.get(cj, {}))
                out[ci][vi] = out[cj].pop(vj)
                notes.append(f"verse {cj}:{vj} moved to {ci}:{vi} across chapter break before re-division")
            elif vj not in out.get(cj, {}) and xi_b and sim(anchor_book[cj][vj], xi_b) >= 0.85 and sim(anchor_book[ci][vi], xi_b) < 0.4:
                if out is wit_book:
                    out = dict(wit_book)
                out[ci] = dict(out.get(ci, {}))
                out[cj] = dict(out.get(cj, {}))
                out[cj][vj] = out[ci].pop(vi)
                notes.append(f"verse {ci}:{vi} moved to {cj}:{vj} across chapter break before re-division")

    for i in range(len(seq) - 1):
        (ci, vi), (cj, vj) = seq[i], seq[i + 1]
        a_txt, b_txt = anchor_book[ci][vi], anchor_book[cj][vj]
        ka, kb = keys(a_txt), keys(b_txt)
        if len(ka) < 3 or len(kb) < 3:
            continue
        has_i, has_j = vi in out.get(ci, {}), vj in out.get(cj, {})
        xi, xj = out.get(ci, {}).get(vi, ""), out.get(cj, {}).get(vj, "")
        for pos, x_txt, other, other_present in (("i", xi, xj, has_j), ("j", xj, xi, has_i)):
            if not x_txt or (other_present and not other):
                continue  # an explicit "verse absent" in the witness is never filled
            kx = keys(x_txt)
            own_k, nb_k = (ka, kb) if pos == "i" else (kb, ka)
            if cont(own_k, kx) < 0.8:
                continue  # X is not this anchor verse at all (a one-off numbering): leave it to alignment
            # A spill (the witness's verse carries the opening words of the next anchor verse, which
            # its own next verse lacks: 2 Sam 11:27 / 12:1) is tested first: there the neighbouring
            # verse is, apart from those words, a whole verse, so the guard below must not stop it.
            spill = None
            if not (other and cont(keys(other), nb_k) < 0.5 and other_is_elsewhere(other, cj if pos == "i" else ci)):
                spill = _spill_split(x_txt, pos, a_txt, b_txt, other, ka, kb, keys, sim, cont, lang)
            if spill:
                if out is wit_book:
                    out = dict(wit_book)
                out[ci] = dict(out.get(ci, {}))
                out[cj] = dict(out.get(cj, {}))
                out[ci][vi], out[cj][vj] = spill
                src = f"{ci}:{vi}" if pos == "i" else f"{cj}:{vj}"
                notes.append(f"verse {src} runs into its neighbour across the anchor's division "
                             f"between {ci}:{vi} and {cj}:{vj}; re-divided there")
                break
            if other and whole_verse_elsewhere(other, i):
                continue
            if cont(nb_k, kx) < 0.5:
                continue
            unique = nb_k - own_k
            toks = x_txt.split()
            best = None
            for k in range(1, len(toks)):
                head, tail = " ".join(toks[:k]), " ".join(toks[k:])
                give = tail if pos == "i" else head
                if not unique or len(keys(give) & unique) < 0.5 * len(unique):
                    continue  # the moved part must carry the neighbour verse's own words
                new_i = head if pos == "i" or not other else f"{other} {head}"
                new_j = tail if pos == "j" or not other else f"{tail} {other}"
                sa, sb = sim(a_txt, new_i), sim(b_txt, new_j)
                if sa >= 0.5 and sb >= 0.5 and (best is None or sa + sb > best[0]):
                    best = (sa + sb, new_i, new_j)
            if not best:
                continue
            if out is wit_book:
                out = dict(wit_book)
            out[ci] = dict(out.get(ci, {}))
            out[cj] = dict(out.get(cj, {}))
            out[ci][vi], out[cj][vj] = best[1], best[2]
            src = f"{ci}:{vi}" if pos == "i" else f"{cj}:{vj}"
            notes.append(f"verse {src} runs across the anchor's division between {ci}:{vi} and {cj}:{vj}; re-divided there")
            break
    return out, notes


def _trim_overlong(
    mapped: Dict[int, str], reference: Dict[int, str], anchor_book: Dict[int, Dict[int, str]], chapter: int, lang: str,
    wit_book: Optional[Dict[int, Dict[int, str]]] = None,
) -> List[str]:
    """A witness verse much longer than the anchor verse it was aligned to, whose extra words are the
    anchor's verse in ANOTHER CHAPTER and are also the witness's own text there (Swete's Sir 30:24 =
    Brenton's 30:24 + 33:12, where chapters 30–36 stand in a different order): keep only the span
    that matches this anchor verse, so the extra words are not printed twice. Never for words the
    anchor prints in a neighbouring verse of the same chapter, and never for an addition the other
    chapter's verse merely resembles (a harmonising plus in the NT is a variant, not a duplicate)."""
    notes: List[str] = []
    for u, x in list(mapped.items()):
        ref = reference.get(u, "")
        if not x or not ref:
            continue
        xt, rn = x.split(), len(ref.split())
        if len(xt) < 1.6 * rn or len(xt) - rn < 4:
            continue
        xk, rk = _seq_keys(x, lang), _seq_keys(ref, lang)
        sm = difflib.SequenceMatcher(a=xk, b=rk, autojunk=False)
        blocks = [b for b in sm.get_matching_blocks() if b.size]
        if not blocks:
            continue
        i, j = blocks[0].a, blocks[-1].a + blocks[-1].size  # the span of X that lines up with the anchor
        if len(xk) != len(xt) or i >= j:
            continue
        rest = " ".join(xt[:i] + xt[j:])
        restk = _keyset(_strip_doubtful(rest), lang)
        if len(restk) < 3:
            continue
        here = anchor_book.get(chapter, {})
        if any(t and v != u and abs(v - u) <= 3 and len(restk & _keyset(_strip_doubtful(t), lang)) / len(restk) >= 0.8
               for v, t in here.items()):
            continue  # the anchor prints these words in a neighbouring verse here (Exod 40:8 / Brenton's 40:10)
        hit = None
        for c, vs in anchor_book.items():
            if c == chapter:
                continue
            for v, t in vs.items():
                ok = _keyset(_strip_doubtful(t), lang) if t else frozenset()
                if ok and len(restk & ok) / len(restk) >= 0.8 and 2 * len(restk & ok) / (len(restk) + len(ok)) >= 0.6:
                    hit = (c, v)
        if hit is None or (len(xt[i:j]) < 3 and rn >= 5):
            continue
        mapped[u] = " ".join(xt[i:j])
        notes.append(f"verse {u} also carried the anchor's {hit[0]}:{hit[1]} (a different chapter); trimmed to its own part")
    return notes


_BARE_ENDINGS = frozenset({"και", "δε", "ο", "η", "το", "τον", "την", "του", "τησ", "τω", "τη", "οι", "αι", "τα",
                           "τουσ", "τασ", "των", "τοισ", "ταισ", "εν", "ε", "εισ", "εκ", "επι", "προσ"})  # keys, final ν dropped


def _drop_duplicated_tails(mapped: Dict[int, str], reference: Dict[int, str], lang: str) -> List[str]:
    """Swete's digitisation sometimes repeats the next verse's words at the end of a verse (Lev 19:30
    ends with 19:31's clause, Job 33:31 with 33:32's 'λάλησον, θέλω γὰρ δικαιωθῆναί σε'). When the
    witness's own next verse has those words too, and the anchor has them in the next verse but not
    in this one, the repeated tail is cut and marked as a lacuna: the duplicate is not printed twice,
    and it no longer outvotes the anchor's own ending of this verse (Lev 19:30 'φοβηθήσεσθε· ἐγώ εἰμι
    κύριος'). At least three words of the verse are always kept."""
    def key(t: str) -> str:
        return re.sub(r"ν$", "", canonical_compare_key(t, lang))

    notes: List[str] = []
    for v in sorted(mapped):
        x, y = mapped.get(v, ""), mapped.get(v + 1, "")
        ref_here, ref_next = reference.get(v, ""), reference.get(v + 1, "")
        if not x or not y or not ref_next or LACUNA_MARK in x or x == VERSE_ABSENT or y == VERSE_ABSENT:
            continue
        toks = x.split()
        keys = [key(t) for t in toks]
        yk = [k for k in (key(t) for t in _strip_doubtful(y).split()) if k]
        # the same ν-stripped keys on both sides (τῶν / ἄρτων must match the anchor's own verse)
        kset = lambda t: {k for k in (key(w) for w in _strip_doubtful(t).split()) if k}  # noqa: E731
        here, nxt = kset(ref_here), kset(ref_next)
        best = 0
        for k in range(4, min(len(toks) - 3, 40) + 1):
            tail = [t for t in keys[-k:] if t]
            if len(tail) < 4:
                continue
            blocks = [b for b in difflib.SequenceMatcher(a=tail, b=yk, autojunk=False).get_matching_blocks() if b.size]
            if not blocks or blocks[0].a > 1 or (blocks[0].a == 1 and len(tail[0]) > 5):
                continue  # the tail must open with the repeated words (one OCR fragment allowed: 'θοις')
            if sum(b.size for b in blocks) / (len(tail) - blocks[0].a) < 0.7:
                continue
            ts = set(tail)
            if len(ts & nxt) / len(ts) < 0.6 or len(ts & here) / len(ts) >= 0.5:
                continue
            # every cut word (beyond the allowed fragment) must really be repeated in the witness's next
            # verse (Ezek 21:7 'προφητεύσεις' is not: a different verse division, not a duplicate), and
            # the last word kept must belong to the anchor's own verse
            # the allowed leading fragment too, when it is longer than three letters (Judg 8:11 'εφυγο')
            content = [t for t in tail[(0 if tail and len(tail[0]) > 3 else blocks[0].a):] if len(t) >= 3]
            if any(max((difflib.SequenceMatcher(a=t, b=u).ratio() for u in yk), default=0) < 0.75 for t in content):
                continue
            kept = [t for t in keys[:-k] if len(t) >= 4]
            if kept and kept[-1] not in here:
                continue
            last_kept = next((t for t in reversed(keys[:-k]) if t), "")
            if last_kept in _BARE_ENDINGS:
                continue  # never leave the verse ending on 'καί' or an article
            best = k
        if best:
            mapped[v] = " ".join(toks[:-best]) + " " + LACUNA_MARK
            notes.append(f"verse {v}: its last {best} words repeat the witness's next verse (the anchor has them only "
                         "there); cut here as a duplicate and treated as a lacuna")
    return notes


def _resolve_break_lacunae(
    mapped: Dict[int, str], moved: Dict[int, str], wit_book: Dict[int, Dict[int, str]],
    reference: Dict[int, str], chapter: int, lang: str,
) -> List[str]:
    """The parser leaves a lacuna mark where a chapter numeral stood at the edge of a verse (the OCR
    often lost words there: Gen 9:1, 27:46). If the words the anchor has at that point turn up in the
    witness's neighbouring verse instead (2 Sam 11:27 / 12:1), nothing was lost: remove the mark, so
    the witness votes normally."""
    notes: List[str] = []
    for v, t in list(mapped.items()):
        if not t or LACUNA_MARK not in t:
            continue
        ref = reference.get(v, "")
        count = lambda s: Counter(k for k in (canonical_compare_key(w, lang) for w in _strip_doubtful(s).split()) if k)  # noqa: E731
        missing = set((count(ref) - count(t)).keys())  # by count: a καί elsewhere does not hide a lost καί
        src = moved.get(v)
        c0, v0 = (int(src.split(":")[0]), int(src.split(":")[1])) if src else (chapter, v)
        at_start = t.strip().startswith(LACUNA_MARK)
        if at_start:
            prev = wit_book.get(c0, {})
            nb = prev.get(v0 - 1) or (wit_book.get(c0 - 1, {}).get(max(wit_book.get(c0 - 1, {}) or [0])) if v0 == 1 else "")
        else:
            nb = wit_book.get(c0, {}).get(v0 + 1) or wit_book.get(c0 + 1, {}).get(1, "")
        moved_away = bool(missing) and bool(nb) and len(missing & _keyset(_strip_doubtful(nb), lang)) / len(missing) >= 0.6
        if not missing or moved_away:
            mapped[v] = " ".join(w for w in t.split() if w != LACUNA_MARK)
            if moved_away:
                notes.append(f"verse {v}: the words at the chapter break are in its neighbouring verse (no lacuna)")
    return notes


class CriticalTextEngine:
    def __init__(self) -> None:
        init_db()
        ensure_repository_scaffold()
        self.config = self.load_settings()

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    def load_settings(self) -> BrainConfig:
        cfg = BrainConfig()
        if SETTINGS_PATH.exists():
            try:
                raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                cfg.provider_id = raw.get("provider_id", cfg.provider_id)
                cfg.offline_locked = bool(raw.get("offline_locked", True))
                cfg.local_endpoint = raw.get("local_endpoint", cfg.local_endpoint)
                cfg.local_model = raw.get("local_model", cfg.local_model)
                cfg.gemini_model = raw.get("gemini_model", cfg.gemini_model)
                cfg.gemini_thinking_level = raw.get("gemini_thinking_level", cfg.gemini_thinking_level)
                cfg.use_decision_model = bool(raw.get("use_decision_model", True))
                cfg.claude_review = bool(raw.get("claude_review", False))
                cfg.claude_model = raw.get("claude_model", cfg.claude_model) or cfg.claude_model
                cfg.claude_effort = raw.get("claude_effort", cfg.claude_effort) or cfg.claude_effort
                cfg.openai_model = raw.get("openai_model", cfg.openai_model) or cfg.openai_model
                cfg.openai_effort = raw.get("openai_effort", cfg.openai_effort) or cfg.openai_effort
            except (OSError, ValueError):
                pass
        if SECRETS_PATH.exists():
            try:
                sec = json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
                cfg.gemini_api_key = sec.get("gemini_api_key", "")
                cfg.anthropic_api_key = sec.get("anthropic_api_key", "")
                cfg.openai_api_key = sec.get("openai_api_key", "")
            except (OSError, ValueError):
                pass
        return cfg

    def save_settings(self, cfg: BrainConfig) -> None:
        self.config = cfg
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        public_data = {
            "provider_id": cfg.provider_id,
            "offline_locked": cfg.offline_locked,
            "local_endpoint": cfg.local_endpoint,
            "local_model": cfg.local_model,
            "gemini_model": cfg.gemini_model,
            "gemini_thinking_level": cfg.gemini_thinking_level,
            "use_decision_model": cfg.use_decision_model,
            "claude_review": cfg.claude_review,
            "claude_model": cfg.claude_model,
            "claude_effort": cfg.claude_effort,
            "openai_model": cfg.openai_model,
            "openai_effort": cfg.openai_effort,
        }
        SETTINGS_PATH.write_text(json.dumps(public_data, indent=2), encoding="utf-8")
        SECRETS_PATH.write_text(
            json.dumps({"gemini_api_key": cfg.gemini_api_key or "", "anthropic_api_key": cfg.anthropic_api_key or "",
                        "openai_api_key": cfg.openai_api_key or ""}, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Witness registry
    # ------------------------------------------------------------------
    def list_witnesses(self, language: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_conn() as conn:
            if language:
                rows = conn.execute(
                    "SELECT * FROM witnesses WHERE language = ? ORDER BY status = 'ADMITTED' DESC, tier ASC, weight DESC",
                    (language.lower(),),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM witnesses ORDER BY language, status = 'ADMITTED' DESC, tier ASC, weight DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    def list_gatekeeper_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute("SELECT * FROM gatekeeper_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def update_witness_status(
        self,
        witness_id: str,
        new_status: str,
        new_weight: Optional[float] = None,
        new_tier: Optional[int] = None,
        reason_note: str = "Manual user override in Desktop Studio",
    ) -> None:
        now = utc_now()
        with get_conn() as conn:
            row = conn.execute("SELECT * FROM witnesses WHERE id = ?", (witness_id,)).fetchone()
            if not row:
                raise KeyError(f"Witness {witness_id} not found.")
            w = new_weight if new_weight is not None else (0.85 if new_status == "ADMITTED" and float(row["weight"]) == 0.0 else float(row["weight"]))
            if new_status != "ADMITTED":
                w = 0.0
            w = max(0.0, min(1.0, float(w)))
            t = new_tier if new_tier is not None else int(row["tier"])
            conn.execute(
                """
                UPDATE witnesses
                SET status = ?, weight = ?, tier = ?, gatekeeper_summary = ?, human_override = 1, updated_at = ?
                WHERE id = ?
                """,
                (new_status, w, t, f"[Human Override → {new_status}] {reason_note}", now, witness_id),
            )
            conn.execute(
                """
                INSERT INTO gatekeeper_log (
                    created_at, language, witness_title, file_path, decision,
                    tier_assigned, confidence, model_used, summary, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (now, row["language"], f"{row['siglum']} — {row['title']}", row["file_path"], new_status, t, 1.0,
                 "Human Scholarly Override", reason_note, json.dumps({"manual_override": True, "weight": w})),
            )

    def _collect_existing_samples(self, language: str) -> Dict[str, str]:
        books = get_books_for_language(language)
        samples: Dict[str, str] = {}
        for w in self.list_witnesses(language):
            if w["status"] != "ADMITTED":
                continue
            for book in books[:1] + [b for b in books if b.testament == "NT"][:1]:
                ch_map = load_chapter_from_witness(w, book, 1)
                if ch_map:
                    samples[str(w["siglum"])] = " ".join(ch_map[k] for k in sorted(ch_map)[:10])
                    break
        return samples

    def ingest_new_witness(
        self,
        language: str,
        siglum: str,
        title: str,
        testament_scope: str = "OT/NT",
        declared_license: str = "",
        source_file: Optional[Path] = None,
        pasted_text: str = "",
    ) -> Tuple[str, GatekeeperVerdict]:
        """Evaluate a new witness file or pasted text via the AI Gatekeeper Brain and register it."""
        lang = language.lower()
        dest_dir = USER_WITNESS_DIR / lang
        dest_dir.mkdir(parents=True, exist_ok=True)

        slug_hash = hashlib.sha256(f"{siglum}-{title}-{utc_now()}".encode("utf-8")).hexdigest()[:8]
        wid = f"usr-{lang}-{slug_hash}"

        if source_file and source_file.exists():
            dest_path = dest_dir / f"{wid}_{source_file.name}"
            shutil.copy2(str(source_file), str(dest_path))
        else:
            dest_path = dest_dir / f"{wid}.txt"
            dest_path.write_text(pasted_text, encoding="utf-8")

        sample_text, file_meta = extract_text_preview(dest_path)
        existing_samples = self._collect_existing_samples(lang)

        brain = create_brain(self.config)
        verdict = brain.evaluate_witness(
            language=lang,
            title=title,
            declared_license=declared_license,
            sample_text=sample_text,
            file_meta=file_meta,
            existing_samples=existing_samples,
        )

        # Sigla key the collation; two witnesses with one siglum would overwrite each other.
        taken = {str(w["siglum"]) for w in self.list_witnesses(lang)}
        final_siglum = siglum.strip() or wid
        n = 2
        while final_siglum in taken:
            final_siglum = f"{siglum.strip() or wid} ({n})"
            n += 1

        now = utc_now()
        details_json = json.dumps({"scores": verdict.scores, "reasons": verdict.reasons, "file_meta": file_meta}, ensure_ascii=False)
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO witnesses (
                    id, language, testament_scope, siglum, title, tier, status, license,
                    date_range, text_type, weight, parser_kind, file_path,
                    gatekeeper_summary, gatekeeper_json, human_override, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'custom_auto', ?, ?, ?, 0, ?, ?)
                """,
                (
                    wid, lang, testament_scope, final_siglum, title.strip() or dest_path.name,
                    verdict.tier_assigned, verdict.decision, verdict.detected_license, "User Added Witness",
                    verdict.detected_text_type,
                    verdict.recommended_weight if verdict.decision == "ADMITTED" else 0.0,
                    str(dest_path), verdict.summary, details_json, now, now,
                ),
            )
            conn.execute(
                """
                INSERT INTO gatekeeper_log (
                    created_at, language, witness_title, file_path, decision,
                    tier_assigned, confidence, model_used, summary, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (now, lang, f"{final_siglum} — {title}", str(dest_path), verdict.decision, verdict.tier_assigned,
                 verdict.confidence, verdict.model_used, verdict.summary, details_json),
            )
        return wid, verdict

    # ------------------------------------------------------------------
    # Collation
    # ------------------------------------------------------------------
    def _pick_by_kind(self, witnesses: List[Dict[str, Any]], kinds: List[str], has_text) -> Optional[Dict[str, Any]]:
        for kind in kinds:
            for w in witnesses:
                if w["parser_kind"] == kind and has_text(w):
                    return w
        return None

    def build_collation(self, language: str, book_slug: str, chapter: int) -> Dict[str, Any]:
        """Load, re-align and collate every admitted witness for one chapter (no persistence)."""
        lang = language.lower()
        if book_slug not in BOOKS_BY_SLUG:
            raise KeyError(f"Unknown book '{book_slug}'.")
        book = BOOKS_BY_SLUG[book_slug]
        if not 1 <= int(chapter) <= book.chapters:
            raise ValueError(f"{book.title} has {book.chapters} chapters; chapter {chapter} does not exist.")

        scope_witnesses = [w for w in self.list_witnesses(lang) if _in_scope(w, book)]
        admitted = [w for w in scope_witnesses if w["status"] == "ADMITTED"]
        quarantined = [w for w in scope_witnesses if w["status"] != "ADMITTED"]
        exclusion_notes = [
            f"{w['siglum']}: {WITNESS_BOOK_EXCLUSIONS[(str(w['id']), book.slug)]}"
            for w in admitted if (str(w["id"]), book.slug) in WITNESS_BOOK_EXCLUSIONS
        ]
        admitted = [w for w in admitted if (str(w["id"]), book.slug) not in WITNESS_BOOK_EXCLUSIONS]
        # Apparatus-only editions are re-aligned like every witness but kept out of the vote (catalog.APPARATUS_ONLY).
        apparatus_only = [w for w in admitted if is_apparatus_only(w)]
        admitted = [w for w in admitted if not is_apparatus_only(w)]

        book_texts = {str(w["siglum"]): load_book_from_witness(w, book) for w in admitted + apparatus_only}
        source_notes = []
        for w in admitted + apparatus_only:
            sig = str(w["siglum"])
            book_texts[sig], repairs = repair_documented_imports(w, book.slug, book_texts[sig])
            source_notes.extend(f"{sig}: {note}" for note in repairs.get(chapter, []))
        has_chapter = lambda w: bool(book_texts[str(w["siglum"])].get(chapter))  # noqa: E731

        key = (lang, book.testament)
        anchor = self._pick_by_kind(admitted, VERSIFICATION_ANCHORS.get(key, []), has_chapter)
        if anchor is None:
            with_ch = [w for w in admitted if has_chapter(w)]
            anchor = max(with_ch, key=lambda w: float(w["weight"])) if with_ch else None
        if anchor is None:
            detail = coverage_gap_detail(lang, book.slug, chapter)
            raise LookupError(f"No admitted {lang.title()} witness contains {book.title} {chapter}."
                              + (f" {detail}" if detail else ""))
        anchor_sig = str(anchor["siglum"])
        reference = {v: _strip_doubtful(t) for v, t in book_texts[anchor_sig][chapter].items()}
        base = self._pick_by_kind(admitted, ORTHOGRAPHIC_BASE.get(key, []), has_chapter)
        base_sig = str(base["siglum"]) if base else ""

        mapped_by_sig: Dict[str, Dict[int, str]] = {}
        moved_by_sig: Dict[str, Dict[int, str]] = {}
        appar_by_sig: Dict[str, Dict[int, str]] = {}
        appar_moved: Dict[str, Dict[int, str]] = {}
        appar_meta: List[Dict[str, Any]] = []
        versification_notes: List[str] = list(exclusion_notes) + source_notes
        active_meta: List[Dict[str, Any]] = []
        for w in admitted + apparatus_only:
            sig = str(w["siglum"])
            chapters = book_texts[sig]
            if sig == anchor_sig:
                mapped, moved = dict(chapters[chapter]), {}
            else:
                width = ALIGNMENT_WINDOW.get((lang, book.slug), ALIGNMENT_WINDOW.get(book.slug, 1))
                if not (lang == "greek" and book.testament == "NT"):
                    # (the NT editions divide verses alike; re-division there only misfired)
                    chapters, split_notes = _split_merged_verses(book_texts[anchor_sig], chapters, chapter, lang)
                    versification_notes.extend(f"{sig}: {n}" for n in split_notes)
                cands = {(c, v): t for c in range(chapter - width, chapter + width + 1) for v, t in chapters.get(c, {}).items()}
                if not cands:
                    continue
                cands_plain = {k: _strip_doubtful(t) for k, t in cands.items()}
                # Two copies of one edition are paired by number only when the wording really agrees:
                # the Saints Latin column and the Clementine number Jeremiah 25–51 differently.
                same_edition = witness_family(w) == witness_family(anchor)
                neighbour_reference = None
                if lang == "greek" and book.testament == "OT":
                    neighbour_reference = {(c, v): _strip_doubtful(t)
                        for c in range(chapter - width, chapter + width + 1) if c != chapter
                        for v, t in book_texts[anchor_sig].get(c, {}).items()}
                mapped_plain, moved, notes = align_versification(
                    reference, chapter, cands_plain, lang,
                    same_number_floor=REMAP_MIN if same_edition else SAME_NUMBER_FLOOR,
                    neighbour_reference=neighbour_reference)
                # restore ⟦ ⟧ markers that were stripped for the similarity test
                mapped = {}
                for v, t in mapped_plain.items():
                    src = (int(moved[v].split(":")[0]), int(moved[v].split(":")[1])) if v in moved else (chapter, v)
                    mapped[v] = cands.get(src, t) if cands_plain.get(src) == t else t
                versification_notes.extend(f"{sig}: {n}" for n in notes)
                if not (lang == "greek" and book.testament == "NT"):
                    versification_notes.extend(f"{sig}: {n}" for n in _trim_overlong(mapped, reference, book_texts[anchor_sig], chapter, lang))
                if not is_apparatus_only(w):  # an apparatus witness's "…" marks only a documented file gap
                    versification_notes.extend(f"{sig}: {n}" for n in _resolve_break_lacunae(mapped, moved, chapters, reference, chapter, lang))
                if lang == "greek" and book.testament != "NT":  # an OCR artefact of the Swete files
                    versification_notes.extend(f"{sig}: {n}" for n in _drop_duplicated_tails(mapped, reference, lang))
                if moved:
                    sample = ", ".join(f"{v}←{r}" for v, r in sorted(moved.items())[:6])
                    versification_notes.append(f"{sig}: {len(moved)} verse(s) re-aligned by content ({sample}{'…' if len(moved) > 6 else ''})")
            if mapped and is_apparatus_only(w):
                appar_by_sig[sig] = mapped
                appar_moved[sig] = moved
                appar_meta.append(w)
            elif mapped:
                mapped_by_sig[sig] = mapped
                moved_by_sig[sig] = moved
                active_meta.append(w)

        base = self._pick_by_kind(
            active_meta,
            ORTHOGRAPHIC_BASE.get(key, []),
            lambda w: bool(mapped_by_sig.get(str(w["siglum"]))),
        )
        base_sig = str(base["siglum"]) if base else ""

        lexicon = get_lexicon(lang, [w for w in self.list_witnesses(lang)
                                     if w["status"] == "ADMITTED" and not is_apparatus_only(w)])
        weights = {str(w["siglum"]): float(w["weight"]) for w in active_meta}
        families = {str(w["siglum"]): witness_family(w) for w in active_meta}
        ext_app = load_sblgnt_apparatus(book.sbl_code, chapter) if lang == "greek" and book.testament == "NT" else {}

        all_verse_nums = sorted({v for m in mapped_by_sig.values() for v in m})
        meta_by_sig = {str(w["siglum"]): w for w in active_meta}
        self._mark_silent_editions(mapped_by_sig, meta_by_sig, all_verse_nums, versification_notes, book_texts, chapter)
        self._mark_silent_editions(appar_by_sig, {str(w["siglum"]): w for w in appar_meta}, all_verse_nums,
                                   versification_notes, book_texts, chapter)
        for sig, m in appar_by_sig.items():
            extra = sorted(u for u, t in m.items() if t and u not in all_verse_nums)
            if extra:
                versification_notes.append(
                    f"{sig}: has verse(s) {', '.join(map(str, extra))} that no voting edition prints here "
                    "(an apparatus witness: not printed)")
        single_stream_notes = self._versification_duplicates(
            lang, book, chapter, mapped_by_sig, book_texts, families, all_verse_nums, versification_notes, anchor_sig)
        collated = []
        for v in all_verse_nums:
            texts = {s: m[v] for s, m in mapped_by_sig.items() if m.get(v)}
            absent = sorted(s for s, m in mapped_by_sig.items() if v in m and m[v] == VERSE_ABSENT)
            if not texts:
                continue
            cv = align_witnesses_for_verse(
                verse_num=v,
                witness_texts=texts,
                witness_weights={s: weights[s] for s in texts},
                language=lang,
                external_apparatus=ext_app.get(v, []),
                pivot_preference=[base_sig] if base_sig else None,
                book_slug=book.slug,
                chapter=chapter,
            )
            cv.absent_witnesses = absent
            cv.doubtful_witnesses = sorted(s for s, t in texts.items() if t.startswith(DOUBTFUL_OPEN) and t.endswith(DOUBTFUL_CLOSE))
            cv.witness_refs = {s: moved_by_sig[s][v] for s in texts if v in moved_by_sig.get(s, {})}
            cv.witness_weights = {s: weights[s] for s in list(texts) + absent}
            cv.witness_families = {s: families[s] for s in list(texts) + absent}
            cv.base_siglum = base_sig
            cv.lexicon = lexicon
            cv.testament = book.testament
            cv.single_stream = single_stream_notes.get(v, "")
            cv.apparatus_texts = {s: m[v] for s, m in appar_by_sig.items() if v in m}
            cv.apparatus_refs = {s: appar_moved[s][v] for s in cv.apparatus_texts if v in appar_moved.get(s, {})}
            cv.open_apparatus_sigla = {str(w["siglum"]) for w in appar_meta if int(w.get("tier", 5)) < 5}
            collated.append(cv)

        return {
            "book": book,
            "language": lang,
            "collated": collated,
            "admitted": active_meta,
            "apparatus_witnesses": appar_meta,
            "quarantined": quarantined,
            "anchor_siglum": anchor_sig,
            "base_siglum": base_sig,
            "versification_notes": versification_notes,
        }

    @staticmethod
    def _mark_silent_editions(mapped_by_sig: Dict[str, Dict[int, str]], meta_by_sig: Dict[str, Dict[str, Any]],
                              verse_nums: List[int], notes: List[str],
                              book_texts: Optional[Dict[str, Dict[int, Dict[int, str]]]] = None, chapter: int = 0) -> None:
        """A printed edition that omits a verse simply skips its number (SBLGNT has no Matt 17:21).
        Count it as lacking the verse when it prints verses within two numbers on both sides — but
        not when it does print a verse with that number that was aligned elsewhere (RP2018 numbers
        Matt 23:13/14 the other way round)."""
        for sig, mapped in mapped_by_sig.items():
            if str(meta_by_sig[sig]["id"]) not in SILENT_MEANS_ABSENT:
                continue
            own = (book_texts or {}).get(sig, {}).get(chapter, {})
            silent = [
                v for v in verse_nums
                if v not in mapped
                and not own.get(v)
                and any(mapped.get(u) for u in (v - 1, v - 2))
                and any(mapped.get(u) for u in (v + 1, v + 2))
            ]
            for v in silent:
                mapped[v] = VERSE_ABSENT
            if silent:
                notes.append(f"{sig}: no verse numbered {', '.join(map(str, silent))} (counted as lacking it)")

    def _versification_duplicates(
        self, lang: str, book: BookSpec, chapter: int,
        mapped_by_sig: Dict[str, Dict[int, str]],
        book_texts: Dict[str, Dict[int, Dict[int, str]]], families: Dict[str, str],
        verse_nums: List[int], notes: List[str], anchor_sig: str,
    ) -> Dict[int, str]:
        """Verses only one edition family (Greek NT: one text stream) prints.

        * Alignment leftovers — the same words are printed under another number by another member of
          the same family or by the other witnesses, while this witness has no such verse there
          (Swete Clean's stale Sirach/Psalm-title verses): removed from the collation and logged.
          A verse of the versification anchor is never removed (it defines the numbering); the
          overlap is only logged.
        * Greek NT single-stream verses (Acts 19:41, Rom 14:24–26 in RP/TR): kept, but returned with a
          note so the brain prints them in ⟦ ⟧ with low presence confidence."""
        out: Dict[int, str] = {}
        for v in verse_nums:
            having = [s for s, m in mapped_by_sig.items() if m.get(v)]
            if not having:
                continue
            fams = {families.get(s, s) for s in having}
            streams = {stream_of(s) for s in having}
            nt = lang == "greek" and book.testament == "NT"
            if nt:
                if len(streams) != 1:
                    continue
            elif len(fams) != 1 and anchor_sig in having:
                continue
            others = [s for s in mapped_by_sig if s not in having]
            if not others:
                continue
            search_others = [anchor_sig] if (not nt and len(fams) > 1 and anchor_sig in others) else others
            text = _strip_doubtful(mapped_by_sig[having[0]][v])
            keys = _keyset(text, lang)
            fam_members = [s for s in mapped_by_sig if families.get(s) in fams and s not in having]
            anchor_last = max((u for u, t in mapped_by_sig.get(anchor_sig, {}).items() if t), default=0)
            stale_copy = (
                # Only Swete Clean, a stale converted copy of First1KGreek, leaves such phantoms; in the
                # Latin a verse the Saints column skips is still a real Clementine verse (Matt 18:11).
                bool(fam_members) and lang == "greek" and book.testament == "OT"
                and all(
                    any(mapped_by_sig[s].get(u) for u in (v - 1, v - 2))
                    # a trailing phantom (Swete Clean's misplaced psalm title after the last verse)
                    and (any(mapped_by_sig[s].get(u) for u in (v + 1, v + 2)) or v > anchor_last)
                    for s in fam_members
                )
            )
            if len(keys) < 3 and not (stale_copy and len(fam_members) >= 2):
                continue
            best: Optional[Tuple[float, int, str, str]] = None
            for o in search_others:
                for c, verses in book_texts.get(o, {}).items():
                    for u, t in verses.items():
                        if not t or (c, u) == (chapter, v):
                            continue
                        ok = _keyset(_strip_doubtful(t), lang)
                        if not ok:
                            continue
                        contained = len(keys & ok) / len(keys)
                        if contained < 0.8 and len(keys & ok) / len(ok) >= 0.8 and 2 * len(keys & ok) / (len(keys) + len(ok)) >= 0.5:
                            contained = len(keys & ok) / len(ok)  # the other verse lies inside this longer one
                        # ties go to the nearest place (Ps 78:72's stray title belongs to 78:1, not 49:1)
                        distance = abs(c - chapter) * 1000 + abs(u - v)
                        if contained >= 0.8 and (best is None or (contained, -distance) > (best[0], -best[1])):
                            best = (contained, distance, o, f"{c}:{u}")
            if best:
                best = (best[0], best[2], best[3])  # type: ignore[assignment]
            same_family_has_it = False
            if best:
                c, u = (int(x) for x in best[2].split(":"))
                own = [book_texts.get(s, {}).get(c, {}).get(u, "") for s in having]
                # The witness repeats the words at that place too (Mark 9:44/46 = 9:48): a genuine
                # repetition, not a numbering leftover.
                repeats = any(own_t and len(keys & _keyset(_strip_doubtful(own_t), lang)) / len(keys) >= 0.8 for own_t in own)
                same_family_has_it = families.get(best[1]) in fams
                if repeats:
                    best = None
            if ((best and (same_family_has_it or not nt)) or stale_copy) and anchor_sig in having:
                if best:
                    notes.append(f"{anchor_sig}: the words of verse {v} are also printed by {best[1]} at {best[2]} (numbering differs; kept at the anchor's number)")
                continue
            if (best and (same_family_has_it or not nt)) or stale_copy:
                where = f" ({best[1]} prints these words at {best[2]})" if best else (
                    f" ({', '.join(fam_members)}, the same edition, has no such verse)")
                for s in having:
                    del mapped_by_sig[s][v]
                notes.append(f"{', '.join(having)}: verse {v} left out as a versification/conversion duplicate{where}")
                continue
            if nt:
                note = f"Only one text stream ({next(iter(streams))}: {', '.join(having)}) has this verse."
                if best:
                    note += f" Its words are printed by {best[1]} at {book.title} {best[2]}: a probable versification duplicate."
                out[v] = note
            elif lang == "hebrew" and not best:
                # The Aleppo-tradition edition leaves the verse out on purpose (MAM omits WLC's Joshua
                # 21:36–37, "included in WLC from the parallel in Chronicles"): record its absence.
                for o in others:
                    om = mapped_by_sig[o]
                    if any(om.get(u) for u in (v - 1, v - 2)) and any(om.get(u) for u in (v + 1, v + 2)):
                        om[v] = VERSE_ABSENT
                        notes.append(f"{o}: has no verse here (counted as lacking {chapter}:{v}, which only {', '.join(having)} prints)")
        return out

    def collate_and_adjudicate(
        self,
        language: str,
        book_slug: str,
        chapter: int,
        preserve_human_locks: bool = True,
    ) -> Dict[str, Any]:
        """Collate all ADMITTED witnesses for (language, book, chapter), run the AI Brain, persist, and export."""
        lang = language.lower()
        col = self.build_collation(lang, book_slug, chapter)
        book: BookSpec = col["book"]
        collated_list = col["collated"]

        brain = create_brain(self.config)
        if hasattr(brain, "set_context"):  # Textual Analysis Brain: chapter context for its canons
            brain.set_context(
                book_slug=book.slug,
                testament=book.testament,
                witnesses=[w for w in self.list_witnesses(lang)
                           if w["status"] == "ADMITTED" and _in_scope(w, book) and not is_apparatus_only(w)],
                families={str(w["siglum"]): witness_family(w) for w in col["admitted"]},
            )
        adjudications = brain.adjudicate_chapter(lang, book.title, chapter, collated_list)
        for cv, adj in zip(collated_list, adjudications):
            record_apparatus_witnesses(cv, adj, lang)
            if hasattr(brain, "refresh_verse_review"):
                brain.refresh_verse_review(adj, cv, lang)

        now = utc_now()
        with get_conn() as conn:
            existing_ch = conn.execute(
                "SELECT id FROM chapters WHERE language = ? AND book_slug = ? AND chapter = ?",
                (lang, book.slug, chapter),
            ).fetchone()
            locked_by_verse: Dict[int, sqlite3.Row] = {}
            if existing_ch and preserve_human_locks:
                locked_rows = conn.execute(
                    "SELECT * FROM verses WHERE chapter_id = ? AND human_locked = 1", (existing_ch["id"],)
                ).fetchall()
                locked_by_verse = {int(r["verse"]): r for r in locked_rows}

            variant_count = sum(1 for a in adjudications if a.apparatus)
            sources = sorted({a.decision_source for a in adjudications}) or [brain.display_name]
            model_used = " + ".join(sources)
            offline_name = OfflinePhilologicalBrain.display_name
            ai_mode = brain.provider_id
            if brain.provider_id != OfflinePhilologicalBrain.provider_id and set(sources) == {offline_name}:
                ai_mode = f"{brain.provider_id} (fell back to offline)"

            if existing_ch:
                chapter_id = int(existing_ch["id"])
                conn.execute(
                    """
                    UPDATE chapters SET status = 'ADJUDICATED', ai_mode = ?, model_used = ?, verse_count = ?,
                        variant_verse_count = ?, updated_at = ? WHERE id = ?
                    """,
                    (ai_mode, model_used, len(adjudications), variant_count, now, chapter_id),
                )
            else:
                cur = conn.execute(
                    """
                    INSERT INTO chapters (
                        language, division, book_slug, book_title, chapter, status,
                        ai_mode, model_used, verse_count, variant_verse_count, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'ADJUDICATED', ?, ?, ?, ?, ?)
                    """,
                    (lang, book.division, book.slug, book.title, chapter, ai_mode, model_used, len(adjudications), variant_count, now),
                )
                chapter_id = int(cur.lastrowid)

            verse_export_rows: List[Dict[str, Any]] = []
            new_verses = set()
            for cv, adj in zip(collated_list, adjudications):
                new_verses.add(adj.verse)
                appar_present = {s: t for s, t in cv.apparatus_texts.items() if t != VERSE_ABSENT}
                common = {
                    "verse": adj.verse,
                    "witness_readings": dict(cv.witness_texts, **appar_present),
                    "absent_witnesses": cv.absent_witnesses + sorted(s for s, t in cv.apparatus_texts.items() if t == VERSE_ABSENT),
                    "witness_refs": dict(cv.witness_refs, **cv.apparatus_refs),
                    "apparatus_witnesses": sorted(cv.apparatus_texts),
                    "apparatus": [asdict(x) for x in adj.apparatus],
                    "disregarded": [asdict(x) for x in adj.disregarded],
                    "analysis": list(adj.analysis),
                    "needs_review": bool(adj.needs_review),
                }
                analysis_json = json.dumps(common["analysis"], ensure_ascii=False)
                stored_readings = {"texts": common["witness_readings"], "absent": common["absent_witnesses"],
                                   "refs": common["witness_refs"], "apparatus_witnesses": common["apparatus_witnesses"]}
                if adj.verse in locked_by_verse:
                    lr = locked_by_verse[adj.verse]
                    # A human has decided this verse: the machine's review flag no longer applies.
                    v_dict = dict(common, critical_text=lr["critical_text"], confidence=float(lr["confidence"]),
                                  decision_source=lr["decision_source"], rationale=lr["rationale"], human_locked=True,
                                  needs_review=False)
                    conn.execute(
                        "UPDATE verses SET witness_readings_json = ?, apparatus_json = ?, disregarded_json = ?, analysis_json = ?, "
                        "needs_review = 0, updated_at = ? WHERE id = ?",
                        (json.dumps(stored_readings, ensure_ascii=False), json.dumps(common["apparatus"], ensure_ascii=False),
                         json.dumps(common["disregarded"], ensure_ascii=False), analysis_json, now, lr["id"]),
                    )
                else:
                    rationale = adj.rationale
                    if adj.baseline_text and adj.baseline_text != adj.critical_text:
                        rationale += f" [Deterministic baseline text: {adj.baseline_text}]"
                    v_dict = dict(common, critical_text=adj.critical_text, confidence=adj.confidence,
                                  decision_source=adj.decision_source, rationale=rationale, human_locked=False)
                    conn.execute(
                        """
                        INSERT INTO verses (
                            chapter_id, verse, critical_text, confidence, decision_source,
                            witness_readings_json, apparatus_json, disregarded_json,
                            rationale, human_locked, updated_at, analysis_json, needs_review
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
                        ON CONFLICT(chapter_id, verse) DO UPDATE SET
                            critical_text = excluded.critical_text,
                            confidence = excluded.confidence,
                            decision_source = excluded.decision_source,
                            witness_readings_json = excluded.witness_readings_json,
                            apparatus_json = excluded.apparatus_json,
                            disregarded_json = excluded.disregarded_json,
                            rationale = excluded.rationale,
                            human_locked = 0,
                            updated_at = excluded.updated_at,
                            analysis_json = excluded.analysis_json,
                            needs_review = excluded.needs_review
                        """,
                        (chapter_id, adj.verse, adj.critical_text, adj.confidence, adj.decision_source,
                         json.dumps(stored_readings, ensure_ascii=False), json.dumps(common["apparatus"], ensure_ascii=False),
                         json.dumps(common["disregarded"], ensure_ascii=False), rationale, now, analysis_json, int(adj.needs_review)),
                    )
                verse_export_rows.append(v_dict)

            # Drop rows left over from an earlier (mis-aligned) run; human-locked verses always stay.
            stale = conn.execute("SELECT id, verse, human_locked FROM verses WHERE chapter_id = ?", (chapter_id,)).fetchall()
            for r in stale:
                if int(r["verse"]) not in new_verses and not int(r["human_locked"]):
                    conn.execute("DELETE FROM verses WHERE id = ?", (r["id"],))

        saved = self.get_saved_chapter(lang, book.slug, chapter)
        assert saved is not None
        self._export(lang, book, chapter, saved, col)
        return self.get_saved_chapter(lang, book.slug, chapter)  # type: ignore[return-value]

    def _export(self, lang: str, book: BookSpec, chapter: int, saved: Dict[str, Any], col: Optional[Dict[str, Any]] = None) -> None:
        if col is None:
            scope_w = [w for w in self.list_witnesses(lang) if _in_scope(w, book)]
            col = {
                "admitted": [w for w in scope_w if w["status"] == "ADMITTED"],
                "quarantined": [w for w in scope_w if w["status"] != "ADMITTED"],
                "anchor_siglum": "",
                "base_siglum": "",
                "versification_notes": [],
            }
        md_path, json_path, tsv_path = export_chapter_files(
            language=lang,
            book=book,
            chapter=chapter,
            admitted_witnesses=col["admitted"],
            apparatus_witnesses=col.get("apparatus_witnesses", []),
            quarantined_witnesses=col["quarantined"],
            verse_rows=saved["verses"],
            model_used=saved["model_used"],
            anchor_siglum=col.get("anchor_siglum", ""),
            base_siglum=col.get("base_siglum", ""),
            versification_notes=col.get("versification_notes", []),
        )
        with get_conn() as conn:
            conn.execute(
                "UPDATE chapters SET local_md_path = ?, local_json_path = ?, local_tsv_path = ? WHERE id = ?",
                (str(md_path), str(json_path), str(tsv_path), saved["id"]),
            )

    def get_saved_chapter(self, language: str, book_slug: str, chapter: int) -> Optional[Dict[str, Any]]:
        with get_conn() as conn:
            ch = conn.execute(
                "SELECT * FROM chapters WHERE language = ? AND book_slug = ? AND chapter = ?",
                (language.lower(), book_slug, chapter),
            ).fetchone()
            if not ch:
                return None
            v_rows = conn.execute("SELECT * FROM verses WHERE chapter_id = ? ORDER BY verse ASC", (ch["id"],)).fetchall()

        verses_out = []
        for r in v_rows:
            readings = json.loads(r["witness_readings_json"])
            if isinstance(readings, dict) and "texts" in readings and isinstance(readings["texts"], dict):
                texts, absent, refs = readings["texts"], readings.get("absent", []), readings.get("refs", {})
                appar = readings.get("apparatus_witnesses", [])
            else:  # rows written before the versification-aware engine
                texts, absent, refs, appar = readings, [], {}, []
            verses_out.append(
                {
                    "id": r["id"],
                    "verse": r["verse"],
                    "critical_text": r["critical_text"],
                    "confidence": r["confidence"],
                    "decision_source": r["decision_source"],
                    "witness_readings": texts,
                    "absent_witnesses": absent,
                    "witness_refs": refs,
                    "apparatus_witnesses": appar,
                    "apparatus": json.loads(r["apparatus_json"]),
                    "disregarded": json.loads(r["disregarded_json"]),
                    "rationale": r["rationale"],
                    "human_locked": bool(r["human_locked"]),
                    "analysis": json.loads(r["analysis_json"] or "[]") if "analysis_json" in r.keys() else [],
                    "needs_review": bool(r["needs_review"]) if "needs_review" in r.keys() else False,
                }
            )
        out = dict(ch)
        out["verses"] = verses_out
        return out

    def list_saved_chapters(self, language: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all saved chapters in the in-Studio Saints Critical Text library with lock & review counts."""
        sql = """
            SELECT c.*,
                   COALESCE(SUM(CASE WHEN v.human_locked = 1 THEN 1 ELSE 0 END), 0) AS locked_count,
                   COALESCE(SUM(CASE WHEN v.needs_review = 1 AND v.human_locked = 0 THEN 1 ELSE 0 END), 0) AS review_flag_count
            FROM chapters c
            LEFT JOIN verses v ON v.chapter_id = c.id
        """
        params: Tuple[Any, ...] = ()
        if language:
            sql += " WHERE c.language = ?"
            params = (language.lower(),)
        sql += " GROUP BY c.id ORDER BY c.language, c.chapter ASC"
        with get_conn() as conn:
            rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        rows.sort(
            key=lambda r: (
                r["language"],
                BOOKS_BY_SLUG[r["book_slug"]].order if r["book_slug"] in BOOKS_BY_SLUG else 999,
                int(r["chapter"]),
            )
        )
        return rows

    def get_edition_home_summary(self, language: str) -> Dict[str, Any]:
        """Summary metrics & saved chapter index for the Saints Critical Text Home tab."""
        lang = language.lower()
        books = get_books_for_language(lang)
        saved = self.list_saved_chapters(lang)
        return {
            "language": lang,
            "edition_title": f"Saints {lang.title()} Critical Text",
            "home_path": str(CRITICAL_OUTPUT_ROOTS[lang]),
            "total_books": len(books),
            "total_chapters_in_canon": sum(b.chapters for b in books),
            "saved_chapter_count": len(saved),
            "saved_verse_count": sum(int(r.get("verse_count", 0)) for r in saved),
            "locked_verse_count": sum(int(r.get("locked_count", 0)) for r in saved),
            "review_flag_count": sum(int(r.get("review_flag_count", 0)) for r in saved),
            "saved_chapters": saved,
        }

    def reexport_all_saved_chapters(self) -> int:
        """Re-write all saved chapters in studio.db to their in-Studio Saints-*-Critical-Text homes."""
        ensure_repository_scaffold()
        count = 0
        for row in self.list_saved_chapters():
            slug = str(row["book_slug"])
            if slug not in BOOKS_BY_SLUG:
                continue
            lang = str(row["language"])
            ch = int(row["chapter"])
            saved = self.get_saved_chapter(lang, slug, ch)
            if saved:
                self._export(lang, BOOKS_BY_SLUG[slug], ch, saved)
                count += 1
        return count

    # ------------------------------------------------------------------
    # Human editing
    # ------------------------------------------------------------------
    def override_verse(
        self,
        language: str,
        book_slug: str,
        chapter: int,
        verse: int,
        new_critical_text: str,
        rationale_note: str,
        lock: bool = True,
    ) -> Dict[str, Any]:
        lang = language.lower()
        book = BOOKS_BY_SLUG[book_slug]
        now = utc_now()
        with get_conn() as conn:
            ch = conn.execute(
                "SELECT * FROM chapters WHERE language = ? AND book_slug = ? AND chapter = ?",
                (lang, book_slug, chapter),
            ).fetchone()
            if not ch:
                raise KeyError("Chapter must be collated first.")
            cur = conn.execute(
                """
                UPDATE verses
                SET critical_text = ?, confidence = ?, decision_source = ?, rationale = ?, human_locked = ?, updated_at = ?,
                    needs_review = CASE WHEN ? THEN 0 ELSE needs_review END
                WHERE chapter_id = ? AND verse = ?
                """,
                (new_critical_text.strip(), 1.0 if lock else 0.95, "Human Scholarly Override" if lock else "Unlocked",
                 rationale_note.strip(), 1 if lock else 0, now, 1 if lock else 0, ch["id"], verse),
            )
            if cur.rowcount == 0:
                raise KeyError(f"{book.title} {chapter}:{verse} is not in the saved chapter.")

        saved = self.get_saved_chapter(lang, book_slug, chapter)
        assert saved is not None
        self._export(lang, book, chapter, saved)
        return saved

    def adopt_variant(
        self,
        language: str,
        book_slug: str,
        chapter: int,
        verse: int,
        apparatus_index: int,
        variant_index: int,
        rationale_note: str = "",
    ) -> Dict[str, Any]:
        """Replace exactly the lemma's words with a variant reading (by word position, never by
        string search) and lock the verse."""
        saved = self.get_saved_chapter(language, book_slug, chapter)
        if not saved:
            raise KeyError("Chapter must be collated first.")
        vr = next((v for v in saved["verses"] if int(v["verse"]) == int(verse)), None)
        if vr is None:
            raise KeyError(f"Verse {verse} not found.")
        app = vr["apparatus"][apparatus_index]
        variant = app["variants"][variant_index]
        start, count = int(app.get("word_index", -1)), int(app.get("word_count", 0))
        if app.get("kind") == "verse" or start < 0:
            raise ValueError("This apparatus entry cannot be adopted automatically; edit the verse text by hand.")
        lang = language.lower()
        words = split_words(vr["critical_text"], lang)
        if start + count > len(words):
            raise ValueError("The verse text no longer matches the apparatus (it was edited after collation). Edit it by hand or re-collate.")
        if count:
            actual = " ".join(strip_punct(w) for w in words[start:start + count]).strip()
            if actual != str(app["lemma"]).strip():
                raise ValueError("The verse text no longer matches the apparatus (it was edited after collation). Edit it by hand or re-collate.")
        reading_words = [] if variant["reading"] == "om." else split_words(str(variant.get("adopt_text") or variant["reading"]), lang)
        if count and reading_words:
            trailing = re.search(r"[.,;·:!?·;׃]+$", words[start + count - 1])
            if trailing and not re.search(r"[.,;·:!?·;׃]$", reading_words[-1]):
                reading_words[-1] += trailing.group(0)
        new_words = words[:start] + reading_words + words[start + count:]
        note = rationale_note or (
            f"[Human editorial adoption: '{variant['reading']}' ({', '.join(variant['witnesses'])}) "
            f"over '{app['lemma']}' ({', '.join(app.get('lemma_witnesses', []))})] {vr['rationale']}"
        )
        return self.override_verse(language, book_slug, chapter, verse, join_words(new_words, lang), note, lock=True)

    def sync_saved_chapter_to_drive(self, language: str, book_slug: str, chapter: int) -> Tuple[str, str]:
        saved = self.get_saved_chapter(language, book_slug, chapter)
        if not saved or not saved.get("local_md_path"):
            raise RuntimeError("Collate and save the chapter locally before syncing to Google Drive.")
        book = BOOKS_BY_SLUG[book_slug]
        doc_id, url = sync_chapter_to_gdrive(
            language=language.lower(),
            book=book,
            chapter=chapter,
            md_path=Path(saved["local_md_path"]),
            offline_locked=self.config.offline_locked,
        )
        with get_conn() as conn:
            conn.execute(
                "UPDATE chapters SET drive_doc_id = ?, drive_url = ?, updated_at = ? WHERE id = ?",
                (doc_id, url, utc_now(), saved["id"]),
            )
        return doc_id, url

    # ------------------------------------------------------------------
    # The Saints Concordance (Trilingual Root, Morpheme & Sense Studio)
    # ------------------------------------------------------------------
    def get_concordance_stats(self) -> Dict[str, Any]:
        with get_conn() as conn:
            return get_concordance_dashboard_stats(conn)

    def search_concordance(
        self,
        query: str = "",
        lang_filter: str = "all",
        colour_filter: str = "all",
        limit: int = 250,
    ) -> List[Dict[str, Any]]:
        with get_conn() as conn:
            return search_concordance_concepts(conn, query=query, lang_filter=lang_filter, colour_filter=colour_filter, limit=limit)

    def get_concordance_concept_graph(self, concept_id: int) -> Dict[str, Any]:
        with get_conn() as conn:
            return get_concept_visual_graph(conn, int(concept_id))

    def list_concordance_catalog(
        self,
        kind: str = "roots",
        lang_filter: str = "all",
        query: str = "",
        limit: int = 300,
    ) -> List[Dict[str, Any]]:
        with get_conn() as conn:
            return list_roots_and_morphemes(conn, kind=kind, lang_filter=lang_filter, query=query, limit=limit)

    def get_verse_concordance(self, book_slug: str, chapter: int, verse: int, language: str = "greek") -> Dict[str, Any]:
        """``chapter``/``verse`` in the numbering of ``language`` as stored in the Studio."""
        with get_conn() as conn:
            return get_verse_concordance_breakdown(
                conn, book_slug=book_slug, chapter=int(chapter), verse=int(verse), language=language
            )

    def concordance_verse_in_language(
        self, language: str, book_slug: str, chapter: int, verse: int, subverse: int = 0
    ) -> List[Tuple[int, int]]:
        """Anchor chapter:verse -> the same verse in ``language``'s own Studio numbering ([] if none)."""
        from .lexica import versification

        if int(subverse) == versification.EXTRA_SITE_SUBVERSE:
            return list(versification.from_extra_site_anchor(language, book_slug, int(chapter), int(verse)))
        return list(versification.from_saints(language, book_slug, int(chapter), int(verse)))

    def seed_concordance_lexicons(
        self,
        stepbible_root: Optional[Path] = None,
        include_proper_nouns: bool = False,
    ) -> Dict[str, Any]:
        with get_conn() as conn:
            return seed_stepbible_and_latin_lexicons(conn, stepbible_root=stepbible_root, include_proper_nouns=include_proper_nouns)

    def index_concordance_chapters(
        self,
        book_slug: Optional[str] = None,
        max_chapters: int = 0,
    ) -> Dict[str, Any]:
        with get_conn() as conn:
            return index_saved_critical_texts(conn, book_slug=book_slug, max_chapters=max_chapters)

    def save_concordance_sense(
        self,
        concept_slug: str,
        eng_base_word: str,
        summary_note: str,
        sense_offset: int,
        sense_base_word: str,
        sense_role: str,
        usage_nuance: str,
        theme_colour: Optional[str] = None,
    ) -> Dict[str, int]:
        with get_conn() as conn:
            return upsert_concept_and_sense(
                conn,
                concept_slug=concept_slug,
                eng_base_word=eng_base_word,
                summary_note=summary_note,
                sense_offset=int(sense_offset),
                sense_base_word=sense_base_word,
                sense_role=sense_role,
                usage_nuance=usage_nuance,
                theme_colour=theme_colour,
            )

    def set_concordance_alignment_sense(
        self,
        align_id: int,
        new_sense_id: int,
        eng_plural: bool = False,
        lock: bool = True,
        rationale: str = "",
    ) -> None:
        with get_conn() as conn:
            update_alignment_sense_and_lock(
                conn,
                align_id=int(align_id),
                new_sense_id=int(new_sense_id),
                eng_plural=bool(eng_plural),
                lock=bool(lock),
                rationale=rationale,
            )

    def export_concordance_pack(self, out_dir: Optional[Path] = None) -> Dict[str, Any]:
        with get_conn() as conn:
            return export_saints_bible_pack(conn, out_dir=out_dir)

    # ------------------------------------------------------------------
    # English-Friendly Greek & Hebrew Latinized Transliteration
    # ------------------------------------------------------------------
    def transliterate(self, text: str, language: str) -> str:
        """Transliterate Greek, Hebrew, or Aramaic text into readable Latin letters."""
        from .translit import transliterate as _tr

        return _tr(text, language)

    def transliterate_mixed(self, text: str) -> str:
        """Transliterate any Greek/Hebrew spans embedded inside mixed apparatus or formula text."""
        from .translit import transliterate_mixed as _tr_mixed

        return _tr_mixed(text)
