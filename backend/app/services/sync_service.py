from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.orchestrator import run_sync
from app.models.sync import SyncJob


class SyncService:
    async def list_jobs(
        self,
        db: AsyncSession,
        data_source_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[SyncJob]:
        query = select(SyncJob).order_by(SyncJob.created_at.desc()).limit(limit)
        if data_source_id:
            query = query.where(SyncJob.data_source_id == data_source_id)
        if status:
            query = query.where(SyncJob.status == status)
        return list((await db.execute(query)).scalars().all())

    async def get_job(self, db: AsyncSession, job_id: str) -> Optional[SyncJob]:
        return (await db.execute(select(SyncJob).where(SyncJob.id == job_id))).scalar_one_or_none()

    async def retry_job(self, db: AsyncSession, job_id: str) -> SyncJob:
        job = await self.get_job(db, job_id)
        if job is None:
            raise ValueError("sync job not found")
        if job.data_source_id is None:
            raise ValueError("job has no data source")
        return await run_sync(
            db,
            job.provider,
            job.data_source_id,
            job.job_type,
            job.range_start,
            job.range_end,
        )
