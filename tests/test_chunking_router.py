from datetime import date
from decimal import Decimal
from itertools import pairwise

import pytest
from hypothesis import given
from hypothesis import strategies as st

from wathiqa.domain.contract import Invoice, LineItem, Party
from wathiqa.query.router import route_question
from wathiqa.rag.chunking import chunk_text, verbalize

TEXT = "\n".join(f"ligne {i:03d} " + "x" * 30 for i in range(60))


def test_chunks_respect_the_size_limit_and_overlap() -> None:
    chunks = chunk_text(TEXT, max_chars=200, overlap=50)
    assert len(chunks) > 5
    assert all(len(c) <= 200 for c in chunks)
    for left, right in pairwise(chunks):
        assert set(left.splitlines()) & set(right.splitlines()), "neighbouring chunks must overlap"


def test_no_content_is_lost() -> None:
    chunks = chunk_text(TEXT, max_chars=200, overlap=50)
    covered = {line for c in chunks for line in c.splitlines()}
    assert covered == set(TEXT.splitlines())


def test_very_long_line_is_hard_split() -> None:
    chunks = chunk_text("a" * 1000, max_chars=300, overlap=0)
    assert [len(c) for c in chunks] == [300, 300, 300, 100]


def test_bad_parameters() -> None:
    with pytest.raises(ValueError):
        chunk_text("x", max_chars=100, overlap=100)


@given(st.text(alphabet="abc \n", max_size=400), st.integers(20, 120))
def test_chunk_invariants(text: str, max_chars: int) -> None:
    chunks = chunk_text(text, max_chars=max_chars, overlap=max_chars // 4)
    assert all(len(c) <= max_chars for c in chunks)
    assert {ln.strip() for ln in text.splitlines() if ln.strip()} <= {
        part for c in chunks for part in c.splitlines()
    } | {c for c in chunks}  # every non-empty line is preserved, or lives inside a hard split


def test_verbalize_contains_the_searchable_facts() -> None:
    inv = Invoice(
        invoice_number="FA-12",
        issue_date=date(2026, 3, 5),
        seller=Party(name="Sonelgaz"),
        total_ttc=Decimal("11900.00"),
        currency="DZD",
        lines=[
            LineItem(
                description="Gaz",
                quantity=Decimal(1),
                unit_price_ht=Decimal(10000),
                total_ht=Decimal(10000),
            )
        ],
    )
    text = verbalize(inv)
    for needle in ("FA-12", "2026-03-05", "Sonelgaz", "11900.00", "Gaz"):
        assert needle in text


@pytest.mark.parametrize(
    ("question", "kind", "tool"),
    [
        ("Combien j'ai payé en mars ?", "analytics", "spend_by_month"),
        ("dépenses par mois", "analytics", "spend_by_month"),
        ("Top 5 fournisseurs", "analytics", "top_suppliers"),
        ("total par fournisseur", "analytics", "spend_by_supplier"),
        ("How much did I spend with each supplier?", "analytics", "spend_by_supplier"),
        ("كم دفعت للمورد", "analytics", "spend_by_supplier"),
        ("Quelle est la date limite de paiement de la facture FA-12 ?", "document_qa", None),
        ("Who signed invoice FA-12?", "document_qa", None),
        (
            "I assume the stop sign is red",
            "document_qa",
            None,
        ),  # "sum" in "assume", "top" in "stop"
    ],
)
def test_router(question: str, kind: str, tool: str | None) -> None:
    route = route_question(question)
    assert (route.kind, route.tool) == (kind, tool)
