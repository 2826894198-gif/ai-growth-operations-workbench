from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint

from app.core.database import Base
from app.models.mixins import UUIDPrimaryKeyMixin, utcnow


class RawApiPayload(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "raw_api_payloads"

    provider = Column(String(32), nullable=False, index=True)
    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=True, index=True)
    endpoint = Column(String(512), nullable=False)
    api_version = Column(String(32), nullable=True)
    request_hash = Column(String(128), nullable=True, index=True)
    request_metadata = Column(JSON, nullable=True)
    payload = Column(JSON, nullable=True)
    fetched_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    sync_job_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class RawWebhookEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "raw_webhook_events"

    provider = Column(String(32), nullable=False)
    delivery_id = Column(String(128), nullable=False)
    topic = Column(String(128), nullable=True)
    shop_domain = Column(String(255), nullable=True)
    api_version = Column(String(32), nullable=True)
    headers_metadata = Column(JSON, nullable=True)
    payload = Column(JSON, nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    verified = Column(Boolean, nullable=False, default=False)
    processed = Column(Boolean, nullable=False, default=False)
    processing_error = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("provider", "delivery_id", name="uq_webhook_delivery"),
    )
