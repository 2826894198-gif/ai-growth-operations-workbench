from typing import Any, Dict, List

from app.etl.validators import parse_dt, to_decimal

PLATFORM = "SHOPIFY"


def map_product(raw: Dict[str, Any], data_source_id: str) -> Dict[str, Any]:
    return {
        "data_source_id": data_source_id,
        "external_product_id": str(raw.get("external_id")),
        "title": raw.get("title"),
        "handle": raw.get("handle"),
        "vendor": raw.get("vendor"),
        "product_type": raw.get("product_type"),
        "status": raw.get("status"),
        "source_created_at": parse_dt(raw.get("created_at")),
        "source_updated_at": parse_dt(raw.get("updated_at")),
        "raw_metadata": raw,
    }


def map_variant(raw: Dict[str, Any], data_source_id: str, product_id: str) -> Dict[str, Any]:
    return {
        "product_id": product_id,
        "data_source_id": data_source_id,
        "external_variant_id": str(raw.get("external_id")),
        "external_product_id": str(raw.get("product_external_id")),
        "sku": raw.get("sku"),
        "title": raw.get("title"),
        "price": to_decimal(raw.get("price")),
        "compare_at_price": to_decimal(raw.get("compare_at_price")),
        "inventory_item_id": raw.get("inventory_item_id"),
    }


def _journey_fields(side: Dict[str, Any], prefix: str) -> Dict[str, Any]:
    side = side or {}
    return {
        f"{prefix}_source": side.get("source"),
        f"{prefix}_landing_page": side.get("landing_page"),
        f"{prefix}_referrer_url": side.get("referrer_url"),
        f"{prefix}_utm_source": side.get("utm_source"),
        f"{prefix}_utm_medium": side.get("utm_medium"),
        f"{prefix}_utm_campaign": side.get("utm_campaign"),
        f"{prefix}_utm_content": side.get("utm_content"),
        f"{prefix}_utm_term": side.get("utm_term"),
    }


def map_journey(raw: Dict[str, Any]) -> Dict[str, Any]:
    first = _journey_fields(raw.get("first"), "first")
    last = _journey_fields(raw.get("last"), "last")
    return {
        "journey_ready": bool(raw.get("ready", False)),
        "days_to_conversion": to_decimal(raw.get("days_to_conversion")),
        **first,
        **last,
        "journey_state": "READY" if raw.get("ready") else "RETRY",
        "fetched_at": parse_dt(raw.get("fetched_at")),
        "raw_metadata": raw,
    }


def map_commerce(
    data_source_id: str,
    orders: List[Dict[str, Any]],
    order_items: List[Dict[str, Any]],
    refunds: List[Dict[str, Any]],
    product_map: Dict[str, str],
    variant_map: Dict[str, str],
    order_map: Dict[str, str],
    sync_job_id: str,
) -> Dict[str, List[Dict[str, Any]]]:
    order_rows = []
    item_rows = []
    refund_rows = []
    for raw in orders:
        gross = to_decimal(raw.get("total"))
        refunded = to_decimal(raw.get("refunded_amount")) or sum(
            to_decimal(r.get("amount")) or 0 for r in refunds if r.get("order_external_id") == raw.get("external_id")
        )
        net = gross - refunded if gross is not None else None
        order_rows.append(
            {
                "data_source_id": data_source_id,
                "external_order_id": str(raw.get("external_id")),
                "order_name": raw.get("name"),
                "order_created_at": parse_dt(raw.get("created_at")),
                "order_updated_at": parse_dt(raw.get("updated_at")),
                "financial_status": raw.get("financial_status"),
                "fulfillment_status": raw.get("fulfillment_status"),
                "currency": raw.get("currency"),
                "subtotal_amount": to_decimal(raw.get("subtotal")),
                "discount_amount": to_decimal(raw.get("discount")),
                "shipping_amount": to_decimal(raw.get("shipping")),
                "tax_amount": to_decimal(raw.get("tax")),
                "gross_amount": gross,
                "current_total_amount": gross,
                "refunded_amount": refunded,
                "net_revenue_amount": net,
                "cancelled_at": parse_dt(raw.get("cancelled_at")),
                "source_name": raw.get("source_name"),
                "provider_customer_id_hash": raw.get("customer_id_hash"),
                "raw_metadata": raw,
                "sync_job_id": sync_job_id,
            }
        )

    for raw in order_items:
        order_external_id = raw.get("order_external_id")
        item_rows.append(
            {
                "order_id": order_map.get(order_external_id),
                "data_source_id": data_source_id,
                "external_line_item_id": str(raw.get("line_item_id")),
                "product_id": product_map.get(str(raw.get("product_external_id"))),
                "variant_id": variant_map.get(str(raw.get("variant_external_id"))),
                "sku": raw.get("sku"),
                "title": raw.get("title"),
                "quantity": to_decimal(raw.get("quantity")),
                "unit_price": to_decimal(raw.get("unit_price")),
                "line_discount": to_decimal(raw.get("line_discount")),
                "line_total": to_decimal(raw.get("line_total")),
                "raw_metadata": raw,
            }
        )

    for raw in refunds:
        refund_rows.append(
            {
                "order_id": order_map.get(raw.get("order_external_id")),
                "data_source_id": data_source_id,
                "external_refund_id": str(raw.get("refund_id")),
                "refund_created_at": parse_dt(raw.get("created_at")),
                "refund_amount": to_decimal(raw.get("amount")),
                "currency": raw.get("currency", "USD"),
                "reason": raw.get("reason"),
                "raw_metadata": raw,
            }
        )
    return {"orders": order_rows, "order_items": item_rows, "refunds": refund_rows}
