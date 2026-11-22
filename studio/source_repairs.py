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
_LATIN_NUM1_COPIES = (
    "lat-clementine-usfx",
    "lat-vulg-hetzenauer",
    "lat-vulg-conte",
    "lat-vulg-sistina",
    "lat-quarantine-stuttgart",
)
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
    (("lat-clementine-usfx",), "sirach", (29, 17), "head", "et super lanceam", (29, 16), "append"),
    (("lat-clementine-usfx",), "sirach", (29, 18), "head", "adversus inimicum tuum pugnabit.", (29, 16), "append"),
    (("grk-brenton-sixtine",), "nehemiah", (12, 18), "head", "Τῷ Ἰωαρὶβ,", (12, 19), "prepend"),
    (("grk-brenton-sixtine",), "nehemiah", (12, 17), "tail", "τῷ βαλγὰς, Σαμουέ· τῷ Σεμία, Ἰωνάθαν·", (12, 18), "new"),
)
_DIVISION_WHY = {
    "numbers": "Swete numbers Brenton's 17:1–15 as 16:36–50 and Brenton's 17:16–28 as 17:1–13; the formulaic "
               "verse 'Καὶ ἐλάλησεν Κύριος πρὸς Μωυσῆν λέγων' was paired with Brenton's 17:1 by its number",
    "joshua": "the list of kings in 12:20–22 is divided differently in each copy and in Brenton",
    "judges": "Swete opens 2:15 with 'ἐν πᾶσιν οἷς ἐξεπορεύοντο', which Brenton ends 2:14 with",
    "nehemiah": "Brenton USFM ran 12:18 into the tail of 12:17 and split 12:19 across 12:18 ('Τῷ Ἰωαρὶβ,') and 12:19; "
                "restored to the standard LXX/Rahlfs/Orthodox verse boundaries",
    "proverbs": "Swete prints Brenton's 31:27 ('τὸ στόμα δὲ ἀνοίγει … ἡ δὲ ἐλεημοσύνη αὐτῆς') inside its 29:45–46",
    "ecclesiastes": "Swete's verse divisions in 7:24–25, 8:2–3 and 9:1–2 differ from Brenton's",
    "song-of-songs": "Swete opens 7:1 with 'Τί ὄψεσθε … παρεμβολῶν', which Brenton ends 7:1 (Swete 6:12) with",
    "sirach": "Swete ends 1:8 with 'Κύριος' opening 1:9; Clementine Vulgate splits Sirach 29:13 across 29:16–18",
    "daniel": "Swete prints the springs (3:77) before the seas and rivers (3:78); Brenton numbers them the other way round",
}
# Whole runs renumbered to Brenton's numbering, in order: (witness id, book) -> [(chapter, first, last,
# new chapter, new first)]. Made only when every verse of every run is there and every new number free.
_RENUMBER = {
    ("grk-swete-csv", "numbers"): [(17, 1, 13, 17, 16), (16, 36, 50, 17, 1)],
    ("grk-brenton-sixtine", "proverbs"): [(24, 35, 53, 30, 15), (24, 54, 62, 31, 1)],
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
               "the words typed twice are kept once")
        notes.setdefault(ch, []).append(
            f"Source import repair, {ch}:{v}: '{needle}' → '{new}' (Swete prints {swete}). "
            f"{how}; no word was supplied. Original file unchanged.")
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
    if wid in _LATIN_NUM1_COPIES and book_slug == "numbers":
        ch1 = result.get(1, {})
        if (all(ch1.get(v) for v in range(24, 38))
                and "Gad" in ch1[24] and "Juda" not in ch1[24] and "Iuda" not in ch1[24]
                and "Zabulon" in ch1[30] and "Ephraim" in ch1[32]):
            result = _copy_chapter(result, original, 1)
            snap = {v: result[1][v] for v in range(24, 38)}
            for v in range(26, 38):
                result[1][v - 2] = snap[v]
            result[1][36], result[1][37] = snap[24], snap[25]
            notes.setdefault(1, []).append(
                "Source division repair: verses 1:24–25 (Gad) moved to 1:36–37 and 1:26–37 (Juda–Benjamin) "
                "renumbered 1:24–35 to match Clem-Saints's LXX tribe order (preventing formulaic census alignment "
                "from swapping Zabulon 1:28 and Ephraim 1:30). Original file unchanged.")
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
