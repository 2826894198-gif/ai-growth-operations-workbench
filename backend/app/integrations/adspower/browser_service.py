import logging
from datetime import datetime, timezone
from typing import Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.adspower.client import AdsPowerClient
from app.integrations.adspower.schemas import StartBrowserData
from app.models.browser_profile import BrowserProfile

logger = logging.getLogger(__name__)


class AdsPowerBrowserService:
    def __init__(self, client: AdsPowerClient):
        self.client = client

    async def start(self, db: AsyncSession, profile: BrowserProfile) -> StartBrowserData:
        if not profile.provider_profile_id:
            raise ValueError("profile has no AdsPower provider_profile_id")
        data = await self.client.start_browser(profile.provider_profile_id)
        profile.status = "RUNNING"
        profile.last_opened_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(profile)
        return data

    async def stop(self, db: AsyncSession, profile: BrowserProfile) -> None:
        if not profile.provider_profile_id:
            raise ValueError("profile has no AdsPower provider_profile_id")
        await self.client.stop_browser(profile.provider_profile_id)
        profile.status = "INACTIVE"
        profile.last_closed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(profile)

    async def status(self, profile: BrowserProfile) -> Tuple[bool, str]:
        running = profile.status == "RUNNING"
        return running, profile.status
