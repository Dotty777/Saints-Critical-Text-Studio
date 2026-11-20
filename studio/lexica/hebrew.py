"""Hebrew / Aramaic gold lemma tagger for The Saints Concordance.

Every Studio Hebrew token is tagged with the lemma that the OpenScriptures Hebrew Bible gives the
same word of the same Masoretic verse; roots come from Brown-Driver-Briggs through the OSHB lexical
index.  Nothing is guessed: a token that cannot be matched to a tagged OSHB word, and whose spelling
is not tied to one lemma across the whole Old Testament, stays untagged (``lemma_key=None``).

Sources (all openly licensed; each is named in the ``LemmaEntry`` fields it feeds):

* Lemmas, prefixes, morphology: OSHB MorphHB ``wlc/*.xml`` -- lemma and morph tags CC BY 4.0
  ("Original work of the Open Scriptures Hebrew Bible available at
  https://github.com/openscriptures/morphhb"), WLC text public domain.
* Lemma headwords, parts of speech and root families: OSHB Hebrew Lexicon
  (``LexicalIndex.xml``, ``AugIndex.xml``, ``BrownDriverBriggs.xml``), CC BY 4.0, Open Scriptures
  Hebrew Bible Project; the BDB and Strong's texts themselves are public domain.
* Display glosses: STEPBible TBESH column 7 "Gloss" (CC BY 4.0, Tyndale House) when its row can be
  matched to the OSHB lemma unambiguously (same augmented Strong's number, same consonants:
  אֱלֹהִים 'God', הָיָה 'to be', אָמַר 'to say', דָּבָר 'word', יהוה 'LORD'); otherwise the lexical
  index <def> (BDB's first sense).  Column 8 ("Meaning", Online Bible) is never read.
* Proper names with several TBESH rows (one per bearer: H8289G 'Lasharon', H8289H/I 'Sharon'):
  the row whose bearer has most of the lemma's OSHB occurrences, counted with the verse lists of
  STEPBible TIPNR (CC BY 4.0, "Translators Individualised Proper Names with all References";
  only its dStrong and reference columns are read) -- שָׁרוֹן 'Sharon' (6 of 7), רוּמָה 'Rumah'
  (2 Kgs 23:36; TBESH's 'Dumah' row is Josh 15:52, where the reading text has דּוּמָה), שָׁאוּל
  'Saul', מִיכָיְהוּ 'Micaiah'.  A TBESH name gloss in backticks is a translation of the name
  (שִׁילֹה '`tribute`', אֻכָל '`worn out`') and a common-noun row is a sense, not the name (רֹאשׁ
  'prince' for Rosh): the lexical index's name is used instead.  Reference residue of the index
  ('Huram. Compare', 'Jair(from the margin)') is cut.  ``GLOSS_OVERRIDES`` (each entry with its
  reason and references) fixes the few glosses that do not fit many occurrences of an OSHB lemma
  (לִקְרַאת 'befall' -> 'meeting; toward', חֵיל 'rampart' -> 'army; rampart', הֹבִישׁ under
  יָבֵשׁ 'to wither' -> 'to dry up; put to shame', יֵשׁ 'there' -> 'there is') or give an emendation
  instead of the name in the text (2 Sam 24:6 תַּחְתִּים חׇדְשִׁי 'Kadesh' -> 'Tahtim-hodshi'), and
  sets the part of speech where gloss and POS clash (סֶלָה is no verb).  A family keeps the first
  sense of a corrected head gloss as its meaning (עוף 'to fly', not 'to fly; be weary').
  ``HEADWORD_OVERRIDES`` replaces a headword that is not the word of the text (מַי -> מַיִם).
* ``lxx_equivalents()``: MACULA Hebrew (Biblica, CC BY 4.0) ``greek``/``greekstrong`` columns.

OSHB corrections
    ``OSHB_LEMMA_CORRECTIONS`` replaces 19 OSHB lemma tags that are demonstrably wrong (wrong
    Strong's number against the word's own letters and OSHB's own morphology; 2 Sam 18:4 יָֽצְאוּ
    tagged יָרַד, 1 Kgs 7:23 שְׂפָתוֹ tagged "second").  The TokenTag notes say so.

Lemma keys
    ``H`` + four-digit Strong's number + the OSHB augment letter, as OSHB tags the word
    (``H7225``, ``H1254a``, ``H0430``).  OSHB tags a word that is only a prefix preposition with
    a pronominal suffix (לוֹ, בָּהֶם) by the prefix letter; those get STEPBible's extended Strong's
    numbers for the prefixes (TBESH, CC BY): ``H9002`` ו, ``H9003`` ב, ``H9004`` כ, ``H9005`` ל,
    ``H9006`` מ, ``H9007`` שֶׁ, ``H9008`` interrogative הֲ, ``H9009`` article; in Aramaic verses
    the same with ``arc:`` in front (``arc:H9005``), pointing at the Aramaic BDB entry.

Alignment (``tag_chapter``)
    The Studio prints an eclectic text (MAM, Leningrad, Aleppo ...), the qere pointed and the ketiv
    in parentheses (dropped by ``tokenize_verse``).  OSHB words are read in the same way (qere in,
    ketiv out).  Studio tokens and OSHB words of the same MT verse are aligned by consonants with
    ``difflib`` (identical runs) and, inside each differing stretch, a small monotone
    dynamic-programming match, so one inserted or omitted word never shifts the rest.  The match
    also pairs one token with 2-3 WLC words written as one (רַבְשָׁקֵה = רַב־שָׁקֵה; tagged only
    when OSHB gives the words one lemma) and 2-3 tokens with one WLC word (פַּת בַּג = פַּתְבַּג; a
    piece is tagged only when its spelling is not another lemma's; never when the Studio prints the
    WLC word as its ketiv and the pieces as the qere: Ps 123:4 לִגְאֵי יוֹנִים).  A 1:1 pair is
    accepted when the consonants are identical (confidence 1.0) -- unless the Studio's vowels make
    it another OSHB word (2 Chr 1:5 Studio שָׁם "there", WLC שָׂם "put"), when the Studio form's lemma
    is taken (``method='gold-form'``) -- or differ only in the matres lectionis ו/י
    (plene/defective, 0.95).  A pair that differs otherwise (0.9) keeps the WLC lemma only when the
    Studio form is attested for that lemma in OSHB, or the difference is orthographic (other
    proclitics; final א/ה in Aramaic and names; quiescent א) and the Studio form is not attested
    for another lemma.  Where OSHB gives a bare Strong's number although BDB has homographs
    (7451 for 7451a/b/c) the word's pointed spelling must single one out, else untagged.
    Unaligned tokens fall back to a whole-OT dictionary of OSHB *pointed* forms, used only when one
    lemma of the verse's language covers >= 95 % of >= 3 occurrences (``method='gold-form'``;
    leave-one-out precision 99.45 % on 30,295 decisions; consonant-only forms were 60-73 % right
    and are not used).  Unpointed tokens without a WLC counterpart (ketiv residue) and everything
    else stay ``untagged``.

Roots
    lemma -> AugIndex -> LexicalIndex entry -> follow ``<etym type="sub">`` links to the family
    head -> its ``<etym root=".." type="main">`` consonants.  BDB's homograph numbers (the ``mod``
    attribute of BDB root entries: I, II, ...) are kept, so I אבה "be willing" and II אבה are two
    families: ``heb:אבה.I`` / ``heb:אבה.II``; separate BDB root entries with the same letters and
    no number (יָרֵא "fear" / יָרָא "shoot") get the BDB entry id (``heb:ירא@j.df.aa``).  The
    sin/shin dot is part of the key (שׂכל is not שׁכל).  Aramaic entries (``xml:lang="arc"``
    part) give ``arc:...`` keys.  When the head has no
    root consonants but is another lemma (מִ under מִן) the family is that lemma
    (``heb:H4480a``); when the data gives no family the lemma is its own family
    (``root_source='self'``, ``root_key='heb:<lemma_key>'``).
    Where the lexical index and BDB's own arrangement disagree, BDB wins (``_root_plan``,
    ``_bdb_section_head``; ``root_notes(key)`` says why): אָחַד joins חָדַד, under which BDB files it;
    a word the index links into another BDB section joins its own section's root when that root's
    letters are in it (אֲרִיאֵל, אֶרְאֵל under I ארה with אֲרִי "lion"; אֶשְׁעָן under שׁען), else it is
    its own family (שָׁיָה); a word BDB lists apart from the root entry of the same letters is its own
    family (תִּרְגֵּם "vb. quadril.", כרבל); Aramaic נְהַר "river" and נְהִיר "light" are two families;
    BDB's "I. אֵל" (these), "I. אֵת", "III. אוּלָם" number those words, so their families carry no
    root homograph number (``heb:אלה@a.dj.aa``, label א-ל-ה, apart from א-ל-ה I of אֱלֹהִים).
    ``root_gloss`` is one value per family: the head lemma's display gloss, else the root's <def>,
    else the main verb's gloss, else the most frequent member's (``_family_glosses``).
    ``BDB_FAMILY_LINKS`` adds the few BDB placements the lexical index leaves out (תִּירוֹשׁ in the
    section of יָרַשׁ, עֲלָמוֹת under עַלְמָה, I כַּרְמֶל "plantation" under כֶּרֶם).
    Root labels are unique within a language: families whose letters (and BDB homograph number)
    coincide carry their gloss in the label -- ר-ו-ח (to smell) / ר-ו-ח (be wide), בָּמָה (high
    place) / בָּמָה (Bamah) -- else the head word, else person/place, else the lemma key.  The
    formula keeps the bare letters (ר-ו-ח → רוּחַ).

Function words (``is_content=False``)
    Decided per lemma from OSHB's own morphology: a lemma is a function word when at least half of
    its OSHB occurrences carry one of the main-segment codes in ``FUNCTION_MORPH_CODES`` -- C
    (conjunction), R (preposition), Td (article), To (object marker אֵת), Tr (relative אֲשֶׁר /
    שֶׁ), Tn (negative), Pp (independent personal pronoun), Pr (relative pronoun) -- or 90 % of at
    least two occurrences when the lexical index calls it a noun, name, verb or adjective (תַּחַת
    stays a preposition, the names לֹא עַמִּי, אַל תַּשְׁחֵת stay content, and one conjunction code on
    a noun -- Isa 3:24 כִּי "branding", Prov 31:4 אוֹ "desire" -- does not make it a function word),
    plus every lemma the lexical index calls a personal, demonstrative or relative pronoun (Pp, Pd,
    Pr: בָּהֵן "in them" H2004, Aramaic אִנּוּן, גֵּה), plus every prefix-letter lemma, plus the
    particles in ``FUNCTION_PARTICLE_KEYS`` (כֹּל, זֶה / זֹאת / אֵלֶּה, מָה, מִי, הִנֵּה, גַּם, כֵּן, אַךְ,
    רַק and their Aramaic counterparts).  ``function_word_keys()`` lists them.

Prefix codes
    From OSHB's lemma prefixes; interrogative הֲ is ``P:i`` also where OSHB writes the article's
    letter 'd' but the morphology says interrogative (``Ti``: 1 Sam 15:22 הַחֵפֶץ).

Parsing (``TokenTag.morph``, ``TokenTag.src``; added 18 Nov 2026 for the per-book word layer)
    A token tagged from one OSHB word (1:1 alignment, the WLC ketiv, or a bare Strong's number
    resolved by spelling) carries ``src='oshb:<w id>'`` and ``morph='O:' + OSHB's morph string``
    with the prefixes (``O:HR/Ncfsa``, ``O:HC/Vqw3ms``) -- but the parse is given only when it
    describes the Studio's spelling: the pointed forms are equal; or they differ only in what does
    not change a parse (matres lectionis ו/י as holam / shureq / hiriq / tsere / segol vowel letters,
    the silent י of -ָיו, hataf for shewa, dagesh, meteg); or OSHB parses the Studio's pointed form
    that way elsewhere.  Otherwise (Ps 8:4 Studio מַעֲשֵׂה singular, WLC מַעֲשֵׂי plural; Judg 19:4
    Studio Hiphil pointing, WLC Qal; other proclitics than WLC) ``morph`` is None and a note says
    why.  One token for 2-3 WLC words (merge) and pieces of one WLC word (split) get no parse (a
    piece keeps the word's ``src``); form-dictionary tags, a Studio pointing that is another word
    (``_pointing_conflict``) and untagged tokens get neither.  ``morph_legend()`` expands every code
    into English from OSHB's own key to its codes, ``parsing/Oshm.xml`` (CC BY 4.0, see
    ``SRC_MORPH_LEGEND``); STEPBible TEHMC was not used because it codes some verb forms with other
    letters (its ``c`` + person is a cohortative, OSHB's ``c`` the infinitive construct) and expands
    586 of the 901 OSHB segment codes.

``lxx_equivalents()`` maps a lemma to the Greek Strong's numbers MACULA gives the LXX rendering of
its occurrences (MACULA words matched to OSHB words by verse, word number and consonants).  For a
content lemma the Greek article, conjunctions, prepositions and pronouns MACULA aligns alongside
(``GREEK_FUNCTION_STRONGS``) are not counted.
"""

from __future__ import annotations

import difflib
import os
import re
import sqlite3
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from . import LemmaEntry, TokenTag, hebrew_consonants, tokenize_verse
from ..catalog import DATA_DIR, REPO_ROOT, STUDIO_ROOT

# ---------------------------------------------------------------------------
# Sources and licences
# ---------------------------------------------------------------------------

SRC_OSHB = "OSHB MorphHB lemma tags (CC BY 4.0, Open Scriptures Hebrew Bible; WLC text public domain)"
SRC_LEX = "OSHB Hebrew Lexicon LexicalIndex/BDB (CC BY 4.0)"
SRC_TBESH_GLOSS = "STEPBible TBESH col. 7 Gloss (CC BY 4.0)"
SRC_TIPNR = "bearer chosen by STEPBible TIPNR references (CC BY 4.0)"
SRC_GLOSS_FIX = "gloss corrected in the Studio (hebrew.GLOSS_OVERRIDES)"
SRC_MACULA = "MACULA Hebrew greek/greekstrong (Biblica, CC BY 4.0)"
SRC_MORPH_LEGEND = ("OSHB morphology key parsing/Oshm.xml (CC BY 4.0, Original work of the Open Scriptures Hebrew "
                    "Bible available at https://github.com/openscriptures/morphhb); changes: segments joined with "
                    "' + ', spacing normalised, 'Adjective adjective' shortened to 'Adjective', codes missing from "
                    "the key composed from its segment expansions")

ROOT_SRC_BDB = "OSHB-BDB"
ROOT_SRC_SELF = "self"

# Studio book slug -> OSHB wlc file stem (OSIS book code)
OSHB_BOOK: Dict[str, str] = {
    "genesis": "Gen", "exodus": "Exod", "leviticus": "Lev", "numbers": "Num", "deuteronomy": "Deut",
    "joshua": "Josh", "judges": "Judg", "ruth": "Ruth", "1-samuel": "1Sam", "2-samuel": "2Sam",
    "1-kings": "1Kgs", "2-kings": "2Kgs", "1-chronicles": "1Chr", "2-chronicles": "2Chr",
    "ezra": "Ezra", "nehemiah": "Neh", "esther": "Esth", "job": "Job", "psalms": "Ps",
    "proverbs": "Prov", "ecclesiastes": "Eccl", "song-of-songs": "Song", "isaiah": "Isa",
    "jeremiah": "Jer", "lamentations": "Lam", "ezekiel": "Ezek", "daniel": "Dan", "hosea": "Hos",
    "joel": "Joel", "amos": "Amos", "obadiah": "Obad", "jonah": "Jonah", "micah": "Mic",
    "nahum": "Nah", "habakkuk": "Hab", "zephaniah": "Zeph", "haggai": "Hag", "zechariah": "Zech",
    "malachi": "Mal",
}
# MACULA / USFM book code -> OSHB book code
_USFM_TO_OSHB: Dict[str, str] = {
    "GEN": "Gen", "EXO": "Exod", "LEV": "Lev", "NUM": "Num", "DEU": "Deut", "JOS": "Josh",
    "JDG": "Judg", "RUT": "Ruth", "1SA": "1Sam", "2SA": "2Sam", "1KI": "1Kgs", "2KI": "2Kgs",
    "1CH": "1Chr", "2CH": "2Chr", "EZR": "Ezra", "NEH": "Neh", "EST": "Esth", "JOB": "Job",
    "PSA": "Ps", "PRO": "Prov", "ECC": "Eccl", "SNG": "Song", "ISA": "Isa", "JER": "Jer",
    "LAM": "Lam", "EZK": "Ezek", "DAN": "Dan", "HOS": "Hos", "JOL": "Joel", "AMO": "Amos",
    "OBA": "Obad", "JON": "Jonah", "MIC": "Mic", "NAM": "Nah", "HAB": "Hab", "ZEP": "Zeph",
    "HAG": "Hag", "ZEC": "Zech", "MAL": "Mal",
}

# OSHB prefix lemma codes -> TokenTag.prefixes codes
PREFIX_CODES: Dict[str, str] = {
    "b": "P:b", "c": "P:w", "d": "P:h", "k": "P:k", "l": "P:l", "m": "P:m", "s": "P:sh",
    "i": "P:i",  # interrogative הֲ
}
# OSHB prefix lemma codes used as the main lemma (prep + suffix) -> STEPBible extended Strong's
LETTER_KEYS: Dict[str, str] = {
    "c": "H9002", "b": "H9003", "k": "H9004", "l": "H9005", "m": "H9006", "s": "H9007",
    "i": "H9008", "d": "H9009",
}
_LETTER_CONSONANT = {"c": "ו", "b": "ב", "k": "כ", "l": "ל", "m": "מ", "s": "ש", "i": "ה", "d": "ה"}

FUNCTION_MORPH_CODES = frozenset({"C", "R", "Td", "To", "Tr", "Tn", "Pp", "Pr"})

# High-frequency particles that OSHB codes as noun, adverb, demonstrative / interrogative pronoun
# or particle (N, D, Pd, Ti, Tm, Ta) and that the concordance also treats as function words
# (is_content=False): כֹּל "all", the demonstratives זֶה / זֹאת / אֵלֶּה, מָה "what", מִי "who",
# הִנֵּה / הֵן "behold", גַּם / אַף "also", כֵּן "so", אַךְ "only, surely", רַק "only", with their
# variant lemmas and the Aramaic counterparts.  Content homographs stay content: H3651a כֵּן "right,
# honest" (adjective), H7534 רַק "thin".  (H2004 הֵן "they (fem.)", which OSHB codes only as a
# suffix, is a function word through its lexical-index POS Pp, see ``FUNCTION_LEX_POS``.)
FUNCTION_PARTICLE_KEYS = frozenset({
    "H3605", "H3606",                                   # כֹּל all (Hebrew, Aramaic)
    "H2088", "H2063", "H2090", "H2097", "H0428", "H0411",  # זֶה זֹאת זֹה זוֹ אֵלֶּה אֵל "this, these"
    "H1975", "H1976", "H1977",                          # הַלָּז הַלָּזֶה הַלֵּזוּ "this, that"
    "H1836", "H1668", "H1791", "H1797", "H0479", "H0459", "H0429", "H0412",  # Aramaic demonstratives
    "H4100", "H4310", "H4101", "H4479", "H3964",        # מָה מִי, Aramaic מָה מַן מָא
    "H2009", "H2005", "H0431", "H0718", "H1888a", "H1888b",  # הִנֵּה הֵן, Aramaic אֲלוּ אֲרוּ הָא הֵא
    "H1571", "H0637", "H0638",                          # גַּם, אַף (Hebrew, Aramaic) "also"
    "H3651c", "H3651b", "H3652",                        # כֵּן "so", כִּי עַל כֵּן, Aramaic כֵּן
    "H0389", "H7535",                                   # אַךְ, רַק "only"
})

# Greek function words (Strong's numbers) that MACULA often aligns to a Hebrew content word only
# because the LXX adds an article, conjunction, preposition or pronoun around its rendering.  They
# are not counted as LXX equivalents of Hebrew content lemmas (they still are for function words).
# Improper prepositions (ἐνώπιον for לִפְנֵי) and indefinites (οὐδείς for מְאוּמָה) are real renderings
# and stay.
GREEK_FUNCTION_STRONGS = frozenset({
    "G3588",                                                        # ὁ article
    "G2532", "G1161", "G0235", "G2228", "G1063", "G3754", "G2443", "G3704", "G5613", "G1437",
    "G1487", "G0302", "G3767", "G5037", "G1211", "G3303", "G2504", "G3779", "G2400",  # conjunctions, particles
    "G1519", "G1722", "G1537", "G0575", "G1909", "G4314", "G3326", "G1223", "G2596", "G3844",
    "G4012", "G5228", "G5259", "G4253", "G0473", "G4862",           # prepositions
    "G3756", "G3361",                                               # οὐ, μή
    "G0846", "G1473", "G4771", "G2249", "G5210", "G1438", "G3739", "G3778", "G1565", "G3748",
    "G3745", "G5101", "G3956",                                      # pronouns, πᾶς
})

# OSHB lemma tags that are demonstrably wrong (wrong Strong's number; the WLC consonants and OSHB's
# own morphology fit only the corrected lemma; STEPBible TAHOT, CC BY, agrees with every correction).
# Keyed by the OSHB <w id>; applied only while OSHB still carries the listed lemma, so a corrected
# OSHB release makes an entry inert.  (ref, OSHB lemma attribute, corrected lemma attribute, reason)
# The first five were found by the independent review of 18 Nov 2026; the others by checking every
# OSHB word whose lemma differs from TAHOT's and whose lemma letters are not in the word at all.
OSHB_LEMMA_CORRECTIONS: Dict[str, Tuple[str, str, str, str]] = {
    "02t7c": ("Exod.16.8", "8519", "3885 b",
              "מַלִּינִם is a Hiphil participle (OSHB morph Vhrmpa) of לוּן 'murmur', not the noun תְּלֻנָּה"),
    "04yhZ": ("Num.23.13", "3212", "4994", "נָא is the particle 'please' (OSHB morph Tj), not יָלַךְ"),
    "09QUD": ("1Sam.28.8", "7080", "4994", "נָא is the particle 'please' (OSHB morph Te), not קָסַם"),
    "13t8Y": ("1Chr.12.39", "6186 a", "5737 a",
              "עֹדְרֵי is a participle of עָדַר I 'help' (BDB, 1 Ch 12:34, 39), not עָרַךְ"),
    "13nVn": ("1Chr.12.39", "b/8003", "b/3824", "בְּלֵבָב 'with a heart': noun לֵבָב (OSHB morph Ncmsa); "
              "OSHB swapped the lemmas of לֵבָב and שָׁלֵם"),
    "13rN2": ("1Chr.12.39", "3824", "8003", "שָׁלֵם 'whole': adjective (OSHB morph Aamsa); "
              "OSHB swapped the lemmas of לֵבָב and שָׁלֵם"),
    "19pUN": ("Ps.5.6", "l/2962", "l/5048", "לְנֶגֶד עֵינֶיךָ: נֶגֶד 'before', not טֶרֶם"),
    "23S76": ("Isa.7.8", "c/b/1157", "c/b/5750", "וּבְעוֹד: וְ + בְּ + עוֹד 'yet' (OSHB morph C/R/D), not בַּעַד"),
    "234TA": ("Isa.10.32", "1323", "6726", "צִיּוֹן is Zion (OSHB morph Np), not בַּת"),
    "231W5": ("Isa.19.5", "c/3001", "c/5405", "וְנִשְּׁתוּ: Niphal of נָשַׁת 'be dried up'; "
              "OSHB swapped the lemmas of נִשְּׁתוּ and יָבֵשׁ"),
    "23Fm5": ("Isa.19.5", "c/5405", "c/3001", "וְיָבֵשׁ: Qal of יָבֵשׁ 'be dry'; OSHB swapped the lemmas of "
              "נִשְּׁתוּ and יָבֵשׁ"),
    "23BDe": ("Isa.28.4", "k/1061", "k/1063", "כְּבִכּוּרָהּ is singular: בִּכּוּרָה 'first-ripe fig', "
              "not the plural-only בִּכּוּרִים 'first-fruits'"),
    "23Lyh": ("Isa.30.2", "l/5810", "l/5756", "לָעוֹז 'to take refuge': BDB files Is 30:2 under עוּז, not עָזַז"),
    "24FGD": ("Jer.7.31", "1323", "1121 a", "בְּנֵיהֶם 'their sons' (then וְאֶת־בְּנֹתֵיהֶם 'their daughters'): "
              "בֵּן, not בַּת"),
    "10V7e": ("2Sam.18.4", "3381", "3318",
              "יָֽצְאוּ 'they went out' is יָצָא; OSHB's 3381 (יָרַד 'go down') shares no root letter with it"),
    "04g9U": ("Num.15.30", "7411 b", "7311 a",
              "בְּיָד רָמָה 'with a high hand': Qal participle f. of רוּם 'be high' (morph Vqrfsa), not רָמָה II 'beguile'"),
    "04dCx": ("Num.18.32", "6918", "6944",
              "קׇדְשֵׁי 'the holy things of' is the noun קֹדֶשׁ (morph Ncmpc), not the adjective קָדוֹשׁ"),
    "10bEm": ("2Sam.5.6", "c/d/6452 b", "c/d/6455",
              "הַפִּסְחִים 'the lame': OSHB's own morph is the adjective (Aampa), BDB פִּסֵּחַ 'lame', not the verb פָּסַח"),
    "11s71": ("1Kgs.7.23", "8145", "8193",
              "שְׂפָתוֹ 'its brim' is שָׂפָה 'lip, edge' (as in מִשְּׂפָתוֹ before it); 8145 is שֵׁנִי 'second'"),
}

# Display glosses (and, where gloss and part of speech clash, the POS) that the Studio corrects.
# OSHB follows Strong's numbering, so a few lemmas cover words that BDB and STEPBible TAHOT (CC BY)
# file elsewhere; the lemma tag stays OSHB's, the gloss must fit the occurrences.  Found by the
# independent check of 18 Nov 2026 (TBESH gloss of the sense TAHOT gives each token).
# lemma key -> (gloss, POS or None, reason)
GLOSS_OVERRIDES: Dict[str, Tuple[str, Optional[str], str]] = {
    "H7125": ("meeting; toward", None,
              "all 100 OSHB occurrences are לִקְרַאת 'to meet, toward' (Gen 14:17 לִקְרָאתוֹ 'to meet him', "
              "Gen 18:2, Exod 4:14); TBESH's 'befall' fits none of them"),
    "H2426": ("army; rampart", None,
              "11 of 19 are חֵיל 'army of' (2 Sam 8:9, 2 Kgs 18:17, Isa 36:2, Joel 2:11), filed by OSHB "
              "under Strong's 2426 'entrenchment, army'; BDB חֵל 'rampart' fits the rest (2 Sam 20:15, Lam 2:8)"),
    "H3001": ("to dry up; put to shame", None,
              "14 of 73 are Hiphil הוֹבִישׁ 'put to shame' (2 Sam 19:6, Jer 6:15, Hos 2:7, Zech 10:5), filed by "
              "OSHB under Strong's 3001 and by BDB under בּוֹשׁ"),
    "H5344a": ("to pierce; designate; curse", None,
               "OSHB files אֶקֹּב 'how shall I curse' (Num 23:8, 23:25; Job 3:8; Prov 11:26, 24:24; BDB קָבַב) "
               "and Niphal נִקְּבוּ 'designated by name' (Num 1:17) under נָקַב I 'pierce'"),
    "H3179": ("to be hot; conceive", None,
              "4 of 10 are 'be warm' (1 Kgs 1:1 יִחַם 'he could not get warm', Deut 19:6, Eccl 4:11, "
              "Ezek 24:11; BDB יָחַם 'be hot'); TBESH gives only 'to conceive' (Gen 30-31)"),
    "H5774a": ("to fly; be weary", None,
               "4 of 31 are וַיָּעַף 'he was weary' (Judg 4:21, 1 Sam 14:28, 14:31, 2 Sam 21:15), filed by "
               "OSHB under עוּף I 'fly'"),
    "H4395": ("full; fullness of produce", None,
              "5 of 8 are the adjective 'full' (Isa 1:21 מְלֵאֲתִי 'full of justice', Isa 22:2, Amos 2:13, "
              "Nah 3:1, 2 Sam 23:11), filed by OSHB under מְלֵאָה 'fullness, produce' (Exod 22:28)"),
    "H3426": ("there is", None, "יֵשׁ 'there is, there are' (BDB 'being, existence'); TBESH's bare 'there' "
                                "reads as the adverb of place"),
    "H0410": ("God; god", None, "about 205 of 245 occurrences name God (Gen 16:13, 17:1; TBESH's own row "
                                "for them says 'God'); 'god' fits the rest (Exod 15:11, Deut 32:12)"),
    "H7473": ("herdsman, shepherd", "N",
              "the participle used as a noun in all 11: רֹעֵי 'herdsmen of' (Gen 13:7-8, 26:20, 1 Sam 21:8), "
              "'shepherd' (Isa 38:12, 44:28, Zech 11:17, 13:7); Strong's 'shepherd', not the verb 'to shepherd'"),
    "H7207": ("sight, seeing", "N",
              "OSHB's one occurrence, the qere רְאוּת 'the seeing (of them) with his eyes' (Eccl 5:10), is a "
              "noun in OSHB's morphology (Strong's 'sight'); the lexical index's verb 'see' clashes with it"),
    "H7202": ("seeing", None, "Job 10:15 רְאֵה: BDB and the lexical index read the adjective 'seeing'; "
                              "TBESH's 'to see' is a verb gloss"),
    "H6033": ("poor", None, "Aramaic עֲנָי 'the poor' (Dan 4:24) is an adjective (lexical index 'poor'); "
                            "TBESH's 'to afflict' is the verb's gloss"),
    "H6358": ("open (of flowers)", None, "פְּטוּרֵי צִצִּים 'open flowers' (1 Kgs 6:18, 29, 32, 35): a passive "
                                         "participle as adjective; TBESH's 'to open' is a verb gloss"),
    "H4984": ("exalted", None, "1 Kgs 1:5 מִתְנַשֵּׂא 'exalted himself', 1 Chr 29:11 'exalted as head': "
                               "the lexical index calls it a noun; TBESH's 'to exalt' is a verb gloss"),
    "H5542": ("Selah", "INTERJ", "סֶלָה, the liturgical marker of the Psalms and Hab 3, is an interjection in "
                                "OSHB's morphology (Tj, all 74); the lexical index's verb class clashes with it"),
    "H8483": ("Tahtim-hodshi", None, "2 Sam 24:6 reads תַּחְתִּים חׇדְשִׁי (lexical index 'Tahtim-hodshi'); "
                                     "TBESH's 'Kadesh' is an emended reading"),
    "H1689": ("Diblah", None, "Ezek 6:14 reads דִּבְלָתָה (BDB [דִּבְלָה] n.pr.loc.); TBESH's 'Riblah' is the "
                              "emendation"),
    "H7384a": ("Diphath", None, "1 Chr 1:6 reads דִּיפַת (BDB n.pr.m.); 'Riphath' is the spelling of Gen 10:3 "
                                "(H7384b)"),
    "H1721": ("Dodanim, Rodanim", None, "one lemma for Gen 10:4 דֹדָנִים 'Dodanim' and 1 Chr 1:7 רוֹדָנִים "
                                        "'Rodanim'"),
    "H1419b": ("Haggedolim", None, "Neh 11:14 'Zabdiel son of Haggedolim' (BDB n.pr.m.); the lexical index's "
                                   "'aloud' is no name"),
    "H3071": ("The LORD Is My Banner", None, "the name of the altar in Exod 17:15, יְהוָה נִסִּי; the lexical "
                                             "index's 'standard' translates נֵס only"),
    # 18 Nov final re-check (TBESH 'X: Y' glosses cut at the colon, or the wrong row of a split number)
    "H7585": ("Sheol", None, "שְׁאוֹל: TBESH 'hell: Sheol' was cut at the colon to 'hell'; TAHOT and the lexical "
                             "index read Sheol, the realm of the dead (Gen 37:35, Ps 16:10)"),
    "H5984": ("Ammonite", None, "עַמּוֹנִי on all 17 Studio tokens is 'Ammonite' (Deut 23:4, 1 Sam 11:1, Neh 2:10, "
                                "Neh 13:1); TBESH's first row 'Meunite' belongs to another people"),
    "H0197": ("porch, vestibule", None, "אוּלָם: 32 of 34 Studio tokens are the temple porch (1 Kgs 6:3, 7:6-8, "
                                        "Ezek 40); TBESH 'Hall' reads as a proper title"),
}

# Headwords that are not the word of the text.  lemma key -> (headword, reason)
HEADWORD_OVERRIDES: Dict[str, Tuple[str, str]] = {
    "H4325": ("מַיִם", "BDB [מַי] 'only pl. מַיִם': the singular never occurs"),
    "H6440": ("פָּנִים", "BDB [פָּנֶה], pl. פָּנִים: the singular never occurs"),
    "H1719b": ("דְּדָן", "Ezek 27:15 reads דְדָן (TBESH 'Dedan'); רֹדָן 'Rhodes' is BDB's emendation"),
}

# Spelling slips in TBESH column 7, corrected word by word (H8240a 'ash heep', H0671b 'govenors').
GLOSS_TYPOS: Dict[str, str] = {"heep": "heap", "govenors": "governors"}

# BDB placements the lexical index leaves out (it marks these words "single"): lemma key -> (lemma
# key of a member of the BDB family, reason).  Only words BDB itself files in the root's section or
# entry; loanwords BDB merely lists there alphabetically are not linked.
BDB_FAMILY_LINKS: Dict[str, Tuple[str, str]] = {
    "H8492": ("H3423", "BDB files תִּירוֹשׁ 'must, new wine' (j.dq.aj) in the section of the root יָרַשׁ (j.dq.aa)"),
    "H5961": ("H5959", "BDB lists עֲלָמוֹת under its entry עַלְמָה 'young woman' (p.cy.ac), root II עלם"),
    "H3759": ("H3754", "BDB files I כַּרְמֶל 'plantation, garden-land' (k.dd.ae) in the section of כֶּרֶם "
                       "'vineyard' (k.dd.aa)"),
}

# Lexical-index parts of speech that make a lemma a function word whatever OSHB's morphology codes
# its occurrences as (H2004 הֵן is coded only as a suffix: בָּהֵן "in them"): personal,
# demonstrative and relative pronouns.  Indefinites (Pf: מְאוּמָה "anything") stay content.
FUNCTION_LEX_POS = frozenset({"Pp", "Pd", "Pr"})
# A noun, name, verb or adjective needs function-word morphology on at least this many occurrences
# (and 90 %) before it counts as a function word: one conjunction code on a noun is no evidence.
FUNCTION_MORPH_MIN = 2

_OSIS_NS = "{http://www.bibletechnologies.net/2003/OSIS/namespace}"
_LEX_NS = "{http://openscriptures.github.com/morphhb/namespace}"
_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

# Confidence of each way a tag is reached
CONF_EXACT = 1.0
CONF_MATRES = 0.95          # consonants differ only in ו/י; also one token = WLC words of one lemma
CONF_FORM_CONFIRMED = 0.9   # other spelling, attested for the same lemma or orthographic (prefixes, final א/ה)
CONF_QUIESCENT = 0.85       # other spelling differing only in quiescent א and ו/י, form unattested
CONF_FORM_UNIQUE = 0.99   # pointed-form decision, >= 10 OSHB occurrences (leave-one-out precision 99.5 %)
CONF_FORM_RARE = 0.99     # pointed-form decision, 3-9 occurrences (leave-one-out precision 99.2 %)
FORM_SHARE_MIN = 0.95
FORM_MIN_COUNT = 3


# ---------------------------------------------------------------------------
# Locating the corpora (self-contained Studio first, legacy layouts after)
# ---------------------------------------------------------------------------

def _tier1_dirs() -> List[Path]:
    out: List[Path] = []
    for base in (REPO_ROOT, STUDIO_ROOT):
        for lang in ("Hebrew", "Greek"):
            p = base / f"Saints-{lang}-Critical-Text" / "01_Tier1_Modern_Critical_Open"
            if p not in out:
                out.append(p)
    ext = STUDIO_ROOT.parents[1] / "01_Tier1_Modern_Critical_Open"
    if ext not in out:
        out.append(ext)
    return out


def _find(*rel: str) -> Optional[Path]:
    for d in _tier1_dirs():
        p = d.joinpath(*rel)
        if p.exists():
            return p
    return None


def oshb_wlc_dir() -> Optional[Path]:
    return _find("OT_OSHB_MorphHB", "wlc")


def oshb_lexicon_dir() -> Optional[Path]:
    return _find("OT_OSHB_HebrewLexicon")


def oshm_path() -> Optional[Path]:
    """OSHB's key to its morphology codes (TEI ``entryFree n="HR/Ncfsa"``), CC BY 4.0."""
    return _find("OT_OSHB_MorphHB", "parsing", "Oshm.xml")


def macula_tsv_path() -> Optional[Path]:
    return _find("OT_Macula_Hebrew", "WLC", "tsv", "macula-hebrew.tsv")


def _stepbible_file(folder: str, pattern: str) -> Optional[Path]:
    for base in ("OT_STEPBible_Data", "NT_OT_STEPBible_Data"):
        d = _find(base, folder)
        if d is not None:
            hits = sorted(d.glob(pattern))
            if hits:
                return hits[0]
    return None


def tbesh_path() -> Optional[Path]:
    return _stepbible_file("Lexicons", "TBESH*.txt")


def tipnr_path() -> Optional[Path]:
    """STEPBible TIPNR, "Translators Individualised Proper Names with all References" (CC BY 4.0)."""
    return _stepbible_file("Proper Nouns", "TIPNR*.txt")


def _open_text(path: Path):
    """Open a UTF-8 text file; on Windows a path past MAX_PATH (TIPNR's is 261 characters inside
    the Studio folder) gets the extended-length prefix."""
    p = str(path)
    if os.name == "nt" and len(p) >= 240 and not p.startswith("\\\\?\\"):
        p = "\\\\?\\" + os.path.abspath(p)
    return open(p, encoding="utf-8-sig", errors="replace")


def corpora_available() -> bool:
    """True when the OSHB morphology and lexicon are present (the tagger cannot run without them)."""
    lex = oshb_lexicon_dir()
    return oshb_wlc_dir() is not None and lex is not None and (lex / "LexicalIndex.xml").exists()


def default_db_path() -> Path:
    return DATA_DIR / "studio.db"


def open_studio_db_readonly(path: Optional[Path] = None) -> sqlite3.Connection:
    p = Path(path or default_db_path()).resolve()
    return sqlite3.connect(p.as_uri() + "?mode=ro", uri=True)


# ---------------------------------------------------------------------------
# Text keys
# ---------------------------------------------------------------------------

_CANTILLATION = re.compile("[\u0591-\u05AF\u05BD\u05BF\u05C0\u05C3-\u05C6\u200C\u200D\u034F/]")
_KEEP_POINTED = re.compile("[^\u05B0-\u05BC\u05C1\u05C2א-ת]")
_MATRES = str.maketrans("", "", "וי")

# Invisible format characters that must not reach a display headword: combining grapheme joiner
# (U+034F, in the lexical index's Jerusalem headword), zero-width space/joiners, LRM/RLM, word
# joiner, BOM, soft hyphen.
_INVISIBLE = re.compile("[\u034F\u200B-\u200F\u2060\uFEFF\u00AD]")


@lru_cache(maxsize=None)
def pointed_key(text: str) -> str:
    """Letters + vowel points + dagesh + shin/sin dot; accents, meteg, rafe, ZWJ removed.
    Qamats qatan is folded to qamats and holam haser to holam so MAM and WLC pointing compare."""
    t = _CANTILLATION.sub("", text).replace("\u05C7", "\u05B8").replace("\u05BA", "\u05B9")
    t = unicodedata.normalize("NFD", t)
    t = _KEEP_POINTED.sub("", t)
    return t.translate(str.maketrans({"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"}))


def strip_accents(text: str) -> str:
    """Remove cantillation marks and invisible joiners (keep vowels) -- for display headwords."""
    return _INVISIBLE.sub("", re.sub("[\u0591-\u05AF]", "", text or "")).strip()


def skeleton(cons: str) -> str:
    """Consonants without the matres lectionis ו and י (plene/defective tolerant)."""
    return cons.translate(_MATRES)


_HIRIQ, _QAMATS, _HOLAM, _QUBUTS, _DAGESH = "ִ", "ָ", "ֹ", "ֻ", "ּ"
_VOWEL_SIGNS = frozenset(chr(c) for c in range(0x05B0, 0x05BC))      # shewa .. qubuts
_HATAF_TO_SHEWA = {"ֱ": "ְ", "ֲ": "ְ", "ֳ": "ְ"}


@lru_cache(maxsize=None)
def parse_key(text: str) -> str:
    """A pointed spelling reduced to what a parse depends on: consonants, sin/shin dot and vowels,
    with the vowel letters of holam, shureq and hiriq written as the vowel alone (plene =
    defective: אֲדוֹמִים = אֲדֹמִם), the silent י of -ָיו dropped (מִבְרָחָיו = מִבְרָחָו), hataf
    vowels read as shewa, dagesh and meteg ignored.  A י after tsere or segol is kept: it can be
    the plural (Ps 35:21 עֵינֵנוּ "our eye" / עֵינֵינוּ "our eyes", pausal כַּפֶּךָ / כַּפֶּיךָ), and so
    is a consonantal ו / י (with a vowel, or after patah: רַגְלַהּ / רַגְלַיהּ)."""
    pk = pointed_key(text)
    clusters: List[Tuple[str, str]] = []
    for ch in pk:
        if "א" <= ch <= "ת" or not clusters:
            clusters.append((ch, ""))
        else:
            clusters[-1] = (clusters[-1][0], clusters[-1][1] + ch)
    out: List[str] = []
    prev_vowel: Optional[str] = None      # vowel of the previous letter, '' = none, None = word start
    for n, (letter, marks) in enumerate(clusters):
        vowels = [m for m in marks if m in _VOWEL_SIGNS]
        dagesh = _DAGESH in marks
        nxt = clusters[n + 1][0] if n + 1 < len(clusters) else ""
        if letter == "ו" and prev_vowel == "" and not dagesh and vowels == [_HOLAM]:
            out.append(_HOLAM)                                  # holam male = holam haser
            prev_vowel = _HOLAM
            continue
        if letter == "ו" and prev_vowel == "" and dagesh and not vowels:
            out.append(_QUBUTS)                                 # shureq = qubuts
            prev_vowel = _QUBUTS
            continue
        if letter == "י" and not vowels and not dagesh and (
                prev_vowel == _HIRIQ or (prev_vowel == _QAMATS and nxt == "ו")):
            continue                                            # vowel letter / silent י of -ָיו
        out.append(letter)
        out.extend(m for m in marks if m in ("ׁ", "ׂ"))
        out.extend(_HATAF_TO_SHEWA.get(v, v) for v in vowels)
        prev_vowel = vowels[-1] if vowels else ""
    return "".join(out)


# ---------------------------------------------------------------------------
# OSHB words
# ---------------------------------------------------------------------------

class OshbWord:
    __slots__ = ("text", "cons", "lemma", "morph", "wid", "ordinal", "kind", "key", "lang",
                 "prefixes", "main_code", "proper", "cont", "bare", "pk", "note")

    def __init__(self, text: str, lemma: str, morph: str, wid: str, ordinal: int, kind: str):
        self.text = text
        self.cons = hebrew_consonants(text)
        self.note: Optional[str] = None
        fix = OSHB_LEMMA_CORRECTIONS.get(wid)
        if fix is not None and lemma.strip() == fix[1]:
            self.note = f"OSHB lemma {fix[1]} corrected to {fix[2]}: {fix[3]}"
            lemma = fix[2]
        self.pk = pointed_key(text)
        self.lemma = lemma
        self.morph = morph
        self.wid = wid
        self.ordinal = ordinal          # 1-based position among all <w> of the verse (= MACULA word no.)
        self.kind = kind                # 'w' | 'qere' | 'ketiv'
        self.lang = "arc" if morph.startswith("A") else "heb"
        self.key, self.prefixes, self.main_code = _analyse(lemma, morph, self.lang)
        segs = morph.split("/") if morph else []
        self.proper = any(s.lstrip("HA").startswith("Np") for s in segs)
        self.cont = (lemma or "").rstrip().endswith("+")   # OSHB: name continues in the next word
        self.bare: Optional[str] = None                     # set when OSHB omits a needed augment

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<OshbWord {self.text} {self.lemma} {self.morph} {self.key}>"


def _main_code(seg: str) -> str:
    if not seg:
        return ""
    return seg[:2] if seg[0] in "PT" else seg[:1]


def _lemma_key(raw: str, lang: str) -> Optional[str]:
    raw = raw.strip().rstrip("+").strip()
    m = re.fullmatch(r"(\d+)\s*([a-z]?)", raw)
    if m:
        return f"H{int(m.group(1)):04d}{m.group(2)}"
    if raw in LETTER_KEYS:
        return ("arc:" if lang == "arc" else "") + LETTER_KEYS[raw]
    return None


def _analyse(lemma: str, morph: str, lang: str) -> Tuple[Optional[str], Tuple[str, ...], str]:
    parts = [p for p in (lemma or "").split("/") if p.strip()]
    segs = (morph[1:] if morph else "").split("/")
    if not parts:
        return None, (), ""
    pre, main = parts[:-1], parts[-1]
    codes: List[str] = []
    for i, p in enumerate(pre):
        code = PREFIX_CODES.get(p.strip())
        seg = segs[i] if i < len(segs) else ""
        if code == "P:h" and seg == "Ti":
            code = "P:i"  # OSHB lemma 'd' but morph 'Ti': interrogative הֲ (1 Sam 15:22 הַחֵפֶץ)
        if code:
            codes.append(code)
        if seg == "Rd" and code in ("P:b", "P:k", "P:l"):
            codes.append("P:h")  # article assimilated into the preposition (בָּאָרֶץ)
    main_seg = segs[len(pre)] if len(pre) < len(segs) else ""
    for seg in segs[len(pre) + 1:]:
        if seg.startswith("Sp") and len(seg) >= 5:
            codes.append("S:" + seg[2:5])
    return _lemma_key(main, lang), tuple(codes), _main_code(main_seg)


class OshbCorpus:
    """All OSHB verses: reading words (qere in, ketiv out) and the ketiv words separately."""

    def __init__(self) -> None:
        self.reading: Dict[Tuple[str, int, int], List[OshbWord]] = {}
        self.ketiv: Dict[Tuple[str, int, int], List[OshbWord]] = {}
        self.all_words: Dict[Tuple[str, int, int], List[OshbWord]] = {}
        self.key_freq: Counter = Counter()
        self.key_langs: Dict[str, Counter] = defaultdict(Counter)
        self.key_lang: Dict[str, str] = {}   # language of the words OSHB tags with the lemma
        self.key_codes: Dict[str, Counter] = defaultdict(Counter)
        self.form_cons: Dict[str, Counter] = defaultdict(Counter)
        self.form_pointed: Dict[str, Counter] = defaultdict(Counter)
        self.form_prefixes: Dict[Tuple[str, str, str], Counter] = defaultdict(Counter)
        self.form_morph: Dict[str, Counter] = defaultdict(Counter)   # pointed key -> OSHB morph strings


def _walk_words(el: ET.Element, in_qere: bool) -> Iterator[Tuple[ET.Element, bool]]:
    """<w> elements in document order, flagged when they sit inside a qere <rdg>.
    Alternative-accent readings (<rdg type="x-accent">) hold no <w> and are skipped."""
    for ch in el:
        if ch.tag == _OSIS_NS + "w":
            yield ch, in_qere
        elif ch.tag == _OSIS_NS + "rdg":
            if ch.get("type") == "x-qere":
                yield from _walk_words(ch, True)
        else:
            yield from _walk_words(ch, in_qere)


def _parse_book(path: Path, corpus: OshbCorpus) -> None:
    book = path.stem
    root = ET.parse(path).getroot()
    for verse in root.iter(_OSIS_NS + "verse"):
        osis = verse.get("osisID") or ""
        bits = osis.split(".")
        if len(bits) != 3:
            continue
        ref = (book, int(bits[1]), int(bits[2]))
        reading: List[OshbWord] = []
        ketiv: List[OshbWord] = []
        allw: List[OshbWord] = []
        for el, in_qere in _walk_words(verse, False):
            kind = "ketiv" if el.get("type") == "x-ketiv" else ("qere" if in_qere else "w")
            text = "".join(el.itertext())
            w = OshbWord(text, el.get("lemma") or "", el.get("morph") or "", el.get("id") or "",
                         len(allw) + 1, kind)
            allw.append(w)
            (ketiv if kind == "ketiv" else reading).append(w)
        corpus.reading[ref] = reading
        corpus.ketiv[ref] = ketiv
        corpus.all_words[ref] = allw


@lru_cache(maxsize=1)
def oshb_corpus() -> OshbCorpus:
    d = oshb_wlc_dir()
    if d is None:
        raise FileNotFoundError("OSHB MorphHB wlc/*.xml not found (OT_OSHB_MorphHB)")
    corpus = OshbCorpus()
    for book in OSHB_BOOK.values():
        p = d / f"{book}.xml"
        if p.exists():
            _parse_book(p, corpus)
    # OSHB occasionally gives a bare Strong's number where BDB distinguishes homographs
    # (7451 for 7451a/b/c): such a word has no single lemma; resolved per token or left untagged.
    _entries, aug = _lexical_index()
    seen: Dict[str, bool] = {}
    for words in corpus.all_words.values():
        for w in words:
            if not w.key or w.key.startswith("arc:") or w.key in LETTER_KEYS.values():
                continue
            if w.key not in seen:
                code = _aug_code(w.key)
                seen[w.key] = code not in aug and any(a[:-1] == code and a[-1].isalpha() for a in aug)
            if seen[w.key]:
                w.bare, w.key = w.key, None
    for words in corpus.all_words.values():
        for w in words:
            if w.morph:
                corpus.form_morph[w.pk][w.morph] += 1
            if not w.key:
                continue
            corpus.key_freq[w.key] += 1
            corpus.key_langs[w.key][w.lang] += 1
            corpus.key_codes[w.key][w.main_code] += 1
            corpus.form_cons[w.cons][w.key] += 1
            corpus.form_pointed[w.pk][w.key] += 1
            corpus.form_prefixes[("c", w.cons, w.key)][w.prefixes] += 1
            corpus.form_prefixes[("p", w.pk, w.key)][w.prefixes] += 1
    corpus.key_lang = {k: c.most_common(1)[0][0] for k, c in corpus.key_langs.items()}
    return corpus


# ---------------------------------------------------------------------------
# Lexicon (OSHB lexical index + BDB)
# ---------------------------------------------------------------------------

class _LiEntry:
    __slots__ = ("id", "lang", "w", "xlit", "pos", "defn", "bdb", "strong", "aug", "etype", "eroot", "etext")


@lru_cache(maxsize=1)
def _lexical_index() -> Tuple[Dict[str, _LiEntry], Dict[str, str]]:
    d = oshb_lexicon_dir()
    if d is None:
        raise FileNotFoundError("OSHB Hebrew Lexicon not found (OT_OSHB_HebrewLexicon)")
    entries: Dict[str, _LiEntry] = {}
    root = ET.parse(d / "LexicalIndex.xml").getroot()
    for part in root.findall(_LEX_NS + "part"):
        plang = part.get(_XML_LANG) or "heb"
        for e in part.findall(_LEX_NS + "entry"):
            r = _LiEntry()
            r.id = e.get("id") or ""
            r.lang = "arc" if plang == "arc" else "heb"
            w = e.find(_LEX_NS + "w")
            r.w = (w.text or "") if w is not None else ""
            r.xlit = (w.get("xlit") or "") if w is not None else ""
            pos = e.find(_LEX_NS + "pos")
            r.pos = (pos.text or "").strip() if pos is not None else ""
            df = e.find(_LEX_NS + "def")
            r.defn = (df.text or "").strip() if df is not None else ""
            x = e.find(_LEX_NS + "xref")
            r.bdb = (x.get("bdb") or "") if x is not None else ""
            r.strong = (x.get("strong") or "") if x is not None else ""
            r.aug = (x.get("aug") or "") if x is not None else ""
            et = e.find(_LEX_NS + "etym")
            r.etype = (et.get("type") or "") if et is not None else ""
            r.eroot = (et.get("root") or "") if et is not None else ""
            r.etext = ((et.text or "").strip()) if et is not None else ""
            entries[r.id] = r
    aug: Dict[str, str] = {}
    for w in ET.parse(d / "AugIndex.xml").getroot().iter(_LEX_NS + "w"):
        a = (w.get("aug") or "").strip()
        if a and w.text:
            aug[a] = w.text.strip()
    return entries, aug


class _BdbEntry:
    __slots__ = ("id", "type", "mod", "defn", "section", "head", "lang")


@lru_cache(maxsize=1)
def _bdb_index() -> Tuple[Dict[str, _BdbEntry], Dict[str, List[str]]]:
    """BrownDriverBriggs.xml: entry id -> entry (type, homograph number ``mod``, first <def>, the
    <section> it stands in, consonants of its heading word, part language); and section id -> the
    ids of its root-type entries.  In BDB's Hebrew part a section is a root with the words BDB
    derives from it (plus words merely filed there alphabetically); Aramaic sections group several
    roots under one root-type entry, so they are not used as families."""
    d = oshb_lexicon_dir()
    entries: Dict[str, _BdbEntry] = {}
    roots: Dict[str, List[str]] = defaultdict(list)
    if d is None or not (d / "BrownDriverBriggs.xml").exists():
        return entries, {}
    root = ET.parse(d / "BrownDriverBriggs.xml").getroot()

    def add(e: ET.Element, section: str, lang: str) -> None:
        b = _BdbEntry()
        b.id = e.get("id") or ""
        b.type = e.get("type") or ""
        b.mod = e.get("mod") or ""
        df = e.find(".//" + _LEX_NS + "def")
        b.defn = " ".join("".join(df.itertext()).split()) if df is not None else ""
        w = e.find(_LEX_NS + "w")
        b.head = hebrew_consonants((w.text or "") if w is not None else "")
        b.section = section
        b.lang = lang
        entries[b.id] = b
        if b.type == "root" and section:
            roots[section].append(b.id)

    for part in root.findall(_LEX_NS + "part"):
        lang = "arc" if part.get(_XML_LANG) == "arc" else "heb"
        for sec in part.iter(_LEX_NS + "section"):
            for e in sec.iter(_LEX_NS + "entry"):
                add(e, sec.get("id") or "", lang)
    for e in root.iter(_LEX_NS + "entry"):
        if (e.get("id") or "") not in entries:
            add(e, "", "heb")
    return entries, dict(roots)


def _bdb_entries() -> Dict[str, Tuple[str, str, str]]:
    """BDB entry id -> (type, mod, first <def> text)."""
    return {k: (b.type, b.mod, b.defn) for k, b in _bdb_index()[0].items()}


@lru_cache(maxsize=1)
def _tbesh_rows() -> Dict[str, List[Tuple[str, str, str, str, str]]]:
    """STEPBible TBESH, columns 1-7 only (column 8 'Meaning' is never read): eStrong (H0001,
    H1254a -- OSHB's own augmented numbers) -> [(relation, Hebrew, Gloss, dStrong, morph)] in file
    order, where the relation is what follows '=' in the dStrong column ('', 'a Meaning of', 'a Part
    of' ...), dStrong what precedes it (H8289G: one row per sense or bearer) and morph column 6
    ('N:N-M-P' a man's name, 'N:N--L' a place, 'H:N-M' a common noun)."""
    p = tbesh_path()
    out: Dict[str, List[Tuple[str, str, str, str, str]]] = defaultdict(list)
    if p is None:
        return {}
    with _open_text(p) as fh:
        for line in fh:
            if not line.startswith("H"):
                continue
            cols = line.rstrip("\n").split("\t", 7)[:7]  # columns 1-7 only
            if len(cols) < 7 or not re.fullmatch(r"H\d{4}[a-zA-Z]?", cols[0].strip()):
                continue
            dstrong, _eq, rel = cols[1].partition("=")
            out[cols[0].strip()].append((rel.strip(), cols[3].strip(), cols[6].strip(), dstrong.strip(),
                                         cols[5].strip()))
    return dict(out)


def _tbesh_glosses() -> Dict[str, str]:
    """STEPBible TBESH: eStrong (H0001) -> Gloss (column 7) of its first row."""
    return {k: next((r[2] for r in rows if r[2]), "") for k, rows in _tbesh_rows().items()}


# STEPBible book abbreviations (TIPNR references) -> OSHB book codes
_STEP_TO_OSHB: Dict[str, str] = {
    "Gen": "Gen", "Exo": "Exod", "Lev": "Lev", "Num": "Num", "Deu": "Deut", "Jos": "Josh", "Jdg": "Judg",
    "Rut": "Ruth", "1Sa": "1Sam", "2Sa": "2Sam", "1Ki": "1Kgs", "2Ki": "2Kgs", "1Ch": "1Chr", "2Ch": "2Chr",
    "Ezr": "Ezra", "Neh": "Neh", "Est": "Esth", "Job": "Job", "Psa": "Ps", "Pro": "Prov", "Ecc": "Eccl",
    "Sng": "Song", "Isa": "Isa", "Jer": "Jer", "Lam": "Lam", "Ezk": "Ezek", "Dan": "Dan", "Hos": "Hos",
    "Jol": "Joel", "Amo": "Amos", "Oba": "Obad", "Jon": "Jonah", "Mic": "Mic", "Nam": "Nah", "Hab": "Hab",
    "Zep": "Zeph", "Hag": "Hag", "Zec": "Zech", "Mal": "Mal",
}
_STEP_REF = re.compile(r"\b(\d?[A-Z][a-z]{1,2})\.(\d+)\.(\d+)")
_TIPNR_DSTRONG = re.compile(r"(H\d{4}[A-Za-z]?)«")

Verse = Tuple[str, int, int]


@lru_cache(maxsize=1)
def _tipnr_refs() -> Dict[str, frozenset]:
    """STEPBible TIPNR: Hebrew dStrong (H8289I) -> the verses (OSHB book code, chapter, verse;
    English numbering) its sub-records ('– Named', '– Spelled' ...) list for that bearer.  Only the
    dStrong and reference columns are read."""
    p = tipnr_path()
    out: Dict[str, set] = defaultdict(set)
    if p is None:
        return {}
    with _open_text(p) as fh:
        for line in fh:
            if not line.startswith("–") or line.startswith("– Total"):
                continue
            cols = line.split("\t")
            if len(cols) < 5 or "«" not in cols[2]:
                continue
            refs = {(_STEP_TO_OSHB[b], int(c), int(v)) for b, c, v in _STEP_REF.findall(cols[4])
                    if b in _STEP_TO_OSHB}
            for ds in _TIPNR_DSTRONG.findall(cols[2]):
                out[ds].update(refs)
    return {k: frozenset(v) for k, v in out.items()}


@lru_cache(maxsize=1)
def _key_verses() -> Dict[str, frozenset]:
    """OSHB lemma key -> the verses (book, chapter, verse) where a reading word (qere in, ketiv
    out, as the Studio prints the text) carries it."""
    out: Dict[str, set] = defaultdict(set)
    for ref, words in oshb_corpus().reading.items():
        for w in words:
            if w.key:
                out[w.key].add(ref)
    return {k: frozenset(v) for k, v in out.items()}


def _bearer_by_occurrence(key: str, pool: Sequence[Tuple[str, str, bool]], want: str) -> Optional[str]:
    """Among TBESH name rows ``(gloss, dStrong, is_core)`` with different glosses, the gloss of
    the bearer(s) TIPNR places in most of the lemma's OSHB verses (שָׁרוֹן: 'Sharon' 6, 'Lasharon'
    1).  Rows are scored by (verses shared with the lemma's occurrences, references in a chapter
    where the lemma occurs, all references) -- TIPNR counts in English numbering, so the later
    figures catch renumbered chapters; ties go to the lexical index's name, then to a row of the
    word itself (not 'a Name of' another), then to TBESH's order.  None without TIPNR evidence."""
    groups = [_strip_qualifier(g).lower() for g, _d, _c in pool]
    if len(set(groups)) < 2:
        return None
    refs = _tipnr_refs()
    if not refs:
        return None
    verses = _key_verses().get(key, frozenset())
    chapters = {(b, c) for b, c, _v in verses}
    score: Dict[str, List[int]] = {}
    for (g, ds, is_core), grp in zip(pool, groups):
        r = refs.get(ds, frozenset())
        s = score.setdefault(grp, [0, 0, 0, 0])
        s[0] += len(r & verses)
        s[1] += sum(1 for b, c, _v in r if (b, c) in chapters)
        s[2] += len(r)
        s[3] = max(s[3], int(is_core))
    best = max(score, key=lambda grp: (score[grp][:3], grp == want, score[grp][3], -groups.index(grp)))
    if not any(score[best][:3]):
        return None
    return _strip_qualifier(next(g for (g, _d, _c), grp in zip(pool, groups) if grp == best))


_BRACKETED = re.compile(r"\[[^\]]*\]|\([^)]*\)")


def _strip_qualifier(gloss: str) -> str:
    """'Hall (of pillars)' -> 'Hall', '(Mount) Tabor' -> 'Tabor' (unchanged if nothing is left)."""
    return re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", " ", gloss)).strip(" -") or gloss


_DEF_RESIDUE = (
    # reference residue the lexical index leaves in a <def> once its cross-reference markup is gone
    re.compile(r"\s*\((?:from the margin|by correction for[^)]*|including the article|[^()]*\d+:\d+[^()]*)\)"),
    re.compile(r"[.;,]?\s*\b(?:Compare|See also|See)\s*$"),
)


def _clean_def(defn: str, is_name: bool = False) -> str:
    """A lexical-index <def> without reference residue ('Huram. Compare' -> 'Huram', 'Jair(from
    the margin)' -> 'Jair', 'Micaiah (2 Chronicles 18:8)' -> 'Micaiah', 'Iddo (from the margin)
    See' -> 'Iddo'); a name also loses BDB's transliteration marks ('Rôsh' -> 'Rosh')."""
    t = defn or ""
    for _round in range(2):
        for rx in _DEF_RESIDUE:
            t = rx.sub("", t)
    t = re.sub(r"\s+", " ", t).strip()
    if is_name:
        t = unicodedata.normalize("NFC", "".join(ch for ch in unicodedata.normalize("NFD", t)
                                                 if not unicodedata.combining(ch)))
    return t or (defn or "").strip()


def _fix_typos(gloss: str) -> str:
    return re.sub(r"[A-Za-z]+", lambda m: GLOSS_TYPOS.get(m.group(0), m.group(0)), gloss)


def _tbesh_gloss(key: str, headword: str, is_name: bool = False, name_rows: bool = True,
                 li_def: str = "", proper: bool = False) -> Tuple[str, bool]:
    """(TBESH's brief gloss for an OSHB lemma, or '' when TBESH cannot be matched unambiguously;
    whether TIPNR's references chose among the bearers).

    The TBESH eStrong number must be the OSHB lemma key itself (TBESH's extended numbers are
    OSHB's augmented Strong's numbers) and the TBESH Hebrew must have the headword's consonants.
    Each row's gloss is cut at ':' (TBESH writes sub-senses as 'word: thing').  Rows that are only
    part of a name or a combination are ignored; rows for a use inside a name ('a Name of') count
    only when there is no other row (אֱלֹהִים 'God').  Any other word prefers lower-case glosses
    (מֶלֶךְ 'king', not "King's" of the King's Valley; סוּס 'horse', not 'Horse (Gate)'), then the
    commonest one, the first row on a tie (דָּבָר 'word', הָלַךְ 'to go').

    A name (``is_name``; ``li_def`` = the lexical index's cleaned name) skips a gloss in backticks
    (a translation of the name: שִׁילֹה '`tribute`') and a lower-case common-noun row when the index
    gives a name (רֹאשׁ 'prince' for the people Rosh).  Several bearers with different glosses: the
    one with most of the lemma's occurrences by TIPNR (``_bearer_by_occurrence``; a proper name
    ``proper`` also counts its 'a Name of' rows: חוּרָם 'Hiram' for the king of Tyre), else the one
    the lexical index names (יִפְתָּח 'Jephthah', not the town 'Iphtah'), else TBESH's first."""
    bare = key.split(":", 1)[1] if key.startswith("arc:") else key
    rows = _tbesh_rows().get(bare)
    cons = hebrew_consonants(headword)
    if not rows or not cons:
        return "", False
    li_is_name = li_def[:1].isupper()
    core: List[Tuple[str, str]] = []
    named: List[Tuple[str, str]] = []
    for rel, heb, gloss, dstrong, morph in rows:
        if rel.startswith(("a Part of", "combination")):
            continue
        if not any(hebrew_consonants(alt) == cons for alt in re.split(r"[,;/]", heb)):
            continue
        raw = gloss.split(":", 1)[0].strip()
        if is_name and (raw.startswith("`") or (li_is_name and morph.startswith("H:") and raw[:1].islower())):
            continue
        base = raw.strip("`").strip()
        if base:
            (named if rel.startswith("a Name of") else core).append((base, dstrong))
    if is_name:
        want = _strip_qualifier(li_def).lower()
        pool = [(g, d, True) for g, d in core] + ([(g, d, False) for g, d in named] if proper else [])
        by_occurrence = _bearer_by_occurrence(key, pool, want)
        if by_occurrence:
            return by_occurrence, True
        if core:
            named_row = next((g for g, _d in core if _strip_qualifier(g).lower() == want), None) if want else None
            return _strip_qualifier(named_row or core[0][0]), False
        if proper and named and not li_is_name:
            # the lexical index translates the name (יֹשֵׁב בַּשֶּׁבֶת 'that sat in the seat'):
            # TBESH's name of the bearer ('Josheb-basshebeth')
            return _strip_qualifier(named[0][0]), False
        return "", False
    picked = [g for g, _d in core] or ([g for g, _d in named] if name_rows else [])
    if not picked:
        return "", False
    lower = [g for g in picked if g[:1].islower()]
    picked = lower or picked
    # group 'Hall (of pillars)' with 'Hall (of Justice)', 'lips' stays apart from 'lip'
    group = [_strip_qualifier(g).lower() for g in picked]
    counts = Counter(group)
    best = max(counts, key=lambda g: (counts[g], -group.index(g)))
    members = [p for p, g in zip(picked, group) if g == best]
    return (members[0] if len(set(members)) == 1 else _strip_qualifier(members[0])), False


# where a display gloss came from (``_display_gloss``)
GLOSS_TBESH, GLOSS_TBESH_TIPNR, GLOSS_LEX, GLOSS_FIXED = "tbesh", "tbesh+tipnr", "lex", "fixed"


def _display_gloss(key: str, li: Optional["_LiEntry"], headword: str) -> Tuple[str, str]:
    """(gloss, where it came from: ``GLOSS_FIXED`` / ``GLOSS_TBESH`` / ``GLOSS_TBESH_TIPNR`` /
    ``GLOSS_LEX`` / '').  A ``GLOSS_OVERRIDES`` entry first; then TBESH's brief gloss when it
    matches the lemma unambiguously and says more than a bracketed placeholder ('[Obj.]',
    '[the]'); else the lexical index <def> (BDB's first sense) without reference residue; else, as
    a last resort, TBESH's gloss for the bare Strong's number."""
    if key in GLOSS_OVERRIDES:
        return GLOSS_OVERRIDES[key][0], GLOSS_FIXED
    names = ("Np", "Ng", "Ag")
    pos = li.pos if li is not None else ""
    is_name = pos in names
    li_def = _clean_def(li.defn, is_name) if li is not None else ""
    # a name or gentilic that TBESH glosses only as a use of another name (gentilic לֵוִי "Levite"
    # -> 'Levi') keeps the lexical index's gloss; a proper name (Np) may take TBESH's name of the
    # bearer it refers to (חוּרָם 'Hiram')
    tb, by_tipnr = _tbesh_gloss(key, headword, is_name, name_rows=not is_name, li_def=li_def,
                                proper=pos == "Np")
    if tb and re.search("[A-Za-z]", _BRACKETED.sub("", tb)):
        # TBESH marks supplied letters in square brackets: '[Ben]jaminite' -> 'Benjaminite'
        return _fix_typos(re.sub(r"\[([^\]]*)\]", r"\1", tb)), GLOSS_TBESH_TIPNR if by_tipnr else GLOSS_TBESH
    if li_def:
        return li_def, GLOSS_LEX
    if tb:
        return _fix_typos(tb), GLOSS_TBESH
    bare = key.split(":", 1)[1] if key.startswith("arc:") else key
    m = re.fullmatch(r"H(\d+)[a-z]?", bare)
    if m:
        tg = _tbesh_glosses().get(f"H{int(m.group(1)):04d}")
        if tg:
            return _fix_typos(tg), GLOSS_TBESH
    return "", ""


def _aug_code(key: str) -> str:
    """'H1254a' -> '1254a', 'H0430' -> '430', 'H9005' / 'arc:H9005' -> 'l'."""
    bare = key.split(":", 1)[1] if key.startswith("arc:") else key
    for letter, k in LETTER_KEYS.items():
        if bare == k:
            return letter
    m = re.fullmatch(r"H(\d+)([a-z]?)", bare)
    return f"{int(m.group(1))}{m.group(2)}" if m else bare


def _arc_letter_entry(letter: str) -> Optional[str]:
    """The Aramaic-part lexical-index entry for a prefix letter (ב, ל, כ, ו), if any."""
    entries, _aug = _lexical_index()
    cons = _LETTER_CONSONANT.get(letter)
    for e in entries.values():
        if e.lang == "arc" and not e.strong and hebrew_consonants(e.w) == cons:
            return e.id
    return None


def _entry_for_key(key: str) -> Optional[_LiEntry]:
    entries, aug = _lexical_index()
    code = _aug_code(key)
    if key.startswith("arc:"):
        eid = _arc_letter_entry(code)
        if eid:
            return entries.get(eid)
    eid = aug.get(code)
    return entries.get(eid) if eid else None


_POS_MAP = {
    "N": "N", "Np": "PROPN", "Ng": "PROPN", "V": "V", "A": "ADJ", "Ag": "ADJ", "Ao": "NUM",
    "D": "ADV", "R": "PREP", "R C": "PREP", "C": "CONJ", "C?": "CONJ", "Td": "ART", "Tj": "INTERJ",
    "P": "PRON", "Pp": "PRON", "Pd": "PRON", "Pi": "PRON", "Pf": "PRON", "Pr": "PRON",
}
_MORPH_POS = {"N": "N", "V": "V", "A": "ADJ", "D": "ADV", "R": "PREP", "C": "CONJ", "Td": "ART",
              "Tj": "INTERJ", "Pp": "PRON", "Pd": "PRON", "Pi": "PRON", "Pf": "PRON", "Pr": "PRON"}


def _pos_for(li: Optional[_LiEntry], codes: Counter) -> str:
    if li is not None and li.pos in ("Np", "Ng") and codes:
        top = codes.most_common(1)[0][0]
        if top in FUNCTION_MORPH_CODES and top in _MORPH_POS and codes[top] / sum(codes.values()) >= 0.9:
            # the lexical index calls it a name, OSHB's morphology never treats it as a noun
            # (מוּל "in front of": preposition in all 36 occurrences)
            return _MORPH_POS[top]
    if li is not None and li.pos:
        if li.pos in _POS_MAP:
            return _POS_MAP[li.pos]
        if li.pos.startswith("T"):
            return "PART"
    if codes:
        top = codes.most_common(1)[0][0]
        if top in _MORPH_POS:
            return _MORPH_POS[top]
        if top.startswith("T"):
            return "PART"
        if top.startswith("P"):
            return "PRON"
    return "PART"


def _family_head(entry_id: str) -> str:
    entries, _aug = _lexical_index()
    seen = {entry_id}
    cur = entry_id
    while True:
        e = entries.get(cur)
        if e is None or e.etype != "sub" or not e.etext:
            return cur
        nxt = e.etext.split(",")[0].strip()
        if nxt in seen or nxt not in entries:
            return cur
        seen.add(nxt)
        cur = nxt


@lru_cache(maxsize=1)
def _li_by_bdb() -> Dict[str, List[str]]:
    """BDB entry id -> the lexical-index entries that point at it."""
    entries, _aug = _lexical_index()
    out: Dict[str, List[str]] = defaultdict(list)
    for e in entries.values():
        if e.bdb:
            out[e.bdb].append(e.id)
    return dict(out)


def _bare_letters(cons: str) -> str:
    """Consonants without the vowel letters ו / י and a final ה (אוּלָם ~ אלם, הָלְאָה ~ הלא, אֵל ~ אלה)."""
    cons = cons[:-1] if cons.endswith("ה") else cons
    return cons.translate(_MATRES)


def _root_letters_in(root_cons: str, word_cons: str) -> bool:
    """The root's letters, without ו / י and a final ה, occur in order in the word (two at least)."""
    letters = root_cons[:-1] if root_cons.endswith("ה") else root_cons
    letters = letters.translate(_MATRES)
    if len(letters) < 2:
        return False
    it = iter(word_cons)
    return all(ch in it for ch in letters)


@lru_cache(maxsize=1)
def _root_plan() -> Tuple[Dict[str, Tuple[str, str]], Dict[str, Tuple[str, str]], Dict[str, str]]:
    """Root families where the lexical index and BDB's own arrangement disagree (BDB wins):

    * redirect -- a lexical-index root head whose BDB reference is BDB's root entry of other
      letters joins that root: אָחַד (Ezek 21:21) is filed by BDB under חָדַד "be sharp" (h.aq.aa).
    * keys -- root key and label per root head.  Heads with the same letters and BDB homograph
      number are one family only when they stand in one BDB unit (a Hebrew <section>, an Aramaic
      entry); otherwise each gets its BDB id (``heb:ירא@j.df.aa`` "fear" / ``@j.dg.aa`` "shoot";
      Aramaic נְהַר "river" ``arc:נהר@xn.ad.ac`` / נְהִיר "light" ``@xn.ad.ad``).  BDB's homograph
      number is kept only when it numbers a root heading with these letters: "I. אֵל" (these),
      "I. אֵת", "III. אוּלָם" number the words, not roots אלה / אות / אלם.
    * selfs -- a head that BDB lists apart from a BDB root entry of the same letters is no member
      of that root: תִּרְגֵּם (BDB "vb. quadril.", w.bq.ah; not רָגַם "stone"), כרבל (k.cx.ah; not כֶּבֶל);
      and a word that is itself BDB's heading, while the index gives it a root of other letters,
      heads its own family: אֵשׁ "fire" (BDB a.gb.aa; the index says אנש) with אִשֶּׁה, אֶשָּׁה.
    """
    entries, _aug = _lexical_index()
    bdbx, _roots = _bdb_index()
    by_bdb = _li_by_bdb()
    redirect: Dict[str, Tuple[str, str]] = {}
    heads = [e for e in entries.values() if e.eroot and _family_head(e.id) == e.id]
    for e in heads:
        b = bdbx.get(e.bdb)
        if b is None or b.type != "root" or not b.head or b.head == hebrew_consonants(e.eroot):
            continue
        for cid in by_bdb.get(e.bdb, []):
            c = entries[cid]
            if cid != e.id and c.eroot and hebrew_consonants(c.eroot) == b.head:
                redirect[e.id] = (_family_head(cid), f"BDB files {strip_accents(e.w)} under the root "
                                                     f"{hyphenate_root(c.eroot)} ({e.bdb})")
                break
    groups: Dict[Tuple[str, str, str], Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    keys: Dict[str, Tuple[str, str]] = {}
    selfs: Dict[str, str] = {}
    for e in heads:
        if e.id in redirect:
            continue
        b = bdbx.get(e.bdb)
        if b is not None and b.lang == "heb" and b.type == "root" and b.head and e.strong \
                and _bare_letters(b.head) != _bare_letters(hebrew_consonants(e.eroot)):
            # BDB heads the family with this very word and gives it no root with the index's
            # letters (אֵשׁ "fire": BDB heading אֵשׁ, the index says root אנש): the word heads its family
            selfs[e.id] = (f"BDB heads the family with {strip_accents(e.w)} itself ({e.bdb}); the lexical "
                           f"index's root {hyphenate_root(e.eroot)} is not BDB's")
            continue
        if b is not None and b.mod and b.head != hebrew_consonants(e.eroot):
            # BDB's number belongs to the heading word ("I. אֵל" these), not to a root with the
            # lexical index's letters: no number, and the family stays apart by its BDB id
            keys[e.id] = (f"{e.lang}:{e.eroot}@{e.bdb}", hyphenate_root(e.eroot))
            continue
        mod = b.mod if b is not None else ""
        unit = (b.section or e.bdb) if b is not None and b.lang == "heb" else (e.bdb or e.id)
        groups[(e.lang, e.eroot, mod)][unit].append(e.id)
    for (lang, eroot, mod), units in groups.items():
        base = f"{lang}:{eroot}" + (f".{mod}" if mod else "")
        label = hyphenate_root(eroot) + (f" {mod}" if mod else "")

        def is_root(i: str) -> bool:
            """A BDB root heading with these very letters."""
            b = bdbx.get(entries[i].bdb)
            return b is not None and b.type == "root" and b.head == hebrew_consonants(entries[i].eroot)

        def is_heading(i: str) -> bool:
            b = bdbx.get(entries[i].bdb)
            return b is not None and b.type == "root"

        rootish = {u for u, ids in units.items() if any(is_root(i) for i in ids)}
        live = units
        if rootish and len(units) > 1:
            # a plain BDB word entry outside the root's section is no member of that root
            apart = {u for u, ids in units.items() if not any(is_heading(i) for i in ids)}
            for u in apart:
                for i in units[u]:
                    selfs[i] = (f"BDB lists {strip_accents(entries[i].w)} apart ({entries[i].bdb}), "
                                f"not under the root {label}")
            live = {u: ids for u, ids in units.items() if u not in apart}
        for u, ids in live.items():
            rep = next((entries[i].bdb for i in ids if is_heading(i)), min(entries[i].bdb or i for i in ids))
            for i in ids:
                keys[i] = (base + (f"@{rep}" if len(live) > 1 else ""), label)
    return redirect, keys, selfs


def _bdb_section_head(li: _LiEntry, head: _LiEntry) -> Optional[Tuple[Optional[str], str]]:
    """A lexical-index link into another BDB section: BDB files the word elsewhere.  It joins the
    root of its own BDB section when that root's letters are in the word (אֲרִיאֵל "lion of God" under
    I אָרָה with אֲרִי "lion", not II ארה "hearth"; אֶשְׁעָן under שָׁעַן), else it is its own family
    (שָׁיָה, Deut 32:18, filed alphabetically; not under נָשָׁה).  None when BDB agrees."""
    bdbx, roots = _bdb_index()
    b, hb = bdbx.get(li.bdb), bdbx.get(head.bdb)
    if b is None or hb is None or b.lang != "heb" or hb.lang != "heb" or not b.section \
            or not hb.section or b.section == hb.section:
        return None
    entries, _aug = _lexical_index()
    word = strip_accents(li.w)
    sec_roots = roots.get(b.section, [])
    if len(sec_roots) == 1 and _root_letters_in(bdbx[sec_roots[0]].head, hebrew_consonants(li.w)):
        for cid in _li_by_bdb().get(sec_roots[0], []):
            c = entries[cid]
            if c.eroot and hebrew_consonants(c.eroot) == bdbx[sec_roots[0]].head:
                target = _family_head(cid)
                label = _root_plan()[1].get(target, ("", hyphenate_root(c.eroot)))[1]
                return target, (f"BDB files {word} under {label} ({b.section}); "
                                f"the lexical index links it to {strip_accents(head.w)}")
    return None, f"BDB files {word} apart ({li.bdb}); the lexical index links it to {strip_accents(head.w)}"


def _key_for_entry(e: _LiEntry) -> Optional[str]:
    if not e.strong or not re.fullmatch(r"\d+", e.strong):
        if e.strong in LETTER_KEYS:
            return LETTER_KEYS[e.strong]
        return None
    return f"H{int(e.strong):04d}{e.aug or ''}"


def hyphenate_root(root: str) -> str:
    """'ראשׁ' -> 'ר-א-שׁ' (a letter keeps its shin/sin dot)."""
    units: List[str] = []
    for ch in root:
        if "\u05B0" <= ch <= "\u05C7" and units:
            units[-1] += ch
        elif "א" <= ch <= "ת":
            units.append(ch)
    return "-".join(units)


def _head_lemma_key(head: _LiEntry) -> Optional[str]:
    hkey = _key_for_entry(head)
    if hkey and head.lang == "arc" and hkey in LETTER_KEYS.values():
        hkey = "arc:" + hkey
    return hkey


def _resolve_head(li: _LiEntry) -> Tuple[Optional[str], List[str]]:
    """The family head of a lexical-index entry (None: its own family) and notes on where BDB's
    placement overrode the lexical index's links."""
    entries, _aug = _lexical_index()
    redirect, _keys, selfs = _root_plan()
    notes: List[str] = []
    head_id: Optional[str] = _family_head(li.id)
    if head_id != li.id and head_id in entries:
        moved = _bdb_section_head(li, entries[head_id])
        if moved is not None:
            head_id, note = moved
            notes.append(note)
    if head_id in redirect:
        head_id, note = redirect[head_id]
        notes.append(note)
    if head_id in selfs:
        notes.append(selfs[head_id])
        if head_id == li.id:
            return None, notes
    return head_id, notes


def _root_info(key: str, li: Optional[_LiEntry], lemma_lang: str, headword: str
               ) -> Tuple[str, str, str, str, Optional[str], List[str]]:
    """(root_key, root_label, root_source, formula, family head entry id or None, notes).
    The root gloss is decided per family afterwards (``_family_glosses``)."""
    self_family = (f"{lemma_lang}:{key}" if not key.startswith("arc:") else key, headword, ROOT_SRC_SELF, headword,
                   None, [])
    if li is None:
        return self_family
    entries, _aug = _lexical_index()
    head_id, notes = _resolve_head(li)
    head = entries.get(head_id) if head_id else None
    if head is None:
        return self_family[:5] + (notes,)
    _redirect, keys, selfs = _root_plan()
    if head.eroot and head_id not in selfs:
        root_key, label = keys.get(head_id, (f"{head.lang}:{head.eroot}", hyphenate_root(head.eroot)))
        formula = label if head_id == li.id and hebrew_consonants(headword) == hebrew_consonants(head.eroot) \
            else f"{label} → {headword}"
        return root_key, label, ROOT_SRC_BDB, formula, head_id, notes
    if head_id != li.id:
        hkey = _head_lemma_key(head)
        if hkey:
            hw = strip_accents(head.w)
            rk = hkey if hkey.startswith("arc:") else f"{head.lang}:{hkey}"
            return rk, hw, ROOT_SRC_BDB, f"{hw} → {headword}", head_id, notes
    return self_family[:4] + (head_id, notes)


_CONTENT_LEX_POS = frozenset({"N", "Np", "Ng", "V", "A", "Ag", "Ao"})


def _is_function(key: str, codes: Counter) -> bool:
    """Prefix-letter lemmas, the particles of ``FUNCTION_PARTICLE_KEYS``, the pronouns of
    ``FUNCTION_LEX_POS``, and lemmas that OSHB tags as C/R/Td/To/Tr/Tn/Pp/Pr in at least half of
    their occurrences -- 90 % of at least ``FUNCTION_MORPH_MIN`` occurrences when the lexical index
    calls the lemma a noun, name, verb or adjective (so תַּחַת stays a preposition but the names
    לֹא עַמִּי / אַל תַּשְׁחֵת and the nouns כִּי "branding", אוֹ "desire" stay content)."""
    bare = key.split(":", 1)[1] if key.startswith("arc:") else key
    if bare in LETTER_KEYS.values() or key in FUNCTION_PARTICLE_KEYS:
        return True
    li = _entry_for_key(key)
    if li is not None and li.pos in FUNCTION_LEX_POS:
        return True
    total = sum(codes.values())
    if not total:
        return False
    n_function = sum(n for c, n in codes.items() if c in FUNCTION_MORPH_CODES)
    if li is not None and li.pos in _CONTENT_LEX_POS:
        return n_function >= FUNCTION_MORPH_MIN and n_function / total >= 0.9
    return n_function / total >= 0.5


@lru_cache(maxsize=1)
def _function_keys() -> frozenset:
    corpus = oshb_corpus()
    return frozenset(k for k in corpus.key_freq if _is_function(k, corpus.key_codes.get(k, Counter())))


def function_word_keys() -> List[str]:
    """The lemma keys tagged is_content=False (derived from OSHB morphology, see module doc)."""
    return sorted(_function_keys())


def is_content_key(key: Optional[str]) -> bool:
    return bool(key) and key not in _function_keys()


def _family_glosses(rows: Dict[str, Dict], freq: Counter) -> Dict[str, str]:
    """One root gloss per root key, the same for every member:

    * a family headed by a lemma (הָיָה, בֵּן ...): that lemma's display gloss;
    * a family headed by a bare BDB root: the root's lexical-index <def>, else the gloss of its main
      verb (the most frequent verb member: קדשׁ -> קָדַשׁ), else of its most frequent member, names
      last (דוד -> דּוֹד, not David), else BDB's first <def> for the root (often only a cognate's
      meaning, "√ of foll.; mng. dub.": מלך I "possess, own exclusively", so it comes last);
    * a lemma that is its own family: ''."""
    entries, _aug = _lexical_index()
    members: Dict[str, List[str]] = defaultdict(list)
    for k, r in rows.items():
        members[r["root_key"]].append(k)
    bdbx, _roots = _bdb_index()
    out: Dict[str, str] = {}
    for rk, ks in members.items():
        heads = sorted({rows[k]["head"] for k in ks if rows[k]["head"]})
        if not heads or all(rows[k]["root_source"] == ROOT_SRC_SELF for k in ks):
            out[rk] = ""
            continue
        lemma_heads = [hk for hk in (_head_lemma_key(entries[h]) for h in heads) if hk in rows]
        if lemma_heads:
            best = max(lemma_heads, key=lambda k: (freq[k], k))
            gloss = rows[best]["gloss"]
            if best in GLOSS_OVERRIDES:
                # the corrected gloss adds the senses of words OSHB files under the head by
                # Strong's numbering ('to fly; be weary'); the family's own meaning is the first
                gloss = re.split(r"\s*;\s*", gloss)[0]
            out[rk] = gloss
            continue
        defn = next((_clean_def(entries[h].defn) for h in heads if entries[h].defn), "")
        if defn:
            out[rk] = defn
            continue
        glossed = [k for k in ks if rows[k]["gloss"]]
        verbs = [k for k in glossed if rows[k]["pos"] == "V"]
        pool = verbs or [k for k in glossed if rows[k]["pos"] != "PROPN"] or glossed
        if pool:
            out[rk] = rows[max(pool, key=lambda k: (freq[k], k))]["gloss"]
            continue
        out[rk] = next((bdbx[entries[h].bdb].defn for h in heads if entries[h].bdb in bdbx), "")
    return out


_TBESH_KIND = (("N:N-M-P", "person"), ("N:N-F-P", "person"), ("N:N--PG", "people"), ("N:N--LG", "people"),
               ("N:N--L", "place"))


def _name_kind(key: str) -> str:
    """'person' / 'place' / 'people' from the morph column of the lemma's first TBESH row, else ''."""
    rows = _tbesh_rows().get(key.split(":", 1)[1] if key.startswith("arc:") else key) or []
    morph = rows[0][4] if rows else ""
    return next((kind for prefix, kind in _TBESH_KIND if morph.startswith(prefix)), "")


def _unique_root_labels(rows: Dict[str, Dict], root_glosses: Dict[str, str], freq: Counter) -> Dict[str, str]:
    """Root key -> display label, unique among the families of each language.  Families whose
    label coincides (no BDB homograph number tells them apart: ר-ו-ח "smell" t.bk.aa / ר-ו-ח "be
    wide" t.bl.aa; homograph headwords of one-word families: בָּמָה "high place" / בָּמָה "Bamah")
    get the family gloss in brackets, and where that still coincides the head word, then person /
    place / people (from TBESH), then the lemma key: 'ר-ו-ח (to smell)', 'א-ל-ה (these, אֵלֶּה)',
    'בִּלְהָה (Bilhah, person)', 'קִיר (Kir, H7024a)'.  Labels that are already unique stay as
    they are."""
    members: Dict[str, List[str]] = defaultdict(list)
    for k, r in rows.items():
        members[r["root_key"]].append(k)
    label = {rk: rows[ks[0]]["root_label"] for rk, ks in members.items()}
    top = {rk: max(ks, key=lambda k: (freq[k], k)) for rk, ks in members.items()}
    by_label: Dict[Tuple[str, str], set] = defaultdict(set)
    for rk, ks in members.items():
        for k in ks:
            by_label[(rows[k]["lang"], label[rk])].add(rk)

    def short_gloss(rk: str) -> str:
        g = root_glosses.get(rk) or rows[top[rk]]["gloss"]
        return _strip_qualifier(re.split(r"\s*;\s*", g.strip())[0])[:40].strip()

    levels = (lambda rk: rows[top[rk]]["lemma"], lambda rk: _name_kind(top[rk]), lambda rk: top[rk])
    out: Dict[str, str] = {}
    for (_lang, lab), rks in sorted(by_label.items()):
        if len(rks) < 2:
            continue
        group = sorted(rks)
        parts: Dict[str, List[str]] = {rk: [g for g in (short_gloss(rk),) if g] for rk in group}
        for n, level in enumerate(levels):
            buckets: Dict[Tuple[str, ...], List[str]] = defaultdict(list)
            for rk in group:
                buckets[tuple(parts[rk])].append(rk)
            for same in buckets.values():
                if len(same) < 2:
                    continue
                vals = {rk: level(rk) for rk in same}
                if len(set(vals.values())) < 2 and n < len(levels) - 1:
                    continue        # this level does not tell them apart
                for rk in same:
                    if vals[rk]:
                        parts[rk].append(vals[rk])
        for rk in group:
            out.setdefault(rk, f"{lab} ({', '.join(parts[rk])})")
    return out


@lru_cache(maxsize=1)
def _lexicon() -> Dict[str, LemmaEntry]:
    corpus = oshb_corpus()

    def order(k: str) -> Tuple[int, int, str]:
        bare = k.split(":", 1)[1] if k.startswith("arc:") else k
        m = re.match(r"H(\d+)", bare)
        return (int(m.group(1)) if m else 99999, -corpus.key_freq[k], k)

    rows: Dict[str, Dict] = {}
    for key in sorted(corpus.key_freq, key=order):
        li = _entry_for_key(key)
        codes = corpus.key_codes.get(key, Counter())
        word_lang = "arc" if key.startswith("arc:") else None
        lang = li.lang if li is not None else (word_lang or "heb")
        if word_lang:
            lang = "arc"
        headword = strip_accents(li.w) if li is not None and li.w else ""
        if not headword:
            # no lexical-index entry: the most frequent OSHB spelling of the lemma
            headword = key
        bare = key.split(":", 1)[1] if key.startswith("arc:") else key
        m = re.fullmatch(r"H(\d+)[a-z]?", bare)
        strongs = f"H{int(m.group(1)):04d}" if m and int(m.group(1)) < 9000 else None
        # TBESH rows are matched on the lexical index's headword (TBESH writes מַי, רֹדָן too)
        gloss, gloss_from = _display_gloss(key, li, headword)
        headword = HEADWORD_OVERRIDES.get(key, (headword, ""))[0]
        source = f"{SRC_OSHB}; {SRC_LEX}"
        if gloss_from in (GLOSS_TBESH, GLOSS_TBESH_TIPNR):
            source += f"; gloss {SRC_TBESH_GLOSS}"
        if gloss_from == GLOSS_TBESH_TIPNR:
            source += f", {SRC_TIPNR}"
        if gloss_from == GLOSS_FIXED:
            source += f"; {SRC_GLOSS_FIX}"
        pos = _pos_for(li, codes)
        if key in GLOSS_OVERRIDES and GLOSS_OVERRIDES[key][1]:
            pos = GLOSS_OVERRIDES[key][1]
        root_key, root_label, root_source, formula, head, _notes = _root_info(key, li, lang, headword)
        rows[key] = dict(lang=lang, lemma=headword, gloss=gloss, pos=pos, strongs=strongs,
                         root_key=root_key, root_label=root_label, root_source=root_source, formula=formula,
                         source=source, head=head)
    for key, (member, _why) in BDB_FAMILY_LINKS.items():
        if key in rows and member in rows and rows[key]["root_source"] == ROOT_SRC_SELF \
                and rows[member]["root_source"] == ROOT_SRC_BDB:
            fam = rows[member]
            rows[key].update(root_key=fam["root_key"], root_label=fam["root_label"], root_source=ROOT_SRC_BDB,
                             formula=f"{fam['root_label']} → {rows[key]['lemma']}", head=fam["head"])
    root_glosses = _family_glosses(rows, corpus.key_freq)
    labels = _unique_root_labels(rows, root_glosses, corpus.key_freq)
    return {
        key: LemmaEntry(
            lang=r["lang"], lemma_key=key, lemma=r["lemma"], gloss=r["gloss"], pos=r["pos"], strongs=r["strongs"],
            root_key=r["root_key"], root_label=labels.get(r["root_key"], r["root_label"]),
            root_gloss=root_glosses[r["root_key"]], root_source=r["root_source"], formula=r["formula"],
            source=r["source"],
        )
        for key, r in rows.items()
    }


def root_notes(key: str) -> List[str]:
    """Where BDB's own placement overrode the lexical index for this lemma's family (else [])."""
    if key in BDB_FAMILY_LINKS:
        return [BDB_FAMILY_LINKS[key][1]]
    li = _entry_for_key(key)
    return _resolve_head(li)[1] if li is not None else []


def load_lexicon() -> Dict[str, LemmaEntry]:
    """Every lemma the Hebrew tagger can emit (all OSHB lemmas), keyed by lemma_key."""
    return _lexicon()


# ---------------------------------------------------------------------------
# Form dictionary (fallback)
# ---------------------------------------------------------------------------

def _decide(counter: Optional[Counter]) -> Tuple[Optional[str], float, int]:
    if not counter:
        return None, 0.0, 0
    total = sum(counter.values())
    key, n = counter.most_common(1)[0]
    share = n / total
    if share >= FORM_SHARE_MIN:
        return key, share, total
    return None, share, total


def _common_prefix(tuples: Iterable[Tuple[str, ...]]) -> Tuple[str, ...]:
    tl = list(tuples)
    if not tl:
        return ()
    first = tl[0]
    n = 0
    while all(len(t) > n and t[n] == first[n] for t in tl):
        n += 1
    return first[:n]


def _same_lang(counter: Optional[Counter], lang: Optional[str]) -> Counter:
    if not counter:
        return Counter()
    if not lang:
        return Counter(counter)
    kl = oshb_corpus().key_lang
    return Counter({k: n for k, n in counter.items() if kl.get(k, "heb") == lang})


def form_lookup(token: str, lang: Optional[str] = None
                ) -> Tuple[Optional[str], float, int, Tuple[str, ...], str]:
    """Whole-OT OSHB form dictionary: (lemma_key or None, share, occurrences, prefixes, key_kind).

    Only the pointed form is used (leave-one-out on 40,029 aligned Studio tokens: pointed-form
    decisions 98.0-99.3 % right, consonant-only decisions 60-73 % -- too unreliable).  With
    ``lang`` ('heb'/'arc') only lemmas of that language count (Aramaic כָּל is not Hebrew כֹּל).
    A decision needs >= ``FORM_MIN_COUNT`` occurrences and one lemma with >= 95 % of them."""
    corpus = oshb_corpus()
    pk = pointed_key(token)
    counter = _same_lang(corpus.form_pointed.get(pk), lang)
    key, share, total = _decide(counter)
    if key is None or total < FORM_MIN_COUNT:
        return None, share, total, (), "p"
    pref = corpus.form_prefixes.get(("p", pk, key))
    prefixes = _common_prefix(pref.keys()) if pref else ()
    return key, share, total, prefixes, "p"


def form_candidates(token: str) -> Counter:
    corpus = oshb_corpus()
    c = corpus.form_pointed.get(pointed_key(token))
    if c:
        return c
    return corpus.form_cons.get(hebrew_consonants(token), Counter())


# ---------------------------------------------------------------------------
# Alignment
# ---------------------------------------------------------------------------

def _pair_kind(a: str, b: str) -> Optional[Tuple[float, str]]:
    if a == b:
        return 3.0, "exact"
    if skeleton(a) == skeleton(b) and skeleton(a):
        return 2.5, "matres"
    r = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
    if r >= 0.6:
        return 1.0 + r, "similar"
    return None


def _concat_kind(joined: str, single: str) -> Optional[float]:
    """Score for one token == several words joined (or the reverse), else None."""
    if joined == single:
        return 3.0
    if skeleton(joined) == skeleton(single) and skeleton(single):
        return 2.5
    return None


# An alignment group: (token indices, word indices, kind) with kind one of
# 'exact' | 'matres' | 'similar' (1:1), 'merge' (1 token : 2-3 words), 'split' (2-3 tokens : 1 word)
Group = Tuple[Tuple[int, ...], Tuple[int, ...], str]


def _dp_match(tc: Sequence[str], wc: Sequence[str]) -> List[Group]:
    """Monotone max-score matching of two short lists (gaps cost nothing).  Besides 1:1 pairs a
    token may match 2-3 consecutive words written as one (רַבְשָׁקֵה = רַב־שָׁקֵה) and 2-3 tokens
    may match one word (פַּת בַּג = פַּתְבַּג)."""
    n, m = len(tc), len(wc)
    score = [[0.0] * (m + 1) for _ in range(n + 1)]
    back: List[List[Optional[Tuple[str, int, int]]]] = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        for j in range(m + 1):
            if i == 0 and j == 0:
                continue
            best, how = -1.0, None
            if i > 0 and score[i - 1][j] > best:
                best, how = score[i - 1][j], ("up", 1, 0)
            if j > 0 and score[i][j - 1] > best:
                best, how = score[i][j - 1], ("left", 0, 1)
            if i > 0 and j > 0:
                pk = _pair_kind(tc[i - 1], wc[j - 1])
                if pk is not None and score[i - 1][j - 1] + pk[0] > best:
                    best, how = score[i - 1][j - 1] + pk[0], (pk[1], 1, 1)
                for k in (2, 3):
                    if j >= k:
                        s = _concat_kind("".join(wc[j - k:j]), tc[i - 1])
                        if s is not None and score[i - 1][j - k] + s + 0.1 * k > best:
                            best, how = score[i - 1][j - k] + s + 0.1 * k, ("merge", 1, k)
                    if i >= k:
                        s = _concat_kind("".join(tc[i - k:i]), wc[j - 1])
                        if s is not None and score[i - k][j - 1] + s + 0.1 * k > best:
                            best, how = score[i - k][j - 1] + s + 0.1 * k, ("split", k, 1)
            score[i][j] = best
            back[i][j] = how
    out: List[Group] = []
    i, j = n, m
    while i > 0 or j > 0:
        how = back[i][j]
        if how is None:
            break
        kind, di, dj = how
        if kind not in ("up", "left"):
            out.append((tuple(range(i - di, i)), tuple(range(j - dj, j)), kind))
        i, j = i - di, j - dj
    out.reverse()
    return out


def align_groups(tokens: Sequence[str], words: Sequence[OshbWord]) -> List[Group]:
    """Align Studio tokens with the OSHB reading words of the same verse (0-based indices)."""
    tc = [hebrew_consonants(t) for t in tokens]
    wc = [w.cons for w in words]
    if tc == wc:
        return [((i,), (i,), "exact") for i in range(len(tc))]
    groups: List[Group] = []
    sm = difflib.SequenceMatcher(None, tc, wc, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            groups.extend(((i1 + k,), (j1 + k,), "exact") for k in range(i2 - i1))
        elif tag == "replace":
            for ti, wi, kind in _dp_match(tc[i1:i2], wc[j1:j2]):
                groups.append((tuple(i1 + t for t in ti), tuple(j1 + w for w in wi), kind))
    return groups


def align_tokens(tokens: Sequence[str], words: Sequence[OshbWord]) -> Dict[int, Tuple[OshbWord, str]]:
    """token index (0-based) -> (OSHB word, kind) for the 1:1 groups and split pieces."""
    out: Dict[int, Tuple[OshbWord, str]] = {}
    for ti, wi, kind in align_groups(tokens, words):
        if kind == "merge":
            continue
        for t in ti:
            out[t] = (words[wi[0]], kind)
    return out


def _form_conf(share: float, total: int) -> float:
    return round(share * (CONF_FORM_UNIQUE if total >= 10 else CONF_FORM_RARE), 3)


def _tag_from_form(idx: int, tok: str, notes: List[str], lang: Optional[str] = None) -> TokenTag:
    key, share, total, prefixes, _kind = form_lookup(tok, lang)
    if key is None:
        cands = _same_lang(oshb_corpus().form_pointed.get(pointed_key(tok)), lang)
        if cands:
            tot = sum(cands.values())
            notes.append(f"pointed form seen {tot}x in OSHB: "
                         + ", ".join(f"{k} {n * 100 // tot}%" for k, n in cands.most_common(3))
                         + "; not decisive")
        else:
            notes.append("pointed form not attested in OSHB")
        return TokenTag(index=idx, surface=tok, lemma_key=None, method="untagged", confidence=0.0, notes=notes)
    notes.append(f"OSHB form dictionary (pointed form, {share * 100:.0f}% of {total})")
    return TokenTag(index=idx, surface=tok, lemma_key=key, method="gold-form", confidence=_form_conf(share, total),
                    prefixes=prefixes, is_content=is_content_key(key), notes=notes)


def _morph_fit(tok: str, w: OshbWord) -> Tuple[Optional[str], Optional[str]]:
    """(``'O:' + w.morph`` when OSHB's parse of ``w`` describes the Studio token, else None; a note
    when the parse is withheld).  The parse fits when the pointed forms are equal, differ only in
    what does not change a parse (``parse_key``), or OSHB parses the Studio's pointed form that way
    elsewhere."""
    if not w.morph:
        return None, None
    pk = pointed_key(tok)
    if pk == w.pk or parse_key(tok) == parse_key(w.text) or oshb_corpus().form_morph.get(pk, {}).get(w.morph):
        return "O:" + w.morph, None
    if w.morph.split("/")[-1] in ("Np", "HNp", "ANp") and hebrew_consonants(tok) == w.cons:
        # A proper name has no inflection to parse: other vowels in the name itself (the Studio's
        # יְהֹוָה, יֱהֹוִה for WLC יְהוָה) leave 'Np'; the proclitics before it must still agree.
        n = len(_prefix_letters(w))
        if parse_key(_head_letters(pk, n)) == parse_key(_head_letters(w.pk, n)):
            return "O:" + w.morph, None
    return None, (f"OSHB parse {w.morph} of WLC {_wlc(w)} not given: the Studio's pointing differs "
                  "and OSHB never parses this form so")


def _head_letters(pk: str, n: int) -> str:
    """The first ``n`` letters of a pointed key with their points."""
    out: List[str] = []
    seen = 0
    for ch in pk:
        if "א" <= ch <= "ת":
            seen += 1
            if seen > n:
                break
        out.append(ch)
    return "".join(out)


def _set_morph(t: TokenTag, tok: str, w: OshbWord, same_proclitics: bool = True) -> TokenTag:
    """Give ``t`` the OSHB word's id and, when it fits the Studio token, its parse."""
    t.src = "oshb:" + w.wid if w.wid else None
    if not same_proclitics:
        t.morph = None
        if w.morph:
            t.notes.append(f"OSHB parse {w.morph} not given: the proclitics differ from WLC")
        return t
    t.morph, note = _morph_fit(tok, w)
    if note:
        t.notes.append(note)
    return t


def _tag_from_word(idx: int, tok: str, w: OshbWord, conf: float, notes: List[str],
                   parse: bool = True) -> TokenTag:
    """A tag from one OSHB word: its lemma and prefixes, its id (``src``) and -- unless ``parse``
    is False (pieces of one WLC word, one token for several) -- its parse when that fits."""
    if w.kind == "qere":
        notes.append("qere")
    elif w.kind == "ketiv":
        notes.append("ketiv")
    if w.note:
        notes.append(w.note)
    t = TokenTag(index=idx, surface=tok, lemma_key=w.key, method="gold-aligned", confidence=conf,
                 prefixes=w.prefixes, is_content=is_content_key(w.key), notes=notes)
    if parse:
        return _set_morph(t, tok, w)
    t.src = "oshb:" + w.wid if w.wid else None
    return t


_LETTER_PREFIX = {"ו": "P:w", "ב": "P:b", "כ": "P:k", "ל": "P:l", "מ": "P:m", "ש": "P:sh"}
_STUDIO_KETIV = re.compile(r"\(([^()]*)\)")   # the Studio prints the ketiv in parentheses
_POINTED_SIGN = re.compile("[\u05B0-\u05BC\u05C7]")


def _fold_final_aleph(cons: str) -> str:
    """Skeleton without a final א or ה (Aramaic emphatic -א/-ה, תְּקִילְתָּ/תְּקִילְתָּה,
    names like עֻזָּא/עֻזָּה)."""
    s = skeleton(cons)
    return s[:-1] if s[-1:] in ("א", "ה") else s


def _wlc(w: OshbWord) -> str:
    return strip_accents(w.text).replace("/", "")


def _core_cons(w: OshbWord) -> str:
    """Consonants of the OSHB word without its prefix segments (main word + suffixes)."""
    segs = w.text.split("/")
    n_pre = max(0, len([p for p in w.lemma.split("/") if p.strip()]) - 1)
    return hebrew_consonants("".join(segs[n_pre:])) if n_pre < len(segs) else w.cons


def _prefix_variant(tok: str, w: OshbWord) -> Optional[Tuple[str, ...]]:
    """When the token is the OSHB word with other proclitics (ו ב כ ל מ ה שׁ) in front, the
    token's prefix codes; else None."""
    if not w.key or w.key.split(":")[-1] in LETTER_KEYS.values():
        return None
    core = _core_cons(w)
    tc = hebrew_consonants(tok)
    if len(core) < 2 or not tc.endswith(core):
        return None
    lead = tc[: len(tc) - len(core)]
    if len(lead) > 3 or any(ch not in "ובכלמהש" for ch in lead):
        return None
    codes: List[str] = []
    for ch in lead:
        if ch == "ה":
            for c in ("P:h", "P:i"):
                if c in w.prefixes:
                    codes.append(c)
                    break
        else:
            codes.append(_LETTER_PREFIX[ch])
    codes.extend(c for c in w.prefixes if c.startswith("S:"))
    return tuple(codes)


def _prefix_letters(w: OshbWord) -> str:
    segs = w.text.split("/")
    n_pre = max(0, len([p for p in w.lemma.split("/") if p.strip()]) - 1)
    return hebrew_consonants("".join(segs[:n_pre])) if n_pre <= len(segs) else ""


def _token_prefixes(tok: str, w: OshbWord) -> Tuple[Tuple[str, ...], List[str]]:
    """Prefix codes for a token aligned to a WLC word whose spelling differs: the WLC codes when
    the token starts with the same proclitic letters, the token's own letters when only the
    proclitics differ, otherwise only the WLC suffix codes."""
    if hebrew_consonants(tok).startswith(_prefix_letters(w)):
        return w.prefixes, []
    pv = _prefix_variant(tok, w)
    if pv is not None:
        return pv, ["prefixes read from the Studio letters"]
    return tuple(c for c in w.prefixes if c.startswith("S:")), ["proclitics differ from WLC; not coded"]


def _quiet_skeleton(cons: str) -> str:
    """Consonants without the vowel letters ו י and the quiescent א."""
    return skeleton(cons).replace("א", "")


def _sin_samekh_key(text: str) -> str:
    """Skeleton with pointed sin (שׂ, U+05E9 + U+05C2) folded to samekh (ס).

    Shin (שׁ, U+05C1) and unpointed ש are left untouched, so only genuine
    Masoretic שׂ/ס orthographic variants (Isa 44:25 יְסַכֵּל / יְשַׂכֵּל,
    Job 10:11 תְּשֹׂכְכֵנִי / תְּסֹכְכֵנִי, Job 34:37 יִשְׂפּוֹק / יִסְפּוֹק) match."""
    nfd = unicodedata.normalize("NFD", text)
    out: List[str] = []
    i = 0
    n = len(nfd)
    while i < n:
        ch = nfd[i]
        if ch == "ש":
            j = i + 1
            has_sin = False
            has_shin = False
            while j < n and unicodedata.combining(nfd[j]):
                if nfd[j] == "\u05C2":
                    has_sin = True
                elif nfd[j] == "\u05C1":
                    has_shin = True
                j += 1
            out.append("ס" if (has_sin and not has_shin) else "ש")
            i = j
        else:
            out.append(ch)
            i += 1
    return skeleton(hebrew_consonants("".join(out)))


def _strip_silent_aleph(pk: str) -> str:
    """Drop an unpointed quiescent א (followed by a consonant or end-of-word,
    carrying no vowel sign of its own; e.g. Isa 30:5 הֹבִאישׁ -> הֹבִישׁ)."""
    out: List[str] = []
    n = len(pk)
    for i, ch in enumerate(pk):
        if ch == "א":
            nxt = pk[i + 1] if i + 1 < n else ""
            if not nxt or not _POINTED_SIGN.match(nxt):
                continue
        out.append(ch)
    return "".join(out)


def _pointing_conflict(idx: int, tok: str, w: OshbWord, in_name: bool) -> Optional[TokenTag]:
    """The token has the WLC word's consonants but other vowels.  When the Studio's pointing makes
    it a different OSHB word (2 Chr 1:5 Studio שָׁם "there", WLC שָׂם "put") the WLC lemma does not
    describe the Studio reading, and the lemma OSHB gives the Studio form is taken instead.  Only
    when (a) OSHB never gives the Studio form the WLC lemma, (b) one lemma of the same language has
    >= 95 % of >= 3 OSHB occurrences of the Studio form, (c) OSHB never gives the WLC form that
    lemma (so it is the pointing that tells the two apart: Exod 17:15 יְהוָה is also H3068, so the
    name יְהוָה נִסִּי keeps H3071), and (d) the word is not part of a name OSHB spreads over several
    words.  Otherwise None: the WLC lemma stands (Gen 30:38 בָּרְהָטִים, Studio form seen once)."""
    pk = pointed_key(tok)
    if pk == w.pk or in_name:
        return None
    corpus = oshb_corpus()
    pc = corpus.form_pointed.get(pk)
    if not pc or pc.get(w.key):
        return None
    key, share, total, prefixes, _kind = form_lookup(tok, w.lang)
    if key is None:
        return None
    wc = corpus.form_pointed.get(w.pk)
    if wc and wc.get(key):
        return None
    return TokenTag(index=idx, surface=tok, lemma_key=key, method="gold-form", confidence=_form_conf(share, total),
                    prefixes=prefixes, is_content=is_content_key(key),
                    notes=[f"WLC {_wlc(w)} ({w.key}) has the same consonants but other vowels; the Studio's "
                           f"pointing is {key} in {share * 100:.0f}% of {total} OSHB occurrences and never {w.key}"])


def _strip_prefix_pointed(text: str, n_pre: int) -> str:
    """Drop the first ``n_pre`` Hebrew consonant letters and their diacritics from ``text``."""
    if n_pre <= 0:
        return text
    seen = 0
    for i, ch in enumerate(text):
        if "א" <= ch <= "ת":
            if seen == n_pre:
                return text[i:]
            seen += 1
    return ""


@lru_cache(maxsize=1)
def _headword_by_pointed() -> Dict[Tuple[str, str, str], List[str]]:
    """(lang, pos, pointed_key(headword)) -> OSHB lexicon keys for single-word lexical entries."""
    entries, _aug = _lexical_index()
    corpus = oshb_corpus()
    idx: Dict[Tuple[str, str, str], List[str]] = defaultdict(list)
    for e in entries.values():
        if not e.w or " " in e.w.strip():
            continue
        k = _head_lemma_key(e)
        if not k or k not in corpus.key_freq:
            continue
        pk = pointed_key(e.w)
        if pk:
            idx[(e.lang, e.pos, pk)].append(k)
    return dict(idx)


def _tag_one_to_one(idx: int, tok: str, w: OshbWord, kind: str, in_name: bool = False) -> TokenTag:
    if kind == "exact":
        alt = _pointing_conflict(idx, tok, w, in_name)
        return alt if alt is not None else _tag_from_word(idx, tok, w, CONF_EXACT, [])
    if kind == "matres":
        t = _tag_from_word(idx, tok, w, CONF_MATRES, [f"spelling differs from WLC {_wlc(w)} (plene/defective)"],
                           parse=False)
        t.prefixes, extra = _token_prefixes(tok, w)
        t.notes[:0] = extra
        return _set_morph(t, tok, w, same_proclitics=not extra)
    # 'similar': the Studio reading differs from WLC beyond matres lectionis.  Keep the WLC lemma
    # when this form is attested for that lemma in OSHB; refuse it when the pointed form is attested
    # only for other lemmas of the same language (a different word), except proper names differing
    # only in final א/ה where OSHB attests the Studio's exact proper-name lemma; otherwise accept
    # only orthographic / lexicon-headword differences.
    corpus = oshb_corpus()
    pk_tok = pointed_key(tok)
    cons_tok = hebrew_consonants(tok)
    pc = _same_lang(corpus.form_pointed.get(pk_tok), w.lang)
    cc = _same_lang(corpus.form_cons.get(cons_tok), w.lang)
    note: Optional[str] = None
    conf = CONF_FORM_CONFIRMED
    if (pc and pc.get(w.key)) or (not pc and cc and cc.get(w.key)):
        note = "this form is attested for the same lemma"
    elif pc:
        if w.proper and _fold_final_aleph(cons_tok) == _fold_final_aleph(w.cons):
            propn_hits = [
                k for k in pc
                if (li := _entry_for_key(k)) is not None
                and li.pos == "Np"
                and " " not in li.w.strip()
                and _fold_final_aleph(hebrew_consonants(li.w)) == _fold_final_aleph(cons_tok)
            ]
            if len(propn_hits) == 1:
                pkey = propn_hits[0]
                prefixes, extra = _token_prefixes(tok, w)
                return TokenTag(
                    index=idx, surface=tok, lemma_key=pkey, method="gold-form",
                    confidence=CONF_FORM_CONFIRMED, prefixes=prefixes,
                    is_content=is_content_key(pkey),
                    notes=extra + [f"WLC reads {_wlc(w)} ({w.key}); final א/ה proper-name variant attested as {pkey}"],
                )
        return TokenTag(index=idx, surface=tok, lemma_key=None, method="untagged", confidence=0.0,
                        notes=[f"Studio reading differs from WLC {_wlc(w)} ({w.key}); the Studio form is "
                               f"attested only for {', '.join(pc)}; not resolved"])
    elif _prefix_variant(tok, w) is not None:
        note = "same word with other prefixes"
    elif ((li := _entry_for_key(w.key)) is not None and li.w and " " not in li.w.strip()
            and cons_tok == _prefix_letters(w) + hebrew_consonants(li.w)):
        note = f"matches the lexicon headword of {w.key} ({strip_accents(li.w)})"
    elif (w.lang == "arc" or w.proper) and _fold_final_aleph(cons_tok) == _fold_final_aleph(w.cons):
        note = f"final א/ה spelling ({'Aramaic' if w.lang == 'arc' else 'proper name'})"
    elif w.lang == "arc" and len(_fold_final_aleph(_quiet_skeleton(w.cons))) >= 2 \
            and _fold_final_aleph(_quiet_skeleton(cons_tok)) == _fold_final_aleph(_quiet_skeleton(w.cons)) \
            and not (cc and not cc.get(w.key)):
        note = "Aramaic final א/ה / glide spelling"
        conf = CONF_QUIESCENT
    elif _strip_silent_aleph(pk_tok) == _strip_silent_aleph(w.pk):
        note = "spelling differs only in unpointed quiescent א"
        conf = CONF_QUIESCENT
    elif _sin_samekh_key(tok) == _sin_samekh_key(w.text) and _sin_samekh_key(w.text) \
            and not (cc and not cc.get(w.key)):
        note = "שׂ/ס orthographic spelling"
        conf = CONF_FORM_CONFIRMED
    elif len(_quiet_skeleton(w.cons)) >= 3 and _quiet_skeleton(cons_tok) == _quiet_skeleton(w.cons) \
            and not (cc and not cc.get(w.key)):
        note = "spelling differs only in quiescent א / vowel letters"
        conf = CONF_QUIESCENT
    if note is None:
        want_pos = ("Np" if w.proper else "N") if w.main_code == "N" else (w.main_code if w.main_code in ("V", "A", "D") else None)
        if want_pos and not _prefix_letters(w):
            hw_hits = _headword_by_pointed().get((w.lang, want_pos, pk_tok), [])
            if len(hw_hits) == 1:
                hkey = hw_hits[0]
                return TokenTag(
                    index=idx, surface=tok, lemma_key=hkey, method="gold-form",
                    confidence=CONF_FORM_RARE, prefixes=(),
                    is_content=is_content_key(hkey),
                    notes=[f"WLC reads {_wlc(w)} ({w.key}); Studio reading is the unique pointed lexicon headword {hkey} ({want_pos})"],
                )
        return TokenTag(index=idx, surface=tok, lemma_key=None, method="untagged", confidence=0.0,
                        notes=[f"Studio reading differs from WLC {_wlc(w)} ({w.key}); not resolved"])
    t = _tag_from_word(idx, tok, w, conf, [f"WLC reads {_wlc(w)}; {note}"], parse=False)
    t.prefixes, extra = _token_prefixes(tok, w)
    t.notes[:0] = extra
    return _set_morph(t, tok, w, same_proclitics=not extra)


def _bare_from_morph(w: OshbWord, num: str) -> Optional[Tuple[str, str]]:
    """Resolve a bare Strong's number using OSHB's own morphology POS/gender when it uniquely
    selects a single-word BDB homograph.  Never separates 'A' from 'N' (substantivised adjectives
    such as Deut 17:12 הָרָע remain ambiguous)."""
    entries, aug = _lexical_index()
    homographs: List[Tuple[str, _LiEntry]] = []
    for a, eid in sorted(aug.items()):
        if len(a) == len(num) + 1 and a[:-1] == num and a[-1].isalpha():
            li = entries.get(eid)
            if li is not None and " " not in li.w.strip():
                homographs.append((f"H{int(num):04d}{a[-1]}", li))
    if not homographs:
        return None
    want_pos: Optional[str] = None
    if w.main_code == "V":
        want_pos = "V"
    elif w.main_code == "D":
        want_pos = "D"
    elif w.main_code == "N":
        want_pos = "Np" if w.proper else "N"
    if want_pos is None:
        return None
    matched = [(k, li) for k, li in homographs if li.pos == want_pos]
    if len(matched) == 1:
        return matched[0][0], f"OSHB morph {w.morph} uniquely selects {matched[0][0]} ({want_pos})"
    if want_pos == "N" and len(matched) > 1 and w.morph:
        # Feminine singular noun without suffix (Ncfsa/Ncfsc): match exact headword consonants
        # (e.g. Job 4:14 וּרְעָדָה -> H7461b רְעָדָה vs H7461a רַעַד).
        segs = w.morph[1:].split("/")
        n_pre = max(0, len([p for p in w.lemma.split("/") if p.strip()]) - 1)
        main_seg = segs[n_pre] if n_pre < len(segs) else ""
        if main_seg in ("Ncfsa", "Ncfsc") and len(segs) == n_pre + 1:
            core = _core_cons(w)
            by_head = [(k, li) for k, li in matched if hebrew_consonants(li.w) == core]
            if len(by_head) == 1:
                return by_head[0][0], f"OSHB morph {w.morph} and headword {by_head[0][1].w} select {by_head[0][0]}"
    return None


def _tag_bare(idx: int, tok: str, w: OshbWord, kind: str) -> TokenTag:
    """OSHB tagged this word with a bare Strong's number (``w.bare``) although BDB has several
    homographs under it.  The OSHB spelling statistics or OSHB's own morphology POS may single one
    out; otherwise untagged."""
    corpus = oshb_corpus()
    num = _aug_code(w.bare or "")
    cand = Counter({k: n for k, n in (corpus.form_pointed.get(pointed_key(tok)) or {}).items()
                    if re.fullmatch(rf"H0*{num}[a-z]", k)})
    key, share, total = _decide(cand)
    if key is not None and total >= FORM_MIN_COUNT:
        prefixes, extra = (w.prefixes, []) if kind == "exact" else _token_prefixes(tok, w)
        t = TokenTag(index=idx, surface=tok, lemma_key=key, method="gold-form", confidence=_form_conf(share, total),
                     prefixes=prefixes, is_content=is_content_key(key),
                     notes=[f"OSHB gives {w.bare} without the BDB homograph letter; this spelling is {key} in "
                            f"{share * 100:.0f}% of {total} OSHB occurrences"])
        return _set_morph(t, tok, w, same_proclitics=not extra)
    if not cand:
        # Full prefixed pointed form not seen in OSHB: check the unprefixed core pointed form
        # corroborated by the full consonant skeleton (e.g. 2 Sam 16:12 בְּעֵינִי -> עֵינִי 29/29 H5869a).
        n_pre = len(_prefix_letters(w))
        core_pk = pointed_key(_strip_prefix_pointed(tok, n_pre)) if n_pre > 0 else ""
        if core_pk:
            core_cand = Counter({k: n for k, n in (corpus.form_pointed.get(core_pk) or {}).items()
                                 if re.fullmatch(rf"H0*{num}[a-z]", k)})
            cons_cand = Counter({k: n for k, n in (corpus.form_cons.get(hebrew_consonants(tok)) or {}).items()
                                 if re.fullmatch(rf"H0*{num}[a-z]", k)})
            ckey, cshare, ctotal = _decide(core_cand)
            skey, sshare, stotal = _decide(cons_cand)
            if ckey is not None and ctotal >= FORM_MIN_COUNT and skey == ckey and stotal >= FORM_MIN_COUNT:
                prefixes, extra = (w.prefixes, []) if kind == "exact" else _token_prefixes(tok, w)
                t = TokenTag(index=idx, surface=tok, lemma_key=ckey, method="gold-form",
                             confidence=_form_conf(min(cshare, sshare), ctotal),
                             prefixes=prefixes, is_content=is_content_key(ckey),
                             notes=[f"OSHB gives {w.bare} without the BDB homograph letter; core spelling is {ckey} in "
                                    f"{cshare * 100:.0f}% of {ctotal} OSHB occurrences ({sshare * 100:.0f}% of {stotal} consonantal)"])
                return _set_morph(t, tok, w, same_proclitics=not extra)
    by_morph = _bare_from_morph(w, num)
    if by_morph is not None:
        mkey, mreason = by_morph
        prefixes, extra = (w.prefixes, []) if kind == "exact" else _token_prefixes(tok, w)
        conf = CONF_EXACT if kind == "exact" else CONF_FORM_CONFIRMED
        t = TokenTag(index=idx, surface=tok, lemma_key=mkey, method="gold-aligned", confidence=conf,
                     prefixes=prefixes, is_content=is_content_key(mkey),
                     notes=[f"OSHB gives {w.bare} without the BDB homograph letter; {mreason}"])
        return _set_morph(t, tok, w, same_proclitics=not extra)
    return TokenTag(index=idx, surface=tok, lemma_key=None, method="untagged", confidence=0.0,
                    notes=[f"OSHB gives {w.bare} without the BDB homograph letter"
                           + (f" ({', '.join(f'{k} {n}' for k, n in cand.most_common())})" if cand else "")
                           + "; not resolved"])


def tag_verse_tokens(tokens: Sequence[str], words: Sequence[OshbWord],
                     ketiv: Sequence[OshbWord] = (), studio_ketiv: Iterable[str] = ()) -> List[TokenTag]:
    """One TokenTag per token: gold-aligned to the OSHB words of the verse where possible.
    ``studio_ketiv``: consonants of the ketivs the Studio prints in parentheses in this verse."""
    tags: Dict[int, TokenTag] = {}
    lang_at: Dict[int, str] = {}   # language of the aligned OSHB word, for the fallback of neighbours
    studio_kets = {hebrew_consonants(k) for k in studio_ketiv}
    in_name = {j for j, w in enumerate(words) if w.cont or (j > 0 and words[j - 1].cont)}
    for ti, wi, kind in (align_groups(tokens, words) if words else []):
        ws = [words[j] for j in wi]
        for t in ti:
            lang_at[t] = ws[0].lang
        if kind == "merge":
            i = ti[0]
            keys = {w.key for w in ws}
            wl = " ".join(_wlc(w) for w in ws)
            # one lemma for the whole group (OSHB tags a name written in two words, רַב־שָׁקֵה,
            # "7262+" then "7262"); two lemmas in one token cannot be represented unless OSHB
            # itself attests the merged pointed form exclusively as one of those lemmas (e.g.
            # 2 Sam 2:30 וַעֲשָׂהאֵל = H6214, 2 Sam 21:7 מְפִיבֹשֶׁת = H4648).
            if ws[0].key and len(keys) == 1:
                # no single OSHB word owns the token: no parse, no src
                t = _tag_from_word(i + 1, tokens[i], ws[0], CONF_MATRES, [f"WLC writes {wl} as {len(ws)} words"],
                                   parse=False)
                t.src = None
                t.prefixes = ws[0].prefixes + tuple(c for c in ws[-1].prefixes if c.startswith("S:"))
                tags[i] = t
            else:
                fk, share, total, fpre, _ = form_lookup(tokens[i], ws[0].lang)
                if fk is not None and fk in keys:
                    tags[i] = TokenTag(
                        index=i + 1, surface=tokens[i], lemma_key=fk, method="gold-form",
                        confidence=_form_conf(share, total), prefixes=fpre, is_content=is_content_key(fk),
                        notes=[f"WLC splits {wl} ({', '.join(str(w.key or w.bare) for w in ws)}); "
                               f"OSHB attests the one-word form as {fk} ({share * 100:.0f}% of {total})"])
                elif (len(ws) == 2 and ws[1].key and not ws[0].prefixes
                        and len(ws[0].cons) == 2 and ws[0].cons[0] in _LETTER_PREFIX):
                    # Erroneous WLC split of proclitic + stem into a 2-letter word + truncated stem
                    # (e.g. Ps 57:10/108:4/149:7 בַּלְאֻמִּים split as בַּל H1077 + אֻמִּים H3816,
                    # whereas stripping proclitic בַּ gives לְאֻמִּים = 100% H3816 in OSHB).
                    rest = _strip_prefix_pointed(tokens[i], 1)
                    rk, rshare, rtotal, rpre, _ = form_lookup(rest, ws[1].lang) if rest else (None, 0.0, 0, (), "p")
                    if rk == ws[1].key:
                        prefs = (_LETTER_PREFIX[ws[0].cons[0]],) + tuple(c for c in rpre if c.startswith("P:")) + tuple(
                            c for c in ws[1].prefixes if c.startswith("S:"))
                        tags[i] = TokenTag(
                            index=i + 1, surface=tokens[i], lemma_key=rk, method="gold-form",
                            confidence=_form_conf(rshare, rtotal), prefixes=prefs, is_content=is_content_key(rk),
                            notes=[f"WLC splits {wl} ({ws[0].key}, {ws[1].key}); stripping proclitic "
                                   f"{ws[0].cons[0]} yields {rk} ({rshare * 100:.0f}% of {rtotal} OSHB occurrences)"])
                    else:
                        tags[i] = TokenTag(index=i + 1, surface=tokens[i], lemma_key=None, method="untagged",
                                           confidence=0.0,
                                           notes=[f"one token for WLC {wl} ({', '.join(str(w.key or w.bare) for w in ws)}); "
                                                  "not one lemma, not resolved"])
                else:
                    tags[i] = TokenTag(index=i + 1, surface=tokens[i], lemma_key=None, method="untagged",
                                       confidence=0.0,
                                       notes=[f"one token for WLC {wl} ({', '.join(str(w.key or w.bare) for w in ws)}); "
                                              "not one lemma, not resolved"])
            continue
        w = ws[0]
        if not w.key:
            if w.bare and kind in ("exact", "matres", "similar"):
                tags[ti[0]] = _tag_bare(ti[0] + 1, tokens[ti[0]], w, kind)
            continue
        if kind == "split":
            if w.cons in studio_kets:
                # The Studio prints this WLC word as its ketiv and the pieces as the qere words
                # (Ps 123:4 ketiv לגאיונים, qere לִגְאֵי יוֹנִים "the proud of the oppressors"): the
                # WLC lemma (גַּאֲיוֹן) is the ketiv's, not the lemma of either qere word.
                for i in ti:
                    tags[i] = TokenTag(index=i + 1, surface=tokens[i], lemma_key=None, method="untagged",
                                       confidence=0.0,
                                       notes=[f"qere word; WLC reads the ketiv {_wlc(w)} as one word ({w.key}), "
                                              "which is not the lemma of this qere word; not resolved"])
                continue
            # Pieces of one WLC word.  A piece takes the WLC lemma only if that spelling is not
            # attested elsewhere for another lemma (פַּת alone is "morsel", not פַּתְבַּג).
            for n, i in enumerate(ti):
                cands = form_candidates(tokens[i])
                if not cands or cands.get(w.key):
                    # the WLC word's parse describes the whole word, not this piece: src only
                    t = _tag_from_word(i + 1, tokens[i], w, CONF_FORM_CONFIRMED,
                                       [f"part of WLC {_wlc(w)}, written as one word there"], parse=False)
                    if n > 0:
                        t.prefixes = ()
                    tags[i] = t
                else:
                    tags[i] = TokenTag(index=i + 1, surface=tokens[i], lemma_key=None, method="untagged",
                                       confidence=0.0,
                                       notes=[f"part of WLC {_wlc(w)} ({w.key}) but also a word of its own "
                                              f"({', '.join(cands)}); not resolved"])
            continue
        tags[ti[0]] = _tag_one_to_one(ti[0] + 1, tokens[ti[0]], w, kind, wi[0] in in_name)
    ket_by_cons: Dict[str, OshbWord] = {}
    for kw in ketiv:
        ket_by_cons.setdefault(kw.cons, kw)
    out: List[TokenTag] = []
    for i, tok in enumerate(tokens):
        if i in tags:
            out.append(tags[i])
            continue
        kw = ket_by_cons.get(hebrew_consonants(tok))
        if kw is not None and kw.key:
            out.append(_tag_from_word(i + 1, tok, kw, CONF_EXACT, ["matches the WLC ketiv"]))
            continue
        if not _POINTED_SIGN.search(tok):
            out.append(TokenTag(index=i + 1, surface=tok, lemma_key=None, method="untagged", confidence=0.0,
                                notes=["unpointed token with no WLC counterpart (ketiv residue?)"]))
            continue
        out.append(_tag_from_form(i + 1, tok, ["no WLC word aligned"] if words else ["verse not in OSHB"],
                                  _neighbour_lang(i, lang_at, words)))
    return out


def _neighbour_lang(i: int, lang_at: Dict[int, str], words: Sequence[OshbWord]) -> Optional[str]:
    """Hebrew or Aramaic for an unaligned token: its nearest aligned neighbour's language, else the
    verse's majority language, else None (no filter)."""
    if lang_at:
        j = min(lang_at, key=lambda k: (abs(k - i), k))
        return lang_at[j]
    if words:
        return Counter(w.lang for w in words).most_common(1)[0][0]
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def tag_chapter(book_slug: str, chapter: int, verses: Dict[int, str]) -> Dict[int, List[TokenTag]]:
    """Tag the Studio Hebrew verses of one chapter (MT numbering, as stored in the Studio)."""
    corpus = oshb_corpus()
    book = OSHB_BOOK.get(book_slug)
    out: Dict[int, List[TokenTag]] = {}
    for vnum, text in verses.items():
        tokens = tokenize_verse(text or "", "heb")
        ref = (book, int(chapter), int(vnum)) if book else None
        words = corpus.reading.get(ref, []) if ref else []
        ketiv = corpus.ketiv.get(ref, []) if ref else []
        out[vnum] = tag_verse_tokens(tokens, words, ketiv, _STUDIO_KETIV.findall(text or ""))
    return out


def iter_all(conn: Optional[sqlite3.Connection] = None) -> Iterator[Tuple[str, int, Dict[int, List[TokenTag]]]]:
    """Yield (book_slug, chapter, {verse: [TokenTag]}) for every Hebrew chapter in the Studio DB."""
    own = conn is None
    if own:
        conn = open_studio_db_readonly()
    try:
        chapters = conn.execute(
            "SELECT id, book_slug, chapter FROM chapters WHERE language = 'hebrew' ORDER BY book_slug, chapter"
        ).fetchall()
        for cid, slug, ch in chapters:
            verses = {int(v): str(t or "") for v, t in conn.execute(
                "SELECT verse, critical_text FROM verses WHERE chapter_id = ? ORDER BY verse", (cid,))}
            yield str(slug), int(ch), tag_chapter(str(slug), int(ch), verses)
    finally:
        if own:
            conn.close()


def tag_all(conn: Optional[sqlite3.Connection] = None) -> Dict[Tuple[str, int], Dict[int, List[TokenTag]]]:
    """{(book_slug, chapter): {verse: [TokenTag]}} for the whole Hebrew OT in the Studio DB."""
    return {(slug, ch): tags for slug, ch, tags in iter_all(conn)}


# ---------------------------------------------------------------------------
# LXX equivalents (MACULA Hebrew)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _lxx_equivalents() -> Dict[str, Counter]:
    path = macula_tsv_path()
    out: Dict[str, Counter] = defaultdict(Counter)
    if path is None:
        return {}
    corpus = oshb_corpus()
    groups: Dict[Tuple[str, int, int, int], List[Tuple[str, str, str, str]]] = defaultdict(list)
    with path.open(encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        col = {name: i for i, name in enumerate(header)}
        i_id, i_ref, i_text = col["xml:id"], col["ref"], col["text"]
        i_sx, i_gs = col["strongnumberx"], col["greekstrong"]
        need = max(i_id, i_ref, i_text, i_sx, i_gs)
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) <= need:
                continue
            xid = f[i_id]
            if not xid or not xid[-1].isdigit():
                continue  # implied article rows (id ends with ה) have no segment of their own
            m = re.fullmatch(r"([1-3A-Z]{3}) (\d+):(\d+)!(\d+)", f[i_ref].strip())
            if not m or m.group(1) not in _USFM_TO_OSHB:
                continue
            k = (_USFM_TO_OSHB[m.group(1)], int(m.group(2)), int(m.group(3)), int(m.group(4)))
            groups[k].append((f[i_text], f[i_sx], f[i_gs], xid))
    stats = LXX_STATS
    stats.clear()
    function_keys = _function_keys()
    for (book, ch, v, wn), rows in groups.items():
        stats["macula_words"] += 1
        words = corpus.all_words.get((book, ch, v))
        if not words or wn - 1 >= len(words):
            stats["no_oshb_word"] += 1
            continue
        w = words[wn - 1]
        if not w.key or hebrew_consonants("".join(r[0] for r in rows)) != w.cons:
            stats["consonants_differ_or_no_lemma"] += 1
            continue
        n_pre = len([p for p in w.lemma.split("/") if p.strip()]) - 1
        if n_pre >= len(rows):
            stats["segments_differ"] += 1
            continue
        text, sx, gs, _xid = rows[n_pre]
        mk = re.match(r"H(\d+)", w.key.split(":", 1)[-1])
        sm = re.match(r"0*(\d+)", sx or "")
        if mk and int(mk.group(1)) < 9000 and (not sm or int(sm.group(1)) != int(mk.group(1))):
            stats["strong_differs"] += 1
            continue  # MACULA segment is not the OSHB main lemma
        stats["matched"] += 1
        greek = [f"G{int(g):04d}" for g in re.split(r"[|\s,;]+", gs or "") if g.isdigit()]
        if greek:
            stats["matched_with_greek"] += 1
        if w.key not in function_keys:
            # a content word: the article, conjunction, preposition or pronoun MACULA aligns
            # alongside the LXX rendering is not its equivalent (רֵעַ is πλησίον, not ὁ)
            kept = [g for g in greek if g not in GREEK_FUNCTION_STRONGS]
            stats["greek_function_words_skipped"] += len(greek) - len(kept)
            greek = kept
        for g in greek:
            out[w.key][g] += 1
    return {k: c for k, c in out.items() if c}


LXX_STATS: Counter = Counter()   # filled by lxx_equivalents(): how MACULA words matched OSHB words


def lxx_equivalents() -> Dict[str, Counter]:
    """Hebrew lemma_key -> Counter of the Greek Strong's numbers ('G0746') that the LXX uses for it
    (MACULA Hebrew ``greekstrong``, CC BY 4.0), counted over aligned occurrences."""
    return _lxx_equivalents()


# ---------------------------------------------------------------------------
# Parse legend (OSHB morphology key, Oshm.xml)
# ---------------------------------------------------------------------------

_TEI_NS = "{http://www.crosswire.org/2008/TEIOSIS/namespace}"


def _clean_morph_text(text: str) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    return re.sub(r"\bAdjective adjective\b", "Adjective", t)


@lru_cache(maxsize=1)
def _oshm() -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    """OSHB's key to its morphology codes: (full code -> its English as the key gives it, segment
    code with its language letter ('HR', 'HNcfsa', 'ASp3ms') -> the English of that segment,
    language letter -> 'Hebrew' / 'Aramaic').  Segments are read from the key's full codes, whose
    English lists the segments in order, separated by '; '."""
    p = oshm_path()
    full: Dict[str, str] = {}
    seg: Dict[str, str] = {}
    langs: Dict[str, str] = {}
    if p is None:
        return full, seg, langs
    for e in ET.parse(p).getroot().iter(_TEI_NS + "entryFree"):
        code = (e.get("n") or "").strip()
        text = "".join(e.itertext()).strip()
        if not code or ":" not in text:
            continue
        full[code] = text
        label, _sep, rest = text.partition(":")
        parts = code[1:].split("/")
        texts = [s.strip() for s in rest.split(";")]
        if len(parts) != len(texts) or not all(parts) or not all(texts):
            continue  # two entries end with a stray '/' ('AC/Ncmpc/'): their segments come from other entries
        langs.setdefault(code[0], label.strip())
        for s, t in zip(parts, texts):
            seg.setdefault(code[0] + s, _clean_morph_text(t))
    return full, seg, langs


def morph_description(code: str) -> Optional[str]:
    """English for one OSHB morph string ('HR/Ncfsa' or 'O:HR/Ncfsa'): 'Hebrew: Preposition + Noun
    common feminine singular absolute'.  Composed from the segment expansions of OSHB's key, so
    combinations the key does not list (8 of the 3,464 in the corpus: HTd/Sp3fs ...) are covered
    too; None when a segment is unknown."""
    if code.startswith("O:"):
        code = code[2:]
    if len(code) < 2:
        return None
    _full, seg, langs = _oshm()
    lang = code[0]
    parts = code[1:].split("/")
    texts = [seg.get(lang + s) for s in parts]
    if lang not in langs or not all(parts) or any(t is None for t in texts):
        return None
    return f"{langs[lang]}: " + " + ".join(texts)


@lru_cache(maxsize=1)
def _morph_legend() -> Dict[str, str]:
    codes = set(_oshm()[0])
    if oshb_wlc_dir() is not None:
        codes.update(w.morph for words in oshb_corpus().all_words.values() for w in words if w.morph)
    out: Dict[str, str] = {}
    for code in sorted(codes):
        desc = morph_description(code)
        if desc:
            out["O:" + code] = desc
    return out


def morph_legend() -> Dict[str, str]:
    """``{'O:HR/Ncfsa': 'Hebrew: Preposition + Noun common feminine singular absolute', ...}`` for
    every morph string in OSHB (reading and ketiv words) and in OSHB's key -- so every ``morph`` a
    Studio TokenTag can carry.  Source and changes: ``SRC_MORPH_LEGEND``."""
    return dict(_morph_legend())


__all__ = [
    "morph_legend", "morph_description", "parse_key", "SRC_MORPH_LEGEND",
    "load_lexicon", "tag_chapter", "tag_all", "iter_all", "lxx_equivalents", "function_word_keys",
    "is_content_key", "form_lookup", "align_tokens", "oshb_corpus", "corpora_available",
    "open_studio_db_readonly", "OSHB_BOOK", "FUNCTION_MORPH_CODES", "FUNCTION_PARTICLE_KEYS",
    "GREEK_FUNCTION_STRONGS", "OSHB_LEMMA_CORRECTIONS", "root_notes", "GLOSS_OVERRIDES", "HEADWORD_OVERRIDES",
    "BDB_FAMILY_LINKS", "FUNCTION_LEX_POS", "tipnr_path",
]
