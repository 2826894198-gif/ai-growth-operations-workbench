from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.mixins import UUIDPrimaryKeyMixin


class EnvironmentHealthCheck(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "environment_health_checks"

    profile_id = Column(String(36), ForeignKey("browser_profiles.id"), nullable=False, index=True)
    status = Column(String(32), nullable=False)
    public_ip = Column(String(64), nullable=True)
    country = Column(String(2), nullable=True)
    timezone = Column(String(128), nullable=True)
    language = Column(String(128), nullable=True)
    proxy_latency_ms = Column(Integer, nullable=True)
    browser_launch_ms = Column(Integer, nullable=True)
    checks = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)

    profile = relationship("BrowserProfile", back_populates="health_checks")
