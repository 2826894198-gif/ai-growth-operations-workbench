"""Seed Part 05 product demo data (workspace, flags, notifications, experiment, brief)."""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./demo_data.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.database import Base  # noqa: E402
from app.models.product import (  # noqa: E402
    CreativeBrief,
    Experiment,
    FeatureFlag,
    Notification,
    Workspace,
)


async def main() -> int:
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        if (await db.execute(select(Workspace).limit(1))).scalar_one_or_none() is None:
            db.add(Workspace(name="Demo Brand", timezone="America/New_York", reporting_currency="USD"))
        flags = {
            "creative_ai": True,
            "competitor_intelligence": False,
            "ai_memory": True,
            "experiments": True,
            "execution_preview": False,
        }
        for key, enabled in flags.items():
            if (await db.execute(select(FeatureFlag).where(FeatureFlag.flag_key == key))).scalar_one_or_none() is None:
                db.add(FeatureFlag(flag_key=key, enabled=enabled))
        if (await db.execute(select(Notification).limit(1))).scalar_one_or_none() is None:
            now = datetime.now(timezone.utc)
            db.add_all(
                [
                    Notification(type="RECOMMENDATION", severity="HIGH", title="Creative fatigue detected", body="META ad 238471444402 CTR -28%", entity_type="AD", entity_id="238471444402"),
                    Notification(type="APPROVAL_REQUIRED", severity="MEDIUM", title="Review required", body="CPA overshoot on 238471444403"),
                    Notification(type="DATA_FAILURE", severity="CRITICAL", title="Google data delayed", body="Last sync 42 minutes ago"),
                    Notification(type="CRITICAL_ALERT", severity="CRITICAL", title="Blended ROAS below break-even", body="0.31x vs 0.50 target", created_at=now - timedelta(hours=1)),
                ]
            )
        if (await db.execute(select(Experiment).limit(1))).scalar_one_or_none() is None:
            db.add(
                Experiment(
                    name="CTA Test: SHOP_NOW vs LEARN_MORE",
                    hypothesis="Tactile cassette-loading hook with SHOP_NOW CTA lifts checkout completion",
                    variable="CTA",
                    control="LEARN_MORE",
                    treatment="SHOP_NOW",
                    primary_metric="checkout_to_purchase",
                    guardrail_metrics=["cpa", "roas"],
                    status="ACTIVE",
                    start_at=datetime.now(timezone.utc) - timedelta(days=3),
                    end_at=datetime.now(timezone.utc) + timedelta(days=11),
                    protected_by_rule=True,
                )
            )
        if (await db.execute(select(CreativeBrief).limit(1))).scalar_one_or_none() is None:
            db.add(
                CreativeBrief(
                    title="Nostalgia Bedroom Hook v2",
                    objective="Restore CTR for fatigued prospecting ads",
                    hypothesis="Bedroom nostalgia + tactile cassette loading may restore attention",
                    hook="Close-up cassette insert with audible click",
                    first_3_seconds="Insert cassette, close lid, press play",
                    scene_sequence=["BEDROOM_NOSTALGIA", "DESK_SETUP", "PLAY_BUTTON"],
                    product_actions=["CASSETTE_INSERT", "LID_CLOSE", "PLAY_BUTTON"],
                    proof=["2 recent winners used indoor nostalgic settings"],
                    cta="SHOP_NOW",
                    audio_direction="lo-fi nostalgic",
                    duration="15s",
                    aspect_ratio="9:16",
                    status="DRAFT",
                )
            )
        await db.commit()
        print("product demo seeded")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
