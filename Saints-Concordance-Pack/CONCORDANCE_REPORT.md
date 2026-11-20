# Saints Concordance — build report

Every number below is measured from the database and the files just written.

## Coverage of the critical texts

| Language | Tokens | Indexed (all tagged) | Content words | Function words | Parsed (morph) | Untagged | Extra-site verses (studio.db) | Skipped dup/placeholder tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hebrew | 305,476 | 305,454 (100.0%) | 233,388 | 72,066 | 305,144 | 22 | 264 | 0 |
| greek | 669,756 | 669,389 (99.9%) | 393,069 | 276,320 | 639,225 | 208 | 31 | 159 |
| latin | 589,568 | 587,294 (99.6%) | 331,723 | 255,571 | 587,294 | 2,209 | 259 | 65 |

All tagged tokens (content and function words) across every non-duplicate verse are indexed in `studio.db` with their morphological parses; non-duplicate MT / TR / Theodotion / Vulgate verses absent from Saints.Bible are stored under dedicated extra-site anchors (`subverse = 9`, marked `*`), while confirmed duplicate and placeholder rows are skipped so no word is counted twice. The downloadable website packs below carry live Saints.Bible (`subverse = 0`) content-word postings only so every published link resolves on the site.

## Pack files (content-word postings)

| File | Lemmas | Roots | Surface forms | Lemma-verse pairs | Raw JSON | Gzip | Same postings keyed by surface form (gzip) |
|---|---:|---:|---:|---:|---:|---:|---:|
| saints-concordance-heb.json.gz | 9,033 | 5,564 | 105,456 | 208,018 | 1,900,137 | 806,013 | 1,132,065 |
| saints-concordance-grc.json.gz | 13,832 | 10,121 | 55,473 | 353,699 | 3,394,952 | 1,399,548 | 1,204,020 |
| saints-concordance-lat.json.gz | 10,964 | 6,268 | 48,481 | 309,336 | 2,886,153 | 1,242,975 | 1,136,594 |
| saints-concordance-hubs.json.gz | 7 hubs | | | | 22,595 | 14,543 | |

Colour-hub occurrences for review (saints-concordance-hub-occurrences.csv, not the word-studies import format): 6,068 rows

Licences: heb CC BY 4.0; grc CC BY-SA 4.0; lat CC BY-SA 4.0; hubs CC BY 4.0; decoder MIT (Saints.Bible code); heb-lex CC BY 4.0; grc-lex CC BY-SA 4.0; lat-lex CC BY-SA 4.0. Sources, links and the note of changes are listed in manifest.json.

Colour-hub senses: a unit gets a specific sense only when one of its words decides it (e.g. ἄνεμος/ventus 'wind', κεφαλή 'head'); otherwise it carries the hub's 'sense not yet chosen' row (offset 64) until a person sets it in Tab 5.
