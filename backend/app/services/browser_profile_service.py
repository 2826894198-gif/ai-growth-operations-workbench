import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.adspower.profile_service import AdsPowerProfileService
from app.models.browser_profile import BrowserProfile
from app.models.browser_profile_audit import BrowserProfileAudit
from app.models.browser_task import BrowserTask
from app.models.environment_health import EnvironmentHealthCheck
from app.schemas.browser_profile import BrowserProfileCreate, BrowserProfileUpdate

logger = logging.getLogger(__name__)

AUDIT_FIELDS = ("proxy", "country", "timezone", "language", "browser_engine", "fingerprint_config")


class BrowserProfileService:
    def __init__(self, adspower: AdsPowerProfileService):
        self.adspower = adspower

    async def list_profiles(
        self, db: AsyncSession, profile_type: Optional[str] = None, status: Optional[str] = None
    ) -> List[BrowserProfile]:
        query = select(BrowserProfile).order_by(BrowserProfile.created_at.asc())
        if profile_type:
            query = query.where(BrowserProfile.profile_type == profile_type)
        if status:
            query = query.where(BrowserProfile.status == status)
        return list((await db.execute(query)).scalars().all())

    async def get_profile(self, db: AsyncSession, profile_id: str) -> Optional[BrowserProfile]:
        return (
            await db.execute(select(BrowserProfile).where(BrowserProfile.id == profile_id))
        ).scalar_one_or_none()

    async def create_profile(
        self, db: AsyncSession, data: BrowserProfileCreate, operator: str = "system", source: str = "api"
    ) -> BrowserProfile:
        return await self.adspower.create_profile(db, data, operator=operator, source=source)

    async def sync(self, db: AsyncSession) -> int:
        return await self.adspower.sync_profiles(db)

    async def update_profile(
        self,
        db: AsyncSession,
        profile: BrowserProfile,
        data: BrowserProfileUpdate,
        operator: str = "system",
        source: str = "api",
    ) -> BrowserProfile:
        changes: Dict[str, Any] = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            old = getattr(profile, field)
            if old != value:
                if field in AUDIT_FIELDS:
                    db.add(
                        BrowserProfileAudit(
                            profile_id=profile.id,
                            field=field,
                            old_value=str(old) if old is not None else None,
                            new_value=str(value) if value is not None else None,
                            operator=operator,
                            source=source,
                        )
                    )
                setattr(profile, field, value)
        await db.commit()
        await db.refresh(profile)
        return profile

    async def detail(self, db: AsyncSession, profile_id: str) -> Optional[Dict[str, Any]]:
        profile = await self.get_profile(db, profile_id)
        if profile is None:
            return None
        audits = list(
            (
                await db.execute(
                    select(BrowserProfileAudit)
                    .where(BrowserProfileAudit.profile_id == profile_id)
                    .order_by(BrowserProfileAudit.created_at.desc())
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )
        checks = list(
            (
                await db.execute(
                    select(EnvironmentHealthCheck)
                    .where(EnvironmentHealthCheck.profile_id == profile_id)
                    .order_by(EnvironmentHealthCheck.created_at.desc())
                    .limit(20)
                )
            )
            .scalars()
            .all()
        )
        tasks = list(
            (
                await db.execute(
                    select(BrowserTask)
                    .where(BrowserTask.profile_id == profile_id)
                    .order_by(BrowserTask.created_at.desc())
                    .limit(20)
                )
            )
            .scalars()
            .all()
        )
        return {"profile": profile, "audits": audits, "health_checks": checks, "recent_tasks": tasks}
