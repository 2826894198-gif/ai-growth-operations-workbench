"""Seed governance foundations: metric definitions, provider manifests, demo admin."""

import asyncio
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///../demo_data.db")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.database import Base  # noqa: E402
from app.services.auth_service import seed_demo_admin  # noqa: E402
from app.services.metric_service import seed_metric_definitions  # noqa: E402
from app.services.provider_control_plane import seed_provider_manifests  # noqa: E402
from app.services.retention_service import seed_retention_policies  # noqa: E402


async def main() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        metrics = await seed_metric_definitions(db)
        manifests = await seed_provider_manifests(db)
        retention = await seed_retention_policies(db)
        user = await seed_demo_admin(db)
        await db.commit()
        print("governance seeded", {"metrics": metrics, "manifests": manifests, "retention": retention, "admin": user.email})


if __name__ == "__main__":
    asyncio.run(main())
