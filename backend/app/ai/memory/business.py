from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AIBusinessMemory


async def list_memories(db: AsyncSession, status: Optional[str] = None, limit: int = 100) -> list:
    query = select(AIBusinessMemory).order_by(AIBusinessMemory.created_at.desc()).limit(limit)
    if status:
        query = query.where(AIBusinessMemory.status == status)
    rows = (await db.execute(query)).scalars().all()
    return [
        {
            "id": str(m.id),
            "memory_type": m.memory_type,
            "statement": m.statement,
            "confidence": m.confidence,
            "evidence_refs": m.evidence_refs,
            "status": m.status,
            "review_after": m.review_after.isoformat() if m.review_after else None,
        }
        for m in rows
    ]


async def approve_memory(db: AsyncSession, memory_id: str, approved_by: str = "operator") -> dict:
    row = (await db.execute(select(AIBusinessMemory).where(AIBusinessMemory.id == memory_id))).scalar_one_or_none()
    if row is None:
        return {"error": "not found"}
    row.status = "ACTIVE"
    row.approved_by = approved_by
    row.valid_from = datetime.now(timezone.utc)
    await db.commit()
    return {"memory_id": memory_id, "status": "ACTIVE"}
