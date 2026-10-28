"""PART 06-01 — multi-account, content intelligence & connection center schema."""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class Brand(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "brands"

    workspace_id = Column(String(36), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(128), nullable=False, index=True)
    default_timezone = Column(String(128), nullable=False, default="America/New_York")
    reporting_currency = Column(String(8), nullable=False, default="USD")
    status = Column(String(32), nullable=False, default="ACTIVE")

    __table_args__ = (UniqueConstraint("workspace_id", "slug", name="uq_brand_workspace_slug"),)


class AccountGroup(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "account_groups"

    workspace_id = Column(String(36), nullable=False, index=True)
    brand_id = Column(String(36), ForeignKey("brands.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)


class ProviderConnection(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "provider_connections"

    workspace_id = Column(String(36), nullable=False, index=True)
    provider = Column(String(64), nullable=False, index=True)  # META/INSTAGRAM/TIKTOK/YOUTUBE/GOOGLE_ADS/SHOPIFY
    connection_type = Column(String(64), nullable=False, default="OAUTH")
    external_identity_id = Column(String(255), nullable=True, index=True)
    credential_reference = Column(String(512), nullable=True)  # never raw tokens
    status = Column(String(32), nullable=False, default="UNKNOWN", index=True)  # HEALTHY/EXPIRING/REAUTH_REQUIRED/SCOPE_MISSING/RATE_LIMITED/WEBHOOK_FAILED/DISABLED/UNKNOWN
    authorized_scopes = Column(JSON, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    last_validated_at = Column(DateTime(timezone=True), nullable=True)
    last_refreshed_at = Column(DateTime(timezone=True), nullable=True)
    app_id_reference = Column(String(255), nullable=True)
    webhook_status = Column(String(32), nullable=True)
    webhook_last_event_at = Column(DateTime(timezone=True), nullable=True)
    webhook_failure_count = Column(Integer, nullable=False, default=0)
    rate_limit_status = Column(String(32), nullable=True)
    rate_limit_retry_after = Column(Integer, nullable=True)
    meta = Column("metadata", JSON, nullable=True)


class ConnectedAccount(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "connected_accounts"

    workspace_id = Column(String(36), nullable=False, index=True)
    brand_id = Column(String(36), ForeignKey("brands.id"), nullable=True, index=True)
    account_group_id = Column(String(36), ForeignKey("account_groups.id"), nullable=True, index=True)
    connection_id = Column(String(36), ForeignKey("provider_connections.id"), nullable=True, index=True)
    provider = Column(String(64), nullable=False, index=True)
    platform = Column(String(64), nullable=False, index=True)
    account_type = Column(String(64), nullable=False)
    external_account_id = Column(String(255), nullable=False)
    external_parent_id = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True, index=True)
    display_name = Column(String(255), nullable=True)
    profile_url = Column(String(512), nullable=True)
    avatar_url = Column(String(512), nullable=True)
    country = Column(String(8), nullable=True)
    timezone = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="LINKED", index=True)  # LINKED/DISCONNECTED/EXPIRED
    health_status = Column(String(32), nullable=False, default="UNKNOWN")  # HEALTHY/DEGRADED/AT_RISK/DISCONNECTED
    is_primary = Column(Boolean, nullable=False, default=False)
    is_test = Column(Boolean, nullable=False, default=False)
    last_profile_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_content_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_analytics_sync_at = Column(DateTime(timezone=True), nullable=True)
    meta = Column("metadata", JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("workspace_id", "provider", "external_account_id", name="uq_connected_account_external"),
        Index("ix_connected_accounts_platform_workspace", "workspace_id", "platform"),
    )


class ProviderCapability(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "provider_capabilities"

    provider = Column(String(64), nullable=False, index=True)
    platform = Column(String(64), nullable=True, index=True)
    capability_key = Column(String(128), nullable=False)
    description = Column(String(512), nullable=True)
    default_supported = Column(Boolean, nullable=False, default=False)
    requires_permission = Column(String(128), nullable=True)
    provider_version = Column(String(64), nullable=True)
    availability_notes = Column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("provider", "platform", "capability_key", name="uq_provider_capability"),)


class AccountCapability(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "account_capabilities"

    account_id = Column(String(36), ForeignKey("connected_accounts.id"), nullable=False, index=True)
    capability_key = Column(String(128), nullable=False, index=True)
    supported = Column(Boolean, nullable=False, default=False)
    permission_granted = Column(Boolean, nullable=False, default=False)
    provider_field = Column(String(255), nullable=True)
    provider_version = Column(String(64), nullable=True)
    last_verified_at = Column(DateTime(timezone=True), nullable=True)
    limitations = Column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("account_id", "capability_key", name="uq_account_capability"),)


class SocialMetricCatalog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "social_metric_catalog"

    metric_key = Column(String(128), nullable=False, index=True)
    canonical_name = Column(String(255), nullable=False)
    metric_level = Column(String(32), nullable=False, default="CONTENT")  # ACCOUNT/CONTENT/AUDIENCE
    aggregation_type = Column(String(32), nullable=False)  # ADDITIVE/SEMI_ADDITIVE/NON_ADDITIVE/RATE/UNIQUE_ESTIMATE/PROVIDER_NATIVE_ONLY
    unit = Column(String(64), nullable=True)
    comparable_cross_platform = Column(Boolean, nullable=False, default=False)
    positive_direction = Column(String(8), nullable=False, default="UP")
    provider = Column(String(64), nullable=True)
    provider_metric_name = Column(String(255), nullable=True)
    availability_notes = Column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("metric_key", "provider", name="uq_social_metric_key"),)


class ContentAsset(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "content_assets"

    workspace_id = Column(String(36), nullable=False, index=True)
    brand_id = Column(String(36), ForeignKey("brands.id"), nullable=True, index=True)
    asset_type = Column(String(64), nullable=False, default="VIDEO")
    title = Column(String(512), nullable=True)
    internal_name = Column(String(512), nullable=True)
    source_asset_uri = Column(String(1024), nullable=True)
    thumbnail_uri = Column(String(1024), nullable=True)
    asset_hash = Column(String(128), nullable=True, index=True)
    duration = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    aspect_ratio = Column(String(16), nullable=True)
    created_at_source = Column(DateTime(timezone=True), nullable=True)
    owner_user_id = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="ACTIVE")
    meta = Column("metadata", JSON, nullable=True)


class ContentPublication(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "content_publications"

    content_asset_id = Column(String(36), ForeignKey("content_assets.id"), nullable=False, index=True)
    account_id = Column(String(36), ForeignKey("connected_accounts.id"), nullable=False, index=True)
    provider = Column(String(64), nullable=False)
    platform = Column(String(64), nullable=False)
    external_post_id = Column(String(255), nullable=False)
    external_media_id = Column(String(255), nullable=True)
    content_type = Column(String(64), nullable=False, default="VIDEO")
    caption = Column(Text, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True, index=True)
    public_url = Column(String(1024), nullable=True)
    provider_status = Column(String(32), nullable=True)
    meta = Column("metadata", JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("provider", "external_post_id", name="uq_publication_external"),
        Index("ix_publications_account_published", "account_id", "published_at"),
    )


class ContentPerformanceSnapshot(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "content_performance_snapshots"

    publication_id = Column(String(36), ForeignKey("content_publications.id"), nullable=False, index=True)
    observed_at = Column(DateTime(timezone=True), nullable=False, index=True)
    views = Column(Float, nullable=True)
    reach = Column(Float, nullable=True)
    likes = Column(Float, nullable=True)
    comments = Column(Float, nullable=True)
    shares = Column(Float, nullable=True)
    saves = Column(Float, nullable=True)
    watch_time = Column(Float, nullable=True)
    average_watch_time = Column(Float, nullable=True)
    completion_rate = Column(Float, nullable=True)
    skip_rate = Column(Float, nullable=True)
    profile_visits = Column(Float, nullable=True)
    follows = Column(Float, nullable=True)
    provider_native_metrics = Column(JSON, nullable=True)
    source = Column(String(32), nullable=False, default="API")

    __table_args__ = (Index("ix_perf_snapshot_publication_observed", "publication_id", "observed_at"),)


class FactContentPerformanceDaily(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "fact_content_performance_daily"

    workspace_id = Column(String(36), nullable=False, index=True)
    account_id = Column(String(36), ForeignKey("connected_accounts.id"), nullable=False, index=True)
    content_asset_id = Column(String(36), ForeignKey("content_assets.id"), nullable=True, index=True)
    publication_id = Column(String(36), ForeignKey("content_publications.id"), nullable=False, index=True)
    date = Column(String(10), nullable=False, index=True)
    views = Column(Float, nullable=True)
    reach = Column(Float, nullable=True)
    likes = Column(Float, nullable=True)
    comments = Column(Float, nullable=True)
    shares = Column(Float, nullable=True)
    saves = Column(Float, nullable=True)
    watch_time = Column(Float, nullable=True)
    follows = Column(Float, nullable=True)
    provider_native_metrics = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("publication_id", "date", name="uq_content_perf_daily"),)


class ContentPromotionLink(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "content_promotion_links"

    workspace_id = Column(String(36), nullable=False, index=True)
    content_asset_id = Column(String(36), ForeignKey("content_assets.id"), nullable=False, index=True)
    publication_id = Column(String(36), ForeignKey("content_publications.id"), nullable=False, index=True)
    paid_platform = Column(String(64), nullable=False)
    paid_account_id = Column(String(36), ForeignKey("connected_accounts.id"), nullable=True, index=True)
    creative_id = Column(String(255), nullable=True, index=True)
    ad_id = Column(String(255), nullable=True, index=True)
    ad_group_id = Column(String(255), nullable=True)
    campaign_id = Column(String(255), nullable=True)
    promotion_type = Column(String(64), nullable=False, default="PAID_BOOST")
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    mapping_confidence = Column(Float, nullable=False, default=1.0)
    mapping_source = Column(String(64), nullable=False, default="MANUAL")  # API_DIRECT/MANUAL/URL_MATCH/ASSET_HASH/CREATIVE_ID/OPERATOR_CONFIRMED
    status = Column(String(32), nullable=False, default="ACTIVE")
    meta = Column("metadata", JSON, nullable=True)

    __table_args__ = (
        Index("ix_promotion_links_publication", "publication_id"),
        Index("ix_promotion_links_creative", "creative_id"),
        Index("ix_promotion_links_ad", "ad_id"),
    )


class FocusMonitor(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "focus_monitors"

    workspace_id = Column(String(36), nullable=False, index=True)
    scope_type = Column(String(64), nullable=False)  # ACCOUNT/CONTENT_ASSET/PUBLICATION/PROMOTION/CAMPAIGN/AD/SEARCH_TERM
    scope_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    priority = Column(String(32), nullable=False, default="NORMAL")  # NORMAL/WATCH/HIGH/CRITICAL
    metrics = Column(JSON, nullable=True)
    rules = Column(JSON, nullable=True)
    refresh_interval_minutes = Column(Integer, nullable=False, default=15)
    notification_policy = Column(JSON, nullable=True)
    baseline_strategy = Column(String(64), nullable=False, default="PREVIOUS_PERIOD")
    started_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, default="ACTIVE", index=True)
    created_by = Column(String(128), nullable=True)

    __table_args__ = (Index("ix_focus_workspace_status", "workspace_id", "status"),)


class Watchlist(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "watchlists"

    workspace_id = Column(String(36), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_default = Column(Boolean, nullable=False, default=False)
    created_by = Column(String(128), nullable=True)


class WatchlistItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "watchlist_items"

    watchlist_id = Column(String(36), ForeignKey("watchlists.id"), nullable=False, index=True)
    focus_monitor_id = Column(String(36), ForeignKey("focus_monitors.id"), nullable=True, index=True)
    scope_type = Column(String(64), nullable=False)
    scope_id = Column(String(255), nullable=False)
    note = Column(Text, nullable=True)


class SavedScope(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "saved_scopes"

    workspace_id = Column(String(36), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    scope = Column(JSON, nullable=False)
    created_by = Column(String(128), nullable=True)
    is_favorite = Column(Boolean, nullable=False, default=False)


class DeveloperAppConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "developer_app_configs"

    workspace_id = Column(String(36), nullable=False, index=True)
    provider = Column(String(64), nullable=False, index=True)
    app_display_name = Column(String(255), nullable=False)
    client_id_reference = Column(String(512), nullable=True)
    secret_reference = Column(String(512), nullable=True)  # never raw secret
    redirect_uri = Column(String(512), nullable=True)
    approval_status = Column(String(32), nullable=False, default="NOT_CONFIGURED")  # SETUP_REQUIRED/APPROVAL_REQUIRED/CONFIGURED/PRODUCTION_READY
    scopes = Column(JSON, nullable=True)
    environment = Column(String(32), nullable=False, default="SANDBOX")
    last_validation = Column(DateTime(timezone=True), nullable=True)
    meta = Column("metadata", JSON, nullable=True)


class ConnectionAudit(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "connection_audits"

    workspace_id = Column(String(36), nullable=True, index=True)
    connection_id = Column(String(36), nullable=True, index=True)
    account_id = Column(String(36), nullable=True, index=True)
    actor = Column(String(128), nullable=True)
    action = Column(String(64), nullable=False, index=True)  # OAUTH_STARTED/TOKEN_REFRESHED/LINKED/UNLINKED/MAPPED/DISCOVERED/REAUTHORIZED
    before = Column(JSON, nullable=True)
    after = Column(JSON, nullable=True)
    meta = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
