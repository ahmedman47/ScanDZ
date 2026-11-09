from datetime import date
from decimal import Decimal

import pytest

from wathiqa.domain.contract import Invoice, LineItem, Party, RawInvoice, RawLine, RawParty
from wathiqa.domain.convert import to_invoice
from wathiqa.domain.validate import RuleConfig, decide, validate

D = Decimal
CFG = RuleConfig(today=date(2026, 10, 1))


def good() -> Invoice:
    return Invoice(
        invoice_number="FA-2026/0012",
        issue_date=date(2026, 1, 12),
        currency="DZD",
        seller=Party(name="SARL Alpha", nif="002016001234567"),
        buyer=Party(name="EURL Beta"),
        lines=[
            LineItem(
                description="Papier A4", quantity=D(2), unit_price_ht=D(5000), total_ht=D(10000)
            ),
            LineItem(description="Toner", quantity=D(1), unit_price_ht=D(2000), total_ht=D(2000)),
        ],
        total_ht=D(12000),
        vat_rate=D(19),
        vat_amount=D(2280),
        total_ttc=D("14280.00"),
    )


def rules(inv: Invoice) -> set[str]:
    return {i.rule for i in validate(inv, CFG)}


def test_valid_invoice_has_no_issues() -> None:
    assert validate(good(), CFG) == []


def test_rounding_inside_tolerance_is_accepted() -> None:
    assert rules(good().model_copy(update={"total_ttc": D("14280.60")})) == set()


@pytest.mark.parametrize(
    ("update", "expected"),
    [
        ({"total_ttc": D("14500")}, "total.ttc"),
        ({"vat_amount": D("2000")}, "vat.amount"),
        ({"total_ht": D("13000")}, "sum.lines"),
        ({"invoice_number": None}, "required"),
        ({"seller": Party(name=None)}, "required"),
        ({"issue_date": date(2027, 1, 1)}, "date.future"),
        ({"issue_date": date(1999, 5, 1)}, "date.old"),
        ({"due_date": date(2025, 12, 31)}, "date.order"),
        ({"currency": "EUR"}, "currency"),
        ({"vat_rate": D("20"), "vat_amount": D("2400"), "total_ttc": D("14400")}, "vat.rate"),
        ({"seller": Party(name="SARL Alpha", nif="12345")}, "id.format"),
        ({"total_ttc": D("-14280")}, "amount.negative"),
    ],
)
def test_each_rule_fires(update: dict[str, object], expected: str) -> None:
    assert expected in rules(good().model_copy(update=update))


def test_line_arithmetic_is_only_a_warning() -> None:
    inv = good()
    inv.lines[0] = LineItem(
        description="Papier", quantity=D(2), unit_price_ht=D(5000), total_ht=D(9000)
    )
    inv = inv.model_copy(
        update={"total_ht": D(11000), "vat_amount": D("2090"), "total_ttc": D("13090")}
    )
    found = {i.rule: i.severity for i in validate(inv, CFG)}
    assert found == {"line.arithmetic": "warning"}


def test_timbre_is_part_of_the_grand_total() -> None:
    inv = good().model_copy(update={"timbre": D(100), "total_ttc": D("14380")})
    assert validate(inv, CFG) == []


def test_decide() -> None:
    assert decide([], confidence=0.95) == "auto_accept"
    assert decide([], confidence=0.80) == "review"
    errors = validate(good().model_copy(update={"total_ttc": D(1)}), CFG)
    assert decide(errors, confidence=0.99) == "review"
    warnings = validate(good().model_copy(update={"currency": "EUR"}), CFG)
    assert decide(warnings, confidence=0.95) == "auto_accept"
    assert decide(warnings, confidence=0.95, block_on_warnings=True) == "review"


def test_raw_to_typed_end_to_end() -> None:
    raw = RawInvoice(
        doc_type="Facture",
        invoice_number=" FA-2026/0012 ",
        issue_date="12 janvier 2026",
        currency="DA",
        seller=RawParty(name="SARL Alpha", nif="٠٠٢٠١٦٠٠١٢٣٤٥٦٧"),
        lines=[
            RawLine(
                description="Papier A4",
                quantity="2",
                unit_price_ht="5 000,00",
                total_ht="10 000,00",
            )
        ],
        total_ht="10 000,00",
        vat_rate="19%",
        vat_amount="1 900,00",
        total_ttc="11 900,00 DA",
    )
    inv, issues = to_invoice(raw)
    assert issues == []
    assert inv.invoice_number == "FA-2026/0012"
    assert inv.issue_date == date(2026, 1, 12)
    assert inv.currency == "DZD"
    assert inv.total_ttc == D("11900.00")
    assert inv.lines[0].unit_price_ht == D("5000.00")
    assert validate(inv, CFG) == []


def test_unparseable_values_become_warnings_not_crashes() -> None:
    inv, issues = to_invoice(RawInvoice(issue_date="n'importe quoi", total_ttc="abc"))
    assert inv.issue_date is None and inv.total_ttc is None
    assert {i.rule for i in issues} == {"parse.date", "parse.amount"}


@pytest.mark.parametrize(
    ("title", "kind"),
    [
        ("FACTURE PROFORMA N° 4", "proforma"),
        ("Facture", "invoice"),
        ("فاتورة", "invoice"),
        ("Bon de livraison", "delivery_note"),
        ("DEVIS", "quote"),
        ("Ticket de caisse", "receipt"),
        ("Relevé bancaire", "other"),
        (None, "invoice"),
    ],
)
def test_document_type_detection(title: str | None, kind: str) -> None:
    inv, _ = to_invoice(RawInvoice(doc_type=title))
    assert inv.doc_type.value == kind
