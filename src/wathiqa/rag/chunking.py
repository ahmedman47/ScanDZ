"""Turn OCR text and structured invoices into chunks for retrieval."""

from __future__ import annotations

from wathiqa.domain.contract import Invoice


def _tail(lines: list[str], overlap: int) -> list[str]:
    """Trailing lines whose total length stays within ``overlap`` characters."""
    carry: list[str] = []
    size = 0
    for line in reversed(lines):
        if size + len(line) + 1 > overlap:
            break
        carry.insert(0, line)
        size += len(line) + 1
    return carry


def chunk_text(text: str, *, max_chars: int = 800, overlap: int = 120) -> list[str]:
    """Split on line boundaries into chunks of at most ``max_chars`` characters.

    Consecutive chunks share up to ``overlap`` characters of trailing lines, so a
    sentence cut at a boundary is still whole in one of the two chunks.
    """
    if max_chars <= 0 or not 0 <= overlap < max_chars:
        raise ValueError("need max_chars > 0 and 0 <= overlap < max_chars")
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        while len(line) > max_chars:  # very long line: hard split
            lines.append(line[:max_chars])
            line = line[max_chars:]
        if line:
            lines.append(line)
    chunks: list[str] = []
    current: list[str] = []
    for line in lines:
        if current and len("\n".join([*current, line])) > max_chars:
            chunks.append("\n".join(current))
            current = _tail(current, overlap)
            while current and len("\n".join([*current, line])) > max_chars:
                current.pop(0)
        current.append(line)
    if current:
        chunks.append("\n".join(current))
    return chunks


def verbalize(invoice: Invoice) -> str:
    """One compact, searchable paragraph per approved invoice (header plus lines)."""
    header = [
        f"{invoice.doc_type.value} {invoice.invoice_number}" if invoice.invoice_number else None,
        f"date {invoice.issue_date}" if invoice.issue_date else None,
        f"supplier {invoice.seller.name}" if invoice.seller.name else None,
        f"buyer {invoice.buyer.name}" if invoice.buyer.name else None,
        f"total_ht {invoice.total_ht}" if invoice.total_ht is not None else None,
        f"vat {invoice.vat_amount}" if invoice.vat_amount is not None else None,
        f"total_ttc {invoice.total_ttc} {invoice.currency or ''}".strip()
        if invoice.total_ttc is not None
        else None,
        f"payment {invoice.payment_method}" if invoice.payment_method else None,
    ]
    lines = [
        f"- {ln.description} x{ln.quantity} @ {ln.unit_price_ht} = {ln.total_ht}"
        for ln in invoice.lines
    ]
    return "\n".join([" | ".join(part for part in header if part), *lines])
