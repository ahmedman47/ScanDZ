"""Convert the model's raw strings into a typed, normalised invoice."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from wathiqa.domain.contract import (
    DocType,
    Invoice,
    Issue,
    LineItem,
    Party,
    RawInvoice,
    RawParty,
)
from wathiqa.domain.normalize import (
    normalize_text,
    parse_amount,
    parse_date,
    parse_percent,
)

# Order matters: "facture proforma" must be tested before "facture".
_DOC_TYPE_KEYWORDS: tuple[tuple[str, DocType], ...] = tuple(
    (normalize_text(word), kind)
    for word, kind in (
        ("proforma", DocType.PROFORMA),
        ("pro forma", DocType.PROFORMA),
        ("شكلية", DocType.PROFORMA),
        ("bon de livraison", DocType.DELIVERY_NOTE),
        ("delivery note", DocType.DELIVERY_NOTE),
        ("سند التسليم", DocType.DELIVERY_NOTE),
        ("وصل التسليم", DocType.DELIVERY_NOTE),
        ("devis", DocType.QUOTE),
        ("عرض سعر", DocType.QUOTE),
        ("ticket", DocType.RECEIPT),
        ("reçu", DocType.RECEIPT),
        ("receipt", DocType.RECEIPT),
        ("وصل", DocType.RECEIPT),
        ("facture", DocType.INVOICE),
        ("invoice", DocType.INVOICE),
        ("فاتورة", DocType.INVOICE),
    )
)


def _doc_type(value: str | None) -> DocType:
    text = normalize_text(value)
    for keyword, kind in _DOC_TYPE_KEYWORDS:
        if keyword in text:
            return kind
    return DocType.OTHER if text else DocType.INVOICE


def _currency(value: str | None) -> str | None:
    text = normalize_text(value)
    if not text:
        return None
    tokens = set(text.split())
    if tokens & {"da", "dzd", "دج"} or {"د", "ج"} <= tokens or "dinar" in text or "دينار" in text:
        return "DZD"
    return text.upper() if text.isascii() and len(text) == 3 else value


def _party(raw: RawParty) -> Party:
    return Party(**{k: (v.strip() or None) if v else None for k, v in raw.model_dump().items()})


def to_invoice(raw: RawInvoice) -> tuple[Invoice, list[Issue]]:
    """Return the typed invoice and the parse problems found on the way."""
    issues: list[Issue] = []

    def amount(value: str | None, field: str) -> Decimal | None:
        if value is None or not value.strip():
            return None
        parsed = parse_amount(value)
        if parsed is None:
            issues.append(Issue("parse.amount", "warning", f"cannot parse {value!r}", (field,)))
        return parsed

    def day(value: str | None, field: str) -> date | None:
        if value is None or not value.strip():
            return None
        parsed = parse_date(value)
        if parsed is None:
            issues.append(Issue("parse.date", "warning", f"cannot parse {value!r}", (field,)))
        return parsed

    def percent(value: str | None, field: str) -> Decimal | None:
        if value is None or not value.strip():
            return None
        parsed = parse_percent(value)
        if parsed is None:
            issues.append(Issue("parse.percent", "warning", f"cannot parse {value!r}", (field,)))
        return parsed

    lines = [
        LineItem(
            description=(line.description or "").strip() or None,
            quantity=amount(line.quantity, f"lines.{i}.quantity"),
            unit_price_ht=amount(line.unit_price_ht, f"lines.{i}.unit_price_ht"),
            vat_rate=percent(line.vat_rate, f"lines.{i}.vat_rate"),
            total_ht=amount(line.total_ht, f"lines.{i}.total_ht"),
        )
        for i, line in enumerate(raw.lines)
    ]
    invoice = Invoice(
        doc_type=_doc_type(raw.doc_type),
        invoice_number=(raw.invoice_number or "").strip() or None,
        issue_date=day(raw.issue_date, "issue_date"),
        due_date=day(raw.due_date, "due_date"),
        currency=_currency(raw.currency),
        seller=_party(raw.seller),
        buyer=_party(raw.buyer),
        lines=lines,
        total_ht=amount(raw.total_ht, "total_ht"),
        vat_rate=percent(raw.vat_rate, "vat_rate"),
        vat_amount=amount(raw.vat_amount, "vat_amount"),
        timbre=amount(raw.timbre, "timbre"),
        total_ttc=amount(raw.total_ttc, "total_ttc"),
        payment_method=(raw.payment_method or "").strip() or None,
    )
    return invoice, issues
