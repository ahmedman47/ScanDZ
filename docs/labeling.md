# Labeling guideline (v1)

Goal: two people labeling the same invoice must write the same JSON.
Rule zero: **label what is printed on the page, not what it should be.**

## Header fields

| Field | Rule |
|---|---|
| `total_ttc` | The final amount the buyer must pay, including VAT and stamp duty (timbre). If several totals appear, take the last one before "Arrêtée la présente facture". Never the amount written in words. |
| `total_ht` | Total before VAT, after discounts. |
| `vat_amount` / `vat_rate` | As printed. If several rates, label the document-level total VAT and leave `vat_rate` null. |
| `timbre` | Only if a stamp-duty line is printed; otherwise null (not 0). |
| `invoice_number` | The whole printed string with prefix and year, e.g. `FA-2026/0012`. |
| `issue_date`, `due_date` | ISO date. Day first: 03/04/2026 is 3 April. Month names (French or Arabic) are converted. |
| `seller` | The issuer: letterhead, or the block labelled "Vendeur" / "Fournisseur". If logo and stamp disagree, follow the printed text block. |
| `buyer` | The block labelled "Client" / "Destinataire". |
| NIF, NIS, RC, AI | Keep digits only for NIF and NIS; RC and AI as printed. |

## Lines

- One gold line per product row.
- A description that wraps over two or more rows is **one** line; join the rows with a single space.
- Subtotal rows, discount rows, shipping notes and "Report" rows are not lines.
- Multi-page documents: lines from all pages; totals from the last page.

## Hard cases

- **Illegible or cut-off text:** leave the field null. Never guess, never infer from other fields.
- **Printed total is arithmetically wrong:** label the printed value anyway. The validator must catch it.
- **Not an invoice** (proforma, delivery note): set `document_type`, still extract what exists.
- **Amount formats:** decide by the printed format only (see ADR on amount parsing).

## Process

1. Label all documents once.
2. Re-check each document the next day, without looking at the first pass.
3. A friend labels 20 documents independently; compute field agreement; fix this guideline if a field is below 90%.
4. Record every change in the history below.

## History

- v1: first draft.
