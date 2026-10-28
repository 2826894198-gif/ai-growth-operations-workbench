from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.mixins import UUIDPrimaryKeyMixin, utcnow


class BrowserProfileAudit(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "browser_profile_audits"

    profile_id = Column(String(36), ForeignKey("browser_profiles.id"), nullable=False, index=True)
    field = Column(String(128), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    operator = Column(String(64), nullable=True)
    source = Column(String(32), nullable=False, default="system")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    profile = relationship("BrowserProfile", back_populates="audits")
