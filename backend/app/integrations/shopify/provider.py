from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.integrations.base import ConnectionResult
from app.integrations.shopify.client import ShopifyClient
from app.integrations.shopify.graphql import JOURNEY_QUERY, ORDERS_QUERY, PRODUCTS_QUERY, SHOP_QUERY

logger = logging.getLogger(__name__)


class ShopifyProvider:
    provider = "SHOPIFY"

    def __init__(self, client: ShopifyClient | None = None):
        self._client = client or ShopifyClient()

    async def validate_connection(self) -> ConnectionResult:
        try:
            data = await self._client.graphql(SHOP_QUERY)
            shop = data.get("shop") or {}
            return ConnectionResult(
                ok=True,
                checks={"graphql_reachable": True, "token_valid": True, "shop_accessible": True},
                currency=shop.get("currencyCode"),
                timezone=shop.get("timezoneAbbreviation"),
            )
        except Exception as exc:  # noqa: BLE001
            return ConnectionResult(ok=False, checks={}, message=str(exc), error_code="PROVIDER_AUTH_FAILED")

    async def sync_accounts(self) -> List[Dict[str, Any]]:
        data = await self._client.graphql(SHOP_QUERY)
        shop = data.get("shop") or {}
        return [
            {
                "external_account_id": shop.get("name") or self._client._shop,
                "name": shop.get("name"),
                "currency": shop.get("currencyCode"),
                "timezone": shop.get("timezoneAbbreviation"),
            }
        ]

    async def sync_dimensions(self) -> Dict[str, List[Dict[str, Any]]]:
        product_nodes = await self._client.paginate_connection(
            PRODUCTS_QUERY, ["products"], {"updatedAfter": "1990-01-01T00:00:00Z"}
        )
        products = []
        variants = []
        for node in product_nodes:
            products.append(
                {
                    "external_id": node.get("id"),
                    "title": node.get("title"),
                    "handle": node.get("handle"),
                    "vendor": node.get("vendor"),
                    "product_type": node.get("productType"),
                    "status": node.get("status"),
                    "created_at": node.get("createdAt"),
                    "updated_at": node.get("updatedAt"),
                }
            )
            for edge in (node.get("variants") or {}).get("edges", []):
                variant = edge.get("node") or {}
                inventory = variant.get("inventoryItem") or {}
                variants.append(
                    {
                        "external_id": variant.get("id"),
                        "product_external_id": node.get("id"),
                        "sku": variant.get("sku"),
                        "title": variant.get("title"),
                        "price": variant.get("price"),
                        "compare_at_price": variant.get("compareAtPrice"),
                        "inventory_item_id": inventory.get("id"),
                    }
                )
        return {
            "products": products,
            "variants": variants,
            "campaigns": [],
            "ad_groups": [],
            "ads": [],
            "creatives": [],
            "keywords": [],
            "search_terms": [],
            "conversion_actions": [],
            "asset_groups": [],
        }

    def _order_to_staging(self, node: Dict[str, Any]) -> Dict[str, Any]:
        money = lambda path: ((node.get(path) or {}).get("shopMoney") or {}).get("amount")  # noqa: E731
        items = []
        for edge in (node.get("lineItems") or {}).get("edges", []):
            item = edge.get("node") or {}
            variant = item.get("variant") or {}
            product = variant.get("product") or {}
            items.append(
                {
                    "line_item_id": item.get("id"),
                    "product_external_id": product.get("id"),
                    "variant_external_id": variant.get("id"),
                    "sku": item.get("sku"),
                    "title": item.get("title"),
                    "quantity": item.get("quantity"),
                    "unit_price": ((item.get("unitPriceSet") or {}).get("shopMoney") or {}).get("amount"),
                    "line_discount": 0,
                    "line_total": None,
                }
            )
        refunds = []
        for edge in (node.get("refunds") or {}).get("edges", []):
            refund = edge.get("node") or {}
            refunds.append(
                {
                    "refund_id": refund.get("id"),
                    "created_at": refund.get("createdAt"),
                    "amount": ((refund.get("totalRefundedSet") or {}).get("shopMoney") or {}).get("amount"),
                    "reason": None,
                }
            )
        customer = node.get("customer") or {}
        return {
            "external_id": node.get("id"),
            "name": node.get("name"),
            "created_at": node.get("createdAt"),
            "updated_at": node.get("updatedAt"),
            "financial_status": node.get("displayFinancialStatus"),
            "fulfillment_status": node.get("displayFulfillmentStatus"),
            "currency": node.get("currencyCode"),
            "subtotal": money("subtotalPriceSet"),
            "shipping": money("totalShippingPriceSet"),
            "tax": money("totalTaxSet"),
            "discount": money("totalDiscountsSet"),
            "total": money("currentTotalPriceSet"),
            "cancelled_at": node.get("cancelledAt"),
            "source_name": node.get("sourceName"),
            "customer_id_hash": customer.get("id"),
            "items": items,
            "refunds": refunds,
        }

    async def sync_commerce(self, start_date: str, end_date: str) -> Dict[str, List[Dict[str, Any]]]:
        order_nodes = await self._client.paginate_connection(
            ORDERS_QUERY,
            ["orders"],
            {"updatedAfter": f"{start_date}T00:00:00Z", "updatedBefore": f"{end_date}T23:59:59Z"},
        )
        orders = []
        items = []
        refunds = []
        for node in order_nodes:
            order = self._order_to_staging(node)
            orders.append(order)
            for item in order["items"]:
                items.append({"order_external_id": order["external_id"], **item})
            for refund in order["refunds"]:
                refunds.append({"order_external_id": order["external_id"], **refund})
        return {"orders": orders, "order_items": items, "refunds": refunds}

    async def fetch_journey(self, external_order_id: str) -> Dict[str, Any]:
        data = await self._client.graphql(JOURNEY_QUERY, {"orderId": external_order_id})
        order = data.get("order") or {}
        journey = order.get("customerJourneySummary") or {}

        def side(visit: Dict[str, Any]) -> Dict[str, Any]:
            utm = visit.get("utmParameters") or {}
            return {
                "source": visit.get("source"),
                "landing_page": visit.get("landingPage"),
                "referrer_url": visit.get("referrerUrl"),
                "utm_source": utm.get("source"),
                "utm_medium": utm.get("medium"),
                "utm_campaign": utm.get("campaign"),
                "utm_content": utm.get("content"),
                "utm_term": utm.get("term"),
            }

        return {
            "order_external_id": external_order_id,
            "ready": bool(journey.get("ready")),
            "days_to_conversion": journey.get("daysToConversion"),
            "first": side(journey.get("firstVisit") or {}),
            "last": side(journey.get("lastVisit") or {}),
        }

    async def backfill(self, start_date: str, end_date: str) -> Dict[str, Any]:
        # Live Shopify backfill uses Bulk Operations (see client.run_bulk_operation).
        return {"method": "bulk_operations", "status": "IMPLEMENTED_READY"}
