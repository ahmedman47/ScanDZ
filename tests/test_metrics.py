from datetime import date
from decimal import Decimal

import pytest

from wathiqa.domain.contract import Invoice, LineItem, Party
from wathiqa.eval.metrics import (
    Counts,
    aggregate,
    anls,
    cer,
    cluster_bootstrap_f1,
    document_exact,
    header_counts,
    line_counts,
    paired_bootstrap_delta,
    score_document,
    stp_at_precision,
    wer,
)

D = Decimal


def invoice() -> Invoice:
    return Invoice(
        invoice_number="FA-2026/0012",
        issue_date=date(2026, 1, 12),
        currency="DZD",
        seller=Party(name="SARL Alpha", nif="002016001234567"),
        total_ht=D(12000),
        vat_rate=D(19),
        vat_amount=D(2280),
        total_ttc=D(14280),
        lines=[
            LineItem(
                description="Papier A4", quantity=D(2), unit_price_ht=D(5000), total_ht=D(10000)
            ),
            LineItem(
                description="Toner noir", quantity=D(1), unit_price_ht=D(2000), total_ht=D(2000)
            ),
        ],
    )


def test_cer_wer_basics() -> None:
    assert cer("abc", "abd") == pytest.approx(1 / 3)
    assert cer("ABC", "abc") == 0
    assert cer("ABC", "abc", fold=False) == pytest.approx(1.0)
    assert wer("a b c d", "a b x d") == pytest.approx(0.25)
    assert cer("", "") == 0 and cer("", "x") == 1


def test_cer_ignores_arabic_spelling_variants_only_when_folding() -> None:
    assert cer("إلى", "الى") == 0
    assert cer("إلى", "الى", fold=False) > 0


def test_anls() -> None:
    assert anls("Papier A4", "papier a4") == 1.0
    assert anls("abcdef", "uvwxyz") == 0.0
    assert 0.5 < anls("Toner noir", "Toner noire") < 1.0


def test_perfect_document() -> None:
    doc = score_document(invoice(), invoice())
    assert document_exact(doc)
    assert header_counts(doc).fp == 0 and header_counts(doc).fn == 0


def test_wrong_value_counts_as_fp_and_fn() -> None:
    pred = invoice().model_copy(update={"total_ttc": D(14000)})
    doc = score_document(pred, invoice())
    assert doc["total_ttc"] == Counts(tp=0, fp=1, fn=1)
    assert not document_exact(doc)


def test_missing_is_fn_and_hallucinated_is_fp() -> None:
    missing = score_document(invoice().model_copy(update={"invoice_number": None}), invoice())
    assert missing["invoice_number"] == Counts(fn=1)
    extra = score_document(invoice().model_copy(update={"timbre": D(100)}), invoice())
    assert extra["timbre"] == Counts(fp=1)


def test_identifier_compared_by_digits_and_codes_by_squash() -> None:
    pred = invoice().model_copy(
        update={
            "invoice_number": "fa 2026-0012",
            "seller": Party(name="sarl alpha", nif="0020 1600 1234 567"),
        }
    )
    assert document_exact(score_document(pred, invoice()))


def test_lines_match_regardless_of_order() -> None:
    gold = invoice().lines
    assert line_counts(list(reversed(gold)), gold) == Counts(tp=2)


def test_line_with_wrong_amount_is_not_a_match() -> None:
    gold = invoice().lines
    pred = [gold[0], gold[1].model_copy(update={"total_ht": D(2500)})]
    assert line_counts(pred, gold) == Counts(tp=1, fp=1, fn=1)


def test_extra_and_missing_lines() -> None:
    gold = invoice().lines
    assert line_counts(gold[:1], gold) == Counts(tp=1, fn=1)
    assert line_counts([], gold) == Counts(fn=2)
    assert line_counts(gold, []) == Counts(fp=2)


def test_counts_algebra() -> None:
    c = Counts(tp=8, fp=2, fn=2)
    assert c.precision == 0.8 and c.recall == 0.8 and c.f1 == pytest.approx(0.8)
    assert Counts().f1 == 1.0
    total = aggregate([score_document(invoice(), invoice()), score_document(invoice(), invoice())])
    assert total["total_ttc"].tp == 2


def test_bootstrap_interval_contains_point_and_is_narrower_with_more_data() -> None:
    mixed = [Counts(tp=9, fp=1, fn=1)] * 10 + [Counts(tp=10)] * 10
    point, low, high = cluster_bootstrap_f1(mixed, n_boot=500, seed=1)
    assert low <= point <= high
    wider = cluster_bootstrap_f1(mixed[7:13], n_boot=500, seed=1)
    assert (wider[2] - wider[1]) > (high - low)
    assert cluster_bootstrap_f1([Counts(tp=5)] * 10, n_boot=200) == (1.0, 1.0, 1.0)


def test_bootstrap_is_reproducible() -> None:
    data = [Counts(tp=9, fp=1, fn=1)] * 8 + [Counts(tp=10)] * 4
    assert cluster_bootstrap_f1(data, seed=7) == cluster_bootstrap_f1(data, seed=7)


def test_paired_bootstrap_detects_a_real_difference_and_a_non_difference() -> None:
    better = [Counts(tp=10)] * 30
    worse = [Counts(tp=8, fp=2, fn=2)] * 30
    clear = paired_bootstrap_delta(better, worse, n_boot=500)
    assert clear.delta > 0 and clear.low > 0 and clear.prob_not_better == 0
    same = paired_bootstrap_delta(better, better, n_boot=500)
    assert same.delta == 0 and same.prob_not_better == 1
    with pytest.raises(ValueError):
        paired_bootstrap_delta(better, worse[:5])


def test_stp_curve() -> None:
    stp, threshold, precision = stp_at_precision(
        [0.99, 0.98, 0.97, 0.60, 0.50], [True, True, True, False, False], target=0.98
    )
    assert (stp, threshold, precision) == (0.6, 0.97, 1.0)
    none = stp_at_precision([0.9, 0.8], [False, False], target=0.98)
    assert none[0] == 0.0 and none[1] is None
