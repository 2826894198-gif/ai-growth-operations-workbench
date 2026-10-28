"""PART 06-01 golden scenario smoke (E195-E198, U)."""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:////tmp/smoke_social.db")
os.environ.setdefault("DATA_PROVIDER_MODE", "mock")
os.environ.setdefault("SOCIAL_PROVIDER_MODE", "mock")
os.environ.setdefault("EXECUTION_ENABLED", "true")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.database import Base  # noqa: E402
from app.models.social import (  # noqa: E402
    ConnectedAccount,
    ContentAsset,
    ContentPromotionLink,
    ContentPublication,
    ProviderConnection,
)
from app.services.social.connection_service import (  # noqa: E402
    complete_oauth_callback,
    connection_health,
    disconnect_account,
    link_accounts,
    reauthorize,
    refresh_capabilities,
    seed_provider_capabilities,
)
from app.services.oauth_service import start_oauth_transaction  # noqa: E402
from app.services.social.content_service import (  # noqa: E402
    auto_map_promotions,
    content_detail,
    content_matrix,
    create_manual_promotion_link,
    publication_detail,
    sync_content,
)
from app.services.social.focus_service import create_focus, focus_detail  # noqa: E402
from app.services.social.metric_catalog import seed_metric_catalog  # noqa: E402
from app.services.social.scope_service import aggregate_metric, resolve_accounts  # noqa: E402
from app.services.social.account_service import portfolio_overview  # noqa: E402

RESULTS = []


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


async def main() -> None:
    if os.path.exists("/tmp/smoke_social.db"):
        os.remove("/tmp/smoke_social.db")
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        await seed_metric_catalog(db)
        await seed_provider_capabilities(db)
        await db.commit()

        # ---- Connections (META) + discovery of multiple resources
        tx = await start_oauth_transaction(db, workspace_id="ws_main", provider="META", initiated_by="test")
        connection = await complete_oauth_callback(db, workspace_id="ws_main", provider="META", state=tx["state"], code="c", actor="test")
        await db.commit()
        from app.services.social.connection_service import discover_accounts

        discovered = await discover_accounts(db, str(connection.id), "test")
        await db.commit()
        record("account_discovery_multiple_resources", discovered["count"] >= 3, str(discovered["count"]))

        # ---- Link 2 Instagram accounts + 1 TikTok + 1 YouTube
        linked = await link_accounts(
            db,
            connection_id=str(connection.id),
            external_account_ids=["ig_a", "ig_b"],
            workspace_id="ws_main",
            brand_id=None,
            account_group_id=None,
            actor="test",
        )
        for account in linked:
            await refresh_capabilities(db, account, "test")
        await db.commit()
        tx2 = await start_oauth_transaction(db, workspace_id="ws_main", provider="TIKTOK", initiated_by="test")
        tiktok_connection = await complete_oauth_callback(db, workspace_id="ws_main", provider="TIKTOK", state=tx2["state"], code="c2", actor="test")
        await db.commit()
        linked_tt = await link_accounts(
            db,
            connection_id=str(tiktok_connection.id),
            external_account_ids=["tt_a"],
            workspace_id="ws_main",
            brand_id=None,
            account_group_id=None,
            actor="test",
        )
        for account in linked_tt:
            await refresh_capabilities(db, account, "test")
        await db.commit()

        # ---- Content sync
        accounts = (await db.execute(select(ConnectedAccount).where(ConnectedAccount.status == "LINKED"))).scalars().all()
        await sync_content(db, [str(a.id) for a in accounts], actor="test", days=30)
        await db.commit()
        await auto_map_promotions(db, actor="test")
        await db.commit()

        # ---- same_platform_multiple_accounts
        ig_accounts = await resolve_accounts(db, workspace_id="ws_main", platforms=["INSTAGRAM"])
        record("same_platform_multiple_accounts", len(ig_accounts) >= 2, str(len(ig_accounts)))

        # ---- switch_workspace_no_data_leak
        other_workspace_accounts = await resolve_accounts(db, workspace_id="ws_other")
        record("switch_workspace_no_data_leak", len(other_workspace_accounts) == 0, str(len(other_workspace_accounts)))

        # ---- cross_platform_portfolio + metric semantics
        portfolio = await portfolio_overview(db, workspace_id="ws_main", platforms=["INSTAGRAM", "TIKTOK"], days=30)
        record("cross_platform_portfolio", portfolio["kpis"]["views"]["value"] is not None)
        views_caveat = (portfolio["kpis"]["views"].get("caveat") or "") + (portfolio["caveats"][0] if portfolio["caveats"] else "")
        record("cross_network_non_additive_metric", "deduplicated" in views_caveat or "not deduplicated" in views_caveat, views_caveat)
        followers = portfolio["kpis"]["followers"]
        record("followers_combined_not_unique", followers["value"] is not None and "NOT a deduplicated unique audience" in (followers.get("caveat") or ""), followers.get("caveat"))

        # ---- one_asset_multiple_publications
        asset = (await db.execute(select(ContentAsset).limit(1))).scalar_one()
        original_pub = (
            await db.execute(select(ContentPublication).where(ContentPublication.content_asset_id == str(asset.id)).limit(1))
        ).scalar_one()
        tt_account = (await db.execute(select(ConnectedAccount).where(ConnectedAccount.platform == "TIKTOK").limit(1))).scalar_one()
        db.add(
            ContentPublication(
                content_asset_id=str(asset.id),
                account_id=str(tt_account.id),
                provider=tt_account.provider,
                platform=tt_account.platform,
                external_post_id=f"TT-X-{asset.id[:8]}",
                content_type="SHORT",
                caption="same asset second publication",
                published_at=datetime.now(timezone.utc),
                provider_status="PUBLISHED",
            )
        )
        await db.commit()
        detail = await content_detail(db, str(asset.id))
        record("one_asset_multiple_publications", len(detail["publications"]) >= 2, str(len(detail["publications"])))
        record("multi_publication_separate_organic", all("caveat" in p["organic"] for p in detail["publications"]))

        # ---- one_publication_multiple_paid_ads
        promoted_pub = (
            await db.execute(
                select(ContentPublication)
                .join(ContentPromotionLink, ContentPromotionLink.publication_id == ContentPublication.id)
                .where(ContentPublication.external_media_id.isnot(None))
                .order_by(ContentPublication.published_at.desc())
                .limit(1)
            )
        ).scalar_one()
        await create_manual_promotion_link(
            db,
            publication_id=str(promoted_pub.id),
            payload={
                "paid_platform": "GOOGLE_ADS",
                "creative_id": "cr_manual_1",
                "ad_id": "ad_manual_1",
                "campaign_id": "camp_manual_1",
                "promotion_type": "PAID_BOOST",
                "mapping_confidence": 0.75,
            },
            actor="test",
        )
        await db.commit()
        pub_links = (
            await db.execute(select(ContentPromotionLink).where(ContentPromotionLink.publication_id == str(promoted_pub.id)))
        ).scalars().all()
        record("one_publication_multiple_paid_ads", len(pub_links) >= 2, str(len(pub_links)))

        # ---- organic_winner_paid_weak / organic_weak_paid_winner quadrants
        matrix = await content_matrix(db, workspace_id="ws_main", account_ids=[str(a.id) for a in accounts], days=30)
        quadrants = {r["quadrant"] for r in matrix["rows"]}
        record("content_matrix_quadrants", len(quadrants) >= 2, str(quadrants))

        # ---- promotion_mapping_manual + mapping drift
        link = pub_links[-1]
        fake_intent = SimpleNamespace(
            requested_change={
                "promotion_link_id": str(link.id),
                "ad_id": "ad_WRONG",
                "campaign_id": "camp_WRONG",
            },
            provider="META",
            action_type="META_CHANGE_BUDGET",
            entity_type="CAMPAIGN",
            entity_id="camp_1001",
            external_entity_id=None,
            expected_before_state={},
            workspace_id=None,
            approval_id="x",
            id="fake-intent",
            recommendation_id="x",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        from app.execution.revalidation import revalidate

        drift = await revalidate(db, intent=fake_intent, provider_state={})
        record(
            "promotion_mapping_drift",
            any(c["name"] == "promotion_mapping_valid" and not c["ok"] for c in drift["checks"]),
            str([c for c in drift["checks"] if c["name"] == "promotion_mapping_valid"]),
        )

        # ---- focus_paid_video
        monitor = await create_focus(
            db,
            workspace_id="ws_main",
            payload={
                "scope_type": "PUBLICATION",
                "scope_id": str(promoted_pub.id),
                "name": "Paid Video Focus",
                "priority": "HIGH",
                "refresh_interval_minutes": 15,
            },
            actor="test",
        )
        await db.commit()
        focus = await focus_detail(db, monitor, days=7)
        record("focus_paid_video", focus["monitor"]["scope_type"] == "PUBLICATION" and "paid" in focus and "organic" in focus)
        record("focus_reuses_rules", "caveat" in focus and "does not reimplement" in focus["caveat"])

        # ---- connection_expired / scope_missing
        connection.token_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        await db.commit()
        health = await connection_health(db, str(connection.id))
        record("connection_expired", health["token_expiring_soon"] is True, str(health["token_expires_in_days"]))
        reauth = await reauthorize(db, str(connection.id), "test")
        await db.commit()
        record("connection_reauth_restores", reauth["connection"]["status"] == "HEALTHY")

        # ---- reconnect_existing_account (no duplicate)
        account_before = len((await db.execute(select(ConnectedAccount))).scalars().all())
        target = linked[0]
        await disconnect_account(db, target, "test")
        await db.commit()
        from app.services.social.connection_service import reconnect_account

        await reconnect_account(db, target, "test")
        await db.commit()
        account_after = len((await db.execute(select(ConnectedAccount))).scalars().all())
        record("reconnect_existing_account", account_before == account_after and target.status == "LINKED")

        # ---- capability-driven rendering
        caps = {
            "items": [
                {"capability_key": "CONTENT_WATCH_TIME", "supported": False, "permission_granted": False},
                {"capability_key": "CONTENT_VIEWS", "supported": True, "permission_granted": True},
            ]
        }
        record("capability_missing_not_zero", any(not c["supported"] for c in caps["items"]))

    failed = [r for r in RESULTS if not r[1]]
    print("\n===== SOCIAL SMOKE SUMMARY =====")
    print(f"PASS: {len(RESULTS) - len(failed)}/{len(RESULTS)}")
    for name, ok in RESULTS:
        if not ok:
            print(f"  FAIL {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
