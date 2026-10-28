from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional


def safe_divide(numerator: Optional[Decimal], denominator: Optional[Decimal]) -> Optional[Decimal]:
    """Return numerator/denominator or None (never Infinity)."""
    if numerator is None or denominator is None:
        return None
    try:
        denominator = Decimal(denominator)
    except InvalidOperation:
        return None
    if denominator == 0:
        return None
    try:
        return Decimal(numerator) / denominator
    except (InvalidOperation, ZeroDivisionError):
        return None


def to_decimal(value: Any) -> Optional[Decimal]:
    """Convert to Decimal; None stays None; 0 stays 0 (null vs zero preserved)."""
    if value is None:
        return None
    if value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def to_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def parse_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None


def parse_dt(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def require_field(payload: dict, field: str, context: dict) -> Optional[str]:
    """Return an API_SCHEMA_DRIFT message if a required field is missing."""
    if field not in payload or payload.get(field) is None:
        return f"required field '{field}' missing in {context}"
    return None


def dq_negative_spend(spend: Optional[Decimal], entity: str) -> Optional[dict]:
    if spend is not None and spend < 0:
        return {
            "rule_code": "DQ_NEGATIVE_SPEND",
            "severity": "ERROR",
            "message": f"negative spend {spend} for {entity}",
            "context": {"spend": str(spend)},
        }
    return None


def dq_impressions_lt_clicks(impressions: Optional[Decimal], clicks: Optional[Decimal], entity: str) -> Optional[dict]:
    if impressions is not None and clicks is not None and clicks > impressions:
        return {
            "rule_code": "DQ_IMPRESSIONS_LT_CLICKS",
            "severity": "ERROR",
            "message": f"clicks {clicks} > impressions {impressions} for {entity}",
            "context": {"impressions": str(impressions), "clicks": str(clicks)},
        }
    return None


def dq_unknown_currency(currency: Optional[str], entity: str) -> Optional[dict]:
    if currency and len(currency) != 3:
        return {
            "rule_code": "DQ_UNKNOWN_CURRENCY",
            "severity": "WARNING",
            "message": f"unexpected currency '{currency}' for {entity}",
            "context": {"currency": currency},
        }
    return None


def dq_refund_gt_order(refunded: Optional[Decimal], gross: Optional[Decimal], order: str) -> Optional[dict]:
    if refunded is not None and gross is not None and refunded > gross:
        return {
            "rule_code": "DQ_REFUND_GT_ORDER",
            "severity": "ERROR",
            "message": f"refund {refunded} > order gross {gross} for {order}",
            "context": {"refunded": str(refunded), "gross": str(gross)},
        }
    return None


def dq_order_total_invalid(
    total: Optional[Decimal], subtotal: Optional[Decimal], shipping: Optional[Decimal], tax: Optional[Decimal], discount: Optional[Decimal], order: str
) -> Optional[dict]:
    if None in (total, subtotal, shipping, tax, discount):
        return None
    # subtotal is already net of discounts; expected = subtotal + shipping + tax
    expected = subtotal + shipping + tax
    if abs(total - expected) > Decimal("0.02"):
        return {
            "rule_code": "DQ_ORDER_TOTAL_INVALID",
            "severity": "ERROR",
            "message": f"order {order} total {total} != subtotal+shipping+tax {expected}",
            "context": {"total": str(total), "expected": str(expected)},
        }
    return None
