# Template split (frozen)

Decided on: YYYY-MM-DD (fill in today). Changing this file after the first test run invalidates all test results.
Version 2 replaces version 1 (one held-out layout) before any test result existed.

| Split | Templates | Languages | Use |
|---|---|---|---|
| Development (8) | `fr`, `compact`, `ticket`, `banner`, `dense`, `bilingual`, `ar`, `en` | French, Arabic, bilingual, English | Prompt writing, regex rules, thresholds, error analysis. You may look at every document. |
| Test (4) | `modern`, `sidebar`, `stamp`, `ar_modern` | French (2), bilingual, Arabic | Final numbers only. |

Defined in code: `DEV_TEMPLATES` and `TEST_TEMPLATES` in `src/wathiqa/synth/generate.py`. Unit tests check that the sets are disjoint, cover all 12 layouts, and that the test layouts include French, Arabic and bilingual documents.

## Rules

1. The test templates are never used to tune prompts, regexes, preprocessing or thresholds.
2. Generate test data only with `--split test`, into `data/synthetic/test`. Do not open those images during development, except for the final error analysis.
3. The split is by **layout**, not by file. Near-identical documents on both sides inflate scores.
4. English has one layout and it is in development, so English is not covered by the synthetic test set. Say this in the report.
5. Business domains (IT, office, construction, food, medical, services) are shared by both splits. The split tests new layouts, not new vocabulary.
6. The hand-labeled real-style set (week 5) is a separate test set, frozen and hashed before the final threshold is chosen.

## What each held-out layout tests

- `modern`: borderless table, seller block on the right, totals on the left.
- `sidebar`: party details in a left column, table in a narrower right column.
- `stamp`: bilingual labels and a round stamp near the totals.
- `ar_modern`: Arabic-only, colored banner with the seller details in a different place from `ar`.

## Change log

- v1: `modern` only held out.
- v2: four held-out layouts covering French, Arabic and bilingual.
