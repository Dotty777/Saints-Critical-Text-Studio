# Third-Party Notices, Licensing & Attribution

**Saints Critical Text Studio** combines MIT-licensed original software with open-licence reconstructed critical texts and the Saints Concordance Pack (`SEED_VERSION = 9`, **114 ADMITTED witnesses**).

> **Important Redistribution Boundary (Catalogue v9):**
> - The **Voting Critical Texts** (`*_Critical_Text.tsv`, Section II of `*_Critical_Text.md`, and `verses[].critical_text` in `data/studio.db`) and the entire **Saints Concordance Pack** (`Saints-Concordance-Pack/`) are built **exclusively from open-licence / Public Domain Tiers 1–4 witnesses**. No NonCommercial (`CC BY-NC*`), NoDerivatives (`CC BY-ND`), or copyrighted modern critical edition ever votes on the 3,510 canonical Bible chapters or enters the Concordance Pack.
> - At the Studio owner's explicit directive, **22 Tier 5 / NonCommercial / study-only apparatus witnesses** (plus `11QPsᵃ Col. XXVIII` for on-demand Hebrew Psalm 151) are wired locally inside `catalog.APPARATUS_ONLY` for comparative textual criticism inside this Studio. Every Tier 5 witness is explicitly tagged `Tier 5` with its upstream licence in Section I of exported `.md` and `.json` files. **Before publishing or commercially redistributing `.md` or `.json` chapter files outside this local Studio, strip Tier 5 apparatus witnesses (or publish the pure open-licence `.tsv` / `Saints-Concordance-Pack` outputs).**

---

## 1. Component Licences at a Glance

| Component | Path | Licence |
| :--- | :--- | :--- |
| **Studio Application, CLI, Engine, Transliteration & Tests** | `app.py`, `cli.py`, `studio/`, `tests/`, `Saints-Concordance-Pack/saints-concordance-decoder.js` | **MIT License** ([LICENSE](LICENSE)) |
| **Saints Concordance Pack — Hebrew & Hubs** | `Saints-Concordance-Pack/saints-concordance-heb*.json.gz`, `saints-concordance-hubs.json.gz`, `saints-concordance-hub-occurrences.csv` | **CC BY 4.0** |
| **Saints Concordance Pack — Greek & Latin** | `Saints-Concordance-Pack/saints-concordance-grc*.json.gz`, `saints-concordance-lat*.json.gz` | **CC BY-SA 4.0** |
| **Saints Greek Critical Text — Old Testament (`.tsv` / Voting Text)** | `Saints-Greek-Critical-Text/01_Law/` – `04_Providence/` | **GNU GPL-3.0** ([LICENSES/GPL-3.0.txt](LICENSES/GPL-3.0.txt)) *(local `.md`/`.json` also carry Tier 5 apparatus entries — see notice above)* |
| **Saints Greek Critical Text — New Testament (`.tsv` / Voting Text)** | `Saints-Greek-Critical-Text/05_Salvation/` – `07_Glory/` | **CC BY-SA 4.0** *(open apparatus compatible under **GNU GPL-3.0**; local `.md`/`.json` also carry Tier 5 apparatus entries)* |
| **Saints Hebrew Critical Text (`.tsv` / Voting Text)** | `Saints-Hebrew-Critical-Text/01_Law/` – `04_Providence/` | **CC BY-SA 4.0** *(open apparatus compatible under **GNU GPL-3.0**; local `.md`/`.json` also carry Tier 5 apparatus entries)* |
| **Saints Latin Critical Text (`.tsv` / Voting Text)** | `Saints-Latin-Critical-Text/01_Law/` – `07_Glory/` | **CC BY-SA 4.0** *(non-Genesis `.tsv` voting text derives exclusively from Public Domain Vulgate witnesses; local `.md`/`.json` also carry Tier 5 apparatus entries)* |

> **Licence compatibility note:** Creative Commons **CC BY-SA 4.0** is officially designated one-way compatible with **GNU GPL-3.0** (https://creativecommons.org/share-your-work/licensing-considerations/compatible-licenses/). CC BY-SA 3.0 material (MAM Aleppo, el.wikisource Septuagint, MorphGNT derivations) is adapted under CC BY-SA 4.0 per CC BY-SA 3.0 §4(b).

---

## 2. Open-Licence Witness Attributions (Tiers 1–4 — 91 Witnesses)

Raw witness research corpora are excluded from Git (`.gitignore`).

### Greek Old Testament (Septuagint — 4 Voting + 3 Open Apparatus)
- **Swete-Amicarelli** *(voting)* — Henry Barclay Swete, *The Old Testament in Greek According to the Septuagint* (Cambridge 1909–1930, Public Domain); digital transcription by Pasquale Amicarelli via [LXX-Swete-1930](https://github.com/eliranwong/LXX-Swete-1930) (**GNU GPL-3.0**).
- **1st1K-LXX** *(voting, same Swete family)* — First1KGreek Septuagint EpiDoc TEI-XML (`tlg0527`), Open Greek and Latin Project (**CC BY-SA 4.0**).
- **Swete (B/A/א)** *(voting, same Swete family)* — Swete LXX Clean Unicode derivative of First1KGreek (**CC BY-SA 4.0** / Public Domain text).
- **Sixtine/Brenton** *(voting)* — Sir Lancelot C. L. Brenton (1851) / Sixtine Septuagint (1587) USFM (**Public Domain**).
- **OG-Daniel** *(apparatus-only)* — Old Greek (Septuagint) Daniel, Swete / First1KGreek `tlg056` (**CC BY-SA 4.0**).
- **A-Ottley (Isaiah)** *(apparatus-only)* — Richard Rusden Ottley (1904) Codex Alexandrinus diplomatic text of Isaiah (**Public Domain / CC BY-SA 4.0**).
- **LXX-Orthodox (Οʹ)** *(apparatus-only)* — Orthodox Ecclesiastical Septuagint via eBible.org (**Public Domain**).

### Greek New Testament (8 Voting + 47 Open Apparatus)
- **SRGNT** *(voting)* — *Statistical Restoration Greek New Testament* (2022), Alan Bunning, Center for New Testament Restoration (**CC BY 4.0**).
- **SBLGNT** *(voting)* — *The Greek New Testament: SBL Edition*, Michael W. Holmes, SBL & Logos (**CC BY 4.0**, https://sblgnt.com).
- **BHP** *(voting)* — *Bunning Heuristic Prototype Greek New Testament*, CNTR (**CC BY 4.0**).
- **Nestle1904** *(voting)* — Eberhard Nestle, *Novum Testamentum Graece* (1904, **Public Domain**).
- **RP2018 (Byz)** *(voting)* — Robinson–Pierpont Byzantine Textform 2018 (**Public Domain / Unlicense**).
- **TR (KJTR)** *(voting)* — Center for New Testament Restoration KJTR Collation (**CC BY 4.0**).
- **א (01) & B (03)** *(voting)* + **18 CNTR Early NT MSS** (`A/02`, `C/04`, `D/05`, `T/029`, `W/032`, `0171`, `0189`, `𝔓1`, `𝔓4`, `𝔓37`, `𝔓45`, `𝔓46`, `𝔓47`, `𝔓52`, `𝔓64+67`, `𝔓66`, `𝔓72`, `𝔓75`, *apparatus-only*) — Direct first-hand manuscript transcriptions, CNTR (`NT_CNTR_Early_MSS`, Alan Bunning, **CC BY-SA 4.0**).
- **NA28 (TAGNT) & THGNT** *(apparatus-only)* — Word streams reconstructed from STEPBible `TAGNT` (**CC BY 4.0**, Tyndale House Cambridge / STEPBible.org).
- **WH1881** *(apparatus-only)* — Westcott & Hort (1881, **Public Domain**; CNTR polytonic transcription **CC BY-SA 4.0**).
- **Tisch8** *(apparatus-only)* — Tischendorf 8th Edition (1869–1872, OSIS v2.8, **Public Domain**).
- **TCGNT (Byz)** & **TR-Boyd** *(apparatus-only)* — Robert Adam Boyd (**Public Domain**).
- **PT1904 (Byz)** *(apparatus-only)* — 1904/1912 Ecumenical Patriarchal Text, Basileios Antoniades (**Public Domain**).
- **TR-Elzevir (1624)** *(apparatus-only)* — 1624 Leiden Textus Receptus, Robinson `.UEL` (**Public Domain**).
- **TR-Scrivener (1894)** *(apparatus-only)* — Scrivener 1894 Textus Receptus (**Public Domain**; digital JSON **GNU GPL-3.0**).
- **TR-Stephanus (1550)** *(apparatus-only)* — Stephanus 1550 *Editio Regia* (**Public Domain**; CNTR transcription **CC BY-SA 4.0**).
- **13 INTF NTVMR NT MSS** (`L/019`, `N/022`, `Δ/037`, `Θ/038`, `Ψ/044`, `1/f¹`, `13/f¹³`, `33`, `565`, `700`, `892`, `1424`, `1739`, *apparatus-only*) — TEI-NTMSS transcriptions, Institut für Neutestamentliche Textforschung (**CC BY 4.0**).
- **5 IGNTP Pauline MSS** (`Dᵖ/06`, `Fᵖ/010`, `Gᵖ/012`, `81`, `1881`, *apparatus-only*) — ITSEE Birmingham / UBIRA eData / IGNTP (**CC BY 4.0**).
- **Ξ (040) Codex Zacynthius** *(apparatus-only)* — 6th-c. Luke 1–11 palimpsest transcription, ITSEE Birmingham / UBIRA eData (**CC BY 4.0**).

### Hebrew & Biblical Aramaic (2 Canonical Voting + 8 On-Demand Ben Sira + 2 Open Apparatus)
- **WLC (L)** *(voting)* — *Westminster Leningrad Codex* (Groves Center, https://tanach.us, **Public Domain**).
- **MAM (Aleppo)** *(voting)* — *Miqra 'al-pi ha-Mesorah* (Aleppo Codex Tradition, **CC BY-SA 3.0**).
- **Hebrew Ben Sira — 8 Direct MSS** (`BenSira-A`, `BenSira-B`, `BenSira-C`, `BenSira-D`, `BenSira-E`, `BenSira-F`, `Mas1h`, `11QPsᵃ (Sir)`, *on-demand voting for Sirach's 46 extant Hebrew chapters*) — Jean-Sébastien Rey & Eric D. Reymond (2024 TEI-XML via Biblissima+ / `metz-theolab/bensira-xml`, **CC BY-SA 4.0**).
- **BenChayyim (1525)** *(apparatus-only)* — Jacob ben Chayyim Second Rabbinic Bible tradition via eBible.org (**Public Domain**).
- **Letteris (1852)** *(apparatus-only)* — Meir Halevi Letteris 1852/1866 Masoretic Hebrew Bible (**Public Domain**; digital repo **GNU GPL-3.0**).

### Latin (3 Voting + 14 Open Apparatus)
- **Clem1598-USFX / Clem-Saints** *(voting, 1 family)* — Sixto-Clementine Vulgate (1598 Official Edition, **Public Domain**).
- **Amiatinus (A)** *(Genesis voting; all 27 NT books apparatus-only)* — *Codex Amiatinus*, Digital Latin Library TEI transcription (**CC BY-SA 4.0**).
- **VulgHetzenauer (1906)**, **VulgSistina (1590)**, **VulgConte (2009)** *(apparatus-only)* — Public Domain Vulgate editions via Scrollmapper MIT database.
- **Psalt-Pianum (1945)** *(apparatus-only)* — Pontifical Biblical Institute Hebrew-Based Psalter via DivinumOfficium (**Public Domain**).
- **9 COMPAUL Old Latin Pauline Witnesses** (`AMst`, `PEL`, `VL 51 (gig)`, `VL 61 (ar)`, `VL 64 (r)`, `VL 75 (d)`, `VL 77 (g)`, `VL 78 (f)`, `VL 89`, *apparatus-only*) — ITSEE Birmingham / UBIRA eData COMPAUL project (**CC BY 4.0**).

---

## 3. Owner-Authorized Tier 5 Study-Only Apparatus Witnesses (Local Studio Only — 22 Apparatus + 1 On-Demand Ps 151)

The following witnesses are wired locally into `catalog.APPARATUS_ONLY` (never voting on the 3,510 canonical chapters, never feeding `Saints-Concordance-Pack`) at the Studio owner's explicit request for local comparative scholarship. **Do not redistribute these texts commercially or outside their upstream licence terms:**

- **Greek (4):** `Tregelles (1879)` (Tyndale House digitization, **CC BY-NC-SA 3.0**); `Pickering-f35` (**CC BY-NC-ND**); `Rahlfs (1935)` (**Copyrighted / Study-Only**); `א (01) [CSP-OT]` Codex Sinaiticus Project XML v1.95 (**CC BY-NC-SA**).
- **Hebrew (8 apparatus + 1 on-demand Ps 151):** `BHS (BHSA 2021)` (ETCBC / VU Amsterdam, **CC BY-NC 4.0**); `SP (Samaritan Pentateuch v7.5.0)` (CACCHT / ETCBC, **CC BY-NC 4.0**); `1QIsaᵃ`, `1QIsaᵇ (1Q8)`, `4QSamᵃ (4Q51)`, `4QJerᵇ,ᵈ`, `11QPsᵃ (11Q5)`, `DSS-Torah (4Q)`, and on-demand `11QPsᵃ (Ps 151)` (Abegg / ETCBC DSS Text-Fabric, **CC BY-NC 4.0**).
- **Latin (10):** `Stuttgart-BSV` (Weber–Gryson Stuttgart Vulgate, **Copyrighted / Study-Only**); `VL 5 (d)` Codex Bezae Old Latin Gospels & Acts (Cambridge UL / ITSEE, **CC BY-NC-SA 3.0**); and 8 *Vetus Latina Iohannes* Old Latin MSS (`VL 2 (e)`, `VL 3 (a)`, `VL 4 (b)`, `VL 6 (c)`, `VL 8 (ff²)`, `VL 10 (f)`, `VL 14 (r¹)`, `VL 15 (aur)`, ITSEE Birmingham eData/61, **CC BY-NC-SA**).

---

## 4. Saints Concordance Pack Attributions (100% Open-Licence)

Full machine-readable attribution and change declarations are shipped in [`Saints-Concordance-Pack/manifest.json`](Saints-Concordance-Pack/manifest.json):

- **OpenScriptures Hebrew Bible (OSHB)** — Hebrew/Aramaic lemmas, morphology, and `VerseMap.xml` (**CC BY 4.0**).
- **OpenScriptures Hebrew Lexicon** — Lexical index of Brown–Driver–Briggs roots and glosses (**CC BY 4.0**).
- **STEPBible Data (Tyndale House Cambridge)** — `TAGNT`, `TAHOT`, `TBESH`/`TBESG` (brief `Gloss` column only — column 8 "Meaning" excluded), `TIPNR`, `TVTMS`, `TEHMC`, `TEGMC` (**CC BY 4.0**).
- **Open Scriptures Septuagint Project (`LxxLemmas` & Greek Word List)** (**CC BY 4.0**).
- **Strong's Greek Dictionary in XML** — Ulrik Sandborg-Petersen (**CC0**).
- **MorphGNT Morphological Lexicon (`derivation.yaml`)** — James K. Tauber (**CC BY-SA 3.0**).
- **GLAUx Corpus (`0527-*` Septuagint files only)** — Alek Keersmaekers (**CC BY-SA 4.0**; Septuagint source texts from `el.wikisource.org` **CC BY-SA 3.0**; Genesis manual treebank from Pedalion Trees **CC BY-SA 4.0**). No NonCommercial GLAUx source files or manual treebanks are read.
- **Lewis & Short, *A Latin Dictionary* (Perseus Digital Library TEI)** (**CC BY-SA 4.0**).
- **MACULA Greek & MACULA Hebrew (Biblica / Clear Bible)** — English/gloss alignment columns (`Cherith` **CC BY 4.0**, Berean gloss **Public Domain**).

### Summary of Changes by Saints.Bible
- Reconstructed trilingual critical texts using automated word-by-word collation, documented OCR/transcription repairs (`studio/source_repairs.py`), orthographic noise filtering, Greek elision harmonisation, Latin Roman-numeral/orthography normalisation, and Saints.Bible versification alignment (see [docs/ACCURACY-AUDIT-2026-11-21.md](docs/ACCURACY-AUDIT-2026-11-21.md)).
- Aligned open-licence lemma, root, and morphology tags word-by-word to the Saints Critical Texts; added English-friendly Latinized transliterations (`studio/translit.py`) for Greek and Hebrew/Aramaic roots, lemmas, and verse tokens; built parallel-verse Latin disambiguation (`studio/lexica/latin_parallel.py`) using exclusively open-licence Hebrew/Greek/Latin parallels and Lewis & Short.
