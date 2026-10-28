from sqlalchemy import JSON, Column, Date, DateTime, ForeignKey, String, Text

from app.core.database import Base
from app.models.mixins import UUIDPrimaryKeyMixin, utcnow


class DataQualityIssue(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "data_quality_issues"

    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=True, index=True)
    rule_code = Column(String(128), nullable=False, index=True)
    severity = Column(String(32), nullable=False, default="WARNING")
    entity_type = Column(String(64), nullable=True)
    entity_id = Column(String(255), nullable=True)
    date = Column(Date, nullable=True)
    message = Column(Text, nullable=True)
    context = Column(JSON, nullable=True)
    status = Column(String(32), nullable=False, default="OPEN", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
