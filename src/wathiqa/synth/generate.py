"""Random invoices with a known ground truth.

Every identifier is random: it has the right *format* but belongs to nobody. Totals are
computed from the lines, so a clean invoice passes ``validate`` with no issues. A labeled
minority can be corrupted on purpose (``inject_error``) to test the validators.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from wathiqa.domain.contract import DocType, Invoice, LineItem, Party
from wathiqa.synth.catalog import (
    CASH_INDEX,
    CITIES,
    DOMAINS,
    LEGAL_FORMS,
    PAYMENTS,
    SPECS,
    STEMS,
    STREETS,
)

CENT = Decimal("0.01")
LANG_INDEX = {"fr": 0, "ar": 1, "en": 2}
DOMAIN_NAMES = tuple(DOMAINS)

# (min lines, max lines, weight): many short invoices, some long ones that spill onto page 2.
LINE_BUCKETS = [(1, 4, 35), (5, 10, 40), (11, 20, 20), (21, 35, 5)]


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _digits(rng: random.Random, n: int) -> str:
    return "".join(str(rng.randrange(10)) for _ in range(n))


def make_party(rng: random.Random, lang: str = "fr", domain: str | None = None) -> Party:
    i = LANG_INDEX[lang]
    city = rng.choice(CITIES)
    street = rng.choice(STREETS)
    stem = rng.choice(STEMS)[i]
    sector = DOMAINS[domain or rng.choice(DOMAIN_NAMES)]["sector"][i]
    legal = rng.choice(LEGAL_FORMS)
    number = rng.randrange(1, 120)
    if lang == "ar":
        name = f"{legal[1]} {stem} {sector}"
        address = f"{number} {street[1]}، {city[1]}"
    elif lang == "en":
        name = f"{stem} {sector} {legal[0]}"
        address = f"{number} {street[2]}, {city[2]}"
    else:
        name = f"{legal[0]} {stem} {sector}"
        address = f"{number} {street[0]}, {city[0]}"
    return Party(
        name=name,
        nif=_digits(rng, 15),
        nis=_digits(rng, 15),
        rc=f"{city[3]}/00-{_digits(rng, 7)}B{_digits(rng, 2)}",
        ai=_digits(rng, 11),
        address=address,
    )


def arabic_for(description: str) -> str:
    """Arabic wording for a French catalogue description (used by bilingual layouts)."""
    for domain in DOMAINS.values():
        for fr, ar, _en, _price in domain["items"]:
            if description.startswith(fr):
                return ar + description[len(fr) :].split(" — ")[0]
    return ""


def _n_lines(rng: random.Random) -> int:
    low, high, _ = rng.choices(LINE_BUCKETS, weights=[b[2] for b in LINE_BUCKETS])[0]
    return rng.randint(low, high)


def make_invoice(
    rng: random.Random,
    today: date = date(2026, 11, 1),
    lang: str = "fr",
    domain: str | None = None,
) -> Invoice:
    """A clean, arithmetically consistent invoice, written in ``lang`` (fr, ar or en)."""
    i = LANG_INDEX[lang]
    domain = domain or rng.choice(DOMAIN_NAMES)
    items = list(DOMAINS[domain]["items"])
    n_lines = _n_lines(rng)
    chosen = rng.sample(items, k=min(n_lines, len(items)))
    while len(chosen) < n_lines:  # long invoices repeat products with other references
        chosen.append(rng.choice(items))
    long_text = n_lines > 10
    lines: list[LineItem] = []
    for item in chosen:
        low, high = item[3]
        qty = Decimal(rng.randint(1, 20))
        unit = _money(
            Decimal(rng.randint(low, high)) + Decimal(rng.choice([0, 0, 50, 250, 990])) / 100
        )
        text = item[i]
        if long_text and rng.random() < 0.5:
            text = (
                f"{text} réf. {rng.randint(100, 9999)}"
                if lang != "ar"
                else f"{text} {rng.randint(100, 9999)}"
            )
        if rng.random() < 0.15:  # a description long enough to wrap
            text = f"{text} — {rng.choice(SPECS[lang])}"
        lines.append(
            LineItem(
                description=text, quantity=qty, unit_price_ht=unit, total_ht=_money(qty * unit)
            )
        )
    total_ht = _money(sum((line.total_ht or Decimal(0) for line in lines), Decimal(0)))
    vat_rate = Decimal(rng.choice([19, 19, 19, 9, 0]))
    vat_amount = _money(total_ht * vat_rate / 100)
    pay_index = rng.randrange(len(PAYMENTS[lang]))
    timbre = (
        _money(max(Decimal(1), min(Decimal(2500), (total_ht + vat_amount) * Decimal("0.01"))))
        if pay_index == CASH_INDEX
        else None
    )
    issue = today - timedelta(days=rng.randint(1, 600))
    proforma = rng.random() < 0.10
    return Invoice(
        doc_type=DocType.PROFORMA if proforma else DocType.INVOICE,
        invoice_number=f"{'PF' if proforma else 'FA'}-{issue.year}/{rng.randint(1, 9999):04d}",
        issue_date=issue,
        due_date=issue + timedelta(days=rng.choice([0, 15, 30, 45])),
        currency="DZD",
        seller=make_party(rng, lang, domain),
        buyer=make_party(rng, lang),
        lines=lines,
        total_ht=total_ht,
        vat_rate=vat_rate,
        vat_amount=vat_amount,
        timbre=timbre,
        total_ttc=_money(total_ht + vat_amount + (timbre or Decimal(0))),
        payment_method=PAYMENTS[lang][pay_index],
    )


ERROR_KINDS = ("wrong_total", "wrong_vat", "missing_date")


def inject_error(invoice: Invoice, kind: str) -> Invoice:
    """Corrupt one thing on purpose. The label is stored so validators can be tested."""
    if kind == "wrong_total":
        return invoice.model_copy(
            update={"total_ttc": _money((invoice.total_ttc or Decimal(0)) + Decimal(1000))}
        )
    if kind == "wrong_vat":
        return invoice.model_copy(
            update={"vat_amount": _money((invoice.vat_amount or Decimal(0)) + Decimal(500))}
        )
    if kind == "missing_date":
        return invoice.model_copy(update={"issue_date": None})
    raise ValueError(f"unknown error kind: {kind}")


@dataclass(frozen=True, slots=True)
class Style:
    template: str
    numbers: str
    dates: str


# template -> label language. "bi" prints French and Arabic labels side by side.
TEMPLATE_LANG = {
    "fr": "fr", "compact": "fr", "ticket": "fr", "banner": "fr", "dense": "fr",
    "modern": "fr", "sidebar": "fr",
    "bilingual": "bi", "stamp": "bi",
    "ar": "ar", "ar_modern": "ar",
    "en": "en",
}  # fmt: skip
# Development layouts are used for everything. Test layouts are never used for tuning.
DEV_TEMPLATES = ("fr", "compact", "bilingual", "ar", "en", "ticket", "banner", "dense")
TEST_TEMPLATES = ("modern", "sidebar", "ar_modern", "stamp")
TEMPLATES = DEV_TEMPLATES + TEST_TEMPLATES

NUMBER_STYLES = ("space", "dots", "arabic", "en")
DATE_STYLES = ("numeric", "long_fr", "long_ar", "long_en")

# Printed styles that are realistic for each label language.
ALLOWED: dict[str, dict[str, tuple[str, ...]]] = {
    "fr": {"numbers": ("space", "dots"), "dates": ("numeric", "long_fr")},
    "ar": {"numbers": ("space", "dots", "arabic"), "dates": ("numeric", "long_ar")},
    "bi": {"numbers": ("space", "dots", "arabic"), "dates": ("numeric", "long_fr", "long_ar")},
    "en": {"numbers": ("en",), "dates": ("numeric", "long_en")},
}


def label_language(template: str) -> str:
    return TEMPLATE_LANG[template]


def content_language(template: str) -> str:
    """Language of names and descriptions: bilingual layouts carry French content."""
    lang = TEMPLATE_LANG[template]
    return "fr" if lang == "bi" else lang


def random_style(
    rng: random.Random,
    template: str | None = None,
    pool: tuple[str, ...] = TEMPLATES,
) -> Style:
    name = template or rng.choice(pool)
    allowed = ALLOWED[label_language(name)]
    return Style(
        template=name,
        numbers=rng.choice(allowed["numbers"]),
        dates=rng.choice(allowed["dates"]),
    )
