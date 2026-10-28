"""PART 06 CLI: dry-run / shadow execution helpers.

Usage:
    cd backend && .venv/bin/python ../scripts/execution_cli.py dry-run INTENT_ID
    cd backend && .venv/bin/python ../scripts/execution_cli.py shadow INTENT_ID
"""

import asyncio
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///../demo_data.db")
os.environ.setdefault("DATA_PROVIDER_MODE", "mock")
os.environ.setdefault("EXECUTION_ENABLED", "true")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.database import Base  # noqa: E402
from app.execution.engine import dry_run_intent, shadow_execute_intent  # noqa: E402


async def main(command: str, intent_id: str) -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        if command == "dry-run":
            result = await dry_run_intent(db, intent_id=intent_id)
            print("DRY RUN", result)
        elif command == "shadow":
            result = await shadow_execute_intent(db, intent_id=intent_id)
            print("SHADOW", result)
        await db.commit()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
