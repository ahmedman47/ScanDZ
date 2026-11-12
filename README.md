# Wathiqa (وثيقة)

**Bilingual (Arabic/French) business-document intelligence.** Turn scanned or photographed
invoices into trustworthy structured data: OCR, schema-constrained LLM extraction, deterministic
validation, human review, and search. Local-first, built entirely with free tools.

> **Status: work in progress (week 1 of 6).** The core logic is implemented and tested.
> The OCR pipeline, API, and review UI are being built. No accuracy results have been measured yet.

## The problem

Many small and medium businesses in Algeria still process invoices on paper or as phone photos,
and enter the data by hand. The documents mix Arabic and French, use Arabic-Indic or Western digits,
local identifiers (NIF, NIS, RC, AI), local month names, and amounts such as `1 234,56 DA`.
General-purpose OCR and extraction tools are often not tuned for this mix, and a silently wrong
total is worse than no automation at all.

## Approach

1. **Preprocess** the image (deskew, denoise, binarize).
2. **OCR** with Tesseract (`ara+fra`), with other engines compared in experiments.
3. **Extract** fields with a local LLM constrained to a JSON schema.
4. **Ground** every extracted value against the OCR text (anti-hallucination).
5. **Normalize** digits, dates, and amounts in code (the model copies, code converts).
6. **Validate** with business rules (sums, VAT, identifiers, dates).
7. **Decide**: auto-accept confident documents, send the rest to human review.
8. **Store** approved data in PostgreSQL (with pgvector) and answer questions with evidence.

Key design ideas: the model proposes and code disposes; doubt means human review; every model
attempt and every human edit is stored as an audit trail; SQL written by a model is guarded by a
parser allow-list, a read-only database role, and a statement timeout.

## What exists today

| Area | State |
|---|---|
| Data contract, normalization (Arabic/French digits, dates, amounts) | Done, tested |
| Business-rule validation and review decision | Done, tested |
| LLM client with egress guard, schema output, grounding check | Done, tested |
| PostgreSQL schema, job queue, hybrid search SQL, read-only role | Done, tested |
| SQL guard for model-written queries | Done, tested |
| Evaluation metrics (CER, field F1, bootstrap confidence intervals) | Done, tested |
| Synthetic invoice generator | In progress |
| OCR pipeline, API, worker, review UI | Planned |
| Evaluation on a hand-labeled test set | Planned |

## Data rule

Only **public and synthetic** documents are used. No client or employer documents are used, and
no real identifiers appear in this repository. Public datasets are downloaded by script and are
never redistributed here.

## Quick start

Requires Python 3.12 or newer.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev,db]"
pytest
```

On Linux or macOS, activate with `source .venv/bin/activate` instead.

The database tests start an embedded PostgreSQL through the `pixeltable-pgserver` package.
If they show as skipped, that package could not be installed on your platform.

## Project structure

```
src/wathiqa/
  domain/     data contract, normalization, validation (pure code, no I/O)
  adapters/   model clients and other I/O
  query/      question router and SQL guard
  rag/        chunking for retrieval
  db/         schema, roles, and SQL queries
  eval/       evaluation metrics
tests/        unit, property-based, and database integration tests
docs/adr/     architecture decision records
```

## Roadmap

1. Foundations and synthetic data
2. OCR baseline and first measured result
3. LLM extraction, validation, and ablations
4. API, worker, and review UI
5. Search, question answering, and security work
6. Evaluation on a real-style test set, documentation, demo

## Limitations

- Country-specific rule defaults (VAT rates, identifier lengths) must be verified against current
  official sources before being relied on.
- The system assists data entry. It does not replace an accountant's judgment or tax compliance.
- Single-tenant by design for the first version.

## License

MIT. See [LICENSE](LICENSE).