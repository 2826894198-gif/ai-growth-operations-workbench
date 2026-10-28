from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class BrowserTaskCreate(BaseModel):
    profile_id: str
    task_type: str = Field(..., pattern="^(environment_check|public_page_snapshot|smoke_test)$")
    task_name: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class BrowserTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    task_type: str
    task_name: Optional[str] = None
    status: str
    payload: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    retry_count: int = 0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    log_path: Optional[str] = None
    created_at: datetime


class BrowserTaskListOut(BaseModel):
    items: List[BrowserTaskOut]
    total: int


class BrowserTaskResultUpdate(BaseModel):
    """Worker -> backend result callback body."""

    status: str = Field(..., pattern="^(RUNNING|SUCCESS|FAILED|TIMEOUT|QUEUED)$")
    result: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    log_path: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
