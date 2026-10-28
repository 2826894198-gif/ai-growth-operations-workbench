from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ai import AIBusinessMemory


async def search_business_memory(db: AsyncSession, query: str, statuses=None, limit: int = 10) -> Dict[str, Any]:
    statuses = statuses or ["ACTIVE", "VERIFIED"]
    rows = (
        await db.execute(
            select(AIBusinessMemory)
            .where(AIBusinessMemory.status.in_(statuses), AIBusinessMemory.statement.ilike(f"%{query}%"))
            .limit(limit)
        )
    ).scalars().all()
    return {"memories": [{"id": str(m.id), "statement": m.statement, "confidence": m.confidence, "evidence_refs": m.evidence_refs, "status": m.status} for m in rows]}


async def write_business_memory(
    db: AsyncSession,
    statement: str,
    memory_type: str = "GENERAL",
    evidence_refs=None,
    confidence: float = 0.5,
    scope_type: str = "GLOBAL",
    scope_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Agents may only PROPOSE memory; approval moves it to ACTIVE."""
    status = "PROPOSED" if settings.ai_memory_require_approval else "ACTIVE"
    row = AIBusinessMemory(
        memory_type=memory_type,
        scope_type=scope_type,
        scope_id=scope_id,
        statement=statement,
        evidence_refs=evidence_refs or [],
        confidence=confidence,
        status=status,
        created_by_run_id=run_id,
        review_after=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.add(row)
    await db.commit()
    return {"memory_id": str(row.id), "status": status}


async def invalidate_memory(db: AsyncSession, memory_id: str) -> Dict[str, Any]:
    row = (await db.execute(select(AIBusinessMemory).where(AIBusinessMemory.id == memory_id))).scalar_one_or_none()
    if row is None:
        return {"error": "not found"}
    row.status = "INVALIDATED"
    await db.commit()
    return {"memory_id": memory_id, "status": "INVALIDATED"}
