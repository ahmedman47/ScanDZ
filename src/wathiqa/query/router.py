"""A rule-based question router: the cheap baseline to beat before using an LLM router.

It also serves as the safe fallback when the model is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from wathiqa.domain.normalize import normalize_text


def _words(*phrases: str) -> tuple[str, ...]:
    return tuple(normalize_text(p) for p in phrases)


AGGREGATE = _words(
    "combien", "total", "somme", "dépensé", "depense", "payé", "how much", "spend", "spent",
    "paid", "sum", "كم", "مجموع", "إجمالي", "دفعت", "أنفقت",
)  # fmt: skip
BY_MONTH = _words("par mois", "mensuel", "by month", "monthly", "per month", "شهريا", "حسب الشهر")
BY_SUPPLIER = _words("fournisseur", "supplier", "vendor", "مورد", "الموردين")
TOP = _words("top", "principaux", "plus gros", "largest", "biggest", "أكبر")


@dataclass(frozen=True, slots=True)
class Route:
    kind: Literal["analytics", "document_qa"]
    tool: str | None = None


def _has(question: str, words: tuple[str, ...]) -> bool:
    """Match whole words (so "sum" does not fire inside "assume"), allow plural endings on
    long Latin words, and match Arabic as a substring because of attached prefixes."""
    tokens = question.split()
    padded = f" {question} "
    for word in words:
        if " " in word:
            if f" {word} " in padded:
                return True
        elif word.isascii():
            if any(t == word or (len(word) >= 6 and t.startswith(word)) for t in tokens):
                return True
        elif word in question:
            return True
    return False


def route_question(question: str) -> Route:
    """Numbers and groupings go to SQL tools; everything else goes to retrieval."""
    q = normalize_text(question)
    if _has(q, TOP) and _has(q, BY_SUPPLIER):
        return Route("analytics", "top_suppliers")
    if _has(q, BY_MONTH):
        return Route("analytics", "spend_by_month")
    if _has(q, AGGREGATE) and _has(q, BY_SUPPLIER):
        return Route("analytics", "spend_by_supplier")
    if _has(q, AGGREGATE):
        return Route("analytics", "spend_by_month")
    return Route("document_qa")
