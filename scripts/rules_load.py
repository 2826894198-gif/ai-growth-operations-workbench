"""Load rule packs and seed parameters into the database."""

import asyncio
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./demo_data.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select  # noqa: E402

from app.core.database import async_session_factory  # noqa: E402
from app.models.rules import RuleDefinition, RuleParameter  # noqa: E402
from app.rules.audit import audit  # noqa: E402
from app.rules.registry import get_seed_parameters, load_defaults, load_rule_packs  # noqa: E402


async def main() -> int:
    status = os.environ.get("RULE_STATUS", "SHADOW")
    defaults = load_defaults()
    async with async_session_factory() as db:
        for rule in load_rule_packs():
            existing = (
                await db.execute(
                    select(RuleDefinition).where(
                        RuleDefinition.rule_key == rule["rule_key"],
                        RuleDefinition.version == 1,
                    )
                )
            ).scalar_one_or_none()
            values = dict(
                name=rule["name"],
                category=rule["category"],
                platform=rule.get("platform"),
                evaluation_level=rule.get("evaluation_level", "AD"),
                severity=rule.get("severity", "MEDIUM"),
                schedule_group=rule.get("schedule_group", "DAILY"),
                conditions=rule.get("conditions"),
                guards=rule.get("guards"),
                action_template=rule.get("action"),
                required_capabilities=rule.get("required_capabilities", []),
                cooldown_minutes=rule.get("cooldown_minutes", 1440),
                minimum_confidence=rule.get("minimum_confidence", 0.4),
                auto_execution_eligible=rule.get("auto_execution_eligible", False),
            )
            if existing is None:
                db.add(
                    RuleDefinition(
                        rule_key=rule["rule_key"],
                        version=1,
                        status=status,
                        enabled=True,
                        created_by="cli",
                        **values,
                    )
                )
                await audit(db, actor="cli", action="rule_created", target=rule["rule_key"])
            else:
                for key, value in values.items():
                    setattr(existing, key, value)
                if os.environ.get("RULE_FORCE_STATUS"):
                    existing.status = status
                await audit(db, actor="cli", action="rule_updated", target=rule["rule_key"])

            for param_key, value in get_seed_parameters(rule["rule_key"], defaults).items():
                existing_param = (
                    await db.execute(
                        select(RuleParameter).where(
                            RuleParameter.rule_key == rule["rule_key"],
                            RuleParameter.parameter_key == param_key,
                            RuleParameter.scope_type == "GLOBAL",
                            RuleParameter.valid_to.is_(None),
                        )
                    )
                ).scalar_one_or_none()
                if existing_param is None:
                    db.add(
                        RuleParameter(
                            rule_key=rule["rule_key"],
                            parameter_key=param_key,
                            scope_type="GLOBAL",
                            value=value,
                            value_type="number" if isinstance(value, (int, float)) else "string",
                            source="SEED",
                        )
                    )
        await db.commit()
    print(f"loaded {len(load_rule_packs())} rules with status={status}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
