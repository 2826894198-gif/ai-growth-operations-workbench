from datetime import datetime, timezone
from typing import Any, Dict

from worker.automation.base import BaseAutomationTask, TaskContext
from worker.automation.screenshot import save_screenshot


class PublicPageSnapshotTask(BaseAutomationTask):
    task_type = "public_page_snapshot"

    async def run(self, ctx: TaskContext) -> Dict[str, Any]:
        url = ctx.payload.get("url")
        if not url:
            raise ValueError("payload.url is required")
        response = await ctx.page.goto(url, wait_until="domcontentloaded")
        if response is None:
            raise RuntimeError("page did not respond")
        screenshot_path = await save_screenshot(ctx.page, ctx.screenshot_dir, f"snap_{ctx.task_id}")
        return {
            "title": await ctx.page.title(),
            "final_url": ctx.page.url,
            "screenshot_path": screenshot_path,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "http_status": response.status,
        }
