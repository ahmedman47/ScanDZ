import json
import random
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from wathiqa.domain.normalize import parse_amount, parse_date
from wathiqa.domain.validate import RuleConfig, validate
from wathiqa.synth.cli import generate
from wathiqa.synth.formatting import format_amount, format_date
from wathiqa.synth.generate import (
    DATE_STYLES,
    ERROR_KINDS,
    NUMBER_STYLES,
    TEMPLATES,
    Style,
    inject_error,
    make_invoice,
    random_style,
)
from wathiqa.synth.render import render_html

CFG = RuleConfig(today=date(2026, 11, 1))


@given(st.decimals(min_value=0, max_value=10**9, places=2), st.sampled_from(NUMBER_STYLES))
def test_printed_amounts_parse_back_exactly(value: Decimal, style: str) -> None:
    assert parse_amount(format_amount(value, style, unit="DA")) == value


@given(
    st.dates(min_value=date(2020, 1, 1), max_value=date(2026, 12, 31)), st.sampled_from(DATE_STYLES)
)
def test_printed_dates_parse_back_exactly(value: date, style: str) -> None:
    assert parse_date(format_date(value, style)) == value


@pytest.mark.parametrize("seed", range(200))
def test_clean_invoices_have_no_validation_issues(seed: int) -> None:
    invoice = make_invoice(random.Random(seed))
    assert validate(invoice, CFG) == []


def test_generation_is_deterministic() -> None:
    assert make_invoice(random.Random(7)) == make_invoice(random.Random(7))
    assert make_invoice(random.Random(7)) != make_invoice(random.Random(8))


def test_identifiers_are_random_with_the_right_shape() -> None:
    invoice = make_invoice(random.Random(1))
    assert len(invoice.seller.nif or "") == 15 and (invoice.seller.nif or "").isdigit()
    assert len(invoice.seller.nis or "") == 15
    assert invoice.seller.nif != invoice.buyer.nif


@pytest.mark.parametrize(
    ("kind", "rule"),
    [("wrong_total", "total.ttc"), ("wrong_vat", "vat.amount"), ("missing_date", "required")],
)
def test_injected_errors_are_caught_by_the_validator(kind: str, rule: str) -> None:
    assert kind in ERROR_KINDS
    bad = inject_error(make_invoice(random.Random(3)), kind)
    assert rule in {i.rule for i in validate(bad, CFG)}


def test_unknown_error_kind_is_rejected() -> None:
    with pytest.raises(ValueError):
        inject_error(make_invoice(random.Random(3)), "nonsense")


@pytest.mark.parametrize("template", TEMPLATES)
@pytest.mark.parametrize("numbers", NUMBER_STYLES)
def test_html_contains_the_printed_total_and_number(template: str, numbers: str) -> None:
    invoice = make_invoice(random.Random(11))
    html = render_html(invoice, Style(template, numbers, "numeric"))
    assert format_amount(invoice.total_ttc or Decimal(0), numbers) in html
    assert invoice.invoice_number in html


def test_arabic_template_has_rtl_text_and_french_template_does_not_need_it() -> None:
    invoice = make_invoice(random.Random(5))
    assert "فاتورة" in render_html(invoice, Style("bilingual", "space", "long_ar"))
    assert "FACTURE" in render_html(invoice, Style("fr", "space", "long_fr"))


def test_html_escapes_hostile_text() -> None:
    invoice = make_invoice(random.Random(5))
    evil = invoice.model_copy(update={"invoice_number": "<script>alert(1)</script>"})
    assert "<script>alert(1)</script>" not in render_html(evil, random_style(random.Random(1)))


def test_end_to_end_files_are_written(tmp_path: Path) -> None:
    pytest.importorskip("playwright")
    try:
        generate(3, tmp_path, seed=1, error_rate=1.0)
    except Exception as err:
        pytest.skip(f"Chromium not available: {err}")
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == [f"inv_1_{i:05d}.{ext}" for i in range(3) for ext in ("json", "pdf", "png")]
    truth = json.loads((tmp_path / "inv_1_00000.json").read_text(encoding="utf-8"))
    assert truth["meta"]["injected_error"] in ERROR_KINDS
    assert (tmp_path / "inv_1_00000.png").stat().st_size > 10_000
