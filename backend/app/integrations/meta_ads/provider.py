from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.core.config import settings
from app.integrations.base import ConnectionResult
from app.integrations.meta_ads.client import MetaClient

logger = logging.getLogger(__name__)


class MetaProvider:
    provider = "META_ADS"

    def __init__(self, client: MetaClient | None = None):
        self._client = client or MetaClient()

    async def validate_connection(self) -> ConnectionResult:
        try:
            account = await self._client.get_ad_account()
            return ConnectionResult(
                ok=True,
                checks={
                    "api_reachable": True,
                    "token_valid": True,
                    "ad_account_accessible": True,
                },
                currency=account.get("currency"),
                timezone=account.get("timezone"),
            )
        except Exception as exc:  # noqa: BLE001
            return ConnectionResult(ok=False, checks={}, message=str(exc), error_code="PROVIDER_AUTH_FAILED")

    async def sync_accounts(self) -> List[Dict[str, Any]]:
        return [await self._client.get_ad_account()]

    async def sync_dimensions(self) -> Dict[str, List[Dict[str, Any]]]:
        campaigns = await self._client.get_campaigns()
        ad_groups = await self._client.get_adsets()
        ads = await self._client.get_ads()
        creatives = await self._client.get_creatives()
        return {"campaigns": campaigns, "ad_groups": ad_groups, "ads": ads, "creatives": creatives}

    async def sync_performance(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for level in ("campaign", "adset", "ad"):
            insights = await self._client.get_insights(start_date, end_date, level=level)
            for item in insights:
                entity_key = "campaign_id" if level == "campaign" else "adset_id" if level == "adset" else "ad_id"
                rows.append(
                    {
                        "date": item.get("date_start"),
                        "entity_type": level.upper(),
                        "external_entity_id": item.get(entity_key),
                        "impressions": item.get("impressions"),
                        "reach": item.get("reach"),
                        "frequency": item.get("frequency"),
                        "clicks": item.get("clicks"),
                        "inline_link_clicks": item.get("inline_link_clicks"),
                        "outbound_clicks": item.get("outbound_clicks"),
                        "spend": item.get("spend"),
                        "cpm": item.get("cpm"),
                        "cpc": item.get("cpc"),
                        "ctr": item.get("ctr"),
                        "actions": item.get("actions"),
                        "action_values": item.get("action_values"),
                        "cost_per_action_type": item.get("cost_per_action_type"),
                        "purchase_roas": item.get("purchase_roas"),
                        "currency": settings.reporting_currency,
                        "attribution_setting": "default",
                        "breakdowns": {},
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
