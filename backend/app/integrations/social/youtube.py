"""YouTube Analytics / Reporting API adapter."""

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List

import httpx

from app.core.config import settings
from app.integrations.social.base import SocialAccount, SocialContent, SocialMetrics

logger = logging.getLogger(__name__)


class YouTubeProvider:
    provider = "YOUTUBE"
    platform = "YOUTUBE"
    BASE_URL = "https://youtube.googleapis.com/youtube/v3"

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=30.0)

    async def _key(self) -> str:
        if not settings.youtube_api_key:
            raise RuntimeError("YOUTUBE_API_KEY not configured; use SOCIAL_PROVIDER_MODE=mock")
        return settings.youtube_api_key

    async def validate_connection(self, connection) -> Dict[str, Any]:
        return {"ok": bool(settings.youtube_api_key), "status": "HEALTHY" if settings.youtube_api_key else "REAUTH_REQUIRED"}

    async def discover_accounts(self, connection) -> List[SocialAccount]:
        return []  # channel discovery requires channel IDs from the app configuration

    async def get_account_profile(self, external_account_id: str) -> SocialAccount:
        body = await self._client.get(
            f"{self.BASE_URL}/channels",
            params={"part": "snippet,statistics", "id": external_account_id, "key": await self._key()},
        ).json()
        item = (body.get("items") or [{}])[0]
        snippet = item.get("snippet", {})
        return SocialAccount(
            external_account_id=external_account_id,
            platform="YOUTUBE",
            username=snippet.get("customUrl", "").lstrip("@"),
            display_name=snippet.get("title", ""),
            account_type="YOUTUBE_CHANNEL",
            avatar_url=snippet.get("thumbnails", {}).get("default", {}).get("url"),
            followers=item.get("statistics", {}).get("subscriberCount"),
            metadata={"video_count": item.get("statistics", {}).get("videoCount")},
        )

    async def get_account_metrics(self, external_account_id: str, start: date, end: date) -> List[Dict[str, Any]]:
        return []

    async def list_content(self, external_account_id: str) -> List[SocialContent]:
        body = await self._client.get(
            f"{self.BASE_URL}/search",
            params={
                "part": "snippet",
                "channelId": external_account_id,
                "type": "video",
                "maxResults": 50,
                "order": "date",
                "key": await self._key(),
            },
        ).json()
        content = []
        for item in body.get("items") or []:
            snippet = item.get("snippet", {})
            content.append(
                SocialContent(
                    external_post_id=item["id"]["videoId"],
                    external_media_id=item["id"]["videoId"],
                    content_type="SHORTS" if snippet.get("liveBroadcastContent") == "none" and "shorts" in (snippet.get("title", "")).lower() else "VIDEO",
                    caption=snippet.get("title"),
                    published_at=datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00")),
                    thumbnail_uri=snippet.get("thumbnails", {}).get("default", {}).get("url"),
                )
            )
        return content

    async def get_content_metrics(self, external_account_id: str, external_post_id: str, start: date, end: date) -> List[SocialMetrics]:
        body = await self._client.get(
            f"{self.BASE_URL}/videos",
            params={"part": "statistics,contentDetails", "id": external_post_id, "key": await self._key()},
        ).json()
        item = (body.get("items") or [{}])[0]
        stats = item.get("statistics", {})
        return [
            SocialMetrics(
                observed_at=datetime.now(timezone.utc),
                views=stats.get("viewCount"),
                likes=stats.get("likeCount"),
                comments=stats.get("commentCount"),
                provider_native={"favorites": stats.get("favoriteCount")},
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
            "CONTENT_WATCH_TIME": True,
            "CONTENT_COMPLETION": True,
            "CONTENT_TRAFFIC_SOURCE": True,
            "ACCOUNT_AUDIENCE": True,
            "PAID_CREATIVE_LINK": True,
        }
