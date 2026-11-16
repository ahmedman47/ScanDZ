# Template split (frozen)

Decided on: YYYY-MM-DD (fill in today). Changing this file after the first test run invalidates all test results.

| Split | Templates | Use |
|---|---|---|
| Development | `fr`, `bilingual`, `compact` | Prompt writing, regex rules, thresholds, error analysis. You may look at every document. |
| Test | `modern` | Final numbers only. |

Defined in code: `DEV_TEMPLATES` and `TEST_TEMPLATES` in `src/wathiqa/synth/generate.py`. A unit test checks that the two sets are disjoint and cover all templates.

## Rules

1. The test templates are never used to tune prompts, regexes, preprocessing or thresholds.
2. Generate test data only with `--split test`, into `data/synthetic/test`. Do not open those images during development, except for the final error analysis.
3. The split is by **template**, not by file, because near-identical documents on both sides inflate scores.
4. When templates are added (target 8 to 12), roughly one in four goes to test. Add them to this file the day they are created, before generating any data from them.
5. The hand-labeled real-style set (week 5) is a separate test set. It is frozen and hashed before the final threshold is chosen.

## Why `modern` is a useful held-out layout

Borderless table, seller block on the right, totals on the left, different font. It differs from the development layouts in exactly the ways that break position-based rules.

## Change log

- v1: initial split.
