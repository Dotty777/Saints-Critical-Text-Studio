# Saints Concordance — build report

Every number below is measured from the database and the files just written.

## Coverage of the critical texts

| Language | Tokens | Indexed (all tagged) | Content words | Function words | Parsed (morph) | Untagged | Extra-site verses (studio.db) | Skipped dup/placeholder tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hebrew | 20,613 | 20,613 (100.0%) | 15,279 | 5,334 | 20,608 | 0 | 0 | 0 |
| greek | 32,634 | 32,633 (100.0%) | 18,511 | 14,122 | 30,801 | 1 | 0 | 0 |
| latin | 25,251 | 25,166 (99.7%) | 14,739 | 10,427 | 25,166 | 85 | 0 | 0 |

All tagged tokens (content and function words) across every non-duplicate verse are indexed in `studio.db` with their morphological parses; non-duplicate MT / TR / Theodotion / Vulgate verses absent from Saints.Bible are stored under dedicated extra-site anchors (`subverse = 9`, marked `*`), while confirmed duplicate and placeholder rows are skipped so no word is counted twice. The downloadable website packs below carry live Saints.Bible (`subverse = 0`) content-word postings only so every published link resolves on the site.

## Pack files (content-word postings)

| File | Lemmas | Roots | Surface forms | Lemma-verse pairs | Raw JSON | Gzip | Same postings keyed by surface form (gzip) |
|---|---:|---:|---:|---:|---:|---:|---:|
| saints-concordance-heb.json.gz | 9,173 | 5,661 | 105,464 | 208,028 | 1,917,158 | 810,294 | 1,133,599 |
| saints-concordance-grc.json.gz | 13,951 | 10,231 | 55,467 | 353,701 | 3,410,718 | 1,404,571 | 1,204,263 |
| saints-concordance-lat.json.gz | 11,110 | 6,349 | 48,454 | 309,358 | 2,901,543 | 1,247,213 | 1,136,857 |
| saints-concordance-hubs.json.gz | 7 hubs | | | | 22,595 | 14,541 | |

Colour-hub occurrences for review (saints-concordance-hub-occurrences.csv, not the word-studies import format): 6,068 rows

Licences: heb CC BY 4.0; grc CC BY-SA 4.0; lat CC BY-SA 4.0; hubs CC BY 4.0; decoder MIT (Saints.Bible code); heb-lex CC BY 4.0; grc-lex CC BY-SA 4.0; lat-lex CC BY-SA 4.0. Sources, links and the note of changes are listed in manifest.json.

Colour-hub senses: a unit gets a specific sense only when one of its words decides it (e.g. ἄνεμος/ventus 'wind', κεφαλή 'head'); otherwise it carries the hub's 'sense not yet chosen' row (offset 64) until a person sets it in Tab 5.
