import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.orchestrator import run_connection_test
from app.models.data_source import DataSource
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class DataSourceService:
    async def list_sources(
        self,
        db: AsyncSession,
        provider: Optional[str] = None,
        workspace_id: str = "ws_main",
    ) -> List[DataSource]:
        query = select(DataSource).where(DataSource.workspace_id == workspace_id).order_by(DataSource.created_at.asc())
        if provider:
            query = query.where(DataSource.provider == provider)
        return list((await db.execute(query)).scalars().all())

    async def get_source(self, db: AsyncSession, source_id: str) -> Optional[DataSource]:
        return (await db.execute(select(DataSource).where(DataSource.id == source_id))).scalar_one_or_none()

    async def create_source(
        self,
        db: AsyncSession,
        *,
        workspace_id: str = "ws_main",
        provider: str,
        name: str,
        external_account_id: Optional[str] = None,
        external_account_name: Optional[str] = None,
        credential_reference: Optional[str] = None,
        api_version: Optional[str] = None,
        timezone: Optional[str] = None,
        currency: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> DataSource:
        source = DataSource(
            workspace_id=workspace_id,
            provider=provider.upper(),
            name=name,
            external_account_id=external_account_id,
            external_account_name=external_account_name,
            credential_reference=credential_reference,
            api_version=api_version,
            timezone=timezone,
            currency=currency,
            status="UNKNOWN",
            sync_enabled=True,
            meta=metadata or {},
        )
        db.add(source)
        await db.commit()
        await db.refresh(source)
        return source

    async def validate(self, db: AsyncSession, source_id: str) -> dict:
        source = await self.get_source(db, source_id)
        if source is None:
            raise ValueError("data source not found")
        return await run_connection_test(db, source.provider, source_id)

    def enqueue_sync(self, source: DataSource, job_type: str, days: Optional[int] = None) -> None:
        queue = {
            "META_ADS": "meta",
            "GOOGLE_ADS": "google",
            "SHOPIFY": "shopify",
        }.get(source.provider, "etl")
        celery_app.send_task(
            "ingestion.run_sync_task",
            args=[source.provider, str(source.id), job_type],
            kwargs={"days": days} if days else {},
            queue=queue,
        )

    def enqueue_backfill(self, source: DataSource, days: Optional[int] = None) -> None:
        celery_app.send_task(
            "ingestion.run_backfill_task",
            args=[source.provider, str(source.id)],
            kwargs={"days": days} if days else {},
            queue="backfill",
        )
