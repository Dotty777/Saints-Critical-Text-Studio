# Saints Concordance — build report

Every number below is measured from the database and the files just written.

## Coverage of the critical texts

| Language | Tokens | Indexed (all tagged) | Content words | Function words | Parsed (morph) | Untagged | Extra-site verses (studio.db) | Skipped dup/placeholder tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hebrew | 305,474 | 305,453 (100.0%) | 233,387 | 72,066 | 305,145 | 21 | 261 | 0 |
| greek | 669,598 | 669,309 (100.0%) | 393,024 | 276,285 | 639,315 | 198 | 31 | 91 |
| latin | 596,875 | 594,652 (99.6%) | 335,904 | 258,748 | 594,652 | 2,211 | 433 | 12 |

All tagged tokens (content and function words) across every non-duplicate verse are indexed in `studio.db` with their morphological parses; non-duplicate MT / TR / Theodotion / Vulgate verses absent from Saints.Bible are stored under dedicated extra-site anchors (`subverse = 9`, marked `*`), while confirmed duplicate and placeholder rows are skipped so no word is counted twice. The downloadable website packs below carry live Saints.Bible (`subverse = 0`) content-word postings only so every published link resolves on the site.

## Pack files (content-word postings)

| File | Lemmas | Roots | Surface forms | Lemma-verse pairs | Raw JSON | Gzip | Same postings keyed by surface form (gzip) |
|---|---:|---:|---:|---:|---:|---:|---:|
| saints-concordance-heb.json.gz | 9,033 | 5,564 | 105,458 | 208,028 | 1,900,160 | 805,948 | 1,132,056 |
| saints-concordance-grc.json.gz | 13,836 | 10,125 | 55,449 | 353,666 | 3,395,511 | 1,399,612 | 1,203,923 |
| saints-concordance-lat.json.gz | 10,953 | 6,247 | 48,633 | 311,392 | 2,900,916 | 1,250,504 | 1,144,155 |
| saints-concordance-hubs.json.gz | 7 hubs | | | | 22,679 | 14,614 | |

Colour-hub occurrences for review (saints-concordance-hub-occurrences.csv, not the word-studies import format): 6,097 rows

Licences: heb CC BY 4.0; grc CC BY-SA 4.0; lat CC BY-SA 4.0; hubs CC BY 4.0; decoder MIT (Saints.Bible code); heb-lex CC BY 4.0; grc-lex CC BY-SA 4.0; lat-lex CC BY-SA 4.0. Sources, links and the note of changes are listed in manifest.json.

Colour-hub senses: a unit gets a specific sense only when one of its words decides it (e.g. ἄνεμος/ventus 'wind', κεφαλή 'head'); otherwise it carries the hub's 'sense not yet chosen' row (offset 64) until a person sets it in Tab 5.
