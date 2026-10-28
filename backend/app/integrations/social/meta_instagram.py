"""Instagram / Facebook social analytics adapter (official APIs, capability-driven)."""

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List

import httpx

from app.core.config import settings
from app.integrations.social.base import SocialAccount, SocialContent, SocialMetrics

logger = logging.getLogger(__name__)


class MetaInstagramProvider:
    provider = "META"
    platform = "INSTAGRAM"
    BASE_URL = "https://graph.facebook.com"

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=30.0)

    async def _ensure_token(self) -> str:
        if not settings.instagram_access_token:
            raise RuntimeError("INSTAGRAM_ACCESS_TOKEN not configured; use SOCIAL_PROVIDER_MODE=mock")
        return settings.instagram_access_token

    async def validate_connection(self, connection) -> Dict[str, Any]:
        token = await self._ensure_token()
        try:
            response = await self._client.get(
                f"{self.BASE_URL}/{settings.instagram_api_version}/me", params={"access_token": token, "fields": "id,name"}
            )
            body = response.json()
            if "error" in body:
                return {"ok": False, "status": "REAUTH_REQUIRED", "message": body["error"].get("message", "")}
            return {"ok": True, "status": "HEALTHY", "identity": body.get("id")}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "status": "UNKNOWN", "message": str(exc)}

    async def discover_accounts(self, connection) -> List[SocialAccount]:
        token = await self._ensure_token()
        accounts: List[SocialAccount] = []
        response = await self._client.get(
            f"{self.BASE_URL}/{settings.instagram_api_version}/me/accounts",
            params={"access_token": token, "fields": "id,name,username,link,access_token"},
        )
        for page in (response.json().get("data") or []):
            ig = await self._client.get(
                f"{self.BASE_URL}/{settings.instagram_api_version}/{page['id']}",
                params={"access_token": page.get("access_token", token), "fields": "id,username,name,profile_picture_url,biography"},
            ).json()
            accounts.append(
                SocialAccount(
                    external_account_id=ig.get("id", page["id"]),
                    platform="FACEBOOK",
                    username=ig.get("username") or page.get("username", ""),
                    display_name=ig.get("name") or page.get("name", ""),
                    account_type="FACEBOOK_PAGE",
                    avatar_url=ig.get("profile_picture_url"),
                    profile_url=page.get("link"),
                    external_parent_id=page.get("id"),
                )
            )
        return accounts

    async def get_account_profile(self, external_account_id: str) -> SocialAccount:
        token = await self._ensure_token()
        body = await self._client.get(
            f"{self.BASE_URL}/{settings.instagram_api_version}/{external_account_id}",
            params={"access_token": token, "fields": "id,username,name,profile_picture_url,biography,followers_count,media_count"},
        ).json()
        return SocialAccount(
            external_account_id=body.get("id", external_account_id),
            platform="INSTAGRAM",
            username=body.get("username", ""),
            display_name=body.get("name", ""),
            account_type="INSTAGRAM_BUSINESS",
            avatar_url=body.get("profile_picture_url"),
            followers=body.get("followers_count"),
            metadata={"media_count": body.get("media_count")},
        )

    async def get_account_metrics(self, external_account_id: str, start: date, end: date) -> List[Dict[str, Any]]:
        return []  # account-level aggregates are derived from content snapshots in the canonical layer

    async def list_content(self, external_account_id: str) -> List[SocialContent]:
        token = await self._ensure_token()
        fields = "id,caption,timestamp,media_type,media_url,permalink,thumbnail_url,duration"
        response = await self._client.get(
            f"{self.BASE_URL}/{settings.instagram_api_version}/{external_account_id}/media",
            params={"access_token": token, "fields": fields, "limit": 100},
        )
        content = []
        for media in (response.json().get("data") or []):
            content.append(
                SocialContent(
                    external_post_id=media["id"],
                    external_media_id=media["id"],
                    content_type=media.get("media_type", "VIDEO"),
                    caption=media.get("caption"),
                    published_at=datetime.fromisoformat(media["timestamp"].replace("Z", "+00:00")) if media.get("timestamp") else None,
                    public_url=media.get("permalink"),
                    thumbnail_uri=media.get("thumbnail_url") or media.get("media_url"),
                    duration=media.get("duration"),
                )
            )
        return content

    async def get_content_metrics(self, external_account_id: str, external_post_id: str, start: date, end: date) -> List[SocialMetrics]:
        token = await self._ensure_token()
        fields = "insights.metric(reach,views,likes,comments,shares,saved,profile_views,follows,total_interactions,plays),media_type"
        body = await self._client.get(
            f"{self.BASE_URL}/{settings.instagram_api_version}/{external_post_id}",
            params={"access_token": token, "fields": fields},
        ).json()
        insight_values = {}
        for insight in body.get("insights", {}).get("data", []):
            name = insight.get("name")
            values = insight.get("values") or []
            if values:
                insight_values[name] = values[-1].get("value")
        return [
            SocialMetrics(
                observed_at=datetime.now(timezone.utc),
                views=insight_values.get("plays") or insight_values.get("views"),
                reach=insight_values.get("reach"),
                likes=insight_values.get("likes"),
                comments=insight_values.get("comments"),
                shares=insight_values.get("shares"),
                saves=insight_values.get("saved"),
                profile_visits=insight_values.get("profile_views"),
                follows=insight_values.get("follows"),
                provider_native={"total_interactions": insight_values.get("total_interactions")},
            )
        ]

    async def get_capabilities(self, external_account_id: str) -> Dict[str, bool]:
        return {
            "ACCOUNT_PROFILE": True,
            "ACCOUNT_FOLLOWERS": True,
            "CONTENT_LIST": True,
            "CONTENT_VIEWS": True,
            "CONTENT_REACH": True,
            "CONTENT_LIKES": True,
            "CONTENT_COMMENTS": True,
            "CONTENT_SHARES": True,
            "CONTENT_SAVES": True,
            "CONTENT_WATCH_TIME": False,
            "CONTENT_SKIP_RATE": False,
            "PAID_CREATIVE_LINK": True,
            "ADS_READ": True,
        }
