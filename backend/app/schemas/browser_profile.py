from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.proxy import ProxyOut


class BrowserProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    profile_type: str = Field(..., pattern="^(brand|research|competitor|test)$")
    profile_no: Optional[str] = Field(None, max_length=128)
    platform: Optional[str] = None
    proxy_id: Optional[str] = None
    country: Optional[str] = Field(None, max_length=2)
    region: Optional[str] = None
    city: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    browser_engine: Optional[str] = None
    os_type: Optional[str] = None


class BrowserProfileUpdate(BaseModel):
    name: Optional[str] = None
    profile_type: Optional[str] = Field(None, pattern="^(brand|research|competitor|test)$")
    proxy_id: Optional[str] = None
    country: Optional[str] = Field(None, max_length=2)
    region: Optional[str] = None
    city: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    browser_engine: Optional[str] = None
    os_type: Optional[str] = None


class BrowserProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider: str
    provider_profile_id: Optional[str] = None
    profile_no: Optional[str] = None
    name: str
    profile_type: str
    platform: Optional[str] = None
    proxy_id: Optional[str] = None
    proxy: Optional[ProxyOut] = None
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    browser_engine: Optional[str] = None
    os_type: Optional[str] = None
    fingerprint_config: Optional[Dict[str, Any]] = None
    status: str
    health: Optional[str] = None
    last_health_check_at: Optional[datetime] = None
    last_opened_at: Optional[datetime] = None
    last_closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class BrowserProfileStatusOut(BaseModel):
    id: str
    name: str
    status: str
    running: bool
    provider_profile_id: Optional[str] = None
    last_opened_at: Optional[datetime] = None
    last_closed_at: Optional[datetime] = None


class ProfileListItemOut(BaseModel):
    id: str
    name: str
    profile_type: str
    country: Optional[str] = None
    city: Optional[str] = None
    proxy: Optional[ProxyOut] = None
    status: str
    last_health_check_at: Optional[datetime] = None


class ProfileDetailOut(BrowserProfileOut):
    audits: List[dict] = Field(default_factory=list)
    health_checks: List[dict] = Field(default_factory=list)
    recent_tasks: List[dict] = Field(default_factory=list)
