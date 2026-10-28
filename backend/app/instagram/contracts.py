"""Stable Phase 1 contracts for Instagram Growth Intelligence.

These contracts deliberately keep source layers and metric availability explicit.
An unavailable metric must carry a null value plus a reason; zero is reserved for
an observed, supported metric whose value is actually zero.
"""

from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InstagramDataLayer(str, Enum):
    RAW = "RAW"
    DERIVED = "DERIVED"
    AI_INFERENCE = "AI_INFERENCE"


class InstagramSourceMode(str, Enum):
    DEMO = "DEMO"
    LIVE = "LIVE"


class InstagramMetricLevel(str, Enum):
    ACCOUNT = "ACCOUNT"
    MEDIA = "MEDIA"
    AUDIENCE = "AUDIENCE"


class InstagramMediaType(str, Enum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    REELS = "REELS"
    CAROUSEL_ALBUM = "CAROUSEL_ALBUM"
    STORIES = "STORIES"
    LIVE = "LIVE"


class InstagramAvailability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    PERMISSION_DENIED = "permission_denied"
    EMPTY = "empty"


class InstagramAccountType(str, Enum):
    BUSINESS = "BUSINESS"
    CREATOR = "CREATOR"


class InstagramRecordStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    EMPTY = "EMPTY"
    FAILED = "FAILED"


class InstagramMetricKey(str, Enum):
    FOLLOWER_COUNT = "follower_count"
    REACH = "reach"
    VIEWS = "views"
    PLAYS = "plays"
    PROFILE_VIEWS = "profile_views"
    WEBSITE_CLICKS = "website_clicks"
    PROFILE_LINKS_TAPS = "profile_links_taps"
    ACCOUNTS_ENGAGED = "accounts_engaged"
    TOTAL_INTERACTIONS = "total_interactions"
    LIKES = "likes"
    COMMENTS = "comments"
    SHARES = "shares"
    SAVED = "saved"
    FOLLOWS = "follows"
    UNFOLLOWS = "unfollows"
    ONLINE_FOLLOWERS = "online_followers"
    WATCH_TIME = "watch_time"
    AVERAGE_WATCH_TIME = "average_watch_time"
    DURATION = "duration"
    REPLAYS = "replays"
    SKIPS = "skips"
    PROFILE_VISITS = "profile_visits"


class InstagramContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InstagramAccountContract(InstagramContractModel):
    account_ref: str = Field(min_length=1)
    external_account_id: str = Field(min_length=1)
    username: str = Field(min_length=1)
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    followers_count: Optional[float] = None
    media_count: Optional[int] = None
    account_type: InstagramAccountType
    connected_at: datetime
    last_sync: Optional[datetime] = None
    timezone: str = "UTC"
    source_mode: InstagramSourceMode
    data_layer: InstagramDataLayer = InstagramDataLayer.RAW

    @model_validator(mode="after")
    def require_raw_identity(self) -> "InstagramAccountContract":
        if self.data_layer is not InstagramDataLayer.RAW:
            raise ValueError("account identity belongs to the RAW layer")
        return self


class InstagramCapabilityContract(InstagramContractModel):
    account_ref: str = Field(min_length=1)
    metric_key: str = Field(min_length=1)
    metric_level: InstagramMetricLevel
    media_type: Optional[InstagramMediaType] = None
    supported: bool
    permission_granted: bool
    reason: Optional[InstagramAvailability] = None
    provider_field: Optional[str] = None
    provider_version: Optional[str] = None
    last_checked_at: datetime

    @property
    def scope_key(self) -> str:
        media_scope = self.media_type.value if self.media_type else "*"
        return f"{self.metric_level.value}:{media_scope}:{self.metric_key}"

    @model_validator(mode="after")
    def validate_scope_and_reason(self) -> "InstagramCapabilityContract":
        if self.metric_level is InstagramMetricLevel.MEDIA and self.media_type is None:
            raise ValueError("media capabilities require media_type")
        if self.metric_level is not InstagramMetricLevel.MEDIA and self.media_type is not None:
            raise ValueError("media_type is only valid for media capabilities")
        if not self.supported and self.reason is None:
            raise ValueError("unsupported capabilities require a reason")
        if not self.permission_granted and self.reason is not InstagramAvailability.PERMISSION_DENIED:
            raise ValueError("permission_granted=false requires permission_denied")
        if self.reason is InstagramAvailability.AVAILABLE and (
            not self.supported or not self.permission_granted
        ):
            raise ValueError("available capability must be supported and permissioned")
        return self


class InstagramMetricCell(InstagramContractModel):
    metric_key: str = Field(min_length=1)
    metric_level: InstagramMetricLevel
    media_type: Optional[InstagramMediaType] = None
    value: Optional[float] = None
    availability: InstagramAvailability
    source_layer: InstagramDataLayer
    provider_field: Optional[str] = None
    unit: Optional[str] = None

    @model_validator(mode="after")
    def validate_value_and_scope(self) -> "InstagramMetricCell":
        if self.metric_level is InstagramMetricLevel.MEDIA and self.media_type is None:
            raise ValueError("media metric cells require media_type")
        if self.metric_level is not InstagramMetricLevel.MEDIA and self.media_type is not None:
            raise ValueError("media_type is only valid for media metric cells")
        if self.availability is InstagramAvailability.AVAILABLE and self.value is None:
            raise ValueError("available metrics require a value")
        if self.availability is not InstagramAvailability.AVAILABLE and self.value is not None:
            raise ValueError("unavailable metrics must keep value null")
        return self


def _validate_metric_maps(
    metrics: Dict[str, Optional[float]],
    availability: Dict[str, InstagramAvailability],
) -> None:
    if set(metrics) != set(availability):
        missing_availability = sorted(set(metrics) - set(availability))
        missing_metric = sorted(set(availability) - set(metrics))
        raise ValueError(
            f"metric availability must cover exactly the metric keys; "
            f"missing_availability={missing_availability}, missing_metric={missing_metric}"
        )
    for metric_key, value in metrics.items():
        reason = availability[metric_key]
        if reason is InstagramAvailability.AVAILABLE and value is None:
            raise ValueError(f"available metric {metric_key!r} cannot be null")
        if reason is not InstagramAvailability.AVAILABLE and value is not None:
            raise ValueError(f"unavailable metric {metric_key!r} must be null")


class InstagramAccountSnapshotContract(InstagramContractModel):
    account_ref: str = Field(min_length=1)
    observed_at: datetime
    window_start: date
    window_end: date
    source_mode: InstagramSourceMode
    api_version: str = Field(min_length=1)
    raw_payload_ref: str = Field(min_length=1)
    timezone: str = "UTC"
    metrics: Dict[str, Optional[float]]
    metric_availability: Dict[str, InstagramAvailability]
    record_status: InstagramRecordStatus = InstagramRecordStatus.COMPLETE
    source_layer: InstagramDataLayer = InstagramDataLayer.RAW

    @model_validator(mode="after")
    def validate_raw_window(self) -> "InstagramAccountSnapshotContract":
        if self.source_layer is not InstagramDataLayer.RAW:
            raise ValueError("account snapshots belong to the RAW layer")
        if self.window_end < self.window_start:
            raise ValueError("window_end cannot precede window_start")
        _validate_metric_maps(self.metrics, self.metric_availability)
        return self


class InstagramMediaContract(InstagramContractModel):
    account_ref: str = Field(min_length=1)
    external_media_id: str = Field(min_length=1)
    media_type: InstagramMediaType
    published_at: datetime
    caption: Optional[str] = None
    permalink: Optional[str] = None
    duration_seconds: Optional[float] = None
    source_mode: InstagramSourceMode
    data_layer: InstagramDataLayer = InstagramDataLayer.RAW

    @model_validator(mode="after")
    def require_raw_media(self) -> "InstagramMediaContract":
        if self.data_layer is not InstagramDataLayer.RAW:
            raise ValueError("media metadata belongs to the RAW layer")
        return self


class InstagramMediaSnapshotContract(InstagramContractModel):
    account_ref: str = Field(min_length=1)
    external_media_id: str = Field(min_length=1)
    observed_at: datetime
    media_type: InstagramMediaType
    source_mode: InstagramSourceMode
    api_version: str = Field(min_length=1)
    raw_payload_ref: str = Field(min_length=1)
    metrics: Dict[str, Optional[float]]
    metric_availability: Dict[str, InstagramAvailability]
    record_status: InstagramRecordStatus = InstagramRecordStatus.COMPLETE
    source_layer: InstagramDataLayer = InstagramDataLayer.RAW

    @model_validator(mode="after")
    def validate_raw_media_snapshot(self) -> "InstagramMediaSnapshotContract":
        if self.source_layer is not InstagramDataLayer.RAW:
            raise ValueError("media insight snapshots belong to the RAW layer")
        _validate_metric_maps(self.metrics, self.metric_availability)
        return self


class InstagramDerivedMetricContract(InstagramContractModel):
    subject_type: InstagramMetricLevel
    subject_ref: str = Field(min_length=1)
    window_start: date
    window_end: date
    source_mode: InstagramSourceMode
    metrics: Dict[str, Optional[float]]
    metric_availability: Dict[str, InstagramAvailability]
    input_metric_keys: List[str] = Field(min_length=1)
    input_snapshot_refs: List[str] = Field(min_length=1)
    calculation_version: str = Field(min_length=1)
    baseline_ref: Optional[str] = None
    source_layer: InstagramDataLayer = InstagramDataLayer.DERIVED

    @model_validator(mode="after")
    def validate_derived_snapshot(self) -> "InstagramDerivedMetricContract":
        if self.source_layer is not InstagramDataLayer.DERIVED:
            raise ValueError("derived metrics must use the DERIVED layer")
        if self.window_end < self.window_start:
            raise ValueError("window_end cannot precede window_start")
        _validate_metric_maps(self.metrics, self.metric_availability)
        return self


class InstagramDemoFixture(InstagramContractModel):
    fixture_version: str = Field(min_length=1)
    generated_at: datetime
    source_mode: InstagramSourceMode
    accounts: List[InstagramAccountContract] = Field(min_length=1)
    capabilities: List[InstagramCapabilityContract]
    account_snapshots: List[InstagramAccountSnapshotContract]
    media: List[InstagramMediaContract]
    media_snapshots: List[InstagramMediaSnapshotContract]

    @model_validator(mode="after")
    def validate_references_and_mode(self) -> "InstagramDemoFixture":
        if self.source_mode is not InstagramSourceMode.DEMO:
            raise ValueError("demo fixtures must be explicitly marked DEMO")

        if any(account.source_mode is not self.source_mode for account in self.accounts):
            raise ValueError("account source_mode must match the fixture source_mode")
        if any(snapshot.source_mode is not self.source_mode for snapshot in self.account_snapshots):
            raise ValueError("account snapshot source_mode must match the fixture source_mode")
        if any(media.source_mode is not self.source_mode for media in self.media):
            raise ValueError("media source_mode must match the fixture source_mode")
        if any(snapshot.source_mode is not self.source_mode for snapshot in self.media_snapshots):
            raise ValueError("media snapshot source_mode must match the fixture source_mode")

        account_refs = {account.account_ref for account in self.accounts}
        if any(capability.account_ref not in account_refs for capability in self.capabilities):
            raise ValueError("capabilities must reference fixture accounts")
        if any(snapshot.account_ref not in account_refs for snapshot in self.account_snapshots):
            raise ValueError("account snapshots must reference fixture accounts")

        media_refs = {media.external_media_id for media in self.media}
        if any(snapshot.external_media_id not in media_refs for snapshot in self.media_snapshots):
            raise ValueError("media snapshots must reference fixture media")
        return self
