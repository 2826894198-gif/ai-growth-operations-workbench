"""PART 06-01 demo seed: workspace/brands/connections/accounts/content/focus.

Usage:
    cd backend && DATABASE_URL=sqlite+aiosqlite:///../demo_data.db \
        .venv/bin/python ../scripts/seed_social_demo.py
"""

import asyncio
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///../demo_data.db")
os.environ.setdefault("DATA_PROVIDER_MODE", "mock")
os.environ.setdefault("SOCIAL_PROVIDER_MODE", "mock")
os.environ.setdefault("EXECUTION_ENABLED", "true")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.database import Base  # noqa: E402
from app.execution.policies import seed_default_policies  # noqa: E402
from app.models.social import (  # noqa: E402
    AccountGroup,
    Brand,
    ConnectedAccount,
    ContentAsset,
    ContentPromotionLink,
    ContentPublication,
    FactContentPerformanceDaily,
    FocusMonitor,
    ProviderConnection,
    SavedScope,
)
from app.services.social.connection_service import (  # noqa: E402
    complete_oauth_callback,
    link_accounts,
    refresh_capabilities,
    seed_provider_capabilities,
)
from app.services.oauth_service import start_oauth_transaction  # noqa: E402
from app.services.social.content_service import auto_map_promotions, sync_content  # noqa: E402
from app.services.social.focus_service import create_focus, create_watchlist  # noqa: E402
from app.services.social.metric_catalog import seed_metric_catalog  # noqa: E402
from app.services.metric_service import seed_metric_definitions  # noqa: E402
from app.services.provider_control_plane import seed_provider_manifests  # noqa: E402
from app.services.auth_service import seed_demo_admin  # noqa: E402
from app.services import entity_service  # noqa: E402


async def main() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        await seed_metric_catalog(db)
        await seed_metric_definitions(db)
        await seed_provider_capabilities(db)
        await seed_provider_manifests(db)
        await seed_default_policies(db, actor="seed")
        await seed_demo_admin(db)
        await db.commit()

        brand = (await db.execute(select(Brand).where(Brand.slug == "recollect"))).scalar_one_or_none()
        if brand is None:
            brand = Brand(
                workspace_id="ws_main",
                name="RECOLLECT",
                slug="recollect",
                default_timezone="America/New_York",
                reporting_currency="USD",
            )
            db.add(brand)
            await db.flush()
            db.add(AccountGroup(workspace_id="ws_main", brand_id=str(brand.id), name="US Main Accounts", description="Primary US operating accounts"))
            db.add(AccountGroup(workspace_id="ws_main", brand_id=str(brand.id), name="Organic Accounts"))
            db.add(AccountGroup(workspace_id="ws_main", brand_id=str(brand.id), name="Paid Accounts"))
            await db.commit()
        brand_id = str(brand.id)

        connections = {}
        for provider in ("META", "TIKTOK", "YOUTUBE"):
            existing = (
                await db.execute(
                    select(ProviderConnection).where(
                        ProviderConnection.provider == provider,
                        ProviderConnection.workspace_id == "ws_main",
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                connections[provider] = existing
                continue
            tx = await start_oauth_transaction(db, workspace_id="ws_main", provider=provider, initiated_by="seed")
            connection = await complete_oauth_callback(
                db,
                workspace_id="ws_main",
                provider=provider,
                state=tx["state"],
                code="seed-code",
                actor="seed",
            )
            connections[provider] = connection
        await db.commit()

        desired = {
            "META": ["ig_a", "ig_b", "fb_page_a"],
            "TIKTOK": ["tt_a", "tt_b"],
            "YOUTUBE": ["yt_a"],
        }
        for provider, external_ids in desired.items():
            connection = connections[provider]
            linked = await link_accounts(
                db,
                connection_id=str(connection.id),
                external_account_ids=external_ids,
                workspace_id="ws_main",
                brand_id=brand_id,
                account_group_id=None,
                actor="seed",
            )
            for account in linked:
                await refresh_capabilities(db, account, actor="seed")
        await db.commit()

        accounts = (await db.execute(select(ConnectedAccount).where(ConnectedAccount.status == "LINKED"))).scalars().all()
        demo_account_ownership = {
            ("INSTAGRAM", "INSTAGRAM_BUSINESS"): {"account_scope": "COMPANY", "owner_label": "公司大号", "channel_role": "主阵地"},
            ("FACEBOOK", "FACEBOOK_PAGE"): {"account_scope": "COMPANY", "owner_label": "公司小号", "channel_role": "社群承接"},
            ("TIKTOK", "TIKTOK_BUSINESS"): {"account_scope": "COMPANY", "owner_label": "公司小号2", "channel_role": "短视频主阵地"},
            ("YOUTUBE", "YOUTUBE_CHANNEL"): {"account_scope": "COMPANY", "owner_label": "公司小号3", "channel_role": "长视频归档"},
            ("INSTAGRAM", "INSTAGRAM_CREATOR"): {"account_scope": "EMPLOYEE", "owner_label": "员工1", "channel_role": "个人内容账号"},
            ("TIKTOK", "TIKTOK_CREATOR"): {"account_scope": "EMPLOYEE", "owner_label": "员工2", "channel_role": "个人内容账号"},
        }
        for account in accounts:
            assignment = demo_account_ownership.get((account.platform, account.account_type))
            if assignment:
                account.meta = {**(account.meta or {}), **assignment}
        await db.flush()
        sync_result = await sync_content(db, [str(a.id) for a in accounts], actor="seed", days=30)
        await db.commit()

        # Canonical entity registry: connected accounts + publications
        for account in accounts:
            await entity_service.resolve_or_create_entity(
                db,
                workspace_id="ws_main",
                brand_id=account.brand_id,
                entity_type="CONNECTED_ACCOUNT",
                display_name=f"{account.platform}:{account.username}",
                external_refs=[
                    {
                        "provider": account.provider,
                        "connected_account_id": str(account.id),
                        "external_type": "PRIMARY",
                        "external_id": account.external_account_id,
                    }
                ],
            )
        publications = (await db.execute(select(ContentPublication))).scalars().all()
        for publication in publications:
            await entity_service.resolve_or_create_entity(
                db,
                workspace_id="ws_main",
                brand_id=None,
                entity_type="CONTENT_PUBLICATION",
                display_name=f"{publication.platform}:{publication.external_post_id}",
                external_refs=[
                    {
                        "provider": publication.provider,
                        "connected_account_id": str(publication.account_id),
                        "external_type": "PRIMARY",
                        "external_id": publication.external_post_id,
                    }
                ],
            )
        await db.commit()

        mapped = await auto_map_promotions(db, actor="seed")
        await db.commit()

        watchlist = await create_watchlist(db, workspace_id="ws_main", name="My Focus", description="Default focus watchlist", actor="seed")
        publications = (await db.execute(select(ContentPublication).order_by(ContentPublication.published_at.desc()).limit(3))).scalars().all()
        focus_ids = []
        for publication in publications:
            monitor = await create_focus(
                db,
                workspace_id="ws_main",
                payload={
                    "scope_type": "PUBLICATION",
                    "scope_id": str(publication.id),
                    "name": f"Watch {str(publication.caption or '')[:40]}",
                    "priority": "HIGH" if publication.content_type == "REEL" else "WATCH",
                    "refresh_interval_minutes": 15,
                    "baseline_strategy": "FIRST_24H",
                    "watchlist_id": str(watchlist.id),
                },
                actor="seed",
            )
            focus_ids.append(str(monitor.id))
        await db.commit()

        existing_scope = (
            await db.execute(select(SavedScope).where(SavedScope.workspace_id == "ws_main", SavedScope.name == "US All Accounts"))
        ).scalar_one_or_none()
        if existing_scope is None:
            db.add(
                SavedScope(
                    workspace_id="ws_main",
                    name="US All Accounts",
                    scope={"workspace_ids": ["ws_main"], "platforms": ["INSTAGRAM", "TIKTOK", "YOUTUBE"], "account_ids": []},
                    created_by="seed",
                    is_favorite=True,
                )
            )
        await db.commit()

        counts = {
            "brands": len((await db.execute(select(Brand))).scalars().all()),
            "accounts": len(accounts),
            "assets": len((await db.execute(select(ContentAsset))).scalars().all()),
            "publications": len((await db.execute(select(ContentPublication))).scalars().all()),
            "daily_facts": len((await db.execute(select(FactContentPerformanceDaily))).scalars().all()),
            "promotion_links": len((await db.execute(select(ContentPromotionLink))).scalars().all()),
            "focus_monitors": len((await db.execute(select(FocusMonitor))).scalars().all()),
        }
        print("SEED SUMMARY", counts)
        print("SYNC", sync_result)
        print("AUTO MAPPED", mapped)
        print("FOCUS", focus_ids)


if __name__ == "__main__":
    asyncio.run(main())
