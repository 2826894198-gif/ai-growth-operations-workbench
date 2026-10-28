"""Instagram Growth Intelligence persistence models.

The tables in this module intentionally distinguish normalized provider data
(RAW) from later calculations (DERIVED). AI inference is not persisted here;
it will receive its own evidence-bound model in a later phase.
"""

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
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


class InstagramOAuthCredential(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Encrypted server-side Instagram Business Login token material.

    Only the ciphertext is stored here.  API-facing connection records retain
    an opaque credential reference and must never contain the raw token.
    """

    __tablename__ = "instagram_oauth_credentials"

    connection_id = Column(String(36), ForeignKey("provider_connections.id"), nullable=False, unique=True, index=True)
    key_version = Column(String(64), nullable=False, default="instagram-token-v1")
    ciphertext = Column(Text, nullable=False)
    token_type = Column(String(64), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    granted_scopes = Column(JSON, nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)


class InstagramCapability(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "instagram_capabilities"

    account_id = Column(String(36), ForeignKey("connected_accounts.id"), nullable=False, index=True)
    metric_key = Column(String(128), nullable=False)
    metric_level = Column(String(32), nullable=False)
    media_type = Column(String(64), nullable=True)
    scope_key = Column(String(255), nullable=False)
    supported = Column(Boolean, nullable=False, default=False)
    permission_granted = Column(Boolean, nullable=False, default=False)
    reason = Column(String(32), nullable=True)
    provider_field = Column(String(255), nullable=True)
    provider_version = Column(String(64), nullable=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=False)
    meta = Column("metadata", JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("account_id", "scope_key", name="uq_instagram_capability_scope"),
        Index("ix_instagram_capabilities_account_level", "account_id", "metric_level"),
        CheckConstraint(
            "reason IS NULL OR reason IN ('available', 'unavailable', 'unsupported', 'permission_denied', 'empty')",
            name="ck_instagram_capability_reason",
        ),
    )


class InstagramAccountSnapshot(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "instagram_account_snapshots"

    account_id = Column(String(36), ForeignKey("connected_accounts.id"), nullable=False, index=True)
    observed_at = Column(DateTime(timezone=True), nullable=False, index=True)
    window_start = Column(Date, nullable=False)
    window_end = Column(Date, nullable=False)
    source_layer = Column(String(32), nullable=False, default="RAW")
    source_mode = Column(String(16), nullable=False, default="DEMO")
    api_version = Column(String(64), nullable=False)
    raw_payload_id = Column(String(36), ForeignKey("raw_api_payloads.id"), nullable=False, index=True)
    timezone = Column(String(128), nullable=False, default="UTC")
    metrics = Column(JSON, nullable=False)
    metric_availability = Column(JSON, nullable=False)
    record_status = Column(String(32), nullable=False, default="COMPLETE")
    dedupe_key = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("ix_instagram_account_snapshots_window", "account_id", "window_start", "window_end"),
        Index("ix_instagram_account_snapshots_source", "source_mode", "source_layer"),
        CheckConstraint("source_layer = 'RAW'", name="ck_instagram_account_snapshot_raw_layer"),
        CheckConstraint("source_mode IN ('DEMO', 'LIVE')", name="ck_instagram_account_snapshot_source_mode"),
    )


class InstagramMediaSnapshot(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "instagram_media_snapshots"

    account_id = Column(String(36), ForeignKey("connected_accounts.id"), nullable=False, index=True)
    publication_id = Column(String(36), ForeignKey("content_publications.id"), nullable=True, index=True)
    external_media_id = Column(String(255), nullable=False)
    observed_at = Column(DateTime(timezone=True), nullable=False, index=True)
    media_type = Column(String(64), nullable=False)
    source_layer = Column(String(32), nullable=False, default="RAW")
    source_mode = Column(String(16), nullable=False, default="DEMO")
    api_version = Column(String(64), nullable=False)
    raw_payload_id = Column(String(36), ForeignKey("raw_api_payloads.id"), nullable=False, index=True)
    metrics = Column(JSON, nullable=False)
    metric_availability = Column(JSON, nullable=False)
    record_status = Column(String(32), nullable=False, default="COMPLETE")
    dedupe_key = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "external_media_id",
            "observed_at",
            "source_mode",
            name="uq_instagram_media_snapshot_observation",
        ),
        Index("ix_instagram_media_snapshots_type", "media_type"),
        Index("ix_instagram_media_snapshots_source", "source_mode", "source_layer"),
        CheckConstraint("source_layer = 'RAW'", name="ck_instagram_media_snapshot_raw_layer"),
        CheckConstraint("source_mode IN ('DEMO', 'LIVE')", name="ck_instagram_media_snapshot_source_mode"),
    )


class InstagramDerivedMetricSnapshot(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "instagram_derived_metric_snapshots"

    subject_type = Column(String(32), nullable=False)
    subject_ref = Column(String(255), nullable=False, index=True)
    account_id = Column(String(36), ForeignKey("connected_accounts.id"), nullable=True, index=True)
    publication_id = Column(String(36), ForeignKey("content_publications.id"), nullable=True, index=True)
    window_start = Column(Date, nullable=False)
    window_end = Column(Date, nullable=False)
    source_mode = Column(String(16), nullable=False)
    source_layer = Column(String(32), nullable=False, default="DERIVED")
    metrics = Column(JSON, nullable=False)
    metric_availability = Column(JSON, nullable=False)
    input_metric_keys = Column(JSON, nullable=False)
    input_snapshot_refs = Column(JSON, nullable=False)
    calculation_version = Column(String(64), nullable=False)
    baseline_ref = Column(String(255), nullable=True)
    dedupe_key = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("ix_instagram_derived_subject_window", "subject_type", "subject_ref", "window_start", "window_end"),
        Index("ix_instagram_derived_calculation_version", "calculation_version"),
        CheckConstraint("source_layer = 'DERIVED'", name="ck_instagram_derived_metric_derived_layer"),
        CheckConstraint("source_mode IN ('DEMO', 'LIVE')", name="ck_instagram_derived_metric_source_mode"),
    )


class InstagramHealthScoreSnapshot(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "instagram_health_score_snapshots"

    workspace_id = Column(String(36), nullable=False, index=True)
    account_id = Column(String(36), ForeignKey("connected_accounts.id"), nullable=False, index=True)
    evaluated_at = Column(DateTime(timezone=True), nullable=False, index=True)
    window_start = Column(Date, nullable=False)
    window_end = Column(Date, nullable=False)
    source_mode = Column(String(16), nullable=False)
    source_layer = Column(String(32), nullable=False, default="DERIVED")
    score = Column(Float, nullable=True)
    dimension_scores = Column(JSON, nullable=False)
    effective_weights = Column(JSON, nullable=False)
    missing_dimensions = Column(JSON, nullable=False)
    data_coverage = Column(Float, nullable=False)
    sample_factor = Column(Float, nullable=False)
    freshness_factor = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    confidence_level = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False)
    calculation_version = Column(String(64), nullable=False)
    evidence = Column(JSON, nullable=True)
    dedupe_key = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("ix_instagram_health_score_account_window", "account_id", "window_start", "window_end"),
        Index("ix_instagram_health_score_confidence", "confidence_level"),
        CheckConstraint("source_layer = 'DERIVED'", name="ck_instagram_health_score_derived_layer"),
        CheckConstraint("source_mode IN ('DEMO', 'LIVE')", name="ck_instagram_health_score_source_mode"),
    )


class InstagramRuleEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "instagram_rule_events"

    workspace_id = Column(String(36), nullable=False, index=True)
    account_id = Column(String(36), ForeignKey("connected_accounts.id"), nullable=True, index=True)
    publication_id = Column(String(36), ForeignKey("content_publications.id"), nullable=True, index=True)
    subject_ref = Column(String(255), nullable=False, index=True)
    rule_code = Column(String(128), nullable=False, index=True)
    rule_version = Column(String(64), nullable=False)
    source_mode = Column(String(16), nullable=False)
    source_layer = Column(String(32), nullable=False, default="DERIVED")
    status = Column(String(32), nullable=False, default="OPEN", index=True)
    triggered = Column(Boolean, nullable=False, default=False)
    severity = Column(String(32), nullable=False, default="INFO")
    detected_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    confidence = Column(Float, nullable=True)
    missing_fields = Column(JSON, nullable=False)
    evidence = Column(JSON, nullable=False)
    dedupe_key = Column(String(255), nullable=False, unique=True)

    __table_args__ = (
        Index("ix_instagram_rule_events_subject_status", "subject_ref", "status"),
        Index("ix_instagram_rule_events_account_rule", "account_id", "rule_code"),
        CheckConstraint("source_layer = 'DERIVED'", name="ck_instagram_rule_event_derived_layer"),
        CheckConstraint("source_mode IN ('DEMO', 'LIVE')", name="ck_instagram_rule_event_source_mode"),
    )


class InstagramSyncRun(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "instagram_sync_runs"

    workspace_id = Column(String(36), nullable=False, index=True)
    account_id = Column(String(36), ForeignKey("connected_accounts.id"), nullable=True, index=True)
    run_type = Column(String(64), nullable=False)
    source_mode = Column(String(16), nullable=False)
    status = Column(String(32), nullable=False, default="RUNNING", index=True)
    requested_window_start = Column(Date, nullable=True)
    requested_window_end = Column(Date, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    items_seen = Column(Integer, nullable=False, default=0)
    items_written = Column(Integer, nullable=False, default=0)
    raw_payloads_written = Column(Integer, nullable=False, default=0)
    error_code = Column(String(64), nullable=True)
    error_detail = Column(Text, nullable=True)
    meta = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
