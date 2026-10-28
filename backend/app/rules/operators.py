from decimal import Decimal
from typing import Any, Optional

from app.etl.validators import safe_divide


def _to_number(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001
        return None


def evaluate_operator(
    operator: str,
    metric_value: Any,
    condition_value: Any = None,
    target_value: Any = None,
    multiple: Optional[float] = None,
) -> bool:
    """Deterministic DSL operator evaluation. No arbitrary Python allowed."""
    if operator == "is_null":
        return metric_value is None
    if operator == "not_null":
        return metric_value is not None

    if operator in ("eq", "neq"):
        equal = metric_value == condition_value
        return equal if operator == "eq" else not equal

    if operator == "between":
        lo, hi = condition_value
        return _to_number(metric_value) is not None and lo <= float(metric_value) <= hi

    number = _to_number(metric_value)
    if number is None:
        return False

    if operator == "gt":
        other = _to_number(condition_value) if condition_value is not None else _to_number(target_value)
        return other is not None and number > other
    if operator == "gte":
        other = _to_number(condition_value) if condition_value is not None else _to_number(target_value)
        return other is not None and number >= other
    if operator == "lt":
        other = _to_number(condition_value) if condition_value is not None else _to_number(target_value)
        return other is not None and number < other
    if operator == "lte":
        other = _to_number(condition_value) if condition_value is not None else _to_number(target_value)
        return other is not None and number <= other

    if operator in ("percent_change_gt", "percent_change_lt"):
        threshold = _to_number(condition_value)
        if threshold is None:
            return False
        return number > threshold if operator.endswith("_gt") else number < threshold

    if operator in ("ratio_gt", "ratio_lt"):
        ratio = safe_divide(number, _to_number(condition_value))
        return ratio is not None and (ratio > 1 if operator.endswith("_gt") else ratio < 1)

    if operator in ("target_multiple_gt", "target_multiple_gte", "target_multiple_lt", "target_multiple_lte"):
        target = _to_number(target_value)
        multiplier = Decimal(str(multiple or 1))
        if target is None:
            return False
        threshold = target * multiplier
        if operator.endswith("_gt"):
            return number > threshold
        if operator.endswith("_gte"):
            return number >= threshold
        if operator.endswith("_lt"):
            return number < threshold
        return number <= threshold

    if operator in ("zscore_gt", "zscore_lt"):
        threshold = _to_number(condition_value)
        return number > threshold if operator.endswith("_gt") else number < threshold

    raise ValueError(f"unsupported operator: {operator}")
