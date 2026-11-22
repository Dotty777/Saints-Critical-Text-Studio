# Saints Latin Critical Text

- **Canonical Scope:** 70 books (43 OT + 27 NT) · 1,290 chapters · 34,446 verses
- **Witness Panel (`SEED_VERSION = 9`):** **27 ADMITTED witnesses** (`3` open-licence voting + `14` open-licence apparatus-only + `10` owner-authorized Tier 5 local study-only apparatus witnesses).
- **Method:** Reasoned eclecticism over open-licence Vulgate and early pandect witnesses (`Clem1598-USFX` + `Clem-Saints` [1 family] + `Amiatinus (A)` in Genesis). Tier 5 witnesses (`Stuttgart-BSV`, `VL 5 (d)` Bezae Latin, and 8 *Vetus Latina Iohannes* MSS) are strictly apparatus-only and never vote on the text.
- **Accuracy Audit:** See [docs/ACCURACY-AUDIT-2026-11-21.md](../docs/ACCURACY-AUDIT-2026-11-21.md) (**93.65%** exact match with Hetzenauer 1906 or Stuttgart BSV; sole truncated verse `Sirach 29:13` restored; Genesis 5 Roman numerals, `Gen 7:5`, `Gen 39:14`, `ę → æ`, safe `u → v`, and proper names verified fixed).

## File Formats per Chapter
- `*_Critical_Text.tsv` — **100% open-licence** verse-level tabular critical text (voting text only).
- `*_Critical_Text.md` — Four-section critical edition (Witness Declaration, Continuous Critical Text, Apparatus & Disregarded Noise Log, Verse-by-Verse Rationale).
- `*_Critical_Text.json` — Full structured collation, apparatus, and witness readings.

## Open-Licence Notice & Attribution
- **Voting Text (`.tsv`):** Released under **CC BY-SA 4.0** (`Clem1598-USFX` & `Clem-Saints` [PD], `Amiatinus (A)` Genesis [CC BY-SA 4.0]; non-Genesis `.tsv` voting text derives exclusively from Public Domain Vulgate witnesses; open apparatus adds `Amiatinus (A)` NT [CC BY-SA 4.0], `VulgHetzenauer (1906)`, `VulgSistina (1590)`, `VulgConte (2009)`, `Psalt-Pianum (1945)` [PD], and 9 COMPAUL Old Latin Pauline witnesses [CC BY 4.0]).
- **Local Studio Apparatus Notice:** Exported `.md` and `.json` files in this local Studio also include 10 owner-authorized Tier 5 study-only apparatus witnesses (`Stuttgart-BSV`, `VL 5 (d)` Codex Bezae Latin, and 8 *Vetus Latina Iohannes* MSS), each tagged `Tier 5` in Section I. Strip Tier 5 entries before commercial/public redistribution of `.md`/`.json` files; see [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

> **Public GitHub Open-Licence Export Note:** Every `.tsv`, `.json`, and `.md` chapter file in this public repository contains strictly **open-licence Tiers 1–4 witnesses only**. All Tier 5 study-only / NonCommercial / copyrighted witnesses are stripped before publication (0 Tier 5 witness readings or apparatus entries present).
