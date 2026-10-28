import logging
from datetime import datetime, timedelta
from datetime import timezone as utc_timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.browser_profile import BrowserProfile
from app.models.browser_task import BrowserTask
from app.models.environment_health import EnvironmentHealthCheck
from app.schemas.environment import AlertOut, EnvironmentOverviewOut
from app.services.health_evaluator import HealthEvaluator

logger = logging.getLogger(__name__)


class EnvironmentHealthService:
    def __init__(self, evaluator: Optional[HealthEvaluator] = None):
        self.evaluator = evaluator or HealthEvaluator()

    async def save_check(
        self,
        db: AsyncSession,
        profile_id: str,
        *,
        status: str,
        public_ip: Optional[str] = None,
        country: Optional[str] = None,
        timezone: Optional[str] = None,
        language: Optional[str] = None,
        proxy_latency_ms: Optional[int] = None,
        browser_launch_ms: Optional[int] = None,
        checks: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
    ) -> EnvironmentHealthCheck:
        check = EnvironmentHealthCheck(
            profile_id=profile_id,
            status=status,
            public_ip=public_ip,
            country=country,
            timezone=timezone,
            language=language,
            proxy_latency_ms=proxy_latency_ms,
            browser_launch_ms=browser_launch_ms,
            checks=checks,
            created_at=created_at or datetime.now(utc_timezone.utc),
        )
        db.add(check)
        profile = (
            await db.execute(select(BrowserProfile).where(BrowserProfile.id == profile_id))
        ).scalar_one_or_none()
        if profile:
            profile.last_health_check_at = check.created_at
        await db.commit()
        await db.refresh(check)
        return check

    async def baseline(self, db: AsyncSession, profile_id: str) -> Optional[EnvironmentHealthCheck]:
        return (
            await db.execute(
                select(EnvironmentHealthCheck)
                .where(EnvironmentHealthCheck.profile_id == profile_id)
                .order_by(EnvironmentHealthCheck.created_at.asc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def detect_drift(
        self, db: AsyncSession, profile_id: str, latest: Optional[EnvironmentHealthCheck] = None
    ) -> List[Dict[str, Any]]:
        if latest is None:
            latest = (
                await db.execute(
                    select(EnvironmentHealthCheck)
                    .where(EnvironmentHealthCheck.profile_id == profile_id)
                    .order_by(EnvironmentHealthCheck.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
        baseline = await self.baseline(db, profile_id)
        if baseline is None or latest is None or baseline.id == latest.id:
            return []

        drift: List[Dict[str, Any]] = []
        for field, old, new in (
            ("country", baseline.country, latest.country),
            ("timezone", baseline.timezone, latest.timezone),
            ("language", baseline.language, latest.language),
        ):
            if old and new and old != new:
                drift.append(
                    {
                        "field": field,
                        "old_value": old,
                        "new_value": new,
                        "severity": "CRITICAL" if field == "country" else "WARNING",
                    }
                )
        return drift

    async def overview(self, db: AsyncSession) -> EnvironmentOverviewOut:
        profiles = (await db.execute(select(BrowserProfile))).scalars().all()
        total = len(profiles)
        healthy = 0
        unhealthy = 0
        for profile in profiles:
            latest_status = (
                await db.execute(
                    select(EnvironmentHealthCheck.status)
                    .where(EnvironmentHealthCheck.profile_id == profile.id)
                    .order_by(desc(EnvironmentHealthCheck.created_at))
                    .limit(1)
                )
            ).scalar_one_or_none()
            if latest_status == "HEALTHY":
                healthy += 1
            elif latest_status == "UNHEALTHY":
                unhealthy += 1
        running = sum(1 for p in profiles if p.status == "RUNNING")
        queued = (
            await db.execute(select(func.count()).select_from(BrowserTask).where(BrowserTask.status == "QUEUED"))
        ).scalar_one()
        failed = (
            await db.execute(select(func.count()).select_from(BrowserTask).where(BrowserTask.status == "FAILED"))
        ).scalar_one()
        return EnvironmentOverviewOut(
            total_profiles=total,
            healthy_profiles=healthy,
            unhealthy_profiles=unhealthy,
            running_browsers=running,
            queued_tasks=queued,
            failed_tasks=failed,
        )

    async def alerts(self, db: AsyncSession) -> List[AlertOut]:
        alerts: List[AlertOut] = []
        now = datetime.now(utc_timezone.utc)
        profiles = (await db.execute(select(BrowserProfile))).scalars().all()
        for profile in profiles:
            latest = (
                await db.execute(
                    select(EnvironmentHealthCheck)
                    .where(EnvironmentHealthCheck.profile_id == profile.id)
                    .order_by(desc(EnvironmentHealthCheck.created_at))
                    .limit(1)
                )
            ).scalar_one_or_none()
            drift = await self.detect_drift(db, profile.id, latest)
            for item in drift:
                severity = "CRITICAL" if item["severity"] == "CRITICAL" else "WARNING"
                alerts.append(
                    AlertOut(
                        severity=severity,
                        code=item["field"].upper() + "_DRIFT",
                        message=f"{profile.name} {item['field']} changed from {item['old_value']} to {item['new_value']}",
                        profile_id=profile.id,
                        profile_name=profile.name,
                        created_at=now,
                    )
                )
            if latest and latest.status == "UNHEALTHY":
                alerts.append(
                    AlertOut(
                        severity="CRITICAL",
                        code="ENVIRONMENT_UNHEALTHY",
                        message=f"{profile.name} environment is unhealthy: {latest.status}",
                        profile_id=profile.id,
                        profile_name=profile.name,
                        created_at=latest.created_at,
                    )
                )

            # 3 consecutive browser launch failures
            recent_tasks = (
                (
                    await db.execute(
                        select(BrowserTask)
                        .where(
                            BrowserTask.profile_id == profile.id,
                            BrowserTask.status == "FAILED",
                            BrowserTask.error_code.in_(
                                ["PROFILE_START_FAILED", "CDP_CONNECTION_FAILED", "ADSPOWER_UNAVAILABLE"]
                            ),
                            BrowserTask.finished_at >= now - timedelta(hours=24),
                        )
                        .order_by(desc(BrowserTask.finished_at))
                        .limit(3)
                    )
                )
                .scalars()
                .all()
            )
            if len(recent_tasks) >= 3:
                alerts.append(
                    AlertOut(
                        severity="WARNING",
                        code="CONSECUTIVE_LAUNCH_FAILURES",
                        message=f"{profile.name} had 3 consecutive browser launch failures",
                        profile_id=profile.id,
                        profile_name=profile.name,
                        created_at=recent_tasks[0].finished_at or now,
                    )
                )
        return alerts
