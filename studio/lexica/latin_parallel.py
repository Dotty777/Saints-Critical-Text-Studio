"""Trilingual parallel-verse Latin disambiguator (100% open-licence, offline, stdlib-only).

Standalone ``studio/lexica/latin.py`` tags Latin verses strictly in isolation from the
Perseus Lewis & Short TEI dictionary (CC BY-SA 4.0) and STEPBible TIPNR names (CC BY 4.0),
leaving genuine Latin homographs (~3,800 tokens: ``quod``, ``cum``, ``quam``, ``quo``,
``vestrum``, ``multum``, ``facies``, ``tribus``, ``mundo``, ``liber``, ``concidit``, ...),
unlisted ``-e`` vocatives/adverbs, and rare OT/Deuterocanonical proper names untagged rather
than guessing.

During ``studio/concordance_gold.build_gold_concordance``, Hebrew (99.99% tagged via OSHB)
and Greek (99.97% tagged via TAGNT / LxxLemmas / open GLAUx) are already indexed into
``studio.db`` on the exact same Saints.Bible ``anchor_verse_id`` before Latin runs.  This
module uses ONLY those openly licensed parallel Greek and Hebrew verses (plus the
unambiguous standalone Latin tags of the same build) to resolve untagged Latin tokens when
parallel evidence cleanly decides the reading:

1. **Bipartite claim subtraction:** already-tagged Latin words in the verse claim their
   matched Greek/Hebrew tokens first, so unrelated words elsewhere in a long verse never
   bias an untagged token.
2. **Big-5 parallel syntax (``quod``, ``cum``, ``quam``, ``quo``, ``vestrum``):** resolves
   conjunction vs. relative vs. preposition vs. comparative against unclaimed Greek/Hebrew
   particles in a proportional local window (full-verse fallback only on short verses, and
   never falling through to lexical PMI; still withholding whenever both sides compete).
3. **``-e`` vocative vs. adverb resolution:** distinguishes true masculine vocatives
   (``magne``, ``dilecte``, ``carissime``, ``mute``, ``benedicte``, ``inclyte``) against
   parallel Greek/Hebrew vocative/adjective evidence from superlative ``-issime`` and
   documented Lewis & Short sub-entry adverbs (``recte``, ``occulte``, ``magnifice``).
4. **Empirical translation + POS + open-gloss lexical disambiguation:** uses the live
   Latin<->Greek/Hebrew co-occurrence table built from the unambiguous verses of the same
   corpus, POS agreement on shared-root and verb-vs-``P. a.`` splits, and POS-compatible
   content-word gloss overlap (Lewis & Short <-> TBESG/TBESH), requiring a decisive margin.
5. **Parallel ``PROPN`` alignment:** matches unlisted capitalised biblical names (stripping
   ``-que`` cleanly) against Greek and Hebrew ``PROPN`` lemmas and English glosses in the
   exact same verse, linking only to attested biblical Latin names that independently match
   the parallel ``PROPN`` (never classical Roman/Greek false matches).

Acrostic Hebrew stanza letters (Lamentations 1-4, Psalm 118) and genuinely undecided
tokens are NEVER guessed and remain untagged.
"""

from __future__ import annotations

import collections
import math
import re
import sqlite3
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from . import LemmaEntry, TokenTag
from . import latin as L

PARALLEL_SOURCE = "Saints trilingual parallel disambiguation (aligned to open OSHB/TAGNT/LxxLemmas/GLAUx)"

_BASE_STRONGS_RE = re.compile(r"^([HG]\d+)[a-z]+$")
_ENG_WORD_RE = re.compile(r"[a-z]{3,}")
_CAP_WORD_RE = re.compile(r"[A-Z][a-zA-Z'\-]{2,}")

_STOP_ENG: Set[str] = {
    "a", "an", "the", "of", "to", "in", "on", "at", "by", "for", "from", "with", "as", "or", "and",
    "be", "is", "are", "was", "were", "been", "one", "two", "that", "this", "these", "those", "it",
    "not", "into", "out", "up", "off", "over", "under", "about", "after", "before", "also", "very",
    "make", "do", "have", "get", "go", "come", "take", "give", "put", "set", "thing", "person",
    "man", "men", "woman", "plur", "sing", "adj", "adv", "noun", "verb", "part", "prep", "conj",
    "etc", "esp", "fig", "lit", "gen", "dat", "acc", "abl", "voc", "nom", "masc", "fem", "neut",
    "used", "often", "more", "most", "some", "any", "all", "such", "other", "same", "own", "self",
    "who", "which", "what", "whose", "whom", "his", "her", "its", "their", "our", "your", "through",
}

_CONTENT_POS: Set[str] = {"N", "V", "ADJ", "ADV", "NUM"}

# ---- Big-5 Greek/Hebrew parallel marker sets (base Strong's numbers) ----
_QUOD_CONJ_GRC = {"G3754", "G1360", "G1893", "G1894", "G2530"}     # ὅτι, διότι, ἐπεί, ἐπειδή, καθότι
_QUOD_CONJ_HEB = {"H3588"}                                          # כִּי
_QUOD_REL_GRC = {"G3739", "G3748", "G3745"}                         # ὅς, ὅστις, ὅσος
_QUOD_REL_HEB = {"H0834"}                                           # אֲשֶׁר

_CUM_PREP_GRC = {"G3326", "G4862", "G0260"}                         # μετά, σύν, ἅμα
_CUM_PREP_HEB = {"H5973", "H0854"}                                  # עִם, אֵת ('with')
_CUM_CONJ_GRC = {"G3753", "G3752", "G2259", "G5613", "G1893"}       # ὅτε, ὅταν, ἡνίκα, ὡς, ἐπεί
_CUM_CONJ_HEB = {"H3588", "H0518"}                                  # כִּי (temporal), אִם

_QUAM_COMP_GRC = {"G2228", "G5228", "G3844", "G4214", "G2245", "G5613", "G3123", "G4119"}
_QUAM_COMP_HEB = {"H4480"}                                          # מִן (comparative)
_QUAM_REL_GRC = {"G3739", "G3748", "G3745"}
_QUAM_REL_HEB = {"H0834"}

_QUO_ADV_GRC = {"G4226", "G3699", "G3606", "G3757"}                 # ποῦ, ὅπου, ὅθεν, οὗ
_QUO_ADV_HEB = {"H0375", "H0575", "H0335"}                          # אֵיפֹה, אָן, אַי
_QUO_REL_GRC = {"G3739", "G3748", "G3745"}
_QUO_REL_HEB = {"H0834"}

# Already-tagged Latin lemmas that consume parallel Big-5 markers before untagged tokens inspect them
_LAT_CONSUMES_HOTI = {"lat:quia", "lat:quoniam", "lat:quod#1", "lat:enim", "lat:nam"}
_LAT_CONSUMES_REL = {"lat:qui#1", "lat:quicumque", "lat:quisquis"}
_LAT_CONSUMES_CUM_PREP = {"lat:cum#1"}
_LAT_CONSUMES_CUM_CONJ = {"lat:cum#2", "lat:quando", "lat:dum", "lat:sicut", "lat:postquam", "lat:antequam", "lat:priusquam"}
_LAT_CONSUMES_QUAM_COMP = {"lat:quam", "lat:sicut", "lat:tamquam", "lat:quasi"}
_LAT_CONSUMES_MIN = {"lat:de", "lat:ex", "lat:a"}

# Documented L&S sub-entry adverbs in -e (matching latin._PARALLEL_ADV_ENTRIES)
_PARALLEL_ADV_BARE: Dict[str, str] = {
    L._b(lemma): key for key, lemma, _gloss, _root in getattr(L, "_PARALLEL_ADV_ENTRIES", ())
}

# Specific Hebrew/Greek biblical idioms for L&S sub-entry adverbs ('Rectene' = הֲשָׁלוֹם H7965, 'occulte' = סֵתֶר H5643,
# 'magnifice' = גֵּאוּת H1348, 'plenissime' = πληροφορέω G4135)
_ADV_E_PAR_KEYS: Dict[str, Set[str]] = {
    "recte": {"G3723", "G2573", "G2117", "G2229", "G3716", "G3718", "H7965", "H3190", "H3474", "H3559", "H5228", "H0571"},
    "occulte": {"G2977", "G2931", "G2927", "H5643", "H3909", "H2791"},
    "magnifice": {"G3171", "G3173", "G3170", "H1348", "H1431", "H3513"},
    "propere": {"G5035", "G5036", "G4704", "H4116"},
    "insensate": {"G0453", "G0878", "G3474"},
    "absconse": {"G2931", "G2977", "G2927", "H5643"},
}

# Vocative invocation neighbours in OT/NT ('Deus magne', 'sacerdos magne', 'dilecte mi', 'draco magne', 'o inclyte')
_VOC_NEIGHBOURS: Set[str] = {
    "deus", "domine", "domini", "sacerdos", "mons", "draco", "mi", "o", "uae", "spiritus",
    "pharisæe", "pharisaee", "gai", "ingredere", "fuge", "uteri", "uotorum", "fortissime", "terribilis",
}

# Regular -issime superlative adverbs -> base adjective lemma key in latin.py
_SUPERLATIVE_ADV_BASE: Dict[str, str] = {
    "certissime": "lat:certus",
    "fortissime": "lat:fortis",
    "uehementissime": "lat:vehemens",
    "libentissime": "lat:libens",
    "abundantissime": "lat:abundans",
    "prudentissime": "lat:prudens",
    "firmissime": "lat:firmus",
    "scelestissime": "lat:scelestus",
    "flagitiosissime": "lat:flagitiosus",
    "latissime": "lat:latus#1",
    "potentissime": "lat:potens",
    "studiosissime": "lat:studiosus",
    "rectissime": "lat:rectus",
    "plenissime": "lat:plenus",
}

# Oblique/gentilic suffixes stripped when matching unlisted Latin PROPNs to parallel Greek/Hebrew PROPNs
_PROPN_TAILS: Tuple[Tuple[str, str], ...] = (
    ("ensium", "ium"), ("itibus", "ibus"), ("orum", "orum"), ("arum", "arum"), ("ibus", "ibus"),
    ("itis", "is"), ("itae", "ae"), ("itas", "as"), ("itam", "am"), ("item", "em"), ("ite", "e"),
    ("enses", "es"), ("ios", "os"), ("iis", "is"), ("ium", "um"), ("ii", "i"), ("ae", "ae"),
    ("am", "am"), ("an", "an"), ("em", "em"), ("en", "en"), ("um", "um"), ("im", "im"),
    ("os", "os"), ("as", "as"), ("es", "es"), ("is", "is"), ("ei", "i"), ("eo", "o"),
    ("i", "i"), ("o", "o"), ("e", "e"), ("a", "a"),
)


@dataclass(frozen=True)
class ParToken:
    seq: int
    key: str          # exact Strong's / GWL key (e.g. 'G3754', 'H0834a', 'grc:Σικιμος')
    base_key: str     # base Strong's without trailing sub-letter (e.g. 'H0834', 'G3754')
    stem: str         # canonical Greek or Hebrew lemma
    pos: str          # N, V, ADJ, ADV, PREP, CONJ, PRON, PROPN, NUM, ...
    gloss: str        # English gloss from TBESG / TBESH / LxxLemmas
    morph: str        # R:..., A:..., O:..., G:WORD, H:WORD
    eng_words: frozenset


def _base_strongs(key: str) -> str:
    m = _BASE_STRONGS_RE.match(key or "")
    return m.group(1) if m else (key or "")


def _eng_words(gloss: str) -> frozenset:
    return frozenset(w for w in _ENG_WORD_RE.findall((gloss or "").lower()) if w not in _STOP_ENG)


def _pos_compatible(lat_pos: str, par_pos: str) -> bool:
    if lat_pos == par_pos:
        return True
    if lat_pos in ("N", "ADJ") and par_pos in ("N", "ADJ"):
        return True
    if lat_pos == "ADJ" and par_pos == "V":
        return True
    if lat_pos == "ADV" and par_pos in ("ADV", "ADJ"):
        return True
    return False


def _is_grc_participle(morph: str) -> bool:
    if not morph:
        return False
    if morph.startswith("R:V-") and len(morph) >= 6 and morph[5] == "P":
        return True
    if morph.startswith("A:v-") and len(morph) >= 7 and morph[6] == "p":
        return True
    return False


def _is_grc_infinitive(morph: str) -> bool:
    if not morph:
        return False
    if morph.startswith("R:V-") and len(morph) >= 6 and morph[5] == "N":
        return True
    if morph.startswith("A:v-") and len(morph) >= 7 and morph[6] == "n":
        return True
    return False


def _is_heb_prep_inf_construct(morph: str) -> bool:
    """True for Hebrew בְּ/כְּ + infinitive construct ('O:HR/Vqc...', 'when doing ...')."""
    if not morph or not morph.startswith("O:"):
        return False
    return "/V" in morph and any(seg.startswith("V") and len(seg) >= 3 and seg[2] == "c" for seg in morph[2:].split("/"))


def _is_grc_vocative(morph: str) -> bool:
    if not morph:
        return False
    if morph.startswith("R:"):
        parts = morph[2:].split("-")
        return len(parts) >= 2 and parts[0] in ("N", "A") and parts[1].startswith("V")
    if morph.startswith("A:") and len(morph) >= 10:
        return morph[2] in ("n", "a") and morph[9] == "v"
    return False


def _is_grc_genitive(morph: str) -> bool:
    if not morph:
        return False
    if morph.startswith("R:"):
        parts = morph[2:].split("-")
        return len(parts) >= 2 and "G" in parts[1]
    if morph.startswith("A:") and len(morph) >= 10:
        return morph[9] == "g"
    return False


def _is_grc_neuter(morph: str) -> bool:
    if not morph:
        return False
    if morph.startswith("R:"):
        parts = morph[2:].split("-")
        return len(parts) >= 2 and parts[1].endswith("N")
    if morph.startswith("A:") and len(morph) >= 9:
        return morph[8] == "n"
    return False


def _is_grc_feminine(morph: str) -> bool:
    if not morph:
        return False
    if morph.startswith("R:"):
        parts = morph[2:].split("-")
        return len(parts) >= 2 and parts[1].endswith("F")
    if morph.startswith("A:") and len(morph) >= 9:
        return morph[8] == "f"
    return False


def _is_grc_comparative(morph: str) -> bool:
    if not morph:
        return False
    if morph.startswith("R:") and morph.endswith("-C"):
        return True
    if morph.startswith("A:") and len(morph) >= 11 and morph[10] == "c":
        return True
    return False


def _is_grc_adv_neuter(morph: str) -> bool:
    """Greek neuter accusative adjective often used adverbially (πολύ, πρῶτον, τρίτον)."""
    if not morph:
        return False
    if morph.startswith("R:A-ASN") or morph.startswith("R:A-APN"):
        return True
    if morph.startswith("A:a-s---na") or morph.startswith("A:a-p---na"):
        return True
    return False


def _has_grc_art_inf(gtoks: Sequence[ParToken], idxs: Iterable[int]) -> bool:
    """True when the verse window contains Greek preposition (ἐν/διά/εἰς) + article + infinitive."""
    for k in set(idxs):
        if k + 2 < len(gtoks) and gtoks[k].base_key in ("G1722", "G1223", "G1519") and \
                gtoks[k + 1].base_key == "G3588" and _is_grc_infinitive(gtoks[k + 2].morph):
            return True
    return False


def _strip_enclitic_que(surface: str) -> Tuple[str, Tuple[str, ...]]:
    """Strip Latin enclitic -que from a capitalised name ('Chananæumque' -> 'Chananæum', ('E:que',))."""
    if len(surface) > 6 and surface.lower().endswith("que"):
        return surface[:-3], ("E:que",)
    return surface, ()


def _propn_skeletons(surface: str) -> Set[str]:
    """Consonant skeletons for a capitalised Latin surface plus its stripped oblique/gentilic stems."""
    surf, _ = _strip_enclitic_que(surface)
    sk = set(L._name_keys(surf))
    b = L._b(surf)
    if b.endswith("ae") and len(b) >= 5:
        sk.update(L._name_keys(b[:-2] + "as"))
    for tail, _code in _PROPN_TAILS:
        if b.endswith(tail) and len(b) - len(tail) >= 3:
            stem = b[: -len(tail)]
            sk.update(L._name_keys(stem))
            break
    if b.startswith(("palaestin", "palaesthin")):
        sk.update(L._name_keys("Philistin"))
    if b.startswith("godorla"):
        sk.update(L._name_keys("Chedorlaomer"))
    return {s for s in sk if s}


def _propn_match_score(lat_skels: Set[str], par: ParToken) -> bool:
    """True when a parallel Greek/Hebrew PROPN matches a Latin name's consonant skeleton."""
    par_skels: Set[str] = set()
    if par.stem and par.key.startswith(("G", "grc:")):
        par_skels.update(L._name_keys(par.stem))
    for w in _CAP_WORD_RE.findall(par.gloss or ""):
        if w not in ("Lord", "God", "King", "Son", "City", "Land", "Mount", "River", "Tribe", "House"):
            par_skels.update(L._name_keys(w))
    if not par_skels:
        return False
    for a in lat_skels:
        for z in par_skels:
            if L._skeletons_match(a, z):
                return True
    return False


def _propn_ending_code(surface: str) -> str:
    surf, _ = _strip_enclitic_que(surface)
    b = L._b(surf)
    for tail, code in _PROPN_TAILS:
        if b.endswith(tail) and len(b) - len(tail) >= 3 and code in L._NAME_CELLS:
            return f"L:NAME|{code}"
    return "L:PROPN|head"


def _clean_latin_nom(surface: str, pt: ParToken) -> str:
    """Derive a clean nominative Latin headword for a verse-attested proper name."""
    surf, _ = _strip_enclitic_que(surface)
    clean = surf.replace("æ", "ae").replace("œ", "oe").replace("Æ", "Ae").replace("Œ", "Oe")
    clean = re.sub(r"[^A-Za-z]", "", L._plain(clean))
    if not clean:
        return ""
    # Restore regular Greek -ος -> Latin -us for accusative/dat/abl/gen -um/-o/-i ('Prochorum', 'Aristobolo', 'Cyrino')
    if clean.endswith("um") and pt.stem.endswith("ος") and len(clean) >= 5:
        return clean[:-2] + "us"
    if clean.endswith(("o", "i")) and pt.stem.endswith("ος") and len(clean) >= 5:
        return clean[:-1] + "us"
    if clean.endswith("ae") and pt.stem.endswith(("ας", "ης")) and len(clean) >= 5:
        return clean[:-2] + "as"
    return clean


def load_parallel_verses(conn: sqlite3.Connection) -> Tuple[Dict[int, List[ParToken]], Dict[int, List[ParToken]]]:
    """Load all already-indexed Greek and Hebrew tokens from ``conn`` grouped by ``anchor_verse_id``."""
    par_grc: Dict[int, List[ParToken]] = collections.defaultdict(list)
    par_heb: Dict[int, List[ParToken]] = collections.defaultdict(list)
    gloss_cache: Dict[str, frozenset] = {}

    def get_ew(g: str) -> frozenset:
        hit = gloss_cache.get(g)
        if hit is None:
            hit = _eng_words(g)
            gloss_cache[g] = hit
        return hit

    for row in conn.execute(
        """
        SELECT wa.anchor_verse_id, wa.lang_stream, wa.slot_seq,
               COALESCE(ls.ext_strongs, ''), ls.canonical_stem, ls.pos_tag, ls.base_gloss, mc.morph_code
        FROM word_anchors wa
        JOIN stream_tokens st ON st.slot_id = wa.slot_id
        JOIN lexical_stems ls ON ls.stem_id = st.stem_id
        JOIN morpheme_catalog mc ON mc.morph_id = st.infl_morph_id
        WHERE wa.lang_stream IN ('grc_ot', 'grc_nt', 'heb_ot')
        ORDER BY wa.anchor_verse_id, wa.slot_seq
        """
    ):
        avid = int(row[0])
        stream = str(row[1])
        key = str(row[3] or "")
        gloss = str(row[6] or "")
        pt = ParToken(
            seq=int(row[2]),
            key=key,
            base_key=_base_strongs(key),
            stem=str(row[4] or ""),
            pos=str(row[5] or ""),
            gloss=gloss,
            morph=str(row[7] or ""),
            eng_words=get_ew(gloss),
        )
        if stream.startswith("grc"):
            par_grc[avid].append(pt)
        else:
            par_heb[avid].append(pt)
    return par_grc, par_heb


def load_existing_latin_lemmas(conn: sqlite3.Connection) -> Dict[int, Set[str]]:
    """Any already-indexed Latin lemmas in ``conn`` by ``anchor_verse_id`` (helps single-book builds)."""
    out: Dict[int, Set[str]] = collections.defaultdict(set)
    for avid, lkey in conn.execute(
        """
        SELECT wa.anchor_verse_id, COALESCE(ls.ext_strongs, '')
        FROM word_anchors wa
        JOIN stream_tokens st ON st.slot_id = wa.slot_id
        JOIN lexical_stems ls ON ls.stem_id = st.stem_id
        WHERE wa.lang_stream = 'lat_bible'
        """
    ):
        if lkey:
            out[int(avid)].add(str(lkey))
    return out


class ParallelDisambiguator:
    """Self-calibrating trilingual parallel-verse disambiguator for untagged Latin tokens."""

    def __init__(
        self,
        par_grc: Dict[int, List[ParToken]],
        par_heb: Dict[int, List[ParToken]],
        latin_lex: Dict[str, LemmaEntry],
        idx: Optional[L._Index] = None,
        tagger: Optional[L._Tagger] = None,
    ) -> None:
        self.par_grc = par_grc
        self.par_heb = par_heb
        self.latin_lex = latin_lex
        self.idx = idx if idx is not None else L._get_index()
        self.tagger = tagger if tagger is not None else L._get_tagger()

        self.n_verses: int = 1
        self.lat_counts: collections.Counter = collections.Counter()
        self.grc_counts: collections.Counter = collections.Counter()
        self.heb_counts: collections.Counter = collections.Counter()
        self.co_grc: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
        self.co_heb: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
        self.root_counts: collections.Counter = collections.Counter()
        self.root_co_grc: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
        self.root_co_heb: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)

        self._lat_gloss_words: Dict[str, frozenset] = {}
        # Index ONLY attested biblical/TIPNR Latin PROPN lemmas (never obscure classical L&S names like Hyades/Proca)
        self._propn_by_skel: Dict[str, List[int]] = collections.defaultdict(list)
        for i, lem in enumerate(self.idx.lemmas):
            if lem.proper and lem.pos == "PROPN" and not lem.key.startswith("lat:~"):
                if self.idx.prior.get(i, 0) >= 1 or lem.source == L.TIPNR_SOURCE:
                    for s in L._name_keys(lem.lemma):
                        self._propn_by_skel[s].append(i)
        self._dynamic_propn_by_bare: Dict[str, str] = {}
        self.stats: collections.Counter = collections.Counter()

    def _gloss_words_for(self, lkey: str, ci: Optional[int] = None) -> frozenset:
        hit = self._lat_gloss_words.get(lkey)
        if hit is not None:
            return hit
        ent = self.latin_lex.get(lkey)
        g = ent.gloss if ent is not None else (self.idx.lemmas[ci].gloss if ci is not None else "")
        ew = _eng_words(g)
        self._lat_gloss_words[lkey] = ew
        return ew

    def fit_from_verses(
        self,
        tagged_by_avid: Dict[int, List[Tuple[str, List[TokenTag]]]],
        existing_lat_by_avid: Optional[Dict[int, Set[str]]] = None,
    ) -> None:
        """Fit empirical Latin <-> Greek/Hebrew co-occurrence counts from unambiguous Latin tags."""
        lat_by_avid: Dict[int, Set[str]] = {}
        if existing_lat_by_avid:
            for avid, keys in existing_lat_by_avid.items():
                if avid not in tagged_by_avid:
                    lat_by_avid[avid] = set(keys)
        for avid, verse_entries in tagged_by_avid.items():
            s: Set[str] = lat_by_avid.setdefault(avid, set())
            for _text, tags in verse_entries:
                for t in tags:
                    if t.lemma_key:
                        s.add(t.lemma_key)

        self.n_verses = max(1, len(lat_by_avid))
        for avid, lkeys in lat_by_avid.items():
            gtoks = self.par_grc.get(avid)
            htoks = self.par_heb.get(avid)
            gkeys = {p.key for p in gtoks if p.key} if gtoks else ()
            hkeys = {p.key for p in htoks if p.key} if htoks else ()
            for gk in gkeys:
                self.grc_counts[gk] += 1
            for hk in hkeys:
                self.heb_counts[hk] += 1
            seen_roots: Set[str] = set()
            for lk in lkeys:
                self.lat_counts[lk] += 1
                cg = self.co_grc[lk]
                for gk in gkeys:
                    cg[gk] += 1
                ch = self.co_heb[lk]
                for hk in hkeys:
                    ch[hk] += 1
                ent = self.latin_lex.get(lk)
                rk = ent.root_key if ent is not None else lk
                if rk and rk not in seen_roots:
                    seen_roots.add(rk)
                    self.root_counts[rk] += 1
                    rg = self.root_co_grc[rk]
                    for gk in gkeys:
                        rg[gk] += 1
                    rh = self.root_co_heb[rk]
                    for hk in hkeys:
                        rh[hk] += 1

    def _pair_pmi(self, lk: str, par: ParToken, is_grc: bool) -> float:
        """Positive translation-association score for (Latin lemma, Greek/Hebrew lemma)."""
        lc = self.lat_counts.get(lk, 0)
        if lc < 2 or not par.key:
            return 0.0
        if is_grc:
            c = self.co_grc[lk].get(par.key, 0)
            pc = self.grc_counts.get(par.key, 1)
        else:
            c = self.co_heb[lk].get(par.key, 0)
            pc = self.heb_counts.get(par.key, 1)
        if c < 2:
            return 0.0
        p_lp = c / pc
        p_pl = c / lc
        lift = (c * self.n_verses) / (lc * pc)
        if lift < 3.0 or (p_lp < 0.05 and p_pl < 0.05):
            return 0.0
        return math.sqrt(p_lp * p_pl) * math.log1p(c) * min(3.0, math.log(lift))

    def _root_pmi(self, lk: str, par: ParToken, is_grc: bool) -> float:
        """Root-family backoff association when a rare Latin lemma has < 2 unambiguous verses."""
        ent = self.latin_lex.get(lk)
        rk = ent.root_key if ent is not None else lk
        rc = self.root_counts.get(rk, 0)
        if rc < 2 or not par.key:
            return 0.0
        if is_grc:
            c = self.root_co_grc[rk].get(par.key, 0)
            pc = self.grc_counts.get(par.key, 1)
        else:
            c = self.root_co_heb[rk].get(par.key, 0)
            pc = self.heb_counts.get(par.key, 1)
        if c < 2:
            return 0.0
        p_rp = c / pc
        p_pr = c / rc
        lift = (c * self.n_verses) / (rc * pc)
        if lift < 3.0 or (p_rp < 0.05 and p_pr < 0.05):
            return 0.0
        return 0.75 * math.sqrt(p_rp * p_pr) * math.log1p(c) * min(3.0, math.log(lift))

    def _claim_already_tagged(
        self,
        tags: Sequence[TokenTag],
        gtoks: Sequence[ParToken],
        htoks: Sequence[ParToken],
    ) -> Tuple[Set[int], Set[int]]:
        """Greedily claim Greek/Hebrew tokens already translated by unambiguous Latin words in this verse."""
        claimed_g: Set[int] = set()
        claimed_h: Set[int] = set()
        n_lat = max(1, len(tags))
        n_g = max(1, len(gtoks))
        n_h = max(1, len(htoks))

        for pos_i, t in enumerate(tags):
            lk = t.lemma_key
            if not lk:
                continue
            lat_frac = pos_i / n_lat
            if t.is_content:
                best_gi, best_gs = -1, 0.25
                for gi, gp in enumerate(gtoks):
                    if gi in claimed_g:
                        continue
                    sc = self._pair_pmi(lk, gp, True)
                    if sc > 0.0:
                        prox = 1.0 + 0.35 * max(0.0, 1.0 - abs(lat_frac - gi / n_g) / 0.35)
                        sc *= prox
                        if sc > best_gs:
                            best_gs, best_gi = sc, gi
                if best_gi >= 0:
                    claimed_g.add(best_gi)
                best_hi, best_hs = -1, 0.25
                for hi, hp in enumerate(htoks):
                    if hi in claimed_h:
                        continue
                    sc = self._pair_pmi(lk, hp, False)
                    if sc > 0.0:
                        prox = 1.0 + 0.35 * max(0.0, 1.0 - abs(lat_frac - hi / n_h) / 0.35)
                        sc *= prox
                        if sc > best_hs:
                            best_hs, best_hi = sc, hi
                if best_hi >= 0:
                    claimed_h.add(best_hi)
            else:
                def _claim_nearest(par_list: Sequence[ParToken], claimed: Set[int], want_bases: Set[str]) -> None:
                    n_p = max(1, len(par_list))
                    best_k, best_d = -1, 9.0
                    for pk, pp in enumerate(par_list):
                        if pk in claimed or pp.base_key not in want_bases:
                            continue
                        d = abs(lat_frac - pk / n_p)
                        if d < best_d:
                            best_d, best_k = d, pk
                    if best_k >= 0:
                        claimed.add(best_k)

                if lk in _LAT_CONSUMES_HOTI:
                    _claim_nearest(gtoks, claimed_g, _QUOD_CONJ_GRC)
                    _claim_nearest(htoks, claimed_h, _QUOD_CONJ_HEB)
                elif lk in _LAT_CONSUMES_REL:
                    _claim_nearest(gtoks, claimed_g, _QUOD_REL_GRC)
                    _claim_nearest(htoks, claimed_h, _QUOD_REL_HEB)
                elif lk in _LAT_CONSUMES_CUM_PREP or "E:cum" in t.prefixes:
                    _claim_nearest(gtoks, claimed_g, _CUM_PREP_GRC)
                    _claim_nearest(htoks, claimed_h, _CUM_PREP_HEB)
                elif lk in _LAT_CONSUMES_CUM_CONJ:
                    _claim_nearest(gtoks, claimed_g, _CUM_CONJ_GRC)
                    _claim_nearest(htoks, claimed_h, _CUM_CONJ_HEB)
                elif lk in _LAT_CONSUMES_QUAM_COMP:
                    _claim_nearest(gtoks, claimed_g, _QUAM_COMP_GRC)
                    _claim_nearest(htoks, claimed_h, _QUAM_COMP_HEB)
                elif lk in _LAT_CONSUMES_MIN:
                    _claim_nearest(htoks, claimed_h, _QUAM_COMP_HEB)
        return claimed_g, claimed_h

    def _window_indices(self, n_par: int, claimed: Set[int], lat_frac: float, radius: Optional[float]) -> List[int]:
        if n_par == 0:
            return []
        if radius is None:
            return [k for k in range(n_par) if k not in claimed]
        return [k for k in range(n_par) if k not in claimed and abs(lat_frac - k / n_par) <= radius]

    def _apply_choice(
        self,
        t: TokenTag,
        ci: int,
        anas: List[Tuple[str, str]],
        b: str,
        note: str,
        conf: float = 0.86,
        prefixes: Optional[Tuple[str, ...]] = None,
        morph_override: Optional[str] = None,
    ) -> None:
        lem = self.idx.lemmas[ci]
        pref = t.prefixes if prefixes is None else prefixes
        morph = morph_override or L._morph_for(self.idx, ci, anas, b, pref) or f"L:{lem.pos}|head"
        t.lemma_key = lem.key
        t.method = "parallel-aligned"
        t.confidence = round(conf, 3)
        t.prefixes = pref
        t.is_content = not (lem.noncontent or lem.hb == "sum")
        t.morph = morph
        t.notes = list(t.notes) + [note]

    # ---- Resolver 1: Big-5 function words ---------------------------------------------------------
    def _resolve_big5(
        self,
        t: TokenTag,
        b: str,
        pos_i: int,
        tags: Sequence[TokenTag],
        gtoks: Sequence[ParToken],
        htoks: Sequence[ParToken],
        claimed_g: Set[int],
        claimed_h: Set[int],
        group: Dict[int, List[Tuple[str, str]]],
    ) -> bool:
        def pick(hb: str, n: str = "") -> Optional[int]:
            for ci in group:
                lem = self.idx.lemmas[ci]
                if lem.hb == hb and (not n or lem.n == n):
                    return ci
            return None

        n_lat = max(1, len(tags))
        lat_frac = pos_i / n_lat
        nxt_b = L._b(tags[pos_i + 1].surface) if pos_i + 1 < len(tags) else ""
        prev_b = L._b(tags[pos_i - 1].surface) if pos_i > 0 else ""
        # Full-verse fallback only on short verses; long verses stay strictly within proportional local window
        radii: Tuple[Optional[float], ...] = (0.26, 0.38, None) if (len(gtoks) <= 20 and len(htoks) <= 18) else (0.24, 0.36)

        def decide_pair(
            check_fn,
            a_spec: Tuple[str, str],
            b_spec: Tuple[str, str],
            tag_label: str,
        ) -> bool:
            for rad in radii:
                gi_list = self._window_indices(len(gtoks), claimed_g, lat_frac, rad)
                hi_list = self._window_indices(len(htoks), claimed_h, lat_frac, rad)
                a_hits, b_hits = check_fn(gi_list, hi_list)
                if a_hits and not b_hits:
                    ci = pick(*a_spec)
                    if ci is not None:
                        kind, idx_hit, desc = a_hits[0]
                        if kind == "g" and idx_hit >= 0:
                            claimed_g.add(idx_hit)
                        elif kind == "h" and idx_hit >= 0:
                            claimed_h.add(idx_hit)
                        self._apply_choice(t, ci, group[ci], b, f"parallel: {tag_label} -> {desc}")
                        self.stats[f"big5:{b}"] += 1
                        return True
                if b_hits and not a_hits:
                    ci = pick(*b_spec)
                    if ci is not None:
                        kind, idx_hit, desc = b_hits[0]
                        if kind == "g" and idx_hit >= 0:
                            claimed_g.add(idx_hit)
                        elif kind == "h" and idx_hit >= 0:
                            claimed_h.add(idx_hit)
                        self._apply_choice(t, ci, group[ci], b, f"parallel: {tag_label} -> {desc}")
                        self.stats[f"big5:{b}"] += 1
                        return True
                if a_hits and b_hits:
                    return False
            return False

        if b == "quod":
            def _check_quod(gis: List[int], his: List[int]):
                conj, rel = [], []
                for gi in gis:
                    gp = gtoks[gi]
                    if gp.base_key in _QUOD_CONJ_GRC:
                        conj.append(("g", gi, f"{gp.key} {gp.stem} (conj)"))
                    elif gp.base_key in _QUOD_REL_GRC:
                        rel.append(("g", gi, f"{gp.key} {gp.stem} (rel)"))
                    elif gp.base_key == "G5101" and (nxt_b == "nomen" or (nxt_b == "est" and pos_i + 2 < len(tags) and L._b(tags[pos_i + 2].surface) == "nomen")):
                        rel.append(("g", gi, f"{gp.key} {gp.stem} ('Quod nomen' -> qui/quod)"))
                if not conj and _has_grc_art_inf(gtoks, gis):
                    conj.append(("g", -1, "Greek articular infinitive (conj)"))
                for hi in his:
                    hp = htoks[hi]
                    if hp.base_key in _QUOD_CONJ_HEB:
                        conj.append(("h", hi, f"{hp.key} {hp.stem} (conj)"))
                    elif hp.base_key in _QUOD_REL_HEB and hp.key != "H0834d":
                        rel.append(("h", hi, f"{hp.key} {hp.stem} (rel)"))
                grc_conj = [x for x in conj if x[0] == "g"]
                grc_neut_rel = [x for x in rel if x[0] == "g" and _is_grc_neuter(gtoks[x[1]].morph)]
                if grc_neut_rel and not grc_conj and not any(x[0] == "h" for x in rel):
                    return [], grc_neut_rel
                if grc_conj and not any(x[0] == "g" for x in rel) and not any(x[0] == "h" for x in conj):
                    return grc_conj, []
                return conj, rel

            return decide_pair(_check_quod, ("quod", ""), ("qui", "1"), "quod")

        if b == "cum":
            has_lat_ptc = any(
                (tg.morph or "").startswith(("L:VPP|", "L:V1N|", "L:V2N|", "L:V3IN|"))
                for tg in tags[max(0, pos_i - 2): min(len(tags), pos_i + 5)]
            )
            nxt_tok_surf = tags[pos_i + 1].surface if pos_i + 1 < len(tags) else ""
            # Grammatical impossibility guard: preposition 'cum' NEVER governs a finite verb ('cum evulsero')
            # or an accusative common noun/adjective ('cum Omnipotentem invocassent', 'cum purissimam aquam')
            nxt_is_verb = L._is_dominant_verb(self.idx, nxt_b)
            nxt_is_acc = bool(nxt_b) and not L._is_pure_abl(self.idx, nxt_b, cap=nxt_tok_surf[:1].isupper()) and (
                nxt_b.endswith(("em", "um", "am", "os", "as")) and (nxt_tok_surf[:1].islower() or nxt_b in ("omnipotentem", "dominum", "deum", "christum", "iesum"))
            )
            prep_impossible = nxt_is_verb or nxt_is_acc
            nxt2_b = L._b(tags[pos_i + 2].surface) if pos_i + 2 < len(tags) else ""
            nxt_is_abl_phrase = L._is_pure_abl(self.idx, nxt_b, cap=nxt_tok_surf[:1].isupper()) or (
                nxt_b in ("utraque", "omni", "tota", "sua", "mea", "tua", "nostra", "uestra",
                          "una", "duabus", "tribus", "multis", "cunctis", "uniuersis", "ipsa", "hac", "illa", "eadem")
                and bool(nxt2_b) and L._is_pure_abl(self.idx, nxt2_b)
            )
            grc_has_causal_hoti = any(gp.base_key == "G3754" for gp in gtoks)

            def _check_cum(gis: List[int], his: List[int]):
                prep, conj = [], []
                for gi in gis:
                    gp = gtoks[gi]
                    if not prep_impossible and gp.base_key in _CUM_PREP_GRC:
                        prep.append(("g", gi, f"{gp.key} {gp.stem} (prep)"))
                    elif not nxt_is_abl_phrase and gp.base_key in _CUM_CONJ_GRC:
                        conj.append(("g", gi, f"{gp.key} {gp.stem} (conj)"))
                if not conj and not nxt_is_abl_phrase and _has_grc_art_inf(gtoks, gis):
                    conj.append(("g", -1, "Greek ἐν/διά + articular inf (conj)"))
                for hi in his:
                    hp = htoks[hi]
                    if not prep_impossible and hp.base_key in _CUM_PREP_HEB:
                        prep.append(("h", hi, f"{hp.key} {hp.stem} (prep)"))
                    elif not nxt_is_abl_phrase and (
                        hp.base_key == "H0518" or hp.key == "H0834d" or _is_heb_prep_inf_construct(hp.morph)
                        or (hp.base_key == "H3588" and (prep_impossible or not grc_has_causal_hoti))
                    ):
                        conj.append(("h", hi, f"{hp.key} {hp.stem} (conj/inf-c)"))
                if not prep and not conj and not has_lat_ptc and not nxt_is_abl_phrase:
                    for gi in gis:
                        gp = gtoks[gi]
                        if _is_grc_participle(gp.morph):
                            conj.append(("g", gi, f"{gp.key} {gp.stem} (circumstantial ptc -> conj)"))
                            break
                if prep_impossible and not conj:
                    # Confirm subordinate clause when next word is finite verb or accusative + verb nearby
                    has_clause_v = nxt_is_verb or any(
                        L._is_dominant_verb(self.idx, L._b(tags[k].surface))
                        for k in range(pos_i + 2, min(len(tags), pos_i + 6))
                    )
                    if has_clause_v and (gis or his):
                        conj.append(("g", -1, "parallel clause + non-ablative Latin object/verb (conj)"))
                return prep, conj

            return decide_pair(_check_cum, ("cum", "1"), ("cum", "2"), "cum")

        if b == "quam":
            has_lat_comp_nearby = any(
                L._b(tags[k].surface) in L._COMPARATIVE_WORDS
                or L._b(tags[k].surface).endswith(("ior", "ius", "iores", "iora", "iorem", "ioris", "iori", "iore"))
                for k in range(max(0, pos_i - 5), pos_i)
            )
            def _check_quam(gis: List[int], his: List[int]):
                comp, rel = [], []
                for gi in gis:
                    gp = gtoks[gi]
                    if gp.base_key in _QUAM_COMP_GRC or _is_grc_comparative(gp.morph):
                        comp.append(("g", gi, f"{gp.key} {gp.stem} (comp/adv)"))
                    elif gp.base_key in _QUAM_REL_GRC:
                        rel.append(("g", gi, f"{gp.key} {gp.stem} (rel)"))
                for hi in his:
                    hp = htoks[hi]
                    # Hebrew מִן (H4480) is overwhelmingly prepositional 'from' — treat as comparative 'than'
                    # ONLY when Latin has a nearby comparative adjective/adverb!
                    if hp.base_key in _QUAM_COMP_HEB and has_lat_comp_nearby:
                        comp.append(("h", hi, f"{hp.key} {hp.stem} (comp)"))
                    elif hp.base_key in _QUAM_REL_HEB and hp.key != "H0834d":
                        rel.append(("h", hi, f"{hp.key} {hp.stem} (rel)"))
                grc_fem_rel = [x for x in rel if x[0] == "g" and _is_grc_feminine(gtoks[x[1]].morph)]
                grc_comp = [x for x in comp if x[0] == "g"]
                if grc_fem_rel and not grc_comp:
                    return [], grc_fem_rel
                return comp, rel

            return decide_pair(_check_quam, ("quam", ""), ("qui", "1"), "quam")

        if b == "quo":
            def _check_quo(gis: List[int], his: List[int]):
                adv, rel = [], []
                for gi in gis:
                    gp = gtoks[gi]
                    if gp.base_key in _QUO_ADV_GRC:
                        adv.append(("g", gi, f"{gp.key} {gp.stem} (whither)"))
                    elif gp.base_key in _QUO_REL_GRC:
                        rel.append(("g", gi, f"{gp.key} {gp.stem} (rel)"))
                for hi in his:
                    hp = htoks[hi]
                    if hp.base_key in _QUO_ADV_HEB:
                        adv.append(("h", hi, f"{hp.key} {hp.stem} (whither)"))
                    elif hp.base_key in _QUO_REL_HEB and hp.key != "H0834d":
                        rel.append(("h", hi, f"{hp.key} {hp.stem} (rel)"))
                return adv, rel

            if decide_pair(_check_quo, ("quo", ""), ("qui", "1"), "quo"):
                return True
            # Tight local window (±0.24) for interrogative τίς (G5101) so distant questions never contaminate
            gi_local = self._window_indices(len(gtoks), claimed_g, lat_frac, 0.24)
            for gi in gi_local:
                if gtoks[gi].base_key == "G5101":
                    if nxt_b in ("mihi", "nobis", "tibi", "ergo"):
                        ci = pick("quo")
                        if ci is not None:
                            claimed_g.add(gi)
                            self._apply_choice(t, ci, group[ci], b, "parallel: quo -> G5101 τίς ('to what purpose')")
                            self.stats["big5:quo"] += 1
                            return True
                    elif prev_b not in ("solum", "loco", "tempore", "die"):
                        ci = pick("quis", "1")
                        if ci is not None:
                            claimed_g.add(gi)
                            self._apply_choice(t, ci, group[ci], b, "parallel: quo -> G5101 τίς (interrogative)")
                            self.stats["big5:quo"] += 1
                            return True
            return False

        if b == "uestrum":
            gi_all = self._window_indices(len(gtoks), claimed_g, lat_frac, 0.45)
            # Explicit Greek possessive ὑμέτερος (G5212) -> lat:vester ('quod vestrum est', Lk 16:12)
            for gi in gi_all:
                if gtoks[gi].base_key == "G5212":
                    ci = pick("uester")
                    if ci is not None:
                        claimed_g.add(gi)
                        self._apply_choice(t, ci, group[ci], b, "parallel: vestrum -> G5212 ὑμέτερος (vester)")
                        self.stats["big5:uestrum"] += 1
                        return True
            part_grc = {"G1520", "G5100", "G5101", "G3173", "G3956", "G4183", "G3319", "G1538", "G3762"}
            has_part, has_noun = False, False
            for gi in gi_all:
                if gtoks[gi].base_key == "G4771" and _is_grc_genitive(gtoks[gi].morph):
                    nbrs = [gtoks[k] for k in (gi - 2, gi - 1, gi + 1) if 0 <= k < len(gtoks)]
                    if prev_b != "quod" and any(nb.base_key in part_grc or _is_grc_comparative(nb.morph) for nb in nbrs):
                        has_part = True
                    elif any(nb.pos == "N" for nb in nbrs):
                        has_noun = True
            if has_part and not has_noun:
                ci = pick("uos")
                if ci is not None:
                    self._apply_choice(t, ci, group[ci], b, "parallel: vestrum -> G4771 gen. partitive (vos)")
                    self.stats["big5:uestrum"] += 1
                    return True
            if has_noun and not has_part and prev_b != "est":
                ci = pick("uester")
                if ci is not None:
                    self._apply_choice(t, ci, group[ci], b, "parallel: vestrum -> G4771 gen. possessive (vester)")
                    self.stats["big5:uestrum"] += 1
                    return True
            return False

        return False

    # ---- Resolver 2: -e vocatives vs. adverbs -----------------------------------------------------
    def _resolve_adv_or_voc_e(
        self,
        t: TokenTag,
        b: str,
        pos_i: int,
        tags: Sequence[TokenTag],
        gtoks: Sequence[ParToken],
        htoks: Sequence[ParToken],
        claimed_g: Set[int],
        claimed_h: Set[int],
        group: Dict[int, List[Tuple[str, str]]],
    ) -> bool:
        n_lat = max(1, len(tags))
        lat_frac = pos_i / n_lat
        gi_win = self._window_indices(len(gtoks), claimed_g, lat_frac, 0.45) or self._window_indices(len(gtoks), claimed_g, lat_frac, None)
        hi_win = self._window_indices(len(htoks), claimed_h, lat_frac, 0.45) or self._window_indices(len(htoks), claimed_h, lat_frac, None)
        nbr_lat = {L._b(tags[k].surface) for k in (pos_i - 2, pos_i - 1, pos_i + 1, pos_i + 2) if 0 <= k < len(tags) and k != pos_i}

        # (0) Capitalised proper name miscaught as vocative in -e ('Aree' in 1 Chr 7:39)
        if t.surface[:1].isupper() and b not in _PARALLEL_ADV_BARE and b not in _SUPERLATIVE_ADV_BASE:
            if self._resolve_propn(t, b, pos_i, gtoks, htoks, claimed_g, claimed_h):
                return True

        # (a) True vocative confirmed by parallel Greek vocative OR OT invocation ('Deus magne', 'sacerdos magne', 'dilecte mi', 'o inclyte')
        has_grc_voc = any(_is_grc_vocative(gtoks[gi].morph) for gi in gi_win)
        is_voc_phrase = bool(nbr_lat & _VOC_NEIGHBOURS) and b not in _PARALLEL_ADV_BARE
        if (has_grc_voc or is_voc_phrase) and group and b not in _PARALLEL_ADV_BARE:
            # For 'Fortissime Deus', resolve as vocative of fortis rather than adverb
            if b in _SUPERLATIVE_ADV_BASE and not is_voc_phrase:
                pass
            else:
                best_ci, best_sc = None, -1.0
                for ci in group:
                    lk = self.idx.lemmas[ci].key
                    ew = self._gloss_words_for(lk, ci)
                    sc = 0.0
                    for gi in gi_win:
                        gp = gtoks[gi]
                        if _is_grc_vocative(gp.morph) or (is_voc_phrase and gp.pos in ("ADJ", "N", "V")):
                            sc = max(sc, self._pair_pmi(lk, gp, True) + len(ew & gp.eng_words))
                    for hi in hi_win:
                        hp = htoks[hi]
                        if is_voc_phrase and hp.pos in ("ADJ", "N", "V"):
                            sc = max(sc, self._pair_pmi(lk, hp, False) + len(ew & hp.eng_words))
                    if sc > best_sc:
                        best_sc, best_ci = sc, ci
                if best_ci is not None and (best_sc > 0 or (has_grc_voc and len(group) == 1) or (is_voc_phrase and len(group) == 1)):
                    why = "parallel: vocative confirmed by Greek vocative" if has_grc_voc else "parallel: vocative invocation confirmed by parallel verse"
                    self._apply_choice(t, best_ci, group[best_ci], b, why)
                    self.stats["adv_e:vocative"] += 1
                    return True

        # (b) Regular -issime superlative adverbs ('certissime', 'fortissime', 'vehementissime', 'plenissime', ...)
        base_key = _SUPERLATIVE_ADV_BASE.get(b)
        if base_key and base_key in self.idx.by_key:
            has_adv_par = any(gtoks[gi].pos in ("ADV", "ADJ", "V") for gi in gi_win) or any(
                htoks[hi].pos in ("ADV", "ADJ", "V") for hi in hi_win
            )
            if has_adv_par:
                ci = self.idx.by_key[base_key]
                self._apply_choice(t, ci, [("ADV", "")], b, f"parallel: superlative adverb -> {base_key}",
                                   morph_override="L:ADV|head")
                self.stats["adv_e:superlative"] += 1
                return True

        # (c) Documented L&S sub-entry adverbs in -e ('recte', 'rectene', 'occulte', 'magnifice', 'propere', ...)
        adv_b = b[:-2] if b.endswith("ne") and b[:-2] in _PARALLEL_ADV_BARE else b
        adv_pref = t.prefixes + (("E:ne",) if adv_b != b else ())
        adv_key = _PARALLEL_ADV_BARE.get(adv_b)
        if adv_key and adv_key in self.latin_lex:
            adv_ew = self._gloss_words_for(adv_key)
            want_keys = _ADV_E_PAR_KEYS.get(adv_b, set())
            matched_par = None
            for gi in gi_win:
                gp = gtoks[gi]
                if gp.base_key in want_keys or gp.pos == "ADV" or (adv_ew and (adv_ew & gp.eng_words)):
                    matched_par = f"{gp.key} {gp.stem}"
                    claimed_g.add(gi)
                    break
            if matched_par is None:
                for hi in hi_win:
                    hp = htoks[hi]
                    if hp.base_key in want_keys or hp.pos in ("ADV", "ADJ") or (adv_ew and (adv_ew & hp.eng_words)):
                        matched_par = f"{hp.key} {hp.stem}"
                        claimed_h.add(hi)
                        break
            if matched_par is not None:
                t.lemma_key = adv_key
                t.method = "parallel-aligned"
                t.confidence = 0.88
                t.prefixes = adv_pref
                t.is_content = True
                t.morph = "L:ADV|head"
                t.notes = list(t.notes) + [f"parallel: L&S sub-entry adverb confirmed by {matched_par}"]
                self.stats["adv_e:ls_adverb"] += 1
                return True
        return False

    # ---- Resolver 3: Lexical homographs (bipartite PMI + POS + gloss) -----------------------------
    def _resolve_lexical_ambig(
        self,
        t: TokenTag,
        b: str,
        pos_i: int,
        tags: Sequence[TokenTag],
        gtoks: Sequence[ParToken],
        htoks: Sequence[ParToken],
        claimed_g: Set[int],
        claimed_h: Set[int],
        group: Dict[int, List[Tuple[str, str]]],
    ) -> bool:
        if len(group) < 2:
            return False
        n_lat = max(1, len(tags))
        n_g = max(1, len(gtoks))
        n_h = max(1, len(htoks))
        lat_frac = pos_i / n_lat

        # Special case: ambiguous PROPN candidates ('Zaram' -> lat:Zara vs lat:Zaram; 'Spartiatas' -> Spartiate/a)
        if t.surface[:1].isupper() and all(self.idx.lemmas[ci].proper for ci in group):
            par_propns = [gp for gi, gp in enumerate(gtoks) if gi not in claimed_g and (gp.pos == "PROPN" or gp.stem[:1].isupper())] + \
                         [hp for hi, hp in enumerate(htoks) if hi not in claimed_h and hp.pos == "PROPN"]
            if par_propns:
                scored_p = []
                for ci in group:
                    lem = self.idx.lemmas[ci]
                    m_cnt = sum(1 for pt in par_propns if _propn_match_score(L._name_keys(lem.lemma), pt))
                    scored_p.append((m_cnt, int(self.idx.prior.get(ci, 0)), 1 if lem.source == L.LS_SOURCE else 0, ci))
                scored_p.sort(reverse=True)
                if scored_p[0][0] > 0 and (scored_p[0][0] > scored_p[1][0] or scored_p[0][1] > scored_p[1][1]):
                    ci = scored_p[0][3]
                    self._apply_choice(t, ci, group[ci], b, f"parallel: ambiguous PROPN resolved to {self.idx.lemmas[ci].key}")
                    self.stats["propn:disambig"] += 1
                    return True

        unclaimed_g = [gi for gi in range(len(gtoks)) if gi not in claimed_g]
        unclaimed_h = [hi for hi in range(len(htoks)) if hi not in claimed_h]
        if not unclaimed_g and not unclaimed_h:
            return False

        # Preposition guard: after a Latin preposition ('ad victum', 'a praesepio', 'in mundo'), drop finite/supine-only
        # verb candidates when nominal/adjectival candidates are present
        prev_b = L._b(tags[pos_i - 1].surface) if pos_i > 0 else ""
        if prev_b in L._PREPS and b.endswith(("o", "um", "am", "em", "is", "ibus", "a", "ae", "e", "u")):
            non_finite_group = {
                ci: anas for ci, anas in group.items()
                if self.idx.lemmas[ci].pos != "V" or any(pc in ("VPP", "VFP", "V1N", "V2N", "V3IN") and e != "u" for pc, e in anas)
            }
            if non_finite_group and len(non_finite_group) < len(group):
                group = non_finite_group
                if len(group) == 1:
                    ci, anas = next(iter(group.items()))
                    self._apply_choice(t, ci, anas, b, f"parallel: nominal after preposition '{prev_b}'")
                    self.stats["ambig:prep_nominal"] += 1
                    return True

        rows = []
        for ci, anas in group.items():
            lem = self.idx.lemmas[ci]
            lk = lem.key
            ew = self._gloss_words_for(lk, ci)
            ent = self.latin_lex.get(lk)
            rk = ent.root_key if ent is not None else lk

            best_pmi = 0.0
            best_pmi_hit: Optional[Tuple[str, int, ParToken]] = None
            best_gloss = 0
            best_gloss_hit: Optional[Tuple[str, int, ParToken]] = None
            best_root_pmi = 0.0
            best_root_hit: Optional[Tuple[str, int, ParToken]] = None

            for gi in unclaimed_g:
                gp = gtoks[gi]
                prox = 1.0 + 0.40 * max(0.0, 1.0 - abs(lat_frac - gi / n_g) / 0.35)
                sc = self._pair_pmi(lk, gp, True) * prox
                if sc > best_pmi:
                    best_pmi, best_pmi_hit = sc, ("g", gi, gp)
                if sc == 0.0 and gp.pos in _CONTENT_POS and _pos_compatible(lem.pos, gp.pos):
                    rsc = self._root_pmi(lk, gp, True) * prox
                    if rsc > best_root_pmi:
                        best_root_pmi, best_root_hit = rsc, ("g", gi, gp)
                # Strict content-POS + POS-compatible gloss overlap (never match prepositions like διά!)
                if ew and gp.eng_words and gp.pos in _CONTENT_POS and _pos_compatible(lem.pos, gp.pos):
                    ov = len(ew & gp.eng_words)
                    if ov > best_gloss:
                        best_gloss, best_gloss_hit = ov, ("g", gi, gp)

            for hi in unclaimed_h:
                hp = htoks[hi]
                prox = 1.0 + 0.40 * max(0.0, 1.0 - abs(lat_frac - hi / n_h) / 0.35)
                sc = self._pair_pmi(lk, hp, False) * prox
                if sc > best_pmi:
                    best_pmi, best_pmi_hit = sc, ("h", hi, hp)
                if sc == 0.0 and hp.pos in _CONTENT_POS and _pos_compatible(lem.pos, hp.pos):
                    rsc = self._root_pmi(lk, hp, False) * prox
                    if rsc > best_root_pmi:
                        best_root_pmi, best_root_hit = rsc, ("h", hi, hp)
                if ew and hp.eng_words and hp.pos in _CONTENT_POS and _pos_compatible(lem.pos, hp.pos):
                    ov = len(ew & hp.eng_words)
                    if ov > best_gloss:
                        best_gloss, best_gloss_hit = ov, ("h", hi, hp)

            rows.append({
                "ci": ci, "lk": lk, "pos": lem.pos, "rk": rk, "anas": anas, "pa_of": lem.pa_of,
                "pmi": best_pmi, "pmi_hit": best_pmi_hit,
                "root_pmi": best_root_pmi, "root_hit": best_root_hit,
                "gloss": best_gloss, "gloss_hit": best_gloss_hit,
            })

        def _claim(hit: Optional[Tuple[str, int, ParToken]]) -> str:
            if hit is None:
                return "parallel"
            kind, idx_h, pt = hit
            if kind == "g":
                claimed_g.add(idx_h)
            else:
                claimed_h.add(idx_h)
            return f"{pt.key} {pt.stem}"

        # (a) Shared-root / POS split disambiguation (multum ADV vs multus ADJ, imminuo V vs imminutus ADJ, ...)
        roots_present = {r["rk"] for r in rows}
        pos_set = {r["pos"] for r in rows}
        if len(roots_present) == 1 and len(pos_set) >= 2:
            best_anchor = max(rows, key=lambda r: (r["pmi"], r["root_pmi"], r["gloss"]))
            anchor_hit = best_anchor["pmi_hit"] or best_anchor["root_hit"] or best_anchor["gloss_hit"]
            if anchor_hit is not None and (best_anchor["pmi"] >= 0.20 or best_anchor["root_pmi"] >= 0.20 or best_anchor["gloss"] >= 1):
                kind, idx_h, pt = anchor_hit
                want_pos: Optional[str] = None
                if kind == "g" and pt.pos == "ADJ" and _is_grc_adv_neuter(pt.morph) and "ADV" in pos_set:
                    adj_neut_noun = any(
                        0 <= k < len(gtoks) and gtoks[k].pos == "N" and _is_grc_neuter(gtoks[k].morph)
                        for k in (idx_h - 1, idx_h + 1)
                    )
                    want_pos = "ADJ" if adj_neut_noun else "ADV"
                elif pt.pos == "ADV" and "ADV" in pos_set:
                    want_pos = "ADV"
                elif pt.pos == "V" and "V" in pos_set:
                    want_pos = "V"
                elif pt.pos == "N" and "N" in pos_set:
                    want_pos = "N"
                elif pt.pos == "ADJ" and "ADJ" in pos_set:
                    want_pos = "ADJ"
                elif pt.pos == "PRON" and "PRON" in pos_set:
                    want_pos = "PRON"
                if want_pos:
                    matches = [r for r in rows if r["pos"] == want_pos]
                    if len(matches) == 1:
                        w = matches[0]
                        src = _claim(anchor_hit)
                        self._apply_choice(t, w["ci"], w["anas"], b, f"parallel: shared-root POS ({want_pos}) via {src}")
                        self.stats["ambig:shared_root_pos"] += 1
                        return True

            # (a2) Verb vs its own L&S P.a. adjective (e.g. incrasso/incrassatus, nascor/nascens, luceo/lucens,
            #      persuadeo/persuasus, vulgo/vulgatus, deludo/delusus, imminuo/imminutus) when rare verb had no PMI
            verb_rows = [r for r in rows if r["pos"] == "V"]
            adj_rows = [r for r in rows if r["pos"] == "ADJ"]
            if len(verb_rows) == 1 and adj_rows and any(r["pa_of"] for r in adj_rows):
                prev_b = L._b(tags[pos_i - 1].surface) if pos_i > 0 else ""
                nxt_b = L._b(tags[pos_i + 1].surface) if pos_i + 1 < len(tags) else ""
                if prev_b in L._SUM_FORMS or nxt_b in L._SUM_FORMS:
                    w = verb_rows[0]
                    self._apply_choice(t, w["ci"], w["anas"], b, "parallel: periphrastic VPP + sum (verb over P.a.)")
                    self.stats["ambig:vpp_vs_pa"] += 1
                    return True
                loc_g = self._window_indices(len(gtoks), claimed_g, lat_frac, 0.25)
                loc_h = self._window_indices(len(htoks), claimed_h, lat_frac, 0.25)
                has_v = any(gtoks[gi].pos == "V" for gi in loc_g) or any(htoks[hi].pos == "V" for hi in loc_h)
                has_a = any(gtoks[gi].pos == "ADJ" for gi in loc_g) or any(htoks[hi].pos == "ADJ" for hi in loc_h)
                if has_v and not has_a:
                    w = verb_rows[0]
                    self._apply_choice(t, w["ci"], w["anas"], b, "parallel: local parallel verb (verb over P.a.)")
                    self.stats["ambig:vpp_vs_pa"] += 1
                    return True
                if has_a and not has_v and len(adj_rows) == 1:
                    w = adj_rows[0]
                    self._apply_choice(t, w["ci"], w["anas"], b, "parallel: local parallel adjective (P.a. over verb)")
                    self.stats["ambig:vpp_vs_pa"] += 1
                    return True

        # (b) Strong empirical translation-table win (guarded against Trap #1)
        by_pmi = sorted(rows, key=lambda r: (-r["pmi"], -r["gloss"]))
        top, sec = by_pmi[0], by_pmi[1]
        if top["pmi"] >= 0.30 and (sec["pmi"] == 0.0 or top["pmi"] >= 2.2 * sec["pmi"]):
            gloss_rivals = [r for r in rows[1:] if r["gloss"] >= 1 and r["gloss_hit"] is not None
                            and r["gloss_hit"][2].pos == r["pos"]]
            if top["gloss"] == 0 and gloss_rivals and top["pmi_hit"] is not None and top["pmi_hit"][2].pos != top["pos"]:
                pass
            else:
                if top["pmi_hit"] is not None and top["pmi_hit"][0] == "g":
                    gp = top["pmi_hit"][2]
                    if top["pos"] == "ADJ" and any(r["pos"] == "ADV" and r["rk"] == top["rk"] for r in rows) and \
                            (gp.pos == "ADV" or _is_grc_adv_neuter(gp.morph)):
                        adv_cands = [r for r in rows if r["pos"] == "ADV" and r["rk"] == top["rk"]]
                        if len(adv_cands) == 1:
                            w = adv_cands[0]
                            src = _claim(top["pmi_hit"])
                            self._apply_choice(t, w["ci"], w["anas"], b, f"parallel: adverbial match via {src}")
                            self.stats["ambig:shared_root_pos"] += 1
                            return True
                src = _claim(top["pmi_hit"])
                self._apply_choice(t, top["ci"], top["anas"], b, f"parallel: translation match via {src} (score={top['pmi']:.2f})")
                self.stats["ambig:empirical_pmi"] += 1
                return True

        # (c) Uncontested POS-compatible content-word gloss overlap
        by_gloss = sorted(rows, key=lambda r: (-r["gloss"], -(1 if (r["gloss_hit"] and r["gloss_hit"][2].pos == r["pos"]) else 0), -r["pmi"]))
        gtop, gsec = by_gloss[0], by_gloss[1]
        if gtop["gloss"] >= 1 and gsec["gloss"] == 0 and gsec["pmi"] < 0.25:
            src = _claim(gtop["gloss_hit"])
            self._apply_choice(t, gtop["ci"], gtop["anas"], b, f"parallel: lexicon gloss match via {src}")
            self.stats["ambig:gloss_overlap"] += 1
            return True

        # (d) Root-backoff PMI when exact lemma counts are sparse (<2) and only one root family matches
        by_rpmi = sorted(rows, key=lambda r: (-r["root_pmi"], -r["gloss"]))
        rtop, rsec = by_rpmi[0], by_rpmi[1]
        if rtop["rk"] != rsec["rk"] and rtop["root_pmi"] >= 0.45 and (rsec["root_pmi"] == 0.0 or rtop["root_pmi"] >= 2.5 * rsec["root_pmi"]):
            src = _claim(rtop["root_hit"])
            self._apply_choice(t, rtop["ci"], rtop["anas"], b, f"parallel: root-family match via {src}")
            self.stats["ambig:root_pmi"] += 1
            return True

        return False

    # ---- Resolver 4: Parallel PROPN matcher -------------------------------------------------------
    def _resolve_propn(
        self,
        t: TokenTag,
        b: str,
        pos_i: int,
        gtoks: Sequence[ParToken],
        htoks: Sequence[ParToken],
        claimed_g: Set[int],
        claimed_h: Set[int],
    ) -> bool:
        if not t.surface[:1].isupper():
            return False
        surf_clean, que_pref = _strip_enclitic_que(t.surface)
        b_clean = L._b(surf_clean)
        lat_skels = _propn_skeletons(surf_clean)
        if not lat_skels:
            return False

        matched_par: Optional[Tuple[str, int, ParToken]] = None
        for gi, gp in enumerate(gtoks):
            if gi in claimed_g:
                continue
            if gp.pos == "PROPN" or (gp.stem and gp.stem[:1].isupper()):
                if _propn_match_score(lat_skels, gp):
                    matched_par = ("g", gi, gp)
                    break
        if matched_par is None:
            for hi, hp in enumerate(htoks):
                if hi in claimed_h:
                    continue
                if hp.pos == "PROPN" or (hp.gloss and hp.gloss[:1].isupper() and not hp.gloss.startswith("to ")):
                    if _propn_match_score(lat_skels, hp):
                        matched_par = ("h", hi, hp)
                        break
        if matched_par is None:
            return False

        kind, idx_h, pt = matched_par
        if kind == "g":
            claimed_g.add(idx_h)
        else:
            claimed_h.add(idx_h)

        # 1. Link to an existing attested biblical Latin PROPN ONLY if that Latin lemma ITSELF independently
        #    matches the parallel Greek/Hebrew PROPN (prevents false links like Jaddo->Hyades, Prochorum->Proca!)
        best_existing: Optional[int] = None
        best_score = -1
        for s in lat_skels:
            skel_core = s.split(":")[1] if ":" in s else s
            for ci in self._propn_by_skel.get(s, ()):
                lem = self.idx.lemmas[ci]
                if not _propn_match_score(L._name_keys(lem.lemma), pt):
                    continue
                # Guard initial-letter mismatch on short/2-consonant skeletons ('Ananiae' != 'Chanaan')
                if (lem.hb[:1] in "bcdfgklmnpqrstxz" and b_clean[:1] in "aeiou") or (
                    b_clean[:1] in "bcdfgklmnpqrstxz" and lem.hb[:1] in "aeiou"
                ):
                    continue
                # Guard short names (len <= 4) and 2-consonant skeletons ('Lydos' != 'Lydda')
                if len(skel_core) <= 2:
                    if lem.hb[:3] != b_clean[:3]:
                        continue
                    if any(ch * 2 in lem.hb and ch * 2 not in b_clean for ch in "bdlmnprst"):
                        continue
                if len(lem.hb) <= 4 and abs(len(b_clean) - len(lem.hb)) <= 2 and b_clean[:3] != lem.hb[:3]:
                    continue
                # Prevent linking a vowel-final name ('Sephei') to a nasal-final name ('Shepham') unless surface has 'm'/'n'
                if lem.hb.endswith(("m", "n")) and not b_clean.endswith(("m", "n")) and "m" not in b_clean[-4:] and "n" not in b_clean[-4:] and len(lem.hb) <= 7:
                    continue
                sc = (20 if lem.hb == b_clean else 0) + (8 if len(skel_core) >= 3 else 0) + (10 if lem.source == L.TIPNR_SOURCE else 5) + int(self.idx.prior.get(ci, 0))
                if sc > best_score:
                    best_score, best_existing = sc, ci
        if best_existing is not None:
            lem = self.idx.lemmas[best_existing]
            morph = "L:PROPN|head" if b_clean == lem.hb else _propn_ending_code(surf_clean)
            self._apply_choice(
                t, best_existing, [("textname", "")], b_clean,
                f"parallel: PROPN linked to {lem.key} via {pt.key} {pt.stem}",
                conf=0.85, prefixes=t.prefixes + que_pref, morph_override=morph,
            )
            self.stats["propn:linked_existing"] += 1
            return True

        # 2. Otherwise register a clean verse-attested Latin PROPN lemma in latin_lex
        clean_nom = _clean_latin_nom(surf_clean, pt)
        if not clean_nom:
            return False
        nom_bare = L._b(clean_nom)
        lkey = self._dynamic_propn_by_bare.get(nom_bare)
        if lkey is None:
            lkey = f"lat:{clean_nom}"
            self._dynamic_propn_by_bare[nom_bare] = lkey
            if lkey not in self.latin_lex:
                gloss = (pt.gloss or pt.stem or clean_nom).strip()
                if gloss == pt.stem and pt.key.startswith("grc:"):
                    gloss = f"{clean_nom} (biblical proper name; LXX {pt.stem})"
                self.latin_lex[lkey] = LemmaEntry(
                    L.LANG, lkey, clean_nom, gloss[:160], "PROPN", None,
                    lkey, clean_nom, gloss[:160], "self", "", PARALLEL_SOURCE,
                )
        t.lemma_key = lkey
        t.method = "parallel-aligned"
        t.confidence = 0.83
        t.prefixes = t.prefixes + que_pref
        t.is_content = True
        t.morph = "L:PROPN|head" if b_clean == nom_bare else _propn_ending_code(surf_clean)
        t.notes = list(t.notes) + [f"parallel: PROPN attested by {pt.key} {pt.stem}"]
        self.stats["propn:new_attested"] += 1
        return True

    # ---- Entry point per verse --------------------------------------------------------------------
    def disambiguate_verse(self, avid: int, tags: List[TokenTag], text: str = "") -> int:
        """Resolve untagged Latin tokens in ``tags`` using parallel Greek/Hebrew tokens at ``avid``."""
        gtoks = self.par_grc.get(avid) or ()
        htoks = self.par_heb.get(avid) or ()
        if not gtoks and not htoks:
            return 0
        if not any(t.lemma_key is None for t in tags):
            return 0

        claimed_g, claimed_h = self._claim_already_tagged(tags, gtoks, htoks)
        flags = L._sentence_initial_flags(text, [t.surface for t in tags]) if text else [i == 0 for i in range(len(tags))]
        resolved = 0

        for pos_i, t in enumerate(tags):
            if t.lemma_key is not None:
                continue
            nstr = " | ".join(t.notes)
            # Never touch Hebrew acrostic stanza headers (Lamentations 1-4, Psalm 118)
            if "Hebrew letter name" in nstr:
                continue
            b = L._b(t.surface)
            ini = flags[pos_i] if pos_i < len(flags) else (pos_i == 0)
            cands, _pref, _notes = self.tagger.analyse_token(t.surface, ini)
            group = L._choose_group(self.idx, cands, b, t.surface, ini) if cands else {}

            # 1. Big-5 function words: handled EXCLUSIVELY by _resolve_big5 (never fall through to lexical PMI!)
            if b in ("quod", "cum", "quam", "quo", "uestrum"):
                if len(group) >= 2 and self._resolve_big5(t, b, pos_i, tags, gtoks, htoks, claimed_g, claimed_h, group):
                    resolved += 1
                continue

            # 2. Missing -e vocatives vs. adverbs
            if "vocative in -e" in nstr:
                if self._resolve_adv_or_voc_e(t, b, pos_i, tags, gtoks, htoks, claimed_g, claimed_h, group):
                    resolved += 1
                continue

            # 3. Genuine lexical homographs
            if len(group) >= 2 and "probably a name" not in nstr:
                if self._resolve_lexical_ambig(t, b, pos_i, tags, gtoks, htoks, claimed_g, claimed_h, group):
                    resolved += 1
                    continue

            # 4. Unlisted capitalised proper names (and mid-sentence verb-guard names like 'Nabo')
            if (not group or "probably a name" in nstr) and t.surface[:1].isupper():
                if self._resolve_propn(t, b, pos_i, gtoks, htoks, claimed_g, claimed_h):
                    resolved += 1
                    continue

        return resolved
