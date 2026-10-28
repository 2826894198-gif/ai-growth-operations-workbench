"""Release records (PART 07 §155, §386)."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.governance import Release


async def record_release(
    db: AsyncSession,
    *,
    version: str,
    git_sha: str,
    environment: str,
    db_revision: Optional[str] = None,
    image_digests: Optional[Dict[str, Any]] = None,
    deployed_by: Optional[str] = None,
    notes: Optional[str] = None,
) -> Release:
    release = Release(
        version=version,
        git_sha=git_sha,
        image_digests=image_digests,
        db_revision=db_revision,
        deployed_by=deployed_by,
        deployed_at=datetime.now(timezone.utc),
        environment=environment,
        status="PENDING",
        notes=notes,
    )
    db.add(release)
    await db.flush()
    return release


async def list_releases(db: AsyncSession, environment: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    query = select(Release).order_by(Release.deployed_at.desc()).limit(limit)
    if environment:
        query = query.where(Release.environment == environment)
    rows = (await db.execute(query)).scalars().all()
    return [
        {
            "id": str(r.id),
            "version": r.version,
            "git_sha": r.git_sha,
            "db_revision": r.db_revision,
            "environment": r.environment,
            "status": r.status,
            "deployed_by": r.deployed_by,
            "deployed_at": r.deployed_at.isoformat() if r.deployed_at else None,
            "notes": r.notes,
        }
        for r in rows
    ]


async def update_release_status(db: AsyncSession, release_id: str, status: str) -> Release:
    release = (await db.execute(select(Release).where(Release.id == release_id))).scalar_one_or_none()
    if release is None:
        raise ValueError("release not found")
    release.status = status
    await db.flush()
    return release
