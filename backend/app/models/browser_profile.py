from sqlalchemy import JSON, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class BrowserProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "browser_profiles"

    provider = Column(String(32), nullable=False, default="adspower")
    provider_profile_id = Column(String(128), unique=True, nullable=True)
    profile_no = Column(String(128), nullable=True)
    name = Column(String(255), nullable=False)
    profile_type = Column(String(32), nullable=False, index=True)
    platform = Column(String(64), nullable=True)
    proxy_id = Column(String(36), ForeignKey("proxies.id"), nullable=True)
    country = Column(String(2), nullable=True)
    region = Column(String(128), nullable=True)
    city = Column(String(128), nullable=True)
    timezone = Column(String(128), nullable=True)
    language = Column(String(64), nullable=True)
    browser_engine = Column(String(32), nullable=True)
    os_type = Column(String(32), nullable=True)
    fingerprint_config = Column(JSON, nullable=True)
    status = Column(String(32), nullable=False, default="INACTIVE", index=True)
    last_health_check_at = Column(DateTime(timezone=True), nullable=True)
    last_opened_at = Column(DateTime(timezone=True), nullable=True)
    last_closed_at = Column(DateTime(timezone=True), nullable=True)

    proxy = relationship("Proxy", lazy="joined")
    tasks = relationship("BrowserTask", back_populates="profile", lazy="selectin")
    audits = relationship("BrowserProfileAudit", back_populates="profile", lazy="selectin")
    health_checks = relationship("EnvironmentHealthCheck", back_populates="profile", lazy="selectin")
