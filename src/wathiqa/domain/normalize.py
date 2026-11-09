"""Normalisation of text, numbers and dates for Arabic/French business documents.

Design rule: the language model copies values *as printed* (strings). This module,
which is plain deterministic code, turns them into typed values. Code is easier to
test and cheaper to debug than a prompt.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

# --------------------------------------------------------------------------- digits
_ARABIC_INDIC = "".join(chr(0x0660 + i) for i in range(10))  # Arabic-Indic digits
_PERSIAN = "".join(chr(0x06F0 + i) for i in range(10))  # Extended Arabic-Indic digits
_DIGITS = str.maketrans(_ARABIC_INDIC + _PERSIAN, "0123456789" * 2)
# U+066B Arabic decimal separator, U+066C Arabic thousands separator, U+060C Arabic comma
_SEPARATORS = str.maketrans({"٫": ".", "٬": ",", "،": ","})


def to_western_digits(text: str) -> str:
    """Map Arabic-Indic and Persian digits (and their separators) to ASCII."""
    return text.translate(_DIGITS).translate(_SEPARATORS)


def digits_only(text: str | None) -> str:
    """Keep only the digits of ``text`` (used to compare identifiers such as the NIF)."""
    return re.sub(r"\D", "", to_western_digits(text or ""))


# ------------------------------------------------------------------- Arabic and text
_DIACRITICS = re.compile("[ً-ٰٟۖ-ۭ]")
_TATWEEL = "ـ"
_ARABIC_FOLD = str.maketrans(
    {
        "أ": "ا",  # alef with hamza above -> alef
        "إ": "ا",  # alef with hamza below -> alef
        "آ": "ا",  # alef with madda -> alef
        "ٱ": "ا",  # alef wasla -> alef
        "ى": "ي",  # alef maqsura -> ya
        "ة": "ه",  # ta marbuta -> ha
    }
)
_NOT_WORD = re.compile(r"[\W_]+")


def normalize_arabic(text: str) -> str:
    """Fold common Arabic spelling variants (Lucene-style) so matching ignores them."""
    # NFKC also folds the Arabic presentation forms that OCR engines often emit.
    text = unicodedata.normalize("NFKC", text)
    text = _DIACRITICS.sub("", text).replace(_TATWEEL, "")
    return text.translate(_ARABIC_FOLD)


def normalize_text(text: str | None) -> str:
    """Canonical form for comparing and searching names, labels and sentences.

    Steps: Western digits, Arabic folding, case folding, accent stripping, then
    every run of punctuation or spaces becomes one space.
    """
    if not text:
        return ""
    text = normalize_arabic(to_western_digits(text)).casefold()
    text = "".join(ch for ch in unicodedata.normalize("NFD", text) if not unicodedata.combining(ch))
    return _NOT_WORD.sub(" ", unicodedata.normalize("NFC", text)).strip()


def squash(text: str | None) -> str:
    """``normalize_text`` without spaces: good for codes such as invoice numbers."""
    return normalize_text(text).replace(" ", "")


def build_or_tsquery(text: str) -> str:
    """Turn a question into an OR query for PostgreSQL ``to_tsquery('simple', ...)``."""
    seen: dict[str, None] = {}
    for token in normalize_text(text).split():
        if len(token) > 1:
            seen.setdefault(token)
    return " | ".join(seen)


# ------------------------------------------------------------------------- amounts
_CURRENCY = re.compile(
    r"(?<![a-z])(?:dzd|d\.?\s?a\.?|dinars?)(?![a-z])|د\.?\s?ج\.?"
    r"|دينار(?:\s+جزائري)?",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\d(?:[\d\s   .,]*\d)?")


def parse_amount(text: str | None) -> Decimal | None:
    """Parse an amount printed in Algerian, French or English style.

    Handles ``1 234,56 DA``, ``1.234,56``, ``1,234.56`` and Arabic-Indic digits.
    A single separator followed by exactly three digits is read as a thousands
    separator, because dinar amounts are printed with two decimals.
    """
    if text is None:
        return None
    s = to_western_digits(str(text)).strip()
    negative = s[:1] in {"-", "−"} or (s.startswith("(") and s.endswith(")"))
    numbers = _NUMBER.findall(_CURRENCY.sub(" ", s))
    if not numbers:
        return None
    token = re.sub(r"\s+", "", numbers[-1])  # last number wins: "Total TTC : 1 234,56"
    decimal_sep: str | None = None
    if "," in token and "." in token:
        decimal_sep = "," if token.rfind(",") > token.rfind(".") else "."
    elif "," in token or "." in token:
        sep = "," if "," in token else "."
        head, *rest = token.split(sep)
        tail = rest[-1]
        thousands = len(rest) > 1 or (len(tail) == 3 and 1 <= len(head) <= 3 and head != "0")
        decimal_sep = None if thousands else sep
    if decimal_sep:
        whole, _, fraction = token.rpartition(decimal_sep)
        token = f"{re.sub(r'[.,]', '', whole)}.{fraction}"
    else:
        token = re.sub(r"[.,]", "", token)
    try:
        value = Decimal(token)
    except InvalidOperation:
        return None
    return -value if negative else value


def parse_percent(text: str | None) -> Decimal | None:
    """Parse ``19 %``, ``TVA 19%`` or ``9,00`` into a Decimal percentage."""
    if text is None:
        return None
    match = re.search(r"\d+(?:[.,]\d+)?", to_western_digits(str(text)))
    return Decimal(match.group().replace(",", ".")) if match else None


# --------------------------------------------------------------------------- dates
_MONTHS: dict[str, int] = {}


def _register(month: int, *names: str) -> None:
    for name in names:
        _MONTHS[normalize_text(name)] = month


# French, English, Maghreb Arabic (used in Algeria) and Egyptian/Gulf Arabic names.
_register(1, "janvier", "january", "جانفي", "يناير")
_register(2, "février", "february", "فيفري", "فبراير")
_register(3, "mars", "march", "مارس")
_register(4, "avril", "april", "أفريل", "أبريل", "ابريل")
_register(5, "mai", "may", "ماي", "مايو")
_register(6, "juin", "june", "جوان", "يونيو")
_register(7, "juillet", "july", "جويلية", "يوليو")
_register(8, "août", "august", "أوت", "أغسطس", "اغسطس")
_register(9, "septembre", "september", "سبتمبر")
_register(10, "octobre", "october", "أكتوبر")
_register(11, "novembre", "november", "نوفمبر")
_register(12, "décembre", "december", "ديسمبر")

_ISO_DATE = re.compile(r"(?<!\d)(\d{4})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{1,2})(?!\d)")
_DMY_DATE = re.compile(r"(?<!\d)(\d{1,2})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{4}|\d{2})(?!\d)")
_TEXT_DMY = re.compile(r"(?<!\d)(\d{1,2})(?:er|st|nd|rd|th)?\s+([^\W\d_]+)\s+(\d{4}|\d{2})(?!\d)")
_TEXT_YMD = re.compile(r"(?<!\d)(\d{4})\s+([^\W\d_]+)\s+(\d{1,2})(?!\d)")


def _month_from_token(token: str) -> int | None:
    if token in _MONTHS:
        return _MONTHS[token]
    if token.isascii() and len(token) >= 3:  # abbreviations: janv, févr, sept, dec ...
        found = {m for name, m in _MONTHS.items() if name.isascii() and name.startswith(token)}
        if len(found) == 1:
            return found.pop()
    return None


def _make_date(year: str, month: int, day: str) -> date | None:
    y = int(year)
    if len(year) == 2:
        y += 2000
    try:
        return date(y, month, int(day))
    except ValueError:
        return None


def parse_date(text: str | None) -> date | None:
    """Parse the date formats seen on Algerian documents; day-first, never guesses."""
    if not text:
        return None
    raw = to_western_digits(str(text)).strip()
    if m := _ISO_DATE.search(raw):
        return _make_date(m.group(1), int(m.group(2)), m.group(3))
    if m := _DMY_DATE.search(raw):
        return _make_date(m.group(3), int(m.group(2)), m.group(1))
    normalized = normalize_text(raw)
    if m := _TEXT_DMY.search(normalized):
        month = _month_from_token(m.group(2))
        return _make_date(m.group(3), month, m.group(1)) if month else None
    if m := _TEXT_YMD.search(normalized):
        month = _month_from_token(m.group(2))
        return _make_date(m.group(1), month, m.group(3)) if month else None
    return None
