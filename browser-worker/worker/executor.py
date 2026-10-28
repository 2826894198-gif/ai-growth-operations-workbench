import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from worker.adspower import (
    AdsPowerAuthFailed,
    AdsPowerClient,
    AdsPowerUnavailable,
    ProfileNotFound,
    ProfileStartFailed,
    ProfileStopFailed,
)
from worker.api_client import BackendApiClient
from worker.automation.base import TaskContext
from worker.automation.page_guard import PageGuard
from worker.automation.playwright_adapter import PlaywrightAdapter
from worker.automation.tasks import get_task_handler
from worker.config import get_settings
from worker.locking import RedisLockManager
from worker.observability.logger import configure_logging, redact, set_log_context
from worker.observability.metrics import metrics

logger = logging.getLogger(__name__)


def map_error(exc: Exception) -> str:
    if isinstance(exc, AdsPowerUnavailable):
        return "ADSPOWER_UNAVAILABLE"
    if isinstance(exc, AdsPowerAuthFailed):
        return "ADSPOWER_AUTH_FAILED"
    if isinstance(exc, ProfileNotFound):
        return "PROFILE_NOT_FOUND"
    if isinstance(exc, ProfileStartFailed):
        return "PROFILE_START_FAILED"
    if isinstance(exc, ProfileStopFailed):
        return "PROFILE_STOP_FAILED"
    if isinstance(exc, asyncio.TimeoutError):
        return "BROWSER_TASK_TIMEOUT"
    message = str(exc).lower()
    if "cdp" in message or "connect_over_cdp" in message:
        return "CDP_CONNECTION_FAILED"
    if "proxy" in message:
        return "PROXY_UNAVAILABLE"
    if "timezone" in message:
        return "ENV_TIMEZONE_MISMATCH"
    if "language" in message:
        return "ENV_LANGUAGE_MISMATCH"
    return "BROWSER_TASK_FAILED"


async def _check_proxy(
    proxy: Dict[str, Any],
    timeout: float = 10.0,
) -> Dict[str, Any]:
    scheme = proxy.get("proxy_type") or "http"
    user = proxy.get("username") or ""
    password = proxy.get("password") or ""
    host = proxy["host"]
    port = proxy["port"]
    auth = f"{user}:{password}@" if user or password else ""
    url = f"{scheme}://{auth}{host}:{port}"
    started = time.monotonic()
    async with httpx.AsyncClient(proxy=url, timeout=timeout) as client:
        response = await client.get("https://api.ipify.org?format=json")
        response.raise_for_status()
        return {
            "ok": True,
            "ip": response.json().get("ip"),
            "latency_ms": int((time.monotonic() - started) * 1000),
        }


async def execute_task(task_id: str) -> Dict[str, Any]:
    settings = get_settings()
    configure_logging(settings.log_level, settings.service_name)
    set_log_context(task_id=task_id)
    api = BackendApiClient(settings.backend_api_url, settings.worker_token)
    ads = AdsPowerClient(
        settings.adspower_base_url,
        settings.adspower_api_key,
        max_concurrency=settings.adspower_max_concurrency,
        requests_per_second=settings.adspower_requests_per_second,
    )
    lock_mgr = RedisLockManager(settings.redis_url)
    metrics.inc("worker_tasks_total")

    try:
        data = await api.get_task(task_id)
    except Exception as exc:
        logger.exception("failed to claim task from backend", extra={"event": "task_claim_failed"})
        metrics.inc("worker_claim_failures_total")
        await api.aclose()
        await ads.aclose()
        await lock_mgr.close()
        return {"status": "FAILED", "task_id": task_id, "error_code": "BACKEND_UNAVAILABLE", "detail": str(exc)}

    task = data["task"]
    profile = data["profile"]
    proxy = data.get("proxy")
    set_log_context(task_id=task_id, profile_id=profile["id"])
    logger.info("task claimed", extra={"event": "task_claimed", "task_type": task["task_type"]})

    ttl_ms = (settings.task_timeout_seconds + settings.lock_margin_seconds) * 1000
    acquired, token = await lock_mgr.acquire(profile["id"], ttl_ms=ttl_ms)
    if not acquired:
        logger.warning("profile lock busy; requeueing", extra={"event": "profile_locked"})
        try:
            await api.requeue(task_id)
        except Exception:
            logger.exception("failed to requeue task", extra={"event": "requeue_failed"})
        await api.aclose()
        await ads.aclose()
        await lock_mgr.close()
        return {"status": "REQUEUED", "task_id": task_id}

    started_at = datetime.now(timezone.utc)
    started_browser = False
    result: Dict[str, Any] = {}
    status = "SUCCESS"
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    try:
        await api.update_task(task_id, "RUNNING", started_at=started_at.isoformat())

        if not profile.get("provider_profile_id"):
            raise ProfileNotFound("profile has no AdsPower provider_profile_id")
        if proxy and proxy.get("country") and proxy["country"].upper() != "US":
            raise RuntimeError("proxy country mismatch")

        proxy_check = None
        if proxy:
            proxy_check = await _check_proxy(proxy)

        launch_started = time.monotonic()
        start_data = await ads.start_browser(profile["provider_profile_id"])
        started_browser = True
        browser_launch_ms = int((time.monotonic() - launch_started) * 1000)

        ws_endpoint = (start_data.get("ws") or {}).get("puppeteer") or (start_data.get("ws") or {}).get("selenium")
        if not ws_endpoint:
            raise RuntimeError("CDP websocket endpoint missing from AdsPower start response")

        guard = PageGuard(
            navigation_timeout_ms=settings.navigation_timeout_ms,
            allow_private=settings.page_guard_allow_private,
        )
        if task["task_type"] == "public_page_snapshot":
            await guard.validate_url((task.get("payload") or {}).get("url", ""))

        handler = get_task_handler(task["task_type"])
        async with PlaywrightAdapter(ws_endpoint) as adapter:
            await guard.apply(adapter.page)
            ctx = TaskContext(
                task_id=task_id,
                profile=profile,
                payload=task.get("payload") or {},
                page=adapter.page,
                screenshot_dir=settings.screenshot_dir,
                log_dir=settings.log_dir,
                navigation_timeout_ms=settings.navigation_timeout_ms,
                diagnostic_url=settings.diagnostic_url,
            )
            result = await asyncio.wait_for(
                handler.run(ctx),
                timeout=settings.task_timeout_seconds,
            )

        result["browser_launch_ms"] = browser_launch_ms
        if "environment" in result:
            result["environment"]["browser_launch_ms"] = browser_launch_ms
            result["environment"]["proxy_latency_ms"] = proxy_check["latency_ms"] if proxy_check else None

        await ads.stop_browser(profile["provider_profile_id"])
        started_browser = False

        screenshot_path = result.get("screenshot_path") or result.get("page", {}).get("screenshot_path")
        await api.update_task(
            task_id,
            "SUCCESS",
            result=result,
            screenshot_path=screenshot_path,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        metrics.inc("worker_tasks_succeeded_total")
        logger.info("task succeeded", extra={"event": "task_succeeded", "task_type": task["task_type"]})

    except Exception as exc:
        status = "FAILED"
        error_code = map_error(exc)
        error_message = redact(str(exc))
        logger.exception("task failed", extra={"event": "task_failed", "error_code": error_code})
        if started_browser:
            try:
                await ads.stop_browser(profile["provider_profile_id"])
            except Exception:
                logger.exception("failed to stop browser during error path", extra={"event": "stop_failed"})
        try:
            await api.update_task(
                task_id,
                "FAILED",
                result=result or None,
                error_code=error_code,
                error_message=error_message,
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception:
            logger.exception("failed to report failure to backend", extra={"event": "report_failed"})
        metrics.inc("worker_tasks_failed_total")
    finally:
        try:
            await lock_mgr.release(profile["id"], token)
        except Exception:
            logger.exception("failed to release profile lock", extra={"event": "lock_release_failed"})

    await api.aclose()
    await ads.aclose()
    await lock_mgr.close()
    return {"status": status, "task_id": task_id, "error_code": error_code}
