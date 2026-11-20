# Full Trilingual Verse-by-Verse Verification & Repair — 17 November 2026

Every available verse of every available chapter of every canonical book across all three Studio languages (`Greek`, `Hebrew`, `Latin`) was audited in an isolated sandbox, compared verse-by-verse before and after each deterministic fix against the admitted witness transcriptions, verified against all 16 repository invariants, and exported across the local edition folders and `data/studio.db`.

## 1. Corpus Scope & Final Verification Totals

| Language | Books Collated | Chapters Exported | Verified Verses | Unavailable Catalogue Entries (Honest Witness Limits) |
| --- | ---: | ---: | ---: | --- |
| **Greek** | 70 / 70 | 1,290 | 34,197 | `Proverbs 30` (LXX places MT 30 inside chapter 24; empty `\c 30` in Brenton) |
| **Hebrew** | 38 / 39 | 929 | 23,213 | `Psalms 151` (not in MT); `Sirach 1–51` (no admitted local Hebrew witness loaded) |
| **Latin** | 70 / 70 | 1,290 | 34,446 | `Psalms 151` (absent from Clementine USFX and Saints Latin column) |
| **Total** | **178 book-streams** | **3,509 chapters** | **91,856 verses** | **54 chapter entries** (explicitly reported via `coverage_gap_detail`, never synthesized) |

> **Later correction (17 Nov 2026, evening).** Greek Proverbs 30 is no longer unavailable. Its text was never lost: the Brenton e-text, the numbering anchor, runs Proverbs 30:1–31:9 on as 24:22–62. The Greek edition now numbers Proverbs as Saints.Bible does (24:1–34, 30:1–33, 31:1–31), so it has 1,291 Greek chapters, and Proverbs has 889 verses, not 875. No words were added or lost. See `README.md` (Proverbs) and `studio/source_repairs.py`.

### Corpus-Wide Invariant Audit (All 91,856 Verses)
- **Unhandled exceptions**: `0`
- **Empty critical verses**: `0`
- **Script contamination or quarantined witness leakage**: `0`
- **Leaked XML/USFM/editorial markup**: `0` (the 12 `[...]` occurrences in Hebrew are genuine Masoretic Qere/Soferim brackets in MAM)
- **Word-internal OCR capitals (`_inner_capital`)**: `0`
- **Unbalanced chapter parentheses**: `0` across all 2,580 Greek and Latin chapters (preserving multi-verse parentheticals such as `Luke 2:36–37` while closing `Latin Genesis 44:14`)
- **Unexpanded nomina sacra in critical text**: `0`
- **Apparatus word-index / slice mismatches**: `0`
- **Edition-family split violations (`EDITION_FAMILIES` voting on both sides)**: `0`

---

## 2. Root Causes Uncovered & Fixed

### A. Hebrew (`studio/parsers.py`)
1. **Inline Masoretic Large/Small/Suspended Letter Markup Splitting Words in WLC**:
   - `OT_WLC_39Books_Raw.tsv` encodes Masoretic special letters (`litterae majusculae / minusculae / suspensae`) with single-quoted inline tags such as `'l s="H8085"'שְׁמַ֖'seg type="x-large"'ע'seg''/l'`.
   - Replacing `seg` tags with spaces left single quotes and spaces inside the word (`' 'שְׁמַ֖' 'ע' '' '`), splitting words and creating false apparatus variants against MAM in **10 verses**, including the **Shema (`Deuteronomy 6:4` שְׁמַע and אֶחָד)**, `Leviticus 11:42` (גָּחוֹן), `Numbers 27:5` (מִשְׁפָּטָן), `Judges 18:30` (מְנַשֶּׁה), `Job 38:13, 15` (רְשָׁעִים / מֵרְשָׁעִים), `Psalms 80:14` (מִיָּעַר), `Proverbs 16:28` (וְנִרְגָּן), `Isaiah 44:14` (אֹרֶן), and `Jeremiah 39:13` (וּנְבוּשַׁזְבָּן).
   - **Fix**: `_wlc_index` now unwraps inline `'l ...'`, `'/l'`, `'seg ...'`, and `'seg'` tags with `""` (no space, matching `_mam_index`), restoring single intact Hebrew words and eliminating the spurious variants.

### B. Latin (`studio/parsers.py`, `studio/catalog.py`, `studio/collator.py`, `studio/brains/offline_philological.py`)
1. **Duplicate-Reference Collisions Deleting Scripture Verses in `_parse_latin_saints_json`**:
   - In `saints-latin-column`, several adjacent Vulgate verses share one Saints `reference` string while the following verse slot is left blank (`Matthew 11:2–3`, `Matthew 11:16–17`, `Matthew 16:3–4`, `Mark 6:27–28`, `Luke 4:18–19`, `Revelation 20:8–9`), or two verses of the same chapter are combined under one Saints verse (`John 6:51` = Vulgate `6:51 + 6:52`, `Luke 9:42` = `9:42 + 9:43`, `Numbers 6:23` = LXX order `6:23 + 6:27`). Previously `out[ch][vn] = lat` overwrote the first half, deleting `"Ego sum panis vivus, qui de cælo descendi."` (`John 6:51a`), `"Joannes autem cum audisset..."` (`Matt 11:2`), and `"Loquere Aaron..."` (`Numbers 6:23a`), and leaving 5 NT verse-number gaps.
   - **Fix**: Canonical NT card IDs whose own verse slot is empty are restored to their own verse number; genuinely combined same-chapter pairs within 5 verses are concatenated in order; and `align_versification`'s leftover folding orders combined verses by `SequenceMatcher` sequence alignment rather than order-insensitive Jaccard similarity.
2. **Cross-Chapter Alignment Window for `Latin Exodus 36–39`**:
   - Saints/LXX `Exodus 36:8–38` (the priestly vestments) corresponds to Vulgate `Exodus 39:1–31` (3 chapters away). Adding `("latin", "exodus"): 3` to `ALIGNMENT_WINDOW` aligns `Clem1598-USFX` and `Amiatinus` across chapters 36–39.
3. **VulSearch Editorial Speaker Rubrics & Poetry Brackets**:
   - Stripped 1,468 `[` / `]` poetry block brackets (e.g. `Joel 4:21` `in Sion.]`) and `<...>` speaker/acrostic tags from `_parse_latin_saints_json`, and stripped inlined VulSearch speaker rubrics (`Sponsa`, `Sponsus`, `Chorus`, `Chorus Adolescentularum`, `Chorus Fratrum`) in `_usfx_index` strictly within `SNG` (`Song of Songs`), leaving `Exodus 4:26` (*"Sponsus sanguinum"*) and `Lamentations` (`Aleph`…`Thau`) untouched.
4. **Amiatinus `<name>` Word Boundaries, Scribal Cola Marks & Proper-Name Casing**:
   - `_render_amiatinus_fragment` now strips XML comments, preserves word boundaries outside `<name>...</name>` (`Genesis 25:3` `</name>fuerunt` → `Dodan fuerunt`), and drops diplomatic `<orig>,</orig>` line-break dots (fixing `,amdan` in `Gen 36:26` and `,rursum` in `Gen 38:17`).
   - `_latin_base_spelling` now transfers Clementine proper-name capitalization onto inflected/orthographic Amiatinus name variants (`Saban`, `Dodan`, `Nahor`, `Aram`, `Abraham`, `Rahel`, `Mesopotamiam`, `Esban`, `Iethran`, `Aegyptum`, `Putipharae`, `Onam`).
   - `_choose_best_surface_form` transfers closing `)` from `base_raw` (`Genesis 44:14` `(necdum enim de loco abierant)`).

### C. Greek (`studio/engine.py`, `studio/collator.py`, `studio/brains/offline_philological.py`)
1. **Cross-Chapter Boundary Shift & Re-Division in `Zephaniah 3:1–2`**:
   - Swete numbers `Zephaniah 2:15` as `3:1` and combines `3:1 + 3:2` in `3:2`; previously `3:1` matched Brenton `3:1` on `"ἡ πόλις"` and was trimmed down to a two-word fragment `"ἡ πόλις"` while `3:2` repeated `3:1`.
   - **Fix**: `_split_merged_verses` relocates cross-chapter boundary shifts (`>= 0.85` match to the adjacent chapter's anchor verse when that slot is empty in the witness) before re-dividing, `align_versification` protects cross-chapter edge candidates, and `_trim_overlong` refuses to trim a long verse down to `< 3` words. Both `Zephaniah 3:1` and `3:2` now align cleanly across all 4 Greek OT witnesses.
2. **Orthographic Base Selection After Re-Alignment (`Joel 4`, `Proverbs 31`, `Latin Joel 4`)**:
   - `build_collation` now selects `base_siglum` from `mapped_by_sig` *after* versification alignment rather than `has_chapter` before alignment, restoring `Swete-Amicarelli` in `Greek Joel 4` and `Proverbs 31` and `Clem1598-USFX` in `Latin Joel 4`.
3. **Short Trailing `Swete Clean` Conversion Phantoms (`Psalms 112:10`, `Psalms 137:9`)**:
   - `_versification_duplicates` now evaluates `stale_copy` before `len(keys) < 3` when both sister copies (`Swete-Amicarelli` and `1st1K-LXX`) lack the phantom verse, removing `Psalms 112:10` (`"Ἁλληλουιά."`) and `Psalms 137:9` (`"Τῷ Δαυεἰδ."`) with logged notes.
4. **Greek Accentuation, Breathing, Word-Division & Sister-Copy Repairs**:
   - `_shape_key` now folds grave `\u0300` → acute `\u0301` *only* on the final vowel of single-accented oxytonic words, preventing impossible non-final graves (`ηὐλὸγησα`, `ὃστις`, `χεὶλους`, `Κὺριος`, `τεὶχη`, `Ἂβελ`) and double-accented slips (`μισοῦντὰς`, `μάχαιρὰ`) from merging into or inflating clean shape buckets (`Gen 27:33`, `Num 16:27`, `Num 27:17`, `Deut 7:15`, `Judg 7:22`, `1 Kgs 7:10`, `2 Chr 33:17`, `Isa 34:5`, `Amos 1:14`, `Heb 11:4`, `Heb 12:24`).
   - Added circumflex-before-naturally-long-ultima detection in `_greek_accent_defect` (`Josh 18:12` `νῶτου` → `νώτου`, `1 Chr 28:13` `Λευεῖτων` → `Λευιτῶν`), per-word defect donor repair inside multi-word units (`2 Kgs 9:2` `ἐκει` → `ἐκεῖ`), movable-`ν` ungluing (`1 Sam 14:48` `ἐπάταξεντὸν` → `ἐπάταξεν τὸν`), spacing-breathing & non-final grave-diaeresis normalization (`1 Chr 7:37` `ʼΩὰ, ʼΙεθρὰ` → `Ὠὰ, Ἰεθρὰ`, `1 Chr 6:15, 36` `Ἀσαΐας, Σαραΐα`), base-comma preservation (`Ps 54:13` `ἐμεγαλορημόνησεν,`), sister-copy adjacent-dittography removal (`Josh 6:17` `ἐστὶν ἐστὶν` → `ἐστὶν`), and corrupt-form sister-copy slip repair (`1 Macc 16:10` `τὴς` → `τὴν`).
   - Four tokens in single-witness Brenton USFM genealogy verses (`1 Chr 5:30–31` `Αβισοὺ` and `Neh 7:26–27` `γἱοὶ`, where Vaticanus/Swete lacks the verses) are intentionally left unemended in accordance with Invariant 15 (never invent unattested readings without a second witness or unambiguous lexicon support).
5. **Greek NT Clause-Continuation Punctuation & Casing**:
   - Removed premature full stops left where `SBLGNT` ended a sentence only because it omitted the adopted continuation (`Mark 7:24` `Τύρου καὶ Σιδῶνος.`, `Luke 24:3` `τὸ σῶμα τοῦ Κυρίου Ἰησοῦ.`, `Luke 24:36`, `Rom 14:12`, `Col 1:2`), preserved sentence stops before liturgical `Ἀμήν.` (`1 Cor 16:24`, `Phil 4:23`, `Phlm 1:25`), and lowercased speech/clause capitals displaced by an inserted word or comma (`Mark 8:21` `Πῶς οὔπω συνίετε;`, `Luke 24:45` `τὰς γραφάς, καὶ εἶπεν αὐτοῖς,`).

---

## 3. Validation & Persistence
- **Automated Test Suite**: `python -m unittest discover -s tests -v` — **114 tests passed (`OK`)** in an isolated temporary `CTS_DATA_DIR` / `CTS_OUTPUT_ROOT` sandbox with network access blocked.
- **Database & Export Generation**: `data/studio.db` and `data/settings.json` were backed up under `data/backups/trilingual-full-verification-20261117T150243Z/`, all 42 prior `Direct local Codex review` verse annotations and any `human_locked` flags were preserved, and all **3,509 available chapters (91,856 verses)** were persisted to `data/studio.db` and exported to **10,527 chapter files** (`.md`, `.json`, and `.tsv`) under `Saints-Greek-Critical-Text/`, `Saints-Hebrew-Critical-Text/`, and `Saints-Latin-Critical-Text/`.
