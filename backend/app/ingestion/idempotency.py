import logging
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def upsert_by(
    db: AsyncSession,
    model,
    unique_fields: List[str],
    values: Dict[str, Any],
) -> tuple:
    """Select-or-insert/update by unique key. Returns (inserted: bool, obj)."""
    filters = {field: values.get(field) for field in unique_fields}
    existing = (
        await db.execute(select(model).filter_by(**filters))
    ).scalar_one_or_none()
    if existing is None:
        obj = model(**values)
        db.add(obj)
        await db.flush()
        return True, obj
    for key, value in values.items():
        if key not in unique_fields and value is not None:
            setattr(existing, key, value)
    await db.flush()
    return False, existing
