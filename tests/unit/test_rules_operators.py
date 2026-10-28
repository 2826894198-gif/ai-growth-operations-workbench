from decimal import Decimal

from app.rules.operators import evaluate_operator


def test_comparisons():
    assert evaluate_operator("eq", 0, 0) is True
    assert evaluate_operator("neq", 0, 1) is True
    assert evaluate_operator("gt", 5, 3) is True
    assert evaluate_operator("gte", 5, 5) is True
    assert evaluate_operator("lt", 2, 3) is True
    assert evaluate_operator("lte", 2, 2) is True


def test_between_and_null():
    assert evaluate_operator("between", 5, [1, 10]) is True
    assert evaluate_operator("between", 11, [1, 10]) is False
    assert evaluate_operator("is_null", None) is True
    assert evaluate_operator("not_null", 1) is True
    assert evaluate_operator("not_null", None) is False


def test_target_multiple():
    assert evaluate_operator("target_multiple_gte", 60.0, None, 30.0, 2.0) is True
    assert evaluate_operator("target_multiple_gt", 59.0, None, 30.0, 2.0) is False
    assert evaluate_operator("target_multiple_lt", 50.0, None, 30.0, 2.0) is True


def test_null_metric_never_passes_comparison():
    assert evaluate_operator("gt", None, 1) is False
    assert evaluate_operator("target_multiple_gte", None, None, 30.0, 2.0) is False


def test_zero_denominator_safe():
    assert evaluate_operator("ratio_gt", Decimal(1), 0) is False
    assert evaluate_operator("zscore_gt", 3.0, 2.5) is True
