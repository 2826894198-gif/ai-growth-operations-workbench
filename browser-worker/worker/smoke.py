import os
from typing import Any, Dict, List, Optional, Tuple

import httpx

from worker.adspower import AdsPowerClient
from worker.automation.page_guard import PageGuard
from worker.automation.playwright_adapter import PlaywrightAdapter
from worker.automation.screenshot import save_screenshot
from worker.config import get_settings


def _row(name: str, ok: bool, detail: str = "") -> Tuple[str, bool, str]:
    return name, ok, detail


async def _proxy_http_check(proxy: Dict[str, Any], url: str, timeout: float = 10.0) -> Dict[str, Any]:
    scheme = proxy.get("proxy_type") or "http"
    auth = ""
    if proxy.get("username") or proxy.get("password"):
        auth = f"{proxy['username']}:{proxy['password']}@"
    proxy_url = f"{scheme}://{auth}{proxy['host']}:{proxy['port']}"
    async with httpx.AsyncClient(proxy=proxy_url, timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


async def run_smoke() -> int:
    settings = get_settings()
    results: List[Tuple[str, bool, str]] = []
    ads = AdsPowerClient(
        settings.adspower_base_url,
        settings.adspower_api_key,
        max_concurrency=settings.adspower_max_concurrency,
        requests_per_second=settings.adspower_requests_per_second,
    )
    try:
        # 1. AdsPower API
        try:
            health = await ads.health_check()
            results.append(_row("AdsPower API", True, f"{health['latency_ms']}ms"))
        except Exception as exc:  # noqa: BLE001
            results.append(_row("AdsPower API", False, str(exc)))
            return _print(results)

        # 2. Profile found
        test_profile_id = os.getenv("SMOKE_PROFILE_ID") or os.getenv("TEST_PROFILE_ID", "")
        test_profile_name = os.getenv("SMOKE_PROFILE_NAME", "")
        profiles = (await ads.list_profiles()).get("list") or []
        profile: Optional[Dict[str, Any]] = None
        if test_profile_id:
            profile = next((p for p in profiles if p.get("profile_id") == test_profile_id), None)
        elif test_profile_name:
            profile = next((p for p in profiles if p.get("name") == test_profile_name), None)
        else:
            profile = next((p for p in profiles if "test" in (p.get("name") or "").lower()), None)
        if profile is None:
            results.append(_row("Profile Found", False, "no TEST_PROFILE_ID / SMOKE_PROFILE_NAME match"))
            return _print(results)
        results.append(_row("Profile Found", True, f"{profile.get('name')} ({profile.get('profile_id')})"))

        # 3. Proxy
        proxy_config = profile.get("user_proxy_config") or {}
        allow_no_proxy = os.getenv("SMOKE_ALLOW_NO_PROXY", "0") == "1"
        if not proxy_config.get("proxy_host"):
            if allow_no_proxy:
                results.append(_row("Proxy", True, "no proxy bound (SMOKE_ALLOW_NO_PROXY=1)"))
            else:
                results.append(_row("Proxy", False, "profile has no proxy; bind a US proxy"))
                return _print(results)
        else:
            proxy = {
                "proxy_type": proxy_config.get("proxy_type") or "http",
                "host": proxy_config["proxy_host"],
                "port": int(proxy_config.get("proxy_port") or 0),
                "username": proxy_config.get("proxy_user") or "",
                "password": proxy_config.get("proxy_password") or "",
            }
            try:
                ipinfo = await _proxy_http_check(proxy, "https://ipinfo.io/json")
                results.append(_row("Proxy", True, ipinfo.get("ip", "unknown")))
            except Exception as exc:  # noqa: BLE001
                results.append(_row("Proxy", False, str(exc)))
                return _print(results)

            # 4. Country US
            country = (ipinfo.get("country") or "").upper()
            results.append(_row("Country US", country == "US", country or "unknown"))
            if country != "US":
                return _print(results)

        # 5-8. Browser launch / CDP / page load / screenshot
        profile_id = profile["profile_id"]
        start_data = await ads.start_browser(profile_id)
        ws_endpoint = (start_data.get("ws") or {}).get("puppeteer") or (start_data.get("ws") or {}).get("selenium")
        results.append(_row("Browser Launch", bool(ws_endpoint), f"debug_port={start_data.get('debug_port')}"))
        if not ws_endpoint:
            return _print(results)

        try:
            async with PlaywrightAdapter(ws_endpoint) as adapter:
                guard = PageGuard(
                    navigation_timeout_ms=settings.navigation_timeout_ms,
                    allow_private=settings.page_guard_allow_private,
                )
                await guard.apply(adapter.page)
                results.append(_row("CDP Connect", True, "playwright connected"))
                response = await adapter.page.goto(settings.smoke_test_url, wait_until="domcontentloaded")
                results.append(_row("Page Load", response is not None and response.status < 500, str(response.status if response else "no response")))
                screenshot = await save_screenshot(adapter.page, settings.screenshot_dir, "smoke_test")
                results.append(_row("Screenshot", os.path.exists(screenshot), screenshot))
        except Exception as exc:  # noqa: BLE001
            results.append(_row("CDP Connect", False, str(exc)))
            return _print(results)
        finally:
            try:
                await ads.stop_browser(profile_id)
                results.append(_row("Browser Close", True, ""))
            except Exception as exc:  # noqa: BLE001
                results.append(_row("Browser Close", False, str(exc)))
        return _print(results)
    finally:
        await ads.aclose()


def _print(results: List[Tuple[str, bool, str]]) -> int:
    ok = True
    for name, passed, detail in results:
        mark = "PASS" if passed else "FAIL"
        if not passed:
            ok = False
        suffix = f"  {detail}" if detail else ""
        print(f"{mark:<5} {name}{suffix}")
    print("SMOKE TEST " + ("PASSED" if ok else "FAILED"))
    return 0 if ok else 1
