# Saints Hebrew Critical Text

- **Canonical Scope:** 39 Masoretic Old Testament books · 929 chapters · 23,213 verses (Hebrew & Biblical Aramaic), plus on-demand generation in Studio for **Hebrew Ben Sira** (46 extant chapters across 8 Genizah/Masada/Qumran MSS) and **Hebrew Psalm 151** (`11QPsᵃ Col. XXVIII`).
- **Witness Panel (`SEED_VERSION = 9`):** **21 ADMITTED witnesses** (`2` canonical Masoretic voting + `8` on-demand Ben Sira + `1` on-demand Ps 151 + `2` open-licence apparatus-only + `8` owner-authorized Tier 5 local study-only apparatus witnesses; `1` corrupt file disregarded).
- **Method:** Reasoned eclecticism over open-licence Masoretic witnesses (`MAM (Aleppo)` + `WLC (L)`). Tier 5 witnesses (`BHS (BHSA 2021)`, `SP (Samaritan Pentateuch v7.5.0)`, and 6 Qumran DSS scroll groups `1QIsaᵃ`, `1QIsaᵇ`, `4QSamᵃ`, `4QJerᵇ,ᵈ`, `11QPsᵃ`, `DSS-Torah`) are strictly apparatus-only and never vote on the 929 canonical chapters.
- **Accuracy Audit:** See [docs/ACCURACY-AUDIT-2026-11-21.md](../docs/ACCURACY-AUDIT-2026-11-21.md) (**99.16%** exact consonantal/Ketiv–Qere/plene–defective match with `BHS (BHSA 2021)`; `0` mechanical defects).

## File Formats per Chapter
- `*_Critical_Text.tsv` — **100% open-licence** verse-level tabular critical text (voting text only).
- `*_Critical_Text.md` — Four-section critical edition (Witness Declaration, Continuous Critical Text, Apparatus & Disregarded Noise Log, Verse-by-Verse Rationale).
- `*_Critical_Text.json` — Full structured collation, apparatus, and witness readings.

## Open-Licence Notice & Attribution
- **Canonical OT Voting Text (`.tsv`):** Released under **CC BY-SA 4.0** (`MAM (Aleppo)` [CC BY-SA 3.0], `WLC (L)` [Public Domain]; open apparatus adds `BenChayyim (1525)` [PD] and `Letteris (1852)` [PD / GPL-3.0]; on-demand Hebrew Ben Sira uses Rey & Reymond 2024 TEI [CC BY-SA 4.0]).
- **Local Studio Apparatus Notice:** Exported `.md` and `.json` files in this local Studio also include 8 owner-authorized Tier 5 study-only apparatus witnesses (`BHS (BHSA)`, `SP (Samaritan)`, and 6 Qumran DSS scroll groups, all `CC BY-NC 4.0`), each tagged `Tier 5` in Section I. Strip Tier 5 entries before commercial/public redistribution of `.md`/`.json` files; see [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

> **Public GitHub Open-Licence Export Note:** Every `.tsv`, `.json`, and `.md` chapter file in this public repository contains strictly **open-licence Tiers 1–4 witnesses only**. All Tier 5 study-only / NonCommercial / copyrighted witnesses are stripped before publication (0 Tier 5 witness readings or apparatus entries present).
