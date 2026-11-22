# Saints Concordance — build report

Every number below is measured from the database and the files just written.

## Coverage of the critical texts

| Language | Tokens | Indexed (all tagged) | Content words | Function words | Parsed (morph) | Untagged | Extra-site verses (studio.db) | Skipped dup/placeholder tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hebrew | 16,408 | 16,407 (100.0%) | 12,870 | 3,537 | 16,399 | 1 | 0 | 0 |
| greek | 25,008 | 24,988 (99.9%) | 15,459 | 9,529 | 23,431 | 1 | 0 | 19 |
| latin | 19,420 | 19,351 (99.6%) | 11,944 | 7,407 | 19,351 | 57 | 0 | 10 |

All tagged tokens (content and function words) across every non-duplicate verse are indexed in `studio.db` with their morphological parses; non-duplicate MT / TR / Theodotion / Vulgate verses absent from Saints.Bible are stored under dedicated extra-site anchors (`subverse = 9`, marked `*`), while confirmed duplicate and placeholder rows are skipped so no word is counted twice. The downloadable website packs below carry live Saints.Bible (`subverse = 0`) content-word postings only so every published link resolves on the site.

## Pack files (content-word postings)

| File | Lemmas | Roots | Surface forms | Lemma-verse pairs | Raw JSON | Gzip | Same postings keyed by surface form (gzip) |
|---|---:|---:|---:|---:|---:|---:|---:|
| saints-concordance-heb.json.gz | 9,173 | 5,661 | 105,464 | 208,028 | 1,917,150 | 810,293 | 1,133,896 |
| saints-concordance-grc.json.gz | 13,951 | 10,231 | 55,467 | 353,701 | 3,411,099 | 1,404,682 | 1,204,316 |
| saints-concordance-lat.json.gz | 11,110 | 6,349 | 48,454 | 309,355 | 2,901,520 | 1,247,185 | 1,136,909 |
| saints-concordance-hubs.json.gz | 7 hubs | | | | 22,595 | 14,541 | |

Colour-hub occurrences for review (saints-concordance-hub-occurrences.csv, not the word-studies import format): 6,068 rows

Licences: heb CC BY 4.0; grc CC BY-SA 4.0; lat CC BY-SA 4.0; hubs CC BY 4.0; decoder MIT (Saints.Bible code); heb-lex CC BY 4.0; grc-lex CC BY-SA 4.0; lat-lex CC BY-SA 4.0. Sources, links and the note of changes are listed in manifest.json.

Colour-hub senses: a unit gets a specific sense only when one of its words decides it (e.g. ἄνεμος/ventus 'wind', κεφαλή 'head'); otherwise it carries the hub's 'sense not yet chosen' row (offset 64) until a person sets it in Tab 5.
