from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProxyCreate(BaseModel):
    provider: str = "manual"
    proxy_type: str = "http"
    host: str = Field(..., min_length=1)
    port: int = Field(..., ge=1, le=65535)
    username: Optional[str] = None
    password: Optional[str] = None
    country: Optional[str] = Field(None, max_length=2)
    region: Optional[str] = None
    city: Optional[str] = None
    is_static: bool = True


class ProxyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider: str
    proxy_type: str
    host: str
    port: int
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    is_static: bool
    status: str
    last_ip: Optional[str] = None
    last_checked_at: Optional[datetime] = None
    latency_ms: Optional[int] = None


class ProxyWithCredentials(ProxyOut):
    """Internal schema returned only to the authenticated browser worker."""

    username: Optional[str] = None
    password: Optional[str] = None
