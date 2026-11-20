"""Latin lemma + root tagger for The Saints Concordance (Saints Latin critical text / Vulgate).

Added 18 Nov 2026.  There is no openly licensed lemmatised Vulgate, so this module is a
dictionary-driven lemmatiser built from **Lewis & Short, A Latin Dictionary** (Perseus TEI XML,
CC BY-SA 4.0, Perseus Digital Library, https://www.perseus.tufts.edu/ ,
https://github.com/PerseusDL/lexica).

How it works
------------
1. Every Lewis & Short entry is read once (headword, homograph number, part of speech, gender,
   ``itype`` = genitive / principal parts / conjugation, etymology, first English gloss).  The parsed
   entries are cached in ``data/latin_form_index.json.gz`` together with a signature of the L&S file
   and ``INDEX_VERSION``; the cache is rebuilt automatically when either changes.
2. From each entry a paradigm is produced as *stems + ending classes* (nouns of the 1st-5th
   declensions, i-stems, neuters, Greek-type ``-as/-es`` nouns; adjectives of the 1st/2nd and 3rd
   declensions with comparative and superlative; verbs of the 1st-4th conjugations, ``-io`` verbs,
   deponents and semi-deponents, perfect system, participles, gerund and gerundive, infinitives).
   Pronouns, irregular verbs (sum and its compounds, possum, eo and compounds, fero and compounds,
   volo / nolo / malo, fio, queo / nequeo), defective verbs (memini, odi, aio, inquam), numerals and
   the irregular comparisons are closed lists in this file.
3. A token is analysed by trying every stem + ending split.  Pronoun + ``-cum`` (mecum, secum, nobiscum)
   is recognised before any paradigm ('secum' is not the adjective secus); Vulgate 'Cumque' is conj. cum
   + -que.  The enclitics ``-que -ne -ve`` (and ``-met`` after pronouns) are split off only when the
   whole word has no analysis, so quoque, atque, itaque, neque, usque, quisque, bene, sine, paene ...
   stay whole; a capitalised word is never split to reach a proper name (Josue is not Ios + -ve), and a
   capitalised form that is never written in lower case is tried as a name first.  If a lower-case word
   has no analysis at all, a few documented Vulgate spelling variants are tried (y/i, ch/c, assimilated
   or unassimilated prefixes ...), with stricter conditions since 18 Nov 2026 (e -> i not in the first
   syllable, no function-word results such as hin -> in); capitalised names are never respelt into
   Latin words or classical names.
4. Capitalised words: Lewis & Short proper-name entries (declined only as L&S's genitive says) and
   STEPBible TIPNR names (CC BY 4.0) matched *exactly*; no declension is invented for either.  Hebrew
   and Greek names that neither covers (Jonathas, Ezechias, Philisthiim ...) are recognised from the
   Studio text itself (``NAME_INFERENCE``): a capitalised token with no analysis that is never written
   in lower case is its own lemma when its ending cannot be a Latin oblique case (David, Galaad,
   Ezechias); an oblique form (Ezechiae, Moysen) gets the lemma of its nominative only when that
   nominative is itself attested.  These tags carry confidence 0.75.
5. Ambiguous forms (est = sum/edo, venit = venio/veneo, vocem = vox/voco, populi = people/poplar) are
   resolved by P(lemma) x P(form | lemma): the lemma prior counts the tokens of the Studio's own Latin
   text whose analysis is unambiguous, plus a small pseudo-count from the size of the L&S entry, plus
   documented manual priors (``_LEMMA_PRIOR``, ``_FORM_PRIOR``, read off random KWIC samples of the
   Studio text); P(form | lemma) is the share of that paradigm slot (e.g. 1st-conj. present subjunctive
   1 sg. vs 3rd-decl. accusative sg.) among the unambiguous tokens.  A few documented context rules
   cover function words ('eo quod', 'magis quam', 'cum autem').  When the best lemma holds < 70 % of
   the mass the token stays untagged (``lemma_key=None``); a prior-resolved tag gets a lower
   confidence (0.9 x share).  A few forms are decided by context only and otherwise stay untagged
   (``_context_form``: facies = face / facio fut., mundi/mundum/mundo = world / clean, sede, vivo,
   scribam, imperative 'Sine', sentence-initial interrogative quem/cui/cujus/quibus).  The Hebrew letter
   names heading the acrostic stanzas of Lamentations 1-4 and Psalm 118 are left untagged.
6. Roots (``root_key``) come only from explicit L&S statements: the ``<etym>`` element or the
   bracketed etymology at the head of the entry (``[primus-capio]``, ``[ad-capio]``), ``P. a. of X``
   (participial adjectives), ``comp./sup. of X``, the ``adv., v. X`` cross-reference of adverbs, and
   L&S's own compound division of the headword (``ab-eo``) when the second part is a headword.
   Chains are followed (principium -> princeps -> primus + capio => root capio), as are L&S stubs that
   only refer to another headword of the same part of speech ('gnosco, v. nosco'); a compound's root is
   its last member that is not a preposition/prefix or an enclitic/suffix (quisque -> quis, ubique ->
   ubi); a compound verb takes the homograph of its own conjugation and perfect (dedico -> dico#1,
   comedo -> edo#1 'eat').  Anything vaguer (``cf.``, ``root ...``, Sanskrit or Greek cognates,
   ``perh.``) gives no family: root_key is the lemma itself (root_source ``'self'``).  caput (head) is
   therefore not merged with capio (take).  L&S's '[id.]' (= as the entry before) is not followed.
7. Glosses: the head rendering of the first L&S sense plus those of the next main senses (facies ->
   'make; face, visage; external form, look'), never a grammar label ('imper.', 'N. cr.'); entries
   without a rendering of their own take the one L&S gives for that word in the entry they point to
   (sanctus, mandatum) or are described from it ('adv. of validus (strong)'); a short documented table
   (``_GLOSS_OVERRIDE``) covers frequent entries whose XML italicises no main sense (facio, do).
   Since 19 Nov 2026 (final check of the live build): a reviewed Saints table (``_SAINTS_GLOSS``, about 1,900
   lemmas: the 1,500+ most frequent lemmas of the Studio Latin by token count and the heads of their families)
   gives the plain biblical sense first (respondeo 'to answer, reply', princeps 'prince, chief, ruler', gens
   'nation, people; (plur.) the Gentiles', pecco 'to sin', aries 'ram'); for the rest the cleaner drops grammar
   labels and Latin construction words ('aliquem aliquid', 'advv. of place', 'object-clause'), Greek etymologies
   and words left dangling, keeps adjacent italics apart ('spread out, extend'), and lets a sense L&S cites from
   the Vulgate lead over a classical first sense (apostolus 'an Apostle', not 'a notice sent to a higher
   tribunal').
8. Name glosses: a name lemma attested in the Studio text is described from the STEPBible TIPNR individuals
   (CC BY 4.0: @Brief / @Briefest lines and every verse of each individual) that stand in its verses and bear a
   compatible name (consonant skeleton of the English, Hebrew-transliterated or Greek form): Paulus -> 'Paul:
   apostle to the Gentiles ...', Simon -> 'several bearers (...)'; a name with no such individual gets 'proper
   name' unless its L&S description names a biblical bearer - never a classical person (Paulus 'a consul who fell
   near Cannae', Anna 'the sister of Dido').  A capitalised form with no analysis that is never written in lower
   case is a Hebrew name of its own when a TIPNR individual with the same skeleton stands in that verse
   (Nephthali, Amri, Lachis, Giezi); declined Greek forms and Latin oblique endings are not made headwords.
9. Parsing (``TokenTag.morph``, 18 Nov 2026): every tagged token gets 'L:' + paradigm class + '|' + ending of
   the analysis that produced the chosen lemma ('L:N1|am', 'L:V3A|unt', 'L:VPF|it'); several analyses of that
   lemma are sorted and joined with ',' ('L:V3A|it,L:VPF|it' for legit).  This is a class and an ending, not a
   single paradigm cell: ``morph_legend()`` lists every cell each code can be ('L:N1|ae': genitive/dative
   singular; nominative/vocative plural).  Hand-listed forms (sum, eo, fero ... and compounds, pronouns, numerals)
   are 'L:closed|<form>' with their cells from hand tables; uninflected words and listed nominatives are
   'L:<class or part of speech>|head'.  The code is computed after the lemma is chosen and changes no choice.

Licences of every file read here: Lewis & Short XML (CC BY-SA 4.0), STEPBible TIPNR (CC BY 4.0; its
descriptions are shortened here, a change its licence asks to note) and the Studio's own critical text
(``data/studio.db``, opened read-only).  No non-commercial data
(PROIEL, ITTB, LASLA ...) is read by this module; PROIEL is used only by evaluation scripts kept
outside ``studio/``.
"""

from __future__ import annotations

import difflib
import gzip
import json
import os
import re
import sqlite3
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Set, Tuple

from . import LemmaEntry, TokenTag, latin_bare, tokenize_verse

LANG = "lat"
INDEX_VERSION = "lat-2026-11-19.12"  # .12: L&S sub-entries, pure Part. comma/v. stubs, Cyrillic y in _b, doubled-prefix _attach_part, noun/verb/eo/odi/ordinal paradigms, TIPNR exact cache

LS_SOURCE = "Lewis & Short, A Latin Dictionary (Perseus TEI XML, CC BY-SA 4.0)"
LS_ROOT_SOURCE = "LewisShort-etym"
TIPNR_SOURCE = "STEPBible TIPNR proper names (CC BY 4.0)"
CLOSED_SOURCE = "Saints closed list (Latin grammar); headword and gloss per Lewis & Short (CC BY-SA 4.0)"

AMBIGUITY_THRESHOLD = 0.70      # the best lemma must hold >= 70 % of the prior mass
_LS_SIZE_WEIGHT = 1.0 / 1500.0  # prior pseudo-count per character of the L&S entry ...
_LS_SIZE_CAP = 25.0             # ... capped


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_STUDIO_ROOT = Path(__file__).resolve().parents[2]


def _catalog_attr(name: str, default: Path) -> Path:
    try:
        from .. import catalog  # type: ignore
        return Path(getattr(catalog, name))
    except Exception:
        return default


def ls_path() -> Path:
    """Lewis & Short TEI XML with Greek in Unicode (the Perseus file meant for use)."""
    env = os.environ.get("SAINTS_LEWIS_SHORT_XML")
    if env:
        return Path(env)
    root = _catalog_attr("LATIN_RESEARCH_ROOT", _STUDIO_ROOT / "Saints-Latin-Critical-Text")
    return (root / "01_Tier1_Open_Vulgate_Base_Texts" / "Lexicon_Lewis_And_Short_XML" / "CTS_XML_TEI" / "perseus"
            / "pdllex" / "lat" / "ls" / "lat.ls.perseus-eng2.xml")


_TIPNR_NAME = "TIPNR - Translators Individualised Proper Names with all References - STEPBible.org CC BY.txt"


def _long(p: Path) -> Path:
    """Windows paths over MAX_PATH (the TIPNR file inside the Studio is ~262 characters) need the
    extended-length prefix."""
    s = str(p)
    if os.name == "nt" and len(s) >= 240 and not s.startswith("\\\\?\\"):
        return Path("\\\\?\\" + os.path.abspath(s))
    return p


def tipnr_path() -> Optional[Path]:
    env = os.environ.get("SAINTS_TIPNR")
    if env:
        return _long(Path(env)) if _long(Path(env)).exists() else None
    greek = _catalog_attr("GREEK_RESEARCH_ROOT", _STUDIO_ROOT / "Saints-Greek-Critical-Text")
    hebrew = _catalog_attr("HEBREW_RESEARCH_ROOT", _STUDIO_ROOT / "Saints-Hebrew-Critical-Text")
    for cand in (greek / "01_Tier1_Modern_Critical_Open" / "NT_OT_STEPBible_Data" / "Proper Nouns" / _TIPNR_NAME,
                 greek / "01_Tier1_Modern_Critical_Open" / "OT_STEPBible_Data" / "Proper Nouns" / _TIPNR_NAME,
                 hebrew / "01_Tier1_Modern_Critical_Open" / "OT_STEPBible_Data" / "Proper Nouns" / _TIPNR_NAME):
        cand = _long(cand)
        if cand.exists():
            return cand
    return None


def data_dir() -> Path:
    return _catalog_attr("DATA_DIR", _STUDIO_ROOT / "data")


def db_path() -> Path:
    return data_dir() / "studio.db"


def cache_path() -> Path:
    return data_dir() / "latin_form_index.json.gz"


# ---------------------------------------------------------------------------
# Small text helpers
# ---------------------------------------------------------------------------

_VOW = set("aeiouy")


_CYRILLIC_Y = str.maketrans({"у": "y", "У": "Y", "ў": "y", "Ў": "Y"})


def _plain(text: str) -> str:
    """Headword without quantity marks/accents; keeps case, letters and hyphens.  The Perseus L&S XML prints
    y-breve with the Cyrillic letter 'ў' in about 1,100 headwords ('sўnăgōga', 'hўmnus'): read as y (before
    19 Nov 2026 these lost their y, so synagoga, hyacinthus, gazophylacium ... had no paradigm)."""
    t = (text or "").replace("æ", "ae").replace("Æ", "Ae").replace("œ", "oe").replace("Œ", "Oe")
    nfd = unicodedata.normalize("NFD", t).translate(_CYRILLIC_Y)
    t = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^A-Za-z\-]", "", t)


def _b(text: str) -> str:
    return latin_bare((text or "").translate(_CYRILLIC_Y))


_ASCII_WORD = re.compile(r"[A-Za-z]+")
_AB_TABLE = str.maketrans("JVjv", "iuiu")


def _ab(word: str) -> str:
    """latin_bare() of a plain ASCII word (fast path for the gloss checks)."""
    return word.lower().translate(_AB_TABLE)


def _common_prefix_len(a: str, z: str) -> int:
    n = 0
    for x, y in zip(a, z):
        if x != y:
            break
        n += 1
    return n


def _strip_parens(text: str) -> str:
    out, depth = [], 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return "".join(out)


# ---------------------------------------------------------------------------
# Ending tables (bare spelling: u for v, i for j)
# ---------------------------------------------------------------------------

def _e(s: str) -> frozenset:
    return frozenset("" if w == "0" else w for w in s.split())


_A12 = "us a um i ae o am os as is orum arum e"
ENDINGS: Dict[str, frozenset] = {
    # nouns
    "N1": _e("a ae am arum is as abus"),
    "N1GA": _e("as ae am an a is arum"),         # Greek masc. -as (Satanas, Isaias, mandragoras)
    "N1GE": _e("es ae en e am a arum is as"),    # Greek -es / -e (Levites, Spartiates, parasceve)
    "N1PL": _e("ae arum is as"),
    "N2": _e("us i o um e orum is os"),
    "N2IUS": _e("us i o um 0 orum is os"),       # filius: fili (voc.), filii
    "N2R": _e("i o um orum is os"),              # puer / ager after the -r stem
    "N2N": _e("um i o a orum is"),
    "N2PLM": _e("i orum is os"),
    "N2PLN": _e("a orum is"),
    "N3": _e("is i em e es um ibus"),
    "N3I": _e("is i em e es ium ibus"),
    "N3IM": _e("is i em im in e es ium ibus"),
    "N3N": _e("is i e a um ibus"),
    "N3NI": _e("is i ia ium ibus"),
    "N3PL": _e("es um ium ibus"),
    "N3PLN": _e("a ia um ium ibus"),
    "N4": _e("us ui u um uum ibus ubus"),
    "N4N": _e("u us ua uum ibus"),
    "N5": _e("es ei em e erum ebus"),
    # adjectives
    "A12": _e(_A12),
    "A12R": _e("a um i ae o am os as is orum arum"),
    "A12PL": _e("i ae a orum arum is os as"),
    "A3": _e("is e i em es ia ium ibus"),
    "A31I": _e("is i em e es ia ium ibus"),
    "A31C": _e("is i em e es a um ibus"),
    "CMP": _e("ior ius ioris iori iorem iore iores iora iorum ioribus"),
    # verbs: present system
    "V1A": _e("o as at amus atis ant abam abas abat abamus abatis abant abo abis abit abimus abitis abunt "
              "em es et emus etis ent arem ares aret aremus aretis arent a ate ato atote anto are"),
    "V1P": _e("or aris are atur amur amini antur abar abaris abare abatur abamur abamini abantur abor aberis "
              "abere abitur abimur abimini abuntur er eris ere etur emur emini entur arer areris arere aretur "
              "aremur aremini arentur ari ator antor"),
    "V1N": _e("ans antis anti antem ante antes antium antibus antia andi ando andum andus anda andae andam "
              "andos andas andis andorum andarum"),
    "V2A": _e("eo es et emus etis ent ebam ebas ebat ebamus ebatis ebant ebo ebis ebit ebimus ebitis ebunt "
              "eam eas eat eamus eatis eant erem eres eret eremus eretis erent e ete eto etote ento ere"),
    "V2P": _e("eor eris ere etur emur emini entur ebar ebaris ebare ebatur ebamur ebamini ebantur ebor eberis "
              "ebere ebitur ebimur ebimini ebuntur ear earis eare eatur eamur eamini eantur erer ereris erere "
              "eretur eremur eremini erentur eri etor entor"),
    "V2N": _e("ens entis enti entem ente entes entium entibus entia endi endo endum endus enda endae endam "
              "endos endas endis endorum endarum"),
    "V3A": _e("o is it imus itis unt ebam ebas ebat ebamus ebatis ebant am es et emus etis ent as at amus "
              "atis ant erem eres eret eremus eretis erent e ite ito itote unto ere"),
    "V3P": _e("or eris ere itur imur imini untur ebar ebaris ebare ebatur ebamur ebamini ebantur ar etur emur "
              "emini entur aris are atur amur amini antur erer ereris erere eretur eremur eremini erentur i "
              "itor untor"),
    "V3IA": _e("io is it imus itis iunt iebam iebas iebat iebamus iebatis iebant iam ies iet iemus ietis ient "
               "ias iat iamus iatis iant erem eres eret eremus eretis erent e ite ito itote iunto ere"),
    "V3IP": _e("ior eris ere itur imur imini iuntur iebar iebaris iebare iebatur iebamur iebamini iebantur iar "
               "ieris iere ietur iemur iemini ientur iaris iare iatur iamur iamini iantur erer ereris erere "
               "eretur eremur eremini erentur i itor iuntor"),
    "V4A": _e("io is it imus itis iunt iebam iebas iebat iebamus iebatis iebant iam ies iet iemus ietis ient "
              "ias iat iamus iatis iant irem ires iret iremus iretis irent i ite ito itote iunto ire "
              "ibo ibis ibit ibimus ibitis ibunt"),
    "V4P": _e("ior iris ire itur imur imini iuntur iebar iebaris iebare iebatur iebamur iebamini iebantur iar "
              "ieris iere ietur iemur iemini ientur iaris iare iatur iamur iamini iantur irer ireris irere "
              "iretur iremur iremini irentur iri itor iuntor"),
    "V3IN": _e("iens ientis ienti ientem iente ientes ientium ientibus ientia iendi iendo iendum iendus ienda "
               "iendae iendam iendos iendas iendis iendorum iendarum"),
    # verbs: perfect system, participles
    "VPF": _e("i isti it imus istis erunt ere eram eras erat eramus eratis erant ero eris erit erimus eritis "
              "erint erim issem isses isset issemus issetis issent isse"),
    "VSY": _e("sti stis runt sse ssem sses sset ssemus ssetis ssent "
              "ram ras rat ramus ratis rant ro ris rit rimus ritis rint"),   # amasti, audisti, cognosse, imperarat
    "VPP": _e(_A12 + " u"),                       # perfect passive participle + supine
    "VFP": _e(_A12),                              # future active participle (stem ends in -ur)
    "VIMP2": _e("et ebat ebit eat eret ere uit uerat uerit uisset uisse "
                "ent ebant ebunt eant erent uerunt uerant uerint uissent"),
    "VSUP": _e("um u"),                           # supine only (intransitive verbs)
}

_PRES_CODES = {"1": ("V1A", "V1P", "V1N"), "2": ("V2A", "V2P", "V2N"), "3": ("V3A", "V3P", "V2N"),
               "3i": ("V3IA", "V3IP", "V3IN"), "4": ("V4A", "V4P", "V3IN")}

# paradigm code -> family used to normalise slot likelihoods (verbs: every code -> 'V')
_FAMILY = {"N1": "N1", "N1GA": "N1", "N1GE": "N1", "N1PL": "N1", "N2": "N2", "N2IUS": "N2", "N2R": "N2",
           "N2PLM": "N2", "N2N": "N2N", "N2PLN": "N2N", "N3": "N3", "N3I": "N3", "N3IM": "N3", "N3PL": "N3",
           "N3N": "N3N", "N3NI": "N3N", "N3PLN": "N3N", "N4": "N4", "N4N": "N4", "N5": "N5", "A12": "ADJ",
           "A12R": "ADJ", "A12PL": "ADJ", "A3": "ADJ", "A31I": "ADJ", "A31C": "ADJ", "CMP": "ADJ"}

# Words of these POS (and forms of sum) are not content words.
_NONCONTENT_POS = {"CONJ", "PREP", "PRON", "PART", "ART"}

# Members that a compound's root never is (prepositions / prefixes / adverbs used in composition).
_COMPOUND_PREFIXES = {
    "a", "ab", "abs", "ad", "ambi", "amb", "an", "ante", "circum", "cis", "co", "com", "con", "contra", "de",
    "di", "dis", "e", "ex", "extra", "in", "indu", "infra", "inter", "intra", "intro", "juxta", "iuxta", "ne",
    "nec", "ob", "per", "por", "post", "prae", "praeter", "pro", "prod", "re", "red", "retro", "se", "sed",
    "sub", "subter", "super", "supra", "trans", "tra", "ultra", "ve", "bene", "male", "satis", "semi", "non",
}
# Enclitics and indefinite suffixes, never the root of a compound: quis-que, uter-que, ubi-que, qui-cumque,
# quam-vis (vis = 'you will', from volo, not vis 'force'), qui-libet, quis-piam, qui-dam
_COMPOUND_SUFFIXES = {"que", "cumque", "cunque", "uis", "libet", "piam", "dam", "nam", "quam", "met", "pte", "ce",
                      "ne", "ue"}


# ---------------------------------------------------------------------------
# 1.  Lewis & Short parsing
# ---------------------------------------------------------------------------

_ENTRY_RE = re.compile(r"<entryFree\b.*?</entryFree>", re.S)
_LABEL_START = ("gen.", "dat.", "acc.", "abl.", "nom.", "voc.", "perf.", "fut.", "pres.", "imp.", "inf.", "part.",
                "pass.", "subj.", "comp.", "sup.", "plur", "sing", "in gen", "lit.", "trop.", "absol", "constr",
                "dep.", "act.", "adv.", "praes", "tempp", "fin.", "init.", "id.", "masc", "fem", "neutr", "neut",
                "sync", "contr", "old ", "arch", "esp.", "sc.", "q. v", "i. e", "v. ", "with ", "in the ",
                "transf", "poet", "class", "post-", "ante-", "of ", "freq", "rare", "late", "eccl")


def _ls_signature(path: Path) -> List[int]:
    st = path.stat()
    return [int(st.st_size), int(st.st_mtime_ns)]


_LABEL_WORDS = {"gen", "dat", "acc", "abl", "nom", "voc", "perf", "fut", "pres", "imp", "imperf", "inf", "part",
                "pass", "subj", "comp", "sup", "plur", "sing", "init", "fin", "lit", "trop", "absol", "constr",
                "dep", "act", "adv", "praes", "tempp", "id", "ib", "masc", "fem", "neutr", "neut", "sync", "contr",
                "arch", "esp", "sc", "subst", "comm", "obsol", "heterocl", "pron", "poss", "num", "adj", "indecl",
                "distr", "card", "ordin", "conj", "prep", "interj", "transf", "med", "fig", "al", "dub", "etym",
                "inch", "freq", "desid", "impers", "rel", "interrog", "demonstr", "indef", "gr", "lat", "cf", "v",
                "q", "fem", "plur", "sq", "sqq", "init", "acc", "orig", "pf", "pp"}


# Grammar labels that L&S prints in italics ('imper.', 'futur.', 'pluperf. subj.', 'N. cr.', 'Absol.') and
# Latin fragments it italicises ('-unt'): never a gloss.
_GRAMMAR_LABELS = _LABEL_WORDS | {
    "imper", "imperat", "futur", "pluperf", "praet", "indic", "n", "cr", "unt", "neutr", "absol", "constr", "prop",
    "orig", "abstr", "concr", "poet", "class", "eccl", "late", "post", "ante", "old", "form", "forms", "dim", "pr",
    "act", "pers", "sync", "contr", "syn", "opp", "ellipt", "intr", "trans", "intrans", "dep", "deponent",
    "absolute", "plural", "singular", "dual", "nomin", "accus", "ablat", "dat", "genit", "voc", "fin", "init",
    "subst", "subj", "inf", "part", "perf", "pres", "fut", "pass", "comp", "sup", "adv", "adj", "m", "f", "c",
    "esp", "lit", "trop", "transf", "med", "fig", "sq", "sqq", "al", "etc", "saep", "q", "v", "i", "e", "s",
    "cf", "id", "ib", "ibid", "abl", "acc", "gen", "nom", "sing", "plur", "num", "pron", "conj", "prep",
    "interj", "impers", "freq", "inch", "desid", "rel", "interrog", "demonstr", "indef", "praep", "ad", "h", "l",
    "posit", "substt", "adverbs", "advv", "prepp", "adjj", "verbs", "substantives", "nouns", "pronouns", "clause",
    "intens",
}
# English glosses of three letters or fewer (anything else that short is a label or a Latin ending)
_SHORT_ENGLISH = {
    "ox", "sea", "sun", "law", "war", "god", "day", "man", "eye", "ear", "arm", "leg", "son", "sin", "lot", "way",
    "joy", "age", "air", "oil", "fig", "sky", "sow", "pig", "dog", "bee", "fly", "egg", "bow", "gem", "ice",
    "ivy", "jar", "key", "lip", "net", "oak", "owl", "pan", "pit", "rod", "rye", "saw", "toe", "tub", "urn",
    "wax", "yew", "yes", "not", "now", "new", "old", "few", "all", "any", "why", "how", "who", "bad", "big",
    "dry", "raw", "red", "wet", "to", "go", "do", "ah", "oh", "lo", "by", "on", "up", "so", "if", "or", "no",
    "we", "ye", "he", "it", "me", "us", "my", "cow", "cup", "ram", "ass", "bed", "box", "cap", "cub", "den",
    "ewe", "far", "fat", "fir", "fox", "gut", "hat", "hay", "hen", "hip", "hut", "jaw", "kid", "lap", "low",
    "mad", "mud", "nut", "pea", "pen", "pot", "rag", "rat", "rib", "rot", "rub", "rug", "run", "sad", "sap",
    "set", "sly", "sob", "sty", "tax", "tie", "tin", "top", "toy", "vat", "vow", "wit", "yet", "foe", "kin",
    "lie", "die", "dig", "eat", "fix", "get", "lay", "let", "put", "say", "see", "sit", "cut", "hit", "hew",
    "mix", "mow", "own", "pay", "pry", "row", "sew", "sow", "tug", "win", "woo", "yoke", "one", "two", "six",
    "ten", "her", "his", "its", "our", "you", "too", "out", "off", "yea", "nay", "fie", "aye",
}
_CONNECTOR = re.compile(r"[\s,;]*(?:(?:or|and|or\s+of|i\.\s*e\.|=)\s*)?[\s,;]*|['’]")
_DANGLING = re.compile(r"\s+(?:of(?:\s+an?|\s+the)?|an?|the|to|with|in|for|or|and|by|on|at|from)\s*$", re.I)
_GLUE_WORDS = re.compile(r"\s*[A-Za-z'’\-]+(?:\s+[A-Za-z'’\-]+)?\s*")
_AUTHOR_ABBR = re.compile(r"[A-Z][a-z]{0,3}\.")


def _is_label(raw: str) -> bool:
    """An italic L&S string that is a grammar label, a speaker/author abbreviation or a Latin ending."""
    txt = re.sub(r"\s+", " ", raw).strip()
    core = txt.strip(" ,.;:—-()[]")
    if len(core) < 2 or len(core) > 90 or txt.startswith("-") or _AUTHOR_ABBR.fullmatch(txt):
        return True
    low = core.lower()
    if low.startswith(_LABEL_START):
        return True
    words = re.findall(r"[a-z]+", low)
    if not words or all(w in _GRAMMAR_LABELS for w in words):
        return True
    if re.search(r"\b(abl|acc|gen|dat|nom|voc|sing|plur|perf|pluperf|fut|futur|inf|part|subj|pass|imper|comp|sup|"
                 r"num|adj|pron|subst|comm|distr|neutr|absol|indic|intens)\.|\b(?:first|second|third)\s+pers\b",
                 txt.lower()):
        return True
    if len(words) == 1 and len(words[0]) <= 3 and words[0] not in _SHORT_ENGLISH:
        return True
    return False


def _walk(el: ET.Element, first_orth: List[bool]):
    """Document-order events of an L&S entry: ('t', text), ('i', italic text), ('q',) for a quotation,
    ('s', level) at a sense, ('o', bare form, boundary?) at an inner headword (a derived word)."""
    if el.text:
        yield ("t", el.text)
    kids = list(el)
    for k, ch in enumerate(kids):
        tag = ch.tag
        if tag == "hi" and ch.get("rend") == "ital":
            yield ("i", "".join(ch.itertext()))
        elif tag in ("cit", "quote", "bibl"):
            # a quotation ends the head of the sense; brackets inside citations still count for nesting
            yield ("q" if tag != "bibl" else "b", "".join(ch.itertext()))
        elif tag == "sense":
            yield ("s", int(ch.get("level") or 1))
            yield from _walk(ch, first_orth)
        elif tag == "orth":
            if first_orth[0]:
                first_orth[0] = False
            else:
                nxt = [c.tag for c in kids[k + 1:k + 4]]
                yield ("o", _plain("".join(ch.itertext())).replace("-", ""), bool({"itype", "gen", "pos"} & set(nxt)))
        else:
            yield from _walk(ch, first_orth)
        if ch.tail:
            yield ("t", ch.tail)


def _entry_glosses(x: ET.Element) -> Tuple[List[List], List[List]]:
    """English renderings of an L&S entry, in order: ``runs`` = [[sense level, text], ...] for the headword
    (only renderings at the head of a sense: before any quotation and outside parentheses; consecutive
    italics joined when only ', ' / 'or' / 'and' separates them) and ``subs`` = [[bare form, runs], ...]
    for the derived words that L&S describes inside the entry ('Hence, sanc-tus, a, um, P. a., ...')."""
    runs: List[List] = []
    subs: List[List] = []
    target = runs
    level = 0
    sense_no = 0
    quoted = False
    depth = 0
    cur: List[str] = []
    gap = ""
    recent = ""
    vulg: Set[int] = set()

    def dangling() -> bool:            # 'privileges of a' + plain 'Roman' + 'citizen'
        return bool(cur) and bool(_DANGLING.search(cur[-1]))

    def close():
        nonlocal cur, gap
        if cur:
            text = re.sub(r"\s+", " ", "".join(cur)).strip(" ,;:.—-")
            text = _DANGLING.sub("", text).strip(" ,;:.—-")
            if text:
                target.append([level, text, sense_no])
        cur, gap = [], ""

    for ev in _walk(x, [True]):
        kind = ev[0]
        if kind == "t":
            t = ev[1]
            if cur:
                gap += t
                if not (_CONNECTOR.fullmatch(gap) or (dangling() and _GLUE_WORDS.fullmatch(gap))):
                    close()
            depth = max(0, depth + t.count("(") + t.count("[") - t.count(")") - t.count("]"))
        elif kind == "i":
            raw = ev[1]
            if _is_label(raw) or depth > 0 or quoted:
                close()
                continue
            if cur and (_CONNECTOR.fullmatch(gap) or (dangling() and _GLUE_WORDS.fullmatch(gap))):
                # two italics with nothing between them are two renderings ('spread out' + 'extend'), not one word
                cur.append(re.sub(r"\s+", " ", gap) if gap.strip(" ") else (gap or ", "))
                cur.append(raw)
                gap = ""
            else:
                close()
                cur = [raw]
        elif kind in ("q", "b"):
            close()
            t = ev[1]
            depth = max(0, depth + t.count("(") + t.count("[") - t.count(")") - t.count("]"))
            if kind == "q":
                quoted = True
        elif kind == "s":
            close()
            level, quoted, depth = ev[1], False, 0
            sense_no += 1
        elif kind == "o":
            # a derived word ('Hence, sanc-tus, a, um, P. a.') starts a section of its own; another spelling
            # at the head of the entry ('rĕ-verto and rĕ-vertor', 'quattŭor, less correctly quātŭor') does not
            if ev[2] and depth == 0 and ev[1] and (sense_no > 0 or re.search(r"(?:—|Hence|derivv?\.?)\s*$", recent)):
                close()
                subs.append([_b(ev[1]), []])
                target = subs[-1][1]
        if kind in ("t", "b"):
            recent = (recent + ev[1])[-40:]
        if kind in ("t", "b", "q") and "Vulg" in ev[1]:
            vulg.add(sense_no)                     # this sense is cited from the Vulgate (19 Nov 2026)
    close()
    for run in runs:
        run.append(run[2] in vulg)
    for _sb, sruns in subs:
        for run in sruns:
            run.append(run[2] in vulg)
    return runs[:10], [s for s in subs if s[1]][:12]


_MORPH_WORD = re.compile(r"^(?:[A-Za-zÀ-ɏ\u0300-\u036f^\-]+|[1-4])$")
_GENDER_LABEL = re.compile(r"^(m|f|n|c|comm|com|masc|fem|neutr)\.(?:\s|$|,)")
_POS_LABEL = re.compile(r"^(?:(?:temp|rel|interrog|demonstr|indef|card|ordin|distrib|poss|pers|dem)\.\s*)*"
                        r"(v\.\s*(?:a|n|dep|freq|inch|desid|intens|impers|defect)\b|adj\b|adv\b|prep\b|conj\b|"
                        r"interj\b|pron\b|num\b|P\.\s*a\.|subst\b|indecl\b|part\b)", re.I)
_PART_GENDER = re.compile(r"^([A-Za-zÀ-ɏ\u0300-\u036f^]{1,8})\.?\s+(m|f|n|c|comm)\.(?:\s|$)")
_PART_POS = re.compile(r"^([A-Za-zÀ-ɏ\u0300-\u036f^]{1,8})\.\s+(.+)$")
_PROSE_HEAD_SEG = re.compile(
    r"^(?:no\s+(?:perf|sup)\.?|perf\.\s+wanting|sup\.\s+wanting|"
    r"(?:and\s+|or\s+)?(?:in\s+late\s+lat\.|old\s+form\b|arch\.|also\s+written\b|less\s+freq\.|"
    r"more\s+freq\.|less\s+correctly\b|acc\.\s+to\b|sync\.|contr\.|separated\b))", re.I)


def _head_morph(lead: str) -> dict:
    """Principal parts / genitive / gender / POS from the plain text that follows the headword:
    'pōno, pŏsŭi, pŏsĭtum, 3, v. a. ...' -> parts ['pŏsŭi', 'pŏsĭtum', '3'], pos 'v. a.'."""
    t = re.sub(r"\[[^\[\]]*\]", " ", lead)
    # OCR period directly after headword before endings ('mūsĭcus. a, um, adj.'), missing comma before 'a, um'
    # ('ĭn-ăquōsus a, um, adj.', 'sescentēsĭmus a, um'), or OCR period before conjugation digit ('rĕ-vĕrĕor, ĭtus. 2,')
    t = re.sub(r"^([A-Za-zÀ-ɏ\u0300-\u036f^\-]+)\.\s+(?=(?:a|ae|i|is|e|um|us|o|1|2|3|4)\b)", r"\1, ", t)
    t = re.sub(r"^([A-Za-zÀ-ɏ\u0300-\u036f^\-]+)\s+(?=a,\s*um\b)", r"\1, ", t)
    t = re.sub(r"\.\s+([1-4])\s*,", r", \1,", t)
    segs = re.split(r"[,;:]", t)
    parts: List[str] = []
    gender = ""
    pos = ""
    indecl = False
    for k_seg, seg in enumerate(segs[1:], 1):
        s = seg.strip()
        if not s or s.lower() in ("and", "or"):
            continue
        if "indecl" in s[:16]:
            indecl = True
        if _PROSE_HEAD_SEG.match(s):
            # L&S interjects 'no perf.', 'old form ...', 'in late Lat. ...', 'less freq. parsi', 'and sync. lamna'
            # before the principal parts / genitive (elevo, propheto, tribulo, dispergo, dissipo, manifestus, parco, lamina)
            continue
        if re.match(r"^(?:and|or)\s+(?:another\s+orthography\s+)?[A-Za-zÀ-ɏ\u0300-\u036f^\-]+$", s, re.I) and \
                not parts and k_seg + 1 < len(segs):
            # 'ĕburnĕus, and ĕbur-nus, a, um, adj.', 'cŏĭtus, and another orthography coetus , ūs , m.'
            nxt_s = segs[k_seg + 1].strip()
            if _MORPH_WORD.match(nxt_s) or _GENDER_LABEL.match(nxt_s) or _POS_LABEL.match(nxt_s):
                continue
        mpg = None if _POS_LABEL.match(s) else _PART_GENDER.match(s)     # OCR form 'ae. f.' / 'i. n.'
        if mpg:
            parts.append(mpg.group(1))
            gender = gender or mpg.group(2)[0]
            break
        mpp = None if _POS_LABEL.match(s) else _PART_POS.match(s)        # 'um. adj.' (manifestus)
        if mpp and _POS_LABEL.match(mpp.group(2).strip()):
            parts.append(mpp.group(1))
            pos = pos or mpp.group(2).strip()[:24]
            break
        mg = _GENDER_LABEL.match(s)
        if mg:
            gender = gender or mg.group(1)[0]
            rest = s[mg.end():].strip()
            if rest and _POS_LABEL.match(rest):
                pos = pos or rest[:24]
            if rest:
                break
            continue
        if _POS_LABEL.match(s):
            pos = pos or s[:24]
            if "indecl" in s:
                indecl = True
            break
        words = [w for w in re.split(r"\s+", s) if w and w not in ("and", "or")]
        if words and all(_MORPH_WORD.match(w) for w in words) and len(words) <= 3:
            parts.extend(words)
            continue
        if words and _MORPH_WORD.match(words[0]) and len(words) > 1 and re.match(r"\d\.", words[1]):
            parts.append(words[0])            # 'um 2. alius. Adj.' -> 'um'
        break
    return {"parts": parts, "gender": gender, "pos": pos, "indecl": indecl}


def _extract_sub_entries(x: ET.Element) -> List[list]:
    """Structured L&S sub-headwords inside <sense> (e.g. 'cilicium, ii, n.' inside Cilicia; 'baptismus, i, m.'
    inside baptisma; 'Hebraeus / Hebraicus / Hebraice' inside Hebraei; 'Leviticus' inside Levites;
    'beneplacitum, i, n.' inside beneplaceo; 'aperte, adv.' inside aperio; 'abundanter' inside abundo)."""
    out: List[list] = []
    seen: Set[str] = set()
    for s in x.iter("sense"):
        kids = list(s)
        for k, ch in enumerate(kids):
            if ch.tag != "orth":
                continue
            raw_h = "".join(ch.itertext()).strip()
            if not raw_h or raw_h.startswith("-") or raw_h.endswith("-"):
                continue
            pl = _plain(raw_h).replace("-", "")
            if len(pl) < 4:
                continue
            hb = _b(pl)
            if not hb or hb in seen:
                continue
            itypes: List[str] = []
            gen = ""
            pos = ""
            hi_gloss: List[str] = []
            for j in range(k + 1, min(len(kids), k + 7)):
                nk = kids[j]
                if nk.tag in ("orth", "cit", "quote", "sense"):
                    break
                if nk.tag == "cb":
                    continue
                txt = re.sub(r"\s+", " ", "".join(nk.itertext())).strip()
                if nk.tag == "itype":
                    if txt and txt.lower() not in ("and", "or"):
                        itypes.append(txt)
                elif nk.tag == "gen" and not gen:
                    gen = txt
                elif nk.tag == "pos" and not pos:
                    pos = txt
                elif nk.tag == "hi" and nk.get("rend") == "ital":
                    if not pos and re.match(r"^(?:adj|adv)\b", txt, re.I):
                        pos = txt.split(",")[0].strip()
                        rest_g = txt.split(",", 1)[1].strip() if "," in txt else ""
                        if rest_g and not _is_label(rest_g):
                            hi_gloss.append(rest_g)
                    elif not _is_label(txt) and len(hi_gloss) < 2:
                        hi_gloss.append(txt)
            parts: List[str] = []
            for it in itypes:
                for p in re.split(r"[,;]+|\s+(?:and|or)\s+", it):
                    p = p.strip()
                    if p:
                        parts.append(p)
            is_struct = bool(parts and (gen or pos or [_b(p) for p in parts[:2]] == ["a", "um"]))
            is_adv_pos = bool(pos and pos.lower().startswith("adv"))
            is_adv_suf = (not parts and not gen and not pos and (ch.tail or "").strip().startswith(",") and
                          bool(hi_gloss) and (hb.endswith("ter") or hb.endswith("ice")) and len(hb) >= 6)
            if not (is_struct or is_adv_pos or is_adv_suf):
                continue
            if is_adv_suf:
                pos = "adv."
            seen.add(hb)
            out.append([pl, parts, gen, pos, "; ".join(hi_gloss)[:80]])
    return out


def _parse_entry(raw: str) -> Optional[dict]:
    try:
        x = ET.fromstring(raw)
    except ET.ParseError:
        return None
    orths = [o for o in x if o.tag == "orth"]
    if not orths:
        return None
    full_plain = re.sub(r"\s+", " ", "".join(x.itertext()))
    lead = _strip_parens(full_plain)[:400]
    hm = _head_morph(lead)
    pos = ""
    for p in x.iter("pos"):
        t = ("".join(p.itertext())).strip()
        if t and 0 <= full_plain.find(t) < 260:
            pos = t
        break
    etym = ""
    for et in x.iter("etym"):
        t = re.sub(r"\s+", " ", "".join(et.itertext())).strip()
        if t and 0 <= full_plain.find(t[:12]) < 400:
            etym = t
        break
    bracket = ""
    m = re.search(r"\[([^\[\]]{1,80})\]", lead[:320])
    if m:
        bracket = m.group(1).strip()
    glosses = _entry_glosses(x)
    alts = ["".join(o.itertext()) for o in orths[1:] if "".join(o.itertext()).strip()]
    # L&S prints '-ens or -es' numeral adverbs ('quotiens or quoties', 'quinquiens or quinquies', 'centiens or
    # centies', 'quotienscumque or quotiescumque') and '-cius or -tius' ('empticius or -tius')
    head_txt = "".join(orths[0].itertext())
    hb0 = _b(_plain(head_txt).replace("-", ""))
    if hb0.endswith("iens") and re.search(r"\bor\s+[^,;.]{3,20}es\b", lead[:90]):
        alts.append(hb0[:-4] + "ies")
    elif hb0.endswith("ienscumque") and re.search(r"\bor\s+[^,;.]{3,24}escumque\b", lead[:90]):
        alts.append(hb0[:-10] + "iescumque")
    elif hb0.endswith("icius") and re.search(r"\bor\s+-t[iĭī]us\b", lead[:90]):
        alts.append(hb0[:-5] + "itius")
    return {
        "key": x.get("key") or "",
        "n": x.get("n") or "",
        "type": x.get("type") or "",
        "head": head_txt,
        "alts": alts,
        "itype": [re.sub(r"\s+", " ", "".join(o.itertext())).strip() for o in x if o.tag == "itype"],
        "gen": [("".join(o.itertext())).strip() for o in x if o.tag == "gen"],
        "pos": pos,
        "mparts": hm["parts"],
        "mgen": hm["gender"],
        "mpos": hm["pos"],
        "mindecl": hm["indecl"],
        "mood": [("".join(o.itertext())).strip() for o in x if o.tag == "mood"],
        "etym": etym,
        "bracket": bracket,
        "lead": lead[:300],
        "gloss": glosses[0],
        "sub": glosses[1],
        "sub_entries": _extract_sub_entries(x),
        "size": len(raw),
    }


# Latin construction words that L&S italicises inside renderings ('aliquem aliquid', 'alicui') and grammar
# phrases that are not glosses ('advv. of place', 'object-clause', 'without a prep.', 'supin.', 'plqpf.')
_LATIN_FRAGMENTS = {"aliquem", "aliquid", "alicui", "alicuius", "aliquo", "aliqua", "aliquam", "aliquos", "aliquas",
                    "aliquorum", "aliquibus", "aliqui", "rem", "rei", "re", "se", "sibi", "sese", "quid", "quod",
                    "quo", "ut", "ne", "cum", "de", "ex", "ab", "ad", "in", "inf", "infin", "supin", "plqpf",
                    "gerundive", "gerund", "finit", "depon", "advv", "adjectives", "clauses", "piur", "synaeresin",
                    "temp", "prepp", "prep", "verb"}
_LABEL_PHRASES = re.compile(r"\b(?:object-clause|objective clause|without a prep\.?|local adverbs?|advv?\.?,? of place|"
                            r"verb,? finit\.?|per synaeresin|temp\.?,? adv\.?|absol\.?|with acc\.?|with dat\.?|"
                            r"with abl\.?|with gen\.?|with inf\.?)", re.I)
_NON_LATIN_SCRIPT = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff\u0590-\u05ff]")


def _drop_dangling(text: str) -> str:
    """Cut words left dangling at the end of a shortened rendering ('principal author of the')."""
    t = text.strip(" ,;:")
    for _k in range(4):
        n = _DANGLING.sub("", t).strip(" ,;:")
        if n == t:
            break
        t = n
    return t


def _compose_gloss(runs: List, latin_heads: Set[str], proper: bool = False, cap: int = 60) -> str:
    """A short gloss from an entry's renderings: the first rendering (up to three of its comma items) and,
    within ``cap`` characters, the first one or two items of the next main senses (L&S levels I/II and A/B),
    e.g. facies -> 'make, form, configuration; face, visage; external form, look'.  Renderings made only of
    Latin words (L&S italicises some Latin: 'ut', 'aliquid alicui') are skipped."""
    def norm(s: str) -> str:
        return re.sub(r"^(?:a|an|the|to)\s+", "", s.lower())

    def latinish(words: List[str]) -> bool:
        return bool(words) and all(w in latin_heads or w in _GRAMMAR_LABELS or w in _LATIN_FRAGMENTS for w in words)

    if not proper and any(len(r) > 3 and r[3] for r in runs) and not (len(runs[0]) > 3 and runs[0][3]):
        # the entry's first sense is classical, a later one is cited from the Vulgate: the biblical sense leads
        # (apostolus 'a notice sent to a higher tribunal' -> 'an Apostle'), 19 Nov 2026
        heads: Set[int] = set()
        firsts = []
        for r in runs:                   # only the head rendering of a sense, not a phrase inside it ('at the barriers')
            if len(r) > 2 and r[2] not in heads:
                heads.add(r[2])
                firsts.append(r)
        vr = [r for r in firsts if len(r) > 3 and r[3] and r[0] <= 2 and
              not latinish([_ab(w) for w in _ASCII_WORD.findall(r[1])]) and
              not re.match(r"(?i)(?:at|in|on|by|from|of|with|for|into|leaps|flows)\b", r[1].strip())]
        if vr:
            runs = [vr[0]] + [r for r in runs if r is not vr[0]]
    parts: List[str] = []
    used: Set[str] = set()
    senses: Set[int] = set()
    for run in runs:
        level, text = run[0], _LABEL_PHRASES.sub(" ", run[1])
        sense = run[2] if len(run) > 2 else -1
        ws = [_ab(w) for w in _ASCII_WORD.findall(text)]
        if not ws or all(w in _GRAMMAR_LABELS for w in ws) or (not proper and latinish(ws)):
            continue
        if parts and (level > 2 or sense in senses):
            continue                     # later parts: the head rendering of another main sense only
        first = norm(re.split(r"\s*[,;]\s*", text)[0].strip(" .:"))
        if parts and any(first == u or first.startswith(u + " ") for u in used):
            continue                     # 'a son' ... 'a son of mother earth'
        senses.add(sense)
        items = []
        for it in re.split(r"\s*[,;]\s*|\.\s+", text):
            it = re.sub(r"\s+-\s+", "-", re.sub(r"\s+", " ", it)).strip(" .:—-")
            if _NON_LATIN_SCRIPT.search(it):
                continue                 # a Greek etymology ('often referred to τίω, τιμάω')
            if len(it) > 45:
                it = it[:45].rsplit(" ", 1)[0]
            it = _drop_dangling(it)
            if it and not proper and it[:1].isupper() and \
                    (it.split(" ")[0] in ("To", "A", "An", "The", "In", "Of", "With") or it[1:].islower()):
                it = it[0].lower() + it[1:]
            iw = [_ab(w) for w in _ASCII_WORD.findall(it)]
            if not proper and iw and latinish(iw):
                continue                 # a Latin word inside the rendering ('aliquid; to fill')
            if not proper and len(iw) > 1 and iw[0].startswith("ali") and iw[0] in _LATIN_FRAGMENTS and                     not latinish(iw[1:2]):
                it = it.split(" ", 1)[1]  # 'aliquem to ask' -> 'to ask' 
            if it and norm(it) not in used and len(re.findall(r"[a-z]", it.lower())) >= 2 and                     it.lower() not in ("or", "and", "of", "the", "to", "an", "with", "by", "for"):
                items.append(it)
                used.add(norm(it))
        if not items:
            continue
        part = ", ".join(items[: (3 if not parts else 2)])
        if parts and len("; ".join(parts + [part])) > cap:
            break
        parts.append(part)
        if len(parts) >= 3:
            break
    return _drop_dangling("; ".join(parts))


_LEAD_ANCHOR = re.compile(r"(?:\b(?:m|f|n|c|comm|adj|adv|prep|conj|interj|indecl|P\.\s*a|v\.\s*(?:a|n|dep|freq|"
                          r"inch|desid|intens|impers)(?:\.?\s+and\s+[an])?)\.)")
_ETYM_LEAD_WORDS = {"of", "from", "for", "v", "q", "cf", "=", "sc", "and", "or", "in", "with", "etc", "id", "sanscr",
                    "gr", "germ", "engl", "root", "perh", "prob", "contr", "kindr", "dim", "freq", "inch", "comp",
                    "sup", "init", "fin", "osc", "umbr", "goth", "lith", "ir", "fr", "it", "span", "zend", "slav",
                    "o", "h", "lat", "old", "kindred", "akin", "etym", "dub", "same", "orig", "hence"}


def _lead_gloss(lead: str, is_latin, proper: bool = False) -> str:
    """Plain-text rendering after the head of an entry whose meaning L&S does not italicise ('Ēlīās, ae, and
    Elia, ae, m., Elijah, a prophet of the Jews: form Elias ...' -> 'Elijah, a prophet of the Jews';
    'prŏphēta, ae, m., = προφήτης, a foreteller, soothsayer, prophet' -> 'a foreteller, soothsayer, prophet')."""
    t = re.sub(r"\[[^\[\]]*\]", " ", _strip_parens(lead))
    anchors = list(_LEAD_ANCHOR.finditer(t[:220]))
    if not anchors:
        return ""
    last = anchors[0]
    for a in anchors[1:]:                 # the run of head labels ('m. indecl.'), not 'adv.' in a citation
        if a.start() - last.end() > 25:
            break
        last = a
    t = t[last.end():]
    # the first clause after the head that reads as an English rendering ('frux, f. from the root FRUG;
    # v. fruor, fruits of the earth' -> 'fruits of the earth'; 'jūro, ..., v. dep. 2. jus, to swear')
    segs = re.split(r"[:;]|\.\s(?=[A-Z])|—|\s(?:cf|Vulg|Liv|Cic|Plin|Mel|Ov|Verg|Hor|Tac|Caes|Just|Nep|Suet|Plaut|Ter|"
                    r"Lucr|Quint|Sen|Sall|Varr|Col|Gell|Hier|Aug|Tert|Lact|Inscr|Prud|Sid|App|Mart|Juv|Stat|Sil|Luc)\.",
                    t)
    for seg in segs[:3]:
        if re.match(r"^[\s,.]*[^\x00-ɏ]", seg):
            continue                                               # a Greek (etymological) clause
        s = seg
        for _k in range(4):
            s = re.sub(r"^[\s,.]*(?:=\s*[^\s,]+(?:\s+[^\s,]+)?\s*,?\s*)?", "", s)           # '= προφήτης,'
            s = re.sub(r"^[\s,]*(?:[^\x00-ɏ]+[\s,]*)+", "", s)                       # Greek words
            s = re.sub(r"^[\s,]*or\s+[^\s,]+\s*,", "", s)                                # 'or -vīdis ,'
            s = re.sub(r"^[\s,]*(?:\d\.\s*)?(?:v\.\s*(?:\d\.\s*)?)?[A-Za-zĀ-ſ\-]+\s*,(?=\s*[a-z])", "",
                       s) if re.match(r"^[\s,]*(?:\d\.|v\.)", s) else s                 # '2. jus,' / 'v. fruor,'
            s = re.sub(r"^[\s,]*(?:Lit|Prop|Orig|In gen|Act|Neutr|Transf|Abstr|Concr)\.?,?\s+", "", s)
        s = re.sub(r"\s+", " ", s).strip(" ,.")
        m = re.match(r"^([A-Za-zĀ-ſ\u0300-\u036f]+)\s*,\s*(.+)$", s)
        if m and not proper and is_latin(_ab(_plain(m.group(1)))) and m.group(1)[:1].islower():
            s = m.group(2)                    # 'dē-sĭlĭo, ..., v. n. salio, to leap down': the source word goes
        if len(s) > 60:
            s = _drop_dangling(s[:60].rsplit(" ", 1)[0].rstrip(" ,"))
        first = (s.split(" ")[0] if s else "").lower().rstrip(".,")
        if first in _ETYM_LEAD_WORDS or first[:1].isdigit() or re.search(r"\d|\b(?:fin|init)\b|\bv\.\s", s):
            continue                                               # a cross-reference, etymology or citation
        ws = [_ab(w) for w in _ASCII_WORD.findall(s)]
        if len(s) < 3 or not ws or all(w in _GRAMMAR_LABELS for w in ws):
            continue
        if not proper and sum(1 for w in ws if is_latin(w)) * 2 >= len(ws):   # mostly Latin: a citation
            continue
        return s
    return ""


def _parse_ls(path: Path) -> List[dict]:
    data = path.read_text(encoding="utf-8")
    out = []
    for raw in _ENTRY_RE.findall(data):
        e = _parse_entry(raw)
        if e:
            out.append(e)
    return out


# ---------------------------------------------------------------------------
# 2.  Paradigms
# ---------------------------------------------------------------------------

def _rime_cut(hb: str) -> str:
    """Drop the last vowel and the consonants after it (caput -> cap, sermo -> serm)."""
    m = re.search(r"[aeiouy][^aeiouy]*$", hb)
    return hb[: m.start()] if m else hb


def _attach_gen(hb: str, tail: str) -> Optional[str]:
    """Full genitive from L&S's abbreviated itype: caput + itis -> capitis, princeps + cipis -> principis."""
    t = _b(tail)
    if not t or not hb:
        return None
    if t[0] in _VOW:
        if t[0] == hb[0] and len(t) > len(hb):
            return t
        base = _rime_cut(hb)
        # the stem already ends in the tail's stem (luminare + aris -> luminar|is, cubile + ilis -> cubil|is;
        # restricted to -e nouns so soror + oris still yields sororis, not soris)
        if hb.endswith("e") and t.endswith("is") and len(t) >= 4 and base.endswith(t[:-2]):
            return base + "is"
        # the stem already ends in the tail's first vowel: aries + ietis -> ar|ietis (not 'ariietis'),
        # paries + ietis -> parietis, abies + ietis -> abietis
        if len(t) >= 3 and base.endswith(t[0]) and t[1] in _VOW and len(base) >= 2:
            base = base[:-1]
        return base + t
    if t[:2] == hb[:2] and len(t) >= len(hb) - 1:
        return t                                        # full genitive: rex, regis; caro, carnis
    i = hb.rfind(t[0])
    if i <= 0:
        if hb.endswith(("s", "x")) and len(hb) >= 3:      # mons, tis -> montis; pars, tis -> partis
            return hb[:-1] + t
        return None
    return hb[:i] + t


_STD_VERB_TAILS = {"aui", "eui", "iui", "ii", "ui", "atum", "etum", "itum", "utum", "atus", "itus", "utus",
                   "aturus", "iturus", "uturus"}


def _attach_part(hb: str, w: str, t: str, prefix: str, cut: Optional[int]) -> Tuple[Optional[str], Optional[int]]:
    """A full principal part from L&S's abbreviation.  ``w`` = headword without its personal ending
    (dic-o -> dic, mon-eo -> mon, audi-o -> audi).  Returns (form, cut position used)."""
    if not t:
        return None, None
    if t[0] in _VOW:
        if t in _STD_VERB_TAILS:
            stem = w
            # inchoative -sco verbs drop -sc- (and the theme vowel before it) before perfect/supine tails:
            # quiesco -> quievi / quietum, cresco -> crevi, erubesco -> erubui, concupisco -> concupivi
            if hb.endswith("sco") and stem.endswith("sc") and len(stem) >= 4:
                stem = stem[:-2]
                if stem and stem[-1] in _VOW and (stem[-1] == t[0] or t == "ui"):
                    stem = stem[:-1]
            elif stem and stem[-1] == t[0]:
                stem = stem[:-1]
            return stem + t, None
        if prefix and hb.startswith(prefix) and len(prefix) < len(hb) - 1:
            if t.startswith(prefix) and len(t) >= len(prefix) + 3:
                return t, len(prefix)          # full form: af-ficio, affeci -> affeci (not 'affaffeci')
            # ad-imo, ēmi -> ademi; but de-spicio, exi -> despexi: the consonants that begin the simple
            # verb stay before a vowel-initial tail
            onset = re.match(r"[^aeiouy]*", hb[len(prefix):]).group(0)
            return prefix + onset + t, len(prefix) + len(onset)
        i = w.rfind(t[:2]) if len(t) >= 2 else -1
        if i > 0:                                   # aperio, erui -> aperui
            return w[:i] + t, i
        if t[0] == hb[0] and len(t) >= len(w):      # full form: offero/obtuli, aufero/abstuli, obliviscor/oblitus
            return t, None
        if len(w) >= 4 and len(t) >= 3:
            # vowel-weakened compound stems without hyphen in L&S: opprimo/oppressi, perimo/peremi,
            # abicio/abieci, conicio/conieci, immitto/immisi, officio/offeci, offringo/offregi
            rc = _rime_cut(w)
            if rc:
                return rc + t, len(rc)
        if hb[0] in _VOW:
            return t, None                          # ago, egi; emo, emi
        return None, None
    if cut is not None and t in ("sum", "tum", "sus", "tus", "xum", "xus", "ssum", "ctum"):
        # the short supine tail after the cut of the perfect: re-spondeo, di, sum -> respon|sum, dē-scendo, di,
        # sum -> descen|sum (not prefix + 'sum' = 'resum', 'desum'), 19 Nov 2026
        return hb[:cut] + t, cut
    if prefix and len(prefix) < len(hb) and hb[len(prefix)] == t[0] and \
            t not in ("si", "xi", "di", "ti", "sum", "tum", "sus", "tus"):
        return prefix + t, len(prefix)              # ac-cipio, cepi -> accepi (not di-spergo + si -> disi)
    if t[0] == hb[0] and len(t) >= 3 and len(t) >= len(w) - 1 and (t[1] == hb[1] or len(w) <= 4):
        return t, None                              # full form: misi, cepi, cecidi, posui
    if cut is not None:
        return hb[:cut] + t, cut
    # Never match t[0] inside the hyphenated prefix (ex-struo + xi must not match 'x' of 'ex-'!)
    search_start = len(prefix) if (prefix and hb.startswith(prefix) and len(prefix) < len(w)) else 0
    # Prefer a 2-letter match for >= 3-letter tails so consuesco + suevi matches 'su', not the 's' of '-sc-'
    i = w.rfind(t[:2], search_start) if len(t) >= 3 else -1
    if i <= 0:
        i = w.rfind(t[0], search_start)
    if i > 0 and (len(t) >= 3 or i >= len(w) - 2):
        return w[:i] + t, i
    base = w
    if base.endswith(("qu", "gu")):
        base = base[:-2]
    elif base.endswith("u") and t in ("xi", "ctum", "xus", "xum"):
        pass                                        # ex-struo, xi, ctum -> exstruxi, exstructum; fluo -> fluxi
    elif base and base[-1] not in _VOW:
        base = base[:-1]
    return base + t, len(base)


def _infinitive_conj(tok: str, body: str) -> Optional[str]:
    """Conjugation shown by an infinitive token of the itype ('āre', 'dăre', 'ēre', 'ĕre', 'lŏqui', 'īri')."""
    nfc = unicodedata.normalize("NFC", tok)
    tb = _b(tok)
    if len(tb) < 3 or not (body.startswith(tb[:-3]) or body.endswith(tb[:-3])):      # 'are', 'dăre' (do, circumdo)
        return None
    if tb.endswith(("are", "ari")):
        return "1"
    if tb.endswith(("ire", "iri")):
        return "4"
    if tb.endswith(("ere", "eri")):
        k = len(nfc) - 3
        ch = nfc[k] if 0 <= k < len(nfc) else ""
        if ch == "ē":
            return "2"
        if ch in ("ĕ",):
            return "3"
        return "2" if body.endswith("e") else "3"
    return None


def _verb_conjs(hb: str, parts: List[str], perfs: List[str]) -> List[str]:
    """All valid conjugations listed for the verb (primary first; e.g. 'lavo, 1 and 3' -> ['1', '3'])."""
    dep = hb.endswith("or")
    body = hb[:-2] if dep else hb[:-1]
    nums: List[str] = []
    inf: Optional[str] = None
    for p in parts:
        if re.fullmatch(r"[1-4]", p):
            if p not in nums:
                nums.append(p)
        else:
            c = _infinitive_conj(p, body)
            if c and inf is None:
                inf = c
            elif dep and _b(p) == body + "i" and inf is None:
                inf = "3"
    raw = list(nums) if nums else ([inf] if inf else [])
    if not raw:
        if any(p.endswith("aui") for p in perfs):
            raw = ["1"]
        elif body.endswith("e") and len(body) > 1:
            raw = ["2"]
        elif body.endswith("i") and any(p.endswith(("iui", "ii")) for p in perfs):
            raw = ["4"]
        elif perfs:
            raw = ["3"]         # an irregular perfect without a conjugation number: 3rd conj. (pono, posui)
    out: List[str] = []
    for c in raw:
        if c == "3" and body.endswith("i"):
            c = "3i"
        if c == "2" and not body.endswith("e"):
            continue
        if c == "4" and not body.endswith("i"):
            continue
        if c not in out:
            out.append(c)
    return out


def _verb_conj(hb: str, parts: List[str], perfs: List[str]) -> Optional[str]:
    cs = _verb_conjs(hb, parts, perfs)
    return cs[0] if cs else None


def _present_stem(hb: str, conj: str) -> Optional[str]:
    body = hb[:-2] if hb.endswith("or") else hb[:-1]
    if conj in ("1", "3"):
        return body or None
    if conj in ("2", "3i", "4"):
        return body[:-1] if len(body) > 1 else None
    return None


def _verb_parts(hb: str, parts: List[str]) -> Tuple[List[str], List[str]]:
    """Split the head tokens into (perfect tails, supine/participle tails), bare spelling."""
    perf, sup = [], []
    dep = hb.endswith("or")
    body = hb[:-2] if dep else hb[:-1]
    prev = ""
    for p in parts:
        pb = _b(p)
        if not pb or pb.isdigit() or _infinitive_conj(p, body) or (dep and pb == body + "i"):
            continue
        last, prev = prev, pb
        if pb == "sum" and perf and not last.endswith("us") and not hb.endswith("sum"):
            # 'con-verto, ti, sum, 3': the abbreviated supine (con)versum, not the verb 'sum' of a semi-deponent's
            # 'ausus sum' (before 19 Nov 2026 every '-di/-ti, sum' verb lost its participle: conversus, reversus,
            # defensus, incensus ...)
            sup.append(pb)
            continue
        if pb in ("i", "sum", "esse", "fui", "se", "ae", "a", "um", "e"):
            continue
        if pb.endswith(("um", "us")) and len(pb) >= 3:
            sup.append(pb)
        elif pb.endswith("i") and len(pb) >= 2:
            perf.append(pb)
    return perf, sup


# heads whose principal parts the L&S XML misprints so that no paradigm can be read ('mălĕdīco , xi. ctum, 3':
# a full stop for the comma), by L&S key
_HEAD_FIX = {
    "maledico": ["xi", "ctum", "3"],
    "vinculum": ["i"],
    "orior": ["ortus", "4"],        # 'ŏrĭor, ortus, fut. part. oriturus, 4': the 4 was lost (19 Nov 2026)
    "caveo": ["cāvi", "cautum", "2"],   # L&S XML prints '3' after '(2d pers. sing. ...)'
    "crucifigo": ["xi", "xum", "3"],    # L&S stub 'crŭcĭfīgo, ēre, better separated, cruci figo'
    "reverto": ["ti", "sum", "3"],      # L&S prints '(... perf. reverti)' inside parens; active + deponent
    "sicera": ["ae"],                   # L&S: 'sīcĕra, n., ... Vulg. Lev. 10, 9' (declined 1st decl. in Vulgate)
    "torquis": ["is"],                  # 'torquis or torques, m. and f.' (3rd decl. i-stem)
    "obryzum": ["i"],                   # 'obrȳzum, = ὄβρυζον, pure gold, Vulg.' (2nd decl. neuter)
    "Aethiops": ["is"],                 # Perseus XML commented out entry body (3rd decl. Aethiops, Aethiopis)
    "sinapi": ["is"],                   # 'sĭnāpi, is, n.' (3rd decl. neuter)
}

# irregular principal parts that the abbreviation rules cannot rebuild (or that the L&S text misprints)
_IRREG_PARTS = {
    "tollo": (["sustuli"], ["sublatum"]),
    "sustollo": (["sustuli"], ["sublatum"]),
    "attollo": ([], []),
    "extollo": ([], []),
    "loquor": ([], ["locutus"]),           # L&S XML prints 'cātus' for cūtus
    "ingredior": ([], ["ingressus"]),      # L&S XML prints 'essus' for gressus
    "intellego": (["intellexi"], ["intellectum"]),   # 'intellĕgo, exi, ectum': the tails drop 'll' (19 Nov 2026)
    "neglego": (["neglexi"], ["neglectum"]),
    "misereor": ([], ["miseritus", "misertus"]),     # syncopated Vulgate participle misertus (31+ tokens)
    "increpo": (["increpui", "increpaui"], ["increpitum", "increpatum"]),  # L&S cites 'increpavi, Vulg. Psa. 9, 6'
    "recingo": ([], ["recinctum"]),        # 'rĕ-cingo, no perf., ctum': prevent false 'rectus'
    "ulciscor": ([], ["ultus"]),           # 'ulciscor, ultus, 3, v. dep.'
    "cubo": (["cubui", "cubaui"], ["cubitum"]),      # L&S notes Vulgate perfect cubavi (2 Sam 13:14)
    "circumfulgeo": (["circumfulsi"], []), # compound of fulgeo, fulsi (Lk 2:9, Acts 9:3)
    "morior": ([], ["mortuus", "moriturus"]),        # irregular future participle moriturus
    "nascor": ([], ["natus", "nasciturus"]),         # irregular future participle nasciturus
}


def _verb_stems(hb: str, parts: List[str], prefix: str, intrans: bool = False, no_perf: bool = False
                ) -> Optional[Tuple[List[Tuple[str, str]], List[str]]]:
    if not hb.endswith(("o", "or")) or len(hb) < 2:
        return None
    perf_t, sup_t = _verb_parts(hb, parts)
    conjs = _verb_conjs(hb, parts, perf_t)
    if not conjs:
        return None
    conj = conjs[0]
    P = _present_stem(hb, conj)
    if not P:
        return None
    dep = hb.endswith("or")
    w = hb[:-2] if dep else hb[:-1]
    if conj in ("2", "3i", "4"):
        w = w[:-1]
    perf_forms: List[str] = []
    sup_forms: List[str] = []
    if hb in _IRREG_PARTS:
        perf_forms, sup_forms = (list(x) for x in _IRREG_PARTS[hb])
    else:
        cut = None
        for t in perf_t:
            f, c = _attach_part(hb, w, t, prefix, None)
            if f and f.endswith("i"):
                perf_forms.append(f)
                if c is not None and cut is None:
                    cut = c
        for t in sup_t:
            f, _c = _attach_part(hb, w, t, prefix, cut)
            if f:
                sup_forms.append(f)
    stems: List[Tuple[str, str]] = []
    semidep = (not dep) and not perf_forms and any(s.endswith("us") and not s.endswith("urus") for s in sup_forms)
    for c in conjs:
        Pc = _present_stem(hb, c)
        if not Pc:
            continue
        a, p, n = _PRES_CODES[c]
        stems.append((Pc, n))
        if dep:
            stems.append((Pc, p))
        else:
            stems.append((Pc, a))
            if not semidep:
                stems.append((Pc, p))
    if not perf_forms and not dep and not semidep:
        if conj == "1":
            perf_forms = [P + "aui"]
            if not sup_forms:
                sup_forms = [P + "atum"]
        elif conj == "2" and not no_perf:
            perf_forms = [P + "ui"]              # regular 2nd-conj. perfect when L&S omits it (areo -> aruit)
        elif conj == "4":
            perf_forms = [P + "iui"]
            if not sup_forms:
                sup_forms = [P + "itum"]
    if dep and not sup_forms:
        if conj == "1":
            sup_forms = [P + "atus"]            # regular 1st-conj. deponent: castrametor, castrametatus
        elif conj == "4":
            sup_forms = [P + "itus"]
    for f in perf_forms:
        F = f[:-1]
        if len(F) < 2:
            continue
        stems.append((F, "VPF"))
        if F.endswith("u") and len(F) >= 3 and F[-2] in "aeio":
            stems.append((F[:-1], "VSY"))
            if F[-2] == "i":
                stems.append((F[:-1], "VPF"))
    for s in sup_forms:
        if s.endswith("urus"):
            S = s[:-4]
            if len(S) >= 2:
                stems.append((S + "ur", "VFP"))
            continue
        elif s.endswith(("um", "us")):
            S = s[:-2]
        else:
            continue
        if len(S) < 2:
            continue
        # an intransitive verb (L&S 'v. n.') has a supine and an impersonal 'ventum est' but no declined
        # perfect passive participle (ventus, venti are the noun 'wind'); deponents keep theirs
        stems.append((S, "VSUP" if intrans and not dep else "VPP"))
        stems.append((S + "ur", "VFP"))
    exact: List[str] = []
    for short, full in (("dic", "dico"), ("duc", "duco"), ("fac", "facio")):
        if hb.endswith(full) and not hb.endswith("ficio"):
            exact.append(hb[: -len(full)] + short)
    return stems, exact


def _noun_stems(hb: str, parts: List[str], g: str, proper: bool, indecl: bool = False
                ) -> Optional[Tuple[List[Tuple[str, str]], List[str]]]:
    if indecl:
        return [], [hb]
    t = _b(parts[0]) if parts else ""
    if not t:
        return None
    S: List[Tuple[str, str]] = []
    X: List[str] = []
    # a full 2nd-declension genitive (vir, viri; filius, filii)
    if t.endswith("i") and not t.endswith(("ei", "ae")) and len(t) >= len(hb) - 1 and len(t) >= 3 and t[:2] == hb[:2]:
        st = t[:-1]
        if hb.endswith("ius") and st.endswith("i"):
            return [(hb[:-2], "N2IUS")], X
        if hb.endswith("us"):
            return [(st, "N2")], X
        if hb.endswith("um"):
            return [(st, "N2N")], X
        if hb.endswith(("er", "ir")):
            return [(st, "N2R")], [hb]
    if t.endswith("ei") and hb.endswith("es") and len(t) <= len(hb) + 1:
        return [(hb[:-2], "N5")], X
    if t == "es" and hb.endswith("e"):
        return [(hb[:-1], "N1GE")], X               # Greek 1st-decl. -e, -es (parasceve, myrice, stacte)
    if t == "em" and hb.endswith("es") and len(parts) > 1 and _b(parts[1]) == "e":
        return [(hb[:-2], "N5")], X                 # defective 5th-decl. (scabies, canities)
    if t == "ae":
        if hb.endswith("a"):
            S.append((hb[:-1], "N1"))
        elif hb.endswith("as") and (g == "m" or proper):
            S.append((hb[:-2], "N1GA"))
        elif hb.endswith("es"):
            S.append((hb[:-2], "N1GE"))
        elif hb.endswith("e"):
            S.append((hb[:-1], "N1GE"))
        else:
            return None
        return S, X
    if t == "arum" and hb.endswith("ae"):
        return [(hb[:-2], "N1PL")], X
    if t == "orum":
        if hb.endswith("i"):
            return [(hb[:-1], "N2PLM")], X
        if hb.endswith("a"):
            return [(hb[:-1], "N2PLN")], X
        return None
    if t in ("i", "ii"):
        if hb.endswith("ius"):
            return [(hb[:-2], "N2IUS")], X
        if hb.endswith("us"):
            if any(_b(p) == "us" for p in parts[1:]):
                return [(hb[:-2], "N2"), (hb[:-2], "N4")], X    # 'fīcus, i and ūs, f.' (ficus/ficu)
            return [(hb[:-2], "N2")], X
        if hb.endswith("os"):
            return [(hb[:-2], "N2")], [hb]
        if hb.endswith("um"):
            return [(hb[:-2], "N2N")], X
        if hb.endswith("on"):
            return [(hb[:-2], "N2N")], [hb]
        if hb.endswith(("er", "ir")):
            if hb == "onager":
                return [(hb, "N2R"), ("onagr", "N2R")], [hb]
            return [(hb, "N2R")], [hb]
        return None
    if re.fullmatch(r"[^aeiouy]{1,3}ri", t) and hb.endswith("er"):
        gen = _attach_gen(hb, t)
        if gen:
            return [(gen[:-1], "N2R")], [hb]
        return None
    if t == "eri" and hb.endswith("er"):
        return [(hb, "N2R")], [hb]
    if t == "us" and hb.endswith("us"):
        return [(hb[:-2], "N4")], X
    if t == "us" and hb.endswith("u"):
        return [(hb[:-1], "N4N")], X
    if t == "u" and hb.endswith("us"):          # Jesus, Jesu
        return [(hb[:-2], "N4")], X
    if t == "ei" and hb.endswith("es"):
        return [(hb[:-2], "N5")], X
    if t in ("ium", "um"):
        if hb.endswith("es"):
            return [(hb[:-2], "N3PL")], X
        if hb.endswith("ia"):
            return [(hb[:-2], "N3PLN")], X
        if hb.endswith("a"):
            return [(hb[:-1], "N3PLN")], X
        return None
    if t.endswith("is"):
        if hb == "uis" and t == "uis":
            return [], [hb]   # irregular defective noun vis (vim, vi, vires... in _EXTRA_FORMS)
        if t == "is":
            if hb.endswith("is"):
                return [(hb[:-2], "N3IM")], [hb]
            if hb.endswith("es"):
                return [(hb[:-2], "N3I")], [hb]
            if hb.endswith(("e", "i")) and g == "n":
                return [(hb[:-1], "N3NI")], [hb]
            if hb.endswith("ps") and len(hb) > 3:
                return [(hb[:-1], "N3")], [hb]          # Aethiops, Aethiopis
            if hb[-1] in "lrn" and len(hb) > 3:
                return [(hb, "N3")], [hb]               # proconsul, is
            return None
        gen = _attach_gen(hb, t)
        if not gen or not gen.endswith("is") or len(gen) < 3:
            return None
        gs = gen[:-2]
        if g == "n":
            code = "N3NI" if hb.endswith(("al", "ar", "e")) else "N3N"
        else:
            syl = len(re.findall(r"[aeiouy]+", hb))
            if syl == 1 and re.search(r"[^aeiouy]{2}$", hb) and not hb.endswith("x"):
                code = "N3I"          # urbs, mons, pars, nox-type monosyllables
            elif hb.endswith(("ns", "rs")):
                code = "N3I"
            else:
                code = "N3"
        return [(gs, code)], [hb]
    return None


def _adj_stems(hb: str, parts: List[str]) -> Optional[Tuple[List[Tuple[str, str]], List[str], Optional[str]]]:
    toks = [_b(x) for x in parts if _b(x)]
    t0 = toks[0] if toks else ""
    S: List[Tuple[str, str]] = []
    X: List[str] = []
    ps: Optional[str] = None
    if not toks:
        # 'potens, P. a., v. possum' / 'beatus, P. a.': the paradigm follows from the ending
        if hb.endswith(("ns",)) and len(hb) > 3:
            toks, t0 = [hb[:-1] + "tis"], hb[:-1] + "tis"
        elif hb.endswith("us") and len(hb) > 3:
            toks, t0 = ["a", "um"], "a"
        else:
            return None
    if t0 == "a" and hb.endswith("us"):
        ps = hb[:-2]
        S.append((ps, "A12"))
    elif t0 == "ae" and len(toks) > 1 and toks[1] == "a" and hb.endswith("i"):
        return [(hb[:-1], "A12PL")], X, None          # ducenti, ae, a
    elif hb.endswith("er") and t0.endswith("a") and len(t0) <= 6 and (len(toks) < 2 or toks[1].endswith("um")):
        sync = any(x.endswith(("ra", "rum")) and not x.endswith(("era", "erum")) for x in toks)
        ps = hb if ((t0.endswith("era") or t0 == "a") and not sync) else hb[:-2] + "r"
        S.append((ps, "A12R"))
        X.append(hb)
    elif t0 == "e" and hb.endswith("is"):
        ps = hb[:-2]
        S.append((ps, "A3"))
    elif t0 == "ius" and hb.endswith("ior") and len(hb) > 4:
        return [(hb[:-3], "CMP")], X, None             # interior, exterior, superior, inferior, prior, senior
    elif hb.endswith("er") and t0.endswith("is") and len(toks) >= 2 and toks[1].endswith("e"):
        ps = hb if t0.startswith("eris") else hb[:-2] + "r"
        S.append((ps, "A3"))
        X.append(hb)
    elif t0.endswith("is") and len(t0) >= 2:
        gen = _attach_gen(hb, t0)
        if not gen or not gen.endswith("is") or len(gen) < 4:
            return None
        ps = gen[:-2]
        S.append((ps, "A31I" if hb.endswith(("ns", "x", "rs")) else "A31C"))
        X.append(hb)
    else:
        return None
    if ps and len(ps) >= 2:
        S.append((ps, "CMP"))
        if hb.endswith("er"):
            S.append((hb + "rim", "A12"))
        elif hb in ("facilis", "difficilis", "similis", "dissimilis", "humilis", "gracilis"):
            S.append((ps + "lim", "A12"))
        else:
            S.append((ps + "issim", "A12"))
    return S, X, ps


_POS_MAP = [
    (r"^v\.", "V"), (r"^P\. a\.", "ADJ"), (r"^adj", "ADJ"), (r"^num", "NUM"), (r"^adv\. num", "NUM"),
    (r"^adv", "ADV"), (r"^prep", "PREP"), (r"^conj", "CONJ"), (r"^interj", "INTERJ"), (r"^pron", "PRON"),
]


def _map_pos(lspos: str) -> str:
    s = re.sub(r"^(?:(?:temp|rel|interrog|demonstr|indef|card|ordin|distrib|poss|pers|dem)\.\s*)+", "", lspos or "",
               flags=re.I)
    if re.match(r"(?:card|ordin|distrib)\.", lspos or "", re.I):
        return "NUM"
    for rx, tag in _POS_MAP:
        if re.search(rx, s if tag != "ADJ" or rx.startswith("^P") else s.lower()):
            return tag
    return ""


def _gender(gens: List[str]) -> str:
    for g in gens:
        g = g.strip().lower()
        for k in ("m", "f", "n", "c"):
            if g.startswith(k):
                return k
    return ""


# ---------------------------------------------------------------------------
# 3.  Closed lists (bare spelling: u for v, i for j)
# ---------------------------------------------------------------------------

def _w(s: str) -> List[str]:
    return [x for x in s.split() if x]


_SUM = _w("sum es est sumus estis sunt eram eras erat eramus eratis erant ero eris erit erimus eritis erunt "
          "sim sis sit simus sitis sint essem esses esset essemus essetis essent forem fores foret foremus "
          "foretis forent este esto estote sunto esse fore")
_SUM_PERF = _w("fui fuisti fuit fuimus fuistis fuerunt fuere fueram fueras fuerat fueramus fueratis fuerant "
               "fuero fueris fuerit fuerimus fueritis fuerint fuerim fuissem fuisses fuisset fuissemus fuissetis "
               "fuissent fuisse")
_FUT_PART = _w("us a um i ae o am os as is orum arum")
_POSSUM = _w("possum potes potest possumus potestis possunt poteram poteras poterat poteramus poteratis poterant "
             "potero poteris poterit poterimus poteritis poterunt possim possis possit possimus possitis possint "
             "possem posses posset possemus possetis possent posse")
_EO = _w("eo is it imus itis eunt ibam ibas ibat ibamus ibatis ibant ibo ibis ibit ibimus ibitis ibunt "
         "ies iet iemus ietis ient eam eas "
         "eat eamus eatis eant irem ires iret iremus iretis irent i ite ito itote eunto ire iens euntis eunti "
         "euntem eunte euntes euntium euntibus eundi eundo eundum itur ibatur ibitur eatur iretur "
         "iui iuisti iuit iuimus iuistis iuerunt iueram iuerat iuero iuerit iuerint iuerim iuissem iuisset iuisse "
         "ii isti iit iimus istis ierunt iere ieram ieras ierat ieramus ieratis ierant iero ieris ierit ierimus "
         "ieritis ierint ierim issem isses isset issemus issetis issent isse iissem iisses iisset iissemus iissetis "
         "iissent iisse itum iturus itura iturum ituri "
         "iturae ituro ituram ituros ituras ituris iturorum")
_EO_PASS = _w("eor iris itur imur imini euntur ibar ibatur ibantur ibor ibitur ibuntur ear eatur eantur irer iretur "
              "irentur iri itus ita itum iti itae ito itam itos itas itis itorum itarum")
_FERO_PRES = _w("fero fers fert ferimus fertis ferunt ferebam ferebas ferebat ferebamus ferebatis ferebant feram "
                "feres feret feremus feretis ferent feras ferat feramus feratis ferant ferrem ferres ferret "
                "ferremus ferretis ferrent fer ferte ferto fertote ferunto ferre ferens ferentis ferenti ferentem "
                "ferente ferentes ferentium ferentibus ferentia ferendi ferendo ferendum ferendus ferenda "
                "ferendae ferendam ferendos ferendas ferendis ferendorum ferendarum feror ferris fertur ferimur "
                "ferimini feruntur ferebar ferebaris ferebatur ferebamur ferebamini ferebantur ferar fereris "
                "feretur feremur feremini ferentur feraris feratur feramur feramini ferantur ferrer ferreris "
                "ferretur ferremur ferremini ferrentur ferri")
_VOLO = _w("uolo uis uult uolt uolumus uultis uolunt uolebam uolebas uolebat uolebamus uolebatis uolebant uolam "
           "uoles uolet uolemus uoletis uolent uelim uelis uelit uelimus uelitis uelint uellem uelles uellet "
           "uellemus uelletis uellent uelle uolens uolentis uolenti uolentem uolente uolentes uolentium "
           "uolentibus")
_NOLO = _w("nolo nolumus nolunt nolebam nolebas nolebat nolebamus nolebatis nolebant nolam noles nolet nolemus "
           "noletis nolent nolim nolis nolit nolimus nolitis nolint nollem nolles nollet nollemus nolletis "
           "nollent noli nolite nolito nolitote nolle nolens nolentis nolentem nolentes")
_MALO = _w("malo mauis mauult malumus mauultis malunt malebam malebat malam males malet malim malis malit "
           "malimus malitis malint mallem malles mallet mallent malle")
_FIO = _w("fio fis fit fimus fitis fiunt fiebam fiebas fiebat fiebamus fiebatis fiebant fiam fies fiet fiemus "
          "fietis fient fias fiat fiamus fiatis fiant fierem fieres fieret fieremus fieretis fierent fieri fite")
_QUEO = _w("queo quis quit quimus quitis queunt quibam quibat quibant quibo quibit queam queas queat queamus "
           "queant quirem quiret quirent quire quiui quiuit quiuerunt quiuerit quiuisset quiit quierunt quiuisse "
           "quisse")
_PERF_ENDS = _w("i isti it imus istis erunt ere eram eras erat eramus eratis erant ero eris erit erimus eritis "
                "erint erim issem isses isset issemus issetis issent isse")


def _perf(stem: str) -> List[str]:
    return [stem + x for x in _PERF_ENDS]


def _a12(stem: str) -> List[str]:
    return [stem + x for x in _FUT_PART]


def _sum_compound(pre: str, pre_vowel: str, perf_pre: str) -> List[str]:
    out = []
    for f in _SUM:
        out.append((pre_vowel if f[0] in _VOW else pre) + f)
    out += _perf(perf_pre + "fu")
    out += _a12(perf_pre + "futur")
    return out


# (headword, L&S homograph n or "", POS, forms)
_CLOSED_VERBS: List[Tuple[str, str, str, List[str]]] = [
    ("sum", "1", "V", _SUM + _SUM_PERF + _a12("futur")),
    ("absum", "", "V", _sum_compound("ab", "ab", "a") + _perf("abfu") + ["abs" + f for f in _SUM if f[0] == "s"]),
    ("adsum", "", "V", _sum_compound("ad", "ad", "ad") + _perf("affu") + ["as" + f for f in _SUM if f[0] == "s"]),
    ("desum", "", "V", _sum_compound("de", "de", "de")),
    ("insum", "", "V", _sum_compound("in", "in", "in")),
    ("intersum", "", "V", _sum_compound("inter", "inter", "inter")),
    ("obsum", "", "V", _sum_compound("ob", "ob", "ob") + _perf("offu")),
    ("praesum", "", "V", _sum_compound("prae", "prae", "prae")),
    ("prosum", "", "V", _sum_compound("pro", "prod", "pro")),
    ("subsum", "", "V", _sum_compound("sub", "sub", "sub")),
    ("supersum", "", "V", _sum_compound("super", "super", "super")),
    ("possum", "", "V", _POSSUM + _perf("potu")),
    ("eo", "1", "V", _EO),
    ("fero", "", "V", _FERO_PRES + _perf("tul") + _a12("lat") + _a12("latur") + ["latu"]),
    ("uolo", "1", "V", _VOLO + _perf("uolu")),
    ("nolo", "", "V", _NOLO + _perf("nolu")),
    ("malo", "", "V", _MALO + _perf("malu")),
    ("fio", "", "V", _FIO),
    ("queo", "", "V", _QUEO),
    ("nequeo", "", "V", ["ne" + f for f in _QUEO]),
    ("memini", "", "V", _w("memini meministi meminit meminimus meministis meminerunt meminere memineram "
                           "memineras meminerat meminerant meminero memineris meminerit meminerint meminerim "
                           "meminissem meminisses meminisset meminissent meminisse memento mementote")),
    ("odi", "", "V", _perf("od") + _perf("odiu") + _w("odiet odietur odient") + _a12("osur") +
     _w("odiens odientis odienti odientem odiente odientes odientium odientibus")),
    ("aio", "", "V", _w("aio ais ait aiunt aiebam aiebas aiebat aiebamus aiebatis aiebant aias aiat aiant aiens "
                        "aientes")),
    ("inquam", "", "V", _w("inquam inquis inquit inquimus inquitis inquiunt inquiebat inquies inquiet inquito inquiens")),
]

# eo compounds: (headword, present prefix, transitive?)
_EO_COMPOUNDS = [("abeo", "ab", False), ("adeo", "ad", True), ("anteeo", "ante", True), ("circumeo", "circum", True),
                 ("circueo", "circu", True), ("coeo", "co", False), ("depereo", "deper", False),
                 ("dispereo", "disper", False), ("exeo", "ex", False), ("ineo", "in", True),
                 ("intereo", "inter", False), ("introeo", "intro", False), ("obeo", "ob", True),
                 ("pereo", "per", False), ("praeeo", "prae", True), ("praetereo", "praeter", True),
                 ("prodeo", "prod", False), ("redeo", "red", False), ("subeo", "sub", True),
                 ("subintroeo", "subintro", False), ("transeo", "trans", True),
                 ("pertranseo", "pertrans", True), ("ueneo", "uen", False), ("exeo", "ex", False)]

# fero compounds: (headword, present prefix(es), perfect prefix(es), supine prefix(es))
_FERO_COMPOUNDS = [
    ("affero", ("af", "ad"), ("at", "ad"), ("al", "ad")),
    ("aufero", ("au",), ("abs",), ("ab",)),
    ("antefero", ("ante",), ("ante",), ("ante",)),
    ("circumfero", ("circum",), ("circum",), ("circum",)),
    ("confero", ("con",), ("con",), ("col", "con")),
    ("defero", ("de",), ("de",), ("de",)),
    ("differo", ("dif",), ("dis",), ("di",)),
    ("effero", ("ef",), ("ex",), ("e",)),
    ("infero", ("in",), ("in",), ("il", "in")),
    ("offero", ("of",), ("ob",), ("ob",)),
    ("perfero", ("per",), ("per",), ("per",)),
    ("praefero", ("prae",), ("prae",), ("prae",)),
    ("profero", ("pro",), ("pro",), ("pro",)),
    ("refero", ("re",), ("ret", "re"), ("re",)),
    ("suffero", ("suf",), ("sus",), ("sub",)),
    ("transfero", ("trans",), ("trans",), ("trans", "tra")),
]

# pronouns, pronominal adjectives and numerals: (headword, n, POS, forms)
_CLOSED_PRON: List[Tuple[str, str, str, List[str]]] = [
    ("ego", "", "PRON", _w("ego mei mihi mi me")),
    ("tu", "", "PRON", _w("tu tui tibi te")),
    ("nos", "", "PRON", _w("nos nostri nostrum nobis")),
    ("uos", "", "PRON", _w("uos uestri uestrum uobis")),
    ("sui", "", "PRON", _w("sui sibi se sese")),
    ("is", "", "PRON", _w("is ea id eius ei eum eam eo ii eae eorum earum eis iis eos eas")),
    ("hic", "", "PRON", _w("hic haec hoc huius huic hunc hanc hac hi hae horum harum his hos has")),
    ("ille", "", "PRON", _w("ille illa illud illius illi illum illam illo illae illorum illarum illis illos illas")),
    ("iste", "", "PRON", _w("iste ista istud istius isti istum istam isto istae istorum istarum istis istos istas")),
    ("ipse", "", "PRON", _w("ipse ipsa ipsum ipsius ipsi ipsam ipso ipsae ipsorum ipsarum ipsis ipsos ipsas")),
    ("idem", "", "PRON", _w("idem eadem eiusdem eidem eundem eumdem eandem eamdem eodem iidem eaedem eorundem "
                            "eorumdem earundem earumdem eisdem iisdem eosdem easdem")),
    ("qui", "1", "PRON", _w("qui quae quod cuius cui quem quam quo qua quorum quarum quibus quos quas")),
    ("quis", "1", "PRON", _w("quis quid cuius cui quem quo quibus")),
    ("aliquis", "", "PRON", _w("aliquis aliqua aliquid aliquod alicuius alicui aliquem aliquam aliquo aliqui "
                               "aliquae aliquorum aliquarum aliquibus aliquos aliquas")),
    ("quidam", "", "PRON", _w("quidam quaedam quoddam quiddam cuiusdam cuidam quemdam quendam quamdam quandam "
                              "quodam quadam quorumdam quorundam quarumdam quarundam quibusdam quosdam quasdam")),
    ("quisque", "", "PRON", _w("quisque quaeque quodque quidque quicque cuiusque cuique quemque quamque quoque "
                               "quaque quique quorumque quibusque quosque")),
    ("quisquam", "", "PRON", _w("quisquam quidquam quicquam cuiusquam cuiquam quemquam quoquam quaquam")),
    ("quispiam", "", "PRON", _w("quispiam quaepiam quodpiam quidpiam quippiam cuiuspiam cuipiam quempiam quampiam "
                                "quopiam quapiam quipiam quorumpiam quibuspiam quospiam")),
    ("quilibet", "", "PRON", _w("quilibet quaelibet quodlibet quidlibet cuiuslibet cuilibet quemlibet quamlibet "
                                "quolibet qualibet")),
    ("quiuis", "", "PRON", _w("quiuis quaeuis quodvis quiduis cuiusuis cuiuis quemuis quamuis quouis quauis")),
    ("quicumque", "", "PRON", _w("quicumque quaecumque quodcumque cuiuscumque cuicumque quemcumque quamcumque "
                                 "quocumque quacumque quorumcumque quarumcumque quibuscumque quoscumque quascumque "
                                 "quicunque quaecunque quodcunque cuiuscunque cuicunque quemcunque quamcunque "
                                 "quocunque quacunque quibuscunque quoscunque quascunque")),
    ("quisquis", "", "PRON", _w("quisquis quidquid quicquid quoquo cuicui")),
    ("uterque", "", "PRON", _w("uterque utraque utrumque utriusque utrique utramque utroque utraeque "
                               "utrorumque utrarumque utrisque utrosque utrasque")),
    ("uter", "", "PRON", _w("uter utra utrum utrius utri utram utro utrae utrorum utrarum utris utros utras")),
    ("neuter", "", "PRON", _w("neuter neutra neutrum neutrius neutri neutram neutro neutrae neutrorum neutrarum "
                              "neutris neutros neutras")),
    ("alter", "", "PRON", _w("alter altera alterum alterius alteri alteram altero alterae alterorum alterarum "
                             "alteris alteros alteras")),
    ("alteruter", "", "PRON", _w("alteruter alterutra alterutrum alterutrius alterutri alterutram alterutro "
                                 "alterutrae alterutrorum alterutrarum alterutris alterutros alterutras")),
    ("alius", "", "PRON", _w("alius alia aliud alii aliae alium aliam alio aliorum aliarum aliis alios alias "
                             "alterius")),
    ("nullus", "", "PRON", _w("nullus nulla nullum nullius nulli nullam nullo nullae nullorum nullarum nullis "
                              "nullos nullas")),
    ("ullus", "", "PRON", _w("ullus ulla ullum ullius ulli ullam ullo ullae ullorum ullarum ullis ullos ullas")),
    ("nemo", "", "PRON", _w("nemo neminis nemini neminem nemine")),
    ("nihil", "", "PRON", _w("nihil nihili nihilo nil nihilum")),
    ("solus", "", "ADJ", _w("solus sola solum solius soli solam solo solae solorum solarum solis solos solas")),
    ("totus", "", "ADJ", _w("totus tota totum totius toti totam toto totae totorum totarum totis totos totas")),
    ("unus", "", "NUM", _w("unus una unum unius uni unam uno unae unorum unarum unis unos unas")),
    ("duo", "", "NUM", _w("duo duae duorum duarum duobus duabus duos duas")),
    ("tres", "", "NUM", _w("tres tria trium tribus")),
    ("ambo", "", "NUM", _w("ambo ambae amborum ambarum ambobus ambabus ambos ambas")),
    ("mille", "", "NUM", _w("mille milia millia milium millium milibus millibus")),
    ("unusquisque", "", "PRON", _w("unusquisque unaquaeque unumquodque unumquidque uniuscuiusque unicuique "
                                   "unumquemque unamquamque unoquoque unaquaque")),
    ("domus", "", "N", _w("domus domui domum domo domi domorum domuum domibus domos")),
]

# irregular comparison: forms -> positive lemma (L&S lists melior, optimus ... under / as comp. of the positive)
_IRREG_COMPARISON = {
    "bonus": _w("melior melius melioris meliori meliorem meliore meliores meliora meliorum melioribus") +
             _a12("optim"),
    "malus": _w("peior pejor peius peioris peiori peiorem peiore peiores peiora peiorum peioribus") + _a12("pessim"),
    "magnus": _w("maior maius maioris maiori maiorem maiore maiores maiora maiorum maioribus") + _a12("maxim"),
    "paruus": _w("minor minoris minori minorem minore minores minora minorum minoribus") + _a12("minim"),
    "multus": _a12("plurim"),
}
# irregular forms that the regular paradigm cannot produce: locus 'plur. loci and loca'; deus 'nom.
# plur. di and dei; dii freq. in MSS.'; requies (3rd decl.) with the 5th-decl. acc./abl. requiem,
# requie; consonant-stem gen. plur. in -um of these -is/-es nouns (panum, canum, juvenum, volucrum,
# sedum, vatum, apum, mensum)
_DOUBLE_ORDINALS: Dict[str, str] = {
    "tertiusdecimus": "terti", "quartusdecimus": "quart", "quintusdecimus": "quint",
    "sextusdecimus": "sext", "septimusdecimus": "septim", "octavusdecimus": "octau",
    "nonusdecimus": "non",
}
_ORD_ENDS = ("us", "a", "um", "i", "ae", "o", "am", "os", "as", "is", "orum", "arum")
_EXTRA_FORMS = {"locus": ["loca"], "deus": ["dii", "diis"], "requies": ["requiem", "requie", "requiei"],
                "panis": ["panum"], "canis": ["canum"], "juvenis": ["juvenum", "iunior", "iunius", "iunioris",
                                                                    "iuniori", "iuniorem", "iuniore", "iuniores",
                                                                    "iuniora", "iuniorum", "iunioribus"],
                "volucris": ["volucrum"], "sedes": ["sedum"], "vates": ["vatum"], "apis": ["apum"],
                "mensis": ["mensum"], "senex": ["senum"],
                "innocens": ["innocentum"], "parens#2": ["parentum"], "sapiens": ["sapientum"],
                "os#2": ["ossium"],
                "fimbriae": ["fimbria", "fimbriae", "fimbriam"],
                "angustiae": ["angustia", "angustiae", "angustiam"],
                "topazos": ["topazius", "topazii", "topazio", "topazium"],
                "cinifes": ["sciniphes"],
                "aether": ["aethera"],
                "vendo": ["uenundatus", "uenundata", "uenundatum", "uenundati", "uenundatae", "uenundatos",
                          "uenundatas", "uenundatis", "uenundato", "uenundari", "uenundabitur", "uenundabuntur",
                          "uenundedit", "uenundederunt"],
                "sycaminus": ["sycomorus", "sycomori", "sycomoro", "sycomorum", "sycomoros", "sycomoris"],
                "murra#1": ["myrrha", "myrrhae", "myrrham", "myrrhis"],
                "paterfamilias": ["paterfamilias", "patrisfamilias", "patrifamilias", "patremfamilias",
                                  "patrefamilias", "patresfamilias"],
                "ecstasis": ["extasis", "extasi", "extasim", "extasin", "extaseos"],
                "commixtio": ["commistio", "commistionis", "commistioni", "commistionem", "commistione"],
                "fornicarius": ["fornicaria", "fornicariae", "fornicariam", "fornicariarum", "fornicariis",
                                "fornicarias"],
                **{k: [st + e + "decim" + e for e in _ORD_ENDS] for k, st in _DOUBLE_ORDINALS.items()},
                # 'vicis (as a gen.; the nom. does not occur), vicem, vice; in plur. vices, vicibus' (L&S)
                # bare 'vicis' is left to vicus (abl. plur. 'in vicis', 6 of 7 in the Studio Latin): 18 Nov re-check
                "uicis": ["uicem", "uice", "uices", "uicibus"],
                # 'bōtrys, ўos, f. ... Latinized bōtrus, i, f., the grape, Vulg.' (L&S): the Vulgate's 2nd-decl. forms
                "botrys": ["botrus", "botri", "botro", "botrum", "botros", "botris", "botrorum"],
                # indeclinables whose L&S head gives no paradigm, and Vulgate spellings L&S lists as other forms
                # ('rursus, rursum ... adv.'; quatuordecim for quattuordecim; necesse; deinceps; sponte), 19 Nov 2026
                "rursus": ["rursum"], "quattuordecim": ["quatuordecim"], "necesse": ["necesse"],
                "deinceps": ["deinceps"], "sponte": ["sponte"],
                # 'dētĕrĭor, ius, adj. comp.': the comparative declension (Heb 10:29 'deteriora')
                "aloe": ["aloes", "aloen"],              # Greek gen. 'myrrhae et aloes' (Jn 19:39)
                "deterior": ["deterior", "deterius", "deterioris", "deteriori", "deteriorem", "deteriore",
                             "deteriores", "deteriora", "deteriorum", "deterioribus"],
                # irregular forms L&S states in prose: bos (boum, bobus, bubus), vis (vim, vi, vires),
                # jusjurandum (double-declined), plus (plura, plurium, pluribus), baculum (baculus),
                # gelum (gelu), satrapes (satrapa), ruminor (rumino), diligenter (diligentius/diligentissime),
                # prudens (prudenter)
                "bos": ["boum", "bobus", "bubus"],
                "uis": ["uim", "ui", "uires", "uirium", "uiribus"],
                "iusiurandum": ["iusiurandum", "iurisiurandi", "iuriiurando", "iureiurando", "iusiurandi"],
                "plus": ["plura", "plurium", "pluribus"],
                "baculum": ["baculus", "baculos"],
                "gelum": ["gelu"],
                "satrapes": ["satrapa", "satrapae", "satrapam", "satrapas", "satraparum", "satrapis"],
                "ruminor": ["rumino", "ruminat", "ruminant", "ruminans", "ruminantis", "ruminantia"],
                "diligenter": ["diligentius", "diligentissime"],
                "prudens": ["prudenter"],
                "dexter": ["dexterum"],
                "sartatecta": ["sartatecta", "sartatectis", "sartatectorum"],
                "brabeum": ["brauium", "brauii", "brauio"],
                "quinquiens": ["quinquies"],
                "quotienscumque": ["quotiescumque"],
                "orichalcum": ["auricalco", "auricalcum", "aurichalco", "aurichalcum"],
                "lambo": ["lambuerunt", "lambuit"],
                "cornupeta": ["cornupeta", "cornupetae", "cornupetam", "cornupetas"],
                "laxo": ["laxate"]}
# names that the Vulgate declines where L&S gives no paradigm: 'Abrahae' (gen. of Abraham, 32 tokens);
# the Hebrew plural 'cherubim' / 'cherubin' of Cherub, 'Baalim' of Baal
_NAME_FORMS = {"lat:Abraham": ["abrahae"], "lat:Cherub": ["cherubim", "cherubin"], "lat:Baal": ["baalim"]}
# L&S proper-name entries that the Clementine text writes in lower case ('pharisæi', 'cherub', 'christus Domini'
# = the Lord's anointed, 'gigantes', 'hyacintho'): these may match a lower-case token
_LOWER_PROPER = {"lat:Pharisaeus", "lat:Sadducaei", "lat:Cherub", "lat:Christus", "lat:Antichristus",
                 "lat:Pseudochristus", "lat:Gigas", "lat:Satan", "lat:Hosanna", "lat:Behemoth", "lat:Aegyptius",
                 "lat:Aegyptiacus", "lat:Hyacinthus", "lat:Ficulneus", "lat:Punicus", "lat:Nazaraeus#1",
                 "lat:Pytho#2", "lat:Python", "lat:Omega", "lat:Graece", "lat:Graecus#1", "lat:Africus",
                 "lat:Hebraeus", "lat:Hebraicus", "lat:Judaicus"}

# L&S cross-reference stubs that are the same word as their target although the declension differs
# ('vasum, i, n. = vas', 'altarium, ii, n., v. altaria'): emitted as the target lemma
_STUB_CANON = {"lat:vasum": "lat:vas#2", "lat:altarium": "lat:altaria", "lat:thus": "lat:tus",
               "lat:quadrigae": "lat:quadriga", "lat:pene": "lat:paene", "lat:arcte": "lat:arte",
               "lat:dilectus#2": "lat:delectus#2", "lat:imo": "lat:immo", "lat:superior": "lat:superus",
               "lat:Hebraei": "lat:Hebraeus", "lat:ossum": "lat:os#2"}

_COMPARISON_ALIASES = {"melior": "bonus", "optimus": "bonus", "major": "magnus", "maximus": "magnus",
                       "pessimus": "malus", "pejor": "malus", "minimus": "parvus", "plurimus": "multus"}

# indeclinable function words: headword (bare) -> (L&S homograph n or "", POS)
_FUNCTION_WORDS = {
    "et": ("", "CONJ"), "atque": ("", "CONJ"), "ac": ("", "CONJ"), "sed": ("", "CONJ"), "autem": ("", "CONJ"),
    "enim": ("", "CONJ"), "nam": ("", "CONJ"), "namque": ("", "CONJ"), "etenim": ("", "CONJ"),
    "ergo": ("", "CONJ"), "igitur": ("", "CONJ"), "itaque": ("", "CONJ"), "quia": ("", "CONJ"),
    "quoniam": ("", "CONJ"), "ut": ("", "CONJ"), "uti": ("", "CONJ"), "nec": ("", "CONJ"), "neque": ("", "CONJ"),
    "neue": ("", "CONJ"), "neu": ("", "CONJ"), "si": ("", "CONJ"), "nisi": ("", "CONJ"), "ni": ("", "CONJ"),
    "sin": ("", "CONJ"), "siquidem": ("", "CONJ"), "etsi": ("", "CONJ"), "etiamsi": ("", "CONJ"),
    "tametsi": ("", "CONJ"), "tamen": ("", "CONJ"), "attamen": ("", "CONJ"), "uerumtamen": ("", "CONJ"),
    "quasi": ("", "CONJ"), "tamquam": ("", "CONJ"), "tanquam": ("", "CONJ"), "sicut": ("", "CONJ"),
    "sicuti": ("", "CONJ"), "uelut": ("", "CONJ"), "ueluti": ("", "CONJ"), "uel": ("", "CONJ"),
    "aut": ("", "CONJ"), "an": ("", "CONJ"), "num": ("", "PART"), "utrum": ("", "CONJ"), "uero": ("", "CONJ"),
    "at": ("", "CONJ"), "ast": ("", "CONJ"), "siue": ("", "CONJ"), "seu": ("", "CONJ"), "dum": ("", "CONJ"),
    "donec": ("", "CONJ"), "quando": ("", "CONJ"), "quandoquidem": ("", "CONJ"), "postquam": ("", "CONJ"),
    "antequam": ("", "CONJ"), "priusquam": ("", "CONJ"), "quamquam": ("", "CONJ"), "quamuis": ("", "CONJ"),
    "quatenus": ("", "CONJ"), "quin": ("", "CONJ"), "quominus": ("", "CONJ"), "ceterum": ("", "CONJ"),
    "que": ("", "CONJ"), "quod": ("1", "CONJ"), "cum": ("", "CONJ"), "quam": ("", "CONJ"),
    "non": ("", "PART"), "ne": ("1", "PART"), "haud": ("", "PART"), "nonne": ("", "PART"),
    "numquid": ("", "PART"), "quidem": ("", "PART"), "ecce": ("", "PART"), "en": ("", "PART"),
    "o": ("", "INTERJ"), "amen": ("", "INTERJ"), "alleluia": ("", "INTERJ"), "uae": ("", "INTERJ"),
    "in": ("1", "PREP"), "ad": ("", "PREP"), "de": ("2", "PREP"), "ex": ("", "PREP"), "e": ("", "PREP"),
    "ab": ("", "PREP"), "abs": ("", "PREP"), "per": ("", "PREP"), "pro": ("", "PREP"), "prae": ("", "PREP"),
    "sub": ("", "PREP"), "super": ("2", "PREP"), "supra": ("", "PREP"), "inter": ("", "PREP"),
    "intra": ("", "PREP"), "infra": ("", "PREP"), "ante": ("", "PREP"), "post": ("", "PREP"),
    "apud": ("", "PREP"), "circa": ("", "PREP"), "circum": ("", "PREP"), "contra": ("", "PREP"),
    "coram": ("", "PREP"), "erga": ("", "PREP"), "extra": ("", "PREP"), "iuxta": ("", "PREP"),
    "ob": ("", "PREP"), "penes": ("", "PREP"), "praeter": ("", "PREP"), "prope": ("", "PREP"),
    "propter": ("", "PREP"), "secundum": ("", "PREP"), "sine": ("", "PREP"), "trans": ("", "PREP"),
    "ultra": ("", "PREP"), "uersus": ("", "PREP"), "aduersus": ("3", "PREP"), "aduersum": ("3", "PREP"),
    "absque": ("", "PREP"), "citra": ("", "PREP"), "cis": ("", "PREP"), "subter": ("", "PREP"),
    "tenus": ("", "PREP"), "usque": ("", "PREP"), "secus": ("", "PREP"), "clam": ("", "PREP"),
    "palam": ("", "PREP"),
    # 19 Nov 2026: frequent Vulgate particles without a usable L&S paradigm (necnon 'nec-non, also separately';
    # 'hūjuscĕmŏdi and hūjusmŏdi, v. under modus'; usquequo 'how long?')
    "necnon": ("", "CONJ"), "usquequo": ("", "PART"), "huiuscemodi": ("", "PRON"), "huiusmodi": ("", "PRON"),
    "eiusmodi": ("", "PRON"), "necdum": ("", "CONJ"), "nequando": ("", "CONJ"), "quoadusque": ("", "CONJ"),
    "tantummodo": ("", "ADV"), "nihilominus": ("", "ADV"), "nudiustertius": ("", "ADV"), "alioquin": ("", "ADV"),
    "usquequaque": ("", "ADV"), "dummodo": ("", "CONJ"), "paulominus": ("", "ADV"), "quinimmo": ("", "ADV"),
}
# function-word spellings that are not L&S headwords of their own: 'adversus or adversum, adv. and prep.'
# (L&S adversus#3) -> that headword
_FUNCTION_HEAD = {"aduersum": "aduersus", "alioquin": "alioqui"}
_POSSESSIVES = {"meus", "tuus", "suus", "noster", "uester", "cuius"}

# Short glosses for the closed-list and function words, whose L&S entries open with grammar notes
# rather than a meaning ('sum' would otherwise get '2d pers', 'non' 'N. cr').
_CLOSED_GLOSS = {
    "sum": "to be", "absum": "to be away", "adsum": "to be present", "desum": "to be lacking", "insum": "to be in",
    "intersum": "to be between, take part", "obsum": "to be against", "praesum": "to be over, rule",
    "prosum": "to be of use", "subsum": "to be under", "supersum": "to remain", "possum": "to be able, can",
    "eo": "to go", "fero": "to bear, carry", "uolo": "to wish, will", "nolo": "to be unwilling",
    "malo": "to prefer", "fio": "to become, be made, happen", "queo": "to be able", "nequeo": "to be unable",
    "memini": "to remember", "odi": "to hate", "aio": "to say", "inquam": "to say",
    "ego": "I", "tu": "you (sing.)", "nos": "we", "uos": "you (plur.)", "sui": "himself, herself, themselves",
    "is": "he, she, it; that", "hic": "this", "ille": "that; he", "iste": "that (of yours)",
    "ipse": "self, the very", "idem": "the same", "qui": "who, which (relative)", "quis": "who? what?",
    "aliquis": "someone, something", "quidam": "a certain one", "quisque": "each one", "quisquam": "anyone",
    "quilibet": "anyone at all", "quiuis": "anyone you will", "quicumque": "whoever, whatever",
    "quisquis": "whoever, whatever", "uterque": "each of two, both", "uter": "which of two",
    "neuter": "neither of two", "alter": "the other (of two)", "alius": "other, another", "nullus": "no, none",
    "ullus": "any", "nemo": "no one", "nihil": "nothing", "solus": "alone, only", "totus": "whole, all",
    "unus": "one", "duo": "two", "tres": "three", "ambo": "both", "mille": "a thousand",
    "unusquisque": "each one", "domus": "house, home", "meus": "my, mine", "tuus": "your (sing.)",
    "suus": "his, her, its, their own", "noster": "our", "uester": "your (plur.)",
    "et": "and", "atque": "and, and also", "ac": "and, and also", "sed": "but", "autem": "but, moreover",
    "enim": "for", "nam": "for", "namque": "for indeed", "etenim": "for indeed", "ergo": "therefore",
    "igitur": "therefore", "itaque": "and so, therefore", "quia": "because, that", "quoniam": "since, because, that",
    "ut": "that, so that; as", "uti": "that, so that", "nec": "nor, and not", "neque": "nor, and not",
    "si": "if", "nisi": "unless, except", "sin": "but if", "tamen": "yet, nevertheless", "quasi": "as if, as it were",
    "tamquam": "as, just as", "sicut": "just as", "uel": "or", "aut": "or", "an": "or (in questions)",
    "num": "whether; surely not", "uero": "truly, but", "at": "but", "dum": "while, until", "donec": "until",
    "quando": "when", "postquam": "after", "antequam": "before", "priusquam": "before", "quamquam": "although",
    "quamuis": "although", "quin": "but that, that not", "que": "and (enclitic)", "quod": "that, because",
    "cum": "with (prep.); when, since (conj.)", "quam": "how, than, as", "non": "not", "ne": "not; that not, lest",
    "haud": "not", "nonne": "not? (expecting yes)", "numquid": "surely not? (expecting no)", "quidem": "indeed",
    "ecce": "behold", "o": "O!", "amen": "amen, truly", "alleluia": "alleluia, praise the Lord", "uae": "woe",
    "in": "in, into, on", "ad": "to, toward, at", "de": "from, down from, concerning", "ex": "out of, from",
    "e": "out of, from", "ab": "from, by", "per": "through", "pro": "for, on behalf of, before",
    "sub": "under", "super": "above, upon, over", "inter": "between, among", "ante": "before", "post": "after, behind",
    "apud": "with, at the house of", "contra": "against", "coram": "in the presence of", "propter": "because of",
    "secundum": "according to", "sine": "without", "usque": "up to, as far as", "iuxta": "near, according to",
    "circa": "around, about", "trans": "across", "ultra": "beyond", "praeter": "beyond, besides",
    "aduersus": "against, toward, opposite to", "necnon": "and also, and moreover", "usquequo": "how long?, until when",
    "huiuscemodi": "of this kind, such", "huiusmodi": "of this kind, such", "quispiam": "anyone, anything, someone",
    "eiusmodi": "of that kind, such", "necdum": "and not yet, not yet", "nequando": "lest at any time",
    "quoadusque": "until, as long as", "tantummodo": "only, merely", "nihilominus": "nevertheless, nonetheless",
    "nudiustertius": "the day before yesterday, two days ago", "alioqui": "otherwise, else",
    "alteruter": "one of the two, either", "usquequaque": "everywhere, on all sides, altogether",
    "dummodo": "provided that, so long as", "paulominus": "a little less, almost",
    "quinimmo": "nay rather, indeed, even more",
    "subintroeo": "to enter secretly, slip in (sub + intro + eo)",
}
# Glosses for L&S entries (by L&S key) whose Perseus XML prints no English rendering at the head of the
# main sense (the meaning is only implied by the citations), so extraction would return a secondary sense;
# each is the entry's own wording where it has one.
_GLOSS_OVERRIDE: Dict[str, str] = {
    "facio": "to make, do", "do1": "to give", "dico2": "to say, speak, tell", "pono": "to put, place, set",
    "civitas": "citizenship; the state; a city", "homo": "a human being, man", "deus": "a god, deity; God",
    "manus1": "a hand", "anima": "air, breath; the soul, life", "spiritus": "breath, air; the spirit, soul",
    "annus": "a year", "dies": "a day", "habito": "to dwell, live, abide", "lex": "a law", "ignis": "fire",
    "praecipio": "to take beforehand; to instruct, enjoin, order", "os1": "the mouth; the face",
    "comedo1": "to eat up, consume, devour", "vero1": "in truth, truly; but, however",
    "cunctus": "all together, the whole, all", "bonus": "good", "rex1": "a king, ruler", "magnus1": "great, large",
    "sanctus": "sacred, inviolable; holy, divine", "credo": "to trust, believe; to entrust", "dormio": "to sleep",
    "semen": "seed", "mensis": "a month", "templum": "a temple, sanctuary", "liber4": "a book",
    "desertus": "deserted, desert; a desert", "quattuor": "four", "vas2": "a vessel, dish; a utensil",
    "coepio": "to begin", "Abraham": "Abraham, the patriarch", "claudo1": "to shut, close",
    "candelabrum": "a candlestick, lampstand", "juro": "to swear, take an oath", "nego": "to say no, deny, refuse",
    "sacrifico": "to make or offer a sacrifice, to sacrifice", "puteus": "a well, pit",
    "benefacio": "to do well, do good, benefit", "famulus1": "a servant, slave", "fabricor": "to frame, build, forge",
    "spica": "a point; an ear of grain", "corruptio": "a corrupting, corruption", "rete": "a net",
    "operimentum": "a covering, cover, lid",
}
# cum (prep., L&S cum1) and cum (conj., L&S cum2) are both non-content words; they are kept apart and
# only the contextual rules in _context_rule() choose between them.

# Vulgate spelling variants tried only when a word has no analysis at all (documented normalisations).
_VARIANT_RULES: List[Tuple[str, str]] = [
    ("y", "i"), ("i", "y"), ("ch", "c"), ("th", "t"), ("ph", "p"), ("mpt", "nt"), ("nt", "mpt"), ("oe", "e"),
    ("e", "oe"), ("ae", "e"), ("e", "ae"), ("oe", "ae"), ("ae", "oe"), ("quot", "cot"), ("cot", "quot"),
    ("h", ""), ("ss", "s"), ("xs", "x"), ("x", "xs"), ("mn", "n"), ("ll", "l"), ("l", "ll"), ("ii", "i"),
    ("i", "ii"), ("cc", "c"), ("e", "i"),          # poenitentia ~ paenitentia, caeremonia ~ caerimonia
    ("nn", "n"),                                   # annulus ~ anulus (L&S: 'ānŭlus (not ann-)')
    ("tt", "t"),                                   # littore / littus ~ litus, quattuor ~ quatuor
    ("intellig", "intelleg"), ("neglig", "negleg"),  # Vulgate intelligo / negligo = L&S intellego / neglego
    ("adolesc", "adulesc"),                        # Vulgate adolescentia = L&S adulescentia
    ("sexc", "sesc"),                              # Vulgate sexcentos / sexcenta = L&S sescenti
    ("moniment", "monument"),                      # Vulgate monimentum = L&S monumentum
    ("reper", "repper"), ("repul", "reppul"),      # Vulgate repererunt / repulisti = L&S repperi / reppuli
]
# Results of a variant that are function words are never accepted ('hin', the Hebrew measure, is not 'in')
_VARIANT_NO_FUNCTION = True
_PREFIX_VARIANTS: List[Tuple[str, str]] = [
    ("aff", "adf"), ("adf", "aff"), ("acc", "adc"), ("adc", "acc"), ("agg", "adg"), ("all", "adl"), ("adl", "all"),
    ("ann", "adn"), ("adn", "ann"), ("app", "adp"), ("adp", "app"), ("arr", "adr"), ("adr", "arr"),
    ("ass", "ads"), ("ads", "ass"), ("att", "adt"), ("adt", "att"), ("aqu", "adqu"), ("adqu", "aqu"),
    ("coll", "conl"), ("conl", "coll"), ("comm", "conm"), ("conm", "comm"), ("comp", "conp"), ("conp", "comp"),
    ("corr", "conr"), ("conr", "corr"), ("comb", "conb"), ("conb", "comb"), ("ill", "inl"), ("inl", "ill"),
    ("imm", "inm"), ("inm", "imm"), ("imp", "inp"), ("inp", "imp"), ("irr", "inr"), ("inr", "irr"),
    ("imb", "inb"), ("inb", "imb"), ("occ", "obc"), ("obc", "occ"), ("off", "obf"), ("obf", "off"), ("opp", "obp"), ("obp", "opp"),
    ("succ", "subc"), ("suff", "subf"), ("sugg", "subg"), ("summ", "subm"), ("subm", "summ"),
    ("supp", "subp"), ("subp", "supp"), ("surr", "subr"), ("subr", "surr"), ("eff", "exf"), ("diff", "disf"),
    ("disr", "dir"), ("transd", "trad"), ("adpl", "appl"), ("adcl", "accl"), ("adtr", "attr"), ("inch", "incoh"),
    ("exs", "ex"), ("ex", "exs"), ("sus", "subs"), ("subs", "sus"), ("tra", "trans"), ("trans", "tra"),
]


# ---------------------------------------------------------------------------
# 4.  The index
# ---------------------------------------------------------------------------

class _Lemma:
    __slots__ = ("key", "lemma", "pos", "gloss", "size", "ls_type", "proper", "source", "noncontent",
                 "etym", "bracket", "hyph", "pa_of", "lead", "hb", "lskey", "n")

    def __init__(self, key: str, lemma: str, pos: str, gloss: str, size: int, ls_type: str, proper: bool,
                 source: str, hb: str, lskey: str = "", n: str = ""):
        self.key = key
        self.lemma = lemma
        self.pos = pos
        self.gloss = gloss
        self.size = size
        self.ls_type = ls_type
        self.proper = proper
        self.source = source
        self.noncontent = pos in _NONCONTENT_POS
        self.etym = ""
        self.bracket = ""
        self.hyph = ""
        self.pa_of = ""
        self.lead = ""
        self.hb = hb
        self.lskey = lskey
        self.n = n


class _Index:
    def __init__(self) -> None:
        self.lemmas: List[_Lemma] = []
        self.by_key: Dict[str, int] = {}
        self.stems: Dict[str, List[Tuple[int, str]]] = defaultdict(list)
        self.exact: Dict[str, List[Tuple[int, str]]] = defaultdict(list)
        self.headwords: Dict[str, List[int]] = defaultdict(list)       # bare headword -> lemma ids (L&S)
        self.prior: Dict[int, float] = {}
        self.prior_lower: Dict[int, int] = {}    # unambiguous lower-case tokens per lemma
        self.lex: Dict[str, LemmaEntry] = {}
        self.cap_lower: Counter = Counter()      # bare form -> lowercase occurrences in the Studio text
        self.cap_mid: Counter = Counter()        # bare form -> capitalised, not sentence-initial occurrences
        self.ana_cache: Dict[str, List[Tuple[int, str, str]]] = {}
        self.canon: Dict[int, int] = {}          # spelling doublet -> the lemma kept
        self.slot: Counter = Counter()           # (paradigm code, ending) -> unambiguous corpus tokens
        self.fam_total: Counter = Counter()      # paradigm family -> unambiguous corpus tokens
        self.fam_slots: Counter = Counter()      # paradigm family -> number of distinct slots
        self.lemma_fam: Dict[int, str] = {}      # lemma id -> family of its first paradigm stem
        self.closed_n: Counter = Counter()       # lemma id -> number of closed-list forms
        self.closed_form: Counter = Counter()    # (lemma id, bare form) -> unambiguous corpus tokens
        self.plural_only: Set[int] = set()       # lemmas with a plural-only paradigm (Athenae, Jerosolyma)
        self.cap_any: Counter = Counter()        # bare form -> capitalised occurrences in the Studio text
        self.cap_surface: Dict[str, str] = {}    # bare form -> its commonest capitalised spelling
        self.tipnr: Optional["_TipnrIndex"] = None                    # TIPNR individuals by verse
        self.name_occ: Dict[int, List[Tuple[str, int, int]]] = defaultdict(list)   # name lemma -> its verses

    def add_lemma(self, lem: _Lemma) -> int:
        if lem.key in self.by_key:
            return self.by_key[lem.key]
        self.lemmas.append(lem)
        i = len(self.lemmas) - 1
        self.by_key[lem.key] = i
        return i

    def add_stems(self, i: int, stems: Iterable[Tuple[str, str]], exact: Iterable[str], tag: str = "x") -> None:
        for st, pc in stems:
            if st:
                self.stems[st].append((i, pc))
                if i not in self.lemma_fam:
                    self.lemma_fam[i] = _FAMILY.get(pc, "V")
                if pc in ("N1PL", "N2PLM", "N2PLN", "N3PL", "N3PLN", "A12PL"):
                    self.plural_only.add(i)
        for f in exact:
            if f:
                self.exact[f].append((i, tag))
                if tag == "closed":
                    self.closed_n[i] += 1

    # -- analysis ---------------------------------------------------------
    def analyse(self, b: str) -> List[Tuple[int, str, str]]:
        """All (lemma id, paradigm code, ending) analyses of a bare form (exact forms: ending '')."""
        hit = self.ana_cache.get(b)
        if hit is not None:
            return hit
        out: List[Tuple[int, str, str]] = [(i, tag, "") for i, tag in self.exact.get(b, ())]
        stems = self.stems
        for k in range(1, len(b) + 1):
            lst = stems.get(b[:k])
            if lst:
                end = b[k:]
                for i, pc in lst:
                    if end in ENDINGS[pc]:
                        out.append((i, pc, end))
        uniq = list(dict.fromkeys(out))
        self.ana_cache[b] = uniq
        return uniq


_INDEX: Optional[_Index] = None


def _lemma_key(plain: str, n: str, dup: bool) -> str:
    base = plain if plain[:1].isupper() else plain.lower()
    return f"lat:{base}#{n}" if dup and n else f"lat:{base}"


def _resolve_alias_target(idx: _Index, raw_target: str) -> Optional[int]:
    t = _b(raw_target)
    ids = idx.headwords.get(t)
    if not ids:
        return None
    return max(ids, key=lambda i: idx.lemmas[i].size)


def _build_index(raw_entries: List[dict], tipnr: List[Tuple[str, str]]) -> _Index:
    idx = _Index()
    # --- 1. select usable entries ------------------------------------------------
    usable = []
    for r in raw_entries:
        if r["type"] == "spur":
            continue
        plain = _plain(r["head"])
        if not plain or plain.startswith("-") or plain.endswith("-"):
            continue
        if re.fullmatch(r"[A-Z]\d*", r["key"]):
            continue                                  # the letters of the alphabet
        if "in composition" in " ".join(r["itype"]) or "inseparable" in r["lead"][:120]:
            continue
        usable.append((r, plain))
    # homograph numbering only where more than one usable entry shares a spelling
    spell = Counter()
    for r, plain in usable:
        spell[plain.replace("-", "")] += 1
    all_heads = {_b(plain.replace("-", "")) for r, plain in usable}
    real_heads = {_b(plain.replace("-", "")) for r, plain in usable if r["size"] >= 400}
    # --- 2. lemmas + paradigms ------------------------------------------------------
    sub_index: Dict[str, List[Tuple[int, List]]] = defaultdict(list)   # derived word -> (parent entry, glosses)
    pointers: Dict[int, List[str]] = {}                                 # gloss-less entry -> words it points to
    pending_alias: List[Tuple[int, str, dict]] = []
    stubs: List[Tuple[int, str]] = []
    part_stubs: List[Tuple[int, str]] = []
    adv_stubs: List[Tuple[int, str]] = []
    for r, plain in usable:
        word = plain.replace("-", "")
        hb = _b(word)
        if not hb:
            continue
        proper = word[:1].isupper()
        lspos = r["pos"] or r.get("mpos", "")
        if r["pos"] and r.get("mpos") and r["pos"] not in re.sub(r"\[[^\[\]]*\]", " ", r["lead"]):
            # the <pos> element sits inside the bracketed etymology ('prīmus, a, um, adj. sup. [obsol. prep. pri
            # ...]'): the part of speech is the one printed after the head ('adj. sup.'), not 'prep.'
            lspos = r["mpos"]
        pos = _map_pos(lspos)
        g = _gender(r["gen"]) or r.get("mgen", "")
        if not g and r["key"] in ("Aethiops", "obryzum", "sinapi"):
            g = "m" if r["key"] == "Aethiops" else "n"
        parts: List[str] = list(_HEAD_FIX.get(r["key"]) or r.get("mparts") or [])
        if not parts and r["itype"]:
            parts = [p.strip() for p in re.split(r",|;|\s+(?:and|or)\s+", r["itype"][0]) if p.strip()]
        indecl = bool(r.get("mindecl")) or "indecl" in " ".join(r["itype"])
        key = _lemma_key(word, r["n"], spell[word] > 1)
        if key in idx.by_key:          # I/J duplicates (Iesus / Jesus) keep the first
            key = key + "~" + r["key"]
        gloss = _GLOSS_OVERRIDE.get(r["key"]) or _compose_gloss(r["gloss"], all_heads, proper)
        lem = _Lemma(key, word, pos, gloss, r["size"], r["type"], proper, LS_SOURCE, hb, r["key"], r["n"])
        lem.etym = r["etym"]
        lem.bracket = r["bracket"]
        lem.hyph = _b(plain.split("-")[0]) if "-" in plain else ""
        lem.lead = r["lead"]
        m = re.search(r"P\. a\.,?\s*(?:of|from)\s+(\d\.\s*)?([^\s,.;:]+)", r["lead"]) or \
            re.search(r"v\.\s+(\d\.\s*)?([^\s,.;:]+)\s*,?\s*P\. a\.", r["lead"])
        if m:
            lem.pa_of = ((m.group(1) or "").replace(".", "").strip() + " " + _plain(m.group(2))).strip()
        # pure cross-reference entries ("Moyses, v. Moses." / "a, prep. = ab, v. ab.")
        rest = r["lead"]
        hplain = re.sub(r"\s+", " ", r["head"]).strip()
        if rest.startswith(hplain):
            rest = rest[len(hplain):]
        alias = None
        if not parts and not g:
            ma = re.fullmatch(r"[\s,]*(?:(?:prep|adv|conj|interj)\.\s*)?(?:=\s*([^\s,.;]+)\s*,?\s*)?v\.\s*(?:\d\.\s*)?"
                              r"([^\s,.;]+)\s*\.?\s*", rest)
            if ma and (ma.group(1) is None or _b(ma.group(1)) == _b(ma.group(2))):
                alias = ma.group(2)
            else:
                ma_lc = re.search(r"less\s+correct\s+form\s+for\s+(?:\d\.\s*)?([^\s,.;]+)", rest, re.I)
                if ma_lc:
                    alias = ma_lc.group(1)
        if word.lower() in _COMPARISON_ALIASES:
            alias = _COMPARISON_ALIASES[word.lower()]
        i = idx.add_lemma(lem)
        idx.headwords[hb].append(i)
        for sb, sruns in r.get("sub") or ():
            sub_index[sb].append((i, sruns))
        if not gloss:
            pointers[i] = [_b(_plain(t)) for t in
                           re.findall(r"(?:\bv\.|\bfrom|\bof)\s+(?:\d\.\s*)?([A-Za-zĀ-ſ^\-]+)", r["lead"][:220])]
        if alias:
            pending_alias.append((i, alias, r))
            continue
        if r["size"] < 260 and not proper and "P. a." not in r["lead"] and hb.endswith(("tus", "sus", "xus")):
            mp = re.search(r",\s*a,\s*um\.?,?\s+Part\.?,?\s*(?:of|from|v\.)\s*(?:\d\.\s*)?([A-Za-zĀ-ſ\-]+)"
                           r"(?:\s+fin)?\.?\s*$", r["lead"].strip())
            if mp and _b(_plain(mp.group(1))) in real_heads:
                # pure perfect-participle stub ('nescītus, a, um, Part. of nescio.', 'caesus, a, um, Part., v. caedo.'),
                # no P. a.: the verb's own VPP paradigm generates its forms, so do not emit duplicate A12 stems
                part_stubs.append((i, mp.group(1)))
                continue
        if r["size"] < 400:          # L&S stub that only points elsewhere: 'vallis, is, v. valles.'
            ms = re.search(r"\bv\.\s*(?:\d\.\s*)?([A-Za-zĀ-ſ^\-]+)\s*(?:init|fin)?\.?(?:\s+and\s+[IVX]+\.(?:\s*\d+\.)?)?"
                           r"\s*$", r["lead"].strip())
            if ms:
                stubs.append((i, ms.group(1)))
            ma2 = re.match(r"^[^,]{1,30},\s*(?:temp\.\s*)?adv\.,?\s*v\.\s*(?:\d\.\s*)?([A-Za-zĀ-ſ^\-]+)", r["lead"].strip())
            if ma2:
                adv_stubs.append((i, ma2.group(1)))
        stems: List[Tuple[str, str]] = []
        exact: List[str] = []
        # alternative spellings at the head of the entry share the paradigm, but not fragments ('emt-'),
        # other full headwords ('at' under ad, 'cor' under cur, 'nec' under neque) or other case forms
        # ('concordis' under concors); allow alt spellings whose own entry is only a tiny stub (spiritualis)
        spellings = [hb]
        alt_exact: List[str] = []
        for a in r["alts"]:
            a = a.strip()
            if not a or a.endswith("-") or a.startswith("-"):
                continue
            ab = _b(_plain(a).replace("-", ""))
            if len(ab) < 3 or ab[:1] != hb[:1]:
                continue
            if ab in real_heads or (ab in all_heads and ab.replace("y", "i") == hb.replace("y", "i")):
                continue
            if ab.startswith(hb) and 0 < len(ab) - len(hb) <= 2:
                alt_exact.append(ab)          # 'altar and altāre': the second nominative form
                continue
            if (hb.endswith("iens") and ab == hb[:-4] + "ies") or \
                    (hb.endswith("ienscumque") and ab == hb[:-10] + "iescumque"):
                alt_exact.append(ab)          # 'quotiens or quoties', 'quinquiens or quinquies', 'centiens or centies'
                continue
            if ab[-2:] != hb[-2:] or abs(len(ab) - len(hb)) > 3:
                continue
            spellings.append(ab)
        spellings = list(dict.fromkeys(spellings))
        btoks = [_b(p) for p in parts]
        its = " ".join(parts)
        verbish = pos == "V" or any(re.fullmatch(r"[1-4]", p) for p in parts) or \
            bool(re.search(r"(?:āvi|ēvi|īvi|ŭi|ui|xi|si|ātum|ītum|ĭtum|ctum|sum|ātus|ītus|ĭtus|āre|ēre|ĕre|īre|āri|ēri)\b",
                           its))
        adjish = len(btoks) >= 2 and (btoks[:2] == ["a", "um"] or (btoks[0].endswith("a") and btoks[1].endswith("um"))
                                      or (btoks[0].endswith("is") and btoks[1].endswith("e"))
                                      or btoks[:2] == ["ae", "a"]) or (btoks[:1] == ["e"] and hb.endswith("is")) \
            or (btoks[:1] == ["a"] and hb.endswith("us")) or (btoks[:1] == ["ius"] and hb.endswith("ior"))
        itype_parts = [p.strip() for p in re.split(r",|;|\s+(?:and|or)\s+", r["itype"][0]) if p.strip()] \
            if r["itype"] else []
        no_perf = "no perf" in r["lead"].lower()
        done = False
        for sp in spellings:
            res = None
            if pos in ("ADJ", "NUM") or (not g and adjish):
                ra = _adj_stems(sp, parts)
                if ra:
                    res = (ra[0], ra[1])
                    if lem.pos not in ("NUM",):
                        lem.pos = "ADJ"
            if res is None and verbish and not g and sp.endswith(("o", "or")):
                intrans = bool(re.match(r"v\.\s*n\.(?!\s*(?:and|et|or|&)\s*a\.)", lspos or "")) and \
                    "orig. v. n." not in r["lead"][:120] and "Part.:" not in r["lead"]
                res = _verb_stems(sp, parts, lem.hyph, intrans, no_perf)
                if res:
                    lem.pos = "V"
            if res is None and (parts or indecl) and (g or pos in ("", "N") or proper):
                res = _noun_stems(sp, parts, g, proper, indecl)
                if res is None and itype_parts and itype_parts != parts:
                    res = _noun_stems(sp, itype_parts, g, proper, indecl)
                if res:
                    lem.pos = "PROPN" if proper else "N"
            if res is None and pos in ("ADV", "PREP", "CONJ", "INTERJ", "PRON", "NUM"):
                res = ([], [sp])
            if res is None and indecl:
                res = ([], [sp])
                lem.pos = lem.pos or ("PROPN" if proper else "N")
            if res is None and proper and g and not parts:
                res = ([], [sp])
                lem.pos = "PROPN"
            if res is None and sp.endswith("et") and len(sp) > 4 and (verbish or "impers" in r["lead"][:80]):
                res = ([(sp[:-2], "VIMP2")], [])          # impersonal: oportet, licet, decet, paenitet
                lem.pos = "V"
            if res is not None:
                stems += res[0]
                exact += res[1]
                done = True
        if proper and lem.pos not in ("PROPN",):
            lem.pos = "PROPN"
        if lem.pos == "":
            lem.pos = "X"
        # the content flag follows the final part of speech (it was set from the first reading of the head:
        # primus, read as 'prep.' from its etymology, stayed a function word after becoming ADJ)
        lem.noncontent = lem.pos in _NONCONTENT_POS
        if done:
            idx.add_stems(i, dict.fromkeys(stems), dict.fromkeys(exact + alt_exact))
    # --- 2a-bis. structured L&S sub-entries inside <sense> (cilicium, baptismus, Hebraeus, Hebraicus, Hebraice,
    # Judaicus, Judaice, Leviticus, Syriace, beneplacitum, coccinum, aperte, abundanter, Babylonius, Palaestinus,
    # Spartiates ...): added only when no active top-level entry exists and no plural-only duplicate is created
    _PLURAL_ONLY_PCS = {"N1PL", "N2PLM", "N2PLN", "N3PL", "N3PLN", "A12PL"}
    real_non_stub = {idx.lemmas[k].hb for k in range(len(idx.lemmas))
                     if idx.lemmas[k].pos not in ("X", "ALIAS")}
    for r, plain in usable:
        sub_ents = r.get("sub_entries") or []
        if not sub_ents:
            continue
        pword = plain.replace("-", "")
        p_hb = _b(pword)
        p_ids = idx.headwords.get(p_hb, [])
        p_lem = idx.lemmas[p_ids[0]] if p_ids else None
        for sub_word, sparts, sgen, spos, sgloss in sub_ents:
            shb = _b(sub_word)
            if not shb or shb in real_non_stub:
                continue
            s_proper = sub_word[:1].isupper() and not (spos.lower().startswith("adv") and shb.endswith("ice"))
            sg = _gender([sgen]) if sgen else ""
            smpos = _map_pos(spos)
            sbtoks = [_b(p) for p in sparts]
            s_adjish = (len(sbtoks) >= 2 and sbtoks[:2] == ["a", "um"]) or (sbtoks[:1] == ["e"] and shb.endswith("is"))
            s_res = None
            final_pos = smpos
            if smpos == "ADV" or (spos.lower().startswith("adv") and not sparts):
                s_res = ([], [shb])
                final_pos = "ADV"
            elif smpos in ("ADJ", "NUM") or (not sg and s_adjish):
                ra = _adj_stems(shb, sparts)
                if ra:
                    s_res = (ra[0], ra[1])
                    final_pos = "ADJ"
            if s_res is None and sparts and (sg or smpos in ("", "N") or s_proper):
                s_res = _noun_stems(shb, sparts, sg, s_proper, False)
                if s_res:
                    final_pos = "PROPN" if s_proper else "N"
            if s_res is None:
                continue
            if any(pc in _PLURAL_ONLY_PCS for _st, pc in s_res[0]):
                continue
            # Do not add a sub-entry whose paradigm stem collides with an existing stem (e.g. Chaldaeus/Chaldaea
            # colliding with Chaldaei, Macedonius colliding with Macedonia, beatum colliding with beatus)
            if any(st in idx.stems for st, _pc in s_res[0]) and shb != "cilicium":
                continue
            # Do not introduce a sub-entry that collides with an already-analysable form (unless it is an adverb
            # whose only existing analysis is a masc. vocative in -e, or lowercase cilicium vs proper Cilices)
            existing_anas = [(idx.canon.get(k, k), pc, e) for k, pc, e in idx.analyse(shb)
                             if idx.lemmas[idx.canon.get(k, k)].pos not in ("X", "ALIAS")]
            if existing_anas and shb != "cilicium":
                if final_pos == "ADV" and all(pc in _ADJ_OR_PART and e == "e" for _k, pc, e in existing_anas):
                    pass
                else:
                    continue
            if s_proper and final_pos not in ("PROPN",):
                final_pos = "PROPN"
            skey = "lat:" + (sub_word.lower() if not s_proper else sub_word)
            if skey in idx.by_key:
                # replace tiny stub ('Cilicium, v. Cilicia.') with its structured sub-entry paradigm
                existing = idx.by_key[skey]
                if idx.lemmas[existing].pos in ("X", "ALIAS"):
                    idx.lemmas[existing].pos = final_pos
                    idx.lemmas[existing].proper = s_proper
                    idx.lemmas[existing].noncontent = final_pos in _NONCONTENT_POS
                    if sgloss and (not idx.lemmas[existing].gloss or idx.lemmas[existing].gloss == "proper name"):
                        idx.lemmas[existing].gloss = sgloss
                    idx.add_stems(existing, dict.fromkeys(s_res[0]), dict.fromkeys(s_res[1]))
                    idx.ana_cache.pop(shb, None)
                    real_non_stub.add(shb)
                continue
            g_text = sgloss or (f"from {pword} ({p_lem.gloss[:48]})" if (p_lem and p_lem.gloss) else f"from {pword}")
            slem = _Lemma(skey, sub_word.lower() if not s_proper else sub_word, final_pos, g_text,
                          min(r["size"] // 3, 600), "sub", s_proper, LS_SOURCE, shb, r["key"] + ":" + shb, "")
            slem.etym = pword
            si = idx.add_lemma(slem)
            idx.headwords[shb].append(si)
            idx.add_stems(si, dict.fromkeys(s_res[0]), dict.fromkeys(s_res[1]))
            idx.ana_cache.pop(shb, None)
            real_non_stub.add(shb)
    idx.ana_cache.clear()
    # --- 2a-ter. documented Vulgate nouns/adverbs/verbs absent as standalone headwords from Perseus L&S XML
    for v_word, v_pos, v_stems, v_exact, v_gloss in (
        ("gazophylacium", "N", [("gazophylaci", "N2N")], (), "treasury, treasury chamber (Greek γαζοφυλάκιον)"),
        ("terraemotus", "N", [("terraemot", "N4")], (), "earthquake (terrae motus)"),
        ("cilicium", "N", [("cilici", "N2N")], (), "haircloth, sackcloth (made of Cilician goats' hair; L&S s.v. Cilicia)"),
        ("subcinericius", "ADJ", [("subcinerici", "A12")], (), "baked under the ashes (sub + cinis; L&S s.v. cinis)"),
        ("supradictus", "ADJ", [("supradict", "A12")], (), "aforesaid, mentioned above (supra + dico)"),
        ("appropio", "V", [("appropi", "V1N"), ("appropi", "V1A"), ("appropi", "V1P"), ("appropiau", "VPF"),
                           ("appropia", "VSY"), ("appropiat", "VPP")], (), "to draw near, approach (Vulgate form of appropinquo)"),
        ("redditus#2", "N", [("reddit", "N4")], (), "return, revenue, income (reddo)"),
        ("stacte", "N", [("stact", "N1GE")], (), "oil of myrrh, stacte (Greek στακτή)"),
        ("judaice", "ADV", (), ("iudaice",), "in the Jewish language or manner (L&S s.v. Judaea)"),
        ("syriace", "ADV", (), ("syriace",), "in the Syrian/Aramaic tongue (L&S s.v. Syria)"),
        ("clementer", "ADV", (), ("clementer",), "mildly, gently, mercifully (L&S s.v. clemens)"),
        ("spiritualiter", "ADV", (), ("spiritualiter",), "spiritually (spiritus)"),
        ("beneplacitum", "N", [("beneplacit", "N2N")], (), "good pleasure, favour, will (bene + placeo)"),
        ("valefacio", "V", [("ualefac", "V3IA"), ("ualefac", "V3IN"), ("ualefec", "VPF"), ("ualefact", "VPP")],
         ("ualefac",), "to bid farewell, say goodbye (vale + facio)"),
        ("Hebraeus", "PROPN", [("hebrae", "A12")], (), "Hebrew (L&S s.v. Hebraei)"),
        ("Africus", "PROPN", [("afric", "A12")], (), "southwest wind; African (L&S s.v. Africa)"),
        ("collyrida", "N", [("collyrid", "N1")], (), "cake, bun (Greek κολλυρίς)"),
        ("brachiolum", "N", [("brachiol", "N2N")], (), "small arm; bracelet, armlet (dim. of bracchium)"),
        ("manufactus", "ADJ", [("manufact", "A12")], (), "made with hands, handmade (manus + facio)"),
        ("ascella", "N", [("ascell", "N1")], (), "armpit (Vulgate variant of axilla)"),
        ("carica", "N", [("caric", "N1")], (), "dried fig, Carian fig (L&S s.v. Caria)"),
        ("pugillus", "N", [("pugill", "N2")], (), "handful (dim. of pugnus)"),
        ("compluo", "V", [("complu", "V3A"), ("complu", "VPF"), ("complut", "VPP")], (), "to rain upon (con + pluo)"),
    ):
        vkey = "lat:" + v_word
        if vkey not in idx.by_key:
            vplain = v_word.split("#")[0]
            vn = v_word.split("#")[1] if "#" in v_word else ""
            vi = idx.add_lemma(_Lemma(vkey, vplain, v_pos, v_gloss, 0, "closed", vplain[:1].isupper(),
                                      CLOSED_SOURCE, _b(vplain), "", vn))
            idx.headwords[_b(vplain)].append(vi)
            idx.add_stems(vi, v_stems, v_exact)
        elif v_word == "cilicium":
            vi = idx.by_key[vkey]
            idx.lemmas[vi].pos = "N"
            idx.lemmas[vi].proper = False
            idx.lemmas[vi].gloss = v_gloss
            idx.add_stems(vi, v_stems, v_exact)
    # --- 2b. entries without a rendering of their own ('sanctus, a, um, Part. and P. a. of sancio';
    # 'mandatum, i, n., v. 1. mando fin.') take the rendering L&S gives for that word inside the entry
    # it points to ('Hence, sanc-tus, a, um, P. a. ... rendered sacred, ...')
    for i, ptr in pointers.items():
        lem = idx.lemmas[i]
        cands = sub_index.get(lem.hb)
        if lem.gloss or not cands:
            continue
        targets = {p for p in ptr if p}
        pick = [c for c in cands if idx.lemmas[c[0]].hb in targets]
        if not pick and len({c[0] for c in cands}) == 1:
            pick = cands
        for _parent, sruns in pick:
            g = _compose_gloss(sruns, all_heads, lem.proper)
            if g:
                lem.gloss = g
                break
    def is_latin(w: str) -> bool:        # a Latin headword or an analysable Latin form
        return w in all_heads or (len(w) > 2 and bool(idx.analyse(w)))

    for i in pointers:                   # still nothing: the plain-text rendering after the head, if any
        lem = idx.lemmas[i]
        if not lem.gloss and lem.size >= 120:
            lem.gloss = _lead_gloss(lem.lead, is_latin, lem.proper)
    idx.ana_cache.clear()
    # cross-reference stubs: 'haerēdĭtas, ātis, v. hereditas' takes the gloss of the entry it names;
    # 'valdē, adv., v. validus fin.' is described as the adverb of that entry
    for _round in range(2):
        for i in pointers:
            lem = idx.lemmas[i]
            if lem.gloss:
                continue
            lead = lem.lead.strip()
            kind = ""
            m = re.search(r"\bPart\.(?:\s+and\s+P\.\s*a\.)?,?\s*(?:v\.|from|of)\s*(?:\d\.\s*)?([A-Za-zĀ-ſ\-]+)", lead)
            if m:
                kind, target = "part", m.group(1)        # 'conspersus, a, um, Part., from conspergo.'
            else:
                m = re.match(r"^[^,]{1,30},\s*(adv\.,?\s*)?(?:[^,]{1,14},\s*){0,3}(?:temp\.\s*)?(adv\.,?\s*)?"
                             r"v\.\s*(?:\d\.\s*)?([A-Za-zĀ-ſ\-]+)(\.?)", lead)
                if not m:
                    continue
                kind = "adv" if (m.group(1) or m.group(2)) else "same"
                target = m.group(3)
                if m.group(4) and len(_b(target)) < len(lem.hb) and _resolve_alias_target(idx, _plain(target)) is None:
                    # 'praelĭum, ..., v. proel.': L&S abbreviates the other spelling
                    target = _b(target) + lem.hb[len(_b(target)):]
            j = _resolve_alias_target(idx, _plain(target))
            if j is None or j == i or not idx.lemmas[j].gloss:
                continue
            tg = idx.lemmas[j].gloss
            first = re.split(r"[;,]", tg)[0].strip()
            if all(_b(w) in _GRAMMAR_LABELS for w in re.findall(r"[A-Za-z]+", first)):
                first = ""
            suffix = f" ({first})" if first else ""
            if kind == "adv":
                lem.gloss = f"adv. of {idx.lemmas[j].lemma}{suffix}"
            elif kind == "part":
                lem.gloss = f"part. of {idx.lemmas[j].lemma}{suffix}"
            else:
                lem.gloss = tg
    # --- 3. aliases share their target's lemma -------------------------------------------
    alias_targets = set()
    resolved_aliases: List[Tuple[int, int]] = []
    for i, target, r in pending_alias:
        j = _resolve_alias_target(idx, target)
        lem = idx.lemmas[i]
        if j is None or j == i:
            lem.pos = "X"
            continue
        lem.pos = "ALIAS"
        lem.source = idx.lemmas[j].key          # remember the target
        idx.exact[lem.hb].append((j, "alias"))
        if not lem.proper and lem.lemma.lower() not in _COMPARISON_ALIASES and len(lem.hb) >= 4:
            alias_targets.add(j)
            resolved_aliases.append((i, j))
    if alias_targets:
        stems_by_lem: Dict[int, List[Tuple[str, str]]] = defaultdict(list)
        for st, lst in idx.stems.items():
            for k, pc in lst:
                if k in alias_targets:
                    stems_by_lem[k].append((st, pc))
        for i, j in resolved_aliases:
            a_hb, z_hb = idx.lemmas[i].hb, idx.lemmas[j].hb
            if len(a_hb) == len(z_hb) and a_hb != z_hb:
                # 1- or 2-char spelling variant of the same length (obstupesco/obstipesco, ditio/dicio,
                # diversorium/deversorius? no, same len = 11: diuersorium/deuersorius!)
                diffs = [k for k in range(len(a_hb)) if a_hb[k] != z_hb[k]]
                if 1 <= len(diffs) <= 2 and diffs[0] >= 1 and a_hb[0] == z_hb[0] and \
                        not all({a_hb[k], z_hb[k]} == {"y", "i"} for k in diffs):
                    cut = diffs[-1] + 1
                    # if the last diff is in the final ending (diversorium vs deversorius), exclude the ending
                    if cut == len(a_hb) and a_hb.endswith("um") and z_hb.endswith("us"):
                        cut = diffs[0] + 1
                    if cut <= len(a_hb) - 2:
                        a_pre, z_pre = a_hb[:cut], z_hb[:cut]
                        copied = [(a_pre + st[len(z_pre):], pc) for st, pc in stems_by_lem.get(j, ())
                                  if st.startswith(z_pre)]
                        if copied:
                            idx.add_stems(j, dict.fromkeys(copied), ())
    # --- 4. closed lists -----------------------------------------------------------------
    _install_closed(idx)
    for key, forms in _NAME_FORMS.items():
        if key in idx.by_key:
            idx.add_stems(idx.by_key[key], (), forms, "extra")
    # --- 5. TIPNR names --------------------------------------------------------------------
    for name, desc in tipnr:
        b = _b(name)
        if not b or len(b) < 2:
            continue
        key = "lat:" + name
        if key in idx.by_key or any(idx.lemmas[k].proper for k in idx.headwords.get(b, ())):
            continue
        lem = _Lemma(key, name, "PROPN", desc, 0, "tipnr", True, TIPNR_SOURCE, b)
        i = idx.add_lemma(lem)
        idx.exact[b].append((i, "tipnr"))
    # drop duplicates in the exact lists
    for f, lst in list(idx.exact.items()):
        idx.exact[f] = list(dict.fromkeys(lst))
    # L&S spelling doublets without homograph numbers (Iesus / Jesus, Ioannes / Joannes): one lemma
    groups: Dict[Tuple[str, bool, str], List[int]] = defaultdict(list)
    for i, lem in enumerate(idx.lemmas):
        if lem.lskey and not lem.n and lem.pos not in ("ALIAS", "X"):
            groups[(lem.hb, lem.proper, lem.pos)].append(i)
    for ids in groups.values():
        if len(ids) < 2:
            continue
        keep = max(ids, key=lambda k: (("J" in idx.lemmas[k].lemma or "j" in idx.lemmas[k].lemma
                                        or "v" in idx.lemmas[k].lemma.lower()), idx.lemmas[k].size))
        for k in ids:
            if k != keep:
                idx.canon[k] = keep
    # stubs that are only another spelling of an entry of the same part of speech share its lemma
    # (vallis -> valles, caelus -> caelum); stubs for derived words (vero adv. 'v. verus') stay lemmas
    for i, target in stubs:
        j = _resolve_alias_target(idx, _plain(target))
        if j is None or j == i or i in idx.canon:
            continue
        a, z = idx.lemmas[i], idx.lemmas[j]
        fa, fz = idx.lemma_fam.get(i), idx.lemma_fam.get(j)
        # caelus (m.) = caelum (n.); 'cănes, is, v. canis' -> canis, whose own head gives no paradigm
        same_fam = fa == fz or {fa, fz} == {"N2", "N2N"} or (fz is None and fa is not None)
        if a.pos == z.pos and a.proper == z.proper and same_fam and \
                _common_prefix_len(a.hb, z.hb) >= max(3, len(a.hb) - 2):
            idx.canon[i] = idx.canon.get(j, j)
            if fz is None:
                idx.lemma_fam[j] = fa
    for a, z in _STUB_CANON.items():
        if a in idx.by_key and z in idx.by_key:
            idx.canon[idx.by_key[a]] = idx.by_key[z]
    # pure participle stubs ('nescītus, a, um, Part. of nescio.', no P. a.): mark ALIAS and point to their verb,
    # and ensure the target verb carries that VPP stem (e.g. ulciscor -> ultus, lavo -> lotus)
    closed_verbs = {h for h, _, _, _ in _CLOSED_VERBS} | {h for h, _, _ in _EO_COMPOUNDS} | \
        {h for h, _, _, _ in _FERO_COMPOUNDS}
    for i, target in part_stubs:
        j = _resolve_alias_target(idx, _plain(target))
        if j is not None and j != i and idx.lemmas[j].pos == "V":
            jc = idx.canon.get(j, j)
            idx.lemmas[i].pos = "ALIAS"
            idx.lemmas[i].source = idx.lemmas[jc].key
            idx.canon[i] = jc
            if idx.lemmas[jc].hb not in closed_verbs and len(idx.lemmas[i].hb) >= 4:
                vpp_st = idx.lemmas[i].hb[:-2]
                if (jc, "VPP") not in idx.stems.get(vpp_st, ()):
                    idx.add_stems(jc, [(vpp_st, "VPP")], ())
        else:
            idx.lemmas[i].pos = "X"
    # adverb stubs ('justē, adv., v. justus fin.') are described inside their base entry: they take half of
    # the base entry's size for the size prior instead of the stub's own few characters
    for i, target in adv_stubs:
        j = _resolve_alias_target(idx, _plain(target))
        if j is not None and j != i:
            idx.lemmas[i].size = max(idx.lemmas[i].size, idx.lemmas[j].size // 2)
    return idx


def _find_ls(idx: _Index, hb: str, n: str = "", want_pos: Tuple[str, ...] = ()) -> Optional[int]:
    ids = [i for i in idx.headwords.get(hb, []) if not idx.lemmas[i].proper and idx.lemmas[i].pos != "ALIAS"]
    if not ids:
        return None
    if n:
        for i in ids:
            if idx.lemmas[i].n == n:
                return i
    if want_pos:
        sel = [i for i in ids if idx.lemmas[i].pos in want_pos]
        if sel:
            ids = sel
    return max(ids, key=lambda i: idx.lemmas[i].size)


def _closed_lemma(idx: _Index, hb: str, n: str, pos: str, gloss: str = "") -> int:
    i = _find_ls(idx, hb, n)
    if i is None:
        key = "lat:" + hb
        if key in idx.by_key:
            i = idx.by_key[key]
        else:
            i = idx.add_lemma(_Lemma(key, hb, pos, gloss, 0, "closed", False, CLOSED_SOURCE, hb))
    lem = idx.lemmas[i]
    lem.pos = pos
    lem.noncontent = pos in _NONCONTENT_POS or hb == "sum"
    # a closed list replaces the generated paradigm of that lemma (reverse maps built once per index)
    rev = getattr(idx, "_rev_forms", None)
    if rev is None:
        rs: Dict[int, Set[str]] = defaultdict(set)
        rx: Dict[int, Set[str]] = defaultdict(set)
        for st, lst in idx.stems.items():
            for k, _pc in lst:
                rs[k].add(st)
        for f, lst in idx.exact.items():
            for k, _t in lst:
                rx[k].add(f)
        rev = idx._rev_forms = (rs, rx)
    for st in rev[0].pop(i, ()):
        idx.stems[st] = [(k, pc) for k, pc in idx.stems[st] if k != i]
    for f in rev[1].pop(i, ()):
        idx.exact[f] = [(k, t) for k, t in idx.exact[f] if k != i or t == "alias"]
    return i


def _install_closed(idx: _Index) -> None:
    # verbs
    for hb, n, pos, forms in _CLOSED_VERBS:
        i = _closed_lemma(idx, hb, n, pos)
        idx.add_stems(i, (), forms, "closed")
    for hb, pre, trans in _EO_COMPOUNDS:
        i = _closed_lemma(idx, hb, "", "V")
        forms = [pre + f for f in _EO]
        if trans:
            forms += [pre + f for f in _EO_PASS]
        idx.add_stems(i, (), forms, "closed")
    for hb, pres, perfs, sups in _FERO_COMPOUNDS:
        i = _closed_lemma(idx, hb, "", "V")
        forms = []
        for p in pres:
            forms += [p + f for f in _FERO_PRES]
        for p in perfs:
            forms += _perf(p + "tul")
        for p in sups:
            forms += _a12(p + "lat") + _a12(p + "latur") + [p + "latu"]
        idx.add_stems(i, (), forms, "closed")
    # pronouns and numerals
    for hb, n, pos, forms in _CLOSED_PRON:
        i = _closed_lemma(idx, hb, n, pos)
        idx.add_stems(i, (), forms, "closed")
    # irregular comparison
    for hb, forms in _IRREG_COMPARISON.items():
        i = _find_ls(idx, hb, "", ("ADJ",))
        if i is None:
            continue
        idx.add_stems(i, (), forms, "closed")
    # forms that L&S states but the regular paradigm cannot produce
    for hb_spec, forms in _EXTRA_FORMS.items():
        if "#" in hb_spec:
            hb_base, hb_n = hb_spec.split("#", 1)
            i = _find_ls(idx, _b(hb_base), hb_n)
        else:
            i = _find_ls(idx, _b(hb_spec))
        if i is not None:
            idx.add_stems(i, (), [_b(f) for f in forms], "extra")
            if idx.lemmas[i].pos in ("X", ""):        # an entry whose head gives no paradigm (canis, vicis)
                idx.lemmas[i].pos = "N"
    # adverbs whose L&S head is read as another part of speech ('praestō, adv. dat. from praestus'; 'immo'; 'revera')
    for hb, n in (("praesto", "1"), ("immo", ""), ("reuera", "")):
        i = _find_ls(idx, hb, n)
        if i is not None:
            idx.lemmas[i].pos = "ADV"
            if hb == "reuera":
                idx.lemmas[i].gloss = "in truth, in fact, really (re vera)"
            if (i, "x") not in idx.exact.get(hb, []):
                idx.exact[hb].append((i, "x"))
    # possessives keep their generated paradigm but are not content words
    for hb in _POSSESSIVES:
        i = _find_ls(idx, hb, "", ("ADJ", "PRON"))
        if i is not None:
            idx.lemmas[i].pos = "PRON"
            idx.lemmas[i].noncontent = True
    idx.exact["mi"].append((_find_ls(idx, "meus", "", ("PRON",)) or 0, "closed"))
    # function words: make sure the L&S headword is indexed with a POS and flagged non-content
    for hb, (n, pos) in _FUNCTION_WORDS.items():
        i = _find_ls(idx, _FUNCTION_HEAD.get(hb, hb), n)
        if i is None:
            key = "lat:" + hb
            i = idx.by_key.get(key)
            if i is None:
                i = idx.add_lemma(_Lemma(key, hb, pos, "", 0, "closed", False, CLOSED_SOURCE, hb))
        lem = idx.lemmas[i]
        if lem.pos in ("", "X", "ADV", "CONJ", "PREP", "PART", "INTERJ", "PRON") or hb in ("super", "quod", "cum",
                                                                                         "amen"):
            lem.pos = pos
        lem.noncontent = lem.pos in _NONCONTENT_POS
        if (i, "x") not in idx.exact.get(hb, []) and (i, "closed") not in idx.exact.get(hb, []):
            idx.exact[hb].append((i, "closed"))
    # adverbs whose L&S head is read as another part of speech ('praestō, adv. dat. from praestus')
    # (handled above together with immo)
    # cum: both L&S homographs (prep. cum1, conj. cum2) are kept; the conj. needs an explicit POS
    for n, pos, gl in (("1", "PREP", "with"), ("2", "CONJ", "when, since, although")):
        i = _find_ls(idx, "cum", n)
        if i is not None:
            idx.lemmas[i].pos = pos
            idx.lemmas[i].gloss = gl
            idx.lemmas[i].noncontent = True
            if (i, "closed") not in idx.exact["cum"] and (i, "x") not in idx.exact["cum"]:
                idx.exact["cum"].append((i, "closed"))
    # glosses for closed-list and function words
    for hb, n, _pos, _f in _CLOSED_VERBS + _CLOSED_PRON:
        i = _find_ls(idx, hb, n) if _find_ls(idx, hb, n) is not None else idx.by_key.get("lat:" + hb)
        if i is not None and hb in _CLOSED_GLOSS:
            idx.lemmas[i].gloss = _CLOSED_GLOSS[hb]
    for hb, _p, _t in _EO_COMPOUNDS:
        i = _find_ls(idx, hb)
        if i is not None and not idx.lemmas[i].gloss:
            idx.lemmas[i].gloss = "to go (compound of eo)"
    for hb in list(_FUNCTION_WORDS) + list(_POSSESSIVES):
        n = _FUNCTION_WORDS.get(hb, ("", ""))[0]
        i = _find_ls(idx, hb, n)
        if i is None:
            i = idx.by_key.get("lat:" + hb)
        if i is not None and hb in _CLOSED_GLOSS and hb != "cum":
            idx.lemmas[i].gloss = _CLOSED_GLOSS[hb]



# ---------------------------------------------------------------------------
# 5.  TIPNR names
# ---------------------------------------------------------------------------

def _load_tipnr(path: Optional[Path]) -> List[Tuple[str, str]]:
    """(name, short description) for every single-word name in TIPNR (English ESV/KJV/NIV forms)."""
    if not path or not path.exists():
        return []
    ind_desc: Dict[str, str] = {}                        # TIPNR individual ('Abraham@Gen.11.26-1Pe') -> description
    name_inds: Dict[str, Set[str]] = defaultdict(set)    # name -> the individuals it names
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "@" not in line:
                continue
            cols = line.rstrip("\n").split("\t")
            if line[:1].isalpha():
                m = re.match(r"([A-Z][A-Za-z]+)((?:\|[A-Z][A-Za-z]+)*)@", cols[0])     # 'Abram|Abraham@Gen...'
                if m:
                    ind = cols[0].split("=")[0].strip()
                    d = (cols[1] if len(cols) > 1 else "").strip()
                    d = re.sub(r"\s*\(?[A-Za-z#]+@[^\s)]*\)?", "", d)           # '(Nineveh@Gen.10.11-Luk=H5210)'
                    d = re.sub(r"^([A-Z][A-Za-z]*)=\s*", r"\1, ", d)            # 'Resen= near Nineveh'
                    ind_desc[ind] = d.strip(" ,")[:80]
                    for nm in [m.group(1)] + [x for x in m.group(2).split("|") if x]:
                        name_inds[nm].add(ind)
            elif line.startswith("–") and len(cols) >= 4 and cols[0].strip("– ").strip() in ("Named", "Greek",
                                                                                              "Aramaic"):
                ind = cols[1].split("=")[0].strip()
                for chunk in cols[3].split(";"):
                    nm = re.sub(r"=\s*[A-Z,]+\s*$", "", chunk).strip()
                    if re.fullmatch(r"[A-Z][a-z]+", nm):
                        name_inds[nm].add(ind)
    out = []
    for nm in sorted(name_inds):
        inds = name_inds[nm]
        # one TIPNR individual: its description; several: a neutral label (the first one listed is not
        # necessarily the bearer meant in a given verse: 'Jacob' names the patriarch and Joseph's grandfather)
        d = ind_desc.get(next(iter(inds)), "") if len(inds) == 1 else ""
        out.append((nm, d or ("proper name (several bearers in TIPNR)" if len(inds) > 1 else "proper name")))
    return out


# ---- TIPNR individuals with their verses (19 Nov 2026) -------------------------------------------------
# Name glosses for readers.  Lewis & Short describes classical bearers (Paulus 'a consul who fell near Cannae',
# Anna 'the sister of Dido'), so a name lemma attested in the Saints Latin text is described from the TIPNR
# individuals (STEPBible, CC BY 4.0) that (a) stand in the same verses and (b) bear a compatible name (English
# or Hebrew/Greek form, compared by consonant skeleton): Paulus -> Paul 'Apostle to the Gentiles ...';
# Simon -> several bearers.  A name with no such individual is described as 'proper name' (never another person).

_TIPNR_BOOKS = {
    "genesis": "Gen", "exodus": "Exo", "leviticus": "Lev", "numbers": "Num", "deuteronomy": "Deu", "joshua": "Jos",
    "judges": "Jdg", "ruth": "Rut", "1-samuel": "1Sa", "2-samuel": "2Sa", "1-kings": "1Ki", "2-kings": "2Ki",
    "1-chronicles": "1Ch", "2-chronicles": "2Ch", "ezra": "Ezr", "nehemiah": "Neh", "esther": "Est", "job": "Job",
    "psalms": "Psa", "proverbs": "Pro", "ecclesiastes": "Ecc", "song-of-songs": "Sng", "isaiah": "Isa",
    "jeremiah": "Jer", "lamentations": "Lam", "ezekiel": "Ezk", "daniel": "Dan", "hosea": "Hos", "joel": "Jol",
    "amos": "Amo", "obadiah": "Oba", "jonah": "Jon", "micah": "Mic", "nahum": "Nam", "habakkuk": "Hab",
    "zephaniah": "Zep", "haggai": "Hag", "zechariah": "Zec", "malachi": "Mal", "matthew": "Mat", "mark": "Mrk",
    "luke": "Luk", "john": "Jhn", "acts": "Act", "romans": "Rom", "1-corinthians": "1Co", "2-corinthians": "2Co",
    "galatians": "Gal", "ephesians": "Eph", "philippians": "Php", "colossians": "Col", "1-thessalonians": "1Th",
    "2-thessalonians": "2Th", "1-timothy": "1Ti", "2-timothy": "2Ti", "titus": "Tit", "philemon": "Phm",
    "hebrews": "Heb", "james": "Jas", "1-peter": "1Pe", "2-peter": "2Pe", "1-john": "1Jn", "2-john": "2Jn",
    "3-john": "3Jn", "jude": "Jud", "revelation": "Rev"}

_GRC_TRANSLIT = str.maketrans({"α": "a", "β": "b", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": "e", "θ": "t",
                               "ι": "i", "κ": "k", "λ": "l", "μ": "m", "ν": "n", "ξ": "x", "ο": "o", "π": "p",
                               "ρ": "r", "σ": "s", "ς": "s", "τ": "t", "υ": "u", "φ": "f", "χ": "k", "ψ": "ps",
                               "ω": "o"})


def _load_tipnr_people(path: Optional[Path]) -> List[list]:
    """[uid, brief, briefest, [[english, original form], ...], [refs 'Gen.30.8', ...], kind, description] for
    every TIPNR person, place and group, read from its header line ('Hezekiah@2Ki.16.20-Mat=H2396G <tab> King
    living at the time of Divided Monarchy'), its '– Named / Spelled / Greek ...' lines (forms and every verse)
    and its @Brief / @Briefest lines."""
    if not path or not path.exists():
        return []
    people: Dict[str, list] = {}
    order: List[str] = []
    cur: Optional[str] = None
    kind = "person"

    def norm_uid(s: str) -> str:
        s = s.split("=")[0].strip()
        return s.split("|")[-1] if "@" in s else s

    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            cols = line.rstrip("\n").split("\t")
            head = cols[0]
            if line.startswith("$=========="):
                kind = "place" if "PLACE" in head and "PERSON" not in head else \
                    "person" if "PERSON" in head else "other"
                continue
            if line[:1].isalpha() and "@" in head and re.match(r"[A-Z][A-Za-z_'\-|]*@", head):
                cur = norm_uid(head)
                if cur not in people:
                    desc = (cols[1] if len(cols) > 1 else "").strip()
                    desc = re.sub(r"\s*\(?[A-Za-z#]+@[^\s)]*\)?", "", desc).strip(" ,")
                    people[cur] = [cur, "", "", [], [], kind, desc[:90]]
                    order.append(cur)
                continue
            if cur is None:
                continue
            if line.startswith("–") and len(cols) >= 5 and "@" in cols[1]:
                uid = norm_uid(cols[1])
                rec = people.get(uid) or people[cur]
                orig = cols[2].split("=")[-1].strip() if "=" in cols[2] else ""
                for chunk in cols[3].split(";"):
                    eng = re.sub(r"=\s*[A-Z,]+\s*$", "", chunk).strip()
                    if re.fullmatch(r"[A-Z][A-Za-z'\-]+", eng) and [eng, orig] not in rec[3]:
                        rec[3].append([eng, orig])
                for r in cols[4].split(";"):
                    m = re.match(r"\s*([1-3]?[A-Z][a-z]+)\.(\d+)\.(\d+)", r)
                    if m:
                        rec[4].append(f"{m.group(1)}.{m.group(2)}.{m.group(3)}")
            elif line.startswith("@Brief= "):
                people[cur][1] = line[len("@Brief= "):].strip()
            elif line.startswith("@Briefest= "):
                people[cur][2] = line[len("@Briefest= "):].strip()
    out = []
    for uid in order:
        rec = people[uid]
        rec[4] = sorted(set(rec[4]))
        if rec[4]:
            out.append(rec)
    return out


_NAME_ENDINGS = ("orum", "arum", "ibus", "iah", "ah", "us", "um", "es", "as", "is", "os", "ae", "am", "em", "im", "a",
                 "e", "i", "o")


def _name_skeleton(name: str, ch: str = "k") -> str:
    """Consonant skeleton of a name in any of its spellings (Latin, English, transliterated Greek/Hebrew):
    Paulus / Paul / Παῦλος -> 'pl'; Ezechias / Hezekiah / Ἐζεκίας -> 'zk'; Nephthali / Naphtali -> 'nftl'."""
    s = unicodedata.normalize("NFD", name or "")
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn").lower().replace("æ", "ae").replace("œ", "oe")
    s = s.translate(_GRC_TRANSLIT)
    s = re.sub(r"[^a-z]", "", s)
    for a, z in (("ph", "f"), ("th", "t"), ("ch", ch), ("sh", "s"), ("ck", "k"), ("c", "k"), ("q", "k"),
                 ("x", "ks"), ("z", "s"), ("j", "i"), ("v", "u"), ("w", "u"), ("y", "i"), ("h", "")):
        s = s.replace(a, z)
    s = re.sub(r"(.)\1+", r"\1", s)
    for e in _NAME_ENDINGS:
        if s.endswith(e) and len(s) - len(e) >= 3:
            s = s[: -len(e)]
            break
    if not s:
        return ""
    # the first sound (any vowel counts as one class: Amri / Omri) keeps David ('d') apart from Judas ('d'); the
    # spelling with its vowels is kept as the third part for a similarity check (David 'dauid' is not Dodo 'dod')
    first = "V" if s[0] in "aeiou" else s[0]
    if s[0] == "i" and len(s) > 1 and s[1] in "aeiou":
        first = "j"                                   # consonantal I/J: Jacob is not Achab, Joannes is John
    return first + ":" + re.sub(r"(.)\1+", r"\1", re.sub(r"[aeiou]", "", s)) + ":" + s


def _name_keys(name: str) -> Set[str]:
    """Keys of a Latin name: its 'ch' read as k (Chanaan / Canaan, Achis / Achish) and as the Hebrew h that the
    English spelling drops (Achab / Ahab, Joachaz / Jehoahaz)."""
    return {k for k in (_name_skeleton(name), _name_skeleton(name, "") if "ch" in (name or "").lower() else "") if k}


def _same_skeleton(a: str, z: str) -> bool:
    return bool(a) and bool(z) and a.split(":")[:2] == z.split(":")[:2]


def _skeletons_match(a: str, z: str) -> bool:
    if not a or not z or a.count(":") != 2 or z.count(":") != 2:
        return False
    fa, a, na = a.split(":")
    fz, z, nz = z.split(":")
    if fa != fz or difflib.SequenceMatcher(None, na, nz).ratio() < 0.6:
        return False
    if not a or not z:
        return False
    if a == z:
        return True
    short, long_ = sorted((a, z), key=len)
    if len(short) >= 2 and long_.startswith(short) and len(long_) - len(short) <= 2:
        return True
    if len(short) >= 3 and len(long_) - len(short) <= 1:
        # one consonant changed, dropped or added (Zechri / Zichri are equal; Elisa 'ls' / Elishah 'ls')
        if len(short) == len(long_):
            return sum(1 for x, y in zip(short, long_) if x != y) <= 1
        return any(long_[:k] + long_[k + 1:] == short for k in range(len(long_)))
    return False


class _TipnrIndex:
    """TIPNR individuals by verse, for name glosses and for recognising Hebrew names at their verses."""

    def __init__(self, people: List[list]):
        self.people = people
        self.by_ref: Dict[Tuple[str, int, int], List[int]] = defaultdict(list)
        self.skel: List[Set[str]] = []
        for k, rec in enumerate(people):
            uid, forms, refs = rec[0], rec[3], rec[4]
            sk = {_name_skeleton(uid.split("@")[0])}
            for eng, orig in forms:
                sk.add(_name_skeleton(eng))
                if orig:
                    sk.add(_name_skeleton(orig))
            self.skel.append({s for s in sk if s})
            for r in refs:
                bk, ch, v = r.split(".")
                self.by_ref[(bk, int(ch), int(v))].append(k)
        self.cache: Dict[Tuple, List[int]] = {}

    def at(self, slug: str, ch: int, v: int, name_skels: Set[str]) -> List[int]:
        """Individuals with a compatible name in this verse (+/- 1 verse; Vulgate Psalm n also as n + 1)."""
        bk = _TIPNR_BOOKS.get(slug)
        if not bk:
            return []
        key = (bk, ch, v, frozenset(name_skels))
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        chs = (ch, ch + 1) if bk == "Psa" else (ch,)
        found: List[int] = []
        # the verse itself first; the neighbouring verses only when nothing matches there (Latin and English
        # verse division differ by a verse in places)
        for verses in ((v,), (v - 1, v + 1)):
            for c in chs:
                for vv in verses:
                    for k in self.by_ref.get((bk, c, vv), ()):
                        if k not in found and any(_skeletons_match(s, t) for s in name_skels for t in self.skel[k]):
                            found.append(k)
            if found:
                break
        self.cache[key] = found
        return found

    def english(self, k: int, name_skels: Set[str]) -> str:
        uid, forms = self.people[k][0], self.people[k][3]
        un = uid.split("@")[0].replace("_", " ")
        if any(_skeletons_match(s, _name_skeleton(un)) for s in name_skels):
            return un
        for eng, orig in forms:
            if any(_skeletons_match(s, _name_skeleton(eng)) or (orig and _skeletons_match(s, _name_skeleton(orig)))
                   for s in name_skels):
                return eng
        return uid.split("@")[0]


_LOWER_FIRST = {"A", "An", "The", "Son", "Sons", "Daughter", "King", "Queen", "Father", "Mother", "Wife", "Husband",
                "Brother", "Sister", "Apostle", "Prophet", "Prophetess", "Priest", "High", "Chief", "One", "Man",
                "Woman", "Town", "City", "Place", "Region", "River", "Mountain", "Mount", "Valley", "Descendant",
                "Ancestor", "Leader", "Official", "Servant", "Ruler", "Governor", "Gatekeeper", "Musician", "Warrior",
                "Head", "Disciple", "Wilderness", "Clan", "Tribe", "Land", "People", "Nation", "Grandson", "Founder",
                "Ancient", "Fortified", "Military", "Captain", "Commander", "Singer", "Scribe", "Judge", "Steward",
                "Village", "Spring", "Well", "Brook", "Stream", "Sea", "Island", "Gate", "Hill", "Area", "District",
                "Country", "Kingdom", "Pagan", "False", "Roman", "Christian", "Believer", "Companion", "Co-worker",
                "Fellow", "Member", "Wealthy", "Righteous", "Wicked", "Evil", "Faithful", "Young", "Old", "Elder",
                "Returned", "Returnee", "Exile", "Mighty", "Hero", "Prince", "Princess", "Concubine", "Nephew",
                "Uncle", "Aunt", "Cousin", "Grandfather", "Grandmother", "Mentioned", "Listed", "Signed", "Builder",
                "Craftsman", "Doorkeeper", "Levitical", "Temple", "Royal", "Eunuch", "Cupbearer", "Treasurer",
                "Magician", "Sorcerer", "Tanner", "Leper", "Ruling", "Tax", "Centurion", "Physician", "Pharaoh's",
                "Firstborn", "Eldest", "Youngest", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh"}


def _brief_text(text: str, cap: int) -> str:
    t = re.sub(r"<[^>]+>", "", text or "").strip().rstrip(".").strip()
    t = re.sub(r"\s*\([^()]*\)", "", t)
    if not t:
        return ""
    w = t.split(" ", 1)[0]
    if w in _LOWER_FIRST:
        t = t[0].lower() + t[1:]
    if len(t) > cap:
        t = t[:cap].rsplit(" ", 1)[0]
        t = _DANGLING.sub("", t).rstrip(" ,;:")
    return t


# ---------------------------------------------------------------------------
# 6.  Roots (explicit L&S etymology only)
# ---------------------------------------------------------------------------

_ETYM_VAGUE = re.compile(r"(Sanscr|Sanskr|Gr\.|\bcf\b|kindr|\broot\b|akin|perh|prob|dub|Celt|Germ|Etr|Osc|Umbr|"
                         r"Goth|Engl|Lith|Slav|Heb|Syr|Pers|Egypt|Phoen|Punic|Ir\.|Fr\.|Ital|Span|\?|unknown|"
                         r"uncertain|corrupt|form of|cogn|compare|same as|old|stem|Indo|Ind\.|Arab)", re.I)


def _etym_refs(text: str) -> Optional[List[Tuple[str, str]]]:
    """Headword references in an L&S etymology ('princeps', '1. capio', 'primus-capio', 'ad + capio')."""
    if not text:
        return None
    t = text.strip().strip(".;, ")
    t = re.sub(r"^(?:from|fr\.|dim\.(?: of| from)?|dimin\.(?: of| from)?|freq\.(?: of| from)?|inch\.(?: of| from)?|"
               r"intens\.(?: of| from)?|desid\.(?: of| from)?|comp\.(?: of| from)?|sup\.(?: of| from)?)\s+", "", t)
    # L&S points to a sense of the source entry ('benedico, II.', 'relinquo, I. B. 1.', 'primus init.'): the
    # word is the reference; and a plain source word before a ';' stands although cognates follow it
    # ('vivo; Sanscr. gīv', 'sepelio; cf. fulcrum'), 19 Nov 2026
    t = re.sub(r"(?:,\s*|\s+)(?:[IVX]+\.?\s*)(?:[A-Z]\.\s*)?(?:\d+\.?\s*)?$", "", t).strip(" ,.")
    t = re.sub(r"\s+(?:init|fin)\.?$", "", t)
    if ";" in t:
        first = t.split(";")[0].strip(" ,.")
        if first and re.fullmatch(r"(?:\d\.\s*)?[A-Za-zĀ-ſ\u0300-\u036f^ăĕĭŏŭāēīōūȳ]+", first):
            t = first
    if _ETYM_VAGUE.search(t):
        return None
    parts = re.split(r"\s*\+\s*|\s*-\s*|\s+and\s+|\s*,\s*", t)
    refs = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        m = re.fullmatch(r"(?:(\d)\.\s*)?([A-Za-zĀ-ſ\u0300-\u036f^ăĕĭŏŭāēīōūȳ]+)", p)
        if not m:
            return None
        if refs and _b(m.group(2)) in _INF_MARKS:
            continue                  # '[2. lego, ĕre]': the infinitive only names the conjugation
        refs.append((m.group(1) or "", _plain(m.group(2))))
    return refs or None


_INF_MARKS = {"are", "ere", "ire", "ari", "eri", "iri"}
_PRES_FAMILY = {"V1A": "1", "V1P": "1", "V2A": "2", "V2P": "2", "V3A": "3", "V3P": "3", "V3IA": "3i", "V3IP": "3i",
                "V4A": "4", "V4P": "4"}


def _verb_info(idx: _Index) -> Dict[int, Tuple[str, Set[str]]]:
    """lemma id -> (conjugation, perfect stems) of every verb paradigm (for choosing a verb homograph)."""
    info = getattr(idx, "_verb_info", None)
    if info is None:
        info = {}
        for st, lst in idx.stems.items():
            for k, pc in lst:
                if pc in _PRES_FAMILY or pc == "VPF":
                    conj, perfs = info.get(k, ("", set()))
                    if pc == "VPF":
                        perfs.add(st)
                    else:
                        conj = conj or _PRES_FAMILY[pc]
                    info[k] = (conj, perfs)
        idx._verb_info = info
    return info


def _resolve_ref(idx: _Index, n: str, word: str, prefer_pos: str = "", child: Optional[int] = None
                 ) -> Optional[int]:
    hb = _b(word)
    if not hb:
        return None
    ids = [i for i in idx.headwords.get(hb, []) if idx.lemmas[i].lskey and idx.lemmas[i].pos not in ("X",)]
    if word[:1].islower():
        # a lower-case reference is a common word, not a name ('in-opis': ops, not the nymph Opis)
        ids = [i for i in ids if not idx.lemmas[i].proper]
    if not ids:
        if word[:1].islower() and hb not in ("id", "idem", "ib", "ibid", "ead", "eod"):
            # L&S sometimes cites a noun's case form ('in-opis' = gen. of ops, '[litterae]'): accept a unique
            # noun analysis (never a verb or adjective form - 'in-mineo' is not mineus - and never a pronoun:
            # L&S's 'id.' = 'the same as above' is not 'is')
            found = {idx.canon.get(k, k) for k, _pc, _e in idx.analyse(hb)}
            found = {k for k in found if not idx.lemmas[k].proper and idx.lemmas[k].pos == "N"
                     and not idx.lemmas[k].noncontent and idx.lemmas[k].lskey}
            if len(found) == 1:
                return _follow_alias(idx, next(iter(found)))
        return None
    if n:
        for i in ids:
            if idx.lemmas[i].n == n:
                return _follow_alias(idx, i)
    if len(ids) > 1 and prefer_pos:
        sel = [i for i in ids if idx.lemmas[i].pos == prefer_pos]
        if sel:
            ids = sel
    if len(ids) > 1 and child is not None and idx.lemmas[child].pos == "V":
        # a compound verb belongs to the homograph of its own conjugation and perfect: dedico (1st conj.) to
        # dico#1, not dico#2 'say'; comedo (comedi) to edo#1 'eat' (edi), not edo#2 'give out' (edidi)
        info = _verb_info(idx)
        cconj, cperfs = info.get(child, ("", set()))

        def score(j: int) -> Tuple[int, int, int]:
            jconj, jperfs = info.get(j, ("", set()))
            same_conj = int(bool(cconj) and cconj == jconj)
            same_perf = int(any(cp.endswith(jp) for cp in cperfs for jp in jperfs))
            return (same_perf, same_conj, idx.lemmas[j].size)
        return _follow_alias(idx, max(ids, key=score))
    return _follow_alias(idx, max(ids, key=lambda i: idx.lemmas[i].size))


def _follow_alias(idx: _Index, i: int) -> Optional[int]:
    """The lemma an L&S cross-reference entry stands for (chains followed); None when it ends nowhere."""
    for _k in range(6):
        lem = idx.lemmas[i]
        if lem.pos != "ALIAS":
            return i
        if lem.source not in idx.by_key:
            return None
        i = idx.by_key[lem.source]
    return None if idx.lemmas[i].pos == "ALIAS" else i


def _direct_parents(idx: _Index, i: int, prev_refs: Optional[List[Tuple[str, str]]]) -> Tuple[List[int], str]:
    """Parents of a lemma per explicit L&S data, and a readable formula."""
    lem = idx.lemmas[i]
    if not lem.lskey:
        return [], ""
    srcs = []
    if lem.etym:
        srcs.append(lem.etym)
    if lem.bracket and lem.bracket != lem.etym:
        srcs.append(lem.bracket)
    for s in srcs:
        if s.strip().strip(". ") == "id":
            # '[id.]' = the same derivation as the entry before (sacrificium after sacrifico)
            refs = prev_refs
        else:
            refs = _etym_refs(s)
        if not refs:
            continue
        if lem.hyph and all(_b(w) in _COMPOUND_PREFIXES or (len(refs) > 1 and _b(w) in _COMPOUND_SUFFIXES)
                            for _n, w in refs):
            return [], ""       # 'in-victus, adj. [2. in]': L&S names only the prefix -> no family
        ids = []
        # abstract nouns in -itia / -itas / -itudo come from an adjective (malitia from malus 'bad', not the mast)
        want = "ADJ" if lem.hb.endswith(("itia", "itas", "itudo", "ities", "tudo")) else lem.pos
        for n, w in refs:
            j = _resolve_ref(idx, n, w, want, i)
            if j is None and len(refs) == 1:
                # 'sanctusfacio': the XML lost the hyphen between two headwords
                hb = _b(w)
                for k in range(3, len(hb) - 2):
                    if idx.headwords.get(hb[:k]) and idx.headwords.get(hb[k:]):
                        a = _resolve_ref(idx, "", hb[:k], "", i)
                        z = _resolve_ref(idx, "", hb[k:], lem.pos, i)
                        if a is not None and z is not None:
                            ids = [a, z]
                        break
                if ids:
                    break
            if j is None:
                ids = []
                break
            ids.append(j)
        if ids and i not in ids:
            return ids, " + ".join(idx.lemmas[j].lemma for j in ids)
    if lem.pa_of:
        parts = lem.pa_of.split()
        j = _resolve_ref(idx, parts[0] if len(parts) == 2 else "", parts[-1], "V")
        if j is not None and j != i:
            return [j], f"P. a. of {idx.lemmas[j].lemma}"
    m = re.match(r"^[^,]{0,30},\s*(?:adv|sup|comp)\.,?\s*v\.\s*(?:(\d)\.\s*)?([^\s,.;]+)", lem.lead)
    if m and lem.pos in ("ADV", "X"):
        j = _resolve_ref(idx, m.group(1) or "", m.group(2))
        if j is not None and j != i and idx.lemmas[j].pos in ("ADJ", "N", "V"):
            return [j], f"adv. of {idx.lemmas[j].lemma}"
    if lem.hyph:
        rest = lem.hb[len(lem.hyph):]
        if lem.hb.startswith(lem.hyph) and len(rest) >= 2:
            if rest in _COMPOUND_SUFFIXES:
                # 'ŭbī-quē', 'quam-vīs': the second member is an enclitic or volo's 'vis' -> the first member
                j = _resolve_ref(idx, "", lem.hyph)
                if j is not None and j != i:
                    return [j], f"{idx.lemmas[j].lemma} + -{rest}"
                return [], ""
            j = _resolve_ref(idx, "", rest, lem.pos, i)
            if j is None and rest in _WEAKENED:
                j = _resolve_ref(idx, "", _WEAKENED[rest], lem.pos, i)      # dē-scendo: scando
            if j is not None and j != i:
                return [j], f"{lem.hyph} + {idx.lemmas[j].lemma}"
    # the source word that L&S prints right after the gender or part of speech, without brackets: 'fīlĭa, ae, f.
    # filius, a daughter', 'fĭdes, ĕi, f. fido, trust', 'caelestis, e, adj. caelum', 'dē-fĭcĭo, ..., v. a. and n.
    # facio, orig. ...' (19 Nov 2026)
    m = re.search(r",\s*(?:[mfnc]\.|adj\.|v\.\s*(?:a|n|dep|inch|freq|intens)\.(?:\s*and\s*[an]\.)?)\s+"
                  r"(?:(\d)\.\s*)?([A-Za-zĀ-ſ^\u0300-\u036f]{3,})\s*[,;.]", lem.lead[:140])
    if m and not lem.proper:
        w = _plain(m.group(2))
        if w and w[:1].islower() and _ab(w) not in _SHORT_ENGLISH and _ab(w) not in _GRAMMAR_LABELS and                 _ab(w) not in _COMPOUND_PREFIXES and _ab(w) not in ("sus", "subs", "dis", "red", "prod") and                 not re.match(r"\s*[,;.]\s*(?:i\.\s*e\.|=)", lem.lead[m.end(2):m.end(2) + 12]):
            # (not a prefix: 'suscĭpĭo, ..., v. a. sus, i. e. subs-capio' is not sus 'swine')
            j = _resolve_ref(idx, m.group(1) or "", w, "", i)
            if j is not None and j != i and idx.lemmas[j].pos in ("N", "V", "ADJ", "ADV", "NUM") and \
                    not idx.lemmas[j].proper:
                return [j], f"{idx.lemmas[j].lemma} (L&S)"
    if lem.size < 400 and not lem.proper:
        # an L&S stub that only refers to another headword of the same part of speech ('gnosco, ĕre, v. nosco
        # init.' = the old form of nosco): same family
        m = re.search(r",\s*v\.\s*(?:(\d)\.\s*)?([A-Za-zĀ-ſ\-]+)", lem.lead)
        if m:
            j = _resolve_ref(idx, m.group(1) or "", _plain(m.group(2)), lem.pos, i)
            if j is not None and j != i and idx.lemmas[j].pos == lem.pos:
                return [j], f"= {idx.lemmas[j].lemma} (L&S cross-reference)"
    return [], ""


# compound members that L&S prints with the weakened vowel of composition (dē-scendo, con-scendo: scando)
_WEAKENED = {"scendo": "scando"}

# family links that the L&S statements give wrongly for the reader (checked against the entries, 19 Nov 2026):
# adoleo 'to magnify, burn' and ab-oleo 'to check the growth of, destroy' are not oleo 'to emit a smell';
# vectis 'a lever' (from veho) is not vectigal; delecto [delicio] does not reach licium 'thread'
_ROOT_OVERRIDE: Dict[str, Optional[str]] = {"lat:adoleo#1": None, "lat:aboleo": None, "lat:vectis": "lat:veho",
                                            "lat:delecto": None,
                                            # 18 Nov re-check: desero 'forsake' is de + sero2 'join' (not sero1
                                            # 'sow'); delicio is from lacio per L&S, not de + licium 'thread'
                                            "lat:desero#2": "lat:sero#2", "lat:delicio": None}


def _compute_roots(idx: _Index) -> Dict[int, Tuple[int, str]]:
    """lemma id -> (root lemma id, formula)."""
    parents: Dict[int, Tuple[List[int], str]] = {}
    prev_refs: Optional[List[Tuple[str, str]]] = None
    for i, lem in enumerate(idx.lemmas):
        if not lem.lskey:
            continue
        if lem.key in _ROOT_OVERRIDE:
            tgt = _ROOT_OVERRIDE[lem.key]
            j = idx.by_key.get(tgt) if tgt else None
            parents[i] = ([j], f"{idx.lemmas[j].lemma} (L&S)") if j is not None else ([], "")
            continue
        ps, formula = _direct_parents(idx, i, prev_refs)
        parents[i] = (ps, formula)
        is_id = lem.etym.strip(". ") == "id"
        own = _etym_refs(lem.etym) if lem.etym and not is_id else None
        if own:
            prev_refs = own
        elif not is_id:
            prev_refs = None
    out: Dict[int, Tuple[int, str]] = {}

    def head_of(ids: List[int]) -> Optional[int]:
        # the last member that is neither a prefix nor an enclitic/suffix ('quis + que' -> quis); a single
        # parent is the parent ('violo [vis]', 'subter [sub]')
        if len(ids) == 1:
            return ids[0]
        for j in reversed(ids):
            if idx.lemmas[j].hb not in _COMPOUND_PREFIXES and idx.lemmas[j].hb not in _COMPOUND_SUFFIXES:
                return j
        return None

    for i in parents:
        chain = [i]
        formulas = []
        cur = i
        seen = {i}
        for _ in range(8):
            ps, f = parents.get(cur, ([], ""))
            if not ps:
                break
            nxt = head_of(ps)
            if nxt is None or nxt in seen or idx.lemmas[nxt].pos in ("ALIAS", "X"):
                break
            formulas.append(f)
            seen.add(nxt)
            chain.append(nxt)
            cur = nxt
        if cur != i:
            out[i] = (cur, " ; ".join(f"{idx.lemmas[chain[k]].lemma} ← {formulas[k]}" for k in range(len(formulas))))
    return out


# ---------------------------------------------------------------------------
# 7.  Corpus priors
# ---------------------------------------------------------------------------

# Form-level manual priors for the commonest ambiguous forms: bare form -> {bare headword or
# 'headword#n' (L&S homograph): weight}.  Each weight is the share observed in a random sample of
# 10-14 contexts of that form in the Saints Latin text (KWIC read by hand, 18 Nov 2026; e.g. 'tui':
# 13 of 14 possessive 'servi tui', 1 'similis tui'), never from PROIEL or any other tagged corpus.
# A form whose best weight is < 0.70 stays untagged unless a context rule applies.
_FORM_PRIOR: Dict[str, Dict[str, float]] = {
    "quod": {"qui#1": 0.6, "quod#1": 0.4},              # 8/14 relative, 5/14 conj.; 'eo quod' -> conj.
    "quam": {"qui#1": 0.5, "quam": 0.5},                # 7/14 relative, 7/14 adverb/conj. ('plus quam', 'tam ... quam')
    "quem": {"qui#1": 0.9, "quis#1": 0.1},              # 14/14 relative in the sample
    "quo": {"qui#1": 0.65, "quis#1": 0.1, "quo": 0.25},  # 10/14 relative, 2 'whither', 1 interrogative
    "cui": {"qui#1": 0.85, "quis#1": 0.15},             # 12/14 relative (incl. connective 'Cui respondit')
    "cuius": {"qui#1": 0.8, "quis#1": 0.2},             # 9/12 relative, 2 interrogative, 1 indefinite
    "quibus": {"qui#1": 0.92, "quis#1": 0.08},          # 12/12 relative
    "qua": {"qui#1": 0.85, "quis#1": 0.1, "qua": 0.05},  # 11/12 relative
    "quoque": {"quoque#1": 0.97, "quisque": 0.03},      # 12/12 'also'
    "secundum": {"secundum": 0.9, "secundus": 0.1},     # 11/12 preposition
    "uero": {"uero#1": 0.97, "uerus": 0.03},            # 12/12 adverb/conjunction 'vero'
    "mi": {"meus": 0.97, "ego": 0.03},                  # 12/12 vocative 'fili mi', 'domine mi'
    "tui": {"tuus": 0.9, "tu": 0.1},                    # 13/14 possessive
    "mei": {"meus": 0.9, "ego": 0.1},                   # 13/14 possessive, 1 'memento mei'
    "sui": {"suus": 0.9, "sui": 0.1},                   # 12/12 possessive 'patris sui'
    "nostri": {"noster": 0.85, "nos": 0.15},            # 12/14 possessive, 1 'memento nostri'
    "nostrum": {"noster": 0.88, "nos": 0.12},           # 11/12 possessive, 1 'omnium nostrum'
    "uestri": {"uester": 0.88, "uos": 0.12},            # 11/12 possessive, 1 'in medio vestri'
    "uestrum": {"uester": 0.65, "uos": 0.35},           # 8/12 possessive, 4/12 partitive -> untagged
    "illuc": {"illuc#2": 1.0},                          # adverb 'thither' (illuc#1 is archaic illud)
    "illic": {"illic#2": 0.97, "illic#1": 0.03},        # adverb 'there'
    "magis": {"magis#1": 0.99},                         # adverb 'more'
    "eodem": {"idem": 0.95, "eodem": 0.05},             # 10/10 'in eodem loco', 'eodem tempore'
    "solum": {"solum#2": 0.85, "solus#1": 0.1, "solum#1": 0.05},   # 9/10 'non solum'
    "cito": {"cito#1": 0.97, "cito#2": 0.03},           # 10/10 adverb 'quickly'
    "amplius": {"amplius": 0.95, "amplus": 0.05},       # 10/10 adverb 'any more'
    "foris": {"foris#2": 0.95, "foris#1": 0.05},        # 10/10 adverb 'outside'
    "maris": {"mare": 0.98, "mas": 0.02},               # 10/10 'of the sea'
    "mari": {"mare": 0.97, "mas": 0.03},
    "longe": {"longe": 0.95, "longus": 0.05},           # adverb 'far'
    "sine": {"sine": 0.95, "sino": 0.05},               # preposition (imperative of sino is rare)
    "ei": {"is": 0.99},                                 # pronoun, not the interjection
    "eo": {"is": 0.85, "eo#2": 0.1, "eo#1": 0.05},      # 'in eo', 'de eo', 'eo quod'; adverb and verb rare
    "uado": {"uado#1": 0.97, "uadum": 0.03},            # 'Vado ad Patrem': verb 'I go', not the ford
    "fili": {"filius": 0.99, "filum": 0.01},            # 12/12 vocative 'fili mi', 'Fili hominis'
    "primum": {"primum": 0.8, "primus": 0.2},           # 9/12 adverb 'first'
    "tantum": {"tantum": 0.85, "tantus": 0.15},         # 11/12 adverb 'only' / 'in tantum'
    "seniorum": {"senex": 0.95, "senium": 0.05},        # 'seniorum populi': the elders
    "genus": {"genus#1": 0.97, "genu": 0.03},           # 'genus electum': race, kind (the knee is 'genu')
    "deserto": {"desertus": 0.9, "desero#2": 0.1},      # 'in deserto': the desert (P. a. of desero)
    "desertum": {"desertus": 0.85, "desero#2": 0.15},
    "senioribus": {"senex": 0.95, "senior": 0.05},
    "uere": {"uere": 0.97, "uer": 0.02, "uerus": 0.01},  # adverb 'truly'
    "continuo": {"continuo#1": 0.97, "continuus": 0.03},  # adverb 'immediately'
    # added after the independent verification of 18 Nov 2026 (every context read):
    "cum": {"cum#1": 0.5, "cum#2": 0.5},                # preposition / conjunction: left to the context rules
                                                        # (now that 'Cumque' counts as conj. cum, the corpus
                                                        # prior alone would wrongly favour the conjunction)
    "aduersum": {"aduersus#3": 0.97, "aduersus#1": 0.03},  # 201: the preposition ('consurrexit adversum me')
    "paratus": {"paro#1": 0.94, "paratus#1": 0.03, "paratus#2": 0.03},   # 16: participle 'Paratus sum'
    "paratum": {"paro#1": 0.94, "paratus#1": 0.03, "paratus#2": 0.03},   # 18: 'Paratum cor meum'
    "nescio": {"nescio": 0.97, "nescius": 0.03},          # 25/25 'Nescio vos', 'nescio quid dicis'
    "praesto": {"praesto#1": 0.97, "praesto#2": 0.03},    # 11/11 adverb 'Praesto sum', 'praesto est'
    "facis": {"facio": 0.97, "fax": 0.03},                # 40/40 'Quid facis?' (never the torch)
    "morata": {"moror#1": 0.95, "moratus#1": 0.02, "moratus#2": 0.03},   # Ruth 1:16 'ubi morata fueris' (stayed)
    "sapis": {"sapio": 0.97, "sapa": 0.03},               # 'non sapis quae Dei sunt' (verb, not 'new wine'); 18 Nov re-check
    "nota": {"nosco": 0.93, "nota": 0.07},                # 15/15 'nota fierent', 'nota faciet' (made known)
    "moratus": {"moror#1": 0.95, "moratus#1": 0.02, "moratus#2": 0.03},   # 8/8 'moratus est' (stayed)
    "praestes": {"praesto#2": 0.95, "praestes": 0.05},    # 2/2 'ut hoc illi praestes' (subj. of praesto)
    # 19 Nov 2026, from every context of each form in the Saints Latin (the final check's untagged clusters):
    "natus": {"nascor": 0.94, "natus": 0.06},            # 'natus est', 'qui natus est': born (60/60 read)
    "natum": {"nascor": 0.94, "natus": 0.04, "natis": 0.02},   # 'quod natum est' (11/11)
    "nati": {"nascor": 0.94, "natus": 0.04, "natis": 0.02},    # 'nati sunt ei' (all read)
    "similis": {"similis": 0.98, "simila": 0.02},        # 'similis tui', 'similis est' (94/94 the adjective)
    "testis": {"testis#1": 0.97, "testis#2": 0.01, "testa": 0.01, "testum": 0.01},   # witness (39/39)
    "amicum": {"amicus#2": 0.92, "amicus#1": 0.08},      # 'amicum suum': the friend (noun), 41/41
    "amicos": {"amicus#2": 0.92, "amicus#1": 0.08},
    "amicis": {"amicus#2": 0.9, "amicus#1": 0.08, "amicio": 0.02},
    "amicorum": {"amicus#2": 0.92, "amicus#1": 0.08},
    "profectus": {"proficiscor": 0.92, "proficio": 0.03, "profectus": 0.05},   # 'profectus est' set out, 44/44
    "profecti": {"proficiscor": 0.94, "proficio": 0.03, "profectus": 0.03},    # 'profecti sunt', 33/33
    "conuersus": {"conuerto": 0.94, "conuersus": 0.04, "conuerro": 0.02},     # 'conversus est' turned, 54/54
    "conuersi": {"conuerto": 0.94, "conuersus": 0.04, "conuerro": 0.02},      # 'conversi sunt', 30/30
    "conuersa": {"conuerto": 0.9, "conuersus": 0.06, "conuerro": 0.02, "conuerso": 0.02},
    "alia": {"alius": 0.98, "alium": 0.01, "alia": 0.01},   # 'alia' = other things (81/81), never garlic
    "extra": {"extra": 0.97, "exter": 0.02, "extro": 0.01},  # the preposition / adverb 'outside' (81/81)
    "grande": {"grandis": 0.95, "grande": 0.05},         # 'grande convivium', 'cornu grande': the adjective (35/35)
    "ortus": {"ortus#2": 0.8, "orior": 0.15, "ortus#1": 0.05},   # without est/sunt: 'ortus solis', 'distat ortus'
    "orto": {"orior": 0.85, "ortus#1": 0.1, "ortus#2": 0.05},    # 'orto mane', 'orto sole' (abl. abs.)
    "oriente": {"oriens": 0.9, "orior": 0.1},            # 'ab oriente': the east (now that orior has a paradigm)
    "orientem": {"oriens": 0.9, "orior": 0.1},
    "oriens": {"oriens": 0.8, "orior": 0.2},
    "orientis": {"oriens": 0.9, "orior": 0.1},
    "responso": {"responsum": 0.85, "responsus": 0.05, "respondeo": 0.05},   # 'responso accepto': the answer
    "responsis": {"responsum": 0.85, "responsus": 0.05, "respondeo": 0.05},
    "incensi": {"incensum": 0.85, "incendo": 0.15},      # 'hora incensi' (Lk 1:10)
    # nouns and adjectives that now meet the participle of their verb (19 Nov 2026: '-di/-ti, sum' supines read)
    "incensum": {"incensum": 0.92, "incendo": 0.08},     # 'offeres incensum': incense (57/57 read)
    "incenso": {"incensum": 0.9, "incendo": 0.1},        # 'plenum incenso'
    "incensumque": {"incensum": 0.92, "incendo": 0.08},
    "aduerso": {"aduersus": 0.95, "aduerto": 0.05},       # 'ex adverso': opposite (44/44)
    "aduersi": {"aduersus#1": 0.9, "aduerto": 0.08, "aduersus#2": 0.02},   # 'nihil adversi': adverse (adj.)
    "aduersis": {"aduersus#1": 0.9, "aduerto": 0.08, "aduersus#2": 0.02},
    "intellectus": {"intellectus#2": 0.9, "intellectus#1": 0.03, "intellego": 0.07},   # understanding (noun)
    "intellectum": {"intellectus#2": 0.88, "intellectus#1": 0.03, "intellego": 0.09},
    "intellectu": {"intellectus#2": 0.95, "intellectus#1": 0.02, "intellego": 0.03},
    "derisum": {"derisus#2": 0.92, "derisus#1": 0.03, "derideo": 0.05},   # 'in derisum': a laughing-stock (12/12)
    "derisus": {"derisus#2": 0.85, "derisus#1": 0.05, "derideo": 0.1},
    "portentum": {"portentum": 0.95, "portendo": 0.05},   # 'signum atque portentum' (7/7)
    "sensus": {"sensus#2": 0.93, "sensus#1": 0.05, "sentio": 0.02},   # 'sensus': understanding (noun)
    "sensum": {"sensus#2": 0.93, "sensus#1": 0.05, "sentio": 0.02},
    "responsum": {"responsum": 0.85, "responsus": 0.05, "respondeo": 0.05},   # 'responsum': the answer
    "retorta": {"retorqueo": 0.9, "retortus": 0.1},     # 'de bysso retorta': twisted (participle)
    # 'content' is contentus#2 (P. a. of contineo); contentus#1 is 'stretched, strained' (of contendo)
    "contenti": {"contentus#2": 0.9, "contentus#1": 0.02, "contineo": 0.06, "contendo": 0.02},   # content
    "contentus": {"contentus#2": 0.9, "contentus#1": 0.02, "contineo": 0.06, "contendo": 0.02},
    "defensio": {"defensio": 1.0},
    "uetera": {"uetus": 0.97, "uetero": 0.03},           # 8/8 'vetera' = old things (Lv 25:22), not 'make old!'
    # KWIC-verified Vulgate form priors (each 8/8 in random Vulgate samples, 19 Nov 2026)
    "mori": {"morior": 0.96, "mos": 0.02, "morus#2": 0.02},
    "fortem": {"fortis": 0.96, "fors": 0.04},
    "luctum": {"luctus": 0.95, "lugeo": 0.05},
    "recta": {"rectus": 0.92, "rego": 0.08},
    "generis": {"genus#1": 0.95, "gener": 0.03, "geno": 0.02},
    "alterius": {"alter": 0.92, "alius": 0.08},
    "siti": {"sitis": 0.95, "sitio": 0.03, "sino": 0.02},
    "armis": {"arma": 0.96, "armus": 0.04},
    "pluuia": {"pluuia": 0.95, "pluuius": 0.05},
    "torrentis": {"torrens": 0.95, "torreo": 0.05},
    "numero": {"numerus": 0.94, "numero#2": 0.04, "numero#1": 0.02},
    "utrum": {"utrum": 0.95, "uter#1": 0.03, "uterus": 0.02},
    "potum": {"potus#2": 0.94, "potus#1": 0.03, "poto": 0.03},
    "custodi": {"custodio": 0.96, "custos": 0.04},
    "creuit": {"cresco": 0.96, "cerno": 0.04},
    "praepositus": {"praepositus#2": 0.92, "praepono": 0.05, "praepositus#1": 0.03},
    "sempiternum": {"sempiternus": 0.92, "sempiternum": 0.08},
    "difficile": {"difficilis": 0.92, "difficile": 0.08},
    "saltus": {"saltus#2": 0.92, "saltus#1": 0.05, "salio#2": 0.03},
    "uinctorum": {"uincio": 0.95, "uinctor": 0.05},
    # Stage 3C-2 KWIC-verified Vulgate form priors (each verified across Vulgate contexts, 19 Nov 2026)
    "honora": {"honoro": 0.98, "honorus": 0.02},
    "habitas": {"habito": 0.98, "habeo": 0.01, "habitus#1": 0.01},
    "habito": {"habito": 0.96, "habeo": 0.03, "habitus#1": 0.01},
    "statuas": {"statua": 0.96, "statuo": 0.04},
    "naui": {"nauis": 0.98, "no": 0.01, "nauus": 0.01},
    "aliquam": {"aliquis": 0.98, "aliquam": 0.02},
    "utroque": {"uterque": 0.97, "utroque": 0.03},
    "sempiterno": {"sempiternus": 0.97, "sempiterno": 0.03},
    "perpetuo": {"perpetuus": 0.96, "perpetuo#1": 0.03, "perpetuo#2": 0.01},
    "serua": {"seruo": 0.94, "serua": 0.04, "seruus#1": 0.02},
    "uenis": {"uenio": 0.97, "uena": 0.01, "ueneo": 0.01, "uenum": 0.01},
    "uadis": {"uado#1": 0.97, "uadum": 0.02, "uas#1": 0.01},
    "uiui": {"uiuus": 0.97, "uiuo": 0.03},
    "caede": {"caedes": 0.95, "caedo": 0.05},
    "arte": {"ars": 0.96, "arte": 0.02, "artus#1": 0.02},
    "summam": {"summa": 0.95, "summus": 0.05},
    "sola": {"solus#1": 0.97, "solo": 0.02, "solum#1": 0.01},
    "seras": {"sera": 0.96, "sero#1": 0.01, "sero#2": 0.01, "sero#3": 0.01, "serus": 0.01},
    "electorum": {"eligo": 0.90, "electus#1": 0.08, "elector#1": 0.01, "elector#2": 0.01},
    "digne": {"digne": 0.97, "dignus": 0.03},
    "ortum": {"ortus#2": 0.92, "orior": 0.06, "ortus#1": 0.02},
    "lineis": {"lineus": 0.92, "linea": 0.08},
    "asinis": {"asinus": 0.90, "asina": 0.10},
    "legi": {"lex": 0.94, "lego#2": 0.06},
    "effectus": {"efficio": 0.94, "effectus#1": 0.03, "effectus#2": 0.03},
    "incidet": {"incido#1": 0.96, "incido#2": 0.04},
    "creuerit": {"cresco": 0.96, "cerno": 0.04},
    "creuerint": {"cresco": 0.96, "cerno": 0.04},
    "creuerat": {"cresco": 0.96, "cerno": 0.04},
    "creuerunt": {"cresco": 0.96, "cerno": 0.04},
    "saltum": {"saltus#2": 0.92, "saltus#1": 0.05, "salio#2": 0.03},
    "ardentis": {"ardeo": 0.90, "ardens": 0.10},
    "infantia": {"infantia": 0.94, "infans": 0.06},
    "statura": {"statura": 0.96, "sto": 0.04},
    "dulce": {"dulcis": 0.94, "dulce": 0.06},
    "praefecti": {"praefectus#3": 0.90, "praeficio": 0.06, "praefectus#2": 0.02, "praefectus#1": 0.02},
    "agnis": {"agnus": 0.92, "agna#1": 0.06, "agna#2": 0.01, "agnos": 0.01},
    "appositus": {"appono": 0.94, "appositus#1": 0.03, "appositus#2": 0.03},
    "accensus": {"accendo#2": 0.94, "accensus#1": 0.03, "accensus#2": 0.02, "accenseo": 0.01},
    "armatus": {"armo": 0.90, "armatus#1": 0.07, "armatus#2": 0.03},
    "clausum": {"claudo#1": 0.92, "clausus": 0.05, "clausum": 0.03},
    "dominatus": {"dominor": 0.92, "dominatus": 0.08},
    "laetamini": {"laetor": 0.96, "laeto": 0.02, "laetamen": 0.02},
    "consolamini": {"consolor": 0.96, "consolo": 0.02, "consolamen": 0.02},
    "operantibus": {"operor": 0.95, "opero": 0.03, "operans": 0.02},
    # Stage 3C-3 KWIC-verified Vulgate form priors (19 Nov 2026)
    "notum": {"nosco": 0.90, "notus": 0.08, "Notus": 0.02},
    "parate": {"paro#1": 0.96, "paro#2": 0.02, "parate": 0.01, "paratus#1": 0.01},
    "aliqui": {"aliquis": 0.97, "aliqui": 0.03},
    "uestitus": {"uestio": 0.92, "uestitus#2": 0.06, "uestitus#1": 0.02},
    "desertam": {"desertus": 0.92, "desero#2": 0.08},
    "iura": {"iuro": 0.95, "ius#1": 0.03, "ius#2": 0.01, "Jura": 0.01},
    "uenissemus": {"uenio": 0.98, "ueneo": 0.02},
    "uenias": {"uenio": 0.97, "uenia": 0.03},
    "alio": {"alius": 0.95, "alio": 0.03, "alium": 0.01, "allium": 0.01},
    "fermentatum": {"fermento": 0.92, "fermentatus": 0.08},
    "pendet": {"pendeo": 0.96, "pendo": 0.04},
    "liba": {"libum": 0.94, "libo": 0.06},
    "pellium": {"pellis": 0.97, "pellion": 0.03},
    "portentis": {"portentum": 0.95, "portendo": 0.05},
    "armorum": {"arma": 0.96, "armus": 0.04},
    "indica": {"indico#1": 0.97, "Indicus": 0.03},
    "conserua": {"conseruo": 0.96, "conserua": 0.04},
    "astitit": {"asto": 0.90, "assisto": 0.10},
    "astiterunt": {"asto": 0.90, "assisto": 0.10},
    "mundis": {"mundus#1": 0.95, "mundus#2": 0.03, "mundicors": 0.02},
    "humilior": {"humilis": 0.96, "humilio": 0.04},
    "occisorum": {"occido#1": 0.92, "occisus": 0.06, "occisor": 0.02},
    "pluuiis": {"pluuia": 0.95, "pluuius": 0.05},
    "laetantes": {"laetor": 0.96, "laeto": 0.02, "laetans": 0.02},
    "incidit": {"incido#1": 0.94, "incido#2": 0.06},
    "recto": {"rectus": 0.94, "recto": 0.03, "rego": 0.03},
    "perfectam": {"perfectus#1": 0.92, "perficio": 0.08},
    "decoris": {"decor": 0.90, "decorus": 0.04, "decus#1": 0.04, "decoris": 0.02},
    "pauere": {"paueo": 0.96, "pasco": 0.04},
    "uenirem": {"uenio": 0.98, "ueneo": 0.02},
    "pastum": {"pastus#2": 0.94, "pasco": 0.04, "pastus#1": 0.02},
    "iecit": {"iacio": 0.98, "inicio": 0.02},
    "auium": {"auis": 0.98, "auius": 0.02},
    "creuisse": {"cresco": 0.97, "cerno": 0.03},
    "portenta": {"portentum": 0.95, "portendo": 0.05},
    "iacula": {"iaculum": 0.97, "iaculus": 0.03},
    "fornicatae": {"fornicor": 0.96, "fornicatus": 0.04},
    "occisum": {"occido#1": 0.92, "occisus": 0.08},
    "laetantium": {"laetor": 0.96, "laeto": 0.02, "laetans": 0.02},
    "desertas": {"desertus": 0.92, "desero#2": 0.08},
    "peius": {"malus#1": 0.94, "peius": 0.06},
    "utrasque": {"uterque": 0.96, "utrasque": 0.04},
}

# lemma-level manual priors: lemma key -> pseudo-count added to the corpus count, for L&S homographs
# whose paradigms coincide completely, so the Studio text gives no unambiguous evidence; chosen from the
# KWIC samples (e.g. every sampled 'caelum/caeli' is the sky, every 'servus' the servant).
_LEMMA_PRIOR: Dict[str, float] = {
    "lat:caelum#2": 2000.0,      # the sky / heaven (caelum#1 = chisel)
    "lat:servus#2": 1500.0,      # slave, servant (servus#1 = adj. slavish)
    "lat:Aegyptus#1": 800.0,     # Egypt (Aegyptus#2 = a king)
    "lat:caro#2": 1000.0,        # flesh (caro#1 = to card wool)
    "lat:peccatum": 1500.0,      # sin (the noun; rival: participle of pecco)
    "lat:pactum": 300.0,         # covenant (rival: participle of paciscor)
    "lat:mandatum": 300.0,       # commandment (rival: participle of mando)
    "lat:singuli": 300.0,        # distributive numeral (rival: L&S stub singulus)
    "lat:filius": 500.0,         # son (rivals: filum 'thread', filia in 'filiis')
    "lat:vinea": 300.0,          # vineyard (L&S headword; rival: fem. of vineus)
    "lat:volucris": 300.0,       # bird, 'volucres caeli' (rival: adj. volucer)
    "lat:patria": 200.0,         # fatherland (rival: fem. of patrius)
    "lat:Elias#2": 300.0,        # the prophet Elijah (Elias#1 is 'Elean', a woman of Elis: 'v. Elis')
    "lat:edo#1": 200.0,          # 'eat': 15/15 present-system forms read (edunt, edent, edetis); edo#2 'give
                                 # out' has its own perfect edidi / editus
    "lat:succido#2": 50.0,       # 'cut down' (lucos succidit): 12/12; succido#1 'fall under' unattested
    "lat:Syrus#2": 300.0,        # 'Syrian' (Bathuel Syri, Naaman Syrus): 27/27, never the island Syros (19 Nov)
    "lat:fornicatio#2": 500.0,   # 'fornication' (Vulg.); fornicatio#1 is 'vaulting, arch'
    "lat:Simon#1": 500.0,        # biblical Simon (Vulg.); Simon#2 is Pliny's statuary, Simo#2 Plautus' character
    "lat:Silo": 400.0,           # Shiloh (1-2 Sam, Josh, Judg, Jer, Ps); rival silo 'snub-nosed' / Silus
    "lat:licet": 300.0,          # 'it is lawful / although'; liceo#1 'be for sale' unattested in Vulgate
    "lat:animal": 1500.0,        # 'living creature, animal'; animalis 'aërial' unattested in Vulgate (outweighs A3 slot prior)
    # Stage 3C-2 KWIC-verified biblical lemma priors (each verified on Studio Vulgate contexts, 19 Nov 2026)
    "lat:sanctus": 1500.0,       # 'holy, saint'; sancio 'to ratify' virtually unattested (p=2)
    "lat:beatus": 500.0,         # 'blessed'; beo 'make happy' (p=0) and beatum (n.) unattested
    "lat:rectus": 400.0,         # 'right, upright, straight'; rego VPP virtually unattested
    "lat:votum": 300.0,          # 'vow, offering'; voveo/veto VPP
    "lat:delictum": 400.0,       # 'sin, offence'; delinquo VPP
    "lat:pullus#1": 300.0,       # 'young animal, foal, young pigeon'; pullus#2/#3 ('pure'/'dark') never biblical
    "lat:faber#1": 250.0,        # 'smith, craftsman'; faber#3 (dory sunfish) never biblical
    "lat:pilus#1": 300.0,        # 'hair'; pilus#2 (Roman centurion division) never biblical
    "lat:excelsus": 300.0,       # 'high, Most High'; excello VPP unattested (p=0)
    "lat:planctus": 300.0,       # 'lamentation, mourning'; plango VPP
    "lat:fletus#2": 300.0,       # 'weeping, wailing'; fleo VPP
    "lat:luctus": 250.0,         # 'mourning, grief'; lugeo VPP
    "lat:ululatus": 250.0,       # 'wailing, howling'; ululo VPP
    "lat:sponsus#1": 300.0,      # 'bridegroom'; spondeo VPP / sponsus#3
    "lat:cultus#2": 250.0,       # 'worship, service'; colo#1 VPP / cultus#1
    "lat:tributum": 300.0,       # 'tribute, tax'; tributus#2 ('by Roman tribes') never biblical
    "lat:serpens": 250.0,        # 'serpent, snake'; serpo part.
    "lat:praepositus#2": 250.0,  # 'overseer, officer, governor'; praepono VPP
    "lat:Sara": 300.0,           # biblical Sarah (Vulgate Sara / Saram / Sarae)
    "lat:Anna": 200.0,           # biblical Hannah / Anna (never abl. of Annas)
    "lat:osculor": 300.0,        # 'to kiss'; osculo#1/#2 never biblical
    "lat:nongenti": 250.0,       # 'nine hundred'; nongentus (Roman election inspector) never biblical
    "lat:decretum": 250.0,       # 'decree, ordinance'; decerno VPP
    "lat:salutaris": 200.0,      # 'saving, salvation' (in salutari tuo, Deo salutari); never saluto inf. pass.
    "lat:potentia": 300.0,       # 'power, might'; never neut. pl. of potens
    "lat:dilectus#1": 350.0,     # 'beloved' (dilectus meus, dilecto meo); delectus#2 (military levy) never biblical
    "lat:aspectus#2": 300.0,     # 'sight, appearance' (26/26 in Vulgate); aspicio VPP
    "lat:gressus#2": 300.0,      # 'step, footstep' (30/30 in Vulgate); gradior VPP
    "lat:stratum": 250.0,        # 'bed, couch, covering'; sterno VPP / stratus#2/#3
    # Stage 3C-3 KWIC-verified biblical lemma priors (19 Nov 2026)
    "lat:Tyrus": 300.0,          # Tyre ('rex Tyri' 23/23); rival tyrus (cheese)
    "lat:Aethiops": 300.0,       # Ethiopian ('Aethiopes'); rival Aethiopis (herb)
    "lat:Sale": 100.0,           # Shelah ('Sale' capitalised proper name; lowercase 'sale' stays lat:sal)
    "lat:legatus": 250.0,        # 'ambassador, envoy' ('legatos', 'legati'); lego#1 VPP
    "lat:occultus": 250.0,       # 'hidden, secret' ('occulta', 'occultis'); occulo VPP
    "lat:adulter#1": 200.0,      # 'adulterer' ('adulteri'); adultero V1A
    "lat:magus#1": 200.0,        # 'magician, wise man, Magus' ('magos'); magus#2 (adj.)
    "lat:respectus#2": 200.0,    # 'regard, respect'; respicio VPP
    "lat:partus#2": 200.0,       # 'birth, bringing forth'; pario VPP
    "lat:transitus#2": 200.0,    # 'passage, crossing'; transeo VPP
    "lat:exitus#2": 200.0,       # 'going out, exit, end'; exeo VPP
    "lat:jubilum": 200.0,        # 'joyful shout' ('jubilo'); jubilo verb
    "lat:rete": 200.0,           # 'net' ('retia'); rare L&S variants retia/retium
    "lat:assiduus#2": 150.0,     # 'continual, diligent' (adj.); assiduus#1 (Roman tax class) never biblical
    "lat:famulus#1": 200.0,      # 'servant'; famula/famulus#2
    "lat:contemplor": 150.0,     # 'to gaze upon, behold'; rare contemplo/contemplatus
    "lat:limus#2": 200.0,        # 'mud, slime, clay' ('de limo terrae'); limo verb ('to file') never biblical
}


def _studio_latin_rows(conn: sqlite3.Connection) -> Iterator[Tuple[str, int, int, str]]:
    q = ("SELECT c.book_slug, c.chapter, v.verse, v.critical_text FROM verses v JOIN chapters c ON c.id = v.chapter_id "
         "WHERE c.language = 'latin' ORDER BY c.id, v.verse")
    for row in conn.execute(q):
        yield row[0], int(row[1]), int(row[2]), row[3] or ""


def _connect_ro(path: Path) -> Optional[sqlite3.Connection]:
    if not path.exists():
        return None
    try:
        return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return None


# ---------------------------------------------------------------------------
# 8.  Token analysis
# ---------------------------------------------------------------------------

_ENCLITICS = ("que", "ne", "ue")
_PRON_CUM = {"mecum": "ego", "tecum": "tu", "secum": "sui", "nobiscum": "nos", "uobiscum": "uos",
             "quocum": "qui", "quacum": "qui", "quibuscum": "qui", "quicum": "qui"}
_MET = {"egomet": "ego", "memet": "ego", "mihimet": "ego", "temet": "tu", "tibimet": "tu", "semet": "sui",
        "sibimet": "sui", "nosmet": "nos", "nobismet": "nos", "uosmet": "uos", "uobismet": "uos"}
_SENT_END = set(".?!:;")


def _sentence_initial_flags(text: str, tokens: List[str]) -> List[bool]:
    """True for tokens at the start of the verse or after . ? ! : ; (the Clementine capitalises there)."""
    flags = []
    pos = 0
    for k, tok in enumerate(tokens):
        j = text.find(tok, pos)
        if j < 0:
            flags.append(k == 0)
            continue
        before = text[:j].rstrip(" \t\"'«»“”‘’()[]—–-")
        flags.append(k == 0 or not before or before[-1] in _SENT_END)
        pos = j + len(tok)
    return flags


class _Tagger:
    def __init__(self, idx: _Index):
        self.idx = idx
        self.cache: Dict[Tuple[str, bool, bool], Tuple] = {}

    # candidate lemma ids for a bare form, filtered by capitalisation: {lemma id: [(code, ending), ...]}
    def _cands(self, b: str, cap: bool) -> Dict[int, List[Tuple[str, str]]]:
        res: Dict[int, List[Tuple[str, str]]] = {}
        canon = self.idx.canon
        for i, pc, end in self.idx.analyse(b):
            i = canon.get(i, i)
            lem = self.idx.lemmas[i]
            if lem.proper and not cap and lem.key not in _LOWER_PROPER:
                continue
            if lem.pos in ("X", "ALIAS"):
                continue
            lst = res.setdefault(i, [])
            if (pc, end) not in lst:
                lst.append((pc, end))
        return res

    def _variant_cands(self, b: str, cap: bool) -> Tuple[Dict[int, List[Tuple[str, str]]], str]:
        """Candidates of documented spelling variants; every variant of the first tier that yields an
        analysis is pooled (prefix assimilation first, then letter-level variants)."""
        tried = {b}
        tiers = []
        tier1 = []
        for a, z in _PREFIX_VARIANTS:
            if b.startswith(a):
                tier1.append((z + b[len(a):], f"{a}->{z}"))
        tiers.append(tier1)
        tier2 = []
        for a, z in _VARIANT_RULES:
            k = b.find(a)
            while k >= 0:
                v = b[:k] + z + b[k + len(a):]
                # stricter evidence (after the 18 Nov verification: setim -> sitis, senum -> sinus, despexit ->
                # dispicio, hin -> in, palatii -> palatum): e -> i only after the first syllable
                # (caeremonia ~ caerimonia); h dropped only when four letters remain; ii -> i not word-finally
                ok = not ((a, z) == ("e", "i") and not re.search(r"[aeiouy]", b[:k])) and \
                    not ((a, z) == ("h", "") and len(v) < 4) and \
                    not ((a, z) == ("ii", "i") and k + 2 == len(b))
                if ok:
                    tier2.append((v, f"{a}->{z}"))
                k = b.find(a, k + 1)
        tiers.append(tier2)
        tier3 = []
        # Tier 3 (tried only when tiers 1-2 find nothing, so never competes with y->i such as clypeus -> clipeus):
        # Vulgate dropped initial silent h- (ariolos -> hariolos, arundinem -> harundinem, aruspices -> haruspices,
        # olera -> holera), dropped h after c (caracterem -> characterem), y/u (cypressus -> cupressus), and
        # single-consonant spellings (agressus -> aggressus, numulariorum -> nummulariorum)
        if len(b) >= 5 and b[0] in _VOW:
            tier3.append(("h" + b, "0->h"))
        if len(b) >= 6 and b.startswith("ag") and not b.startswith("agg"):
            tier3.append(("agg" + b[2:], "ag->agg"))
        if len(b) >= 7 and "c" in b:
            k = b.find("c")
            while k >= 0:
                if b[k:k + 2] != "ch":
                    tier3.append((b[:k] + "ch" + b[k + 1:], "c->ch"))
                k = b.find("c", k + 1)
        if len(b) >= 6 and "y" in b:
            k = b.find("y")
            while k >= 0:
                tier3.append((b[:k] + "u" + b[k + 1:], "y->u"))
                k = b.find("y", k + 1)
        if len(b) >= 8 and "m" in b and "mm" not in b:
            k = b.find("m")
            while k >= 0:
                tier3.append((b[:k] + "mm" + b[k + 1:], "m->mm"))
                k = b.find("m", k + 1)
        tiers.append(tier3)
        for tier in tiers:
            pooled: Dict[int, List[Tuple[str, str]]] = {}
            whys = []
            for v, why in tier:
                if not v or v in tried:
                    continue
                tried.add(v)
                c = self._cands(v, cap)
                if _VARIANT_NO_FUNCTION:
                    c = {i: a for i, a in c.items() if not self.idx.lemmas[i].noncontent}
                if c:
                    whys.append(why)
                    for i, anas in c.items():
                        lst = pooled.setdefault(i, [])
                        lst.extend(x for x in anas if x not in lst)
            if pooled:
                return pooled, "variant:" + ",".join(whys)
        return {}, ""

    def analyse_token(self, tok: str, initial: bool
                      ) -> Tuple[Dict[int, List[Tuple[str, str]]], Tuple[str, ...], List[str]]:
        cap = tok[:1].isupper()
        key = (tok, initial, cap)
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        b = _b(tok)
        notes: List[str] = []
        prefixes: Tuple[str, ...] = ()
        if b in _PRON_CUM:
            # pronoun + enclitic cum before any paradigm analysis: 'secum' is se + cum, not the adjective
            # secus 'lower'; 'nobiscum' is nos + cum (L&S's 'nobiscum, v. ego' cross-reference aside)
            j = _find_ls(self.idx, _PRON_CUM[b])
            if j is not None:
                out = ({j: [("closed", "")]}, ("E:cum",), notes)
                self.cache[key] = out
                return out
        if b == "cumque":
            # Vulgate 'Cumque' = conj. cum + -que ('and when'), not the classical indefinite adverb cumque
            j = _find_ls(self.idx, "cum", "2")
            if j is not None:
                out = ({j: [("closed", "")]}, ("E:que",), notes)
                self.cache[key] = out
                return out
        cands = self._cands(b, cap)
        if cands and not cap and all(pc == "alias" for anas in cands.values() for pc, _e in anas):
            # only an L&S spelling stub matches ('clypeo, v. clipeo' - the verb), but the same word is also a
            # case form of another stub's target ('clypeus, v. clipeus': abl. clypeo): pool the documented
            # spelling variants so that both readings compete
            vc, why = self._variant_cands(b, cap)
            if vc and any(i not in cands for i in vc):
                cands = dict(cands)
                for i, anas in vc.items():
                    cands.setdefault(i, anas)
                notes.append(why)
        if not cands and b in _MET:
            cands = {i: [("closed", "")] for i in [_find_ls(self.idx, _MET[b])] if i is not None}
            prefixes = ("E:met",)
        if not cands:
            # Vulgate fused clitic/prefix forms: haeccine (haec + -cine), quaenam (quae + -nam), utrumnam,
            # siquis/siqua/siquid (si + quis/quae/quid)
            if b == "haeccine":
                j = _find_ls(self.idx, "hic")
                if j is not None:
                    cands, prefixes = {j: [("closed", "")]}, ("E:cine",)
            elif b in ("quaenam", "quidnam", "quisnam", "quemnam", "quonam", "quibusnam"):
                j = _find_ls(self.idx, "quis", "1") if b != "quaenam" else _find_ls(self.idx, "qui", "1")
                if j is not None:
                    cands, prefixes = {j: [("closed", "")]}, ("E:nam",)
            elif b == "utrumnam":
                j = _find_ls(self.idx, "utrum")
                if j is not None:
                    cands, prefixes = {j: [("closed", "")]}, ("E:nam",)
            elif b in ("siquis", "siqua", "siquid", "siquod", "siquem", "siquam", "siquo", "siqui", "siquae"):
                j = _find_ls(self.idx, "quis", "1") if b[2:] in ("quis", "quid", "quem", "quo") else _find_ls(self.idx, "qui", "1")
                if j is not None:
                    cands, prefixes = {j: [("closed", "")]}, ("P:si",)
        if not cands:
            m = re.fullmatch(r"(se|me|te|nos|uos|id|nobis|uobis|mihi|tibi|sibi)(?:met)?(ips[a-z]+)", b)
            if m:
                c = self._cands(m.group(2), False)
                ips = _find_ls(self.idx, "ipse")
                if ips is not None and ips in c:
                    cands = {ips: c[ips]}
                    prefixes = ("P:" + b[: len(b) - len(m.group(2))],)
        if not cands and cap and self.idx.cap_mid.get(b, 0) > 0 and not b.endswith("que"):
            # a capitalised form that is never written in lower case and stands mid-sentence somewhere is
            # a name before it is a word + enclitic ('Josue' is Joshua, not the island Ios + -ve)
            found = _names_from_text(self.idx, b)
            if found:
                cands = {j: [("textname", "")] for j in found}
                notes.append("name attested in the Saints Latin text")
        if not cands:
            for enc in _ENCLITICS:
                if b.endswith(enc) and len(b) > len(enc) + 1:
                    rest = b[: -len(enc)]
                    if enc == "que" and rest in _PRON_CUM:
                        j = _find_ls(self.idx, _PRON_CUM[rest])
                        if j is not None:
                            cands = {j: [("closed", "")]}
                            prefixes = ("E:cum", "E:que")
                            break
                    c = self._cands(rest, cap)
                    if not c and enc == "que" and len(rest) >= 5 and (not cap or initial or not _cap_attested(self.idx, b)):
                        c, why_v = self._variant_cands(rest, cap)
                        if c and cap:
                            c = {i: a for i, a in c.items() if not self.idx.lemmas[i].proper}
                        if c:
                            notes.append(why_v)
                    if cap:
                        # never split an enclitic off a capitalised word to reach a proper name
                        # ('Ninive' is not Ninus + -ve, 'Parumne' is parum + -ne, not Paros)
                        c = {i: a for i, a in c.items() if not self.idx.lemmas[i].proper}
                    if c:
                        cands = c
                        prefixes = ("E:" + ("ve" if enc == "ue" else enc),)
                        break
        if not cands and cap:
            found = _names_from_text(self.idx, b)
            if found:
                cands = {j: [("textname", "")] for j in found}
                notes.append("name attested in the Saints Latin text")
        if not cands:
            # documented spelling variants.  A capitalised form that is never written in lower case and stands
            # mid-sentence is a name (Lachis, Achis, Tharsis, Caree, Manue ...), not a respelt Latin word: for it
            # only a biblical (TIPNR) name is accepted (Zechri ~ Zichri), never a classical name or a common word.
            # Words attested only sentence-initially ('Abjicite', 'Expectatis', 'Adsensi') may use Latin variants.
            name_only = cap and (not initial or self.idx.cap_mid.get(b, 0) > 0) and _cap_attested(self.idx, b)
            cands, why = self._variant_cands(b, cap)
            if name_only:
                cands = {i: a for i, a in cands.items() if all(pc == "tipnr" for pc, _e in a)}
            if cands:
                notes.append(why)
        if cap and cands and not initial and _cap_attested(self.idx, b) and \
                not any(not self.idx.lemmas[i].proper and self.idx.lemmas[i].pos == "N" and
                        len(self.idx.lemmas[i].hb) >= 6 for i in cands):
            # mid-sentence and never written in lower case: names attested in the text compete with the
            # other readings ('Petro' -> Petrus against L&S's Roman 'Petro, onis'; 'Judaeis' -> Judaeus
            # against Judaea), but never override a revered capitalised common noun (Scripturas, Salvatore)
            has_name = any(self.idx.lemmas[i].proper for i in cands)
            extra = [j for j in _names_from_text(self.idx, b, allow_e=not has_name) if j not in cands]
            if extra:
                cands = dict(cands)
                for j in extra:
                    cands[j] = [("textname", "")]
        if cap and cands:
            # a TIPNR English name that is really an oblique case of an attested Vulgate name
            # ('Eliam' = acc. of Elias) is not kept
            tip = [i for i, anas in cands.items() if all(pc == "tipnr" for pc, _e in anas)]
            if tip and _latin_oblique_of_attested(self.idx, b):
                cands = {i: a for i, a in cands.items() if i not in tip}
                if not cands:
                    j = _name_from_text(self.idx, b)
                    if j is not None:
                        cands = {j: [("textname", "")]}
                        notes.append("name attested in the Saints Latin text")
            elif tip:
                # the exact TIPNR name stands: a nominative merely inferred from the text ('Jehus' for Jehu,
                # 'Sara' for Sarai) does not compete with it
                cands = {i: a for i, a in cands.items() if not all(pc == "textname" for pc, _e in a)}
        out = (cands, prefixes, notes)
        self.cache[key] = out
        return out


# ---------------------------------------------------------------------------
# 9.  Saints editorial glosses (19 Nov 2026)
# ---------------------------------------------------------------------------
# Readers see one short English gloss per lemma.  Lewis & Short often opens with a literal, classical or rare
# sense (respondeo 'to promise', princeps 'first', gens 'a race or clan', pecco 'to miss', aries 'the Ram, a sign of
# the zodiac'), so the most frequent lemmas of the Saints Latin text (by token count) and the family heads of
# their roots have a reviewed gloss: the plain biblical sense first, then the other main senses, each checked
# against the Lewis & Short entry (Saints editorial wording; L&S CC BY-SA 4.0 consulted).  Format: one
# 'lemma key without "lat:" | gloss' per line.  Names are described from STEPBible TIPNR where they are not here.

_SAINTS_GLOSS_TEXT = """
sum#1|to be, exist
dominus|lord, master; the Lord
dico#2|to say, speak, tell
omnis|all, every, whole
filius|son; (plur.) children
deus|God; a god
facio|to make, do
terra|earth, land, ground
rex|king
dies|day
Israel|Israel: the people of Israel; also Jacob, the patriarch
venio|to come
do#1|to give
populus#1|people, nation
domus|house, home; household
video|to see, look, perceive
manus#1|hand; power; band (of men)
vir|man; husband
homo|man, human being
habeo|to have, hold
audio|to hear, listen
loquor|to speak, say
pater|father; (plur.) forefathers
aio|to say
mitto|to send; to put, throw
verbum|word, saying; thing
nomen|name
David|David: king of Israel, son of Jesse
civitas|city; state, citizenship
unus|one
frater|brother
cor|heart
Jesus|Jesus: Jesus Christ; also Joshua (son of Nun) and Jeshua
magnus|great, large
Judas|Judah, Judas: son of Jacob and his tribe; Judas Iscariot; Judas Maccabeus; others
pono|to put, place, set
bonus|good
universus|all, whole, entire
anima|soul, life; breath
multus|much, many
possum|to be able, can
princeps|prince, chief, ruler
servus#2|servant, slave
gens|nation, people; (plur.) the Gentiles
respondeo|to answer, reply
morior|to die
annus|year
via|way, road, path
malus#1|bad, evil
sanctus|holy, sacred
caelum#2|heaven, sky
Jerusalem|Jerusalem: the holy city, capital of Judah
sacerdos|priest
locus|place
tempus|time, season
opus|work, deed
facies|face; appearance, surface
Moses|Moses: the lawgiver who led Israel out of Egypt
praecipio|to command, instruct; to take beforehand
spiritus|spirit; breath, wind
aqua|water
invenio|to find, come upon
scio|to know
duo|two
ascendo|to go up, ascend, climb
oculus|eye
egredior|to go out, come forth
habito|to dwell, live, inhabit
sto|to stand
peccatum|sin, fault
sermo|word, speech, saying
medius|middle, the midst
voco|to call, summon, name
mons|mountain, hill
mille|a thousand
exercitus#2|army, host
accipio|to receive, take, accept
Aegyptus#1|Egypt
nolo|to be unwilling, not want
Christus|Christ, the Anointed One; (in the OT) the Lord's anointed
vox|voice, sound
cunctus|all, whole
lex|law
filia|daughter
percutio|to strike, smite, kill
nunc|now
sic|thus, so
ingredior|to go in, enter; to walk
os#1|mouth
comedo#1|to eat, devour
offero|to offer, bring, present
ignis|fire
judicium|judgment, justice; trial
vivo|to live
vero#1|truly, indeed; but
ibi|there
regnum|kingdom, reign
mulier|woman; wife
propheta|prophet
trado|to hand over, deliver up, betray
uxor|wife
caput|head; chief
pars|part, share, side
mare|sea
gloria|glory
sanguis|blood
iniquitas|iniquity, injustice
timeo|to fear, be afraid
aedifico|to build
tabernaculum|tent, tabernacle
scribo|to write
gladius|sword
surgo|to rise, arise, get up
sedeo|to sit; to stay, dwell
benedico|to bless; to praise
quaero|to seek, ask
vita|life
justus|just, righteous
caro#2|flesh
fio|to become, be made, happen
ita|so, thus
eo#1|to go
cado|to fall
dimitto|to send away, let go; to forgive
volo#1|to wish, want, will
porta|gate
templum|temple
conspectus#2|sight, presence
Saul|Saul: first king of Israel; also Saul (Paul) of Tarsus
ambulo|to walk
transeo|to pass over, cross, go past
mors|death
interficio|to kill, slay
congrego|to gather together, assemble
panis|bread, loaf
abeo|to go away, depart
fero|to bear, carry, bring
descendo|to go down, descend
diligo|to love, esteem
justitia|righteousness, justice
multitudo|multitude, great number
inimicus|enemy; hostile
septem|seven
Judaeus|Jew; Jewish; (plur.) the Jews
cognosco|to know, recognize, learn
credo|to believe, trust
altaria|altar
urbs|city
tunc|then
pes|foot
gratia|grace, favour; thanks
misericordia|mercy, compassion
judico|to judge
custodio|to keep, guard, watch
ago|to do, act; to drive, lead
singuli|one each, each one, individual
pax|peace
tollo|to take up, lift; to take away
ubi|where
fugio|to flee
nox|night
finis|end; border, boundary
sapientia|wisdom
aufero|to take away, carry off
mensis|month
Jacob|Jacob: the patriarch Jacob, also called Israel
virtus|strength, power; virtue, mighty deed
lapis|stone
reverto|to return, turn back
regno|to reign, rule
Aaron|Aaron: brother of Moses, the first high priest
lignum|wood, tree
vado#1|to go
constituo|to set up, appoint, establish
mater|mother
saeculum|age, world; for ever (in saeculum)
aeternus|eternal, everlasting
angelus|angel; messenger
eligo|to choose
bibo#1|to drink
puer|boy, child; servant
fortis|strong, brave, mighty
aurum|gold
gigno|to beget, bear
clamo|to cry out, call aloud
testimonium|testimony, witness
tres|three
sequor|to follow
novus|new
quinque#1|five
fides#1|faith, trust; faithfulness
exeo|to go out, depart
aperio|to open
adduco|to bring, lead
Babylon|Babylon
quomodo|how, in what way; as
semen|seed, offspring
viginti|twenty
pecco|to sin
totus#1|whole, all
Salomon|Solomon: son of David, king of Israel
adhuc|still, yet; until now
holocaustum|burnt offering, holocaust
servio|to serve
vas#2|vessel, dish, utensil
educo#1|to lead out, bring out
nosco|to know, get to know
porro|moreover, then; further on
impius|ungodly, wicked
veritas|truth
castrum|camp; fortress
discipulus|disciple, pupil
reddo|to give back, render, repay
ager|field, land
regio|region, country
impleo|to fill, fulfil
circuitus#2|circuit; (in circuitu) round about
ira|anger, wrath
Abraham|Abraham: the patriarch
dux|leader, chief
coepio|to begin
adoro|to worship, adore
maneo|to remain, stay, abide
abscondo|to hide, conceal
possideo|to possess, own
argentum|silver; money
converto|to turn, turn back; to convert
pereo|to perish, be lost
quattuor|four
cubitum|cubit; elbow
mandatum|commandment, order
decem|ten
capio#1|to take, seize, capture
duco|to lead; to take (a wife)
Levites|Levite
excelsus|high, lofty; (as noun) high place
generatio|generation; begetting, offspring
senex|old man, elder; old
relinquo|to leave, leave behind, abandon
sanctifico|to sanctify, make holy, consecrate
hodie|today
porto|to carry, bear
familia|family, household
tribus|tribe
desertus|desert, wilderness; deserted
ostendo|to show, reveal
doceo|to teach
arca|ark; chest
dormio|to sleep
pauper|poor
fructus#2|fruit, produce
intro#2|to enter, go in
consilium|counsel, plan, advice
signum|sign, mark; standard
vinum|wine
Jonathas|Jonathan: son of Saul, friend of David; Jonathan Maccabeus; others
ovis|sheep
sapiens|wise
vestimentum|garment, clothing
lingua|tongue; language
derelinquo|to forsake, abandon
quare|why; wherefore
primus|first
oro|to pray; to beg
corpus|body
recedo|to depart, withdraw, go back
accedo|to come near, approach
jam|now, already
foedus#2|covenant, treaty
Pharao|Pharaoh, king of Egypt
auris|ear
appareo|to appear
operor|to work, perform
libero|to deliver, set free
mane|morning; in the morning
potestas|power, authority
sol|sun
sacrificium|sacrifice
simul|together, at the same time
habitator|inhabitant, dweller
murus|wall
laudo|to praise
respicio|to look back, look upon, regard
aureus|golden, of gold
centum|a hundred
turba|crowd, multitude
fortitudo|strength, might
oleum|oil
sabbatum|sabbath
furor#2|fury, wrath, rage
divido|to divide
contero|to crush, break in pieces
Jordanes|Jordan, the river
interrogo|to ask, question
alienus|foreign, strange; another's; (as noun) stranger
placeo|to please
duodecim|twelve
exaudio|to hear, give ear to (a prayer)
possessio|possession
timor|fear
cogito|to think, consider, devise
bellum|war, battle
plenus|full
teneo|to hold, keep
Joseph|Joseph: son of Jacob; husband of Mary; Joseph of Arimathea; others
confundo|to confound, put to shame; to confuse
salus|salvation; safety, health
liber#4|book
suscipio|to receive, take up, support
juro|to swear, take an oath
Josue|Joshua: son of Nun, Moses' successor; Joshua (Jeshua) the high priest
nescio|not to know
proximus|neighbour; nearest, next
persequor|to persecute, pursue
immolo|to sacrifice, offer
grex|flock, herd
aries|ram; battering ram
Ephraim|Ephraim: son of Joseph, his tribe and its hill country
inde|thence, from there; thereafter
terminus|boundary, border, limit
reliquus|remaining, the rest
secundus|second; favourable
res|thing, matter, affair
annuntio|to announce, proclaim
Sion|Zion (Jerusalem)
bos|ox, bull, cow
haereditas|inheritance
pugno|to fight
salvus|safe, saved
bestia|beast, wild animal
affero|to bring, carry, offer
nuntio|to announce, tell, report
semper|always
ostium|door; entrance, mouth
triginta|thirty
eicio|to cast out, drive out
voluntas|will, wish; goodwill
proicio|to cast forth, throw down, cast away
manduco#1|to eat
maledico|to curse, revile
salvo|to save
effundo|to pour out, shed
pergo|to go on, proceed
suscito|to raise up, awaken
multiplico|to multiply, increase
spero|to hope, trust
assumo|to take up, take to oneself
Benjamin|Benjamin: youngest son of Jacob, and his tribe
numerus|number
propterea|therefore, for that reason
iterum|again
agnus|lamb
tango|to touch
exalto|to exalt, lift up
sanctuarium|sanctuary, holy place
ecclesia|church, assembly
deficio|to fail, faint, come to an end; to fall away
irascor|to be angry
magis#1|more, rather
Paulus|Paul: the apostle Paul (Saul of Tarsus)
tenebrae|darkness
confiteor|to confess, acknowledge; to praise
paro#1|to prepare, make ready
tertius|third
consurgo|to rise up, arise
vinea|vineyard; vine
cognatio|kindred, family, relatives
equus|horse
rogo|to ask, pray, beseech
Petrus|Peter: the apostle Simon Peter
valde|very, greatly, exceedingly
quadraginta|forty
Jeremias|Jeremiah: the prophet; others of the name
statim|at once, immediately
debeo|to owe; ought, must
Moab|Moab: the land and people of Moab
deleo|to blot out, destroy
Joannes|John: John the Baptist; the apostle John; others
consumo|to consume, destroy, use up
introeo|to go in, enter
extendo|to stretch out, extend
nubes|cloud
labium|lip
impono|to put on, lay upon, impose
idcirco|therefore, for that reason
causa|cause, reason, case; sake
peccator|sinner
solitudo|wilderness, desert; solitude
devoro|to devour, swallow up
lux|light
flumen|river, stream
Philisthiim|Philistines
pario#2|to bear, bring forth
invoco|to call upon, invoke
levo#1|to lift up, raise
polluo|to defile, pollute, profane
Samuel|Samuel: the prophet and judge
oratio|prayer; speech
repleo|to fill, fill up
ignoro|not to know, be ignorant
sepelio|to bury
vitulus|calf, young bull
tantum|only; so much
stultus|foolish; a fool
dextera|right hand
idolum|idol, image
Manasses|Manasseh: son of Joseph and his tribe; the king of Judah
leo#2|lion
cogitatio|thought, purpose
patior|to suffer, endure; to allow
Joab|Joab: commander of David's army
parvulus|little one, child; very small
mundus#2|world; universe
primogenitus|firstborn
quinquaginta|fifty
immundus|unclean, impure
perdo|to destroy; to lose
compleo|to fill, fulfil, complete
nimis|very, exceedingly; too much
aquilo|north; north wind
septimus|seventh
unde|whence, from where
statuo|to set up, establish, decree
tribulatio|tribulation, distress
parvus|small, little
laetor|to rejoice, be glad
scientia|knowledge
cibus|food
hora|hour
atrium|court, forecourt
ventus|wind
fidelis|faithful, trustworthy
ceterus|the rest, the other
nuntius|messenger; message
sustineo|to bear, endure; to wait for, sustain
humilio|to humble, bring low
apprehendo|to seize, take hold of; to understand
similiter|likewise, in like manner
jumentum|beast of burden, cattle
sumo|to take, take up
latus#2|side
valles|valley
praeparo|to prepare
Galaad|Gilead: the region east of the Jordan; also a man of that name
gaudium|joy, gladness
Samaria|Samaria: the city and region
vestis|garment, clothing
currus|chariot
vae|woe!
spes|hope
misereo|to have mercy, have pity
recordor|to remember
decimus|tenth
sex|six
jubeo|to command, order, bid
Ezechias|Hezekiah: king of Judah
soror|sister
induo|to put on, clothe
fames|famine, hunger
ideo|therefore
amicus#2|friend
averto|to turn away, avert
moveo|to move, stir
bene|well
potens|mighty, powerful
servo|to keep, observe, preserve
hostia|sacrificial victim, offering
amplius|more, any more, further
hostis|enemy
scriba|scribe
columna|pillar, column
dolor|pain, sorrow, grief
munus|gift, offering; office, duty
altus#1|high, deep
desero#2|to forsake, desert, abandon
destruo|to destroy, pull down
oportet|it is necessary, one must
indico#1|to show, declare, make known
iter|way, journey
pecunia|money; property
plus|more; (plur.) many, several
ministro|to minister, serve
considero|to consider, look at closely
invicem|one another, mutually; in turn
sors|lot, portion
remaneo|to remain, stay behind
ancilla|handmaid, maidservant
declino|to turn aside, decline, avoid
exspecto|to wait, await, expect
peto|to ask, seek, request; to attack
mensura|measure
operio|to cover
obliviscor|to forget
beatus|blessed, happy
mando#1|to command, commit, entrust
Assyrius|Assyrian; (plur.) the Assyrians
inquam|to say
conforto|to strengthen, comfort
virga|rod, staff; branch
thesaurus|treasure, treasury, storehouse
labor#2|labour, toil, hardship
fleo|to weep
victima|victim, sacrifice
benedictio|blessing
affligo|to afflict, oppress, strike down
pacificus|peaceable; (sacrifice) peace offering
iniquus|unjust, wicked
latitudo|breadth, width
addo|to add, increase
Isaac|Isaac: son of Abraham, father of Jacob and Esau
narro|to tell, relate, declare
odi|to hate
Judaea|Judaea, Judah (the land)
malitia|malice, wickedness
visio|vision, sight
revelo|to reveal, uncover
tam|so, so much
separo|to separate, set apart
Syria|Syria
cesso|to cease, stop
cornu|horn
dexter|right, on the right hand
vendo|to sell
oblatio|offering, oblation
argenteus|of silver; (as noun) a silver coin
visito|to visit; to punish
petra|rock
laus|praise
longe|far, far off
praedico#1|to preach, proclaim
solus#1|alone, only
mendacium|lie, falsehood
saluto|to greet, salute
doctrina|teaching, doctrine
Elias#2|Elijah: the prophet
pastor|shepherd
permaneo|to remain, continue, endure
disperdo|to destroy utterly, ruin
pecus#1|cattle, flock
sempiternus|everlasting, eternal
Aegyptius|Egyptian
obsecro|to beseech, entreat; I pray (you)
convenio|to come together, assemble; to agree
dirigo|to direct, guide; to set straight
judex|judge
colligo#1|to gather, collect
recipio|to receive, take back
pactum|covenant, agreement
eruo|to deliver, rescue; to pluck out
gaudeo|to rejoice
Absalom|Absalom: son of David
exsulto|to exult, rejoice greatly
appropinquo|to draw near, approach
transfero|to carry over, transfer
procedo|to go forth, proceed
tuba|trumpet
praesens|present; in person
Ammon|Ammon: the Ammonites and their land
torreo|to roast, parch, scorch
comburo|to burn up
redimo|to redeem, buy back, ransom
confringo|to break in pieces, shatter
caritas|love, charity
vultus|face, countenance
dignus|worthy
indignatio|indignation, wrath
pasco|to feed, pasture
reliquiae|remnant, remains
abominatio|abomination
Pharisaeus|Pharisee
merces#1|reward, wages
superbia|pride, arrogance
deduco|to lead, bring, conduct
prior|former, first, earlier
ministerium|ministry, service
bracchium|arm
honor|honour
Chanaan|Canaan: the land of Canaan; Canaan son of Ham
testamentum|covenant, testament; will
praelium|battle
Jeroboam|Jeroboam: king of Israel (two kings of the name)
Jerosolyma|Jerusalem
psalmus|psalm
quartus|fourth
vesper|evening
induco|to bring in, lead in; to put on
oriens|east, sunrise; rising
puto|to think, suppose, reckon
infero|to bring in, inflict
dives|rich
prius|before, first, earlier
divitiae|riches, wealth
succendo|to set on fire, kindle
mensa|table
initium|beginning
septuaginta|seventy
octo|eight
emo|to buy
introduco|to bring in, lead in
sepulcrum|tomb, sepulchre
mirabilis|wonderful, marvellous
disciplina|discipline, instruction, correction
similis|like, similar
os#2|bone
pulvis|dust
substantia|substance, possessions; being
natio|nation, people
magnifico|to magnify, extol
siclus|shekel
occurro|to meet, run to meet
conturbo|to trouble, disturb, confound
summus|highest, chief
curro|to run
animus|mind, heart, spirit
probo|to prove, test; to approve
custodia|guard, watch, custody
laboro|to labour, toil; to be in distress
mundo|to cleanse, purify
eques|horseman, rider
deprecor|to pray, entreat; to beg off
carcer|prison
paenitentia|repentance, penance
fons|fountain, spring
taceo|to be silent
solvo|to loose, release; to pay
viduus|widowed; (fem. as noun) widow
minister|minister, servant, attendant
thronus|throne
glorior|to glory, boast
nascor|to be born
altitudo|height, depth
ducenti|two hundred
longitudo|length
somnium|dream
opprobrium|reproach, disgrace
robustus|strong, mighty; (as noun) mighty man
asinus|ass, donkey
confirmo|to confirm, strengthen, establish
talis|such
requies|rest
Achab|Ahab: king of Israel, husband of Jezebel
paries|wall (of a house)
ungo|to anoint
laetitia|joy, gladness
Nabuchodonosor|Nebuchadnezzar: king of Babylon
creo|to create
consolor|to console, comfort
platea#1|street, broad way
reduco|to lead back, bring back
advena|stranger, sojourner
modicus|little, small, moderate; (adv.) a little while
tento|to tempt, try, test
resisto|to resist, withstand
dominor|to rule, have dominion
disco|to learn
Amorrhaeus|Amorite
canticum|song, canticle
pervenio|to come to, arrive, reach
magister|master, teacher
similitudo|likeness, similitude
orientalis|eastern
inclino|to bend, incline, bow
Esau|Esau: son of Isaac, brother of Jacob
vasto|to lay waste, devastate
commoveo|to move, stir up, shake
semita|path
lego#2|to read; to gather
auxilium|help, aid
Josaphat|Jehoshaphat: king of Judah; also the valley of Jehoshaphat and others
Daniel|Daniel: the prophet; others of the name
juvenis|young man, youth; young
oboedio|to obey
corruo|to fall down, collapse
glorifico|to glorify
basis|base, pedestal
captivitas|captivity
confido|to trust, be confident
fundo#1|to pour out, shed
sano|to heal
virgo|virgin, maiden
introitus#2|entrance, entering in
scindo|to tear, rend, split
praeda|prey, spoil, booty
primitiae|firstfruits
primum|first, at first
Simon#1|Simon: Simon Peter; other men of the name (the Zealot, the Pharisee, of Cyrene, Maccabeus)
tentorium|tent
odor|odour, smell, fragrance
hircus|he-goat
navis|ship
Galilaea|Galilee
lumen|light
apostolus|apostle
fluvius|river
Cherub|cherub; (plur. cherubim) cherubim
adolesco|to grow up
requiro|to seek, require, inquire
evangelium|gospel, good news
planto|to plant
pariter|together, likewise, equally
plebs|people, common people
o|O!
semino|to sow
synagoga|synagogue; assembly, congregation
justifico|to justify
observo|to observe, keep, watch
scelus|crime, wickedness
venter|belly, womb
radix|root
pondus|weight, burden
mens|mind
pulcher|beautiful, fair
meridies|noon; south
sinister|left, on the left
numero#1|to number, count
clamor|cry, shout, clamour
pretium|price, value
tribuo|to grant, give, bestow
paucus|few, little
erigo|to raise up, set up, erect
Levi|Levi: son of Jacob; also Levi (Matthew) the apostle
imperium|command, rule, empire
ordo|order, rank, row
collis|hill
caecus|blind
dimidius|half
corona|crown, garland
baptizo|to baptize
genus#1|kind, race, family
subverto|to overthrow, overturn
immaculatus|spotless, undefiled
suburbanus|suburb, (plur.) pasture-lands round a city
parabola|parable, proverb
daemonium|demon, devil
confusio|confusion, shame
epistola|letter, epistle
decipio|to deceive
requiesco|to rest
despicio|to despise, look down on
omnipotens|almighty
extremus|last, outermost, extreme
praetereo|to pass by, pass over
memoria|memory, remembrance
delictum|offence, sin
pretiosus|precious, costly
grandis|great, large, grown-up
esca|food, meat
circumeo|to go round, surround
Chaldaeus|Chaldean; (plur.) the Chaldeans
armentum|herd, cattle
vere|truly, indeed
erro#1|to wander, go astray, err
Ruben|Reuben: eldest son of Jacob, and his tribe
turbo#1|to trouble, disturb
onus|burden, load; (prophetic) burden, oracle
rectus|right, upright, straight
talentum|talent (a weight or sum of money)
Libanus#1|Lebanon
quippe|for indeed, surely
consummo|to finish, complete, accomplish
turris|tower
illuc#2|thither, to that place
solium|throne
canto|to sing
sedes|seat, throne; dwelling
incensum|incense
quintus|fifth
adeps|fat
sexaginta|sixty
trecenti|three hundred
Hebron|Hebron: the city in Judah; also a Levite of the name
memini|to remember
cito#1|quickly, soon
Gad|Gad: son of Jacob, and his tribe; also Gad the prophet
orbis|world (orbis terrae); circle
attendo|to attend, give heed, take heed
cur|why
prohibeo|to forbid, hinder, restrain
arcus|bow; rainbow; arch
liber#1|free
uterus|womb
comprehendo|to seize, take hold of; to comprehend
sacrifico|to sacrifice, offer sacrifice
contristo|to sadden, grieve
resurgo|to rise again
Maria#1|Mary: the mother of Jesus; Mary Magdalene; other women of the name; also Miriam, sister of Moses
vescor|to eat, feed on
aspicio|to look at, behold
ineo|to enter, go in; to begin; to make (a covenant)
Dan|Dan: son of Jacob, his tribe and the city of Dan
desuper|from above, above
postulo|to ask, demand, request
puella|girl, maiden
colo#1|to worship; to till, cultivate; to dwell
vanitas|vanity, emptiness
principium|beginning; principality
solum#2|only, alone
nequaquam|by no means, not at all
moror#1|to delay, tarry, stay
huc|hither, here
jugum|yoke
praecedo|to go before, precede
lugeo|to mourn, lament
adjuvo|to help, aid
species|appearance, form, beauty
subicio|to subject, put under
Bethel|Bethel: the town north of Jerusalem
irruo|to rush upon, fall upon
afflictio|affliction, distress
arbor|tree
postea|afterwards
valeo|to be strong, be able; to be well
arguo|to rebuke, reprove, convict
ala|wing
durus|hard, harsh, stubborn
vigesimus|twentieth
saturo|to fill, satisfy
Jericho|Jericho: the city near the Jordan
curo|to care for, heal, take care
manifesto#2|to manifest, make known
cresco|to grow, increase
obtineo|to obtain, hold, possess
reputo|to reckon, count, consider
circumdo|to surround, encompass
Eleazar|Eleazar: son of Aaron and high priest; others of the name
tabula|tablet, board
lucerna|lamp
fiducia|confidence, trust
Antiochus|Antiochus: name of Seleucid kings of Syria (Maccabees)
perficio|to finish, perfect, accomplish
cano|to sing
ferrum|iron
sensus#2|sense, understanding, mind
convivium|feast, banquet
muto#1|to change
infernus|hell, the underworld; lower
inferus|lower; (plur.) the dead, the underworld
dens|tooth
spolium|spoil, plunder
sollemnitas|solemnity, feast, festival
Baal|Baal: the Canaanite god; also a man of the name
sagitta|arrow
proelium|battle
provoco|to provoke, challenge
umbra|shadow, shade
donum|gift
detraho|to detract, slander; to draw down, take away
infirmus|weak, sick
mel|honey
flamma|flame
perpetuus|perpetual, everlasting
vivus|living, alive
infirmitas|infirmity, weakness, sickness
erudio|to instruct, teach
fundamentum|foundation
profero|to bring forth, bring out
piscis|fish
verto|to turn
occursus|meeting; (in occursum) to meet
foris#2|outside, without
praebeo|to offer, give, provide
accido#2|to happen, befall; to fall upon
desiderium|desire, longing
impero|to command, order
caedo|to cut, strike, kill
ruina|ruin, fall
Joas|Joash: king of Judah; king of Israel; others of the name
appello#2|to call, name; to appeal
stella|star
quingenti|five hundred
Chananaeus|Canaanite
Damascus|Damascus
militia|warfare, service; host (of heaven)
eripio|to deliver, rescue, snatch away
restituo|to restore
angulus|corner
scriptura|scripture, writing
lepra|leprosy
laqueus|snare, noose
Philisthaeus|Philistine
foras|out, outside, forth
custos|guard, keeper, watchman
simila|fine flour
appendo|to weigh
innocens|innocent
caerimonia|ceremony, rite, ordinance
memor|mindful
calix|cup, chalice
prudens|prudent, wise
pontifex|high priest, priest
munitus|fortified, defended
discedo|to depart, go away
Eliseus|Elisha: the prophet
illic#2|there
campester|level, of the plain; (as noun) plain
rapio|to seize, snatch, carry off
dolus|deceit, guile
insidiae|ambush, snare, plot
contineo|to contain, hold together, restrain
incipio|to begin
castrametor|to encamp, pitch camp
desidero|to desire, yearn, long
mundus#1|clean, pure
prudentia|prudence, understanding
gyrus|circle; (in gyro) round about
vestibulum|porch, vestibule
contamino|to defile, pollute
blasphemo|to blaspheme, revile
Abner|Abner: commander of Saul's army
Azarias|Azariah: Uzziah king of Judah; companion of Daniel; others of the name
Sedecias|Zedekiah: last king of Judah; others of the name
Isaias|Isaiah: the prophet
superbus|proud, haughty
avis|bird
adhaereo|to cleave, cling, adhere
quadringenti|four hundred
camelus|camel
festino|to hasten, make haste
nego|to deny, refuse
cinis|ashes
vicis|turn, change; stead (vicem)
votum|vow, offering
turma|troop, company
salvator|saviour
consecro|to consecrate, dedicate
adversarius|adversary, enemy
testis#1|witness
Zacharias|Zechariah, Zachary: the prophet; the father of John the Baptist; others
patientia|patience
adjutor#2|helper
socius|companion, partner, ally
procul|far off, at a distance
sino|to let, allow, permit
Edom|Edom: the land of Esau's descendants
frumentum|grain, corn, wheat
gravis|heavy, grievous, severe
vestio|to clothe
necessarius|necessary; (as noun) relative, friend
Iob|Job: the man of Uz
accingo|to gird
frustra|in vain
vectis|bar, pole (for carrying)
abundo|to abound, overflow
suavis|sweet, pleasant
concipio|to conceive
cadaver|corpse, carcass
promitto|to promise
juramentum|oath
plango|to lament, mourn, beat (the breast)
miles|soldier
defero|to bring, carry down, report
odium#1|hatred
provincia|province
miror|to wonder, marvel
qualis|of what kind; such as
applico|to apply, join; to come to land
contemno|to despise, scorn
auster#1|south; south wind
ara|altar
intellectus#2|understanding
antiquus|ancient, old
Tyrus|Tyre
adsum|to be present
pertineo|to belong, pertain; to reach
lac|milk
captivus|captive, prisoner
lavo|to wash
insuper|moreover, besides; above
eloquium|word, utterance, saying
Basan|Bashan
Sadoc|Zadok: the priest; others of the name
Joiada|Jehoiada: the high priest; others of the name
Jehu|Jehu: king of Israel; Jehu the prophet, son of Hanani
vigilo|to watch, be awake
Pilatus|Pontius Pilate, governor of Judaea
tunica|tunic, coat
amo|to love
prosum#1|to profit, be of use
arma|arms, weapons
collum|neck
gradus|step, degree
anniculus|one year old, yearling
honoro|to honour
bellator|warrior
insipiens|foolish, unwise; fool
messis|harvest
depono|to lay down, put off, depose
jaceo|to lie
modo|now, just now; only
sufficio|to suffice, be enough
vanus|vain, empty
sacerdotium|priesthood
sanctificatio|sanctification, holiness
desolo|to make desolate, lay waste
Josias|Josiah: king of Judah
abyssus|abyss, deep
gradior|to walk, step
insula|island
campus#1|plain, field
servitus|bondage, servitude, service
circumcido|to circumcise
stirps|root, stock, offspring
azymus|unleavened; (neut. plur.) unleavened bread
Abimelech|Abimelech: king of Gerar; son of Gideon; others of the name
quiesco|to rest, be quiet
cras|tomorrow
eunuchus|eunuch, chamberlain
vinco|to conquer, overcome
sonitus|sound, noise
vulnero|to wound
purus|pure, clean
effugio|to escape, flee away
iracundia|wrath, anger
metior|to measure
herba|grass, herb
erubesco|to blush, be ashamed
vehementer|greatly, exceedingly
habitatio|dwelling, habitation
tendo|to stretch, extend, bend (a bow)
monumentum|tomb, monument, memorial
maledictio|curse, malediction
claudo#1|to shut, close
ligo#1|to bind, tie
lacus|pit, lake, cistern; winepress
remitto|to forgive, remit; to send back
villa|village, country house
profundus|deep, profound
seduco|to seduce, lead astray
expando|to spread out
adoleo#1|to burn (as an offering)
ignominia|disgrace, shame
praevaricor|to transgress
verum#3|but, yet
munitio|fortification, stronghold
exsurgo|to rise up, arise
Asa|Asa: king of Judah
resurrectio|resurrection
imago|image, likeness
volucris|bird, fowl
ultio|vengeance, revenge
ramus|branch, bough
celebro|to celebrate, keep (a feast)
puteus|well, pit
peregrinus|stranger, foreigner; foreign
reperio|to find
fluo|to flow
supervenio|to come upon, overtake
aes|bronze, brass; money
purpura|purple (cloth)
candelabrum|lampstand, candlestick
frons#2|forehead, brow; front
corripio|to rebuke, chastise; to seize
obsideo|to besiege
perditio|perdition, destruction
conculco|to trample, tread underfoot
Demetrius|Demetrius: kings of Syria (Maccabees); the silversmith of Ephesus; others
quemadmodum|as, just as; how
masculus|male
summitas|top, summit
alienigena|foreigner, stranger
soleo|to be accustomed, be wont
magnitudo|greatness, size
convoco|to call together, assemble
numquam|never
longus|long
sculptilis|graven, carved; (as noun) graven image
festus|festal; (as noun) feast day
volumen|scroll, roll, book
humilis|humble, lowly
impietas|ungodliness, impiety
impetus|attack, onset, rush
retribuo|to repay, render, reward
psallo|to sing psalms, sing praise
Joram|Joram, Jehoram: kings of Judah and of Israel; others of the name
germino|to sprout, bud, bring forth
praesum|to be over, rule, preside
nudus|naked, bare
edo#1|to eat
spina|thorn
cithara|harp, lyre
vespera|evening
pallium|cloak, mantle
oppidum|town
sinus#1|bosom, lap; bay
semel|once
spelunca|cave, den
octavus|eighth
somnus|sleep
voveo|to vow
Simeon|Simeon: son of Jacob and his tribe; Simeon who blessed the child Jesus; others
residuus|remaining, left over
benefacio|to do good, do well
jungo|to join, yoke, unite
Bethlehem|Bethlehem: the town in Judah, birthplace of David and of Jesus
tantus|so great, so much
frux|fruit, produce of the earth
triticum|wheat
adversus#1|adverse, opposite, contrary
meto#2|to reap, harvest
digitus|finger
fundo#2|to found, lay the foundation
palma#1|palm (of the hand); palm tree
habitaculum|dwelling place
centurio#2|centurion
exstinguo|to extinguish, quench; to destroy
aeneus|of bronze, brazen
recenseo|to number, count, review
funiculus|cord, line; measured portion
membrum|member, limb
immunditia|uncleanness, impurity
adventus|coming, arrival
zelus|zeal, jealousy
aereus#1|of bronze, brazen
contritio|destruction, ruin; contrition
Noe|Noah
terror|terror, fear
inebrio|to make drunk, inebriate; to fill
Syrus#2|Syrian; (plur.) the Syrians
faenum|hay, grass
audeo|to dare
luna|moon
dissolvo|to dissolve, loosen, destroy
verus|true
area|threshing floor; open space
Semei|Shimei: the Benjamite who cursed David; many others of the name
macula|spot, stain, blemish
rota|wheel
pugna|fight, battle
propono|to set before, propose; to set forth
succido#2|to cut down
justificatio|justification; (plur.) ordinances, statutes
Gabaa|Gibeah, Geba: towns of Benjamin
vivifico|to give life, quicken
regina|queen
transmigratio|deportation, exile; migration
Mardochaeus|Mordecai: cousin of Esther
Philippus|Philip: the apostle; the evangelist; Herod Philip; Philip of Macedon
carus|dear, beloved
evangelizo|to preach the gospel, bring good news
aspectus#2|sight, appearance, look
columba|dove
tergum|back
protego|to protect, cover
duplex|double, twofold
genu|knee
Zabulon|Zebulun: son of Jacob, and his tribe
varius|various, manifold
vetus|old, ancient
Madian|Midian: the land and people of Midian
aestimo|to value, reckon, think
interitus#2|destruction, ruin, death
littera|letter; (plur.) writings, a letter
hasta|spear
stultitia|folly, foolishness
Roboam|Rehoboam: son of Solomon, king of Judah
Asaph|Asaph: the psalmist and Levite singer; others of the name
praevaleo|to prevail
redeo|to return, go back
excipio|to receive, take up; to except
pellis|skin, hide
quantus|how great, how much
modus|measure, manner, way
lacrima|tear
draco|dragon, serpent
phiala|bowl, vial
calamus|reed; measuring reed; pen
praesidium|garrison, help, protection
hortus|garden
cedrus|cedar
existimo|to think, suppose, esteem
humus|ground, earth
Adam|Adam: the first man
ficus|fig tree; fig
emitto|to send out, put forth
octoginta|eighty
tectum|roof; house
Sodoma|Sodom
proficiscor|to set out, depart, journey
Sichem|Shechem: the city; also Shechem son of Hamor
figo|to fix, fasten, pitch (a tent)
prex|prayer, entreaty
parens#2|parent
Aser|Asher: son of Jacob, and his tribe
error|error, wandering
ploro|to weep, lament
vertex|top, crown (of the head)
lutum#2|mud, clay, mire
negotium|business, affair
sperno|to despise, reject
pupillus|orphan, fatherless child
usus#2|use; need
ferreus|of iron
consummatio|end, consummation, completion
inhabito|to dwell in, inhabit
perhibeo|to bear (witness), present
vacuus|empty, void
coquo|to cook, bake, boil
ambo|both
adjicio|to add, cast
cervix|neck
terribilis|terrible, dreadful
opprimo|to oppress, crush
lumbus|loin
desum|to be lacking, be wanting
cura|care, concern
amaritudo|bitterness
vicinus|neighbour; neighbouring
firmo|to strengthen, establish
amarus|bitter
tribunus|tribune, captain, commander
frango|to break
simulacrum|image, idol
artifex|craftsman, artificer
condemno|to condemn
ratio|account, reckoning; reason
Balaam|Balaam: the seer, son of Beor
calco|to tread, trample
robur|strength; oak
exsultatio|rejoicing, exultation
Nathan|Nathan: the prophet; a son of David; others
tristitia|sorrow, sadness
Nicanor|Nicanor: Syrian general (Maccabees); one of the seven deacons
Herodes|Herod: Herod the Great; Herod Antipas; Herod Agrippa
produco|to bring forth, lead out
concludo|to shut up, enclose
fumus|smoke
mos|custom, manner
fodio|to dig
Nephthali|Naphtali: son of Jacob, and his tribe
aliquando|at some time, once; at last
intueor|to look at, gaze upon
scrutor|to search, examine
Core|Korah: the Levite who rebelled against Moses; others of the name
hinc|hence, from here
saccus|sack; sackcloth
natus#2|birth; age
nutrio|to nourish, bring up
fornicor|to commit fornication
dispono|to arrange, set in order, dispose
Idumaea|Idumaea, Edom
praesto#2|to grant, give, provide; to excel
infirmo#1|to weaken
Timotheus|Timothy: Paul's companion; also Timotheus the Ammonite leader (Maccabees)
novem|nine
animal|animal, living creature
Hethaeus|Hittite
capra|she-goat
verso|to turn, turn over
consulo|to consult, ask counsel; to take care
metuo|to fear
ros|dew
accuso|to accuse
aroma|spice
clausus|shut, closed
fallo|to deceive
sententia|sentence, judgment; opinion
pinguis|fat, rich
conservo|to keep, preserve
canis|dog
Phase|Passover (the Pasch)
sitio|to thirst
concupiscentia|desire, lust, concupiscence
angustio|to distress, straiten
cantor|singer
diabolus|devil
illumino|to enlighten, illumine
insidior|to lie in wait, plot against
fenestra|window
Jebusaeus|Jebusite
irritus#1|void, vain, of no effect
obviam|to meet, in the way
Issachar|Issachar: son of Jacob, and his tribe
dono|to give, grant; to forgive
indigeo|to need, lack
libamen|drink offering, libation
Caath|Kohath: son of Levi
mendax|lying, false; liar
grando|hail
firmus|firm, strong
tentatio|temptation, trial
tego|to cover
amicitia|friendship
capillus|hair
Gedeon|Gideon: the judge
doleo|to grieve, feel pain
Caleb|Caleb: son of Jephunneh; others of the name
vindicta|vengeance, punishment
diripio|to plunder, despoil
Banaias|Benaiah: son of Jehoiada; others of the name
Urias|Uriah: the Hittite; Urijah the priest; others
janitor|porter, doorkeeper
firmamentum|firmament; support
pluvia|rain
incedo|to walk, advance
Assur|Asshur: Assyria; Asshur, son of Shem
Seir|Seir: the mountain land of Edom; Seir the Horite
Sara|Sarah: wife of Abraham; also Sara of Tobit
absum|to be absent, be away
seorsum|apart, aside, separately
refero|to bring back, report, relate
spondeo|to promise, pledge
parturio|to be in labour, travail
confestim|immediately
nequam|wicked, worthless
meretrix|harlot, prostitute
redigo|to bring back, reduce
contingo#1|to touch; to happen
proprius|one's own, proper
diluculum|daybreak, dawn
Amalec|Amalek: the Amalekites
byssus|fine linen
comminuo|to break in pieces, crush
janua|door
Galgala|Gilgal
signo|to seal, mark, sign
plenitudo|fulness
jejuno|to fast
Achaz|Ahaz: king of Judah
intendo|to attend, give heed; to bend (a bow)
dilectio|love
femina|woman, female
septingenti|seven hundred
oliva|olive, olive tree
caligo#1|darkness, mist
infans|infant, child
circumcisio|circumcision
aetas|age, lifetime
mentior|to lie, deceive
polliceor|to promise
sileo|to be silent
efficio|to make, effect, bring about
famulus#1|servant
ardeo|to burn, be on fire
appono|to set before, add, apply
bucina|trumpet, horn
unguentum|ointment, perfume
diligenter|diligently, carefully
exprobro|to reproach, upbraid
Hesebon|Heshbon: the Amorite city east of the Jordan
sublimis|high, lofty, exalted
necessitas|necessity, need, distress
Isai|Jesse: father of David
Joakim|Jehoiakim: king of Judah; Joakim the husband of Susanna; others
minus#2|less
volatilis|winged; (as noun) bird, fowl
male|badly, ill, wickedly
pronus|bending forward, prostrate
ortus#2|rising; east (ortus solis)
praeputium|foreskin; uncircumcision
noceo|to harm, hurt
haurio|to draw (water); to drink up
ritus|rite, custom, manner
anulus#1|ring
uva|grape, cluster of grapes
traho|to draw, drag
sanitas|health, soundness
sescenti|six hundred
exemplum|example, pattern; copy
speciosus|beautiful, fair
Ochozias|Ahaziah: king of Israel; king of Judah
turbo#2|whirlwind, storm
contumelia|insult, reproach, outrage
magistratus|magistrate, official
Aman|Haman: the enemy of the Jews in Esther
sextus|sixth
formo|to form, fashion
colloco|to place, set, settle
intrinsecus#1|within, inwardly
corrumpo|to corrupt, destroy, spoil
compono|to compose, put together, arrange
paululum|a little, a little while
paveo|to be afraid, tremble
vestigium|footstep, track
incircumcisus|uncircumcised
persevero|to persevere, continue
cottidie|daily
conscientia|conscience
coetus|assembly, gathering
expugno|to take by storm, conquer
aspergo#1|to sprinkle
concito|to stir up, rouse
Emath|Hamath: the city and kingdom in Syria
aequitas|equity, justice, uprightness
irrito#1|to provoke, anger
clipeus|shield
exclamo|to cry out, exclaim
injustus|unjust
utique#2|certainly, surely, at any rate
creatura|creature, creation
Satanas|Satan
adjutorium|help, aid
posterus|later, following; (plur.) posterity
grande|greatly; great
expleo|to fill up, fulfil, complete
illudo|to mock, deride
germen|bud, sprout, offspring
contrarius|contrary, opposite
consequor|to obtain, attain; to follow
committo|to commit, entrust; to join (battle)
Merari|Merari: son of Levi
induro|to harden
scandalum|stumbling block, offence, scandal
deicio|to cast down, throw down
concupisco|to desire, covet, lust after
misericors|merciful
catena|chain
tumultus|tumult, uproar
persona|person; face
contradico|to contradict, speak against
jejunium|fast, fasting
Gabaon|Gibeon
Geth|Gath: the Philistine city
deprecatio|prayer, supplication
Semeias|Shemaiah: the prophet; many others of the name
alligo|to bind
Persae|Persians; Persia
superexalto|to exalt above all, extol
scandalizo|to cause to stumble, scandalize
sal|salt
forsitan|perhaps
officium|duty, service, office
meditor|to meditate
abundantia|abundance
sanus|sound, healthy, whole
humilitas|humility, lowliness
albus|white
miseratio|mercy, compassion
crux|cross
pavor|fear, dread, trembling
locusta|locust
ruber|red
ren|kidney; (plur.) the reins, inmost heart
velociter|swiftly, quickly
vulgus|people, multitude, common people
fluctus|wave, billow
Sinai|Sinai: the mountain of the law
cognatus|kinsman, relative; related
turpitudo|shame, disgrace; nakedness
decerno|to decree, decide
Carmelus|Carmel: the mountain; also a town in Judah
gressus#2|step, going
utilis|useful, profitable
blasphemia|blasphemy, slander
nondum|not yet
vulnus|wound
deorsum|down, downward
dilato|to enlarge, widen, spread out
Sidon|Sidon: the Phoenician city; also Sidon son of Canaan
Lot|Lot: Abraham's nephew
asina|she-ass, donkey
Ismahel|Ishmael: son of Abraham and Hagar; others of the name
concubina|concubine
deinde|then, afterwards, next
diversus|various, different, diverse
occupo|to seize, occupy, possess
aedes|house, temple; (plur.) dwelling
interpretatio|interpretation
velox|swift
viscus#1|(plur.) bowels, entrails, inward parts
nimius|excessive, too great; (adv. nimium) exceedingly
cubile|bed, couch; lair
proelior|to fight, do battle
injuria|injury, wrong, injustice
fabricor|to make, build, forge
legitimus|lawful, legitimate; (neut. plur.) ordinances
effero#1|to bring out, carry out; to exalt
testificor|to testify, bear witness
fur|thief
extermino|to destroy, drive out
intereo|to perish
nobilis|noble, famous
communis|common
ululo|to howl, wail
concilium|council, assembly
latro#2|robber, thief
gloriosus|glorious
optimas|noble, chief; (plur.) nobles
Helcias|Hilkiah: the high priest under Josiah; others of the name
tempestas|tempest, storm; season
Alexander|Alexander: Alexander the Great; Alexander Balas; men of the name in the NT
enarro|to declare, tell, show forth
aridus|dry; (fem. as noun) dry land
masculinus|male, masculine
transgredior|to cross over; to transgress
utor|to use
perambulo|to walk through, go about
evado|to escape, get away
acquiesco|to agree, consent; to rest
fuga|flight
arena|sand
patria|homeland, country
immuto|to change, alter
Hiram|Hiram: king of Tyre; Hiram the craftsman
calceamentum|shoe, sandal
hordeum|barley
cultus#2|worship; cultivation; adornment
lapido|to stone
aquila|eagle
commendo|to commend, entrust
bis|twice
thymiama|incense
velum|veil, curtain; sail
cedrinus|of cedar
delecto|to delight, please
egenus|needy, poor
sollicitus|anxious, solicitous, careful
pascuus|of pasture; (neut. as noun) pasture
navigo|to sail
Johanan|Johanan: several men of the name (Jeremiah's time and others)
pascha|Passover, the Pasch; the paschal lamb
centesimus|hundredth
Esther|Esther: the Jewish queen of Persia
Machabaeus|Maccabeus: surname of Judas (and his brothers); (plur.) the Maccabees
Antiochia|Antioch
caelestis|heavenly, celestial
scilicet|namely, that is to say; certainly
retroversus|backwards, turned back
proverbium|proverb, byword
peregrinor|to sojourn, live as a stranger
pango|to make, fix; to make (a covenant)
festinus|hasty, in haste
orno|to adorn, furnish
supero|to overcome, surpass
consuetudo|custom, habit
cerno|to see, perceive, discern
advenio|to come, arrive
propitius|gracious, merciful, favourable
agnosco|to know, recognize, acknowledge
exquiro|to seek, search out, inquire
converso|to turn, turn round; (dep.) to live, dwell
fermentum|leaven, yeast
involvo|to wrap up, roll up
pugnator|fighter, warrior
exitus#2|going out, departure; outcome, end
aequus|equal, fair, just; level
majestas|majesty
delinquo|to sin, offend, do wrong
praevaricatio|transgression, prevarication
potentia|power, might
increpo|to rebuke, chide
satio#1|to satisfy, fill
Sehon|Sihon: king of the Amorites
commoror|to stay, dwell, abide
heu|alas!
ulciscor|to avenge, take vengeance
vicus|village; street
extentus#1|outstretched, extended
silva|forest, wood
imber|rain, shower
scutum|shield
percipio|to receive, obtain; to perceive
Heli|Eli: the priest at Shiloh; also Heli in Luke's genealogy
demolior|to demolish, destroy
arx|citadel, stronghold
undique|from all sides, on every side
instauro|to restore, renew, repair
Ionas|Jonah: the prophet; also Jonas, father of Simon Peter
Godolias|Gedaliah: governor of Judah after the fall; others of the name
secus#2|otherwise
continuo#1|immediately, forthwith
inutilis|useless, unprofitable
abundans|abundant, plentiful
congregatio|congregation, assembly
minuo|to diminish, lessen
haeres|heir
maritus#1|husband
heri|yesterday
vulva|womb
praedico#2|to foretell, say beforehand
Bersabee|Beersheba
jus#2|right, law, justice
femur|thigh
adjuro#1|to adjure, charge on oath
Laban|Laban: brother of Rebekah, father of Leah and Rachel
propinquus|near; (as noun) kinsman, relative
umerus|shoulder
contendo|to contend, strive, strain
supersum|to remain, survive
vires|strength, power
sollicitudo|anxiety, care, solicitude
reus|guilty; (as noun) the accused
erumpo|to break out, burst forth
regius|royal, kingly
permitto|to permit, allow
lectulus|bed, couch
deliciae|delights, pleasures
vinculo|to bind, chain
omnino|altogether, wholly, at all
murmuro|to murmur, grumble
incendo|to set on fire, burn
expio|to expiate, atone for, purify
Nun|Nun: father of Joshua
civis|citizen, fellow citizen
claudus|lame
viculus|small village, hamlet
prosterno|to prostrate, cast down, overthrow
pravus|wicked, crooked, perverse
fovea|pit, ditch
Abiathar|Abiathar: the priest in David's time
adimpleo|to fulfil, fill up
Sellum|Shallum: king of Israel; others of the name
exter|outer, outward; foreign
rapina#1|robbery, plunder
particeps|partaker, sharer
fatuus|foolish
exerceo|to exercise, practise
sterilis|barren
acies|edge (of the sword); battle line
videlicet|namely, that is to say
fornax|furnace, oven
haedus|kid, young goat
nuptiae|wedding, marriage
alioqui|otherwise, else
acervus|heap
taurus|bull
oblivio|forgetfulness, oblivion
stola|robe, long garment
plaustrum|wagon, cart
bello|to wage war, fight
nix|snow
sollemnis|solemn, festal
nequitia|wickedness
formido#1|to fear, dread
correptio|rebuke, reproof
stupeo|to be astonished, amazed
tabesco|to waste away, pine
Balac|Balak: king of Moab
absque#1|without, apart from
prae|before; in comparison; because
ob|because of, on account of; before
supra|above, upon, over
intra|within, inside
subter|under, beneath
prope|near, nigh
etiam|also, even
quoque#1|also, too
sive|or, or if; whether
verumtamen|but yet, nevertheless
velut|just as, like
en|behold!, lo!
siquidem|since indeed, for indeed
etsi|although, even if
palam|openly, publicly
clam|secretly
erga|towards
circum|around, round about
abs|from, away from
penes|in the power, in the keeping
quamquam|although
quamvis|although
quominus|that not
tametsi|although
infra|below, beneath
nempe|truly, certainly
quisnam|who? what? (emphatic)
quinam|who? which?
attamen|but yet, nevertheless
namque|for indeed
etiamsi|even if, although
# family heads (root lemmas) of the curated lemmas
rego|to rule, guide, direct
cedo#1|to go, move; to yield, give way
specio|to look, behold
jacio|to throw, cast
sacer|holy, sacred
linquo|to leave, forsake
ruo|to rush, fall, tumble down
quies#1|rest, quiet
sapio|to taste; to be wise, understand
pius|dutiful, devout, godly
tero|to rub, grind, wear away
cieo|to set in motion, stir, rouse
pleo|to fill
super#1|upper, higher
juvo|to help, aid; to delight
unda|wave, water
calx#1|heel
mas|male
sancio|to make sacred, ordain, ratify
arceo|to enclose, keep off
sero#1|to sow, plant
heres|heir
luceo|to shine, be light
prehendo|to seize, grasp
miser|wretched, miserable
dico#1|to proclaim, dedicate
fligo|to strike, dash
par|equal
precor|to pray, entreat
fido|to trust
oleo#1|to smell, emit a smell
pendo|to weigh; to pay
mora#1|delay
satis|enough
necesse|necessary, unavoidable
plico|to fold
fundus|bottom, foundation; estate
terreo|to frighten, terrify
cupio|to desire, long, wish
rumpo|to break, burst
volvo|to roll, turn
spiro|to breathe, blow
scando|to climb, mount
quatio|to shake, strike
taberna|hut, booth, shop
grego|to gather into a flock
fruor|to enjoy
intro#1|within, inside; inwards
pareo|to appear; to obey
furo|to rage, rave
possido|to take possession, seize
multiplex|manifold, many
fateor|to confess, acknowledge
ter|three times
labia|lip
solum#1|ground, soil, floor
voro|to devour, swallow
levis#1|light (in weight)
ignarus|ignorant, unaware
amplus|large, great, ample
struo|to build, pile up
anculus|servant
specto|to look at, behold
beo|to bless, make happy
latus#1|broad, wide
malus#3|mast, pole
rigo|to water, moisten
omen|omen, sign
paeniteo|to repent, regret
alo|to nourish, raise
solor|to console, comfort
cantus|song, singing
augeo|to increase
planta|plant, shoot; sole of the foot
epistula|letter, epistle
summa|sum, total; the chief point
tristis|sad, sorrowful
puellus|little boy
manifestus|manifest, clear, evident
sentio|to feel, perceive, think
nocens|harmful; guilty
illic#1|that (one) there
meta|turning post, boundary mark
haereo|to cling, stick, adhere
cingo|to gird, surround
vectigal|tax, revenue
temno|to despise, scorn
vigeo|to thrive, be vigorous
rubeo|to be red
vehemens|vehement, violent, strong
pando#2|to spread out, open
munio|to fortify, defend
peregre|abroad, in a foreign land
pario#3|to procure, obtain (in reperio)
candela|candle
umquam|ever
sculpo|to carve, engrave
stinguo|to quench
censeo#1|to assess, count; to think
funis|rope, cord
ebrio|to make drunk
migro|to migrate, depart
columbus|dove, pigeon
luo#2|to loose; to pay, atone
pupus|boy, child
vaco|to be empty, be free
premo|to press
damnum|loss, harm; penalty
ratus|reckoned, fixed, valid
tueor|to look at; to protect
caper|he-goat
metus|fear
cuso|to strike (in accuso)
sitis|thirst
angustus|narrow, strait
libo|to pour out (an offering)
vindico|to avenge; to claim
pluo|to rain
seorsus|apart, separately
for|to speak
probrum|disgrace, shameful act
imo|lowest (in eximo, take out)
forma|form, shape, beauty
paulus|little, small
spargo#1|to scatter, sprinkle
uti#1|that, so that; as
ludo|to play; to mock
turpis|base, shameful, ugly
concubinus|concubine
cubo|to lie down
faber#1|workman, smith, craftsman
munis|obliging, serviceable
areo|to be dry
harena|sand
licium|thread
egeo|to need, lack
consuesco|to become accustomed
crepo|to rattle, crack
moles|mass, bulk
continuus|continuous, unbroken
vis|force, strength, violence
sterno|to spread, lay low
nupta|bride, wife
tabes|wasting, decay
# lemmas made frequent by the 19 Nov tagging fixes, and the remaining empty or garbled glosses
occido#1|to kill, slay
occido#2|to fall, go down; (of the sun) to set
poena|punishment, penalty
cohors|cohort, band of soldiers; enclosure
intellego|to understand, perceive
intellegentia|understanding, intelligence
fors|chance; (forte) perhaps, by chance
plaga#1|blow, stroke, wound; plague
plaga#2|region, quarter, side
plaga#3|net, snare
rursus|again, back
orior|to rise, arise, spring up
exorior|to rise, spring up, arise
extra|outside, without; beyond
vinculum|bond, chain, fetter
hujuscemodi|of this kind, such
huiusmodi|of this kind, such
juxta|near, beside; according to
Jacobus|James: James son of Zebedee; James son of Alphaeus; James the brother of the Lord
liberi|children
quispiam|anyone, anything, someone
necnon|and also, and moreover
usquequo|how long?, until when
deinceps|thereafter, from now on, successively
sponte|of one's own accord, freely
quattuordecim|fourteen
deterior|worse
senesco|to grow old
sexus|sex, kind (male or female)
asto|to stand by, stand near
frenum|bridle, bit
commentarius|record, chronicle, book of records
aestimatio|valuation, estimation
butyrum|butter
decurro|to run down, flow down; to run one's course
exinde|thence; thereafter, from then on
hortor|to exhort, encourage, urge
pardus|leopard
possessor|possessor, owner
salsus|salt, salty
deforis|from outside, without
mediator|mediator
pugillum|handful
abbrevio|to shorten, cut short
commemoro|to remember, call to mind; to mention
fabrefactus|skilfully made, wrought
magus#1|magus, wise man; magician
serus|late
apis|bee
coitus#1|united, joined
formosus|beautiful, fair
fornicator|fornicator
praesepis|manger, crib, stall
sero#4|late
bitumen|bitumen, pitch
conclave|room, chamber
coturnix|quail
creditor|creditor, lender
mula|she-mule
parvipendo|to make little of, despise
superius|above, higher up; before
urceus|pitcher, jug
dea|goddess
pie|devoutly, dutifully
radicatus|rooted
vespertilio|bat
armatus#1|armed
assentior|to agree, assent
assuetus|accustomed
concors|of one mind, harmonious
contego|to cover, cover over
culmen|top, summit, roof
diaconus|deacon
edulium|food, victuals
femininus|female, feminine
frustror|to frustrate, disappoint
frutetum|thicket
inquilinus#2|sojourner, tenant
lamento|to lament, mourn
lapicidinae|stone quarries
lens#2|lentil
propius|nearer
simia|ape
smaragdinus|of emerald
sospes|safe, unharmed
talpa|mole
velato|veiled, covered
abhorresco|to shrink back from, abhor
arceuthinus|of juniper
arctus#1|narrow, close, strait
canitia|grey hair, old age
caupo|innkeeper
condelector|to delight in
convenientia|agreement, harmony
deintus|from within
dithalassus|between two seas (where two seas meet)
gratificor|to gratify, do a favour
hereditarie|by inheritance
jusjurandum|oath
naphtha|naphtha
neptis|granddaughter; niece
panifica|baker (woman)
progressus#1|advanced
quingenteni|five hundred each
runcina|plane (carpenter's tool)
stragulatus|covered with a rug
vermiculatus|inlaid, chequered
vilico#1|to be a steward
Cyrenensis|of Cyrene, Cyrenian
Thessalonicensis|Thessalonian
botrys|cluster of grapes
Hyacinthus|hyacinth, blue-purple dye or cloth; jacinth (gem)
sartatecta|repairs of a building, roof and walls
crucifigo|to crucify, nail to a cross
"""

_SAINTS_GLOSS: Dict[str, str] = {}
for _line in _SAINTS_GLOSS_TEXT.splitlines():
    if "|" in _line and not _line.lstrip().startswith("#"):
        _k, _g = _line.split("|", 1)
        _SAINTS_GLOSS["lat:" + _k.strip()] = _g.strip()

# Parts of speech that the L&S head misleads (princeps 'adj. and subst.' is the noun 'prince' in the Bible; plus
# is read from 'plūs, plūris' as a noun; prior from its etymology as a preposition)
_POS_OVERRIDE: Dict[str, str] = {
    "lat:princeps": "N", "lat:plus": "ADJ", "lat:prior": "ADJ", "lat:alioqui": "ADV",
}


def _apply_saints_glosses(idx: _Index) -> None:
    for key, g in _SAINTS_GLOSS.items():
        i = idx.by_key.get(key)
        if i is not None:
            idx.lemmas[i].gloss = g
    for key, pos in _POS_OVERRIDE.items():
        i = idx.by_key.get(key)
        if i is not None:
            idx.lemmas[i].pos = pos
            idx.lemmas[i].noncontent = pos in _NONCONTENT_POS


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

_TIPNR_PEOPLE: List[list] = []


def _load_raw() -> Tuple[List[dict], List[Tuple[str, str]]]:
    """Parsed L&S entries and TIPNR names (cached in data/); the TIPNR individuals with their verses are kept
    in ``_TIPNR_PEOPLE`` (same cache)."""
    global _TIPNR_PEOPLE
    path = ls_path()
    if not path.exists():
        raise FileNotFoundError(f"Lewis & Short XML not found: {path}")
    tp = tipnr_path()
    sig = {"version": INDEX_VERSION, "ls": _ls_signature(path), "tipnr": _ls_signature(tp) if tp else None}
    cp = cache_path()
    if cp.exists():
        try:
            with gzip.open(cp, "rt", encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("sig") == sig:
                _TIPNR_PEOPLE = data.get("tipnr_people") or []
                return data["entries"], [tuple(x) for x in data["tipnr"]]
        except (OSError, ValueError, KeyError):
            pass
    entries = _parse_ls(path)
    tipnr = _load_tipnr(tp)
    _TIPNR_PEOPLE = _load_tipnr_people(tp)
    try:
        cp.parent.mkdir(parents=True, exist_ok=True)
        tmp = cp.with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as fh:
            json.dump({"sig": sig, "source": LS_SOURCE, "entries": entries, "tipnr": tipnr,
                       "tipnr_people": _TIPNR_PEOPLE}, fh, ensure_ascii=False)
        os.replace(tmp, cp)
    except OSError:
        pass
    return entries, tipnr


_LEXICON: Optional[Dict[str, LemmaEntry]] = None
_TAGGER: Optional[_Tagger] = None
_ROOTS: Optional[Dict[int, Tuple[int, str]]] = None
_PRIORS_READY = False


def _get_index() -> _Index:
    global _INDEX
    if _INDEX is None:
        entries, tipnr = _load_raw()
        _INDEX = _build_index(entries, tipnr)
        _INDEX.tipnr = _TipnrIndex(_TIPNR_PEOPLE)
    return _INDEX


def _get_tagger() -> _Tagger:
    global _TAGGER
    if _TAGGER is None:
        _TAGGER = _Tagger(_get_index())
    _ensure_priors()
    return _TAGGER


def reset_cache() -> None:
    """Forget every in-memory structure (the on-disk cache is kept)."""
    global _INDEX, _LEXICON, _TAGGER, _ROOTS, _PRIORS_READY
    _INDEX = None
    _LEXICON = None
    _TAGGER = None
    _ROOTS = None
    _PRIORS_READY = False


def _ensure_priors(conn: Optional[sqlite3.Connection] = None) -> None:
    """Lemma priors from the Studio's own Latin text: tokens whose analysis has one lemma only."""
    global _PRIORS_READY
    if _PRIORS_READY:
        return
    _PRIORS_READY = True
    idx = _get_index()
    tagger = _TAGGER or _Tagger(idx)
    own = conn is None
    if conn is None:
        conn = _connect_ro(db_path())
    counts: Counter = Counter()
    lower: Counter = Counter()
    if conn is not None:
        try:
            verses = []
            surf: Dict[str, Counter] = defaultdict(Counter)
            for _book, _ch, _v, text in _studio_latin_rows(conn):
                toks = tokenize_verse(text, LANG)
                flags = _sentence_initial_flags(text, toks)
                verses.append((toks, flags, (_book, _ch, _v)))
                for tok, ini in zip(toks, flags):
                    b = _b(tok)
                    if tok[:1].isupper():
                        idx.cap_any[b] += 1
                        surf[b][tok] += 1
                        if not ini:
                            idx.cap_mid[b] += 1
                    else:
                        idx.cap_lower[b] += 1
            idx.cap_surface = {b: c.most_common(1)[0][0] for b, c in surf.items()}
            for toks, flags, ref in verses:
                for tok, ini in zip(toks, flags):
                    cands, _pre, _n = tagger.analyse_token(tok, ini)
                    group = _choose_group(idx, cands, _b(tok), tok, ini)
                    if not group and tok[:1].isupper():
                        j = _tipnr_name_here(idx, tok, ini, ref)
                        if j is not None:
                            group = {j: [("textname", "")]}
                    for i in group:
                        if idx.lemmas[i].proper:
                            idx.name_occ[i].append(ref)
                    if len(group) == 1:
                        i, anas = next(iter(group.items()))
                        counts[i] += 1
                        if not tok[:1].isupper():
                            lower[i] += 1
                        if any(pc == "closed" for pc, _e in anas):
                            idx.closed_form[(i, _b(tok))] += 1
                        # slot statistics from unambiguous tokens (each analysis gets an equal share)
                        w = 1.0 / len(anas)
                        for pc, end in anas:
                            sk = _slot_key(idx, i, pc, end)
                            if sk:
                                idx.slot[sk] += w
                                idx.fam_total[sk[0]] += w
        except sqlite3.Error:
            pass
        finally:
            if own:
                conn.close()
    idx.prior = dict(counts)
    idx.prior_lower = dict(lower)
    tagger.cache.clear()
    _apply_name_glosses(idx)
    _apply_saints_glosses(idx)
    fam_slots: Counter = Counter()
    for (fam, _pc, _end) in idx.slot:
        fam_slots[fam] += 1
    idx.fam_slots = fam_slots


_PLURAL_ENDINGS = {"N1": {"arum", "is", "as", "abus"}, "N2": {"orum", "is", "os"}, "N2N": {"a", "orum", "is"},
                   "N3": {"es", "um", "ium", "ibus"}, "N3N": {"a", "ia", "um", "ium", "ibus"},
                   "N4": {"uum", "ibus", "ubus", "ua"}, "N5": {"erum", "ebus"}}

_SLOT_GROUP = {"N1GA": "N1", "N1GE": "N1", "N1PL": "N1", "N2IUS": "N2", "N2R": "N2", "N2PLM": "N2",
               "N2PLN": "N2N", "N3I": "N3", "N3IM": "N3", "N3PL": "N3", "N3NI": "N3N", "N3PLN": "N3N",
               "A12R": "A12", "A12PL": "A12", "A31I": "A3", "A31C": "A3"}


def _slot_key(idx: _Index, i: int, pc: str, end: str) -> Optional[Tuple[str, str, str]]:
    """(family, slot group, ending) of a paradigm analysis (nominal codes of one declension share their
    slots; verb codes keep their own); nominatives listed as exact forms get (family, 'NOM', '')."""
    if (pc == "N1GA" and end == "as") or (pc == "N1GE" and end in ("es", "e")):
        return ("N1", "N1", "a")          # Greek nominative (Elias, Isaias): the 1st-decl. nominative slot,
                                          # not the acc. plural in -as
    if pc in ENDINGS:
        return (_FAMILY.get(pc, "V"), _SLOT_GROUP.get(pc, pc), end)
    if pc == "x" and i in idx.lemma_fam:
        return (idx.lemma_fam[i], "NOM", "")
    return None


def _likelihood(idx: _Index, i: int, anas: List[Tuple[str, str]], b: str) -> float:
    """P(form | lemma) up to a constant: paradigm slots from corpus statistics; closed-list forms from the
    lemma's own unambiguous tokens (add-one); indeclinables, names and cross-reference spellings 1."""
    total = 0.0
    proper = idx.lemmas[i].proper
    for pc, end in anas:
        sk = _slot_key(idx, i, pc, end)
        if sk:
            fam = sk[0]
            n = idx.fam_slots.get(fam, 0) or 50
            p = (idx.slot.get(sk, 0.0) + 0.5) / (idx.fam_total.get(fam, 0.0) + 0.5 * n)
            if proper and sk[2] == end and end in _PLURAL_ENDINGS.get(fam, ()) and i not in idx.plural_only:
                p *= 0.05          # a personal or place name is (almost) never plural: 'Bacchides', 'Judaeis'
            total += p
        elif pc == "closed":
            nf = max(1, idx.closed_n.get(i, 1))
            # uniform over the list, or the form's own unambiguous share if that is larger
            total += max(1.0 / nf, (idx.closed_form.get((i, b), 0) + 1.0) / (idx.prior.get(i, 0) + nf))
        else:
            total += 1.0
    return total


def _base_prior(idx: _Index, i: int) -> float:
    lem = idx.lemmas[i]
    weight = {"hapax": 0.3, "gloss": 0.2, "foreign": 0.3}.get(lem.ls_type, 1.0)
    size = min(_LS_SIZE_CAP, lem.size * _LS_SIZE_WEIGHT) * weight
    if lem.ls_type == "tipnr":
        size = 2.0          # a biblical name (TIPNR) outweighs an obscure classical L&S name ('Levi' / 'Laevi')
    manual = _LEMMA_PRIOR.get(lem.key, 0.0)
    return idx.prior.get(i, 0.0) + size + manual + 0.05


def _choose_group(idx: _Index, cands: Dict[int, str], b: str, tok: str, initial: bool) -> Dict[int, str]:
    """For a capitalised token decide between proper-name and common-word readings."""
    if not cands or not tok[:1].isupper():
        return cands
    proper = {i: pc for i, pc in cands.items() if idx.lemmas[i].proper}
    common = {i: pc for i, pc in cands.items() if not idx.lemmas[i].proper}
    if not proper or not common:
        return cands
    # L&S personifications of a frequent common word of the same spelling ('Princeps' / princeps,
    # 'Pax' / pax) give way to it; unrelated homographs ('Asia' / asia 'rye') do not
    real = {}
    for i, a in proper.items():
        twin = [j for j in common if idx.lemmas[j].hb == idx.lemmas[i].hb]
        if twin and max(_base_prior(idx, j) for j in twin) >= 10 * _base_prior(idx, i):
            continue
        real[i] = a
    if not real:
        return common
    if all(idx.lemmas[i].noncontent for i in common):
        # a function word is never capitalised mid-sentence ('desertum Sin'); at the start of a sentence
        # the function word is the usual reading ('Sin autem')
        return common if initial else real
    lower = idx.cap_lower.get(b, 0)
    if initial and lower == 0:
        return real                     # never written in lower case in the Studio text
    if lower == 0:
        # mid-sentence and never in lower case: a common reading reached only through an L&S cross-reference
        # to an archaic spelling ('amos, v. amor') or only as a finite verb form ('in Perside': persido)
        # does not compete with the name ('Amos' the prophet's father; Persis)
        kept = {i: a for i, a in common.items()
                if not all(pc == "alias" for pc, _e in a) and
                not (idx.lemmas[i].pos == "V" and all(pc.startswith("V") and pc not in ("V1N", "V2N", "V3IN",
                                                                                         "VPP", "VFP")
                                                      for pc, _e in a))}
        if not kept:
            return real
        common = kept
    # otherwise both readings compete in _decide, the name boosted: 'Maria' (Mary, not the seas) but
    # 'Patris' (the Father, not the town Patrae)
    merged = dict(common)
    merged.update(real)
    return merged


_PROPER_BOOST = 20.0           # capitalised mid-sentence
_PROPER_BOOST_INITIAL = 3.0    # capitalised at the start of a sentence

# ---- names attested in the Studio text itself -------------------------------------------------
# Hebrew and Greek names missing from L&S and TIPNR (Jonathas, Ezechias, Philisthiim ...).  Applied only
# to a capitalised token that has no analysis at all and is never written in lower case in the Studio
# text.  (a) A form whose ending cannot be a Latin oblique case (David, Galaad, Isai, Esau, Ezechias,
# Jerusalem when no sibling form is attested) is its own lemma.  (b) An oblique form (Ezechiae, Moysen,
# Petri) gets the lemma of its nominative only when exactly one candidate nominative is attested.
NAME_INFERENCE = True
NAMES_TEXT_SOURCE = "Saints Latin text (attested capitalised name forms)"
_OBLIQUE = [("orum", ("us", "i")), ("arum", ("a", "ae")), ("ibus", ("es", "")), ("ae", ("as", "a", "es")),
            ("am", ("as", "a", "es")), ("an", ("as",)), ("em", ("es", "")), ("en", ("es", "e")), ("um", ("us",)),
            ("im", ("is",)), ("os", ("us", "i")), ("is", ("", "a", "us", "es", "i")),
            ("i", ("ius", "us", "es", "is", "")),
            ("o", ("us", "")), ("e", ("es", "us", "")), ("a", ("as",)), ("u", ("us",))]


def _cap_attested(idx: _Index, b: str) -> bool:
    return idx.cap_any.get(b, 0) > 0 and idx.cap_lower.get(b, 0) == 0


def _nominatives(idx: _Index, b: str) -> List[str]:
    """Attested capitalised forms of which ``b`` can be an oblique case (by Latin case endings)."""
    out = []
    for end, reps in _OBLIQUE:
        if b.endswith(end) and len(b) > len(end) + 1:
            base = b[: -len(end)]
            for r in reps:
                n = base + r
                if n != b and len(n) >= 3 and _cap_attested(idx, n) and n not in out:
                    out.append(n)
    # Jonathas beats Jonatha (abl./voc.), Judaeus beats Judaei (nom. pl.)
    out = [n for n in out if not (n + "s" in out or (n.endswith("i") and n[:-1] + "us" in out))]
    # the patriarch Jacob is indeclinable in the Vulgate: Jacobi / Jacobo / Jacobum (all in the NT) are of
    # Jacobus, James (other pairs such as Saul / Saulus, Eleazar / Eleazarus are declined both ways)
    if "iacob" in out and "iacobus" in out:
        out.remove("iacob")
    return out


# Latin case endings of the declinable name types: nominative ending -> oblique endings
_NAME_DECL = {"as": ("am", "an", "ae", "a"), "us": ("i", "o", "um", "e"), "es": ("em", "en", "e", "is", "i"),
              "a": ("ae", "am"), "is": ("im", "in", "i", "e", "em")}


def _latin_oblique_of_attested(idx: _Index, b: str) -> bool:
    """Is ``b`` (a form TIPNR also lists as a name of its own) really a Latin case of a declinable name
    attested more often in the text ('Eliam' = acc. of Elias, 'Jonam' of Jonas, 'Tyre' voc. of Tyrus)?
    Hebrew names in -i/-ai/-am/-o of their own (Joram, Hiram, Heli, Neri, Amasai, Ahio, Amos) are not
    oblique cases of a rarer look-alike (Jora, Hiras, Heles, Ner, Amasa, Ahi, Ami)."""
    n_form = idx.cap_any.get(b, 0)
    for nom in _nominatives(idx, b):
        for nend, obl in _NAME_DECL.items():
            if nom.endswith(nend) and b[:len(nom) - len(nend)] == nom[:len(nom) - len(nend)] and \
                    b[len(nom) - len(nend):] in obl and idx.cap_any.get(nom, 0) > n_form:
                return True
    return False


def _lemma_shaped(idx: _Index, b: str, allow_e: bool = True) -> bool:
    """Can ``b`` be a nominative / indeclinable name?"""
    if b.endswith(("ibus", "ubus", "orum", "arum")):
        return False                                     # always oblique (names in -imus like Alcimus stay)
    if re.search(r"[bcdghklprtz]$|(ai|oi|au|eu|iu)$", b):
        return True
    if re.search(r"(as|es|us)$", b) and not b.endswith(("ios", "eos", "aeos")):
        return True
    if b.endswith(("m", "n", "a", "u")):
        return not _nominatives(idx, b)
    if allow_e and b.endswith("e") and not b.endswith(("ae", "que", "de")) and idx.cap_mid.get(b, 0) > 0:
        # Hebrew names in -e (Josue, Jesse, Bersabee, Ninive, Bete), capitalised mid-sentence somewhere and
        # not the ablative/vocative of an attested name (Moyse -> Moyses); '-ide/-ade' forms are Latin
        # ablatives of names in -is/-as (Moabitide, Ptolemaide) and are left alone
        return not _nominatives(idx, b)
    return False


def _name_lemma(idx: _Index, nom: str) -> int:
    # an L&S or TIPNR name with that spelling, directly or through an L&S cross-reference
    # ('Moyses, v. Moses')
    known = []
    for k, pc, _e in idx.analyse(nom):
        if pc not in ("x", "alias", "tipnr"):
            continue                      # only a headword spelling, not a case form ('Bacchides' of Bacchis)
        k = idx.canon.get(k, k)
        if idx.lemmas[k].proper and idx.lemmas[k].pos == "PROPN" and k not in known:
            known.append(k)
    if len(known) == 1:
        return known[0]
    for k in idx.headwords.get(nom, ()):
        if idx.lemmas[k].proper and idx.lemmas[k].pos == "PROPN":
            return idx.canon.get(k, k)
    disp = (_plain(idx.cap_surface[nom]) if nom in idx.cap_surface else "") or nom.capitalize()
    key = "lat:" + disp
    if key in idx.by_key:
        return idx.by_key[key]
    i = idx.add_lemma(_Lemma(key, disp, "PROPN", "proper name", 0, "textname", True, NAMES_TEXT_SOURCE, nom))
    idx.headwords[nom].append(i)
    if _LEXICON is not None:
        _LEXICON[key] = _lemma_entry(idx, i, _roots())
    return i


def _names_from_text(idx: _Index, b: str, allow_e: bool = True) -> List[int]:
    """Name lemmas a capitalised form can belong to, from the forms attested in the Studio text.
    ``allow_e``: Hebrew names in -e count as nominatives (not when such a name would only compete with an
    existing analysis: 'in Perside' is Persis)."""
    if not NAME_INFERENCE or not _cap_attested(idx, b):
        return []
    if b.endswith("ensium") and len(b) > 8:
        # gen. plur. of a gentile adjective in -ensis (Cyrenensium, Thessalonicensium, Laodicensium): its
        # nominative is the headword, not the inflected form (19 Nov 2026)
        return [_name_lemma(idx, b[:-3] + "is")]
    if b.endswith(("inorum", "enorum")) and len(b) > 8:
        # gen. plur. of a Vulgate gentile name in -inus / -enus (Philisthinorum -> Philisthinus,
        # Palaestinorum -> Palaestinus, Gerasenorum -> Gerasenus)
        return [_name_lemma(idx, b[:-4] + "us")]
    if b.endswith("itarum") and len(b) > 8:
        # gen. plur. of a gentile name in -ita / -ites (Moabitarum -> Moabites/Moabita,
        # Gersonitarum -> Gersonita, Rechabitarum -> Rechabita)
        cand_es = b[:-4] + "es"
        if _cap_attested(idx, cand_es) or any(idx.lemmas[k].proper for k in idx.headwords.get(cand_es, ())):
            return [_name_lemma(idx, cand_es)]
        return [_name_lemma(idx, b[:-4] + "a")]
    if b.endswith("poleos") and len(b) > 7:
        # Greek genitive of -polis place names (Heliopoleos -> Heliopolis, Decapoleos -> Decapolis)
        return [_name_lemma(idx, b[:-3] + "is")]
    if b.endswith("eos") and len(b) > 5:
        # Greek genitive of -is place names (Taneos -> Tanis, Mempheos -> Memphis)
        return [_name_lemma(idx, b[:-3] + "is")]
    if b.endswith("iadis") and len(b) > 7:
        # Greek genitive of -ias names (Tiberiadis -> Tiberias, Herodiadis -> Herodias)
        return [_name_lemma(idx, b[:-3] + "s")]
    if b.endswith(("itide", "itidis", "itim")) and len(b) > 7:
        # feminine gentilic / regional name in -itis (Moabitide -> Moabitis, Galaaditim/itide/itidis -> Galaaditis)
        stem = re.sub(r"(?:itide|itidis|itim)$", "itis", b)
        return [_name_lemma(idx, stem)]
    if b.endswith("itis") and len(b) > 6 and idx.cap_mid.get(b, 0) > 0:
        # feminine gentilic nominative in -itis (Madianitis, Isaaritis, Hebronitis, Gaditis)
        return [_name_lemma(idx, b)]
    if b.endswith(("itae", "itas")) and len(b) > 6 and idx.cap_mid.get(b, 0) > 0:
        # plural gentilic in -itae / -itas (Bethsamitae -> Bethsamites, Ninivitae -> Ninivites, Coritae -> Corites)
        cand_es = b[:-2] + "es"
        if _cap_attested(idx, cand_es) or any(idx.lemmas[k].proper for k in idx.headwords.get(cand_es, ())):
            return [_name_lemma(idx, cand_es)]
        return [_name_lemma(idx, b[:-2] + "a")]
    if b.endswith(("aei", "aeis", "aeos", "aeorum")) and len(b) > 6 and idx.cap_mid.get(b, 0) > 0:
        # plural/oblique biblical gentilic in -aeus (Nathinaei/is/os -> Nathinaeus, Ziphaei -> Ziphaeus,
        # Horraei/Horraeorum -> Horraeus, Assidaei -> Assidaeus)
        suf = "aeorum" if b.endswith("aeorum") else ("aeis" if b.endswith("aeis") else ("aeos" if b.endswith("aeos") else "aei"))
        if not b.endswith(("ebedaei", "alphaei")):       # personal names Zebedaeus / Alphaeus handled via TIPNR below
            return [_name_lemma(idx, b[:-len(suf)] + "aeus")]
    noms = _nominatives(idx, b)
    if _lemma_shaped(idx, b, allow_e) and not noms:
        return [_name_lemma(idx, b)]
    return [_name_lemma(idx, n) for n in noms if _lemma_shaped(idx, n, allow_e)]


def _name_from_text(idx: _Index, b: str) -> Optional[int]:
    found = _names_from_text(idx, b)
    return found[0] if len(found) == 1 else None


_HEBREW_SCRIPT = re.compile(r"[֐-׿]")
# Latin oblique endings: a form ending so is not made a headword of its own ('Philisthinorum', 'Romeliae')
_OBLIQUE_TAILS = ("ae", "orum", "arum", "ibus", "um", "am", "em")


def _tipnr_name_here(idx: _Index, tok: str, initial: bool, ref: Optional[Tuple[str, int, int]]) -> Optional[int]:
    """A capitalised form with no analysis at all, never written in lower case, is a name of its own when a TIPNR
    individual with the same consonant skeleton stands in this very verse (Nephthali = Naphtali at Gen 30:8,
    Amri = Omri, Lachis = Lachish, Noemi = Naomi, Chamos = Chemosh, Siloe = Siloam, Nabo = Nebo).  Oblique-only
    biblical names ('Romeliae', 'Zebedaei', 'Selemiae', 'Alphaei', 'Laodiciae', 'Ceturae', 'Stephanae') are mapped
    to their Latin nominative headword ('Romelias', 'Zebedaeus', ...) rather than making an inflected headword."""
    if not ref or idx.tipnr is None or not NAME_INFERENCE:
        return None
    b = _b(tok)
    if len(b) < 3 or b.endswith("que"):
        return None
    # Mid-sentence capitalised biblical place name (e.g. 'de Setim' = Shittim in Josh 2:1) may match TIPNR even if
    # a homographic loanword ('ligna setim') appears in lower case; lowercase tokens never call this function.
    if not _cap_attested(idx, b) and (initial or idx.cap_mid.get(b, 0) == 0):
        return None
    sks = {k for k in _name_keys(tok) if k.split(":")[1]}
    if not sks:
        return None
    # Oblique-only biblical personal/place names whose nominative is unattested in the Vulgate:
    # map -ae / -aei / -aeo to their proper Latin nominative when a TIPNR bearer stands in this very verse.
    if b.endswith(("ae", "aei", "aeo")) and len(b) >= 6:
        hits = idx.tipnr.at(ref[0], int(ref[1]), int(ref[2]), sks)
        if hits:
            rec = idx.tipnr.people[hits[0]]
            kind = rec[5] if len(rec) > 5 else "person"
            eng = idx.tipnr.english(hits[0], sks)
            if b.endswith(("aei", "aeo")):
                nom = b[:-1] + "us"                  # Zebedaei/o -> Zebedaeus, Alphaei -> Alphaeus
            else:
                # -ae: Greek/Hebrew male names take -as (Romelias, Selemias, Stephanas); places/women take -a
                desc_low = ((rec[1] or "") + " " + (rec[2] or "") + " " + (rec[6] if len(rec) > 6 else "")).lower()
                is_fem_or_place = (kind == "place" or eng.endswith(("a", "ah")) and any(w in desc_low for w in
                                   ("wife", "mother", "woman", "daughter", "concubine", "sister", "city", "town",
                                    "place", "region")))
                nom = b[:-1] if (is_fem_or_place or eng.endswith("ea")) else (b[:-1] + "s")
            if nom and nom != b:
                j = _name_lemma(idx, nom)
                if (j, "textname") not in idx.exact.get(b, ()):
                    idx.exact[b].append((j, "textname"))
                    idx.ana_cache.pop(b, None)
                if idx.lemmas[j].ls_type == "textname" and idx.lemmas[j].gloss == "proper name":
                    g = _name_gloss(idx, sks, Counter({k: 1 for k in hits}), 1)
                    if g:
                        idx.lemmas[j].gloss = g
                        if _LEXICON is not None:
                            _LEXICON[idx.lemmas[j].key] = _lemma_entry(idx, j, _roots())
                return j
        return None
    if b.endswith(_OBLIQUE_TAILS) or b.endswith(("aei", "aeo", "aeis", "ici", "itis", "itae", "itas")):
        return None                                  # inflected forms are never made headwords of their own
    if "ë" not in tok:
        for suf in ("is", "a", "e", "o"):            # Rahelis -> Rahel (not Noemi -> Noe, Siloë -> Silo!)
            cut = len(suf)
            if b.endswith(suf) and len(b) > cut + 2 and (_cap_attested(idx, b[:-cut]) or
                                                         any(idx.lemmas[k].proper for k in idx.headwords.get(b[:-cut], ()))):
                return None
    hits = idx.tipnr.at(ref[0], int(ref[1]), int(ref[2]), sks)
    # only a name with a Hebrew (OT) form: the Vulgate leaves Hebrew names undeclined (Nephthali, Mageddo,
    # Noemi, Zambri, Musi, Chamos, Ceros, Bercos, Nabo, Siloe), but declines Greek ones
    tnorm = _name_skeleton(tok).split(":")[-1]
    exact_orig = [k for k in hits if any(orig and _name_skeleton(orig).split(":")[-1] == tnorm
                                         for _e, orig in idx.tipnr.people[k][3])]
    if "ë" not in tok and _nominatives(idx, b) and not exact_orig:
        return None                                  # Corneli, Archippo: a case of an attested Cornelius, Archippus
    hits = [k for k in hits if any(_HEBREW_SCRIPT.search(orig or "") or
                                   (orig and _name_skeleton(orig).split(":")[-1] == tnorm)   # Achim = Ἀχίμ
                                   for _e, orig in idx.tipnr.people[k][3])]
    if not hits:                                     # must match a TIPNR Hebrew/exact bearer in this verse
        return None
    known = ("lat:" + (_plain(idx.cap_surface.get(b, b)) or b)) in idx.by_key
    j = _name_lemma(idx, b)
    if (j, "textname") not in idx.exact.get(b, ()):
        idx.exact[b].append((j, "textname"))
        idx.ana_cache.pop(b, None)
    if idx.lemmas[j].ls_type == "textname" and not known and idx.lemmas[j].gloss == "proper name":
        g = _name_gloss(idx, sks, Counter({k: 1 for k in hits}), 1)
        if g:
            idx.lemmas[j].gloss = g
            if _LEXICON is not None:
                _LEXICON[idx.lemmas[j].key] = _lemma_entry(idx, j, _roots())
    return j


# Lewis & Short name descriptions kept when no TIPNR individual matches: only those that describe a biblical
# bearer (the rest describe classical people and places: 'Nicanor: A grammarian', 'Anas: a river in Spain')
_BIBLICAL_MARKERS = re.compile(r"\b(?:Jews?|Jewish|Hebrews?|Israel\w*|Vulg|Bible|biblical|patriarch|prophet\w*|"
                               r"apostle|Christ|Judaea|Jud[aæ]a|Jerusalem|Maccab\w*)\b", re.I)


def _name_gloss(idx: _Index, sks: Set[str], hits: Counter, n_in: int) -> str:
    """'English: brief description' for one TIPNR bearer, 'English: several bearers (...)' for more."""
    tp = idx.tipnr
    ranked = hits.most_common()
    top = ranked[0][1] if ranked else 0
    # a bearer must stand in two of the lemma's verses and in at least 2 % as many as the main bearer (a name in
    # a neighbouring verse is noise); a name with three verses or fewer keeps every bearer found
    keep = [k for k, n in ranked if (n >= 2 and n >= 0.02 * top) or n_in <= 3]
    if not keep or tp is None:
        return ""
    # a bearer reached only through a by-name of another entity (Jerusalem's 'Salem' / 'City of David' records,
    # 'Solomon's portico') is listed only when it holds a quarter of the main bearer's verses
    keep = [k for k in keep if k == keep[0] or hits[k] >= 0.25 * top or
            any(_skeletons_match(s, _name_skeleton(tp.people[k][0].split("@")[0])) for s in sks)]

    def describe(k: int, cap: int) -> str:
        rec = list(tp.people[k]) + ["", ""]
        brief, briefest, kind, desc = rec[1], rec[2], rec[5], rec[6]
        t = _brief_text(brief, cap) or _brief_text(briefest, cap) or _brief_text(desc, cap)
        return t or {"place": "a place", "person": "a person"}.get(kind, "")

    eng = tp.english(keep[0], sks)
    if len(keep) == 1:
        d = describe(keep[0], 100)
        return f"{eng}: {d}" if d else eng
    parts: List[str] = []
    for k in keep[:3]:
        uid_name = tp.people[k][0].split("@")[0]
        d = describe(k, 48)
        if uid_name != eng and not d.lower().startswith(uid_name.lower()):
            d = f"{uid_name}, {d}" if d else uid_name
        if d and d not in parts:
            parts.append(d)
    more = "; ..." if len(keep) > 3 else ""
    return f"{eng}: several bearers ({'; '.join(parts)}{more})"


def _apply_name_glosses(idx: _Index) -> None:
    """Glosses of the name lemmas attested in the Saints Latin text, from the TIPNR individuals in their verses."""
    tp = idx.tipnr
    for i, occ in idx.name_occ.items():
        lem = idx.lemmas[i]
        if not lem.proper or lem.key in _SAINTS_GLOSS:
            continue
        sks = _name_keys(lem.lemma) | _name_keys(idx.cap_surface.get(lem.hb, ""))
        hits: Counter = Counter()
        n_in = 0
        if tp is not None:
            for slug, ch, v in set(occ):
                if slug not in _TIPNR_BOOKS:
                    continue
                n_in += 1
                for k in tp.at(slug, int(ch), int(v), sks):
                    hits[k] += 1
        g = _name_gloss(idx, sks, hits, n_in) if hits else ""
        if g:
            lem.gloss = g
        elif lem.source == LS_SOURCE and lem.gloss and _BIBLICAL_MARKERS.search(lem.gloss):
            pass                                  # L&S describes the biblical bearer ('Elijah, a prophet ...')
        else:
            lem.gloss = "proper name"


# context rules for frequent function-word homographs (documented; the rest stays untagged)
_POSTPOSITIVE = {"autem", "ergo", "enim", "uero", "igitur", "quoque", "tamen"}
_COMPARATIVE_WORDS = {"magis", "plus", "potius", "prius", "ante", "post", "tam", "melius", "maius", "minus",
                      "amplius", "citius", "alius", "aliud", "aliter", "secus", "malle", "mauult", "malo"}
_CUM_CONJ_NEXT_ADV = {"adhuc", "iam", "non", "nondum", "neque", "nec", "itaque", "quidem", "tunc", "nunc",
                      "ibi", "inde", "unde", "prope", "simul"}
_CUM_CONJ_NEXT_PREP = {"in", "ad", "de", "ex", "ab", "a", "per", "super", "sub", "inter", "contra", "coram",
                       "ante", "post", "iuxta"}
_CUM_CONJ_NEXT_NOM = {"ego", "tu", "nos", "uos", "ipse", "ille", "is", "hi", "qui", "quae", "nemo", "nihil",
                      "dominus", "deus", "iesus", "christus", "paulus", "petrus"}
_CUM_PREP_NEXT_ABL = {"eo", "eis", "illo", "illis", "ea", "ipso", "ipsis", "his", "quo", "qua", "quibus",
                      "omni", "omnibus", "uno", "duobus", "tribus", "cunctis", "uniuersis", "toto", "totis",
                      "suo", "suis", "tuo", "tuis", "meo", "meis", "nostro", "nostris", "uestro", "uestris",
                      "alio", "aliis", "altero", "eodem", "eisdem", "iisdem", "nullo", "multis", "paucis",
                      "magno", "magnis", "isto", "istis", "populo", "seruis", "liberis", "amico", "dolo",
                      "diis", "concilio", "uxore", "filiis", "fratribus", "militibus", "principibus",
                      "sacerdotibus", "discipulis", "angelis", "homine", "hominibus", "mulieribus",
                      "pueris", "senibus", "regibus", "pelle", "capite", "ciuitate", "foetibus"}
_CUM_PREP_PREV = {"erat", "erant", "est", "sunt", "fuit", "fuerunt", "erit", "erunt", "sit", "sint", "esset",
                  "essent", "loqueretur", "loquebatur", "loquens", "locutus", "foedus", "pacem", "pactum",
                  "bellum", "dormiuit", "habitabat", "mansit", "abiit", "uenit", "egressus", "ingressus",
                  "ascendit", "descendit", "simul", "una", "dimicauit", "pugnauit", "iniit", "pepigit"}
_QUO_PREP_PREV = {"in", "a", "ab", "de", "ex", "e", "pro", "super", "cum", "sub", "sine", "absque", "coram", "prae"}
_QUO_TIME_PREV = {"tempore", "die", "diem", "anno", "loco", "itinere", "iter", "modo", "tempus"}
_QUO_ABL_ABS_NEXT = {"audito", "mortuo", "facto", "dicto", "completo", "expleto", "uiso", "cognito", "peracto",
                     "dimisso", "accepto", "intellecto", "nuntiato", "comperto"}
_QUO_ADV_PREV = {"nescit", "nescis", "nescio", "nescimus", "nescitis", "scit", "scis", "scio", "scimus", "scitis",
                 "ignorat"}
_QUO_ADV_NEXT = {"uado", "uadis", "uadit", "uadam", "uadas", "uadat", "ibis", "ibo", "ibit", "eat", "eam", "eamus",
                 "abieris", "abiit", "abierit", "fugiam", "fugiamus", "pergam", "pergis", "pergit"}
_QUAM_REL_PREP = {"ad", "per", "super", "in", "propter", "contra", "inter", "circa", "secundum", "ob"}
_QUAM_EXCL_NEXT = {"diu", "multi", "multa", "multum", "magna", "magnus", "magnum", "bonus", "bonum", "pulchra",
                   "dulcia", "terribilis", "mirabile", "speciosi", "dilecta", "parua", "angusta", "breuis"}
_QUOD_REL_PREP = {"propter", "secundum", "iuxta", "ad", "per", "in", "super", "ante", "ob", "contra", "inter",
                  "circa", "sub", "trans"}
_QUOD_REL_PREV = {"omne", "id", "hoc", "aliquid", "quidquid", "nihil", "bonum", "malum", "uerbum", "altare", "nisi",
                  "fecit", "fecitque", "fecerit", "feceris", "fecerunt", "fecerat", "fac", "facias", "facite",
                  "faciet", "faciam", "adimpleretur", "impleatur", "impleretur", "postula", "patiar", "habuerit"}
_QUOD_REL_NEXT = {"locutus", "dictum", "scriptum", "pepigit", "respicit", "praecepit", "praecepi", "praeceperat",
                  "fecerat", "fecerunt", "iusserat", "iussit", "uis", "iustum", "rectum", "placitum",
                  "interpretatur", "mouetur"}
_QUOD_REL_EST_NEXT2 = {"in", "super", "sub", "inter", "ante", "coram", "contra", "circa", "iuxta", "de", "ex", "ad",
                       "apud", "quasi", "bonum", "malum", "rectum", "iustum", "placitum", "sanctum"}
_QUOD_CONJ_PREV = {"propterea", "ideo", "idcirco", "excepto", "scito", "scitote", "scientes", "sciens", "scitis",
                   "scimus", "scio", "scit", "nescitis", "nesciens", "cognoscentes", "cognoscetis", "cognoscant",
                   "cognouerunt", "cognoui", "intelligam", "intellexi", "indicasti", "confiteri", "uiditque",
                   "dices", "crediderunt", "crederet", "credatis", "credo", "credimus", "timuerat", "timens",
                   "gaudeo", "gauisus", "gaudebant", "laetati", "miror", "mirati", "confiteor", "testificor",
                   "certus"}
_QUOD_CONJ_VERBS = _QUOD_CONJ_PREV | {
    "sciet", "scietis", "scietisque", "scies", "sciat", "sciant", "scire", "sciebat", "sciebant",
    "nescit", "nescio", "nescis", "nescimus", "nesciebat", "nesciebant",
    "noui", "nouit", "nouimus", "nostis", "nouerunt", "nouerat", "nouerant",
    "cognouit", "cognoscens", "cognoscet", "cognoscat", "cognoscite",
    "uidit", "uidens", "uidentes", "uidistis", "uidimus", "uidi", "uiderunt", "uiderant", "uidisset", "uidissent",
    "audiuit", "audierunt", "audiens", "audientes", "audistis", "audiuimus", "auditum",
    "nuntiatum", "nuntiatumque", "nuntiauerunt", "nuntiauit", "indicauit", "indica", "poenitet", "poenituit",
    "memento", "mementote", "recordatus", "recorderis", "probauimus", "probauit",
    "perspicuum", "certum", "manifestum", "notum", "sufficit", "laetatus", "intellexit",
    "intelligens", "intelligentes", "animaduertit", "considera", "considerate", "spondete",
    "iurauit", "iurauerat", "obsecro", "dico", "dixerunt", "dixit", "uides", "nosti",
}
_NEUT_MOD_INTERVENING = {"domini", "dei", "eius", "meum", "tuum", "suum", "nostrum", "uestrum", "hoc", "illud",
                         "istud", "ipsum", "omne", "suo", "tuo", "meo", "nostro", "uestro", "eorum", "illius",
                         "bonum", "malum", "magnum", "sanctum", "nouum", "ueterem", "foederis", "testimonii",
                         "israel", "sempiterni", "sempiternum"}
_FEM_MOD_INTERVENING = {"domini", "dei", "eius", "mea", "tua", "sua", "nostra", "uestra", "meam", "tuam", "suam",
                        "nostram", "uestram", "meae", "tuae", "suae", "nostrae", "uestrae", "hac", "hanc", "illa",
                        "illam", "ipsa", "ipsam", "optima", "optimam", "aurea", "auream", "magna", "magnam",
                        "sancta", "sanctam", "chanaan", "moysi", "israel", "iuda", "tui", "mei", "sui", "eorum",
                        "duplicem", "duplici", "laterum", "ranarum", "saccorum", "fletu", "nouam", "ueterem",
                        "omnium", "populi", "regis", "patris", "patrum", "filiorum", "tuorum", "meorum", "suorum"}
_CUM_CONJ_NON_ABL = {"haec", "se", "me", "te", "eum", "eam", "eos", "eas", "illum", "illam", "illos", "illas",
                     "hunc", "hanc", "hos", "has", "quem", "quam", "quos", "quas", "quid", "quod", "quis",
                     "aliquis", "aliquid", "omnes", "omnia", "dies", "tibi", "mihi", "ei", "sibi", "illud",
                     "id", "istud", "eius", "huius", "illius", "ipsius", "eorum", "earum"}
_CUM_INDECL_NUM = {"duodecim", "quatuor", "quattuor", "quinque", "sex", "septem", "octo", "nouem", "decem",
                   "undecim", "tredecim", "quatuordecim", "quattuordecim", "quindecim", "sedecim",
                   "uiginti", "triginta", "quadraginta", "quinquaginta", "centum", "mille"}
_CUM_ABL_FEM_A = {"laetitia", "ira", "gloria", "fiducia", "magna", "uniuersa", "multa", "tota", "sua", "tua",
                  "mea", "nostra", "uestra", "gratia", "misericordia", "benedictione", "reuerentia", "fallacia",
                  "ambitione", "potentia", "sapientia", "iustitia", "diligentia", "audacia", "patientia",
                  "tristitia", "superbia", "ferocia", "furia", "aqua", "familia", "turba", "pecunia", "praeda",
                  "sustantia", "substantia", "domina", "ancilla", "filia", "sponsa", "uxore", "uita", "terra"}
_UESTRUM_PARTITIVE = {"unusquisque", "unumquemque", "uniuscuiusque", "unicuique", "unoquoque", "quis", "nemo",
                      "neminem", "quem", "aliquis", "nullus", "nullius", "multi", "multis", "plures", "quidam",
                      "quilibet", "omnes", "omnium", "pars", "medio", "medium", "quisque", "quisquam", "singuli",
                      "singulos", "singulis", "alii", "ex", "de", "memor", "misereatur"}


def _dominant_analyses(idx: _Index, b: str, cap: bool = False) -> List[Tuple[int, str, str]]:
    """Analyses of ``b`` from its dominant lemma(s), filtering out rare classical homographs (< 1/15 of best prior)
    so 'rege' sees rex (N3|e) without rego impv., 'patrem' sees pater without patro subj., 'via' sees via without
    vio, 'legem' sees lex without lego#1, 'exercitu' sees exercitus without exerceo supine."""
    if not b:
        return []
    raw = []
    for i, pc, end in idx.analyse(b):
        ci = idx.canon.get(i, i)
        lem = idx.lemmas[ci]
        if lem.pos in ("X", "ALIAS"):
            continue
        if lem.proper and not cap and lem.key not in _LOWER_PROPER:
            continue
        raw.append((ci, pc, end))
    if not raw:
        return []
    by_i: Dict[int, List[Tuple[str, str]]] = defaultdict(list)
    for ci, pc, end in raw:
        by_i[ci].append((pc, end))
    if len(by_i) == 1:
        return raw
    priors = {ci: _base_prior(idx, ci) for ci in by_i}
    best = max(priors.values())
    if best >= 25.0:
        keep = {ci for ci, p in priors.items() if p * 15.0 >= best}
        if keep:
            return [(ci, pc, end) for ci, pc, end in raw if ci in keep]
    return raw


def _is_pure_verb(idx: _Index, b: str) -> bool:
    """True when ``b`` only analyses as finite/infinitive verb forms (never ablative/nominal)."""
    if not b:
        return False
    anas = idx.analyse(b)
    if not anas:
        return False
    for i, pc, _end in anas:
        lem = idx.lemmas[idx.canon.get(i, i)]
        if lem.pos != "V" or pc in ("VPP", "VFP", "V1N", "V2N", "V3IN", "VSUP"):
            return False
    return True


def _is_dominant_verb(idx: _Index, b: str) -> bool:
    """True when the dominant reading(s) of ``b`` are finite/infinitive verb forms."""
    anas = _dominant_analyses(idx, b, False)
    if not anas:
        return False
    for i, pc, _end in anas:
        lem = idx.lemmas[i]
        if lem.pos != "V" or pc in ("VPP", "VFP", "V1N", "V2N", "V3IN", "VSUP"):
            return False
    return True


def _is_pure_abl(idx: _Index, b: str, cap: bool = False) -> bool:
    """True when the dominant analyses of ``b`` are ablative (or dat/abl) nominal/adjectival forms."""
    if not b:
        return False
    if b in ("domo", "uasis"):
        return True
    anas = _dominant_analyses(idx, b, cap)
    if not anas:
        return False
    has_abl = False
    for i, pc, end in anas:
        lem = idx.lemmas[i]
        if lem.proper and not cap:
            continue
        if lem.pos in ("V", "ADV", "CONJ", "PREP", "INTERJ", "PART"):
            if lem.pos == "V" and pc in ("VPP", "VFP") and end in ("o", "is"):
                has_abl = True
                continue
            if lem.pos == "V" and pc in ("V1N", "V2N", "V3IN") and end in ("antibus", "entibus", "ientibus"):
                has_abl = True
                continue
            if lem.pos == "V" and pc == "VPP" and end == "u":
                continue          # supine in -u never follows conj. cum ('cum exercitu', 'cum fletu')
            return False
        if pc in ("N1", "N1PL") and end in ("is", "abus"):
            has_abl = True
        elif pc in ("N2", "N2IUS", "N2N", "N2R", "N2PLM", "N2PLN") and end in ("o", "is"):
            has_abl = True
        elif pc in ("N3", "N3N") and end in ("e", "ibus"):
            has_abl = True
        elif pc in ("N3I", "N3IM", "N3NI", "N3PL", "N3PLN") and end in ("e", "i", "ibus"):
            has_abl = True
        elif pc == "N4" and end in ("u", "ibus", "ubus"):
            has_abl = True
        elif pc == "N4N" and end in ("u", "ibus", "ubus"):
            has_abl = True
        elif pc == "N5" and end in ("e", "ebus"):
            has_abl = True
        elif pc in ("A12", "A12R", "A12PL") and end in ("o", "is"):
            has_abl = True
        elif pc in ("A3", "A31", "A31I", "A31C") and end in ("i", "ibus"):
            has_abl = True
        elif pc == "CMP" and end in ("iore", "iori", "ioribus"):
            has_abl = True
        elif pc in ("closed", "extra") and b in ("domo", "diis", "bobus", "bubus", "ui", "uiribus", "uobis", "nobis",
                                                 "eo", "eis", "illo", "illis", "ipso", "ipsis", "his", "eodem",
                                                 "eisdem", "iisdem", "tribus", "duobus", "duabus"):
            has_abl = True
        else:
            return False
    return has_abl


def _is_fem_sg_antecedent(idx: _Index, b: str) -> bool:
    """True when ``b`` is an unambiguous feminine singular noun/pronoun antecedent for relative ``quam``."""
    if not b:
        return False
    if b.endswith("que") and len(b) > 5 and not idx.analyse(b):
        b = b[:-3]
    if b in ("hanc", "eam", "illam", "ipsam", "suam", "tuam", "meam", "nostram", "uestram", "unam",
             "domum", "domo", "domus", "manum", "manu", "manus", "tribum", "tribu", "porticum",
             "ea", "haec", "illa"):
        return True
    anas = _dominant_analyses(idx, b, False)
    if not anas:
        return False
    has_fem = False
    for i, pc, end in anas:
        lem = idx.lemmas[i]
        if lem.proper or lem.pos != "N":
            return False
        if pc == "N1" and end in ("a", "am", "ae"):
            has_fem = True
        elif pc == "N5" and end in ("es", "em", "ei", "e") and lem.hb != "dies":
            has_fem = True
        elif (pc in ("N3", "N3I", "N3IM") and end in ("em", "im", "is", "e", "")) or \
                (pc == "x" and idx.lemma_fam.get(i) == "N3"):
            if lem.hb.endswith(("tas", "tio", "sio", "xio", "tudo", "ies", "uox", "lux", "pax", "lex", "nox",
                                "gens", "urbs", "pars", "sors", "mors", "mens", "crux", "salus", "uirtus",
                                "mulier", "uxor", "mater", "soror", "uirgo", "imago", "origo", "caligo",
                                "arbor", "nauis", "auis", "ouis", "pellis", "uallis", "turris", "auris",
                                "caro", "fames", "sitis", "seruitus", "iuuentus", "senectus", "securis",
                                "messis", "classis")):
                has_fem = True
            else:
                return False
        else:
            return False
    return has_fem


def _is_neut_sg_noun(idx: _Index, b: str) -> bool:
    """True when ``b`` is an unambiguous neuter singular noun antecedent for relative ``quod``."""
    if not b:
        return False
    if b.endswith("que") and len(b) > 5 and not idx.analyse(b):
        b = b[:-3]
    anas = _dominant_analyses(idx, b, False)
    if not anas:
        return False
    has_neut = False
    for i, pc, end in anas:
        lem = idx.lemmas[i]
        if lem.proper:
            continue
        if lem.pos == "V" and pc in ("VPP", "VSUP") and end in ("um", "i", "o"):
            continue          # substantival neuter nouns (pactum, peccatum, mandatum, decretum) alongside VPP
        if lem.pos == "ADJ" and b in ("foedus", "foederis", "foedere", "malum", "bonum", "reptile", "reptili"):
            continue
        if lem.pos != "N":
            return False
        if pc == "N2N" and end in ("um", "i", "o"):
            has_neut = True
        elif pc in ("N3N", "N3NI") and end in ("", "is", "e", "i"):
            has_neut = True
        elif pc == "x" and idx.lemma_fam.get(i) == "N3N" and b == lem.hb:
            has_neut = True
        elif pc == "N4N" and end == "u":
            has_neut = True
        else:
            return False
    return has_neut


def _is_masc_neut_noun(idx: _Index, b: str) -> bool:
    """True when ``b`` is a masculine or neuter singular noun (potential antecedent of relative ``quo``)."""
    if not b or b in _PREPS or b in _POSTPOSITIVE or b in ("et", "ac", "atque", "sed", "non", "nec", "neque", "ut", "si"):
        return False
    if b.endswith("que") and len(b) > 5 and not idx.analyse(b):
        b = b[:-3]
    anas = _dominant_analyses(idx, b, False)
    if not anas:
        return False
    ok = False
    for i, pc, end in anas:
        lem = idx.lemmas[i]
        if lem.proper:
            continue
        if lem.pos == "V" and pc in ("VPP", "VSUP") and end in ("us", "um", "u", "o", "i"):
            continue
        if lem.pos != "N":
            return False
        if pc in ("N2", "N2IUS", "N2R", "N2N") and end in ("us", "um", "i", "o", ""):
            ok = True
        elif pc in ("N3", "N3I", "N3IM", "N3N", "N3NI") and end in ("", "em", "is", "e", "i"):
            ok = True
        elif pc == "x" and idx.lemma_fam.get(i) in ("N2", "N3", "N3N"):
            ok = True
        elif pc in ("N4", "N4N") and end in ("us", "um", "u"):
            ok = True
        else:
            return False
    return ok


def _is_vestrum_poss_noun(idx: _Index, b: str) -> bool:
    """True when ``b`` is a masc. acc. sg. or neut. nom/acc sg. noun that takes possessive ``vestrum``."""
    if not b or b in _UESTRUM_PARTITIVE or b in ("autem", "et", "in", "de", "ex", "ad", "cum", "per", "est", "sunt",
                                                 "non", "quia", "quod", "unus", "cuius", "meum", "tuum", "suum"):
        return False
    if b in ("malum", "bonum", "cornu"):
        return True
    if b.endswith("que") and len(b) > 5 and not idx.analyse(b):
        b = b[:-3]
    anas = _dominant_analyses(idx, b, False)
    if not anas:
        return False
    ok = False
    for i, pc, end in anas:
        lem = idx.lemmas[i]
        if lem.proper:
            continue
        if lem.pos in ("PRON", "PREP", "CONJ", "ADV", "PART", "INTERJ"):
            return False
        if lem.pos != "N":
            continue
        if pc in ("N2", "N2IUS", "N2R", "N4") and end == "um":
            ok = True
        elif pc == "N2N" and end == "um":
            ok = True
        elif pc in ("N3", "N3I", "N3IM") and end == "em":
            ok = True
        elif pc in ("N3N", "N3NI") and end == "" and b == lem.hb:
            ok = True
        elif pc == "x" and idx.lemma_fam.get(i) in ("N3N", "N4N") and b == lem.hb:
            ok = True
        elif pc == "N4N" and end == "u":
            ok = True
    return ok


def _is_abl_participle(idx: _Index, b: str) -> bool:
    """True when ``b`` is an ablative participle ('Quo hausto', 'Quo respondente', 'Quo nato', 'Quo transeunte')."""
    if b.endswith("eunte"):
        return True
    anas = _dominant_analyses(idx, b, False)
    if not anas:
        return False
    return any(idx.lemmas[i].pos == "V" and ((pc == "VPP" and end == "o") or (pc in ("V1N", "V2N", "V3IN") and end in ("ante", "ente", "iente")))
               for i, pc, end in anas)


def _is_nom_participle(idx: _Index, b: str) -> bool:
    """True when ``b`` is a nominative/accusative perfect participle ('cum ingressi fueritis', 'cum nuntiatum esset')."""
    anas = _dominant_analyses(idx, b, False)
    if not anas:
        return False
    return any(idx.lemmas[i].pos == "V" and pc == "VPP" and end in ("us", "a", "um", "i", "ae") for i, pc, end in anas)


def _context_rule(idx: _Index, b: str, prev: str, nxt: str, cands: Dict[int, str],
                  prevs: Tuple[str, ...] = (), tok: str = "", nxt2: str = "",
                  initial: bool = False, question: bool = False, nxt_tok: str = ""
                  ) -> Optional[Tuple[int, str]]:
    """``prevs``: up to three preceding bare tokens ('melior est obedientia quam')."""
    prevs = prevs or (prev,)
    def pick(hb: str, n: str = "") -> Optional[int]:
        for i in cands:
            lem = idx.lemmas[i]
            if lem.hb == hb and (not n or lem.n == n):
                return i
        return None

    if b in ("cum", "cumque"):
        if nxt in _POSTPOSITIVE or b == "cumque" or prev == "praesertim":
            j = pick("cum", "2")
            if j is not None:
                return j, "context: conj. cum (followed by a postpositive particle / cumque / praesertim cum)"
        if nxt in _CUM_CONJ_NEXT_ADV or nxt in _CUM_CONJ_NEXT_PREP or nxt in _CUM_CONJ_NEXT_NOM or \
                nxt in _CUM_CONJ_NON_ABL:
            j = pick("cum", "2")
            if j is not None:
                return j, "context: conj. cum (followed by adverb, preposition, or non-ablative)"
        if nxt in ("ipsa", "hac", "utraque") and _is_pure_abl(idx, nxt2):
            j = pick("cum", "1")
            if j is not None:
                return j, "context: prep. cum ('cum ipsa/hac/utraque' + ablative noun)"
        if nxt == "hoc":
            if _is_dominant_verb(idx, nxt2):
                j = pick("cum", "2")
                if j is not None:
                    return j, "context: conj. cum ('cum hoc dixisset/fecissent')"
            if _is_pure_abl(idx, nxt2):
                j = pick("cum", "1")
                if j is not None:
                    return j, "context: prep. cum ('cum hoc mundo')"
        if nxt == "illa":
            j = pick("cum", "2") if _is_dominant_verb(idx, nxt2) else pick("cum", "1")
            if j is not None:
                return j, "context: conj. cum ('cum illa' + verb)" if _is_dominant_verb(idx, nxt2) else \
                    "context: prep. cum ('cum illa')"
        if _is_nom_participle(idx, nxt) and nxt2 in _SUM_FORMS:
            j = pick("cum", "2")
            if j is not None:
                return j, "context: conj. cum (followed by periphrastic participle + sum)"
        if (prev != "" or tok[:1].isupper()) and (nxt in _SUM_FORMS or _is_dominant_verb(idx, nxt)):
            j = pick("cum", "2")
            if j is not None:
                return j, "context: conj. cum (followed by a verb in a clause)"
        if nxt in _CUM_PREP_NEXT_ABL or (_is_pure_abl(idx, nxt, cap=nxt_tok[:1].isupper()) and not (
                nxt.endswith(("o", "is", "i")) and _is_dominant_verb(idx, nxt2) and
                nxt2.endswith(("et", "ent", "es", "em", "isset", "issent", "isses", "issem", "eret", "erent")))):
            j = pick("cum", "1")
            if j is not None:
                return j, "context: prep. cum (followed by an ablative)"
        if (nxt in _CUM_INDECL_NUM or nxt.endswith(("orum", "arum"))) and nxt2 in _SUM_FORMS:
            j = pick("cum", "2")
            if j is not None:
                return j, "context: conj. cum (age/predicate genitive + sum)"
        if nxt in _CUM_INDECL_NUM and _is_pure_abl(idx, nxt2):
            j = pick("cum", "1")
            if j is not None:
                return j, "context: prep. cum (numeral + ablative noun)"
        if nxt == "seruo" and nxt2 in ("tuo", "suo", "meo", "eius", "domini", "dei", "et", "in", ""):
            j = pick("cum", "1")
            if j is not None:
                return j, "context: prep. cum ('cum servo tuo/suo')"
        if nxt in _CUM_ABL_FEM_A and not _is_dominant_verb(idx, nxt2):
            j = pick("cum", "1")
            if j is not None:
                return j, "context: prep. cum (followed by ablative feminine noun/adjective)"
        if nxt_tok[:1].isupper() and not _is_dominant_verb(idx, nxt2) and (
                prev in _CUM_PREP_PREV or nxt in ("israel", "iuda", "absalom") or
                _is_pure_abl(idx, nxt2) or
                nxt2 in ("et", "est", "sunt", "erat", "erant", "fuit", "fuerunt", "erit", "erunt",
                         "in", "de", "ex", "ad", "super", "per", "", "rege", "filio", "filiis",
                         "uxore", "fratre", "patre", "matre", "uiro", "seruo", "seruis", "ducibus",
                         "principibus", "populo")):
            j = pick("cum", "1")
            if j is not None:
                return j, "context: prep. cum (governing a proper name)"
    if b == "quod":
        if prev == "eo":
            j = pick("quod")
            if j is not None:
                return j, "context: eo quod"
        if nxt in ("si", "nisi", "etsi"):
            j = pick("quod")
            if j is not None:
                return j, "context: transitional quod si / quod nisi"
        if initial and nxt == "autem":
            j = pick("quod")
            if j is not None:
                return j, "context: transitional 'Quod autem ...'"
        if prev in _QUOD_CONJ_PREV:
            j = pick("quod")
            if j is not None:
                return j, "context: conj. quod after verb of knowing/rejoicing or causal adverb"
        neut_ant = _is_neut_sg_noun(idx, prev) or (
            prev in _NEUT_MOD_INTERVENING and len(prevs) >= 2 and _is_neut_sg_noun(idx, prevs[-2])) or (
            prev == "enim" and len(prevs) >= 2 and prevs[-2] in ("omne", "id", "hoc", "aliquid", "nihil"))
        if prev in _QUOD_REL_PREP or nxt == "cum" or prev in _QUOD_REL_PREV or neut_ant:
            j = pick("qui", "1")
            if j is not None:
                return j, "context: relative quod (after preposition, neuter antecedent, or quod cum)"
        conj_win = any(p in _QUOD_CONJ_VERBS for p in prevs[-3:]) and prev not in _QUOD_REL_PREV
        if not conj_win and (nxt in _QUOD_REL_NEXT or
                             (nxt in ("est", "erat", "erit") and nxt2 in _QUOD_REL_EST_NEXT2) or
                             (nxt in ("bonum", "factum", "reliquum") and nxt2 in _SUM_FORMS)):
            j = pick("qui", "1")
            if j is not None:
                return j, "context: relative quod ('quod locutus/dictum/scriptum/bonum est')"
        if conj_win and nxt not in _QUOD_REL_NEXT:
            j = pick("quod")
            if j is not None:
                return j, "context: conj. quod after verb of perception/cognition/speech"
    if b == "quam":
        if any(p in _COMPARATIVE_WORDS or
               p.endswith(("ior", "iores", "iora", "iorem", "ioris", "iori", "iore", "iorum", "ioribus")) or
               (p.endswith("ius") and len(p) > 4) for p in prevs) or prev in ("supra", "ultra") or nxt == "ut":
            j = pick("quam")
            if j is not None:
                return j, "context: comparative + quam"
        if nxt in ("ob", "cum"):
            j = pick("qui", "1")
            if j is not None:
                return j, "context: relative quam ('quam ob rem' / 'Quam cum')"
        if nxt in _QUAM_EXCL_NEXT:
            j = pick("quam")
            if j is not None:
                return j, "context: exclamatory / adverbial quam"
        fem_ant = _is_fem_sg_antecedent(idx, prev) or (
            prev in _FEM_MOD_INTERVENING and len(prevs) >= 2 and _is_fem_sg_antecedent(idx, prevs[-2]))
        if prev in _QUAM_REL_PREP or fem_ant:
            j = pick("qui", "1")
            if j is not None:
                return j, "context: relative quam (after preposition or feminine antecedent)"
    if b == "quo":
        if prev in _QUO_ADV_PREV or nxt in _QUO_ADV_NEXT:
            j = pick("quo")
            if j is not None:
                return j, "context: adverb quo 'whither' with verb of motion / knowing"
        if (prev in _QUO_PREP_PREV and not (question and prev == "in" and initial)) or \
                prev in _QUO_TIME_PREV or (prev in _POSTPOSITIVE and len(prevs) >= 2 and prevs[-2] in _QUO_TIME_PREV) or \
                nxt == "cum" or nxt in _QUO_ABL_ABS_NEXT or _is_abl_participle(idx, nxt) or \
                prev == "eo" or (prev in _POSTPOSITIVE and len(prevs) >= 2 and prevs[-2] == "eo") or \
                (nxt in ("die", "tempore", "nomine", "loco", "modo") and not (initial and question)) or \
                (_is_masc_neut_noun(idx, prev) and nxt not in _QUO_ADV_NEXT) or \
                (prev in _NEUT_MOD_INTERVENING and len(prevs) >= 2 and _is_masc_neut_noun(idx, prevs[-2]) and
                 nxt not in _QUO_ADV_NEXT):
            j = pick("qui", "1")
            if j is not None:
                return j, "context: relative quo (after preposition, noun antecedent, or ablative absolute)"
    if b == "uestrum":
        if prev in _UESTRUM_PARTITIVE or (prev in _POSTPOSITIVE and len(prevs) >= 2 and prevs[-2] in _UESTRUM_PARTITIVE):
            j = pick("uos")
            if j is not None:
                return j, "context: partitive genitive vestrum (vos)"
        if _is_vestrum_poss_noun(idx, prev) or _is_vestrum_poss_noun(idx, nxt) or \
                (prev in _POSTPOSITIVE and len(prevs) >= 2 and _is_vestrum_poss_noun(idx, prevs[-2])) or \
                (prev in ("et", "ac", "atque") and len(prevs) >= 2 and prevs[-2] == "nostrum"):
            j = pick("uester")
            if j is not None:
                return j, "context: possessive vestrum agreeing with masc. acc. or neut. sg. noun"
    return None


# ---- forms decided by context only -----------------------------------------------------------
# Each rule set was written from a reading of every context of the form in the Saints Latin text (18 Nov 2026,
# e.g. all 207 'facies': 26 of 40 sampled were facio fut. 2 sg.).  When no rule applies, or rules for both
# readings apply, the token stays untagged instead of following the corpus prior.
_PREPS = {"in", "de", "ex", "e", "a", "ab", "ad", "super", "sub", "per", "pro", "ante", "contra", "coram", "cum",
          "inter", "post", "propter", "sine", "usque", "iuxta", "circa", "apud"}
_POSS_GEN = {"eius", "eorum", "earum", "illius", "ipsius", "huius", "tua", "tuae", "mea", "meae", "sua", "suas",
             "suae", "nostra", "nostras", "nostrae", "uestra", "uestras", "uestrae", "mearum", "tuarum"}
_FACIES_NOUN_NEXT = _POSS_GEN | {"hominis", "hominum", "leonis", "aquilae", "bouis", "regis", "domini", "pauperum",
                                 "peccatorum", "principum", "sacerdotum", "senum", "omnium", "sanctuarii", "cherub",
                                 "terrae", "abyssi", "caeli", "tristis"}
_FACIES_NOUN_PREV = _PREPS | {"quatuor", "quattuor", "duas", "duasque", "tres", "omnis", "uniuersae", "concidit"}
_FACIES_VERB_PREV = {"non", "nec", "neque", "ne", "sic", "ita", "similiter", "quid", "quae", "quod", "quaecumque",
                     "quodcumque", "saluum", "saluam", "saluos", "saluosque", "hoc", "cuncta", "furtum", "homicidium",
                     "irritum", "notum", "requiescere"}
_FACIES_VERB_NEXT = {"tibi", "mihi", "ei", "eis", "sibi", "nobis", "illi", "illis", "illud", "eam", "eum", "eos",
                     "eas", "me", "te", "mecum", "tecum", "quodcumque", "quaecumque", "omnia", "cuncta", "ut",
                     "iudicium", "misericordiam", "opus", "opera", "panem", "panes", "hircum", "coronas",
                     "remissionem", "murum", "calumniam", "sicut", "postea", "ergo", "homines", "mandata",
                     "iniquitatem", "quidquam", "omne"}
_MUNDUS_NOUN_PREV = {"huius", "lux", "saluator", "saluatorem", "rex", "princeps", "principe", "constitutione",
                     "constitutionem", "origine", "initio", "institutione", "creatura", "peccatum", "peccata",
                     "elementa", "elementis", "regna", "fines", "totius", "gentes", "colles", "ignobilia", "infirma",
                     "stulta", "sapientiam", "sapientia", "figura", "amicitia", "substantiam", "lucem", "saeculum",
                     "coinquinationes", "rectores", "creatori", "reconciliatio", "pro", "ante", "in", "hunc", "per",
                     "ad", "uniuersum", "totum", "uincit", "uici", "dilexit", "diligere", "diligit", "fecit",
                     "iudicet", "iudicem", "iudicabit", "saluificem", "relinquo", "arguet", "damnauit", "ingrediens",
                     "lucretur", "illuminans", "hoc", "huic", "de", "ex", "toto", "uniuerso", "originali"}
_MUNDUS_NOUN_NEXT = {"huius", "constitutionem", "creatori", "rectores", "principe", "creator", "uniuersum",
                     "totum", "reconcilians", "muliebrem", "muliebri"}
_MUNDUS_ADJ_PREV = {"estis", "uos", "omnes", "erimus", "cor", "aurum", "iumentum", "locum", "hominem", "quod",
                    "quidquid", "est", "siue", "uitro", "uase", "lino", "homo", "beati"}
_MUNDUS_ADJ_NEXT = {"estis", "estote", "sunt", "erimus", "eritis", "est", "esse", "me", "corde", "obrizo"}
_SCRIBAM_VERB_NEXT = {"super", "in", "ei", "eis", "eam", "eum", "illis", "illi"}
_SEDE_VERB_NEXT = {"a", "hic", "et", "in", "tacens", "cito", "sub", "ibi"}
_SEDE_VERB_PREV = {"et", "aut", "tu", "surge", "consurge", "descende"}
_HIC_ADV_PREV = {"sede", "sedete", "sta", "state", "mane", "manete", "expectate", "exspectate", "sustinete",
                 "pone", "quid"}
_HIC_ADV_NEXT = {"esse", "agis", "statis", "sumus", "maneatis", "maneas", "moriar", "sedebitis", "habitabo"}
_INTERROG = {"quem", "cui", "cuius", "quibus"}
_SUM_FORMS = {"est", "sunt", "erat", "erant", "fuit", "fuerit", "fuerat", "fuerint", "fuerant", "fuerunt", "esset",
              "essent", "sit", "sint", "fuisset", "fuissent", "es", "sum", "sumus", "estis", "eram", "ero", "erit",
              "erunt", "esse", "fuisse", "fueris", "fuero", "fuissem", "fuisti"}
_PERFECT_VERBS = {"orior", "exorior", "progredior", "egredior", "regredior", "ingredior", "aggredior", "transgredior",
                  "nascor", "patior", "coorior", "adorior"}
_PRONOUN_OBJ = {"me", "te", "se", "eum", "eam", "illum", "illam", "deum", "dominum", "hunc", "hanc"}
_POSSESSIVE_FORMS = {"suis", "suos", "suorum", "tuis", "tuos", "tuorum", "meis", "meos", "meorum", "nostris", "nostros",
                     "uestris", "uestros", "eius", "eorum", "earum", "illius", "ipsius"}
_LIBERI_PREV = {"absque", "sine", "cum", "duobus", "uxoribus", "coniugibus", "ac", "impositis", "habebat", "genuerat",
                "oppressit", "da", "nec", "suis", "tuis", "quam"}
_PLAGA_REGION = ("orient", "occident", "austr", "meridi", "septentrion", "aquilo", "maris")
_ORDINAL_ABL = {"primo", "secundo", "tertio", "quarto", "quinto", "sexto", "septimo", "octauo", "nono", "decimo",
                "undecimo", "duodecimo", "uigesimo", "uicesimo", "tricesimo", "trigesimo", "quadragesimo"}
_ORDINAL_NOUNS = {"die", "diei", "mense", "mensis", "anno", "tempore", "diluculo", "loco", "uersu", "sabbato"}
_TRIBUS_TRIBE_NEXT = {"filiorum", "israel", "iuda", "sua", "suae", "eius", "tua", "mea", "ipsorum", "patrum",
                      "nostra", "uestra", "eorum"}
_TRIBUS_TRIBE_PREV = {"dimidia", "dimidiae", "una", "unius", "omnis", "omnes", "singulas", "singulae", "alterius",
                      "cuncta", "cunctae", "uniuersa", "uniuersae", "de", "ex", "per", "in", "super", "ad",
                      "duodecim", "minimus", "tota", "totius", "alia", "aliam", "aliqua", "quae", "qua", "eius"}
_VENIA_WORDS = {"dare", "da", "dabas", "dedit", "dabit", "dabo", "impetrabit", "impetrabitque", "impetret", "peto",
                "petere", "petiit", "precor", "deprecor", "oro", "prodeundi", "indulgeo"}


def _context_form(idx: _Index, b: str, tok: str, prev: str, nxt: str, nxt2: str, prevs: Tuple[str, ...],
                  cands: Dict[int, List[Tuple[str, str]]], initial: bool, question: bool, prev_tok: str = ""
                  ) -> Optional[Tuple[Optional[int], str]]:
    """(lemma id or None for 'leave untagged', note) for forms decided by context; None = no special rule."""
    def pick(hb: str, n: str = "") -> Optional[int]:
        for i in cands:
            lem = idx.lemmas[i]
            if lem.hb == hb and (not n or lem.n == n):
                return i
        return None

    def choose(noun_ok: bool, verb_ok: bool, noun: Optional[int], verb: Optional[int], what: str):
        if noun_ok and not verb_ok and noun is not None:
            return noun, f"context: {what} (noun/adjective reading)"
        if verb_ok and not noun_ok and verb is not None:
            return verb, f"context: {what} (verb reading)"
        return None, f"ambiguous: {what} not decided by its context"

    window = set(prevs[-2:]) | {nxt, nxt2}
    # ---- 19 Nov 2026: frequent forms left untagged before (every context of each form read in the Saints Latin)
    if b.startswith("plag") and b[4:] in ("a", "am", "ae", "as", "is", "arum"):
        # plaga 'region, side' beside a quarter of the sky ('ad orientalem plagam', 'a plaga orientali usque ad
        # plagam maris': 60 of 255); otherwise plāga 'blow, wound, plague' ('facta est plaga magna', 'plaga leprae')
        region = any(w.startswith(_PLAGA_REGION) for w in window if w)
        j = pick("plaga", "2") if region else pick("plaga", "1")
        if j is not None:
            return j, "context: plaga 'region' beside a quarter of the sky" if region else \
                "context: plaga 'blow, plague' (no quarter of the sky beside it)"
        return None
    if b.startswith("occid") and not (b.startswith("occident") and len(b) > 8) and pick("occido", "2") is not None and \
            pick("occido", "1") is not None:
        # occīdo 'kill' and occĭdo 'fall, set' share every present and perfect form; 'set' only of the sun or
        # moon ('antequam occidat sol').  L&S: occido1 = occīdo [ob-caedo] 'kill', occido2 = occĭdo [obcado] 'fall'.
        if any(w in ("sol", "solis", "solem", "luna", "lunae") for w in set(prevs) | {nxt, nxt2}):
            return pick("occido", "2"), "context: occido 'set' (of the sun)"
        return pick("occido", "1"), "context: occido 'kill' (no sun or moon in the context)"
    if b in _ORDINAL_ABL and (window & _ORDINAL_NOUNS or any(p in _ORDINAL_NOUNS for p in prevs) or
                              any(w.endswith("esimo") for w in window if w) or
                              (prev in ("in", "a", "ab", "ex", "de") and not _is_pure_verb(idx, nxt))):
        # 'die septimo', 'in primo mense', 'anno primo', 'vicesimo septimo': the ordinal adjective, not the adverb
        for i in cands:
            if idx.lemmas[i].pos in ("ADJ", "NUM") and idx.lemmas[i].hb.endswith("us"):
                return i, "context: ordinal beside die / mense / anno / preposition"
        return None
    if b == "uoluit":
        tl = tok.lower()
        if "lu" in tl:
            j = pick("uolo", "1")
            if j is not None:
                return j, "orthography: voluit (volo 'willed', u not v)"
        elif "lv" in tl:
            j = pick("uoluo")
            if j is not None:
                return j, "orthography: volvit (volvo 'rolled', v not u)"
    if b in ("aeris", "aeri", "aere", "aera"):
        tl = tok.lower()
        if "æ" in tl:
            j = pick("aes")
            if j is not None:
                return j, "orthography: æ- (aes 'bronze/brass')"
        elif "ë" in tl:
            j = pick("aer")
            if j is not None:
                return j, "orthography: aë- (aer 'air')"
    if b in ("occidentem", "occidente") and (prev in _PREPS or (b == "occidente" and prev == "et" and "oriente" in prevs)):
        j = pick("occidens")
        if j is not None:
            return j, "context: ad/contra/in/ab occidente(m) (the west)"
    if b == "lectum":
        if nxt in _SUM_FORMS:
            j = pick("lego", "2")
            if j is not None:
                return j, "context: lectum est (passive of lego 'read')"
        if prev in _PREPS or prev in ("tetigerit", "tolle", "tulit", "noctes", "transgreditur") or \
                nxt in ("suum", "tuum", "meum", "eius", "doloris", "strati", "ponit"):
            j = pick("lectus", "2")
            if j is not None:
                return j, "context: lectum 'bed' (super/in lectum, tolle lectum)"
    if b == "tribui":
        if prev in ("dimidiae", "mediae", "sors", "quinta", "possessionem", "moyses", "autem") or \
                nxt in ("manasse", "filiorum", "gad", "leui") or (nxt == "autem" and nxt2 == "leui"):
            j = pick("tribus")
            if j is not None:
                return j, "context: tribui 'to the tribe' (dimidiae tribui Manasse)"
    if b == "uis":
        if prev in ("nulla", "magna", "tanta", "quanta", "omnis", "ipsa", "haec", "illa") or \
                nxt in ("aquae", "ignis", "uenti", "flammae", "spiritus", "naturae"):
            j = pick("uis")
            if j is not None:
                return j, "context: vis 'force, power' (nominal context)"
        if question or prev in ("quid", "non", "si", "quod", "quo", "domine", "tibi", "tu", "ut", "me", "ei", "ubi",
                                "sicut", "quemadmodum", "inquit", "istum") or \
                (prev in _POSTPOSITIVE and len(prevs) >= 2 and prevs[-2] in ("si", "quid", "quod", "quo", "non")) or \
                nxt in ("ut", "sed", "potes", "facere", "dimittere", "possidere", "faciam", "paremus", "tollere",
                        "discere", "noli", "uenire", "currere", "ascendere", "ire", "dare", "dicere", "uideam",
                        "manducare", "bibere", "accipere", "sequi", "eamus", "dicimus") or \
                nxt.endswith(("are", "ere", "ire")):
            j = pick("uolo", "1")
            if j is not None:
                return j, "context: vis 'you wish' (volo 2 sg.)"
    if b == "mensa":
        j = pick("metior") if nxt == "est" else pick("mensa")
        if j is not None:
            return j, "context: mensa est (participle of metior)" if nxt == "est" else "context: mensa 'table'"
    if b == "rei" and tok[:1].islower():
        if prev in ("hujus", "huius", "omnis", "nullius", "cuius", "alicui", "uniuscuiusque", "necessariae",
                    "euentum", "ordinem", "finem", "ueritatem", "exitum", "postea"):
            j = pick("res")
            if j is not None:
                return j, "context: rei 'of the matter/thing' (res gen./dat. sg.)"
        if prev in ("iniquitatis", "praeuaricationis", "mortis", "sanguinis", "iudicii", "gehennae"):
            j = pick("reus")
            if j is not None:
                return j, "context: rei 'guilty' (reus nom. pl.)"
    if b == "lineis" and prev == "decem":
        j = pick("linea")
        if j is not None:
            return j, "context: decem lineis 'ten lines/degrees' (2 Kgs 20:10)"
    if b == "soli":
        if nxt in ("et",) and nxt2 in ("lunae", "stellis") or prev in ("in", "sub", "ad", "coram", "contra") and \
                nxt in ("et", "lunae"):
            j = pick("sol")
            if j is not None:
                return j, "context: soli 'to the sun' (beside lunae)"
        if prev in ("domino", "deo", "illi", "ei", "tibi", "mihi", "sibi", "uos", "nos", "estis", "eritis", "sunt",
                    "homines", "ipsi", "uni", "patri") or nxt in ("seruies", "seruietis", "homines", "in", "estis"):
            j = pick("solus", "1")
            if j is not None:
                return j, "context: soli 'alone/only' (solus)"
    if b == "liber":
        if nxt in ("generationis", "legis", "sermonum", "uerborum", "repudii", "uitae", "foederis", "dierum",
                   "iustorum", "mandatorum", "domini", "iste", "hic") or prev in ("hic", "est", "scriptus") and \
                nxt not in ("gratis", "ab", "a", "non", "sum", "es", "est", "sicut"):
            j = pick("liber", "4")
            if j is not None:
                return j, "context: liber 'book'"
        if prev in ("egredietur", "egrediar", "egrediatur", "sum", "es", "est", "fuit", "eris", "erit", "mortuos",
                    "uir", "seruus", "homo", "non") or nxt in ("gratis", "ab", "a", "est", "erit", "sum"):
            j = pick("liber", "1")
            if j is not None:
                return j, "context: liber 'free'"
    if b == "munda":
        if nxt in ("me", "nos", "cor", "eum", "eam", "prius"):
            j = pick("mundo")
            if j is not None:
                return j, "context: munda 'cleanse!' (mundo impv.)"
        if nxt in _SUM_FORMS or prev in ("oblatio", "omnia", "congregatio", "uasa", "uestimenta", "animalia", "quae"):
            j = pick("mundus", "1")
            if j is not None:
                return j, "context: munda 'clean' (mundus adj.)"
    if b == "uiuam":
        if prev in ("aquam", "hostiam", "animam", "eam", "carnem", "uocem", "uictoriam"):
            j = pick("uiuus")
            if j is not None:
                return j, "context: vivam 'living' (vivus adj.)"
        if prev in ("non", "sed", "et", "ut", "iam", "ego", "ne", "nec") or nxt in ("et", "in", "domino", "deo"):
            j = pick("uiuo")
            if j is not None:
                return j, "context: vivam 'I will/may live' (vivo)"
    if b == "uiuas":
        if prev == "aquas":
            j = pick("uiuus")
            if j is not None:
                return j, "context: aquas vivas 'living water' (vivus adj.)"
        if prev in ("ut", "ea", "longo", "multo", "et", "tu", "quod") or nxt in ("tempore", "et", "atque"):
            j = pick("uiuo")
            if j is not None:
                return j, "context: vivas 'that you may live' (vivo subj.)"
    if b == "ibis":
        if any(w in ("coruus", "ericius", "onocrotalus") for w in window):
            j = pick("ibis")
            if j is not None:
                return j, "context: ibis 'ibis' (bird list, Isa 34:11)"
        if prev in ("autem", "eam", "sic", "te", "caesarem") or nxt in ("ad", "et", "cum"):
            j = pick("eo", "1")
            if j is not None:
                return j, "context: ibis 'you will go' (eo fut. 2 sg.)"
    if b == "passus":
        if any(w in ("sex", "mille", "uiginti", "quindecim", "centum", "duo", "tres", "quatuor", "quattuor", "decem")
               for w in window):
            j = pick("passus", "3")
            if j is not None:
                return j, "context: numeral + passus 'pace, step' (passus#3)"
        if prev in ("similia", "dira", "multa") or nxt in _SUM_FORMS or prev in _SUM_FORMS:
            j = pick("patior")
            if j is not None:
                return j, "context: passus 'having suffered' (patior)"
    if b == "disco" and prev == "in":
        j = pick("discus")
        if j is not None:
            return j, "context: in disco 'on a platter' (discus)"
    if b in ("perfectus", "perfectum", "perfecto"):
        if b == "perfecto" or prev in ("uir", "esto", "cor", "hominem", "atque", "et", "in", "ad", "post", "corde", "uis") or \
                nxt in ("corde", "esse", "eris", "cum", "decore", "fuit"):
            j = pick("perfectus", "1")
            if j is not None:
                return j, "context: perfectus 'perfect, complete' (adj.)"
        if nxt in _SUM_FORMS or prev in _SUM_FORMS:
            j = pick("perficio")
            if j is not None:
                return j, "context: perfectus/perfectum + sum (perficio pass.)"
    if b == "tertio" and not (window & _ORDINAL_NOUNS):
        if prev in ("concepit", "iam", "ac", "et", "feceruntque", "uenit", "uocauit", "orauit", "dixit", "interrogauit",
                    "deliquit", "percussit", "cecinit", "negabis", "uenio", "samuelem", "petrum") or \
                nxt in ("et", "idipsum", "in", "autem", "ait", "dixit"):
            j = pick("tertio", "1")
            if j is not None:
                return j, "context: tertio 'a third time' (adverb)"
    if b == "tertium":
        if prev in ("diem", "ostium", "annum", "mensem", "locum", "calicem", "signum", "filium", "secundum", "et") or \
                nxt in ("animal", "diem", "ostium", "annum", "mensem", "quoque", "caelum", "partem", "angelum", "sigillum"):
            j = pick("tertius")
            if j is not None:
                return j, "context: tertium 'third' (ordinal adj.)"
    if b == "sumptus":
        if nxt in _SUM_FORMS or prev in _SUM_FORMS:
            j = pick("sumo")
            if j is not None:
                return j, "context: sumptus + sum (sumo pass.)"
        if prev in ("in", "ad", "omnes", "de", "et") or nxt in ("autem", "dabuntur", "et", "ad", "de"):
            j = pick("sumptus", "2")
            if j is not None:
                return j, "context: sumptus 'expense, cost' (noun)"
    if b == "motus":
        if nxt in ("magnus", "terrae", "maris", "aquae") or prev in ("factus", "est", "ecce") and nxt in ("magnus", "terrae"):
            j = pick("motus", "2")
            if j is not None:
                return j, "context: motus 'commotion, quake' (noun)"
        if nxt in _SUM_FORMS or prev in _SUM_FORMS or nxt in ("nimis", "est", "fuit", "isaac", "misericordia"):
            j = pick("moueo")
            if j is not None:
                return j, "context: motus 'moved' (moveo part.)"
    if b == "tecta":
        if prev in ("super", "in", "de", "omnia", "et") and nxt not in _SUM_FORMS:
            j = pick("tectum")
            if j is not None:
                return j, "context: tecta 'roofs' (tectum)"
        if nxt in _SUM_FORMS or prev in ("plaustra", "quae", "sunt", "erant"):
            j = pick("tego")
            if j is not None:
                return j, "context: tecta 'covered' (tego part.)"
    if b == "ornatum":
        if prev in ("ad", "in", "depone", "suum", "tuum", "eius") or nxt in ("tuum", "suum", "meum", "eius", "superhumeralis", "pertinens"):
            j = pick("ornatus", "2")
            if j is not None:
                return j, "context: ornatum 'ornament, attire' (noun)"
        if nxt in _SUM_FORMS or prev in _SUM_FORMS:
            j = pick("orno")
            if j is not None:
                return j, "context: ornatum + sum (orno pass.)"
    if b == "mundus":
        clean = any(w.startswith(("immund", "pollut", "profan", "purific")) for w in window if w)
        adj_ok = clean or nxt in ("sum", "ego", "erit", "est", "sit", "fuit", "subtilis") or \
            prev in ("esset", "erat", "erit", "sit", "fuerit", "tam", "homo", "uir", "non", "qui") and nxt != "dat"
        noun_ok = (prev in ("cognouit", "cognoscat", "iudicabitur", "odit", "tunc", "ille", "mihi", "uos", "hoc",
                            "quomodo", "totus", "uniuersus", "hic") or
                   nxt in ("totus", "transit", "non", "per", "eos", "crucifixus", "aqua", "dat", "iste", "hic",
                           "odit", "cognouit", "saluetur", "credit", "uideat")) and not clean
        if noun_ok and not adj_ok:
            j = pick("mundus", "2")
            if j is not None:
                return j, "context: mundus 'world' (nom. sg.)"
        if adj_ok and not noun_ok:
            j = pick("mundus", "1")
            if j is not None:
                return j, "context: mundus 'clean' (nom. sg.)"
    if b == "reliqui":
        adj_ok = nxt in ("fuerint", "erant", "fuerant", "populi", "principes", "sacerdotes", "pecoris", "autem",
                         "fugerunt", "philisthinorum", "ex", "de") or prev in ("omnes", "manus", "peribunt")
        verb_ok = prev in ("ego", "quam", "quos", "quem", "quae", "te", "me", "eum", "eos", "trophimum") or \
            nxt in ("uos", "te", "eum", "eam", "eos", "eas", "illum", "illam", "troade", "infirmum")
        if adj_ok and not verb_ok:
            j = pick("reliquus")
            if j is not None:
                return j, "context: reliqui 'the remaining / rest'"
        if verb_ok and not adj_ok:
            j = pick("relinquo")
            if j is not None:
                return j, "context: reliqui 'I left' (relinquo perf. 1 sg.)"
    if b == "libera":
        verb_ok = nxt in ("me", "nos", "eum", "eam", "eos", "eas", "animam", "fratres", "populum", "israel",
                          "seruum", "filios") or prev in ("domine", "dicens", "dicet", "temetipsum", "surge", "cito", "nunc")
        adj_ok = prev in ("de", "erat", "fuit", "domo", "ierusalem", "quae", "sancta", "meo") or \
            nxt in ("est", "facta", "seorsum", "ab", "habeant")
        if verb_ok and not adj_ok:
            j = pick("libero")
            if j is not None:
                return j, "context: libera 'deliver!' (libero impv.)"
        if adj_ok and not verb_ok:
            j = pick("liber", "1")
            if j is not None:
                return j, "context: libera 'free' (adj. fem.)"
    if b == "statuam":
        noun_ok = prev in ("adorate", "adorauerunt", "adoret", "fecit", "percussit", "percusserat", "protulerunt",
                           "constitues", "michol", "in") or nxt in ("auream", "salis", "quam", "quae", "factus")
        verb_ok = prev in ("ego", "meum") or nxt in ("pactum", "foedus", "testamentum", "eum", "eam", "eos",
                                                     "te", "uos", "super", "contra", "ad")
        if noun_ok and not verb_ok:
            j = pick("statua")
            if j is not None:
                return j, "context: statuam 'statue / image'"
        if verb_ok and not noun_ok:
            j = pick("statuo")
            if j is not None:
                return j, "context: statuam 'I will establish' (statuo fut. 1 sg.)"
    if b in ("multo", "quanto"):
        comp_next = nxt in ("magis", "plus", "minus", "plures", "plura", "maiora", "melius", "amplius", "ampliorem",
                            "differentius", "pretiosior") or \
            nxt.endswith(("ior", "ius", "iores", "iora", "iorem")) or \
            (nxt in _POSTPOSITIVE and nxt2 in ("magis", "plus", "plures", "plura", "maiora"))
        abl_noun = nxt in ("tempore", "exercitu", "populo", "desiderio", "uino", "labore", "tremore", "decore",
                           "comitatu", "miraculo", "gaudio", "fletu", "amore", "timore", "honore", "auro",
                           "argento", "sanguine", "numero", "strepitu", "tumultu", "clamore", "impetu",
                           "dolore", "maerore", "studio", "pondere") or \
            prev in ("exercitu", "populo", "tremore", "decore", "tempore", "labore", "uino", "gaudio",
                     "fletu", "clamore", "honore", "timore", "dolore", "pondere", "numero", "in", "cum")
        if comp_next and not abl_noun:
            j = pick("multo", "1") if b == "multo" else pick("quanto")
            if j is not None:
                return j, f"context: {b} + comparative (adverb 'by much / how much')"
        if abl_noun and not comp_next:
            j = pick("multus") if b == "multo" else pick("quantus")
            if j is not None:
                return j, f"context: {b} with ablative noun (adjective)"
    if b == "tribus":
        if not nxt[:1].isupper() and nxt.endswith(("bus", "is")) and nxt not in _POSS_GEN:
            j = pick("tres")
            if j is not None:
                return j, "context: tribus 'three' before a plural ablative ('tribus diebus')"
        if nxt in _TRIBUS_TRIBE_NEXT or prev in _TRIBUS_TRIBE_PREV or (nxt and _cap_attested(idx, nxt)):
            j = pick("tribus")
            if j is not None:
                return j, "context: tribus 'tribe' ('tribus Juda', 'dimidia tribus')"
        return None, "ambiguous: tribus = tribe / three not decided by its context"
    if b == "forte":
        if prev in ("ne", "si", "nisi", "num", "sicubi", "quod") or \
                (prev in ("quid", "quis", "quando", "ubi", "quo") and len(prevs) >= 2 and prevs[-2] in ("si", "ne", "nisi")) or \
                (initial and nxt in ("uiuos", "est", "sunt", "non")):
            j = pick("fors")
            if j is not None:
                return j, "context: 'ne/si/quod forte' (forte = by chance, perhaps)"
        if prev in ("exemplum", "brachium", "cor", "murum", "lignum", "uincere", "uas", "bellum", "opus"):
            j = pick("fortis")
            if j is not None:
                return j, "context: forte 'strong' (fortis neut. sg.)"
    if prev in _SUM_FORMS or nxt in _SUM_FORMS:
        # 'ortus est', 'orta est lepra', 'exortum est', 'progressus est', 'natus est': the deponent's participle in
        # a perfect, not the noun ortus 'rising' or the P. a. ortus 'sprung' (19 Nov 2026)
        for i, anas in cands.items():
            if idx.lemmas[i].hb in _PERFECT_VERBS and any(pc == "VPP" and e != "u" for pc, e in anas):
                return i, "context: participle + form of sum (perfect of the verb)"
    if b in ("solum", "solumque"):
        if prev in _PREPS:
            j = pick("solum", "1")
            if j is not None:
                return j, "context: solum 'ground' after a preposition ('ad solum')"
        if prev in _PRONOUN_OBJ or nxt in _PRONOUN_OBJ:
            j = pick("solus")
            if j is not None:
                return j, "context: solum 'alone' with a pronoun ('me solum relinquatis')"
    if b in ("liberi", "liberos", "liberis", "liberorum") and tok[:1].islower():
        children = nxt in _POSS_GEN or nxt in _POSSESSIVE_FORMS or prev in _LIBERI_PREV
        free = nxt in _SUM_FORMS or prev in ("eos", "dimiseris", "dimittes", "dimittetis", "dimittet", "esse")
        j = pick("liberi") if children and not free else pick("liber", "1") if free and not children else None
        if j is not None:
            return j, "context: liberi 'children'" if children else "context: liber 'free'"
    if b == "ueniam":
        j = pick("uenia") if window & _VENIA_WORDS else pick("uenio")
        if j is not None:
            return j, "context: venia 'pardon' ('veniam dare')" if window & _VENIA_WORDS else                 "context: veniam 'I will come / that I may come'"
        return None
    if b == "facies":
        noun_ok = nxt in _FACIES_NOUN_NEXT or prev in _FACIES_NOUN_PREV
        verb_ok = prev in _FACIES_VERB_PREV or nxt in _FACIES_VERB_NEXT or \
            (initial and tok[:1].isupper() and nxt in ("et", "quoque", "in"))
        return choose(noun_ok, verb_ok, pick("facies"), pick("facio"), "facies = face / facio fut. 2 sg.")
    if b in ("mundi", "mundum", "mundo"):
        clean = any(w.startswith(("immund", "pollut", "profan")) for w in window if w)
        adj_ok = clean or prev in _MUNDUS_ADJ_PREV or nxt in _MUNDUS_ADJ_NEXT
        noun_ok = (prev in _MUNDUS_NOUN_PREV or nxt in _MUNDUS_NOUN_NEXT) and not clean
        return choose(noun_ok and not adj_ok, adj_ok and not noun_ok, pick("mundus", "2"), pick("mundus", "1"),
                      "mundus = world / clean")
    if b == "scribam":
        # 'Baruch scribam', 'ad Saphan scribam': the scribe after a name; 'scribam super eas': I will write
        noun_ok = (prev_tok[:1].isupper() and prev not in ("et", "sed", "nunc", "tunc", "ecce", "ego", "quid")) or \
            nxt == "templi"
        verb_ok = nxt in _SCRIBAM_VERB_NEXT or prev in ("quid", "certum")
        return choose(noun_ok, verb_ok, pick("scriba"), pick("scribo"), "scribam = scribe / I will write")
    if b == "sede":
        noun_ok = prev in _PREPS
        verb_ok = not noun_ok and ((initial and tok[:1].isupper()) or nxt in _SEDE_VERB_NEXT or
                                   prev in _SEDE_VERB_PREV)
        return choose(noun_ok, verb_ok, pick("sedes"), pick("sedeo"), "sede = seat / sit!")
    if b == "uiuo":
        verb_ok = nxt in ("ego", "autem", "in") or prev in ("ego", "nunc", "idcirco", "propterea")
        adj_ok = prev in ("deo", "passere")
        return choose(adj_ok, verb_ok, pick("uiuus"), pick("uiuo"), "vivo = living / I live")
    if b == "sine":
        if nxt in ("ut", "modo", "prius", "uideamus", "eiiciam", "eiciam") or \
                (initial and tok[:1].isupper() and nxt in ("me", "nos", "eum", "eam", "eos", "quid")):
            j = pick("sino")
            if j is not None:
                return j, "context: imperative of sino ('Sine modo', 'Sine ut ...')"
        return None
    if b == "hic":
        if prev in _HIC_ADV_PREV or nxt in _HIC_ADV_NEXT or (prev == "est" and prevs[-2:-1] == ("non",)):
            j = pick("hic")
            if j is not None:
                return j, "context: adverb hīc 'here' (Lewis & Short lists it under hic)"
        return None
    if b in _INTERROG and initial and question:
        j = pick("quis", "1")
        if j is not None:
            return j, "context: interrogative (sentence-initial, the sentence ends with '?')"
    return None


_ADJ_OR_PART = {"A12", "A12R", "VPP", "VFP"}
# prepositions after which an adverbial -o/-um form is an adjective/noun case form ('in occulto',
# 'in vanum', 'de proximo'); 'a', 'ab', 'usque' are left out ('a longe', 'a modo', 'usque modo')
_PREPOSITION_FORMS = {"in", "de", "ex", "cum", "pro", "sine", "ad", "per", "sub", "super", "propter", "ob"}


def _decide(idx: _Index, cands: Dict[int, List[Tuple[str, str]]], b: str, prev: str, nxt: str,
            initial: bool = False, prevs: Tuple[str, ...] = (), prefixes: Tuple[str, ...] = (),
            tok: str = "", nxt2: str = "", question: bool = False, nxt_tok: str = ""
            ) -> Tuple[Optional[int], float, List[str]]:
    if not cands:
        return None, 0.0, []
    # only masc. vocatives of adjectives / participles in -e ('recte', 'juste' when the adverb is missing
    # from L&S's headwords): far more likely an adverb than a vocative -> no tag
    if all(pc in _ADJ_OR_PART and e == "e" for anas in cands.values() for pc, e in anas):
        return None, 0.0, ["only an adjective/participle vocative in -e: probably an adverb missing from L&S"]
    if len(cands) == 1:
        i, anas = next(iter(cands.items()))
        return i, _single_conf(idx, i, anas[0][0]), []
    ctx = _context_rule(idx, b, prev, nxt, cands, prevs, tok=tok, nxt2=nxt2,
                        initial=initial, question=question, nxt_tok=nxt_tok)
    if ctx:
        return ctx[0], 0.85, [ctx[1]]
    fp = _FORM_PRIOR.get(b)
    if not fp and prefixes:
        for p in prefixes:
            if p in ("E:que", "E:ne", "E:ve"):
                enc = "ue" if p == "E:ve" else p[2:]
                if b.endswith(enc) and len(b) > len(enc) + 1:
                    fp = _FORM_PRIOR.get(b[:-len(enc)])
                    if fp:
                        break
    scores: Dict[int, float] = {}
    if fp:
        for i in cands:
            lem = idx.lemmas[i]
            k = lem.hb + (f"#{lem.n}" if lem.n else "")
            scores[i] = fp.get(k, fp.get(lem.hb, 0.0))
        src = "manual prior"
        if sum(scores.values()) <= 0:
            scores = {}
    if not scores:
        scores = {i: _base_prior(idx, i) * _likelihood(idx, i, anas, b) for i, anas in cands.items()}
        if any(idx.lemmas[i].proper for i in cands) and any(not idx.lemmas[i].proper for i in cands):
            boost = _PROPER_BOOST if not initial else _PROPER_BOOST_INITIAL
            for i in scores:                       # a capital is evidence for the name
                if idx.lemmas[i].proper:
                    scores[i] *= boost
        # Vulgate imperatives / infinitives in -ate/-ete/-ite/-are/-ere/-ire (Laudate, Vigilate, tenere)
        # against the rare classical adverbs of the same spelling: the verb
        imp = [i for i, anas in cands.items() if any(pc.startswith("V") and pc.endswith("A") and
                                                     e in ("ate", "ete", "ite", "are", "ere", "ire") for pc, e in anas)]
        if imp:
            for i, anas in cands.items():
                if i not in imp and idx.lemmas[i].pos == "ADV":
                    scores[i] *= 0.02
        # an adverb does not follow a preposition ('in occulto', 'de proximo'): the noun/adjective
        if prev in _PREPOSITION_FORMS and b.endswith(("o", "um")):
            for i in scores:
                if idx.lemmas[i].pos == "ADV":
                    scores[i] *= 0.05
        # an explicit L&S adverb in -e ('digne', 'aperte', 'judaice', 'syriace', 'hebraice') strongly outweighs a
        # bare masculine vocative singular of its adjective/participle in lower-case prose
        if b.endswith("e") and tok[:1].islower() and any(idx.lemmas[i].pos == "ADV" for i in cands):
            for i, anas in cands.items():
                if idx.lemmas[i].pos != "ADV" and all(pc in _ADJ_OR_PART and e == "e" for pc, e in anas):
                    scores[i] *= 0.05
        src = "corpus prior"
    tot = sum(scores.values())
    best = max(scores, key=lambda k: scores[k])
    share = scores[best] / tot if tot else 0.0
    rivals = sorted((k for k in scores if k != best), key=lambda k: -scores[k])[:2]
    note = f"{src} {share:.2f} over " + ", ".join(idx.lemmas[k].key for k in rivals)
    if share < AMBIGUITY_THRESHOLD:
        return None, 0.0, [f"ambiguous ({note})"]
    return best, round(min(0.9, 0.9 * share), 3), [note]


def _single_conf(idx: _Index, i: int, pc: str) -> float:
    lem = idx.lemmas[i]
    if pc == "closed":
        return 0.97
    if pc == "tipnr":
        return 0.85
    if pc == "textname":
        return 0.75
    if lem.ls_type in ("hapax", "gloss", "foreign"):
        return 0.8
    return 0.92


def _question_flags(text: str, tokens: List[str]) -> List[bool]:
    """True for tokens whose sentence (up to the next . ? ! : ;) ends with a question mark."""
    pos_after = []
    pos = 0
    for tok in tokens:
        j = text.find(tok, pos)
        pos = (j + len(tok)) if j >= 0 else pos
        pos_after.append(pos)
    out = []
    for p in pos_after:
        m = re.search(r"[.?!:;]", text[p:])
        out.append(bool(m) and m.group(0) == "?")
    return out


# Hebrew letter names that head the stanzas of the alphabetic acrostics (Lamentations 1-4, Psalm 118 in the
# Vulgate numbering): not Latin words ('Res', 'Sin', 'He') and not the persons/places TIPNR lists ('Nun',
# 'Heth', 'Ain'); left untagged there.
_HEBREW_LETTERS = {"Aleph", "Beth", "Ghimel", "Gimel", "Daleth", "He", "Vau", "Zain", "Heth", "Teth", "Jod", "Joth",
                   "Caph", "Lamed", "Mem", "Nun", "Samech", "Ain", "Phe", "Sade", "Coph", "Res", "Sin", "Schin",
                   "Thau", "Tau"}


def _is_acrostic(book_slug: str, chapter: int) -> bool:
    s = (book_slug or "").lower()
    try:
        ch = int(chapter)
    except (TypeError, ValueError):
        return False
    return (s.startswith("lam") and 1 <= ch <= 4) or (s in ("psalms", "psalm", "ps", "psalmi") and ch == 118)


def _verb_only_capital(idx: _Index, cands: Dict[int, List[Tuple[str, str]]], b: str, tok: str, ini: bool) -> bool:
    """A capitalised mid-sentence form, never written in lower case, whose only readings are finite verb forms of
    verbs never attested in lower case in the Studio text ('de Bete et de Beroth', not the verb beto)."""
    if not cands or ini or not tok[:1].isupper() or not _cap_attested(idx, b):
        return False
    for i, anas in cands.items():
        lem = idx.lemmas[i]
        if lem.proper or lem.pos != "V" or idx.prior_lower.get(i, 0) > 0:
            return False
        if any(not pc.startswith("V") or pc in ("V1N", "V2N", "V3IN", "VPP", "VFP") for pc, _e in anas):
            return False
    return True


def _tag_verse(tagger: _Tagger, text: str, acrostic: bool = False,
               ref: Optional[Tuple[str, int, int]] = None) -> List[TokenTag]:
    idx = tagger.idx
    toks = tokenize_verse(text, LANG)
    flags = _sentence_initial_flags(text, toks)
    quest = _question_flags(text, toks)
    bares = [_b(t) for t in toks]
    letters = set()
    if acrostic:
        for k, tok in enumerate(toks):
            if tok in _HEBREW_LETTERS and (k + 1 == len(toks) or toks[k + 1][:1].isupper()):
                letters.add(k)
                if k + 1 < len(toks):
                    flags[k + 1] = True          # the stanza's first word follows the letter name
    out: List[TokenTag] = []
    for k, (tok, ini) in enumerate(zip(toks, flags)):
        b = bares[k]
        if k in letters:
            out.append(TokenTag(index=k + 1, surface=tok, lemma_key=None, method="untagged", confidence=0.0,
                                prefixes=(), is_content=False,
                                notes=["Hebrew letter name heading an acrostic stanza (not a Latin word)"]))
            continue
        prev = bares[k - 1] if k > 0 else ""
        nxt = bares[k + 1] if k + 1 < len(bares) else ""
        nxt2 = bares[k + 2] if k + 2 < len(bares) else ""
        prevs = tuple(bares[max(0, k - 3):k])
        cands, prefixes, notes = tagger.analyse_token(tok, ini)
        group = _choose_group(idx, cands, b, tok, ini)
        if not group and tok[:1].isupper() and k not in letters:
            j = _tipnr_name_here(idx, tok, ini, ref)
            if j is not None:
                group = {j: [("textname", "")]}
                notes = list(notes) + ["name attested in the Saints Latin text; a TIPNR individual of that name "
                                       "stands in this verse"]
        if _verb_only_capital(idx, group, b, tok, ini):
            names = _names_from_text(idx, b)
            if not names:
                tj = _tipnr_name_here(idx, tok, ini, ref)
                if tj is not None:
                    names = [tj]
            if names:
                group = {j: [("textname", "")] for j in names}
                notes = list(notes) + ["name attested in the Saints Latin text (capitalised mid-sentence; the "
                                       "verb reading is never attested in lower case)"]
            else:
                out.append(TokenTag(index=k + 1, surface=tok, lemma_key=None, method="untagged", confidence=0.0,
                                    prefixes=prefixes, is_content=True,
                                    notes=list(notes) + ["capitalised mid-sentence and never in lower case: "
                                                         "probably a name, not the verb form"]))
                continue
        cf = _context_form(idx, b, tok, prev, nxt, nxt2, prevs, group, ini, quest[k],
                           toks[k - 1] if k > 0 else "") if group else None
        if cf is not None:
            i, note = cf
            conf, more = (0.85, [note]) if i is not None else (0.0, [note])
        else:
            i, conf, more = _decide(idx, group, b, prev, nxt, ini, prevs, prefixes=prefixes,
                                    tok=tok, nxt2=nxt2, question=quest[k],
                                    nxt_tok=toks[k + 1] if k + 1 < len(toks) else "")
        notes = list(notes) + more
        if i is None:
            out.append(TokenTag(index=k + 1, surface=tok, lemma_key=None, method="untagged", confidence=0.0,
                                prefixes=prefixes, is_content=True, notes=notes))
            continue
        lem = idx.lemmas[i]
        if any(n.startswith("variant") for n in notes):
            conf *= 0.9
        if prefixes:
            conf *= 0.97
        pcs = {pc for pc, _e in group.get(i, [])}
        # 'gold-form': an exact TIPNR name; everything else comes from the L&S-driven paradigms,
        # the closed lists, or names attested in the Studio text
        method = "gold-form" if pcs and pcs <= {"tipnr"} else "paradigm"
        # parsing code of the analyses of the chosen lemma (computed after the choice; section 10)
        morph = _morph_for(idx, i, group.get(i, []), b, prefixes)
        out.append(TokenTag(index=k + 1, surface=tok, lemma_key=lem.key, method=method,
                            confidence=round(conf, 3), prefixes=prefixes,
                            is_content=not (lem.noncontent or lem.hb == "sum"), notes=notes, morph=morph))
    return out


def tag_chapter(book_slug: str, chapter: int, verses: Dict[int, str]) -> Dict[int, List[TokenTag]]:
    """One TokenTag per token of ``tokenize_verse(text, 'lat')`` for every verse given.
    ``book_slug``/``chapter`` (Studio Latin numbering) are used only to recognise the alphabetic acrostics
    (Lamentations 1-4, Psalm 118), whose Hebrew letter names stay untagged."""
    tagger = _get_tagger()
    acro = _is_acrostic(book_slug, chapter)
    return {int(v): _tag_verse(tagger, text or "", acro, (book_slug, int(chapter), int(v)))
            for v, text in verses.items()}


def tag_all(conn: Optional[sqlite3.Connection] = None) -> Iterator[Tuple[str, int, Dict[int, List[TokenTag]]]]:
    """Yield ``(book_slug, chapter, {verse: [TokenTag]})`` for every Latin chapter of the Studio DB.
    ``conn`` should be a read-only connection; when None the Studio DB is opened read-only."""
    own = conn is None
    if conn is None:
        conn = _connect_ro(db_path())
        if conn is None:
            return
    try:
        _ensure_priors(conn)
        tagger = _get_tagger()
        cur_key = None
        verses: Dict[int, str] = {}
        for book, ch, v, text in _studio_latin_rows(conn):
            if (book, ch) != cur_key:
                if cur_key is not None:
                    acro = _is_acrostic(*cur_key)
                    yield cur_key[0], cur_key[1], {vv: _tag_verse(tagger, t, acro, (cur_key[0], cur_key[1], vv))
                                                   for vv, t in verses.items()}
                cur_key = (book, ch)
                verses = {}
            verses[v] = text
        if cur_key is not None:
            acro = _is_acrostic(*cur_key)
            yield cur_key[0], cur_key[1], {vv: _tag_verse(tagger, t, acro, (cur_key[0], cur_key[1], vv))
                                           for vv, t in verses.items()}
    finally:
        if own:
            conn.close()


# ---------------------------------------------------------------------------
# 10.  Parsing codes (TokenTag.morph) and their legend (18 Nov 2026)
# ---------------------------------------------------------------------------
# A tagged token carries morph = 'L:' + paradigm class + '|' + ending of the analysis that produced the chosen
# lemma ('L:N1|am', 'L:V3A|unt').  It is a class and an ending, NOT one paradigm cell: 'L:N1|ae' may be gen./dat.
# singular or nom. plural, and the tagger does not decide which.  When several analyses of the chosen lemma
# remain (legit: present 'L:V3A|it' and perfect 'L:VPF|it') their codes are sorted and joined with ','.
# The codes are computed after the lemma is chosen and never influence the choice.  Other code shapes:
#   'L:<class>|0'      the paradigm ending is empty (vocative 'fili' of filius)
#   'L:<class>|head'   the form listed as the headword (rex, corpus, felix); classes ADV, PREP, CONJ, PART, INTERJ,
#                      PRON, NUM, N, PROPN, ADJ, V, X when no paradigm was derived ('L:CONJ|head' for et)
#   'L:V3A|short'      the short imperatives dic, duc, fac (and compounds)
#   'L:closed|<form>'  a hand-listed form (sum, possum, eo, fero, volo, nolo, malo, fio, queo, memini, odi, aio,
#                      inquam and compounds; pronouns; numerals; domus; irregular comparison; forms L&S states
#                      outside the regular paradigm); its cells come from the hand tables below
#   'L:NAME|<ending>'  a name declined from a nominative attested in the Saints Latin text ('Ezechiae': -ae);
#                      'L:NAME|x' when the case could not be read off the ending
#   'L:PROPN|head'     a name in its own (TIPNR / text) form: no case is derived
# morph_legend() gives an English description of every code; describe_morph() describes a token's morph string.

_MORPH_PREFIX = "L:"
_ABBR = {"nom": "nominative", "gen": "genitive", "dat": "dative", "acc": "accusative", "abl": "ablative",
         "voc": "vocative", "loc": "locative", "sg": "singular", "pl": "plural", "masc": "masculine",
         "fem": "feminine", "neut": "neuter"}
_ABBR_RE = re.compile(r"\b(nom|gen|dat|acc|abl|voc|loc|sg|pl|masc|fem|neut)\b")


def _xc(s: str) -> str:
    """Expand the case / number / gender abbreviations of the cell tables ('nom/voc sg')."""
    return _ABBR_RE.sub(lambda m: _ABBR[m.group(1)], s)


def _ct(d: Dict[str, str]) -> Dict[str, List[str]]:
    """{ending: 'cell; cell'} -> {ending: [cell, cell]} (abbreviations expanded)."""
    return {e: [_xc(c.strip()) for c in s.split(";") if c.strip()] for e, s in d.items()}


def _cells(pairs: Iterable[Tuple[str, str]]) -> Dict[str, List[str]]:
    d: Dict[str, List[str]] = {}
    for e, c in pairs:
        lst = d.setdefault(e, [])
        c = _xc(c)
        if c not in lst:
            lst.append(c)
    return d


def _union(*lists: List[str]) -> List[str]:
    out: List[str] = []
    for lst in lists:
        for c in lst:
            if c not in out:
                out.append(c)
    return out


_PERS6 =("1st singular", "2nd singular", "3rd singular", "1st plural", "2nd plural", "3rd plural")


def _six(label: str, ends: str) -> List[Tuple[str, str]]:
    """Six person endings of one tense; a passive 2nd singular in -ris also gets its form in -re."""
    es = ends.split()
    if len(es) != 6:
        raise ValueError(f"six endings expected: {ends}")
    out = [(e, f"{label} {p}") for e, p in zip(es, _PERS6)]
    if "passive" in label and es[1].endswith("ris"):
        out.append((es[1][:-3] + "re", f"{label} 2nd singular (form in -re)"))
    return out


def _imp_act(sg: str, pl: str, fut: str, futpl: str, fut3: str) -> List[Tuple[str, str]]:
    return [(sg, "present imperative active 2nd singular"), (pl, "present imperative active 2nd plural"),
            (fut, "future imperative active 2nd/3rd singular"), (futpl, "future imperative active 2nd plural"),
            (fut3, "future imperative active 3rd plural")]


def _imp_pass(sg: str, pl: str, fut: str, fut3: str, inf: str) -> List[Tuple[str, str]]:
    return [(sg, "present imperative passive 2nd singular"), (pl, "present imperative passive 2nd plural"),
            (fut, "future imperative passive 2nd/3rd singular"), (fut3, "future imperative passive 3rd plural"),
            (inf, "present infinitive passive")]


def _perf_pairs(voice: str = " active") -> List[Tuple[str, str]]:
    """The perfect-system endings of _PERF_ENDS with their cells."""
    return (_six(f"perfect indicative{voice}", "i isti it imus istis erunt") +
            [("ere", f"perfect indicative{voice} 3rd plural (form in -ere)")] +
            _six(f"pluperfect indicative{voice}", "eram eras erat eramus eratis erant") +
            _six(f"future perfect indicative{voice}", "ero eris erit erimus eritis erint") +
            _six(f"perfect subjunctive{voice}", "erim eris erit erimus eritis erint") +
            _six(f"pluperfect subjunctive{voice}", "issem isses isset issemus issetis issent") +
            [("isse", f"perfect infinitive{voice}")])


def _sy_pairs(voice: str = " active") -> List[Tuple[str, str]]:
    """Contracted perfect forms (amasti, audisse, isti, imperarat)."""
    return ([("sti", f"perfect indicative{voice} 2nd singular (contracted)"),
             ("stis", f"perfect indicative{voice} 2nd plural (contracted)"),
             ("runt", f"perfect indicative{voice} 3rd plural (contracted)"),
             ("sse", f"perfect infinitive{voice} (contracted)")] +
            [(e, c + " (contracted)") for e, c in _six(f"pluperfect subjunctive{voice}",
                                                       "ssem sses sset ssemus ssetis ssent")] +
            [(e, c + " (contracted)") for e, c in _six(f"pluperfect indicative{voice}",
                                                       "ram ras rat ramus ratis rant")] +
            [(e, c + " (contracted)") for e, c in _six(f"future perfect indicative{voice}",
                                                       "ro ris rit rimus ritis rint")])


_A12_CELLS = _ct({"us": "nom masc sg", "a": "nom/voc fem sg; abl fem sg; nom/acc/voc neut pl",
                  "um": "acc masc sg; nom/acc/voc neut sg", "i": "gen masc/neut sg; nom/voc masc pl",
                  "ae": "gen/dat fem sg; nom/voc fem pl", "o": "dat/abl masc/neut sg", "am": "acc fem sg",
                  "os": "acc masc pl", "as": "acc fem pl", "is": "dat/abl pl", "orum": "gen masc/neut pl",
                  "arum": "gen fem pl", "e": "voc masc sg"})


def _ptc_cells(v: str) -> Dict[str, List[str]]:
    """Present participle, gerund and gerundive after the theme vowel ``v`` ('a', 'e', 'ie')."""
    return _ct({v + "ns": "present active participle nom/voc sg (all genders); present active participle acc "
                          "neut sg",
                v + "ntis": "present active participle gen sg", v + "nti": "present active participle dat/abl sg",
                v + "ntem": "present active participle acc masc/fem sg", v + "nte": "present active participle abl sg",
                v + "ntes": "present active participle nom/acc/voc masc/fem pl",
                v + "ntium": "present active participle gen pl",
                v + "ntibus": "present active participle dat/abl pl",
                v + "ntia": "present active participle nom/acc/voc neut pl",
                v + "ndi": "gerund gen; gerundive gen masc/neut sg; gerundive nom masc pl",
                v + "ndo": "gerund dat/abl; gerundive dat/abl masc/neut sg",
                v + "ndum": "gerund acc; gerundive acc masc sg; gerundive nom/acc neut sg",
                v + "ndus": "gerundive nom masc sg",
                v + "nda": "gerundive nom/abl fem sg; gerundive nom/acc neut pl",
                v + "ndae": "gerundive gen/dat fem sg; gerundive nom fem pl", v + "ndam": "gerundive acc fem sg",
                v + "ndos": "gerundive acc masc pl", v + "ndas": "gerundive acc fem pl",
                v + "ndis": "gerundive dat/abl pl", v + "ndorum": "gerundive gen masc/neut pl",
                v + "ndarum": "gerundive gen fem pl"})


# paradigm class -> ending (as in the code: '0' = no ending) -> cells.  Every (class, ending) of ENDINGS has an entry
# (tests/test_lexica_latin.py checks it).
_PARADIGM_CELLS: Dict[str, Dict[str, List[str]]] = {
    "N1": _ct({"a": "nom/voc/abl sg", "ae": "gen/dat sg; nom/voc pl", "am": "acc sg", "arum": "gen pl",
               "is": "dat/abl pl", "as": "acc pl", "abus": "dat/abl pl (form in -abus)"}),
    "N1GA": _ct({"as": "nom sg", "ae": "gen/dat sg; nom/voc pl", "am": "acc sg", "an": "acc sg (Greek form)",
                 "a": "voc/abl sg", "is": "dat/abl pl", "arum": "gen pl"}),
    "N1GE": _ct({"es": "nom sg", "ae": "gen/dat sg; nom/voc pl", "en": "acc sg (Greek form)",
                 "e": "nom sg (Greek feminines in -e); voc/abl sg", "am": "acc sg", "a": "voc/abl sg",
                 "arum": "gen pl", "is": "dat/abl pl", "as": "acc pl"}),
    "N1PL": _ct({"ae": "nom/voc pl", "arum": "gen pl", "is": "dat/abl pl", "as": "acc pl"}),
    "N2": _ct({"us": "nom sg", "i": "gen sg; nom/voc pl", "o": "dat/abl sg", "um": "acc sg", "e": "voc sg",
               "orum": "gen pl", "is": "dat/abl pl", "os": "acc pl"}),
    "N2IUS": _ct({"us": "nom sg", "i": "gen sg; nom/voc pl", "o": "dat/abl sg", "um": "acc sg",
                  "0": "voc sg (fili); gen sg (contracted form)", "orum": "gen pl", "is": "dat/abl pl",
                  "os": "acc pl"}),
    "N2R": _ct({"i": "gen sg; nom/voc pl", "o": "dat/abl sg", "um": "acc sg", "orum": "gen pl", "is": "dat/abl pl",
                "os": "acc pl"}),
    "N2N": _ct({"um": "nom/acc/voc sg", "i": "gen sg", "o": "dat/abl sg", "a": "nom/acc/voc pl", "orum": "gen pl",
                "is": "dat/abl pl"}),
    "N2PLM": _ct({"i": "nom/voc pl", "orum": "gen pl", "is": "dat/abl pl", "os": "acc pl"}),
    "N2PLN": _ct({"a": "nom/acc/voc pl", "orum": "gen pl", "is": "dat/abl pl"}),
    "N3": _ct({"is": "gen sg", "i": "dat sg; abl sg (some nouns)", "em": "acc sg", "e": "abl sg",
               "es": "nom/voc/acc pl", "um": "gen pl", "ibus": "dat/abl pl"}),
    "N3I": _ct({"is": "gen sg; acc pl (i-stem form in -is)", "i": "dat sg; abl sg (some nouns)", "em": "acc sg",
                "e": "abl sg", "es": "nom/voc/acc pl; nom/voc sg (nouns in -es)", "ium": "gen pl",
                "ibus": "dat/abl pl"}),
    "N3IM": _ct({"is": "nom/voc sg (nouns in -is); gen sg; acc pl (i-stem form in -is)",
                 "i": "dat sg; abl sg (form in -i)", "em": "acc sg", "im": "acc sg (form in -im)",
                 "in": "acc sg (Greek form)", "e": "abl sg",
                 "es": "nom/voc/acc pl", "ium": "gen pl", "ibus": "dat/abl pl"}),
    "N3N": _ct({"is": "gen sg", "i": "dat sg", "e": "abl sg", "a": "nom/acc/voc pl", "um": "gen pl",
                "ibus": "dat/abl pl"}),
    "N3NI": _ct({"is": "gen sg", "i": "dat/abl sg", "ia": "nom/acc/voc pl", "ium": "gen pl", "ibus": "dat/abl pl"}),
    "N3PL": _ct({"es": "nom/voc/acc pl", "um": "gen pl", "ium": "gen pl", "ibus": "dat/abl pl"}),
    "N3PLN": _ct({"a": "nom/acc/voc pl", "ia": "nom/acc/voc pl", "um": "gen pl", "ium": "gen pl",
                  "ibus": "dat/abl pl"}),
    "N4": _ct({"us": "nom/voc sg; gen sg; nom/voc/acc pl", "ui": "dat sg",
               "u": "abl sg; dat sg (form in -u); gen/dat/voc sg of Jesus (Jesu)", "um": "acc sg",
               "uum": "gen pl", "ibus": "dat/abl pl", "ubus": "dat/abl pl (form in -ubus)"}),
    "N4N": _ct({"u": "nom/acc/voc/dat/abl sg", "us": "gen sg", "ua": "nom/acc/voc pl", "uum": "gen pl",
                "ibus": "dat/abl pl"}),
    "N5": _ct({"es": "nom/voc sg; nom/voc/acc pl", "ei": "gen/dat sg", "em": "acc sg", "e": "abl sg",
               "erum": "gen pl", "ebus": "dat/abl pl"}),
    "A12": dict(_A12_CELLS),
    "A12R": {e: c for e, c in _A12_CELLS.items() if e not in ("us", "e")},
    "A12PL": _ct({"i": "nom/voc masc pl", "ae": "nom/voc fem pl", "a": "nom/acc/voc neut pl",
                  "orum": "gen masc/neut pl", "arum": "gen fem pl", "is": "dat/abl pl", "os": "acc masc pl",
                  "as": "acc fem pl"}),
    "A3": _ct({"is": "nom/voc masc/fem sg; gen sg; acc masc/fem pl (form in -is)", "e": "nom/acc/voc neut sg",
               "i": "dat/abl sg", "em": "acc masc/fem sg", "es": "nom/acc/voc masc/fem pl",
               "ia": "nom/acc/voc neut pl", "ium": "gen pl", "ibus": "dat/abl pl"}),
    "A31I": _ct({"is": "gen sg; acc masc/fem pl (form in -is)", "i": "dat/abl sg", "em": "acc masc/fem sg",
                 "e": "abl sg", "es": "nom/acc/voc masc/fem pl", "ia": "nom/acc/voc neut pl", "ium": "gen pl",
                 "ibus": "dat/abl pl"}),
    "A31C": _ct({"is": "gen sg", "i": "dat sg; abl sg (form in -i)", "em": "acc masc/fem sg", "e": "abl sg",
                 "es": "nom/acc/voc masc/fem pl", "a": "nom/acc/voc neut pl", "um": "gen pl",
                 "ibus": "dat/abl pl"}),
    "CMP": _ct({"ior": "nom/voc masc/fem sg", "ius": "nom/acc/voc neut sg (also the comparative adverb)",
                "ioris": "gen sg", "iori": "dat sg; abl sg (form in -i)", "iorem": "acc masc/fem sg",
                "iore": "abl sg", "iores": "nom/acc/voc masc/fem pl", "iora": "nom/acc/voc neut pl",
                "iorum": "gen pl", "ioribus": "dat/abl pl"}),
    "V1A": _cells(_six("present indicative active", "o as at amus atis ant") +
                  _six("imperfect indicative active", "abam abas abat abamus abatis abant") +
                  _six("future indicative active", "abo abis abit abimus abitis abunt") +
                  _six("present subjunctive active", "em es et emus etis ent") +
                  _six("imperfect subjunctive active", "arem ares aret aremus aretis arent") +
                  _imp_act("a", "ate", "ato", "atote", "anto") + [("are", "present infinitive active")]),
    "V1P": _cells(_six("present indicative passive", "or aris atur amur amini antur") +
                  _six("imperfect indicative passive", "abar abaris abatur abamur abamini abantur") +
                  _six("future indicative passive", "abor aberis abitur abimur abimini abuntur") +
                  _six("present subjunctive passive", "er eris etur emur emini entur") +
                  _six("imperfect subjunctive passive", "arer areris aretur aremur aremini arentur") +
                  _imp_pass("are", "amini", "ator", "antor", "ari")),
    "V1N": _ptc_cells("a"),
    "V2A": _cells(_six("present indicative active", "eo es et emus etis ent") +
                  _six("imperfect indicative active", "ebam ebas ebat ebamus ebatis ebant") +
                  _six("future indicative active", "ebo ebis ebit ebimus ebitis ebunt") +
                  _six("present subjunctive active", "eam eas eat eamus eatis eant") +
                  _six("imperfect subjunctive active", "erem eres eret eremus eretis erent") +
                  _imp_act("e", "ete", "eto", "etote", "ento") + [("ere", "present infinitive active")]),
    "V2P": _cells(_six("present indicative passive", "eor eris etur emur emini entur") +
                  _six("imperfect indicative passive", "ebar ebaris ebatur ebamur ebamini ebantur") +
                  _six("future indicative passive", "ebor eberis ebitur ebimur ebimini ebuntur") +
                  _six("present subjunctive passive", "ear earis eatur eamur eamini eantur") +
                  _six("imperfect subjunctive passive", "erer ereris eretur eremur eremini erentur") +
                  _imp_pass("ere", "emini", "etor", "entor", "eri")),
    "V2N": _ptc_cells("e"),
    "V3A": _cells(_six("present indicative active", "o is it imus itis unt") +
                  _six("imperfect indicative active", "ebam ebas ebat ebamus ebatis ebant") +
                  _six("future indicative active", "am es et emus etis ent") +
                  _six("present subjunctive active", "am as at amus atis ant") +
                  _six("imperfect subjunctive active", "erem eres eret eremus eretis erent") +
                  _imp_act("e", "ite", "ito", "itote", "unto") + [("ere", "present infinitive active")]),
    "V3P": _cells(_six("present indicative passive", "or eris itur imur imini untur") +
                  _six("imperfect indicative passive", "ebar ebaris ebatur ebamur ebamini ebantur") +
                  _six("future indicative passive", "ar eris etur emur emini entur") +
                  _six("present subjunctive passive", "ar aris atur amur amini antur") +
                  _six("imperfect subjunctive passive", "erer ereris eretur eremur eremini erentur") +
                  _imp_pass("ere", "imini", "itor", "untor", "i")),
    "V3IA": _cells(_six("present indicative active", "io is it imus itis iunt") +
                   _six("imperfect indicative active", "iebam iebas iebat iebamus iebatis iebant") +
                   _six("future indicative active", "iam ies iet iemus ietis ient") +
                   _six("present subjunctive active", "iam ias iat iamus iatis iant") +
                   _six("imperfect subjunctive active", "erem eres eret eremus eretis erent") +
                   _imp_act("e", "ite", "ito", "itote", "iunto") + [("ere", "present infinitive active")]),
    "V3IP": _cells(_six("present indicative passive", "ior eris itur imur imini iuntur") +
                   _six("imperfect indicative passive", "iebar iebaris iebatur iebamur iebamini iebantur") +
                   _six("future indicative passive", "iar ieris ietur iemur iemini ientur") +
                   _six("present subjunctive passive", "iar iaris iatur iamur iamini iantur") +
                   _six("imperfect subjunctive passive", "erer ereris eretur eremur eremini erentur") +
                   _imp_pass("ere", "imini", "itor", "iuntor", "i")),
    "V3IN": _ptc_cells("ie"),
    "V4A": _cells(_six("present indicative active", "io is it imus itis iunt") +
                  _six("imperfect indicative active", "iebam iebas iebat iebamus iebatis iebant") +
                  _six("future indicative active", "iam ies iet iemus ietis ient") +
                  _six("present subjunctive active", "iam ias iat iamus iatis iant") +
                  _six("imperfect subjunctive active", "irem ires iret iremus iretis irent") +
                  _imp_act("i", "ite", "ito", "itote", "iunto") + [("ire", "present infinitive active")] +
                  _six("future indicative active (old form in -ibo)", "ibo ibis ibit ibimus ibitis ibunt")),
    "V4P": _cells(_six("present indicative passive", "ior iris itur imur imini iuntur") +
                  _six("imperfect indicative passive", "iebar iebaris iebatur iebamur iebamini iebantur") +
                  _six("future indicative passive", "iar ieris ietur iemur iemini ientur") +
                  _six("present subjunctive passive", "iar iaris iatur iamur iamini iantur") +
                  _six("imperfect subjunctive passive", "irer ireris iretur iremur iremini irentur") +
                  _imp_pass("ire", "imini", "itor", "iuntor", "iri")),
    "VPF": _cells(_perf_pairs()),
    "VSY": _cells(_sy_pairs()),
    "VPP": dict({e: ["perfect participle " + c for c in cs] for e, cs in _A12_CELLS.items()},
                um=["perfect participle " + c for c in _A12_CELLS["um"]] + ["supine in -um (accusative)"],
                u=["supine in -u (ablative)"]),
    "VFP": {e: ["future active participle " + c for c in cs] for e, cs in _A12_CELLS.items()},
    "VIMP2": _ct({"et": "present indicative 3rd singular", "ebat": "imperfect indicative 3rd singular",
                  "ebit": "future indicative 3rd singular", "eat": "present subjunctive 3rd singular",
                  "eret": "imperfect subjunctive 3rd singular", "ere": "present infinitive",
                  "uit": "perfect indicative 3rd singular", "uerat": "pluperfect indicative 3rd singular",
                  "uerit": "future perfect indicative 3rd singular; perfect subjunctive 3rd singular",
                  "uisset": "pluperfect subjunctive 3rd singular", "uisse": "perfect infinitive",
                  "ent": "present indicative 3rd plural", "ebant": "imperfect indicative 3rd plural",
                  "ebunt": "future indicative 3rd plural", "eant": "present subjunctive 3rd plural",
                  "erent": "imperfect subjunctive 3rd plural", "uerunt": "perfect indicative 3rd plural",
                  "uerant": "pluperfect indicative 3rd plural",
                  "uerint": "future perfect indicative 3rd plural; perfect subjunctive 3rd plural",
                  "uissent": "pluperfect subjunctive 3rd plural"}),
    "VSUP": _ct({"um": "supine in -um (accusative)", "u": "supine in -u (ablative)"}),
}

_CLASS_DESC: Dict[str, str] = {
    "N1": "1st declension noun (-a, -ae)",
    "N1GA": "1st declension masculine noun in -as (Greek type: Satanas, Isaias)",
    "N1GE": "1st declension noun in -es / -e (Greek type)",
    "N1PL": "1st declension noun, plural only (-ae, -arum)",
    "N2": "2nd declension noun in -us / -os (-i)",
    "N2IUS": "2nd declension noun in -ius (filius, vocative fili)",
    "N2R": "2nd declension noun in -er / -ir (puer, ager, vir)",
    "N2N": "2nd declension neuter noun (-um / -on, -i)",
    "N2PLM": "2nd declension masculine noun, plural only (-i, -orum)",
    "N2PLN": "2nd declension neuter noun, plural only (-a, -orum)",
    "N3": "3rd declension noun, consonant stem",
    "N3I": "3rd declension noun, i-stem (nouns in -es; monosyllables ending in two consonants; nouns in -ns, -rs)",
    "N3IM": "3rd declension noun in -is (i-stem; accusative -em or -im)",
    "N3N": "3rd declension neuter noun, consonant stem",
    "N3NI": "3rd declension neuter noun, i-stem (-e, -al, -ar)",
    "N3PL": "3rd declension noun, plural only (-es)",
    "N3PLN": "3rd declension neuter noun, plural only (-a / -ia)",
    "N4": "4th declension noun (-us, -us)",
    "N4N": "4th declension neuter noun (-u, -us)",
    "N5": "5th declension noun (-es, -ei)",
    "A12": "1st/2nd declension adjective in -us, -a, -um (also superlatives in -issimus, -limus, -rimus)",
    "A12R": "1st/2nd declension adjective in -er (liber, pulcher)",
    "A12PL": "1st/2nd declension adjective, plural only (ducenti, -ae, -a)",
    "A3": "3rd declension adjective of two or three endings (omnis, omne; acer, acris, acre)",
    "A31I": "3rd declension adjective of one ending, i-stem (felix, ingens, potens)",
    "A31C": "3rd declension adjective of one ending, consonant stem (vetus, pauper)",
    "CMP": "comparative adjective (-ior, -ius)",
    "V1A": "1st conjugation verb, active (present system)",
    "V1P": "1st conjugation verb, passive or deponent (present system)",
    "V1N": "1st conjugation verb: present participle, gerund, gerundive",
    "V2A": "2nd conjugation verb, active (present system)",
    "V2P": "2nd conjugation verb, passive or deponent (present system)",
    "V2N": "2nd / 3rd conjugation verb: present participle, gerund, gerundive (-ens, -endus)",
    "V3A": "3rd conjugation verb, active (present system)",
    "V3P": "3rd conjugation verb, passive or deponent (present system)",
    "V3IA": "3rd conjugation verb in -io, active (present system)",
    "V3IP": "3rd conjugation verb in -io, passive or deponent (present system)",
    "V3IN": "3rd conjugation -io / 4th conjugation verb: present participle, gerund, gerundive (-iens, -iendus)",
    "V4A": "4th conjugation verb, active (present system)",
    "V4P": "4th conjugation verb, passive or deponent (present system)",
    "VPF": "perfect stem: perfect, pluperfect, future perfect (active)",
    "VSY": "perfect stem, contracted forms (amasti, audisse)",
    "VPP": "perfect participle (passive; active in sense for deponents) and supine",
    "VFP": "future active participle (-urus)",
    "VIMP2": "impersonal verb, 2nd conjugation (oportet, licet, decet)",
    "VSUP": "supine of an intransitive verb",
    "closed": "hand-listed form (irregular verbs, pronouns, numerals, domus, irregular comparison, forms Lewis & "
              "Short states outside the regular paradigm)",
    "NAME": "name declined like a Latin noun; its nominative is attested in the Saints Latin text (the case is "
            "read off the ending only)",
    "ADV": "adverb", "PREP": "preposition", "CONJ": "conjunction", "PART": "particle", "INTERJ": "interjection",
    "PRON": "pronoun or pronominal word", "NUM": "numeral", "N": "noun", "PROPN": "proper name",
    "ADJ": "adjective", "V": "verb", "X": "word",
}

# the headword form ('L:<class>|head') of each class
_HEAD_CELLS: Dict[str, str] = {
    **{c: "nom/voc sg" for c in ("N1", "N1GA", "N1GE", "N2", "N2IUS", "N2R", "N3", "N3I", "N3IM", "N4", "N5")},
    **{c: "nom/acc/voc sg" for c in ("N2N", "N3N", "N3NI", "N4N")},
    "N1PL": "nom/voc pl", "N2PLM": "nom/voc pl", "N3PL": "nom/voc pl", "N2PLN": "nom/acc/voc pl",
    "N3PLN": "nom/acc/voc pl", "A12": "nom masc sg", "A12R": "nom/voc masc sg", "A3": "nom/voc masc sg",
    "A12PL": "nom masc pl", "A31I": "nom/voc sg (all genders); acc neut sg",
    "A31C": "nom/voc sg (all genders); acc neut sg", "CMP": "nom/voc masc/fem sg",
    **{c: "present indicative active 1st singular (the dictionary form)" for c in ("V1A", "V2A", "V3A", "V3IA", "V4A")},
    **{c: "present indicative 1st singular (the dictionary form; passive or deponent)"
       for c in ("V1P", "V2P", "V3P", "V3IP", "V4P")},
    "VIMP2": "present indicative 3rd singular (the dictionary form of an impersonal verb)",
    "ADV": "not inflected", "PREP": "not inflected", "CONJ": "not inflected", "PART": "not inflected",
    "INTERJ": "not inflected", "PRON": "headword form (no paradigm derived)",
    "NUM": "headword form (indeclinable, or no paradigm derived)",
    "N": "headword form; Lewis & Short gives no declension (indeclinable, or the case is not derived)",
    "PROPN": "the name's own form; no case is derived (Hebrew names are mostly indeclinable in the Vulgate)",
    "ADJ": "headword form (no paradigm derived)", "V": "headword form (no paradigm derived)",
    "X": "a spelling Lewis & Short lists (as a headword or a cross-reference); no cell derived",
}
_NOMINAL_PREF = ("N1", "N1GA", "N1GE", "N1PL", "N2", "N2IUS", "N2R", "N2N", "N2PLM", "N2PLN", "N3", "N3I", "N3IM",
                 "N3N", "N3NI", "N3PL", "N3PLN", "N4", "N4N", "N5", "A12R", "A3", "A31I", "A31C", "A12PL", "A12",
                 "CMP")
_VERB_PREF = ("V1A", "V2A", "V3A", "V3IA", "V4A", "V1P", "V2P", "V3P", "V3IP", "V4P", "VIMP2")
_HEAD_POS = ("ADV", "PREP", "CONJ", "PART", "INTERJ", "PRON", "NUM", "N", "PROPN", "ADJ", "V", "X")
_SHORT_IMP = {"V3A": "present imperative active 2nd singular (short form: dic, duc and their compounds)",
              "V3IA": "present imperative active 2nd singular (short form: fac and its compounds)"}

# names declined from an attested nominative (_OBLIQUE): ending -> cells
_NAME_CELLS: Dict[str, List[str]] = _ct({
    "orum": "gen pl", "arum": "gen pl", "ibus": "dat/abl pl", "ae": "gen/dat sg; nom pl", "am": "acc sg",
    "an": "acc sg (Greek form)", "em": "acc sg", "en": "acc sg (Greek form)", "um": "acc sg", "im": "acc sg",
    "os": "acc pl", "is": "gen sg (3rd declension); dat/abl pl", "i": "gen sg (2nd declension); dat sg (3rd "
    "declension); nom pl", "o": "dat/abl sg", "e": "abl sg; voc sg", "a": "abl/voc sg (names in -as)",
    "u": "dat/abl sg (4th declension)", "ium": "gen pl (gentile adjectives in -ensis)",
    "x": "a declined form of the name; the case is not derived"})

# ---- hand tables of the closed lists --------------------------------------------------------------------------
_SUM_CORE = _cells(
    _six("present indicative", "sum es est sumus estis sunt") +
    _six("imperfect indicative", "eram eras erat eramus eratis erant") +
    _six("future indicative", "ero eris erit erimus eritis erunt") +
    _six("present subjunctive", "sim sis sit simus sitis sint") +
    _six("imperfect subjunctive", "essem esses esset essemus essetis essent") +
    _six("imperfect subjunctive (form forem)", "forem fores foret foremus foretis forent") +
    [("es", "present imperative 2nd singular"), ("este", "present imperative 2nd plural"),
     ("esto", "future imperative 2nd/3rd singular"), ("estote", "future imperative 2nd plural"),
     ("sunto", "future imperative 3rd plural"), ("esse", "present infinitive"), ("fore", "future infinitive")] +
    [("fu" + e, c) for e, c in _perf_pairs("")] +
    [("futur" + e, "future participle " + c) for e, cs in _A12_CELLS.items() for c in cs])
_SUM_PREFIXES = {"sum": ("",), "absum": ("ab", "a", "abs"), "adsum": ("ad", "af", "as"), "desum": ("de",),
                 "insum": ("in",), "intersum": ("inter",), "obsum": ("ob", "of"), "praesum": ("prae",),
                 "prosum": ("pro", "prod"), "subsum": ("sub",), "supersum": ("super",)}
_POSSUM_CORE = _cells(
    _six("present indicative", "possum potes potest possumus potestis possunt") +
    _six("imperfect indicative", "poteram poteras poterat poteramus poteratis poterant") +
    _six("future indicative", "potero poteris poterit poterimus poteritis poterunt") +
    _six("present subjunctive", "possim possis possit possimus possitis possint") +
    _six("imperfect subjunctive", "possem posses posset possemus possetis possent") +
    [("posse", "present infinitive")] + [("potu" + e, c) for e, c in _perf_pairs("")])
_EO_ACT_CORE = _cells(
    _six("present indicative active", "eo is it imus itis eunt") +
    _six("imperfect indicative active", "ibam ibas ibat ibamus ibatis ibant") +
    _six("future indicative active", "ibo ibis ibit ibimus ibitis ibunt") +
    [("ies", "future indicative active 2nd singular (Vulgate form)"),
     ("iet", "future indicative active 3rd singular (Vulgate form)"),
     ("iemus", "future indicative active 1st plural (Vulgate form)"),
     ("ietis", "future indicative active 2nd plural (Vulgate form)"),
     ("ient", "future indicative active 3rd plural (Vulgate form)")] +
    _six("present subjunctive active", "eam eas eat eamus eatis eant") +
    _six("imperfect subjunctive active", "irem ires iret iremus iretis irent") +
    _imp_act("i", "ite", "ito", "itote", "eunto") + [("ire", "present infinitive active")] +
    [("iens", "present active participle nom/voc sg (all genders); acc neut sg"),
     ("euntis", "present active participle gen sg"), ("eunti", "present active participle dat/abl sg"),
     ("euntem", "present active participle acc masc/fem sg"), ("eunte", "present active participle abl sg"),
     ("euntes", "present active participle nom/acc/voc masc/fem pl"),
     ("euntium", "present active participle gen pl"), ("euntibus", "present active participle dat/abl pl"),
     ("eundi", "gerund gen"), ("eundo", "gerund dat/abl"), ("eundum", "gerund acc"),
     ("itur", "present indicative passive 3rd singular (impersonal)"),
     ("ibatur", "imperfect indicative passive 3rd singular (impersonal)"),
     ("ibitur", "future indicative passive 3rd singular (impersonal)"),
     ("eatur", "present subjunctive passive 3rd singular (impersonal)"),
     ("iretur", "imperfect subjunctive passive 3rd singular (impersonal)"),
     ("itum", "supine in -um")] +
    [("iu" + e, c) for e, c in _perf_pairs()] + [("i" + e, c) for e, c in _perf_pairs()] +
    [("i" + e, c) for e, c in _sy_pairs()] +
    [("itur" + e, "future active participle " + c) for e, cs in _A12_CELLS.items() for c in cs])
_EO_PASS_CORE = _cells(
    _six("present indicative passive", "eor iris itur imur imini euntur") +
    [("ibar", "imperfect indicative passive 1st singular"), ("ibatur", "imperfect indicative passive 3rd singular"),
     ("ibantur", "imperfect indicative passive 3rd plural"), ("ibor", "future indicative passive 1st singular"),
     ("ibitur", "future indicative passive 3rd singular"), ("ibuntur", "future indicative passive 3rd plural"),
     ("ear", "present subjunctive passive 1st singular"), ("eatur", "present subjunctive passive 3rd singular"),
     ("eantur", "present subjunctive passive 3rd plural"), ("irer", "imperfect subjunctive passive 1st singular"),
     ("iretur", "imperfect subjunctive passive 3rd singular"),
     ("irentur", "imperfect subjunctive passive 3rd plural"), ("iri", "present infinitive passive")] +
    [("it" + e, "perfect passive participle " + c) for e, cs in _A12_CELLS.items() for c in cs])
_FERO_CORE = _cells(
    _six("present indicative active", "fero fers fert ferimus fertis ferunt") +
    _six("imperfect indicative active", "ferebam ferebas ferebat ferebamus ferebatis ferebant") +
    _six("future indicative active", "feram feres feret feremus feretis ferent") +
    _six("present subjunctive active", "feram feras ferat feramus feratis ferant") +
    _six("imperfect subjunctive active", "ferrem ferres ferret ferremus ferretis ferrent") +
    _imp_act("fer", "ferte", "ferto", "fertote", "ferunto") + [("ferre", "present infinitive active")] +
    [("fer" + e, c) for e, cs in _ptc_cells("e").items() for c in cs] +
    _six("present indicative passive", "feror ferris fertur ferimur ferimini feruntur") +
    _six("imperfect indicative passive", "ferebar ferebaris ferebatur ferebamur ferebamini ferebantur") +
    _six("future indicative passive", "ferar fereris feretur feremur feremini ferentur") +
    _six("present subjunctive passive", "ferar feraris feratur feramur feramini ferantur") +
    _six("imperfect subjunctive passive", "ferrer ferreris ferretur ferremur ferremini ferrentur") +
    [("ferri", "present infinitive passive")] +
    [("tul" + e, c) for e, c in _perf_pairs()] +
    [("lat" + e, "perfect passive participle " + c) for e, cs in _A12_CELLS.items() for c in cs] +
    [("latur" + e, "future active participle " + c) for e, cs in _A12_CELLS.items() for c in cs] +
    [("latum", "supine in -um (accusative)"), ("latu", "supine in -u (ablative)")])
_VOLO_CORE = _cells(
    _six("present indicative", "uolo uis uult uolumus uultis uolunt") +
    [("uolt", "present indicative 3rd singular (old form)")] +
    _six("imperfect indicative", "uolebam uolebas uolebat uolebamus uolebatis uolebant") +
    _six("future indicative", "uolam uoles uolet uolemus uoletis uolent") +
    _six("present subjunctive", "uelim uelis uelit uelimus uelitis uelint") +
    _six("imperfect subjunctive", "uellem uelles uellet uellemus uelletis uellent") +
    [("uelle", "present infinitive")] +
    [("uol" + e, c) for e, cs in _ptc_cells("e").items() if "participle" in cs[0] for c in cs] +
    [("uolu" + e, c) for e, c in _perf_pairs("")])
_NOLO_CORE = _cells(
    [("nolo", "present indicative 1st singular"), ("nolumus", "present indicative 1st plural"),
     ("nolunt", "present indicative 3rd plural")] +
    _six("imperfect indicative", "nolebam nolebas nolebat nolebamus nolebatis nolebant") +
    _six("future indicative", "nolam noles nolet nolemus noletis nolent") +
    _six("present subjunctive", "nolim nolis nolit nolimus nolitis nolint") +
    _six("imperfect subjunctive", "nollem nolles nollet nollemus nolletis nollent") +
    [("noli", "present imperative 2nd singular"), ("nolite", "present imperative 2nd plural"),
     ("nolito", "future imperative 2nd/3rd singular"), ("nolitote", "future imperative 2nd plural"),
     ("nolle", "present infinitive")] +
    [("nol" + e, c) for e, cs in _ptc_cells("e").items() if "participle" in cs[0] for c in cs] +
    [("nolu" + e, c) for e, c in _perf_pairs("")])
_MALO_CORE = _cells(
    _six("present indicative", "malo mauis mauult malumus mauultis malunt") +
    [("malebam", "imperfect indicative 1st singular"), ("malebat", "imperfect indicative 3rd singular"),
     ("malam", "future indicative 1st singular"), ("males", "future indicative 2nd singular"),
     ("malet", "future indicative 3rd singular")] +
    _six("present subjunctive", "malim malis malit malimus malitis malint") +
    [("mallem", "imperfect subjunctive 1st singular"), ("malles", "imperfect subjunctive 2nd singular"),
     ("mallet", "imperfect subjunctive 3rd singular"), ("mallent", "imperfect subjunctive 3rd plural"),
     ("malle", "present infinitive")] +
    [("malu" + e, c) for e, c in _perf_pairs("")])
_FIO_CORE = _cells(
    _six("present indicative", "fio fis fit fimus fitis fiunt") +
    _six("imperfect indicative", "fiebam fiebas fiebat fiebamus fiebatis fiebant") +
    _six("future indicative", "fiam fies fiet fiemus fietis fient") +
    _six("present subjunctive", "fiam fias fiat fiamus fiatis fiant") +
    _six("imperfect subjunctive", "fierem fieres fieret fieremus fieretis fierent") +
    [("fieri", "present infinitive"), ("fite", "present imperative 2nd plural")])
_MEMINI_CORE = _cells([("memin" + e, c + " (present in sense)") for e, c in _perf_pairs("")] +
                      [("memento", "future imperative 2nd singular"), ("mementote", "future imperative 2nd plural")])
_ODI_CORE = _cells([("od" + e, c + " (present in sense)") for e, c in _perf_pairs("")] +
                   [("odiu" + e, c + " (Vulgate perfect)") for e, c in _perf_pairs("")] +
                   [("odiet", "future indicative active 3rd singular (Vulgate form)"),
                    ("odietur", "future indicative passive 3rd singular (Vulgate form)"),
                    ("odient", "future indicative active 3rd plural (Vulgate form)")] +
                   [("osur" + e, "future active participle " + c) for e, cs in _A12_CELLS.items() for c in cs] +
                   [("od" + e, c) for e, cs in _ptc_cells("ie").items() if "participle" in cs[0] for c in cs])
_AIO_CORE = _cells(
    [("aio", "present indicative 1st singular"), ("ais", "present indicative 2nd singular"),
     ("ait", "present indicative 3rd singular; perfect indicative 3rd singular"),
     ("aiunt", "present indicative 3rd plural")] +
    _six("imperfect indicative", "aiebam aiebas aiebat aiebamus aiebatis aiebant") +
    [("aias", "present subjunctive 2nd singular"), ("aiat", "present subjunctive 3rd singular"),
     ("aiant", "present subjunctive 3rd plural"),
     ("aiens", "present active participle nom/voc sg (all genders); acc neut sg"),
     ("aientes", "present active participle nom/acc/voc masc/fem pl")])
_INQUAM_CORE = _cells(
    _six("present indicative", "inquam inquis inquit inquimus inquitis inquiunt") +
    [("inquit", "perfect indicative 3rd singular"), ("inquiebat", "imperfect indicative 3rd singular"),
     ("inquies", "future indicative 2nd singular"), ("inquiet", "future indicative 3rd singular"),
     ("inquito", "future imperative 2nd/3rd singular"),
     ("inquiens", "present active participle nom/voc sg (all genders)")])
_VERB_CORES: Dict[str, Tuple[Dict[str, List[str]], Tuple[str, ...]]] = {
    **{hb: (_SUM_CORE, pre) for hb, pre in _SUM_PREFIXES.items()},
    "possum": (_POSSUM_CORE, ("",)), "eo": (_EO_ACT_CORE, ("",)), "fero": (_FERO_CORE, ("",)),
    "uolo": (_VOLO_CORE, ("",)), "nolo": (_NOLO_CORE, ("",)), "malo": (_MALO_CORE, ("",)),
    "fio": (_FIO_CORE, ("",)), "queo": (_EO_ACT_CORE, ("qu",)), "nequeo": (_EO_ACT_CORE, ("nequ",)),
    "memini": (_MEMINI_CORE, ("",)), "odi": (_ODI_CORE, ("",)), "aio": (_AIO_CORE, ("",)),
    "inquam": (_INQUAM_CORE, ("",)),
}
_EO_TRANS_CORE = {f: _union(_EO_ACT_CORE.get(f, []), _EO_PASS_CORE.get(f, []))
                  for f in list(_EO_ACT_CORE) + [f for f in _EO_PASS_CORE if f not in _EO_ACT_CORE]}
for _hb, _pre, _trans in _EO_COMPOUNDS:      # transitive compounds also have the passive (adeo, transeo)
    _VERB_CORES[_hb] = (_EO_TRANS_CORE if _trans else _EO_ACT_CORE, (_pre,))
for _hb, _pres, _perfs, _sups in _FERO_COMPOUNDS:
    _VERB_CORES[_hb] = (_FERO_CORE, tuple(dict.fromkeys(_pres + _perfs + _sups)))

_PRON_CELLS: Dict[str, Dict[str, List[str]]] = {
    "ego": _ct({"ego": "nom sg", "mei": "gen sg", "mihi": "dat sg", "mi": "dat sg", "me": "acc/abl sg"}),
    "tu": _ct({"tu": "nom/voc sg", "tui": "gen sg", "tibi": "dat sg", "te": "acc/abl sg"}),
    "nos": _ct({"nos": "nom/acc pl", "nostri": "gen pl (objective)", "nostrum": "gen pl (partitive)",
                "nobis": "dat/abl pl"}),
    "uos": _ct({"uos": "nom/voc/acc pl", "uestri": "gen pl (objective)", "uestrum": "gen pl (partitive)",
                "uobis": "dat/abl pl"}),
    "sui": _ct({"sui": "gen (sg or pl)", "sibi": "dat (sg or pl)", "se": "acc/abl (sg or pl)",
                "sese": "acc/abl (sg or pl)"}),
    "is": _ct({"is": "nom masc sg", "ea": "nom fem sg; abl fem sg; nom/acc neut pl", "id": "nom/acc neut sg",
               "eius": "gen sg", "ei": "dat sg; nom masc pl", "eum": "acc masc sg", "eam": "acc fem sg",
               "eo": "abl masc/neut sg", "ii": "nom masc pl", "eae": "nom fem pl", "eorum": "gen masc/neut pl",
               "earum": "gen fem pl", "eis": "dat/abl pl", "iis": "dat/abl pl", "eos": "acc masc pl",
               "eas": "acc fem pl"}),
    "hic": _ct({"hic": "nom masc sg", "haec": "nom fem sg; nom fem pl; nom/acc neut pl",
                "hoc": "nom/acc neut sg; abl masc/neut sg", "huius": "gen sg", "huic": "dat sg",
                "hunc": "acc masc sg", "hanc": "acc fem sg", "hac": "abl fem sg", "hi": "nom masc pl",
                "hae": "nom fem pl", "horum": "gen masc/neut pl", "harum": "gen fem pl", "his": "dat/abl pl",
                "hos": "acc masc pl", "has": "acc fem pl"}),
    "idem": _ct({"idem": "nom masc sg; nom/acc neut sg", "eadem": "nom fem sg; abl fem sg; nom/acc neut pl",
                 "eiusdem": "gen sg", "eidem": "dat sg; nom masc pl", "eundem": "acc masc sg",
                 "eumdem": "acc masc sg", "eandem": "acc fem sg", "eamdem": "acc fem sg",
                 "eodem": "abl masc/neut sg", "iidem": "nom masc pl", "eaedem": "nom fem pl",
                 "eorundem": "gen masc/neut pl", "eorumdem": "gen masc/neut pl", "earundem": "gen fem pl",
                 "earumdem": "gen fem pl", "eisdem": "dat/abl pl", "iisdem": "dat/abl pl", "eosdem": "acc masc pl",
                 "easdem": "acc fem pl"}),
    "qui": _ct({"qui": "nom masc sg; nom masc pl", "quae": "nom fem sg; nom fem pl; nom/acc neut pl",
                "quod": "nom/acc neut sg", "cuius": "gen sg", "cui": "dat sg", "quem": "acc masc sg",
                "quam": "acc fem sg", "quo": "abl masc/neut sg", "qua": "abl fem sg", "quorum": "gen masc/neut pl",
                "quarum": "gen fem pl", "quibus": "dat/abl pl", "quos": "acc masc pl", "quas": "acc fem pl"}),
    "quis": _ct({"quis": "nom masc/fem sg", "quid": "nom/acc neut sg", "cuius": "gen sg", "cui": "dat sg",
                 "quem": "acc masc/fem sg", "quo": "abl masc/neut sg", "quibus": "dat/abl pl"}),
    "nemo": _ct({"nemo": "nom sg", "neminis": "gen sg", "nemini": "dat sg", "neminem": "acc sg",
                 "nemine": "abl sg"}),
    "nihil": _ct({"nihil": "nom/acc sg", "nil": "nom/acc sg", "nihilum": "nom/acc sg", "nihili": "gen sg",
                  "nihilo": "abl sg; dat sg"}),
    "duo": _ct({"duo": "nom/acc masc/neut", "duae": "nom fem", "duorum": "gen masc/neut", "duarum": "gen fem",
                "duobus": "dat/abl masc/neut", "duabus": "dat/abl fem", "duos": "acc masc", "duas": "acc fem"}),
    "ambo": _ct({"ambo": "nom/acc masc/neut", "ambae": "nom fem", "amborum": "gen masc/neut", "ambarum": "gen fem",
                 "ambobus": "dat/abl masc/neut", "ambabus": "dat/abl fem", "ambos": "acc masc", "ambas": "acc fem"}),
    "tres": _ct({"tres": "nom/acc masc/fem", "tria": "nom/acc neut", "trium": "gen", "tribus": "dat/abl"}),
    "mille": _ct({"mille": "not declined in the singular", "milia": "nom/acc pl", "millia": "nom/acc pl",
                  "milium": "gen pl", "millium": "gen pl", "milibus": "dat/abl pl", "millibus": "dat/abl pl"}),
    "domus": _ct({"domus": "nom/voc sg; gen sg; nom/voc/acc pl", "domui": "dat sg", "domum": "acc sg",
                  "domo": "abl sg", "domi": "loc sg (at home); gen sg", "domorum": "gen pl", "domuum": "gen pl",
                  "domibus": "dat/abl pl", "domos": "acc pl"}),
    "unusquisque": _ct({"unusquisque": "nom masc sg", "unaquaeque": "nom fem sg", "unumquodque": "nom/acc neut sg",
                        "unumquidque": "nom/acc neut sg", "uniuscuiusque": "gen sg", "unicuique": "dat sg",
                        "unumquemque": "acc masc sg", "unamquamque": "acc fem sg", "unoquoque": "abl masc/neut sg",
                        "unaquaque": "abl fem sg"}),
    "quisquis": _ct({"quisquis": "nom masc sg", "quidquid": "nom/acc neut sg", "quicquid": "nom/acc neut sg",
                     "quoquo": "abl masc/neut sg", "cuicui": "dat sg"}),
    "meus": _ct({"mi": "voc masc sg"}),
}
# pronominal declension (gen. -ius, dat. -i): lemma -> stem; the nominative masc. sing. is the headword
_PRONOMINAL = {"ille": "ill", "iste": "ist", "ipse": "ips", "alius": "ali", "alter": "alter", "alteruter": "alterutr",
               "uter": "utr", "neuter": "neutr", "nullus": "null", "ullus": "ull", "solus": "sol", "totus": "tot",
               "unus": "un", "uterque": "utr"}
_PRONOMINAL_ENDS = _ct({"a": "nom fem sg; abl fem sg; nom/acc neut pl", "ud": "nom/acc neut sg",
                        "ius": "gen sg", "i": "dat sg; nom masc pl", "am": "acc fem sg", "o": "abl masc/neut sg",
                        "ae": "nom fem pl", "orum": "gen masc/neut pl", "arum": "gen fem pl", "is": "dat/abl pl",
                        "os": "acc masc pl", "as": "acc fem pl"})
# indefinite and relative compounds of qui / quis: lemma -> (prefix, suffixes)
_QUI_COMPOUNDS = {"aliquis": ("ali", ("",)), "quidam": ("", ("dam",)), "quisque": ("", ("que",)),
                  "quisquam": ("", ("quam",)), "quispiam": ("", ("piam",)), "quilibet": ("", ("libet",)),
                  "quiuis": ("", ("uis", "vis")), "quicumque": ("", ("cumque", "cunque"))}
_QUI_ANY = _ct({"quis": "nom masc/fem sg", "qui": "nom masc sg; nom masc pl",
                "quae": "nom fem sg; nom fem pl; nom/acc neut pl", "quod": "nom/acc neut sg (adjectival)",
                "quid": "nom/acc neut sg (substantival)", "cuius": "gen sg", "cui": "dat sg", "quem": "acc masc sg",
                "quam": "acc fem sg", "quo": "abl masc/neut sg", "qua": "abl fem sg", "quorum": "gen masc/neut pl",
                "quarum": "gen fem pl", "quibus": "dat/abl pl", "quos": "acc masc pl", "quas": "acc fem pl"})
# irregular forms that L&S states outside the regular paradigm (_EXTRA_FORMS, _NAME_FORMS): lemma -> form -> cells
_EXTRA_CELLS: Dict[str, Dict[str, List[str]]] = {
    "locus": _ct({"loca": "nom/acc/voc pl (neuter plural form)"}),
    "deus": _ct({"dii": "nom/voc pl", "diis": "dat/abl pl"}),
    "requies": _ct({"requiem": "acc sg (5th declension form)", "requie": "abl sg (5th declension form)",
                    "requiei": "gen/dat sg (5th declension form)"}),
    **{_b(h): _ct({_b(f): "gen pl (form in -um)"}) for h, f in (("panis", "panum"), ("canis", "canum"),
                                                                ("volucris", "volucrum"),
                                                                ("sedes", "sedum"), ("vates", "vatum"),
                                                                ("apis", "apum"), ("mensis", "mensum"),
                                                                ("senex", "senum"), ("innocens", "innocentum"),
                                                                ("parens", "parentum"), ("sapiens", "sapientum"))},
    "iuuenis": {**_ct({"iuuenum": "gen pl (form in -um)"}),
                **{"iun" + e: ["comparative " + c for c in cs]
                   for e, cs in _PARADIGM_CELLS["CMP"].items()}},
    "os": _ct({"ossium": "gen pl"}),
    "fimbriae": _ct({"fimbria": "nom/voc/abl sg (Vulgate singular)", "fimbriae": "gen/dat sg; nom/voc pl",
                     "fimbriam": "acc sg (Vulgate singular)"}),
    "angustiae": _ct({"angustia": "nom/voc/abl sg (Vulgate singular)", "angustiae": "gen/dat sg; nom/voc pl",
                      "angustiam": "acc sg (Vulgate singular)"}),
    "topazos": _ct({"topazius": "nom sg (2nd decl. variant)", "topazii": "gen sg; nom pl",
                    "topazio": "dat/abl sg", "topazium": "acc sg"}),
    "cinifes": _ct({"sciniphes": "nom/voc/acc pl (Vulgate spelling)"}),
    "aether": _ct({"aethera": "acc sg (Greek form)"}),
    "uendo": _ct({"uenundatus": "perf pass part nom masc sg (uncontracted venundo)",
                  "uenundata": "perf pass part nom/abl fem sg; nom/acc neut pl",
                  "uenundatum": "perf pass part acc masc sg; nom/acc neut sg",
                  "uenundati": "perf pass part gen masc/neut sg; nom masc pl",
                  "uenundatae": "perf pass part gen/dat fem sg; nom fem pl",
                  "uenundatos": "perf pass part acc masc pl", "uenundatas": "perf pass part acc fem pl",
                  "uenundatis": "perf pass part dat/abl pl", "uenundato": "perf pass part dat/abl masc/neut sg",
                  "uenundari": "pres inf pass", "uenundabitur": "fut ind pass 3 sg",
                  "uenundabuntur": "fut ind pass 3 pl", "uenundedit": "perf ind act 3 sg",
                  "uenundederunt": "perf ind act 3 pl"}),
    "sycaminus": _ct({"sycomorus": "nom sg (Vulgate spelling)", "sycomori": "gen sg; nom pl",
                      "sycomoro": "dat/abl sg", "sycomorum": "acc sg", "sycomoros": "acc pl",
                      "sycomoris": "dat/abl pl"}),
    "murra": _ct({"myrrha": "nom/voc/abl sg (Vulgate spelling)", "myrrhae": "gen/dat sg; nom pl",
                  "myrrham": "acc sg", "myrrhis": "dat/abl pl"}),
    "paterfamilias": _ct({"paterfamilias": "nom/voc sg", "patrisfamilias": "gen sg", "patrifamilias": "dat sg",
                          "patremfamilias": "acc sg", "patrefamilias": "abl sg", "patresfamilias": "nom/acc pl"}),
    "ecstasis": _ct({"extasis": "nom/gen sg (Vulgate spelling)", "extasi": "dat/abl sg", "extasim": "acc sg",
                     "extasin": "acc sg (Greek form)", "extaseos": "gen sg (Greek form)"}),
    "commixtio": _ct({"commistio": "nom/voc sg (Vulgate spelling)", "commistionis": "gen sg",
                      "commistioni": "dat sg", "commistionem": "acc sg", "commistione": "abl sg"}),
    "fornicarius": _ct({"fornicaria": "nom/voc/abl fem sg", "fornicariae": "gen/dat fem sg; nom fem pl",
                        "fornicariam": "acc fem sg", "fornicariarum": "gen fem pl",
                        "fornicariis": "dat/abl fem pl", "fornicarias": "acc fem pl"}),
    **{_b(k): {st + e + "decim" + e: list(_A12_CELLS[e]) for e in _ORD_ENDS} for k, st in _DOUBLE_ORDINALS.items()},
    "uicis": _ct({"uicem": "acc sg", "uice": "abl sg", "uices": "nom/acc pl", "uicibus": "dat/abl pl"}),
    "botrys": _ct({"botrus": "nom sg (Latin 2nd declension form)", "botri": "gen sg; nom pl", "botro": "dat/abl sg",
                   "botrum": "acc sg", "botros": "acc pl", "botris": "dat/abl pl", "botrorum": "gen pl"}),
    "rursus": _ct({"rursum": "adverb (other spelling), not inflected"}),
    "quattuordecim": _ct({"quatuordecim": "indeclinable numeral (other spelling)"}),
    "necesse": _ct({"necesse": "indeclinable"}), "deinceps": _ct({"deinceps": "adverb, not inflected"}),
    "sponte": _ct({"sponte": "abl sg (used adverbially: of one's own accord)"}),
    "aloe": _ct({"aloes": "gen sg (Greek form)", "aloen": "acc sg (Greek form)"}),
    "abraham": _ct({"abrahae": "gen/dat sg"}),
    "cherub": _ct({"cherubim": "pl (Hebrew plural form)", "cherubin": "pl (Hebrew plural form)"}),
    "baal": _ct({"baalim": "pl (Hebrew plural form)"}),
    "bos": _ct({"boum": "gen pl", "bobus": "dat/abl pl", "bubus": "dat/abl pl"}),
    "uis": _ct({"uim": "acc sg", "ui": "abl sg", "uires": "nom/voc/acc pl", "uirium": "gen pl",
                "uiribus": "dat/abl pl"}),
    "iusiurandum": _ct({"iusiurandum": "nom/acc sg", "iurisiurandi": "gen sg", "iusiurandi": "gen sg",
                        "iuriiurando": "dat sg", "iureiurando": "abl sg"}),
    "plus": _ct({"plura": "nom/acc neut pl", "plurium": "gen pl", "pluribus": "dat/abl pl"}),
    "baculum": _ct({"baculus": "nom sg (masc. variant)", "baculos": "acc pl (masc. variant)"}),
    "gelum": _ct({"gelu": "nom/acc/abl sg (4th decl. neut.)"}),
    "satrapes": _ct({"satrapa": "nom/abl sg (1st decl. variant)", "satrapae": "gen/dat sg; nom pl",
                     "satrapam": "acc sg", "satrapas": "acc pl", "satraparum": "gen pl", "satrapis": "dat/abl pl"}),
    "ruminor": _ct({"rumino": "pres ind act 1 sg (active variant)", "ruminat": "pres ind act 3 sg (active variant)",
                    "ruminant": "pres ind act 3 pl (active variant)", "ruminans": "pres act part nom/acc sg",
                    "ruminantis": "pres act part gen sg", "ruminantia": "pres act part nom/acc neut pl"}),
    "diligenter": _ct({"diligentius": "adverb comparative", "diligentissime": "adverb superlative"}),
    "prudens": _ct({"prudenter": "adverb"}),
    "dexter": _ct({"dexterum": "acc masc sg; nom/acc neut sg"}),
    "sartatecta": _ct({"sartatecta": "nom/acc neut pl", "sartatectis": "dat/abl neut pl",
                       "sartatectorum": "gen neut pl"}),
    "brabeum": _ct({"brauium": "nom/acc sg (Vulgate spelling)", "brauii": "gen sg", "brauio": "dat/abl sg"}),
    "quinquiens": _ct({"quinquies": "numeral adverb (Vulgate spelling), not inflected"}),
    "quotienscumque": _ct({"quotiescumque": "adverb (Vulgate spelling), not inflected"}),
    "orichalcum": _ct({"auricalco": "dat/abl sg (Vulgate spelling)", "auricalcum": "nom/acc sg (Vulgate spelling)",
                       "aurichalco": "dat/abl sg (Vulgate spelling)", "aurichalcum": "nom/acc sg (Vulgate spelling)"}),
    "lambo": _ct({"lambuerunt": "perfect indicative active 3rd plural (Vulgate form)",
                  "lambuit": "perfect indicative active 3rd singular (Vulgate form)"}),
    "cornupeta": _ct({"cornupeta": "nom/voc/abl sg", "cornupetae": "gen/dat sg; nom/voc pl",
                      "cornupetam": "acc sg", "cornupetas": "acc pl"}),
    "laxo": _ct({"laxate": "present imperative active 2nd plural"}),
}
_SUPERLATIVE_STEMS = ("optim", "pessim", "maxim", "minim", "plurim")


def _comparison_cells(form: str) -> List[str]:
    """Irregular comparison (melior, peius, optimus, minoris; deterior): comparative or superlative cells."""
    for st in _SUPERLATIVE_STEMS:
        if form.startswith(st) and form[len(st):] in _A12_CELLS:
            return ["superlative " + c for c in _A12_CELLS[form[len(st):]]]
    ends = sorted([(e, cs) for e, cs in _PARADIGM_CELLS["CMP"].items()] +
                  [(e[1:], cs) for e, cs in _PARADIGM_CELLS["CMP"].items()], key=lambda x: -len(x[0]))
    for e, cs in ends:
        if form.endswith(e) and len(form) > len(e):
            return ["comparative " + c for c in cs]
    return []


def _closed_cells(hb: str, form: str) -> List[str]:
    """Cells of a hand-listed form ``form`` (bare spelling) of the closed lemma ``hb``; [] when not derivable."""
    if hb in _VERB_CORES:
        core, prefixes = _VERB_CORES[hb]
        return _union(*[core[form[len(p):]] for p in prefixes if form.startswith(p) and form[len(p):] in core])
    if hb in _PRON_CELLS and form in _PRON_CELLS[hb]:
        return list(_PRON_CELLS[hb][form])
    if hb in _PRONOMINAL:
        base = form[:-3] if hb == "uterque" and form.endswith("que") else form
        head = "uter" if hb == "uterque" else hb
        if base == head:
            return [_xc("nom masc sg")]
        if hb == "alius" and base == "alterius":
            return [_xc("gen sg")]
        st = _PRONOMINAL[hb]
        if base.startswith(st) and base[len(st):] in _PRONOMINAL_ENDS:
            end = base[len(st):]
            return list(_PRONOMINAL_ENDS[end])
        if base == st + "um":               # ipsum, alterum, totum ...; illum, istum, alium have a neuter in -ud
            return [_xc("acc masc sg")] + ([] if hb in ("ille", "iste", "alius") else [_xc("nom/acc neut sg")])
        return []
    if hb in _QUI_COMPOUNDS:
        pre, sufs = _QUI_COMPOUNDS[hb]
        if hb == "aliquis" and form == "aliqua":
            return [_xc("nom fem sg"), _xc("abl fem sg"), _xc("nom/acc neut pl")]
        if not form.startswith(pre):
            return []
        core = form[len(pre):]
        for suf in sufs:
            if suf and core.endswith(suf):
                core = core[: -len(suf)]
                break
        if core.endswith("n") and hb == "quidam":
            core = core[:-1] + "m"          # quendam, quorundam
        if core in ("quic", "quip"):
            core = "quid"                   # quicque, quicquam, quippiam
        return list(_QUI_ANY.get(core, []))
    if hb in _IRREG_COMPARISON or hb == "deterior":
        return _comparison_cells(form)
    if hb in _EXTRA_CELLS and form in _EXTRA_CELLS[hb]:
        return list(_EXTRA_CELLS[hb][form])
    return []


def _function_heads() -> Set[str]:
    return {_FUNCTION_HEAD.get(h, h) for h in _FUNCTION_WORDS} | {"cum"}


_FUNCTION_HB: Set[str] = _function_heads()


def _lemma_codes(idx: _Index) -> Dict[int, Set[str]]:
    """lemma id (after spelling-doublet merging) -> its paradigm codes (built once per index)."""
    codes = getattr(idx, "_morph_codes", None)
    if codes is None:
        codes = defaultdict(set)
        for _st, lst in idx.stems.items():
            for k, pc in lst:
                codes[idx.canon.get(k, k)].add(pc)
        idx._morph_codes = codes
    return codes


def _head_class(idx: _Index, i: int) -> str:
    """Class of a lemma that has no paradigm of its own (or is uninflected): its part of speech."""
    lem = idx.lemmas[i]
    if lem.pos in _HEAD_POS:
        return lem.pos
    return "PROPN" if lem.proper else "X"


# nominative (dictionary-form) endings of the classes whose headword is built from stem + ending
_NOM_END = {"N1": ("a",), "N1GA": ("as",), "N1GE": ("es", "e"), "N1PL": ("ae",), "N2": ("us",), "N2IUS": ("us",),
            "N2N": ("um",), "N2PLM": ("i",), "N2PLN": ("a",), "N3I": ("es",), "N3IM": ("is",), "N4": ("us",),
            "N4N": ("u",), "N5": ("es",), "A12": ("us",), "A12PL": ("i",), "A3": ("is",), "CMP": ("ior",),
            "V1A": ("o",), "V2A": ("eo",), "V3A": ("o",), "V3IA": ("io",), "V4A": ("io",), "V1P": ("or",),
            "V2P": ("eor",), "V3P": ("or",), "V3IP": ("ior",), "V4P": ("ior",), "VIMP2": ("et",)}
# classes whose nominative is listed as an exact form (rex, corpus, puer, felix, acer); Greek -os / -on below
_EXACT_HEAD = ("N2R", "N3", "N3I", "N3IM", "N3N", "N3NI", "A12R", "A3", "A31I", "A31C")


def _head_code(idx: _Index, i: int, pc: str, f: str) -> str:
    """Code of an exact ('x') or cross-reference spelling ('alias') analysis whose listed form is ``f``."""
    lem = idx.lemmas[i]
    if lem.pos in ("ADV", "PREP", "CONJ", "PART", "INTERJ"):
        return f"L:{lem.pos}|head"          # uninflected, whatever stems an L&S cross-reference may have given
    have = _lemma_codes(idx).get(i, ())
    verbal = lem.pos == "V" or any(c.startswith("V") for c in have)
    if pc == "x" and verbal and f.endswith(("dic", "duc", "fac")):
        return "L:V3IA|short" if f.endswith("fac") else "L:V3A|short"
    if not have:
        if pc == "alias" and f != lem.hb and f[-2:] != lem.hb[-2:] and not lem.proper:
            return "L:X|head"               # an inflected form L&S lists as a cross-reference ('noctu, v. nox')
        return f"L:{_head_class(idx, i)}|head"
    order =[c for c in (_VERB_PREF + _NOMINAL_PREF if lem.pos == "V" else _NOMINAL_PREF + _VERB_PREF) if c in have]
    for c in order:                         # the dictionary form built from stem + ending: its regular code
        for e in _NOM_END.get(c, ()):
            if f.endswith(e) and len(f) > len(e):
                return f"L:{c}|{e}"
    # a nominative listed as such; a cross-reference spelling only when it ends like the headword ('vasa' under
    # vas is a plural, not the headword form)
    if pc == "x" or f == lem.hb or f[-2:] == lem.hb[-2:]:
        for c in order:
            if c in _EXACT_HEAD or (c == "N2" and f.endswith("os")) or (c == "N2N" and f.endswith("on")):
                # a name's listed nominative claims no case: the Vulgate leaves Hebrew names undeclined where
                # L&S declines them ('filii Israel', Israel, elis)
                return "L:PROPN|head" if lem.proper else f"L:{c}|head"
    if pc == "alias":                       # another spelling of an inflected form ('diversorium' of deversorius)
        best: Optional[Tuple[str, str]] = None
        for c in order:
            for e in ENDINGS.get(c, ()):
                if e and f.endswith(e) and len(f) > len(e) and (best is None or len(e) > len(best[1])):
                    best = (c, e)
        if best:
            return f"L:{best[0]}|{best[1]}"
    return "L:PROPN|head" if lem.proper else "L:X|head"


def _form_candidates(b: str, prefixes: Tuple[str, ...]) -> List[str]:
    """The bare token and the form left after the clitics the tagger split off (eumque, mecum, semetipsum)."""
    out = [b]
    for p in prefixes:
        if p.startswith("E:"):
            enc = {"ve": "ue"}.get(p[2:], p[2:])
            if b.endswith(enc) and len(b) > len(enc):
                out.append(b[: -len(enc)])
        elif p.startswith("P:"):
            if b.startswith(p[2:]) and len(b) > len(p) - 2:
                out.append(b[len(p) - 2:])
    return out


def _variant_spellings(b: str) -> List[str]:
    out = [z + b[len(a):] for a, z in _PREFIX_VARIANTS if b.startswith(a)]
    for a, z in _VARIANT_RULES:
        k = b.find(a)
        while k >= 0:
            out.append(b[:k] + z + b[k + len(a):])
            k = b.find(a, k + 1)
    return out


def _listed_form(idx: _Index, i: int, forms: List[str], tags: Tuple[str, ...]) -> Optional[str]:
    """The listed spelling (exact form with one of ``tags``) of lemma ``i`` that the token was analysed as."""
    for pool in (forms, [v for f in forms for v in _variant_spellings(f)]):
        for f in pool:
            for k, t in idx.exact.get(f, ()):
                if t in tags and idx.canon.get(k, k) == i:
                    return f
    return None


def _is_name_of(idx: _Index, n: str, i: int) -> bool:
    if n == idx.lemmas[i].hb or any(idx.canon.get(k, k) == i for k in idx.headwords.get(n, ())):
        return True
    return any(idx.canon.get(k, k) == i and pc in ("x", "alias", "tipnr") for k, pc, _e in idx.analyse(n))


def _name_codes(idx: _Index, i: int, b: str) -> List[str]:
    if b == idx.lemmas[i].hb:
        return ["L:PROPN|head"]
    if b.endswith("ensium") and _is_name_of(idx, b[:-3] + "is", i):
        return ["L:NAME|ium"]
    ends = []
    for end, reps in _OBLIQUE:
        if b.endswith(end) and len(b) > len(end) + 1:
            base = b[: -len(end)]
            if any(base + r != b and _is_name_of(idx, base + r, i) for r in reps) and end not in ends:
                ends.append(end)
    return ["L:NAME|" + e for e in ends] or ["L:NAME|x"]


def _morph_for(idx: _Index, i: int, anas: List[Tuple[str, str]], b: str, prefixes: Tuple[str, ...]) -> Optional[str]:
    """TokenTag.morph of a token whose chosen lemma is ``i`` and whose analyses of that lemma are ``anas``."""
    codes: List[str] = []
    forms: Optional[List[str]] = None
    for pc, end in anas:
        if pc in ENDINGS:
            got = [f"L:{pc}|{end or '0'}"]
        elif pc in ("x", "alias"):
            forms = forms or _form_candidates(b, prefixes)
            got = [_head_code(idx, i, pc, _listed_form(idx, i, forms, (pc,)) or b)]
        elif pc in ("closed", "extra"):
            if idx.lemmas[i].hb in _FUNCTION_HB:
                got = [f"L:{_head_class(idx, i)}|head"]
            else:
                forms = forms or _form_candidates(b, prefixes)
                got = [f"L:closed|{_listed_form(idx, i, forms, ('closed', 'extra')) or b}"]
        elif pc == "tipnr":
            got = ["L:PROPN|head"]
        elif pc == "textname":
            got = _name_codes(idx, i, b)
        else:
            got = []
        for c in got:
            if c not in codes:
                codes.append(c)
    if any(c.startswith("L:closed|") for c in codes):
        # the hand table gives the cell; an L&S cross-reference entry of the same form ('te, v. tu') adds nothing
        codes = [c for c in codes if not c.endswith("|head")]
    return ",".join(sorted(codes)) if codes else None


def _closed_legend(idx: _Index) -> Dict[str, List[Tuple[str, str, List[str]]]]:
    """form -> [(lemma key, lemma, cells)] for every hand-listed form in the index (function words excepted)."""
    out: Dict[str, List[Tuple[str, str, List[str]]]] = {}
    for f, lst in idx.exact.items():
        for k, t in lst:
            if t not in ("closed", "extra"):
                continue
            i = idx.canon.get(k, k)
            lem = idx.lemmas[i]
            if lem.hb in _FUNCTION_HB or lem.pos in ("ALIAS", "X"):
                continue
            cells = _closed_cells(lem.hb, f) or _closed_cells(idx.lemmas[k].hb, f)
            row = (lem.key, lem.lemma, cells)
            if row not in out.setdefault(f, []):
                out[f].append(row)
    return out


def morph_legend(include_closed: bool = True) -> Dict[str, str]:
    """English description of every Latin parsing code the tagger can emit (``TokenTag.morph`` parts).

    Keys: 'L:<class>' (the class), 'L:<class>|<ending>' (every ending of the class, with all the cells it can
    be), 'L:<class>|head', 'L:V3A|short', 'L:NAME|<ending>' and, when ``include_closed`` (needs the Lewis & Short
    index), 'L:closed|<form>' for every hand-listed form, listing each lemma's cells for it."""
    leg: Dict[str, str] = {}
    for cls, desc in _CLASS_DESC.items():
        leg[_MORPH_PREFIX + cls] = desc
    for pc, ends in ENDINGS.items():
        desc = _CLASS_DESC[pc]
        cells = _PARADIGM_CELLS.get(pc, {})
        for e in sorted(ends, key=lambda x: (len(x), x)):
            key = e or "0"
            cs = cells.get(key)
            what = f"ending -{e}" if e else "no ending"
            leg[f"L:{pc}|{key}"] = f"{desc}, {what}: {'; '.join(cs)}" if cs else f"{desc}, {what} (cells not derived)"
    for cls, cell in _HEAD_CELLS.items():
        what = "" if cls == "X" else "headword form: "
        leg[f"L:{cls}|head"] = f"{_CLASS_DESC[cls]}, {what}{_xc(cell)}"
    for cls, cell in _SHORT_IMP.items():
        leg[f"L:{cls}|short"] = f"{_CLASS_DESC[cls]}: {cell}"
    for e, cs in _NAME_CELLS.items():
        what = f"ending -{e}" if e != "x" else "case not derived"
        leg[f"L:NAME|{e}"] = f"{_CLASS_DESC['NAME']}, {what}: {'; '.join(cs)}"
    if include_closed:
        try:
            idx = _get_index()
        except FileNotFoundError:
            idx = None
        if idx is not None:
            for f, rows in sorted(_closed_legend(idx).items()):
                parts = [f"{lemma}: {'; '.join(cells) if cells else 'listed form (cell not given)'}"
                         for _k, lemma, cells in rows]
                leg[f"L:closed|{f}"] = f"hand-listed form '{f}' - " + " | ".join(parts)
    return leg


def describe_morph(morph: Optional[str], lemma_key: Optional[str] = None) -> str:
    """Readable description of a TokenTag.morph string (codes joined with ','); for hand-listed forms only the
    cells of ``lemma_key`` are given when it is passed."""
    if not morph:
        return ""
    leg = morph_legend(include_closed=False)
    out = []
    for code in morph.split(","):
        if code.startswith("L:closed|"):
            f = code[len("L:closed|"):]
            rows = _closed_legend(_get_index()).get(f, [])
            if lemma_key:
                rows = [r for r in rows if r[0] == lemma_key] or rows
            cells = _union(*[r[2] for r in rows])
            out.append(f"hand-listed form '{f}': " + ("; ".join(cells) if cells else "cell not given"))
        else:
            out.append(leg.get(code, f"{code} (no description)"))
    return " | ".join(out)


def _roots() -> Dict[int, Tuple[int, str]]:
    global _ROOTS
    if _ROOTS is None:
        _ROOTS = _compute_roots(_get_index())
    return _ROOTS


def _lemma_entry(idx: _Index, i: int, roots: Dict[int, Tuple[int, str]]) -> LemmaEntry:
    lem = idx.lemmas[i]
    pos = lem.pos if lem.pos in ("N", "V", "ADJ", "ADV", "PREP", "CONJ", "PRON", "ART", "PART", "NUM", "INTERJ",
                                 "PROPN") else ("PROPN" if lem.proper else "N")
    if i in roots:
        r, formula = roots[i]
        rl = idx.lemmas[r]
        return LemmaEntry(LANG, lem.key, lem.lemma, lem.gloss, pos, None, rl.key, rl.lemma, rl.gloss,
                          LS_ROOT_SOURCE, formula, lem.source)
    return LemmaEntry(LANG, lem.key, lem.lemma, lem.gloss, pos, None, lem.key, lem.lemma, lem.gloss, "self", "",
                      lem.source)


# Documented L&S sub-entry adverbs in -e (not indexed as standalone forms in idx, so standalone tagging keeps
# its anti-vocative guard on e.g. 'recte'; emitted only by latin_parallel.py when parallel Greek/Hebrew confirms
# an adverbial reading in the same verse).
_PARALLEL_ADV_ENTRIES: Tuple[Tuple[str, str, str, str], ...] = (
    ("lat:recte", "recte", "rightly, correctly, properly (L&S s.v. rectus)", "lat:rego"),
    ("lat:occulte", "occulte", "secretly, privately, in hidden manner (L&S s.v. occulo)", "lat:occulo"),
    ("lat:magnifice", "magnifice", "magnificently, splendidly, nobly (L&S s.v. magnificus)", "lat:magnus"),
    ("lat:propere", "propere", "hastily, quickly, speedily (L&S s.v. properus)", "lat:propero"),
    ("lat:insperate", "insperate", "unexpectedly, unhoped for (L&S s.v. insperatus)", "lat:spero"),
    ("lat:absconse", "absconse", "secretly, hiddenly (L&S s.v. abscondo)", "lat:do#1"),
    ("lat:sensate", "sensate", "intelligently, sensibly, with understanding (L&S s.v. sensatus)", "lat:sentio"),
    ("lat:feste", "feste", "festively, joyfully (L&S s.v. festus)", "lat:festus#1"),
)


def load_lexicon() -> Dict[str, LemmaEntry]:
    """Every lemma the tagger can emit, keyed by lemma_key, with its Lewis & Short root family."""
    global _LEXICON
    if _LEXICON is None:
        idx = _get_index()
        _get_tagger()          # corpus statistics; the pass over the Studio text creates its attested names
        roots = _roots()
        lex: Dict[str, LemmaEntry] = {}
        for i, lem in enumerate(idx.lemmas):
            if lem.pos in ("ALIAS",):
                continue
            lex[lem.key] = _lemma_entry(idx, i, roots)
        for pkey, plemma, pgloss, proot in _PARALLEL_ADV_ENTRIES:
            if pkey not in lex:
                re_ent = lex.get(proot)
                if re_ent is not None:
                    lex[pkey] = LemmaEntry(LANG, pkey, plemma, pgloss, "ADV", None,
                                           re_ent.root_key, re_ent.root_label, re_ent.root_gloss,
                                           LS_ROOT_SOURCE, f"{plemma} ← {re_ent.lemma} (L&S)", LS_SOURCE)
                else:
                    lex[pkey] = LemmaEntry(LANG, pkey, plemma, pgloss, "ADV", None,
                                           pkey, plemma, pgloss, "self", "", LS_SOURCE)
        _LEXICON = lex
    return _LEXICON


def lemma_root(lemma_key: str) -> Optional[str]:
    """Convenience: the root_key of a lemma (None when unknown)."""
    e = load_lexicon().get(lemma_key)
    return e.root_key if e else None
