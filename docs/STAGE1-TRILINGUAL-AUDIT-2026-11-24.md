# Stage 1 Trilingual Critical Text Audit & Repair — 2026-11-24

**Scope:** Full trilingual scholarly & technical audit, code repair, offline regeneration under the Textual Analysis Brain, full-corpus Concordance re-index, versification verification, and open-licence publication of **Saints Critical Text Studio (Catalogue v10)**.

---

## 1. Provenance & Methodology

- **Pre-Regeneration Safety Backup:** `data/backups/v9-stage1-pre-regen-20261124/`
  - `studio.db` (`843,595,776` bytes, SHA-256 `1b47e9ca3c56dff2…`, `studio.db-wal = 0` bytes)
  - `settings.json` (`416` bytes, SHA-256 `571d144999c229f4…`, preserved untouched)
- **Catalogue Version:** Upgraded `meta.seed_version` from `9` to `10`.
- **Adjudication Engine:** Offline `Textual Analysis Brain` (`provider_id = "textual_analysis"`, strict offline lock) across all 70 Greek books, 39 Masoretic Hebrew books, and 70 Latin books.
- **Zero-Third-Party & Licence Hygiene:** 100% Python stdlib offline execution; Tiers 1–4 open-licence witnesses vote on the critical text; Tier 5 / NonCommercial / copyrighted study apparatus witnesses (`Stuttgart-BSV`, `Rahlfs (1935)`, `BHS (BHSA)`, `Tregelles (1879)`, `Pickering-f35`, `א (01) [CSP-OT]`, `SP (Samaritan)`, Dead Sea Scrolls, and ITSEE Old Latin `VL 2..15`) remain local study-only apparatus witnesses and are strictly stripped from all public open-licence exports.

---

## 2. Approved Editorial & Architectural Decisions (D1–D5)

- **D1 — Native Vulgate Latin Versification Anchor:** Switched `VERSIFICATION_ANCHORS[("latin", "OT"/"NT")]` to `["usfx_xml", "scrollmapper_csv", "latin_saints_json"]` (`Clem1598-USFX`) and moved `lat-saints-staging` (`Clem-Saints`) to `APPARATUS_ONLY`. Added `LANGUAGE_CHAPTER_COUNTS` and `chapters_for_language(book, lang)` so Latin preserves native Vulgate chapter divisions (`Esther 1–16`, `Daniel 1–14`, `Malachi 1–4`, `Joel 1–3`, `Psalms 1–150`). Purged stale pre-D1 Latin `Joel 4` (21 verses) and all Greek-slotted placeholder rows (`0` placeholders remaining). Rebuilt `_INVENTORY["latin"]`, `_RULES["latin"]`, and `_SITE_RULES["latin"]` in `studio/lexica/versification.py` so parallel Saints.Bible alignment lives strictly in the versification map.
- **D2 — Latin Witness Role & Orthography Consistency:** Moved `lat-amiatinus` (Genesis) to `APPARATUS_ONLY` to match Amiatinus NT across all 70 books; kept `Clem1598-USFX` as the consistent Sixto-Clementine voting base with `VulgHetzenauer (1906)` in `APPARATUS_ONLY` (preserving Invariant #17). Repaired 9 verified USFX typos (`Gen 20:2 uxore sua`, `Neh 4:18 ædificantium`, `Dan 5:2–3 Jerusalem`, `Hos 2:13 inaure sua`, `Amos 8:8 ejicietur`, `Mic 3:7 vultus`, `Luke 8:2 infirmitatibus`, `2 Cor 1:23 vestræ`) and normalized Latin `i`/`j` orthography (`eius -> ejus`, `iam -> jam`, `coniugem -> conjugem`, `Iethran -> Jethran`, `iecit -> jecit`, `adiecit -> adjecit`) in `offline_philological.py`.
- **D3 — Preserved Historic `[different reading]` Items:** Left untouched all 14 documented historic Sixto-Clementine Vulgate readings (e.g., `Gen 3:15 ipsa`, `Gen 4:8 Egrediamur foras`, `Ps 95:10`, etc.), all genuine Masoretic Ketiv/Qere traditions, and legitimate textual variants between editions.
- **D4 — Hebrew Masoretic Punctuation & Apparatus Cleanliness:** Kept `(ketiv) qere` convention intact while fixing 6 verse-ending `(ketiv)׃` sof pasuqs (`2 Sam 3:15, 19:32`, `Ezek 16:25`, `Isa 30:32`, `Neh 11:17`, `Ps 105:28`) to place sof pasuq on the qere before the parenthesised ketiv, unwrapping nested `<seg type="x-small">` in `Job 7:5` (`(וגיש) וְג֣וּשׁ`), eliminating double-parenthesised Ketiv-wela-Qere (`((...))`), repairing 7 MAM double-vowel slips, stripping parser artifacts in BHSA (`׆`), Letteris (bare niqqud), BenChayyim (`*`, `()`, `:`), and DSS (`-א-`), fixing maqaf `word_index` alignment in `apparatus_witnesses.py`, and enabling `neighbour_reference` for Hebrew so cross-chapter DSS steals (`Deut 4:40`, `Ps 148:14`, 31 total) are blocked.
- **D5 — Open-Licence Scrubber & GitHub Publication:** Added canonical open-licence scrubbing in `studio/exporter.py` (`KNOWN_TIER5_SIGLA`, `scrub_verse_for_open_export`, `scrub_chapter_for_open_export`, `scrub_chapter_json_for_open_export`, `export_chapter_files(..., open_licence_only=True)`) stripping all 23 Tier-5 sigla from both chapter metadata and every verse-level field (fixing the `verses[*].apparatus_witnesses` leak) while leaving local full Studio exports intact. Fixed the single-book overwrite bug in `studio/concordance_gold.py` (`_corpus_coverage`) and `studio/concordance.py` so `manifest.json["coverage"]`, `CONCORDANCE_REPORT.md`, and Tab 5 always report live full-corpus totals. Updated `studio/concordance_site.py` to split the native Vulgate Latin Sirach Translator's Prologue alongside Greek Sirach 1:1.

---

## 3. Source-Derived Trilingual Corpus Inventory (Before vs. After)

| Edition | Books | Chapters (Before -> After) | Verses (Before -> After) | `needs_review` | DB <-> Export Parity | Versification Drift |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Greek** (LXX 43 + NT 27) | 70 | 1,291 -> **1,291** | 34,210 -> **34,198** | 60 | 100% (`0` diffs) | `0` |
| **Hebrew** (MT OT) | 39 | 929 -> **929** | 23,213 -> **23,213** | 2 | 100% (`0` diffs) | `0` |
| **Latin** (Native Vulgate) | 70 | 1,290 -> **1,298** | 34,446 -> **34,952** | 0 | 100% (`0` diffs) | `0` |
| **Total** | **179** | **3,510 -> 3,518** | **91,869 -> 92,363** | **62** | **100% (`0` diffs)** | **`0`** |

- **Greek `-12` verses:** Eliminated 9 phantom trailing Swete Clean Psalm headings (`Ps 25:22, 27:14, 71:24, 102:29, 114:26, 116:10, 136:26, 149:14, 150:9`) and 3 chapter-boundary duplicate verses (`1 Sam 20:43`, `Num 16:44`, `Ezek 20:45`). Also resolved all 5 NT mid-clause raised-dot `·` splices (`Rom 15:19`, `Matt 25:16`, `1 Cor 14:37`, `Heb 13:21`, `John 18:17`), `Mark 6:23` recitative `ὅτι`, `Jas 2:3` stray `”`, NT elision apostrophe normalization (`U+02BC`), 12 Greek OT verse-division repairs (`Exod 39`, `Lev 8`, `Num 21 & 27`, `1 Kgs 6`, `1 Chr 1, 6, 7, 12`, `Neh 12`, `Job 41`, `Ps 12`, `Sir 41`, `Ezek 21`), polytonic/proper-name `_SLIPS`, and all Greek alphabetic numeral concordance tags (`Neh 7:41`, `Ezra 2:37–38`, `Neh 7:70`, `Judg 19:2`, `Job 1:17`).
- **Hebrew `23,213` exact MT verses:** `0` `(וג)יש` leaks (`Job 7:5` = `(וגיש)`), `0` `((...))` double parens, `0` verse-ending `(ketiv)׃`, `0` BHSA `׆`, `0` cross-chapter DSS steals (`Deut 4:40`, `Ps 148:14`), `0` maqaf apparatus `word_index` mismatches (down from 121), `0` unpointed witnesses credited on vocalic units (down from 35), and 5 OSHB `heb`/`arc` lemma corrections.
- **Latin `+506` verses (`34,952` exact native `Clem1598-USFX`):** Restored `Esther 11–16` (6 ch), `Daniel 13–14` (2 ch), `Malachi 4` (1 ch), and 366 previously dropped Vulgate verses; purged stale `Joel 4`; `0` placeholder verses; native Vulgate ordering restored (`Deut 5:17–18`, `Num 6:23–27`, `Jer 25–51`, `Sirach`, `Exod 39`).

---

## 4. Full-Corpus Concordance & Verification Metrics

| Language | Tokens | Indexed (Tagged) | Content | Function | Morph-Parsed | Untagged | Extra-Site Verses | Skipped Dup Tokens |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Hebrew** | 305,474 | 305,453 (100.0%) | 233,387 | 72,066 | 305,145 | 21 | 261 | 0 |
| **Greek** | 669,598 | 669,309 (100.0%) | 393,024 | 276,285 | 639,315 | 198 | 31 | 91 |
| **Latin** | 596,875 | 594,652 (99.6%) | 335,904 | 258,748 | 594,652 | 2,211 | 433 | 12 |

- **Website Pack (`Saints-Concordance-Pack/`):** `heb` 9,033 lemmas / 5,564 roots (`805,948` B gz), `grc` 13,836 lemmas / 10,125 roots (`1,399,612` B gz), `lat` 10,953 lemmas / 6,247 roots (`1,250,504` B gz), `7` colour hubs (`14,614` B gz), `6,097` hub occurrence CSV rows.
- **Versification & Anchor Integrity:** `snapshot_not_in_db = 0`, `not_in_snapshot = 0`, `target_missing_on_site = 0`, `studio_greek_target_missing_in_db = 0`, `orphaned_word_anchors = 0`, `orphaned_stream_tokens = 0`, `id_formula_errors = 0`, `unresolved = 0`.
- **Automated Test Suite (`python -B -m unittest discover -s tests -v`):** **479 / 479 PASS** (`0` failures, `0` errors, `0` skips, `371.863s`), including `LiveDatabase` and all four new Stage 1 regression suites (`test_stage1_greek`, `test_stage1_hebrew`, `test_stage1_latin`, `test_stage1_infra`).
- **Open-Licence Export Audit:** Programmatically verified `0` Tier-5 sigla leaks across all exported JSON, TSV, and Markdown files (outside the Markdown Section I `EXCLUDED_TIER5_OPEN_EXPORT` quarantine declaration table).
