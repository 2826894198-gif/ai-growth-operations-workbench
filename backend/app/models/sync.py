from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class SyncJob(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "sync_jobs"

    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=True, index=True)
    provider = Column(String(32), nullable=False)
    job_type = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="QUEUED", index=True)
    range_start = Column(String(32), nullable=True)
    range_end = Column(String(32), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    records_received = Column(Integer, nullable=False, default=0)
    records_inserted = Column(Integer, nullable=False, default=0)
    records_updated = Column(Integer, nullable=False, default=0)
    records_failed = Column(Integer, nullable=False, default=0)
    api_requests = Column(Integer, nullable=False, default=0)
    error_code = Column(String(128), nullable=True)
    error_message = Column(String(4000), nullable=True)
    meta = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class SyncCursor(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "sync_cursors"

    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=False, index=True)
    resource_type = Column(String(64), nullable=False)
    cursor_type = Column(String(32), nullable=False, default="updated_at")
    cursor_value = Column(String(512), nullable=True)
    watermark_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("data_source_id", "resource_type", "cursor_type", name="uq_sync_cursor_grain"),
    )


class ProviderApiUsage(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "provider_api_usage"

    provider = Column(String(32), nullable=False, index=True)
    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=True)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    request_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    failure_count = Column(Integer, nullable=False, default=0)
    rate_limit_count = Column(Integer, nullable=False, default=0)
    meta = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
