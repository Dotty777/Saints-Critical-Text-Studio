# Majority and ecclesiastical editions in the apparatus (17 November 2026)

**What was added.** Ten Majority and ecclesiastical editions were added to the Studio:
- **Greek OT:** the Orthodox ecclesiastical Septuagint (LXX-Orthodox).
- **Greek NT:** Robert Adam Boyd's Byzantine text (TCGNT), the 1904 Patriarchal text (PT1904), and Scrivener's (1894) and
  Boyd's Textus Receptus.
- **Hebrew:** Ben Chayyim (1525) and Letteris (1852).
- **Latin:** Hetzenauer (1906), Conte (2009) and the Sixtine Vulgate (1590).

The Stuttgart CSV was quarantined.

**Decision.** These editions are **apparatus witnesses** (`catalog.APPARATUS_ONLY`, `studio/apparatus_witnesses.py`):
- **Collated:** each is re-aligned to the numbering anchor like every witness and collated against the adopted text.
- **Recorded:** each is added to every apparatus unit on the side it supports. A new unit records its reading wherever it
  differs in substance from a text the voting editions agree on.
- **Not voting:** it never votes, never chooses a spelling and never feeds the corpus lexicon.

The weights changed to make room for them (Sixtine/Brenton 0.84 → 0.48, Clementine 0.88 → 0.54, Saints Latin column
0.86 → 0.52, Amiatinus 0.97 → 0.98) were restored. Seed version 7.

## Why they do not vote

Both versions were built for every verse, sandboxed: the Studio as committed (`bf9bd92`) and the Studio with the new
editions voting as added. The new editions changed the text substantially:

| Corpus | Verses | Changed when they voted | What changed |
| :--- | ---: | ---: | :--- |
| Greek OT | 26,250 | 275 | **126 verses printed that Codex Vaticanus lacks**, from the Orthodox text alone (1 Sam 17:12–31, 3 Kgdms 14:1–20, Sir 26:19–27); **18 verses of 4 Maccabees printed as 2 Maccabees** (that file is 4 Maccabees); 148 wording changes |
| Greek NT | 7,960 | 494 | The text moved to the Byzantine reading against B, Sinaiticus, SBLGNT and Nestle, e.g. Matt 6:15 + τὰ παραπτώματα αὐτῶν, Matt 11:19 ἔργων → τέκνων, Matt 1:20 Μαρίαν → Μαριάμ |
| Hebrew | 23,213 | 11,541 | MAM's pointing outvoted (qamats qatan, the holem of the divine name, meteg); some words printed with doubled marks no source has (יְהוָה֙֙, עָרְלָת֔וֹֹ) |
| Latin | 34,446 | 145 | Punctuation flips, and errors from the new files (Deut 13:15 quære → quare, viginti → vigintiquattuor) |

**Cause.** Four Byzantine/TR editions voted as four editions of one stream, and two Masoretic prints joined WLC against
MAM's pointing. A whole verse was printed when a single edition had it.

**Result as apparatus witnesses.** The Studio's text is identical to `bf9bd92` in all 91,869 verses.

## What the apparatus gains

| Corpus | Verses with new units | New units | Readings held only by the new editions | New editions added to a voting edition's reading |
| :--- | ---: | ---: | ---: | ---: |
| Greek OT | 3,718 | 4,447 | 5,877 | 11,213 |
| Greek NT | 735 | 895 | 2,131 | 7,591 |
| Hebrew | 125 | 133 | 159 | 83 |
| Latin | 2,495 | 2,831 | 2,972 | 933 |

Examples:
- **Matt 6:13:** the doxology is recorded with RP2018, the TR and all four new NT editions.
- **John 1:18:** μονογενὴς υἱός is recorded (PT1904, TCGNT, both TRs).
- **Deut 23:2:** Letteris reads דַּכָּה; Ben Chayyim supports the text's דַּכָּא.
- **Gen 1:2 (Latin):** Sistina reads *Spiritus Domini*.

Spelling, accent, pointing and layout differences are not units. They go to the disregarded log, once per verse and
reason: Greek movable ν, itacism and word division; Latin conventions; Hebrew pointing, ketiv/qere layout, and plene or
defective spelling (vav or yod as a vowel letter). In Hebrew a unit is made only when the consonants differ or a word is
added or missing, so 2,737 units fell to 133 real ones.

## Source problems found and handled

- **Orthodox Septuagint, 2 Maccabees:** the file labelled `2MA` (`53-2MAgrclxx.usfm`) is 4 Maccabees (ΜΑΚΚΑΒΑΙΩΝ Δ,
  18 chapters). The witness is left out of 2 Maccabees (`WITNESS_BOOK_EXCLUSIONS`).
- **Orthodox Septuagint, numbering in the text:**
  - cross-references to other chapter divisions ("(Κεφ. ΛΘ 1)", "(Μασ. Ι, 6)");
  - Esther's lettered verse labels (12α–12η) and 3 Kgdms 2:35's "35·1" … "35·14";
  - verses whose marker is missing and whose number stands in running text, as in Deut 2:9 "… (10 οἱ Ὀμμὶν …".
  
  The parser now removes the labels and splits such verses out. No Orthodox verse holds a digit any more.
- **Hetzenauer and Conte CSV files:** both leave out Jerome's prologue to Lamentations, which the printed editions have.
  It is marked as lost text in those files, not recorded as their omission.
- **Verses only the new editions print**, such as 1 Sam 17:12–31 in the Orthodox text, are noted with the chapter and
  not printed.

## Editions regenerated

Every chapter edition in Greek, Hebrew and Latin was regenerated with the offline Textual Analysis brain, after a backup
(`data/backups/majority-apparatus-*`). The Markdown lists the new editions in a separate table ("Apparatus Witnesses …
recorded, not voting"). The JSON gives them `apparatus_witnesses` and each verse's `apparatus_witnesses`. Their full
readings are in `witness_readings`.

## For the owner

Letting one of these editions vote is an editorial decision. The table above shows what that would do. If the Byzantine
stream should weigh more in the NT, that is better decided as a stream weight than by adding editions.
