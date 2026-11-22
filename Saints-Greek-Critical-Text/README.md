# Saints Greek Critical Text

- **Canonical Scope:** 70 books (43 Old Greek / Septuagint + 27 New Testament) · 1,291 chapters (including Psalm 151) · 34,210 verses
- **Witness Panel (`SEED_VERSION = 9`):** **66 ADMITTED witnesses** (`12` open-licence voting + `50` open-licence apparatus-only + `4` owner-authorized Tier 5 local study-only apparatus witnesses).
- **Method:** Reasoned eclecticism over open-licence Tiers 1–4 voting witnesses (`Swete` family + `Sixtine/Brenton` in OT; `SRGNT`, `SBLGNT`, `BHP`, `Nestle1904`, `RP2018`, `TR (KJTR)`, `א (01)`, `B (03)` in NT). Tier 5 witnesses (`Rahlfs 1935`, `א (01) [CSP-OT]`, `Tregelles 1879`, `Pickering-f35`) are strictly apparatus-only and never vote on the text.
- **Accuracy Audit:** See [docs/ACCURACY-AUDIT-2026-11-21.md](../docs/ACCURACY-AUDIT-2026-11-21.md) (**99.50%** exact NT agreement with ≥1 of 6 major critical editions; all audited OCR, elision, polytonic, and homoeoteleuton defects verified fixed).

## File Formats per Chapter
- `*_Critical_Text.tsv` — **100% open-licence** verse-level tabular critical text (voting text only).
- `*_Critical_Text.md` — Four-section critical edition (Witness Declaration, Continuous Critical Text, Apparatus & Disregarded Noise Log, Verse-by-Verse Rationale).
- `*_Critical_Text.json` — Full structured collation, apparatus, and witness readings.

## Open-Licence Notice & Attribution
- **Greek Old Testament Voting Text (`01_Law/`–`04_Providence/` `.tsv`):** Released under **GNU GPL-3.0** (`Swete-Amicarelli` [GPL-3.0], `1st1K-LXX` [CC BY-SA 4.0], `Sixtine/Brenton` [PD]; open apparatus adds `OG-Daniel`, `A-Ottley (Isaiah)`, `LXX-Orthodox`).
- **Greek New Testament Voting Text (`05_Salvation/`–`07_Glory/` `.tsv`):** Released under **CC BY-SA 4.0** (`SRGNT`, `SBLGNT`, `BHP`, `TR (KJTR)` [CC BY 4.0], `B (03)` & `א (01)` [CC BY-SA 4.0], `Nestle1904` & `RP2018` [PD]; open apparatus adds `NA28 (TAGNT)`, `THGNT`, `WH1881`, `Tisch8`, `PT1904`, `TCGNT`, `TR*`, 18 CNTR early MSS, 5 IGNTP Pauline MSS, 13 INTF NTVMR MSS, and `Ξ (040)`).
- **Local Studio Apparatus Notice:** Exported `.md` and `.json` files in this local Studio also include 4 owner-authorized Tier 5 study-only apparatus witnesses (`Rahlfs 1935`, `א (01) [CSP-OT]`, `Tregelles 1879`, `Pickering-f35`), each tagged `Tier 5` in Section I. Strip Tier 5 entries before commercial/public redistribution of `.md`/`.json` files; see [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

> **Public GitHub Open-Licence Export Note:** Every `.tsv`, `.json`, and `.md` chapter file in this public repository contains strictly **open-licence Tiers 1–4 witnesses only**. All Tier 5 study-only / NonCommercial / copyrighted witnesses are stripped before publication (0 Tier 5 witness readings or apparatus entries present).
