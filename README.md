# Saints Critical Text Studio

**Self-contained, offline-capable desktop app, edition library, Saints Concordance, and witness gatekeeper for building the open-source Saints Critical Texts of the Bible in Greek, Hebrew and Latin.**

- **Studio Code:** [MIT License](LICENSE)
- **Saints Concordance Pack:** CC BY 4.0 (Hebrew & Hubs) · CC BY-SA 4.0 (Greek & Latin) · MIT (`saints-concordance-decoder.js`)
- **Reconstructed Critical Texts (Voting Text / `.tsv`):** Greek OT under [GNU GPL-3.0](LICENSES/GPL-3.0.txt) · Greek NT, Hebrew & Latin under CC BY-SA 4.0 (with GPL-3.0 compatibility where apparatus witnesses use GPL-3.0 repos)
- **Witness Catalogue (`SEED_VERSION = 9`):** **114 ADMITTED witnesses** (`66` Greek, `21` Hebrew/Aramaic, `27` Latin) — `91` open-licence Tiers 1–4 witnesses plus `23` owner-authorized Tier 5 local study-only apparatus witnesses (kept strictly non-voting on the 3,510 canonical chapters so the voting critical text and Saints Concordance Pack stay 100% open-licence).
- **Full Attributions, Licence Ledger & Accuracy Audit:** See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), [docs/OPEN-LICENCE-ACQUISITION-PLAN.md](docs/OPEN-LICENCE-ACQUISITION-PLAN.md), [docs/ACCURACY-AUDIT-2026-11-21.md](docs/ACCURACY-AUDIT-2026-11-21.md), and [`Saints-Concordance-Pack/manifest.json`](Saints-Concordance-Pack/manifest.json).

---

## What it does

1. **Gatekeeps witnesses.** Every source file is checked before it may vote: licence (NonCommercial / NoDerivatives / protected editions are quarantined), script purity and encoding damage (corrupt files are disregarded), and duplication (a copy of an admitted witness is disregarded or down-weighted).
2. **Aligns verse numbering by content.** Editions number chapters differently (Swete vs. Brenton in Joel and Malachi, the Vulgate vs. Saints.Bible numbering, the Septuagint tribe order in Numbers 1…). Each witness is re-aligned to the language's numbering anchor by comparing wording across the current and neighbouring chapters, so a verse is never collated against a different verse. Every re-alignment is listed in the chapter's output.
3. **Collates word by word** and sorts each difference into:
   - **orthographic noise** — spelling conventions (movable ν, itacism, elision κατὰ/κατʼ, doubled ρ/π/κ/σ and Ἰωάννης — but not λλ, which separates tenses such as βάλλειν/βαλεῖν — u/v, plene/defective Hebrew spelling, qamats qaṭan, divine-name pointing; an iota subscript difference such as γῆ/γῇ is a case difference and stays in the apparatus), nomina sacra (`ιυ̅` = Ἰησοῦ), verified letter-numeral expansions (`ιδʹ` = δεκατέσσαρες), punctuation, and differences between two digital copies of one printed edition. Numerals must match in value and wording; differing values, ambiguous grammatical forms, and word order stay in the apparatus. Combined σσ/σ and ι/ει spelling in Matthew 1:18 is logged, while the distinct words χειμάρρων/χιμάρων in Micah 6:7 remain separate. Surface differences are kept in a "Disregarded Surface Noise" log with the reason;
   - **substantive variants** — which go to the critical apparatus.
4. **Adjudicates** each variant by weighted vote of independent edition families (two digital copies of one edition count once), with a small lectio-brevior bonus for omissions supported by Vaticanus, Sinaiticus or Amiatinus. A whole verse that weightier witnesses lack (e.g. Mark 16:9–20, John 7:53–8:11) is printed in `⟦ ⟧` with a verse-level apparatus entry — never silently deleted. Printed NT editions that simply skip a verse number (SBLGNT has no Matt 17:21) count as lacking it; a verse found in one NT text stream only (RP/TR's Acts 19:41, Rom 14:24–26) is bracketed with low confidence and its duplicate elsewhere is named.
   Two safety nets work on the whole verse after the word-by-word vote, because the aligner can put one phrase at two places:
   - **word conservation** (Greek NT) — a word that witnesses with most of the weight contain, but whose support was split between two positions so that it lost at both (Matt 20:30 κύριε, Matt 22:43 κύριον, John 14:16 ᾖ), is printed once at the better-supported position. Words are compared by a spelling-tolerant key (ἐπίσταται = ἐφίσταται), a forced reading may only add words that are themselves missing, a position backed by a single witness is used only when the word is near-certain, and a word that witnesses really lacking it outvoted is left alone;
   - **duplicate removal** (all languages) — a content word printed more often than any witness has it (a transposed phrase adopted at both places) is removed again; units decided by an OCR repair are never reopened;
   - **omission credit follows the words** (Greek NT) — a witness whose copy of the "omitted" words sits in a neighbouring unit where its reading loses is not counted as omitting them (Mark 3:14 and Luke 22:31 in Sinaiticus); a witness that merely transposed the words keeps its vote.
   Spelling variants of one reading (γινώσκομεν / B's γεινωσκομεν) are pooled before the vote.
   **Versification repairs** before collation: a witness verse that runs across the anchor's verse division is re-divided there (Swete's Gen 3:1 = Brenton's 2:25 + 3:1, MAM's Num 26:1 = WLC's 25:19 + 26:1, Swete's Ezra 6:19 = Brenton's 6:19 + 6:20, Swete's 2 Sam 11:27 running into 12:1); a witness verse left without a partner whose words the anchor prints in the neighbouring verse is folded into it (Swete's Joshua 9:3–8 = Brenton's 9:2, RP's 2 Cor 13:13 = SBLGNT's 13:12b, Swete's Prov 24:24–37 = Brenton's 24:22); an over-long witness verse whose extra words the anchor prints elsewhere is trimmed (Swete's Sir 30:24); leftovers whose words are printed under another number are left out and logged (stale Swete Clean verses, MAM's 1 Sam 23:29 = 24:1). The anchor edition's verses are never dropped. Where Swete's digitisation lost words at a chapter break (the chapter numeral stood there: Gen 9:1, 27:46, Exod 5:23, 6:1), its silence at that edge casts no vote, unless the words turn up in its neighbouring verse. Every witness verse that finds no place is logged.
   **Confidence** is fitted per unit against modern critical-edition agreement on the Greek NT (softmax over pooled, family-deduplicated support, with the Byzantine–TR dependence and singular readings of 01/03 discounted; fitted with a whole witness stream held out). A verse's score is the product of its units' scores. This assumes independence between units and is a heuristic verse-level score, not a measured probability that every word is original. Outside the Greek NT the same formula is used but is labelled uncalibrated.
5. **Lets a human decide.** Any verse can be edited and locked; locked verses survive re-collation. "Adopt variant" swaps exactly the lemma's words by position.
6. **Houses & Exports** each chapter as Markdown (four-section edition), JSON (full collation and provenance) and TSV (for translation pipelines) directly inside `Saints-{Greek,Hebrew,Latin}-Critical-Text/<division>/<book>/` within the Studio folder, and displays them in the built-in **Saints Critical Text Home (Library)** tab.

### Witnesses on disk (`SEED_VERSION = 9` · 114 ADMITTED)

| Language | Voting Witnesses | Apparatus-Only Witnesses (`catalog.APPARATUS_ONLY`) | Notes |
| :--- | :--- | :--- | :--- |
| **Greek OT** | Swete in 3 copies voting once (`Swete-Amicarelli`, `1st1K-LXX`, `Swete (B/A/א)`) + `Sixtine/Brenton` | **Open (3):** `OG-Daniel` (`tlg056`), `A-Ottley (Isaiah)`, `LXX-Orthodox (Οʹ)` · **Tier 5 Local (2):** `Rahlfs (1935)`, `א (01) [CSP-OT]` | Diplomatic Vaticanus (Swete) vs Sixtine/Brenton; Rahlfs 1935 & Sinaiticus OT recorded in apparatus. Daniel uses Theodotion with Old Greek in apparatus. |
| **Greek NT** | `SRGNT`, `SBLGNT`, `BHP`, `Nestle1904`, `RP2018 (Byz)`, `TR (KJTR)`, `א (01)`, `B (03)` | **Open (47):** `NA28 (TAGNT)`, `THGNT`, `WH1881`, `Tisch8`, `PT1904`, `TCGNT`, `TR-Boyd`, `TR-Elzevir (1624)`, `TR-Scrivener (1894)`, `TR-Stephanus (1550)`, 18 CNTR early MSS (`A/02, C/04, D/05, T/029, W/032, 0171, 0189, 𝔓1, 𝔓4, 𝔓37, 𝔓45–𝔓75`), 5 IGNTP Pauline MSS (`Dᵖ/06, Fᵖ/010, Gᵖ/012, 81, 1881`), 13 INTF NTVMR MSS (`L/019, N/022, Δ/037, Θ/038, Ψ/044, 1/f¹, 13/f¹³, 33, 565, 700, 892, 1424, 1739`), `Ξ (040)` · **Tier 5 Local (2):** `Tregelles (1879)`, `Pickering-f35` | **99.50%** exact agreement with ≥1 of 6 major critical editions (`NA28`/`THGNT`/`SBL`/`SR`/`Treg`/`WH`). CNTR MES & INTF/IGNTP TEI-NTMSS markup decoded cleanly. |
| **Hebrew & Aramaic** | Canonical OT (929 ch.): `MAM (Aleppo)`, `WLC (L)` · On-demand deuterocanon: 8 Hebrew Ben Sira MSS (`BenSira-A..F`, `Mas1h`, `11QPsᵃ (Sir)`, 46 extant ch.) + `11QPsᵃ (Ps 151)` | **Open (2):** `BenChayyim (1525)`, `Letteris (1852)` · **Tier 5 Local (8):** `BHS (BHSA 2021)`, `SP (Samaritan Pentateuch v7.5.0)`, `1QIsaᵃ`, `1QIsaᵇ (1Q8)`, `4QSamᵃ (4Q51)`, `4QJerᵇ,ᵈ`, `11QPsᵃ (11Q5)`, `DSS-Torah (4Q)` | **99.16%** exact consonantal/Ketiv–Qere/plene–defective match with `BHS (BHSA)`; ketiv printed in parentheses before qere. Disregarded: `Leningrad-USFX` (corrupt). |
| **Latin** | `Clem1598-USFX` + `Clem-Saints` (1 family), `Amiatinus (A)` (Genesis) | **Open (14):** `Amiatinus (A)` (all 27 NT books), `VulgHetzenauer (1906)`, `VulgConte (2009)`, `VulgSistina (1590)`, `Psalt-Pianum (1945)`, 9 COMPAUL Old Latin Pauline MSS (`AMst, PEL, VL 51/61/64/75/77/78/89`) · **Tier 5 Local (10):** `Stuttgart-BSV`, `VL 5 (d)` (Bezae Latin), 8 *Vetus Latina Iohannes* MSS (`VL 2/3/4/6/8/10/14/15`) | **93.65%** exact match with Hetzenauer (1906) or Stuttgart BSV; Roman numerals in Amiatinus Gen 5 normalised to spelled-out Latin numbers; `ę → æ`, safe `u → v`, and proper-name capitalisation applied. |

Disregarded: eBible `Leningrad-USFX` (glued words). All Tier 5 witnesses are strictly non-voting (`catalog.APPARATUS_ONLY`) for the 3,510 canonical chapters; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [docs/ACCURACY-AUDIT-2026-11-21.md](docs/ACCURACY-AUDIT-2026-11-21.md).

### Corpus-frequency safeguard (Greek)

Where the two Greek OT families disagree by one or two letters and the winning form occurs almost nowhere in the whole Greek corpus while the other form is common (e.g. Swete's OCR `Γαντοκράτωρ` vs `παντοκράτωρ`, `νεαυίσκοι` vs `νεανίσκοι`), the common form is adopted and the decision is logged as a probable transcription error. Accent forms found almost nowhere else (`τοὺ` for `τοῦ`) are corrected the same way. The lexicon is cached in `data/lexicon_greek.json` and rebuilt when witnesses change.

Counts alone never decide: a genuine rare reading of Codex B occurs once in the corpus, just like a garbled word, so a repair also needs a change OCR actually makes — a visually confusable letter (ρ/π, ο/α, ν/υ, γ/λ…), one letter dropped or added, or two letters swapped — and is refused when another common word is an equally good reading of the damaged letter. Preverb changes, itacism, movable ν, doubled consonants and elided forms are never "repaired". Tokens with punctuation, '/' or '(??)' inside them are broken tokens; Latin look-alike letters are read as Greek when that gives an attested word (’Aχεικὰμ → Ἀχεικὰμ, keeping B's spelling), footnote digits are removed (θρό9νου → θρόνου), and stray sigla ('B', 'ABBREV') are dropped.

Two grammar checks catch OCR slips that make another common form, where counts cannot decide: a word that differs from the other edition only by a lost iota subscript right after ἐν, σύν, τῇ or τῷ, or right after a dative with the same ending and no punctuation between (`ἐν τῆ γῆ`, `τῇ ἡμέρα τῇ ἕκτη`, `ἐν ὅλῃ γῆ` → the dative; never a capitalised name such as the indeclinable Φαραώ), and Swete's υ-for-ν slip making a genitive right after the accusative article τόν/τό (`τὸν οἶκου` → `οἶκον`; genitive pronouns such as `τὸν αὐτοῦ` are left alone). Both apply only when the damaged reading is one edition family's and are logged with the reason.

**Three copies of Swete, one vote.** Where the Amicarelli transcription and the two OCR copies of Swete disagree, one reading stands for the edition (logged as an encoding difference): the one another edition shares; else the one that is another edition's reading in another spelling (Μαχεὶρ ~ Brenton's Μαχὶρ); else words against a gap when another edition has words there; else, when the transcription's form occurs nowhere else in the corpus and the OCR copies' form one or two letters away is common, the OCR copies' (keying slips such as Ἰεδᾶε for Ἰωδᾶε); else the transcription. Swete's own word division (ἀνὰ μέσον, ἵνα τί, διὰ τοῦτο, τὸ πρωί) is printed, not Brenton's joined forms. A spelling that the transcription and the OCR share is Swete's own and is never replaced by Brenton's (Ἰεροσολύμων in 2 Maccabees, θάλασσαι in Dan 3:77).

**Documented repairs of the Swete copies** (`studio/source_repairs.py`). About 40 known slips are mended at import, each only while the copy reads exactly as recorded, and each logged with the chapter. These include keying slips of the transcription (Σαμονὴλ, a skipped clause in Judg 11:19), isolated words in the OCR copies that diverged from Swete's printed Codex B text (3 Kgdms 2:3, 21:25, 21:32), and places where Swete divides verses differently from Brenton (Judg 2:14–15, Song 7:1, Prov 31:26–27, Eccl 7–9, Num 16:36–17:28, Dan 3:77–78, Josh 12:20–22). A wrong word becomes a gap that casts no vote, so the other copies of Swete decide. No word is ever supplied, and the original files are untouched.

**Apparatus-only editions & direct manuscripts** (`catalog.APPARATUS_ONLY`, `studio/apparatus_witnesses.py`).
- **The witnesses (88 apparatus-only across all 3 languages):** 50 open + 4 Tier 5 local Greek witnesses (including `NA28 (TAGNT)`, `THGNT`, `Rahlfs (1935)`, `OG-Daniel`, `A-Ottley`, `א (01) [CSP-OT]`, `Tregelles`, `Tisch8`, `WH1881`, `Pickering-f35`, `PT1904`, `TCGNT`, `TR*`, 18 CNTR early papyri/uncials, 5 IGNTP Pauline MSS, 13 INTF NTVMR MSS, and `Ξ (040)`); 2 open + 8 Tier 5 local Hebrew witnesses (`BenChayyim`, `Letteris`, `BHS (BHSA)`, `SP (Samaritan)`, and 6 Qumran DSS scroll groups); and 14 open + 10 Tier 5 local Latin witnesses (`Amiatinus NT`, `Hetzenauer`, `Conte`, `Sistina`, `Psalt-Pianum`, `Stuttgart-BSV`, 9 COMPAUL Old Latin Pauline MSS, `VL 5 (d)` Bezae Latin, and 8 *Vetus Latina Iohannes* MSS). See [docs/OPEN-LICENCE-ACQUISITION-PLAN.md](docs/OPEN-LICENCE-ACQUISITION-PLAN.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
- **How they are collated:** each is re-aligned to the numbering anchor like every witness. It is then collated against the adopted text and added to every apparatus unit on the side it supports. Where it differs in substance from a text the voting editions agree on, a new unit records its reading. Spelling, accent and pointing differences go to the disregarded log; in Hebrew a unit is made only when the consonants differ or a word is added or missing. A verse only these editions print is noted with the chapter, not printed.
- **What they never do:** vote, choose a spelling or feed the lexicon. So the edition keeps its basis: Swete's Codex Vaticanus, reasoned eclecticism in the NT (the Byzantine stream keeps its two votes, RP2018 and the TR), MAM's pointing, and the Saints Clementine.

### AI brains (`studio/brains/`)

- `offline_philological` *(default)* — the deterministic engine described above; no network.
- `textual_analysis` — **Textual Analysis Brain** (written by Claude for the Studio; offline). Everything the deterministic engine does, plus the internal-evidence reasoning of a textual critic, written into the apparatus for every unit:
  - *eye-skip* (Greek NT) — an omission explicable by homoeoteleuton, homoeoarcton or haplography between longer words (e.g. the Byzantine omission in 1 John 2:23 between the two "τὸν πατέρα ἔχει") gets no shorter-reading credit, unless B and א both omit; a skip between short words (καί/τό) is noted only; additions repeating adjacent words are dittography;
  - *harmonisation* (Greek NT) — a reading reproducing the wording of another passage is noted with that passage (Matthew 1:25 → Luke 2:7, Mark 1:14 → Matthew 4:23, Colossians 1:14 → Ephesians 1:7), using a word-trigram index of the corpus. Only an addition of real words counts against a reading; for substitutions the note is neutral. Spelling conventions (ἕνεκα/ἕνεκεν, -ατε/-ετε), closing formulae and the same sentence under a neighbouring verse number are never called harmonisations. A verse missing from two or more witnesses that reproduces another passage (Matt 18:11 = Luke 19:10) gets a whole-verse note;
  - *variant types* — omission/addition, transposition, substitution, inflection or spelling (same stem), proper-name spelling, conflation, sacred-name additions (called a "pious expansion" only when B and א lack the name and at least two families omit it), liturgical ἀμήν (neutral after a doxology);
  - *independent evidence* — which text streams (early manuscripts, modern editions, Byzantine; Swete vs Brenton; Aleppo vs Leningrad; Amiatinus vs Clementine) support each reading;
  - *review flags* — a verse is marked ⚑ when the vote is close and internal evidence points the other way, when a whole verse is bracketed, or when the optional Claude review disagrees.
  Neighbouring words that divide the witnesses the same way are presented as one variation unit (an omitted clause is one entry, a word-order change is one transposition).
  **Optional Claude review** (off by default; needs the Offline Lock off, `pip install anthropic` and an Anthropic key or `ant auth login`): sends each contested verse to `claude-opus-5-5` (effort `high`, JSON-schema output, cached system prompt, server-side refusal fallback). Claude can only point at a reading the witnesses attest — it never writes text — and its opinion is recorded beside the deterministic decision; a disagreement flags the verse for review instead of changing it.
- `openai_review` — **OpenAI Review Brain** (added by Codex): runs the Textual Analysis Brain, then asks OpenAI for an advisory review of contested word-level readings. It may choose only a numbered reading with supporting witness sigla, or abstain. It never changes the critical text, calibrated scores, witness admission, or human locks. Disagreements, abstentions, and uncompleted reviews flag the verse for human attention. Whole-verse presence/absence stays with deterministic rules and the editor. Existing optional Claude review can also run when enabled.
  Uses the [Responses API](https://developers.openai.com/api/docs/guides/text) with [strict structured output](https://developers.openai.com/api/docs/guides/structured-outputs), `store: false`, and no third-party Python dependencies. Default model: [`gpt-6-astra`](https://developers.openai.com/api/docs/models/gpt-6-astra), effort `high`; both are configurable. At most 20 units are sent per request. Refusals, truncated output, missing answers, invalid choices, duplicate answers, and invented supporting witnesses remain visible in the rationale/apparatus. Each accepted review includes the returned model, response ID, prompt version, UTC attempt time, and input hash in JSON exports. Model certainty is explicitly subjective and uncalibrated. This evaluates the supplied transcriptions and apparatus; it does not independently inspect manuscript images or fetch additional sources.
- `local_ollama` — a local model at `127.0.0.1` / `localhost` only.
- `cloud_gemini` — Gemini via the Interactions API and `gemini-decision-1` (Decisions API); only when the Strict Offline Lock is off and an API key is set. Untested here (no key configured).

Safeguards for both model brains: a model may make a gatekeeper verdict **stricter** but never admit a witness the deterministic checks rejected; a model's proposed verse text is accepted **only if every word is attested by a witness** (otherwise the deterministic text is kept and the rejection is noted); whole-verse presence/absence is never delegated to a model; failures are written into the rationale instead of being swallowed.

The **Strict Offline Lock** is an application-level guard: while it is on, the cloud brain and Google Drive sync refuse to run. It does not firewall other software.

### Direct review with Codex

For direct review by Codex through an active chat, use **Textual Analysis Brain**, turn **Strict Offline Lock** on, and leave optional cloud review off. Codex can inspect the local sources, operate the desktop app, run the engine, and make evidence-backed fixes through the workspace. This workflow does not use the Studio's OpenAI API connection. Codex's direct reviews take place in the chat; selecting the offline brain does not start an unattended Codex reviewer inside Studio.

### Enable OpenAI review

1. Restart the desktop app after updating it. Choose **OpenAI Review Brain** in the top **AI Brain** selector.
2. In **Settings**, enter an OpenAI API key, or leave the field blank to use `OPENAI_API_KEY` from the app's environment. Save Brain Configuration. Like the existing provider keys, a key entered here is stored locally in the Git-ignored `data/.local_secrets.json`; it is not encrypted.
3. Turn **Strict Offline Lock** off when ready to send witness text to OpenAI. API usage may incur charges. Re-collate a chapter in the Workbench to generate its reviews; selecting a brain alone does not review previously saved chapters.
4. Inspect **OpenAI review** findings in the apparatus and review flags. Adopt a variant or lock a verse only after your own editorial decision.

For one CLI run, with `OPENAI_API_KEY` already set:

```powershell
python cli.py collate --lang greek --book matthew --chapters 1 --brain openai_review --allow-network
```

`--allow-network` unlocks this run only and does not save a changed Offline Lock setting. Without credentials or with the lock on, collation still works and records why OpenAI did not review the disputed units. The reviewer runs on requested collations; it is not a background service.

**OpenAI connection errors:** the reviewer distinguishes exhausted credits (`credit_balance_exhausted`), organization/project spend or usage limits, and temporary request/token rate limits. It shows a safe explanation and records the HTTP status and recognized error code in review findings; raw API error bodies and credentials are never displayed. Billing, access, and HTTP 429 failures stop the remaining review batches in that chapter, marking unsent batches explicitly while preserving earlier successful reviews.

For exhausted credits, restore the balance for the organization that owns the saved key in [API Billing](https://platform.openai.com/settings/organization/billing/). Eligible Pro/Business subscriptions may offer an [API credit benefit that must be activated](https://help.openai.com/en/articles/20001626-api-credits-benefit-for-eligible-chatgpt-subscriptions). For spend/usage limits, inspect the named organization's or project's controls; retries do not restore credits or raise limits. See [OpenAI's troubleshooting guide](https://help.openai.com/en/articles/6614457-troubleshooting-api-usage-and-spend-limits). After resolving the account issue, restart Studio to load updated code and re-collate the chapter to request fresh reviews.

### Saints Concordance & English-Friendly Transliteration (`studio/concordance*.py`, `studio/translit.py`)

- **Trilingual Concordance (Tab 5):** Indexes **99.83%** of all `1,564,800` original-language tokens across Hebrew/Aramaic (`100.0%`), Greek (`99.95%`), and Latin (`99.61%`) under Saints.Bible verse numbers, using strictly open-licence tagged editions, Lewis & Short, GLAUx Septuagint parses (`CC BY-SA 4.0`), and parallel-verse Latin disambiguation (`studio/lexica/latin_parallel.py`).
- **Latinized Transliteration (Tabs 1, 2 & 5):** Optional English-friendly Latinized transliteration for polytonic Greek and pointed Hebrew/Aramaic (`studio/translit.py`) with toggleable interlinear reading in the Edition Home and Workbench, plus transliterated roots, lemmas, and aligned occurrences in the Saints Concordance and exported pack.

---

## Quick start

```powershell
python app.py                      # desktop app (or double-click Launch-Saints-Critical-Text-Studio.vbs)
python cli.py library              # list saved Saints Critical Text chapters inside the Studio home
python cli.py status               # list witnesses and gatekeeper statuses
python cli.py collate --lang greek --book matthew --chapters 1-5
python cli.py collate --lang hebrew --book genesis --chapters all
python cli.py gatekeep --lang greek --siglum "P46" --title "Chester Beatty Pauline Papyrus" --scope NT --license "CC BY-SA 4.0" --file path\to\p46.txt
python cli.py concordance stats    # measured coverage, lemma/root counts and pack size
python cli.py concordance seed     # rebuild the whole concordance from the tagged editions (same as index without --book)
python cli.py concordance index    # tag saved chapters with lemmas/roots, filed under Saints.Bible verse numbers (--book genesis)
python cli.py concordance search --query ἀρχή --lang grc   # search lemmas, roots, glosses, Strong's numbers
python cli.py concordance export   # Saints-Concordance-Pack/: one .json.gz per language + hubs + decoder + manifest + report
python -m unittest discover -s tests -v
```

Python 3.11+ and the standard library only (`pymupdf` optional for PDF witnesses, `google-genai` optional for the cloud brain, `anthropic` optional for the Claude review).

### Self-Contained Paths

Everything the Studio needs lives inside `Saints-Critical-Text-Studio/` so the folder can be used offline or moved as a unit:
- `Saints-Greek-Critical-Text/` — Greek Critical Text chapter folders (`01_Law` … `07_Glory`) alongside Greek witness tier folders (`01_Tier1_Modern_Critical_Open` …).
- `Saints-Hebrew-Critical-Text/` — Hebrew Critical Text chapter folders alongside Hebrew witness folders (`hebrew-base`, `01_Tier1_Modern_Critical_Open`, …).
- `Saints-Latin-Critical-Text/` — Latin Critical Text chapter folders alongside Latin witness folders (`latin-base`, `saints-latin-column`, `01_Tier1_Open_Vulgate_Base_Texts`, …).
- `data/` — `studio.db`, settings, lexicon cache, backups, and user-uploaded witnesses.

Override with environment variables (used by the test suite so tests never touch real data):

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `CTS_REPO_ROOT` | `<Studio>` (`Saints-Critical-Text-Studio`) | where `Saints-{Greek,Hebrew,Latin}-Critical-Text` research corpora live |
| `CTS_OUTPUT_ROOT` | `<Studio>` (`Saints-Critical-Text-Studio`) | where `Saints-{Greek,Hebrew,Latin}-Critical-Text` chapter editions are written |
| `CTS_DATA_DIR` | `<Studio>/data` | `studio.db`, settings, API key, lexicon cache, user witnesses |

The test suite sets `CTS_OUTPUT_ROOT` and `CTS_DATA_DIR` to a temporary folder, so running it never touches your real database or critical-text folders.

---

## Versification

- **Greek:** Septuagint numbering as in Brenton/eBible (the Saints.Bible numbering) for the OT; standard NT numbering (anchor: SBLGNT).
- **Hebrew:** Masoretic numbering. Psalms 10–147 therefore carry MT numbers, one higher than the Greek and Latin files for the same psalm.
- **Latin:** Saints.Bible numbering (anchor: the Saints Latin column). The Clementine USFX is re-aligned to it by content. Where the Saints column pads a verse number with a copy of another verse (same card id: Gen 5:32 = 5:31, 49:32 = 49:30, 50:23 = 50:22), the copy is ignored; the Vulgate has no separate verse there, so that number is absent from the Latin critical text rather than printed twice.
- **Proverbs:** numbered as Saints.Bible numbers it, with Hebrew chapter and verse numbers in the Greek order (24:1–22e, 30:1–14, 24:23–34, 30:15–33, 31:1–9, chapters 25–29, 31:10–31). The Brenton e-text runs 30:1–31:9 on as 24:22–62, with 30:1–14 inside one long 24:22. `source_repairs.py` cuts that verse where each verse of 30:1–14 opens and renumbers 24:35–62 as 30:15–33 and 31:1–9; the Swete copies (24:24–77, 29:28–49) are re-aligned by content.
- **Sirach:** chapters 30–36 stand in a different order in Swete and in Brenton, so Sirach verses are re-aligned from up to six chapters away (one chapter elsewhere). The Swete transcription already prints them in Brenton's order; First1KGreek keeps Swete's.
- **Swete transcription:** numbered like Brenton almost everywhere (Swete's suffixed verses such as 3 Kgdms 2:35a–o and Esther's Additions are folded into their verse, as Brenton's `\v 35a` is; Wisdom 16–19, which First1KGreek numbers 17–20, are numbered like Brenton). Joel, Malachi and Proverbs 24–31 are re-aligned by content like the other Swete copies. Verses it leaves empty (Swete prints the number without text, e.g. 1 Sam 17:12–31, Jer 10:6–8, which B lacks) cast no vote, like the silence of the other copies.

---

## Repository layout

```text
Saints-Critical-Text-Studio/
├── app.py                          # Tk desktop GUI (1 · Edition Home, 2 · Workbench, 3 · Gatekeeper, 4 · Settings, 5 · Saints Concordance)
├── cli.py                          # headless CLI (status, library, reexport, collate, gatekeep, concordance)
├── LICENSE                         # MIT License (Studio application & tooling code)
├── LICENSES/GPL-3.0.txt            # GNU GPL-3.0 (Greek OT & GPL-3.0-compatible apparatus files)
├── THIRD_PARTY_NOTICES.md          # Complete per-component licence & upstream attribution ledger
├── gemini-code-1795017603985.sql   # SQL v2.0 sketch of the Concordance schema (reference only; the Python DDL is canonical)
├── Launch-Saints-Critical-Text-Studio.vbs
├── Saints-Concordance-Pack/        # exported website pack (per-language .json.gz, lexica, hubs, JS decoder, manifest, report)
├── Saints-Greek-Critical-Text/     # Priority 1 Greek Critical Text (70 books, 1,291 chapters; raw corpora git-ignored)
├── Saints-Hebrew-Critical-Text/    # Priority 2 Hebrew Critical Text (39 books, 929 chapters; raw corpora git-ignored)
├── Saints-Latin-Critical-Text/     # Priority 3 Latin Critical Text (70 books, 1,290 chapters; raw corpora git-ignored)
├── studio/
│   ├── catalog.py          # 70-book canon, paths, versification anchors, edition families
│   ├── translit.py         # English-friendly Latinized transliteration for polytonic Greek and pointed Hebrew/Aramaic
│   ├── concordance*.py     # Concordance schema, gold builder, alignment, site export, LEB128 delta-varint postings
│   ├── lexica/             # hebrew.py (OSHB+BDB), greek.py (TAGNT, LXX), glaux.py, latin.py (L&S), latin_parallel.py, versification.py
│   ├── db.py               # SQLite store and built-in witness catalogue (refreshed on upgrade; human overrides kept)
│   ├── parsers.py          # witness readers (Swete Clean, Swete CSV transcription, First1K TEI, USFM, CNTR, SBLGNT, Nestle, RP, WLC, MAM, USFX, Saints JSON, Amiatinus TEI, uploads)
│   ├── collator.py         # word alignment, comparison keys, orthographic rules, verse re-alignment
│   ├── lexicon.py          # corpus word frequencies for the Greek OCR safeguard
│   ├── engine.py           # orchestration: load → re-align → collate → adjudicate → persist → export
│   ├── exporter.py         # Markdown / JSON / TSV (+ optional gdrive CLI sync)
│   └── brains/             # offline, local-LLM and cloud adjudicators
└── tests/
    ├── test_studio.py      # offline unit and corpus regression tests (sandboxed)
    ├── test_translit.py    # Greek & Hebrew/Aramaic transliteration tests
    ├── test_concordance*.py# Concordance accuracy, alignment, site export & licence hygiene tests (sandboxed)
    └── test_lexica_*.py    # Hebrew, Greek, GLAUx, Latin, Latin-parallel and versification tagger tests
```
