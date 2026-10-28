from datetime import datetime, timezone
from typing import Any, Dict

from worker.automation.base import BaseAutomationTask, TaskContext
from worker.automation.screenshot import save_screenshot


class SmokeTestTask(BaseAutomationTask):
    task_type = "smoke_test"

    async def run(self, ctx: TaskContext) -> Dict[str, Any]:
        url = ctx.payload.get("url") or "https://example.com"
        response = await ctx.page.goto(url, wait_until="domcontentloaded")
        if response is None:
            raise RuntimeError("page did not respond")
        title = await ctx.page.title()
        screenshot_path = await save_screenshot(ctx.page, ctx.screenshot_dir, f"smoke_{ctx.task_id}")
        return {
            "title": title,
            "final_url": ctx.page.url,
            "http_status": response.status,
            "screenshot_path": screenshot_path,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
