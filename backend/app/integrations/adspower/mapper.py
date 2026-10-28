from typing import Any, Dict, Optional

from app.integrations.adspower.schemas import ProxyConfig
from app.models.browser_profile import BrowserProfile
from app.models.proxy import Proxy

# Part 01 fingerprint baseline (see spec section 11).
FINGERPRINT_BASELINE: Dict[str, Any] = {
    "automatic_timezone": "1",
    "location_switch": "1",
    "language_switch": "0",
    "language": ["en-US", "en"],
    "page_language_switch": "0",
    "page_language": "en-US",
    "webrtc": "disabled",
    "canvas": "1",
    "webgl_image": "1",
    "webgl": "3",
    "scan_port_type": "1",
}


def build_create_payload(
    profile: BrowserProfile,
    proxy: Optional[Proxy] = None,
    proxy_username: Optional[str] = None,
    proxy_password: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the AdsPower V2 create-profile payload from internal entities.

    All profile JSON construction is centralized here; business code must not
    assemble AdsPower payloads directly.
    """
    fingerprint = dict(FINGERPRINT_BASELINE)
    if profile.fingerprint_config:
        fingerprint.update(profile.fingerprint_config)
    if profile.timezone:
        fingerprint["timezone"] = profile.timezone

    payload: Dict[str, Any] = {
        "name": profile.name,
        "group_name": profile.profile_type.upper(),
        "domain_name": profile.platform or "",
        "fingerprint_config": fingerprint,
    }
    if proxy:
        payload["user_proxy_config"] = ProxyConfig(
            proxy_soft="other",
            proxy_type=proxy.proxy_type or "http",
            proxy_host=proxy.host,
            proxy_port=str(proxy.port),
            proxy_user=proxy_username or "",
            proxy_password=proxy_password or "",
        ).model_dump()
    return payload


def ads_power_item_to_internal(item: Dict[str, Any]) -> Dict[str, Any]:
    """Map an AdsPower profile list item to internal browser_profiles fields."""
    fingerprint = item.get("fingerprint_config") or {}
    return {
        "provider_profile_id": item.get("profile_id"),
        "name": item.get("name"),
        "platform": item.get("domain_name"),
        "browser_engine": "ads_power_auto",
        "os_type": "auto",
        "fingerprint_config": fingerprint,
        "country": fingerprint.get("country") or "US",
        "timezone": fingerprint.get("timezone"),
        "language": "en-US",
    }


def proxy_url(proxy: Proxy, username: Optional[str] = None, password: Optional[str] = None) -> str:
    scheme = proxy.proxy_type or "http"
    host = proxy.host
    port = proxy.port
    if username or password:
        return f"{scheme}://{username}:{password}@{host}:{port}"
    return f"{scheme}://{host}:{port}"
