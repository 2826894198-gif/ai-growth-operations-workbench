"""MockSocialProvider — deterministic multi-platform social analytics sandbox."""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.integrations.social.base import SocialAccount, SocialContent, SocialMetrics

_SHARED_STORE: Dict[str, Any] = None


class MockSocialProvider:
    """In-memory multi-account social provider for demo + tests."""

    def __init__(self, platform: str = "INSTAGRAM", store: Optional[Dict[str, Any]] = None):
        global _SHARED_STORE
        self.platform = platform.upper()
        self.provider = self.platform
        if _SHARED_STORE is None:
            _SHARED_STORE = self._default_store()
        self.store = store if store is not None else _SHARED_STORE
        self._rng_counter = 0

    def _default_store(self) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        store = {
            "connections": {
                "META": {
                    "external_identity_id": "meta_identity_1",
                    "scopes": ["instagram_basic", "instagram_content_publish", "insights", "pages_show_list", "ads_read"],
                    "accounts": [
                        {
                            "external_account_id": "ig_a",
                            "platform": "INSTAGRAM",
                            "username": "brand_main",
                            "display_name": "Brand Main",
                            "account_type": "INSTAGRAM_BUSINESS",
                            "followers": 12500,
                            "country": "US",
                            "timezone": "America/New_York",
                        },
                        {
                            "external_account_id": "ig_b",
                            "platform": "INSTAGRAM",
                            "username": "brand_test",
                            "display_name": "Brand Test",
                            "account_type": "INSTAGRAM_CREATOR",
                            "followers": 3200,
                            "country": "US",
                            "timezone": "America/New_York",
                        },
                        {
                            "external_account_id": "fb_page_a",
                            "platform": "FACEBOOK",
                            "username": "brandpage",
                            "display_name": "Brand Page",
                            "account_type": "FACEBOOK_PAGE",
                            "followers": 8200,
                            "country": "US",
                        },
                    ],
                },
                "TIKTOK": {
                    "external_identity_id": "tiktok_identity_1",
                    "scopes": ["user.info.basic", "video.list", "video.data"],
                    "accounts": [
                        {
                            "external_account_id": "tt_a",
                            "platform": "TIKTOK",
                            "username": "brand_main",
                            "display_name": "Brand TikTok",
                            "account_type": "TIKTOK_BUSINESS",
                            "followers": 9800,
                            "country": "US",
                        },
                        {
                            "external_account_id": "tt_b",
                            "platform": "TIKTOK",
                            "username": "brand_creator",
                            "display_name": "Brand Creator",
                            "account_type": "TIKTOK_CREATOR",
                            "followers": 4100,
                            "country": "US",
                        },
                    ],
                },
                "YOUTUBE": {
                    "external_identity_id": "yt_identity_1",
                    "scopes": ["youtube.readonly", "yt-analytics.readonly"],
                    "accounts": [
                        {
                            "external_account_id": "yt_a",
                            "platform": "YOUTUBE",
                            "username": "brandchannel",
                            "display_name": "Brand Channel",
                            "account_type": "YOUTUBE_CHANNEL",
                            "followers": 15400,
                            "country": "US",
                        }
                    ],
                },
            },
            "content": {},
            "paid_creatives": {"IG": [], "TT": [], "YT": []},
        }
        store["content"] = {
            "ig_a": self._content_for("IG", "ig_a", now, 5, store),
            "ig_b": self._content_for("IG", "ig_b", now, 3, store),
            "tt_a": self._content_for("TT", "tt_a", now, 4, store),
            "tt_b": self._content_for("TT", "tt_b", now, 2, store),
            "yt_a": self._content_for("YT", "yt_a", now, 3, store),
        }
        return store

    def _content_for(self, prefix: str, account_id: str, now: datetime, count: int, store: Dict[str, Any]) -> List[Dict[str, Any]]:
        items = []
        for index in range(1, count + 1):
            published = now - timedelta(days=count - index + 2)
            post_id = f"{prefix}-{published.strftime('%Y%m%d')}-{index:02d}"
            base_views = 20000 if prefix == "IG" and index in (1, 3) else 3000 + index * 1200
            base_likes = base_views // 25
            metrics = []
            for day_offset in range(0, 7):
                day = published.date() + timedelta(days=day_offset)
                if day > now.date():
                    continue
                velocity = 1.0 / (day_offset + 1)
                metrics.append(
                    {
                        "date": day.isoformat(),
                        "views": round(base_views * velocity * (0.9 + (index % 3) * 0.05)),
                        "likes": round(base_likes * velocity),
                        "comments": round(max(2, base_likes * 0.06 * velocity)),
                        "shares": round(max(1, base_likes * 0.04 * velocity)),
                        "saves": round(max(1, base_likes * 0.09 * velocity)),
                        "watch_time": round(base_views * 18 * velocity),
                        "average_watch_time": 12 + index,
                        "completion_rate": 0.28 + (index % 4) * 0.05,
                        "skip_rate": 0.32 if prefix == "IG" else 0.28,
                    }
                )
            items.append(
                {
                    "external_post_id": post_id,
                    "external_media_id": post_id,
                    "content_type": "REEL" if prefix == "IG" else "SHORT" if prefix == "TT" else "SHORTS",
                    "caption": f"{prefix} demo content {index} — cassette insert hook",
                    "published_at": published.isoformat(),
                    "public_url": f"https://example.com/{prefix.lower()}/{post_id}",
                    "thumbnail_uri": f"/assets/thumbs/{post_id}.jpg",
                    "duration": 18 + index * 3,
                    "asset_hash": f"hash-{prefix}-{index}",
                    "metrics_daily": metrics,
                }
            )
            # A few posts are promoted with provider-native creative relationships.
            if (prefix == "IG" and index in (1, 3)) or (prefix == "TT" and index == 1):
                campaign = "camp_1001" if prefix == "IG" else "camp_g1001"
                ad = f"ad_{4100 + index}" if prefix == "IG" else "ad_4201"
                store["paid_creatives"][prefix].append(
                    {
                        "creative_id": f"cr_{1000 + index}" if prefix == "IG" else "cr_2001",
                        "media_id": post_id,
                        "account_id": account_id,
                        "campaign_id": campaign,
                        "ad_id": ad,
                    }
                )
        return items

    async def validate_connection(self, connection) -> Dict[str, Any]:
        if connection is None or not getattr(connection, "external_identity_id", None):
            return {"ok": False, "status": "REAUTH_REQUIRED", "message": "missing connection identity"}
        return {"ok": True, "status": "HEALTHY", "scopes": self.store["connections"].get(connection.provider, {}).get("scopes", [])}

    async def discover_accounts(self, connection) -> List[SocialAccount]:
        provider_key = self._provider_key(connection)
        accounts = self.store["connections"].get(provider_key, {}).get("accounts", [])
        return [SocialAccount(**{k: v for k, v in a.items()}) for a in accounts]

    def _provider_key(self, connection) -> str:
        if connection is not None and getattr(connection, "provider", None):
            return connection.provider.upper()
        mapping = {"INSTAGRAM": "META", "FACEBOOK": "META", "TIKTOK": "TIKTOK", "YOUTUBE": "YOUTUBE"}
        return mapping.get(self.platform, self.platform)

    async def get_account_profile(self, external_account_id: str) -> SocialAccount:
        for provider_accounts in self.store["connections"].values():
            for account in provider_accounts.get("accounts", []):
                if account["external_account_id"] == external_account_id:
                    return SocialAccount(**{k: v for k, v in account.items()})
        raise ValueError(f"account not found: {external_account_id}")

    async def get_account_metrics(self, external_account_id: str, start: date, end: date) -> List[Dict[str, Any]]:
        rows = []
        content = self.store["content"].get(external_account_id, [])
        for day in self._date_range(start, end):
            views = 0
            likes = 0
            comments = 0
            shares = 0
            follows = 0
            for item in content:
                for metric in item.get("metrics_daily", []):
                    if metric["date"] == day.isoformat():
                        views += metric["views"]
                        likes += metric["likes"]
                        comments += metric["comments"]
                        shares += metric["shares"]
                        follows += max(0, metric["likes"] // 60)
            profile = await self.get_account_profile(external_account_id)
            rows.append(
                {
                    "date": day.isoformat(),
                    "followers": profile.followers,
                    "views": views,
                    "likes": likes,
                    "comments": comments,
                    "shares": shares,
                    "follows": follows,
                    "content_count": len(content),
                }
            )
        return rows

    async def list_content(self, external_account_id: str) -> List[SocialContent]:
        return [self._to_content(item) for item in self.store["content"].get(external_account_id, [])]

    async def get_content_metrics(self, external_account_id: str, external_post_id: str, start: date, end: date) -> List[SocialMetrics]:
        for item in self.store["content"].get(external_account_id, []):
            if item["external_post_id"] == external_post_id:
                out = []
                for metric in item.get("metrics_daily", []):
                    day = date.fromisoformat(metric["date"])
                    if day < start or day > end:
                        continue
                    out.append(
                        SocialMetrics(
                            observed_at=datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc),
                            views=metric["views"],
                            likes=metric["likes"],
                            comments=metric["comments"],
                            shares=metric["shares"],
                            saves=metric.get("saves"),
                            watch_time=metric.get("watch_time"),
                            average_watch_time=metric.get("average_watch_time"),
                            completion_rate=metric.get("completion_rate"),
                            skip_rate=metric.get("skip_rate"),
                            follows=metric.get("follows"),
                            provider_native={"mock_native": True, "platform": self.platform},
                        )
                    )
                return out
        return []

    async def get_capabilities(self, external_account_id: str) -> Dict[str, bool]:
        base = {
            "ACCOUNT_PROFILE": True,
            "ACCOUNT_FOLLOWERS": True,
            "CONTENT_LIST": True,
            "CONTENT_VIEWS": True,
            "CONTENT_LIKES": True,
            "CONTENT_COMMENTS": True,
            "CONTENT_SHARES": True,
            "CONTENT_SAVES": True,
            "PAID_CREATIVE_LINK": True,
            "ADS_READ": True,
        }
        if self.platform == "INSTAGRAM":
            base.update({"CONTENT_WATCH_TIME": True, "CONTENT_SKIP_RATE": True, "CONTENT_COMPLETION": True})
        if self.platform == "TIKTOK":
            base.update({"CONTENT_WATCH_TIME": False, "CONTENT_COMPLETION": False})
        if self.platform == "YOUTUBE":
            base.update(
                {
                    "CONTENT_WATCH_TIME": True,
                    "CONTENT_COMPLETION": True,
                    "CONTENT_TRAFFIC_SOURCE": True,
                    "ACCOUNT_AUDIENCE": True,
                }
            )
        return base

    def _to_content(self, item: Dict[str, Any]) -> SocialContent:
        return SocialContent(
            external_post_id=item["external_post_id"],
            external_media_id=item.get("external_media_id"),
            content_type=item.get("content_type", "VIDEO"),
            caption=item.get("caption"),
            published_at=datetime.fromisoformat(item["published_at"]) if item.get("published_at") else None,
            public_url=item.get("public_url"),
            thumbnail_uri=item.get("thumbnail_uri"),
            duration=item.get("duration"),
            asset_hash=item.get("asset_hash"),
            metadata={"metrics_daily": item.get("metrics_daily", [])},
        )

    @staticmethod
    def _date_range(start: date, end: date):
        day = start
        while day <= end:
            yield day
            day += timedelta(days=1)

    def paid_creatives(self, platform: str) -> List[Dict[str, Any]]:
        return list(self.store.get("paid_creatives", {}).get(platform, []))

    def clear_content(self) -> None:
        self.store["content"] = {key: [] for key in self.store["content"]}
