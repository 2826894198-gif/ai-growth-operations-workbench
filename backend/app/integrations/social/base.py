"""Social analytics provider interface (PART 06-01 §E112)."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class SocialAccount:
    external_account_id: str
    platform: str
    username: str
    display_name: str
    account_type: str
    avatar_url: Optional[str] = None
    profile_url: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    followers: Optional[float] = None
    external_parent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SocialContent:
    external_post_id: str
    external_media_id: Optional[str] = None
    content_type: str = "VIDEO"
    caption: Optional[str] = None
    published_at: Optional[datetime] = None
    public_url: Optional[str] = None
    thumbnail_uri: Optional[str] = None
    duration: Optional[int] = None
    asset_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SocialMetrics:
    observed_at: datetime
    views: Optional[float] = None
    reach: Optional[float] = None
    likes: Optional[float] = None
    comments: Optional[float] = None
    shares: Optional[float] = None
    saves: Optional[float] = None
    watch_time: Optional[float] = None
    average_watch_time: Optional[float] = None
    completion_rate: Optional[float] = None
    skip_rate: Optional[float] = None
    profile_visits: Optional[float] = None
    follows: Optional[float] = None
    provider_native: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observed_at": self.observed_at.isoformat(),
            "views": self.views,
            "reach": self.reach,
            "likes": self.likes,
            "comments": self.comments,
            "shares": self.shares,
            "saves": self.saves,
            "watch_time": self.watch_time,
            "average_watch_time": self.average_watch_time,
            "completion_rate": self.completion_rate,
            "skip_rate": self.skip_rate,
            "profile_visits": self.profile_visits,
            "follows": self.follows,
            "provider_native": self.provider_native,
        }


class SocialAnalyticsProvider(Protocol):
    provider: str
    platform: str

    async def validate_connection(self, connection) -> Dict[str, Any]: ...

    async def discover_accounts(self, connection) -> List[SocialAccount]: ...

    async def get_account_profile(self, external_account_id: str) -> SocialAccount: ...

    async def get_account_metrics(self, external_account_id: str, start: date, end: date) -> List[Dict[str, Any]]: ...

    async def list_content(self, external_account_id: str) -> List[SocialContent]: ...

    async def get_content_metrics(self, external_account_id: str, external_post_id: str, start: date, end: date) -> List[SocialMetrics]: ...

    async def get_capabilities(self, external_account_id: str) -> Dict[str, bool]: ...
