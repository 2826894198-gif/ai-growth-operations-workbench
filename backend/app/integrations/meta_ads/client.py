import logging
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.integrations.meta_ads.exceptions import ProviderTimeout, map_meta_error
from app.integrations.meta_ads.rate_limit import MetaRateLimiter

logger = logging.getLogger(__name__)


class MetaClient:
    """Read-only Meta Marketing API client (Graph API)."""

    BASE_URL = "https://graph.facebook.com"

    CAMPAIGN_FIELDS = "id,name,status,effective_status,objective,buying_type,created_time,updated_time,start_time,stop_time"
    ADSET_FIELDS = (
        "id,campaign_id,name,status,effective_status,optimization_goal,billing_event,"
        "daily_budget,lifetime_budget,start_time,end_time,targeting"
    )
    AD_FIELDS = "id,campaign_id,adset_id,name,status,effective_status,creative,created_time,updated_time"
    CREATIVE_FIELDS = (
        "id,name,object_type,title,body,thumbnail_url,image_url,video_id,"
        "call_to_action,url_tags,landing_page_url"
    )
    INSIGHT_FIELDS = (
        "date_start,date_stop,account_id,campaign_id,adset_id,ad_id,"
        "impressions,reach,frequency,clicks,inline_link_clicks,outbound_clicks,"
        "spend,cpm,cpc,ctr,actions,action_values,cost_per_action_type,purchase_roas"
    )

    def __init__(self):
        self._limiter = MetaRateLimiter()
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))

    async def aclose(self) -> None:
        await self._client.aclose()

    def _url(self, path: str) -> str:
        return f"{self.BASE_URL}/{settings.meta_graph_api_version}/{path}"

    async def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        params = {**params, "access_token": settings.meta_access_token}
        async with self._limiter:
            try:
                response = await self._client.get(self._url(path), params=params)
            except httpx.TimeoutException as exc:
                raise ProviderTimeout(str(exc)) from exc
            except httpx.HTTPError as exc:
                raise ProviderTimeout(str(exc)) from exc
        body = response.json()
        if "error" in body:
            raise map_meta_error(body["error"])
        return body

    async def _paginate(self, path: str, params: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        after: Optional[str] = None
        for _ in range(100):
            page_params = {**params, "limit": limit}
            if after:
                page_params["after"] = after
            body = await self._get(path, page_params)
            data = body.get("data") or []
            items.extend(data)
            cursors = (body.get("paging") or {}).get("cursors") or {}
            after = cursors.get("after")
            if not after:
                break
        return items

    async def get_ad_account(self) -> Dict[str, Any]:
        account_id = settings.meta_ad_account_id
        body = await self._get(f"act_{account_id}", {"fields": "name,currency,timezone_name"})
        return {
            "external_account_id": f"act_{account_id}",
            "name": body.get("name"),
            "currency": body.get("currency"),
            "timezone": body.get("timezone_name"),
        }

    async def get_campaigns(self) -> List[Dict[str, Any]]:
        return await self._paginate(f"act_{settings.meta_ad_account_id}/campaigns", {"fields": self.CAMPAIGN_FIELDS})

    async def get_adsets(self) -> List[Dict[str, Any]]:
        return await self._paginate(f"act_{settings.meta_ad_account_id}/adsets", {"fields": self.ADSET_FIELDS})

    async def get_ads(self) -> List[Dict[str, Any]]:
        ads = await self._paginate(f"act_{settings.meta_ad_account_id}/ads", {"fields": self.AD_FIELDS})
        out = []
        for ad in ads:
            creative = ad.pop("creative", None) or {}
            out.append(
                {
                    "external_id": ad.get("id"),
                    "campaign_external_id": ad.get("campaign_id"),
                    "ad_group_external_id": ad.get("adset_id"),
                    "name": ad.get("name"),
                    "status": ad.get("status"),
                    "effective_status": ad.get("effective_status"),
                    "creative_id": creative.get("id"),
                    "created_time": ad.get("created_time"),
                    "updated_time": ad.get("updated_time"),
                }
            )
        return out

    async def get_creatives(self) -> List[Dict[str, Any]]:
        return await self._paginate(f"act_{settings.meta_ad_account_id}/adcreatives", {"fields": self.CREATIVE_FIELDS})

    async def get_insights(
        self,
        start_date: str,
        end_date: str,
        level: str = "ad",
        breakdowns: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {
            "fields": self.INSIGHT_FIELDS,
            "level": level,
            "time_range": {"since": start_date, "until": end_date},
            "time_increment": 1,
            "limit": 100,
        }
        if breakdowns:
            params["breakdowns"] = breakdowns
        return await self._paginate(f"act_{settings.meta_ad_account_id}/insights", params)
