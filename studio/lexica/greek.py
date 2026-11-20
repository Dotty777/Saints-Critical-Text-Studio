"""Greek lemma and root tagger for The Saints Concordance (Septuagint + New Testament).

Every Greek token of the Studio's critical text gets the lemma that an openly licensed,
word-by-word tagged edition gives the same word, or stays untagged.  Nothing is guessed from
suffixes.

New Testament
    STEPBible TAGNT (Tyndale House / STEPBible.org, CC BY 4.0) lists every word of the major
    editions (NA27/28, SBL, Tyndale, WH, Tregelles, TR, Byzantine), variants included, with its
    extended Strong number and dictionary form.  Studio tokens are aligned to the TAGNT words of
    the same verse (NA numbering) by accent-free form, with movable ν and elision allowed for
    (order-preserving alignment in which exact accents win ties, so the article ἡ and the
    conjunction ἤ resolve by position).  A token left over is looked for, in this order, among
    the verse's unpaired TAGNT words in another word order, among the words TAGNT files under
    another edition's verse number (the Romans doxology the Studio also prints at 14:24-26), and
    in the neighbouring verses, each time only when all candidates give one lemma; then in an
    NT-wide form -> lemma table used only when one lemma has >= 95% of the form's attestations.
    Where TAGNT gives the printed (NA) word the lemma of another edition's word, the printed word
    does not take it: a TR/Byz variant listed beside it that is the same stem with other
    prepositions (Acts 21:15 ἐπισκευασάμενοι 'G0643 ἀποσκευάζω' from TR ἀποσκευασάμενοι, Luke
    16:21 ἐπέλειχον 'ἀπολείχω', Mark 15:7 στασιαστῶν 'συστασιαστής') keeps the tag, the printed
    word stays untagged unless TAGNT prints it elsewhere with its own lemma.  A listed 'spelling'
    that TAGNT prints elsewhere as another word takes that word's lemma (Mark 3:4 ἀγαθοποιῆσαι
    beside ποιῆσαι is ἀγαθοποιέω; κἀγώ is not ἐγώ).

Septuagint
    Open Scriptures Septuagint Project lemma files (LxxLemmas, CC BY 4.0) give the lemma of every
    word of every verse (CCAT/Rahlfs numbering), without the inflected forms.  The Studio's text is
    Swete's (Codex B), so each Studio verse is aligned to the lemma list of the same verse (letter
    sub-verses such as Esth 1:1a-s belong to their verse, Sirach's prologue to 1:1 as the Studio
    prints it; the neighbouring verses are part of the window; a verse that matches badly is
    located elsewhere in the book; Theodotion's Daniel and the B texts of Joshua/Judges are tried
    before the alternative files).  A token is paired with a lemma of that list only when
      * a tagged corpus attests the token's form for that lemma (TAGNT, and after a first pass
        over the whole Greek OT the LXX's own pairings; a pairing that rests only on the first
        pass keeps that pass's confidence, at most 0.93, note '(LXX form)'), or
      * the token's letters continue the lemma's stem (augment, reduplication, preverbs, contract
        and -μι stems, one internal vowel-grade change, Codex B's ει/ι spellings allowed for; a
        shared preposition alone is no match: προσοίσει is not προσχέω) and the form is not
        attested for another lemma; function words, prepositions and lemmas of three letters or
        fewer are never paired this way (ἀπέθανεν is not ἀπό), and a function word with the same
        letters must also agree in breathing and accent (oath ἦ μήν is not ἤ 'or'), or
      * it is the one unpaired word between two paired words facing the one unpaired lemma of the
        same verse, its form is not attested for another lemma, and either its stem similarity is
        >= 0.5 or it shares a stem with a form attested for that lemma (ὀφθήτω / ὤφθη for ὁράω);
        a capitalised token facing a name keeps the lax rule (Codex B's Δαμνιήλ for Δανιήλ).
    Context rules: an accented ὃ / ἣ / οἳ / αἳ is the relative, never the article (which is
    accented only before an enclitic: οἵ τε); the Hebrew letter that opens an acrostic stanza in
    Lamentations 1-4 (Ἥ, Μήμ, Νούν ...) stays untagged.
    Unpaired tokens fall back to the LXX-wide and then the NT-wide form -> lemma table (>= 95%,
    >= 2 attestations), unless the verse's own gold list contradicts the answer: an unpaired lemma
    of the verse that the word could be (homographs the tables cannot see: Isa 2:6 ἀνῆκεν is
    ἀνίημι, not ἀνήκω; 2 Sam 20:3 ζῶσαι is ζάω, not ζώννυμι; Num 11:23 γνώσει is γινώσκω, not
    γνῶσις; Deut 25:2 ἀσεβῶν is ἀσεβέω, not ἀσεβής) leaves the word untagged.  Form lookups keep
    breathings and accents (ἁφή is not ἀφῇ, ἢ is not ἡ), allowing only enclitic accent changes; a
    capitalised token only takes a lemma the corpus also prints capitalised, or one that is not a
    common noun (Γάζης the city is not γάζα 'treasure'; Λάβε opening a sentence is λαμβάνω);
    proper names come only from the LXX's own pairings and only for capitalised tokens (TAGNT's
    Βόες is Boaz, lower-case βόες are oxen).  Otherwise the token stays untagged.

    The LXX-wide table is one fixed function of the Greek OT corpus, built once per process by
    whichever runs first: tag_chapter() on an OT book (from the Studio DB data/studio.db, opened
    read-only), tag_all(conn) or prepare(conn) (from ``conn``).  It never changes afterwards
    (prepare(force=True) excepted), so a chapter gets the same tags whether or not tag_all() or
    prepare() ran before it.  AUTO_PREPARE = False (tests) makes tag_chapter() fix an empty table
    instead of reading the DB.

    Where TAGNT and the LXX lemma files lemmatise the same form differently, the TAGNT form
    evidence decides (εἶδον/ἰδών are εἴδω G1492 throughout, as in the NT, although the LXX files
    give ὁράω in some verses and εἴδω in others).

Lemma keys
    The Strong number where one exists (``G0746``; TBESG extended numbers such as ``G6181`` for
    LXX words), else ``grc:<lemma>``.  Meaning splits of one Strong number (G3004G/G3004H) share
    one key; inflected-form numbers of the personal pronouns, εἰμί, the article, οὗτος and εἷς
    (μου G3450, σοῦ G4675, ἦν G2258 ...) and the forms TAGNT itself files under another lemma
    (μέ G3165 -> ἐγώ, οἶδα G6063 -> εἴδω, ἐρῶ G2046 -> εἶπον) are folded into that lemma, so the
    LXX (which keeps μου, σοῦ as headwords) and the NT agree.  Where TAGNT tags a word with a
    family's number but names another dictionary form (ἐμός and ἐμαυτοῦ as G1473, ὤφθη as G3700),
    the dictionary form's own number is used.  The LXX lists unaccented names (Εσθηρ) take a TBESG
    number only when exactly one TBESG person/place/title has those letters and the same
    capitalisation.  Homographs stay apart (ὄρος G3735 vs ὅρος, εἰμί G1510 vs εἶμι G7063).  A Greek
    Word List entry without a Strong number takes its own TBESG number first (ἐπισκευάζω G7447,
    δέος G6015, φονευτής G9655); its 'v' (variant) pointer is followed only for spellings
    (χειμάρρους / χείμαρρος, Ἰσσαχάρ / Ἰσαχάρ, or a form TBESG lists: 'Νεεμάν, Ναιμάν'), not to
    another headword (ἐπισκευάζω is not ἀποσκευάζω, δέος is not δειλός).  TBESG's lower-case
    headword of a name that differs from Strong's (G2748 'κέδρος' for Κεδρών) gives way to Strong's,
    so the LXX's κέδρος 'cedar' is not Kidron.

Root families
    Followed through explicit derivation statements only: Strong's Greek Dictionary
    (CC0, ``from G3004``, ``from G575 and G2192``), then MorphGNT's morphological lexicon
    ``derivation.yaml`` (CC BY-SA 3.0), then the Open Scriptures Greek Word List ``src`` field
    (CC BY 4.0) - and since the final check of 18 Nov 2026 a link joins two words only under the
    conservative policy described above _FAMILY_PREFIX_SPELLINGS: a transparent compound (every
    named preposition / prefix / content word visible in the word), a link MorphGNT or Abbott-Smith
    (public domain) also names, or a derivative that visibly continues the base's stem (three
    letters or more; only the listed regular vowel grades and stem-final consonant changes).
    Everything else is its own family.  Strong's guesses no longer join πορεύομαι to πεῖρα, ἄρτος
    and ἀριθμός to αἴρω, ὕδωρ to ὕω, στρέφω to τρέπω, οὗτος to αὐτός, δῆμος / δεῖ / δέομαι to δέω
    'bind', τότε to τε, τόξον to τίκτω, ἄνθρωπος to ἀνήρ, περί to πέραν, ὀργή to ὀρέγω, πέτρα to
    the name Πέτρος.  A family head must have a meaning of its own: ``root_gloss`` is the head's
    general gloss (κῦρος 'supreme power', ἔργω 'to work' and δελφύς 'the womb' from Strong's, στέλλω
    'to set, place, arrange' from Abbott-Smith), never a member's gloss; a chain that reaches a base
    nobody glosses stops at the word before it.  GreekTagger.linked() keeps the permissive walk
    (``root_of(strict=False)``) it was verified with; that walk never reaches readers.
    Hedged statements (probably / probable / perhaps / possibly / apparently / akin
    to / of uncertain / as if / through the idea of / or rather / "properly, ..." ...) are not
    followed (προσκυνέω 'a probable derivative of G2965' is not filed under κύων), nor a link
    that names only a preverb, nor 'from the same as' a compound of two content words (πυκνός
    'from the same as G4635' σκηνοποιός).  Five slips in Strong's numbers are corrected
    (Ἀρχέλαος G2994 -> λαός G2992, εὐπορέω G2090 -> εὖ G2095, διαφθείρω G1225 -> διά G1223,
    συγκινέω G4682 -> σύν G4862, πεποίθησις G3958 -> πείθω G3982).  A Greek Word List 'src' link
    is followed only where Strong's does not hedge it, call the word primary or foreign, and
    MorphGNT does not derive it from another word, unless Strong's names the same word itself
    (φῶς 'from an obsolete φάω'): so φημί 'src φάω' (Strong's: 'properly, ...') is not followed
    and the speech words (φημί, φωνή, προφήτης, βλασφημέω) form one family apart from the light
    words.  Under the conservative policy the light words are two families: φῶς (φωστήρ, φωτίζω)
    and φαίνω (φανερόω, ἐπιφάνεια; πρόφασις with them: Strong's and MorphGNT both derive it from
    προφαίνω), since φῶς < φάω and φαίνω < φῶς are not visible in the words.  When Strong's derives a word from an unnumbered word that has the letters of
    a numbered entry (ἄργυρος 'from ἀργός (shining)', not G692 ἀργός 'idle' < α + ἔργον), no other
    source may resolve that headword to the numbered entry: silver is not in the family of work.
    In a compound the family is the last component that is not a preposition or inseparable
    prefix (ἀπέχω: ἀπό + ἔχω -> family ἔχω); ``formula`` records the chain without repeating a
    component.  When two
    sources derive two words from each other (μιμνήσκω / μνάομαι) the loop's lowest key heads the
    family.  ``root_source`` names the source of each link of the chain ('Strongs-CC0',
    'MorphGNT-derivation', 'OSSP-GWL-src', joined by '+' when a chain crosses sources); without
    derivation data the family is the lemma itself (``root_source='self'``).

Function words (``is_content=False``): the article; conjunctions (καί δέ γάρ ἀλλά ἤ ὅτι ἵνα
ὡς ἕως ἄχρι μέχρι πρίν ...) and conditional particles (εἰ ἐάν ἄν); particles (μέν οὖν τε γε δή
...), including the negatives οὐ/μή and their compounds (οὐδέ μηδέ οὔτε); and every pronoun:
personal (ἐγώ σύ αὐτός and their case forms), relative (ὅς ὅστις ὅσπερ), demonstrative (οὗτος
ἐκεῖνος ὅδε), interrogative / indefinite (τίς τις), reflexive (ἑαυτοῦ σεαυτοῦ ἐμαυτοῦ),
reciprocal (ἀλλήλων), possessive (ἐμός σός ἡμέτερος) and correlative (ὅσος τοιοῦτος ποῖος
πόσος).  Classification follows TBESG's morph column (G:T, G:CONJ*, G:COND*, G:PRT, G:PRT-N*,
G:P-1, G:P-2, G:P, G:R, and the other pronoun classes D F S I X Q K C) or, for LXX lemmas without
a Strong number, the Greek Word List part of speech (C, X, R); ὡς, ἕως, ἄχρι, μέχρι and πρίν,
which TBESG files as adverb or preposition, are added by hand (MorphGNT parses them as
conjunctions).  Prepositions count as content.  (Until 18 Nov 2026 demonstratives,
interrogatives, reflexives and possessives were indexed; the tagger's own closed-class test was
already treating them as pronouns, so tagging does not change.)

Glosses
    TBESG's brief gloss (a split Strong number gives its general part: 'lord: God' -> 'lord',
    'to do/make: do' -> 'to do/make'; names give every person's gloss, 'Jesus; Joshua', plus the
    Hebrew original of the LXX name, 'Mary; Miriam'); a New Testament name or title the LXX uses
    as a common word adds the Word List's definition ('Christ; anointed'); a verb TAGNT folds in
    adds its gloss (εἴδω 'to perceive; to know').  Words without a TBESG number: TAGNT's gloss, the
    Word List definition, TBESG / TFLSJ for the same headword (cols 1-7, CC BY), TBESH for a
    transliterated Hebrew word, last the first translation of Liddell-Scott-Jones (Perseus XML,
    CC BY-SA 4.0; a sense citing the LXX first).  The Greek headword is never used as a gloss.
    Lower-case Septuagint nouns keep their own lemma instead of an NT name's number (τύραννος
    'tyrant' is not Τύραννος, δορκάς 'gazelle' not Δορκάς, χλόη 'grass' not Χλόη, ῥώμη 'strength'
    not Ῥώμη, πέτρος 'rock' not Πέτρος), and TBESG's lower-case 'N:' (name-class) words are common
    nouns (κοιλάς, λοβός, νάβλα, οἰφί, τήγανον, ἐλαιών).

Parsing (``TokenTag.morph`` / ``TokenTag.src``, added 18 Nov 2026)
    A New Testament token aligned to a TAGNT word (method 'gold-aligned') carries that word's
    parse from TAGNT column 4 with the scheme prefix ``R:`` ('G0746=N-DSF' -> 'R:N-DSF'; a word
    TAGNT tags with several numbers, crasis such as κἀγώ 'G1473=P-1NS + G2532=CONJ', joins the
    parses with '+': 'R:P-1NS+CONJ') and ``src = 'tagnt:<ref>'`` ('tagnt:Mat.1.1#01').  The parse
    is the one of the form the token matched: the printed word's own (also for its listed
    spellings), or that of another edition's word in the same place when the token is that word
    (Acts 1:10 ἐσθῆτι 'N-DSF' beside NA's ἐσθήσεσι 'N-DPF').  A listed 'spelling' that is another
    word printed elsewhere with its own lemma has no parse here.  When a token is found in another
    word order / verse number / neighbouring verse and the matching TAGNT words disagree on the
    parse, ``morph`` stays None (``src`` still names the first word).  Tokens resolved by the NT-wide
    form table ('gold-form') and untagged tokens have neither: no single TAGNT word stands behind
    them.  The Septuagint has no openly licensed parsing source, so every LXX token has
    ``morph = None`` (the Rahlfs/CCAT morphology is non-commercial; GLAUx is an owner decision; no
    parse is guessed from forms).  ``morph_legend()`` gives the English description of every code
    from STEPBible TEGMC (Translators Expansion of Greek Morphology Codes, Tyndale House /
    STEPBible.org, CC BY 4.0), see SRC_TEGMC for the note of changes.  Lemma choices do not depend
    on any of this.

Licences: only CC BY / CC BY-SA / CC0 / public-domain data is read here (since 18 Nov 2026 also
Abbott-Smith's TEI lexicon, public domain, for its hyphenated headwords, '(< X)' etymology notes
and first senses; TBESH and TFLSJ-extra, CC BY, columns 1-7; Perseus LSJ XML, CC BY-SA 4.0, for
the first translation of words no Bible lexicon glosses).  The Rahlfs/CCAT text, PROIEL and other
non-commercial data are used by evaluation scripts outside ``studio/`` only.  TBESG, TBESH and
TFLSJ are read in columns 1-7 only.
"""

from __future__ import annotations

import difflib
import glob
import json
import os
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple

from . import LemmaEntry, TokenTag, greek_bare, tokenize_verse

LANG = "grc"

# ---------------------------------------------------------------------------
# Source locations (all inside the self-contained Studio, with the shared corpus folder as fallback)
# ---------------------------------------------------------------------------

_STUDIO_ROOT = Path(__file__).resolve().parents[2]


def _fs(path) -> str:
    """Path string usable by open()/exists() even past Windows' 260-character limit (the TAGNT
    files inside the Studio sit at about 250 characters)."""
    s = os.path.abspath(str(path))
    if os.name == "nt" and len(s) >= 240 and not s.startswith("\\\\?\\"):
        s = "\\\\?\\" + s.replace("/", "\\")
    return s


def _exists(path) -> bool:
    return os.path.exists(_fs(path))


def _research_root() -> Path:
    try:
        from ..catalog import GREEK_RESEARCH_ROOT  # respects CTS_REPO_ROOT
        root = Path(GREEK_RESEARCH_ROOT)
        if _exists(root / "01_Tier1_Modern_Critical_Open"):
            return root
    except Exception:  # pragma: no cover - catalog import problems must not hide the corpus
        pass
    return _STUDIO_ROOT / "Saints-Greek-Critical-Text"


def _open_dir() -> Path:
    return _research_root() / "01_Tier1_Modern_Critical_Open"


def _step_dir() -> Path:
    cands = [
        _open_dir() / "NT_OT_STEPBible_Data",
        _STUDIO_ROOT.parent.parent / "01_Tier1_Modern_Critical_Open" / "NT_OT_STEPBible_Data",
    ]
    for c in cands:
        if _exists(c / "Lexicons"):
            return c
    return cands[0]


def _tagnt_files() -> List[Path]:
    return sorted(Path(p) for p in glob.glob(str(_step_dir() / "Translators Amalgamated OT+NT" / "TAGNT*.txt")))


def _tbesg_file() -> Optional[Path]:
    hits = sorted(glob.glob(str(_step_dir() / "Lexicons" / "TBESG*.txt")))
    return Path(hits[0]) if hits else None


def _tegmc_file() -> Optional[Path]:
    hits = sorted(glob.glob(str(_step_dir() / "Morphology codes" / "TEGMC*.txt")))
    return Path(hits[0]) if hits else None


def _ossp_dir() -> Path:
    return _open_dir() / "OT_NT_OpenScriptures_Lemmas"


def _strongs_xml() -> Path:
    return _open_dir() / "Lexicon_MorphGNT_Strongs" / "strongs-dictionary-xml" / "strongsgreek.xml"


def _morphgnt_derivation() -> Path:
    return _open_dir() / "Lexicon_MorphGNT_Strongs" / "morphological-lexicon" / "derivation.yaml"


def corpora_available() -> Dict[str, bool]:
    """Which source files are present (used by the tests to skip cleanly)."""
    return {
        "tagnt": bool(_tagnt_files()),
        "tbesg": _tbesg_file() is not None,
        "lxx_lemmas": _exists(_ossp_dir() / "LxxLemmas" / "Gen.js"),
        "greek_word_list": _exists(_ossp_dir() / "GreekWordList.js"),
        "strongs": _exists(_strongs_xml()),
        "morphgnt_derivation": _exists(_morphgnt_derivation()),
        "abbott_smith": _exists(_abbott_smith_file()),
        "lsj": bool(glob.glob(str(_lsj_dir() / "*.xml"))),
    }


SRC_TAGNT = "STEPBible TAGNT + TBESG cols 1-7 (Tyndale House/STEPBible.org, CC BY 4.0)"
SRC_OSSP = "Open Scriptures Septuagint Project LxxLemmas + Greek Word List (CC BY 4.0)"
SRC_STRONGS = "Strong's Greek Dictionary XML, U. Sandborg-Petersen (CC0)"
SRC_MORPHGNT = "MorphGNT morphological-lexicon derivation.yaml (CC BY-SA 3.0)"
SRC_TEGMC = ("STEPBible TEGMC, Translators Expansion of Greek Morphology Codes (Tyndale House/STEPBible.org, "
             "CC BY 4.0, https://STEPBible.github.io/STEPBible-Data); changes: the summary phrase (line 2 "
             "of each full code) only, quotes and extra spaces removed, a word repeated next to itself "
             "given once ('Negative Particle Negative Negative' -> 'Negative Particle Negative'), "
             "crasis codes joined with ' + '")
MORPH_SCHEME = "R"        # TokenTag.morph prefix of TAGNT (Robinson-style) parses: 'R:N-DSF'

# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

_ELISION_MARKS = "᾽’'ʼ᾿"
_GRAVE = "̀"
_ACUTE = "́"


def accent_key(text: str) -> str:
    """Lower-case Greek keeping breathings and accents (grave folded to acute, final σ folded,
    diaeresis, length marks and punctuation dropped).  Distinguishes ὄρος/ὅρος, ἡ/ἤ/ἦ."""
    t = unicodedata.normalize("NFD", text.lower())
    out = []
    for ch in t:
        if ch == _GRAVE:
            out.append(_ACUTE)
        elif unicodedata.category(ch) == "Mn":
            if ch in ("̓", "̔", _ACUTE, "͂", "ͅ"):  # breathings, acute, circumflex, iota subscript
                out.append(ch)
        elif "α" <= ch <= "ω" or ch == "ς":
            out.append("σ" if ch == "ς" else ch)
    return unicodedata.normalize("NFC", "".join(out))


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


# Elided spellings of function words (the elision mark is on the token): bare -> full bare forms.
_ELIDED = {
    "δ": ["δε"], "τ": ["τε"], "γ": ["γε"],
    "απ": ["απο"], "αφ": ["απο"], "κατ": ["κατα"], "καθ": ["κατα"], "μετ": ["μετα"], "μεθ": ["μετα"],
    "επ": ["επι"], "εφ": ["επι"], "υπ": ["υπο"], "υφ": ["υπο"], "παρ": ["παρα"], "αλλ": ["αλλα"],
    "δι": ["δια"], "αντ": ["αντι"], "ανθ": ["αντι"], "αν": ["ανα"], "ουδ": ["ουδε"], "μηδ": ["μηδε"],
    "ουτ": ["ουτε"], "μητ": ["μητε"], "τουτ": ["τουτο"], "ταυτ": ["ταυτα"], "εστ": ["εστι"],
    "ιν": ["ινα"], "ειτ": ["ειτα"], "ειθ": ["ειτα"], "ποτ": ["ποτε"], "ποθ": ["ποτε"],
    "εγωγ": ["εγωγε"], "ταυθ": ["ταυτα"], "τουθ": ["τουτο"],
}


def _has_elision(token: str) -> bool:
    return bool(token) and token[-1] in _ELISION_MARKS


def _form_keys(token: str) -> List[str]:
    """Bare lookup keys for a token: the bare form, its movable-ν twin, the unelided form."""
    b = greek_bare(token)
    keys = [b] if b else []
    keys += [k for k in _nu_variants(b) if k not in keys]
    if _has_elision(token) and b in _ELIDED:
        keys += [k for k in _ELIDED[b] if k not in keys]
    return keys


def _nu_twins(key: str) -> List[str]:
    """Movable-ν twin of an (accented or breathing) key: ἐστιν <-> ἐστι, εἶπεν <-> εἶπε."""
    letters = greek_bare(key)
    if len(letters) > 2 and letters.endswith("ν") and letters[-2] in "ει":
        return [key[:-1]]
    if len(letters) > 2 and letters[-1] in "ει" and not letters.endswith("ει"):
        return [key + "ν"]
    return []


_BREATHINGS = ("̓", "̔")
_ACCENTS = (_ACUTE, "͂")


def _accent_sig(ak: str) -> Tuple[str, Tuple[Tuple[int, str], ...]]:
    """(breathing key, (position-from-the-end, accent) of accented letters) of an accent key.
    The accent's kind counts: ἐργᾶται (verb) is not ἐργάται (noun)."""
    letters: List[str] = []
    accented: List[Tuple[int, str]] = []
    for ch in unicodedata.normalize("NFD", ak):
        if unicodedata.category(ch) == "Mn":
            if ch in _ACCENTS and letters:
                accented.append((len(letters) - 1, ch))
            elif ch in _BREATHINGS or ch == "ͅ":
                if letters:
                    letters[-1] = letters[-1] + ch
            continue
        letters.append(ch)
    n = len(letters)
    return unicodedata.normalize("NFC", "".join(letters)), tuple(sorted((n - 1 - i, c) for i, c in accented))


def _accents_compatible(a: Tuple, b: Tuple) -> bool:
    """Same word under enclitic/proclitic accent changes: identical accent positions, one side
    unaccented, or one side carrying an extra accent thrown back by an enclitic."""
    if a == b or not a or not b:
        return True
    if len(a) == 2 and len(b) == 1:
        return b[0] == a[1]
    if len(b) == 2 and len(a) == 1:
        return a[0] == b[1]
    return False


class _FormTable:
    """Form -> lemma attestations with three lookup tiers: the accented form; the same letters
    and breathing with a compatible accent (enclitic accent changes); the bare letters only when
    the token itself carries no diacritics.  Bare-letter collisions (ἡ/ἤ/ἦ/ᾗ, ἁφή/ἀφῇ,
    μαρτύρια/μαρτυρία) therefore never merge."""

    def __init__(self, common_noun=None) -> None:
        # common_noun(key) -> True for a common noun; a capitalised token drops those unless the
        # corpus prints them capitalised.  Without it every lemma counts as a noun.
        self.common_noun = common_noun
        self.acc: Dict[str, Counter] = defaultdict(Counter)
        self.by_breath: Dict[str, Set[str]] = defaultdict(set)
        self.by_bare: Dict[str, Set[str]] = defaultdict(set)
        self.caps: Counter = Counter()          # lemma keys attested with a capitalised form
        self.total: Counter = Counter()         # lemma keys, every attestation
        self.by_key: Dict[str, Set[str]] = defaultdict(set)      # lemma key -> bare forms
        self.best: Dict[Tuple[str, str], float] = {}             # (accent key, lemma) -> confidence

    def add(self, surface: str, key: str, n: int = 1, conf: Optional[float] = None) -> None:
        ak = accent_key(surface)
        if not ak:
            return
        self.acc[ak][key] += n
        self.by_breath[_accent_sig(ak)[0]].add(ak)
        self.by_bare[greek_bare(ak)].add(ak)
        self.by_key[key].add(greek_bare(ak))
        if conf is not None and conf > self.best.get((ak, key), 0.0):
            self.best[(ak, key)] = conf
        self.total[key] += n
        if surface[:1].isupper():
            self.caps[key] += n

    def __len__(self) -> int:
        return len(self.acc)

    def forms_of(self, key: str) -> Set[str]:
        return self.by_key.get(key, set())

    def best_conf(self, token: str, key: str) -> Optional[float]:
        vals = [self.best[(a, key)] for a in self._matches(token) if (a, key) in self.best]
        return max(vals) if vals else None

    def candidates(self, token: str) -> Counter:
        """Attested lemma keys of the token's form.  A capitalised token keeps only lemmas that
        the corpus also prints capitalised (Γάζης the city is not γάζα 'treasure'), and words
        other than common nouns (a verb that opens a sentence: Λάβε, Ἔζησεν)."""
        c = Counter()
        for a in self._matches(token):
            c.update(self.acc[a])
        if c and token[:1].isupper():
            cn = self.common_noun
            c = Counter({k: n for k, n in c.items() if self.caps.get(k) or (cn is not None and not cn(k))})
        return c

    def _matches(self, token: str) -> List[str]:
        """The attested accent keys the token's form matches, first tier that matches only."""
        ak = accent_key(token)
        if not ak:
            return []
        for a in [ak] + _nu_twins(ak):
            if a in self.acc:
                return [a]
        out: List[str] = []
        bk, pos = _accent_sig(ak)
        for b in [bk] + _nu_twins(bk):
            for other in sorted(self.by_breath.get(b, ())):
                if _accents_compatible(pos, _accent_sig(other)[1]):
                    out.append(other)
            if out:
                return out
        bare = greek_bare(token)
        if _has_elision(token) and bare in _ELIDED:
            for full in _ELIDED[bare]:
                out.extend(sorted(self.by_bare.get(full, ())))
            return out
        if ak == bare:                       # the token carries no breathing or accent at all
            for b in [bare] + _nu_variants(bare):
                out.extend(sorted(self.by_bare.get(b, ())))
        return out

    def lookup(self, token: str, min_share: float, min_count: int, exclude=None) -> Optional[Tuple[str, float]]:
        c = self.candidates(token)
        if exclude is not None and c:
            c = Counter({k: n for k, n in c.items() if not exclude(k)})
        if not c:
            return None
        k, n = c.most_common(1)[0]
        tot = sum(c.values())
        if n >= min_count and n / tot >= min_share:
            return k, n / tot
        return None

    def known(self, token: str, floor: float = 0.02) -> Set[str]:
        c = self.candidates(token)
        if not c:
            return set()
        tot = sum(c.values())
        return {k for k, n in c.items() if n / tot >= floor}


def _spelling_norm(word: str) -> str:
    """Bare letters with the spelling differences of the Greek Word List's variant pairs levelled:
    doubled consonants (χειμάρρους/χείμαρρος, Ἰσσαχάρ), ει/ι, ω/ο, middle -ομαι/-ω."""
    b = greek_bare(word)
    if b.endswith("ομαι"):
        b = b[:-4] + "ω"
    b = b.replace("ει", "ι").replace("ω", "ο")
    return re.sub(r"([βγδζθκλμνξπρστφχψ])\1", r"\1", b)


def _edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return prev[-1]


def _spelling_variant(a: str, b: str) -> bool:
    """Two headwords that differ only in spelling or ending (Ἐμμώρ/Ἐμμόρ, πετεινόν/πετεινός,
    χιόνα/χιών), not two words (ἐπισκευάζω/ἀποσκευάζω, δέος/δειλός)."""
    x, y = _spelling_norm(a), _spelling_norm(b)
    if not x or not y:
        return False
    d = _edit_distance(x, y)
    return d <= 1 or (d <= 2 and _lcp(x, y) >= 2)


def _clean_headword(h: str) -> str:
    h = (h or "").strip()
    for sep in ("=", ","):
        if sep in h:
            h = h.split(sep)[0].strip()
    return unicodedata.normalize("NFC", h)


_STRONGS_ASIDE = re.compile(
    r"\b(contraction|obsolete|probabl\w*|perhaps|akin|origin|bent|base|apparently|uncertain|primary|from|"
    r"same as|derivative|compare|comp\.|a form of)\b", re.I)


def _strong_num(key: Optional[str]) -> Optional[int]:
    if not key:
        return None
    m = re.match(r"^G(\d+)", key)
    return int(m.group(1)) if m else None


def _gkey(n: int, letter: str = "") -> str:
    return f"G{n:04d}{letter}"


def _key_order(key: str) -> Tuple[int, int, str]:
    """Stable order of lemma keys: Strong numbers numerically, then 'grc:' keys."""
    n = _strong_num(key)
    return (0, n, key) if (n is not None and key.startswith("G")) else (1, 0, key)


# ---------------------------------------------------------------------------
# Lexical sources
# ---------------------------------------------------------------------------

class _Tbesg:
    """TBESG rows, columns 1-7 only (eStrong, dStrong=relation, uStrong/target, Greek, translit,
    morph, gloss).  Column 8 (Abbott-Smith/LSJ meaning) is never stored."""

    def __init__(self) -> None:
        self.rows: Dict[str, dict] = {}          # dStrong -> row
        self.estrong_of: Dict[str, str] = {}     # dStrong -> eStrong
        self.by_estrong: Dict[str, List[dict]] = defaultdict(list)
        self.by_head: Dict[str, Set[str]] = defaultdict(set)      # accent_key(head) -> eStrongs
        self.by_bare: Dict[str, Set[str]] = defaultdict(set)      # bare(head) -> eStrongs
        self.combination: Dict[frozenset, str] = {}               # component set -> eStrong
        f = _tbesg_file()
        if f is None:
            return
        with open(_fs(f), encoding="utf-8-sig") as fh:
            for line in fh:
                p = line.rstrip("\r\n").split("\t")
                if len(p) < 7 or not re.match(r"^G\d+$", p[0]):
                    continue
                m = re.match(r"^(G\d+[A-Z]?)\s*=\s*(.*)$", p[1].strip())
                if not m:
                    continue
                d, relation = m.group(1), m.group(2).strip()
                row = {
                    "estrong": p[0], "dstrong": d, "relation": relation, "target": p[2].strip(),
                    "head": _clean_headword(p[3]), "raw_head": p[3].strip(), "translit": p[4].strip(),
                    "morph": p[5].strip(), "gloss": p[6].strip(),
                }
                self.rows[d] = row
                self.estrong_of[d] = p[0]
                self.by_estrong[p[0]].append(row)
                if row["head"] and not row["head"].startswith("["):
                    self.by_head[accent_key(row["head"])].add(p[0])
                    self.by_bare[greek_bare(row["head"])].add(p[0])
                if relation == "a Combination of":
                    comps = re.findall(r"G\d+", re.sub(r"^[^(]*", "", row["target"]))
                    if comps:
                        self.combination.setdefault(frozenset(_gkey(int(c[1:])) for c in comps), p[0])

    def primary(self, estrong: str) -> Optional[dict]:
        rows = self.by_estrong.get(estrong)
        if not rows:
            return None
        for r in rows:
            if not r["relation"]:
                return r
        return rows[0]


class _Tbesh:
    """TBESH (STEPBible brief Hebrew lexicon, CC BY 4.0), columns 1-7 only: the gloss of a Hebrew
    Strong number, for the Septuagint's names and transliterations whose Word List entry gives
    their Hebrew source ('src H4813' Μαρία -> 'Miriam')."""

    def __init__(self) -> None:
        self.by_num: Dict[int, List[str]] = defaultdict(list)
        hits = sorted(glob.glob(str(_step_dir() / "Lexicons" / "TBESH*.txt")))
        if not hits:
            return
        with open(_fs(hits[0]), encoding="utf-8-sig") as fh:
            for line in fh:
                p = line.rstrip("\r\n").split("\t")
                if len(p) < 7 or not re.match(r"^H\d+$", p[0]):
                    continue
                rel = p[1].split("=", 1)[1].strip() if "=" in p[1] else ""
                if rel in ("a Spelling of", "a Form of"):
                    continue
                g = p[6].strip()
                if g and g not in self.by_num[int(p[0][1:])]:
                    self.by_num[int(p[0][1:])].append(g)

    def glosses(self, n: int) -> List[str]:
        return [g for g in self.by_num.get(n, []) if not g.startswith("(")]


class _TflsjExtra:
    """TFLSJ extra (STEPBible formatted LSJ for the Septuagint's extra numbers, CC BY 4.0), columns
    1-7 only (number, headword, morph, gloss); the LSJ text in column 8 is not read."""

    def __init__(self) -> None:
        self.by_bare: Dict[str, List[dict]] = defaultdict(list)
        for fn in sorted(glob.glob(str(_step_dir() / "Lexicons" / "TFLSJ*extra*.txt"))):
            with open(_fs(fn), encoding="utf-8-sig") as fh:
                for line in fh:
                    p = line.split("\t", 7)
                    if len(p) < 7 or not re.match(r"^G\d+$", p[0]):
                        continue
                    head = _clean_headword(p[3])
                    self.by_bare[greek_bare(head)].append({"estrong": p[0], "head": head,
                                                           "morph": p[5].strip(), "gloss": p[6].strip()})


def _lsj_dir() -> Path:
    return _open_dir() / "Lexicon_Perseus_LSJ_XML" / "CTS_XML_TEI" / "perseus" / "pdllex" / "grc" / "lsj"


_BETA = dict(zip("abgdezhqiklmncoprstufxyw", "αβγδεζηθικλμνξοπρστυφχψω"))


class _Lsj:
    """Liddell-Scott-Jones (Perseus Digital Library XML, CC BY-SA 4.0), read lazily and only for the
    words no Bible lexicon glosses: the first translations (<tr>) of the entry with the same
    letters (the same accents preferred); an entry that only says '= X' takes X's.  Read once."""

    def __init__(self) -> None:
        self._index: Optional[Dict[str, List[Tuple[str, List[str], Optional[str]]]]] = None

    def _load(self) -> Dict[str, List[Tuple[str, List[str], Optional[str]]]]:
        if self._index is not None:
            return self._index
        idx: Dict[str, List[Tuple[str, List[str], Optional[str]]]] = defaultdict(list)
        for fn in sorted(glob.glob(str(_lsj_dir() / "*.xml"))):
            with open(_fs(fn), encoding="utf-8") as fh:
                text = fh.read()
            for m in re.finditer(r'<entryFree [^>]*?key="([^"]+)"[^>]*>(.*?)</entryFree>', text, re.S):
                key = m.group(1)
                bare = "".join(_BETA.get(ch, "") for ch in re.sub(r"\d", "", key.lower()))
                body = m.group(2)
                # a sense that cites the Septuagint first (λογεῖον: the high priest's breastpiece,
                # not 'speaking-place'), then the entry's first translations
                blocks = [b for b in re.split(r"<sense\b", body) if "LXX" in b]
                found: List[List[str]] = []
                for part in blocks[:1] + [body]:
                    trs = [re.sub(r"\s+", " ", t).strip(" ,.;:") for t in
                           re.findall(r"<tr(?:\s[^>]*)?>([^<]*)</tr>", part)[:4]]
                    found.append([t for t in trs if len(t) > 2])
                # (translations of the LXX sense or else the first, translations of the first sense)
                lxx_trs = next((f for f in found if f), [])
                eq = re.search(r'^[^<]*<orth[^>]*>[^<]*</orth>[^<]{0,12}=\s*<foreign lang="greek"[^>]*>([^<]+)</foreign>', body) \
                    or re.search(r'\bfor\s*<foreign lang="greek"[^>]*>([^<]+)</foreign>', body[:700])
                idx[bare].append((key, lxx_trs, eq.group(1).strip() if eq else None, found[-1]))
        self._index = idx
        return idx

    def gloss(self, head: str, depth: int = 0, general: bool = False) -> str:
        """``general``: the entry's first sense even when another sense cites the LXX (a family
        meaning: ἕδρα 'seat', not the LXX's 'buttock')."""
        if not head or depth > 1:
            return ""
        b = greek_bare(head)
        ents = self._load().get(b, [])
        if not ents:
            return ""
        acc = accent_key(head)
        ents = sorted(ents, key=lambda e: 0 if accent_key(_beta_to_greek(e[0])) == acc else 1)
        for key, trs, eq, first in ents:
            use = first if general else trs
            if use:
                return _short_def(use[0], None)
        for key, trs, eq, first in ents:
            if eq:
                other = _beta_to_greek(eq)
                if other.startswith("-"):
                    # '= -ιάω' (θυμιάζω = θυμιάω): the same word with another ending
                    tail = greek_bare(other)
                    for i in range(len(b) - 1, 1, -1):
                        if b[i] == tail[:1]:
                            g = self.gloss(b[:i] + tail, depth + 1, general)
                            if g:
                                return g
                            break
                else:
                    g = self.gloss(other, depth + 1, general)
                    if g:
                        return g
        return ""


def _beta_to_greek(beta: str) -> str:
    """Perseus beta code -> Greek letters with breathings and accents (enough for accent_key)."""
    out = []
    marks = {")": "̓", "(": "̔", "/": "́", "\\": "̀", "=": "͂", "|": "ͅ"}
    for ch in re.sub(r"\d", "", beta):
        c = ch.lower()
        if c in _BETA:
            out.append(_BETA[c])
        elif ch in marks and out:
            out.append(marks[ch])
        elif ch == "-":
            out.append("-")
    return unicodedata.normalize("NFC", "".join(out))


# Lemmas whose gloss leads with the Word List definition (n items) before TBESG's brief gloss,
# which gives one New Testament sense only: γίνομαι 'to be' -> 'to happen, become; to be', ἔθνος
# 'Gentiles' -> 'a nation; Gentiles' (845 Septuagint tokens are 'nations').
_GLOSS_WORD_LIST_FIRST: Dict[str, int] = {"G1096": 2, "G1484": 1}

# Family heads whose TBESG gloss is one narrow sense: the family's meaning is Abbott-Smith's first
# sense (public domain), the Word List's first definition (CC BY) or LSJ's first sense (CC BY-SA).
# στέλλω 'to avoid' heads ἀποστέλλω / ἀπόστολος / ἐπιστολή ('to set, place, arrange'); δίκη
# 'condemnation' heads δίκαιος / δικαιοσύνη ('justice'); ψύχω 'to cool' heads ψυχή ('to breathe,
# blow'); ἕδρα 'buttock' (the LXX's sense) heads ἑδραῖος / ἐνέδρα ('seat').
_ROOT_MEANING_OVERRIDE: Dict[str, str] = {"G4724": "abbott-smith", "G1349": "word-list", "G5594": "abbott-smith",
                                          "G7045": "lsj"}

# Family heads whose only gloss is one narrow sense (18 Nov re-check: λείπω 'to lack' heading καταλείπω and
# λοιπός, τρέπω 'to rout' heading τρόπος and ἐπιτρέπω): the head's general meaning, Saints editorial wording.
_ROOT_MEANING_TEXT: Dict[str, str] = {"G3007": "to leave; to lack", "G9472": "to turn", "G1208": "second",
                                      "G2339": "hunting; prey", "G5530": "to use"}

# Glosses that stay capitalised on a common word (a proper noun or title inside the gloss).
_KEEP_CAPITAL = {"god", "lord", "christ", "messiah", "hades", "gehenna", "tartarus", "sabbath", "passover",
                 "pentecost", "gentile", "gentiles", "hebrew", "greek", "jew", "jews", "jewish", "israel",
                 "israelite", "amen", "hallelujah", "spirit", "egyptian", "roman", "latin", "aramaic", "syrian",
                 "satan", "devil", "levite", "pharisee", "sadducee", "samaritan", "nazarene", "olivet"}


def _short_def(d: str, n: Optional[int] = None) -> str:
    """The first item(s) of a Word List definition ('to post, send, restrict' -> 'to post, send'):
    ``n`` items, or as many as fit in 32 letters (at least one)."""
    items = [x.strip() for x in re.split(r",(?![^()]*\))", d or "") if x.strip()]
    if not items:
        return ""
    if n is not None:
        return ", ".join(items[:n])
    out = [items[0]]
    for it in items[1:]:
        if len(", ".join(out + [it])) > 32:
            break
        out.append(it)
    return ", ".join(out)


def _tidy_gloss(g: str, is_name: bool) -> str:
    """Whitespace, and a capital the gloss of a common word does not need ('Straight' ->
    'straight'; 'Gentiles', 'God' stay)."""
    g = re.sub(r"\s+", " ", (g or "")).strip(" ,;")
    if re.search(r"\w: \w", g):
        # a sense suffix left in any part ('Belial: destruction', LSJ 'unlucky day: mishap')
        g = "; ".join(dict.fromkeys(p.split(": ")[0].strip() for p in g.split("; ")))
    if not g or is_name:
        return g
    first = re.match(r"^([A-Z])([a-z]+)\b", g)
    if first and (first.group(1) + first.group(2)).lower() not in _KEEP_CAPITAL:
        g = g[0].lower() + g[1:]
    return g


class _Strongs:
    """Strong's Greek Dictionary (CC0): headword, derivation clause, short definition."""

    def __init__(self) -> None:
        self.entries: Dict[int, dict] = {}
        self.by_refs: Dict[Tuple[int, ...], List[int]] = defaultdict(list)
        # accent key of an unnumbered word Strong's names with its meaning: 'ἔργω (to work)',
        # 'δελφύς (the womb)', 'ἵημι (to send)' -> that meaning (the base word's own gloss)
        self.unnumbered_gloss: Dict[str, str] = {}
        path = _strongs_xml()
        if not _exists(path):
            return
        with open(_fs(path), encoding="utf-8") as fh:
            text = fh.read()
        for num, body in re.findall(r'<entry strongs="(\d+)">(.*?)</entry>', text, re.S):
            n = int(num)
            g = re.search(r'unicode="([^"]*)"', body)
            der = re.search(r"<strongs_derivation>(.*?)</strongs_derivation>", body, re.S)
            for w, mean in re.findall(r'<greek [^>]*unicode="([^"]+)"[^>]*/>\s*\(([^()<]{3,80})', der.group(1) if der else ""):
                mean = re.split(r";|, i\.e\.|, by |\bcompare\b", mean)[0].strip(" ,.")
                if mean and re.match(r"^[a-z]", mean) and not re.match(r"^(as |or |from |through |the same|a primary|obsolete)", mean):
                    self.unnumbered_gloss.setdefault(accent_key(unicodedata.normalize("NFC", w)), mean)
            dfn = re.search(r"<strongs_def>(.*?)</strongs_def>", body, re.S)
            kjv = re.search(r"<kjv_def>(.*?)</kjv_def>", body, re.S)
            ent = {
                "lemma": unicodedata.normalize("NFC", g.group(1)) if g else "",
                "derivation": re.sub(r"\s+", " ", der.group(1)).strip() if der else "",
                "def": re.sub(r"<[^>]+>", "", re.sub(r"\s+", " ", dfn.group(1))).strip() if dfn else "",
                "kjv": re.sub(r"<[^>]+>", "", re.sub(r"\s+", " ", kjv.group(1))).strip(" :-") if kjv else "",
            }
            parsed = _parse_strongs_derivation(ent["derivation"])
            ent["parents"], ent["hedged"], ent["foreign"] = parsed
            fix = _STRONGS_TYPOS.get(n)
            if fix:
                ent["parents"] = [fix.get(p, p) for p in ent["parents"]]
            info = _strongs_clause_info(ent["derivation"])
            ent["unnumbered"], ent["primary"], ent["same_as"] = info
            self.entries[n] = ent
            if ent["parents"] and not ent["hedged"]:
                self.by_refs[tuple(ent["parents"])].append(n)


# Strong's references that point at the wrong number (the entry's own words show the slip):
# Ἀρχέλαος 'from G757 and G2994' names Λαοδικεύς for λαός G2992; εὐπορέω 'from a compound of G2090
# and the base of G4197' names ἑτοιμάζω for εὖ G2095 (εὐπορία, εὔπορος: εὖ + πόρος); διαφθείρω 'from
# G1225 and G5351' names διαβάλλω for διά G1223; συγκινέω 'from G4682 and G2795' names σπαράσσω
# for σύν G4862; πεποίθησις 'from the perfect of the alternate of G3958' names πάσχω for πείθω G3982.
_STRONGS_TYPOS: Dict[int, Dict[int, int]] = {745: {2994: 2992}, 2141: {2090: 2095}, 1311: {1225: 1223},
                                             4787: {4682: 4862}, 4006: {3958: 3982}}

# Derivation links that join two homographs (the conservative family policy refuses them), as
# (child headword, head headword): Strong's derives δέομαι 'to beg' ('middle voice of G1210') and
# δεῖ 'it is necessary' from δέω 'to bind'; both belong to the other δέω, 'to lack'.  MorphGNT's
# ἐνδεής 'needy' < ἐνδέω means ἐνδέω 'to lack', not the lemma ἐνδέω 'to bind in'.  Strong's
# φύλλον 'leaf' < φυλή 'tribe', πλάξ 'flat stone' < πλάσσω 'to mould' and ἀρτέμων 'foresail' <
# ἄρτι 'now' share only their first letters (hand checks of 100 random families, 18 Nov).
_FAMILY_SLIPS: Set[Tuple[str, str]] = {("δέομαι", "δέω"), ("δεῖ", "δέω"), ("ἐνδεής", "ἐνδέω"), ("φύλλον", "φυλή"),
                                       ("πλάξ", "πλάσσω"), ("ἀρτέμων", "ἄρτι")}
_FAMILY_SLIP_KEYS = {(accent_key(a), accent_key(b)) for a, b in _FAMILY_SLIPS}

_HEDGES = re.compile(
    r"\b(probably|probable|perhaps|apparently|akin|uncertain|possibly|possible|likely|compare|"
    r"cognate|obscure|doubtful|unknown|disputed|or from|or else|or rather|through the idea|"
    r"in the sense of|as if|conjectur\w*)\b", re.I)


def _main_clause(der: str) -> str:
    """The derivation up to the first ';' outside a tag."""
    depth = 0
    for i, ch in enumerate(der):
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        elif ch == ";" and depth == 0:
            return der[:i]
    return der


def _strongs_clause_info(der: str) -> Tuple[Set[str], bool, Optional[int]]:
    """(accent keys of the unnumbered Greek words the main clause names, 'a primary word'?,
    the number after 'from the same as' when that is the whole statement).

    An unnumbered word is one Strong's prints in Greek without a number although a numbered entry
    with the same letters may exist (ἄργυρος 'from ἀργός (shining)', not G692 ἀργός 'idle'): Strong's
    is naming another word, so no other source may resolve that headword to the numbered entry."""
    main = _main_clause(der or "")
    words = {accent_key(w) for w in re.findall(r'<greek [^>]*unicode="([^"]+)"', main)}
    plain = re.sub(r"<[^>]+>", " X ", main).strip().lower()
    primary = bool(re.match(r"^(a|an)\s+(primary|prim\.)", plain))
    m = re.match(r'^\s*(?:from\s+)?the same as\s*<strongsref language="GREEK" strongs="(\d+)"\s*/>\s*$',
                 re.sub(r"\([^()]*\)", " ", main).strip())
    return words, primary, (int(m.group(1)) if m else None)


def _parse_strongs_derivation(der: str) -> Tuple[List[int], bool, bool]:
    """(Greek parents in order, hedged?, foreign?) from the main clause of a derivation."""
    if not der:
        return [], False, False
    main = der
    # cut at the first ';' that is not inside a tag
    depth = 0
    cut = len(main)
    for i, ch in enumerate(main):
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        elif ch == ";" and depth == 0:
            cut = i
            break
    main = main[:cut]
    # hedges anywhere in the clause, asides included ("from the base of G4008 (through the idea
    # of piercing)") mean the link is not a plain statement of derivation
    hedged = bool(_HEDGES.search(re.sub(r"<[^>]+>", " X ", main)))
    # "properly, the same as the base of G5457 and G5316" (φημί from φῶς + φαίνω): a gloss on the
    # sense, not a statement of derivation
    hedged = hedged or main.strip().lower().startswith("properly")
    # drop parenthesised asides (they hold comparisons, not components)
    prev = None
    while prev != main:
        prev = main
        main = re.sub(r"\([^()]*\)", " ", main)
    plain = re.sub(r"<[^>]+>", " X ", main)
    foreign = bool(re.search(r"\bof (Hebrew|Chaldee|Latin|foreign|Egyptian|Persian|Aramaic)\b", plain, re.I))
    parents = [int(n) for n in re.findall(r'<strongsref language="GREEK" strongs="(\d+)"', main)]
    return parents, hedged, foreign


def _load_gwl() -> Dict[str, dict]:
    path = _ossp_dir() / "GreekWordList.js"
    if not _exists(path):
        return {}
    with open(_fs(path), encoding="utf-8-sig") as fh:
        txt = fh.read()
    start = txt.index("{", txt.index("greekWordList"))
    end = txt.rindex("}")
    return json.loads(txt[start:end + 1])


def _load_derivation_yaml() -> Dict[str, List[str]]:
    """MorphGNT derivation.yaml: lemma -> derivation components (only 'derivation:' lists)."""
    path = _morphgnt_derivation()
    out: Dict[str, List[str]] = {}
    if not _exists(path):
        return out
    cur = None
    in_der = False
    with open(_fs(path), encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            if not line.startswith(" "):
                cur = unicodedata.normalize("NFC", line.rstrip(":").strip())
                in_der = False
                continue
            s = line.strip()
            if line.startswith("    ") and not line.startswith("     "):
                in_der = s.startswith("derivation:")
                continue
            if in_der and s.startswith("- ") and cur:
                out.setdefault(cur, []).append(unicodedata.normalize("NFC", s[2:].strip()))
    return out


# ---------------------------------------------------------------------------
# Lemma-key canonicalisation
# ---------------------------------------------------------------------------

# Strong numbers whose inflected-form entries are folded into the lemma (TBESG "a Form of" /
# "a Spelling of" one of these, with the same TBESG morph class).
_FOLD_TARGETS = {"G1473", "G4771", "G1510", "G3588", "G3778", "G1520"}

# Prepositions and inseparable prefixes: never the head of a compound.
_PREFIX_STRONGS = {1, 2095, 1418, 2255, 303, 473, 575, 1223, 1519, 1537, 1722, 1909, 2596, 3326,
                   3844, 4012, 4253, 4314, 4862, 5228, 5259, 297, 2736, 1854, 1787, 5231, 3825}
_PREFIX_BARE = {"α", "αν", "ευ", "δυσ", "ημι", "ανα", "αντι", "απο", "δια", "εισ", "εκ", "εξ", "εν",
                "επι", "κατα", "μετα", "παρα", "περι", "προ", "προσ", "συν", "υπερ", "υπο", "αμφι",
                "αρχι", "νη", "ζα", "αει", "παν", "παλιν"}

_NONCONTENT_MORPH = re.compile(r"^G:(T|CONJ|COND|PRT|PRT-N|P-1|P-2|P|R|CONJ-N)(\b|[ +]|$)")
_NONCONTENT_GWL_POS = {"C", "X"}
# Conjunctions that TBESG files as adverbs or prepositions (G:ADV, G:PREP): ὡς, ἕως, ἄχρι, μέχρι,
# πρίν join clauses ('as', 'until', 'before'), as MorphGNT's part of speech (C-) has them.
_FUNCTION_EXTRA = {"G5613", "G2193", "G0891", "G3360", "G4250"}


def _pos_from_morph(morph: str) -> Optional[str]:
    m = (morph or "").strip()
    if not m or m in ("G:",):
        return None
    head = m.split("/")[0].split("+")[0].strip()
    lang, _, typ = head.partition(":")
    typ = typ.strip()
    if lang == "N":
        return "ADJ" if typ.startswith("A") else "PROPN"
    if typ.startswith("N-PRI"):
        return "PROPN"
    if typ.startswith("N"):
        return "N"
    if typ.startswith("V"):
        return "V"
    if typ == "A-NUI":
        return "NUM"
    if typ.startswith("ADV"):
        return "ADV"
    if typ.startswith("A"):
        return "ADJ"
    if typ.startswith("PREP"):
        return "PREP"
    if typ.startswith("CONJ") or typ.startswith("COND"):
        return "CONJ"
    if typ == "T":
        return "ART"
    if typ.startswith("PRT"):
        return "PART"
    if typ.startswith("INJ"):
        return "INTERJ"
    if typ and typ[0] in "PRDFSIXQKC":
        return "PRON"
    return None


_GWL_POS = {"N": "N", "Np": "PROPN", "V": "V", "A": "ADJ", "R": "PRON", "C": "CONJ", "X": "PART",
            "I": "INTERJ", "M": "NUM", "P": "PREP", "D": "ADV"}


def _gwl_pos(ent: dict) -> Optional[str]:
    """Part of speech of a Greek Word List entry.  The list files a few capitalised names as
    indeclinable numbers ('M N' Ιωναθαν, Ιαβιν, 'M' Γεθθεμ) or plain nouns: a capitalised headword
    is never a number, and a capitalised plain noun is a name."""
    gp = (ent.get("pos") or "").split()
    if not gp or gp[0] not in _GWL_POS:
        return None
    if (ent.get("lemma") or "")[:1].isupper() and (gp[0] == "M" or gp == ["N"]):
        return "PROPN"            # also the 'N' names of the list's R section: Ῥαγουήλ, Ῥαψάκης
    return _GWL_POS[gp[0]]


# ---------------------------------------------------------------------------
# Root-family link validation (conservative policy after the 18 Nov final check)
# ---------------------------------------------------------------------------
# A derivation link (child -> parent words) joins the child to the parent's family only when
#   (a) it is a transparent compound: every preposition / prefix the source names stands at the
#       start of the child in one of its spellings (ἀπο ἀπ ἀφ, συν συμ συγ συλ συσ συ ...), every
#       other content word the source names follows with its stem (and an optional linking vowel),
#       and what is left continues the head's stem (test (c)); or
#   (b) MorphGNT's derivation list or Abbott-Smith (its '(< X)' note, or a hyphenated headword
#       'ἀπο-στέλλω' whose last part is the head) names the same head, and Strong's does not call
#       the word primary, foreign or of uncertain derivation; or
#   (c) the child (after (a)'s prefixes and content words) visibly continues the head's stem:
#       it begins with a stem of the head of at least three letters, or (head stems shorter than
#       three letters: ἄγω, ἔχω, ἵημι, εἰμί) it IS the head word (συνάγω, ἀπέχω, ἀφίημι), middle
#       and active endings counted alike.  A head stem is the headword minus one inflectional
#       ending, with only these regular variants: contract and -μι verbs (ποιε/ποι/ποιη,
#       τιθη/θη/θε), present suffixes (-ζω -σσω -ττω -λλω -αινω -υνω -πτω -σκω -ευω, the nasal
#       infix of λαμβάνω/λανθάνω/μανθάνω/τυγχάνω), a few listed principal-part stems
#       (_FAMILY_OBLIQUE: θνῄσκω θαν-, πάσχω παθ-/πενθ-, τρέχω δραμ-/δρομ-), one stem-final consonant
#       of the same class (γ κ χ ξ / β π φ ψ μ / δ τ θ, stems of four letters or more) or one vowel
#       grade of _FAMILY_ABLAUT (ε/ο/α, ει/οι/ι, ευ/ου/υ, η/α/ε, ω/ο).
# A name (PROPN) needs test (a)/(c) even when a source supports the link, and a link Abbott-Smith
# contradicts ('(< βαίνω)' for βαθμός, which Strong's puts under βάθος) is refused.
# Never: a function word (article, conjunction, particle, personal or relative pronoun), a
# preposition or prefix, a bare suffix ('-θεν') or a proper name heading common words (πέτρα is
# not filed under Πέτρος); a preposition or function word is its own family.  Everything else is
# its own family (root_source 'self').  Examples the old walk joined and this one keeps apart:
# πορεύομαι / πεῖρα, ἄρτος and ἀριθμός / αἴρω, ὕδωρ / ὕω, στρέφω / τρέπω, οὗτος / αὐτός,
# δῆμος / δέω, τότε / τε, ἄνθρωπος / ἀνήρ, περί / πέραν, ὀργή / ὀρέγω, ἥττων / κακός.

_FAMILY_PREFIX_SPELLINGS: Dict[str, Tuple[str, ...]] = {
    "αντι": ("αντι", "αντ", "ανθ"), "απο": ("απο", "απ", "αφ"), "ανα": ("ανα", "αν"),
    "δια": ("δια", "δι"), "εισ": ("εισ", "εσ"), "εκ": ("εκ", "εξ", "εγ"), "εξ": ("εξ", "εκ"),
    "εν": ("εν", "εμ", "εγ", "ελ", "ερ"), "επι": ("επι", "επ", "εφ"), "κατα": ("κατα", "κατ", "καθ"),
    "μετα": ("μετα", "μετ", "μεθ"), "παρα": ("παρα", "παρ"), "περι": ("περι",), "προσ": ("προσ",),
    "προ": ("προ", "πρου", "πρω"), "συν": ("συν", "συμ", "συγ", "συλ", "συρ", "συσ", "συ"),
    "υπερ": ("υπερ",), "υπο": ("υπο", "υπ", "υφ"), "αμφι": ("αμφι", "αμφ"),
    "α": ("α", "αν"), "αν": ("αν", "α"), "ευ": ("ευ",), "δυσ": ("δυσ", "δυ"), "ημι": ("ημι",),
    "αρχι": ("αρχι", "αρχ"), "νη": ("νη",), "ζα": ("ζα",), "αει": ("αει",),
    "παν": ("παντο", "παντ", "παν", "παμ", "παγ", "πασ"), "πασ": ("παντο", "παντ", "παν", "παμ", "παγ", "πασ"),
    "παλιν": ("παλιν", "παλιμ", "παλιγ", "παλι"), "ημισυ": ("ημι",), "κατω": ("κατω", "κατ"),
    "εξω": ("εξω", "εξ"), "εντοσ": ("εντο", "εντ"), "υπερανω": ("υπερανω", "υπερ"),
    "αμφοτεροσ": ("αμφοτερ", "αμφι", "αμφ"),
}

# Short words whose stem in compounds is not the headword minus its ending (πᾶς -> παντο-).
_FAMILY_OBLIQUE: Dict[str, Tuple[str, ...]] = {
    "πασ": ("παντ", "παν", "παμ", "παγ"), "μεγασ": ("μεγαλ", "μεγα"), "πολυσ": ("πολυ", "πολλ"),
    "ανηρ": ("ανδρ",), "γυνη": ("γυναικ", "γυνα"), "πατηρ": ("πατρ", "πατερ"),
    "μητηρ": ("μητρ", "μητερ"), "χειρ": ("χειρ",), "πουσ": ("ποδ",), "ουσ": ("ωτ",),
    "νουσ": ("νοε", "νοη", "νου"), "γη": ("γεω", "γε"), "υδωρ": ("υδατ", "υδρ"), "φωσ": ("φωτ",),
    "ουσια": ("ουσι",), "ναυσ": ("ναυ",), "βουσ": ("βου", "βο"), "οφισ": ("οφι", "οφε"),
    # the other principal-part stems of a few verbs (θάνατος / ἔθανον, πάθος / ἔπαθον)
    "θνησκω": ("θαν", "θνη"), "αποθνησκω": ("αποθαν", "αποθνη"), "πασχω": ("παθ", "πενθ"),
    "πιπτω": ("πτω", "πεσ"), "γινομαι": ("γεν", "γον", "γιν"), "γινωσκω": ("γνω", "γνο"),
    "τρεχω": ("δραμ", "δρομ"), "τικτω": ("τεκ", "τοκ"), "ερχομαι": ("ελθ", "ελευσ", "ελευθ"),
    "μιμνησκω": ("μνη", "μνα", "μνε"), "καλεω": ("κλη",),     # μι-μνῄσκω; κλῆσις, ἐκκλησία
}

_FAMILY_ENDINGS = sorted([
    "ομαι", "ουμαι", "ωμαι", "αμαι", "υμι", "ημι", "ωμι", "μι", "εω", "αω", "οω", "ω",
    "ευσ", "ουσ", "ιοσ", "οσ", "ον", "ησ", "ασ", "ισ", "υσ", "ωσ", "ων", "ωρ", "ηρ",
    "α", "η", "ι", "υ", "ο", "ξ", "ψ", "σ", "ν",
], key=len, reverse=True)

# One vowel-grade change inside a stem (the last vowel group): λεγ/λογ, τρεπ/τροπ, στελ/στολ/σταλ,
# λειπ/λοιπ/λιπ, φευγ/φυγ, σπευδ/σπουδ, ληθ/λαθ, θη/θε, γνω/γνο.  Nothing else (στρεφ is not τρεπ).
_FAMILY_ABLAUT: Tuple[Tuple[str, str], ...] = (
    ("ει", "οι"), ("ει", "ι"), ("οι", "ει"), ("οι", "ι"), ("ευ", "ου"), ("ευ", "υ"), ("ου", "ευ"),
    ("ε", "ο"), ("ε", "α"), ("ο", "ε"), ("α", "ε"), ("α", "ο"), ("α", "η"), ("η", "α"), ("η", "ε"),
    ("ω", "ο"), ("ο", "ω"),
)
_FAMILY_CONSONANT_CLASSES = ("γκχξ", "βπφψμ", "δτθ")    # σ / ζ only through the -ζω, -σσω rules
_FAMILY_VOWELS = "αεηιουω"


@lru_cache(maxsize=None)
def _family_base_stems(bare: str) -> Tuple[str, ...]:
    """Stems of a headword for the family test (see the policy above), longest first."""
    out: List[str] = []

    def add(s: Optional[str]) -> None:
        if s and s not in out:
            out.append(s)

    for e in _FAMILY_ENDINGS:
        if bare.endswith(e) and len(bare) > len(e):
            add(bare[: -len(e)])
            break
    for s in list(out):
        # contract verbs and -μι verbs: ποιε- -> ποι-/ποιη-, τιμα- -> τιμ-/τιμη-, φανερο- -> φανερ-
        if s[-1:] in ("ε", "α", "ο") and bare.endswith(("εω", "αω", "οω", "εομαι", "αομαι", "οομαι",
                                                         "ουμαι", "ωμαι")):
            add(s[:-1])
            add(s[:-1] + {"ε": "η", "α": "η", "ο": "ω"}[s[-1]])
        if bare.endswith(("ημι", "ωμι")):
            # reduplicated presents: τιθη -> θη/θε, διδω -> δω/δο, ιστη -> στη/στα
            core = s[2:] if len(s) >= 4 and s[1] == "ι" else s[1:] if s.startswith("ι") and len(s) >= 4 else s
            add(core)
            if core[-1:] in "ηω":
                add(core[:-1] + {"η": "ε", "ω": "ο"}[core[-1]])
            if core.endswith("στη"):
                add(core[:-1] + "α")
        if bare.endswith("νυμι") and s.endswith("νυ"):
            add(s[:-2].rstrip("ν"))
        if s.endswith("ευ"):
            add(s[:-1])                              # πορευ- / πορε-ία
        for suf, repl in (("σσ", ("κ", "γ", "χ", "ξ")), ("ττ", ("κ", "γ", "χ", "ξ")), ("ζ", ("δ", "γ", "σ", "")),
                          ("λλ", ("λ",)), ("αιν", ("αν",)), ("υν", ("υ",)), ("πτ", ("π", "β", "φ")),
                          ("ισκ", ("",)), ("σκ", ("", "χ", "κ")), ("ν", ("",))):
            if s.endswith(suf) and bare.endswith(("ω", "ομαι")) and len(s) - len(suf) >= 2:
                for r in repl:
                    add(s[: -len(suf)] + r)
        m = re.match(r"^(.*?)([μνγ])([βπφθτδχκγ])αν$", s)
        if m and bare.endswith(("ανω", "ανομαι")):
            add(m.group(1) + m.group(3))             # λαμβαν- -> λαβ, λανθαν- -> λαθ, τυγχαν- -> τυχ
        if s.endswith("αν") and bare.endswith(("ανω", "ανομαι")) and len(s) >= 5:
            add(s[:-2])                              # αὐξάνω -> αυξ, ἁμαρτάνω -> αμαρτ
    base = list(out)
    # one consonant of the same class at the end of a stem of four letters or more (λεγ / λεξ
    # stay apart from δεχ / δεξ: δεξιός is not δέχομαι) ...
    for s in base:
        for cls in _FAMILY_CONSONANT_CLASSES:
            if len(s) >= 4 and s[-1] in cls:
                for c in cls:
                    add(s[:-1] + c)
    # ... or one vowel grade in the last vowel group of the stem (not both); a stem of three
    # letters or fewer that begins with its vowel keeps its vowel (ἐργ- is not ὀργ-)
    for s in base:
        m = re.search(r"([αεηιουω]+)([^αεηιουω]*)$", s)
        if not m or (m.start(1) == 0 and len(s) <= 3):
            continue
        for a, b in _FAMILY_ABLAUT:
            if m.group(1) == a:
                add(s[: m.start(1)] + b + m.group(2))
    for s in _FAMILY_OBLIQUE.get(bare, ()):
        add(s)                                       # listed stems take no further variant
    return tuple(sorted(out, key=len, reverse=True))


def _family_voice_twins(bare: str) -> Set[str]:
    """A verb's headword under either voice: ἔρχομαι / ἔρχω, πορεύω / πορεύομαι."""
    out = {bare}
    if bare.endswith("ομαι"):
        out.add(bare[:-4] + "ω")
    elif bare.endswith("ουμαι"):
        out.update({bare[:-5] + "εω", bare[:-5] + "οω"})
    elif bare.endswith("ωμαι"):
        out.add(bare[:-4] + "αω")
    elif bare.endswith("ω"):
        out.add(bare[:-1] + "ομαι")
    return out


def _family_continues(rest: str, head_bare: str, after_word: bool = False) -> bool:
    """Test (c): ``rest`` is the head word itself or begins with one of its stems of at least
    three letters.  ``after_word``: a content word precedes (οἰκο-δομ-, φιλ-άδελφος), so the
    head's first vowel may be elided or contracted with the linking vowel (κακ-οῦργος)."""
    if not rest or not head_bare:
        return False
    rests = [rest]
    if len(rest) > 5 and rest[1] == "ι" and rest[0] == rest[2] and rest[0] not in _FAMILY_VOWELS:
        rests.append(rest[2:])                       # reduplicated present: μι-μνῄσκω, πι-πράσκω
    for r in rests:
        if _family_voice_twins(r) & _family_voice_twins(head_bare):
            return True
    for s in _family_base_stems(head_bare):
        if len(s) < 3:
            continue
        cands = [s]
        if after_word and s[0] in _FAMILY_VOWELS and len(s) >= 4:
            cands += [s[1:], "ου" + s[1:] if s[0] == "ε" else None, "ω" + s[1:] if s[0] in "αο" else None]
        for c in cands:
            if c and len(c) >= 3 and any(r.startswith(c) for r in rests):
                return True
    return False


def _family_visible(child_bare: str, prefixes: Sequence[str], contents: Sequence[str]) -> bool:
    """Tests (a) and (c): ``prefixes`` (bare canonical spellings) stand at the start of the child,
    then every content word of ``contents`` in order; the last content word is the head."""
    if not child_bare or not contents:
        return False
    rests = {child_bare}
    for p in prefixes:
        nxt: Set[str] = set()
        for r in rests:
            for sp in _FAMILY_PREFIX_SPELLINGS.get(p, (p,)):
                if r.startswith(sp) and len(r) > len(sp) + 1:
                    nxt.add(r[len(sp):])
        if not nxt:
            return False
        rests = nxt
    # after a prefix or a content word the head's first vowel may be contracted away (ἀ-εργός ->
    # ἀργός, κακ-οῦργος)
    after_word = bool(prefixes)
    for c in contents[:-1]:
        nxt = set()
        stems = [s for s in _family_base_stems(c) if len(s) >= 3] + list(_FAMILY_PREFIX_SPELLINGS.get(c, ()))
        if not stems:
            stems = [c]
        for r in rests:
            for s in stems:
                if r.startswith(s) and len(r) > len(s) + 1:
                    rr = r[len(s):]
                    nxt.add(rr)
                    if rr[:1] in _FAMILY_VOWELS:
                        nxt.add(rr[1:])
        if not nxt:
            return False
        rests = nxt
        after_word = True
    return any(_family_continues(r, contents[-1], after_word) for r in rests)


def _abbott_smith_file() -> Path:
    return _open_dir() / "Lexicon_Abbott_Smith_TEI" / "abbott-smith.tei.xml"


def _load_abbott_smith() -> Dict[str, dict]:
    """Abbott-Smith, Manual Greek Lexicon of the NT (1922; TEI markup, public domain): headword ->
    {'parts': the hyphenated headword split at '-', 'from': Greek words its '(< X)' etymology note
    names, 'gloss': {word: English gloss the note gives for it}}.  Only the headword and the
    etymology note are read."""
    path = _abbott_smith_file()
    out: Dict[str, dict] = {}
    if not _exists(path):
        return out
    with open(_fs(path), encoding="utf-8") as fh:
        text = fh.read()
    for m in re.finditer(r'<entry n="([^"]*)">(.*?)</entry>', text, re.S):
        head = unicodedata.normalize("NFC", m.group(1).split("|")[0].split("_")[0].strip())
        body = m.group(2)
        orth = re.search(r"<orth>([^<]*)</orth>", body)
        parts = [p for p in (orth.group(1).strip() if orth else "").split("-")]
        froms: List[str] = []
        glosses: Dict[str, str] = {}
        for seg in re.findall(r'<seg type="derivation">(.*?)</seg>', body, re.S):
            plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", seg)).replace("&lt;", "<").strip()
            mm = re.match(r"^\(\s*<\s*([^)]*)\)", plain)
            if not mm:
                continue
            items = [x.strip() for x in mm.group(1).split(";")[0].split(",")]
            last_greek = None
            for it in items:
                w = it.split()[0] if it.split() else ""
                if w and re.match(r"^[Ͱ-Ͽἀ-῿]", w) and not w.endswith(("-", ".")):
                    froms.append(unicodedata.normalize("NFC", w))
                    last_greek = froms[-1]
                elif (last_greek and re.match(r"^[a-z][a-z' ]+$", it) and last_greek not in glosses
                      and not re.match(r"^(cf|v|q|id|sc|lat|heb|aram|al)\b", it)):
                    glosses[last_greek] = it.strip(" .")        # '(< λέπω, to peel)'
                else:
                    last_greek = None
        senses = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", g)).strip(" ,.;:")
                  for g in re.findall(r"<gloss>(.*?)</gloss>", body, re.S)[:3]]
        out.setdefault(head, {"parts": parts, "from": froms, "gloss": glosses,
                              "senses": [s for s in senses if len(s) > 2]})
    return out


class _Lexicon:
    """All lexical data, built once per process."""

    def __init__(self) -> None:
        self.tbesg = _Tbesg()
        self.strongs = _Strongs()
        self.gwl = _load_gwl()
        self.mgnt_deriv = _load_derivation_yaml()
        self.fold: Dict[str, str] = {}
        self._build_fold()
        self.entries: Dict[str, LemmaEntry] = {}
        self._entry_info: Dict[str, dict] = {}
        self.gwl_key_to_lemma_key: Dict[str, str] = {}
        self._root_cache: Dict[Tuple[str, bool], Tuple[str, str, str, str]] = {}
        self.head_override: Dict[str, str] = {}
        self._fix_name_heads()
        self.abbott = _load_abbott_smith()
        self._abbott_by_bare: Dict[str, dict] = {}
        for h, ent in self.abbott.items():
            self._abbott_by_bare.setdefault(greek_bare(h), ent)
            orth = "".join(ent["parts"])
            if orth:
                self._abbott_by_bare.setdefault(greek_bare(orth), ent)
        self.head_gwl: Dict[str, str] = {}      # 'grc:' family head -> the Word List key naming it
        # Abbott-Smith's etymology notes gloss the words they name: '(< πόρος, a ford, a passage)'
        self.abbott_gloss: Dict[str, str] = {}
        for ent in self.abbott.values():
            for w, g in ent["gloss"].items():
                self.abbott_gloss.setdefault(accent_key(w), g)
        self.tbesh = _Tbesh()
        self.tflsj = _TflsjExtra()
        self.lsj = _Lsj()
        self.tagnt_folded: Dict[str, Set[str]] = defaultdict(set)   # target -> eStrongs TAGNT folds in
        self._gloss_cache: Dict[str, str] = {}
        self._meaning_cache: Dict[str, str] = {}

    # -- keys ---------------------------------------------------------------------------------
    def _build_fold(self) -> None:
        t = self.tbesg
        for d, row in t.rows.items():
            rel = row["relation"]
            if rel not in ("a Form of", "a Spelling of"):
                continue
            tgt = re.match(r"(G\d+)", row["target"] or "")
            if not tgt:
                continue
            tgt_e = t.estrong_of.get(row["target"].split()[0], _gkey(int(tgt.group(1)[1:])))
            if tgt_e not in _FOLD_TARGETS:
                continue
            trow = t.primary(tgt_e)
            src_m, tgt_m = row["morph"], (trow or {}).get("morph", "")
            if src_m in ("", "G:") or src_m == tgt_m:
                self.fold[row["estrong"]] = tgt_e

    def add_tagnt_folds(self, dict_forms: Dict[str, Counter]) -> None:
        """Fold X -> Y where TAGNT files words tagged X under Y's dictionary form (μέ -> ἐγώ)."""
        t = self.tbesg
        for d, row in t.rows.items():
            if row["relation"] not in ("a Form of", "a Spelling of"):
                continue
            tgt = re.match(r"(G\d+[A-Z]?)", row["target"] or "")
            if not tgt:
                continue
            tgt_e = t.estrong_of.get(tgt.group(1))
            trow = t.primary(tgt_e) if tgt_e else None
            if not trow or not trow["head"]:
                continue
            forms = dict_forms.get(row["estrong"])
            if not forms:
                continue
            top, n = forms.most_common(1)[0]
            heads = {accent_key(h.strip()) for h in top.split(",")}
            if accent_key(trow["head"]) in heads and n >= 0.9 * sum(forms.values()):
                self.fold[row["estrong"]] = tgt_e
                if accent_key(row["head"]) != accent_key(trow["head"]):
                    self.tagnt_folded[tgt_e].add(row["estrong"])     # οἶδα G6063 -> εἴδω G1492

    def canonical(self, key: Optional[str]) -> Optional[str]:
        if not key:
            return key
        seen = set()
        while key in self.fold and key not in seen:
            seen.add(key)
            key = self.fold[key]
        return key

    def key_for_dstrong(self, d: str) -> str:
        """dStrong (G3004H) -> lemma key (G3004); letters kept only where one eStrong number
        covers different headwords (G0001G Alpha / G0001H ἆ)."""
        t = self.tbesg
        e = t.estrong_of.get(d)
        if e is None:
            m = re.match(r"^G(\d+)", d)
            e = _gkey(int(m.group(1))) if m else d
        rows = t.by_estrong.get(e, [])
        heads = {accent_key(r["head"]) for r in rows
                 if r["head"] and not r["head"].startswith("[") and r["relation"] != "a Spelling of"}
        if len(heads) > 1:
            row = t.rows.get(d)
            prim = t.primary(e)
            if row and prim and accent_key(row["head"]) != accent_key(prim["head"]) and row["relation"] != "a Spelling of":
                return self.canonical(d) or d
        return self.canonical(e) or e

    def key_for_headword(self, head: str, same_case: bool = False) -> Optional[str]:
        """TBESG headword -> eStrong when exactly one entry carries that (accented) headword.
        ``same_case``: a lower-case word does not take a proper name's number nor a capitalised
        word a common word's (the LXX's τύραννος 'tyrant' is not Τύραννος, δορκάς 'gazelle' is
        not Δορκάς, χλόη 'grass' is not Χλόη, ῥώμη 'strength' is not Ῥώμη)."""
        hits = self.tbesg.by_head.get(accent_key(head))
        if hits and same_case:
            # (a verb is never a name: TBESG's capitalised 'Σαββατίζω' is σαββατίζω)
            hits = {e for e in hits if self._tbesg_head_case(e) == head[:1].isupper()
                    or ((self.tbesg.primary(e) or {}).get("morph") or "").startswith("G:V")}
        if hits and len(hits) == 1:
            return self.canonical(next(iter(hits)))
        return None

    def _tbesg_head_case(self, estrong: str) -> bool:
        """True when the eStrong entry's headword is capitalised (Strong's form for the names
        _fix_name_heads repairs)."""
        h = self.head_override.get(estrong)
        if not h:
            row = self.tbesg.primary(estrong)
            h = row["head"] if row else ""
        return h[:1].isupper()

    def _tbesg_lists(self, estrong: str, lemma: str) -> bool:
        """True when TBESG prints ``lemma`` among the headword forms of ``estrong``
        ('Νεεμάν, Ναιμάν')."""
        ak = accent_key(lemma)
        for r in self.tbesg.by_estrong.get(estrong, []):
            if any(accent_key(h) == ak for h in re.split(r"[,=]", r["raw_head"]) if h.strip()):
                return True
        return False

    def gwl_lemma_key(self, gkey: str) -> str:
        """Open Scriptures Greek Word List key (e.g. 'ορος.1') -> lemma key."""
        hit = self.gwl_key_to_lemma_key.get(gkey)
        if hit:
            return hit
        ent = self.gwl.get(gkey, {})
        strong = ent.get("strong")
        lemma = unicodedata.normalize("NFC", ent.get("lemma") or gkey.split(".")[0])
        key = None
        if strong and str(strong).isdigit():
            key = self.canonical(_gkey(int(strong)))
        if key is None:
            # the word's own TBESG entry first (ἐπισκευάζω G7447, δέος G6015, φονευτής G9655): the
            # Word List 'v' pointer also links distinct headwords (ἐπισκευάζω -> ἀποσκευάζω).  The
            # capitalisation must agree: the common nouns τύραννος, δορκάς, χλόη, εὐοδία, ῥώμη
            # and πέτρος are not the NT names Tyrannus, Dorcas, Chloe, Euodia, Rome and Peter.
            key = self.key_for_headword(lemma, same_case=True)
        vent = self.gwl.get(ent.get("v") or "", None)
        if key is None and vent:
            vs = vent.get("strong")
            vkey = _gkey(int(vs)) if vs and str(vs).isdigit() else None
            if _spelling_variant(lemma, vent.get("lemma", "")) or (vkey and self._tbesg_lists(vkey, lemma)):
                key = self.canonical(vkey) if vkey else self.key_for_headword(vent.get("lemma", ""))
        if key is None and accent_key(lemma) == greek_bare(lemma):
            # the Word List prints most names unaccented (Εσθηρ); TBESG has them accented
            # (Ἐσθήρ).  Use TBESG's number only when exactly one TBESG name has these letters.
            hits = self.tbesg.by_bare.get(greek_bare(lemma), set())
            if len(hits) == 1:
                e = next(iter(hits))
                prim = self.tbesg.primary(e)
                # a person / place / title (N:N-M-P, N:N--L, G:N-PRI), capitalised on both
                # sides: Ιαμιν the man is not TBESG's ιαμίν 'mules'
                if (prim and re.search(r"(-[PLT]G?$|N-PRI)", prim["morph"])
                        and prim["head"][:1].isupper() == lemma[:1].isupper()):
                    key = self.canonical(e)
        if key is None:
            key = "grc:" + lemma
        self.gwl_key_to_lemma_key[gkey] = key
        return key

    # -- lemma metadata -------------------------------------------------------------------------
    def note_lemma(self, key: str, *, head: str = "", gloss: str = "", pos: Optional[str] = None,
                   source: str = "", gwl_key: Optional[str] = None) -> None:
        info = self._entry_info.setdefault(key, {"heads": Counter(), "gloss": "", "pos": None,
                                                 "sources": set(), "gwl": set()})
        if head:
            info["heads"][unicodedata.normalize("NFC", head)] += 1
        if gloss and not info["gloss"]:
            info["gloss"] = gloss
        if pos and not info["pos"]:
            info["pos"] = pos
        if source:
            info["sources"].add(source)
        if gwl_key:
            info["gwl"].add(gwl_key)

    def _fix_name_heads(self) -> None:
        """TBESG rows of a proper name printed with a lower-case headword whose letters differ from
        Strong's capitalised lemma (G2748 Kidron: TBESG 'κέδρος' = 'cedar', Strong's 'Κεδρών').
        Strong's form becomes the headword and the lower-case word no longer finds the name (the
        LXX's κέδρος 'cedar' is not Kidron)."""
        t = self.tbesg
        for d, row in t.rows.items():
            head = row["head"]
            if (not head or head.startswith("[") or not head[:1].islower()
                    or not re.search(r"(-[PLT]G?$|N-PRI)", row["morph"])):
                continue
            n = _strong_num(row["estrong"])
            ent = self.strongs.entries.get(n) if n is not None and n <= 5624 else None
            s = (ent or {}).get("lemma", "")
            if not s or not s[:1].isupper() or greek_bare(s) == greek_bare(head):
                continue
            e = row["estrong"]
            t.by_head.get(accent_key(head), set()).discard(e)
            t.by_bare.get(greek_bare(head), set()).discard(e)
            t.by_head[accent_key(s)].add(e)
            t.by_bare[greek_bare(s)].add(e)
            self.head_override[e] = s

    def headword(self, key: str) -> str:
        hit = self.head_override.get(key)
        if hit:
            return hit
        n = _strong_num(key)
        if n is not None and key.startswith("G"):
            row = self.tbesg.rows.get(key) or self.tbesg.primary(key)
            if row and row["head"] and not row["head"].startswith("["):
                return row["head"]
            ent = self.strongs.entries.get(n)
            if ent and ent["lemma"]:
                return ent["lemma"]
        if key.startswith("grc:"):
            return key[4:]
        info = self._entry_info.get(key)
        if info and info["heads"]:
            return info["heads"].most_common(1)[0][0]
        return key

    # -- glosses ---------------------------------------------------------------------------------
    # A lemma's gloss, in order: TBESG's brief gloss (cols 1-7, CC BY) - for a Strong number split
    # into meanings ('lord: God', 'lord: master') the shared general part before ': ', for a name
    # every person's / place's gloss ('Jesus; Joshua'); the LXX name's Hebrew original (Word List
    # 'src H4813' -> TBESH 'Miriam'); a verb TAGNT folds in (οἶδα 'to know' into εἴδω); then for
    # words without a TBESG number: TAGNT's dictionary gloss, the Word List definition, the gloss
    # TBESG / TFLSJ give the same headword (the Word List spells some differently: ῥοά / ῥόα), the
    # Hebrew word a transliteration renders (TBESH), and last the first translation Liddell-Scott-
    # Jones gives (Perseus LSJ XML, CC BY-SA 4.0).  Never the Greek headword itself.

    def gloss(self, key: str) -> str:
        hit = self._gloss_cache.get(key)
        if hit is None:
            hit = self._gloss_cache[key] = self._gloss_and_source(key)[0]
        return hit

    def gloss_source(self, key: str) -> str:
        return self._gloss_and_source(key)[1]

    def _gloss_and_source(self, key: str) -> Tuple[str, str]:
        g, src = self._raw_gloss(key)
        g = _tidy_gloss(g, self.pos(key) == "PROPN" or self.headword(key)[:1].isupper())
        return g, (src if g else "")

    def _tbesg_rows_of(self, key: str) -> List[dict]:
        if key in self.tbesg.by_estrong:
            prim = self.tbesg.primary(key)
            rows = self.tbesg.by_estrong[key]
            return ([prim] if prim else []) + [r for r in rows if r is not prim]
        row = self.tbesg.rows.get(key)
        return [row] if row else []

    def _tbesg_gloss(self, key: str) -> str:
        rows = self._tbesg_rows_of(key)
        gl = [r["gloss"].strip() for r in rows if r["gloss"].strip()]
        if not gl:
            return ""
        if self.pos(key) == "PROPN":
            # 'Jesus; Joshua'; a name's sense suffix goes ('Belial: destruction' -> 'Belial')
            return "; ".join(dict.fromkeys(g.split(": ")[0].strip() for g in gl))
        if ": " not in gl[0]:
            return gl[0]
        general, sense = (x.strip() for x in gl[0].split(": ", 1))
        senses = {g.split(": ", 1)[1].strip() for g in gl if ": " in g}
        if (len(senses) == 1 and sense[:1].isupper() and sense.lower() != general.lower()
                and ": " not in sense):
            return f"{sense} ({general})"                          # one sense: 'hell: Hades' -> 'Hades (hell)'
        return general                                             # 'lord: God', 'lord: master' -> 'lord'

    def _gwl_defs(self, key: str) -> List[str]:
        info = self._entry_info.get(key) or {}
        keys = sorted(info.get("gwl", ()))
        if key in self.head_gwl:
            keys.append(self.head_gwl[key])
        out = []
        for g in keys:
            ent = self.gwl.get(g, {})
            if ent.get("def"):
                out.append(ent["def"])
            v = self.gwl.get(ent.get("v") or "", {})
            if not ent.get("def") and v.get("def") and _spelling_variant(ent.get("lemma", ""), v.get("lemma", "")):
                out.append(v["def"])
        return out

    def _lxx_common_def(self, key: str) -> str:
        """The Word List definition of an LXX lemma of this key whose Word List entry is a common
        word (pos not 'Np', lower-case headword), else ''."""
        info = self._entry_info.get(key) or {}
        for g in sorted(info.get("gwl", ())):
            ent = self.gwl.get(g, {})
            if ent.get("def") and ent.get("lemma", "")[:1].islower() and not (ent.get("pos") or "").startswith("Np"):
                return _short_def(ent["def"], 1)
        return ""

    def _hebrew_src_glosses(self, key: str) -> List[str]:
        info = self._entry_info.get(key) or {}
        out: List[str] = []
        for g in sorted(info.get("gwl", ())):
            for part in (self.gwl.get(g, {}).get("src") or "").split(","):
                m = re.match(r"^\s*H(\d+)", part)
                if m:
                    out += self.tbesh.glosses(int(m.group(1)))
        return list(dict.fromkeys(out))

    def _raw_gloss(self, key: str) -> Tuple[str, str]:
        is_name = self.pos(key) == "PROPN"
        if key.startswith("G"):
            g = self._tbesg_gloss(key)
            if g:
                src = "TBESG"
                lead = _GLOSS_WORD_LIST_FIRST.get(key)
                defs = self._gwl_defs(key)
                if lead and defs:
                    g = _short_def(defs[0], lead) + "; " + g          # γίνομαι, ἔθνος
                    src = "OSSP-GWL+TBESG"
                if is_name:
                    extra = [h for h in self._hebrew_src_glosses(key) if h not in g.split("; ")]
                    if extra:
                        g = "; ".join([g] + extra)                    # Μαρία 'Mary; Miriam'
                        src = "TBESG+TBESH"
                common = self._lxx_common_def(key)
                if common and g[:1].isupper() and common.lower() not in g.lower():
                    # a New Testament name / title the Septuagint uses as a common word:
                    # Χριστός 'Christ; anointed', ἐλαιών 'an olive orchard; Olivet'
                    g = g + "; " + common.lower() if is_name else common + "; " + g
                    src = "OSSP-GWL+TBESG"
                for f in sorted(self.tagnt_folded.get(key, ())):
                    fg = self._tbesg_gloss(f)
                    if fg and self.pos(f) == "V" and fg.lower() not in g.lower():
                        g = g + "; " + fg                             # εἴδω + οἶδα 'to know'
                return g, src
            ent = self.strongs.entries.get(_strong_num(key) or -1)
            if ent and (ent["kjv"] or ent["def"]):
                return (ent["kjv"] or ent["def"])[:80], "Strongs"
        info = self._entry_info.get(key) or {}
        if info.get("gloss"):
            return info["gloss"], "TAGNT"
        defs = self._gwl_defs(key)
        if defs:
            return _short_def(defs[0]), "OSSP-GWL"
        head = self.headword(key)
        g = self._same_headword_gloss(key, head)
        if g:
            return g, "TBESG/TFLSJ"
        heb = self._hebrew_src_glosses(key)
        if heb:
            return "; ".join(heb), "TBESH"
        if not is_name:
            g = self.lsj.gloss(head)
            if g:
                return g, "LSJ"
        return "", ""

    def _same_headword_gloss(self, key: str, head: str) -> str:
        """The gloss TBESG or TFLSJ give a headword with the same letters (accents aside; a neuter
        headword also in its plural, περισπόριον / περισπόρια) and the same capitalisation, when
        all such entries agree."""
        b0 = greek_bare(head)
        if not b0:
            return ""
        want_name = head[:1].isupper()
        for b in (b0, b0[:-2] + "α" if b0.endswith("ον") and len(b0) > 4 else None):
            if not b:
                continue
            gl: List[str] = []
            for e in self.tbesg.by_bare.get(b, ()):
                row = self.tbesg.primary(e)
                if row and row["gloss"] and self._tbesg_head_case(e) == want_name:
                    gl.append(row["gloss"].split(": ")[0].strip())
            if not gl:
                for row in self.tflsj.by_bare.get(b, ()):
                    if row["gloss"] and row["head"][:1].isupper() == want_name:
                        gl.append(row["gloss"].split(": ")[0].strip())
            gl = list(dict.fromkeys(gl))
            if len(gl) == 1:
                return gl[0]
        return ""

    def root_meaning(self, key: str) -> str:  # noqa: C901
        """The family head's own meaning (LemmaEntry.root_gloss), never a member's gloss.  A word
        the Studio prints: its general gloss (gloss() as above; a few heads whose TBESG gloss is
        one New Testament sense take the Word List's general definition: στέλλω 'to avoid' ->
        'to post, send', δίκη 'condemnation' -> 'justice').  A base word only the derivation
        sources name: the meaning they give it - the Word List definition (κῦρος 'supreme
        power'), Abbott-Smith's etymology note ('< πόρος, a ford, a passage'), Strong's
        ('ἔργω (to work)', 'δελφύς (the womb)')."""
        cache = self._meaning_cache
        if key in cache:
            return cache[key]
        m = _ROOT_MEANING_TEXT.get(key[4:] if key.startswith("grc:") else key, "")
        how = None if m else _ROOT_MEANING_OVERRIDE.get(key)
        if how == "abbott-smith":
            ent = self._abbott_entry(key)
            m = _short_def(ent["senses"][0]) if ent and ent["senses"] else ""
        elif how == "word-list":
            defs = self._gwl_defs(key)
            m = _short_def(defs[0], 1) if defs else ""
        elif how == "lsj":
            m = _tidy_gloss(self.lsj.gloss(self.headword(key), general=True), False)
        n = _strong_num(key)
        ak = accent_key(self.headword(key))
        own = key in self._entry_info or (key.startswith("G") and self._tbesg_rows_of(key))
        if not m and not (key.startswith("G") and n is not None and n <= 5624):
            # a base Strong's names without a number of its own, with the meaning the derivation
            # uses (πρέσβυς 'elderly' for πρεσβύτερος, not the Word List's 'an ambassador'); never
            # Strong's etymological asides ('contraction for obsolete', 'perhaps as bent', 'of Latin
            # origin'), which the 18 Nov re-check found shown as family meanings (σῶς for σῴζω)
            cand = _tidy_gloss(self.strongs.unnumbered_gloss.get(ak, ""), False)
            if not _STRONGS_ASIDE.search(cand):
                m = cand
        if not m and own:
            m = self.gloss(key)
            if m and self.gloss_source(key) == "LSJ":
                m = _tidy_gloss(self.lsj.gloss(self.headword(key), general=True), False) or m
        if not m:
            defs = self._gwl_defs(key)
            m = (_short_def(defs[0]) if defs else "") or self.abbott_gloss.get(ak, "")
            m = _tidy_gloss(m, False)
        cache[key] = m
        return m

    def pos(self, key: str) -> str:
        if key.startswith("G"):
            row = self.tbesg.rows.get(key) or self.tbesg.primary(key)
            p = _pos_from_morph(row["morph"]) if row else None
            if p == "PROPN" and row and not self._is_name_row(row, key):
                # TBESG's 'N:' (name) class also holds lower-case Septuagint words with no person,
                # place or title mark (κοιλάς 'valley', λοβός, νάβλα, οἰφί, τήγανον) and the
                # lower-case ἐλαιών 'olive grove' (Olivet): common nouns
                p = "N"
            if p == "ADJ" and row and self._gwl_says_adverb(key):
                p = "ADV"                    # περικύκλῳ 'round about' (TBESG G:A, Word List D)
            if p:
                return p
        info = self._entry_info.get(key) or {}
        if info.get("pos"):
            return info["pos"]
        for g in sorted(info.get("gwl", ())):
            gp = _gwl_pos(self.gwl.get(g, {}))
            if gp:
                return gp
        return "N"

    def _is_name_row(self, row: dict, key: str) -> bool:
        """A TBESG 'N:' row that is a proper name: capitalised headword (Strong's form included)
        or a person / place / title mark (N-M-P, N--L, N--T), unless the headword is lower-case."""
        head = self.head_override.get(key) or row["head"] or ""
        if head[:1].isupper():
            return True
        if head[:1].islower():
            return False
        return bool(re.search(r"(-[PLT]G?$|N-PRI)", row["morph"]))

    def _gwl_says_adverb(self, key: str) -> bool:
        b = greek_bare(self.headword(key))
        ent = self.gwl.get(b) or self.gwl.get(b[:-1] + "ς" if b.endswith("σ") else b)
        if not ent or _strong_num(key) is None:
            return False
        s = str(ent.get("strong") or "")
        return (not s or (s.isdigit() and _gkey(int(s)) == key)) and (ent.get("pos") or "").split()[:1] == ["D"] \
            and bool(ent.get("lemma")) and accent_key(ent["lemma"]) == accent_key(self.headword(key))

    def is_content(self, key: Optional[str]) -> bool:
        """False for function words (article, conjunctions, particles, personal and relative
        pronouns: is_function_word) and for every other pronoun (part of speech PRON:
        demonstrative, interrogative / indefinite, reflexive, reciprocal, possessive and
        correlative pronouns, οὗτος τίς τις ἐκεῖνος ἑαυτοῦ ὅσος ὅδε ἐμός ἀλλήλων τοιοῦτος)."""
        if not key:
            return True
        return not self.is_function_word(key) and self.pos(key) != "PRON"

    def is_function_word(self, key: Optional[str]) -> bool:
        """Article, conjunctions, particles, personal and relative pronouns (TBESG morph or Word
        List part of speech; ὡς ἕως ἄχρι μέχρι πρίν added by hand)."""
        if not key:
            return False
        if key in _FUNCTION_EXTRA:
            return True
        if key.startswith("G"):
            row = self.tbesg.rows.get(key) or self.tbesg.primary(key)
            if row and row["morph"]:
                return bool(_NONCONTENT_MORPH.match(row["morph"]))
        info = self._entry_info.get(key) or {}
        for g in info.get("gwl", ()):
            gp = (self.gwl.get(g, {}).get("pos") or "").split()
            if gp and gp[0] in _NONCONTENT_GWL_POS:
                return True
        return False

    # -- root families -------------------------------------------------------------------------
    def _parent_from_strongs(self, key: str) -> Optional[Tuple[List[str], str]]:
        n = _strong_num(key)
        if n is None or not key.startswith("G") or n > 5624:
            return None
        ent = self.strongs.entries.get(n)
        if not ent or ent["hedged"] or ent["foreign"] or not ent["parents"]:
            return None
        if ent["same_as"] is not None:
            # 'from the same as G4635' where G4635 is a compound of two content words (σκηνοποιός <
            # σκηνή + ποιέω) does not say which part is meant (πυκνός would land under ποιέω): not
            # followed.  'the same as G626' (ἀπολογέομαι < ἀπό + λόγος) is clear and stays.
            ref = self.strongs.entries.get(ent["same_as"])
            if ref:
                content = [p for p in ref["parents"]
                           if p in self.strongs.entries and not self._is_prefix_key(self.canonical(_gkey(p)) or "")]
                if len(content) >= 2:
                    return None
        comps = [self.canonical(_gkey(p)) for p in ent["parents"] if p in self.strongs.entries]
        comps = [c for c in comps if c and c != key]
        return (comps, "Strongs-CC0") if comps else None

    def _strongs_entry(self, key: str) -> Optional[dict]:
        n = _strong_num(key)
        if n is None or not key.startswith("G") or n > 5624:
            return None
        return self.strongs.entries.get(n)

    def _names_other_word(self, key: str, comp: str) -> bool:
        """True when Strong's derives ``key`` from an unnumbered word spelled like the numbered
        entry ``comp`` (ἄργυρος 'from ἀργός (shining)' is not G692 ἀργός 'idle' < α + ἔργον):
        another source's headword match would then join two different words."""
        ent = self._strongs_entry(key)
        n = _strong_num(comp)
        if not ent or not ent["unnumbered"] or n is None or not comp.startswith("G") or n > 5624:
            return False
        return accent_key(self.headword(comp)) in ent["unnumbered"]

    def _mgnt_components(self, key: str) -> Optional[List[str]]:
        """MorphGNT derivation components of ``key`` (PREFIX:... for prefixes), None when there is
        no entry or a component cannot be identified."""
        head = self.headword(key)
        items = self.mgnt_deriv.get(head)
        if not items:
            return None
        comps: List[str] = []
        for it in items:
            word = it.split()[0].rstrip(",")
            if word.endswith("-") or word in ("ἀ-", "ἀν-"):
                comps.append("PREFIX:" + greek_bare(word))
                continue
            k = self.key_for_headword(word)
            if k is None:
                return None          # one component we cannot identify: do not guess
            if k != key:
                comps.append(k)
        return comps

    def _parent_from_morphgnt(self, key: str) -> Optional[Tuple[List[str], str]]:
        comps = self._mgnt_components(key)
        if not comps:
            return None
        if any(self._names_other_word(key, c) for c in comps):
            return None
        real = [c for c in comps if not c.startswith("PREFIX:")]
        return (comps, "MorphGNT-derivation") if real else None

    def _parent_from_gwl(self, key: str) -> Optional[Tuple[List[str], str]]:
        """The Greek Word List 'src' link, followed only where Strong's and MorphGNT do not
        contradict or hedge it: φημί 'src φάω' (Strong's: 'properly, the same as the base of ...')
        is not followed, so speech words (φημί, φωνή, προφήτης) stay apart from light words (φῶς,
        φαίνω); φῶς 'src φάω' is followed because Strong's itself derives it from φάω."""
        info = self._entry_info.get(key) or {}
        sent = self._strongs_entry(key)
        mgnt = self._mgnt_components(key)
        mgnt_real = {c for c in (mgnt or []) if not c.startswith("PREFIX:")}
        for g in sorted(info.get("gwl", ())):
            src = self.gwl.get(g, {}).get("src")
            if not src:
                continue
            comps: List[str] = []
            ok = True
            for part in [s.strip() for s in src.split(",") if s.strip()]:
                if re.match(r"^H\d+", part):
                    ok = False
                    break
                if part in _PREFIX_BARE or part.split(".")[0] in _PREFIX_BARE and part not in self.gwl:
                    comps.append("PREFIX:" + part.split(".")[0])
                    continue
                if part not in self.gwl:
                    ok = False
                    break
                k = self.gwl_lemma_key(part)
                if k != key:
                    comps.append(k)
                    if k.startswith("grc:"):
                        self.head_gwl.setdefault(k, part)
            real = [c for c in comps if not c.startswith("PREFIX:")]
            if not (ok and real):
                continue
            if any(self._names_other_word(key, c) for c in real):
                continue
            # Strong's names the same (unnumbered) word: the two sources agree
            corroborated = bool(sent and sent["unnumbered"]
                                and any(accent_key(self.headword(c)) in sent["unnumbered"] for c in real))
            if not corroborated:
                if sent and (sent["hedged"] or sent["primary"] or sent["foreign"]):
                    continue        # Strong's doubts the link, calls the word primary or foreign
                if mgnt_real and not (mgnt_real & set(real)):
                    continue        # MorphGNT derives it from another word
            return comps, "OSSP-GWL-src"
        return None

    def _is_prefix_key(self, k: str) -> bool:
        if k.startswith("PREFIX:"):
            return True
        n = _strong_num(k)
        if n is not None and k.startswith("G") and n in _PREFIX_STRONGS:
            return True
        return greek_bare(self.headword(k)) in _PREFIX_BARE and self.pos(k) in ("PREP", "PART", "ADV")

    def _parent(self, key: str, strict: bool = False) -> Optional[Tuple[str, List[str], str]]:
        """(head component, prefix components, source) of a lemma's derivation, or None.
        ``strict``: only links that pass the family policy (_family_link_ok); a source whose
        link fails gives way to the next source."""
        if strict and self._family_excluded(key):
            return None
        for fn in (self._parent_from_strongs, self._parent_from_morphgnt, self._parent_from_gwl):
            got = fn(key)
            if got:
                comps, src = got
                content = [c for c in comps if not self._is_prefix_key(c)]
                if not content:
                    # only a preverb is linked ("from G575 and εἶμι"): the stem word is not
                    # identified by this source, so ask the next one
                    continue
                head = content[-1]
                if strict and not self._family_link_ok(key, comps, head):
                    continue
                others = [c for c in comps if c != head]
                return head, others, src
        return None

    # -- the conservative family policy (see the comment above _FAMILY_PREFIX_SPELLINGS) --------
    def _family_bare(self, k: str) -> str:
        if k.startswith("PREFIX:"):
            return k[7:]
        return greek_bare(self.headword(k))

    def _family_excluded(self, key: str) -> bool:
        """Its own family whatever a source says, and never a family head: prepositions used as
        prefixes (ἀπό, περί, σύν ...), inseparable prefixes and function words.  Adverbs that
        TBESG files as prepositions (ἐγγύς, ἔμπροσθεν) are ordinary words."""
        return self._is_prefix_key(key) or self.is_function_word(key)

    def _strongs_denies(self, key: str) -> bool:
        """Strong's calls the word primary, foreign or of uncertain derivation (not merely a
        hedged link of its own: φωνή 'probably akin to G5316' still takes MorphGNT's φημί)."""
        ent = self._strongs_entry(key)
        if not ent:
            return False
        if ent["primary"] or ent["foreign"]:
            return True
        main = re.sub(r"<[^>]+>", " X ", _main_clause(ent["derivation"] or "")).lower()
        return bool(re.search(r"\b(uncertain|unknown|obscure|doubtful|disputed)\b", main))

    def _abbott_entry(self, key: str) -> Optional[dict]:
        h = self.headword(key)
        return self.abbott.get(h) or self._abbott_by_bare.get(greek_bare(h))

    def _family_supported(self, key: str, head: str) -> bool:
        """Policy (b): MorphGNT's derivation list or Abbott-Smith names the same head."""
        mg = self._mgnt_components(key)
        if mg and head in mg:
            return True
        raw = self.mgnt_deriv.get(self.headword(key)) or []
        hb = greek_bare(self.headword(head))
        for item in raw:
            # 'contracted from ἄεργος (ἀ- priv., ἔργον)': MorphGNT names the head inside a note
            for w in re.findall(r"[Ͱ-Ͽἀ-῿]+", item):
                if len(greek_bare(w)) >= 3 and _family_voice_twins(greek_bare(w)) & _family_voice_twins(hb):
                    return True
        if raw and raw[-1].split()[0].endswith("-"):
            # MorphGNT segments the word into stems: βλάσφημος 'βλας-', 'φημ-' (the last is φήμη's)
            last = greek_bare(raw[-1].split()[0])
            if len(last) >= 3 and last in _family_base_stems(greek_bare(self.headword(head))):
                return True
        ent = self._abbott_entry(key)
        if not ent:
            return False
        twins = _family_voice_twins(greek_bare(self.headword(head)))
        for w in ent["from"]:
            if self.key_for_headword(w) == head or (_family_voice_twins(greek_bare(w)) & twins):
                return True
        parts = [p for p in ent["parts"] if p.strip()]
        return len(parts) >= 2 and bool(_family_voice_twins(greek_bare(parts[-1])) & twins)

    def _abbott_contradicts(self, key: str, head: str) -> bool:
        """Abbott-Smith derives the word ('(< X)') from a known word X other than ``head`` that
        does not continue the head's stem either (βαθμός '< βαίνω, to step': not βάθος 'depth')."""
        ent = self._abbott_entry(key)
        if not ent or not ent["from"]:
            return False
        hb = greek_bare(self.headword(head))
        stems = [s for s in _family_base_stems(hb) if len(s) >= 3]
        named = False
        for w in ent["from"]:
            k = self.key_for_headword(w)
            if k is None:
                continue
            named = True
            wb = greek_bare(w)
            parts = [greek_bare(p) for p in w.split("-") if greek_bare(p)]
            if (k == head or any(_family_voice_twins(p) & _family_voice_twins(hb) for p in parts + [wb])
                    or any(_family_continues(p, hb) for p in parts + [wb]) or any(s in wb for s in stems)):
                return False                 # '(< ἐκ-καλέω)' still names καλέω
        return named

    def _family_link_ok(self, key: str, comps: Sequence[str], head: str) -> bool:
        """Is the link key -> comps (head ``head``) one the conservative family policy keeps?"""
        if self._family_excluded(head) or self.headword(head).startswith("-"):
            return False                     # function word, preposition, bare suffix ('-θεν')
        if self.pos(head) == "PROPN" and self.pos(key) != "PROPN":
            return False                     # πέτρα is not filed under Πέτρος
        if (accent_key(self.headword(key)), accent_key(self.headword(head))) in _FAMILY_SLIP_KEYS:
            return False
        if self._abbott_contradicts(key, head):
            return False                     # βαθμός: Abbott-Smith '< βαίνω', not βάθος (Strong's)
        if (not self._strongs_denies(key) and self.pos(key) != "PROPN"
                and self._family_supported(key, head)):
            return True                      # a name needs a visible link (Λυκαονία is not < Λυκία)
        prefixes: List[str] = []
        contents: List[str] = []
        for c in comps:
            if self._is_prefix_key(c):
                if contents:
                    return False             # a prefix after a content word: not transparent
                prefixes.append(self._family_bare(c))
            else:
                contents.append(self._family_bare(c))
        return _family_visible(greek_bare(self.headword(key)), prefixes, contents)

    def root_of(self, key: str, strict: bool = True) -> Tuple[str, str, str, str]:
        """(root_lemma_key, root_source, formula, '') following the derivation chain.

        ``strict`` (the reader-facing families of build_entry): only links the conservative
        family policy keeps, and the family head must have a meaning of its own
        (root_meaning); a chain that reaches a head without one stops at the word before it.
        ``strict=False`` is the permissive walk that GreekTagger.linked() has always used to
        recognise two lemmatisation conventions for one word; it does not reach readers."""
        ck = (key, strict)
        if ck in self._root_cache:
            return self._root_cache[ck]
        chain: List[str] = [key]
        steps: List[str] = []
        sources: List[str] = []
        cur = key
        root_at = None
        while True:
            got = self._parent(cur, strict)
            if not got:
                break
            head, others, src = got
            if head in chain:
                # two sources derive the words from each other (Strong's: μιμνήσκω < μνάομαι; Word
                # List: μνάομαι < μιμνήσκω).  Every member of the loop gets the same family head,
                # the lowest key of the loop, wherever the walk starts.
                loop = chain[chain.index(head):]
                root_at = chain.index(min(loop, key=_key_order))
                break
            if len(chain) > 12:
                break
            parts = list(dict.fromkeys([self._label(o) for o in others] + [self.headword(head)]))
            steps.append(" + ".join(parts))
            sources.append(src)
            chain.append(head)
            cur = head
        if root_at is not None:
            chain, steps, sources = chain[:root_at + 1], steps[:root_at], sources[:root_at]
        if strict:
            # the family head must have a meaning of its own: ἔργω 'to work' (Strong's), κῦρος
            # 'supreme power' (Word List); a base nobody glosses (δελφύς) does not head a family
            while len(chain) > 1 and not self.root_meaning(chain[-1]):
                chain, steps, sources = chain[:-1], steps[:-1], sources[:-1]
        root = chain[-1]
        if root == key:
            res = (key, "self", self.headword(key), "")
        else:
            formula = self.headword(key) + " < " + " < ".join(steps)
            src = sources[0] if len(set(sources)) == 1 else "+".join(dict.fromkeys(sources))
            res = (root, src, formula, "")
        self._root_cache[ck] = res
        return res

    def _label(self, k: str) -> str:
        if k.startswith("PREFIX:"):
            base = k[7:]
            if base in ("α", "αν"):
                return {"α": "ἀ-", "αν": "ἀν-"}[base]
            ent = self.gwl.get(base)
            return ent["lemma"] if ent and ent.get("lemma") else base + "-"
        return self.headword(k)

    def ensure_entry(self, key: str, *, head: str = "", gloss: str = "", pos: Optional[str] = None,
                     source: str = "", gwl_key: Optional[str] = None) -> LemmaEntry:
        """Register ``key`` if needed and return its LemmaEntry (keeping ``self.entries`` in sync)."""
        if key not in self._entry_info:
            self.note_lemma(key, head=head, gloss=gloss, pos=pos, source=source, gwl_key=gwl_key)
        if self.entries and key not in self.entries:
            self.entries[key] = self.build_entry(key)
        return self.entries[key] if key in self.entries else self.build_entry(key)

    def resolve_external_lemma(self, head: str, pos_hint: Optional[str] = None,
                               allow_propn: bool = True, allow_lsj: bool = True) -> Optional[str]:
        """Find or register a canonical Greek lemma key for a headword from TBESG, GWL, TFLSJ-extra
        or (for common words with an English gloss) Perseus LSJ XML.  Used when an aligned open
        corpus (e.g. GLAUx) attests a genuine Greek word absent from TAGNT / LxxLemmas."""
        clean = unicodedata.normalize("NFC", re.sub(r"\d+$", "", head or "").strip())
        if not clean:
            return None
        want_cap = clean[:1].isupper()
        if want_cap and not allow_propn:
            return None
        b = greek_bare(clean)
        if not b:
            return None

        def _pos_ok(k: str) -> bool:
            if not pos_hint:
                return True
            p = self.pos(k)
            if pos_hint == "V":
                return p == "V"
            if pos_hint == "N":
                return p in ("N", "PROPN", "ADJ")
            if pos_hint == "ADJ":
                return p in ("ADJ", "N", "PROPN")
            if pos_hint == "ADV":
                return p in ("ADV", "PREP", "PART", "CONJ")
            return True

        # 1. TBESG exact accented headword (same capitalisation; verbs never names)
        k = self.key_for_headword(clean, same_case=True)
        if k and _pos_ok(k):
            self.ensure_entry(k, source=SRC_TAGNT)
            return k
        # 2. TBESG bare headword (unique match with same capitalisation & compatible POS)
        t_hits = [self.canonical(e) or e for e in self.tbesg.by_bare.get(b, ())]
        t_hits = list(dict.fromkeys(
            e for e in t_hits
            if (self._tbesg_head_case(e) == want_cap or self.pos(e) == "V") and _pos_ok(e)
        ))
        if len(t_hits) == 1:
            self.ensure_entry(t_hits[0], source=SRC_TAGNT)
            return t_hits[0]
        # 3. Open Scriptures Greek Word List entry
        gwl_cands = []
        for gk_try in (b, b[:-1] + "ς" if b.endswith("σ") else b):
            if gk_try in self.gwl:
                gwl_cands.append(gk_try)
        gwl_cands = list(dict.fromkeys(gwl_cands))
        if len(gwl_cands) == 1:
            gk = gwl_cands[0]
            ent = self.gwl[gk]
            lk = self.gwl_lemma_key(gk)
            gpos = _gwl_pos(ent)
            if (not want_cap or (ent.get("lemma", "")[:1].isupper() or gpos == "PROPN")) and (
                    not pos_hint or not gpos or gpos == pos_hint or (pos_hint == "N" and gpos in ("N", "PROPN", "ADJ"))):
                self.ensure_entry(lk, head=ent.get("lemma", ""), pos=gpos, source=SRC_OSSP, gwl_key=gk)
                return lk
        # 4. TFLSJ-extra (STEPBible formatted LSJ columns 1-7)
        tf_hits = [r for r in self.tflsj.by_bare.get(b, ())
                   if r["head"][:1].isupper() == want_cap or r["morph"].startswith("G:V")]
        if len(tf_hits) == 1:
            r = tf_hits[0]
            ek = self.canonical(r["estrong"]) or r["estrong"]
            if _pos_ok(ek):
                self.ensure_entry(ek, head=r["head"], gloss=r["gloss"], pos=_pos_from_morph(r["morph"]),
                                  source=SRC_TAGNT)
                return ek
        # 5. Perseus LSJ XML (common words with a real English gloss only)
        if allow_lsj and not want_cap:
            lsj_g = self.lsj.gloss(clean)
            if lsj_g:
                use_head = clean
                if accent_key(clean) == b:
                    ents = self.lsj._load().get(b, [])
                    if ents:
                        cand_h = _beta_to_greek(ents[0][0])
                        if cand_h.endswith("σ"):
                            cand_h = cand_h[:-1] + "ς"
                        if cand_h and not cand_h.startswith("-"):
                            use_head = cand_h
                lk = "grc:" + use_head
                self.ensure_entry(lk, head=use_head, gloss=lsj_g, pos=pos_hint or "N",
                                  source=_GLOSS_SOURCE_NOTES["LSJ"])
                return lk
        return None

    def build_entry(self, key: str) -> LemmaEntry:
        root, src, formula, _ = self.root_of(key)
        info = self._entry_info.get(key) or {}
        sources = sorted(info.get("sources", ()))
        n = _strong_num(key)
        gsrc = self.gloss_source(key)
        if gsrc in _GLOSS_SOURCE_NOTES:
            sources.append(_GLOSS_SOURCE_NOTES[gsrc])
        return LemmaEntry(
            lang=LANG,
            lemma_key=key,
            lemma=_display(self.headword(key)),
            gloss=self.gloss(key),
            pos=self.pos(key),
            strongs=_gkey(n) if (n is not None and key.startswith("G")) else None,
            root_key=root if root.startswith("grc:") else "grc:" + root,
            root_label=_display(self.headword(root)),
            root_gloss=self.root_meaning(root),
            root_source=src,
            formula=_display(formula),
            source="; ".join(sources) if sources else SRC_TAGNT,
        )


# Where a gloss came from when it is not one of the lemma sources already named.
_GLOSS_SOURCE_NOTES = {
    "LSJ": "gloss: Liddell-Scott-Jones, Perseus Digital Library (CC BY-SA 4.0)",
    "TBESH": "gloss: STEPBible TBESH cols 1-7 (Tyndale House/STEPBible.org, CC BY 4.0)",
    "TBESG+TBESH": "gloss: STEPBible TBESH cols 1-7 (Tyndale House/STEPBible.org, CC BY 4.0)",
    "TBESG/TFLSJ": "gloss: STEPBible TBESG/TFLSJ cols 1-7 (Tyndale House/STEPBible.org, CC BY 4.0)",
    "OSSP-GWL+TBESG": "gloss: Open Scriptures Greek Word List (CC BY 4.0)",
}


def _display(text: str) -> str:
    """Display form: vowel-length marks (breve, macron) dropped (κόλλᾰ -> κόλλα, ὕψῐ -> ὕψι)."""
    t = unicodedata.normalize("NFD", text or "")
    t = t.replace("̆", "").replace("̄", "")
    return unicodedata.normalize("NFC", t)


# ---------------------------------------------------------------------------
# TAGNT (New Testament gold tags)
# ---------------------------------------------------------------------------

_TAGNT_BOOKS = {
    "Mat": "matthew", "Mrk": "mark", "Luk": "luke", "Jhn": "john", "Act": "acts", "Rom": "romans",
    "1Co": "1-corinthians", "2Co": "2-corinthians", "Gal": "galatians", "Eph": "ephesians",
    "Php": "philippians", "Col": "colossians", "1Th": "1-thessalonians", "2Th": "2-thessalonians",
    "1Ti": "1-timothy", "2Ti": "2-timothy", "Tit": "titus", "Phm": "philemon", "Heb": "hebrews",
    "Jas": "james", "1Pe": "1-peter", "2Pe": "2-peter", "1Jn": "1-john", "2Jn": "2-john",
    "3Jn": "3-john", "Jud": "jude", "Rev": "revelation",
}
_TAGNT_ROW = re.compile(r"^(\d?[A-Z][a-z]+)\.(\d+)\.(\d+)(?:([\[\(\{])(\d+)\.(\d+)[\]\)\}])?#(\d+)=(\S*)\t")
_TAG_RE = re.compile(r"(G\d+[A-Z]?)=")
_TAG_PARSE_RE = re.compile(r"(G\d+[A-Z]?)=([A-Z0-9]+(?:-[A-Z0-9]+)*)")


def _tag_parse(tagcol: str) -> Optional[str]:
    """TAGNT parse code(s) of a 'dStrongs=Grammar' cell: 'G0746=N-DSF' -> 'N-DSF'; crasis
    'G1473=P-1NS + G2532=CONJ' -> 'P-1NS+CONJ'.  None unless every tag carries a parse."""
    tags = _TAG_RE.findall(tagcol)
    parts = _TAG_PARSE_RE.findall(tagcol)
    if not tags or len(parts) != len(tags):
        return None
    return "+".join(p for _t, p in parts)


class _TagntWord:
    __slots__ = ("ref", "surface", "key", "alts", "akey", "parse", "morphs")

    def __init__(self, ref: str, surface: str, key: Optional[str], alts: Dict[str, str], akey: str,
                 parse: Optional[str] = None, morphs: Optional[Dict[str, Optional[str]]] = None):
        self.ref = ref
        self.surface = surface
        self.key = key            # lemma key of the printed word (None if unresolvable)
        self.alts = alts          # bare form -> lemma key (printed word, spellings, variant words)
        self.akey = akey          # accent key of the printed word
        self.parse = parse        # TAGNT parse of the printed word ('N-DSF'), None if TAGNT gives none
        # bare form -> parse of the word that form is (same keys as ``alts``; None = no parse)
        self.morphs: Dict[str, Optional[str]] = morphs if morphs is not None else {}

    def morph_of(self, bare_form: str) -> Optional[str]:
        """Parse of the form ``bare_form`` (a key of ``alts``) with the scheme prefix: 'R:N-DSF'."""
        p = self.morphs.get(bare_form)
        return f"{MORPH_SCHEME}:{p}" if p else None


class _NT:
    def __init__(self, lex: _Lexicon) -> None:
        self.lex = lex
        self.verses: Dict[Tuple[str, int, int], List[_TagntWord]] = defaultdict(list)
        self.alt_verses: Dict[Tuple[str, int, int], List[_TagntWord]] = defaultdict(list)
        dict_forms: Dict[str, Counter] = defaultdict(Counter)
        raw_rows = []
        for f in _tagnt_files():
            with open(_fs(f), encoding="utf-8-sig") as fh:
                for line in fh:
                    m = _TAGNT_ROW.match(line)
                    if not m:
                        continue
                    cols = line.rstrip("\r\n").split("\t")
                    if len(cols) < 6:
                        continue
                    raw_rows.append((m, cols))
                    tags = _TAG_RE.findall(cols[3])
                    dform = cols[4].split("=")[0].strip()
                    if len(tags) == 1:
                        dict_forms[lex.tbesg.estrong_of.get(tags[0], tags[0][:5])][dform] += 1
        lex.add_tagnt_folds(dict_forms)
        self.forms = _FormTable(common_noun=lambda k: lex.pos(k) == "N")
        self.key_overrides: Counter = Counter()      # (tag key, dictionary-form key) pairs used
        row_keys = [self._key_from_tag(cols[3], cols[4], cols[1].split(" (")[0].strip()) for _, cols in raw_rows]
        printed: Dict[str, Counter] = defaultdict(Counter)   # accent key of a printed word -> keys
        for (m, cols), key in zip(raw_rows, row_keys):
            if key:
                printed[accent_key(cols[1].split(" (")[0])][key] += 1
        self.detached: List[str] = []                # rows whose tag belongs to a variant word
        for (m, cols), key in zip(raw_rows, row_keys):
            book, ch, vs = m.group(1), int(m.group(2)), int(m.group(3))
            slug = _TAGNT_BOOKS.get(book)
            if not slug:
                continue
            if m.group(4) == "(":                    # Nestle-Aland numbering differs from NRSV
                ch, vs = int(m.group(5)), int(m.group(6))
            surface = cols[1].split(" (")[0].strip()
            alts: Dict[str, str] = {}
            spellings: List[Tuple[str, str]] = []
            b = greek_bare(surface)
            sps = []
            if key and len(cols) > 7 and cols[7].strip():
                # spelling variants of the same word: "Tyn+WH: Δαυεὶδ ; +TR: Δαβὶδ ;"
                sps = [sp for sp in re.findall(r":\s*([^;:]+?)\s*;", cols[7])
                       if len(sp.split()) == 1 and greek_bare(sp)]
            surface_key = key
            if key and sps and self._tag_is_the_variants(surface, sps, key, cols[4]):
                # TAGNT gives the printed (NA) word the lemma of another edition's word: Acts
                # 21:15 ἐπισκευασάμενοι 'G0643 ἀποσκευάζω' (TR ἀποσκευασάμενοι), Luke 16:21
                # ἐπέλειχον 'ἀπολείχω' (TR ἀπέλειχον).  The tag stays with the variant; the
                # printed word takes a lemma TAGNT prints it with elsewhere, or its own GWL
                # headword when GWL explicitly records the variant/compound (ἐπισκευάζω G7447,
                # ἐπιλείχω, διαπαρατριβή G6856, στασιαστής, παρεδρεύω G8645).
                c = printed.get(accent_key(surface))
                other = Counter({k: n for k, n in (c or {}).items() if k != key})
                surface_key = None
                if other:
                    k2, n2 = other.most_common(1)[0]
                    if n2 >= 0.95 * sum(other.values()):
                        surface_key = k2
                if surface_key is None:
                    gmatch = self._gwl_for_detached(surface, key, cols[4])
                    if gmatch is not None:
                        gk, lk = gmatch
                        surface_key = lk
                        gent = lex.gwl.get(gk, {})
                        lex.note_lemma(lk, head=gent.get("lemma", ""), pos=_gwl_pos(gent),
                                       source=SRC_OSSP, gwl_key=gk)
                self.detached.append(f"{book}.{m.group(2)}.{m.group(3)}#{m.group(7)}")
            # the printed word's parse (column 4); it describes the word in this place, so it also
            # stands when the lemma was detached above (the variants differ only in the preverb)
            parse = _tag_parse(cols[3])
            morphs: Dict[str, Optional[str]] = {}      # mirrors alts: the parse of each form
            if surface_key and b:
                alts[b] = surface_key
                morphs[b] = parse
            for sp in sps:
                sk = key
                c = printed.get(accent_key(sp))
                if c and not _spelling_variant(surface, sp):
                    # the 'spelling' is another word that TAGNT prints with its own lemma
                    # (Mark 3:4 ἀγαθοποιῆσαι beside ποιῆσαι is ἀγαθοποιέω; κἀγώ is not ἐγώ)
                    k2, n2 = c.most_common(1)[0]
                    if k2 != key and n2 >= 0.95 * sum(c.values()):
                        sk = k2
                spb = greek_bare(sp)
                if spb not in alts:
                    alts[spb] = sk
                    # a spelling of this word has its parse; another word printed elsewhere has none here
                    morphs[spb] = parse if sk == key else None
                spellings.append((sp, sk))
            if len(cols) > 6 and cols[6].strip():
                # other editions' words in this place: one word with one tag only
                for entry in cols[6].split("¦"):
                    mv = re.match(r"^\s*(.+?) \([A-Za-z]=[^)]*\)(.*?)\s-\s(.+?)\sin:", entry)
                    if not mv or len(mv.group(1).split()) != 1:
                        continue
                    vtags = _TAG_RE.findall(mv.group(3))
                    if len(vtags) != 1:
                        continue
                    vk = lex.key_for_dstrong(vtags[0])
                    bw = greek_bare(mv.group(1))
                    if bw and vk:
                        if bw not in alts:
                            alts[bw] = vk
                            morphs[bw] = _tag_parse(mv.group(3))   # the variant word's own parse
                        lex.note_lemma(vk, source=SRC_TAGNT)   # every key a tag can carry is listed
            ref = f"{book}.{m.group(2)}.{m.group(3)}#{m.group(7)}"
            w = _TagntWord(ref, surface, surface_key, alts, accent_key(surface), parse, morphs)
            self.verses[(slug, ch, vs)].append(w)
            if m.group(4) in ("[", "{"):
                # KJV / other editions' place of the same words (the Romans doxology also
                # stands at 14:24-26, which the Studio prints there in double brackets)
                self.alt_verses[(slug, int(m.group(5)), int(m.group(6)))].append(w)
            if key:
                tag_head = cols[4].split("=")[0].strip()
                lex.note_lemma(key, head="" if "+" in cols[4] else tag_head.split(",")[0].strip(),
                               gloss=cols[4].split("=", 1)[1].split("+")[0].strip() if "=" in cols[4] else "",
                               source=SRC_TAGNT)
                if surface_key:
                    self.forms.add(surface, surface_key)
                for sp, sk in spellings:
                    self.forms.add(sp, sk)

    def _tag_is_the_variants(self, surface: str, variants: Sequence[str], key: str, dictcol: str) -> bool:
        """True when a row's lemma fits one of its listed variant words (stem similarity >= 0.78)
        and not the printed word (< 0.5, TBESG's own headword forms included), and the variant is
        another compound of the same stem (other prepositions in front): ἐπισκευασάμενοι /
        ἀποσκευάζω, ἐπέλειχον / ἀπολείχω, στασιαστῶν / συστασιαστής.  Spellings (Καφαρναούμ /
        Καπερναούμ, ἤμελλεν / ἔμελλεν) and other tenses (ἀφελεῖ / ἀφαιρήσει) keep the tag."""
        if "+" in dictcol:
            return False
        forms = [h.strip() for h in dictcol.split("=")[0].split(",") if h.strip()]
        for r in self.lex.tbesg.by_estrong.get(key, []):
            forms += [h.strip() for h in re.split(r"[,=]", r["raw_head"]) if h.strip()]
        forms = [greek_bare(f) for f in forms if greek_bare(f)]
        if not forms:
            return False
        sb = greek_bare(surface)
        if max(stem_similarity(sb, f) for f in forms) >= 0.5:
            return False
        sp_pre, s_core = _preverb_split(sb)
        for sp in variants:
            vb = greek_bare(sp)
            if max(stem_similarity(vb, f) for f in forms) < 0.78:
                continue
            v_pre, v_core = _preverb_split(vb)
            if v_pre == sp_pre or not (v_core == s_core or _spelling_variant(v_core, s_core)):
                continue
            n = min(len(v_pre), len(sp_pre))
            if v_pre[:n] != sp_pre[:n]:
                return True             # another preposition in the same place (ἐπι- / ἀπο-)
            if not _spelling_variant(surface, sp):
                return True             # an added preposition (συ-στασιαστής), not a spelling
        return False

    def _gwl_for_detached(self, surface: str, detached_key: str, dictcol: str) -> Optional[Tuple[str, str]]:
        """Find the Open Scriptures Greek Word List headword for a printed NA word whose TR-variant
        lemma was detached (Acts 21:15 ἐπισκευασάμενοι -> ἐπισκευάζω G7447, Luke 16:21 ἐπέλειχον ->
        ἐπιλείχω, 1 Tim 6:5 διαπαρατριβαὶ -> διαπαρατριβή G6856, Mark 15:7 στασιαστῶν -> στασιαστής,
        1 Cor 9:13 παρεδρεύοντες -> παρεδρεύω G8645)."""
        sb = greek_bare(surface)
        if not sb:
            return None
        s_pre, s_core = _preverb_split(sb)
        dforms = {greek_bare(h.strip()) for h in dictcol.split("=")[0].split(",") if h.strip()}
        dforms.add(greek_bare(self.lex.headword(detached_key)))
        d_cores = {_preverb_split(f)[1] for f in dforms if f}
        best: Optional[Tuple[float, str, str]] = None
        for gk, ent in self.lex.gwl.items():
            lb = _lemma_bare(gk)
            if not lb or lb in dforms:
                continue
            g_pre, g_core = _preverb_split(lb)
            if g_pre != s_pre and not (g_pre and s_pre[:len(g_pre)] == g_pre):
                continue
            v_match = _lemma_bare(ent.get("v") or "") in dforms
            core_match = any(stem_similarity(g_core, dc) >= 0.85 for dc in d_cores if dc)
            if not (v_match or core_match):
                continue
            sim = stem_similarity(sb, gk)
            if sim < 0.85:
                continue
            lk = self.lex.gwl_lemma_key(gk)
            if lk == detached_key:
                continue
            score = sim + (0.2 if v_match else 0.0)
            if best is None or score > best[0]:
                best = (score, gk, lk)
        return (best[1], best[2]) if best is not None else None

    def _key_from_tag(self, tagcol: str, dictcol: str, surface: str = "") -> Optional[str]:
        """Lemma key of a TAGNT word.  TAGNT tags some words with the unified number of a word
        family (ἐμός and ἐμαυτοῦ as G1473 ἐγώ, σεαυτοῦ as G4771, ὤφθη as G3700 ὀπτάνομαι) but
        gives the true dictionary form beside it; that dictionary form decides when TBESG has
        exactly one entry for it - unless the printed word is a form of the tagged headword and
        not of the named one (Luke 21:5 ἀναθήμασιν, tagged G0334 ἀνάθημα 'votive offering' beside
        the dictionary form 'ἀνάθεμα': it stays ἀνάθημα)."""
        lex = self.lex
        tags = _TAG_RE.findall(tagcol)
        if not tags:
            return None
        dform = dictcol.split("=")[0].strip()
        if len(tags) == 1:
            k_tag = lex.key_for_dstrong(tags[0])
            if "+" in dictcol:              # "μή=not + τις=one": a description, not a headword
                return k_tag
            tag_bare = greek_bare(lex.headword(k_tag))
            forms = [h.strip() for h in dform.split(",") if h.strip()]
            if not forms or any(greek_bare(h) == tag_bare for h in forms):
                return k_tag                # same letters (πως for πῶς): the number decides
            heads = {lex.key_for_headword(h) for h in forms}
            heads.discard(None)
            if len(heads) == 1:
                k_dict = next(iter(heads))
                if k_dict != k_tag and surface:
                    sb = greek_bare(surface)
                    if (stem_similarity(sb, tag_bare) >= 0.9
                            and max(stem_similarity(sb, greek_bare(h)) for h in forms) < 0.85):
                        return k_tag        # ἀναθήμασιν is ἀνάθημα, whatever the dictionary column says
                if k_dict != k_tag:
                    self.key_overrides[(k_tag, k_dict)] += 1
                return k_dict
            return k_tag
        # crasis / compounds written as one word: κἀγώ = G2532 + G1473
        if "+" not in dictcol:
            k = lex.key_for_headword(dform)
            if k:
                return k
        comps = frozenset(lex.key_for_dstrong(t) for t in tags)
        e = lex.tbesg.combination.get(comps)
        if e:
            return lex.canonical(e)
        nums = tuple(_strong_num(lex.tbesg.estrong_of.get(t, t)) for t in tags)
        for order in (nums, tuple(reversed(nums))):
            hits = lex.strongs.by_refs.get(order)
            if hits and len(hits) == 1:
                return lex.canonical(_gkey(hits[0]))
        if surface:
            clean_surf = surface.strip(".,;·:?!()[]\"'¶")
            k = lex.key_for_headword(clean_surf, same_case=True)
            if k:
                return k
        return None

    def lookup(self, token: str, min_share: float = 0.95, min_count: int = 2, exclude=None) -> Optional[Tuple[str, float]]:
        return self.forms.lookup(token, min_share, min_count, exclude)


# ---------------------------------------------------------------------------
# LXX lemma files (Open Scriptures Septuagint Project)
# ---------------------------------------------------------------------------

# Studio book slug -> LXX lemma files (first = primary) with a chapter offset into the file.
_LXX_FILES: Dict[str, List[Tuple[str, int]]] = {
    "genesis": [("Gen", 0)], "exodus": [("Exod", 0)], "leviticus": [("Lev", 0)],
    "numbers": [("Num", 0)], "deuteronomy": [("Deut", 0)],
    "joshua": [("JoshB", 0), ("JoshA", 0)], "judges": [("JudgB", 0), ("JudgA", 0)],
    "ruth": [("Ruth", 0)], "1-samuel": [("1Sam", 0)], "2-samuel": [("2Sam", 0)],
    "1-kings": [("1Kgs", 0)], "2-kings": [("2Kgs", 0)], "1-chronicles": [("1Chr", 0)],
    "2-chronicles": [("2Chr", 0)], "ezra": [("2Esd", 0)], "nehemiah": [("2Esd", 10)],
    "esther": [("Esth", 0)], "1-maccabees": [("1Macc", 0)], "2-maccabees": [("2Macc", 0)],
    "job": [("Job", 0)], "psalms": [("Ps", 0)], "proverbs": [("Prov", 0)],
    "ecclesiastes": [("Eccl", 0)], "song-of-songs": [("Song", 0)], "lamentations": [("Lam", 0)],
    "wisdom-of-solomon": [("Wis", 0)], "sirach": [("Sir", 0)], "isaiah": [("Isa", 0)],
    "jeremiah": [("Jer", 0)], "ezekiel": [("Ezek", 0)], "daniel": [("DanTh", 0), ("DanOG", 0)],
    "hosea": [("Hos", 0)], "joel": [("Joel", 0)], "amos": [("Amos", 0)], "obadiah": [("Obad", 0)],
    "jonah": [("Jonah", 0)], "micah": [("Mic", 0)], "nahum": [("Nah", 0)], "habakkuk": [("Hab", 0)],
    "zephaniah": [("Zeph", 0)], "haggai": [("Hag", 0)], "zechariah": [("Zech", 0)],
    "malachi": [("Mal", 0)],
    # books outside the current 70-book canon, kept so tag_chapter works if they are added
    "tobit": [("TobBA", 0), ("TobS", 0)], "judith": [("Jdt", 0)], "baruch": [("Bar", 0)],
    "1-esdras": [("1Esd", 0)], "3-maccabees": [("3Macc", 0)], "4-maccabees": [("4Macc", 0)],
    "letter-of-jeremiah": [("EpJer", 0)], "psalms-of-solomon": [("PsSol", 0)], "odes": [("Odes", 0)],
    "susanna": [("SusTh", 0), ("SusOG", 0)], "bel-and-the-dragon": [("BelTh", 0), ("BelOG", 0)],
}

_LXX_REF = re.compile(r"^[^.]+\.(\w+)\.(\d+)([a-z]*)$")


class _LxxBook:
    """One lemma file: verse groups keyed (chapter, verse) in file order.  Letter sub-verses
    (Esth 1:1a-s, Prov 24:22a-e) belong to their numbered verse."""

    def __init__(self, name: str, data: Dict[str, List[dict]]) -> None:
        self.name = name
        self.groups: Dict[Tuple[int, int], List[str]] = {}
        self.order: List[Tuple[int, int]] = []
        self.refs: Dict[Tuple[int, int], List[str]] = defaultdict(list)
        for ref, words in data.items():
            m = _LXX_REF.match(ref)
            if not m:
                continue
            chs, vs, letter = m.group(1), int(m.group(2)), m.group(3)
            if chs == "Prolog":
                key = (1, 1)                   # the Studio prints Sirach's prologue in 1:1
            elif chs.isdigit():
                key = (int(chs), vs)
            else:
                continue
            if key not in self.groups:
                self.groups[key] = []
                self.order.append(key)
            self.groups[key].extend(w["key"] for w in words)
            self.refs[key].append(ref)
        self.index = {k: i for i, k in enumerate(self.order)}


# ---------------------------------------------------------------------------
# Stem comparison (only ever used to pair a token with a lemma of the SAME verse's gold list)
# ---------------------------------------------------------------------------

_LEMMA_ENDINGS = sorted([
    "ομαι", "ουμαι", "αμαι", "υμαι", "ημι", "ωμι", "υμι", "ειμι", "εω", "αω", "οω", "ευω", "ιζω", "αζω",
    "υζω", "σσω", "ττω", "πτω", "σκω", "ζω", "νω", "ω",
    "ευσ", "ουσ", "ιον", "ια", "ιοσ", "οσ", "ον", "ησ", "ασ", "ισ", "υσ", "ων", "ωρ", "ηρ", "μα",
    "α", "η", "ξ", "ψ", "ν", "ρ", "σ", "ι", "υ",
], key=len, reverse=True)

_PREVERBS = [   # (spelling in the lemma, spellings in inflected forms: full, elided, assimilated)
    ("αντι", ("αντι", "αντ", "ανθ")), ("απο", ("απο", "απ", "αφ")), ("ανα", ("ανα", "αν")),
    ("δια", ("δια", "δι")), ("εισ", ("εισ",)), ("εκ", ("εκ", "εξ")), ("εξ", ("εξ", "εκ")),
    ("εν", ("εν", "εμ", "εγ", "ελ")), ("εμ", ("εμ", "εν")), ("εγ", ("εγ", "εν")),
    ("επι", ("επι", "επ", "εφ")), ("κατα", ("κατα", "κατ", "καθ")), ("μετα", ("μετα", "μετ", "μεθ")),
    ("παρα", ("παρα", "παρ")), ("περι", ("περι",)), ("προσ", ("προσ",)), ("προ", ("προ", "πρου")),
    ("συν", ("συν", "συμ", "συγ", "συλ", "συσ", "συ")), ("συμ", ("συμ", "συν")),
    ("συγ", ("συγ", "συν")), ("συλ", ("συλ", "συν")), ("υπερ", ("υπερ",)), ("υπο", ("υπο", "υπ", "υφ")),
]
_AUGMENTS = {"ε": "", "η": "αε", "ω": "ο", "ει": "ει", "ηυ": "ευαυ", "ηι": "αι"}


_PREVERB_CANON = {"εξ": "εκ", "εμ": "εν", "εγ": "εν", "συμ": "συν", "συγ": "συν", "συλ": "συν"}


def _leading_preverb(bare: str) -> Optional[Tuple[str, int]]:
    """(preposition, letters used) a word begins with (ἐπ-έλειχον -> ἐπι, ἀπ-έλειχον -> ἀπο,
    ἐξ- -> ἐκ), or None; the longest spelling wins and at least four letters must follow it."""
    best: Optional[Tuple[str, int]] = None
    for full, variants in _PREVERBS:
        for v in variants:
            if bare.startswith(v) and len(bare) >= len(v) + 4 and (best is None or len(v) > best[1]):
                best = (_PREVERB_CANON.get(full, full), len(v))
    return best


def _preverb_split(bare: str) -> Tuple[Tuple[str, ...], str]:
    """Leading prepositions and the rest: διαπαρατριβαί -> (δια, παρα), τριβαι.  ἐν- and ἐκ-
    before a guttural (ἐγκακέω / ἐκκακέω) count as one spelling."""
    pre: List[str] = []
    rest = bare
    while True:
        got = _leading_preverb(rest)
        if not got:
            break
        p, n = got
        if p == "εκ" and rest[n:n + 1] in ("κ", "γ", "χ"):
            p = "εν"
        pre.append(p)
        rest = rest[n:]
    return tuple(pre), rest


_STEMS_CACHE: Dict[str, List[str]] = {}


def _stems(lemma_bare: str) -> List[str]:
    hit = _STEMS_CACHE.get(lemma_bare)
    if hit is None:
        hit = _STEMS_CACHE[lemma_bare] = _compute_stems(lemma_bare)
    return hit


# Irregular / suppletive principal-part stems used ONLY by stem_similarity() to pair a Studio
# LXX token with a lemma already present in that same verse's gold LxxLemmas list.
_IRREG_LXX_STEMS: Dict[str, Tuple[str, ...]] = {
    "λειπω": ("λιπ", "λοιπ"), "φευγω": ("φυγ",), "πειθω": ("πιθ", "ποιθ"),
    "τρεπω": ("τραπ",), "στρεφω": ("στραφ",), "τρεφω": ("τραφ",),
    "τεμνω": ("ταμ", "τμη"), "καμνω": ("καμ",), "βαινω": ("βη", "βα"),
    "εχω": ("σχ", "εξ"), "φερω": ("οισ", "ενεγκ", "ηνεγκ", "ενηνοχ"),
    "εσθιω": ("φαγ", "εδ"), "φαγω": ("φαγ", "εδ"), "τρωγω": ("φαγ",),
    "λαμβανω": ("λαβ", "ληφ", "λημφ", "λημψ", "ληψ"),
    "λανθανω": ("λαθ", "λησ"), "μανθανω": ("μαθ",), "τυγχανω": ("τυχ", "τευξ"),
    "πιπτω": ("πεσ", "πτω"), "τρεχω": ("δραμ",), "πινω": ("πι", "ποθ"),
    "οραω": ("ιδε", "ιδη", "ιδει", "ιδο", "ειδ", "οφθ", "οψ", "εορακ", "εωρακ", "ωρακ"),
    "λεγω": ("ειπ", "ερ", "ρηθ"), "επω": ("ειπ",),
    "ερχομαι": ("ελθ", "ελευσ"), "γινομαι": ("γεν",), "γινωσκω": ("γνω",),
    "ζαω": ("ζα", "ζη", "ζησ", "ζω"), "ετοσ": ("ετου", "ετη", "ετων", "ετεσ"),
    "κλινω": ("κλιθ",), "κρινω": ("κριθ",), "πλυνω": ("πλυθ",),
    "τελλω": ("ταλ", "τειλ"), "στελλω": ("σταλ", "στειλ"),
    "αιρω": ("αρ", "ηρ", "αρθ", "ηρθ"), "αιρεω": ("ειλ", "ελ"),
    "κραζω": ("κραξ", "κραγ"), "ρηγνυμι": ("ραγ", "ρηξ"),
    "ολεθρευω": ("ολεθρ", "ωλεθρ", "ολοθρ", "ωλοθρ"),
    "ολοθρευω": ("ολοθρ", "ωλοθρ", "ολεθρ", "ωλεθρ"),
    "χαιρω": ("χαρ",), "θνησκω": ("θαν", "θνη"), "καλεω": ("κλη",),
    "βαλλω": ("βαλ", "βλη"), "απολλυμι": ("απολ", "απωλ"), "ολλυμι": ("ολ", "ωλ"),
    "ομνυμι": ("ομ", "ωμ"),
    "ευρισκω": ("ευρ", "ηυρ"), "ρυομαι": ("ρυσ", "ερρυσ", "ερυσ"),
    "αγω": ("αγ", "ηγ", "αξ", "ηξ", "αχθ", "ηχθ", "αγιοχ"),
    "αδω": ("αδ", "ασ", "ησ"), "θυω": ("θυ", "θυσ", "τυθ"),
    "απτω": ("απτ", "αψ", "αφ", "ηψ", "ηφ"), "απτομαι": ("απτ", "αψ", "αφ", "ηψ", "ηφ"),
    "ιαομαι": ("ια", "ιασ", "ιαθ"), "κτεινω": ("κτειν", "κταν", "κτον"),
    "μναομαι": ("μνα", "μνησ", "μνη"), "χραω": ("χρα", "χρη", "χρησ"),
    "στρωννυμι": ("στρω", "στρωσ", "στορ"), "ζωννυμι": ("ζωσ", "ζων"),
    "νιπτω": ("νιπ", "νιψ", "νιφ"), "εαω": ("εα", "ειασ", "εασ"),
    "χεω": ("χε", "χευ", "χυθ", "χυ"), "καταραομαι": ("κατηρ", "καταρ"),
    "σπειρω": ("σπερ", "σπαρ", "σπορ"), "φαινω": ("φαν", "φην"),
    "κρεμαννυμι": ("κρεμα", "κρεμασ"), "ελαυνω": ("ελα", "ελασ", "ηλα"),
    "δεικνυμι": ("δεικ", "δειξ", "δειγ"), "κολαπτω": ("κολαπ", "κολαμ", "κολαφ", "κολαψ"),
    "ερευναω": ("ερευν", "εραυν", "ηραυν"), "οσφραινομαι": ("οσφραν", "οσφρη"),
    "συνιημι": ("συνι", "συνη", "συνει"), "ενοχλεω": ("ενοχλ", "ηνοχλ", "ηνωχλ"),
    "λυω": ("λυ", "λυσ", "λυθ"), "ρεω": ("ρε", "ρυ", "ρρυ"),
    "δυναμαι": ("δυνα", "ηδυνα", "δυνη", "ηδυνη"), "δυναμοω": ("δυναμ", "ηδυναμ"),
    "ωθεω": ("ωθ", "ωσ"), "πηγνυμι": ("πηγ", "παγ", "πηξ"),
    "μιαινω": ("μιαν", "μιαμ"), "κλαιω": ("κλαυ", "κλαι"),
    "μαινομαι": ("μαν",), "αφικνεομαι": ("αφικ",), "δυνω": ("δυ",),
    "ψαω": ("ψη", "ψα"), "ευχομαι": ("ευχ", "ευξ", "ηυξ"),
    "πεταμαι": ("πετ", "πτ", "ιπτ"), "επειδον": ("εφιδ", "επιδ"),
    "διαρραινω": ("διερραγκ", "διαρραν"), "ανασωζω": ("ανασω", "ανασεσω"),
    "προιημι": ("προι", "προη", "προω"),
    "γηρασ": ("γηρ",), "ναυσ": ("ναυ", "νη", "νε"), "ρισ": ("ριν",),
    "ωδη": ("ωδ",), "αρα": ("αρ",), "ροα": ("ροα",), "γη": ("γη", "γαι"),
    "εγγυσ": ("εγγυ", "εγγιστ", "εγγυτ"),
    "περαν": ("περα",), "παισ": ("παιδ", "παισ"), "ιβησ": ("ιβ", "ειβ"), "ιν": ("ειν", "ιν"),
    "τιθημι": ("θη", "θε", "τεθ"), "τιθεμαι": ("θη", "θε", "τεθ"),
    "διδωμι": ("δω", "δο", "δοθ"), "ιημι": ("ι", "η", "εθ", "εικ"),
    "ιστημι": ("στη", "στα", "στ"), "ισταμαι": ("στη", "στα", "στ"),
}

# Closed-class pronoun / indefinite forms rarely or never printed in TAGNT, used ONLY when
# the target lemma key is already in the verse's gold LxxLemmas slots.
_CLOSED_LXX_FORMS: Dict[str, Set[str]] = {
    "G4572": {"σαυτου", "σαυτω", "σαυτον", "σαυτησ", "σαυτη", "σαυτην",
              "σεαυτησ", "σεαυτη", "σεαυτην"},
    "G4674": {"σοσ", "ση", "σον", "σησ", "σω", "σην", "σαι", "σα", "σων", "σοισ", "σαισ", "σουσ", "σασ"},
    "G3745": {"οσοσ", "οση", "οσον", "οσου", "οσησ", "οσω", "οσην", "οσοι", "οσαι", "οσα",
              "οσων", "οσοισ", "οσαισ", "οσουσ", "οσασ"},
    "G3762": {"ουθεισ", "ουθεν", "ουθενοσ", "ουθενι", "ουθενα"},
    "G3367": {"μηθεισ", "μηθεν", "μηθενοσ", "μηθενι", "μηθενα"},
    "G3592": {"οδε", "ηδε", "τοδε", "τουδε", "τησδε", "τωδε", "τηδε", "τονδε", "τηνδε",
              "οιδε", "αιδε", "ταδε", "τωνδε", "τοισδε", "ταισδε", "τουσδε", "τασδε"},
    "G3746": {"οσπερ", "ηπερ", "οπερ", "ουπερ", "ησπερ", "ωπερ", "ονπερ", "ηνπερ",
              "οιπερ", "αιπερ", "απερ"},
    "G21422": {"τοιοσ", "τοια", "τοιον", "τοιου", "τοιασ", "τοιω",
               "τοιοι", "τοιαι", "τοιων", "τοιοισ", "τοιαισ", "τοιουσ"},
}

# Unambiguous Koine aspirated aorist forms of ἐπεῖδον (G1896 = ἐφοράω 'to look upon':
# ἐφιδεῖν, ἐφίδῃ, ἔφιδε, Ἐφίδοι).
_EPIDON_BARE = frozenset({"εφιδειν", "εφιδη", "εφιδε", "εφιδοι", "εφιδησ", "εφιδον", "εφιδωσιν"})

# Contracted reflexive forms of ἑαυτοῦ (G1438) distinguished from αὐτός (G0846) by rough breathing.
_CONTRACTED_REFLEXIVE_BARE = frozenset({
    "αυτου", "αυτησ", "αυτω", "αυτη", "αυτον", "αυτην",
    "αυτων", "αυτοισ", "αυταισ", "αυτουσ", "αυτασ",
})

# Milesian (alphabetic) Greek numerals printed with keraia in Swete (e.g. μ᾽ = 40, ιδ᾽ = 14)
# -> canonical TBESG numeral lemma key.  Only unambiguous single-word numerals absent from _ELIDED.
_GREEK_NUMERALS: Dict[str, str] = {
    "α": "G1520", "β": "G1417", "ε": "G4002", "ζ": "G2033", "η": "G3638", "θ": "G1767",
    "ι": "G1176", "ια": "G1733", "ιβ": "G1427", "ιδ": "G1180", "ιε": "G1178",
    "κ": "G1501", "λ": "G5144", "μ": "G5062", "ν": "G4004", "ξ": "G1835",
    "ο": "G1440", "π": "G3589", "ρ": "G1540", "σ": "G1250", "υ": "G5071",
    "φ": "G4001", "χ": "G1812",
}


def _milesian_numeral_key(token: str) -> Optional[str]:
    """If ``token`` is an unaccented Greek alphabetic numeral with keraia (e.g. μ᾽, ιδ᾽, χ᾽),
    return its canonical TBESG lemma key; else None."""
    if not _has_elision(token):
        return None
    b = greek_bare(token)
    if not b or b in _ELIDED or accent_key(token) != b:
        return None
    return _GREEK_NUMERALS.get(b)


def _is_contracted_reflexive(token: str) -> bool:
    """True for rough-breathing contracted forms of ἑαυτοῦ (αὑτοῦ, αὑτῇ, αὑτόν), never αὐτοῦ."""
    b = greek_bare(token)
    if b not in _CONTRACTED_REFLEXIVE_BARE:
        return False
    nfd = unicodedata.normalize("NFD", accent_key(token))
    return "̔" in nfd[:5]


def _is_smooth_autai(token: str) -> bool:
    """True for smooth-breathing αὐταί / αὐταὶ (G0846 αὐτός), never rough-breathing αὗται (G3778)."""
    if greek_bare(token) != "αυται":
        return False
    nfd = unicodedata.normalize("NFD", accent_key(token))
    return "̓" in nfd[:5] and "̔" not in nfd[:5]


def _is_crasis_autos(token: str) -> bool:
    """True for crasis ταὐτά / ταὐτό / ταὐτοῦ (= τὰ αὐτά, coronis/smooth breathing over υ)."""
    b = greek_bare(token)
    if b not in ("ταυτα", "ταυτο", "ταυτου", "ταυτω", "ταυτον"):
        return False
    return "ὐ" in token.lower() or "ὔ" in token.lower() or "ὒ" in token.lower() or "ὖ" in token.lower()


def _compute_stems(lemma_bare: str) -> List[str]:
    if lemma_bare == "πασ":
        return ["πασ", "παντ", "παν"]
    out = [lemma_bare]
    for e in _LEMMA_ENDINGS:
        if lemma_bare.endswith(e) and len(lemma_bare) - len(e) >= 2:
            st = lemma_bare[: -len(e)]
            if st not in out:
                out.append(st)
            break
    # contract verbs lengthen the stem vowel (ποιε- -> ποιη-, τιμα- -> τιμη-); -ιζω Attic futures (-ιω/-ιεις)
    for full, short in (("εω", "η"), ("αω", "η"), ("οω", "ω")):
        if lemma_bare.endswith(full) and len(lemma_bare) > 3:
            out.append(lemma_bare[:-2] + short)
    if lemma_bare.endswith("ιζω") and len(lemma_bare) >= 6:
        st = lemma_bare[:-3] + "ι"
        if st not in out:
            out.append(st)
    # sigmatic / passive verb stems: -πτω -> -ψ/-φ, -σσω/-ττω -> -ξ/-χ/-γ, -χω/-γω/-κω -> -ξ/-χθ
    for suf, repls in (("πτω", ("ψ", "φ", "β")), ("πτομαι", ("ψ", "φ", "β")),
                       ("σσω", ("ξ", "χ", "γ", "κ")), ("ττω", ("ξ", "χ", "γ", "κ")),
                       ("σσομαι", ("ξ", "χ", "γ", "κ")), ("ττομαι", ("ξ", "χ", "γ", "κ")),
                       ("χω", ("ξ", "χθ")), ("γω", ("ξ", "χθ")), ("κω", ("ξ", "χθ"))):
        if lemma_bare.endswith(suf) and len(lemma_bare) - len(suf) >= 2:
            base = lemma_bare[:-len(suf)]
            for r in repls:
                st = base + r
                if st not in out:
                    out.append(st)
            break
    # reduplicated -μι presents: τί-θη-μι, δί-δω-μι, ἵ-στη-μι -> θη/θε, δω/δο, στη/στα
    if lemma_bare.endswith(("ημι", "ωμι")) and len(lemma_bare) >= 5:
        core = lemma_bare[2:-2] if lemma_bare[1] == "ι" and lemma_bare[0] != "ι" else lemma_bare[1:-2]
        if len(core) >= 2:
            short = core[:-1] + {"η": "ε", "ω": "ο"}[core[-1]] if core[-1] in "ηω" else core
            for st in (core, short, core[:-1] + "α" if core.endswith("στη") else None):
                if st and st not in out:
                    out.append(st)
    # reduplicated -σκω presents: βιβρώσκω -> βρω, διδράσκω -> δρα, μιμνήσκω -> μνη, τιτρώσκω -> τρω
    if lemma_bare.endswith(("σκω", "σκομαι")) and len(lemma_bare) >= 6 and lemma_bare[1] == "ι":
        cut = 3 if lemma_bare.endswith("σκω") else 6
        core = lemma_bare[2:-cut]
        if len(core) >= 3 and core not in out:
            out.append(core)
    # -ννυμι / -νυμι presents: σβέννυμι -> σβεσ, ζώννυμι -> ζωσ, σκεδάννυμι -> σκεδασ, δείκνυμι -> δεικ
    if lemma_bare.endswith(("ννυμι", "ννυμαι")) and len(lemma_bare) >= 7:
        cut = 5 if lemma_bare.endswith("ννυμι") else 6
        s = lemma_bare[:-cut]
        for st in (s, s + "σ"):
            if len(st) >= 3 and st not in out:
                out.append(st)
    elif lemma_bare.endswith(("νυμι", "νυμαι")) and len(lemma_bare) >= 6:
        cut = 4 if lemma_bare.endswith("νυμι") else 5
        s = lemma_bare[:-cut]
        if len(s) >= 3 and s not in out:
            out.append(s)
    for st in _IRREG_LXX_STEMS.get(lemma_bare, ()):
        if st not in out:
            out.append(st)
    return out


def _lcp(a: str, b: str) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def _is_verb_lemma(lemma_bare: str) -> bool:
    return lemma_bare.endswith(("ω", "μαι", "μι"))


def _strip_augment(t: str, lemma_core: str) -> List[str]:
    """Token variants with a verbal augment / reduplication removed (verb lemmas only, so
    ἐφορᾷ is never read as an augmented form of the noun φορά)."""
    outs = [t]
    if len(t) > 3 and _is_verb_lemma(lemma_core):
        if t[0] == "ε" and (not lemma_core.startswith("ε") or lemma_core in _IRREG_LXX_STEMS):
            outs.append(t[1:])
        if t[:2] == "ει" and not lemma_core.startswith("ει"):
            outs.append(t[2:])
        if t[0] == "η" and lemma_core[:1] in ("α", "ε"):
            outs.append(lemma_core[0] + t[1:])
        if t[0] == "η" and lemma_core[:2] in ("αι", "ει"):
            outs.append(lemma_core[:2] + t[1:])
        if t[0] == "ω" and lemma_core[:1] == "ο":
            outs.append("ο" + t[1:])
        if t[0] == "ω" and lemma_core[:2] == "οι":
            outs.append("οι" + t[1:])
        if t[:2] == "ηυ" and lemma_core[:2] in ("ευ", "αυ"):
            outs.append(lemma_core[:2] + t[2:])
        # reduplication: λε-λυκα, πε-ποιηκα, γε-γραφα; pluperfect / reduplicated aorist ἐ-κέ-κραξαν
        if len(t) > 4 and t[1] == "ε" and t[0] == lemma_core[:1]:
            outs.append(t[2:])
        if len(t) > 4 and t[1] == "ε" and t[0] in "πτκ" and lemma_core[:1] in "φθχ":
            outs.append(t[2:])
        if len(t) > 5 and t[0] == "ε" and t[2] == "ε" and (
                t[1] == lemma_core[:1] or (t[1] in "πτκ" and lemma_core[:1] in "φθχ")):
            outs.append(t[3:])
    return outs


def _augment_variants(core: str) -> List[str]:
    """A form with a possible augment or reduplication removed (lemma unknown): ἐλήμφθη ->
    λήμφθη, ὤφθη -> ὀφθη, ἠγάπησεν -> ἀγάπησεν / ἐγάπησεν, πεποίηκα -> ποίηκα."""
    out = [core]
    if len(core) > 3:
        if core[:2] == "ει":
            out.append(core[2:])
        elif core[0] == "ε":
            out.append(core[1:])
        if core[:2] == "ηυ":
            out += ["ευ" + core[2:], "αυ" + core[2:]]
        elif core[0] == "η":
            out += ["α" + core[1:], "ε" + core[1:], "αι" + core[1:], "ει" + core[1:]]
        if core[0] == "ω":
            out += ["ο" + core[1:], "οι" + core[1:]]
        if len(core) > 4 and core[1] == "ε" and core[0] not in "αεηιουω" and core[0] in core[2:4]:
            out.append(core[2:])
    return out


_LB_CACHE: Dict[str, str] = {}


def _lemma_bare(gkey: str) -> str:
    """Greek Word List key ('ἀλλόφυλος' is keyed 'αλλοφυλος', homographs 'ορος.1') -> the
    bare letters with final sigma folded, as greek_bare() writes tokens."""
    v = _LB_CACHE.get(gkey)
    if v is None:
        v = _LB_CACHE[gkey] = greek_bare(gkey.split(".")[0])
    return v


_SIM_CACHE: Dict[Tuple[str, str], float] = {}


def stem_similarity(token_bare: str, lemma_bare: str) -> float:
    """How far the token's letters continue the lemma's stem (0..1).  Used only to pair a token
    with one of the lemmas that the gold data lists for the same verse."""
    k = (token_bare, lemma_bare)
    v = _SIM_CACHE.get(k)
    if v is None:
        if len(_SIM_CACHE) > 2_000_000:
            _SIM_CACHE.clear()
        v = _SIM_CACHE[k] = _stem_similarity(token_bare, _lemma_bare(lemma_bare))
    return v


# Preverb families used by _stem_similarity() to peel 1-2 matching preverbs (including elided
# preverbs in vowel-initial compound lemmas like ἀπ-αντάω, ἀν-οικοδομέω, δι-αρπάζω, ἐπ-ελπίζω,
# and εὐ- compounds like εὐ-οδόω / εὐωδώθη).  Ordered longest-first within each family.
_STEM_PREVERBS: Tuple[Tuple[str, ...], ...] = (
    ("αντι", "αντ", "ανθ"), ("απο", "απ", "αφ"), ("ανα", "αν"),
    ("δια", "δι"), ("εισ",), ("εξ", "εκ"),
    ("εν", "εμ", "εγ", "ελ"), ("επι", "επ", "εφ"),
    ("κατα", "κατ", "καθ"), ("μετα", "μετ", "μεθ"),
    ("παρα", "παρ"), ("περι",), ("προσ",), ("προ", "πρου"),
    ("συν", "συμ", "συγ", "συλ", "συσ", "συ"),
    ("υπερ",), ("υπο", "υπ", "υφ"), ("ευ",),
    ("παν", "παγ", "παμ"),
)

_NASAL_VELAR = re.compile(r"ν(?=[κγχξ])")
_NASAL_LABIAL = re.compile(r"ν(?=[πβφψμ])")
_DBL_CONS = re.compile(r"([βγδζθκλμνξπρστφχψ])\1")


@lru_cache(maxsize=200000)
def _ortho_norm(s: str) -> str:
    """Normalise Codex B / Koine orthographic variants (unassimilated nasals νκ/νπ/νλ/συνσ,
    μπτ/μφ/μψ, ει/ι, γιγν/γιν, ολοθρ/ολεθρ, doubled consonants)."""
    x = s.replace("ει", "ι").replace("γιγν", "γιν").replace("ολοθρ", "ολεθρ")
    if "ν" in x:
        x = _NASAL_VELAR.sub("γ", x)
        x = _NASAL_LABIAL.sub("μ", x)
        x = x.replace("νλ", "λλ").replace("συνσ", "συσ")
    if "μ" in x:
        x = x.replace("μπτ", "πτ").replace("μφ", "φ").replace("μψ", "ψ")
    return _DBL_CONS.sub(r"\1", x)


@lru_cache(maxsize=100000)
def _propn_norm(s: str) -> str:
    """Normalise Codex B / Swete proper-name spelling variants (ει/ι, αι/ε, ω/ο, doubled letters)."""
    x = s.replace("ει", "ι").replace("αι", "ε").replace("ω", "ο")
    return _DBL_CONS.sub(r"\1", x)


_PROPN_CONS_TABLE = str.maketrans({
    "φ": "β", "π": "β",
    "θ": "τ", "δ": "τ",
    "χ": "κ", "γ": "κ",
    "ζ": "σ",
    "ρ": "λ",
    "μ": "ν",
    "ε": "α", "η": "ι", "υ": "ι", "ω": "ο",
})


@lru_cache(maxsize=100000)
def _propn_cons_norm(s: str) -> str:
    """Coarser Hebrew-transliteration class normalisation for same-verse proper-name alignment
    (catches Codex B consonant interchanges β/φ/π, δ/θ/τ, γ/κ/χ, ζ/σ, λ/ρ, μ/ν)."""
    x = s.replace("ει", "ι").replace("αι", "α").replace("ου", "ο").replace("οι", "ι")
    x = _DBL_CONS.sub(r"\1", x)
    return _DBL_CONS.sub(r"\1", x.translate(_PROPN_CONS_TABLE))


def _propn_similarity(tb: str, lb: str) -> float:
    """Edit-based similarity (0..1) for a capitalised token facing a proper-name lemma in the
    same verse (catches prosthetic vowels Ἐρειφάθ/Ῥιφάθ, Ἰουδαδάν/Οὐδαδάν, Ζαρειά/Ἀζαρία)."""
    nx, ny = _propn_norm(tb), _propn_norm(lb)
    if not nx or not ny:
        return 0.0
    if nx == ny:
        return 0.96
    return difflib.SequenceMatcher(None, nx, ny, autojunk=False).ratio()


def _propn_cons_sim(tb: str, lb: str) -> float:
    """Consonant-class edit similarity for a same-verse proper-name / Hebrew-transliteration pair."""
    nx, ny = _propn_cons_norm(tb), _propn_cons_norm(lb)
    if not nx or not ny:
        return 0.0
    if nx == ny:
        return 0.92
    return difflib.SequenceMatcher(None, nx, ny, autojunk=False).ratio()


_GAP_VOWELS = frozenset("αεηιουω")


@lru_cache(maxsize=100000)
def _gap_ortho_norm(s: str) -> str:
    """Normalise Codex B / Koine spelling variants for 1-to-1 same-verse gap confirmation
    (ει/ι/η/υι, αι/ε, ω/ο, μβ/β, μπ/π, ντ/τ, εγ/εκ, doubled consonants)."""
    x = _ortho_norm(s)
    x = x.replace("υι", "ι").replace("αι", "ε").replace("η", "ι").replace("ω", "ο")
    x = x.replace("μβ", "β").replace("μπ", "π").replace("ντ", "τ")
    if x.startswith("εγ"):
        x = "εκ" + x[2:]
    return _DBL_CONS.sub(r"\1", x)


def _gap_ortho_match(tb: str, lb: str) -> bool:
    """True when an unattested token and a single unused content lemma in a 1-to-1 gap are
    orthographic / Codex B spelling variants (μιερὸς/μιαρός, ἐφνιδίως/αἰφνιδίως, ἀρωδιὸν/ἐρωδιός,
    ῥιτίνης/ῥητίνη, βοββήσει/βομβέω, ῥοβοπῶλαι/ῥωποπώλης, or lowercase Hebrew transliterations)."""
    if not tb or not lb:
        return False
    if tb in _EPIDON_BARE:
        return lb == "επειδον"
    if lb == "ποα" and tb in ("ποια", "ποιαν", "ποιασ", "ποιαι"):
        return True
    if lb == "ιβισ" and tb in ("ειβιν", "ειβισ", "ειβι"):
        return True
    if len(tb) < 4 or len(lb) < 4:
        return False
    nt, nl = _gap_ortho_norm(tb), _gap_ortho_norm(lb)
    # 1. Full orthographic form match (e.g. μιερος/μιαρος, εφνιδιως/αιφνιδιως, ριτινης/ρητινη)
    full_r = difflib.SequenceMatcher(None, nt, nl, autojunk=False).ratio()
    same_start = (nt[0] == nl[0]) or (nt[0] in _GAP_VOWELS and nl[0] in _GAP_VOWELS)
    if full_r >= 0.80 and same_start:
        return True
    # 2. Stem-prefix match under orthographic normalisation (handles verb/noun inflectional endings)
    for st in _stems(lb):
        if len(st) < 4:
            continue
        nst = _gap_ortho_norm(st)
        if len(nst) < 4:
            continue
        pref = nt[:len(nst)]
        if len(pref) >= 4:
            r = difflib.SequenceMatcher(None, pref, nst, autojunk=False).ratio()
            if r >= 0.82 and (pref[0] == nst[0] or (pref[0] in _GAP_VOWELS and nst[0] in _GAP_VOWELS)):
                return True
            # single vowel-to-vowel swap on a 4+ letter stem with all consonants identical
            # (μιεραῖς/μιαρός, ἀρωδιὸν/ἐρωδιός, ὀμείρονται/ἱμείρομαι)
            if len(pref) == len(nst):
                diffs = [(x, y) for x, y in zip(pref, nst) if x != y]
                if len(diffs) == 1 and diffs[0][0] in _GAP_VOWELS and diffs[0][1] in _GAP_VOWELS:
                    return True
            # labial / dental voicing or aspiration shift inside a 5+ letter stem (εφισος/επισος, ροβοπωλ/ρωποπωλ)
            if len(nst) >= 5 and _propn_cons_norm(pref) == _propn_cons_norm(nst):
                return True
    # 3. Indeclinable lowercase Hebrew transliterations (θοαμαὶ/θολμαι, σαλημὼθ/σαδημωθ, ταβείν/γαβιν)
    if not _is_verb_lemma(lb) and not lb.endswith(("οσ", "ησ", "ον", "μα", "ισ", "υσ", "ωσ", "ων")):
        if len(tb) >= 4 and len(lb) >= 4 and _propn_cons_sim(tb, lb) >= 0.78:
            return True
    return False


def _peel_preverbs(t: str, l: str, depth: int = 0) -> Tuple[List[Tuple[str, str, int]], int]:
    """Strip 1-2 matching preverbs from ``(t, l)``; returns (list of (rest_t, rest_l, pv_len),
    leading lemma preverb length for the preverb-only guard)."""
    out: List[Tuple[str, str, int]] = []
    pv0 = 0
    is_verb = _is_verb_lemma(l)
    for fam in _STEM_PREVERBS:
        matched_fam = False
        for lv in fam:
            if l.startswith(lv) and len(l) > len(lv) + 2:
                matched_fam = True
                if pv0 == 0:
                    pv0 = len(lv)
                rest_l = l[len(lv):]
                for tv in fam:
                    t_cands: List[str] = []
                    if t.startswith(tv) and len(t) > len(tv) + 1:
                        t_cands.append(t[len(tv):])
                    # Koine double augment before preverb (ἐ-συν-έθετο, ἐ-κατ-έλαβεν, δι-ε-παρ-ε-τηροῦντο)
                    if is_verb and t.startswith("ε" + tv) and len(t) > len(tv) + 2:
                        t_cands.append(t[len(tv) + 1:])
                    for rest_t in t_cands:
                        out.append((rest_t, rest_l, len(lv)))
                        if tv.endswith("σ") and rest_l == "εχω" and rest_t.startswith("χ"):
                            out.append(("σ" + rest_t, rest_l, len(lv)))   # προσ-σχες -> πρόσχες
                        if depth == 0:
                            sub, _ = _peel_preverbs(rest_t, rest_l, depth=1)
                            for st, sl, spv in sub:
                                out.append((st, sl, len(lv) + spv))
                # If lv ended in a vowel (e.g. 'δια' on 'διαρπαζω'), also try the elided variant
                # ('δι' leaving 'αρπαζω') so augmented α-initial stems (διήρπασεν) match.
                if lv[-1] not in "αειο":
                    break
        if matched_fam:
            break
    return out, pv0


def _stem_similarity(t: str, l: str) -> float:
    if not t or not l:
        return 0.0
    if t == l:
        return 1.0
    best = 0.0
    cores: List[Tuple[str, str, bool]] = [(t, l, False)]
    if "ει" in t or "ει" in l:
        # Codex B's itacistic spellings (Λευεῖται / Λευίτης, Ἐλεισαῖε / Ἐλισαιε)
        ti, li = t.replace("ει", "ι"), l.replace("ει", "ι")
        if ti == li:
            return 0.95
        cores.append((ti, li, False))
    # Codex B unassimilated nasals, nasal-labial spellings (συνελήμφθη, ἀντιλήμπτωρ), Attic γιγν-,
    # ολοθρ/ολεθρ, and doubled consonants (οἴμμοι / οἴμοι)
    tn, ln = _ortho_norm(t), _ortho_norm(l)
    if tn != t or ln != l:
        if tn == ln:
            return 0.95
        cores.append((tn, ln, False))
    peeled, pv = _peel_preverbs(t, l)
    for rest_t, rest_l, _ in peeled:
        cores.append((rest_t, rest_l, True))
    if tn != t or ln != l:
        peeled_n, pv_n = _peel_preverbs(tn, ln)
        if not pv:
            pv = pv_n
        for rest_t, rest_l, _ in peeled_n:
            cores.append((rest_t, rest_l, True))
    seen_cores: Set[Tuple[str, str, bool]] = set()
    for tc, lc, compound in cores:
        if (tc, lc, compound) in seen_cores:
            continue
        seen_cores.add((tc, lc, compound))
        for st in _stems(lc):
            if len(st) < 1:
                continue
            for tv in _strip_augment(tc, lc):
                cp = _lcp(tv, st)
                if cp == 0 or (not compound and cp <= pv):
                    # nothing shared, or only the preverb (προσ-οίσει is not προσ-χέω)
                    continue
                cover = cp / len(st)
                strength = min(1.0, cp / 4.0)
                score = cover * (0.55 + 0.45 * strength)
                if cp >= 3 and cover >= 0.999:
                    score = max(score, 0.9 if cp >= 4 else 0.8)
                elif compound and cp >= 2 and cover >= 0.999:
                    # the preverb already matched: ἐπι-θήσεις / ἐπι-τί-θη-μι
                    score = max(score, 0.8)
                elif cp >= 3 and len(st) >= 4 and _one_edit(tv[:len(st)], st):
                    # one vowel grade / consonant changed inside the stem: ἀπ-έ-στειλ-εν / ἀπο-στέλλ-ω
                    score = max(score, 0.8)
                # an ending far longer than inflection allows is another word that merely
                # begins with the lemma's letters (ἀνῃρημένοις is not a form of ἀνήρ)
                extra = len(tv) - len(st)
                if extra > (9 if _is_verb_lemma(lc) else 5):
                    score *= 0.6
                best = max(best, score)
    return min(best, 0.99)


# Accent keys of the article's letters carrying an accent: the article ὁ ἡ οἱ αἱ is proclitic and
# takes an accent only before an enclitic (ὅ τε, οἵ τε); otherwise ὃ / ἣ / οἳ / αἳ is the relative.
_ACCENTED_ARTICLE_FORMS = {"ὅ", "ἥ", "οἵ", "αἵ"}
_ENCLITICS_AFTER_ARTICLE = {"τε", "γε"}
_NO_EXCL: Set[str] = frozenset()  # type: ignore[assignment]


def _context_exclusions(tokens: Sequence[str]) -> List[Set[str]]:
    """Per token, lemma keys its context rules out (the article G3588 for a relative ὃ / οἳ)."""
    out: List[Set[str]] = []
    for i, t in enumerate(tokens):
        if (len(t) <= 6 and accent_key(t) in _ACCENTED_ARTICLE_FORMS
                and not (i + 1 < len(tokens) and greek_bare(tokens[i + 1]) in _ENCLITICS_AFTER_ARTICLE)):
            out.append({"G3588"})
        else:
            out.append(set(_NO_EXCL))
    return out


# The Hebrew letter names Swete prints at the head of the acrostic stanzas of Lamentations 1-4
# (bare letters, Codex B spellings included).
_ACROSTIC_LETTERS = {
    "αλεφ", "αλφ", "βηθ", "βη", "γιμελ", "γιμλ", "δαλεθ", "δελθ", "η", "ουαυ", "ουαυ", "ζαιν", "ζαι",
    "ηθ", "τηθ", "ιωθ", "ιωδ", "χαφ", "καφ", "λαμεδ", "λαβδ", "μημ", "νουν", "σαμχ", "σαμεχ", "αιν",
    "φη", "τιαδη", "σαδη", "κωφ", "ρηχσ", "ρησ", "χσεν", "σεν", "θαυ",
}


def _acrostic_letter(slug: str, ch: int, text: str, tokens: Sequence[str]) -> Optional[int]:
    """Index of the acrostic letter name that opens a verse of Lamentations 1-4 ('Ἥ. Ἐγένοντο'),
    or None.  The name stands first and is followed by a full stop (in Lam 1:1, where Swete prints
    the LXX prologue before Ἄλεφ., and in Lam 3:45, where Swete prints Ἄιν. mid-verse after a full
    stop, the letter stands immediately after that period)."""
    if slug != "lamentations" or not tokens or not (1 <= ch <= 4):
        return None
    first = tokens[0]
    if greek_bare(first) in _ACROSTIC_LETTERS and first[:1].isupper():
        m = re.match(r"\s*(\S+?)\s*[.·]", text or "")
        if m and m.group(1).strip("".join(_ELISION_MARKS)) == first:
            return 0
    if ch == 1 and "Ἄλεφ." in (text or ""):
        for idx, tok in enumerate(tokens):
            if tok == "Ἄλεφ":
                return idx
    if ch == 3 and ". Ἄιν." in (text or ""):
        for idx, tok in enumerate(tokens):
            if tok == "Ἄιν":
                return idx
    return None


def _one_edit(a: str, b: str) -> bool:
    """True when a and b (same length) differ by one substitution inside the stem (not in its
    last letter: ἀνηγ- is not ἀνήρ, but στειλ- is στελλ-)."""
    if a == b:
        return True
    if len(a) == len(b) and a[-1:] == b[-1:]:
        return sum(1 for x, y in zip(a, b) if x != y) == 1
    return False


# ---------------------------------------------------------------------------
# The tagger
# ---------------------------------------------------------------------------

class GreekTagger:
    """Loads every source once; tags chapters of the Studio's Greek text."""

    # alignment thresholds (calibrated on the Rahlfs yardstick, see the build notes)
    STEM_ACCEPT = 0.78
    GAP_FILL_MIN = 0.0        # capitalised token facing a proper name: any shared stem letter
    GAP_FILL_STEM = 0.5       # every other between-words pairing needs this stem similarity
    DICT_SHARE = 0.95
    DICT_MIN = 2

    def __init__(self) -> None:
        self.lex = _Lexicon()
        self.nt = _NT(self.lex)
        self.lxx: Dict[str, _LxxBook] = {}
        self._load_lxx()
        self.lxx_table = self._new_table()      # filled by build_lxx_form_table()
        self._lxx_dict_ready = False
        self._known_cache: Dict[str, Set[str]] = {}
        self._known_tok_cache: Dict[str, Set[str]] = {}
        self._lemma_forms_cache: Dict[str, Set[str]] = {}
        self._forms_by_key: Optional[Dict[str, Set[str]]] = None
        self._targets_index: Dict[str, Set[str]] = {}
        self._attested_cache: Dict[Tuple[str, str, bool], bool] = {}
        self._nt_known_cache: Dict[str, Set[str]] = {}
        self._head_ok_cache: Dict[Tuple[str, str], bool] = {}
        self._linked_cache: Dict[Tuple[str, str], bool] = {}
        self._content_cache: Dict[str, bool] = {}
        self._propn_cache: Dict[str, bool] = {}
        self._closed_cache: Dict[str, bool] = {}

    # -- loading -------------------------------------------------------------------------------
    def _load_lxx(self) -> None:
        folder = _ossp_dir() / "LxxLemmas"
        names = {n for files in _LXX_FILES.values() for n, _ in files}
        for name in sorted(names):
            path = folder / f"{name}.js"
            if not _exists(path):
                continue
            with open(_fs(path), encoding="utf-8-sig") as fh:
                data = json.load(fh)
            book = _LxxBook(name, data)
            self.lxx[name] = book
            for words in data.values():
                for w in words:
                    k = self.lex.gwl_lemma_key(w["key"])
                    pos = _gwl_pos(self.lex.gwl.get(w["key"], {}))
                    self.lex.note_lemma(k, head=w.get("lemma", ""), pos=pos, source=SRC_OSSP, gwl_key=w["key"])

    # -- lexicon -------------------------------------------------------------------------------
    def lexicon(self) -> Dict[str, LemmaEntry]:
        lex = self.lex
        if not lex.entries:
            for key in list(lex._entry_info.keys()):
                lex.entries[key] = lex.build_entry(key)
        return lex.entries

    # -- form knowledge -------------------------------------------------------------------------
    def known_keys(self, token: str) -> Set[str]:
        """Lemma keys a tagged corpus attests for this form (TAGNT, and after the first pass the
        LXX's own unambiguous pairings); accent-aware, see _FormTable."""
        hit = self._known_tok_cache.get(token)
        if hit is not None:
            return hit
        # a capitalised token keeps only lemmas the corpus prints capitalised: its own cache entry
        ck = accent_key(token) + ("'" if _has_elision(token) else "") + ("^" if token[:1].isupper() else "")
        hit = self._known_cache.get(ck)
        if hit is None:
            hit = self.nt.forms.known(token) | self.lxx_table.known(token)
            if not token[:1].isupper():
                # a lower-case word is not 'attested' for a name the corpora print capitalised
                # only: TAGNT's Χλόης (Chloe) does not make Ps 22:2 χλόης 'grass' a known form of
                # the name, so the verse's own lemma χλόη can still take it
                hit = {k for k in hit if not (self.is_propn(k) and self._always_capitalised(k))}
            self._known_cache[ck] = hit
        self._known_tok_cache[token] = hit
        return hit

    def _always_capitalised(self, key: str) -> bool:
        tot = self.nt.forms.total[key] + self.lxx_table.total[key]
        return tot > 0 and self.nt.forms.caps[key] + self.lxx_table.caps[key] >= tot

    def is_content(self, key: Optional[str]) -> bool:
        if not key:
            return True
        v = self._content_cache.get(key)
        if v is None:
            v = self._content_cache[key] = self.lex.is_content(key)
        return v

    def is_closed_class(self, key: str) -> bool:
        v = self._closed_cache.get(key)
        if v is None:
            v = self._closed_cache[key] = (not self.is_content(key)) or self.lex.pos(key) in (
                "PREP", "ART", "CONJ", "PART", "PRON", "INTERJ")
        return v

    def is_propn(self, key: str) -> bool:
        v = self._propn_cache.get(key)
        if v is None:
            v = self._propn_cache[key] = self.lex.pos(key) == "PROPN"
        return v

    def nt_known(self, token: str) -> Set[str]:
        """Lemma keys TAGNT itself attests for this form (the LXX first-pass pairings excluded)."""
        hit = self._nt_known_cache.get(token)
        if hit is None:
            hit = self._nt_known_cache[token] = self.nt.forms.known(token)
        return hit

    def head_accents_agree(self, token: str, gkey: str) -> bool:
        """For a token with the same letters as the Word List headword: do breathing and accent
        allow the same word?  ἦ (oath, 'truly') is not ἤ 'or'; ἕν is not ἐν.  Headwords printed
        without diacritics (most names) never object."""
        ck = (accent_key(token), gkey)
        v = self._head_ok_cache.get(ck)
        if v is None:
            head = self.lex.gwl.get(gkey, {}).get("lemma", "")
            ha = accent_key(head)
            if not ha or ha == greek_bare(head):
                v = True
            elif greek_bare(head) == "ω" and greek_bare(ck[0]) == "ω" and "̔" not in unicodedata.normalize("NFD", ck[0]):
                # the interjection ὦ is printed ὢ / ὤ / Ὢ too; only a rough breathing (ᾧ, ὧ) makes it the relative
                v = True
            else:
                tb, tpos = _accent_sig(ck[0])
                hb, hpos = _accent_sig(ha)
                v = (tb == hb or tb == greek_bare(tb) or hb == greek_bare(hb)) and _accents_compatible(tpos, hpos)
            self._head_ok_cache[ck] = v
        return v

    def linked(self, a: str, b: str) -> bool:
        """Two lemma keys for one word under different lemmatisation conventions: TBESG links them
        (ὁράω 'a Meaning of' εἴδω, φαγεῖν 'a Form of' ἐσθίω), or they share a root family and a
        part of speech (μιμνήσκω / μνάομαι).  γνῶσις / γινώσκω (noun / verb) are not linked."""
        if a == b:
            return True
        ck = (a, b) if a < b else (b, a)
        v = self._linked_cache.get(ck)
        if v is None:
            t = self.lex.tbesg

            def targets(k: str) -> Set[str]:
                out = {k}
                for r in t.by_estrong.get(k, []):
                    m = re.match(r"(G\d+[A-Z]?)", r["target"] or "")
                    if m:
                        out.add(t.estrong_of.get(m.group(1), _gkey(int(re.sub(r"\D", "", m.group(1)[:6]) or 0))))
                return out

            v = bool(targets(a) & targets(b))
            if not v and self.lex.pos(a) == self.lex.pos(b):
                # the permissive derivation walk (unchanged since the tagger was verified), not the
                # conservative reader-facing families
                v = self.lex.root_of(a, strict=False)[0] == self.lex.root_of(b, strict=False)[0]
            self._linked_cache[ck] = v
        return v

    # -- New Testament ------------------------------------------------------------------------
    def tag_nt_verse(self, slug: str, ch: int, vs: int, text: str) -> List[TokenTag]:
        tokens = tokenize_verse(text, LANG)
        words = self.nt.verses.get((slug, ch, vs), [])
        tags: List[Optional[TokenTag]] = [None] * len(tokens)
        used: Set[int] = set()
        if words:
            pairs = _align_exact(tokens, words)
            for i, j, w_key, exact in pairs:
                used.add(j)
                w = words[j]
                bk = _matched_form(tokens[i], w)          # the form _align_exact paired on
                tags[i] = TokenTag(index=i + 1, surface=tokens[i], lemma_key=w_key, method="gold-aligned",
                                   confidence=0.99 if exact else 0.97, is_content=self.is_content(w_key),
                                   notes=[f"TAGNT {w.ref}"],
                                   morph=w.morph_of(bk) if bk else None, src=f"tagnt:{w.ref}")
        # 1. the same verse in another word order (the DP keeps one order only)
        # 2. the same words filed under another edition's verse number (Rom 16:25-27 = 14:24-26)
        # 3. the neighbouring verses (words that cross a verse boundary between editions)
        steps = (
            ("", [w for j, w in enumerate(words) if j not in used], 0.95),
            (" (alternative verse number)", self.nt.alt_verses.get((slug, ch, vs), []), 0.95),
            (" (neighbouring verse)", self.nt.verses.get((slug, ch, vs - 1), []) + self.nt.verses.get((slug, ch, vs + 1), []), 0.9),
        )
        for label, pool, conf in steps:
            if not pool or all(t is not None for t in tags):
                continue
            for i, tok in enumerate(tokens):
                if tags[i] is not None:
                    continue
                keys: Set[str] = set()
                refs: List[str] = []
                parses: Set[Optional[str]] = set()
                for w in pool:
                    for bk in _form_keys(tok):
                        if bk in w.alts:
                            keys.add(w.alts[bk])
                            refs.append(w.ref)
                            parses.add(w.morph_of(bk))
                            break
                if len(keys) == 1:
                    k = next(iter(keys))
                    # the parse only when every matching TAGNT word gives the same one
                    morph = next(iter(parses)) if len(parses) == 1 else None
                    tags[i] = TokenTag(index=i + 1, surface=tok, lemma_key=k, method="gold-aligned", confidence=conf,
                                       is_content=self.is_content(k), notes=[f"TAGNT {refs[0]}{label or ' (word order)'}"],
                                       morph=morph, src=f"tagnt:{refs[0]}")
        # 4. Two Studio tokens that split one multi-word TAGNT entry (1 Cor 16:22 Μαράνα θά -> μαράνα θά G3134)
        unused_words = [w for j, w in enumerate(words) if j not in used]
        if unused_words and any(t is None for t in tags):
            for i in range(len(tokens) - 1):
                if tags[i] is not None or tags[i + 1] is not None:
                    continue
                joined = greek_bare(tokens[i] + tokens[i + 1])
                for w in unused_words:
                    if " " in w.surface and w.key and greek_bare(w.surface) == joined:
                        for k_idx in (i, i + 1):
                            tags[k_idx] = TokenTag(
                                index=k_idx + 1, surface=tokens[k_idx], lemma_key=w.key,
                                method="gold-aligned", confidence=0.95, is_content=self.is_content(w.key),
                                notes=[f"TAGNT {w.ref} (split word)"], morph=None, src=f"tagnt:{w.ref}")
                        break
        # 4b. One Studio token that joins two consecutive unused TAGNT words (e.g. μήγε = μή G3361 + γε G1065)
        if len(words) >= 2 and any(t is None for t in tags):
            _ENCLITIC_PARTICLES = frozenset({"G1065", "G5037", "G4007", "G1211"})
            for i, tok in enumerate(tokens):
                if tags[i] is not None:
                    continue
                tb = greek_bare(tok)
                for j in range(len(words) - 1):
                    if j in used or (j + 1) in used:
                        continue
                    w1, w2 = words[j], words[j + 1]
                    if greek_bare(w1.surface + w2.surface) != tb:
                        continue
                    k = None
                    if w1.key and w2.key:
                        comb = self.lex.tbesg.combination.get(frozenset({w1.key, w2.key}))
                        k = self.lex.canonical(comb) if comb else (w1.key if w2.key in _ENCLITIC_PARTICLES else None)
                    if k:
                        morph = w1.morph_of(greek_bare(w1.surface))
                        tags[i] = TokenTag(
                            index=i + 1, surface=tok, lemma_key=k, method="gold-aligned", confidence=0.96,
                            is_content=self.is_content(k), notes=[f"TAGNT {w1.ref} (joined with {w2.ref})"],
                            morph=morph, src=f"tagnt:{w1.ref}")
                        used.add(j)
                        used.add(j + 1)
                        break
        # 5. Same-verse spelling / Koine acc.-ν / proper-name variant against an unused TAGNT word
        if unused_words and any(t is None for t in tags):
            for i, tok in enumerate(tokens):
                if tags[i] is not None:
                    continue
                tb = greek_bare(tok)
                tbi = tb.replace("ει", "ι")
                for w in unused_words:
                    akeys = set(w.alts.values())
                    if len(akeys) != 1:
                        continue
                    k = next(iter(akeys))
                    matched_alt: Optional[str] = None
                    for ab in w.alts:
                        if ab.replace("ει", "ι") == tbi or ab == tb + "ν" or tb == ab + "ν":
                            matched_alt = ab
                            break
                        if tok[:1].isupper() and self.is_propn(k) and (
                                stem_similarity(tb, ab) >= 0.78
                                or (abs(len(tb) - len(ab)) <= 1 and len(tb) >= 5
                                    and (tb[0] == ab[0] and tb[-2:] == ab[-2:]))):
                            matched_alt = ab
                            break
                    if matched_alt is not None:
                        tags[i] = TokenTag(
                            index=i + 1, surface=tok, lemma_key=k, method="gold-aligned", confidence=0.95,
                            is_content=self.is_content(k), notes=[f"TAGNT {w.ref} (spelling variant)"],
                            morph=w.morph_of(matched_alt), src=f"tagnt:{w.ref}")
                        break
        for i, tok in enumerate(tokens):
            if tags[i] is not None:
                continue
            hit = self.nt.lookup(tok, self.DICT_SHARE, self.DICT_MIN)
            if not hit and len(greek_bare(tok)) >= 5 and accent_key(tok) in self.nt.forms.acc:
                hit = self.nt.lookup(tok, 1.0, 1)
            if hit:
                k, share = hit
                tags[i] = TokenTag(index=i + 1, surface=tok, lemma_key=k, method="gold-form",
                                   confidence=round(0.9 * share, 3), is_content=self.is_content(k),
                                   notes=["TAGNT NT-wide form table"])
            else:
                tags[i] = TokenTag(index=i + 1, surface=tok, lemma_key=None, method="untagged", confidence=0.0)
        return tags  # type: ignore[return-value]

    # -- Septuagint ---------------------------------------------------------------------------
    def _slot_score(self, token: str, tbare: str, gkey: str, lkey: str, known: Set[str],
                    excl: Set[str] = frozenset()) -> Tuple[float, str]:
        if excl and (lkey in excl or "*" in excl):
            return 0.0, "stem"
        lb = _lemma_bare(gkey)
        if lkey in known:
            if tbare == lb and self.is_closed_class(lkey) and not self.head_accents_agree(token, gkey):
                return 0.0, "stem"        # ἦ μήν is not ἤ 'or'
            return 1.0, "known"           # (TAGNT or LXX first pass: told apart when tagging)
        if lkey in _CLOSED_LXX_FORMS and tbare in _CLOSED_LXX_FORMS[lkey]:
            return 0.95, "stem"
        if lkey == "G1438" and _is_contracted_reflexive(token):
            return 0.95, "stem"
        if lkey == "G0846" and (_is_crasis_autos(token) or _is_smooth_autai(token)):
            return 0.95, "stem"
        if tbare in _EPIDON_BARE:
            return (0.95, "stem") if lkey == "G1896" else (0.0, "stem")
        num_k = _milesian_numeral_key(token)
        if num_k is not None:
            return (1.0, "stem") if num_k == lkey else (0.0, "stem")
        closed = self.is_closed_class(lkey)
        if closed or len(lb) <= 3:
            # function words, prepositions and three-letter lemmas are paired only by an attested
            # form or by the same letters (for function words with agreeing breathing and accent):
            # their short stems would also match compounds (ἀπέθανεν / ἀπό, ἐπωνόμασεν / ἔπω).  A
            # capitalised name in its dictionary form is that name even where the form is attested
            # for another word (Ὤν the city, not ὤν; Εἰοὺ = Ιου).
            if (tbare == lb and (not known or (token[:1].isupper() and self.is_propn(lkey)))
                    and (not closed or self.head_accents_agree(token, gkey))):
                return 1.0, "stem"
            if (not closed and token[:1].isupper() and self.is_propn(lkey)
                    and _propn_norm(tbare) == _propn_norm(lb)):
                return 0.95, "stem"
            if not closed and lb in _IRREG_LXX_STEMS and not known:
                # 3-letter content verbs/nouns with explicit principal-part stems (ζάω, ᾠδή, θύω,
                # ᾄδω, ἄγω, ῥίς, ἀρά, ἐάω, χέω, εἵν): match only exact stems with short inflection
                # and no preverb prefix (so ἐπωνόμασεν still never matches ἔπω).
                for st in _IRREG_LXX_STEMS[lb]:
                    for tv in _strip_augment(tbare, lb):
                        if tv.startswith(st) and len(tv) - len(st) <= (6 if _is_verb_lemma(lb) else 4):
                            return 0.85, "stem"
            return 0.0, "stem"
        if token[:1].isupper() and self.is_propn(lkey):
            if tbare == lb or _propn_norm(tbare) == _propn_norm(lb):
                return 1.0, "stem"        # Ἰεροσόλυμα / Ἱεροσόλυμα, Ἀφεσή / Ἀφεσσή, Ναβδαιήλ / Ναβδεήλ
            psim = _propn_similarity(tbare, lb)
            if psim >= 0.80:
                return min(0.95, psim), "stem"
        if tbare == lb:
            # the very headword (a name in its dictionary form), unless the form is attested for
            # another lemma and the accents say it is that other word (ὄρος is not ὅρος)
            head = self.lex.gwl.get(gkey, {}).get("lemma", "")
            hk = accent_key(head)
            if not known or hk == greek_bare(head) or hk == accent_key(token):
                return 1.0, "stem"
        s = stem_similarity(tbare, gkey)
        if known:
            # Do not penalise when the attested lemma is linked to the verse's gold lemma
            # (φαγω/ἐσθίω, μιμνῄσκομαι/μνάομαι, ὁράω/εἴδω), or when a capitalised name faces
            # only lower-case common-word attestations (Λείας 'Leah' vs λεῖος 'smooth').
            if not any(self.linked(k, lkey) for k in known) and not (
                    token[:1].isupper() and self.is_propn(lkey) and all(not self.is_propn(k) for k in known)):
                s *= 0.5          # the form is attested for another lemma
        return s, "stem"

    def _align_lxx(self, tokens: List[str], slots: List[Tuple[str, str, Tuple[int, int], float]],
                   excl: Optional[List[Set[str]]] = None) -> Tuple[Dict[int, Tuple[int, float, str]], float]:
        """Order-preserving alignment of tokens to gold lemma slots.  Returns token index ->
        (slot index, score, kind) and the summed score.  ``excl[i]`` holds lemma keys token i may
        not take ('*': none at all)."""
        n, m = len(tokens), len(slots)
        if n == 0 or m == 0:
            return {}, 0.0
        tb = [greek_bare(t) for t in tokens]
        if excl is None:
            excl = _context_exclusions(tokens)
        known = [self.known_keys(t) - excl[i] if excl[i] else self.known_keys(t) for i, t in enumerate(tokens)]
        W: List[List[float]] = [[0.0] * m for _ in range(n)]
        K: List[List[str]] = [[""] * m for _ in range(n)]
        for i in range(n):
            memo: Dict[str, Tuple[float, str]] = {}
            for j in range(m):
                gk, lk, _, wt = slots[j]
                got = memo.get(gk)
                if got is None:
                    got = memo[gk] = self._slot_score(tokens[i], tb[i], gk, lk, known[i], excl[i])
                s, kind = got
                attested = kind == "known"
                if attested or s >= self.STEM_ACCEPT:
                    # neighbouring verses weigh less, and a stem pairing there less again
                    W[i][j] = s * (wt if (wt >= 1.0 or attested) else wt - 0.05)
                    K[i][j] = kind
        # DP (maximise total weight; matched pairs strictly increasing in both sequences)
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
        out: Dict[int, Tuple[int, float, str]] = {}
        i, j = n, m
        while i > 0 and j > 0:
            w = W[i - 1][j - 1]
            if w > 0.0 and abs(D[i][j] - (D[i - 1][j - 1] + w)) < 1e-9:
                out[i - 1] = (j - 1, w, K[i - 1][j - 1])
                i -= 1
                j -= 1
            elif D[i - 1][j] >= D[i][j - 1]:
                i -= 1
            else:
                j -= 1
        return out, D[n][m]

    def _slots_for(self, book: _LxxBook, keys: Sequence[Tuple[int, int]], centre: Tuple[int, int]
                   ) -> List[Tuple[str, str, Tuple[int, int], float]]:
        slots = []
        for k in keys:
            wt = 1.0 if k == centre else 0.9
            for g in book.groups.get(k, []):
                slots.append((g, self.lex.gwl_lemma_key(g), k, wt))
        return slots

    def _locate(self, book: _LxxBook, tokens: List[str]) -> Optional[Tuple[int, int]]:
        """Find the verse group whose lemma list best covers the tokens' attested lemmas."""
        idx = self._book_index(book)
        votes: Counter = Counter()
        for t in tokens:
            ks = self.known_keys(t)
            if not ks or len(ks) > 3:
                continue
            for k in ks:
                post = idx.get(k)
                if not post or len(post) > 150:
                    continue
                w = 1.0 / len(post)
                for g in post:
                    votes[g] += w
        if not votes:
            return None
        return votes.most_common(1)[0][0]

    def _book_index(self, book: _LxxBook) -> Dict[str, List[Tuple[int, int]]]:
        cache = getattr(book, "_lemma_index", None)
        if cache is None:
            cache = defaultdict(list)
            for g, gkeys in book.groups.items():
                for k in set(self.lex.gwl_lemma_key(x) for x in gkeys):
                    cache[k].append(g)
            book._lemma_index = cache  # type: ignore[attr-defined]
        return cache

    def _lxx_candidates(self, slug: str, ch: int, vs: int, tokens: List[str]):
        """Yield (book, centre, window keys) to try, best guesses first."""
        for name, off in _LXX_FILES.get(slug, []):
            book = self.lxx.get(name)
            if not book:
                continue
            centre = (ch + off, vs)
            yield book, centre
        for name, off in _LXX_FILES.get(slug, [])[:1]:
            book = self.lxx.get(name)
            if book:
                loc = self._locate(book, tokens)
                if loc:
                    yield book, loc

    def tag_lxx_verse(self, slug: str, ch: int, vs: int, text: str, use_dict: bool = True) -> List[TokenTag]:
        tokens = tokenize_verse(text, LANG)
        tags: List[Optional[TokenTag]] = [None] * len(tokens)
        if not tokens:
            return []
        # context rules: an accented ὅ/ἥ/οἵ/αἵ is the relative, not the article (unless an
        # enclitic follows: οἵ τε); the Hebrew letter Swete prints before each acrostic stanza
        # (Lam 1:5 Ἥ, Μήμ, Νούν) is no Greek word at all ('*': never paired, left untagged)
        excl = _context_exclusions(tokens)
        letter = _acrostic_letter(slug, ch, text, tokens)
        if letter is not None:
            excl[letter] = {"*"}
        best = None
        tried = set()
        for book, centre in self._lxx_candidates(slug, ch, vs, tokens):
            if (book.name, centre) in tried:
                continue
            tried.add((book.name, centre))
            if centre not in book.index:
                continue
            pos = book.index[centre]
            window = [book.order[p] for p in (pos - 1, pos, pos + 1) if 0 <= p < len(book.order)]
            slots = self._slots_for(book, window, centre)
            pairs, total = self._align_lxx(tokens, slots, excl)
            frac = len(pairs) / len(tokens)
            if best is None or total > best[2] + 1e-9:
                best = (book, slots, total, pairs, centre)
            if frac >= 0.8:
                break
        window_keys: Set[str] = set()
        open_slots: List[Tuple[int, Tuple[str, str, Tuple[int, int], float]]] = []
        anchors: List[Tuple[int, int]] = []
        if best is not None:
            book, slots, total, pairs, centre = best
            for i, (j, w, kind) in pairs.items():
                g, lk, gref, _ = slots[j]
                # a form only the LXX first pass attests keeps the confidence of the pairing it
                # came from (at most 0.93)
                if kind == "known" and lk not in self.nt_known(tokens[i]):
                    kind = "lxx-known"
                if kind == "known":
                    conf = 0.98
                elif kind == "lxx-known":
                    conf = self.lxx_form_confidence(tokens[i], lk)
                else:
                    conf = 0.93 if w >= 0.9 else 0.88
                tags[i] = TokenTag(index=i + 1, surface=tokens[i], lemma_key=lk, method="gold-aligned",
                                   confidence=conf, is_content=self.is_content(lk),
                                   notes=[f"LXX {book.name} {gref[0]}:{gref[1]} {g}" + (
                                       "" if kind == "known" else " (LXX form)" if kind == "lxx-known" else " (stem)")])
            filled = self._gap_fill(tokens, tags, slots, pairs, book, excl)
            window_keys = {s[1] for s in slots}
            used = {j for j, _, _ in pairs.values()} | set(filled.values())
            open_slots = [(j, s) for j, s in enumerate(slots) if j not in used and s[2] == centre]
            anchors = sorted([(i, j) for i, (j, _, _) in pairs.items()] + list(filled.items()))
        if use_dict:
            unpaired = [i for i in range(len(tokens)) if tags[i] is None]
            for i, tok in enumerate(tokens):
                if tags[i] is not None or "*" in excl[i]:
                    continue
                num_k = _milesian_numeral_key(tok)
                if num_k is not None:
                    self.lex.ensure_entry(num_k, source=SRC_TAGNT)
                    tags[i] = TokenTag(index=i + 1, surface=tok, lemma_key=num_k, method="gold-form",
                                       confidence=0.95, is_content=self.is_content(num_k),
                                       notes=["Greek alphabetic numeral"])
                    continue
                if _is_contracted_reflexive(tok):
                    tags[i] = TokenTag(index=i + 1, surface=tok, lemma_key="G1438", method="gold-form",
                                       confidence=0.95, is_content=self.is_content("G1438"),
                                       notes=["contracted reflexive (ἑαυτοῦ)"])
                    continue
                if _is_crasis_autos(tok) or _is_smooth_autai(tok):
                    tags[i] = TokenTag(index=i + 1, surface=tok, lemma_key="G0846", method="gold-form",
                                       confidence=0.95, is_content=self.is_content("G0846"),
                                       notes=["crasis / smooth-breathing form (αὐτός)"])
                    continue
                tb_i = greek_bare(tok)
                if tb_i in _EPIDON_BARE and "G1896" not in excl[i]:
                    self.lex.ensure_entry("G1896", source=SRC_TAGNT)
                    tags[i] = TokenTag(index=i + 1, surface=tok, lemma_key="G1896", method="gold-form",
                                       confidence=0.95, is_content=self.is_content("G1896"),
                                       notes=["Koine aspirated aorist (ἐπεῖδον)"])
                    continue
                if accent_key(tok) == "μήν" and i > 0 and greek_bare(tokens[i - 1]) in ("ει", "ουδε", "μηδε", "η"):
                    self.lex.ensure_entry("G3375", source=SRC_TAGNT)
                    tags[i] = TokenTag(index=i + 1, surface=tok, lemma_key="G3375", method="gold-form",
                                       confidence=0.95, is_content=self.is_content("G3375"),
                                       notes=["asseverative particle (μήν)"])
                    continue
                if accent_key(tok) == "οὗ" and i > 0 and greek_bare(tokens[i - 1]) in ("εξ", "εκ", "απο", "προ"):
                    self.lex.ensure_entry("G3739", source=SRC_TAGNT)
                    tags[i] = TokenTag(index=i + 1, surface=tok, lemma_key="G3739", method="gold-form",
                                       confidence=0.95, is_content=self.is_content("G3739"),
                                       notes=["prepositional relative (ἐξ οὗ / ἀφ' οὗ)"])
                    continue
                hit = None
                src = ""
                # a proper name comes from the LXX's own pairings and only for a capitalised token
                # (the TAGNT table is not used for names in the OT: its Βόες is Boaz, its Ἀσάφ
                # is King Asa; and lower-case βόες are oxen)
                ex_i = excl[i]
                if self._lxx_dict_ready:
                    if tok[:1].isupper():
                        excl_fn = (lambda k, e=ex_i: k in e) if ex_i else None
                    else:
                        excl_fn = (lambda k, e=ex_i: k in e or self.is_propn(k))
                    hit = self.lxx_table.lookup(tok, self.DICT_SHARE, self.DICT_MIN, exclude=excl_fn)
                    src = "LXX-wide form table"
                if not hit:
                    hit = self.nt.lookup(tok, self.DICT_SHARE, self.DICT_MIN,
                                         exclude=lambda k, e=ex_i: k in e or self.is_propn(k))
                    src = "TAGNT NT-wide form table"
                if not hit and len(tb_i) >= 5:
                    ak = accent_key(tok)
                    if self._lxx_dict_ready and ak in self.lxx_table.acc:
                        hit = self.lxx_table.lookup(tok, 1.0, 1, exclude=excl_fn)
                        src = "LXX-wide form table"
                    if not hit and ak in self.nt.forms.acc:
                        hit = self.nt.lookup(tok, 1.0, 1, exclude=lambda k, e=ex_i: k in e or self.is_propn(k))
                        src = "TAGNT NT-wide form table"
                if not hit and len(tb_i) >= 4:
                    if tok[:1].islower():
                        hk = self._exact_headword_lookup(tok, ex_i)
                        if hk is not None:
                            hit = (hk, 1.0)
                            src = "Greek lexicon headword"
                    elif i == 0 and not self._has_propn_bare(tb_i):
                        hk = self._exact_headword_lookup(tok.lower(), ex_i)
                        if hk is not None:
                            hit = (hk, 1.0)
                            src = "Greek lexicon headword"
                if not hit and tok[:1].isupper() and len(tb_i) >= 3:
                    pk = self._exact_propn_headword_lookup(tok, ex_i)
                    if pk is not None:
                        hit = (pk, 0.96)
                        src = "Greek proper-name lexicon headword"
                if not hit and len(tb_i) >= 6 and (tok[:1].islower() or not self._has_propn_bare(tb_i)):
                    ck = self._resolve_compound_by_preverb(tok, ex_i, verbs_only=tok[:1].isupper())
                    if ck is not None:
                        hit = (ck, 0.95)
                        src = "Greek compound preverb + attested simplex"
                if hit and best is not None and self._table_contradicted(
                        i, tok, hit[0], slots, open_slots, anchors, unpaired, window_keys,
                        from_nt=src.startswith("TAGNT")):
                    hit = None
                if hit:
                    k, share = hit
                    tags[i] = TokenTag(index=i + 1, surface=tok, lemma_key=k, method="gold-form",
                                       confidence=round(0.88 * share, 3), is_content=self.is_content(k),
                                       notes=[src])
        for i, tok in enumerate(tokens):
            if tags[i] is None:
                tags[i] = TokenTag(index=i + 1, surface=tok, lemma_key=None, method="untagged", confidence=0.0,
                                   notes=["acrostic letter name"] if i == letter else [])
        return tags  # type: ignore[return-value]

    def _table_contradicted(self, i: int, tok: str, hit: str, slots, open_slots, anchors, unpaired,
                            window_keys: Set[str], from_nt: bool = False) -> bool:
        """The form tables must not contradict the verse's own gold list.  An unpaired lemma of
        the verse that this word could be, and that is not the table's lemma under another
        convention (εἶδον: TAGNT εἴδω, the LXX files ὁράω), leaves the word untagged:
          * any unpaired lemma of the verse whose stem the word continues (similarity >= 0.6,
            the original rule: ὄψει in Gen 24:16 is ὄψις 'appearance', not ὁράω);
          * an unpaired lemma between the word's paired neighbours of which the word is a
            plausible form: it shares a stem with a form attested for that lemma (at least three
            letters and 60%, only endings differing), or stem similarity >= 0.9, or, for an
            answer of the NT-wide table, >= 0.5.  These are homographs the tables cannot see:
            ἀνῆκεν ἀνίημι/ἀνήκω, ζῶσαι ζάω/ζώννυμι, γνώσει γινώσκω/γνῶσις, ἀσεβῶν ἀσεβέω/ἀσεβής.
            A different word of Rahlfs' text in that place (Swete ἐλέει, Rahlfs ἐλαίῳ) does not
            count: the table's answer stands.
        Calibrated on the Rahlfs yardstick of the 18 Nov verification (evaluation only)."""
        tb = greek_bare(tok)
        head = self.lex.headword(hit)
        if accent_key(head) == accent_key(tok) or (accent_key(head) == greek_bare(head) == tb):
            return False     # the token is the lemma's own dictionary form (ἔνθεν, where the
                             # LXX files print ἐνθάδε)
        if hit not in window_keys:
            for _, s in open_slots:
                if s[1] != hit and not self.is_closed_class(s[1]) and stem_similarity(tb, s[0]) >= 0.6:
                    return True
        left = [(a, b) for a, b in anchors if a < i]
        right = [(a, b) for a, b in anchors if a > i]
        i0, j0 = left[-1] if left else (-1, -1)
        i1, j1 = right[0] if right else (10 ** 6, len(slots))
        gap = [s for j, s in open_slots if j0 < j < j1]
        if not gap or hit in {s[1] for s in gap}:
            return False
        for s in gap:
            g, lk = s[0], s[1]
            if lk == hit or self.linked(hit, lk):
                continue
            if self.is_closed_class(lk):
                could = tb == _lemma_bare(g) and self.head_accents_agree(tok, g)
            else:
                sim = stem_similarity(tb, g)
                could = (sim >= 0.9 or (from_nt and sim >= 0.5)
                         or self.continues_attested_form(tok, lk, strict=True))
            if could:
                return True
        return False

    def _gap_fill(self, tokens, tags, slots, pairs, book, excl=None) -> Dict[int, int]:
        """A single unpaired token between two paired tokens, facing a single unpaired lemma
        between the same two lemmas, is that lemma's word when the form is attested for that
        lemma, or when it is not attested for another lemma (or the attested lemma does not appear
        in the verse at all and this word strongly matches the verse's gold lemma) and either its
        letters continue the lemma's stem (stem similarity >= GAP_FILL_STEM) or it shares a stem
        with a form attested for the lemma (continues_attested_form: ὀφθήτω / ὤφθη for ὁράω).
        ᾔνεσεν is not ἐγγίζω, δικάσωμεν not δοκιμάζω.  A capitalised token facing a proper name
        uses proper-name similarity too, because Codex B spells names its own way (Δαμνιήλ /
        Δανιήλ, Ἐρειφάθ / Ῥιφάθ).  A contiguous k-to-k gap of capitalised proper names facing k
        proper-name slots in order is also paired when every pair matches.  Returns token -> slot."""
        filled: Dict[int, int] = {}
        anchors = sorted((i, j) for i, (j, _, _) in pairs.items())
        window_keys = {s[1] for s in slots}
        for (i0, j0), (i1, j1) in zip(anchors, anchors[1:]):
            gap_len = i1 - i0 - 1
            if gap_len <= 0 or (j1 - j0 - 1) != gap_len:
                continue
            if gap_len > 1:
                # k-to-k gap of consecutive proper names in genealogies (e.g. 1 Chr 1:40)
                if gap_len > 6 or slots[j0][2] != slots[j1][2]:
                    continue
                ok_all = True
                for k in range(1, gap_len + 1):
                    i, j = i0 + k, j0 + k
                    if excl is not None and excl[i] and ("*" in excl[i] or slots[j][1] in excl[i]):
                        ok_all = False
                        break
                    g, lk, _gref, wt = slots[j]
                    tok = tokens[i]
                    if wt < 1.0 or not tok[:1].isupper() or not (self.is_propn(lk) or self.lex.headword(lk)[:1].isupper()):
                        ok_all = False
                        break
                    tb = greek_bare(tok)
                    if not (stem_similarity(tb, g) > self.GAP_FILL_MIN or _propn_similarity(tb, _lemma_bare(g)) >= 0.45):
                        ok_all = False
                        break
                if ok_all:
                    for k in range(1, gap_len + 1):
                        i, j = i0 + k, j0 + k
                        g, lk, gref, _wt = slots[j]
                        tags[i] = TokenTag(index=i + 1, surface=tokens[i], lemma_key=lk, method="gold-aligned",
                                           confidence=0.8, is_content=self.is_content(lk),
                                           notes=[f"LXX {book.name} {gref[0]}:{gref[1]} {g} (between aligned words)"])
                        filled[i] = j
                continue
            i, j = i0 + 1, j0 + 1
            if excl is not None and excl[i]:
                if "*" in excl[i] or slots[j][1] in excl[i]:
                    continue
            g, lk, gref, wt = slots[j]
            if wt < 1.0 or slots[j0][2] != slots[j1][2] or self.is_closed_class(lk):
                continue
            tok = tokens[i]
            tb = greek_bare(tok)
            if tb in _EPIDON_BARE and lk != "G1896":
                continue
            known = self.known_keys(tok)
            is_name = tok[:1].isupper() and (self.is_propn(lk) or self.lex.headword(lk)[:1].isupper())
            centre_keys = {s[1] for s in slots if s[2] == gref}
            if known and lk not in known:
                # Allow a 1-to-1 gap homograph (γνώσει -> γινώσκω, δοκῶν -> δοκός, ἀνῆκεν -> ἀνίημι,
                # ποία/ποίαν -> πόα) or a Codex B proper name when the attested lemma is NOT in this
                # verse's gold slots and the token strongly matches this verse's own gold lemma.
                if known & centre_keys:
                    continue
                s = stem_similarity(tb, g)
                if is_name:
                    ok = (s > self.GAP_FILL_MIN or _propn_similarity(tb, _lemma_bare(g)) >= 0.40
                          or _propn_cons_sim(tb, _lemma_bare(g)) >= 0.72)
                else:
                    ok = (s >= self.STEM_ACCEPT or self.continues_attested_form(tok, lk, strict=True)
                          or _gap_ortho_match(tb, _lemma_bare(g)))
                if not ok:
                    continue
            elif lk not in known:
                s = stem_similarity(tb, g)
                if is_name:
                    ok = (s > self.GAP_FILL_MIN or _propn_similarity(tb, _lemma_bare(g)) >= 0.40
                          or _propn_cons_sim(tb, _lemma_bare(g)) >= 0.72)
                else:
                    ok = (s >= self.GAP_FILL_STEM or self.continues_attested_form(tok, lk)
                          or _gap_ortho_match(tb, _lemma_bare(g)))
                if not ok:
                    continue
            tags[i] = TokenTag(index=i + 1, surface=tok, lemma_key=lk, method="gold-aligned", confidence=0.8,
                               is_content=self.is_content(lk),
                               notes=[f"LXX {book.name} {gref[0]}:{gref[1]} {g} (between aligned words)"])
            filled[i] = j
        # 2. Verse-boundary pairing (start / end of verse: proper names e.g. 1 Chr 3:13 Ἀχὰς,
        #    or unattested content words e.g. Job 34:12 οἴῃ -> οἴομαι)
        if anchors:
            centre = slots[anchors[0][1]][2]
            centre_js = [j for j, s in enumerate(slots) if s[2] == centre]
            centre_keys = {slots[j][1] for j in centre_js}
            if centre_js:
                c_lo, c_hi = centre_js[0], centre_js[-1]
                used_js = {j for j, _, _ in pairs.values()} | set(filled.values())
                # Start / end boundary helper
                for b_i, b_j in ((0, anchors[0][1] - 1) if anchors[0][0] == 1 else (-1, -1),
                                 (len(tokens) - 1, anchors[-1][1] + 1) if anchors[-1][0] == len(tokens) - 2 else (-1, -1)):
                    if b_i < 0 or not (c_lo <= b_j <= c_hi) or b_j in used_js or tags[b_i] is not None:
                        continue
                    g, lk, gref, wt = slots[b_j]
                    tok = tokens[b_i]
                    if wt < 1.0 or (excl is not None and excl[b_i] and ("*" in excl[b_i] or lk in excl[b_i])):
                        continue
                    tb = greek_bare(tok)
                    is_name = tok[:1].isupper() and (self.is_propn(lk) or self.lex.headword(lk)[:1].isupper())
                    if is_name:
                        ok = (stem_similarity(tb, g) > self.GAP_FILL_MIN
                              or _propn_similarity(tb, _lemma_bare(g)) >= 0.50
                              or _propn_cons_sim(tb, _lemma_bare(g)) >= 0.72)
                        label = "verse-boundary name"
                    elif not self.is_closed_class(lk) and not self.known_keys(tok):
                        ok = stem_similarity(tb, g) >= 0.70 or _gap_ortho_match(tb, _lemma_bare(g))
                        label = "verse-boundary word"
                    else:
                        ok = False
                        label = ""
                    if ok:
                        tags[b_i] = TokenTag(index=b_i + 1, surface=tok, lemma_key=lk, method="gold-aligned",
                                             confidence=0.8, is_content=self.is_content(lk),
                                             notes=[f"LXX {book.name} {gref[0]}:{gref[1]} {g} ({label})"])
                        filled[b_i] = b_j
                        used_js.add(b_j)
                # 3. Same-verse swapped-order & orthographic-variant content words
                #    (e.g. Hos 6:2 ἀναστησόμεθα, Isa 13:16 ῥάξουσιν, Lev 11:17 εἶβιν, 2 Macc 5:16 μιεραῖς)
                open_content = [(j, slots[j]) for j in centre_js
                                if j not in used_js and slots[j][3] >= 1.0
                                and not self.is_closed_class(slots[j][1])
                                and not self.is_propn(slots[j][1])]
                if open_content:
                    for i, tok in enumerate(tokens):
                        if tags[i] is not None:
                            continue
                        if excl is not None and excl[i] and "*" in excl[i]:
                            continue
                        tb = greek_bare(tok)
                        if len(tb) < 4:
                            continue
                        known = self.known_keys(tok)
                        scored = []
                        for j, s in open_content:
                            if j in used_js:
                                continue
                            if excl is not None and excl[i] and s[1] in excl[i]:
                                continue
                            if tb in _EPIDON_BARE and s[1] != "G1896":
                                continue
                            lb = _lemma_bare(s[0])
                            sim = stem_similarity(tb, s[0])
                            ortho = _gap_ortho_match(tb, lb) or (
                                len(tb) >= 8 and len(lb) >= 8
                                and difflib.SequenceMatcher(None, tb[1:], lb[1:], autojunk=False).ratio() >= 0.85
                            )
                            if known and s[1] not in known:
                                if known & centre_keys:
                                    continue
                                if not any(self.linked(k, s[1]) for k in known) and sim < 0.88 and not ortho:
                                    continue
                            if sim >= 0.85:
                                scored.append((sim, j, s))
                            elif ortho:
                                scored.append((0.83, j, s))
                        if scored:
                            scored.sort(key=lambda x: x[0], reverse=True)
                            if len(scored) == 1 or scored[0][0] >= scored[1][0] + 0.05 or scored[0][2][1] == scored[1][2][1]:
                                _sim, j, (g, lk, gref, _wt) = scored[0]
                                tags[i] = TokenTag(index=i + 1, surface=tok, lemma_key=lk, method="gold-aligned",
                                                   confidence=0.85 if _sim >= 0.85 else 0.8,
                                                   is_content=self.is_content(lk),
                                                   notes=[f"LXX {book.name} {gref[0]}:{gref[1]} {g} (same-verse word order)"])
                                filled[i] = j
                                used_js.add(j)
                # 4. Same-verse swapped-order, consonant-variant & compound proper names
                open_propn = [(j, slots[j]) for j in centre_js
                              if j not in used_js and slots[j][3] >= 1.0
                              and (self.is_propn(slots[j][1]) or self.lex.headword(slots[j][1])[:1].isupper())]
                if open_propn:
                    for i, tok in enumerate(tokens):
                        if tags[i] is not None or not tok[:1].isupper():
                            continue
                        if excl is not None and excl[i] and "*" in excl[i]:
                            continue
                        tb = greek_bare(tok)
                        scored = []
                        for j, s in open_propn:
                            if j in used_js:
                                continue
                            if excl is not None and excl[i] and s[1] in excl[i]:
                                continue
                            lb = _lemma_bare(s[0])
                            ps = _propn_similarity(tb, lb)
                            cs = _propn_cons_sim(tb, lb) if len(tb) >= 4 and len(lb) >= 4 else 0.0
                            score = max(ps, cs - 0.04)
                            if ps >= 0.65 or cs >= 0.70:
                                scored.append((score, ps, cs, j, s))
                        if scored:
                            scored.sort(key=lambda x: x[0], reverse=True)
                            top_sc, top_ps, top_cs, j, (g, lk, gref, _wt) = scored[0]
                            strong = top_ps >= 0.72 or top_cs >= 0.76
                            unique_clear = (len(scored) == 1 or top_sc >= scored[1][0] + 0.12
                                            or scored[0][4][1] == scored[1][4][1])
                            if (strong and (len(scored) == 1 or top_sc >= scored[1][0] + 0.05
                                            or scored[0][4][1] == scored[1][4][1])) or unique_clear:
                                tags[i] = TokenTag(index=i + 1, surface=tok, lemma_key=lk, method="gold-aligned",
                                                   confidence=0.8, is_content=self.is_content(lk),
                                                   notes=[f"LXX {book.name} {gref[0]}:{gref[1]} {g} (same-verse name)"])
                                filled[i] = j
                                used_js.add(j)
                    # Compound split / merged proper names in the same centre verse
                    # (e.g. Φαρσὰν + Νεσταὶν -> φαρσαννεσταιν, Λαβὼ + Ἑμάθ -> λαβωεμαθ,
                    # Φασράθ + Ἁσεβωείν -> φαχεραθ-ασεβωιν, 2 Chr 20:2 Θαμαρά -> ασασανθαμαρ).
                    # Keep long/hyphenated compound slots available even if one half paired above.
                    comp_propn = [(j, s) for j, s in open_propn
                                  if (j not in used_js) or ("-" in s[0])
                                  or len(_propn_norm(_lemma_bare(s[0]))) >= 7]
                    for i, tok in enumerate(tokens):
                        if tags[i] is not None:
                            continue
                        if excl is not None and excl[i] and "*" in excl[i]:
                            continue
                        tb = greek_bare(tok)
                        is_cap = tok[:1].isupper()
                        if len(tb) < (2 if is_cap else 4):
                            continue
                        pn_t = _propn_norm(tb)
                        hit_slot = None
                        for j, s in comp_propn:
                            if excl is not None and excl[i] and s[1] in excl[i]:
                                continue
                            g, lk, gref, _wt = s
                            lb = _lemma_bare(g)
                            pn_l = _propn_norm(lb)
                            has_hyphen = "-" in g
                            if not is_cap and not (has_hyphen or len(pn_l) >= 8):
                                continue
                            parts = [greek_bare(p) for p in g.split(".")[0].split("-") if p]
                            # 1) token matches a hyphen-separated part or is a substring of a long compound slot
                            if len(pn_l) >= 7 or has_hyphen:
                                pn_t_stem = pn_t[:-1] if len(pn_t) >= 5 and pn_t.endswith("α") else ""
                                if ((len(pn_t) >= 3 and pn_t in pn_l)
                                        or (pn_t_stem and pn_t_stem in pn_l)
                                        or any(
                                            (len(p) >= 2 and _propn_norm(p) == pn_t)
                                            or (len(p) >= 4 and len(tb) >= 4
                                                and (_propn_similarity(tb, p) >= 0.72 or _propn_cons_sim(tb, p) >= 0.78))
                                            for p in parts)):
                                    hit_slot = (j, s)
                                    break
                                # 2) prefix/suffix of compound slot with consonant-class match (e.g. Ἁσὰμ / Θαμαρά in ασασανθαμαρ)
                                if is_cap and len(pn_t) >= 4 and len(pn_l) >= len(pn_t) + 3:
                                    wlen = len(pn_t)
                                    if (_propn_cons_sim(tb, lb[:wlen + 1]) >= 0.78
                                            or _propn_cons_sim(tb, lb[-(wlen + 1):]) >= 0.78):
                                        hit_slot = (j, s)
                                        break
                            # 3) Swete merged compound token containing an unused Rahlfs name (Ἀναμεσιρδάθαι -> σιρδαθα)
                            if is_cap and len(pn_t) >= 9 and len(pn_l) >= 4:
                                if pn_l in pn_t or _propn_cons_sim(tb[-len(lb):], lb) >= 0.78:
                                    hit_slot = (j, s)
                                    break
                        if hit_slot is not None:
                            j, (g, lk, gref, _wt) = hit_slot
                            tags[i] = TokenTag(index=i + 1, surface=tok, lemma_key=lk, method="gold-aligned",
                                               confidence=0.8, is_content=self.is_content(lk),
                                               notes=[f"LXX {book.name} {gref[0]}:{gref[1]} {g} (compound name)"])
                            filled[i] = j
        return filled

    def _has_propn_bare(self, bare: str) -> bool:
        """True if TBESG or GWL holds any proper-name entry with these bare letters."""
        for e in self.lex.tbesg.by_bare.get(bare, ()):
            ce = self.lex.canonical(e) or e
            if self.is_propn(ce) or self.lex._tbesg_head_case(ce):
                return True
        for gk in (bare, bare[:-1] + "ς" if bare.endswith("σ") else bare):
            ent = self.lex.gwl.get(gk)
            if ent and (ent.get("lemma", "")[:1].isupper() or _gwl_pos(ent) == "PROPN"):
                return True
        return False

    def _exact_propn_headword_lookup(self, tok: str, excl: Set[str]) -> Optional[str]:
        """Match a capitalised proper-name token (len >= 3) against a unique PROPN headword in
        TBESG or GWL under _propn_norm (e.g. Ἰεθέτ, Ἐλιὰκ, Σουφεὶ, Ὀζείου, Ἡλειά), only when
        no lowercase common word shares the token's bare letters."""
        bare = greek_bare(tok)
        if len(bare) < 3:
            return None
        # Refuse if any common word has the same bare letters (protects Γάζης, Βόες, Ὤν, etc.)
        for e in self.lex.tbesg.by_bare.get(bare, ()):
            ce = self.lex.canonical(e) or e
            if not self.is_propn(ce) and not self.lex._tbesg_head_case(ce):
                return None
        for gk in (bare, bare[:-1] + "ς" if bare.endswith("σ") else bare):
            ent = self.lex.gwl.get(gk)
            if ent and _gwl_pos(ent) != "PROPN" and not ent.get("lemma", "")[:1].isupper():
                return None
        idx = getattr(self, "_propn_pn_index", None)
        if idx is None:
            idx = defaultdict(list)
            seen_k: Dict[str, Set[str]] = defaultdict(set)
            for gk, ent in self.lex.gwl.items():
                if _gwl_pos(ent) == "PROPN":
                    lk = self.lex.gwl_lemma_key(gk)
                    pn = _propn_norm(_lemma_bare(gk))
                    if pn and lk not in seen_k[pn]:
                        seen_k[pn].add(lk)
                        idx[pn].append((lk, gk, ent))
            for e in self.lex.tbesg.by_estrong:
                ce = self.lex.canonical(e) or e
                if self.is_propn(ce):
                    pn = _propn_norm(greek_bare(self.lex.headword(ce)))
                    if pn and ce not in seen_k[pn]:
                        seen_k[pn].add(ce)
                        idx[pn].append((ce, None, None))
            self._propn_pn_index = dict(idx)
        hits = [(lk, gk, ent) for lk, gk, ent in idx.get(_propn_norm(bare), ()) if lk not in excl]
        if len(hits) != 1:
            return None
        lk, gk, ent = hits[0]
        if lk not in self.lex._entry_info:
            if gk and ent:
                self.lex.ensure_entry(lk, head=ent.get("lemma", ""), pos="PROPN",
                                      source=SRC_OSSP, gwl_key=gk)
            else:
                self.lex.ensure_entry(lk, pos="PROPN", source=SRC_TAGNT)
        return lk

    def _resolve_compound_by_preverb(self, tok: str, excl: Set[str], verbs_only: bool = False) -> Optional[str]:
        """Resolve an unaligned Greek compound form (e.g. συνέθλιβεν, ἐνκαλύπτει, προσδεχθήσεται,
        παρεβιάζετο, ὑποστρέψουσιν, συνπολεμήσω) by peeling a standard preverb, verifying the
        remainder against attested simplex forms in TAGNT / lxx_table, and confirming that the
        recomposed Greek headword exists in TBESG, GWL, TFLSJ-extra, or Perseus LSJ."""
        bare = greek_bare(tok)
        if len(bare) < 6:
            return None
        # 0. Koine double-augment before a compound already attested in TAGNT / lxx_table (ἐπροσηύξατο)
        if bare.startswith("ε") and len(bare) >= 7:
            sub_b = bare[1:]
            sub_c: Counter = Counter()
            for tbl in (self.nt.forms, self.lxx_table):
                for ak in tbl.by_bare.get(sub_b, ()):
                    for k, n in tbl.acc[ak].items():
                        if k not in excl and not self.is_propn(k) and self.lex.pos(k) == "V":
                            sub_c[k] += n
            if sub_c:
                top_k, n = sub_c.most_common(1)[0]
                if n / sum(sub_c.values()) >= 0.95:
                    return top_k

        # Helper to look up a bare simplex form in TAGNT + lxx_table
        def _lookup_simplex(sb: str, need_verb: bool) -> Optional[Tuple[str, str]]:
            c: Counter = Counter()
            for tbl in (self.nt.forms, self.lxx_table):
                for ak in tbl.by_bare.get(sb, ()):
                    for k, n in tbl.acc[ak].items():
                        if self.is_propn(k) or self.is_closed_class(k):
                            continue
                        p = self.lex.pos(k)
                        if need_verb and p != "V":
                            continue
                        c[k] += n
            if not c:
                return None
            top_k, n = c.most_common(1)[0]
            if n / sum(c.values()) < 0.95:
                return None
            return top_k, (self.lex.pos(top_k) or "V")

        # Try peeling each preverb family (longest spelling first)
        pv_fams = (
            ("αντι", ("αντι", "αντ", "ανθ")),
            ("απο", ("απο", "απ", "αφ")),
            ("ανα", ("ανα", "αν")),
            ("δια", ("δια", "δι")),
            ("εισ", ("εισ",)),
            ("εκ", ("εξ", "εκ")),
            ("εν", ("εν", "εμ", "εγ", "ελ")),
            ("επι", ("επι", "επ", "εφ")),
            ("κατα", ("κατα", "κατ", "καθ")),
            ("μετα", ("μετα", "μετ", "μεθ")),
            ("παρα", ("παρα", "παρ")),
            ("περι", ("περι",)),
            ("προσ", ("προσ",)),
            ("προ", ("προ",)),
            ("συν", ("συν", "συμ", "συγ", "συλ", "συσ", "συ")),
            ("υπερ", ("υπερ",)),
            ("υπο", ("υπο", "υπ", "υφ")),
            ("ευ", ("ευ",)),
        )
        # Canonical spelling variants of each preverb when forming a Greek dictionary headword
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
        matches: Set[str] = set()
        for canon_pv, forms in pv_fams:
            for fv in forms:
                if not bare.startswith(fv) or len(bare) < len(fv) + 4:
                    continue
                rem = bare[len(fv):]
                # Build candidate simplex forms (direct, augmented, or de-augmented)
                rem_tries: List[Tuple[str, bool]] = [(rem, verbs_only)]
                if rem.startswith("ε") and len(rem) >= 5:
                    rem_tries.append((rem[1:], True))
                elif rem[:2] == "ηυ" and len(rem) >= 6:
                    rem_tries.append(("ευ" + rem[2:], True))
                    rem_tries.append(("αυ" + rem[2:], True))
                elif rem.startswith("η") and len(rem) >= 5:
                    for v in ("α", "ε", "αι", "ει"):
                        rem_tries.append((v + rem[1:], True))
                elif rem.startswith("ω") and len(rem) >= 5:
                    for v in ("ο", "οι"):
                        rem_tries.append((v + rem[1:], True))
                # Also try adding ε- augment if rem looks unaugmented (e.g. προσ-δεχθησεται)
                if rem[0] not in "αεηιουω":
                    rem_tries.append(("ε" + rem, True))
                sim_hit = None
                for sb, need_v in rem_tries:
                    sim_hit = _lookup_simplex(sb, need_v)
                    if sim_hit is not None:
                        break
                if sim_hit is None:
                    continue
                sim_k, sim_pos = sim_hit
                if verbs_only and sim_pos != "V":
                    continue
                sim_head = greek_bare(self.lex.headword(sim_k))
                if not sim_head or len(sim_head) < 3:
                    continue
                # Recompose canonical Greek compound headword and check open dictionaries
                sim_heads = [sim_head]
                if sim_head.endswith("ομαι"):
                    sim_heads.append(sim_head[:-4] + "ω")
                elif sim_head.endswith("ω"):
                    sim_heads.append(sim_head[:-1] + "ομαι")
                for hpv in head_pvs[canon_pv]:
                    for sh in sim_heads:
                        cand_heads = [hpv + sh]
                        if sh.startswith("ρ") and hpv[-1] in "αεηιουω":
                            cand_heads.append(hpv + "ρ" + sh)
                        for ch_b in cand_heads:
                            rk = self.lex.resolve_external_lemma(
                                ch_b, pos_hint=sim_pos, allow_propn=False, allow_lsj=True)
                            if rk and rk not in excl:
                                matches.add(rk)
                break  # longest spelling matched in this family
        return next(iter(matches)) if len(matches) == 1 else None

    def _exact_headword_lookup(self, tok: str, excl: Set[str]) -> Optional[str]:
        """Match a lowercase token of length >= 4 that is literally the accented dictionary
        headword (allowing enclitic throw-back) of a single non-PROPN lemma in TBESG or GWL."""
        ak = accent_key(tok)
        bk, tpos = _accent_sig(ak)
        bare = greek_bare(tok)
        if not bare:
            return None
        cands: Set[str] = set()
        # 1. TBESG entries with the same bare form and compatible accent/breathing
        for e in self.lex.tbesg.by_bare.get(bare, ()):
            ce = self.lex.canonical(e) or e
            if ce in excl or self.is_propn(ce) or self.lex._tbesg_head_case(ce):
                continue
            head = self.lex.headword(ce)
            hb, hpos = _accent_sig(accent_key(head))
            if hb == bk and _accents_compatible(tpos, hpos):
                cands.add(ce)
        # 2. GWL exact key with compatible accent/breathing (only if not ambiguous with TBESG)
        for gk in (bare, bare[:-1] + "ς" if bare.endswith("σ") else bare):
            ent = self.lex.gwl.get(gk)
            if not ent:
                continue
            head = ent.get("lemma", "")
            if not head or head[:1].isupper():
                continue
            lk = self.lex.gwl_lemma_key(gk)
            if lk in excl or self.is_propn(lk):
                continue
            hb, hpos = _accent_sig(accent_key(head))
            if (hb == bk or accent_key(head) == greek_bare(head)) and _accents_compatible(tpos, hpos):
                cands.add(lk)
        if len(cands) == 1:
            k = next(iter(cands))
            if k not in self.lex._entry_info:
                # Register via ensure_entry so it is always present in load_lexicon()
                gk_hit = next((g for g in (bare, bare[:-1] + "ς" if bare.endswith("σ") else bare)
                               if g in self.lex.gwl and self.lex.gwl_lemma_key(g) == k), None)
                if gk_hit:
                    ent = self.lex.gwl[gk_hit]
                    self.lex.ensure_entry(k, head=ent.get("lemma", ""), pos=_gwl_pos(ent),
                                          source=SRC_OSSP, gwl_key=gk_hit)
                else:
                    self.lex.ensure_entry(k, source=SRC_TAGNT)
            return k
        return None

    def build_lxx_form_table(self, verses: Iterable[Tuple[str, int, int, str]]) -> None:
        """LXX-wide form -> lemma table from the aligned pairings of the whole Greek OT (first
        pass; pairings by attested form or by stem, not the between-words pairings).  The table
        keeps the best first-pass confidence of each (form, lemma), and a second-pass pairing that
        rests on it ('LXX form') gets that confidence, never more than 0.93: a pairing first made
        by stem alone is not promoted to 'attested'."""
        # the first pass runs with an empty LXX table, whatever was built before (force=True)
        self._set_lxx_table(self._new_table(), False)
        table = self._new_table()
        for slug, ch, vs, text in verses:
            for t in self.tag_lxx_verse(slug, ch, vs, text, use_dict=False):
                if t.lemma_key and t.method == "gold-aligned" and t.confidence >= 0.88:
                    table.add(t.surface, t.lemma_key, conf=t.confidence)
        self._set_lxx_table(table, True)

    def _new_table(self) -> "_FormTable":
        lex = self.lex
        return _FormTable(common_noun=lambda k: lex.pos(k) == "N")

    def _set_lxx_table(self, table: "_FormTable", ready: bool) -> None:
        self.lxx_table = table
        self._lxx_dict_ready = ready
        self._known_cache.clear()
        self._known_tok_cache.clear()
        self._lemma_forms_cache.clear()
        self._attested_cache.clear()

    def lxx_form_confidence(self, token: str, key: str) -> float:
        """Confidence of a second-pass pairing that rests on the LXX first-pass table."""
        return min(0.93, self.lxx_table.best_conf(token, key) or 0.88)

    # -- paradigm evidence for the between-words pairing ----------------------------------------
    def lemma_forms(self, key: str) -> Set[str]:
        """Bare forms a tagged corpus attests for ``key`` or for a lemma TBESG links to it under
        another convention (ἔφαγον: φαγεῖν 'a Form of' ἐσθίω): TAGNT and the LXX first pass."""
        hit = self._lemma_forms_cache.get(key)
        if hit is not None:
            return hit
        if self._forms_by_key is None:
            self._forms_by_key = defaultdict(set)
            for ak, c in self.nt.forms.acc.items():
                for k in c:
                    self._forms_by_key[k].add(greek_bare(ak))
            self._targets_index = defaultdict(set)
            for k in list(self._forms_by_key):
                for tgt in self._tbesg_targets(k):
                    self._targets_index[tgt].add(k)
        related = {key}
        for tgt in self._tbesg_targets(key):
            related |= self._targets_index.get(tgt, set())
        out: Set[str] = set()
        for k in related:
            out |= self._forms_by_key.get(k, set())
            out |= self.lxx_table.forms_of(k)
        self._lemma_forms_cache[key] = out
        return out

    def _tbesg_targets(self, k: str) -> Set[str]:
        t = self.lex.tbesg
        out = {k}
        for r in t.by_estrong.get(k, []):
            if r["relation"] in ("a Form of", "a Spelling of", "a Meaning of"):
                m = re.match(r"(G\d+[A-Z]?)", r["target"] or "")
                if m:
                    out.add(t.estrong_of.get(m.group(1), m.group(1)))
        return out

    def continues_attested_form(self, token: str, key: str, strict: bool = False) -> bool:
        """The token and a form a tagged corpus attests for this lemma share a stem (at least two
        letters and 40% of the shorter word) and differ only in endings (at most five letters of
        the token, six of the attested form), with the same prepositions in front (augment and
        reduplication set aside): ὀφθήτω / ὤφθη, ἔφαγες / ἔφαγεν (φαγεῖν, TBESG 'a Form of'
        ἐσθίω), ἀφελῶ / ἀφελεῖ, εὐηρέστησεν / εὐηρεστηκέναι.  Not ᾔνεσεν / ἤγγισεν (ἐγγίζω),
        δικάσωμεν / ἐδοκίμασεν (δοκιμάζω), ἐνεποίησεν / ἐξεποίησεν (ἐκποιέω), κατακληρονομῇ /
        κατακληροδοτ- (κατακληροδοτέω).  ``strict`` (at least three shared letters and 60%) is the
        test of _table_contradicted: ζῶσαι / ζῶσαν (ζάω), not ἐλέει / ἐλαίῳ (ἔλαιον).
        Calibrated on the Rahlfs yardstick of the 18 Nov verification (evaluation only)."""
        tb = greek_bare(token)
        ck = (tb, key, strict)
        v = self._attested_cache.get(ck)
        if v is not None:
            return v
        cp_min, share = (3, 0.6) if strict else (2, 0.4)
        t_pre, t_core = _preverb_split(tb)
        t_vars = _augment_variants(t_core)
        v = False
        for f in self.lemma_forms(key):
            f_pre, f_core = _preverb_split(f)
            if f_pre != t_pre:
                continue
            for a in t_vars:
                for b in _augment_variants(f_core):
                    cp = _lcp(a, b)
                    if (cp >= cp_min and len(a) - cp <= 5 and len(b) - cp <= 6
                            and cp >= share * min(len(a), len(b))):
                        v = True
                        break
                if v:
                    break
            if v:
                break
        self._attested_cache[ck] = v
        return v

    # -- chapters --------------------------------------------------------------------------------
    def tag_chapter(self, book_slug: str, chapter: int, verses: Dict[int, str]) -> Dict[int, List[TokenTag]]:
        nt = _is_nt(book_slug)
        out: Dict[int, List[TokenTag]] = {}
        for vs in sorted(verses):
            text = verses[vs] or ""
            if nt:
                out[vs] = self.tag_nt_verse(book_slug, chapter, vs, text)
            else:
                out[vs] = self.tag_lxx_verse(book_slug, chapter, vs, text)
        return out


def _is_nt(slug: str) -> bool:
    try:
        from ..catalog import BOOKS_BY_SLUG
        b = BOOKS_BY_SLUG.get(slug)
        if b is not None:
            return b.testament == "NT"
    except Exception:  # pragma: no cover
        pass
    return slug in set(_TAGNT_BOOKS.values())


def _matched_form(token: str, w: _TagntWord) -> Optional[str]:
    """The bare form of ``w`` that ``token`` pairs with: the first of _form_keys(token) that is a
    key of ``w.alts`` (the same choice _align_exact makes), or None."""
    for bk in _form_keys(token):
        if w.alts.get(bk):
            return bk
    return None


def _align_exact(tokens: List[str], words: List[_TagntWord]) -> List[Tuple[int, int, str, bool]]:
    """Order-preserving alignment of Studio tokens to TAGNT words by bare form (printed word,
    its spellings or variant words).  Exact accent agreement wins ties (ἡ/ἤ, εἰ/εἶ)."""
    n, m = len(tokens), len(words)
    keys = [_form_keys(t) for t in tokens]
    aks = [accent_key(t) for t in tokens]
    W: List[List[float]] = [[0.0] * m for _ in range(n)]
    L: List[List[Optional[str]]] = [[None] * m for _ in range(n)]
    for i in range(n):
        for j, w in enumerate(words):
            for bk in keys[i]:
                k = w.alts.get(bk)
                if k:
                    exact = aks[i] == w.akey
                    W[i][j] = 1.0 + (0.01 if exact else 0.0) + (0.001 if bk == keys[i][0] else 0.0)
                    L[i][j] = k
                    break
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
            out.append((i - 1, j - 1, L[i - 1][j - 1], w >= 1.01))
            i -= 1
            j -= 1
        elif D[i - 1][j] >= D[i][j - 1]:
            i -= 1
        else:
            j -= 1
    out.reverse()
    return out


# ---------------------------------------------------------------------------
# Module-level contract
# ---------------------------------------------------------------------------

_TAGGER: Optional[GreekTagger] = None


def get_tagger() -> GreekTagger:
    global _TAGGER
    if _TAGGER is None:
        _TAGGER = GreekTagger()
    return _TAGGER


def load_lexicon() -> Dict[str, LemmaEntry]:
    """Every lemma the Greek tagger can emit, keyed by lemma_key (cached)."""
    return get_tagger().lexicon()


@lru_cache(maxsize=1)
def _tegmc_codes() -> Dict[str, str]:
    """TEGMC full morphology codes -> summary phrase ('N-DSF' -> 'Noun Dative Singular Feminine').

    The 'FULL MORPHOLOGY CODES' part of the file is a list of blocks: a line 'CODE<TAB>Function=...'
    followed by tab-indented lines (summary phrase, description, example) and a '$' line."""
    path = _tegmc_file()
    if path is None:
        return {}
    with open(_fs(path), encoding="utf-8-sig") as fh:
        lines = fh.read().replace("\r", "").split("\n")
    out: Dict[str, str] = {}
    in_full = False
    code_re = re.compile(r"^[A-Z0-9]+(?:-[A-Z0-9]+)*$")
    for i, line in enumerate(lines[:-1]):
        if line.startswith("FULL MORPHOLOGY CODES"):
            in_full = True
            continue
        if not in_full or not line or line[0].isspace() or "\t" not in line:
            continue
        code, rest = line.split("\t", 1)
        nxt = lines[i + 1]
        if not code_re.match(code) or "Function=" not in rest or not nxt.startswith("\t"):
            continue
        words = nxt.strip().strip('"').replace("‚", ",").split()
        phrase = [wd for k, wd in enumerate(words) if k == 0 or wd != words[k - 1]]
        if phrase:
            out[code] = " ".join(phrase)
    return out


def _bare_code(code: str) -> str:
    prefix = MORPH_SCHEME + ":"
    return code[len(prefix):] if code.startswith(prefix) else code


def morph_legend(codes: Optional[Iterable[str]] = None) -> Dict[str, str]:
    """English description of Greek parse codes, keyed exactly as ``TokenTag.morph`` ('R:N-DSF'):
    ``{'R:N-DSF': 'Noun Dative Singular Feminine', 'R:P-1NS+CONJ': 'Personal pronoun 1st
    Nominative Singular + Conjunction', ...}`` from STEPBible TEGMC (CC BY 4.0, see SRC_TEGMC).

    ``codes``: the codes to describe (with or without the 'R:' prefix); None = every parse the
    TAGNT words can give a token (printed words and other editions' words; builds the tagger).
    A code TEGMC does not describe is left out, so ``set(codes) - set(result)`` lists the gaps."""
    table = _tegmc_codes()
    if codes is None:
        nt = get_tagger().nt
        seen: Set[str] = set()
        for words in nt.verses.values():
            for w in words:
                seen.update(p for p in w.morphs.values() if p)
        codes = seen
    out: Dict[str, str] = {}
    for code in codes:
        if not code:
            continue
        bare = _bare_code(code)
        parts = bare.split("+")
        if all(p in table for p in parts):
            out[f"{MORPH_SCHEME}:{bare}"] = " + ".join(table[p] for p in parts)
    return dict(sorted(out.items()))


# The LXX-wide form table is one fixed function of the Greek OT corpus, built once per process by
# whichever runs first: tag_chapter() on an OT book, tag_all() or prepare().  tag_chapter() and
# prepare() read the Studio database (data/studio.db, opened read-only); tag_all(conn) and
# prepare(conn) read ``conn``.  Once built the table never changes (prepare(..., force=True)
# excepted), so a chapter gets the same tags whether or not tag_all()/prepare() ran before it.
AUTO_PREPARE = True      # False: tag_chapter() fixes an EMPTY table instead of reading the Studio
                         # DB (per-verse alignment only; tests); the table is still fixed once


def _studio_db_path() -> Optional[Path]:
    try:
        from ..catalog import DATA_DIR
    except Exception:   # pragma: no cover
        return None
    return Path(DATA_DIR) / "studio.db"


def prepare(conn: Optional[sqlite3.Connection] = None, force: bool = False) -> None:
    """Build the LXX-wide form table (a first alignment pass over the whole Greek OT) unless it
    is already built.  ``conn``: the corpus to read; None reads the Studio DB read-only (an empty
    table when there is none).  ``force`` rebuilds it."""
    tagger = get_tagger()
    if tagger._lxx_dict_ready and not force:
        return
    if conn is not None:
        chapters = _db_chapters(conn)
    else:
        chapters = []
        db = _studio_db_path()
        if db is not None and db.exists():
            try:
                ro = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
                try:
                    chapters = _db_chapters(ro)
                finally:
                    ro.close()
            except sqlite3.Error:   # pragma: no cover - no Greek text: the per-verse alignment only
                chapters = []
    tagger.build_lxx_form_table(
        (slug, ch, vs, text) for slug, ch, verses in chapters if not _is_nt(slug)
        for vs, text in verses.items())


def _ensure_prepared() -> None:
    tagger = get_tagger()
    if tagger._lxx_dict_ready:
        return
    if AUTO_PREPARE:
        prepare()
    else:
        tagger.build_lxx_form_table(())


def tag_chapter(book_slug: str, chapter: int, verses: Dict[int, str]) -> Dict[int, List[TokenTag]]:
    """Tag one chapter: ``verses`` maps the Studio's Greek verse numbers to critical text.  The
    first OT chapter of a process builds the LXX-wide form table (about 40 s; see prepare())."""
    if not _is_nt(book_slug):
        _ensure_prepared()
    return get_tagger().tag_chapter(book_slug, chapter, verses)


def _db_chapters(conn: sqlite3.Connection) -> List[Tuple[str, int, Dict[int, str]]]:
    rows = conn.execute(
        "SELECT c.book_slug, c.chapter, v.verse, v.critical_text FROM verses v "
        "JOIN chapters c ON c.id = v.chapter_id WHERE c.language = 'greek' "
        "ORDER BY c.id, v.verse").fetchall()
    chapters: Dict[Tuple[str, int], Dict[int, str]] = {}
    order: List[Tuple[str, int]] = []
    for slug, ch, vs, text in rows:
        k = (slug, int(ch))
        if k not in chapters:
            chapters[k] = {}
            order.append(k)
        chapters[k][int(vs)] = text or ""
    return [(s, c, chapters[(s, c)]) for s, c in order]


def tag_all(conn: sqlite3.Connection) -> Iterator[Tuple[str, int, Dict[int, List[TokenTag]]]]:
    """Tag every Greek chapter in the Studio DB: yields (book_slug, chapter, {verse: tags}).

    The LXX-wide form table is built from a first alignment pass over the whole Greek OT, so
    the second pass can resolve forms that the per-verse alignment left open."""
    tagger = get_tagger()
    chapters = _db_chapters(conn)
    if not tagger._lxx_dict_ready:
        tagger.build_lxx_form_table(
            (slug, ch, vs, text) for slug, ch, verses in chapters if not _is_nt(slug)
            for vs, text in verses.items())
    for slug, ch, verses in chapters:
        yield slug, ch, tag_chapter(slug, ch, verses)


def tag_all_dict(conn: sqlite3.Connection) -> Dict[Tuple[str, int], Dict[int, List[TokenTag]]]:
    """tag_all() collected into {(book_slug, chapter): {verse: [TokenTag]}}."""
    return {(slug, ch): res for slug, ch, res in tag_all(conn)}
