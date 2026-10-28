from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class DataSourceCreate(BaseModel):
    workspace_id: str = "ws_main"
    provider: str = Field(..., pattern="^(META_ADS|GOOGLE_ADS|SHOPIFY)$")
    name: str = Field(..., min_length=1, max_length=255)
    external_account_id: Optional[str] = None
    external_account_name: Optional[str] = None
    credential_reference: Optional[str] = None
    api_version: Optional[str] = None
    timezone: Optional[str] = None
    currency: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default=None, validation_alias="meta")


class DataSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: Optional[str] = None
    provider: str
    name: str
    external_account_id: Optional[str] = None
    external_account_name: Optional[str] = None
    status: str
    api_version: Optional[str] = None
    timezone: Optional[str] = None
    currency: Optional[str] = None
    credential_reference: Optional[str] = None
    sync_enabled: bool
    last_successful_sync_at: Optional[datetime] = None
    last_failed_sync_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = Field(default=None, validation_alias="meta")
    created_at: datetime


class SyncJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    data_source_id: Optional[str] = None
    provider: str
    job_type: str
    status: str
    range_start: Optional[str] = None
    range_end: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    records_received: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    records_failed: int = 0
    api_requests: int = 0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
