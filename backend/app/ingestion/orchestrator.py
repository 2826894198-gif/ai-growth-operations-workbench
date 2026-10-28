import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.etl.pipeline import (
    EtlCounts,
    run_google_pipeline,
    run_meta_pipeline,
    run_shopify_pipeline,
)
from app.ingestion.providers import get_provider
from app.integrations.base import (
    ProviderError,
    ProviderRateLimited,
)
from app.models.data_source import DataSource
from app.models.raw import RawApiPayload
from app.models.sync import ProviderApiUsage, SyncJob

logger = logging.getLogger(__name__)


def _request_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


async def _persist_raw(
    db: AsyncSession,
    provider: str,
    data_source_id: Optional[str],
    endpoint: str,
    payload: Any,
    sync_job_id: str,
    api_version: Optional[str] = None,
) -> None:
    db.add(
        RawApiPayload(
            provider=provider,
            data_source_id=data_source_id,
            endpoint=endpoint,
            api_version=api_version,
            request_hash=_request_hash(payload),
            request_metadata={"mode": settings.data_provider_mode},
            payload=payload,
            fetched_at=datetime.now(timezone.utc),
            sync_job_id=sync_job_id,
        )
    )


async def _execute_sync(
    db: AsyncSession,
    provider: str,
    data_source_id: str,
    job_type: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    scenario: Optional[str] = None,
) -> SyncJob:
    source = (
        await db.execute(select(DataSource).where(DataSource.id == data_source_id))
    ).scalar_one_or_none()
    if source is None:
        raise ValueError("data source not found")

    job = SyncJob(
        data_source_id=data_source_id,
        provider=provider,
        job_type=job_type,
        status="RUNNING",
        range_start=start_date,
        range_end=end_date,
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.flush()
    provider_obj = get_provider(provider, scenario=scenario or (source.meta or {}).get("scenario"))
    counts = EtlCounts()
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    status = "SUCCESS"
    api_requests = 0
    try:
        accounts = await provider_obj.sync_accounts()
        api_requests += 1
        await _persist_raw(db, provider, data_source_id, "accounts", accounts, str(job.id), source.api_version)

        dimensions = await provider_obj.sync_dimensions()
        api_requests += 1
        await _persist_raw(db, provider, data_source_id, "dimensions", dimensions, str(job.id), source.api_version)

        if provider == "META_ADS":
            counts = await run_meta_pipeline(
                db,
                data_source_id,
                accounts=accounts,
                campaigns=dimensions.get("campaigns", []),
                ad_groups=dimensions.get("ad_groups", []),
                ads=dimensions.get("ads", []),
                creatives=dimensions.get("creatives", []),
                performance=[],
                sync_job_id=str(job.id),
            )
        elif provider == "GOOGLE_ADS":
            counts = await run_google_pipeline(
                db,
                data_source_id,
                accounts=accounts,
                campaigns=dimensions.get("campaigns", []),
                ad_groups=dimensions.get("ad_groups", []),
                ads=dimensions.get("ads", []),
                asset_groups=dimensions.get("asset_groups", []),
                keywords=dimensions.get("keywords", []),
                search_terms=dimensions.get("search_terms", []),
                conversion_actions=dimensions.get("conversion_actions", []),
                performance=[],
                sync_job_id=str(job.id),
            )
        elif provider == "SHOPIFY":
            counts = await run_shopify_pipeline(
                db,
                data_source_id,
                products=dimensions.get("products", []),
                variants=dimensions.get("variants", []),
                orders=[],
                order_items=[],
                refunds=[],
                journeys=[],
                sync_job_id=str(job.id),
            )

        if start_date and end_date:
            performance = await provider_obj.sync_performance(start_date, end_date)
            api_requests += 1
            await _persist_raw(db, provider, data_source_id, "performance", performance, str(job.id), source.api_version)
            if provider == "META_ADS":
                perf_counts = await run_meta_pipeline(
                    db, data_source_id,
                    accounts=[], campaigns=[], ad_groups=[], ads=[], creatives=[],
                    performance=performance, sync_job_id=str(job.id),
                )
            elif provider == "GOOGLE_ADS":
                perf_counts = await run_google_pipeline(
                    db, data_source_id,
                    accounts=[], campaigns=[], ad_groups=[], ads=[], asset_groups=[],
                    keywords=dimensions.get("keywords", []), search_terms=dimensions.get("search_terms", []),
                    conversion_actions=dimensions.get("conversion_actions", []),
                    performance=performance, sync_job_id=str(job.id),
                )
            else:
                perf_counts = EtlCounts()
            counts.records_received += perf_counts.records_received
            counts.inserted += perf_counts.inserted
            counts.updated += perf_counts.updated
            counts.failed += perf_counts.failed

        if provider == "SHOPIFY" and start_date and end_date:
            commerce = await provider_obj.sync_commerce(start_date, end_date)
            api_requests += 1
            await _persist_raw(db, provider, data_source_id, "commerce", commerce, str(job.id), source.api_version)
            shop_counts = await run_shopify_pipeline(
                db, data_source_id,
                products=[], variants=[],
                orders=commerce.get("orders", []),
                order_items=commerce.get("order_items", []),
                refunds=commerce.get("refunds", []),
                journeys=[],
                sync_job_id=str(job.id),
            )
            counts.records_received += shop_counts.records_received
            counts.inserted += shop_counts.inserted
            counts.updated += shop_counts.updated
            counts.failed += shop_counts.failed

        if counts.failed > 0:
            status = "PARTIAL_SUCCESS"
        source.last_successful_sync_at = datetime.now(timezone.utc)
    except ProviderRateLimited as exc:
        status = "RATE_LIMITED"
        error_code = "PROVIDER_RATE_LIMITED"
        error_message = str(exc)
        source.last_failed_sync_at = datetime.now(timezone.utc)
    except ProviderError as exc:
        status = "FAILED"
        error_code = exc.error_code
        error_message = str(exc)
        source.last_failed_sync_at = datetime.now(timezone.utc)
    except Exception as exc:  # noqa: BLE001
        logger.exception("sync failed", extra={"event": "sync_failed", "provider": provider})
        status = "FAILED"
        error_code = "SYNC_FAILED"
        error_message = str(exc)
        source.last_failed_sync_at = datetime.now(timezone.utc)
    finally:
        job.status = status
        job.finished_at = datetime.now(timezone.utc)
        job.records_received = counts.records_received
        job.records_inserted = counts.inserted
        job.records_updated = counts.updated
        job.records_failed = counts.failed
        job.api_requests = api_requests
        job.error_code = error_code
        job.error_message = error_message
        db.add(
            ProviderApiUsage(
                provider=provider,
                data_source_id=data_source_id,
                window_start=job.started_at,
                window_end=job.finished_at,
                request_count=api_requests,
                success_count=api_requests if status in ("SUCCESS", "PARTIAL_SUCCESS") else 0,
                failure_count=0 if status in ("SUCCESS", "PARTIAL_SUCCESS") else 1,
                rate_limit_count=1 if status == "RATE_LIMITED" else 0,
            )
        )
        await db.commit()
        await db.refresh(job)
    return job


async def run_sync(
    db: AsyncSession,
    provider: str,
    data_source_id: str,
    job_type: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    scenario: Optional[str] = None,
) -> SyncJob:
    return await _execute_sync(db, provider, data_source_id, job_type, start_date, end_date, scenario)


async def run_connection_test(db: AsyncSession, provider: str, data_source_id: str) -> Dict[str, Any]:
    source = (
        await db.execute(select(DataSource).where(DataSource.id == data_source_id))
    ).scalar_one_or_none()
    if source is None:
        raise ValueError("data source not found")
    provider_obj = get_provider(provider, scenario=(source.meta or {}).get("scenario"))
    job = SyncJob(
        data_source_id=data_source_id,
        provider=provider,
        job_type="CONNECTION_TEST",
        status="RUNNING",
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.flush()
    try:
        result = await provider_obj.validate_connection()
        if result.ok:
            job.status = "SUCCESS"
            source.status = "HEALTHY"
            source.currency = result.currency or source.currency
            source.timezone = result.timezone or source.timezone
            source.last_successful_sync_at = datetime.now(timezone.utc)
        else:
            job.status = "FAILED"
            job.error_code = result.error_code or "PROVIDER_ERROR"
            job.error_message = result.message
            source.status = result.error_code or "DEGRADED"
            source.last_failed_sync_at = datetime.now(timezone.utc)
        job.finished_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(job)
        return {"ok": result.ok, "checks": result.checks, "currency": result.currency, "timezone": result.timezone}
    except ProviderError as exc:
        job.status = "FAILED"
        job.error_code = exc.error_code
        job.error_message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        source.status = "AUTH_ERROR" if exc.error_code == "PROVIDER_AUTH_FAILED" else "DEGRADED"
        source.last_failed_sync_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(job)
        return {"ok": False, "checks": {}, "error_code": exc.error_code, "message": str(exc)}
