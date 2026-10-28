"""Run rule evaluation (manual trigger)."""

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./demo_data.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.database import async_session_factory  # noqa: E402
from app.rules.engine import run_evaluation  # noqa: E402


async def main(rule_keys: list, as_of: Optional[str] = None) -> int:
    from app.rules.registry import load_rule_packs

    packs = [r["rule_key"] for r in load_rule_packs()]
    expanded = []
    for key in rule_keys:
        if key.endswith("*"):
            prefix = key[:-1]
            expanded.extend([k for k in packs if k.startswith(prefix)])
        else:
            expanded.append(key)
    async with async_session_factory() as db:
        as_of_dt = datetime.fromisoformat(as_of.replace("Z", "+00:00")) if as_of else datetime.now(timezone.utc)
        run = await run_evaluation(db, trigger_type="MANUAL", rule_keys=expanded or None, as_of=as_of_dt)
        if run is None:
            print("no rules evaluated (check RULE_ENGINE_ENABLED and loaded rules)")
            return 1
        print(
            f"run={run.id} rules={run.rules_evaluated} entities={run.entities_evaluated} "
            f"triggered={run.triggered} suppressed={run.suppressed}"
        )
        return 0


if __name__ == "__main__":
    keys = [k for k in sys.argv[1:] if "=" not in k]
    as_of_value = None
    for arg in sys.argv[1:]:
        if arg.startswith("as_of="):
            as_of_value = arg.split("=", 1)[1]
    sys.exit(asyncio.run(main(keys, as_of_value)))
