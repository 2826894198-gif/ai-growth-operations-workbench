from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Proxy(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "proxies"

    provider = Column(String(64), nullable=False, default="manual")
    proxy_type = Column(String(16), nullable=False, default="http")
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    username_encrypted = Column(String(2048), nullable=False, default="")
    password_encrypted = Column(String(2048), nullable=False, default="")
    country = Column(String(2), nullable=True)
    region = Column(String(128), nullable=True)
    city = Column(String(128), nullable=True)
    is_static = Column(Boolean, nullable=False, default=True)
    status = Column(String(32), nullable=False, default="UNKNOWN", index=True)
    last_ip = Column(String(64), nullable=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    latency_ms = Column(Integer, nullable=True)
