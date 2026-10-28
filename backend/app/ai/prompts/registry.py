from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.project_paths import config_path
from app.models.ai import AIPrompt

PROMPT_ROOT = config_path("prompts")
AGENTS = ["supervisor", "performance", "creative", "search", "funnel", "competitor", "strategy", "reviewer"]


def load_prompt_file(agent: str, version: str = "v1") -> str:
    path = PROMPT_ROOT / agent / f"{version}.md"
    if not path.exists():
        raise FileNotFoundError(f"prompt missing: {path}")
    return path.read_text(encoding="utf-8")


async def sync_prompts(db: AsyncSession) -> int:
    count = 0
    for agent in AGENTS:
        content = load_prompt_file(agent)
        existing = (
            await db.execute(
                select(AIPrompt).where(AIPrompt.prompt_key == agent, AIPrompt.version == "v1")
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                AIPrompt(
                    prompt_key=agent,
                    version="v1",
                    agent_type=agent,
                    system_prompt=content,
                    status="ACTIVE",
                    output_schema_version="1",
                )
            )
            count += 1
    await db.commit()
    return count


async def get_prompt(db: AsyncSession, agent: str) -> Optional[AIPrompt]:
    return (
        await db.execute(
            select(AIPrompt)
            .where(AIPrompt.prompt_key == agent, AIPrompt.status == "ACTIVE")
            .order_by(AIPrompt.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
