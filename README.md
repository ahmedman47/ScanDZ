# Wathiqa reference code

Tested core of the Wathiqa document-intelligence system (see the playbook PDF).

    python -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev,db]"
    pytest -q                      # 186 tests; DB tests need pixeltable-pgserver (dev extra)
    ruff check src tests && mypy src

Tested with Python 3.13 and PostgreSQL 18.4 + pgvector 0.8.5. The design targets Python 3.12+
and PostgreSQL 16+ with pgvector 0.7+; run the suite on your own versions first.
Country-specific rule defaults (VAT rates, identifier lengths) must be verified against
current official sources before you rely on them.
