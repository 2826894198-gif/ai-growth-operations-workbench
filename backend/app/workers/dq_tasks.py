import asyncio

from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.ad_performance import AdPerformanceDaily
from app.models.data_quality import DataQualityIssue
from app.workers.celery_app import celery_app


async def _record(db, source_id, rule_code, severity, entity_type, entity_id, date_value, message, context) -> None:
    existing = (
        await db.execute(
            select(DataQualityIssue).where(
                DataQualityIssue.data_source_id == source_id,
                DataQualityIssue.rule_code == rule_code,
                DataQualityIssue.entity_id == entity_id,
                DataQualityIssue.date == date_value,
                DataQualityIssue.status == "OPEN",
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            DataQualityIssue(
                data_source_id=source_id,
                rule_code=rule_code,
                severity=severity,
                entity_type=entity_type,
                entity_id=entity_id,
                date=date_value,
                message=message,
                context=context,
                status="OPEN",
            )
        )


@celery_app.task(name="data_quality.sweep", bind=True)
def dq_sweep(self) -> dict:
    async def _run() -> dict:
        async with async_session_factory() as db:
            rows = (
                await db.execute(
                    select(AdPerformanceDaily).where(
                        AdPerformanceDaily.spend_amount.isnot(None),
                        AdPerformanceDaily.spend_amount < 0,
                    )
                )
            ).scalars().all()
            for row in rows:
                await _record(
                    db, row.data_source_id, "DQ_NEGATIVE_SPEND", "ERROR", row.entity_type,
                    row.external_entity_id, row.date, "negative spend", {"spend": str(row.spend_amount)},
                )
            rows = (
                await db.execute(
                    select(AdPerformanceDaily).where(
                        AdPerformanceDaily.clicks.isnot(None),
                        AdPerformanceDaily.impressions.isnot(None),
                        AdPerformanceDaily.clicks > AdPerformanceDaily.impressions,
                    )
                )
            ).scalars().all()
            for row in rows:
                await _record(
                    db, row.data_source_id, "DQ_IMPRESSIONS_LT_CLICKS", "ERROR", row.entity_type,
                    row.external_entity_id, row.date, "clicks > impressions", {},
                )
            await db.commit()
            return {"negative_spend": 0, "impressions_lt_clicks": 0}

    return asyncio.run(_run())
