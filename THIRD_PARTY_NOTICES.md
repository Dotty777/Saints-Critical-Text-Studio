# Third-Party Notices, Licensing & Attribution

**Saints Critical Text Studio** combines MIT-licensed original software with open-licence reconstructed critical texts and the Saints Concordance Pack. Every component uses strictly open-licence or Public Domain material; **no NonCommercial (CC BY-NC), NoDerivatives (CC BY-ND), or copyrighted modern critical editions** (such as Rahlfs 1935, Nestle-Aland / UBS, BHS, Weber–Gryson Stuttgart Vulgate, Pickering Family 35, PROIEL, ETCBC BHSA, or the CC BY-NC-SA Codex Sinaiticus TEI-XML) are included in this repository or used to generate its outputs.

---

## 1. Component Licences at a Glance

| Component | Path | Licence |
| :--- | :--- | :--- |
| **Studio Application, CLI, Engine, Transliteration & Tests** | `app.py`, `cli.py`, `studio/`, `tests/`, `Saints-Concordance-Pack/saints-concordance-decoder.js` | **MIT License** ([LICENSE](LICENSE)) |
| **Saints Concordance Pack — Hebrew & Hubs** | `Saints-Concordance-Pack/saints-concordance-heb*.json.gz`, `saints-concordance-hubs.json.gz`, `saints-concordance-hub-occurrences.csv` | **CC BY 4.0** |
| **Saints Concordance Pack — Greek & Latin** | `Saints-Concordance-Pack/saints-concordance-grc*.json.gz`, `saints-concordance-lat*.json.gz` | **CC BY-SA 4.0** |
| **Saints Greek Critical Text — Old Testament** | `Saints-Greek-Critical-Text/01_Law/` – `04_Providence/` | **GNU GPL-3.0** ([LICENSES/GPL-3.0.txt](LICENSES/GPL-3.0.txt)) |
| **Saints Greek Critical Text — New Testament** | `Saints-Greek-Critical-Text/05_Salvation/` – `07_Glory/` | **CC BY-SA 4.0** (combined apparatus files including Scrivener 1894 JSON reference also compatible under **GNU GPL-3.0**) |
| **Saints Hebrew Critical Text** | `Saints-Hebrew-Critical-Text/01_Law/` – `04_Providence/` | **CC BY-SA 4.0** (combined apparatus files including Letteris 1852 reference also compatible under **GNU GPL-3.0**) |
| **Saints Latin Critical Text** | `Saints-Latin-Critical-Text/01_Law/` – `07_Glory/` | **CC BY-SA 4.0** (non-Genesis books derive exclusively from Public Domain Vulgate witnesses) |

> **Licence compatibility note:** Creative Commons **CC BY-SA 4.0** is officially designated one-way compatible with **GNU GPL-3.0** (https://creativecommons.org/share-your-work/licensing-considerations/compatible-licenses/). CC BY-SA 3.0 material (MAM Aleppo, el.wikisource Septuagint, MorphGNT derivations) is adapted under CC BY-SA 4.0 per CC BY-SA 3.0 §4(b).

---

## 2. Reconstructed Critical Text Witness Attributions

Raw witness research corpora are excluded from this repository (`.gitignore`) to keep the repository lightweight and ensure no quarantined study-only corpora are ever redistributed. The reconstructed chapter files (`*_Critical_Text.{md,tsv,json}`) were built strictly from the following open-licence witnesses:

### Greek Old Testament (Septuagint)
- **Swete-Amicarelli** — Henry Barclay Swete, *The Old Testament in Greek According to the Septuagint* (Cambridge 1909–1930, Public Domain); digital transcription compiled by Pasquale Amicarelli via [LXX-Swete-1930](https://github.com/eliranwong/LXX-Swete-1930) (**GNU GPL-3.0**).
- **1st1K-LXX** — First1KGreek Septuagint EpiDoc TEI-XML (`tlg0527`), Open Greek and Latin Project (**CC BY-SA 4.0**).
- **Swete (B/A/א)** — Swete LXX Clean Unicode derivative of First1KGreek (**CC BY-SA 4.0** / Public Domain text).
- **Sixtine/Brenton** — Sir Lancelot C. L. Brenton (1851) / Sixtine Septuagint (1587) USFM (**Public Domain**).
- **LXX-Orthodox (Οʹ)** *(apparatus-only)* — Orthodox Ecclesiastical Septuagint via eBible.org (**Public Domain**).

### Greek New Testament
- **SRGNT** — *Statistical Restoration Greek New Testament* (2022), Alan Bunning, Center for New Testament Restoration (**CC BY 4.0**).
- **SBLGNT** — *The Greek New Testament: SBL Edition*, edited by Michael W. Holmes, Society of Biblical Literature & Logos Bible Software (**CC BY 4.0**, https://sblgnt.com).
- **BHP** — *Bunning Heuristic Prototype Greek New Testament*, Center for New Testament Restoration (**CC BY 4.0**).
- **א (01) & B (03)** — Direct manuscript transcriptions of Codex Sinaiticus and Codex Vaticanus, Center for New Testament Restoration (`NT_CNTR_Early_MSS`, Alan Bunning, **CC BY-SA 4.0**).
- **Nestle1904** — Eberhard Nestle, *Novum Testamentum Graece* (1904, **Public Domain**).
- **RP2018 (Byz)** — Robinson–Pierpont Byzantine Textform 2018 (**Public Domain / Unlicense**).
- **TR (KJTR)** — Center for New Testament Restoration KJTR Collation (**CC BY 4.0**).
- **TCGNT (Byz)** *(apparatus-only)* — *The Text-Critical Greek New Testament: Byzantine Text*, Robert Adam Boyd (**Public Domain**).
- **PT1904 (Byz)** *(apparatus-only)* — 1904/1912 Ecumenical Patriarchal Text, Basileios Antoniades (**Public Domain**).
- **TR-Boyd (Elz/Scr/Steph)** *(apparatus-only)* — Polytonic Textus Receptus, Adam Boyd (**Public Domain**).
- **TR-Scrivener (1894)** *(apparatus-only)* — F. H. A. Scrivener 1894 Textus Receptus (underlying 1894 text **Public Domain**; digital JSON repository **GNU GPL-3.0**).

### Hebrew & Biblical Aramaic (Old Testament)
- **WLC (L)** — *Westminster Leningrad Codex* (Groves Center, https://tanach.us, **Public Domain**).
- **MAM (Aleppo)** — *Miqra 'al-pi ha-Mesorah* (Aleppo Codex Tradition, https://en.wikisource.org/wiki/User:Dovi/Miqra_according_to_the_Mesorah, **CC BY-SA 3.0**).
- **BenChayyim (1525)** *(apparatus-only)* — Jacob ben Chayyim Second Rabbinic Bible tradition via eBible.org (**Public Domain**).
- **Letteris (1852)** *(apparatus-only)* — Meir Halevi Letteris 1852/1866 Masoretic Hebrew Bible (underlying 1852/1866 text **Public Domain**; digital UTF-8 repository https://github.com/benemanuel/letteris **GNU GPL-3.0**).

### Latin (Old & New Testaments)
- **Clem1598-USFX / Clem-Saints** — Sixto-Clementine Vulgate (1598 Official Edition, eBible.org / VulSearch, **Public Domain**).
- **Amiatinus (A)** — *Codex Amiatinus* (Genesis), Digital Latin Library TEI transcription (**CC BY-SA 4.0**).
- **VulgHetzenauer (1906)** *(apparatus-only)* — Michael Hetzenauer Critical Clementine Edition (Innsbruck 1906, via Scrollmapper MIT database, **Public Domain**).
- **VulgSistina (1590)** *(apparatus-only)* — Pope Sixtus V Official Rome Edition (1590, via Scrollmapper MIT database, **Public Domain**).
- **VulgConte (2009)** *(apparatus-only)* — Ronald L. Conte Jr. SacredBible Clementine Edition (2009, via Scrollmapper MIT database, **Public Domain**).

---

## 3. Saints Concordance Pack Attributions

Full machine-readable attribution and change declarations are also shipped in [`Saints-Concordance-Pack/manifest.json`](Saints-Concordance-Pack/manifest.json):

- **OpenScriptures Hebrew Bible (OSHB)** — Hebrew/Aramaic lemmas, morphology, and `VerseMap.xml` (https://hb.openscriptures.org, **CC BY 4.0**).
- **OpenScriptures Hebrew Lexicon** — Lexical index of Brown–Driver–Briggs roots and glosses (https://github.com/openscriptures/HebrewLexicon, **CC BY 4.0**).
- **STEPBible Data (Tyndale House Cambridge)** — `TAGNT`, `TAHOT`, `TBESH`/`TBESG` (brief `Gloss` column only — column 8 "Meaning" is excluded), `TIPNR`, `TVTMS`, `TEHMC`, `TEGMC` (https://STEPBible.github.io/STEPBible-Data, **CC BY 4.0**).
- **Open Scriptures Septuagint Project (`LxxLemmas` & Greek Word List)** — https://github.com/openscriptures/GreekResources (**CC BY 4.0**).
- **Strong's Greek Dictionary in XML** — Ulrik Sandborg-Petersen (https://github.com/morphgnt/strongs-dictionary-xml, **CC0**).
- **MorphGNT Morphological Lexicon (`derivation.yaml`)** — James K. Tauber (https://github.com/morphgnt/morphological-lexicon, **CC BY-SA 3.0**).
- **GLAUx Corpus (`0527-*` Septuagint files only)** — Alek Keersmaekers (Keersmaekers 2021, *LChange*, doi:10.18653/v1/2021.lchange-1.6; https://github.com/alekkeersmaekers/glaux, **CC BY-SA 4.0**; Septuagint source texts from `el.wikisource.org` **CC BY-SA 3.0**; Genesis manual treebank from Pedalion Trees **CC BY-SA 4.0**). No NonCommercial GLAUx source files or NonCommercial manual treebanks are read.
- **Lewis & Short, *A Latin Dictionary* (Perseus Digital Library TEI)** — https://github.com/PerseusDL/lexica (**CC BY-SA 4.0**).
- **MACULA Greek & MACULA Hebrew (Biblica / Clear Bible)** — English/gloss alignment columns (`Cherith` **CC BY 4.0**, Berean gloss **Public Domain**; https://github.com/Clear-Bible/macula-greek, https://github.com/Clear-Bible/macula-hebrew, **CC BY 4.0**).

### Summary of Changes by Saints.Bible
- Reconstructed trilingual critical texts using automated word-by-word collation, documented OCR/transcription repairs, orthographic noise filtering, and Saints.Bible versification alignment.
- Aligned open-licence lemma, root, and morphology tags word-by-word to the Saints Critical Texts; added English-friendly Latinized transliterations (`studio/translit.py`) for Greek and Hebrew/Aramaic roots, lemmas, and verse tokens; built parallel-verse Latin disambiguation (`studio/lexica/latin_parallel.py`) using exclusively open-licence Hebrew/Greek/Latin parallels and Lewis & Short.
