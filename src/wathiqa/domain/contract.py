"""Data contracts.

Two layers, on purpose:

* ``Raw*``    - what the language model returns: strings exactly as printed.
* ``Invoice`` - typed, normalised values produced by deterministic code.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DocType(StrEnum):
    INVOICE = "invoice"
    PROFORMA = "proforma"
    RECEIPT = "receipt"
    DELIVERY_NOTE = "delivery_note"
    QUOTE = "quote"
    OTHER = "other"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------ raw (LLM output)
class RawParty(_Strict):
    name: str | None = Field(None, description="Company name exactly as printed")
    nif: str | None = Field(None, description="Tax identification number (NIF), as printed")
    nis: str | None = Field(None, description="Statistical identification number (NIS)")
    rc: str | None = Field(None, description="Trade register number (RC)")
    ai: str | None = Field(None, description="Tax article number (AI)")
    address: str | None = None


class RawLine(_Strict):
    description: str | None = None
    quantity: str | None = None
    unit_price_ht: str | None = Field(None, description="Unit price excluding VAT, as printed")
    vat_rate: str | None = Field(None, description="VAT rate of the line, as printed")
    total_ht: str | None = Field(None, description="Line amount excluding VAT, as printed")


class RawInvoice(_Strict):
    doc_type: str | None = Field(None, description="Document title, e.g. Facture, Devis")
    invoice_number: str | None = None
    issue_date: str | None = Field(None, description="Issue date exactly as printed")
    due_date: str | None = None
    currency: str | None = None
    seller: RawParty = RawParty()
    buyer: RawParty = RawParty()
    lines: list[RawLine] = []
    total_ht: str | None = Field(None, description="Total excluding VAT, as printed")
    vat_rate: str | None = Field(None, description="Main VAT rate, as printed")
    vat_amount: str | None = Field(None, description="Total VAT amount, as printed")
    timbre: str | None = Field(None, description="Stamp duty (droit de timbre), as printed")
    total_ttc: str | None = Field(None, description="Grand total including VAT, as printed")
    payment_method: str | None = None


# ----------------------------------------------------------- typed (normalised) form
class Party(_Strict):
    name: str | None = None
    nif: str | None = None
    nis: str | None = None
    rc: str | None = None
    ai: str | None = None
    address: str | None = None


class LineItem(_Strict):
    description: str | None = None
    quantity: Decimal | None = None
    unit_price_ht: Decimal | None = None
    vat_rate: Decimal | None = None
    total_ht: Decimal | None = None


class Invoice(_Strict):
    doc_type: DocType = DocType.INVOICE
    invoice_number: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    currency: str | None = None
    seller: Party = Party()
    buyer: Party = Party()
    lines: list[LineItem] = []
    total_ht: Decimal | None = None
    vat_rate: Decimal | None = None
    vat_amount: Decimal | None = None
    timbre: Decimal | None = None
    total_ttc: Decimal | None = None
    payment_method: str | None = None


@dataclass(frozen=True, slots=True)
class Issue:
    """A problem found while converting or validating a document."""

    rule: str
    severity: Literal["error", "warning"]
    message: str
    fields: tuple[str, ...] = ()
