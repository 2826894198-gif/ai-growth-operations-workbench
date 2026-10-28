import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.browser_profile import BrowserProfile
from app.models.browser_task import BrowserTask
from app.schemas.browser_task import BrowserTaskCreate, BrowserTaskResultUpdate
from app.services.environment_health_service import EnvironmentHealthService
from app.workers.browser_worker import enqueue_browser_task

logger = logging.getLogger(__name__)


class BrowserTaskService:
    def __init__(self, health_service: Optional[EnvironmentHealthService] = None):
        self.health_service = health_service or EnvironmentHealthService()

    async def create_task(self, db: AsyncSession, data: BrowserTaskCreate) -> BrowserTask:
        profile = (
            await db.execute(select(BrowserProfile).where(BrowserProfile.id == data.profile_id))
        ).scalar_one_or_none()
        if profile is None:
            raise ValueError("profile not found")
        if data.task_type == "public_page_snapshot":
            url = (data.payload or {}).get("url", "")
            if not url.startswith(("http://", "https://")):
                raise ValueError("public_page_snapshot requires a valid http(s) url in payload")
        if data.task_type in ("environment_check", "smoke_test") and profile.status == "RUNNING":
            # A running browser is fine; the worker will attach to the same profile.
            pass

        task = BrowserTask(
            profile_id=data.profile_id,
            task_type=data.task_type,
            task_name=data.task_name or data.task_type,
            status="QUEUED",
            payload=data.payload or {},
            retry_count=0,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        enqueue_browser_task(str(task.id))
        return task

    async def list_tasks(
        self, db: AsyncSession, profile_id: Optional[str] = None, status: Optional[str] = None, limit: int = 50
    ) -> List[BrowserTask]:
        query = select(BrowserTask).order_by(BrowserTask.created_at.desc()).limit(limit)
        if profile_id:
            query = query.where(BrowserTask.profile_id == profile_id)
        if status:
            query = query.where(BrowserTask.status == status)
        return list((await db.execute(query)).scalars().all())

    async def get_task(self, db: AsyncSession, task_id: str) -> Optional[BrowserTask]:
        return (await db.execute(select(BrowserTask).where(BrowserTask.id == task_id))).scalar_one_or_none()

    async def update_result(self, db: AsyncSession, task_id: str, update: BrowserTaskResultUpdate) -> BrowserTask:
        task = await self.get_task(db, task_id)
        if task is None:
            raise ValueError("task not found")
        task.status = update.status
        if update.result is not None:
            task.result = update.result
        task.error_code = update.error_code
        task.error_message = update.error_message
        task.screenshot_path = update.screenshot_path
        task.log_path = update.log_path
        if update.started_at:
            task.started_at = update.started_at
        if update.finished_at:
            task.finished_at = update.finished_at
        if update.status in ("SUCCESS", "FAILED", "TIMEOUT"):
            task.finished_at = update.finished_at or datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(task)

        if update.status == "SUCCESS" and update.result and update.result.get("environment"):
            env = update.result["environment"]
            await self.health_service.save_check(
                db,
                task.profile_id,
                status=env.get("status", "UNKNOWN"),
                public_ip=env.get("public_ip"),
                country=env.get("country"),
                timezone=env.get("timezone"),
                language=env.get("language"),
                proxy_latency_ms=env.get("proxy_latency_ms"),
                browser_launch_ms=env.get("browser_launch_ms"),
                checks=env.get("checks"),
            )
        return task

    async def cancel_task(self, db: AsyncSession, task_id: str) -> BrowserTask:
        task = await self.get_task(db, task_id)
        if task is None:
            raise ValueError("task not found")
        if task.status == "RUNNING":
            raise ValueError("running tasks cannot be cancelled in Part 01")
        task.status = "CANCELLED"
        task.finished_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(task)
        return task

    async def requeue(self, db: AsyncSession, task_id: str) -> BrowserTask:
        task = await self.get_task(db, task_id)
        if task is None:
            raise ValueError("task not found")
        if task.retry_count >= settings.browser_task_max_retries:
            task.status = "FAILED"
            task.error_code = "PROFILE_LOCKED"
            task.error_message = "max retries exceeded while waiting for profile lock"
            await db.commit()
            await db.refresh(task)
            return task
        task.status = "QUEUED"
        task.retry_count += 1
        await db.commit()
        await db.refresh(task)
        enqueue_browser_task(str(task.id), countdown=task.retry_count * 3)
        return task

    async def worker_task(self, db: AsyncSession, task_id: str) -> Optional[Dict[str, Any]]:
        task = await self.get_task(db, task_id)
        if task is None:
            return None
        profile = (
            await db.execute(select(BrowserProfile).where(BrowserProfile.id == task.profile_id))
        ).scalar_one_or_none()
        if profile is None:
            return None
        from app.core.security import decrypt_secret

        proxy = profile.proxy
        proxy_payload = None
        if proxy:
            proxy_payload = {
                "id": proxy.id,
                "proxy_type": proxy.proxy_type,
                "host": proxy.host,
                "port": proxy.port,
                "username": decrypt_secret(proxy.username_encrypted),
                "password": decrypt_secret(proxy.password_encrypted),
                "country": proxy.country,
            }
        return {
            "task": {
                "id": str(task.id),
                "profile_id": str(task.profile_id),
                "task_type": task.task_type,
                "task_name": task.task_name,
                "status": task.status,
                "payload": task.payload or {},
                "retry_count": task.retry_count,
            },
            "profile": {
                "id": str(profile.id),
                "provider_profile_id": profile.provider_profile_id,
                "name": profile.name,
                "profile_type": profile.profile_type,
                "country": profile.country,
                "timezone": profile.timezone,
                "language": profile.language,
            },
            "proxy": proxy_payload,
        }
