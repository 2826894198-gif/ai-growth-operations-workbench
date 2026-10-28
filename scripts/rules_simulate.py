"""Simulate a candidate parameter change for a rule (no mutation)."""

import asyncio
import os
import sys
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./demo_data.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.database import async_session_factory  # noqa: E402
from app.rules.simulation.simulator import simulate_rule  # noqa: E402


async def main(rule_key: str, params: dict, days: int) -> int:
    end = date.today()
    start = end - timedelta(days=max(days - 1, 0))
    async with async_session_factory() as db:
        result = await simulate_rule(db, rule_key, params, start.isoformat(), end.isoformat())
    print(result)
    return 0


if __name__ == "__main__":
    rule = sys.argv[1] if len(sys.argv) > 1 else "META_NO_PURCHASE_BURN"
    params = {}
    days = 30
    args = sys.argv[2:]
    index = 0
    while index < len(args):
        if args[index] == "--param" and index + 1 < len(args):
            key, value = args[index + 1].split("=", 1)
            try:
                params[key] = float(value)
            except ValueError:
                params[key] = value
            index += 2
        elif args[index] == "--days" and index + 1 < len(args):
            days = int(args[index + 1])
            index += 2
        else:
            index += 1
    sys.exit(asyncio.run(main(rule, params, days)))
