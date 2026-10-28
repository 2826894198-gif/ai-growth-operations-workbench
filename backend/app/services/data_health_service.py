from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_quality import DataQualityIssue
from app.models.data_source import DataSource
from app.models.raw import RawWebhookEvent
from app.models.sync import SyncJob


def _ensure_aware(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class DataHealthService:
    @staticmethod
    def _workspace_filter(workspace_id: str):
        # Null rows are allowed only for the legacy ws_main compatibility
        # window.  New rows are always workspace-scoped.
        if workspace_id == "ws_main":
            return or_(DataSource.workspace_id == workspace_id, DataSource.workspace_id.is_(None))
        return DataSource.workspace_id == workspace_id

    async def freshness(self, db: AsyncSession, workspace_id: str = "ws_main") -> List[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        sources = (
            await db.execute(select(DataSource).where(self._workspace_filter(workspace_id)))
        ).scalars().all()
        result = []
        for source in sources:
            if not source.sync_enabled:
                result.append({"provider": source.provider, "name": source.name, "status": "DISABLED"})
                continue
            last = _ensure_aware(source.last_successful_sync_at)
            lag = (now - last).total_seconds() if last else None
            if lag is None:
                status = "UNKNOWN"
            elif source.provider == "SHOPIFY" and lag <= 120:
                status = "FRESH"
            elif lag <= 1200:
                status = "FRESH"
            elif lag <= 3600:
                status = "DELAYED"
            elif lag <= 86400:
                status = "STALE"
            else:
                status = "STALE"
            result.append(
                {
                    "provider": source.provider,
                    "name": source.name,
                    "workspace_id": source.workspace_id or "ws_main",
                    "status": status,
                    "last_successful_sync_at": last.isoformat() if last else None,
                    "sync_lag_seconds": lag,
                    "last_failed_sync_at": source.last_failed_sync_at.isoformat() if source.last_failed_sync_at else None,
                }
            )
        return result

    async def webhook_lag(
        self,
        db: AsyncSession,
        workspace_id: str = "ws_main",
    ) -> Dict[str, Any]:
        # Raw webhook rows predate workspace ownership.  Do not expose the
        # legacy global stream to any newly introduced workspace until the
        # provider connection mapping is migrated in a later contract step.
        if workspace_id != "ws_main":
            return {
                "latest_webhook_at": None,
                "lag_seconds": None,
                "processed": True,
                "scope_status": "UNAVAILABLE",
                "note": "当前工作区尚未建立 Webhook 归属映射",
            }
        now = datetime.now(timezone.utc)
        latest = (
            await db.execute(
                select(RawWebhookEvent)
                .where(RawWebhookEvent.provider == "SHOPIFY")
                .order_by(RawWebhookEvent.received_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest is None:
            return {"latest_webhook_at": None, "lag_seconds": None, "processed": True}
        lag = (now - _ensure_aware(latest.received_at)).total_seconds()
        return {
            "latest_webhook_at": latest.received_at.isoformat(),
            "lag_seconds": round(lag, 1),
            "processed": latest.processed,
        }

    async def quality(self, db: AsyncSession, workspace_id: str = "ws_main") -> Dict[str, Any]:
        issues = (
            await db.execute(
                select(
                    DataQualityIssue.rule_code,
                    DataQualityIssue.severity,
                    func.count(DataQualityIssue.id).label("count"),
                )
                .join(DataSource, DataSource.id == DataQualityIssue.data_source_id)
                .where(DataQualityIssue.status == "OPEN")
                .where(self._workspace_filter(workspace_id))
                .group_by(DataQualityIssue.rule_code, DataQualityIssue.severity)
            )
        ).all()
        return {
            "open_issues": [
                {"rule_code": row.rule_code, "severity": row.severity, "count": row.count} for row in issues
            ],
            "total_open": sum(row.count for row in issues),
        }

    async def recent_jobs(
        self,
        db: AsyncSession,
        limit: int = 10,
        workspace_id: str = "ws_main",
    ) -> List[Dict[str, Any]]:
        jobs = (
            await db.execute(
                select(SyncJob)
                .join(DataSource, DataSource.id == SyncJob.data_source_id)
                .where(self._workspace_filter(workspace_id))
                .order_by(SyncJob.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
        return [
            {
                "id": str(job.id),
                "provider": job.provider,
                "job_type": job.job_type,
                "status": job.status,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            }
            for job in jobs
        ]
