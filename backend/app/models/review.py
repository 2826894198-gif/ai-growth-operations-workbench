"""Account health snapshots and durable business review records."""

from sqlalchemy import JSON, Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class AccountHealthSnapshot(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "account_health_snapshots"

    workspace_id = Column(String(36), nullable=False, index=True)
    account_id = Column(String(36), ForeignKey("connected_accounts.id"), nullable=False, index=True)
    evaluated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    connection_status = Column(String(32), nullable=False)
    data_status = Column(String(32), nullable=False)
    performance_status = Column(String(32), nullable=False)
    content_status = Column(String(32), nullable=False)
    overall_status = Column(String(32), nullable=False, index=True)
    data_usable = Column(Boolean, nullable=False, default=False)
    rule_version = Column(String(32), nullable=False, default="v1")
    summary = Column(JSON, nullable=True)


class AccountHealthEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "account_health_events"

    workspace_id = Column(String(36), nullable=False, index=True)
    account_id = Column(String(36), ForeignKey("connected_accounts.id"), nullable=False, index=True)
    rule_code = Column(String(128), nullable=False, index=True)
    rule_version = Column(String(32), nullable=False, default="v1")
    severity = Column(String(32), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="OPEN", index=True)
    detected_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    observed_value = Column(String(255), nullable=True)
    baseline_value = Column(String(255), nullable=True)
    evidence = Column(JSON, nullable=True)
    owner_id = Column(String(128), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)


class AccountDetectionSetting(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "account_detection_settings"

    workspace_id = Column(String(36), nullable=False, unique=True, index=True)
    sync_delay_minutes = Column(Integer, nullable=False, default=20)
    sync_stale_minutes = Column(Integer, nullable=False, default=60)
    content_inactive_days = Column(Integer, nullable=False, default=7)


class ReviewRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "review_runs"

    workspace_id = Column(String(36), nullable=False, index=True)
    review_type = Column(String(32), nullable=False, index=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    baseline_start = Column(Date, nullable=False)
    baseline_end = Column(Date, nullable=False)
    scope = Column(JSON, nullable=False, default=dict)
    data_status = Column(String(32), nullable=False, default="UNKNOWN", index=True)
    metric_snapshot = Column(JSON, nullable=False, default=dict)
    summary = Column(Text, nullable=True)
    caveats = Column(JSON, nullable=True)
    status = Column(String(32), nullable=False, default="DRAFT", index=True)
    created_by = Column(String(128), nullable=False, default="operator")
    locked_at = Column(DateTime(timezone=True), nullable=True)


class ReviewFinding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "review_findings"

    review_id = Column(String(36), ForeignKey("review_runs.id"), nullable=False, index=True)
    finding_type = Column(String(32), nullable=False, default="OBSERVATION")
    severity = Column(String(32), nullable=False, default="INFO")
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    evidence = Column(JSON, nullable=True)
    health_event_id = Column(String(36), ForeignKey("account_health_events.id"), nullable=True)


class ReviewFollowup(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "review_followups"

    review_id = Column(String(36), ForeignKey("review_runs.id"), nullable=False, index=True)
    workspace_id = Column(String(36), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    owner_id = Column(String(128), nullable=True)
    due_date = Column(Date, nullable=True)
    status = Column(String(32), nullable=False, default="OPEN", index=True)
    result = Column(Text, nullable=True)
