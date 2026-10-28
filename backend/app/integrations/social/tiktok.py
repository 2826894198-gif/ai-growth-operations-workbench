"""TikTok Display API adapter (capability-driven, read + analytics)."""

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List

import httpx

from app.core.config import settings
from app.integrations.social.base import SocialAccount, SocialContent, SocialMetrics

logger = logging.getLogger(__name__)


class TikTokProvider:
    provider = "TIKTOK"
    platform = "TIKTOK"
    BASE_URL = "https://open.tiktokapis.com/v2"

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=30.0)

    async def _token(self) -> str:
        if not settings.tiktok_access_token:
            raise RuntimeError("TIKTOK_ACCESS_TOKEN not configured; use SOCIAL_PROVIDER_MODE=mock")
        return settings.tiktok_access_token

    async def validate_connection(self, connection) -> Dict[str, Any]:
        return {"ok": bool(settings.tiktok_access_token), "status": "HEALTHY" if settings.tiktok_access_token else "REAUTH_REQUIRED"}

    async def discover_accounts(self, connection) -> List[SocialAccount]:
        response = await self._client.get(
            f"{self.BASE_URL}/user/info/",
            params={"fields": "open_id,union_id,avatar_url,display_name,username"},
            headers={"Authorization": f"Bearer {await self._token()}"},
        )
        user = response.json().get("data", {}).get("user", {})
        return [
            SocialAccount(
                external_account_id=user.get("open_id", "tt_default"),
                platform="TIKTOK",
                username=user.get("username", ""),
                display_name=user.get("display_name", ""),
                account_type="TIKTOK_BUSINESS",
                avatar_url=user.get("avatar_url"),
            )
        ]

    async def get_account_profile(self, external_account_id: str) -> SocialAccount:
        return SocialAccount(external_account_id=external_account_id, platform="TIKTOK", username="", display_name="", account_type="TIKTOK_BUSINESS")

    async def get_account_metrics(self, external_account_id: str, start: date, end: date) -> List[Dict[str, Any]]:
        return []

    async def list_content(self, external_account_id: str) -> List[SocialContent]:
        response = await self._client.post(
            f"{self.BASE_URL}/video/list/",
            headers={"Authorization": f"Bearer {await self._token()}", "Content-Type": "application/json"},
            json={"max_count": 20, "fields": ["id", "title", "cover_image_url", "create_time", "duration"]},
        )
        videos = response.json().get("data", {}).get("videos", [])
        return [
            SocialContent(
                external_post_id=video["id"],
                external_media_id=video["id"],
                content_type="SHORT",
                caption=video.get("title"),
                published_at=datetime.fromtimestamp(video["create_time"], tz=timezone.utc) if video.get("create_time") else None,
                thumbnail_uri=(video.get("cover_image_url") or {}).get("url_list", [None])[0],
                duration=video.get("duration"),
            )
            for video in videos
        ]

    async def get_content_metrics(self, external_account_id: str, external_post_id: str, start: date, end: date) -> List[SocialMetrics]:
        response = await self._client.post(
            f"{self.BASE_URL}/video/data/",
            headers={"Authorization": f"Bearer {await self._token()}", "Content-Type": "application/json"},
            json={"fields": ["id", "view_count", "like_count", "comment_count", "share_count"], "filters": {"video_ids": [external_post_id]}},
        )
        video = (response.json().get("data", {}).get("videos") or [{}])[0]
        return [
            SocialMetrics(
                observed_at=datetime.now(timezone.utc),
                views=video.get("view_count"),
                likes=video.get("like_count"),
                comments=video.get("comment_count"),
                shares=video.get("share_count"),
            )
        ]

    async def get_capabilities(self, external_account_id: str) -> Dict[str, bool]:
        return {
            "ACCOUNT_PROFILE": True,
            "ACCOUNT_FOLLOWERS": True,
            "CONTENT_LIST": True,
            "CONTENT_VIEWS": True,
            "CONTENT_LIKES": True,
            "CONTENT_COMMENTS": True,
            "CONTENT_SHARES": True,
            "CONTENT_WATCH_TIME": False,
            "CONTENT_COMPLETION": False,
            "PAID_CREATIVE_LINK": False,
        }
