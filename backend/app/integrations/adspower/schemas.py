from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class AdsPowerWsEndpoints(BaseModel):
    selenium: Optional[str] = None
    puppeteer: Optional[str] = None


class StartBrowserData(BaseModel):
    debug_port: Optional[str] = None
    ws: Optional[AdsPowerWsEndpoints] = None
    webdriver: Optional[str] = None


class CreateProfileData(BaseModel):
    profile_id: Optional[str] = None
    message: Optional[str] = None


class ProxyConfig(BaseModel):
    proxy_soft: str = "other"
    proxy_type: Optional[str] = None
    proxy_host: Optional[str] = None
    proxy_port: Optional[str] = None
    proxy_user: Optional[str] = None
    proxy_password: Optional[str] = None


class ProfileListItem(BaseModel):
    profile_id: Optional[str] = None
    name: Optional[str] = None
    group_name: Optional[str] = None
    domain_name: Optional[str] = None
    user_proxy_config: Optional[Dict[str, Any]] = None
    fingerprint_config: Optional[Dict[str, Any]] = None
    created_time: Optional[str] = None
    updated_time: Optional[str] = None


class ProfileListData(BaseModel):
    list: List[ProfileListItem] = []
    page: Optional[int] = None
    page_size: Optional[int] = None
    total: Optional[int] = None
