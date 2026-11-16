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

CENT = Decimal("0.01")

COMPANY_STEMS = [
    "Atlas", "Numidia", "El Baraka", "Tassili", "Djurdjura", "Hoggar", "Mitidja", "Soummam",
    "Aurès", "El Amel", "Ibn Khaldoun", "Sahara", "Chelia", "Medina", "El Feth", "Rayan",
    "Nour", "Salam", "Rim", "Zahra",
]  # fmt: skip
COMPANY_SECTORS = ["Informatique", "Fournitures", "Négoce", "Bâtiment", "Services", "Alimentaire"]
LEGAL_FORMS = ["SARL", "EURL", "SPA", "Ets"]
CITIES = [
    ("Alger", "16"), ("Oran", "31"), ("Constantine", "25"), ("Annaba", "23"),
    ("Sétif", "19"), ("Blida", "09"), ("Batna", "05"), ("Tlemcen", "13"),
    ("Béjaïa", "06"), ("Biskra", "07"),
]  # fmt: skip
STREETS = [
    "Rue Didouche Mourad", "Boulevard de l'ALN", "Cité des Frères",
    "Zone industrielle", "Rue de la Liberté",
]  # fmt: skip

# (French description, Arabic description, typical unit price range in DZD)
CATALOGUE = [
    ("Ramette papier A4", "رزمة ورق A4", (450, 900)),
    ("Cartouche toner noir", "خرطوشة حبر أسود", (6000, 18000)),
    ("Clavier USB", "لوحة مفاتيح USB", (1200, 4500)),
    ("Souris sans fil", "فأرة لاسلكية", (900, 3500)),
    ("Écran 24 pouces", "شاشة 24 بوصة", (22000, 48000)),
    ("Classeur à levier", "ملف أرشيف", (150, 450)),
    ("Câble réseau 10 m", "كابل شبكة 10 م", (700, 2200)),
    ("Ciment 50 kg", "إسمنت 50 كغ", (700, 1100)),
    ("Peinture 20 L", "طلاء 20 لتر", (5500, 14000)),
    ("Maintenance mensuelle", "صيانة شهرية", (15000, 60000)),
    ("Formation (jour)", "تكوين (يوم)", (20000, 55000)),
    ("Transport de marchandises", "نقل بضائع", (8000, 30000)),
]
PAYMENTS = ["Virement", "Chèque", "Espèces", "Traite"]


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _digits(rng: random.Random, n: int) -> str:
    return "".join(str(rng.randrange(10)) for _ in range(n))


def make_party(rng: random.Random) -> Party:
    city, wilaya = rng.choice(CITIES)
    name = f"{rng.choice(LEGAL_FORMS)} {rng.choice(COMPANY_STEMS)} {rng.choice(COMPANY_SECTORS)}"
    return Party(
        name=name,
        nif=_digits(rng, 15),
        nis=_digits(rng, 15),
        rc=f"{wilaya}/00-{_digits(rng, 7)}B{_digits(rng, 2)}",
        ai=_digits(rng, 11),
        address=f"{rng.randrange(1, 120)} {rng.choice(STREETS)}, {city}",
    )


def make_invoice(rng: random.Random, today: date = date(2026, 11, 1)) -> Invoice:
    """A clean, arithmetically consistent invoice."""
    n_lines = rng.randint(1, 8)
    lines: list[LineItem] = []
    for item in rng.sample(CATALOGUE, k=min(n_lines, len(CATALOGUE))):
        low, high = item[2]
        qty = Decimal(rng.randint(1, 20))
        unit = _money(
            Decimal(rng.randint(low, high)) + Decimal(rng.choice([0, 0, 50, 250, 990])) / 100
        )
        lines.append(
            LineItem(
                description=item[0],
                quantity=qty,
                unit_price_ht=unit,
                total_ht=_money(qty * unit),
            )
        )
    total_ht = _money(sum((line.total_ht or Decimal(0) for line in lines), Decimal(0)))
    vat_rate = Decimal(rng.choice([19, 19, 19, 9, 0]))
    vat_amount = _money(total_ht * vat_rate / 100)
    payment = rng.choice(PAYMENTS)
    timbre = (
        _money(max(Decimal(1), min(Decimal(2500), (total_ht + vat_amount) * Decimal("0.01"))))
        if payment == "Espèces"
        else None
    )
    issue = today - timedelta(days=rng.randint(1, 600))
    return Invoice(
        doc_type=DocType.INVOICE,
        invoice_number=f"FA-{issue.year}/{rng.randint(1, 9999):04d}",
        issue_date=issue,
        due_date=issue + timedelta(days=rng.choice([0, 15, 30, 45])),
        currency="DZD",
        seller=make_party(rng),
        buyer=make_party(rng),
        lines=lines,
        total_ht=total_ht,
        vat_rate=vat_rate,
        vat_amount=vat_amount,
        timbre=timbre,
        total_ttc=_money(total_ht + vat_amount + (timbre or Decimal(0))),
        payment_method=payment,
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
    """How numbers and dates are *printed*. The ground truth never depends on this."""

    template: str  # "fr" or "bilingual"
    numbers: str  # "space" -> 1 234,56 | "dots" -> 1.234,56 | "arabic" -> ١ ٢٣٤,٥٦
    dates: str  # "numeric" | "long_fr" | "long_ar"


DEV_TEMPLATES = ("fr", "bilingual", "compact")
TEST_TEMPLATES = ("modern",)  # never used for tuning prompts, regexes or thresholds
TEMPLATES = DEV_TEMPLATES + TEST_TEMPLATES

NUMBER_STYLES = ("space", "dots", "arabic")
DATE_STYLES = ("numeric", "long_fr", "long_ar")

# Which printed styles each template can realistically show.
FRENCH_ONLY = {"numbers": ("space", "dots"), "dates": ("numeric", "long_fr")}
BILINGUAL = {"numbers": NUMBER_STYLES, "dates": DATE_STYLES}
ALLOWED = {
    "fr": FRENCH_ONLY,
    "compact": FRENCH_ONLY,
    "modern": FRENCH_ONLY,
    "bilingual": BILINGUAL,
}


def random_style(
    rng: random.Random,
    template: str | None = None,
    pool: tuple[str, ...] = TEMPLATES,
) -> Style:
    name = template or rng.choice(pool)
    allowed = ALLOWED[name]
    return Style(
        template=name,
        numbers=rng.choice(allowed["numbers"]),
        dates=rng.choice(allowed["dates"]),
    )
