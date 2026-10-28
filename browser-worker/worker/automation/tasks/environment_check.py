import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from worker.automation.base import BaseAutomationTask, TaskContext
from worker.automation.screenshot import save_screenshot

logger = logging.getLogger(__name__)


def _evaluate_status(
    *,
    country: Optional[str],
    timezone: Optional[str],
    language: Optional[str],
    expected_country: Optional[str],
    expected_timezone: Optional[str],
    expected_language: Optional[str],
    api_ok: bool = True,
    proxy_ok: bool = True,
) -> Dict[str, Any]:
    checks = {
        "api": {"ok": api_ok},
        "proxy": {"ok": proxy_ok},
        "country": {"ok": country == "US", "expected": "US"},
        "page_load": {"ok": True},
        "timezone": {"ok": not expected_timezone or timezone == expected_timezone, "expected": expected_timezone},
        "language": {"ok": not expected_language or (language or "").lower() == expected_language.lower(), "expected": expected_language},
    }
    reasons = [name for name, check in checks.items() if not check["ok"]]
    if reasons:
        status = "UNHEALTHY" if any(name in ("api", "proxy", "country", "page_load") for name in reasons) else "DEGRADED"
    else:
        status = "HEALTHY"
    return {"status": status, "checks": checks, "reasons": reasons}


class EnvironmentCheckTask(BaseAutomationTask):
    task_type = "environment_check"

    async def run(self, ctx: TaskContext) -> Dict[str, Any]:
        url = ctx.payload.get("url") or ctx.diagnostic_url
        response = await ctx.page.goto(url, wait_until="domcontentloaded")
        if response is None:
            raise RuntimeError("diagnostic page did not respond")

        raw: Optional[Dict[str, Any]] = None
        try:
            raw = await response.json()
        except Exception:  # noqa: BLE001 - fall back to parsing body text
            raw = json.loads(await ctx.page.inner_text("body"))

        public_ip = (raw or {}).get("ip")
        country = (raw or {}).get("country")
        tz = (raw or {}).get("timezone")
        language = await ctx.page.evaluate("navigator.language")

        expected_country = ctx.profile.get("country") or "US"
        expected_tz = ctx.profile.get("timezone")
        expected_language = ctx.profile.get("language") or "en-US"
        evaluation = _evaluate_status(
            country=country,
            timezone=tz,
            language=language,
            expected_country=expected_country,
            expected_timezone=expected_tz,
            expected_language=expected_language,
        )
        screenshot_path = await save_screenshot(ctx.page, ctx.screenshot_dir, f"env_{ctx.task_id}")
        return {
            "environment": {
                "status": evaluation["status"],
                "public_ip": public_ip,
                "country": country,
                "timezone": tz,
                "language": language,
                "checks": evaluation["checks"],
                "reasons": evaluation["reasons"],
                "expected": {
                    "country": expected_country,
                    "timezone": expected_tz,
                    "language": expected_language,
                },
            },
            "page": {
                "url": url,
                "final_url": ctx.page.url,
                "title": await ctx.page.title(),
                "screenshot_path": screenshot_path,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
