# Witness Expansion & Acquisition Plan (Catalogue v9 Status)

**Date:** 21 November 2026 · **Catalogue Version:** `SEED_VERSION = 9` (**114 ADMITTED witnesses**, `0` missing files)  
**Scope:** Greek (OT & NT), Hebrew & Biblical Aramaic (OT + Ben Sira + Psalm 151), and Latin (OT & NT)  
**Licensing Boundary:**
- **Voting Critical Text (`.tsv`, Section II, & `Saints-Concordance-Pack`):** Derived **strictly from open-licence / Public Domain Tiers 1–4 witnesses** (`Public Domain`, `CC0`, `CC BY 4.0`, `CC BY-SA 3.0/4.0`, `MIT/Unlicense`, `GPL-3.0`).
- **Owner-Authorized Tier 5 Apparatus-Only Witnesses (`catalog.APPARATUS_ONLY`):** Included locally in this Studio at the owner's explicit request for comprehensive scholarly comparison (`NA28`/`THGNT` word streams, `Rahlfs 1935`, `Tregelles 1879`, `Pickering-f35`, `א (01) [CSP-OT]`, `BHS (BHSA)`, `Samaritan Pentateuch`, `Dead Sea Scrolls`, `Stuttgart BSV`, and `Vetus Latina` NC-SA MSS). They **never vote** on the 3,510 canonical chapters and never feed the Saints Concordance Pack. *(Exception: on-demand Hebrew Psalm 151 uses `11QPsᵃ Col. XXVIII` as its sole surviving Hebrew manuscript.)*

---

## 1. Current State After Catalogue v9 (`114 ADMITTED Witnesses`)

| Language | Voting Witnesses | Open-Licence Apparatus-Only (`Tiers 1–4`) | Owner-Authorized Tier 5 Apparatus-Only | Disregarded |
| :--- | :--- | :--- | :--- | :--- |
| **Greek OT** | **2 independent families (4 copies):** `Swete-Amicarelli`, `1st1K-LXX`, `Swete (B/A/א)` *(1 vote)* + `Sixtine/Brenton` | **3 witnesses:** `OG-Daniel` (`tlg056`), `A-Ottley (Isaiah)`, `LXX-Orthodox (Οʹ)` | **2 witnesses:** `Rahlfs (1935)`, `א (01) [CSP-OT]` | — |
| **Greek NT** | **8 witnesses:** `SRGNT`, `SBLGNT`, `BHP`, `Nestle1904`, `RP2018 (Byz)`, `TR (KJTR)`, `B (03)`, `א (01)` | **47 witnesses:** `NA28 (TAGNT)`, `THGNT` *(CC BY 4.0)*; `Tisch8`, `WH1881`; `PT1904`, `TCGNT`, `TR-Boyd`, `TR-Elzevir (1624)`, `TR-Scrivener (1894)`, `TR-Stephanus (1550)`; **18 CNTR early MSS** (`A/02, C/04, D/05, T/029, W/032, 0171, 0189, 𝔓1, 𝔓4, 𝔓37, 𝔓45, 𝔓46, 𝔓47, 𝔓52, 𝔓64+67, 𝔓66, 𝔓72, 𝔓75`); **5 IGNTP Pauline MSS** (`Dᵖ/06, Fᵖ/010, Gᵖ/012, 81, 1881`); **13 INTF NTVMR MSS** (`L/019, N/022, Δ/037, Θ/038, Ψ/044, 1/f¹, 13/f¹³, 33, 565, 700, 892, 1424, 1739`); `Ξ (040)` *(Codex Zacynthius)* | **2 witnesses:** `Tregelles (1879)` *(CC BY-NC-SA 3.0)*, `Pickering-f35` *(CC BY-NC-ND)* | — |
| **Hebrew & Aramaic** | **2 canonical OT:** `MAM (Aleppo)`, `WLC (L)` *(incl. Biblical Aramaic)* · **On-demand deuterocanon:** 8 Hebrew Ben Sira MSS (`BenSira-A..F`, `Mas1h`, `11QPsᵃ (Sir)`, `CC BY-SA 4.0`, 46 extant chapters) + `11QPsᵃ (Ps 151)` *(sole surviving Hebrew witness, Tier 5)* | **2 witnesses:** `BenChayyim (1525)`, `Letteris (1852)` | **8 witnesses:** `BHS (BHSA 2021)`, `SP (Samaritan Pentateuch v7.5.0)`, `1QIsaᵃ`, `1QIsaᵇ (1Q8)`, `4QSamᵃ (4Q51)`, `4QJerᵇ,ᵈ`, `11QPsᵃ (11Q5)`, `DSS-Torah (4Q)` | `Leningrad-USFX` *(corrupt)* |
| **Latin** | **2 families in Genesis; 1 elsewhere:** `Clem1598-USFX` + `Clem-Saints` *(1 vote)* + `Amiatinus (A)` *(Genesis)* | **14 witnesses:** `Amiatinus (A)` *(all 27 NT books)*, `VulgHetzenauer (1906)`, `VulgConte (2009)`, `VulgSistina (1590)`, `Psalt-Pianum (1945)`, + **9 COMPAUL Old Latin Pauline MSS** (`AMst`, `PEL`, `VL 51 (gig)`, `VL 61 (ar)`, `VL 64 (r)`, `VL 75 (d)`, `VL 77 (g)`, `VL 78 (f)`, `VL 89`) | **10 witnesses:** `Stuttgart-BSV` *(Weber–Gryson)*, `VL 5 (d)` *(Codex Bezae Latin Gospels & Acts)*, + **8 Vetus Latina Iohannes MSS** (`VL 2 (e)`, `VL 3 (a)`, `VL 4 (b)`, `VL 6 (c)`, `VL 8 (ff²)`, `VL 10 (f)`, `VL 14 (r¹)`, `VL 15 (aur)`) | — |
| **Totals** | **26** *(15 voting on canonical 3,510 ch. + 9 on-demand Hebrew Sirach/Ps 151)* | **66 open-licence apparatus witnesses** | **22 Tier 5 study-only apparatus witnesses** | **1 corrupt** |

---

## 2. Completed Acquisitions (Phases 1–3 & Owner-Authorized Tier 5)

All major machine-readable datasets targeted in v8 have been acquired, parsed, verified, and wired into `SEED_VERSION = 9`:
- **Greek OT:** `OG-Daniel` (`tlg056`), `A-Ottley (Isaiah)`, `Rahlfs (1935)` *(8-word Hosea CSV offset repaired)*, `א (01) [CSP-OT]`.
- **Greek NT:** `NA28 (TAGNT)` & `THGNT` *(with `>N:`/`<N:` transposition & `|` meaning-variant parser fixes)*, `TR-Elzevir (1624)`, `Tregelles (1879)`, `Pickering-f35`, `Ξ (040)` (Codex Zacynthius), 7 more CNTR early MSS (`𝔓1`, `𝔓4`, `𝔓37`, `𝔓64+67`, `T/029`, `0171`, `0189`), 5 IGNTP Pauline MSS (`Dᵖ/06`, `Fᵖ/010`, `Gᵖ/012`, `81`, `1881`), and 7 more INTF NTVMR MSS (`N/022`, `Δ/037`, `Ψ/044`, `565`, `700`, `892`, `1424`).
- **Hebrew & Aramaic:** **8 Hebrew Ben Sira MSS** (`Rey & Reymond 2024 TEI`, `CC BY-SA 4.0`, covering all 46 extant chapters), **Hebrew Psalm 151** (`11QPsᵃ Col. XXVIII`), **6 Dead Sea Scrolls biblical witnesses** (`1QIsaᵃ`, `1QIsaᵇ`, `4QSamᵃ`, `4QJerᵇ,ᵈ`, `11QPsᵃ`, `DSS-Torah 4Q`), **`BHS (BHSA 2021)`** *(mid-verse parashah/inverted-nun markers stripped)*, **`SP (Samaritan Pentateuch v7.5.0)`**, plus companion Aramaic Targum datasets (`Onkelos`, `Jonathan`, `Pseudo-Jonathan`) staged in `Saints-Hebrew-Critical-Text/`.
- **Latin:** **9 COMPAUL Old Latin Pauline witnesses** (`CC BY 4.0`), **8 Vetus Latina Iohannes Old Latin MSS** (`CC BY-NC-SA`), **`VL 5 (d)` Codex Bezae Old Latin Gospels & Acts**, **`Psalt-Pianum (1945)`**, and **`Stuttgart-BSV`**.

*(Additionally, 118+ remaining CNTR `class 1/2/3` early NT fragments and 590+ INTF NTVMR XML minuscules are already on disk and immediately importable via `cli.py gatekeep`.)*

---

## 3. Remaining External / Long-Term Gaps (Not Yet Published Openly in Machine-Readable Form)

Only sources that do **not** currently exist as freely accessible, non-paywalled machine-readable transcriptions remain outside the Studio:
1. **Paywalled / Unpublished Copyrighted Modern Editions** *(strictly no piracy / no access-control bypass)*:
   - **Greek:** Göttingen *Septuaginta* (Vandenhoeck & Ruprecht), *Editio Critica Maior* (INTF/DBG) full apparatus, *NA29* / *UBS6* (unpublished/copyrighted).
   - **Hebrew / Aramaic:** *BHQ* (Biblia Hebraica Quinta), *HUBP* (Hebrew University Bible Project), *HBCE* (Hebrew Bible: A Critical Edition), locked Sefaria Targum Neofiti.
   - **Latin:** Rome Benedictine Vulgate OT, Beuron *Vetus Latina* print fascicles, Jülicher *Itala* Gospels, Nova Vulgata (Vatican).
2. **Ongoing Open-Scholarship Releases to Track:**
   - **Codex Amiatinus OT (Exodus–2 Maccabees):** Digital Latin Library (`github.com/adunning/bedes-bible`) — drop new XML book files into `OT_NT_Codex_Amiatinus_TEI/text/` and map in `_AMIATINUS_BOOK_FILES` as published.
   - **Public-Domain Historic Prints Requiring Clean OCR/Keying:** Wordsworth–White *Novum Testamentum Latine* (pre-1929 vols), Jerome *Psalterium iuxta Hebraeos* (Lagarde 1874 / Harden 1922), Ranke *Codex Fuldensis* (1868), Gwynn *Book of Armagh* (1913), von Gall *Samaritan Pentateuch* (1914–1918), Brooke–McLean *Larger Cambridge Septuagint* (pre-1929 vols), Field *Hexapla* (1875), Lachmann (1842–1850), and early Hebrew codices (`Cairo C`, `Sassoon 507/1053`, `BL Or. 4445`).
   - **Hebrew Ben Sira Chapters 2, 17, 24, 28, 29:** Permanently unattested in any known extant Hebrew manuscript (survive only in Greek, Syriac, and Latin).

---

## 4. Standard Workflow for Adding Future Witnesses

1. Verify licence metadata and known edition fingerprints.
2. Stage in the matching Tier folder (`01_Tier1`–`04_Tier4` for open-licence; `05_Tier5` for NC/study-only).
3. Register via `cli.py gatekeep` or `studio/db.py`, keeping new comparative editions/MSS in `catalog.APPARATUS_ONLY` so the audited voting panel and calibrated confidence remain stable.
4. Measure any candidate voting-panel change across the full corpus in a temp sandbox (`CTS_DATA_DIR` / `CTS_OUTPUT_ROOT`) before touching live outputs; see [ACCURACY-AUDIT-2026-11-21.md](ACCURACY-AUDIT-2026-11-21.md) for the empirical methodology.
5. Update `THIRD_PARTY_NOTICES.md` and run the complete 10-module unittest suite.
