import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_secret
from app.integrations.adspower.client import AdsPowerClient
from app.integrations.adspower.mapper import ads_power_item_to_internal, build_create_payload
from app.models.browser_profile import BrowserProfile
from app.models.browser_profile_audit import BrowserProfileAudit
from app.models.mixins import new_uuid
from app.models.proxy import Proxy
from app.schemas.browser_profile import BrowserProfileCreate

logger = logging.getLogger(__name__)


class AdsPowerProfileService:
    """Unified control for AdsPower profile creation and reconciliation."""

    def __init__(self, client: AdsPowerClient):
        self.client = client

    async def sync_profiles(self, db: AsyncSession) -> int:
        page = 1
        page_size = 100
        synced = 0
        while True:
            data = await self.client.list_profiles({"page": page, "page_size": page_size})
            items = data.list or []
            for item in items:
                mapped = ads_power_item_to_internal(item.model_dump())
                provider_profile_id = mapped.get("provider_profile_id")
                existing = (
                    await db.execute(
                        select(BrowserProfile).where(
                            BrowserProfile.provider_profile_id == provider_profile_id
                        )
                    )
                ).scalar_one_or_none()
                if existing:
                    existing.name = mapped.get("name") or existing.name
                    existing.platform = mapped.get("platform") or existing.platform
                    existing.fingerprint_config = mapped.get("fingerprint_config")
                    existing.browser_engine = mapped.get("browser_engine") or existing.browser_engine
                    existing.os_type = mapped.get("os_type") or existing.os_type
                else:
                    db.add(
                        BrowserProfile(
                            provider="adspower",
                            provider_profile_id=provider_profile_id,
                            name=mapped.get("name") or provider_profile_id or "unknown",
                            profile_type="research",
                            status="INACTIVE",
                            fingerprint_config=mapped.get("fingerprint_config"),
                            country="US",
                        )
                    )
                synced += 1
            total = data.total or 0
            if not items or page * page_size >= total:
                break
            page += 1
        await db.commit()
        return synced

    async def create_profile(
        self,
        db: AsyncSession,
        create: BrowserProfileCreate,
        operator: str = "system",
        source: str = "api",
    ) -> BrowserProfile:
        proxy: Optional[Proxy] = None
        if create.proxy_id:
            proxy = (
                await db.execute(select(Proxy).where(Proxy.id == create.proxy_id))
            ).scalar_one_or_none()
            if proxy is None:
                raise ValueError("proxy not found")

        profile = BrowserProfile(
            provider="adspower",
            name=create.name,
            profile_type=create.profile_type,
            profile_no=create.profile_no,
            platform=create.platform,
            proxy_id=create.proxy_id,
            country=create.country or (proxy.country if proxy else "US"),
            region=create.region or (proxy.region if proxy else None),
            city=create.city or (proxy.city if proxy else None),
            timezone=create.timezone,
            language=create.language or "en-US",
            browser_engine=create.browser_engine,
            os_type=create.os_type,
            status="INACTIVE",
            fingerprint_config=None,
        )
        profile.id = new_uuid()
        payload = build_create_payload(
            profile,
            proxy,
            decrypt_secret(proxy.username_encrypted) if proxy else None,
            decrypt_secret(proxy.password_encrypted) if proxy else None,
        )
        result = await self.client.create_profile(payload)
        profile.provider_profile_id = result.profile_id
        db.add(profile)
        db.add(
            BrowserProfileAudit(
                profile_id=profile.id,
                field="profile.create",
                old_value=None,
                new_value=create.model_dump_json(),
                operator=operator,
                source=source,
            )
        )
        await db.commit()
        await db.refresh(profile)
        return profile
