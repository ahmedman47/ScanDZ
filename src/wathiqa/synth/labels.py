"""Printed labels per language. The model must learn that these all mean the same field."""

from __future__ import annotations

_FR = {
    "title_invoice": "FACTURE", "title_proforma": "FACTURE PROFORMA", "number": "N°",
    "date": "Date", "due": "Échéance", "payment": "Mode de paiement",
    "seller": "Fournisseur", "buyer": "Client", "designation": "Désignation", "qty": "Qté",
    "unit_price": "P.U. HT", "amount": "Montant HT", "total_ht": "Total HT", "vat": "TVA",
    "timbre": "Droit de timbre", "total_ttc": "Total TTC",
    "words": "Arrêtée la présente facture à la somme de", "unit": "DA",
    "nif": "NIF", "nis": "NIS", "rc": "RC", "ai": "AI", "stamp": "Cachet et signature",
}  # fmt: skip
_AR = {
    "title_invoice": "فاتورة", "title_proforma": "فاتورة شكلية", "number": "رقم",
    "date": "التاريخ", "due": "تاريخ الاستحقاق", "payment": "طريقة الدفع",
    "seller": "البائع", "buyer": "الزبون", "designation": "البيان", "qty": "الكمية",
    "unit_price": "سعر الوحدة", "amount": "المبلغ", "total_ht": "المجموع خارج الرسم",
    "vat": "الرسم على القيمة المضافة", "timbre": "حقوق الطابع", "total_ttc": "المجموع مع الرسم",
    "words": "أوقفت هذه الفاتورة عند مبلغ", "unit": "دج",
    "nif": "رقم التعريف الجبائي", "nis": "رقم التعريف الإحصائي", "rc": "السجل التجاري",
    "ai": "رقم المادة", "stamp": "الختم والإمضاء",
}  # fmt: skip
_EN = {
    "title_invoice": "INVOICE", "title_proforma": "PROFORMA INVOICE", "number": "No.",
    "date": "Date", "due": "Due date", "payment": "Payment method",
    "seller": "Seller", "buyer": "Bill to", "designation": "Description", "qty": "Qty",
    "unit_price": "Unit price (excl. VAT)", "amount": "Amount (excl. VAT)",
    "total_ht": "Total excl. VAT", "vat": "VAT", "timbre": "Stamp duty",
    "total_ttc": "Total incl. VAT", "words": "Total amount of this invoice:", "unit": "DZD",
    "nif": "Tax ID (NIF)", "nis": "Statistical ID (NIS)", "rc": "Trade register (RC)",
    "ai": "Tax article (AI)", "stamp": "Stamp and signature",
}  # fmt: skip
# Bilingual: "French / Arabic" side by side.
_BI = {k: f"{_FR[k]} / {_AR[k]}" for k in _FR}
_BI["unit"] = "دج"
_BI["title_invoice"] = "FACTURE / فاتورة"
_BI["title_proforma"] = "PROFORMA / فاتورة شكلية"
_BI["number"] = "N° / رقم"

LABELS = {"fr": _FR, "ar": _AR, "en": _EN, "bi": _BI}
