"""Textual Analysis Brain — internal-evidence analysis on top of the deterministic adjudicator.

Written by Claude for the Studio. It keeps everything the Offline Philological Brain does
(weighted vote by edition family, orthographic normalisation, verse-level omissions) and adds the
reasoning a textual critic applies to each variation unit:

* **Transcriptional probability** — omissions explicable by eye-skip (homoeoteleuton,
  homoeoarcton, haplography) lose the shorter-reading bonus; additions that merely repeat adjacent
  words are dittography.
* **Harmonisation** — a reading that reproduces wording found in another passage of the corpus
  (Synoptic parallels, OT quotations, Ephesians/Colossians, repeated formulae) is flagged; the
  reading that differs from the parallel is the harder one.
* **Variant typing** — every unit is labelled (omission/addition, transposition, substitution,
  inflection, proper-name spelling, conflation, expansion of a sacred name or liturgical ending).
* **Independent evidence** — each unit records which text streams support each reading (early
  manuscripts, modern critical editions, Byzantine/ecclesiastical, LXX editions, Masoretic codices,
  Vulgate witnesses) so a decision made only by counting dependent editions is visible.
* **Review flags** — a verse is marked "needs review" when the decision is close and internal
  evidence points the other way, when a whole verse is bracketed, or when the optional Claude
  review disagrees.
* **Optional Claude review** (``claude_review.py``) — advisory only; chooses among attested
  readings by number and never rewrites text.

Every finding is written into the apparatus (``ApparatusItem.analysis``) with the canon it
applies, which reading it favours and how strongly, so nothing is decided invisibly.
"""

from __future__ import annotations
import re
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from ..catalog import BOOKS, STREAM_OF_SIGLUM, get_books_for_language, stream_of  # noqa: F401
from ..collator import CollatedVerse, VariationSlot, canonical_compare_key, strip_punct, tokenize_for_alignment
from .base import ApparatusItem, BrainConfig, CriticalBrainProvider, GatekeeperVerdict, VerseAdjudication
from .offline_philological import (
    LECTIO_BREVIOR_BONUS,
    LECTIO_BREVIOR_MIN_WEIGHT,
    OfflinePhilologicalBrain,
    _family_count,
    _family_weighted_sum,
    _is_transposition_pair,
    _itacism_key,
    _transposition_components,
)

# ---------------------------------------------------------------------------
# Text streams (for "independent evidence"). Keys are witness sigla prefixes.
# ---------------------------------------------------------------------------
# (one stream map for the whole Studio: see catalog.STREAM_OF_SIGLUM)

# Sacred names/titles and liturgical words scribes tended to add (canonical keys, Greek).
GREEK_EXPANSION_WORDS = {
    "ιησουσ", "ιησου", "ιησουν", "χριστοσ", "χριστου", "χριστω", "χριστον", "κυριοσ", "κυριου", "κυριω",
    "κυριον", "θεοσ", "θεου", "θεω", "θεον", "ημων", "υμων", "ο", "του", "τω", "τον", "η", "τησ", "αμην",
    "πατροσ", "πατηρ", "υιου", "υιοσ", "αγιου", "αγιον", "πνευματοσ", "δαυιδ",
}
LATIN_EXPANSION_WORDS = {"iesus", "iesu", "christus", "christi", "christo", "dominus", "domini", "domino", "deus",
                         "dei", "deo", "noster", "nostri", "amen"}

TWO_STREAM_POLICY = {
    "greek_ot": ("Policy decision, not independent evidence: Swete (a diplomatic print of Codex Vaticanus) against the "
                 "Sixtine/Brenton text, itself printed from Vaticanus. Close to a coin flip; the heavier edition is followed."),
    "latin": ("Policy decision: one early Vulgate manuscript (Amiatinus) against the Clementine edition, with no third "
              "Hieronymian witness. Amiatinus, the oldest complete Vulgate, is followed; check against a critical Vulgate."),
    "hebrew": ("Aleppo tradition (MAM) against the Leningrad Codex (WLC): a codex-level difference within the Masoretic "
               "text. MAM is followed."),
}

# Closing benedictions, doxologies and fulfilment formulae recur verbatim in many passages: never
# evidence of assimilation, and never the "source" of a whole verse.
_FORMULA_GRAMS = {
    ("η", "χαρισ", "του"), ("χαρισ", "του", "κυριου"), ("χαρισ", "υμιν", "και"), ("χαρισ", "μεθ", "υμων"),
    ("ειρηνη", "απο", "θεου"), ("δοξα", "εισ", "τουσ"), ("εισ", "τουσ", "αιωνασ"), ("των", "αιωνων", "αμην"),
    ("τουσ", "αιωνασ", "των"), ("μετα", "παντων", "υμων"),
    # fulfilment formulae: ἐπληρώθη ἡ γραφὴ ἡ λέγουσα, ἵνα (ἡ γραφὴ) πληρωθῇ, τὸ ῥηθὲν διὰ τοῦ προφήτου λέγοντος
    ("επληρωθη", "η", "γραφη"), ("η", "γραφη", "η"), ("γραφη", "η", "λεγουσα"), ("ινα", "η", "γραφη"),
    ("η", "γραφη", "πληρωθη"), ("ινα", "πληρωθη", "το"), ("ινα", "πληρωθη", "η"), ("πληρωθη", "το", "ρηθεν"),
    ("επληρωθη", "το", "ρηθεν"), ("τοτε", "επληρωθη", "το"), ("το", "ρηθεν", "δια"), ("το", "ρηθεν", "υπο"),
    ("ρηθεν", "δια", "του"), ("δια", "του", "προφητου"), ("του", "προφητου", "λεγοντοσ"),
}

# Greek function words. A skip between two of them is a mere possibility (never "moderate"
# evidence), and two different function words are never "the same stem" unless they belong to one
# paradigm (αὐτοῦ/αὐτῷ, μου/ἐμοῦ), e.g. τούτου/τοῦ, πρό/πρός, διότι/διό are different words.
_GREEK_PARADIGMS = [
    {"ο", "η", "το", "του", "τησ", "τω", "τη", "τον", "την", "οι", "αι", "τα", "των", "τοισ", "ταισ", "τουσ", "τασ"},
    {"αυτοσ", "αυτη", "αυτο", "αυτου", "αυτησ", "αυτω", "αυτον", "αυτην", "αυτοι", "αυται", "αυτα", "αυτων",
     "αυτοισ", "αυταισ", "αυτουσ", "αυτασ"},
    {"εαυτου", "εαυτησ", "εαυτω", "εαυτη", "εαυτον", "εαυτην", "εαυτο", "εαυτα", "εαυτων", "εαυτοισ", "εαυταισ",
     "εαυτουσ", "εαυτασ"},
    {"ουτοσ", "αυτη", "τουτο", "τουτου", "ταυτησ", "τουτω", "ταυτη", "τουτον", "ταυτην", "ουτοι", "αυται", "ταυτα",
     "τουτων", "τουτοισ", "ταυταισ", "τουτουσ", "ταυτασ"},
    {"εκεινοσ", "εκεινη", "εκεινο", "εκεινου", "εκεινησ", "εκεινω", "εκεινον", "εκεινην", "εκεινοι", "εκειναι",
     "εκεινα", "εκεινων", "εκεινοισ", "εκειναισ", "εκεινουσ", "εκεινασ"},
    {"εγω", "μου", "εμου", "μοι", "εμοι", "με", "εμε"},
    {"ημεισ", "ημων", "ημιν", "ημασ"},
    {"συ", "σου", "σοι", "σε"},
    {"υμεισ", "υμων", "υμιν", "υμασ"},
]
_GREEK_PARTICLES = {
    "και", "δε", "τε", "γαρ", "ουν", "αλλα", "αλλ", "μη", "ου", "ουκ", "ουχ", "ουδε", "μηδε", "ουτε", "μητε", "αν", "εαν",
    "ει", "οτι", "ινα", "ιν", "ωσ", "ωστε", "διο", "διοτι", "οτε", "οταν", "επει", "μεν", "γε", "δη", "αρα",
}
_GREEK_PREPOSITIONS = {
    "εν", "εισ", "εσ", "εκ", "εξ", "απο", "απ", "αφ", "προσ", "προ", "επι", "επ", "εφ", "μετα", "μετ", "μεθ", "κατα",
    "κατ", "καθ", "δια", "δι", "υπο", "υπ", "υφ", "υπερ", "περι", "παρα", "παρ", "συν", "αντι", "αντ", "ανθ", "ανα",
    "αχρι", "μεχρι", "εωσ", "χωρισ",
}
_GREEK_FUNCTION_WORDS = set().union(*_GREEK_PARADIGMS) | _GREEK_PARTICLES | _GREEK_PREPOSITIONS
# Spellings of one function word (movable consonants, elision before an aspirate).
_MOVABLE_PAIRS = ({"ου", "ουκ", "ουχ"}, {"εκ", "εξ"}, {"ουτω", "ουτωσ"}, {"αχρι", "αχρισ"}, {"μεχρι", "μεχρισ"},
                  {"απο", "απ", "αφ"}, {"επι", "επ", "εφ"}, {"κατα", "κατ", "καθ"}, {"μετα", "μετ", "μεθ"},
                  {"υπο", "υπ", "υφ"}, {"αντι", "αντ", "ανθ"}, {"παρα", "παρ"}, {"δια", "δι"}, {"αλλα", "αλλ"},
                  {"ινα", "ιν"})

# Words that make a clause a doxology (ἀμήν after one is often original). "εἰς τοὺς αἰῶνας" alone
# is not enough after the epithet "the one living for ever" (τῷ ζῶντι εἰς τοὺς αἰῶνας).
_DOXOLOGY_PRAISE = {"δοξα", "δοξαν", "κρατοσ", "τιμη", "τιμην", "ευλογια", "ευλογιαν", "ευλογητοσ", "μεγαλωσυνη",
                    "ισχυσ", "ευχαριστια", "gloria", "gloriam", "honor", "benedictus", "benedictio", "imperium"}
_DOXOLOGY_AEON = {"αιωνασ", "αιωνων", "αιωνα", "αιωνοσ", "saecula", "saeculorum", "saeculi", "saeculum"}
_SENTENCE_END = re.compile("[.;;··!?][”’\"'»)\\]]*$")


def _is_formula(window: List[str]) -> bool:
    if "αμην" in window:
        return True
    return any(tuple(window[i:i + 3]) in _FORMULA_GRAMS for i in range(len(window) - 2))


def _greek_convention_pair(a: str, b: str) -> bool:
    """Readings that differ only by an editorial spelling convention (word by word)."""
    wa, wb = a.split(), b.split()
    if len(wa) != len(wb):
        return False
    from ..collator import _greek_assimilate
    pairs = [(x, y) for x, y in zip(wa, wb) if x != y]
    if not pairs:
        return False
    for x, y in pairs:
        xy = {x, y}
        if xy <= {"ενεκα", "ενεκεν", "εινεκεν"} or xy == {"εαν", "αν"} or xy in ({"μοι", "εμοι"}, {"μου", "εμου"}, {"με", "εμε"}):
            continue
        if x[:-3] == y[:-3] and len(x) > 4 and {x[-3:], y[-3:]} == {"ατε", "ετε"}:
            continue
        if x[:-2] == y[:-2] and len(x) > 4 and {x[-2:], y[-2:]} == {"αν", "ον"}:
            continue
        if (x == "ε" + y and y.startswith("αυτ")) or (y == "ε" + x and x.startswith("αυτ")):
            continue
        if re.sub(r"([ωηα])ι$", r"\1", x) == re.sub(r"([ωηα])ι$", r"\1", y):
            continue
        if _greek_assimilate(x) == _greek_assimilate(y):
            continue
        return False
    return True


NGRAM_N = 3
MIN_AFFIX = 3           # letters that must match for homoeoteleuton/-arcton
HARMONISATION_WINDOW = 1  # context words on each side used to recognise a parallel
HARMONISATION_MIN_WINDOW = 4  # reading + context must span at least this many words


def _stream(siglum: str) -> str:
    return stream_of(siglum)


def _streams(sigla: Iterable[str]) -> List[str]:
    return sorted({_stream(s) for s in sigla})


def _keys(text: str, language: str) -> List[str]:
    return [k for k in (canonical_compare_key(t, language) for t in tokenize_for_alignment(text, language)) if k]


def _common_suffix(a: str, b: str) -> int:
    n = 0
    while n < min(len(a), len(b)) and a[-1 - n] == b[-1 - n]:
        n += 1
    return n


def _common_prefix(a: str, b: str) -> int:
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    return n


def _finding(canon: str, note: str, favours: str, reading: str = "", strength: str = "moderate", key: str = "",
             delta: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """favours: "reading" (supports ``reading``), "against" (counts against it) or "neither".
    ``delta``: the weight change this finding made ({canonical key: change}), if any."""
    out = {"canon": canon, "note": note, "favours": favours, "reading": reading, "key": key, "strength": strength}
    if delta:
        out["delta"] = dict(delta)
    return out


def _lemma_keys(a: ApparatusItem, language: str) -> List[str]:
    """Canonical keys of a unit's adopted reading: the brain's own key when it stored one (the display
    lemma may show a contraction such as ισ̅ or punctuation), else re-derived from the display text."""
    if a.lemma_key:
        return [] if a.lemma_key == "om." else a.lemma_key.split()
    return [] if a.lemma == "om." else _keys(a.lemma, language)


def _is_function_word(key: str) -> bool:
    return key in _GREEK_FUNCTION_WORDS


def _itacism_equal(a: str, b: str) -> bool:
    """Same words once the itacistic confusions are merged (γεινεται = γίνεται). Two different
    function words are never merged: ἡμῶν/ὑμῶν, τῷ/τό are real variants even if itacism caused them."""
    wa, wb = a.split(), b.split()
    if len(wa) != len(wb):
        return False
    return all(x == y or (_itacism_key(x) == _itacism_key(y) and not (_is_function_word(x) and _is_function_word(y)))
               for x, y in zip(wa, wb))


# ---------------------------------------------------------------------------
# Parallel-passage index (for harmonisation)
# ---------------------------------------------------------------------------
class ParallelIndex:
    """Word trigrams → verse references, to recognise wording shared with another passage.

    Built lazily, once per process and testament, from one representative witness (for the NT the
    heaviest modern critical edition only; elsewhere one per text stream) so it stays small. A trigram
    seen in more than ``CAP`` verses is marked common (-1) and never counts as a parallel."""

    CAP = 8

    def __init__(self) -> None:
        self.grams: Dict[int, Any] = {}
        self.built_for: Set[Tuple[str, str]] = set()
        self.refs: List[Tuple[str, int, int]] = []
        self.ref_ids: Dict[Tuple[str, int, int], int] = {}

    def _ref_id(self, ref: Tuple[str, int, int]) -> int:
        rid = self.ref_ids.get(ref)
        if rid is None:
            rid = self.ref_ids[ref] = len(self.refs)
            self.refs.append(ref)
        return rid

    def ensure(self, language: str, testament: str, witnesses: List[Dict[str, Any]], families: Dict[str, str]) -> None:
        if (language, testament) in self.built_for:
            return
        from ..parsers import load_book_from_witness

        chosen: Dict[str, Dict[str, Any]] = {}
        for w in sorted(witnesses, key=lambda r: -float(r.get("weight", 0) or 0)):
            stream = _stream(str(w["siglum"]))
            if stream == "early manuscripts":
                continue  # unaccented, contracted, lacunose: poor material for phrase matching
            chosen.setdefault(stream, w)
        # Greek NT: the critical edition only. A Byzantine harmonising addition indexed as the wording
        # of its passage would make the genuine reading of the source passage look like the copy.
        reps = [chosen["modern critical editions"]] if "modern critical editions" in chosen else list(chosen.values())[:2]
        books = [b for b in get_books_for_language(language) if b.testament == testament]
        for w in reps:
            for book in books:
                for ch, verses in load_book_from_witness(w, book).items():
                    for v, text in verses.items():
                        rid = self._ref_id((book.slug, ch, v))
                        ks = _keys(text, language)
                        for i in range(len(ks) - NGRAM_N + 1):
                            h = hash(tuple(ks[i:i + NGRAM_N]))
                            cur = self.grams.get(h)
                            if cur is None:
                                self.grams[h] = rid
                            elif cur == -1:
                                continue
                            elif isinstance(cur, int):
                                if cur != rid:
                                    self.grams[h] = [cur, rid]
                            elif rid not in cur:
                                if len(cur) >= self.CAP:
                                    self.grams[h] = -1
                                else:
                                    cur.append(rid)
        self.built_for.add((language, testament))

    def _lookup(self, gram: Tuple[str, ...]) -> Optional[Set[int]]:
        cur = self.grams.get(hash(gram))
        if cur is None:
            return set()
        if cur == -1:
            return None  # common wording: no evidence either way
        return {cur} if isinstance(cur, int) else set(cur)

    def other_refs(self, keys: List[str], here: Tuple[str, int, int]) -> Set[Tuple[str, int, int]]:
        """Verses other than ``here`` in which every trigram of ``keys`` occurs."""
        if len(keys) < NGRAM_N:
            return set()
        common: Optional[Set[int]] = None
        informative = False
        for i in range(len(keys) - NGRAM_N + 1):
            ids = self._lookup(tuple(keys[i:i + NGRAM_N]))
            if ids is None:
                continue
            informative = True
            common = set(ids) if common is None else common & ids
            if not common:
                return set()
        if not informative or not common:
            return set()
        here_id = self.ref_ids.get(here)
        return {self.refs[r] for r in common if r != here_id}


_PARALLELS = ParallelIndex()


# ---------------------------------------------------------------------------
# The brain
# ---------------------------------------------------------------------------
class TextualAnalysisBrain(OfflinePhilologicalBrain):
    provider_id = "textual_analysis"
    display_name = "Textual Analysis Brain (Claude-designed · internal evidence · offline)"
    requires_internet = False

    def __init__(self, config: Optional[BrainConfig] = None) -> None:
        self.config = config or BrainConfig()
        self.context: Dict[str, Any] = {}

    # The engine passes the chapter context (book, witnesses) before adjudicating.
    def set_context(self, **context: Any) -> None:
        self.context = dict(context)

    def evaluate_witness(self, language, title, declared_license, sample_text, file_meta, existing_samples) -> GatekeeperVerdict:
        verdict = super().evaluate_witness(language, title, declared_license, sample_text, file_meta, existing_samples)
        verdict.model_used = self.display_name
        return verdict

    # ------------------------------------------------------------------
    # Stage B with internal evidence
    # ------------------------------------------------------------------
    def adjudicate_chapter(self, language: str, book_title: str, chapter: int, collated_verses: List[CollatedVerse]) -> List[VerseAdjudication]:
        self._language = language
        self._chapter = chapter
        self._book_slug = str(self.context.get("book_slug", ""))
        self._testament = str(self.context.get("testament", ""))
        self._prepare_parallels(language)
        results = []
        for cv in collated_verses:
            self._verse = cv.verse
            results.append(self._adjudicate_single_verse(language, cv))
        for adj, cv in zip(results, collated_verses):
            self._type_units(adj, cv, language)
        try:
            self.whole_verse_parallels(results, collated_verses, language)
        except Exception:  # annotation only: never block collation
            pass
        for adj, cv in zip(results, collated_verses):
            self._verse_level_review(adj, cv, language)
        self._maybe_claude_review(language, book_title, chapter, results, collated_verses)
        return results

    def _prepare_parallels(self, language: str) -> None:
        witnesses = self.context.get("witnesses") or []
        families = self.context.get("families") or {}
        if witnesses and self._testament:
            try:
                _PARALLELS.ensure(language, self._testament, witnesses, families)
            except Exception:  # an index failure must never block collation
                pass

    # -- hook called by the deterministic brain for every substantive unit --
    def _internal_evidence(self, language, cv, slot, idx, scored, preceding):
        deltas: Dict[str, float] = {}
        findings: List[Dict[str, Any]] = []
        groups = {k: (w, sigla, rep) for (w, k, sigla, rep) in scored}
        before = [canonical_compare_key(t, language) for t in " ".join(preceding).split()][-4:]
        before = [k for k in before if k]
        after = self._following_keys(cv, idx, language, 4)
        greek_nt = language == "greek" and self._testament == "NT"

        harmonised = self._harmonisation(cv, groups, before, after, language)
        harmonised_keys = {f["key"] for f in harmonised}
        if "om." in groups and len(groups) == 2:
            longer_key = next(k for k in groups if k != "om.")
            longer_words = longer_key.split()
            longer_sigla = groups[longer_key][1]
            omit_sigla = groups["om."][1]
            if self._moved_elsewhere(cv, idx, longer_words, longer_sigla, omit_sigla, language):
                # The "omitting" witnesses have these very words at another place in the verse: half
                # of a word-order transposition, so neither an eye-skip nor an expansion (no delta).
                findings.extend(harmonised)
                return deltas, findings
            got_bonus = language in ("greek", "latin") and any(cv.witness_weights.get(s, 0) >= LECTIO_BREVIOR_MIN_WEIGHT for s in omit_sigla)
            # Dittography is tested first (every repeated block also looks like an eye-skip), but only
            # for a doubling in one edition family against at least two (every other family where
            # only two exist): a doubling kept by the majority (ἀμὴν ἀμήν) makes the omission the slip.
            n_fams = _family_count(list(longer_sigla) + list(omit_sigla), cv.witness_families)
            all_before = [k for k in (canonical_compare_key(t, language) for t in " ".join(preceding).split()) if k]
            ditto = (
                _family_count(longer_sigla, cv.witness_families) == 1
                and _family_count(omit_sigla, cv.witness_families) >= min(2, n_fams - 1)
                and self._is_dittography(longer_words, all_before,
                                         self._following_keys(cv, idx, language, max(4, len(longer_words)), majority=True),
                                         itacism=language == "greek")
            )
            # Eye-skip is tested in the Greek NT only (measured there); if the longer reading is
            # explained as a harmonisation, an accidental eye-skip is not needed to explain the shorter.
            skip = None if (ditto or longer_key in harmonised_keys or not greek_nt) else self._eye_skip(longer_words, before, after)
            if ditto:
                findings.append(_finding(
                    "transcriptional: dittography",
                    f"The addition '{groups[longer_key][2]}' (only in {', '.join(longer_sigla)}) repeats the adjacent "
                    "words; probably a copying slip.",
                    "against", reading=groups[longer_key][2], strength="moderate", key=longer_key,
                ))
            elif skip:
                # Between two long matching words an eye-skip is evidence; between two instances of
                # καί / τό / τούς / αὐτοῦ (any function word) it is a mere possibility (annotation only).
                function_skip = language == "greek" and any(_is_function_word(w) for w in skip[3])
                strength = "moderate" if skip[2] >= 4 and not function_skip else "weak"
                both_early = {"B (03)", "א (01)"} <= set(omit_sigla)
                withhold = got_bonus and strength == "moderate" and not both_early
                if withhold:
                    tail = "; the shorter reading gets no lectio-brevior credit."
                elif strength == "moderate" and both_early and got_bonus:
                    tail = "; B and א both omit, so the shorter reading keeps its credit."
                elif strength == "moderate":
                    tail = ("; an accidental omission is the likelier explanation (the shorter reading had no "
                            "lectio-brevior credit to withhold, so the vote is unchanged).")
                elif function_skip:
                    tail = " (between such common short words a possibility only; the vote is unchanged)."
                else:
                    tail = " (a possibility only; the vote is unchanged)."
                findings.append(_finding(
                    "transcriptional: " + skip[0],
                    f"The omission in {', '.join(omit_sigla)} is explicable by {skip[1]}" + tail,
                    "reading" if strength == "moderate" else "neither",
                    reading=groups[longer_key][2], strength=strength, key=longer_key,
                    delta={"om.": -LECTIO_BREVIOR_BONUS} if withhold else None,
                ))
                if withhold:
                    deltas["om."] = -LECTIO_BREVIOR_BONUS
            clause, ends_sentence = self._clause_before(preceding, language)
            expansion = self._expansion_kind(longer_words, language, after, clause, ends_sentence)
            if expansion:
                text = groups[longer_key][2]
                pious = (
                    expansion.startswith("expansion")
                    and not ({"B (03)", "א (01)"} & set(longer_sigla))
                    and _family_count(omit_sigla, cv.witness_families) >= 2
                )
                if expansion.startswith("expansion") and not pious:
                    # Say who actually supports the name (in the Greek OT and the Vulgate only one
                    # edition against one is possible, so the "pious expansion" branch cannot fire).
                    early = [s for s in ("B (03)", "א (01)") if s in longer_sigla]
                    if early:
                        support = f"{' and '.join(early)} support{'s' if len(early) == 1 else ''} it"
                    else:
                        n_long = _family_count(longer_sigla, cv.witness_families)
                        n_omit = _family_count(omit_sigla, cv.witness_families)
                        support = (f"it is read by {', '.join(longer_sigla)} and lacking in {', '.join(omit_sigla)} "
                                   f"({_count_word(n_long)} witness famil{'y' if n_long == 1 else 'ies'} against "
                                   f"{_count_word(n_omit)})")
                    findings.append(_finding(
                        "variant type: sacred name or title",
                        f"'{text}' adds a sacred name or title; {support}, so the usual scribal tendency to expand "
                        "such names gives no direction here.",
                        "neither", reading=text, strength="info", key=longer_key,
                    ))
                elif expansion.startswith("liturgical") and "after a doxology" in expansion:
                    findings.append(_finding(
                        "variant type: liturgical ending",
                        f"'{text}' closes a doxology, where it is often original; no direction.",
                        "neither", reading=text, strength="info", key=longer_key,
                    ))
                else:
                    findings.append(_finding(
                        "scribal tendency: " + expansion,
                        f"'{text}' is a typical scribal {expansion}; such additions are more likely than omissions.",
                        "against", reading=text, strength="weak", key=longer_key,
                    ))

        findings.extend(harmonised)
        # (The "external: independent streams" note is written in _type_units, once the adopted
        # reading is final: deltas, word conservation and OCR swaps are applied after this hook.)
        return deltas, findings

    @staticmethod
    def _moved_elsewhere(cv: CollatedVerse, idx: int, words: List[str], longer_sigla: List[str],
                         omit_sigla: List[str], language: str) -> bool:
        """Do the witnesses that lack ``words`` here (most of their weight) read exactly these words in
        another unit of the verse, where the witnesses that have them here read nothing? (1 John
        2:28: א's ἀπʼ αὐτοῦ.) A name only one omitter moves (John 18:5) is still an addition."""
        if not words:
            return False
        longer, omit = set(longer_sigla), set(omit_sigla)
        have: Set[str] = set()
        for j, other in enumerate(cv.slots):
            if j == idx or not (longer & set(other.raw_forms.get("om.", []))):
                continue
            for form, sigs in other.raw_forms.items():
                if form == "om." or not (omit & set(sigs)):
                    continue
                key = other.form_keys.get(form) or " ".join(_keys(form, language))
                if key.split() == words:
                    have |= omit & set(sigs)
        if not have:
            return False
        w_have = _family_weighted_sum(sorted(have), cv.witness_weights, cv.witness_families)
        return w_have > 0.5 * _family_weighted_sum(list(omit_sigla), cv.witness_weights, cv.witness_families)

    @staticmethod
    def _clause_before(preceding: List[str], language: str) -> Tuple[List[str], bool]:
        """Keys of the clause before this point (back to the previous sentence end) and whether the
        text so far ends a sentence (a trailing comma means the sentence runs on)."""
        toks = " ".join(preceding).split()
        ends_sentence = not toks or not toks[-1].rstrip("”’\"'»)]").endswith(",")
        clause: List[str] = []
        for i, tok in enumerate(reversed(toks)):
            if i and _SENTENCE_END.search(tok):
                break
            k = canonical_compare_key(tok, language)
            if k:
                clause.append(k)
            if len(clause) >= 25:
                break
        clause.reverse()
        return clause, ends_sentence

    # ------------------------------------------------------------------
    # Individual canons
    # ------------------------------------------------------------------
    def _following_keys(self, cv: CollatedVerse, idx: int, language: str, n: int, majority: bool = False) -> List[str]:
        """Keys of the words after unit ``idx`` (the heaviest written form of each later slot; with
        ``majority``, a slot whose heaviest reading is an omission contributes nothing)."""
        out: List[str] = []
        for slot in cv.slots[idx + 1:]:
            best = max(
                ((f, sum(cv.witness_weights.get(s, 0.5) for s in sigs)) for f, sigs in slot.raw_forms.items()
                 if majority or f != "om."),
                key=lambda p: p[1], default=None,
            )
            if best and best[0] != "om.":
                out.extend(k for k in (slot.form_keys.get(best[0]) or canonical_compare_key(best[0], language)).split() if k)
            if len(out) >= n:
                break
        return out[:n]

    @staticmethod
    def _eye_skip(omitted: List[str], before: List[str], after: List[str]) -> Optional[Tuple[str, str, int, Tuple[str, str]]]:
        """Does the omitted text begin/end like its neighbours, so a copyist's eye could jump it?
        Returns (kind, description, matching letters, the two words the eye could confuse)."""
        if not omitted:
            return None
        last, first = omitted[-1], omitted[0]
        if before:
            prev = before[-1]
            if prev == last:
                return ("haplography" if len(omitted) == 1 else "homoeoteleuton",
                        f"eye-skip between the two occurrences of '{prev}'", len(prev), (prev, last))
            if len(omitted) >= 2 and _common_suffix(prev, last) >= MIN_AFFIX:
                n = _common_suffix(prev, last)
                return ("homoeoteleuton", f"homoeoteleuton (…{last[-n:]} / …{prev[-n:]})", n, (prev, last))
        if after:
            nxt = after[0]
            if nxt == first:
                return ("haplography" if len(omitted) == 1 else "homoeoarcton",
                        f"eye-skip between the two occurrences of '{nxt}'", len(nxt), (nxt, first))
            if len(omitted) >= 2 and _common_prefix(nxt, first) >= MIN_AFFIX:
                n = _common_prefix(nxt, first)
                return ("homoeoarcton", f"homoeoarcton ({first[:n]}… / {nxt[:n]}…)", n, (nxt, first))
        return None

    @staticmethod
    def _is_dittography(added: List[str], before: List[str], after: List[str], itacism: bool = False) -> bool:
        """Does the addition repeat the words right before or after it? (``itacism``: compare Greek
        with the itacistic spellings merged — a scribe who repeats a line spells it as he likes.)"""
        n = len(added)
        if not n:
            return False
        norm = (lambda ws: [_itacism_key(w) for w in ws]) if itacism else (lambda ws: list(ws))
        return norm(before[-n:]) == norm(added) or norm(after[:n]) == norm(added)

    @staticmethod
    def _expansion_kind(added: List[str], language: str, after: List[str], clause: Optional[List[str]] = None,
                        ends_sentence: bool = True) -> str:
        """``clause``: keys of the clause before the addition; ``ends_sentence``: whether the text
        before it closes a sentence (an ἀμήν inside a running sentence is no liturgical ending)."""
        if not added:
            return ""
        vocab = GREEK_EXPANSION_WORDS if language == "greek" else LATIN_EXPANSION_WORDS if language == "latin" else set()
        if not vocab:
            return ""
        if added == ["αμην"] or added == ["amen"]:
            if after or not ends_sentence:
                return ""
            if _is_doxology(clause or []):
                return "liturgical ending (ἀμήν) after a doxology"
            return "liturgical ending (ἀμήν)"
        sacred = {"ιησουσ", "ιησου", "ιησουν", "χριστοσ", "χριστου", "χριστω", "χριστον", "κυριοσ", "κυριου", "κυριω",
                  "κυριον", "iesus", "iesu", "christus", "christi", "christo", "dominus", "domini", "domino"}
        if all(w in vocab for w in added) and any(w in sacred for w in added):
            return "expansion of a sacred name or title"
        return ""

    def _witness_window(self, cv: CollatedVerse, sigla: List[str], words: List[str], before: List[str], after: List[str], language: str) -> List[str]:
        """The reading in the words of one of its own witnesses, with two words of that witness's
        context on each side (an edition rather than a manuscript where possible)."""
        ordered = sorted(sigla, key=lambda s: (_stream(s) == "early manuscripts", -cv.witness_weights.get(s, 0.5)))
        for sig in ordered:
            wk = _keys(cv.witness_texts.get(sig, ""), language)
            if not wk:
                continue
            if words:
                hits = [p for p in range(len(wk) - len(words) + 1) if wk[p:p + len(words)] == words]
                if not hits:
                    continue
                pos = next((p for p in hits if before and p > 0 and wk[p - 1] == before[-1]), hits[0])
                return wk[max(0, pos - HARMONISATION_WINDOW):pos] + words + wk[pos + len(words):pos + len(words) + HARMONISATION_WINDOW]
            if before and after:
                for p in range(len(wk) - 1):
                    if wk[p] == before[-1] and wk[p + 1] == after[0]:
                        return wk[max(0, p - HARMONISATION_WINDOW + 1):p + 1] + wk[p + 1:p + 1 + HARMONISATION_WINDOW]
        return before[-HARMONISATION_WINDOW:] + words + after[:HARMONISATION_WINDOW]

    def _harmonisation(self, cv: CollatedVerse, groups: Dict[str, Tuple[float, List[str], str]], before: List[str], after: List[str], language: str) -> List[Dict[str, Any]]:
        # Measured in the Greek NT only: in the LXX, Hebrew and Vulgate the "parallels" are mostly
        # the book's own repeated formulae.
        if language != "greek" or self._testament != "NT" or len(groups) < 2 or (language, self._testament) not in _PARALLELS.built_for:
            return []
        non_om = [k for k in groups if k != "om."]
        if len(non_om) == 2 and len(groups) == 2 and _greek_convention_pair(non_om[0], non_om[1]):
            return []  # ἕνεκα/ἕνεκεν, ἐάν/ἄν, -ατε/-ετε … are editorial conventions, not assimilation
        here = (self._book_slug, self._chapter, self._verse)
        matches: Dict[str, Set[Tuple[str, int, int]]] = {}
        for key, (_w, sigla, _rep) in groups.items():
            words = [] if key == "om." else key.split()
            window = self._witness_window(cv, sigla, words, before, after, language)
            if len(window) < HARMONISATION_MIN_WINDOW or _is_formula(window):
                continue
            refs = {
                r for r in _PARALLELS.other_refs(window, here)
                # the same sentence under a neighbouring number is a displacement, not a parallel
                if not (r[0] == here[0] and r[1] == here[1] and abs(r[2] - here[2]) <= 3)
            }
            if 0 < len(refs) <= 6:  # wording common to many passages is a formula, not a parallel
                matches[key] = refs
        if len(matches) != 1:
            return []  # none, or every reading has a parallel: no signal
        key, refs = next(iter(matches.items()))
        others = [g for k, g in groups.items() if k != key]
        if all(len(g[1]) == 1 for g in others) and len(_streams(groups[key][1])) >= 2:
            # The alternative is one manuscript's singular reading: agreement with a parallel says
            # nothing about the majority text here (e.g. Luke reproducing Mark's wording).
            return []
        reading = "om." if key == "om." else groups[key][2]
        ref_txt = ", ".join(_format_ref(r) for r in sorted(refs)[:3])
        # The wording follows the unit's shape: an addition (against "om." or a shorter reading it
        # contains, e.g. υἱόν → τὸν υἱὸν αὐτῆς τὸν πρωτότοκον) of any real word, short ones such as
        # λαῷ included, counts against the reading; articles, pronouns and connectives do not.
        added = _added_words(key, groups)
        if added and any(not _is_function_word(w) and w != "αμην" for w in added):
            return [_finding(
                "transcriptional: harmonisation",
                f"The addition '{reading}' reproduces the wording of {ref_txt}; scribes tended to assimilate to familiar "
                "parallels, so the reading without it is the harder one.",
                "against", reading=reading, strength="weak", key=key,
            )]
        if key == "om.":
            why = "for an omission the direction of change is not certain"
        elif added:
            why = "the added words are only articles, pronouns or connectives, so the direction of change is not certain"
        else:
            why = "for a substitution the direction of change is not certain"
        return [_finding(
            "transcriptional: harmonisation",
            f"The reading '{reading}' agrees with the wording of {ref_txt}. Assimilation to a parallel is possible, "
            f"but {why}.",
            "neither", reading=reading, strength="info", key=key,
        )]

    def whole_verse_parallels(self, results: List[VerseAdjudication], collated: List[CollatedVerse], language: str) -> None:
        """A verse missing from two or more witnesses that reproduces another passage (Matt 18:11 =
        Luke 19:10) gets a note naming the passage. Annotation only. Not for verses inside a block
        of three or more verses missing from the same witnesses (an interpolated passage such as
        John 7:53–8:11), nor for chapter-edge verses whose block cannot be seen from here."""
        if language != "greek" or self._testament != "NT" or (language, self._testament) not in _PARALLELS.built_for:
            return
        chapter_sigla: Set[str] = set()
        for cv in collated:
            chapter_sigla |= set(cv.witness_texts) | set(cv.absent_witnesses)
        lacking = {}
        for cv in collated:
            lack = frozenset(cv.absent_witnesses) | frozenset(cv.doubtful_witnesses)
            if cv.single_stream:
                # The engine records no absences for a verse only one stream prints: every witness
                # outside it lacks the verse (so Rom 14:24–26 in RP2018 is seen as one block).
                lack |= frozenset(chapter_sigla - set(cv.witness_texts))
            lacking[cv.verse] = lack
        verses = sorted(lacking)
        for adj, cv in zip(results, collated):
            lack = lacking[cv.verse]
            if len(lack) < 2 and not cv.single_stream:
                continue
            if cv.single_stream and "probable versification duplicate" in cv.single_stream:
                continue  # the same words printed under another number, not a verse supplied from a parallel
            if cv.verse in (verses[0], verses[-1]):
                continue
            run = [v for v in (cv.verse - 2, cv.verse - 1, cv.verse + 1, cv.verse + 2) if lacking.get(v) and lacking[v] & lack]
            if len([v for v in (cv.verse - 1, cv.verse + 1) if v in run]) >= 1 and len(run) >= 2:
                continue  # part of a block
            present = [s for s in cv.witness_texts if s not in lack]
            if not present:
                continue
            keys = _keys(cv.witness_texts[present[0]], language)
            if len(keys) < 5:
                continue
            # Fulfilment formulae, benedictions and ἀμήν are shared by many passages: they are left
            # out of the coverage, so only the verse's own content can point to a source passage.
            formula_pos = {i for i, k in enumerate(keys) if k == "αμην"}
            for i in range(len(keys) - NGRAM_N + 1):
                if tuple(keys[i:i + NGRAM_N]) in _FORMULA_GRAMS:
                    formula_pos.update(range(i, i + NGRAM_N))
            n_content = len(keys) - len(formula_pos)
            if n_content < 5:
                continue
            covered: Dict[int, Set[int]] = defaultdict(set)
            here_id = _PARALLELS.ref_ids.get((self._book_slug, self._chapter, cv.verse))
            for i in range(len(keys) - NGRAM_N + 1):
                ids = _PARALLELS._lookup(tuple(keys[i:i + NGRAM_N]))
                for rid in ids or ():
                    if rid != here_id:
                        covered[rid].update(range(i, i + NGRAM_N))
            best = None
            for rid, pos in covered.items():
                ref = _PARALLELS.refs[rid]
                if ref[0] == self._book_slug and ref[1] == self._chapter:
                    if abs(ref[2] - cv.verse) <= 1:
                        continue  # the same verse under another edition's numbering
                    if lacking.get(ref[2]) and lacking[ref[2]] & lack:
                        continue  # never cite a verse missing from the same witnesses
                content_pos = pos - formula_pos
                cov = len(content_pos) / n_content
                if cov >= 0.5 and len(content_pos) >= 5 and (best is None or cov > best[0]):
                    best = (cov, ref)
            if best:
                adj.analysis.append(_finding(
                    "transcriptional: harmonisation (whole verse)",
                    f"Verse found only in {', '.join(present)} reproduces the wording of {_format_ref(best[1])} "
                    f"(coverage {best[0]:.0%}); a verse supplied from a parallel passage is a typical later addition.",
                    "neither", strength="info",
                ))

    # ------------------------------------------------------------------
    # Unit typing and verse-level review
    # ------------------------------------------------------------------
    def _type_units(self, adj: VerseAdjudication, cv: CollatedVerse, language: str) -> None:
        words_units = [a for a in adj.apparatus if a.kind == "word"]
        for a in adj.apparatus:
            if a.kind == "verse":
                a.variant_type = "whole-verse omission/addition"
                continue
            # display-derived keys on both sides (the brain's lemma_key may carry extra normalisation,
            # e.g. συν-/συλ- assimilation, that the variants' display forms do not)
            lemma_keys = [] if a.lemma == "om." else _keys(a.lemma, language)
            var_keys = [[] if v["reading"] == "om." else _keys(v.get("adopt_text") or v["reading"], language) for v in a.variants]
            name_like = None
            if len(lemma_keys) == 1 and var_keys and all(len(v) == 1 for v in var_keys) and a.lemma[:1].isupper():
                name_like = _name_like(cv, {lemma_keys[0]} | {v[0] for v in var_keys}, language)
            a.variant_type = _classify(lemma_keys, var_keys, a.lemma, [v["reading"] for v in a.variants], language, name_like)
            if a.variant_type == "word-order transposition":
                _drop_moved_findings(a)
        # Transpositions: the collator splits "A B" vs "B A" into an addition and an omission
        # (including 1-to-k multi-fragment splits such as Luke 12:1 'τῶν Φαρισαίων').
        for comp in _transposition_components(words_units, language):
            if len(comp) < 2:
                continue
            group = [words_units[k] for k in comp]
            for u in group:
                u.variant_type = "word-order transposition"
                _drop_moved_findings(u)
            labels = ", ".join(f"'{u.lemma}'" for u in group)
            transp_sigs = sorted({s for u in group for v in u.variants for s in v["witnesses"]})
            note = f"Units {labels} together form one word-order variant ({', '.join(transp_sigs)} transpose)."
            for u in group:
                u.analysis.append(_finding("variant type: transposition", note, "neither", strength="info"))
        conflations = _conflations(words_units, language, cv)
        for a, reading, key in conflations:
            a.analysis.append(_finding(
                "transcriptional: conflation",
                f"'{reading}' combines the other readings of this unit; conflate readings are typically later.",
                "against", reading=reading, strength="moderate", key=key,
            ))
        # External evidence, from the unit's final lemma and variants (the adopted reading may have
        # changed after the internal-evidence hook ran, e.g. by word conservation).
        greek_nt = language == "greek" and getattr(self, "_testament", "") == "NT"
        for a in words_units:
            lemma_streams = _streams(a.lemma_witnesses)
            variant_streams = _streams(s for v in a.variants for s in v["witnesses"])
            a.analysis.append(_finding(
                "external: independent streams",
                f"Adopted reading: {', '.join(lemma_streams)}; other reading(s): {', '.join(variant_streams)}.",
                "neither", strength="info",
            ))
            if not greek_nt and len(lemma_streams) == 1 and len(variant_streams) == 1 and variant_streams != lemma_streams:
                policy = TWO_STREAM_POLICY.get(language if language != "greek" else "greek_ot")
                if policy:
                    a.analysis.append(_finding("external: two-stream policy", policy, "neither", strength="info"))

    def _verse_level_review(self, adj: VerseAdjudication, cv: CollatedVerse, language: str) -> None:
        reasons: List[str] = []
        voting_sigla = set(cv.witness_texts) | set(cv.absent_witnesses)
        open_app = set(getattr(cv, "open_apparatus_sigla", None) or set())
        allowed_sigla = voting_sigla | open_app
        if any(a.kind == "verse" for a in adj.apparatus) and adj.critical_text.startswith("⟦"):
            reasons.append("whole verse printed in ⟦ ⟧ against some witnesses")
        for a in adj.apparatus:
            if a.kind != "word":
                continue
            # Apparatus-only units added by record_apparatus_witnesses carry no voting variants: skip them.
            voting_lemma = [s for s in a.lemma_witnesses if s in voting_sigla] if voting_sigla else list(a.lemma_witnesses)
            voting_vars = [
                v for v in a.variants
                if not voting_sigla or any(s in voting_sigla for s in v.get("witnesses", []))
            ]
            if not voting_vars:
                continue
            # the brain's own key: the display lemma may be a contraction (ισ̅) whose letters differ
            lemma_key = a.lemma_key or ("om." if a.lemma == "om." else " ".join(_keys(a.lemma, language)))
            weighty = [f for f in a.analysis if f.get("strength") in ("moderate", "strong")]
            against = [f for f in weighty if f.get("favours") == "against" and f.get("key") == lemma_key]
            favours_variant = [f for f in weighty if f.get("favours") == "reading" and f.get("key") and f.get("key") != lemma_key]
            lemma_w = _family_weighted_sum(voting_lemma, cv.witness_weights, cv.witness_families)
            best_var = max((float(v.get("weight_sum", 0)) for v in voting_vars), default=0.0)
            close = lemma_w - best_var < 0.5
            if (against or favours_variant) and close:
                reasons.append(f"unit '{a.lemma}': close vote and internal evidence favours another reading")
            # A manuscript that has the adopted words in an itacistic spelling (γεινεται = γίνεται)
            # agrees with them: only readings that differ beyond ει/ι, αι/ε, η/ι, ω/ο count against.
            shown_key = "om." if a.lemma == "om." else " ".join(_keys(a.lemma, language))
            differing = []
            for v in voting_vars:
                vk = "om." if v["reading"] == "om." else " ".join(_keys(v.get("adopt_text") or v["reading"], language))
                if not (_itacism_equal(lemma_key, vk) or _itacism_equal(shown_key, vk)):
                    differing.append(v)
            # Open-licence (tier < 5) early manuscripts attached by record_apparatus_witnesses (e.g.
            # A/02, C/04, 𝔓47 in Revelation where B/03 is lacunose) count as early-MS corroboration
            # of the adopted lemma; non-early apparatus editions (WH1881, Tisch8, Byz) and Tier 5
            # study-only witnesses NEVER clear the flag.
            voting_lemma_streams = set(_streams(voting_lemma))
            open_early_corroboration = any(
                s in open_app and _stream(s) in ("early manuscripts", "early papyri", "early Alexandrian uncials")
                for s in a.lemma_witnesses
            )
            var_for_streams = [s for v in differing for s in v["witnesses"] if not voting_sigla or s in voting_sigla]
            var_streams = set(_streams(var_for_streams))
            if (voting_lemma_streams == {"modern critical editions"}
                    and not open_early_corroboration
                    and "early manuscripts" in var_streams):
                reasons.append(f"unit '{a.lemma}': adopted on modern editions alone against the early manuscripts")
        if reasons:
            adj.needs_review = True
            adj.analysis.append(_finding("review flag", "; ".join(reasons) + ".", "neither", strength="info"))
        adj.decision_source = self.display_name

    def refresh_verse_review(self, adj: VerseAdjudication, cv: CollatedVerse, language: str) -> None:
        """Re-evaluate verse-level review flags after record_apparatus_witnesses attaches open-licence
        (tier < 5) early manuscripts such as A (02), C (04), and 𝔓47."""
        claude_flags = [f for f in adj.analysis if f.get("canon") == "review flag" and "Claude review" in f.get("note", "")]
        adj.analysis = [f for f in adj.analysis if f.get("canon") != "review flag"]
        adj.needs_review = bool(claude_flags)
        self._verse_level_review(adj, cv, language)
        adj.analysis.extend(claude_flags)

    # ------------------------------------------------------------------
    # Optional Claude review
    # ------------------------------------------------------------------
    def _maybe_claude_review(self, language: str, book_title: str, chapter: int, results: List[VerseAdjudication], collated: List[CollatedVerse]) -> None:
        if not self.config.claude_review:
            return
        from .claude_review import ClaudeReviewUnavailable, build_unit_payload, review_chapter

        payloads = []
        for adj, cv in zip(results, collated):
            units = []
            for u_idx, a in enumerate(adj.apparatus):
                if a.kind != "word":
                    continue
                readings = [{"choice": 0, "text": a.lemma, "witnesses": a.lemma_witnesses}] + [
                    {"choice": i + 1, "text": v["reading"], "witnesses": v["witnesses"]} for i, v in enumerate(a.variants)
                ]
                units.append({
                    "unit": u_idx, "readings": readings, "variant_type": a.variant_type,
                    "analysis": [f"{f['canon']}: {f['note']}" for f in a.analysis if f.get("strength") != "info"],
                })
            if units:
                payloads.append(build_unit_payload(cv.verse, cv.witness_texts, cv.witness_weights, cv.witness_families, adj.critical_text, units))
        if not payloads:
            return
        try:
            answers = review_chapter(self.config, language, book_title, chapter, payloads, client=self.context.get("claude_client"))
        except (ClaudeReviewUnavailable, PermissionError) as exc:
            for adj in results:
                if any(a.kind == "word" for a in adj.apparatus):
                    adj.analysis.append(_finding("Claude review", f"not run: {exc}", "neither", strength="info"))
                    break
            return
        model = self.config.claude_model
        for adj in results:
            for u_idx, a in enumerate(adj.apparatus):
                ans = answers.get((adj.verse, u_idx))
                if not ans:
                    continue
                choice = int(ans["choice"])
                chosen = a.lemma if choice == 0 else a.variants[choice - 1]["reading"]
                agrees = choice == 0
                a.analysis.append(_finding(
                    "Claude review",
                    f"{model} {'agrees with' if agrees else 'prefers'} '{chosen}' ({ans['confidence']:.0%}; "
                    f"{', '.join(ans.get('canons', [])) or 'no canons named'}): {ans.get('rationale', '').strip()}",
                    "reading", reading=chosen, strength=f"{ans['confidence']:.2f}",
                    key="om." if chosen == "om." else " ".join(_keys(chosen, language)),
                ))
                if not agrees:
                    adj.needs_review = True
                    adj.analysis.append(_finding(
                        "review flag", f"Claude review prefers '{chosen}' over the adopted '{a.lemma}'.", "neither", strength="info",
                    ))


# ---------------------------------------------------------------------------
# Helpers for typing
# ---------------------------------------------------------------------------
def _format_ref(ref: Tuple[str, int, int]) -> str:
    slug, ch, v = ref
    title = next((b.title for b in BOOKS if b.slug == slug), slug)
    return f"{title.split(' (')[0]} {ch}:{v}"


def _count_word(n: int) -> str:
    return {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}.get(n, str(n))


def _is_doxology(clause: List[str]) -> bool:
    """A clause ascribing glory/blessing, or ending "for ever" — but not the epithet "the one living
    for ever" (τῷ ζῶντι εἰς τοὺς αἰῶνας, Rev 4:9, 15:7), which is no doxology."""
    if set(clause) & _DOXOLOGY_PRAISE:
        return True
    aeon = [i for i, k in enumerate(clause) if k in _DOXOLOGY_AEON]
    return bool(aeon) and not any(w.startswith(("ζων", "uiu")) for i in aeon for w in clause[max(0, i - 4):i])


def _added_words(key: str, groups: Dict[str, Tuple[float, List[str], str]]) -> Optional[List[str]]:
    """Words the reading ``key`` adds to another reading of the unit ("om." or a reading whose words it
    contains), or None when it adds nothing (an omission or a substitution)."""
    if key == "om.":
        return None
    kw = Counter(key.split())
    if "om." in groups:
        return list(kw.elements())
    for other in groups:
        if other in (key, "om."):
            continue
        ow = Counter(other.split())
        if not (ow - kw) and sum(ow.values()) < sum(kw.values()):
            return list((kw - ow).elements())
    return None


def _name_like(cv: CollatedVerse, keys: Set[str], language: str) -> Optional[bool]:
    """Is the word written as a proper name in this verse? Editions capitalise sentence and quotation
    starts (Εἰσέλθατε, Θυγάτηρ), so: False if any cased witness writes it in lower case (BHP and
    Swete lower-case such starts); True if at least two cased witnesses (one, if only one has it)
    capitalise it in mid-sentence; None (undecided) if it is only ever seen, capitalised, at a verse or
    sentence start (Ἀσάφ opening Matt 1:8). Transcriptions without case (B, א, Amiatinus) say nothing."""
    cased_having = mid_witnesses = 0
    for text in cv.witness_texts.values():
        if not any(ch.isupper() for ch in text):
            continue
        toks = tokenize_for_alignment(text, language)
        has_word = has_mid = False
        for i, tok in enumerate(toks):
            if canonical_compare_key(tok, language) not in keys:
                continue
            has_word = True
            word = tok.lstrip("“‘\"'«([⟦")
            if not word[:1].isupper():
                return False
            if word != tok or i == 0 or re.search("[.,;:;··!?—–”’\"'»)\\]]$", toks[i - 1]):
                continue  # verse, sentence, clause or quotation start
            has_mid = True
        cased_having += has_word
        mid_witnesses += has_mid
    if not cased_having:
        return None
    if mid_witnesses >= min(2, cased_having):
        return True
    return None if mid_witnesses == 0 else False


_MOVED_CANONS = ("scribal tendency", "transcriptional: homoeo", "transcriptional: haplo", "transcriptional: dittography",
                 "transcriptional: harmonisation",
                 "variant type: sacred name", "variant type: liturgical")


def _drop_moved_findings(u: ApparatusItem) -> None:
    """A moved word is neither an addition nor an omission: drop eye-skip, dittography and expansion
    findings. A weight change one of them already made stays explained (invariant 9)."""
    kept: List[Dict[str, Any]] = []
    delta: Dict[str, float] = {}
    for f in u.analysis:
        if f["canon"].startswith(_MOVED_CANONS):
            for k, d in (f.get("delta") or {}).items():
                delta[k] = delta.get(k, 0.0) + d
        else:
            kept.append(f)
    if delta:
        kept.append(_finding(
            "transcriptional: eye-skip withdrawn",
            "An eye-skip explanation first withheld the lectio-brevior credit here ("
            + ", ".join(f"{k} {d:+.2f}" for k, d in delta.items())
            + "); the unit then proved to be half of a word-order transposition, so the explanation was withdrawn, "
            "but the vote had already been taken without that credit.",
            "neither", strength="info", delta=delta,
        ))
    u.analysis = kept


_ELIDED = {"απ", "αφ", "επ", "εφ", "κατ", "καθ", "μετ", "μεθ", "παρ", "υπ", "υφ", "δι", "αντ", "ανθ", "αλλ", "ιν"}


def _same_stem(a: str, b: str, language: str) -> bool:
    if language == "greek":
        fa, fb = _is_function_word(a), _is_function_word(b)
        if fa or fb:
            if not (fa and fb):
                return False
            if any(a in g and b in g for g in _GREEK_PARADIGMS) or any({a, b} <= s for s in _MOVABLE_PAIRS):
                return True
            longer, shorter = (a, b) if len(a) > len(b) else (b, a)
            if shorter in _ELIDED and longer.startswith(shorter) and len(longer) == len(shorter) + 1:
                return True  # elision: ἀπʼ / ἀπό, ἀλλʼ / ἀλλά
            return longer == "ε" + shorter and shorter.startswith("αυτ")  # ἑαυτοῦ / αὐτοῦ
        ia, ib = _itacism_key(a), _itacism_key(b)
        if ia == ib:
            return True  # φοβεῖσθε / φοβισθε, ἔχωμεν / ἔχομεν
        diff_at = next((i for i, (p, q) in enumerate(zip(a, b)) if p != q), min(len(a), len(b)))
        if min(len(a), len(b)) >= 4 and _edit(a, b) <= 1 and (diff_at >= 3 or a[:1] in "εη" and b[:1] in "εη"):
            # one-letter spelling (εὐδόκησα / ηὐδόκησα); a letter changed in the first syllable is another
            # prefix or word (ἐκδύσαντες / ἐνδύσαντες, λαθεῖν / λαλεῖν, ἀνῆλθον / ἀπῆλθον)
            return True
        # the stem test also on itacism keys (a vowel spelling inside the stem must not end it early),
        # but then with four letters at least: πρῶτα / πρόβατα are different words
        if _common_prefix(ia, ib) >= max(4, min(len(ia), len(ib)) - 3):
            return True
    return _common_prefix(a, b) >= max(3, min(len(a), len(b)) - 3)


def _classify(lemma: List[str], variants: List[List[str]], lemma_raw: str, variant_raw: List[str], language: str,
              name_like: Optional[bool] = None) -> str:
    """``name_like``: whether the word is written as a proper name in the verse (None: not checked)."""
    if not lemma or any(not v for v in variants):
        return "omission / addition"
    if all(sorted(v) == sorted(lemma) for v in variants) and any(v != lemma for v in variants):
        return "word-order transposition"
    if all(len(v) == 1 for v in variants) and len(lemma) == 1:
        # The unit gets the label of its largest difference: one different word among several
        # readings (τούτου vs τοῦ vs τούτων) makes it a lexical substitution.
        a = lemma[0]
        labels = set()
        for v in variants:
            b = v[0]
            if (name_like is not False and lemma_raw[:1].isupper() and variant_raw
                    and any(r[:1].isupper() for r in variant_raw) and _edit(a, b) <= 2):
                labels.add("proper-name spelling")
            elif _same_stem(a, b, language):
                labels.add("inflection or spelling (same stem)")
            else:
                labels.add("lexical substitution")
        for label in ("lexical substitution", "inflection or spelling (same stem)"):
            if label in labels:
                return label
        return "proper-name spelling"
    if set(lemma) & set(w for v in variants for w in v):
        return "partial substitution"
    return "lexical substitution"


def _edit(a: str, b: str) -> int:
    from ..lexicon import edit_distance
    return edit_distance(a, b, limit=3)


def _fragment_nearby(cv: CollatedVerse, idx: int, comp_sigla: List[str], missing: List[str], whole_sigla: List[str],
                     language: str) -> bool:
    """Do a component reading's witnesses carry the missing words (or a form of them) in a nearby
    unit where the supposedly conflate reading's witnesses have nothing? Then the component is only
    the part of a longer reading that the alignment left in this unit (Rev 9:16: א's δυο … μυριαδασ)."""
    comp, whole = set(comp_sigla), set(whole_sigla)
    for j in range(max(0, idx - 2), min(len(cv.slots), idx + 3)):
        if j == idx:
            continue
        other = cv.slots[j]
        if not (whole & set(other.raw_forms.get("om.", []))):
            continue
        for form, sigs in other.raw_forms.items():
            if form == "om." or not (comp & set(sigs)):
                continue
            ks = (other.form_keys.get(form) or " ".join(_keys(form, language))).split()
            if any(k == m or _common_prefix(k, m) >= 4 for k in ks for m in missing):
                return True
    return False


def _conflations(units: List[ApparatusItem], language: str, cv: Optional[CollatedVerse] = None) -> List[Tuple[ApparatusItem, str, str]]:
    """Readings whose words are exactly two other readings of the unit put together (optionally
    joined by καί / et / ו), e.g. αἰνοῦντες καὶ εὐλογοῦντες vs αἰνοῦντες vs εὐλογοῦντες.
    Returns (unit, reading, canonical key of the reading)."""
    joiners = Counter({"και": 1}) if language == "greek" else Counter({"et": 1}) if language == "latin" else Counter()
    out = []
    for a in units:
        lemma_keys = [] if a.lemma == "om." else _keys(a.lemma, language)
        # the finding key of the adopted reading is the brain's own key (compared with lemma_key later)
        lemma_finding_key = " ".join(_lemma_keys(a, language)) or "om."
        readings = [(a.lemma, Counter(lemma_keys), list(a.lemma_witnesses), lemma_finding_key)] + [
            (v["reading"], Counter(_keys(v.get("adopt_text") or v["reading"], language)) if v["reading"] != "om." else Counter(),
             list(v["witnesses"]), "om." if v["reading"] == "om." else " ".join(_keys(v.get("adopt_text") or v["reading"], language)))
            for v in a.variants
        ]
        for raw, words, sigla, key in readings:
            others = [(w, sg) for r, w, sg, _k in readings if r != raw and w]
            found = False
            for i in range(len(others)):
                for j in range(i + 1, len(others)):
                    combo = others[i][0] + others[j][0]
                    if words == combo or words == combo + joiners:
                        if cv is not None and any(
                            _fragment_nearby(cv, a.slot_index, sg, list((words - w).elements()), sigla, language)
                            for w, sg in (others[i], others[j])
                        ):
                            continue  # a "component" is an alignment fragment, not a complete reading
                        found = True
            if found and sum(words.values()) >= 2:
                out.append((a, raw, key))
    return out
