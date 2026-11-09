from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from wathiqa.domain.normalize import (
    build_or_tsquery,
    digits_only,
    normalize_arabic,
    normalize_text,
    parse_amount,
    parse_date,
    parse_percent,
    squash,
    to_western_digits,
)

D = Decimal


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1 234,56 DA", D("1234.56")),
        ("1.234,56", D("1234.56")),
        ("1,234.56", D("1234.56")),
        ("1 234 567,89", D("1234567.89")),
        ("1 234,56", D("1234.56")),  # no-break space
        ("1 234,56", D("1234.56")),  # narrow no-break space
        ("٣٤٥٫٥٠", D("345.50")),  # Arabic-Indic digits and decimal separator
        ("١٢٣٤", D("1234")),
        ("12 500", D("12500")),
        ("12,500", D("12500")),  # single separator + 3 digits = thousands
        ("12.5", D("12.5")),
        ("0,500", D("0.500")),
        ("(150,00)", D("-150.00")),
        ("-75,25 DZD", D("-75.25")),
        ("Total TTC : 11 900,00 DA", D("11900.00")),
        ("1234", D("1234")),
        ("10 000,00 دج", D("10000.00")),
        ("5000 دينار جزائري", D("5000")),
    ],
)
def test_parse_amount(text: str, expected: Decimal) -> None:
    assert parse_amount(text) == expected


@pytest.mark.parametrize("text", [None, "", "abc", "DA", "N/A"])
def test_parse_amount_none(text: str | None) -> None:
    assert parse_amount(text) is None


@given(st.decimals(min_value=0, max_value=10**9, places=2))
def test_amount_roundtrip_in_three_styles(value: Decimal) -> None:
    whole, frac = f"{value:.2f}".split(".")
    groups = f"{int(whole):,}"
    styles = [
        f"{groups.replace(',', ' ')},{frac}",  # 1 234,56
        f"{groups.replace(',', '.')},{frac}",  # 1.234,56
        f"{groups}.{frac}",  # 1,234.56
    ]
    for text in styles:
        assert parse_amount(text) == value, text


@pytest.mark.parametrize(
    ("text", "expected"),
    [("TVA 19%", D("19")), ("9,00", D("9.00")), ("19 %", D("19")), ("١٩٪", D("19"))],
)
def test_parse_percent(text: str, expected: Decimal) -> None:
    assert parse_percent(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("12/01/2026", date(2026, 1, 12)),
        ("12-01-26", date(2026, 1, 12)),
        ("12.01.2026", date(2026, 1, 12)),
        ("2026-01-12", date(2026, 1, 12)),
        ("2026/01/12", date(2026, 1, 12)),
        ("12 janvier 2026", date(2026, 1, 12)),
        ("1er mars 2026", date(2026, 3, 1)),
        ("12 janv. 2026", date(2026, 1, 12)),
        ("5 Sept 2025", date(2025, 9, 5)),
        ("12 Dec 2025", date(2025, 12, 12)),
        ("3 février 2024", date(2024, 2, 3)),
        ("15 août 2025", date(2025, 8, 15)),
        ("١٢ جانفي ٢٠٢٦", date(2026, 1, 12)),
        ("12 جانفي 2026", date(2026, 1, 12)),
        ("5 أوت 2025", date(2025, 8, 5)),
        ("٢٠٢٦/٠١/١٢", date(2026, 1, 12)),
        ("Date : 12/01/2026 à Alger", date(2026, 1, 12)),
    ],
)
def test_parse_date(text: str, expected: date) -> None:
    assert parse_date(text) == expected


@pytest.mark.parametrize(
    "text", [None, "", "31/02/2026", "13/13/2026", "yesterday", "12 jui 2026", "2026"]
)
def test_parse_date_rejects(text: str | None) -> None:
    assert parse_date(text) is None


def test_day_first_never_guessed_as_month_first() -> None:
    assert parse_date("03/04/2026") == date(2026, 4, 3)


def test_normalize_text_french() -> None:
    assert normalize_text("Société  ÉTOILE, S.A.R.L") == "societe etoile s a r l"


def test_normalize_text_arabic_variants_collapse() -> None:
    assert normalize_text("أحمد") == normalize_text("احمد")
    assert normalize_text("مدرسة") == normalize_text("مدرسه")
    assert normalize_text("مُحَمَّد") == normalize_text("محمد")
    assert normalize_text("فاتورة ٢٠٢٦") == "فاتوره 2026"


def test_normalize_arabic_handles_presentation_forms_and_tatweel() -> None:
    assert normalize_arabic("ﻓﺎﺗﻮﺭﺓ") == normalize_arabic("فاتورة")
    assert normalize_arabic("الــجزائر") == "الجزائر"


def test_squash_and_digits() -> None:
    assert squash("FA-2026/0012") == "fa20260012"
    assert digits_only("NIF : ٠٠٢٠١٦٠٠١٢٣٤٥٦٧") == "002016001234567"
    assert to_western_digits("٠١٢٣٤٥٦٧٨٩") == "0123456789"


def test_or_tsquery() -> None:
    assert build_or_tsquery("combien payé à Sonelgaz ?") == "combien | paye | sonelgaz"
    assert build_or_tsquery("   ") == ""


@given(st.text(max_size=80))
def test_normalize_is_idempotent(text: str) -> None:
    once = normalize_text(text)
    assert normalize_text(once) == once
