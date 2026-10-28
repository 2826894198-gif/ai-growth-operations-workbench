from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict


class HealthCheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    status: str
    public_ip: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    proxy_latency_ms: Optional[int] = None
    browser_launch_ms: Optional[int] = None
    checks: Optional[Dict[str, Any]] = None
    created_at: datetime


class EnvironmentOverviewOut(BaseModel):
    total_profiles: int
    healthy_profiles: int
    unhealthy_profiles: int
    running_browsers: int
    queued_tasks: int
    failed_tasks: int


class AlertOut(BaseModel):
    severity: str
    code: str
    message: str
    profile_id: Optional[str] = None
    profile_name: Optional[str] = None
    created_at: datetime
