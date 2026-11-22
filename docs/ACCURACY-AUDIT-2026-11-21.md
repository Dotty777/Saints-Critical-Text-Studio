# Full-Corpus Accuracy Audit & Verification Report (Catalogue v9)

**Date:** 21 November 2026 · **Catalogue Version:** `SEED_VERSION = 9` (**114 ADMITTED witnesses**, `0` missing files)  
**Scope:** Complete verse-by-verse audit of all **91,869 verses** across all **3,510 chapters** in `data/studio.db` (Greek NT, Greek OT / Septuagint, Hebrew & Biblical Aramaic OT, and Latin Vulgate OT & NT), plus on-demand verification of Hebrew Ben Sira (46 extant chapters) and Hebrew Psalm 151 (`11QPsᵃ`).

---

## 1. Executive Summary & Quantitative Benchmarks

After expanding the Studio to **114 witnesses** (`66` Greek, `21` Hebrew [+1 `DISREGARDED_CORRUPT`], `27` Latin), every saved verse in all four corpora was audited programmatically against the highest-authority external reference editions (`NA28`, `THGNT`, `SBLGNT`, `SRGNT`, `Tregelles 1879`, `WH1881`, `Rahlfs 1935`, `BHS / BHSA 2021`, `Stuttgart BSV`, and `Hetzenauer 1906`) and checked for mechanical, philological, morphological, OCR, accentuation, versification, and markup defects.

| Corpus | Chapters | Verses | Primary Accuracy Benchmark | Mechanical / Markup Defects Found → Fixed |
| :--- | :---: | :---: | :--- | :--- |
| **Greek NT** | 260 | 7,960 | **99.50%** (`7,920/7,960`) exact agreement with ≥1 of 6 major critical editions (`NA28`, `THGNT`, `SBLGNT`, `SRGNT`, `Tregelles`, `WH1881`); **94.25%** (`7,502/7,960`) exact match with `NA28` or `THGNT`; `0` missing verses | **6 verse defects fixed:** `Heb 12:15` elision before consonant (`διʼ ταύτης` → `διὰ ταύτης`), `Rev 16:3` unattested hybrid (`ζῶσα [ἀπέθανεν] τὰ` → `ζωῆς ἀπέθανεν τὰ`), 4 bracketed polytonic typos (`Acts 8:37`, `Acts 24:7`, `Luke 17:36`, `John 8:3`) |
| **Greek OT (LXX)** | 1,031 | 26,250 | **87.95%** ≥90% Dice similarity with `Rahlfs (1935)` (`61.43%` exact — expected because Swete is diplomatic Codex Vaticanus `B` whereas Rahlfs is eclectic); all 43 short verses confirmed as genuine Codex B homoeoteleuton omissions shared across all 3 Swete copies | **4 live verse defects fixed:** `Sir 24:34` (`ἅποσιν` → `ἅπασιν`, restoring `ἀλλ᾽ ἅπασιν`), `1 Macc 8:14` (`πᾶσιν` → Swete's authentic `ἅπασιν`), `1 Chr 6:54` (`τπερισπόρια` OCR typo masked, eliminating a misaligned duplicate of v66 Heshbon/Jazer and restoring Swete's authentic Aijalon reading `καὶ τὴν Αἰλὼν καὶ τὰ περισπόρια αὐτῆς.`, plus `1 Chr 6:67` `φυγαδευτρηίων` → `φυγαδευτηρίων`), `1 Kgs 12:24m` (recovered 10-word Amicarelli homoeoteleuton skip + 3 OCR typos `Ἵωα/ἄπτους/στάμον` → `Ἵνα/ἄρτους/στάμνον`) |
| **Hebrew & Aramaic OT** | 929 | 23,213 | **99.16%** (`23,019/23,213`) exact consonantal / Ketiv–Qere / plene–defective match with `BHS (BHSA 2021)`; remaining `55` non-parashah consonantal differences are 100% authentic Aleppo (`MAM`) vs Leningrad (`BHS`) manuscript variants | **0 critical-text defects**; 1 apparatus parser bug fixed (`BHSA` mid-verse parashah/inverted-nun markers `פ`/`ס`/`נ` stripped); Hebrew Ben Sira (46 ch.) `MsB 32:1` empty `<g type="reconstructed"/>` fixed; DSS unpointed `sof pasuq` (`U+05C3`) fixed in `_has_hebrew_niqqud` |
| **Latin (OT & NT)** | 1,290 | 34,446 | **93.65%** (`32,259/34,446`) exact agreement with `Hetzenauer (1906)` or `Stuttgart BSV` (`93.35%` exact with Hetzenauer); `0` truncated verses remaining across all 70 books | **18 verse defects fixed:** `Sirach 29:13` (sole truncated verse in all 34,446 Latin verses restored from `Clem1598-USFX`), `Gen 5:3, 5, 7, 14, 17` (Amiatinus Roman numerals normalised to spelled-out Latin numbers), `Gen 7:5` (unattested double-pronoun conflation `ei Dominus illi` removed), `Gen 39:14` (`haebrę um` XML line-break split → `hebræum`), plus `ę → æ`, safe post-`r`/`l` `u → v`, and proper-name capitalisation in `Gen 14:4, 9; 15:19; 27:25; 30:32–33; 36:22–24; 44:25` |
| **Total** | **3,510** | **91,869** | All 4 corpora audited & verified (`0` known mechanical defects remaining) | **28 live critical-text verses repaired** + **5 parser/collator bugs fixed** |

---

## 2. Detailed Repairs Implemented

### A. Parser & Witness-Ingestion Repairs (`studio/parsers.py`, `studio/collator.py`)
1. **Rahlfs 1935 CSV 8-Word Drift (`_rahlfs_csv_index`):** 8 rows in Hosea 1–2 of `text_accented.csv` have 2 tab columns instead of 3, which previously caused an 8-word cumulative shift across all 623,693 words. Fixed by indexing explicitly by `int(parts[0]) -> parts[-1]`. Verified Isaiah 7:14 opens cleanly with `διὰ τοῦτο δώσει κύριος...`.
2. **STEPBible `TAGNT` `THGNT` Edition Reconstructor (`_tagnt_pick_word`, `_tagnt_edition_index`):**
   - Strips stray `¶` paragraph pilcrows from reconstructed verses.
   - Splits `MEANING VARIANTS` on `[‖¦|]` (fixes `1 Cor 13:3` `καυθήσομαι` in `THGNT`).
   - Parses `>N:` and `<N:` relative word-order shifts in `EDITIONS` using exact stable sort `(r_idx + offset, r_idx)` (fixes `1 Cor 8:8` transposed `THGNT` clause order).
3. **`BHSA` Text-Fabric Mid-Verse Masoretic Markers (`_bhsa_tf_index`):** Strips mid-verse and final parashah / inverted-nun markers (`פ`, `ס`, `נ`) cleanly (`Deut 2:8`, `Num 10:35`, `Gen 35:22`).
4. **Hebrew Ben Sira Empty Reconstruction Tags (`_clean_bensira_word`):** Flags self-closing `<g type="reconstructed"/>` elements so stray incomplete letters (`BenSira-B` Sirach 32:1) never leak into Hebrew Sirach.
5. **Dead Sea Scrolls Unpointed Versification Alignment (`_has_hebrew_niqqud`):** Restricted vowel-point detection to true niqqud `(0x05B0–0x05BB, 0x05C7)` so `sof pasuq` (`U+05C3`) never causes unpointed DSS scrolls (`1QIsaᵃ`, `1QIsaᵇ`, `4QSamᵃ`, `4QDeutq`) to score `0.000` similarity against pointed Masoretic anchors.
6. **Lacuna-Safe Versification Keysets (`_keyset`):** Excludes `…` (`LACUNA_MARK`) and `[…]` (`GAP_WORD`) from Dice similarity sets so marked truncations align cleanly with complete sister witnesses (e.g., Latin `Sirach 29:13`).

### B. Documented Source Import Repairs (`studio/source_repairs.py`)
All source repairs are exact-match, idempotent, logged per chapter, and leave every original research corpus file untouched:
- **Greek OT:**
  - `sirach 24:34` (`_OCR`): `ἅποσιν` → `[…]`, allowing `Swete-Amicarelli`'s `ἅπασιν` (corroborated by `א (01)` & `Rahlfs 1935`) to restore `ἀλλ᾽ ἅπασιν`.
  - `1-chronicles 6:81` (aligned to `6:54`, `_OCR`): `τπερισπόρια` → `[…]` (restores `περισπόρια`).
  - `1-chronicles 6:67` (`_CSV`): `φυγαδευτρηίων` → `[…]` (restores `φυγαδευτηρίων`).
  - `1-kings 12:24` (`_CSV` + `_OCR`): marks Amicarelli's 10-word homoeoteleuton skip with `…` and repairs the 3 single-letter OCR typos (`Ἵωα` → `Ἵνα`, `ἄπτους` → `ἄρτους`, `στάμον` → `[…]`), recovering the complete Swete / Larger Cambridge B text of 3 Kgdms 12:24m.
- **Greek NT (Bracketed Verses):**
  - `acts 8:37` (`grk-nt-kjtr`): repairs 5 polytonic typos (`Εἰπε`/`εἷπε` → `Εἶπε`/`εἶπε`, `τὴς` → `τῆς`, `Ὑιὸν` → `Υἱὸν`, `ἐιναι` → `εἶναι`, corroborated by Scrivener 1894 & Boyd TR).
  - `acts 24:7` (`grk-nt-kjtr`): `ὁ χιλιαρχος,` → `ὁ χιλίαρχος,`.
  - `luke 17:36` (`grk-nt-kjtr`): `ὁ εἴς` → `ὁ εἷς`.
  - `john 8:3` (`grk-nt-sblgnt`): `καταλήφθεισαν·` → `καταληφθεῖσαν·` (upstream SBLGNT 2010 accent typo).
- **Latin:**
  - `genesis 7:5` (`lat-amiatinus`): removes `<supplied reason="omitted" source="#s">ei</supplied>` placeholder `[…]` in `"praeceperat […] dominus illi"` so Amiatinus's transposition `illi` does not conflate with Clementine's `ei` (`praeceperat Dominus illi`).
  - `genesis 39:14` (`lat-amiatinus`): joins `"haebrę um"` → `"haebręum"` (missing `break="no"` on `<lb rend="indent"/>`), matching Clementine's `hebræum`.
  - `sirach 29:13` (`lat-saints-staging` + `lat-clementine-usfx` 29:16–18): folds Vulgate 29:17–18 onto 29:16 in `Clem1598-USFX` and marks `Clem-Saints` 29:13 truncated (`…`), restoring the complete verse `Super scutum potentis et super lanceam adversus inimicum tuum pugnabit.`.

### C. Philological Engine & Collator Rules (`studio/brains/offline_philological.py`, `studio/collator.py`)
1. **Greek Elision Harmonisation (`_harmonise_greek_elision`):** Restores the unelided vowel on elided multi-letter prepositions/particles (`διʼ`, `ἀλλʼ`, `κατʼ`, `μετʼ`, etc.) whenever eclectic adjudication places a consonant-initial word after them (`Heb 12:15`: `διʼ ταύτης` → `διὰ ταύτης`). Explicitly skips letter-numerals and single-letter forms (preserving `Judg 19:2` `δ᾽ μηνῶν`).
2. **Emphatic `ἅπας`/`πᾶς` OCR Guard (`_ocr_word_slip`):** Prevents genuine `ἅπας`/`ἅπαντ-`/`ἅπασ-` forms (`Sir 24:34` `ἅπασιν` and `1 Macc 8:14` `ἐν ἅπασιν τούτοις`) from being misclassified as a "stray α" OCR typo of `πᾶς`/`πᾶσιν`.
3. **1-Agreed-Slot Attested-Run Bridging (`_attested_run_fix`):** When two variation units separated by a single agreed word produce an unattested hybrid combination, weighs the witnesses' own complete combinations. Tested across all 260 Greek NT chapters (7,960 verses): touches **exactly 1 verse** — **`Revelation 16:3`**, turning the unattested conflation `πᾶσα ψυχὴ ζῶσα ἀπέθανεν τὰ ἐν τῇ θαλάσσῃ` into `πᾶσα ψυχὴ ζωῆς ἀπέθανεν τὰ ἐν τῇ θαλάσσῃ` (exact agreement with `NA28`, `THGNT`, `SBLGNT`, `SRGNT`, `Nestle1904`, `Tisch8`, `Tregelles`, `WH1881`, `A (02)`, and `C (04)`).
4. **Latin Roman-Numeral Equivalence (`is_latin_roman_numeral`, `classify_forms`):** Recognises classical and medieval additive Roman numerals (`cxxx`, `dcccc xxx`, `dccc vii`, `dcccc x`, `dccc xcv`) against spelled-out Latin cardinals of the exact same integer value (`130`, `930`, `807`, `910`, `895`) as orthographic abbreviations, printing consistent spelled-out numbers across all of `Genesis 5` while logging Amiatinus's Roman numerals in `disregarded`.
5. **Latin Orthography & Proper-Name Capitalisation (`_latin_u_to_v`, `_latin_base_spelling`):**
   - Normalises medieval e-caudata `ę → æ` (`Gen 15:19` `Cetmonæos`).
   - Normalises unambiguous `[rl]uu` before consonant/end (`paruum → parvum`, `fuluum → fulvum`) and safe classical `v`-stems (`seruierant → servierant`, `fulua → fulva`, `aluam → alvam`) without touching vowel-`u` verbs (`Apparuitque` `Gen 12:7`, `Seruit` "sowed" `Gen 26:12`, `pluit`, `eruit`, `voluit`, `instruebat`).
   - Improves proper-name capitalisation matching across initial-consonant variants (`godorlahomor → Godorlahomor`, `theman → Theman`) and Clementine post-colon list names (`Horrei`, `Alvam`, `Ahaia`, `Offer`), verified across all 50 Genesis chapters with zero regressions (`Rahel`, `Omor`, `Sephum` preserved).

---

## 3. Hypotheses Empirically Tested & Intentionally Rejected

To ensure every change genuinely raised textual accuracy rather than introducing bias or noise, several candidate modifications were tested in isolated sandboxes and deliberately **not** adopted:
1. **Merging `BHP` into `SRGNT`'s Edition Family:** Tested across all 260 NT chapters. Lowered exact agreement with `NA28` (`7,073 → 7,039`), `NA28|THGNT` (`7,501 → 7,479`), and `SRGNT` (`7,356 → 7,272`), and introduced 3 alignment regressions (`Matt 15:31, 15:37, 17:3`). The calibrated 8-witness Greek NT voting panel was therefore kept unchanged.
2. **Globally removing `<supplied reason="omitted" source="#s">` → `[…]` in Amiatinus:** All 70 `<supplied>` tags in `0011r-genesis.xml` carry `reason="omitted" source="#s"`, including genuine accidental scribal omissions (`tem`, `ad uescendum`). Targeted repair of `Gen 7:5` in `source_repairs.py` avoids corrupting the other 69 loci.
3. **Overriding Codex B/A diplomatic readings in Greek OT:** Verified `2 Macc 7:37` (`τύχην`), `1 Macc 3:35` (`ἐκρίψαι`), `1 Macc 12:30` (`ἐκατέλαβεν`), `Ezra 10:1` (`ἐπροσηύξατο`), `Isa 22:23` (`στηλῶ`), and `1 Kgs 11:18` (`ἄρχονται`) across all 3 Swete copies — all are genuine historical Codex B/A readings intentionally printed by Swete, with `Rahlfs (1935)` and `Sixtine/Brenton` clearly recorded in the apparatus.
4. **Remaining 40 Greek NT Verses Outside the 6-Edition Exact-Match Set:** Consist strictly of (a) the 15 TR/Byzantine-only bracketed verses (`⟦…⟧`, e.g. `Matt 18:11`, `23:14`, `Mark 11:26`, `Luke 17:36`, `23:17`, `John 5:4`, `Acts 8:37`, `15:34`, `24:7`, `28:29`, `Rom 14:24–26`, intentionally preserved in double brackets rather than silently deleted) and (b) 25 reasoned-eclectic split-unit verses (`Matt 3:16`, `14:9`, `24:31`, `27:46`, `Mark 8:20`, `10:7`, `13:15`, `15:40`, `Luke 7:19`, `10:1`, `14:26`, `John 13:18`, `13:26`, `14:10`, `19:16`, `Acts 1:14`, `17:3`, `1 Cor 8:8`, `13:3`, `Col 2:16`, `1 Tim 2:7`, `Heb 12:15`, `Rev 11:11`, `12:5`, `13:8`, `13:15`) where every individual variation unit reflects documented external manuscript support and calibrated confidence.

---

## 4. Verification Status

- **Automated Test Suite:** All **406 tests** across all 10 test modules (`test_studio`, `test_translit`, `test_concordance`, `test_lexica_greek`, `test_lexica_latin`, `test_lexica_hebrew`, `test_lexica_versification`, `test_lexica_glaux`, `test_lexica_latin_parallel`, `test_concordance_site`) pass 100%, including the new `TestV9AccuracyAuditRepairs` regression suite pinning every defect above.
- **Database Backup & Live Regeneration:** `data/studio.db` was backed up to `data/backups/v9-accuracy-regen-20261121/studio.db` and all **3,510 live chapters** (`91,869` verses) were regenerated and exported cleanly (`0` errors, exactly **28** verified `critical_text` improvements across the entire Bible) with the full 114-witness `SEED_VERSION = 9` apparatus.

---

## 5. Addendum — Phase 2 Zero-Scuff Philological Audit & Complete Ecosystem Parity Sync (22 November 2026)

Following an exhaustive verse-by-verse audit of all **179 books** (`3,510` chapters / `91,869` verses) across Greek, Hebrew/Aramaic, and Latin, verified zero-scuff P0/P1 repairs were implemented across `studio/parsers.py`, `studio/collator.py`, `studio/source_repairs.py`, `studio/brains/offline_philological.py`, `studio/brains/textual_analysis.py`, and `studio/engine.py`, backed up to `data/backups/v9-phase2-pre-regen-20261122/studio.db`, regenerated across all **3,510 chapters** under `Textual Analysis Brain (Claude-designed · internal evidence · offline)` (`0` errors), and synced to 100.00% downstream parity.

### A. Before vs. After Corpus Confidence & Review Summary

| Corpus | Books | Verses | Mean Confidence | 80–99% Band | `<80%` Verses | `needs_review` | `⟦ ⟧` | Text Diffs |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Greek (All)** | 70 | 34,210 | 80.04% → **81.04%** | 66.27% → **67.52%** | 11,539 → **11,111** (`-428`) | 144 → **60** (`-84`) | 44 → 44 | 34 |
| — *Greek OT (LXX)* | 43 | 26,250 | 75.85% → **77.07%** | 58.75% → **60.26%** | 10,829 → **10,432** (`-397`) | 9 → **9** | 0 → 0 | 16 |
| — *Greek NT* | 27 | 7,960 | 93.86% → **94.12%** | 91.08% → **91.47%** | 710 → **679** (`-31`) | 135 → **51** (`-84`) | 44 → 44 | 18 |
| **Hebrew / Aramaic OT** | 39 | 23,213 | 98.07% → **98.61%** | 98.11% → **99.20%** | 438 → **185** (`-253`) | 2 → **2** | 2 → 2 | 16 |
| **Latin (OT & NT)** | 70 | 34,446 | 97.80% → **97.84%** | 97.85% → **97.87%** | 741 → **733** (`-8`) | 0 → **0** | 0 → 0 | 68 |
| **Total** | **179** | **91,869** | — | — | 12,718 → **12,029** (`-689`) | 146 → **62** (`-84`) | 46 → 46 | **118** |

- **Highlights:** Hebrew `Daniel` rose from `82.35%` to **`94.40%`** in the 80–99% band (`<80%` `63 → 20`) via scoped Biblical Aramaic final `-א`/`-ה` and Ketiv/Qere presentation fixes; Greek OT `Job` (`79.49% → 80.62%`) and `Nahum` (`78.72% → 85.11%`) crossed `≥80%`; Greek `Revelation` false-positive singular-`א` `needs_review` flags dropped `60 → 2` while retaining genuine review loci.
- **P0 Live Critical-Text Repairs Verified:** Latin `Gen 40:13` (`consueveras.` restored), `Gen 45:15` (`post quam`), `Gen 1:29` (`semetipsis`), `Gen 9:19` (`hominum`), `Gen 30:26` (`habeam` vs `abeam`), `Gen 50:18` (`in terram, adoraverunt et dixerunt:`), `Num 1:28/1:30` (Zabulon/Ephraim swap repaired), `Num 35:1` (`campestribus`), `Matt 25:42` (`dedistis`), `Mark 3:18` (`Andream`); Greek `Neh 7:26–27` (`υἱοὶ`), `1 Chr 5:30–31` (`Ἀβισοὺ`), `Neh 12:17–19` (verse boundaries), `Num 17:21` (`δώδεκα`) + 9 multi-word letter numerals, and word-division + itacism safeguard preserving `Rom 2:17` (`Εἰ δὲ`), `Jas 3:3`, `Phil 2:16`, `Job 34:16`, `Matt 6:30`, `Luke 12:28`; Hebrew `0` multi-word Ketiv `_` leaks (`15` fixed), `Jer 3:7` `(ותראה)`, `Num 11:32` & `Jer 28:4` double-qamats collapsed.
- **Anti-Scuff Honesty Preserved:** `CONFIDENCE_K` (`1.3`), witness weights, product confidence, all `46` `⟦ ⟧` verses, `1` Latin (`Genesis`) and `38` Greek OT genuine 2-stream books `<80%`, and all genuine Hebrew/Greek/Latin variants remain untouched.

### B. Complete Downstream Ecosystem Parity & Licensing Verification

- **Concordance Index (`cli.py concordance index`):** `1,562,174` tokens indexed (`0` unmapped across Hebrew, Greek, and Latin).
- **Six-Layer + Modern English Parity (`audit_complete_ecosystem.py` — PASS):** **100.00% parity (`0` diffs)** and **`0` Tier 5 leaks** across Studio DB, In-Studio Exports (`3,510/3,510` TSV+JSON+MD), `Saints-Concordance-Pack`, `Saints-Plugins-Repository\saints-concordance\data` (`619` files, `21,961,164` bytes / `20.94 MiB`; `90` open-licence apparatus witnesses, `bad_streams=0`), `Saints Plugins\saints-concordance-2.0.0\saints-concordance\data` (`619/619` byte-identical), `Latin-Translation\Saints-Latin-Critical-Text` (`1,290/1,290` open-licence chapters), and `Saints-Modern-English\full\source\{grc,heb,lat}` (`3,510/3,510` chapters exact, `full/out/` untouched).
- **WordPress Packaging Note:** Fresh deflate-9 plugin `.zip` (excluding `export_apparatus.py`) measures `21,421,236` bytes (`20.43 MiB`; `20.41 MiB` excluding `harness/`), ~`0.41 MiB` above a strict `20.00 MiB` WordPress web-uploader ceiling due to the expanded open-licence apparatus (`1.90 MiB` gzipped across 176 books).
- **Regression Suites:** `tests.test_concordance_site` (**18/18 OK** against live `studio.db`) and `TestPhase2ZeroScuffAudit` + `TestTextualAnalysisBrain` (**12/12 OK**).
