from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class BrowserTask(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "browser_tasks"

    profile_id = Column(String(36), ForeignKey("browser_profiles.id"), nullable=False, index=True)
    task_type = Column(String(64), nullable=False)
    task_name = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False, default="QUEUED", index=True)
    payload = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    error_code = Column(String(128), nullable=True)
    error_message = Column(Text, nullable=True)
    screenshot_path = Column(Text, nullable=True)
    log_path = Column(Text, nullable=True)

    profile = relationship("BrowserProfile", back_populates="tasks")
