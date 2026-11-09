"""Business-rule validation. Pure functions: no I/O, no model calls.

Rules that depend on the country (VAT rates, identifier lengths) live in
``RuleConfig`` so they can be changed without touching the rules themselves.
Confirm every default against the official source before you rely on it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from wathiqa.domain.contract import Invoice, Issue
from wathiqa.domain.normalize import digits_only


@dataclass(frozen=True, slots=True)
class RuleConfig:
    vat_rates: frozenset[Decimal] = frozenset({Decimal(0), Decimal(9), Decimal(19)})
    total_tolerance: Decimal = Decimal("1.00")  # printed totals are often rounded
    line_tolerance: Decimal = Decimal("0.02")
    nif_lengths: frozenset[int] = frozenset({15, 20})
    nis_lengths: frozenset[int] = frozenset({15})
    min_date: date = date(2000, 1, 1)
    today: date | None = None
    currencies: frozenset[str] = field(default_factory=lambda: frozenset({"DZD"}))


Rule = Callable[[Invoice, RuleConfig], list[Issue]]


def _required(inv: Invoice, cfg: RuleConfig) -> list[Issue]:
    values = {
        "invoice_number": inv.invoice_number,
        "issue_date": inv.issue_date,
        "seller.name": inv.seller.name,
        "total_ttc": inv.total_ttc,
    }
    return [
        Issue("required", "error", f"{name} is missing", (name,))
        for name, value in values.items()
        if value is None
    ]


def _dates(inv: Invoice, cfg: RuleConfig) -> list[Issue]:
    issues: list[Issue] = []
    today = cfg.today or date.today()
    if inv.issue_date is not None:
        if inv.issue_date > today + timedelta(days=1):
            issues.append(
                Issue("date.future", "error", "issue date is in the future", ("issue_date",))
            )
        if inv.issue_date < cfg.min_date:
            issues.append(Issue("date.old", "error", "issue date is before 2000", ("issue_date",)))
        if inv.due_date is not None and inv.due_date < inv.issue_date:
            issues.append(
                Issue("date.order", "error", "due date is before issue date", ("due_date",))
            )
    return issues


def _sum_of_lines(inv: Invoice, cfg: RuleConfig) -> list[Issue]:
    amounts = [line.total_ht for line in inv.lines]
    if inv.total_ht is None or not amounts or any(a is None for a in amounts):
        return []
    total = sum((a for a in amounts if a is not None), Decimal(0))
    if abs(total - inv.total_ht) > cfg.total_tolerance:
        message = f"sum of lines {total} differs from total_ht {inv.total_ht}"
        return [Issue("sum.lines", "error", message, ("lines", "total_ht"))]
    return []


def _line_arithmetic(inv: Invoice, cfg: RuleConfig) -> list[Issue]:
    issues: list[Issue] = []
    for i, line in enumerate(inv.lines):
        if line.quantity is None or line.unit_price_ht is None or line.total_ht is None:
            continue
        expected = line.quantity * line.unit_price_ht
        if abs(expected - line.total_ht) > cfg.line_tolerance:
            # A warning, not an error: a discount column can legitimately break the identity.
            message = f"line {i + 1}: {line.quantity} x {line.unit_price_ht} is not {line.total_ht}"
            issues.append(Issue("line.arithmetic", "warning", message, (f"lines.{i}.total_ht",)))
    return issues


def _vat(inv: Invoice, cfg: RuleConfig) -> list[Issue]:
    if inv.vat_amount is None or inv.total_ht is None:
        return []
    if inv.vat_rate is not None:
        expected = inv.total_ht * inv.vat_rate / 100
    elif inv.lines and all(ln.total_ht is not None and ln.vat_rate is not None for ln in inv.lines):
        expected = sum(
            (ln.total_ht * ln.vat_rate / 100 for ln in inv.lines if ln.total_ht and ln.vat_rate),
            Decimal(0),
        )
    else:
        return []
    if abs(expected - inv.vat_amount) > cfg.total_tolerance:
        message = f"expected VAT {expected:.2f}, found {inv.vat_amount}"
        return [Issue("vat.amount", "error", message, ("vat_amount",))]
    return []


def _grand_total(inv: Invoice, cfg: RuleConfig) -> list[Issue]:
    if inv.total_ht is None or inv.vat_amount is None or inv.total_ttc is None:
        return []
    expected = inv.total_ht + inv.vat_amount + (inv.timbre or Decimal(0))
    if abs(expected - inv.total_ttc) > cfg.total_tolerance:
        message = f"total_ht + VAT + timbre = {expected}, but total_ttc is {inv.total_ttc}"
        return [Issue("total.ttc", "error", message, ("total_ttc",))]
    return []


def _vat_rates(inv: Invoice, cfg: RuleConfig) -> list[Issue]:
    rates = [inv.vat_rate, *(line.vat_rate for line in inv.lines)]
    unknown = sorted({r for r in rates if r is not None and r not in cfg.vat_rates})
    return [Issue("vat.rate", "warning", f"unusual VAT rate {r}%", ("vat_rate",)) for r in unknown]


def _identifiers(inv: Invoice, cfg: RuleConfig) -> list[Issue]:
    issues: list[Issue] = []
    for role, party in (("seller", inv.seller), ("buyer", inv.buyer)):
        for name, value, lengths in (
            ("nif", party.nif, cfg.nif_lengths),
            ("nis", party.nis, cfg.nis_lengths),
        ):
            if not value:
                continue
            digits = digits_only(value)
            if len(digits) not in lengths:
                message = f"{role}.{name} has {len(digits)} digits, expected {sorted(lengths)}"
                issues.append(Issue("id.format", "warning", message, (f"{role}.{name}",)))
    return issues


def _currency(inv: Invoice, cfg: RuleConfig) -> list[Issue]:
    if inv.currency is not None and inv.currency not in cfg.currencies:
        return [
            Issue("currency", "warning", f"currency {inv.currency!r} not expected", ("currency",))
        ]
    return []


def _signs(inv: Invoice, cfg: RuleConfig) -> list[Issue]:
    amounts = {"total_ht": inv.total_ht, "vat_amount": inv.vat_amount, "total_ttc": inv.total_ttc}
    return [
        Issue("amount.negative", "warning", f"{name} is negative", (name,))
        for name, value in amounts.items()
        if value is not None and value < 0
    ]


RULES: tuple[Rule, ...] = (
    _required,
    _dates,
    _sum_of_lines,
    _line_arithmetic,
    _vat,
    _grand_total,
    _vat_rates,
    _identifiers,
    _currency,
    _signs,
)


def validate(invoice: Invoice, cfg: RuleConfig | None = None) -> list[Issue]:
    """Run every rule and return all issues (order is stable)."""
    cfg = cfg or RuleConfig()
    return [issue for rule in RULES for issue in rule(invoice, cfg)]


def decide(
    issues: list[Issue],
    *,
    confidence: float,
    min_confidence: float = 0.9,
    block_on_warnings: bool = False,
) -> Literal["auto_accept", "review"]:
    """Straight-through processing decision: any error or low confidence means review."""
    if any(i.severity == "error" for i in issues):
        return "review"
    if block_on_warnings and issues:
        return "review"
    return "auto_accept" if confidence >= min_confidence else "review"
