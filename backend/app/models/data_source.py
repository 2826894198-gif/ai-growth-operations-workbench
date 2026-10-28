from sqlalchemy import JSON, Boolean, Column, DateTime, String

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DataSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "data_sources"

    # Added as an expand/contract field in 0010.  Existing rows are backfilled
    # to ws_main; the column remains nullable during the compatibility window.
    workspace_id = Column(String(36), nullable=True, index=True)
    provider = Column(String(32), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    external_account_id = Column(String(255), nullable=True)
    external_account_name = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False, default="UNKNOWN", index=True)
    api_version = Column(String(32), nullable=True)
    timezone = Column(String(128), nullable=True)
    currency = Column(String(8), nullable=True)
    credential_reference = Column(String(512), nullable=True)
    sync_enabled = Column(Boolean, nullable=False, default=True)
    last_successful_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_failed_sync_at = Column(DateTime(timezone=True), nullable=True)
    meta = Column("metadata", JSON, nullable=True)
