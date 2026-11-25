"""Narrow, documented import repairs; original witness files remain untouched.

These apply only to the three bundled digital copies of Swete (two copies of one OCR and the
keyed Amicarelli transcription), and only while the exact damaged passages remain. See
docs/SOURCE-REVIEW-2026-11-17.md and docs/RAHLFS-CHECK-2026-11-17.md for the evidence.
Never supply missing words.
"""

from typing import Dict, List, Tuple

from .parsers import GAP_WORD, LACUNA_MARK


_OCR_COPIES = {
    "grk-1st1k-lxx": "first1k_tei",
    "grk-swete-lxx": "swete_clean",
}
_SWETE_COPIES = dict(_OCR_COPIES, **{"grk-swete-csv": "swete_csv"})
_ANCHOR_COPIES = {"grk-brenton-sixtine": "brenton_usfm"}  # numbering anchor: documented OCR & division repairs
_NT_KEYING_COPIES = {
    "grk-nt-kjtr": "cntr_edition",
    "grk-nt-sblgnt": "sblgnt_txt",
}
_LATIN_REPAIR_COPIES = {
    "lat-amiatinus": "amiatinus_tei",
    "lat-clementine-usfx": "usfx_xml",
    "lat-saints-staging": "latin_saints_json",
    "lat-vulg-hetzenauer": "scrollmapper_csv",
    "lat-vulg-conte": "scrollmapper_csv",
    "lat-vulg-sistina": "scrollmapper_csv",
    "lat-quarantine-stuttgart": "scrollmapper_csv",
}
_HEBREW_REPAIR_COPIES = {
    "heb-mam-aleppo": "mam_osis",
}
_REPAIRABLE_COPIES = {**_SWETE_COPIES, **_ANCHOR_COPIES, **_NT_KEYING_COPIES, **_LATIN_REPAIR_COPIES, **_HEBREW_REPAIR_COPIES}
# Digital files that leave out text their printed edition has: the gap is marked lost ("…"), so it is not
# recorded as the edition's omission. (witness id, parser kind) -> [(book, chapter, verse, exact opening, what is lost)]
_FILE_GAPS = {
    ("lat-saints-staging", "latin_saints_json"): [("lamentations", 1, 1, "Quomodo sedet",
                                                   "Jerome's prologue 'Et factum est, postquam in captivitatem …' and acrostic letter 'Aleph'")],
    ("lat-vulg-hetzenauer", "scrollmapper_csv"): [("lamentations", 1, 1, "Aleph Quomodo sedet",
                                                    "Jerome's prologue 'Et factum est, postquam in captivitatem …'")],
    ("lat-vulg-conte", "scrollmapper_csv"): [("lamentations", 1, 1, "Aleph Quomodo sedet",
                                               "Jerome's prologue 'Et factum est, postquam in captivitatem …'")],
}
_CSV = ("grk-swete-csv",)
_OCR = tuple(_OCR_COPIES)
_ALL = _CSV + _OCR
_KINGS_PREFIX = "τους γνωριστας om τους Α τα θεραειν om τα A γη pr τη A "
_KINGS_TAIL = ("καὶ τρίμηνον ἐβασίλευσεν ἐν Ἰερουσαλήμ, καὶ ὄνομα τῇ μητρὶ αὐτοῦ "
               "Ἀμειταί, θυγάτηρ Ἰερεμίου ἐκ Λημνά.")
_PSALM_46 = "ἐσμίκρυνας τὰς ἡμέρας τοῦ θρόνου αὐτοῦ, κατέχεας αὐτοῦ αἰσχύνην."
_PSALM_84 = ("μνήσθητι τίς μου ἡ ὑπόστασις· διάψαλμα. "
             "μὴ γὰρ ματαίως ἔκτισας πάντας τοὺς υἱοὺς τῶν ἀυθρώπων")
_G = GAP_WORD

# Keying slips of the transcription and Rahlfs-patched words of the OCR, found by the Rahlfs check of
# 17 Nov 2026 (docs/RAHLFS-CHECK-2026-11-17.md; each confirmed against the other copies of Swete and,
# for Kingdoms, the Larger Cambridge B text). (copies, book, chapter, verse in the copy's own
# numbering, exact text, replacement, what Swete prints.) The text must occur exactly once. A wrong
# word becomes "[…]", which casts no vote, so the other copies of Swete decide; a skipped word becomes
# an extra "[…]", a skipped clause "…"; a word or clause typed twice is removed once. No word is supplied.
_SLIPS: Tuple[Tuple[Tuple[str, ...], str, int, int, str, str, str], ...] = (
    (_CSV, "exodus", 28, 23, "μνημόσυνου", _G, "μνημόσυνον"),
    (_CSV, "numbers", 15, 12, "ὧν ἐὰν ποιήσετε,", f"ὧν ἐὰν {_G}", "ὧν ἐὰν ποιήσητε,"),
    (_CSV, "numbers", 26, 26, "τῷ, Ἀροδεί,", f"{_G} Ἀροδεί,", "τῷ Ἀροδεί, (no comma after the article)"),
    (_CSV, "numbers", 29, 36, "καρπώματα Κυρίου·", f"καρπώματα {_G} {_G}",
     "καρπώματα τῷ Κυρίῳ (Larger Cambridge B; both OCR copies lost the two words)"),
    (_OCR, "numbers", 29, 36, "καρπώματα μόσχον", f"καρπώματα {_G} {_G} μόσχον",
     "καρπώματα τῷ Κυρίῳ, μόσχον (two words lost in the OCR)"),
    (_CSV, "joshua", 4, 5, "Ἰροδάνου,", _G, "Ἰορδάνου,"),
    (_CSV, "judges", 11, 19, "καὶ ἀπέστειλεν καὶ εἶπεν αὐτῷ", f"καὶ ἀπέστειλεν {LACUNA_MARK} καὶ εἶπεν αὐτῷ",
     "καὶ ἀπέστειλεν Ἰσραὴλ ἀγγέλους πρὸς Σηὼν βασιλέα τοῦ Ἀμορραίου βασιλέα Ἐσεβών, καὶ εἶπεν (clause skipped)"),
    (_OCR, "judges", 11, 19, "καὶ ἀπέστειλεν ἀλλέλους πρὸς", f"καὶ ἀπέστειλεν {LACUNA_MARK} πρὸς",
     "καὶ ἀπέστειλεν Ἰσραὴλ ἀγγέλους πρὸς (Ἰσραὴλ lost and ἀγγέλους garbled to ἀλλέλους in the OCR)"),
    (_OCR, "judges", 11, 19, "Εσεβών, αὐτῷ", f"Εσεβών, {LACUNA_MARK} αὐτῷ", "Ἐσεβών, καὶ εἶπεν αὐτῷ (two words lost in the OCR)"),
    (_CSV, "judges", 21, 14, "βενιαμεὶν", _G, "Βενιαμεὶν"),
    (_CSV, "ruth", 4, 4, "εἶπεν Ἐγώ εἰμι ἀγχιστεῦσαι, κἀγώ εἰμι μετὰ σέ. ὁ δὲ εἶπεν Ἐγώ εἰμι ἀγχιστεύσω.",
     "εἶπεν Ἐγώ εἰμι ἀγχιστεύσω.", "ὁ δὲ εἶπεν Ἐγώ εἰμι ἀγχιστεύσω (a clause typed twice)"),
    (_CSV, "ruth", 4, 19, "Ἐσρὼν δὲ ἐγέννησεν τὸν Ἀρράν, καὶ Ἁρρὰν ἐγέννησεν",
     f"{_G} δὲ ἐγέννησεν τὸν Ἀρράν, καὶ {_G} ἐγέννησεν", "Ἑσρὼν … καὶ Ἀρρὰν (breathings)"),
    (_CSV, "1-samuel", 3, 20, "Σαμονὴλ", _G, "Σαμουὴλ"),
    (_CSV, "1-samuel", 20, 42, "σηέρματός", _G, "σπέρματός"),
    (_CSV, "1-samuel", 25, 16, "ἤμεθα", _G, "ἥμεθα"),
    (_CSV, "2-samuel", 19, 27, "κύριόν μου, πρὸς τὸν βασιλέα", f"κύριόν μου, {_G} τὸν βασιλέα",
     "πρὸς τὸν κύριόν μου τὸν βασιλέα"),
    (_CSV, "1-kings", 1, 51, "σήμερον Σαλωμὼν", f"σήμερον {_G} {_G} Σαλωμὼν", "σήμερον ὁ βασιλεὺς Σαλωμὼν"),
    (_CSV, "1-kings", 2, 4, "Οὐκ ἐξολοθρευθήσεταί", f"Οὐκ {_G}", "ἐξολεθρευθήσεταί"),
    (_CSV, "1-kings", 4, 20, "βσαιλεῖ", _G, "βασιλεῖ (a typo the Brenton e-text shares)"),
    (_CSV, "1-kings", 16, 15, "Γαβαὼν τῶν ἀλλοφύλων", f"Γαβαὼν {_G} τῶν ἀλλοφύλων", "ἐπὶ Γαβαὼν τὴν τῶν ἀλλοφύλων"),
    (_OCR, "1-kings", 2, 3, "καὶ φυλάξεις τὴν φυλακὴν κυρίου τοῦ θεοῦ σου",
     f"καὶ φυλάξεις {_G} φυλακὴν {_G} {_G} θεοῦ σου",
     "καὶ φυλάξεις φυλακὴν θεοῦ σου (transcription and Larger Cambridge B; the OCR copy follows Rahlfs here)"),
    (_OCR, "1-kings", 21, 25, "κατὰ τὴν ἵππον", f"κατὰ {_G} ἵππον",
     "κατὰ τὸν ἵππον (transcription and Larger Cambridge B; the OCR copy follows Rahlfs here)"),
    (_OCR, "1-kings", 21, 32, "σάκκους ἐπὶ τὰς ὀσφύας", f"σάκκους {_G} τὰς ὀσφύας",
     "σάκκους περὶ τὰς ὀσφύας (transcription and Larger Cambridge B; the OCR copy follows Rahlfs here)"),
    (_CSV, "2-kings", 25, 22, "κατέιλπεν", _G, "κατέλιπεν"),
    (_OCR, "2-kings", 25, 22, "οὓς Ναβουχοδονοσὸρ", f"οὓς {_G} Ναβουχοδονοσὸρ", "οὓς κατέλιπεν (a word lost in the OCR)"),
    (_CSV, "1-chronicles", 5, 13, "Χιμὰ Ζοῦε", f"Χιμὰ {_G} Ζοῦε", "Χιμὰ καὶ Ζοῦε"),
    (_CSV, "2-maccabees", 11, 5, "χερίῳ,", _G, "χωρίῳ,"),
    (_CSV, "psalms", 27, 1, "ἐπ᾽ ἑμοί·", f"ἐπ᾽ {_G}", "ἐπ᾽ ἐμοί·"),
    (_CSV, "psalms", 111, 2, "εὐθέων", _G, "εὐθείων"),
    (_CSV, "ecclesiastes", 7, 23, "κακώσει καρδία σου,", f"κακώσει {_G} σου,", "κακώσει καρδίαν σου"),
    (_CSV, "ecclesiastes", 9, 9, "πᾶσαι ἡμέραι ἡμέραι ἀτμοῦ", "πᾶσαι ἡμέραι ἀτμοῦ", "πᾶσαι ἡμέραι ἀτμοῦ (a word typed twice)"),
    (_CSV, "ecclesiastes", 9, 12, "ἀμφιβλήστρῳ καλῷ,", f"ἀμφιβλήστρῳ {_G}", "ἀμφιβλήστρῳ κακῷ"),
    (_CSV, "song-of-songs", 6, 12, "ὀφόμεθα", _G, "ὀψόμεθα"),
    (_CSV, "ezekiel", 10, 22, "ποταμοῦ Χοβάρ", f"ποταμοῦ {_G} Χοβάρ", "ἐπὶ τοῦ ποταμοῦ τοῦ Χοβάρ"),
    (_CSV, "daniel", 1, 10, "φοβοῦμαι", _G, "Φοβοῦμαι (capital: direct speech)"),
    (_CSV, "daniel", 3, 77, "ὑμερυψοῦτε", _G, "ὑπερυψοῦτε"),
    # Swete Clean lost Swete's prologue to Lamentations in conversion (First1KGreek, the same OCR, has it).
    (("grk-swete-lxx",), "lamentations", 1, 1, "^Ἄλεφ. Πῶς ἐκάθισεν", f"{LACUNA_MARK} Ἄλεφ. Πῶς ἐκάθισεν",
     "ΚΑΙ ἐγένετο … καὶ εἶπεν Ἄλεφ. (prologue lost in conversion: not evidence that Swete lacks it)"),
    # Accuracy Audit (21 Nov 2026) — verified OCR / keying / XML-markup import repairs across Greek OT, Greek NT, Latin:
    (_OCR, "sirach", 24, 34, "ἅποσιν", _G, "ἅπασιν (OCR ο for α; Swete-Amicarelli and Rahlfs print ἅπασιν)"),
    (_OCR, "1-chronicles", 6, 81, "τπερισπόρια", _G, "περισπόρια (stray initial τ in OCR; Swete-Amicarelli prints περισπόρια)"),
    (_CSV, "1-chronicles", 6, 67, "φυγαδευτρηίων", _G, "φυγαδευτηρίων (transposed ρη/ηρ in Amicarelli transcription)"),
    (_CSV, "1-kings", 12, 24, "πρὸς τὸν ἄνθρωπον τοῦ θεοῦ, καὶ κολλύρια",
     f"πρὸς τὸν ἄνθρωπον τοῦ θεοῦ, {LACUNA_MARK} καὶ κολλύρια",
     "πρὸς τὸν ἄνθρωπον τοῦ θεοῦ, καὶ εἶπεν αὐτῇ Ἀχειά Ἵνα τί μοι ἐνήνοχας ἄρτους καὶ σταφυλὴν καὶ κολλύρια (10-word homoeoteleuton skip in Amicarelli transcription)"),
    (_OCR, "1-kings", 12, 24, "Ἵωα τί μοι ἐνήνοχας ἄπτους καὶ σταφυλὴν καὶ κολλύρια καὶ στάμον",
     f"Ἵνα τί μοι ἐνήνοχας ἄρτους καὶ σταφυλὴν καὶ κολλύρια καὶ {_G}",
     "Ἵνα … ἄρτους … στάμνον (three single-letter OCR typos in 3 Kgdms 12:24m addition; corroborated by Swete II p. 719, Rahlfs, & Larger Cambridge B)"),
    (("grk-nt-kjtr",), "acts", 8, 37,
     "Εἰπε δὲ ὁ Φίλιππος, Εἰ πιστεύεις ἐξ ὅλης τὴς καρδίας, ἔξεστιν. Ἀποκριθεὶς δὲ εἷπε, Πιστεύω τὸν Ὑιὸν τοῦ Θεοῦ ἐιναι",
     "Εἶπε δὲ ὁ Φίλιππος, Εἰ πιστεύεις ἐξ ὅλης τῆς καρδίας, ἔξεστιν. Ἀποκριθεὶς δὲ εἶπε, Πιστεύω τὸν Υἱὸν τοῦ Θεοῦ εἶναι",
     "polytonic accent/breathing typos in CNTR KJTR (corroborated verbatim by Scrivener 1894 & Boyd TR)"),
    (("grk-nt-kjtr",), "acts", 24, 7, "ὁ χιλιαρχος,", "ὁ χιλίαρχος,",
     "missing acute accent on χιλίαρχος in CNTR KJTR (corroborated by Scrivener 1894 & Boyd TR)"),
    (("grk-nt-kjtr",), "luke", 17, 36, "ὁ εἴς παραληφθήσεται", "ὁ εἷς παραληφθήσεται",
     "acute+smooth typo εἴς for numeral εἷς in CNTR KJTR (corroborated by Scrivener 1894 & Boyd TR)"),
    (("grk-nt-sblgnt",), "john", 8, 3, "καταλήφθεισαν·", "καταληφθεῖσαν·",
     "upstream SBLGNT 2010 accent slip; feminine aorist passive participle is properispomenon καταληφθεῖσαν (RP2018, NA28)"),
    (("lat-amiatinus",), "genesis", 7, 5, "praeceperat […] dominus illi", "praeceperat dominus illi",
     "DLL <supplied reason=\"omitted\" source=\"#s\">ei</supplied> marks Amiatinus's transposition ei → illi after dominus, not a physical lacuna"),
    (("lat-amiatinus",), "genesis", 39, 14, "haebrę um", "haebręum",
     "missing break=\"no\" on <lb rend=\"indent\"/> inside haebręum in DLL Amiatinus XML"),
    (("lat-saints-staging",), "sirach", 29, 13, "^Super scutum potentis$", f"Super scutum potentis {LACUNA_MARK}",
     "Saints Latin JSON omits Vulgate 29:17–18 ('et super lanceam adversus inimicum tuum pugnabit.'); marked truncated so Clem1598-USFX supplies the complete verse"),
    # Phase 2 Audit (22 Nov 2026) — verified Latin USFX typos, Greek Brenton OCR/breathing slips, and Hebrew MAM XML tagging slip:
    (("lat-clementine-usfx",), "numbers", 35, 1, "in campes tribus Moab", "in campestribus Moab",
     "in campestribus Moab (split-word typo in Clem1598-USFX; corroborated by Clem-Saints, VulgHetzenauer, VulgSistina, Stuttgart-BSV)"),
    (("lat-clementine-usfx",), "matthew", 25, 42, "non desistis mihi potum:", "non dedistis mihi potum:",
     "non dedistis mihi potum: (typesetting/OCR slip in Clem1598-USFX; corroborated by Clem-Saints, VulgSistina, Amiatinus NT, Stuttgart-BSV)"),
    (("lat-clementine-usfx",), "mark", 3, 18, "Andræam,", "Andream,",
     "Andream, (erroneous æ ligature in Clem1598-USFX for Greek Ἀνδρέας; corroborated by Clem-Saints, VulgSistina, Amiatinus NT, Stuttgart-BSV)"),
    (("grk-brenton-sixtine",), "1-chronicles", 5, 30, "τὸν Αβισοὺ,", "τὸν Ἀβισοὺ,",
     "Ἀβισού (missing initial smooth breathing in Brenton USFM; corroborated by LXX-Orthodox & Rahlfs)"),
    (("grk-brenton-sixtine",), "1-chronicles", 5, 31, "^Αβισοὺ ἐγέννησεν", "Ἀβισοὺ ἐγέννησεν",
     "Ἀβισού (missing initial smooth breathing in Brenton USFM; corroborated by LXX-Orthodox & Rahlfs)"),
    (("heb-mam-aleppo",), "jeremiah", 3, 7, "וְלֹא־שָׁ֑בָה ותראה וַתֵּ֛רֶא", "וְלֹא־שָׁ֑בָה (ותראה) וַתֵּ֛רֶא",
     "(ותראה) וַתֵּ֛רֶא (upstream MAPM_Masorah.xml omitted <seg type=\"x-ketiv\"> around ketiv ותראה; corroborated by WLC/BHS/OSHB)"),
    # 48 verified Brenton USFM OCR slips printing γἱ/νἱ (impossible rough breathing after consonant) for υἱ- (υἱοὶ/υἱῶν/υἱοὺς/υἱὸς);
    # every locus occurs once in its verse and is corroborated verbatim by LXX-Orthodox, Swete (where extant), and Rahlfs.
    *(
        (("grk-brenton-sixtine",), _book, _ch, _v, _old, _new,
         f"{_new} (Brenton USFM OCR slip '{_old}' with impossible post-consonant rough breathing; corroborated by LXX-Orthodox & Rahlfs)")
        for _book, _ch, _v, _old, _new in (
            ("genesis", 46, 9, "γἱοὶ", "υἱοὶ"),
            ("leviticus", 16, 34, "νἱῶν", "υἱῶν"),
            ("joshua", 5, 1, "νἱῶν", "υἱῶν"),
            ("joshua", 16, 9, "νἱῶν", "υἱῶν"),
            ("joshua", 17, 14, "νἱοὶ", "υἱοὶ"),
            ("judges", 6, 8, "νἱοὺς", "υἱοὺς"),
            ("2-kings", 18, 18, "νἱὸς", "υἱὸς"),
            ("1-chronicles", 15, 17, "νἱῶν", "υἱῶν"),
            ("1-chronicles", 19, 2, "νἱῶν", "υἱῶν"),
            ("1-chronicles", 23, 8, "γἱοὶ", "υἱοὶ"),
            ("1-chronicles", 23, 9, "γἱοὶ", "υἱοὶ"),
            ("1-chronicles", 23, 12, "γἱοὶ", "υἱοὶ"),
            ("1-chronicles", 23, 13, "γἱοὶ", "υἱοὶ"),
            ("1-chronicles", 23, 15, "γἱοὶ", "υἱοὶ"),
            ("1-chronicles", 23, 16, "γἱοὶ", "υἱοὶ"),
            ("1-chronicles", 23, 18, "γἱοὶ", "υἱοὶ"),
            ("1-chronicles", 23, 19, "γἱοὶ", "υἱοὶ"),
            ("1-chronicles", 23, 20, "γἱοὶ", "υἱοὶ"),
            ("1-chronicles", 23, 21, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 8, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 9, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 10, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 11, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 12, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 13, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 14, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 15, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 16, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 17, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 18, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 19, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 20, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 21, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 22, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 23, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 24, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 25, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 26, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 27, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 35, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 36, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 37, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 38, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 42, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 57, "γἱοὶ", "υἱοὶ"),
            ("nehemiah", 7, 62, "γἱοὶ", "υἱοὶ"),
            ("psalms", 61, 10, "νἱοὶ", "υἱοὶ"),
            ("isaiah", 17, 9, "νἱῶν", "υἱῶν"),
        )
    ),
    # Stage 1 Accuracy Audit (24 Nov 2026) — Latin D2 verified digital/1598 non-word typos & orthography:
    (("lat-clementine-usfx",), "genesis", 20, 2, "de Sara uxore suo:", "de Sara uxore sua:",
     "uxore sua (grammatical gender slip in 1598 Clementine; corroborated by Codex Amiatinus & Stuttgart-BSV)"),
    (("lat-clementine-usfx",), "nehemiah", 4, 18, "^ædificentium enim unusquisque", "ædificantium enim unusquisque",
     "ædificantium (1598 printing slip for 1st-conj. participle; corroborated by Stuttgart-BSV aedificantium)"),
    (("lat-clementine-usfx",), "daniel", 5, 2, "in Ierusalem,", "in Jerusalem,",
     "Jerusalem (j-orthography consistency with all 795 other occurrences in Clem1598-USFX)"),
    (("lat-clementine-usfx",), "daniel", 5, 3, "in Ierusalem:", "in Jerusalem:",
     "Jerusalem (j-orthography consistency with all 795 other occurrences in Clem1598-USFX)"),
    (("lat-clementine-usfx",), "hosea", 2, 13, "ornabatur in aure sua,", "ornabatur inaure sua,",
     "inaure sua (word-split typo in Clem1598-USFX; corroborated by VulgHetzenauer, VulgConte, VulgSistina, Stuttgart-BSV)"),
    (("lat-clementine-usfx",), "amos", 8, 8, "et ejicicetur,", "et ejicietur,",
     "ejicietur (1598 doubled-syllable non-word typo; corroborated by Stuttgart-BSV eicietur)"),
    (("lat-clementine-usfx",), "micah", 3, 7, "omnes vultos suos,", "omnes vultus suos,",
     "vultus (1598 non-word 2nd-decl. typo for 4th-decl. acc. pl.; corroborated by Stuttgart-BSV)"),
    (("lat-clementine-usfx",), "luke", 8, 2, "malignis et infirmatibus:", "malignis et infirmitatibus:",
     "infirmitatibus (1598 haplography; corroborated by Codex Amiatinus NT & Stuttgart-BSV)"),
    (("lat-clementine-usfx",), "2-corinthians", 1, 23, "dominamur fidei vestæ,", "dominamur fidei vestræ,",
     "vestræ (1598 printing slip; corroborated by Codex Amiatinus NT, 9 COMPAUL Old Latin MSS, & Stuttgart-BSV)"),
    # Stage 1 Accuracy Audit (24 Nov 2026) — Hebrew MAM double-vowel corruptions & verse-ending (ketiv)׃ sof pasuqs:
    (("heb-mam-aleppo",), "numbers", 6, 2, "לַֽיהוָֹֽה׃", "לַֽיהֹוָֽה׃",
     "misplaced holam on waw in upstream MAPM_Masorah.xml (corroborated by MAM normal יְהֹוָה & WLC/BHSA)"),
    (("heb-mam-aleppo",), "2-chronicles", 24, 4, "בֵּ֥ית יְהוָֹֽה׃", "בֵּ֥ית יְהֹוָֽה׃",
     "misplaced holam on waw in upstream MAPM_Masorah.xml (corroborated by MAM normal יְהֹוָה & WLC/BHSA)"),
    (("heb-mam-aleppo",), "jonah", 4, 2, "אֶל־יְהוָֹ֜ה", "אֶל־יְהֹוָ֜ה",
     "misplaced holam on waw in upstream MAPM_Masorah.xml (corroborated by יְהֹוָה in same verse & WLC/BHSA)"),
    (("heb-mam-aleppo",), "nahum", 1, 2, "נֹקֵ֤ם יְהוָֹה֙", "נֹקֵ֤ם יְהֹוָה֙",
     "misplaced holam on waw in upstream MAPM_Masorah.xml (corroborated by יְהֹוָה twice in same verse & WLC/BHSA)"),
    (("heb-mam-aleppo",), "numbers", 11, 32, "הַֽמָׇּחֳרָ֗ת", "הַֽמׇּחֳרָ֗ת",
     "stacked qamats+qamats-qatan in upstream MAPM_Masorah.xml (matches MAM 1 Sam 5:3, 5:4, 11:11; 1 Chr 10:8)"),
    (("heb-mam-aleppo",), "jeremiah", 28, 4, "מֶלֶךְ־יְ֠הוּדָׇ֠ה", "מֶלֶךְ־יְ֠הוּדָ֠ה",
     "stray qamats-qatan after qamats on dalet of Yehudah in upstream MAPM_Masorah.xml (corroborated by WLC/BHSA)"),
    (("heb-mam-aleppo",), "ezekiel", 17, 7, "שָׇׁרָשֶׁ֣יהָ", "שׇׁרָשֶׁ֣יהָ",
     "stacked qamats+qamats-qatan in upstream MAPM_Masorah.xml (matches MAM Ezek 17:9 & Dan 11:7)"),
    (("heb-mam-aleppo",), "2-samuel", 3, 15, "בֶּן־לָֽיִשׁ (לוש)׃$", "בֶּן־לָֽיִשׁ׃ (לוש)",
     "move verse-ending sof pasuq from silent Ketiv onto Qere (D4)"),
    (("heb-mam-aleppo",), "2-samuel", 19, 32, "אֶת־הַיַּרְדֵּֽן (בירדן)׃$", "אֶת־הַיַּרְדֵּֽן׃ (בירדן)",
     "move verse-ending sof pasuq from silent Ketiv onto Qere (D4)"),
    (("heb-mam-aleppo",), "ezekiel", 16, 25, "אֶת־תַּזְנוּתָֽיִךְ (תזנותך)׃$", "אֶת־תַּזְנוּתָֽיִךְ׃ (תזנותך)",
     "move verse-ending sof pasuq from silent Ketiv onto Qere (D4)"),
    (("heb-mam-aleppo",), "isaiah", 30, 32, "נִלְחַם־בָּֽם (בה)׃$", "נִלְחַם־בָּֽם׃ (בה)",
     "move verse-ending sof pasuq from silent Ketiv onto Qere (D4)"),
    (("heb-mam-aleppo",), "nehemiah", 11, 17, "בֶּן־יְדוּתֽוּן (ידיתון)׃$", "בֶּן־יְדוּתֽוּן׃ (ידיתון)",
     "move verse-ending sof pasuq from silent Ketiv onto Qere (D4)"),
    (("heb-mam-aleppo",), "psalms", 105, 28, "אֶת־דְּבָרֽוֹ (דבריו)׃$", "אֶת־דְּבָרֽוֹ׃ (דבריו)",
     "move verse-ending sof pasuq from silent Ketiv onto Qere (D4)"),
    # Stage 1 Accuracy Audit (24 Nov 2026) — Greek OT & NT P0 mechanical/polytonic/numeral typos & P1 proper names:
    (("grk-brenton-sixtine",), "leviticus", 8, 29, "προσέῤῥνεν", "προσέρρανεν",
     "προσέρρανεν (Brenton USFM OCR omission of α; corroborated by Swete, Rahlfs, & LXX-Orthodox)"),
    (("grk-brenton-sixtine",), "numbers", 21, 20, "πρέαβεις", "πρέσβεις",
     "πρέσβεις (Brenton USFM OCR α for σ; corroborated by Swete, Rahlfs, & LXX-Orthodox)"),
    (_CSV, "exodus", 21, 22, "ἀξιώματος·.$", "ἀξιώματος·",
     "ἀξιώματος· (double stop ·. in Swete-Amicarelli; 1st1K-LXX, Swete Clean, & Brenton have single stop)"),
    (_CSV, "1-samuel", 19, 21, "αὐτοί·.$", "αὐτοί.",
     "αὐτοί. (double stop ·. in Swete-Amicarelli; 1st1K-LXX, Swete Clean, & Brenton have single stop)"),
    (_OCR, "judges", 9, 33, "ὅσα ἀν’ εὕρῃ", "ὅσα ἂν εὕρῃ",
     "ὅσα ἂν εὕρῃ (stray apostrophe & accent slip on unelided ἂν in OCR; corroborated by Brenton, Rahlfs, & Orthodox)"),
    (_OCR, "joel", 3, 15, "φέγγος αὐτῶυ.", "φέγγος αὐτῶν.",
     "φέγγος αὐτῶν. (Swete OCR υ for ν in Joel 3:15 = 4:15; corroborated by Swete-Amicarelli, Brenton, Rahlfs, & LXX-Orthodox)"),
    (("grk-nt-kjtr",), "matthew", 23, 14, "προσευχόμενοι: διὰ", "προσευχόμενοι· διὰ",
     "προσευχόμενοι· διὰ (ASCII colon in CNTR KJTR; TR-Scrivener has Greek raised dot ·)"),
    (_ALL, "psalms", 106, 24, "εἶδοσαν", "εἴδοσαν",
     "εἴδοσαν (impossible antepenult circumflex in Swete; corroborated by Rahlfs εἴδοσαν)"),
    (_CSV, "genesis", 25, 32, "εἶπεν δε Ἠσαύ", "εἶπεν δὲ Ἠσαύ",
     "εἶπεν δὲ Ἠσαύ (missing grave accent in Swete-Amicarelli; corroborated by 1st1K-LXX, Swete Clean, & Rahlfs)"),
    (_OCR, "sirach", 33, 37, "πολλὴν γαρ κακίαν", "πολλὴν γὰρ κακίαν",
     "πολλὴν γὰρ κακίαν (missing grave accent in Swete OCR; corroborated by Swete-Amicarelli, Brenton, Rahlfs, & Orthodox)"),
    (("grk-brenton-sixtine",), "deuteronomy", 25, 16, "σου πας ποιῶν ταῦτα, πας ποιῶν ἄδικον.", "σου πᾶς ποιῶν ταῦτα, πᾶς ποιῶν ἄδικον.",
     "πᾶς … πᾶς (missing circumflex accents in Brenton-only verse; corroborated by Rahlfs & LXX-Orthodox)"),
    (("grk-brenton-sixtine",), "deuteronomy", 23, 3, "ἐκκλησίαν Κύριου.", "ἐκκλησίαν Κυρίου.",
     "Κυρίου (impossible proparoxytone with long ultima in Brenton-only verse; corroborated by Rahlfs & LXX-Orthodox)"),
    (_OCR + ("grk-brenton-sixtine",), "1-kings", 22, 8, "ὄτι", "ὅτι",
     "ὅτι (smooth breathing typo in OCR & Brenton; corroborated by Swete-Amicarelli, Rahlfs, & LXX-Orthodox)"),
    (_CSV, "2-kings", 11, 21, "ἐτῶν ἐπτὰ Ἰωὰς", "ἐτῶν ἑπτὰ Ἰωὰς",
     "ἑπτὰ (smooth breathing typo in Swete-Amicarelli; corroborated by Rahlfs & LXX-Orthodox)"),
    (("grk-brenton-sixtine",), "2-kings", 12, 1, "Υἱὸς ἐπτὰ ἐτῶν", "Υἱὸς ἑπτὰ ἐτῶν",
     "ἑπτὰ (smooth breathing typo in Brenton USFM; corroborated by Rahlfs & LXX-Orthodox)"),
    (_ALL, "1-maccabees", 8, 13, "ἃν", "ἂν",
     "ἂν (rough breathing typo in Swete; corroborated by Brenton, Rahlfs, & LXX-Orthodox)"),
    (_OCR + ("grk-brenton-sixtine",), "1-maccabees", 15, 5, "νῦν οὗν", "νῦν οὖν",
     "οὖν (rough breathing typo in OCR & Brenton; corroborated by Swete-Amicarelli, Rahlfs, & LXX-Orthodox)"),
    (_OCR + ("grk-brenton-sixtine",), "jeremiah", 4, 13, "τὰ ἄρματα", "τὰ ἅρματα",
     "ἅρματα (smooth breathing typo in OCR & Brenton; corroborated by Swete-Amicarelli, Rahlfs, & LXX-Orthodox)"),
    (_CSV + ("grk-brenton-sixtine",), "genesis", 49, 1, "τῶν ἡμέρων.", "τῶν ἡμερῶν.",
     "ἡμερῶν (1st-decl. gen. pl. perispomenon; corroborated by Rahlfs & LXX-Orthodox)"),
    (_ALL, "judges", 7, 9, "Ἀνάστας", "Ἀναστὰς",
     "Ἀναστὰς (aorist active participle is oxytone; corroborated by Rahlfs & LXX-Orthodox)"),
    (_ALL, "1-chronicles", 28, 21, "τῶν Λευείτων", "τῶν Λευειτῶν",
     "Λευειτῶν (1st-decl. gen. pl. perispomenon; matches Λευειτῶν 60x elsewhere in Swete)"),
    (_ALL + ("grk-brenton-sixtine",), "nehemiah", 11, 26, "ἐν Ἰησοὺ", "ἐν Ἰησοῦ",
     "Ἰησοῦ (grave for circumflex; matches Ἰησοῦ 367x elsewhere & LXX-Orthodox)"),
    (_CSV, "nehemiah", 7, 41, "ας᾽ τεσσεράκοντα", "͵ασ᾽ τεσσεράκοντα",
     "͵ασ᾽ = 1,200 (Swete dropped lower keraia ͵ and printed stigma ς for σ; Brenton, Rahlfs, & Orthodox read χίλιοι διακόσιοι)"),
    (_OCR, "nehemiah", 7, 41, "ας΄ τεσσεράκοντα", "͵ασ΄ τεσσεράκοντα",
     "͵ασ΄ = 1,200 (Swete OCR dropped lower keraia ͵ and printed stigma ς for σ; Brenton, Rahlfs, & Orthodox read χίλιοι διακόσιοι)"),
    (_ALL, "ezra", 2, 37, "Ἐμμήρ, α πεντήκοντα", "Ἐμμήρ, ͵α πεντήκοντα",
     "͵α = 1,000 (Swete dropped lower keraia ͵ on numeral 1,000; Brenton, Rahlfs, & Orthodox read χίλιοι)"),
    (_ALL, "ezra", 2, 38, "Φασσούρ, α διακόσιοι", "Φασσούρ, ͵α διακόσιοι",
     "͵α = 1,000 (Swete dropped lower keraia ͵ on numeral 1,000; Brenton, Rahlfs, & Orthodox read χίλιοι)"),
    (_CSV, "nehemiah", 7, 70, "χρυσοῦς, α, φιάλας", "χρυσοῦς, ͵α, φιάλας",
     "͵α = 1,000 (Swete-Amicarelli dropped lower keraia ͵ on numeral 1,000; Brenton, Rahlfs, & Orthodox read χιλίους)"),
    (_OCR, "nehemiah", 7, 70, "χρυσοῦς α, φιάλας", "χρυσοῦς ͵α, φιάλας",
     "͵α = 1,000 (Swete OCR dropped lower keraia ͵ on numeral 1,000; Brenton, Rahlfs, & Orthodox read χιλίους)"),
    # Stage 1 Greek P1 safe lowercase proper names & NT proper-name diacritics:
    (("grk-brenton-sixtine",), "2-kings", 25, 10, "τῶν χαλδαίων.", "τῶν Χαλδαίων.",
     "Χαλδαίων (proper gentilic capitalised; corroborated by Rahlfs & LXX-Orthodox)"),
    (_CSV, "1-chronicles", 5, 12, "ἐν βασάν.", "ἐν Βασάν.",
     "Βασάν (proper place name capitalised; corroborated by 1st1K-LXX, Swete Clean, Brenton, Rahlfs, & Orthodox)"),
    (_CSV, "2-chronicles", 23, 18, "καὶ τῶν λευειτῶν,", "καὶ τῶν Λευειτῶν,",
     "Λευειτῶν (proper tribal name capitalised; corroborated by 1st1K-LXX, Swete Clean, Brenton, & same verse)"),
    (_CSV, "1-maccabees", 4, 9, "αὐτοὺς φαραὼ", "αὐτοὺς Φαραὼ",
     "Φαραὼ (proper royal title capitalised; corroborated by 1st1K-LXX, Swete Clean, Brenton, Rahlfs, & Orthodox)"),
    (_CSV, "jeremiah", 43, 10, "ἀνεγίνωσκε βαροὺχ", "ἀνεγίνωσκε Βαροὺχ",
     "Βαροὺχ (proper name capitalised; corroborated by 1st1K-LXX, Swete Clean, Brenton, Rahlfs, & Orthodox)"),
    (_CSV, "micah", 6, 5, "κατὰ σοῦ βαλὰκ", "κατὰ σοῦ Βαλὰκ",
     "Βαλὰκ (proper name capitalised; corroborated by 1st1K-LXX, Swete Clean, Brenton, Rahlfs, & Orthodox)"),
    (("grk-brenton-sixtine",), "nehemiah", 12, 17, "τῷ βαλγὰς,", "τῷ Βαλγὰς,",
     "Βαλγὰς (proper name capitalised in Brenton-only verse; corroborated by Rahlfs & LXX-Orthodox)"),
    (("grk-brenton-sixtine",), "nehemiah", 12, 19, "Ματθαναΐ τῷ Ἐδίῳ,", "Ματθαναΐ· τῷ Ἐδίῳ,",
     "Ματθαναΐ· (missing raised-dot separator in Brenton USFM; corroborated by Rahlfs & LXX-Orthodox)"),
    (("grk-brenton-sixtine",), "nehemiah", 12, 20, "Τῷ Σαλαῒ, καλλαΐ·", "Τῷ Σαλαῒ, Καλλαΐ·",
     "Καλλαΐ (proper name capitalised in Brenton-only verse; corroborated by Rahlfs & LXX-Orthodox)"),
    (_OCR, "1-chronicles", 1, 51, "ἠγεμὼν Θαιμάν", f"{_G} Θαιμάν",
     "ἡγεμὼν (smooth breathing OCR slip in 1st1K/Swete Clean; Swete-Amicarelli reads ἡγεμὼν)"),
    (_OCR, "numbers", 21, 21, "Ἀμορεἰρηνικοῖς ραίων", _G,
     "Ἀμορραίων (OCR line-splice corruption in 1st1K/Swete Clean; Swete-Amicarelli reads Ἀμορραίων)"),
    (_OCR, "sirach", 42, 1, "εὑρίσκαων", _G,
     "εὑρίσκων (extra α OCR slip in 1st1K/Swete Clean; Swete-Amicarelli reads εὑρίσκων)"),
    (_OCR, "1-kings", 6, 18, "κιβωτν", _G,
     "κιβωτὸν (dropped ὸ OCR slip in 1st1K/Swete Clean; Swete-Amicarelli reads κιβωτὸν)"),
    (("grk-nt-sblgnt",), "john", 19, 13, "Ἑβραϊστὶ δὲ Γαββαθα.", "Ἑβραϊστὶ δὲ Γαββαθᾶ.",
     "Γαββαθᾶ (unaccented proper name in SBLGNT; corroborated by SRGNT, BHP, RP2018, & TR-Scrivener)"),
    (("grk-nt-kjtr",), "john", 19, 13, "Ἑβραϊστὶ δὲ, Γαββαθα.", "Ἑβραϊστὶ δὲ, Γαββαθᾶ.",
     "Γαββαθᾶ (unaccented proper name in CNTR KJTR; corroborated by SRGNT, BHP, RP2018, & TR-Scrivener)"),
    (("grk-nt-sblgnt",), "john", 20, 16, "Ἑβραϊστί· Ραββουνι", "Ἑβραϊστί· Ῥαββουνί",
     "Ῥαββουνί (missing rough breathing on initial Ρ & acute accent in SBLGNT; corroborated by Nestle1904, RP2018, THGNT, & TR-Scrivener)"),
)

# Swete divides some verses differently from Brenton, the numbering anchor, and the content
# alignment cannot move a clause across a division by itself. These moves put the clause in the copy
# into Brenton's verse, so it is collated with that verse instead of being printed in the wrong verse
# or twice. (copies, book, (chapter, verse), "head" or "tail", the exact clause, (chapter, verse) it
# moves to, how: "append" / "prepend" to an existing verse, or "new" for a number the copy lacks.)
# A move is made only while the copy still reads exactly so, which also makes it idempotent.
_DIVISIONS: Tuple[Tuple[Tuple[str, ...], str, Tuple[int, int], str, str, Tuple[int, int], str], ...] = (
    (_CSV, "joshua", (12, 21), "tail", "βασιλέα Μαρεδὼθ καὶ βασιλέα Ἰεκὸμ τοῦ Χερμέλ,", (12, 22), "new"),
    (_OCR, "joshua", (12, 21), "head", "βασιλέα Μαμρώθ, βασιλέα Ἀζείφ,", (12, 20), "append"),
    (_OCR, "joshua", (12, 22), "head", "βασιλέα Κάδης, βασιλέα Ζακάχ,", (12, 21), "new"),
    (_ALL, "judges", (2, 15), "head", "ἐν πᾶσιν οἷς ἐξεπορεύοντο.", (2, 14), "append"),
    (_CSV, "proverbs", (29, 45), "tail", "τὸ στόμα δὲ ἀνοίγει σοφοῖς νομοθέσμως, ἡ δὲ ἐλεημοσύνη αὐτῆς", (31, 27), "new"),
    (_OCR, "proverbs", (29, 45), "tail", "τὸ στόμα δὲ ἀνοίγει σοφοῖς νομοθέσμως,", (31, 27), "new"),
    (_OCR, "proverbs", (29, 46), "head", "ἡ δὲ ἐλεημοσύνη αὐτῆς", (31, 27), "append"),
    (_CSV, "ecclesiastes", (7, 25), "head", "καὶ αὕτη ἐμακρύνθη ἀπ᾽ ἐμοῦ·", (7, 24), "append"),
    (_CSV, "ecclesiastes", (8, 2), "tail", "μὴ σπουδάσῃς·", (8, 3), "prepend"),
    (_CSV, "ecclesiastes", (9, 1), "tail", "ματαιότης ἐν τοῖς πᾶσιν.", (9, 2), "prepend"),
    (_CSV, "song-of-songs", (7, 1), "head", "Τί ὄψεσθε ἐν τῇ Σουμανείτιδι; ἡ ἐρχομένη ὡς χοροὶ τῶν παρεμβολῶν.", (6, 12), "append"),
    (_OCR, "song-of-songs", (7, 1), "head", "Τί δψεοθε ἐν τῆ Σουμανείτιδις ἡ ἐρχομένη ὡς χοροὶ τῶν παρεμβολῶν.", (6, 12), "append"),
    (_CSV, "sirach", (1, 8), "tail", "Κύριος", (1, 9), "prepend"),
    (("grk-brenton-sixtine",), "nehemiah", (12, 18), "head", "Τῷ Ἰωαρὶβ,", (12, 19), "prepend"),
    (("grk-brenton-sixtine",), "nehemiah", (12, 17), "tail", "τῷ Βαλγὰς, Σαμουέ· τῷ Σεμία, Ἰωνάθαν·", (12, 18), "new"),
    # Stage 1 Accuracy Audit (24 Nov 2026) — Greek OT Swete-to-Brenton verse-division splits eliminating
    # cross-chapter misalignments and merged-verse clause duplications:
    (_ALL, "exodus", (39, 15), "head", "καὶ τὴν κιβωτὸν τῆς διαθήκης καὶ τοὺς διωστῆρας αὐτῆς,", (39, 14), "append"),
    (_ALL, "exodus", (39, 16), "head", "καὶ τὸ θυσιαστήριον καὶ πάντα τὰ σκεύη αὐτοῦ,", (39, 15), "new"),
    (_ALL, "numbers", (21, 18), "tail", "καὶ ἀπὸ φρέατος εἰς Μανθαναείν·", (21, 19), "prepend"),
    (_ALL, "numbers", (21, 20), "head", "καὶ ἀπὸ Βαμὼθ εἰς Ἰανήν, ἥ ἐστιν ἐν τῷ πεδίῳ Μωὰβ ἀπὸ κορυφῆς τοῦ λελαξευμένου, τὸ βλέπον κατὰ πρόσωπον τῆς ἐρήμου.", (21, 19), "append"),
    (_CSV, "numbers", (21, 21), "head", "Καὶ ἀπέστειλεν Μωυσῆς πρέσβεις πρὸς Σηὼν βασιλέα Ἀμορραίων λόγοις εἰρηνικοῖς λέγων", (21, 20), "new"),
    (_OCR, "numbers", (21, 21), "head", f"καὶ ἀπέστειλεν Μωυσῆς πρέσβεις πρὸς Σηὼν βασιλέα {_G} λόγοις εἰρηνικοῖς λέγων", (21, 20), "new"),
    (_ALL, "numbers", (21, 22), "head", "Παρελευσόμεθα διὰ τῆς γῆς σου· τῇ ὁδῷ πορευσόμεθα, οὐκ ἐκκλινοῦμεν οὔτε εἰς ἀγρὸν οὔτε εἰς ἀμπελῶνα,", (21, 21), "new"),
    (_CSV, "numbers", (27, 4), "head", "μὴ ἐξαλειφθήτω τὸ ὄνομα τοῦ πατρὸς ἡμῶν ἐκ μέσου τοῦ δήμου αὐτοῦ, ὅτι οὐκ ἔστιν αὐτῷ υἱός· δότε ἡμῖν κατάσχεσιν ἐν μέσῳ ἀδελφῶν πατρὸς ἡμῶν.", (27, 3), "append"),
    (_OCR, "numbers", (27, 4), "head", "μὴ ἐξαλειφθήτω τὸ ὄνομα τοῦ πατρὸς ἡμῶν ἐκ μέσου τοῦ δήμου αὐτοῦ, ὅτι οὐκ ἔστιν αὐτῷ υἱός· δότε ἡμῖν κατάσῳ ἀδελφῶν πατρὸς ἡμῶν.", (27, 3), "append"),
    (_CSV, "numbers", (27, 5), "head", "καὶ προσήγαγεν Μωυσῆς τὴν κρίσιν αὐτῶν ἔναντι Κυρίου.", (27, 4), "new"),
    (_OCR, "numbers", (27, 5), "head", "καὶ προσήγαγεν Μωυσῆς κρίσιν αὐτῶν ἔναντι Κυρίου.", (27, 4), "new"),
    (_CSV, "numbers", (27, 6), "head", "καὶ ἐλάλησεν Κύριος πρὸς Μωυσῆν", (27, 5), "new"),
    (_OCR, "numbers", (27, 6), "head", "καὶ ἐλάλησεν κύριος πρὸς Μωυσῆν", (27, 5), "new"),
    (_CSV, "numbers", (27, 7), "head", "Ὀρθῶς θυγατέρες Σαλπαὰδ λελαλήκασιν· δόμα δώσεις αὐταῖς κατάσχεσιν κληρονομίας ἐν μέσῳ ἀδελφῶν πατρὸς αὐτῶν, καὶ περιθήσεις τὸν κλῆρον τοῦ πατρὸς αὐτῶν αὐταῖς.", (27, 6), "append"),
    (_OCR, "numbers", (27, 7), "head", "δόμα δώσεις αὐταῖς κληρονομίας ἐν μέσῳ ἀδελφῶν πατρὸς αὐτῶν, καὶ περ θήσεις τὸν κλῆρον τοῦ πατρὸς αὐτῶν αὐταῖς.", (27, 6), "append"),
    (_ALL, "numbers", (27, 8), "head", "καὶ τοῖς υἱοῖς Ἰσραὴλ λαλήσεις", (27, 7), "new"),
    (_CSV, "1-kings", (6, 18), "tail", "δοῦναι ἐκεῖ τὴν κιβωτὸν διαθήκης Κυρίου.", (6, 19), "new"),
    (_OCR, "1-kings", (6, 18), "tail", f"δοῦναι ἐκεῖ τὴν {_G} διαθήκης Κυρίου.", (6, 19), "new"),
    (_CSV, "1-chronicles", (1, 51), "head", "καὶ ἀπέθανεν Ἁδδά, καὶ ἐβασίλευσεν ἀντ᾽ αὐτοῦ Σαμαὰ ἐκ Μασέκκας· καὶ ἀπέθανεν Σαμαά, καὶ ἐβασίλευσεν ἀντ᾽ αὐτοῦ Σαοὺλ ἐκ Ῥοβὼθ τῆς παρὰ ποταμόν. καὶ ἀπέθανεν Σαούλ.", (1, 48), "new"),
    (_OCR, "1-chronicles", (1, 51), "head", "καὶ ἀπέθανεν Ἀδδά καὶ ἐβασίλευσεν ἀντʼ αὐτοῦ Σαμαὰ ἐκ Μασέκκας· καὶ ἀπέθανεν Σαμαά, καὶ ἐβασίλευσεν ἀντʼ αὐτοῦ Σαοὺλ ἐκ Ῥοβὼθ τῆς παρὰ ποταμόν. καὶ ἀπέθανεν Σαούλ.", (1, 48), "new"),
    (_ALL, "1-chronicles", (12, 4), "tail", "Ἰερμίας καὶ Ἰεζὴλ καὶ Ἰωανὰν καὶ Ἰωαζαβὰβ ὁ Γαδαραθειείμ,", (12, 5), "new"),
    (_ALL, "nehemiah", (12, 8), "tail", "εἰς τὰς ἐφημερίας.", (12, 9), "new"),
    (_CSV, "job", (41, 1), "tail", "οὐδὲ δέδοικας ὅτι ἡτοίμασταί μοι;", (41, 2), "new"),
    (_OCR, "job", (41, 1), "tail", "οὐδὲ δέδοικας ὅτι ἡτοίμασταί μοι", (41, 2), "new"),
    (_ALL, "job", (41, 3), "head", "τίς γάρ ἐστιν ὁ ἐμοὶ ἀντιστάς;", (41, 2), "append"),
    (_CSV, "psalms", (12, 2), "head", "Ἕως πότε, Κύριε, ἐπιλήσῃ μου εἰς τέλος; ἕως πότε ἀποστρέψεις τὸ πρόσωπόν σου ἀπ᾽ ἐμοῦ;", (12, 1), "append"),
    (_OCR, "psalms", (12, 2), "head", "Ἕως πότε, Κύριε, ἐπιλήσῃ μου εἰς τέλος; ἕως πότε ἀποστρέψεις τὸ πρόσωπόν σου ἀπʼ ἐμοῦ;", (12, 1), "append"),
    (_CSV, "psalms", (12, 3), "head", "ἕως τίνος θήσομαι βουλὰς ἐν ψυχῇ μου, ὀδύνας ἐν καρδίᾳ μου ἡμέρας; ἕως πότε ὑψωθήσεται ὁ ἐχθρός μου ἐπ᾽ ἐμέ;", (12, 2), "new"),
    (_OCR, "psalms", (12, 3), "head", "ἕως τίνος θήσομαι βουλὰς ἐν ψυχῇ μου, ὀδύνας ἐν καρδίᾳ μου ἡμέρας; ἕως πότε ὑψωθήσεται ὁ ἐχθρός μου ἐπʼ ἐμέ;", (12, 2), "new"),
    (_CSV, "psalms", (12, 4), "head", "ἐπίβλεψον, εἰσάκουσόν μου, Κύριε ὁ θεός μου· φώτισον τοὺς ὀφθαλμούς, μή ποτε ὑπνώσω εἰς θάνατον,", (12, 3), "new"),
    (_OCR, "psalms", (12, 4), "head", "ἐπίβλεψον, εἰσάκουσόν μου, Κύριε ὁ θεός μου· φώτισον τοὺς ὀφθαλμούς, μὴ ποτε ὑπνώσω εἰς θάνατον,", (12, 3), "new"),
    (_ALL, "psalms", (12, 5), "head", "μή ποτε εἴπῃ ὁ ἐχθρός μου Ἴσχυσα πρὸς αὐτόν· οἱ θλίβοντές με ἀγαλλιάσονται ἐὰν σαλευθῶ.", (12, 4), "new"),
    (_ALL, "psalms", (12, 6), "head", "ἐγὼ δὲ ἐπὶ τῷ ἐλέει σου ἤλπισα· ἀγαλλιάσεται ἡ καρδία μου ἐν τῷ σωτηρίῳ σου·", (12, 5), "new"),
    (_ALL, "sirach", (42, 1), "head", "ἀπὸ δευτερώσεως καὶ λόγου ἀκοῆς, καὶ ἀπὸ ἀποκαλύψεων λόγων κρυφίων·", (41, 23), "new"),
    (_CSV, "sirach", (42, 1), "head", "καὶ ἔσῃ αἰσχυντηρὸς ἀληθινῶς, καὶ εὑρίσκων χάριν ἔναντι παντὸς ἀνθρώπου.", (41, 24), "new"),
    (_OCR, "sirach", (42, 1), "head", f"καὶ ἔσῃ αἰσχυντηρὸς ἀληθινῶς, καὶ {_G} χάριν ἔναντι παντὸς ἀνθρώπου.", (41, 24), "new"),
    (_ALL, "ezekiel", (21, 19), "head", "Καὶ σύ, υἱὲ ἀνθρώπου, διάταξον σεαυτῷ δύο ὁδοὺς", (21, 20), "prepend"),
    (_CSV, "ezekiel", (21, 20), "tail", "τοῦ εἰσελθεῖν ῥομφαίαν ἐπὶ Ῥαββὰθ υἱῶν Ἀμμὼν καὶ ἐπὶ τὴν Ἰουδαίαν καὶ ἐπὶ Ἰερουσαλὴμ ἐν μέσῳ αὐτῆς.", (21, 25), "new"),
    (_OCR, "ezekiel", (21, 20), "tail", "τοῦ εἰσελθεῖν ῥομφαίαν ἐπὶ Ῥαββὰθ υἱῶν Ἀμμῶν καὶ ἐπὶ τὴν Ἰουδαίαν καὶ ἐπὶ Ἰερουσαλὴμ ἐν μέσῳ αὐτῆς.", (21, 25), "new"),
)
_DIVISION_WHY = {
    "exodus": "Swete places Brenton's 39:15 ('καὶ τὸ θυσιαστήριον …') at the start of 39:16; moving 39:15 onto 39:14 and 39:16a into 39:15 preserves the Ark clause and prevents cross-chapter mis-alignment with 40:8",
    "leviticus": "Swete's 8:18–30 stand one verse ahead of Brenton's 8:18–29 (Codex B omits Brenton 8:30); aligning 8:18–30 to Brenton's verse divisions prevents 8:28 from absorbing 8:29 and 8:30 from being truncated",
    "numbers": "Swete numbers Brenton's 17:1–15 as 16:36–50 and 17:16–28 as 17:1–13, and divides 21:18–22 and 27:3–8 differently from Brenton",
    "joshua": "the list of kings in 12:20–22 is divided differently in each copy and in Brenton",
    "judges": "Swete opens 2:15 with 'ἐν πᾶσιν οἷς ἐξεπορεύοντο', which Brenton ends 2:14 with",
    "1-kings": "Swete attaches Brenton's 6:19 ('δοῦναι ἐκεῖ τὴν κιβωτὸν διαθήκης Κυρίου.') to the end of 6:18",
    "1-chronicles": "Swete numbers 1 Chr 6:1–15 as Brenton 5:27–41 and 6:16–81 as 6:1–66, places Edomite king clauses in 1:51, and attaches Brenton's 12:5 to the tail of 12:4",
    "nehemiah": "Swete ends 12:8 with Brenton's 12:9 ('εἰς τὰς ἐφημερίας.'); Brenton USFM ran 12:18 into 12:17 and split 12:19 across 12:18–19",
    "job": "Swete divides 41:1–2 across Brenton's 41:1–3",
    "psalms": "Swete's 12:1–6 stand one verse offset from Brenton's 12:1–6",
    "proverbs": "Swete prints Brenton's 31:27 ('τὸ στόμα δὲ ἀνοίγει … ἡ δὲ ἐλεημοσύνη αὐτῆς') inside its 29:45–46",
    "ecclesiastes": "Swete's verse divisions in 7:24–25, 8:2–3 and 9:1–2 differ from Brenton's",
    "song-of-songs": "Swete opens 7:1 with 'Τί ὄψεσθε … παρεμβολῶν', which Brenton ends 7:1 (Swete 6:12) with",
    "sirach": "Swete ends 1:8 with 'Κύριος' opening 1:9 and begins 42:1 with Brenton's 41:23–24",
    "ezekiel": "Swete divides 21:19–20 across Brenton's 21:24–25",
    "daniel": "Swete prints the springs (3:77) before the seas and rivers (3:78); Brenton numbers them the other way round",
}
# Whole runs renumbered to Brenton's numbering, in order: (witness id, book) -> [(chapter, first, last,
# new chapter, new first)]. Made only when every verse of every run is there and every new number free.
_RENUMBER = {
    ("grk-swete-csv", "numbers"): [(17, 1, 13, 17, 16), (16, 36, 50, 17, 1)],
    ("grk-brenton-sixtine", "proverbs"): [(24, 35, 53, 30, 15), (24, 54, 62, 31, 1)],
    ("grk-swete-csv", "1-chronicles"): [(6, 1, 15, 5, 27), (6, 16, 72, 6, 1), (6, 74, 81, 6, 59), (12, 5, 40, 12, 6)],
    ("grk-1st1k-lxx", "1-chronicles"): [(6, 1, 15, 5, 27), (6, 16, 72, 6, 1), (6, 74, 81, 6, 59), (12, 5, 7, 12, 6), (12, 9, 40, 12, 10)],
    ("grk-swete-lxx", "1-chronicles"): [(6, 1, 15, 5, 27), (6, 16, 72, 6, 1), (6, 74, 81, 6, 59), (12, 5, 7, 12, 6), (12, 9, 40, 12, 10)],
    ("grk-swete-csv", "1-kings"): [(6, 19, 34, 6, 20)],
    ("grk-1st1k-lxx", "1-kings"): [(6, 19, 34, 6, 20)],
    ("grk-swete-lxx", "1-kings"): [(6, 19, 34, 6, 20)],
    ("grk-swete-csv", "job"): [(41, 2, 25, 41, 3)],
    ("grk-1st1k-lxx", "job"): [(41, 2, 25, 41, 3)],
    ("grk-swete-lxx", "job"): [(41, 2, 25, 41, 3)],
    ("grk-swete-csv", "ezekiel"): [(21, 21, 32, 21, 26)],
    ("grk-1st1k-lxx", "ezekiel"): [(21, 21, 32, 21, 26)],
    ("grk-swete-lxx", "ezekiel"): [(21, 21, 32, 21, 26)],
}
_RENUMBER_WHY = {
    ("grk-brenton-sixtine", "proverbs"): (
        "Saints.Bible numbering: the site numbers Proverbs as Rahlfs does, with Hebrew chapter and verse numbers in "
        "the Greek order (24:1–22e, 30:1–14, 24:23–34, 30:15–33, 31:1–9, 25–29, 31:10–31); the Brenton e-text runs "
        "30:1–33 and 31:1–9 on as 24:22–62 and leaves chapter 30 empty"),
}

# Saints.Bible numbering for the versification anchor (Brenton). The Brenton e-text runs 30:1–14 into one
# 283-word verse 24:22 without verse marks. It is cut where each verse of 30:1–14 begins (Brenton's own
# words, matching the verse divisions of the site's English and of Swete's 24:24–37); the text before
# the first cut stays 24:22 (with 22a–e). Made only when every opening occurs once, in this order.
_SPLITS = {
    ("grk-brenton-sixtine", "proverbs"): ((24, 22), 30, (
        "τοὺς ἐμοὺς λόγους υἱὲ φοβήθητι,", "Ἀφρονέστατος γάρ εἰμι", "Θεὸς δεδίδαχέ με σοφίαν,",
        "Τίς ἀνέβη εἰς τὸν οὐρανὸν", "Πάντες γὰρ λόγοι Θεοῦ", "Μὴ προσθῇς τοῖς λόγοις αὐτοῦ,",
        "Δύο αἰτοῦμαι παρὰ σοῦ,", "Μάταιον λόγον καὶ ψευδῆ", "Ἵνα μὴ πλησθεὶς ψευδὴς",
        "Μὴ παραδῷς οἰκέτην", "Ἔκγονον κακὸν πατέρα", "Ἔκγονον κακὸν δίκαιον",
        "Ἔκγονον κακὸν ὑψηλοὺς", "Ἔκγονον κακὸν μαχαίρας",
    )),
}


def _copy_chapter(result, chapters, ch):
    if result is chapters:
        result = dict(chapters)
    if result.get(ch) is chapters.get(ch):
        result[ch] = dict(chapters.get(ch, {}))
    return result


def _apply_slips(wid, book_slug, chapters, original, notes):
    result = chapters
    for copies, book, ch, v, old, new, swete in _SLIPS:
        if wid not in copies or book != book_slug:
            continue
        text = result.get(ch, {}).get(v)
        if not text:
            continue
        anchored = old.startswith("^")
        end_anchored = old.endswith("$")
        needle = old[1 if anchored else 0 : (-1 if end_anchored else None)]
        if text.count(needle) != 1 or (anchored and not text.startswith(needle)) or (end_anchored and not text.endswith(needle)):
            continue
        result = _copy_chapter(result, original, ch)
        result[ch][v] = text.replace(needle, new, 1)
        how = ("'[…]' casts no vote, so the other copies of Swete decide" if GAP_WORD in new else
               "'…' marks text this copy lost: its omissions in this verse are not evidence" if LACUNA_MARK in new else
               "verified import repair applied")
        src_note = f"Swete prints {swete}" if wid in _ALL else swete
        notes.setdefault(ch, []).append(
            f"Source import repair, {ch}:{v}: '{needle}' → '{new}' ({src_note}). "
            f"{how}. Original file unchanged.")
    return result


def _apply_split(wid, book_slug, chapters, original, notes):
    spec = _SPLITS.get((wid, book_slug))
    if not spec:
        return chapters
    (ch, v), nch, openings = spec
    text = chapters.get(ch, {}).get(v, "")
    cuts, pos = [], 0
    for opening in openings:
        if text.count(opening) != 1 or text.find(opening) < pos:
            return chapters  # the copy no longer reads as recorded (or the split was already made)
        pos = text.find(opening)
        cuts.append(pos)
    if not cuts or any(chapters.get(nch, {}).get(n) for n in range(1, len(cuts) + 1)):
        return chapters
    result = _copy_chapter(_copy_chapter(chapters, original, ch), original, nch)
    result[ch][v] = text[: cuts[0]].strip()
    for n, (a, b) in enumerate(zip(cuts, cuts[1:] + [len(text)]), start=1):
        result[nch][n] = text[a:b].strip()
    notes.setdefault(nch, []).append(
        f"Source division repair: {ch}:{v} cut into {ch}:{v} and {nch}:1–{len(cuts)} where each verse opens "
        f"({_RENUMBER_WHY.get((wid, book_slug), '')}). No word added or dropped. Original file unchanged.")
    return result


def _apply_divisions(wid, book_slug, chapters, original, notes):
    result = _apply_split(wid, book_slug, chapters, original, notes)
    runs = _RENUMBER.get((wid, book_slug), [])
    if runs:
        trial = {c: set(vs) for c, vs in result.items()}
        ok = True
        for c, a, b, nc, na in runs:
            if not all(v in trial.get(c, set()) and result.get(c, {}).get(v) for v in range(a, b + 1)):
                ok = False
                break
            trial[c] -= set(range(a, b + 1))
            new = set(range(na, na + b - a + 1))
            if new & trial.get(nc, set()):
                ok = False
                break
            trial.setdefault(nc, set()).update(new)
        if ok:
            for c, a, b, nc, na in runs:
                result = _copy_chapter(_copy_chapter(result, original, c), original, nc)
                moving = {v: result[c].pop(v) for v in range(a, b + 1)}
                for v, t in moving.items():
                    result[nc][na + v - a] = t
                notes.setdefault(nc, []).append(
                    f"Source division repair: verses {c}:{a}–{b} renumbered {nc}:{na}–{na + b - a} "
                    f"({_RENUMBER_WHY.get((wid, book_slug)) or 'Brenton' + chr(39) + 's numbering; ' + _DIVISION_WHY.get(book_slug, '')}). "
                    "Original file unchanged.")
    if wid in _ALL and book_slug == "daniel":
        a, b = result.get(3, {}).get(77, ""), result.get(3, {}).get(78, "")
        if "πηγαί" in a and "θάλασσαι" in b and "πηγαί" not in b and "θάλασσαι" not in a:
            result = _copy_chapter(result, original, 3)
            result[3][77], result[3][78] = b, a
            notes.setdefault(3, []).append(
                f"Source division repair: 3:77 and 3:78 exchanged ({_DIVISION_WHY['daniel']}). Original file unchanged.")
    if wid in _ALL and book_slug == "leviticus":
        ch8 = result.get(8, {})
        head_21 = next(
            (h for h in (
                "καὶ τὴν κοιλίαν καὶ τούς πόδας ἔπλυνεν ὕδατι,",
                "καὶ τὴν κοιλίαν καὶ τοὺς πόδας ἔπλυνεν ὕδατι,",
            ) if ch8.get(21, "").startswith(h + " ")),
            "",
        )
        if (all(ch8.get(v) for v in range(18, 31))
                and head_21
                and ch8[19].startswith("καὶ ἔσφαξεν Μωυσῆς τὸν κριόν")
                and "προσέρανεν" in ch8[30]):
            result = _copy_chapter(result, original, 8)
            result[8][18] = f"{ch8[18]} {ch8[19]}"
            snap_20 = f"{ch8[20]} {head_21}"
            snap_21 = ch8[21][len(head_21):].strip()
            snap_rest = {v: ch8[v] for v in range(22, 31)}
            result[8][19] = snap_20
            result[8][20] = snap_21
            for v in range(22, 31):
                result[8][v - 1] = snap_rest[v]
            del result[8][30]
            notes.setdefault(8, []).append(
                f"Source division repair: 8:18–30 aligned to Brenton's 8:18–29 ({_DIVISION_WHY['leviticus']}). "
                "Original file unchanged.")
    for copies, book, (ch, v), part, clause, (tch, tv), how in _DIVISIONS:
        if wid not in copies or book != book_slug:
            continue
        text = result.get(ch, {}).get(v) or ""
        if part == "head" and (text == clause or text.startswith(clause + " ")):
            rest = text[len(clause):].strip()
        elif part == "tail" and (text == clause or text.endswith(" " + clause)):
            rest = text[: len(text) - len(clause)].strip()
        else:
            continue  # the copy no longer reads as recorded (or the move was already made)
        target = result.get(tch, {}).get(tv)
        if (how == "new") == bool(target):
            continue  # "new" needs a free number, "append" / "prepend" an existing verse
        result = _copy_chapter(_copy_chapter(result, original, ch), original, tch)
        if how == "prepend":
            result[tch][tv] = f"{clause} {target}"
        elif how == "append":
            result[tch][tv] = f"{target} {clause}"
        else:
            result[tch][tv] = clause
        if rest:
            result[ch][v] = rest
        else:
            del result[ch][v]
        notes.setdefault(tch, []).append(
            f"Source division repair: '{clause}' moved from {ch}:{v} to {tch}:{tv} "
            f"({_DIVISION_WHY.get(book, '')}). No word added or dropped. Original file unchanged.")
    return result


def repair_documented_imports(witness, book_slug, chapters):
    """Return a copy on repair, plus notes keyed by source chapter.

The raw parser output remains accessible. Explicit gaps describe lost digital
text, not a claim that the printed edition or its manuscript lacks the words.
Content-based alignment still handles the erroneous source number 88:84.
Each repair checks the exact recorded text first, so applying it twice changes nothing.
"""
    wid = str(witness["id"])
    notes: Dict[int, List[str]] = {}
    result = chapters
    gaps = _FILE_GAPS.get((wid, witness["parser_kind"]), [])
    if gaps:
        for book, ch, v, opening, lost in gaps:
            text = result.get(ch, {}).get(v, "") if book == book_slug else ""
            if text.startswith(opening):
                result = _copy_chapter(result, chapters, ch)
                result[ch][v] = f"{LACUNA_MARK} {text}"
                notes.setdefault(ch, []).append(
                    f"Source file gap, {ch}:{v}: the file leaves out {lost}, which the printed edition has; marked "
                    "lost (…), so it is not recorded as the edition's omission. Original file unchanged.")
    if _REPAIRABLE_COPIES.get(wid) != witness["parser_kind"]:
        return result, notes
    if wid in _OCR_COPIES and book_slug == "2-kings" and chapters.get(23, {}).get(31) == _KINGS_PREFIX + _KINGS_TAIL:
        result = _copy_chapter(result, chapters, 23)
        result[23][31] = LACUNA_MARK + " " + _KINGS_TAIL
        notes[23] = [
            "Source import repair, 23:31: excluded the intrusive apparatus prefix "
            f"'{_KINGS_PREFIX.strip()}'. It duplicates the note on 23:24, not verse text "
            "(Swete I, 1887, p. 797). Marked the missing digital opening with …; "
            "did not supply words from another witness. Original file unchanged."
        ]
    if (wid in _OCR_COPIES and book_slug == "psalms" and chapters.get(88, {}).get(46) == _PSALM_46
            and chapters.get(88, {}).get(84) == _PSALM_84):
        result = _copy_chapter(result, chapters, 88)
        result[88][46] = _PSALM_46 + " διάψαλμα."
        result[88][84] = _PSALM_84.replace(" διάψαλμα.", "", 1)
        notes[88] = [
            "Source import repair, 88:46/84: moved 'διάψαλμα.' from inside the "
            "misnumbered source 88:84 (= 88:48) to the end of 88:46. Swete II "
            "(1907), p. 334 places it there, corroborated by the keyed transcription. "
            "The separate διάψαλμα in 88:49 is untouched. Original file unchanged."
        ]
    result = _apply_slips(wid, book_slug, result, chapters, notes)
    return _apply_divisions(wid, book_slug, result, chapters, notes), notes


def coverage_gap_detail(language, book_slug, chapter):
    """Explain known local gaps only after all admitted witnesses were checked."""
    if language == "hebrew" and book_slug == "sirach":
        if int(chapter) in (2, 17, 24, 28, 29):
            return (f"No extant Hebrew manuscript of Sirach preserves chapter {chapter} "
                    "(chapters 2, 17, 24, 28, and 29 survive only in ancient translations such as "
                    "Greek, Syriac, and Latin). This is a historical manuscript-survival gap, not "
                    "evidence that Hebrew Sirach never existed; Greek or Latin text cannot supply a Hebrew witness.")
        return ("No admitted local Hebrew Sirach transcription is loaded for this chapter. This is "
                "a source-coverage gap, not evidence that Hebrew Sirach never existed; "
                "Greek or Latin text cannot supply a Hebrew witness.")
    if language in {"hebrew", "latin"} and book_slug == "psalms" and chapter == 151:
        return (f"The admitted local {language.title()} Psalms sources have no "
                "chapter 151. It remains in the catalogue; a source in this language "
                "is needed before collation. Greek Psalm 151 is available separately.")
    return ""
