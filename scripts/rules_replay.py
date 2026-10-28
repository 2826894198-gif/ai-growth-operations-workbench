"""Replay a rule over the last N days (approximate point-in-time)."""

import asyncio
import os
import sys
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./demo_data.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.database import async_session_factory  # noqa: E402
from app.rules.simulation.replay import replay_rule  # noqa: E402


async def main(rule_key: str, days: int) -> int:
    end = date.today()
    start = end - timedelta(days=max(days - 1, 0))
    async with async_session_factory() as db:
        result = await replay_rule(db, rule_key, start.isoformat(), end.isoformat())
    print(result)
    return 0


if __name__ == "__main__":
    rule = sys.argv[1] if len(sys.argv) > 1 else "META_NO_PURCHASE_BURN"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    sys.exit(asyncio.run(main(rule, days)))
