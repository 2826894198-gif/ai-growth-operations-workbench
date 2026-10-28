"""Retention governance (PART 07 §210-§215)."""

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.governance import RetentionPolicy

RETENTION_SEEDS = [
    {"category": "raw_provider_payload", "description": "Raw immutable provider responses", "retention_days": 180, "action": "DELETE", "pii": False},
    {"category": "webhook_raw", "description": "Raw webhook events", "retention_days": 30, "action": "DELETE", "pii": False},
    {"category": "intraday_snapshot", "description": "Intraday ad/social snapshots", "retention_days": 90, "action": "DELETE", "pii": False},
    {"category": "content_performance_snapshot", "description": "Social content performance snapshots", "retention_days": 730, "action": "ARCHIVE", "pii": False},
    {"category": "rule_evaluation", "description": "Rule evaluation history", "retention_days": 730, "action": "ARCHIVE", "pii": False},
    {"category": "ai_trace", "description": "AI traces and model IO", "retention_days": 30, "action": "DELETE", "pii": False},
    {"category": "execution_audit", "description": "Execution audit evidence (long-term)", "retention_days": 2555, "action": "ARCHIVE", "pii": False},
    {"category": "approval_history", "description": "Approval history (long-term)", "retention_days": 2555, "action": "ARCHIVE", "pii": False},
    {"category": "customer_pii", "description": "Customer PII (delete on request)", "retention_days": 0, "action": "ANONYMIZE", "pii": True},
    {"category": "audit_logs", "description": "Application audit logs", "retention_days": 730, "action": "ARCHIVE", "pii": False},
]


async def seed_retention_policies(db: AsyncSession) -> int:
    created = 0
    for seed in RETENTION_SEEDS:
        existing = (await db.execute(select(RetentionPolicy).where(RetentionPolicy.category == seed["category"]))).scalar_one_or_none()
        if existing is not None:
            continue
        db.add(RetentionPolicy(**seed))
        created += 1
    if created:
        await db.flush()
    return created


async def list_policies(db: AsyncSession) -> List[Dict[str, Any]]:
    rows = (await db.execute(select(RetentionPolicy).order_by(RetentionPolicy.category))).scalars().all()
    return [
        {
            "category": r.category,
            "description": r.description,
            "retention_days": r.retention_days,
            "archive_after_days": r.archive_after_days,
            "action": r.action,
            "pii": r.pii,
            "enabled": r.enabled,
        }
        for r in rows
    ]
