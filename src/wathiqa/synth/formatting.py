"""Print numbers and dates the way Algerian documents print them.

Round-trip tests check that ``parse_amount(format_amount(x)) == x`` for every style, so the
generator and the parsers can never silently disagree.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

NBSP = "\u00a0"
_ARABIC_INDIC = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
             "septembre", "octobre", "novembre", "décembre"]  # fmt: skip
MONTHS_AR = ["جانفي", "فيفري", "مارس", "أفريل", "ماي", "جوان", "جويلية", "أوت",
             "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]  # fmt: skip


def format_amount(value: Decimal, style: str, *, unit: str = "") -> str:
    whole, frac = f"{value:.2f}".split(".")
    sign = "-" if whole.startswith("-") else ""
    groups = f"{int(whole.lstrip('-')):,}"
    if style == "space":
        text = f"{groups.replace(',', ' ')},{frac}"
    elif style == "dots":
        text = f"{groups.replace(',', '.')},{frac}"
    elif style == "arabic":
        # A no-break space (a "common separator" in Unicode bidi rules) keeps digit groups in
        # reading order inside right-to-left text; an ordinary space would reverse them.
        text = f"{groups.replace(',', NBSP)},{frac}".translate(_ARABIC_INDIC)
    else:
        raise ValueError(f"unknown number style: {style}")
    return f"{sign}{text} {unit}".strip()


def format_quantity(value: Decimal, style: str) -> str:
    text = str(int(value)) if value == value.to_integral() else f"{value:.3f}".replace(".", ",")
    return text.translate(_ARABIC_INDIC) if style == "arabic" else text


def format_date(value: date, style: str) -> str:
    if style == "numeric":
        return f"{value.day:02d}/{value.month:02d}/{value.year}"
    if style == "long_fr":
        day = "1er" if value.day == 1 else str(value.day)
        return f"{day} {MONTHS_FR[value.month - 1]} {value.year}"
    if style == "long_ar":
        return f"{value.day} {MONTHS_AR[value.month - 1]} {value.year}".translate(_ARABIC_INDIC)
    raise ValueError(f"unknown date style: {style}")
