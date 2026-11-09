"""Evaluation metrics: OCR error rates, field-level extraction scores, line matching,
bootstrap confidence intervals and the straight-through-processing (STP) curve."""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import numpy as np
import numpy.typing as npt
from rapidfuzz.distance import Levenshtein
from scipy.optimize import linear_sum_assignment  # type: ignore[import-untyped]

from wathiqa.domain.contract import Invoice, LineItem
from wathiqa.domain.normalize import digits_only, normalize_text, squash

# Field name -> comparison kind. "amount" compares numbers, "digits" keeps digits only,
# "code" ignores case, spaces and punctuation, "text" compares normalised text.
FIELD_KINDS: dict[str, str] = {
    "invoice_number": "code",
    "issue_date": "date",
    "due_date": "date",
    "currency": "text",
    "seller.name": "text",
    "seller.nif": "digits",
    "seller.nis": "digits",
    "seller.rc": "code",
    "seller.ai": "digits",
    "buyer.name": "text",
    "buyer.nif": "digits",
    "total_ht": "amount",
    "vat_rate": "amount",
    "vat_amount": "amount",
    "timbre": "amount",
    "total_ttc": "amount",
    "payment_method": "text",
}
AMOUNT_TOLERANCE = Decimal("0.005")


# ------------------------------------------------------------------------- OCR
def _prepare(text: str, fold: bool) -> str:
    if fold:
        return normalize_text(text)
    return " ".join(unicodedata.normalize("NFKC", text).split())


def cer(reference: str, hypothesis: str, *, fold: bool = True) -> float:
    """Character error rate. ``fold=False`` keeps case and punctuation (strict)."""
    ref, hyp = _prepare(reference, fold), _prepare(hypothesis, fold)
    if not ref:
        return 0.0 if not hyp else 1.0
    return Levenshtein.distance(ref, hyp) / len(ref)


def wer(reference: str, hypothesis: str, *, fold: bool = True) -> float:
    """Word error rate on whitespace-separated tokens."""
    ref, hyp = _prepare(reference, fold).split(), _prepare(hypothesis, fold).split()
    if not ref:
        return 0.0 if not hyp else 1.0
    return Levenshtein.distance(ref, hyp) / len(ref)


def anls(prediction: str, truth: str, tau: float = 0.5) -> float:
    """Average normalised Levenshtein similarity (as used in DocVQA) for one pair."""
    a, b = normalize_text(prediction), normalize_text(truth)
    if not a and not b:
        return 1.0
    nl = Levenshtein.distance(a, b) / max(len(a), len(b))
    return 1.0 - nl if nl < tau else 0.0


# -------------------------------------------------------------------- field scores
@dataclass(frozen=True, slots=True)
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def __add__(self, other: Counts) -> Counts:
        return Counts(self.tp + other.tp, self.fp + other.fp, self.fn + other.fn)

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 1.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 1.0

    @property
    def f1(self) -> float:
        den = 2 * self.tp + self.fp + self.fn
        return 2 * self.tp / den if den else 1.0


def match_value(pred: Any, gold: Any, kind: str) -> bool:
    """Strict comparison after normalisation. A wrong value is never a partial match."""
    if kind == "amount":
        return abs(Decimal(pred) - Decimal(gold)) <= AMOUNT_TOLERANCE
    if kind == "date":
        return bool(pred == gold)
    if kind == "digits":
        return digits_only(str(pred)) == digits_only(str(gold))
    if kind == "code":
        return squash(str(pred)) == squash(str(gold))
    return normalize_text(str(pred)) == normalize_text(str(gold))


def flatten(invoice: Invoice) -> dict[str, Any]:
    """Header fields of an invoice as a flat dict keyed like ``seller.name``."""
    out: dict[str, Any] = {}
    for name in FIELD_KINDS:
        value: Any = invoice
        for part in name.split("."):
            value = getattr(value, part)
        out[name] = value if value != "" else None
    return out


def _amount_equal(a: Decimal | None, b: Decimal | None) -> bool:
    return a is not None and b is not None and abs(a - b) <= AMOUNT_TOLERANCE


def line_counts(pred: Sequence[LineItem], gold: Sequence[LineItem]) -> Counts:
    """Match predicted and true lines with the Hungarian algorithm, then count.

    A matched pair is a true positive when the amounts agree and the descriptions
    are similar (ANLS >= 0.5). Order and line splits therefore do not matter much.
    """
    if not pred or not gold:
        return Counts(fp=len(pred), fn=len(gold))
    sim = np.array(
        [
            [
                0.5 * _amount_equal(p.total_ht, g.total_ht)
                + 0.5 * anls(p.description or "", g.description or "")
                for g in gold
            ]
            for p in pred
        ]
    )
    rows, cols = linear_sum_assignment(-sim)
    tp = sum(
        1
        for r, c in zip(rows, cols, strict=True)
        if _amount_equal(pred[r].total_ht, gold[c].total_ht)
        and anls(pred[r].description or "", gold[c].description or "") >= 0.5
    )
    return Counts(tp=tp, fp=len(pred) - tp, fn=len(gold) - tp)


def score_document(pred: Invoice, gold: Invoice) -> dict[str, Counts]:
    """Per-field counts for one document, plus a ``lines`` entry."""
    p, g = flatten(pred), flatten(gold)
    result: dict[str, Counts] = {}
    for name, kind in FIELD_KINDS.items():
        pv, gv = p[name], g[name]
        if pv is None and gv is None:
            result[name] = Counts()
        elif pv is not None and gv is not None and match_value(pv, gv, kind):
            result[name] = Counts(tp=1)
        else:  # a wrong value is both a false positive and a false negative
            result[name] = Counts(fp=int(pv is not None), fn=int(gv is not None))
    result["lines"] = line_counts(pred.lines, gold.lines)
    return result


def aggregate(per_doc: Sequence[Mapping[str, Counts]]) -> dict[str, Counts]:
    """Sum counts over documents (micro-averaging), field by field."""
    total: dict[str, Counts] = {}
    for doc in per_doc:
        for name, counts in doc.items():
            total[name] = total.get(name, Counts()) + counts
    return total


def header_counts(doc: Mapping[str, Counts]) -> Counts:
    """Micro counts over header fields only (lines excluded)."""
    return sum((c for name, c in doc.items() if name != "lines"), Counts())


def document_exact(doc: Mapping[str, Counts]) -> bool:
    """True when every field and every line of the document is right."""
    return all(c.fp == 0 and c.fn == 0 for c in doc.values())


# ---------------------------------------------------------------------- statistics
def _f1(tp: npt.ArrayLike, fp: npt.ArrayLike, fn: npt.ArrayLike) -> npt.NDArray[np.float64]:
    tp_, fp_, fn_ = (np.asarray(x, dtype=float) for x in (tp, fp, fn))
    den = 2 * tp_ + fp_ + fn_
    return np.where(den > 0, 2 * tp_ / np.maximum(den, 1), 1.0)


def _arrays(per_doc: Sequence[Counts]) -> tuple[npt.NDArray[Any], ...]:
    return tuple(
        np.array([getattr(c, k) for c in per_doc], dtype=float) for k in ("tp", "fp", "fn")
    )


def cluster_bootstrap_f1(
    per_doc: Sequence[Counts], *, n_boot: int = 2000, seed: int = 0, alpha: float = 0.05
) -> tuple[float, float, float]:
    """Micro F1 with a percentile bootstrap interval. Resampling whole documents keeps
    the fields of one document together (they are not independent of each other)."""
    if not per_doc:
        raise ValueError("no documents")
    tp, fp, fn = _arrays(per_doc)
    point = float(_f1(tp.sum(), fp.sum(), fn.sum()))
    idx = np.random.default_rng(seed).integers(0, len(per_doc), size=(n_boot, len(per_doc)))
    samples = _f1(tp[idx].sum(axis=1), fp[idx].sum(axis=1), fn[idx].sum(axis=1))
    low, high = np.quantile(samples, [alpha / 2, 1 - alpha / 2])
    return point, float(low), float(high)


@dataclass(frozen=True, slots=True)
class PairedResult:
    delta: float  # F1(a) - F1(b)
    low: float
    high: float
    prob_not_better: float  # share of resamples where a is not better than b


def paired_bootstrap_delta(
    a: Sequence[Counts],
    b: Sequence[Counts],
    *,
    n_boot: int = 2000,
    seed: int = 0,
    alpha: float = 0.05,
) -> PairedResult:
    """Compare two systems scored on the *same* documents."""
    if len(a) != len(b) or not a:
        raise ValueError("both systems must be scored on the same, non-empty document set")
    ta, fa, na = _arrays(a)
    tb, fb, nb = _arrays(b)
    point = float(_f1(ta.sum(), fa.sum(), na.sum()) - _f1(tb.sum(), fb.sum(), nb.sum()))
    idx = np.random.default_rng(seed).integers(0, len(a), size=(n_boot, len(a)))
    delta = _f1(ta[idx].sum(1), fa[idx].sum(1), na[idx].sum(1)) - _f1(
        tb[idx].sum(1), fb[idx].sum(1), nb[idx].sum(1)
    )
    low, high = np.quantile(delta, [alpha / 2, 1 - alpha / 2])
    return PairedResult(point, float(low), float(high), float((delta <= 0).mean()))


def stp_at_precision(
    confidences: Sequence[float], correct: Sequence[bool], target: float = 0.98
) -> tuple[float, float | None, float]:
    """Largest share of documents that can be auto-accepted while the precision of the
    accepted set stays >= ``target``. Returns (stp, confidence threshold, precision)."""
    conf = np.asarray(confidences, dtype=float)
    ok = np.asarray(correct, dtype=bool)
    best: tuple[float, float | None, float] = (0.0, None, float("nan"))
    for threshold in np.unique(conf)[::-1]:
        accepted = conf >= threshold
        precision = float(ok[accepted].mean())
        stp = float(accepted.sum() / len(conf))
        if precision >= target and stp > best[0]:
            best = (stp, float(threshold), precision)
    return best
