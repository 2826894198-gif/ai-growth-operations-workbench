from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.integrations.base import ConnectionResult
from app.integrations.google_ads.client import GoogleAdsClient
from app.integrations.google_ads.gaql import GAQLQueryBuilder

logger = logging.getLogger(__name__)


def _field(row: Dict[str, Any], *path: str) -> Any:
    current: Any = row
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


class GoogleAdsProvider:
    provider = "GOOGLE_ADS"

    def __init__(self, client: Optional[GoogleAdsClient] = None):
        self._client = client or GoogleAdsClient()
        self._queries = GAQLQueryBuilder()

    async def validate_connection(self) -> ConnectionResult:
        try:
            rows = self._client.search("SELECT customer.id, customer.currency_code, customer.time_zone FROM customer")
            if not rows:
                return ConnectionResult(ok=False, checks={}, message="customer not found", error_code="PROVIDER_INVALID_ACCOUNT")
            row = rows[0]
            return ConnectionResult(
                ok=True,
                checks={"developer_token": True, "auth_valid": True, "customer_reachable": True},
                currency=_field(row, "customer", "currency_code"),
                timezone=_field(row, "customer", "time_zone"),
            )
        except Exception as exc:  # noqa: BLE001
            return ConnectionResult(ok=False, checks={}, message=str(exc), error_code=getattr(exc, "error_code", "PROVIDER_ERROR"))

    async def sync_accounts(self) -> List[Dict[str, Any]]:
        return [
            {
                "external_account_id": settings.google_ads_customer_id,
                "name": f"Google Ads {settings.google_ads_customer_id}",
                "currency": "USD",
                "timezone": "America/New_York",
            }
        ]

    async def sync_dimensions(self) -> Dict[str, List[Dict[str, Any]]]:
        queries = self._queries.dimensions()
        campaigns = [
            {
                "external_id": _field(r, "campaign", "id"),
                "name": _field(r, "campaign", "name"),
                "status": _field(r, "campaign", "status"),
                "channel_type": _field(r, "campaign", "advertising_channel_type"),
                "channel_sub_type": _field(r, "campaign", "advertising_channel_sub_type"),
                "start_time": _field(r, "campaign", "start_date"),
                "end_time": _field(r, "campaign", "end_date"),
            }
            for r in self._client.search(queries["campaigns"])
        ]
        ad_groups = [
            {
                "external_id": _field(r, "ad_group", "id"),
                "campaign_external_id": _field(r, "campaign", "id"),
                "name": _field(r, "ad_group", "name"),
                "status": _field(r, "ad_group", "status"),
            }
            for r in self._client.search(queries["ad_groups"])
        ]
        ads = [
            {
                "external_id": _field(r, "ad", "id"),
                "campaign_external_id": _field(r, "campaign", "id"),
                "ad_group_external_id": _field(r, "ad_group", "id"),
                "status": _field(r, "ad", "status"),
                "name": None,
            }
            for r in self._client.search(queries["ads"])
        ]
        keywords = [
            {
                "criterion_id": _field(r, "ad_group_criterion", "criterion_id"),
                "ad_group_external_id": _field(r, "ad_group", "id"),
                "keyword_text": _field(r, "ad_group_criterion", "keyword", "text"),
                "match_type": _field(r, "ad_group_criterion", "keyword", "match_type"),
            }
            for r in self._client.search(queries["keywords"])
        ]
        asset_groups = [
            {
                "external_id": _field(r, "asset_group", "id"),
                "campaign_external_id": _field(r, "campaign", "id"),
                "name": _field(r, "asset_group", "name"),
                "status": _field(r, "asset_group", "status"),
            }
            for r in self._client.search(queries["asset_groups"])
        ]
        conversion_actions = [
            {
                "id": _field(r, "conversion_action", "id"),
                "name": _field(r, "conversion_action", "name"),
            }
            for r in self._client.search(queries["conversion_actions"])
        ]
        return {
            "campaigns": campaigns,
            "ad_groups": ad_groups,
            "ads": ads,
            "keywords": keywords,
            "asset_groups": asset_groups,
            "conversion_actions": conversion_actions,
            "creatives": [],
            "search_terms": [],
            "products": [],
            "variants": [],
        }

    async def sync_performance(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for level, query in (
            ("CAMPAIGN", self._queries.campaign_daily(start_date, end_date)),
            ("AD_GROUP", self._queries.ad_group_daily(start_date, end_date)),
            ("AD", self._queries.ad_daily(start_date, end_date)),
        ):
            for r in self._client.search_stream(query):
                entity_id = _field(r, "campaign", "id") if level == "CAMPAIGN" else _field(r, "ad_group", "id") if level == "AD_GROUP" else _field(r, "ad", "id")
                rows.append(
                    {
                        "date": _field(r, "segments", "date"),
                        "entity_type": level,
                        "external_entity_id": entity_id,
                        "impressions": _field(r, "metrics", "impressions"),
                        "clicks": _field(r, "metrics", "clicks"),
                        "cost_micros": _field(r, "metrics", "cost_micros"),
                        "conversions": _field(r, "metrics", "conversions"),
                        "conversion_value": _field(r, "metrics", "conversions_value"),
                        "currency": "USD",
                    }
                )
        return rows

    async def sync_commerce(self, start_date: str, end_date: str) -> Dict[str, List[Dict[str, Any]]]:
        return {"orders": [], "order_items": [], "refunds": []}

    async def fetch_journey(self, external_order_id: str) -> Dict[str, Any]:
        return {"ready": False, "days_to_conversion": None}

    async def backfill(self, start_date: str, end_date: str) -> Dict[str, Any]:
        rows = await self.sync_performance(start_date, end_date)
        return {"records": len(rows)}
